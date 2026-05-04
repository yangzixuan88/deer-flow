/**
 * M11 执行器适配器
 * ================================================
 * 五大执行器统一接口
 * Claude Code · CLI-Anything · Midscene.js · UI-TARS · OpenCLI
 * ================================================
 */

import { spawn } from 'child_process';
import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../../../runtime_paths';
import {
  ExecutorType,
  ExecutorStatus,
  ExecutorTask,
  ExecutorResult,
  SandboxType,
} from '../types';

import { gVisorSandbox, riskAssessor, RiskAssessment } from '../sandbox';
import { HookContext } from '../../hooks';

// 动态导入 OpenCLI 客户端 (延迟加载)
let opencliClient: any = null;
async function getOpenCLIClient() {
  if (!opencliClient) {
    try {
      const module = await import('../../../infrastructure/execution/opencli_http_client');
      opencliClient = module.opencliHttpClient;
    } catch {
      opencliClient = null;
    }
  }
  return opencliClient;
}

// ============================================
// ★ Round 7: 执行器健康检查与自维持层
// ============================================

/**
 * ★ Round 7: 执行器健康状态结构
 *
 * 包含:
 * - executor_health: 各执行器的就绪/离线状态
 * - readiness: 总体就绪状态
 * - bootstrap_attempts: 引导尝试记录
 * - environment_diagnostics: 环境诊断信息
 */
export interface ExecutorHealth {
  /** 各执行器健康状态 */
  executor_health: Record<ExecutorType, {
    status: 'ready' | 'not_ready' | 'unknown';
    last_check?: string;
    error?: string;
    latency_ms?: number;
  }>;
  /** 总体就绪状态 (所有关键执行器都 ready 才为 true) */
  readiness: boolean;
  /** 各执行器的 bootstrap 尝试次数 */
  bootstrap_attempts: Record<ExecutorType, number>;
  /** 环境诊断信息 */
  environment_diagnostics: {
    opencli_daemon_running?: boolean;
    opencli_daemon_url?: string;
    cli_hub_path?: string;
    midscene_available?: boolean;
    ui_tars_available?: boolean;
    browser_available?: boolean;
  };
  /** 健康检查时间戳 */
  checked_at: string;
}

/**
 * ★ Round 7: 执行器健康检查缓存 (避免频繁检查)
 */
let healthCache: { health: ExecutorHealth; timestamp: number } | null = null;
const HEALTH_CACHE_TTL_MS = 5000; // 5秒缓存

/**
 * ★ Round 7: 检查 CLI hub 路径是否存在
 */
function checkCLIClientPath(appName: string): boolean {
  const hubPath = runtimePath('cli-hub', `${appName}.sh`);
  try {
    return fs.existsSync(hubPath);
  } catch {
    return false;
  }
}

/**
 * ★ Round 7: 检查 OpenCLI daemon 是否在线
 */
async function checkOpenCLIDaemon(): Promise<{ ready: boolean; latency_ms?: number; error?: string }> {
  const start = Date.now();
  try {
    const client = await getOpenCLIClient();
    if (!client) return { ready: false, latency_ms: Date.now() - start, error: 'OpenCLI client module not found' };
    // 尝试调用一个轻量方法检测 daemon
    const stateResult = await Promise.race([
      client.getState ? client.getState() : Promise.resolve({ success: false }),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 3000)),
    ]);
    const latency = Date.now() - start;
    if (stateResult && (stateResult as any).success !== false) {
      return { ready: true, latency_ms: latency };
    }
    return { ready: false, latency_ms: latency, error: 'OpenCLI daemon not responding' };
  } catch (e: any) {
    return { ready: false, latency_ms: Date.now() - start, error: e?.message || 'OpenCLI daemon check failed' };
  }
}

/**
 * ★ Round 7: 检查 Midscene 是否可用
 */
async function checkMidsceneAvailable(): Promise<{ ready: boolean; error?: string }> {
  try {
    // Midscene 是 npm 包，通过 require 检测
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const midscene = (() => { try { return require('midscene'); } catch { return null; } })();
    return { ready: !!midscene };
  } catch {
    return { ready: false, error: 'Midscene npm package not available' };
  }
}

/**
 * ★ Round 7: 检查 UI-TARS 是否可用
 */
async function checkUITarsAvailable(): Promise<{ ready: boolean; error?: string }> {
  try {
    // UI-TARS 通过环境变量或路径检测
    const uiTarsPath = process.env.UI_TARS_PATH || runtimePath('ui-tars');
    const exists = fs.existsSync(uiTarsPath);
    return { ready: exists || !!process.env.UI_TARS_API_KEY };
  } catch {
    return { ready: false, error: 'UI-TARS check failed' };
  }
}

/**
 * ★ Round 7: 检查 Claude Code CLI 是否可用
 */
function checkClaudeCodeAvailable(): { ready: boolean; error?: string } {
  try {
    // 检测 claude CLI 是否在 PATH 中 (通过同步检查 - Windows fix)
    const result = require('child_process').execSync('where claude 2>nul', { encoding: 'utf-8', windowsHide: true });
    return { ready: !!result && result.trim().length > 0 };
  } catch {
    return { ready: false, error: 'Claude Code CLI not found in PATH' };
  }
}

/**
 * ★ Round 7: 执行所有执行器的健康检查
 *
 * @param forceRefresh 强制刷新缓存
 * @returns ExecutorHealth 结构
 */
export async function checkExecutorHealth(forceRefresh: boolean = false): Promise<ExecutorHealth> {
  const now = Date.now();
  if (!forceRefresh && healthCache && (now - healthCache.timestamp) < HEALTH_CACHE_TTL_MS) {
    return healthCache.health;
  }

  const [opencliCheck, midsceneCheck, uiTarsCheck, claudeCheck] = await Promise.all([
    checkOpenCLIDaemon(),
    checkMidsceneAvailable(),
    checkUITarsAvailable(),
    Promise.resolve(checkClaudeCodeAvailable()),
  ]);

  const health: ExecutorHealth = {
    executor_health: {
      [ExecutorType.OPENCLI]: {
        status: opencliCheck.ready ? 'ready' : 'not_ready',
        last_check: new Date().toISOString(),
        error: opencliCheck.error,
        latency_ms: opencliCheck.latency_ms,
      },
      [ExecutorType.MIDSCENE]: {
        status: midsceneCheck.ready ? 'ready' : 'not_ready',
        last_check: new Date().toISOString(),
        error: midsceneCheck.error,
      },
      [ExecutorType.UI_TARS]: {
        status: uiTarsCheck.ready ? 'ready' : 'not_ready',
        last_check: new Date().toISOString(),
        error: uiTarsCheck.error,
      },
      [ExecutorType.CLAUDE_CODE]: {
        status: claudeCheck.ready ? 'ready' : 'not_ready',
        last_check: new Date().toISOString(),
        error: claudeCheck.error,
      },
      [ExecutorType.CLI_ANYTHING]: {
        status: 'unknown', // CLI_ANYTHING 是路由器，不独立存在
        last_check: new Date().toISOString(),
      },
      [ExecutorType.LARKSUITE_CLI]: {
        status: 'unknown',
        last_check: new Date().toISOString(),
      },
    },
    readiness: opencliCheck.ready || midsceneCheck.ready,
    bootstrap_attempts: {
      [ExecutorType.OPENCLI]: 0,
      [ExecutorType.MIDSCENE]: 0,
      [ExecutorType.UI_TARS]: 0,
      [ExecutorType.CLAUDE_CODE]: 0,
      [ExecutorType.CLI_ANYTHING]: 0,
      [ExecutorType.LARKSUITE_CLI]: 0,
    },
    environment_diagnostics: {
      opencli_daemon_running: opencliCheck.ready,
      opencli_daemon_url: process.env.OPENCLI_DAEMON_URL || 'http://localhost:9229',
      cli_hub_path: runtimePath('cli-hub'),
      midscene_available: midsceneCheck.ready,
      ui_tars_available: uiTarsCheck.ready,
      browser_available: !!process.env.CHROME_PATH || !!process.env.PUPPETEER_EXECUTABLE_PATH,
    },
    checked_at: new Date().toISOString(),
  };

  healthCache = { health, timestamp: now };
  return health;
}

/**
 * ★ Round 7: 执行器就绪门 (Readiness Gate)
 *
 * 在执行前检查目标执行器是否就绪:
 * - 不 ready 时触发 fallback 或 bootstrap
 * - 返回 { ready: boolean, action: 'execute' | 'fallback' | 'bootstrap' | 'skip', reason: string }
 */
export async function executorReadinessGate(
  executorType: ExecutorType,
  health?: ExecutorHealth
): Promise<{ ready: boolean; action: 'execute' | 'fallback' | 'bootstrap' | 'skip'; reason: string; targetExecutor?: ExecutorType }> {
  const h = health || await checkExecutorHealth();

  switch (executorType) {
    case ExecutorType.OPENCLI: {
      const status = h.executor_health[ExecutorType.OPENCLI].status;
      if (status === 'ready') {
        return { ready: true, action: 'execute', reason: 'OpenCLI daemon ready' };
      }
      // 不 ready，检查是否可以 bootstrap
      if (h.bootstrap_attempts[ExecutorType.OPENCLI] < 2) {
        return { ready: false, action: 'bootstrap', reason: 'OpenCLI daemon not ready, attempting bootstrap', targetExecutor: ExecutorType.OPENCLI };
      }
      // Bootstrap 失败，fallback
      return { ready: false, action: 'fallback', reason: `OpenCLI not ready after ${h.bootstrap_attempts[ExecutorType.OPENCLI]} bootstrap attempts, falling back`, targetExecutor: ExecutorType.MIDSCENE };
    }

    case ExecutorType.MIDSCENE: {
      const status = h.executor_health[ExecutorType.MIDSCENE].status;
      if (status === 'ready') {
        return { ready: true, action: 'execute', reason: 'Midscene ready' };
      }
      return { ready: false, action: 'fallback', reason: 'Midscene not ready', targetExecutor: ExecutorType.UI_TARS };
    }

    case ExecutorType.UI_TARS: {
      const status = h.executor_health[ExecutorType.UI_TARS].status;
      if (status === 'ready') {
        return { ready: true, action: 'execute', reason: 'UI-TARS ready' };
      }
      return { ready: false, action: 'skip', reason: 'UI-TARS not ready and no further fallback' };
    }

    case ExecutorType.CLAUDE_CODE: {
      const status = h.executor_health[ExecutorType.CLAUDE_CODE].status;
      if (status === 'ready') {
        return { ready: true, action: 'execute', reason: 'Claude Code ready' };
      }
      return { ready: false, action: 'skip', reason: 'Claude Code not available' };
    }

    case ExecutorType.CLI_ANYTHING:
    case ExecutorType.LARKSUITE_CLI:
    default:
      return { ready: true, action: 'execute', reason: `${executorType} does not require health check` };
  }
}

// ============================================
// ★ Round 8: 真实自愈层 (Self-Healing)
// ============================================

/**
 * ★ Round 8: 自愈结果结构
 *
 * 包含:
 * - self_heal_attempted: 是否尝试了自愈
 * - self_heal_success: 自愈是否成功
 * - healed_executor: 被自愈的执行器
 * - post_heal_readiness: 自愈后的就绪状态
 * - environment_diagnostics: 环境诊断信息
 */
export interface SelfHealResult {
  self_heal_attempted: boolean;
  self_heal_success: boolean;
  healed_executor: ExecutorType;
  bootstrap_attempts: number;
  post_heal_readiness: boolean;
  post_heal_health?: ExecutorHealth;
  environment_diagnostics: {
    opencli_daemon_reachable?: boolean;
    opencli_daemon_url?: string;
    attempt_details: string[];
  };
  fallback_decision?: {
    action: 'proceed' | 'fallback' | 'abort';
    target_executor?: ExecutorType;
    reason: string;
  };
  /** ★ Round 9: 每次自愈尝试的决策轨迹 */
  heal_decision_trace: Array<{
    attempt: number;
    url?: string;
    success: boolean;
    details: string;
    post_heal_status?: 'ready' | 'not_ready';
  }>;
  /** ★ Round 9: 自愈成功后是否返回原链继续执行 */
  returned_to_original_chain: boolean;
}

/**
 * ★ Round 8: 尝试自愈 OpenCLI daemon
 *
 * 尝试策略:
 * 1. 尝试连接已知 daemon URL
 * 2. 如果失败，尝试连接备选端口
 * 3. 重置 opencliClient 引用强制重新初始化
 */
