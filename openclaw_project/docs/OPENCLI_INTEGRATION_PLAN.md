# OpenCLI 深度接入规划报告

> **文档版本**: v1.0
> **生成日期**: 2026-04-15
> **基于**: OpenCLI 源码深度分析 + Hermes Agent 源码考察报告
> **目标**: 将 OpenCLI 完整接入 OpenClaw，实现浏览器桥接 + CLI-Hub + 技能自合成

---

## 第一章 · OpenCLI 核心技术架构

### 1.1 项目定位

| 维度 | OpenCLI | OpenClaw 当前状态 |
|------|---------|-------------------|
| **核心能力** | 浏览器会话复用 + CLI 适配器生成 | 意图分类 → DAG 规划 → 执行 |
| **差异化** | 零 LLM 成本、确定性输出 | 多 Agent 协作、DeerFlow 编排 |
| **生态** | 87+ 内置适配器、插件市场 | 资产库、MCP Server |
| **架构** | 守护进程 + 浏览器扩展桥接 | Dapr 状态层 + M04 工具调用 |

### 1.2 核心架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        OpenClaw (M01)                           │
│   意图分类 → DAG 规划 → 跨系统协同 (M04/M11)                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              OpenCLI Integration Layer (NEW)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ OpenCLI      │  │ CLI-Anything │  │ Skill Synthesizer    │ │
│  │ Daemon Bridge│  │ Hub          │  │ (explore→synthesize) │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘ │
└─────────┼─────────────────┼──────────────────────┼─────────────┘
          │                 │                      │
          ▼                 ▼                      ▼
┌─────────────────┐  ┌─────────────┐  ┌─────────────────────────┐
│ opencli daemon  │  │ 87+ CLI     │  │ Browser Extension        │
│ (WebSocket/HTTP)│  │ Adapters    │  │ (CDP Protocol)           │
│ Port: 19825     │  │ clis/ dir   │  │ Tab Management          │
└────────┬────────┘  └─────────────┘  └───────────┬─────────────┘
         │                                        │
         │  WebSocket                             │ CDP
         │  chrome-extension://                   │ DevTools Protocol
         │                                        ▼
         │                              ┌─────────────────────────┐
         │                              │ Chrome/Chromium         │
         │                              │ (复用用户登录态)       │
         └─────────────────────────────►│ • 用户标签页           │
                                        │ • 自动化窗口           │
                                        └─────────────────────────┘
```

### 1.3 OpenCLI 源码结构

```
opencli/
├── src/
│   ├── daemon.ts          # HTTP+WebSocket 守护进程 (19825 端口)
│   ├── registry.ts        # 全局命令注册表 (globalThis Map)
│   ├── execution.ts       # 命令执行引擎 (参数校验/管道/Hot-reload)
│   ├── capabilityRouting.ts # 浏览器会话路由判断
│   ├── plugin.ts          # 插件生命周期管理
│   ├── explorer.ts        # 浏览器行为发现 (API 探测)
│   ├── synthesize.ts      # CLI 配置生成 (YAML/JSON)
│   ├── external.ts        # 外部 CLI 集成
│   ├── main.ts / cli.ts   # 入口点
│   └── commands/          # 内置命令实现 (87+ 适配器)
├── extension/
│   ├── src/background.ts  # Service Worker (WebSocket 客户端)
│   ├── manifest.json      # 扩展配置
│   └── popup.html/js      # 弹窗 UI
└── cli-manifest.json     # 预生成清单 (毫秒级启动)
```

### 1.4 关键技术细节

#### 1.4.1 Daemon 通信协议

```
┌────────────────────────────────────────────────────────────┐
│                     daemon.ts API                          │
├─────────┬────────────┬────────────────────────────────────┤
│ Method  │ Path       │ Function                           │
├─────────┼────────────┼────────────────────────────────────┤
│ GET     │ /ping      │ 健康检查                           │
│ GET     │ /status    │ 状态信息 (uptime/memory/pending)   │
│ GET     │ /logs      │ 日志查询                           │
│ DELETE  │ /logs      │ 清空日志                           │
│ POST    │ /command   │ 发送命令 → 转发 Extension          │
│ POST    │ /shutdown  │ 关闭守护进程                       │
└─────────┴────────────┴────────────────────────────────────┘

