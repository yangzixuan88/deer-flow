/**
 * M12 多任务自治运营层 · 持续进化闭环 · 主权治理
 * ================================================
 * Round 12: 从"超人运营智能基线"到"多任务自治+持续进化+主权治理"
 * ================================================
 */

import { ExecutorType } from './types';
import { StepInput } from './world_model_round11';

// ============================================
// ★ Round 12: 多任务自治运营层
// ============================================

/**
 * ★ Round 12: 任务优先级
 */
export type TaskPriority = 'urgent' | 'important' | 'background' | 'blocked' | 'waiting_user';

/**
 * ★ Round 12: 任务审批状态
 */
export type ApprovalState = 'auto_allowed' | 'approval_required' | 'waiting_approval' | 'rejected' | 'frozen';

/**
 * ★ Round 12: 任务状态
 */
export type TaskStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'terminated' | 'frozen';

/**
 * ★ Round 12: 调度决策
 */
export type SchedulerDecision = 'run_now' | 'queue' | 'pause' | 'resume' | 'terminate_low_value' | 'wait_resource';

/**
 * ★ Round 12: 任务链
 */
export interface TaskChain {
  task_id: string;
  task_type: string;
  status: TaskStatus;
  priority: TaskPriority;
  resource_needs: {
    executor?: ExecutorType;
    app_name?: string;
    browser_url?: string;
    requires_focus: boolean;
  };
  current_goal: string;
  blocking_reason?: string;
  approval_state: ApprovalState;
  progress: number;        // 0-100
  health: 'healthy' | 'degraded' | 'critical' | 'unknown';
  failure_count: number;
  recovery_count: number;
  drift_risk: number;      // 0-1
  created_at: string;
  updated_at: string;
  chain_id: string;
}

/**
 * ★ Round 12: 多任务 Portfolio
 */
export class TaskPortfolio {
  private tasks: Map<string, TaskChain> = new Map();
  private eventLog: Array<{ timestamp: string; event: string; task_id?: string; details: any }> = [];

  /**
   * ★ Round 12: 注册新任务
   */
  register(task: TaskChain): void {
    this.tasks.set(task.task_id, task);
    this.log('task_registered', task.task_id, { priority: task.priority, approval_state: task.approval_state });
  }

  /**
   * ★ Round 12: 获取任务
   */
  get(taskId: string): TaskChain | undefined {
    return this.tasks.get(taskId);
  }

  /**
   * ★ Round 12: 获取所有任务
   */
  getAll(): TaskChain[] {
    return Array.from(this.tasks.values());
  }

  /**
   * ★ Round 12: 获取活跃任务
   */
  getActive(): TaskChain[] {
    return this.getAll().filter(t => t.status === 'running' || t.status === 'pending');
  }

  /**
   * ★ Round 12: 更新任务状态
   */
  update(taskId: string, updates: Partial<TaskChain>): void {
    const task = this.tasks.get(taskId);
    if (task) {
      Object.assign(task, updates, { updated_at: new Date().toISOString() });
      this.log('task_updated', taskId, updates);
    }
  }

  /**
   * ★ Round 12: 冻结任务
   */
  freeze(taskId: string, reason: string): void {
    const task = this.tasks.get(taskId);
    if (task) {
      task.status = 'frozen';
      task.approval_state = 'frozen';
      task.updated_at = new Date().toISOString();
      this.log('task_frozen', taskId, { reason });
    }
  }

  /**
   * ★ Round 12: 解冻任务
   */
  unfreeze(taskId: string): void {
    const task = this.tasks.get(taskId);
    if (task) {
      if (task.approval_state === 'frozen') {
        task.approval_state = 'waiting_approval';
      }
      task.updated_at = new Date().toISOString();
      this.log('task_unfrozen', taskId, {});
    }
  }

  /**
   * ★ Round 12: 终止低价值任务
   */
  terminateLowValue(taskId: string): void {
    const task = this.tasks.get(taskId);
    if (task && (task.priority === 'background' || task.health === 'critical')) {
      task.status = 'terminated';
      task.updated_at = new Date().toISOString();
      this.log('task_terminated_low_value', taskId, { priority: task.priority, health: task.health });
    }
  }

