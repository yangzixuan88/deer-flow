# R241-21C CAND-001 / CAND-005 Path and Structure Verification

**报告ID**: R241-21C_CAND001_CAND005_PATH_AND_STRUCTURE_VERIFICATION
**生成时间**: 2026-04-29T11:05:00+08:00
**阶段**: Phase 21C — CAND-001/CAND-005 Path and Structure Verification
**前置条件**: R241-21B Safe Config Change Batch 2 (blocked)
**状态**: ⚠️ BLOCKED_CANDIDATES_REQUIRES_AUTH_BUNDLE_DESIGN

---

## 1. Executive Conclusion

**状态**: ⚠️ BLOCKED_CANDIDATES_REQUIRES_AUTH_BUNDLE_DESIGN
**decision**: no_cand001_cand005_safe_to_apply_without_auth_bundle
**cand001_status**: requires_auth_bundle_design
**cand005_status**: requires_auth_bundle_design
**safe_to_implement_now**: []

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. Local Structure Verification

### backend/app/gateway/ Directory

| Item | Local Path | Status |
|------|------------|--------|
| `backend/app/gateway/` | ✅ EXISTS | gateway dir present |
| `backend/app/gateway/app.py` | ✅ EXISTS | gateway main app present |
| `backend/app/gateway/services.py` | ✅ EXISTS | CAND-019 (protected) |
| `backend/app/gateway/routers/` | ✅ EXISTS | routers directory present |
| `backend/app/gateway/auth/` | ❌ **NOT FOUND** | auth submodule missing |
| `backend/app/gateway/auth/__init__.py` | ❌ **NOT FOUND** | CAND-001 blocked |
| `backend/app/gateway/auth_middleware.py` | ❌ **NOT FOUND** | CAND-005 blocked |
| `backend/app/gateway/authz.py` | ❌ **NOT FOUND** | auth_middleware dependency |
| `backend/app/gateway/internal_auth.py` | ❌ **NOT FOUND** | auth_middleware dependency |
| `backend/packages/harness/deerflow/runtime/user_context.py` | ❌ **NOT FOUND** | auth_middleware dependency |

---

## 4. CAND-001 Dependency Analysis

### Upstream Content: `backend/app/gateway/auth/__init__.py`

**Imports**:
```python
from app.gateway.auth.config import AuthConfig, get_auth_config, set_auth_config
from app.gateway.auth.errors import AuthErrorCode, AuthErrorResponse, TokenError
from app.gateway.auth.jwt import TokenPayload, create_access_token, decode_token
from app.gateway.auth.local_provider import LocalAuthProvider
from app.gateway.auth.models import User, UserResponse
from app.gateway.auth.password import hash_password, verify_password
from app.gateway.auth.providers import AuthProvider
from app.gateway.auth.repositories.base import UserRepository
```

**Required Submodules** (8 total):
| Submodule | Local Exists? |
|-----------|--------------|
| `auth/config.py` | ❌ NOT FOUND |
| `auth/errors.py` | ❌ NOT FOUND |
| `auth/jwt.py` | ❌ NOT FOUND |
| `auth/local_provider.py` | ❌ NOT FOUND |
| `auth/models.py` | ❌ NOT FOUND |
| `auth/password.py` | ❌ NOT FOUND |
| `auth/providers.py` | ❌ NOT FOUND |
| `auth/repositories/base.py` | ❌ NOT FOUND |

**CAND-001 Assessment**:
- **Cannot apply independently** — requires entire auth module subtree
- **No local adaptation path** — all submodules missing
- **Status**: `requires_auth_bundle_design`
- **Priority**: P3 (after SURFACE-010 unblock)

---

## 5. CAND-005 Dependency Analysis

### Upstream Content: `backend/app/gateway/auth_middleware.py`

**Imports**:
```python
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from app.gateway.auth.errors import AuthErrorCode, AuthErrorResponse
from app.gateway.authz import _ALL_PERMISSIONS, AuthContext
from app.gateway.internal_auth import INTERNAL_AUTH_HEADER_NAME, get_internal_user, is_valid_internal_auth_token
from deerflow.runtime.user_context import reset_current_user, set_current_user
```

**Required Files** (4 total):
| File | Local Exists? |
|------|--------------|
| `app/gateway/auth/errors.py` | ❌ NOT FOUND |
| `app/gateway/authz.py` | ❌ NOT FOUND |
| `app/gateway/internal_auth.py` | ❌ NOT FOUND |
| `deerflow/runtime/user_context.py` | ❌ NOT FOUND |

**Additional Note**: `deerflow.runtime.user_context` is the same runtime module implicated by SURFACE-010 — activating this module would trigger memory runtime initialization.

**CAND-005 Assessment**:
- **Cannot apply independently** — requires auth errors + authz + internal_auth + user_context
- **Triggers SURFACE-010** — user_context is part of memory runtime
- **Status**: `requires_auth_bundle_design`
- **Priority**: P4 (after SURFACE-010 unblock)

