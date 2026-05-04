# R241-7B RTCM Read-only Runtime Projection Report

## 1. Modification Scope

新增文件：

- `backend/app/rtcm/rtcm_runtime_projection.py`
- `backend/app/rtcm/test_rtcm_runtime_projection.py`
- `migration_reports/foundation_audit/R241-7B_RTCM_RUNTIME_PROJECTION_SAMPLE.json`
- `migration_reports/foundation_audit/R241-7B_RTCM_RUNTIME_PROJECTION_REPORT.md`

本轮未修改 RTCM 状态机、RTCM session runtime、dossier/final_report/signoff/followup、governance_state、memory runtime、asset runtime。

## 2. RTCMRuntimePathProjection Fields

`RTCMRuntimePathProjection` 字段：

- `runtime_ref_id`
- `source_path`
- `surface_type`
- `runtime_role`
- `artifact_type`
- `rtcm_session_id`
- `context_id`
- `gateway_thread_id`
- `mode_session_id`
- `mode_invocation_id`
- `is_runtime_state`
- `is_source_code`
- `is_config`
- `is_prompt`
- `is_report`
- `is_session_artifact`
- `truth_candidate_eligible`
- `asset_candidate_eligible`
- `memory_candidate_eligible`
- `followup_candidate_eligible`
- `should_output_content`
- `warnings`
- `observed_at`

所有 projection 均为只读路径/元数据投影，`should_output_content=false`，不输出 RTCM artifact 全文。

## 3. RTCMSessionRuntimeProjection Fields

`RTCMSessionRuntimeProjection` 字段：

- `session_projection_id`
- `rtcm_session_id`
- `session_root`
- `status`
- `manifest_refs`
- `runtime_state_refs`
- `dossier_refs`
- `final_report_refs`
- `signoff_refs`
- `evidence_refs`
- `council_log_refs`
- `followup_refs`
- `context_links`
- `mode_links`
- `truth_candidate_refs`
- `asset_candidate_refs`
- `memory_candidate_refs`
- `warnings`
- `observed_at`

session projection 只聚合引用路径，不改 session 状态，不 close/archive/signoff/reopen。

## 4. RTCMContextLinkProjection Fields

`RTCMContextLinkProjection` 字段：

- `link_projection_id`
- `rtcm_session_id`
- `context_id`
- `request_id`
- `gateway_thread_id`
- `mode_session_id`
- `mode_invocation_id`
- `source_path`
- `link_type`
- `confidence`
- `warnings`
- `observed_at`

context link 是只读推断，不写 ContextLink runtime，也不合并 `rtcm_session_id` 与 Gateway `thread_id`。

## 5. Runtime Taxonomy Implementation

新增 runtime taxonomy：

- `rtcm_session_runtime`
- `rtcm_project_dossier`
- `rtcm_config_spec`
- `rtcm_prompt_template`
- `rtcm_source_code`
- `rtcm_test_file`
- `rtcm_docs`
- `rtcm_example_project`
- `rtcm_runtime_state`
- `rtcm_evidence_extract`
- `rtcm_validation_run`
- `rtcm_report`
- `rtcm_schema_spec`
- `rtcm_feishu_bridge`
- `rtcm_recovery_component`
- `rtcm_observability_component`
- `rtcm_unknown`

新增 runtime role：

- `session_state`
- `session_manifest`
- `project_context`
- `council_transcript`
- `evidence`
- `final_decision`
- `followup_action`
- `config`
- `prompt`
- `source`
- `test`
- `documentation`
- `adapter`
- `runtime_cache`
- `validation`
- `unknown`

关键规则：

- `rtcm/config/*.yaml` -> `rtcm_config_spec / config`，不进入 truth/asset/memory candidate。
- `rtcm/prompts/*.md` -> `rtcm_prompt_template / prompt`，不进入 rtcm_truth。
- `rtcm/docs/*.md` -> `rtcm_docs / documentation`，不进入 rtcm_truth。
- `backend/src/rtcm/*.ts|*.mjs` -> `rtcm_source_code` 或 `rtcm_test_file`，不作为 session artifact。
- `runtime/session_state.json` -> `rtcm_runtime_state / session_state`。
- `runtime/evidence_extracts/*.json` -> `rtcm_evidence_extract / evidence`，可为 memory candidate，但不是直接 rtcm_truth。
- `project_dossier/final_report.md` -> `final_decision`，truth/asset/memory candidate eligible。
- `project_dossier/evidence_ledger.json` -> `evidence`，truth/asset/memory candidate eligible。
- `project_dossier/council_log.jsonl` -> `council_transcript`，不长期化，不作为 asset/truth candidate。

## 6. Session Discovery / Session-level Projection

runtime sample：

- `classified_count=663`
- `session_count=3`
- `truth_candidate_count=15`
- `asset_candidate_count=18`
- `memory_candidate_count=77`
- `followup_candidate_count=12`

surface 分布：

- `rtcm_unknown=214`
- `rtcm_docs=17`
- `rtcm_validation_run=2`
- `rtcm_config_spec=38`
- `rtcm_prompt_template=12`
- `rtcm_example_project=2`
- `rtcm_project_dossier=85`
- `rtcm_runtime_state=2`
- `rtcm_evidence_extract=3`
- `rtcm_session_runtime=178`
- `rtcm_test_file=48`
- `rtcm_source_code=34`
- `rtcm_feishu_bridge=9`
- `rtcm_recovery_component=19`

