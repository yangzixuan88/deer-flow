# R241-22B Auth Sub-Bundle C Implementation Plan Review

**报告ID**: R241-22B_AUTH_SUB_BUNDLE_C_IMPLEMENTATION_PLAN_REVIEW
**生成时间**: 2026-04-29T13:30:00+08:00
**阶段**: Phase 22B — Auth Sub-Bundle C Implementation Plan Review
**前置条件**: R241-22A Memory Runtime Unblock Design Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: auth_sub_bundle_c_plan_completed_no_route_registration_no_gateway_modification
**auth_sub_bundle_c_plan_completed**: true
**implementation_allowed**: false
**surface010_unblocked**: false
**no_route_registration_guaranteed**: true
**no_gateway_main_path_modification_guaranteed**: true

**关键结论**：
- Sub-Bundle C 包含 4 个文件：user_context.py, auth_middleware.py, authz.py, internal_auth.py
- 所有文件仅提供 runtime 基础设施，**不注册任何 FastAPI routes**
- auth_middleware.py 依赖 user_context (SURFACE-010 direct)，但 middleware 本身不修改 gateway/app.py
- GSIC-003/GSIC-004 影响：Sub-Bundle C 不直接触发，但 auth_middleware 的使用方 (app.py) 会触发 GSIC-003
- 实现顺序：user_context → authz (可并行) → internal_auth → auth_middleware

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. Sub-Bundle C File Inventory

### Files Overview

| File | Candidate | Type | LOC | SURFACE-010 | Route Reg | Gateway Mod |
|------|----------|------|-----|-------------|-----------|-------------|
| `auth_middleware.py` | CAND-005 | Starlette BaseHTTPMiddleware | ~120 | **DIRECT** | ❌ | ❌ |
| `user_context.py` | N/A | ContextVars module | 147 | **DIRECT** | ❌ | ❌ |
| `internal_auth.py` | N/A | Internal auth utils | 40 | indirect | ❌ | ❌ |
| `authz.py` | N/A | Decorator definitions | ~120 | ❌ | ❌ | ❌ |

**Total**: 4 files, ~327 LOC
**No route registration**: ✅ guaranteed
**No gateway main path modification**: ✅ guaranteed

### Why Safe Despite SURFACE-010

```
Sub-Bundle C provides runtime infrastructure (ContextVar) but does NOT:
1. Register FastAPI routes
2. Modify gateway/app.py middleware chain
3. Call app.add_middleware() or app.include_router()

auth_middleware.py provides the middleware CLASS that app.py imports and chains.
The middleware class definition does NOT modify app.py — the IMPORT and CHAINING
in app.py is the GSIC-003 modification, not Sub-Bundle C.

Therefore: Sub-Bundle C is safe at the DESIGN level; actual app.py modification
is a separate step under GSIC-003.
```

---

## 4. user_context.py Implementation Contract

**文件**: `backend/packages/harness/deerflow/runtime/user_context.py`
**行数**: 147 LOC
**验证**: 上游内容已读取确认

### Core Type Definitions

```python
# Structural Protocol — any object with .id: str satisfies this
class CurrentUser(Protocol):
    id: str

# ContextVar — asyncio task-local, default None
_current_user: Final[ContextVar[CurrentUser | None]] = ContextVar(
    'deerflow_current_user', default=None
)
```

### API Surface

| Function | Signature | Contract |
|----------|-----------|----------|
| `set_current_user` | `(user: CurrentUser) -> Token` | Returns reset token; **MUST** call `reset_current_user(token)` in finally |
| `reset_current_user` | `(token: Token) -> None` | Restores context to token-captured state |
| `get_current_user` | `() -> CurrentUser \| None` | Safe to call anywhere; returns None if unset |
| `require_current_user` | `() -> CurrentUser` | **Raises RuntimeError** if unset |
| `get_effective_user_id` | `() -> str` | Returns `user.id` or `'default'` if unset |
| `resolve_user_id` | `(value, method_name) -> str \| None` | AUTO→contextvar, str→verbatim, None→bypass |

### Three-State Semantics for user_id Parameter

| Value | Behavior |
|-------|----------|
| `AUTO` (sentinel) | Read from contextvar; raise RuntimeError if unset |
| `explicit str` | Use provided str verbatim, overriding contextvar |
| `explicit None` | No WHERE clause — migration/CLI path |

---

## 5. ContextVar Token Reset Contract

### Mandatory Pattern

```python
token = set_current_user(user)
try:
    # code that uses user context
    result = await call_next(request)
finally:
    reset_current_user(token)  # ALWAYS reset, even on exception
```

### Why Mandatory

| Risk | Without Reset | With Token Reset |
|------|---------------|------------------|
| Memory leak | ContextVar retains reference to user object | Context cleared, GC can collect |
| Cross-request contamination | Next request might see previous user's context | Context properly restored |

### Anti-Patterns

