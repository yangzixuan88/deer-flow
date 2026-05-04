# 容灾恢复演练剧本 (Disaster Recovery Playbook)

**版本**: v1.0
**日期**: 2026-04-15
**维护人**: Accio Agent

---

## 1. 架构概览与依赖

### 1.1 核心组件

| 组件 | 技术栈 | 端口 | 容灾级别 |
|------|--------|------|----------|
| OpenClaw 核心 | TypeScript/Node | 3000 | 应用层 |
| DeerFlow 编排引擎 | Python/FastAPI | 8001 | 外部依赖 |
| Dapr 运行时 | Dapr | 3500/50001 | 状态持久化 |
| MCP Server | Python/FastAPI | 8080 | 工具接口 |
| n8n 工作流 | Node.js | 5678 | 自动化编排 |
| Qdrant 向量数据库 | Rust | 6333 | 记忆存储 |
| Redis | - | 6379 | 缓存/会话 |

### 1.2 数据流

```
用户请求 → MCP Server (8080) → OpenClaw (3000)
                                      ↓
                              Dapr State (3500)
                                      ↓
                              DeerFlow (8001) → 执行层
                                      ↓
                              n8n (5678) → 工作流自动化
```

---

## 2. 风险矩阵

| 风险场景 | 影响等级 | 发生概率 | 恢复时间目标 (RTO) | 数据恢复目标 (RPO) |
|----------|----------|----------|-------------------|-------------------|
| DeerFlow 服务宕机 | 🔴 高 | 中 | 5 分钟 | N/A |
| Dapr 状态存储不可用 | 🔴 高 | 低 | 10 分钟 | 1 分钟 |
| MCP Server 无响应 | 🟡 中 | 中 | 3 分钟 | N/A |
| Qdrant 向量库崩溃 | 🟡 中 | 低 | 15 分钟 | 5 分钟 |
| Redis 会话丢失 | 🟡 中 | 中 | 2 分钟 | 1 分钟 |
| n8n 工作流中断 | 🟢 低 | 低 | 10 分钟 | N/A |

---

## 3. 恢复场景与步骤

### 场景 A：DeerFlow 服务宕机

**症状**：编排请求超时，日志显示 `Connection refused` 或 `DeerFlow unavailable`

**自动恢复**：
- M01 `deerflowEnabled=true` 时，Orchestrator 会自动降级到本地 Coordinator 执行
- 无需人工干预

**手动恢复**：
```bash
# 1. 检查 DeerFlow 进程
ps aux | grep deerflow

# 2. 重启 DeerFlow
cd e:/OpenClaw-Base/deerflow
./start_deerflow.bat

# 3. 验证健康状态
curl http://localhost:8001/health
```

---

### 场景 B：Dapr 状态存储不可用

**症状**：日志显示 `State store error`，任务状态卡在 `PROCESSING`

**恢复步骤**：
```bash
# 1. 检查 Dapr 运行时
dapr list

# 2. 重启 Dapr 边车
dapr stop openclaw-app
dapr run --app-id openclaw-app --dapr-http-port 3500 --dapr-grpc-port 50001

# 3. 验证状态存储
curl http://localhost:3500/v1.0/state/statestore
```

**状态恢复**：
- Dapr 的 state store 具有持久化能力
- 重启后自动恢复未完成的任务状态
- 任务执行器应实现幂等检查点（Checkpoint）

---

### 场景 C：MCP Server 无响应

**症状**：工具调用返回 503，WebSocket 断开

**恢复步骤**：
```bash
# 1. 检查 MCP Server 进程
curl http://localhost:8080/health

# 2. 重启 MCP Server
pkill -f mcp_server.py
python src/infrastructure/server/mcp_server.py &

# 3. 验证工具列表
curl http://localhost:8080/tools
```

---

### 场景 D：Qdrant 向量库崩溃

**症状**：`Knowledge Graph` 查询返回空，记忆检索失效

**恢复步骤**：
```bash
# 1. 检查 Qdrant 容器
docker ps | grep qdrant

# 2. 重启 Qdrant 容器
docker restart qdrant

# 3. 等待服务恢复
sleep 10
curl http://localhost:6333/collections

# 4. 验证数据完整性
# 检查集合是否完整，必要时从备份恢复
```

---

### 场景 E：Redis 会话丢失

**症状**：用户会话中断，`Session memory` 返回空

**恢复步骤**：
```bash
# 1. 检查 Redis 状态
redis-cli ping

# 2. 如果 Redis 崩溃，重启
# Windows: net start Redis
# Linux: systemctl restart redis

# 3. 验证连接
redis-cli info clients
```

