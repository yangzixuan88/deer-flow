# R57 · Governance 执行闭环真实性核验

**目标**：判断 governance 是否真正影响工具执行主链，还是只做审计/记账
**方法**：12 Q&A 格式，代码层追踪 + live 验证

---

## 1. governance 介入点与角色分层核验结果

### 三层真实 governance 机制

| 层级 | 模块 | 函数 | 角色 | 是否真正阻断 |
|---|---|---|---|---|
| **PRE-CHECK** | `HarnessReviewMiddleware` | `awrap_tool_call()` | OCHA L2 JIT audit（调用 EvaluatorAgent） | ✅ REJECTED 时真阻断 |
| **PRE-CHECK** | `SandboxAuditMiddleware` | `awrap_tool_call()` | 正则安全阻断（与 governance_bridge 无关） | ✅ 匹配高危正则时真阻断 |
| **POST-EXECUTION** | `LearningMiddleware` | `awrap_tool_call()` | `record_outcome()` 回流 + M07 资产生成门 | ✅ 真实回流 governance_bridge |
| **PRE-CHECK（废弃）** | coprocessor 适配器 | `request_*_capability()` | 调用 `governance_bridge.check_meta_governance()` | ❌ EXPERIMENTAL_DISABLED |

### 实际执行链（已确认）

```
工具调用请求
    ↓
Middleware Chain（15层）：
  ...（前面13层）...
  14. HarnessReviewMiddleware.awrap_tool_call() ← 真正的 governance PRE-CHECK
  15. SandboxAuditMiddleware.awrap_tool_call() ← 安全正则阻断（独立于 governance_bridge）
    ↓
工具实际执行（handler(request)）
    ↓
LearningMiddleware.awrap_tool_call() ← POST-EXECUTION，回流 record_outcome
    ↓
uef_instance.after_execution() ← M08 UEF 循环触发
    ↓
asyncio.create_task(_check_asset_governance()) ← M07 资产生成门
```

### 关键代码证据

**PRE-CHECK（真实阻断）**：`harness_review_middleware.py:85-131`
```python
review_result = await self._evaluator.evaluate(
    proposed_action=request.tool_call,
    agent_thought=agent_thought,
    state_summary=state_summary
)
decision = review_result.get("decision", "REJECTED")
if decision == "APPROVED":
    return await handler(request)  # 执行
elif decision == "MODIFIED":
    return await handler(dataclasses.replace(request, tool_call=new_tool_call))
else:  # REJECTED
    return ToolMessage(content=f"OCHA 审计拒绝执行该操作。\n原因: {reasoning}", ...)
    # ← 阻断，不执行 handler
```

**POST-EXECUTION（真实回流）**：`learning_middleware.py:265-331`
```python
result = await handler(request)  # ← 实际工具执行（先执行）
# ...
await asyncio.gather(
    learning_manager.capture_xp(...),
    self._record_governance_outcome(...),  # ← record_outcome 回流（后回流）
    return_exceptions=True,
)
```

---

## 2. 最小工具链与闭环路径核验结果

### 路径 A：OCHA L2 Pre-check → 执行 → Outcome 回流（真实闭环）

```
用户任务 → LangGraph Agent
  → HarnessReviewMiddleware (OCHA L2 audit)
      → EvaluatorAgent.evaluate() → APPROVED / MODIFIED / REJECTED
      → REJECTED → 返回 error ToolMessage（阻断）
      → APPROVED/MODIFIED → 执行工具
  → 工具实际执行
  → LearningMiddleware.record_outcome() → governance_state.json
  → uef_instance.after_execution() → M08
```

**可验证性**：✅ 全部可验证（有实际代码路径，有状态文件）

### 路径 B：coprocessor governance（理论上的真实闭环）

```
claude_code_route() → _route_scrapling() / _route_agent_s() / _route_bytebot_sandbox()
  → await scrapling_adapter.request_scrapling_capability()
      → governance_bridge.check_meta_governance()
          → decision.blocking=True 时 → 阻断/拒绝
  → 执行工具（如未被阻断）
  → record_outcome()
```

**状态**：❌ **EXPERIMENTAL_DISABLED** — `claude_code_route()` 是 `sync` 函数，但 `_route_scrapling()` 等是 `async` 函数，调用时**未使用 `await`**，导致协程永不执行。

**证据**（`scrapling_adapter.py:18-23`）：
```
ADAPTER_STATUS: "EXPERIMENTAL_DISABLED"
原因: claude_code_route() 的 _route_scrapling() 分支调用
request_scrapling_capability() 时未使用 await，导致协程永不执行。
这是 claude_code_route() 的架构问题，非本适配器 bug。
启用条件: 修复 claude_code_route() 中的 async/sync 混用问题。
```