安全机制:
• Origin 检查: 仅接受 chrome-extension:// 来源
• X-OpenCLI Header: 防止跨站请求伪造
• Body Size 限制: 1MB
• WebSocket 心跳: 15s interval, 2 次 missed → 断开
```

#### 1.4.2 浏览器扩展 (background.ts) CDP 层

```typescript
// 白名单允许的 CDP 方法
const ALLOWED_CDP_METHODS = [
  'Page.enable', 'Page.disable', 'Page.navigate',
  'Runtime.evaluate', 'Runtime.callFunctionOn',
  'Network.getResponseBody', 'Network.enable',
  'DOM.getDocument', 'DOM.querySelector',
  'Input.dispatchMouseEvent', 'Input.dispatchKeyEvent',
  // ... 更多
];

// 窗口隔离策略
// • 专用自动化窗口 (与用户会话隔离)
// • 30s 空闲超时自动关闭
// • Tab 漂移检测与修复
```

#### 1.4.3 注册表机制 (registry.ts)

```typescript
// 全局单例注册表 (解决 npm link 隔离问题)
declare global { var __opencli_registry__: Map<string, CliCommand> | undefined; }
const _registry = globalThis.__opencli_registry__ ??= new Map<string, CliCommand>();

// 命令注册
cli({
  name: 'bilibili',
  subcommand: 'hot',
  strategy: 'public',  // or 'cookie' | 'header' | 'intercept' | 'ui'
  args: [...],
  pipeline: [...]      // 可选的管道步骤
});

// 策略派生运行时行为
// • PUBLIC → 无需浏览器
// • COOKIE/HEADER → navigateBefore: domain URL
// • UI → 始终需要浏览器
```

#### 1.4.4 适配器生命周期 (explore → synthesize)

```typescript
// Step 1: explore 探测行为
opencli explore https://example.com --site mysite
// 输出: explore bundle (包含 URL 模式、参数、认证信息)

// Step 2: synthesize 生成适配器
opencli synthesize mysite
// 输出: CLI 配置 YAML/JSON → 保存到 clis/ 目录

// Step 3: generate 一次性生成
opencli generate https://example.com --goal "hot"
```

---

## 第二章 · OpenCLI vs Hermes Agent 功能对标

### 2.1 功能矩阵

| 功能领域 | Hermes Agent | OpenCLI | OpenClaw 当前 | 接入优先级 |
|----------|-------------|---------|-------------|-----------|
| **浏览器控制** | 无 | ✅ CDP + 扩展 | ❌ | P0 |
| **CLI 适配器** | 45+ 工具 | ✅ 87+ | CLI-Anything 词典 | P0 |
| **会话持久化** | SQLite WAL + FTS5 | ❌ | Dapr State | P1 |
| **定时任务** | Cron 调度器 | ❌ | Watchdog | P2 |
| **技能系统** | Markdown 技能 | ❌ | SOUL.md | P1 |
| **自进化** | Trajectory 压缩 | ✅ synthesize | ❌ | P2 |
| **多平台** | 14+ Gateway | ❌ | 飞书/MCP | P2 |
| **记忆策略** | 8 种 Provider | ❌ | 5 层记忆 | P1 |

### 2.2 OpenCLI 独有优势 (Hermes 没有)

1. **浏览器会话复用**: 无需处理登录/2FA，直接使用用户已登录态
2. **零 LLM 成本**: 适配器执行为确定性 CLI，无 token 消耗
3. **确定性输出**: JSON/CSV/YAML/MD 多格式，天然管道友好
4. **适配器自生成**: `explore → synthesize → cascade` 闭环生成新 CLI
5. **Electron 应用控制**: Cursor/ChatGPT/Notion 等桌面应用 CDP 控制

### 2.3 Hermes 独有优势 (OpenCLI 没有)

1. **轨迹压缩**: 长程对话 15,250 token 预算保护
2. **多模型路由**: 15+ Provider + 凭证池轮转
3. **完整记忆系统**: FTS5 + 8 种策略 + 会话链
4. **Insights 提取**: 从执行轨迹自动提取改进洞察
5. **多平台 Gateway**: Telegram/Discord/Slack/Matrix 等

---

## 第三章 · OpenClaw 接入架构设计

### 3.1 接入层次

```
┌─────────────────────────────────────────────────────────────────┐
│                    OpenClaw 接入架构                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: 协议接入层 (Protocol Bridge)                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • MCP Server (Python) 暴露 OpenCLI 工具                  │   │
│  │ • 命令: opencli_<platform>_<action>                      │   │
│  │ • 示例: opencli_bilibili_hot, opencli_twitter_post     │   │
│  │ • HTTP 客户端 → opencli daemon (19825)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│  Layer 2: 适配器管理层 (Adapter Manager)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • opencli_adapter.ts: 适配器注册与生命周期               │   │
│  │ • browser_bridge.ts: 浏览器会话管理                     │   │
│  │ • synthesize_engine.ts: 适配器自生成                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│  Layer 3: 执行层集成 (M04/M11 对接)                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • M04 Tools: 将 OpenCLI 命令作为 ToolSet 暴露           │   │
│  │ • M11 Daemon: opencli daemon 进程管理                   │   │
│  │ • 跨系统协同: DAG 支持 OpenCLI 节点类型                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心模块设计

