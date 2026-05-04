# Phase 16-18 详细实施计划
> **编制日期**: 2026-04-14
> **编制依据**: BUILD_PLAN.md + PHASE_10_5_DETAILED_PLAN.md + NEXT_PLAN.md + 设计文档(M09/M06/M00)
> **计划版本**: V1.0
> **状态**: 待执行

---

## 一、现状总结

### 1.1 已完成里程碑

| Phase | 名称 | 完成度 | 关键成果 |
|-------|------|--------|----------|
| Phase 12 | Beta准备 | ✅ | 27个集成测试通过, API文档, 性能优化554 tasks/min |
| Phase 13 | Beta测试 | ✅ | 11个E2E场景通过, 8个压力测试通过 |
| Phase 14 | 生产准备 | ✅ | Dapr持久化, Redis集群, 监控告警 |
| **Phase 15** | **核心模块完善** | ✅ | **265个单元测试全部通过** |

### 1.2 Phase 15 完成清单

```
✅ hooks.test.ts          - HookRegistry注册/执行/priority/blocking
✅ watchdog.test.ts       - 日夜切换/任务队列扫描/watchdog协调
✅ asset_manager.test.ts   - 五级分级/快速淘汰/九类资产
✅ optimizer.test.ts      - 冗余检测/并行化识别/即时优化
✅ ice_engine.test.ts     - 五维评分/专项问题/四模式注入
✅ nightly_distiller.test.ts - 六阶段复盘/fixDegradedAsset
✅ prompt_engine.test.ts  - 五层架构/P1-P6组装/九大任务类型
```

### 1.3 仍需建设模块

| 优先级 | 模块 | 当前状态 | 差距 |
|--------|------|----------|------|
| P0 | **M09 Layer2-5 完善** | Layer1已实现 | 监控/反馈/进化/固化层未完整 |
| P0 | **MCP Server 真实实现** | 桩代码 | tools/call未对接M06/M07/M09 |
| P1 | **外部API集成** | 部分实现 | Jina/Claude/Feishu完整集成 |
| P1 | **Dapr状态管理** | 已有完整实现 | 需与Node.js核心联调 |
| P2 | **M12 云端编排** | 未开始 | 跨Agent通信协议 |

---

## 二、Phase 16: 集成联调 (Week 1-4)

### 2.1 目标
验证模块间集成，替换桩代码为真实实现

### 2.2 P0 任务详解

#### 任务 16.1: MCP Server 真实实现

**现状**: `src/infrastructure/server/mcp_server.py` 仅桩代码

**目标**: 实现 `tools/call` 真实调用链路

```
┌──────────────────────────────────────────────────────────────┐
│ MCP Server (Python) - 端口3500                                │
├──────────────────────────────────────────────────────────────┤
│  /tools/list          → 读取M09资产注册表                    │
│  /tools/call          → 路由到M06/M07/M09                   │
│  /assets/query        → M07 AssetRetriever                  │
│  /memory/search       → M06 MemoryNode.read()                │
│  /prompt/route        → M09 PromptRouter.route()            │
└──────────────────────────────────────────────────────────────┘
                              ↑ HTTP (Dapr sidecar)
┌──────────────────────────────────────────────────────────────┐
│ OpenClaw Core (Node.js)                                      │
│  ├── M06 Memory      → MemoryNode.read(query)               │
│  ├── M07 Asset       → AssetManager.query(intent)           │
│  └── M09 Prompt      → PromptRouter.route(input)            │
└──────────────────────────────────────────────────────────────┘
```

**实施步骤**:

| Day | 任务 | 交付物 | 验收标准 |
|-----|------|--------|----------|
| 1 | M09资产注册表对接 | 修改layer1_router.ts添加MCP导出接口 | `/tools/list`返回资产列表 |
| 2 | M06 Memory读取工具 | 添加memory/mod.ts MCP接口 | `/memory/search`返回记忆片段 |
| 3 | M07 Asset查询工具 | 添加asset_manager.ts MCP接口 | `/assets/query`返回资产列表 |
| 4 | M09 Prompt路由工具 | 添加prompt_engine MCP接口 | `/prompt/route`返回组装提示词 |
| 5 | 认证授权 | 实现API Key验证+5分钟缓存 | 未授权请求返回401 |

**文件变更清单**:

```
src/infrastructure/server/mcp_server.py     [修改] Python MCP Server真实调用Node.js核心
src/domain/prompt_engine/layer1_router.ts  [修改] 添加MCP导出方法
src/domain/memory/mod.ts                   [修改] 添加MCP接口
src/domain/asset_manager.ts                 [修改] 添加MCP接口
src/infrastructure/dapr/dapr_client.ts     [已存在] 完整实现，需联调
```

#### 任务 16.2: 外部 API 集成

**实施步骤**:

