# Feishu CLI 深度接入 DeerFlow 计划

> **计划版本**：v1.1（修订）
> **创建日期**：2026-04-17
> **目标**：将 larksuite/cli (官方 Feishu CLI) 深度集成到 DeerFlow 项目
> **项目路径**：E:\OpenClaw-Base\deerflow

---

## 一、背景与现状

### 1.1 DeerFlow 架构概览

```
DeerFlow (E:\OpenClaw-Base\deerflow)
├── backend/src/domain/
│   ├── m04/                    ← 调度器（意图识别 + 路由决策）
│   └── m11/                    ← 执行器（CLI/沙盒/工具执行）
├── backend/src/infrastructure/ ← 基础设施
├── skills/                    ← GStack Skills (public/custom/learned)
├── frontend/                  ← Next.js 前端
└── app/channels/feishu.py     ← 飞书 IM 通道（WebSocket）
```

### 1.2 现状分析

| 组件 | 状态 | 说明 |
|------|------|------|
| **DeerFlow Feishu IM** | ✅ 已接入 | WebSocket 消息通道，725 行代码 |
| **Feishu CLI** | ❌ 未接入 | 需要新增 |
| **lark-oapi SDK** | ✅ 已有 | IM 通道已用 |
| **官方 larksuite/cli** | ❌ 未安装 | 目标集成目标 |

### 1.3 接入目标

1. **CLI 命令能力**：通过命令行操作飞书文档、消息、日历等
2. **Skill 集成**：22 个官方 AI Skills 适配 DeerFlow SkillRouter
3. **工作流自动化**：工作流技能迁移
4. **双通道并存**：IM 消息通道 + CLI 命令能力

---

## 二、目标项目：larksuite/cli

### 2.1 项目信息

| 属性 | 值 |
|------|-----|
| **GitHub** | https://github.com/larksuite/cli |
| **Stars** | 8,021 |
| **语言** | Go |
| **安装** | `npm install -g @larksuite/cli` |
| **许可** | MIT |
| **维护者** | 飞书官方（Bytedance） |
| **许可** | MIT |
| **维护者** | 飞书官方（Bytedance） |
| **命令数** | 200+ |
| **AI Skills** | 22 个 |
| **业务域** | 14 个 |

### 2.2 能力矩阵

| 业务域 | 命令示例 | OpenClaw 对应模块 |
|--------|---------|------------------|
| Messenger | `lark msg send`, `lark msg read` | M04 Coordinator |
| Docs | `lark doc create`, `lark doc update` | M11 Executor |
| Base | `lark base table create`, `lark base item create` | M11 Executor |
| Sheets | `lark sheet create`, `lark sheet value update` | M11 Executor |
| Calendar | `lark calendar event create`, `lark calendar event list` | M04 Workflow |
| Tasks | `lark task create`, `lark task subtask add` | M04 Workflow |
| Meetings | `lark meeting room list`, `lark meeting record download` | M04 Workflow |
| Wiki | `lark wiki node create`, `lark wiki node search` | M04 Search |
| Drive | `lark drive file upload`, `lark drive file permission` | M11 Executor |
| Contacts | `lark contact user get`, `lark contact department list` | M04 Coordinator |
| Mail | `lark mail message send`, `lark mail group list` | M04 Workflow |
| Attendance | `lark attendance user stats`, `lark attendance group get` | M04 Workflow |
| Approval | `lark approval instance create`, `lark approval instance list` | M04 Workflow |
| Slides | `lark slides create`, `lark slides page add` | M11 Executor |

### 2.3 22 个官方 AI Skills

