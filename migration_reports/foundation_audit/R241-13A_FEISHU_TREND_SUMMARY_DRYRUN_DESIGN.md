# R241-13A Feishu Trend Summary Dry-run Design

## 1. 修改文件清单

新增：

- `backend/app/audit/audit_trend_feishu_contract.py`
- `backend/app/audit/test_audit_trend_feishu_contract.py`
- `migration_reports/foundation_audit/R241-13A_FEISHU_TREND_SUMMARY_DRYRUN_CONTRACT.json`
- `migration_reports/foundation_audit/R241-13A_FEISHU_TREND_SUMMARY_DRYRUN_DESIGN.md`

修改：

- `backend/app/audit/__init__.py`

## 2. FeishuTrendPayloadStatus / FeishuTrendCardSectionType / FeishuTrendSeverity / FeishuTrendSendPermission

`FeishuTrendPayloadStatus`：`design_only`、`projection_only`、`ready_for_dry_run`、`blocked_no_webhook_policy`、`blocked_sensitive_content`、`blocked_line_count_changed`、`blocked_runtime_write_risk`、`unknown`。

`FeishuTrendCardSectionType`：`headline`、`trend_overview`、`regression_summary`、`guard_summary`、`artifact_links`、`warnings`、`next_step`、`safety_notice`、`unknown`。

`FeishuTrendSeverity`：`info`、`low`、`medium`、`high`、`critical`、`unknown`。

`FeishuTrendSendPermission`：`forbidden`、`projection_only`、`manual_send_later`、`requires_webhook_policy`、`requires_user_confirmation`、`unknown`。

## 3. FeishuTrendCardSection 字段

字段：`section_id`、`section_type`、`title`、`content`、`severity`、`items`、`source_metric_names`、`source_regression_ids`、`warnings`。

用途：定义 Feishu trend card 的分区 schema，只承载摘要字段、metric name、regression id 和 warnings，不承载完整 audit payload、prompt、memory 或 RTCM body。

## 4. FeishuTrendPayloadProjection 字段

字段：`payload_id`、`generated_at`、`status`、`title`、`template`、`source_trend_report_id`、`source_window`、`source_record_count`、`regression_count`、`by_severity`、`sections`、`card_json`、`send_permission`、`send_allowed`、`webhook_required`、`no_webhook_call`、`no_runtime_write`、`no_action_queue_write`、`no_auto_fix`、`warnings`、`errors`。

默认边界：`send_allowed=false`、`send_permission=projection_only`、`webhook_required=true`、`no_webhook_call=true`、`no_runtime_write=true`、`no_action_queue_write=true`、`no_auto_fix=true`。

## 5. FeishuTrendValidationResult 字段

字段：`validation_id`、`valid`、`status`、`send_allowed_is_false`、`no_webhook_call_is_true`、`no_runtime_write_is_true`、`no_action_queue_write_is_true`、`no_auto_fix_is_true`、`sensitive_content_detected`、`line_count_changed`、`blocked_reasons`、`warnings`、`errors`、`validated_at`。

验证目标：确保 dry-run payload 不具备发送能力、不含 webhook URL / token / secret / api_key、不写 runtime/action queue、不执行 auto-fix，并能阻断 line count changed 风险。

## 6. FeishuTrendDryRunDesign 字段

字段：`design_id`、`generated_at`、`input_sources`、`payload_schema`、`card_section_schema`、`validation_rules`、`blocked_send_paths`、`future_integration_points`、`implementation_phases`、`warnings`。

设计输入源引用：`audit_trend_projection`、`audit_trend_report_artifact`、`audit_trend_cli_guard`、`foundation_health_summary`。本轮仅定义 schema / mapping / validation，不调用 webhook，不推送 Feishu。

## 7. section catalog

已定义 8 个 card section：

- `headline`：总体结论，来源 trend status / regression count / severity counts。
- `trend_overview`：窗口、记录数、series 数、regression 数、by_severity。
- `regression_summary`：top regressions，最多 5 条，只显示 metric / severity / recommended action。
- `guard_summary`：JSONL line count、sensitive output、network、auto-fix guard 结果。
- `artifact_links`：只允许 report artifact path，不允许 runtime/audit_trail path。
- `warnings`：趋势投影 warnings，最多 8 条，脱敏显示。
- `next_step`：下一步建议，仅生成 action candidate，不执行。
- `safety_notice`：projection-only、no webhook、no auto-fix 提示。

## 8. payload mapping design

映射规则已定义：

