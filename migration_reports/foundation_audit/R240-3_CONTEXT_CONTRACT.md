# R240-3 Context Contract — Draft

**Status**: design draft, not implemented
**Root**: `E:\OpenClaw-Base\deerflow`
**Scope**: read-only inspection plus report/schema generation under `migration_reports\foundation_audit`
**Rounds precedent**: R240-0 (root), R240-1A/B (system map), R240-2 (intent/mode)

---

## 1. 主线任务校准思辨

### R240-2 断点的本质

R240-2 最终判定"不能直接实现 Mode Router"，原因是：

> 当前系统存在多个未统一的上下文标识：M01 requestId、Gateway/frontend thread_id/run_id、M04 task_id/workflow_id、RTCM session_id/governance trace_id、DeerFlow checkpointer/store thread state、memory scope、runtime artifact root。

这个判断是**准确的**。经过本轮只读摸查，证实问题比 R240-2 预估的更复杂：

1. **不同系统对同一概念使用不同名称**：
   - Gateway 叫 `thread_id`，LangGraph checkpointer 叫 `thread_id`（同名不同实例）
   - DeerFlow RunManager 用 `run_id`，Gateway router 用 `run_id`（但 RunManager 的 run_id 是 UUID，Gateway 的 run_id 来自哪里？）
   - M01 Orchestrator 没有自己的 request_id 概念，依赖外部传入

2. **同一名称在不同系统有不同语义**：
   - Gateway `thread_id` = LangGraph checkpoint thread ID
   - RTCM `session_id` = `rtcm-proj-XXX` 格式的 project-scoped 会话 ID
   - Governance `trace_id` = governance_state.json 里的决策追溯 ID
   - 这三者**不能互等**，只能通过 ContextLink 关联

3. **有些 ID 根本不存在**：
   - M01 OrchestrationRequest 没有 request_id 字段
   - Governance decision record 的 decision_id 是内部生成的，与业务 request 无映射
   - Asset promotion 的 asset_id 与 request context 无关

### 本轮目标达成

本轮唯一目标：**只读摸清所有上下文 ID、状态载体、存储位置、跨系统传递路径，并设计统一 Context Contract 草案**。

经过全面扫描，达成情况：
- ✅ 所有 8 个 Context 域已摸查
- ✅ ID 分类、同义判断、不可合并判断已完成
- ✅ 污染风险已识别
- ✅ ContextEnvelope、ContextLink、ContextScopeRules、ContextNormalizationPlan 草案已设计
- ✅ 最终三选一判定已给出

---

## 2. 当前上下文 ID 全量盘点

### 2.1 Request Context IDs

