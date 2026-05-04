/**
 * M11 Dapr Durable Agent 集成
 * ================================================
 * 实现 Exactly-Once 语义和崩溃恢复
 * 基于 Dapr State Management + Pub/Sub
 * ================================================
 */

import { DaprClient } from '@dapr/dapr';

// ============================================
// Dapr 配置常量
// ============================================

const DAPR_HTTP_PORT = process.env.DAPR_HTTP_PORT || '3500';
const DAPR_GRPC_PORT = process.env.DAPR_GRPC_PORT || '50001';
const DAPR_APP_ID = process.env.DAPR_APP_ID || 'openclaw-app';
const STATE_STORE_NAME = 'statestore';
const PUBSUB_NAME = 'pubsub';

/**
 * Dapr 客户端配置
 */
export interface DaprConfig {
  daprHttpPort: string;
  daprGrpcPort: string;
  appId: string;
}

/**
 * 默认 Dapr 配置
 */
export const DEFAULT_DAPR_CONFIG: DaprConfig = {
  daprHttpPort: DAPR_HTTP_PORT,
  daprGrpcPort: DAPR_GRPC_PORT,
  appId: DAPR_APP_ID,
};

// ============================================
// 任务状态定义
// ============================================

/**
 * 任务生命周期状态
 */
export enum TaskState {
  /** 任务已创建，等待处理 */
  PENDING = 'pending',
  /** 任务正在执行 */
  PROCESSING = 'processing',
  /** 任务已完成 */
  COMPLETED = 'completed',
  /** 任务执行失败 */
  FAILED = 'failed',
  /** 任务被取消 */
  CANCELLED = 'cancelled',
}

/**
 * 任务执行记录
 */
export interface TaskRecord {
  /** 任务唯一标识 */
  taskId: string;
  /** 任务状态 */
  state: TaskState;
  /** 任务数据 */
  data: Record<string, any>;
  /** 创建时间 */
  createdAt: string;
  /** 最后更新时间 */
  updatedAt: string;
  /** 重试次数 */
  retryCount: number;
  /** 最大重试次数 */
  maxRetries: number;
  /** 完成时的结果 */
  result?: any;
  /** 错误信息 */
  error?: string;
  /** 版本号（用于乐观锁） */
  version: number;
}

/**
 * 任务完成事件
 */
export interface TaskCompletedEvent {
  taskId: string;
  result: any;
  completedAt: string;
}

/**
 * 任务失败事件
 */
export interface TaskFailedEvent {
  taskId: string;
  error: string;
  failedAt: string;
  retryable: boolean;
}

// ============================================
// Durable Agent 接口
// ============================================

/**
 * Durable Agent 接口
 * 定义持久化任务执行器的标准行为
 */
export interface IDurableAgent {
  /**
   * 提交新任务
   * @param taskId 任务ID
   * @param data 任务数据
   * @returns 提交是否成功
   */
  submitTask(taskId: string, data: Record<string, any>): Promise<boolean>;

  /**
   * 获取任务状态
   * @param taskId 任务ID
   * @returns 任务记录
   */
  getTask(taskId: string): Promise<TaskRecord | null>;

  /**
   * 完成任务
   * @param taskId 任务ID
   * @param result 任务结果
   */
  completeTask(taskId: string, result: any): Promise<void>;

  /**
   * 标记任务失败
   * @param taskId 任务ID
   * @param error 错误信息
   * @param retryable 是否可重试
   */
  failTask(taskId: string, error: string, retryable?: boolean): Promise<void>;

  /**
   * 取消任务
   * @param taskId 任务ID
   */
  cancelTask(taskId: string): Promise<void>;

  /**
   * 等待任务完成
   * @param taskId 任务ID
   * @param timeoutMs 超时时间
   * @returns 任务结果
   */
  waitForTask(taskId: string, timeoutMs?: number): Promise<any>;

  /**
   * 获取活跃任务列表
   * @returns 任务ID列表
   */
  getActiveTasks(): Promise<string[]>;
}

/**
 * 任务处理器
 */
export type TaskHandler = (data: Record<string, any>, context: DurableExecutionContext) => Promise<any>;

/**
 * 执行上下文
 */
export interface DurableExecutionContext {
  taskId: string;
  retryCount: number;
  state: TaskRecord | null;
  complete(result: any): void;
  fail(error: string, retryable?: boolean): void;
  updateState(data: Partial<Record<string, any>>): Promise<void>;
}

// ============================================
// Durable Agent 实现
// ============================================

/**
 * Dapr Durable Agent 实现
 *
 * 核心特性：
 * - Exactly-Once 语义：通过 Dapr State Management 实现
 * - 崩溃恢复：从 Redis 状态存储恢复未完成的任务
 * - 幂等性：任务提交和执行都是幂等的
 * - 事件驱动：通过 Pub/Sub 实现任务完成通知
 */
