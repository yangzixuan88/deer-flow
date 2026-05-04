# R241-6B Prompt Read-only Projection Report

## 1. 修改文件清单

新增文件：

- `backend/app/prompt/prompt_projection.py`
- `backend/app/prompt/test_prompt_projection.py`
- `migration_reports/foundation_audit/R241-6B_PROMPT_PROJECTION_RUNTIME_SAMPLE.json`
- `migration_reports/foundation_audit/R241-6B_PROMPT_READONLY_PROJECTION_REPORT.md`

未修改文件：

- 未修改任何生产 prompt。
- 未修改 `SOUL.md`。
- 未修改 DeerFlow lead_agent prompt。
- 未修改 M09 Prompt Engine 主逻辑。
- 未写 prompt runtime。
- 未写 memory / asset / governance / gateway runtime。

## 2. 新增 projection helper 函数

新增函数：

- `discover_prompt_runtime_paths(root=None)`
- `load_prompt_source_snapshot(path)`
- `project_prompt_sources(root=None, max_files=500)`
- `project_prompt_replacement_risks(records)`
- `project_prompt_asset_candidates(records)`
- `detect_prompt_governance_risks(projection)`
- `aggregate_prompt_projection(root=None, max_files=500)`
- `generate_prompt_projection_report(output_path=None, root=None, max_files=500)`

实现约束：

- 复用 R241-6A `classify_prompt_source()`、`scan_prompt_sources()`、`assess_prompt_replacement_risk()`、`project_prompt_asset_candidate()`。
- 不复制 PromptSourceRecord / P1-P6 / conflict / replacement risk 逻辑。
- 不输出完整 prompt 内容。
- 不写 prompt runtime。

## 3. Prompt runtime paths discovery 结果

Runtime sample：

`migration_reports/foundation_audit/R241-6B_PROMPT_PROJECTION_RUNTIME_SAMPLE.json`

发现摘要：

- discovered prompt-related paths: 265
- checked expected paths including `SOUL.md`、`MEMORY.md`、`AGENTS.md`、`backend/app/prompt`、DeerFlow agents、R241-6A sample
- 缺失 expected paths 会记录在 `missing_expected_paths`
- 只列路径、存在性、类型和 classification hint
- 不读取 prompt 全文

## 4. Prompt source projection 摘要

本轮 sample 使用 `max_files=500`。

结果：

- scanned/classified: 500
- by layer:
  - `P3_mode_collaboration`: 270
  - `P4_task_skill`: 140
  - `P6_identity_base`: 18
  - `P5_runtime_context`: 8
  - `unknown`: 64
- critical_sources_count: 1
- asset_candidate_count: 359
- rollback_missing_count: 293

records 仅包含：

- path
- hash
- source_type
- layer
- risk
- optimization_status
- asset_candidate_eligible
- rollback_available
- warnings

不包含完整 prompt 内容。

## 5. Replacement risk summary

Replacement risk 使用 R241-6A `assess_prompt_replacement_risk()` 逐条投影。

Sample summary：

- critical replacement sources: 1
- high replacement sources: derived from P2/P3/P6 high-risk prompt records
- rollback_required_count: 覆盖全部 replacement risk records
- backup_required_count: 覆盖全部 replacement risk records
- test_required_count: 覆盖全部 replacement risk records
- user_confirmation_required_count: 覆盖 P1/P2/P6/SOUL/unknown 高保护类
- governance_review_required_count: 覆盖 P1/P2 等需治理审查类

本轮不执行替换、不写 prompt runtime。

## 6. A7 Prompt asset candidate summary

Prompt asset candidates 使用 R241-6A `project_prompt_asset_candidate()`。

Sample summary：

- candidate_count: 359
- 允许候选：
  - DSPy / GEPA / fewshot
  - reusable skill prompt
  - reusable task prompt
  - mode prompt
- protected sources:
  - `SOUL.md` 不作为普通 A7 资产
  - P1 hard constraints 不作为普通 A7 资产

本轮不写 asset registry，不执行 asset promotion。

## 7. Prompt governance risk signals

Sample risk signals：

- total risk_count: 734
- `rollback_missing`: 293
- `backup_missing`: 293
- `unknown_prompt_source`: 64
- `unknown_prompt_layer`: 64
- `runtime_context_prompt_leakage_review_required`: 8
- `generated_prompt_candidate_without_test`: 5
- `dspy_gepa_direct_replace_forbidden`: 5
- `critical_prompt_without_rollback`: 1
- `soul_replacement_requires_user_confirmation`: 1

这些是只读诊断信号，不触发修复、不阻止运行。

## 8. Runtime sample 位置与摘要

文件：

`migration_reports/foundation_audit/R241-6B_PROMPT_PROJECTION_RUNTIME_SAMPLE.json`

内容：

- discovered_paths
- source_projection
- replacement_risks
- asset_candidates
- risk_signals
- generated_at
- warnings

该文件是审计报告样例，不是 prompt runtime state。

## 9. 测试结果

RootGuard：

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile：

- `python -m py_compile backend/app/prompt/prompt_governance_contract.py backend/app/prompt/prompt_projection.py`: PASS

Prompt tests：

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

## 10. 是否修改生产 Prompt

否。

本轮没有修改、替换、删除任何 prompt 文件，没有修改 `SOUL.md` 或 DeerFlow lead_agent prompt。

## 11. 是否启用 GEPA / DSPy

否。

本轮只识别 DSPy / GEPA candidate，不运行优化器，不生成生产替换。

## 12. 是否改变 Prompt runtime / prompt assembly

否。

本轮没有写 prompt runtime，没有接入 Prompt Engine 主链，没有改变五大模式 prompt 组装逻辑。

## 13. 当前剩余断点

- 真实 PromptSourceRegistry 尚未持久化。
- unknown prompt source / layer 数量仍需后续人工或规则补全。
- replacement risk 仍是 projection，不是 enforcement。
- A7 candidate 仍未接入 Asset registry。
- GEPA/DSPy candidate 尚未进入测试、评分、rollback、governance gate。

## 14. 下一步建议

进入 R241-7A：RTCM / Roundtable Integration Instrumentation。

建议下一轮继续保持 instrumentation-only：先投影 RTCM session / dossier / final_report / signoff 与 ModeInvocation、TruthEvent、AssetCandidate 的引用关系，不改变 RTCM 状态机。

## 15. 最终判定

A. R241-6B 成功，可进入 R241-7A RTCM / Roundtable Integration Instrumentation。
