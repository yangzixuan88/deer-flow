# 三位一体自动化 + Hermes 全量学习系统 深度接入规划

> **文档版本**: v4.0 (本地验证修正版)
> **核心战略**: OpenCLI 接入 + 现有架构优化 + Hermes 全量学习系统
> **生成日期**: 2026-04-15
> **本地验证完成**: E:\OpenClaw-Base\ 目录结构已验证
> **重要更新**: 添加实际安装检查清单，修正部署状态认知

`★ Insight ─────────────────────────────────────`
**架构启示:** OpenClaw采用**双轨架构**:
- **OpenClaw CLI** (`E:\OpenClaw-Base\.openclaw\`) — Node.js运行时,核心引擎
- **DeerFlow** (`E:\OpenClaw-Base\deerflow\`) — Python编排层,提供m08-m12模块
- **TypeScript项目** (`openclaw超级工程项目/src/domain/`) — 业务逻辑实现

三者需要通过统一协议集成,而不是各自独立。
─────────────────────────────────────────────────

---

## ⚠️ 项目实际部署状态 (本地验证后修正)

### 系统架构全貌

```
E:\OpenClaw-Base\
├── .openclaw/              # OpenClaw 运行时 (Node.js) ✅ 已安装
│   ├── openclaw.json       # 主配置 (55KB)
│   ├── memory/            # 记忆系统 (SQLite: main.sqlite 15MB)
│   ├── core/              # Ralph 循环·心跳·进化引擎
│   ├── browser/           # 浏览器会话 (user-data/)
│   ├── mcp-config.json    # MCP 服务器配置
│   └── cron/              # 定时任务
│
├── deerflow/              # DeerFlow 编排层 (Python) ✅ 源码完整
│   ├── backend/app/       # Python m08-m12 模块
│   │   ├── m08/learning_system.py  # Mock 实现
│   │   └── m11/sandbox_executor.py # 沙盒执行
│   ├── skills/public/      # 20+ 内置技能
│   └── cli-hub/          # ⚠️ 空目录 (CLI-Anything 工具待安装)
│
├── npm/                   # CLI 工具
│   └── openclaw.cmd       # OpenClaw CLI v2026.4.2 ✅ 可执行
│
└── openclaw超级工程项目/  # TypeScript 项目 (主要工作区)
    └── src/domain/        # m01-m11 TypeScript 实现
        ├── m11/adapters/executor_adapter.ts  # 四大执行器 ✅
        ├── nightly_distiller.ts              # 完整夜间复盘 ✅
        └── memory/                           # 五层记忆 ✅
```

### 组件安装状态矩阵

| 组件 | 代码状态 | 安装状态 | 位置 |
|------|---------|---------|------|
| **OpenCLI 运行时** | ✅ 已安装 | ✅ v2026.4.2 | `E:\OpenClaw-Base\.openclaw\` |
| **OpenCLI CLI** | ✅ 可执行 | ✅ | `E:\OpenClaw-Base\npm\openclaw.cmd` |
| **OpenCLI npm 包** | ❌ 未安装 | ❌ | `npm list -g @jackwener/opencli` = 无 |
| **OpenCLI MCP Server** | ❌ 未配置 | ❌ | `mcp-config.json` 只有 tavily |
| **CLI-Anything 代码** | ✅ 已部署 | ⚠️ 工具未装 | `executor_adapter.ts` L202-276 |
| **CLI-Hub 目录** | ✅ 存在 | ⚠️ 空 | `deerflow/cli-hub/` |
| **UI-TARS 代码** | ✅ 已部署 | ❌ 未安装 | `executor_adapter.ts` L323-353 |
| **Midscene.js 代码** | ✅ 已部署 | ❌ 未安装 | `executor_adapter.ts` L281-318 |
| **VisualToolSelector** | ✅ 已就绪 | ✅ | `executor_adapter.ts` L445-518 |

### OpenCLI vs Midscene.js 决策树 (已部署)

```
┌─────────────────────────────────────────────────────────────────────┐
│              Enhanced VisualToolSelector (L445-518)                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   浏览器操作:                                                        │
│   ├── OpenCLI daemon 可用? → 检查扩展连接                          │
│   │          ↓ 是                                                    │
│   │      → OpenCLI 执行层 (复用登录态·零成本·确定性)              │
│   │                                                               │
│   └── OpenCLI 不可用 → Midscene.js (视觉兜底)                      │
│                                                                     │
│   桌面应用 (<3次): → UI-TARS (视觉兜底) ✅ 已部署                 │
│   桌面应用 (≥3次): → CLI-Anything (CLI化) ✅ 已部署              │
│   CLI 命令:       → Claude Code ✅ 已部署                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 已部署自动化组件

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    现有自动化执行层 (代码已部署·工具待安装)                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  VisualToolSelector (src/domain/m11/adapters/executor_adapter.ts) ✅      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │   web_browser    → Midscene.js (代码已部署·工具待安装)              │   │
│  │       ↓                                                                │   │
│  │   desktop_app    → 使用次数 ≥3 → CLI-Anything (代码已部署)         │   │
│  │                   → 使用次数 <3 → UI-TARS (代码已部署)              │   │
│  │       ↓                                                                │   │
│  │   cli_command    → Claude Code ✅                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ExecutorAdapter (executor_adapter.ts)                                      │
│  ├── executeCLIAnything() → 9 工具白名单 ✅ 代码已部署 ⚠️ 工具待安装      │
│  ├── executeMidscene()    → Midscene.js ✅ 代码已部署 ⚠️ 工具待安装      │
│  └── executeUITARS()      → UI-TARS ✅ 代码已部署 ⚠️ 工具待安装          │
│                                                                             │
│  mapping_dictionaries.json → 7 个 CLI-Anything 映射 ✅                     │
│                                                                             │
│  ⚠️ 重要: 代码部署 ≠ 工具安装                                              │
│     CLI-Anything/UI-TARS/Midscene.js 需要单独安装才能真正执行              │
└────────────────────────────────────────────────────────────────────────────┘
```

### OpenCLI 接入定位

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    OpenCLI 接入后增强架构                                   │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  OpenCLI 新增为浏览器自动化的首选层 (优于 Midscene.js)                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │   浏览器操作                                                         │   │
│  │   ├── OpenCLI 可用 + 已登录 → OpenCLI (复用登录态/零成本/确定性)     │   │
│  │   └── OpenCLI 不可用     → Midscene.js (视觉兜底)                   │   │
│  │                                                                       │   │
│  │   桌面应用 (<3次)     → UI-TARS (视觉兜底)                           │   │
│  │   桌面应用 (≥3次)     → CLI-Anything (CLI化)                        │   │
│  │   CLI 命令             → Claude Code                                 │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  OpenCLI vs Midscene.js 对比:                                             │
│  ├── OpenCLI: 登录态复用、CDP 确定性、零 token 消耗                      │
│  └── Midscene.js: 视觉兜底、无需 Chrome 扩展、通用性更强                   │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 核心战略定位

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    战略定位 (修正版)                                         │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   OpenCLI 接入优先级: ★★★★★                                               │
│   ├── 浏览器会话复用 (登录态) → 首选                                      │
│   ├── 87+ 平台适配器 (B站/小红书/知乎/淘宝等)                           │
│   └── 自生成能力 (explore → synthesize)                                    │
│                                                                             │
│   CLI-Anything: ★★★★★ 已部署 (9 工具白名单)                             │
│   ├── 本地软件 CLI 化                                                     │
│   └── ≥3 次使用时自动切换                                                 │
│                                                                             │
│   UI-TARS: ★★★★☆ 已部署 (视觉兜底)                                      │
│   ├── 桌面应用视觉自动化                                                  │
│   └── <3 次使用时优先                                                     │
│                                                                             │
│   Midscene.js: ★★★☆☆ 已部署 (视觉兜底)                                  │
│   ├── Web 视觉自动化                                                      │
│   └── OpenCLI 不可用时的兜底                                              │
│                                                                             │
├────────────────────────────────────────────────────────────────────────────┤
│                        Hermes Agent 接入战略                                 │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   核心定位: ▶▶▶ 学习系统全量复刻 (最高优先级) ◀◀◀                        │
│                                                                             │
│   复用组件:                                                                │
│   ├── hermes_state.py     → M06 记忆系统核心 (FTS5/WAL/会话链)           │
│   ├── trajectory_compressor.py → M08 轨迹压缩 (长对话管理)                │
│   ├── insights.py          → M08 洞察提取 (自我改进)                      │
│   ├── credential_pool.py   → M03 凭证池 (多 API Key 轮转) - 可选        │
│   ├── smart_model_routing.py → M03 智能路由 (复杂度评估) - 可选            │
│                                                                             │
│   低优先级功能:                                                            │
│   ├── 14+ 平台 Gateway (Telegram/Discord 等) → 可选                       │
│   └── 其他辅助功能 → 可选                                                  │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 第一部分: OpenCLI 深度接入

### 1.1 OpenCLI 与现有架构的协同

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    OpenCLI 接入架构 (增强 VisualToolSelector)               │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  用户请求 → M01 编排引擎                                                    │
│       ↓                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              Enhanced VisualToolSelector (优化)                       │   │
│  │                                                                       │   │
│  │   浏览器操作:                                                         │   │
│  │   1. OpenCLI daemon 可用? → 检查扩展连接                            │   │
│  │          ↓ 是                                                        │   │
│  │      → OpenCLI 执行层 (复用 Chrome 登录态)                           │   │
│  │                                                                       │   │
│  │   2. OpenCLI 命令支持? → cli-manifest.json 查找                     │   │
│  │          ↓ 支持                                                      │   │
│  │      → OpenCLI 执行层                                                 │   │
│  │                                                                       │   │
│  │   3. OpenCLI 不可用 → Midscene.js (视觉兜底)                        │   │
│  │                                                                       │   │
│  │   桌面应用 (<3次): → UI-TARS (已部署)                               │   │
│  │   桌面应用 (≥3次): → CLI-Anything (已部署)                          │   │
│  │   CLI 命令:       → Claude Code (已部署)                            │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ↓                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      执行结果反馈层                                    │   │
│  │   → M06 记忆系统 (记录执行轨迹，包含 OpenCLI/Midscene 选择结果)       │   │
│  │   → M08 学习系统 (XP 捕获 → 成功率统计)                              │   │
│  │   → VisualToolSelector 学习 (下次更优选择)                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 OpenCLI 核心价值

| 维度 | OpenCLI 价值 | 对 OpenClaw 意义 |
|------|-------------|-----------------|
| **核心能力** | 浏览器会话复用 + CDP 控制 | 浏览器自动化首选 |
| **差异化** | 零 LLM 成本、确定性输出 | 降低 API 依赖 |
| **平台覆盖** | 87+ 内置命令 | 中国平台全覆盖 (B站/小红书/知乎/淘宝等) |
| **自生成** | explore → synthesize | 新平台分钟级接入 |

#### 1.2.2 OpenCLI 源码核心解析

**daemon.ts 通信架构**:
```typescript
// HTTP API 端点 (端口 19825)
GET  /ping        → 健康检查
GET  /status      → 进程状态、扩展连接数、内存
GET  /logs        → 日志查询
POST /command     → 发送命令 → 转发 Extension
POST /shutdown    → 关闭守护进程

// WebSocket 端点 (/ext)
→ 接收 Extension 日志
→ 推送命令到 Extension
→ 心跳保活 (15s interval)

// 安全机制
• Origin 检查: 仅接受 chrome-extension://
• X-OpenCLI Header: 防 CSRF
• Body 1MB 限制
```

**registry.ts 全局注册表**:
```typescript
// globalThis 解决 npm link 模块隔离
declare global {
  var __opencli_registry__: Map<string, CliCommand> | undefined;
}

// 策略驱动运行时行为
enum Strategy {
  PUBLIC   = 'public',   // 无需浏览器
  COOKIE   = 'cookie',   // Cookie 认证
  HEADER   = 'header',   // Header 认证
  INTERCEPT = 'intercept', // 拦截请求
  UI       = 'ui'        // 需要用户界面
}
```

**background.ts CDP 协议层**:
```typescript
// 白名单 CDP 方法
const ALLOWED = [
  'Page.navigate', 'Runtime.evaluate',
  'DOM.getDocument', 'DOM.querySelector',
  'Input.dispatchMouseEvent', 'Input.dispatchKeyEvent',
  'Network.getResponseBody'
];

// 窗口隔离: 专用自动化窗口 (与用户浏览器隔离)
// 空闲超时: 30s 自动关闭
// Tab 漂移检测与自动修复
```

#### 1.2.3 OpenCLI 接入架构

```
OpenClaw M01/M04
      ↓
┌──────────────────────────────────────┐
│   OpenCLI Integration Layer            │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ opencli_http_client.ts          │  │
│  │ HTTP → daemon:19825             │  │
│  └────────────────────────────────┘  │
│              ↓                         │
│  ┌────────────────────────────────┐  │
│  │ opencli_ws_bridge.ts            │  │
│  │ WebSocket → ext (实时日志/心跳)  │  │
│  └────────────────────────────────┘  │
│              ↓                         │
│  ┌────────────────────────────────┐  │
│  │ opencli_adapter_manager.ts       │  │
│  │ 命令注册/生命周期/状态监控       │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
      ↓
┌──────────────────────────────────────┐
│   opencli daemon (19825)              │
│      ↓                               │
│   chrome-extension                    │
│   (CDP Protocol)                     │
│      ↓                               │
│   用户 Chrome 浏览器                    │
└──────────────────────────────────────┘
```

### 1.3 第二层: CLI-Anything 深度接入

#### 1.3.1 CLI-Anything 定位再明确

| 维度 | CLI-Anything 价值 | 对 OpenClaw 意义 |
|------|------------------|-----------------|
| **核心能力** | 本地软件 CLI 生成 | 桌面应用控制 |
| **差异化** | 7 阶段流水线生成 + SKILL.md | AI 原生软件控制 |
| **软件覆盖** | 31+ 预建 harness | Blender/GIMP/OBS/LibreOffice |
| **扩展方式** | `cli-anything <software>` 自动生成 | 任意软件分钟级接入 |

**⚠️ 本地验证发现**:
- `executor_adapter.ts` L202-276 代码已部署 ✅
- `deerflow/cli-hub/` 目录存在但为空 ❌
- 工具未安装到 cli-hub 目录

#### 1.3.2 CLI-Anything 源码核心解析

**HARNESS.md 核心方法论**:
```
7 阶段流水线:
1. 源码分析 (分析目标软件源码/文档)
2. 架构设计 (设计 CLI 接口)
3. CLI 实现 (Click 框架)
4. 测试规划 (设计测试用例)
5. 测试编写 (单元 + E2E)
6. 文档更新 (自动生成 SKILL.md)
7. 发布 (CLI-Hub 社区共享)

核心原则:
• 真实软件调用 (非模拟/非替代)
• 双模式交互 (REPL + 子命令)
• JSON 结构化输出 (管道友好)
• 零妥协依赖 (必须调用实际后端)
```

**31+ 预建 Harness 一览**:

| 类别 | 软件 | 测试数 | OpenClaw 用途 |
|------|------|--------|---------------|
| **3D/图像** | Blender | 208 | 3D 渲染自动化 |
| | GIMP | 107 | 图像处理批量自动化 |
| | Inkscape | 202 | 矢量图形批量操作 |
| **视频/音频** | OBS Studio | 153 | 直播/录屏自动化 |
| | Kdenlive | 155 | 视频编辑自动化 |
| | Audacity | 161 | 音频处理批量自动化 |
| **办公** | LibreOffice | 158 | 文档格式转换/批量处理 |
| | Zotero | - | 文献管理自动化 |
| **开发** | Ollama | 98 | 本地 LLM 调用 |
| | WireMock | - | API 模拟/测试 |
| **AI** | ComfyUI | 70 | AI 图像生成流水线 |
| | Stable Diffusion | - | AI 生图自动化 |
| **工作流** | n8n | 55+ | 工作流自动化 |
| | Dify | 11 | DSL 编辑 |
| **浏览器** | Browser | - | Playwright 替代方案 |

**⚠️ 本地验证发现**:
- `deerflow/cli-hub/` 目录存在但为空
- 需要安装工具到该目录才能使用 CLI-Anything

**CLI-Hub 架构**:
```bash
# 安装社区 CLI
cli-hub install blender
cli-hub install gimp

# Agent 自主发现
openclaw skills install cli-anything-hub
```

#### 1.3.3 CLI-Anything 接入架构

```
OpenClaw M01/M04
      ↓
┌──────────────────────────────────────┐
│   CLI-Anything Integration Layer       │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ cli_anything_hub.ts              │  │
│  │ CLI-Hub 客户端                   │  │
│  │ • 搜索/安装/卸载 harness         │  │
│  │ • cli_anything.<software> 命令   │  │
│  └────────────────────────────────┘  │
│              ↓                         │
│  ┌────────────────────────────────┐  │
│  │ harness_registry.ts              │  │
│  │ 本地 harness 扫描与注册          │  │
│  │ • ~/.opencli/harnesses/         │  │
│  │ • mapping_dictionaries.json     │  │
│  └────────────────────────────────┘  │
│              ↓                         │
│  ┌────────────────────────────────┐  │
│  │ cli_executor.ts                  │  │
│  │ 子进程执行 + 输出解析            │  │
│  │ • spawn() 执行                   │  │
│  │ • JSON/YAML 输出标准化           │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
      ↓
┌──────────────────────────────────────┐
│   本地软件 (Blender/GIMP/OBS 等)      │
└──────────────────────────────────────┘
```

### 1.4 第三层: 视觉模拟点击 (兜底方案)

#### 1.4.1 视觉模拟定位再明确

| 维度 | 视觉模拟价值 | 对 OpenClaw 意义 |
|------|------------|-----------------|
| **核心能力** | 图像识别 + 模拟点击 | 最后兜底 |
| **触发条件** | OpenCLI/CLI-Anything 不可用或失败 | 兜底保障 |
| **适用场景** | 未知软件、复杂交互、非标准界面 | 全覆盖 |
| **平衡选择** | 作为上述两者的补充，而非首选 | 资源优化 |

#### 1.4.2 视觉模拟技术选型

**方案 A: OpenCV + PyAutoGUI (已有基础)**
```python
# 基于现有的 browser_subagent.py
# 扩展为通用视觉模拟引擎
class VisualSimulator {
  screenshot() → cv2.imread()
  find_template(template, threshold=0.8) → (x, y)
  click(x, y)
  type(text)
  drag(from_xy, to_xy)
}
```

**方案 B: Playwright (更现代)**
```typescript
// 利用 Playwright 的计算机视觉能力
import { chromium } from 'playwright';

async function visualClick(selector: string) {
  const page = await browser.newPage();
  await page.screenshot();
  // 图像识别定位
  const loc = await page.locator(selector);
  await loc.click();
}
```

**推荐: 混合方案**
```
视觉模拟选择器:
┌────────────────────────────────────────────────────────────┐
│  1. OpenCLI 可用? → 执行浏览器 CDP (优先)                    │
│  2. CLI-Anything 可用? → 执行本地 harness (次优先)           │
│  3. 上述都不可用 → 视觉模拟点击 (兜底)                       │
└────────────────────────────────────────────────────────────┘
```

### 1.5 三层协同策略

#### 1.5.1 选择算法

```typescript
/**
 * 三层自动化选择器
 * 决定使用哪一层执行任务
 */

enum AutomationLayer {
  OPENCLI = 'opencli',
  CLI_ANYTHING = 'cli_anything',
  VISUAL = 'visual'
}

class TriLayerSelector {
  async select(request: UserRequest): Promise<AutomationLayer> {
    const { target, action, context } = this.parse(request);

    // 层级 1: OpenCLI 检查
    if (this.isBrowserTarget(target)) {
      const status = await opencliClient.getStatus();
      if (status.extensionConnected) {
        // OpenCLI 可用，检查命令支持
        if (await this.opencliSupports(action, target)) {
          return AutomationLayer.OPENCLI;
        }
      }
    }

    // 层级 2: CLI-Anything 检查
    if (this.isLocalSoftware(target)) {
      if (await this.cliAnythingHasHarness(target)) {
        return AutomationLayer.CLI_ANYTHING;
      }
    }

    // 层级 3: 视觉模拟兜底
    if (context.visualModeEnabled) {
      return AutomationLayer.VISUAL;
    }

    // 无可用方案
    throw new Error('No automation layer available');
  }

  // 学习反馈: 记录成功率，下次优化选择
  async recordResult(layer: AutomationLayer, success: boolean): Promise<void> {
    await memory.commit({
      type: 'automation_choice',
      layer,
      success,
      timestamp: Date.now()
    });
  }
}
```

#### 1.5.2 三层执行对比

| 维度 | OpenCLI | CLI-Anything | 视觉模拟 |
|------|---------|--------------|----------|
| **速度** | ⚡ 快 (CLI) | ⚡ 快 (CLI) | 🐢 慢 (图像识别) |
| **准确性** | ✅ 高 (API) | ✅ 高 (CLI) | ⚠️ 中 (依赖识别率) |
| **成本** | ✅ 零成本 | ✅ 零成本 | ✅ 零成本 |
| **依赖** | Chrome 扩展 | 本地软件 | 屏幕可见 |
| **成功率** | 99%+ | 95%+ | 80%+ |
| **适用场景** | 浏览器 | 本地软件 | 兜底 |

#### 1.5.3 协同工作流示例

```
场景: 用户 "帮我把 B站视频下载下来，截图视频封面，然后用 GIMP 裁剪一下"

┌────────────────────────────────────────────────────────────────────────┐
│  步骤 1: OpenCLI → 下载 B站视频                                        │
│  opencli bilibili download BV1xxx --output ./video                     │
│  → 成功率 99%                                                          │
├────────────────────────────────────────────────────────────────────────┤
│  步骤 2: OpenCLI → 截图封面                                            │
│  opencli browser navigate "b站播放页"                                   │
│  opencli browser screenshot                                             │
│  → 成功率 99%                                                          │
├────────────────────────────────────────────────────────────────────────┤
│  步骤 3: CLI-Anything → GIMP 裁剪                                      │
│  cli-anything-gimp batch-crop --input cover.png --output cropped.png   │
│  → 成功率 95%                                                          │
├────────────────────────────────────────────────────────────────────────┤
│  如果步骤 2 失败 (B站 UI 变更):                                        │
│  → 兜底: 视觉模拟点击 → 截图 → 裁剪                                    │
│  → 记录: "OpenCLI B站截图失败，切换视觉模式"                            │
│  → 下次同类任务: 直接视觉模拟 (学习反馈)                                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 第二部分: Hermes Agent 全量学习系统

### 2.1 战略优先级定位

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Hermes Agent 接入优先级                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ★★★ 最高优先级 ★★★                                                     │
│   ───────────────────────────────────                                   │
│   学习系统全量复刻                                                        │
│   ├── M06 记忆系统核心 (FTS5/WAL/会话链)     → 必须全量                 │
│   ├── M08 轨迹压缩 (15,250 token 预算)      → 必须全量                 │
│   ├── M08 Insights 提取 (自我改进)          → 必须全量                 │
│   └── M08 技能合成 (Hermes + OpenCLI 融合)  → 必须全量                 │
│                                                                          │
│   ★★ 中优先级 ★★                                                        │
│   ───────────────────                                                   │
│   模型引擎增强                                                            │
│   ├── M03 凭证池 (多 API Key 轮转)           → 可选                     │
│   ├── M03 智能路由 (复杂度评估)              → 可选                     │
│   └── M03 降级链 (OpenRouter → Nous → 本地) → 可选                     │
│                                                                          │
│   ★ 低优先级 ★                                                           │
│   ──────────────                                                        │
│   辅助功能                                                               │
│   ├── 14+ 平台 Gateway                       → 未来考虑                 │
│   ├── RL Training 工具                        → 未来考虑               │
│   └── 多模型 Fine-tune 管线                   → 未来考虑                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 M06 记忆系统核心升级 (最高优先级)

#### 2.2.1 hermes_state.py 全量解析

**核心架构: SessionDB (SQLite WAL + FTS5)**

```python
# hermes_state.py 核心设计 (~1254 行)

class SessionDB:
    """
    SQLite 持久化会话存储
    核心: WAL 模式 + FTS5 全文检索 + 会话链
    """

    # Schema 设计
    sessions 表:
        - id: 主键
        - parent_session_id: 外键 (会话链)
        - title: 唯一索引 (命名会话)
        - model: 模型选择
        - model_config: 模型配置
        - token 统计 (input/output/cache/reasoning)
        - billing: 计费信息

    messages 表:
        - session_id: 外键
        - role: user/assistant/tool
        - content: 消息内容
        - tool_calls: 工具调用记录
        - reasoning: 思维链

    messages_fts 表:
        - FTS5 虚拟表
        - 全文检索 messages.content
        - 触发器自动同步

    # 关键实现
    def _execute_write(self, sql, params):
        # 1. BEGIN IMMEDIATE (立即争抢写锁)
        # 2. 15 次重试 + 20~150ms 随机抖动
        # 3. WAL checkpoint (每 50 次写)

    def fork_session(self, session_id):
        # 创建子会话 (parent_session_id)
        # 支持多路径探索
```

**OpenClaw 借鉴方案**:

```typescript
// src/domain/m06/storage/session_db.ts

/**
 * 基于 Hermes SessionDB 的 OpenClaw 实现
 * 核心: SQLite WAL + FTS5 + 会话链
 */

export class SessionDB {
  private db: Database;

  // 1. WAL 模式 + 随机抖动重试
  async write(sql: string, params: unknown[]): Promise<void> {
    const maxRetries = 15;
    for (let i = 0; i < maxRetries; i++) {
      try {
        await this.db.exec('BEGIN IMMEDIATE');
        await this.db.run(sql, params);
        await this.db.exec('COMMIT');

        // 每 50 次写执行 WAL checkpoint
        this.checkpointIfNeeded();
        return;
      } catch (err) {
        await this.db.exec('ROLLBACK');
        if (i === maxRetries - 1) throw err;
        await sleep(randomInt(20, 150)); // 随机抖动
      }
    }
  }

  // 2. FTS5 全文检索 + 触发器同步
  async createFTS(): Promise<void> {
    await this.db.exec(`
      CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
      USING fts5(content, tokenize='porter unicode61');

      CREATE TRIGGER IF NOT EXISTS messages_fts_insert
      AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(rowid, content)
        VALUES (new.rowid, new.content);
      END;
    `);
  }

  // 3. 会话链 (parent_session_id)
  async forkSession(sessionId: string): Promise<string> {
    const parent = await this.getSession(sessionId);
    const newId = uuid();
    await this.write(`
      INSERT INTO sessions (id, parent_session_id, title, model, ...)
      VALUES (?, ?, ?, ?, ...)
    `, [newId, sessionId, `${parent.title} #fork`, parent.model]);
    return newId;
  }

  // 4. 命名会话 + 自动编号
  async ensureUniqueTitle(baseTitle: string): Promise<string> {
    const existing = await this.db.all(
      `SELECT title FROM sessions WHERE title LIKE ?`,
      [`${baseTitle}%`]
    );
    if (existing.length === 0) return baseTitle;
    return `${baseTitle} #${existing.length + 1}`;
  }
}
```

#### 2.2.2 trajectory_compressor.py 全量解析

**核心架构: 5 步轨迹压缩**

```python
# trajectory_compressor.py (~1471 行)