| API | 适配器文件 | Day | 集成内容 | 验收标准 |
|-----|-----------|-----|----------|----------|
| Jina | `jina_adapter.ts` | 6-7 | 搜索结果解析/分页/重试 | 分页支持, 3次重试 |
| Claude | `claude_code_adapter.ts` | 8-9 | 代码生成/分析/流式响应 | 支持tools调用 |
| Feishu | `feishu_client.ts` | 10-11 | 四色卡片推送/交互回调 | 推送成功, 回调响应 |

**文件变更清单**:

```
src/infrastructure/jina_adapter.ts         [修改] 完善分页和重试
src/infrastructure/execution/claude_code_adapter.ts [修改] 支持流式
src/infrastructure/feishu_client.ts       [新建] 完整飞书客户端
src/application/ui/feishu_cards.json       [修改] 四色卡片模板
```

### 2.3 P1 任务详解

#### 任务 16.3: Dapr 状态管理集成

**目标**: 将内存状态迁移到 Dapr statestore

```
┌─────────────────────────────────────────────────────────────┐
│ Dapr State Store (Redis-backed)                             │
├─────────────────────────────────────────────────────────────┤
│  memory_items    → L3-L5记忆持久化                          │
│  asset_index     → 九维资产索引                              │
│  session_state   → DAG执行状态                              │
│  task_queue      → 任务队列Pub/Sub                          │
└─────────────────────────────────────────────────────────────┘
```

**实施步骤**:

| Day | 任务 | 交付物 | 验收标准 |
|-----|------|--------|----------|
| 12-13 | dapr_client.ts完整实现 | 状态CRUD操作 | 增删改查成功 |
| 14-15 | 状态存储迁移 | memory_items/asset_index迁移 | 数据一致 |
| 16-17 | Pub/Sub集成 | 任务队列事件驱动 | 消息可靠传递 |
| 18-19 | DurableAgent语义 | exactly-once执行保证 | 状态机正确 |

**文件变更清单**:

```
src/infrastructure/dapr/client.ts           [修改] 完整实现
src/infrastructure/dapr/components/statestore.yaml [修改] 状态存储配置
src/infrastructure/dapr/components/pubsub.yaml [修改] Pub/Sub配置
src/domain/memory/pipeline/semantic_writer.ts [修改] 写入Dapr
src/domain/asset_manager.ts                [修改] 索引Dapr化
```

### 2.4 Phase 16 验收标准

```
[ ] MCP Server tools/call 真实调用 M06/M07/M09
[ ] Jina 适配器支持分页和重试
[ ] Claude 适配器支持流式响应
[ ] 飞书客户端实现四色卡片推送
[ ] Dapr state store 完整实现
[ ] Pub/Sub 任务队列可靠传递
[ ] 集成测试覆盖率 > 70%
```

---

## 三、Phase 17: 优化加固 (Week 5-6)

### 3.1 目标
生产级稳定性验证

### 3.2 P0 任务详解

#### 任务 17.1: 压力测试完善

**目标差距**:

| 测试项 | 目标 | 当前 | 差距 |
|--------|------|------|------|
| 记忆条目规模 | 10k+ | 1k | 10x |
| 并发任务数 | 100+ | 50 | 2x |
| 稳定性时长 | 7x24h | 50次迭代 | ~6小时模拟 |

**实施步骤**:

| Day | 任务 | 验收标准 |
|-----|------|----------|
| 20-21 | 10k记忆条目压测 | 1k条目已验证, 10k目标 |
| 22-23 | 100并发压测 | 50并发100%成功→100并发 |
| 24-25 | 24小时稳定性测试(后台) | 0错误 |

**执行命令**:

```bash
# 10k记忆条目压测
npx jest --testPathPattern="stress" --testNamePattern="10k.*memory"

# 100并发压测
npx jest --testPathPattern="stress" --testNamePattern="100.*concurrent"
```

### 3.3 P1 任务详解

#### 任务 17.2: 安全渗透测试

**目标**: 全部拦截 SQL注入/命令注入/XSS/权限绕过

| 测试项 | Day | 工具 | 验收标准 |
|--------|-----|------|----------|
| SQL注入 | 26 | sqlmap + manual | 全部拦截 |
| 命令注入 | 27 | RiskAssessor | 全部拦截 |
| XSS | 28 | burpsuite | 全部拦截 |
| 权限绕过 | 29 | manual | 全部拦截 |

#### 任务 17.3: 性能 Profiling

**目标**: 消除内存泄漏和 CPU 热点

| Day | 任务 | 工具 | 验收标准 |
|-----|------|------|----------|
| 30-31 | 内存泄漏检测 | `--detectLeaks + heap snapshot` | 无泄漏 |
| 32-33 | CPU热点分析 | `v8-profiler` | 热点优化 |
| 34-35 | 异步调用栈 | `async_hooks` | 链路清晰 |
| 36 | 优化策略实施 | 缓存/懒加载/流式 | 性能提升 |

