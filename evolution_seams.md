# OpenClaw · 演进接口清单（Evolution Seams）

**版本**：R69
**日期**：2026-04-21
**性质**：已降级模块的开放式收口记录 — 不进入主链，但保留未来演进入口
**与 baseline.md 的分工**：baseline.md = 当前系统事实，evolution_seams.md = 已降级模块的重接路径

---

## 概述：收口原则

> **收口 ≠ 封死**。已降级模块不是"废弃删除"，而是"当前条件不满足、接口已保留、未来可重接"。

| 状态标签 | 含义 | 主链依赖 | smoke 覆盖 |
|---|---|---|---|
| `INACTIVE_SERVICE` | 服务/容器在跑，但当前无主链调用 | 无 | 否 |
| `ABANDONED` | 代码/配置保留，当前无激活路径 | 无 | 否 |
| `FUTURE_COPROCESSOR_ORCHESTRATION` | 架构预留，当前无触发条件 | 无 | 否 |

---

## 1. n8n（INACTIVE_SERVICE）

**为什么当前不进主链**：n8n workflow 自动化层与 DeerFlow M10/M11 自驱 governance 架构存在功能重叠。n8n 是外部触发的流程编排，DeerFlow governance 是内部预执行路由。当前无触发条件。

**未来最小重接条件**：
1. 有明确的跨系统 workflow 编排需求（DeerFlow 无法自驱完成的外部系统联动）
2. n8n workflow 作为 DeerFlow 外部工具被调用，而非 DeerFlow 依赖 n8n 触发
3. governance 边界已划定（DeF 内部决策，n8n 外部执行）

**当前保留的接口契约**：
- `deerflow-n8n` 容器在 docker-compose 中继续存在（端口 5678）
- n8n REST API/webhook 接口契约不变
- `/api/channels/` 扩展点可接入新的 channel type（未来可扩展 n8n channel）

**状态标签**：`INACTIVE_SERVICE` — 容器在跑，但主链无引用

---

## 2. Dify（ABANDONED）

**为什么当前不进主链**：Dify 提供低代码 LLM 应用平台（知识库 + 流程编排），与 DeerFlow M08 LearningSystem 存在功能重叠但技术路线不同。M08 已实现内部 learning capability，Dify 无接入价值。

**未来最小重接条件**：
1. 有明确的外部知识库检索需求（Dify RAG 作为 DeerFlow 的外部 tool）
2. Dify 作为独立 LLM 应用平台与 DeerFlow 并列运行
3. 有明确的知识库同步机制（Dify knowledge ↔ DeerFlow memory）

**当前保留的接口契约**：
- Dify 是标准 REST API 服务，任何时候可通过标准 API tool 接入
- 无特殊接口依赖，重接时只需实现 tool wrapper
- 配置和密钥在 `.env` 中（`DIFY_*` 变量，如已清除则需重建）

**状态标签**：`ABANDONED` — 无主链引用，无激活路径

---

## 3. Qdrant（INACTIVE_SERVICE）

**为什么当前不进主链**：Qdrant 是向量数据库，用于 RAG 语义检索。DeerFlow 当前没有激活的 RAG pipeline（M08 learning 是行为学习，不是知识库检索）。无向量检索需求时，Qdrant 只是资源消耗。

**未来最小重接条件**：
1. 有明确的 RAG 知识库检索需求（文档 Q&A、语义搜索等）
2. DeerFlow M08 无法满足该知识库场景
3. Qdrant 作为外部向量库被 DeerFlow 的 tool 调用（标准向量 API）

**当前保留的接口契约**：
- `deerflow-qdrant` 容器继续在 docker-compose 中存在（端口 6333/6334）
- Qdrant 标准 REST + gRPC 接口契约不变
- 重接时只需实现标准向量检索 tool wrapper

**状态标签**：`INACTIVE_SERVICE` — 容器在跑，但主链无向量需求

---

## 4. Bytebot（INACTIVE_SERVICE）

**为什么当前不进主链**：`bytebot_sandbox_mode.py` 的 `CAPABILITY SHAPE` 注释已完整记录：
> "CAPABILITY SHAPE ONLY — no bytebotd daemon, bytebot-ui, or bytebot-agent"
> "启用条件: 修复 claude_code_route() 中的 async/sync 混用问题"
Bytebot 的桌面自动化能力需要完整的 `bytebotd` daemon 在跑，当前未启动。

**未来最小重接条件**：
1. `bytebotd` Docker daemon 启动并监听 `localhost:8765`
2. `claude_code_route()` 的 `_route_bytebot_sandbox()` async/sync 问题修复
3. Bytebot desktop daemon 容器（Xvfb + XFCE4 + nut-js）正常运行

**当前保留的接口契约**：
- `bytebot_sandbox_mode.py` 完整保留
- `BytebotCapability` schema（name/type/risk_level）完整
- capability map 包含 `bytebotd_docker`、`docker_isolation`、`base_url` 等完整配置结构
- 重接时无需重新发明，只需满足条件后启用分支

**状态标签**：`INACTIVE_SERVICE` — 代码完整，capability shape 文档化，最佳保留实践

---

## 5. M04 TypeScript（ABANDONED）

**为什么当前不进主链**：TypeScript registry 系统（`m04/registry_db.py` + `registry_manager.py`）需要额外类型注解体系和构建系统，DeerFlow Python-first 架构下 ROI 不足。M04 的类型安全模块注册价值在 Python 动态类型体系下无可量化收益。

