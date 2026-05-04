# R240-6 Truth / State Contract

**Generated**: 2026-04-24
**Scope**: Truth/State semantic separation, OutcomeContract mapping, normalization plan
**Verdict**: **A — 可以开始实现 Truth/State wrapper**

---

## 1. 主线任务校准思辨

### 1.1 本轮性质确认

本轮是 **P0 Foundation Contract 设计轮**，不是实现轮。目标：

- 彻底分清 actual / predicted / success / status / state / outcome 的语义边界
- 定义 TruthEvent / StateEvent / OutcomeContract 草案
- 不修改任何业务代码
- 为 R240-5 Mode Router 提供可消费的 truth/state 语义基础

### 1.2 核心发现

经过对 7 个 truth/state 来源的全面摸查，发现当前系统存在 **3 层语义混淆**：

| 混淆层 | 问题 | 严重性 |
|--------|------|--------|
| **字段级复用** | `actual` 字段同时用于 1.0/0.0 (success) 和 0.95/0.2 (quality) | HIGH |
| **状态级复用** | `status` 同时用于 queue 工作流、UC approval、watchdog health | HIGH |
| **预测级混淆** | `predicted` 字段在 4 个 UC outcome 中缺失 | MEDIUM |
| **真值级混淆** | `actual_result = 1.0` 在 `nightly_evolution` 中无意义 | HIGH |

### 1.3 为什么本轮可以达到 A 判定

尽管有 3 层混淆，但 **actual/predicted/state 的分类边界可以通过 schema 设计清晰化**，不需要修改任何现有代码即可开始实施：

- `sandbox_execution_result` 是完整的 actual_outcome + predicted_outcome 对
- `upgrade_center_execution_result` 有 predicted_value 但 actual 字段语义不清
- 3 个 UC observation 类型没有 actual/predicted 但有业务含义
- RTCM verdict 是 approval_decision truth_type 的候选
- Memory update 不是 truth，是 state update

---

## 2. Truth / State 来源盘点

### 2.1 Governance Truth（来源：governance_bridge.py, governance_state.json）

**record_outcome() 签名**：
```python
async def record_outcome(
    self,
    outcome_type: str,          # 14 种 outcome_type
    actual_result: Any,         # 语义不统一
    predicted_result: Any,      # 语义不统一
    context: Dict[str, Any]     # 各 outcome_type 字段完全不同
)
```

**outcome_record 写入结构**：
```python
{
    "outcome_type": str,
    "actual": Any,           # 语义不统一：1.0/0.0 | 0.95/0.2 | null
    "predicted": Any,        # 语义不统一：number | null
    "context": Dict,         # 每个 outcome_type 字段完全不同
    "context_id": str|null, # R240-4 注入，但不传播 governance_trace_id
    "timestamp": str
}
```

**14 种 outcome_type 分类**：

| outcome_type | actual | predicted | truth_type | truth_track |
|---|---|---|---|---|
| `tool_execution` | 1.0/0.0 | 0.9/0.3 | actual_outcome + predicted_outcome | execution_truth |
| `tool_execution_uef` | 0.95/0.2 | from metadata | actual_outcome | execution_truth |
| `nightly_evolution` | 1.0 (hardcoded) | 0.9 (hardcoded) | observation_signal | governance_truth |
| `asset_promotion` | 1.0 | 0.9 | actual_outcome | asset_truth |
| `doctrine_drift_detected` | 1.0 | 0.5 | observation_signal | governance_truth |
| `upgrade_center_execution` | null | null | observation_signal | governance_truth |
| `upgrade_center_summary` | null | null | observation_signal | governance_truth |
| `upgrade_queue_snapshot` | in_context | in_context | state_snapshot | governance_truth |
| `upgrade_center_approval` | 1.0 (hardcoded) | predicted_value | predicted_outcome | governance_truth |
| `upgrade_center_approval_result` | 1.0/0.0 | 0.9 | approval_decision | governance_truth |
| `upgrade_center_execution_result` | in_context (ctx.success) | predicted_value | actual_outcome | governance_truth |
| `queue_health_signal` | 1.0 | 0.9 | observation_signal | governance_truth |
| `sandbox_execution_result` | 1.0/0.0 | from task.predicted | actual_outcome + predicted_outcome | execution_truth |

