# R134B — Main Chain Entrypoint and Branch Boundary Cross-Validation

**Phase:** R134B — Main Chain Entrypoint and Branch Boundary Cross-Validation
**Generated:** 2026-04-30
**Status:** COMPLETED
**Preceded by:** R134A
**Proceeding to:** R134C

---

## LANE 0 — Pressure Assessment

| Item | Value |
|------|-------|
| previous_phase | R134A |
| previous_status | passed |
| current_recommended_pressure | XXL++ |
| reason | Read-only cross-validation; map TypeScript M01/M04/M11 chains, classify main vs branch, revalidate blocker taxonomy, output R134C proposal. No code changes. |

---

## LANE 1 — TypeScript Main Entry Mapping

### Orchestrator Entry Chain

```
orchestrator.execute()
  └── handleOrchestration()           [m01/orchestrator.ts:168]
        └── deerflowEnabled check     [this.config.deerflowEnabled]
        └── handleDeerFlowExecution()[m01/orchestrator.ts:199]
              ├── DeerFlowClient.healthCheck()
              ├── DeerFlowClient.createThread()
              │     └── POST /api/threads           ← non-streaming, auth-protected
              ├── DeerFlowClient.executeUntilComplete()
              │     ├── runTask()
              │     │     └── POST /api/threads/{threadId}/runs  ← SYNCHRONOUS, NOT /stream
              │     └── getThreadStatus() polling
              └── timeout → handleLocalExecution() fallback
```

**Key endpoint correction from R134B investigation:**
- DeerFlowClient uses `POST /api/threads/{threadId}/runs` (synchronous, waits for completion) — NOT `POST .../runs/stream` (SSE streaming)
- `/stream` endpoint exists in `thread_runs.py:103` as `stream_run()` but is NOT called by the DeerFlowClient production path
- These are two DISTINCT endpoint behaviors

### Local Execution Path (Path A)

```
orchestrator.execute()
  └── handleOrchestration()
        └── handleLocalExecution()
              └── M04Coordinator.execute()
                    └── executorAdapter (m11/mod.ts)
                          └── executeWithAutoSelect()
                                └── Claude Code CLI (subprocess)
```

---

## LANE 2 — Path A (Local Execution) Boundary

### M04 Coordinator

| Property | Value |
|----------|-------|
| File | `backend/src/domain/m04/coordinator.ts` |
| Routes | SEARCH, TASK, WORKFLOW, CLAUDE_CODE, GSTACK_SKILL, LARKSUITE, VISUAL_WEB, DESKTOP_APP |
| Executor | `executorAdapter` from `m11/mod.ts` |

### M11 Module

| Export | Purpose |
|--------|---------|
| `executorAdapter` | Executor selection + health gate |
| `executeWithAutoSelect` | Auto-select executor |
| `checkExecutorHealth` | Health check |
| `larkCLIAdapter` | Lark CLI adapter |
| `DesktopToolSelector` | Desktop tool selection |
| `VisualToolSelector` | Visual tool selection |

**M11 health gate:** `checkExecutorHealth()` / `executorReadinessGate()`

---

## LANE 3 — Path B (DeerFlow) Boundary

### DeerFlowClient Chain

```
POST /api/threads                         → threads.py:create_thread()
POST /api/threads/{threadId}/runs        → thread_runs.py:create_run()
                                             └── start_run() async
                                             └── run_agent() in asyncio.Task
GET  /api/threads/{threadId}/runs         → thread_runs.py:list_runs()
GET  /api/threads/{threadId}/runs/{runId}→ thread_runs.py:get_run()
```

### Endpoint vs SSE Distinction (CRITICAL CORRECTION)

| Endpoint | Handler | Behavior | CSRF |
|----------|---------|----------|------|
| `POST /api/threads/{id}/runs` | `create_run()` (line 97) | Returns `RunResponse` immediately, runs async | Blocked |
| `POST /api/threads/{id}/runs/stream` | `stream_run()` (line 105) | SSE StreamingResponse | Blocked |
| `POST /api/threads/{id}/runs/wait` | `wait_run()` (line 133) | Blocks until complete, returns final state | Blocked |

**All three POST endpoints blocked by CSRF in TestClient.** `/stream` was the endpoint tested in R133G smoke, but `/runs` (synchronous) is the one actually used by DeerFlowClient.

