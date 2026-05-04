/**
 * OpenCLI Daemon 管理器
 * ================================================
 * T2: OpenCLI Daemon 进程管理
 * 端口 19825 · 扩展连接 · 健康检查
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

// OpenCLI Daemon 配置
const OPENCLI_DAEMON_PORT = 19825;
const OPENCLI_DAEMON_HOST = 'localhost';
const HEALTH_CHECK_INTERVAL_MS = 30000; // 30秒

export interface OpenCLIDaemonStatus {
  daemon: boolean;
  extension: boolean;
  port: number;
  uptime?: number; // 秒
  version?: string;
  lastCheck: string;
}

export interface OpenCLIDaemonInfo {
  version: string;
  port: number;
  extensionVersion?: string;
  browserConnected: boolean;
}

/**
 * OpenCLI Daemon 健康状态
 */
export enum OpenCLIDaemonHealth {
  HEALTHY = 'healthy',           // daemon + extension 都连接
  DEGRADED = 'degraded',         // daemon 运行但 extension 未连接
  DOWN = 'down',                 // daemon 未运行
  UNKNOWN = 'unknown',           // 未知状态
}

/**
 * OpenCLI Daemon 管理器
 */
export class OpenCLIDaemonManager {
  private healthCheckInterval: NodeJS.Timeout | null = null;
  private lastStatus: OpenCLIDaemonStatus | null = null;
  private statusListeners: Set<(status: OpenCLIDaemonStatus) => void> = new Set();
  private startupTime: number | null = null;

  constructor() {
    this.startupTime = null;
  }

  /**
   * 检查 daemon 健康状态 (通过 opencli doctor)
   */
  async checkHealth(): Promise<OpenCLIDaemonStatus> {
    try {
      const { stdout } = await execAsync('opencli doctor', { timeout: 10000 });

      const daemonRunning = stdout.includes('[OK]') && stdout.includes('Daemon');
      const extensionConnected = stdout.includes('[OK]') && stdout.includes('Extension');

      this.lastStatus = {
        daemon: daemonRunning,
        extension: extensionConnected,
        port: OPENCLI_DAEMON_PORT,
        version: this.extractVersion(stdout),
        lastCheck: new Date().toISOString(),
      };

      if (this.startupTime === null && daemonRunning) {
        this.startupTime = Date.now();
      }

      if (this.startupTime && daemonRunning) {
        this.lastStatus.uptime = Math.floor((Date.now() - this.startupTime) / 1000);
      }

      return this.lastStatus;
    } catch (error) {
      this.lastStatus = {
        daemon: false,
        extension: false,
        port: OPENCLI_DAEMON_PORT,
        lastCheck: new Date().toISOString(),
      };
      return this.lastStatus;
    }
  }

  /**
   * 获取健康状态枚举
   */
  getHealthStatus(): OpenCLIDaemonHealth {
    if (!this.lastStatus) {
      return OpenCLIDaemonHealth.UNKNOWN;
    }

    if (!this.lastStatus.daemon) {
      return OpenCLIDaemonHealth.DOWN;
    }

    if (!this.lastStatus.extension) {
      return OpenCLIDaemonHealth.DEGRADED;
    }

    return OpenCLIDaemonHealth.HEALTHY;
  }

  /**
   * 检查 daemon 是否可用
   */
  async isAvailable(): Promise<boolean> {
    const status = await this.checkHealth();
    return status.daemon;
  }

  /**
   * 检查扩展是否已连接
   */
  async isExtensionConnected(): Promise<boolean> {
    const status = await this.checkHealth();
    return status.extension;
  }

  /**
   * 启动 daemon (仅启动，不等待连接)
   * 注意: daemon 通常通过 opencli 命令自动启动
   */
  async start(): Promise<{ success: boolean; message: string }> {
    try {
      // 检查是否已在运行
      const status = await this.checkHealth();
      if (status.daemon) {
        return { success: true, message: 'Daemon already running' };
      }

      // 尝试启动 daemon (通常 opencli 命令会自动启动 daemon)
      const { stdout } = await execAsync('opencli daemon start 2>&1 || true', { timeout: 5000 });

      // 等待一下再检查
      await new Promise(resolve => setTimeout(resolve, 2000));

      const newStatus = await this.checkHealth();
      if (newStatus.daemon) {
        return { success: true, message: 'Daemon started successfully' };
      }

      return { success: false, message: 'Failed to start daemon' };
    } catch (error) {
      return { success: false, message: `Error starting daemon: ${error}` };
    }
  }

  /**
   * 停止 daemon
   */
  async stop(): Promise<{ success: boolean; message: string }> {
    try {
      await execAsync('opencli daemon stop 2>&1', { timeout: 5000 });

      // 等待停止
      await new Promise(resolve => setTimeout(resolve, 1000));

      const status = await this.checkHealth();
      if (!status.daemon) {
        this.startupTime = null;
        return { success: true, message: 'Daemon stopped' };
      }

      return { success: false, message: 'Daemon still running' };
    } catch (error) {
      return { success: false, message: `Error stopping daemon: ${error}` };
    }
  }

