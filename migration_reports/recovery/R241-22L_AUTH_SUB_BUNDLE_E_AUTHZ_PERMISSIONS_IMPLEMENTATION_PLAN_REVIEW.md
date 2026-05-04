# R241-22L Auth Sub-Bundle E (authz/permissions) Implementation Plan Review

**报告ID**: R241-22L_AUTH_SUB_BUNDLE_E_AUTHZ_PERMISSIONS_IMPLEMENTATION_PLAN_REVIEW
**生成时间**: 2026-04-29T17:00:00+08:00
**阶段**: Phase 22L — Auth Sub-Bundle E authz/permissions Implementation Plan Review
**前置条件**: R241-22J reset_admin Implementation Plan Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: authz_permissions_plan_completed_two_decorator_system_confirmed
**authz_plan_completed**: true
**two_layer_auth_confirmed**: true
**all_permissions_flat_model_confirmed**: true
**internal_auth_dt_independent_confirmed**: true
**langgraph_auth_shares_jwt_chain_confirmed**: true
**surface010_dt001_required_confirmed**: true
**gsic003_004_not_required_for_authz_confirmed**: true

**关键结论**：
- 两层认证系统：AuthMiddleware（全局 fail-closed 大门）+ `@require_auth`/`@require_permission`（路由级细粒度）
- 所有认证用户获得全部 6 个权限（ALL_PERMISSIONS）—— 无 RBAC 粒度
- `internal_auth.py` 完全独立于 SURFACE-010（进程内 32 字节 token）
- `langgraph_auth.py` 复用 gateway JWT 验证链（共享 `decode_token`）
- Authz/permissions 代码可独立于 GSIC-003/GSIC-004 验证

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. Two-Layer Auth System

### Layer 1: AuthMiddleware（全局 fail-closed 大门）

| 属性 | 值 |
|------|---|
| 文件 | `app/gateway/auth_middleware.py` |
| 行为 | 所有非 public 请求必须通过 JWT 验证 |
| public 路径 | `/health`, `/docs`, `/redoc`, `/openapi.json`, `/api/v1/auth/login/local`, `/register`, `/logout`, `/setup-status`, `/initialize` |
| 内部 token | `X-DeerFlow-Internal-Token` 绕过 JWT 检查 |
| 设置 | `request.state.user` + `request.state.auth = AuthContext(user, _ALL_PERMISSIONS)` |
| GSIC-003 target | ✅ 是（但 authz 验证不依赖它） |

### Layer 2: @require_auth / @require_permission（路由级装饰器）

| 属性 | 值 |
|------|---|
| 文件 | `app/gateway/authz.py` |
| `@require_auth` | 独立调用 `_authenticate(request)` — 自己的验证链 |
| `@require_permission` | 检查 `auth.has_permission(resource, action)` + `owner_check` |
| 装饰器顺序 | `@require_permission` 在 `@require_auth` 之上（从下往上执行） |

### 两层关系

```
请求 → AuthMiddleware (Layer 1)
           ↓ (未通过则 401)
       路由处理函数
           ↓ (@require_auth / @require_permission)
       路由级认证 (Layer 2)
```

**关键**：AuthMiddleware 是全局大门，路由装饰器是细粒度补充。Layer 1 失败 → 401；Layer 2 失败 → 403 或 404。

---

## 4. authz.py 文件清单

| 文件 | 路径 | LOC | 职责 |
|------|------|-----|------|
| `authz.py` | `app/gateway/authz.py` | ~180 | 装饰器 + AuthContext + Permissions |
| `auth_middleware.py` | `app/gateway/auth_middleware.py` | ~120 | AuthMiddleware (GSIC-003 target) |
| `internal_auth.py` | `app/gateway/internal_auth.py` | ~60 | 进程内 trusted token |
| `langgraph_auth.py` | `app/gateway/langgraph_auth.py` | ~80 | LangGraph SDK auth hooks |

**无路由文件修改**
**无 gateway main path 修改**

---

## 5. Permissions 定义

### 6 个权限常量