### Auth Endpoint Exemptions

`_AUTH_EXEMPT_PATHS` (csrf_middleware.py:46):
- `/api/v1/auth/login/local` — exempt
- `/api/v1/auth/logout` — exempt
- `/api/v1/auth/register` — exempt
- `/api/v1/auth/initialize` — exempt

`POST /api/threads/{id}/runs` is NOT exempt → requires CSRF token.

---

## LANE 4 — Gateway Runtime Boundary

### Full Runtime Chain

```
HTTP Request
    │
    ▼
POST /api/threads/{thread_id}/runs  or  POST /api/threads/{thread_id}/runs/stream
    │
    ▼ [thread_runs.py]
create_run()  or  stream_run()
    │              │
    ▼              │
start_run(body, thread_id, request)   [services.py:191]
    │
    ├── get_stream_bridge(request)     [app.state.stream_bridge]
    ├── get_run_manager(request)      [app.state.run_manager]
    ├── get_run_context(request)     [app.state thread_store]
    ├── run_mgr.create_or_reject()     → RunRecord created
    ├── thread_store upsert
    ├── resolve_agent_factory()       → make_lead_agent
    ├── normalize_input()
    ├── build_run_config()
    │     └── stores thread_id in config["configurable"]["thread_id"]
    └── asyncio.create_task(run_agent(...))
          │
          ▼ [runtime/runs/worker.py run_agent()]
          # Runtime injection
          runtime = Runtime(context={"thread_id": thread_id, "run_id": run_id})
          config["configurable"]["__pregel_runtime"] = runtime   [worker.py:181]
          │
          # Agent factory call
          agent = agent_factory(config=runnable_config, app_config=ctx.app_config)
          │
          # ThreadDataMiddleware prepended by factory.py:201
          chain = [ThreadDataMiddleware(lazy_init=True), UploadsMiddleware(), SandboxMiddleware(...)]
          │
          # LangGraph agent created with middleware chain
          └── graph.astream()        [worker.py:236]

Persistence surfaces initialized by langgraph_runtime(app):
    ├── app.state.stream_bridge        [StreamBridge via make_stream_bridge]
    ├── app.state.checkpointer         [Async checkpoint saver]
    ├── app.state.store                [MemoryRunStore or SQLite-backed]
    ├── app.state.run_store           [RunRepository or MemoryRunStore]
    ├── app.state.feedback_repo        [FeedbackRepository or None]
    ├── app.state.thread_store         [ThreadMetaStore]
    └── app.state.run_event_store      [RunEventStore]
```

### ThreadDataMiddleware Placement

```
middleware_chain_order (factory.py:193-203):
  [0] ThreadDataMiddleware(lazy_init=True)  ← accesses runtime.context.get("run_id") at line 110
  [1] UploadsMiddleware()
  [2] SandboxMiddleware(lazy_init=True)
  [3] DanglingToolCallMiddleware()
  [4] GuardrailMiddleware()
  [5] ToolErrorHandlingMiddleware()
  [6] SummarizationMiddleware()
  [7] TodoMiddleware()
  [8] TitleMiddleware()
  [9] MemoryMiddleware()
  [10] ViewImageMiddleware()
  [11] SubagentLimitMiddleware()
  [12] LoopDetectionMiddleware()
  [13] ClarificationMiddleware()
```

**ThreadDataMiddleware line 110** (full context):
```python
additional_kwargs={**last_message.additional_kwargs,
    "run_id": runtime.context.get("run_id"),   # ← unguarded, crashes if runtime.context is None
    "timestamp": datetime.now(UTC).isoformat()},
```

**Null-guarded path** (thread_data_middleware.py:83-90):
```python
context = runtime.context or {}          # ← this is the guard
thread_id = context.get("thread_id")
if thread_id is None:
    config = get_config()
    thread_id = config.get("configurable", {}).get("thread_id")
```

`runtime.context` uses `or {}` as fallback → returns empty dict. But `.get("run_id")` on empty dict returns None (not AttributeError). The bug requires `runtime` itself to be `None` (not just empty context) to trigger AttributeError.

### Gateway Runtime Boundary Status

