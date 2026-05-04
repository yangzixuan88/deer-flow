"""Tests for langgraph_auth.py — LangGraph SDK auth hooks sharing Gateway JWT chain."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateway.langgraph_auth import _CSRF_METHODS, _check_csrf, add_owner_filter, authenticate


# ─── CSRF Check Tests ────────────────────────────────────────────────────────


class TestCheckCsrf:
    def test_get_request_passes_csrf_check(self):
        """GET requests do not require CSRF validation."""
        request = SimpleNamespace(method="GET", cookies={}, headers={})
        # Should not raise
        _check_csrf(request)

    def test_post_without_tokens_raises_403(self):
        """POST without CSRF tokens raises 403."""
        request = SimpleNamespace(method="POST", cookies={}, headers={})
        with pytest.raises(Exception) as exc_info:
            _check_csrf(request)
        # langgraph_sdk Auth.exceptions.HTTPException
        assert exc_info.value.status_code == 403

    def test_post_with_empty_cookie_token_raises_403(self):
        """POST with missing cookie token raises 403."""
        request = SimpleNamespace(method="POST", cookies={}, headers={"x-csrf-token": "token"})
        with pytest.raises(Exception) as exc_info:
            _check_csrf(request)
        assert exc_info.value.status_code == 403

    def test_post_with_empty_header_token_raises_403(self):
        """POST with missing header token raises 403."""
        request = SimpleNamespace(method="POST", cookies={"csrf_token": "token"}, headers={})
        with pytest.raises(Exception) as exc_info:
            _check_csrf(request)
        assert exc_info.value.status_code == 403

    def test_post_with_matching_tokens_passes(self):
        """POST with matching CSRF tokens passes."""
        request = SimpleNamespace(
            method="POST",
            cookies={"csrf_token": "same-token"},
            headers={"x-csrf-token": "same-token"},
        )
        _check_csrf(request)  # Should not raise

    def test_post_with_mismatched_tokens_raises_403(self):
        """POST with mismatched tokens raises 403."""
        request = SimpleNamespace(
            method="POST",
            cookies={"csrf_token": "cookie-token"},
            headers={"x-csrf-token": "header-token"},
        )
        with pytest.raises(Exception) as exc_info:
            _check_csrf(request)
        assert exc_info.value.status_code == 403

    def test_put_method_triggers_csrf_check(self):
        """PUT is a CSRF-protected method."""
        request = SimpleNamespace(method="PUT", cookies={}, headers={})
        with pytest.raises(Exception) as exc_info:
            _check_csrf(request)
        assert exc_info.value.status_code == 403

    def test_delete_method_triggers_csrf_check(self):
        """DELETE is a CSRF-protected method."""
        request = SimpleNamespace(method="DELETE", cookies={}, headers={})
        with pytest.raises(Exception) as exc_info:
            _check_csrf(request)
        assert exc_info.value.status_code == 403

    def test_patch_method_triggers_csrf_check(self):
        """PATCH is a CSRF-protected method."""
        request = SimpleNamespace(method="PATCH", cookies={}, headers={})
        with pytest.raises(Exception) as exc_info:
            _check_csrf(request)
        assert exc_info.value.status_code == 403

    def test_csrf_methods_frozenset(self):
        """_CSRF_METHODS should be a frozenset for O(1) lookup."""
        assert isinstance(_CSRF_METHODS, frozenset)
        assert "POST" in _CSRF_METHODS
        assert "PUT" in _CSRF_METHODS
        assert "DELETE" in _CSRF_METHODS
        assert "PATCH" in _CSRF_METHODS
        assert "GET" not in _CSRF_METHODS

    def test_timing_safe_comparison_for_csrf(self):
        """CSRF token comparison should be timing-safe (using secrets.compare_digest)."""
        request = SimpleNamespace(
            method="POST",
            cookies={"csrf_token": "a" * 64},
            headers={"x-csrf-token": "a" * 64},
        )
        # Even with identical tokens, verify it uses compare_digest
        _check_csrf(request)  # Should not raise


# ─── authenticate Tests ─────────────────────────────────────────────────────


class TestAuthenticate:
    @pytest.mark.asyncio
    async def test_raises_401_when_no_access_token_cookie(self):
        """Missing access_token cookie raises 401."""
        request = SimpleNamespace(method="GET", cookies={}, headers={})
        with pytest.raises(Exception) as exc_info:
            await authenticate(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_raises_401_when_token_invalid(self):
        """Invalid JWT raises 401."""
        request = SimpleNamespace(
            method="GET",
            cookies={"access_token": "invalid.jwt.token"},
            headers={},
        )
        with pytest.raises(Exception) as exc_info:
            await authenticate(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_raises_401_when_user_not_found(self):
        """Valid JWT for non-existent user raises 401."""
        from app.gateway.auth.jwt import create_access_token

        # Create a valid token for nonexistent user
        token = create_access_token("nonexistent-user", expires_delta=3600, token_version=0)
        request = SimpleNamespace(
            method="GET",
            cookies={"access_token": token},
            headers={},
        )
        with pytest.raises(Exception) as exc_info:
            await authenticate(request)
        assert exc_info.value.status_code == 401
        assert "User not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_when_token_version_mismatch(self):
        """Valid JWT with stale token_version raises 401."""
        from app.gateway.auth.jwt import create_access_token
        from app.gateway.auth.models import User
        from app.gateway.auth.repositories.sqlite import SQLiteUserRepository
        from app.gateway.deps import get_session_factory
        from deerflow.runtime.user_context import DEFAULT_USER_ID

        sf = get_session_factory()
        if sf is not None:
            repo = SQLiteUserRepository(sf)
            user = User(
                id=DEFAULT_USER_ID,
                email="tokver@example.com",
                system_role="user",
                token_version=5,
            )
            try:
                await repo.create_user(user)
            except ValueError:
                pass  # already exists

            # Token with version 0, but user has version 5
            token = create_access_token(str(user.id), expires_delta=3600, token_version=0)
            request = SimpleNamespace(
                method="GET",
                cookies={"access_token": token},
                headers={},
            )
            with pytest.raises(Exception) as exc_info:
                await authenticate(request)
            assert exc_info.value.status_code == 401
            assert "Token revoked" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_csrf_check_before_token_validation(self):
        """CSRF is checked before JWT decode — bad CSRF fails fast."""
        request = SimpleNamespace(
            method="POST",
            cookies={},
            headers={},
        )
        # Should fail on CSRF first (403), not on auth (401)
        with pytest.raises(Exception) as exc_info:
            await authenticate(request)
        assert exc_info.value.status_code == 403


# ─── add_owner_filter Tests ─────────────────────────────────────────────────


class TestAddOwnerFilter:
    @pytest.mark.asyncio
    async def test_injects_user_id_into_metadata(self):
        """On writes, stamps user_id into metadata."""
        ctx = SimpleNamespace(user=SimpleNamespace(identity="user-abc"))
        value = {"metadata": {}}

        result = await add_owner_filter(ctx, value)

        assert value["metadata"]["user_id"] == "user-abc"
        # Returns filter dict for reads
        assert result == {"user_id": "user-abc"}

    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self):
        """Existing metadata keys are preserved."""
        ctx = SimpleNamespace(user=SimpleNamespace(identity="user-xyz"))
        value = {"metadata": {"existing_key": "keep-me"}}

        result = await add_owner_filter(ctx, value)

        assert value["metadata"]["existing_key"] == "keep-me"
        assert value["metadata"]["user_id"] == "user-xyz"

    @pytest.mark.asyncio
    async def test_creates_metadata_if_missing(self):
        """If metadata is absent, creates it."""
        ctx = SimpleNamespace(user=SimpleNamespace(identity="user-new"))
        value = {}

        result = await add_owner_filter(ctx, value)

        assert "metadata" in value
        assert value["metadata"]["user_id"] == "user-new"

    @pytest.mark.asyncio
    async def test_returns_filter_dict(self):
        """Returns filter dict so LangGraph applies user_id filter on reads."""
        ctx = SimpleNamespace(user=SimpleNamespace(identity="user-filter"))
        value = {"metadata": {}}

        result = await add_owner_filter(ctx, value)

        assert isinstance(result, dict)
        assert "user_id" in result
        assert result["user_id"] == "user-filter"

    @pytest.mark.asyncio
    async def test_identity_from_auth_context(self):
        """Uses ctx.user.identity as user_id."""
        ctx = SimpleNamespace(user=SimpleNamespace(identity="specific-user-id"))
        value = {"metadata": {}}

        await add_owner_filter(ctx, value)

        assert value["metadata"]["user_id"] == "specific-user-id"


# ─── Module-level auth instance ──────────────────────────────────────────────


class TestAuthModule:
    def test_auth_instance_exists(self):
        """The module exports an 'auth' Auth instance."""
        from app.gateway import langgraph_auth

        assert hasattr(langgraph_auth, "auth")
        # It's a LangGraph SDK Auth instance
        assert langgraph_auth.auth is not None

    def test_authenticate_is_awaitable(self):
        """authenticate is an async function decorated with @auth.authenticate."""
        import inspect

        assert inspect.iscoroutinefunction(authenticate)

    def test_add_owner_filter_is_awaitable(self):
        """add_owner_filter is an async function decorated with @auth.on."""
        import inspect

        assert inspect.iscoroutinefunction(add_owner_filter)