| 字段名 | 生成位置 | 格式 | 生命周期 | 备注 |
|--------|----------|------|----------|------|
| 无统一 request_id | M01 入口（orchestrator.ts） | — | — | OrchestrationRequest 没有 request_id 字段 |
| message_id | Feishu channel | lark message_id | per-message | 仅 Feishu 入口 |
| command_id | Channel commands | string | per-command | 仅 COMMAND 类型消息 |
| 无 request_id | Gateway /threads/* API | — | — | thread_runs.py RunCreateRequest 无 request_id |
| trace_id | governance_bridge.py | UUID | per-decision | governance 内部追溯用，不透传 |

**结论**：当前没有跨系统的统一 request_id。M01 Orchestrator 依赖外部传入的请求上下文。

### 2.2 Session / Thread / Run IDs

| 字段名 | 系统 | 格式 | 生命周期 | 备注 |
|--------|------|------|----------|------|
| `thread_id` | Gateway LangGraph checkpointer | UUID | long-lived | Gateway /api/threads 核心标识 |
| `run_id` | RunManager (in-memory) | UUID | per-run | Gateway /api/threads/{tid}/runs/* |
| `thread_id` | DeerFlow Harness client | UUID | per-session | packages/harness/deerflow/client.py |
| `session_id` | RTCM SessionManager | `rtcm-proj-{timestamp}-{hex}` | per-project | 完全独立于 Gateway thread_id |
| `rtcm_session_id` | RTCM runtime_state | `rtcm-{proj-...}` | per-RTCM-session | 与 RTCM SessionManager session_id 同源 |
| `activeRtcmSessionId` | MainAgentHandoffManager | UUID | per-handoff | 内存 + handoff dir |
| `activeRtcmThreadId` | MainAgentHandoffManager | UUID | per-handoff | 独立于 Gateway thread_id |
| `conversation_id` | frontend (AgentThreadContext) | UUID | per-conversation | frontend/src/core/threads/hooks.ts |
| `session_id` | Feishu channel | string | per-Feishu-im-session | 解析自 Feishu 消息 |
| `checkpoint_id` | LangGraph checkpointer | UUID | per-checkpoint | 用于 state history 分页 |
| `parent_checkpoint_id` | LangGraph checkpointer | UUID | per-checkpoint | 用于历史追溯 |

**结论**：
- `thread_id` 在 Gateway 和 DeerFlow Harness 中**同名不同源**：Gateway thread_id 是 LangGraph checkpointer 的 thread_id，DeerFlow client 自己生成 UUID 作为 thread_id
- RTCM `session_id` 与 Gateway `thread_id` **完全独立**，不能互等
- `run_id` 是 Gateway RunManager 内的临时 ID（内存），不持久化到 checkpointer

### 2.3 Task / Workflow IDs

| 字段名 | 系统 | 格式 | 生命周期 | 备注 |
|--------|------|------|----------|------|
| `task_id` | M04 registry | UUID | per-task | backend/app/m04/registry_db.py |
| `workflow_id` | M04 workflow | UUID | per-workflow | backend/app/m04/ |
| `dag_id` | M01 DAGPlanner | UUID | per-DAG-plan | backend/src/domain/m01/dag_planner.ts |
| `plan_id` | M01 types (DAGNode.id) | string (node id) | per-DAG-node | 不是独立 ID，是 DAG 内节点标识 |
| `candidate_id` | governance_bridge | UUID | per-candidate | governance outcome records |
| `task_id` | DeerFlow task_tool | UUID | per-task-invocation | packages/harness/deerflow/tools/builtins/task_tool.py |
| `run_id` | DeerFlow subagent executor | UUID | per-subagent-run | packages/harness/deerflow/subagents/executor.py |

**结论**：
- M04 task_id 与 DeerFlow task_id **不同源**：M04 task_id 是 registry DB 持久化的，DeerFlow task_id 是运行时工具调用生成的
- `candidate_id` 是 governance 层的 ID，与业务 task_id 无直接映射
- workflow_id 和 task_id 在 M04 层面有区分，但 DeerFlow 层混用

### 2.4 RTCM-specific IDs

| 字段名 | 格式 | 生命周期 | 备注 |
|--------|------|----------|------|
| `session_id` | `rtcm-proj-{timestamp}-{hex}` | per-project | SessionManager 管理的项目会话 |
| `project_id` | `proj-{timestamp}-{hex}` | per-project | 比 session_id 更顶层的项目标识 |
| `activeRtcmSessionId` | UUID | per-handoff | MainAgentHandoffManager 内存 |
| `activeRtcmThreadId` | UUID | per-handoff | 独立于 Gateway thread_id |
| `issue_id` | UUID | per-issue | RTCM 议题卡 |
| `hypothesis_id` | UUID | per-hypothesis | 议题内的候选假设 |
| `verdict_id` | UUID | per-verdict | 裁决记录 |
| `signoff_id` | UUID | per-signoff | 签批记录 |
| `followup_id` | UUID | per-followup | 后续跟进记录 |

**结论**：RTCM 有完整的独立 ID 体系，与 Gateway/DeerFlow 完全隔离。

### 2.5 Governance IDs

| 字段名 | 格式 | 生命周期 | 备注 |
|--------|------|----------|------|
| `decision_id` | UUID | per-decision | governance_bridge 内部生成 |
| `outcome_id` | UUID | per-outcome | outcome_records 追溯用 |
| `trace_id` | UUID | per-trace | governance 决策追溯 |
| `candidate_id` | UUID | per-candidate | doctrine/norm/asset candidates |
| `actual` | string | per-execution | sandbox 实际执行结果 |
| `predicted` | string | per-prediction | 预测结果 |
| `execution_stage` | enum string | per-execution | 当前执行阶段 |

**结论**：Governance 有自己的 ID 体系，但与业务 request/task/workflow 无直接关联路径。

### 2.6 Memory IDs

| 字段名 | 系统 | 格式 | 生命周期 | 备注 |
|--------|------|------|----------|------|
| `memory_scope` | M01 types | string enum | per-request | `user`, `session`, `task`, `workflow`, `rtcm`, `governance` |
| `memory_id` | DeerFlow memory | UUID | per-memory-item | memory updater |
| 无统一 memory_id | M08 learning_system | — | — | 使用不同的内部标识 |

**结论**：memory 没有统一的 ID 体系，依赖外部 scope 标记。

### 2.7 Asset IDs

| 字段名 | 系统 | 格式 | 生命周期 | 备注 |
|--------|------|------|----------|------|
| `asset_id` | M07 DPBS | UUID | per-asset | backend/app/m07/asset_system.py |
| `asset_name` | M07 | string | per-asset | **已知问题**：曾出现 "unknown" 值 |
| `asset_promotion` | M07 | record | per-promotion | promotion 事件记录 |
| `candidate_id` | governance | UUID | per-candidate | asset_promotion record 中的 candidate_id |

**结论**：asset_id 与 request/task context 的关联是间接的，通过 candidate_id 桥接。

### 2.8 Runtime Artifact Paths

| 字段名 | 位置 | 格式 | 生命周期 | 备注 |
|--------|------|------|----------|------|
| `checkpoint_id` | LangGraph checkpointer | UUID | per-checkpoint | 存储在 checkpointer DB |
| `verify_script_path` | queue_consumer task | filesystem path | per-task | 指向 upgrade-center verify_scripts |
| `rollback_script_path` | queue_consumer task | filesystem path | per-task | 指向 upgrade-center rollback_templates |
| `dossier_dir` | RTCM ProjectContext | `rtcm/sessions/{projectId}/dossier` | per-project | RTCM 工件目录 |
| `telemetry_dir` | RTCM ProjectContext | `rtcm/sessions/{projectId}/telemetry` | per-project | RTCM 遥测目录 |
| `runtime_artifact_root` | paths.py VIRTUAL_PATH_PREFIX | `~/.deerflow/` | system | 运行时工件统一根路径 |

---

## 3. 各上下文域边界分析

### 3.1 Request Domain（请求域）

**边界**：M01 orchestrator.ts 入口、Gateway API 入口、Channel 入口。

**关键问题**：
- OrchestrationRequest 没有 request_id，依赖外部上下文
- Gateway thread_runs.py RunCreateRequest 没有 request_id
- Feishu/Telegram 入口各自解析自己的 session_id，没有归一化到统一请求ID

**可追溯性**：request → thread → run → checkpoint 的链路在 Gateway 层是清晰的（thread_id 贯穿），但 M01/RTCM 层断开了。

### 3.2 Session/Thread Domain（会话/线程域）

**边界**：Gateway LangGraph checkpointer、frontend AgentThreadContext、DeerFlow client。

**关键问题**：
- Gateway `thread_id` = LangGraph checkpointer thread_id（持久化）
- DeerFlow `thread_id` = client 生成的 UUID（与 Gateway 不同实例）
- RTCM `session_id` 与以上两者完全独立

**可追溯性**：一个 Gateway thread_id 可以通过 Content-Location header 追溯到 run_id，但 run_id 是内存态的，不持久化。

### 3.3 Task/Workflow Domain（任务/工作流域）

**边界**：M04 registry/manager、workflow builder/executor、DAG planner。

**关键问题**：
- M04 task_id 是 registry 持久化的
- DeerFlow task_tool 生成的 task_id 是运行时工具调用 ID
- workflow_id 和 task_id 在 M04 层面有区分，但执行时可能混用

**可追溯性**：M04 task 可以关联到 DAG node（通过 plan_id），但 DAG plan 与 workflow executor 的映射需要额外追溯。

### 3.4 RTCM Domain（圆桌域）

**边界**：RTCM SessionManager、MainAgentHandoffManager、rtcm_entry_adapter。

**关键问题**：
- RTCM 有完整的独立 ID 体系
- MainAgentHandoffManager 的 `activeRtcmThreadId` 独立于 Gateway thread_id
- RTCM dossier/project 工件存储在 `~/.deerflow/rtcm/` 下，与项目源码隔离

**可追溯性**：RTCM session 可以通过 `mainAgentHandoff.hasActiveRTCMSession()` 检查活跃状态，但与原始 user request 的关联需要通过 threadAdapter 追溯。

### 3.5 Governance Domain（治理域）

**边界**：governance_bridge.py、TypeScript R17-R19 engine、governance_state.json。

**关键问题**：
- Governance decision_id 是内部生成的，与业务 request_id 无映射
- outcome_id/candidate_id 存在于 governance_state.json，但与业务 thread_id 无关联
- sandbox_execution_result 通过 R212 机制回写到 governance_state，但与原始 task 的关联需要通过 task 内部追溯

**可追溯性**：governance outcome 通过 `write_governance_outcome()` 记录，但无法反向追溯到原始 request/thread。

### 3.6 Memory Domain（记忆域）

**边界**：memory_middleware.py、memory/updater.py、session_memory.ts、layer5_asset.ts。

**关键问题**：
- memory_scope 区分 user/session/task/workflow/rtcm/governance
- 但 memory_id 没有统一生成和管理
- 存在 scratchpad 被长期化风险（memory updater 可能写入 session_memory 而非 intended scope）

**可追溯性**：memory writes 依赖 thread_id 作为 scope 标识，但 memory item 本身没有独立 ID。

### 3.7 Asset Domain（资产域）

**边界**：asset_system.py（DPBS）、asset_manager.py、learning_manager.py。

**关键问题**：
- asset_id 是 DPBS 内部生成的
- asset_name 曾经出现 "unknown"（已知问题）
- asset_promotion record 中的 candidate_id 与 governance candidate_id 可能是同一个（需验证）

**可追溯性**：asset 可以通过 candidate_id 关联到 governance，但与 request/thread 的关联需要额外路径。

### 3.8 Runtime Artifact Domain（运行时产物域）

**边界**：paths.py（VIRTUAL_PATH_PREFIX）、upgrade-center、queue_consumer、watchdog。

**关键问题**：
- Runtime artifact root 是 `~/.deerflow/`，与项目源码 `E:\OpenClaw-Base\deerflow` 隔离
- checkpoint 存储在 checkpointer DB 或 `~/.deerflow/checkpoints/`
- RTCM 工件存储在 `~/.deerflow/rtcm/`
- Upgrade Center 工件存储在 `~/.deerflow/upgrade-center/`

**可追溯性**：runtime artifact 与 request 的关联通过 checkpoint_id 追溯，但 checkpoint_id 是 LangGraph 内部的，与 request_id 无直接映射。

---

## 4. 同义 ID / 不可合并 ID 判断

### 4.1 同义 ID（可合并但未合并）

| ID A | ID B | 同义理由 | 当前状态 |
|------|------|----------|----------|
| Gateway thread_id | LangGraph checkpointer thread_id | 同一个 UUID，传给 checkpointer 作为 configurable.thread_id | 已合并（Gateway thread_id 就是 checkpointer thread_id） |
| frontend conversation_id | AgentThreadContext.thread_id | 前端 conversation 映射到后端 thread | 已合并（通过 thread_runs.py 创建时使用同一 UUID） |
| DeerFlow client thread_id | DeerFlow checkpointer thread_id | client 生成的 UUID 传给 checkpointer | 已合并 |

**结论**：Gateway/DeerFlow/frontend 的 thread_id 已经基本统一（都是传给 LangGraph checkpointer 的同一个 UUID）。

### 4.2 不可合并的 ID（只能建立 ContextLink）

| ID A | ID B | 不能合并的理由 | 建议关系类型 |
|------|------|----------------|--------------|
| Gateway thread_id | RTCM session_id | 完全独立的 ID 体系，RTCM 有自己的 project/session 管理 | `belongs_to_session`（thread belongs to rtcm session） |
| Gateway run_id | Governance decision_id | run_id 是 RunManager 内存态，decision_id 是 governance 持久态 | `records_outcome_for` |
| M04 task_id | DeerFlow task_tool task_id | M04 task_id 是 registry 持久化，DeerFlow task_id 是运行时工具调用 | `executes_as`（DeerFlow task_tool executes M04 task） |
| Governance candidate_id | Asset candidate_id | candidate_id 在 governance 和 asset 中是同一语义（都是待审批候选） | `promotes_asset_for` |
| sandbox actual | M04 task/workflow | actual 是 governance 层对 sandbox 执行的真实记录，与原始 task 的映射需要 task 内部追溯 | `writes_memory_for` |

**关键判断**：**不能把 RTCM session_id 等同于 Gateway thread_id**。它们服务于不同的上下文域：RTCM 是圆桌讨论机制，Gateway thread 是 LangGraph 执行上下文。强行合并会导致 RTCM 工件污染 Gateway thread 上下文，或反之。

---

## 5. 上下文污染风险分析

### 5.1 Memory 污染风险

**风险等级**：⚠️ MEDIUM

**具体表现**：
- memory_middleware.py 和 memory/updater.py 写入 memory 时依赖 thread_id 作为 scope
- 但 memory item 本身没有独立 ID，无法精确追踪特定 memory 属于哪个 request
- session_memory 可能被 task workflow 长期化，导致 task 级别的 scratchpad 进入 user session memory

**已有保护**：memory_updater.py 有 scope 标记（user/session/task/workflow），但实际写入时可能超出预期 scope。

### 5.2 Governance Truth 混写风险

**风险等级**：⚠️ MEDIUM

**具体表现**：
- governance_state.json 包含混合的 outcome_types：nightly_evolution、doctrine_drift、upgrade_center_*、sandbox_execution_result
- 这些 outcome 混杂在一起，没有按 request/thread/task 隔离
- R212 sandbox_execution_result 回写时，没有携带原始 task/workflow 上下文

**已有保护**：governance_bridge.py 有 `_KEY_OUTCOME_TYPES` 分离机制，critical outcomes 立即持久化。

### 5.3 RTCM Dossier 与 User Thread 混写风险

**风险等级**：✅ LOW（已隔离）

**具体表现**：
- RTCM dossier 存储在 `~/.deerflow/rtcm/sessions/{projectId}/dossier`
- 与 Gateway thread 数据完全隔离
- MainAgentHandoffManager 的 activeRtcmThreadId 独立于 Gateway thread_id

**已有保护**：RTCM 有完整的独立目录结构，dossier 不污染 Gateway thread 上下文。

### 5.4 Task/Workflow 状态混写风险

**风险等级**：⚠️ MEDIUM

**具体表现**：
- M04 registry task 和 DeerFlow task_tool task 都叫 task_id，但语义不同
- workflow_id 和 task_id 在 M04 层面有区分，但 DeerFlow 层混用
- DAG plan 的 node id（plan_id）与 M04 task_id 的映射不明确

**已有保护**：M04 有 TaskStatus enum 和 TaskCategory 区分，但跨系统追溯路径不清晰。

### 5.5 Sandbox Artifact 与 Source Code 混写风险

**风险等级**：✅ LOW（已隔离）

**具体表现**：
- Runtime artifact root 是 `~/.deerflow/`，与项目源码 `E:\OpenClaw-Base\deerflow` 完全隔离
- upgrade-center verify_scripts 和 rollback_templates 都在 `~/.deerflow/upgrade-center/`
- 没有发现 artifact 写入项目源码目录的情况

**已有保护**：paths.py 的 VIRTUAL_PATH_PREFIX 机制确保了运行时产物与源码的隔离。

---

## 6. ContextEnvelope Schema 草案

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "R240-3_ContextEnvelope.schema.json",
  "title": "ContextEnvelope",
  "description": "统一上下文包 — 跨 M01/M04/RTCM/Gateway/DeerFlow/Governance 的上下文传递载体",
  "type": "object",
  "required": [
    "context_id",
    "request_id",
    "created_at",
    "source_system"
  ],
  "properties": {
    "context_id": {
      "type": "string",
      "description": "此 ContextEnvelope 的唯一标识符（UUID）",
      "format": "uuid"
    },
    "request_id": {
      "type": "string",
      "description": "业务请求级唯一标识 — 用于追溯整个请求生命周期。所有入口（M01/Gateway/Channel）都必须生成或传递此 ID",
      "format": "uuid"
    },
    "session_id": {
      "type": "string",
      "description": "Gateway LangGraph thread_id — 对应 checkpointer configurable.thread_id",
      "format": "uuid"
    },
    "run_id": {
      "type": "string",
      "description": "Gateway RunManager run_id — per-run 生命周期，内存态",
      "format": "uuid"
    },
    "task_id": {
      "type": "string",
      "description": "M04 registry task_id 或 DeerFlow task_tool task_id — 需通过 task_origin 区分来源",
      "format": "uuid"
    },
    "workflow_id": {
      "type": "string",
      "description": "M04 workflow_id — 工作流级上下文标识",
      "format": "uuid"
    },
    "dag_id": {
      "type": "string",
      "description": "M01 DAG plan ID — 编排计划级上下文标识",
      "format": "uuid"
    },
    "rtcm_session_id": {
      "type": "string",
      "description": "RTCM SessionManager session_id（格式：rtcm-proj-XXX）— 若无 RTCM 上下文则为空",
      "pattern": "^rtcm-proj-.*"
    },
    "rtcm_project_id": {
      "type": "string",
      "description": "RTCM project_id — 若无 RTCM 上下文则为空",
      "pattern": "^proj-.*"
    },
    "governance_trace_id": {
      "type": "string",
      "description": "Governance decision trace ID — 用于追溯 governance 决策链",
      "format": "uuid"
    },
    "governance_decision_id": {
      "type": "string",
      "description": "Governance decision record ID — governance 层决策标识",
      "format": "uuid"
    },
    "candidate_id": {
      "type": "string",
      "description": "Doctrine/Asset/Norm candidate ID — governance 和 asset 共享",
      "format": "uuid"
    },
    "asset_id": {
      "type": "string",
      "description": "M07 DPBS asset ID — 若无 asset 上下文则为空",
      "format": "uuid"
    },
    "checkpoint_id": {
      "type": "string",
      "description": "LangGraph checkpointer checkpoint_id — 用于 state history 分页",
      "format": "uuid"
    },
    "parent_checkpoint_id": {
      "type": "string",
      "description": "父 checkpoint ID — 用于历史追溯",
      "format": "uuid"
    },
    "memory_scope": {
      "type": "string",
      "enum": ["user", "session", "task", "workflow", "rtcm", "governance", "global"],
      "description": "记忆作用域 — 决定此上下文关联的长期记忆范围"
    },
    "runtime_artifact_root": {
      "type": "string",
      "description": "运行时产物根路径 — 通常为 ~/.deerflow/",
      "format": "uri"
    },
    "parent_context_id": {
      "type": "string",
      "description": "父 ContextEnvelope ID — 用于嵌套上下文的父子追溯",
      "format": "uuid"
    },
    "created_at": {
      "type": "string",
      "description": "上下文创建时间（ISO 8601）",
      "format": "date-time"
    },
    "updated_at": {
      "type": "string",
      "description": "上下文最后更新时间（ISO 8601）",
      "format": "date-time"
    },
    "source_system": {
      "type": "string",
      "enum": ["m01", "m04", "gateway", "deerflow", "rtcm", "governance", "channel", "frontend"],
      "description": "上下文生成来源系统"
    },
    "owner_system": {
      "type": "string",
      "enum": ["m01", "m04", "gateway", "deerflow", "rtcm", "governance", "channel", "frontend"],
      "description": "上下文主权系统 — 有权修改此上下文的空间"
    },
    "task_origin": {
      "type": "string",
      "enum": ["m04_registry", "deerflow_task_tool", "dag_node", "unknown"],
      "description": "task_id 的来源标识 — 用于区分 M04 registry task 和 DeerFlow task_tool task"
    },
    "truth_scope": {
      "type": "string",
      "enum": ["sandbox", "production", "governance", "memory", "unknown"],
      "description": "真值来源标识 — 区分执行结果来自沙盒、生产、治理还是记忆"
    },
    "state_scope": {
      "type": "string",
      "enum": ["idle", "running", "interrupted", "completed", "failed", "cancelled"],
      "description": "执行状态范围"
    },
    "execution_permissions": {
      "type": "object",
      "description": "此上下文允许的执行权限",
      "properties": {
        "can_write_memory": { "type": "boolean" },
        "can_write_asset": { "type": "boolean" },
        "can_write_governance": { "type": "boolean" },
        "can_execute_sandbox": { "type": "boolean" },
        "can_trigger_rtcm": { "type": "boolean" }
      }
    }
  }
}
```

---

## 7. ContextLink Schema 草案

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "R240-3_ContextLink.schema.json",
  "title": "ContextLink",
  "description": "上下文 ID 之间的关系链 — 表达不同系统 ID 之间的语义关联",
  "type": "object",
  "required": ["link_id", "from_context_id", "to_context_id", "relation_type", "source_system", "created_at"],
  "properties": {
    "link_id": {
      "type": "string",
      "description": "此链接的唯一标识符",
      "format": "uuid"
    },
    "from_context_id": {
      "type": "string",
      "description": "起始上下文 ID（通常是上游/父上下文）",
      "format": "uuid"
    },
    "to_context_id": {
      "type": "string",
      "description": "目标上下文 ID（通常是下游/子上下文）",
      "format": "uuid"
    },
    "relation_type": {
      "type": "string",
      "enum": [
        "derived_from",
        "delegates_to",
        "executes_as",
        "records_outcome_for",
        "writes_memory_for",
        "promotes_asset_for",
        "belongs_to_session",
        "belongs_to_thread",
        "belongs_to_workflow",
        "belongs_to_rtcm",
        "supersedes",
        "intercepts",
        "spawns"
      ],
      "description": "关系类型"
    },
    "source_system": {
      "type": "string",
      "enum": ["m01", "m04", "gateway", "deerflow", "rtcm", "governance", "channel", "frontend"],
      "description": "链接关系的来源系统"
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "链接关系的可信度（0-1）",
      "default": 1.0
    },
    "metadata": {
      "type": "object",
      "description": "可选的额外元数据",
      "additionalProperties": true
    },
    "created_at": {
      "type": "string",
      "description": "链接创建时间（ISO 8601）",
      "format": "date-time"
    }
  }
}
```

**relation_type 详解**：

- `derived_from`：下游上下文从上游上下文派生（例如 DeerFlow run 派生自 Gateway thread）
- `delegates_to`：上游上下文委托给下游（例如 ModeRequest 委托给 ModeDecision）
- `executes_as`：执行代理关系（例如 DeerFlow task_tool executes M04 task）
- `records_outcome_for`：记录结果关系（例如 Governance outcome records sandbox actual for task）
- `writes_memory_for`：写记忆关系（例如 memory updater writes for thread）
- `promotes_asset_for`：资产提升关系（例如 asset_promotion for candidate）
- `belongs_to_session`：属于会话关系（例如 Gateway thread belongs to session）
- `belongs_to_thread`：属于线程关系（例如 run belongs to thread）
- `belongs_to_workflow`：属于工作流关系（例如 task belongs to workflow）
- `belongs_to_rtcm`：属于 RTCM 关系（例如 RTCM session belongs to thread... 或反之）
- `supersedes`：替代关系（例如新 checkpoint supersedes 旧 checkpoint）
- `intercepts`：拦截关系（例如 RTCM intercepts 活跃 session）
- `spawns`：衍生关系（例如 RTCM project spawns new issue）

---

## 8. ContextScopeRules 与 ContextNormalizationPlan

### 8.1 ContextScopeRules

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "R240-3_ContextScopeRules.json",
  "title": "ContextScopeRules",
  "description": "各上下文 Scope 的生命周期、读写权限、归属规则",
  "scopes": {
    "request": {
      "lifecycle": "per request — 从入口到完成或失败",
      "readable_by": ["m01", "gateway", "channel", "frontend"],
      "writable_by": ["m01", "gateway", "channel"],
      "can进入_longterm_memory": false,
      "can进入_governance": false,
      "can进入_nightly_review": false,
      "can被_mode_router使用": true,
      "notes": "request scope 是最顶层，不能被任何下游 scope 写入"
    },
    "session": {
      "lifecycle": "long-lived — 直到 user explicitly ends session",
      "readable_by": ["gateway", "deerflow", "frontend", "m01"],
      "writable_by": ["gateway", "deerflow", "memory_middleware"],
      "can进入_longterm_memory": true,
      "can进入_governance": false,
      "can进入_nightly_review": false,
      "can被_mode_router使用": true,
      "notes": "session scope 对应 Gateway thread_id，LangGraph checkpointer 持久化"
    },
    "thread": {
      "lifecycle": "per session — 多个 runs 可以在同一个 thread 中串行",
      "readable_by": ["gateway", "deerflow", "frontend"],
      "writable_by": ["gateway", "deerflow"],
      "can进入_longterm_memory": true,
      "can进入_governance": false,
      "can进入_nightly_review": false,
      "can被_mode_router使用": true,
      "notes": "thread scope 和 session scope 在当前实现中几乎同义，thread_id = session_id"
    },
    "run": {
      "lifecycle": "per invocation — run 完成或取消后结束",
      "readable_by": ["gateway", "deerflow", "frontend"],
      "writable_by": ["gateway", "deerflow"],
      "can进入_longterm_memory": false,
      "can进入_governance": false,
      "can进入_nightly_review": false,
      "can被_mode_router使用": true,
      "notes": "run_id 是内存态的 RunManager ID，不持久化到 checkpointer"
    },
    "task": {
      "lifecycle": "per task — 从创建到完成/失败/取消",
      "readable_by": ["m04", "deerflow", "governance"],
      "writable_by": ["m04", "deerflow"],
      "can进入_longterm_memory": true,
      "can进入_governance": true,
      "can进入_nightly_review": true,
      "can被_mode_router使用": true,
      "notes": "task_origin 字段必须标注是 m04_registry 还是 deerflow_task_tool"
    },
    "workflow": {
      "lifecycle": "per workflow — 比 task 更长，包含多个 tasks",
      "readable_by": ["m04", "deerflow"],
      "writable_by": ["m04", "workflow_executor"],
      "can进入_longterm_memory": true,
      "can进入_governance": true,
      "can进入_nightly_review": true,
      "can被_mode_router使用": true,
      "notes": "workflow_id 和 task_id 必须通过 ContextLink 关联"
    },
    "rtcm": {
      "lifecycle": "per project — 可跨越多个 user sessions，可暂停/恢复",
      "readable_by": ["rtcm", "m01"],
      "writable_by": ["rtcm"],
      "can进入_longterm_memory": true,
      "can进入_governance": true,
      "can进入_nightly_review": true,
      "can被_mode_router使用": true,
      "notes": "RTCM session_id/project_id 与 Gateway thread_id 完全独立，必须通过 ContextLink 关联"
    },
    "governance": {
      "lifecycle": "long-lived — decision/outcome 持久化到 governance_state.json",
      "readable_by": ["governance", "m11"],
      "writable_by": ["governance_bridge"],
      "can进入_longterm_memory": false,
      "can进入_governance": true,
      "can进入_nightly_review": true,
      "can被_mode_router使用": true,
      "notes": "governance scope 的写入必须通过 governance_bridge，不能直接修改 governance_state.json"
    },
    "memory": {
      "lifecycle": "variable — 取决于 memory_scope（session 短，user 长）",
      "readable_by": ["memory_middleware", "m08", "deerflow"],
      "writable_by": ["memory_middleware", "memory_updater"],
      "can进入_longterm_memory": true,
      "can进入_governance": false,
      "can进入_nightly_review": true,
      "can被_mode_router使用": true,
      "notes": "memory scope 必须与 thread_id/request_id 关联，防止跨请求污染"
    },
    "asset": {
      "lifecycle": "long-lived — asset 持久化，可被多个 requests 复用",
      "readable_by": ["m07", "governance", "asset_manager"],
      "writable_by": ["m07"],
      "can进入_longterm_memory": false,
      "can进入_governance": true,
      "can进入_nightly_review": true,
      "can被_mode_router使用": true,
      "notes": "asset_id 必须通过 candidate_id 关联到 governance"
    },
    "runtime_artifact": {
      "lifecycle": "per run/task — checkpoint/verify_script/rollback_script",
      "readable_by": ["checkpointer", "queue_consumer", "watchdog"],
      "writable_by": ["checkpointer", "sandbox", "queue_consumer"],
      "can进入_longterm_memory": false,
      "can进入_governance": false,
      "can进入_nightly_review": false,
      "can被_mode_router使用": false,
      "notes": "runtime artifact 是执行副产品，不应进入 context chain 主链"
    }
  }
}
```

### 8.2 ContextNormalizationPlan

**目标**：设计未来如何将各系统接入统一 ContextEnvelope，而不是一次性重构所有系统。

#### Phase 1：最小接入点（Mode Router 实现前必须完成）

**M01 接入点**：
- 位置：`backend/src/domain/m01/orchestrator.ts` 的 `execute(request: OrchestrationRequest)`
- 最小改动：在 OrchestrationRequest 中添加 `context_envelope: ContextEnvelope` 字段
- 不需要修改 orchestrator 内部逻辑，只需要传递 envelope
- 生成或传递 `request_id`（如果外部未提供）

**Gateway 接入点**：
- 位置：`backend/app/gateway/routers/thread_runs.py` 的 `create_run()`
- 最小改动：在 `RunCreateRequest` 中添加 `context_envelope` 字段透传
- 从 envelope 中提取 `thread_id` 传给 checkpointer

**DeerFlow Harness 接入点**：
- 位置：`backend/packages/harness/deerflow/client.py` 的 `run()` 方法
- 最小改动：传递 context_envelope 而不是单独传递 thread_id
- 不需要修改内部 UUID 生成逻辑

**Governance Bridge 接入点**：
- 位置：`backend/app/m11/governance_bridge.py` 的 `record_outcome()`
- 最小改动：在 outcome record 中添加 `context_envelope_ref` 字段
- 不需要修改 decision_id 生成逻辑

#### Phase 2：ContextLink 填充

- 在 M01→M04→DeerFlow→Governance 的关键调用路径上，填充 ContextLink 关系
- 优先级：request→task（高）、task→governance（中）、rtcm↔thread（低）

#### Phase 3：Memory Scope 规范化

- 在 memory_middleware 和 memory_updater 中，严格按 memory_scope 写入
- 添加 memory item ID 生成（不依赖 thread_id 作为唯一标识）

**约束**：
- 每次接入只做 wrapper/adapter，不直接大改内部逻辑
- 不需要一次性重构所有系统
- 优先 wrapper，不直接修改

---

## 9. 当前不能实现的断点

### 断点 1：M01 OrchestrationRequest 没有 request_id 字段

**现状**：`OrchestrationRequest` 类型（`backend/src/domain/m01/types.ts`）中没有 `request_id` 字段。

**障碍**：如果要实现 ContextEnvelope，M01 需要能够从入口接收或生成 request_id，并将其传递到所有下游调用。但当前 M01 依赖外部传入的上下文，没有自己的请求级标识。

**不能实现原因**：这需要 M01 架构层面的改动（添加 request_id 到 OrchestrationRequest 并贯穿整个编排流程），超出了 Context Contract 设计范围。

### 断点 2：Governance outcome 与原始 request/task 的追溯路径不完整

**现状**：R212 通过 `write_governance_outcome()` 将 sandbox execution result 写入 governance_state，但没有携带原始 task/workflow 的完整上下文（只有 task 内部追溯）。

**障碍**：如果要在 governance outcome 和原始 request 之间建立追溯，需要在 task 执行时将 context_envelope 嵌入 task state，这样 governance outcome 记录时可以回溯。

**不能实现原因**：需要在 DeerFlow task_tool 和 governance_bridge 之间建立双向追溯路径，这需要两边同时改动。

### 断点 3：RTCM session 与 Gateway thread 的关联是单向的

**现状**：RTCM MainAgentHandoffManager 通过 `threadAdapter` 与 Gateway thread 交互，但 `activeRtcmThreadId` 是独立生成的。

**障碍**：如果要建立 RTCM session 和 Gateway thread 的双向关联，需要在 RTCM 侧维护对 Gateway thread_id 的引用，并在 Gateway 侧知道当前是否有活跃 RTCM session。

**不能实现原因**：RTCM intercept 机制通过内存态的 `hasActiveRTCMSession()` 检查，没有持久化到 ContextEnvelope。

---

## 10. 下一轮最优先方向建议

### 最终判定：B. 可以开始实现最小 ContextEnvelope wrapper

**理由**：

1. **ID 域已经摸清**：所有 8 个 Context 域的 ID 体系已明确，同义 ID 和不可合并 ID 已判断清楚。

2. **最小字段集稳定**：ContextEnvelope 的必须字段（context_id, request_id, created_at, source_system）已经确定，可选字段覆盖了所有已发现的 ID 类型。

3. **接入点明确**：M01（orchestrator.ts）、Gateway（thread_runs.py）、DeerFlow（client.py）、Governance（governance_bridge.py）的最小接入点已识别。

4. **不需要先修 Truth/State**：虽然 governance actual/success 语义有改进空间，但这不影响 ContextEnvelope 的实现。ContextEnvelope 只负责 ID 追溯，不负责状态真值判断。

### 建议下一轮实现顺序

1. **先实现 ContextEnvelope 数据类**：在 `backend/src/domain/m01/context.ts`（或 Python 侧 `backend/app/gateway/context.py`）实现最小 ContextEnvelope struct，包含必须字段。

2. **在 Gateway thread_runs.py 入口包装**：RunCreateRequest 接收可选 context_envelope，传递给 RunManager。

3. **在 M01 orchestrator 入口包装**：OrchestrationRequest 添加 context_envelope 字段透传。

4. **实现 ContextLink 表**：轻量级内存表或文件存储，记录关键 ID 关系（request↔thread↔run↔task）。

5. **Governance 侧接入**：在 record_outcome 时，尝试从调用栈提取 context_envelope_ref。

**不建议**：同时实现 memory scope 规范化和 governance 追溯优化——这些是独立的子任务，应在 ContextEnvelope wrapper 稳定后再推进。

---

## 附录：ID 分类总表

| ID 类 | 数量 | 代表 ID | 同义合并状态 | 可 Link 建立 |
|-------|------|---------|-------------|-------------|
| request | ~1 | 无统一 request_id | ❌ 未统一 | — |
| session | 3 | Gateway thread_id, RTCM session_id, Feishu session_id | ⚠️ 部分同义（Gateway RTCM Feishu） | ✅ 可建立 ContextLink |
| thread | 2 | Gateway thread_id, DeerFlow thread_id | ✅ 已统一（同名同源） | — |
| run | 1 | RunManager run_id | ✅ 独立但清晰 | ✅ ContextLink |
| task | 2 | M04 task_id, DeerFlow task_id | ⚠️ 同名不同源 | ✅ task_origin 标注 |
| workflow | 1 | M04 workflow_id | ✅ 独立清晰 | ✅ ContextLink |
| rtcm | 7+ | session_id, project_id, issue_id, hypothesis_id, verdict_id, signoff_id, followup_id | ✅ 完整独立体系 | ✅ ContextLink |
| governance | 4 | decision_id, outcome_id, trace_id, candidate_id | ✅ 独立体系 | ✅ ContextLink |
| memory | 1 | memory_scope（无独立 memory_id） | ⚠️ 需要独立 ID | 待设计 |
| asset | 2 | asset_id, candidate_id | ⚠️ candidate_id 与 governance 共用 | ✅ ContextLink |
| runtime artifact | 4+ | checkpoint_id, verify_script_path, rollback_script_path, dossier_dir | ✅ 隔离清晰 | ✅ ContextLink |

**总计：至少 10 类不同上下文 ID，约 25+ 独立 ID 类型。**

---

*Generated by R240-3 Context Contract audit — 2026/04/24*
