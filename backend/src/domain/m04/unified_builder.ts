/**
 * 统一工作流构建器
 * ================================================
 * 智能体描述高层目标 → 自动拆解为 n8n+Dify 混合 DAG
 * 完全对智能体屏蔽引擎差异
 * ================================================
 */

import {
  WorkflowEngine,
  NodeCapability,
  NodeCategory,
  WhitelistLevel,
  CrossEngineDataFlow,
} from './engine_enum';

import {
  UniversalNodeConfig,
  NodeMetadata,
  HybridWorkflow,
  HybridNode,
  CrossEngineEdge,
  IntentAnalysis,
  MatchResult,
  RiskLevel,
} from './types';

import { unifiedNodeRegistry } from './unified_registry';

// ============================================
// 构建请求/结果类型
// ============================================

export interface BuildRequest {
  /** 智能体的高层描述 */
  goal: string;
  /** 可选的执行上下文 */
  context?: Record<string, any>;
  /** 约束条件 */
  constraints?: BuildConstraints;
}

export interface BuildConstraints {
  /** 最大成本（USD） */
  max_cost_usd?: number;
  /** 最大延迟（ms） */
  max_latency_ms?: number;
  /** 必需的能力 */
  required_capabilities?: NodeCapability[];
  /** 强制使用特定引擎 */
  preferred_engine?: WorkflowEngine;
  /** 仅使用白名单节点 */
  whitelist_only?: boolean;
  /** 需要流式输出 */
  streaming_required?: boolean;
  /** 最大节点数 */
  max_nodes?: number;
}

export interface BuildResult {
  /** 生成的混合工作流 */
  workflow: HybridWorkflow;
  /** 引擎分布统计 */
  engine_breakdown: { n8n: number; dify: number };
  /** 成本估算 */
  cost_estimate: number;
  /** 执行计划说明 */
  execution_plan: string[];
  /** 意图分析结果 */
  intent: IntentAnalysis;
}

// ============================================
// 意图分析器
// ============================================

/**
 * 关键词 → 能力映射表
 */
const KEYWORD_CAPABILITY_MAP: Map<NodeCapability, string[]> = new Map([
  [NodeCapability.LLM, ['分析', '推理', '思考', '生成', '写', '总结', '翻译', '解释', 'LLM', '大模型', 'GPT', 'Claude']],
  [NodeCapability.RAG, ['搜索', '调研', '查找', '知识', '文档', 'RAG', '检索', '查询', '资料']],
  [NodeCapability.AGENT, ['Agent', '自主', '工具调用', 'ReAct', '规划', '多步']],
  [NodeCapability.CLASSIFICATION, ['分类', '意图', '路由', '判断', '识别']],
  [NodeCapability.CODE_EXEC, ['代码', '编程', '实现', '开发', 'Python', 'JavaScript', '计算']],
  [NodeCapability.HTTP, ['请求', 'API', '调用', '获取数据', '抓取']],
  [NodeCapability.DATABASE, ['数据库', 'SQL', '查询', '存储', 'PostgreSQL', 'MySQL']],
  [NodeCapability.SCHEDULE, ['定时', '调度', '周期', 'Cron', '自动']],
  [NodeCapability.WEBHOOK, ['Webhook', '回调', '通知', '推送', '发送']],
  [NodeCapability.CONDITION, ['如果', '条件', '分支', '判断', 'IF', 'Switch']],
  [NodeCapability.ITERATION, ['循环', '迭代', '批量', '遍历', '每个']],
  [NodeCapability.TRANSFORM, ['转换', '清洗', '格式化', 'JSON', 'XML', 'CSV']],
  [NodeCapability.FILE, ['文件', '读取', '写入', '上传', '下载']],
  [NodeCapability.STREAMING, ['流式', 'SSE', '实时', 'Streaming']],
  [NodeCapability.REASONING, ['推理', '思考', '分析原因', '逻辑']],
]);

/**
 * 意图分析器
 * 将自然语言目标分解为结构化能力需求
 */
