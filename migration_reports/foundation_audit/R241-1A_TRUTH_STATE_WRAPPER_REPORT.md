# R241-1A Truth / State Wrapper Report

Generated: 2026-04-24  
Root: `E:\OpenClaw-Base\deerflow`  
Scope: minimal non-destructive TruthEvent / StateEvent wrapper implementation.

## 1. 修改文件清单

新增文件：

- `backend/app/m11/truth_state_contract.py`
- `backend/app/m11/test_truth_state_contract.py`
- `migration_reports/foundation_audit/R241-1A_TRUTH_STATE_WRAPPER_REPORT.md`

未修改：

- `backend/app/m11/governance_bridge.py`
- `backend/app/m11/governance_state.json`
- Upgrade Center / Sandbox / RTCM / Asset / Memory / Prompt 主逻辑

## 2. TruthEvent / StateEvent 字段

`TruthEvent` 字段：

- `truth_event_id`
- `source_system`
- `truth_type`
- `truth_track`
- `subject_type`
- `subject_id`
- `predicted_value`
- `actual_value`
- `confidence`
- `evidence_refs`
- `producer`
- `created_at`
- `context_id`
- `request_id`
- `governance_trace_id`
- `related_state_id`
- `legacy_outcome_type`
- `legacy_record_ref`

`StateEvent` 字段：

- `state_event_id`
- `source_system`
- `state_domain`
- `subject_type`
- `subject_id`
- `previous_state`
- `new_state`
- `transition_reason`
- `actor_system`
- `created_at`
- `context_id`
- `request_id`
- `related_truth_event_id`
- `artifact_refs`
- `legacy_outcome_type`
- `legacy_record_ref`

## 3. Legacy outcome 映射规则

### `sandbox_execution_result`

- `actual=0.0/1.0` maps to `truth_type=actual_outcome`, `truth_track=execution_truth`.
- `predicted` maps to `truth_type=predicted_outcome`.
- `verify_exit_code`, `rollback_invoked`, and execution artifact paths are preserved in evidence/artifact refs.
- State projection maps to `state_domain=sandbox_execution`, with `completed` if `verify_exit_code == 0`, otherwise `failed`.

### `upgrade_center_execution_result`

- `predicted` maps to `truth_type=predicted_outcome`, `truth_track=governance_truth`.
- `actual=1.0` maps to `truth_type=approval_decision`, `truth_track=governance_truth`.
- `filter_result=observation_pool` with `actual=0.5` maps to `truth_type=observation_signal`, `truth_track=observation_truth`.
- It is explicitly not mapped as `execution_truth`.

### `upgrade_center_approval`

- Maps to `truth_type=approval_decision`, `truth_track=governance_truth`.
- `predicted` also produces a predicted outcome projection when present.

### `asset_promotion`

- Maps to `truth_type=asset_quality_signal`, `truth_track=asset_truth`.
- Asset score or quality score is preserved as the signal value.
- Asset score does not enter execution success rate.

### RTCM / roundtable outcomes

- `rtcm`, `roundtable`, `final_report`, `signoff`, or `verdict` signals map to `truth_type=rtcm_verdict`, `truth_track=rtcm_truth`.
- State projection maps to `state_domain=rtcm_session`.

### Unknown outcomes

- Unknown `outcome_type` returns empty truth/state lists.
- No exception is raised.
- `summarize_outcome_contract()` records an `unknown_mapping:*` warning.

## 4. success_rate eligibility 规则

`execution_success_rate` allows only:

- `truth_track=execution_truth`
- `truth_type in {actual_outcome, verification_result}`

Explicitly excluded:

- `observation_signal`
- `approval_decision`
- `governance_truth`
- `asset_quality_signal`
- `memory_update_signal`
- `prompt_optimization_signal`
- `rtcm_truth`

Other metric scopes:

- `tool_success_rate`: only `tool_truth / tool_execution_result`
- `asset_quality_score`: only `asset_truth / asset_quality_signal`
- `rtcm_decision_quality`: only `rtcm_truth / rtcm_verdict`

## 5. 测试结果

RootGuard:

- `python scripts\root_guard.py`: PASS, `ROOT_OK`
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS, `ROOT_OK`

Compile:

- `python -m py_compile backend/app/m11/truth_state_contract.py`: PASS

New wrapper tests:

- `python -m pytest backend/app/m11/test_truth_state_contract.py -v`: PASS, 13 passed

Existing smoke test:

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: PASS, 11 passed

## 6. 是否修改 governance_state

否。

`governance_state.json` was not read/write-mutated by the wrapper. The new module is projection-only.

## 7. 是否改变业务执行逻辑

否。

No changes were made to:

- `record_outcome()`
- queue consumer actual/predicted writes
- Upgrade Center actual/predicted logic
- Sandbox verify_exit_code mapping
- RTCM state machine
- Asset registry / binding report
- Memory / Prompt logic

## 8. 当前剩余断点

- This wrapper is not yet exposed through `governance_bridge.py`.
- No historical `outcome_records` migration was performed.
- Legacy records still keep original fields; typed projection is computed on demand.
- `tool_execution_result`, `memory_update_signal`, and `prompt_optimization_signal` enum support exists for eligibility, but this round did not implement new legacy mappings for outcomes not requested by R241-1A.

## 9. 下一步建议

Proceed to R241-1B only as read-only projection integration:

- Add a helper such as `project_truth_state(record: dict) -> dict` in `governance_bridge.py`, if confirmed safe.
- Keep `record_outcome()` write structure unchanged.
- Do not mutate existing governance history.
- Add read-only reporting over recent outcome records using `summarize_outcome_contract()`.

## Final Judgment

A. R241-1A 成功，可进入 R241-1B governance read-only projection 接入。