| Skill 文件 | 功能描述 | 对应 M04 Case |
|-----------|---------|---------------|
| `msg-send.md` | 发送消息 | `handleClaudeCodeRequest` |
| `doc-create.md` | 创建文档 | `handleClaudeCodeRequest` |
| `doc-append-block.md` | 追加文档块 | `handleClaudeCodeRequest` |
| `sheet-create.md` | 创建电子表格 | `handleClaudeCodeRequest` |
| `sheet-update-cell.md` | 更新单元格 | `handleClaudeCodeRequest` |
| `base-create-table.md` | 创建多维表格 | `handleClaudeCodeRequest` |
| `base-add-item.md` | 添加记录 | `handleClaudeCodeRequest` |
| `calendar-event-create.md` | 创建日历事件 | `handleGStackSkillRequest` |
| `calendar-event-list.md` | 列出日历事件 | `handleGStackSkillRequest` |
| `task-create.md` | 创建任务 | `handleGStackSkillRequest` |
| `task-subtask-add.md` | 添加子任务 | `handleGStackSkillRequest` |
| `meeting-room-list.md` | 列出会议室 | `handleGStackSkillRequest` |
| `wiki-node-search.md` | 搜索知识库 | `handleGStackSkillRequest` |
| `drive-file-upload.md` | 上传文件 | `handleClaudeCodeRequest` |
| `contact-user-get.md` | 获取用户信息 | `handleClaudeCodeRequest` |
| `mail-message-send.md` | 发送邮件 | `handleGStackSkillRequest` |
| `attendance-stats.md` | 考勤统计 | `handleGStackSkillRequest` |
| `approval-instance-create.md` | 创建审批实例 | `handleGStackSkillRequest` |
| `slides-create.md` | 创建幻灯片 | `handleClaudeCodeRequest` |
| ... | ... | ... |

---

## 三、接入架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     M04 Coordinator                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ SystemType  │  │ SkillRouter  │  │  IntentClassifier  │  │
│  │CLAUDE_CODE  │  │  (15+ skills)│  │                   │  │
│  │GSTACK_SKILL │  │              │  │                   │  │
│  │LARKSUITE_CLI│  │              │  │                   │  │
│  └──────┬──────┘  └──────────────┘  └────────────────────┘  │
└─────────┼───────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                    M11 Executor                             │
│  ┌─────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ ClaudeCodeAdapter│  │ LarkCLIAdapter │  │GVisorSandbox │  │
│  │                 │  │                │  │              │  │
│  │ execute()       │  │ execute()      │  │ execute()    │  │
│  │ executeWithCLI() │  │ executeCLI()   │  │ runsc/docker │  │
│  └─────────────────┘  └────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│              @larksuite/cli (200+ commands)                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ lark msg send --to user_id --content "hello"       │    │
│  │ lark doc create --title "新文档"                      │    │
│  │ lark calendar event create --start "2026-04-17"     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                    飞书开放平台 API                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 消息 API  │  │ 文档 API  │  │日历 API  │  │ 任务 API  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 新增/修改文件清单

```
DeerFlow (E:\OpenClaw-Base\deerflow) - 需修改的文件
├── backend/src/domain/m11/
│   ├── types.ts                  📝 修改：添加 LARKSUITE_CLI 到 ExecutorType
│   └── adapters/
│       └── lark_cli_adapter.ts   🆕 新增：Lark CLI 适配器
├── backend/src/domain/m04/
│   ├── types.ts                  📝 修改：添加 LARKSUITE_CLI 到 SystemType
│   ├── coordinator.ts           📝 修改：添加 handleLarkCLIRequest case
│   └── skill_router.ts          📝 修改：添加 LARKSUITE_PATTERNS 路由规则
├── skills/custom/larksuite/      🆕 Lark CLI Skills 安装目录 (共 22 个)
│   ├── msg-send.md
│   ├── doc-create.md
│   ├── doc-append-block.md
│   ├── sheet-create.md
│   ├── sheet-update-cell.md
│   ├── base-create-table.md
│   ├── base-add-item.md
│   ├── calendar-event-create.md
│   ├── calendar-event-list.md
│   ├── task-create.md
│   ├── task-subtask-add.md
│   ├── meeting-room-list.md
│   ├── wiki-node-search.md
│   ├── drive-file-upload.md
│   ├── contact-user-get.md
│   ├── mail-message-send.md
│   ├── attendance-stats.md
│   ├── approval-instance-create.md
│   └── slides-create.md

配置文件
├── .env.example                   📝 修改：添加 LARK_APP_ID, LARK_APP_SECRET
└── docs/
    └── FEISHU_CLI深度接入计划.md   ✅ 本计划
```

### 3.3 OpenClaw Skill 加载机制

OpenClaw 使用 **SkillLoader** 从以下路径加载 GStack Skills：
```
```

