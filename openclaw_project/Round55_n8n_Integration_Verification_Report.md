# R55 · n8n 集成真实性核验

**目标**：核验 n8n 服务是否真实启动、workflow 是否真实存在、是否与 deerflow/openclaw 主链有真实交互
**方法**：12 Q&A 格式，live 验证服务 + 数据库 + 代码调用链

---

## 1. n8n 服务与代码入口核验结果

### 容器服务状态

| 检查项 | 结果 | 详情 |
|---|---|---|
| n8n 容器 | ✅ 运行中 | `deerflow-n8n Up 6 hours`，端口 `5678:5678` |
| n8n /healthz | ✅ 200 `{"status":"ok"}` | 健康检查正常 |
| n8n API 认证 | ❌ 401 Unauthorized | 需要 `N8N_API_KEY` |
| n8n 根路径 | ✅ 200 text/html | UI 可访问 |

### 代码入口（n8n_client.ts）

| 检查项 | 结果 | 详情 |
|---|---|---|
| `n8n_client.ts` | ✅ 存在 | 208 行，N8NClient 类，完整 REST API 封装 |
| SSRF 防护 | ✅ 有 | `validateWebhookUrl()` 检查内网地址 |
| API Key 处理 | ✅ 安全 | 无硬编码，支持 env fallback，disabled mode |
| `listWorkflows()` | ✅ 有 | `GET /api/v1/workflows` |
| `getWorkflow(id)` | ✅ 有 | `GET /api/v1/workflows/${id}` |
| `createWorkflow()` | ✅ 有 | `POST /api/v1/workflows` |
| `executeWebhook()` | ✅ 有 | 直接 HTTP POST 到 webhook URL |

### 消费者（代码调用链）

| 模块 | 导入方式 | 调用点 | 状态 |
|---|---|---|---|
| `m04/coordinator.ts` | `import { N8NClient }` | 构造 `new N8NClient(...)` | ⚠️ 代码存在但从未在 Python runtime 中被调用 |
| `m04/bridge_manager.ts` | `import { BridgeManager }` | `new BridgeManager(n8nClient, difyClient)` | ⚠️ 同上 |
| `m04/unified_executor.ts` | `import { BridgeManager }` | `new BridgeManager(...)` | ⚠️ 同上 |
| `m04/dify_adapter.ts` | `import { DifyClient }` | Dify 适配器也存在 | ⚠️ 同上 |

**关键发现**：所有 n8n 客户端代码在 TypeScript 层（`backend/src/`），但 OpenClaw 的 runtime 是 Python uvicorn（`backend/app/`）。**没有任何 Python 模块 import 或调用 n8n_client.ts 的功能**。

### M04 TypeScript 层与 Python runtime 的关系

```
Python runtime (app/gateway/app.py):
  - uvicorn FastAPI (port 8001)
  - M03/M07/M08/M11 等 Python 模块
  - ChannelService (Python)

TypeScript 层 (src/):
  - M04 Coordinator + adapters (TypeScript)
  - n8n_client, DifyClient, BridgeManager
  - 被谁调用？→ 目前看起来是独立工具/能力包，不在主 Python 调用链上
```

---

## 2. n8n 数据库状态核验

**直接查询** `n8n_data/database.sqlite`：

| 检查项 | 结果 |
|---|---|
| `workflow_entity` 总数 | **0** |
| `workflow_entity` 活跃 | **0** |
| `webhook_entity` 总数 | **0** |
| `execution_entity` 总数 | **0** |
| `shared_workflow` 总数 | **0** |
| `user_api_keys` | **1 条**（key= `MptDTJIdxP24AoJK`，label=`00`，用户 `90f4d78b`） |

**结论**：n8n 数据库存在且有用户认证（`ygggd123456@gmail.com`），但**没有任何 workflow、webhook 或执行记录**。

---

## 3. workflow/webhook 能力链核验结果

### 当前最接近真实的 n8n 能力链

```
Inbound 链路（当前不存在）：
  Feishu 用户 → ??? → n8n webhook → n8n workflow → ??? → DeerFlow
  ❌ 0 webhooks，❌ 0 workflows，❌ 无触发入口

Outbound 链路（当前不存在）：
  DeerFlow/M04 → n8n_client.executeWebhook() → n8n workflow → ???
  ⚠️ n8n_client 代码存在但无消费者，0 workflows 待触发

BridgeManager 能力（n8n ↔ Dify）：
  ⚠️ 代码存在（field mapping），但无实际 workflow 数据可 bridge
  0 workflows in n8n，0 apps in Dify → bridge 两端都空
```

