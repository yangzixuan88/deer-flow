/**
 * M17 外部结果真相 + 经营层控制 + 元治理
 * ================================================
 * Round 17: Executive & Constitutional Intelligence Layer
 * ================================================
 */

// ============================================
// PART 1: EXTERNAL OUTCOME TRUTH LAYER
// ============================================

/**
 * ★ Round 17: Outcome 类型
 */
export type OutcomeType = 'execution_observed' | 'user_feedback' | 'mission_result' | 'cost_report' | 'delay_report';

/**
 * ★ Round 17: Outcome 条目
 */
export interface OutcomeEntry {
  id: string;
  mission_id?: string;
  task_id?: string;
  outcome_type: OutcomeType;
  expected_outcome: string;
  actual_outcome: string;
  outcome_gap: number;        // 0-1, gap between expected and actual
  expectation_error: number;  // -1 to 1, negative = worse than expected
  confidence: number;         // 0-1, source reliability
  source: string;            // 'user', 'system', 'external_monitor', etc.
  observed_at: string;
  metadata?: Record<string, any>;
}

/**
 * ★ Round 17: Outcome 差距分析
 */
export interface OutcomeGapAnalysis {
  outcome_id: string;
  mission_id?: string;
  task_id?: string;
  gap_detected: boolean;
  gap_magnitude: number;     // 0-1
  is_positive_gap: boolean; // actual > expected
  severity: 'none' | 'minor' | 'major' | 'critical';
  recommended_action: 'none' | 'memory_update' | 'portfolio_adjust' | 'escalate';
}

/**
 * ★ Round 17: 外部结果真相层
 */
export class ExternalOutcomeTruth {
  private outcomes: Map<string, OutcomeEntry> = new Map();
  private trace: Array<{
    timestamp: string;
    action: 'outcome_truth_recorded' | 'outcome_gap_detected' | 'portfolio_adjusted_by_outcome' | 'memory_updated_by_outcome' | 'evaluation_adjusted_by_outcome';
    outcome_id?: string;
    details: any;
  }> = [];

