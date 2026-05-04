cmended_pressure | XXL++ |
| reason | Read-only CSRF and DeerFlowClient HTTP path cross-validation; no runtime execution. |

---

## LANE 1 — CSRF Middleware Mechanism Mapping

### Mechanism Details

| Property | Value |
|----------|-------|
| Pattern | **Double Submit Cookie** |
| Cookie name | `csrf_token` |
| Header name | `X-CSRF-Token` |
| Token generation | `secrets.token_urlsafe(64)` — 64 bytes, URL-safe base64 |
| Cookie attributes | `httponly=False` (JS-readable), `secure` (HTTPS only), `samesite=strict` |
| Validation | `secrets.compare_digest(cookie, header)` — constant-time compare |
| CSRF check scope | Only for `POST, PUT, DELETE, PATCH` methods |
| GET/HEAD/OPTIONS/TRACE | **Exempt** per RFC 7231 |
| CSRF middleware enabled | **Unconditional** — no feature flag exists |

### Exempt Paths

`_AUTH_EXEMPT_PATHS` (set in csrf_middleware.py:46):
```
/api/v1/auth/login/local     ← Sets csrf_token cookie on POST
/api/v1/auth/logout          ← Sets csrf_token cookie on POST
/api/v1/auth/register         ← Sets csrf_token cookie on POST
/api/v1/auth/initialize       ← Sets csrf_token cookie on POST
/api/v1/auth/me              ← Exempt from CSRF check (GET path)
/health                      ← Exempt (public)
```

### Token Flow

```
1. Client POST /api/v1/auth/login/local (no CSRF needed)
2. Server validates credentials
3. Server generates: csrf_token = secrets.token_urlsafe(64)
4. Server sets: Set-Cookie: csrf_token=<token>; httponly=False; secure; samesite=strict
5. Subsequent state-changing requests: Cookie: csrf_token=<token> + Header: X-CSRF-Token: <token>
6. Server compares: secrets.compare_digest(cookie, header) — must match exactly
```

### Key Finding: No Token Acquisition Endpoint

There is **no `/csrf-token` endpoint** in the gateway. The only way to acquire a valid CSRF token is:
1. POST to one of the 4 `_AUTH_EXEMPT_PATHS` auth endpoints
2. Extract `csrf_token` from `Set-Cookie` response header
3. Use that token value in subsequent requests via cookie + `X-CSRF-Token` header

`★ Insight ─────────────────────────────────────`
**CSRF 双提交Cookie模式（Double Submit Cookie）** 的安全前提：攻击者无法读取目标域的 cookie（因为 `samesite=strict` 防止跨站请求携带 cookie），因此即使攻击者诱导用户向目标域发起请求，也无法在请求中包含正确的 `csrf_token`。服务器通过比对 cookie 中的 token 和 header 中的 token 来验证请求来源。但这也意味着：没有先调用 auth endpoint 获取 token 的客户端，无法构造合法的 state-changing 请求。
`─────────────────────────────────────────────────`

---

## LANE 2 — TestClient CSRF Feasibility

### Assessment

| Question | Answer |
|----------|--------|
| Can TestClient GET /health? | ✅ YES — GET is exempt from CSRF |
| Is there a `/csrf-token` endpoint? | ❌ NO — no endpoint to acquire token |
| Can token be manually constructed? | ❌ NO — requires `secrets.token_urlsafe(64)`, cryptographically random |
| Is there a CSRF bypass feature flag? | ❌ NO — CSRF middleware is unconditional at app.py:306 |
| Does `_deerflow_test_bypass_auth` bypass CSRF? | ❌ NO — only bypasses auth (authz.py:185, 278), not CSRF dispatch |
| Can POST /api/v1/auth/login/local set cookie in TestClient? | ⚠️ UNKNOWN — requires valid credentials |
| Can TestClient follow cookie + send header? | ✅ YES — TestClient supports cookie handling and custom headers |

### Path Analysis: Can TestClient Acquire a Valid CSRF Token?

**Path A: POST /api/v1/auth/login/local**
```
1. TestClient POST /api/v1/auth/login/local with credentials
2. Server validates credentials, sets Set-Cookie: csrf_token=<token>
3. TestClient receives cookie automatically (TestClient cookie jar)
4. TestClient subsequent POST: Cookie: csrf_token=<token>; X-CSRF-Token: <token>
```

**Problem**: This requires valid credentials. In the test environment:
- No valid credentials are bootstrapped
- Auth is disabled by default (`AUTH_MIDDLEWARE_ENABLED=false`, `AUTH_ROUTES_ENABLED=false`)
- The `_deerflow_test_bypass_auth` flag bypasses `require_auth` decorator but NOT the CSRF middleware itself

