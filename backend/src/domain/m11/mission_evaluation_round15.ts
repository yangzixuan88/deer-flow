/**
 * M15 使命系统 + 量化评估 + 组织协作
 * ================================================
 * Round 15: 使命层 + 评估裁判层 + 组织分治层
 * ================================================
 */

import { ExecutorType } from './types';
import {
  TaskPortfolio, TaskChain, TaskStatus, ApprovalState, TaskPriority,
  MultiTaskScheduler, SchedulerDecision,
  SovereigntyGovernance, HIGH_RISK_PATTERNS,
  DailyEvolutionEngine, ExperienceEntry, DailyEvolutionReport,
} from './autonomous_governance_round12';
import {
  ExecutionEvent, ExecutionEventEmitter, ResourceSnapshot,
  AutonomousRuntimeLoop, ExperiencePersister, AutonomousExecutionEngine,
} from './autonomous_runtime_round13';
import {
  ControlledEvolutionEngine, ResourceLockManager, DurableAutonomousEngine,
  StrategyPatch, EvolutionAuditEntry,
} from './autonomous_durable_round14';
import * as fs from 'fs';
import * as path from 'path';

// ============================================
// PART 1: MISSION OPERATING LAYER
// ============================================

/**
 * ★ Round 15: 使命状态
 */
export type MissionStatus = 'active' | 'completed' | 'failed' | 'blocked' | 'paused' | 'cancelled';

/**
 * ★ Round 15: 里程碑
 */
export interface Milestone {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  completion_criteria: string;
  completed_at?: string;
}

/**
 * ★ Round 15: 子目标
 */
export interface Subgoal {
  id: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  task_ids: string[];
  completion_score: number; // 0-1
  blocked_reason?: string;
}

/**
 * ★ Round 15: 使命
 */
export interface Mission {
  id: string;
  mission_goal: string;
  status: MissionStatus;
  priority: TaskPriority;
  subgoals: Subgoal[];
  milestones: Milestone[];
  task_ids: string[];
  created_at: string;
  updated_at: string;
  completion_score: number; // 0-1
  goal_gap: number; // 0-1, remaining work
  blocked_reasons: string[];
  governance_state: 'auto_allowed' | 'approval_required' | 'frozen' | 'halted';
}

/**
 * ★ Round 15: 使命追踪条目
 */
export interface MissionTraceEntry {
  timestamp: string;
  action: 'mission_created' | 'task_added' | 'task_completed' | 'task_failed' | 'subgoal_progress' | 'milestone_completed' | 'mission_replan' | 'mission_blocked' | 'mission_completed';
  mission_id: string;
  task_id?: string;
  subgoal_id?: string;
  milestone_id?: string;
  details: any;
}

/**
 * ★ Round 15: 使命注册与管理
 */
export class MissionRegistry {
  private missions: Map<string, Mission> = new Map();
  private trace: MissionTraceEntry[] = [];

  /**
   * ★ Round 15: 创建使命
   */
  createMission(
    missionGoal: string,
    priority: TaskPriority = 'important',
    successCriteria?: string
  ): Mission {
    const id = `mission_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const now = new Date().toISOString();

    const mission: Mission = {
      id,
      mission_goal: missionGoal,
      status: 'active',
      priority,
      subgoals: [],
      milestones: successCriteria ? [{
        id: `ms_${Date.now()}`,
        name: 'Primary Goal',
        description: successCriteria,
        status: 'pending',
        completion_criteria: successCriteria,
      }] : [],
      task_ids: [],
      created_at: now,
      updated_at: now,
      completion_score: 0,
      goal_gap: 1,
      blocked_reasons: [],
      governance_state: 'auto_allowed',
    };

    this.missions.set(id, mission);
    this.log('mission_created', id, {}, missionGoal);
    return mission;
  }

  /**
   * ★ Round 15: 添加子目标
   */
  addSubgoal(missionId: string, description: string, taskIds: string[] = []): Subgoal | null {
    const mission = this.missions.get(missionId);
    if (!mission) return null;

    const subgoal: Subgoal = {
      id: `sg_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      description,
      status: 'pending',
      task_ids: taskIds,
      completion_score: 0,
    };