  /**
   * ★ Round 12: 获取按优先级排序的任务
   */
  getByPriority(): TaskChain[] {
    const priorityOrder: Record<TaskPriority, number> = {
      urgent: 0, important: 1, background: 2, blocked: 3, waiting_user: 4,
    };
    return this.getActive().sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);
  }

  /**
   * ★ Round 12: 获取需要审批的任务
   */
  getPendingApprovals(): TaskChain[] {
    return this.getAll().filter(t => t.approval_state === 'waiting_approval' || t.approval_state === 'approval_required');
  }

  /**
   * ★ Round 12: 事件日志
   */
  log(event: string, taskId: string | undefined, details: any): void {
    this.eventLog.push({ timestamp: new Date().toISOString(), event, task_id: taskId, details });
  }

  /**
   * ★ Round 12: 获取事件日志
   */
  getEventLog(): Array<{ timestamp: string; event: string; task_id?: string; details: any }> {
    return this.eventLog;
  }

  /**
   * ★ Round 12: 检查任务间冲突
   */
  checkInterTaskConflicts(tasks: TaskChain[]): Array<{
    type: 'focus_steal' | 'browser_exclusive' | 'executor_mutex' | 'resource_contention';
    involved_tasks: string[];
    description: string;
    severity: 'high' | 'medium' | 'low';
  }> {
    const conflicts: Array<{
      type: 'focus_steal' | 'browser_exclusive' | 'executor_mutex' | 'resource_contention';
      involved_tasks: string[];
      description: string;
      severity: 'high' | 'medium' | 'low';
    }> = [];

    for (let i = 0; i < tasks.length; i++) {
      for (let j = i + 1; j < tasks.length; j++) {
        const a = tasks[i];
        const b = tasks[j];

        // Focus steal - both require focus
        if (a.resource_needs.requires_focus && b.resource_needs.requires_focus) {
          if (a.resource_needs.app_name === b.resource_needs.app_name) {
            conflicts.push({
              type: 'focus_steal',
              involved_tasks: [a.task_id, b.task_id],
              description: `Both tasks need focus on ${a.resource_needs.app_name}`,
              severity: 'high',
            });
          }
        }

        // Browser exclusive conflict
        if (a.resource_needs.browser_url && b.resource_needs.browser_url) {
          if (a.resource_needs.browser_url === b.resource_needs.browser_url &&
              a.status === 'running' && b.status === 'running') {
            conflicts.push({
              type: 'browser_exclusive',
              involved_tasks: [a.task_id, b.task_id],
              description: `Both tasks target same browser URL: ${a.resource_needs.browser_url}`,
              severity: 'high',
            });
          }
        }

        // Executor mutex
        if (a.resource_needs.executor && b.resource_needs.executor) {
          if (a.resource_needs.executor === b.resource_needs.executor &&
              a.status === 'running' && b.status === 'running') {
            conflicts.push({
              type: 'executor_mutex',
              involved_tasks: [a.task_id, b.task_id],
              description: `Both tasks need same executor: ${a.resource_needs.executor}`,
              severity: 'medium',
            });
          }
        }
      }
    }

    return conflicts;
  }
}

// ============================================
// ★ Round 12: 多任务调度器
// ============================================
export class MultiTaskScheduler {
  private portfolio: TaskPortfolio;
  private scheduleLog: Array<{ timestamp: string; decision: SchedulerDecision; task_id: string; reason: string }> = [];

  constructor(portfolio: TaskPortfolio) {
    this.portfolio = portfolio;
  }