```python
# ❌ WRONG — no reset
set_current_user(user)
await something()

# ❌ WRONG — reset before potential exception
set_current_user(user)
if not check():
    reset_current_user(token)  # too early
await risky_call()  # no cleanup if this throws

# ❌ WRONG — asyncio task without copy_context
async def bg_task():
    # inherits parent context — may see wrong user
    pass
asyncio.create_task(bg_task())  # should use copy_context() for isolation

# ✅ CORRECT — finally block
token = set_current_user(user)
try:
    await call_next(request)
finally:
    reset_current_user(token)
```

---

## 6. auth_middleware.py Try/Finally Safety Contract

**文件**: `backend/app/gateway/auth_middleware.py`
**类型**: Starlette `BaseHTTPMiddleware`
**行数**: ~120 LOC

### Dispatch Contract

```python
async def dispatch(self, request: Request, call_next):
    # Step 1: Public path bypass
    if _is_public(request.url.path):
        return await call_next(request)

    # Step 2: Internal auth (IM channels, etc.)
    if is_valid_internal_auth_token(request.headers.get(INTERNAL_AUTH_HEADER_NAME)):
        internal_user = get_internal_user()
        token = set_current_user(internal_user)
    # Step 3: Cookie/JWT validation
    else:
        user = await get_optional_user_from_request(request)
        if user is None:
            raise HTTPException(401)
        token = set_current_user(user)

    # Step 4: try/finally — ALWAYS reset
    try:
        return await call_next(request)
    finally:
        reset_current_user(token)
```

### Fail-Closed Guarantee

| Path Type | Behavior |
|-----------|----------|
| Public (`/health`, `/docs`, `/api/v1/auth/login/*`, etc.) | No auth check |
| Non-public with valid cookie/JWT | Set context → call → reset |
| Non-public without valid auth | **401 Unauthorized** immediately |

### What Sub-Bundle C Does NOT Do

| Action | Who Does It | Blocker |
|--------|-------------|---------|
| Register routes | `routers/auth.py` | GSIC-004 |
| Add middleware to app | `app.py` (imports and chains) | GSIC-003 |
| Initialize persistence engine | `deps.py` langgraph_runtime | SURFACE-010 |

**Sub-Bundle C provides the middleware class; app.py performs the chain.**

---

## 7. internal_auth.py Read-Only Boundary

**文件**: `backend/app/gateway/internal_auth.py`
**行数**: 40 LOC
**验证**: 上游内容已读取确认

### Read-Only Evidence

```python
# internal_auth.py — IMPORT ONLY, no ContextVar write
from deerflow.runtime.user_context import DEFAULT_USER_ID

def get_internal_user():
    return SimpleNamespace(id=DEFAULT_USER_ID, system_role="internal")
```

| Property | Value |
|----------|-------|
| Calls `set_current_user`? | ❌ NO |
| Calls `reset_current_user`? | ❌ NO |
| Modifies gateway main path? | ❌ NO |
| Registers routes? | ❌ NO |
| SURFACE-010 impact | Indirect (imports from user_context) |

**Usage**: Internal channel service (IM) calls use `X-DeerFlow-Internal-Token` header, get synthetic `internal` user.

---

## 8. authz.py Decorator-Only Boundary

**文件**: `backend/app/gateway/authz.py`
**行数**: ~120 LOC
**验证**: 上游内容已读取确认

### Decorator Definitions Only

```python
# authz.py — DECORATOR DEFINITIONS
class AuthContext:
    """Authentication context stored in request.state.auth"""
    ...

def require_auth():
    """Sets request.state.auth"""
    ...

def require_permission(resource, action, owner_check=False):
    """Permission check decorator"""
    ...
```

### No Route Registration Evidence

| Check | Result | Evidence |
|-------|--------|----------|
| Calls `app.add_api_route`? | ❌ NO | Decorator definitions only |
| Calls `router.get/post/etc`? | ❌ NO | Applied by routers, not defined here |
| Calls `app.include_router`? | ❌ NO | Same |

**Decorators are APPLIED in router files (e.g., `routers/auth.py`), not registered by authz.py itself.**

---

## 9. SURFACE-010 Evidence Mapping

### CV-ISO Test → File Mapping

| Test | File(s) | What It Validates |
|------|---------|-------------------|
| CV-ISO-01 | user_context.py | Sequential set/get/reset pattern |
| CV-ISO-02 | user_context.py | Concurrent task isolation |
| CV-ISO-03 | user_context.py | Background task inheritance |
| CV-ISO-04 | user_context.py | copy_context() for isolation |
| CV-ISO-05 | user_context.py | Token reset restores previous |
| CV-ISO-06 | user_context.py | require_current_user raises when unset |
| CV-ISO-07 | user_context.py | resolve_user_id AUTO sentinel |
| CV-ISO-08 | user_context.py | resolve_user_id explicit str |
| CV-ISO-09 | user_context.py | resolve_user_id None bypass |
| CV-ISO-10 | user_context.py | DEFAULT_USER_ID fallback |

### MEM-LEAK Test → File Mapping

