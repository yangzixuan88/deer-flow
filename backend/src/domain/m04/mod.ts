/**
 * M04 三系统协同 - 模块导出
 * ================================================
 * 搜索系统 · 任务系统 · 工作流系统
 * 统一调度 · 共享上下文 · 数据流互联
 * ================================================
 */

// 类型导出
export * from './types';

// 核心组件
export { SharedContext, CrossSystemAggregator, sharedContext, crossSystemAggregator } from './shared_context';
export { Coordinator, coordinator } from './coordinator';

// 适配器
export { SearchAdapter, searchAdapter } from './adapters/search_adapter';
export { TaskAdapter, taskAdapter } from './adapters/task_adapter';
export { WorkflowAdapter, workflowAdapter } from './adapters/workflow_adapter';

// ============================================
// 统一工作流引擎（n8n + Dify 融合）
// ============================================

// 引擎枚举
export {
  WorkflowEngine,
  NodeCapability,
  NodeCategory,
  WhitelistLevel,
  CrossEngineDataFlow,
  BridgeType,
  NodeExecutionStatus,
  CircuitBreakerState,
} from './engine_enum';

// 统一构建器
export {
  IntentAnalyzer,
  DAGBuilder,
  UnifiedWorkflowBuilder,
  unifiedWorkflowBuilder,
  BuildRequest,
  BuildConstraints,
  BuildResult,
} from './unified_builder';

// 统一执行器
export {
  UnifiedExecutor,
  createUnifiedExecutor,
  getUnifiedExecutor,
  ExecutorConfig,
} from './unified_executor';

// 跨引擎数据转换器
export {
  CrossEngineDataTransformer,
  crossEngineTransformer,
  TransformResult,
} from './transformer';

// 跨引擎桥接管理器
export {
  BridgeManager,
  createBridgeManager,
  getBridgeManager,
  BridgeConfig,
  BridgeResult,
} from '../../infrastructure/workflow/bridge_manager';

// Dify 适配器
export {
  DifyAdapter,
  createDifyAdapter,
  getDifyAdapter,
  DifyAdapterConfig,
  DifyApp,
  DifyExecutionResult,
} from './dify_adapter';