export class IntentAnalyzer {
  /**
   * 分析用户目标，返回所需能力
   */
  analyze(goal: string, constraints?: BuildConstraints): IntentAnalysis {
    const capabilities = this.extractCapabilities(goal);
    const priority = this.computePriority(capabilities, goal);
    const risk = this.assessRisk(goal, capabilities);
    const enginePref = this.determineEnginePreference(capabilities, constraints);

    return {
      required_capabilities: capabilities,
      capability_priority: priority,
      constraints: {
        max_cost_usd: constraints?.max_cost_usd,
        max_latency_ms: constraints?.max_latency_ms,
        required_engines: constraints?.preferred_engine ? [constraints.preferred_engine] : undefined,
        whitelist_only: constraints?.whitelist_only ?? false,
        streaming_required: constraints?.streaming_required ?? false,
      },
      risk_assessment: risk,
      engine_preference: enginePref,
    };
  }

  /**
   * 从目标描述中提取能力需求
   */
  private extractCapabilities(goal: string): NodeCapability[] {
    const lowerGoal = goal.toLowerCase();
    const detected = new Set<NodeCapability>();

    for (const [capability, keywords] of KEYWORD_CAPABILITY_MAP.entries()) {
      for (const keyword of keywords) {
        if (lowerGoal.includes(keyword.toLowerCase())) {
          detected.add(capability);
          break;
        }
      }
    }

    // 默认至少需要 LLM
    if (detected.size === 0) {
      detected.add(NodeCapability.LLM);
    }

    // 自动补全能力依赖
    const augmented = this.addImplicitDependencies(Array.from(detected));

    return augmented;
  }

  /**
   * 添加隐式依赖
   */
  private addImplicitDependencies(capabilities: NodeCapability[]): NodeCapability[] {
    const result = [...capabilities];

    // Agent 通常需要 LLM
    if (capabilities.includes(NodeCapability.AGENT) && !result.includes(NodeCapability.LLM)) {
      result.push(NodeCapability.LLM);
    }

    // 分类可能需要 RAG
    if (capabilities.includes(NodeCapability.CLASSIFICATION) && !result.includes(NodeCapability.RAG)) {
      // 不强制添加 RAG
    }

    return result;
  }

  /**
   * 计算能力优先级
   */
  private computePriority(capabilities: NodeCapability[], goal: string): Map<NodeCapability, number> {
    const priority = new Map<NodeCapability, number>();
    const lowerGoal = goal.toLowerCase();

    // 首先出现的关键词优先级更高
    let index = 0;
    for (const cap of capabilities) {
      priority.set(cap, 100 - index * 10);
      index++;
    }

    // 特别优先级调整
    if (lowerGoal.includes('首先') || lowerGoal.includes('第一步')) {
      priority.set(capabilities[0] || NodeCapability.LLM, 200);
    }

    return priority;
  }

  /**
   * 风险评估
   */
  private assessRisk(goal: string, capabilities: NodeCapability[]): IntentAnalysis['risk_assessment'] {
    const riskFactors: string[] = [];
    let level: RiskLevel = RiskLevel.LOW;

    const highRiskCaps = [NodeCapability.CODE_EXEC, NodeCapability.DATABASE, NodeCapability.AGENT];
    for (const cap of capabilities) {
      if (highRiskCaps.includes(cap)) {
        riskFactors.push(`${cap} 能力需要监控`);
        level = RiskLevel.MEDIUM;
      }
    }

    if (goal.includes('删除') || goal.includes('销毁')) {
      riskFactors.push('检测到危险操作');
      level = RiskLevel.HIGH;
    }

    return { level, risk_factors: riskFactors };
  }

  /**
   * 确定引擎偏好
   */
  private determineEnginePreference(
    capabilities: NodeCapability[],
    constraints?: BuildConstraints
  ): IntentAnalysis['engine_preference'] {
    // 如果指定了引擎，优先使用
    if (constraints?.preferred_engine) {
      return {
        preferred: [constraints.preferred_engine],
        fallback: [WorkflowEngine.N8N, WorkflowEngine.DIFY],
      };
    }

    // AI 原生能力优先 Dify
    const aiNativeCaps = [NodeCapability.LLM, NodeCapability.RAG, NodeCapability.AGENT, NodeCapability.CLASSIFICATION];
    const hasAIPrimitive = capabilities.some((c) => aiNativeCaps.includes(c));

    // 通用自动化优先 n8n
    const automationCaps = [NodeCapability.HTTP, NodeCapability.DATABASE, NodeCapability.SCHEDULE, NodeCapability.WEBHOOK];
    const hasAutomation = capabilities.some((c) => automationCaps.includes(c));

    if (hasAIPrimitive && !hasAutomation) {
      return {
        preferred: [WorkflowEngine.DIFY],
        fallback: [WorkflowEngine.N8N],
      };
    }

    if (hasAutomation && !hasAIPrimitive) {
      return {
        preferred: [WorkflowEngine.N8N],
        fallback: [WorkflowEngine.DIFY],
      };
    }

    // 混合场景：两者都需要
    return {
      preferred: [WorkflowEngine.DIFY, WorkflowEngine.N8N],
      fallback: [],
    };
  }
}

