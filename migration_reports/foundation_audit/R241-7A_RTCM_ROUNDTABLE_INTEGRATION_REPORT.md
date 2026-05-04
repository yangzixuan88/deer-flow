# R241-7A RTCM / Roundtable Integration Instrumentation Report

## 1. 修改文件清单

新增文件：

- `backend/app/rtcm/__init__.py`
- `backend/app/rtcm/rtcm_integration_contract.py`
- `backend/app/rtcm/test_rtcm_integration_contract.py`
- `migration_reports/foundation_audit/R241-7A_RTCM_ROUNDTABLE_INTEGRATION_SAMPLE.json`
- `migration_reports/foundation_audit/R241-7A_RTCM_ROUNDTABLE_INTEGRATION_REPORT.md`

未修改文件：

- 未修改 RTCM 状态机。
- 未修改 RTCM session runtime。
- 未修改 RTCM dossier / final_report / signoff / followup 文件。
- 未修改 Feishu / Lark bridge。
- 未修改 M01 / M04 / Gateway / DeerFlow run 主路径。
- 未写 governance_state / memory / asset / prompt runtime。

## 2. RoundtableSessionProjection 字段

`RoundtableSessionProjection` 字段：

- `roundtable_session_ref_id`
- `executor`
- `rtcm_session_id`
- `context_id`
- `request_id`
- `gateway_thread_id`
- `mode_session_id`
- `mode_invocation_id`
- `status`
- `topic`
- `artifact_refs`
- `truth_candidate_refs`
- `asset_candidate_refs`
- `memory_candidate_refs`
- `followup_refs`
- `source_path`
- `warnings`
- `observed_at`

语义：

- Roundtable 是五大模式之一。
- RTCM 是当前主要 roundtable executor。
- roundtable mode 不等于 RTCM。
- `rtcm_session_id` 与 gateway `thread_id` 不合并，只通过 projection / ModeInvocation / ContextLink 关联。

## 3. RTCMArtifactProjection 字段

`RTCMArtifactProjection` 字段：

- `artifact_ref_id`
- `artifact_type`
- `source_path`
- `rtcm_session_id`
- `context_id`
- `producer`
- `consumer_candidates`
- `truth_event_eligible`
- `asset_candidate_eligible`
- `memory_candidate_eligible`
- `long_term_memory_eligible`
- `warnings`
- `observed_at`

## 4. RTCMTruthProjection 字段

`RTCMTruthProjection` 字段：

- `truth_candidate_id`
- `truth_type`
- `truth_track=rtcm_truth`
- `source_artifact_ref`
- `rtcm_session_id`
- `subject_type`
- `subject_id`
- `evidence_refs`
- `confidence`
- `warnings`
- `observed_at`

语义：

- `rtcm_truth` 不等于 `execution_truth`。
- `final_report` 不等于 task success。
- `archived` 不等于 user goal success。

## 5. RTCM artifact classification 规则

已实现 artifact 类型：

- `session_manifest`
- `dossier`
- `brief_report`
- `council_log`
- `evidence_ledger`
- `final_report`
- `issue_card`
- `signoff`
- `followup`
- `verdict`
- `unknown`

关键规则：

- `final_report`: truth eligible, asset candidate, memory candidate, long-term memory candidate。
- `signoff`: truth eligible, not ordinary asset candidate, not memory candidate。
- `evidence_ledger`: truth eligible, asset candidate, memory candidate, long-term memory candidate。
- `council_log`: not truth candidate, not asset candidate, not memory candidate, not long-term; warning `council_log_not_long_term_memory`。
- `followup`: followup candidate。
- unknown: `unknown_rtcm_artifact_type` warning。

## 6. rtcm_truth / asset_candidate / memory_candidate / followup projection 规则

Truth candidates：

- final_report -> `final_report_conclusion`
- signoff -> `signoff_decision`
- verdict -> `rtcm_verdict`
- evidence_ledger -> `evidence_summary`
- council_log excluded

Asset candidates：

- final_report -> `A5_cognitive_method`
- evidence_ledger -> `A6_information_source_network`
- issue_card -> `A4_execution_experience`
- brief_report -> `A3_workflow_solution`
- council_log excluded
- returns candidate only, does not write asset registry

Memory candidates：

- final_report / brief_report -> L3 candidate
- evidence_ledger -> L4 candidate
- dossier -> L2/session-like candidate
- council_log excluded from long-term memory
- signoff is truth source, not direct memory source

