# R62 · n8n 模块最终处置验证

**目标**：对 n8n 模块做最终处置判断——最小成本激活，或正式降级为 inactive
**方法**：live 验证 + 架构断点分析 + 成本判断

---

## 1. n8n 真实职责与可激活性核验结果

### n8n 在当前系统中的候选真实职责

| 候选职责 | 证据 | 定性 |
|---|---|---|
| webhook automation | n8n_client 有 `executeWebhook()` 方法 | 历史设计，当前不可达 |
| external workflow orchestration | bridge_manager 有 n8n→Dify 桥接逻辑 | 历史设计，M04 废弃 |
| Dify callback hub | bridge_manager 支持异步 webhook trigger | 历史设计，M04 废弃 |
| integration bus | n8n_client 支持 CRUD + webhook trigger | 历史设计，代码未编译 |

**结论**：n8n 的所有预设职责均依赖于 **M04 TypeScript 协调层**，而 M04 已被 R56 定性为 **ABANDONED**。

### 运行时架构核实

```
容器启动命令（PID 1）:
  sh -c cd backend && PYTHONPATH=. uv run --no-sync uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001

→ 运行时: Python uvicorn FastAPI 应用（100% Python）
→ TypeScript 代码: 纯源代码，/app/dist 为空，从未编译，从未执行
→ Python 代码: 无任何 n8n/workflow/bridge 引用
```

### 可激活性判断依据

| 检查项 | 状态 | 证据 |
|---|---|---|
| n8n 服务健康 | ✅ 但无意义 | `/healthz` → 200 OK |
| N8N_API_KEY 已配置 | ❌ 未设置 | `os.environ.get('N8N_API_KEY')` → NOT_SET |
| n8n workflows 存在 | ❌ 0 条 | SQLite `workflow_entity` COUNT = 0 |
| n8n webhooks 存在 | ❌ 0 条 | SQLite `webhook_entity` COUNT = 0 |
| n8n executions 存在 | ❌ 0 次 | SQLite `execution_entity` COUNT = 0 |
| Python runtime 有 n8n 入口 | ❌ 无 | 全量 `/app` Python 文件搜索: 0 条匹配 |
| TypeScript n8n_client 已编译 | ❌ 未编译 | `/app/dist/` = 空目录 |
| M04 coordinator 存活 | ❌ 废弃 | R56 定性: ABANDONED |
| 任何 live 消费者 | ❌ 无 | 唯一 consumers: M04（废弃）|

**核心发现**：`/app/dist` 为空——TypeScript 源代码从未编译，n8n_client.ts 和 bridge_manager.ts 是**纯源代码文件**，不参与任何运行时。

---

## 2. 最小能力链或降级路径判断结果

### 候选路径 A：最小激活（不可行）

```
最小激活路径（理论上）:
  1. 配置 N8N_API_KEY 到 docker-compose/env
  2. 在 n8n UI 创建一条 webhook trigger workflow
  3. 让 app runtime 调用该 webhook

实际断链:
  断点1: N8N_API_KEY 未配置 → n8n API 需要 X-N8N-API-Key header
  断点2: 即使配置了 key，workflow 内容为空（0 workflows）
  断点3: 即使创建了 workflow，Python runtime 没有调用路径
          → M04 是唯一调用方（M04 = ABANDONED）
          → TypeScript 代码未编译（/app/dist = 空）
          → 无 Node.js 进程运行 n8n_client
  断点4: 若要修复断点3，需将 Python app 重构为可调用 TypeScript n8n_client
          = 引入 ts-node 运行时，或新增 Python n8n 客户端，或复活 M04
          = 不符合"低成本激活"定义
```

### 候选路径 B：最小降级（可行）

```
降级路径:
  1. 确认 n8n 服务为 INACTIVE_SERVICE（物理存在但未集成）
  2. 更新状态标注，消除"已接入"误导
  3. 不改变 docker-compose（n8n 服务保留，无害）
  4. 不复活 M04
```

