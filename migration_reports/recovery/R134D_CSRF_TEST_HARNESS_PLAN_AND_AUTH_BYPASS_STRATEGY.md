# R134D — CSRF Test Harness Plan and Auth Bypass Strategy

**Phase:** R134D — CSRF Test Harness Plan and Auth Bypass Strategy
**Generated:** 2026-04-30
**Status:** COMPLETED
**Preceded by:** R134C
**Proceeding to:** R135

---

## LANE 0 — Pressure Assessment

| Item | Value |
|------|-------|
| previous_phase | R134C |
| previous_status | passed |
| current_recommended_pressure | XXL++ |
| reason | Design legal Auth+CSRF test harness before any Gateway HTTP smoke; no patch this round. |

---

## LANE 1 — Real Login Path Feasibility

### Auth Endpoint: /api/v1/auth/login/local

| Property | Value |
|----------|-------|
| Path | `POST /api/v1/auth/login/local` |
| CSRF exempt | ✅ YES — in `_AUTH_EXEMPT_PATHS` |
| Sets `csrf_token` cookie | ✅ YES — line 93-102 of csrf_middleware.py |
| Sets `access_token` cookie | ✅ YES — JWT session cookie |
| Auth provider | `LocalAuthProvider` → `SQLiteUserRepository` |
| User storage | SQLAlchemy `users` table |

### Requirements

| Requirement | Status |
|-------------|--------|
| Valid email in `users` table | ❌ Must pre-exist or be bootstrapped |
| Valid password hash | ❌ Must pre-exist |
| DB write for user creation | ⚠️ Yes if bootstrapping |
| CSRF token acquisition | ✅ Works — exempt path sets cookie |
| Session cookie acquisition | ✅ Works — auth endpoint sets `access_token` |

### Key Finding: No Credential Bootstrap in Test Environment

`credential_file.py` (lines 21-48): `write_initial_credentials()` writes admin credentials to `{base_dir}/admin_initial_credentials.txt` with mode 0600. This is:
- A first-boot / password-reset mechanism for operators
- NOT a test environment bootstrap
- NOT called automatically in test context

`LocalAuthProvider.authenticate()` (local_provider.py:24-59): Validates against `users` table — no bootstrap user exists without explicit creation.

### SQLite User Repository

`SQLiteUserRepository.create_user()` — inserts into `users` table with hashed password. This is a DB write operation.

### Flow for Real Login Path (A)

```
1. SQLite: Create test user directly in DB (password hash via hash_password_async)
2. TestClient POST /api/v1/auth/login/local with test credentials
3. Response sets: Set-Cookie: csrf_token=<token>; access_token=<jwt>
4. TestClient cookie jar now has both cookies
5. TestClient subsequent POST: Cookie: csrf_token=<token>; access_token=<jwt> + Header: X-CSRF-Token: <token>
6. Both auth + CSRF pass → protected endpoint accessible
```

### Real Login Assessment

| Criterion | Score | Notes |
|-----------|-------|-------|
| production_fidelity | 10/10 | Uses real auth flow |
| safety | 5/10 | Temporary test user in DB |
| implementation_cost | 6/10 | Needs SQLite test user setup + session management |
| cleanup_complexity | 5/10 | Must delete test user after test |
| recommended_for_smoke | ❌ NO | Too heavy for no-tool smoke |
| recommended_for_final_acceptance | ✅ YES | Required for real auth flow validation |

**Constraint**: Requires DB write for test user creation. Under the constraint "不写 DB", Option A is **NOT available** for the current scope.

`★ Insight ─────────────────────────────────────`
**Real Login Path 的双重写入问题**：Option A 需要两步独立的写入操作：(1) 在 `users` 表中创建测试用户（需要 SQLAlchemy session），(2) 调用登录 endpoint 获取 CSRF cookie。如果第一步使用 `Memory` session（in-memory DB），测试结束后数据消失；如果使用同一个 test database session，则需要确保事务隔离。
`─────────────────────────────────────────────────`