### 2.2 UC State（来源：TypeScript UC, upgrade_center_result.json）

**predicted_value 来源**（在 U6 ApprovalTierClassifier 设置）：
```typescript
// filter_result -> predicted_value 映射
experiment_pool / deep_analysis_pool / bypass -> 0.9
observation_pool + can_proceed=true -> 0.75
observation_pool + can_proceed=false -> 0.6
excluded -> 0.3
```

**关键发现**：predicted_value 存在于 UC candidate 对象中，但 **4 个 UC outcome_type 没有写入 governance 的 predicted 字段**：
- `upgrade_center_execution` — actual=null, predicted=null（只有 context 里有 demands_scanned）
- `upgrade_center_summary` — actual=null, predicted=null（context.top_candidates_for_approval 有 predicted_value）
- `upgrade_queue_snapshot` — actual/predicted 在 context 内
- `upgrade_center_approval` — 有 predicted_value，但 actual=1.0（硬编码，无意义）

### 2.3 Sandbox / Queue State（来源：queue_consumer.py）

**sandbox_execution_result 是 Execution Truth Track 的核心**：

| 字段 | PREDICTED / ACTUAL / STATE | 说明 |
|------|----------------------------|------|
| `candidate_id` | Identifier | metadata key |
| `execution_status` | **STATE** | success/failed/failed_no_rollback |
| `verify_exit_code` | **ACTUAL TRUTH** | 0=pass, 非0=fail |
| `rollback_invoked` | **STATE** | boolean |
| `rollback_exit_code` | **ACTUAL TRUTH** (conditional) | 0=rollback成功 |
| `actual_result` | **ACTUAL TRUTH** | 1.0 if verify_exit_code==0 else 0.0 |
| `predicted` | **PREDICTED** | from task.predicted (U6 predicted_value) |
| `filter_result` | **STATE** | 管线来源：experiment_pool/observation_pool/deep_analysis |
| `execution_stage` | **STATE** | queued_for_experiment |
| `last_error` | **ACTUAL TRUTH** | stderr/stdout |

**关键语义发现**：
- `task.status = "completed"` ≠ `execution_status = "success"`
- `task.status = "completed"` 仅表示 verify 脚本退出码为 0
- `execution_status = "success"` = verify_exit_code == 0 + rollback 未触发
- `failed_no_rollback` = 验证失败 + 无回滚脚本

### 2.4 RTCM State（来源：backend/src/rtcm/）

**两个独立状态机**：

```
MainChatMode (mode state — rtcm_main_agent_handoff.ts)
  NORMAL ←→ RTCM ←→ SUSPENDED

ProjectStatus (workflow state — rtcm_session_manager.ts)
  ACTIVE ←→ PAUSED ←→ WAITING_FOR_USER ←→ ARCHIVED/FAILED

SessionStatus (execution state — types.ts)
  init → issue_definition → debate → solution_convergence → execution → validation → archived
```

**关键发现**：
- `WAITING_FOR_USER` ≠ `PAUSED`：前者是等待用户接受决策，后者是暂停项目
- `final_report` 是共识输出，不是 truth event
- `signoff` 是 approval_decision truth_type 的候选（多方确认记录）
- RTCM **不**直接写 governance（通过 Feishu 间接回流）
- `rtcm_session_id` 未进入 ContextEnvelope

### 2.5 Gateway / DeerFlow Run State（来源：services.py, manager.py, worker.py）

**RunStatus（6 个值）**：
```
pending → running → success / error / timeout / interrupted
```

**TaskStatus（5 个值）**：
```
pending → in_progress → completed / failed / cancelled
```

**NodeExecutionStatus（7 个值）**：
```
pending → queued → running → completed / failed / skipped / timeout
```

**关键发现**：
- `RunStatus.success` ≠ `TaskStatus.COMPLETED`（不同系统）
- `RunStatus.error` 不写 governance
- Tool call 失败通过 LearningMiddleware 间接写 governance，不直接改变 RunStatus

