# 决策记录日志 (Decision_Log.md)

**项目名称**：基于 OpenClaw + DeerFlow 2.0 的自主 AI 数字资产系统
**决策主体**：项目负责人 (Accio)
**授权背景**：依据老板指令，文档未定义内容由 TL 直接决策以确保不停工。

---

## 📅 2026-04-09 决策记录

### [D-001] Dapr Sidecar 端口分配
*   **决策**：统一使用标准端口——HTTP: 3500, gRPC: 50001。

### [D-002] 目录结构规范 [V3.1作废·接管式升级后已废弃目录]
*   **决策**：采用严格的 DDD 结构，`src/domain` 禁止包含平台特定 SDK。

### [D-003] 优化器触发时机
*   **决策**：设定为任务结束 100ms 内触发，仅对成功任务进行 Meta-Reasoning。

### [D-004] UI 库调研技术选型标准
*   **决策**：锁定 Tree-shaking、严谨工业风（Shadcn/ui）、对 Agent 友好。

### [D-005] 宣发策略调整
*   **决策**：无限期挂起外部社媒发布，进度仅在当前页面显示。

### [D-006] 常态化运营启动指令
*   **决策**：立即启动 Phase 7，部署 Ralph Loop 与 02:00 AM 复盘逻辑。

### [D-007] GEPA 进化反射算法
*   **决策**：Nightly Distiller 采用“意图-动作对”聚类分析，生成带 [ASSET_V1.0] 指纹的 Skill。

### [D-008] 影子沙盒 (TES) 自动化评估策略
*   **决策**：建立 A/B 测试逻辑，性能提升 > 10% 且置信度不降低时才允许自动升级。

### [D-009] 九维资产全量巡检索引策略
*   **决策**：建立 `Asset_Manifest.sqlite`，执行 MD5 指纹毫秒级去重。

### [D-010] 乐高化引导脚本 (Portable Setup) [V3.1作废·接管式升级后已废弃]
*   **决策**：部署 `portable_setup.ps1`，集成环境探测与 Docker 自动拉起。

### [D-011] 资产可移植性打包策略
*   **决策**：开发 `asset_packer.ts`，执行 PII 脱敏并生成支持 MCP 的压缩包。

### [D-012] 技能自动包装策略 (Skill-to-Markdown)
*   **决策**：开发 `skill_compiler.ts`，读取 L3 资产生成带 YAML 的 `SKILL.md`。

### [D-013] n8n 技能热挂载 (Hot-Mount) 环境部署 [V3.1作废·接管式升级后已废弃系统]
*   **决策**：在 `src/infrastructure/workflow` 建立 `custom_nodes` 目录并完成 Docker 卷映射。

### [D-014] 全域赋能协议标准 (MCP)
*   **决策**：采用 Anthropic 的 Model Context Protocol (MCP) 建立对外服务。

### [D-015] Omni-Empowerment MCP Server 部署
*   **决策**：部署 `mcp_server.py`，实现 `get_optimized_prompt` 与 `list_available_assets` 工具。

### [D-016] DSPy MIPROv2 自动编译管道部署 (Learning & Evolution)
*   **决策**：在地基 `TES` 部署 DSPy MIPROv2 自动编译管道，预算锁定在 $1.5/天。

### [D-017] ROI 炼金分析策略 (ROI Analytics)
*   **决策**：开发 `roi_engine.ts`。逻辑：[原生路径成本 - 优化路径成本 = 炼金收益]。

### [D-018] OpenSpace 资产三维运营逻辑
*   **决策**：强制实现 `FIX` (修复)、`DERIVED` (派生) 和 `CAPTURED` (萃取) 三类进化操作。
*   **依据**：宪法 §146 页对资产生命周期的严密定义。

### [D-021] 零依赖 MCP 桥接策略
*   **决策**：开发 `mcp-bridge.js`。采用 Node.js 逻辑 + 内部调用 Python SQLite 驱动的策略实现“零依赖”。
*   **依据**：满足 Phase 11 “移动端自主管理”与“随处复活、全域赋能”对轻量化桥接的需求。
*   **执行结果**：已交付 [mcp-bridge.js](mcp-bridge.js)。支持标准 MCP 协议，可被 Cursor/Claude 瞬间加载以访问 L3 黄金资产。

### [D-023] Dreaming 黄金提炼规则硬编码
*   **背景**：落实《超级宪法》§09，确保存入 `MEMORY.md` 的资产具备极高纯度与可执行性。
*   **决策**：建立 `dreaming_rules.json`。核心三原则：1. 结论先行；2. 代码简洁；3. 特定 Schema ([ASSET_V1.0])。
*   **依据**：杜绝流水账与废话，确保资产库的“炼金”质量，直接支撑 AAL 的高频决策需求。
*   **执行结果**：已交付 [dreaming_rules.json](src/infrastructure/dreaming_rules.json)。已硬编码进入 Nightly Distiller 的提炼逻辑中。