```python
class Permissions:
    THREADS_READ = "threads:read"
    THREADS_WRITE = "threads:write"
    THREADS_DELETE = "threads:delete"
    RUNS_CREATE = "runs:create"
    RUNS_READ = "runs:read"
    RUNS_CANCEL = "runs:cancel"

ALL_PERMISSIONS = [
    Permissions.THREADS_READ,
    Permissions.THREADS_WRITE,
    Permissions.THREADS_DELETE,
    Permissions.RUNS_CREATE,
    Permissions.RUNS_READ,
    Permissions.RUNS_CANCEL,
]
```

### 权限分配模型

| 用户类型 | 权限分配 |
|----------|----------|
| 认证用户 | **ALL_PERMISSIONS**（全部 6 个） |
| 未认证用户 | 无权限 |
| internal token | ALL_PERMISSIONS（通过 AuthContext） |

### 资源-操作矩阵

| 权限 | 资源 | 操作 |
|------|------|------|
| `threads:read` | thread | GET /api/v1/threads/{thread_id} |
| `threads:write` | thread | PUT/PATCH /api/v1/threads/{thread_id} |
| `threads:delete` | thread | DELETE /api/v1/threads/{thread_id} |
| `runs:create` | run | POST /api/v1/threads/{thread_id}/runs |
| `runs:read` | run | GET /api/v1/runs/{run_id} |
| `runs:cancel` | run | POST /api/v1/runs/{run_id}/cancel |

---

## 6. Decorator 清单

### @require_auth

```python
def require_auth(func):
    # 获取 request from kwargs
    # 调用 _authenticate(request)
    # 设置 request.state.auth = AuthContext(user, ALL_PERMISSIONS)
    # 未认证 → HTTPException(401)
    # _deerflow_test_bypass_auth=True → bypass（测试用）
```

### @require_permission

```python
def require_permission(resource, action, owner_check=False, require_existing=False):
    # 检查 auth.has_permission(resource, action)
    # 如果 owner_check=True:
    #     get_thread_store(request).check_access(thread_id, user_id, require_existing)
    # 无权限 → HTTPException(403)
    # 线程不存在 + require_existing=True → HTTPException(404)
```

### @auth.authenticate (LangGraph)

```python
@auth.authenticate
def authenticate(self, request):
    # CSRF 检查
    # cookie → session_id
    # decode_token
    # get_user + token_version 匹配
    # 返回 user_id
```

### @auth.on (LangGraph)

```python
@auth.on
async def on(self, ctx, store, **kwargs):
    # 写入操作：metadata.user_id = ctx.user.identity
    # 返回 filter dict: {user_id: ctx.user.identity}
```

---

## 7. AuthContext 契约

### __slots__

```python
class AuthContext:
    __slots__ = ("user", "permissions")
```

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `user` | User | `request.state.user` 的别名 |
| `permissions` | list[str] | ALL_PERMISSIONS（6 个） |

### 方法

| 方法 | 说明 |
|------|------|
| `is_authenticated` | `self.user is not None` |
| `has_permission(resource, action)` | 检查 `f"{resource}:{action}"` 是否在 permissions 中 |
| `require_user()` | `self.user` 为 None 则 raise |

### request.state 布局

```python
request.state.user   # User 对象（来自 AuthMiddleware 或 _authenticate）
request.state.auth   # AuthContext(user, ALL_PERMISSIONS)
```

---

## 8. Owner Check 契约

### 签名

```python
get_thread_store(request).check_access(thread_id, user_id, require_existing=False)
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `thread_id` | str | 线程 ID |
| `user_id` | str | 用户 ID |
| `require_existing` | bool | True = 不存在的线程返回 404；False = 允许不存在的线程（遗留兼容） |

### 行为

| 条件 | require_existing=False | require_existing=True |
|------|------------------------|----------------------|
| 线程存在 + 用户有权限 | ✅ 放行 | ✅ 放行 |
| 线程存在 + 用户无权限 | ❌ 403 | ❌ 403 |
| 线程不存在 | ✅ 放行（legacy 兼容） | ❌ 404 |
| 线程存在 + 无 ownership 元数据 | ❌ 403 | ❌ 403 |

---

## 9. internal_auth.py 契约

### 令牌

```python
_INTERNAL_AUTH_TOKEN = secrets.token_urlsafe(32)  # 进程内 32 字节
```

### 验证

```python
is_valid_internal_auth_token(token: str) -> bool
    # 使用 secrets.compare_digest 防止时序攻击