### 2.6 Memory / Asset / Learning State

**Memory**：纯 state，非 truth。MemoryUpdater 不写 governance。

**LearningMiddleware**：写 `tool_execution_uef` 到 governance，是 execution_truth track。

**Asset**：bind_platform() 同时写 state（platform dict）和 truth（asset_promotion outcome）。

**关键发现**：
- `result_quality = 0.95/0.2`（tool_execution_uef）不是 1.0/0.0，是质量信号，不是真假信号
- `actual_result = 1.0` 在 `nightly_evolution` 中是硬编码，无业务意义
- Memory update signal **没有**对应的 governance outcome_type

---

## 3. 同名字段语义冲突分析

### 3.1 `actual` 字段 — 三种完全不同语义

| outcome_type | actual 语义 | 类型 |
|---|---|---|
| `sandbox_execution_result` | 1.0=成功, 0.0=失败 | 二值真假 |
| `tool_execution_uef` | 0.95=成功高质量, 0.2=失败 | 质量信号 |
| `nightly_evolution` | 1.0（硬编码） | 无业务意义 |
| `upgrade_center_approval` | 1.0（硬编码） | 无业务意义 |
| `upgrade_center_approval_result` | 1.0=批准, 0.0=拒绝 | 二值真假 |
| `upgrade_center_execution_result` | 在 context.success 中 | 二值真假 |

### 3.2 `status` 字段 — 三种完全不同语义

| 出现在 | status 语义 | 值域 |
|--------|------------|------|
| experiment_queue.json task | Queue 工作流状态 | pending/running/completed/failed |
| upgrade_center_approval context | UC candidate 状态 | pending（在 governance_state.json 中）|
| queue_health_signal context | Watchdog 健康状态 | empty/stale/backlog/healthy |
| sandbox_execution_result context | 执行结果状态 | success/failed/failed_no_rollback |
| upgrade_center_execution_result context | 不使用 status | — |

### 3.3 `execution_stage` — 两种完全不同语义

| outcome_type | execution_stage 语义 |
|---|---|
| `sandbox_execution_result` context | 管线节点：queued_for_experiment |
| `upgrade_center_execution_result` context | 审批路由：awaiting_approval/approved_for_experiment/bypass_to_experiment |

### 3.4 `filter_result` — 两个不同来源

| outcome_type | filter_result 来源 |
|---|---|
| `sandbox_execution_result` | 来自 task 元数据（UC 管线传播）|
| `upgrade_center_execution_result` | 来自 UC U2：deep_analysis_pool/observation_pool |

---

## 4. OutcomeType 映射表

| outcome_type | truth_type | truth_track | actual语义 | predicted语义 | 可进入success_rate? | 推荐映射 |
|---|---|---|---|---|---|---|
| `sandbox_execution_result` | actual_outcome | execution_truth | 1.0/0.0 (verify_exit_code) | predicted_value (U6) | YES | TruthEvent, actual_value + predicted_value |
| `tool_execution` | actual_outcome | execution_truth | 1.0/0.0 | 0.9/0.3 | YES | TruthEvent |
| `tool_execution_uef` | actual_outcome | execution_truth | result_quality (0.95/0.2) | from metadata | YES (质量) | TruthEvent，actual_value=result_quality |
| `asset_promotion` | actual_outcome | asset_truth | 1.0 | 0.9 | YES | TruthEvent |
| `upgrade_center_approval` | predicted_outcome | governance_truth | 1.0 (硬编码,无用) | predicted_value | YES (预测质量) | TruthEvent，移除硬编码actual |
| `upgrade_center_approval_result` | approval_decision | governance_truth | 1.0/0.0 (批准/拒绝) | 0.9 | YES | TruthEvent，actual_value=批准/拒绝 |
| `upgrade_center_execution_result` | actual_outcome | governance_truth | context.success | predicted_value | YES | TruthEvent |
| `nightly_evolution` | observation_signal | governance_truth | 1.0 (硬编码) | 0.9 (硬编码) | NO | StateEvent，标记为observation |
| `doctrine_drift_detected` | observation_signal | governance_truth | 1.0 (hardcoded) | 0.5 | NO | StateEvent |
| `upgrade_center_execution` | observation_signal | governance_truth | null | null | NO | StateEvent |
| `upgrade_center_summary` | observation_signal | governance_truth | null | null | NO | StateEvent |
| `upgrade_queue_snapshot` | state_snapshot | governance_truth | 在context中 | 在context中 | NO | StateEvent |
| `queue_health_signal` | observation_signal | governance_truth | 1.0 | 0.9 | NO | StateEvent |
| `rtcm_verdict` (NEW) | approval_decision | rtcm_truth | accept/reject/needs_revision | — | YES | TruthEvent (待实现) |
| `memory_update_signal` (NEW) | state_update | memory_truth | success/failure | — | NO | StateEvent (待实现) |