---

## LANE 2 — TestClient Auth + CSRF Fixture Feasibility

### TestClient Cookie/Header Injection Capabilities

TestClient supports:
- `client.cookies.set(name, value)` — sets cookie in jar
- `client.cookies.get(name)` — reads from jar
- `client.get(url, cookies={...})` — override per-request
- `client.post(url, headers={...})` — custom headers
- TestClient merges cookies from jar with explicit `cookies=` dict

### Critical TestClient Limitation

TestClient does NOT automatically set `httponly=False` cookies as JavaScript-readable in browser contexts. It maintains a cookie jar internally that persists across requests.

### Can TestClient Inject Matching CSRF Token?

**Yes, trivially:**
```python
token = secrets.token_urlsafe(64)
client.cookies.set("csrf_token", token)
resp = client.post(
    "/api/threads/test-thread/runs",
    headers={"X-CSRF-Token": token},
    # ... other args
)
```

This is exactly how `test_auth_type_system.py:451` tests CSRF with matching tokens:
```python
client.cookies.set(CSRF_COOKIE_NAME, token)  # cookie
client.post(..., headers={CSRF_HEADER_NAME: token})  # header
```

**The pattern works for TestClient.** The only blocker is: the token must be known at test setup time — TestClient cannot get a token from a prior POST response and then use it in a subsequent request UNLESS using the same TestClient instance with cookie jar persistence.

### Auth Bypass in TestClient

The `_deerflow_test_bypass_auth` flag is checked at the **decorator level** (`authz.py:185, 278`), not in the middleware. It requires `request._deerflow_test_bypass_auth = True` to be set on the request object.

**TestClient cannot set custom request attributes directly** — but it CAN set cookies and headers. The auth bypass is orthogonal to cookie-based auth.

**Key finding**: For the internal auth path (`X-DeerFlow-Internal-Token` header), there's a cleaner mechanism:

```python
from app.gateway.internal_auth import create_internal_auth_headers
# This is already used in test_auth_middleware.py:177-188
headers = create_internal_auth_headers()  # {INTERNAL_AUTH_HEADER_NAME: _INTERNAL_AUTH_TOKEN}
resp = client.post("/api/threads/abc/runs/stream", headers=headers)
# → 200 OK (auth bypassed, but CSRF still checked)
```

The internal auth header **bypasses session cookie authentication** but **does NOT bypass CSRF middleware** — because CSRF middleware sits above the auth middleware in the ASGI stack and checks `should_check_csrf(request)` independently.

### Can TestClient Bypass Both Auth AND CSRF?

**No single mechanism bypasses both.** The options are:
1. Use internal auth header (bypasses auth) + manually set CSRF cookie/header matching pair (bypasses CSRF)
2. Use session cookie auth + CSRF cookie/header matching pair

Option 1 is **cleaner for testing** because internal auth requires no user bootstrapping.

### TestClient Fixture Pattern (Option C)

```python
import secrets
from fastapi.testclient import TestClient

@pytest.fixture
def auth_csrf_client():
    """TestClient with valid auth + CSRF for internal testing."""
    client = TestClient(app)
    # Internal auth header bypasses session cookie auth
    csrf_token = secrets.token_urlsafe(64)
    client.headers.update({
        INTERNAL_AUTH_HEADER_NAME: _INTERNAL_AUTH_TOKEN,
        "X-CSRF-Token": csrf_token,
    })
    client.cookies.set("csrf_token", csrf_token)
    return client
```

**Problem**: The `_INTERNAL_AUTH_TOKEN` is generated at module import time (`secrets.token_urlsafe(32)`) and stored as `_INTERNAL_AUTH_TOKEN` in `internal_auth.py`. The TestClient fixture would need to know this value, which is only accessible by importing `create_internal_auth_headers()`.

**This CAN work** — the fixture imports `create_internal_auth_headers()`, extracts the header value, generates a CSRF token, and sets both cookie and header on the TestClient instance.