---

## 6. Classification Results

### Status Definitions

| Status | Meaning |
|--------|---------|
| `safe_to_implement_now` | No blocker dependencies, isolated, config-only |
| `requires_auth_bundle_design` | Requires full auth module subtree to be ported first |
| `blocked_by_surface_010` | Depends on memory runtime (SURFACE-010 blocker) |
| `blocked_by_carryover` | Blocked by specific carryover blocker |

### CAND-001 Final Classification

| Field | Value |
|-------|-------|
| **Status** | `requires_auth_bundle_design` |
| **Reason** | 8 auth submodules missing locally |
| **Can apply independently** | ❌ NO |
| **SURFACE-010 impact** | None directly, but auth bundle does |
| **Related candidates** | CAND-002, CAND-004, CAND-006, CAND-023 (all auth) |

### CAND-005 Final Classification

| Field | Value |
|-------|-------|
| **Status** | `requires_auth_bundle_design` |
| **Reason** | 4 dependency files missing + user_context triggers SURFACE-010 |
| **Can apply independently** | ❌ NO |
| **SURFACE-010 impact** | ⚠️ YES — user_context is memory runtime |
| **Related candidates** | All auth candidates |

---

## 7. Auth Bundle Design Requirement

### All Auth Candidates

| ID | Path | Status | Dependencies |
|----|------|--------|---------------|
| CAND-001 | auth/__init__.py | requires_auth_bundle | 8 submodules |
| CAND-002 | auth/jwt.py | blocked | auth module |
| CAND-004 | auth/reset_admin.py | auth_review | auth module |
| CAND-005 | auth_middleware.py | requires_auth_bundle + SURFACE-010 | user_context |
| CAND-006 | langgraph_auth.py | blocked | upstream auth module |
| CAND-023 | auth/providers.py | auth_review | auth module |

**Conclusion**: All 6 auth candidates form a tightly coupled bundle. They cannot be applied individually.

---

## 8. Revised Safe Subset

After R241-21B + R241-21C verification:

| ID | Path | Status | Reason |
|----|------|--------|--------|
| CAND-022 | langgraph.json | ✅ no action needed | already adapted locally |
| CAND-001 | auth/__init__.py | ❌ requires_auth_bundle | 8 submodules missing |
| CAND-005 | auth_middleware.py | ❌ requires_auth_bundle + SURFACE-010 | user_context triggers memory |
| CAND-006 | langgraph_auth.py | ❌ blocked | upstream auth module |
| CAND-002 | auth/jwt.py | ❌ blocked (CAND-002) | memory_read_binding |
| CAND-014 | runtime/events/store/memory.py | ❌ blocked (SURFACE-010) | memory BLOCKED CRITICAL |
| CAND-015 | runtime/journal.py | ❌ blocked (SURFACE-010) | memory BLOCKED CRITICAL |
| CAND-019 | gateway/services.py | ❌ blocked (GSIC-003/004) | protected path |

**Safe subset for future implementation**: 0 candidates

---

## 9. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| patch_applied | ❌ false |
| auth_dir_created | ❌ false |
| auth_middleware_created | ❌ false |
| gateway_modified | ❌ false |
| route_registered | ❌ false |
| runtime_activated | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

---

## 10. Carryover Blockers (8 preserved)

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

## 11. Final Decision

**status**: blocked_candidates_requires_auth_bundle_design
**decision**: no_cand001_cand005_safe_to_apply_without_auth_bundle
**cand001_status**: requires_auth_bundle_design
**cand005_status**: requires_auth_bundle_design
**safe_to_implement_now**: []
**auth_bundle_required**: true
**auth_bundle_candidates**: [CAND-001, CAND-002, CAND-004, CAND-005, CAND-006, CAND-023]
**surface_010_related_cand005**: true
**runtime_touch_detected**: false
**dependency_execution_executed**: false
**code_modified**: false
**blockers_preserved**: true
**safety_violations**: []
**recommended_resume_point**: R241-21C
**next_prompt_needed**: user_selection

---

## R241_21C_CAND001_CAND005_PATH_AND_STRUCTURE_VERIFICATION_DONE

```
status=blocked_candidates_requires_auth_bundle_design
decision=no_cand001_cand005_safe_to_apply_without_auth_bundle
cand001_status=requires_auth_bundle_design
cand005_status=requires_auth_bundle_design
safe_to_implement_now=[]
requires_bundle_design=[CAND-001,CAND-005]
blocked_candidates=[CAND-001,CAND-002,CAND-004,CAND-005,CAND-006,CAND-023,CAND-014,CAND-015,CAND-019,CAND-022]
auth_bundle_required=true
auth_bundle_candidates_count=6
surface_010_related_cand005=true
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-21C
next_prompt_needed=user_selection
```