---

## 5. TruthEvent Schema 草案

### 设计原则

1. **不修改**现有 governance_bridge.record_outcome() 签名
2. 在**封装层**（wrapper/adapter）做 schema 转换
3. 新增 outcome_type 时扩展 truth_type 枚举，不修改现有代码
4. 所有可选字段兼容现有数据（null 值允许）

### Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "R240-6_TruthEvent.schema.json",
  "title": "TruthEvent",
  "description": "统一真值事件 — actual observations, predictions, approvals",
  "type": "object",
  "required": ["truth_event_id", "truth_type", "truth_track", "subject_type", "subject_id", "source_system", "created_at"],
  "properties": {
    "truth_event_id": {
      "type": "string",
      "description": "UUID — 全局唯一标识"
    },
    "context_id": {
      "type": "string",
      "description": "关联的 ContextEnvelope.context_id (R240-4)"
    },
    "request_id": {
      "type": "string",
      "description": "关联的 OrchestrationRequest.requestId (M01)"
    },
    "governance_trace_id": {
      "type": "string",
      "description": "ContextEnvelope.governance_trace_id，用于跨系统血缘追踪"
    },
    "source_system": {
      "type": "string",
      "description": "产生该事件的系统：queue_consumer, governance_bridge, learning_system, rtcm, ..."
    },
    "truth_type": {
      "type": "string",
      "enum": [
        "predicted_outcome",
        "actual_outcome",
        "approval_decision",
        "execution_result",
        "verification_result",
        "rollback_result",
        "observation_signal",
        "user_feedback",
        "asset_quality_signal",
        "rtcm_verdict"
      ]
    },
    "truth_track": {
      "type": "string",
      "enum": [
        "execution_truth",
        "governance_truth",
        "observation_truth",
        "user_truth",
        "asset_truth",
        "rtcm_truth"
      ]
    },
    "subject_type": {
      "type": "string",
      "enum": [
        "candidate",
        "tool",
        "asset",
        "rule",
        "doctrine",
        "rtcm_issue",
        "memory_fact"
      ]
    },
    "subject_id": {
      "type": "string",
      "description": "具体标识：candidate_id, tool_name, asset_id, ..."
    },
    "actual_value": {
      "type": ["number", "null"],
      "description": "实际观测值或决策结果。1.0/0.0 用于二值真假；0.0-1.0 用于质量信号；accept/reject/needs_revision 用于审批"
    },
    "predicted_value": {
      "type": ["number", "null"],
      "description": "预测值或期望值。0.0-1.0 范围。null 表示无预测"
    },
    "confidence": {
      "type": ["number", "null"],
      "minimum": 0,
      "maximum": 1,
      "description": "置信度，仅用于预测类 truth_type"
    },
    "evidence_refs": {
      "type": "array",
      "items": {"type": "string"},
      "description": "证据引用：artifact 路径、log 文件、governance_trace_id 等"
    },
    "producer": {
      "type": "string",
      "description": "产生该事件的函数或类：queue_consumer.write_governance_outcome, governance_bridge.record_outcome, ..."
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 时间戳"
    },
    "related_state_id": {
      "type": ["string", "null"],
      "description": "关联的 StateEvent.state_event_id（如果该 truth 触发了状态转换）"
    }
  }
}
```

### truth_type 分类逻辑

| truth_type | actual_value | predicted_value | confidence | 进入success_rate? |
|---|---|---|---|---|
| actual_outcome | 1.0/0.0 | 0.0-1.0 | null | YES |
| predicted_outcome | null | 0.0-1.0 | 0.0-1.0 | YES (预测质量) |
| approval_decision | accept/reject | null | null | YES (人工决策) |
| verification_result | 1.0/0.0 | null | null | YES |
| rollback_result | 0.0/1.0 (rollback成功/失败) | null | null | YES |
| observation_signal | null | null | null | NO |
| user_feedback | accept/reject/needs_revision | null | null | YES |
| asset_quality_signal | 0.0-1.0 (avg_quality) | null | null | YES (质量) |
| rtcm_verdict | accept/reject/needs_revision | null | null | YES |

---

## 6. StateEvent Schema 草案

### 设计原则

1. StateEvent 记录**状态转换**，不是真值
2. 不区分"成功/失败"，只记录**状态变更**
3. terminal 状态有特殊标记
4. 关联 TruthEvent 用 `related_truth_event_id`

### Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "R240-6_StateEvent.schema.json",
  "title": "StateEvent",
  "description": "统一状态事件 — 状态转换记录",
  "type": "object",
  "required": ["state_event_id", "state_domain", "subject_type", "subject_id", "new_state", "source_system", "created_at"],
  "properties": {
    "state_event_id": {
      "type": "string",
      "description": "UUID — 全局唯一标识"
    },
    "context_id": {
      "type": ["string", "null"],
      "description": "关联的 ContextEnvelope.context_id"
    },
    "source_system": {
      "type": "string",
      "description": "产生该事件的系统"
    },
    "state_domain": {
      "type": "string",
      "enum": [
        "gateway_run",
        "deerflow_thread",
        "m01_request",
        "m04_task",
        "m04_workflow",
        "m04_node",
        "rtcm_project",
        "rtcm_session",
        "rtcm_round",
        "governance_decision",
        "experiment_queue_task",
        "sandbox_execution",
        "asset_lifecycle",
        "memory_update",
        "nightly_review",
        "watchdog_health"
      ]
    },
    "subject_type": {
      "type": "string",
      "enum": [
        "run",
        "thread",
        "request",
        "task",
        "workflow",
        "node",
        "project",
        "session",
        "round",
        "decision",
        "queue_task",
        "execution",
        "asset",
        "memory",
        "review",
        "health"
      ]
    },
    "subject_id": {
      "type": "string",
      "description": "具体标识"
    },
    "previous_state": {
      "type": ["string", "null"],
      "description": "转换前的状态值（如有）"
    },
    "new_state": {
      "type": "string",
      "description": "转换后的状态值"
    },
    "state_category": {
      "type": "string",
      "enum": ["terminal", "intermediate", "neutral", "error", "pending"],
      "description": "状态分类：terminal=终态, intermediate=中间态, neutral=中性, error=错误态, pending=等待态"
    },
    "transition_reason": {
      "type": ["string", "null"],
      "description": "状态转换原因"
    },
    "actor_system": {
      "type": ["string", "null"],
      "description": "触发该转换的主动系统"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "related_truth_event_id": {
      "type": ["string", "null"],
      "description": "关联的 TruthEvent.truth_event_id（如果该状态转换由 truth 触发）"
    },
    "artifact_refs": {
      "type": "array",
      "items": {"type": "string"},
      "description": "相关 artifact 引用"
    }
  }
}
```