**Path B: Use `_deerflow_test_bypass_auth` to bypass auth but not CSRF**
- Even with `_deerflow_test_bypass_auth=True`, CSRF middleware still checks cookie+header
- Without a valid `csrf_token` cookie, CSRF fails with 403

**Conclusion**: TestClient cannot acquire a valid CSRF token without either:
1. Valid credentials for an auth endpoint that returns a token cookie
2. A code change to add a CSRF token acquisition endpoint
3. A code change to add a CSRF bypass feature flag

`testclient_csrf_feasible: false`
`csrf_token_acquisition_path: none_without_credentials_or_code_change`

---

## LANE 3 — Thread / Run Route Schema Mapping

### Route Summary

| Method | Path | Handler | Auth | CSRF | require_existing |
|--------|------|---------|------|------|-----------------|
| POST | `/api/threads` | `create_thread()` | ✅ | ❌ exempt (POST not in exempt list but no decorator) | ❌ N/A (creates) |
| GET | `/api/threads/{thread_id}` | `get_thread()` | ✅ | ❌ GET-exempt | ❌ N/A (reads) |
| POST | `/api/threads/{thread_id}/runs` | `create_run()` | ✅ | ❌ POST checked | ✅ `require_existing=True` |
| POST | `/api/threads/{thread_id}/runs/stream` | `stream_run()` | ✅ | ❌ POST checked | ✅ `require_existing=True` |
| POST | `/api/threads/{thread_id}/runs/wait` | `wait_run()` | ✅ | ❌ POST checked | ✅ `require_existing=True` |
| GET | `/api/threads/{thread_id}/runs` | `list_runs()` | ✅ | ❌ GET-exempt | ❌ N/A (reads) |

### POST /api/threads — create_thread()

**Decorator**: None (no `@require_permission` decorator on `create_thread()` at threads.py:224)

```python
# Schema
ThreadCreateRequest:
  thread_id: str | None          # Optional, auto-generated if None
  assistant_id: str | None        # Optional
  metadata: dict[str, Any]        # Optional, stripped of owner_id/user_id

# Behavior
- Writes thread_meta record to store
- Creates empty checkpoint
- Idempotent: returns existing record if thread_id already exists
```

**Important**: `create_thread()` has NO `@require_permission` decorator — it relies on the global AuthMiddleware for session cookie check. But it is NOT in the CSRF exempt list, so POST /api/threads SHOULD require CSRF.

Wait — re-reading csrf_middleware.py: `should_check_csrf()` returns True only for `POST, PUT, DELETE, PATCH` methods. The exempt paths are for auth endpoints. `/api/threads` is not in the exempt list, so CSRF IS checked for POST /api/threads.

But `create_thread()` itself has no decorator. The CSRF check is at the middleware level.

### POST /api/threads/{thread_id}/runs — create_run()

```python
# Decorator: @require_permission("runs", "create", owner_check=True, require_existing=True)

# Schema (RunCreateRequest)
input: dict[str, Any] | None      # e.g., {"messages": [...]}
config: dict[str, Any] | None     # RunnableConfig overrides
metadata: dict[str, Any] | None
context: dict[str, Any] | None    # DeerFlow context overrides
assistant_id: str | None
command: dict[str, Any] | None
webhook: str | None
checkpoint_id: str | None
checkpoint: dict[str, Any] | None
interrupt_before: list[str] | None
interrupt_after: list[str] | None
stream_mode: list[str] | str | None
stream_subgraphs: bool = False
stream_resumable: bool | None
on_disconnect: "cancel" | "continue" = "cancel"
on_completion: "delete" | "keep" = "keep"
multitask_strategy: "reject" | "rollback" | "interrupt" | "enqueue" = "reject"
after_seconds: float | None
if_not_exists: "reject" | "create" = "create"   # ← Thread creation policy
feedback_keys: list[str] | None
```

**Critical**: `require_existing=True` means the thread must already exist in `threads_meta` table. But `RunCreateRequest.if_not_exists: "create"` (default) means... wait, let me re-read.

Actually looking at `create_run()` at thread_runs.py:97:
- `@require_permission("runs", "create", owner_check=True, require_existing=True)` — the decorator has `require_existing=True`
- This is NOT the `if_not_exists` field in RunCreateRequest — that field controls behavior INSIDE `start_run()`, not the decorator

