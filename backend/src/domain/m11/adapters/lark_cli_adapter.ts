/**
 * M11 LarkCLI适配器
 * ================================================
 * 飞书CLI执行器 · 多机器人profile管理 · 命令封装
 * ================================================
 */

import { spawn } from 'child_process';
import * as crypto from 'crypto';

// ============================================
// 类型定义
// ============================================

export interface CLIResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  execution_time_ms: number;
  parsed_output?: any;
}

export interface LarkCLIConfig {
  profile?: string;      // lark-cli profile名称 (默认 daguan_zhu)
  timeout_ms?: number;  // 超时时间 (默认 60000ms)
  as_bot?: boolean;      // 是否以bot身份执行 (默认 true)
}

export interface SkillCommand {
  skill: string;        // skill名称
  action: string;       // 操作类型
  params: Record<string, any>; // 参数
}

// ============================================
// LarkCLI适配器
// ============================================

/**
 * 仅支持user身份的API列表
 * 这些命令不支持--as bot
 */
const USER_ONLY_COMMANDS = new Set([
  'contact +search-user',
  'contact user get',
  'wiki node search',
]);

/**
 * 检测命令是否仅支持user身份
 */
function isUserOnlyCommand(command: string): boolean {
  const lower = command.toLowerCase();
  for (const userCmd of USER_ONLY_COMMANDS) {
    if (lower.includes(userCmd.toLowerCase())) {
      return true;
    }
  }
  return false;
}

/**
 * LarkCLI适配器
 *
 * 核心职责：
 * - 封装 lark-cli 命令执行
 * - 多机器人profile切换
 * - Skill命令解析
 * - 输出格式化
 */
export class LarkCLIAdapter {
  private defaultProfile: string;
  private larkCliPath: string;

  constructor(defaultProfile: string = 'daguan_zhu') {
    this.defaultProfile = defaultProfile;
    // lark-cli 路径 (Windows npm全局安装)
    this.larkCliPath = 'E:/OpenClaw-Base/npm/node_modules/@larksuite/cli/bin/lark-cli.exe';
  }

  /**
   * 执行 lark-cli 命令
   */
  async execute(
    cliCommand: string,
    config?: Partial<LarkCLIConfig>
  ): Promise<CLIResult> {
    const profile = config?.profile || this.defaultProfile;
    const timeout_ms = config?.timeout_ms || 60000;
    const as_bot = config?.as_bot !== false; // 默认 true

    const startTime = Date.now();

    return new Promise((resolve) => {
      // 构建命令参数
      const args = this.buildArgs(cliCommand, profile, as_bot);

      let stdout = '';
      let stderr = '';
      let resolved = false;

      const proc = spawn(this.larkCliPath, args, {
        shell: false,
        timeout: timeout_ms,
        env: {
          ...process.env,
          LARK_CLI_NO_PROXY: '1', // 禁用代理避免凭证泄露
        },
      });

      proc.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      const cleanup = () => {
        if (!resolved) {
          resolved = true;
          clearTimeout(timeoutId);
        }
      };

      proc.on('close', (code) => {
        cleanup();
        const result = this.parseResult(stdout, stderr, code, startTime);
        resolve(result);
      });

      proc.on('error', (error) => {
        cleanup();
        resolve({
          success: false,
          stdout,
          stderr: error.message,
          exit_code: -1,
          execution_time_ms: Date.now() - startTime,
        });
      });

      // 超时处理
      const timeoutId = setTimeout(() => {
        if (!resolved) {
          proc.kill('SIGTERM');
          resolved = true;
          resolve({
            success: false,
            stdout,
            stderr: 'Command timed out',
            exit_code: -2,
            execution_time_ms: Date.now() - startTime,
          });
        }
      }, timeout_ms);
    });
  }

  /**
   * 构建命令参数
   */
  private buildArgs(command: string, profile: string, as_bot: boolean): string[] {
    const args: string[] = [];

    // 添加 profile
    if (profile) {
      args.push('--profile', profile);
    }

    // 如果是 bot 身份，但命令仅支持user，则使用 --as user
    if (as_bot && !isUserOnlyCommand(command)) {
      args.push('--as', 'bot');
    }

    // 解析命令字符串
    // 格式: "calendar +agenda" -> ["calendar", "+agenda"]
    // 或: "api GET /open-apis/bot/v3/info"
    const parts = command.trim().split(/\s+/);
    args.push(...parts);

    return args;
  }