  /**
   * ★ Round 17: 记录外部结果真相
   */
  recordOutcome(
    missionId: string | undefined,
    taskId: string | undefined,
    outcomeType: OutcomeType,
    expectedOutcome: string,
    actualOutcome: string,
    expectedValue: number,
    actualValue: number,
    confidence: number,
    source: string
  ): OutcomeEntry {
    const id = `outcome_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const gap = Math.abs(expectedValue - actualValue);
    const error = actualValue - expectedValue; // negative = worse

    const entry: OutcomeEntry = {
      id,
      mission_id: missionId,
      task_id: taskId,
      outcome_type: outcomeType,
      expected_outcome: expectedOutcome,
      actual_outcome: actualOutcome,
      outcome_gap: gap,
      expectation_error: error,
      confidence,
      source,
      observed_at: new Date().toISOString(),
    };

    this.outcomes.set(id, entry);
    this.logAction('outcome_truth_recorded', id, { mission_id: missionId, outcome_type: outcomeType, gap, error });

    return entry;
  }

  /**
   * ★ Round 17: 分析 outcome 差距
   */
  analyzeGap(outcomeId: string): OutcomeGapAnalysis | null {
    const outcome = this.outcomes.get(outcomeId);
    if (!outcome) return null;

    const gapDetected = outcome.outcome_gap > 0.1;
    const severity = outcome.outcome_gap < 0.1 ? 'none'
      : outcome.outcome_gap < 0.25 ? 'minor'
      : outcome.outcome_gap < 0.5 ? 'major'
      : 'critical';

    let recommendedAction: OutcomeGapAnalysis['recommended_action'] = 'none';
    if (outcome.outcome_gap > 0.3) {
      recommendedAction = outcome.mission_id ? 'portfolio_adjust' : 'memory_update';
    }
    if (outcome.outcome_gap > 0.5) {
      recommendedAction = 'escalate';
    }

    if (gapDetected) {
      this.logAction('outcome_gap_detected', outcomeId, {
        gap: outcome.outcome_gap,
        error: outcome.expectation_error,
        severity,
      });
    }

    return {
      outcome_id: outcomeId,
      mission_id: outcome.mission_id,
      task_id: outcome.task_id,
      gap_detected: gapDetected,
      gap_magnitude: outcome.outcome_gap,
      is_positive_gap: outcome.expectation_error > 0,
      severity,
      recommended_action: recommendedAction,
    };
  }

  /**
   * ★ Round 17: 获取某 mission 的所有 outcome
   */
  getMissionOutcomes(missionId: string): OutcomeEntry[] {
    return Array.from(this.outcomes.values()).filter(o => o.mission_id === missionId);
  }

  /**
   * ★ Round 17: 获取所有 outcome
   */
  getAllOutcomes(): OutcomeEntry[] {
    return Array.from(this.outcomes.values());
  }

  /**
   * ★ Round 17: 获取差距分析
   */
  getGapAnalyses(): OutcomeGapAnalysis[] {
    const analyses: OutcomeGapAnalysis[] = [];
    for (const id of this.outcomes.keys()) {
      const analysis = this.analyzeGap(id);
      if (analysis) analyses.push(analysis);
    }
    return analyses;
  }

  /**
   * ★ Round 17: 获取追踪日志
   */
  getTrace(): Array<{ timestamp: string; action: string; outcome_id?: string; details: any }> {
    return [...this.trace];
  }

  /**
   * ★ Round 17: 标记为影响 portfolio
   */
  markPortfolioAdjusted(outcomeId: string): void {
    this.logAction('portfolio_adjusted_by_outcome', outcomeId, {});
  }

  /**
   * ★ Round 17: 标记为影响 memory
   */
  markMemoryUpdated(outcomeId: string): void {
    this.logAction('memory_updated_by_outcome', outcomeId, {});
  }

  private logAction(action: 'outcome_truth_recorded' | 'outcome_gap_detected' | 'portfolio_adjusted_by_outcome' | 'memory_updated_by_outcome' | 'evaluation_adjusted_by_outcome', outcomeId: string | undefined, details: any): void {
    this.trace.push({ timestamp: new Date().toISOString(), action, outcome_id: outcomeId, details });
  }
}

// ============================================
// PART 2: EXECUTIVE OPERATING LAYER
// ============================================

/**
 * ★ Round 17: Executive 决策类型
 */
export type ExecutiveDecisionType =
  | 'continue_invest'
  | 'throttle'
  | 'cut_loss'
  | 'emergency_accelerate'
  | 'escalate_for_budget_review';

/**
 * ★ Round 17: Commitment 条目
 */
export interface Commitment {
  id: string;
  mission_id: string;
  promised_by_system: string;
  due_time: string;
  met: boolean;
  missed_reason?: string;
  created_at: string;
}

/**
 * ★ Round 17: Operating Score
 */
export interface OperatingScore {
  budget_burn: number;           // 0-1, how much budget consumed
  deadline_risk: number;          // 0-1, risk of missing deadline
  sla_health: number;            // 0-1, SLA compliance
  commitment_reliability: number; // 0-1, promises kept / total promises
  opportunity_cost: number;       // 0-1, cost of blocked alternatives
  overall_health: number;         // composite
  timestamp: string;
}

/**
 * ★ Round 17: Executive Control 条目
 */
export interface ExecutiveControlEntry {
  mission_id: string;
  budget_allocated: number;
  budget_used: number;
  deadline: string | undefined;
  time_remaining_percent: number;
  commitments: Commitment[];
  operating_score: OperatingScore;
  last_decision?: ExecutiveDecisionType;
  last_decision_reason?: string;
}

/**
 * ★ Round 17: 经营层控制
 */
export class ExecutiveOperatingLayer {
  private controls: Map<string, ExecutiveControlEntry> = new Map();
  private commitments: Map<string, Commitment> = new Map();
  private trace: Array<{
    timestamp: string;
    action: 'executive_control_decision' | 'budget_gate_hit' | 'deadline_reprioritization' | 'commitment_missed' | 'opportunity_cost_calculated' | 'throttle_applied' | 'cut_loss_triggered';
    mission_id?: string;
    details: any;
  }> = [];

  /**
   * ★ Round 17: 初始化 mission 控制
   */
  initializeMission(
    missionId: string,
    budget: number,
    deadline?: string
  ): void {
    const entry: ExecutiveControlEntry = {
      mission_id: missionId,
      budget_allocated: budget,
      budget_used: 0,
      deadline,
      time_remaining_percent: 100,
      commitments: [],
      operating_score: {
        budget_burn: 0,
        deadline_risk: 0,
        sla_health: 1,
        commitment_reliability: 1,
        opportunity_cost: 0,
        overall_health: 1,
        timestamp: new Date().toISOString(),
      },
    };
    this.controls.set(missionId, entry);
  }

  /**
   * ★ Round 17: 记录预算消耗
   */
  recordBudgetUse(missionId: string, amount: number): void {
    const control = this.controls.get(missionId);
    if (!control) return;

    control.budget_used += amount;
    const burn = control.budget_used / control.budget_allocated;
    control.operating_score.budget_burn = Math.min(1, burn);

    if (burn >= 0.9) {
      this.logAction('budget_gate_hit', missionId, { burn, budget_used: control.budget_used, allocated: control.budget_allocated });
    }
  }

  /**
   * ★ Round 17: 更新时间剩余
   */
  updateTimeRemaining(missionId: string, percentRemaining: number): void {
    const control = this.controls.get(missionId);
    if (!control) return;

    control.time_remaining_percent = percentRemaining;
    control.operating_score.deadline_risk = 1 - percentRemaining;

    if (percentRemaining < 0.2) {
      this.logAction('deadline_reprioritization', missionId, { percent_remaining: percentRemaining });
    }
  }

  /**
   * ★ Round 17: 添加 commitment
   */
  addCommitment(missionId: string, promisedBySystem: string, dueTime: string): Commitment {
    const id = `commit_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const commitment: Commitment = {
      id,
      mission_id: missionId,
      promised_by_system: promisedBySystem,
      due_time: dueTime,
      met: false,
      created_at: new Date().toISOString(),
    };

    this.commitments.set(id, commitment);

    const control = this.controls.get(missionId);
    if (control) {
      control.commitments.push(commitment);
    }

    return commitment;
  }