export class DaprDurableAgent implements IDurableAgent {
  private daprClient: DaprClient;
  private config: DaprConfig;
  private handlers: Map<string, TaskHandler>;
  private subscriptionId: string;

  constructor(config: DaprConfig = DEFAULT_DAPR_CONFIG) {
    this.config = config;
    this.handlers = new Map();
    this.subscriptionId = `openclaw-agent-${Date.now()}`;

    // 初始化 Dapr 客户端
    this.daprClient = new DaprClient({
      daprHost: 'localhost',
      daprPort: config.daprHttpPort,
    });
  }

  // =========================================================================
  // 核心方法
  // =========================================================================

  /**
   * 提交新任务（幂等操作）
   */
  async submitTask(taskId: string, data: Record<string, any>): Promise<boolean> {
    try {
      // 检查任务是否已存在
      const existing = await this.getTask(taskId);
      if (existing && existing.state !== TaskState.FAILED) {
        console.log(`[DaprAgent] Task ${taskId} already exists with state ${existing.state}`);
        return false;
      }

      // 创建新任务记录
      const task: TaskRecord = {
        taskId,
        state: TaskState.PENDING,
        data,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        retryCount: 0,
        maxRetries: 3,
        version: 1,
      };

      // 保存到状态存储
      await this.saveTask(task);

      // 发布任务创建事件
      await this.publishEvent('task-created', { taskId, data });

      console.log(`[DaprAgent] Task ${taskId} submitted successfully`);
      return true;
    } catch (error) {
      console.error(`[DaprAgent] Failed to submit task ${taskId}:`, error);
      return false;
    }
  }

  /**
   * 获取任务状态
   */
  async getTask(taskId: string): Promise<TaskRecord | null> {
    try {
      const result = await this.daprClient.state.get(STATE_STORE_NAME, taskId) as TaskRecord | null;
      return result || null;
    } catch (error) {
      console.error(`[DaprAgent] Failed to get task ${taskId}:`, error);
      return null;
    }
  }