  /**
   * 重启 daemon
   */
  async restart(): Promise<{ success: boolean; message: string }> {
    const stopResult = await this.stop();
    if (!stopResult.success) {
      return stopResult;
    }

    await new Promise(resolve => setTimeout(resolve, 2000));

    return this.start();
  }

  /**
   * 启动健康检查循环
   */
  startHealthCheck(intervalMs: number = HEALTH_CHECK_INTERVAL_MS): void {
    if (this.healthCheckInterval) {
      return; // 已启动
    }

    // 立即执行一次检查
    this.checkHealth().then(status => {
      this.notifyListeners(status);
    });

    // 定期检查
    this.healthCheckInterval = setInterval(async () => {
      const status = await this.checkHealth();
      this.notifyListeners(status);
    }, intervalMs);
  }

  /**
   * 停止健康检查循环
   */
  stopHealthCheck(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }

  /**
   * 订阅状态变化
   */
  subscribe(listener: (status: OpenCLIDaemonStatus) => void): () => void {
    this.statusListeners.add(listener);
    return () => {
      this.statusListeners.delete(listener);
    };
  }

  /**
   * 获取最后状态
   */
  getLastStatus(): OpenCLIDaemonStatus | null {
    return this.lastStatus;
  }

  /**
   * 获取 daemon 信息
   */
  async getInfo(): Promise<OpenCLIDaemonInfo | null> {
    try {
      const { stdout } = await execAsync('opencli --version 2>&1');

      const status = await this.checkHealth();

      return {
        version: stdout.trim() || 'unknown',
        port: OPENCLI_DAEMON_PORT,
        extensionVersion: status.extension ? 'v1.0.0' : undefined,
        browserConnected: status.extension,
      };
    } catch {
      return null;
    }
  }

  /**
   * 等待扩展连接
   */
  async waitForExtension(timeoutMs: number = 60000): Promise<boolean> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const connected = await this.isExtensionConnected();
      if (connected) {
        return true;
      }
      await new Promise(resolve => setTimeout(resolve, 2000));
    }

    return false;
  }

  /**
   * 等待 daemon 可用
   */
  async waitForDaemon(timeoutMs: number = 30000): Promise<boolean> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const available = await this.isAvailable();
      if (available) {
        return true;
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    return false;
  }

  /**
   * 从 doctor 输出提取版本
   */
  private extractVersion(output: string): string | undefined {
    const match = output.match(/opencli v?([\d.]+)/i);
    return match ? match[1] : undefined;
  }

  /**
   * 通知所有监听器
   */
  private notifyListeners(status: OpenCLIDaemonStatus): void {
    for (const listener of this.statusListeners) {
      try {
        listener(status);
      } catch (error) {
        console.error('[OpenCLIDaemonManager] Listener error:', error);
      }
    }
  }
}

// ============================================
// OpenCLI Daemon 状态钩子 (供 hooks.ts 使用)
// ============================================

/**
 * OpenCLI Daemon 状态检查结果
 */
export interface OpenCLIDaemonCheckResult {
  healthy: boolean;
  status: OpenCLIDaemonHealth;
  daemon: boolean;
  extension: boolean;
  message: string;
}

/**
 * 检查 OpenCLI Daemon 状态 (用于钩子)
 */
export async function checkOpenCLIDaemonStatus(): Promise<OpenCLIDaemonCheckResult> {
  const manager = opencliDaemonManager;
  const status = await manager.checkHealth();
  const health = manager.getHealthStatus();

  let message: string;
  let healthy = false;

  switch (health) {
    case OpenCLIDaemonHealth.HEALTHY:
      message = 'OpenCLI Daemon running with extension connected';
      healthy = true;
      break;
    case OpenCLIDaemonHealth.DEGRADED:
      message = 'OpenCLI Daemon running but extension not connected';
      healthy = false;
      break;
    case OpenCLIDaemonHealth.DOWN:
      message = 'OpenCLI Daemon is not running';
      healthy = false;
      break;
    default:
      message = 'OpenCLI Daemon status unknown';
      healthy = false;
  }

  return {
    healthy,
    status: health,
    daemon: status.daemon,
    extension: status.extension,
    message,
  };
}

/**
 * OpenCLI 浏览器操作前检查
 */
export async function preOpenCLICheck(): Promise<OpenCLIDaemonCheckResult> {
  const result = await checkOpenCLIDaemonStatus();

  if (!result.daemon) {
    return {
      ...result,
      message: `${result.message}. Attempting to start...`,
    };
  }

  if (!result.extension) {
    console.warn('[OpenCLI] Extension not connected. Browser commands may fail.');
  }

  return result;
}

// ============================================
// 单例导出
// ============================================

export const opencliDaemonManager = new OpenCLIDaemonManager();
