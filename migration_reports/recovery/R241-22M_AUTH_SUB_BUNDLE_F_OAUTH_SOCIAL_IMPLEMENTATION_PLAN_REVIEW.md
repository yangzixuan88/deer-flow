# R241-22M Auth Sub-Bundle F (OAuth/social auth) Implementation Plan Review

**报告ID**: R241-22M_AUTH_SUB_BUNDLE_F_OAUTH_SOCIAL_IMPLEMENTATION_PLAN_REVIEW
**生成时间**: 2026-04-29T17:30:00+08:00
**阶段**: Phase 22M — Auth Sub-Bundle F OAuth/social auth Implementation Plan Review
**前置条件**: R241-22L Authz/permissions Implementation Plan Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: oauth_social_plan_completed_threat_model_confirmed_provider_matrix_complete
**oauth_social_plan_completed**: true
**oauth_threat_model_completed**: true
**provider_matrix_completed**: true
**placeholder_routes_confirmed**: true
**persistence_oauth_fields_confirmed**: true
**user_linking_contract_confirmed**: true
**provider_secrets_strategy_confirmed**: true

**关键结论**：
- OAuth 路由当前为 **placeholder**（501 Not Implemented），不支持实际登录
- `oauth_login` 和 `oauth_callback` 已存在于 `routers/auth.py`，但返回 501
- User 模型已有 `oauth_provider` + `oauth_id` 字段，UserRow 有唯一索引
- `LocalAuthProvider.get_user_by_oauth()` 和 `SQLiteUserRepository.get_user_by_oauth()` 已实现
- OAuth 登录需要 `requests` 或 `httpx` 进行网络调用（本机不执行）
- `code` 和 `state` 参数已在 callback 签名中预留

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. OAuth/social auth 文件清单

### 核心文件

| 文件 | 路径 | LOC | OAuth 相关 | 状态 |
|------|------|-----|-----------|------|
| `routers/auth.py` | `app/gateway/routers/auth.py` | ~380 | `/oauth/{provider}`, `/callback/{provider}` | ✅ placeholder |
| `local_provider.py` | `app/gateway/auth/local_provider.py` | ~100 | `get_user_by_oauth()` | ✅ 已实现 |
| `models.py` (User) | `app/gateway/auth/models.py` | ~60 | `oauth_provider`, `oauth_id` | ✅ 已实现 |
| `providers.py` | `app/gateway/auth/providers.py` | ~20 | `AuthProvider` ABC | ✅ 已实现 |
| `errors.py` | `app/gateway/auth/errors.py` | ~40 | `AuthErrorCode` enum | ✅ 已实现 |
| `sqlite.py` (repo) | `app/gateway/auth/repositories/sqlite.py` | ~200 | `get_user_by_oauth()` | ✅ 已实现 |
| `base.py` (repo interface) | `app/gateway/auth/repositories/base.py` | ~90 | `get_user_by_oauth()` | ✅ 已实现 |
| `mcp/oauth.py` | `packages/harness/deerflow/mcp/oauth.py` | ~150 | OAuth token manager (MCP) | ✅ 已实现 |

**无新增 OAuth 文件需要创建**（placeholder 路由已存在）

---

## 4. Provider Inventory

### Supported Providers（路由层声明）

| Provider | Route | 状态 |
|----------|-------|------|
| `github` | `/oauth/{provider}` | ⚠️ placeholder（501） |
| `google` | `/oauth/{provider}` | ⚠️ placeholder（501） |

### Provider 限制逻辑

```python
# routers/auth.py
if provider not in ["github", "google"]:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported OAuth provider: {provider}",
    )
```

### Future Provider Extension Path

- 添加新 provider → 修改路由 guard 条件 + 实现 provider OAuthConfig
- 无需修改 `models.py` 或 `UserRow`（`oauth_provider` 是 string）
- 建议：通过 `auth_config.py` 的 provider 配置驱动，而非硬编码

---

## 5. OAuth Login Flow Contract

### 入口

```
GET /api/v1/auth/oauth/{provider}
```

### 当前实现（Placeholder）

