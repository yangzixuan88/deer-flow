# R241-12A Nightly Trend Report Design

## 1. 修改文件清单

- `backend/app/audit/audit_trend_contract.py`
- `backend/app/audit/test_audit_trend_contract.py`
- `backend/app/audit/__init__.py`
- `migration_reports/foundation_audit/R241-12A_NIGHTLY_TREND_REPORT_CONTRACT.json`
- `migration_reports/foundation_audit/R241-12A_NIGHTLY_TREND_REPORT_DESIGN.md`

## 2. AuditTrendPoint 字段

- `point_id`
- `timestamp`
- `window`
- `metric_type`
- `metric_name`
- `metric_value`
- `source_command`
- `event_type`
- `domain`
- `severity`
- `source_record_refs`
- `warnings`

## 3. AuditTrendSeries 字段

- `series_id`
- `metric_type`
- `metric_name`
- `window`
- `points`
- `direction`
- `latest_value`
- `previous_value`
- `delta`
- `delta_percent`
- `sample_count`
- `warnings`

## 4. TrendRegressionSignal 字段

- `regression_id`
- `metric_type`
- `metric_name`
- `severity`
- `direction`
- `current_value`
- `baseline_value`
- `threshold`
- `affected_commands`
- `affected_domains`
- `evidence_record_refs`
- `recommended_action`
- `warnings`

## 5. NightlyTrendReport 字段

- `trend_report_id`
- `generated_at`
- `status`
- `window`
- `source_query_refs`
- `total_records_analyzed`
- `series`
- `regression_signals`
- `summary`
- `warnings`
- `errors`

## 6. NightlyTrendDesign 字段

- `design_id`
- `generated_at`
- `input_sources`
- `metric_catalog`
- `trend_windows`
- `regression_rules`
- `output_formats`
- `future_integration_points`
- `blocked_actions`
- `implementation_phases`
- `warnings`

## 7. metric catalog

- `partial_warning_rate` / `diagnostic_status_rate`: Ratio of diagnostic audit records whose status is partial_warning.
- `failed_rate` / `diagnostic_status_rate`: Ratio of diagnostic audit records whose status is failed.
- `total_audit_records` / `append_record_count`: Total valid append-only audit records in the selected window.
- `critical_signal_count` / `critical_count`: Number of critical health or summary signals.
- `high_signal_count` / `high_count`: Number of high-severity health or summary signals.
- `queue_missing_warning_count` / `queue_missing_count`: Occurrences of queue_missing warnings in diagnostics.
- `unknown_taxonomy_count` / `unknown_taxonomy_count`: Unknown taxonomy warnings across Memory, Prompt, RTCM, Asset, and Truth projections.
- `rollback_missing_count` / `rollback_missing_count`: Missing rollback warning count from Prompt/ToolRuntime/Health signals.
- `backup_missing_count` / `backup_missing_count`: Missing backup warning count from Prompt/ToolRuntime/Health signals.
- `feishu_dry_run_count` / `command_run_count`: Count of Feishu summary dry-run projection records.
- `nightly_review_count` / `command_run_count`: Count of Nightly Foundation Health Review records.
- `invalid_jsonl_line_count` / `invalid_line_count`: Invalid JSONL line count reported by scan_append_only_audit_trail.

## 8. trend window specs

- `last_24h`: now - 24 hours -> now, min_points=2
- `last_7d`: now - 7 days -> now, min_points=3
- `last_30d`: now - 30 days -> now, min_points=5
- `all_available`: first available audit record -> last available audit record, min_points=1
- `custom`: caller supplied start_time -> caller supplied end_time, min_points=1

## 9. extraction design

- source: `AuditQueryResult.records from query_audit_trail() and file_summaries from scan_append_only_audit_trail()`
- `source_command`: Group trend points by CLI command or dry-run command surface.
- `event_type`: Separate diagnostic_run, nightly_health_review, feishu_summary_dryrun, and append events.
- `status`: Compute ok / partial_warning / failed rates.
- `warnings`: Count queue_missing, unknown taxonomy, backup_missing, rollback_missing, and policy warnings.
- `errors`: Compute hard failure trends and query/runtime design errors.
- `summary`: Extract total_signals, by_severity, action_candidate_count, blocked_high_risk_count, requires_confirmation_count.
- `summary.by_severity`: Compute critical/high/medium/low severity series.
- `summary.action_candidate_count`: Track action candidate volume over time.
- `summary.blocked_high_risk_count`: Track blocked high-risk action trend.
- `payload_hash`: Detect repeated identical payloads and de-duplicate trend evidence.
- `generated_at`: Primary event timestamp for trend bucketing.
- `observed_at`: Fallback source observation timestamp.
- `appended_at`: Append-only record timestamp and fallback ordering key.