#### 3.2.1 opencli_client.ts

```typescript
/**
 * OpenCLI HTTP/WebSocket 客户端
 * 负责与 opencli daemon 通信
 */

// POST /command → 返回命令结果
async executeCommand(cmd: {
  id: string;
  site: string;
  action: string;
  args: Record<string, unknown>;
  timeout?: number;
}): Promise<OpenCLIResult>;

// GET /status → 守护进程状态
async getStatus(): Promise<{
  pid: number;
  uptime: number;
  extensionConnected: boolean;
  extensionVersion: string;
  pending: number;
}>;

// WebSocket /ext → 实时日志/心跳
onLog(callback: (entry: LogEntry) => void): void;
onHello(callback: (info: ExtensionInfo) => void): void;
```

#### 3.2.2 opencli_adapter_manager.ts

```typescript
/**
 * OpenCLI 适配器管理器
 * 负责注册、发现、生命周期管理
 */

class OpenCLIAdapterManager {
  // 从 cli-manifest.json 加载预定义适配器
  async loadManifest(): Promise<CliManifest>;

  // 从 clis/ 目录扫描用户适配器
  async discoverUserAdapters(): Promise<CliCommand[]>;

  // 注册适配器到 M04 Tools
  async registerToM04(commands: CliCommand[]): Promise<void>;

  // 检查适配器是否需要浏览器会话
  needsBrowserSession(cmd: CliCommand): boolean;

  // 验证适配器可执行性
  async validateAdapter(cmd: CliCommand): Promise<ValidationResult>;
}
```

#### 3.2.3 browser_bridge.ts

```typescript
/**
 * 浏览器桥接管理器
 * 封装 OpenCLI 的 CDP 能力
 */

class BrowserBridge {
  // 连接状态
  private extensionConnected: boolean = false;

  // 执行浏览器操作
  async click(selector: string): Promise<void>;
  async type(selector: string, text: string): Promise<void>;
  async navigate(url: string): Promise<void>;
  async evaluate(code: string): Promise<unknown>;
  async screenshot(): Promise<string>;  // base64

  // 标签页管理
  async createTab(url: string): Promise<number>;
  async closeTab(tabId: number): Promise<void>;
  async switchToTab(tabId: number): Promise<void>;

  // 网络捕获
  async captureNetwork requests(): Promise<NetworkRequest[]>;
}
```

#### 3.2.4 synthesize_engine.ts