| Property | Value |
|---------|-------|
| endpoint_to_service | ✅ VALID — `start_run()` in services.py |
| service_to_worker | ✅ VALID — `run_agent()` called via `asyncio.create_task()` |
| worker_to_agent | ✅ VALID — `Runtime(context={thread_id, run_id})` injected at worker.py:181 |
| runtime_context_injection | ✅ VALID — Gateway path properly injects Runtime |
| persistence_surfaces | ✅ VALID — All surfaces from `langgraph_runtime()` app lifecycle |
| ThreadDataMiddleware.before_agent() | ⚠️ UNGUARDED — `runtime.context.get("run_id")` at line 110, but guarded at line 83 with `or {}` |

**gateway_runtime_boundary_status: VALID** — The gateway/HTTP path injects Runtime correctly at worker.py:181. `ThreadDataMiddleware` is part of the agent chain (factory.py:201), not a separate gateway component.

---

## LANE 5 — Main vs Branch Chain Classification

### Chain Taxonomy

| Chain | Type | Status | Notes |
|-------|------|--------|-------|
| HTTP → thread_runs → start_run → run_agent → astream | **MAIN** | ✅ Unblocked | Runtime properly injected by worker.py |
| HTTP → thread_runs/stream → SSE | **BRANCH (SSE)** | ⚠️ CSRF blocked (TestClient artifact) | Same start_run path; different response serialization |
| Direct Python → make_lead_agent() → astream() | **BRANCH (direct)** | ❌ BLOCKED | No Runtime injection → ThreadDataMiddleware crashes |
| DeerFlowClient → POST /threads/runs | **MAIN (DeerFlowClient)** | ⚠️ CSRF + require_existing=True | Sync wait endpoint; CSRF blocks in TestClient |
| M01 orchestrator → M04 → M11 → CLI | **MAIN (Path A)** | ✅ CLEAR | No gateway dependency |

### Blocker Classification

| Blocker | Type | Gateway Path | Direct Python | Test Artifact |
|---------|------|-------------|---------------|---------------|
| ThreadDataMiddleware runtime.context | **Runtime Context** | ✅ RESOLVED (worker.py:181 injects) | ❌ BLOCKED (no injection) | ❌ No |
| CSRF middleware on POST | **CSRF** | ❌ Blocked | ❌ Blocked | ✅ TestClient only |
| config ${VAR} placeholder bug | **Latent Config** | ✅ BYPASS (GatewayConfig uses os.getenv) | ⚠️ Latent | ❌ No |
| require_existing=True on runs | **Auth Gate** | ❌ Blocks new thread creation | ❌ N/A | ❌ No |

---

## LANE 6 — Boundary Risk Matrix

| Boundary | Risk | Assessment |
|----------|------|-------------|
| TypeScript → Python (DeerFlowClient) | LOW | POST /api/threads/{id}/runs is stable; endpoint verified |
| Gateway → services → worker | LOW | start_run() interface stable; worker called correctly |
| worker → Runtime injection | LOW | Runtime(context={thread_id, run_id}) at worker.py:181 confirmed correct |
| ThreadDataMiddleware → agent chain | **MEDIUM** | Line 110 unguarded for run_id; but context fallback at line 83 reduces crash probability |
| langgraph_runtime → app.state | LOW | All surfaces initialized before yield |
| CSRF → POST endpoints | LOW (test artifact) | Not a runtime risk; TestClient limitation only |

### Risk: ThreadDataMiddleware Line 110

**Severity: MEDIUM** — While `runtime.context or {}` provides a fallback for empty context, the specific access pattern at line 110 is:
```python
"run_id": runtime.context.get("run_id")
```
If `runtime` itself is `None` (not just empty context), `None.get()` raises `AttributeError`. This happens in:
- Direct Python invocation without Runtime injection (debug.py confirms this)
- NOT in gateway path (worker.py:181 always creates Runtime before calling agent)

---

## LANE 7 — R134C Proposal

### Next Phase Recommendation

**R134C — Direct Python Path Runtime Context Fix and DeerFlowClient Smoke**

### Rationale

After LANE 4-5 mapping, three findings demand action:

1. **ThreadDataMiddleware line 110 unguarded** — `runtime.context.get("run_id")` will crash when `runtime` is `None`. This blocks any direct Python invocation of `make_lead_agent()` without going through `worker.py`. While the gateway path is immune (worker.py:181 injects properly), the direct path bug is real and blocks `debug.py`.

