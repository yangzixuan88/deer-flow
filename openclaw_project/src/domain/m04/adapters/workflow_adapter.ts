/**
 * M04 工作流系统适配器
 * ================================================
 * 工作流构建 · 节点注册 · SOP管理
 * ================================================
 */

import {
  Workflow,
  WorkflowNode,
  WorkflowExecution,
  NodeType,
  RiskLevel,
  TaskStatus,
} from '../types';

import { N8NClient } from '../../../infrastructure/workflow/n8n_client';

import * as crypto from 'crypto';

// ============================================
// 工作流系统适配器
// ============================================

/**
 * 节点注册项
 */
interface NodeRegistryItem {
  node_id: string;
  category: 'tool' | 'cli' | 'mcp' | 'llm' | 'control' | 'sop';
  name: string;
  description: string;
  inputs: { name: string; type: string; optional?: boolean }[];
  outputs: { name: string; type: string }[];
  cost_estimate: {
    tokens: number;
    api_calls: number;
    latency_ms: number;
  };
  whitelist_level: 'white' | 'gray' | 'black';
  skill_file?: string;
}

/**
 * 工作流系统适配器
 *
 * 封装工作流系统的核心能力：
 * - 6步自主构建
 * - 节点注册表管理
 * - SOP模板化
 */
export class WorkflowAdapter {
  private nodeRegistry: Map<string, NodeRegistryItem>;
  private workflows: Map<string, Workflow>;
  private executions: Map<string, WorkflowExecution>;
  private sopTemplates: Map<string, Workflow>;
  private n8nClient: N8NClient | null = null;
  private n8nConfig: { host: string; port: number; apiKey: string; webhookUrl: string } | null = null;

  constructor() {
    this.nodeRegistry = new Map();
    this.workflows = new Map();
    this.executions = new Map();
    this.sopTemplates = new Map();
    this.initN8NClient();
    this.registerDefaultNodes();
  }

  /**
   * 初始化 N8N 客户端
   */
  private initN8NClient(): void {
    const host = process.env.N8N_HOST || 'localhost';
    const port = parseInt(process.env.N8N_PORT || '5678');
    const apiKey = process.env.N8N_API_KEY || undefined;
    const webhookUrl = process.env.N8N_WEBHOOK_URL || `http://${host}:${port}/webhook`;

    if (apiKey) {
      this.n8nConfig = { host, port, apiKey, webhookUrl };
      this.n8nClient = new N8NClient(host, port, apiKey, webhookUrl);
      console.log(`[WorkflowAdapter] N8N client initialized: ${host}:${port}`);
    } else {
      // Only warn in verbose/debug mode - this is expected when N8N is optional
      if (process.env.DEBUG === 'true' || process.env.LOG_LEVEL === 'debug') {
        console.warn('[WorkflowAdapter] N8N_API_KEY not set, workflow execution will be mocked');
      }
    }
  }