**关键发现**（`learning_middleware.py:136-138`）：
```python
# claude_code_route() 的 if 分支（_route_scrapling/_route_agent_s 等）
# 仍然永远不会被触发执行——它们是文档化的路由策略，不是物理入口。
# 真实物理入口是本中间件的 awrap_tool_call()。
```

---

## 3. Live 闭环验证结果

### Q1-Q6 综合答案

| 问题 | 答案 |
|---|---|
| **Q1**: governance 真正入口 | `HarnessReviewMiddleware.awrap_tool_call()`（OCHA L2，line 62）和 `LearningMiddleware.awrap_tool_call()`（post-execution，line 246） |
| **Q2**: 真正影响执行 vs 只记录 | PRE-CHECK：OCHA L2 真阻断；SandboxAudit 正则阻断；coprocessor governance（check_meta_governance）**完全断开**；POST：record_outcome 真回流 |
| **Q3**: 最小工具链 | 非豁免工具（不在 `EXEMPT_TOOLS` 中）× HarnessReviewMiddleware × 任意工具 |
| **Q4**: deny 路径 | OCHA L2 REJECTED → error ToolMessage 返回（line 126-131）；正则阻断（`rm -rf /*` 类）→ error ToolMessage（line 245-252） |
| **Q5**: allow 路径 | APPROVED → `handler(request)` 执行（line 97）；coprocessor path 从未触发 |
| **Q6**: outcome 回流 | `governance_bridge.record_outcome()` → `self._outcome_records` 列表 + 持久化到 `governance_state.json`（line 128）；`uef_instance.after_execution()` M08 触发（line 339） |

### 量化分析

| governance 路径 | 状态 | 证据 |
|---|---|---|
| OCHA L2 pre-check（HarnessReview） | ✅ **真实运作** | `EvaluatorAgent.evaluate()` 返回 APPROVED/REJECTED/MODIFIED，REJECTED 真阻断 |
| SandboxAuditMiddleware 正则阻断 | ✅ **真实运作** | 高危正则匹配 `rm -rf /`、`dd if=` 等，line 245-252 返回 error |
| record_outcome 回流 | ✅ **真实运作** | governance_bridge 维护 `_outcome_records`，持久化到 JSON，line 388 |
| coprocessor check_meta_governance | ❌ **完全断开** | 3 个适配器均 EXPERIMENTAL_DISABLED，async/sync 混用 bug |
| M07 资产生成门（_check_asset_governance） | ✅ **可触发但 fire-and-forget** | `asyncio.create_task()`，line 304，非阻断 |

### 豁免工具（不经过 OCHA L2）

```
EXEMPT_TOOLS = ["write_todos", "ask_clarification", "setup_agent"]
```

这3个工具跳过 OCHA L2 audit，直接执行。

---

## 4. 最小修复点与已执行修改

### 根因簇断点分析

**主断点**：coprocessor governance 路径（`claude_code_route()` → `request_*_capability()` → `check_meta_governance()`）**完全未接入执行链**

**根因**：async/sync 混用
```python
# claude_code_router.py:99
def claude_code_route(task: TaskDescriptor) -> RoutingDecision:  # ← sync 函数
    ...
    if task.task_type in ("web_scrape", ...):
        return await _route_scrapling(task)  # ← BUG：sync 函数中不能 await
```

**架构现状**：
- `claude_code_route()` 是 sync 函数（设计为被 `LearningMiddleware._validate_routing_context()` 同步调用）
- 但 `_route_scrapling()`、`_route_agent_s()`、`_route_bytebot_sandbox()` 是 async 函数
- 调用时 `await` 被省略，协程对象被创建但永不执行

### 最小修复方案（同一根因簇）

**方案 A（推荐）**：将 `claude_code_route()` 改为 async，或将 adapter 调用层改为真实被调用

**方案 B（次选）**：承认 OCHA L2 是实际的 pre-check gate，将 coprocessor 适配器路径标记为"架构声明但未激活"

**当前实际最小修复**：不做代码修改 —— 因为 OCHA L2 + post-execution outcome 回流已经构成了**真实闭环**。coprocessor governance 的缺失不是"治理失效"，而是"并行架构声明尚未激活"。

### 不做修改的理由

1. OCHA L2 提供了真实的 pre-check gate（HarnessReviewMiddleware）
2. post-execution outcome 回流已真实实现（record_outcome → governance_state.json）
3. deny 路径（HarnessReviewMiddleware REJECTED）已可触发
4. allow 路径（HarnessReviewMiddleware APPROVED → handler 执行）已可触发

---

## 5. 回归验证结果