  /**
   * ★ Round 12: 做出调度决策
   */
  decide(taskId: string): { decision: SchedulerDecision; reason: string } {
    const task = this.portfolio.get(taskId);
    if (!task) {
      return { decision: 'queue', reason: 'task not found' };
    }

    // Check if frozen
    if (task.status === 'frozen' || task.approval_state === 'frozen') {
      this.log('wait_resource', taskId, 'task is frozen');
      return { decision: 'wait_resource', reason: 'task is frozen awaiting approval or user veto' };
    }

    // Check approval state
    if (task.approval_state === 'waiting_approval' || task.approval_state === 'approval_required') {
      this.log('wait_resource', taskId, 'task awaiting approval');
      return { decision: 'wait_resource', reason: 'task awaiting approval gate' };
    }

    if (task.approval_state === 'rejected') {
      this.portfolio.freeze(taskId, 'rejected by approval gate');
      this.log('terminate_low_value', taskId, 'task rejected and frozen');
      return { decision: 'terminate_low_value', reason: 'task rejected, freezing' };
    }

    // Check blocking
    if (task.blocking_reason) {
      this.log('wait_resource', taskId, `blocked: ${task.blocking_reason}`);
      return { decision: 'wait_resource', reason: `blocked by: ${task.blocking_reason}` };
    }

    // Check health
    if (task.health === 'critical' && task.failure_count > 3) {
      this.log('terminate_low_value', taskId, 'critical health and repeated failures');
      return { decision: 'terminate_low_value', reason: 'critical health, terminating' };
    }

    // Priority-based decision
    switch (task.priority) {
      case 'urgent':
        this.log('run_now', taskId, 'urgent priority');
        return { decision: 'run_now', reason: 'urgent priority' };

      case 'important':
        // Check if conflicts with running tasks
        const conflicts = this.portfolio.checkInterTaskConflicts(
          this.portfolio.getActive().filter(t => t.task_id !== taskId && t.status === 'running')
        );
        if (conflicts.some(c => c.involved_tasks.includes(taskId) && c.severity === 'high')) {
          this.log('queue', taskId, 'conflicts with running urgent task');
          return { decision: 'queue', reason: 'conflicts with higher priority running task' };
        }
        this.log('run_now', taskId, 'important and no high-severity conflicts');
        return { decision: 'run_now', reason: 'important priority, resources available' };

      case 'background':
        const activeTasks = this.portfolio.getActive().filter(t => t.priority !== 'background');
        if (activeTasks.length >= 2) {
          this.log('queue', taskId, 'too many non-background tasks running');
          return { decision: 'queue', reason: 'resource contention with non-background tasks' };
        }
        this.log('run_now', taskId, 'background, resources available');
        return { decision: 'run_now', reason: 'background task, resources available' };

      case 'waiting_user':
        this.log('wait_resource', taskId, 'waiting for user input');
        return { decision: 'wait_resource', reason: 'waiting for user' };

      default:
        this.log('queue', taskId, 'default queue');
        return { decision: 'queue', reason: 'default queue' };
    }
  }

  /**
   * ★ Round 12: 批量调度决策
   */
  decideAll(): Array<{ task_id: string; decision: SchedulerDecision; reason: string }> {
    const results: Array<{ task_id: string; decision: SchedulerDecision; reason: string }> = [];
    const sorted = this.portfolio.getByPriority();

    for (const task of sorted) {
      const result = this.decide(task.task_id);
      results.push({ task_id: task.task_id, ...result });
    }

    return results;
  }

  private log(decision: SchedulerDecision, taskId: string, reason: string): void {
    this.scheduleLog.push({ timestamp: new Date().toISOString(), decision, task_id: taskId, reason });
  }

  getScheduleLog(): Array<{ timestamp: string; decision: SchedulerDecision; task_id: string; reason: string }> {
    return this.scheduleLog;
  }
}

// ============================================
// ★ Round 12: 主权治理层
// ============================================

/**
 * ★ Round 12: 高风险动作分类
 */
export const HIGH_RISK_PATTERNS: Array<{ pattern: RegExp; risk_type: string; severity: 'high' | 'medium' | 'low' }> = [
  { pattern: /install|npm install|pip install|apt-get|yum|brew/i, risk_type: 'dependency_install', severity: 'high' },
  { pattern: /delete|rm -rf|remove.*file/i, risk_type: 'file_deletion', severity: 'high' },
  { pattern: /overwrite|replace.*config|\.env|settings\.json/i, risk_type: 'config_overwrite', severity: 'high' },
  { pattern: /batch.*script|bulk.*modify|multiple.*file.*change/i, risk_type: 'bulk_modification', severity: 'high' },
  { pattern: /send.*data|upload.*file|external.*api|webhook/i, risk_type: 'sensitive_data', severity: 'high' },
  { pattern: /sudo|chmod|chown|admin|root/i, risk_type: 'privilege_escalation', severity: 'high' },
  { pattern: /database.*delete|drop.*table|truncate/i, risk_type: 'data_destruction', severity: 'high' },
  { pattern: /format|kill.*process|terminate.*task/i, risk_type: 'system_modification', severity: 'medium' },
  { pattern: /git.*push|git.*force|deploy|release/i, risk_type: 'deployment_risk', severity: 'medium' },
];

/**
 * ★ Round 12: 主权治理决策
 */
export interface SovereigntyDecision {
  allowed: boolean;
  requires_approval: boolean;
  can_suggest: boolean;
  blocked_reason?: string;
  risk_type?: string;
  risk_severity?: 'high' | 'medium' | 'low';
  governance_tag?: string;
}

/**
 * ★ Round 12: 用户主权硬规则
 */
export class SovereigntyGovernance {
  private vetoedInstructions: Set<string> = new Set();
  private vetoedPaths: Set<string> = new Set();
  private frozenTaskInstructions: Map<string, Set<string>> = new Map(); // taskId -> blocked instructions
  private governanceLog: Array<{ timestamp: string; decision: string; task_id?: string; instruction?: string; details: any }> = [];
  private isSystemHalted: boolean = false;
  private haltReason?: string;

