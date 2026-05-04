/**
 * M14 长期自治与可控进化
 * ================================================
 * Round 14: 长期自治存活 + 可控进化 + 操作系统级资源治理
 * ================================================
 */

import { ExecutorType } from './types';
import {
  TaskPortfolio, TaskChain, TaskStatus, ApprovalState, TaskPriority,
  MultiTaskScheduler, SchedulerDecision,
  SovereigntyGovernance, HIGH_RISK_PATTERNS,
  DailyEvolutionEngine, ExperienceEntry, DailyEvolutionReport,
  AutonomousOperationEngine,
} from './autonomous_governance_round12';
import { ExecutionEvent, ExecutionEventEmitter, ResourceSnapshot } from './autonomous_runtime_round13';
import * as fs from 'fs';
import * as path from 'path';

// ============================================
// PART 1: DURABLE AUTONOMOUS RUNTIME
// ============================================

/**
 * ★ Round 14: 运行时持久化状态
 */
export interface DurableRuntimeState {
  version: string;
  timestamp: string;
  runtime_snapshot_id: string;
  portfolio: {
    tasks: TaskChain[];
    pending_queue: string[];
    frozen_tasks: string[];
  };
  scheduler: {
    last_decisions: Array<{ task_id: string; decision: string; reason: string; timestamp: string }>;
  };
  governance: {
    vetoed_instructions: Array<{ instruction: string; task_id?: string; reason: string; timestamp: string }>;
    halted: boolean;
    halt_reason?: string;
  };
  evolution: {
    patch_version: number;
    last_patch_id: string;
    active_shadows: string[];
  };
  durable_event_log_id: string;
  restored_tasks: string[];
  replayed_events: number;
  stale_runtime_detected: boolean;
}

/**
 * ★ Round 14: 持久化事件条目
 */
export interface DurableEventEntry {
  id: string;
  seq: number;
  timestamp: string;
  type: string;
  task_id?: string;
  task_type?: string;
  instruction?: string;
  success?: boolean;
  error?: string;
  governance_blocked?: boolean;
  resource_contention?: boolean;
  metadata: Record<string, any>;
}

/**
 * ★ Round 14: 持久化事件日志
 */
export class DurableEventLog {
  private logPath: string;
  private seq = 0;
  private entries: DurableEventEntry[] = [];

  constructor(persistDir: string = './data/durable') {
    this.logPath = persistDir;
    this.ensureDir();
    this.load();
  }

  private ensureDir(): void {
    try {
      if (!fs.existsSync(this.logPath)) {
        fs.mkdirSync(this.logPath, { recursive: true });
      }
    } catch { /* ignore */ }
  }

  private load(): void {
    try {
      const file = path.join(this.logPath, 'durable_event_log.jsonl');
      if (fs.existsSync(file)) {
        const data = fs.readFileSync(file, 'utf-8');
        const lines = data.trim().split('\n').filter(l => l.trim());
        this.entries = lines.map((l, i) => {
          try { return JSON.parse(l); } catch { return null; }
        }).filter(Boolean) as DurableEventEntry[];
        if (this.entries.length > 0) {
          this.seq = Math.max(...this.entries.map(e => e.seq));
        }
      }
    } catch { /* ignore */ }
  }

  /**
   * ★ Round 14: 追加持久化事件
   */
  append(event: Omit<DurableEventEntry, 'id' | 'seq'>): DurableEventEntry {
    this.seq++;
    const entry: DurableEventEntry = {
      ...event,
      id: `de_${Date.now()}_${this.seq}`,
      seq: this.seq,
    };
    this.entries.push(entry);
    this.persist();
    return entry;
  }

  private persist(): void {
    try {
      const file = path.join(this.logPath, 'durable_event_log.jsonl');
      const lines = this.entries.map(e => JSON.stringify(e)).join('\n');
      fs.writeFileSync(file, lines, 'utf-8');
    } catch { /* ignore */ }
  }

  /**
   * ★ Round 14: 获取所有条目
   */
  getEntries(): DurableEventEntry[] {
    return [...this.entries];
  }

  /**
   * ★ Round 14: 从指定序列号重放
   */
  replayFrom(seq: number): DurableEventEntry[] {
    return this.entries.filter(e => e.seq > seq);
  }