### state_category 分类逻辑

| state_category | 定义 | 可进入 governance? | 可进入 nightly_review? |
|---|---|---|---|
| terminal | 终态，无法转换到其他状态 | 部分（如 ARCHIVED）| 是 |
| intermediate | 中间态，可以转换 | 是 | 是 |
| neutral | 中性状态，不产生 truth | 否 | 是 |
| error | 错误/失败态 | 是（failure outcomes）| 是 |
| pending | 等待态 | 否 | 是 |

---

## 7. StateTransitionRules 草案

### 7.1 Gateway Run State

```
RunStatus: pending → running → success (terminal)
                          → error (terminal)
                          → timeout (terminal)
                          → interrupted (terminal)

state_category:
  pending = pending
  running = intermediate
  success = terminal (neutral)
  error = terminal (error)
  timeout = terminal (error)
  interrupted = terminal (neutral)
```

**进入 governance 的条件**：否（RunStatus 是内部状态，不自动产生 outcome）

**进入 nightly_review 的条件**：否

### 7.2 M04 Task State

```
TaskStatus: pending → in_progress → completed (terminal)
                                 → failed (terminal)
                                 → cancelled (terminal)

NodeExecutionStatus: pending → queued → running → completed (terminal)
                                               → failed (terminal) → skipped (terminal)
                                               → timeout (terminal)

state_category:
  completed = terminal (neutral)
  failed = terminal (error)
  cancelled = terminal (neutral)
```

