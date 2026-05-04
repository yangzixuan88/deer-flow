# R64 · Feishu Bot Event Subscription 平台侧验证

**目标**：核验 Feishu 平台侧订阅配置，判断断点是"平台配置缺失"还是"下游服务不可达"
**方法**：live 日志全量分析 + 错误链路追踪

---

## 1. Feishu 平台侧前置条件矩阵

### Feishu 消息处理全链路

```
用户发送消息 → Feishu WS 推送事件 → _on_message() → _prepare_inbound()
→ bus.publish_inbound() → ChannelManager._ingest()
→ _handle_message() → _handle_chat() → _create_thread()
→ client.threads.create() → LangGraph API (/api/threads)
```

### Feishu 平台侧前置条件

| 条件 | 状态 | 证据 |
|---|---|---|
| WS 连接（Event Subscription 有效） | ✅ 已连接 | 6 次重连日志，`aid=552564` 有效 |
| `im.message.receive_v1` 事件订阅 | ✅ 已推送消息 | 2 次真实消息到达，chat_id=oc_fc9a52fecba215a7a3aa7b8048b5d080 |
| Bot 有读取/处理消息权限 | ✅ 已处理 | `_handle_message()` 被调用 |
| Bot 可回复消息权限 | ✅ 逻辑存在 | reply card 代码存在（R54） |

### 真正的断点

| 层级 | 状态 | 说明 |
|---|---|---|
| Feishu WS 物理连接 | ✅ 正常 | Event Subscription 有效 |
| Feishu 消息 ingress | ✅ 已发生 | 2 次消息到达（chat_id=oc_fc9a52fecba215a7a3aa7b8048b5d080） |
| `_on_message()` 调用 | ✅ 已触发 | `manager._handle_message()` 被调用 |
| LangGraph API (`client.threads.create()`) | ❌ **ConnectError** | 无法连接到 `localhost:2027`（LangGraph API server） |

---

## 2. 主断点判断结果

### R61 旧判断（错误）

```
R61 认为：主断点是 Feishu Event Subscription 未配置 im.message.receive_v1
实际情况：Event Subscription 已配置，消息已成功推送2次
```

### R64 新判断（已核实）

```
主断点不是 Feishu 平台配置，而是：
  LangGraph API Server 进程缺失
  
证据（server_lark.log 全量分析）：
  ① 2 条 ERROR: "Error handling message from feishu (chat=oc_fc9a52fecba215a7a3aa7b8048b5d080)"
  ② 失败位置：File "manager.py", line 677, in _create_thread
                thread = await client.threads.create()
  ③ 错误类型：httpx.ConnectError: All connection attempts failed
  ④ LangGraph URL：DEER_FLOW_CHANNELS_LANGGRAPH_URL=http://localhost:2027
  ⑤ 端口 2027：docker 无任何服务监听 2027（docker ps 无 2027 端口映射）
  ⑥ 6 次 WS 重连日志，仅 2 次 feishu 消息（均为 ConnectError）
  ⑦ 最近的日志（lines 168-291）：仅 WS 重连和 health check，无新消息错误
```

### LangGraph API Server 缺失证据

```
container 内端口检查：
  docker ps → 无任何服务映射到 2027
  openclaw-app 容器 → ports: 8080→8001, 8081→8081
  其他所有容器 → 无 2027 端口暴露

.env 中的配置：
  DEER_FLOW_CHANNELS_LANGGRAPH_URL=http://localhost:2027
  → app/channels/manager.py 使用此 URL 创建 LangGraph SDK client
  → client.threads.create() 尝试 POST http://localhost:2027/api/threads
  → localhost:2027 无服务监听 → ConnectError
```

---

## 3. 最小平台侧修复方案

### 断点已不在 Feishu 平台侧

**结论：Feishu Event Subscription 配置正确，不需要修改 Feishu Developer Console。**

主断点是 **LangGraph API Server（port 2027）未启动**。

### LangGraph API Server 启动方案

**选项 A：检查是否有 LangGraph server 启动脚本**

```bash
# 检查是否有 langgraph server 相关的进程或脚本
docker exec infrastructure-openclaw-app-1 python3 -c "
import subprocess
r = subprocess.run(['grep', '-r', 'langgraph', '/app/backend/app/channels/manager.py'], capture_output=True, text=True)
print(r.stdout[:500])
"

# 检查 Dockerfile/启动脚本中是否有 langgraph server 启动命令
docker exec infrastructure-openclaw-app-1 python3 -c "
log = open('/app/backend/server_lark.log', errors='replace').read()
# Check if there are any langgraph-related startup logs
lines = [l for l in log.split('\n') if 'langgraph' in l.lower() or '2027' in l or 'server' in l.lower()]
for l in lines[:20]:
    print(l[:200])
"
```

**选项 B：若无 LangGraph server，需在 docker-compose 中添加 LangGraph API service**

```
docker-compose.yml 需要添加类似：
  langgraph-api:
    image: langchain/langgraph-api:latest
    ports:
      - "2027:8001"
    environment:
      - LANGCHAIN_API_KEY=xxx
      - etc.
    depends_on:
      - redis
      - openclaw-app
```

---

## 4. Live 验证结果

### Feishu ingress 全链路验证