  /**
   * ★ Round 14: 获取最后 N 条
   */
  getLast(count: number): DurableEventEntry[] {
    return this.entries.slice(-count);
  }

  /**
   * ★ Round 14: 获取日志ID（最后一条序列号）
   */
  getLogId(): string {
    return `log_${this.seq}`;
  }

  /**
   * ★ Round 14: 清除旧日志
   */
  clear(): void {
    this.entries = [];
    this.seq = 0;
    try {
      const file = path.join(this.logPath, 'durable_event_log.jsonl');
      if (fs.existsSync(file)) fs.unlinkSync(file);
    } catch { /* ignore */ }
  }
}

/**
 * ★ Round 14: 持久化运行时状态
 */
export class DurableRuntimeState {
  private statePath: string;
  private state: DurableRuntimeState;

  constructor(persistDir: string = './data/durable') {
    this.statePath = persistDir;
    this.ensureDir();
    this.state = this.load();
  }

  private ensureDir(): void {
    try {
      if (!fs.existsSync(this.statePath)) {
        fs.mkdirSync(this.statePath, { recursive: true });
      }
    } catch { /* ignore */ }
  }

  private createEmptyState(): DurableRuntimeState {
    return {
      version: '1.0',
      timestamp: new Date().toISOString(),
      runtime_snapshot_id: `snap_${Date.now()}`,
      portfolio: { tasks: [], pending_queue: [], frozen_tasks: [] },
      scheduler: { last_decisions: [] },
      governance: { vetoed_instructions: [], halted: false },
      evolution: { patch_version: 0, last_patch_id: '', active_shadows: [] },
      durable_event_log_id: 'log_0',
      restored_tasks: [],
      replayed_events: 0,
      stale_runtime_detected: false,
    } as unknown as DurableRuntimeState;
  }

  /**
   * ★ Round 14: 加载状态
   */
  load(): DurableRuntimeState {
    try {
      const file = path.join(this.statePath, 'runtime_state.json');
      if (fs.existsSync(file)) {
        const data = fs.readFileSync(file, 'utf-8');
        return JSON.parse(data);
      }
    } catch { /* ignore */ }
    return this.createEmptyState();
  }

  /**
   * ★ Round 14: 保存状态
   */
  save(state: Partial<DurableRuntimeState> & { governance?: any; evolution?: any }): void {
    const s = state as any;
    if (s.governance) (this.state as any).governance = s.governance;
    if (s.evolution) (this.state as any).evolution = s.evolution;
    Object.assign(this.state, { ...state, timestamp: new Date().toISOString() });
    try {
      const file = path.join(this.statePath, 'runtime_state.json');
      fs.writeFileSync(file, JSON.stringify(this.state, null, 2), 'utf-8');
    } catch { /* ignore */ }
  }

  /**
   * ★ Round 14: 获取当前状态
   */
  getState(): DurableRuntimeState {
    return this.state as unknown as DurableRuntimeState;
  }

  /**
   * ★ Round 14: 检查是否是冷启动
   */
  isColdStart(): boolean {
    return this.state.portfolio.tasks.length === 0 && this.state.restored_tasks.length === 0;
  }

  /**
   * ★ Round 14: 快照运行时
   */
  snapshot(
    portfolio: TaskPortfolio,
    scheduler: MultiTaskScheduler,
    governance: SovereigntyGovernance,
    durableEventLog: DurableEventLog,
    evolution: { patch_version: number; last_patch_id: string; active_shadows: string[] }
  ): string {
    const portfolioState = portfolio.getAll();
    const pendingQueue = portfolioState
      .filter(t => t.status === 'pending')
      .map(t => t.task_id);
    const frozenTasks = portfolioState
      .filter(t => t.status === 'frozen')
      .map(t => t.task_id);

    const snap = {
      version: '1.0',
      timestamp: new Date().toISOString(),
      runtime_snapshot_id: `snap_${Date.now()}`,
      portfolio: {
        tasks: portfolioState,
        pending_queue: pendingQueue,
        frozen_tasks: frozenTasks,
      },
      scheduler: {
        last_decisions: scheduler.getScheduleLog().slice(-20).map(d => ({
          task_id: d.task_id,
          decision: typeof d.decision === 'string' ? d.decision : JSON.stringify(d.decision),
          reason: d.reason,
          timestamp: d.timestamp,
        })),
      },
      governance: {
        vetoed_instructions: governance.getGovernanceLog().slice(-50).map(l => ({
          instruction: l.instruction || '',
          task_id: l.task_id,
          reason: l.details?.reason || '',
          timestamp: l.timestamp,
        })),
        halted: governance.isHalted(),
      },
      evolution: {
        patch_version: evolution.patch_version,
        last_patch_id: evolution.last_patch_id,
        active_shadows: evolution.active_shadows,
      },
      durable_event_log_id: durableEventLog.getLogId(),
      restored_tasks: [],
      replayed_events: 0,
      stale_runtime_detected: false,
    };

    this.save(snap);
    return snap.runtime_snapshot_id;
  }

