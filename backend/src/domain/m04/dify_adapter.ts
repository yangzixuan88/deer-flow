/**
 * Dify 适配器
 * ================================================
 * DifyClient 之上的语义适配层
 * 将 Dify API 响应转换为统一格式
 * 提供高级抽象接口
 * ================================================
 */

import { DifyClient } from '../../infrastructure/workflow/dify_client';
import {
  WorkflowEngine,
  NodeCapability,
  NodeCategory,
  WhitelistLevel,
} from './engine_enum';

import {
  UniversalNodeConfig,
  NodeMetadata,
  IntentAnalysis,
  CrossEngineEdge,
} from './types';

export interface DifyAdapterConfig {
  baseUrl?: string;
  apiKey?: string;
  timeoutMs?: number;
  defaultModel?: string;
  defaultUser?: string;
}

/**
 * Dify 应用信息
 */
export interface DifyApp {
  id: string;
  name: string;
  type: 'chat' | 'completion' | 'agent' | 'workflow';
  description?: string;
  icon?: string;
}

/**
 * Dify 执行结果
 */
export interface DifyExecutionResult {
  success: boolean;
  task_id?: string;
  outputs?: Record<string, any>;
  answer?: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  error?: string;
  latency_ms?: number;
}

/**
 * Dify 适配器
 *
 * 职责：
 * 1. Dify 应用/工作流注册与管理
 * 2. 执行结果标准化
 * 3. 输入/输出格式转换
 * 4. 能力映射到 Dify 节点
 */
export class DifyAdapter {
  private client: DifyClient;
  private config: Required<DifyAdapterConfig>;
  private defaultUser: string;
  private defaultModel: string;

  // 已注册的应用缓存
  private registeredApps: Map<string, DifyApp> = new Map();

  constructor(config?: DifyAdapterConfig) {
    this.client = new DifyClient({
      baseUrl: config?.baseUrl,
      apiKey: config?.apiKey,
      timeout: config?.timeoutMs,
    });

    this.defaultUser = 'openclaw';
    this.defaultModel = config?.defaultModel || 'gpt-4';
    this.config = {
      baseUrl: config?.baseUrl || process.env.DIFY_BASE_URL || 'http://localhost/v1',
      apiKey: config?.apiKey || process.env.DIFY_API_KEY || '',
      timeoutMs: config?.timeoutMs || parseInt(process.env.DIFY_TIMEOUT_MS || '60000'),
      defaultModel: this.defaultModel,
      defaultUser: this.defaultUser,
    };
  }

  // ============================================
  // 应用管理
  // ============================================

  /**
   * 注册 Dify 应用
   */
  registerApp(app: DifyApp): void {
    this.registeredApps.set(app.id, app);
    console.log(`[DifyAdapter] Registered app: ${app.name} (${app.type})`);
  }

  /**
   * 获取已注册应用
   */
  getApp(appId: string): DifyApp | undefined {
    return this.registeredApps.get(appId);
  }

  /**
   * 列出所有已注册应用
   */
  listApps(): DifyApp[] {
    return Array.from(this.registeredApps.values());
  }

  /**
   * 从 Dify API 同步应用列表
   */
  async syncAppsFromServer(): Promise<DifyApp[]> {
    // 实际从 Dify API 获取应用列表
    // 简化实现
    return this.listApps();
  }

  // ============================================
  // 意图 → Dify 节点映射
  // ============================================

  /**
   * 能力 → Dify 节点类型映射
   */
  private capabilityToNodeType(capability: NodeCapability): string | null {
    const mapping: Record<NodeCapability, string | null> = {
      [NodeCapability.LLM]: 'dify_llm',
      [NodeCapability.RAG]: 'dify_knowledge_retrieval',
      [NodeCapability.AGENT]: 'dify_agent',
      [NodeCapability.CLASSIFICATION]: 'dify_question_classifier',
      [NodeCapability.CODE_EXEC]: 'dify_code',
      [NodeCapability.HTTP]: 'dify_http_request',
      [NodeCapability.DATABASE]: null,
      [NodeCapability.SCHEDULE]: null,
      [NodeCapability.WEBHOOK]: 'dify_http_request',
      [NodeCapability.CONDITION]: 'dify_condition',
      [NodeCapability.ITERATION]: 'dify_loop',
      [NodeCapability.TRANSFORM]: 'dify_template',
      [NodeCapability.TEMPLATE]: 'dify_template',
      [NodeCapability.FILE]: null,
      [NodeCapability.STREAMING]: null,
      [NodeCapability.REASONING]: 'dify_llm',
    };
    return mapping[capability] || null;
  }

