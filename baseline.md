> **维护模式声明**：R69 起系统从"排查模式"正式切换到"维护模式"。核心主链已闭环，所有降级模块已开放式收口（见 `evolution_seams.md`）。后续工作仅限：CI 固化 / 必要文档更新 / 已验证模块的被动维护。

---

**版本**：R69
**日期**：2026-04-21
**性质**：最小可交接系统基线 — 仅记录当前已验证的事实，不做推测

> **相关文档**：`evolution_seams.md` — 已降级模块的重接路径与接口契约

---

## 1. 核心 Smoke 集（统一入口）

统一入口：`deerflow/backend/src/infrastructure/smoke_host.py`

```bash
python3 smoke_host.py   # Windows: python.exe smoke_host.py
```

**当前通过标准**：6/6 checks PASS

| # | 检查项 | 端点 | 成功判据 |
|---|---|---|---|
| 1 | Gateway 进程存活 | `GET /health` | status=healthy |
| 2 | service_running | `GET /api/channels/` | service_running=true |
| 3 | Feishu enabled | `GET /api/channels/` | feishu.enabled=true |
| 4 | Feishu running | `GET /api/channels/` | feishu.running=true |
| 5 | LangGraph server 在线 | `GET /` | ok=true |
| 6 | lead_agent thread 可查 | `POST /threads/search` | 返回非空列表，含 graph_id=lead_agent |

**Smoke 失败时直接指向**：
- 检查 1/2/3/4 失败 → Gateway 侧问题（容器进程或 channel 配置）
- 检查 5/6 失败 → LangGraph 侧问题（langgraph.exe 进程或 URL 配置）

---

## 2. 当前系统总体定性

```
OpenClaw/DeerFlow 系统状态（R69 后）

✅ 核心主链（已闭环验证）：
  Gateway /health ✅ / LangGraph API ✅ / lead_agent graph ✅
  MiniMax-M2.7 ✅ / Docker Runtime ✅ / Feishu 通道五段链路 ✅

✅ Feishu 通道（FULL_CHANNEL_CLOSED，R66B 验证）：
  WS 连接 ✅ / Event Subscription ✅ / Bot 权限 ✅
  _on_message ✅ / M10 classification ✅ / LangGraph run ✅
  MiniMax reply ✅ / Feishu reply API ✅

✅ 已知 limitation（不影响核心功能）：
  - app_id/app_secret 在 .env 不在容器环境变量（lark-oapi 从 .env 读）
  - 日志级别 WARNING，INFO 细节不可见
  - LangGraph server 运行在 Windows 主机（不在容器内）

🔶 已降级模块（不纳入 Smoke，不修复；详见 evolution_seams.md）：
  n8n: INACTIVE_SERVICE — 容器在跑，无主链调用，演进接口已保留
  Dify: ABANDONED — 无激活路径，REST API 重接标准
  Qdrant: INACTIVE_SERVICE — 容器在跑，无向量需求，REST+gRPC 重接
  Bytebot: INACTIVE_SERVICE — 代码完整，capability shape 文档最佳实践
  M04 TypeScript: ABANDONED — 代码保留，RegistryManager 接口不变
  Coprocessor Gov: FUTURE_COPROCESSOR_ORCHESTRATION — 接口预置，无实例

🔶 非飞书 channels（INACTIVE — 未接入）：
  discord / telegram / wechat / wecom / slack — 代码存在，无触发机会
```

---

## 3. 网络拓扑（关键）

```
Windows 主机侧：
  localhost:2027  → langgraph.exe（PID 15256/15544）
  localhost:8001  → Docker port mapping（openclaw-app 容器）

Docker 容器内：
  host.docker.internal:2027 → Windows 主机 langgraph.exe（正确路径）
  容器内 localhost:2027 → 无服务（错误，已废弃）

配置文件（生效优先级最高）：
  config.yaml（bind-mounted）→ channels.langgraph_url: http://host.docker.internal:2027
  .env（named volume）→ DEER_FLOW_CHANNELS_LANGGRAPH_URL（不直接生效）
```

---

## 4. 关键文件路径

| 文件 | 作用 |
|---|---|
| `deerflow/config.yaml` | 主配置，bind 到容器 `/app/config.yaml` |
| `deerflow/backend/src/infrastructure/smoke_host.py` | 统一 smoke 入口 |
| `deerflow/backend/src/infrastructure/e2e_regression_host.py` | 旧 E2E 回归脚本（端口需更新为 8001） |

---

## 5. 运行与维护

```bash
# 运行 smoke（从 deerflow/backend/src/infrastructure/ 目录）
python3 smoke_host.py   # 或 python.exe smoke_host.py（Windows）

# 重启 openclaw-app 容器（配置修改后）
docker restart infrastructure-openclaw-app-1

# 查看 Feishu WS 连接状态
docker logs --tail 50 infrastructure-openclaw-app-1 2>&1 | grep -i lark

# 查看 LangGraph 进程
tasklist | findstr langgraph
```
