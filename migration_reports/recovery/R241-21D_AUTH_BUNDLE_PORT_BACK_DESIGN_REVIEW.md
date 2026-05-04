# R241-21D Auth Bundle Port-Back Design Review

**报告ID**: R241-21D_AUTH_BUNDLE_PORT_BACK_DESIGN_REVIEW
**生成时间**: 2026-04-29T11:30:00+08:00
**阶段**: Phase 21D — Auth Bundle Port-Back Design Review
**前置条件**: R241-21C CAND-001/CAND-005 Path Verification (blocked)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: auth_bundle_design_review_completed_interface_stub_viable
**auth_bundle_design_completed**: true
**implementation_allowed**: false (design only, no implementation this phase)
**surface_010_implicated**: true (user_context.py)
**gsic_implicated**: false (auth bundle does not register routes directly)

**关键结论**：
- Auth bundle 可拆分为 pure-Python interface stub + runtime-dependent implementation
- 11/13 files are pure Python (no runtime activation)
- 2 files implicated: auth_middleware.py + user_context.py (SURFACE-010)
- reset_admin.py depends on persistence.engine (SURFACE-010 related)
- No FastAPI route registration in auth bundle itself
- Auth stub design viable for future implementation

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. Auth Bundle Dependency Graph

```
auth/__init__.py (root aggregate)
├── auth/config.py (standalone — no runtime)
├── auth/errors.py (standalone — no runtime)
├── auth/jwt.py (standalone — no runtime)
│   └── auth/config.py, auth/errors.py
├── auth/password.py (standalone — no runtime)
├── auth/models.py (standalone — no runtime)
├── auth/providers.py (standalone — no runtime)
├── auth/repositories/base.py (standalone — no runtime)
├── auth/local_provider.py (standalone — no runtime)
│   ├── auth/providers.py
│   ├── auth/models.py
│   ├── auth/password.py
│   └── auth/repositories/base.py
├── auth/reset_admin.py (CLI tool)
│   ├── deerflow.persistence.engine (SURFACE-010 related)
│   └── deerflow.persistence.user.model
└── (CAND-004) auth/reset_admin.py privileged

auth_middleware.py (CAND-005)
├── app.gateway.auth.errors
├── app.gateway.authz (decorator only — no route registration)
├── app.gateway.internal_auth
└── deerflow.runtime.user_context (SURFACE-010 implicated)

authz.py (decorator definitions)
└── app.gateway.auth.models

internal_auth.py
└── deerflow.runtime.user_context (SURFACE-010 implicated)

user_context.py (memory contextvar — SURFACE-010 root)
├── deerflow.runtime.user_context.DEFAULT_USER_ID
└── persistence reads from this (not writes)

langgraph_auth.py (CAND-006)
└── app.gateway.auth.jwt + app.gateway.deps
```

---

## 4. Required Files Inventory

### Core Auth Files (8 submodules + __init__)

| File | LOC | Runtime Impact | Local Exists | Notes |
|------|-----|----------------|--------------|-------|
| auth/__init__.py | 34 | None | ❌ | root aggregate |
| auth/config.py | 60 | None | ❌ | AuthConfig + get_auth_config |
| auth/errors.py | 44 | None | ❌ | enum definitions |
| auth/jwt.py | 53 | None | ❌ | JWT create/decode |
| auth/password.py | 75 | None | ❌ | bcrypt operations |
| auth/models.py | 42 | None | ❌ | User/UserResponse Pydantic |
| auth/providers.py | 22 | None | ❌ | abstract AuthProvider |
| auth/repositories/base.py | 92 | None | ❌ | abstract UserRepository |

### Implementation Files

| File | LOC | Runtime Impact | Local Exists | Notes |
|------|-----|----------------|--------------|-------|
| auth/local_provider.py | 88 | None | ❌ | concrete LocalAuthProvider |
| auth/reset_admin.py | ~80 | ⚠️ persistence.engine | ❌ | CLI tool, privileged |

### Middleware + Authz Files

| File | LOC | Runtime Impact | Local Exists | Notes |
|------|-----|----------------|--------------|-------|
| auth_middleware.py | ~120 | ⚠️ user_context | ❌ | CAND-005, SURFACE-010 |
| authz.py | ~120 | None | ❌ | decorator definitions |
| internal_auth.py | ~25 | ⚠️ user_context | ❌ | internal caller auth |

### Runtime Dependency

| File | LOC | Runtime Impact | Local Exists | Notes |
|------|-----|----------------|--------------|-------|
| user_context.py | ~120 | ⚠️ MEMORY CONTEXTVAR | ❌ | SURFACE-010 implicated |

### langgraph_auth

| File | LOC | Runtime Impact | Local Exists | Notes |
|------|-----|----------------|--------------|-------|
| langgraph_auth.py | ~100 | None | ❌ | CAND-006, depends on jwt.py |