The `require_existing` parameter on the decorator means the decorator checks if the thread exists BEFORE calling the handler. The `if_not_exists` field in RunCreateRequest is passed to `start_run()` and controls whether a new thread is created if it doesn't exist — but since `require_existing=True` on the decorator, this code path is never hit because the decorator rejects first.

### GET /api/threads/{threadId} vs GET /api/threads/{threadId}/runs/{runId}

**DeerFlowClient uses**:
- `GET /api/threads/{threadId}` — fetches thread status (busy/idle/error)
- **NOT** `GET /api/threads/{threadId}/runs/{runId}`

`thread_id` and `run_id` are different resources. The thread status endpoint polls the thread, not individual runs.

---

## LANE 4 — DeerFlowClient Request Mapping

### DeerFlowClient Sequence (from deerflow_client.ts)

```
1. createThread()
   POST /api/threads
   Body: {}
   Response: { thread_id: string, status, created_at, updated_at }

2. runTask(threadId, dagPlan, meta)
   POST /api/threads/{threadId}/runs
   Body: {
     input: { messages: [{ role: "user", "content": dagPlan.rootTask }] },
     metadata: { session_id, request_id, priority, dag_plan: dagPlan },
     config: { recursion_limit: 100 }
   }
   Response: { run_id, status, thread_id, created_at }

3. getThreadStatus(threadId)
   GET /api/threads/{threadId}
   Response: { thread_id, status, created_at, updated_at }
   Polling: interval=2000ms, timeout=300000ms

4. deleteThread(threadId) — on completion or timeout
   DELETE /api/threads/{threadId}
```

### Gateway vs TypeScript Schema Alignment

| Field | DeerFlowClient sends | Gateway expects | Match? |
|-------|---------------------|-----------------|--------|
| `input` | `{messages: [...]}` | `input: dict | None` (directly) | ⚠️ **Mismatch** — Gateway reads `input["messages"]`, expects nested structure |
| `metadata` | top-level | `RunCreateRequest.metadata` | ✅ Match |
| `config.recursion_limit` | nested in `config` | `RunCreateRequest.config` | ✅ Match |
| `assistant_id` | not sent | `RunCreateRequest.assistant_id` | ✅ Defaults to "lead_agent" |
| `if_not_exists` | not sent | default `"create"` | ✅ Default works |

### Schema Mismatch: input.messages Structure

**DeerFlowClient** sends:
```json
{
  "input": {
    "messages": [
      { "role": "user", "content": "task description" }
    ]
  }
}
```

**Gateway normalize_input()** reads:
```python
messages = raw_input.get("messages")  # ← expects "messages" at top level of input
```

This means DeerFlowClient's `input.messages` structure is **correct** — it sends `input.messages` which `normalize_input()` finds at `raw_input.get("messages")`.

### CSRF Non-Compliance

DeerFlowClient **never sets `X-CSRF-Token` header** and does **not handle the `csrf_token` cookie**. This means any POST from DeerFlowClient to the gateway would fail CSRF validation.

However, DeerFlowClient is a **Node.js server-side client** — it does NOT maintain a browser cookie jar. CSRF is a browser-only threat. In production, the browser would set the cookie and header automatically (via JS), but DeerFlowClient as a server-side client does not need CSRF protection.

### Key Correction from R134B

R134B confirmed: DeerFlowClient uses `POST /api/threads/{threadId}/runs` (synchronous), **NOT** `POST /api/threads/{threadId}/runs/stream` (SSE). These are two distinct endpoints sharing the same `start_run()` backend.

`★ Insight ─────────────────────────────────────`
**DeerFlowClient 与 CSRF 的关系**：DeerFlowClient 是 Node.js 服务器端客户端，它不维护浏览器 cookie jar，因此传统 CSRF 攻击对其不适用。但当 DeerFlowClient 通过 HTTP POST 调用 Gateway 时，Gateway 的 CSRF middleware 会检查 cookie + header pair，而 DeerFlowClient 从不设置这些。这意味着在测试环境中（模拟浏览器行为时），DeerFlowClient 会触发 CSRF 403。
`─────────────────────────────────────────────────`

---

## LANE 5 — No-Model HTTP Smoke Feasibility

### Candidate: Schema Validation via OPTIONS or 405