`★ Insight ─────────────────────────────────────`
**TestClient fixture 的组合灵活性**：TestClient 实际上支持分层 auth 策略——可以用 internal header bypass session cookie auth，同时用手动设置的 cookie/header pair bypass CSRF。这两个机制是**正交的**，互不干扰。

关键在于：`authz.py:185` 的 `getattr(request, "_deerflow_test_bypass_auth", False)` 检查发生在 `require_auth` decorator 中，而不是 middleware。这意味着即使 middleware 被 `access_token` cookie bypass 了（通过 internal header），decorator 仍然会调用 `_authenticate()` unless `_deerflow_test_bypass_auth` is True。

但 internal auth header 的优先级更高（auth_middleware.py:93-94: `if is_valid_internal_auth_token(...) → internal_user = get_internal_user()`），所以实际上 internal header 在 middleware 层面已经完全 bypass 了 session cookie check。
`─────────────────────────────────────────────────`

### Option C Assessment

| Criterion | Score | Notes |
|-----------|-------|-------|
| production_fidelity | 8/10 | Uses real gateway endpoints; internal auth = production code path |
| safety | 5/10 | Uses internal auth which is production code; manual CSRF token is test infrastructure only |
| implementation_cost | 4/10 | Fixture function + token generation; no middleware changes |
| cleanup_complexity | 10/10 | No cleanup needed |
| recommended_for_smoke | ✅ YES | Fast, clean, no DB writes |
| recommended_for_final_acceptance | ❌ NO | Doesn't test real login flow |

---

## LANE 3 — Test-only CSRF Bypass Flag Feasibility

### Mechanism

The CSRF middleware has **no feature flag**. Adding one requires code change in two locations:

**Option B1: Global env var in csrf_middleware.py**
```python
# At top of dispatch()
import os
if os.environ.get("CSRF_ENABLED", "true").lower() != "true":
    return await call_next(request)
```

**Option B2: Per-request flag on app.state**
```python
# In app.py after add_middleware
if os.environ.get("CSRF_TEST_BYPASS", "").lower() == "true":
    app.state.csrf_bypass = True
# Then check in csrf_middleware dispatch
if getattr(request.app.state, "csrf_bypass", False):
    return await call_next(request)
```

### Safest Flag Design

```python
# csrf_middleware.py — guard at start of dispatch()
import os

async def dispatch(self, request: Request, call_next: Callable) -> Response:
    # Test-only bypass: only enable when explicitly set for testing
    if os.environ.get("DEERFLOW_TEST_CSRF_BYPASS", "").lower() == "true":
        return await call_next(request)
    # ... rest of existing dispatch logic
```

**Properties:**
- Name `DEERFLOW_TEST_CSRF_BYPASS` makes it obviously test-only
- Default unset/absent → CSRF always active (safe for production)
- No code path changes needed for bypass logic itself

### Bypass Flag Assessment

| Criterion | Score | Notes |
|-----------|-------|-------|
| production_fidelity | 5/10 | Skips CSRF entirely; tests a different code path |
| safety | 4/10 | Flag must be test-only; production must not set it |
| implementation_cost | 3/10 | Small env var + guard in csrf_middleware.py |
| cleanup_complexity | 10/10 | No cleanup needed |
| recommended_for_smoke | ❌ CONDITIONAL | Only if Option C is not available |
| recommended_for_final_acceptance | ❌ NO | Skips critical security validation |

**Constraint**: Requires code change (`csrf_middleware.py`). Under the constraint "不修改代码", Option B is **NOT available** for the current scope unless the code change is pre-authorized as a test infrastructure change.

---

## LANE 4 — DeerFlowClient CSRF Support Feasibility

### Production Requirement