def compress_trajectory(messages, target_tokens=15250):
    """
    5 步压缩策略:
    1. 保护首轮 (system + human + first gpt + first tool)
    2. 保护尾部 N 轮 (默认 4 轮)
    3. 仅压缩中间区域
    4. 按需压缩 (满足 token 预算即可)
    5. [CONTEXT SUMMARY] 替换被压缩区域
    """

    # 受保护区域
    protected = find_protected_indices(messages)
    tokens_to_save = protected + tail_n

    # 计算需要压缩的 token
    total = count_tokens(messages)
    if total <= target_tokens:
        return messages  # 无需压缩

    # 压缩中间区域
    compress_start = first_tool_response_index
    middle_messages = messages[compress_start:-tail_n]
    compressed_middle = summarize(middle_messages)  # LLM 摘要

    # 构建压缩结果
    return (
        messages[:protected] +
        [create_summary_message(compressed_middle)] +
        messages[-tail_n:]
    )
```

**OpenClaw 借鉴方案**:

```typescript
// src/domain/m08/trajectory_compressor.ts

/**
 * 基于 Hermes TrajectoryCompressor 的 OpenClaw 实现
 * 核心: 首尾保护 + 中间折叠 + 15,250 token 预算
 */

export class TrajectoryCompressor {
  private targetTokens = 15250;
  private protectedHead = 4;  // 首轮 + 前 3 轮
  private protectedTail = 4;  // 尾部 4 轮