```

### 用户

```python
get_internal_user() -> SimpleNamespace(id=DEFAULT_USER_ID, system_role="internal")
```

### 关键属性

| 属性 | 值 |
|------|---|
| 进程内 | ✅ 不需要网络调用 |
| SURFACE-010 独立 | ✅ 不依赖 DT-001 或 DT-002 |
| 权限 | ALL_PERMISSIONS |
| 用途 | Gateway 内部 trusted 调用 |

---

## 10. langgraph_auth.py 契约

### 复用 gateway JWT 链

```python
@auth.authenticate  # → decode_token() → get_user() → token_version 匹配
```

### metadata 注入

```python
@auth.on
async def on(self, ctx, store, **kwargs):
    metadata.user_id = ctx.user.identity
    return {"user_id": ctx.user.identity}  # LangGraph store filter
```

### 配置文件

```json
// langgraph.json
{
  "auth": {
    "path": "app.gateway.langgraph_auth"
  }
}
```

---

## 11. Public / Protected Route Mapping

### Public Routes（无需认证）

| Method | Path | Auth Required |
|--------|------|--------------|
| GET | `/health` | ❌ |
| GET | `/docs` | ❌ |
| GET | `/redoc` | ❌ |
| GET | `/openapi.json` | ❌ |
| POST | `/api/v1/auth/login/local` | ❌ |
| POST | `/api/v1/auth/register` | ❌ |
| POST | `/api/v1/auth/logout` | ❌ |
| GET | `/api/v1/auth/setup-status` | ❌ |
| POST | `/api/v1/auth/initialize` | ❌ |
| GET | `/api/v1/auth/oauth/{provider}` | ❌ |
| GET | `/api/v1/auth/callback/{provider}` | ❌ |

### Protected Routes（需要认证）

| Method | Path | Permission | owner_check |
|--------|------|------------|-------------|
| GET | `/api/v1/threads` | threads:read | ❌ |
| POST | `/api/v1/threads` | threads:write | ❌ |
| GET | `/api/v1/threads/{thread_id}` | threads:read | optional |
| PUT | `/api/v1/threads/{thread_id}` | threads:write | optional |
| DELETE | `/api/v1/threads/{thread_id}` | threads:delete | ✅ require_existing=True |
| POST | `/api/v1/threads/{thread_id}/runs` | runs:create | optional |
| GET | `/api/v1/runs/{run_id}` | runs:read | optional |
| POST | `/api/v1/runs/{run_id}/cancel` | runs:cancel | optional |

---

## 12. GSIC-003 / GSIC-004 依赖关系

### Authz 与 GSIC-003

```
authz.py @require_auth → _authenticate(request)
                          ↓
                     AuthMiddleware (GSIC-003 target)
                          ↓
                     get_current_user_from_request()
                          ↓
                     decode_token() → get_user()
```

**结论**：`@require_auth` 依赖 AuthMiddleware 设置的 `request.state.user`。**GSIC-003 是必需的**。

### Authz 与 GSIC-004

```
app.py include_router(auth.router)  ← GSIC-004
    ↓
路由使用 @require_auth / @require_permission
```

**结论**：路由必须先注册才能应用装饰器。**GSIC-004 也是必需的**。

### Authz 独立于 GSIC-003/GSIC-004 的部分

| 组件 | GSIC-003 依赖 | GSIC-004 依赖 |
|------|--------------|--------------|
| `Permissions` 类 | ❌ | ❌ |
| `AuthContext` 类 | ❌ | ❌ |
| `@require_permission` 逻辑 | ❌ | ❌ |
| `internal_auth.py` | ❌ | ❌ |
| `langgraph_auth.py` | ❌ | ❌ |

---

## 13. SURFACE-010 依赖映射

### Authz → DT-001 (user_context.py)

```
auth_middleware.py → set_current_user(user)
                          ↓
                     user_context.py ContextVar