| Environment | CSRF Needed? | Reason |
|-------------|---------------|-------|
| Browser → Gateway | ✅ YES | Browser sends cookies automatically; CSRF protects against cross-site POST |
| DeerFlowClient (Node.js) | ❌ NO | Node.js fetch client does NOT automatically send cookies; no cookie jar = no CSRF attack surface |
| Direct API calls (curl) | ❌ NO | No cookie automatically sent; CSRF requires attacker to have cookie access |

**CSRF is a browser-only threat.** DeerFlowClient runs in Node.js (server-side), not a browser. It does NOT maintain a cookie jar. The Double Submit Cookie pattern requires the attacker to somehow get the browser to send the cookie — impossible for a server-side client.

### Test Environment Requirement

DeerFlowClient in test would need the same CSRF handling as in production:
- No cookie jar → no CSRF vulnerability → no CSRF header needed

If DeerFlowClient is used in tests that call the gateway, it would need CSRF support **only if** the tests use browser-like clients that maintain cookies.

### Recommendation

**Do NOT add CSRF handling to DeerFlowClient.** It's a server-side client with no cookie jar. The Double Submit Cookie pattern is unnecessary overhead.

---

## LANE 5 — Strategy Comparison

### Summary Comparison

| Criterion | Option A: Real Login | Option B: CSRF Bypass Flag | Option C: TestClient Fixture |
|-----------|---------------------|---------------------------|------------------------------|
| production_fidelity | 10/10 | 5/10 | 8/10 |
| safety | 5/10 | 4/10 | 5/10 |
| implementation_cost | 6/10 | 3/10 | 4/10 |
| test_speed | 7/10 | 10/10 | 10/10 |
| cleanup_complexity | 5/10 | 10/10 | 10/10 |
| future_acceptance_value | 10/10 | 3/10 | 7/10 |
| risk_security_regression | LOW | MEDIUM | LOW |
| requires_code_change | NO | YES | NO |
| requires_db_write | YES | NO | NO |
| recommended_for_smoke | ❌ NO | ❌ NO | ✅ YES |
| recommended_for_final_acceptance | ✅ YES | ❌ NO | ❌ NO |

### Default Decision

**Option C for HTTP smoke (R135).**

Option A (real login) is the right choice for full end-to-end auth flow acceptance tests, but requires DB writes that violate current constraints. It should be the goal of a later acceptance test phase.

Option B (CSRF bypass flag) is safe and simple, but requires a code change that hasn't been authorized yet.

**Option C** uses existing production code paths without modification:
- Internal auth header bypasses session cookie auth (production code path)
- Manual CSRF token injection bypasses CSRF (using TestClient cookie API)

The combination is:
- `headers=create_internal_auth_headers()` → bypasses `access_token` session cookie requirement
- `cookies.set("csrf_token", token)` + `headers["X-CSRF-Token"] = token` → passes CSRF check

`★ Insight ─────────────────────────────────────`
**为何 Option C 是三种中最实用的**：它利用了两个现有机制的组合，而不是引入新机制：

1. `create_internal_auth_headers()` 是已有的生产代码（internal_auth.py），用于进程内认证旁路
2. TestClient 的 `cookies.set()` + `headers=` 覆盖是标准 TestClient API，用于手动设置 cookie 和 header

两者结合 = auth bypass + CSRF bypass，无新代码，无 DB 写入，无配置变更。这是"用现有机制组合"而非"添加新机制"的典型例子。
`─────────────────────────────────────────────────`

---

## LANE 6 — R135 Entry Contract

### R135 Goals

```
1. Implement Auth + CSRF test harness (Option C) for gateway HTTP smoke
2. Smoke test POST /api/threads (create thread)
3. Smoke test GET /api/threads/{id} (get thread)
4. Smoke test POST /api/threads/{id}/runs (create run on existing thread)
5. Smoke test GET /api/threads/{id}/runs (list runs)
```

### R135 Entry Conditions

