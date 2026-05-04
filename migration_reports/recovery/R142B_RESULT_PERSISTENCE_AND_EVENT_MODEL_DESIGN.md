# R142B: Result Persistence and Event Model Design

## Status: PASSED ✅

## Preceded By: R142_RUN_STATUS_RESULT_CLOSURE
## Proceeding To: R142C_RESULT_PERSISTENCE_PATCH

## Pressure: XXL

---

## Summary

R142B is a read-only design phase investigating the result persistence gap found in R142 (RunStore record has no result/output/messages fields, GET /runs/{run_id} returns only metadata). Research across 6 areas confirms the gap and recommends Option A — add `result` field to `RunRecord` and capture final state via worker.py finally block.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| Previous phase | R142 |
| Current phase | R142B |
| Recommended pressure | XXL |
| Pressure check | PASS |

---

## LANE 1: R142 Evidence Reconciliation

| Field | R142 JSON value | Corrected value |
|---|---|---|
| `final_run_status` | success | **success** ✅ |
| `model_api_called` | false (lane_4) / true (safety_constraints) | **true** ✅ (2 MiniMax API calls in logs) |
| `model_api_call_count` | 1 | 1 |
| `http_get_run_has_result` | false | **false** ✅ |
| `runstore_has_result` | false | **false** ✅ |
| `run_event_count` | 13 | 13 |
| `stream_event_count` | 5 | 5 |
| `tool_call_detected` | false | **false** ✅ |
| `mcp_runtime_called` | false | **false** ✅ |

**Conclusion:** R142 was correct — model API was called, run succeeded, but result surface is only in StreamBridge and events, not in RunStore record or HTTP GET response.

---

## LANE 2: RunStore / RunRecord Data Model

**RunRecord definition** (`packages/harness/deerflow/runtime/runs/manager.py`, line 25):

```python
@dataclass
class RunRecord:
    run_id: str
    thread_id: str
    assistant_id: str | None
    status: RunStatus
    on_disconnect: DisconnectMode
    multitask_strategy: str = "reject"
    metadata: dict = field(default_factory=dict)
    kwargs: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    task: asyncio.Task | None
    abort_event: asyncio.Event
    abort_action: str = "interrupt"
    error: str | None = None
```

**Fields:** run_id, thread_id, assistant_id, status, on_disconnect, multitask_strategy, metadata, kwargs, created_at, updated_at, task, abort_event, abort_action, error

**Result fields:** ❌ NO `result` ❌ NO `output` ❌ NO `messages`

**Existing method:** `update_run_completion(token_counts, last_ai_message, first_human_message, error)` — stores token counts and convenience fields, not full result.

**Storage backends:** MemoryRunStore (in-memory dict), pluggable RunStore interface.

`★ Insight ─────────────────────────────────────`
**核心缺口**：RunRecord 是一个简单的 dataclass，只有状态和元数据字段，没有任何 result/output 存储能力。`update_run_completion` 方法只记录 token 使用统计，不记录模型的实际输出内容。
`─────────────────────────────────────────────────`

---

## LANE 3: HTTP GET /runs/{run_id} Response Model

**GET endpoint** (`thread_runs.py:166`):
```python
@router.get("/{thread_id}/runs/{run_id}", response_model=RunResponse)
async def get_run(thread_id: str, run_id: str, request: Request) -> RunResponse:
```

**RunResponse model** (`thread_runs.py:59`):
```python
class RunResponse(BaseModel):
    run_id: str
    thread_id: str
    assistant_id: str | None = None
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    multitask_strategy: str = "reject"
    created_at: str = ""
    updated_at: str = ""
```

**Result fields in response:** ❌ NO `result` ❌ NO `output` ❌ NO `messages`

**Other result access paths:**
- `POST /{thread_id}/runs/wait` (line 133) — reads from **checkpointer** latest checkpoint's `channel_values`, returns `serialize_channel_values(channel_values)` — this IS the result access path
- `GET /{thread_id}/runs/{run_id}/messages` (line 329) — returns messages from **RunEventStore** `list_messages_by_run()`

**Conclusion:** GET /runs/{run_id} is intentionally metadata-only. The actual result is accessible via `/wait` endpoint (checkpointer) and `/messages` endpoint (event store).

---

## LANE 4: RunEventStore Event Model

**Event structure** (`MemoryRunEventStore._put_one()`, line 37):
```python
{
    "thread_id": thread_id,
    "run_id": run_id,
    "event_type": event_type,   # e.g. "llm.ai.response", "llm.human.input"
    "category": category,       # "message" | "trace" | "middleware" | "error" | "outputs"
    "content": content,         # str | dict — AIMessage.model_dump() for AI responses
    "metadata": metadata or {},
    "seq": seq,                 # monotonically increasing per thread
    "created_at": created_at or datetime.now(UTC).isoformat(),
}
```