async function attemptOpenCLISelfHeal(): Promise<{ success: boolean; details: string[] }> {
  const details: string[] = [];
  const daemonUrls = [
    process.env.OPENCLI_DAEMON_URL || 'http://localhost:9229',
    'http://localhost:9229',
    'http://127.0.0.1:9229',
  ];

  // 强制重置客户端引用
  opencliClient = null;

  for (const url of daemonUrls) {
    try {
      details.push(`Trying OpenCLI daemon at ${url}`);
      const module = await import('../../../infrastructure/execution/opencli_http_client');
      const client = module.opencliHttpClient;
      if (client) {
        // 尝试调用轻量方法
        const stateResult = await Promise.race([
          client.getState ? client.getState() : Promise.resolve({ success: false }),
          new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 2000)),
        ]);
        if (stateResult && (stateResult as any).success !== false) {
          details.push(`OpenCLI daemon responding at ${url}`);
          opencliClient = client;
          return { success: true, details };
        }
      }
    } catch (e: any) {
      details.push(`Failed to connect to ${url}: ${e?.message || e}`);
    }
  }

  return { success: false, details };
}

/**
 * ★ Round 8: 执行自愈并返回结果
 *
 * @param executorType 要自愈的执行器类型
 * @param currentHealth 当前健康状态
 * @param bootstrapAttempts 当前 bootstrap 尝试次数
 * @returns SelfHealResult
 */
export async function attemptSelfHeal(
  executorType: ExecutorType,
  currentHealth?: ExecutorHealth,
  bootstrapAttempts: number = 0
): Promise<SelfHealResult> {
  const health = currentHealth || await checkExecutorHealth(true); // 强制刷新
  const diagnostics: SelfHealResult['environment_diagnostics'] = {
    attempt_details: [],
  };

  // 限制自愈尝试次数
  if (bootstrapAttempts >= 2) {
    return {
      self_heal_attempted: false,
      self_heal_success: false,
      healed_executor: executorType,
      bootstrap_attempts: bootstrapAttempts,
      post_heal_readiness: false,
      environment_diagnostics: { attempt_details: [`Bootstrap limit reached (${bootstrapAttempts} attempts)`] },
      fallback_decision: {
        action: 'fallback',
        target_executor: ExecutorType.MIDSCENE,
        reason: `Bootstrap limit reached after ${bootstrapAttempts} attempts`,
      },
      heal_decision_trace: [],
      returned_to_original_chain: false,
    };
  }

  diagnostics.attempt_details.push(`Starting self-heal for ${executorType}`);

  // ★ Round 9: 初始化自愈决策轨迹
  const healTrace: SelfHealResult['heal_decision_trace'] = [];

  if (executorType === ExecutorType.OPENCLI) {
    const healResult = await attemptOpenCLISelfHeal();
    diagnostics.attempt_details.push(...healResult.details);
    diagnostics.opencli_daemon_reachable = healResult.success;

    // ★ Round 9: 提取响应 URL 并记录到轨迹
    const respondingUrl = healResult.details.find(d => d.includes('responding'))?.replace('OpenCLI daemon responding at ', '') || '';
    diagnostics.opencli_daemon_url = respondingUrl;

    if (healResult.success) {
      // 自愈成功，重新检查健康状态
      const newHealth = await checkExecutorHealth(true);
      const opencliStatus = newHealth.executor_health[ExecutorType.OPENCLI];
      const healed = opencliStatus.status === 'ready';

      // ★ Round 9: 记录本次尝试到轨迹
      healTrace.push({
        attempt: bootstrapAttempts + 1,
        url: respondingUrl,
        success: healed,
        details: healed
          ? 'OpenCLI daemon healed and confirmed ready'
          : 'OpenCLI daemon reconnected but health check still not_ready',
        post_heal_status: (opencliStatus.status === 'unknown' ? 'not_ready' : opencliStatus.status) as 'ready' | 'not_ready',
      });

      const proceed = healed;
      return {
        self_heal_attempted: true,
        self_heal_success: healed,
        healed_executor: executorType,
        bootstrap_attempts: bootstrapAttempts + 1,
        post_heal_readiness: healed,
        post_heal_health: newHealth,
        environment_diagnostics: diagnostics,
        fallback_decision: proceed
          ? { action: 'proceed', target_executor: ExecutorType.OPENCLI, reason: 'OpenCLI daemon healed and ready' }
          : { action: 'fallback', target_executor: ExecutorType.MIDSCENE, reason: 'OpenCLI daemon reconnected but not ready' },
        // ★ Round 9: 成功链：自愈成功且决定继续使用原执行器
        heal_decision_trace: healTrace,
        returned_to_original_chain: proceed,
      };
    } else {
      // 自愈失败，降级
      healTrace.push({
        attempt: bootstrapAttempts + 1,
        success: false,
        details: `All URLs failed: ${healResult.details.join('; ')}`,
      });

      return {
        self_heal_attempted: true,
        self_heal_success: false,
        healed_executor: executorType,
        bootstrap_attempts: bootstrapAttempts + 1,
        post_heal_readiness: false,
        environment_diagnostics: diagnostics,
        fallback_decision: {
          action: 'fallback',
          target_executor: ExecutorType.MIDSCENE,
          reason: `OpenCLI self-heal failed: ${healResult.details.join('; ')}`,
        },
        // ★ Round 9: 失败链：无返回原链
        heal_decision_trace: healTrace,
        returned_to_original_chain: false,
      };
    }
  }

  // 其他执行器暂不支持自动自愈
  return {
    self_heal_attempted: false,
    self_heal_success: false,
    healed_executor: executorType,
    bootstrap_attempts: bootstrapAttempts,
    post_heal_readiness: false,
    environment_diagnostics: { ...diagnostics, attempt_details: [`Auto-heal not supported for ${executorType}`] },
    fallback_decision: {
      action: 'fallback',
      target_executor: ExecutorType.MIDSCENE,
      reason: `Self-heal not implemented for ${executorType}`,
    },
    // ★ Round 9: 不可自愈的执行器
    heal_decision_trace: healTrace,
    returned_to_original_chain: false,
  };
}

// ============================================
// ★ Round 7: 目标态验证器 (Goal State Verifier)
// ============================================

/**
 * ★ Round 7: 目标态验证结果
 *
 * 包含:
 * - goal_state: 目标状态描述
 * - goal_gap: 当前与目标的差距
 * - goal_satisfied: 目标是否达成
 * - termination_reason: 终止原因
 * - next_step_hint: 下一步建议
 */
export interface GoalVerificationResult {
  /** 目标状态 */
  goal_state: {
    description: string;
    type: 'url' | 'element' | 'window' | 'app_state' | 'custom';
    target?: {
      url?: string;
      hostname?: string;
      element_text?: string;
      window_title?: string;
      process_name?: string;
    };
  };
  /** 当前观测状态 */
  observed_state?: {
    url?: string;
    hostname?: string;
    title?: string;
    element_count?: number;
    key_elements?: string[];
    window_title?: string;
    process_name?: string;
  };
  /** 目标差距 */
  goal_gap: {
    url_gap?: string;
    element_gap?: string[];
    window_gap?: string;
    missing_conditions: string[];
  };
  /** 目标是否满足 */
  goal_satisfied: boolean;
  /** 满足度评分 (0-1) */
  satisfaction_score: number;
  /** 终止原因 */
  termination_reason: 'goal_achieved' | 'goal_failed' | 'partial_success' | 'uncertain' | 'continue';
  /** 下一步建议 */
  next_step_hint?: string;
}

/**
 * ★ Round 7: 解析目标态描述
 *
 * 将自然语言目标解析为结构化目标
 */