```typescript
/**
 * 适配器自生成引擎
 * explore → synthesize → register 闭环
 */

class SynthesizeEngine {
  // Step 1: 探测网站行为
  async explore(url: string, siteName: string): Promise<ExploreBundle>;

  // Step 2: 生成适配器配置
  synthesize(bundle: ExploreBundle): Promise<SynthesizeOutput>;

  // Step 3: 注册到系统
  async register(adapter: CliCommand): Promise<void>;

  // Step 4: 验证可用性
  async test(adapter: CliCommand): Promise<boolean>;
}
```

---

## 第四章 · 分阶段接入计划

### 4.1 Phase A: 基础接入 (1-2 周)

#### A.1 依赖安装与环境配置

```bash
# OpenCLI 全局安装
npm install -g @jackwener/opencli

# 浏览器扩展安装
# 1. 下载 opencli-extension-v*.zip from Releases
# 2. chrome://extensions → 开发者模式 → 加载已解压

# 验证安装
opencli doctor
```

#### A.2 OpenCLI MCP Server 实现

```typescript
// src/infrastructure/opencli_mcp_server.ts

/**
 * OpenCLI MCP Server
 * 将 OpenCLI 命令通过 MCP 协议暴露给 OpenClaw
 */

// 工具列表
const OPENCLI_TOOLS = [
  // 热门平台
  'opencli_bilibili_hot',
  'opencli_twitter_trending',
  'opencli_reddit_hot',
  'opencli_hackernews_top',
  // 电商
  'opencli_amazon_search',
  'opencli_1688_search',
  // 社交
  'opencli_xiaohongshu_search',
  'opencli_zhihu_hot',
  // 开发者
  'opencli_github_trending',
  'opencli_gh_pr_list',
];

// 执行流程
async function handle_opencli_bilibili_hot(args: {
  limit?: number;
  format?: 'json' | 'csv' | 'md';
}) {
  const result = await daemonClient.executeCommand({
    id: uuid(),
    site: 'bilibili',
    action: 'hot',
    args: { limit: args.limit ?? 10, format: args.format ?? 'json' }
  });
  return formatOutput(result, args.format);
}
```

#### A.3 M04 Tools 集成

```typescript
// src/domain/m04/adapters/opencli_adapter.ts

/**
 * M04 OpenCLI 适配器
 * 将 OpenCLI 命令作为 ToolSet 接入执行层
 */

export class OpenCLIAdapter {
  readonly systemType = SystemType.OPENCLI;
  readonly commands: CliCommand[];

  async execute(context: ExecutionContext): Promise<ExecutionResult> {
    const { command, args } = context.metadata;
    const result = await this.opencliClient.executeCommand({
      id: context.request_id,
      site: command.site,
      action: command.action,
      args,
      timeout: command.timeout ?? 60000,
    });
    return { success: true, data: result };
  }

  // 浏览器会话协商
  async ensureBrowserSession(): Promise<void> {
    const status = await this.daemonClient.getStatus();
    if (!status.extensionConnected) {
      throw new Error('OpenCLI 浏览器扩展未连接');
    }
  }
}
```

#### A.4 验收标准

- [ ] `opencli doctor` 返回成功
- [ ] MCP Server 启动正常，端口 8080
- [ ] `opencli bilibili hot` 返回 JSON 数据
- [ ] M04 ToolSet 包含 20+ OpenCLI 命令

---

### 4.2 Phase B: 浏览器桥接 (2-3 周)

#### B.1 BrowserBridge 实现