## 10. regression detection rules

- `partial_warning_rate_increases`: current window rate exceeds baseline by >= 20% or crosses 0.5; severity=`medium`; auto_fix_allowed=False
- `critical_count_increases`: critical count is greater than previous comparable window; severity=`critical`; auto_fix_allowed=False
- `high_count_increases`: high count is greater than previous comparable window; severity=`high`; auto_fix_allowed=False
- `queue_missing_persists`: queue_missing appears in two or more consecutive nightly windows; severity=`medium`; auto_fix_allowed=False
- `unknown_taxonomy_persists`: unknown taxonomy warning count remains > 0 across configured window; severity=`medium`; auto_fix_allowed=False
- `backup_missing_persists`: backup_missing remains > 0 across configured window; severity=`high`; auto_fix_allowed=False
- `rollback_missing_persists`: rollback_missing remains > 0 across configured window; severity=`high`; auto_fix_allowed=False
- `invalid_line_count_gt_zero`: scan_append_only_audit_trail reports invalid_line_count > 0; severity=`high`; auto_fix_allowed=False
- `no_nightly_record_in_expected_window`: nightly health review record count is 0 in expected nightly window; severity=`high`; auto_fix_allowed=False
- `feishu_dry_run_missing_after_nightly`: nightly record exists but no Feishu summary dry-run record follows it in window; severity=`medium`; auto_fix_allowed=False

## 11. implementation phases

- `Phase 1` Design-only Contract: Current R241-12A; define schema, metrics, windows, extraction rules, and regression rules.
- `Phase 2` Dry-run Trend Projection: Call audit query engine to generate trend points without writing trend runtime.
- `Phase 3` Trend Report Artifact: Write report artifacts to migration_reports/foundation_audit only.
- `Phase 4` Nightly Trend CLI: Add read-only audit-trend CLI; no scheduler coupling.
- `Phase 5` Feishu Trend Summary Dry-run: Generate Feishu trend payload projection, do not send.
- `Phase 6` Long-term Trend Dashboard: Future separate design; not connected to Gateway main path.

## 12. validation result

- valid: `True`
- warnings: `[]`
- errors: `[]`
- json_contract: `E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit\R241-12A_NIGHTLY_TREND_REPORT_CONTRACT.json`

## 13. 测试结果

- RootGuard Python: PASS
- RootGuard PowerShell: PASS
- Compile `backend/app/audit/audit_trend_contract.py`: PASS
- R241-12A audit trend tests: 17 passed
- Previous Audit tests: 109 passed
- Previous Nightly tests: 36 passed
- Previous RTCM tests: 38 passed
- Previous Prompt tests: 33 passed
- Previous ToolRuntime tests: 36 passed
- Previous Mode / Gateway instrumentation tests: 30 passed
- Previous Asset tests: 32 passed
- Previous Memory tests: 24 passed
- Previous Truth / State tests: 33 passed
- Gateway smoke: 11 passed
- Foundation `test_integration_readiness.py`: 16 passed
- Foundation `test_read_only_integration_plan.py`: 18 passed
- Foundation `test_read_only_diagnostics_cli.py`: execution attempted but timed out at 240s/300s in this environment; no assertion failure was returned before timeout. This file currently covers later R241-10C/R241-11D real diagnostic paths and is retained as a historical performance/timeout caveat, not an R241-12A code failure.

## 14. 是否写 audit JSONL / runtime / action queue

否。本轮只写审计设计 JSON 与 Markdown，不写 audit_trail JSONL，不修改已有 JSONL，不写 runtime，不写 action queue。

## 15. 是否调用 Feishu / network

否。Feishu trend summary 仅作为未来 dry-run projection，不调用 webhook，不进行网络访问。

## 16. 当前剩余断点

- R241-12A 只完成 design-only contract，尚未执行 audit query trend projection。
- 趋势点生成、序列计算、baseline 比较和 Feishu trend payload 将在后续阶段单独实现。
- 当前 audit_trail 样本数量有限，真实 regression detection 需要 R241-12B dry-run projection 验证。

## 17. 下一轮建议

A. R241-12A 成功后，可进入 R241-12B Dry-run Trend Projection 实现：只读调用 audit query engine，生成趋势点与 regression projection，不写 audit JSONL/runtime/action queue。
