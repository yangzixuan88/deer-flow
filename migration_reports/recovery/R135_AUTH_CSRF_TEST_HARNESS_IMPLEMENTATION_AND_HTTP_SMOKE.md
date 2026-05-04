# R135 — AUTH_CSRF Test Harness Implementation and HTTP Smoke

**Phase:** R135 — Auth+CSRF TestClient Harness Implementation + HTTP Smoke
**Generated:** 2026-04-30
**Status:** PARTIAL — blocked by production code defect
**Preceded by:** R134D
**Proceeding to:** R135B (diagnostic + fix authorization)

---

## LANE 0 — Pressure Assessment

| Item | Value |
|------|-------|
| previous_phase | R134D |
| previous_status | completed |
| current_status | partial_blocked |
| recommended_pressure | XXL++ |
| reason | Option C Auth+CSRF TestClient harness; no code change, no production DB, no model call |

---

## LANE 1 — Preflight Safety Gate

| Check | Result |
|-------|--------|
| workspace_clean | ✅ True |
| testclient_available | ✅ True |
| health_200 | ✅ True (GET /health → 200) |
| production_db_write_risk | ✅ none (app.state._state is empty — no stores initialized) |
| safe_to_post_threads | ✅ True (will get 503, not a real POST) |
| **preflight_passed** | ✅ **True** |

---

## LANE 2 — Auth + CSRF Harness Construction

| Item | Result |
|------|--------|
| internal_auth_headers_constructed | ✅ True |
| INTERNAL_AUTH_HEADER_NAME | `X-DeerFlow-Internal-Token` |
| auth header present | ✅ True |
| csrf_token generated | ✅ 86 chars |
| secret_values_printed | ✅ False |
| csrf_cookie_set | ✅ True |
| csrf_header_set | ✅ True |
| csrf_cookie_header_match | ✅ True |

---

## LANE 3 — Negative Control Checks

### Test 1: POST without CSRF token
```
POST /api/threads (no CSRF header, auth headers present)
Status: 403
Body: {"detail":"CSRF token missing. Include X-CSRF-Token header."}
```
✅ **CSRF gate validated** — correctly blocks without CSRF token

### Test 2: POST without auth header
```
POST /api/threads (CSRF token present, no auth header)
Status: 401
Body: {"detail":{"code":"not_authenticated","message":"Authentication required"}}
```
✅ **Auth gate validated** — correctly blocks without auth

### Test 3: POST with both auth + CSRF
```
POST /api/threads (auth + CSRF both present)
Status: 401 ← UNEXPECTED
Body: {"detail":{"code":"not_authenticated","message":"Authentication required"}}
```
❌ **Auth fails despite valid internal auth header**

---

## LANE 4 — Endpoint 1: POST /api/threads

| Item | Value |
|------|-------|
| create_thread_attempted | True |
| create_thread_status | 401 ❌ |
| thread_id | missing |
| thread_created | False |

**Root Cause:** `auth_middleware.py:82-130` — internal auth header check happens AFTER the access_token cookie check, and the JWT validation (`get_current_user_from_request`) is called unconditionally at line 128, before `internal_user` is evaluated at line 135.

---

## LANE 5 — Endpoint 2: GET /api/threads/{thread_id}

| Item | Value |
|------|-------|
| get_thread_attempted | True |
| get_thread_status | 401 ❌ |
| detail | Same auth bug; GET endpoints also require access_token cookie |

---

## LANE 6 — Endpoint 3: POST /api/threads/{thread_id}/runs (Guarded Feasibility)

| Item | Value |
|------|-------|
| post_runs_safe_without_model | True (static analysis) |
| post_runs_attempted | False |
| requires_R136_model_authorization | True |
| detail | Auth must be fixed first before POST /runs can be tested |

Static analysis: `create_run()` at `thread_runs.py:97` has `@require_permission("runs", "create", owner_check=True, require_existing=True)`. Even with auth fixed, this endpoint would attempt to start a worker. Model authorization (R136) is still required.

---

## LANE 7 — Endpoint 4: GET /api/threads/{thread_id}/runs/{run_id}

Not executed — auth bug blocks all endpoints.

---

## LANE 8 — Result Classification

