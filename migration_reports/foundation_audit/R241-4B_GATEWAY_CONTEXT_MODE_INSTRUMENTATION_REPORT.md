# R241-4B Gateway / ContextEnvelope ModeInstrumentation Report

## 1. 修改文件清单

新增文件：

- `backend/app/gateway/mode_instrumentation.py`
- `backend/app/gateway/test_mode_instrumentation_smoke.py`
- `migration_reports/foundation_audit/R241-4B_GATEWAY_MODE_INSTRUMENTATION_SAMPLE.json`
- `migration_reports/foundation_audit/R241-4B_GATEWAY_CONTEXT_MODE_INSTRUMENTATION_REPORT.md`

未修改文件：

- 未修改 `backend/app/gateway/context.py`
- 未修改 `backend/app/gateway/services.py`
- 未修改 Gateway API response schema
- 未修改 Gateway run / DeerFlow run 主路径
- 未修改 M01 / M04 / RTCM
- 未写入 governance / memory / asset / prompt runtime

## 2. ModeInstrumentationEnvelope 字段

`ModeInstrumentationEnvelope` 是 Gateway 边界 metadata envelope，不参与生产路由决策。

字段：

- `context_id`
- `request_id`
- `thread_id`
- `mode_session`
- `mode_call_graph`
- `selected_mode_hint`
- `primary_mode`
- `active_modes`
- `instrumentation_only`
- `warnings`

`instrumentation_only` 固定为 `true`。

## 3. infer_primary_mode_hint 规则

`infer_primary_mode_hint(payload, context_envelope)` 只做启发式 hint，不改变执行。

优先级：

1. 显式 `selected_mode_hint` / `selected_mode` / `requested_mode_hint` / `requested_mode` / `primary_mode` / `mode`
2. `roundtable` / `rtcm` / `council` / `debate` / `meeting` -> `roundtable`
3. `workflow` / `dag` / `pipeline` / `automation` / `sop` -> `workflow`
4. `autonomous` / `agent` / `long-running` / `delegate` -> `autonomous_agent`
5. `search` / `research` / `evidence` / `citation` / `find` -> `search`
6. `task` / `execute` / `fix` / `build` / `test` / `implement` -> `task`
7. 无明显证据 -> `direct_answer` with low confidence

返回：

- `primary_mode`
- `confidence`
- `evidence`
- `warnings`

## 4. create_gateway_mode_instrumentation 实现

`create_gateway_mode_instrumentation()` 复用 `create_mode_session()` 创建 ModeSession metadata。

实现结果：

- 从 payload / context 提取 `context_id`、`request_id`、`thread_id`
- 根据 hint 创建 `ModeSession`
- `active_modes` 至少包含 `primary_mode`
- 支持 payload / context 中已有 `active_modes`
- 返回 `ModeInstrumentationEnvelope` dict

禁止项保持：

- 不执行 mode
- 不调用 M01/M04/RTCM
- 不触发 tools
- 不写 runtime

## 5. attach_mode_metadata_to_context 实现

`attach_mode_metadata_to_context(context_envelope, mode_metadata)` 返回 context copy。

新增 optional 字段：

- `mode_session_id`
- `primary_mode`
- `active_modes`
- `mode_metadata`
- `mode_instrumentation_ref`

实现约束：

- 不修改原始 context 输入
- 不改变 ContextEnvelope required fields
- 不改 `ContextEnvelope` class schema
- 不改变 Gateway response schema

## 6. call graph projection 实现

`build_gateway_mode_call_graph_projection()` 基于 mode metadata 和可选 invocations / results 构建 ModeCallGraph。

实现结果：

- 没有 invocation 时，生成只有 primary mode node 的 graph
- 有 invocation 时，复用 R241-4A `build_mode_call_graph()`
- 不写任何 runtime
- 不触发任何执行路径

## 7. sample 摘要

样例文件：

`migration_reports/foundation_audit/R241-4B_GATEWAY_MODE_INSTRUMENTATION_SAMPLE.json`

样例包含：

- payload with task + search hints
- ContextEnvelope-like dict with `context_id` / `request_id` / `thread_id`
- inferred primary mode
- ModeSession
- attached context copy
- simple call graph projection
- warnings

样例结果：

- inferred `primary_mode`: `search`
- confidence: `0.78`
- evidence: `keyword:search`, `keyword:evidence`
- call graph `node_count`: 1
- call graph `edge_count`: 0
- warnings: none

说明：样例 payload 同时包含 task 与 search hints；当前启发式规则中 evidence/search 优先于 task/fix/test，因此样例 primary hint 为 `search`。这是 hint，不是 router decision。

## 8. 测试结果

RootGuard：

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile：

- `python -m py_compile backend/app/mode/mode_orchestration_contract.py backend/app/gateway/mode_instrumentation.py`: PASS

Mode + Gateway instrumentation tests：

- `python -m pytest backend/app/mode/test_mode_orchestration_contract.py backend/app/gateway/test_mode_instrumentation_smoke.py -v`: 30 passed

Existing Gateway smoke：

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: 11 passed

Previous Asset tests：

- `python -m pytest backend/app/asset/test_asset_lifecycle_contract.py backend/app/asset/test_asset_projection.py -v`: 32 passed

Previous Memory tests：

- `python -m pytest backend/app/memory/test_memory_layer_contract.py backend/app/memory/test_memory_projection.py -v`: 24 passed

Previous Truth/State tests：

- `python -m pytest backend/app/m11/test_truth_state_contract.py backend/app/m11/test_governance_truth_projection.py backend/app/m11/test_queue_sandbox_truth_projection.py -v`: 33 passed

## 9. 是否修改 Gateway response / run path

否。

本轮未修改 `context.py` / `services.py`，未接入 `start_run()` 主路径，未改变 Gateway API response schema，也未改变 DeerFlow run / thread 行为。

## 10. 是否替换 M01/M04/RTCM

否。

本轮没有替换、包装、拦截或调用：

- M01 IntentClassifier
- M04 Coordinator
- RTCM 状态机
- DeerFlow run logic

## 11. 是否改变模式路由 / 执行逻辑

否。

本轮只新增 Gateway 边界 metadata projection helper：

- 不实现 Mode Router
- 不改变 selected_mode / intent 现有使用方式
- 不改变用户请求执行路径
- 不触发 tool execution
- 不写 governance_state
- 不写 memory / asset / prompt runtime

## 12. 当前剩余断点

- ModeInstrumentation 仍未接入 Gateway run 主路径。
- 当前只支持 hint projection，不代表最终 mode decision。
- `attach_mode_metadata_to_context()` 是 standalone helper，尚未进入 `ContextEnvelope` class 内部。
- CallGraph projection 在无 invocation 时只产生 single-node graph。
- 后续若接入 Gateway，需要保持 optional / try-except safe / 不改变 response。

## 13. 下一步建议

进入 R241-5A：ToolExecutionEvent / ToolRuntime instrumentation。

建议继续保持 append-only / instrumentation-first 原则：先定义工具执行事件和 runtime policy projection，再考虑与 Gateway / ModeInvocation / TruthEvent 交叉引用。

## 14. 最终判定

A. R241-4B 成功，可进入 R241-5A ToolExecutionEvent / ToolRuntime instrumentation。
