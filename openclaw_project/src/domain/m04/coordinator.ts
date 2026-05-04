/**
 * M04 统一调度器实现
 * ================================================
 * 三系统协同调度 · DAG执行 · 熔断机制
 * 搜索系统 · 任务系统 · 工作流系统
 * ================================================
 */

import {
  CoordinatorConfig,
  ExecutionContext,
  CoordinatorResult,
  SystemType,
  Task,
  TaskDAG,
  TaskNode,
  TaskStatus,
  NodeStatus,
  Workflow,
  SearchResponse,
  DEFAULT_COORDINATOR_CONFIG,
  TaskCategory,
  RiskLevel,
} from './types';

import {
  SharedContext,
  CrossSystemAggregator,
  sharedContext,
  crossSystemAggregator,
} from './shared_context';

import { SearchAdapter } from './adapters/search_adapter';
import { N8NClient } from '../../infrastructure/workflow/n8n_client';
import { DifyClient } from '../../infrastructure/workflow/dify_client';

import * as crypto from 'crypto';

// M11 执行器适配器 (Claude Code CLI 集成)
import { executorAdapter, ExecutorType } from '../m11/mod';

// GStack Skill 路由器
import { SkillRouter, skillRouter } from './skill_router';
import { SkillLoader, skillLoader } from './skill_loader';

import { UnifiedWorkflowBuilder, unifiedWorkflowBuilder } from './unified_builder';
import { UnifiedExecutor, createUnifiedExecutor } from './unified_executor';
import { DifyAdapter, createDifyAdapter } from './dify_adapter';
import { BridgeManager } from '../../infrastructure/workflow/bridge_manager';
import {
  WorkflowEngine,
  NodeCapability,
  WhitelistLevel,
  NodeCategory,
} from './engine_enum';

// ============================================
// 统一调度器
// ============================================

/**
 * 三系统统一调度器
 *
 * 核心职责：
 * - 接收用户请求，判定使用哪个系统
 * - 协调搜索/任务/工作流三系统执行
 * - 管理DAG执行和依赖
 * - 熔断机制和错误恢复
 * - Checkpoint持久化
 */
export class Coordinator {
  private config: CoordinatorConfig;
  private activeTasks: Map<string, Task>;
  private checkpoints: Map<string, Task>;
  private sharedContext: SharedContext;
  private aggregator: CrossSystemAggregator;
  private searchAdapter: SearchAdapter;
  private n8nClient: N8NClient;
  private difyClient: DifyClient;
  private unifiedBuilder: UnifiedWorkflowBuilder;
  private unifiedExecutor: UnifiedExecutor;
  private difyAdapter: DifyAdapter;
  private bridgeManager: BridgeManager;
  private skillRouter: SkillRouter;
  private skillLoader: SkillLoader;

  constructor(config: CoordinatorConfig = DEFAULT_COORDINATOR_CONFIG) {
    this.config = config;
    this.activeTasks = new Map();
    this.checkpoints = new Map();
    this.sharedContext = sharedContext;
    this.aggregator = crossSystemAggregator;
    this.searchAdapter = new SearchAdapter();

    // N8N客户端初始化 - 从环境变量读取配置
    this.n8nClient = new N8NClient(
      process.env.N8N_HOST || 'localhost',
      Number(process.env.N8N_PORT) || 5678,
      process.env.N8N_API_KEY || undefined,
      process.env.N8N_WEBHOOK_URL || 'http://localhost:5678'
    );

    // Dify客户端初始化
    this.difyClient = new DifyClient({
      baseUrl: process.env.DIFY_BASE_URL || 'http://localhost/v1',
      apiKey: process.env.DIFY_API_KEY || '',
      timeout: parseInt(process.env.DIFY_TIMEOUT_MS || '60000'),
    });

    // 统一构建器和执行器
    this.unifiedBuilder = unifiedWorkflowBuilder;
    this.unifiedExecutor = createUnifiedExecutor(this.n8nClient, this.difyClient, {
      enable_checkpoint: true,
      checkpoint_path: '/tmp/openclaw/checkpoints',
      enable_circuit_breaker: true,
      circuit_breaker_threshold: 3,
      parallel_execution: true,
      max_parallel_nodes: 5,
    });

    // Dify适配器
    this.difyAdapter = createDifyAdapter({
      baseUrl: process.env.DIFY_BASE_URL,
      apiKey: process.env.DIFY_API_KEY,
      timeoutMs: parseInt(process.env.DIFY_TIMEOUT_MS || '60000'),
    });

    // 桥接管理器
    this.bridgeManager = new BridgeManager(this.n8nClient, this.difyClient);

    // GStack Skill 路由器和加载器
    this.skillRouter = skillRouter;
    this.skillLoader = skillLoader;
  }

