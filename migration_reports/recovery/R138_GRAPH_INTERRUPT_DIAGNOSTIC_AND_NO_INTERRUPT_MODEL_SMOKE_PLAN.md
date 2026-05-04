# R138: Graph Interrupt Diagnostic + No-Interrupt Model Smoke Plan

## Status: COMPLETED

## Preceded By: R137
## Proceeding To: R139_NO_INTERRUPT_ONE_MODEL_SMOKE (execution authorization required)

## Pressure: XXL

---

## Summary

R138 performed a 9-lane read-only diagnostic to map the interrupt source in R137 and plan R139. Key finding: **The interrupt in R137 fired even though `interrupt_before_nodes` was NOT set** (worker.py:201 check fails when `interrupt_before=None`). This means the interrupt source is NOT in the explicit interrupt node assignment path.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| R137 actual status | passed_with_interrupted |
| R137 actual outcome | Outcome D |
| R137 worker path | exercised correctly |
| R137 model API called | false |
| Pressure for R138 | XXL |
| Rationale | Read-only scan only |

---

## LANE 1: R137 Outcome Reclassification

| Item | Value |
|---|---|
| R137 actual result | passed_with_interrupted |
| Reclassification | partial_mainline_success |
| Lane 8 classification | Outcome D — graph-level interrupt triggered; worker path exercised correctly |
| Reclassification confidence | high |

**Key evidence:** run_manager.set_status(running) succeeded at 11:19:44, set_status(interrupted) succeeded at 11:19:53, no CancelledError, no error message in record.error.

---

## LANE 2: Interrupt Source Mapping

### interrupt_before_sources

| File | Lines | Code | Condition |
|---|---|---|---|
| worker.py | 201-202 | `if interrupt_before: agent.interrupt_before_nodes = interrupt_before` | Only set when truthy; default=None |
| services.py | 283-284 | `interrupt_before=body.interrupt_before, ...` | Passes through from RunCreateRequest |
| thread_runs.py | 46-47 | `interrupt_before: list[str] \| Literal["*"] \| None = Field(default=None)` | Request field defaults to None |
| langchain.agents.factory | 664 | `interrupt_before: list[str] \| None = None` | create_agent() parameter defaults to None |

### interrupt_after_sources

| File | Lines | Code | Condition |
|---|---|---|---|
| worker.py | 203-204 | `if interrupt_after: agent.interrupt_after_nodes = interrupt_after` | Only set when truthy; default=None |
| services.py | 283-284 | `interrupt_after=body.interrupt_after` | Passes through from RunCreateRequest |
| thread_runs.py | 46-47 | `interrupt_after: list[str] \| Literal["*"] \| None = Field(default=None)` | Request field defaults to None |
| langchain.agents.factory | 665 | `interrupt_after: list[str] \| None = None` | create_agent() parameter defaults to None |

### langchain.agents factory default interrupt behavior

- **File:** `langchain/agents/factory.py:1596-1604`
- **Finding:** `interrupt_before` and `interrupt_after` passed to `graph.compile()` — LangGraph sets `interrupt_before_nodes`/`interrupt_after_nodes` on the CompiledStateGraph at compile time
- **Conclusion:** `create_agent()` does NOT set any default interrupt nodes when both are None

### lead_agent/agent.py interrupt check

- **File:** `agents/lead_agent/agent.py`
- **grep result:** No matches for `interrupt_before_nodes|interrupt_after_nodes` in entire agents directory
- **Conclusion:** `make_lead_agent` does NOT set `interrupt_before_nodes` or `interrupt_after_nodes` anywhere

### LANE 2 Conclusion

**`interrupt_before` and `interrupt_after` are NOT set by default anywhere in the chain.** They must be explicitly passed via POST /runs body. In R137, `interrupt_before=None` from the request body → worker.py:201 check `if interrupt_before:` → **False** → `interrupt_before_nodes` was NOT set on the agent.

---

## LANE 3: Request Payload Influence Check

### Question

Can POST /runs payload disable interrupt via explicit `interrupt_before: []` / `interrupt_after: []`?

### Findings

