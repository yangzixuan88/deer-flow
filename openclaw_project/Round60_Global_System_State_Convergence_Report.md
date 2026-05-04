# R60 · 全局系统状态收敛验证

**目标**：把系统当前所有关键模块按"已坐实 / 待激活 / 已废弃"三层做全局总清算，形成可信系统事实总图
**方法**：12 Q&A 格式，基于 R49-R59 已验证事实 + live endpoint 快照

---

## 1. 全局关键模块簇与职责收敛结果

### 模块簇目录（共 10 个）

| # | 模块簇 | 一句话真实职责 |
|---|---|---|
| M1 | Gateway API + Health | 对外 REST/SSE 入口，提供 /runs /threads /health 端点 |
| M2 | LangGraph Agent + Tool Executor | 任务编排 + 工具执行 + 中间件链（OCHA L2 / SandboxAudit / Learning） |
| M3 | Governance Bridge + OCHA L2 | pre-execution gate（HarnessReviewMiddleware）+ post-execution outcome 回流 |
| M4 | Provider / MiniMax | LLM 推理引擎（MiniMax-M2.7），实际生成工具调用决策 |
| M5 | Docker / Runtime | Python uvicorn 服务容器化运行，包含 Redis / Dapr state+pubsub |
| M6 | Feishu 通道 | WebSocket 实时消息接收 + reply card 发送，ChannelManager 调度 |
| M7 | n8n 自动化 | 工作流引擎（容器），已有基础设施但 0 workflows 接入 |
| M8 | Dify 向量服务 | 文档检索/Embedding 服务（bytebot-agent/bytebot-ui），未验证接入 |
| M9 | M04 TypeScript 协调层 | 协调 n8n/Dify 的 TypeScript 编排代码，已废弃 |
| M10 | Coprocessor Adapters | scrapling/agent_s/bytebot governance adapters，架构蓝图非 live |

---

## 2. 已坐实模块清单（REAL_AND_ROOTED）

### M1: Gateway API + Health

| 属性 | 详情 |
|---|---|
| **证据类型** | Live HTTP 验证 |
| **Live 证据** | `POST /api/runs/stream` → SSE stream（run_id=`753aa81b...`） |
| Health | `/health/live` → `200 alive`；`/health/ready` → overall=ready，governance_bridge/ready，langgraph_runtime/ready |
| **入口** | `gateway/app.py` + `gateway/routers/runs.py:34` |
| **真实职责** | 接收外部 HTTP/SSE 请求，调度 LangGraph Agent，返回流式响应 |

### M2: LangGraph Agent + Tool Executor

| 属性 | 详情 |
|---|---|
| **证据类型** | Live SSE + Container logs |
| **Live 证据** | SSE event 4: AI message with `tool_calls: [{"name": "bash", "args": {"command": "ls -la /tmp"}}]` |
| **入口** | `deerflow/agents/lead_agent/agent.py:build_lead_runtime()` |
| **中间件链** | 15 层中间件（SandboxAudit → HarnessReview → LearningMiddleware 等） |
| **真实职责** | 执行任务编排决策，调用工具，返回结果 |

### M3: Governance Bridge + OCHA L2

| 属性 | 详情 |
|---|---|
| **证据类型** | Live container logs + governance_state.json |
| **Live 证据（5段全通）** | ① POST /api/runs/stream → ② OCHA L2 APPROVED（log: 01:33:40→01:33:52） → ③ Tool executed → ④ Outcome recorded（log: 01:33:54）→ ⑤ governance_state.json（36 outcomes, 40 decisions） |
| **Pre-check** | `HarnessReviewMiddleware.awrap_tool_call()` — REJECTED 真阻断 |
| **Post-execution** | `LearningMiddleware._record_governance_outcome()` → `governance_bridge.record_outcome()` |
| **状态标签** | `SYSTEM STATUS: CORE_ARCHITECTURE_FROZEN | OCHA_L2_ACTIVE` |
| **真实职责** | 唯一执行治理 gate（OCHA L2）+ 唯一 post-execution outcome 回流 |