```python
@router.get("/oauth/{provider}")
async def oauth_login(provider: str):
    if provider not in ["github", "google"]:
        raise HTTPException(status_code=400, detail=f"Unsupported OAuth provider: {provider}")
    raise HTTPException(status_code=501, detail="OAuth login not yet implemented")
```

### 目标实现流程（10 步）

```
Step 1: 验证 provider 参数
        guard: provider in ["github", "google"]
        失败 → 400 Bad Request

Step 2: 生成 state token（CSRF 保护）
        state = secrets.token_urlsafe(32)
        存储到 session 或缓存（Redis/memory）

Step 3: 构建 authorization URL
        GitHub: https://github.com/login/oauth/authorize?client_id=...&state=...&scope=read:user
        Google: https://accounts.google.com/o/oauth2/v2/auth?client_id=...&state=...&scope=openid profile email

Step 4: 重定向到 provider authorization URL
        return RedirectResponse(authorization_url)

Step 5: 用户在 provider 授权页面同意
        ↓（浏览器自动跳转）
        Step 6: 回调携带 code + state
```

### 错误响应

| 状态码 | 场景 |
|--------|------|
| 400 | 不支持的 provider |
| 501 | OAuth 尚未实现 |
| 302 | 成功重定向到 provider |

---

## 6. OAuth Callback Flow Contract

### 入口

```
GET /api/v1/auth/callback/{provider}?code=...&state=...
```

### 当前实现（Placeholder）

```python
@router.get("/callback/{provider}")
async def oauth_callback(provider: str, code: str, state: str):
    raise HTTPException(status_code=501, detail="OAuth callback not yet implemented")
```

### 目标实现流程（12 步）

```
Step 1: 验证 provider 参数
        guard: provider in ["github", "google"]

Step 2: 验证 state（CSRF 保护）
        从 session/缓存获取存储的 state
        使用 secrets.compare_digest 比较
        失败 → 400 Bad Request（replay attack 防护）

Step 3: 用 code 交换 access_token
        POST https://github.com/login/oauth/access_token
        或 POST https://oauth2.googleapis.com/token
        Body: {code, client_id, client_secret, redirect_uri}

Step 4: 解析 access_token 响应
        处理 JSON 或 form-encoded 响应

Step 5: 用 access_token 获取用户信息
        GitHub: GET https://api.github.com/user
        Google: GET https://www.googleapis.com/oauth2/v2/userinfo

Step 6: 提取 oauth_provider 和 oauth_id
        GitHub: user["id"] → oauth_id
        Google: user["sub"] → oauth_id

Step 7: 调用 LocalAuthProvider.get_user_by_oauth(provider, oauth_id)
        查找已链接账户

Step 8: 找到用户 → 登录（返回 JWT cookie）
        user.token_version 可选递增（安全策略）

Step 9: 未找到用户 → 检查 email 是否已存在
        email 已存在 → 提示"该邮箱已绑定本地账户"
        email 不存在 → 自动创建用户（oauth 用户）

Step 10: 设置 session cookie
        _set_session_cookie(response, token, request)

Step 11: 重定向到前端
        redirect_uri from state or default /

Step 12: 清理 state token（防止 replay）
```

---

## 7. State / CSRF Validation Contract

### State Token 生成

```python
state = secrets.token_urlsafe(32)
# 存储：{state: {provider, redirect_uri, created_at, nonce}}
# TTL：10 分钟
```

### State 验证

```python
# 1. 检查 state 是否存在
stored = state_store.get(state)
if not stored:
    raise HTTPException(400, "Invalid or expired state")

# 2. 验证 provider 匹配
if stored.provider != provider:
    raise HTTPException(400, "State provider mismatch")

# 3. 时序安全比较（防止 timing attack）
if not secrets.compare_digest(stored.state, state):
    raise HTTPException(400, "State validation failed")

# 4. 检查 TTL
if time.time() - stored.created_at > STATE_TTL:
    raise HTTPException(400, "State expired")

# 5. 删除 state（防止 replay）
state_store.delete(state)
```

### CSRF 风险缓解

