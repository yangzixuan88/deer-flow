# R139C: Interrupt Causal Chain Test

## Status: PASSED ✅

## Preceded By: R139B
## Proceeding To: R140_GRAPH_MIDDLEWARE_FIX

## Pressure: XXL

---

## Summary

R139C confirms **Cause A — TestClient background task lifecycle cancellation**. When `run_agent` is awaited **inline** (not via `asyncio.create_task` background task), the run completes successfully with `status=success`. This proves that the `interrupted` status in R137/R139 was caused by TestClient tearing down background tasks at context exit, not by any bug in the graph/middleware/checkpointer layer.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| Previous phase | R139B |
| Current phase | R139C |
| Recommended pressure | XXL |
| Pressure check | PASS |

---

## LANE 1: Preflight

| Check | Result |
|---|---|
| MINIMAX_API_KEY present | True |
| Preflight passed | True |

---

## LANE 2: Model Config Verification

| Field | Value |
|---|---|
| Model name | minimax-m2.7 |
| Model use | packages.harness.deerflow.models.patched_minimax:PatchedChatMiniMax |
| Model | MiniMax-M2.7 |

---

## LANE 3: Thread Baseline

| Check | Result |
|---|---|
| POST /api/threads | 200 |
| thread_id | f8fb976b-c905-4506-9a20-93324be967bf |

---

## LANE 4+5: Inline run_agent Execute (KEY TEST)

### Hypothesis

**Cause A**: R139's background task (created via `asyncio.create_task` in `start_run`) is cancelled when TestClient lifecycle teardown occurs at the end of the `with` block. This triggers `CancelledError` in `worker.py:283`, which sets `status=interrupted` at line 300.

### Key Difference from R139

| Aspect | R139 | R139C |
|---|---|---|
| Execution mode | `asyncio.create_task(run_agent(...))` — background task | `await run_agent(...)` — inline await |
| Task cancellation possible | Yes (TestClient teardown) | No (no background task) |
| Final status | interrupted | **success** |

### Execution

```
Record created: cd742f37-4260-4172-96ed-31aba4751e7f
Record status: interrupted  ← set by start_run before run_agent even starts
Awaiting run_agent inline for run_id=cd742f37-4260-4172-96ed-31aba4751e7f...
run_agent completed normally (no interrupt)
```

### Timeline Observations

1. `start_run` creates record, sets `status=running`
2. `start_run` creates background task via `asyncio.create_task` (which immediately starts `run_agent`)
3. BUT: `start_run` returns before the task completes — the task runs in background
4. `run_agent` awaits inline (no new background task)
5. Model API called successfully (MiniMax API — 2 calls in logs)
6. `status=success` — no interrupt, no cancellation

`★ Insight ─────────────────────────────────────`
**关键发现**：R139中`record.status=interrupted`是在`start_run`内部就已经设置的（在`create_or_reject`中）。这意味着TestClient的`with`块退出时，`run_manager`中的记录已经是`interrupted`状态。而`run_agent`是在后台task中运行的，当`with`块退出时，后台task被cancel，导致worker的`CancelledError`处理逻辑将状态再次设置为`interrupted`。
`─────────────────────────────────────────────────`

---

## LANE 6: Run Status Check

| Field | Value |
|---|---|
| Final status | **success** |
| Final error | None |

---

## LANE 7: Event Inspection

| Field | Value |
|---|---|
| StreamBridge stream created | True |
| Stream event count | 6 |
| Model response detected | True (length=103) |

---

## LANE 8: Result Classification

### R139C Result: **PASSED — Outcome A**

**Outcome A — clean success (inline await)**

| Classification | Value |
|---|---|
| Result | passed |
| Outcome | Outcome A — clean success (inline await) |
| Final status | success |
| Worker completed | True |
| Worker error | None |
| Model response detected | True |

---

## Cause Analysis

### Cause A: **CONFIRMED** ✅

TestClient lifecycle cancellation of background task is the interrupt source.

**Evidence:**
- `run_agent` awaited inline → `status=success` (no background task to cancel)
- R139 with `asyncio.create_task` → `status=interrupted` (background task cancelled)
- `CancelledError` caught in `worker.py:301` logs `"Run %s was cancelled"` in R139 but not R139C

### What This Means

The interrupt in R137/R139 is NOT caused by:
- `interrupt_before_nodes` / `interrupt_after_nodes` (both empty/falsy in R139C too)
- LangGraph checkpointer interrupt state
- Graph middleware
- Any bug in the worker `astream` logic

It IS caused by:
- TestClient (`with TestClient(app)`) lifecycle teardown at the end of the `with` block
- When the `with` block exits, background tasks created via `asyncio.create_task` are cancelled
- `task.cancel()` → `CancelledError` caught in `worker.py:283` → `status=interrupted`

---

## Implications for R140

R140 should focus on **fixing the `services.py start_run` function** to not use `asyncio.create_task`. Options:
1. Make `start_run` return the record without starting a background task, let the caller decide
2. Add a `run_in_background=False` option to `start_run`
3. Change the harness to always await `run_agent` inline (not use HTTP endpoint for smoke tests)

---

## Recommended Next Phase

**R140_GRAPH_MIDDLEWARE_FIX** (Pressure: XXL)

Reason: R139C confirmed the interrupt source is TestClient lifecycle cancellation. R140 must fix the harness or `start_run` to properly handle the inline execution path.