  /**
   * ★ Round 12: 用户否决（硬停）
   */
  veto(instruction: string, taskId?: string, reason?: string): void {
    const key = instruction.toLowerCase().trim();
    this.vetoedInstructions.add(key);
    if (taskId) {
      if (!this.frozenTaskInstructions.has(taskId)) {
        this.frozenTaskInstructions.set(taskId, new Set());
      }
      this.frozenTaskInstructions.get(taskId)!.add(key);
    }
    this.log('user_veto', taskId, instruction, { reason, source: 'user_directive' });
  }

  /**
   * ★ Round 12: 用户否决路径
   */
  vetoPath(path: string, reason?: string): void {
    this.vetoedPaths.add(path.toLowerCase().trim());
    this.log('path_veto', undefined, path, { reason, source: 'user_path_ban' });
  }

  /**
   * ★ Round 12: 检查指令是否被否决
   */
  isVetoed(instruction: string, taskId?: string): boolean {
    const key = instruction.toLowerCase().trim();
    if (this.vetoedInstructions.has(key)) return true;
    if (taskId && this.frozenTaskInstructions.has(taskId)) {
      if (this.frozenTaskInstructions.get(taskId)!.has(key)) return true;
    }
    return false;
  }

  /**
   * ★ Round 12: 检查路径是否被否决
   */
  isPathVetoed(path: string): boolean {
    return this.vetoedPaths.has(path.toLowerCase().trim());
  }

  /**
   * ★ Round 12: 系统级停机
   */
  halt(reason: string): void {
    this.isSystemHalted = true;
    this.haltReason = reason;
    this.log('system_halt', undefined, undefined, { reason, source: 'user_system_halt' });
  }

  /**
   * ★ Round 12: 恢复系统
   */
  resume(): void {
    this.isSystemHalted = false;
    this.haltReason = undefined;
    this.log('system_resume', undefined, undefined, { source: 'user_system_resume' });
  }

  /**
   * ★ Round 12: 清除任务级否决（用于审批通过或解冻后恢复指令）
   */
  clearTaskVetoes(taskId: string): void {
    const cleared = this.frozenTaskInstructions.get(taskId);
    if (cleared) {
      for (const instr of cleared) {
        this.vetoedInstructions.delete(instr);
      }
      this.frozenTaskInstructions.delete(taskId);
    }
  }

  /**
   * ★ Round 12: 是否系统停机
   */
  isHalted(): boolean {
    return this.isSystemHalted;
  }

  /**
   * ★ Round 12: 治理检查
   */
  check(instruction: string, taskId?: string, taskApprovalState?: ApprovalState): SovereigntyDecision {
    // System halted - everything blocked
    if (this.isSystemHalted) {
      return {
        allowed: false,
        requires_approval: false,
        can_suggest: false,
        blocked_reason: `System halted: ${this.haltReason}`,
        governance_tag: 'system_halt',
      };
    }

    // Check veto
    if (this.isVetoed(instruction, taskId)) {
      return {
        allowed: false,
        requires_approval: false,
        can_suggest: false,
        blocked_reason: 'Instruction vetoed by user',
        governance_tag: 'user_veto',
      };
    }

    // Check path veto
    const pathMatch = Array.from(this.vetoedPaths).find(p => instruction.toLowerCase().includes(p));
    if (pathMatch) {
      return {
        allowed: false,
        requires_approval: false,
        can_suggest: false,
        blocked_reason: `Path vetoed: ${pathMatch}`,
        governance_tag: 'path_veto',
      };
    }

    // Check approval state
    if (taskApprovalState === 'frozen' || taskApprovalState === 'rejected') {
      return {
        allowed: false,
        requires_approval: true,
        can_suggest: false,
        blocked_reason: `Task ${taskApprovalState}`,
        governance_tag: 'task_state_blocked',
      };
    }

    // Check high-risk patterns - but auto_allowed tasks have blanket approval for all their instructions
    if (taskApprovalState !== 'auto_allowed') {
      for (const hp of HIGH_RISK_PATTERNS) {
        if (hp.pattern.test(instruction)) {
          this.log('approval_gate_hit', taskId, instruction, {
            risk_type: hp.risk_type,
            severity: hp.severity,
            governance_tag: 'approval_required',
          });
          return {
            allowed: false,
            requires_approval: true,
            can_suggest: true,
            risk_type: hp.risk_type,
            risk_severity: hp.severity,
            blocked_reason: `High-risk action: ${hp.risk_type} requires approval`,
            governance_tag: 'approval_required',
          };
        }
      }
    }

    // Default: allowed to execute autonomously
    return {
      allowed: true,
      requires_approval: false,
      can_suggest: true,
    };
  }

