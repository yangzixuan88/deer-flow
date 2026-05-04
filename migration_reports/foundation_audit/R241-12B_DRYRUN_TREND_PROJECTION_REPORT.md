# R241-12B Dry-run Trend Projection Report

## 1. 修改文件清单

新增：

- `backend/app/audit/audit_trend_projection.py`
- `backend/app/audit/test_audit_trend_projection.py`
- `migration_reports/foundation_audit/R241-12B_DRYRUN_TREND_PROJECTION_SAMPLE.json`
- `migration_reports/foundation_audit/R241-12B_DRYRUN_TREND_PROJECTION_REPORT.md`

修改：

- `backend/app/audit/__init__.py`
- `backend/app/foundation/read_only_diagnostics_cli.py`
- `backend/app/foundation/test_read_only_diagnostics_cli.py`

## 2. TrendProjectionStatus / TrendAggregationMethod

`TrendProjectionStatus`：

- `ok`
- `partial_warning`
- `insufficient_data`
- `query_error`
- `failed`

`TrendAggregationMethod`：

- `count`
- `sum`
- `rate`
- `latest`
- `delta`
- `warning_contains`
- `summary_field_sum`
- `unknown`

## 3. trend design loading 结果

`load_trend_design_contract()` 已实现，只读加载：

- `migration_reports/foundation_audit/R241-12A_NIGHTLY_TREND_REPORT_CONTRACT.json`

行为：

- 文件缺失返回 warning
- malformed JSON 返回 warning
- 不写文件
- 不崩溃

R241-12B sample 中 design contract 加载成功。

## 4. window resolution 结果

`resolve_trend_window()` 已实现：

- `all_available`: 不强制 start/end
- `last_24h`: `now - 24h` 到 `now`
- `last_7d`: `now - 7d` 到 `now`
- `last_30d`: `now - 30d` 到 `now`
- `custom`: 缺 start/end 返回 warning，malformed datetime 返回 warning

CLI smoke 覆盖：

- `all_available`
- `last_24h`
- `last_7d`

## 5. audit query fetch 结果

`fetch_audit_records_for_trend()` 已实现，只读调用：

- `build_audit_query_filter()`
- `query_audit_trail()`
- `scan_append_only_audit_trail()`

当前真实 audit_trail 行数：

- `feishu_summary_dryruns.jsonl`: 2
- `foundation_diagnostic_runs.jsonl`: 14
- `nightly_health_reviews.jsonl`: 2

CLI smoke 前后行数一致，未追加、覆盖、截断或重写 JSONL。

## 6. metric extraction 结果

`extract_metric_value_from_records()` 已支持：

- `partial_warning_rate`
- `failed_rate`
- `total_audit_records`
- `critical_signal_count`
- `high_signal_count`
- `queue_missing_warning_count`
- `unknown_taxonomy_count`
- `rollback_missing_count`
- `backup_missing_count`
- `feishu_dry_run_count`
- `nightly_review_count`
- `invalid_jsonl_line_count`

抽取规则：

- status rate 来自 `record.status`
- warning count 来自 `record.warnings`
- severity count 来自 `record.summary.by_severity` 或 summary count 字段
- invalid JSONL line count 来自 scan summary
- source refs 仅保留 `audit_record_id` / `payload_hash` / `source_command`

## 7. trend points / series 结果

`build_trend_points()` 为 metric catalog 中每个 metric 生成 `AuditTrendPoint`。

`build_trend_series()` 将 points 聚合为 `AuditTrendSeries`：

- 当前样本每个 metric 1 个 point
- `sample_count` 正确
- `latest_value` 正确
- 样本不足时 `direction=insufficient_data`
- 多点时按 delta 推断 improving/stable/worsening

R241-12B sample：

- total_records_analyzed: 18
- series_count: 12

## 8. regression signals 结果

`detect_trend_regressions()` 已实现 R241-12A 规则：

- `partial_warning_rate_increases`
- `critical_count_increases`
- `high_count_increases`
- `queue_missing_persists`
- `unknown_taxonomy_persists`
- `backup_missing_persists`
- `rollback_missing_persists`
- `invalid_line_count_gt_zero`
- `no_nightly_record_in_expected_window`
- `feishu_dry_run_missing_after_nightly`