role 分布：

- `unknown=214`
- `documentation=17`
- `validation=2`
- `config=38`
- `prompt=12`
- `project_context=61`
- `council_transcript=4`
- `evidence=6`
- `final_decision=12`
- `session_manifest=173`
- `session_state=2`
- `followup_action=12`
- `test=48`
- `source=34`
- `adapter=28`

## 7. Context Link Projection

已实现：

- `project_rtcm_context_links(session_projection, mode_metadata, context_envelope)`
- 有 `context_id/request_id/thread_id` 时生成 `belongs_to_context` / `belongs_to_thread` link。
- 有 `mode_session_id/mode_invocation_id` 时生成 `belongs_to_mode_session` / `belongs_to_mode_invocation` link。
- 无 context 时只返回 `missing_context_link` warning，不阻断、不写 runtime。

runtime sample 当前风险中包含：

- `session_missing_context_link=3`

这表示真实 RTCM session 尚未有可投影的 Gateway/Mode context metadata，属于后续接入点，不是本轮失败。

## 8. Truth / Asset / Memory / Followup Projection

已实现：

- `project_rtcm_runtime_truth_asset_memory_followup(session_projection)`
- 复用 R241-7A 的 `project_rtcm_truth_candidates`
- 复用 R241-7A 的 `project_rtcm_asset_candidates`
- 复用 R241-7A 的 `project_rtcm_memory_candidates`
- 复用 R241-7A 的 `project_rtcm_followups`

规则保持：

- `final_report` 可成为 `rtcm_truth` / asset candidate / memory candidate。
- `evidence_ledger` 可成为 evidence summary / source-network or knowledge-map asset candidate / memory candidate。
- `council_log` 不进入长期记忆，不作为资产候选，不直接成为 rtcm_truth。
- `followup` 只生成 task/workflow/autonomous_agent/roundtable target mode candidate，不执行 followup。

## 9. Unknown Taxonomy Reduction

R241-7A runtime sample：

- classified artifacts = 352
- unknown artifact type = 246

R241-7B runtime sample：

- classified runtime paths = 663
- unknown runtime surface = 214

结果：

- unknown 从 246 降到 214，减少 32。
- 新增 taxonomy 成功吸收 config/docs/prompts/source/tests/runtime_state/project_dossier/session_runtime/support bridge/recovery 等支持文件。
- 剩余 `rtcm_unknown=214` 主要仍为无法仅凭路径安全归类的 support/runtime 文件，后续可通过内容 schema 或 manifest link 继续降低，但本轮不读取全文、不修改 runtime。

## 10. Risk Signals

runtime sample 风险：

- `risk_count=219`
- `unknown_rtcm_runtime_surface=214`
- `session_missing_manifest=2`
- `session_missing_context_link=3`

诊断含义：

- `unknown_rtcm_runtime_surface`：路径 taxonomy 仍需后续细化。
- `session_missing_manifest`：部分 session-like root 缺 manifest，不自动修复。
- `session_missing_context_link`：session 与 Gateway/Mode metadata 尚未建立 runtime link，不写入 ContextLink。

未发现本轮由 projection 造成的 runtime 修改。

## 11. Test Results

RootGuard：

- `python scripts\root_guard.py` PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1` PASS

Compile：

- `python -m py_compile backend/app/rtcm/rtcm_integration_contract.py backend/app/rtcm/rtcm_runtime_projection.py` PASS

RTCM tests：

- `python -m pytest backend/app/rtcm/test_rtcm_integration_contract.py backend/app/rtcm/test_rtcm_runtime_projection.py -v`
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

Gateway smoke：

- Result: `11 passed`

## 12. Runtime Mutation Check

未修改：

- RTCM 状态机
- RTCM session runtime
- RTCM dossier / final_report / signoff / followup
- `rtcm/config`
- `rtcm/prompts`
- `rtcm/docs`
- Feishu / Lark bridge
- M01 / M04 / Gateway / DeerFlow run 主路径
- governance_state
- memory runtime
- asset runtime

未执行：

- RTCM session create / close / archive / reopen / signoff
- final_report asset registration
- council_log long-term memory write

## 13. Current Remaining Breakpoints

- RTCM runtime taxonomy 仍有 `rtcm_unknown=214`，但已低于 R241-7A unknown=246。
- 真实 session-level context link 仍缺失，当前只能 projection warning。
- 部分 session-like root 缺 manifest，需要后续只读 schema 对齐或由 RTCM 运行链路补 metadata。

## 14. Next Step

建议进入：

R241-8A Nightly Foundation Health Review Wrapper

下一轮应继续保持 wrapper / projection-only，聚合 Truth/State、Memory、Asset、Mode、ToolRuntime、Prompt、RTCM 的只读 health signals，生成 Nightly Foundation Health Review，不自动修复高风险项。

## 15. Final Verdict

A. R241-7B 成功，可进入 R241-8A Nightly Foundation Health Review Wrapper。