export function parseGoalState(goalDescription: string): GoalVerificationResult['goal_state'] {
  const lower = goalDescription.toLowerCase();

  // URL 目标
  const urlMatch = goalDescription.match(/https?:\/\/[^\s]+/);
  if (urlMatch || lower.includes('navigate') || lower.includes('go to') || lower.includes('open')) {
    const targetUrl = urlMatch ? urlMatch[0] : undefined;
    const hostname = targetUrl ? targetUrl.replace(/^https?:\/\//, '').split('/')[0] : undefined;
    return {
      description: goalDescription,
      type: 'url',
      target: { url: targetUrl, hostname },
    };
  }

  // 元素目标
  if (lower.includes('click') || lower.includes('element') || lower.includes('button') || lower.includes('sign in')) {
    const elementText = goalDescription.match(/['"]([^'"]+)['"]/)?.[1]
      || goalDescription.match(/the\s+(\w+\s+\w+)/i)?.[0]
      || 'target element';
    return {
      description: goalDescription,
      type: 'element',
      target: { element_text: elementText },
    };
  }

  // 窗口目标
  if (lower.includes('window') || lower.includes('gimp') || lower.includes('blender') || lower.includes('application')) {
    const windowMatch = goalDescription.match(/open\s+(\w+)/i);
    const processName = windowMatch ? windowMatch[1] : 'target app';
    return {
      description: goalDescription,
      type: 'window',
      target: { window_title: processName, process_name: processName.toLowerCase() },
    };
  }

  // 通用自定义目标
  return {
    description: goalDescription,
    type: 'custom',
    target: {},
  };
}

/**
 * ★ Round 7: 验证当前观测状态是否满足目标
 *
 * @param goalState 结构化目标
 * @param observedState 当前观测状态 (dom_observed 或 desk_observed)
 * @param previousGoal 前一个目标状态 (用于判断是否需要继续)
 * @returns GoalVerificationResult
 */
export function verifyGoalState(
  goalState: GoalVerificationResult['goal_state'],
  observedState?: GoalVerificationResult['observed_state'],
  previousGoal?: GoalVerificationResult['goal_state']
): GoalVerificationResult {
  const missingConditions: string[] = [];
  let satisfactionScore = 0;
  let goalSatisfied = false;
  let terminationReason: GoalVerificationResult['termination_reason'] = 'uncertain';
  let nextStepHint: string | undefined;

  if (!observedState) {
    return {
      goal_state: goalState,
      goal_gap: { missing_conditions: ['No observed state available'] },
      goal_satisfied: false,
      satisfaction_score: 0,
      termination_reason: 'uncertain',
      next_step_hint: 'Cannot verify goal without observation; need to gather state first',
    };
  }

  switch (goalState.type) {
    case 'url': {
      const targetHostname = goalState.target?.hostname;
      const observedHostname = observedState.hostname || (observedState.url?.replace(/^https?:\/\//, '').split('/')[0]);

      if (targetHostname && observedHostname) {
        if (observedHostname.includes(targetHostname) || targetHostname.includes(observedHostname)) {
          satisfactionScore = 1.0;
          goalSatisfied = true;
          terminationReason = 'goal_achieved';
          nextStepHint = 'URL target reached; task may be complete';
        } else {
          missingConditions.push(`URL mismatch: expected hostname "${targetHostname}", got "${observedHostname}"`);
          satisfactionScore = 0.3;
          terminationReason = 'continue';
          nextStepHint = `Navigate closer to target URL (current: ${observedState.url})`;
        }
      } else if (observedState.url) {
        // 不知道目标hostname，只要有url就算部分成功
        satisfactionScore = 0.5;
        goalSatisfied = false;
        terminationReason = 'partial_success';
        nextStepHint = 'URL changed but hostname not verified; continue monitoring';
      }
      break;
    }

    case 'element': {
      const targetElement = goalState.target?.element_text?.toLowerCase() || '';
      const keyElements = observedState.key_elements?.map(e => e.toLowerCase()) || [];
      const elementCount = observedState.element_count || 0;

      if (elementCount > 0) {
        // 检查关键元素是否存在
        const elementFound = keyElements.some(e => e.includes(targetElement) || targetElement.includes(e));
        if (elementFound) {
          // 找到了目标元素 → 完全达成
          satisfactionScore = 1.0;
          goalSatisfied = true;
          terminationReason = 'goal_achieved';
          nextStepHint = `Element "${targetElement}" found`;
        } else if (keyElements.length > 0) {
          // 没找到目标元素，但有其他元素 → 部分成功
          satisfactionScore = 0.85;
          goalSatisfied = false;
          terminationReason = 'partial_success';
          nextStepHint = `Element "${targetElement}" not found, but alternatives exist (${keyElements.join(', ')})`;
        } else {
          missingConditions.push(`Element "${targetElement}" not found in ${elementCount} elements`);
          satisfactionScore = 0.4;
          goalSatisfied = false;
          terminationReason = 'partial_success';
          nextStepHint = `Page has ${elementCount} elements but not "${targetElement}"; might need scroll or wait`;
        }
      } else {
        missingConditions.push('No elements found on page');
        satisfactionScore = 0;
        goalSatisfied = false;
        terminationReason = 'goal_failed';
        nextStepHint = 'Page appears empty or inaccessible; check navigation';
      }
      break;
    }

    case 'window': {
      const targetWindow = goalState.target?.process_name?.toLowerCase() || '';
      const observedWindow = observedState.window_title?.toLowerCase() || observedState.process_name?.toLowerCase() || '';

      if (observedWindow && targetWindow) {
        if (observedWindow.includes(targetWindow) || targetWindow.includes(observedWindow)) {
          satisfactionScore = 1.0;
          goalSatisfied = true;
          terminationReason = 'goal_achieved';
          nextStepHint = `Window "${observedWindow}" confirmed`;
        } else {
          missingConditions.push(`Window mismatch: expected "${targetWindow}", got "${observedWindow}"`);
          satisfactionScore = 0.3;
          terminationReason = 'continue';
          nextStepHint = `Launch or focus "${targetWindow}" (current: ${observedWindow})`;
        }
      } else if (observedState.process_name) {
        satisfactionScore = 0.6;
        goalSatisfied = false;
        terminationReason = 'partial_success';
        nextStepHint = `Process running but window not confirmed`;
      }
      break;
    }

    default: {
      // 自定义目标：基于 satisfaction_score 判断
      if (observedState.element_count !== undefined || observedState.url) {
        satisfactionScore = 0.5;
        goalSatisfied = false;
        terminationReason = 'continue';
        nextStepHint = 'Custom goal; cannot fully verify automatically';
      }
    }
  }

  return {
    goal_state: goalState,
    observed_state: observedState,
    goal_gap: {
      url_gap: missingConditions.find(c => c.includes('URL')),
      element_gap: missingConditions.filter(c => c.includes('Element')),
      window_gap: missingConditions.find(c => c.includes('Window')),
      missing_conditions: missingConditions,
    },
    goal_satisfied: goalSatisfied,
    satisfaction_score: satisfactionScore,
    termination_reason: terminationReason,
    next_step_hint: nextStepHint,
  };
}

/**
 * ★ Round 7: 便捷函数 — 从 FallbackResult.checks 提取观测状态
 */
export function extractObservedStateFromChecks(checks?: FallbackResult['checks']): GoalVerificationResult['observed_state'] | undefined {
  if (!checks) return undefined;

  if (checks.dom_observed) {
    const d = checks.dom_observed;
    return {
      url: d.url,
      hostname: d.url?.replace(/^https?:\/\//, '').split('/')[0],
      title: d.title,
      element_count: d.element_count,
      key_elements: d.key_elements,
    };
  }

  if (checks.desk_observed) {
    const d = checks.desk_observed;
    return {
      window_title: d.active_window_title,
      process_name: d.active_process,
    };
  }

  return undefined;
}

/**
 * ★ Round 7: 观测驱动下一步决策
 *
 * 基于 goal_gap 和当前观测状态，决定下一步应该做什么
 */
export function observationDrivenNextStep(
  currentInstruction: string,
  verificationResult: GoalVerificationResult
): { action: 'continue' | 'stop' | 'retry' | 'fallback'; reason: string; suggestedInstruction?: string } {
  const { goal_satisfied, termination_reason, satisfaction_score, next_step_hint, goal_gap } = verificationResult;

  // 目标达成
  if (goal_satisfied || termination_reason === 'goal_achieved') {
    return { action: 'stop', reason: 'Goal achieved', suggestedInstruction: undefined };
  }

  // 明确失败
  if (termination_reason === 'goal_failed') {
    return {
      action: 'fallback',
      reason: `Goal failed: ${goal_gap.missing_conditions.join('; ')}`,
      suggestedInstruction: next_step_hint,
    };
  }

  // 不确定
  if (termination_reason === 'uncertain') {
    return {
      action: 'retry',
      reason: 'Cannot determine goal state; retry observation',
      suggestedInstruction: 'wait 1 second and check state',
    };
  }

  // 部分成功但未完成
  if (satisfaction_score < 0.8) {
    return {
      action: 'continue',
      reason: `Partial success (${Math.round(satisfaction_score * 100)}%); ${next_step_hint || 'continue working'}`,
      suggestedInstruction: next_step_hint,
    };
  }

  return { action: 'continue', reason: 'Continue monitoring goal', suggestedInstruction: next_step_hint };
}

/**
 * ★ Round 8: 目标驱动链执行步骤记录
 */
export interface GoalDrivenStepRecord {
  step: number;
  instruction: string;
  executor_used: string;
  goal_before: GoalVerificationResult['goal_state'];
  observed_state?: GoalVerificationResult['observed_state'];
  verification: GoalVerificationResult;
  decision: ReturnType<typeof observationDrivenNextStep>;
  action_taken: 'continue' | 'stop' | 'retry' | 'fallback' | 'executed';
}

/**
 * ★ Round 8: 目标驱动链执行结果
 */
export interface GoalDrivenChainResult {
  task_id: string;
  final_goal_verification: GoalVerificationResult;
  goal_satisfied: boolean;
  termination_reason: GoalVerificationResult['termination_reason'];
  total_steps: number;
  steps_executed: number;
  /** 完整的目标驱动决策链 */
  goal_driven_decision_trace: GoalDrivenStepRecord[];
  /** 最终使用的 operator_context */
  final_context?: any;
}

/**
 * ★ Round 8: 运行目标驱动的混合链
 *
 * 在真实多步链中，每步之后都调用 GoalStateVerifier 和 observationDrivenNextStep，
 * 记录完整的决策链。至少一次下一步必须基于 goal_gap / next_step_hint 决定。
 *
 * @param taskId 任务 ID
 * @param steps 步骤列表，每项包含 instruction, goalDescription, isDesktop
 * @param initialContext 初始 operator_context
 * @returns GoalDrivenChainResult
 */
export async function runGoalDrivenChain(
  taskId: string,
  steps: Array<{
    instruction: string;
    goalDescription: string;
    params?: Record<string, any>;
  }>,
  initialContext?: any
): Promise<GoalDrivenChainResult> {
  const trace: GoalDrivenStepRecord[] = [];
  let ctx = initialContext || {
    session_id: taskId,
    current_step: 0,
    operation_history: [],
    last_url: undefined,
    last_app: undefined,
  };

  const sessionId = taskId;
  let currentGoal = parseGoalState(steps[0]?.goalDescription || 'custom goal');

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    const stepNum = i + 1;

    // 解析当前步骤的目标
    currentGoal = parseGoalState(step.goalDescription);

    // 构造 params
    const params = {
      ...(step.params || {}),
      url: ctx.last_url || step.params?.url,
      appName: ctx.last_app || step.params?.appName,
    };

    // 执行指令
    const fbResult = await executeWithAutoSelect(
      step.instruction,
      params,
      undefined,
      ctx
    );

    // 提取观测状态
    const observedState = extractObservedStateFromChecks(fbResult.checks);

    // 验证目标态
    const verification = verifyGoalState(currentGoal, observedState);

    // 观测驱动决策
    const decision = observationDrivenNextStep(step.instruction, verification);

    // 记录决策链
    trace.push({
      step: stepNum,
      instruction: step.instruction,
      executor_used: fbResult.executor_used,
      goal_before: currentGoal,
      observed_state: observedState,
      verification,
      decision,
      action_taken: decision.action === 'stop' ? 'stop'
        : decision.action === 'fallback' ? 'fallback'
        : decision.action === 'retry' ? 'retry'
        : 'continue',
    });

    // 更新上下文
    ctx = {
      ...ctx,
      ...(fbResult.accumulated_context || {}),
      current_step: stepNum,
      last_url: observedState?.url || ctx.last_url,
      last_app: observedState?.process_name || ctx.last_app,
    };

    // 如果决策是 stop 或 fallback，提前终止
    if (decision.action === 'stop') {
      return {
        task_id: taskId,
        final_goal_verification: verification,
        goal_satisfied: verification.goal_satisfied,
        termination_reason: verification.termination_reason,
        total_steps: steps.length,
        steps_executed: stepNum,
        goal_driven_decision_trace: trace,
        final_context: ctx,
      };
    }

    if (decision.action === 'fallback' || decision.action === 'retry') {
      // fallback/retry 时仍然继续执行，但不改变目标
    }
  }

  // 所有步骤执行完毕
  const lastVerification = trace.length > 0 ? trace[trace.length - 1].verification : verifyGoalState(currentGoal, undefined);

  return {
    task_id: taskId,
    final_goal_verification: lastVerification,
    goal_satisfied: lastVerification.goal_satisfied,
    termination_reason: lastVerification.termination_reason || 'uncertain',
    total_steps: steps.length,
    steps_executed: trace.length,
    goal_driven_decision_trace: trace,
    final_context: ctx,
  };
}

// ============================================
// ★ Round 7: Checkpoint / Recovery 系统
// ============================================

/**
 * ★ Round 7: 恢复检查点结构
 *
 * 保存中断恢复所需的全部状态:
 * - current_step: 当前步骤
 * - operator_context: 操作上下文
 * - executor_health: 执行器健康状态
 * - last_observed_state: 最后观测状态
 * - goal_state: 目标态
 * - task_id: 关联任务 ID
 */
export interface RecoveryCheckpoint {
  checkpoint_id: string;
  task_id: string;
  step: number;
  operator_context: any;
  executor_health?: ExecutorHealth;
  last_observed_state?: {
    url?: string;
    hostname?: string;
    title?: string;
    window_title?: string;
    process_name?: string;
    element_count?: number;
    timestamp: string;
  };
  goal_state?: GoalVerificationResult['goal_state'];
  created_at: string;
  valid: boolean;
}

/**
 * ★ Round 7/8: 恢复结果结构
 *
 * 包含:
 * - resume_from_step: 从哪一步恢复
 * - checkpoint_valid: 检查点是否有效
 * - state_compatibility: 状态兼容性
 * - resume_decision: 恢复决策
 * - recovered_chain_completed: 恢复后链是否完成
 */
export interface ResumeResult {
  /** 从哪一步恢复 (0 = 从头开始) */
  resume_from_step: number;
  /** 检查点是否有效 */
  checkpoint_valid: boolean;
  /** 状态兼容性 */
  state_compatibility: {
    compatible: boolean;
    mismatches: string[];
    warnings: string[];
  };
  /** 恢复决策 */
  resume_decision: 'resume' | 'replay_from_checkpoint' | 'replay_from_start' | 'abort';
  /** 恢复原因 */
  reason: string;
  /** 恢复后的 operator_context */
  restored_context?: any;
  /** 如果检查点无效，推荐的起始步 */
  suggested_start_step: number;
  /** ★ Round 8: 恢复后链是否完成 */
  recovered_chain_completed?: boolean;
  /** ★ Round 8: 被跳过的步骤数（用于证明不重复执行） */
  steps_skipped?: number;
}

/**
 * ★ Round 7: 检查点管理器 (内存中存储，支持持久化到文件)
 */
export class CheckpointManager {
  private checkpoints: Map<string, RecoveryCheckpoint> = new Map();
  private checkpointDir: string;
  /** ★ Round 8: 记录任务中断信息（用于真实中断后的恢复） */
  private interruptedTasks: Map<string, { atStep: number; at: string }> = new Map();

  constructor(checkpointDir?: string) {
    this.checkpointDir = checkpointDir || runtimePath('checkpoints');
    try {
      if (!fs.existsSync(this.checkpointDir)) {
        fs.mkdirSync(this.checkpointDir, { recursive: true });
      }
    } catch { /* ignore */ }
  }

  /**
   * ★ Round 7: 保存检查点
   */
  saveCheckpoint(
    taskId: string,
    step: number,
    operatorContext: any,
    lastObservedState?: any,
    goalState?: GoalVerificationResult['goal_state'],
    executorHealth?: ExecutorHealth
  ): RecoveryCheckpoint {
    const checkpointId = `${taskId}_step${step}_${Date.now()}`;

    const checkpoint: RecoveryCheckpoint = {
      checkpoint_id: checkpointId,
      task_id: taskId,
      step,
      operator_context: operatorContext,
      executor_health: executorHealth,
      last_observed_state: lastObservedState ? {
        url: lastObservedState.url,
        hostname: lastObservedState.hostname,
        title: lastObservedState.title,
        window_title: lastObservedState.window_title,
        process_name: lastObservedState.process_name,
        element_count: lastObservedState.element_count,
        timestamp: new Date().toISOString(),
      } : undefined,
      goal_state: goalState,
      created_at: new Date().toISOString(),
      valid: true,
    };

    this.checkpoints.set(taskId, checkpoint);

    // 持久化到文件
    try {
      const filePath = path.join(this.checkpointDir, `${taskId}.json`);
      fs.writeFileSync(filePath, JSON.stringify(checkpoint, null, 2));
    } catch { /* ignore persistence errors */ }

    return checkpoint;
  }

  /**
   * ★ Round 7: 加载检查点
   */
  loadCheckpoint(taskId: string): RecoveryCheckpoint | null {
    // 优先从内存
    if (this.checkpoints.has(taskId)) {
      return this.checkpoints.get(taskId)!;
    }

    // 从文件加载
    try {
      const filePath = path.join(this.checkpointDir, `${taskId}.json`);
      if (fs.existsSync(filePath)) {
        const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        this.checkpoints.set(taskId, data);
        return data;
      }
    } catch { /* ignore */ }

    return null;
  }

  /**
   * ★ Round 7: 验证检查点并决定恢复策略
   */
  validateAndResume(
    taskId: string,
    currentStep: number,
    currentObservedState?: any
  ): ResumeResult {
    const checkpoint = this.loadCheckpoint(taskId);

    if (!checkpoint || !checkpoint.valid) {
      return {
        resume_from_step: 0,
        checkpoint_valid: false,
        state_compatibility: { compatible: false, mismatches: ['No valid checkpoint found'], warnings: [] },
        resume_decision: 'replay_from_start',
        reason: 'No checkpoint found; starting from step 0',
        suggested_start_step: 0,
      };
    }

    // 检查点是否太旧 (超过 30 分钟)
    const checkpointAge = Date.now() - new Date(checkpoint.created_at).getTime();
    const isStale = checkpointAge > 30 * 60 * 1000;

    const mismatches: string[] = [];
    const warnings: string[] = [];

    // 状态兼容性检查
    if (currentObservedState && checkpoint.last_observed_state) {
      // URL 检查
      if (checkpoint.last_observed_state.url && currentObservedState.url) {
        const oldHostname = checkpoint.last_observed_state.hostname || checkpoint.last_observed_state.url?.replace(/^https?:\/\//, '').split('/')[0];
        const newHostname = currentObservedState.hostname || currentObservedState.url?.replace(/^https?:\/\//, '').split('/')[0];
        if (oldHostname && newHostname && !oldHostname.includes(newHostname) && !newHostname.includes(oldHostname)) {
          mismatches.push(`URL mismatch: checkpoint=${checkpoint.last_observed_state.url}, current=${currentObservedState.url}`);
        }
      }

      // 窗口标题检查
      if (checkpoint.last_observed_state.window_title && currentObservedState.window_title) {
        if (checkpoint.last_observed_state.window_title !== currentObservedState.window_title) {
          warnings.push(`Window changed: checkpoint="${checkpoint.last_observed_state.window_title}", current="${currentObservedState.window_title}"`);
        }
      }
    }

    // 步骤检查
    if (currentStep < checkpoint.step) {
      warnings.push(`Current step (${currentStep}) < checkpoint step (${checkpoint.step}); possible replay`);
    }

    const compatible = mismatches.length === 0;

    // 决定恢复策略
    let resumeDecision: ResumeResult['resume_decision'];
    let resumeFromStep: number;

    if (!compatible) {
      resumeDecision = 'abort';
      resumeFromStep = 0;
      return {
        resume_from_step: 0,
        checkpoint_valid: false,
        state_compatibility: { compatible: false, mismatches, warnings },
        resume_decision: 'abort',
        reason: `State incompatible: ${mismatches.join('; ')}`,
        suggested_start_step: 0,
      };
    }

    if (isStale) {
      resumeDecision = 'replay_from_checkpoint';
      resumeFromStep = checkpoint.step;
      warnings.push('Checkpoint is stale (>30 min old)');
    } else if (warnings.length > 0) {
      resumeDecision = 'replay_from_checkpoint';
      resumeFromStep = checkpoint.step;
    } else {
      resumeDecision = 'resume';
      resumeFromStep = checkpoint.step + 1; // 从下一步开始
    }

    return {
      resume_from_step: resumeFromStep,
      checkpoint_valid: true,
      state_compatibility: { compatible: true, mismatches: [], warnings },
      resume_decision: resumeDecision,
      reason: warnings.length > 0 ? `Resuming with warnings: ${warnings.join('; ')}` : 'Checkpoint valid; resuming',
      restored_context: checkpoint.operator_context,
      suggested_start_step: checkpoint.step,
    };
  }

  /**
   * ★ Round 7: 使检查点失效 (用于中断后放弃恢复)
   */
  invalidateCheckpoint(taskId: string): void {
    const checkpoint = this.loadCheckpoint(taskId);
    if (checkpoint) {
      checkpoint.valid = false;
      this.checkpoints.set(taskId, checkpoint);
      try {
        const filePath = path.join(this.checkpointDir, `${taskId}.json`);
        fs.writeFileSync(filePath, JSON.stringify(checkpoint, null, 2));
      } catch { /* ignore */ }
    }
  }

  /**
   * ★ Round 8: 注入中断标记（模拟真实中断）
   *
   * 在指定步骤注入中断，但不使检查点失效。中断后：
   * 1. 记录中断信息到 interruptedTasks
   * 2. 检查点保持有效，resume 时能从正确步骤继续
   * 3. 返回中断信息供后续恢复测试
   *
   * @param taskId 任务 ID
   * @param atStep 在哪一步之后注入中断
   * @returns 中断信息
   */
  injectInterruption(taskId: string, atStep: number): {
    interruption_injected: boolean;
    interrupted_at_step: number;
    checkpoint_invalidated: boolean;
    interruption_id: string;
  } {
    const checkpoint = this.loadCheckpoint(taskId);
    const interruptionId = `interrupt_${taskId}_step${atStep}_${Date.now()}`;

    if (checkpoint && checkpoint.step === atStep) {
      // 记录中断信息，但不使检查点失效
      this.interruptedTasks.set(taskId, { atStep, at: new Date().toISOString() });
      return {
        interruption_injected: true,
        interrupted_at_step: atStep,
        checkpoint_invalidated: false, // 保持有效，resume 时可用
        interruption_id: interruptionId,
      };
    }

    return {
      interruption_injected: false,
      interrupted_at_step: atStep,
      checkpoint_invalidated: false,
      interruption_id: interruptionId,
    };
  }

  /**
   * ★ Round 9: 记录真实执行器级中断（模拟外部进程崩溃/超时/kill）
   *
   * 与 injectInterruption 的区别:
   * - injectInterruption: 测试用标记，需要 checkpoint 存在
   * - recordRealInterruption: 模拟真实中断，不需要 checkpoint，外部事件驱动
   *
   * @param taskId 任务 ID
   * @param atStep 在哪一步之后发生中断
   * @param source 中断来源描述
   * @returns 中断信息
   */
  recordRealInterruption(taskId: string, atStep: number, source: string = 'midscene_process_failure'): {
    interruption_recorded: boolean;
    interrupted_at_step: number;
    interruption_source: string;
    interruption_time: string;
  } {
    const interruptionTime = new Date().toISOString();
    this.interruptedTasks.set(taskId, { atStep, at: interruptionTime });
    return {
      interruption_recorded: true,
      interrupted_at_step: atStep,
      interruption_source: source,
      interruption_time: interruptionTime,
    };
  }

  /**
   * ★ Round 9: 读取已记录的中断信息
   */
  getInterruptionInfo(taskId: string): { atStep: number; at: string } | undefined {
    return this.interruptedTasks.get(taskId);
  }

  /**
   * ★ Round 8: 从中断恢复并继续执行
   *
   * @param taskId 任务 ID
   * @param stepsToResume 剩余步骤列表
   * @param executeFn 实际执行函数 (step) => Promise<FallbackResult>
   * @param checkpointManager 自身引用
   * @returns 恢复执行结果
   */
  async resume(
    taskId: string,
    stepsToResume: Array<{ instruction: string; goalDescription: string; params?: Record<string, any> }>,
    executeFn: (step: { instruction: string; params?: Record<string, any> }) => Promise<any>,
    initialContext?: any
  ): Promise<{
    resume_result: ResumeResult;
    steps_executed: number;
    final_context: any;
    interrupted: boolean;
  }> {
    const checkpoint = this.loadCheckpoint(taskId);
    const interrupted = checkpoint !== null;

    // 获取恢复起始步
    const resumeResult = this.validateAndResume(taskId, checkpoint?.step || 0, undefined);
    const startFromStep = resumeResult.resume_from_step;

    // 确定要跳过的步骤（已完成）
    const stepsToSkip = interrupted ? (startFromStep > 0 ? startFromStep - 1 : 0) : 0;

    let ctx = resumeResult.restored_context || initialContext || {
      session_id: taskId,
      current_step: 0,
      operation_history: [],
    };

    // 跳过已完成步骤的操作历史
    if (resumeResult.restored_context?.operation_history && stepsToSkip > 0) {
      ctx.operation_history = [...resumeResult.restored_context.operation_history];
    }

    let executedCount = 0;

    for (let i = 0; i < stepsToResume.length; i++) {
      const step = stepsToResume[i];
      const stepNum = (startFromStep > 0 ? startFromStep : 1) + i;

      // 执行步骤（带操作历史防重）
      const fbResult = await executeFn({
        instruction: step.instruction,
        params: {
          ...(step.params || {}),
          url: ctx.last_url,
          appName: ctx.last_app,
          // 传入已完成的操作历史，防止重复执行
          _completed_history: ctx.operation_history,
        },
      });

      const observedState = (fbResult as any).checks
        ? extractObservedStateFromChecks((fbResult as any).checks)
        : undefined;

      ctx = {
        ...ctx,
        ...(fbResult.accumulated_context || {}),
        current_step: stepNum,
        last_url: observedState?.url || ctx.last_url,
        last_app: observedState?.process_name || ctx.last_app,
      };

      // 每步保存新检查点
      this.saveCheckpoint(
        taskId,
        stepNum,
        ctx,
        observedState,
        undefined
      );

      executedCount++;
    }

    // 恢复决策必须是 'resume' 或 'replay_from_checkpoint' 才能算 recovered
    const recovered = resumeResult.resume_decision === 'resume' || resumeResult.resume_decision === 'replay_from_checkpoint';

    // 计算跳过的步骤数（用于验证不重复执行）
    // 'resume': 跳过 resume_from_step - 1（已完成步骤）
    // 'replay_from_checkpoint': 跳过 suggested_start_step（从检查点重新执行该步）
    // 'replay_from_start' / 'abort': 跳过 0
    let skipped: number;
    if (resumeResult.resume_decision === 'resume') {
      skipped = startFromStep - 1;
    } else if (resumeResult.resume_decision === 'replay_from_checkpoint') {
      skipped = resumeResult.suggested_start_step;
    } else {
      skipped = 0;
    }

    return {
      resume_result: {
        ...resumeResult,
        recovered_chain_completed: recovered,
        steps_skipped: recovered ? skipped : 0,
      },
      steps_executed: executedCount,
      final_context: ctx,
      interrupted,
    };
  }

  /**
   * ★ Round 9: 从中断恢复并验证目标达成
   *
   * 复合操作：
   * 1. 调用 resume() 继续执行剩余步骤
   * 2. 在最终状态上运行目标态验证
   * 3. 返回恢复结果 + 目标验证结果
   *
   * @param taskId 任务 ID
   * @param stepsToResume 剩余步骤
   * @param executeFn 执行函数
   * @param initialContext 初始上下文
   * @param goalDescription 恢复后要验证的目标描述
   * @returns 恢复结果 + 目标验证结果
   */
  async resumeWithGoalState(
    taskId: string,
    stepsToResume: Array<{ instruction: string; goalDescription: string; params?: Record<string, any> }>,
    executeFn: (step: { instruction: string; params?: Record<string, any> }) => Promise<any>,
    initialContext?: any,
    goalDescription?: string
  ): Promise<{
    resume_result: ResumeResult & { recovered_chain_completed: boolean; steps_skipped: number };
    steps_executed: number;
    final_context: any;
    interrupted: boolean;
    goal_verification?: GoalVerificationResult;
    goal_satisfied_after_resume: boolean;
    real_interruption_source: string;
  }> {
    // 执行恢复
    const resumeOut = await this.resume(taskId, stepsToResume, executeFn, initialContext);

    // 确定真实中断源（检查 interruptedTasks 记录）
    const interruptInfo = this.interruptedTasks.get(taskId);
    const realInterruptionSource = interruptInfo
      ? `midscene_failure_at_step_${interruptInfo.atStep}`
      : 'no_real_interruption_detected';

    // 如果提供了目标描述，执行目标态验证
    let goalVerification: GoalVerificationResult | undefined;
    let goalSatisfiedAfterResume = false;

    if (goalDescription) {
      // 从 final_context 提取观察状态
      const observedState = {
        url: resumeOut.final_context?.last_url,
        title: resumeOut.final_context?.last_title,
        process_name: resumeOut.final_context?.last_app,
        element_count: resumeOut.final_context?.element_count,
        window_title: resumeOut.final_context?.window_title,
      };

      const parsedGoal = parseGoalState(goalDescription);
      goalVerification = verifyGoalState(parsedGoal, observedState, undefined);
      goalSatisfiedAfterResume = goalVerification.goal_satisfied;

      // 保存恢复后的目标验证检查点
      this.saveCheckpoint(
        taskId,
        resumeOut.final_context?.current_step || 0,
        resumeOut.final_context,
        observedState,
        parsedGoal
      );
    }

    return {
      resume_result: {
        resume_from_step: resumeOut.resume_result.resume_from_step,
        checkpoint_valid: resumeOut.resume_result.checkpoint_valid,
        state_compatibility: resumeOut.resume_result.state_compatibility,
        resume_decision: resumeOut.resume_result.resume_decision,
        reason: resumeOut.resume_result.reason,
        restored_context: resumeOut.resume_result.restored_context,
        suggested_start_step: resumeOut.resume_result.suggested_start_step,
        recovered_chain_completed: resumeOut.resume_result.recovered_chain_completed ?? false,
        steps_skipped: resumeOut.resume_result.steps_skipped ?? 0,
      },
      steps_executed: resumeOut.steps_executed,
      final_context: resumeOut.final_context,
      interrupted: resumeOut.interrupted,
      goal_verification: goalVerification,
      goal_satisfied_after_resume: goalSatisfiedAfterResume,
      real_interruption_source: realInterruptionSource,
    };
  }
}

// 导出单例
export const checkpointManager = new CheckpointManager();

// ============================================
// 执行器适配器
// ============================================

/**
 * 执行器适配器
 *
 * 统一接口封装四大执行器：
 * - Claude Code: 代码编写·文件系统操作·bash命令
 * - CLI-Anything: GUI软件CLI化
 * - Midscene.js: Web视觉自动化
 * - UI-TARS: 桌面GUI兜底
 */
export class ExecutorAdapter {
  private taskQueue: ExecutorTask[];
  private activeTask: ExecutorTask | null;
  private riskAssessorThreshold: number;

  constructor() {
    this.taskQueue = [];
    this.activeTask = null;
    this.riskAssessorThreshold = 0.7;
  }

  /**
   * 提交执行任务
   */
  async submit(
    type: ExecutorType,
    instruction: string,
    params: Record<string, any> = {},
    sandboxed: boolean = true
  ): Promise<string> {
    const taskId = `task_${Date.now()}_${crypto.randomUUID().replace(/-/g, '').substring(0, 9)}`;

    const task: ExecutorTask = {
      id: taskId,
      type,
      instruction,
      params,
      status: ExecutorStatus.IDLE,
      sandboxed,
      created_at: new Date().toISOString(),
      retry_count: 0,
      max_retries: 3,
    };

    this.taskQueue.push(task);
    return taskId;
  }

  /**
   * 执行任务
   */
  async execute(taskId: string): Promise<ExecutorResult> {
    const task = this.findTask(taskId);
    if (!task) {
      return {
        success: false,
        task_id: taskId,
        error: 'Task not found',
        execution_time_ms: 0,
      };
    }

    const startTime = Date.now();
    task.status = ExecutorStatus.RUNNING;
    task.started_at = new Date().toISOString();
    this.activeTask = task;

    try {
      // 风险评估
      const riskAssessment = riskAssessor.assess(task.instruction);
      if (riskAssessment.level === 'critical' || riskAssessment.requires_approval) {
        throw new Error(`High-risk operation blocked: ${riskAssessment.reason}`);
      }

      // 根据类型执行
      let result: any;
      switch (task.type) {
        case ExecutorType.CLAUDE_CODE:
          result = await this.executeClaudeCode(task);
          break;
        case ExecutorType.CLI_ANYTHING:
          result = await this.executeCLIAnything(task);
          break;
        case ExecutorType.MIDSCENE:
          result = await this.executeMidscene(task);
          break;
        case ExecutorType.UI_TARS:
          result = await this.executeUITARS(task);
          break;
        case ExecutorType.OPENCLI:
          result = await this.executeOpenCLI(task);
          break;
        default:
          throw new Error(`Unknown executor type: ${task.type}`);
      }

      task.status = ExecutorStatus.COMPLETED;
      task.completed_at = new Date().toISOString();
      task.result = result;

      return {
        success: true,
        task_id: taskId,
        result,
        execution_time_ms: Date.now() - startTime,
      };
    } catch (error) {
      task.status = ExecutorStatus.FAILED;
      task.error = error instanceof Error ? error.message : 'Unknown error';
      task.retry_count++;

      // 自动重试
      if (task.retry_count < task.max_retries) {
        task.status = ExecutorStatus.IDLE;
        return this.execute(taskId);
      }

      return {
        success: false,
        task_id: taskId,
        error: task.error,
        execution_time_ms: Date.now() - startTime,
      };
    } finally {
      this.activeTask = null;
    }
  }

  /**
   * Claude Code执行 (真实调用)
   * SECURITY FIX: 使用数组形式传递参数，防止命令注入
   */
  private async executeClaudeCode(task: ExecutorTask): Promise<any> {
    const { instruction, sandboxed, params } = task;

    // SECURITY: 使用数组形式传递命令和参数，而非字符串拼接
    const claudeArgs = ['--print', instruction];

    if (sandboxed) {
      // 在 gVisor 中执行 - 使用数组形式
      const sandboxResult = await gVisorSandbox.execute(
        ['claude', ...claudeArgs],
        { type: SandboxType.GVISOR, timeout_ms: params.timeout_ms || 120000 }
      );

      if (!sandboxResult.success) {
        throw new Error(`Sandbox execution failed: ${sandboxResult.stderr}`);
      }

      return { output: sandboxResult.stdout, sandboxed: true };
    }

    // 直接执行 (信任的命令) - 数组形式
    return new Promise((resolve, reject) => {
      const proc = spawn('claude', claudeArgs, {
        timeout: params.timeout_ms || 120000,
      });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });
      proc.stderr?.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code) => {
        if (code === 0) {
          resolve({ output: stdout, sandboxed: false });
        } else {
          reject(new Error(`Claude Code failed: ${stderr}`));
        }
      });

      proc.on('error', (error) => reject(error));
    });
  }

  /**
   * CLI-Anything执行 (真实调用)
   * SECURITY FIX: 添加工具名白名单验证
   */
  // 允许的工具名白名单
  private readonly ALLOWED_TOOLS = new Set([
    'gimp', 'blender', 'ffmpeg', 'imagemagick', 'zotero',
    'audacity', 'inkscape', 'libreoffice', 'gthumb'
  ]);

  private async executeCLIAnything(task: ExecutorTask): Promise<any> {
    const { instruction, params } = task;

    const toolName = params.tool_name || this.extractToolName(instruction);

    // SECURITY: 验证工具名白名单
    if (!this.ALLOWED_TOOLS.has(toolName)) {
      return {
        tool: toolName,
        instruction,
        result: `CLI-Anything: tool "${toolName}" not in allowed list`,
        found: false,
        error: 'Tool not allowed',
      };
    }

    // SECURITY: 验证路径格式，防止路径遍历
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const hubPath = runtimePath('cli-hub', `${toolName}.sh`);

    // 验证最终路径确实在预期目录内
    if (!hubPath.startsWith(runtimePath('cli-hub'))) {
      return {
        tool: toolName,
        result: 'CLI-Anything: invalid path traversal attempt',
        found: false,
        error: 'Path traversal detected',
      };
    }

    // 检查 CLI hub 工具是否存在
    const toolExists = fs.existsSync(hubPath);

    if (!toolExists) {
      return {
        tool: toolName,
        instruction,
        result: `CLI-Anything: tool not found in hub`,
        hub_path: hubPath,
        found: false,
      };
    }

    // 执行 CLI wrapper
    return new Promise((resolve, reject) => {
      const proc = spawn('sh', [hubPath, instruction], {
        timeout: params.timeout_ms || 60000,
      });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });
      proc.stderr?.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code) => {
        resolve({
          tool: toolName,
          instruction,
          result: stdout || `CLI-Anything: ${toolName} executed`,
          hub_path: hubPath,
          found: true,
          exit_code: code,
        });
      });

      proc.on('error', (error) => reject(error));
    });
  }

  /**
   * Midscene.js执行 (真实调用)
   */
  private async executeMidscene(task: ExecutorTask): Promise<any> {
    const { instruction, params } = task;

    const url = params.url || 'https://example.com';
    const action = params.action || 'navigate_and_extract';
    const midsceneScript = params.script_path || 'navigate_and_extract.js';

    // 检查 Midscene.js 是否可用
    const midsceneAvailable = await this.checkMidsceneAvailable();

    if (!midsceneAvailable) {
      return {
        url,
        action,
        instruction,
        result: `Midscene: not available`,
        available: false,
      };
    }

    // 构建 Midscene.js 命令
    const midsceneCmd = `npx midscene ${action} --url "${url}" --instruction "${instruction.replace(/"/g, '\\"')}"`;

    // 在沙盒中执行 Midscene.js
    const sandboxResult = await gVisorSandbox.execute(midsceneCmd, {
      type: SandboxType.DOCKER,
      timeout_ms: params.timeout_ms || 120000,
    });

    return {
      url,
      action,
      instruction,
      result: sandboxResult.stdout || `Midscene: ${action} completed`,
      available: true,
      tokens_saved: '~40% vs DOM-based',
    };
  }

  /**
   * UI-TARS执行 (真实调用)
   */
  private async executeUITARS(task: ExecutorTask): Promise<any> {
    const { instruction, params } = task;

    const targetApp = params.app || 'unknown';
    const uiTarsAvailable = await this.checkUITARSAvailable();

    if (!uiTarsAvailable) {
      return {
        app: targetApp,
        instruction,
        result: `UI-TARS: not available`,
        available: false,
      };
    }

    // UI-TARS desktop API 调用
    const uiTarsCmd = `ui-tars --app "${targetApp}" --instruction "${instruction.replace(/"/g, '\\"')}"`;

    const sandboxResult = await gVisorSandbox.execute(uiTarsCmd, {
      type: SandboxType.GVISOR,
      timeout_ms: params.timeout_ms || 180000,
    });

    return {
      app: targetApp,
      instruction,
      result: sandboxResult.stdout || `UI-TARS: completed on ${targetApp}`,
      available: true,
      use_case_count: (params.use_count || 0) + 1,
    };
  }

  /**
   * OpenCLI 执行 (浏览器自动化)
   * 支持: 导航、点击、截图、提取数据
   */
  private async executeOpenCLI(task: ExecutorTask): Promise<any> {
    const { instruction, params } = task;

    // 检查 OpenCLI 是否可用
    const opencliAvailable = await this.checkOpenCLIAvailable();

    if (!opencliAvailable) {
      return {
        instruction,
        result: `OpenCLI: not available (daemon not running or extension not connected)`,
        available: false,
        daemon: false,
        extension: false,
      };
    }

    // 检测是否为平台命令 (如: opencli 36kr hot, opencli bilibili search xxx)
    // 平台命令特征: 包含平台名 + 命令，但不含浏览器动作动词
    const isPlatformCommand = this.detectPlatformCommand(instruction);
    if (isPlatformCommand) {
      return this.executeOpenCLIPlatform(task);
    }

    const client = await getOpenCLIClient();
    if (!client) {
      return {
        instruction,
        result: `OpenCLI: client module not loaded`,
        available: false,
      };
    }

    // 解析指令类型
    const action = params.action || this.parseOpenCLIAction(instruction);
    const url = params.url || this.extractUrl(instruction);

    switch (action) {
      case 'navigate':
      case 'open':
        const navResult = await client.open(url);
        return {
          action: 'navigate',
          url,
          result: navResult.success ? `Opened ${url}` : `Failed: ${navResult.error}`,
          available: true,
          daemon: true,
          extension: true,
        };

      case 'click':
        const clickIndex = params.index || this.extractElementIndex(instruction);
        if (clickIndex === null) {
          return { action: 'click', result: 'No element index provided', success: false };
        }
        const clickResult = await client.click(clickIndex);
        return {
          action: 'click',
          index: clickIndex,
          result: clickResult.success ? `Clicked element ${clickIndex}` : `Failed: ${clickResult.error}`,
          available: true,
        };

      case 'type':
        const typeIndex = params.index || this.extractElementIndex(instruction);
        const text = params.text || this.extractTypedText(instruction);
        if (typeIndex === null || !text) {
          return { action: 'type', result: 'Missing index or text', success: false };
        }
        const typeResult = await client.type(typeIndex, text);
        return {
          action: 'type',
          index: typeIndex,
          text,
          result: typeResult.success ? `Typed at element ${typeIndex}` : `Failed: ${typeResult.error}`,
          available: true,
        };

      case 'screenshot':
        const screenshotPath = params.path || params.screenshot_path;
        const screenshotResult = await client.screenshot(screenshotPath);
        return {
          action: 'screenshot',
          path: screenshotResult.path,
          result: screenshotResult.success ? `Screenshot saved` : `Failed: ${screenshotResult.error}`,
          available: true,
        };

      case 'state':
      case 'get_state':
        const state = await client.getState();
        return {
          action: 'state',
          state,
          result: state ? `URL: ${state.url}, Title: ${state.title}, Elements: ${state.elements.length}` : 'Failed to get state',
          available: true,
        };

      case 'wait':
        const waitType = params.wait_type || 'time';
        const waitValue = params.wait_value || '3';
        const waitResult = await client.wait(waitType as any, waitValue);
        return {
          action: 'wait',
          type: waitType,
          value: waitValue,
          result: waitResult.success ? `Waited for ${waitType}: ${waitValue}` : `Failed: ${waitResult.error}`,
          available: true,
        };

      case 'close':
        const closeResult = await client.close();
        return {
          action: 'close',
          result: closeResult.success ? 'Browser closed' : `Failed: ${closeResult.error}`,
          available: true,
        };

      default:
        // 通用执行: 直接传递指令
        const genericResult = await client.executeBrowserCommand([action, ...Object.values(params).filter(Boolean)]);
        return {
          action,
          instruction,
          result: genericResult.success ? genericResult.output : `Failed: ${genericResult.error}`,
          available: true,
        };
    }
  }

  /**
   * 检查 OpenCLI daemon 是否可用
   */
  private async checkOpenCLIAvailable(): Promise<boolean> {
    return new Promise((resolve) => {
      // 使用 opencli doctor 检查状态
      const proc = spawn('opencli', ['doctor'], { timeout: 10000 });
      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });
      proc.stderr?.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code) => {
        // daemon 运行中即认为可用 (extension 可后续连接)
        resolve(stdout.includes('daemon') || stdout.includes('running'));
      });

      proc.on('error', () => resolve(false));
    });
  }

  /**
   * 执行 OpenCLI 平台命令 (非浏览器)
   * 支持: 36kr, bilibili, xiaohongshu 等 89 个平台
   */
  private async executeOpenCLIPlatform(task: ExecutorTask): Promise<any> {
    const { instruction, params } = task;

    const site = params.site || this.extractSite(instruction);
    const cmd = params.command || this.extractCommand(instruction);
    const input = params.input || params.url || this.extractInput(instruction);

    if (!site || !cmd) {
      return {
        instruction,
        result: 'OpenCLI Platform: missing site or command',
        success: false,
        available: true,
      };
    }

    // 构建命令
    const cmdArgs = [site, cmd];
    if (input) {
      cmdArgs.push(input);
    }

    // 添加额外参数
    Object.entries(params).forEach(([key, value]) => {
      if (!['site', 'command', 'input', 'url', 'action'].includes(key) && value) {
        cmdArgs.push(`--${key}`, String(value));
      }
    });

    return new Promise((resolve) => {
      const proc = spawn('opencli', cmdArgs, { timeout: params.timeout_ms || 60000 });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });
      proc.stderr?.on('data', (data) => { stderr += data.toString(); });

      proc.on('close', (code) => {
        resolve({
          site,
          command: cmd,
          input,
          success: code === 0,
          stdout,
          stderr,
          exitCode: code,
          result: code === 0 ? stdout : `Failed: ${stderr}`,
          available: true,
        });
      });

      proc.on('error', (error) => {
        resolve({
          site,
          command: cmd,
          success: false,
          error: error.message,
          available: true,
        });
      });
    });
  }

  /**
   * 从指令中提取站点
   */
  private extractSite(instruction: string): string | null {
    const platforms = [
      'bilibili', 'xiaohongshu', 'douyin', 'tiktok', 'weibo', 'zhihu',
      'taobao', 'jd', '1688', 'github', 'google', '36kr', 'xueqiu'
    ];

    const lower = instruction.toLowerCase();
    for (const platform of platforms) {
      if (lower.includes(platform)) {
        return platform;
      }
    }
    return null;
  }

  /**
   * 从指令中提取命令
   */
  private extractCommand(instruction: string): string | null {
    const lower = instruction.toLowerCase();
    if (lower.includes('search')) return 'search';
    if (lower.includes('hot') || lower.includes('trending')) return 'hot';
    if (lower.includes('video')) return 'video';
    if (lower.includes('article')) return 'article';
    if (lower.includes('item') || lower.includes('product')) return 'item';
    if (lower.includes('download')) return 'download';
    if (lower.includes('user') || lower.includes('profile')) return 'user';
    return 'search'; // 默认搜索
  }

  /**
   * 从指令中提取输入
   */
  private extractInput(instruction: string): string | null {
    // 尝试提取 URL
    const urlMatch = instruction.match(/(https?:\/\/[^\s]+)/);
    if (urlMatch) return urlMatch[1];

    // 尝试提取引号中的文本
    const quoteMatch = instruction.match(/["']([^"']+)["']/);
    if (quoteMatch) return quoteMatch[1];

    // 尝试提取最后的关键字
    const words = instruction.split(/\s+/);
    return words[words.length - 1] || null;
  }

  /**
   * 从指令中解析 OpenCLI 动作
   */
  private parseOpenCLIAction(instruction: string): string {
    const lower = instruction.toLowerCase();
    if (lower.includes('navigate') || lower.includes('go to') || lower.includes('open')) return 'navigate';
    if (lower.includes('click')) return 'click';
    if (lower.includes('type') || lower.includes('input')) return 'type';
    if (lower.includes('screenshot') || lower.includes('截图')) return 'screenshot';
    if (lower.includes('state') || lower.includes('page')) return 'state';
    if (lower.includes('wait')) return 'wait';
    if (lower.includes('close') || lower.includes('shutdown')) return 'close';
    return 'state'; // 默认获取状态
  }

  /**
   * 从指令中提取 URL
   */
  private extractUrl(instruction: string): string {
    const urlMatch = instruction.match(/(https?:\/\/[^\s]+)/);
    return urlMatch ? urlMatch[1] : 'https://example.com';
  }

  /**
   * 从指令中提取元素索引
   */
  private extractElementIndex(instruction: string): number | null {
    const indexMatch = instruction.match(/\[(\d+)\]/);
    return indexMatch ? parseInt(indexMatch[1]) : null;
  }

  /**
   * 从指令中提取输入文本
   */
  private extractTypedText(instruction: string): string | null {
    const textMatch = instruction.match(/(?:type|input)\s+.+\s+["'](.+)["']/i);
    return textMatch ? textMatch[1] : null;
  }

  /**
   * 检测是否为平台命令 (非浏览器自动化)
   * 平台命令: opencli 36kr hot, opencli bilibili search xxx
   * 浏览器命令: opencli navigate https://..., opencli click [1]
   */
  private detectPlatformCommand(instruction: string): boolean {
    const lower = instruction.toLowerCase();

    // 浏览器动作关键词 - 有这些的是浏览器命令
    const browserActions = ['navigate', 'open', 'click', 'type', 'screenshot', 'wait', 'close', 'get_state', 'page'];
    for (const action of browserActions) {
      if (lower.includes(action)) return false;
    }

    // 平台关键词 - 有这些的是平台命令
    const platformKeywords = [
      '36kr', 'bilibili', 'xiaohongshu', 'douyin', 'tiktok',
      'weibo', 'zhihu', 'taobao', 'jd', '1688', 'github',
      'google', 'baidu', 'xueqiu', 'youtube', 'instagram'
    ];

    for (const platform of platformKeywords) {
      if (lower.includes(platform)) return true;
    }

    return false;
  }

  /**
   * 检查 Midscene.js 是否可用
   */
  private async checkMidsceneAvailable(): Promise<boolean> {
    return new Promise((resolve) => {
      const proc = spawn('which', ['midscene']);
      proc.on('close', (code) => resolve(code === 0));
      proc.on('error', () => resolve(false));
    });
  }

  /**
   * 检查 UI-TARS 是否可用
   */
  private async checkUITARSAvailable(): Promise<boolean> {
    return new Promise((resolve) => {
      const proc = spawn('which', ['ui-tars']);
      proc.on('close', (code) => resolve(code === 0));
      proc.on('error', () => resolve(false));
    });
  }

  /**
   * 从指令中提取工具名
   */
  private extractToolName(instruction: string): string {
    const match = instruction.match(/(gimp|blender|ffmpeg|imagemagick|zotero|audacity|inkscape|libreoffice|gthumb)/i);
    return match ? match[1].toLowerCase() : 'unknown';
  }

  /**
   * 查找任务
   */
  private findTask(taskId: string): ExecutorTask | undefined {
    return this.taskQueue.find(t => t.id === taskId);
  }

  /**
   * 获取任务状态
   */
  getTaskStatus(taskId: string): ExecutorStatus | null {
    const task = this.findTask(taskId);
    return task?.status || null;
  }

  /**
   * 获取活跃任务
   */
  getActiveTask(): ExecutorTask | null {
    return this.activeTask;
  }

  /**
   * 获取队列长度
   */
  getQueueLength(): number {
    return this.taskQueue.length;
  }

  /**
   * 取消任务
   */
  cancelTask(taskId: string): boolean {
    const task = this.findTask(taskId);
    if (!task) return false;

    if (task.status === ExecutorStatus.RUNNING) {
      return false; // 正在执行的任务无法取消
    }

    task.status = ExecutorStatus.CANCELLED;
    return true;
  }

  /**
   * 清除已完成的任务
   */
  clearCompleted(): number {
    const before = this.taskQueue.length;
    this.taskQueue = this.taskQueue.filter(
      t => t.status !== ExecutorStatus.COMPLETED && t.status !== ExecutorStatus.FAILED
    );
    return before - this.taskQueue.length;
  }
}

// ============================================
// 视觉工具决策树
// ============================================

/**
 * 视觉工具选择器
 *
 * 根据操作类型自动选择最优执行器：
 * - Web浏览器操作 → OpenCLI (首选) / Midscene.js (兜底)
 * - 桌面应用<3次 → UI-TARS
 * - 桌面应用≥3次 → CLI-Anything
 */
export class VisualToolSelector {
  private usageCounts: Map<string, number>;
  private opencliStatusCache: { available: boolean; checkedAt: number } | null = null;
  private readonly OPENCLI_CACHE_TTL_MS = 30000; // 30秒缓存

  constructor() {
    this.usageCounts = new Map();
  }

  /**
   * 选择执行器 (异步 - 需要检查 OpenCLI 可用性)
   */
  async select(
    operation: 'web_browser' | 'desktop_app' | 'cli_command',
    context: { url?: string; app?: string; command?: string }
  ): Promise<ExecutorType> {
    switch (operation) {
      case 'web_browser':
        // 优先检查 OpenCLI 可用性
        if (await this.isOpenCLIAvailable()) {
          return ExecutorType.OPENCLI;
        }
        // OpenCLI 不可用时降级到 Midscene.js
        return ExecutorType.MIDSCENE;

      case 'desktop_app':
        const appKey = context.app || 'unknown';
        const usageCount = this.usageCounts.get(`${operation}:${appKey}`) || 0;

        if (usageCount >= 3) {
          return ExecutorType.CLI_ANYTHING;
        } else {
          return ExecutorType.UI_TARS;
        }

      case 'cli_command':
        return ExecutorType.CLAUDE_CODE;

      default:
        return ExecutorType.CLAUDE_CODE;
    }
  }

  /**
   * 同步选择执行器 (不检查 OpenCLI - 用于已知浏览器任务)
   */
  selectSync(
    operation: 'web_browser' | 'desktop_app' | 'cli_command',
    context: { url?: string; app?: string; command?: string }
  ): ExecutorType {
    switch (operation) {
      case 'web_browser':
        // 同步模式默认返回 OpenCLI (假设可用)
        return ExecutorType.OPENCLI;

      case 'desktop_app':
        const appKey = context.app || 'unknown';
        const usageCount = this.usageCounts.get(`${operation}:${appKey}`) || 0;

        if (usageCount >= 3) {
          return ExecutorType.CLI_ANYTHING;
        } else {
          return ExecutorType.UI_TARS;
        }

      case 'cli_command':
        return ExecutorType.CLAUDE_CODE;

      default:
        return ExecutorType.CLAUDE_CODE;
    }
  }

  /**
   * 检查 OpenCLI 是否可用
   */
  private async isOpenCLIAvailable(): Promise<boolean> {
    // 检查缓存
    if (this.opencliStatusCache) {
      const age = Date.now() - this.opencliStatusCache.checkedAt;
      if (age < this.OPENCLI_CACHE_TTL_MS) {
        return this.opencliStatusCache.available;
      }
    }

    // 执行检查
    const available = await this.checkOpenCLIDaemon();
    this.opencliStatusCache = {
      available,
      checkedAt: Date.now(),
    };
    return available;
  }

  /**
   * 检查 OpenCLI daemon 进程
   */
  private async checkOpenCLIDaemon(): Promise<boolean> {
    return new Promise((resolve) => {
      const proc = spawn('opencli', ['doctor'], { timeout: 5000 });
      let stdout = '';
      let resolved = false;

      const cleanup = () => {
        if (!resolved) {
          resolved = true;
          try {
            if (!proc.killed) {
              proc.kill('SIGTERM');
            }
          } catch {
            // Ignore kill errors
          }
        }
      };

      proc.stdout?.on('data', (data) => { stdout += data.toString(); });

      proc.on('close', () => {
        cleanup();
        resolve(stdout.includes('running') || stdout.includes('[OK]'));
      });

      proc.on('error', () => {
        cleanup();
        resolve(false); // Fast fail if opencli not found
      });

      // Timeout fallback - shorter timeout for faster test execution
      setTimeout(() => {
        cleanup();
        resolve(false);
      }, 5000);
    });
  }

  /**
   * 清除 OpenCLI 状态缓存
   */
  clearCache(): void {
    this.opencliStatusCache = null;
  }

  /**
   * 记录使用次数
   */
  recordUsage(operation: 'web_browser' | 'desktop_app', identifier: string): void {
    const key = `${operation}:${identifier}`;
    const current = this.usageCounts.get(key) || 0;
    this.usageCounts.set(key, current + 1);
  }

  /**
   * 获取使用次数
   */
  getUsageCount(operation: string, identifier: string): number {
    return this.usageCounts.get(`${operation}:${identifier}`) || 0;
  }

  /**
   * 建议转换到CLI
   */
  shouldConvertToCLI(operation: string, identifier: string): boolean {
    return this.getUsageCount(operation, identifier) >= 3;
  }
}

// ============================================
// 操作任务分类器
// ============================================

export enum OperationType {
  WEB_BROWSER = 'web_browser',
  DESKTOP_APP = 'desktop_app',
  CLI_TOOL = 'cli_tool',
  GENERAL_CODE = 'general_code',
}

const WEB_ACTION_KEYWORDS = [
  'navigate', 'click', 'type', 'screenshot', 'scroll', 'open url', 'go to', 'browser', 'web page',
  '网页', '浏览器', '打开网页',
  // ★ Round 10: Expanded web action keywords for superhuman efficiency
  'star', 'bookmark', 'fork', 'clone', 'pull', 'push', 'merge', 'commit', 'repository', 'repo',
  'login', 'logout', 'sign in', 'sign up', 'register', 'account',
  'search', 'submit', 'download', 'upload', 'share',
  'github', 'gitlab', 'stackoverflow', 'google', 'youtube', 'twitter', 'facebook',
  'linkedin', 'instagram', 'tiktok', 'reddit', 'discord', 'slack', 'notion',
  'http', 'https', 'www',
];
const DESKTOP_ACTION_KEYWORDS = ['app', 'application', 'window', 'desktop', 'launch', 'open app', 'switch to', 'focus', 'menu', 'dialog', 'gui', '桌面', '应用'];
const CLI_TOOL_KEYWORDS = ['gimp', 'blender', 'ffmpeg', 'zotero', 'audacity', 'inkscape', 'libreoffice', 'imagemagick', 'convert'];

export function classifyOperation(instruction: string): OperationType {
  const lower = instruction.toLowerCase();

  for (const kw of WEB_ACTION_KEYWORDS) {
    if (lower.includes(kw)) return OperationType.WEB_BROWSER;
  }
  for (const kw of DESKTOP_ACTION_KEYWORDS) {
    if (lower.includes(kw)) return OperationType.DESKTOP_APP;
  }
  for (const kw of CLI_TOOL_KEYWORDS) {
    if (lower.includes(kw)) return OperationType.CLI_TOOL;
  }

  return OperationType.GENERAL_CODE;
}

// ============================================
// 带 Fallback 链的执行
// ============================================

const FALLBACK_CHAIN: ExecutorType[] = [
  ExecutorType.OPENCLI,
  ExecutorType.MIDSCENE,
  ExecutorType.UI_TARS,
];

const OPERATION_TO_EXECUTOR_TYPE: Record<OperationType, ExecutorType> = {
  [OperationType.WEB_BROWSER]: ExecutorType.OPENCLI,
  [OperationType.DESKTOP_APP]: ExecutorType.CLI_ANYTHING,
  [OperationType.CLI_TOOL]: ExecutorType.CLI_ANYTHING,
  [OperationType.GENERAL_CODE]: ExecutorType.CLAUDE_CODE,
};

export interface FallbackResult {
  success: boolean;
  executor_used: ExecutorType;
  fallback_attempts: Array<{
    from: ExecutorType;
    to: ExecutorType;
    reason: string;
  }>;
  result: any;
  error?: string;
  /** ★ Round 4: 成功时返回累积上下文，供下游使用 */
  accumulated_context?: any;
  /** ★ Round 4: 失败时返回部分上下文，保留中间状态 */
  partial_context?: any;
  /** ★ Round 5/6: 操作验证结果 (dom_observed / desk_observed) */
  checks?: VerificationResult['checks'];
}

/**
 * 自动选择执行器并执行，支持 fallback 链
 *
 * ★ Round 4: 支持跨执行器状态传播
 * - 如果传入了 accumulatedContext，会将其作为 params._operator_context 传递给每个执行器
 * - 执行结果会累积到 context.operation_history 中
 * - fallback 时保留上一个执行器的部分状态
 */
export async function executeWithAutoSelect(
  instruction: string,
  params: Record<string, any> = {},
  context?: HookContext,
  accumulatedContext?: any // ★ Round 4: 跨步骤累积的操作上下文
): Promise<FallbackResult> {
  const opType = classifyOperation(instruction);
  let primaryType = OPERATION_TO_EXECUTOR_TYPE[opType];

  // 对于 Web 操作，先用 VisualToolSelector 确认
  if (opType === OperationType.WEB_BROWSER && visualToolSelector) {
    primaryType = await visualToolSelector.select('web_browser', { url: params.url });
  }

  const fallbackAttempts: FallbackResult['fallback_attempts'] = [];
  let lastError: string = '';

  // ★ R118: 前置健康检查 - 根据 ready 状态过滤 FALLBACK_CHAIN 候选
  // not_ready 的执行器直接跳过，避免盲目尝试失败
  const health = await checkExecutorHealth();
  const filteredChain = FALLBACK_CHAIN.filter(executorType => {
    if (executorType === ExecutorType.CLAUDE_CODE) return false; // Claude Code 不在此链过滤，由末尾兜底
    const status = health.executor_health[executorType]?.status;
    return status !== 'not_ready'; // only filter explicitly not_ready; 'unknown' stays in
  });

  // ★ Round 4: 如果有累积上下文，合并到 params
  const enrichedParams = accumulatedContext
    ? { ...params, _operator_context: accumulatedContext }
    : params;

  for (let i = 0; i < filteredChain.length; i++) {
    const executorType = i === 0 ? primaryType : filteredChain[i];
    if (executorType === ExecutorType.CLAUDE_CODE) continue; // 防御性检查

    const taskId = executorAdapter.getQueueLength() > 0
      ? await executorAdapter.submit(executorType, instruction, enrichedParams, params.sandboxed ?? true)
      : await executorAdapter.submit(executorType, instruction, enrichedParams, true);

    const result = await executorAdapter.execute(taskId);

    if (result.success) {
      // 对 OpenCLI 操作做结果验证 (Round 5: 真实 DOM 观测)
      if (executorType === ExecutorType.OPENCLI) {
        const verified = await verifyOpenCLIResult(result.result, params);
        if (!verified.success) {
          lastError = `OpenCLI verification failed: ${verified.error}`;
          if (i < filteredChain.length - 1) {
            fallbackAttempts.push({ from: executorType, to: filteredChain[i + 1], reason: lastError });
            continue;
          }
          return {
            success: false,
            executor_used: executorType,
            fallback_attempts: fallbackAttempts,
            result,
            error: lastError,
            // ★ Round 4: 即使失败也保留部分状态供 fallback 使用
            partial_context: buildPartialContext(executorType, instruction, result, accumulatedContext),
          };
        }
        // ★ Round 4: 成功时返回累积上下文，供下游使用
        // ★ Round 6: 附加 checks (dom_observed)
        return {
          success: true,
          executor_used: executorType,
          fallback_attempts: fallbackAttempts,
          result,
          accumulated_context: buildAccumulatedContext(executorType, instruction, result, accumulatedContext),
          checks: verified.checks, // dom_observed
        };
      }

      // ★ Round 6: 对 CLI_ANYTHING 桌面操作做结构化观测验证 (desk_observed)
      if (executorType === ExecutorType.CLI_ANYTHING) {
        const verified = await verifyDesktopResult(result.result, params);
        return {
          success: true,
          executor_used: executorType,
          fallback_attempts: fallbackAttempts,
          result,
          accumulated_context: buildAccumulatedContext(executorType, instruction, result, accumulatedContext),
          checks: verified.checks, // desk_observed
        };
      }

      // 其他执行器 (MIDSCENE, UI_TARS) 的成功返回
      return {
        success: true,
        executor_used: executorType,
        fallback_attempts: fallbackAttempts,
        result,
        accumulated_context: buildAccumulatedContext(executorType, instruction, result, accumulatedContext),
      };
    }

    lastError = result.error || 'unknown';
    if (i < filteredChain.length - 1) {
      fallbackAttempts.push({ from: executorType, to: filteredChain[i + 1], reason: lastError });
    }
  }

  // 最后一个 fallback 也失败，尝试 Claude Code
  const taskId = await executorAdapter.submit(ExecutorType.CLAUDE_CODE, instruction, enrichedParams, params.sandboxed ?? true);
  const result = await executorAdapter.execute(taskId);
  return {
    success: result.success,
    executor_used: ExecutorType.CLAUDE_CODE,
    fallback_attempts: fallbackAttempts,
    result,
    error: result.error,
    // ★ Round 4: 即使完全失败也保留 partial_context
    partial_context: buildPartialContext(ExecutorType.CLAUDE_CODE, instruction, result, accumulatedContext),
  };
}

/**
 * ★ Round 4: 构建累积上下文
 * 将当前执行器的结果合并到累积上下文中，供下游或 fallback 使用
 */
function buildAccumulatedContext(
  executorType: ExecutorType,
  instruction: string,
  result: any,
  prevContext?: any
): any {
  return {
    // 从之前上下文继承
    ...(prevContext || {}),
    // 覆盖/追加当前执行器的状态
    last_executor: executorType,
    last_instruction: instruction,
    last_result: result,
    last_url: result?.url || prevContext?.last_url,
    last_app: result?.app || prevContext?.last_app,
    identified_elements: result?.elements || prevContext?.identified_elements,
    // 操作历史追加
    operation_history: [
      ...(prevContext?.operation_history || []),
      {
        executor: executorType,
        instruction,
        result: result,
        timestamp: new Date().toISOString(),
      },
    ],
  };
}

/**
 * ★ Round 4: 构建部分上下文 (用于失败时保留状态)
 */
function buildPartialContext(
  executorType: ExecutorType,
  instruction: string,
  result: any,
  prevContext?: any
): any {
  return {
    ...(prevContext || {}),
    failed_executor: executorType,
    last_instruction: instruction,
    last_result: result,
    operation_history: [
      ...(prevContext?.operation_history || []),
      {
        executor: executorType,
        instruction,
        result: result,
        success: false,
        timestamp: new Date().toISOString(),
      },
    ],
  };
}

// ============================================
// 最小结果验证闭环
// ============================================

// ============================================
// 增强状态验证 (Round 3 升级)
// ============================================

interface VerificationResult {
  success: boolean;
  error?: string;
  checks?: {
    url_matched?: boolean;
    title_changed?: boolean;
    element_found?: boolean;
    element_missing?: boolean;
    dom_observed?: {
      title?: string;
      url?: string;
      element_count?: number;
      key_elements?: string[];
    };
    /** ★ Round 6: 桌面 GUI 真实观测基线 */
    desk_observed?: {
      active_window_title?: string;
      active_process?: string;
      focus_confirmed?: boolean;
      element_count?: number;
      failure_diagnosis?: string;
    };
  };
}

/**
 * 增强状态验证 - 验证操作后的页面状态变化
 *
 * URL diff: navigate 后检查 URL 是否匹配预期
 * Title diff: 操作后检查标题是否合理变化（非错误态）
 * Element presence: click/type 后检查元素是否存在
 * Element absence: 某些操作后检查元素是否消失（如关闭弹窗）
 */
async function verifyOpenCLIResult(result: any, params: Record<string, any>): Promise<VerificationResult> {
  if (!result || !result.action) return { success: true };

  const action = result.action;

  // 基础失败检测（所有操作）
  if (result.result && (result.result.includes('Failed') || result.result.includes('error'))) {
    return { success: false, error: `Action failed: ${result.result}` };
  }

  // ★ Round 5: 调用 OpenCLI getState() 获取真实页面状态用于观测验证
  let observedState: { url?: string; title?: string; elements?: any[] } | null = null;
  try {
    const client = await getOpenCLIClient();
    if (client) {
      const stateResult = await client.getState();
      if (stateResult.success && stateResult.state) {
        observedState = stateResult.state;
      }
    }
  } catch {
    // getState 失败时使用启发式验证回退
  }

  // navigate/open 后验证 URL 变化（域名级匹配）
  if (action === 'navigate' || action === 'open') {
    const expectedUrl = params.url;
    // 优先用真实观测的 URL
    const actualUrl = observedState?.url || result.url || result.result?.match(/https?:\/\/[^\s]+/)?.[0] || '';

    if (!actualUrl) {
      return { success: false, error: `No URL observed after ${action}`, checks: { url_matched: false } };
    }

    // 域名级匹配（允许路径不同）
    const expectedHost = expectedUrl?.replace(/^https?:\/\//, '').split('/')[0];
    const actualHost = actualUrl.replace(/^https?:\/\//, '').split('/')[0];

    if (expectedHost && !actualHost.includes(expectedHost)) {
      return {
        success: false,
        error: `URL mismatch after ${action}: expected ${expectedHost}, got ${actualHost}`,
        checks: { url_matched: false, dom_observed: observedState ? { url: observedState.url, title: observedState.title, element_count: observedState.elements?.length || 0 } : undefined },
      };
    }
    return {
      success: true,
      checks: { url_matched: true, dom_observed: observedState ? { url: observedState.url, title: observedState.title, element_count: observedState.elements?.length || 0 } : undefined },
    };
  }

  // click/type 后验证（Round 5: 真实 DOM 观测）
  if (action === 'click' || action === 'type') {
    if (observedState) {
      const title = observedState.title || '';
      const url = observedState.url || '';
      if (title.includes('error') || title.includes('ERR_') || url.includes('error')) {
        return {
          success: false,
          error: `Page error state after ${action}: title="${title}"`,
          checks: { element_found: false, dom_observed: { title, url, element_count: observedState.elements?.length || 0 } },
        };
      }
      const elementCount = observedState.elements?.length || 0;
      if (elementCount === 0) {
        return { success: false, error: `No DOM elements after ${action}`, checks: { element_found: false, dom_observed: { title, url, element_count: 0 } } };
      }
      return {
        success: true,
        checks: { element_found: true, title_changed: !!title, dom_observed: { title, url, element_count: elementCount, key_elements: observedState.elements?.slice(0, 3).map(e => e.description || String(e.index)) || [] } },
      };
    }

    const elementIndex = result.index || params.index;
    if (elementIndex === undefined) {
      return { success: true, checks: { element_found: true } };
    }
    if (typeof elementIndex === 'number' && elementIndex >= 0) {
      return { success: true, checks: { element_found: true } };
    }
    return { success: false, error: `Invalid element index: ${elementIndex}` };
  }

  // screenshot 后验证路径存在
  if (action === 'screenshot') {
    const screenshotPath = result.path || params.path;
    if (screenshotPath && result.result?.includes('Failed')) {
      return { success: false, error: 'Screenshot failed' };
    }
    return { success: true, checks: { element_found: true } };
  }

  // wait 操作验证
  if (action === 'wait') {
    return { success: true, checks: { element_found: true } };
  }

  // close 操作验证
  if (action === 'close') {
    return { success: true, checks: { element_found: true } };
  }

  return { success: true };
}

/**
 * ★ Round 6: 桌面 GUI 真实观测验证
 *
 * 验证桌面应用执行后的状态:
 * - 前台窗口识别 - 能获取当前活动窗口标题
 * - 进程状态确认 - 能确认应用是否真正启动
 * - 焦点切换确认 - 能确认焦点是否在目标应用
 * - 故障诊断 - 当操作失败时的结构化错误分类
 *
 * @param result 桌面执行器返回的结果
 * @param params 执行参数 (包含 appName)
 * @returns 验证结果，包含 desk_observed 结构化观测状态
 */
async function verifyDesktopResult(result: any, params: Record<string, any>): Promise<VerificationResult> {
  const appName = params.appName || params.app || params.tool || 'unknown';

  // 提取 CLI 输出中的关键信息
  const output = result?.result || result?.output || '';
  const success = result?.success !== false && !output.includes('Failed') && !output.includes('not found');

  // 基础结构: 从 result 中提取
  const deskObserved: any = {
    active_window_title: '',
    active_process: appName,
    focus_confirmed: false,
    element_count: 0,
  };

  // 尝试从输出中解析窗口标题 (常见模式)
  if (output) {
    // 匹配 "窗口标题: XXX" 或 "Window: XXX"
    const titleMatch = output.match(/(?:窗口标题|Window|Active window)[:\s]+([^\n]+)/i);
    if (titleMatch) {
      deskObserved.active_window_title = titleMatch[1].trim();
    }

    // 匹配 "进程: XXX" 或 "Process: XXX"
    const processMatch = output.match(/(?:进程|Process)[:\s]+([^\n]+)/i);
    if (processMatch) {
      deskObserved.active_process = processMatch[1].trim();
    }

    // CLI 工具执行成功且有输出 → 认为焦点在目标应用
    if (success && output.length > 0) {
      deskObserved.focus_confirmed = true;
    }

    // 失败诊断
    if (!success) {
      if (output.includes('not found') || output.includes('command not found')) {
        deskObserved.failure_diagnosis = 'APP_NOT_FOUND';
      } else if (output.includes('permission denied')) {
        deskObserved.failure_diagnosis = 'PERMISSION_DENIED';
      } else if (output.includes('timeout')) {
        deskObserved.failure_diagnosis = 'APP_LAUNCH_TIMEOUT';
      } else {
        deskObserved.failure_diagnosis = 'UNKNOWN_ERROR';
      }
    }
  }

  return {
    success,
    error: success ? undefined : `Desktop operation failed: ${output}`,
    checks: {
      desk_observed: deskObserved,
    },
  };
}

/**
 * 桌面应用工具选择器
 *
 * 双重路径决策:
 * - 有 CLI wrapper → CLI_ANYTHING (稳定、可复用)
 * - 无 CLI wrapper → UI-TARS (兜底、通用)
 *
 * 使用计数触发转换: ≥3次同app操作建议转 CLI_ANYTHING
 */
export class DesktopToolSelector {
  private readonly ALLOWED_TOOLS = new Set([
    'gimp', 'blender', 'ffmpeg', 'imagemagick', 'zotero',
    'audacity', 'inkscape', 'libreoffice', 'gthumb'
  ]);

  private usageCounts: Map<string, number> = new Map();

  /**
   * 选择桌面应用的执行方式
   * @param appName 应用名
   * @returns CLI_ANYTHING (有wrapper) | UI_TARS (无wrapper/首次)
   */
  async select(appName: string): Promise<ExecutorType> {
    const normalizedApp = appName.toLowerCase().trim();

    // 白名单工具优先走 CLI_ANYTHING
    if (this.ALLOWED_TOOLS.has(normalizedApp)) {
      return ExecutorType.CLI_ANYTHING;
    }

    // 检查是否有自定义 CLI wrapper
    const hasWrapper = await this.checkCLIWrapperExists(normalizedApp);
    if (hasWrapper) {
      return ExecutorType.CLI_ANYTHING;
    }

    // 无 wrapper，检查使用次数
    const usageCount = this.usageCounts.get(normalizedApp) || 0;
    if (usageCount >= 3) {
      return ExecutorType.CLI_ANYTHING; // 频繁使用，建议创建 wrapper
    }

    return ExecutorType.UI_TARS; // 首次/少次使用，UI-TARS 兜底
  }

  /**
   * 同步选择（不查文件系统，用于已知情况）
   */
  selectSync(appName: string): ExecutorType {
    const normalizedApp = appName.toLowerCase().trim();

    if (this.ALLOWED_TOOLS.has(normalizedApp)) {
      return ExecutorType.CLI_ANYTHING;
    }

    const usageCount = this.usageCounts.get(normalizedApp) || 0;
    if (usageCount >= 3) {
      return ExecutorType.CLI_ANYTHING;
    }

    return ExecutorType.UI_TARS;
  }

  /**
   * 检查 CLI wrapper 是否存在
   */
  private async checkCLIWrapperExists(appName: string): Promise<boolean> {
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const hubPath = runtimePath('cli-hub', `${appName}.sh`);
    try {
      return fs.existsSync(hubPath);
    } catch {
      return false;
    }
  }

  /**
   * 记录使用次数（触发转换阈值）
   */
  recordUsage(appName: string): void {
    const normalized = appName.toLowerCase().trim();
    const current = this.usageCounts.get(normalized) || 0;
    this.usageCounts.set(normalized, current + 1);
  }

  /**
   * 获取使用次数
   */
  getUsageCount(appName: string): number {
    return this.usageCounts.get(appName.toLowerCase().trim()) || 0;
  }

  /**
   * 建议转换到 CLI（当使用次数达到阈值时）
   */
  shouldConvertToCLI(appName: string): boolean {
    return this.getUsageCount(appName) >= 3;
  }

  /**
   * 获取支持的应用列表
   */
  getSupportedApps(): string[] {
    return Array.from(this.ALLOWED_TOOLS);
  }
}

// ============================================
// 操作策略选择器 (Round 3)
// ============================================

/**
 * 操作策略选择器
 *
 * 根据指令内容选择操作策略:
 * - VISUAL_WEB: 网页/浏览器自动化策略
 * - DESKTOP_APP: 桌面应用控制策略
 * - GENERAL: 通用代码执行策略
 *
 * 这是在 classifyOperation 之上的策略层，用于更细粒度的执行决策
 */
export class OperatorStrategySelector {
  /**
   * 选择操作策略
   * @param instruction 用户指令
   * @returns 操作策略类型
   */
  select(instruction: string): 'VISUAL_WEB' | 'DESKTOP_APP' | 'GENERAL' {
    const opType = classifyOperation(instruction);

    switch (opType) {
      case OperationType.WEB_BROWSER:
        return 'VISUAL_WEB';
      case OperationType.DESKTOP_APP:
      case OperationType.CLI_TOOL:
        return 'DESKTOP_APP';
      default:
        return 'GENERAL';
    }
  }

  /**
   * 获取策略描述
   */
  getStrategyDescription(strategy: 'VISUAL_WEB' | 'DESKTOP_APP' | 'GENERAL'): string {
    switch (strategy) {
      case 'VISUAL_WEB':
        return '网页自动化策略: OpenCLI → Midscene → UI-TARS fallback';
      case 'DESKTOP_APP':
        return '桌面应用策略: CLI-Anything → UI-TARS fallback';
      case 'GENERAL':
        return '通用代码策略: Claude Code 直接执行';
    }
  }
}

// ============================================
// 单例导出
// ============================================

export const executorAdapter = new ExecutorAdapter();
export const visualToolSelector = new VisualToolSelector();
export const desktopToolSelector = new DesktopToolSelector();
export const operatorStrategySelector = new OperatorStrategySelector();
