# R241-5A ToolExecutionEvent / ToolRuntime Instrumentation Report

## 1. 修改文件清单

新增文件：

- `backend/app/tool_runtime/__init__.py`
- `backend/app/tool_runtime/tool_runtime_contract.py`
- `backend/app/tool_runtime/test_tool_runtime_contract.py`
- `migration_reports/foundation_audit/R241-5A_TOOL_RUNTIME_SAMPLE.json`
- `migration_reports/foundation_audit/R241-5A_TOOL_RUNTIME_INSTRUMENTATION_REPORT.md`

未修改文件：

- 未修改 M11 Executor 主逻辑。
- 未修改 M04 Skill Router。
- 未修改 DeerFlow tools。
- 未修改 MCP / Claude Code / OpenCLI / CLI-Anything 调用逻辑。
- 未修改 queue_consumer / sandbox executor。
- 未写入 governance_state。
- 未写入 memory / asset / prompt runtime。

## 2. ToolPolicy 字段

`ToolPolicy` 字段：

- `tool_id`
- `tool_type`
- `owner_system`
- `default_risk_level`
- `allowed_modes`
- `denied_modes`
- `requires_root_guard`
- `requires_backup_for`
- `supports_dry_run`
- `supports_rollback`
- `can_read_files`
- `can_write_files`
- `can_execute_shell`
- `can_access_network`
- `audit_required`
- `warnings`

默认策略语义：

- `shell` / `python` / `file_system` / `claude_code` / `opencli` 默认要求 RootGuard。
- `search` / readonly `browser` 默认 Level 0。
- `sandbox` 可通过 metadata 标记 rollback support。
- `mcp` 根据 metadata capabilities 判断读写能力。

## 3. ToolExecutionEvent 字段

`ToolExecutionEvent` 字段：

- `tool_execution_id`
- `context_id`
- `request_id`
- `mode_session_id`
- `mode_invocation_id`
- `caller_mode`
- `caller_system`
- `tool_id`
- `tool_type`
- `operation_type`
- `risk_level`
- `cwd`
- `root_guard_required`
- `root_guard_passed`
- `status`
- `success`
- `backup_refs`
- `rollback_refs`
- `modified_files`
- `artifact_refs`
- `truth_event_refs`
- `state_event_refs`
- `asset_candidate_refs`
- `warnings`
- `started_at`
- `finished_at`

本轮只创建事件 projection，不执行工具，不写 runtime。

## 4. Risk level 分类规则

已实现风险等级：

- `level_0_free_readonly`: 只读、搜索、扫描、静态分析。
- `level_1_standard_auto`: 普通代码编辑、创建普通文件、测试、构建、sandbox verify、Claude Code/MCP 调用 projection。
- `level_2_protected_auto`: 配置修改、package manager、RootGuard / registry / prompt core / protected runtime state 非破坏性修改。
- `level_3_confirm_or_archive`: 删除、schema migration、不可逆外部副作用、无 rollback 的 prompt_replace、memory_cleanup、Core/Premium asset elimination。
- `unknown`: 未知 operation。

路径规则：

- `package.json`、`tsconfig.json`、`pytest.ini`、`pyproject.toml`、lockfile -> Level 2。
- `governance_state.json`、`asset_registry.json`、`memory.json`、Qdrant、SQLite、`checkpoints.db` 写入 -> Level 2；删除 / cleanup / migration -> Level 3。
- `migration_reports/foundation_audit` 报告写入 -> Level 1。

## 5. ProtectedOperationDecision 规则

`decide_protected_operation()` 返回：

- `operation_type`
- `risk_level`
- `auto_allowed`
- `requires_backup`
- `requires_rollback`
- `requires_confirmation`
- `should_archive_instead_of_delete`
- `requires_root_guard`
- `requires_nightly_review`
- `required_followups`
- `warnings`

实现语义：

- Level 0: auto allowed, no backup.
- Level 1: auto allowed, write/exec requires RootGuard.
- Level 2: auto allowed, requires backup, rollback, RootGuard, audit, nightly review.
- Level 3: not auto allowed unless confirmation or archive strategy exists; requires backup, rollback, RootGuard, nightly review.
- delete -> archive instead of delete.
- prompt_replace -> backup + rollback required.
- memory_cleanup -> quarantine / observation required.
- Core/Premium asset elimination -> user confirmation + nightly review required.