**进入 governance 的条件**：`failed` 不直接写 governance，通过 LearningMiddleware 写 `tool_execution_uef`

### 7.3 Sandbox Queue State

```
Queue Task: pending → running → completed (terminal)
                                → failed (terminal)

Execution Status (context):
  success (sandbox pass)
  failed (verify fail + rollback invoked)
  failed_no_rollback (verify fail，无回滚)

state_category:
  pending = pending
  running = intermediate
  completed = terminal (neutral — 但不等同 success)
  failed = terminal (error)
```

**关键规则**：
- `task.status = completed` ≠ `execution_status = success`
- `task.status = completed` 仅表示 verify 脚本退出码为 0
- `failed_no_rollback` 是 terminal error，且无安全网

**进入 governance 的条件**：
- 执行完成 → 写 `sandbox_execution_result` (actual_outcome)
- `failed_no_rollback` 标记为高风险

### 7.4 UC Experiment Queue State

```
ExperimentTask.status: pending → running → completed (terminal)
                                          → failed (terminal)

ApprovalBacklog.status: pending → approved/rejected/expired (terminal)
```

**进入 governance 的条件**：否（queue 状态不直接写 governance）

### 7.5 RTCM State

```
ProjectStatus:
  ACTIVE → PAUSED/WAITING_FOR_USER → ARCHIVED (terminal)
  ACTIVE → FAILED_RECOVERABLE → FAILED_TERMINAL (terminal)

SessionStatus:
  init → issue_definition → debate → solution_convergence
       → execution → validation → archived (terminal)
       → reopen → ...
```

**关键规则**：
- `WAITING_FOR_USER` = intermediate，不是 terminal（等待人工决策）
- `ARCHIVED` = terminal (neutral)
- `FAILED_TERMINAL` = terminal (error)

**进入 governance 的条件**：待定（需要实现 rtcm_verdict outcome_type）

### 7.6 Governance State（governance_state.json）

```
decisions[]: 追加写入，无状态机
outcome_records[]: 追加写入，无状态机
```

**终态定义**：
- 超过 100 条时最早的 decision/outcome 被删除（非终态）

---

## 8. TruthStateNormalizationPlan

### Phase 1：只加 Wrapper / Adapter（不修改原结构）

**目标**：在 governance_bridge.record_outcome() 外层加 TruthEvent/StateEvent 封装

**操作**：
1. 新建 `TruthEventWrapper` 类：
   - 接收原始 `outcome_type + actual_result + predicted_result + context`
   - 映射到 `TruthEvent` schema
   - 提取 `actual_value / predicted_value / confidence`
   - 补全 `governance_trace_id`（从 context.context_envelope 提取）

2. 新建 `StateEventWrapper` 类：
   - 接收 queue/gateway/M04/RTCM 状态变更事件
   - 映射到 `StateEvent` schema
   - 关联相关 TruthEvent

3. 新建 `OutcomeContractMapper`：
   - 处理 `actual_result` 的类型分歧（1.0/0.0 vs 0.95/0.2）
   - 处理 `predicted_result` 的缺失（null 映射）

**不修改**：governance_bridge.py, queue_consumer.py, UC TypeScript 代码

### Phase 2：Governance Outcome 增加 TruthEvent Envelope

**目标**：outcome_record 增加 truth_type / truth_track 分类

