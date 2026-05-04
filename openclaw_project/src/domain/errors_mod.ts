/**
 * 统一错误类型导出
 * Phase 23: Action 045
 */

// 错误级别和恢复动作枚举
export {
  ErrorSeverity,
  RecoveryAction,
} from './errors';

// 错误基类
export {
  AppError,
} from './errors';

// 提示词引擎错误
export {
  PromptEngineError,
  PromptCompilationError,
  PromptValidationError,
  PromptExecutionError,
} from './errors';

// 记忆系统错误
export {
  MemoryError,
  MemoryLayerError,
  MemoryCompressionError,
  MemoryWriteError,
} from './errors';

// 沙箱错误
export {
  SandboxError,
  SandboxTimeoutError,
  SandboxPermissionError,
} from './errors';

// 适配器错误
export {
  AdapterError,
  LLMAdapterError,
  APIAdapterError,
} from './errors';

// 验证和配置错误
export {
  ValidationError,
  ConfigurationError,
} from './errors';

// 执行器错误
export {
  ExecutorError,
  TaskExecutionError,
} from './errors';

// 错误工具函数
export {
  ErrorUtils,
} from './errors';
