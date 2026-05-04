# OpenClaw · 故障定位 Runbook（最小版）

**版本**：R69
**目的**：Smoke 失败时快速定位断点，不做全量诊断

> **相关文档**：`evolution_seams.md` — 已降级模块的重接路径（降级模块故障不纳入主链排查）

---

## 1. 运行 Smoke

```bash
cd deerflow/backend/src/infrastructure
python3 smoke_host.py   # Windows: python.exe smoke_host.py
```

---

## 2. 失败定位矩阵

| 失败的检查项 | 先看哪里 | 常见原因 | 修复方式 |
|---|---|---|---|
| 检查 1: gateway healthy | `docker ps` + `docker logs` | 容器挂了 | `docker restart infrastructure-openclaw-app-1` |
| 检查 2: service_running | `docker logs --tail 100` | Gateway app 启动中 | 等 30s 再跑 smoke |
| 检查 3/4: feishu enabled/running | `docker logs --tail 50` | Feishu WS 断 | 重启容器，或检查 Event Subscription |
| 检查 5: langgraph server online | `tasklist \| findstr langgraph` | langgraph.exe 没跑 | 手动启动 `langgraph dev --port 2027` |
| 检查 6: lead_agent thread | 检查 5 先通过再说 | LangGraph 未初始化 thread | 先修检查 5 |

---

## 3. 典型断点速查

### 断点 A：Gateway 无响应（检查 1 FAIL）
```bash
# 1. 容器是否在跑
docker ps | grep openclaw

# 2. 容器健康状态
docker inspect infrastructure-openclaw-app-1 --format '{{.State.Health.Status}}'

# 3. 重启
docker restart infrastructure-openclaw-app-1
```

### 断点 B：Feishu channel 不 running（检查 4 FAIL）
```bash
# 看 Feishu WS 日志
docker logs --tail 100 infrastructure-openclaw-app-1 2>&1 | grep -i "lark\|feishu\|ws\|websocket"

# 常见原因：WS 断开后未重连 → 重启容器触发重连
docker restart infrastructure-openclaw-app-1
```

### 断点 C：LangGraph 不可达（检查 5 FAIL）
```bash
# 1. Windows 主机进程检查
tasklist | findstr langgraph

# 2. 本机端口检查
netstat -ano | findstr 2027

# 3. 启动 LangGraph（如未跑）
cd deerflow/backend
.venv\Scripts\langgraph.exe dev --port 2027 --no-browser --allow-blocking --no-reload
```

### 断点 D：LangGraph URL 配置错误（检查 5 FAIL + 检查 6 PASS）
```bash
# 确认 config.yaml 中 langgraph_url 是 host.docker.internal
grep -A2 "channels:" deerflow/config.yaml

# 如是 localhost → 改为 host.docker.internal → 重启容器
```

---

## 4. 已排除的干扰项（降级模块池）

以下模块已降级，Smoke 失败时**不需要检查**，详见 `evolution_seams.md`：
- n8n — INACTIVE_SERVICE（容器在跑，无主链调用）
- Dify — ABANDONED（无激活路径）
- Qdrant — INACTIVE_SERVICE（容器在跑，无向量需求）
- Bytebot — INACTIVE_SERVICE（代码完整，capability shape 已文档化）
- M04 TypeScript — ABANDONED（代码保留，RegistryManager 接口不变）
- Coprocessor Gov — FUTURE_COPROCESSOR_ORCHESTRATION（接口预置，无实例）
- 非飞书 channels — INACTIVE（代码存在，无触发机会）
- perception/ — INACTIVE（代码存在，无音视频触发条件）

---

## 5. 紧急联系信息

| 场景 | 联系人 |
|---|---|
| LangGraph server 问题 | 启动脚本：`deerflow/backend/start_langgraph.bat` |
| Feishu WS 问题 | 检查 Event Subscription + Bot 权限 |
| Gateway 问题 | `docker logs infrastructure-openclaw-app-1` |
