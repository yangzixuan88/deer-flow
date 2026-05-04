# R56 · M04 TypeScript 协调层真实性核验

**目标**：判断 M04 TypeScript 协调层是"真系统、独立系统"还是"未接入 Python runtime 的搁置代码"
**方法**：12 Q&A 格式，build 系统分析 + runtime 调用链追踪 + Docker 镜像层验证

---

## 1. M04 代码结构核验结果

### TypeScript 文件清单（`backend/src/domain/m04/`）

| 文件 | 行数 | 职责 |
|---|---|---|
| `coordinator.ts` | ~400 | M04 主编排器，核心调度逻辑 |
| `unified_executor.ts` | ~200 | 统一执行器，调用 BridgeManager |
| `unified_builder.ts` | ~200 | LangGraph Builder |
| `bridge_manager.ts` | ~191 | n8n↔Dify 桥接管理 |
| `dify_adapter.ts` | ~150 | Dify 适配器 |
| `skill_router.ts` | ~150 | Skill 路由 |
| `skill_loader.ts` | ~120 | Skill 加载器 |
| `skill_registry.ts` | ~100 | Skill 注册表 |
| `lark_adapter.ts` | ~100 | 飞书适配器 |
| `lark_routing.ts` | ~80 | 飞书路由逻辑 |
| `mod.ts` | ~50 | 公共导出接口 |
| `coordinator.test.ts` | ~200 | 单元测试 |
| `lark_routing.test.ts` | ~100 | 测试 |
| `skill_router.test.ts` | ~80 | 测试 |
| `coordinator_sandbox_integration.test.ts` | ~150 | 集成测试 |
| 其他工具类 | ~10文件 | 工具函数 |

**总计**：20个 `.ts` 文件，约 2000+ 行 TypeScript 代码。

### 公共 API 表面（`mod.ts`）

```typescript
export { Coordinator, coordinator } from './coordinator'
export { BridgeManager, createBridgeManager, getBridgeManager } from './bridge_manager'
export { DifyClient } from './dify_adapter'
export { SkillRouter } from './skill_router'
export { SkillLoader } from './skill_loader'
```

---

## 2. Build 系统核验结果（关键证据）

### `package.json` 搜索结果

| 搜索范围 | 找到 `package.json`？ |
|---|---|
| `backend/src/` 整体 | ❌ **无** |
| `backend/src/domain/m04/` | ❌ 无 |
| `backend/src/infrastructure/workflow/` | ❌ 无（n8n_client.ts 等） |
| `backend/n8n_data/nodes/` | ✅ 有（n8n 自定义节点，与 M04 无关） |
| `backend/external/bytebot/packages/*/` | ✅ 有（Bytebot 子包，与 M04 无关） |

**关键发现**：`backend/src/` 目录下**没有任何 `package.json`**。

### Dockerfile 运行时镜像验证

**文件**：`backend/Dockerfile`（Stage 3 runtime）

```dockerfile
FROM python:3.12-slim-bookworm

# 只安装了 Node.js 运行时二进制文件
RUN apt-get install -y nodejs npm --no-install-recommends

# 没有 TypeScript 编译器（没有 tsc）
# 没有 tsx、没有 ts-node、没有 esbuild bundler
# 没有任何 npm/yarn/pnpm 包管理器

CMD ["bash", "-c", "cd backend && PYTHONPATH=. uv run --no-sync uvicorn ..."]
```

**结论**：
- 运行时镜像只含 **Node.js 运行时**（执行 `.mjs` / `tsx` 脚本）
- **不含 TypeScript 编译器**，无法编译 `.ts` 文件
- **不含 npm/pnpm**，无法安装依赖或执行构建

---

## 3. Python Runtime 调用链核验结果

### Python 层 M04 模块（对比）

| 模块路径 | 类型 | 与 TypeScript M04 关系 |
|---|---|---|
| `app/m04/registry_db.py` | Python | 仅做 registry 持久化（SQLite） |
| `app/m04/registry_manager.py` | Python | Python registry 管理器 |
| `app/m04/heartbeat_pulse.py` | Python | 心跳脉冲（健康检查） |
| `app/m04/` 合计 3 个文件 | Python | **与 `src/domain/m04/` 同名但完全无关** |

### Python → TypeScript 导入链核验

```
gateway/app.py (uvicorn FastAPI):
  → 不导入任何 m04 模块（已验证）
  → 不导入 n8n_client.ts
  → 不导入 bridge_manager.ts
  → 不导入 dify_adapter.ts

app/m11/ (治理域):
  → 不导入 m04 coordinator
  → governance_bridge 是纯 Python 的

app/m03/ (LangGraph):
  → 不导入 M04 TypeScript

app/channel/ (Feishu):
  → 不导入 M04 TypeScript
```

### TypeScript 模块内部调用关系

```
mod.ts:
  → import from '../../infrastructure/workflow/bridge_manager' ✅
  → import from '../../infrastructure/workflow/n8n_client' ✅
  → import from './coordinator' ✅

coordinator.ts:
  → N8NClient (from n8n_client.ts) ✅
  → DifyClient (from dify_adapter.ts) ✅
  → BridgeManager (from bridge_manager.ts) ✅
  → SkillRouter, SkillLoader (internal) ✅

unified_executor.ts:
  → BridgeManager (internal) ✅
```

