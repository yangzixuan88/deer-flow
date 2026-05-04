/**
 * M16 战略组合管理 + 制度级记忆 + 模拟实验决策
 * ================================================
 * Round 16: 战略组织智能层
 * ================================================
 */

import {
  MissionRegistry, Mission, MissionTraceEntry,
} from './mission_evaluation_round15';
import {
  TaskPriority,
} from './autonomous_governance_round12';
import {
  ControlledEvolutionEngine, StrategyPatch,
} from './autonomous_durable_round14';
import * as fs from 'fs';
import * as path from 'path';

// ============================================
// PART 1: STRATEGIC MISSION PORTFOLIO LAYER
// ============================================

/**
 * ★ Round 16: Portfolio 任务状态
 */
export type PortfolioMissionStatus = 'active' | 'deferred' | 'killed' | 'completed' | 'frozen';

/**
 * ★ Round 16: Portfolio 决策类型
 */
export type PortfolioDecisionType = 'accelerate' | 'continue' | 'defer' | 'kill' | 'escalate_for_human_review';

/**
 * ★ Round 16: Portfolio Mission 条目
 */
export interface PortfolioMission {
  mission_id: string;
  mission_goal: string;
  status: PortfolioMissionStatus;
  priority: TaskPriority;
  expected_value: number;      // 0-1, 预期收益
  execution_cost: number;      // 估算执行成本
  strategic_alignment: number; // 0-1, 战略一致性
  mission_risk: number;        // 0-1, 风险等级
  dependency_load: number;     // 0-1, 依赖负载
  progress: number;            // 0-1, 当前进度
  roi: number;                 // 计算得出的 ROI
  created_at: string;
  updated_at: string;
  kill_reason?: string;
  defer_reason?: string;
  drift_score: number;         // 价值漂移检测
}

/**
 * ★ Round 16: Portfolio 得分
 */
export interface PortfolioScore {
  total_expected_value: number;
  total_execution_cost: number;
  total_strategic_alignment: number;
  average_mission_risk: number;
  total_dependency_load: number;
  portfolio_health: number;    // 综合健康度
  timestamp: string;
}

/**
 * ★ Round 16: Portfolio 决策
 */
export interface PortfolioDecision {
  decision_id: string;
  mission_id: string;
  decision: PortfolioDecisionType;
  reason: string;
  expected_impact: number;
  timestamp: string;
  applied: boolean;
}

/**
 * ★ Round 16: Portfolio 追踪条目
 */
export interface PortfolioTraceEntry {
  timestamp: string;
  action: 'mission_added' | 'mission_killed' | 'mission_deferred' | 'mission_accelerated' | 'mission_continued' | 'portfolio_scored' | 'rebalance_decision' | 'drift_detected' | 'human_escalation';
  mission_id?: string;
  details: any;
}

/**
 * ★ Round 16: 战略 Mission Portfolio 管理器
 */
export class StrategicPortfolioManager {
  private portfolio: Map<string, PortfolioMission> = new Map();
  private trace: PortfolioTraceEntry[] = [];
  private decisions: PortfolioDecision[] = [];

  /**
   * ★ Round 16: 添加 Mission 到 Portfolio
   */
  addMission(
    missionId: string,
    missionGoal: string,
    priority: TaskPriority,
    expectedValue: number = 0.5,
    executionCost: number = 0.5,
    strategicAlignment: number = 0.5
  ): void {
    const entry: PortfolioMission = {
      mission_id: missionId,
      mission_goal: missionGoal,
      status: 'active',
      priority,
      expected_value: expectedValue,
      execution_cost: executionCost,
      strategic_alignment: strategicAlignment,
      mission_risk: 0.3,
      dependency_load: 0.2,
      progress: 0,
      roi: this.calculateROI(expectedValue, executionCost),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      drift_score: 0,
    };

    this.portfolio.set(missionId, entry);
    this.log('mission_added', missionId, { goal: missionGoal, priority, expected_value: expectedValue });
  }

  /**
   * ★ Round 16: 更新 Mission 进度
   */
  updateMissionProgress(missionId: string, progress: number): void {
    const mission = this.portfolio.get(missionId);
    if (!mission) return;
    mission.progress = progress;
    mission.updated_at = new Date().toISOString();
  }

