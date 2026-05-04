# R63 · Dify 向量服务接入真实性核验

**目标**：核验 Dify 在当前系统里的真实接入状态，判断是"可低成本激活"还是"应正式降级"
**方法**：live 容器核查 + 代码态分析 + Python runtime 调用链追踪

---

## 1. Dify 服务与代码入口核验结果

### Q1: Dify 在当前系统中的真实职责候选

| 候选职责 | 证据 | 定性 |
|---|---|---|
| Dify workflow/agent backend | 无 Dify 容器 | **完全不存在** |
| 向量检索/知识库 | 有 Qdrant（`deerflow-qdrant`），但 collection 为空 | 存在但未接入 |
| bridge 另一端 | bridge_manager 有 Dify→n8n HTTP poll 路径 | 历史设计，从未触发 |
| Bytebot 桌面 agent | `bytebot-ui` / `bytebot-agent` / `bytebot-desktop` | 独立桌面 agent，非 Dify |

**关键发现：R60 报告将 `bytebot-agent/bytebot-ui` 标注为"Dify 向量服务"是错误的。Bytebot 是独立的桌面 agent 系统（Next.js UI + agent runtime），不是 Dify。**

### Q2: Dify 服务是否真实存在

```
容器核查（docker ps）:
  ❌ 无 dify 容器
  ✅ deerflow-qdrant (Qdrant vector DB) — ports 6333-6334
  ✅ bytebot-ui — port 9992 (Next.js web UI for Bytebot)
  ✅ bytebot-agent — port 9991 (Bytebot agent runtime)
  ✅ bytebot-desktop — port 9990 (Desktop isolation)
  ✅ bytebot-postgres — port 5432 (Bytebot's postgres)

结论：Dify 容器完全不存在。
```

### Q3: 代码里的 Dify 入口

| 文件 | 语言 | 状态 | 是否参与 runtime |
|---|---|---|---|
| `src/infrastructure/workflow/dify_client.ts` | TypeScript | M04 层 | ❌ 未编译（/app/dist 为空） |
| `src/domain/m04/dify_adapter.ts` | TypeScript | M04 层 | ❌ 未编译（/app/dist 为空） |
| `src/domain/m04/unified_executor.ts` | TypeScript | M04 层 | ❌ 未编译（/app/dist 为空） |
| `src/domain/m04/bridge_manager.ts` | TypeScript | M04 层 | ❌ 未编译（/app/dist 为空） |

所有 Dify 相关代码均在 **M04 ABANDONED** 层，与 n8n 完全相同。

### Q4: Python runtime 是否消费 Dify

```
Python runtime 核查（全量 /app .py 文件搜索）:
  ❌ 0 条 qdrant 导入
  ❌ 0 条 dify 导入
  ❌ 0 条向量/embedding 客户端导入
  ✅ Agent-S 的 embedding 代码存在于 /app/backend/external/Agent-S/（独立系统）

结论：Python uvicorn 运行时与 Dify/Qdrant/向量服务完全断链。
```

---

## 2. 最小能力链或降级路径判断结果

### Q5: Qdrant 向量服务的实际状态

```
Qdrant 容器状态（live）:
  ✅ 服务健康：REST API 响应正常
  ✅ collection 存在：deerflow_experiences
  ✅ collection 配置：1536 维，Cosine 距离
  ❌ 0 indexed_vectors，0 points — 完全空的

结论：Qdrant 已初始化但从未写入数据。可能是"先部署了基础设施，计划以后接入"的状态。
```

### Q6: 最小激活路径分析

**候选 A：激活 Dify workflow**
- 无 Dify 容器 → 需要新部署 Dify 服务 → 不符合"低成本"
- M04 已废弃，TypeScript 未编译 → 即使部署了 Dify 也无法从 app 调用

**候选 B：激活 Qdrant 向量检索**
- Qdrant 服务存在，但 collection 为空（0 points）
- 需要：① 接入 Python 向量写入 pipeline；② 接入向量检索 API 到 app
- Python runtime 无向量客户端 → 需要新增 Python 向量客户端代码
- 不是"激活"而是"从零构建" → 高成本

**候选 C：降级为 ABANDONED（与 R62 n8n 一致）**
- Dify：完全不存在，无容器，无 runtime 入口 → ABANDONED
- Qdrant：服务存在但内容为空 → INACTIVE_SERVICE
- Bytebot：独立桌面 agent 系统，未与主链交互 → INACTIVE_SERVICE

**判断：选择候选 C（降级）**

---

## 3. 最小修复/处置方案

### Dify 定性修正

| 模块 | R60 标注 | R63 更新 | 原因 |
|---|---|---|---|
| Dify 向量服务 | REAL_BUT_NOT_ACTIVATED / 未验证 | **ABANDONED** | 无 Dify 容器，无 runtime 入口 |
| Qdrant 向量 DB | （未单独标注） | **INACTIVE_SERVICE** | collection 为空，从未写入 |
| Bytebot 系统 | （未单独标注） | **INACTIVE_SERVICE** | 独立 desktop agent，未与主链交互 |

### 无需代码修改的原因

```
所有 Dify/Bytebot/Qdrant 相关代码均为 TypeScript（M04 ABANDONED 层）：
  - dify_client.ts / dify_adapter.ts / unified_executor.ts — TypeScript 源码
  - bridge_manager.ts — TypeScript 源码
  - /app/dist = 空目录（从未编译）

Python uvicorn 运行时：
  - 100% Python 代码
  - 0 条 qdrant/dify/向量 导入
  - 与 TypeScript M04 层完全隔离

Qdrant collection：
  - deerflow_experiences: 0 points（从未写入）
  - 是"已初始化的空基础设施"，不是"待激活的内容"
```

---