    mission.subgoals.push(subgoal);
    mission.updated_at = new Date().toISOString();
    this.log('subgoal_progress', missionId, { subgoal_id: subgoal.id }, description);
    return subgoal;
  }

  /**
   * ★ Round 15: 添加任务到使命
   */
  addTask(missionId: string, taskId: string): boolean {
    const mission = this.missions.get(missionId);
    if (!mission) return false;

    mission.task_ids.push(taskId);
    mission.updated_at = new Date().toISOString();
    this.log('task_added', missionId, { task_id: taskId });
    return true;
  }

  /**
   * ★ Round 15: 回写任务完成
   */
  reportTaskCompletion(missionId: string, taskId: string, success: boolean): void {
    const mission = this.missions.get(missionId);
    if (!mission) return;

    this.log(success ? 'task_completed' : 'task_failed', missionId, { task_id: taskId }, success ? 'success' : 'failed');

    // Update subgoal completion
    for (const subgoal of mission.subgoals) {
      if (subgoal.task_ids.includes(taskId)) {
        if (success) {
          const completedTasks = subgoal.task_ids.filter(tid =>
            // In real impl, would check task status in portfolio
            tid === taskId
          ).length;
          subgoal.completion_score = Math.min(1, subgoal.completion_score + (1 / subgoal.task_ids.length));
          if (subgoal.completion_score >= 1) {
            subgoal.status = 'completed';
          }
        } else {
          subgoal.status = 'blocked';
          subgoal.blocked_reason = `Task ${taskId} failed`;
        }
      }
    }

    // Recalculate mission completion
    this.recalculateProgress(missionId);
  }

  /**
   * ★ Round 15: 重新计算进度
   */
  private recalculateProgress(missionId: string): void {
    const mission = this.missions.get(missionId);
    if (!mission) return;

    if (mission.subgoals.length > 0) {
      mission.completion_score = mission.subgoals.reduce((sum, sg) => sum + sg.completion_score, 0) / mission.subgoals.length;
    }

    // Check milestones
    let completedMilestones = 0;
    for (const milestone of mission.milestones) {
      if (milestone.status === 'completed') completedMilestones++;
    }
    if (mission.milestones.length > 0) {
      mission.completion_score = (mission.completion_score + (completedMilestones / mission.milestones.length)) / 2;
    }

    mission.goal_gap = 1 - mission.completion_score;
    mission.updated_at = new Date().toISOString();

    // Update mission status
    if (mission.completion_score >= 1) {
      mission.status = 'completed';
    } else if (mission.blocked_reasons.length > 0) {
      mission.status = 'blocked';
    }
  }

  /**
   * ★ Round 15: 使命级重规划
   */
  replanMission(missionId: string, newSubgoals: Array<{ description: string; task_ids: string[] }>): boolean {
    const mission = this.missions.get(missionId);
    if (!mission) return false;

    // Archive old subgoals
    const oldSubgoals = [...mission.subgoals];

    // Add new subgoals
    mission.subgoals = [];
    for (const sg of newSubgoals) {
      this.addSubgoal(missionId, sg.description, sg.task_ids);
    }

    this.log('mission_replan', missionId, { old_subgoal_count: oldSubgoals.length, new_subgoal_count: newSubgoals.length });
    return true;
  }

  /**
   * ★ Round 15: 使命级冻结
   */
  freezeMission(missionId: string, reason: string): boolean {
    const mission = this.missions.get(missionId);
    if (!mission) return false;

    mission.status = 'paused';
    mission.governance_state = 'frozen';
    mission.blocked_reasons.push(`frozen: ${reason}`);
    this.log('mission_blocked', missionId, {}, reason);
    return true;
  }

  /**
   * ★ Round 15: 获取使命
   */
  getMission(missionId: string): Mission | undefined {
    return this.missions.get(missionId);
  }

  /**
   * ★ Round 15: 获取所有使命
   */
  getAllMissions(): Mission[] {
    return Array.from(this.missions.values());
  }

  /**
   * ★ Round 15: 获取活跃使命
   */
  getActiveMissions(): Mission[] {
    return this.getAllMissions().filter(m => m.status === 'active');
  }

  /**
   * ★ Round 15: 获取追踪日志
   */
  getTrace(): MissionTraceEntry[] {
    return [...this.trace];
  }

  private log(action: MissionTraceEntry['action'], missionId: string, details: any, extra?: string): void {
    this.trace.push({
      timestamp: new Date().toISOString(),
      action,
      mission_id: missionId,
      details,
    } as MissionTraceEntry);
  }
}