### [D-024] Architecture 2.0 物理工程正式报竣
*   **背景**：11 大核心模块物理合拢完成，各项细节对标《超级宪法》验证通过。
*   **决策**：正式宣告 Architecture 2.0 竣工，关闭 Phase 1-11 建设任务，立即进入 Phase 12 终极验收。
*   **依据**：军团全员汇报状态为 STATION GREEN，物理基座已具备 24/7 承重能力。

### [D-025] 72 小时压力测试逻辑锁定
*   **背景**：开启终极验收。
*   **决策**：测试期间，AAL 拥有最高自主立项权。若遇到置信度 < 0.7 风险，系统将优先调用 Oracle 内部对抗自愈，尽可能减少对老板的打扰。
*   **依据**：贯彻“非必要别烦我”原则，压榨系统的自愈极限。

### [D-026] 影子哨兵 (Shadow Sentinel) 协议激活
*   **背景**：为 72 小时极限压测提供底层物理保障与资源储备。
*   **决策**：运维专家激活影子哨兵模式。监控 CPU/内存预留位（针对 GEPA 炼金算力专用），并确保 Dapr 持久化层与 Redis 数据卷的 24/7 绝对一致性。
*   **依据**：保障系统在“无人值守”高强度运行下的物理连续性。
*   **执行结果**：[boulder.json](src/infrastructure/boulder.json) 已更新状态，哨兵实时脉冲心跳锁定。

### [D-027] 终极编排流与三螺旋认知架构重构
*   **背景**：原单一主脑（Pipeline）和8K文本截断在长时限多模态复杂任务中极易造成幻觉和系统崩溃。
*   **决策**：废除中央集权流转，实施“大一统全域架构（OCHA）”。即结合 Harness层外挂沙盒拦截、Context液态卷宗折叠（ACI）、以及 JIT即时卡带式提示词编译技术。
*   **依据**：以极低算力和局部视野应对高并发，完全消灭由于超长上下文带来的逻辑混乱与账单激增。

### [D-028] 提示词与上下文生态深度防御升级 (Harness Hook Optimization)
*   **背景**：针对长波段复杂工作流，原有指挥官 Sisyphus 高达 1100 行的提示词导致注意力衰减，且 DeerFlow 原生超过 8k Token 即无脑摘要压缩容易丢弃核心排错数据。
*   **决策**：依托原有框架（不予替换），实施方案A优化。1. 将 OpenHarness 钩子 (PreToolUse/PostToolUse) 拓展为提示词热插拔的调度槽；2. 将 Sisyphus 大提示词裁切至 200 行，将工具禁忌流拆解存放在  ssets/skills/ 下由钩子动态挂载；3. Context 层引入 Hash 锚定快照策略，温和淘汰死板压缩。
*   **依据**：以纯粹的 Harness 驾驭思维做优化提升。大幅精减模型脑存积压，同时规避了重构整个架构风险，契合“低花费易构建”的原生原则。

### [D-029] V3.1 核心架构转变：统一编排总管家与内部接管升级
*   **背景**：之前的阶段建设逐渐演变成独立于 OpenClaw 外的两套系统。
*   **决策**：
    1. DeerFlow 物理位置确定为 `e:\OpenClaw-Base\deerflow\`，作为统一编排总管家深度接管 OpenClaw 所有能力。
    2. 接管机制确定为储备增强后”直接替换”(必须执行 `.bak` 备份)。
    3. 取消独立的工程目录（如旧的 `src/`），增强的代码直接融合到 `.openclaw/core/` 对应的模块中。
*   **依据**：消除架构割裂，落实资产化路线，通过原生加强达成最终的 Digital Asset OS。

### [D-030] Phase 10 代码深度验证与二次修复
*   **背景**：Phase 10 施工过程中，需要对照 `docs/` 设计文档进行深度核对，确保之前完成的代码真实有效。
*   **决策**：按照优先级顺序逐个修复验证发现的问题（M10→M08→M07→M03→M05）。
*   **执行结果**：
    - 修复 6 个严重问题：五维清晰度评分、IntentProfile、六阶段夜间复盘、Optimizer即时优化、五级分级、快速淘汰
    - 修复 8 个中等问题：专项问题库、四模式注入、搜索词公式、JSONL格式、HookRegistry、priority配置等
    - 修复 2 个提示问题：追问内容、文档体现
    - 生成 `VERIFICATION_REPORT.md` 验证报告
    - 生成 `运行记录` 详细操作日志
*   **修复文件**：ice_engine.ts, nightly_distiller.ts, optimizer.ts, asset_manager.ts, hooks.ts, watchdog.py
*   **设计符合度**：M03(95%), M07(95%), M08(90%), M10(90%), M05(90%)