  compress(messages: Message[]): CompressedResult {
    const total = this.countTokens(messages);

    // 无需压缩
    if (total <= this.targetTokens) {
      return { compressed: messages, saved: 0, metrics: null };
    }

    // 找到压缩起点
    const compressStart = this.findCompressStart(messages);

    // 保护首尾
    const head = messages.slice(0, compressStart);
    const tail = messages.slice(-this.protectedTail);

    // 压缩中间区域
    const middle = messages.slice(compressStart, -this.protectedTail);
    const summarized = await this.summarizeMiddle(middle);

    // 构建压缩轨迹
    const compressed = [
      ...head,
      this.createSummaryMessage(summarized),
      ...tail
    ];

    return {
      compressed,
      saved: total - this.countTokens(compressed),
      metrics: {
        originalTokens: total,
        compressedTokens: this.countTokens(compressed),
        compressionRatio: (total - this.countTokens(compressed)) / total
      }
    };
  }

  private async summarizeMiddle(messages: Message[]): Promise<string> {
    // 调用 LLM 生成摘要
    const prompt = `Summarize this conversation concisely:\n${messages.map(m => `${m.role}: ${m.content}`).join('\n')}`;
    return this.llm.complete(prompt);
  }
}
```

#### 2.2.3 insights.py 全量解析

**核心架构: 从执行轨迹提取改进洞察**

```python
# insights.py (~34KB)