### 3.4 Phase 17 验收标准

```
[ ] 10k记忆条目压测通过
[ ] 100并发任务100%成功
[ ] 24小时0错误
[ ] SQL注入全部拦截
[ ] 命令注入全部拦截
[ ] XSS全部拦截
[ ] 内存泄漏0发现
[ ] CPU热点优化完成
```

---

## 四、Phase 18: 部署上线 (Week 7-8)

### 4.1 目标
生产环境就绪

### 4.2 P0 任务详解

#### 任务 18.1: Staging 环境搭建

| Day | 任务 | 交付物 | 验收标准 |
|-----|------|--------|----------|
| 37-38 | docker-compose分离 | dev/staging/prod三套 | 独立配置 |
| 39-40 | 环境变量验证 | env_validator.sh | 必填变量检查 |
| 41-42 | Terraform配置 | main.tf | 基础设施代码化 |

**docker-compose 分离方案**:

```yaml
# docker-compose.yml 结构
services:
  openclaw-dev:
    profiles: [dev]
    environment:
      - NODE_ENV=development
    ...

  openclaw-staging:
    profiles: [staging]
    environment:
      - NODE_ENV=staging
    ...

  openclaw-prod:
    profiles: [prod]
    environment:
      - NODE_ENV=production
    ...
```

#### 任务 18.2: CI/CD 流水线

**GitHub Actions 配置**:

```yaml
stages:
  - lint: ESLint + Prettier
  - type-check: tsc --noEmit
  - test: Jest (unit + integration)
  - build: Docker image
  - deploy-staging: docker-compose up
  - e2e: Playwright
  - deploy-prod: approval gate
```

| Day | 任务 | 交付物 | 验收标准 |
|-----|------|--------|----------|
| 43-44 | GitHub Actions配置 | `.github/workflows/ci.yml` | 流水线正常 |
| 45-46 | E2E测试套件 | `playwright/` | 核心流程通过 |
| 47-48 | 审批Gate | approval配置 | 生产部署需审批 |

### 4.3 P1 任务详解

#### 任务 18.3: 监控告警配置

| 告警项 | 阈值 | Day | 动作 |
|--------|------|-----|------|
| CPU使用率 | >80% 5min | 49 | 飞书通知 |
| 内存使用率 | >85% 5min | 49 | 飞书通知 |
| 任务失败率 | >10% 10min | 50 | 飞书通知 |
| 响应延迟P99 | >500ms | 50 | 日志记录 |
| 磁盘使用率 | >90% | 51 | 立即通知 |

### 4.4 P2 任务详解

#### 任务 18.4: 生产部署

| Day | 任务 | 交付物 |
|-----|------|--------|
| 52-53 | 数据迁移方案 | migration_guide.md |
| 54-55 | 回滚预案 | rollback_plan.md |
| 56-57 | 运维手册 | ops_manual.md |
| 58-59 | 故障切换演练 | failover_drill.md |
| 60 | 部署上线 | 生产环境就绪 |

### 4.5 Phase 18 验收标准

```
[ ] dev/staging/prod 三套环境独立配置
[ ] CI/CD 流水线正常运行
[ ] E2E 测试套件通过
[ ] 生产部署需要审批Gate
[ ] 监控告警配置完成
[ ] 告警阈值符合要求
[ ] 数据迁移方案可行
[ ] 回滚预案完整
[ ] 运维手册齐全
```

---

## 五、执行时间线

```
Week 1 (Day 1-5):   Phase 16.1 MCP Server 核心实现
  Day 1:   M09资产注册表对接
  Day 2:   M06 Memory读取工具
  Day 3:   M07 Asset查询工具
  Day 4:   M09 Prompt路由工具
  Day 5:   认证授权

Week 2 (Day 6-11):  Phase 16.2 外部API集成
  Day 6-7: Jina适配器完善
  Day 8-9: Claude适配器完善
  Day 10-11: 飞书客户端实现

Week 3 (Day 12-16): Phase 16.3 Dapr状态管理
  Day 12-13: dapr_client完整实现
  Day 14-15: 状态存储迁移
  Day 16: Pub/Sub集成

Week 4 (Day 17-19): Phase 16 收尾
  Day 17-18: 集成测试
  Day 19: 文档完善

Week 5 (Day 20-25): Phase 17.1-2 压力测试+安全
  Day 20-21: 10k记忆压测
  Day 22-23: 100并发压测
  Day 24-25: 24小时稳定性

Week 6 (Day 26-36): Phase 17.3 性能Profiling
  Day 26-29: 安全渗透测试
  Day 30-33: 内存+CPU分析
  Day 34-36: 优化实施

Week 7 (Day 37-44): Phase 18.1-2 环境+CI/CD
  Day 37-40: Staging环境
  Day 41-44: CI/CD流水线

Week 8 (Day 45-60): Phase 18.3-4 监控+生产部署
  Day 45-50: 监控告警
  Day 51-55: 生产部署准备
  Day 56-60: 上线+收尾
```