| Fact | Implication |
|---|---|
| worker.py:201-204 sets interrupt nodes ONLY when truthy: `if interrupt_before:` | Passing `interrupt_before=[]` (empty list) is falsy → `agent.interrupt_before_nodes` would NOT be set |
| `LangGraph.graph.compile(interrupt_before=None)` → graph has no interrupt nodes | Even if empty list bypassed worker check, `compile(None)` would not add interrupt nodes |
| langchain.agents.factory:1599-1600 passes `interrupt_before` to `graph.compile()` | `compile()` receives `None`, graph has no built-in interrupts |
| `interrupt_before_nodes` is a writable attribute set at runtime in worker.py:202 | Runtime assignment is independent of what `create_agent()` set at compile time |

### Conclusion

Explicit `interrupt_before=[]` / `interrupt_after=[]` in POST /runs body **would disable interrupts at the worker level** (empty list is falsy → assignment skipped). However, the interrupt in R137 was NOT caused by `interrupt_before_nodes` — since `interrupt_before=None` meant `interrupt_before_nodes` was never set. The interrupt source is elsewhere.

---

## LANE 4: Worker/Graph Execution Boundary

### Code Path Analysis

**worker.py:262-281** — Normal astream completion:
```python
if record.abort_event.is_set():
    ... → interrupted
else:
    await run_manager.set_status(run_id, RunStatus.success)
```
- Normal astream completion → success. abort_event NOT set → success path.

**worker.py:283-301** — `asyncio.CancelledError`:
```python
except asyncio.CancelledError:
    record.abort_action ...
    record.abort_event.set()
    → interrupted
```
- Task cancellation path. No CancelledError was logged in R137.

**worker.py:303-306** — Exception:
```python
except Exception as exc:
    → error status
```
- No exception in R137.

### abort_event Analysis

| Source | Mechanism |
|---|---|
| manager.py:159-160 | `cancel()` sets `abort_event` and `abort_action` |
| manager.py:201-208 | `create_or_reject()` with `multitask_strategy` in `(interrupt, rollback)` sets `abort_event` on inflight runs |

**Conclusion:** `abort_event` is set by EXTERNAL calls to `cancel()` or by `create_or_reject()` clearing inflight runs. R137 did NOT call `cancel()`.

### Interrupt Hypothesis

The interrupt is NOT caused by `interrupt_before_nodes` (was None/not set). The 9-second elapsed time between running and interrupted is consistent with a LangGraph checkpoint-based interrupt firing at the first node.

**Possible sources:**
1. LangGraph checkpointer interrupt state from prior execution (unlikely — new run_id)
2. LangGraph's own internal interrupt for empty/initial graph input
3. Something in the middleware chain triggering an interrupt
4. The abort_event being set by create_or_reject during inflight cleanup

### Leading Hypothesis

**The interrupt must originate from LangGraph's internal behavior**, not from the explicit `interrupt_before_nodes` assignment in worker.py. This needs R139 with `interrupt_before=[]` to confirm.

---

## LANE 5: Resume Path Feasibility

### Question: Is there a POST /runs/{run_id}/resume endpoint?

**Answer: NO.** Resume is NOT a single `/runs/{run_id}/resume` endpoint.

### Endpoints in thread_runs.py

| Endpoint | Purpose |
|---|---|
| `POST /api/threads/{thread_id}/runs` | Create run |
| `GET /api/threads/{thread_id}/runs/{run_id}` | Status |
| `POST /api/threads/{thread_id}/runs/{run_id}/cancel` | Cancel |
| `GET /api/threads/{thread_id}/runs/{run_id}/stream` | SSE stream |

### Actual Resume Mechanism (threads.py:459-462)

| Endpoint | Purpose |
|---|---|
| `POST /api/threads/{thread_id}/state` | Update thread state (human-in-the-loop resume or title rename) |

**Resume pattern (LangGraph Platform):**
1. `POST /threads/{thread_id}/state` with `values` updates the checkpoint
2. Next `POST /runs` with `checkpoint_id` parameter references that checkpoint

---

## LANE 6: R139 No-Interrupt One-Model Smoke Plan

### Objective

Verify that POST /runs with `interrupt_before=[]` / `interrupt_after=[]` produces a clean success outcome (no interrupt, model API called, run completes successfully).