  /**
   * ★ Round 14: 恢复运行时
   */
  restore(
    portfolio: TaskPortfolio,
    scheduler: MultiTaskScheduler,
    governance: SovereigntyGovernance
  ): { restored: string[]; replayed: number } {
    const state = this.getState();
    const restored: string[] = [];

    // Restore tasks to portfolio
    for (const task of state.portfolio.tasks) {
      if (task.status === 'pending' || task.status === 'frozen') {
        portfolio.register(task);
        restored.push(task.task_id);
      }
    }

    // Restore governance state
    if (state.governance.halted) {
      governance.halt(state.governance.halt_reason || 'restored from cold start');
    }

    // Restore vetoed instructions
    for (const veto of state.governance.vetoed_instructions) {
      governance.veto(veto.instruction, veto.task_id, veto.reason);
    }

    // Mark state as restored
    this.save({
      ...state,
      restored_tasks: restored,
      stale_runtime_detected: false,
    });

    return { restored, replayed: state.replayed_events };
  }

  /**
   * ★ Round 14: 检测过时运行时
   */
  detectStale(lastHeartbeat: number | null, maxIdleMs: number = 5 * 60 * 1000): boolean {
    if (!lastHeartbeat) return true;
    const stale = Date.now() - lastHeartbeat > maxIdleMs;
    if (stale) {
      this.save({ ...this.getState(), stale_runtime_detected: true });
    }
    return stale;
  }
}

/**
 * ★ Round 14: 心跳监控器
 */
export class HeartbeatMonitor {
  private lastHeartbeat: number = Date.now();
  private staleDetected: boolean = false;

  /**
   * ★ Round 14: 记录心跳
   */
  beat(): void {
    this.lastHeartbeat = Date.now();
    this.staleDetected = false;
  }

  /**
   * ★ Round 14: 检查是否过时
   */
  isStale(maxIdleMs: number = 5 * 60 * 1000): boolean {
    this.staleDetected = Date.now() - this.lastHeartbeat > maxIdleMs;
    return this.staleDetected;
  }

  /**
   * ★ Round 14: 获取最后心跳时间
   */
  getLastHeartbeat(): number {
    return this.lastHeartbeat;
  }

  /**
   * ★ Round 14: 获取追踪信息
   */
  getTrace(): { last_heartbeat: number; stale_detected: boolean; uptime_ms: number } {
    return {
      last_heartbeat: this.lastHeartbeat,
      stale_detected: this.staleDetected,
      uptime_ms: Date.now() - this.lastHeartbeat,
    };
  }
}

// ============================================
// PART 2: CONTROLLED EVOLUTION GOVERNANCE
// ============================================

/**
 * ★ Round 14: 经验生命周期状态
 */
export type ExperienceLifecycle = 'draft' | 'candidate' | 'promoted' | 'blocked' | 'rolled_back';

/**
 * ★ Round 14: 带生命周期标记的经验
 */
export interface GradedExperience extends ExperienceEntry {
  lifecycle: ExperienceLifecycle;
  patch_version: number;
  promotion_timestamp?: string;
  rollback_timestamp?: string;
  promotion_reason?: string;
  rollback_reason?: string;
  shadow_mode: boolean;
}

/**
 * ★ Round 14: 策略补丁记录
 */
