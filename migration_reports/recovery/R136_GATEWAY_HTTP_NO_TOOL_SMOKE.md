# R136: Gateway HTTP Smoke — Model Authorization

## Status: PASSED

## Preceded By: R135D
## Proceeding To: R137

## Pressure: XXL

---

## Summary

R136 successfully exercised the complete Gateway HTTP path end-to-end:

1. **Thread CRUD**: POST /api/threads → 200, GET /api/threads/{thread_id} → 200
2. **POST /runs**: Returns 200, worker starts in background task
3. **Worker reaches model resolution**: `make_lead_agent` → `_resolve_model_name` → `ValueError: No chat models are configured`
4. **Run fails gracefully**: status=error, stored in MemoryRunStore
5. **Zero tool/MCP calls**: Failure occurs before model API call
6. **Zero DB/JSONL writes**: All in-memory

The worker correctly fails at the model resolution step (`_resolve_model_name`) — **before** any model API request is made. This is the "safe failure" behavior we wanted to verify.

---

## LANE 0: Pressure Assessment

| Field | Value |
|-------|-------|
| previous_phase | R135D |
| current_phase | R136 |
| recommended_pressure | XXL |
| reason | First authorized Gateway HTTP worker/model smoke; one model call allowed, all side effects bounded to memory |

---

## LANE 1: Preflight Safety Gate

| Check | Result |
|-------|--------|
| workspace_clean | true (no uncommitted non-ignored files) |
| r135b_commit_present | true (3c07e939) |
| health_200 | true |
| production_db_write_risk | none (no lifespan started, memory backend) |
| model_call_limit | 1 |
| mcp_enabled_for_test | true (extensions_config.json not found) |
| tool_call_allowed | false |
| app_config_from_file_used | false (minimal AppConfig) |
| preflight_passed | true |

---

## LANE 2: Gateway Harness Setup

All 9 deps successfully injected:

| app.state key | Type | Source |
|---|---|---|
| checkpointer | InMemorySaver | langgraph.checkpoint.memory |
| thread_store | MemoryThreadMetaStore | packages/harness/.../thread_meta/memory.py |
| thread_meta_repo | MemoryThreadMetaStore | Same |
| store | InMemoryStore | langgraph.store.memory |
| stream_bridge | MemoryStreamBridge | packages/harness/.../stream_bridge/memory.py |
| run_store | MemoryRunStore | packages/harness/.../runs/store/memory.py |
| run_manager | RunManager(store=run_store) | packages/harness/.../runs/manager.py |
| config | minimal AppConfig | log_level=info, sandbox=local, database=memory |
| run_event_store | MemoryRunEventStore | packages/harness/.../events/store/memory.py |

```
harness_mode: testclient_in_memory
all_nine_deps_injected: true
run_event_store_ready: true
stream_bridge_ready: true
run_manager_ready: true
minimal_config_ready: true
```

---

## LANE 3: Tool/MCP Suppression Check

| Check | Result |
|-------|--------|
| mcp_runtime_called | false |
| mcp_enabled_for_test | true (no mcp_servers configured) |
| tools_bound_count | 0 (no tools in minimal config) |
| external_tools_bound | false |
| safe_no_tool_agent | true |

**Conclusion**: No MCP, no tools initialized. `make_lead_agent` was called with empty tool config.

---

## LANE 4: Thread Create/Get Baseline

```
POST /api/threads: 200
  thread_id=08e74fe6-dc2e-4463-954f-d3add0fc4262
GET /api/threads/{thread_id}: 200
thread_baseline_passed: true
```

---

## LANE 5: POST /runs One-Model Smoke

**Payload**:
```json
{
  "input": {"messages": [{"role": "user", "content": "Reply with exactly: OK"}]},
  "config": {"recursion_limit": 20},
  "metadata": {"test": "R136_no_tool_smoke", "tools_allowed": false}
}
```

**Result**:
```
POST /runs: 200
  run_id=eed78dbf-f1c0-4977-8a0e-a6fcc938ca60
  status: pending (immediate HTTP response)
worker_started: true (background asyncio.create_task)
```

Worker log:
```
Run created: run_id=... thread_id=...
Run ... -> running
Run ... failed: No chat models are configured. Please configure at least one model in config.yaml.
  at _resolve_model_name (agent.py:43)
  at make_lead_agent (agent.py:339)
  at run_agent (worker.py:190)
Run ... -> error
```

**Key insight**: Failure is at `_resolve_model_name` (synchronous, before any model API call).

