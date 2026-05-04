# R241-1C Queue / Sandbox TruthEvent Projection Report

Generated: 2026-04-24  
Root: `E:\OpenClaw-Base\deerflow`  
Scope: read-only queue/sandbox truth diagnostics.

## 1. 修改文件清单

Added:

- `backend/app/m11/queue_sandbox_truth_projection.py`
- `backend/app/m11/test_queue_sandbox_truth_projection.py`
- `migration_reports/foundation_audit/R241-1C_QUEUE_SANDBOX_TRUTH_PROJECTION_REPORT.md`
- `migration_reports/foundation_audit/R241-1C_QUEUE_SANDBOX_TRUTH_PROJECTION_RUNTIME_SAMPLE.json`

Not modified:

- `backend/app/m11/queue_consumer.py`
- `backend/app/m11/sandbox_executor.py`
- `backend/app/m11/governance_state.json`
- `experiment_queue.json`

## 2. 新增只读 projection 函数

New module: `backend/app/m11/queue_sandbox_truth_projection.py`

Functions:

- `load_experiment_queue_snapshot(queue_path: str | None = None) -> dict`
- `project_sandbox_outcomes(limit: int = 100) -> dict`
- `get_sandbox_execution_success_candidates(limit: int = 100) -> dict`
- `correlate_queue_with_sandbox_truth(queue_path: str | None = None, limit: int = 100) -> dict`
- `generate_queue_sandbox_projection_report(output_path: str | None = None) -> dict`

The module reuses:

- `governance_bridge.project_truth_state`
- `governance_bridge.project_recent_outcomes`
- `governance_bridge.get_success_rate_candidates`

It does not copy Truth/State mapping logic.

## 3. Queue snapshot 只读验证

Default queue path used by the requested contract:

```text
C:\Users\win\.deerflow\upgrade-center\state\experiment_queue.json
```

Runtime diagnostic result:

```text
exists=False
task_count=0
status_counts={}
with_verify_script_count=0
warning=queue_missing:C:\Users\win\.deerflow\upgrade-center\state\experiment_queue.json
```

This is a diagnostic warning only. The module does not create or modify the queue file.

## 4. Sandbox truth projection 验证

Read-only projection over current governance outcomes:

```text
sandbox_records_count=17
execution_truth_count=17
actual_pass_count=5
actual_fail_count=12
predicted_present_count=10
warnings=[]
```

Only `execution_truth / actual_outcome` events are counted for pass/fail. Governance approvals, observations, asset scores, and predicted outcomes are not counted as sandbox execution truth.

## 5. execution_success_rate candidate 验证

`get_sandbox_execution_success_candidates(limit=100)` result:

```text
eligible_count=17
pass_count=5
fail_count=12
simple_success_rate=0.29411764705882354
```

The value is explicitly labeled as raw execution truth rate, not user-goal success rate.

Observed exclusions included:

- `not_execution_success_rate:approval_decision`
- `not_execution_success_rate:observation_signal`
- `unknown_mapping:upgrade_center_execution`
- `unknown_mapping:upgrade_center_summary`

## 6. queue ↔ sandbox truth correlation 验证

Correlation result with the requested default queue path:

```text
queue_task_count=0
queue_status_counts={}
sandbox_truth_count=17
sandbox_predicted_present_count=10
sandbox_truth_with_provenance_count=17
queue_verify_without_sandbox_truth_count=0
sandbox_truth_without_queue_task_count=17
warnings=[
  queue_missing:C:\Users\win\.deerflow\upgrade-center\state\experiment_queue.json,
  sandbox_truth_without_queue_task:17
]
```

Because the default queue path is missing, sandbox truths cannot be correlated to queue tasks in this runtime sample. This is a diagnostic mismatch, not a failure of projection.

## 7. 测试结果

RootGuard:

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile:

- `python -m py_compile backend/app/m11/truth_state_contract.py backend/app/m11/governance_bridge.py backend/app/m11/queue_sandbox_truth_projection.py`: PASS

Truth/State + governance + queue/sandbox tests:

- `python -m pytest backend/app/m11/test_truth_state_contract.py backend/app/m11/test_governance_truth_projection.py backend/app/m11/test_queue_sandbox_truth_projection.py -v`: PASS, 33 passed

Existing smoke:

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: PASS, 11 passed

## 8. 是否修改 experiment_queue / governance_state

No.

- `experiment_queue.json` was not modified.
- `governance_state.json` was not modified.
- Tests use `tmp_path` and `monkeypatch`.
- The only generated JSON is the audit sample under `migration_reports/foundation_audit`.

## 9. 是否改变 queue_consumer / sandbox 执行逻辑

No.

No changes were made to:

- `queue_consumer.py`
- `sandbox_executor.py`
- `verify_exit_code -> actual` mapping
- `write_governance_outcome()`
- sandbox verify / rollback logic

## 10. 当前剩余断点

- Default requested queue path under `C:\Users\win\.deerflow` is missing in this environment, so queue ↔ sandbox correlation reports mismatch warnings.
- The module computes raw execution truth rate only; it does not compute user-goal success rate.
- Queue/Sandbox projection is diagnostic-only and not yet surfaced through a CLI/API endpoint.

## 11. 下一步建议

Proceed to R241-2 Memory Layer Contract Wrapper:

- Keep Truth/State projection read-only.
- Define MemoryLayerContract before touching runtime memory.
- Preserve the rule that observations, approvals, and asset quality signals must not leak into execution success rate.

## Final Judgment

A. R241-1C 成功，可进入 R241-2 Memory Layer Contract Wrapper。