export interface StrategyPatch {
  id: string;
  version: number;
  timestamp: string;
  changes: Array<{
    experience_id: string;
    action: 'promote' | 'block' | 'rollback' | 'shadow_add' | 'shadow_promote' | 'shadow_discard';
    before_lifecycle: ExperienceLifecycle;
    after_lifecycle: ExperienceLifecycle;
    reason: string;
  }>;
  superseded_by?: string;
}

/**
 * ★ Round 14: 进化审计日志条目
 */
export interface EvolutionAuditEntry {
  id: string;
  timestamp: string;
  action: 'experience_promoted' | 'experience_blocked' | 'experience_rollback' | 'patch_created' | 'shadow_applied' | 'shadow_promoted' | 'shadow_discarded';
  patch_id?: string;
  experience_id?: string;
  before_state?: ExperienceLifecycle;
  after_state?: ExperienceLifecycle;
  reason: string;
  confidence?: number;
  source_count?: number;
}

/**
 * ★ Round 14: 受控进化引擎
 */
export class ControlledEvolutionEngine {
  private gradedExperiences: Map<string, GradedExperience> = new Map();
  private patches: StrategyPatch[] = [];
  private auditLog: EvolutionAuditEntry[] = [];
  private currentVersion = 0;
  private rollbackStack: StrategyPatch[] = [];

  constructor(existingExperiences: ExperienceEntry[] = []) {
    // Initialize existing experiences as draft
    for (const exp of existingExperiences) {
      const graded: GradedExperience = {
        ...exp,
        lifecycle: 'draft',
        patch_version: 0,
        shadow_mode: false,
      };
      this.gradedExperiences.set(exp.id, graded);
    }
  }

  /**
   * ★ Round 14: 添加经验（默认draft）
   */
  addExperience(exp: ExperienceEntry, shadowMode: boolean = false): void {
    const graded: GradedExperience = {
      ...exp,
      lifecycle: shadowMode ? 'draft' : 'draft',
      patch_version: this.currentVersion,
      shadow_mode: shadowMode,
    };
    this.gradedExperiences.set(exp.id, graded);
  }

  /**
   * ★ Round 14: 尝试晋升经验
   */
  promote(experienceId: string, reason: string): { success: boolean; blocked_reason?: string } {
    const exp = this.gradedExperiences.get(experienceId);
    if (!exp) return { success: false, blocked_reason: 'experience not found' };

    // Shadow mode: never promote through normal path
    if (exp.shadow_mode) {
      this.logAudit('experience_blocked', experienceId, exp.lifecycle, 'draft', 'shadow experiences must use promoteShadow()', exp.confidence, exp.source_count);
      return { success: false, blocked_reason: 'shadow experiences must use promoteShadow()' };
    }

    // Check promotion gate
    const gateResult = this.checkPromotionGate(exp);
    if (!gateResult.canPromote) {
      this.logAudit('experience_blocked', experienceId, exp.lifecycle ?? 'unknown', 'blocked', gateResult.reason ?? 'unknown', exp.confidence, exp.source_count);
      // Don't mark as blocked - stay in draft so it can be improved and retried
      return { success: false, blocked_reason: gateResult.reason };
    }

    // High-risk check: if confidence is very high but source_count is low, require approval
    if (exp.confidence >= 0.9 && exp.source_count < 2) {
      this.logAudit('experience_blocked', experienceId, exp.lifecycle, 'blocked', 'high confidence but low source count - requires approval', exp.confidence, exp.source_count);
      return { success: false, blocked_reason: 'requires approval: high confidence but insufficient sources' };
    }

    // Promote
    const prev = exp.lifecycle;
    exp.lifecycle = 'promoted';
    exp.patch_version = this.currentVersion;
    exp.promotion_timestamp = new Date().toISOString();
    exp.promotion_reason = reason;

    this.logAudit('experience_promoted', experienceId, prev, 'promoted', reason, exp.confidence, exp.source_count);

    return { success: true };
  }