**操作**：
1. 在 `outcome_record` 增加可选字段：
   ```python
   {
       "truth_type": "actual_outcome|predicted_outcome|observation_signal|...",
       "truth_track": "execution_truth|governance_truth|...",
       "truth_event_id": "uuid",
   }
   ```

2. 对现有 14 个 outcome_type 分类：
   - `actual_outcome`：sandbox, tool_execution, asset_promotion, approval_result
   - `predicted_outcome`：upgrade_center_approval
   - `observation_signal`：nightly_evolution, doctrine_drift, UC executions
   - `state_snapshot`：upgrade_queue_snapshot

3. 修复 `actual = null` 问题：
   - `upgrade_center_execution` / `upgrade_center_summary` → 标记 `observation_signal`
   - `upgrade_center_approval` 的 actual=1.0 硬编码 → 移除或改为 null

### Phase 3：Queue / Sandbox / UC Predicted 与 Actual 对齐

**目标**：解决 sandbox_execution_result 的 predicted 来源不透明问题

**操作**：
1. 在 `ExperimentTask` 增加 `truth_event_id` 字段（贯穿 UC → Queue → Governance）
2. UC `upgrade_center_approval` outcome 携带 `predicted_value`
3. QueueConsumer 写 `sandbox_execution_result` 时，补全 `predicted_value` 来源链路
4. UC pipeline 的 `experiment_pool.json` / `approval_backlog.json` 作为 predicted state 独立存储

### Phase 4：RTCM / Asset / Memory / Prompt 接入

**目标**：补全 TruthEvent 覆盖范围

**操作**：
1. **RTCM**：
   - 新增 `rtcm_verdict` outcome_type
   - 映射 final_report.acceptance_recommendation → actual_value
   - signoff 记录 → approval_decision truth_type
   - rtcm_session_id 进入 ContextEnvelope

2. **Asset**：
   - asset_promotion 已存在，补全 governance_trace_id
   - asset quality signal（待实现）

3. **Memory**：
   - 新增 `memory_update_signal` outcome_type（可选，不强制）
   - MemoryMiddleware 不改，但 memory_scope 泄漏问题需在 Phase 5 前修复

4. **Prompt**：
   - Optimizer 目前是 stub，暂不处理

### Phase 5：Mode Router 安全消费

**前提**：Phase 1-4 完成，truth/state 边界清晰

**操作**：
1. Mode Router 只消费 TruthEvent（actual_outcome + approval_decision）
2. observation_signal 不参与 success_rate 计算
3. StateEvent 用于 mode 切换触发
4. Memory scope 过滤在 MemoryMiddleware 层执行

---

## 9. 当前不能实现的断点

### 断点 1：`actual_result` 硬编码（nightly_evolution, upgrade_center_approval）

**现状**：
```python
# nightly_evolution
actual_result = 1.0  # 硬编码，无业务意义
predicted_result = 0.9  # 硬编码，无业务意义

# upgrade_center_approval
actual_result = 1.0  # 硬编码，无意义
```

**为什么不能现在修**：这两个硬编码是现有 governance_state.json 的事实，不能简单改值而不理解业务影响

**修复路径**：Phase 2 — 将 `nightly_evolution` 标记为 `observation_signal`，移除 actual/predicted 硬编码意义

### 断点 2：`governance_trace_id` 未传播到 outcome_record

**现状**：R240-4 在 context.py 中定义了 governance_trace_id，但没有任何 outcome_type 的 context 中携带此字段

**影响**：Mode Router 无法将 governance outcome 关联回原始 request

**修复路径**：Phase 1 — `TruthEventWrapper` 从 `context.context_envelope.governance_trace_id` 提取并写入 TruthEvent

### 断点 3：UC predicted_value 没有写入 governance outcome 的 predicted 字段

**现状**：
- `upgrade_center_summary` context 内有 `top_candidates_for_approval[].predicted_value`
- 但 `actual` 和 `predicted` 顶层字段为 null

**影响**：Mode Router 无法用 predicted_value 计算预测准确率

**修复路径**：Phase 3 — UC backflow 时将 candidate.predicted_value 写入 predicted 字段

