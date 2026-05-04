/**
 * 统一节点注册表
 * ================================================
 * 融合 n8n (35个) + Dify (20个) 节点
 * 对智能体暴露单一抽象，按能力搜索
 * ================================================
 */

import {
  WorkflowEngine,
  NodeCapability,
  NodeCategory,
  WhitelistLevel,
} from './engine_enum';

import { NodeMetadata } from './types';

// ============================================
// n8n 节点注册 (35个)
// ============================================

const n8nNodeRegistry: NodeMetadata[] = [
  // ========== 触发器 ==========
  {
    node_id: 'n8n_webhook',
    name: 'Webhook 触发器',
    description: '接收外部 HTTP 请求触发工作流',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.AUTOMATION,
    capabilities: [NodeCapability.WEBHOOK, NodeCapability.STREAMING],
    inputs: [
      { name: 'body', type: 'object' },
      { name: 'headers', type: 'object' },
      { name: 'query', type: 'object', optional: true },
    ],
    outputs: [
      { name: 'response', type: 'object' },
      { name: 'status_code', type: 'number' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['触发', 'HTTP', '入口', 'Webhook'],
  },
  {
    node_id: 'n8n_schedule',
    name: '定时触发器',
    description: 'Cron 表达式定时触发工作流',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.AUTOMATION,
    capabilities: [NodeCapability.SCHEDULE],
    inputs: [
      { name: 'cron', type: 'string', optional: true },
      { name: 'timezone', type: 'string', optional: true },
    ],
    outputs: [
      { name: 'triggered_at', type: 'string' },
      { name: 'run_index', type: 'number' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['定时', '调度', 'Cron', '触发'],
  },
  {
    node_id: 'n8n_manual_trigger',
    name: '手动触发器',
    description: '手动执行工作流',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.AUTOMATION,
    capabilities: [NodeCapability.WEBHOOK],
    inputs: [{ name: 'params', type: 'object', optional: true }],
    outputs: [{ name: 'result', type: 'object' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['手动', '触发'],
  },

  // ========== HTTP/集成 ==========
  {
    node_id: 'n8n_http_request',
    name: 'HTTP 请求',
    description: '调用任意 HTTP API，支持 GET/POST/PUT/DELETE',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.INTEGRATION,
    capabilities: [NodeCapability.HTTP, NodeCapability.WEBHOOK],
    inputs: [
      { name: 'url', type: 'string' },
      { name: 'method', type: 'string', optional: true },
      { name: 'headers', type: 'object', optional: true },
      { name: 'body', type: 'any', optional: true },
      { name: 'auth', type: 'object', optional: true },
    ],
    outputs: [
      { name: 'response', type: 'object' },
      { name: 'status_code', type: 'number' },
      { name: 'headers', type: 'object' },
    ],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 500 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['HTTP', 'API', '集成', '请求'],
  },
  {
    node_id: 'n8n_oauth2_api',
    name: 'OAuth2 API 调用',
    description: '使用 OAuth2 认证调用 API',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.INTEGRATION,
    capabilities: [NodeCapability.HTTP, NodeCapability.WEBHOOK],
    inputs: [
      { name: 'url', type: 'string' },
      { name: 'scopes', type: 'array', optional: true },
      { name: 'auth_type', type: 'string', optional: true },
    ],
    outputs: [
      { name: 'data', type: 'object' },
      { name: 'access_token', type: 'string' },
    ],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 800 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['OAuth', '认证', 'HTTP', 'API'],
  },

  // ========== 数据库 ==========
  {
    node_id: 'n8n_postgres',
    name: 'PostgreSQL',
    description: 'PostgreSQL 数据库查询和操作',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.DATABASE],
    inputs: [
      { name: 'query', type: 'string' },
      { name: 'params', type: 'array', optional: true },
      { name: 'operation', type: 'string', optional: true },
    ],
    outputs: [
      { name: 'rows', type: 'array' },
      { name: 'affected_count', type: 'number' },
    ],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 100 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['数据库', 'PostgreSQL', 'SQL'],
  },
  {
    node_id: 'n8n_mysql',
    name: 'MySQL',
    description: 'MySQL 数据库查询和操作',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.DATABASE],
    inputs: [
      { name: 'query', type: 'string' },
      { name: 'params', type: 'array', optional: true },
    ],
    outputs: [
      { name: 'rows', type: 'array' },
      { name: 'affected_count', type: 'number' },
    ],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 100 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['数据库', 'MySQL', 'SQL'],
  },
  {
    node_id: 'n8n_mongodb',
    name: 'MongoDB',
    description: 'MongoDB 文档数据库操作',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.DATABASE],
    inputs: [
      { name: 'operation', type: 'string' },
      { name: 'collection', type: 'string' },
      { name: 'filter', type: 'object', optional: true },
      { name: 'document', type: 'object', optional: true },
    ],
    outputs: [
      { name: 'documents', type: 'array' },
      { name: 'inserted_id', type: 'string' },
    ],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 100 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['数据库', 'MongoDB', 'NoSQL'],
  },
  {
    node_id: 'n8n_redis',
    name: 'Redis 缓存',
    description: 'Redis 缓存读写',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.DATABASE],
    inputs: [
      { name: 'operation', type: 'string' },
      { name: 'key', type: 'string' },
      { name: 'value', type: 'any', optional: true },
      { name: 'ttl', type: 'number', optional: true },
    ],
    outputs: [{ name: 'result', type: 'any' }],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 10 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['Redis', '缓存', 'NoSQL'],
  },

  // ========== 消息通知 ==========
  {
    node_id: 'n8n_gmail',
    name: 'Gmail 发送',
    description: '通过 Gmail 发送邮件',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.INTEGRATION,
    capabilities: [NodeCapability.WEBHOOK],
    inputs: [
      { name: 'to', type: 'string' },
      { name: 'subject', type: 'string' },
      { name: 'body', type: 'string' },
      { name: 'attachments', type: 'array', optional: true },
      { name: 'cc', type: 'string', optional: true },
      { name: 'bcc', type: 'string', optional: true },
    ],
    outputs: [{ name: 'message_id', type: 'string' }],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 500 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['邮件', 'Gmail', '通知'],
  },
  {
    node_id: 'n8n_slack',
    name: 'Slack 消息',
    description: '发送 Slack 频道消息',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.INTEGRATION,
    capabilities: [NodeCapability.WEBHOOK],
    inputs: [
      { name: 'channel', type: 'string' },
      { name: 'text', type: 'string' },
      { name: 'blocks', type: 'array', optional: true },
      { name: 'thread_ts', type: 'string', optional: true },
    ],
    outputs: [{ name: 'ts', type: 'string' }],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 300 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['Slack', '消息', '通知'],
  },
  {
    node_id: 'n8n_feishu',
    name: '飞书消息',
    description: '发送飞书机器人消息',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.INTEGRATION,
    capabilities: [NodeCapability.WEBHOOK],
    inputs: [
      { name: 'webhook_url', type: 'string' },
      { name: 'msg_type', type: 'string' },
      { name: 'content', type: 'object' },
    ],
    outputs: [{ name: 'code', type: 'number' }],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 300 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['飞书', '消息', '通知'],
  },
  {
    node_id: 'n8n_telegram',
    name: 'Telegram 消息',
    description: '发送 Telegram 消息',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.INTEGRATION,
    capabilities: [NodeCapability.WEBHOOK],
    inputs: [
      { name: 'chat_id', type: 'string' },
      { name: 'text', type: 'string' },
      { name: 'parse_mode', type: 'string', optional: true },
    ],
    outputs: [{ name: 'message_id', type: 'number' }],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 300 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['Telegram', '消息', '通知'],
  },

  // ========== 数据处理 ==========
  {
    node_id: 'n8n_code',
    name: '代码执行',
    description: '执行 JavaScript 代码进行数据处理',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.CODE_EXEC, NodeCapability.TRANSFORM],
    inputs: [
      { name: 'js_code', type: 'string' },
      { name: 'input_data', type: 'any', optional: true },
    ],
    outputs: [
      { name: 'output', type: 'any' },
      { name: 'error', type: 'string' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 100 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['代码', 'JavaScript', '转换'],
  },
  {
    node_id: 'n8n_data_transform',
    name: '数据转换',
    description: 'JSON 数据清洗、转换、映射',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.TRANSFORM],
    inputs: [
      { name: 'data', type: 'any' },
      { name: 'mappings', type: 'object', optional: true },
    ],
    outputs: [{ name: 'result', type: 'any' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 10 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['转换', 'JSON', '清洗', '数据'],
  },
  {
    node_id: 'n8n_split_in_batches',
    name: '批量分片',
    description: '将数组拆分为多个批次处理',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.LOGIC,
    capabilities: [NodeCapability.ITERATION],
    inputs: [
      { name: 'data', type: 'array' },
      { name: 'batch_size', type: 'number', optional: true },
    ],
    outputs: [
      { name: 'batch', type: 'any' },
      { name: 'index', type: 'number' },
      { name: 'total', type: 'number' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 5 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['批量', '分片', '循环'],
  },
  {
    node_id: 'n8n_loop_over_items',
    name: '数组迭代',
    description: '遍历数组每一项执行子流程',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.LOGIC,
    capabilities: [NodeCapability.ITERATION],
    inputs: [{ name: 'items', type: 'array' }],
    outputs: [
      { name: 'item', type: 'any' },
      { name: 'index', type: 'number' },
      { name: 'total', type: 'number' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 10 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['循环', '迭代', '数组'],
  },

  // ========== 逻辑控制 ==========
  {
    node_id: 'n8n_if',
    name: 'IF 条件分支',
    description: '根据条件选择执行分支',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.LOGIC,
    capabilities: [NodeCapability.CONDITION],
    inputs: [
      { name: 'condition', type: 'boolean' },
      { name: 'value1', type: 'any', optional: true },
      { name: 'operation', type: 'string', optional: true },
      { name: 'value2', type: 'any', optional: true },
    ],
    outputs: [
      { name: 'true', type: 'any' },
      { name: 'false', type: 'any' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['条件', '分支', 'IF'],
  },
  {
    node_id: 'n8n_switch',
    name: 'Switch 多条件分支',
    description: '多条件路由分支',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.LOGIC,
    capabilities: [NodeCapability.CONDITION],
    inputs: [
      { name: 'value', type: 'any' },
      { name: 'mode', type: 'string', optional: true },
    ],
    outputs: [{ name: 'output', type: 'any' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['分支', 'Switch', '路由'],
  },
  {
    node_id: 'n8n_wait',
    name: '等待',
    description: '等待指定时间后继续',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.LOGIC,
    capabilities: [NodeCapability.SCHEDULE],
    inputs: [
      { name: 'wait_amount', type: 'number' },
      { name: 'unit', type: 'string', optional: true },
    ],
    outputs: [{ name: 'resumed', type: 'boolean' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1000 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['等待', '延迟', '定时'],
  },

  // ========== 文件处理 ==========
  {
    node_id: 'n8n_read_binary',
    name: '读取二进制文件',
    description: '读取文件作为二进制数据',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.FILE],
    inputs: [{ name: 'file_path', type: 'string' }],
    outputs: [
      { name: 'data', type: 'binary' },
      { name: 'file_name', type: 'string' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 100 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['文件', '读取', '二进制'],
  },
  {
    node_id: 'n8n_write_binary',
    name: '写入二进制文件',
    description: '将数据写入文件',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.FILE],
    inputs: [
      { name: 'file_path', type: 'string' },
      { name: 'data', type: 'binary' },
      { name: 'mode', type: 'string', optional: true },
    ],
    outputs: [{ name: 'written', type: 'boolean' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 100 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['文件', '写入', '二进制'],
  },
  {
    node_id: 'n8n_read_binary_file',
    name: '读取文件',
    description: '读取文本或二进制文件内容',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.FILE],
    inputs: [{ name: 'file_path', type: 'string' }],
    outputs: [
      { name: 'content', type: 'string' },
      { name: 'mime_type', type: 'string' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 100 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['文件', '读取', '文本'],
  },

  // ========== AI 辅助 ==========
  {
    node_id: 'n8n_openai',
    name: 'OpenAI GPT',
    description: '调用 OpenAI GPT 模型',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.LLM],
    inputs: [
      { name: 'prompt', type: 'string' },
      { name: 'model', type: 'string', optional: true },
      { name: 'temperature', type: 'number', optional: true },
      { name: 'max_tokens', type: 'number', optional: true },
    ],
    outputs: [
      { name: 'response', type: 'string' },
      { name: 'usage', type: 'object' },
    ],
    cost_estimate: { tokens: 1000, api_calls: 1, latency_ms: 2000 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['OpenAI', 'GPT', 'LLM', 'AI'],
  },

  // ========== 队列/事件 ==========
  {
    node_id: 'n8n_rabbitmq',
    name: 'RabbitMQ',
    description: 'RabbitMQ 消息队列发布/订阅',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.INTEGRATION,
    capabilities: [NodeCapability.WEBHOOK],
    inputs: [
      { name: 'queue', type: 'string' },
      { name: 'message', type: 'any' },
      { name: 'operation', type: 'string', optional: true },
    ],
    outputs: [{ name: 'delivered', type: 'boolean' }],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 50 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['队列', 'RabbitMQ', '消息'],
  },

  // ========== 其他工具 ==========
  {
    node_id: 'n8n_set',
    name: '设置变量',
    description: '设置工作流变量',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.TRANSFORM],
    inputs: [{ name: 'value', type: 'any' }],
    outputs: [{ name: 'value', type: 'any' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['变量', '设置'],
  },
  {
    node_id: 'n8n_merge',
    name: '合并数据',
    description: '合并多个分支的数据',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.TRANSFORM],
    inputs: [
      { name: 'input1', type: 'any' },
      { name: 'input2', type: 'any' },
      { name: 'mode', type: 'string', optional: true },
    ],
    outputs: [{ name: 'merged', type: 'any' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 5 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['合并', '数据', 'Join'],
  },
  {
    node_id: 'n8n_remove_doublets',
    name: '去重',
    description: '移除重复的数据项',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.TRANSFORM],
    inputs: [
      { name: 'data', type: 'array' },
      { name: 'fields', type: 'array', optional: true },
    ],
    outputs: [{ name: 'deduplicated', type: 'array' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 50 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['去重', '清洗', '数据'],
  },
  {
    node_id: 'n8n_move_binary_data',
    name: '二进制数据转换',
    description: '二进制数据格式转换',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.FILE, NodeCapability.TRANSFORM],
    inputs: [
      { name: 'data', type: 'binary' },
      { name: 'operation', type: 'string' },
    ],
    outputs: [{ name: 'result', type: 'binary' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 100 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['二进制', '转换', '编码'],
  },
  {
    node_id: 'n8n_html_extract',
    name: 'HTML 提取',
    description: '从 HTML 中提取数据',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.TRANSFORM],
    inputs: [
      { name: 'html', type: 'string' },
      { name: 'css_selector', type: 'string' },
    ],
    outputs: [
      { name: 'extracted', type: 'array' },
      { name: 'text', type: 'string' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 100 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['HTML', '提取', '解析'],
  },
  {
    node_id: 'n8n_xml',
    name: 'XML 处理',
    description: 'XML 数据解析和构建',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.TRANSFORM],
    inputs: [
      { name: 'data', type: 'string' },
      { name: 'operation', type: 'string' },
    ],
    outputs: [{ name: 'result', type: 'any' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 50 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['XML', '解析', '数据'],
  },
  {
    node_id: 'n8n_date_time',
    name: '日期时间',
    description: '日期时间格式转换和计算',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.TRANSFORM],
    inputs: [
      { name: 'value', type: 'string' },
      { name: 'operation', type: 'string' },
      { name: 'format', type: 'string', optional: true },
    ],
    outputs: [{ name: 'result', type: 'string' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 10 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['日期', '时间', '格式'],
  },
  {
    node_id: 'n8n_spreadsheet',
    name: '电子表格',
    description: 'Excel/CSV 文件读写',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.FILE],
    inputs: [
      { name: 'file_path', type: 'string' },
      { name: 'operation', type: 'string' },
      { name: 'sheet_name', type: 'string', optional: true },
    ],
    outputs: [
      { name: 'data', type: 'array' },
      { name: 'file_path', type: 'string' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 500 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['Excel', 'CSV', '表格'],
  },
  {
    node_id: 'n8n_error_trigger',
    name: '错误触发器',
    description: '工作流出错时触发',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.AUTOMATION,
    capabilities: [NodeCapability.WEBHOOK],
    inputs: [{ name: 'error', type: 'object' }],
    outputs: [{ name: 'error_message', type: 'string' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['错误', '异常', '触发'],
  },
  {
    node_id: 'n8n_notify',
    name: '工作流通知',
    description: '发送工作流状态通知',
    engine: WorkflowEngine.N8N,
    category: NodeCategory.AUTOMATION,
    capabilities: [NodeCapability.WEBHOOK],
    inputs: [
      { name: 'message', type: 'string' },
      { name: 'run_id', type: 'string', optional: true },
    ],
    outputs: [{ name: 'sent', type: 'boolean' }],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 100 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['通知', '状态'],
  },
];

// ============================================
// Dify 节点注册 (20个)
// ============================================

const difyNodeRegistry: NodeMetadata[] = [
  // ========== LLM 节点 ==========
  {
    node_id: 'dify_llm',
    name: 'LLM 推理',
    description: '多模型 LLM 推理（Claude/GPT/本地模型）',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.LLM, NodeCapability.STREAMING],
    inputs: [
      { name: 'prompt', type: 'string' },
      { name: 'model', type: 'string', optional: true },
      { name: 'temperature', type: 'number', optional: true },
      { name: 'max_tokens', type: 'number', optional: true },
    ],
    outputs: [
      { name: 'text', type: 'string' },
      { name: 'usage', type: 'object' },
    ],
    cost_estimate: { tokens: 1000, api_calls: 1, latency_ms: 2000 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['LLM', '推理', '大模型', 'Claude', 'GPT'],
  },
  {
    node_id: 'dify_chat',
    name: '对话补全',
    description: '多轮对话上下文补全',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.LLM, NodeCapability.STREAMING],
    inputs: [
      { name: 'query', type: 'string' },
      { name: 'conversation_id', type: 'string', optional: true },
      { name: 'model', type: 'string', optional: true },
    ],
    outputs: [
      { name: 'text', type: 'string' },
      { name: 'conversation_id', type: 'string' },
    ],
    cost_estimate: { tokens: 1200, api_calls: 1, latency_ms: 2500 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['对话', 'Chat', '上下文'],
  },
  {
    node_id: 'dify_completion',
    name: '文本补全',
    description: '不带上下文的纯文本补全',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.LLM],
    inputs: [
      { name: 'prompt', type: 'string' },
      { name: 'model', type: 'string', optional: true },
    ],
    outputs: [{ name: 'text', type: 'string' }],
    cost_estimate: { tokens: 800, api_calls: 1, latency_ms: 1800 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['补全', 'Completion', '文本'],
  },

  // ========== RAG / 知识检索 ==========
  {
    node_id: 'dify_knowledge_retrieval',
    name: '知识检索',
    description: 'Dify RAG 知识库检索（内置分块/向量化/重排）',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.RAG],
    inputs: [
      { name: 'query', type: 'string' },
      { name: 'dataset_id', type: 'string' },
      { name: 'top_k', type: 'number', optional: true },
      { name: 'score_threshold', type: 'number', optional: true },
    ],
    outputs: [
      { name: 'chunks', type: 'array' },
      { name: 'summary', type: 'string' },
      { name: 'sources', type: 'array' },
    ],
    cost_estimate: { tokens: 200, api_calls: 1, latency_ms: 500 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['RAG', '知识', '检索', '向量'],
  },
  {
    node_id: 'dify_knowledge_inline',
    name: '知识检索(内联)',
    description: '直接在工作流中嵌入知识检索，无需预建知识库',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.RAG],
    inputs: [
      { name: 'query', type: 'string' },
      { name: 'documents', type: 'array' },
      { name: 'top_k', type: 'number', optional: true },
    ],
    outputs: [
      { name: 'chunks', type: 'array' },
      { name: 'answer', type: 'string' },
    ],
    cost_estimate: { tokens: 500, api_calls: 1, latency_ms: 800 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['RAG', '内联', '文档'],
  },
  {
    node_id: 'dify_document_extractor',
    name: '文档提取',
    description: '从上传文档中提取文本内容',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.FILE],
    inputs: [{ name: 'file', type: 'binary' }],
    outputs: [
      { name: 'text', type: 'string' },
      { name: 'metadata', type: 'object' },
    ],
    cost_estimate: { tokens: 100, api_calls: 1, latency_ms: 2000 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['文档', '提取', '文本'],
  },

  // ========== Agent 节点 ==========
  {
    node_id: 'dify_agent',
    name: 'AI Agent',
    description: 'Dify Agent 节点（自主工具调用 + 思维链 + ReAct）',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.AGENT, NodeCapability.LLM, NodeCapability.HTTP],
    inputs: [
      { name: 'task', type: 'string' },
      { name: 'app_id', type: 'string' },
      { name: 'max_steps', type: 'number', optional: true },
      { name: 'tools', type: 'array', optional: true },
    ],
    outputs: [
      { name: 'result', type: 'object' },
      { name: 'thoughts', type: 'array' },
      { name: 'steps', type: 'number' },
    ],
    cost_estimate: { tokens: 3000, api_calls: 5, latency_ms: 15000 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['Agent', '自主', '工具调用', 'ReAct'],
  },
  {
    node_id: 'dify_react_agent',
    name: 'ReAct Agent',
    description: '推理-行动循环 Agent（Think-Act-Observe）',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.AGENT, NodeCapability.REASONING],
    inputs: [
      { name: 'query', type: 'string' },
      { name: 'tools', type: 'array' },
    ],
    outputs: [
      { name: 'answer', type: 'string' },
      { name: 'history', type: 'array' },
    ],
    cost_estimate: { tokens: 5000, api_calls: 10, latency_ms: 30000 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['ReAct', '推理', 'Agent'],
  },

  // ========== 分类/理解 ==========
  {
    node_id: 'dify_question_classifier',
    name: '问答分类',
    description: '用户意图分类和路由',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.CLASSIFICATION],
    inputs: [
      { name: 'query', type: 'string' },
      { name: 'categories', type: 'array' },
      { name: 'description', type: 'string', optional: true },
    ],
    outputs: [
      { name: 'category', type: 'string' },
      { name: 'confidence', type: 'number' },
    ],
    cost_estimate: { tokens: 300, api_calls: 1, latency_ms: 800 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['分类', '意图', '路由'],
  },
  {
    node_id: 'dify_sentiment_analysis',
    name: '情感分析',
    description: '文本情感极性分析',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.CLASSIFICATION],
    inputs: [{ name: 'text', type: 'string' }],
    outputs: [
      { name: 'sentiment', type: 'string' },
      { name: 'score', type: 'number' },
    ],
    cost_estimate: { tokens: 100, api_calls: 1, latency_ms: 500 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['情感', '分析', 'NLP'],
  },
  {
    node_id: 'dify_entity_extraction',
    name: '实体提取',
    description: '命名实体识别（NER）',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.CLASSIFICATION],
    inputs: [
      { name: 'text', type: 'string' },
      { name: 'schema', type: 'array', optional: true },
    ],
    outputs: [
      { name: 'entities', type: 'array' },
      { name: 'relations', type: 'array' },
    ],
    cost_estimate: { tokens: 200, api_calls: 1, latency_ms: 600 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['NER', '实体', '提取'],
  },
  {
    node_id: 'dify_parameter_extractor',
    name: '参数提取',
    description: '将自然语言转换为结构化参数',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.AI,
    capabilities: [NodeCapability.CLASSIFICATION],
    inputs: [
      { name: 'text', type: 'string' },
      { name: 'parameters', type: 'array' },
    ],
    outputs: [{ name: 'params', type: 'object' }],
    cost_estimate: { tokens: 400, api_calls: 1, latency_ms: 1000 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['参数', '结构化', '提取'],
  },

  // ========== 代码执行 ==========
  {
    node_id: 'dify_code',
    name: '代码执行',
    description: 'Python / JavaScript 代码执行',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.CODE_EXEC, NodeCapability.TRANSFORM],
    inputs: [
      { name: 'code', type: 'string' },
      { name: 'language', type: 'string' },
      { name: 'inputs', type: 'object', optional: true },
    ],
    outputs: [
      { name: 'result', type: 'any' },
      { name: 'logs', type: 'array' },
    ],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 1000 },
    whitelist_level: WhitelistLevel.GRAY,
    version: '1.0',
    tags: ['代码', 'Python', 'JS', '执行'],
  },
  {
    node_id: 'dify_template',
    name: '模板渲染',
    description: 'Jinja2 模板生成',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.LOGIC,
    capabilities: [NodeCapability.TEMPLATE, NodeCapability.TRANSFORM],
    inputs: [
      { name: 'template', type: 'string' },
      { name: 'variables', type: 'object' },
    ],
    outputs: [{ name: 'output', type: 'string' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 50 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['模板', 'Jinja2', '渲染'],
  },

  // ========== 逻辑控制 ==========
  {
    node_id: 'dify_if_else',
    name: 'IF-ELSE 条件',
    description: 'Dify 工作流条件分支',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.LOGIC,
    capabilities: [NodeCapability.CONDITION],
    inputs: [
      { name: 'condition', type: 'boolean' },
      { name: 'logical_operator', type: 'string', optional: true },
    ],
    outputs: [{ name: 'output', type: 'any' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['条件', 'IF', '分支'],
  },
  {
    node_id: 'dify_iteration',
    name: '迭代循环',
    description: '对数组每个元素执行子工作流',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.LOGIC,
    capabilities: [NodeCapability.ITERATION],
    inputs: [
      { name: 'items', type: 'array' },
      { name: 'max_concurrency', type: 'number', optional: true },
    ],
    outputs: [{ name: 'results', type: 'array' }],
    cost_estimate: { tokens: 500, api_calls: 1, latency_ms: 5000 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['迭代', '循环', '数组'],
  },
  {
    node_id: 'dify_loop',
    name: '次数循环',
    description: '指定次数的循环执行',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.LOGIC,
    capabilities: [NodeCapability.ITERATION],
    inputs: [
      { name: 'times', type: 'number' },
      { name: 'incr_var', type: 'string', optional: true },
    ],
    outputs: [{ name: 'iteration_result', type: 'any' }],
    cost_estimate: { tokens: 100, api_calls: 1, latency_ms: 2000 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['循环', '次数', '迭代'],
  },

  // ========== 变量 ==========
  {
    node_id: 'dify_variable_assigner',
    name: '变量赋值',
    description: '设置/修改变量值',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.TRANSFORM],
    inputs: [
      { name: 'variable', type: 'string' },
      { name: 'value', type: 'any' },
    ],
    outputs: [{ name: 'assigned', type: 'any' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['变量', '赋值'],
  },
  {
    node_id: 'dify_variable_aggregator',
    name: '变量聚合',
    description: '合并多个分支的变量输出',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.TRANSFORM],
    inputs: [{ name: 'variables', type: 'array' }],
    outputs: [{ name: 'aggregated', type: 'object' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 1 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['变量', '聚合'],
  },
  {
    node_id: 'dify_list_operator',
    name: '列表操作',
    description: '数组过滤、排序、切片',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.DATA,
    capabilities: [NodeCapability.TRANSFORM],
    inputs: [
      { name: 'list', type: 'array' },
      { name: 'operation', type: 'string' },
      { name: 'params', type: 'object', optional: true },
    ],
    outputs: [{ name: 'result', type: 'array' }],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 50 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['列表', '数组', '操作'],
  },

  // ========== HTTP/工具 ==========
  {
    node_id: 'dify_http_request',
    name: 'HTTP 请求',
    description: 'Dify 内置 HTTP 请求节点',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.INTEGRATION,
    capabilities: [NodeCapability.HTTP],
    inputs: [
      { name: 'url', type: 'string' },
      { name: 'method', type: 'string' },
      { name: 'headers', type: 'object', optional: true },
      { name: 'body', type: 'any', optional: true },
    ],
    outputs: [
      { name: 'response', type: 'object' },
      { name: 'status', type: 'number' },
    ],
    cost_estimate: { tokens: 0, api_calls: 1, latency_ms: 1000 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['HTTP', '请求'],
  },

  // ========== 交互 ==========
  {
    node_id: 'dify_human_input',
    name: '人工输入',
    description: '暂停工作流等待人工确认或输入',
    engine: WorkflowEngine.DIFY,
    category: NodeCategory.LOGIC,
    capabilities: [NodeCapability.WEBHOOK],
    inputs: [
      { name: 'prompt', type: 'string' },
      { name: 'timeout_seconds', type: 'number', optional: true },
    ],
    outputs: [
      { name: 'user_input', type: 'string' },
      { name: 'confirmed', type: 'boolean' },
    ],
    cost_estimate: { tokens: 0, api_calls: 0, latency_ms: 60000 },
    whitelist_level: WhitelistLevel.WHITE,
    version: '1.0',
    tags: ['人工', '交互', '确认'],
  },
];

// ============================================
// 统一节点注册表
// ============================================

export class UnifiedNodeRegistry {
  private registry: Map<string, NodeMetadata> = new Map();

  constructor() {
    // 注册所有 n8n 节点
    for (const node of n8nNodeRegistry) {
      this.registry.set(node.node_id, node);
    }

    // 注册所有 Dify 节点
    for (const node of difyNodeRegistry) {
      this.registry.set(node.node_id, node);
    }

    console.log(`[UnifiedNodeRegistry] Initialized with ${n8nNodeRegistry.length} n8n nodes + ${difyNodeRegistry.length} Dify nodes = ${this.registry.size} total nodes`);
  }

  /**
   * 获取节点元数据
   */
  get(nodeId: string): NodeMetadata | undefined {
    return this.registry.get(nodeId);
  }

  /**
   * 检查节点是否存在
   */
  has(nodeId: string): boolean {
    return this.registry.has(nodeId);
  }

  /**
   * 按引擎列出节点
   */
  listByEngine(engine: WorkflowEngine): NodeMetadata[] {
    return Array.from(this.registry.values()).filter((n) => n.engine === engine);
  }

  /**
   * 按分类列出节点
   */
  listByCategory(category: NodeCategory): NodeMetadata[] {
    return Array.from(this.registry.values()).filter((n) => n.category === category);
  }

  /**
   * 按能力搜索节点
   */
  findByCapability(capability: NodeCapability): NodeMetadata[] {
    return Array.from(this.registry.values()).filter((n) =>
      n.capabilities.includes(capability)
    );
  }

  /**
   * 按标签搜索节点
   */
  findByTag(tag: string): NodeMetadata[] {
    const lowerTag = tag.toLowerCase();
    return Array.from(this.registry.values()).filter((n) =>
      n.tags.some((t) => t.toLowerCase().includes(lowerTag))
    );
  }

  /**
   * 为一组能力找到最优节点
   */
  findBestNode(capability: NodeCapability, whitelistOnly: boolean = false): NodeMetadata | undefined {
    const candidates = Array.from(this.registry.values())
      .filter((n) => {
        if (!n.capabilities.includes(capability)) return false;
        if (whitelistOnly && n.whitelist_level !== WhitelistLevel.WHITE) return false;
        return true;
      })
      .sort((a, b) => {
        // 白名单优先
        if (a.whitelist_level === WhitelistLevel.WHITE && b.whitelist_level !== WhitelistLevel.WHITE) return -1;
        if (b.whitelist_level === WhitelistLevel.WHITE && a.whitelist_level !== WhitelistLevel.WHITE) return 1;
        // 再按成本排序
        return a.cost_estimate.tokens - b.cost_estimate.tokens;
      });

    return candidates[0];
  }

  /**
   * 为多个能力找到节点组合
   */
  findNodeCombo(requiredCapabilities: NodeCapability[], whitelistOnly: boolean = false): NodeMetadata[] {
    const result: NodeMetadata[] = [];
    const usedNodeIds = new Set<string>();
    const remaining = [...requiredCapabilities];

    // 先尝试找到全能节点
    for (const cap of remaining) {
      const allInOne = Array.from(this.registry.values()).find((n) => {
        if (usedNodeIds.has(n.node_id)) return false;
        if (!requiredCapabilities.every((c) => n.capabilities.includes(c))) return false;
        if (whitelistOnly && n.whitelist_level !== WhitelistLevel.WHITE) return false;
        return true;
      });

      if (allInOne) {
        result.push(allInOne);
        usedNodeIds.add(allInOne.node_id);
        remaining.splice(remaining.indexOf(cap), 1);
      }
    }

    // 再为剩余能力找节点
    for (const cap of remaining) {
      const best = this.findBestNode(cap, whitelistOnly);
      if (best && !usedNodeIds.has(best.node_id)) {
        result.push(best);
        usedNodeIds.add(best.node_id);
      }
    }

    return result;
  }

  /**
   * 搜索节点（模糊匹配）
   */
  search(query: string, limit: number = 10): NodeMetadata[] {
    const lowerQuery = query.toLowerCase();
    const scored = Array.from(this.registry.values())
      .map((n) => {
        let score = 0;
        if (n.name.toLowerCase().includes(lowerQuery)) score += 10;
        if (n.description.toLowerCase().includes(lowerQuery)) score += 5;
        if (n.node_id.toLowerCase().includes(lowerQuery)) score += 3;
        if (n.tags.some((t) => t.toLowerCase().includes(lowerQuery))) score += 2;
        if (n.capabilities.some((c) => c.toLowerCase().includes(lowerQuery))) score += 1;
        return { node: n, score };
      })
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score);

    return scored.slice(0, limit).map((x) => x.node);
  }

  /**
   * 获取所有节点
   */
  listAll(): NodeMetadata[] {
    return Array.from(this.registry.values());
  }

  /**
   * 获取节点统计
   */
  getStats(): {
    total: number;
    byEngine: Record<WorkflowEngine, number>;
    byCategory: Record<NodeCategory, number>;
    byCapability: Record<NodeCapability, number>;
    byWhitelist: Record<WhitelistLevel, number>;
  } {
    const nodes = Array.from(this.registry.values());

    const stats = {
      total: nodes.length,
      byEngine: {} as Record<WorkflowEngine, number>,
      byCategory: {} as Record<NodeCategory, number>,
      byCapability: {} as Record<NodeCapability, number>,
      byWhitelist: {} as Record<WhitelistLevel, number>,
    };

    for (const engine of Object.values(WorkflowEngine)) {
      stats.byEngine[engine] = nodes.filter((n) => n.engine === engine).length;
    }
    for (const category of Object.values(NodeCategory)) {
      stats.byCategory[category] = nodes.filter((n) => n.category === category).length;
    }
    for (const cap of Object.values(NodeCapability)) {
      stats.byCapability[cap] = nodes.filter((n) => n.capabilities.includes(cap)).length;
    }
    for (const level of Object.values(WhitelistLevel)) {
      stats.byWhitelist[level] = nodes.filter((n) => n.whitelist_level === level).length;
    }

    return stats;
  }

  /**
   * 注册自定义节点
   */
  register(node: NodeMetadata): void {
    this.registry.set(node.node_id, node);
  }
}

// ============================================
// 单例导出
// ============================================

export const unifiedNodeRegistry = new UnifiedNodeRegistry();