Skill 文件格式为 `SKILL.md`（YAML frontmatter），由 DeerFlow Skills 系统自动扫描 `skills/custom/` 目录加载。

---

## 四、实施计划

### Phase 0：环境准备

**目标**：确认环境就绪，安装 larksuite/cli

**任务清单**：

| # | 任务 | 负责组件 | 验证方式 | 状态 |
|---|------|---------|---------|------|
| P0.1 | 安装 Node.js 18+ | 系统 | `node --version` | ⬜ |
| P0.2 | 安装 npm | 系统 | `npm --version` | ⬜ |
| P0.3 | 安装 @larksuite/cli | M11 | `lark --version` | ⬜ |
| P0.4 | 创建飞书应用获取 App ID/Secret | 配置 | 飞书开放平台 | ⬜ |
| P0.5 | 配置 lark cli 认证 | M11 | `lark config list` | ⬜ |

**验收标准**：
```bash
$ lark --version
@larksuite/cli version x.x.x

$ lark config list
app_id: cli_xxxxxxxxx
app_secret: xxxxxxxxxxxx
```

---

### Phase 1：核心适配器开发

**目标**：开发 `LarkCLIAdapter` 并集成到 M04/M11 架构

**任务清单**：

| # | 任务 | 负责组件 | 验证方式 | 状态 |
|---|------|---------|---------|------|
| P1.1 | 创建 `src/domain/m11/adapters/lark_cli_adapter.ts` | M11 Adapter | 文件创建 | ✅ |
| P1.2 | 实现 `execute(cliCommand: string): Promise<CLIResult>` | M11 Adapter | 单元测试 | ✅ |
| P1.3 | 实现 `parseSkillCommand(skill: string, params: object): string` | M11 Adapter | 单元测试 | ✅ |
| P1.4 | 实现 `formatOutput(raw: string, format: 'json'|'text'): string` | M11 Adapter | 单元测试 | ✅ |
| P1.5 | 添加 `LARKSUITE_CLI` 到 `ExecutorType` (m11/types.ts) | M11 Types | 类型编译 | ✅ |
| P1.6 | 添加 LARKSUITE_CLI executor 到 `executor_adapter.ts` | M11 Executor | 执行测试 | ✅ |
| P1.7 | 实现命令超时处理（参考 `sandbox.ts`） | M11 Adapter | 超时测试 | ✅ |
| P1.8 | 实现错误模式识别与回退 | M11 Adapter | 错误处理测试 | ✅ |
| P1.9 | 实现 `lark config` 认证管理 (listProfiles) | M11 Adapter | 认证测试 | ✅ |

**核心接口设计**：

```typescript
// lark_cli_adapter.ts
interface LarkCLIAdapter {
  // 执行 lark cli 命令
  execute(cliCommand: string, config?: Partial<CLIConfig>): Promise<CLIResult>;

  // 解析 skill 为 cli 命令
  parseSkillCommand(skillName: string, params: Record<string, any>): string;

  // 格式化输出
  formatOutput(raw: string, format: 'json' | 'text' | 'markdown'): string;

  // 健康检查
  isAvailable(): Promise<boolean>;
}

interface CLIResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  execution_time_ms: number;
  parsed_output?: any;
}
```

**验收标准**：
```typescript
// P1.2 验证
const result = await larkCLIAdapter.execute('lark msg send --to user123 --content "test"');
console.assert(result.success === true, '消息发送成功');
console.assert(result.exit_code === 0, 'exit_code 为 0');

// P1.3 验证
const cmd = larkCLIAdapter.parseSkillCommand('msg-send', { to: 'user123', content: 'hello' });
console.assert(cmd === 'lark msg send --to user123 --content "hello"', '命令解析正确');

// P1.5 验证
type SystemType = 'CLAUDE_CODE' | 'GSTACK_SKILL' | 'LARKSUITE_CLI'; // 编译通过
type ExecutorType = 'CLAUDE_CODE' | 'LARKSUITE_CLI'; // 编译通过

// P1.7 验证
const executor = executorAdapter.getExecutor(ExecutorType.LARKSUITE_CLI);
console.assert(executor !== null, 'LARKSUITE_CLI executor 注册成功');
```

