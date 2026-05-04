/**
 * OpenClaw MCP API Server
 * ============================================
 * Phase 16: 集成联调 - MCP Server真实实现
 *
 * 功能:
 * - HTTP API暴露M06/M07/M09核心能力
 * - 供Python MCP Server通过HTTP调用
 * - 无外部依赖，使用Node.js内置http模块
 * ============================================
 */

import * as http from 'http';
import { fileURLToPath } from 'url';
import { PromptRouter, TaskType, PromptFragment, PromptFragmentType, PromptPriority } from '../../domain/prompt_engine/mod';
import { WorkingMemory, SessionMemory, PersistentMemory, KGStorage, MemorySource } from '../../domain/memory/mod';
// M01 Orchestrator - TS域编排引擎（复杂任务辅助入口）
import { orchestrator } from '../../domain/m01/orchestrator';
import { IntentRoute } from '../../domain/m01/types';
import { deerflowClient } from '../../domain/m01/deerflow_client';

// ============================================
// MCP API 配置
// ============================================

const MCP_API_PORT = process.env.MCP_API_PORT || 8082;
const DAPR_HTTP_PORT = process.env.DAPR_HTTP_PORT || '3500';

// SECURITY FIX: API密钥必须通过环境变量设置，无默认值
const API_KEY = process.env.MCP_API_KEY;
if (!API_KEY) {
  console.error('[MCP-Server] FATAL: MCP_API_KEY environment variable is not set');
  process.exit(1);  // 启动时即失败，而非使用不安全的默认值
}

const AUTH_CACHE_TTL_MS = 5 * 60 * 1000; // 5分钟

// SECURITY FIX: CORS允许的来源域名列表
const CORS_ALLOWED_ORIGINS = (process.env.CORS_ALLOWED_ORIGINS || 'localhost,127.0.0.1')
  .split(',')
  .map(s => s.trim());

// ============================================
// 认证缓存
// ============================================

interface AuthResult {
  valid: boolean;
  cachedAt: number;
}

const authCache = new Map<string, AuthResult>();
const AUTH_CACHE_MAX_SIZE = 1000;  // SECURITY: 防止缓存耗尽攻击

function validateApiKey(key: string): boolean {
  // SECURITY: 如果缓存超过最大限制，清除最旧的条目
  if (authCache.size >= AUTH_CACHE_MAX_SIZE) {
    const firstKey = authCache.keys().next().value;
    if (firstKey) authCache.delete(firstKey);
  }
  // 检查缓存
  const cached = authCache.get(key);
  if (cached && Date.now() - cached.cachedAt < AUTH_CACHE_TTL_MS) {
    return cached.valid;
  }

  // 验证API Key
  const valid = key === API_KEY;

  // 更新缓存
  authCache.set(key, { valid, cachedAt: Date.now() });

  return valid;
}

function extractAuthToken(req: http.IncomingMessage): string | null {
  const authHeader = req.headers['authorization'];
  if (!authHeader) return null;

  // 支持 "Bearer <token>" 格式
  if (authHeader.startsWith('Bearer ')) {
    return authHeader.slice(7);
  }

  return authHeader;
}

function sendAuthError(res: http.ServerResponse): void {
  res.writeHead(401, {
    'Content-Type': 'application/json',
    'WWW-Authenticate': 'Bearer realm="OpenClaw MCP API"'
  });
  res.end(JSON.stringify({
    jsonrpc: '2.0',
    id: null,
    error: { code: -32600, message: 'Unauthorized: Invalid or missing API key' }
  }));
}

// ============================================
// 全局实例
// ============================================

const promptRouter = new PromptRouter();

// 创建Memory实例用于API
const workingMemory = new WorkingMemory();
const sessionMemory = new SessionMemory();
const persistentMemory = new PersistentMemory();
const knowledgeGraph = new KGStorage();

// ============================================
// 请求解析
// ============================================

interface MCPRequest {
  jsonrpc: '2.0';
  id: string | number | null;
  method: string;
  params?: Record<string, any>;
}

interface MCPResponse {
  jsonrpc: '2.0';
  id: string | number | null;
  result?: any;
  error?: { code: number; message: string };
}

function parseBody(req: http.IncomingMessage): Promise<any> {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      if (!body) return resolve(null);
      try {
        resolve(JSON.parse(body));
      } catch {
        resolve(null);
      }
    });
  });
}

