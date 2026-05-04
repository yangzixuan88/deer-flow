# R241-10A Read-only Diagnostic CLI Report

## 1. 修改文件清单

新增：

- `backend/app/foundation/read_only_diagnostics_cli.py`
- `backend/app/foundation/test_read_only_diagnostics_cli.py`
- `scripts/foundation_diagnose.py`
- `migration_reports/foundation_audit/R241-10A_READONLY_DIAGNOSTIC_CLI_SAMPLE.json`
- `migration_reports/foundation_audit/R241-10A_READONLY_DIAGNOSTIC_CLI_REPORT.md`

未修改 Gateway / M01 / M04 / scheduler / watchdog / runtime state。

## 2. DiagnosticRunResult 字段

`DiagnosticRunResult` 使用 dataclass 定义，字段：

- `command`
- `status`
- `generated_at`
- `root`
- `format`
- `summary`
- `payload`
- `warnings`
- `errors`
- `report_path`

状态枚举语义：

- `ok`
- `partial_warning`
- `failed`

## 3. DiagnosticCommandRegistry 字段

`DiagnosticCommandRegistry` 使用 dataclass 定义，字段：

- `available_commands`
- `disabled_commands`
- `source_plan_ref`
- `warnings`

`source_plan_ref` 指向 `migration_reports/foundation_audit/R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.json`。

## 4. implemented / disabled commands

已实现内部 CLI binding：

- `truth-state`
- `queue-sandbox`
- `nightly`
- `all`

本轮保持 disabled：

- `memory`
- `asset`
- `prompt`
- `rtcm`
- `feishu-summary`

Registry warning 包含 `partial_phase_a_cli_implementation`，表示本轮只实现 Phase A 第一批 CLI helper。

## 5. truth-state diagnostic 实现结果

`run_truth_state_diagnostic()` 只读调用：

- `governance_bridge.project_recent_outcomes()`
- `governance_bridge.get_success_rate_candidates()`

输出摘要包含：

- `truth_events_count`
- `state_events_count`
- `execution_success_candidates_count`
- `ineligible_count`
- `excluded_governance_or_observation_count`

CLI smoke `limit=20` 结果：

- status: `partial_warning`
- truth_events_count: 31
- state_events_count: 14
- execution_success_candidates_count: 13
- excluded_governance_or_observation_count: 8

Warnings 来自 legacy projection 诊断，例如 approval / observation 不进入 execution success rate，以及 unknown legacy mapping。未写 `governance_state.json`。

## 6. queue-sandbox diagnostic 实现结果

`run_queue_sandbox_diagnostic()` 只读调用：

- `load_experiment_queue_snapshot()`
- `project_sandbox_outcomes()`
- `get_sandbox_execution_success_candidates()`
- `correlate_queue_with_sandbox_truth()`

CLI smoke `limit=20` 结果：

- status: `partial_warning`
- queue exists: false
- sandbox_records_count: 17
- actual_pass_count: 5
- actual_fail_count: 12
- simple_success_rate: 0.38461538461538464
- queue_path_mismatch warning: `queue_missing:C:\Users\win\.deerflow\upgrade-center\state\experiment_queue.json`
- correlation warning: `sandbox_truth_without_queue_task:17`

未写 `experiment_queue.json`，未写 `governance_state.json`。

## 7. nightly diagnostic 实现结果

`run_nightly_diagnostic()` 只读调用：

- `aggregate_nightly_foundation_health()`
- `summarize_review_for_user()`
- `build_plaintext_nightly_summary()`

CLI smoke `max_files=100` 结果：

- status: `partial_warning`
- total_signals: 20
- by_severity: `{'medium': 11, 'info': 1, 'high': 8}`
- action_candidate_count: 20
- blocked_high_risk_count: 0
- requires_confirmation_count: 4
- headline: `Nightly Foundation Health Review: critical=0, high=8, actions=20, blocked=0. 本摘要为 projection，不会自动修复。`

未写 action queue，未执行自动修复，未推送 Feishu。

## 8. all diagnostic 实现结果