当前真实 sample regression：

- regression_count: 2
- by_severity: `{'medium': 2}`
- top regressions:
  - `queue_missing_warning_count=8.0`
  - `unknown_taxonomy_count=46.0`

persist 类规则在单窗口样本中附带 insufficient-data warning，不伪造连续恶化。

## 9. dry-run trend report 结果

`generate_dryrun_nightly_trend_report()` 已实现完整流程：

1. load trend design contract
2. resolve trend window
3. fetch audit records
4. build trend points
5. build trend series
6. detect regressions
7. assemble `NightlyTrendReport`

当前 sample：

- status: `ok`
- window: `all_available`
- total_records_analyzed: 18
- series_count: 12
- regression_count: 2

## 10. format / CLI audit-trend smoke 结果

`format_trend_report()` 支持：

- `json`: 返回 structured dict
- `markdown`: 返回简明 Markdown，不展开 source records
- `text`: 返回简明文本，不展开 source records

CLI 新增：

- `python scripts/foundation_diagnose.py audit-trend --window all_available --format json`
- `python scripts/foundation_diagnose.py audit-trend --window last_24h --format text`
- `python scripts/foundation_diagnose.py audit-trend --window last_7d --format markdown`

Smoke 结果：

- all_available/json: exit 0
- last_24h/text: exit 0
- last_7d/markdown: exit 0
- JSONL line count before/after unchanged

## 11. 测试结果

RootGuard：

- Python: PASS
- PowerShell: PASS

Compile：

- `audit_trend_contract.py`: PASS
- `audit_trend_projection.py`: PASS
- `audit/__init__.py`: PASS
- `read_only_diagnostics_cli.py`: PASS
- `scripts/foundation_diagnose.py`: PASS

Tests：

- R241-12A/12B trend tests: 43 passed
- Previous Audit tests: 109 passed
- Foundation readiness / integration plan tests: 34 passed
- Foundation CLI tests: 79 passed
- Previous Nightly tests: 36 passed
- Previous RTCM tests: 38 passed
- Previous Prompt tests: 33 passed
- Previous ToolRuntime tests: 36 passed
- Previous Mode / Gateway instrumentation tests: 30 passed
- Previous Asset tests: 32 passed
- Previous Memory tests: 24 passed
- Previous Truth / State tests: 33 passed
- Gateway smoke: 11 passed

## 12. 是否写 audit JSONL / runtime / action queue

否。

本轮没有写新的 audit JSONL，没有修改已有 audit JSONL，没有写趋势 runtime/database，没有写 action queue。

## 13. 是否修改 JSONL line count

否。

CLI smoke 前后：

- `feishu_summary_dryruns.jsonl`: 2 -> 2
- `foundation_diagnostic_runs.jsonl`: 14 -> 14
- `nightly_health_reviews.jsonl`: 2 -> 2

## 14. 是否调用 network / Feishu

否。

未调用 webhook，未推送 Feishu/Lark，未进行网络访问。

## 15. 是否执行 auto-fix

否。

Regression signals 只生成 dry-run projection，不创建 action queue，不执行修复，不执行工具，不做 asset promotion/elimination、memory cleanup 或 prompt replacement。

## 16. 当前剩余断点

- 当前 trend series 主要是单窗口 dry-run，direction 多为 `insufficient_data`；真实趋势方向需要 R241-12C/12D 后逐步积累多窗口 artifacts。
- persist 类 regression 目前可基于当前值生成 diagnostic signal，但连续窗口证据仍不足。
- `test_read_only_diagnostics_cli.py` 已通过，但耗时约 6 分 51 秒，后续应拆分慢速真实诊断测试与快速单元测试。

## 17. 下一轮建议

最终判定：A. R241-12B 成功，可进入 R241-12C Trend Report Artifact 实现。

R241-12C 建议仍保持只读输入，只允许将 trend report artifact 写入 `migration_reports/foundation_audit`，不得写 audit JSONL/runtime/action queue，不接 scheduler，不推送 Feishu。
