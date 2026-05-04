# 下一步行动计划
> **编制日期**: 2026-04-14
> **编制依据**: ACCEPTANCE_REPORT.md 全面验收结果
> **当前阶段**: Phase 18 完成 · Phase 19 待启动

---

## 一、当前状态总览

### 1.1 建设成就 (Phase 1-18)

| 里程碑 | 完成度 | 说明 |
|--------|:------:|------|
| Mission.md 组件 | 96.6% | 32/32 项已实现 |
| M06 五层记忆 | 89% | L1-L5 核心框架完成 |
| M04 三系统协同 | 90.8% | Search/Task/Workflow 协同完成 |
| Phase 0-4 + V3.1 | 98.3% | 全阶段建设完成 |
| 测试覆盖率 | >75% | 432 测试用例通过 |
| **综合符合度** | **93.7%** | **✅ 全面验收通过** |

### 1.2 已识别待办 (来自 ACCEPTANCE_REPORT.md)

| 优先级 | 待办项 | 影响 | 状态 |
|:------:|--------|:----:|:----:|
| 🟡 P1 | L4 GraphRAG 夜间提纯联动 | 中 | 待校准 |
| 🟡 P1 | L5 视觉锚定生产验证 | 低 | 待校准 |
| 🟡 P1 | MCP Server 参数补全 | 低 | 待校准 |
| 🟢 P2 | M01 DeerFlow 注入方案 | 高 | 待规划 |
| 🟢 P2 | 容灾恢复演练 | 中 | 待添加 |

---

## 二、Phase 19: 精度校准与增强

**目标**: 修复验收中发现的 P1 差距，将综合符合度提升至 97%+

### 2.1 Action 036: L4 GraphRAG 夜间提纯联动 (P1)

**目标**: 将 GraphRAG 实体关系抽取集成到 NightlyDistiller Stage2

**交付物**:
1. `nightly_distiller.ts` Stage2 扩展 — 加入 `extractEntityRelations()` 调用
2. `knowledge_graph.ts` — 添加 `addEntities()` / `addRelations()` 接口
3. 新增测试 `should extract entities for graph`

**执行步骤**:
```
Stage 2 (瓶颈识别) 现有逻辑
    ↓ 扩展
Stage 2.5 新增: 实体关系抽取
  - 调用轻量 LLM 提取实体 (entity)
  - 提取实体间关系 (relation)
  - 调用 knowledge_graph.ts 写入三元组
  - 生成 entities_found_count 指标
```

**验收标准**:
- [ ] NightlyDistiller Stage2 执行后，knowledge_graph 包含当日实体
- [ ] 实体数量统计写入 evolution_digest.json
- [ ] 测试覆盖 entity_relation_extract 函数

**预计工时**: 3-4 小时

---

### 2.2 Action 037: MCP Server 参数补全 (P1)

**目标**: 扩展 get_asset / list_assets 接口，支持 tier/category/status 过滤

**交付物**:
1. `mcp_server.py` — 扩展 get_asset/list_assets 参数
2. `asset_manager.ts` — 添加 filter 查询接口
3. 新增集成测试验证过滤参数

**接口扩展**:
```python
# get_asset
- 现有: query (string)
- 新增: tier (optional), category (optional), status (optional), limit (int)

# list_assets
- 现有: 无参数
- 新增: tier, category, status, limit, offset
```

**验收标准**:
- [ ] get_asset 支持 tier=premium 过滤
- [ ] list_assets 支持 category=task 过滤
- [ ] 集成测试验证参数组合过滤

**预计工时**: 2 小时

---

### 2.3 Action 038: L5 视觉锚定生产验证 (P1)

**目标**: 添加 visual_anchor 生产集成测试，验证 CortexaDB 锚定格式

**交付物**:
1. `e2e/visual_anchor.test.ts` — 生产集成测试
2. 验证锚定格式 `{step_id, action, target_element, result, timestamp}`
3. 验证单帧活跃策略 (历史帧坍缩为文本锚)

**验收标准**:
- [ ] 测试验证锚定写入格式正确
- [ ] 测试验证历史帧坍缩逻辑
- [ ] 检索召回率 > 80%

**预计工时**: 2-3 小时

---

## 三、Phase 20: 运维体系完善

**目标**: 完成 P2 待办，增强生产运维能力

### 3.1 Action 039: 容灾恢复演练剧本 (P2)

**目标**: 创建 DR 演练剧本，添加到 DEPLOYMENT_CHECKLIST

**交付物**:
1. `disaster_recovery.md` — 完整 DR 演练剧本
2. 演练场景:
   - 场景 A: Redis down → 自动切换 → 恢复验证
   - 场景 B: Docker 容器崩溃 → 自动重启 → 数据完整性验证
   - 场景 C: 网络中断 → 队列积压 → 恢复后补处理
   - 场景 D: 磁盘满 → 告警触发 → 清理验证

