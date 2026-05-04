/**
 * M11 守护进程管理器
 * ================================================
 * Daemon三层实现
 * 脚本舱 · Cron挂载 · 心跳驱动
 * ================================================
 */

import {
  DaemonConfig,
  DaemonInstance,
  DaemonStatus,
  CrontabConfig,
  CrontabEntry,
  DEFAULT_SANDBOX_CONFIG,
  SandboxType,
} from './types';

import { gVisorSandbox } from './sandbox';

// ============================================
// 守护进程管理器
// ============================================

/**
 * 守护进程管理器
 *
 * 三层实现：
 * 1. 脚本舱（Daemon Isolation Pod）
 * 2. Cron扳机动态挂载引擎
 * 3. 心跳驱动执行
 */
export class DaemonManager {
  private daemons: Map<string, DaemonConfig>;
  private instances: Map<string, DaemonInstance>;
  private crontab: CrontabConfig;
  private schedulerInterval: NodeJS.Timeout | null;
  private lastTick: Date;

  constructor() {
    this.daemons = new Map();
    this.instances = new Map();
    this.crontab = {
      version: '1.0',
      updated_at: new Date().toISOString(),
      daemons: [],
    };
    this.schedulerInterval = null;
    this.lastTick = new Date();
  }

  /**
   * 注册守护进程
   */
  register(config: DaemonConfig): void {
    this.daemons.set(config.name, config);

    // 更新crontab
    this.syncCrontab();

    // 创建实例
    this.instances.set(config.name, {
      name: config.name,
      status: DaemonStatus.STOPPED,
      consecutive_failures: 0,
    });
  }

  /**
   * 启动守护进程
   */
  async start(name: string): Promise<boolean> {
    const config = this.daemons.get(name);
    const instance = this.instances.get(name);

    if (!config || !instance) {
      return false;
    }

    if (instance.status === DaemonStatus.RUNNING) {
      return false; // 已在运行
    }

    try {
      // 在沙盒中执行脚本
      if (config.sandbox) {
        const result = await gVisorSandbox.execute(
          `python ${config.script_path}`,
          {
            ...DEFAULT_SANDBOX_CONFIG,
            type: SandboxType.GVISOR,
            timeout_ms: 300000, // 5分钟超时
          }
        );

        if (result.success) {
          instance.status = DaemonStatus.RUNNING;
          instance.last_run_at = new Date().toISOString();
          instance.consecutive_failures = 0;
        } else {
          instance.consecutive_failures++;
          instance.last_failure_at = new Date().toISOString();

          if (instance.consecutive_failures >= config.max_consecutive_failures) {
            instance.status = DaemonStatus.FAILED;
          }

          // 发送通知
          if (config.notify_on_failure) {
            await this.sendNotification(config, result.stderr || 'Unknown error');
          }
        }
      } else {
        // 非沙盒执行（仅信任的脚本）
        instance.status = DaemonStatus.RUNNING;
        instance.last_run_at = new Date().toISOString();
      }

      return true;
    } catch (error) {
      instance.consecutive_failures++;
      instance.last_failure_at = new Date().toISOString();
      return false;
    }
  }

  /**
   * 停止守护进程
   */
  async stop(name: string): Promise<boolean> {
    const instance = this.instances.get(name);
    if (!instance) return false;

    instance.status = DaemonStatus.STOPPED;
    instance.pid = undefined;
    return true;
  }

  /**
   * 重启守护进程
   */
  async restart(name: string): Promise<boolean> {
    await this.stop(name);
    return this.start(name);
  }

  /**
   * 获取守护进程实例
   */
  getInstance(name: string): DaemonInstance | undefined {
    return this.instances.get(name);
  }

  /**
   * 获取所有守护进程
   */
  getAllInstances(): DaemonInstance[] {
    return Array.from(this.instances.values());
  }

  /**
   * 获取运行中的守护进程
   */
  getRunningDaemons(): DaemonInstance[] {
    return this.getAllInstances().filter(d => d.status === DaemonStatus.RUNNING);
  }

  /**
   * 启动调度器
   */
  startScheduler(intervalMs: number = 60000): void {
    if (this.schedulerInterval) {
      return; // 已启动
    }

    this.schedulerInterval = setInterval(() => {
      this.tick();
    }, intervalMs);
  }