```typescript
// src/infrastructure/browser_bridge.ts

/**
 * 浏览器桥接客户端
 * 封装 OpenCLI daemon 的浏览器控制能力
 */

export class BrowserBridge {
  private ws: WebSocket;
  private daemonPort: number = 19825;

  async connect(): Promise<void> {
    // 1. 检查 daemon 状态
    const status = await this.httpGet('/status');
    if (!status.extensionConnected) {
      throw new Error('浏览器扩展未连接');
    }

    // 2. 建立 WebSocket 监听日志
    this.ws = new WebSocket(`ws://127.0.0.1:${this.daemonPort}/ext`);
  }

  // 鼠标点击
  async click(selector: string): Promise<void> {
    await this.sendCommand({
      type: 'exec',
      action: 'click',
      selector,
    });
  }

  // 键盘输入
  async type(selector: string, text: string): Promise<void> {
    await this.sendCommand({
      type: 'exec',
      action: 'type',
      selector,
      text,
    });
  }

  // 页面导航
  async navigate(url: string, waitUntil: 'load' | 'networkidle' = 'load'): Promise<void> {
    await this.sendCommand({
      type: 'navigate',
      url,
      waitUntil,
    });
  }

  // JavaScript 执行
  async evaluate<T = unknown>(code: string): Promise<T> {
    const result = await this.sendCommand({
      type: 'exec',
      action: 'evaluate',
      expression: code,
    });
    return result.value as T;
  }

  // 截图
  async screenshot(): Promise<string> {
    const result = await this.sendCommand({ type: 'screenshot' });
    return result.data;  // base64
  }
}
```

#### B.2 M11 Daemon 进程管理

```typescript
// src/domain/m11/daemon_manager.ts 增强

/**
 * OpenCLI Daemon 进程管理
 * 集成到 M11 守护进程三层实现
 */

export class OpenCLIDaemonManager {
  private process: ChildProcess | null = null;
  private port: number = 19825;

  async start(): Promise<void> {
    // 检查端口是否已被占用
    const inUse = await this.isPortInUse(this.port);
    if (inUse) {
      console.log('[OpenCLI] Daemon already running on port', this.port);
      return;
    }

    // 启动 opencli daemon
    this.process = spawn('opencli', ['daemon'], {
      stdio: 'pipe',
      env: { ...process.env, OPENCLI_DAEMON_PORT: String(this.port) }
    });

    // 等待启动完成
    await this.waitForPort(this.port, 5000);
  }

  async stop(): Promise<void> {
    if (!this.process) return;
    try {
      await this.httpPost('/shutdown', {});
    } catch {
      this.process.kill();
    }
    this.process = null;
  }

  async healthCheck(): Promise<boolean> {
    try {
      const res = await this.httpGet('/ping');
      return res.ok === true;
    } catch {
      return false;
    }
  }
}
```

#### B.3 验收标准

- [ ] 浏览器扩展成功连接 daemon
- [ ] `click`, `type`, `navigate` 操作正常
- [ ] `screenshot` 返回 base64 图片
- [ ] M11 守护进程自动启动/停止 OpenCLI daemon

---

### 4.3 Phase C: 技能自合成 (2-3 周)

#### C.1 SynthesizeEngine 实现

```typescript
// src/infrastructure/synthesize_engine.ts

/**
 * 适配器自生成引擎
 * 实现 OpenCLI 的 explore → synthesize 闭环
 */

export class SynthesizeEngine {
  // 探测网站行为
  async explore(url: string, siteName: string): Promise<ExploreBundle> {
    const process = spawn('opencli', ['explore', url, '--site', siteName], {
      stdio: 'pipe'
    });

    let output = '';
    process.stdout.on('data', (d) => output += d.toString());

    return new Promise((resolve, reject) => {
      process.on('close', (code) => {
        if (code === 0) {
          resolve(JSON.parse(output));
        } else {
          reject(new Error(`explore failed: ${code}`));
        }
      });
    });
  }

  // 生成适配器
  async synthesize(siteName: string): Promise<CliCommand> {
    const process = spawn('opencli', ['synthesize', siteName], {
      stdio: 'pipe'
    });

    let yaml = '';
    process.stdout.on('data', (d) => yaml += d.toString());

    return new Promise((resolve, reject) => {
      process.on('close', (code) => {
        if (code === 0) {
          resolve(parseYaml(yaml));  // 转换为 CliCommand
        } else {
          reject(new Error(`synthesize failed: ${code}`));
        }
      });
    });
  }

