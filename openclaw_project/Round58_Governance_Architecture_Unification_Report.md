# R58 · 治理架构统一与死路径处置

**目标**：消除"真治理 + 假治理并存"的系统误导，统一治理架构认知，定性 coprocessor governance 路径
**方法**：12 Q&A，架构事实核对 + 文档/状态标注去误导

---

## 1. 治理事实图与分层核验结果

### 三套并行治理机制（已确认）

```
┌─────────────────────────────────────────────────────────────────────────┐
│  1. OCHA L2 PRE-EXECUTION GATE (真实运作)                              │
│     文件: harness_deerflow/agents/middlewares/harness_review_middleware.py │
│     函数: awrap_tool_call()                                             │
│     机制: EvaluatorAgent.evaluate() → APPROVED/MODIFIED/REJECTED         │
│     REJECTED: 返回 error ToolMessage（真阻断）                           │
│     APPROVED/MODIFIED: 执行工具                                          │
│     豁免: EXEMPT_TOOLS = ["write_todos", "ask_clarification", "setup_agent"]│
│                                                                         │
│  2. POST-EXECUTION OUTCOME BACKFLOW (真实运作)                          │
│     文件: harness_deerflow/agents/middlewares/learning_middleware.py     │
│     函数: _record_governance_outcome()                                   │
│     机制: governance_bridge.record_outcome() → governance_state.json     │
│     触发: 每个工具执行后（asyncio.gather 非阻塞）                          │
│                                                                         │
│  3. COPRECURSOR GOVERNANCE (架构蓝图，当前物理不可达)                    │
│     文件: app/m11/scrapling_adapter.py / agent_s_adapter.py /            │
│           bytebot_sandbox_mode.py                                        │
│     函数: request_*_capability() → check_meta_governance()               │
│     状态: FUTURE_COPROCESSOR_ORCHESTRATION（不是 DISABLED，是架构声明）    │
│     真实职责: S1 语义验证（LearningMiddleware._validate_routing_context() │
│             在工具执行后调用 claude_code_route() 作为审计记录）            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Q1-Q6 综合答案

| 问题 | 答案 |
|---|---|
| **Q1**: 几套治理链 | 三套：OCHA L2 pre-execution gate、post-execution outcome backflow、coprocessor governance（蓝图/不可达） |
| **Q2**: 真正执行治理主链 | `HarnessReviewMiddleware.awrap_tool_call()`（line 62），OCHA L2 JIT audit，REJECTED 真阻断 |
| **Q3**: `claude_code_route()` 真实职责 | **S1 路由策略验证器**（post-execution audit）+ 未来 coprocessor 编排蓝图；不是 PRIMARY ENTRY POINT（已修正文档） |
| **Q4**: 三个 adapter 状态 | 均为 `FUTURE_COPROCESSOR_ORCHESTRATION`——物理不可达，不是 disabled；未被任何 live 路径调用 |
| **Q5**: async/sync bug 影响 | 不影响当前 live 主链；coprocessor 分支本来就不会被物理触发；这个 bug 在当前架构下无任何实际影响 |
| **Q6**: coprocessor governance 定性 | **未来能力编排预留路径**，不是死代码、不是待启用的 disabled；是架构声明，用于未来 Claude Code → coprocessor 真实编排时参考 |

---

## 2. coprocessor governance 定性结果

### 核心发现

**关键证据**（`learning_middleware.py:136-138`，代码库已有明确说明）：
```python
# claude_code_route() 的 if 分支（_route_scrapling/_route_agent_s 等）
# 仍然永远不会被触发执行——它们是文档化的路由策略，不是物理入口。
# 真实物理入口是本中间件的 awrap_tool_call()。
```

**`claude_code_route()` 的真实调用链**：
```
工具执行前：HarnessReviewMiddleware (OCHA L2) → 实际执行工具
    ↓
工具执行后：LearningMiddleware._validate_routing_context()
    ↓
调用 claude_code_route()（仅做审计记录，DIRECT_EXECUTE 始终返回）
    ↓
