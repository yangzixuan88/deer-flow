# R241-1B Governance Read-only Projection Report

Generated: 2026-04-24  
Root: `E:\OpenClaw-Base\deerflow`  
Scope: read-only Truth / State projection helper integration.

## 1. 修改文件清单

Modified:

- `backend/app/m11/governance_bridge.py`

Added:

- `backend/app/m11/test_governance_truth_projection.py`
- `migration_reports/foundation_audit/R241-1B_GOVERNANCE_READONLY_PROJECTION_REPORT.md`

Unchanged by design:

- `backend/app/m11/governance_state.json`
- `record_outcome()` write structure
- Upgrade Center / Sandbox / RTCM / Asset / Memory / Prompt main logic

## 2. 新增 helper 函数

Added module-level helpers in `governance_bridge.py`:

- `project_truth_state(record: dict) -> dict`
- `project_recent_outcomes(limit: int = 20, outcome_type: str | None = None) -> dict`
- `get_success_rate_candidates(metric_scope: str = "execution_success_rate", limit: int = 100) -> dict`

These helpers reuse R241-1A functions from `truth_state_contract.py`:

- `map_legacy_outcome_to_truth_events`
- `map_legacy_outcome_to_state_events`
- `summarize_outcome_contract`
- `is_success_rate_eligible`

The helpers are module-level functions, not `GovernanceBridge` methods, to avoid changing bridge instance lifecycle or `_save_state()` behavior.

## 3. Projection 结果示例

Read-only sample against current `governance_state.json`:

```text
project_recent_outcomes(limit=5)
total_scanned=5
projected_count=5
truth_events_count=10
state_events_count=5
warnings=0
```

```text
get_success_rate_candidates("execution_success_rate", limit=20)
eligible_count=13
ineligible_count=18
excluded_reasons={
  "not_execution_truth:governance_truth": 8,
  "not_execution_success_type:predicted_outcome": 10
}
```

This confirms governance and predicted signals are projected but excluded from execution success-rate candidates.

## 4. success_rate candidate 筛选规则

Supported metric scopes:

- `execution_success_rate`
- `tool_success_rate`
- `asset_quality_score`
- `rtcm_decision_quality`

For `execution_success_rate`, eligible TruthEvents must satisfy:

- `truth_track == "execution_truth"`
- `truth_type in {"actual_outcome", "verification_result"}`

Excluded from `execution_success_rate`:

- `observation_signal`
- `approval_decision`
- `governance_truth`
- `asset_quality_signal`
- `memory_update_signal`
- `prompt_optimization_signal`
- `rtcm_truth`

## 5. 测试结果

RootGuard:

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile:

- `python -m py_compile backend/app/m11/truth_state_contract.py backend/app/m11/governance_bridge.py`: PASS

Truth/State + governance projection tests:

- `python -m pytest backend/app/m11/test_truth_state_contract.py backend/app/m11/test_governance_truth_projection.py -v`: PASS, 23 passed

Existing smoke:

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: PASS, 11 passed

## 6. 是否修改 governance_state

否。

`project_recent_outcomes()` and `get_success_rate_candidates()` read `_STATE_FILE` only. Tests use `tmp_path` and `monkeypatch` for temporary state files and do not write the real `governance_state.json`.

## 7. 是否改变 record_outcome()

否。

`record_outcome()` function body, signature, outcome record field names, save conditions, and actual/predicted semantics were not changed.

## 8. 是否改变业务执行逻辑

否。

No changes were made to:

- queue consumer actual mapping
- Upgrade Center actual/predicted logic
- Sandbox verify_exit_code behavior
- RTCM state machine
- Asset registry / binding report
- Memory / Prompt main logic
- Mode Orchestrator

## 9. 当前剩余断点

- Projection is now available from `governance_bridge.py`, but no caller has been wired to consume it yet.
- Projection results are not persisted, by design.
- Success-rate candidates are filtered but final metric computation is not implemented in this round.
- Tool/memory/prompt-specific outcome mappings remain future extension points.

## 10. 下一步建议

Proceed to R241-1C Queue / Sandbox TruthEvent projection:

- Add read-only projection at queue/sandbox reporting boundary.
- Keep queue/sandbox writes unchanged.
- Use projected TruthEvents for reporting or diagnostics only.
- Continue excluding observation and governance approval signals from execution success-rate inputs.

## Final Judgment

A. R241-1B 成功，可进入 R241-1C Queue / Sandbox TruthEvent 投影。
