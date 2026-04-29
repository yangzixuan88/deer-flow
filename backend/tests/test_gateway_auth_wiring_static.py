"""R241-23G - Gateway auth wiring static validation (test-only, no runtime).

Scope: Verify app.py conditional auth wiring is correct by AST only.
NO app startup, NO DB, NO init_engine, NO HTTP server.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))


# ── Helpers ───────────────────────────────────────────────────────────────


def _parse_app() -> ast.Module:
    with open(BACKEND / "app/gateway/app.py", encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename="app.py")


def _find_auth_ifs(tree: ast.Module) -> list[ast.If]:
    """Find all If nodes that contain _auth_middleware_enabled or _auth_routes_enabled."""
    auth_ifs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            cond = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
            if "_auth_middleware_enabled" in cond or "_auth_routes_enabled" in cond:
                auth_ifs.append(node)
    return auth_ifs


def _get_calls_in_if(if_node: ast.If, attr: str) -> list[str]:
    """Get all Call node function.attr values inside an If block."""
    calls = []
    for node in ast.walk(if_node):
        if isinstance(node, ast.Call) and hasattr(node.func, "attr"):
            if node.func.attr == attr:
                calls.append(ast.unparse(node) if hasattr(ast, "unparse") else node.func.attr)
    return calls


# ── Test: AST parse ─────────────────────────────────────────────────────────


class TestAppPyAst:
    @pytest.fixture
    def tree(self):
        return _parse_app()

    def test_ast_parses(self, tree):
        assert tree is not None

    def test_create_app_exists(self, tree):
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        assert "create_app" in names


# ── Test: Feature flag structure ─────────────────────────────────────────────


class TestFeatureFlags:
    @pytest.fixture
    def tree(self):
        return _parse_app()

    def test_auth_middleware_flag_name_present(self, tree):
        src = open(BACKEND / "app/gateway/app.py", encoding="utf-8").read()
        assert "AUTH_MIDDLEWARE_ENABLED" in src

    def test_auth_routes_flag_name_present(self, tree):
        src = open(BACKEND / "app/gateway/app.py", encoding="utf-8").read()
        assert "AUTH_ROUTES_ENABLED" in src

    def test_flags_default_to_false(self, tree):
        src = open(BACKEND / "app/gateway/app.py", encoding="utf-8").read()
        # Both flags should use 'false' as default
        assert '"false"' in src or "'false'" in src


# ── Test: Conditional wiring structure ────────────────────────────────────────


class TestConditionalWiring:
    @pytest.fixture
    def tree(self):
        return _parse_app()

    def test_auth_if_blocks_exist(self, tree):
        auth_ifs = _find_auth_ifs(tree)
        assert len(auth_ifs) >= 2, f"Expected at least 2 auth If blocks (middleware + routes), got {len(auth_ifs)}"

    def test_middleware_if_contains_add_middleware(self, tree):
        auth_ifs = _find_auth_ifs(tree)
        for if_node in auth_ifs:
            cond = ast.unparse(if_node.test) if hasattr(ast, "unparse") else ""
            if "_auth_middleware_enabled" in cond:
                calls = _get_calls_in_if(if_node, "add_middleware")
                assert len(calls) >= 1, "middleware If block must contain app.add_middleware call"
                assert "AuthMiddleware" in calls[0]
                return
        pytest.fail("_auth_middleware_enabled If block not found")

    def test_routes_if_contains_include_router(self, tree):
        auth_ifs = _find_auth_ifs(tree)
        for if_node in auth_ifs:
            cond = ast.unparse(if_node.test) if hasattr(ast, "unparse") else ""
            if "_auth_routes_enabled" in cond:
                calls = _get_calls_in_if(if_node, "include_router")
                assert len(calls) >= 1, "routes If block must contain app.include_router call"
                assert "auth_router" in calls[0]
                return
        pytest.fail("_auth_routes_enabled If block not found")


# ── Test: No unconditional auth wiring ────────────────────────────────────────


class TestNoUnconditionalAuth:
    @pytest.fixture
    def tree(self):
        return _parse_app()

    def _get_all_mw_calls(self, func_node: ast.FunctionDef) -> list[tuple[str, bool]]:
        """Get all add_middleware calls with whether they're inside an If block."""
        results = []
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call) and hasattr(node.func, "attr") and node.func.attr == "add_middleware":
                src = ast.unparse(node) if hasattr(ast, "unparse") else ""
                # Check if this call is inside an If node
                inside_if = False
                for parent in ast.walk(func_node):
                    if parent is node:
                        continue
                    if isinstance(parent, ast.If):
                        for child in ast.walk(parent):
                            if child is node:
                                inside_if = True
                results.append((src, inside_if))
        return results

    def _get_all_ir_calls(self, func_node: ast.FunctionDef) -> list[tuple[str, bool]]:
        """Get all include_router calls with whether they're inside an If block."""
        results = []
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call) and hasattr(node.func, "attr") and node.func.attr == "include_router":
                src = ast.unparse(node) if hasattr(ast, "unparse") else ""
                inside_if = False
                for parent in ast.walk(func_node):
                    if parent is node:
                        continue
                    if isinstance(parent, ast.If):
                        for child in ast.walk(parent):
                            if child is node:
                                inside_if = True
                results.append((src, inside_if))
        return results

    def test_no_unconditional_auth_middleware(self, tree):
        """AuthMiddleware must NOT be added unconditionally."""
        create_app = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "create_app":
                create_app = node
                break

        mw_calls = self._get_all_mw_calls(create_app)
        auth_mw_unconditional = [(src, inside) for src, inside in mw_calls if "AuthMiddleware" in src and not inside]
        assert len(auth_mw_unconditional) == 0, f"Unconditional AuthMiddleware call found: {auth_mw_unconditional}"

    def test_no_unconditional_auth_router(self, tree):
        """auth_router must NOT be included unconditionally."""
        create_app = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "create_app":
                create_app = node
                break

        ir_calls = self._get_all_ir_calls(create_app)
        auth_ir_unconditional = [(src, inside) for src, inside in ir_calls if "auth_router" in src and not inside]
        assert len(auth_ir_unconditional) == 0, f"Unconditional auth_router call found: {auth_ir_unconditional}"


# ── Test: No production DB / init_engine wiring ───────────────────────────────


class TestNoProductionDbWiring:
    def test_no_init_engine_from_config_added(self):
        src = open(BACKEND / "app/gateway/app.py", encoding="utf-8").read()
        # init_engine_from_config already existed in the pre-existing auth-on-2.0-rc changes
        # This test only checks our patch didn't add NEW calls
        # We check by looking at the auth wiring section only
        lines = src.split("\n")
        auth_section = []
        in_auth = False
        for line in lines:
            if "Auth wiring" in line:
                in_auth = True
            if in_auth and ("def create_app" in line or "def _env_flag" in line):
                break
            if in_auth:
                auth_section.append(line)

        auth_src = "\n".join(auth_section)
        assert "init_engine_from_config" not in auth_src, "init_engine_from_config must not be in auth wiring section"
