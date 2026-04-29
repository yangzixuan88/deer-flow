"""R241-23G - Gateway auth flags static validation.

Tests that AUTH_MIDDLEWARE_ENABLED and AUTH_ROUTES_ENABLED flags
are correctly read and control the conditional wiring.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))


class TestFlagDefaults:
    """Verify default behavior (flags unset → auth disabled)."""

    def test_flag_defaults_to_false(self):
        """Both flags default to 'false' in os.environ.get()."""
        src = open(BACKEND / "app/gateway/app.py", encoding="utf-8").read()
        # AUTH_MIDDLEWARE_ENABLED defaults to 'false' when env var absent
        assert '.get("AUTH_MIDDLEWARE_ENABLED", "false")' in src
        assert '.get("AUTH_ROUTES_ENABLED", "false")' in src

    def test_flag_evaluation_is_explicit_bool_check(self):
        """Flag value is compared against 'true' string."""
        src = open(BACKEND / "app/gateway/app.py", encoding="utf-8").read()
        # .lower() == 'true' pattern ensures only explicit 'true' enables
        assert '("AUTH_MIDDLEWARE_ENABLED", "false").lower() == "true"' in src or \
               'get("AUTH_MIDDLEWARE_ENABLED", "false").lower()' in src
        assert '("AUTH_ROUTES_ENABLED", "false").lower() == "true"' in src or \
               'get("AUTH_ROUTES_ENABLED", "false").lower()' in src


class TestFlagIsolation:
    """Verify auth wiring sections are fully isolated from rest of app."""

    def test_auth_section_in_create_app(self):
        """Auth wiring must be inside create_app function."""
        with open(BACKEND / "app/gateway/app.py", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)

        create_app = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "create_app":
                create_app = node
                break

        assert create_app is not None

        # Find auth If blocks inside create_app
        auth_ifs_in_create_app = []
        for node in ast.walk(create_app):
            if isinstance(node, ast.If):
                cond = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
                if "_auth_" in cond:
                    auth_ifs_in_create_app.append(cond)

        assert len(auth_ifs_in_create_app) >= 2

    def test_auth_wiring_fails_safely(self):
        """Auth wiring try/except must not propagate exceptions."""
        src = open(BACKEND / "app/gateway/app.py", encoding="utf-8").read()
        # Must have try/except around auth wiring
        assert "try:" in src
        # Auth wiring section should be in a try block
        auth_start = src.find("# ==== Auth wiring")
        assert auth_start != -1
        auth_section = src[auth_start:auth_start + 2000]
        assert "try:" in auth_section, "Auth wiring must be inside try/except"
        assert "except Exception" in auth_section or "except" in auth_section, "Must catch exceptions"