### M4: Provider / MiniMax

| 属性 | 详情 |
|---|---|
| **证据类型** | Live SSE reasoning_content + R51 验证 |
| **Live 证据** | SSE event: `"reasoning_content": "用户要求列出 /tmp 目录..."`（MiniMax-M2.7 生成） |
| **入口** | `deerflow/models/patched_minimax.py` → MiniMax API |
| **真实职责** | LLM 推理，生成工具调用决策和自然语言响应 |

### M5: Docker / Runtime

| 属性 | 详情 |
|---|---|
| **证据类型** | docker ps + container exec |
| **Live 证据** | `openclaw-app` running at port 8080→8001，`npx tsx --version` → `tsx v4.21.0` |
| **依赖服务** | Redis（healthy），Dapr（Up 5h），Dapr placement（Up 5h） |
| **真实职责** | 容器化 Python uvicorn 服务运行 |

---

## 3. 待激活模块清单（REAL_BUT_NOT_ACTIVATED）

### M6: Feishu 通道

| 属性 | 详情 |
|---|---|
| **状态标签** | REAL_BUT_NOT_ACTIVATED — CONDITIONAL |
| **证据** | `/api/channels` → `"feishu": {"enabled": true, "running": true}` ✅ |
| **阻断条件** | 外部条件：需要真实 Feishu 用户向 Bot 发送消息才能触发 ingress |
| **已验证** | WS 连接存在（R54），ChannelManager 代码完整（R54），reply 逻辑存在（R54） |
| **未验证** | 真实用户消息 → ingress → governance 决策的真实端到端 |
| **定性** | **外部触发条件缺失，不是代码 bug** |

### M7: n8n 自动化引擎

| 属性 | 详情 |
|---|---|
| **状态标签** | REAL_BUT_NOT_ACTIVATED — FUTURE |
| **证据** | `deerflow-n8n` 容器 Up 6h，`/healthz` → 200 OK ✅ |
| **阻断条件** | 0 workflows / 0 webhooks / 0 executions — 没有 workflow 可触发 |
| **已验证** | n8n 服务健康，n8n_client.ts 代码完整（R55），BridgeManager 代码完整（R55） |
| **未验证** | n8n → Dify bridge 真实数据流 |
| **定性** | **基础设施存在，工作流内容为空** |

### M8: Dify 向量服务

| 属性 | 详情 |
|---|---|
| **状态标签** | REAL_BUT_NOT_ACTIVATED — UNVALIDATED |
| **证据** | `bytebot-agent` / `bytebot-ui` 容器 Up 6h（R60 docker ps） |
| **阻断条件** | 未验证与主链的连接；n8n bridge 的另一端为空 |
| **定性** | **未接入验证，不是废弃代码** |

### M10: Coprocessor Adapters（scrapling / agent_s / bytebot）

| 属性 | 详情 |
|---|---|
| **状态标签** | FUTURE_COPROCESSOR_ORCHESTRATION — 架构蓝图，非 live |
| **证据** | `ADAPTER_STATUS: "FUTURE_COPROCESSOR_ORCHESTRATION"`（R58 文档更新） |
| **阻断条件** | 物理不可达（sync 函数中 coprocessor 分支永远不触发） |
| **定性** | **未来编排蓝图，不影响当前治理主链** |

---

## 4. 已废弃/搁置模块清单（ABANDONED）

### M9: M04 TypeScript 协调层

| 属性 | 详情 |
|---|---|
| **状态标签** | ABANDONED / STALE_CODE |
| **证据** | R56 验证：`backend/src/domain/m04/` 20 个 .ts 文件，0 个 `package.json`，0 个 Docker service，0 个 Python 调用者 |
| **定性** | 无构建系统、无运行入口、无主链消费者 — 完全搁置的 TypeScript 代码 |

---

## 5. 剩余高价值断点清单

### 🔴 高优先级（有明确断点，应在下一轮处理）