  /**
   * 根据意图创建 Dify 节点元数据
   */
  createNodeFromIntent(
    capability: NodeCapability,
    name: string,
    description: string
  ): NodeMetadata | null {
    const nodeId = this.capabilityToNodeType(capability);
    if (!nodeId) return null;

    return {
      node_id: nodeId,
      name,
      description,
      engine: WorkflowEngine.DIFY,
      category: NodeCategory.AI,
      capabilities: [capability],
      inputs: this.getInputsForCapability(capability),
      outputs: this.getOutputsForCapability(capability),
      cost_estimate: this.estimateCost(capability),
      whitelist_level: WhitelistLevel.WHITE,
      version: '1.0',
      tags: ['Dify', capability],
    };
  }

  /**
   * 获取能力对应的输入定义
   */
  private getInputsForCapability(cap: NodeCapability): Array<{ name: string; type: string }> {
    const inputs: Record<NodeCapability, Array<{ name: string; type: string }>> = {
      [NodeCapability.LLM]: [
        { name: 'prompt', type: 'string' },
        { name: 'model', type: 'string' },
        { name: 'temperature', type: 'number' },
      ],
      [NodeCapability.RAG]: [
        { name: 'query', type: 'string' },
        { name: 'dataset_id', type: 'string' },
        { name: 'top_k', type: 'number' },
      ],
      [NodeCapability.AGENT]: [
        { name: 'task', type: 'string' },
        { name: 'app_id', type: 'string' },
      ],
      [NodeCapability.CLASSIFICATION]: [
        { name: 'query', type: 'string' },
        { name: 'categories', type: 'array' },
      ],
      [NodeCapability.CODE_EXEC]: [
        { name: 'code', type: 'string' },
        { name: 'language', type: 'string' },
      ],
      [NodeCapability.HTTP]: [
        { name: 'url', type: 'string' },
        { name: 'method', type: 'string' },
        { name: 'body', type: 'object' },
      ],
      [NodeCapability.DATABASE]: [],
      [NodeCapability.SCHEDULE]: [],
      [NodeCapability.WEBHOOK]: [
        { name: 'url', type: 'string' },
        { name: 'body', type: 'object' },
      ],
      [NodeCapability.CONDITION]: [
        { name: 'expression', type: 'string' },
        { name: 'true_branch', type: 'any' },
        { name: 'false_branch', type: 'any' },
      ],
      [NodeCapability.ITERATION]: [
        { name: 'items', type: 'array' },
        { name: 'action', type: 'string' },
      ],
      [NodeCapability.TRANSFORM]: [
        { name: 'template', type: 'string' },
        { name: 'data', type: 'object' },
      ],
      [NodeCapability.TEMPLATE]: [
        { name: 'template', type: 'string' },
        { name: 'data', type: 'object' },
      ],
      [NodeCapability.FILE]: [
        { name: 'file_path', type: 'string' },
        { name: 'operation', type: 'string' },
      ],
      [NodeCapability.STREAMING]: [
        { name: 'stream_url', type: 'string' },
      ],
      [NodeCapability.REASONING]: [
        { name: 'problem', type: 'string' },
        { name: 'model', type: 'string' },
      ],
    };
    return inputs[cap] || [];
  }