  /**
   * 停止调度器
   */
  stopScheduler(): void {
    if (this.schedulerInterval) {
      clearInterval(this.schedulerInterval);
      this.schedulerInterval = null;
    }
  }

  /**
   * 调度器Tick
   */
  private async tick(): Promise<void> {
    this.lastTick = new Date();

    for (const [name, config] of this.daemons.entries()) {
      if (!config.enabled) continue;

      // 检查是否应该触发
      if (this.shouldTrigger(config)) {
        await this.start(name);
      }
    }
  }

  /**
   * 检查是否应该触发
   */
  private shouldTrigger(config: DaemonConfig): boolean {
    const instance = this.instances.get(config.name);
    if (!instance) return false;

    // 检查是否在冷却期
    if (instance.last_run_at) {
      const lastRun = new Date(instance.last_run_at);
      const elapsed = Date.now() - lastRun.getTime();

      // 至少需要等待cron表达式指定的时间
      // 此处简化：检查是否超过1分钟
      if (elapsed < 60000) return false;
    }

    // 简单的cron解析（实际应使用cron-parser库）
    return this.parseCron(config.cron_expression);
  }

  /**
   * 简单Cron解析
   */
  private parseCron(cronExpr: string): boolean {
    // 简化实现：支持标准5段cron
    // */30 * * * * = 每30分钟
    // 0 8 * * * = 每天8点
    const parts = cronExpr.split(' ');
    if (parts.length !== 5) return false;

    const now = new Date();
    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

    // 检查分钟
    if (minute.startsWith('*/')) {
      const interval = parseInt(minute.substring(2));
      if (now.getMinutes() % interval !== 0) return false;
    } else if (minute !== '*' && parseInt(minute) !== now.getMinutes()) {
      return false;
    }

    // 检查小时
    if (hour !== '*' && parseInt(hour) !== now.getHours()) {
      return false;
    }

    return true;
  }

  /**
   * 同步Crontab配置
   */
  private syncCrontab(): void {
    this.crontab.daemons = Array.from(this.daemons.values()).map(d => ({
      daemon_name: d.name,
      cron: d.cron_expression,
      script: d.script_path,
      sandbox: d.sandbox,
      notify: d.notify_on_failure ? d.notification_channel : undefined,
    }));
    this.crontab.updated_at = new Date().toISOString();
  }

  /**
   * 导出Crontab配置
   */
  exportCrontab(): CrontabConfig {
    return { ...this.crontab };
  }

  /**
   * 导入Crontab配置
   */
  importCrontab(config: CrontabConfig): void {
    this.crontab = { ...config };

    for (const entry of config.daemons) {
      const daemonConfig: DaemonConfig = {
        name: entry.daemon_name,
        script_path: entry.script,
        cron_expression: entry.cron,
        enabled: true,
        sandbox: entry.sandbox,
        notify_on_failure: !!entry.notify,
        notification_channel: entry.notify,
        max_consecutive_failures: 3,
      };

      this.register(daemonConfig);
    }
  }

  /**
   * 发送通知
   */
  private async sendNotification(config: DaemonConfig, error: string): Promise<void> {
    // 简化实现：应接入飞书/钉钉等
    console.error(`[Daemon:${config.name}] Failed: ${error}`);
    if (config.notification_channel === 'feishu') {
      // TODO: 接入飞书WebSocket
    }
  }

  /**
   * 获取统计信息
   */
  getStats(): {
    totalDaemons: number;
    running: number;
    failed: number;
    stopped: number;
    lastTick: string;
  } {
    const instances = this.getAllInstances();
    return {
      totalDaemons: instances.length,
      running: instances.filter(i => i.status === DaemonStatus.RUNNING).length,
      failed: instances.filter(i => i.status === DaemonStatus.FAILED).length,
      stopped: instances.filter(i => i.status === DaemonStatus.STOPPED).length,
      lastTick: this.lastTick.toISOString(),
    };
  }
}

// ============================================
// 脚本舱管理器
// ============================================

/**
 * 脚本舱 - 存储和管理Daemon脚本
 */