  /**
   * ★ Round 14: 检查晋升门
   */
  private checkPromotionGate(exp: GradedExperience): { canPromote: boolean; reason?: string } {
    // Gate 1: Confidence threshold (>= 0.6)
    if (exp.confidence < 0.6) {
      return { canPromote: false, reason: `confidence ${exp.confidence} below 0.6 threshold` };
    }

    // Gate 2: Multi-source support (>= 2 sources)
    if (exp.source_count < 2) {
      return { canPromote: false, reason: `source_count ${exp.source_count} below 2` };
    }

    // Gate 3: Anti-pattern conflict check (can't promote if it conflicts with existing anti-pattern)
    // Note: In real implementation, would check against anti_patterns in experience base

    return { canPromote: true };
  }

  /**
   * ★ Round 14: 回滚经验
   */
  rollback(experienceId: string, reason: string): boolean {
    const exp = this.gradedExperiences.get(experienceId);
    if (!exp || exp.lifecycle !== 'promoted') return false;

    const prev = exp.lifecycle;
    exp.lifecycle = 'rolled_back';
    exp.rollback_timestamp = new Date().toISOString();
    exp.rollback_reason = reason;

    this.logAudit('experience_rollback', experienceId, prev, 'rolled_back', reason, exp.confidence, exp.source_count);

    return true;
  }

  /**
   * ★ Round 14: 以shadow模式应用经验
   */
  applyShadow(experienceId: string): boolean {
    const exp = this.gradedExperiences.get(experienceId);
    if (!exp) return false;

    exp.shadow_mode = true;
    this.logAudit('shadow_applied', experienceId, exp.lifecycle, exp.lifecycle, 'shadow mode applied', exp.confidence, exp.source_count);

    return true;
  }

  /**
   * ★ Round 14: 将shadow经验晋升为主流
   */
  promoteShadow(experienceId: string, reason: string): { success: boolean; blocked_reason?: string } {
    const exp = this.gradedExperiences.get(experienceId);
    if (!exp || !exp.shadow_mode) return { success: false, blocked_reason: 'not a shadow experience' };

    exp.shadow_mode = false;
    const result = this.promote(experienceId, `shadow validated: ${reason}`);

    if (result.success) {
      this.logAudit('shadow_promoted', experienceId, 'draft', 'promoted', reason, exp.confidence, exp.source_count);
    }

    return result;
  }

  /**
   * ★ Round 14: 创建策略补丁
   */
  createPatch(changes: StrategyPatch['changes']): StrategyPatch {
    this.currentVersion++;
    const patch: StrategyPatch = {
      id: `patch_${Date.now()}_v${this.currentVersion}`,
      version: this.currentVersion,
      timestamp: new Date().toISOString(),
      changes,
    };
    this.patches.push(patch);
    this.rollbackStack = [];
    this.logAudit('patch_created', undefined, undefined, undefined, `created patch v${this.currentVersion}`);
    return patch;
  }

  /**
   * ★ Round 14: 回滚到上一补丁
   */
  rollbackToPreviousPatch(): StrategyPatch | null {
    if (this.patches.length < 2) return null;

    const currentPatch = this.patches[this.patches.length - 1];
    const prevPatch = this.patches[this.patches.length - 2];

    // Mark current as superseded
    currentPatch.superseded_by = prevPatch.id;

    // Revert changes from current patch
    for (const change of currentPatch.changes) {
      const exp = this.gradedExperiences.get(change.experience_id);
      if (exp) {
        exp.lifecycle = change.before_lifecycle;
        this.logAudit('experience_rollback', change.experience_id, change.after_lifecycle, change.before_lifecycle, `rollback: ${change.reason}`, exp.confidence, exp.source_count);
      }
    }

    this.rollbackStack.push(currentPatch);
    return prevPatch;
  }

  /**
   * ★ Round 14: 获取可用的（promoted）经验
   */
  getActiveExperiences(): GradedExperience[] {
    return Array.from(this.gradedExperiences.values()).filter(e => e.lifecycle === 'promoted' && !e.shadow_mode);
  }

  /**
   * ★ Round 14: 获取所有经验
   */
  getAllExperiences(): GradedExperience[] {
    return Array.from(this.gradedExperiences.values());
  }

  /**
   * ★ Round 14: 获取审计日志
   */
  getAuditLog(): EvolutionAuditEntry[] {
    return [...this.auditLog];
  }

  /**
   * ★ Round 14: 获取补丁历史
   */
  getPatches(): StrategyPatch[] {
    return [...this.patches];
  }