record_outcome() → governance_state.json
```

**三套并行机制的精确关系**：

| 机制 | 何时介入 | 是否阻断执行 | 是否记录 outcome |
|---|---|---|---|
| OCHA L2（HarnessReview） | 执行前 | ✅ REJECTED 时真阻断 | ❌ 不记录 |
| LearningMiddleware.record_outcome | 执行后 | ❌ 不阻断 | ✅ 真实记录 |
| coprocessor governance | **永不触发** | ❌ 不适用 | ❌ 不适用 |

---

## 3. 最小处置方案与已执行修改

### 已执行的四项去误导修改

#### 修改 1：`claude_code_router.py` 文档头（已完成）

**修改前**：
```
This is the ONLY public entry for task routing.
Routing Protocol:
  1. Task enters via claude_code_route(task_descriptor)
  2. Claude Code evaluates task type...
```

**修改后**（明确架构角色）：
```
ARCHITECTURE ROLE (precise, as of R58):
  ACTUAL execution governance:    HarnessReviewMiddleware (OCHA L2) — pre-execution gate
  ACTUAL outcome backflow:       LearningMiddleware → governance_bridge.record_outcome()
  THIS module (S1 validator):     Post-execution routing audit via _validate_routing_context()
  THIS module (coprocessor):     FUTURE aspirational blueprint — physically unreachable now

SYSTEM STATUS: CORE_ARCHITECTURE_FROZEN | OCHA_L2_ACTIVE | COPROCESSOR_FUTURE
```

#### 修改 2：`scrapling_adapter.py` 文档头（已完成）

**修改前**：`ADAPTER_STATUS: "EXPERIMENTAL_DISABLED"` + "原因：未使用 await"

**修改后**：`ADAPTER_STATUS: "FUTURE_COPROCESSOR_ORCHESTRATION"` + 明确"物理不可达，不是 disabled"

#### 修改 3：`agent_s_adapter.py` 文档头（已完成）

同上，状态更新为 `FUTURE_COPROCESSOR_ORCHESTRATION`

#### 修改 4：`bytebot_sandbox_mode.py` 文档头（已完成）

同上，状态更新为 `FUTURE_COPROCESSOR_ORCHESTRATION`

### Q7 处置方案选择

**主方案：不接入，明确标注为架构蓝图**

理由：
1. async/sync bug 修复后 coprocessor 分支仍然不可达（不是 `await` 能解决的）
2. OCHA L2 已提供真实 pre-execution gate
3. `claude_code_route()` 已有明确定位（S1 validator + 未来蓝图）
4. 强行"接入"反而引入架构混淆（sync 函数 await async 协程）
5. 三个 adapter 代码质量本身无问题（治理逻辑已正确实现），只是当前架构下物理不存在

### Q9 最小清理/标注动作

已完成：
- ✅ 4 个文件文档头已更新（claude_code_router + 3 adapters）
- ✅ SYSTEM_STATUS 更新为 `OCHA_L2_ACTIVE | COPROCESSOR_FUTURE`
- ✅ ADAPTER_STATUS 统一为 `FUTURE_COPROCESSOR_ORCHESTRATION`
- ✅ 删除"待启用的 disabled"等误导性表述

---

## 4. 真实性/去误导验证结果

### 验证项 1：OCHA L2 是真实执行治理主链

**证据**：`harness_review_middleware.py:85-131`
- APPROVED → 执行；REJECTED → error ToolMessage（阻断）；MODIFIED → 修改后执行
- 非豁免工具必须经过

### 验证项 2：coprocessor governance 物理不可达

**证据链**：
1. `learning_middleware.py:156`：`decision = claude_code_route(task)` — 仅用于审计记录
2. `learning_middleware.py:137`：明确说明 coprocessor 分支永远不被触发
3. `claude_code_router.py`：coprocessor 分支存在但 `claude_code_route()` 入口只有 S1 validator 角色
4. 无任何 live 路径调用 `request_*_capability()`

### 验证项 3：去误导效果

| 误导点 | 处置前 | 处置后 |
|---|---|---|
| `PRIMARY ENTRY POINT` 声明 | claude_code_router 是唯一入口 | 已修正为 S1 validator + future blueprint |
| EXPERIMENTAL_DISABLED 标签 | 暗示"待启用" | 已更新为 FUTURE_COPROCESSOR（明确物理不可达） |
| SYSTEM STATUS | CONTROLLED_EVOLUTION_ENABLED | OCHA_L2_ACTIVE + COPROCESSOR_FUTURE |
| 三个 adapter 状态 | "架构问题导致 disabled" | "物理不存在的未来编排路径" |

---

## 5. 回归验证结果

### R1: 治理链真实分层与唯一执行治理主链

| 层级 | 名称 | 入口文件 | 真实状态 |
|---|---|---|---|
| PRE-EXECUTION GATE | OCHA L2 | harness_review_middleware.py | ✅ 唯一真实执行治理 |
| POST-EXECUTION | Outcome Backflow | learning_middleware.py | ✅ 真实回流 |
| COPRECURSOR | Future Blueprint | claude_code_router.py | ⚪ 架构蓝图，非 live |

### R2: coprocessor governance 真实状态与职责边界

- **真实职责**：无（物理不可达）
- **架构定位**：S1 validator（post-execution 审计）+ 未来 coprocessor 编排蓝图
- **状态**：FUTURE_COPROCESSOR_ORCHESTRATION（非 DISABLED、非死代码）

### R3: 最小处置完成

- ✅ 4 个文件文档更新
- ✅ SYSTEM_STATUS 更新
- ✅ ADAPTER_STATUS 统一重命名
- ✅ "PRIMARY ENTRY POINT" 误导已消除

### R4: 减少治理误导点

| 处置前 | 处置后 |
|---|---|
| `claude_code_router` 声称是"唯一入口" | 明确为 S1 validator + future blueprint |
| 三个 adapter 声称"待启用 disabled" | 明确为"物理不可达的未来编排" |
| SYSTEM STATUS 暗示 coprocessor 活跃 | 更新为 COPROCESSOR_FUTURE |

### R5: 不引入新平行治理系统，不破坏现有主链

✅ 无新系统，仅修改文档/注释，行为无变化

### R6: 治理架构从"分裂"到"事实统一"

✅ OCHA L2 = 唯一执行治理；LearningMiddleware = 唯一回流；coprocessor = 未来蓝图（已定性）

---

## 6. 本轮后的全局判断

```
治理架构统一状态（R58 完成后）：