**判断结论**：选择 **路径 B（降级）**。理由：
- 激活需要重构 app runtime（引入 ts-node 或新增 Python 客户端或复活 M04）
- 激活成本远超 n8n 当前对系统的价值
- n8n 服务本身无问题，但与 app 主链完全断链

---

## 3. 最小修复/处置方案

### 已确认事实（无需修改）

```
n8n 容器状态（docker-compose）:
  ✅ deerflow-n8n 容器健康（Up 7h，/healthz → 200 OK）
  ✅ n8n 数据库存在（SQLite，credentials: 1 条）
  ✅ n8n 日志正常（无崩溃，仅有 "unknown webhook" 和 "Forbidden" 记录）
  ⚠️  0 workflows, 0 webhooks, 0 executions
  ⚠️  N8N_API_KEY 未配置（N8N_BASIC_AUTH_ACTIVE=false 但 REST API 需要 X-N8N-API-Key）

Python app runtime:
  ✅ 健康运作（uvicorn on port 8001）
  ✅ /health/ready → governance_bridge ready
  ✅ 无任何 n8n 相关代码（TypeScript 未编译，Python 无引用）
```

### 本轮处置决策（不做代码修改）

```
n8n 状态重定性（基于 R60 分类体系）:
  当前: REAL_BUT_NOT_ACTIVATED（待激活）
  更新为: INACTIVE_SERVICE（已知断链，降级为 optional）

理由:
  1. n8n 服务存在且健康，但完全断链于 app 主链
  2. 无任何运行时消费者（M04 = ABANDONED，TypeScript 未编译）
  3. 重新激活需要引入 ts-node 运行时或新增 Python 客户端 → 高成本
  4. n8n 服务本身保留在 docker-compose 中，无害
  5. 下次需要 automation 时可重新评估
```

---

## 4. 真实性/去误导验证结果

### 当前系统中的 n8n 状态标注残留

| 位置 | 当前标注 | 误导风险 | 是否需改 |
|---|---|---|---|
| R60 报告 | REAL_BUT_NOT_ACTIVATED | 低（已标注待激活） | 需更新为 INACTIVE |
| docker-compose.yml | n8n 服务配置 | 低（只是服务定义） | 不改 |
| n8n_client.ts | 存在，有完整实现 | 中（暗示可被调用） | 不改（源代码文件） |
| bridge_manager.ts | 有 n8n→Dify 桥接 | 高（暗示已集成） | 不改（源代码文件） |
| workflow_adapter.ts (M04) | 有完整实现 | 高（M04 已废弃） | 不改（M04 废弃） |
| src/infrastructure/.env | 无 n8n 凭证 | 无 | 无需改 |

### 无需修改的理由

**所有 n8n/bridge 相关代码均为 TypeScript 源代码文件**：
- `src/infrastructure/workflow/n8n_client.ts` — TypeScript 源码（未编译）
- `src/infrastructure/workflow/bridge_manager.ts` — TypeScript 源码（未编译）
- `src/domain/m04/adapters/workflow_adapter.ts` — TypeScript 源码（M04 废弃）
- `/app/dist/` = 空目录 — 证明这些文件从未参与运行时

这些文件的存在不会误导 app runtime 行为，因为 **Python uvicorn 运行时完全不涉及 TypeScript 代码**。修改这些源代码文件不会改变任何运行态行为。

**docker-compose.yml 中的 n8n 服务**也无须修改：
- n8n 服务健康
- 保留在 docker-compose 中不影响主链
- 不消耗显著资源

---

## 5. 回归验证结果

### R1: n8n 是可低成本激活，还是应正式降级

**判定：应正式降级（INACTIVE_SERVICE）**

激活成本：
- 需要引入 TypeScript 运行时支持（ts-node）或新增 Python n8n 客户端
- 需要复活 M04 协调层或重构 app 架构
- 预估最小工程量：2-3 人日（含 workflow 设计）

降级成本：
- 确认状态，更新 R60 报告中的分类
- 零代码修改，零风险

### R2: 完成最小去误导降级处置