class Insights:
    """
    从 Agent 执行轨迹中提取改进洞察
    用于自我诊断和自我改进
    """

    def extract_from_turn(self, turn: Turn) -> list[Insight]:
        # 分析失败的工具调用
        # 分析长时间的思考
        # 分析重复的尝试
        # 分析成功的捷径

    def generate_insight_report(self, turns: list[Turn]) -> InsightReport:
        # 聚合分析
        # 识别模式
        # 生成建议

    def apply_learning(self, insight: Insight):
        # 更新系统提示词
        # 调整工具参数
        # 优化决策策略
```

#### 2.2.4 M06 升级架构

```
┌────────────────────────────────────────────────────────────────────────┐
│                    M06 记忆系统升级架构                                 │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  L1: Working Memory (ReMe 三阶段压缩)    ← 已有                         │
│  L2: Session Memory (LoCoMo F1=0.613)  ← 已有                         │
│                                                                         │
│  ↓ Hermes 增强                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  L2.5: Hermes SessionDB (NEW)                                    │  │
│  │  ├── SQLite WAL 模式 (高并发)                                     │  │
│  │  ├── FTS5 全文检索 (触发器同步)                                  │  │
│  │  ├── 会话链 (parent_session_id)                                  │  │
│  │  ├── 命名会话 + 自动编号                                         │  │
│  │  └── Token 计费系统                                               │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  L3: Persistent Memory (MemOS 混合检索)  ← 已有                        │
│  L4: Knowledge Graph (GraphRAG BFS)     ← 已有                         │
│  L5: Visual Anchor (CortexaDB)          ← 已有                         │
│                                                                         │
│  ↓ Hermes 增强                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  L6: Trajectory Archive (NEW)                                     │  │
│  │  ├── 15,250 token 预算                                          │  │
│  │  ├── 首尾保护 + 中间折叠                                         │  │
│  │  ├── [CONTEXT SUMMARY] 替换                                     │  │
│  │  └── Insight 提取 (自我改进)                                     │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.3 M08 学习系统核心升级 (最高优先级)