Before entering R135, the following must be true:
- [ ] Option C fixture approach selected (internal auth header + manual CSRF token)
- [ ] Allowed modification files explicitly listed (test fixtures only)
- [ ] Forbidden modification files explicitly listed (no production code changes)
- [ ] Verification criteria defined (HTTP 200 responses, correct schemas)
- [ ] Rollback plan defined (remove fixture, no production impact)

### R135 Allowed Actions

```
- Create test fixture files (backend/tests/gateway/)
- Use create_internal_auth_headers() from existing production code
- Use TestClient cookie/header injection API
- Generate CSRF token via secrets.token_urlsafe(64)
- Execute smoke tests via TestClient
```

### R135 Forbidden Actions

```
- Modify production CSRF behavior (no bypass flags)
- Modify production auth behavior
- Write to production DB
- Print secrets or credentials
- Start production gateway server
- Call model API
```

---

## LANE 7 — Patch Authorization Package

### Option C: No Code Changes Required

Option C uses only existing mechanisms:
1. `create_internal_auth_headers()` — already in production (`internal_auth.py`)
2. TestClient `cookies.set()` + `headers=` — standard TestClient API
3. `secrets.token_urlsafe(64)` — Python standard library

**No production code modification needed.**
**No patch authorization required.**

### If Option B Were Needed (CSRF bypass flag)

Should Option C prove insufficient, a CSRF bypass flag would require:

| File | Change | Lines |
|------|--------|-------|
| `csrf_middleware.py` | Add env var guard at start of `dispatch()` | ~4 lines |
| No other files needed | — | — |

Flag design: `DEERFLOW_TEST_CSRF_BYPASS=true` — test-only naming, default absent.

**This is NOT the recommended path for R135** — Option C is available without code changes.

---

## LANE 8 — Unknown Registry Update

### New or Updated Unknowns

| Unknown ID | Name | Type | Status Change | Notes |
|------------|------|------|---------------|-------|
| U-001 | Auth + CSRF Test Channel | Previously "feasible" | ✅ RESOLVED | Option C available without code changes |
| U-011 | TestClient greenlet ImportError | Environment | NEW | May affect Option C execution in some environments |
| U-012 | require_existing thread creation order | Auth constraint | ✅ MAPPED | Must POST /api/threads before POST /api/threads/{id}/runs |

### Deferred Unknowns (Not Phase 1 Scope)

| Unknown ID | Name | Notes |
|------------|------|-------|
| U-002 | RunStore / RunEventStore behavior | Phase 3 |
| U-003 | Tool event observability | Phase 4 |
| U-004 | Path A executor availability | Phase 5 |
| U-005 | Tavily MCP 405 | Phase 6 |
| U-006 | Exa/Lark credential provisioning | Phase 6 |

---

## LANE 9 — Report Generation

### Files Generated

| File | Status |
|------|--------|
| `migration_reports/recovery/R134D_...md` | Written |
| `migration_reports/recovery/R134D_...json` | Written |

---

## Final Report