## 6. validate_tool_event_policy 诊断规则

已实现诊断：

- `root_guard_required_but_missing`
- `level_2_missing_backup`
- `level_2_missing_rollback`
- `level_3_requires_confirmation`
- `delete_should_archive`
- `prompt_replace_missing_rollback`
- `memory_cleanup_requires_quarantine`
- `asset_core_elimination_forbidden`
- `external_side_effect_requires_confirmation`
- `unknown_operation_type`

该函数只诊断，不阻止真实工具执行，也不改变 enforcement。

## 7. sample 摘要

样例文件：

`migration_reports/foundation_audit/R241-5A_TOOL_RUNTIME_SAMPLE.json`

样例包含 8 个 ToolExecutionEvent projection：

- `read_file`: Level 0
- `edit_code`: Level 1
- `modify_config package.json`: Level 2 with backup / rollback
- `delete_file`: Level 3 archive warning
- `prompt_replace`: Level 3 without rollback
- `memory_cleanup`: Level 3 quarantine warning
- `claude_code_call`: Level 1 with `mode_invocation_id`
- `sandbox_verify`: Level 1 with rollback support

样例统计：

- total: 8
- Level 0: 1
- Level 1: 3
- Level 2: 1
- Level 3: 3
- high_risk_count: 4
- root_guard_required_count: 7
- sample-only; no tool execution

## 8. 测试结果

RootGuard：

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile：

- `python -m py_compile backend/app/tool_runtime/tool_runtime_contract.py`: PASS

ToolRuntime tests：

- `python -m pytest backend/app/tool_runtime/test_tool_runtime_contract.py -v`: 18 passed

Previous Mode tests：

- `python -m pytest backend/app/mode/test_mode_orchestration_contract.py backend/app/gateway/test_mode_instrumentation_smoke.py -v`: 30 passed

Previous Asset tests：

- `python -m pytest backend/app/asset/test_asset_lifecycle_contract.py backend/app/asset/test_asset_projection.py -v`: 32 passed

Previous Memory tests：

- `python -m pytest backend/app/memory/test_memory_layer_contract.py backend/app/memory/test_memory_projection.py -v`: 24 passed

Previous Truth/State tests：

- `python -m pytest backend/app/m11/test_truth_state_contract.py backend/app/m11/test_governance_truth_projection.py backend/app/m11/test_queue_sandbox_truth_projection.py -v`: 33 passed

Gateway smoke：

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: 11 passed

## 9. 是否修改工具执行器 / 权限 enforcement

否。

本轮未修改任何执行器、工具调用器、权限 enforcement、M11/M04/MCP/Claude Code/OpenCLI/queue_consumer/sandbox 逻辑。

## 10. 是否执行真实工具

否。

本轮只运行验证命令和 pytest。`ToolExecutionEvent` / `ToolPolicy` / `ProtectedOperationDecision` 均为 projection 数据结构，没有执行 shell/MCP/Claude Code/OpenCLI/Feishu/browser/tool call。

## 11. 是否写 runtime

否。

仅写入：

- wrapper code
- tests
- `migration_reports/foundation_audit` 下的报告和样例

未写入：

- `governance_state.json`
- memory runtime
- asset runtime
- prompt runtime
- tool runtime state

## 12. 当前剩余断点

- ToolExecutionEvent 尚未接入 Gateway / ModeInvocation 真实调用边界。
- ToolPolicy 仍是默认 projection，尚未读取统一 tool registry。
- ProtectedOperationDecision 只做诊断，不做 enforcement。
- RootGuard pass/fail 由 metadata 输入，尚未自动关联实际 RootGuard 运行结果。
- TruthEvent / StateEvent refs 只是引用字段，尚未自动生成 tool truth projection。

## 13. 下一步建议

进入 R241-5B：ToolRuntime Gateway / ModeInvocation 关联投影。

建议下一轮继续保持 instrumentation-only：把 ToolExecutionEvent 与 Gateway ModeInstrumentation / ModeInvocation 只读关联起来，不改变真实工具执行路径，不启用权限 enforcement。

## 14. 最终判定

A. R241-5A 成功，可进入 R241-5B ToolRuntime Gateway / ModeInvocation 关联投影。