---

### Phase 2：Skill 文件适配

**目标**：将官方 22 个 AI Skills 转换为 OpenClaw SKILL.md 格式

**任务清单**：

| # | 任务 | 负责组件 | 验证方式 | 状态 |
|---|------|---------|---------|------|
| P2.1 | 创建 `skills/custom/larksuite/` 目录 | 文件系统 | 目录创建 | ✅ |
| P2.2-P2.16 | 转换 22 个 SKILL.md 文件 | Skill 文件 | 文件创建 | ✅ |
| P2.17 | 创建 `larksuite_skills.json` 注册配置 | 配置 | JSON 验证 | ✅ |
| P2.18 | 验证 Skills 安装 | 目录 | `ls skills/custom/larksuite/*.md \| wc -l` | ✅ (22个) |

**SKILL.md 格式模板**：

```markdown
---
name: larksuite_msg_send
description: 发送飞书消息给指定用户或群组
category: larksuite
version: 1.0.0
author: OpenClaw Team
compatibility:
  - "@larksuite/cli>=1.0.0"
inputs:
  - name: to
    type: string
    description: 用户 ID 或群组 ID
    required: true
  - name: content
    type: string
    description: 消息内容
    required: true
  - name: msg_type
    type: string
    description: 消息类型 (text/post/card)
    default: text
    required: false
outputs:
  - name: message_id
    type: string
    description: 发送成功的消息 ID
  - name: code
    type: number
    description: API 响应码
cli_command_template: "lark msg send --to {to} --content '{content}' --msg-type {msg_type}"
examples:
  - input:
      to: "ou_xxxxxxxx"
      content: "Hello from OpenClaw"
    output:
      message_id: "om_xxxxxxxx"
      code: 0
---

# Lark CLI 消息发送技能

## 功能说明
通过 lark CLI 发送飞书消息，支持文本、卡片等格式。

## 使用限制
- 机器人每分钟最多发送 20 条消息
- 消息内容不超过 4000 字符
```

**验收标准**：
```bash
# P2.18 验证 - Skills 安装到 DeerFlow skills/custom/larksuite/
$ ls e:/OpenClaw-Base/deerflow/skills/custom/larksuite/*.md | wc -l
22

$ grep -l "name: larksuite_" e:/OpenClaw-Base/deerflow/skills/custom/larksuite/*.md | wc -l
22

# Skills 加载验证 (DeerFlow Skills 系统自动扫描 skills/custom/)
const skills = await skillLoader.loadAllSkills();
const larksuiteSkills = Array.from(skills.values()).filter(s => s.category === 'larksuite');
console.assert(larksuiteSkills.length === 22, '22 个 larksuite skills 全部加载');
```

---

### Phase 3：意图识别与路由

**目标**：让 M04 Coordinator 能够正确识别飞书 CLI 意图并路由

**任务清单**：

| # | 任务 | 负责组件 | 验证方式 | 状态 |
|---|------|---------|---------|------|
| P3.1 | 更新 IntentClassifier 支持 larksuite 模式 | M04 Coordinator | 路由测试 | ⬜ |
| P3.2 | 添加 larksuite 命令模式到 `DANGEROUS_PATTERNS` 白名单 | M11 Sandbox | 安全测试 | ⬜ |
| P3.3 | 添加 `LARKSUITE_CLI` 到 SkillRouter 路由规则 | SkillRouter | 路由测试 | ⬜ |
| P3.4 | 实现自然语言 → lark cli 命令的 LLM 路由 | M04 Coordinator | E2E 测试 | ⬜ |
| P3.5 | 验证与现有 DeerFlow IM 通道不冲突 | 集成测试 | 通道隔离 | ⬜ |

**路由规则设计**：

