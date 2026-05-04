# 夜间升级中枢 - Upgrade Center

> 文档版本: v1.0
> 生成时间: 2026-04-19
> 状态: 设计草案
> 所属模块: M08 学习系统扩展

---

## 一、概述

### 1.1 目的

将升级治理流水线嵌入现有 M08 夜间复盘系统，形成**三轨并行夜间复盘**：

```
夜间复盘 = 学习复盘轨 + 升级中枢轨 + 资产维护轨
```

### 1.2 设计原则

**宪法Gate**：所有升级候选必须先通过宪法规则过滤才能执行任何操作。

| 层级 | 可自动执行 | 需要审批 |
|------|-----------|---------|
| T0 只读 | 情报收集、映射、报告、patch草案 | - |
| T1 实验 | 沙盒部署、基准测试 | - |
| T2 审批 | - | 依赖安装、服务启动、正式patch |
| T3 核心 | - | 触碰不可变区、核心逻辑变更 |

**冷静期机制**：同类升级默认 7 天内只记录、不重复打扰。

---

## 二、架构设计

### 2.0 架构统一说明

**设计决策**：升级中枢采用TypeScript实现，与`nightly_distiller.ts`保持语言一致。

| 组件 | 语言 | 位置 | 说明 |
|------|------|------|------|
| NightlyDistiller | TypeScript | `backend/src/domain/nightly_distiller.ts` | 现有M08六阶段实现 |
| 升级中枢 | TypeScript | `backend/src/upgrade_center/` | 新增U0-U8治理流水线 |
| 学习系统 | Python | `backend/app/m08/learning_system.py` | 骨架实现（暂不依赖） |

**数据流**：升级中枢直接导入`nightly_distiller.ts`的TypeScript类型定义，无需跨语言调用。

### 2.1 现有组件接口映射

为确保设计可落地，明确以下现有组件的接口扩展点：

| 现有组件 | 文件 | 扩展点 | 扩展方式 |
|---------|------|--------|---------|
| Watchdog | `watchdog.py` | 新增`should_trigger_upgrade_center()` | 在02:00触发后新增03:00触发 |
| NightlyDistiller | `nightly_distiller.ts` | 六阶段输出类型 | 直接导入`Stage2Bottlenecks`/`Stage4AssetChanges` |
| boulder.json | `boulder.json` | 新增`upgrade_center`字段 | JSON扩展，不改现有结构 |
| UnifiedConfig | `unified_config.py` | 新增9个阈值参数 | 在`_get_default_18_thresholds()`中追加 |
| feishu_cards.json | `feishu_cards.json` | 新增2个模板 | 在`templates`对象中追加 |

### 2.2 目录结构

### 2.1 目录结构

```
~/.deerflow/upgrade-center/          # 根目录（与M07资产隔离）
├── constitution/
│   ├── system_constitution_v1.md     # 宪法原文
│   ├── immutable_zone_candidates.json # 核心不可变区清单
│   └── approval_policy.yaml          # 审批策略配置
├── baselines/
│   ├── capability_topology.json      # 能力拓扑图
│   ├── module_tag_library.json       # 模块标签库
│   └── upgrade_mapping_index.json    # 升级映射索引
├── scouting/
│   ├── raw_intel/                   # 原始情报
│   └── normalized_candidates/        # 标准化候选
├── analysis/
│   ├── prior_scores/                # 先验分析分
│   ├── local_validation_plans/       # 本地验证计划
│   └── integration_maps/             # 集成映射
├── sandbox/
│   ├── experiment_queue.json         # 实验队列
│   ├── patches_draft/               # patch草案
│   ├── verify_scripts/              # 验证脚本
│   └── rollback_templates/           # 回滚模板
├── reports/
│   ├── nightly_internal/            # 内部夜间报告
│   ├── morning_feishu/               # 飞书晨报
│   └── approval_cards/               # 审批卡片
└── state/
    ├── observation_pool.json         # 观察池
    ├── experiment_pool.json          # 实验池
    ├── approval_backlog.json         # 审批待办
    └── cooldown_registry.json        # 冷静期注册表
```

