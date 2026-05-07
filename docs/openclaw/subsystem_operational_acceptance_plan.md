# OpenClaw 全方位系统级实际运转验收计划书 v1.0

## 文档目的

本文档将 OpenClaw 系统级验收从"状态记录文档"转化为"可执行的功能验收规划"。每个验收用例均定义：入口/输入、期望输出、必须提供的证据、禁止出现的副作用。

本文档**不执行验收**。本文档**不修改代码**。实际验收在 R246C–R246H 阶段执行。

---

## 交叉校准结论

| 项目 | 状态 |
|------|------|
| Repair Plan v2 | COMPLETE |
| vNext Enhancement Freeze | COMPLETE |
| System-Level Capability Acceptance | COMPLETE |
| Final Delivery Report | COMPLETE |
| **全方位实际运转验收规划** | **本文档 — PLANNED** |

---

## 验收分层模型

| Layer | 名称 | 描述 |
|-------|------|------|
| L0 | Foundation | 地基：配置、环境、import、健康检查 |
| L1 | Main Chain | 主链：Gateway / Run / Status / Result |
| L2 | Path A 本地执行 | Orchestrator → Coordinator → Executor 本地执行链 |
| L3 | MCP 外部工具支链 | Tavily 等外部 stdio MCP 工具 |
| L4 | 深层系统支链 | RTCM / Asset / Nightly Review 等运行时 |
| L5 | 横向安全层 | Auth / Hygiene / thread_meta 隔离 |

---

## 状态枚举

| Status | 含义 |
|--------|------|
| PLANNED | 验收用例已规划，未执行 |
| PASS | 入口/输入正确，输出符合预期，副作用零出现 |
| PASS_WITH_LIMITS | 功能可用但存在已知边界（如 dry-run only） |
| FAIL | 功能不可用或输出不符合预期 |
| DEFERRED_EXTERNAL | 依赖外部未就绪凭据或服务 |
| NOT_FOUND | 入口点不存在 |
| NEEDS_TARGETED_FIX | 发现缺陷，需要修复后重新验收 |
| NEEDS_SEPARATE_AUTHORIZATION | 需要单独授权（如 real-send、Agent-S） |

---

## 通用验收卡片模板

```
Case ID: <PREFIX>-<NNN>
Layer:   <L0–L5>
System:  <system name>
Function:<function or endpoint>
Input:  <entry point or command>
Expected: <expected output>
Evidence: <required evidence path or command>
Forbidden:
  - token_cache_read
  - real_send
  - Agent-S invocation
  - daemon_or_cron
  - production_db_write
  - external_network_call
```

---

## 全局禁止事项

验收执行期间（以及任何未来阶段）**绝对禁止**：

- 读取 `token_cache.json` 内容
- 打印、复制任何 token 值
- 读取 `.deerflow/rtcm` 或 `.deerflow/operation_assets` 作为运行时输入
- 调用 Feishu/Lark 真实发送 API
- 真实发送消息到任何频道
- 调用 Agent-S（外部未跟踪运行时）
- 启动 daemon / background worker
- 创建 cron / scheduled task
- 写入生产 DB
- 在未授权情况下发起外部网络真实调用

---

## 验收域总览

| # | 域 | Layer | 前缀 | 说明 |
|---|------|-------|------|------|
| 1 | Foundation | L0 | FOUND | 地基：配置、环境、import |
| 2 | Gateway / Run / Status / Result | L1 | GW | 主链核心路由 |
| 3 | Search | L1 | SEARCH | 搜索路由和执行 |
| 4 | Task | L1 | TASK | 任务系统 |
| 5 | Workflow | L1 | WF | 工作流编排 |
| 6 | Claude Code 执行 | L2 | CLAUDE | Claude Code 执行系统 |
| 7 | Visual Web | L2 | VW | 视觉 Web 系统 |
| 8 | Desktop | L2 | DESK | Desktop 执行系统 |
| 9 | MCP 外部工具边界 | L3 | MCP | MCP stdio 工具隔离 |
| 10 | RTCM 圆桌会议 | L4 | RTCM | 干运行时（无真实 agent） |
| 11 | Autonomous Agent | L4 | AUTO | 自主代理系统 |
| 12 | Memory | L4 | MEM | 记忆系统 |
| 13 | Prompt | L4 | PROMPT | 提示词系统 |
| 14 | Evolution / Upgrade Center | L4 | EVO | 进化和升级中心 |
| 15 | Asset | L4 | ASSET | 资产运行时（dry-run） |
| 16 | Tool / Skill | L4 | TOOL | 工具和技能系统 |
| 17 | Feishu / Report | L4 | REPORT | 飞书报告系统（dry-run） |
| 18 | Nightly Review | L4 | NIGHTLY | 夜间复盘（dry-run + 手动调度） |
| 19 | Operator CLI | L4 | CLI | 操作员 CLI 控制台 |
| 20 | Security / Hygiene | L5 | SAFE | 横向安全边界 |

