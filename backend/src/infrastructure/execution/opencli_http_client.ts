/**
 * OpenCLI HTTP Client
 * ================================================
 * 与 OpenCLI daemon (端口 19825) 通信
 * 支持: 浏览器控制、截图、元素交互
 * ================================================
 */

import { spawn, exec } from 'child_process';

const execAsync = (cmd: string, options: { timeout?: number } = {}): Promise<{ stdout: string; stderr: string }> => {
  return new Promise((resolve, reject) => {
    exec(cmd, options, (error: any, stdout: string, stderr: string) => {
      if (error) reject(error);
      else resolve({ stdout, stderr });
    });
  });
};

// OpenCLI daemon 配置
const OPENCLI_DAEMON_HOST = 'localhost';
const OPENCLI_DAEMON_PORT = 19825;
const OPENCLI_DAEMON_URL = `http://${OPENCLI_DAEMON_HOST}:${OPENCLI_DAEMON_PORT}`;

export interface OpenCLIBrowserState {
  url: string;
  title: string;
  elements: Array<{
    index: number;
    tag: string;
    text: string;
    attrs: Record<string, string>;
  }>;
}

export interface OpenCLIStatus {
  daemon: boolean;
  extension: boolean;
  port: number;
}

export interface OpenCLIScreenshotResult {
  success: boolean;
  path?: string;
  error?: string;
}

/**
 * OpenCLI HTTP 客户端
 */
export class OpenCLIHttpClient {
  private daemonUrl: string;
  private healthCheckInterval: NodeJS.Timeout | null = null;
  private isConnected: boolean = false;

  constructor(host: string = OPENCLI_DAEMON_HOST, port: number = OPENCLI_DAEMON_PORT) {
    this.daemonUrl = `http://${host}:${port}`;
  }