  /**
   * ★ Round 16: 更新 Mission 指标
   */
  updateMissionMetrics(
    missionId: string,
    metrics: { expected_value?: number; execution_cost?: number; mission_risk?: number; dependency_load?: number }
  ): void {
    const mission = this.portfolio.get(missionId);
    if (!mission) return;

    if (metrics.expected_value !== undefined) mission.expected_value = metrics.expected_value;
    if (metrics.execution_cost !== undefined) mission.execution_cost = metrics.execution_cost;
    if (metrics.mission_risk !== undefined) mission.mission_risk = metrics.mission_risk;
    if (metrics.dependency_load !== undefined) mission.dependency_load = metrics.dependency_load;

    mission.roi = this.calculateROI(mission.expected_value, mission.execution_cost);
    mission.updated_at = new Date().toISOString();
  }

  /**
   * ★ Round 16: 计算 ROI
   */
  private calculateROI(expectedValue: number, executionCost: number): number {
    if (executionCost === 0) return expectedValue;
    return expectedValue / (executionCost * 2);
  }

  /**
   * ★ Round 16: 计算 Portfolio 得分
   */
  computePortfolioScore(): PortfolioScore {
    const missions = Array.from(this.portfolio.values());
    if (missions.length === 0) {
      return {
        total_expected_value: 0,
        total_execution_cost: 0,
        total_strategic_alignment: 0,
        average_mission_risk: 0,
        total_dependency_load: 0,
        portfolio_health: 0,
        timestamp: new Date().toISOString(),
      };
    }

    const activeMissions = missions.filter(m => m.status === 'active');
    const totalExpectedValue = activeMissions.reduce((sum, m) => sum + m.expected_value * m.progress, 0);
    const totalExecutionCost = activeMissions.reduce((sum, m) => sum + m.execution_cost * m.progress, 0);
    const totalStrategicAlignment = activeMissions.reduce((sum, m) => sum + m.strategic_alignment, 0) / activeMissions.length;
    const averageMissionRisk = activeMissions.reduce((sum, m) => sum + m.mission_risk, 0) / activeMissions.length;
    const totalDependencyLoad = activeMissions.reduce((sum, m) => sum + m.dependency_load, 0);

    // Portfolio health = (value - cost - risk - dependency) normalized
    const portfolioHealth = Math.max(0, Math.min(1,
      (totalExpectedValue - totalExecutionCost - averageMissionRisk - totalDependencyLoad * 0.1) / 2
    ));

    this.log('portfolio_scored', undefined, {
      total_expected_value: totalExpectedValue,
      total_execution_cost: totalExecutionCost,
      portfolio_health: portfolioHealth,
    });

    return {
      total_expected_value: totalExpectedValue,
      total_execution_cost: totalExecutionCost,
      total_strategic_alignment: totalStrategicAlignment,
      average_mission_risk: averageMissionRisk,
      total_dependency_load: totalDependencyLoad,
      portfolio_health: portfolioHealth,
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * ★ Round 16: 价值漂移检测
   */
  detectValueDrift(missionId: string, currentValue: number): number {
    const mission = this.portfolio.get(missionId);
    if (!mission) return 0;

    // Drift = initial expected value - current observed value
    const drift = mission.expected_value - currentValue;
    mission.drift_score = Math.abs(drift);

    if (Math.abs(drift) > 0.2) {
      this.log('drift_detected', missionId, {
        initial_expected: mission.expected_value,
        current_value: currentValue,
        drift_score: mission.drift_score,
      });
    }

    return mission.drift_score;
  }

  /**
   * ★ Round 16: 产出 Portfolio 决策
   */
  makeDecision(missionId: string, context: {
    resourcePressure?: number;
    driftScore?: number;
    lowROI?: boolean;
    humanEscalation?: boolean;
  }): PortfolioDecision {
    const mission = this.portfolio.get(missionId);
    if (!mission) {
      return {
        decision_id: `dec_${Date.now()}`,
        mission_id: missionId,
        decision: 'escalate_for_human_review',
        reason: 'mission not found in portfolio',
        expected_impact: 0,
        timestamp: new Date().toISOString(),
        applied: false,
      };
    }

    let decision: PortfolioDecisionType;
    let reason: string;
    let expectedImpact: number;

    // Decision logic
    if (context.humanEscalation) {
      decision = 'escalate_for_human_review';
      reason = 'Human review requested';
      expectedImpact = 0;
      this.log('human_escalation', missionId, { reason });
    } else if (context.lowROI || mission.roi < 0.2) {
      decision = 'kill';
      reason = `Low ROI: ${mission.roi.toFixed(3)} < 0.2 threshold`;
      expectedImpact = -0.1;
      mission.status = 'killed';
      mission.kill_reason = reason;
      this.log('mission_killed', missionId, { roi: mission.roi, reason });
    } else if ((context.driftScore !== undefined && context.driftScore >= 0.3) || mission.drift_score >= 0.3) {
      decision = 'defer';
      reason = `Value drift detected: ${context.driftScore || mission.drift_score} > 0.3`;
      expectedImpact = 0.1;
      mission.status = 'deferred';
      mission.defer_reason = reason;
      this.log('mission_deferred', missionId, { drift: context.driftScore || mission.drift_score, reason });
    } else if (context.resourcePressure !== undefined && context.resourcePressure > 0.8 && mission.priority === 'background') {
      decision = 'defer';
      reason = 'Resource pressure, background mission deferred';
      expectedImpact = 0.05;
      mission.status = 'deferred';
      mission.defer_reason = reason;
      this.log('mission_deferred', missionId, { resource_pressure: context.resourcePressure, reason });
    } else if (mission.priority === 'urgent' && mission.status === 'active') {
      decision = 'accelerate';
      reason = 'Urgent priority mission, accelerating';
      expectedImpact = 0.2;
      this.log('mission_accelerated', missionId, { reason });
    } else {
      decision = 'continue';
      reason = 'Mission on track, continuing';
      expectedImpact = 0;
      this.log('mission_continued', missionId, { reason });
    }

    const portfolioDecision: PortfolioDecision = {
      decision_id: `dec_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      mission_id: missionId,
      decision,
      reason,
      expected_impact: expectedImpact,
      timestamp: new Date().toISOString(),
      applied: false,
    };

    this.decisions.push(portfolioDecision);
    this.log('rebalance_decision', missionId, { decision, reason, expected_impact: expectedImpact });

    return portfolioDecision;
  }

  /**
   * ★ Round 16: 跨 Mission 资源重分配
   */
  rebalanceResources(missionId1: string, missionId2: string, reallocationRatio: number = 0.2): boolean {
    const m1 = this.portfolio.get(missionId1);
    const m2 = this.portfolio.get(missionId2);
    if (!m1 || !m2) return false;

    // Transfer some expected value from m1 to m2 based on ratio
    const transferredValue = m1.expected_value * reallocationRatio;
    m1.expected_value = Math.max(0.1, m1.expected_value - transferredValue);
    m2.expected_value = Math.min(1, m2.expected_value + transferredValue);

    // Recalculate ROI
    m1.roi = this.calculateROI(m1.expected_value, m1.execution_cost);
    m2.roi = this.calculateROI(m2.expected_value, m2.execution_cost);

    this.log('rebalance_decision', missionId1, {
      action: 'resource_transfer',
      from: missionId1,
      to: missionId2,
      ratio: reallocationRatio,
      transferred_value: transferredValue,
    });

    return true;
  }

  /**
   * ★ Round 16: 获取 Portfolio 中所有 Mission
   */
  getPortfolioMissions(): PortfolioMission[] {
    return Array.from(this.portfolio.values());
  }

  /**
   * ★ Round 16: 获取活跃 Mission
   */
  getActiveMissions(): PortfolioMission[] {
    return Array.from(this.portfolio.values()).filter(m => m.status === 'active');
  }

  /**
   * ★ Round 16: 获取追踪日志
   */
  getTrace(): PortfolioTraceEntry[] {
    return [...this.trace];
  }

  /**
   * ★ Round 16: 获取所有决策
   */
  getDecisions(): PortfolioDecision[] {
    return [...this.decisions];
  }

  private log(action: PortfolioTraceEntry['action'], missionId: string | undefined, details: any): void {
    this.trace.push({
      timestamp: new Date().toISOString(),
      action,
      mission_id: missionId,
      details,
    });
  }
}

// ============================================
// PART 2: INSTITUTIONAL MEMORY LAYER
// ============================================

/**
 * ★ Round 16: 记忆类型
 */
export type MemoryType = 'precedent' | 'failure_case' | 'governance_case' | 'recovery_case' | 'mission_playbook';

/**
 * ★ Round 16: 记忆条目
 */
export interface MemoryEntry {
  id: string;
  type: MemoryType;
  title: string;
  content: string;
  confidence: number;           // 0-1, 置信度
  reuse_count: number;          // 被复用次数
  last_used_at?: string;
  created_at: string;
  applicable_context: string[];  // 适用场景标签
  superseded_by?: string;       // 被哪条记忆替代
  deprecated: boolean;
  tags: string[];
}

/**
 * ★ Round 16: 记忆检索结果
 */
export interface MemoryRetrievalResult {
  memory: MemoryEntry;
  relevance_score: number;
  retrieved_for_decision?: string;
}

/**
 * ★ Round 16: 制度级记忆管理器
 */
export class InstitutionalMemory {
  private memories: Map<string, MemoryEntry> = new Map();
  private index: Map<string, string[]> = new Map(); // tag -> memory IDs
  private trace: Array<{
    timestamp: string;
    action: 'memory_created' | 'memory_retrieved' | 'memory_applied' | 'memory_superseded';
    memory_id?: string;
    decision_context?: string;
    details: any;
  }> = [];

  constructor() {
    this.initializeDefaultMemories();
  }

  /**
   * ★ Round 16: 初始化默认记忆（制度沉淀）
   */
  private initializeDefaultMemories(): void {
    const defaults: Omit<MemoryEntry, 'id' | 'created_at'>[] = [
      {
        type: 'precedent',
        title: 'High-risk task approval workflow',
        content: 'When a task has approval_state=approval_required and task_type in HIGH_RISK_PATTERNS, governance should block execution and require explicit user approval.',
        confidence: 0.9,
        reuse_count: 0,
        applicable_context: ['high_risk_task', 'approval_required', 'governance_block'],
        deprecated: false,
        tags: ['governance', 'high_risk', 'approval'],
      },
      {
        type: 'failure_case',
        title: 'Shared resource lock preemption pattern',
        content: 'When a shared lock is held and a preemptible exclusive request comes in with higher priority, the shared lock should be preempted. Priority threshold: 3+ points difference.',
        confidence: 0.85,
        reuse_count: 0,
        applicable_context: ['resource_lock', 'preemption', 'priority_conflict'],
        deprecated: false,
        tags: ['resource_management', 'lock', 'priority'],
      },
      {
        type: 'recovery_case',
        title: 'Self-heal on executor health check failure',
        content: 'When executor health check fails, attempt self-heal by restarting the executor adapter. If self-heal fails after 3 attempts, escalate to human review.',
        confidence: 0.8,
        reuse_count: 0,
        applicable_context: ['executor_health', 'self_heal', 'escalation'],
        deprecated: false,
        tags: ['health_check', 'recovery', 'escalation'],
      },
      {
        type: 'governance_case',
        title: 'Mission freeze when governance_state=frozen',
        content: 'When a mission governance_state becomes frozen, all tasks in that mission should be paused immediately. No new tasks should be started for frozen missions.',
        confidence: 0.95,
        reuse_count: 0,
        applicable_context: ['mission_freeze', 'governance_state', 'pause_tasks'],
        deprecated: false,
        tags: ['governance', 'mission_control', 'freeze'],
      },
      {
        type: 'mission_playbook',
        title: 'Decompose large mission into 3-5 subgoals',
        content: 'Missions with more than 5 subgoals tend to have lower completion rates. Best practice: decompose into 3-5 subgoals, each with 2-4 tasks.',
        confidence: 0.75,
        reuse_count: 0,
        applicable_context: ['mission_planning', 'subgoal_decomposition', 'mission_structure'],
        deprecated: false,
        tags: ['mission_design', 'subgoal', 'best_practice'],
      },
    ];

    for (const mem of defaults) {
      const id = `mem_${mem.type}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
      const entry: MemoryEntry = { ...mem, id, created_at: new Date().toISOString() };
      this.memories.set(id, entry);

      // Index by tags
      for (const tag of mem.tags) {
        if (!this.index.has(tag)) this.index.set(tag, []);
        this.index.get(tag)!.push(id);
      }
    }
  }

  /**
   * ★ Round 16: 添加记忆
   */
  addMemory(
    type: MemoryType,
    title: string,
    content: string,
    applicableContext: string[],
    tags: string[],
    confidence: number = 0.5
  ): MemoryEntry {
    const id = `mem_${type}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const entry: MemoryEntry = {
      id,
      type,
      title,
      content,
      confidence,
      reuse_count: 0,
      created_at: new Date().toISOString(),
      applicable_context: applicableContext,
      deprecated: false,
      tags,
    };

    this.memories.set(id, entry);

    for (const tag of tags) {
      if (!this.index.has(tag)) this.index.set(tag, []);
      this.index.get(tag)!.push(id);
    }

    this.log('memory_created', id, { type, title });
    return entry;
  }

  /**
   * ★ Round 16: 检索相关记忆
   */
  retrieve(context: string, decisionType?: string, limit: number = 5): MemoryRetrievalResult[] {
    const contextTags = context.toLowerCase().split(/[\s,_-]+/).filter(t => t.length > 2);
    const results: MemoryRetrievalResult[] = [];

    // Find candidate memories
    const candidateIds = new Set<string>();
    for (const tag of contextTags) {
      const ids = this.index.get(tag);
      if (ids) {
        for (const id of ids) {
          const mem = this.memories.get(id);
          if (mem && !mem.deprecated) candidateIds.add(id);
        }
      }
    }

    // Score and rank
    for (const id of candidateIds) {
      const mem = this.memories.get(id)!;
      let relevance = 0;

      // Tag overlap
      for (const tag of contextTags) {
        if (mem.tags.includes(tag)) relevance += 0.3;
        if (mem.applicable_context.some(c => c.toLowerCase().includes(tag))) relevance += 0.2;
      }

      // Decision type match
      if (decisionType) {
        const dtl = decisionType.toLowerCase();
        if (mem.applicable_context.some(c => c.toLowerCase().includes(dtl))) relevance += 0.4;
      }

      // Confidence bonus
      relevance += mem.confidence * 0.2;

      if (relevance > 0) {
        results.push({ memory: mem, relevance_score: relevance, retrieved_for_decision: decisionType });
      }
    }

    results.sort((a, b) => b.relevance_score - a.relevance_score);
    const top = results.slice(0, limit);

    // Log retrieval
    for (const r of top) {
      this.log('memory_retrieved', r.memory.id, {
        context,
        decision_type: decisionType,
        relevance_score: r.relevance_score,
      });
    }

    return top;
  }

  /**
   * ★ Round 16: 应用记忆到决策（增加复用计数）
   */
  applyMemory(memoryId: string, decisionContext: string): boolean {
    const mem = this.memories.get(memoryId);
    if (!mem || mem.deprecated) return false;

    mem.reuse_count++;
    mem.last_used_at = new Date().toISOString();

    this.log('memory_applied', memoryId, { decision_context: decisionContext, new_reuse_count: mem.reuse_count });
    return true;
  }

  /**
   * ★ Round 16: 标记记忆为过时
   */
  supersede(memoryId: string, supersedingMemoryId: string, reason: string): boolean {
    const mem = this.memories.get(memoryId);
    if (!mem) return false;

    mem.deprecated = true;
    mem.superseded_by = supersedingMemoryId;

    this.log('memory_superseded', memoryId, { superseding_id: supersedingMemoryId, reason });
    return true;
  }

  /**
   * ★ Round 16: 获取所有有效记忆
   */
  getActiveMemories(): MemoryEntry[] {
    return Array.from(this.memories.values()).filter(m => !m.deprecated);
  }

  /**
   * ★ Round 16: 获取某类型记忆
   */
  getMemoriesByType(type: MemoryType): MemoryEntry[] {
    return Array.from(this.memories.values()).filter(m => m.type === type && !m.deprecated);
  }

  /**
   * ★ Round 16: 获取追踪日志
   */
  getTrace(): Array<{
    timestamp: string;
    action: string;
    memory_id?: string;
    decision_context?: string;
    details: any;
  }> {
    return [...this.trace];
  }

  private log(
    action: 'memory_created' | 'memory_retrieved' | 'memory_applied' | 'memory_superseded',
    memoryId: string | undefined,
    details: any
  ): void {
    this.trace.push({
      timestamp: new Date().toISOString(),
      action,
      memory_id: memoryId,
      details,
    });
  }
}

// ============================================
// PART 3: SIMULATION & EXPERIMENT DECISION LAYER
// ============================================

/**
 * ★ Round 16: 实验结果
 */
export type ExperimentResult = 'success' | 'failure' | 'inconclusive' | 'regression';

/**
 * ★ Round 16: 实验状态
 */
export type ExperimentStatus = 'running' | 'completed' | 'rolled_back';

/**
 * ★ Round 16: 实验条目
 */
export interface Experiment {
  id: string;
  hypothesis: string;
  tested_change: string;
  metrics_before?: Record<string, number>;
  metrics_after?: Record<string, number>;
  result: ExperimentResult;
  rollout_recommendation: 'full_rollout' | 'partial_rollout' | 'rollback' | 'hold';
  risk_envelope: {
    expected_gain: number;
    expected_risk: number;
    uncertainty: number;
    rollback_cost: number;
  };
  timestamp: string;
  status: ExperimentStatus;
}

/**
 * ★ Round 16: 模拟结果
 */
export interface SimulationResult {
  simulated: boolean;
  predicted_outcome: string;
  expected_metrics: Record<string, number>;
  confidence: number;
  warnings: string[];
  dry_run: boolean;
}

/**
 * ★ Round 16: 战略实验管理器
 */
export class StrategicExperimentEngine {
  private experiments: Map<string, Experiment> = new Map();
  private simulationHistory: SimulationResult[] = [];
  private trace: Array<{
    timestamp: string;
    action: 'simulation_run' | 'experiment_started' | 'experiment_completed' | 'promotion_blocked_by_simulation' | 'rollout_recommended';
    experiment_id?: string;
    details: any;
  }> = [];

  /**
   * ★ Round 16: 运行反事实模拟
   */
  simulate(
    change: string,
    currentMetrics: Record<string, number>,
    changeType: 'strategy_patch' | 'portfolio_policy' | 'governance_rule'
  ): SimulationResult {
    // Simple simulation: predict outcome based on change type
    const warnings: string[] = [];
    let predictedOutcome = '';
    let expectedMetrics = { ...currentMetrics };
    let confidence = 0.7;
    let expectedGain = 0;
    let expectedRisk = 0;

    if (changeType === 'strategy_patch') {
      // Strategy patches tend to improve success_rate by 0.05-0.15
      expectedGain = 0.08;
      expectedRisk = 0.03;
      expectedMetrics = {
        ...currentMetrics,
        success_rate: Math.min(1, (currentMetrics.success_rate || 0) + expectedGain),
        capability_score: Math.min(1, (currentMetrics.capability_score || 0) + expectedGain * 0.5),
      };
      predictedOutcome = 'Strategy patch expected to improve success_rate by ~8%';
      confidence = 0.75;
    } else if (changeType === 'portfolio_policy') {
      // Portfolio policy changes affect resource reallocation
      expectedGain = 0.1;
      expectedRisk = 0.05;
      expectedMetrics = {
        ...currentMetrics,
        portfolio_health: Math.min(1, (currentMetrics.portfolio_health || 0) + expectedGain),
        total_execution_cost: Math.max(0, (currentMetrics.total_execution_cost || 0) - expectedGain * 0.3),
      };
      predictedOutcome = 'Portfolio rebalancing expected to improve portfolio health by ~10%';
      confidence = 0.65;
    } else if (changeType === 'governance_rule') {
      // Governance changes are higher risk
      expectedGain = 0.05;
      expectedRisk = 0.12;
      if (change.toLowerCase().includes('relax') || change.toLowerCase().includes('lower')) {
        expectedRisk = 0.2;
        warnings.push('Relaxing governance rules increases risk exposure');
      }
      predictedOutcome = 'Governance change has moderate expected gain but elevated risk';
      confidence = 0.6;
    }

    const result: SimulationResult = {
      simulated: true,
      predicted_outcome: predictedOutcome,
      expected_metrics: expectedMetrics,
      confidence,
      warnings,
      dry_run: true,
    };

    this.simulationHistory.push(result);
    this.log('simulation_run', undefined, { change, change_type: changeType, predicted_outcome: predictedOutcome });

    return result;
  }

  /**
   * ★ Round 16: 干跑 Strategy Patch（不实际应用）
   */
  dryRunPatch(patch: StrategyPatch, currentState: Record<string, number>): SimulationResult {
    const change = `Apply patch v${patch.version}: ${JSON.stringify(patch.changes.slice(0, 2))}`;
    return this.simulate(change, currentState, 'strategy_patch');
  }

  /**
   * ★ Round 16: 创建实验
   */
  createExperiment(
    hypothesis: string,
    testedChange: string,
    metricsBefore?: Record<string, number>
  ): Experiment {
    const id = `exp_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

    const experiment: Experiment = {
      id,
      hypothesis,
      tested_change: testedChange,
      metrics_before: metricsBefore,
      result: 'inconclusive',
      rollout_recommendation: 'hold',
      risk_envelope: {
        expected_gain: 0,
        expected_risk: 0,
        uncertainty: 0.5,
        rollback_cost: 0.1,
      },
      timestamp: new Date().toISOString(),
      status: 'running',
    };

    this.experiments.set(id, experiment);
    this.log('experiment_started', id, { hypothesis, tested_change: testedChange });

    return experiment;
  }

  /**
   * ★ Round 16: 完成实验并产出 rollout recommendation
   */
  completeExperiment(
    experimentId: string,
    metricsAfter: Record<string, number>,
    rolloutRecommendation?: 'full_rollout' | 'partial_rollout' | 'rollback' | 'hold'
  ): Experiment | null {
    const exp = this.experiments.get(experimentId);
    if (!exp) return null;

    exp.metrics_after = metricsAfter;
    exp.status = 'completed';

    // Determine result based on metrics
    const beforeSuccessRate = exp.metrics_before?.success_rate ?? 0.5;
    const afterSuccessRate = metricsAfter.success_rate ?? 0.5;
    const improvement = afterSuccessRate - beforeSuccessRate;

    if (improvement > 0.05) {
      exp.result = 'success';
    } else if (improvement < -0.03) {
      exp.result = 'regression';
    } else {
      exp.result = 'inconclusive';
    }

    // Compute risk envelope
    exp.risk_envelope = {
      expected_gain: Math.max(0, improvement),
      expected_risk: Math.abs(Math.min(0, improvement)) + 0.05,
      uncertainty: 0.3,
      rollback_cost: 0.1,
    };

    // Determine rollout recommendation
    if (rolloutRecommendation) {
      exp.rollout_recommendation = rolloutRecommendation;
    } else if (exp.result === 'success' && exp.risk_envelope.expected_risk < 0.15) {
      exp.rollout_recommendation = 'full_rollout';
    } else if (exp.result === 'success') {
      exp.rollout_recommendation = 'partial_rollout';
    } else if (exp.result === 'regression') {
      exp.rollout_recommendation = 'rollback';
    } else {
      exp.rollout_recommendation = 'hold';
    }

    this.log('experiment_completed', experimentId, {
      result: exp.result,
      rollout_recommendation: exp.rollout_recommendation,
      improvement,
    });

    // If regression, log as blocked
    if (exp.result === 'regression') {
      this.log('promotion_blocked_by_simulation', experimentId, {
        reason: 'Regression detected in experiment',
        expected_risk: exp.risk_envelope.expected_risk,
      });
    }

    return exp;
  }

  /**
   * ★ Round 16: 影子对比（Shadow comparison）
   */
  shadowCompare(
    policyA: string,
    policyB: string,
    currentMetrics: Record<string, number>
  ): { winner: string; confidence: number; recommendation: string } {
    const simA = this.simulate(policyA, currentMetrics, 'governance_rule');
    const simB = this.simulate(policyB, currentMetrics, 'governance_rule');

    // Compare expected gains
    const gainA = simA.expected_metrics.success_rate - (currentMetrics.success_rate || 0);
    const gainB = simB.expected_metrics.success_rate - (currentMetrics.success_rate || 0);

    let winner: string;
    let recommendation: string;

    if (gainB > gainA + 0.02) {
      winner = policyB;
      recommendation = 'promote_b';
    } else if (gainA > gainB + 0.02) {
      winner = policyA;
      recommendation = 'promote_a';
    } else {
      winner = 'keep_both';
      recommendation = 'keep_both';
    }

    const confidence = Math.abs(gainA - gainB) < 0.02 ? 0.5 : 0.8;

    return { winner, confidence, recommendation };
  }

  /**
   * ★ Round 16: 检查是否应阻止晋升
   */
  shouldBlockPromotion(experimentId: string): { blocked: boolean; reason?: string } {
    const exp = this.experiments.get(experimentId);
    if (!exp || exp.status !== 'completed') {
      return { blocked: false };
    }

    if (exp.result === 'regression') {
      return {
        blocked: true,
        reason: `Experiment ${experimentId} showed regression, promotion blocked`,
      };
    }

    if (exp.risk_envelope.expected_risk > 0.2) {
      return {
        blocked: true,
        reason: `Experiment ${experimentId} risk envelope too high: ${exp.risk_envelope.expected_risk}`,
      };
    }

    return { blocked: false };
  }

  /**
   * ★ Round 16: 获取所有实验
   */
  getExperiments(): Experiment[] {
    return Array.from(this.experiments.values());
  }

  /**
   * ★ Round 16: 获取实验追踪日志
   */
  getTrace(): Array<{
    timestamp: string;
    action: string;
    experiment_id?: string;
    details: any;
  }> {
    return [...this.trace];
  }

  private log(
    action: 'simulation_run' | 'experiment_started' | 'experiment_completed' | 'promotion_blocked_by_simulation' | 'rollout_recommended',
    experimentId: string | undefined,
    details: any
  ): void {
    this.trace.push({
      timestamp: new Date().toISOString(),
      action,
      experiment_id: experimentId,
      details,
    });
  }
}

// ============================================
// PART 4: INTEGRATED STRATEGIC MANAGEMENT ENGINE
// ============================================

/**
 * ★ Round 16: 战略管理引擎（整合三层子系统）
 */
export class StrategicManagementEngine {
  portfolio: StrategicPortfolioManager;
  memory: InstitutionalMemory;
  experiments: StrategicExperimentEngine;

  constructor() {
    this.portfolio = new StrategicPortfolioManager();
    this.memory = new InstitutionalMemory();
    this.experiments = new StrategicExperimentEngine();
  }

  /**
   * ★ Round 16: 添加 Mission 到 Portfolio（集成记忆检索）
   */
  addMissionToPortfolio(
    missionId: string,
    missionGoal: string,
    priority: TaskPriority
  ): { missionAdded: boolean; precedentUsed?: MemoryEntry } {
    // Retrieve relevant memory before adding
    const memories = this.memory.retrieve(missionGoal, 'mission_planning', 1);
    let precedentUsed: MemoryEntry | undefined;

    if (memories.length > 0 && memories[0].relevance_score > 0.3) {
      precedentUsed = memories[0].memory;
      this.memory.applyMemory(precedentUsed.id, `add_mission:${missionId}`);
    }

    // Calculate initial metrics (could use memory-based heuristics)
    const expectedValue = priority === 'urgent' ? 0.9 : priority === 'important' ? 0.7 : 0.5;
    const executionCost = 0.5;
    const strategicAlignment = 0.6;

    this.portfolio.addMission(missionId, missionGoal, priority, expectedValue, executionCost, strategicAlignment);

    return { missionAdded: true, precedentUsed };
  }

  /**
   * ★ Round 16: 做出 Portfolio 决策（集成制度记忆）
   */
  makePortfolioDecision(missionId: string, context: {
    resourcePressure?: number;
    driftScore?: number;
    lowROI?: boolean;
  }): PortfolioDecision & { memoryInfluenced?: boolean; precedentApplied?: string } {
    // Check institutional memory before making decision
    const memories = this.memory.retrieve(`mission ${missionId}`, context.lowROI ? 'kill_decision' : 'portfolio_management', 2);
    let memoryInfluenced = false;
    let precedentApplied: string | undefined;

    if (memories.length > 0 && memories[0].relevance_score > 0.4) {
      const topMem = memories[0].memory;
      this.memory.applyMemory(topMem.id, `portfolio_decision:${missionId}`);
      memoryInfluenced = true;
      precedentApplied = topMem.title;

      // Memory may influence ROI threshold
      if (topMem.type === 'failure_case' && topMem.content.includes('Low ROI')) {
        context.lowROI = true;
      }
    }

    const decision = this.portfolio.makeDecision(missionId, context);

    return { ...decision, memoryInfluenced, precedentApplied };
  }

  /**
   * ★ Round 16: 评估 Strategy Patch（先模拟再决定）
   */
  evaluatePatchWithSimulation(patch: StrategyPatch, currentMetrics: Record<string, number>): {
    simulation: SimulationResult;
    experiment?: Experiment;
    shouldPromote: boolean;
    reason: string;
  } {
    // Step 1: Dry-run simulation
    const simulation = this.experiments.dryRunPatch(patch, currentMetrics);

    // Step 2: Create actual experiment
    const experiment = this.experiments.createExperiment(
      `Test patch v${patch.version} effects`,
      `Apply ${patch.changes.length} changes from patch`,
      currentMetrics
    );

    // Step 3: Simulate metrics after
    const afterMetrics = simulation.expected_metrics;

    // Step 4: Complete experiment
    const completedExp = this.experiments.completeExperiment(experiment.id, afterMetrics);

    // Step 5: Decide promotion
    const blockCheck = this.experiments.shouldBlockPromotion(experiment.id);

    return {
      simulation,
      experiment: completedExp || experiment,
      shouldPromote: !blockCheck.blocked && completedExp?.rollout_recommendation !== 'rollback',
      reason: blockCheck.blocked
        ? blockCheck.reason || 'Blocked by risk envelope'
        : completedExp?.rollout_recommendation === 'full_rollout'
          ? 'Full rollout recommended'
          : 'Partial rollout or hold',
    };
  }

  /**
   * ★ Round 16: 从真实运行中沉淀制度记忆
   */
  distillMemoryFromRun(
    type: MemoryType,
    title: string,
    content: string,
    contextTags: string[],
    tags: string[],
    confidence: number
  ): MemoryEntry {
    const memory = this.memory.addMemory(type, title, content, contextTags, tags, confidence);

    return memory;
  }

  /**
   * ★ Round 16: 获取完整追踪
   */
  getFullTrace(): {
    portfolio_trace: PortfolioTraceEntry[];
    memory_trace: any[];
    experiment_trace: any[];
  } {
    return {
      portfolio_trace: this.portfolio.getTrace(),
      memory_trace: this.memory.getTrace(),
      experiment_trace: this.experiments.getTrace(),
    };
  }
}

// ============================================
// 单例
// ============================================
export const strategicManagementEngine = new StrategicManagementEngine();
