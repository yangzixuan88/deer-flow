# DeerFlow 核心决策日志 (Decision Log)

本文档旨在记录系统在演进过程中的关键架构选型与逻辑决策，确保改动有迹可循。

---

## [2026-04-12] 决策 001：开启 Phase 3 建设

### 背景 (Context)
系统已完成 Phase 1 (基础设施) 与 Phase 2 (多模态与飞书稳定化)。
大主管 (Lead Agent) 当前采用单体架构，记忆存储为本地文件（JSON），生成资产存储于本地磁盘无 UI 查看。

### 决策内容 (Decision)
1. **启动 Phase 3** 建设，目标是提升系统的企业级能力。
2. **待选方案**：
   - A. 向量化记忆 (Qdrant Sync): 引入语义检索能力。
   - B. 多智能体分工 (Swarm/LangGraph): 实现专业化角色。
   - C. 资产可视化门户 (Gallery): 建立 Web 预览端。

### 影响 (Consequences)
- 需要引入新的数据库依赖 (Qdrant) 或前端框架 (Next.js)。
- 系统的 LangGraph 拓扑结构可能会变得更加复杂。

---

## [2026-04-12] 决策 002：多模态工具链路选型

### 背景
用户需要本地创作能力，但 Kokoro TTS 等本地模型体积过大且显存压力高。

### 决策
- 优先接入 **MiniMax** 的图像、音频、音乐、视频全系列 API。
- 采用 **异步状态轮询** 处理长周期的视频生成任务。
- 所有生成结果强制落地到 `deerflow/workspace/media` 维护资产主权。

---

## [2026-04-13] 决策 003：Qdrant 向量记忆实施细节

### 背景
系统需要从简单的 JSON 事实记录进化为支持语义检索的长短期记忆系统，以实现长周期的 RAG 能力。

### 决策内容 (Decision)
1. **API 优先**：Embedding 转换目前锁定为**在线 API**（如 OpenAI/DeepSeek 等），确保精度与响应速度。
2. **架构前瞻**：实现 `EmbeddingProvider` 抽象层，为未来接入 `fastembed` 等本地模型预留接口。
3. **存储隔离**：初期采用 **Local Path** 模式（基于本地文件夹存储），无需独立 Docker 服务，便于敏捷开发。
4. **延迟迁移**：在向量库模块完全开发完成并通过 E2E 测试前，**禁止**将旧的 `memory.json` 数据转移至向量库，确保生产环境稳定性。

### 影响 (Consequences)
- `MemoryMiddleware` 将新增 `before_agent` 逻辑。
- 引导提示词 (Prompt) 将引入新的语义上下文注入块。
- Qdrant 本地持久持久性文件将存储在 `backend/data/qdrant` 路径下。