  /**
   * ★ Round 17: 完成 commitment
   */
  fulfillCommitment(commitmentId: string): boolean {
    const commitment = this.commitments.get(commitmentId);
    if (!commitment) return false;

    commitment.met = true;
    this.updateCommitmentReliability(commitment.mission_id);
    return true;
  }

  /**
   * ★ Round 17: 错过 commitment
   */
  missCommitment(commitmentId: string, reason: string): boolean {
    const commitment = this.commitments.get(commitmentId);
    if (!commitment) return false;

    commitment.met = false;
    commitment.missed_reason = reason;
    this.logAction('commitment_missed', commitment.mission_id, { commitment_id: commitmentId, reason });
    this.updateCommitmentReliability(commitment.mission_id);
    return true;
  }

  /**
   * ★ Round 17: 更新 commitment 可靠性
   */
  private updateCommitmentReliability(missionId: string): void {
    const control = this.controls.get(missionId);
    if (!control) return;

    const missionCommitments = control.commitments;
    if (missionCommitments.length === 0) {
      control.operating_score.commitment_reliability = 1;
      return;
    }

    const met = missionCommitments.filter(c => c.met).length;
    control.operating_score.commitment_reliability = met / missionCommitments.length;
  }

  /**
   * ★ Round 17: 计算机会成本
   */
  calculateOpportunityCost(missionId: string, alternativeMissionIds: string[]): number {
    const control = this.controls.get(missionId);
    if (!control) return 0;

    // Opportunity cost based on budget pressure and deadline pressure
    const budgetPressure = control.operating_score.budget_burn;
    const deadlinePressure = control.operating_score.deadline_risk;

    // When this mission is resource-constrained, alternatives suffer
    const opportunityCost = (budgetPressure + deadlinePressure) / 2;

    control.operating_score.opportunity_cost = opportunityCost;

    this.logAction('opportunity_cost_calculated', missionId, {
      alternative_missions: alternativeMissionIds,
      cost: opportunityCost,
    });

    return opportunityCost;
  }