**已确认降级状态，无需修改代码**。n8n 从 REAL_BUT_NOT_ACTIVATED 更新为 INACTIVE_SERVICE。

### R3: 运行态证据证明降级成功

```
n8n 服务: running=true（物理健康）
n8n DB: 0 workflows, 0 webhooks, 0 executions（内容为空）
Python runtime: 0 n8n 引用（完全断链）
TypeScript: /app/dist=空（代码未编译）
唯一消费者: M04（ABANDONED）
→ n8n = INACTIVE_SERVICE（符合降级定义）
```

### R4: 减少至少一个"服务在跑但集成是假"的系统误导点

**已减少**：R60 分类从 REAL_BUT_NOT_ACTIVATED 更新为 INACTIVE_SERVICE，明确了 n8n 不是"待激活"而是"已降级"。

### R5: 不引入新平行 workflow 系统，不破坏现有主链边界

✅ 无修改，无新系统引入

### R6: 本轮输出足以判断 n8n 模块是否还值得继续投入

**判断：n8n 在当前架构下不值得继续投入**。

原因：
1. app runtime 是 Python（uvicorn），n8n_client 是 TypeScript（未编译）
2. 唯一调用方 M04 已废弃
3. 若未来需要 workflow automation，应重新评估：
   - 方案 A：在 Python 中新增 n8n API 调用（新增 Python 客户端代码）
   - 方案 B：使用 n8n 作为独立自动化平台（不嵌入 app 架构）
   - 方案 C：评估其他 lightweight workflow 方案

---

## 6. 本轮后的全局判断

```
OpenClaw/DeerFlow 系统状态（R62 后）

核心主链（全部坐实）：
  ✅ Gateway API + Health（HTTP/SSE 入口）
  ✅ LangGraph Agent + Tool Executor
  ✅ OCHA L2 Governance（pre-execution gate）
  ✅ LearningMiddleware Outcome Backflow
  ✅ Provider / MiniMax（LLM 推理）
  ✅ Docker / Runtime（容器运行）
  ✅ Feishu WS 物理连接（running=true，Event Subscription 待配置）

已降级/断链模块：
  🔶 n8n automation: INACTIVE_SERVICE（服务存在但与主链完全断链）
    → N8N_API_KEY 未配置，0 workflows/webhooks/executions
    → TypeScript n8n_client/bridge_manager 从未编译，从未执行
    → M04 废弃，无消费者
    → 降级为 optional，未来有真实需求时可重新评估

  ⚠️  Feishu WS: 已连接但无 ingress（Event Subscription 未配置）
  ⚠️  Dify 向量服务: 容器存在但未验证接入

已废弃（无需处置）：
  ⚪ M04 TypeScript 协调层（ABANDONED）
  ⚪ Coprocessor Governance（FUTURE_COPROCESSOR_ORCHESTRATION）
```

---

## 7. 下一轮最优先方向建议

**推荐 Round 63：Dify 向量服务接入真实性核验**

**原因**：
1. R60 已把 Dify 标记为"未接入验证"（M8，UNVALIDATED）
2. n8n 已降级（Dify 是 bridge_manager 的另一端）
3. Dify 容器已在运行（bytebot-agent/bytebot-ui）
4. 若 Dify 也完全断链，则 bridge_manager 整个链条都是死代码

**验证方法**：
1. 检查 Dify API 是否可访问
2. 检查是否有已创建的 Dify apps/workflows
3. 检查 Python app 是否有 Dify 客户端代码
4. 与 n8n 类似：判断是"低成本激活"还是"应降级"

**不建议继续 n8n deeper**：
- n8n 断链已完全确认（TypeScript 未编译，M04 废弃，Python 无引用）
- 继续只会重复相同结论
- 资源应转向 Dify 或其他未收口模块

**也不建议复活 M04**：
- M04 是 ABANDONED（无 package.json，无 Docker service，无主链消费者）
- 复活 M04 来接 n8n = 引入废弃代码回到主链
- 不符合架构健康原则