// ============================================
// DAG 构建器
// ============================================

/**
 * DAG 构建器
 * 将节点编织为带跨引擎边的执行图
 */
export class DAGBuilder {
  /**
   * 构建混合引擎 DAG
   */
  build(
    nodes: NodeMetadata[],
    intent: IntentAnalysis,
    workflowId: string
  ): {
    hybridNodes: HybridNode[];
    edges: [string, string][];
    crossEdges: CrossEngineEdge[];
  } {
    const hybridNodes: HybridNode[] = [];
    const edges: [string, string][] = [];
    const crossEdges: CrossEngineEdge[] = [];

    // 1. 转换为 HybridNode
    for (const meta of nodes) {
      const nodeId = `n_${meta.node_id}`;
      const config = this.metaToConfig(meta);

      hybridNodes.push({
        id: nodeId,
        name: meta.name,
        description: meta.description,
        metadata: meta,
        config,
        execution: {
          timeout_ms: meta.cost_estimate.latency_ms * 3, // 3倍估算延迟作为超时
          retry_count: 0,
          continue_on_error: false,
        },
      });
    }

    // 2. 添加起始节点（用户输入）
    const startNode: HybridNode = {
      id: 'n_start',
      name: '用户输入',
      description: '工作流触发入口',
      metadata: {
        node_id: 'start',
        name: '用户输入',
        description: '工作流触发入口',
        engine: WorkflowEngine.N8N,
        category: NodeCategory.AUTOMATION,
        capabilities: [NodeCapability.WEBHOOK],
        inputs: [{ name: 'goal', type: 'string' }],
        outputs: [{ name: 'goal', type: 'string' }],
        cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
        whitelist_level: WhitelistLevel.WHITE,
        version: '1.0',
        tags: ['开始', '入口'],
      },
      config: {
        engine: WorkflowEngine.N8N,
        node_id: 'start',
        entrypoint: { type: 'webhook' },
        raw_config: {},
      },
      execution: {
        timeout_ms: 1000,
        retry_count: 0,
        continue_on_error: false,
      },
    };
    hybridNodes.unshift(startNode);

    // 3. 构建边连接
    for (let i = 0; i < hybridNodes.length - 1; i++) {
      const from = hybridNodes[i];
      const to = hybridNodes[i + 1];

      // 检查是否跨引擎
      if (from.metadata.engine !== to.metadata.engine) {
        crossEdges.push({
          id: `edge_${from.id}_${to.id}`,
          from_node: from.id,
          from_engine: from.metadata.engine,
          to_node: to.id,
          to_engine: to.metadata.engine,
          data_flow: CrossEngineDataFlow.SYNC,
          transform: {
            type: 'passthrough',
            expression: '',
          },
        });
      } else {
        edges.push([from.id, to.id]);
      }
    }

    return { hybridNodes, edges, crossEdges };
  }

  /**
   * 节点元数据转换为配置
   */
  private metaToConfig(meta: NodeMetadata): UniversalNodeConfig {
    const entrypoint = this.getEntrypoint(meta);

    return {
      engine: meta.engine,
      node_id: meta.node_id,
      entrypoint,
      raw_config: {},
    };
  }

  /**
   * 获取节点入口配置
   */
  private getEntrypoint(meta: NodeMetadata): UniversalNodeConfig['entrypoint'] {
    if (meta.engine === WorkflowEngine.N8N) {
      if (meta.node_id.startsWith('n8n_webhook')) {
        return { type: 'webhook', webhook_path: `/webhook/${meta.node_id}` };
      }
      if (meta.node_id.startsWith('n8n_schedule')) {
        return { type: 'workflow' };
      }
      return { type: 'workflow' };
    }

    if (meta.engine === WorkflowEngine.DIFY) {
      if (meta.node_id.startsWith('dify_chat')) {
        return { type: 'chat' };
      }
      if (meta.node_id.startsWith('dify_agent')) {
        return { type: 'agent' };
      }
      if (meta.capabilities.includes(NodeCapability.RAG)) {
        return { type: 'workflow', dify_workflow_id: meta.node_id };
      }
      return { type: 'workflow', dify_workflow_id: meta.node_id };
    }

    return { type: 'tool' };
  }