// ============================================
// PART 2: CAPABILITY EVALUATION LAYER
// ============================================

/**
 * ★ Round 15: 基准任务集
 */
export interface BenchmarkTask {
  id: string;
  name: string;
  category: 'web' | 'desktop' | 'mixed' | 'recovery' | 'autonomous_governance' | 'long_running';
  task_type: string;
  expected_success: boolean;
  complexity: number; // 1-10
  run_count: number;
  success_count: number;
}

/**
 * ★ Round 15: 能力指标
 */
export interface CapabilityMetrics {
  success_rate: number;
  recovery_success_rate: number;
  goal_completion_rate: number;
  average_steps: number;
  fallback_rate: number;
  time_to_completion: number;
  resource_conflict_rate: number;
  timestamp: string;
}

/**
 * ★ Round 15: 版本比较结果
 */
export interface VersionComparison {
  version_a: string;
  version_b: string;
  metrics_delta: Partial<CapabilityMetrics>;
  capability_score_delta: number;
  regression_detected: boolean;
  improvement_areas: string[];
  regression_areas: string[];
  recommendation: 'promote_a' | 'promote_b' | 'keep_both' | 'rollback_required';
}

/**
 * ★ Round 15: 评估报告
 */
export interface EvaluationReport {
  evaluation_id: string;
  timestamp: string;
  version: string;
  metrics: CapabilityMetrics;
  capability_score: number; // 0-1
  version_delta?: Partial<CapabilityMetrics>;
  regression_detected: boolean;
  promotion_recommendation: 'promote' | 'block' | 'needs_improvement';
  rollback_recommendation?: { target_version: string; reason: string };
}

/**
 * ★ Round 15: 能力评估引擎
 */
export class CapabilityEvaluationEngine {
  private benchmarkTasks: Map<string, BenchmarkTask> = new Map();
  private evaluationHistory: EvaluationReport[] = [];
  private currentVersion: string = 'v0';

  constructor() {
    this.initializeBenchmarkTasks();
  }

  /**
   * ★ Round 15: 初始化基准任务集
   */
  private initializeBenchmarkTasks(): void {
    const tasks: BenchmarkTask[] = [
      { id: 'bench_web_nav', name: 'Web Navigation', category: 'web', task_type: 'web_browser', expected_success: true, complexity: 3, run_count: 0, success_count: 0 },
      { id: 'bench_web_form', name: 'Web Form Fill', category: 'web', task_type: 'web_browser', expected_success: true, complexity: 5, run_count: 0, success_count: 0 },
      { id: 'bench_desktop_edit', name: 'Desktop Edit', category: 'desktop', task_type: 'desktop_app', expected_success: true, complexity: 4, run_count: 0, success_count: 0 },
      { id: 'bench_mixed_ops', name: 'Mixed Operations', category: 'mixed', task_type: 'cli_tool', expected_success: true, complexity: 6, run_count: 0, success_count: 0 },
      { id: 'bench_recovery', name: 'Recovery Pattern', category: 'recovery', task_type: 'web_browser', expected_success: true, complexity: 7, run_count: 0, success_count: 0 },
      { id: 'bench_gov_approval', name: 'Governance Approval', category: 'autonomous_governance', task_type: 'system', expected_success: true, complexity: 4, run_count: 0, success_count: 0 },
      { id: 'bench_durable', name: 'Long Running Task', category: 'long_running', task_type: 'multi_task', expected_success: true, complexity: 8, run_count: 0, success_count: 0 },
    ];

    for (const task of tasks) {
      this.benchmarkTasks.set(task.id, task);
    }
  }

  /**
   * ★ Round 15: 记录任务执行结果
   */
  recordTaskResult(taskId: string, success: boolean, steps: number = 1): void {
    const task = this.benchmarkTasks.get(taskId);
    if (task) {
      task.run_count++;
      if (success) task.success_count++;
    }
  }