| Test | File(s) | What It Validates |
|------|---------|-------------------|
| MEM-LEAK-01 | user_context.py | 10k set/reset cycles, no leak |
| MEM-LEAK-02 | user_context.py | 10k without reset, growth plateaus |
| MEM-LEAK-03 | user_context.py + auth_middleware | 100 concurrent 30s, memory stable |
| MEM-LEAK-04 | user_context.py | Error path, no leak |

### Rollback Expectations

| Failure Scenario | Expected Behavior |
|-----------------|-------------------|
| user_context.py import fails | All calls raise NameError — fail fast |
| require_current_user called without context | RuntimeError raised — fail fast, no contamination |
| auth_middleware token reset fails | ContextVar may leak — but middleware chain broken → visible error |

---

## 10. No Route Registration Guarantee

**Guarantee ID**: GRT-NO-ROUTE-REG

| File | Route Registration | Evidence |
|------|---------------------|----------|
| `user_context.py` | ❌ NONE | ContextVar definition only |
| `authz.py` | ❌ NONE | Decorator definitions only |
| `internal_auth.py` | ❌ NONE | Utility functions only |
| `auth_middleware.py` | ❌ NONE | BaseHTTPMiddleware subclass, added to app but does NOT register routes |

**GSIC-004 Impact**: NONE — Sub-Bundle C does not trigger FastAPI route registration.

---

## 11. No Gateway Main Path Modification Guarantee

**Guarantee ID**: GRT-NO-GATEWAY-MOD

| File | Gateway Mod | Evidence |
|------|--------------|----------|
| `user_context.py` | ❌ NONE | Standalone module |
| `authz.py` | ❌ NONE | Standalone module |
| `internal_auth.py` | ❌ NONE | Standalone module |
| `auth_middleware.py` | ❌ NONE | Provides class; app.py imports and chains |

**Note**: `app.py` modification (adding AuthMiddleware to the middleware chain) is the GSIC-003 concern. That modification happens when app.py is ported, not when auth_middleware.py is ported.

**GSIC-003 Impact**: Indirect — auth_middleware is USED BY app.py, but Sub-Bundle C does not modify app.py itself.

---

## 12. Test File Plan

| File ID | Test File | Cases | Framework | Duration |
|---------|-----------|-------|----------|----------|
| TF-01 | `tests/unit/runtime/test_user_context.py` | CV-ISO-01 through CV-ISO-10 | pytest-asyncio | 5s |
| TF-02 | `tests/unit/runtime/test_user_context_memory_leak.py` | MEM-LEAK-01 through MEM-LEAK-04 | pytest + memory_profiler | 2min |
| TF-03 | `tests/unit/gateway/test_auth_middleware.py` | dispatch, public bypass, fail-closed, token reset | pytest + httpx | 10s |
| TF-04 | `tests/unit/gateway/test_authz.py` | decorator, permissions, owner_check | pytest | 5s |

**Total**: 4 test files, 24 test cases, ~2.5 minutes

---

## 13. Implementation Order (If Authorization Granted)

| Step | File | Reason | Can Parallelize |
|------|------|--------|-----------------|
| **1** | `user_context.py` | Foundation — all depend on ContextVar | ✅ with step 2 |
| **2** | `authz.py` | Pure decorators, no runtime dep at import | ✅ with step 1 |
| **3** | `internal_auth.py` | Imports DEFAULT_USER_ID from user_context | Step 1 first |
| **4** | `auth_middleware.py` | Uses all three above | After steps 1+2+3 |

**Parallelization**: Step 1 + Step 2 can run in parallel (independent).
**Critical path**: Step 3 → Step 4 (sequential due to auth_middleware dependency)

---

## 14. Explicit Stop Conditions

| Condition | Action |
|-----------|--------|
| SURFACE-010 not unblocked | Do not implement Sub-Bundle C |
| Authorization scope does not expand | Design only, no file creation |
| CV-ISO / MEM-LEAK gates not all passed | Halt before implementation |
| Any test fails during validation | Investigate before proceeding |
| Code modification detected during review | Abort and report safety violation |

---

## 15. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| user_context_created | ❌ false |
| auth_middleware_created | ❌ false |
| authz_created | ❌ false |
| internal_auth_created | ❌ false |
| gateway_app_modified | ❌ false |
| route_registered | ❌ false |
| patch_applied | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

---

## 16. Carryover Blockers (8 preserved)

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

## R241_22B_AUTH_SUB_BUNDLE_C_IMPLEMENTATION_PLAN_REVIEW_DONE

```
status=passed_with_warnings
auth_sub_bundle_c_plan_completed=true
implementation_allowed=false
surface010_unblocked=false
files_planned=[user_context.py, authz.py, internal_auth.py, auth_middleware.py]
test_plan_completed=true
cv_iso_mapping_completed=true
mem_leak_mapping_completed=true
no_route_registration_guaranteed=true
no_gateway_main_path_modification_guaranteed=true
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-22C
next_prompt_needed=user_selection
```