```
R134D_CSRF_TEST_HARNESS_PLAN_AND_AUTH_BYPASS_STRATEGY_DONE

status=passed
pressure_assessment_completed=true
recommended_pressure=XXL++
real_login_path={
  feasible: true,
  requires_test_user: true,
  requires_tmp_sqlite: false,
  writes_db: true (user creation in users table),
  obtains_csrf_cookie: true,
  obtains_access_cookie: true,
  risks: ["DB write for test user creation violates current constraints", "Test user must be cleaned up after test"],
  recommended_for_smoke: false,
  recommended_for_final_acceptance: true,
  blocked_by_constraints: true
}
testclient_fixture_option={
  feasible: true,
  requires_code_change: false,
  code_change_scope: none,
  can_inject_cookie_header: true,
  can_bypass_auth_without_bypassing_csrf: false,
  can_bypass_csrf_without_bypassing_auth: true,
  combined_both_bypass: true,
  mechanism: "Internal auth header (create_internal_auth_headers) + manual csrf_token cookie/header injection",
  risks: ["Internal auth is production code path (safe to use)", "CSRF token is manually generated (not from login flow)"],
  recommended_for_smoke: true,
  recommended_for_final_acceptance: false,
  available_in_current_constraints: true
}
test_only_bypass_design={
  feasible: true,
  requires_code_change: true,
  proposed_flag_name: "DEERFLOW_TEST_CSRF_BYPASS",
  default_false: true,
  production_risk: LOW,
  guard_conditions: ["env var must be test-only naming", "default must be absent/false", "only bypass CSRF, not auth"],
  recommended_for_smoke: false,
  recommended_for_final_acceptance: false,
  blocked_by_constraints: true (code change not authorized)
}
deerflow_client_csrf_support={
  needed_for_production: false,
  needed_for_test: false,
  reason: "DeerFlowClient is Node.js server-side; no browser cookie jar = no CSRF attack surface",
  recommended_design: "Do NOT add CSRF handling to DeerFlowClient"
}
strategy_comparison=[
  {
    option: "A_real_login",
    production_fidelity: 10,
    safety: 5,
    implementation_cost: 6,
    test_speed: 7,
    cleanup_complexity: 5,
    future_acceptance_value: 10,
    risk_security_regression: "LOW",
    requires_code_change: false,
    requires_db_write: true,
    recommended_for_smoke: false,
    recommended_for_final_acceptance: true,
    blocked_by_constraints: true
  },
  {
    option: "B_csrf_bypass_flag",
    production_fidelity: 5,
    safety: 4,
    implementation_cost: 3,
    test_speed: 10,
    cleanup_complexity: 10,
    future_acceptance_value: 3,
    risk_security_regression: "MEDIUM",
    requires_code_change: true,
    requires_db_write: false,
    recommended_for_smoke: false,
    recommended_for_final_acceptance: false,
    blocked_by_constraints: true
  },
  {
    option: "C_testclient_fixture",
    production_fidelity: 8,
    safety: 5,
    implementation_cost: 4,
    test_speed: 10,
    cleanup_complexity: 10,
    future_acceptance_value: 7,
    risk_security_regression: "LOW",
    requires_code_change: false,
    requires_db_write: false,
    recommended_for_smoke: true,
    recommended_for_final_acceptance: false,
    blocked_by_constraints: false
  }
]
recommended_smoke_strategy=option_C_testclient_fixture
recommended_final_acceptance_strategy=option_A_real_login
r135_entry_conditions=[
  "Option C fixture approach selected",
  "Allowed modification files explicitly listed (test fixtures only)",
  "Forbidden modification files explicitly listed (no production code changes)",
  "Verification criteria defined (HTTP 200 responses, correct schemas)",
  "Rollback plan defined"
]
r135_allowed_actions=[
  "Create test fixture files (backend/tests/gateway/)",
  "Use create_internal_auth_headers() from existing production code",
  "Use TestClient cookie/header injection API",
  "Generate CSRF token via secrets.token_urlsafe(64)",
  "Execute smoke tests via TestClient"
]
r135_forbidden_actions=[
  "Modify production CSRF behavior",
  "Modify production auth behavior",
  "Write to production DB",
  "Print secrets or credentials",
  "Start production gateway server",
  "Call model API"
]
patch_authorization_required=false
patch_authorization_package={
  files_allowed: [],
  files_forbidden: [],
  note: "Option C requires no code changes; uses existing production mechanisms only"
}
unknown_registry=[
  {id: "U-001", status: "RESOLVED", note: "Option C available without code changes"},
  {id: "U-011", status: "NEW", note: "TestClient greenlet ImportError may affect execution"},
  {id: "U-012", status: "MAPPED", note: "Must POST /api/threads before POST /api/threads/{id}/runs"}
]
repair_allowed=false
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
next_prompt_needed=R135_AUTH_CSRF_TEST_HARNESS_IMPLEMENTATION_AUTHORIZATION
```

---

*Generated by Claude Code — R134D (CSRF Test Harness Plan and Auth Bypass Strategy)*