  /**
   * ★ Round 12: 审批任务
   */
  approve(taskId: string): void {
    this.log('task_approved', taskId, undefined, { source: 'approval_gate_passed' });
    // Clear task-specific vetoes so previously blocked instructions can proceed
    this.clearTaskVetoes(taskId);
  }

  /**
   * ★ Round 12: 拒绝任务
   */
  reject(taskId: string, reason?: string): void {
    this.log('task_rejected', taskId, undefined, { reason, source: 'approval_gate_denied' });
    this.log('task_frozen', taskId, undefined, { reason, source: 'approval_gate_denied' });
  }

  private log(decision: string, taskId: string | undefined, instruction: string | undefined, details: any): void {
    this.governanceLog.push({
      timestamp: new Date().toISOString(),
      decision,
      task_id: taskId,
      instruction,
      details,
    });
  }

  logTaskFrozen(taskId: string, instruction: string, details: any): void {
    this.governanceLog.push({
      timestamp: new Date().toISOString(),
      decision: 'task_frozen',
      task_id: taskId,
      instruction,
      details,
    });
  }

  getGovernanceLog(): Array<{ timestamp: string; decision: string; task_id?: string; instruction?: string; details: any }> {
    return this.governanceLog;
  }
}

// ============================================
// ★ Round 12: 夜间进化闭环
// ============================================

/**
 * ★ Round 12: 经验条目
 */
export interface ExperienceEntry {
  id: string;
  type: 'strategy_update' | 'asset_promotion' | 'recovery_pattern' | 'environment_heuristic' | 'anti_pattern';
  content: string;
  confidence: number;        // 0-1
  source_count: number;       // 多少任务贡献了这条经验
  recency: number;           // 最新任务时间戳
  reuse_score: number;        // 被复用次数
  task_signature?: string;    // 相关任务签名
  created_at: string;
  applied_at?: string;
  effectiveness?: number;    // 应用后的效果评分
}

/**
 * ★ Round 12: 夜间蒸馏报告
 */
export interface DailyEvolutionReport {
  date: string;
  total_tasks: number;
  successful_tasks: number;
  failed_tasks: number;
  strategy_updates: ExperienceEntry[];
  asset_promotions: ExperienceEntry[];
  recovery_patterns: ExperienceEntry[];
  anti_patterns: ExperienceEntry[];
  environment_heuristics: ExperienceEntry[];
  recommendations: Array<{ type: string; content: string; priority: 'high' | 'medium' | 'low' }>;
}

/**
 * ★ Round 12: 持续进化引擎
 */
export class DailyEvolutionEngine {
  private experienceBase: ExperienceEntry[] = [];
  private evolutionLog: Array<{ timestamp: string; action: string; entry_id?: string; details: any }> = [];
  private lastReport?: DailyEvolutionReport;