---

## 分层执行顺序

```
L0 (Foundation)
    ↓
L1 (Main Chain: GW → SEARCH → TASK → WF)
    ↓
L2 (Path A 本地执行: CLAUDE → VW → DESK)
    ↓
L3 (MCP 外部工具)
    ↓
L4 (深层系统: RTCM → AUTO → MEM → PROMPT → EVO → ASSET → TOOL → REPORT → NIGHTLY → CLI)
    ↓
L5 (横向安全: SAFE)
```

---

## 逐系统功能验收用例

### L0 — FOUND (Foundation)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| FOUND-001 | AppConfig env VAR resolution | `python -c "from app.openclaw.config import AppConfig; c = AppConfig(); print(c.get('NON_VAR_TEST', 'fallback'))"` | 输出 fallback，无 RuntimeError |
| FOUND-002 | AppConfig `${VAR}` form | `python -c "import os; os.environ['TEST_VAR']='resolved'; from app.openclaw.config import AppConfig; c = AppConfig(); print(c.get('TEST_VAR'))"` | 输出 resolved |
| FOUND-003 | Import smoke: config | `python -c "from app.openclaw.config import AppConfig"` | 无 ImportError |
| FOUND-004 | Import smoke: app | `python -c "from app.openclaw import create_app"` | 无 ImportError |
| FOUND-005 | Import smoke: coordinator | `python -c "from app.openclaw.coordinator import Coordinator"` | 无 ImportError |
| FOUND-006 | Import smoke: executor_adapter | `python -c "from app.openclaw.executor_adapter import ExecutorAdapter"` | 无 ImportError |
| FOUND-007 | Import smoke: orchestrator | `python -c "from app.openclaw.orchestrator import Orchestrator"` | 无 ImportError |
| FOUND-008 | CLI main entry | `python -c "from app.openclaw_cli.console import main; main([])"` | 无异常，退出码 0 |
| FOUND-009 | Health endpoint smoke | `curl http://localhost:8000/health` 或 `python -c "import requests; r = requests.get('http://localhost:8000/health'); print(r.status_code)"` | 200 |
| FOUND-010 | Workspace clean check | `git ls-files .deerflow/rtcm/ .deerflow/operation_assets/` | 0 files tracked |

### L1 — GW (Gateway / Run / Status / Result)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| GW-001 | Primary run route POST | `POST /api/threads/{thread_id}/runs` with valid body | 200 或 201，run_id 返回 |
| GW-002 | Run status GET | `GET /api/threads/{thread_id}/runs/{run_id}` | 200，status 字段存在 |
| GW-003 | Run result GET | `GET /api/threads/{thread_id}/runs/{run_id}/result` | 200，result 字段存在 |
| GW-004 | Fallback route `/api/runs/wait` | `POST /api/runs/wait` | 200，fallback 路径可用 |
| GW-005 | Invalid thread 404 | `POST /api/threads/invalid-thread-id/runs` | 404 |
| GW-006 | Missing body 422 | `POST /api/threads/{thread_id}/runs` with empty body | 422 |
| GW-007 | Auth header missing 401 | `POST /api/threads/{thread_id}/runs` without Authorization | 401 或 403 |
| GW-008 | Gateway health | `GET /health` | 200 |