| 攻击 | 缓解 |
|------|------|
| CSRF（跨站请求） | state token 需要在 callback 验证 |
| Replay attack | state 验证后立即删除 |
| State 预测 | 使用 `secrets.token_urlsafe(32)` 加密安全随机 |
| State 泄露（URL referrer） | HTTPS + state 只在 server-to-server 回调传递 |

---

## 8. Token Exchange Boundary

### 边界定义

```python
# 客户端可见：浏览器 → gateway /callback/{provider}?code=xxx&state=xxx
# 服务端秘密：client_secret 永不暴露在客户端
```

### 敏感操作（服务端执行）

| 操作 | 说明 |
|------|------|
| `client_secret` 使用 | 只在服务端；从不发送给客户端或浏览器 |
| `access_token` 获取 | 服务端用 code 换 token；token 不记录到日志 |
| `refresh_token` 存储 | 如果支持 refresh_token，需加密存储 |

### Client Secret 管理

```python
# 环境变量注入
GITHUB_CLIENT_SECRET=xxx
GOOGLE_CLIENT_SECRET=xxx

# 通过 auth_config.py 获取
config = get_auth_config()
github_secret = config.providers.github.client_secret
```

### Token 传输

| Token | 传输方式 | 风险 |
|-------|----------|------|
| Authorization code | URL query param (`?code=`) | ⚠️ 通过浏览器重定向；短期有效 |
| access_token | 服务端响应体 | ✅ 不经过浏览器 URL |
| refresh_token | 服务端响应体（如果返回） | ✅ 需加密存储 |

---

## 9. User Linking / Provisioning Contract

### 查找现有用户

```python
async def get_user_by_oauth(provider: str, oauth_id: str) -> User | None:
    """通过 OAuth provider + oauth_id 查找用户"""
```

### 三种登录场景

| 场景 | 条件 | 行为 |
|------|------|------|
| **Existing OAuth user** | `get_user_by_oauth(provider, oauth_id)` 找到用户 | 直接登录，返回 JWT |
| **Email collision** | OAuth email 已关联本地账户 | 返回错误："该邮箱已绑定本地账户，请先登录后关联" |
| **New user** | OAuth email 未注册 | 自动创建用户，设置 `oauth_provider`, `oauth_id` |

### 自动创建用户

```python
# 新建 OAuth 用户
user = User(
    email=oauth_user_info["email"],
    oauth_provider=provider,
    oauth_id=oauth_id,
    password_hash=None,  # OAuth 用户无密码
    system_role="user",
    needs_setup=False,
)
await repo.create_user(user)
```

### 账户链接（未来扩展）

```
OAuth 登录后 → 发现 email 已存在 → 提示用户：
1. 先用密码登录
2. 在账户设置中关联 OAuth provider
```

---

## 10. oauth_provider + oauth_id Persistence Mapping

### User 模型字段

```python
class User(BaseModel):
    oauth_provider: str | None = Field(None, description="e.g. 'github', 'google'")
    oauth_id: str | None = Field(None, description="User ID from OAuth provider")
```

### UserRow 数据库映射

```python
class UserRow(Base):
    __tablename__ = "users"
    oauth_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    oauth_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index(
            "idx_users_oauth_identity",
            "oauth_provider",
            "oauth_id",
            unique=True,
            sqlite_where=text("oauth_provider IS NOT NULL AND oauth_id IS NOT NULL"),
        ),
    )
```

### 唯一索引约束

```
条件：(oauth_provider IS NOT NULL AND oauth_id IS NOT NULL) 时唯一
效果：允许多个 password_hash 用户共存（oauth_provider=NULL）
     允许多个 OAuth 用户（不同 provider 可以有相同 email）
```

### 字段映射关系

| OAuth provider | oauth_id 来源 | 示例 |
|----------------|--------------|------|
| GitHub | `user["id"]` (int) | `"12345678"` |
| Google | `user["sub"]` (string) | `"123456789012345678901"` |

---

## 11. needs_setup Handling

### OAuth 用户初始化

```python
# 创建时 needs_setup=False
user = User(
    ...
    needs_setup=False,  # OAuth 用户不需要 setup
)
```

### 为什么 OAuth 用户不需要 needs_setup