  /**
   * 统一入口：处理任意请求
   */
  async execute(context: ExecutionContext): Promise<CoordinatorResult> {
    const startTime = Date.now();

    try {
      let result: any;

      switch (context.system_type) {
        case SystemType.SEARCH:
          result = await this.handleSearchRequest(context);
          break;
        case SystemType.TASK:
          result = await this.handleTaskRequest(context);
          break;
        case SystemType.WORKFLOW:
          result = await this.handleWorkflowRequest(context);
          break;
        case SystemType.CLAUDE_CODE:
          result = await this.handleClaudeCodeRequest(context);
          break;
        case SystemType.GSTACK_SKILL:
          result = await this.handleGStackSkillRequest(context);
          break;
        default:
          throw new Error(`Unknown system type: ${context.system_type}`);
      }

      return {
        success: true,
        system_type: context.system_type,
        result,
        execution_time_ms: Date.now() - startTime,
        context,
      };
    } catch (error) {
      return {
        success: false,
        system_type: context.system_type,
        error: error instanceof Error ? error.message : 'Unknown error',
        execution_time_ms: Date.now() - startTime,
        context,
      };
    }
  }

  /**
   * 处理搜索请求
   */
  private async handleSearchRequest(context: ExecutionContext): Promise<SearchResponse> {
    // 存储上下文
    this.sharedContext.set(`search_context_${context.request_id}`, context);

    // 获取查询参数
    const query = context.metadata?.query as string || '';
    const depth = (context.metadata?.depth as 1 | 2 | 3) || 3;

    // 调用实际搜索系统
    const response = await this.searchAdapter.executeThreeRoundSearch(query, depth);

    this.aggregator.setSearchResult(response);
    return response;
  }

  /**
   * 处理任务请求
   */
  private async handleTaskRequest(context: ExecutionContext): Promise<Task> {
    const goal = context.metadata?.goal as string;
    if (!goal) {
      throw new Error('Task goal is required');
    }

    // 创建任务DAG
    const task = this.createTask(context.request_id, goal);

    // 存储活跃任务
    this.activeTasks.set(task.task_id, task);

    // 执行DAG
    await this.executeDAG(task);

    return task;
  }

  /**
   * 处理工作流请求
   */
  private async handleWorkflowRequest(context: ExecutionContext): Promise<Workflow> {
    const workflowId = context.metadata?.workflow_id as string;
    const webhookPath = context.metadata?.webhook_path as string;
    const workflowData = context.metadata?.workflow_data;

    // 如果有workflow_id，获取已有工作流
    if (workflowId) {
      return await this.n8nClient.getWorkflow(workflowId) as Workflow;
    }

    // 如果有webhook_path，通过webhook触发执行
    if (webhookPath) {
      const result = await this.n8nClient.executeWebhook(webhookPath, 'POST', workflowData);
      return result as Workflow;
    }

    // 创建新工作流
    if (workflowData) {
      return await this.n8nClient.createWorkflow(workflowData) as Workflow;
    }

    // 兜底：返回空的Workflow对象
    const workflow: Workflow = {
      flow_id: `wf_${Date.now()}`,
      created_by: 'coordinator',
      created_at: new Date().toISOString(),
      trigger: { type: 'manual' },
      nodes: [],
      edges: [],
      estimated_cost_usd: 0.01,
      risk_level: RiskLevel.LOW,
    };

    return workflow;
  }

  /**
   * 处理 Claude Code CLI 请求 (M11 ExecutorAdapter 集成)
   *
   * 通过 M11 ExecutorAdapter 调用 Claude Code CLI 执行自主任务
   * 使用 --agent openclaw-master 标志赋予同等执行能力
   */
  private async handleClaudeCodeRequest(context: ExecutionContext): Promise<{
    task_id: string;
    output: string;
    execution_time_ms: number;
  }> {
    const instruction = context.metadata?.instruction as string;
    if (!instruction) {
      throw new Error('Claude Code instruction is required');
    }

    // 从 metadata 获取可选参数
    const params = {
      timeout_ms: context.metadata?.timeout_ms as number || 120000,
      sandboxed: context.metadata?.sandboxed as boolean ?? true,
    };

    // 1. 提交任务到 M11 ExecutorAdapter
    const taskId = await executorAdapter.submit(
      ExecutorType.CLAUDE_CODE,
      instruction,
      params,
      params.sandboxed
    );

    // 2. 执行任务
    const startTime = Date.now();
    const result = await executorAdapter.execute(taskId);

    return {
      task_id: taskId,
      output: result.success ? (result.result?.output || result.result) : `Error: ${result.error}`,
      execution_time_ms: Date.now() - startTime,
    };
  }