  // 完整闭环
  async createAdapter(url: string, siteName: string): Promise<CliCommand> {
    // 1. 探测
    const bundle = await this.explore(url, siteName);

    // 2. 生成
    const adapter = await this.synthesize(siteName);

    // 3. 注册
    await this.registerAdapter(adapter);

    // 4. 验证
    const valid = await this.testAdapter(adapter);
    if (!valid) {
      throw new Error(`Adapter validation failed for ${siteName}`);
    }

    return adapter;
  }
}
```

#### C.2 技能自合成 Hook

```typescript
// src/domain/hooks.ts 增强

/**
 * 技能自合成钩子
 * 当 Agent 发现现有工具无法满足需求时触发
 */

export class SkillSynthesisHook {
  readonly name = 'onSkillSynthesisNeeded';
  readonly description = '当任务需要但工具缺失时自动触发技能合成';

  async trigger(context: HookContext): Promise<SkillSynthesisResult> {
    const { task, failedAttempts, suggestedTools } = context;

    // 检查是否满足合成条件
    if (failedAttempts < 3 || !suggestedTools.length) {
      return { triggered: false };
    }

    // 调用合成引擎
    const engine = new SynthesizeEngine();
    const adapter = await engine.createAdapter(
      suggestedTools[0].url,
      suggestedTools[0].siteName
    );

    return {
      triggered: true,
      adapter,
      message: `已为 ${adapter.name} 生成新适配器`,
    };
  }
}
```

#### C.3 验收标准

- [ ] `opencli explore` 成功探测网站
- [ ] `opencli synthesize` 生成有效 YAML
- [ ] 生成的适配器可正常执行
- [ ] Hook 正确触发合成流程

---

### 4.4 Phase D: 高级特性 (3-4 周)

#### D.1 Electron 应用控制

```typescript
/**
 * 桌面应用 CDP 控制
 * 支持 Cursor, ChatGPT, Notion, Codex 等
 */

export class DesktopAppBridge {
  // Cursor Composer 控制
  async cursorComposer(command: string): Promise<string> {
    return this.executeAppCommand({
      app: 'cursor',
      endpoint: 'ws://localhost:9222',
      command,
    });
  }

  // Notion 页面读写
  async notionSearch(query: string): Promise<NotionPage[]> {
    return this.executeAppCommand({
      app: 'notion',
      action: 'search',
      args: { query },
    });
  }
}
```

#### D.2 CLI-Anything 集成增强

```typescript
/**
 * CLI-Anything 适配器集群
 * 87+ 预构建命令直接可用
 */

export class CLIAnythingHub {
  private adapters: Map<string, CliCommand>;

  async initialize(): Promise<void> {
    // 从 mapping_dictionaries.json 加载
    const manifest = await readFile('src/infrastructure/execution/cli_dictionary/mapping_dictionaries.json');
    this.adapters = this.parseManifest(manifest);

    // 动态安装所需适配器
    for (const adapter of this.adapters.values()) {
      await this.ensureInstalled(adapter);
    }
  }

  // 按类别获取适配器
  getAdaptersByCategory(category: string): CliCommand[] {
    return [...this.adapters.values()].filter(a => a.category === category);
  }

  // 执行适配器
  async execute(adapterName: string, args: Record<string, unknown>): Promise<unknown> {
    const adapter = this.adapters.get(adapterName);
    if (!adapter) throw new Error(`Unknown adapter: ${adapterName}`);

    return opencliClient.executeCommand({
      id: uuid(),
      site: adapter.name,
      action: adapter.defaultAction,
      args,
    });
  }
}
```

#### D.3 多适配器编排

```typescript
/**
 * 跨平台聚合工作流
 * 例: 搜索 B站热门 → 转发 Twitter → 存档 Notion
 */

export class CrossPlatformWorkflow {
  async execute(steps: WorkflowStep[]): Promise<WorkflowResult> {
    const results: Record<string, unknown> = {};

    for (const step of steps) {
      const { adapter, action, args } = step;
      const result = await cliAnythingHub.execute(adapter, { action, ...args });
      results[`${adapter}_${action}`] = result;

      // 链式传递: 上一步输出作为下一步输入
      if (step.pipeTo) {
        steps.find(s => s.id === step.pipeTo).input = result;
      }
    }

    return { success: true, results };
  }
}
```

---

## 第五章 · 与现有系统集成

### 5.1 M01 编排引擎集成

```typescript
// src/domain/m01/orchestrator.ts 增强