| Candidate | Feasibility | Notes |
|-----------|-------------|-------|
| OPTIONS /api/threads | ❌ Not supported | No CORS preflight handler defined |
| GET /api/threads/{id} | ✅ Possible | Returns thread state (busy/idle/error); exempt from CSRF; requires auth bypass |
| GET /api/threads/{id}/runs | ✅ Possible | Returns run list; exempt from CSRF; requires auth bypass |
| POST /api/threads (create thread) | ⚠️ Blocked | CSRF checked (POST not exempt); requires valid cookie+header pair AND auth |
| POST /api/threads/{id}/runs | ⚠️ Blocked | CSRF checked; requires valid cookie+header pair AND auth AND require_existing |

### Why GET Works But POST Doesn't

CSRF middleware `should_check_csrf()` exempts GET/HEAD/OPTIONS/TRACE methods. But AuthMiddleware still requires session cookie OR internal auth token for GET /api/threads/{id}.

The global AuthMiddleware (app.py:303) checks for `access_token` cookie. No `access_token` → 401 NOT_AUTHENTICATED.

### `require_permission` Without Auth Context

Both `require_auth` and `require_permission` decorators check `request.state.auth`. Without proper auth context:
- `request.state.auth` is `None` → triggers `_authenticate()` which fails → 401

The `_deerflow_test_bypass_auth` flag helps for direct handler calls, but not for TestClient routing.

### Conclusion: No-Model HTTP Smoke

| Scenario | Status | Blocker |
|----------|--------|--------|
| GET thread status (no model) | ⚠️ BLOCKED | Auth (no `_deerflow_test_bypass_auth` in TestClient request) |
| POST create thread (no model) | ⚠️ BLOCKED | Auth + CSRF — requires valid credentials + token acquisition flow |
| POST create run (no model) | ⚠️ BLOCKED | Auth + CSRF + require_existing thread |
| Import gateway app only | ✅ POSSIBLE | `py_compile` pass |

`no_model_http_smoke_possible: false`

Reason: Auth middleware blocks all non-public GET endpoints without a valid session cookie. No credential-free auth path exists for GET /api/threads/{id}.

---

## LANE 6 — One-Model-Call Gateway Smoke Feasibility

### Requirements for One-Model-Call Smoke

| Requirement | Status | Notes |
|-------------|--------|-------|
| Create thread via POST /api/threads | ❌ BLOCKED | Auth + CSRF — requires valid credentials |
| Create run via POST /api/threads/{id}/runs | ❌ BLOCKED | Auth + CSRF + require_existing thread |
| Acquire CSRF token | ❌ IMPOSSIBLE | No endpoint; requires auth credentials |
| Bypass auth for TestClient | ❌ NO | No mechanism to inject `_deerflow_test_bypass_auth` via TestClient |
| Bypass CSRF middleware | ❌ NO | No feature flag |

### Preconditions That Would Enable

1. **CSRF bypass feature flag** added to `csrf_middleware.py` or `app.py`
2. **Auth bypass for TestClient** via TestClient header or fixture
3. **Valid test credentials** to auth endpoint that returns CSRF cookie
4. **Direct handler call** bypassing HTTP stack — but this isn't a "gateway smoke test"

### Conclusion

`one_model_gateway_smoke_possible: false`
`required_preconditions: [CSRF bypass flag, or valid test credentials, or auth bypass for TestClient]`
`risks: [No credential-free auth path exists for POST; CSRF blocks all state-changing requests without token]`

---

## LANE 7 — Updated Blocker Classification

### Blocker: CSRF Middleware

| Property | Value |
|----------|-------|
| Type | **Config Gap** (not a bug — middleware is correctly implemented) |
| Is it a test artifact? | **No** — CSRF is legitimate protection; only blocks TestClient |
| Is there a bypass? | ❌ No feature flag, no test harness |
| Is the mechanism correct? | ✅ Yes — Double Submit Cookie pattern properly implemented |
| Can TestClient work around? | ❌ No — requires credentials + CSRF cookie acquisition flow |

### Blocker: Auth Middleware

| Property | Value |
|----------|-------|
| Type | **Config Gap** |
| Public paths | `/health`, `/docs`, `/redoc`, `/openapi.json`, `/api/v1/auth/*` |
| Blocked paths | All `/api/threads/*` and `/api/threads/{id}/runs/*` without session cookie |
| TestClient bypass | `_deerflow_test_bypass_auth` exists but NOT accessible via TestClient |
| Credential bootstrap | No bootstrap credentials in test environment |

### True Gateway HTTP Path Blockers

| Order | Blocker | Type | Resolution |
|-------|---------|------|------------|
| 1 | Auth middleware session cookie | Config Gap | Need valid credentials OR test auth bypass |
| 2 | CSRF middleware token | Config Gap | Need token acquisition flow |
| 3 | `require_existing=True` | Auth constraint | Thread must exist before run can be created |
| 4 | Model API credentials | BP-02 deferred | EXA_API_KEY, LARK_APP_ID, LARK_APP_SECRET MISSING |

