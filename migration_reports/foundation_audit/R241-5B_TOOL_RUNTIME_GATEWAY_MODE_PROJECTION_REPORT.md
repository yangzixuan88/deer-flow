# R241-5B ToolRuntime Gateway / ModeInvocation Projection Report

## 1. 修改文件清单

新增文件：

- `backend/app/tool_runtime/tool_runtime_projection.py`
- `backend/app/tool_runtime/test_tool_runtime_projection.py`
- `migration_reports/foundation_audit/R241-5B_TOOL_RUNTIME_GATEWAY_MODE_SAMPLE.json`
- `migration_reports/foundation_audit/R241-5B_TOOL_RUNTIME_GATEWAY_MODE_PROJECTION_REPORT.md`

未修改文件：

- 未修改 M11 Executor 主逻辑。
- 未修改 M04 Skill Router。
- 未修改 DeerFlow tools。
- 未修改 MCP / Claude Code / OpenCLI / CLI-Anything 调用逻辑。
- 未修改 queue_consumer / sandbox executor。
- 未修改 Gateway run / DeerFlow run 主路径。
- 未修改 Gateway response schema。
- 未写 governance_state / memory / asset / prompt runtime。

## 2. link_tool_event_to_mode_invocation 实现

`link_tool_event_to_mode_invocation()` 返回 `tool_event` 的 copy，不修改原输入，不写 runtime。

关联来源：

- 从 `mode_invocation` 提取 `mode_invocation_id`、`mode_session_id`、`from_mode` as `caller_mode`。
- 从 `mode_metadata` 提取 `mode_session_id`、`primary_mode`。
- 从 `context_envelope` 提取 `context_id`、`request_id`、`thread_id`。

容错行为：

- `mode_invocation` 缺失时返回 `missing_mode_invocation` warning。
- `context_id` 缺失时返回 `missing_context_id` warning。
- `caller_mode` 优先级：`mode_invocation.from_mode` > `mode_metadata.primary_mode`。

返回：

- `linked_event`
- `link_summary`
- `warnings`

## 3. create_contextual_tool_event 实现

`create_contextual_tool_event()` 调用 R241-5A `create_tool_execution_event()`，再注入 context / mode metadata，并自动调用 `validate_tool_event_policy()`。

实现结果：

- 保留 `backup_refs` / `rollback_refs` / `root_guard_passed`。
- 保留 `mode_invocation_id` / `mode_session_id`。
- 保留 `context_id` / `request_id`。
- 返回 `tool_event`、`policy_validation`、`warnings`。
- 不执行工具，不触发 shell / MCP / Claude Code / OpenCLI。

## 4. project_tool_events_for_mode_callgraph 实现

`project_tool_events_for_mode_callgraph()` 对 ToolExecutionEvent list 做只读聚合。

聚合维度：

- `by_mode_session_id`
- `by_mode_invocation_id`
- `by_caller_mode`
- `by_risk_level`

诊断：

- `high_risk_events`
- `orphan_tool_events`
- `orphan_tool_events_detected`

orphan 定义：

- 缺 `mode_session_id`
- 或缺 `mode_invocation_id`
- 或缺 `context_id`

## 5. project_gateway_tool_runtime 实现

`project_gateway_tool_runtime()` 使用 Gateway ModeInstrumentation helper 创建 mode metadata，并把 `planned_tool_calls` 投影为 contextual ToolExecutionEvent。

实现结果：

- `planned_tool_calls` 为空时返回空 events，不报错。
- 不执行 planned tool calls。
- 不改变 Gateway response。
- 不调用真实工具。
- 输出 `mode_metadata`、`tool_events`、`policy_validations`、`summary`、`warnings`。

## 6. detect_tool_mode_risks 实现

已实现只读风险诊断：

- `high_risk_tool_without_mode_context`
- `level_2_missing_backup`
- `level_2_missing_rollback`
- `level_3_requires_confirmation`
- `root_guard_required_but_missing`
- `autonomous_agent_high_risk_tool`
- `roundtable_direct_high_risk_tool`
- `prompt_replace_without_rollback`
- `memory_cleanup_without_quarantine`
- `asset_core_elimination_attempt`

该函数只诊断，不阻止执行，不改变权限 enforcement。

## 7. sample 摘要

样例文件：

`migration_reports/foundation_audit/R241-5B_TOOL_RUNTIME_GATEWAY_MODE_SAMPLE.json`

样例输入：

- payload: task + autonomous hints
- context: `context_id` / `request_id` / `thread_id`
- planned tool calls:
  - `read_file`
  - `claude_code_call`
  - `modify_config` with backup / rollback
  - `delete_file` without archive strategy
  - `prompt_replace` without rollback

样例输出摘要：

- `primary_mode`: `autonomous_agent`
- total tool events: 5
- by risk level:
  - Level 0: 1
  - Level 1: 1
  - Level 2: 1
  - Level 3: 2
- high risk events: 3
- orphan events: 5, because sample has mode session context but no explicit ModeInvocation
- risk signals:
  - `high_risk_tool_without_mode_context`: 3
  - `autonomous_agent_high_risk_tool`: 3
  - `level_3_requires_confirmation`: 2
  - `root_guard_required_but_missing`: 2
  - `prompt_replace_without_rollback`: 1

说明：样例 intentionally 不创建真实工具调用和真实 ModeInvocation execution，仅展示 projection 诊断能力。

## 8. 测试结果

RootGuard：

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile：

- `python -m py_compile backend/app/tool_runtime/tool_runtime_contract.py backend/app/tool_runtime/tool_runtime_projection.py`: PASS

ToolRuntime tests：

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

## 9. 是否执行真实工具

否。

本轮没有执行 shell / MCP / Claude Code / OpenCLI / CLI-Anything / Feishu / browser / sandbox 工具调用。`planned_tool_calls` 仅被投影为 `ToolExecutionEvent`。

## 10. 是否改变工具执行器 / 权限 enforcement

否。

本轮未修改任何 executor、tool adapter、MCP client、Claude Code/OpenCLI 调用逻辑，也没有启用权限 enforcement 或阻止现有工具执行。

## 11. 是否改变 Gateway / Mode routing

否。

本轮未修改 Gateway run / DeerFlow run 主路径，未改变 response schema，未实现 Mode Router，未替换 M01/M04/RTCM。

## 12. 当前剩余断点

- ToolRuntime projection 尚未接入真实 tool execution boundary。
- 样例中没有显式 ModeInvocation，因此高风险工具会被诊断为缺 `mode_invocation_id`。
- ToolExecutionEvent 尚未自动生成 TruthEvent / StateEvent。
- RootGuard 状态仍由 metadata 输入，尚未自动绑定 RootGuard 实际运行结果。
- Tool registry / policy registry 尚未统一读取。

## 13. 下一步建议

进入 R241-6A：PromptSourceRegistry / PromptGovernance wrapper。

建议下一轮继续保持 wrapper-first：先建立 prompt source / layer / replacement risk 的只读治理模型，不替换生产 prompt，不接入 GEPA/DSPy 自动优化，不修改 prompt runtime。

## 14. 最终判定

A. R241-5B 成功，可进入 R241-6A PromptSourceRegistry / PromptGovernance wrapper。