### 2.2 模块位置

```
backend/src/upgrade_center/          # 位于backend/src/目录下
├── index.ts                         # 主编排器
├── types.ts                         # 共享类型定义
├── constitution_loader.ts           # U0 宪法装载
├── demand_sampler.ts                # U1 需求采样
├── external_scout.ts                # U1 外部情报采集
├── constitution_filter.ts            # U2 宪法筛选
├── local_mapper.ts                  # U3 本地映射
├── prior_scorer.ts                  # U4 先验评分
├── sandbox_planner.ts               # U5 沙盒计划
├── approval_tier.ts                 # U6 审批分级
├── report_generator.ts              # U7 报告生成
└── queue_manager.ts                 # U8 任务排队
```

**语言统一说明**：升级中枢采用TypeScript实现，与`nightly_distiller.ts`同语言，可直接导入其类型定义，无需跨语言调用。

### 2.3 时间安排

```
02:00-03:00: NightlyDistiller 六阶段（现有）
03:00-05:30: 升级中枢 U0-U8（新增）
08:00: 飞书升级日报（仅T2/T3候选存在时发送）
```

---

## 三、阶段定义

### U0: 宪法装载

**目的**：夜间复盘开始时加载宪法规则和状态。

**输入**：
- 用户审批历史
- 宪法规则文件
- 核心不可变区清单
- 上次未决审批项
- 观察池/实验层状态

**输出**：`ConstitutionState`
```typescript
interface ConstitutionState {
  constitution_loaded: boolean;
  immutable_zones: string[];
  pending_approvals: PendingApproval[];
  observation_pool_snapshot: Candidate[];
}
```

### U1: 升级需求采样

**目的**：从三条来源汇聚升级需求。

| 来源 | 内容 | 接入点 |
|------|------|--------|
| 内部痛点 | 失败工具、重复搜索、瓶颈步骤 | `NightlyDistiller.stage2_identifyBottlenecks()` → `Stage2Bottlenecks` |
| 资产退化 | 降级资产、失效工具、FIX候选 | `NightlyDistiller.stage4_generateAssets()` → `Stage4AssetChanges` |
| 外部情报 | GitHub release、npm/PyPI、文档 | `backend/src/upgrade_center/external_scout.ts` (新增) |

**关键接口**：直接导入`nightly_distiller.ts`的TypeScript类型定义：
```typescript
import { Stage2Bottlenecks, Stage4AssetChanges, NightlyReviewReport } from '../domain/nightly_distiller';
```

**新增文件**：`external_scout.ts` 实现外部情报采集，替代空壳`AssetGuardian.scout_and_retire()`

**输出**：`upgrade_demand_pool.json`

### U2: 宪法初筛

**目的**：按宪法对每个候选项做第一层分流。

| 条件 | 结论 |
|------|------|
| 热点但无长期价值 | 排除 |
| 纯包装/无真实增强 | 排除 |
| 与主方向弱相关 | 排除 |
| 高潜力但不成熟 | 观察池 |
| 先进但工程风险高 | 实验层 |
| 有明确增强潜力/补短板/0→1 | 深度分析池 |

**输出**：`constitution_filter_result.json`

### U3: 本地系统映射

**目的**：将外部项目翻译成对本地模块的增强价值。

**强制基线刷新**：
- 当前能力拓扑图
- 模块标签库
- 升级映射索引

**输出**：`local_mapping_report.json`
```typescript
interface LocalMapping {
  candidate_id: string;
  target_modules: string[];
  capability_gain: string[];
  integration_type: 'adapter' | 'patch' | 'replace' | 'fork_refactor';
  risk_zone_touches: string[];
  immutable_zone_touches: string[];
  affected_call_chains: string[];
  estimated_token_overhead: number;
}
```

