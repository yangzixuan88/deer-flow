# R241-8B Nightly Read-only Projection / Feishu Summary Report

## 1. Modification Scope

新增文件：

- `backend/app/nightly/foundation_health_summary.py`
- `backend/app/nightly/test_foundation_health_summary.py`
- `migration_reports/foundation_audit/R241-8B_NIGHTLY_FEISHU_SUMMARY_SAMPLE.json`
- `migration_reports/foundation_audit/R241-8B_NIGHTLY_FEISHU_SUMMARY_PROJECTION_REPORT.md`

未修改：

- Nightly scheduler / watchdog
- Feishu / Lark bridge
- action queue
- governance_state / experiment_queue
- memory / asset / prompt / RTCM runtime
- Gateway / M01 / M04 / DeerFlow run 主路径

## 2. NightlySummarySection Fields

`NightlySummarySection` 字段：

- `section_id`
- `section_type`
- `title`
- `severity`
- `content`
- `items`
- `source_signal_ids`
- `source_action_candidate_ids`
- `warnings`

section 类型：

- `headline`
- `severity_overview`
- `domain_summary`
- `critical_actions`
- `high_priority_actions`
- `blocked_actions`
- `diagnostic_findings`
- `next_step`
- `warnings`
- `unknown`

## 3. NightlyReadableSummary Fields

`NightlyReadableSummary` 字段：

- `summary_id`
- `generated_at`
- `audience`
- `title`
- `headline`
- `severity_counts`
- `critical_count`
- `high_count`
- `action_candidate_count`
- `requires_confirmation_count`
- `blocked_high_risk_count`
- `sections`
- `warnings`

audience 支持：

- `user_brief`
- `operator_detail`
- `feishu_card`
- `machine_json`
- `unknown`

## 4. FeishuCardPayloadProjection Fields

`FeishuCardPayloadProjection` 字段：

- `payload_id`
- `generated_at`
- `status`
- `title`
- `template`
- `card_json`
- `source_review_id`
- `send_allowed`
- `send_blocked_reason`
- `webhook_required`
- `warnings`

安全约束：

- `send_allowed=false`
- `status=projection_only`
- `webhook_required=true`
- `no_webhook_call=true`
- `no_runtime_write=true`

## 5. User Summary Implementation

已实现：

- `load_latest_nightly_review_sample()`
- `summarize_review_for_user()`
- `build_plaintext_nightly_summary()`

当前 sample headline：

`Nightly Foundation Health Review: critical=2, high=10, actions=26, blocked=2. 本摘要为 projection，不会自动修复。`

用户摘要包含：

- headline
- severity overview
- top critical signals
- top high signals
- blocked actions
- confirmation-required actions
- domain summaries
- next step suggestion

## 6. Domain Summary Implementation

已实现 `summarize_review_by_domain()`，覆盖：

- `truth_state`
- `queue_sandbox`
- `memory`
- `asset`
- `mode`
- `tool_runtime`
- `prompt`
- `rtcm`

每个 domain 输出：

- `signal_count`
- `critical_count`
- `high_count`
- `medium_count`
- `top_signal_types`
- `recommended_action_types`
- `blocked_count`
- `requires_confirmation_count`

当前 sample domain 数量：8。

## 7. Top Action Candidates Rule

已实现 `select_top_action_candidates()`。

排序规则：

1. `critical`
2. `high`
3. `forbidden_auto` / `requires_user_confirmation`
4. prompt rollback / tool high-risk / rtcm unknown / memory unknown / queue mismatch
5. medium diagnostic

当前 sample：

- `selected_count=10`

该结果只用于摘要和人工审查，不写 action queue。

## 8. Feishu Card Payload Projection

已实现：

- `build_feishu_card_payload_projection()`
- `validate_feishu_payload_projection()`

当前 sample：

- `status=projection_only`
- `send_allowed=false`
- `webhook_required=true`
- validation: `valid=true`
- blocked_reasons: `[]`

Feishu card payload 只写入审计 sample，不调用 webhook，不推送。

## 9. Plaintext Summary

已实现 `build_plaintext_nightly_summary()`。

当前 sample：

- plaintext length = 1170
- 中文摘要包含关键数字、domain signals、Top Actions、projection-only 安全提示、下一步建议

## 10. Runtime Sample Summary

sample 文件：

- `migration_reports/foundation_audit/R241-8B_NIGHTLY_FEISHU_SUMMARY_SAMPLE.json`

sample 加载：

- source: `migration_reports/foundation_audit/R241-8A_NIGHTLY_FOUNDATION_HEALTH_REVIEW_SAMPLE.json`
- review_id: `nightly_review_5539144633`
- total_signals: 26
- action_candidate_count: 26
- top_action_candidates: 10
- domain_count: 8
- warnings: []

## 11. Test Results

RootGuard：

- `python scripts\root_guard.py` PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1` PASS

Compile：

- `python -m py_compile backend/app/nightly/foundation_health_review.py backend/app/nightly/foundation_health_summary.py` PASS

Nightly tests：

- `python -m pytest backend/app/nightly/test_foundation_health_review.py backend/app/nightly/test_foundation_health_summary.py -v`
- Result: `36 passed`

Previous RTCM tests:

- Result: `38 passed`

Previous Prompt tests:

- Result: `33 passed`

Previous ToolRuntime tests:

- Result: `36 passed`

Previous Mode / Gateway tests:

- Result: `30 passed`

Previous Asset tests:

- Result: `32 passed`

Previous Memory tests:

- Result: `24 passed`

Previous Truth / State tests:

- Result: `33 passed`

Gateway smoke:

- Result: `11 passed`

## 12. Runtime / Push / Action Queue Check

未执行：

- Feishu / Lark 真实推送
- webhook 调用
- 自动修复
- 真实工具调用
- asset promotion / elimination
- memory cleanup
- prompt replacement

未写入：

- action queue
- governance_state
- experiment_queue
- memory runtime
- asset runtime
- prompt runtime
- RTCM runtime

## 13. Current Remaining Breakpoints

- Feishu payload 仍是 projection-only，未接入真实 webhook。
- Summary 尚未接入真实 nightly scheduler/watchdog。
- Action candidates 尚未进入用户确认或 implementation readiness review。
- 后续如接入真实 Feishu，需要单独的 webhook policy、secret handling、rate limit、dry-run 和 audit trail。

## 14. Next Step

建议进入：

R241-9A Foundation Integration Readiness Review

下一轮应审查 R241-1A 到 R241-8B 的所有 wrapper/projection surface，判断哪些可以进入最小只读集成，哪些仍需保持报告态。

## 15. Final Verdict

A. R241-8B 成功，可进入 R241-9A Foundation Integration Readiness Review。
