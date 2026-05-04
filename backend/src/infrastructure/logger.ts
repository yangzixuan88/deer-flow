/**
 * 统一日志框架
 * ===============================
 * Phase 23: 技术债务清理 - Action 046
 * ===============================
 *
 * 提供结构化日志系统：
 * - 日志级别: TRACE < DEBUG < INFO < WARN < ERROR < FATAL
 * - 标签体系: 按模块/组件分类
 * - 上下文注入: correlation ID、user ID 等
 * - 多输出目标: console、file、custom transport
 * - 性能优化: 异步写入、缓冲批处理
 */

/**
 * 日志级别
 */
export enum LogLevel {
  TRACE = 0,
  DEBUG = 1,
  INFO = 2,
  WARN = 3,
  ERROR = 4,
  FATAL = 5,
  OFF = 6,
}

/**
 * 日志级别名称
 */
const LOG_LEVEL_NAMES: Record<LogLevel, string> = {
  [LogLevel.TRACE]: 'TRACE',
  [LogLevel.DEBUG]: 'DEBUG',
  [LogLevel.INFO]: 'INFO',
  [LogLevel.WARN]: 'WARN',
  [LogLevel.ERROR]: 'ERROR',
  [LogLevel.FATAL]: 'FATAL',
  [LogLevel.OFF]: 'OFF',
};

/**
 * 日志输出目标
 */
export enum LogTransport {
  CONSOLE = 'console',
  FILE = 'file',
  CUSTOM = 'custom',
}

/**
 * 日志条目
 */
export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  levelName: string;
  message: string;
  tags: string[];
  context: Record<string, any>;
  correlationId?: string;
  error?: {
    name: string;
    message: string;
    stack?: string;
  };
}

/**
 * 日志传输器接口
 */
export interface LogTransportInterface {
  write(entry: LogEntry): void;
  flush?(): Promise<void>;
  close?(): void;
}

/**
 * 控制台传输器
 */
class ConsoleTransport implements LogTransportInterface {
  private minLevel: LogLevel;
  private colorful: boolean;

  constructor(minLevel: LogLevel = LogLevel.INFO, colorful: boolean = true) {
    this.minLevel = minLevel;
    this.colorful = colorful;
  }

  write(entry: LogEntry): void {
    if (entry.level < this.minLevel) return;

    const prefix = this.colorful ? this.getColorPrefix(entry.level) : '';
    const suffix = this.colorful ? '\x1b[0m' : '';
    const tagStr = entry.tags.length > 0 ? `[${entry.tags.join('][')}]` : '';
    const contextStr = this.formatContext(entry.context);
    const corrIdStr = entry.correlationId ? `[${entry.correlationId}]` : '';

    const formatted = `${prefix}${entry.timestamp} ${entry.levelName} ${corrIdStr}${tagStr} ${entry.message}${contextStr}${suffix}`;

    switch (entry.level) {
      case LogLevel.ERROR:
      case LogLevel.FATAL:
        console.error(formatted);
        if (entry.error) {
          console.error(`  ${entry.error.name}: ${entry.error.message}`);
          if (entry.error.stack) {
            console.error(entry.error.stack.split('\n').slice(0, 3).join('\n'));
          }
        }
        break;
      case LogLevel.WARN:
        console.warn(formatted);
        break;
      default:
        console.log(formatted);
    }
  }

  private getColorPrefix(level: LogLevel): string {
    switch (level) {
      case LogLevel.TRACE:
      case LogLevel.DEBUG:
        return '\x1b[90m'; // 灰色
      case LogLevel.INFO:
        return '\x1b[36m'; // 青色
      case LogLevel.WARN:
        return '\x1b[33m'; // 黄色
      case LogLevel.ERROR:
        return '\x1b[31m'; // 红色
      case LogLevel.FATAL:
        return '\x1b[35m'; // 紫色
      default:
        return '\x1b[0m';
    }
  }