### U4: 先验分析评分

**目的**：计算先验分析分，为本地验证提供输入。

**评分公式（100分制）**：

| 维度 | 最高分 | 说明 |
|------|--------|------|
| 长期价值 | 15 | 符合OpenClaw长期方向 |
| 能力上限提升 | 20 | 系统能力天花板的提升 |
| 补短板价值 | 15 | 解决明确短板 |
| 工程成熟度 | 10 | 项目质量/社区/维护状态 |
| 架构兼容度 | 15 | 与现有架构的契合程度 |
| 代码质量 | 10 | 代码规范/可读性/测试覆盖 |
| 部署可控性 | 5 | 部署难度/依赖复杂度 |
| 风险/回退复杂度 | 10 | 风险越高分越低 |

**门槛规则**：

| 分数 | 结论 |
|------|------|
| < 20% | 默认不接 |
| 20%+ | 可候选 |
| 50%+ | 高优先级 |
| 补短板/0→1/战略一致 | 允许进观察池或实验层 |

**输出**：`prior_score.json`

### U5: 沙盒验证计划生成

**目的**：为进入实验层的候选生成沙盒验证计划。

**生成内容（不直接修改主系统）**：
- 沙盒部署方案
- patch草案
- 依赖清单草案
- 验证样本脚本
- 回滚脚本模板
- 风险点与观测项

**输出文件**：
- `sandbox_deployment_plan.json`
- `patches_draft/{candidate}.patch`
- `verify_scripts/{candidate}_test.sh`
- `rollback_templates/{candidate}_rollback.sh`

### U6: 审批分级

**目的**：将候选分为T0/T1/T2/T3四级。

| 级别 | 可自动执行 | 需要审批 |
|------|-----------|---------|
| T0 | 情报/映射/报告/patch草案/入池 | - |
| T1 | 沙盒/基准测试/验证报告 | - |
| T2 | - | 依赖安装/服务启动/正式patch |
| T3 | - | 触碰核心不可变区/核心逻辑变更 |

**输出**：`approval_tiers.json`

### U7: 双报告生成

**A. 内部夜间报告**

路径：`reports/nightly_internal/upgrade-center-{date}.json`

**B. 飞书升级日报**

触发条件：仅当T2/T3候选存在时，08:00发送。

### U8: 任务排队与冷静期

**目的**：将结果写入队列，并执行冷静期检查。

**输出文件**：
- `upgrade_queue.json` - 实验层任务
- `approval_backlog.json` - 待用户审批
- `cooldown_registry.json` - 冷静期追踪

---

## 四、接口扩展

### 4.1 Watchdog 扩展

**文件**：`backend/src/infrastructure/watchdog.py`

**修改方式**：在现有`should_trigger_nightly_review()`后新增：
```python
NIGHTLY_UPGRADE_TRIGGER_HOUR = 3  # 03:00 AM

def should_trigger_upgrade_center():
    """检查是否应触发升级中枢（03:00执行）"""
    current_hour = datetime.datetime.now().hour
    current_minute = datetime.datetime.now().minute

    if current_hour == NIGHTLY_UPGRADE_TRIGGER_HOUR and current_minute < 5:
        # 检查boulder.json中的upgrade_center状态
        if BOULDER_PATH.exists():
            with open(BOULDER_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_run = data.get("upgrade_center", {}).get("last_full_run", "")
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            if not last_run.startswith(today):
                return True
    return False
```

**触发顺序**：NightlyDistiller(02:00) → UpgradeCenter(03:00)，共用boulder.json状态管理。

### 4.2 boulder.json 扩展

**文件**：`backend/src/infrastructure/boulder.json`