`run_all_diagnostics()` 聚合本轮已实现命令：

- `truth-state`
- `queue-sandbox`
- `nightly`

本轮不包含 disabled 命令：

- `memory`
- `asset`
- `prompt`
- `rtcm`
- `feishu-summary`

CLI smoke `all --format json --write-report` 结果：

- status: `partial_warning`
- child_statuses: truth-state / queue-sandbox / nightly 均为 `partial_warning`
- report_path: `migration_reports/foundation_audit/R241-10A_READONLY_DIAGNOSTIC_CLI_SAMPLE.json`

`write_report=false` 默认不写文件；`write_report=true` 只写 R241-10A 审计 sample。

## 9. format 输出支持

`format_diagnostic_result()` 支持：

- `json`: 返回完整 structured dict
- `markdown`: 返回简短 Markdown 摘要，保留 warnings/errors
- `text`: 返回简短纯文本摘要，保留 warnings/errors

Markdown/text 不展开超长 payload；JSON 保留完整 payload。

## 10. CLI smoke 结果

手动 CLI smoke：

- `python scripts/foundation_diagnose.py truth-state --format json --limit 20`: exit 0, status `partial_warning`
- `python scripts/foundation_diagnose.py queue-sandbox --format text --limit 20`: exit 0, status `partial_warning`
- `python scripts/foundation_diagnose.py nightly --format text --max-files 100`: exit 0, status `partial_warning`
- `python scripts/foundation_diagnose.py all --format json --write-report`: exit 0, status `partial_warning`, only wrote R241-10A sample

`partial_warning` 为诊断状态，不是执行失败；来源包括 queue default path 缺失、legacy mapping warning、只读 health signal。

## 11. 测试结果

RootGuard：

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile：

- `python -m py_compile backend/app/foundation/read_only_diagnostics_cli.py scripts/foundation_diagnose.py`: PASS

Tests：

- Foundation tests: 52 passed
- Nightly tests: 36 passed
- RTCM tests: 38 passed
- Prompt tests: 33 passed
- ToolRuntime tests: 36 passed
- Mode / Gateway instrumentation tests: 30 passed
- Asset tests: 32 passed
- Memory tests: 24 passed
- Truth / State tests: 33 passed
- Gateway smoke: 11 passed

## 12. 是否开放 HTTP API

否。

本轮没有新增 HTTP route，没有修改 Gateway router，没有注册 API endpoint，没有实现 POST / PUT / DELETE / PATCH。

## 13. 是否修改 runtime / action queue / Gateway

否。

未修改：

- `governance_state.json`
- `experiment_queue.json`
- memory / Qdrant / SQLite / checkpoints
- asset registry / binding report / DPBS runtime
- prompt runtime / SOUL.md / DeerFlow prompts
- RTCM runtime / dossier / final_report / signoff / followup
- Gateway / M01 / M04 / DeerFlow run 主路径
- scheduler / watchdog
- action queue

未执行真实工具、自动修复、Feishu 推送、asset promotion / elimination、memory cleanup、prompt replacement。

## 14. 当前剩余断点

- `memory` / `asset` / `prompt` / `rtcm` / `feishu-summary` CLI binding 尚未接入，本轮按计划保持 disabled。
- 默认 queue path `C:\Users\win\.deerflow\upgrade-center\state\experiment_queue.json` 缺失，继续作为 diagnostic warning。
- `truth-state` 中仍存在 legacy unknown mapping，例如 `upgrade_center_execution` / `upgrade_center_summary`，本轮只诊断不迁移。
- CLI 当前为内部 helper + script wrapper，未注册全局命令。

## 15. 下一轮建议

最终判定：A. R241-10A 成功，可进入 R241-10B 扩展 memory/asset/prompt/rtcm CLI binding。

建议 R241-10B 继续保持 read-only-only：

- 扩展 `foundation diagnose memory`
- 扩展 `foundation diagnose asset`
- 扩展 `foundation diagnose prompt`
- 扩展 `foundation diagnose rtcm`
- 保持 `feishu-summary` 为 dry-run/projection，不真实推送