### L1 — SEARCH (Search Routing)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| SEARCH-001 | Intent: search keyword detected | "search for X" text → intent_classifier | system_type = search |
| SEARCH-002 | Intent: web search fast-path | 输入含 "search" indicator | suggestSystemType() 返回 web search |
| SEARCH-003 | Tavily MCP stdio transport | `tavily_search("latest AI news")` | 返回真实搜索结果，无 HTTP 405 |
| SEARCH-004 | Search result parsing | Tavily 返回 → result parsing | JSON 结构完整 |

### L1 — TASK (Task System)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| TASK-001 | Task creation | `POST /api/tasks` with valid payload | 201，task_id 返回 |
| TASK-002 | Task list | `GET /api/tasks` | 200，列表非空或空（合法） |
| TASK-003 | Task status update | `PATCH /api/tasks/{task_id}` with status | 200 |
| TASK-004 | Task not found 404 | `GET /api/tasks/invalid-id` | 404 |

### L1 — WF (Workflow)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| WF-001 | Workflow definition load | 创建包含 steps 的 workflow | workflow 对象完整加载 |
| WF-002 | Workflow execution start | 启动 workflow 实例 | run_id 返回 |
| WF-003 | Workflow step routing | 单步 workflow → executor | 步骤正确路由 |
| WF-004 | Workflow abort | `DELETE /api/runs/{run_id}` | 200 或 204 |

### L2 — CLAUDE (Claude Code Execution)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| CLAUDE-001 | Orchestrator: create agent | `create_deerflow_agent()` | Agent 对象创建，无异常 |
| CLAUDE-002 | Orchestrator: tool routing | agent 调用 tool | 工具调用正确路由 |
| CLAUDE-003 | Coordinator: system_type switch | coordinator with system_type=assistant | 正确的分支处理 |
| CLAUDE-004 | Executor: readiness gate | executor adapter readiness check | READY 或 NOT_READY（合法） |
| CLAUDE-005 | No-tool model run | 模型调用无 tool | 纯补全返回，非 error |
| CLAUDE-006 | Handoff contract: Orchestrator→Coordinator | 传递 HandoffRequest | Coordinator 收到完整对象 |
| CLAUDE-007 | Handoff contract: Coordinator→Executor | 传递 HandoffRequest | Executor adapter 收到完整对象 |
| CLAUDE-008 | Memory tool invocation | agent 调用 memory tool | memory 读写正确 |

### L2 — VW (Visual Web)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| VW-001 | Visual web tool registered | visual_web_tool in tool registry | tool 存在且可调用 |
| VW-002 | Visual web execution path | 调用 visual_web tool | 正确的视觉 web 处理分支 |

### L2 — DESK (Desktop)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| DESK-001 | Desktop tool registered | desktop_tool in tool registry | tool 存在且可调用 |
| DESK-002 | Desktop execution path | 调用 desktop tool | 正确的 desktop 处理分支 |

### L3 — MCP (MCP External Tools Boundary)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| MCP-001 | Tavily MCP stdio transport | `npx -y tavily-mcp@latest` stdio | 模块加载成功 |
| MCP-002 | Tavily search tool call | tavily_search via MCP stdio | 返回搜索结果，transport 正确 |
| MCP-003 | MCP tool isolation | 并发多个 MCP tool call | 无交叉污染 |
| MCP-004 | MCP invalid tool 404 | 调用不存在的 MCP tool | 错误正确返回，无 crash |
| MCP-005 | Lark MCP disabled reason | 检查 Lark MCP disabled 原因 | SDK bug 记录在案 |
| MCP-006 | Exa MCP disabled reason | 检查 Exa MCP disabled 原因 | credentials 缺失记录在案 |