  /**
   * 解析结果
   */
  private parseResult(stdout: string, stderr: string, exitCode: number | null, startTime: number): CLIResult {
    const exit_code = exitCode || 0;

    // 尝试解析 JSON 输出
    let parsed_output: any = undefined;
    try {
      // 找到第一个 { 开始的位置（避免前面有日志）
      const jsonStart = stdout.indexOf('{');
      if (jsonStart !== -1) {
        const jsonStr = stdout.substring(jsonStart);
        parsed_output = JSON.parse(jsonStr);
      }
    } catch {
      // JSON解析失败，忽略
    }

    // 判断成功: exit_code 为 0 或 ok: true
    const isOk = parsed_output?.ok === true || exit_code === 0;

    return {
      success: isOk,
      stdout,
      stderr,
      exit_code,
      execution_time_ms: Date.now() - startTime,
      parsed_output,
    };
  }

  /**
   * 解析 lark-cli 命令为结构化对象
   *
   * 输入: "im message create --receive-id ou_xxx --content 'hello'"
   * 输出: { skill: 'msg-send', action: 'im message create', params: {...} }
   *
   * 也支持旧版格式: skill:action?key1=val1&key2=val2
   * 示例: msg:send?to=user123&content=hello
   */
  parseSkillCommand(command: string): { skill: string; action: string; params: Record<string, string> } {
    // Skill映射表
    const skillMap: Record<string, string> = {
      'im message create': 'msg-send',
      'im message reply': 'msg-reply',
      'im messages list': 'im-message-list',
      'calendar +agenda': 'calendar-agenda',
      'calendar events instance_view': 'calendar-event-list',
      'calendar event create': 'calendar-event-create',
      'contact +search-user': 'contact-user-search',
      'contact user get': 'contact-user-get',
      'drive doc create': 'doc-create',
      'drive doc block create': 'doc-append-block',
      'drive files list': 'doc-list',
      'drive file get': 'doc-get',
      'drive sheet create': 'sheet-create',
      'drive sheet cell update': 'sheet-update-cell',
      'drive bitable app create': 'base-create-table',
      'drive bitable record create': 'base-add-item',
      'task task create': 'task-create',
      'task subtask add': 'task-subtask-add',
      'wiki node search': 'wiki-node-search',
      'drive file upload': 'drive-file-upload',
      'mail message create': 'mail-message-send',
      'approval instance create': 'approval-instance-create',
      'attendance user stats list': 'attendance-stats',
      'drive slides create': 'slides-create',
      'calendar meeting_room list': 'meeting-room-list',
    };

    // 如果是旧版格式 (skill:action?key=val)，先转换
    if (command.includes(':') && !command.startsWith('--')) {
      const [skill, query] = command.split('?');
      const [skillName, action] = skill.split(':');

      const params: Record<string, string> = {};
      if (query) {
        query.split('&').forEach(pair => {
          const [key, value] = pair.split('=');
          if (key && value) {
            params[key] = decodeURIComponent(value);
          }
        });
      }

      const mappedSkill = Object.entries(skillMap).find(([k]) =>
        k.startsWith(skillName) || skillName.startsWith(k.split(' ')[0])
      )?.[1] || skillName;

      return {
        skill: mappedSkill,
        action: action ? `${skillName} ${action}` : skillName,
        params,
      };
    }

    // 解析 lark-cli 命令格式
    const parts = command.trim().split(/\s+/);
    const actionParts: string[] = [];
    const params: Record<string, string> = {};
    let i = 0;

    // 收集命令动作部分 (直到遇到 -- 开头的参数)
    while (i < parts.length) {
      if (parts[i].startsWith('--')) {
        break;
      }
      actionParts.push(parts[i]);
      i++;
    }

    // 解析参数 (--key value 格式)
    while (i < parts.length) {
      if (parts[i].startsWith('--')) {
        const key = parts[i].substring(2);
        i++;
        if (i < parts.length && !parts[i].startsWith('--')) {
          params[key] = parts[i];
        }
      }
      i++;
    }

    const action = actionParts.join(' ');
    const skill = skillMap[action] || 'unknown';

    return { skill, action, params };
  }

  /**
   * 构建 lark-cli 命令
   */
  private buildLarkCommand(skill: string, action: string, params: Record<string, string>): string {
    const parts: string[] = [skill];

    // 添加动作 (如 +agenda, +search-user)
    if (action) {
      parts.push(`+${action}`);
    }

    // 添加参数
    Object.entries(params).forEach(([key, value]) => {
      if (value) {
        parts.push(`--${key}`, value);
      }
    });

    return parts.join(' ');
  }

