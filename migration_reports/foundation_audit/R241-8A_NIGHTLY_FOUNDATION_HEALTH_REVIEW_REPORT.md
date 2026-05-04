# R241-8A Nightly Foundation Health Review Wrapper Report

## 1. Modification Scope

新增文件：

- `backend/app/nightly/__init__.py`
- `backend/app/nightly/foundation_health_review.py`
- `backend/app/nightly/test_foundation_health_review.py`
- `migration_reports/foundation_audit/R241-8A_NIGHTLY_FOUNDATION_HEALTH_REVIEW_SAMPLE.json`
- `migration_reports/foundation_audit/R241-8A_NIGHTLY_FOUNDATION_HEALTH_REVIEW_REPORT.md`

审计目录中另有首次 sample 生成过程中产生的辅助样例文件：

- `migration_reports/foundation_audit/R241-8A_MODE_HEALTH_SAMPLE.json`
- `migration_reports/foundation_audit/R241-8A_TOOL_RUNTIME_HEALTH_SAMPLE.json`
- `migration_reports/foundation_audit/R241-8A_TOOL_GATEWAY_MODE_HEALTH_SAMPLE.json`

这些文件均位于 `migration_reports/foundation_audit`，不是 runtime state、不是 action queue、不是 governance/memory/asset/prompt/RTCM 数据。

## 2. FoundationHealthSignal Fields

`FoundationHealthSignal` 字段：

- `signal_id`
- `domain`
- `severity`
- `signal_type`
- `message`
- `source_system`
- `source_ref`
- `affected_refs`
- `metric_name`
- `metric_value`
- `evidence_refs`
- `recommended_action_type`
- `action_permission`
- `requires_user_confirmation`
- `requires_backup`
- `requires_rollback`
- `warnings`
- `observed_at`

## 3. FoundationActionCandidate Fields

`FoundationActionCandidate` 字段：

- `action_candidate_id`
- `domain`
- `action_type`
- `title`
- `description`
- `severity`
- `permission`
- `source_signal_ids`
- `target_refs`
- `auto_executable`
- `requires_user_confirmation`
- `requires_backup`
- `requires_rollback`
- `blocked_reason`
- `suggested_next_step`
- `warnings`
- `created_at`

ActionCandidate 只是 projection，不写真实 action queue，不执行修复。

## 4. NightlyFoundationHealthReview Fields

`NightlyFoundationHealthReview` 字段：

- `review_id`
- `generated_at`
- `root`
- `domain_summaries`
- `total_signals`
- `by_severity`
- `critical_count`
- `high_count`
- `action_candidate_count`
- `auto_allowed_count`
- `requires_confirmation_count`
- `blocked_high_risk_count`
- `signals`
- `action_candidates`
- `warnings`

## 5. Domain Collector Implementation

已实现 collector：

- `collect_truth_state_health()`
- `collect_memory_health()`
- `collect_asset_health()`
- `collect_mode_health()`
- `collect_tool_runtime_health()`
- `collect_prompt_health()`
- `collect_rtcm_health()`

实现原则：

- 复用现有 projection 模块。
- 任一 collector 失败只转 warning + signal，不中断整体聚合。
- 不写 runtime。
- 不创建真实 action queue。
- 不执行任何自动修复。

当前 sample domain summary：

- `truth_state`: queue missing diagnostic、sandbox execution truth 17、simple raw execution truth rate 0.2941。
- `memory`: classified 263、long-term candidates 14、asset candidates 7、risk count 272。
- `asset`: total projected 26、candidate count 26、formal asset count 12、risk count 0。
- `mode`: sample invocation count 2、Gateway run path 未修改。
- `tool_runtime`: sample event count 3、risk count 7。
- `prompt`: classified 500、A7 candidates 353、risk count 748。
- `rtcm`: classified 665、unknown 216、session count 3、risk count 216。

## 6. Health Signal Normalization Rules

已实现 `normalize_health_signal()`。

核心映射：