  private formatContext(context: Record<string, any>): string {
    const keys = Object.keys(context);
    if (keys.length === 0) return '';

    const parts: string[] = [];
    for (const key of keys) {
      const value = context[key];
      if (value !== undefined && value !== null) {
        if (typeof value === 'object') {
          parts.push(`${key}=${JSON.stringify(value)}`);
        } else {
          parts.push(`${key}=${value}`);
        }
      }
    }
    return parts.length > 0 ? ` ${parts.join(' ')}` : '';
  }
}

/**
 * 文件传输器
 */
class FileTransport implements LogTransportInterface {
  private filepath: string;
  private buffer: string[];
  private flushInterval: number;
  private maxBufferSize: number;
  private timer?: NodeJS.Timeout;

  constructor(filepath: string, flushInterval: number = 5000, maxBufferSize: number = 100) {
    this.filepath = filepath;
    this.buffer = [];
    this.flushInterval = flushInterval;
    this.maxBufferSize = maxBufferSize;
  }

  async init(): Promise<void> {
    this.timer = setInterval(() => this.flush(), this.flushInterval);
  }

  write(entry: LogEntry): void {
    const line = JSON.stringify(entry) + '\n';
    this.buffer.push(line);

    if (this.buffer.length >= this.maxBufferSize) {
      this.flush();
    }
  }

  async flush(): Promise<void> {
    if (this.buffer.length === 0) return;

    const fs = await import('fs');
    const content = this.buffer.join('');
    this.buffer = [];

    await fs.promises.appendFile(this.filepath, content, 'utf8');
  }

  close(): void {
    if (this.timer) {
      clearInterval(this.timer);
    }
  }
}

/**
 * Logger 配置
 */
export interface LoggerConfig {
  /** 最小日志级别 */
  minLevel?: LogLevel;
  /** 默认标签 */
  defaultTags?: string[];
  /** 是否启用颜色 */
  colorful?: boolean;
  /** 是否启用时间戳 */
  timestamp?: boolean;
  /** 日志文件路径（可选） */
  logFile?: string;
  /** 自定义传输器 */
  transports?: LogTransportInterface[];
}

/**
 * Logger 类
 */
export class Logger {
  private transports: LogTransportInterface[];
  private defaultTags: string[];
  private minLevel: LogLevel;
  private colorful: boolean;
  private showTimestamp: boolean;
  private correlationId?: string;
  private globalContext: Record<string, any>;

  constructor(config: LoggerConfig = {}) {
    this.minLevel = config.minLevel ?? LogLevel.INFO;
    this.defaultTags = config.defaultTags ?? [];
    this.colorful = config.colorful ?? true;
    this.showTimestamp = config.timestamp ?? true;
    this.globalContext = {};
    this.transports = [];

    // 添加控制台传输器
    this.transports.push(new ConsoleTransport(this.minLevel, this.colorful));

    // 添加文件传输器（如果配置了）
    if (config.logFile) {
      const fileTransport = new FileTransport(config.logFile);
      fileTransport.init().catch(console.error);
      this.transports.push(fileTransport);
    }

    // 添加自定义传输器
    if (config.transports) {
      this.transports.push(...config.transports);
    }
  }

  /**
   * 设置全局上下文（所有日志都会携带）
   */
  setGlobalContext(context: Record<string, any>): void {
    this.globalContext = { ...this.globalContext, ...context };
  }

  /**
   * 设置 correlation ID
   */
  setCorrelationId(id: string): void {
    this.correlationId = id;
  }

  /**
   * 清除 correlation ID
   */
  clearCorrelationId(): void {
    this.correlationId = undefined;
  }

  /**
   * 创建子 logger（带额外标签）
   */
  child(tags: string[]): Logger {
    const childLogger = new Logger({
      minLevel: this.minLevel,
      defaultTags: [...this.defaultTags, ...tags],
      colorful: this.colorful,
      timestamp: this.showTimestamp,
    });
    childLogger.globalContext = { ...this.globalContext };
    childLogger.correlationId = this.correlationId;
    childLogger.transports = this.transports;
    return childLogger;
  }