  /**
   * 拓扑排序
   */
  topologicalSort(
    nodes: HybridNode[],
    edges: [string, string][],
    crossEdges: CrossEngineEdge[]
  ): string[] {
    const inDegree = new Map<string, number>();
    const adj = new Map<string, string[]>();

    // 初始化
    for (const node of nodes) {
      inDegree.set(node.id, 0);
      adj.set(node.id, []);
    }

    // 计算入度
    for (const [from, to] of edges) {
      inDegree.set(to, (inDegree.get(to) || 0) + 1);
      adj.get(from)?.push(to);
    }

    // 跨引擎边也增加入度
    for (const edge of crossEdges) {
      inDegree.set(edge.to_node, (inDegree.get(edge.to_node) || 0) + 1);
      adj.get(edge.from_node)?.push(edge.to_node);
    }

    // BFS
    const queue = nodes.filter((n) => inDegree.get(n.id) === 0).map((n) => n.id);
    const result: string[] = [];

    while (queue.length > 0) {
      const id = queue.shift()!;
      result.push(id);

      for (const neighbor of adj.get(id) || []) {
        inDegree.set(neighbor, inDegree.get(neighbor)! - 1);
        if (inDegree.get(neighbor) === 0) {
          queue.push(neighbor);
        }
      }
    }

    return result;
  }
}

// ============================================
// 统一构建器
// ============================================

/**
 * 统一工作流构建器
 */
export class UnifiedWorkflowBuilder {
  private intentAnalyzer: IntentAnalyzer;
  private dagBuilder: DAGBuilder;

  constructor() {
    this.intentAnalyzer = new IntentAnalyzer();
    this.dagBuilder = new DAGBuilder();
  }

  /**
   * 构建混合工作流
   */
  async build(request: BuildRequest): Promise<BuildResult> {
    const { goal, context, constraints } = request;

    // 1. 意图分析
    const intent = this.intentAnalyzer.analyze(goal, constraints);

    // 2. 节点匹配
    const matchResult = this.matchNodes(intent, constraints);

    // 3. 构建 DAG
    const { hybridNodes, edges, crossEdges } = this.dagBuilder.build(
      matchResult.selected_nodes,
      intent,
      `wf_${Date.now()}`
    );

    // 4. 拓扑排序获取执行顺序
    const executionOrder = this.dagBuilder.topologicalSort(hybridNodes, edges, crossEdges);

    // 5. 生成执行计划说明
    const executionPlan = this.generateExecutionPlan(hybridNodes, executionOrder);

    // 6. 构建工作流
    const workflow: HybridWorkflow = {
      flow_id: `hybrid_${Date.now()}`,
      version: '1.0',
      created_by: 'unified_builder',
      created_at: new Date().toISOString(),
      name: goal.substring(0, 50),
      description: goal,
      tags: this.extractTags(goal),
      trigger: { type: 'manual', config: {} },
      nodes: hybridNodes,
      edges,
      cross_edges: crossEdges,
      execution_config: {
        max_parallel_nodes: 5,
        enable_checkpoint: true,
        checkpoint_interval_ms: 30000,
        enable_circuit_breaker: true,
        max_cost_usd: constraints?.max_cost_usd,
      },
      estimated_cost_usd: matchResult.cost.estimated_cost_usd,
      risk_assessment: {
        level: intent.risk_assessment.level,
        white_list_compliant: intent.constraints.whitelist_only,
        requires_approval: intent.risk_assessment.level !== RiskLevel.LOW,
        blocked_nodes: [],
      },
    };

    // 7. 统计引擎分布
    const engineBreakdown = {
      n8n: hybridNodes.filter((n) => n.metadata.engine === WorkflowEngine.N8N).length,
      dify: hybridNodes.filter((n) => n.metadata.engine === WorkflowEngine.DIFY).length,
    };

    return {
      workflow,
      engine_breakdown: engineBreakdown,
      cost_estimate: matchResult.cost.estimated_cost_usd,
      execution_plan: executionPlan,
      intent,
    };
  }