**扩展方式**：在现有JSON根对象中新增`upgrade_center`字段：
```json
{
  "system_id": "OpenClaw-Foundation-AAL-001",
  "heartbeat": {
    "last_sync": "2026-04-09T23:45:00",
    "mode": "ACTIVE",
    "interval_minutes": 5
  },
  "current_phase": "Phase 9 - 学习与进化系统 (CONSTRUCTING)",

  "upgrade_center": {
    "last_full_run": "2026-04-09T03:00:00Z",
    "last_partial_run": "2026-04-09T04:30:00Z",
    "current_stage": "U0",
    "pending_approvals": 3,
    "experiment_queue_size": 2,
    "observation_pool_size": 5,
    "nightly_upgrade_pending": false
  },

  "metrics": {
    "aal_sovereignty": "Master_Node",
    "storm_confidence": 0.98,
    "token_saving_rate": 0.72,
    "evolution_budget_remaining": 1.5
  }
}
```

### 4.3 M12 UnifiedConfig 扩展

**文件**：`backend/app/m12/unified_config.py`

**扩展方式**：在`_get_default_18_thresholds()`方法中新增9个升级中枢参数：
```python
def _get_default_18_thresholds(self):
    base = super()._get_default_18_thresholds()
    base.update({
        # === 现有18参数 ===
        # ... (保持不变)

        # === 升级中枢阈值 (新增9个) ===
        "upgrade_center_enabled": True,       # 升级中枢总开关
        "upgrade_trigger_hour": 3,           # 升级中枢触发时间(03:00)
        "upgrade_scan_interval_hours": 24,  # 扫描间隔(24小时)
        "prior_score_threshold": 20,         # 先验分门槛(<20%默认拒绝)
        "high_priority_threshold": 50,     # 高优先级门槛(>50%)
        "cooldown_days": 7,                 # 冷静期天数
        "auto_experiment_pool_size": 3,    # 自动进入实验层最大候选数
        "feishu_upgrade_report_hour": 8,    # 飞书升级日报发送时间
        "experiment_execution_hour": 10,    # 实验层任务执行时间
    })
    return base
```

### 4.4 飞书卡片扩展

**文件**：`backend/src/application/ui/feishu_cards.json`

**扩展方式**：在现有`templates`对象中新增两个模板：
```json
{
  "templates": {
    "red_alert": { ... },
    "yellow_milestone": { ... },
    "blue_progress": { ... },
    "gray_summary": { ... },
    "upgrade_review": {
      "title": "🟠 夜间升级中枢日报",
      "description": "**日期**: {{date}}\n**扫描候选**: {{demands_scanned}}\n**高价值候选**: {{high_value_count}}\n\n{{candidate_details}}",
      "actions": ["查看详情", "批准接入", "加入观察池", "否决"]
    },
    "approval_request": {
      "title": "🔴 升级审批请求",
      "description": "**项目**: {{project_name}}\n**先验分**: {{prior_score}}/100 ({{tier}})\n**涉及模块**: {{modules}}\n**风险等级**: {{risk_level}}\n\n{{impact_analysis}}\n\n**回滚方案**: {{rollback_plan}}",
      "actions": ["批准", "修改参数", "加入观察池", "否决"]
    }
  }
}
```

---

## 五、数据流