- `trend_report.status` -> headline / card status。
- `trend_report.window` -> trend overview。
- `total_records_analyzed`、`series_count`、`regression_count` -> trend overview。
- `by_severity`、`top_regressions` -> regression summary。
- `guard.audit_jsonl_unchanged`、`guard.sensitive_output_detected`、`guard.network_call_detected` -> guard summary。
- artifact paths -> artifact_links，且仅限 report artifact。

所有 payload projection 强制：`send_allowed=false`、`no_webhook_call=true`、`no_runtime_write=true`、`no_action_queue_write=true`、`no_auto_fix=true`。

## 9. validation rules

已定义 validation rules：

- `send_allowed` 必须为 false。
- `status` 必须为 `design_only` 或 `projection_only`。
- webhook URL 不得出现。
- token / secret / api_key 不得出现。
- `no_webhook_call` 必须为 true。
- `no_runtime_write` 必须为 true。
- `no_action_queue_write` 必须为 true。
- `no_auto_fix` 必须为 true。
- `line_count_changed` 必须为 false。
- `sensitive_output_detected` 必须为 false。
- `card_json` 必须可序列化。
- artifact links 只能指向 report artifacts。

## 10. blocked send paths

阻断路径：

- real webhook send。
- webhook URL in payload/design。
- network call / HTTP client execution。
- scheduler/watchdog integration。
- runtime write / action queue write。
- audit JSONL write/modification。
- auto-fix / tool execution。
- payload containing secrets or full prompt/memory/RTCM/audit bodies。

## 11. implementation phases

- Phase 1：Design-only Contract，当前 R241-13A，仅定义 schema / mapping / validation。
- Phase 2：Payload Projection，从 trend report + guard result 生成 projection，不发送。
- Phase 3：CLI Dry-run Preview，新增 audit-trend-feishu CLI，只输出 payload preview。
- Phase 4：Manual Send Policy Design，定义 webhook policy、人工确认、脱敏审查，不发送。
- Phase 5：Manual Send Implementation，后续单独实施，默认禁用。
- Phase 6：Scheduler Integration Review，后续独立审查，不接主链。

## 12. validation result

`validate_feishu_trend_dryrun_design()` 结果：`valid=true`。

生成后静态检查结果：未发现 webhook URL、敏感 key/value、`send_allowed=true`、`no_webhook_call=false`、`no_runtime_write=false`、`no_action_queue_write=false`、`no_auto_fix=false` 或 `auto_fix_enabled=true`。

## 13. 测试结果

必跑验证：

- RootGuard Python：PASS。
- RootGuard PowerShell：PASS。
- Compile：PASS。
- R241-13A Feishu trend contract tests：21 passed。

回归验证：

- Previous Trend tests：81 passed。
- Previous Audit tests：109 passed。
- Previous Foundation tests：125 passed。
- Previous Nightly tests：36 passed。
- Previous RTCM tests：38 passed。
- Previous Prompt tests：33 passed。
- Previous ToolRuntime tests：36 passed。
- Previous Mode / Gateway tests：30 passed。
- Previous Asset tests：32 passed。
- Previous Memory tests：24 passed。
- Previous Truth / State tests：33 passed。
- Gateway smoke：11 passed。

## 14. 是否真实推送 Feishu / 调用 webhook / network

否。未真实推送 Feishu / Lark，未调用 webhook，未调用网络。当前仅生成 dry-run design contract 与审计报告。

## 15. 是否写 audit JSONL / runtime / action queue

否。未写新的 audit JSONL，未修改已有 audit JSONL，未写 trend runtime / governance_state / experiment_queue / memory / asset / prompt / RTCM runtime，未写 action queue。

## 16. 是否执行 auto-fix

否。未执行 auto-fix，未执行真实工具调用，未执行 asset promotion / elimination、memory cleanup 或 prompt replacement。

## 17. 当前剩余断点

- R241-13A 只定义 design contract，尚未实现真实 FeishuTrendPayloadProjection 生成器。
- 尚未实现 audit-trend-feishu CLI dry-run preview。
- Manual send policy、webhook allowlist、人工确认与脱敏审查仍未设计完成。
- Scheduler integration 继续保持 blocked，需要后续独立审查。

## 18. 下一轮建议

进入 R241-13B：Feishu Trend Payload Projection 实现。建议继续保持 projection-only：输入 trend report summary + guard result，输出 `FeishuTrendPayloadProjection` 与 validation result，强制 `send_allowed=false`，不接 webhook，不接 scheduler，不写 runtime/action queue。