Followups：

- fix / verify / run test -> task
- multi-step / plan / pipeline -> workflow
- monitor / recurring / long-running -> autonomous_agent
- dispute / review / decision -> roundtable
- unknown -> warning

## 7. ModeInvocation link 规则

`link_rtcm_to_mode_invocation()` 已实现：

- 返回 roundtable projection copy。
- 关联 `mode_session_id` / `mode_invocation_id`。
- 当 `mode_invocation.to_mode=roundtable` 且 `executor=rtcm` 时 `link_ok=true`。
- 缺 mode_invocation 时返回 `missing_mode_invocation` warning。
- 不写 runtime。

## 8. runtime sample 摘要

样例文件：

`migration_reports/foundation_audit/R241-7A_RTCM_ROUNDTABLE_INTEGRATION_SAMPLE.json`

Sample scan 使用 `max_files=500`。

结果：

- classified artifacts: 352
- truth candidates: 16
- asset candidates: 18
- memory candidates: 80
- followup candidates: 19
- risk_count: 264

by artifact type：

- unknown: 246
- session_manifest: 5
- dossier: 62
- brief_report: 6
- council_log: 4
- evidence_ledger: 3
- final_report: 6
- issue_card: 3
- followup: 10
- signoff: 6
- verdict: 1

risk signals：

- `rtcm_artifact_unknown_type`: 246
- `followup_without_target_mode`: 18

说明：

- unknown 数量高说明 RTCM 相关路径中存在大量尚未纳入 artifact taxonomy 的文件，需要 R241-7B 进一步 runtime projection 分层。
- sample 不输出完整 RTCM 内容。

## 9. 测试结果

RootGuard：

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile：

- `python -m py_compile backend/app/rtcm/rtcm_integration_contract.py`: PASS

RTCM tests：

- `python -m pytest backend/app/rtcm/test_rtcm_integration_contract.py -v`: 18 passed

Previous Prompt tests：

- `python -m pytest backend/app/prompt/test_prompt_governance_contract.py backend/app/prompt/test_prompt_projection.py -v`: 33 passed

Previous ToolRuntime tests：

- `python -m pytest backend/app/tool_runtime/test_tool_runtime_contract.py backend/app/tool_runtime/test_tool_runtime_projection.py -v`: 36 passed

Previous Mode / Gateway tests：

- `python -m pytest backend/app/mode/test_mode_orchestration_contract.py backend/app/gateway/test_mode_instrumentation_smoke.py -v`: 30 passed

Previous Asset tests：

- `python -m pytest backend/app/asset/test_asset_lifecycle_contract.py backend/app/asset/test_asset_projection.py -v`: 32 passed

Previous Memory tests：

- `python -m pytest backend/app/memory/test_memory_layer_contract.py backend/app/memory/test_memory_projection.py -v`: 24 passed

Previous Truth/State tests：

- `python -m pytest backend/app/m11/test_truth_state_contract.py backend/app/m11/test_governance_truth_projection.py backend/app/m11/test_queue_sandbox_truth_projection.py -v`: 33 passed

Gateway smoke：

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: 11 passed

## 10. 是否修改 RTCM 状态机 / session / dossier

否。

本轮没有修改 RTCM 状态机、session runtime、dossier、final_report、signoff、followup、Feishu/Lark bridge，也没有自动创建、关闭、archive 或 signoff RTCM session。

## 11. 是否写 governance / memory / asset runtime

否。

本轮只写入代码、测试、migration_reports 下样例和报告。未写 governance_state、memory runtime、asset registry、prompt runtime。

## 12. 当前剩余断点

- RTCM artifact unknown 类型数量高，需 R241-7B 针对真实 runtime 目录继续细分 taxonomy。
- RoundtableSessionProjection 尚未接入真实 RTCM session manifest。
- `rtcm_truth` candidates 仍未转为 TruthEvent。
- final_report / evidence_ledger 仍只是 asset/memory candidates，未进入 asset registry 或 long-term memory。
- followup candidates 尚未接入 ModeInvocation 或 action queue。

## 13. 下一步建议

进入 R241-7B：RTCM Read-only Runtime Projection 接入。

建议下一轮只读扫描真实 RTCM runtime structure，补齐 session-level projection、context link projection、unknown artifact taxonomy，不改变 RTCM 状态机。

## 14. 最终判定

A. R241-7A 成功，可进入 R241-7B RTCM Read-only Runtime Projection 接入。