**Event types detectable:** ✅ Yes — `event_type` field distinguishes model responses (`llm.ai.response`), human inputs (`llm.human.input`), tool results (`llm.tool.result`), etc.

**Model response captured as:** `AIMessage.model_dump()` dict in `content` field — full message structure.

**Storage format:** Raw `dict` objects (not typed) — consistent with R142 observation that `event_types=['dict']`.

**RunEventStore is already a canonical log** — all events are stored with full content. No model change needed to query final result from events.

---

## LANE 5: StreamBridge Event Model

**StreamEvent structure** (`stream_bridge/base.py`, line 17):
```python
@dataclass(frozen=True)
class StreamEvent:
    id: str    # "timestamp-sequence"
    event: str # SSE event name: "metadata", "values", "messages", "custom", "error", "end"
    data: Any  # JSON-serializable payload
```

**For `values` stream mode:** `data = serialize_channel_values(channel_values)` — dict with `messages`, `title`, `artifacts`, `todos` keys.

**R142 false negative explanation:** The inspection code used `isinstance(ev_data, str) and len(ev_data) > 5` — but `data` is a **dict** (serialized channel_values), not a string. So model response was present but not detected by the string check. The StreamBridge 5 events contain accumulated channel state.

**StreamBridge is ephemeral** — events exist only during active stream. Not suitable as primary result store.

---

## LANE 6: Worker / Agent Output Capture Points

**astream loop** (worker.py:232-259):
```python
async for chunk in agent.astream(graph_input, config=runnable_config, stream_mode=single_mode):
    if record.abort_event.is_set():
        break
    sse_event = _lg_mode_to_sse_event(single_mode)
    await bridge.publish(run_id, sse_event, serialize(chunk, mode=single_mode))
```

**Event publishing:** Events buffered in `journal` (BaseCallbackHandler), flushed via `journal.flush()` in finally block.

**Post-loop section** (worker.py:262-281):
```python
if record.abort_event.is_set():
    # interrupt/rollback path
else:
    await run_manager.set_status(run_id, RunStatus.success)  # line 276
```

**Recommended capture point:** worker.py finally block — `journal.get_completion_data()` already extracts `last_ai_message`, `first_human_message`, token counts. This is the lowest-risk extension point — just capture `serialize_channel_values(final_channel_values)` as `result` and store in RunRecord.

---

## LANE 7: DeerFlowClient / Caller Expectation

**DeerFlowClient** (`packages/harness/deerflow/client.py`):
- `stream()` — yields `StreamEvent(type, data)` until end events
- `chat()` — accumulates delta chunks, returns last AI message text
- **NO polling** of GET /runs/{run_id} for result

**Frontend** (`frontend/src/core/threads/hooks.ts`):
- Uses `@langchain/langgraph-sdk/react` `useStream` hook
- `onFinish(state)` receives `state.values` (channel_values dict)
- Does NOT read `result` field from GET /runs/{run_id}
- Result comes from **SSE stream**, not from HTTP GET

**Current gap:** No persistent result accessible via GET /runs/{run_id} — only metadata. Result is only available via SSE stream or `POST /runs/wait` (checkpointer read).

---

## LANE 8: Design Options

| Option | Implementation Cost | Correctness | Frontend Usefulness | Risk |
|---|---|---|---|---|
| **A — RunStore Snapshot** | medium | high | high | medium |
| B — RunEventStore Canonical + Projection | low | high | medium | low |
| C — StreamBridge Only | low | medium | low | low |
| D — Hybrid (EventStore + Store summary) | medium | high | high | medium |

### Option A — RunStore Snapshot (Recommended)

**What:** Add `result: dict` field to `RunRecord`. Worker.py finally block captures `serialize_channel_values(final_state)` and stores via `update_run_completion` or new method.

**Why recommended:** Directly addresses R142 finding. Minimal worker changes. GET /runs/{run_id} immediately returns result. Lowest cost to give callers a persistent result handle.

**Patch surface:**
1. `RunRecord` dataclass — add `result: dict | None = None`
2. `RunResponse` model — add `result: dict | None = None`
3. `_record_to_response()` — copy `record.result` to response
4. `worker.py` finally block — capture final state and write to record

---

## LANE 9: Patch Authorization for R142C

**Authorization:** ✅ Required

