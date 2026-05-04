# 下一步构建计划
> **编制日期**: 2026-04-14
> **编制依据**: 对照 docs/ 设计文档深度分析 + 当前建设现状评估

---

## 一、现状评估

### 1.1 已完成模块（基于 Mission.md）

| 模块族 | 状态 | 完成度 |
|--------|------|--------|
| 基础层 (F-01 ~ F-07) | ✅ 完成 | 100% |
| 感知层 (P2-01) | ✅ 完成 | 100% |
| 执行层 (P3-01 ~ P3-03) | ✅ 完成 | 100% |
| 决策层 (P4-01 ~ P4-02) | ✅ 完成 | 100% |
| 财富层 (P5-01 ~ P5-04) | ✅ 完成 | 95% |
| 进化层 (P9-01 ~ P9-03) | ✅ 完成 | 100% |
| 基础设施 (F-10 ~ F-17) | ✅ 完成 | 95% |

### 1.2 本次修复成果（2026-04-14）

| 模块 | 修复内容 | 完成度 |
|------|----------|--------|
| M10 意图澄清 | 五维清晰度评分 + IntentProfile + 四模式注入 + 九类专项问题 | 90% |
| M08 学习系统 | 六阶段夜间复盘 + Optimizer即时优化 + 经验包格式 | 90% |
| M07 数字资产 | 五级分级 + 快速淘汰机制 | 95% |
| M03 钩子系统 | HookRegistry注册/分发引擎 + priority配置 | 95% |
| M05 感知层 | 任务队列扫描 + Distiller协调 | 90% |

### 1.3 仍需建设的关键模块

| 优先级 | 模块 | 设计文档 | 当前状态 | 差距分析 |
|:------:|------|----------|----------|----------|
| 🔴 P0 | **M09 提示词系统** | docs/09_Prompt_Engineering_System.md | 仅有 roi_engine.ts | 五层架构未实现，SOUL.md未创建，DSPy未集成 |
| 🔴 P0 | **M06 记忆架构** | docs/06_Memory_Architecture.md | 无对应实现 | 五层记忆未实现，GraphRAG未集成 |
| 🟡 P1 | **M01 编排引擎** | docs/01_Orchestration_Engine.md | 部分实现 | DeerFlow注入未完成 |
| 🟡 P1 | **M04 三系统协同** | docs/04_Three_Systems_Coordination.md | search_service.ts存在 | 三大系统协同未实现 |
| 🟡 P1 | **M02 OMO Agent矩阵** | docs/02_OMO_Agent_Matrix.md | 无具体实现 | Agent路由未实现 |
| 🟢 P2 | **M11 执行守护** | docs/11_Execution_And_Daemons.md | watchdog.py存在 | gVisor沙盒未集成 |

---

## 二、下一步建设计划

### 2.1 总体建议：Phase 10.5 聚焦 M09+M06 基础设施

**理由**：
1. **M09 提示词系统**是横切整个系统的基础设施层（如同TCP/IP），影响所有模块的输出质量
2. **M06 记忆架构**是防止"越用越蠢"的关键，当前代码中完全没有实现
3. 这两个模块是 Phase 10 "OpenSpace生命周期"的核心支撑

### 2.2 详细执行计划

---

#### Step 1: M09 提示词系统工程启动（P0优先级）

**目标**: 建立五层提示词架构，实现提示词的动态组装和进化

**交付物**:
1. `src/domain/prompt_engine/soul.md` - SOUL.md基础提示词
2. `src/domain/prompt_engine/layer1_router.ts` - 提示词路由层
3. `src/domain/prompt_engine/layer2_monitor.ts` - 执行监控层
4. `src/domain/prompt_engine/layer3_feedback.ts` - 反馈采集层
5. `src/domain/prompt_engine/layer4_nightly.ts` - 夜间进化层
6. `src/domain/prompt_engine/layer5_asset.ts` - 资产固化层

**验收标准**:
- [ ] 五层架构代码框架完成
- [ ] Layer1 能根据任务类型路由到对应提示词策略
- [ ] Layer3 能捕获用户显式反馈并归因到提示词片段
- [ ] Layer4 能与 NightlyDistiller 联动执行提示词进化

---

#### Step 2: M06 记忆架构工程启动（P0优先级）

**目标**: 实现五层记忆架构，防止灾难性遗忘

**交付物**:
1. `src/domain/memory/working_memory.ts` - L1 工作记忆（ReMe压缩）
2. `src/domain/memory/session_memory.ts` - L2 会话记忆
3. `src/domain/memory/persistent_memory.ts` - L3 持久记忆
4. `src/domain/memory/knowledge_graph.ts` - L4 知识图谱
5. `src/domain/memory/visual_anchor.ts` - L5 视觉锚定

**验收标准**:
- [ ] 五层记忆代码框架完成
- [ ] L1 工作记忆在90k token时触发压缩
- [ ] L2 会话记忆在会话结束时自动写入
- [ ] 与现有 asset_manager.ts 联动

---

#### Step 3: M04 三系统协同完善（P1优先级）

**目标**: 实现搜索/任务/工作流三大系统的协同

**交付物**:
1. `src/application/coordination/coordinator.ts` - 统一调度器
2. `src/application/coordination/shared_context.ts` - SharedContext 管理
3. `src/application/coordination/search_adapter.ts` - 搜索系统适配器
4. `src/application/coordination/task_adapter.ts` - 任务系统适配器
5. `src/application/coordination/workflow_adapter.ts` - 工作流系统适配器

**验收标准**:
- [ ] Coordinator 能根据任务类型路由到对应系统
- [ ] SharedContext 能在三系统间共享
- [ ] 与 M10 Intent Clarification 联动

---

#### Step 4: Phase 10 收尾与 Phase 11 准备

**Phase 10 收尾**:
- [ ] OpenSpace FIX/DERIVED/CAPTURE 三操作闭环验证
- [ ] Real Doc 原子化执行验证
- [ ] 完整执行轨迹记录

**Phase 11 准备**:
- [ ] M01 DeerFlow 注入方案设计
- [ ] M11 gVisor 沙盒集成方案
- [ ] M12 统一配置中心方案

---

## 三、风险评估

| 风险 | 等级 | 影响 | 缓解措施 |
|------|------|------|----------|
| M09 五层架构过于复杂 | 高 | 实施周期拉长 | 分批次交付，先完成Layer1-3 |
| M06 GraphRAG依赖外部服务 | 中 | 可能不可用 | 先用简化版，后续集成 |
| 两模块同时开发资源分散 | 中 | 进度受影响 | 串行开发，先M09后M06 |

---

## 四、建议执行顺序

```
Week 1-2: M09 Layer1-3 实现 + 与M10/M08联动测试
Week 3-4: M09 Layer4-5 实现 + 提示词固化验证
Week 5-6: M06 五层记忆实现 + 与现有系统集成
Week 7-8: M04 三系统协同完善 + Phase10收尾
Week 9+: Phase 11准备（DeerFlow注入 + gVisor）
```

---

*本计划基于 2026-04-14 代码深度验证结果编制*