  /**
   * ★ Round 15: 计算能力指标
   */
  computeMetrics(
    taskResults: Array<{ task_id: string; success: boolean; steps: number; fallback_triggered: boolean; time_ms: number }>,
    resourceConflicts: number = 0
  ): CapabilityMetrics {
    if (taskResults.length === 0) {
      return {
        success_rate: 0,
        recovery_success_rate: 0,
        goal_completion_rate: 0,
        average_steps: 0,
        fallback_rate: 0,
        time_to_completion: 0,
        resource_conflict_rate: 0,
        timestamp: new Date().toISOString(),
      };
    }

    const successCount = taskResults.filter(r => r.success).length;
    const fallbackCount = taskResults.filter(r => r.fallback_triggered).length;
    const totalTime = taskResults.reduce((sum, r) => sum + r.time_ms, 0);
    const totalSteps = taskResults.reduce((sum, r) => sum + r.steps, 0);

    return {
      success_rate: successCount / taskResults.length,
      recovery_success_rate: successCount / Math.max(1, taskResults.filter(r => r.fallback_triggered).length || 1),
      goal_completion_rate: successCount / taskResults.length,
      average_steps: totalSteps / taskResults.length,
      fallback_rate: fallbackCount / taskResults.length,
      time_to_completion: totalTime / taskResults.length,
      resource_conflict_rate: resourceConflicts / taskResults.length,
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * ★ Round 15: 计算能力分数（综合指标）
   */
  computeCapabilityScore(metrics: CapabilityMetrics): number {
    // Weighted composite score
    const successWeight = 0.35;
    const recoveryWeight = 0.15;
    const stepsWeight = 0.1;
    const fallbackWeight = 0.15;
    const timeWeight = 0.1;
    const conflictWeight = 0.15;

    // Normalize steps (lower is better, so invert)
    const stepsScore = Math.max(0, 1 - (metrics.average_steps / 20));

    // Normalize time (lower is better, so invert)
    const timeScore = Math.max(0, 1 - (metrics.time_to_completion / 60000));

    // Normalize conflict (lower is better)
    const conflictScore = Math.max(0, 1 - metrics.resource_conflict_rate);

    return (
      metrics.success_rate * successWeight +
      Math.min(1, metrics.recovery_success_rate) * recoveryWeight +
      stepsScore * stepsWeight +
      (1 - metrics.fallback_rate) * fallbackWeight +
      timeScore * timeWeight +
      conflictScore * conflictWeight
    );
  }

  /**
   * ★ Round 15: 比较两个版本
   */
  compareVersions(
    versionA: string,
    metricsA: CapabilityMetrics,
    versionB: string,
    metricsB: CapabilityMetrics
  ): VersionComparison {
    const metricsDelta = {
      success_rate: metricsB.success_rate - metricsA.success_rate,
      recovery_success_rate: metricsB.recovery_success_rate - metricsA.recovery_success_rate,
      goal_completion_rate: metricsB.goal_completion_rate - metricsA.goal_completion_rate,
      average_steps: metricsB.average_steps - metricsA.average_steps,
      fallback_rate: metricsB.fallback_rate - metricsA.fallback_rate,
      time_to_completion: metricsB.time_to_completion - metricsA.time_to_completion,
      resource_conflict_rate: metricsB.resource_conflict_rate - metricsA.resource_conflict_rate,
    };

    const scoreA = this.computeCapabilityScore(metricsA);
    const scoreB = this.computeCapabilityScore(metricsB);
    const scoreDelta = scoreB - scoreA;

    const regressionDetected = scoreDelta < -0.05;

    const improvementAreas: string[] = [];
    const regressionAreas: string[] = [];

    if (metricsDelta.success_rate > 0) improvementAreas.push('success_rate');
    else if (metricsDelta.success_rate < 0) regressionAreas.push('success_rate');

    if (metricsDelta.fallback_rate < 0) improvementAreas.push('fallback_reduction');
    else if (metricsDelta.fallback_rate > 0) regressionAreas.push('fallback_increase');

    if (metricsDelta.average_steps < 0) improvementAreas.push('steps_reduction');
    else if (metricsDelta.average_steps > 0) regressionAreas.push('steps_increase');

    let recommendation: VersionComparison['recommendation'];
    if (regressionDetected) {
      recommendation = 'rollback_required';
    } else if (scoreDelta > 0.05) {
      recommendation = 'promote_b';
    } else if (scoreDelta < -0.05) {
      recommendation = 'promote_a';
    } else {
      recommendation = 'keep_both';
    }

    return {
      version_a: versionA,
      version_b: versionB,
      metrics_delta: metricsDelta,
      capability_score_delta: scoreDelta,
      regression_detected: regressionDetected,
      improvement_areas: improvementAreas,
      regression_areas: regressionAreas,
      recommendation,
    };
  }

  /**
   * ★ Round 15: 生成评估报告
   */
  evaluate(
    version: string,
    taskResults: Array<{ task_id: string; success: boolean; steps: number; fallback_triggered: boolean; time_ms: number }>,
    resourceConflicts: number = 0
  ): EvaluationReport {
    const metrics = this.computeMetrics(taskResults, resourceConflicts);
    const capabilityScore = this.computeCapabilityScore(metrics);

    let promotionRecommendation: EvaluationReport['promotion_recommendation'] = 'block';
    if (capabilityScore >= 0.7) {
      promotionRecommendation = 'promote';
    } else if (capabilityScore >= 0.5) {
      promotionRecommendation = 'needs_improvement';
    }

    let rollbackRecommendation: EvaluationReport['rollback_recommendation'] | undefined;
    let versionDelta: Partial<CapabilityMetrics> | undefined;
    let regressionDetected = false;

    // Compare with previous version if exists
    if (this.evaluationHistory.length > 0) {
      const prevReport = this.evaluationHistory[this.evaluationHistory.length - 1];
      const comparison = this.compareVersions(
        prevReport.version,
        prevReport.metrics,
        version,
        metrics
      );

      versionDelta = comparison.metrics_delta;
      regressionDetected = comparison.regression_detected;

      if (regressionDetected && capabilityScore < prevReport.capability_score) {
        rollbackRecommendation = {
          target_version: prevReport.version,
          reason: `Regression detected: ${comparison.regression_areas.join(', ')}`,
        };
      }
    }

    const report: EvaluationReport = {
      evaluation_id: `eval_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      timestamp: new Date().toISOString(),
      version,
      metrics,
      capability_score: capabilityScore,
      version_delta: versionDelta,
      regression_detected: regressionDetected,
      promotion_recommendation: promotionRecommendation,
      rollback_recommendation: rollbackRecommendation,
    };

    this.evaluationHistory.push(report);
    this.currentVersion = version;

    return report;
  }

  /**
   * ★ Round 15: 获取历史评估
   */
  getEvaluationHistory(): EvaluationReport[] {
    return [...this.evaluationHistory];
  }

  /**
   * ★ Round 15: 获取基准任务
   */
  getBenchmarkTasks(): BenchmarkTask[] {
    return Array.from(this.benchmarkTasks.values());
  }

  /**
   * ★ Round 15: 回归检测（供晋升门使用）
   */
  shouldBlockPromotion(currentMetrics: CapabilityMetrics): { blocked: boolean; reason?: string } {
    if (this.evaluationHistory.length === 0) {
      return { blocked: false };
    }

    const prevReport = this.evaluationHistory[this.evaluationHistory.length - 1];
    const comparison = this.compareVersions(
      prevReport.version,
      prevReport.metrics,
      this.currentVersion,
      currentMetrics
    );

    if (comparison.regression_detected) {
      return {
        blocked: true,
        reason: `Regression detected: ${comparison.regression_areas.join(', ')}. Capability score delta: ${comparison.capability_score_delta.toFixed(3)}`,
      };
    }

    return { blocked: false };
  }
}

// ============================================
// PART 3: MULTI-AGENT ORGANIZATIONAL LAYER
// ============================================

/**
 * ★ Round 15: 角色类型
 */
export type AgentRole = 'mission_orchestrator' | 'execution_operator' | 'evolution_distiller' | 'audit_guard' | 'governance_gatekeeper';

/**
 * ★ Round 15: Agent 描述
 */
export interface Agent {
  id: string;
  role: AgentRole;
  name: string;
  allowed_actions: string[];
  forbidden_actions: string[];
  escalation_rules: string[];
  is_active: boolean;
}

/**
 * ★ Round 15: 任务交接记录
 */
export interface HandoffRecord {
  id: string;
  from_agent: string;
  from_role: AgentRole;
  to_agent: string;
  to_role: AgentRole;
  mission_id?: string;
  task_id?: string;
  instruction: string;
  timestamp: string;
  feedback?: string;
  completed: boolean;
}

/**
 * ★ Round 15: 组织追踪条目
 */
export interface OrgTraceEntry {
  timestamp: string;
  action: 'agent_registered' | 'agent_assignment' | 'handoff_initiated' | 'handoff_completed' | 'cross_agent_feedback' | 'governance_separation_event' | 'escalation_triggered';
  from_agent?: string;
  from_role?: AgentRole;
  to_agent?: string;
  to_role?: AgentRole;
  mission_id?: string;
  task_id?: string;
  details: any;
}

/**
 * ★ Round 15: 多自治体组织层
 */
export class MultiAgentOrganization {
  private agents: Map<string, Agent> = new Map();
  private handoffs: HandoffRecord[] = [];
  private trace: OrgTraceEntry[] = [];
  private feedbackCallbacks: Map<AgentRole, Array<(feedback: any) => void>> = new Map();

  constructor() {
    this.initializeDefaultAgents();
  }

  /**
   * ★ Round 15: 初始化默认 Agent
   */
  private initializeDefaultAgents(): void {
    const defaultAgents: Agent[] = [
      {
        id: 'agent_orchestrator',
        role: 'mission_orchestrator',
        name: 'Mission Orchestrator',
        allowed_actions: ['create_mission', 'assign_task', 'request_handoff', 'receive_feedback', 'replan_mission'],
        forbidden_actions: ['execute_task', 'modify_governance_rules', 'bypass_approval'],
        escalation_rules: ['task_failed_3_times', 'mission_blocked', 'resource_deadlock'],
        is_active: true,
      },
      {
        id: 'agent_executor',
        role: 'execution_operator',
        name: 'Execution Operator',
        allowed_actions: ['execute_task', 'report_result', 'request_governance_check', 'release_resource'],
        forbidden_actions: ['create_mission', 'modify_evolution_rules', 'modify_governance_rules', 'bypass_governance'],
        escalation_rules: ['execution_failed', 'resource_conflict', 'task_timeout'],
        is_active: true,
      },
      {
        id: 'agent_distiller',
        role: 'evolution_distiller',
        name: 'Evolution Distiller',
        allowed_actions: ['extract_experience', 'promote_experience', 'create_patch', 'receive_feedback'],
        forbidden_actions: ['execute_task', 'bypass_governance', 'modify_governance_rules'],
        escalation_rules: ['low_confidence_experience', 'anti_pattern_conflict'],
        is_active: true,
      },
      {
        id: 'agent_auditor',
        role: 'audit_guard',
        name: 'Audit Guard',
        allowed_actions: ['evaluate_capability', 'detect_regression', 'generate_report', 'receive_feedback'],
        forbidden_actions: ['execute_task', 'modify_evolution', 'approve_high_risk'],
        escalation_rules: ['regression_detected', 'capability_degradation'],
        is_active: true,
      },
      {
        id: 'agent_gatekeeper',
        role: 'governance_gatekeeper',
        name: 'Governance Gatekeeper',
        allowed_actions: ['approve_task', 'reject_task', 'veto_instruction', 'halt_system', 'receive_feedback'],
        forbidden_actions: ['execute_task', 'modify_evolution', 'create_mission'],
        escalation_rules: ['high_risk_task', 'user_veto', 'system_halt'],
        is_active: true,
      },
    ];

    for (const agent of defaultAgents) {
      this.agents.set(agent.id, agent);
    }

    // Log registrations
    for (const agent of defaultAgents) {
      this.log('agent_registered', { agent_id: agent.id, role: agent.role });
    }
  }

  /**
   * ★ Round 15: 获取 Agent
   */
  getAgent(agentId: string): Agent | undefined {
    return this.agents.get(agentId);
  }

  /**
   * ★ Round 15: 获取某角色的所有 Agent
   */
  getAgentsByRole(role: AgentRole): Agent[] {
    return Array.from(this.agents.values()).filter(a => a.role === role);
  }

  /**
   * ★ Round 15: 执行 handoff
   */
  performHandoff(
    fromAgentId: string,
    toRole: AgentRole,
    instruction: string,
    missionId?: string,
    taskId?: string
  ): HandoffRecord | null {
    const fromAgent = this.agents.get(fromAgentId);
    if (!fromAgent) return null;

    // Find a suitable agent of the target role
    const targetAgents = this.getAgentsByRole(toRole);
    if (targetAgents.length === 0) return null;

    const toAgent = targetAgents[0];

    const record: HandoffRecord = {
      id: `handoff_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      from_agent: fromAgentId,
      from_role: fromAgent.role,
      to_agent: toAgent.id,
      to_role: toRole,
      mission_id: missionId,
      task_id: taskId,
      instruction,
      timestamp: new Date().toISOString(),
      completed: false,
    };

    this.handoffs.push(record);
    this.log('handoff_initiated', { from_agent: fromAgentId, from_role: fromAgent.role, to_agent: toAgent.id, to_role: toRole, mission_id: missionId, task_id: taskId, details: { instruction } });

    return record;
  }

  /**
   * ★ Round 15: 完成 handoff 并提供反馈
   */
  completeHandoff(handoffId: string, feedback: string, success: boolean): boolean {
    const handoff = this.handoffs.find(h => h.id === handoffId);
    if (!handoff) return false;

    handoff.completed = true;
    handoff.feedback = feedback;

    this.log('handoff_completed', { from_agent: handoff.from_agent, from_role: handoff.from_role, to_agent: handoff.to_agent, to_role: handoff.to_role, mission_id: handoff.mission_id, task_id: handoff.task_id, details: { feedback, success } });

    // Trigger cross-agent feedback
    this.deliverFeedback(handoff.from_role, { handoff_id: handoffId, feedback, success, to_role: handoff.to_role });

    return true;
  }

  /**
   * ★ Round 15: 注册反馈回调
   */
  registerFeedbackCallback(role: AgentRole, callback: (feedback: any) => void): void {
    if (!this.feedbackCallbacks.has(role)) {
      this.feedbackCallbacks.set(role, []);
    }
    this.feedbackCallbacks.get(role)!.push(callback);
  }

  /**
   * ★ Round 15: 传递反馈给某角色
   */
  private deliverFeedback(toRole: AgentRole, feedback: any): void {
    const callbacks = this.feedbackCallbacks.get(toRole);
    if (callbacks) {
      for (const cb of callbacks) {
        cb(feedback);
      }
    }
    this.log('cross_agent_feedback', { to_role: toRole, feedback });
  }

  /**
   * ★ Round 15: 检查治理分离（执行体不能做高风险决策）
   */
  checkGovernanceSeparation(agentId: string, action: string): { allowed: boolean; reason?: string } {
    const agent = this.agents.get(agentId);
    if (!agent) return { allowed: false, reason: 'agent not found' };

    // High-risk governance actions
    const highRiskActions = ['approve_task', 'veto_instruction', 'halt_system', 'modify_governance_rules'];

    if (agent.role === 'execution_operator' && highRiskActions.includes(action)) {
      this.log('governance_separation_event', { agent_id: agentId, action, reason: 'execution_operator cannot perform governance actions' });
      return { allowed: false, reason: `${agent.role} is not allowed to perform ${action}` };
    }

    if (agent.role === 'governance_gatekeeper' && action === 'execute_task') {
      this.log('governance_separation_event', { agent_id: agentId, action, reason: 'governance_gatekeeper cannot execute tasks' });
      return { allowed: false, reason: `${agent.role} is not allowed to execute tasks` };
    }

    return { allowed: true };
  }

  /**
   * ★ Round 15: 验证 Agent 行为是否在允许列表内
   */
  validateAgentAction(agentId: string, action: string): { allowed: boolean; forbidden_action?: string } {
    const agent = this.agents.get(agentId);
    if (!agent) return { allowed: false };

    if (agent.forbidden_actions.includes(action)) {
      this.log('governance_separation_event', { agent_id: agentId, action, reason: `forbidden action: ${action}` });
      return { allowed: false, forbidden_action: action };
    }

    return { allowed: true };
  }

  /**
   * ★ Round 15: 触发升级
   */
  triggerEscalation(fromAgentId: string, reason: string, missionId?: string): void {
    const agent = this.agents.get(fromAgentId);
    if (!agent) return;

    // Find escalation target (orchestrator handles escalations)
    const orchestrators = this.getAgentsByRole('mission_orchestrator');
    if (orchestrators.length > 0) {
      this.log('escalation_triggered', { from_agent: fromAgentId, from_role: agent.role, to_agent: orchestrators[0].id, to_role: 'mission_orchestrator', mission_id: missionId, details: { reason } });
    }
  }

  /**
   * ★ Round 15: 获取追踪日志
   */
  getTrace(): OrgTraceEntry[] {
    return [...this.trace];
  }

  /**
   * ★ Round 15: 获取 handoff 历史
   */
  getHandoffHistory(): HandoffRecord[] {
    return [...this.handoffs];
  }

  private log(
    action: OrgTraceEntry['action'],
    params: any
  ): void {
    let fromAgent: string | undefined;
    let fromRole: AgentRole | undefined;
    let toAgent: string | undefined;
    let toRole: AgentRole | undefined;
    let missionId: string | undefined;
    let taskId: string | undefined;
    let details: any;

    if (typeof params === 'object' && 'agent_id' in params) {
      details = params;
    } else if (params.from_agent !== undefined) {
      fromAgent = params.from_agent;
      fromRole = params.from_role;
      toAgent = params.to_agent;
      toRole = params.to_role;
      missionId = params.mission_id;
      taskId = params.task_id;
      details = params.instruction || params;
    } else {
      details = params;
    }

    this.trace.push({
      timestamp: new Date().toISOString(),
      action,
      from_agent: fromAgent,
      from_role: fromRole,
      to_agent: toAgent,
      to_role: toRole,
      mission_id: missionId,
      task_id: taskId,
      details,
    });
  }
}

// ============================================
// PART 4: INTEGRATED MISSION ENGINE
// ============================================

/**
 * ★ Round 15: 使命评估引擎（整合所有子系统）
 */
export class MissionEvaluationEngine {
  missions: MissionRegistry;
  evaluation: CapabilityEvaluationEngine;
  organization: MultiAgentOrganization;

  constructor() {
    this.missions = new MissionRegistry();
    this.evaluation = new CapabilityEvaluationEngine();
    this.organization = new MultiAgentOrganization();

    // Set up feedback loop: auditor -> evolution distiller
    this.organization.registerFeedbackCallback('evolution_distiller', (feedback) => {
      // Auditor feedback triggers evaluation review
      console.log(`[Auditor->Distiller] Feedback: ${JSON.stringify(feedback)}`);
    });
  }

  /**
   * ★ Round 15: 创建使命并分配给 orchestrator
   */
  createAndAssignMission(missionGoal: string, priority?: TaskPriority): Mission {
    const mission = this.missions.createMission(missionGoal, priority);

    // Orchestrator assigns to execution operator
    this.organization.performHandoff(
      'agent_orchestrator',
      'execution_operator',
      `Execute mission: ${missionGoal}`,
      mission.id
    );

    return mission;
  }

  /**
   * ★ Round 15: 执行使命级评估
   */
  evaluateMission(missionId: string, taskResults: any[]): EvaluationReport {
    const mission = this.missions.getMission(missionId);
    if (!mission) {
      throw new Error(`Mission ${missionId} not found`);
    }

    const version = `mission_${missionId}_v${Date.now()}`;
    const report = this.evaluation.evaluate(version, taskResults);

    // If regression detected, trigger escalation
    if (report.regression_detected) {
      this.organization.triggerEscalation('agent_auditor', `Regression in mission ${missionId}`, missionId);
    }

    return report;
  }

  /**
   * ★ Round 15: 获取完整追踪
   */
  getFullTrace(): {
    mission_trace: MissionTraceEntry[];
    evaluation_history: EvaluationReport[];
    org_trace: OrgTraceEntry[];
    handoff_history: HandoffRecord[];
  } {
    return {
      mission_trace: this.missions.getTrace(),
      evaluation_history: this.evaluation.getEvaluationHistory(),
      org_trace: this.organization.getTrace(),
      handoff_history: this.organization.getHandoffHistory(),
    };
  }
}

// ============================================
// 单例
// ============================================
export const missionEvaluationEngine = new MissionEvaluationEngine();