  /**
   * ★ Round 17: 计算综合 operating score
   */
  computeOperatingScore(missionId: string): OperatingScore | null {
    const control = this.controls.get(missionId);
    if (!control) return null;

    const { budget_burn, deadline_risk, sla_health, commitment_reliability, opportunity_cost } = control.operating_score;

    // Weighted composite
    control.operating_score.overall_health = (
      (1 - budget_burn) * 0.25 +
      (1 - deadline_risk) * 0.2 +
      sla_health * 0.2 +
      commitment_reliability * 0.2 +
      (1 - opportunity_cost) * 0.15
    );

    return { ...control.operating_score };
  }

  /**
   * ★ Round 17: 做出 executive 决策
   */
  makeExecutiveDecision(missionId: string): ExecutiveDecisionType {
    const control = this.controls.get(missionId);
    if (!control) return 'escalate_for_budget_review';

    const score = this.computeOperatingScore(missionId);
    if (!score) return 'escalate_for_budget_review';

    let decision: ExecutiveDecisionType;
    let reason: string;

    // Decision logic
    if (score.budget_burn >= 0.95) {
      decision = 'cut_loss';
      reason = `Budget exhausted: ${(score.budget_burn * 100).toFixed(0)}%`;
      this.logAction('cut_loss_triggered', missionId, { burn: score.budget_burn, reason });
    } else if (score.budget_burn >= 0.8) {
      decision = 'throttle';
      reason = `Budget pressure: ${(score.budget_burn * 100).toFixed(0)}%`;
      this.logAction('throttle_applied', missionId, { burn: score.budget_burn, reason });
    } else if (score.deadline_risk >= 0.8) {
      decision = 'emergency_accelerate';
      reason = `Deadline risk: ${(score.deadline_risk * 100).toFixed(0)}%`;
    } else if (score.commitment_reliability < 0.5) {
      decision = 'escalate_for_budget_review';
      reason = `Commitment reliability low: ${(score.commitment_reliability * 100).toFixed(0)}%`;
    } else {
      decision = 'continue_invest';
      reason = 'Operating within bounds';
    }

    control.last_decision = decision;
    control.last_decision_reason = reason;
    this.logAction('executive_control_decision', missionId, { decision, reason });

    return decision;
  }

  /**
   * ★ Round 17: 获取控制状态
   */
  getControl(missionId: string): ExecutiveControlEntry | undefined {
    return this.controls.get(missionId);
  }

  /**
   * ★ Round 17: 获取追踪日志
   */
  getTrace(): Array<{ timestamp: string; action: string; mission_id?: string; details: any }> {
    return [...this.trace];
  }

  private logAction(action: 'executive_control_decision' | 'budget_gate_hit' | 'deadline_reprioritization' | 'commitment_missed' | 'opportunity_cost_calculated' | 'throttle_applied' | 'cut_loss_triggered', missionId: string | undefined, details: any): void {
    this.trace.push({ timestamp: new Date().toISOString(), action, mission_id: missionId, details });
  }
}

// ============================================
// PART 3: META-GOVERNANCE / CONSTITUTIONAL LAYER
// ============================================

/**
 * ★ Round 17: 规则类型
 */
export type RuleType = 'immutable' | 'changeable' | 'approval_required' | 'forbidden_modification';

/**
 * ★ Round 17: Constitution 条目
 */
export interface ConstitutionRule {
  id: string;
  name: string;
  description: string;
  rule_type: RuleType;
  content: string;
  version: number;
  created_at: string;
  updated_at: string;
  superseded_by?: string;
}

/**
 * ★ Round 17: Rule Patch Proposal
 */
export interface RulePatchProposal {
  id: string;
  rule_id: string;
  patch_type: 'modify' | 'supersede' | 'create' | 'delete';
  proposed_content: string;
  justification: string;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  status: 'proposed' | 'meta_approved' | 'meta_rejected' | 'shadow' | 'applied' | 'rolled_back';
  meta_approval_required: boolean;
  shadow_applied: boolean;
  created_at: string;
  decided_at?: string;
  applied_at?: string;
  rollback_at?: string;
  rollback_reason?: string;
}

/**
 * ★ Round 17: Meta-Governance / Constitutional Layer
 */