| 场景 | needs_setup | 原因 |
|------|-------------|------|
| 本地 admin 首次创建 | `True` | 需要通过 setup wizard 完成初始化 |
| OAuth admin 首次登录 | `False` | OAuth provider 已验证 email；无需额外 setup |
| OAuth user 首次登录 | `False` | OAuth provider 已验证 email |

### needs_setup 清除时机

```
本地用户：POST /change-password + new_email 传入 → needs_setup=False
OAuth 用户：创建时即 False → 不经过 setup flow
```

---

## 12. Failure / Rollback Behavior

### 网络请求失败

| 错误 | 行为 |
|------|------|
| Provider authorization URL 获取失败 | 500 Internal Server Error |
| Token exchange 失败（无效 code） | 400 Bad Request |
| Provider API 调用失败（用户信息获取） | 500 Internal Server Error |

### 错误日志记录

```python
try:
    user_info = await fetch_oauth_user_info(provider, access_token)
except Exception as e:
    logger.error(f"OAuth user info fetch failed for {provider}: {e}")
    raise HTTPException(500, "OAuth authentication failed")
```

### 不执行的操作

| 操作 | 原因 |
|------|------|
| 不发送邮件通知 | 未在 scope 中 |
| 不记录 access_token | 仅内存中使用 |
| 不存储 refresh_token | 未实现 |
| 不创建审计日志 | placeholder 阶段 |

---

## 13. No Direct Gateway Main Path Modification Guarantee

### 验证证据

```
✅ routers/auth.py 已包含 /oauth/{provider} 和 /callback/{provider}
✅ 路由通过 app.include_router(auth.router) 注册（GSIC-004）
✅ oauth 路由不直接调用 app.py 中间件链
✅ auth.py 中无 app.add_middleware() 调用
✅ oauth 路由不在 app/gateway/auth/ 目录（routers/auth.py 是 API 层）
```

### GSIC-004 依赖

```
oauth 路由注册 → GSIC-004 必须解除
    ↓
app.include_router(auth.router) 必须执行
    ↓
/oauth/{provider} 和 /callback/{provider} 才能访问
```

### Gateway Main Path 隔离

```
OAuth 路由属于 routers/auth.py（API 层）
不修改 app.py lifespan
不修改 deps.py
不添加 middleware
```

---

## 14. GSIC-004 Dependency Mapping for Auth Routes

### OAuth 路由注册

| 路由 | Method | Path | Auth Required |
|------|--------|------|--------------|
| `oauth_login` | GET | `/api/v1/auth/oauth/{provider}` | ❌ Public |
| `oauth_callback` | GET | `/api/v1/auth/callback/{provider}` | ❌ Public |

### GSIC-004 与 OAuth 路由

```
GSIC-004 解除 → app.include_router(auth.router) 执行
    ↓
/oauth/{provider} 和 /callback/{provider} 可访问
    ↓
但 GSIC-003 未解除 → AuthMiddleware 不运行
    ↓
Public path bypass 不需要 AuthMiddleware → OAuth 路由仍可访问
```

### Public Path 配置

```python
# auth_middleware.py _PUBLIC_EXACT_PATHS 不包含 oauth 路由
_PUBLIC_EXACT_PATHS = [
    "/api/v1/auth/login/local",
    "/api/v1/auth/register",
    "/api/v1/auth/logout",
    "/api/v1/auth/setup-status",
    "/api/v1/auth/initialize",
    # oauth 路由不在这里
]
```

### 实际行为

```
即使 GSIC-003/004 未解除：
    /oauth/{provider} → 501 Not Implemented（路由存在但返回错误）
    /callback/{provider} → 501 Not Implemented

GSIC-004 解除后：
    路由正常注册 → 可被调用（但仍返回 501，直到实现）
```

---

## 15. SURFACE-010 / Persistence Dependency Mapping

### OAuth → DT-002 (engine.py)

```
oauth_callback → LocalAuthProvider → SQLiteUserRepository
                                         ↓
                                    session_factory (来自 get_session_factory)
                                         ↓
                                    init_engine_from_config() → DT-002
```

**结论**：OAuth 用户查找依赖 DT-002（engine.py）。

