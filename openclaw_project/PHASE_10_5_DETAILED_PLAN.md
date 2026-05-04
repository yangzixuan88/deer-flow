# Phase 10.5 详细施工计划
> **编制日期**: 2026-04-14
> **编制依据**: docs/09_Prompt_Engineering_System.md (655行) + docs/06_Memory_Architecture.md (665行)
> **计划级别**: 详细施工蓝图（直接可执行）

---

## 一、M09 提示词系统工程详细施工计划

### 1.1 架构总览

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        M09 五层提示词架构                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  Layer1 路由层 (layer1_router.ts)                                            │
│   ├── 任务类型识别器 → 九大任务类型路由                                       │
│   ├── 资产检索器 → 相似度≥0.85命中历史优质提示词                             │
│   └── 上下文组装器 → P1-P6优先级组装                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│  Layer2 监控层 (layer2_monitor.ts)                                          │
│   ├── LLM-Judge实时评分 → 完整性/准确性/格式/偏好匹配                         │
│   └── 执行轨迹记录 → 提示词片段+质量分+token消耗+失败原因                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  Layer3 反馈层 (layer3_feedback.ts)                                         │
│   ├── 自动质量信号 → 任务完成度/后续成功率/用户重做率                         │
│   ├── 显式用户反馈 → 飞书负面关键词捕获                                        │
│   └── 贡献度归因 → 优质片段标注晋升候选                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│  Layer4 进化层 (layer4_nightly.ts)                                          │
│   ├── GEPA反射进化 → 六步流程：选候选→反思→生成→沙盒→决策→晋升               │
│   └── DSPy自动编译 → 三种触发：模型更新/质量下降7天/用户主动触发               │
├──────────────────────────────────────────────────────────────────────────────┤
│  Layer5 固化层 (layer5_asset.ts)                                            │
│   └── 第7类提示词资产 → 四级分级体系(记录/一般/可用/核心)                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 P1-P6 优先级组装体系

| 优先级 | 层级名称 | 内容来源 | 注入规则 |
|:---:|---|---|---|
| **P1** | 安全约束层 | Mission.md边界+权限规则 | 不可覆盖·任何任务最高优先级 |
| **P2** | 用户偏好层 | 第8类用户偏好资产 | 输出语言/格式/详细程度 |
| **P3** | 任务专用层 | 九大Signature模板库 | 搜索/代码/写作等专用提示词 |
| **P4** | Few-shot示例层 | 提示词资产库检索 | 同类任务Top3-5示例自动注入 |
| **P5** | 上下文信息层 | SharedContext+记忆召回 | 工具状态/搜索结果/记忆片段 |
| **P6** | 基础系统层 | SOUL.md | 身份定义+通用格式+基础能力 |

### 1.3 九大任务类型与Signature对照表

| 任务类型 | 核心Signature | 特殊注入内容 | 质量指标 |
|---|---|---|---|
| 信息搜索 | `SearchSynth` | 时效性要求+来源可信度+摘要长度 | 引用准确率·信息完整度 |
| 代码生成 | `CodeGen` | 语言版本+代码风格+测试要求+依赖约束 | 可运行率·代码质量分 |
| 文档写作 | `DocWrite` | 目标受众+文档类型+结构模板+字数要求 | 可读性·结构完整性 |
| 数据分析 | `DataAnalysis` | 数据类型+分析维度+可视化偏好+结论格式 | 结论准确率·洞察深度 |
| 问题诊断 | `Diagnosis` | 错误信息+环境上下文+历史解决方案+排查顺序 | 首次修复成功率 |
| 规划制定 | `Planning` | 时间约束+资源限制+优先级偏好+风险容忍度 | 计划可执行率·完成率 |
| 创意生成 | `Creative` | 风格参考+创意边界+用户审美偏好历史 | 用户满意度·采纳率 |
| 系统配置 | `SysConfig` | 目标系统版本+已有配置+已知兼容问题 | 配置成功率·副作用 |
| 自主决策 | `AALDecision` | Mission约束+权限级别+当前能力版图+风险评估 | 决策质量·Mission对齐 |