```typescript
// backend/src/domain/m04/skill_router.ts
const LARKSUITE_PATTERNS = [
  { pattern: /发送.*飞书|飞书.*消息|lark.*msg/i, skill: 'larksuite_msg_send' },
  { pattern: /创建.*文档|新建.*文档|lark.*doc.*create/i, skill: 'larksuite_doc_create' },
  { pattern: /更新.*表格|lark.*sheet/i, skill: 'larksuite_sheet_update_cell' },
  { pattern: /创建.*日历|新建.*日程|lark.*calendar/i, skill: 'larksuite_calendar_event_create' },
  { pattern: /创建.*任务|lark.*task/i, skill: 'larksuite_task_create' },
  { pattern: /搜索.*wiki|知识库.*搜索|lark.*wiki/i, skill: 'larksuite_wiki_node_search' },
  { pattern: /上传.*文件|lark.*drive/i, skill: 'larksuite_drive_file_upload' },
  { pattern: /获取.*用户|lark.*contact/i, skill: 'larksuite_contact_user_get' },
  { pattern: /发送.*邮件|lark.*mail/i, skill: 'larksuite_mail_message_send' },
  { pattern: /考勤.*统计|lark.*attendance/i, skill: 'larksuite_attendance_stats' },
  { pattern: /创建.*审批|lark.*approval/i, skill: 'larksuite_approval_instance_create' },
  { pattern: /创建.*幻灯片|lark.*slides/i, skill: 'larksuite_slides_create' },
];
```

**验收标准**：
```typescript
// P3.4 验证
const intent = await coordinator.recognizeIntent('帮我给张三发一条飞书消息说项目已启动');
console.assert(intent.system === 'LARKSUITE_CLI', '识别为 larksuite cli');
console.assert(intent.skill === 'larksuite_msg_send', '路由到 msg-send skill');
console.assert(intent.params.to === 'zhangsan', '提取参数正确');

// P3.5 验证 - 同时测试 IM 通道和 CLI 能力
const imResult = await feishuChannel.send({ content: 'IM message' }); // 现有功能正常
const cliResult = await larkCLIAdapter.execute('lark msg send ...'); // 新 CLI 功能正常
```

---

### Phase 4：集成与测试

**目标**：完整集成测试，确保与现有架构兼容

**任务清单**：

| # | 任务 | 负责组件 | 验证方式 | 状态 |
|---|------|---------|---------|------|
| P4.1 | 编写 `lark_cli_adapter.test.ts` 单元测试 | M11 | Jest 测试 | ⬜ |
| P4.2 | 编写路由集成测试 | M04 | Jest 测试 | ⬜ |
| P4.3 | 执行全部 Jest 测试（确保无回归） | 全局 | `npm test` | ⬜ |
| P4.4 | E2E 测试：飞书消息发送 | 人工验证 | 功能演示 | ⬜ |
| P4.5 | E2E 测试：飞书文档创建 | 人工验证 | 功能演示 | ⬜ |
| P4.6 | E2E 测试：飞书日历事件创建 | 人工验证 | 功能演示 | ⬜ |
| P4.7 | Docker 环境验证 | DevOps | `docker-compose up` | ⬜ |
| P4.8 | 性能基准测试（命令执行时间） | M11 | 性能报告 | ⬜ |

**验收标准**：
```bash
# P4.3 验证
$ npm test
Test Suites: 25 passed, 25 total
Tests: 538 passed, 538 total
✓ 无回归

# P4.4-4.6 E2E 验证清单
✅ 发送消息到指定用户
✅ 创建新飞书文档
✅ 向文档追加内容块
✅ 创建电子表格并更新单元格
✅ 创建多维表格并添加记录
✅ 创建日历事件
✅ 列出日历事件
✅ 创建任务并添加子任务
✅ 列出会议室
✅ 搜索知识库节点
✅ 上传文件到云盘
✅ 获取用户信息
✅ 发送邮件
✅ 获取考勤统计
✅ 创建审批实例
✅ 创建幻灯片
```

---

### Phase 5：文档与部署

**目标**：完成文档编写和部署配置

**任务清单**：

| # | 任务 | 负责组件 | 验证方式 | 状态 |
|---|------|---------|---------|------|
| P5.1 | 编写接入文档 `docs/LARK_CLI_INTEGRATION.md` | 文档 | 文档完成 | ⬜ |
| P5.2 | 更新 `README.md` 飞书集成部分 | 文档 | 文档更新 | ⬜ |
| P5.3 | 更新 `CLAUDE.md` 架构文档 | 文档 | 文档更新 | ⬜ |
| P5.4 | 添加 `larksuite/cli` 到 `package.json` 依赖 | 配置 | 依赖安装 | ⬜ |
| P5.5 | 更新 `docker-compose.yml` 添加 npm 依赖安装 | DevOps | Docker 构建 | ⬜ |
| P5.6 | 创建环境变量配置示例 `.env.example` | 配置 | 配置模板 | ⬜ |

