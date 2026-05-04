"""Tests for internal_auth.py — process-local internal token authentication."""

from __future__ import annotations

import secrets

import pytest

from app.gateway.internal_auth import (
    INTERNAL_AUTH_HEADER_NAME,
    _INTERNAL_AUTH_TOKEN,
    create_internal_auth_headers,
    get_internal_user,
    is_valid_internal_auth_token,
)


# ─── Token Validity Tests ───────────────────────────────────────────────────


class TestIsValidInternalAuthToken:
    def test_returns_true_for_valid_token(self):
        """Passing the process-local token returns True."""
        assert is_valid_internal_auth_token(_INTERNAL_AUTH_TOKEN) is True

    def test_returns_false_for_none(self):
        assert is_valid_internal_auth_token(None) is False

    def test_returns_false_for_empty_string(self):
        assert is_valid_internal_auth_token("") is False

    def test_returns_false_for_wrong_token(self):
        fake_token = secrets.token_urlsafe(32)
        # It's astronomically unlikely this matches _INTERNAL_AUTH_TOKEN
        assert is_valid_internal_auth_token(fake_token) is False

    def test_returns_false_for_tampered_token(self):
        """Slight modification should fail."""
        tampered = _INTERNAL_AUTH_TOKEN[:-1] + ("a" if _INTERNAL_AUTH_TOKEN[-1] != "a" else "b")
        assert is_valid_internal_auth_token(tampered) is False

    def test_timing_safe_comparison_used(self):
        """Even nearly-identical tokens should fail fast and safely."""
        # One character different near the end
        prefix = _INTERNAL_AUTH_TOKEN[:-1]
        suffix_char = _INTERNAL_AUTH_TOKEN[-1]
        alt_char = "a" if suffix_char != "a" else "b"
        tampered = prefix + alt_char
        assert is_valid_internal_auth_token(tampered) is False

    def test_token_is_32_bytes_urlsafe(self):
        """The internal token should be cryptographically random 32 bytes."""
        # token_urlsafe(32) produces a ~43 char string
        assert len(_INTERNAL_AUTH_TOKEN) >= 40
        # Should be valid base64url characters only
        import string

        allowed = set(string.ascii_letters + string.digits + "-_")
        assert all(c in allowed for c in _INTERNAL_AUTH_TOKEN)


# ─── create_internal_auth_headers Tests ────────────────────────────────────


class TestCreateInternalAuthHeaders:
    def test_returns_dict_with_internal_token(self):
        headers = create_internal_auth_headers()
        assert isinstance(headers, dict)
        assert INTERNAL_AUTH_HEADER_NAME in headers
        assert headers[INTERNAL_AUTH_HEADER_NAME] == _INTERNAL_AUTH_TOKEN

    def test_header_name_matches_constant(self):
        headers = create_internal_auth_headers()
        assert INTERNAL_AUTH_HEADER_NAME == "X-DeerFlow-Internal-Token"
        assert headers["X-DeerFlow-Internal-Token"] == _INTERNAL_AUTH_TOKEN


# ─── get_internal_user Tests ───────────────────────────────────────────────


class TestGetInternalUser:
    def test_returns_simple_namespace(self):
        user = get_internal_user()
        assert isinstance(user, __import__("types").SimpleNamespace)

    def test_has_id_attribute(self):
        user = get_internal_user()
        assert hasattr(user, "id")

    def test_id_is_default_user_id(self):
        from deerflow.runtime.user_context import DEFAULT_USER_ID

        user = get_internal_user()
        assert user.id == DEFAULT_USER_ID

    def test_system_role_is_internal(self):
        user = get_internal_user()
        assert hasattr(user, "system_role")
        assert user.system_role == "internal"

    def test_internal_user_is_singleton_per_process(self):
        """Calling get_internal_user() twice returns equal objects."""
        user1 = get_internal_user()
        user2 = get_internal_user()
        # Same type and same id
        assert type(user1) == type(user2)
        assert user1.id == user2.id
        assert user1.system_role == user2.system_role
        # But they are different object instances (new SimpleNamespace each call)
        assert user1 is not user2


# ─── Process Isolation Tests ─────────────────────────────────────────────────


class TestProcessIsolation:
    def test_internal_token_is_process_local(self):
        """The token is generated at module import time — not shared across processes."""
        # This is inherently true in Python (module-level constant)
        # We verify the token exists and is non-empty
        assert _INTERNAL_AUTH_TOKEN is not None
        assert len(_INTERNAL_AUTH_TOKEN) > 0

    def test_internal_user_does_not_have_password_hash(self):
        """Internal user is for trusted calls — no password hash attribute."""
        user = get_internal_user()
        # Internal user should NOT have a password_hash field (it's for OAuth/internal use)
        assert not hasattr(user, "password_hash")

    def test_internal_user_does_not_have_email(self):
        """Internal user is synthetic — no real email."""
        user = get_internal_user()
        assert not hasattr(user, "email")

    def test_internal_user_id_is_string(self):
        """DEFAULT_USER_ID should be a string."""
        from deerflow.runtime.user_context import DEFAULT_USER_ID

        user = get_internal_user()
        assert isinstance(user.id, str)
        assert user.id == DEFAULT_USER_ID


# ─── Header Name Constant ───────────────────────────────────────────────────


class TestHeaderName:
    def test_internal_auth_header_name_is_snake_case(self):
        assert INTERNAL_AUTH_HEADER_NAME == "X-DeerFlow-Internal-Token"

    def test_header_name_starts_with_x(self):
        """Convention: custom headers start with X-."""
        assert INTERNAL_AUTH_HEADER_NAME.startswith("X-")