  /**
   * 处理 GStack Skill 请求
   *
   * 通过 SkillRouter 匹配用户意图，然后通过 M11 ExecutorAdapter 执行
   */
  private async handleGStackSkillRequest(context: ExecutionContext): Promise<{
    skill: string;
    description: string;
    task_id: string;
    output: string;
    execution_time_ms: number;
  }> {
    const intent = context.metadata?.intent as string;
    const taskContext = context.metadata?.task_context as string || '';

    if (!intent) {
      throw new Error('GStack Skill intent is required');
    }

    // 1. 路由意图到 Skill
    const routeResult = this.skillRouter.routeAndBuild(intent, taskContext);

    if (!routeResult.matched) {
      throw new Error(`No GStack Skill matched for intent: "${intent}"`);
    }

    console.log(`[Coordinator] Routing intent to ${routeResult.skill}: ${routeResult.description}`);

    // 2. 通过 M11 ExecutorAdapter 执行 Skill
    const skillInstruction = routeResult.instruction!;
    const params = {
      timeout_ms: context.metadata?.timeout_ms as number || 180000, // Skill 执行可能需要更长时间
      sandboxed: context.metadata?.sandboxed as boolean ?? true,
      skill: routeResult.skill,
    };

    const taskId = await executorAdapter.submit(
      ExecutorType.CLAUDE_CODE,
      skillInstruction,
      params,
      params.sandboxed
    );

    const startTime = Date.now();
    const result = await executorAdapter.execute(taskId);

    return {
      skill: routeResult.skill!,
      description: routeResult.description!,
      task_id: taskId,
      output: result.success ? (result.result?.output || result.result) : `Error: ${result.error}`,
      execution_time_ms: Date.now() - startTime,
    };
  }

  /**
   * 获取可用 GStack Skills 列表
   */
  getAvailableSkills(): { skill: string; description: string; category: string }[] {
    return this.skillRouter.getAllSkills();
  }

  /**
   * 检查 Skill 路由是否可用
   */
  isSkillRoutingAvailable(): boolean {
    return this.skillRouter.hasSkillsDirectory();
  }

  // ============================================
  // 统一工作流处理（n8n + Dify 融合）
  // ============================================

  /**
   * 处理统一工作流请求
   *
   * 使用统一的 builder + executor 处理 n8n 和 Dify 混合工作流
   * 智能体描述高层目标 → 自动拆解为混合 DAG → 跨引擎执行
   */
  async handleUnifiedWorkflowRequest(
    goal: string,
    constraints?: {
      max_cost_usd?: number;
      max_latency_ms?: number;
      preferred_engine?: WorkflowEngine;
      whitelist_only?: boolean;
      streaming_required?: boolean;
    }
  ): Promise<{
    workflow: any;
    execution_trace: any;
    engine_breakdown: { n8n: number; dify: number };
    cost_estimate: number;
    execution_plan: string[];
  }> {
    console.log(`[Coordinator] handleUnifiedWorkflowRequest: ${goal}`);

    // 1. 使用统一构建器从目标构建混合工作流
    const buildResult = await this.unifiedBuilder.build({
      goal,
      constraints: {
        max_cost_usd: constraints?.max_cost_usd,
        max_latency_ms: constraints?.max_latency_ms,
        preferred_engine: constraints?.preferred_engine,
        whitelist_only: constraints?.whitelist_only,
        streaming_required: constraints?.streaming_required,
      },
    });

    console.log(`[Coordinator] Built hybrid workflow with ${buildResult.engine_breakdown.n8n} n8n + ${buildResult.engine_breakdown.dify} Dify nodes`);

    // 2. 使用统一执行器执行工作流
    const executionTrace = await this.unifiedExecutor.execute(buildResult.workflow);

    console.log(`[Coordinator] Execution completed: ${executionTrace.status}`);

    // 3. 返回执行结果
    return {
      workflow: buildResult.workflow,
      execution_trace: executionTrace,
      engine_breakdown: buildResult.engine_breakdown,
      cost_estimate: buildResult.cost_estimate,
      execution_plan: buildResult.execution_plan,
    };
  }