**验收标准**:
- [ ] 4 个演练场景剧本完成
- [ ] 每个场景包含: 触发条件 → 预期行为 → 恢复步骤 → 验证方法
- [ ] 添加到 DEPLOYMENT_CHECKLIST.md

**预计工时**: 2 小时

---

### 3.2 Action 040: M01 DeerFlow 注入方案设计 (P2)

**目标**: 设计 M01 编排引擎增强方案，为 Phase 21 实施做准备

**交付物**:
1. `M01_DEERFLOW_INJECTION_PLAN.md` — 详细设计方案
2. 设计内容:
   - DeerFlow 2.0 注入点分析
   - OpenClaw 消息管线对接方案
   - 飞书→DeerFlow→编排→OpenClaw 执行路径
   - 风险评估与回退方案

**验收标准**:
- [ ] 完成 DeerFlow 注入点分析文档
- [ ] 完成消息流转图
- [ ] 评审通过 (内部评审)

**预计工时**: 4 小时 (设计文档)

---

## 四、Phase 21: 可选增强 (视资源情况)

**优先级较低，视 Phase 19-20 完成后资源情况决定**

### 4.1 Phase 21.1: 语音 I/O 集成 (P2)

| 组件 | 技术选型 | 优先级 |
|------|---------|:------:|
| 语音输入 | fast-whisper | 🟢 P2 |
| 语音输出 | Kokoro TTS | 🟢 P2 |
| 唤醒词检测 | 独立模块 | 🟢 P2 |

### 4.2 Phase 21.2: 屏幕监控增强 (P2)

| 组件 | 技术选型 | 优先级 |
|------|---------|:------:|
| 屏幕截图 | mss | 🟢 P2 |
| 视觉理解 | UI-TARS-2 | 🟢 P2 |
| 变化检测 | 差异比对 | 🟢 P2 |

---

## 五、执行时间线

```
2026-04-15 (Day 1)
├── Action 036: L4 GraphRAG 联动
│   ├── 扩展 nightly_distiller.ts Stage2
│   ├── 添加 knowledge_graph.ts 接口
│   └── 测试验证
│
├── Action 037: MCP Server 参数补全
│   ├── 扩展 get_asset/list_assets
│   └── 集成测试

2026-04-16 (Day 2)
├── Action 038: L5 视觉锚定验证
│   ├── 创建 visual_anchor.test.ts
│   └── 锚定格式验证

├── Action 039: 容灾恢复演练剧本
│   ├── 创建 disaster_recovery.md
│   └── 添加到 DEPLOYMENT_CHECKLIST

2026-04-17 (Day 3)
├── Action 040: M01 DeerFlow 注入方案设计
│   ├── 注入点分析
│   ├── 消息流转设计
│   └── 评审文档

2026-04-18 (Day 4+)
├── Phase 19 验收
├── Phase 20 验收
└── Phase 21 可选增强 (视资源)
```

---

## 六、验收标准

### Phase 19 验收 (精度校准)

| Action | 验收标准 | 完成标志 |
|--------|---------|---------|
| 036 | L4 GraphRAG 联动 | Stage2 执行后 knowledge_graph 包含实体 |
| 037 | MCP 参数补全 | get_asset 支持 tier/category 过滤 |
| 038 | L5 视觉锚定验证 | visual_anchor.test.ts 全部通过 |

**目标**: 综合符合度提升至 **97%+**

### Phase 20 验收 (运维完善)

| Action | 验收标准 | 完成标志 |
|--------|---------|---------|
| 039 | DR 演练剧本 | 4 个场景剧本完整 |
| 040 | DeerFlow 注入方案 | 设计文档评审通过 |

---

## 七、资源需求

| 资源 | 需求 | 备注 |
|------|------|------|
| 开发时间 | 2 人/天 | Action 036-038 |
| 开发时间 | 1 人/天 | Action 039-040 |
| 测试环境 | 1 套 | Docker Compose 本地环境 |
| 评审资源 | 1 次 | M01 设计方案评审 |

---

## 八、风险与依赖

| 风险 | 等级 | 缓解措施 |
|------|:----:|---------|
| GraphRAG 依赖外部服务不可用 | 🟡 中 | 使用本地轻量 LLM 作为降级方案 |
| L5 生产验证发现新问题 | 🟡 中 | 预留 2 小时缓冲 |
| M01 设计方案评审不通过 | 🟢 低 | 设计多套备选方案 |

---

*本计划基于 ACCEPTANCE_REPORT.md 验收结果编制*
*下次更新: Phase 19-20 完成后*