  /**
   * ★ Round 14: 获取当前版本
   */
  getCurrentVersion(): number {
    return this.currentVersion;
  }

  private logAudit(
    action: EvolutionAuditEntry['action'],
    experienceId: string | undefined,
    before_state: ExperienceLifecycle | undefined,
    after_state: ExperienceLifecycle | undefined,
    reason: string,
    confidence?: number,
    source_count?: number
  ): void {
    this.auditLog.push({
      id: `audit_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      timestamp: new Date().toISOString(),
      action,
      experience_id: experienceId,
      before_state,
      after_state,
      reason,
      confidence,
      source_count,
    });
  }
}

// ============================================
// PART 3: OS-LIKE RESOURCE SCHEDULING
// ============================================

/**
 * ★ Round 14: 资源锁类型
 */
export type LockMode = 'shared' | 'exclusive' | 'preemptible';

/**
 * ★ Round 14: 资源锁状态
 */
export interface ResourceLock {
  lock_id: string;
  resource_type: string;
  resource_id?: string;
  mode: LockMode;
  holder_task_id: string;
  acquired_at: string;
  last_renewed_at: string;
  preemptible: boolean;
  priority: number;
}

/**
 * ★ Round 14: 资源调度追踪条目
 */
export interface ResourceSchedulingTrace {
  timestamp: string;
  action: 'resource_lock_acquired' | 'resource_preempted' | 'resource_released' | 'resource_renewed' | 'starvation_risk' | 'fairness_adjustment' | 'lock_denied';
  lock_id?: string;
  resource_type: string;
  task_id?: string;
  from_task_id?: string;
  mode?: LockMode;
  reason: string;
  wait_time_ms?: number;
  fairness_score?: number;
}

/**
 * ★ Round 14: 资源锁管理器
 */
export class ResourceLockManager {
  private locks: Map<string, ResourceLock> = new Map();
  private trace: ResourceSchedulingTrace[] = [];
  private taskWaitTimes: Map<string, number> = new Map(); // task_id -> wait time ms
  private taskStartTimes: Map<string, number> = new Map(); // task_id -> start time ms

  /**
   * ★ Round 14: 请求资源锁
   */
  acquire(
    resourceType: string,
    resourceId: string | undefined,
    taskId: string,
    mode: LockMode,
    priority: number
  ): { acquired: boolean; lock_id?: string; denied_reason?: string; preempted_task_id?: string } {
    const lockKey = `${resourceType}:${resourceId || 'default'}`;
    const existing = this.locks.get(lockKey);

    if (existing) {
      // Check if can share
      if (existing.mode === 'shared' && mode === 'shared') {
        const lock = this.createLock(resourceType, resourceId, taskId, mode, priority);
        this.locks.set(lockKey, lock);
        this.logTrace('resource_lock_acquired', resourceType, taskId, undefined, mode, 'shared lock granted');
        return { acquired: true, lock_id: lock.lock_id };
      }

      // Check preemption - preemptible mode can preempt shared locks or lower priority preemptible locks
      if (mode === 'exclusive' || mode === 'preemptible') {
        // Can preempt if: existing is preemptible OR existing is shared (lower priority lock type)
        const canPreempt = existing.preemptible || existing.mode === 'shared';
        if (canPreempt && priority > existing.priority) {
          const preemptedTaskId = existing.holder_task_id;
          this.release(existing.lock_id, 'preempted by higher priority');
          const lock = this.createLock(resourceType, resourceId, taskId, mode, priority);
          this.locks.set(lockKey, lock);
          this.logTrace('resource_preempted', resourceType, taskId, preemptedTaskId, mode, 'preempted lower priority task');
          return { acquired: true, lock_id: lock.lock_id, preempted_task_id: preemptedTaskId };
        }

        this.logTrace('lock_denied', resourceType, taskId, existing.holder_task_id, mode, 'lock held by lower or equal priority task');
        return { acquired: false, denied_reason: 'lock held by lower or equal priority task' };
      }

      this.logTrace('lock_denied', resourceType, taskId, existing.holder_task_id, mode, 'incompatible lock mode');
      return { acquired: false, denied_reason: 'incompatible lock mode' };
    }

    // No existing lock
    const lock = this.createLock(resourceType, resourceId, taskId, mode, priority);
    this.locks.set(lockKey, lock);
    this.taskStartTimes.set(taskId, Date.now());
    this.logTrace('resource_lock_acquired', resourceType, taskId, undefined, mode, 'new lock acquired');
    return { acquired: true, lock_id: lock.lock_id };
  }

  /**
   * ★ Round 14: 续期锁
   */
  renew(lockId: string): boolean {
    for (const [key, lock] of this.locks) {
      if (lock.lock_id === lockId) {
        lock.last_renewed_at = new Date().toISOString();
        this.logTrace('resource_renewed', lock.resource_type, lock.holder_task_id, undefined, lock.mode, 'lock renewed');
        return true;
      }
    }
    return false;
  }

  /**
   * ★ Round 14: 释放锁
   */
  release(lockId: string, reason: string = 'normal'): boolean {
    for (const [key, lock] of this.locks) {
      if (lock.lock_id === lockId) {
        const taskId = lock.holder_task_id;
        this.taskWaitTimes.delete(taskId);
        this.taskStartTimes.delete(taskId);
        this.locks.delete(key);
        this.logTrace('resource_released', lock.resource_type, taskId, undefined, lock.mode, reason);
        return true;
      }
    }
    return false;
  }

  /**
   * ★ Round 14: 强制释放（用于超时或抢占）
   */
  forceRelease(lockId: string, reason: string): boolean {
    return this.release(lockId, `force_release: ${reason}`);
  }

  /**
   * ★ Round 14: 获取任务的等待时间
   */
  getTaskWaitTime(taskId: string): number {
    const startTime = this.taskStartTimes.get(taskId);
    if (!startTime) return 0;
    return Date.now() - startTime;
  }

  /**
   * ★ Round 14: 检测饥饿风险
   */
  detectStarvationRisk(maxWaitMs: number = 60000): string[] {
    const atRisk: string[] = [];
    for (const [taskId, waitTime] of this.taskWaitTimes) {
      if (waitTime > maxWaitMs) {
        atRisk.push(taskId);
        this.logTrace('starvation_risk', 'any', taskId, undefined, undefined, `wait time ${waitTime}ms exceeds ${maxWaitMs}ms`);
      }
    }
    return atRisk;
  }

  /**
   * ★ Round 14: 记录任务开始等待
   */
  recordTaskWait(taskId: string): void {
    this.taskWaitTimes.set(taskId, Date.now());
  }

  /**
   * ★ Round 14: 获取公平性分数（0-1，越高越公平）
   */
  getFairnessScore(): number {
    const waitTimes = Array.from(this.taskWaitTimes.values());
    if (waitTimes.length === 0) return 1.0;
    if (waitTimes.length === 1) return 1.0;

    const avg = waitTimes.reduce((a, b) => a + b, 0) / waitTimes.length;
    const variance = waitTimes.reduce((sum, w) => sum + Math.pow(w - avg, 2), 0) / waitTimes.length;
    const stdDev = Math.sqrt(variance);

    // Normalize: low variance = high fairness
    const normalizedStdDev = Math.min(stdDev / avg, 1);
    const fairness = 1 - normalizedStdDev;

    if (fairness < 0.7) {
      this.logTrace('fairness_adjustment', 'system', undefined, undefined, undefined, `fairness score ${fairness.toFixed(2)} below 0.7 threshold`, undefined, fairness);
    }

    return Math.max(0, Math.min(1, fairness));
  }

  /**
   * ★ Round 14: 获取持有中的锁
   */
  getHeldLocks(): ResourceLock[] {
    return Array.from(this.locks.values());
  }

  /**
   * ★ Round 14: 获取任务的锁
   */
  getTaskLocks(taskId: string): ResourceLock[] {
    return Array.from(this.locks.values()).filter(l => l.holder_task_id === taskId);
  }

  /**
   * ★ Round 14: 获取调度追踪
   */
  getTrace(): ResourceSchedulingTrace[] {
    return [...this.trace];
  }

  private createLock(
    resourceType: string,
    resourceId: string | undefined,
    taskId: string,
    mode: LockMode,
    priority: number
  ): ResourceLock {
    const now = new Date().toISOString();
    return {
      lock_id: `lock_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      resource_type: resourceType,
      resource_id: resourceId,
      mode,
      holder_task_id: taskId,
      acquired_at: now,
      last_renewed_at: now,
      preemptible: mode === 'preemptible',
      priority,
    };
  }

  private logTrace(
    action: ResourceSchedulingTrace['action'],
    resourceType: string,
    taskId: string | undefined,
    fromTaskId: string | undefined,
    mode: LockMode | undefined,
    reason: string,
    waitTimeMs?: number,
    fairnessScore?: number
  ): void {
    this.trace.push({
      timestamp: new Date().toISOString(),
      action,
      resource_type: resourceType,
      task_id: taskId,
      from_task_id: fromTaskId,
      mode,
      reason,
      wait_time_ms: waitTimeMs,
      fairness_score: fairnessScore,
    });
  }
}

// ============================================
// PART 4: DURABLE AUTONOMOUS ENGINE (整合)
// ============================================

/**
 * ★ Round 14: 持久化运行时封装（整合所有子系统）
 */
export class DurableAutonomousEngine {
  portfolio: TaskPortfolio;
  scheduler: MultiTaskScheduler;
  governance: SovereigntyGovernance;
  evolution: ControlledEvolutionEngine;
  resourceLocks: ResourceLockManager;
  durableEventLog: DurableEventLog;
  durableState: DurableRuntimeState;
  heartbeat: HeartbeatMonitor;

