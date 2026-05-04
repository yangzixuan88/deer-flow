/**
 * M04 三系统协同 - 类型定义
 * ================================================
 * 搜索系统 · 任务系统 · 工作流系统
 * 统一调度 · 共享上下文 · 数据流互联
 * ================================================
 */

// ============================================
// 系统枚举
// ============================================

export enum SystemType {
  SEARCH = 'search',
  TASK = 'task',
  WORKFLOW = 'workflow',
  CLAUDE_CODE = 'claude_code',  // Claude Code CLI 执行 (M11 ExecutorAdapter)
  GSTACK_SKILL = 'gstack_skill',  // GStack Skill 路由执行
}

export enum TaskCategory {
  SEARCH = 'search',
  CODE_GEN = 'code_gen',
  RESEARCH = 'research',
  ANALYSIS = 'analysis',
  PLANNING = 'planning',
  CREATIVE = 'creative',
  SYS_CONFIG = 'sys_config',
  DATA_PROCESSING = 'data_processing',
  DECISION = 'decision',
}

// ============================================
// 搜索系统类型
// ============================================

export enum SearchEngine {
  SEARXNG = 'searxng',
  TAVILY = 'tavily',
  EXA = 'exa',
  CONTEXT7 = 'context7',
  GITHUB = 'github',
  JINA = 'jina',
  BUILTIN = 'builtin',
}

export enum SearchRound {
  ROUND_1 = 1,
  ROUND_2 = 2,
  ROUND_3 = 3,
}

export interface SearchSource {
  title: string;
  url: string;
  content: string;
  confidence: number;
}

export interface SearchResult {
  query: string;
  round: SearchRound;
  sources: SearchSource[];
  summary: string;
  confidence: number;
}

export interface SearchResponse {
  results: SearchResult[];
  summary: string;
  missing_info: string[];
  search_rounds_used: number;
  engines_used: SearchEngine[];
  cross_validation: {
    sources_count: number;
    conflicts: string[];
    confidence: number;
  };
}

export interface SearchStrategy {
  round: SearchRound;
  strategy: string;
  query: string;
  engines: SearchEngine[];
}

// ============================================
// 任务系统类型
// ============================================

export enum TaskStatus {
  PENDING = 'pending',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum NodeStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  SKIPPED = 'skipped',
}

export interface TaskNode {
  id: string;
  name: string;
  category: TaskCategory;
  status: NodeStatus;
  depends_on: string[];
  timeout_min: number;
  result_summary?: string;
  tokens_used?: number;
  error?: string;
  retry_count: number;
}

export interface TaskDAG {
  nodes: TaskNode[];
  edges: [string, string][];
}

export interface Task {
  task_id: string;
  goal: string;
  status: TaskStatus;
  created_at: string;
  dag: TaskDAG;
  total_tokens: number;
  checkpoints: string[];
  current_node_id?: string;
  result?: string;
}

export interface TaskResult {
  task_id: string;
  status: TaskStatus;
  result?: string;
  experience_id?: string;
  tokens_used: number;
  execution_time_ms: number;
  nodes_executed: number;
}

// ============================================
// 工作流系统类型
// ============================================

export enum NodeType {
  TRIGGER = 'trigger',
  TOOL = 'tool',
  CLI = 'cli',
  MCP = 'mcp',
  LLM = 'llm',
  CONTROL = 'control',
  SOP = 'sop',
}

export enum RiskLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical',
}

export interface WorkflowNode {
  id: string;
  type: NodeType;
  config: Record<string, any>;
  children?: string[];
  wait_confirm?: boolean;
}

export interface Workflow {
  flow_id: string;
  created_by: string;
  created_at: string;
  trigger: { type: string; pattern?: string };
  nodes: WorkflowNode[];
  edges: [string, string][];
  estimated_cost_usd: number;
  risk_level: RiskLevel;
  sop_source?: string;
}

export interface WorkflowExecution {
  execution_id: string;
  flow_id: string;
  status: TaskStatus;
  started_at: string;
  completed_at?: string;
  current_node?: string;
  result?: any;
  error?: string;
}

