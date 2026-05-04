/**
 * 跨引擎桥接管理器
 * ================================================
 * Purpose: 在 n8n 和 Dify 引擎间传递数据
 * 支持同步/异步/流式三种数据流模式
 * ================================================
 */

import {
  WorkflowEngine,
  CrossEngineDataFlow,
  BridgeType,
} from '../../domain/m04/engine_enum';

import {
  CrossEngineEdge,
  UniversalNodeConfig,
  HybridNode,
} from '../../domain/m04/types';

import { N8NClient } from './n8n_client';
import { DifyClient } from './dify_client';

export interface BridgeConfig {
  defaultBridgeType: BridgeType;
  redisHost?: string;
  redisPort?: number;
  sharedStoragePath?: string;
  pollIntervalMs?: number;
  streamBufferSize?: number;
}

export interface BridgeResult {
  success: boolean;
  data?: any;
  error?: string;
  bridge_type: BridgeType;
}

/**
 * 跨引擎桥接管理器
 *
 * 职责：
 * 1. 在不同引擎的节点间传递数据
 * 2. 选择最优桥接方式
 * 3. 处理数据转换
 */
export class BridgeManager {
  private config: BridgeConfig;
  private n8nClient: N8NClient;
  private difyClient: DifyClient;

  // 内存缓存（用于同进程内节点间传递）
  private memoryCache: Map<string, any> = new Map();

  // 轮询状态跟踪
  private pollStatus: Map<string, {
    taskId: string;
    startedAt: number;
    status: 'pending' | 'completed' | 'failed';
  }> = new Map();

  constructor(
    n8nClient: N8NClient,
    difyClient: DifyClient,
    config?: Partial<BridgeConfig>
  ) {
    this.n8nClient = n8nClient;
    this.difyClient = difyClient;
    this.config = {
      defaultBridgeType: (process.env.BRIDGE_TYPE as BridgeType) || BridgeType.MEMORY,
      redisHost: process.env.REDIS_HOST || 'localhost',
      redisPort: parseInt(process.env.REDIS_PORT || '6379'),
      sharedStoragePath: process.env.SHARED_STORAGE_PATH || '/tmp/openclaw/bridge',
      pollIntervalMs: 1000,
      streamBufferSize: 100,
      ...config,
    };
  }

  // ============================================
  // 公共接口
  // ============================================

  /**
   * 在两个节点间传递数据
   */
  async bridge(
    fromNode: HybridNode,
    toNode: HybridNode,
    data: any,
    edge?: CrossEngineEdge
  ): Promise<BridgeResult> {
    const fromEngine = fromNode.config.engine;
    const toEngine = toNode.config.engine;

    // 同引擎直接传递
    if (fromEngine === toEngine) {
      return {
        success: true,
        data,
        bridge_type: BridgeType.MEMORY,
      };
    }

    // 选择桥接类型
    const bridgeType = edge?.bridge_type || this.selectBridgeType(fromEngine, toEngine, data, edge?.data_flow);
    const dataFlow = edge?.data_flow || CrossEngineDataFlow.SYNC;

    console.log(`[BridgeManager] Bridging ${fromEngine} → ${toEngine} via ${bridgeType} (${dataFlow})`);

    switch (bridgeType) {
      case BridgeType.MEMORY:
        return this.memoryBridge(fromNode.id, toNode.id, data);

      case BridgeType.HTTP_POLL:
        return this.httpPollBridge(fromNode, toNode, data);

      case BridgeType.WEBHOOK_TRIGGER:
        return this.webhookTriggerBridge(fromNode, toNode, data);

      case BridgeType.SHARED_STORAGE:
        return this.sharedStorageBridge(fromNode.id, toNode.id, data);

      case BridgeType.STREAMING_BUFFER:
        return this.streamingBridge(fromNode, toNode, data);

      default:
        return {
          success: false,
          error: `Unknown bridge type: ${bridgeType}`,
          bridge_type: bridgeType,
        };
    }
  }

  /**
   * 选择最优桥接方式
   */
  private selectBridgeType(
    from: WorkflowEngine,
    to: WorkflowEngine,
    data: any,
    preferredFlow?: CrossEngineDataFlow
  ): BridgeType {
    const flow = preferredFlow || CrossEngineDataFlow.SYNC;

    // 流式优先用流式缓冲
    if (flow === CrossEngineDataFlow.STREAMING) {
      return BridgeType.STREAMING_BUFFER;
    }

    // 异步优先用Webhook触发
    if (flow === CrossEngineDataFlow.ASYNC) {
      return BridgeType.WEBHOOK_TRIGGER;
    }

    // n8n → Dify: HTTP轮询
    if (from === WorkflowEngine.N8N && to === WorkflowEngine.DIFY) {
      return BridgeType.HTTP_POLL;
    }

    // Dify → n8n: Webhook触发
    if (from === WorkflowEngine.DIFY && to === WorkflowEngine.N8N) {
      return BridgeType.WEBHOOK_TRIGGER;
    }

    // 默认内存
    return BridgeType.MEMORY;
  }

  // ============================================
  // 内存桥接（同进程内直接传递）
  // ============================================

  private memoryBridge(fromNodeId: string, toNodeId: string, data: any): BridgeResult {
    const key = `${fromNodeId}:${toNodeId}`;
    this.memoryCache.set(key, data);
    console.log(`[BridgeManager] Memory bridge: ${key}`);

    return {
      success: true,
      data,
      bridge_type: BridgeType.MEMORY,
    };
  }

  /**
   * 从内存缓存读取
   */
  getFromCache(fromNodeId: string, toNodeId: string): any {
    const key = `${fromNodeId}:${toNodeId}`;
    return this.memoryCache.get(key);
  }

