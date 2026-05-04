/**
 * M11 执行器适配器
 * ================================================
 * 五大执行器统一接口
 * Claude Code · CLI-Anything · Midscene.js · UI-TARS · OpenCLI
 * ================================================
 */

import { spawn } from 'child_process';
import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import {
  ExecutorType,
  ExecutorStatus,
  ExecutorTask,
  ExecutorResult,
  SandboxType,
} from '../types';

import { gVisorSandbox, riskAssessor, RiskAssessment } from '../sandbox';

// 动态导入 OpenCLI 客户端 (延迟加载)
let opencliClient: any = null;
async function getOpenCLIClient() {
  if (!opencliClient) {
    try {
      const module = await import('../../../infrastructure/execution/opencli_http_client');
      opencliClient = module.opencliHttpClient;
    } catch {
      opencliClient = null;
    }
  }
  return opencliClient;
}

// ============================================
// 执行器适配器
// ============================================

/**
 * 执行器适配器
 *
 * 统一接口封装四大执行器：
 * - Claude Code: 代码编写·文件系统操作·bash命令
 * - CLI-Anything: GUI软件CLI化
 * - Midscene.js: Web视觉自动化
 * - UI-TARS: 桌面GUI兜底
 */
export class ExecutorAdapter {
  private taskQueue: ExecutorTask[];
  private activeTask: ExecutorTask | null;
  private riskAssessorThreshold: number;

  constructor() {
    this.taskQueue = [];
    this.activeTask = null;
    this.riskAssessorThreshold = 0.7;
  }

  /**
   * 提交执行任务
   */
  async submit(
    type: ExecutorType,
    instruction: string,
    params: Record<string, any> = {},
    sandboxed: boolean = true
  ): Promise<string> {
    const taskId = `task_${Date.now()}_${crypto.randomUUID().replace(/-/g, '').substring(0, 9)}`;

    const task: ExecutorTask = {
      id: taskId,
      type,
      instruction,
      params,
      status: ExecutorStatus.IDLE,
      sandboxed,
      created_at: new Date().toISOString(),
      retry_count: 0,
      max_retries: 3,
    };

    this.taskQueue.push(task);
    return taskId;
  }

  /**
   * 执行任务
   */
  async execute(taskId: string): Promise<ExecutorResult> {
    const task = this.findTask(taskId);
    if (!task) {
      return {
        success: false,
        task_id: taskId,
        error: 'Task not found',
        execution_time_ms: 0,
      };
    }

    const startTime = Date.now();
    task.status = ExecutorStatus.RUNNING;
    task.started_at = new Date().toISOString();
    this.activeTask = task;

    try {
      // 风险评估
      const riskAssessment = riskAssessor.assess(task.instruction);
      if (riskAssessment.level === 'critical' || riskAssessment.requires_approval) {
        throw new Error(`High-risk operation blocked: ${riskAssessment.reason}`);
      }

      // 根据类型执行
      let result: any;
      switch (task.type) {
        case ExecutorType.CLAUDE_CODE:
          result = await this.executeClaudeCode(task);
          break;
        case ExecutorType.CLI_ANYTHING:
          result = await this.executeCLIAnything(task);
          break;
        case ExecutorType.MIDSCENE:
          result = await this.executeMidscene(task);
          break;
        case ExecutorType.UI_TARS:
          result = await this.executeUITARS(task);
          break;
        case ExecutorType.OPENCLI:
          result = await this.executeOpenCLI(task);
          break;
        default:
          throw new Error(`Unknown executor type: ${task.type}`);
      }

      task.status = ExecutorStatus.COMPLETED;
      task.completed_at = new Date().toISOString();
      task.result = result;

      return {
        success: true,
        task_id: taskId,
        result,
        execution_time_ms: Date.now() - startTime,
      };
    } catch (error) {
      task.status = ExecutorStatus.FAILED;
      task.error = error instanceof Error ? error.message : 'Unknown error';
      task.retry_count++;

      // 自动重试
      if (task.retry_count < task.max_retries) {
        task.status = ExecutorStatus.IDLE;
        return this.execute(taskId);
      }

      return {
        success: false,
        task_id: taskId,
        error: task.error,
        execution_time_ms: Date.now() - startTime,
      };
    } finally {
      this.activeTask = null;
    }
  }