  /**
   * 检查 daemon 健康状态
   */
  async ping(): Promise<boolean> {
    try {
      const response = await fetch(`${this.daemonUrl}/ping`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * 获取 daemon 状态
   */
  async getStatus(): Promise<OpenCLIStatus> {
    try {
      // 使用 opencli doctor 命令获取状态
      const { stdout } = await execAsync('opencli doctor');
      return {
        daemon: stdout.includes('[OK] Daemon'),
        extension: stdout.includes('[OK] Extension'),
        port: OPENCLI_DAEMON_PORT,
      };
    } catch {
      return {
        daemon: false,
        extension: false,
        port: OPENCLI_DAEMON_PORT,
      };
    }
  }

  /**
   * 检查 daemon 是否可用
   */
  async isAvailable(): Promise<boolean> {
    const status = await this.getStatus();
    return status.daemon;
  }

  /**
   * 执行 OpenCLI 浏览器命令 (通过 CLI)
   */
  async executeBrowserCommand(args: string[]): Promise<{ success: boolean; output: string; error?: string }> {
    return new Promise((resolve) => {
      const proc = spawn('opencli', ['browser', ...args], {
        timeout: 60000,
      });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });
      proc.stderr?.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code) => {
        resolve({
          success: code === 0,
          output: stdout,
          error: stderr || undefined,
        });
      });

      proc.on('error', (error) => {
        resolve({
          success: false,
          output: '',
          error: error.message,
        });
      });
    });
  }

  /**
   * 打开 URL
   */
  async open(url: string): Promise<{ success: boolean; error?: string }> {
    const result = await this.executeBrowserCommand(['open', url]);
    return { success: result.success, error: result.error };
  }

  /**
   * 获取页面状态
   */
  async getState(): Promise<OpenCLIBrowserState | null> {
    const result = await this.executeBrowserCommand(['state']);
    if (!result.success) return null;

    try {
      // 解析 state 输出
      const lines = result.output.split('\n').filter(l => l.trim());
      const state: OpenCLIBrowserState = {
        url: '',
        title: '',
        elements: [],
      };

      let currentTag = '';
      for (const line of lines) {
        if (line.startsWith('URL:')) {
          state.url = line.replace('URL:', '').trim();
        } else if (line.startsWith('Title:')) {
          state.title = line.replace('Title:', '').trim();
        } else if (line.match(/^\[\d+\]/)) {
          const match = line.match(/^\[(\d+)\]\s*<(\w+)>(.+)/);
          if (match) {
            state.elements.push({
              index: parseInt(match[1]),
              tag: match[2],
              text: match[3].trim(),
              attrs: {},
            });
          }
        }
      }

      return state;
    } catch {
      return null;
    }
  }

  /**
   * 点击元素
   */
  async click(index: number): Promise<{ success: boolean; error?: string }> {
    const result = await this.executeBrowserCommand(['click', index.toString()]);
    return { success: result.success, error: result.error };
  }

  /**
   * 输入文本
   */
  async type(index: number, text: string): Promise<{ success: boolean; error?: string }> {
    const result = await this.executeBrowserCommand(['type', index.toString(), text]);
    return { success: result.success, error: result.error };
  }

  /**
   * 截图
   */
  async screenshot(path?: string): Promise<OpenCLIScreenshotResult> {
    const args = path ? ['screenshot', path] : ['screenshot'];
    const result = await this.executeBrowserCommand(args);
    return {
      success: result.success,
      path: result.output.trim() || undefined,
      error: result.error,
    };
  }

  /**
   * 等待
   */
  async wait(type: 'selector' | 'text' | 'time', value: string): Promise<{ success: boolean; error?: string }> {
    const result = await this.executeBrowserCommand(['wait', type, value]);
    return { success: result.success, error: result.error };
  }

  /**
   * 获取页面属性
   */
  async get(): Promise<Record<string, any> | null> {
    const result = await this.executeBrowserCommand(['get']);
    if (!result.success) return null;

    try {
      // 解析 get 输出
      return JSON.parse(result.output);
    } catch {
      return null;
    }
  }

  /**
   * 关闭浏览器
   */
  async close(): Promise<{ success: boolean; error?: string }> {
    const result = await this.executeBrowserCommand(['close']);
    return { success: result.success, error: result.error };
  }

  /**
   * 启动健康检查
   */
  startHealthCheck(callback: (status: OpenCLIStatus) => void, intervalMs: number = 30000): void {
    this.healthCheckInterval = setInterval(async () => {
      const status = await this.getStatus();
      callback(status);
    }, intervalMs);
  }

  /**
   * 停止健康检查
   */
  stopHealthCheck(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }
}

/**
 * OpenCLI 会话管理器
 */
export class OpenCLISessionManager {
  private client: OpenCLIHttpClient;
  private currentUrl: string | null = null;

  constructor() {
    this.client = new OpenCLIHttpClient();
  }

  /**
   * 创建新会话
   */
  async createSession(url?: string): Promise<{ sessionId: string; url: string }> {
    const sessionId = `opencli_session_${Date.now()}`;

    if (url) {
      await this.client.open(url);
      this.currentUrl = url;
    }

    return { sessionId, url: url || '' };
  }

  /**
   * 导航到 URL
   */
  async navigate(url: string): Promise<{ success: boolean; error?: string }> {
    const result = await this.client.open(url);
    if (result.success) {
      this.currentUrl = url;
    }
    return result;
  }

  /**
   * 获取当前 URL
   */
  getCurrentUrl(): string | null {
    return this.currentUrl;
  }

  /**
   * 检查是否已登录 (通过检查特定元素)
   */
  async isLoggedIn(checkSelector?: string): Promise<boolean> {
    const state = await this.client.getState();
    if (!state) return false;

    if (checkSelector) {
      return state.elements.some(el =>
        el.text.includes(checkSelector) || el.attrs['class']?.includes(checkSelector)
      );
    }

    // 通用检查: 检查是否存在登录相关元素
    return !state.url.includes('login') && !state.url.includes('signin');
  }

  /**
   * 获取客户端实例
   */
  getClient(): OpenCLIHttpClient {
    return this.client;
  }
}

// ============================================
// 单例导出
// ============================================

export const opencliHttpClient = new OpenCLIHttpClient();
export const opencliSessionManager = new OpenCLISessionManager();