### 1.4 搜索触发场景

| 场景 | 触发条件 | 搜索目标 | 执行流程 |
|---|---|---|---|
| **场景1** | 遇到全新任务类型 | `[任务类型] prompt best practices 2026` | 搜索→抓取5篇→提炼候选→测试3次→入库 |
| **场景2** | 某类提示词连续3次低于阈值 | `[失败关键词] [任务类型] prompt fix` | 搜索→社区方案→生成改进→夜间GEPA测试 |
| **场景3** | 检测到模型版本更新 | `[新模型] prompting guide changes` | 搜索→变化分析→DSPy重编译 |
| **场景4** | 每周日01:00定期 | `prompt engineering techniques [当月]` | 扫描新技术→评估提升可能 |

### 1.5 GEPA 六步反射进化流程

```
① 选候选
  从当天轨迹选出：低分case(<0.7) + 高分case(>0.9)
  ↓
② 轨迹反思
  LLM读取完整执行轨迹：
  "使用了哪段提示词 → 输出是什么 → 评分多少 → 失败原因"
  ↓
③ 生成候选
  基于反思生成3-5个改进版
  保留Pareto前沿上表现最好的多样化候选
  ↓
④ 沙盒测试
  用历史case集跑验证
  计算综合质量分 vs 当前最优版本
  ↓
⑤ 决策固化
  候选分数 > 当前版本 + 0.05阈值
  → 替换（原版本保留一周作回滚备份）
  ↓
⑥ 晋升入库
  新版本进入提示词资产库
  按四级体系管理·自动更新版本号
```

### 1.6 DSPy 三种编译触发条件

| 触发条件 | 触发时机 | 编译范围 | 执行方式 |
|---|---|---|---|
| **模型版本更新** | 检测到Claude/GPT版本变化 | 所有Signatures重编译 | 沙盒执行，100-500次LLM调用 |
| **持续质量下降** | 某类任务成功率连续7天下跌 | 该任务类型Signatures | 后台自动执行 |
| **用户主动触发** | 飞书发送「重优化提示词」 | 指定Signature | 立即执行 |

---

## 二、M06 记忆体系工程详细施工计划

### 2.1 架构总览

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        M06 五层记忆架构                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  L1: 工作记忆 (working_memory.ts)                                          │
│   ├── ReMe三阶段压缩框架                                                    │
│   ├── 90k token触发阈值                                                    │
│   └── 保留最近10k + 结构化摘要                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  L2: 会话记忆 (session_memory.ts)                                          │
│   ├── SimpleMem语义无损压缩                                                 │
│   ├── 跨会话LoCoMo F1=0.613                                                │
│   └── agent_end钩子自动写入                                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│  L3: 持久记忆 (persistent_memory.ts)                                        │
│   ├── MemOS Local Plugin (降token 72%)                                     │
│   ├── FTS5+向量混合检索 (BM25+RRF融合)                                      │
│   └── 02:00 Dreaming进程→短期信号整合→晋升MEMORY.md                        │
├──────────────────────────────────────────────────────────────────────────────┤
│  L4: 知识图谱 (knowledge_graph.ts)                                          │
│   ├── GraphRAG夜间提纯 (00:30-06:00)                                        │
│   ├── Mem0语义节点网络                                                     │
│   └── 实体-关系三元组提取→防灾难性遗忘                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│  L5: 视觉锚定 (visual_anchor.ts)                                             │
│   ├── CortexaDB本地向量/图数据库                                            │
│   ├── Single-Frame-Active策略                                               │
│   └── GUI操作历史坍缩为文本锚                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 PostToolUse 七阶段语义写入管线

```
PostToolUse钩子触发
    ↓
① SHA-256去重 (5分钟窗口·重复调用跳过)
    ↓
② 隐私脱敏 (移除API Key/密码/<private>标签)
    ↓
③ 观察存储 (原始事件流·只追加不修改)
    ↓
④ LLM语义压缩 (轻量模型提取: 类型/事实/叙述/概念/涉及文件)
    ↓
⑤ Zod格式验证 (失败自动重试一次)
    ↓
⑥ 质量打分 (0-100·低于30分直接丢弃)
    ↓
⑦ 向量嵌入生成 → 写入对应记忆层
    ├── 高紧急度 → L1工作记忆
    ├── 中重要度 → L2会话记忆
    └── 持久价值 → L3持久记忆+L4图谱候选
```