export class MetaGovernanceLayer {
  private constitution: Map<string, ConstitutionRule> = new Map();
  private patchProposals: Map<string, RulePatchProposal> = new Map();
  private patchHistory: Map<string, ConstitutionRule[]> = new Map(); // rule_id -> previous versions
  private trace: Array<{
    timestamp: string;
    action: 'rule_created' | 'rule_patch_proposed' | 'constitutional_gate_hit' | 'shadow_rule_applied' | 'rule_patch_applied' | 'meta_rollback_executed' | 'meta_rollback_reason';
    rule_id?: string;
    patch_id?: string;
    details: any;
  }> = [];

  constructor() {
    this.initializeDefaultConstitution();
  }

  /**
   * ★ Round 17: 初始化默认宪法
   */
  private initializeDefaultConstitution(): void {
    const defaultRules: Omit<ConstitutionRule, 'id' | 'created_at' | 'updated_at'>[] = [
      {
        name: 'User Veto Is Absolute',
        description: 'User veto on any decision is final and cannot be overridden by any agent or meta-layer',
        rule_type: 'immutable',
        content: 'user_veto_final: true',
        version: 1,
      },
      {
        name: 'High-Risk Approval Requirement',
        description: 'Tasks with HIGH_RISK_PATTERNS require explicit user approval before execution',
        rule_type: 'changeable',
        content: 'high_risk_approval_required: true',
        version: 1,
      },
      {
        name: 'Promotion Threshold',
        description: 'Strategy patches require capability_score >= 0.7 for promotion',
        rule_type: 'changeable',
        content: 'promotion_threshold: 0.7',
        version: 1,
      },
      {
        name: 'Regression Detection Threshold',
        description: 'Version comparisons with score_delta < -0.05 trigger regression alert',
        rule_type: 'changeable',
        content: 'regression_threshold: -0.05',
        version: 1,
      },
      {
        name: 'Shadow Mode Requirement',
        description: 'Experimental experiences must run in shadow mode before promotion',
        rule_type: 'changeable',
        content: 'shadow_mode_required: true',
        version: 1,
      },
      {
        name: 'Meta-Governance Self-Amendment',
        description: 'Constitutional rules themselves cannot be modified without meta-approval',
        rule_type: 'forbidden_modification',
        content: 'constitution_immutable: true',
        version: 1,
      },
    ];

    for (const rule of defaultRules) {
      this.createRule(rule.name, rule.description, rule.rule_type, rule.content);
    }
  }

  /**
   * ★ Round 17: 创建规则
   */
  private createRule(name: string, description: string, ruleType: RuleType, content: string): ConstitutionRule {
    const id = `rule_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const now = new Date().toISOString();
    const rule: ConstitutionRule = {
      id,
      name,
      description,
      rule_type: ruleType,
      content,
      version: 1,
      created_at: now,
      updated_at: now,
    };
    this.constitution.set(id, rule);
    this.trace.push({ timestamp: now, action: 'rule_created', rule_id: id, details: { name, rule_type: ruleType } });
    return rule;
  }

  /**
   * ★ Round 17: 获取规则
   */
  getRule(ruleId: string): ConstitutionRule | undefined {
    return this.constitution.get(ruleId);
  }

  /**
   * ★ Round 17: 获取所有规则
   */
  getAllRules(): ConstitutionRule[] {
    return Array.from(this.constitution.values());
  }

  /**
   * ★ Round 17: 提出 Rule Patch
   */
  proposeRulePatch(
    ruleId: string,
    patchType: 'modify' | 'supersede' | 'delete',
    proposedContent: string,
    justification: string
  ): RulePatchProposal | null {
    const rule = this.constitution.get(ruleId);
    if (!rule) return null;

    // Check forbidden modification
    if (rule.rule_type === 'forbidden_modification') {
      this.logAction('constitutional_gate_hit', ruleId, { reason: 'forbidden_modification', patch_type: patchType });
      return null;
    }

    // Immutable rules require special process
    const metaApprovalRequired = rule.rule_type === 'immutable' || rule.rule_type === 'approval_required';

    // High risk if changing governance-critical rules
    const riskLevel: RulePatchProposal['risk_level'] =
      proposedContent.includes('veto') || proposedContent.includes('immutable') ? 'critical'
      : proposedContent.includes('threshold') || proposedContent.includes('approval') ? 'high'
      : proposedContent.includes('governance') ? 'medium'
      : 'low';

    const id = `patch_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const proposal: RulePatchProposal = {
      id,
      rule_id: ruleId,
      patch_type: patchType,
      proposed_content: proposedContent,
      justification,
      risk_level: riskLevel,
      status: 'proposed',
      meta_approval_required: metaApprovalRequired,
      shadow_applied: false,
      created_at: new Date().toISOString(),
    };

    this.patchProposals.set(id, proposal);
    this.logAction('rule_patch_proposed', ruleId, { patch_id: id, risk_level: riskLevel, meta_approval_required: metaApprovalRequired });

    // If high/critical risk, log constitutional gate hit
    if (metaApprovalRequired || riskLevel === 'critical') {
      this.logAction('constitutional_gate_hit', ruleId, { patch_id: id, risk_level: riskLevel });
    }

    return proposal;
  }

