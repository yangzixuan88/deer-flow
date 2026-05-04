# R139B: Graph/Middleware/Checkpointer Interrupt Diagnostic

## Status: PARTIAL

## Preceded By: R139
## Proceeding To: R139C_INTERRUPT_CAUSAL_CHAIN_TEST

## Pressure: XXL

---

## Summary

R139B is a 12-lane read-only diagnostic to trace the exact code path from `running → interrupted` in R139. Key finding: **Model response WAS published (103 chars, 2 events) before the interrupt, but `task.cancel()` was definitely called (CancelledError caught). Neither `manager.cancel()` nor `create_or_reject` interrupt/rollback is in R139's call path. POST /runs returns plain JSON (RunResponse), not StreamingResponse.**

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| R139 actual outcome | Outcome B2 — still interrupted (WITH model call) |
| R139 model response detected | True (103 chars, 2 events) |
| R139 final status | interrupted |
| R139 poll elapsed | 3s |
| Pressure for R139B | XXL |
| Rationale | R139 confirmed interrupt fires AFTER model response; model was called; next diagnostic must trace exact causal chain |

---

## LANE 1: R139 Outcome Deconstruction

| Item | Value |
|---|---|
| R139 result | partial |
| Outcome | Outcome B2 — still interrupted (WITH model call) |
| interrupt_before_sent | `[]` (empty list) |
| interrupt_after_sent | `[]` (empty list) |
| model_api_called | True |
| model_response_detected | True |
| model_response_length | 103 |
| stream_event_count | 2 |
| stream_bridge_stream_created | True |
| final_status | interrupted |

**Key observation:** Model response was published to stream bridge BEFORE the interrupt. `abort_event.is_set()` returned False during model response publish, but True at final status check.

**Implication:** `abort_event` was set AFTER the model response was published and BEFORE the worker loop exited normally.

---

## LANE 2: Worker astream Loop Analysis

### Loop Structure (worker.py:233-241)

```python
async for chunk in agent.astream(graph_input, config=runnable_config, stream_mode=single_mode):
    if record.abort_event.is_set():
        logger.info("Run %s abort requested — stopping", run_id)
        break
    sse_event = _lg_mode_to_sse_event(single_mode)
    await bridge.publish(run_id, sse_event, serialize(chunk, mode=single_mode))
```

### Post-Loop Status (worker.py:262-281)

```python
if record.abort_event.is_set():
    action = record.abort_action
    if action == "rollback":
        await run_manager.set_status(run_id, RunStatus.error, error="Rolled back by user")
        ...
    else:
        await run_manager.set_status(run_id, RunStatus.interrupted)
else:
    await run_manager.set_status(run_id, RunStatus.success)
```

### Publish Order Analysis

| Step | Event | abort_event State | Evidence |
|---|---|---|---|
| 1 | model response published to stream bridge | False | stream_event_count=2, model_response_detected=True |
| 2 | loop continues or exits normally (no more chunks) | False | abort_event False during loop |
| 3 | `if record.abort_event.is_set():` at line 262 | **TRUE** | final_status=interrupted, not success |
| 4 | `await run_manager.set_status(run_id, RunStatus.interrupted)` at line 279 | — | final_status=interrupted confirmed |

**Critical finding:** `abort_event` was set AFTER model response published (step 1) and BEFORE final status check (step 3). The only way `abort_event` is set is via: (a) `manager.cancel()`, (b) `create_or_reject` interrupt/rollback cleanup, or (c) something external.

---

## LANE 3: manager.cancel() and create_or_reject Analysis

### manager.cancel() (manager.py:155-166)

```python
def cancel(self, run_id: str, action: str = "interrupt") -> bool:
    record = self._runs.get(run_id)
    if record is None:
        return False
    if record.status not in (RunStatus.pending, RunStatus.running):
        return False
    record.abort_action = action
    record.abort_event.set()          # line 160
    if record.task is not None and not record.task.done():
        record.task.cancel()          # line 162
    record.status = RunStatus.interrupted  # line 163
```

**Callers found:** `services.py:296` (sse_consumer finally block) — **NOT called in R139** (stream endpoint never invoked).

### create_or_reject interrupt/rollback (manager.py:201-208)

```python
if multitask_strategy in ("interrupt", "rollback") and inflight:
    for r in inflight:
        r.abort_action = multitask_strategy
        r.abort_event.set()          # line 204
        if r.task is not None and not r.task.done():
            r.task.cancel()          # line 206
        r.status = RunStatus.interrupted  # line 207
```

**Condition:** `multitask_strategy in ('interrupt', 'rollback')` AND inflight runs exist. **NOT triggered in R139** — `multitask_strategy='reject'` (default) and no inflight runs exist for R139's thread.

