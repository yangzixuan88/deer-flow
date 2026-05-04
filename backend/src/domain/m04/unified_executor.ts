/**
 * 统一执行引擎
 * ================================================
 * 一个 DAG 中混合执行 n8n 和 Dify 节点
 * 自动处理跨引擎数据流
 * ================================================
 */

import {
  WorkflowEngine,
  CircuitBreakerState,
  NodeExecutionStatus,
} from './engine_enum';

import {
  HybridWorkflow,
  HybridNode,
  ExecutionTrace,
  NodeExecutionResult,
  TaskStatus,
  CrossEngineEdge,
} from './types';

import { N8NClient } from '../../infrastructure/workflow/n8n_client';
import { DifyClient } from '../../infrastructure/workflow/dify_client';
import { BridgeManager } from '../../infrastructure/workflow/bridge_manager';
import { DAGBuilder } from './unified_builder';
import { CrossEngineDataTransformer, crossEngineTransformer } from './transformer';

export interface ExecutorConfig {
  enable_checkpoint: boolean;
  checkpoint_path: string;
  enable_circuit_breaker: boolean;
  circuit_breaker_threshold: number;
  parallel_execution: boolean;
  max_parallel_nodes: number;
}

// ============================================
// 熔断器
// ============================================

interface NodeBreakerState {
  failures: number;
  lastFailure: number;
  state: CircuitBreakerState;
}

class CircuitBreaker {
  private threshold: number;
  private resetTimeoutMs: number;
  private nodeStates: Map<string, NodeBreakerState> = new Map();

  constructor(threshold: number = 3, resetTimeoutMs: number = 60000) {
    this.threshold = threshold;
    this.resetTimeoutMs = resetTimeoutMs;
  }

  /**
   * 检查节点是否允许执行
   */
  canExecute(nodeId: string): boolean {
    const state = this.nodeStates.get(nodeId);
    if (!state) return true;

    if (state.state === CircuitBreakerState.CLOSED) return true;

    if (state.state === CircuitBreakerState.OPEN) {
      // 检查是否超时恢复
      if (Date.now() - state.lastFailure > this.resetTimeoutMs) {
        state.state = CircuitBreakerState.HALF_OPEN;
        return true;
      }
      return false;
    }

    // HALF_OPEN：允许一次尝试
    return true;
  }

  /**
   * 记录失败
   */
  recordFailure(nodeId: string): void {
    let state = this.nodeStates.get(nodeId);
    if (!state) {
      state = { failures: 0, lastFailure: 0, state: CircuitBreakerState.CLOSED };
      this.nodeStates.set(nodeId, state);
    }

    state.failures++;
    state.lastFailure = Date.now();

    if (state.failures >= this.threshold) {
      state.state = CircuitBreakerState.OPEN;
      console.warn(`[CircuitBreaker] Node ${nodeId} circuit OPEN (${state.failures} failures)`);
    }
  }

  /**
   * 记录成功
   */
  recordSuccess(nodeId: string): void {
    const state = this.nodeStates.get(nodeId);
    if (state) {
      state.failures = 0;
      state.state = CircuitBreakerState.CLOSED;
    }
  }

  /**
   * 重置节点熔断器
   */
  reset(nodeId: string): void {
    this.nodeStates.delete(nodeId);
  }

  /**
   * 重置所有熔断器
   */
  resetAll(): void {
    this.nodeStates.clear();
  }
}

// ============================================
// 执行器
// ============================================

export class UnifiedExecutor {
  private config: ExecutorConfig;
  private n8nClient: N8NClient;
  private difyClient: DifyClient;
  private bridgeManager: BridgeManager;
  private circuitBreaker: CircuitBreaker;
  private dagBuilder: DAGBuilder;
  private transformer: CrossEngineDataTransformer;

  // 执行缓存（node_id → result）
  private executionCache: Map<string, any> = new Map();