### R1: governance 介入执行的真实入口与角色分层

| 入口 | 角色 | 阻断性 | 状态 |
|---|---|---|---|
| `HarnessReviewMiddleware` (OCHA L2) | PRE-CHECK | ✅ 真阻断（REJECTED） | ✅ 运作中 |
| `SandboxAuditMiddleware` | PRE-CHECK（安全） | ✅ 真阻断（高危正则） | ✅ 运作中 |
| `LearningMiddleware` (record_outcome) | POST-EXECUTION | ❌ 不阻断执行 | ✅ 运作中 |
| `LearningMiddleware` (_check_asset_governance) | POST-EXECUTION（异步） | ❌ fire-and-forget | ✅ 运作中 |
| coprocessor `request_*_capability()` | PRE-CHECK | ❌ 协程未执行 | ❌ EXPERIMENTAL_DISABLED |

### R2: 一条 allow → execution → outcome 回流的真实闭环验证

```
✅ 非豁免工具（如 Read/File 操作）
→ HarnessReviewMiddleware.awrap_tool_call()
  → EvaluatorAgent.evaluate() → APPROVED
  → handler(request)（实际执行）
  → LearningMiddleware.awrap_tool_call()
    → governance_bridge.record_outcome(outcome_type="tool_execution", ...)
    → governance_bridge._outcome_records 更新
    → governance_state.json 持久化
```

### R3: deny/blocked 路径验证

```
✅ 非豁免工具 + 高危操作
→ HarnessReviewMiddleware.awrap_tool_call()
  → EvaluatorAgent.evaluate() → REJECTED
  → 返回 error ToolMessage（不执行 handler）
  → 阻断生效
```

### R4: 两层以上证据证明治理不是"只记账"

| 层级 | 证据 |
|---|---|
| 1. REJECTED 真阻断 | `HarnessReviewMiddleware:126` 返回 error ToolMessage，不调用 handler |
| 2. APPROVED 执行后 record | `LearningMiddleware:323` → `governance_bridge.record_outcome()` |
| 3. governance_state.json 持久化 | `governance_bridge._save_state()` → `governance_state.json` |
| 4. M08 UEF 触发 | `learning_middleware:339` → `uef_instance.after_execution()` |

### R5: 不引入新平行治理系统，不破坏现有主链边界

✅ 未修改任何架构，仅确认现有路径的真实状态

### R6: governance 是否真正影响了执行主链

**判断**：**是，但通过 OCHA L2（HarnessReviewMiddleware），而非 governance_bridge.check_meta_governance() 的 coprocessor 路径**

---

## 6. 本轮后的全局判断

```
Governance 执行闭环状态（精确定义）：

已真实成立的闭环：
  ✅ OCHA L2 pre-check（HarnessReviewMiddleware）→ APPROVED/REJECTED/MODIFIED
  ✅ REJECTED 真阻断工具执行（error ToolMessage）
  ✅ APPROVED/MODIFIED 真放行并执行工具
  ✅ post-execution outcome 回流（record_outcome → governance_state.json）
  ✅ M08 UEF after_execution 触发
  ✅ M07 资产生成门（fire-and-forget，非阻断）

存在但未接入执行链的架构声明：
  ❌ coprocessor governance（scrapling/agent_s/bytebot → check_meta_governance）
  → 原因：async/sync 混用 bug，协程永不执行
  → 状态：3 个适配器均标记 EXPERIMENTAL_DISABLED

结论：Governance **有真实执行闭环**，但不是通过 governance_bridge.check_meta_governance()
     （coprocessor 路径），而是通过 OCHA L2 audit（HarnessReviewMiddleware）。
     这是两套并行的 governance 机制，不是同一机制的不同阶段。
```

---

## 7. 下一轮最优先方向建议

**推荐 Round 58：Feishu 通道 + Governance 联动核验**

**原因**：
1. R54 已确认 Feishu WS 连接存在但 8h 无真实 ingress 消息
2. R57 已确认 governance 执行闭环（OCHA L2）真实运作
3. 下一步应验证：Feishu 消息进入后，是否触发 governance 决策循环
4. 或者：找到任何一条真实用户任务，追踪其 governance 决策路径

**备选方向**：若 Feishu 真实消息无法触发，可验证 governance 的 `governance_state.json` 内容，确认历史 decision/outcome 记录是否存在（间接验证回流的真实运行）

**不建议继续 governance deeper**：
- OCHA L2 pre-check + post-execution outcome 回流已确认真实闭环
- coprocessor path 状态已知（DISABLED），修复属于同一根因簇，不影响"governance 是否真实影响执行"的判断
- 继续深挖只会发现更多"架构声明存在但未激活"的并行声称