#### 2.3.1 融合架构: Hermes + OpenCLI

```
┌────────────────────────────────────────────────────────────────────────┐
│              M08 学习系统融合架构 (Hermes + OpenCLI)                    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    XP 捕获 (Experience Capture)                    │  │
│  │                                                                   │  │
│  │   成功路径记录:                                                   │  │
│  │   ├── OpenCLI 成功执行 → 记录为 XP                               │  │
│  │   ├── CLI-Anything 成功执行 → 记录为 XP                          │  │
│  │   └── 视觉模拟成功 → 记录为 XP (兜底经验)                         │  │
│  │                                                                   │  │
│  │   失败路径记录:                                                   │  │
│  │   ├── OpenCLI 失败 → 记录 + 尝试 CLI-Anything                    │  │
│  │   ├── CLI-Anything 失败 → 记录 + 尝试视觉模拟                   │  │
│  │   └── 全部失败 → Insights 提取                                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              ↓                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    技能合成 (Skill Synthesis)                      │  │
│  │                                                                   │  │
│  │   Hermes trajectory_compressor → 轨迹压缩 → 训练数据               │  │
│  │           ↓                                                        │  │
│  │   OpenCLI explore → synthesize → 新 CLI 适配器                   │  │
│  │           ↓                                                        │  │
│  │   CLI-Anything harness 生成 → SKILL.md                           │  │
│  │           ↓                                                        │  │
│  │   融合: 成功 XP → SKILL.md (供下次复用)                           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              ↓                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    夜间蒸馏 (Nightly Distiller)                   │  │
│  │                                                                   │  │
│  │   Stage 1-6: 已有流程                                            │  │
│  │   新增 Stage 7: Hermes Insights 提取                              │  │
│  │   ├── 失败模式识别                                               │  │
│  │   ├── 成功捷径提取                                               │  │
│  │   └── 系统提示词自动优化                                          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

#### 2.3.2 技能合成流程

```typescript
// src/domain/m08/skill_synthesizer.ts