  // Checkpoint 数据
  private checkpoints: Map<string, any> = new Map();

  constructor(n8nClient: N8NClient, difyClient: DifyClient, config?: Partial<ExecutorConfig>) {
    this.n8nClient = n8nClient;
    this.difyClient = difyClient;
    this.bridgeManager = new BridgeManager(n8nClient, difyClient);
    this.circuitBreaker = new CircuitBreaker(
      config?.circuit_breaker_threshold ?? 3
    );
    this.dagBuilder = new DAGBuilder();
    this.transformer = crossEngineTransformer;

    this.config = {
      enable_checkpoint: config?.enable_checkpoint ?? true,
      checkpoint_path: config?.checkpoint_path ?? '/tmp/openclaw/checkpoints',
      enable_circuit_breaker: config?.enable_circuit_breaker ?? true,
      circuit_breaker_threshold: config?.circuit_breaker_threshold ?? 3,
      parallel_execution: config?.parallel_execution ?? true,
      max_parallel_nodes: config?.max_parallel_nodes ?? 5,
    };
  }

  // ============================================
  // 主执行入口
  // ============================================

  /**
   * 执行混合工作流
   */
  async execute(workflow: HybridWorkflow): Promise<ExecutionTrace> {
    const executionId = `exec_${Date.now()}`;
    const startTime = new Date().toISOString();

    const trace: ExecutionTrace = {
      execution_id: executionId,
      flow_id: workflow.flow_id,
      started_at: startTime,
      status: TaskStatus.IN_PROGRESS,
      node_executions: [],
      metrics: {
        total_tokens: 0,
        total_api_calls: 0,
        total_cost_usd: 0,
        total_latency_ms: 0,
        engine_breakdown: {
          [WorkflowEngine.N8N]: { nodes: 0, cost_usd: 0 },
          [WorkflowEngine.DIFY]: { nodes: 0, cost_usd: 0 },
          [WorkflowEngine.DEERFLOW]: { nodes: 0, cost_usd: 0 },
          [WorkflowEngine.MOCK]: { nodes: 0, cost_usd: 0 },
        },
      },
    };

    try {
      // 拓扑排序获取执行顺序
      const order = this.dagBuilder.topologicalSort(
        workflow.nodes,
        workflow.edges,
        workflow.cross_edges
      );

      // 分批执行（可并行的批次）
      const batches = this.groupIntoBatches(workflow, order);

      for (const batch of batches) {
        if (this.config.parallel_execution) {
          // 并行执行批次内节点
          const results = await Promise.all(
            batch.map((nodeId) => this.executeNode(workflow, nodeId, batch))
          );

          // 收集结果
          for (const result of results) {
            if (result) {
              trace.node_executions.push(result);
            }
          }
        } else {
          // 串行执行
          for (const nodeId of batch) {
            const result = await this.executeNode(workflow, nodeId, batch);
            if (result) {
              trace.node_executions.push(result);
            }
          }
        }
      }

      // 确定最终状态
      const hasFailed = trace.node_executions.some(
        (n) => n.status === NodeExecutionStatus.FAILED
      );
      trace.status = hasFailed ? TaskStatus.FAILED : TaskStatus.COMPLETED;
      trace.completed_at = new Date().toISOString();
    } catch (error) {
      trace.status = TaskStatus.FAILED;
      trace.completed_at = new Date().toISOString();
      console.error(`[UnifiedExecutor] Execution failed: ${error}`);
    }

    // 聚合指标
    this.aggregateMetrics(trace);

    return trace;
  }

