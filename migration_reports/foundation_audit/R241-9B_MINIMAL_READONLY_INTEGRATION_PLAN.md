# R241-9B Minimal Read-only Integration Plan

## 1. 修改文件清单

- `backend/app/foundation/read_only_integration_plan.py`
- `backend/app/foundation/test_read_only_integration_plan.py`
- `migration_reports/foundation_audit/R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.json`
- `migration_reports/foundation_audit/R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.md`

## 2. Source Matrix Summary

- source_matrix_ref: `C:\Users\win\AppData\Local\Temp\pytest-of-win\pytest-631\test_no_action_queue_written1\matrix.json`
- approved_surfaces: 2
- excluded_surfaces: 1
- blocked_surfaces: 1

## 3. CLI Command Specs

- `foundation diagnose truth-state` -> backend/app/m11/truth_state_contract.py; backend/app/m11/governance_bridge.py / permission=read_only_allowed
- `foundation diagnose queue-sandbox` -> backend/app/m11/queue_sandbox_truth_projection.py / permission=read_only_allowed
- `foundation diagnose memory` -> backend/app/memory/memory_projection.py / permission=read_only_allowed
- `foundation diagnose asset` -> backend/app/asset/asset_projection.py / permission=read_only_allowed
- `foundation diagnose prompt` -> backend/app/prompt/prompt_projection.py / permission=read_only_allowed
- `foundation diagnose rtcm` -> backend/app/rtcm/rtcm_runtime_projection.py / permission=read_only_allowed
- `foundation diagnose nightly` -> backend/app/nightly/foundation_health_review.py / permission=read_only_allowed
- `foundation diagnose feishu-summary` -> backend/app/nightly/foundation_health_summary.py / permission=dry_run_only
- `foundation diagnose all` -> backend/app/nightly/foundation_health_review.py; backend/app/nightly/foundation_health_summary.py / permission=read_only_allowed

## 4. API Endpoint Specs

- `GET /foundation/diagnostics/truth-state` disabled_by_default=True writes_runtime=False
- `GET /foundation/diagnostics/queue-sandbox` disabled_by_default=True writes_runtime=False
- `GET /foundation/diagnostics/memory` disabled_by_default=True writes_runtime=False
- `GET /foundation/diagnostics/asset` disabled_by_default=True writes_runtime=False
- `GET /foundation/diagnostics/prompt` disabled_by_default=True writes_runtime=False
- `GET /foundation/diagnostics/rtcm` disabled_by_default=True writes_runtime=False
- `GET /foundation/diagnostics/nightly` disabled_by_default=True writes_runtime=False
- `GET /foundation/diagnostics/feishu-summary` disabled_by_default=True writes_runtime=False
- `GET /foundation/diagnostics/all` disabled_by_default=True writes_runtime=False

## 5. Validation

- valid: True
- warnings: ['queue_path_mismatch_unresolved']
- errors: []

## 6. Implementation Sequence

- 1. CLI internal helpers only
- 2. CLI report output to migration_reports
- 3. API endpoint stubs disabled by default
- 4. API auth/rate-limit policy
- 5. Gateway sidecar router / not main run path
- 6. Feishu dry-run preview
- 7. Append-only audit later

## 7. Safety

- 本轮未实现真实 CLI/API。
- 本轮未修改 runtime、Gateway、action queue。
- Feishu summary 仅 dry-run/projection。

## 8. JSON Spec

- `C:\Users\win\AppData\Local\Temp\pytest-of-win\pytest-631\test_no_action_queue_written1\plan.json`

## 9. Final Verdict

A. R241-9B 成功，可进入 R241-10A Read-only Diagnostic CLI 内部实现。