/**
 * 技能合成引擎
 * 融合 Hermes 轨迹压缩 + OpenCLI 适配器生成
 */

export class SkillSynthesizer {
  // 融合 Hermes + OpenCLI 的合成流程
  async synthesizeFromXP(xp: Experience): Promise<Skill> {
    // 1. Hermes: 轨迹压缩 → 训练数据
    const compressor = new TrajectoryCompressor();
    const compressed = compressor.compress(xp.messages);

    // 2. OpenCLI: 分析成功模式
    const patterns = this.analyzePatterns(xp);

    // 3. 生成 SKILL.md
    const skill: Skill = {
      name: xp.taskName,
      trigger: xp.trigger,
      steps: xp.steps.map(s => ({
        layer: s.layer,      // opencli / cli_anything / visual
        command: s.command,
        args: s.args,
        successRate: s.successRate
      })),
      compressed: compressed.compressed,
      insights: xp.insights,
      generatedAt: Date.now()
    };

    // 4. 注册到 Skills 系统
    await this.registerSkill(skill);

    return skill;
  }

  // XP 捕获 → 技能合成闭环
  async xpToSkillLoop(): Promise<void> {
    // 1. 扫描 L2.5 SessionDB 中的成功会话
    const successfulSessions = await this.sessionDB.find({
      type: 'opencli_execution',
      success: true
    });

    // 2. 提取 XP
    for (const session of successfulSessions) {
      const xp = await this.extractXP(session);

      // 3. 检查是否满足合成条件
      if (xp.successRate > 0.8 && xp.frequency > 3) {
        // 4. 合成技能
        const skill = await this.synthesizeFromXP(xp);
        console.log(`[SkillSynthesizer] 新技能: ${skill.name}`);
      }
    }
  }
}
```

### 2.4 M03 模型引擎增强 (中优先级-可选)

#### 2.4.1 credential_pool.py 解析

```python
# credential_pool.py (~54KB)

