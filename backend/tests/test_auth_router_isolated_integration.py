"""R241-23I - Isolated auth router integration tests (test-only, no app.py).

Scope:
- Create standalone FastAPI() with ONLY auth.router included
- Verify route structure, path count, and decorators
- NO app.py import, NO lifespan, NO DB write, NO init_engine

Behavior tests (Lane 5) mock get_local_provider and get_current_user_from_request.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))


# ── Route structure helpers ─────────────────────────────────────────────────

def _route_functions(tree: ast.Module) -> list[tuple[str, int]]:
    """Extract all async def / def functions decorated with @router.*."""
    from ast import AsyncFunctionDef, FunctionDef

    routes = []
    for node in ast.walk(tree):
        if isinstance(node, (AsyncFunctionDef, FunctionDef)):
            for dec in node.decorator_list:
                dec_src = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                if "router." in dec_src:
                    routes.append((node.name, node.lineno))
    return routes


# ── Lane 4: Route Structure Tests (no mocks needed) ──────────────────────────

class TestAuthRouterStructure:
    """Verify auth router structure via AST and route introspection."""

    def test_router_imports_without_errors(self):
        """Router module must import without app.py."""
        # This imports the router object and its dependencies (auth models, deps)
        # deps.get_local_provider is NOT called on import — deferred to function body
        from app.gateway.routers.auth import router

        assert router is not None
        assert len(router.routes) == 8, f"Expected 8 routes, got {len(router.routes)}"

    def test_route_count_via_introspection(self):
        """Router must have exactly 8 registered routes."""
        from app.gateway.routers.auth import router

        # Filter to only the auth-prefixed routes (not sub-routers)
        auth_routes = [r for r in router.routes if hasattr(r, "path")]
        assert len(auth_routes) == 8, f"Expected 8 auth routes, got {len(auth_routes)}: {[r.path for r in auth_routes]}"

    def test_expected_route_names_present(self):
        """All 8 expected endpoint names must be present."""
        from app.gateway.routers.auth import router

        # Get function names from routes
        route_funcs = {}
        for route in router.routes:
            if hasattr(route, "endpoint") and hasattr(route.endpoint, "__name__"):
                route_funcs[route.endpoint.__name__] = route.path

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
        actual = set(route_funcs.keys())
        assert actual == expected, f"Route mismatch: missing={expected - actual}, extra={actual - expected}"

    def test_expected_http_methods(self):
        """POST endpoints: login, register, logout, change-password.
        GET endpoints: me, setup-status.
        GET with path param: oauth/{provider}.
        GET with path params: callback/{provider}."""
        from app.gateway.routers.auth import router

        methods_by_path: dict[str, set[str]] = {}
        for route in router.routes:
            if hasattr(route, "path") and hasattr(route, "methods"):
                methods_by_path.setdefault(route.path, set()).update(route.methods)

        assert "/api/v1/auth/login/local" in methods_by_path
        assert "POST" in methods_by_path["/api/v1/auth/login/local"]

        assert "/api/v1/auth/register" in methods_by_path
        assert "POST" in methods_by_path["/api/v1/auth/register"]

        assert "/api/v1/auth/logout" in methods_by_path
        assert "POST" in methods_by_path["/api/v1/auth/logout"]

        assert "/api/v1/auth/change-password" in methods_by_path
        assert "POST" in methods_by_path["/api/v1/auth/change-password"]

        assert "/api/v1/auth/me" in methods_by_path
        assert "GET" in methods_by_path["/api/v1/auth/me"]

        assert "/api/v1/auth/setup-status" in methods_by_path
        assert "GET" in methods_by_path["/api/v1/auth/setup-status"]

        assert "/api/v1/auth/oauth/{provider}" in methods_by_path
        assert "GET" in methods_by_path["/api/v1/auth/oauth/{provider}"]

        assert "/api/v1/auth/callback/{provider}" in methods_by_path
        assert "GET" in methods_by_path["/api/v1/auth/callback/{provider}"]

    def test_oauth_routes_have_path_params(self):
        """OAuth routes must accept provider as path parameter."""
        from app.gateway.routers.auth import router

        oauth_routes = [r for r in router.routes if "oauth" in getattr(r, "path", "") or "callback" in getattr(r, "path", "")]
        assert len(oauth_routes) == 2, f"Expected 2 OAuth routes, got {len(oauth_routes)}: {[r.path for r in oauth_routes]}"

        for r in oauth_routes:
            param_names = [p.name for p in r.dependant.path_params]
            assert "provider" in param_names, f"Route {r.path} missing 'provider' path param: {param_names}"

    def test_login_uses_oauth2_form(self):
        """login_local must depend on OAuth2PasswordRequestForm."""
        from app.gateway.routers.auth import router

        login_route = next((r for r in router.routes if getattr(r.endpoint, "__name__", "") == "login_local"), None)
        assert login_route is not None

        # Check signature has OAuth2PasswordRequestForm dependency
        sig = str(login_route.dependant.signature) if hasattr(login_route.dependant, "signature") else ""
        assert "OAuth2PasswordRequestForm" in sig or any(
            "form_data" in str(d.name) for d in login_route.dependant.dependencies
        ), f"login_local does not use OAuth2PasswordRequestForm"

    def test_register_request_model_is_pydantic(self):
        """register endpoint must accept RegisterRequest (email + password)."""
        from app.gateway.routers.auth import router
        from app.gateway.routers.auth import RegisterRequest

        register_route = next((r for r in router.routes if getattr(r.endpoint, "__name__", "") == "register"), None)
        assert register_route is not None

        # RegisterRequest must be a valid Pydantic model
        assert hasattr(RegisterRequest, "model_validate") or hasattr(RegisterRequest, "model_config")

    def test_ast_routes_match_introspection(self):
        """AST-discovered route count must match router.routes count."""
        tree = _parse_ast("app/gateway/routers/auth.py")
        ast_routes = _route_functions(tree)
        assert len(ast_routes) == 8, f"AST found {len(ast_routes)} routes: {ast_routes}"

    def test_no_include_router_in_auth_module(self):
        """Auth router module must NOT call include_router itself."""
        tree = _parse_ast("app/gateway/routers/auth.py")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                src = ast.unparse(node) if hasattr(ast, "unparse") else ""
                assert "include_router" not in src, f"include_router call found in auth.py: {src}"


# ── Lane 5: Behavior Mock Tests ───────────────────────────────────────────────

class TestAuthRouterBehaviorMocks:
    """Verify route handler behavior using mocked providers.

    get_local_provider() requires init_engine → mocked.
    get_current_user_from_request() → mocked.
    """

    @pytest.fixture
    def mock_local_provider(self):
        """Create a mock LocalAuthProvider."""
        provider = AsyncMock()
        provider.authenticate = AsyncMock(return_value=MagicMock(
            id="user-123",
            email="test@example.com",
            system_role="user",
            token_version=0,
            needs_setup=False,
            password_hash="fake_hash",
        ))
        provider.create_user = AsyncMock(return_value=MagicMock(
            id="user-456",
            email="new@example.com",
            system_role="user",
            token_version=0,
            needs_setup=False,
        ))
        provider.count_users = AsyncMock(return_value=1)
        provider.get_user = AsyncMock(return_value=MagicMock(
            id="user-123",
            email="test@example.com",
            system_role="user",
            token_version=0,
            needs_setup=False,
            password_hash="fake_hash",
        ))
        provider.update_user = AsyncMock(return_value=None)
        provider.get_user_by_email = AsyncMock(return_value=None)
        return provider

    @pytest.fixture
    def mock_current_user(self):
        """Mock get_current_user_from_request returning a test user."""
        return MagicMock(
            id="user-123",
            email="test@example.com",
            system_role="user",
            token_version=0,
            needs_setup=False,
            password_hash="fake_hash",
        )

    @pytest.fixture
    def mock_request(self):
        """Create a mock Request with cookies and client info."""
        request = MagicMock()
        request.cookies = {}
        request.headers = {}
        request.client = MagicMock(host="127.0.0.1")
        return request

    @pytest.mark.asyncio
    async def test_login_local_returns_login_response(self, mock_local_provider, mock_request):
        """POST /login/local with valid creds returns LoginResponse."""
        from app.gateway.routers.auth import LoginResponse, login_local
        from fastapi.security import OAuth2PasswordRequestForm

        mock_form = MagicMock(spec=OAuth2PasswordRequestForm)
        mock_form.username = "test@example.com"
        mock_form.password = "password123"

        with patch("app.gateway.routers.auth.get_local_provider", return_value=mock_local_provider):
            mock_response = MagicMock()
            result = await login_local(
                request=mock_request,
                response=mock_response,
                form_data=mock_form,
            )

        assert isinstance(result, LoginResponse)
        assert result.expires_in > 0
        assert isinstance(result.needs_setup, bool)
        mock_local_provider.authenticate.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_local_invalid_credentials(self, mock_local_provider, mock_request):
        """POST /login/local with wrong password raises 401."""
        from app.gateway.routers.auth import login_local
        from fastapi.security import OAuth2PasswordRequestForm
        from fastapi import HTTPException

        mock_local_provider.authenticate = AsyncMock(return_value=None)

        mock_form = MagicMock(spec=OAuth2PasswordRequestForm)
        mock_form.username = "test@example.com"
        mock_form.password = "wrongpassword"

        with patch("app.gateway.routers.auth.get_local_provider", return_value=mock_local_provider):
            with pytest.raises(HTTPException) as exc_info:
                await login_local(request=mock_request, response=MagicMock(), form_data=mock_form)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_setup_status_returns_needs_setup_true_when_no_users(self, mock_local_provider):
        """GET /setup-status returns needs_setup=True when user_count==0."""
        from app.gateway.routers.auth import setup_status

        mock_local_provider.count_users = AsyncMock(return_value=0)

        with patch("app.gateway.routers.auth.get_local_provider", return_value=mock_local_provider):
            result = await setup_status()

        assert result == {"needs_setup": True}

    @pytest.mark.asyncio
    async def test_setup_status_returns_needs_setup_false_when_users_exist(self, mock_local_provider):
        """GET /setup-status returns needs_setup=False when users exist."""
        from app.gateway.routers.auth import setup_status

        mock_local_provider.count_users = AsyncMock(return_value=1)

        with patch("app.gateway.routers.auth.get_local_provider", return_value=mock_local_provider):
            result = await setup_status()

        assert result == {"needs_setup": False}

    @pytest.mark.asyncio
    async def test_logout_returns_message_response(self, mock_request):
        """POST /logout returns MessageResponse and clears cookie."""
        from app.gateway.routers.auth import logout, MessageResponse

        mock_response = MagicMock()

        result = await logout(request=mock_request, response=mock_response)

        assert isinstance(result, MessageResponse)
        assert "message" in result.model_dump()
        mock_response.delete_cookie.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_me_returns_user_response(self, mock_current_user, mock_request):
        """GET /me returns UserResponse for authenticated user."""
        from app.gateway.routers.auth import get_me, UserResponse

        mock_request.cookies = {"access_token": "valid_token"}

        with patch("app.gateway.routers.auth.get_current_user_from_request", return_value=mock_current_user):
            result = await get_me(request=mock_request)

        assert isinstance(result, UserResponse)
        assert result.email == "test@example.com"
        assert result.system_role == "user"

    @pytest.mark.asyncio
    async def test_oauth_login_raises_501(self):
        """GET /oauth/{provider} raises 501 NOT_IMPLEMENTED."""
        from app.gateway.routers.auth import oauth_login
        from fastapi import HTTPException

        mock_request = MagicMock()

        for provider in ["github", "google"]:
            with pytest.raises(HTTPException) as exc_info:
                await oauth_login(provider=provider)

            assert exc_info.value.status_code == 501

    @pytest.mark.asyncio
    async def test_oauth_callback_raises_501(self):
        """GET /callback/{provider} raises 501 NOT_IMPLEMENTED."""
        from app.gateway.routers.auth import oauth_callback
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await oauth_callback(provider="github", code="abc", state="xyz")

        assert exc_info.value.status_code == 501

    @pytest.mark.asyncio
    async def test_change_password_unauthenticated_raises_401(self, mock_request):
        """POST /change-password without auth raises 401."""
        from app.gateway.routers.auth import change_password, ChangePasswordRequest
        from fastapi import HTTPException

        mock_request.cookies = {}

        with patch("app.gateway.routers.auth.get_current_user_from_request", side_effect=HTTPException(status_code=401, detail="Not authenticated")):
            with pytest.raises(HTTPException) as exc_info:
                await change_password(
                    request=mock_request,
                    response=MagicMock(),
                    body=ChangePasswordRequest(
                        current_password="old",
                        new_password="newnewnew",
                    ),
                )

        assert exc_info.value.status_code == 401


# ── Helper ───────────────────────────────────────────────────────────────────

def _parse_ast(rel_path: str) -> ast.Module:
    with open(BACKEND / rel_path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=rel_path)