```
┌─────────────────────────────────────────────────────────────────────┐
│  02:00 NightlyDistiller 六阶段                                        │
│  输出: NightlyReviewReport                                          │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  03:00 升级中枢（Watchdog触发）                                        │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ U0: 宪法装载 → 读取 constitution/                               │ │
│  │ U1: 需求采样 → M08阶段2/4 + AssetGuardian                      │ │
│  │ U2: 宪法筛选 → 排除/观察池/实验层/深度分析池                    │ │
│  │ U3: 本地映射 → baselines/                                       │ │
│  │ U4: 先验评分 → 100分制公式                                       │ │
│  │ U5: 沙盒计划 → sandbox/patches_draft/                          │ │
│  │ U6: 审批分级 → T0/T1/T2/T3                                     │ │
│  │ U7: 报告生成 → reports/nightly_internal/ + 飞书                 │ │
│  │ U8: 任务排队 → upgrade_queue.json + approval_backlog.json       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  08:00 飞书升级日报（仅T2/T3候选存在时发送）                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 六、实施步骤

### 阶段一：基础设施（第1周）

1. 在 `~/.deerflow/upgrade-center/` 下创建目录结构
2. 创建宪法文件
3. 在 `boulder.json` 中增加 `upgrade_center` 字段

### 阶段二：核心模块（第2-3周）

1. 创建 `backend/src/upgrade_center/` 模块
2. 实现 U0-U8 各阶段
3. 实现 `external_scout.ts` 外部情报采集（替代空壳AssetGuardian）
4. 扩展 Watchdog 增加 03:00 升级中枢触发
5. 与 NightlyDistiller 集成（共享TypeScript类型）

### 阶段三：飞书集成（第4周）

1. 扩展 `feishu_cards.json` 模板
2. 实现晨报发送逻辑

### 阶段四：测试验收（第5周）

1. 端到端测试
2. M08 集成验证
3. 冷静期机制验证

---

## 七、风险缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 升级中枢运行超时 | 影响M08复盘 | 独立时间窗口(03:00-05:30) |
| 飞书日报过于频繁 | 用户疲劳 | 7天冷静期 + 仅高价值触发 |
| 误判核心不可变区 | 系统稳定性 | 宪法明确定义 + 双重确认 |
| 沙盒验证不充分 | 引入生产问题 | T2及以上必须验证通过才能上线 |

---

## 八、验收标准

### 功能验收
- [ ] 升级中枢能完整执行U0-U8所有阶段
- [ ] 冷静期机制正常工作（7天内同类不重复打扰）
- [ ] T2/T3候选能正确生成飞书审批卡片

### 集成验收
- [ ] 现有M08六阶段不受影响
- [ ] 升级中枢能读取M08阶段2/4输出
- [ ] 飞书卡片能正常发送

### 性能验收
- [ ] 升级中枢在30分钟内完成
- [ ] 不影响白天系统正常运行

---

## 附录A：核心不可变区清单

```json
{
  "immutable_zones": [
    {
      "zone_id": "M01_coordinator",
      "description": "M01协调器核心路由逻辑",
      "protection_level": "absolute"
    },
    {
      "zone_id": "M03_hooks",
      "description": "M03钩子系统敏感路径保护",
      "protection_level": "absolute"
    },
    {
      "zone_id": "M04_unified_executor",
      "description": "M04统一执行器核心",
      "protection_level": "high"
    },
    {
      "zone_id": "boulder_json",
      "description": "系统心跳配置",
      "protection_level": "high"
    }
  ]
}
```

## 附录B：先验评分细则

| 维度 | 0分 | 5分 | 10分 | 15分 | 20分 |
|------|-----|-----|------|------|------|
| 长期价值 | 纯追热点 | 短期有用 | 中期价值 | 符合方向 | 战略核心 |
| 能力上限提升 | 无提升 | <10% | 10-30% | 30-50% | >50% |
| 补短板价值 | 无关短板 | 边缘相关 | 部分相关 | 明确相关 | 核心短板 |
| 工程成熟度 | 概念验证 | 实验性 | 早期开源 | 成熟项目 | 行业标准 |
| 架构兼容度 | 完全冲突 | 较大改造 | 中等改造 | 小量适配 | 无缝接入 |
| 代码质量 | 无测试 | 测试<30% | 30-60% | 60-80% | >80% |
| 部署可控性 | 极高风险 | 高风险 | 中等风险 | 低风险 | 零风险 |
| 回退复杂度 | 无法回退 | 需数小时 | 需半小时 | 需数分钟 | 一键回退 |

---

*文档状态：设计草案 - 待审查*