  /**
   * 执行已有混合工作流
   */
  async executeUnifiedWorkflow(workflow: any): Promise<any> {
    console.log(`[Coordinator] executeUnifiedWorkflow: ${workflow.flow_id}`);
    return await this.unifiedExecutor.execute(workflow);
  }

  /**
   * 获取统一执行器状态
   */
  getUnifiedExecutorStatus(): {
    cache_size: number;
    checkpoints_size: number;
    config: any;
  } {
    return {
      cache_size: (this.unifiedExecutor as any).executionCache?.size || 0,
      checkpoints_size: (this.unifiedExecutor as any).checkpoints?.size || 0,
      config: this.unifiedExecutor.getConfig(),
    };
  }

  /**
   * 重置统一执行器
   */
  resetUnifiedExecutor(): void {
    this.unifiedExecutor.reset();
    console.log('[Coordinator] Unified executor reset');
  }

  /**
   * 创建任务
   */
  createTask(taskId: string, goal: string): Task {
    const dag = this.generateDAG(goal);

    const task: Task = {
      task_id: taskId,
      goal,
      status: TaskStatus.PENDING,
      created_at: new Date().toISOString(),
      dag,
      total_tokens: 0,
      checkpoints: [],
    };

    return task;
  }

  /**
   * 生成DAG（简化实现）
   */
  private generateDAG(goal: string): TaskDAG {
    // 简化：根据目标关键词生成分解
    const nodes: TaskNode[] = [];

    // 根节点
    const rootNode: TaskNode = {
      id: 'n_root',
      name: goal,
      category: TaskCategory.PLANNING,
      status: NodeStatus.PENDING,
      depends_on: [],
      timeout_min: this.config.default_timeout_min,
      retry_count: 0,
    };
    nodes.push(rootNode);

    // 检测是否需要搜索
    if (goal.includes('搜索') || goal.includes('调研') || goal.includes('查找')) {
      nodes.push({
        id: 'n_search',
        name: '执行搜索',
        category: TaskCategory.SEARCH,
        status: NodeStatus.PENDING,
        depends_on: ['n_root'],
        timeout_min: 5,
        retry_count: 0,
      });
    }

    // 检测是否需要代码
    if (goal.includes('代码') || goal.includes('实现') || goal.includes('开发')) {
      nodes.push({
        id: 'n_code',
        name: '代码生成',
        category: TaskCategory.CODE_GEN,
        status: NodeStatus.PENDING,
        depends_on: ['n_root'],
        timeout_min: 10,
        retry_count: 0,
      });
    }

    // 检测是否需要分析
    if (goal.includes('分析') || goal.includes('对比')) {
      nodes.push({
        id: 'n_analysis',
        name: '分析执行',
        category: TaskCategory.ANALYSIS,
        status: NodeStatus.PENDING,
        depends_on: ['n_search'],
        timeout_min: 8,
        retry_count: 0,
      });
    }

    // 构建边
    const edges: [string, string][] = [];
    for (const node of nodes) {
      for (const dep of node.depends_on) {
        edges.push([dep, node.id]);
      }
    }

    return { nodes, edges };
  }

