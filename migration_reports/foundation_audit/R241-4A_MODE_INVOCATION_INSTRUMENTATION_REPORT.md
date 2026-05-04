# R241-4A ModeInvocation / ModeCallGraph Instrumentation Report

## 1. 修改文件清单

新增文件：

- `backend/app/mode/__init__.py`
- `backend/app/mode/mode_orchestration_contract.py`
- `backend/app/mode/test_mode_orchestration_contract.py`
- `migration_reports/foundation_audit/R241-4A_MODE_CALLGRAPH_RUNTIME_SAMPLE.json`
- `migration_reports/foundation_audit/R241-4A_MODE_INVOCATION_INSTRUMENTATION_REPORT.md`

未修改文件：

- 未修改 M01 IntentClassifier。
- 未修改 M04 Coordinator。
- 未修改 RTCM 状态机。
- 未修改 Gateway / DeerFlow run 逻辑。
- 未写入 `governance_state.json`。
- 未写入 memory / asset / prompt runtime。

## 2. ModeSession / ModeInvocation / ModeResult / ModeCallGraph 字段

### ModeSession

字段：

- `mode_session_id`
- `context_id`
- `request_id`
- `thread_id`
- `primary_mode`
- `active_modes`
- `status`
- `owner_system`
- `created_at`
- `updated_at`
- `warnings`

### ModeInvocation

字段：

- `mode_invocation_id`
- `mode_session_id`
- `from_mode`
- `to_mode`
- `reason`
- `parent_context_id`
- `child_context_id`
- `return_policy`
- `requires_user_confirmation`
- `status`
- `started_at`
- `finished_at`
- `result_ref`
- `executor`
- `warnings`

### ModeResult

字段：

- `mode_result_id`
- `mode_invocation_id`
- `from_mode`
- `to_mode`
- `result_type`
- `output_refs`
- `truth_event_refs`
- `state_event_refs`
- `asset_candidate_refs`
- `memory_refs`
- `created_at`
- `warnings`

### ModeCallGraph

字段：

- `mode_session_id`
- `primary_mode`
- `nodes`
- `edges`
- `invocations`
- `results`
- `created_at`
- `updated_at`
- `warnings`

## 3. create_mode_session 实现

`create_mode_session()` 只创建并返回 `ModeSession` dict，不触发任何现有模式执行逻辑。

实现规则：

- `primary_mode` 非法时映射为 `unknown` 并写入 warning。
- `active_modes` 自动包含 `primary_mode`。
- `active_modes` 去重并按稳定顺序输出。
- 默认 `owner_system=mode_instrumentation`。
- 默认 `status=started`。

## 4. create_mode_invocation 实现

`create_mode_invocation()` 只创建并返回 `ModeInvocation` dict，不执行子模式、不触发工具、不切换主模式。

实现规则：

- 支持 `search`、`task`、`workflow`、`autonomous_agent`、`roundtable`、`direct_answer`、`clarification`、`governance_review`、`mixed_mode`、`unknown`。
- 非法 `from_mode` / `to_mode` 映射为 `unknown` 并写入 warning。
- 非法 `return_policy` 映射为 `return_to_parent` 并写入 warning。
- RTCM 可通过 `executor="rtcm"` 记录为 roundtable 当前执行器。
- 默认 `status=planned`。

## 5. complete_mode_invocation 实现

`complete_mode_invocation()` 返回：

- `updated_invocation`
- `mode_result`

实现规则：

- 不执行任何外部动作。
- 将 invocation status 更新为 `completed`。
- 生成 `ModeResult`，并保留 output / truth / state / asset / memory 引用。
- 非法 `result_type` 映射为 `unknown` 并写入 warning。
- `updated_invocation.result_ref` 指向生成的 `mode_result_id`。

## 6. build_mode_call_graph 实现

`build_mode_call_graph()` 只基于输入 session / invocations / results 构建图结构，不执行模式逻辑。

实现规则：

- nodes 包含 `primary_mode` 以及所有 `from_mode` / `to_mode`。
- edges 逐条保留 invocation，支持 repeated edge。
- edge metadata 保留 `executor`、`return_policy`、`requires_user_confirmation`、`status`、`reason`。
- 支持 `roundtable` 使用 `executor=rtcm` 的 metadata。
- 调用 `validate_mode_invocation_policy()` 生成诊断 warnings，但不阻止执行。