**未来最小重接条件**：
1. 有明确的 TypeScript 端侧 Agent 需要接入 DeerFlow 主链
2. 该 Agent 的类型安全需求无法通过 `typing` + `pydantic` 替代
3. 构建系统支持 TypeScript → Python 类型对齐

**当前保留的接口契约**：
- `m04/registry_db.py` 和 `m04/registry_manager.py` 完整保留
- `RegistryManager` 类接口不变（`__init__`, `register`, `get`, `list` 等方法）
- Future 重接只需实现具体方法，无需重新设计接口

**状态标签**：`ABANDONED` — 代码保留，无构建需求

---

## 6. Coprocessor Governance（FUTURE_COPROCESSOR_ORCHESTRATION）

**为什么当前不进主链**：`governance_bridge.py` 的 `routing_policy` 已预置 `coprocessors_subordinate` 路径，但当前主链没有活跃的 coprocessor 实例。`agent_s_adapter.py` 和 `bytebot_sandbox_mode.py` 是 capability shape 文档，不是运行时模块。

**未来最小重接条件**：
1. 有明确的 coprocessor 需要接入 governance 路由（不通过 Claude Code 直接执行的外部工具）
2. coprocessor 自身具备 governance 接口契约（allow/block/escalate/veto/modify）
3. `routing_policy` 配置已更新为包含该 coprocessor

**当前保留的接口契约**：
- `governance_bridge.py` 中的 `MODIFY = "modify"` 和 `decision: str  # allow | block | escalate | veto | modify` 接口不变
- `agent_s_adapter.py` 和 `bytebot_sandbox_mode.py` 作为 capability shape 文档保留
- `evolvable_surface` 列表中已包含 `coprocessors_for_claude_code`

**状态标签**：`FUTURE_COPROCESSOR_ORCHESTRATION` — 接口预置，当前无实例

---

## 7. 非飞书 Channels（INACTIVE — 未接入）

**为什么当前不进主链**：`channels/` 目录下有 `discord.py`、`telegram.py`、`wechat.py`、`wecom.py`、`slack.py`，但从未通过这些 channel 收到消息。无接入机会。

**未来最小重接条件**（以 discord 为例）：
1. Discord Bot Token 已配置且在 `.env` 或 config.yaml 中
2. Discord 的 Event Subscription 已配置（类似 Feishu WS）
3. `channels/manager.py` 的 channel registry 已注册该 channel type

**当前保留的接口契约**：
- 所有 channel 文件保留标准 `ChannelAdapter` 接口
- `channels/base.py` 中的 `InboundMessage`/`OutboundMessage` schema 不变
- 任何新 channel 接入只需实现 adapter + 配置，无需修改 manager

**状态标签**：`INACTIVE — 未接入` — 代码存在，无触发机会

---

## 8. perception/（INACTIVE — 无触发条件）

**为什么当前不进主链**：`perception/audio_codec.py` + `vision_capture.py` 提供音视频处理能力，但当前系统无音视频输入触发条件（没有用户上传音视频、没有 microphone 输入）。

**未来最小重接条件**：
1. 有音视频输入来源（用户上传 / microphone capture）
2. `perception/` 模块被主链中某处引用（当前无引用）
3. 处理结果注入主链的 message  pipeline

**当前保留的接口契约**：
- `audio_codec.py` 和 `vision_capture.py` 完整保留
- 接口契约未经验证（无调用方），重接时需要先确认接口兼容性

**状态标签**：`INACTIVE — 无触发条件` — 代码保留，无引用

---

## 9. 降级模块池汇总

| 模块 | 状态标签 | 代码保留 | 容器保留 | 接口契约 | 重接条件文档化 |
|---|---|---|---|---|---|
| n8n | INACTIVE_SERVICE | — | ✅ :5678 | REST API | ✅ 需补充 |
| Dify | ABANDONED | — | ❌ | REST API | ✅ 需补充 |
| Qdrant | INACTIVE_SERVICE | — | ✅ :6333 | REST+gRPC | ✅ 需补充 |
| Bytebot | INACTIVE_SERVICE | ✅ 完整 | ⚠️ 需启动 | Capability schema | ✅ 最佳 |
| M04 TypeScript | ABANDONED | ✅ 完整 | — | RegistryManager | ✅ 需补充 |
| Coprocessor Gov | FUTURE | ✅ 接口预置 | — | allow/block/veto | ✅ 需补充 |
| 非飞书 channels | INACTIVE | ✅ 完整 | — | ChannelAdapter | ✅ 需补充 |
| perception/ | INACTIVE | ✅ 完整 | — | 未验证 | ❌ 未记录 |

---

## 10. 维护原则

**如何避免"已降级"被误解为"可以删除"**：
- 所有降级模块代码完整保留，不做删除
- 状态标签统一：`INACTIVE_SERVICE` / `ABANDONED` / `FUTURE_COPROCESSOR_ORCHESTRATION`
- 本文档作为唯一演进入口，后续任何重接从这里查入口

**如何避免"保留代码"被误解为"正在运行"**：
- smoke 不覆盖任何降级模块
- baseline.md 明确列出"已降级模块（不纳入 Smoke）"
- 运行态与设计态分离：代码存在 ≠ 正在执行

**如何避免"当前不投入"被误解为"永不用"**：
- 每个模块的未来重接条件已记录
- 本文档作为"演进入口清单"持续维护
- 满足重接条件后，可直接激活，不需要重新发明接口
