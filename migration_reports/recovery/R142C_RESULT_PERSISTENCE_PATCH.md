# R142C: Result Persistence Patch

## Status: PASSED ✅

## Preceded By: R142B_RESULT_PERSISTENCE_AND_EVENT_MODEL_DESIGN
## Proceeding To: R143_INTERNAL_TOOL_CALL_OBSERVABILITY_PLAN

## Pressure: XXL

---

## Summary

R142C executes the Option A patch from R142B. Three files modified — RunRecord dataclass (+result), RunResponse model (+result), worker.py finally block (captures serialize_channel_values). Smoke test confirms: GET /runs/{run_id} returns non-null result with 2 messages.

---

## LANE 0: Pre-flight

| Check | Result |
|---|---|
| minimax_api_key_present | True |
| workspace_clean | True |
| preflight_passed | True |

---

## LANE 1: Scope Gate — Patch Target Confirmation

| Check | Result |
|---|---|
| RunRecord has result field | True |
| RunResponse has result field | True |
| _record_to_response copies result | True |
| worker.py has result capture | True |
| scope_gate_passed | True |

---

## LANE 2: Thread Baseline

| Check | Result |
|---|---|
| POST /api/threads | 200 |
| thread_baseline_passed | True |

---

## LANE 3: Inline No-tool Run

| Check | Result |
|---|---|
| run_id | (unique) |
| record_created | True |
| worker_completed | True |
| final_status | success |
| final_error | None |

---

## LANE 4: GET /runs/{run_id} — Result Field Verification

| Check | Result |
|---|---|
| GET status | 200 |
| has result field | True |
| result is non-null | True |
| result.messages exists | True |
| result.messages non-empty | True |
| result.messages count | 2 |

---

## LANE 5: RunStore Record — Result Field Check

| Check | Result |
|---|---|
| RunRecord has result attr | True |
| record.result is non-null | True |
| record.result keys | ['messages', 'thread_data', 'title'] |

---

## LANE 6: Regression — Background Default Unchanged

| Check | Result |
|---|---|
| default_run_in_background | True (preserved) |
| inline_execution_works | True |
| production_path_unchanged | True |

---

## LANE 7: Result Classification

**Classification: PASSED ✅**

- run_status: success
- response_has_result: True
- result_messages_non_empty: True

---

## Patch Files

1. `packages/harness/deerflow/runtime/runs/manager.py`
   - RunRecord dataclass: `+result: dict | None = None`
   - update_run_completion: now propagates kwargs to in-memory RunRecord AND backing store; skips `status` key to preserve RunStatus enum

2. `app/gateway/routers/thread_runs.py`
   - RunResponse model: `+result: dict[str, Any] | None = None`
   - `_record_to_response()`: `+result=record.result`

3. `packages/harness/deerflow/runtime/runs/worker.py`
   - finally block: captures `serialize_channel_values(channel_values)` from checkpointer as `result_snapshot`, passes via `update_run_completion(..., result=result_snapshot)`

---

## Root Cause Fixes

| Phase | Finding | Fix |
|---|---|---|
| R142 | GET /runs/{run_id} has no result field | RunResponse +result, _record_to_response copies record.result |
| R142 | RunStore record has no result field | RunRecord +result field |
| R142 | worker.py doesn't capture final state | serialize_channel_values captured in finally block |
| R142C bug | status string overwriting RunStatus enum | update_run_completion skips 'status' key |
| R142C bug | result not propagating to RunRecord | update_run_completion writes to in-memory record via setattr |

---

## Safety Verification

| Constraint | Result |
|---|---|
| No code modified outside patch files | ✅ |
| Production default run_in_background=True | ✅ preserved |
| No DB schema changes | ✅ additive only |
| Safety violations | **None** |

---

## R142C_RESULT_PERSISTENCE_PATCH_DONE

```
status=passed
classification=passed
run_status=success
result_field_present=true
result_non_null=true
result_messages_count=2
production_default_preserved=true
patch_files=[manager.py, thread_runs.py, worker.py]
commit=b3c0670
recommended_next_phase=R143_INTERNAL_TOOL_CALL_OBSERVABILITY_PLAN
```