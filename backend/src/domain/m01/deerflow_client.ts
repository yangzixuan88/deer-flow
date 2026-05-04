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

/**
 * R99 Fix: Align with Python Gateway RunCreateRequest semantics.
 * - input.messages is what normalize_input() consumes (not input.prompt)
 * - dag_plan is preserved in metadata for context but not executed by Python agent
 * - Top-level metadata carries session/request/priority for Gateway routing
 */
export interface DeerFlowRunRequest {
  /** Python Gateway normalize_input() reads input.messages */
  input: {
    messages: Array<{ role: string; content: string }>;
  };
  /** Top-level metadata for Gateway/agent routing (mirrors RunCreateRequest.metadata) */
  metadata: {
    session_id: string;
    request_id: string;
    priority: string;
    dag_plan?: DAGPlan;  // Preserved as context, not executed by Python agent
  };
  /** RunnableConfig overrides */
  config?: {
    recursion_limit?: number;
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

// ============================================
// Memory Types (aligned with Python /api/memory response)
// ============================================

export interface MemoryContextSection {
  summary: string;
  updatedAt: string;
}

export interface MemoryUserContext {
  workContext: MemoryContextSection;
  personalContext: MemoryContextSection;
  topOfMind: MemoryContextSection;
}

export interface MemoryHistoryContext {
  recentMonths: MemoryContextSection;
  earlierContext: MemoryContextSection;
  longTermBackground: MemoryContextSection;
}

export interface MemoryFact {
  id: string;
  content: string;
  category: string;
  confidence: number;
  createdAt: string;
  source: string;
  sourceError?: string | null;
}

export interface MemoryResponse {
  version: string;
  lastUpdated: string;
  user: MemoryUserContext;
  history: MemoryHistoryContext;
  facts: MemoryFact[];
}

export interface MemoryConfigResponse {
  enabled: boolean;
  storage_path: string;
  debounce_seconds: number;
  max_facts: number;
  fact_confidence_threshold: number;
  injection_enabled: boolean;
  max_injection_tokens: number;
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
    // R99 Fix: Align input with Python Gateway RunCreateRequest semantics.
    // normalize_input() reads input.messages, not input.prompt.
    // dag_plan is preserved in metadata for context.
    const request: DeerFlowRunRequest = {
      input: {
        messages: [
          { role: 'user', content: dagPlan.rootTask }
        ],
      },
      metadata: {
        session_id: meta.session_id,
        request_id: meta.request_id,
        priority: meta.priority,
        dag_plan: dagPlan,  // Preserved as context, not executed by Python agent
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

  // ============================================
  // Memory Read Interface (R114-A)
  // ============================================

  /**
   * 读取全局 Memory 数据
   * 对应 GET /api/memory
   */
  async getMemory(): Promise<MemoryResponse> {
    const response = await fetch(`${this.baseUrl}/api/memory`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get memory: ${response.statusText}`);
    }

    return response.json() as Promise<MemoryResponse>;
  }

  /**
   * 读取 Memory 系统配置
   * 对应 GET /api/memory/config
   */
  async getMemoryConfig(): Promise<MemoryConfigResponse> {
    const response = await fetch(`${this.baseUrl}/api/memory/config`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get memory config: ${response.statusText}`);
    }

    return response.json() as Promise<MemoryConfigResponse>;
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