  /**
   * 执行单个节点
   */
  private async executeNode(
    workflow: HybridWorkflow,
    nodeId: string,
    currentBatch: string[]
  ): Promise<ExecutionTrace['node_executions'][0] | null> {
    const node = workflow.nodes.find((n) => n.id === nodeId);
    if (!node) return null;

    const nodeStartTime = Date.now();

    // 熔断检查
    if (this.config.enable_circuit_breaker && !this.circuitBreaker.canExecute(nodeId)) {
      return {
        node_id: nodeId,
        engine: node.metadata.engine,
        status: NodeExecutionStatus.SKIPPED,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        input: null,
        output: null,
        error: 'Circuit breaker open',
        latency_ms: 0,
        cost_usd: 0,
      };
    }

    // 解析输入（从缓存或前序节点）
    const inputs = this.resolveInputs(node, workflow);

    try {
      let output: any;

      // 根据引擎执行
      switch (node.metadata.engine) {
        case WorkflowEngine.N8N:
          output = await this.executeN8NNode(node, inputs);
          break;
        case WorkflowEngine.DIFY:
          output = await this.executeDifyNode(node, inputs);
          break;
        case WorkflowEngine.MOCK:
          output = this.mockExecute(node, inputs);
          break;
        default:
          throw new Error(`Unknown engine: ${node.metadata.engine}`);
      }

      // 缓存结果
      this.executionCache.set(nodeId, output);

      // 熔断成功
      this.circuitBreaker.recordSuccess(nodeId);

      const latencyMs = Date.now() - nodeStartTime;
      const costUsd = this.estimateNodeCost(node, latencyMs);

      return {
        node_id: nodeId,
        engine: node.metadata.engine,
        status: NodeExecutionStatus.COMPLETED,
        started_at: new Date(nodeStartTime).toISOString(),
        completed_at: new Date().toISOString(),
        input: inputs,
        output,
        latency_ms: latencyMs,
        cost_usd: costUsd,
      };
    } catch (error) {
      // 熔断失败
      this.circuitBreaker.recordFailure(nodeId);

      const latencyMs = Date.now() - nodeStartTime;

      return {
        node_id: nodeId,
        engine: node.metadata.engine,
        status: NodeExecutionStatus.FAILED,
        started_at: new Date(nodeStartTime).toISOString(),
        completed_at: new Date().toISOString(),
        input: inputs,
        output: null,
        error: error instanceof Error ? error.message : 'Unknown error',
        latency_ms: latencyMs,
        cost_usd: 0,
      };
    }
  }

  // ============================================
  // n8n 节点执行
  // ============================================