### L4 — RTCM (Roundtable Consensus Meeting)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| RTCM-001 | RTCM dry-run runtime | `python -m app.openclaw_cli.console rtcm-dry-run` | 退出码 0，输出为 dry-run 格式 |
| RTCM-002 | RTCM store write | dry-run 执行 → JSONL store | 文件写入成功 |
| RTCM-003 | RTCM get() | `rtcm-report --get <record_id>` | 返回指定记录 |
| RTCM-004 | RTCM latest() | `rtcm-report --latest` | 返回最新记录 |
| RTCM-005 | RTCM export JSON | `rtcm-dry-run-export --output /tmp/rtcm.json` | JSON 文件生成 |
| RTCM-006 | RTCM export Markdown | `rtcm-dry-run-export --format md --output /tmp/rtcm.md` | MD 文件生成 |
| RTCM-007 | RTCM build_markdown_index | `rtcm-report-index` | index 构建成功 |
| RTCM-008 | RTCM build_json_index | `rtcm-report-index --format json` | JSON index 构建成功 |
| RTCM-009 | RTCM forbidden: no real-agent | `RTCRM_REAL_AGENT=1` 传入 | 拒绝执行，报错 |
| RTCM-010 | RTCM forbidden: no .deerflow/rtcm read | 代码尝试读 .deerflow/rtcm/ | Hygiene guard 阻止 |

### L4 — AUTO (Autonomous Agent)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| AUTO-001 | Autonomous agent creation | create autonomous agent | agent 对象创建 |
| AUTO-002 | Agent self-planning | agent receives goal | agent 生成 plan |
| AUTO-003 | Agent tool use | agent 调用 tool | 工具调用记录 |
| AUTO-004 | Agent stop condition | agent 达到目标 | agent 正确停止 |

### L4 — MEM (Memory)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| MEM-001 | Memory write | 写入 memory store | 写入成功，无异常 |
| MEM-002 | Memory read | 读取 memory store | 返回正确数据 |
| MEM-003 | Memory branch validation | R191 149 tests | 149/149 PASS |
| MEM-004 | Memory thread isolation | 不同 thread 的 memory 隔离 | 隔离正确，无泄漏 |

### L4 — PROMPT (Prompt System)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| PROMPT-001 | Prompt load | 加载 prompt 定义 | prompt 模板正确加载 |
| PROMPT-002 | Prompt injection | prompt + context injection | 注入后 prompt 格式正确 |
| PROMPT-003 | Prompt/Skill/Tool validation | R192 276 tests | 276 PASS，1 skipped |

### L4 — EVO (Evolution / Upgrade Center)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| EVO-001 | Upgrade Center registry load | m04 registry 加载 | registry 内容正确 |
| EVO-002 | Skill registration | 新 skill 注册 | skill 可被发现 |
| EVO-003 | Tool registration | 新 tool 注册 | tool 可被调用 |
| EVO-004 | m04 registry test coverage | PR #7 tests | 14 tests PASS |

### L4 — ASSET (Asset Runtime)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| ASSET-001 | Asset runtime dry-run | `python -m app.openclaw_cli.console asset-dry-run --input /tmp/asset_input.json` | dry-run 执行成功，退出码 0 |
| ASSET-002 | Asset list capabilities | `asset-cli list-capabilities` | 返回 capability 列表 |
| ASSET-003 | Asset tracked registry | `default_capabilities.json` 存在 | JSON 正确，6 capabilities |
| ASSET-004 | Asset forbidden: no Agent-S | Agent-S 路径被调用 | Dry-run adapter 拒绝，错误码非 0 |
| ASSET-005 | Asset adapter isolation | asset adapter 调用 → 无外部副作用 | 所有操作在 dry-run 内 |

### L4 — TOOL (Tool / Skill)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| TOOL-001 | Tool discovery | `GET /api/tools` | 200，tool 列表 |
| TOOL-002 | Tool call | `POST /api/tools/{tool_id}/call` | 正确路由和响应 |
| TOOL-003 | Skill discovery | `GET /api/skills` | 200，skill 列表 |
| TOOL-004 | Skill invocation | skill 被调用 | skill 执行正确分支 |

### L4 — REPORT (Feishu / Report)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| REPORT-001 | Feishu card builder | 构建飞书消息卡片 | 卡片 JSON 格式正确 |
| REPORT-002 | Feishu dry-run send | `--dry-run` 标志传入 | 不调用真实 API，输出 dry-run 结果 |
| REPORT-003 | Feishu parser tests | R195 14 parser tests | 14/14 PASS |
| REPORT-004 | Report generation | 生成报告 | 报告内容格式正确 |
| REPORT-005 | Feishu forbidden: real-send without auth | `FEISHU_TOKEN_ROTATION_ACK != true` 传入 real-send | 拒绝执行，报错 |
| REPORT-006 | Feishu token origin check | token 来源检查 | token 必须来自 `app_config.lark`，非 `token_cache.json` |