**Files allowed:**
- `packages/harness/deerflow/runtime/runs/worker.py`
- `packages/harness/deerflow/runtime/runs/manager.py` (RunRecord dataclass)
- `app/gateway/routers/thread_runs.py` (RunResponse model + _record_to_response)
- `packages/harness/deerflow/runtime/serialization.py` (serialize_channel_values — no change needed)

**Files forbidden:** `app/gateway/app.py`, `auth_middleware.py`, `csrf_middleware.py`, persistence modules, config.yaml, .env

**Expected diff:**
1. `RunRecord` dataclass: `+result: dict | None = None`
2. `RunResponse` model: `+result: dict | None = None`
3. `_record_to_response()`: add `result=record.result` copy
4. `worker.py` finally block: after `journal.get_completion_data()` call, capture `serialize_channel_values(channel_values)` and write to record via existing `update_run_completion` path

**Validation:** R142C inline smoke test — GET /runs/{run_id} has non-empty `result.messages`

**Rollback:** Revert all changes — all are additive only

---

## LANE 10: Unknown Registry Update

| ID | Description | Priority |
|---|---|---|
| U-result-persistence-design | Option A recommended — RunRecord gains result field, worker captures final state | high |
| U-final-output-capture-point | Recommended: worker.py finally block via journal.get_completion_data() + serialize_channel_values | high |
| U-runeventstore-canonical-log | RunEventStore already stores llm.ai.response events — already canonical log | medium |
| U-deerflowclient-result-expectation | DeerFlowClient uses stream, not result polling. Result not from GET /runs/{run_id}. | medium |
| U-streambridge-false-negative | R142 model_response_detected=False was false negative — data is dict not string | low |

---

## Safety Verification

| Constraint | Result |
|---|---|
| No code modified | ✅ |
| No DB/JSONL written | ✅ |
| No model API called | ✅ |
| No MCP started | ✅ |
| No tool call executed | ✅ |
| Safety violations | **None** |

---

## R142B_RESULT_PERSISTENCE_AND_EVENT_MODEL_DESIGN_DONE

```
status=passed
pressure_assessment_completed=true
recommended_pressure=XXL
r142_reconciled_facts={
  final_run_status=success,
  model_api_called=true,
  model_api_call_count=1,
  http_get_run_has_result=false,
  runstore_has_result=false,
  run_event_count=13,
  stream_event_count=5,
  tool_call_detected=false,
  mcp_runtime_called=false
}
runstore_model={
  record_fields=[run_id,thread_id,assistant_id,status,on_disconnect,multitask_strategy,metadata,kwargs,created_at,updated_at,task,abort_event,abort_action,error],
  has_result_field=false,
  has_output_field=false,
  has_messages_field=false,
  update_result_method_exists=false,
  update_run_completion_exists=true
}
http_run_response_model={
  response_fields=[run_id,thread_id,assistant_id,status,metadata,kwargs,multitask_strategy,created_at,updated_at],
  has_result=false,
  wait_endpoint_reads_from=checkpointer channel_values,
  messages_endpoint=GET /{thread_id}/runs/{run_id}/messages
}
runevent_model={
  event_store_fields=[thread_id,run_id,event_type,category,content,metadata,seq,created_at],
  model_response_event_type=llm.ai.response,
  canonical_log_candidate=true
}
streambridge_model={
  values_mode_data=serialize_channel_values(channel_values) dict,
  false_negative_reason=data is dict not string,
  persistence_candidate=limited
}
worker_capture_points=[
  {location:"worker.py finally block", recommended:true, risk:low, reason:"journal.get_completion_data() already called; expand to capture serialize_channel_values(final_state)"}
]
caller_expectations={
  deerflow_client_uses_stream=true,
  frontend_uses_useStream_hook_onFinish=true,
  result_from_sse_stream=true,
  result_from_http_get=false
}
design_options=[A:RunStore Snapshot (recommended), B:EventStore Projection, C:StreamBridge Only, D:Hybrid]
recommended_design=Option A — RunStore Snapshot
r142c_patch_authorization_required=true
r142c_patch_package={
  files_allowed=[worker.py, manager.py (RunRecord), thread_runs.py (RunResponse), serialization.py],
  files_forbidden=[app.py, auth_middleware.py, csrf_middleware.py, persistence, config.yaml, .env],
  expected_diff="RunRecord+result field; RunResponse+result field; _record_to_response copies result; worker finally captures serialize_channel_values",
  validation="R142C inline smoke — GET /runs/{run_id} has non-empty result.messages",
  rollback="revert all — all additive only"
}
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
recommended_next_phase=R142C_RESULT_PERSISTENCE_PATCH
next_prompt_needed=R142C execution authorization
```