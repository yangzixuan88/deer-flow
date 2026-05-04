/**
 * M01 编排引擎类型定义
 * ================================================
 * 意图路由、DAG规划、编排请求类型
 * ================================================
 */

import { SystemType } from '../m04/types';

// ============================================
// 意图路由
// ============================================

/**
 * 三条路由路径
 */
export enum IntentRoute {
  /** 路径A: 直接回答 */
  DIRECT_ANSWER = 'direct',
  /** 路径B: 追问补全 */
  CLARIFICATION = 'clarify',
  /** 路径C: DeerFlow编排 */
  ORCHESTRATION = 'orchestrate',
}

/**
 * 意图复杂度评估
 */
export interface ComplexityAssessment {
  /** 复杂度评分 1-10 */
  score: number;
  /** 估计耗时(秒) */
  estimatedDuration: number;
  /** 是否需要搜索 */
  needsSearch: boolean;
  /** 是否需要工具 */
  needsTools: boolean;
  /** 是否需要文件操作 */
  needsFileOps: boolean;
  /** 风险等级 */
  riskLevel: 'low' | 'medium' | 'high';
}

/**
 * 意图分类结果
 */
export interface IntentClassification {
  /** 路由路径 */
  route: IntentRoute;
  /** 复杂度评估 */
  complexity: ComplexityAssessment;
  /** 置信度 0-1 */
  confidence: number;
  /** 推荐系统类型 */
  suggestedSystem?: SystemType;
  /** 分类理由 */
  reasoning: string;
}

// ============================================
// DAG 规划
// ============================================

/**
 * DAG 节点状态
 */
export enum DAGNodeStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  SKIPPED = 'skipped',
}

/**
 * DAG 节点
 */
export interface DAGNode {
  /** 节点ID */
  id: string;
  /** 任务描述 */
  task: string;
  /** 系统类型 */
  systemType: SystemType;
  /** 依赖节点ID列表 */
  dependencies: string[];
  /** 超时时间(ms) */
  timeout: number;
  /** 预期输出描述 */
  expectedOutput: string;
  /** 优先级 */
  priority: 'low' | 'normal' | 'high';
  /** 状态 */
  status: DAGNodeStatus;
  /** 实际执行结果 */
  result?: any;
  /** 执行错误 */
  error?: string;
}

/**
 * DAG 执行计划
 */
export interface DAGPlan {
  /** 计划ID */
  id: string;
  /** 根任务 */
  rootTask: string;
  /** DAG 节点列表 */
  nodes: DAGNode[];
  /** 拓扑排序后的执行顺序 */
  executionOrder: string[];
  /** 预估总耗时(ms) */
  estimatedDuration: number;
  /** 创建时间 */
  createdAt: string;
}

// ============================================
// 编排请求与结果
// ============================================

/**
 * 编排请求
 */
export interface OrchestrationRequest {
  /** 请求ID */
  requestId: string;
  /** 会话ID */
  sessionId: string;
  /** 用户原始输入 */
  userInput: string;
  /** 意图画像(M10输出) */
  intentProfile?: {
    goal: string;
    task_category?: string;
    quality_bar?: string;
    dimensions?: Record<string, number>;
  };
  /** 共享上下文 */
  sharedContext?: Record<string, any>;
  /** 优先级 */
  priority: 'low' | 'normal' | 'high';
  /** 元数据 */
  metadata?: Record<string, any>;
}

/**
 * 编排执行结果
 */
export interface OrchestrationResult {
  /** 请求ID */
  requestId: string;
  /** 是否成功 */
  success: boolean;
  /** 路由路径 */
  route: IntentRoute;
  /** 直接回答内容(路径A) */
  directAnswer?: string;
  /** 澄清问题(路径B) */
  clarification?: {
    question: string;
    dimension: string;
  };
  /** 执行结果(路径C) */
  execution?: {
    dagPlan: DAGPlan;
    completedNodes: number;
    totalNodes: number;
    duration: number;
  };
  /** 错误信息 */
  error?: string;
  /** 执行耗时(ms) */
  executionTime: number;
}

// ============================================
// 路由决策配置
// ============================================

/**
 * 路由决策配置
 */
export const ROUTING_CONFIG = {
  /** 直接回答字数上限 */
  DIRECT_ANSWER_MAX_CHARS: 30,
  /** 直接回答最大耗时(秒) */
  DIRECT_ANSWER_MAX_DURATION: 3,
  /** 编排模式最小复杂度 */
  ORCHESTRATION_MIN_COMPLEXITY: 5,
  /** 追问触发阈值(维度缺失) */
  CLARIFICATION_DIMENSION_THRESHOLD: 0.4,
};

// ============================================
// 模块配置
// ============================================

/**
 * M01 模块配置
 */
export interface M01Config {
  /** 是否启用DeerFlow */
  deerflowEnabled: boolean;
  /** DeerFlow服务地址 */
  deerflowHost: string;
  /** DeerFlow端口 */
  deerflowPort: number;
  /** 默认超时(ms) */
  defaultTimeout: number;
  /** 最大DAG节点数 */
  maxDAGNodes: number;
}

/**
 * 默认配置
 */
export const DEFAULT_M01_CONFIG: M01Config = {
  deerflowEnabled: true,
  deerflowHost: 'localhost',
  deerflowPort: 2024,
  defaultTimeout: 300000, // 5分钟
  maxDAGNodes: 50,
};