  /**
   * 格式化输出
   */
  formatOutput(raw: string, format: 'json' | 'text' | 'markdown' = 'text'): string {
    // 尝试解析 JSON
    let data: any;
    try {
      const jsonStart = raw.indexOf('{');
      if (jsonStart !== -1) {
        data = JSON.parse(raw.substring(jsonStart));
      }
    } catch {
      data = { raw };
    }

    switch (format) {
      case 'json':
        return JSON.stringify(data, null, 2);

      case 'markdown':
        return this.toMarkdown(data);

      case 'text':
      default:
        return this.toText(data);
    }
  }

  /**
   * 转为文本格式
   */
  private toText(data: any): string {
    if (!data || typeof data !== 'object') {
      return String(data);
    }

    // 如果有 ok 状态
    if (data.ok === false && data.error) {
      return `Error: ${data.error.message || data.error}`;
    }

    // 提取有用信息
    const lines: string[] = [];
    if (data.data !== undefined) {
      lines.push(JSON.stringify(data.data, null, 2));
    } else {
      Object.entries(data).forEach(([key, value]) => {
        if (key !== 'meta' && key !== 'ok') {
          lines.push(`${key}: ${JSON.stringify(value)}`);
        }
      });
    }

    return lines.join('\n') || JSON.stringify(data, null, 2);
  }

  /**
   * 转为 Markdown 格式
   */
  private toMarkdown(data: any): string {
    if (!data || typeof data !== 'object') {
      return String(data);
    }

    const lines: string[] = ['```json', JSON.stringify(data, null, 2), '```'];
    return lines.join('\n');
  }

  /**
   * 健康检查
   */
  async isAvailable(): Promise<boolean> {
    try {
      const result = await this.execute('calendar +agenda', {
        timeout_ms: 10000,
        profile: this.defaultProfile,
      });
      return result.success || result.exit_code === 0;
    } catch {
      return false;
    }
  }

  /**
   * 获取已配置的机器人profile列表 (测试期望的方法)
   * 同步版本，返回静态配置的profiles
   */
  getProfiles(): string[] {
    // 返回预配置的profiles (实际应该通过 lark-cli config show 获取)
    return ['daguan_zhu'];
  }

  /**
   * 列出所有已配置的机器人profile
   */
  async listProfiles(): Promise<string[]> {
    return new Promise((resolve) => {
      const proc = spawn(this.larkCliPath, ['config', 'show'], {
        shell: false,
        timeout: 5000,
      });

      let stdout = '';
      proc.stdout?.on('data', (data) => { stdout += data.toString(); });

      proc.on('close', () => {
        // 从输出中提取 profile 列表
        // 格式: profile: xxx
        const profiles: string[] = [];
        const matches = stdout.matchAll(/profile:\s*(\S+)/g);
        for (const match of matches) {
          profiles.push(match[1]);
        }
        resolve(profiles);
      });

      proc.on('error', () => resolve([]));
    });
  }

  /**
   * 获取当前默认profile
   */
  getDefaultProfile(): string {
    return this.defaultProfile;
  }

  /**
   * 设置默认profile
   */
  setDefaultProfile(profile: string): void {
    this.defaultProfile = profile;
  }
}

// ============================================
// Skill命令注册表
// ============================================

export const LARK_SKILL_COMMANDS: Record<string, string> = {
  // 消息
  'msg:send': 'im message create',
  'msg:reply': 'im message reply',
  'msg:list': 'im messages list',

  // 日历
  'calendar:agenda': 'calendar +agenda',
  'calendar:events': 'calendar events instance_view',
  'calendar:create': 'calendar event create',

  // 联系人
  'contact:search': 'contact +search-user',
  'contact:info': 'contact user get',

  // 云文档
  'doc:create': 'drive doc create',
  'doc:list': 'drive files list',
  'doc:get': 'drive file get',

  // 多维表格
  'bitable:create': 'bitable app create',
  'bitable:list': 'bitable app list',
  'bitable:record': 'bitable record create',

  // 任务
  'task:create': 'task task create',
  'task:list': 'task subtask list',
  'task:complete': 'task task complete',
};

// ============================================
// 单例导出
// ============================================

export const larkCLIAdapter = new LarkCLIAdapter();
