/**
 * @file queue_manager.ts
 * @description U8: 任务排队与冷静期
 * 将结果写入队列，执行冷静期检查
 */

import * as fs from 'fs';
import * as path from 'path';
import { runtimePath } from '../runtime_paths';
import {
  UpgradeCenterReport,
  UpgradeQueue,
  ExperimentTask,
  CooldownRegistry,
  CooldownEntry,
} from './types';

const STATE_DIR = runtimePath('upgrade-center', 'state');
const COOLDOWN_DAYS = 7;
// R209: Sandbox script paths — must match sandbox_planner.ts naming convention
const SANDBOX_DIR = runtimePath('upgrade-center', 'sandbox');
const VERIFY_SCRIPTS_DIR = path.join(SANDBOX_DIR, 'verify_scripts');
const ROLLBACK_SCRIPTS_DIR = path.join(SANDBOX_DIR, 'rollback_templates');

/**
 * R209: Compute sandbox script paths from candidate_id.
 * Uses the same naming rule as sandbox_planner.ts:
 * candidate_id with all non-alphanumeric chars replaced by '_'.
 * e.g. "demand-1776968732049-dspy-001" → "demand_1776968732049_dspy_001"
 */
function candidateIdToScriptName(candidateId: string, suffix: string): string {
  return candidateId.replace(/[^a-zA-Z0-9]/g, '_') + suffix;
}

export class QueueManager {
  /**
   * 入队实验层任务
   */
  public async enqueue(report: UpgradeCenterReport): Promise<void> {
    console.log('[QueueManager] 入队实验任务...');

    const queue = this.loadQueue();
    const now = new Date().toISOString();

    // R227-fix: Use experiment_queue_candidates (TieredCandidate[]) to preserve provenance metadata
    // Previously used report.experiment_queue (string[]) which lost filter_result/execution_stage/predicted
    for (const candidate of report.experiment_queue_candidates) {
      const candidateId = candidate.candidate_id;
      if (!this.isInCooldown(candidateId)) {
        // R209: Compute script paths from candidate_id (matches sandbox_planner.ts naming)
        const verifyScriptName = candidateIdToScriptName(candidateId, '_verify.sh');
        const rollbackScriptName = candidateIdToScriptName(candidateId, '_rollback.sh');
        const verifyScriptPath = path.join(VERIFY_SCRIPTS_DIR, verifyScriptName);
        const rollbackScriptPath = path.join(ROLLBACK_SCRIPTS_DIR, rollbackScriptName);

        // R227-fix: Preserve pipeline provenance metadata in task for sandbox ground truth segmentation
        const task: ExperimentTask = {
          id: `task-${Date.now()}-${candidateId}`,
          candidate_id: candidateId,
          status: 'pending',
          type: 'sandbox_validation',
          created_at: now,
          // R209: Script paths for executor consumption
          verify_script_path: verifyScriptPath,
          rollback_script_path: rollbackScriptPath,
          // R227-fix: provenance fields from pipeline
          filter_result: candidate.filter_result,
          execution_stage: 'queued_for_experiment',
          predicted: candidate.predicted_value,
          tier: candidate.tier,
          ltv: candidate.long_term_value,
        };
        queue.experiment_tasks.push(task);
      }
    }

    for (const candidate of report.candidates_for_approval) {
      this.registerForCooldown(candidate.candidate_id, candidate.project || 'unknown');
    }

    this.saveQueue(queue);
    console.log(`[QueueManager] 入队完成，队列大小: ${queue.experiment_tasks.length}`);
  }

  /**
   * 检查冷静期
   */
  public async checkCooldowns(): Promise<void> {
    console.log('[QueueManager] 检查冷静期...');

    const cooldown = this.loadCooldown();
    const now = new Date();

    const active: CooldownEntry[] = [];
    let expiredCount = 0;

    for (const entry of cooldown.entries) {
      const expires = new Date(entry.cooldown_expires);
      if (expires > now) {
        active.push(entry);
      } else {
        expiredCount++;
      }
    }

    cooldown.entries = active;
    this.saveCooldown(cooldown);

    console.log(`[QueueManager] 冷静期检查完成: ${expiredCount} 个过期, ${active.length} 个有效`);
  }