  /**
   * 执行DAG（优化版本：支持并行执行独立节点）
   */
  async executeDAG(task: Task): Promise<void> {
    task.status = TaskStatus.IN_PROGRESS;

    // 拓扑排序获取执行顺序
    const executionOrder = this.topologicalSort(task.dag);
    const nodeMap = new Map(task.dag.nodes.map(n => [n.id, n]));
    const completedNodes = new Set<string>();

    // 分批执行：每一批是可以并行执行的节点
    let batchIndex = 0;
    while (completedNodes.size < task.dag.nodes.length) {
      // 找到所有依赖已完成的节点（可以并行执行）
      const readyNodes = executionOrder
        .filter(nodeId => {
          const node = nodeMap.get(nodeId);
          if (!node) return false;
          if (completedNodes.has(nodeId)) return false;

          // 检查所有依赖是否已完成
          const deps = task.dag.edges
            .filter(([_, to]) => to === nodeId)
            .map(([from]) => from);
          return deps.every(dep => completedNodes.has(dep));
        })
        .map(nodeId => nodeMap.get(nodeId)!);

      if (readyNodes.length === 0) {
        // 没有可执行的节点但还有未完成的节点，可能是循环依赖
        break;
      }

      // 并行执行这一批节点
      const batchPromises = readyNodes.map(async (node) => {
        node.status = NodeStatus.RUNNING;
        task.current_node_id = node.id;

        // 保存checkpoint
        if (this.config.enable_checkpoint) {
          this.saveCheckpoint(task);
        }

        try {
          await this.executeNode(node, task);
          node.status = NodeStatus.COMPLETED;
        } catch (error) {
          node.status = NodeStatus.FAILED;
          node.error = error instanceof Error ? error.message : 'Unknown error';
          if (node.retry_count < 3) {
            node.retry_count++;
            node.status = NodeStatus.PENDING;
          }
        }
      });

      await Promise.all(batchPromises);

      // 标记这一批节点为已完成
      readyNodes.forEach(node => {
        if (node.status === NodeStatus.COMPLETED) {
          completedNodes.add(node.id);
        }
      });

      batchIndex++;
      // 防止无限循环
      if (batchIndex > 1000) break;
    }

    // 确定最终状态
    const hasFailed = task.dag.nodes.some(n => n.status === NodeStatus.FAILED && n.retry_count >= 3);
    task.status = hasFailed ? TaskStatus.FAILED : TaskStatus.COMPLETED;
  }

  /**
   * 执行单个节点
   */
  private async executeNode(node: TaskNode, task: Task): Promise<void> {
    // 模拟执行
    await new Promise(resolve => setTimeout(resolve, 100));

    // 简化：根据category设置result
    node.result_summary = `Completed ${node.category} task: ${node.name}`;
    node.tokens_used = crypto.randomInt(500, 1501);
    task.total_tokens += node.tokens_used || 0;
  }

  /**
   * 拓扑排序
   */
  private topologicalSort(dag: TaskDAG): string[] {
    const inDegree = new Map<string, number>();
    const adjList = new Map<string, string[]>();

    // 初始化
    for (const node of dag.nodes) {
      inDegree.set(node.id, 0);
      adjList.set(node.id, []);
    }

    // 计算入度和构建邻接表
    for (const [from, to] of dag.edges) {
      inDegree.set(to, (inDegree.get(to) || 0) + 1);
      adjList.get(from)?.push(to);
    }

    // BFS
    const queue: string[] = [];
    for (const [id, degree] of inDegree.entries()) {
      if (degree === 0) queue.push(id);
    }

    const result: string[] = [];
    while (queue.length > 0) {
      const nodeId = queue.shift()!;
      result.push(nodeId);

      for (const neighbor of adjList.get(nodeId) || []) {
        inDegree.set(neighbor, inDegree.get(neighbor)! - 1);
        if (inDegree.get(neighbor) === 0) {
          queue.push(neighbor);
        }
      }
    }

    return result;
  }

  /**
   * 保存checkpoint
   */
  private saveCheckpoint(task: Task): void {
    const checkpointId = `${task.task_id}_${task.current_node_id}`;
    this.checkpoints.set(checkpointId, JSON.parse(JSON.stringify(task)));
    task.checkpoints.push(checkpointId);
  }

  /**
   * 恢复checkpoint
   */
  recoverFromCheckpoint(taskId: string): Task | null {
    const checkpoints = Array.from(this.checkpoints.values())
      .filter(t => t.task_id === taskId)
      .sort((a, b) => b.checkpoints.length - a.checkpoints.length);

    return checkpoints[0] || null;
  }

  /**
   * 获取活跃任务
   */
  getActiveTasks(): Task[] {
    return Array.from(this.activeTasks.values());
  }

  /**
   * 获取任务状态
   */
  getTaskStatus(taskId: string): Task | undefined {
    return this.activeTasks.get(taskId);
  }

  /**
   * 取消任务
   */
  cancelTask(taskId: string): boolean {
    const task = this.activeTasks.get(taskId);
    if (!task) return false;

    task.status = TaskStatus.CANCELLED;
    return true;
  }

  /**
   * 获取配置
   */
  getConfig(): CoordinatorConfig {
    return { ...this.config };
  }
}

// ============================================
// 单例导出
// ============================================

export const coordinator = new Coordinator();