---

## 5. Sub-Bundle Decomposition

### Sub-Bundle A: Pure Python Interface Stub (No Runtime Activation)

**Files**: config.py, errors.py, jwt.py, password.py, models.py, providers.py, repositories/base.py

| Property | Value |
|----------|-------|
| Files | 7 |
| Total LOC | ~388 |
| Runtime activation | **None** |
| FastAPI registration | None |
| Gateway modification | None |
| SURFACE-010 impact | **None** |
| GSIC impact | None |
| Privileged operations | None |
| **Can implement now** | Design: YES, Apply: NO (no auth dir) |

### Sub-Bundle B: Concrete Auth Implementation

**Files**: local_provider.py, auth/__init__.py (aggregate)

| Property | Value |
|----------|-------|
| Files | 2 |
| Total LOC | ~122 |
| Runtime activation | **None** |
| Dependencies | Sub-Bundle A |
| **Can implement now** | Design: YES, Apply: NO (needs Bundle A) |

### Sub-Bundle C: Auth Middleware (SURFACE-010 Implicated)

**Files**: auth_middleware.py, authz.py, internal_auth.py, user_context.py

| Property | Value |
|----------|-------|
| Files | 4 |
| Total LOC | ~385 |
| Runtime activation | **user_context contextvar** |
| SURFACE-010 implicated | **YES** |
| **Can implement now** | ❌ NO — SURFACE-010 must unblock first |

### Sub-Bundle D: Privileged Auth Tools

**Files**: reset_admin.py

| Property | Value |
|----------|-------|
| Files | 1 |
| LOC | ~80 |
| Runtime activation | persistence.engine |
| Privileged | **YES** (admin reset) |
| Auth review required | **YES** |
| **Can implement now** | ❌ NO — privileged + SURFACE-010 |

### Sub-Bundle E: langgraph_auth

**Files**: langgraph_auth.py

| Property | Value |
|----------|-------|
| Files | 1 |
| LOC | ~100 |
| Runtime activation | None |
| Dependencies | jwt.py + deps |
| **Can implement now** | ❌ NO — needs Bundle A + Bundle B first |

---

## 6. Privileged Auth Risk Matrix

| File | Risk Level | Privilege Type | Auth Review Required | persistence Dependency |
|------|------------|----------------|---------------------|----------------------|
| auth/reset_admin.py | **HIGH** | Admin password reset CLI | YES | ✅ Yes (engine) |
| auth/local_provider.py | MEDIUM | User auth provider | NO | Indirect (UserRepository) |
| auth_middleware.py | MEDIUM | HTTP middleware | NO | No |

---

## 7. SURFACE-010 / user_context Impact Analysis

### Files Implicated

| File | user_context Usage | Impact |
|------|-------------------|--------|
| user_context.py | **Definition** | MEMORY CONTEXTVAR — SURFACE-010 root |
| auth_middleware.py | `set_current_user`, `reset_current_user` | Sets contextvar on request |
| internal_auth.py | `DEFAULT_USER_ID` import | Read-only reference |

### Why user_context = SURFACE-010

The `user_context.py` module defines:
```python
user_context: ContextVar[CurrentUser | None] = ContextVar("user_context", default=None)
```

This is a **memory contextvar** — it holds per-request user state in memory. The SURFACE-010 blocker states "memory runtime BLOCKED CRITICAL" because activating memory-based request-scoped state requires the memory infrastructure to be verified stable first.

### unblock Prerequisites

| Step | Action | Dependency |
|------|--------|------------|
| 1 | SURFACE-010 memory unblock | Root blocker must first be resolved |
| 2 | Then Bundle C can be implemented | auth_middleware + user_context |

---

## 8. FastAPI / Gateway Route Impact Analysis

### Route Registration Check

| Check | Result | Notes |
|-------|--------|-------|
| auth bundle registers routes | ❌ NO | Only middleware + decorators |
| authz.py registers routes | ❌ NO | Decorator definitions only |
| auth_middleware.py registers routes | ❌ NO | Adds middleware to app |
| auth/routers/auth.py (CAND-007) | ✅ Has routes | **Different candidate — GSIC-004 blocked** |

### Gateway app.py Impact

auth_middleware.py is added to app.py:
```python
from app.gateway.auth_middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)
```

This modifies `app.py` (gateway main path) — which is **GSIC-003** implicated. However, this is a middleware addition, not a route registration.

---

## 9. Read-Only / Interface-Only Version Analysis

### Interface Stub Viability

**Question**: Can we implement an interface-only auth stub that doesn't touch runtime?

**Answer**: YES, for Sub-Bundles A + B