/**
 * OpenCLI 路由决策
 * 在 handleOrchestration 中添加 OpenCLI 判断
 */

private async handleOrchestration(request, dagPlan, startTime) {
  // 检查是否涉及 OpenCLI 命令
  const opencliNodes = dagPlan.nodes.filter(n =>
    n.systemType === SystemType.OPENCLI
  );

  if (opencliNodes.length > 0) {
    // 确保 OpenCLI daemon 运行
    await this.opencliDaemonManager.ensureRunning();
  }

  // 继续原有 DAG 执行
}
```

### 5.2 M04 工具调用集成

```typescript
// src/domain/m04/coordinator.ts 增强

/**
 * OpenCLI ToolSet 注册
 * 在 coordinator 初始化时注册
 */

async initialize() {
  // 注册 OpenCLI 适配器
  this.adapters.set(SystemType.OPENCLI, new OpenCLIAdapter());

  // 加载所有内置命令
  const opencliAdapters = await opencliAdapterManager.loadManifest();
  for (const cmd of opencliAdapters) {
    this.tools.register({
      name: `opencli_${cmd.site}_${cmd.action}`,
      description: cmd.description,
      parameters: cmd.args,
      executor: SystemType.OPENCLI,
    });
  }
}
```

### 5.3 M06 记忆系统集成

```typescript
// src/domain/m06/memory/pipeline/semantic_writer.ts 增强

/**
 * 适配器执行记录存入记忆
 * 用于跨会话复用成功经验
 */

async writeExecutionRecord(record: {
  adapter: string;
  args: Record<string, unknown>;
  result: unknown;
  success: boolean;
  timestamp: number;
}) {
  // 存入 persistent_memory 层
  await this.memoryLayers.persistent.commit({
    type: 'opencli_execution',
    content: JSON.stringify(record),
    tags: [record.adapter, record.success ? 'success' : 'failure'],
    embedding: await this.embedder.embed(
      `${record.adapter}: ${JSON.stringify(record.args)}`
    ),
  });
}
```

### 5.4 M08 学习系统集成

```typescript
// src/domain/m08/nightly_distiller.ts 增强

/**
 * 适配器使用分析
 * 夜间复盘时分析哪些适配器最常用/最成功
 */

async analyzeAdapterUsage(stats: AssetStats): Promise<AdapterInsight> {
  // 发现高频但低成功率 → 标记为待优化
  // 发现新成功路径 → 建议添加到 Skill 系统
  // 发现高频成功 → 考虑制作宏命令
}
```

---

## 第六章 · 配置文件

### 6.1 opencli.config.ts

```typescript
// src/infrastructure/config/opencli.config.ts

