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
import * as cp from 'child_process';
import * as path from 'path';
import { PromptRouter, TaskType, PromptFragment, PromptFragmentType, PromptPriority } from '../../domain/prompt_engine/mod';
import { WorkingMemory, SessionMemory, PersistentMemory, KGStorage, MemorySource } from '../../domain/memory/mod';

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
// 认证缓存 + 暴力破解防护
// ============================================

interface AuthResult {
  valid: boolean;
  cachedAt: number;
}

// 认证缓存：key -> AuthResult
const authCache = new Map<string, AuthResult>();
const AUTH_CACHE_MAX_SIZE = 1000;

// 暴力破解防护：追踪每个 IP 的失败尝试次数
const AUTH_RATE_LIMIT_WINDOW_MS = 15 * 60 * 1000; // 15分钟窗口
const AUTH_MAX_FAILURES_PER_WINDOW = 10;           // 窗口内最多失败10次
const AUTH_LOCKOUT_MS = 5 * 60 * 1000;            // 锁定5分钟

interface RateLimitEntry {
  failures: number;
  firstFailureAt: number;
  lockedUntil: number | null;
}

const authRateLimit = new Map<string, RateLimitEntry>();

function getClientIP(req: http.IncomingMessage): string {
  // 优先从 X-Forwarded-For 获取（反向代理场景）
  const forwarded = req.headers['x-forwarded-for'];
  if (forwarded) {
    const ips = Array.isArray(forwarded) ? forwarded[0] : forwarded;
    return ips.split(',')[0].trim();
  }
  // 回退到 socket 地址
  const addr = req.socket?.remoteAddress || 'unknown';
  // 移除 IPv6 前缀
  return addr.replace(/^::ffff:/, '');
}

function isRateLimited(clientIP: string): boolean {
  const entry = authRateLimit.get(clientIP);
  if (!entry) return false;

  const now = Date.now();

  // 如果在锁定期间
  if (entry.lockedUntil && now < entry.lockedUntil) {
    return true;
  }

  // 窗口过期，重置计数
  if (now - entry.firstFailureAt > AUTH_RATE_LIMIT_WINDOW_MS) {
    authRateLimit.delete(clientIP);
    return false;
  }

  return false;
}

function recordAuthFailure(clientIP: string): void {
  const now = Date.now();
  let entry = authRateLimit.get(clientIP);

  if (!entry || now - entry.firstFailureAt > AUTH_RATE_LIMIT_WINDOW_MS) {
    // 新窗口
    entry = { failures: 0, firstFailureAt: now, lockedUntil: null };
  }

  entry.failures++;

  // 达到阈值，触发锁定
  if (entry.failures >= AUTH_MAX_FAILURES_PER_WINDOW) {
    entry.lockedUntil = now + AUTH_LOCKOUT_MS;
    console.warn(`[MCP-Server] Auth rate limit exceeded for IP: ${clientIP}, locked until ${new Date(entry.lockedUntil).toISOString()}`);
  }

  authRateLimit.set(clientIP, entry);
}

function recordAuthSuccess(clientIP: string): void {
  // 成功后清除该 IP 的失败记录
  authRateLimit.delete(clientIP);
}

function validateApiKey(key: string, clientIP: string = 'unknown'): boolean {
  // SECURITY: 首先检查是否被速率限制锁定
  if (isRateLimited(clientIP)) {
    console.warn(`[MCP-Server] Rejected auth attempt from rate-limited IP: ${clientIP}`);
    return false;
  }

  // SECURITY: 如果缓存超过最大限制，清除最旧的条目
  if (authCache.size >= AUTH_CACHE_MAX_SIZE) {
    const firstKey = authCache.keys().next().value;
    if (firstKey) authCache.delete(firstKey);
  }

  // 检查缓存
  const cached = authCache.get(key);
  if (cached && Date.now() - cached.cachedAt < AUTH_CACHE_TTL_MS) {
    // 从缓存命中时也清除失败记录（用户可能之前输错，现在终于对了）
    recordAuthSuccess(clientIP);
    return cached.valid;
  }

  // 验证API Key
  const valid = key === API_KEY;

  // 更新缓存
  authCache.set(key, { valid, cachedAt: Date.now() });

  if (!valid) {
    recordAuthFailure(clientIP);
  } else {
    recordAuthSuccess(clientIP);
  }

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
// Python 子进程调用辅助函数
// ============================================

function callPythonScript(scriptName: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(process.cwd(), 'src', 'infrastructure', scriptName);
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    cp.execFile(pythonCmd, [scriptPath, ...args], { encoding: 'utf-8' }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(`${scriptName} failed: ${error.message}`));
        return;
      }
      if (stderr) {
        console.warn(`[${scriptName}] stderr: ${stderr}`);
      }
      resolve(stdout.trim());
    });
  });
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
  try {
    const args = ['query'];
    if (params.category) args.push('--category', params.category);
    if (params.minQuality !== undefined) args.push('--min-quality', String(params.minQuality));
    if (params.limit) args.push('--limit', String(params.limit));

    const output = await callPythonScript('asset_indexer.py', args);
    const assets = JSON.parse(output);
    return { assets, count: assets.length };
  } catch (error) {
    return { assets: [], count: 0, error: error instanceof Error ? error.message : 'Query failed' };
  }
}

// ============================================
// M07: 资产详情 API (通过SQLite直接访问)
// ============================================

async function handleAssetGet(params: { assetId: string }): Promise<any> {
  try {
    const output = await callPythonScript('asset_indexer.py', ['get', '--id', params.assetId]);
    const asset = JSON.parse(output);
    if (!asset) return { error: 'Asset not found', asset_id: params.assetId };
    return asset;
  } catch (error) {
    return { error: error instanceof Error ? error.message : 'Get failed', asset_id: params.assetId };
  }
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
  try {
    const args = ['create', '--name', params.name, '--type', params.category, '--content', params.content];
    if (params.qualityScore !== undefined) args.push('--quality', String(params.qualityScore));

    const output = await callPythonScript('asset_indexer.py', args);
    const result = JSON.parse(output);
    return result;
  } catch (error) {
    return { success: false, message: error instanceof Error ? error.message : 'Create failed' };
  }
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
    const clientIP = getClientIP(req);
    const token = extractAuthToken(req);
    if (!token || !validateApiKey(token, clientIP)) {
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
        ],
      });
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

// ESM方式检测是否直接运行
const isMainModule = import.meta.url === `file://${process.argv[1]}`;

if (isMainModule) {
  startMCPServer(Number(MCP_API_PORT));
}

export default { startMCPServer, stopMCPServer };