- unknown taxonomy -> `medium / refine_taxonomy`
- missing context link -> `medium / add_context_link`
- missing backup -> `high / add_backup`
- missing rollback -> `high / add_rollback`
- generated prompt without test -> `high / add_test`
- high-risk operation without confirmation -> `critical / requires_user_confirmation`
- asset candidate unverified -> `medium / review_asset_candidate`
- memory candidate unverified -> `medium / review_memory_candidate`
- rtcm followup/session issue -> `medium / review_rtcm_session`

## 7. Action Candidate Permission Rules

已实现 `create_action_candidate_from_signal()`。

权限规则：

- info/low diagnostic -> `report_only` 或 `auto_allowed_low_risk`
- medium diagnostic -> `report_only`
- high -> `requires_backup` / `requires_rollback` / `requires_user_confirmation`
- critical -> `forbidden_auto` 或 `requires_user_confirmation`
- prompt replacement / memory cleanup / asset elimination / RTCM state mutation / governance write -> 默认 `forbidden_auto`，除非后续用户显式确认并提供备份/回滚方案

当前 sample：

- `action_candidate_count=26`
- `auto_allowed_count=0`
- `requires_confirmation_count=6`
- `blocked_high_risk_count=2`

## 8. Runtime Sample Summary

sample 文件：

- `migration_reports/foundation_audit/R241-8A_NIGHTLY_FOUNDATION_HEALTH_REVIEW_SAMPLE.json`

sample 统计：

- `total_signals=26`
- `by_severity={'medium': 13, 'info': 1, 'high': 10, 'critical': 2}`
- `action_candidate_count=26`
- `auto_allowed_count=0`
- `requires_confirmation_count=6`
- `blocked_high_risk_count=2`
- `warnings_count=24`

本 sample 是审计报告，不是真实 nightly state。

## 9. Test Results

RootGuard：

- `python scripts\root_guard.py` PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1` PASS

Compile：

- `python -m py_compile backend/app/nightly/foundation_health_review.py` PASS

Nightly tests：

- `python -m pytest backend/app/nightly/test_foundation_health_review.py -v`
- Result: `20 passed`

Previous RTCM tests：

- Result: `38 passed`

Previous Prompt tests：

- Result: `33 passed`

Previous ToolRuntime tests：

- Result: `36 passed`

Previous Mode / Gateway tests：

- Result: `30 passed`

Previous Asset tests：

- Result: `32 passed`

Previous Memory tests：

- Result: `24 passed`

Previous Truth / State tests：

- Result: `33 passed`

Gateway smoke:

- Result: `11 passed`

## 10. Runtime / Action Queue Mutation Check

未修改：

- `governance_state.json`
- `experiment_queue.json`
- memory.json / Qdrant / SQLite / checkpoints
- asset_registry / binding report / DPBS runtime
- prompt runtime / SOUL.md / DeerFlow prompts
- RTCM 状态机 / session / dossier / final_report / signoff / followup
- Gateway / M01 / M04 / DeerFlow run 主路径

未执行：

- 真实工具调用
- 自动修复
- 真实 action queue 创建
- asset promotion / elimination
- memory cleanup
- prompt replacement
- RTCM state mutation

## 11. Current Remaining Breakpoints

- Nightly 当前仍是 wrapper/sample 聚合器，未接入真实 scheduler/watchdog。
- action candidates 只生成 projection，不会进入生产 action queue。
- Prompt rollback/backup 风险、RTCM unknown taxonomy、Memory unknown artifacts 仍是主要 health signals。
- Queue path missing 仍作为 diagnostic warning 保留。

## 12. Next Step

建议进入：

R241-8B Nightly Read-only Projection / Feishu Summary 接入

下一轮仍应只做 read-only projection：将 Nightly review 输出整理成稳定 summary surface，可选生成 Feishu 摘要 payload，但不得真实推送、不得写 action queue、不得执行修复。

## 13. Final Verdict

A. R241-8A 成功，可进入 R241-8B Nightly Read-only Projection / Feishu Summary 接入。