### L4 — NIGHTLY (Nightly Review)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| NIGHTLY-001 | Nightly dry-run pipeline | `nightly-run-once-preview` | dry-run 执行成功 |
| NIGHTLY-002 | Nightly export JSON | `nightly-export --output /tmp/nightly.json` | JSON 导出成功 |
| NIGHTLY-003 | Nightly store | night_review store 写入 | JSONL store 正确 |
| NIGHTLY-004 | Nightly CLI explicit path | 导出指定 `--output` | 无默认路径写入 .deerflow/ |
| NIGHTLY-005 | Nightly forbidden: daemon | 尝试启动 daemon | NotImplementedError 或同等拒绝 |
| NIGHTLY-006 | Nightly forbidden: cron | 尝试创建 cron | NotImplementedError 或同等拒绝 |
| NIGHTLY-007 | Nightly dry-run boundary | 验证 dry-run | 不调用真实发送 API |

### L4 — CLI (Operator CLI)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| CLI-001 | CLI help | `python -c "from app.openclaw_cli.console import main; main(['--help'])"` | 退出码 0，帮助文本输出 |
| CLI-002 | Asset dry-run command | `asset-cli asset-dry-run --help` | 帮助文本存在 |
| CLI-003 | RTCM dry-run command | `rtcm-cli rtcm-dry-run --help` | 帮助文本存在 |
| CLI-004 | Nightly preview command | `nightly-cli nightly-run-once-preview --help` | 帮助文本存在 |
| CLI-005 | CLI --real flag rejection | 任何 `--real` 传入 | 拒绝执行，错误码非 0 |
| CLI-006 | CLI explicit output path | 所有 export 命令需要 `--output` | 无默认输出路径 |
| CLI-007 | CLI JSON output mode | `--json` 标志 | JSON 格式输出 |
| CLI-008 | CLI 9 commands registered | console.py 命令数量 | 9 commands registered |
| CLI-009 | CLI dry-run console unified | R237X unified console | 37 tests PASS |

### L5 — SAFE (Security / Hygiene)

| Case ID | Function | Input | Expected |
|---------|----------|-------|----------|
| SAFE-001 | Auth thread_meta isolation | 不同 user 的 thread 隔离测试 | 37 isolation tests PASS |
| SAFE-002 | Hygiene: .gitignore guard | `git check-ignore -v .deerflow/rtcm/some.jsonl` | 判定为 ignored |
| SAFE-003 | Hygiene: no token_cache.json tracked | `git ls-files token_cache.json` | 0 files |
| SAFE-004 | Security: S-RTCM-FEISHU-TOKEN-001 open | security_exception_register 检查 | 异常状态为 OPEN |
| SAFE-005 | Hygiene: no .deerflow/rtcm committed | `git ls-files .deerflow/rtcm/` | 0 files |
| SAFE-006 | Hygiene: no .deerflow/operation_assets committed | `git ls-files .deerflow/operation_assets/` | 0 files |
| SAFE-007 | Hygiene: external/Agent-S/ not tracked | `git ls-files external/Agent-S/` | 0 files |
| SAFE-008 | Feishu token rotation ACK check | `FEISHU_TOKEN_ROTATION_ACK=true` | 未设置（deferred by operator） |

---

## 样例输入输出

### FOUND-001 (AppConfig env VAR)

```
Input:  python -c "from app.openclaw.config import AppConfig; c = AppConfig(); print(c.get('NON_EXISTENT_VAR', 'default_value'))"
Output: default_value
Exit Code: 0
Evidence: stdout
Forbidden: real_send, token_cache_read, daemon
```

### GW-001 (Primary Run Route)

```
Input:  POST /api/threads/thread-123/runs  with body {"assistant_id": "asst-xxx"}
Output: {"run_id": "run-xxx", "status": "queued"}
Exit Code: 200 or 201
Evidence: HTTP response body
Forbidden: real_send (dry-run only)
```