class CredentialPool:
    """
    多 API Key 轮转系统
    支持: OpenRouter, Nous, Codex, xAI, Kimi, MiniMax, Ollama
    """

    def __init__(self):
        self.providers = {}  # provider → list of credentials
        self.usage = {}      # credential → usage count
        self.cooldown = {}  # credential → cooldown until

    def get_credential(self, provider: str) -> Credential:
        # 1. 过滤冷却中的凭证
        # 2. 选择使用最少的
        # 3. 轮转返回

    def on_rate_limit(self, credential: Credential):
        # 402 错误时进入冷却
        # 30 秒后解除

    def on_error(self, credential: Credential, error: Exception):
        # 错误计数
        # 超过阈值永久禁用
```

#### 2.4.2 smart_model_routing.py 解析

```python
# smart_model_routing.py (~6KB)

class SmartModelRouter:
    """
    智能模型选择
    根据任务复杂度选择模型
    """

    def route(self, messages: list[Message]) -> str:
        # 1. 关键词匹配 → 强制路由
        if contains_keyword(messages, ['代码', 'code']):
            return 'claude-3-opus'

        # 2. 复杂度评估
        complexity = self.assess_complexity(messages)

        if complexity == 'low':
            return 'kimi-free'
        elif complexity == 'medium':
            return 'claude-3-sonnet'
        else:
            return 'claude-3-opus'

    def assess_complexity(self, messages) -> str:
        # token 数量
        # 工具调用数量
        # 上下文依赖
```

---

## 第三部分: 分阶段实施计划

### 3.1 OpenCLI 接入 - 前置条件检查清单

```markdown
## OpenCLI 深度接入 - 前置条件 (本地验证后补充)

### 1. OpenCLI 安装状态
- [x] OpenCLI CLI 已安装: `E:\OpenClaw-Base\npm\openclaw.cmd` (v2026.4.2)
- [ ] npm 包未安装: `npm install -g @jackwener/opencli`
- [ ] MCP Server 未配置: `mcp-config.json` 只有 tavily

### 2. MCP Server 配置 (T1 任务)
- [ ] 在 `E:\OpenClaw-Base\.openclaw\mcp-config.json` 添加:
```json
{
  "mcpServers": {
    "opencli": {
      "command": "opencli",
      "args": ["mcp", "serve"]
    }
  }
}
```

### 3. CLI-Hub 工具安装 (可选 - CLI-Anything)
- [ ] 工具安装到 `E:\OpenClaw-Base\deerflow\cli-hub\`
- [ ] 配置 `EXECUTOR_CLI_HUB_PATH=E:\OpenClaw-Base\deerflow\cli-hub`

### 4. VisualToolSelector 集成 (T3)
- [x] 路由逻辑已就绪: executor_adapter.ts L445-518
- [x] 待验证: web_browser → OpenCLI (优先) / Midscene (兜底)
```

### 3.2 分阶段实施计划 (修正版)

| Phase | 工期 | 任务 | 前置条件 | 状态 |
|-------|------|------|---------|------|
| **T1** | 1 周 | OpenCLI MCP Server 接入 | 需先安装 npm 包 | ⏳ 待实施 |
| **T2** | 1 周 | OpenCLI Daemon 进程管理 | 需完成 T1 | ⏳ 待实施 |
| **T3** | 1 周 | Enhanced VisualToolSelector | 已就绪代码 | ⏳ 待实施 |
| **T4** | 1 周 | OpenCLI 命令注册 | 需完成 T1-T2 | ⏳ 待实施 |
| **T5** | 1 周 | 三层协同测试 + 调优 | 需完成 T1-T4 | ⏳ 待实施 |

**已部署组件 (无需重复实施)**:
- ✅ CLI-Anything: `executeCLIAnything()` 已实现，9 工具白名单
- ✅ UI-TARS: `executeUITARS()` 已实现
- ✅ Midscene.js: `executeMidscene()` 已实现
- ✅ VisualToolSelector: 三层决策树已实现 (L445-518)

### 3.2 OpenCLI 与现有架构集成点