  /**
   * ★ Round 17: Meta 审批 Patch
   */
  metaApprove(patchId: string): boolean {
    const patch = this.patchProposals.get(patchId);
    if (!patch) return false;

    // Critical/high risk patches require meta approval
    if (patch.risk_level === 'critical' || patch.risk_level === 'high' || patch.meta_approval_required) {
      patch.status = 'meta_approved';
      patch.decided_at = new Date().toISOString();
      this.logAction('constitutional_gate_hit', patch.rule_id, { patch_id: patchId, action: 'meta_approved' });
      return true;
    }

    return false;
  }

  /**
   * ★ Round 17: Meta 拒绝 Patch
   */
  metaReject(patchId: string, reason: string): boolean {
    const patch = this.patchProposals.get(patchId);
    if (!patch) return false;

    patch.status = 'meta_rejected';
    patch.decided_at = new Date().toISOString();
    this.logAction('constitutional_gate_hit', patch.rule_id, { patch_id: patchId, action: 'meta_rejected', reason });
    return true;
  }

  /**
   * ★ Round 17: Shadow 应用 Patch
   */
  shadowApplyPatch(patchId: string): boolean {
    const patch = this.patchProposals.get(patchId);
    if (!patch || patch.status !== 'meta_approved') return false;

    patch.shadow_applied = true;
    patch.status = 'shadow';
    this.logAction('shadow_rule_applied', patch.rule_id, { patch_id: patchId });
    return true;
  }

  /**
   * ★ Round 17: 正式应用 Patch
   */
  applyPatch(patchId: string): boolean {
    const patch = this.patchProposals.get(patchId);
    if (!patch) return false;

    // Must be meta approved, shadow, or low risk (low risk can be applied directly)
    if (patch.status !== 'meta_approved' && patch.status !== 'shadow' && patch.risk_level !== 'low') return false;

    const rule = this.constitution.get(patch.rule_id);
    if (!rule) return false;

    // Save current version to history
    if (!this.patchHistory.has(patch.rule_id)) {
      this.patchHistory.set(patch.rule_id, []);
    }
    this.patchHistory.get(patch.rule_id)!.push({ ...rule });

    // Apply the patch
    rule.content = patch.proposed_content;
    rule.version++;
    rule.updated_at = new Date().toISOString();

    patch.status = 'applied';
    patch.applied_at = new Date().toISOString();

    this.logAction('rule_patch_applied', patch.rule_id, { patch_id: patchId, new_version: rule.version });
    return true;
  }

  /**
   * ★ Round 17: 回滚 Patch（元治理回滚）
   */
  rollbackPatch(patchId: string, reason: string): boolean {
    const patch = this.patchProposals.get(patchId);
    if (!patch) return false;

    const history = this.patchHistory.get(patch.rule_id);
    if (!history || history.length === 0) return false;

    // Restore previous version
    const previousRule = history[history.length - 1];
    const rule = this.constitution.get(patch.rule_id);
    if (!rule) return false;

    rule.content = previousRule.content;
    rule.version = previousRule.version;
    rule.updated_at = new Date().toISOString();

    patch.status = 'rolled_back';
    patch.rollback_at = new Date().toISOString();
    patch.rollback_reason = reason;

    this.logAction('meta_rollback_executed', patch.rule_id, { patch_id: patchId, reason, restored_version: rule.version });
    this.logAction('meta_rollback_reason', patch.rule_id, { patch_id: patchId, reason });

    return true;
  }