**Conclusion:** Neither `cancel()` nor `create_or_reject` interrupt path is in R139's call path. Yet `task.cancel()` was definitely called (`CancelledError` caught). Something else must be calling `task.cancel()`.

---

## LANE 4: sse_consumer and Stream Endpoint Inaccessibility

### Stream Endpoint Inaccessibility

| Item | Value |
|---|---|
| Stream endpoint | `POST /api/threads/{thread_id}/runs/stream` (thread_runs.py:103) |
| sse_consumer function | `services.py:296` — async generator with `finally: if on_disconnect == cancel and status in (pending, running): await run_mgr.cancel()` |
| R139 HTTP calls | POST /api/threads, GET /api/threads/{thread_id}, POST /api/threads/{thread_id}/runs, GET /api/threads/{thread_id}/runs/{run_id} |
| Stream endpoint called | **False** |
| sse_consumer invoked | **False** |

**Conclusion:** `sse_consumer`'s cancel path is **IMPOSSIBLE** to reach in R139. `on_disconnect` cancel requires: (a) stream endpoint called, (b) SSE client disconnected, (c) `on_disconnect == cancel`. None of these apply to R139.

### on_disconnect Field

`thread_runs.py:51`: `on_disconnect: cancel | continue (default='cancel')` — uses default 'cancel' but stream endpoint never called. **No impact.**

---

## LANE 5: Worker astream Completion Logic

### Why stream_event_count=2 then interrupted?

The `abort_event.is_set()` check at worker.py:237 runs **inside** the astream loop. During the model response publish, `abort_event.is_set()` returned **False** (otherwise the loop would break before publishing). After the model response was published, the loop continued (or exited normally). At the **post-loop** check (line 262), `abort_event.is_set()` returned **True**.

**Timeline:**

1. `worker:running` → model API starts → model API completes (response published to stream bridge) → abort_event still False
2. Loop continues or exits normally (no more chunks coming)
3. worker.py:262: `if record.abort_event.is_set():` → **TRUE** (but WHEN was it set?)
4. worker.py:279: `await run_manager.set_status(run_id, RunStatus.interrupted)` — final status confirmed

**Critical gap:** `abort_event` was set BETWEEN model response publish and the final status check. But HOW?

### worker.py:283 CancelledError Handler

```python
except asyncio.CancelledError:
    action = record.abort_action
    if action == "rollback":
        await run_manager.set_status(run_id, RunStatus.error, ...)
    else:
        await run_manager.set_status(run_id, RunStatus.interrupted)
        logger.info("Run %s was cancelled", run_id)
```

**R139 log evidence:** worker.py:301 log line `"Run %s was cancelled"` confirms `CancelledError` WAS caught — `task.cancel()` was called.

**task.cancel() sources:** Only at `manager.py:162` (cancel method) and `manager.py:206` (create_or_reject). Neither in R139's call path.

---

## LANE 6: TestClient Background Task / Event Loop Lifecycle Hypothesis

### Hypothesis: Cause A — TestClient StreamingResponse / response handling triggering background task cancellation

### POST /runs Response Type

**Key finding:** `POST /runs` (create_run endpoint, thread_runs.py:97-100) returns `RunResponse` (plain JSON), **NOT** `StreamingResponse`.

```python
async def create_run(thread_id: str, body: RunCreateRequest, request: Request) -> RunResponse:
    """Create a background run (returns immediately)."""
    record = await start_run(body, thread_id, request)
    return _record_to_response(record)
```

The `StreamingResponse` is only used by `POST /runs/stream` endpoint (thread_runs.py:103-128). **R139 never calls the stream endpoint.**

### services.py:272 Task Creation

```python
task = asyncio.create_task(
    run_agent(...),
)
record.task = task
# HTTP response returns immediately after create_run() returns
```

The `run_agent` task is created as a background task that outlives the HTTP request/response cycle.

### TestClient Lifecycle Teardown Hypothesis

**Mechanism:** `with TestClient(app) as client: client.post('/runs', json=payload)` returns immediately with run_id. Test then polls status. Then `'with'` block exits → TestClient tears down lifespan/event loop → background `run_agent` task cancelled → `CancelledError` caught → status=`interrupted`.

**R139 polling timing:** poll_elapsed_seconds=3. The test polled until completion. If TestClient context exited during or shortly after polling, the background task could be cancelled.

**Evidence FOR:** Explains why `CancelledError` was caught despite no explicit `cancel()` call. The timeline gap (abort_event set AFTER model response but BEFORE final check) is consistent with TestClient context teardown happening during the worker's post-model processing.

**Evidence AGAINST:** Would apply to ALL tests using TestClient background tasks, not just R139.

---

## LANE 9: Diagnostic Conclusion