### 2.3 记忆检索优先级

| 优先级 | 记忆层 | 召回速度 | 用途场景 |
|:---:|---|---|---|
| 1 | L1工作记忆 | 最快 | 当前任务上下文 |
| 2 | L4知识图谱 | 快 | 结构化实体查询·跨时间精准检索 |
| 3 | L2会话记忆 | 中 | 近期会话语义·温热高质量 |
| 4 | L3持久记忆 | 慢 | 全量混合检索·广泛兜底 |
| 5 | L5视觉锚定 | 中 | 仅视觉任务时 |

### 2.4 夜间记忆整合节奏

| 时间 | 进程 | 引擎 | 动作 |
|---|---|---|---|
| 每日 00:30-06:00 | GraphRAG炼金 | GraphRAG+Mem0 | 全天流水→实体关系提取→知识图谱更新 |
| 每日 02:00 | Dreaming整合 | OpenClaw内置 | 短期信号→评分+频率+多样性门槛→晋升MEMORY.md |
| 每周日 01:00 | 外部情报 | 搜索系统 | prompt engineering新技术扫描 |

---

## 三、详细交付物清单与文件结构

### 3.1 M09 提示词系统交付物

```
src/domain/prompt_engine/
├── soul.md                          # SOUL.md基础提示词 (P6基础层)
├── layer1_router.ts                 # 路由层：任务识别+资产检索+P1-P6组装
├── layer2_monitor.ts                # 监控层：LLM-Judge+执行轨迹
├── layer3_feedback.ts               # 反馈层：质量信号+用户反馈+贡献归因
├── layer4_nightly.ts                # 进化层：GEPA+ DSPy编译
├── layer5_asset.ts                  # 固化层：第7类资产对接
├── signatures/
│   ├── mod.ts                       # Signature模块导出
│   ├── search_synth.ts              # SearchSynth签名
│   ├── code_gen.ts                  # CodeGen签名
│   ├── doc_write.ts                 # DocWrite签名
│   ├── data_analysis.ts             # DataAnalysis签名
│   ├── diagnosis.ts                 # Diagnosis签名
│   ├── planning.ts                  # Planning签名
│   ├── creative.ts                  # Creative签名
│   ├── sys_config.ts                # SysConfig签名
│   └── aal_decision.ts              # AALDecision签名
├── recipes/
│   ├── mod.ts                       # 配方模块导出
│   ├── search_recipe.ts             # 搜索任务配方
│   ├── code_recipe.ts               # 代码任务配方
│   └── ...                          # 其他8个配方
├── assembly/
│   ├── mod.ts                       # 组装模块导出
│   ├── priority_assembler.ts        # P1-P6优先级组装器
│   └── context_builder.ts           # 上下文构建器
├── gefa/
│   ├── mod.ts                       # GEPA模块导出
│   ├── candidate_selector.ts        # 候选选择器
│   ├── trajectory_reflector.ts      # 轨迹反思器
│   ├── candidate_generator.ts       # 候选生成器
│   ├── sandbox_tester.ts            # 沙盒测试器
│   └── decision_engine.ts           # 决策引擎(固化判断)
├── dspy/
│   ├── mod.ts                       # DSPy模块导出
│   ├── compiler.ts                  # MIPROv2编译器
│   └── signature_manager.ts         # Signature管理器
├── search/
│   ├── mod.ts                       # 搜索模块导出
│   ├── trigger_detector.ts          # 触发场景检测器
│   ├── result_processor.ts          # 结果处理器
│   └── asset_converter.ts           # 转化为提示词资产
└── types.ts                         # 类型定义

```

### 3.2 M06 记忆系统交付物