  /**
   * ★ Round 17: 检查 Patch 是否安全
   */
  isPatchSafe(patchId: string): { safe: boolean; reason?: string } {
    const patch = this.patchProposals.get(patchId);
    if (!patch) return { safe: false, reason: 'Patch not found' };

    // Critical patches are never fully safe
    if (patch.risk_level === 'critical') {
      return { safe: false, reason: 'Critical risk patch requires extended shadow period' };
    }

    // Must be meta approved first
    if (patch.meta_approval_required && patch.status !== 'meta_approved' && patch.status !== 'applied') {
      return { safe: false, reason: 'Meta approval required before application' };
    }

    // Immutable rules cannot be patched
    const rule = this.constitution.get(patch.rule_id);
    if (rule?.rule_type === 'forbidden_modification') {
      return { safe: false, reason: 'Constitutional rules cannot be modified' };
    }

    if (rule?.rule_type === 'immutable') {
      return { safe: false, reason: 'Immutable rules cannot be changed' };
    }

    return { safe: true };
  }

  /**
   * ★ Round 17: 获取所有 Patch Proposal
   */
  getPatchProposals(): RulePatchProposal[] {
    return Array.from(this.patchProposals.values());
  }

  /**
   * ★ Round 17: Governance gate for capability/tool admission checks.
   * Used by governance_bridge via subprocess entry.
   */
  checkGovernanceGate(context: {
    decisionType: string;
    description: string;
    riskLevel: string;
    stakeHolders: string[];
  }): { allowed: boolean; reason: string; requires_constitutional_patch: boolean } {
    const { decisionType, description, riskLevel, stakeHolders } = context;

    // Log the governance check
    this.logAction('constitutional_gate_hit', undefined, {
      decision_type: decisionType,
      description: description.slice(0, 100),
      risk_level: riskLevel,
      stake_holders: stakeHolders,
    });

    // FAIL_CLOSED: CRITICAL always requires constitutional patch review
    if (riskLevel === 'critical') {
      return {
        allowed: false,
        reason: `CRITICAL risk decision '${decisionType}' requires constitutional patch — FAIL_CLOSED`,
        requires_constitutional_patch: true,
      };
    }

    // HIGH risk: requires stakeholder signals before allowing
    if (riskLevel === 'high') {
      // If no stakeholders registered, default to requiring patch
      if (!stakeHolders || stakeHolders.length === 0) {
        return {
          allowed: false,
          reason: `HIGH risk '${decisionType}' with no stakeholder signals — FAIL_CLOSED, requires patch`,
          requires_constitutional_patch: true,
        };
      }
      // Stakeholders present: allow with note that governance reviewed it
      return {
        allowed: true,
        reason: `HIGH risk '${decisionType}' approved with stakeholder review (${stakeHolders.join(', ')})`,
        requires_constitutional_patch: false,
      };
    }

    // Medium and low risk: allowed (governance aware, not blocking)
    return {
      allowed: true,
      reason: `${riskLevel.toUpperCase()} risk decision '${decisionType}' — no governance block`,
      requires_constitutional_patch: false,
    };
  }

  /**
   * ★ Round 17: 获取追踪日志
   */
  getTrace(): Array<{ timestamp: string; action: string; rule_id?: string; patch_id?: string; details: any }> {
    return [...this.trace];
  }

  private logAction(action: 'rule_created' | 'rule_patch_proposed' | 'constitutional_gate_hit' | 'shadow_rule_applied' | 'rule_patch_applied' | 'meta_rollback_executed' | 'meta_rollback_reason', ruleId: string | undefined, details: any): void {
    this.trace.push({ timestamp: new Date().toISOString(), action, rule_id: ruleId, patch_id: undefined, details });
  }
}

// ============================================
// PART 4: INTEGRATED META GOVERNANCE ENGINE
// ============================================

/**
 * ★ Round 17: 元治理引擎（整合三层子系统）
 */
export class MetaGovernanceEngine {
  outcomeTruth: ExternalOutcomeTruth;
  executive: ExecutiveOperatingLayer;
  metaGovernance: MetaGovernanceLayer;

  constructor() {
    this.outcomeTruth = new ExternalOutcomeTruth();
    this.executive = new ExecutiveOperatingLayer();
    this.metaGovernance = new MetaGovernanceLayer();
  }