  /**
   * ★ Round 12: 从任务历史提取经验
   */
  extractFromTasks(tasks: TaskChain[], taskOutcomes: Array<{
    task_id: string;
    success: boolean;
    failed_step?: string;
    recovery_used?: boolean;
    fallback_triggered?: boolean;
    execution_time_ms?: number;
  }>): DailyEvolutionReport {
    const date = new Date().toISOString().split('T')[0];
    const strategyUpdates: ExperienceEntry[] = [];
    const assetPromotions: ExperienceEntry[] = [];
    const recoveryPatterns: ExperienceEntry[] = [];
    const antiPatterns: ExperienceEntry[] = [];
    const envHeuristics: ExperienceEntry[] = [];

    // Group outcomes by task type
    const outcomesByTask = new Map<string, typeof taskOutcomes>();
    for (const outcome of taskOutcomes) {
      const task = tasks.find(t => t.task_id === outcome.task_id);
      if (task) {
        const key = task.task_type;
        if (!outcomesByTask.has(key)) outcomesByTask.set(key, []);
        outcomesByTask.get(key)!.push(outcome);
      }
    }

    // Extract anti-patterns from failures
    for (const [taskType, outcomes] of outcomesByTask) {
      const failures = outcomes.filter(o => !o.success && o.failed_step);
      if (failures.length >= 2) {
        const failureSteps = [...new Set(failures.map(f => f.failed_step))];
        for (const step of failureSteps) {
          antiPatterns.push(this.createExperience(
            'anti_pattern',
            `Avoid: ${step} in ${taskType} context`,
            0.5 + (failures.length * 0.1),
            failures.length,
            taskType
          ));
        }
      }

      // Recovery patterns
      const recoveries = outcomes.filter(o => o.recovery_used);
      if (recoveries.length > 0) {
        recoveryPatterns.push(this.createExperience(
          'recovery_pattern',
          `Recovery effective for ${taskType} after ${recoveries.length} uses`,
          0.6 + (recoveries.length * 0.05),
          recoveries.length,
          taskType
        ));
      }

      // Fallback patterns
      const fallbacks = outcomes.filter(o => o.fallback_triggered);
      if (fallbacks.length >= 2) {
        envHeuristics.push(this.createExperience(
          'environment_heuristic',
          `Fallback commonly triggered for ${taskType}: consider alternative strategy`,
          0.5,
          fallbacks.length,
          taskType
        ));
      }
    }

    // Asset promotions - successful chains become high-value
    for (const outcome of taskOutcomes.filter(o => o.success)) {
      const task = tasks.find(t => t.task_id === outcome.task_id);
      if (task && task.progress >= 80) {
        assetPromotions.push(this.createExperience(
          'asset_promotion',
          `High-value chain: ${task.current_goal}`,
          0.7,
          1,
          task.task_type
        ));
      }
    }

    // Strategy updates
    for (const [taskType, outcomes] of outcomesByTask) {
      const successRate = outcomes.filter(o => o.success).length / outcomes.length;
      if (successRate >= 0.7) {
        strategyUpdates.push(this.createExperience(
          'strategy_update',
          `${taskType} has ${Math.round(successRate * 100)}% success rate - maintain current approach`,
          successRate,
          outcomes.length,
          taskType
        ));
      } else if (successRate < 0.4) {
        strategyUpdates.push(this.createExperience(
          'strategy_update',
          `${taskType} has low ${Math.round(successRate * 100)}% success rate - needs strategy revision`,
          1 - successRate,
          outcomes.length,
          taskType
        ));
      }
    }

    const report: DailyEvolutionReport = {
      date,
      total_tasks: tasks.length,
      successful_tasks: taskOutcomes.filter(o => o.success).length,
      failed_tasks: taskOutcomes.filter(o => !o.success).length,
      strategy_updates: strategyUpdates,
      asset_promotions: assetPromotions,
      recovery_patterns: recoveryPatterns,
      anti_patterns: antiPatterns,
      environment_heuristics: envHeuristics,
      recommendations: this.generateRecommendations(strategyUpdates, antiPatterns, assetPromotions),
    };

    this.lastReport = report;
    this.evolutionLog.push({ timestamp: new Date().toISOString(), action: 'report_generated', details: { date, task_count: tasks.length } });

    return report;
  }

  /**
   * ★ Round 12: 应用经验到次日决策
   */
  applyExperience(context: {
    task_type?: string;
    instruction?: string;
    failed_attempts?: number;
    current_strategy?: string;
  }): {
    strategy_shift?: string;
    asset_promoted?: string;
    anti_pattern_blocked: boolean;
    suggested_strategy?: string;
    confidence: number;
  } {
    // Check anti-patterns - flexible matching: match on key action words
    if (context.instruction) {
      const instruction = context.instruction.toLowerCase();
      const blockedAntiPatterns = this.experienceBase.filter(e => {
        if (e.type !== 'anti_pattern') return false;
        const anti = e.content.toLowerCase().replace('avoid: ', '');
        // Extract key action words (at least 2 significant words)
        const words = anti.split(' ').filter(w => w.length > 3 && !['context', 'directly', 'operations'].includes(w));
        if (words.length === 0) return false;
        // Match if most key words appear in instruction
        const matchCount = words.filter(w => instruction.includes(w)).length;
        return matchCount >= Math.max(1, Math.floor(words.length * 0.6));
      });

      if (blockedAntiPatterns.length > 0) {
        const best = blockedAntiPatterns.sort((a, b) => b.confidence - a.confidence)[0];
        this.evolutionLog.push({
          timestamp: new Date().toISOString(),
          action: 'anti_pattern_blocked',
          entry_id: best.id,
          details: { instruction: context.instruction, match: best.content },
        });
        return {
          anti_pattern_blocked: true,
          confidence: best.confidence,
        };
      }
    }

    // Check strategy updates
    if (context.task_type) {
      const relevantStrategies = this.experienceBase.filter(e =>
        e.type === 'strategy_update' &&
        e.task_signature === context.task_type &&
        e.applied_at === undefined
      );

      if (relevantStrategies.length > 0) {
        const best = relevantStrategies.sort((a, b) => b.confidence - a.confidence)[0];
        best.applied_at = new Date().toISOString();
        best.reuse_score++;
        this.evolutionLog.push({
          timestamp: new Date().toISOString(),
          action: 'strategy_applied',
          entry_id: best.id,
          details: { task_type: context.task_type, content: best.content },
        });
        return {
          strategy_shift: best.content,
          anti_pattern_blocked: false,
          suggested_strategy: best.content,
          confidence: best.confidence,
        };
      }
    }

    // Check asset promotions
    if (context.instruction) {
      const relevantAssets = this.experienceBase.filter(e =>
        e.type === 'asset_promotion' &&
        e.content.toLowerCase().includes(context.instruction!.toLowerCase().substring(0, 30))
      );
      if (relevantAssets.length > 0) {
        const best = relevantAssets[0];
        best.applied_at = new Date().toISOString();
        best.reuse_score++;
        this.evolutionLog.push({
          timestamp: new Date().toISOString(),
          action: 'asset_applied',
          entry_id: best.id,
          details: { asset: best.content },
        });
        return {
          asset_promoted: best.content,
          anti_pattern_blocked: false,
          confidence: best.confidence,
        };
      }
    }

    return { anti_pattern_blocked: false, confidence: 0 };
  }