```

**结论**：AuthMiddleware 依赖 DT-001。

### Authz → DT-002 (engine.py)

```
无直接依赖
authz.py 不使用数据库
auth_middleware.py 不使用数据库
```

**结论**：authz/permissions 代码不依赖 DT-002。

### Authz → Auth Bundle C

```
authz.py @require_auth → _authenticate(request)
                              ↓
                         get_user_from_session() 或 get_current_user_from_request()
```

**结论**：authz 依赖 Auth Bundle C 的用户查找逻辑。

---

## 14. ALL_PERMISSIONS 扁平模型风险

### 当前实现

```python
request.state.auth = AuthContext(user, ALL_PERMISSIONS)  # 所有认证用户获得全部权限
```

### 风险

| 风险 | 严重性 | 说明 |
|------|--------|------|
| 无 RBAC 粒度 | MEDIUM | 所有认证用户可以删除任何线程、取消任何 run |
| 内部用户同等权限 | MEDIUM | internal token 获得 ALL_PERMISSIONS |
| 未来扩展点 | LOW | 权限系统已有结构，可扩展为角色 |

### 缓解

- owner_check 提供资源级保护
- 内部服务间调用使用 internal_auth（可信上下文）
- 日志记录操作（future audit trail）

### 改进机会

```python
# 未来可扩展为：
ADMIN_PERMISSIONS = [THREADS_READ, THREADS_WRITE, THREADS_DELETE, RUNS_CREATE, RUNS_READ, RUNS_CANCEL]
USER_PERMISSIONS = [THREADS_READ, THREADS_WRITE, RUNS_CREATE, RUNS_READ]
# 根据 system_role 分配不同权限集
```

---

## 15. Test File Plan

### test_authz.py

```python
# tests/unit/authz/test_authz.py
# Cases:
# - @require_auth sets request.state.auth on valid user
# - @require_auth raises 401 on missing auth
# - @require_permission grants access when user has permission
# - @require_permission raises 403 when user lacks permission
# - @require_permission with owner_check=True grants access to owner
# - @require_permission with owner_check=True denies non-owner
# - @require_permission with require_existing=True raises 404 for missing thread
# - @require_permission with require_existing=False allows missing thread
# - AuthContext.has_permission returns correct results
# - AuthContext.is_authenticated returns correct results
```

### test_internal_auth.py

```python
# tests/unit/authz/test_internal_auth.py
# Cases:
# - is_valid_internal_auth_token returns True for valid token
# - is_valid_internal_auth_token returns False for invalid token
# - get_internal_user returns SimpleNamespace with correct fields
# - constant token is process-local (not shared across processes)
```

### test_langgraph_auth.py

```python
# tests/unit/authz/test_langgraph_auth.py
# Cases:
# - @auth.authenticate calls decode_token with valid JWT
# - @auth.authenticate raises on invalid token
# - @auth.authenticate raises on expired token
# - @auth.authenticate raises on token_version mismatch
# - @auth.on injects user_id into metadata
# - @auth.on returns correct filter dict
```

### Summary

| Files | Cases | Duration |
|-------|-------|----------|
| 3 | 24 | ~20s |

---

## 16. Implementation Order If Authorized

### Current Blockers for Authz

| Blocker | Status |
|---------|--------|
| SURFACE-010 DT-001 (user_context.py) | BLOCKED — AuthMiddleware 依赖 set_current_user |
| Auth Bundle C (user lookup chain) | BLOCKED — @require_auth 需要 get_user() |
| GSIC-004 (route registration) | BLOCKED — 路由需先注册才能应用装饰器 |

### Recommended Sequence

```
1. 验证 authz.py, auth_middleware.py, internal_auth.py, langgraph_auth.py 源码
2. 验证 Permissions 和 AuthContext 类定义
3. 验证 @require_auth 和 @require_permission 装饰器逻辑
4. 验证 owner_check 实现（ThreadMetaStore.check_access）
5. 创建 tests/unit/authz/ 目录
6. 创建 test_authz.py — 实现所有 @require_permission 边界测试
7. 创建 test_internal_auth.py — 验证进程内 token 隔离
8. 创建 test_langgraph_auth.py — 验证 LangGraph SDK hooks
9. 如果 Auth Bundle C 完成 → 实现 auth_middleware.py 集成测试
```

---

## 17. Auth Bundle Readiness Summary

| Sub-Bundle | 依赖 | Authz 需要 | 状态 |
|------------|------|-----------|------|
| Sub-Bundle A (jwt, password, models) | None | 核心依赖 | ✅ 完成 |
| Sub-Bundle B (local_provider, sqlite repo) | Sub-Bundle A | 用户查找依赖 | ✅ 完成 |
| Sub-Bundle C (user_context, authz, internal_auth, auth_middleware) | Sub-Bundle A | **直接需要** | ⚠️ 部分完成 |
| Sub-Bundle D (reset_admin) | Sub-Bundle B | 不需要 | ✅ 完成 |
| Sub-Bundle E (authz/permissions) | Sub-Bundle C | **自身** | ✅ 计划完成 |

---

## 18. Explicit Stop Conditions

| Condition | Action |
|-----------|--------|
| SURFACE-010 DT-001 not yet unblocked | AuthMiddleware 无法使用 ContextVar — authz 功能部分不可用 |
| Auth Bundle C not complete | user lookup chain 不可用 |
| GSIC-004 not unblocked | 路由未注册，装饰器无法应用 |
| Code modification detected during review | Abort and report safety violation |

---

## 19. Danger Zones

### ALL_PERMISSIONS Flat Model (MEDIUM)

```
风险：所有认证用户获得全部 6 个权限
场景：普通用户可以删除任意线程
缓解：owner_check 提供资源级保护，但不能防止同一用户删除自己的其他线程
改进：未来添加角色分离
```

### internal_auth Process Isolation (LOW)

```
风险：_INTERNAL_AUTH_TOKEN 是进程内全局变量
场景：多进程部署时每个进程的 token 不同
缓解：内部调用只在同进程内有效，跨进程需要外部认证
```

### langgraph_auth Token Reuse (LOW)

```
风险：LangGraph SDK 使用与 gateway 相同的 JWT 链
场景：gateway token 泄露 → LangGraph 调用也被冒用
缓解：token_version 检查使旧 token 失效
```

---

## 20. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| authz_py_modified | ❌ false |
| auth_middleware_modified | ❌ false |
| internal_auth_modified | ❌ false |
| langgraph_auth_modified | ❌ false |
| route_registered | ❌ false |
| gateway_app_modified | ❌ false |
| db_written | ❌ false |
| jsonl_written | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

---

## 21. Carryover Blockers (8 preserved)

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

## R241_22L_AUTH_SUB_BUNDLE_E_AUTHZ_PERMISSIONS_IMPLEMENTATION_PLAN_REVIEW_DONE

```
status=passed_with_warnings
authz_plan_completed=true
two_layer_auth_confirmed=true
all_permissions_flat_model_confirmed=true
internal_auth_dt_independent_confirmed=true
langgraph_auth_shares_jwt_chain_confirmed=true
surface010_dt001_required_confirmed=true
gsic003_004_not_required_for_authz_confirmed=true
implementation_allowed=false
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
db_written=false
jsonl_written=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-22K_or_R241-22M
next_prompt_needed=user_selection
```

---

## 选项

**A.** R241-22K — Continue with CAND-016/CAND-017/CAND-020 on R241 mainline

**B.** R241-22M — Auth Bundle Sub-Bundle F (remaining OAuth/social auth) implementation plan review

**C.** R241-22G — GSIC-003 + GSIC-004 COUPLED unblock design（需要 SURFACE-010 + Auth Bundle C + Persistence Stage 3+4 全部完成）

**D.** Pause R241-22 entirely, return when SURFACE-010 is unblocked