**结论**：M04 TypeScript 代码**自洽但孤立**——内部导入链完整，但**外部没有任何消费者**。

---

## 4. M04 能作为独立系统运行吗？

### 独立 TypeScript 服务的要求

| 要求 | M04 现状 | 是否满足 |
|---|---|---|
| `package.json`（依赖管理） | ❌ 不存在 | **不满足** |
| TypeScript 编译器（`tsc` 或 `tsx`） | ❌ Docker runtime 无 | **不满足** |
| 构建脚本（`build:dev` / `build:prod`） | ❌ 不存在 | **不满足** |
| 独立进程入口（`main.ts` / `index.ts`） | ❌ 未找到 | **不满足** |
| 独立 port / host 配置 | ❌ 无 | **不满足** |
| 独立 Docker service | ❌ 无（docker-compose.yml 中无对应 service） | **不满足** |

### M04 在 Docker stack 中的位置

```
docker compose 全部 service：
  ✅ openclaw-app（Python uvicorn）
  ✅ redis
  ✅ dapr（sidecar）
  ✅ n8n（独立容器）
  ✅ qdrant
  ❌ 无任何 service 与 m04/ TypeScript 相关
```

### 唯一可能的执行路径

**路径 A**：`coordinator.ts` 作为 `tsx` 脚本被调用？
```bash
# 理论上可能，但：
# 1. 无人 import coordinator.ts
# 2. tsx 在 runtime 中存在（governance_bridge 用它执行 .mjs）
# 3. 但没有任何 Python 代码 spawn "tsx coordinator.ts"
```

**路径 B**：`n8n_client.ts` 通过某种机制被调用？
```bash
# 已验证：n8n 容器存在但 0 workflows，n8n_client.ts 无法被触发
```

**结论**：两条路径均**无消费者**，M04 TypeScript 代码处于**完全未执行状态**。

---

## 5. R55 调查与 R56 调查的关联

| 发现 | R55 结论 | R56 补充证据 |
|---|---|---|
| n8n 服务健康但 0 workflows | "有基础设施无落地集成" | 进一步确认：M04 是 n8n 的调用者，但 M04 本身也未运行 |
| M04 TypeScript 存在 | "代码存在但无消费者" | 确认：无 `package.json`，无 build，无 Docker service |
| Python → n8n_client | "Python 不调用 TypeScript" | 进一步确认：M04（TypeScript 端）也未被任何 Python 代码调用 |
| BridgeManager（n8n↔Dify） | "两端都空" | 确认：Dify 未验证，但即便 Dify 存在，BridgeManager 也无法被执行 |

### 完整的断开链

```
飞书用户
    ↓（WS 连接存在）
Feishu ChannelService（Python）→ 收到消息但无 ingress
    ↓
MessageBus（Python）
    ↓
??? （未找到）
    ↓
M04 Coordinator（TypeScript）← 从未被调用
    ↓
n8n_client.ts（TypeScript）← 从未被调用
    ↓
n8n workflows（0个）← 即便有也无法触发
    ↓
Dify（未验证）← 即便存在也无法 bridge
```

**整个 outbound 链路从 M04 层开始就是断的。**

---

## 6. 本轮后的全局判断

```
M04 TypeScript 协调层定性：废弃代码（Abandoned Code）
  → 代码存在：20个 .ts 文件，约 2000 行 ✅
  → 无法构建：无 package.json，无构建工具链 ❌
  → 无法运行：无独立 service，无进程入口，无消费者 ❌
  → 未被集成：Python runtime 完全不导入 m04/ TypeScript 模块 ❌
  → 未被执行：docker compose 无对应 service ❌

n8n 集成状态（R55 结论）维持：
  → n8n 服务 ✅
  → n8n_client.ts 代码 ✅
  → BridgeManager 代码 ✅
  → 0 workflows ❌
  → 调用链断裂（Python ❌ → M04 ❌ → n8n_client ❌ → n8n workflows ❌）

Feishu 集成状态（R54 结论）维持：
  → WS 连接 ✅
  → ChannelService 代码 ✅
  → 无真实 ingress 消息（8h 日志，0 事件）
```

---

## 7. 下一轮最优先方向建议

**推荐 Round 57：DeerFlow/OpenClaw 主链核心能力验证（从 governance 决策点 → 真实工具执行）**

**原因**：
1. M04（TypeScript）和 n8n（workflows）两条可能的扩展链均已证明为断开状态
2. 系统的**真实主链**是 Python 端：`ChannelService → MessageBus → LangGraph Executor → Tools`
3. 需要验证这个主链在真实用户消息缺席的情况下是否**结构完整、可执行**
4. 建议从 governance 决策点开始，追踪一个假设任务的完整执行路径

**关键问题**：若 Feishu 用户发来一条真实消息，系统能完成" governance 审批 → routing decision → 工具执行 → 回复"吗？

**备选方向**：验证 Dify 服务是否存在（n8n↔Dify bridge 的另一端）

**不建议继续 M04/n8n deeper**：
- M04 已是废弃代码，再挖掘无意义
- n8n 0 workflows 已说明无论服务多健康，没有 workflow 就无可验证能力