**文档结构**：

```markdown
# LARK CLI 集成文档

## 1. 快速开始
## 2. 认证配置
## 3. 可用命令
## 4. Skill 列表
## 5. 路由规则
## 6. 故障排除
## 7. API 参考
```

**验收标准**：
```bash
# P5.4 验证
$ grep "@larksuite/cli" package.json
"@larksuite/cli": "^1.0.0"

# P5.5 验证
$ docker-compose build --no-cache
# 构建成功，无错误

# P5.6 验证
$ cat .env.example | grep LARK
LARK_APP_ID=cli_xxxxxxxxx
LARK_APP_SECRET=xxxxxxxxxxxxxxxx
LARK_BOT_NAME=OpenClawBot
```

---

## 五、风险与缓解

### 5.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| larksuite/cli 版本迭代导致 API 变更 | 中 | 中 | 固定版本号 `~1.0.0`，定期更新 |
| 飞书开放平台 API 权限不足 | 低 | 高 | 配置检查脚本，权限指引文档 |
| 与现有 IM 通道冲突 | 低 | 中 | 双通道隔离，独立认证 |
| CLI 命令执行超时 | 中 | 低 | 参考 deerflow sandbox.ts 超时处理模式 |

### 5.2 安全风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| App Secret 泄露 | 低 | 高 | 仅使用环境变量，不写入代码 |
| 命令注入攻击 | 低 | 高 | 输入验证，参考 DANGEROUS_PATTERNS |
| 权限过载（机器人权限过大） | 中 | 中 | 最小权限原则，按需申请 scopes |

### 5.3 运维风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| CLI 版本不一致 | 中 | 低 | Docker 镜像版本固定 |
| 飞书 API 限流 | 中 | 中 | 请求间隔控制，指数回退 |
| 网络不可达 | 低 | 高 | 超时配置，健康检查 |

---

## 六、里程碑

| 里程碑 | 目标日期 | 交付物 |
|--------|---------|--------|
| **M0: 环境就绪** | Day 1 | larksuite/cli 安装完成，认证配置完成 |
| **M1: 核心适配器** | Day 2-3 | LarkCLIAdapter 代码完成，单元测试通过 |
| **M2: Skills 就绪** | Day 4-5 | 22 个 Skill 文件转换完成 |
| **M3: 路由完成** | Day 6-7 | 意图识别 + 路由集成测试通过 |
| **M4: 集成测试** | Day 8-9 | E2E 测试全部通过，Jest 无回归 |
| **M5: 文档完成** | Day 10 | 全部文档编写完成 |
| **M6: 上线部署** | Day 11 | Docker 镜像发布，生产部署 |

---

## 七、验收检查清单

### 7.1 代码检查

- [ ] `backend/src/domain/m11/adapters/lark_cli_adapter.ts` 文件存在且编译通过
- [ ] `backend/src/domain/m04/coordinator.ts` 包含 `handleLarkCLIRequest` 方法
- [ ] `backend/src/domain/m04/types.ts` 包含 `SystemType.LARKSUITE_CLI` 枚举
- [ ] `backend/src/domain/m11/types.ts` 包含 `ExecutorType.LARKSUITE_CLI` 枚举
- [ ] 22 个 SKILL.md 文件存在于 `skills/custom/larksuite/`

### 7.2 功能检查

- [ ] `lark --version` 命令执行成功
- [ ] `lark config list` 显示正确配置
- [ ] `lark msg send --to test --content "test"` 执行成功
- [ ] DeerFlow Skills 系统能加载全部 22 个 larksuite skills
- [ ] M04 能正确识别 "发送飞书消息" 意图

### 7.3 测试检查

- [ ] `backend/tests/test_lark_cli_adapter.py` 全部测试通过
- [ ] 路由集成测试全部通过
- [ ] `make test` 显示全部测试通过
- [ ] E2E 测试清单 16 项全部验证

