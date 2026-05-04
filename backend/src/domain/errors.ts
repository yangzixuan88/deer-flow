/**
 * 统一错误类型定义
 * ===============================
 * Phase 23: 技术债务清理 - Action 045
 * ===============================
 *
 * 提供统一的错误分类体系：
 * - PromptEngineError: 提示词引擎相关错误
 * - MemoryError: 记忆系统相关错误
 * - SandboxError: 沙箱执行相关错误
 * - AdapterError: 适配器相关错误
 * - ValidationError: 验证/校验相关错误
 * - ConfigurationError: 配置相关错误
 */

/**
 * 错误严重级别
 */
export enum ErrorSeverity {
  LOW = 'low',      // 可恢复的错误，记录即可
  MEDIUM = 'medium', // 需要关注，但不影响主流程
  HIGH = 'high',    // 重要错误，需要立即处理
  CRITICAL = 'critical', // 系统级错误，必须终止流程
}

/**
 * 错误恢复建议
 */
export enum RecoveryAction {
  RETRY = 'retry',                    // 重试一次
  FALLBACK = 'fallback',              // 使用降级方案
  SKIP = 'skip',                      // 跳过当前项
  ABORT = 'abort',                    // 终止整个流程
  IGNORE = 'ignore',                  // 忽略并继续
}

/**
 * 错误基类
 */
export abstract class AppError extends Error {
  public readonly code: string;
  public readonly severity: ErrorSeverity;
  public readonly recovery: RecoveryAction;
  public readonly context: Record<string, any>;
  public readonly timestamp: string;

  constructor(
    message: string,
    code: string,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    recovery: RecoveryAction = RecoveryAction.IGNORE,
    context: Record<string, any> = {}
  ) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.severity = severity;
    this.recovery = recovery;
    this.context = context;
    this.timestamp = new Date().toISOString();

    // Capture stack trace
    Error.captureStackTrace(this, this.constructor);
  }

  /**
   * 获取错误摘要
   */
  toJSON(): Record<string, any> {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
      severity: this.severity,
      recovery: this.recovery,
      context: this.context,
      timestamp: this.timestamp,
      stack: this.stack,
    };
  }

  /**
   * 获取简短描述（用于日志）
   */
  toShortString(): string {
    return `[${this.code}] ${this.name}: ${this.message}`;
  }
}

/**
 * 提示词引擎错误
 */
export class PromptEngineError extends AppError {
  constructor(
    message: string,
    code: string = 'PROMPT_ENGINE_ERROR',
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    recovery: RecoveryAction = RecoveryAction.FALLBACK,
    context: Record<string, any> = {}
  ) {
    super(message, code, severity, recovery, context);
  }
}

/**
 * 提示词编译错误
 */
export class PromptCompilationError extends PromptEngineError {
  public readonly phase: string;

  constructor(message: string, phase: string, context: Record<string, any> = {}) {
    super(message, 'PROMPT_COMPILATION_ERROR', ErrorSeverity.HIGH, RecoveryAction.ABORT, {
      phase,
      ...context,
    });
    this.phase = phase;
  }
}

/**
 * 提示词验证错误
 */
export class PromptValidationError extends PromptEngineError {
  public readonly validationErrors: string[];

  constructor(message: string, validationErrors: string[], context: Record<string, any> = {}) {
    super(message, 'PROMPT_VALIDATION_ERROR', ErrorSeverity.MEDIUM, RecoveryAction.SKIP, {
      validationErrors,
      ...context,
    });
    this.validationErrors = validationErrors;
  }
}

/**
 * 提示词执行错误
 */
export class PromptExecutionError extends PromptEngineError {
  public readonly executorType: string;

  constructor(message: string, executorType: string, context: Record<string, any> = {}) {
    super(message, 'PROMPT_EXECUTION_ERROR', ErrorSeverity.HIGH, RecoveryAction.RETRY, {
      executorType,
      ...context,
    });
    this.executorType = executorType;
  }
}

/**
 * 记忆系统错误
 */
export class MemoryError extends AppError {
  constructor(
    message: string,
    code: string = 'MEMORY_ERROR',
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    recovery: RecoveryAction = RecoveryAction.FALLBACK,
    context: Record<string, any> = {}
  ) {
    super(message, code, severity, recovery, context);
  }
}

/**
 * 记忆层错误
 */
export class MemoryLayerError extends MemoryError {
  public readonly layer: string;

  constructor(message: string, layer: string, context: Record<string, any> = {}) {
    super(message, 'MEMORY_LAYER_ERROR', ErrorSeverity.MEDIUM, RecoveryAction.FALLBACK, {
      layer,
      ...context,
    });
    this.layer = layer;
  }
}

/**
 * 记忆压缩错误
 */
export class MemoryCompressionError extends MemoryError {
  public readonly originalLength: number;

  constructor(message: string, originalLength: number, context: Record<string, any> = {}) {
    super(message, 'MEMORY_COMPRESSION_ERROR', ErrorSeverity.HIGH, RecoveryAction.SKIP, {
      originalLength,
      ...context,
    });
    this.originalLength = originalLength;
  }
}

/**
 * 记忆写入错误
 */
export class MemoryWriteError extends MemoryError {
  public readonly targetLayer: string;

  constructor(message: string, targetLayer: string, context: Record<string, any> = {}) {
    super(message, 'MEMORY_WRITE_ERROR', ErrorSeverity.HIGH, RecoveryAction.RETRY, {
      targetLayer,
      ...context,
    });
    this.targetLayer = targetLayer;
  }
}

/**
 * 沙箱执行错误
 */