  /**
   * ★ Round 12: 存储经验
   */
  storeExperiences(entries: ExperienceEntry[]): void {
    for (const entry of entries) {
      // Check if similar experience exists
      const existing = this.experienceBase.find(e =>
        e.type === entry.type &&
        e.content === entry.content
      );
      if (existing) {
        existing.source_count += entry.source_count;
        existing.confidence = Math.min(1, existing.confidence + entry.confidence * 0.1);
        existing.recency = Math.max(existing.recency, entry.recency);
      } else {
        this.experienceBase.push({ ...entry, id: `exp_${Date.now()}_${Math.random().toString(36).slice(2, 6)}` });
      }
    }
    this.evolutionLog.push({ timestamp: new Date().toISOString(), action: 'experiences_stored', details: { count: entries.length } });
  }

  /**
   * ★ Round 12: 获取经验库
   */
  getExperienceBase(): ExperienceEntry[] {
    return this.experienceBase;
  }

  /**
   * ★ Round 12: 获取最近报告
   */
  getLastReport(): DailyEvolutionReport | undefined {
    return this.lastReport;
  }

  /**
   * ★ Round 12: 获取进化日志
   */
  getEvolutionLog(): Array<{ timestamp: string; action: string; entry_id?: string; details: any }> {
    return this.evolutionLog;
  }

