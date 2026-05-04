"""Tests for authz.py — @require_auth and @require_permission decorators."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

# We import the module under test
from app.gateway.authz import (
    AuthContext,
    Permissions,
    _ALL_PERMISSIONS,
    _make_test_request_stub,
    require_auth,
    require_permission,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


class MockUser:
    """Minimal User mock matching the User model shape."""

    def __init__(self, id: str = "user-123", email: str = "test@example.com", system_role: str = "user"):
        self.id = id
        self.email = email
        self.system_role = system_role
        self.token_version = 0


def make_request(overrides: dict[str, Any] | None = None) -> SimpleNamespace:
    """Build a minimal request stub for unit tests."""
    base = _make_test_request_stub()
    base.state = SimpleNamespace()
    if overrides:
        for k, v in overrides.items():
            setattr(base, k, v)
    return base


# ─── AuthContext Tests ──────────────────────────────────────────────────────


class TestAuthContext:
    def test_is_authenticated_true_when_user_set(self):
        ctx = AuthContext(user=MockUser(), permissions=_ALL_PERMISSIONS)
        assert ctx.is_authenticated is True

    def test_is_authenticated_false_when_user_none(self):
        ctx = AuthContext(user=None, permissions=[])
        assert ctx.is_authenticated is False

    def test_has_permission_returns_true_for_valid_permission(self):
        ctx = AuthContext(user=MockUser(), permissions=_ALL_PERMISSIONS)
        assert ctx.has_permission("threads", "read") is True
        assert ctx.has_permission("threads", "write") is True
        assert ctx.has_permission("threads", "delete") is True
        assert ctx.has_permission("runs", "create") is True
        assert ctx.has_permission("runs", "read") is True
        assert ctx.has_permission("runs", "cancel") is True

    def test_has_permission_returns_false_for_missing_permission(self):
        ctx = AuthContext(user=MockUser(), permissions=[])
        assert ctx.has_permission("threads", "read") is False
        assert ctx.has_permission("runs", "cancel") is False

    def test_has_permission_builds_resource_action_string(self):
        ctx = AuthContext(user=MockUser(), permissions=["threads:write"])
        assert ctx.has_permission("threads", "write") is True
        assert ctx.has_permission("threads", "read") is False

    def test_require_user_returns_user_when_authenticated(self):
        user = MockUser()
        ctx = AuthContext(user=user, permissions=_ALL_PERMISSIONS)
        assert ctx.require_user() is user

    def test_require_user_raises_401_when_anonymous(self):
        ctx = AuthContext(user=None, permissions=[])
        with pytest.raises(HTTPException) as exc_info:
            ctx.require_user()
        assert exc_info.value.status_code == 401

    def test_all_permissions_contains_six_permissions(self):
        assert len(_ALL_PERMISSIONS) == 6
        assert "threads:read" in _ALL_PERMISSIONS
        assert "threads:write" in _ALL_PERMISSIONS
        assert "threads:delete" in _ALL_PERMISSIONS
        assert "runs:create" in _ALL_PERMISSIONS
        assert "runs:read" in _ALL_PERMISSIONS
        assert "runs:cancel" in _ALL_PERMISSIONS

    def test_auth_context_slots(self):
        ctx = AuthContext(user=None, permissions=[])
        # __slots__ should prevent arbitrary attributes
        with pytest.raises(AttributeError):
            ctx.arbitrary_attr = "not allowed"


# ─── @require_auth Tests ────────────────────────────────────────────────────


class TestRequireAuth:
    @pytest.mark.asyncio
    async def test_require_auth_sets_request_state_auth(self):
        user = MockUser()

        @require_auth
        async def handler(request):
            assert hasattr(request.state, "auth")
            assert request.state.auth is not None
            return "ok"

        request = make_request({"state": SimpleNamespace()})
        # Simulate _deerflow_test_bypass_auth behavior by mocking authentication
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = AuthContext(user=user, permissions=_ALL_PERMISSIONS)
            result = await handler(request=request)
            assert result == "ok"
            assert request.state.auth.user == user

    @pytest.mark.asyncio
    async def test_require_auth_raises_401_when_not_authenticated(self):
        @require_auth
        async def handler(request):
            return "ok"

        request = make_request({"state": SimpleNamespace()})
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = AuthContext(user=None, permissions=[])
            with pytest.raises(HTTPException) as exc_info:
                await handler(request=request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_require_auth_bypasses_when_deerflow_test_bypass_flag_set(self):
        """When _deerflow_test_bypass_auth=True, no actual auth is performed."""

        @require_auth
        async def handler(request):
            return "success"

        request = make_request({"state": SimpleNamespace(), "_deerflow_test_bypass_auth": True})
        result = await handler(request=request)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_require_auth_injects_request_stub_when_missing(self):
        """If 'request' param is declared but None passed, stub is injected."""

        @require_auth
        async def handler(request):
            assert request is not None
            assert hasattr(request, "state")
            return "injected"

        # Call without passing request — decorator should inject stub
        result = await handler()
        assert result == "injected"

    @pytest.mark.asyncio
    async def test_require_auth_raises_value_error_when_request_param_missing_and_not_declared(self):
        """If 'request' is not in function signature and not provided, raise ValueError."""

        @require_auth
        async def handler(not_request):
            return "ok"

        with pytest.raises(ValueError, match="require_auth"):
            await handler(not_request="something")


# ─── @require_permission Tests ─────────────────────────────────────────────


class TestRequirePermission:
    @pytest.mark.asyncio
    async def test_require_permission_sets_auth_context_when_missing(self):
        user = MockUser()

        @require_permission("threads", "read")
        async def handler(request):
            return "ok"

        request = make_request({"state": SimpleNamespace()})
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = AuthContext(user=user, permissions=_ALL_PERMISSIONS)
            result = await handler(request=request)
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_require_permission_raises_401_when_not_authenticated(self):
        @require_permission("threads", "read")
        async def handler(request):
            return "ok"

        request = make_request({"state": SimpleNamespace()})
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = AuthContext(user=None, permissions=[])
            with pytest.raises(HTTPException) as exc_info:
                await handler(request=request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_require_permission_raises_403_when_permission_missing(self):
        user = MockUser()

        @require_permission("threads", "delete")
        async def handler(request):
            return "ok"

        request = make_request({"state": SimpleNamespace()})
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = AuthContext(user=user, permissions=["threads:read"])
            with pytest.raises(HTTPException) as exc_info:
                await handler(request=request)
            assert exc_info.value.status_code == 403
            assert "threads:delete" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_allows_when_permission_present(self):
        user = MockUser()

        @require_permission("threads", "read")
        async def handler(request):
            return "allowed"

        request = make_request({"state": SimpleNamespace()})
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = AuthContext(user=user, permissions=_ALL_PERMISSIONS)
            result = await handler(request=request)
            assert result == "allowed"

    @pytest.mark.asyncio
    async def test_require_permission_bypasses_when_test_bypass_flag_set(self):
        """_deerflow_test_bypass_auth=True skips permission check."""

        @require_permission("threads", "delete")
        async def handler(request):
            return "bypass success"

        request = make_request({"state": SimpleNamespace(), "_deerflow_test_bypass_auth": True})
        result = await handler(request=request)
        assert result == "bypass success"

    @pytest.mark.asyncio
    async def test_require_permission_owner_check_requires_thread_id(self):
        """owner_check=True requires 'thread_id' in kwargs."""

        @require_permission("threads", "delete", owner_check=True)
        async def handler(request, thread_id: str = "t-1"):
            return "ok"

        request = make_request({"state": SimpleNamespace()})
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = AuthContext(user=MockUser(), permissions=_ALL_PERMISSIONS)
            with pytest.raises(ValueError, match="thread_id"):
                await handler(request=request)

    @pytest.mark.asyncio
    async def test_require_permission_owner_check_calls_check_access(self):
        """owner_check=True calls thread_store.check_access with user_id."""

        user = MockUser(id="user-456")

        @require_permission("threads", "delete", owner_check=True)
        async def handler(request, thread_id: str = "t-1"):
            return "ok"

        request = make_request({"state": SimpleNamespace()})
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock) as mock_auth, \
             patch("app.gateway.authz.get_thread_store") as mock_get_store:
            mock_auth.return_value = AuthContext(user=user, permissions=_ALL_PERMISSIONS)
            mock_store = AsyncMock()
            mock_store.check_access = AsyncMock(return_value=True)
            mock_get_store.return_value = mock_store

            result = await handler(request=request, thread_id="t-1")

            mock_store.check_access.assert_called_once_with(
                "t-1", "user-456", require_existing=False
            )
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_require_permission_owner_check_returns_404_when_denied(self):
        """check_access returning False raises 404."""

        user = MockUser(id="user-789")

        @require_permission("threads", "delete", owner_check=True)
        async def handler(request, thread_id: str = "t-1"):
            return "ok"

        request = make_request({"state": SimpleNamespace()})
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock) as mock_auth, \
             patch("app.gateway.authz.get_thread_store") as mock_get_store:
            mock_auth.return_value = AuthContext(user=user, permissions=_ALL_PERMISSIONS)
            mock_store = AsyncMock()
            mock_store.check_access = AsyncMock(return_value=False)
            mock_get_store.return_value = mock_store

            with pytest.raises(HTTPException) as exc_info:
                await handler(request=request, thread_id="t-1")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_require_permission_require_existing_true_passes_to_check_access(self):
        """require_existing=True is passed to check_access."""

        user = MockUser(id="user-999")

        @require_permission("threads", "delete", owner_check=True, require_existing=True)
        async def handler(request, thread_id: str = "t-1"):
            return "ok"

        request = make_request({"state": SimpleNamespace()})
        with patch("app.gateway.authz._authenticate", new_callable=AsyncMock) as mock_auth, \
             patch("app.gateway.authz.get_thread_store") as mock_get_store:
            mock_auth.return_value = AuthContext(user=user, permissions=_ALL_PERMISSIONS)
            mock_store = AsyncMock()
            mock_store.check_access = AsyncMock(return_value=True)
            mock_get_store.return_value = mock_store

            await handler(request=request, thread_id="t-1")

            mock_store.check_access.assert_called_once_with(
                "t-1", "user-999", require_existing=True
            )

    @pytest.mark.asyncio
    async def test_require_permission_injects_request_stub_when_missing(self):
        """When request is None but declared in signature, inject stub."""

        @require_permission("threads", "read")
        async def handler(request):
            assert request is not None
            return "injected"

        # With test bypass, should proceed without auth
        result = await handler()
        assert result == "injected"


# ─── Permissions Class Tests ──────────────────────────────────────────────


class TestPermissions:
    def test_permission_constants(self):
        assert Permissions.THREADS_READ == "threads:read"
        assert Permissions.THREADS_WRITE == "threads:write"
        assert Permissions.THREADS_DELETE == "threads:delete"
        assert Permissions.RUNS_CREATE == "runs:create"
        assert Permissions.RUNS_READ == "runs:read"
        assert Permissions.RUNS_CANCEL == "runs:cancel"