2. **CSRF blocks all POST /runs in TestClient** — Both `/runs` (synchronous) and `/runs/stream` (SSE) are blocked. DeerFlowClient uses `/runs` (sync). This is a test artifact for TestClient, but means the R133G goal (gateway smoke) cannot be achieved via POST in TestClient without CSRF bypass.

3. **require_existing=True blocks new thread creation** — `POST /api/threads/{id}/runs` requires an existing thread (`require_existing=True`). This blocks stateless new-thread runs from external clients. New threads must be created via `POST /api/threads` first.

### R134C Goals

1. Fix `ThreadDataMiddleware` line 110 null guard — add `runtime.context or {}` or equivalent fallback before accessing `.get()`
2. Confirm DeerFlowClient smoke with HTTP-level test (requires CSRF bypass or GET-only endpoint)
3. Map deferred BP-02 MCP credential gap (R134A: "BP-02 MCP credentials MISSING")

### R134C Constraints

- Code modification ALLOWED for ThreadDataMiddleware fix
- Gateway startup ALLOWED (smoke test)
- Model API calls ALLOWED (basic health check)
- Production DB writes PROHIBITED
- Push to remote PROHIBITED

---

## LANE 8 — Report Generation

### Files Generated

| File | Status |
|------|--------|
| `migration_reports/recovery/R134B_...md` | Written |
| `migration_reports/recovery/R134B_...json` | Written |

---

## Final Report

```
R134B_MAIN_CHAIN_ENTRYPOINT_AND_BRANCH_BOUNDARY_CROSS_VALIDATION_DONE

status=completed
pressure_assessment_completed=true
recommended_pressure=XXL++
typescript_chain_mapped=true
path_a_boundary_mapped=true
path_b_boundary_mapped=true
endpoint_vs_sse_distinction_confirmed=true
gateway_runtime_chain_mapped=true
endpoint_to_service=start_run (services.py:191)
service_to_worker=run_agent (worker.py:79)
worker_to_agent=Runtime(context={thread_id,run_id}) at worker.py:181
runtime_context_injection=confirmed_valid
persistence_surfaces=stream_bridge, checkpointer, store, run_store, thread_store, run_event_store
thread_data_middleware_status=unguarded_run_id_access_line_110_but_context_fallback_at_line_83
gateway_runtime_boundary_status=valid
chain_taxonomy={
  main_http: "POST /runs → start_run → run_agent → astream",
  branch_sse: "POST /stream → SSE (same start_run path, different response)",
  branch_direct: "Direct make_lead_agent() → astream() (BLOCKED by no Runtime injection)",
  main_deerflow_client: "POST /runs (sync wait)",
  main_path_a: "M01→M04→M11→CLI"
}
blocker_classification={
  thread_data_middleware: {gateway: RESOLVED, direct: BLOCKED, test_artifact: false},
  csrf: {gateway: BLOCKED, direct: BLOCKED, test_artifact: true},
  config_var_bug: {gateway: BYPASS, direct: LATENT, test_artifact: false},
  require_existing: {gateway: BLOCKED, direct: N/A, test_artifact: false}
}
boundary_risk_matrix={
  typescript_to_python: LOW,
  gateway_to_services: LOW,
  worker_to_runtime_injection: LOW,
  thread_data_middleware: MEDIUM,
  langgraph_runtime: LOW,
  csrf_post: LOW_test_artifact
}
r134c_proposed=true
r134c_goals=[
  "Fix ThreadDataMiddleware line 110 null guard",
  "DeerFlowClient HTTP-level smoke (CSRF-aware)",
  "BP-02 MCP credential gap mapping"
]
r134c_constraints={code_modification: ALLOWED, gateway_startup: ALLOWED, model_api: ALLOWED, db_write: PROHIBITED, push: PROHIBITED}
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
next_prompt_needed=R134C_DIRECT_PYTHON_PATH_RUNTIME_CONTEXT_FIX_AND_DEERFLOW_CLIENT_SMOKE
```

---

*Generated by Claude Code — R134B (Main Chain Entrypoint and Branch Boundary Cross-Validation)*