### Most Likely Cause: **Cause A — TestClient background task cancellation via event loop lifecycle**

**Confidence:** Medium

**Supporting evidence:**
1. `task.cancel()` was called (`CancelledError` caught in worker.py:301)
2. Neither `manager.cancel()` nor `create_or_reject` interrupt/rollback is in R139's call path
3. `POST /runs` returns plain JSON (`RunResponse`), not `StreamingResponse` — no SSE stream cleanup involved
4. TestClient lifecycle teardown could cancel background tasks when the context exits
5. 3-second poll_elapsed is consistent with TestClient context exiting during polling
6. `abort_event.is_set()` returned False during model response publish, then True at final check — suggests cancellation happening between model completion and worker loop completion

### Alternative Cause: **Cause C — Unknown cleanup path in run_agent completion**

**Confidence:** Low

**Reasoning:** `create_run()` returns `RunResponse`, not `StreamingResponse` — no SSE stream handling involved. However, there could be an unknown cleanup path in the run_agent completion that triggers cancellation.

### Cause B (StreamBridge drain): **Partially plausible**

`stream_event_count=2` (model response published), `abort_event.is_set()` returned False during model response, then True at final check — suggests `abort_event.set()` called BETWEEN model response publish and worker loop completion. But the StreamBridge drain hypothesis doesn't explain the `CancelledError` caught in worker.py (StreamBridge doesn't call `task.cancel()`).

### Cause D (Checkpointer interrupt): **Unlikely**

R139 used new run_id and new thread_id. Checkpointer interrupt state from prior execution is unlikely.

---

## CRITICAL FINDING

> Model response was published (103 chars, 2 events, stream_event_count=2) before the interrupt. `abort_event.is_set()` returned False during model response publish, then True at final status check. `task.cancel()` was definitely called (`CancelledError` caught at worker.py:301). Neither `manager.cancel()` nor `create_or_reject` interrupt/rollback is in R139's call path. `POST /runs` returns plain JSON (`RunResponse`), not `StreamingResponse`. **Most likely cause: TestClient background task cancellation during event loop lifecycle teardown (Cause A), OR an unknown cleanup path in the run_agent completion path (Cause C).**

---

## LANE 10: R140 Plan Generation

### Phase: R140 — INTERRUPT_CAUSAL_CHAIN_TEST

**Objective:** Test the causal chain between TestClient background task lifecycle and the interrupt. Specifically: await `run_agent` inline (not as background task) and see if interrupt still occurs.

**Approach:** Modify `POST /runs` to await `run_agent` inline instead of `asyncio.create_task` — eliminates background task that could be cancelled by TestClient lifecycle.

**Expected outcome:** If interrupt still fires with inline await → interrupt source is in graph/middleware/checkpointer, NOT TestClient lifecycle. If interrupt disappears with inline await → Cause A (TestClient background task cancellation) confirmed.

**Constraints:**

| Constraint | Value |
|---|---|
| code_modified | true |
| db_written | false |
| jsonl_written | false |
| gateway_started | false |
| model_api_called | true |
| mcp_runtime_called | false |
| tool_call_executed | false |
| push_executed | false |
| merge_executed | false |

**Note:** `code_modified=true` because modifying `services.py` start_run behavior is required.

**Pressure:** XXL — model API call with modified task execution path.

---

## LANE 11: Unknown Registry Update

| ID | Description | Priority | Updated |
|---|---|---|---|
| U-explicit-empty-interrupt-effect | interrupt_before=[] and interrupt_after=[] passed — interrupt PERSISTS | critical | CONFIRMED: interrupt persists with interrupt_before=[]; now confirmed interrupt fires AFTER model response |
| U-interrupt-source-still-unknown | Interrupt source STILL_UNCLEAR after R139 | critical | Narrowed to: (A) TestClient lifecycle cancellation, (B) StreamBridge cleanup, (C) Unknown middleware, (D) Checkpointer interrupt |
| **U-task-cancel-source-unknown** | `task.cancel()` was called in R139 (CancelledError caught) but neither `manager.cancel()` nor `create_or_reject` interrupt/rollback is in R139 call path | critical | NEW — critical |
| **U-post-runs-response-type** | `create_run()` returns `RunResponse` (JSON), not `StreamingResponse` — no SSE stream cleanup should be involved, yet interrupt fires | high | NEW — high |

---

## Recommended Next Phase

**R139C_INTERRUPT_CAUSAL_CHAIN_TEST** (Pressure: XXL)

Reason: R139C must test: disable `asyncio.create_task` — await `run_agent` directly instead — to see if interrupt still fires. If interrupt disappears when `run_agent` is awaited inline (not background), Cause A (TestClient lifecycle) is confirmed. If interrupt still fires, the interrupt source is in the graph/middleware/checkpointer layer.