### Constraints

| Constraint | Value |
|---|---|
| code_modified | false |
| db_written | false |
| jsonl_written | false |
| gateway_started | false |
| model_api_called | true |
| mcp_runtime_called | false |
| tool_call_executed | false |
| push_executed | false |
| merge_executed | false |
| interrupt_before_nodes | Must be explicitly disabled via `interrupt_before=[]` in request body |

### Pressure: XXL

### Expected Outcome: Outcome A — clean success

### Test Steps

1. **LANE 0:** Pressure check (XXL, R138→R139)
2. **LANE 1:** Preflight — MINIMAX_API_KEY, workspace clean, health_200
3. **LANE 2:** Model injection — same as R137
4. **LANE 3:** Thread create — POST /api/threads
5. **LANE 4:** POST /runs with `interrupt_before=[]` and `interrupt_after=[]`
6. **LANE 5:** Poll run status until completed/success (not interrupted)
7. **LANE 6:** Verify model API called exactly once
8. **LANE 7:** Verify no tool calls, no MCP, no DB/JSONL writes
9. **LANE 8:** Result classification — expect Outcome A (clean success)

### Key Differences from R137

| Aspect | R137 | R139 |
|---|---|---|
| interrupt_before | `None` | `[]` (empty list — falsy, disables assignment) |
| interrupt_after | `None` | `[]` (empty list — falsy, disables assignment) |
| Expected status | interrupted | success |
| Expected model API call | false | true (exactly 1) |

---

## LANE 7: Tool-Enabled Readiness Gate

| Check | Result |
|---|---|
| R137 model API call count | 0 |
| R137 interrupt behavior | interrupt fires WITHOUT model API call |
| interrupt_before_nodes=None in worker.py | confirmed — worker.py:201 check fails |
| Tool-enabled smoke readiness | **BLOCKED** — need to understand interrupt source first |

### Conclusion

R139 (no-interrupt smoke) must run before R138_TOOL_ENABLED_SMOKE. The unexpected interrupt in R137 (fires with `interrupt_before_nodes=None`) must be characterized first. If R139 with `interrupt_before=[]` still gets interrupted, the interrupt source is in the graph itself, not the `interrupt_before_nodes` assignment.

---

## LANE 8: Unknown Registry

| Registry ID | Description | Priority |
|---|---|---|
| U-interrupt-source-unknown | `interrupt_before_nodes=None` yet `status=interrupted` fires at worker.py:279 in ~9s without model API call | critical |
| U-resume-mechanism | Resume is NOT a `/runs/{run_id}/resume` single endpoint — uses `POST /threads/{thread_id}/state` + `checkpoint_id` parameter pattern | informational |

---

## CRITICAL FINDING

> **The interrupt in R137 fired even though `interrupt_before_nodes` was NOT set** (worker.py:201 check fails when `interrupt_before=None`). This means the interrupt source is NOT in the explicit interrupt node assignment path. The interrupt must originate from:
> 1. LangGraph's internal behavior with the empty graph input
> 2. Middleware chain
> 3. The checkpointer
>
> **R139 with `interrupt_before=[]` must run to determine if the interrupt persists without explicit interrupt nodes.**

---

## Recommended Next Phase

**R139_NO_INTERRUPT_ONE_MODEL_SMOKE** (Pressure: XXL)

Reason: R139 must characterize whether the interrupt persists when `interrupt_before=[]` is explicitly passed. If R139 succeeds (clean success, model API called), the interrupt in R137 was caused by `None` being passed for interrupt parameters. If R139 still gets interrupted, the interrupt source is in the graph/middleware/checkpointer layer, not the explicit interrupt node assignment.

---

## Unknown Registry

| ID | Description | Evidence | Priority |
|---|---|---|---|
| U-interrupt-source-unknown | interrupt_before_nodes=None yet status=interrupted fires at worker.py:279 in ~9s without model API call | R137 timeline: running@11:19:44, interrupted@11:19:53, no API call, no CancelledError, no error | critical |
| U-resume-mechanism | Resume is NOT a /runs/{run_id}/resume single endpoint | thread_runs.py has no resume endpoint; threads.py:462 has update_thread_state | informational |