```
┌────────────────────────────────────────────────────────────────────────┐
│                    OpenCLI 集成架构                                      │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  src/domain/m11/adapters/executor_adapter.ts                           │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                                                                     │  │
│  │  // 新增 ExecutorType                                              │  │
│  │  enum ExecutorType {                                               │  │
│  │    CLAUDE_CODE = 'claude_code',                                  │  │
│  │    CLI_ANYTHING = 'cli_anything',  ← 已存在                      │  │
│  │    MIDSCENE = 'midscene',         ← 已存在                      │  │
│  │    UI_TARS = 'ui_tars',           ← 已存在                      │  │
│  │    OPENCLI = 'opencli',           ← 新增                          │  │
│  │  }                                                               │  │
│  │                                                                     │  │
│  │  // 新增 OpenCLI 执行方法                                          │  │
│  │  private async executeOpenCLI(task): Promise<any> {               │  │
│  │    const status = await opencliClient.getStatus();               │  │
│  │    if (!status.extensionConnected) {                             │  │
│  │      // 降级到 Midscene.js                                        │  │
│  │      return this.executeMidscene(task);                         │  │
│  │    }                                                              │  │
│  │    // ... OpenCLI 执行逻辑                                        │  │
│  │  }                                                                │  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  VisualToolSelector.select() 增强                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                                                                     │  │
│  │  select(operation, context): ExecutorType {                        │  │
│  │    case 'web_browser':                                            │  │
│  │      // 1. OpenCLI 优先 (daemon 可用 + 扩展已连接)              │  │
│  │      if (await opencliClient.isAvailable()) {                     │  │
│  │        return ExecutorType.OPENCLI;                               │  │
│  │      }                                                            │  │
│  │      // 2. OpenCLI 不可用 → Midscene.js 兜底                    │  │
│  │      return ExecutorType.MIDSCENE;                               │  │
│  │                                                                     │  │
│  │    case 'desktop_app':                                            │  │
│  │      // ≥3次 → CLI-Anything (已部署)                             │  │
│  │      // <3次 → UI-TARS (已部署)                                 │  │
│  │  }                                                                │  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Hermes 学习系统实施

| Phase | 工期 | 任务 | 优先级 |
|-------|------|------|--------|
| **H1** | 2 周 | SessionDB 全量复刻 (WAL/FTS5/会话链) | ★★★ |
| **H2** | 1 周 | TrajectoryCompressor 全量复刻 | ★★★ |
| **H3** | 1 周 | Insights 提取引擎 | ★★★ |
| **H4** | 2 周 | 技能合成融合 (Hermes + OpenCLI) | ★★★ |
| **H5** | 1 周 | Credential Pool (可选) | ★★ |
| **H6** | 1 周 | Smart Router (可选) | ★★ |

### 3.4 总工期估算

| 模块 | Phase | 工期 |
|------|-------|------|
| OpenCLI 接入 | T1-T5 | 5 周 |
| Hermes 学习系统 | H1-H4 | 6 周 |
| 可选增强 | H5-H6 | 2 周 |
| **总计** | - | **8-10 周** |

---

## 第四部分: 验收标准

### 4.1 三位一体自动化

| 任务 | 验收标准 | 测试场景 |
|------|----------|----------|
| OpenCLI 接入 | `opencli bilibili hot` → JSON | B站热门获取 |
| OpenCLI Daemon | M11 自动启停 | 重启测试 |
| CLI-Anything Hub | `cli-anything-gimp --help` 正常 | GIMP 命令执行 |
| 三层选择器 | 正确路由到最合适层 | 模拟 3 种场景 |
| 视觉兜底 | 前两层失败时自动切换 | 强制失败测试 |
| 学习反馈 | 选择器准确率 > 90% | 100 次执行统计 |

### 4.2 Hermes 学习系统

| 任务 | 验收标准 | 测试场景 |
|------|----------|----------|
| SessionDB WAL | 15 次并发写入无冲突 | 压力测试 |
| FTS5 检索 | 100 条记录 < 10ms | 全文检索测试 |
| 会话链 | fork 后正确追溯父会话 | 分支探索测试 |
| 轨迹压缩 | 50k token → 15k token | 长对话测试 |
| Insights 提取 | 失败模式识别准确 > 80% | 100 次失败分析 |
| 技能合成 | 成功 XP → SKILL.md 可用 | 端到端合成测试 |

---

## 第五部分: 总结

### 5.1 核心价值

```
OpenCLI 接入 (唯一新增):
• 浏览器会话复用 → 零成本、确定性、复用 Chrome 登录态
• 87+ 平台适配器 → B站/小红书/知乎/淘宝等中国平台全覆盖
• 自生成能力 → explore → synthesize 分钟级新平台接入
• 降级策略 → OpenCLI 不可用时自动切换 Midscene.js

现有架构 (已部署无需修改):
• CLI-Anything → 本地软件控制 (9 工具白名单已实现)
• UI-TARS → 桌面应用视觉自动化 (<3 次使用)
• Midscene.js → Web 视觉自动化 (OpenCLI 降级兜底)
• VisualToolSelector → 三层决策树已实现

Hermes 学习系统 (最高优先级):
• SessionDB: 记忆持久化 → WAL/FTS5/会话链
• Trajectory: 长对话管理 → 首尾保护/中间折叠
• Insights: 自我改进 → 失败模式/成功捷径
• Synthesis: 技能生成 → Hermes + OpenCLI 融合
```

### 5.2 与你的战略完全对齐

| 你的要求 | 本方案对应 |
|----------|-----------|
| OpenCLI + CLI-Anything 互补 | ✅ OpenCLI 补充浏览器自动化层 |
| 视觉模拟 UI-TARS 已部署 | ✅ executeUITARS() 已实现 |
| CLI-Anything 已部署 | ✅ executeCLIAnything() 已实现 |
| OpenCLI 作为浏览器首选 | ✅ T1-T5 接入任务 |
| Hermes 全量学习系统 (最高优先级) | ✅ H1-H4 全部任务 |
| 其他功能低优先级 | ✅ H5-H6 可选 |

---

*本文档基于项目实际部署状态修正。*
*OpenCLI 唯一新增 + Hermes 全量学习 = OpenClaw 进化目标。*