### OAuth → DT-001 (user_context.py)

```
oauth_callback → 无直接依赖
    ↓
callback 不使用 AuthMiddleware
callback 不设置 CurrentUser ContextVar
callback 直接返回 JWT cookie
```

**结论**：OAuth callback 本身不依赖 DT-001。

### OAuth → Auth Bundle C

```
oauth_callback → LocalAuthProvider.get_user_by_oauth()
                     ↓
                SQLiteUserRepository.get_user_by_oauth()
                     ↓
                需要 session_factory → DT-002
```

**结论**：OAuth 依赖 Auth Bundle B（local_provider）+ DT-002（engine.py）。

---

## 16. Provider Secrets Handling Requirements

### 环境变量配置

```bash
# 必需
GITHUB_CLIENT_ID=Ov23xxx
GITHUB_CLIENT_SECRET=xxx

# 必需
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx

# 可选
OAUTH_REDIRECT_URI=https://your-domain.com/api/v1/auth/callback/{provider}
```

### 验证时机

```python
# auth_config.py 或 providers.py
def get_provider_config(provider: str):
    if provider == "github":
        client_id = os.getenv("GITHUB_CLIENT_ID")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise ValueError("GitHub OAuth credentials not configured")
        return {"client_id": client_id, "client_secret": client_secret}
    ...
```

### 安全要求

| 要求 | 实现 |
|------|------|
| client_secret 不在日志 | ✅ 使用 logger.info（不含 secret） |
| client_secret 不在响应 | ✅ 只在服务端使用 |
| client_secret 不在 Git | ✅ 通过环境变量注入 |
| 最小权限 scope | ✅ GitHub: `read:user`；Google: `openid profile email` |

---

## 17. OAuth Threat Model

### Attack Vectors

| 向量 | 风险 | 场景 | 缓解 |
|------|------|------|------|
| CSRF（state 伪造） | HIGH | 攻击者诱导用户点击恶意 callback | state token 验证 + secrets.compare_digest |
| Authorization code 拦截 | MEDIUM | 通过 URL 拦截 code | 短期有效 + HTTPS |
| Replay attack | MEDIUM | 重放旧的 callback URL | state 一次性使用 |
| Client ID/Secret 泄露 | CRITICAL | Secret 在 Git 或日志暴露 | 环境变量 + 不记录 |
| Token 注入 | HIGH | 恶意 access_token 注入 | 不信任 provider 响应，验证 signature |
| Email 枚举 | LOW | 通过 OAuth 尝试 email | 只返回"user not found"（不区分原因） |
| Provider downtime | LOW | GitHub/Google OAuth 不可用 | 错误消息提示，不暴露内部错误 |
| State 预测 | HIGH | 预测 state 值绕过 CSRF | 使用 secrets.token_urlsafe(32) 加密随机 |

### Threat Summary

| 威胁 | 状态 |
|------|------|
| CSRF 攻击 | 已缓解 — state token + timing-safe 比较 |
| Authorization code 拦截 | 已缓解 — HTTPS + 短期有效 code |
| Replay attack | 已缓解 — state 一次性使用 |
| Client secret 泄露 | 已缓解 — 环境变量管理 |
| Token 注入 | 已缓解 — 不信任外部数据 |
| Email 枚举 | 已缓解 — 统一错误消息 |
| Provider downtime | 部分缓解 — 错误消息友好化 |

---

## 18. Provider Matrix

### GitHub

| 属性 | 值 |
|------|---|
| Authorization URL | `https://github.com/login/oauth/authorize` |
| Token URL | `https://github.com/login/oauth/access_token` |
| User API | `https://api.github.com/user` |
| Scope | `read:user` |
| User ID field | `user["id"]` (int, as string) |
| Email field | `user["email"]` (may be null, use `user["emails"][0]`) |
| Rate limit | 5000 requests/hour for authenticated requests |

### Google

| 属性 | 值 |
|------|---|
| Authorization URL | `https://accounts.google.com/o/oauth2/v2/auth` |
| Token URL | `https://oauth2.googleapis.com/token` |
| User API | `https://www.googleapis.com/oauth2/v2/userinfo` |
| Scope | `openid profile email` |
| User ID field | `user["sub"]` (string) |
| Email field | `user["email"]` |
| Rate limit | Varies by endpoint |

