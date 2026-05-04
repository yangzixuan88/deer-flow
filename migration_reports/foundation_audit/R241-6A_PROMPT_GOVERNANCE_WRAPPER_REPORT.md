# R241-6A PromptSourceRegistry / PromptGovernance Wrapper Report

## 1. 修改文件清单

新增文件：

- `backend/app/prompt/__init__.py`
- `backend/app/prompt/prompt_governance_contract.py`
- `backend/app/prompt/test_prompt_governance_contract.py`
- `migration_reports/foundation_audit/R241-6A_PROMPT_GOVERNANCE_SAMPLE.json`
- `migration_reports/foundation_audit/R241-6A_PROMPT_GOVERNANCE_WRAPPER_REPORT.md`

未修改文件：

- 未修改任何生产 prompt。
- 未修改 `SOUL.md`。
- 未修改 DeerFlow lead_agent prompt。
- 未修改 M09 Prompt Engine 主逻辑。
- 未写 prompt runtime。
- 未写 memory / asset / governance / gateway runtime。

## 2. PromptSourceRecord 字段

`PromptSourceRecord` 字段：

- `prompt_source_id`
- `source_type`
- `source_path`
- `owner_system`
- `priority_layer`
- `allowed_modes`
- `denied_modes`
- `can_override_lower_layer`
- `can_be_optimized`
- `optimization_status`
- `version`
- `rollback_available`
- `backup_refs`
- `rollback_refs`
- `asset_candidate_eligible`
- `risk_level`
- `source_hash`
- `last_verified_at`
- `warnings`
- `observed_at`

## 3. P1-P6 分类规则

已实现层级：

- `P1_hard_constraints`
- `P2_user_preferences`
- `P3_mode_collaboration`
- `P4_task_skill`
- `P5_runtime_context`
- `P6_identity_base`
- `unknown`

关键映射：

- `SOUL.md` -> `P6_identity_base`，`source_type=soul`，`risk_level=critical`，warning: `soul_is_identity_base_not_highest_override`
- hard constraints / RootGuard / safety / secrets / irreversible -> `P1_hard_constraints`
- user preference / high autonomy / user rule -> `P2_user_preferences`
- mode / orchestration / roundtable / workflow / autonomous / ModeInvocation / ModeCallGraph -> `P3_mode_collaboration`
- skill / task / tool / M09 / DeerFlow task prompt -> `P4_task_skill`
- context / memory / asset / tool event / governance / truth / state -> `P5_runtime_context`
- DeerFlow base identity / system base -> `P6_identity_base`
- DSPy / GEPA -> `P4_task_skill` candidate

## 4. Prompt conflict resolution 规则

`resolve_prompt_conflict()` 按层级优先级解决冲突：

`P1 > P2 > P3 > P4 > P5 > P6 > unknown`

规则：

- P1 永远胜出。
- P2 高于 P4/P5/P6。
- P3 高于 P4/P5/P6。
- P5 高于 P6。
- 同层冲突返回 `requires_review`。
- unknown 层不应覆盖 known 层，并返回 warning。

样例冲突：

- P2 user high-autonomy vs P4 conservative task prompt -> P2 wins。
- P1 hard constraint vs P6 identity prompt -> P1 wins。

## 5. Prompt replacement risk 规则

`assess_prompt_replacement_risk()` 已实现：

- P1 替换：critical，必须 user confirmation + backup + rollback + test + governance review。
- P2 替换：high，必须 backup + rollback + user confirmation 或 governance review。
- P3 替换：high，必须 test + rollback。
- P4 替换：production 为 high，candidate 为 medium。
- P5 替换：medium，必须避免 memory/context 泄漏。
- P6 / SOUL.md 替换：critical/high，SOUL.md 必须 backup + rollback + user confirmation。
- DSPy / GEPA candidate 不得直接替换 production，必须走 candidate path + test + backup + rollback + asset candidate。

## 6. Prompt asset candidate 规则

`project_prompt_asset_candidate()` 已实现只读 A7 判断：

- DSPy / GEPA / fewshot / skill prompt / reusable task prompt / mode prompt -> `A7_prompt_instruction` candidate。
- SOUL.md 不直接成为普通 A7 资产，标记为 `protected_identity_source`。
- P1 hard constraint 不作为普通 prompt asset，标记为 `protected_hard_constraint_source`。
- 不写 asset registry，不执行 asset promotion。

## 7. Prompt source scan / sample 摘要

样例文件：

`migration_reports/foundation_audit/R241-6A_PROMPT_GOVERNANCE_SAMPLE.json`

样例包含：

- SOUL.md
- user preference prompt
- mode orchestration prompt
- skill prompt
- runtime context prompt
- DSPy candidate
- GEPA candidate
- hard constraint prompt
- replacement risk
- conflict examples
- asset candidate projection

样例摘要：

- total: 8
- by layer:
  - P1: 1
  - P2: 1
  - P3: 1
  - P4: 3
  - P5: 1
  - P6: 1
- critical sources: 2
- optimization candidates: 2
- asset candidates: 4
- rollback_missing_count: 6

扫描实现说明：

- `scan_prompt_sources()` 只扫描路径和文件名。
- 不读取大文件全文。
- 不输出 prompt 全文。
- 排除 `node_modules`、`.git`、`__pycache__`、`dist`、`build`、`.venv`。

## 8. 测试结果

RootGuard：

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile：

- `python -m py_compile backend/app/prompt/prompt_governance_contract.py`: PASS

Prompt tests：

- `python -m pytest backend/app/prompt/test_prompt_governance_contract.py -v`: 18 passed

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

## 9. 是否修改生产 prompt

否。

本轮没有修改任何 prompt 文件，没有替换 SOUL.md，没有修改 DeerFlow lead_agent prompt，没有修改 M09 Prompt Engine。

## 10. 是否启用 GEPA / DSPy

否。

本轮仅识别 DSPy / GEPA candidate，并标记其不得直接替换 production。未执行真实 prompt optimization。

## 11. 是否替换 prompt runtime

否。

本轮没有写 prompt runtime，没有改变五大模式 prompt 组装逻辑，没有接入 Prompt Engine 主链。

## 12. 当前剩余断点

- PromptGovernance 仍是 wrapper，尚未接入 Prompt Engine / Gateway / ModeInvocation。
- 真实 prompt source registry 尚未统一读取。
- Prompt replacement risk 仍是 projection，不是 enforcement。
- DSPy / GEPA candidate 尚未与 ToolRuntime、TruthEvent、AssetLifecycle 建立自动闭环。
- P1/P2/P3 冲突规则尚未进入实际 prompt assembly。

## 13. 下一步建议

进入 R241-6B：Prompt Read-only Projection 接入。

建议下一轮继续只读扫描真实 prompt sources，输出 PromptSourceRegistry projection、replacement risk summary、A7 prompt asset candidates，不修改任何生产 prompt。

## 14. 最终判定

A. R241-6A 成功，可进入 R241-6B Prompt Read-only Projection 接入。