  /**
   * 记录 TRACE 级别日志
   */
  trace(message: string, context?: Record<string, any>): void {
    this.log(LogLevel.TRACE, message, [], context);
  }

  /**
   * 记录 DEBUG 级别日志
   */
  debug(message: string, context?: Record<string, any>): void {
    this.log(LogLevel.DEBUG, message, [], context);
  }

  /**
   * 记录 INFO 级别日志
   */
  info(message: string, context?: Record<string, any>): void {
    this.log(LogLevel.INFO, message, [], context);
  }

  /**
   * 记录 WARN 级别日志
   */
  warn(message: string, context?: Record<string, any>): void {
    this.log(LogLevel.WARN, message, [], context);
  }

  /**
   * 记录 ERROR 级别日志
   */
  error(message: string, error?: Error, context?: Record<string, any>): void {
    const errorInfo = error ? {
      name: error.name,
      message: error.message,
      stack: error.stack,
    } : undefined;
    this.log(LogLevel.ERROR, message, [], context, errorInfo);
  }

  /**
   * 记录 FATAL 级别日志
   */
  fatal(message: string, error?: Error, context?: Record<string, any>): void {
    const errorInfo = error ? {
      name: error.name,
      message: error.message,
      stack: error.stack,
    } : undefined;
    this.log(LogLevel.FATAL, message, [], context, errorInfo);
  }

  /**
   * 通用日志方法
   */
  private log(
    level: LogLevel,
    message: string,
    tags: string[],
    context?: Record<string, any>,
    error?: { name: string; message: string; stack?: string }
  ): void {
    if (level < this.minLevel) return;

    const mergedContext = { ...this.globalContext, ...context };
    const mergedTags = [...this.defaultTags, ...tags];

    const entry: LogEntry = {
      timestamp: this.showTimestamp ? new Date().toISOString() : '',
      level,
      levelName: LOG_LEVEL_NAMES[level],
      message,
      tags: mergedTags,
      context: mergedContext,
      correlationId: this.correlationId,
      error,
    };

    for (const transport of this.transports) {
      try {
        transport.write(entry);
      } catch (err) {
        // 避免日志系统本身的错误导致程序崩溃
        console.error('Logger transport error:', err);
      }
    }
  }

  /**
   * 分组日志开始
   */
  group(label: string): void {
    console.group(`[GROUP] ${label}`);
  }

  /**
   * 分组日志结束
   */
  groupEnd(): void {
    console.groupEnd();
  }

  /**
   * 表格日志
   */
  table(data: any): void {
    console.table(data);
  }

  /**
   * 刷新所有传输器
   */
  async flush(): Promise<void> {
    for (const transport of this.transports) {
      if (transport.flush) {
        await transport.flush();
      }
    }
  }

  /**
   * 关闭所有传输器
   */
  close(): void {
    for (const transport of this.transports) {
      if (transport.close) {
        transport.close();
      }
    }
  }
}

/**
 * 全局日志器实例
 */
let globalLogger: Logger | null = null;

/**
 * 初始化全局日志器
 */
export function initLogger(config?: LoggerConfig): Logger {
  globalLogger = new Logger(config);
  return globalLogger;
}

/**
 * 获取全局日志器
 */
export function getLogger(): Logger {
  if (!globalLogger) {
    globalLogger = new Logger();
  }
  return globalLogger;
}

/**
 * 创建模块日志器
 */
export function createLogger(moduleName: string, config?: LoggerConfig): Logger {
  return getLogger().child([moduleName]);
}

/**
 * 常用日志级别常量
 */
export const LogLevels = {
  TRACE: LogLevel.TRACE,
  DEBUG: LogLevel.DEBUG,
  INFO: LogLevel.INFO,
  WARN: LogLevel.WARN,
  ERROR: LogLevel.ERROR,
  FATAL: LogLevel.FATAL,
};