  /**
   * 注册默认节点
   */
  private registerDefaultNodes(): void {
    const defaultNodes: NodeRegistryItem[] = [
      // 触发节点
      {
        node_id: 'trigger_heartbeat',
        category: 'tool',
        name: 'HEARTBEAT定时',
        description: '定时触发工作流',
        inputs: [{ name: 'interval_min', type: 'number' }],
        outputs: [{ name: 'triggered', type: 'boolean' }],
        cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 10 },
        whitelist_level: 'white',
      },
      // 搜索节点
      {
        node_id: 'searxng_search',
        category: 'tool',
        name: 'SearXNG搜索',
        description: '本地部署的聚合搜索引擎',
        inputs: [
          { name: 'query', type: 'string' },
          { name: 'engines', type: 'array', optional: true },
        ],
        outputs: [
          { name: 'results', type: 'array' },
          { name: 'summary', type: 'string' },
        ],
        cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 800 },
        whitelist_level: 'white',
      },
      {
        node_id: 'tavily_search',
        category: 'tool',
        name: 'Tavily搜索',
        description: 'AI优化搜索API',
        inputs: [{ name: 'query', type: 'string' }],
        outputs: [{ name: 'results', type: 'array' }],
        cost_estimate: { tokens: 500, api_calls: 1, latency_ms: 1000 },
        whitelist_level: 'white',
      },
      // LLM节点
      {
        node_id: 'llm_claude',
        category: 'llm',
        name: 'Claude推理',
        description: 'Claude Sonnet 4.0推理',
        inputs: [
          { name: 'prompt', type: 'string' },
          { name: 'model', type: 'string', optional: true },
        ],
        outputs: [{ name: 'response', type: 'string' }],
        cost_estimate: { tokens: 1000, api_calls: 1, latency_ms: 2000 },
        whitelist_level: 'white',
      },
      // 控制节点
      {
        node_id: 'control_if',
        category: 'control',
        name: 'IF条件分支',
        description: '条件判断分支',
        inputs: [
          { name: 'condition', type: 'boolean' },
          { name: 'true_branch', type: 'array' },
          { name: 'false_branch', type: 'array' },
        ],
        outputs: [{ name: 'result', type: 'any' }],
        cost_estimate: { tokens: 10, api_calls: 0, latency_ms: 1 },
        whitelist_level: 'white',
      },
      {
        node_id: 'control_parallel',
        category: 'control',
        name: 'PARALLEL并行',
        description: '并行执行多个节点',
        inputs: [{ name: 'nodes', type: 'array' }],
        outputs: [{ name: 'results', type: 'array' }],
        cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
        whitelist_level: 'white',
      },
      {
        node_id: 'control_retry',
        category: 'control',
        name: 'RETRY重试',
        description: '失败自动重试',
        inputs: [
          { name: 'node', type: 'any' },
          { name: 'max_attempts', type: 'number' },
        ],
        outputs: [{ name: 'result', type: 'any' }],
        cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
        whitelist_level: 'white',
      },
      // SOP节点
      {
        node_id: 'sop_three_round_search',
        category: 'sop',
        name: '三轮搜索SOP',
        description: '标准三轮搜索流程',
        inputs: [{ name: 'query', type: 'string' }],
        outputs: [{ name: 'results', type: 'object' }],
        cost_estimate: { tokens: 2000, api_calls: 3, latency_ms: 5000 },
        whitelist_level: 'white',
        skill_file: '~/.deerflow/skills/search/SKILL.md',
      },
    ];

    for (const node of defaultNodes) {
      this.nodeRegistry.set(node.node_id, node);
    }
  }

  /**
   * 注册节点
   */
  registerNode(node: NodeRegistryItem): void {
    this.nodeRegistry.set(node.node_id, node);
  }

  /**
   * 获取节点注册信息
   */
  getNode(nodeId: string): NodeRegistryItem | undefined {
    return this.nodeRegistry.get(nodeId);
  }

  /**
   * 列出所有节点
   */
  listNodes(category?: string): NodeRegistryItem[] {
    const all = Array.from(this.nodeRegistry.values());
    if (category) {
      return all.filter(n => n.category === category);
    }
    return all;
  }

  /**
   * 构建工作流（6步流程）
   */
  async buildWorkflow(
    goal: string,
    constraints?: {
      max_cost?: number;
      risk_level?: RiskLevel;
      max_duration_ms?: number;
    }
  ): Promise<Workflow> {
    const flowId = `wf_${Date.now()}_${crypto.randomUUID().replace(/-/g, '').substring(0, 9)}`;

    // 简化实现：基于目标自动构建
    const nodes: WorkflowNode[] = [];
    const edges: [string, string][] = [];

    // 分析目标类型
    if (goal.includes('搜索')) {
      // 添加搜索节点
      nodes.push({
        id: 'n_search',
        type: NodeType.TOOL,
        config: { node_id: 'searxng_search', query: goal },
      });
    }

    if (goal.includes('分析') || goal.includes('对比')) {
      // 添加分析节点
      nodes.push({
        id: 'n_analyze',
        type: NodeType.LLM,
        config: { node_id: 'llm_claude', prompt: `分析: ${goal}` },
      });

      if (nodes.find(n => n.id === 'n_search')) {
        edges.push(['n_search', 'n_analyze']);
      }
    }

    if (goal.includes('发送') || goal.includes('通知')) {
      // 添加通知节点
      nodes.push({
        id: 'n_notify',
        type: NodeType.TOOL,
        config: { action: 'send_notification' },
      });

      const prevNode = nodes[nodes.length - 2]?.id || 'n_analyze';
      edges.push([prevNode, 'n_notify']);
    }

    // 默认根节点
    if (nodes.length === 0) {
      nodes.push({
        id: 'n_start',
        type: NodeType.LLM,
        config: { node_id: 'llm_claude', prompt: goal },
      });
    }

    const workflow: Workflow = {
      flow_id: flowId,
      created_by: 'workflow_adapter',
      created_at: new Date().toISOString(),
      trigger: { type: 'manual' },
      nodes,
      edges,
      estimated_cost_usd: this.estimateCost(nodes),
      risk_level: constraints?.risk_level || RiskLevel.LOW,
    };

    this.workflows.set(flowId, workflow);
    return workflow;
  }

  /**
   * 估算成本
   */
  private estimateCost(nodes: WorkflowNode[]): number {
    let cost = 0;
    for (const node of nodes) {
      const registry = this.nodeRegistry.get(node.config.node_id as string);
      if (registry) {
        cost += registry.cost_estimate.tokens * 0.00001; // 简化token成本
        cost += registry.cost_estimate.api_calls * 0.01; // API调用成本
      }
    }
    return Math.max(cost, 0.001);
  }

  /**
   * 执行工作流
   */
  async execute(flowId: string): Promise<WorkflowExecution> {
    const workflow = this.workflows.get(flowId);
    if (!workflow) {
      throw new Error(`Workflow ${flowId} not found`);
    }

    const executionId = `exec_${Date.now()}_${crypto.randomUUID().replace(/-/g, '').substring(0, 9)}`;
    const startTime = new Date().toISOString();

    const execution: WorkflowExecution = {
      execution_id: executionId,
      flow_id: flowId,
      status: TaskStatus.IN_PROGRESS,
      started_at: startTime,
    };

    this.executions.set(executionId, execution);

    try {
      // 模拟执行
      for (const node of workflow.nodes) {
        execution.current_node = node.id;
        await this.executeNode(node);
      }

      execution.status = TaskStatus.COMPLETED;
      execution.completed_at = new Date().toISOString();
    } catch (error) {
      execution.status = TaskStatus.FAILED;
      execution.error = error instanceof Error ? error.message : 'Unknown error';
      execution.completed_at = new Date().toISOString();
    }

    return execution;
  }

  /**
   * 执行单个节点
   */
  private async executeNode(node: WorkflowNode): Promise<void> {
    const registry = this.nodeRegistry.get(node.config.node_id as string);
    const nodeId = node.config.node_id as string;

    // 检查是否有 N8N 集成的 workflow 节点
    if (nodeId.startsWith('n8n_') && this.n8nClient) {
      const workflowId = nodeId.replace('n8n_', '');
      try {
        // 通过 N8N API 触发 workflow
        await this.n8nClient.executeWebhook(`/${workflowId}`, 'POST', node.config);
        return;
      } catch (error) {
        console.warn(`[WorkflowAdapter] N8N workflow ${workflowId} failed, falling back to mock`);
      }
    }

    // 检查是否是 SOP 节点
    if (registry?.skill_file && this.n8nClient) {
      // SOP 节点可以尝试通过 n8n 执行
      console.log(`[WorkflowAdapter] Executing SOP node: ${nodeId}`);
    }

    // 模拟执行延迟 (降级方案)
    const latency = registry?.cost_estimate.latency_ms || 100;
    await new Promise(resolve => setTimeout(resolve, latency / 10));
  }

  /**
   * 晋升为SOP
   */
  promoteToSOP(flowId: string, name: string): string | null {
    const workflow = this.workflows.get(flowId);
    if (!workflow) return null;

    workflow.sop_source = name;
    this.sopTemplates.set(name, workflow);
    return name;
  }

  /**
   * 获取SOP模板
   */
  getSOP(name: string): Workflow | undefined {
    return this.sopTemplates.get(name);
  }

  /**
   * 列出所有SOP
   */
  listSOPs(): string[] {
    return Array.from(this.sopTemplates.keys());
  }

  /**
   * 获取工作流
   */
  getWorkflow(flowId: string): Workflow | undefined {
    return this.workflows.get(flowId);
  }

  /**
   * 列出所有工作流
   */
  listWorkflows(): Workflow[] {
    return Array.from(this.workflows.values());
  }

  /**
   * 获取执行记录
   */
  getExecution(executionId: string): WorkflowExecution | undefined {
    return this.executions.get(executionId);
  }
}

// ============================================
// 单例导出
// ============================================

export const workflowAdapter = new WorkflowAdapter();
