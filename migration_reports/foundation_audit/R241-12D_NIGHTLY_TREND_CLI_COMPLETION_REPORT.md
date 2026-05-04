# R241-12D Nightly Trend CLI Completion Report

## 1. 修改文件清单

新增：

- `backend/app/audit/audit_trend_cli_guard.py`
- `backend/app/audit/test_audit_trend_cli_guard.py`
- `migration_reports/foundation_audit/R241-12D_NIGHTLY_TREND_CLI_COMPLETION_SAMPLE.json`
- `migration_reports/foundation_audit/R241-12D_TREND_REPORT_ARTIFACT.json`
- `migration_reports/foundation_audit/R241-12D_TREND_REPORT_ARTIFACT.md`
- `migration_reports/foundation_audit/R241-12D_TREND_REPORT_ARTIFACT.txt`
- `migration_reports/foundation_audit/R241-12D_NIGHTLY_TREND_CLI_COMPLETION_REPORT.md`

修改：

- `backend/app/audit/audit_trend_report_artifact.py`
- `backend/app/audit/__init__.py`
- `backend/app/foundation/read_only_diagnostics_cli.py`
- `backend/app/foundation/test_read_only_diagnostics_cli.py`

`script/foundation_diagnose.py` 未改变主体逻辑，仍只导入并调用 CLI main。

## 2. TrendCliGuardStatus / TrendCliSafetyCheckType / TrendCliCommandMode

`TrendCliGuardStatus`：`ok`、`warning`、`blocked`、`failed`、`unknown`。

`TrendCliSafetyCheckType`：`line_count_guard`、`output_path_guard`、`sensitive_output_guard`、`runtime_write_guard`、`network_guard`、`auto_fix_guard`、`unknown`。

`TrendCliCommandMode`：`dry_run`、`write_report`、`scan_only`、`validate_only`、`unknown`。

## 3. TrendCliSafetyCheckResult 字段

字段：`check_id`、`check_type`、`status`、`message`、`before_value`、`after_value`、`warnings`、`errors`、`checked_at`。

## 4. TrendCliExecutionGuard 字段

字段：`guard_id`、`command_mode`、`root`、`line_count_before`、`line_count_after`、`safety_checks`、`write_report_allowed`、`audit_jsonl_unchanged`、`runtime_write_detected`、`network_call_detected`、`sensitive_output_detected`、`auto_fix_detected`、`warnings`、`errors`、`created_at`。

## 5. line count guard 实现结果

`capture_audit_jsonl_line_counts()` 只读捕获以下 JSONL 行数，不创建目录、不创建文件：

- `foundation_diagnostic_runs.jsonl`
- `nightly_health_reviews.jsonl`
- `feishu_summary_dryruns.jsonl`
- `tool_runtime_projections.jsonl`
- `mode_callgraph_projections.jsonl`

`compare_audit_jsonl_line_counts()` 对比 before/after，并在变动时返回 `audit_jsonl_line_count_changed`。当前真实 CLI smoke 前后行数一致：

- `feishu_summary_dryruns.jsonl`：2 → 2
- `foundation_diagnostic_runs.jsonl`：14 → 14
- `nightly_health_reviews.jsonl`：2 → 2

`tool_runtime_projections.jsonl` 与 `mode_callgraph_projections.jsonl` 当前缺失，仅作为 warning，不创建。

## 6. sensitive output guard 实现结果

`validate_trend_cli_output_safety()` 已识别：webhook URL、`api_key`、`token`、`secret`、`prompt_body`、`memory_body`、`rtcm_artifact_body`、full source record payload、可疑长内容块。CLI 输出 guard summary，不输出 secret/token/webhook/full prompt/full memory/full RTCM body。sample 检查未发现敏感输出触发项。

## 7. artifact path guard 实现结果

`validate_trend_cli_artifact_paths()` 复用 artifact path validation，并允许 `R241-12D_` / `R241-12C_` 前缀，后缀仅 `.json` / `.md` / `.txt`。拒绝 `audit_trail/`、`..`、runtime/action queue/governance/memory/asset/prompt/RTCM 运行态路径和 symlink 逃逸。

本轮 write-report smoke 仅生成：