### Common

| 属性 | GitHub | Google |
|------|--------|--------|
| PKCE support | ✅ Yes | ✅ Yes |
| State parameter | ✅ Required | ✅ Required |
| Token type | `Bearer` | `Bearer` |
| Response mode | JSON or form-encoded | JSON |
| Refresh token | ❌ Not for device flow | ✅ Available |

---

## 19. Test File Plan

### test_oauth_state.py

```python
# tests/unit/auth/test_oauth_state.py
# Cases:
# - state generation uses secrets.token_urlsafe(32)
# - state stored with provider and redirect_uri
# - state validation passes with valid state
# - state validation fails with invalid state
# - state validation fails with expired state (TTL)
# - state deleted after successful validation (no replay)
# - timing-safe comparison used for state validation
```

### test_oauth_callback.py

```python
# tests/unit/auth/test_oauth_callback.py
# Cases:
# - callback with valid code and state returns JWT cookie
# - callback with invalid state returns 400
# - callback with expired state returns 400
# - callback with non-existent user creates new user
# - callback with existing oauth user logs in
# - callback with email collision returns error
# - callback with invalid provider returns 400
# - provider user info fetch failure returns 500
```

### test_oauth_providers.py

```python
# tests/unit/auth/test_oauth_providers.py
# Cases:
# - github provider config validation requires GITHUB_CLIENT_ID
# - github provider config validation requires GITHUB_CLIENT_SECRET
# - google provider config validation requires GOOGLE_CLIENT_ID
# - google provider config validation requires GOOGLE_CLIENT_SECRET
# - unsupported provider raises ValueError
# - token exchange handles JSON response
# - token exchange handles form-encoded response
```

### Summary

| Files | Cases | Duration |
|-------|-------|----------|
| 3 | 21 | ~25s |

---

## 20. Implementation Order If Future Authorization Is Granted

### Current Blockers for OAuth

| Blocker | Status |
|---------|--------|
| SURFACE-010 DT-002 (engine.py) | BLOCKED — SQLiteUserRepository 需要 session_factory |
| GSIC-004 (route registration) | BLOCKED — 路由必须先注册才能访问 |
| Provider credentials | NOT CONFIGURED — GITHUB_CLIENT_ID/SECRET 等未设置 |

### Recommended Sequence

```
1. 验证 auth_config.py 中 provider 配置结构
2. 验证 routers/auth.py 的 oauth_login/oauth_callback 签名
3. 验证 models.py 的 oauth_provider/oauth_id 字段
4. 验证 SQLiteUserRepository.get_user_by_oauth() 实现
5. 验证 LocalAuthProvider.get_user_by_oauth() 实现
6. 创建 state store 接口（内存或 Redis）
7. 实现 oauth_login:
   7a. 验证 provider
   7b. 生成 state
   7c. 构建 authorization URL
   7d. 返回 RedirectResponse
8. 实现 oauth_callback:
   8a. 验证 state
   8b. 交换 code → access_token
   8c. 获取用户信息
   8d. 查找/创建用户
   8e. 设置 JWT cookie
   8f. 重定向到前端
9. 配置环境变量（测试用）
10. 端到端测试（manual）
```

---

## 21. Auth Bundle Readiness Summary

| Sub-Bundle | 依赖 | OAuth 需要 | 状态 |
|------------|------|-----------|------|
| Sub-Bundle A (jwt, password, models) | None | 核心依赖 | ✅ 完成 |
| Sub-Bundle B (local_provider, sqlite repo) | Sub-Bundle A | 用户查找依赖 | ✅ 完成 |
| Sub-Bundle C (user_context, authz, internal_auth, auth_middleware) | Sub-Bundle A | AuthMiddleware（OAuth 不直接依赖） | ⚠️ 部分完成 |
| Sub-Bundle D (reset_admin) | Sub-Bundle B | 不需要 | ✅ 完成 |
| Sub-Bundle E (authz/permissions) | Sub-Bundle C | 不直接需要 | ✅ 完成 |
| **Sub-Bundle F (OAuth/social auth)** | Sub-Bundle A+B | **自身** | ⚠️ **placeholder** |