## 4. 真实性/去误导验证结果

### R60 报告中的 Dify 标注错误

R60 报告将 `bytebot-agent/bytebot-ui` 标注为"Dify 向量服务"：

```
R60 原文：
  | M8 | Dify 向量服务 | 文档检索/Embedding 服务（bytebot-agent/bytebot-ui），未验证接入 |

修正：
  bytebot-agent/bytebot-ui ≠ Dify
  它们是 Bytebot Desktop Agent 系统的容器（bytebot.ai 产品）
  Dify 服务在当前系统中完全不存在
```

### Qdrant 实际状态

```
Qdrant（deerflow-qdrant，ports 6333-6334）:
  - 是向量数据库（Qdrant）
  - 不是 Dify（后者是 LLM workflow/agent 平台）
  - collection deerflow_experiences: 1536维，0 points
  - 存在但从未被写入数据

Bytebot（bytebot-*, ports 9990-9992）:
  - 是独立桌面 agent 产品（bytebot.ai）
  - 有自己的 Next.js UI（bytebot-ui）
  - 有自己的 agent runtime（bytebot-agent）
  - 有自己的 desktop isolation（bytebot-desktop）
  - 与 OpenClaw 主链没有已知 API 集成
```

---

## 5. 回归验证结果

### R1: Dify 服务、代码入口、运行态调用者三者状态

| 组件 | 服务态 | 代码态 | 运行态 | 定性 |
|---|---|---|---|---|
| Dify | ❌ 无容器 | TypeScript in M04 | ❌ 未编译 | **ABANDONED** |
| Qdrant | ✅ 6333-6334 健康 | 无 Python 客户端 | ❌ 0 points 写入 | **INACTIVE_SERVICE** |
| Bytebot | ✅ 9990-9992 健康 | 无 Python 客户端 | ❌ 0 交互 | **INACTIVE_SERVICE** |

### R2: Dify 是可低成本激活还是应正式降级

**判定：应降级（ABANDONED）**

- Dify：无容器 + M04 废弃 + TypeScript 未编译 → 完全没有低成本激活路径
- Qdrant：服务存在但 collection 为空 → 需要从零构建向量 pipeline
- Bytebot：独立产品，未集成 → 需要额外集成工作

### R3: 完成最小降级处置

**无需代码修改**。更新分类体系标注即可。

### R4: 减少"服务在跑但集成是假"的误导点

- R60 中"Dify 向量服务（bytebot-agent/bytebot-ui）"标签已修正
- Qdrant 和 Bytebot 现在有正确的 INACTIVE_SERVICE 定性

### R5: 不引入新平行系统，不破坏主链

✅ 无修改

### R6: 本轮输出足以判断 Dify 模块不值得继续投入

**判定：完全不值得。** Dify 容器不存在，无法激活。

---

## 6. 本轮后的全局判断

```
OpenClaw/DeerFlow 系统状态（R63 后）

核心主链（全部坐实）：
  ✅ Gateway API + Health（HTTP/SSE 入口）
  ✅ LangGraph Agent + Tool Executor
  ✅ OCHA L2 Governance（pre-execution gate）
  ✅ LearningMiddleware Outcome Backflow
  ✅ Provider / MiniMax（LLM 推理）
  ✅ Docker / Runtime（容器运行）
  ✅ Feishu WS（running=true，Event Subscription 待配置）

已降级/断链模块：
  🔶 n8n automation: INACTIVE_SERVICE（服务在跑但与主链完全断链）
  🔶 Dify: ABANDONED（无容器，无 runtime 入口，从未部署）
  🔶 Qdrant 向量: INACTIVE_SERVICE（collection 空，从未写入）
  🔶 Bytebot Desktop Agent: INACTIVE_SERVICE（独立产品，未集成）
  ⚠️  Feishu WS 无 ingress（Event Subscription 未配置）

已废弃（无需处置）：
  ⚪ M04 TypeScript 协调层（ABANDONED，无构建无入口）
  ⚪ Coprocessor Governance（FUTURE_COPROCESSOR_ORCHESTRATION）

结论：
  R60-R63 完成了对所有"非核心主链但看起来存在"的模块的总清算。
  n8n、Dify、Qdrant、Bytebot 都是"已部署但未集成"或"从未部署"的模块。
  核心主链之外的模块全部处于断链/空壳状态，不是代码 bug，是架构未落地。
```

---

## 7. 下一轮最优先方向建议

**推荐 Round 64：Feishu Bot Event Subscription 手动配置验证**

**原因**：
1. R61 已确认：Feishu WS 物理连接正常（`running=true`），但 8h 无 ingress 消息
2. 原因是 **Feishu Developer Console 的 Event Subscription 未配置**（`InboundMessage.__init__() missing user_id` 证明收到过格式不对的消息）
3. 这是**唯一一个可以手动配置激活**的断点——其他模块（n8n、Dify、Qdrant）都需要重构或从零构建

**处置步骤**（已在 R61 给出）：
1. 登录 https://open.feishu.cn/app → 找到 `cli_a92772edd278dcc1` 应用
2. 检查 Event Subscription → 添加 `im.message.receive_v1`
3. 将 Bot 添加到测试群/对话
4. 手动发送一条消息，验证 `_on_message` 是否触发

**不建议继续深挖 Dify/Bytebot**：
- Dify 完全不存在容器，无法激活
- Bytebot 是独立产品，未集成，无 API 调用路径
- 继续只会重复相同结论

**本轮核心贡献**：R60-R63 建立了完整的"主链 vs 断链"认知地图。所有断链模块均已定性：n8n INACTIVE，Dify ABANDONED，Qdrant INACTIVE，Bytebot INACTIVE，Feishu 待配置（唯一可低成本激活的断点）。