  private async executeN8NNode(node: HybridNode, inputs: any): Promise<any> {
    const config = node.config;
    const nodeId = config.node_id;

    console.log(`[UnifiedExecutor] Executing n8n node: ${nodeId}`);

    // HTTP 请求类节点
    if (nodeId === 'n8n_http_request') {
      const { url, method = 'POST', body } = inputs;
      return this.n8nClient.executeWebhook('/webhook/generic', method, {
        url,
        method,
        body,
      });
    }

    // Webhook 触发
    if (nodeId === 'n8n_webhook') {
      return inputs;
    }

    // 定时器
    if (nodeId === 'n8n_schedule') {
      return { triggered: true, timestamp: new Date().toISOString() };
    }

    // 数据库
    if (nodeId.startsWith('n8n_postgres') || nodeId.startsWith('n8n_mysql')) {
      const result = await this.n8nClient.executeWebhook('/webhook/db', 'POST', {
        query: inputs.query,
      });
      return result;
    }

    // 代码执行
    if (nodeId === 'n8n_code') {
      // SECURITY FIX: n8n_code 节点允许执行用户提供的 JavaScript 代码
      // 这是一个高危安全漏洞！必须使用沙箱隔离执行
      const jsCode = inputs.js_code;
      if (!jsCode || typeof jsCode !== 'string') {
        throw new Error('n8n_code node requires js_code input');
      }

      // 高危模式检测 - 防止常见命令注入
      const dangerousPatterns = [
        /require\s*\(/i,           // require() 调用
        /import\s*\(/i,            // dynamic import
        /process\./i,              // process 对象访问
        /eval\s*\(/i,              // eval 调用
        /Function\s*\(/i,          // 嵌套 Function
        /child_process/i,          // child_process 模块
        /exec\s*\(/i,              // exec 调用
        /execSync\s*\(/i,          // execSync 调用
        /\.\/|\.\.\//i,           // 路径遍历尝试
        /readFileSync\s*\(/i,     // 文件读取
        /writeFileSync\s*\(/i,    // 文件写入
      ];

      for (const pattern of dangerousPatterns) {
        if (pattern.test(jsCode)) {
          throw new Error(`n8n_code: Blocked potentially dangerous pattern: ${pattern.toString()}`);
        }
      }

      // 使用 vm.runInNewContext 限制代码访问的全局变量
      // 创建一个受限的 inputs 对象，不包含 __proto__ 等危险属性
      // SECURITY: 使用 Object.fromEntries + filter 显式排除原型链属性
      const DANGEROUS_KEYS = new Set(['__proto__', 'constructor', 'prototype', 'toString', 'valueOf']);
      const safeInputs = Object.fromEntries(
        Object.entries(inputs)
          .filter(([k, v]) => !DANGEROUS_KEYS.has(k) && typeof v !== 'function')
          .map(([k, v]) => [k, typeof v === 'object' && v !== null ? JSON.parse(JSON.stringify(v)) : v])
      );

      try {
        const vm = require('vm');
        // 创建一个禁止访问 require 和其他危险全局变量的上下文
        const context = vm.createContext({
          inputs: safeInputs,
          console: {
            log: (...args: any[]) => console.log('[n8n_code]', ...args),
            error: (...args: any[]) => console.error('[n8n_code]', ...args),
            warn: (...args: any[]) => console.warn('[n8n_code]', ...args),
          },
          setTimeout: global.setTimeout,
          setInterval: global.setInterval,
          clearTimeout: global.clearTimeout,
          clearInterval: global.clearInterval,
          Math: Math,
          JSON: JSON,
          Array: Array,
          Object: Object,
          String: String,
          Number: Number,
          Boolean: Boolean,
          RegExp: RegExp,
          Date: Date,
          Map: Map,
          Set: Set,
          Error: Error,
          Promise: Promise,
          undefined: undefined,
          null: null,
          NaN: NaN,
          Infinity: Infinity,
        }, {
          name: 'n8n_code_sandbox',
          codeGeneration: {
            strings: false,  // 禁止使用 eval 和 Function 生成新代码
            wasm: false,      // 禁止 WebAssembly
          },
        });

        const result = vm.runInContext(jsCode, context, {
          timeout: 5000,  // 5秒超时
          displayErrors: true,
        });
        return result;
      } catch (error: any) {
        if (error.code === 'ERR_SCRIPT_EXECUTION_TIMEOUT') {
          throw new Error('n8n_code execution timeout (5s)');
        }
        throw new Error(`n8n_code execution failed: ${error.message}`);
      }
    }

    // 默认：模拟执行
    return { result: `n8n_${nodeId}_executed`, inputs };
  }

  // ============================================
  // Dify 节点执行
  // ============================================

  private async executeDifyNode(node: HybridNode, inputs: any): Promise<any> {
    const config = node.config;
    const nodeId = config.node_id;

    console.log(`[UnifiedExecutor] Executing Dify node: ${nodeId}`);

    switch (nodeId) {
      case 'dify_llm': {
        const { prompt, model, temperature } = inputs;
        const result = await this.difyClient.completion(prompt, 'openclaw', {
          model,
        });
        return { text: result.output_text, usage: result.usage };
      }

      case 'dify_chat': {
        const { query, conversation_id } = inputs;
        const result = await this.difyClient.chat('default', query, 'openclaw', {
          conversation_id,
        });
        return result;
      }

      case 'dify_knowledge_retrieval': {
        const { query, dataset_id, top_k = 5 } = inputs;
        const result = await this.difyClient.retrieve({
          dataset_ids: [dataset_id],
          query,
          top_k,
        });
        return { chunks: result.records, count: result.records.length };
      }

      case 'dify_agent': {
        const { task, app_id } = inputs;
        const result = await this.difyClient.chat(app_id, task, 'openclaw');
        return { result, thoughts: [] };
      }

      case 'dify_question_classifier': {
        const { query, categories } = inputs;
        const prompt = `分类查询 "${query}" 到以下类别: ${categories.join(', ')}`;
        const result = await this.difyClient.completion(prompt, 'openclaw');
        return {
          category: result.output_text,
          confidence: 0.9,
        };
      }

      case 'dify_code': {
        // 通过 Dify Code 节点执行
        const { code, language } = inputs;
        // 简化：直接返回代码（实际应调用 Dify workflow）
        return { result: `Code (${language}) executed`, output: code };
      }

      case 'dify_completion': {
        const { prompt } = inputs;
        const result = await this.difyClient.completion(prompt, 'openclaw');
        return result;
      }

      case 'dify_http_request': {
        const { url, method, body } = inputs;
        const result = await this.difyClient.triggerWebhook(url.replace(/.*webhook/, '/webhook'), body);
        return result;
      }

      default: {
        // 通用 Dify workflow 调用
        const workflowId = config.entrypoint?.dify_workflow_id || nodeId;
        const result = await this.difyClient.runWorkflow(workflowId, inputs);
        return result;
      }
    }
  }

  // ============================================
  // 跨引擎数据流
  // ============================================

  /**
   * 处理跨引擎边
   */
  private async handleCrossEngineEdge(
    workflow: HybridWorkflow,
    edge: CrossEngineEdge,
    data: any
  ): Promise<any> {
    const fromNode = workflow.nodes.find((n) => n.id === edge.from_node);
    const toNode = workflow.nodes.find((n) => n.id === edge.to_node);

    if (!fromNode || !toNode) return data;

    // 转换数据格式
    const transformed = this.transformer.transform(data, fromNode.metadata.engine, toNode, edge.transform);

    // 通过桥接管理器传递
    const bridgeResult = await this.bridgeManager.bridge(fromNode, toNode, transformed.data, edge);

    return bridgeResult.data;
  }

  // ============================================
  // 输入解析
  // ============================================

  /**
   * 解析节点输入
   */
  private resolveInputs(node: HybridNode, workflow: HybridWorkflow): Record<string, any> {
    const config = node.config;
    const resolved: Record<string, any> = {};

    // 如果有输入映射
    if (config.input_mapping) {
      for (const [target, source] of Object.entries(config.input_mapping)) {
        // 解析 {{node_id.outputs.field}} 格式
        const match = source.match(/\{\{(\w+)\.outputs\.(\w+)\}\}/);
        if (match) {
          const [, sourceNodeId, field] = match;
          const sourceResult = this.executionCache.get(sourceNodeId);
          resolved[target] = sourceResult ? sourceResult[field] : undefined;
        } else {
          // 常量值
          resolved[target] = source;
        }
      }
    }

    // 检查跨引擎边作为输入
    const crossEdges = workflow.cross_edges.filter((e) => e.to_node === node.id);
    for (const edge of crossEdges) {
      const sourceData = this.executionCache.get(edge.from_node);
      if (sourceData) {
        const transformed = this.transformer.transform(
          sourceData,
          workflow.nodes.find((n) => n.id === edge.from_node)!.metadata.engine,
          node,
          edge.transform
        );
        if (transformed.success) {
          resolved[edge.to_node] = transformed.data;
        }
      }
    }

    return resolved;
  }

  // ============================================
  // 批次分组
  // ============================================

  /**
   * 将节点分组为可并行执行的批次
   */
  private groupIntoBatches(workflow: HybridWorkflow, order: string[]): string[][] {
    const batches: string[][] = [];
    const completed = new Set<string>();
    const nodeMap = new Map(workflow.nodes.map((n) => [n.id, n]));

    for (const nodeId of order) {
      if (completed.has(nodeId)) continue;

      // 找到所有依赖已完成的节点（可以并行）
      const ready = order.filter((id) => {
        if (completed.has(id)) return false;

        const node = nodeMap.get(id);
        if (!node) return false;

        // 检查所有入边依赖
        const fromEdges = workflow.edges.filter(([, to]) => to === id).map(([from]) => from);
        const fromCrossEdges = workflow.cross_edges.filter((e) => e.to_node === id).map((e) => e.from_node);
        const allFroms = [...fromEdges, ...fromCrossEdges];

        return allFroms.every((from) => completed.has(from));
      });

      if (ready.length === 0) continue;

      // 限制每批数量
      const batchSize = Math.min(ready.length, this.config.max_parallel_nodes);
      batches.push(ready.slice(0, batchSize));
      ready.slice(0, batchSize).forEach((id) => completed.add(id));
    }

    return batches;
  }

  // ============================================
  // 工具方法
  // ============================================

  /**
   * 模拟执行（降级/测试）
   */
  private mockExecute(node: HybridNode, inputs: any): any {
    console.log(`[UnifiedExecutor] Mock executing ${node.id}`);
    return { mock: true, node_id: node.id, inputs };
  }

  /**
   * 估算节点执行成本
   */
  private estimateNodeCost(node: HybridNode, latencyMs: number): number {
    const { tokens, api_calls } = node.metadata.cost_estimate;
    return tokens * 0.00001 + api_calls * 0.01;
  }

  /**
   * 聚合执行指标
   */
  private aggregateMetrics(trace: ExecutionTrace): void {
    trace.metrics.total_tokens = 0; // tokens tracked per-node if needed
    trace.metrics.total_api_calls = trace.node_executions.length;
    trace.metrics.total_cost_usd = trace.node_executions.reduce(
      (sum, n) => sum + n.cost_usd,
      0
    );
    trace.metrics.total_latency_ms = trace.node_executions.reduce(
      (sum, n) => sum + n.latency_ms,
      0
    );

    for (const exec of trace.node_executions) {
      const engineMetrics = trace.metrics.engine_breakdown[exec.engine];
      if (engineMetrics) {
        engineMetrics.nodes++;
        engineMetrics.cost_usd += exec.cost_usd;
      }
    }
  }

  /**
   * 保存检查点
   */
  saveCheckpoint(workflowId: string, nodeId: string, data: any): void {
    const key = `${workflowId}:${nodeId}`;
    this.checkpoints.set(key, data);
  }

  /**
   * 获取检查点
   */
  getCheckpoint(workflowId: string, nodeId: string): any | undefined {
    const key = `${workflowId}:${nodeId}`;
    return this.checkpoints.get(key);
  }

  /**
   * 清除检查点
   */
  clearCheckpoints(workflowId: string): void {
    for (const key of this.checkpoints.keys()) {
      if (key.startsWith(`${workflowId}:`)) {
        this.checkpoints.delete(key);
      }
    }
  }

  /**
   * 重置执行器状态
   */
  reset(): void {
    this.executionCache.clear();
    this.circuitBreaker.resetAll();
    this.checkpoints.clear();
  }

  /**
   * 获取配置
   */
  getConfig(): ExecutorConfig {
    return { ...this.config };
  }
}

// ============================================
// 工厂函数
// ============================================

let executorInstance: UnifiedExecutor | null = null;

export function createUnifiedExecutor(
  n8nClient: N8NClient,
  difyClient: DifyClient,
  config?: Partial<ExecutorConfig>
): UnifiedExecutor {
  if (!executorInstance) {
    executorInstance = new UnifiedExecutor(n8nClient, difyClient, config);
  }
  return executorInstance;
}

export function getUnifiedExecutor(): UnifiedExecutor | null {
  return executorInstance;
}
