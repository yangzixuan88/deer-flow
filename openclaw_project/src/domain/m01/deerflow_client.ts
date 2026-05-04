/**
 * M01 DeerFlow 客户端
 * ================================================
 * 与 DeerFlow 2.0 服务通信的 HTTP 客户端
 * ================================================
 */

import { DAGPlan, OrchestrationRequest, M01Config } from './types';

export interface DeerFlowConfig {
  enabled: boolean;
  host: string;
  port: number;
  timeoutMs: number;
  pollIntervalMs: number;
}

export interface DeerFlowThreadResponse {
  thread_id: string;
  status: 'idle' | 'busy' | 'interrupted' | 'error';
  created_at: string;
  updated_at: string;
}

export interface DeerFlowRunRequest {
  input: {
    prompt: string;
    dag_plan: DAGPlan;
    metadata: {
      session_id: string;
      request_id: string;
      priority: string;
    };
  };
  config: {
    recursion_limit: number;
  };
}

export interface DeerFlowRunResponse {
  run_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  thread_id: string;
  created_at: string;
}

export interface DeerFlowExecutionResult {
  request_id: string;
  success: boolean;
  dag_plan: DAGPlan;
  completed_nodes: number;
  total_nodes: number;
  duration: number;
  error?: string;
}

export class DeerFlowClient {
  private config: DeerFlowConfig;
  private baseUrl: string;

  constructor(config: DeerFlowConfig) {
    this.config = config;
    this.baseUrl = `http://${config.host}:${config.port}`;
  }

  /**
   * 创建新线程
   */
  async createThread(): Promise<string> {
    const response = await fetch(`${this.baseUrl}/api/threads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });

    if (!response.ok) {
      throw new Error(`Failed to create thread: ${response.statusText}`);
    }

    const data = await response.json() as DeerFlowThreadResponse;
    return data.thread_id;
  }

  /**
   * 触发任务执行
   */
  async runTask(
    threadId: string,
    dagPlan: DAGPlan,
    meta: { session_id: string; request_id: string; priority: string },
  ): Promise<DeerFlowRunResponse> {
    const request: DeerFlowRunRequest = {
      input: {
        prompt: dagPlan.rootTask,
        dag_plan: dagPlan,
        metadata: meta,
      },
      config: {
        recursion_limit: 100,
      },
    };

    const response = await fetch(`${this.baseUrl}/api/threads/${threadId}/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to run task: ${response.statusText}`);
    }

    return response.json() as Promise<DeerFlowRunResponse>;
  }

  /**
   * 获取线程状态
   */
  async getThreadStatus(threadId: string): Promise<DeerFlowThreadResponse> {
    const response = await fetch(`${this.baseUrl}/api/threads/${threadId}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Failed to get thread status: ${response.statusText}`);
    }

    return response.json() as Promise<DeerFlowThreadResponse>;
  }

  /**
   * 删除线程
   */
  async deleteThread(threadId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/threads/${threadId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      console.warn(`Failed to delete thread ${threadId}: ${response.statusText}`);
    }
  }

  /**
   * 执行 DAG 直到完成（带轮询）
   */
  async executeUntilComplete(
    dagPlan: DAGPlan,
    meta: { session_id: string; request_id: string; priority: string },
  ): Promise<DeerFlowExecutionResult> {
    const threadId = await this.createThread();
    const runResponse = await this.runTask(threadId, dagPlan, meta);

    const startTime = Date.now();
    const deadline = startTime + this.config.timeoutMs;

    while (Date.now() < deadline) {
      const status = await this.getThreadStatus(threadId);

      if (status.status === 'idle' || status.status === 'error') {
        // 线程完成，尝试获取结果
        // 注意：DeerFlow 的实际结果格式可能需要根据具体实现调整
        await this.deleteThread(threadId);
        return {
          request_id: meta.request_id,
          success: status.status !== 'error',
          dag_plan: dagPlan,
          completed_nodes: status.status === 'idle' ? dagPlan.nodes.length : 0,
          total_nodes: dagPlan.nodes.length,
          duration: Date.now() - startTime,
          error: status.status === 'error' ? 'DeerFlow execution failed' : undefined,
        };
      }

      // 等待轮询间隔
      await new Promise(resolve => setTimeout(resolve, this.config.pollIntervalMs));
    }

    // 超时
    await this.deleteThread(threadId);
    return {
      request_id: meta.request_id,
      success: false,
      dag_plan: dagPlan,
      completed_nodes: 0,
      total_nodes: dagPlan.nodes.length,
      duration: Date.now() - startTime,
      error: 'DeerFlow execution timeout',
    };
  }

  /**
   * 检查 DeerFlow 服务是否可用
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

// ============================================
// 默认配置
// ============================================

export const DEFAULT_DEERFLOW_CONFIG: DeerFlowConfig = {
  enabled: true,
  host: 'localhost',
  port: 8001,
  timeoutMs: 300000,  // 5分钟
  pollIntervalMs: 2000,
};

export function createDeerFlowClient(config: Partial<DeerFlowConfig> = {}): DeerFlowClient {
  return new DeerFlowClient({ ...DEFAULT_DEERFLOW_CONFIG, ...config });
}

// 单例
export const deerflowClient = createDeerFlowClient();