  /**
   * 获取能力对应的输出定义
   */
  private getOutputsForCapability(cap: NodeCapability): Array<{ name: string; type: string }> {
    const outputs: Record<NodeCapability, Array<{ name: string; type: string }>> = {
      [NodeCapability.LLM]: [
        { name: 'text', type: 'string' },
        { name: 'usage', type: 'object' },
      ],
      [NodeCapability.RAG]: [
        { name: 'chunks', type: 'array' },
        { name: 'count', type: 'number' },
      ],
      [NodeCapability.AGENT]: [
        { name: 'result', type: 'any' },
        { name: 'thoughts', type: 'array' },
      ],
      [NodeCapability.CLASSIFICATION]: [
        { name: 'category', type: 'string' },
        { name: 'confidence', type: 'number' },
      ],
      [NodeCapability.CODE_EXEC]: [
        { name: 'result', type: 'any' },
        { name: 'output', type: 'string' },
      ],
      [NodeCapability.HTTP]: [
        { name: 'status', type: 'number' },
        { name: 'body', type: 'any' },
      ],
      [NodeCapability.DATABASE]: [],
      [NodeCapability.SCHEDULE]: [],
      [NodeCapability.WEBHOOK]: [
        { name: 'received', type: 'boolean' },
      ],
      [NodeCapability.CONDITION]: [
        { name: 'result', type: 'any' },
      ],
      [NodeCapability.ITERATION]: [
        { name: 'results', type: 'array' },
        { name: 'count', type: 'number' },
      ],
      [NodeCapability.TRANSFORM]: [
        { name: 'result', type: 'string' },
      ],
      [NodeCapability.TEMPLATE]: [
        { name: 'result', type: 'string' },
      ],
      [NodeCapability.FILE]: [
        { name: 'success', type: 'boolean' },
        { name: 'path', type: 'string' },
      ],
      [NodeCapability.STREAMING]: [
        { name: 'chunks', type: 'array' },
      ],
      [NodeCapability.REASONING]: [
        { name: 'reasoning', type: 'string' },
        { name: 'conclusion', type: 'string' },
      ],
    };
    return outputs[cap] || [];
  }

  /**
   * 估算能力成本
   */
  private estimateCost(cap: NodeCapability): NodeMetadata['cost_estimate'] {
    const costs: Record<NodeCapability, NodeMetadata['cost_estimate']> = {
      [NodeCapability.LLM]: { tokens: 1000, api_calls: 1, latency_ms: 2000 },
      [NodeCapability.RAG]: { tokens: 200, api_calls: 1, latency_ms: 1000 },
      [NodeCapability.AGENT]: { tokens: 3000, api_calls: 5, latency_ms: 10000 },
      [NodeCapability.CLASSIFICATION]: { tokens: 300, api_calls: 1, latency_ms: 1000 },
      [NodeCapability.CODE_EXEC]: { tokens: 500, api_calls: 1, latency_ms: 3000 },
      [NodeCapability.HTTP]: { tokens: 0, api_calls: 1, latency_ms: 500 },
      [NodeCapability.DATABASE]: { tokens: 0, api_calls: 1, latency_ms: 200 },
      [NodeCapability.SCHEDULE]: { tokens: 0, api_calls: 0, latency_ms: 0 },
      [NodeCapability.WEBHOOK]: { tokens: 0, api_calls: 1, latency_ms: 300 },
      [NodeCapability.CONDITION]: { tokens: 50, api_calls: 0, latency_ms: 10 },
      [NodeCapability.ITERATION]: { tokens: 500, api_calls: 1, latency_ms: 5000 },
      [NodeCapability.TRANSFORM]: { tokens: 100, api_calls: 0, latency_ms: 50 },
      [NodeCapability.TEMPLATE]: { tokens: 50, api_calls: 0, latency_ms: 30 },
      [NodeCapability.FILE]: { tokens: 0, api_calls: 1, latency_ms: 500 },
      [NodeCapability.STREAMING]: { tokens: 1000, api_calls: 1, latency_ms: 3000 },
      [NodeCapability.REASONING]: { tokens: 2000, api_calls: 3, latency_ms: 5000 },
    };
    return costs[cap] || { tokens: 100, api_calls: 1, latency_ms: 1000 };
  }

  // ============================================
  // 执行接口
  // ============================================

  /**
   * 执行 LLM 补全
   */
  async complete(
    prompt: string,
    options?: {
      model?: string;
      temperature?: number;
      user?: string;
    }
  ): Promise<DifyExecutionResult> {
    const startTime = Date.now();

    try {
      const result = await this.client.completionRequest({
        query: prompt,
        user: options?.user || this.defaultUser,
      });

      return {
        success: true,
        outputs: result,
        answer: result.output_text,
        usage: result.usage,
        latency_ms: Date.now() - startTime,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        latency_ms: Date.now() - startTime,
      };
    }
  }