```
src/domain/memory/
├── mod.ts                           # 模块导出
├── layer1/
│   ├── mod.ts                       # L1模块导出
│   ├── working_memory.ts            # 工作记忆(ReMe压缩)
│   ├── reme_compressor.ts           # ReMe三阶段压缩
│   └── contradiction_detector.ts     # 矛盾检测器
├── layer2/
│   ├── mod.ts                       # L2模块导出
│   ├── session_memory.ts            # 会话记忆
│   └── simplemem_adapter.ts         # SimpleMem适配器
├── layer3/
│   ├── mod.ts                       # L3模块导出
│   ├── persistent_memory.ts         # 持久记忆
│   ├── memos_plugin.ts              # MemOS Local Plugin适配器
│   └── hybrid_retriever.ts          # FTS5+向量混合检索
├── layer4/
│   ├── mod.ts                       # L4模块导出
│   ├── knowledge_graph.ts           # 知识图谱
│   ├── graphrag_purifier.ts         # GraphRAG夜间提纯
│   ├── mem0_adapter.ts              # Mem0适配器
│   └── entity_extractor.ts          # 实体关系提取器
├── layer5/
│   ├── mod.ts                       # L5模块导出
│   ├── visual_anchor.ts             # 视觉锚定
│   ├── cortexa_adapter.ts           # CortexaDB适配器
│   └── frame_collapser.ts           # 历史帧坍缩器
├── pipeline/
│   ├── mod.ts                       # 管线模块导出
│   ├── semantic_writer.ts           # PostToolUse语义写入
│   ├── deduplicator.ts              # SHA-256去重
│   ├── privacy_sanitizer.ts         # 隐私脱敏
│   ├── llm_compressor.ts           # LLM语义压缩
│   ├── zod_validator.ts            # Zod格式验证
│   ├── quality_scorer.ts            # 质量打分
│   └── vector_embedder.ts           # 向量嵌入生成
└── types.ts                         # 类型定义

```

---

## 四、详细施工步骤（Week 1-8）

### Week 1-2: M09 Layer1-3 实现