---

## 六、文件变更总清单

### 6.1 新建文件

```
src/infrastructure/feishu_client.ts              # 飞书完整客户端 (当前仅模板)
.github/workflows/ci.yml                          # CI/CD流水线
playwright/                                       # E2E测试套件
terraform/                                        # IaC配置
prometheus/rules/                                 # 告警规则
grafana/provisioning/                             # Grafana配置
env_validator.sh                                  # 环境变量验证脚本
migration_guide.md                                # 数据迁移方案
rollback_plan.md                                  # 回滚预案
ops_manual.md                                     # 运维手册
```

### 6.2 修改文件

```
src/infrastructure/server/mcp_server.py            # Python MCP Server真实调用Node.js核心
src/infrastructure/jina_adapter.ts                # 分页+重试完善 (当前桩代码)
src/domain/prompt_engine/layer2_monitor.ts        # LLM-Judge评分完善
src/domain/prompt_engine/layer3_feedback.ts       # 反馈采集完善
src/domain/prompt_engine/layer4_nightly.ts         # GEPA进化完善
src/domain/prompt_engine/layer5_asset.ts         # 固化层完善
src/domain/memory/mod.ts                          # MCP接口添加
src/domain/asset_manager.ts                       # MCP接口添加
src/infrastructure/execution/claude_code_adapter.ts # 流式响应+tools调用
src/application/ui/feishu_cards.json               # 四色卡片模板完善
docker-compose.yml                                # dev/staging/prod环境分离
.env.example                                      # 环境变量补充
src/infrastructure/server/health_server.ts         # 健康检查增强
src/infrastructure/server/backup_manager.py         # 备份增强
src/infrastructure/dapr/dapr_client.ts          # [已存在] Dapr完整实现(571行)
src/infrastructure/dapr/components/statestore.yaml # [已存在] 状态存储配置
src/infrastructure/dapr/components/pubsub.yaml   # [已存在] Pub/Sub配置
```

---

## 七、验收检查清单

### Phase 16 验收

- [ ] MCP Server tools/call 真实调用 M06/M07/M09
- [ ] Jina 适配器支持分页和重试
- [ ] Claude 适配器支持流式响应
- [ ] 飞书客户端实现四色卡片推送
- [ ] Dapr state store 联调完成 (dapr_client.ts已完整实现)
- [ ] Pub/Sub 任务队列可靠传递
- [ ] 集成测试覆盖率 > 70%

### Phase 17 验收

- [ ] 10k记忆条目压测通过
- [ ] 100并发任务100%成功
- [ ] 24小时0错误
- [ ] SQL注入全部拦截
- [ ] 命令注入全部拦截
- [ ] XSS全部拦截
- [ ] 内存泄漏0发现
- [ ] CPU热点优化完成

### Phase 18 验收

- [ ] dev/staging/prod 三套环境独立配置
- [ ] CI/CD 流水线正常运行
- [ ] E2E 测试套件通过
- [ ] 生产部署需要审批Gate
- [ ] 监控告警配置完成
- [ ] 数据迁移方案可行
- [ ] 回滚预案完整
- [ ] 运维手册齐全

---

## 八、风险登记

| 风险ID | 风险描述 | 概率 | 影响 | 缓解措施 |
|--------|----------|:---:|:---:|----------|
| R-16-01 | MCP Server跨语言调用不稳定 | 中 | 高 | 添加重试和超时控制 |
| R-16-02 | Dapr运行时依赖 | 中 | 中 | 提供Docker Compose一键启动 |
| R-17-01 | 10k记忆压测内存不足 | 低 | 高 | 分批压测+监控 |
| R-17-02 | 安全测试阻断上线 | 低 | 高 | 提前进行P1扫描 |
| R-18-01 | 生产环境配置复杂 | 高 | 中 | IaC标准化+文档化 |
| R-18-02 | 数据迁移风险 | 中 | 高 | 充分测试+回滚预案 |

---

## 九、依赖关系

```
Phase 16 (完成) → Phase 17 (开始)
Phase 17 (完成) → Phase 18 (开始)

外部依赖:
- Dapr 1.17+ 运行时
- Redis 6.0+ 集群
- Docker 24.0+ 
- GitHub Actions (CI/CD)
- Prometheus + Grafana (监控)
```

---

*本计划由 Claude Code 编制*
*依据: BUILD_PLAN.md + PHASE_10_5_DETAILED_PLAN.md + NEXT_PLAN.md*
*日期: 2026-04-14*