  /**
   * 节点匹配
   */
  private matchNodes(intent: IntentAnalysis, constraints?: BuildConstraints): MatchResult {
    const selectedNodes: NodeMetadata[] = [];
    const covered: NodeCapability[] = [];
    let totalTokens = 0;
    let totalApiCalls = 0;
    let totalLatency = 0;

    const whitelistOnly = intent.constraints.whitelist_only;

    // 按优先级依次匹配
    const sortedCaps = Array.from(intent.capability_priority.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([cap]) => cap);

    for (const cap of sortedCaps) {
      // 成本检查
      if (constraints?.max_cost_usd) {
        const estimatedCost = this.estimateCapabilityCost(cap);
        if (totalTokens * 0.00001 + totalApiCalls * 0.01 > constraints.max_cost_usd) {
          continue;
        }
      }

      const node = unifiedNodeRegistry.findBestNode(cap, whitelistOnly);
      if (node && !selectedNodes.find((n) => n.node_id === node.node_id)) {
        selectedNodes.push(node);
        covered.push(cap);
        totalTokens += node.cost_estimate.tokens;
        totalApiCalls += node.cost_estimate.api_calls;
        totalLatency += node.cost_estimate.latency_ms;
      }
    }

    const uncovered = sortedCaps.filter((c) => !covered.includes(c));

    return {
      selected_nodes: selectedNodes,
      coverage: {
        covered,
        uncovered,
        coverage_rate: sortedCaps.length > 0 ? covered.length / sortedCaps.length : 0,
      },
      cost: {
        estimated_tokens: totalTokens,
        estimated_api_calls: totalApiCalls,
        estimated_latency_ms: totalLatency,
        estimated_cost_usd: Math.max(totalTokens * 0.00001 + totalApiCalls * 0.01, 0.001),
      },
      execution_plan: {
        stages: [],
        parallel_groups: [],
        estimated_total_time_ms: totalLatency,
      },
    };
  }

  /**
   * 估算能力成本
   */
  private estimateCapabilityCost(cap: NodeCapability): number {
    const baseCosts: Record<NodeCapability, number> = {
      [NodeCapability.LLM]: 1000,
      [NodeCapability.RAG]: 200,
      [NodeCapability.AGENT]: 3000,
      [NodeCapability.CLASSIFICATION]: 300,
      [NodeCapability.CODE_EXEC]: 0,
      [NodeCapability.HTTP]: 0,
      [NodeCapability.DATABASE]: 0,
      [NodeCapability.SCHEDULE]: 0,
      [NodeCapability.WEBHOOK]: 0,
      [NodeCapability.CONDITION]: 0,
      [NodeCapability.ITERATION]: 500,
      [NodeCapability.TRANSFORM]: 0,
      [NodeCapability.TEMPLATE]: 0,
      [NodeCapability.FILE]: 0,
      [NodeCapability.STREAMING]: 1000,
      [NodeCapability.REASONING]: 2000,
    };
    return baseCosts[cap] || 0;
  }

  /**
   * 生成执行计划说明
   */
  private generateExecutionPlan(nodes: HybridNode[], order: string[]): string[] {
    const plan: string[] = [];
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    for (const nodeId of order) {
      const node = nodeMap.get(nodeId);
      if (!node) continue;

      const engineLabel =
        node.metadata.engine === WorkflowEngine.N8N ? '🔧 n8n' : '🤖 Dify';
      plan.push(
        `${engineLabel} ${node.name} (${node.metadata.description})`
      );
    }

    return plan;
  }

  /**
   * 提取标签
   */
  private extractTags(goal: string): string[] {
    const tags: string[] = [];
    const lowerGoal = goal.toLowerCase();

    const tagKeywords: Record<string, string[]> = {
      搜索: ['搜索', '查找', '调研'],
      分析: ['分析', '对比', '评估'],
      自动化: ['自动', '定时', '调度'],
      AI: ['LLM', '推理', 'Agent', 'GPT'],
      数据: ['数据', '处理', '转换'],
    };

    for (const [tag, keywords] of Object.entries(tagKeywords)) {
      if (keywords.some((k) => lowerGoal.includes(k))) {
        tags.push(tag);
      }
    }

    return tags;
  }
}

// ============================================
// 单例导出
// ============================================

export const unifiedWorkflowBuilder = new UnifiedWorkflowBuilder();
