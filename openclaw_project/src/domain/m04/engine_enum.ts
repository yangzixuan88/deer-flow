/**
 * M04 工作流引擎枚举定义
 * ================================================
 * 引擎类型 · 节点能力 · 节点分类
 * ================================================
 */

/** 工作流引擎类型 */
export enum WorkflowEngine {
  N8N = 'n8n',           // n8n 通用自动化引擎
  DIFY = 'dify',          // Dify AI 原生引擎
  DEERFLOW = 'deerflow',  // DeerFlow LangGraph 引擎
  MOCK = 'mock',          // 模拟/测试引擎
}

/** 节点能力标签（可组合） */
export enum NodeCapability {
  // AI 能力
  LLM = 'llm',                     // 大语言模型推理
  RAG = 'rag',                      // 知识检索/RAG
  AGENT = 'agent',                  // 自主 Agent 循环
  CLASSIFICATION = 'classification', // 意图分类
  CODE_EXEC = 'code_exec',          // 代码执行
  REASONING = 'reasoning',          // 推理能力

  // 集成能力
  WEBHOOK = 'webhook',             // Webhook 触发/调用
  HTTP = 'http',                    // HTTP 请求
  DATABASE = 'database',            // 数据库操作
  SCHEDULE = 'schedule',           // 定时调度

  // 逻辑能力
  CONDITION = 'condition',          // 条件分支
  ITERATION = 'iteration',          // 循环迭代
  TRANSFORM = 'transform',          // 数据转换
  TEMPLATE = 'template',            // 模板渲染

  // 输入输出
  STREAMING = 'streaming',         // 流式输出
  FILE = 'file',                   // 文件处理
}

/** 节点分类 */
export enum NodeCategory {
  AI = 'ai',                  // AI 能力节点
  AUTOMATION = 'automation',  // 自动化节点
  INTEGRATION = 'integration', // 集成节点
  LOGIC = 'logic',            // 逻辑控制节点
  DATA = 'data',              // 数据处理节点
}

/** 节点白名单等级 */
export enum WhitelistLevel {
  WHITE = 'white',  // 白名单：允许使用
  GRAY = 'gray',    // 灰名单：受限使用
  BLACK = 'black',  // 黑名单：禁止使用
}

/** 跨引擎数据流类型 */
export enum CrossEngineDataFlow {
  SYNC = 'sync',       // 同步：等待结果返回
  ASYNC = 'async',     // 异步：触发后继续，通过回调/轮询获取结果
  STREAMING = 'streaming', // 流式：SSE/流式传输
}

/** 跨引擎桥接类型 */
export enum BridgeType {
  HTTP_POLL = 'http_poll',         // HTTP 轮询桥
  WEBHOOK_TRIGGER = 'webhook_trigger', // Webhook 触发桥
  SHARED_STORAGE = 'shared_storage',   // 共享存储桥（Redis/文件）
  STREAMING_BUFFER = 'streaming_buffer', // 流式缓冲桥
  MEMORY = 'memory',               // 内存直接传递
}

/** 节点执行状态 */
export enum NodeExecutionStatus {
  PENDING = 'pending',
  QUEUED = 'queued',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  SKIPPED = 'skipped',
  TIMEOUT = 'timeout',
}

/** 熔断器状态 */
export enum CircuitBreakerState {
  CLOSED = 'closed',     // 正常：允许执行
  OPEN = 'open',         // 断开：拒绝执行
  HALF_OPEN = 'half_open', // 半开：尝试恢复
}