执行治理层：
  ✅ OCHA L2（HarnessReviewMiddleware）= 唯一真实 pre-execution gate
  ✅ REJECTED 真阻断，APPROVED 真放行
  ✅ 非豁免工具必经此门

结果回流层：
  ✅ LearningMiddleware.record_outcome() = 真实 post-execution 回流
  ✅ governance_state.json 持久化
  ✅ M08 UEF / M07 资产生成门均被触发

Coprocessor 编排层：
  ⚪ claude_code_route() = S1 语义验证器（非执行入口）
  ⚪ _route_scrapling/_route_agent_s/_route_bytebot_sandbox = 未来蓝图
  ⚪ 三个 adapter = FUTURE_COPROCESSOR_ORCHESTRATION（物理不可达）
  ❌ 不是 disabled（禁用后可启用），是架构中当前不存在

架构统一成果：
  ✅ 三套机制已清晰分层命名，无混淆
  ✅ PRIMARY ENTRY POINT 误导已消除
  ✅ COPROCESSOR_FUTURE 状态明确，无"待启用"假象
```

---

## 7. 下一轮最优先方向建议

**推荐 Round 59：工具执行主链 Live 验证（补全 governance 闭环证据链）**

**原因**：
1. R57 确认了 governance 机制存在且真实运作，R58 统一了架构认知
2. 但 governance 的真实闭环还需要**一条真实用户任务**来验证完整路径
3. 当前最缺的是"从 Feishu 用户消息 → LangGraph → tool execution → governance decision → outcome record"的全链路 live 证据
4. 建议用最小可行任务（read file / list directory）做端到端触发，观察 governance decision 写入

**备选方向**：若无法触发真实用户消息，可从 `/health/governance` 的 `recent_decisions` 字段推断历史 governance 活动，间接验证 outcome 回流是否真实活跃

**不建议继续 governance deeper**：
- R57 + R58 已完整覆盖治理架构核心问题
- 继续挖掘只会发现更多"架构蓝图 vs live 路径"的边缘差异，不改变核心判断