  private createExperience(
    type: ExperienceEntry['type'],
    content: string,
    confidence: number,
    sourceCount: number,
    taskSignature?: string
  ): ExperienceEntry {
    return {
      id: `exp_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      type,
      content,
      confidence: Math.min(1, confidence),
      source_count: sourceCount,
      recency: Date.now(),
      reuse_score: 0,
      task_signature: taskSignature,
      created_at: new Date().toISOString(),
    };
  }

  private generateRecommendations(
    strategies: ExperienceEntry[],
    antiPatterns: ExperienceEntry[],
    assets: ExperienceEntry[]
  ): DailyEvolutionReport['recommendations'] {
    const recs: DailyEvolutionReport['recommendations'] = [];

    if (antiPatterns.length > 0) {
      recs.push({
        type: 'anti_pattern_avoidance',
        content: `${antiPatterns.length} anti-patterns identified - implement avoidance`,
        priority: 'high',
      });
    }

    if (strategies.filter(s => s.confidence > 0.7).length > 0) {
      recs.push({
        type: 'strategy_maintenance',
        content: 'High-confidence strategies confirmed - maintain current approach',
        priority: 'medium',
      });
    }

    if (assets.length > 0) {
      recs.push({
        type: 'asset_promotion',
        content: `${assets.length} assets promoted - consider registry enrichment`,
        priority: 'medium',
      });
    }

    return recs;
  }
}

// ============================================
// ★ Round 12: 多任务自治运营引擎
// ============================================
export class AutonomousOperationEngine {
  portfolio: TaskPortfolio;
  scheduler: MultiTaskScheduler;
  governance: SovereigntyGovernance;
  evolution: DailyEvolutionEngine;

  constructor() {
    this.portfolio = new TaskPortfolio();
    this.scheduler = new MultiTaskScheduler(this.portfolio);
    this.governance = new SovereigntyGovernance();
    this.evolution = new DailyEvolutionEngine();
  }

  /**
   * ★ Round 12: 提交任务
   */
  submitTask(task: TaskChain): { accepted: boolean; governance_decision: SovereigntyDecision } {
    const govDecision = this.governance.check(
      task.current_goal,
      task.task_id,
      task.approval_state
    );

    if (govDecision.allowed || govDecision.can_suggest) {
      this.portfolio.register(task);
    }

    return { accepted: govDecision.allowed, governance_decision: govDecision };
  }

  /**
   * ★ Round 12: 执行调度
   */
  schedule(): Array<{ task_id: string; decision: SchedulerDecision; reason: string }> {
    return this.scheduler.decideAll();
  }

  /**
   * ★ Round 12: 用户否决
   */
  userVeto(instruction: string, taskId?: string, reason?: string): void {
    this.governance.veto(instruction, taskId, reason);
    if (taskId) {
      this.portfolio.freeze(taskId, `user vetoed: ${reason || instruction}`);
      this.governance.logTaskFrozen(taskId, instruction, { reason: `user vetoed: ${reason || instruction}`, source: 'user_veto' });
    }
  }

  /**
   * ★ Round 12: 夜间蒸馏
   */
  nightlyDistill(
    tasks: TaskChain[],
    outcomes: Array<{
      task_id: string;
      success: boolean;
      failed_step?: string;
      recovery_used?: boolean;
      fallback_triggered?: boolean;
    }>
  ): DailyEvolutionReport {
    const report = this.evolution.extractFromTasks(tasks, outcomes);

    // Store all experience entries
    const allEntries: ExperienceEntry[] = [
      ...report.strategy_updates,
      ...report.asset_promotions,
      ...report.recovery_patterns,
      ...report.anti_patterns,
      ...report.environment_heuristics,
    ];
    this.evolution.storeExperiences(allEntries);

    return report;
  }

  /**
   * ★ Round 12: 次日决策影响
   */
  applyYesterdayToToday(context: {
    task_type?: string;
    instruction?: string;
    failed_attempts?: number;
  }): ReturnType<DailyEvolutionEngine['applyExperience']> {
    return this.evolution.applyExperience(context);
  }

  /**
   * ★ Round 12: 获取综合 trace
   */
  getTrace(): {
    task_portfolio_state: TaskChain[];
    scheduler_decision_trace: Array<{ timestamp: string; decision: SchedulerDecision; task_id: string; reason: string }>;
    resource_conflict_trace: ReturnType<TaskPortfolio['checkInterTaskConflicts']>;
    task_lifecycle_events: Array<{ timestamp: string; event: string; task_id?: string; details: any }>;
    governance_decisions: Array<{ timestamp: string; decision: string; task_id?: string; instruction?: string; details: any }>;
    evolution_applied: Array<{ timestamp: string; action: string; entry_id?: string; details: any }>;
  } {
    return {
      task_portfolio_state: this.portfolio.getAll(),
      scheduler_decision_trace: this.scheduler.getScheduleLog(),
      resource_conflict_trace: this.portfolio.checkInterTaskConflicts(this.portfolio.getActive()),
      task_lifecycle_events: this.portfolio.getEventLog(),
      governance_decisions: this.governance.getGovernanceLog(),
      evolution_applied: this.evolution.getEvolutionLog(),
    };
  }

  /**
   * ★ Round 12: 获取指标
   */
  getMetrics(): {
    active_tasks: number;
    pending_approvals: number;
    frozen_tasks: number;
    vetoed_instructions: number;
    experience_base_size: number;
    last_evolution_date?: string;
    system_halted: boolean;
  } {
    return {
      active_tasks: this.portfolio.getActive().length,
      pending_approvals: this.portfolio.getPendingApprovals().length,
      frozen_tasks: this.portfolio.getAll().filter(t => t.status === 'frozen' || t.approval_state === 'frozen').length,
      vetoed_instructions: this.governance.isHalted() ? -1 : this.governance.getGovernanceLog().filter(l => l.decision === 'user_veto').length,
      experience_base_size: this.evolution.getExperienceBase().length,
      last_evolution_date: this.evolution.getLastReport()?.date,
      system_halted: this.governance.isHalted(),
    };
  }
}

// ============================================
// 单例
// ============================================
export const autonomousEngine = new AutonomousOperationEngine();