- `migration_reports/foundation_audit/R241-12D_TREND_REPORT_ARTIFACT.json`
- `migration_reports/foundation_audit/R241-12D_TREND_REPORT_ARTIFACT.md`
- `migration_reports/foundation_audit/R241-12D_TREND_REPORT_ARTIFACT.txt`

## 8. guarded audit-trend helper 结果

`run_guarded_audit_trend_cli_projection()` 流程：capture line counts before → dry-run trend projection → format output → optional R241-12D artifact write → capture line counts after → compare line counts → sensitive output guard → artifact path guard → return `TrendCliExecutionGuard`。

当前真实样本：`status=ok`，`window=all_available`，`total_records_analyzed=18`，`series_count=12`，`regression_count=2`，`by_severity={medium: 2}`。

## 9. CLI 参数完整化结果

`python scripts/foundation_diagnose.py audit-trend` 已支持：

- `--window all_available|last_24h|last_7d|last_30d|custom`
- `--start-time`
- `--end-time`
- `--format json|text|markdown`
- `--write-trend-report`
- `--report-format json|markdown|text|all`
- `--output-prefix R241-12D_TREND_REPORT_ARTIFACT`

默认不写 artifact；只有 `--write-trend-report` 才写 artifact。输出包含 `guard_summary` 或等价文本形式。

## 10. CLI smoke 结果

已执行并通过：

- `audit-trend --window all_available --format json`：exit 0，guard summary present，未写 artifact
- `audit-trend --window last_24h --format text`：exit 0，guard summary present，未写 artifact
- `audit-trend --window last_7d --format markdown`：exit 0，guard summary present，未写 artifact
- `audit-trend --window custom --start-time 2026-04-25T00:00:00Z --end-time 2026-04-25T23:59:59Z --format json`：exit 0，guard summary present，未写 artifact
- `audit-trend --window all_available --format json --write-trend-report --report-format all --output-prefix R241-12D_TREND_REPORT_ARTIFACT`：exit 0，仅写 3 个 R241-12D artifact

## 11. 测试结果

RootGuard：PASS

Compile：PASS

- `python -m py_compile backend/app/audit/audit_trend_contract.py backend/app/audit/audit_trend_projection.py backend/app/audit/audit_trend_report_artifact.py backend/app/audit/audit_trend_cli_guard.py backend/app/audit/__init__.py backend/app/foundation/read_only_diagnostics_cli.py scripts/foundation_diagnose.py`

Tests：

- Trend contract/projection/artifact/CLI guard：81 passed
- Previous Audit tests：109 passed
- Previous Foundation tests：125 passed
- Previous Nightly tests：36 passed
- Previous RTCM tests：38 passed
- Previous Prompt tests：33 passed
- Previous ToolRuntime tests：36 passed
- Previous Mode/Gateway tests：30 passed
- Previous Asset tests：32 passed
- Previous Memory tests：24 passed
- Previous Truth/State tests：33 passed
- Gateway smoke：11 passed

## 12. 是否写 audit JSONL / 修改 line count

否。未写新 audit JSONL，未覆盖、truncate、rewrite、delete audit JSONL。CLI smoke 前后 line count 一致：`2 / 14 / 2`。

## 13. 是否写 runtime/action queue

否。未写 trend runtime/trend database/action queue/governance_state/experiment_queue/memory/asset/prompt/RTCM runtime。

## 14. 是否调用 network/Feishu

否。未调用 webhook，未真实推送 Feishu/Lark，未执行网络调用。

## 15. 是否执行 auto-fix

否。未执行自动修复，未执行真实工具调用，未执行 asset promotion/elimination、memory cleanup、prompt replacement。

## 16. 当前剩余断点

- Trend CLI 已完成只读 guard 化，但尚未实现 Feishu trend summary dry-run payload。
- `tool_runtime_projections.jsonl` 与 `mode_callgraph_projections.jsonl` 当前缺失，仅作为 line count guard warning，不创建。
- 仍未接 scheduler/watchdog，也未建立 trend runtime 或长期趋势数据库。

## 17. 下一轮建议

进入 R241-13A：Feishu Trend Summary Dry-run 设计。建议继续保持 projection-only：复用 trend report summary 和 guard result，生成 Feishu/Lark payload schema 与 validation，但不调用 webhook、不写 action queue、不接 scheduler。

最终判定：A. R241-12D 成功，可进入 R241-13A Feishu Trend Summary Dry-run 设计。