### 7.4 文档检查

- [ ] `docs/LARK_CLI_INTEGRATION.md` 文档完整
- [ ] `README.md` 已更新飞书集成部分
- [ ] `CLAUDE.md` 已更新架构文档
- [ ] `.env.example` 包含 LARK 相关环境变量

---

## 八、依赖关系

```
Phase 0 (环境准备)
    │
    ▼
Phase 1 (核心适配器) ──────────────────────┐
    │                                       │
    ▼                                       │
Phase 2 (Skill 适配) ───┐                   │
    │                   │                   │
    ▼                   │                   │
Phase 3 (路由) ◄────────┴───────────────────┤
    │                                       │
    ▼                                       │
Phase 4 (集成测试) ◄────────────────────────┤
    │                                       │
    ▼                                       │
Phase 5 (文档部署) ◄────────────────────────┘
```

**说明**：
- **Phase 1 与 Phase 2 可并行开发**（独立文件，无直接依赖）
- Phase 3 依赖 Phase 1 完成（需要 executor 执行 skill 命令）
- Phase 4 依赖 Phase 1-3 全部完成
- Phase 5 依赖 Phase 4 完成

---

## 九、附录

### 9.1 参考资源

- [larksuite/cli GitHub](https://github.com/larksuite/cli)
- [飞书开放平台文档](https://open.feishu.cn/)
- [lark-oapi SDK](https://github.com/larksuite/lark-oapi)
- [DeerFlow Feishu IM 集成参考](./deerflow/backend/app/channels/feishu.py)

### 9.2 术语表

| 术语 | 说明 |
|------|-----|
| **lark-cli** | 官方 Feishu/Lark CLI 工具 |
| **SKILL.md** | DeerFlow 技能定义文件格式 |
| **SkillRouter** | DeerFlow 技能路由组件 |
| **IM Channel** | 即时通讯通道（消息收发） |
| **CLI Adapter** | 命令行适配器（执行器子组件） |

---

**计划编制**：OpenClaw Agent
**审核状态**：✅ 已校验（2026-04-17）
**最后更新**：2026-04-17

---

## 十、计划校验报告

### 10.1 校验结果

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 架构对齐 | ✅ 通过 | DeerFlow backend/src/domain/m04 + m11 架构一致 |
| 类型定义 | ✅ 通过 | SystemType 和 ExecutorType 枚举位置已确认 |
| Skill 加载 | ✅ 通过 | 使用 DeerFlow Skills 系统从 `skills/custom/` 加载 |
| 适配器模式 | ✅ 通过 | 参考 DeerFlow executor/sandbox 实现模式 |
| 路由机制 | ✅ 通过 | 复用 DeerFlow SkillRouter，新增 LARKSUITE_PATTERNS |
| 文件清单 | ✅ 修正 | 已修正为 DeerFlow 项目路径 |
| 类型枚举 | ✅ 修正 | P1.5 任务已拆分，明确两处修改 |
| Executor 注册 | ✅ 新增 | P1.7 新增 executor 注册任务 |

### 10.2 与 DeerFlow 现有组件的关系

| 现有组件 | 集成方式 | 说明 |
|---------|---------|------|
| **backend/src/domain/m11/adapters/** | 扩展 | 新增 lark_cli_adapter.ts |
| **backend/src/domain/m04/coordinator.ts** | 扩展 | 新增 handleLarkCLIRequest case |
| **backend/src/domain/m04/skill_router.ts** | 扩展 | 新增 LARKSUITE_PATTERNS |
| **skills/custom/** | 扩展 | 安装 22 个 larksuite SKILL.md |
| **backend/app/channels/feishu.py** | 并存 | IM 通道（消息）+ CLI（命令），互补不冲突 |

### 10.3 关键设计决策

1. **Skill 安装位置**：`E:\OpenClaw-Base\deerflow\skills\custom\larksuite\`（DeerFlow 项目内）
2. **认证方式**：`lark config` 管理，通过环境变量或配置文件注入
3. **执行模式**：复用 DeerFlow 执行器框架，通过 spawn 执行 lark cli 命令
4. **路由优先**：SkillRouter 先于执行器处理，精确路由到具体 skill