  // ============================================
  // HTTP轮询桥接（n8n → Dify）
  // ============================================

  private async httpPollBridge(
    fromNode: HybridNode,
    toNode: HybridNode,
    data: any
  ): Promise<BridgeResult> {
    const difyConfig = toNode.config.entrypoint;

    if (!difyConfig.dify_workflow_id && !difyConfig.dify_app_id) {
      return {
        success: false,
        error: 'Dify workflow_id or app_id required for HTTP poll bridge',
        bridge_type: BridgeType.HTTP_POLL,
      };
    }

    try {
      // 通过 n8n 调用 Dify API
      const workflowId = difyConfig.dify_workflow_id || difyConfig.dify_app_id;
      if (!workflowId) {
        return {
          success: false,
          error: 'Dify workflow_id or app_id required',
          bridge_type: BridgeType.HTTP_POLL,
        };
      }
      const result = await this.difyClient.runWorkflow(workflowId, data);

      // 轮询直到完成
      const finalResult = await this.pollUntilComplete(result.task_id);

      return {
        success: true,
        data: finalResult,
        bridge_type: BridgeType.HTTP_POLL,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        bridge_type: BridgeType.HTTP_POLL,
      };
    }
  }

  /**
   * 轮询直到工作流完成
   */
  private async pollUntilComplete(taskId: string, timeoutMs: number = 60000): Promise<any> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      const detail = await this.difyClient.getRunDetail(taskId);

      if (detail.status === 'completed') {
        return detail.outputs;
      }
      if (detail.status === 'failed' || detail.status === 'stopped') {
        throw new Error(`Workflow ${taskId} ${detail.status}: ${detail.error}`);
      }

      // 等待下一次轮询
      await new Promise((r) => setTimeout(r, this.config.pollIntervalMs));
    }

    throw new Error(`Workflow ${taskId} polling timeout after ${timeoutMs}ms`);
  }

  // ============================================
  // Webhook触发桥接（Dify → n8n）
  // ============================================

  private async webhookTriggerBridge(
    fromNode: HybridNode,
    toNode: HybridNode,
    data: any
  ): Promise<BridgeResult> {
    const n8nWebhookPath = toNode.config.entrypoint.webhook_path;

    if (!n8nWebhookPath) {
      return {
        success: false,
        error: 'n8n webhook_path required for webhook trigger bridge',
        bridge_type: BridgeType.WEBHOOK_TRIGGER,
      };
    }

    try {
      // 通过 n8n webhook 触发
      const result = await this.n8nClient.executeWebhook(
        n8nWebhookPath,
        'POST',
        data
      );

      return {
        success: true,
        data: result,
        bridge_type: BridgeType.WEBHOOK_TRIGGER,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        bridge_type: BridgeType.WEBHOOK_TRIGGER,
      };
    }
  }

  // ============================================
  // 共享存储桥接（Redis/文件）
  // ============================================

  private sharedStorageBridge(
    fromNodeId: string,
    toNodeId: string,
    data: any
  ): BridgeResult {
    // 使用 Redis 或文件系统作为共享存储
    // 这里使用内存模拟，实际可替换为 Redis 或文件
    const key = `bridge:${fromNodeId}:${toNodeId}`;

    try {
      // 序列化数据（支持大对象）
      const serialized = JSON.stringify(data);
      this.memoryCache.set(key, data);
      console.log(`[BridgeManager] Shared storage bridge: ${key} (${serialized.length} bytes)`);

      return {
        success: true,
        data,
        bridge_type: BridgeType.SHARED_STORAGE,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Serialization failed',
        bridge_type: BridgeType.SHARED_STORAGE,
      };
    }
  }

  /**
   * 从共享存储读取
   */
  getFromSharedStorage(fromNodeId: string, toNodeId: string): any {
    const key = `bridge:${fromNodeId}:${toNodeId}`;
    return this.memoryCache.get(key);
  }

  // ============================================
  // 流式缓冲桥接
  // ============================================

  private streamingBridge(
    fromNode: HybridNode,
    toNode: HybridNode,
    data: any
  ): BridgeResult {
    // 流式数据缓冲：用于处理 SSE 等流式输出
    const key = `stream:${fromNode.id}:${toNode.id}`;

    // 将数据作为流缓冲
    const chunks: any[] = Array.isArray(data) ? data : [data];
    this.memoryCache.set(key, chunks);

    console.log(`[BridgeManager] Streaming buffer bridge: ${key} (${chunks.length} chunks)`);

    return {
      success: true,
      data: chunks,
      bridge_type: BridgeType.STREAMING_BUFFER,
    };
  }

  /**
   * 获取流缓冲数据
   */
  getStreamBuffer(fromNodeId: string, toNodeId: string): any[] {
    const key = `stream:${fromNodeId}:${toNodeId}`;
    return this.memoryCache.get(key) || [];
  }

  // ============================================
  // 工具方法
  // ============================================

  /**
   * 清除所有缓存
   */
  clearCache(): void {
    this.memoryCache.clear();
    this.pollStatus.clear();
    console.log('[BridgeManager] Cache cleared');
  }

  /**
   * 获取配置
   */
  getConfig(): BridgeConfig {
    return { ...this.config };
  }
}

// ============================================
// 工厂函数
// ============================================

let bridgeManagerInstance: BridgeManager | null = null;

export function createBridgeManager(
  n8nClient: N8NClient,
  difyClient: DifyClient,
  config?: Partial<BridgeConfig>
): BridgeManager {
  if (!bridgeManagerInstance) {
    bridgeManagerInstance = new BridgeManager(n8nClient, difyClient, config);
  }
  return bridgeManagerInstance;
}

export function getBridgeManager(): BridgeManager | null {
  return bridgeManagerInstance;
}
