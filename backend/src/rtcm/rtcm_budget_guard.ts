/**
 * @file rtcm_budget_guard.ts
 * @description RTCM 资源/成本/并发控制层 - Gamma 可运营态核心
 * 防止成本失控、regeneration 无限循环、多 session 并发爆炸
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';

// ============================================================================
// Types
// ============================================================================

// 会话预算配置
export interface SessionBudget {
  maxRounds: number;
  maxRegenerations: number;
  maxProviderCalls: number;
  maxValidationAttempts: number;
  maxTokenBudget?: number; // 可选最大 token 预算
  maxCostBudget?: number; // 可选最大成本预算 (USD)
}

// 并发限制配置
export interface ConcurrencyLimits {
  maxActiveSessions: number;
  maxConcurrentProviderCallsPerSession: number;
  maxParallelEvidencePods: number;
}

// 预算状态
export interface BudgetState {
  sessionId: string;
  currentRound: number;
  totalRegenerations: number;
  totalProviderCalls: number;
  totalValidationAttempts: number;
  totalTokensUsed: number;
  totalCostUSD: number;
  isPaused: boolean;
  isEscalated: boolean;
  pauseReason?: string;
  escalationReason?: string;
  warnedAt?: string;
}

// 超预算动作
export enum BudgetAction {
  PAUSE = 'pause',       // 暂停，等待用户继续
  ESCALATE = 'escalate', // 升级到用户
  SUMMARY = 'summary',   // 转入 summary/checkpoint 模式
  TERMINATE = 'terminate', // 终止会话（极端情况）
}

// 资源告警
export interface ResourceAlert {
  alertId: string;
  sessionId: string;
  level: 'warning' | 'critical';
  type: 'budget_warning' | 'budget_exceeded' | 'concurrency_warning' | 'concurrency_exceeded';
  message: string;
  currentValue: number;
  threshold: number;
  timestamp: string;
  acknowledged: boolean;
}

// ============================================================================
// Budget Guard
// ============================================================================

export class BudgetGuard {
  private budgetDir: string;
  private activeStates: Map<string, BudgetState> = new Map();
  private alerts: ResourceAlert[] = [];

  // 默认配置
  private static readonly DEFAULT_SESSION_BUDGET: SessionBudget = {
    maxRounds: 20,
    maxRegenerations: 10,
    maxProviderCalls: 50,
    maxValidationAttempts: 5,
  };

  private static readonly DEFAULT_CONCURRENCY_LIMITS: ConcurrencyLimits = {
    maxActiveSessions: 5,
    maxConcurrentProviderCallsPerSession: 3,
    maxParallelEvidencePods: 3,
  };

  constructor() {
    this.budgetDir = runtimePath('rtcm', 'budget');
    this.ensureDir(this.budgetDir);
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  // ===========================================================================
  // Session Budget Management
  // ===========================================================================

  /**
   * 初始化会话预算
   */
  initSessionBudget(sessionId: string, budget?: Partial<SessionBudget>): BudgetState {
    const config = { ...BudgetGuard.DEFAULT_SESSION_BUDGET, ...budget };
    const state: BudgetState = {
      sessionId,
      currentRound: 0,
      totalRegenerations: 0,
      totalProviderCalls: 0,
      totalValidationAttempts: 0,
      totalTokensUsed: 0,
      totalCostUSD: 0,
      isPaused: false,
      isEscalated: false,
    };

    this.activeStates.set(sessionId, state);
    this.saveState(state);
    this.saveConfig(sessionId, config);

    return state;
  }

  /**
   * 消耗预算（每轮调用后）
   */
  consumeBudget(
    sessionId: string,
    type: 'round' | 'regeneration' | 'provider_call' | 'validation' | 'token' | 'cost',
    value: number = 1
  ): { allowed: boolean; action?: BudgetAction; state: BudgetState } {
    const state = this.activeStates.get(sessionId) || this.loadState(sessionId);
    if (!state) {
      return { allowed: false, action: BudgetAction.TERMINATE, state: null as any };
    }

    const config = this.loadConfig(sessionId) || BudgetGuard.DEFAULT_SESSION_BUDGET;
    const prevState = { ...state };

    switch (type) {
      case 'round':
        state.currentRound += value;
        break;
      case 'regeneration':
        state.totalRegenerations += value;
        break;
      case 'provider_call':
        state.totalProviderCalls += value;
        break;
      case 'validation':
        state.totalValidationAttempts += value;
        break;
      case 'token':
        state.totalTokensUsed += value;
        break;
      case 'cost':
        state.totalCostUSD += value;
        break;
    }

    // 检查各项阈值
    const checkResult = this.checkThresholds(state, config);

    if (checkResult.action) {
      state.isPaused = checkResult.action === BudgetAction.PAUSE || checkResult.action === BudgetAction.TERMINATE;
      state.isEscalated = checkResult.action === BudgetAction.ESCALATE;

      if (checkResult.action === BudgetAction.PAUSE || checkResult.action === BudgetAction.ESCALATE) {
        state.pauseReason = checkResult.reason;
        state.warnedAt = new Date().toISOString();
      } else if (checkResult.action === BudgetAction.TERMINATE) {
        state.escalationReason = checkResult.reason;
      }
    }

    this.activeStates.set(sessionId, state);
    this.saveState(state);

    // 记录告警
    if (checkResult.alert) {
      this.alerts.push(checkResult.alert);
      this.saveAlert(checkResult.alert);
    }

    return {
      allowed: !state.isPaused && !state.isEscalated,
      action: checkResult.action,
      state,
    };
  }

  private checkThresholds(
    state: BudgetState,
    config: SessionBudget
  ): { action?: BudgetAction; reason?: string; alert?: ResourceAlert } {
    // 检查 round 限制
    if (state.currentRound >= config.maxRounds) {
      return {
        action: BudgetAction.ESCALATE,
        reason: `Max rounds (${config.maxRounds}) exceeded`,
        alert: this.createAlert(state, 'budget_exceeded', 'Rounds limit reached', state.currentRound, config.maxRounds),
      };
    }

    // 检查 regeneration 限制
    if (state.totalRegenerations >= config.maxRegenerations) {
      return {
        action: BudgetAction.ESCALATE,
        reason: `Max regenerations (${config.maxRegenerations}) exceeded`,
        alert: this.createAlert(state, 'budget_exceeded', 'Regenerations limit reached', state.totalRegenerations, config.maxRegenerations),
      };
    }

    // 检查 provider call 限制
    if (state.totalProviderCalls >= config.maxProviderCalls) {
      return {
        action: BudgetAction.PAUSE,
        reason: `Max provider calls (${config.maxProviderCalls}) reached`,
        alert: this.createAlert(state, 'budget_warning', 'Provider calls limit reached', state.totalProviderCalls, config.maxProviderCalls),
      };
    }

    // 检查 validation 限制
    if (state.totalValidationAttempts >= config.maxValidationAttempts) {
      return {
        action: BudgetAction.ESCALATE,
        reason: `Max validation attempts (${config.maxValidationAttempts}) exceeded`,
        alert: this.createAlert(state, 'budget_exceeded', 'Validation limit reached', state.totalValidationAttempts, config.maxValidationAttempts),
      };
    }

    // 检查 token 预算
    if (config.maxTokenBudget && state.totalTokensUsed >= config.maxTokenBudget) {
      return {
        action: BudgetAction.PAUSE,
        reason: `Token budget (${config.maxTokenBudget}) exhausted`,
        alert: this.createAlert(state, 'budget_warning', 'Token budget exhausted', state.totalTokensUsed, config.maxTokenBudget),
      };
    }

    // 检查 cost 预算
    if (config.maxCostBudget && state.totalCostUSD >= config.maxCostBudget) {
      return {
        action: BudgetAction.TERMINATE,
        reason: `Cost budget ($${config.maxCostBudget}) exhausted`,
        alert: this.createAlert(state, 'budget_exceeded', 'Cost budget exhausted', state.totalCostUSD, config.maxCostBudget),
      };
    }

    // 预警告警 (70% threshold)
    const roundWarningThreshold = config.maxRounds * 0.7;
    const regenWarningThreshold = config.maxRegenerations * 0.7;

    if (state.currentRound >= roundWarningThreshold && !state.warnedAt) {
      return {
        action: undefined,
        reason: undefined,
        alert: this.createAlert(state, 'budget_warning', 'Rounds approaching limit', state.currentRound, config.maxRounds),
      };
    }

    if (state.totalRegenerations >= regenWarningThreshold && !state.warnedAt) {
      return {
        action: undefined,
        reason: undefined,
        alert: this.createAlert(state, 'budget_warning', 'Regenerations approaching limit', state.totalRegenerations, config.maxRegenerations),
      };
    }

    return {};
  }

  private createAlert(
    state: BudgetState,
    type: ResourceAlert['type'],
    message: string,
    currentValue: number,
    threshold: number
  ): ResourceAlert {
    return {
      alertId: `alert-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      sessionId: state.sessionId,
      level: type === 'budget_exceeded' || type === 'concurrency_exceeded' ? 'critical' : 'warning',
      type,
      message,
      currentValue,
      threshold,
      timestamp: new Date().toISOString(),
      acknowledged: false,
    };
  }

  // ===========================================================================
  // Concurrency Control
  // ===========================================================================

  private activeSessions: Set<string> = new Set();
  private sessionProviderCalls: Map<string, number> = new Map();

  /**
   * 检查是否可以启动新 session
   */
  canStartSession(): { allowed: boolean; reason?: string } {
    const limits = BudgetGuard.DEFAULT_CONCURRENCY_LIMITS;

    if (this.activeSessions.size >= limits.maxActiveSessions) {
      return {
        allowed: false,
        reason: `Max active sessions (${limits.maxActiveSessions}) reached`,
      };
    }

    return { allowed: true };
  }

  /**
   * 注册新 session
   */
  registerSession(sessionId: string): boolean {
    const check = this.canStartSession();
    if (!check.allowed) return false;

    this.activeSessions.add(sessionId);
    this.sessionProviderCalls.set(sessionId, 0);
    return true;
  }

  /**
   * 注销 session
   */
  unregisterSession(sessionId: string): void {
    this.activeSessions.delete(sessionId);
    this.sessionProviderCalls.delete(sessionId);
  }

  /**
   * 检查是否可以在 session 内发起 provider call
   */
  canCallProvider(sessionId: string): boolean {
    const limits = BudgetGuard.DEFAULT_CONCURRENCY_LIMITS;
    const currentCalls = this.sessionProviderCalls.get(sessionId) || 0;

    if (currentCalls >= limits.maxConcurrentProviderCallsPerSession) {
      return false;
    }

    return true;
  }

  /**
   * 记录 provider call 开始
   */
  recordProviderCallStart(sessionId: string): void {
    const current = this.sessionProviderCalls.get(sessionId) || 0;
    this.sessionProviderCalls.set(sessionId, current + 1);
  }

  /**
   * 记录 provider call 结束
   */
  recordProviderCallEnd(sessionId: string): void {
    const current = this.sessionProviderCalls.get(sessionId) || 0;
    if (current > 0) {
      this.sessionProviderCalls.set(sessionId, current - 1);
    }
  }

  // ===========================================================================
  // State Persistence
  // ===========================================================================

  private saveState(state: BudgetState): void {
    const filePath = path.join(this.budgetDir, `${state.sessionId}_state.json`);
    fs.writeFileSync(filePath, JSON.stringify(state, null, 2), 'utf-8');
  }

  private loadState(sessionId: string): BudgetState | null {
    const filePath = path.join(this.budgetDir, `${sessionId}_state.json`);
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  }

  private saveConfig(sessionId: string, config: SessionBudget): void {
    const filePath = path.join(this.budgetDir, `${sessionId}_config.json`);
    fs.writeFileSync(filePath, JSON.stringify(config, null, 2), 'utf-8');
  }

  private loadConfig(sessionId: string): SessionBudget | null {
    const filePath = path.join(this.budgetDir, `${sessionId}_config.json`);
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  }

  private saveAlert(alert: ResourceAlert): void {
    const filePath = path.join(this.budgetDir, `${alert.sessionId}_alerts.jsonl`);
    fs.appendFileSync(filePath, JSON.stringify(alert) + '\n', 'utf-8');
  }

  // ===========================================================================
  // Public Accessors
  // ===========================================================================

  getActiveSessionCount(): number {
    return this.activeSessions.size;
  }

  getBudgetState(sessionId: string): BudgetState | null {
    return this.activeStates.get(sessionId) || this.loadState(sessionId);
  }

  getAlerts(sessionId?: string): ResourceAlert[] {
    if (sessionId) {
      return this.alerts.filter(a => a.sessionId === sessionId);
    }
    return [...this.alerts];
  }

  acknowledgeAlert(alertId: string): void {
    const alert = this.alerts.find(a => a.alertId === alertId);
    if (alert) {
      alert.acknowledged = true;
    }
  }

  /**
   * 重置 session 预算（用于续会场景）
   */
  resetSessionBudget(sessionId: string): void {
    this.activeStates.delete(sessionId);
    const state = this.initSessionBudget(sessionId);
    this.saveState(state);
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const budgetGuard = new BudgetGuard();