export const OpenCLIConfig = {
  // Daemon 配置
  daemon: {
    port: parseInt(process.env.OPENCLI_DAEMON_PORT ?? '19825', 10),
    startupTimeout: 5000,
    healthCheckInterval: 30000,
  },

  // 浏览器扩展配置
  browser: {
    connectTimeout: 30000,
    commandTimeout: 60000,
    exploreTimeout: 120000,
    idleTimeout: 30000,
  },

  // 适配器管理
  adapters: {
    manifestPath: './cli-manifest.json',
    userAdaptersDir: './clis',
    autoInstall: true,
  },

  // MCP Server 配置
  mcp: {
    enabled: true,
    port: 8080,
    tools: [
      'opencli_bilibili_hot',
      'opencli_twitter_trending',
      'opencli_github_trending',
      // ... 更多
    ],
  },

  // 技能自合成
  synthesis: {
    enabled: true,
    triggerThreshold: 3,  // 失败 3 次后触发
    testAfterCreate: true,
  },
};
```

### 6.2 docker-compose.yml 增强

```yaml
services:
  # ... 现有服务 ...

  opencli-daemon:
    image: node:21-alpine
    command: sh -c "npm install -g @jackwener/opencli && opencli daemon"
    ports:
      - "19825:19825"
    volumes:
      - opencli-data:/root/.opencli
    environment:
      - OPENCLI_DAEMON_PORT=19825
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:19825/ping"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  opencli-data:
```

---

## 第七章 · 验收清单

### 7.1 Phase A (基础接入)

| 任务 | 验收标准 | 状态 |
|------|----------|------|
| OpenCLI 安装 | `opencli doctor` 成功 | ⏳ |
| 浏览器扩展安装 | 扩展连接 daemon 成功 | ⏳ |
| MCP Server 实现 | 端口 8080 可用 | ⏳ |
| M04 工具注册 | 20+ 命令可用 | ⏳ |
| 端到端测试 | `opencli bilibili hot` → OpenClaw → 结果 | ⏳ |

### 7.2 Phase B (浏览器桥接)

| 任务 | 验收标准 | 状态 |
|------|----------|------|
| BrowserBridge 实现 | click/type/navigate 可用 | ⏳ |
| 截图功能 | 返回 base64 图片 | ⏳ |
| M11 进程管理 | 自动启动/停止 daemon | ⏳ |
| 错误处理 | 超时/扩展断开处理正确 | ⏳ |

### 7.3 Phase C (技能自合成)

| 任务 | 验收标准 | 状态 |
|------|----------|------|
| explore 功能 | 网站探测成功 | ⏳ |
| synthesize 功能 | YAML 生成成功 | ⏳ |
| 自动注册 | 新适配器立即可用 | ⏳ |
| Hook 触发 | 失败 3 次后触发合成 | ⏳ |

### 7.4 Phase D (高级特性)

| 任务 | 验收标准 | 状态 |
|------|----------|------|
| Cursor 控制 | Composer 操作成功 | ⏳ |
| Notion 集成 | 页面读写成功 | ⏳ |
| CLI-Anything | 87+ 命令可用 | ⏳ |
| 跨平台工作流 | 多适配器编排成功 | ⏳ |

---

## 第八章 · 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 浏览器扩展安装复杂 | 用户体验差 | 提供自动化安装脚本 |
| OpenCLI daemon 崩溃 | 浏览器控制失效 | M11 自动重启 + 健康检查 |
| 登录态过期 | 操作失败 | 添加 Cookie 刷新机制 |
| CDP 版本不兼容 | 扩展失效 | 锁定 Chrome 版本 |
| 适配器生成失败 | 新平台无法接入 | 提供手动注册接口 |

---

## 第九章 · 总结

### 9.1 核心价值

接入 OpenCLI 后，OpenClaw 将获得：

1. **零成本浏览器控制**: 无需 LLM token，直接操作用户已登录浏览器
2. **87+ 预建适配器**: 开箱即用的中国平台支持 (B站/小红书/知乎/淘宝等)
3. **确定性执行**: CLI 命令保证相同输入→相同输出，管道友好
4. **自进化能力**: `explore → synthesize` 自动生成新平台适配器
5. **Electron 应用控制**: 覆盖 Cursor/ChatGPT/Notion 等桌面应用

### 9.2 时间估算

| Phase | 工期 | 工作量 |
|-------|------|--------|
| Phase A: 基础接入 | 1-2 周 | 1 人 |
| Phase B: 浏览器桥接 | 2-3 周 | 1 人 |
| Phase C: 技能自合成 | 2-3 周 | 1 人 |
| Phase D: 高级特性 | 3-4 周 | 1 人 |
| **总计** | **8-12 周** | **1 人** |

### 9.3 与 Hermes Agent 协同

OpenCLI 填补了 Hermes Agent 在**浏览器自动化**方面的空白：

```
Hermes Agent (记忆/学习/多平台)
    ↓ 互补
OpenCLI (浏览器/CLI/确定性执行)
    ↓ 共同注入
OpenClaw (多 Agent 协作 + 意图理解 + 编排)
```

---

*本文档结合 OpenCLI 源码深度分析 (2026-04-15) 与 Hermes Agent 源码考察报告 (改造计划.md) 编制。*