export class ScriptCabinet {
  private scripts: Map<string, { path: string; content: string; created_at: string }>;

  constructor() {
    this.scripts = new Map();
  }

  /**
   * 注册脚本
   */
  register(name: string, content: string): string {
    const path = `src/tasks/daemons/${name}.py`;
    this.scripts.set(name, {
      path,
      content,
      created_at: new Date().toISOString(),
    });
    return path;
  }

  /**
   * 获取脚本
   */
  get(name: string): { path: string; content: string } | undefined {
    return this.scripts.get(name);
  }

  /**
   * 列出所有脚本
   */
  list(): { name: string; path: string; created_at: string }[] {
    return Array.from(this.scripts.entries()).map(([name, data]) => ({
      name,
      path: data.path,
      created_at: data.created_at,
    }));
  }

  /**
   * 删除脚本
   */
  remove(name: string): boolean {
    return this.scripts.delete(name);
  }
}

// ============================================
// OpenCLI Daemon 集成
// ============================================

import { opencliDaemonManager, OpenCLIDaemonHealth } from './opencli_daemon';

/**
 * OpenCLI Daemon 健康检查集成到 DaemonManager
 * 用于在心跳Tick中检查 OpenCLI daemon 状态
 */
export async function checkOpenCLIDaemonIntegration(): Promise<{
  opencli: {
    healthy: boolean;
    health: OpenCLIDaemonHealth;
    daemon: boolean;
    extension: boolean;
  };
  daemons: {
    total: number;
    running: number;
    failed: number;
    stopped: number;
  };
}> {
  // 检查 OpenCLI daemon 状态
  const opencliStatus = await opencliDaemonManager.checkHealth();
  const opencliHealth = opencliDaemonManager.getHealthStatus();

  // 获取其他 daemon 状态
  const stats = daemonManager.getStats();

  return {
    opencli: {
      healthy: opencliHealth === OpenCLIDaemonHealth.HEALTHY,
      health: opencliHealth,
      daemon: opencliStatus.daemon,
      extension: opencliStatus.extension,
    },
    daemons: {
      total: stats.totalDaemons,
      running: stats.running,
      failed: stats.failed,
      stopped: stats.stopped,
    },
  };
}

/**
 * 获取系统健康报告
 */
export async function getSystemHealthReport(): Promise<{
  overall: 'healthy' | 'degraded' | 'critical';
  opencli: {
    status: string;
    daemon: boolean;
    extension: boolean;
    uptime?: number;
  };
  daemons: {
    status: string;
    running: number;
    total: number;
  };
  recommendations: string[];
}> {
  const integration = await checkOpenCLIDaemonIntegration();

  const recommendations: string[] = [];

  // OpenCLI 状态评估
  let opencliStatusText: string;
  if (integration.opencli.healthy) {
    opencliStatusText = 'Healthy';
  } else if (integration.opencli.daemon) {
    opencliStatusText = 'Degraded (extension disconnected)';
    recommendations.push('Reconnect Chrome extension for full browser automation');
  } else {
    opencliStatusText = 'Down';
    recommendations.push('Start OpenCLI daemon: opencli daemon start');
  }

  // Daemon 状态评估
  const daemonStatusText = `${integration.daemons.running}/${integration.daemons.total} running`;

  // 总体状态评估
  let overall: 'healthy' | 'degraded' | 'critical';
  if (!integration.opencli.daemon) {
    overall = integration.daemons.running === 0 ? 'critical' : 'degraded';
  } else if (!integration.opencli.extension || integration.daemons.failed > 0) {
    overall = 'degraded';
  } else {
    overall = 'healthy';
  }

  return {
    overall,
    opencli: {
      status: opencliStatusText,
      daemon: integration.opencli.daemon,
      extension: integration.opencli.extension,
      uptime: integration.opencli.daemon ? 0 : undefined,
    },
    daemons: {
      status: daemonStatusText,
      running: integration.daemons.running,
      total: integration.daemons.total,
    },
    recommendations,
  };
}

// ============================================
// 单例导出
// ============================================

export const daemonManager = new DaemonManager();
export const scriptCabinet = new ScriptCabinet();
export { opencliDaemonManager } from './opencli_daemon';