  /**
   * R201: 处理 Feishu 审批结果，驱动状态迁移
   *
   * 来自 governance_upgrade_center_approval_result demands 的三种结果：
   *   approved → 加入实验队列（绕过 U2-U6，直接入队）
   *   rejected → 注册冷静期
   *   observe  → 加入观察池
   *
   * @param demands governance_upgrade_center_approval_result demands
   */
  public async handleApprovalResultDemands(demands: Array<{
    id: string;
    source: string;
    governance_priority: string;
    governance_data: Record<string, string>;
  }>): Promise<void> {
    console.log(`[QueueManager] R201: 处理 ${demands.length} 个 approval_result demands...`);

    for (const demand of demands) {
      const gd = demand.governance_data || {};
      const result = gd.result || 'unknown';
      const candidateId = gd.candidate_id || 'unknown';
      const guidance = gd.governance_guidance || '';

      if (result === 'approved' || guidance === 'enqueue_to_experiment') {
        // R201: 审批通过 → 直接加入实验队列
        // R202 幂等修复: 检查是否已有相同 candidate 的 feishu_approval_approved 任务（防止重复 enqueue）
        if (!this.isInCooldown(candidateId)) {
          const queue = this.loadQueue();
          const alreadyEnqueued = queue.experiment_tasks.some(
            (t) => t.candidate_id === candidateId && (t.type as any) === 'feishu_approval_approved'
          );
          if (alreadyEnqueued) {
            console.log(`[QueueManager] R202: ${candidateId} already enqueued as feishu_approval_approved — skipping duplicate`);
          } else {
            const now = new Date().toISOString();
            const task: ExperimentTask = {
              id: `task-r201-${Date.now()}-${candidateId.replace(/[^a-zA-Z0-9]/g, '-')}`,
              candidate_id: candidateId,
              status: 'pending',
              type: 'feishu_approval_approved' as any,
              created_at: now,
            };
            queue.experiment_tasks.push(task);
            this.saveQueue(queue);
            console.log(`[QueueManager] R201: approved → enqueued ${candidateId}`);
          }
        } else {
          console.log(`[QueueManager] R201: approved but in cooldown → skipping ${candidateId}`);
        }
      } else if (result === 'rejected' || guidance === 'register_cooldown') {
        // R201: 审批拒绝 → 注册冷静期
        // R202 幂等修复: 检查是否已有相同 candidate 的有效 cooldown（防止重复写入）
        const cooldown = this.loadCooldown();
        const hash = this.hashCandidate(candidateId);
        const now = new Date();
        const alreadyCooling = cooldown.entries.some(
          (e) => e.candidate_hash === hash && new Date(e.cooldown_expires) > now
        );
        if (alreadyCooling) {
          console.log(`[QueueManager] R202: ${candidateId} already in cooldown — skipping duplicate`);
        } else {
          this.registerForCooldownPublic(candidateId, 'feishu_rejected');
          console.log(`[QueueManager] R201: rejected → cooldown registered for ${candidateId}`);
        }
      } else if (result === 'observe' || guidance === 'add_to_observation') {
        // R201: 观察池
        // R202 幂等修复: 检查是否已有相同 candidate（防止重复累积）
        const queue = this.loadQueue();
        if (queue.pending_verification.includes(candidateId)) {
          console.log(`[QueueManager] R202: ${candidateId} already in observation_pool — skipping duplicate`);
        } else {
          queue.pending_verification.push(candidateId);
          this.saveQueue(queue);
          console.log(`[QueueManager] R201: observe → added to observation pool ${candidateId}`);
        }
      } else {
        console.warn(`[QueueManager] R201: unknown result="${result}" for ${candidateId} — skipping`);
      }
    }

    console.log(`[QueueManager] R201: 处理完成`);
  }

  /**
   * 注册冷静期（公开版本，供外部调用）
   */
  public registerForCooldownPublic(candidateId: string, reason: string = 'approval_rejected'): void {
    const cooldown = this.loadCooldown();

    const entry: CooldownEntry = {
      candidate_hash: this.hashCandidate(candidateId),
      project: candidateId,  // project 字段用 candidateId 代替
      rejected_at: new Date().toISOString(),
      cooldown_expires: this.calculateExpiresDate(),
      reason,
    };

    cooldown.entries.push(entry);
    this.saveCooldown(cooldown);
  }