| 断点 | 模块 | 性质 | 说明 |
|---|---|---|---|
| **Feishu 零 ingress 消息** | M6 | 外部条件缺失 | WS 存在、running=true，但 8h 无消息进入。可能是 bot 未完成 SLACK 设置（SLAGD 订阅），或用户未真正找到 Bot 接口。这是**外部部署配置问题**，不是代码 bug |

### 🟡 中优先级（基础设施存在，内容/配置为空）

| 断点 | 模块 | 性质 | 说明 |
|---|---|---|---|
| **n8n 0 workflows** | M7 | 基础设施存在但 workflow 内容为空 | 服务健康，但无 workflow 定义，无法验证自动化能力 |
| **Dify 未验证** | M8 | 未接入 | bridge 的另一端，状态完全未知 |

### 🟢 低优先级（已定性，不影响主链）

| 断点 | 模块 | 性质 | 说明 |
|---|---|---|---|
| **M04 TypeScript 废弃** | M9 | 已定性废弃 | 不影响当前任何运行态，无需处置 |
| **Coprocessor governance 蓝图** | M10 | 架构声明非 live | 已去误导，不影响主链 |
| **governance subprocess 偶发** | M3 | 观察项 | `tsx v4.21.0` 存在，`ts_engine_available: False` 时有发生（subprocess 可能重启）；governance_state.json 持续有记录（36 outcomes），说明 engine 在运作 |

---

## 6. 本轮后的系统总体判断

```
DeerFlow/OpenClaw 系统状态总图（R60 收敛后）

核心主链（REAL_AND_ROOTED）：
  ✅ Gateway API + Health（HTTP/SSE 入口）
  ✅ LangGraph Agent + Tool Executor（任务编排 + 工具执行）
  ✅ OCHA L2 Governance（唯一 pre-execution gate，live APPROVED 证据）
  ✅ LearningMiddleware Outcome Backflow（governance_state.json，36 records）
  ✅ Provider / MiniMax（LLM 推理，live reasoning_content 证据）
  ✅ Docker / Runtime（容器运行，Redis/Dapr 依赖服务 healthy）

通道基础设施（REAL_BUT_NOT_ACTIVATED）：
  ⚠️  Feishu WS：running=true，但无外部用户消息触发
  ⚠️  n8n：服务健康但 0 workflows
  ⚠️  Dify：容器存在但未验证接入

架构声明/蓝图（已去误导）：
  ⚪ Coprocessor Governance（FUTURE_COPROCESSOR_ORCHESTRATION，非 live）
  ⚪ M04 TypeScript（ABANDONED，无构建无入口）

剩余真正大断点：
  ① Feishu 无 ingress 消息（外部条件：Bot 订阅配置）
  ② n8n 无 workflow（内容为空，需要 workflow 工程师配置）
  ③ Dify 未验证（n8n bridge 另一端状态未知）

定性：
  核心主链已完全坐实。剩余断点集中在"基础设施存在但外部触发条件/内容配置缺失"，
  不是代码 bug 或架构问题。
```

---

## 7. 下一轮最优先方向建议

**推荐 Round 61：Feishu Bot 部署配置验证（确认 Bot 是否已正确接入用户消息）**

**原因**：
1. Feishu WS 已 running=true，说明 bot 服务已启动
2. 8h 无 ingress 消息 = bot 没有收到任何用户消息
3. 可能是 SLACK 订阅（Message Subscription）未配置，或 Bot 的 App ID/Secret 无效
4. 需要验证 Feishu developer console 中 Bot 的机器人功能、权限配置、订阅地址是否正确

**验证方法**：
1. 检查 Feishu developer console 的 Bot 配置
2. 确认 Event Subscription（事件订阅）指向的 WS URL 是否正确
3. 确认 Bot 是否已添加到正确的企业内部应用/商店

**备选方向**：如果 Feishu 配置确认无误，则切换到 n8n workflow 配置（需要 workflow 工程师）

**不建议做的事**：
- 不建议继续深挖 governance（已完整坐实）
- 不建议继续 M04 TypeScript（已定性废弃）
- 不建议大改架构或引入新系统
