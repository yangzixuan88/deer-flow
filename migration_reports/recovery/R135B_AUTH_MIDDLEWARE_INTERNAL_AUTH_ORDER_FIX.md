# R135B — AuthMiddleware Internal Auth Order Fix

**Phase:** R135B — AuthMiddleware Internal Auth Order Fix
**Generated:** 2026-04-30
**Status:** PASSED
**Preceded by:** R135
**Proceeding to:** R135C

---

## LANE 0 — Pressure Assessment

| Item | Value |
|------|-------|
| previous_phase | R135 |
| previous_status | partial |
| current_status | passed |
| recommended_pressure | XXL++ |
| reason | Minimal production logic repair; internal auth ordering defect blocks Option C harness |

---

## LANE 1 — Scope Gate

| Check | Result |
|-------|--------|
| scope_gate_passed | ✅ True |
| target_file | `backend/app/gateway/auth_middleware.py` |
| bug_confirmed | ✅ True (internal auth checked after access_token required) |
| allowed_files | `auth_middleware.py` only |
| forbidden_files | `csrf_middleware.py`, `authz.py`, `app.py`, `deps.py`, routers, config.yaml, .env |

---

## LANE 2 — Pre-Fix Reproduction

```
POST /api/threads with auth + CSRF (before fix)
Status: 401
Body: {"detail":{"code":"not_authenticated","message":"Authentication required"}}
```
✅ **Pre-fix reproduced** — internal auth header blocked by access_token requirement

---

## LANE 3 — Fix Applied

**File modified:** `backend/app/gateway/auth_middleware.py`

**Before (buggy):**
```python
# Line 82-91: access_token required FIRST
if not request.cookies.get("access_token"):
    return 401  # ← internal auth never checked
internal_user = None
if is_valid_internal_auth_token(...):
    internal_user = get_internal_user()
# ... then JWT validation unconditionally at line 128
```

**After (fixed):**
```python
# Internal auth checked FIRST
internal_user = None
if is_valid_internal_auth_token(request.headers.get(INTERNAL_AUTH_HEADER_NAME)):
    internal_user = get_internal_user()

if internal_user is not None:
    user = internal_user  # ← Priority path — no cookie/JWT needed
else:
    # JWT/session-cookie path only when internal auth absent
    if not request.cookies.get("access_token"):
        return 401
    user = await get_current_user_from_request(request)
```

**Key properties preserved:**
- CSRF middleware behavior unchanged (403 without token)
- JWT cookie auth path unchanged (401 without valid cookie)
- Public path logic unchanged
- User context stamping unchanged
- No new bypass flags

---

## LANE 4 — Static Validation

| Check | Result |
|-------|--------|
| py_compile | ✅ PASSED |
| ast_parse | ✅ PASSED |
| auth_middleware import | ✅ PASSED |
| gateway_app import | ✅ PASSED |
| TestClient creation | ✅ PASSED |
| GET /health | ✅ 200 |

---

## LANE 5 — Auth + CSRF Control Tests

| Test | Condition | Expected | Actual | Pass? |
|------|-----------|----------|--------|-------|
| 1 | POST without CSRF | 403 | 403 | ✅ |
| 2 | POST without auth | 401 | 401 | ✅ |
| 3 | POST with auth + CSRF | NOT 401 | **503** | ✅ |

Test 3 result changed from `401 not_authenticated` → `503 Checkpointer not available` — **auth fixed**, next blocker is store initialization (expected for smoke).

---

## LANE 6 — POST /api/threads Recheck

```
POST /api/threads with internal auth + CSRF
Status: 503
Body: {"detail":"Checkpointer not available"}
auth_blocked: False
csrf_blocked: False
thread_created: False
next_blocker_after_auth: store_not_initialized
```

✅ **Auth fixed** — no longer 401. Store not initialized (expected — app.state empty during smoke).

---

## LANE 7 — POST /runs Feasibility

| Item | Value |
|------|-------|
| post_runs_attempted | False |
| requires_R136_model_authorization | True |
| model_api_called | False |

`create_run()` has `@require_permission("runs", "create", owner_check=True, require_existing=True)`. Auth fix validated but model risk requires R136 authorization before executing runs.

---

## LANE 8 — Regression Guard

| Check | Result |
|-------|--------|
| csrf_behavior_changed | ❌ False — 403 still returned without token |
| auth_flags_changed | ❌ False |
| db_written | ❌ False |
| jsonl_written | ❌ False |
| gateway_started | ❌ False |
| regression_guard_passed | ✅ True |

---

## LANE 9 — Commit

| Item | Value |
|------|-------|
| commit_created | ✅ True |
| commit_sha | `2e1a69da` |
| message | fix(gateway): honor internal auth before session cookie lookup |
| push_executed | ❌ False |

---

## Final Report

```
R135B_AUTH_MIDDLEWARE_INTERNAL_AUTH_ORDER_FIX_DONE

status=passed
pressure_assessment_completed=true
recommended_pressure=XXL++
scope_gate_passed=true
bug_confirmed=true
pre_fix_reproduced=true
pre_fix_status=401
fix_applied=true
modified_files=["backend/app/gateway/auth_middleware.py"]
py_compile_passed=true
ast_parse_passed=true
gateway_app_import_passed=true
testclient_passed=true
health_200=true
without_csrf_status=403
without_auth_status=401
with_auth_csrf_status=503
csrf_still_enforced=true
auth_internal_header_works=true
auth_jwt_path_preserved=true
create_thread_status=503
auth_blocked=false
csrf_blocked=false
next_blocker_after_auth=store_not_initialized
post_runs_attempted=false
requires_R136_model_authorization=true
model_api_called=false
regression_guard_passed=true
csrf_behavior_changed=false
auth_flags_changed=false
db_written=false
jsonl_written=false
gateway_started=false
commit_created=true
commit_sha=2e1a69da
push_executed=false
blockers_preserved=true
safety_violations=[]
recommended_next_phase=R135C_AUTH_CSRF_HARNESS_HTTP_ENDPOINT_RETRY
next_prompt_needed=R135C
```

---

*Generated by Claude Code — R135B (AuthMiddleware Internal Auth Order Fix)*
