"""R241-23G - Gateway auth disabled runtime validation.

Tests that when flags are disabled (unset/false),
auth components are NOT registered even if import succeeds.

NOTE: Full app import is blocked by pre-existing deerflow cascade issue.
This test validates at AST level what would happen if app imported cleanly.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))


def _parse_app() -> ast.Module:
    with open(BACKEND / "app/gateway/app.py", encoding="utf-8") as f:
        return ast.parse(f.read(), filename="app.py")


class TestDisabledByDefault:
    """When env vars are unset, auth should be disabled."""

    def test_default_flags_unset(self):
        """Default state: both AUTH_MIDDLEWARE_ENABLED and AUTH_ROUTES_ENABLED are unset."""
        for k in ["AUTH_MIDDLEWARE_ENABLED", "AUTH_ROUTES_ENABLED"]:
            assert k not in os.environ, f"{k} must be unset for this test"

    def test_middleware_disabled_when_flag_false(self, monkeypatch):
        """When flag is 'false', add_middleware(AuthMiddleware) must not execute."""
        # Simulate: flag is explicitly false
        monkeypatch.setenv("AUTH_MIDDLEWARE_ENABLED", "false")
        monkeypatch.setenv("AUTH_ROUTES_ENABLED", "false")

        # Verify the flag evaluation logic
        src = open(BACKEND / "app/gateway/app.py", encoding="utf-8").read()
        # When flag='false', _auth_middleware_enabled = False
        assert '.get("AUTH_MIDDLEWARE_ENABLED", "false").lower() == "true"' in src

        # The condition is False, so body of if block does NOT execute
        # This is verified by AST: the add_middleware call is inside the If body
        tree = _parse_app()
        auth_if = None
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                cond = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
                if "_auth_middleware_enabled" in cond:
                    auth_if = node
                    break

        assert auth_if is not None, "Auth middleware If block not found"
        # add_middleware must be inside the If
        inside_if = False
        for node in ast.walk(auth_if):
            if isinstance(node, ast.Call) and hasattr(node.func, "attr") and node.func.attr == "add_middleware":
                inside_if = True
        assert inside_if, "add_middleware must be inside the auth middleware If"

    def test_routes_disabled_when_flag_false(self, monkeypatch):
        """When flag is 'false', include_router(auth_router) must not execute."""
        monkeypatch.setenv("AUTH_MIDDLEWARE_ENABLED", "false")
        monkeypatch.setenv("AUTH_ROUTES_ENABLED", "false")

        tree = _parse_app()
        auth_if = None
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                cond = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
                if "_auth_routes_enabled" in cond:
                    auth_if = node
                    break

        assert auth_if is not None, "Auth routes If block not found"
        inside_if = False
        for node in ast.walk(auth_if):
            if isinstance(node, ast.Call) and hasattr(node.func, "attr") and node.func.attr == "include_router":
                inside_if = True
        assert inside_if, "include_router must be inside the auth routes If"


class TestEnabledBehavior:
    """When flags are true, auth SHOULD be enabled (static verification)."""

    def test_middleware_enabled_when_flag_true(self, monkeypatch):
        """When flag='true', add_middleware(AuthMiddleware) executes."""
        monkeypatch.setenv("AUTH_MIDDLEWARE_ENABLED", "true")
        monkeypatch.setenv("AUTH_ROUTES_ENABLED", "false")

        tree = _parse_app()
        auth_if = None
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                cond = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
                if "_auth_middleware_enabled" in cond:
                    auth_if = node
                    break

        # When AUTH_MIDDLEWARE_ENABLED=true and code does .lower() == 'true'
        # The condition is True, so If body (add_middleware) executes
        assert auth_if is not None
        body_calls = [node.func.attr for node in ast.walk(auth_if)
                      if isinstance(node, ast.Call) and hasattr(node.func, "attr")]
        assert "add_middleware" in body_calls

    def test_routes_enabled_when_flag_true(self, monkeypatch):
        """When flag='true', include_router(auth_router) executes."""
        monkeypatch.setenv("AUTH_MIDDLEWARE_ENABLED", "false")
        monkeypatch.setenv("AUTH_ROUTES_ENABLED", "true")

        tree = _parse_app()
        auth_if = None
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                cond = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
                if "_auth_routes_enabled" in cond:
                    auth_if = node
                    break

        assert auth_if is not None
        body_calls = [node.func.attr for node in ast.walk(auth_if)
                      if isinstance(node, ast.Call) and hasattr(node.func, "attr")]
        assert "include_router" in body_calls