function sendJSON(res: http.ServerResponse, status: number, data: any): void {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

// ============================================
// M09: 提示词路由 API
// ============================================

async function handlePromptRoute(params: {
  userInput: string;
  taskType?: string;
  safetyRules?: string[];
  userPreferences?: Record<string, string>;
  availableTools?: string[];
}): Promise<any> {
  const taskType = params.taskType as TaskType | undefined;
  const safetyRules = params.safetyRules || [];
  const userPreferences = params.userPreferences || {};
  const availableTools = params.availableTools || [];

  const result = await promptRouter.route(params.userInput, {
    taskType,
    safetyRules,
    userPreferences,
    availableTools,
  });

  return {
    content: result.content,
    task_type: result.task_type,
    fragments_used: result.fragments_used,
    few_shot_ids: result.few_shot_ids,
    estimated_tokens: result.estimated_tokens,
    assembled_at: result.assembled_at,
  };
}

// ============================================
// M09: 资产注册 API
// ============================================

function handleRegisterPromptFragment(params: {
  id: string;
  type: string;
  content: string;
  priority: string;
  quality_score_history?: number[];
}): any {
  const fragment: PromptFragment = {
    id: params.id,
    type: params.type as PromptFragmentType,
    content: params.content,
    priority: params.priority as PromptPriority,
    quality_score_history: params.quality_score_history || [],
    gepa_version: 1,
    created_at: new Date().toISOString(),
  };

  promptRouter.registerAsset(fragment);

  return { success: true, fragment_id: params.id };
}

// ============================================
// M09: 任务类型识别 API
// ============================================

async function handleRecognizeTaskType(params: { userInput: string }): Promise<any> {
  const { userInput } = params;

  // 使用recognizer直接
  const { TaskTypeRecognizer } = await import('../../domain/prompt_engine/layer1_router');
  const recognizer = new TaskTypeRecognizer();
  const results = recognizer.recognizeFromInput(userInput);

  return {
    task_types: results.map(r => ({
      task_type: r.taskType,
      confidence: r.confidence,
    })),
  };
}

// ============================================
// M06: 记忆搜索 API
// ============================================

async function handleMemorySearch(params: {
  query: string;
  layer?: 'working' | 'session' | 'persistent' | 'knowledge';
  limit?: number;
}): Promise<any> {
  const { query, layer = 'session', limit = 10 } = params;

  try {
    let results: any[] = [];

    switch (layer) {
      case 'working': {
        // L1: 工作记忆 - 使用retrieve
        const retrieved = workingMemory.retrieve(query, limit);
        results = retrieved.map(r => ({
          id: r.id,
          content: r.content,
          similarity: r.similarity,
          layer: 'working',
        }));
        break;
      }

      case 'session': {
        // L2: 会话记忆 - 使用retrieve
        const retrieved = sessionMemory.retrieve(query, limit);
        results = retrieved.map(r => ({
          id: r.item.id,
          content: r.item.content,
          similarity: r.similarity,
          layer: 'session',
        }));
        break;
      }

      case 'persistent': {
        // L3: 持久记忆 - 使用retrieve
        const retrieved = await persistentMemory.retrieve({ query: query, limit });
        results = retrieved.map(r => ({
          id: r.item.id,
          content: r.item.content,
          similarity: r.similarity,
          layer: 'persistent',
        }));
        break;
      }

      case 'knowledge': {
        // L4: 知识图谱 - 使用queryEntities
        const entities = knowledgeGraph.queryEntities({ name: query, limit });
        results = entities.map(e => ({
          id: e.id,
          name: e.name,
          type: e.type,
          layer: 'knowledge',
        }));
        break;
      }

      default:
        results = [];
    }

    return {
      layer,
      query,
      results,
      count: results.length,
    };
  } catch (error) {
    return {
      layer,
      query,
      results: [],
      count: 0,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// ============================================
// 飞书事件回调 Webhook Handler
// ============================================

async function handleFeishuWebhook(event: any): Promise<any> {
  const eventType = event?.header?.event_type;
  const eventId = event?.header?.event_id;

  console.log(`[Feishu-Webhook] Processing event: ${eventType}, id: ${eventId}`);

  // 卡片动作事件
  if (eventType === 'card.action.trigger') {
    const actionValue = event?.event?.action?.value || '';
    const message = event?.event?.message;
    const chatId = message?.chat_id;
    const openId = message?.sender?.sender_id?.open_id;

    console.log(`[Feishu-Webhook] Card action: value=${actionValue}, chat=${chatId}`);

    // action.value 格式: session:xxx 或 close:issue_id 或 sign:issue_id 等
    return handleFeishuCardAction(actionValue, { chatId, openId, eventId });
  }

  // 线程消息事件 (im.message.receive_v1)
  if (eventType === 'im.message.receive_v1') {
    const message = event?.event?.message;
    const chatId = message?.chat_id;
    const openId = message?.sender?.sender_id?.open_id;
    const contentStr = message?.content || '{}';

    let content: any;
    try {
      content = JSON.parse(contentStr);
    } catch {
      content = { text: contentStr };
    }

    const text = content?.text || '';
    if (!text || text.startsWith('[AIAgent]')) {
      // 忽略 AI 自身消息
      return { ignored: true, reason: 'bot_message' };
    }

    console.log(`[Feishu-Webhook] Thread message: text="${text.slice(0, 50)}", chat=${chatId}`);

    return handleFeishuThreadMessage(text, { chatId, openId, eventId });
  }

  // 卡片 URL 跳转事件
  if (eventType === 'card.action.url') {
    const url = event?.event?.action?.url || '';
    console.log(`[Feishu-Webhook] Card URL action: ${url}`);
    return { handled: true, type: 'url_navigation', url };
  }

  return { ignored: true, reason: `unknown_event_type: ${eventType}` };
}

async function handleFeishuCardAction(
  actionValue: string,
  meta: { chatId: string; openId: string; eventId: string }
): Promise<any> {
  const [actionType, ...rest] = actionValue.split(':');
  const targetId = rest.join(':');

  console.log(`[Feishu-Webhook] Card action type=${actionType}, target=${targetId}`);

  // 动态导入 RTCM 模块（避免循环依赖）
  const { mainAgentHandoff } = await import('../../rtcm/rtcm_main_agent_handoff');
  const { userInterventionClassifier } = await import('../../rtcm/rtcm_user_intervention');

  const session = mainAgentHandoff.getActiveSession();
  if (!session) {
    return { error: 'no_active_session' };
  }

  const threadId = session.activeRtcmThreadId;
  const sessionId = session.activeRtcmSessionId;

  // 将卡片动作映射为干预类型
  let interventionType = 'correction';
  let rawText = `卡片动作: ${actionValue}`;

  if (actionType === 'session') {
    // 查看实时状态 - 不算干预
    return { handled: true, type: 'status_query', sessionId };
  }

  if (actionType === 'close') {
    return { handled: true, type: 'issue_close', issueId: targetId };
  }

  if (actionType === 'sign') {
    return { handled: true, type: 'issue_sign', issueId: targetId };
  }

  if (actionType === 'report') {
    return { handled: true, type: 'report_request', issueId: targetId };
  }

  // 其他动作统一走干预分类器
  const intervention = userInterventionClassifier.processIntervention({
    threadId,
    sessionId,
    issueId: 'current',
    userMessage: rawText,
  });

  const actions = userInterventionClassifier.determineActions(intervention);

  return {
    handled: true,
    type: 'card_intervention',
    interventionId: intervention.interventionId,
    interventionType: intervention.type,
    actions,
  };
}

async function handleFeishuThreadMessage(
  text: string,
  meta: { chatId: string; openId: string; eventId: string }
): Promise<any> {
  const { chatId, openId, eventId } = meta;

  // 动态导入 RTCM 模块
  const { mainAgentHandoff } = await import('../../rtcm/rtcm_main_agent_handoff');
  const { userInterventionClassifier } = await import('../../rtcm/rtcm_user_intervention');
  const { followUpManager } = await import('../../rtcm/rtcm_follow_up');
  const { threadAdapter } = await import('../../rtcm/rtcm_thread_adapter');

  const session = mainAgentHandoff.getActiveSession();
  if (!session) {
    return { error: 'no_active_session' };
  }

  const threadId = session.activeRtcmThreadId;
  const sessionId = session.activeRtcmSessionId;

  // 处理用户干预
  const intervention = userInterventionClassifier.processIntervention({
    threadId,
    sessionId,
    issueId: 'current',
    userMessage: text,
  });

  const actions = userInterventionClassifier.determineActions(intervention);

  console.log(`[Feishu-Webhook] Intervention: type=${intervention.type}, confidence=${intervention.confidence}`);

  // 根据干预类型处理
  if (actions.shouldCreateFollowUpIssue) {
    const parentIssue = { issue_id: 'current', issue_title: '当前议题' };
    const followUpIssue = followUpManager.createFollowUpIssue({
      threadId,
      sessionId,
      parentIssueId: parentIssue.issue_id,
      parentIssueTitle: parentIssue.issue_title,
      newIssueTitle: actions.newIssueTitle || 'FOLLOW_UP 新议题',
      newIssueDescription: text,
      inheritedAssets: followUpManager.extractInheritedAssets(parentIssue as any),
      followUpRequestText: text,
      followUpType: 'new_topic_based_on_conclusion',
    });

    // 更新线程锚点消息
    threadAdapter.updateAnchorMessage(threadId, {
      currentIssueTitle: followUpIssue.issue_title,
      currentStage: 'issue_definition',
    });

    // 确认干预已纳入
    userInterventionClassifier.acknowledgeIntervention(intervention.interventionId);

    return {
      handled: true,
      type: 'follow_up_created',
      interventionId: intervention.interventionId,
      followUpIssueId: followUpIssue.issue_id,
      followUpTitle: followUpIssue.issue_title,
    };
  }

  if (actions.shouldReopenIssue || actions.shouldRecomputeCurrentIssue) {
    // 重新打开/重新计算当前议题
    mainAgentHandoff.resumeRTCMSession({
      sessionId,
      mode: actions.shouldReopenIssue ? 'reopen' : 'recompute',
      userMessage: text,
    });

    userInterventionClassifier.acknowledgeIntervention(intervention.interventionId);

    return {
      handled: true,
      type: actions.shouldReopenIssue ? 'issue_reopened' : 'issue_recomputed',
      interventionId: intervention.interventionId,
      interventionType: intervention.type,
    };
  }

  // 标记为已处理
  userInterventionClassifier.acknowledgeIntervention(intervention.interventionId);

  return {
    handled: true,
    type: 'intervention_logged',
    interventionId: intervention.interventionId,
    interventionType: intervention.type,
    confidence: intervention.confidence,
  };
}

// ============================================
// M06: 记忆写入 API
// ============================================

async function handleMemoryWrite(params: {
  content: string;
  layer: 'working' | 'session' | 'persistent';
  metadata?: Record<string, any>;
}): Promise<any> {
  const { content, layer, metadata = {} } = params;

  try {
    const item = {
      id: `mem_${Date.now()}`,
      content,
      timestamp: new Date().toISOString(),
      metadata,
    };

    switch (layer) {
      case 'working':
        workingMemory.add(item.id, content, 50);
        break;
      case 'session':
        sessionMemory.addItem({
          id: item.id,
          content: content,
          metadata: { source: MemorySource.USER_INPUT, importance: 50, urgency: 0 },
        });
        break;
      case 'persistent':
        persistentMemory.add({
          id: item.id,
          content: content,
          created_at: new Date().toISOString(),
          access_count: 0,
          metadata: { source: MemorySource.USER_INPUT, importance: 50, urgency: 0, promoted_to_memory_md: false },
        });
        break;
    }

    return { success: true, layer, item_id: item.id };
  } catch (error) {
    return {
      success: false,
      layer,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// ============================================
// M07: 资产查询 API (通过SQLite直接访问)
// ============================================

async function handleAssetQuery(params: {
  intent?: string;
  category?: string;
  minQuality?: number;
  limit?: number;
}): Promise<any> {
  // TODO: 实现通过SQLite查询资产
  // 当前返回模拟数据，待与asset_indexer.py集成
  return {
    assets: [],
    count: 0,
    message: 'Asset query via SQLite - integration pending',
  };
}

// ============================================
// M07: 资产详情 API (通过SQLite直接访问)
// ============================================

async function handleAssetGet(params: { assetId: string }): Promise<any> {
  // TODO: 实现通过SQLite获取资产详情
  return {
    error: 'Asset get via SQLite - integration pending',
    asset_id: params.assetId,
  };
}

// ============================================
// M07: 资产创建 API (通过SQLite直接访问)
// ============================================

async function handleAssetCreate(params: {
  name: string;
  category: string;
  description: string;
  content: string;
  qualityScore?: number;
}): Promise<any> {
  // TODO: 实现通过SQLite创建资产
  return {
    success: false,
    message: 'Asset create via SQLite - integration pending',
  };
}

// ============================================
// MCP API 路由
// ============================================

async function handleMCPRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
  const url = new URL(req.url || '/', `http://localhost:${MCP_API_PORT}`);
  const pathname = url.pathname;

  // CORS 头 - SECURITY FIX: 使用域名白名单而非 wildcard
  const origin = req.headers.origin;
  if (origin && CORS_ALLOWED_ORIGINS.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Access-Control-Allow-Credentials', 'true');
  }
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // 认证检查（健康检查端点除外）
  if (pathname !== '/health' && pathname !== '/api/v1') {
    const token = extractAuthToken(req);
    if (!token || !validateApiKey(token)) {
      sendAuthError(res);
      return;
    }
  }

  // MCP API 路由
  try {
    let body: MCPRequest | null = null;
    if (req.method === 'POST') {
      body = await parseBody(req) as MCPRequest;
    }

    // M09: 提示词路由
    if (pathname === '/api/v1/prompt/route' && req.method === 'POST') {
      const bodyParams = body?.params || {};
      const result = await handlePromptRoute({
        userInput: bodyParams.userInput || '',
        taskType: bodyParams.taskType,
        safetyRules: bodyParams.safetyRules,
        userPreferences: bodyParams.userPreferences,
        availableTools: bodyParams.availableTools,
      });
      sendJSON(res, 200, { jsonrpc: '2.0', id: body?.id || null, result });
      return;
    }

    // M09: 注册提示词片段
    if (pathname === '/api/v1/prompt/register' && req.method === 'POST') {
      const bodyParams = body?.params || {};
      const result = handleRegisterPromptFragment({
        id: bodyParams.id || '',
        type: bodyParams.type || '',
        content: bodyParams.content || '',
        priority: bodyParams.priority || 'medium',
        quality_score_history: bodyParams.quality_score_history,
      });
      sendJSON(res, 200, { jsonrpc: '2.0', id: body?.id || null, result });
      return;
    }

    // M09: 任务类型识别
    if (pathname === '/api/v1/prompt/recognize' && req.method === 'POST') {
      const bodyParams = body?.params || {};
      const result = await handleRecognizeTaskType({
        userInput: bodyParams.userInput || '',
      });
      sendJSON(res, 200, { jsonrpc: '2.0', id: body?.id || null, result });
      return;
    }

    // M06: 记忆搜索
    if (pathname === '/api/v1/memory/search' && req.method === 'POST') {
      const bodyParams = body?.params || {};
      const result = await handleMemorySearch({
        query: bodyParams.query || '',
        layer: bodyParams.layer,
        limit: bodyParams.limit,
      });
      sendJSON(res, 200, { jsonrpc: '2.0', id: body?.id || null, result });
      return;
    }

    // M06: 记忆写入
    if (pathname === '/api/v1/memory/write' && req.method === 'POST') {
      const bodyParams = body?.params || {};
      const result = await handleMemoryWrite({
        content: bodyParams.content || '',
        layer: bodyParams.layer || 'session',
        metadata: bodyParams.metadata,
      });
      sendJSON(res, 200, { jsonrpc: '2.0', id: body?.id || null, result });
      return;
    }

    // M06: Python Memory 只读入口
    if (pathname === '/api/v1/memory/python' && req.method === 'GET') {
      try {
        const memory = await deerflowClient.getMemory();
        sendJSON(res, 200, {
          jsonrpc: '2.0',
          id: null,
          result: {
            source: 'python_memory',
            timestamp: new Date().toISOString(),
            data: memory,
          }
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        sendJSON(res, 200, {
          jsonrpc: '2.0',
          id: null,
          error: { code: -32000, message: `Python Memory unavailable: ${msg}` }
        });
      }
      return;
    }

    // M06: Python Memory Config 只读入口
    if (pathname === '/api/v1/memory/python/config' && req.method === 'GET') {
      try {
        const config = await deerflowClient.getMemoryConfig();
        sendJSON(res, 200, {
          jsonrpc: '2.0',
          id: null,
          result: {
            source: 'python_memory_config',
            timestamp: new Date().toISOString(),
            data: config,
          }
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        sendJSON(res, 200, {
          jsonrpc: '2.0',
          id: null,
          error: { code: -32000, message: `Python Memory Config unavailable: ${msg}` }
        });
      }
      return;
    }

    // M07: 资产查询
    if (pathname === '/api/v1/asset/query' && req.method === 'POST') {
      const bodyParams = body?.params || {};
      const result = await handleAssetQuery({
        intent: bodyParams.intent,
        category: bodyParams.category,
        minQuality: bodyParams.minQuality,
        limit: bodyParams.limit,
      });
      sendJSON(res, 200, { jsonrpc: '2.0', id: body?.id || null, result });
      return;
    }

    // M07: 资产详情
    if (pathname === '/api/v1/asset/get' && req.method === 'POST') {
      const bodyParams = body?.params || {};
      const result = await handleAssetGet({
        assetId: bodyParams.assetId || '',
      });
      sendJSON(res, 200, { jsonrpc: '2.0', id: body?.id || null, result });
      return;
    }

    // M07: 资产创建
    if (pathname === '/api/v1/asset/create' && req.method === 'POST') {
      const bodyParams = body?.params || {};
      const result = await handleAssetCreate({
        name: bodyParams.name || '',
        category: bodyParams.category || '',
        description: bodyParams.description || '',
        content: bodyParams.content || '',
        qualityScore: bodyParams.qualityScore,
      });
      sendJSON(res, 200, { jsonrpc: '2.0', id: body?.id || null, result });
      return;
    }

    // 健康检查
    if (pathname === '/health') {
      sendJSON(res, 200, {
        status: 'healthy',
        service: 'mcp-api-server',
        version: '1.0.0',
        timestamp: new Date().toISOString(),
      });
      return;
    }

    // API概览
    if (pathname === '/api/v1') {
      sendJSON(res, 200, {
        name: 'OpenClaw MCP API Server',
        version: '1.0.0',
        endpoints: [
          'POST /api/v1/prompt/route - 提示词路由',
          'POST /api/v1/prompt/register - 注册提示词片段',
          'POST /api/v1/prompt/recognize - 任务类型识别',
          'POST /api/v1/memory/search - 记忆搜索',
          'POST /api/v1/memory/write - 记忆写入',
          'POST /api/v1/asset/query - 资产查询',
          'POST /api/v1/asset/get - 资产详情',
          'POST /api/v1/asset/create - 资产创建',
          'POST /api/v1/orchestrate - M01编排辅助入口(复杂任务)',
          'POST /webhook/feishu - 飞书事件回调',
        ],
      });
      return;
    }

    // ============================================
    // M01: 编排引擎辅助入口 POST /api/v1/orchestrate
    // ============================================
    if (pathname === '/api/v1/orchestrate' && req.method === 'POST') {
      const bodyParams = body?.params || body || {};
      try {
        const result = await handleOrchestrate({
          userInput: bodyParams.userInput || bodyParams.user_input || '',
          requestId: bodyParams.requestId || bodyParams.request_id,
          sessionId: bodyParams.sessionId || bodyParams.session_id,
          priority: bodyParams.priority,
        });
        sendJSON(res, 200, { jsonrpc: '2.0', id: body?.id || null, result });
      } catch (error) {
        console.error('[M01-Entrypoint] Error:', error);
        sendJSON(res, 200, {
          jsonrpc: '2.0',
          id: body?.id || null,
          error: { code: -32603, message: error instanceof Error ? error.message : String(error) },
        });
      }
      return;
    }

    // ============================================
    // 飞书事件回调 Webhook
    // ============================================
    if (pathname === '/webhook/feishu' && req.method === 'POST') {
      const feishuEvent = body;
      console.log('[Feishu-Webhook] Received event:', JSON.stringify(feishuEvent).slice(0, 200));

      try {
        const result = await handleFeishuWebhook(feishuEvent);
        sendJSON(res, 200, { code: 0, msg: 'ok', data: result });
      } catch (error) {
        console.error('[Feishu-Webhook] Error:', error);
        sendJSON(res, 200, { code: -1, msg: String(error) });
      }
      return;
    }

    // 404
    sendJSON(res, 404, {
      jsonrpc: '2.0',
      id: body?.id || null,
      error: { code: -32601, message: 'Method not found' },
    });

  } catch (error) {
    console.error('[MCP-API] Error handling request:', error);
    sendJSON(res, 500, {
      jsonrpc: '2.0',
      id: null,
      error: { code: -32603, message: error instanceof Error ? error.message : 'Internal error' },
    });
  }
}

// ============================================
// M01: 编排引擎辅助入口（有限接入）
// ============================================

/**
 * POST /api/v1/orchestrate
 *
 * M01 有限辅助入口：接收复杂任务，通过 orchestrator.execute() 做意图分类和 DAG 编排。
 *
 * 路由行为：
 *   - IntentRoute.DIRECT_ANSWER  → 直接返回回答（本地处理）
 *   - IntentRoute.CLARIFICATION   → 返回追问请求
 *   - IntentRoute.ORCHESTRATION   → 通过 DeerFlowClient → Python Gateway 执行复杂任务
 *
 * 注意：此入口是「辅助入口」，不替代 Python Gateway:8001 的生产主路径。
 * dag_plan 作为 metadata 附带，Python 侧只理解 rootTask 字符串，不执行 DAG 语义。
 */
async function handleOrchestrate(params: {
  userInput: string;
  requestId?: string;
  sessionId?: string;
  priority?: string;
}): Promise<any> {
  const { userInput, priority = 'normal' } = params;
  const requestId = params.requestId || `m01-${Date.now()}`;
  const sessionId = params.sessionId || `m01-session-${Date.now()}`;

  console.log(`[M01-Entrypoint] orchestrating requestId=${requestId} input="${userInput.slice(0, 60)}..."`);

  // 调用 M01 orchestrator
  const startExec = Date.now();
  const result = await orchestrator.execute({
    requestId,
    sessionId,
    userInput,
    priority: priority as any,
  });

  // 辅助入口说明：route 为 ORCHESTRATION 时表示该任务适合多步编排执行
  // 但 Python 侧当前只把 dag_plan 作为 metadata，不做 DAG 语义执行
  return {
    requestId,
    sessionId,
    route: result.route,
    executionTime: result.executionTime,
    // ORCHESTRATION 时包含编排元信息
    orchestration: result.route === IntentRoute.ORCHESTRATION ? {
      dagPlan: result.execution?.dagPlan || null,
      completedNodes: result.execution?.completedNodes || 0,
      totalNodes: result.execution?.totalNodes || 0,
      // dag_plan 在 metadata 中保留，不做执行保证
      note: 'dag_plan is metadata only; Python agent does not execute DAG semantics today',
    } : null,
    // DIRECT_ANSWER 时返回直接回答
    directAnswer: result.directAnswer || null,
    // CLARIFICATION 时返回追问
    clarification: result.clarification || null,
    error: result.error || null,
  };
}

// ============================================
// 服务器启动
// ============================================

let server: http.Server | null = null;

export function startMCPServer(port = MCP_API_PORT): Promise<http.Server> {
  return new Promise((resolve) => {
    const httpServer = http.createServer(handleMCPRequest);
    server = httpServer;

    httpServer.listen(port, () => {
      console.log(`[MCP-API] OpenClaw MCP API Server running on port ${port}`);
      console.log(`[MCP-API] Endpoints:`);
      console.log(`  - POST /api/v1/prompt/route    - 提示词路由`);
      console.log(`  - POST /api/v1/prompt/register - 注册提示词片段`);
      console.log(`  - POST /api/v1/prompt/recognize - 任务类型识别`);
      console.log(`  - POST /api/v1/memory/search   - 记忆搜索`);
      console.log(`  - POST /api/v1/memory/write    - 记忆写入`);
      console.log(`  - POST /api/v1/asset/query     - 资产查询`);
      console.log(`  - POST /api/v1/asset/get       - 资产详情`);
      console.log(`  - POST /api/v1/asset/create    - 资产创建`);
      console.log(`  - POST /api/v1/orchestrate    - M01编排辅助入口(有限接入)`);
      resolve(httpServer);
    });

    httpServer.on('error', (error) => {
      console.error('[MCP-API] Server error:', error);
    });
  });
}

export function stopMCPServer(): Promise<void> {
  return new Promise((resolve) => {
    if (server) {
      server.close(() => {
        console.log('[MCP-API] Server stopped');
        resolve();
      });
    } else {
      resolve();
    }
  });
}

// ============================================
// 启动演示
// ============================================

// Detect direct execution in a cross-platform way.
// import.meta.url uses forward slashes on Windows; process.argv[1] uses
// backslashes.  fileURLToPath() normalises both to the OS-native format.
const isMainModule = fileURLToPath(import.meta.url) === process.argv[1];

if (isMainModule) {
  startMCPServer(Number(MCP_API_PORT));
}

export default { startMCPServer, stopMCPServer };