### Bug Confirmed

**Location:** `auth_middleware.py:82-130`

**Type:** Logic error — internal auth header check happens AFTER JWT validation call

**Description:**
```python
# Line 82-91: access_token cookie check happens FIRST
if not request.cookies.get("access_token"):
    return 401  # ← Internal auth header is never checked if cookie is absent

# Line 92-94: Internal auth header check (too late)
internal_user = None
if is_valid_internal_auth_token(request.headers.get(INTERNAL_AUTH_HEADER_NAME)):
    internal_user = get_internal_user()

# Line 127-130: get_current_user_from_request called UNCONDITIONALLY
try:
    user = await get_current_user_from_request(request)  # ← Requires access_token cookie
except HTTPException:
    return 401
```

**Impact:** Option C test harness cannot work until this bug is fixed. `create_internal_auth_headers()` produces valid tokens that `is_valid_internal_auth_token()` correctly validates, but the code path never reaches that check when the access_token cookie is absent.

**Fix Needed:** Reorder the logic so internal auth is checked BEFORE the access_token cookie requirement, and internal_user bypasses `get_current_user_from_request()`.

### CSRF Analysis

| Item | Value |
|------|-------|
| csrf_cookie_set_correctly | ✅ True |
| csrf_header_set_correctly | ✅ True |
| csrf_validation_works | ✅ True |
| detail | CSRF mechanism is correctly implemented |

### Result Summary

| Criterion | Status |
|-----------|--------|
| r135_result | **partial** |
| auth_csrf_harness_status | **blocked_by_production_bug** |
| gateway_thread_endpoint_status | **blocked** |
| gateway_run_endpoint_status | **requires_fix_before_r136** |
| csrf_works | ✅ True |
| auth_broken | ❌ True |

---

## LANE 9 — Next Phase Decision

**Recommended next phase:** `R135B_DIAGNOSTIC_AND_FIX_AUTHORIZATION`

**Reason:** Must fix `auth_middleware.py` logic bug before Option C can work.

**Note:** The bug is in production code, not a test infrastructure issue. The fix requires modifying `auth_middleware.py` — which violates the "不修改代码" constraint of R135. This is a production code defect that was introduced during the cherry-pick of the auth bundle (commit `550b541f`).

---

## LANE 10 — Unknown Registry Update

| Unknown ID | Name | Status Change | Notes |
|------------|------|---------------|-------|
| U-013 | internal_auth_header_bypass | **CONFIRMED BROKEN** | `auth_middleware.py` logic error prevents internal auth from working |

---

## Final Report

```
R135_AUTH_CSRF_TEST_HARNESS_IMPLEMENTATION_AND_HTTP_SMOKE_DONE

status=partial
pressure_assessment_completed=true
preflight_passed=true
production_db_write_risk=none
safe_to_post_threads=true
internal_auth_headers_constructed=true
csrf_cookie_set=true
csrf_header_set=true
csrf_cookie_header_match=true
secret_values_printed=false
negative_without_csrf_status=403 (validated)
negative_without_auth_status=401 (validated)
csrf_gate_validated=true
auth_gate_validated=true
create_thread_attempted=true
create_thread_status=401 (BLOCKED by auth bug)
thread_created=false
get_thread_attempted=true
get_thread_status=401 (BLOCKED by auth bug)
post_runs_safe_without_model=true
post_runs_attempted=false
requires_R136_model_authorization=true
r135_result=partial
auth_csrf_harness_status=blocked_by_production_bug
gateway_thread_endpoint_status=blocked
gateway_run_endpoint_status=requires_fix_before_r136
csrf_works=true
auth_broken=true
bug_confirmed_in=auth_middleware.py:82-130
recommended_next_phase=R135B_DIAGNOSTIC_AND_FIX_AUTHORIZATION
code_modified=false
db_written=false
jsonl_written=false
gateway_started=false
model_api_called=false
mcp_runtime_called=false
tool_call_executed=false
push_executed=false
merge_executed=false
blockers_preserved=true
safety_violations=[]
next_prompt_needed=R135B_FIX_AUTHORIZATION
```

---

*Generated by Claude Code — R135 (Auth+CSRF Test Harness Implementation + HTTP Smoke)*