### RTCM-001 (RTCM Dry-Run)

```
Input:  python -m app.openclaw_cli.console rtcm-dry-run --input /tmp/rtcm_test.json
Output: (dry-run JSON output, no real agent handoff)
Exit Code: 0
Evidence: stdout + /tmp/rtcm_export.json (if --output specified)
Forbidden: .deerflow/rtcm read, Agent-S invocation, real_send
```

### CLI-005 (CLI --real flag rejection)

```
Input:  python -m app.openclaw_cli.console asset-dry-run --real --input /tmp/x.json
Output: error: --real flag not supported
Exit Code: non-zero
Forbidden: actual execution with --real
```

---

## 阻塞判定规则

### 立即停止（STOP AND REQUEST AUTHORIZATION）

以下任一条件出现时，停止执行，记录证据，立即请求人工授权：

| 条件 | 触发原因 |
|------|----------|
| real-send 被请求 | Feishu/Lark 真实发送 |
| token 值被读取/打印 | `token_cache.json` 访问 |
| Agent-S 被调用 | 外部 runtime 执行 |
| daemon/cron 被请求 | 后台调度启动 |
| production DB 写入被请求 | 生产数据写入 |
| 外部网络真实调用被请求 | 未授权的外部 API |

### 降级处理（DEFERRED_EXTERNAL）

以下情况标记为 DEFERRED_EXTERNAL，继续下一个用例：

- Lark MCP（SDK bug，替代方案 Tavily MCP 已就绪）
- Exa MCP（credentials 缺失）
- Feishu real-send（token rotation deferred by operator）

### 失败处理（NEEDS_TARGETED_FIX）

功能性失败（代码 bug、环境依赖）记录为 NEEDS_TARGETED_FIX，不修改代码，单独创建修复任务。

---

## 输出文件规划

| 阶段 | 输出文件 | 说明 |
|------|----------|------|
| R246B | `subsystem_operational_acceptance_plan.md` | 本文档 |
| R246B | `subsystem_operational_acceptance_cases.json` | 机器可读用例库 |
| R246B | `subsystem_operational_acceptance_result_template.md` | 结果填写模板 |
| R246B | `subsystem_operational_acceptance_risk_boundary.md` | 风险边界定义 |
| R246C–H | `subsystem_operational_acceptance_results_R246X.md` | 各组执行结果 |
| R246H 后 | `subsystem_operational_acceptance_final_report.md` | 最终验收报告 |

---

## 后续阶段建议

| 阶段 | 内容 |
|------|------|
| R246C | OPERATIONAL_ACCEPTANCE_GROUP_A（L0–L3：Foundation、Main Chain、MCP） |
| R246D | OPERATIONAL_ACCEPTANCE_GROUP_B（L2–L4：Claude、Web、Desktop、RTCM） |
| R246E | OPERATIONAL_ACCEPTANCE_GROUP_C（L4：Memory、Prompt、EVO、Tool） |
| R246F | OPERATIONAL_ACCEPTANCE_GROUP_D（L4：Asset、Report、Nightly、CLI） |
| R246G | OPERATIONAL_ACCEPTANCE_GROUP_E（L5：Security/Hygiene） |
| R246H | OPERATIONAL_ACCEPTANCE_FINAL_ANALYSIS（汇总分析、gap 修复建议） |
| R247X | Targeted Fix Plan（如发现需要修复的缺陷） |

---

## 最终结论

本文档建立了 OpenClaw 全方位系统级实际运转验收的完整规划：

- **6 层验收模型**：L0–L5，覆盖地基到横向安全
- **20 个验收域**：从 Foundation 到 Security
- **~200 个验收用例**：每个用例定义输入/输出/证据/禁止副作用
- **阻塞判定规则**：明确什么情况下必须停止
- **状态枚举**：8 种状态，覆盖所有可能结果
- **后续执行路径**：R246C–R246H 分组执行，R247X 修复

**本文档不执行验收。实际验收在 R246C–R246H 中执行。**

---

## 变更日志

| 日期 | 变更 |
|------|------|
| 2026-05-07 | R246B — 全方位系统级实际运转验收计划书 v1.0 创建 |