  private persistDir: string;

  constructor(persistDir: string = './data/durable') {
    this.persistDir = persistDir;
    this.portfolio = new TaskPortfolio();
    this.scheduler = new MultiTaskScheduler(this.portfolio);
    this.governance = new SovereigntyGovernance();
    this.evolution = new ControlledEvolutionEngine();
    this.resourceLocks = new ResourceLockManager();
    this.durableEventLog = new DurableEventLog(persistDir);
    this.durableState = new DurableRuntimeState(persistDir);
    this.heartbeat = new HeartbeatMonitor();

    // Restore from cold start if available
    const { restored, replayed } = this.durableState.restore(this.portfolio, this.scheduler, this.governance);
    if (restored.length > 0) {
      this.heartbeat.beat();
    }
  }

  /**
   * ★ Round 14: 快照运行时状态
   */
  snapshotRuntime(): string {
    this.heartbeat.beat();
    return this.durableState.snapshot(
      this.portfolio,
      this.scheduler,
      this.governance,
      this.durableEventLog,
      {
        patch_version: this.evolution.getCurrentVersion(),
        last_patch_id: this.evolution.getPatches().slice(-1)[0]?.id || '',
        active_shadows: this.evolution.getAllExperiences().filter(e => e.shadow_mode).map(e => e.id),
      }
    );
  }