## 7. validate_mode_invocation_policy 规则

`validate_mode_invocation_policy()` 只做策略诊断，不改变 invocation，不阻止执行。

已实现诊断：

- `invalid_mode`
- `roundtable_executor_missing_when_to_mode_roundtable`
- `child_mode_without_return_policy`
- `switch_primary_mode_requires_reason`
- `autonomous_agent_high_risk_requires_review`
- `governance_review_requires_context`
- `clarification_should_not_call_autonomous_agent`
- `unknown_return_policy`

返回字段：

- `allowed`
- `warnings`
- `required_followups`

## 8. sample call graph 摘要

样例文件：

`migration_reports/foundation_audit/R241-4A_MODE_CALLGRAPH_RUNTIME_SAMPLE.json`

样例包含：

- `task -> search`
- `task -> roundtable` with `executor=rtcm`
- `roundtable -> search`
- `roundtable -> task`
- `workflow -> autonomous_agent`

样例摘要：

- `primary_mode`: `task`
- `active_modes`: `autonomous_agent`, `roundtable`, `search`, `task`, `workflow`
- `node_count`: 5
- `edge_count`: 5
- `by_from_mode`: `task=2`, `roundtable=2`, `workflow=1`
- `by_to_mode`: `search=2`, `roundtable=1`, `task=1`, `autonomous_agent=1`
- `roundtable_invocation_count`: 1
- `autonomous_agent_invocation_count`: 1
- `warnings`: none

## 9. 测试结果

RootGuard：

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile：

- `python -m py_compile backend/app/mode/mode_orchestration_contract.py`: PASS

新增 Mode tests：

- `python -m pytest backend/app/mode/test_mode_orchestration_contract.py -v`: 15 passed

Previous Asset tests：

- `python -m pytest backend/app/asset/test_asset_lifecycle_contract.py backend/app/asset/test_asset_projection.py -v`: 32 passed

Previous Memory tests：

- `python -m pytest backend/app/memory/test_memory_layer_contract.py backend/app/memory/test_memory_projection.py -v`: 24 passed

Previous Truth/State tests：

- `python -m pytest backend/app/m11/test_truth_state_contract.py backend/app/m11/test_governance_truth_projection.py backend/app/m11/test_queue_sandbox_truth_projection.py -v`: 33 passed

Gateway smoke：

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: 11 passed

## 10. 是否替换 M01/M04/RTCM/Gateway

否。

本轮没有修改、替换、包装或接入：

- M01 IntentClassifier
- M04 Coordinator
- RTCM 状态机
- Gateway routers / ContextEnvelope 执行路径
- DeerFlow run 逻辑

## 11. 是否改变模式路由 / 执行逻辑

否。

本轮只新增离线 instrumentation contract 与报告目录样例：

- 不做 Mode Router。
- 不改变模式选择。
- 不执行子模式。
- 不触发工具。
- 不写 governance / memory / asset / prompt runtime。
- 不改变用户请求执行路径。

## 12. 当前剩余断点

- ModeInvocation 目前仍是独立 wrapper，尚未接入 Gateway / ContextEnvelope。
- CallGraph 当前只支持 append/report style 样例，尚未进入生产 runtime state。
- Policy validation 只做诊断，不具备 enforcement。
- RTCM 仍只作为 `roundtable` 的 executor metadata 记录，未做运行链路整合。
- ModeResult 与 TruthEvent / StateEvent / AssetCandidate / Memory refs 目前只保留引用字段，尚未建立跨系统自动关联。

## 13. 下一步建议

进入 R241-4B：Gateway / ContextEnvelope ModeInstrumentation 接入。

建议下一轮仍保持只读或 append-only 原则，只在 Gateway / ContextEnvelope 边界记录 ModeSession / ModeInvocation metadata，不替换 M01/M04/RTCM，不改变模式路由与执行路径。

## 14. 最终判定

A. R241-4A 成功，可进入 R241-4B Gateway / ContextEnvelope ModeInstrumentation 接入。