**会话恢复策略**：
- 短期会话 → 重新开始（影响最小）
- 关键会话 → 从 `persistent_memory` 恢复上下文

---

### 场景 F：系统级故障（全部组件宕机）

**恢复步骤**：

```bash
# Phase 1: 基础设施恢复 (0-5 分钟)
# ============================================

# 1.1 启动 Redis
net start Redis  # Windows
# systemctl start redis  # Linux

# 1.2 启动 Qdrant
docker start qdrant

# 1.3 启动 Dapr 运行时
dapr run --app-id openclaw-app --dapr-http-port 3500 --dapr-grpc-port 50001 &

# Phase 2: 核心服务恢复 (5-10 分钟)
# ============================================

# 2.1 启动 MCP Server
cd e:/OpenClaw-Base/openclaw超级工程项目
python src/infrastructure/server/mcp_server.py &

# 2.2 启动 OpenClaw 应用
npm run dev &
# 或: node dist/server.js

# 2.3 启动 DeerFlow
cd e:/OpenClaw-Base/deerflow
./start_deerflow.bat

# Phase 3: 自动化层恢复 (10-15 分钟)
# ============================================

# 3.1 启动 n8n
docker start n8n
# 或: n8n start

# 3.2 验证 Watchdog 心跳
python src/infrastructure/watchdog.py --health

# 3.3 检查夜间任务调度
crontab -l | grep nightly
```

---

## 4. 检查清单 (Recovery Checklist)

### 4.1 启动前检查

- [ ] 所有依赖服务端口未被占用
- [ ] 磁盘空间充足（> 20%）
- [ ] 网络连接正常
- [ ] 配置文件完整（.env, config.yaml）

### 4.2 服务健康检查

| 服务 | 检查命令 | 健康指标 |
|------|----------|----------|
| OpenClaw | `curl localhost:3000/health` | `200 OK` |
| DeerFlow | `curl localhost:8001/health` | `200 OK` |
| Dapr | `dapr list` | APP ID 显示 |
| MCP Server | `curl localhost:8080/health` | `200 OK` |
| Qdrant | `curl localhost:6333/collections` | 返回集合列表 |
| Redis | `redis-cli ping` | `PONG` |
| n8n | `curl localhost:5678/healthz` | `200 OK` |

### 4.3 功能验证

- [ ] 用户可发起新任务
- [ ] 意图分类正常（直答/追问/编排）
- [ ] DAG 执行正常
- [ ] 记忆写入/读取正常
- [ ] 飞书 Webhook 回调正常

---

## 5. 备份策略

### 5.1 关键数据

| 数据类型 | 备份频率 | 存储位置 | 恢复方式 |
|----------|----------|----------|----------|
| Dapr State | 实时复制 | SQLite 文件 | 自动恢复 |
| Qdrant Collection | 每小时 | `qdrant_storage/` | `docker cp` 恢复 |
| Redis Dump | 每小时 | `dump.rdb` | `redis-cli restore` |
| 资产文件 | 每日 | `assets/` | `git archive` |
| 用户配置 | 变更时 | `.env` | 版本控制 |

### 5.2 备份命令

```bash
# Qdrant 备份
docker cp qdrant:/qdrant/storage ./backups/qdrant-$(date +%Y%m%d)

# Redis 备份
redis-cli SAVE
docker cp redis:/data/dump.rdb ./backups/redis-$(date +%Y%m%d).rdb

# 资产文件备份
git archive HEAD:assets > backups/assets-$(date +%Y%m%d).tar
```

---

## 6. 联系人与依赖

| 服务 | 负责人 | 联系方式 |
|------|--------|----------|
| OpenClaw 核心 | Accio Agent | 内置 |
| DeerFlow | DeerFlow Team | GitHub Issues |
| Dapr | Dapr Community | dapr.io |
| 飞书集成 | 飞书开放平台 | open.feishu.cn |

---

## 7. 演练计划

### 7.1 季度演练（每 90 天）

1. **场景 A 演练**：模拟 DeerFlow 宕机，验证自动降级
2. **场景 E 演练**：模拟 Redis 崩溃，验证会话恢复
3. **场景 F 演练**：全系统重启，验证 15 分钟 RTO

### 7.2 演练记录

| 日期 | 演练场景 | 耗时 | 结果 | 改进项 |
|------|----------|------|------|--------|
| 2026-04-15 | 剧本初始创建 | - | - | 待首次演练 |