  /**
   * ★ Round 14: 持久化运行时并获取追踪
   */
  getDurabilityTrace(): {
    runtime_snapshot_id: string;
    durable_event_log_id: string;
    restored_tasks: string[];
    replayed_events: number;
    stale_runtime_detected: boolean;
    last_heartbeat: number;
    fairness_score: number;
    starvation_risks: string[];
  } {
    const state = this.durableState.getState();
    const fairness = this.resourceLocks.getFairnessScore();
    const starvationRisks = this.resourceLocks.detectStarvationRisk();

    return {
      runtime_snapshot_id: state.runtime_snapshot_id,
      durable_event_log_id: this.durableEventLog.getLogId(),
      restored_tasks: state.restored_tasks,
      replayed_events: state.replayed_events,
      stale_runtime_detected: state.stale_runtime_detected,
      last_heartbeat: this.heartbeat.getLastHeartbeat(),
      fairness_score: fairness,
      starvation_risks: starvationRisks,
    };
  }

  /**
   * ★ Round 14: 获取进化审计日志
   */
  getEvolutionAuditLog(): EvolutionAuditEntry[] {
    return this.evolution.getAuditLog();
  }

  /**
   * ★ Round 14: 获取资源调度追踪
   */
  getResourceSchedulingTrace(): ResourceSchedulingTrace[] {
    return this.resourceLocks.getTrace();
  }
}

// ============================================
// 单例
// ============================================
export const durableAutonomousEngine = new DurableAutonomousEngine();