### Default Decision

**No legitimate path for TestClient gateway smoke without code changes.**

Decision: `R134D_CSRF_TEST_HARNESS_PLAN_AND_AUTH_BYPASS_STRATEGY`

The blockers are NOT bugs — they are correct security implementations that require explicit test infrastructure changes to bypass in a test context.

`★ Insight ─────────────────────────────────────`
**为什么 `_deerflow_test_bypass_auth` 不能 bypass CSRF**：这是一个常见的混淆。`_deerflow_test_bypass_auth` 是在 `authz.py` 的 `require_auth` 和 `require_permission` decorators 内部检查的标志（在 authz.py:185 和 :278），它只告诉 decorators 跳过认证检查。但 CSRF middleware 是一个独立的 ASGI middleware，运行在 decorators 之前，检查 `should_check_csrf(request)` 并验证 cookie/header pair。所以即使 `_deerflow_test_bypass_auth=True`，CSRF 检查仍然会执行并失败。
`─────────────────────────────────────────────────`

---

## LANE 8 — Report Generation

### Files Generated

| File | Status |
|------|--------|
| `migration_reports/recovery/R134C_...md` | Written |
| `migration_reports/recovery/R134C_...json` | Written |

---

## Final Report

```
R134C_GATEWAY_HTTP_PATH_CSRF_AND_DEERFLOWCLIENT_SMOKE_CROSS_VALIDATION_DONE

status=passed
pressure_assessment_completed=true
recommended_pressure=XXL++
csrf_mechanism={
  pattern: "Double Submit Cookie",
  cookie_name: "csrf_token",
  header_name: "X-CSRF-Token",
  token_source: "secrets.token_urlsafe(64)",
  exempt_paths: ["/api/v1/auth/login/local", "/api/v1/auth/logout", "/api/v1/auth/register", "/api/v1/auth/initialize"],
  safe_methods: ["GET", "HEAD", "OPTIONS", "TRACE"],
  unsafe_methods: ["POST", "PUT", "DELETE", "PATCH"],
  test_bypass_exists: false,
  feature_flag_exists: false
}
testclient_csrf_feasible=false
csrf_token_acquisition_path=none_without_credentials_or_code_change
requires_code_change_for_csrf=true
thread_run_http_sequence={
  create_thread: "POST /api/threads {thread_id, assistant_id, metadata}",
  create_run: "POST /api/threads/{threadId}/runs {input, metadata, config, if_not_exists: create}",
  get_thread_status: "GET /api/threads/{threadId}",
  list_runs: "GET /api/threads/{threadId}/runs",
  require_existing_constraints: ["create_run requires threads_meta row (require_existing=True)", "create_thread idempotent but creates thread_meta row"]
}
deerflow_client_sequence=[
  "createThread() → POST /api/threads {} → thread_id",
  "runTask() → POST /api/threads/{threadId}/runs {input: {messages: [...]}, metadata: {...}, config: {...}}",
  "getThreadStatus() → GET /api/threads/{threadId} (NOT /runs/{runId})",
  "deleteThread() → DELETE /api/threads/{threadId}"
]
deerflow_client_matches_gateway_schema=true
schema_mismatches=[]
deerflow_client_csrf_compliant=false
csrf_classification=config_gap_not_test_artifact
gateway_http_path_status=blocked_by_csrf_and_auth
no_model_http_smoke_possible=false
one_model_gateway_smoke_possible=false
required_preconditions=["CSRF bypass feature flag", "Valid test credentials for auth endpoint", "Auth bypass for TestClient (_deerflow_test_bypass_auth not accessible)"]
updated_blocker_order=[
  "1. Auth session cookie — requires valid credentials or test auth bypass",
  "2. CSRF token — requires credential + POST to auth endpoint + cookie extraction",
  "3. require_existing — threads_meta row must exist before create_run",
  "4. BP-02 MCP credentials MISSING"
]
csrf_is_test_artifact=false
csrf_is_correctly_implemented=true
recommended_next_phase=R134D_CSRF_TEST_HARNESS_PLAN_AND_AUTH_BYPASS_STRATEGY
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
next_prompt_needed=R134D_CSRF_TEST_HARNESS_PLAN_AND_AUTH_BYPASS_STRATEGY
```

---

*Generated by Claude Code — R134C (Gateway HTTP Path CSRF and DeerFlowClient Smoke Cross-Validation)*