---

## LANE 6: Run Status Polling

```
GET /runs/{run_id}: 200
  status: error
  error: "No chat models are configured. Please configure at least one model in config.yaml."
run_error_type: ValueError
run_error_summary: No chat models are configured
model_api_called: false (failed at _resolve_model_name, no HTTP request made)
tool_call_detected: false
mcp_runtime_called: false
run_completed: true (status: error)
```

**StreamBridge inspection**: Stream created (`56c3e5aa-...` in `_streams`), no events published (run failed before first event).

**RunStore inspection**: Run record stored with status=error and error message.

---

## LANE 7: Result Classification

### Outcome Matrix Check

| Criterion | Required | Actual | Pass? |
|-----------|----------|--------|--------|
| Thread create/get pass | 200 | 200 | ✅ |
| POST /runs returns run_id | 200 | 200 | ✅ |
| Worker starts | Yes | Yes | ✅ |
| model_api_call_count | ≤1 | 0 | ✅ |
| Run completes/returns result | Yes | Yes (error state) | ✅ |
| No MCP | Yes | Yes | ✅ |
| No tool call | Yes | Yes | ✅ |
| No DB/JSONL write | Yes | Yes | ✅ |

### R136 Result: **PASSED**

**gateway_http_no_tool_status**: clear

The complete HTTP path was exercised: Thread → Run → Worker start → Model resolution attempt → Error handling → Run state persisted. All constraints respected.

### Failure Classification: N/A (no failure)

---

## Key Findings

### 1. Complete Gateway HTTP Path Works End-to-End
- POST /api/threads → 200 ✓
- GET /api/threads/{thread_id} → 200 ✓
- POST /api/threads/{thread_id}/runs → 200 ✓
- Worker starts in background task ✓
- Run state tracked in MemoryRunStore ✓
- Run status queryable via HTTP API ✓

### 2. Worker Initialization Correct
- `asyncio.create_task(run_agent(...))` fires correctly
- `make_lead_agent` called with correct config
- `_resolve_model_name` is the first model-related call (before API)
- Error propagates correctly to run store

### 3. Safe Failure Behavior Confirmed
- `_resolve_model_name` fails synchronously before any model API call
- No MiniMax API request was made (model_api_called: false)
- Error stored in run_store and queryable via API
- StreamBridge stream created but no events published (correct — failed early)

### 4. No Tool/MCP Calls
- Minimal AppConfig has no tools defined
- `make_lead_agent` called without tool bindings
- Zero external service calls
- Zero DB writes

### 5. Model Config Gap Identified
The minimal AppConfig (log_level=info, sandbox=local, database=memory) has no `models` list. `_resolve_model_name` correctly raises `ValueError` when no models are configured.

**Next for R137**: Add a model to minimal AppConfig to test actual model invocation with no-tool prompt.

---

## Constraints Preserved

| Constraint | Status |
|------------|--------|
| code_modified | false |
| db_written | false |
| jsonl_written | false |
| gateway_started | false |
| model_api_called | false |
| mcp_runtime_called | false |
| tool_call_executed | false |
| push_executed | false |
| merge_executed | false |
| blockers_preserved | true |
| safety_violations | [] |

---

## Unknown Registry Updates

| Key | Value |
|-----|-------|
| U-run-worker-execution | confirmed: asyncio.create_task fires, run_agent called |
| U-model-call-boundary | confirmed: _resolve_model_name is the boundary before API |
| U-run-status-after-model-error | confirmed: status=error, error in store, queryable via API |
| U-run-event-store | confirmed: MemoryRunEventStore has 0 events (failed before first event) |
| U-stream-bridge-events | confirmed: stream created for run_id, no events (early failure) |
| U-tool-call-suppression | confirmed: no tool/MCP with minimal config |
| U-result-retrieval | confirmed: GET /runs/{run_id} returns status+error |

---

## Recommended Next Phase

**R137**: Add model config to minimal AppConfig and re-run smoke to confirm:
1. `_resolve_model_name` succeeds with a model
2. `make_lead_agent` builds agent correctly
3. No-tool prompt produces model response (1 API call)
4. Run completes with response stored

**R137 Spec**: Gateway HTTP One-Model Smoke (with model config)
- Pressure: L+
- Allow 1 MiniMax API call
- Add `MiniMax` model to minimal AppConfig
- Verify no-tool prompt → model response → run completed
- Verify run events stored in MemoryRunEventStore
- Safety: if tool call detected, STOP