  /**
   * 获取队列状态
   */
  public async getQueueStatus(): Promise<{
    pending_approvals: number;
    experiment_queue_size: number;
    observation_pool_size: number;
  }> {
    const queue = this.loadQueue();
    const pending = queue.experiment_tasks.filter((t) => t.status === 'pending');

    return {
      pending_approvals: pending.length,
      experiment_queue_size: queue.experiment_tasks.length,
      observation_pool_size: queue.pending_verification.length,
    };
  }

  /**
   * 获取 Top-N 实验队列候选（Round 10 U8 主链消费最小化）
   * 返回结构化摘要而非全量队列，主链可理解、可记录
   */
  public async getTopCandidates(topN: number = 5): Promise<Array<{
    candidate_id: string;
    status: string;
    created_at: string;
    type: string;
  }>> {
    const queue = this.loadQueue();
    const pending = queue.experiment_tasks
      .filter((t) => t.status === 'pending')
      .slice(0, topN);

    return pending.map((t) => ({
      candidate_id: t.candidate_id,
      status: t.status,
      created_at: t.created_at,
      type: t.type,
    }));
  }

  /**
   * 加载队列
   */
  private loadQueue(): UpgradeQueue {
    const filePath = path.join(STATE_DIR, 'experiment_queue.json');

    if (fs.existsSync(filePath)) {
      try {
        const content = fs.readFileSync(filePath, 'utf-8');
        return JSON.parse(content);
      } catch (error) {
        console.warn(`[QueueManager] 加载队列失败: ${error}`);
      }
    }

    return {
      date: new Date().toISOString().split('T')[0],
      experiment_tasks: [],
      pending_verification: [],
    };
  }

  /**
   * 保存队列
   */
  private saveQueue(queue: UpgradeQueue): void {
    this.ensureStateDir();
    const filePath = path.join(STATE_DIR, 'experiment_queue.json');
    fs.writeFileSync(filePath, JSON.stringify(queue, null, 2), 'utf-8');
  }

  /**
   * 加载冷静期注册表
   */
  private loadCooldown(): CooldownRegistry {
    const filePath = path.join(STATE_DIR, 'cooldown_registry.json');

    if (fs.existsSync(filePath)) {
      try {
        const content = fs.readFileSync(filePath, 'utf-8');
        return JSON.parse(content);
      } catch (error) {
        console.warn(`[QueueManager] 加载冷静期注册表失败: ${error}`);
      }
    }

    return { entries: [] };
  }

  /**
   * 保存冷静期注册表
   */
  private saveCooldown(cooldown: CooldownRegistry): void {
    this.ensureStateDir();
    const filePath = path.join(STATE_DIR, 'cooldown_registry.json');
    fs.writeFileSync(filePath, JSON.stringify(cooldown, null, 2), 'utf-8');
  }

  /**
   * 注册冷静期
   */
  private registerForCooldown(candidateId: string, project: string): void {
    const cooldown = this.loadCooldown();

    const entry: CooldownEntry = {
      candidate_hash: this.hashCandidate(candidateId),
      project,
      rejected_at: new Date().toISOString(),
      cooldown_expires: this.calculateExpiresDate(),
      reason: '审批拒绝或同类升级',
    };

    cooldown.entries.push(entry);
    this.saveCooldown(cooldown);
  }

  /**
   * 检查是否在冷静期
   */
  private isInCooldown(candidateId: string): boolean {
    const cooldown = this.loadCooldown();
    const hash = this.hashCandidate(candidateId);
    const now = new Date();

    return cooldown.entries.some((entry) => {
      if (entry.candidate_hash !== hash) return false;
      const expires = new Date(entry.cooldown_expires);
      return expires > now;
    });
  }

  /**
   * 生成候选哈希
   */
  private hashCandidate(candidateId: string): string {
    let hash = 0;
    for (let i = 0; i < candidateId.length; i++) {
      const char = candidateId.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash;
    }
    return Math.abs(hash).toString(36);
  }

  /**
   * 计算过期日期
   */
  private calculateExpiresDate(): string {
    const date = new Date();
    date.setDate(date.getDate() + COOLDOWN_DAYS);
    return date.toISOString();
  }

  /**
   * 确保状态目录存在
   */
  private ensureStateDir(): void {
    if (!fs.existsSync(STATE_DIR)) {
      fs.mkdirSync(STATE_DIR, { recursive: true });
    }
  }
}