export class SandboxError extends AppError {
  constructor(
    message: string,
    code: string = 'SANDBOX_ERROR',
    severity: ErrorSeverity = ErrorSeverity.HIGH,
    recovery: RecoveryAction = RecoveryAction.FALLBACK,
    context: Record<string, any> = {}
  ) {
    super(message, code, severity, recovery, context);
  }
}

/**
 * 沙箱执行超时
 */
export class SandboxTimeoutError extends SandboxError {
  public readonly timeoutMs: number;

  constructor(message: string, timeoutMs: number, context: Record<string, any> = {}) {
    super(message, 'SANDBOX_TIMEOUT', ErrorSeverity.HIGH, RecoveryAction.RETRY, {
      timeoutMs,
      ...context,
    });
    this.timeoutMs = timeoutMs;
  }
}

/**
 * 沙箱权限拒绝
 */
export class SandboxPermissionError extends SandboxError {
  public readonly requiredPermission: string;

  constructor(message: string, requiredPermission: string, context: Record<string, any> = {}) {
    super(
      message,
      'SANDBOX_PERMISSION_DENIED',
      ErrorSeverity.CRITICAL,
      RecoveryAction.ABORT,
      { requiredPermission, ...context }
    );
    this.requiredPermission = requiredPermission;
  }
}

/**
 * 适配器错误
 */
export class AdapterError extends AppError {
  constructor(
    message: string,
    code: string = 'ADAPTER_ERROR',
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    recovery: RecoveryAction = RecoveryAction.FALLBACK,
    context: Record<string, any> = {}
  ) {
    super(message, code, severity, recovery, context);
  }
}

/**
 * LLM 适配器错误
 */
export class LLMAdapterError extends AdapterError {
  public readonly provider: string;

  constructor(message: string, provider: string, context: Record<string, any> = {}) {
    super(message, 'LLM_ADAPTER_ERROR', ErrorSeverity.HIGH, RecoveryAction.FALLBACK, {
      provider,
      ...context,
    });
    this.provider = provider;
  }
}

/**
 * API 适配器错误
 */
export class APIAdapterError extends AdapterError {
  public readonly endpoint: string;
  public readonly statusCode?: number;

  constructor(message: string, endpoint: string, statusCode?: number, context: Record<string, any> = {}) {
    super(
      message,
      'API_ADAPTER_ERROR',
      ErrorSeverity.MEDIUM,
      statusCode ? RecoveryAction.RETRY : RecoveryAction.FALLBACK,
      { endpoint, statusCode, ...context }
    );
    this.endpoint = endpoint;
    this.statusCode = statusCode;
  }
}

/**
 * 验证错误
 */
export class ValidationError extends AppError {
  public readonly field: string;
  public readonly value: any;

  constructor(message: string, field: string, value: any, context: Record<string, any> = {}) {
    super(message, 'VALIDATION_ERROR', ErrorSeverity.LOW, RecoveryAction.SKIP, {
      field,
      value,
      ...context,
    });
    this.field = field;
    this.value = value;
  }
}

/**
 * 配置错误
 */
export class ConfigurationError extends AppError {
  public readonly configKey: string;

  constructor(message: string, configKey: string, context: Record<string, any> = {}) {
    super(
      message,
      'CONFIGURATION_ERROR',
      ErrorSeverity.CRITICAL,
      RecoveryAction.ABORT,
      { configKey, ...context }
    );
    this.configKey = configKey;
  }
}

/**
 * 执行器错误
 */
export class ExecutorError extends AppError {
  public readonly executorType: string;
  public readonly taskId?: string;

  constructor(
    message: string,
    executorType: string,
    taskId?: string,
    context: Record<string, any> = {}
  ) {
    super(message, 'EXECUTOR_ERROR', ErrorSeverity.HIGH, RecoveryAction.RETRY, {
      executorType,
      taskId,
      ...context,
    });
    this.executorType = executorType;
    this.taskId = taskId;
  }
}

/**
 * 任务执行错误
 */
export class TaskExecutionError extends ExecutorError {
  public readonly instruction: string;

  constructor(message: string, executorType: string, instruction: string, taskId?: string) {
    super(message, executorType, taskId, { instruction });
    this.instruction = instruction;
  }
}

/**
 * 错误工具函数
 */
export const ErrorUtils = {
  /**
   * 判断是否为 AppError
   */
  isAppError(error: unknown): error is AppError {
    return error instanceof AppError;
  },

  /**
   * 判断错误是否可重试
   */
  isRetryable(error: unknown): boolean {
    if (error instanceof AppError) {
      return error.recovery === RecoveryAction.RETRY;
    }
    // 默认网络错误可重试
    if (error instanceof Error) {
      return error.message.includes('ECONNRESET') ||
             error.message.includes('ETIMEDOUT') ||
             error.message.includes('network');
    }
    return false;
  },

  /**
   * 格式化错误为字符串
   */
  format(error: unknown): string {
    if (error instanceof AppError) {
      return error.toShortString();
    }
    if (error instanceof Error) {
      return `[ERROR] ${error.name}: ${error.message}`;
    }
    return String(error);
  },

  /**
   * 安全获取错误消息
   */
  getMessage(error: unknown): string {
    if (error instanceof AppError) {
      return error.message;
    }
    if (error instanceof Error) {
      return error.message;
    }
    return String(error);
  },

  /**
   * 创建错误链
   */
  chain(errors: Array<Error | AppError>): Error {
    const messages = errors.map(e => e.message).join(' -> ');
    return new Error(messages) as Error;
  },
};