  /**
   * 执行聊天
   */
  async chat(
    query: string,
    appId?: string,
    options?: {
      conversation_id?: string;
      inputs?: Record<string, any>;
      user?: string;
    }
  ): Promise<DifyExecutionResult> {
    const startTime = Date.now();

    try {
      const result = await this.client.chat(
        appId || 'default',
        query,
        options?.user || this.defaultUser,
        {
          conversation_id: options?.conversation_id,
          inputs: options?.inputs,
        }
      );

      return {
        success: true,
        task_id: result.message_id,
        outputs: result,
        answer: result.answer,
        usage: result.usage,
        latency_ms: Date.now() - startTime,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        latency_ms: Date.now() - startTime,
      };
    }
  }

  /**
   * 执行知识检索
   */
  async retrieve(
    query: string,
    datasetIds: string[],
    options?: {
      top_k?: number;
      score_threshold?: number;
      user?: string;
    }
  ): Promise<DifyExecutionResult> {
    const startTime = Date.now();

    try {
      const result = await this.client.retrieve({
        dataset_ids: datasetIds,
        query,
        top_k: options?.top_k || 5,
        score_threshold: options?.score_threshold,
      });

      return {
        success: true,
        outputs: {
          records: result.records,
          count: result.records.length,
        },
        latency_ms: Date.now() - startTime,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        latency_ms: Date.now() - startTime,
      };
    }
  }

  /**
   * 执行 Agent
   */
  async runAgent(
    task: string,
    appId: string,
    options?: {
      user?: string;
    }
  ): Promise<DifyExecutionResult> {
    const startTime = Date.now();

    try {
      const result = await this.client.chat(appId, task, options?.user || this.defaultUser);

      return {
        success: true,
        task_id: result.message_id,
        outputs: {
          result: result.answer,
          thoughts: [],
        },
        answer: result.answer,
        usage: result.usage,
        latency_ms: Date.now() - startTime,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        latency_ms: Date.now() - startTime,
      };
    }
  }

  /**
   * 执行工作流
   */
  async runWorkflow(
    workflowId: string,
    inputs: Record<string, any>,
    options?: {
      response_mode?: 'blocking' | 'streaming';
      user?: string;
    }
  ): Promise<DifyExecutionResult> {
    const startTime = Date.now();

    try {
      const result = await this.client.runWorkflow(
        workflowId,
        inputs,
        options?.user || this.defaultUser,
        options?.response_mode || 'blocking'
      );

      // 如果是异步，轮询直到完成
      let outputs = result.outputs;
      if (result.status === 'pending' || result.status === 'running') {
        outputs = await this.pollWorkflowResult(result.task_id!);
      }

      return {
        success: result.status === 'completed',
        task_id: result.task_id,
        outputs,
        error: result.error,
        latency_ms: Date.now() - startTime,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        latency_ms: Date.now() - startTime,
      };
    }
  }

  /**
   * 轮询工作流结果
   */
  private async pollWorkflowResult(
    taskId: string,
    timeoutMs: number = 60000
  ): Promise<Record<string, any> | undefined> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const detail = await this.client.getRunDetail(taskId);

      if (detail.status === 'completed') {
        return detail.outputs;
      }
      if (detail.status === 'failed' || detail.status === 'stopped') {
        throw new Error(`Workflow ${taskId} ${detail.status}: ${detail.error}`);
      }

      // 等待下次轮询
      await new Promise((r) => setTimeout(r, 1000));
    }

    throw new Error(`Workflow ${taskId} polling timeout`);
  }

  // ============================================
  // 工具方法
  // ============================================

  /**
   * 健康检查
   */
  async healthCheck(): Promise<boolean> {
    return this.client.healthCheck();
  }

  /**
   * 获取客户端配置
   */
  getConfig(): Readonly<Required<DifyAdapterConfig>> {
    return { ...this.config };
  }

  /**
   * 获取底层 DifyClient（用于高级用法）
   */
  getClient(): DifyClient {
    return this.client;
  }
}

// ============================================
// 单例导出
// ============================================

let difyAdapterInstance: DifyAdapter | null = null;

export function createDifyAdapter(config?: DifyAdapterConfig): DifyAdapter {
  if (!difyAdapterInstance) {
    difyAdapterInstance = new DifyAdapter(config);
  }
  return difyAdapterInstance;
}

export function getDifyAdapter(): DifyAdapter | null {
  return difyAdapterInstance;
}