### 已核验的真实组件

| 组件 | 是否真实存在 | 备注 |
|---|---|---|
| n8n 服务（容器） | ✅ 是 | 健康检查通过 |
| n8n 数据库 | ✅ 是 | 有用户，有 API key |
| n8n_client.ts | ✅ 是 | 完整 REST API 封装 |
| BridgeManager | ✅ 是 | n8n ↔ Dify bridge 代码 |
| DifyClient | ✅ 是 | Dify 适配器存在 |
| M04 Coordinator | ✅ 是 | 调度器，但依赖 n8n_client |
| N8N API Key | ✅ 有 | DB 中存在，container 中 env 未设置 |

### 缺失的关键组件

| 缺失项 | 影响 |
|---|---|
| n8n workflows（0 个） | outbound webhook 触发无目标 |
| n8n webhooks（0 个） | inbound 触发无注册入口 |
| n8n API key 未注入到容器 | 无法通过 API 管理/验证 workflows |
| Dify service（未确认） | bridge 的另一端可能也不存在 |
| Python runtime → TypeScript 桥接 | M04 Coordinator 运行在哪个进程？ |

---

## 4. Live 验证结果

### 服务层验证

```bash
# n8n 健康检查
GET http://localhost:5678/healthz
→ 200 {"status":"ok"} ✅

# n8n workflows API（需认证）
GET http://localhost:5678/api/v1/workflows
→ 401 Unauthorized ❌（无 API key）

# n8n 数据库查询（host 文件系统）
n8n_data/database.sqlite → workflow_entity.COUNT() = 0 ❌
→ webhook_entity.COUNT() = 0 ❌
→ execution_entity.COUNT() = 0 ❌
→ user_api_keys: 1 条（有效）✅
```

### 代码调用链验证

```
gateway/app.py 导入链：
  → 不导入任何 m04 模块
  → 不导入任何 n8n_client
  → ChannelService 是纯 Python 的

app/m11/ → m04 依赖？
  → 不导入 m04（已确认）
```

**结论**：n8n 的 TypeScript 客户端代码（n8n_client、bridge_manager、dify_adapter）存在且结构完整，但：
1. **完全不在 Python runtime 的调用链上**
2. **没有任何 workflow 已创建**（0 workflows，0 webhooks，0 executions）
3. **无法验证任何 workflow 执行能力链**

---

## 5. 本轮后的全局判断

```
n8n 服务状态：部署存在 → 服务健康 ✅
n8n 数据库状态：有用户 + 有 API key ✅
n8n 客户端代码：存在且完整 ✅

n8n 集成落地状态：
  → 服务层：✅ 真实运行
  → 客户端层：⚠️ 代码存在但无消费者（Python 不调用 TypeScript 模块）
  → Workflow 层：❌ 0 workflows，0 webhooks，0 executions
  → Bridge 层：⚠️ 两端都空（n8n 0 workflows，Dify 未验证）

定性：n8n 是"有基础设施、无落地集成"的空壳状态。
  - 服务健康不等于 workflow 可用
  - 客户端代码存在不等于已接入调用链
  - 0 workflows 意味着 outbound webhook 触发无目标
  - 0 webhooks 意味着 inbound 触发无入口
```

---

## 6. 下一轮最优先方向建议

**推荐 Round 56：M04 TypeScript 调度器运行态核验**

**原因**：
1. n8n 的核心问题是 M04 coordinator（TypeScript）未被 Python runtime 调用
2. 需要确认 M04 是独立的 TypeScript 服务（跑在独立进程），还是被错误放置在不可执行的位置
3. 若 M04 是独立服务，需验证其是否能真实运行 coordinator 并调用 n8n_client
4. 若 M04 只是"代码存在但从未运行"，需要确定这是否是架构设计（还是遗漏）

**备选方向**：若 M04 确认是独立 TypeScript 服务，下一轮应验证 M04 → n8n 的真实能力链（创建 workflow → trigger → 执行）。

**不建议继续 n8n deeper**：当前 0 workflows 已说明无论 n8n 服务多健康，没有 workflow 就没有可验证的能力链。优先确认 M04 是否运行，以及 Dify 服务是否存在。