// ============================================
// 协调器类型
// ============================================

export interface CoordinatorConfig {
  enable_search: boolean;
  enable_task: boolean;
  enable_workflow: boolean;
  max_parallel_tasks: number;
  default_timeout_min: number;
  enable_checkpoint: boolean;
}

export interface ExecutionContext {
  request_id: string;
  user_id?: string;
  session_id: string;
  system_type: SystemType;
  priority: 'high' | 'normal' | 'low';
  metadata: Record<string, any>;
}

export interface CoordinatorResult {
  success: boolean;
  system_type: SystemType;
  result?: any;
  error?: string;
  execution_time_ms: number;
  context: ExecutionContext;
}

// ============================================
// 共享上下文类型
// ============================================

export interface SharedContextData {
  key: string;
  value: any;
  ttl_ms: number;
  created_at: string;
  access_count: number;
}

export interface CrossSystemData {
  search_results?: SearchResponse;
  task_result?: TaskResult;
  workflow_result?: WorkflowExecution;
  shared_state: Record<string, SharedContextData>;
}

export const DEFAULT_COORDINATOR_CONFIG: CoordinatorConfig = {
  enable_search: true,
  enable_task: true,
  enable_workflow: true,
  max_parallel_tasks: 3,
  default_timeout_min: 10,
  enable_checkpoint: true,
};

// ============================================
// 统一工作流引擎类型（新增）
// ============================================

import {
  WorkflowEngine,
  NodeCapability,
  NodeCategory,
  WhitelistLevel,
  CrossEngineDataFlow,
  BridgeType,
  NodeExecutionStatus,
  CircuitBreakerState,
} from './engine_enum';

// Re-export engine enums
export {
  WorkflowEngine,
  NodeCapability,
  NodeCategory,
  WhitelistLevel,
  CrossEngineDataFlow,
  BridgeType,
  NodeExecutionStatus,
  CircuitBreakerState,
};

/** 统一节点配置（核心抽象） */
export interface UniversalNodeConfig {
  // 引擎路由
  engine: WorkflowEngine;
  node_id: string;

  // 入口定义
  entrypoint: {
    type: 'webhook' | 'workflow' | 'agent' | 'tool' | 'chat' | 'completion';

    // n8n 场景
    webhook_path?: string;
    workflow_id?: string;

    // Dify 场景
    dify_app_id?: string;
    dify_workflow_id?: string;

    // 通用
    raw_endpoint?: string;
  };

  // 数据映射
  input_mapping?: Record<string, string>;    // { "prompt": "{{n_search.output}}", "model": "claude" }
  output_mapping?: Record<string, string>;   // { "answer": "outputs.text" }

  // 引擎原生配置（透传）
  raw_config: {
    // n8n 原生
    n8n_node_type?: string;
    n8n_credentials?: Record<string, string>;
    n8n_parameters?: Record<string, any>;

    // Dify 原生
    dify_inputs?: Record<string, any>;
    dify_model_config?: {
      model?: string;
      temperature?: number;
      max_tokens?: number;
    };
    dify_retrieval_config?: {
      dataset_id: string;
      top_k?: number;
      score_threshold?: number;
    };

    // 通用
    timeout_ms?: number;
    retry_policy?: {
      max_attempts: number;
      backoff_ms: number;
    };
  };

  // 熔断与降级
  fallback?: {
    enabled: boolean;
    strategy: 'mock' | 'skip' | 'alternative_node';
    alternative_node_id?: string;
  };
}

/** 节点元数据（注册表用） */
export interface NodeMetadata {
  node_id: string;
  name: string;
  description: string;
  engine: WorkflowEngine;
  category: NodeCategory;
  capabilities: NodeCapability[];
  inputs: { name: string; type: string; optional?: boolean }[];
  outputs: { name: string; type: string }[];
  cost_estimate: {
    tokens: number;
    api_calls: number;
    latency_ms: number;
  };
  whitelist_level: WhitelistLevel;
  skill_file?: string;
  version: string;
  tags: string[];
}