  /**
   * Claude Code执行 (真实调用)
   * SECURITY FIX: 使用数组形式传递参数，防止命令注入
   */
  private async executeClaudeCode(task: ExecutorTask): Promise<any> {
    const { instruction, sandboxed, params } = task;

    // SECURITY: 使用数组形式传递命令和参数，而非字符串拼接
    const claudeArgs = ['--print', instruction];

    if (sandboxed) {
      // 在 gVisor 中执行 - 使用数组形式
      const sandboxResult = await gVisorSandbox.execute(
        ['claude', ...claudeArgs],
        { type: SandboxType.GVISOR, timeout_ms: params.timeout_ms || 120000 }
      );

      if (!sandboxResult.success) {
        throw new Error(`Sandbox execution failed: ${sandboxResult.stderr}`);
      }

      return { output: sandboxResult.stdout, sandboxed: true };
    }

    // 直接执行 (信任的命令) - 数组形式
    return new Promise((resolve, reject) => {
      const proc = spawn('claude', claudeArgs, {
        timeout: params.timeout_ms || 120000,
      });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });
      proc.stderr?.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code) => {
        if (code === 0) {
          resolve({ output: stdout, sandboxed: false });
        } else {
          reject(new Error(`Claude Code failed: ${stderr}`));
        }
      });

      proc.on('error', (error) => reject(error));
    });
  }

  /**
   * CLI-Anything执行 (真实调用)
   * SECURITY FIX: 添加工具名白名单验证
   */
  // 允许的工具名白名单
  private readonly ALLOWED_TOOLS = new Set([
    'gimp', 'blender', 'ffmpeg', 'imagemagick', 'zotero',
    'audacity', 'inkscape', 'libreoffice', 'gthumb'
  ]);

  private async executeCLIAnything(task: ExecutorTask): Promise<any> {
    const { instruction, params } = task;

    const toolName = params.tool_name || this.extractToolName(instruction);

    // SECURITY: 验证工具名白名单
    if (!this.ALLOWED_TOOLS.has(toolName)) {
      return {
        tool: toolName,
        instruction,
        result: `CLI-Anything: tool "${toolName}" not in allowed list`,
        found: false,
        error: 'Tool not allowed',
      };
    }

    // SECURITY: 验证路径格式，防止路径遍历
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const hubPath = path.join(homeDir, '.deerflow', 'cli-hub', `${toolName}.sh`);

    // 验证最终路径确实在预期目录内
    if (!hubPath.startsWith(path.join(homeDir, '.deerflow', 'cli-hub'))) {
      return {
        tool: toolName,
        result: 'CLI-Anything: invalid path traversal attempt',
        found: false,
        error: 'Path traversal detected',
      };
    }

    // 检查 CLI hub 工具是否存在
    const toolExists = fs.existsSync(hubPath);

    if (!toolExists) {
      return {
        tool: toolName,
        instruction,
        result: `CLI-Anything: tool not found in hub`,
        hub_path: hubPath,
        found: false,
      };
    }

    // 执行 CLI wrapper
    return new Promise((resolve, reject) => {
      const proc = spawn('sh', [hubPath, instruction], {
        timeout: params.timeout_ms || 60000,
      });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });
      proc.stderr?.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code) => {
        resolve({
          tool: toolName,
          instruction,
          result: stdout || `CLI-Anything: ${toolName} executed`,
          hub_path: hubPath,
          found: true,
          exit_code: code,
        });
      });

      proc.on('error', (error) => reject(error));
    });
  }

  /**
   * Midscene.js执行 (真实调用)
   */
  private async executeMidscene(task: ExecutorTask): Promise<any> {
    const { instruction, params } = task;

    const url = params.url || 'https://example.com';
    const action = params.action || 'navigate_and_extract';
    const midsceneScript = params.script_path || 'navigate_and_extract.js';

    // 检查 Midscene.js 是否可用
    const midsceneAvailable = await this.checkMidsceneAvailable();

    if (!midsceneAvailable) {
      return {
        url,
        action,
        instruction,
        result: `Midscene: not available`,
        available: false,
      };
    }

    // 构建 Midscene.js 命令
    const midsceneCmd = `npx midscene ${action} --url "${url}" --instruction "${instruction.replace(/"/g, '\\"')}"`;

    // 在沙盒中执行 Midscene.js
    const sandboxResult = await gVisorSandbox.execute(midsceneCmd, {
      type: SandboxType.DOCKER,
      timeout_ms: params.timeout_ms || 120000,
    });

    return {
      url,
      action,
      instruction,
      result: sandboxResult.stdout || `Midscene: ${action} completed`,
      available: true,
      tokens_saved: '~40% vs DOM-based',
    };
  }

  /**
   * UI-TARS执行 (真实调用)
   */
  private async executeUITARS(task: ExecutorTask): Promise<any> {
    const { instruction, params } = task;

    const targetApp = params.app || 'unknown';
    const uiTarsAvailable = await this.checkUITARSAvailable();

    if (!uiTarsAvailable) {
      return {
        app: targetApp,
        instruction,
        result: `UI-TARS: not available`,
        available: false,
      };
    }

    // UI-TARS desktop API 调用
    const uiTarsCmd = `ui-tars --app "${targetApp}" --instruction "${instruction.replace(/"/g, '\\"')}"`;

    const sandboxResult = await gVisorSandbox.execute(uiTarsCmd, {
      type: SandboxType.GVISOR,
      timeout_ms: params.timeout_ms || 180000,
    });

    return {
      app: targetApp,
      instruction,
      result: sandboxResult.stdout || `UI-TARS: completed on ${targetApp}`,
      available: true,
      use_case_count: (params.use_count || 0) + 1,
    };
  }

  /**
   * OpenCLI 执行 (浏览器自动化)
   * 支持: 导航、点击、截图、提取数据
   */
  private async executeOpenCLI(task: ExecutorTask): Promise<any> {
    const { instruction, params } = task;

    // 检查 OpenCLI 是否可用
    const opencliAvailable = await this.checkOpenCLIAvailable();

    if (!opencliAvailable) {
      return {
        instruction,
        result: `OpenCLI: not available (daemon not running or extension not connected)`,
        available: false,
        daemon: false,
        extension: false,
      };
    }

    // 检测是否为平台命令 (如: opencli 36kr hot, opencli bilibili search xxx)
    // 平台命令特征: 包含平台名 + 命令，但不含浏览器动作动词
    const isPlatformCommand = this.detectPlatformCommand(instruction);
    if (isPlatformCommand) {
      return this.executeOpenCLIPlatform(task);
    }

    const client = await getOpenCLIClient();
    if (!client) {
      return {
        instruction,
        result: `OpenCLI: client module not loaded`,
        available: false,
      };
    }

    // 解析指令类型
    const action = params.action || this.parseOpenCLIAction(instruction);
    const url = params.url || this.extractUrl(instruction);

    switch (action) {
      case 'navigate':
      case 'open':
        const navResult = await client.open(url);
        return {
          action: 'navigate',
          url,
          result: navResult.success ? `Opened ${url}` : `Failed: ${navResult.error}`,
          available: true,
          daemon: true,
          extension: true,
        };

      case 'click':
        const clickIndex = params.index || this.extractElementIndex(instruction);
        if (clickIndex === null) {
          return { action: 'click', result: 'No element index provided', success: false };
        }
        const clickResult = await client.click(clickIndex);
        return {
          action: 'click',
          index: clickIndex,
          result: clickResult.success ? `Clicked element ${clickIndex}` : `Failed: ${clickResult.error}`,
          available: true,
        };

      case 'type':
        const typeIndex = params.index || this.extractElementIndex(instruction);
        const text = params.text || this.extractTypedText(instruction);
        if (typeIndex === null || !text) {
          return { action: 'type', result: 'Missing index or text', success: false };
        }
        const typeResult = await client.type(typeIndex, text);
        return {
          action: 'type',
          index: typeIndex,
          text,
          result: typeResult.success ? `Typed at element ${typeIndex}` : `Failed: ${typeResult.error}`,
          available: true,
        };

      case 'screenshot':
        const screenshotPath = params.path || params.screenshot_path;
        const screenshotResult = await client.screenshot(screenshotPath);
        return {
          action: 'screenshot',
          path: screenshotResult.path,
          result: screenshotResult.success ? `Screenshot saved` : `Failed: ${screenshotResult.error}`,
          available: true,
        };

      case 'state':
      case 'get_state':
        const state = await client.getState();
        return {
          action: 'state',
          state,
          result: state ? `URL: ${state.url}, Title: ${state.title}, Elements: ${state.elements.length}` : 'Failed to get state',
          available: true,
        };

      case 'wait':
        const waitType = params.wait_type || 'time';
        const waitValue = params.wait_value || '3';
        const waitResult = await client.wait(waitType as any, waitValue);
        return {
          action: 'wait',
          type: waitType,
          value: waitValue,
          result: waitResult.success ? `Waited for ${waitType}: ${waitValue}` : `Failed: ${waitResult.error}`,
          available: true,
        };

      case 'close':
        const closeResult = await client.close();
        return {
          action: 'close',
          result: closeResult.success ? 'Browser closed' : `Failed: ${closeResult.error}`,
          available: true,
        };

      default:
        // 通用执行: 直接传递指令
        const genericResult = await client.executeBrowserCommand([action, ...Object.values(params).filter(Boolean)]);
        return {
          action,
          instruction,
          result: genericResult.success ? genericResult.output : `Failed: ${genericResult.error}`,
          available: true,
        };
    }
  }

  /**
   * 检查 OpenCLI daemon 是否可用
   */
  private async checkOpenCLIAvailable(): Promise<boolean> {
    return new Promise((resolve) => {
      // 使用 opencli doctor 检查状态
      const proc = spawn('opencli', ['doctor'], { timeout: 10000 });
      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });
      proc.stderr?.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code) => {
        // daemon 运行中即认为可用 (extension 可后续连接)
        resolve(stdout.includes('daemon') || stdout.includes('running'));
      });

      proc.on('error', () => resolve(false));
    });
  }

  /**
   * 执行 OpenCLI 平台命令 (非浏览器)
   * 支持: 36kr, bilibili, xiaohongshu 等 89 个平台
   */
  private async executeOpenCLIPlatform(task: ExecutorTask): Promise<any> {
    const { instruction, params } = task;

    const site = params.site || this.extractSite(instruction);
    const cmd = params.command || this.extractCommand(instruction);
    const input = params.input || params.url || this.extractInput(instruction);

    if (!site || !cmd) {
      return {
        instruction,
        result: 'OpenCLI Platform: missing site or command',
        success: false,
        available: true,
      };
    }

    // 构建命令
    const cmdArgs = [site, cmd];
    if (input) {
      cmdArgs.push(input);
    }

    // 添加额外参数
    Object.entries(params).forEach(([key, value]) => {
      if (!['site', 'command', 'input', 'url', 'action'].includes(key) && value) {
        cmdArgs.push(`--${key}`, String(value));
      }
    });

    return new Promise((resolve) => {
      const proc = spawn('opencli', cmdArgs, { timeout: params.timeout_ms || 60000 });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });
      proc.stderr?.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code) => {
        resolve({
          site,
          command: cmd,
          input,
          success: code === 0,
          stdout,
          stderr,
          exitCode: code,
          result: code === 0 ? stdout : `Failed: ${stderr}`,
          available: true,
        });
      });

      proc.on('error', (error) => {
        resolve({
          site,
          command: cmd,
          success: false,
          error: error.message,
          available: true,
        });
      });
    });
  }

  /**
   * 从指令中提取站点
   */
  private extractSite(instruction: string): string | null {
    const platforms = [
      'bilibili', 'xiaohongshu', 'douyin', 'tiktok', 'weibo', 'zhihu',
      'taobao', 'jd', '1688', 'github', 'google', '36kr', 'xueqiu'
    ];

    const lower = instruction.toLowerCase();
    for (const platform of platforms) {
      if (lower.includes(platform)) {
        return platform;
      }
    }
    return null;
  }

  /**
   * 从指令中提取命令
   */
  private extractCommand(instruction: string): string | null {
    const lower = instruction.toLowerCase();
    if (lower.includes('search')) return 'search';
    if (lower.includes('hot') || lower.includes('trending')) return 'hot';
    if (lower.includes('video')) return 'video';
    if (lower.includes('article')) return 'article';
    if (lower.includes('item') || lower.includes('product')) return 'item';
    if (lower.includes('download')) return 'download';
    if (lower.includes('user') || lower.includes('profile')) return 'user';
    return 'search'; // 默认搜索
  }

  /**
   * 从指令中提取输入
   */
  private extractInput(instruction: string): string | null {
    // 尝试提取 URL
    const urlMatch = instruction.match(/(https?:\/\/[^\s]+)/);
    if (urlMatch) return urlMatch[1];

    // 尝试提取引号中的文本
    const quoteMatch = instruction.match(/["']([^"']+)["']/);
    if (quoteMatch) return quoteMatch[1];

    // 尝试提取最后的关键字
    const words = instruction.split(/\s+/);
    return words[words.length - 1] || null;
  }

  /**
   * 从指令中解析 OpenCLI 动作
   */
  private parseOpenCLIAction(instruction: string): string {
    const lower = instruction.toLowerCase();
    if (lower.includes('navigate') || lower.includes('go to') || lower.includes('open')) return 'navigate';
    if (lower.includes('click')) return 'click';
    if (lower.includes('type') || lower.includes('input')) return 'type';
    if (lower.includes('screenshot') || lower.includes('截图')) return 'screenshot';
    if (lower.includes('state') || lower.includes('page')) return 'state';
    if (lower.includes('wait')) return 'wait';
    if (lower.includes('close') || lower.includes('shutdown')) return 'close';
    return 'state'; // 默认获取状态
  }

  /**
   * 从指令中提取 URL
   */
  private extractUrl(instruction: string): string {
    const urlMatch = instruction.match(/(https?:\/\/[^\s]+)/);
    return urlMatch ? urlMatch[1] : 'https://example.com';
  }

  /**
   * 从指令中提取元素索引
   */
  private extractElementIndex(instruction: string): number | null {
    const indexMatch = instruction.match(/\[(\d+)\]/);
    return indexMatch ? parseInt(indexMatch[1]) : null;
  }

  /**
   * 从指令中提取输入文本
   */
  private extractTypedText(instruction: string): string | null {
    const textMatch = instruction.match(/(?:type|input)\s+.+\s+["'](.+)["']/i);
    return textMatch ? textMatch[1] : null;
  }

  /**
   * 检测是否为平台命令 (非浏览器自动化)
   * 平台命令: opencli 36kr hot, opencli bilibili search xxx
   * 浏览器命令: opencli navigate https://..., opencli click [1]
   */
  private detectPlatformCommand(instruction: string): boolean {
    const lower = instruction.toLowerCase();

    // 浏览器动作关键词 - 有这些的是浏览器命令
    const browserActions = ['navigate', 'open', 'click', 'type', 'screenshot', 'wait', 'close', 'get_state', 'page'];
    for (const action of browserActions) {
      if (lower.includes(action)) return false;
    }

    // 平台关键词 - 有这些的是平台命令
    const platformKeywords = [
      '36kr', 'bilibili', 'xiaohongshu', 'douyin', 'tiktok',
      'weibo', 'zhihu', 'taobao', 'jd', '1688', 'github',
      'google', 'baidu', 'xueqiu', 'youtube', 'instagram'
    ];

    for (const platform of platformKeywords) {
      if (lower.includes(platform)) return true;
    }

    return false;
  }

  /**
   * 检查 Midscene.js 是否可用
   */
  private async checkMidsceneAvailable(): Promise<boolean> {
    return new Promise((resolve) => {
      const proc = spawn('which', ['midscene']);
      proc.on('close', (code) => resolve(code === 0));
      proc.on('error', () => resolve(false));
    });
  }

  /**
   * 检查 UI-TARS 是否可用
   */
  private async checkUITARSAvailable(): Promise<boolean> {
    return new Promise((resolve) => {
      const proc = spawn('which', ['ui-tars']);
      proc.on('close', (code) => resolve(code === 0));
      proc.on('error', () => resolve(false));
    });
  }

  /**
   * 从指令中提取工具名
   */
  private extractToolName(instruction: string): string {
    const match = instruction.match(/(gimp|blender|ffmpeg|imagemagick|zotero|audacity|inkscape|libreoffice|gthumb)/i);
    return match ? match[1].toLowerCase() : 'unknown';
  }

  /**
   * 查找任务
   */
  private findTask(taskId: string): ExecutorTask | undefined {
    return this.taskQueue.find(t => t.id === taskId);
  }

  /**
   * 获取任务状态
   */
  getTaskStatus(taskId: string): ExecutorStatus | null {
    const task = this.findTask(taskId);
    return task?.status || null;
  }

  /**
   * 获取活跃任务
   */
  getActiveTask(): ExecutorTask | null {
    return this.activeTask;
  }

  /**
   * 获取队列长度
   */
  getQueueLength(): number {
    return this.taskQueue.length;
  }

  /**
   * 取消任务
   */
  cancelTask(taskId: string): boolean {
    const task = this.findTask(taskId);
    if (!task) return false;

    if (task.status === ExecutorStatus.RUNNING) {
      return false; // 正在执行的任务无法取消
    }

    task.status = ExecutorStatus.CANCELLED;
    return true;
  }

  /**
   * 清除已完成的任务
   */
  clearCompleted(): number {
    const before = this.taskQueue.length;
    this.taskQueue = this.taskQueue.filter(
      t => t.status !== ExecutorStatus.COMPLETED && t.status !== ExecutorStatus.FAILED
    );
    return before - this.taskQueue.length;
  }
}

// ============================================
// 视觉工具决策树
// ============================================

/**
 * 视觉工具选择器
 *
 * 根据操作类型自动选择最优执行器：
 * - Web浏览器操作 → OpenCLI (首选) / Midscene.js (兜底)
 * - 桌面应用<3次 → UI-TARS
 * - 桌面应用≥3次 → CLI-Anything
 */
export class VisualToolSelector {
  private usageCounts: Map<string, number>;
  private opencliStatusCache: { available: boolean; checkedAt: number } | null = null;
  private readonly OPENCLI_CACHE_TTL_MS = 30000; // 30秒缓存

  constructor() {
    this.usageCounts = new Map();
  }

  /**
   * 选择执行器 (异步 - 需要检查 OpenCLI 可用性)
   */
  async select(
    operation: 'web_browser' | 'desktop_app' | 'cli_command',
    context: { url?: string; app?: string; command?: string }
  ): Promise<ExecutorType> {
    switch (operation) {
      case 'web_browser':
        // 优先检查 OpenCLI 可用性
        if (await this.isOpenCLIAvailable()) {
          return ExecutorType.OPENCLI;
        }
        // OpenCLI 不可用时降级到 Midscene.js
        return ExecutorType.MIDSCENE;

      case 'desktop_app':
        const appKey = context.app || 'unknown';
        const usageCount = this.usageCounts.get(`${operation}:${appKey}`) || 0;

        if (usageCount >= 3) {
          return ExecutorType.CLI_ANYTHING;
        } else {
          return ExecutorType.UI_TARS;
        }

      case 'cli_command':
        return ExecutorType.CLAUDE_CODE;

      default:
        return ExecutorType.CLAUDE_CODE;
    }
  }

  /**
   * 同步选择执行器 (不检查 OpenCLI - 用于已知浏览器任务)
   */
  selectSync(
    operation: 'web_browser' | 'desktop_app' | 'cli_command',
    context: { url?: string; app?: string; command?: string }
  ): ExecutorType {
    switch (operation) {
      case 'web_browser':
        // 同步模式默认返回 OpenCLI (假设可用)
        return ExecutorType.OPENCLI;

      case 'desktop_app':
        const appKey = context.app || 'unknown';
        const usageCount = this.usageCounts.get(`${operation}:${appKey}`) || 0;

        if (usageCount >= 3) {
          return ExecutorType.CLI_ANYTHING;
        } else {
          return ExecutorType.UI_TARS;
        }

      case 'cli_command':
        return ExecutorType.CLAUDE_CODE;

      default:
        return ExecutorType.CLAUDE_CODE;
    }
  }

  /**
   * 检查 OpenCLI 是否可用
   */
  private async isOpenCLIAvailable(): Promise<boolean> {
    // 检查缓存
    if (this.opencliStatusCache) {
      const age = Date.now() - this.opencliStatusCache.checkedAt;
      if (age < this.OPENCLI_CACHE_TTL_MS) {
        return this.opencliStatusCache.available;
      }
    }

    // 执行检查
    const available = await this.checkOpenCLIDaemon();
    this.opencliStatusCache = {
      available,
      checkedAt: Date.now(),
    };
    return available;
  }

  /**
   * 检查 OpenCLI daemon 进程
   */
  private async checkOpenCLIDaemon(): Promise<boolean> {
    return new Promise((resolve) => {
      const proc = spawn('opencli', ['doctor'], { timeout: 5000 });
      let stdout = '';
      let resolved = false;

      const cleanup = () => {
        if (!resolved) {
          resolved = true;
          try {
            if (!proc.killed) {
              proc.kill('SIGTERM');
            }
          } catch {
            // Ignore kill errors
          }
        }
      };

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });

      proc.on('close', () => {
        cleanup();
        resolve(stdout.includes('running') || stdout.includes('[OK]'));
      });

      proc.on('error', () => {
        cleanup();
        resolve(false); // Fast fail if opencli not found
      });

      // Timeout fallback - shorter timeout for faster test execution
      setTimeout(() => {
        cleanup();
        resolve(false);
      }, 5000);
    });
  }

  /**
   * 清除 OpenCLI 状态缓存
   */
  clearCache(): void {
    this.opencliStatusCache = null;
  }

  /**
   * 记录使用次数
   */
  recordUsage(operation: 'web_browser' | 'desktop_app', identifier: string): void {
    const key = `${operation}:${identifier}`;
    const current = this.usageCounts.get(key) || 0;
    this.usageCounts.set(key, current + 1);
  }

  /**
   * 获取使用次数
   */
  getUsageCount(operation: string, identifier: string): number {
    return this.usageCounts.get(`${operation}:${identifier}`) || 0;
  }

  /**
   * 建议转换到CLI
   */
  shouldConvertToCLI(operation: string, identifier: string): boolean {
    return this.getUsageCount(operation, identifier) >= 3;
  }
}

// ============================================
// 单例导出
// ============================================

export const executorAdapter = new ExecutorAdapter();
export const visualToolSelector = new VisualToolSelector();
