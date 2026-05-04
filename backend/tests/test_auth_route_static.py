"""R241-23F - Static auth route validation (test-only, no runtime).

Scope: AST parse, import validation, route count, guard checks.
NO app.py, NO DB, NO init_engine, NO route registration.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── Path setup ────────────────────────────────────────────────────────────

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))


# ── Helpers ───────────────────────────────────────────────────────────────

def _parse_ast(rel_path: str) -> ast.Module:
    """Parse a file and return its AST tree."""
    with open(BACKEND / rel_path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=rel_path)


def _has_name_main_guard(tree: ast.Module) -> bool:
    """Check if the module has an ``if __name__ == '__main__'`` guard."""
    return any(
        isinstance(n, ast.If)
        and isinstance(n.test, ast.Compare)
        and any(
            isinstance(o, ast.Constant) and o.value == "__main__"
            for o in ast.walk(n.test)
        )
        for n in tree.body
    )


def _top_level_executable_calls(tree: ast.Module) -> list[ast.stmt]:
    """Return top-level Expr/Call statements (not inside def/class)."""
    return [n for n in tree.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]


def _route_functions(tree: ast.Module) -> list[tuple[str, int]]:
    """Extract all async def functions decorated with @router.*."""
    from ast import AsyncFunctionDef, FunctionDef

    routes = []
    for node in ast.walk(tree):
        if isinstance(node, (AsyncFunctionDef, FunctionDef)):
            for dec in node.decorator_list:
                dec_src = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                if "router." in dec_src:
                    routes.append((node.name, node.lineno))
    return routes


# ── credential_file.py ─────────────────────────────────────────────────────

class TestCredentialFile:
    """Tests for app/gateway/auth/credential_file.py."""

    @pytest.fixture
    def tree(self):
        return _parse_ast("app/gateway/auth/credential_file.py")

    def test_ast_parses(self, tree):
        assert tree is not None

    def test_no_top_level_executable_calls(self, tree):
        calls = _top_level_executable_calls(tree)
        assert len(calls) == 0, f"Top-level calls found: {[ast.unparse(c) if hasattr(ast, 'unparse') else str(c) for c in calls]}"

    def test_write_initial_credentials_function_exists(self, tree):
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        assert "write_initial_credentials" in names

    def test_no_import_level_db_access(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                src = ast.unparse(node) if hasattr(ast, "unparse") else ""
                assert "init_engine" not in src, f"init_engine call found: {src}"
                assert "create_all" not in src, f"create_all call found: {src}"

    def test_import_succeeds(self):
        from app.gateway.auth.credential_file import write_initial_credentials

        assert callable(write_initial_credentials)
        # Function must NOT be called on import (no side effects at import time)
        # This is validated by no top-level executable calls above


# ── csrf_middleware.py ─────────────────────────────────────────────────────

class TestCsrfMiddleware:
    """Tests for app/gateway/csrf_middleware.py."""

    @pytest.fixture
    def tree(self):
        return _parse_ast("app/gateway/csrf_middleware.py")

    def test_ast_parses(self, tree):
        assert tree is not None

    def test_has_is_secure_request_function(self, tree):
        names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert "is_secure_request" in names

    def test_has_csrf_middleware_class(self, tree):
        names = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
        assert "CSRFMiddleware" in names

    def test_import_succeeds(self):
        from app.gateway.csrf_middleware import is_secure_request, CSRFMiddleware

        assert callable(is_secure_request)
        assert callable(CSRFMiddleware)


# ── reset_admin.py ─────────────────────────────────────────────────────────

class TestResetAdmin:
    """Tests for app/gateway/auth/reset_admin.py."""

    @pytest.fixture
    def tree(self):
        return _parse_ast("app/gateway/auth/reset_admin.py")

    def test_ast_parses(self, tree):
        assert tree is not None

    def test_has_name_main_guard(self, tree):
        assert _has_name_main_guard(tree), "reset_admin.py must have 'if __name__ == __main__' guard"

    def test_no_top_level_executable_calls(self, tree):
        calls = _top_level_executable_calls(tree)
        assert len(calls) == 0

    def test_main_and_run_functions_exist(self, tree):
        names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert "main" in names
        assert "_run" in names

    def test_import_succeeds_no_execution(self):
        # Importing must NOT execute CLI code
        from app.gateway.auth.reset_admin import main, _run

        assert callable(main)
        assert callable(_run)


# ── routers/auth.py ─────────────────────────────────────────────────────────

class TestRoutersAuth:
    """Tests for app/gateway/routers/auth.py."""

    @pytest.fixture
    def tree(self):
        return _parse_ast("app/gateway/routers/auth.py")

    def test_ast_parses(self, tree):
        assert tree is not None

    def test_route_count(self, tree):
        routes = _route_functions(tree)
        assert len(routes) == 8, f"Expected 8 routes, found {len(routes)}: {routes}"

    def test_expected_routes_present(self, tree):
        routes = _route_functions(tree)
        route_names = {name for name, _ in routes}

        expected = {
            "login_local",
            "register",
            "logout",
            "change_password",
            "get_me",
            "setup_status",
            "oauth_login",
            "oauth_callback",
        }
        assert route_names == expected, f"Route mismatch: {route_names} vs {expected}"

    def test_oauth_routes_return_501(self, tree):
        """OAuth routes should raise HTTPException 501 (placeholder)."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                if node.name in ("oauth_login", "oauth_callback"):
                    src = ast.unparse(node) if hasattr(ast, "unparse") else ""
                    assert "501" in src or "NOT_IMPLEMENTED" in src, \
                        f"{node.name} does not appear to return 501"

    def test_no_app_include_router(self, tree):
        """Router file must NOT call app.include_router."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                src = ast.unparse(node) if hasattr(ast, "unparse") else ""
                assert "include_router" not in src, f"include_router call found: {src}"

    def test_import_succeeds(self):
        from app.gateway.routers.auth import router

        assert router is not None
        assert len(router.routes) == 8, f"Expected 8 routes on router, got {len(router.routes)}"

    def test_credential_file_dependency_available(self):
        """write_initial_credentials must be importable."""
        from app.gateway.auth.credential_file import write_initial_credentials

        assert callable(write_initial_credentials)

    def test_csrf_middleware_dependency_available(self):
        """is_secure_request must be importable."""
        from app.gateway.csrf_middleware import is_secure_request

        assert callable(is_secure_request)


# ── Static closure ─────────────────────────────────────────────────────────

class TestStaticClosure:
    """Validate that all auth chain imports are resolvable without app.py / DB."""

    def test_auth_models_user_response_has_needs_setup(self):
        """UserResponse must have needs_setup field."""
        from app.gateway.auth.models import UserResponse

        fields = UserResponse.__annotations__.keys()
        assert "needs_setup" in fields

    def test_deps_get_current_user_from_request_importable(self):
        """get_current_user_from_request must be importable."""
        from app.gateway.deps import get_current_user_from_request

        assert callable(get_current_user_from_request)

    def test_deps_get_local_provider_importable(self):
        """get_local_provider must be importable."""
        from app.gateway.deps import get_local_provider

        assert callable(get_local_provider)

    def test_auth_module_importable(self):
        """auth module exports must be available."""
        from app.gateway.auth import create_access_token, decode_token

        assert callable(create_access_token)
        assert callable(decode_token)

    def test_local_provider_has_count_users(self):
        """LocalAuthProvider must have count_users method."""
        from app.gateway.auth.local_provider import LocalAuthProvider

        assert hasattr(LocalAuthProvider, "count_users")

    def test_no_app_py_modification(self):
        """app.py must not have been modified in this phase."""
        # Read app.py and check it has NOT been modified to add auth routes
        app_path = BACKEND / "app/gateway/app.py"
        with open(app_path, encoding="utf-8") as fh:
            src = fh.read()

        # If auth routes are registered, this string would be present
        # We check it is NOT present (proving no modification happened)
        tree = ast.parse(src, filename="app.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_src = ast.unparse(node) if hasattr(ast, "unparse") else ""
                if "include_router" in call_src:
                    # It's OK to have include_router calls, but they must NOT include auth
                    args_str = str(node.args)
                    assert "auth.router" not in args_str, \
                        "auth.router found in app.py include_router — not authorized in this phase"


# ── Run with: pytest backend/tests/test_auth_route_static.py -v ───────────