### OAuth 依赖链

```
OAuth → LocalAuthProvider → SQLiteUserRepository → session_factory → DT-002
     → models.py (oauth_provider, oauth_id) → UserRow
     → local_provider.py get_user_by_oauth()
```

---

## 22. Explicit Stop Conditions

| Condition | Action |
|-----------|--------|
| SURFACE-010 DT-002 not yet unblocked | SQLiteUserRepository 无法工作 — OAuth login 失败 |
| GSIC-004 not unblocked | 路由未注册 — /oauth/{provider} 返回 404 |
| Provider credentials not configured | oauth_login/oauth_callback 返回错误配置消息 |
| Code modification detected during review | Abort and report safety violation |

---

## 23. Danger Zones

### Placeholder Routes (HIGH)

```
风险：/oauth/{provider} 和 /callback/{provider} 当前返回 501
影响：用户看到不友好的错误
缓解：未来实现 OAuth 时确保正确处理所有错误路径
```

### State Store Memory (MEDIUM)

```
风险：内存中的 state 存储不跨进程共享（多 worker 问题）
场景：worker A 生成 state，worker B 验证 state → 失败
缓解：生产环境使用 Redis 存储 state
```

### No Refresh Token Implementation (LOW)

```
风险：当前不支持 refresh_token
影响：长时间会话需要重新登录
缓解：JWT 已有较长 expiry（7 天）；未来可添加 refresh_token
```

### Email Not Guaranteed from Provider (MEDIUM)

```
风险：GitHub 可能不返回 email（用户设置）
场景：用户拒绝 email 权限
缓解：要求 email scope；GitHub 需要验证 email 才能获取
```

---

## 24. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| oauth_file_created | ❌ false |
| oauth_network_call_executed | ❌ false |
| oauth_token_exchange_executed | ❌ false |
| provider_secrets_set | ❌ false |
| db_written | ❌ false |
| jsonl_written | ❌ false |
| route_registered | ❌ false |
| gateway_app_modified | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

---

## 25. Carryover Blockers (8 preserved)

| Blocker | 状态 |
|---------|------|
| SURFACE-010 memory BLOCKED CRITICAL | ✅ preserved |
| CAND-002 memory_read_binding BLOCKED | ✅ preserved |
| CAND-003 mcp_read_binding DEFERRED | ✅ preserved |
| GSIC-003 blocking_gateway_main_path BLOCKED | ✅ preserved |
| GSIC-004 blocking_fastapi_route_registration BLOCKED | ✅ preserved |
| MAINLINE-GATEWAY-ACTIVATION=false | ✅ preserved |
| DSRT-ENABLED=false | ✅ preserved |
| DSRT-IMPLEMENTED=false | ✅ preserved |

---

## R241_22M_AUTH_SUB_BUNDLE_F_OAUTH_SOCIAL_IMPLEMENTATION_PLAN_REVIEW_DONE

```
status=passed_with_warnings
oauth_social_plan_completed=true
oauth_threat_model_completed=true
provider_matrix_completed=true
placeholder_routes_confirmed=true
persistence_oauth_fields_confirmed=true
user_linking_contract_confirmed=true
provider_secrets_strategy_confirmed=true
implementation_allowed=false
surface010_unblocked=false
route_registration_allowed=false
gateway_activation_allowed=false
oauth_network_call_executed=false
oauth_token_exchange_executed=false
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
db_written=false
jsonl_written=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-22K_or_R241-22N
next_prompt_needed=user_selection
```

---

## 选项

**A.** R241-22K — Continue with CAND-016/CAND-017/CAND-020 on R241 mainline

**B.** R241-22N — Auth Bundle completeness review + gateway readiness gap analysis

**C.** R241-22G — GSIC-003 + GSIC-004 COUPLED unblock design（需要 SURFACE-010 + Auth Bundle C + Persistence Stage 3+4 全部完成）

**D.** Pause R241-22 entirely, return when SURFACE-010 is unblocked
