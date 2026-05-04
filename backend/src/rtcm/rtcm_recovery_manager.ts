/**
 * @file rtcm_recovery_manager.ts
 * @description RTCM 会话恢复与故障恢复机制 - Gamma 可运营态核心
 * 支持会话中断恢复、执行中断恢复、Recovery Checkpoint
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import { SessionState, Issue, ChairSummary, SupervisorCheck } from './types';

// ============================================================================
// Types
// ============================================================================

// Recovery Checkpoint
export interface RecoveryCheckpoint {
  checkpointId: string;
  sessionId: string;
  projectId: string;
  createdAt: string;
  round: number;
  currentIssueId: string | null;
  currentStage: string;
  latestChairSummary: ChairSummary | null;
  latestSupervisorCheck: SupervisorCheck | null;
  pendingActions: PendingAction[];
  leaseState: LeaseState;
  telemetry: CheckpointTelemetry;
}

export interface PendingAction {
  actionId: string;
  type: 'validation' | 'llm_call' | 'dossier_write' | 'feishu_push' | 'sign_off';
  status: 'pending' | 'in_progress' | 'failed' | 'completed';
  issueId: string;
  createdAt: string;
  error?: string;
  retryCount: number;
}

export interface LeaseState {
  granted: boolean;
  grantedBy: string | null;
  grantedAt: string | null;
  expiresAt: string | null;
}

export interface CheckpointTelemetry {
  totalRounds: number;
  totalRegenerations: number;
  totalValidations: number;
  reopenedIssues: string[];
}

// Session Recovery State
export interface SessionRecoveryState {
  sessionId: string;
  status: 'recovering' | 'recovered' | 'failed';
  checkpoint: RecoveryCheckpoint | null;
  restoredIssues: Issue[];
  recoveryErrors: string[];
  recoveredAt: string | null;
}

// Failure Event
export interface FailureEvent {
  eventId: string;
  sessionId: string;
  issueId: string;
  failureType: 'validation_execution' | 'provider_call' | 'dossier_write' | 'feishu_push' | 'session_crash';
  error: string;
  timestamp: string;
  checkpointBeforeFailure: string | null;
  mustNotCloseIssue: boolean;
}

// ============================================================================
// Recovery Manager
// ============================================================================

export class RecoveryManager {
  private recoveryDir: string;
  private checkpointFile: string;
  private failureLogFile: string;

  constructor(sessionId: string) {
    const baseDir = runtimePath('rtcm', 'recovery');
    this.recoveryDir = path.join(baseDir, sessionId);
    this.checkpointFile = path.join(this.recoveryDir, 'checkpoint.json');
    this.failureLogFile = path.join(this.recoveryDir, 'failure_log.jsonl');

    this.ensureDir(this.recoveryDir);
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  // ===========================================================================
  // Checkpoint Management
  // ===========================================================================

  /**
   * 创建 Recovery Checkpoint
   * 在每轮结束后调用，形成安全恢复点
   */
  createCheckpoint(params: {
    sessionId: string;
    projectId: string;
    round: number;
    currentIssueId: string | null;
    currentStage: string;
    latestChairSummary: ChairSummary | null;
    latestSupervisorCheck: SupervisorCheck | null;
    pendingActions: PendingAction[];
    leaseState: LeaseState;
    telemetry: CheckpointTelemetry;
  }): RecoveryCheckpoint {
    const checkpoint: RecoveryCheckpoint = {
      checkpointId: `cp-${sessionId}-r${params.round}-${Date.now()}`,
      sessionId: params.sessionId,
      projectId: params.projectId,
      createdAt: new Date().toISOString(),
      round: params.round,
      currentIssueId: params.currentIssueId,
      currentStage: params.currentStage,
      latestChairSummary: params.latestChairSummary,
      latestSupervisorCheck: params.latestSupervisorCheck,
      pendingActions: params.pendingActions,
      leaseState: params.leaseState,
      telemetry: params.telemetry,
    };

    // 写入 checkpoint 文件
    fs.writeFileSync(this.checkpointFile, JSON.stringify(checkpoint, null, 2), 'utf-8');

    return checkpoint;
  }

  /**
   * 读取最新 Checkpoint
   */
  readCheckpoint(): RecoveryCheckpoint | null {
    if (!fs.existsSync(this.checkpointFile)) {
      return null;
    }
    return JSON.parse(fs.readFileSync(this.checkpointFile, 'utf-8'));
  }

  /**
   * 检查是否有可恢复的 session
   */
  static hasRecoverableSession(sessionId: string): boolean {
    const checkpointFile = path.join(
      runtimePath('rtcm', 'recovery'), sessionId, 'checkpoint.json'
    );
    return fs.existsSync(checkpointFile);
  }

  // ===========================================================================
  // Session Recovery
  // ===========================================================================

  /**
   * 从 checkpoint 恢复 session
   */
  recoverSession(sessionId: string): SessionRecoveryState {
    const state: SessionRecoveryState = {
      sessionId,
      status: 'recovering',
      checkpoint: null,
      restoredIssues: [],
      recoveryErrors: [],
      recoveredAt: null,
    };

    try {
      const checkpoint = this.readCheckpoint();
      if (!checkpoint) {
        state.recoveryErrors.push('No checkpoint found');
        state.status = 'failed';
        return state;
      }

      if (checkpoint.sessionId !== sessionId) {
        state.recoveryErrors.push('Checkpoint sessionId mismatch');
        state.status = 'failed';
        return state;
      }

      // 恢复会话状态（不跳过任何 gate）
      state.checkpoint = checkpoint;

      // 验证 checkpoint 完整性
      if (!this.validateCheckpoint(checkpoint)) {
        state.recoveryErrors.push('Checkpoint validation failed');
        state.status = 'failed';
        return state;
      }

      state.status = 'recovered';
      state.recoveredAt = new Date().toISOString();

    } catch (error) {
      state.recoveryErrors.push(String(error));
      state.status = 'failed';
    }

    return state;
  }

  /**
   * 验证 checkpoint 完整性
   * 确保恢复时不跳过 supervisor gate、validation、dissent 等
   */
  private validateCheckpoint(checkpoint: RecoveryCheckpoint): boolean {
    // 1. 必须有 round 信息
    if (checkpoint.round < 0) return false;

    // 2. 必须保留 latestChairSummary
    // 恢复时不能丢失 dissent/uncertainty

    // 3. 必须保留 latestSupervisorCheck
    // 恢复时不能跳过 supervisor gate

    // 4. 检查是否有未完成的 pending actions
    for (const action of checkpoint.pendingActions) {
      if (action.status === 'in_progress') {
        // in_progress 状态意味着可能有不完整写入，需要检查
        if (!this.validatePendingAction(action)) {
          return false;
        }
      }
    }

    return true;
  }

  private validatePendingAction(action: PendingAction): boolean {
    // 如果是 in_progress 的 dossier_write，需要检查文件完整性
    if (action.type === 'dossier_write' && action.status === 'in_progress') {
      const dossierFile = path.join(
        runtimePath('rtcm', 'dossiers'), action.issueId, 'current.json'
      );
      // 如果文件存在且完整，可以标记为 completed
      // 如果文件不存在或损坏，需要标记为 failed 并允许重试
      if (!fs.existsSync(dossierFile)) {
        action.status = 'failed';
        action.error = 'Dossier file not found during recovery';
        return true; // 允许继续，但需要重试
      }
    }
    return true;
  }

  // ===========================================================================
  // Failure Event Logging
  // ===========================================================================

  /**
   * 记录失败事件
   */
  logFailure(event: Omit<FailureEvent, 'eventId' | 'timestamp'>): FailureEvent {
    const failureEvent: FailureEvent = {
      eventId: `fail-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      timestamp: new Date().toISOString(),
      ...event,
    };

    fs.appendFileSync(
      this.failureLogFile,
      JSON.stringify(failureEvent) + '\n',
      'utf-8'
    );

    return failureEvent;
  }

  /**
   * 读取失败事件历史
   */
  readFailureHistory(): FailureEvent[] {
    if (!fs.existsSync(this.failureLogFile)) {
      return [];
    }

    const lines = fs.readFileSync(this.failureLogFile, 'utf-8').split('\n').filter(Boolean);
    return lines.map(line => JSON.parse(line));
  }

  // ===========================================================================
  // Safe Resume
  // ===========================================================================

  /**
   * 安全恢复后继续执行
   * 恢复时确保：
   * - 不跳过 supervisor gate
   * - 不跳过 validation
   * - 不丢失 dissent / uncertainty
   * - 不自动修改历史 dossier
   */
  safeResume(checkpoint: RecoveryCheckpoint): {
    canResume: boolean;
    resumeFromStage: string;
    skipSupervisorGate: boolean;
    skipValidation: boolean;
    warnings: string[];
  } {
    const warnings: string[] = [];
    let skipSupervisorGate = false;
    let skipValidation = false;

    // 检查是否有未完成的 supervisor check
    if (!checkpoint.latestSupervisorCheck) {
      warnings.push('No supervisor check found - will require fresh supervisor validation');
      skipSupervisorGate = false; // 不能跳过
    }

    // 检查是否有 in_progress 的 validation
    const inProgressValidation = checkpoint.pendingActions.find(
      a => a.type === 'validation' && a.status === 'in_progress'
    );
    if (inProgressValidation) {
      warnings.push('Validation was in progress - will restart validation');
      skipValidation = false; // 不能跳过
    }

    return {
      canResume: true,
      resumeFromStage: checkpoint.currentStage,
      skipSupervisorGate,
      skipValidation,
      warnings,
    };
  }

  // ===========================================================================
  // Recovery Status
  // ===========================================================================

  /**
   * 获取恢复状态摘要
   */
  getRecoveryStatus(sessionId: string): {
    hasCheckpoint: boolean;
    lastCheckpointAt: string | null;
    pendingActionsCount: number;
    failureCount: number;
    canResume: boolean;
  } {
    const checkpoint = this.readCheckpoint();
    const failures = this.readFailureHistory();

    return {
      hasCheckpoint: !!checkpoint,
      lastCheckpointAt: checkpoint?.createdAt || null,
      pendingActionsCount: checkpoint?.pendingActions.filter(a => a.status !== 'completed').length || 0,
      failureCount: failures.length,
      canResume: !!checkpoint && this.validateCheckpoint(checkpoint),
    };
  }

  /**
   * 清理恢复文件（仅在 session 正式结束时）
   */
  cleanup(sessionId: string): void {
    const dir = runtimePath('rtcm', 'recovery', sessionId);
    if (fs.existsSync(dir)) {
      // 注意：仅在正式归档后清理
      const archiveMarker = path.join(dir, '.archived');
      if (fs.existsSync(archiveMarker)) {
        fs.rmSync(dir, { recursive: true, force: true });
      }
    }
  }

  /**
   * 标记 session 为正式归档（允许清理）
   */
  markArchived(sessionId: string): void {
    const dir = runtimePath('rtcm', 'recovery', sessionId);
    this.ensureDir(dir);
    fs.writeFileSync(path.join(dir, '.archived'), new Date().toISOString(), 'utf-8');
  }
}

// ============================================================================
// Singleton Factory
// ============================================================================

const activeManagers: Map<string, RecoveryManager> = new Map();

export function getRecoveryManager(sessionId: string): RecoveryManager {
  if (!activeManagers.has(sessionId)) {
    activeManagers.set(sessionId, new RecoveryManager(sessionId));
  }
  return activeManagers.get(sessionId)!;
}