  /**
   * ★ Round 17: 处理外部结果并驱动决策
   */
  processExternalOutcome(
    missionId: string,
    taskId: string | undefined,
    outcomeType: OutcomeType,
    expectedOutcome: string,
    actualOutcome: string,
    expectedValue: number,
    actualValue: number,
    source: string
  ): { outcome: OutcomeEntry; gapAnalysis: OutcomeGapAnalysis | null; portfolioAdjusted: boolean } {
    // Record the outcome
    const outcome = this.outcomeTruth.recordOutcome(
      missionId, taskId, outcomeType,
      expectedOutcome, actualOutcome,
      expectedValue, actualValue,
      0.8, source
    );

    // Analyze gap
    const gapAnalysis = this.outcomeTruth.analyzeGap(outcome.id);

    let portfolioAdjusted = false;

    // If significant gap, trigger portfolio adjustment
    if (gapAnalysis && gapAnalysis.gap_detected && gapAnalysis.gap_magnitude > 0.2) {
      this.outcomeTruth.markPortfolioAdjusted(outcome.id);
      portfolioAdjusted = true;
    }

    // If gap is critical, trigger memory update
    if (gapAnalysis && gapAnalysis.severity === 'critical') {
      this.outcomeTruth.markMemoryUpdated(outcome.id);
    }

    return { outcome, gapAnalysis, portfolioAdjusted };
  }

  /**
   * ★ Round 17: 执行 mission 的 executive control
   */
  controlMission(
    missionId: string,
    budget: number,
    deadline: string | undefined,
    promisedDeliverable: string | undefined
  ): { control: ExecutiveControlEntry; decision: ExecutiveDecisionType } {
    // Initialize if needed
    if (!this.executive.getControl(missionId)) {
      this.executive.initializeMission(missionId, budget, deadline);
    }

    // Add commitment if provided
    if (promisedDeliverable && deadline) {
      this.executive.addCommitment(missionId, promisedDeliverable, deadline);
    }

    // Make executive decision
    const decision = this.executive.makeExecutiveDecision(missionId);
    const control = this.executive.getControl(missionId)!;

    return { control, decision };
  }

  /**
   * ★ Round 17: 提出规则变更并处理
   */
  proposeAndProcessRuleChange(
    ruleId: string,
    proposedContent: string,
    justification: string
  ): { proposal: RulePatchProposal | null; safe: boolean; applied: boolean } {
    // Propose the patch
    const proposal = this.metaGovernance.proposeRulePatch(ruleId, 'modify', proposedContent, justification);
    if (!proposal) {
      return { proposal: null, safe: false, applied: false };
    }

    // Check if safe
    const safety = this.metaGovernance.isPatchSafe(proposal.id);

    // If high/critical risk, need meta approval first
    if (proposal.risk_level === 'critical' || proposal.risk_level === 'high') {
      return { proposal, safe: false, applied: false };
    }

    // Medium risk can shadow apply
    if (proposal.risk_level === 'medium') {
      this.metaGovernance.metaApprove(proposal.id);
      this.metaGovernance.shadowApplyPatch(proposal.id);
      return { proposal, safe: true, applied: false };
    }

    // Low risk can apply directly
    this.metaGovernance.applyPatch(proposal.id);
    return { proposal, safe: true, applied: true };
  }

  /**
   * ★ Round 17: 回滚规则
   */
  rollbackRuleChange(patchId: string, reason: string): boolean {
    return this.metaGovernance.rollbackPatch(patchId, reason);
  }

  /**
   * ★ Round 17: 获取完整追踪
   */
  getFullTrace(): {
    outcome_trace: ReturnType<ExternalOutcomeTruth['getTrace']>;
    executive_trace: ReturnType<ExecutiveOperatingLayer['getTrace']>;
    meta_trace: ReturnType<MetaGovernanceLayer['getTrace']>;
  } {
    return {
      outcome_trace: this.outcomeTruth.getTrace(),
      executive_trace: this.executive.getTrace(),
      meta_trace: this.metaGovernance.getTrace(),
    };
  }
}

// ============================================
// 单例
// ============================================
export const metaGovernanceEngine = new MetaGovernanceEngine();