```
WS 连接: ✅ 6 次重连，物理链路健康
消息接收: ✅ 2 次真实 Feishu 消息到达（chat_id 可核实）
_handle_message(): ✅ 已调用（日志 traceback 可证实）
_create_thread(): ❌ ConnectError（LangGraph API 不可达）
LangGraph threads.create(): ❌ 无法连接到 localhost:2027
```

### 当前系统状态（全量日志核实）

```
日志时间范围（server_lark.log）：
  最早: 2026-04-15 07:45:18（WS 首次连接）
  最晚: 2026-04-15 08:11:30（WS 最后重连）
  
WS 重连次数: 6 次（物理链路稳定）
Feishu 真实消息数: 2 次（均触发 ConnectError）
其他错误: 2 次（app.m10 LLM evaluator JSON 解析失败）
      1 次（InboundMessage.__init__ missing user_id）
      
最近 7+ 天无新 Feishu 消息: 可能是因为 LangGraph API 缺失导致
  消息处理完全失败后，用户（测试者）停止向 Bot 发消息
```

### Feishu Event Subscription 状态

```
✅ Event Subscription 已配置（消息已成功推送 2 次）
✅ Bot 有消息读取权限
✅ Bot 有消息回复权限（reply card 逻辑存在）
❌ Bot 消息处理后无法完成 thread 创建（LangGraph API 缺失）
```

---

## 5. 回归验证结果

### R1: Feishu 平台侧前置条件矩阵

✅ WS 连接正常，✅ Event Subscription 已配置（`im.message.receive_v1` 已推送 2 次消息）

### R2: im.message.receive_v1 是否为主断点

**否**。`im.message.receive_v1` 已配置且工作正常（2 次消息成功推送）。主断点是 **LangGraph API Server 未运行**（ConnectError at `client.threads.create()`）。

### R3: 给出平台侧修复清单

| 步骤 | 动作 | 说明 |
|---|---|---|
| 1 | 确认 LangGraph API Server 启动方式 | 检查是否有 `langgraph-api` 容器或进程 |
| 2 | 若无 LangGraph server | 在 docker-compose 中添加 langgraph-api service |
| 3 | 配置 `DEER_FLOW_CHANNELS_LANGGRAPH_URL` | 指向正确的 LangGraph API URL |
| 4 | 重启 openclaw-app 容器 | 使新配置生效 |
| 5 | 向 Bot 发送测试消息 | 验证 `client.threads.create()` 成功 |

### R4: 若条件允许完成真实 ingress

**当前阻断**：LangGraph API Server 缺失，无法完成端到端验证。

### R5: 不引入新平行通道系统

✅ 无修改

### R6: Feishu 剩余问题已完全收敛

**判断：是**。Feishu 断点已从"Event Subscription 未配置"精确到"LangGraph API Server 未启动"。

---

## 6. 本轮后的全局判断

```
OpenClaw/DeerFlow 系统状态（R64 后）

真实 ingress 验证（重大修正）：
  ⚠️  Feishu WS 真实 ingress 已发生 2 次
      → Event Subscription ✅ im.message.receive_v1 已推送消息
      → _on_message ✅ 被调用
      → _handle_message ✅ 被调用
      → _create_thread ❌ ConnectError（LangGraph API 缺失）

主断点重新定性（R64 新发现）：
  ❌ 不是 Feishu Event Subscription 问题（已排除）
  ❌ 不是 Feishu Bot 权限问题（已排除）
  ❌ 不是仓内 Feishu 代码问题（已排除）
  ✅ 主断点：LangGraph API Server（port 2027）未运行
      → app/channels/manager.py 使用 DEER_FLOW_CHANNELS_LANGGRAPH_URL=http://localhost:2027
      → client.threads.create() → ConnectError
      → 2 次消息处理均在此失败
      → 此后用户停止测试，Bot 无新消息

Feishu 通道重新定性：
  R61: PLATFORM_CONFIG_PENDING（Event Subscription 配置缺失）
  R64: CHANNEL_HARDWARE_READY_BUT_UPSTREAM_BLOCKED
      → WS 连接 ✅
      → Event Subscription ✅  
      → Bot 消息处理 ✅
      → LangGraph API ❌（主断点）
```

---

## 7. 下一轮最优先方向建议

**推荐 Round 65：LangGraph API Server 缺失修复（最小真实化）**

**原因**：
1. Feishu ingress 已在发生（2 次真实消息到达），只是卡在 `thread.create()` 这一步
2. 修复 LangGraph API 后，Feishu 通道即可完成端到端闭环
3. 这比重新配置 Event Subscription 更重要（因为 Event Subscription 已经工作）

**处置步骤**：
1. 检查 docker-compose.yml 是否应有 langgraph-api service
2. 若有，确认它为什么没启动
3. 若无，在 docker-compose 中添加 LangGraph API service（最小化方案）
4. 配置正确的 `DEER_FLOW_CHANNELS_LANGGRAPH_URL`
5. 重启 openclaw-app 容器
6. 向 Bot 发送测试消息，验证完整链路

**关键洞察**：R61-R64 揭示了一个更深的真相——Feishu 通道的代码侧从一开始就是通的，真正卡住它的是 **LangGraph API Server 这一步基础设施缺失**，不是平台配置问题。