/** 跨引擎边 */
export interface CrossEngineEdge {
  id: string;
  from_node: string;
  from_engine: WorkflowEngine;
  to_node: string;
  to_engine: WorkflowEngine;
  data_flow: CrossEngineDataFlow;

  // 数据转换
  transform?: {
    type: 'passthrough' | 'json_path' | 'jinja2' | 'custom_js';
    expression: string;
  };

  // 桥接类型（自动选择或手动指定）
  bridge_type?: BridgeType;
}

/** 混合引擎工作流 */
export interface HybridWorkflow {
  flow_id: string;
  version: string;
  created_by: string;
  created_at: string;

  // 元信息
  name: string;
  description: string;
  tags: string[];

  // 触发器
  trigger: {
    type: 'manual' | 'webhook' | 'schedule' | 'event' | 'mcp';
    config: Record<string, any>;
  };

  // 节点定义
  nodes: HybridNode[];

  // 边定义（支持跨引擎）
  edges: [string, string][];
  cross_edges: CrossEngineEdge[];

  // 执行配置
  execution_config: {
    max_parallel_nodes: number;
    enable_checkpoint: boolean;
    checkpoint_interval_ms: number;
    enable_circuit_breaker: boolean;
    max_cost_usd?: number;
  };

  // 成本估算
  estimated_cost_usd: number;

  // 风险评估
  risk_assessment: {
    level: RiskLevel;
    white_list_compliant: boolean;
    requires_approval: boolean;
    blocked_nodes: string[];
  };
}

/** 混合节点 */
export interface HybridNode {
  id: string;
  name: string;
  description?: string;
  metadata: NodeMetadata;
  config: UniversalNodeConfig;

  // 执行控制
  execution: {
    timeout_ms: number;
    retry_count: number;
    continue_on_error: boolean;
  };

  // 状态（运行时）
  status?: NodeExecutionStatus;
  last_result?: any;
  error?: string;
}

/** 执行轨迹 */
export interface ExecutionTrace {
  execution_id: string;
  flow_id: string;
  started_at: string;
  completed_at?: string;
  status: TaskStatus;

  // 节点执行轨迹
  node_executions: {
    node_id: string;
    engine: WorkflowEngine;
    status: NodeExecutionStatus;
    started_at: string;
    completed_at?: string;
    input: any;
    output: any;
    error?: string;
    latency_ms: number;
    cost_usd: number;
  }[];

  // 聚合指标
  metrics: {
    total_tokens: number;
    total_api_calls: number;
    total_cost_usd: number;
    total_latency_ms: number;
    engine_breakdown: Record<WorkflowEngine, { nodes: number; cost_usd: number }>;
  };
}

/** 意图分析结果 */
export interface IntentAnalysis {
  required_capabilities: NodeCapability[];
  capability_priority: Map<NodeCapability, number>;
  constraints: {
    max_cost_usd?: number;
    max_latency_ms?: number;
    required_engines?: WorkflowEngine[];
    whitelist_only: boolean;
    streaming_required: boolean;
  };
  risk_assessment: {
    level: RiskLevel;
    risk_factors: string[];
  };
  engine_preference: {
    preferred: WorkflowEngine[];
    fallback: WorkflowEngine[];
  };
}

/** 匹配结果 */
export interface MatchResult {
  selected_nodes: NodeMetadata[];
  coverage: {
    covered: NodeCapability[];
    uncovered: NodeCapability[];
    coverage_rate: number;
  };
  cost: {
    estimated_tokens: number;
    estimated_api_calls: number;
    estimated_latency_ms: number;
    estimated_cost_usd: number;
  };
  execution_plan: {
    stages: {
      stage_id: string;
      nodes: string[];
      can_parallel: boolean;
      depends_on: string[];
      estimated_time_ms: number;
    }[];
    parallel_groups: string[][];
    estimated_total_time_ms: number;
  };
}

/** 节点执行结果 */
export interface NodeExecutionResult {
  node_id: string;
  status: NodeExecutionStatus;
  output: any;
  error?: string;
  latency_ms: number;
  cost_usd: number;
  tokens_used?: number;
}