| Day | 任务 | 交付物 | 验收标准 |
|:---:|---|---|
| 1 | 创建src/domain/prompt_engine/目录结构 | 目录骨架+types.ts | 目录创建成功 |
| 2 | 实现TaskType九大类型识别逻辑 | layer1_router.ts核心逻辑 | 能识别9种任务类型 |
| 3 | 实现P1-P6优先级组装器 | priority_assembler.ts | P1安全层不可覆盖·P6兜底 |
| 4 | 实现九大Signature定义 | signatures/*.ts | 9个Signature文件 |
| 5 | **用户贡献点**: 验证任务类型识别准确率 | 反馈改进方向 | 识别准确率≥85% |
| 6 | 实现资产检索器(0.85阈值) | asset_retriever.ts | 相似度≥0.85直接复用 |
| 7 | **用户贡献点**: 提供已知优质提示词案例 | 补充到资产库 | 资产库≥10条 |
| 8 | 实现LLM-Judge评分(维度:完整性/准确性/格式/偏好) | layer2_monitor.ts | 评分输出标准化 |
| 9 | 实现执行轨迹记录 | trace_recorder.ts | 记录片段+分+token+失败原因 |
| 10 | **用户贡献点**: 定义质量阈值 | 反馈阈值设置建议 | 阈值0.7合理 |

### Week 3-4: M09 Layer4-5 + DSPy集成

| Day | 任务 | 交付物 | 验收标准 |
|:---:|---|---|
| 11 | 实现GEPA六步流程骨架 | layer4_nightly.ts | 六步都有空实现 |
| 12 | 实现候选选择器(低分<0.7+高分>0.9) | candidate_selector.ts | 选出对比集 |
| 13 | 实现轨迹反思器 | trajectory_reflector.ts | LLM反思输出结构化 |
| 14 | 实现候选生成器(3-5个多样版本) | candidate_generator.ts | Pareto前沿保留 |
| 15 | **用户贡献点**: 决定阈值参数 | 0.05阈值是否合理 | 确认阈值 |
| 16 | 实现沙盒测试器 | sandbox_tester.ts | 质量对比输出 |
| 17 | 实现决策固化引擎 | decision_engine.ts | 分数>当前+0.05才替换 |
| 18 | 实现DSPy Signature管理器 | dspy/signature_manager.ts | 9个Signature注册 |
| 19 | 实现MIPROv2编译器 | dspy/compiler.ts | 三种触发条件检测 |
| 20 | 实现Layer5固化层对接第7类资产 | layer5_asset.ts | 资产四级分级 |

### Week 5-6: M06 五层记忆实现

| Day | 任务 | 交付物 | 验收标准 |
|:---:|---|---|
| 21 | 创建src/domain/memory/目录结构 | 目录骨架+types.ts | 目录创建成功 |
| 22 | 实现L1 ReMe压缩框架(90k阈值) | working_memory.ts | 触发后保留10k+摘要 |
| 23 | 实现矛盾检测+压缩前Flush | contradiction_detector.ts | 矛盾标记UNVERIFIED |
| 24 | **用户贡献点**: 确定保留token数 | 10k是否合理 | 确认参数 |
| 25 | 实现L2 SimpleMem适配器 | session_memory.ts | 跨会话F1≥0.6 |
| 26 | 实现L3 MemOS适配器 | persistent_memory.ts | 降token72% |
| 27 | 实现FTS5+向量混合检索 | hybrid_retriever.ts | BM25+RRF融合 |
| 28 | **用户贡献点**: 确定检索参数 | maxResults等 | 确认参数 |
| 29 | 实现L4 GraphRAG夜间提纯 | knowledge_graph.ts | 00:30-06:00执行 |
| 30 | 实现实体关系提取器 | entity_extractor.ts | 三元组格式输出 |
| 31 | 实现Mem0适配器 | mem0_adapter.ts | 语义节点网 |
| 32 | **用户贡献点**: 图谱更新频率 | 每日vs每周 | 确认策略 |
| 33 | 实现L5 CortexaDB适配器 | cortexa_adapter.ts | Single-Frame-Active |
| 34 | 实现历史帧坍缩器 | frame_collapser.ts | 锚点text_summary格式 |
| 35 | **用户贡献点**: 视觉锚定策略 | 单帧活跃策略确认 | 确认策略 |

### Week 7-8: PostToolUse管线 + M04三系统协同

| Day | 任务 | 交付物 | 验收标准 |
|:---:|---|---|
| 36 | 实现七阶段语义写入管线骨架 | pipeline/semantic_writer.ts | 七阶段都有空实现 |
| 37 | 实现SHA-256去重(5分钟窗口) | pipeline/deduplicator.ts | 重复跳过 |
| 38 | 实现隐私脱敏 | pipeline/privacy_sanitizer.ts | API Key等移除 |
| 39 | 实现LLM语义压缩 | pipeline/llm_compressor.ts | 5类提取:类型/事实/叙述/概念/文件 |
| 40 | **用户贡献点**: 脱敏规则 | 确定脱敏模式 | 确认规则 |
| 41 | 实现Zod格式验证 | pipeline/zod_validator.ts | 失败重试一次 |
| 42 | 实现质量打分(0-100, <30丢弃) | pipeline/quality_scorer.ts | 电路断路器 |
| 43 | 实现向量嵌入生成 | pipeline/vector_embedder.ts | 写入对应记忆层 |
| 44 | 实现M04 Coordinator统一调度器 | coordinator.ts | 三系统路由 |
| 45 | 实现SharedContext管理 | shared_context.ts | prompt_context字段 |
| 46 | **用户贡献点**: 三系统优先级 | 搜索/任务/工作流 | 确认路由策略 |
| 47 | 跨模块联调:M09+M06 | 完整集成测试 | PostToolUse→写入→检索→组装→执行 |
| 48 | 生成Phase 10.5验收报告 | VERIFICATION_10_5.md | 所有验收标准通过 |

---

## 五、关键设计决策点（需用户参与）

### 5.1 M09 设计决策

| # | 决策项 | 选项A | 选项B | 推荐 | 依据 |
|---|--------|-------|-------|------|------|
| D-031 | 任务类型识别方式 | 规则匹配 | LLM动态识别 | LLM动态 | 九大类型边界模糊 |
| D-032 | 资产检索阈值 | 0.80 | **0.85** | 0.85 | 平衡精度与复用率 |
| D-033 | GEPA阈值参数 | 0.03 | **0.05** | 0.05 | 防止频繁替换 |
| D-034 | DSPy编译触发方式 | 手动+自动 | **自动为主** | 自动为主 | 减少人工干预 |
| D-035 | 固化通知方式 | 晨报汇总 | **仅核心资产飞书** | 仅核心资产 | 减少噪音 |

### 5.2 M06 设计决策

| # | 决策项 | 选项A | 选项B | 推荐 | 依据 |
|---|--------|-------|-------|------|------|
| D-036 | L1保留token数 | 8k | **10k** | 10k | 保留足够上下文 |
| D-037 | L4提纯频率 | 每日 | **每周** | 每周 | 算力成本考量 |
| D-038 | 质量断路器阈值 | 20分 | **30分** | 30分 | 过滤噪音 |
| D-039 | 视觉帧保留策略 | 全量 | **单帧活跃** | 单帧活跃 | 防止Token爆炸 |
| D-040 | Dreaming晋升门槛 | 75分 | **80分** | 75分 | 保证MEMORY.md质量 |

---

## 六、验收标准清单

### 6.1 M09 验收标准

| 层级 | 验收项 | 验收条件 | 验证方法 |
|---|---|---|---|
| Layer1 | 任务类型识别 | 9种类型识别准确率≥85% | 测试集验证 |
| Layer1 | P1-P6组装 | P1不可覆盖·P6兜底 | 单元测试 |
| Layer2 | LLM-Judge评分 | 评分维度完整输出 | 评分结果检查 |
| Layer2 | 执行轨迹 | 片段+分+token+失败原因全记录 | 日志审查 |
| Layer3 | 反馈捕获 | 飞书负面关键词捕获率≥90% | 模拟测试 |
| Layer4 | GEPA进化 | 夜间自动执行6步 | 观察日志 |
| Layer4 | DSPy编译 | 三种触发条件响应 | 模拟触发 |
| Layer5 | 资产固化 | 四级分级+晋升机制 | 资产状态检查 |
| 全局 | 集成测试 | M10→M09→M07联动 | E2E测试 |

### 6.2 M06 验收标准

| 层级 | 验收项 | 验收条件 | 验证方法 |
|---|---|---|---|
| L1 | ReMe压缩 | 90k触发·保留10k+摘要 | 压测验证 |
| L1 | 矛盾检测 | 矛盾标记UNVERIFIED | 注入矛盾测试 |
| L2 | 跨会话召回 | F1≥0.6 | 基准测试 |
| L3 | 降token效果 | 降token≥70% | 对比测试 |
| L3 | 混合检索 | BM25+RRF融合 | 检索测试 |
| L4 | GraphRAG提纯 | 00:30-06:00执行 | 定时日志 |
| L4 | 实体关系 | 三元组格式输出 | 输出检查 |
| L5 | 视觉锚定 | Single-Frame-Active | GUI任务测试 |
| Pipeline | 七阶段管线 | 全链路通过 | 集成测试 |

---

## 七、风险登记与缓解

| 风险ID | 风险描述 | 概率 | 影响 | 缓解措施 |
|--------|----------|:---:|:---:|----------|
| R-01 | M09五层架构过于复杂，交付延期 | 高 | 高 | Week1-2聚焦Layer1-3，后续分批 |
| R-02 | DSPy MIPROv2编译算力成本超预算 | 中 | 高 | 设置每日编译上限$1.5 |
| R-03 | M06 GraphRAG依赖外部服务不可用 | 中 | 中 | 先用简化版Mem0替代 |
| R-04 | PostToolUse管线性能瓶颈 | 中 | 中 | 异步执行+电路断路器 |
| R-05 | 两模块同时开发资源分散 | 中 | 低 | Week1-4先M09，Week5-6后M06 |

---

*本计划基于 2026-04-14 M09(655行)+M06(665行)设计文档深度分析编制*
*下一步: 待用户确认设计决策点后启动施工*