| Module | Interface Definition | Can Stub? |
|--------|---------------------|-----------|
| config.py | AuthConfig class | ✅ YES |
| errors.py | Enums + AuthErrorResponse | ✅ YES |
| jwt.py | TokenPayload + create/decode | ✅ YES |
| password.py | hash_password/verify_password | ✅ YES |
| models.py | User/UserResponse | ✅ YES |
| providers.py | AuthProvider ABC | ✅ YES |
| repositories/base.py | UserRepository ABC | ✅ YES |
| local_provider.py | LocalAuthProvider | ✅ YES (concrete) |
| auth/__init__.py | Module exports | ✅ YES |

**Constraint**: We cannot CREATE auth directory or files per current authorization. Design is viable; implementation requires separate authorization.

---

## 10. Implementation Timeline Constraints

| Phase | What Can Be Done | Blocker Status |
|-------|------------------|----------------|
| **Now (SURFACE-010 blocked)** | Design only — Sub-Bundle A + B interface stub design | SURFACE-010 blocks runtime activation |
| **After SURFACE-010 unblock** | Implement user_context.py + auth_middleware.py | SURFACE-010 must be resolved |
| **After GSIC-003/004 unblock** | Register routes in gateway/routers/auth.py | GSIC-003/004 must be resolved |
| **Any time (no runtime)** | Design review, interface stub design | No blockers for design |

---

## 11. Safe Design Subset (Interface Stub)

### Files That Form Safe Interface Stub

```
backend/app/gateway/auth/
├── __init__.py          # aggregate exports
├── config.py            # AuthConfig (no runtime)
├── errors.py            # AuthErrorCode, TokenError enums
├── jwt.py               # create_access_token, decode_token
├── password.py          # hash_password, verify_password
├── models.py            # User, UserResponse
├── providers.py          # AuthProvider ABC
├── repositories/
│   └── base.py          # UserRepository ABC
└── local_provider.py    # LocalAuthProvider (concrete, no runtime)
```

### Why Safe

| Property | Status |
|----------|--------|
| No memory contextvar | ✅ |
| No persistence.engine | ✅ |
| No FastAPI route registration | ✅ |
| No gateway modification | ✅ |
| No runtime activation | ✅ |
| Pure Python definitions | ✅ |
| No async initialization at import | ✅ |

### Why Still Blocked

| Constraint | Reason |
|------------|--------|
| Cannot create auth directory | Per authorization scope |
| Cannot create auth files | Per authorization scope |
| Bundle E depends on Bundle A | langgraph_auth needs jwt.py |

---

## 12. Carryover Blockers Impact on Auth Bundle

| Blocker | Auth Bundle Impact | Unblock Requirement |
|---------|-------------------|---------------------|
| SURFACE-010 | ⚠️ user_context.py + auth_middleware.py blocked | Memory runtime must be stable |
| CAND-002 | auth/jwt.py not directly blocked | memory_read_binding |
| GSIC-003 | app.py modification (middleware add) blocked | Gateway main path |
| GSIC-004 | auth/routers/auth.py route registration blocked | FastAPI route registration |
| MAINLINE-GATEWAY-ACTIVATION | Affects gateway activation chain | Gateway must be activatable |

---

## 13. Final Decision

**status**: passed_with_warnings
**decision**: auth_bundle_design_review_completed_interface_stub_viable
**auth_bundle_design_completed**: true
**bundle_candidates**: [CAND-001, CAND-002, CAND-004, CAND-005, CAND-006, CAND-023]
**required_files**: 13 files total
**safe_design_subset**: [config.py, errors.py, jwt.py, password.py, models.py, providers.py, repositories/base.py, local_provider.py]
**blocked_runtime_subset**: [auth_middleware.py, user_context.py, internal_auth.py, reset_admin.py]
**privileged_auth_subset**: [reset_admin.py]
**surface_010_implicated**: true
**gsic_implicated**: false (auth bundle itself doesn't register routes)
**implementation_allowed**: false (design only this phase)
**recommended_resume_point**: R241-21D
**next_prompt_needed**: user_selection

---

## 14. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| auth_dir_created | ❌ false |
| auth_file_created | ❌ false |
| gateway_modified | ❌ false |
| route_registered | ❌ false |
| patch_applied | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

---

## R241_21D_AUTH_BUNDLE_PORT_BACK_DESIGN_REVIEW_DONE

```
status=passed_with_warnings
decision=auth_bundle_design_review_completed_interface_stub_viable
auth_bundle_design_completed=true
bundle_candidates=[CAND-001,CAND-002,CAND-004,CAND-005,CAND-006,CAND-023]
required_files=13
safe_design_subset=[config.py,errors.py,jwt.py,password.py,models.py,providers.py,repositories/base.py,local_provider.py]
blocked_runtime_subset=[auth_middleware.py,user_context.py,internal_auth.py,reset_admin.py]
privileged_auth_subset=[reset_admin.py]
surface_010_implicated=true
gsic_implicated=false
implementation_allowed=false
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-21D
next_prompt_needed=user_selection
```