### 断点 4：RTCM signoff / verdict 无 governance outcome 映射

**现状**：RTCM final_report / signoff 是独立 artifacts，不写 governance

**影响**：RTCM 共识结果无法进入 governance 学习循环

**修复路径**：Phase 4 — 新增 rtcm_verdict outcome_type

### 断点 5：Memory update 不是 truth 也不是 state event

**现状**：MemoryUpdater 不写 governance，无 outcome_type

**影响**：memory update success/failure 不进入任何 truth/state 系统

**修复路径**：Phase 4 — 可选新增 memory_update_signal，或明确 Memory 属于纯 state 而非 truth

---

## 10. 下一轮最优先方向建议

### 首选：Phase 1 — TruthEventWrapper + OutcomeContractMapper

**理由**：
1. **不修改任何业务代码** — 完全在封装层操作
2. **立即可用** — 所有 14 个现有 outcome_type 都有分类映射
3. **解锁 Mode Router** — TruthEventWrapper 让 Mode Router 可以正确区分 actual vs predicted vs observation
4. **风险最低** — 不改变 governance_state.json 格式，不影响现有消费者

**具体操作**：
1. 新建 `backend/app/m11/truth_event_wrapper.py`
2. 新建 `backend/app/m11/outcome_contract_mapper.py`
3. `governance_bridge.record_outcome()` 外层加 wrapper（不改原函数）
4. 对所有 14 个 outcome_type 做 actual/predicted/truth_type/truth_track 分类
5. 补全 governance_trace_id 传播

### 次选：Phase 2（需 Phase 1 完成后）

在 TruthEventWrapper 验证稳定后，再在 outcome_record 增加 truth_type/truth_track envelope 字段。

---

## 附录：9 个核心问题答案

**Q1**: actual/predicted/success/status/state 来源？
- actual: governance.outcome_records[].actual（1.0/0.0 或 0.95/0.2 或 null）
- predicted: governance.outcome_records[].predicted（number 或 null）
- success: 无单一来源 — RunStatus.success, TaskStatus.COMPLETED, execution_status=success 是三个不同概念
- status: 三种完全不同的语义（queue工作流/UC approval/watchdog health）
- state: 11 个独立 state systems，无统一 schema

**Q2**: 同名不同义字段？
- `actual`: 二值真假 / 质量信号 / 硬编码null
- `status`: queue状态 / UC approval状态 / watchdog健康状态 / 执行状态
- `execution_stage`: 管线节点 / UC审批路由
- `filter_result`: UC U2 pool来源 / task元数据来源

**Q3**: 哪些可进入 success_rate？
- YES: sandbox, tool_execution, asset_promotion, upgrade_center_approval_result, upgrade_center_execution_result
- NO: nightly_evolution, doctrine_drift, UC executions, queue_health_signal

**Q4**: observation_pool actual=0.5？
- observation_signal truth_track，不进入 success_rate
- 0.5 是 neutral 信号，表示"不确定，需观察"

**Q5**: sandbox_execution_result actual=0/1？
- execution_truth truth_track
- actual_value=1.0（verify通过）或 0.0（verify失败）
- 与 predicted_value 配对计算预测准确率

**Q6**: UC execution_result actual=1.0？
- governance_truth truth_track
- actual_outcome truth_type（UC执行结果）
- 但 context.success=true 是真正的 actual

**Q7**: RTCM ARCHIVED/signoff/final_report？
- rtcm_verdict truth_type（新定义）
- actual_value = accept/reject/needs_revision（from acceptance_recommendation）
- rtcm_truth truth_track

**Q8**: Asset promotion？
- 同时是 truth_event（asset_promotion outcome）和 state_event（platform bound）
- asset_truth truth_track
- actual_value=1.0（绑定成功）

**Q9**: 三选一？
- **A — 可以开始实现 Truth/State wrapper**
- Memory scope 问题在 Phase 4 处理，不阻塞 Phase 1
- RTCM context 问题在 Phase 4 处理，不阻塞 Phase 1
- 现有 actual/predicted/state 边界足够清晰，可以开始 wrapper 设计