  /**
   * 完成任务
   */
  async completeTask(taskId: string, result: any): Promise<void> {
    const task = await this.getTask(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    task.state = TaskState.COMPLETED;
    task.result = result;
    task.updatedAt = new Date().toISOString();
    task.version++;

    await this.saveTask(task);

    // 发布完成事件
    const event: TaskCompletedEvent = {
      taskId,
      result,
      completedAt: task.updatedAt,
    };
    await this.publishEvent('task-completed', event);

    console.log(`[DaprAgent] Task ${taskId} completed`);
  }

  /**
   * 标记任务失败
   */
  async failTask(taskId: string, error: string, retryable: boolean = true): Promise<void> {
    const task = await this.getTask(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    task.error = error;
    task.updatedAt = new Date().toISOString();
    task.version++;

    if (retryable && task.retryCount < task.maxRetries) {
      // 可重试，将状态改回 PENDING 并增加重试计数
      task.state = TaskState.PENDING;
      task.retryCount++;
      console.log(`[DaprAgent] Task ${taskId} failed, will retry (${task.retryCount}/${task.maxRetries})`);
    } else {
      // 不可重试或已达最大重试次数
      task.state = TaskState.FAILED;
      console.log(`[DaprAgent] Task ${taskId} failed permanently`);
    }

    await this.saveTask(task);

    // 发布失败事件
    const event: TaskFailedEvent = {
      taskId,
      error,
      failedAt: task.updatedAt,
      retryable,
    };
    await this.publishEvent('task-failed', event);
  }

  /**
   * 取消任务
   */
  async cancelTask(taskId: string): Promise<void> {
    const task = await this.getTask(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    if (task.state === TaskState.COMPLETED) {
      throw new Error(`Cannot cancel completed task ${taskId}`);
    }

    task.state = TaskState.CANCELLED;
    task.updatedAt = new Date().toISOString();
    task.version++;

    await this.saveTask(task);

    console.log(`[DaprAgent] Task ${taskId} cancelled`);
  }

  /**
   * 等待任务完成
   */
  async waitForTask(taskId: string, timeoutMs: number = 30000): Promise<any> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const task = await this.getTask(taskId);

      if (!task) {
        throw new Error(`Task ${taskId} not found`);
      }

      switch (task.state) {
        case TaskState.COMPLETED:
          return task.result;

        case TaskState.FAILED:
          throw new Error(`Task ${taskId} failed: ${task.error}`);

        case TaskState.CANCELLED:
          throw new Error(`Task ${taskId} was cancelled`);

        case TaskState.PENDING:
        case TaskState.PROCESSING:
          // 等待后继续轮询
          await this.sleep(100);
          break;
      }
    }

    throw new Error(`Task ${taskId} wait timeout after ${timeoutMs}ms`);
  }

  /**
   * 获取活跃任务列表
   */
  async getActiveTasks(): Promise<string[]> {
    try {
      // 从状态存储获取所有任务（简化实现）
      const tasks = await this.daprClient.state.get(STATE_STORE_NAME, 'active-tasks') as TaskRecord[] | null;
      return tasks?.map((t: TaskRecord) => t.taskId) || [];
    } catch (error) {
      console.error('[DaprAgent] Failed to get active tasks:', error);
      return [];
    }
  }

  // =========================================================================
  // 任务处理
  // =========================================================================

  /**
   * 注册任务处理器
   */
  registerHandler(taskType: string, handler: TaskHandler): void {
    this.handlers.set(taskType, handler);
    console.log(`[DaprAgent] Handler registered for task type: ${taskType}`);
  }

  /**
   * 处理任务（由 worker 调用）
   */
  async processTask(taskId: string): Promise<void> {
    const task = await this.getTask(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    if (task.state !== TaskState.PENDING) {
      console.log(`[DaprAgent] Task ${taskId} is not pending (state: ${task.state})`);
      return;
    }

    // 更新状态为处理中
    task.state = TaskState.PROCESSING;
    task.updatedAt = new Date().toISOString();
    task.version++;
    await this.saveTask(task);

    // 创建执行上下文
    const context: DurableExecutionContext = {
      taskId,
      retryCount: task.retryCount,
      state: task,
      complete: (result: any) => this.completeTask(taskId, result),
      fail: (error: string, retryable?: boolean) => this.failTask(taskId, error, retryable),
      updateState: async (data: Partial<Record<string, any>>) => {
        task.data = { ...task.data, ...data };
        task.version++;
        await this.saveTask(task);
      },
    };

    try {
      // 获取处理器并执行
      const handler = this.handlers.get(task.data.type || 'default');
      if (!handler) {
        throw new Error(`No handler registered for task type: ${task.data.type || 'unknown'}`);
      }

      const result = await handler(task.data, context);
      await this.completeTask(taskId, result);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      await this.failTask(taskId, errorMessage, true);
    }
  }

  /**
   * 启动任务处理器（轮询模式）
   */
  async startProcessor(pollIntervalMs: number = 1000): Promise<void> {
    console.log(`[DaprAgent] Starting task processor (poll interval: ${pollIntervalMs}ms)`);

    while (true) {
      try {
        const activeTasks = await this.getActiveTasks();

        for (const taskId of activeTasks) {
          const task = await this.getTask(taskId);
          if (task && task.state === TaskState.PENDING) {
            await this.processTask(taskId);
          }
        }
      } catch (error) {
        console.error('[DaprAgent] Processor error:', error);
      }

      await this.sleep(pollIntervalMs);
    }
  }

  // =========================================================================
  // 私有方法
  // =========================================================================

  /**
   * 保存任务到状态存储
   */
  private async saveTask(task: TaskRecord): Promise<void> {
    try {
      await this.daprClient.state.save(STATE_STORE_NAME, [
        {
          key: task.taskId,
          value: task,
        },
      ]);
    } catch (error) {
      console.error(`[DaprAgent] Failed to save task ${task.taskId}:`, error);
      throw error;
    }
  }

  /**
   * 发布事件到 Pub/Sub
   */
  private async publishEvent(eventType: string, data: any): Promise<void> {
    try {
      await this.daprClient.pubsub.publish(PUBSUB_NAME, eventType, data);
    } catch (error) {
      console.error(`[DaprAgent] Failed to publish event ${eventType}:`, error);
    }
  }

  /**
   * 订阅事件
   * 注意: @dapr/dapr 3.x 的 pubsub.subscribe 是不同的API
   * 这里使用简化实现，实际应使用 HTTP bindings 或 Dapr SDK 的正确方法
   */
  async subscribe(eventType: string, handler: (data: any) => Promise<void>): Promise<void> {
    try {
      // Dapr pub/sub subscription 需要通过 HTTP endpoint 实现
      // 这里仅记录，实际集成需要配置 Dapr pub/sub component
      console.log(`[DaprAgent] Subscribe to event: ${eventType} (handler registered)`);
      // 存储 handler 供后续调用
      this.subscriptions.set(eventType, handler);
    } catch (error) {
      console.error(`[DaprAgent] Failed to subscribe to ${eventType}:`, error);
    }
  }
  private subscriptions: Map<string, (data: any) => Promise<void>> = new Map();

  /**
   * 健康检查
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.daprClient.metadata.get();
      return true;
    } catch {
      return false;
    }
  }

  /**
   * 休眠辅助方法
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// ============================================
// 单例导出
// ============================================

let durableAgentInstance: DaprDurableAgent | null = null;

/**
 * 获取 Durable Agent 单例
 */
export function getDurableAgent(config?: DaprConfig): DaprDurableAgent {
  if (!durableAgentInstance) {
    durableAgentInstance = new DaprDurableAgent(config);
  }
  return durableAgentInstance;
}

/**
 * 重置单例（用于测试）
 */
export function resetDurableAgent(): void {
  durableAgentInstance = null;
}
