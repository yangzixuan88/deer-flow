/**
 * M18 认知真相治理 + 多方谈判 + 战略前瞻
 * ================================================
 * Round 18: Cognitive & Strategic Intelligence Layer
 * ================================================
 */

// ============================================
// PART 1: EPISTEMIC GOVERNANCE LAYER
// ============================================

/**
 * ★ Round 18: Truth Source 类型
 */
export type SourceType = 'user' | 'system_monitor' | 'external_monitor' | 'model_inference' | 'experiment_result' | 'historical_precedent';

/**
 * ★ Round 18: Truth Source Registry Entry
 */
export interface TruthSource {
  source_id: string;
  source_type: SourceType;
  trust_level: number;         // 0-1, calibrated trust
  calibration_score: number;   // 0-1, how well-calibrated this source is
  conflict_history: number;    // how many times this source conflicted with others
  correct_count: number;        // times this source was proven correct
  total_count: number;         // total reports from this source
  recency: string;             // ISO timestamp of last report
  reliability_trend: 'improving' | 'stable' | 'degrading';
}

/**
 * ★ Round 18: Truth Entry
 */
export interface TruthEntry {
  id: string;
  fact: string;
  truth_confidence: number;    // 0-1
  uncertainty_reason?: string;
  evidence_needed?: string;
  conflict_resolved: boolean;
  resolved_by_source?: string;
  resolution_method?: 'prefer_high_trust' | 'mark_uncertain' | 'require_more_evidence' | 'escalate_for_human_review';
  sources: Array<{ source_id: string; value: number; confidence: number }>;
  memory_corrected?: boolean;
  trace: Array<{ timestamp: string; action: string; details: any }>;
}

/**
 * ★ Round 18: 认知真相治理层
 */
export class EpistemicGovernanceLayer {
  private sources: Map<string, TruthSource> = new Map();
  private truths: Map<string, TruthEntry> = new Map();
  private truthTrace: Array<{ timestamp: string; action: string; truth_id?: string; details: any }> = [];

  constructor() {
    this.initializeDefaultSources();
  }

  private initializeDefaultSources(): void {
    const defaultSources: Array<Omit<TruthSource, 'recency' | 'reliability_trend'>> = [
      { source_id: 'user', source_type: 'user', trust_level: 0.95, calibration_score: 0.9, conflict_history: 0, correct_count: 0, total_count: 0 },
      { source_id: 'system_monitor', source_type: 'system_monitor', trust_level: 0.85, calibration_score: 0.88, conflict_history: 0, correct_count: 0, total_count: 0 },
      { source_id: 'external_monitor', source_type: 'external_monitor', trust_level: 0.75, calibration_score: 0.7, conflict_history: 0, correct_count: 0, total_count: 0 },
      { source_id: 'model_inference', source_type: 'model_inference', trust_level: 0.7, calibration_score: 0.65, conflict_history: 0, correct_count: 0, total_count: 0 },
      { source_id: 'experiment_result', source_type: 'experiment_result', trust_level: 0.8, calibration_score: 0.85, conflict_history: 0, correct_count: 0, total_count: 0 },
      { source_id: 'historical_precedent', source_type: 'historical_precedent', trust_level: 0.6, calibration_score: 0.55, conflict_history: 0, correct_count: 0, total_count: 0 },
    ];

    for (const src of defaultSources) {
      this.sources.set(src.source_id, { ...src, recency: new Date().toISOString(), reliability_trend: 'stable' });
    }
  }

  /**
   * ★ Round 18: 注册新 truth
   */
  registerTruth(fact: string, sourceId: string, value: number, sourceConfidence: number): TruthEntry {
    const id = `truth_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const entry: TruthEntry = {
      id,
      fact,
      truth_confidence: sourceConfidence,
      conflict_resolved: false,
      sources: [{ source_id: sourceId, value, confidence: sourceConfidence }],
      trace: [],
    };

    entry.trace.push({ timestamp: new Date().toISOString(), action: 'truth_registered', details: { source_id: sourceId, value } });
    this.truths.set(id, entry);
    this.log('truth_registered', id, { fact, source_id: sourceId, initial_confidence: sourceConfidence });

    // Update source recency
    const source = this.sources.get(sourceId);
    if (source) {
      source.recency = new Date().toISOString();
      source.total_count++;
    }

    return entry;
  }

  /**
   * ★ Round 18: 添加冲突的 source 到已存在的 truth
   */
  addConflictingSource(truthId: string, sourceId: string, value: number, sourceConfidence: number): TruthEntry | null {
    const entry = this.truths.get(truthId);
    if (!entry) return null;

    entry.sources.push({ source_id: sourceId, value, confidence: sourceConfidence });

    const source = this.sources.get(sourceId);
    if (source) {
      source.conflict_history++;
      source.recency = new Date().toISOString();
      source.total_count++;
    }

    this.log('truth_conflict_detected', truthId, { source_id: sourceId, value, conflict_count: entry.sources.length });

    // Resolve conflict automatically
    return this.resolveConflict(truthId);
  }

  /**
   * ★ Round 18: 冲突解决
   */
  resolveConflict(truthId: string, method?: 'prefer_high_trust' | 'mark_uncertain' | 'require_more_evidence' | 'escalate_for_human_review'): TruthEntry | null {
    const entry = this.truths.get(truthId);
    if (!entry) return null;

    if (entry.sources.length < 2) {
      entry.conflict_resolved = true;
      return entry;
    }

    // Determine resolution method
    const resolutionMethod = method || this.determineResolutionMethod(entry);

    entry.resolution_method = resolutionMethod;
    entry.trace.push({ timestamp: new Date().toISOString(), action: 'conflict_resolved', details: { method: resolutionMethod } });
    this.log('confidence_adjusted', truthId, { method: resolutionMethod });

    switch (resolutionMethod) {
      case 'prefer_high_trust': {
        // Find highest trust source
        let bestSource: { source_id: string; value: number; confidence: number } = entry.sources[0];
        let highestTrust = 0;
        for (const src of entry.sources) {
          const source = this.sources.get(src.source_id);
          if (source && source.trust_level > highestTrust) {
            highestTrust = source.trust_level;
            bestSource = src;
          }
        }
        // Adjust confidence based on trust of winner
        const winnerSource = this.sources.get(bestSource.source_id);
        entry.truth_confidence = bestSource.confidence * (winnerSource ? winnerSource.trust_level : 0.8);
        entry.resolved_by_source = bestSource.source_id;
        break;
      }
      case 'mark_uncertain':
        entry.truth_confidence = entry.truth_confidence * 0.5;
        entry.uncertainty_reason = 'Conflicting sources detected, confidence reduced';
        break;
      case 'require_more_evidence':
        entry.truth_confidence = entry.truth_confidence * 0.3;
        entry.evidence_needed = 'Additional evidence from independent source required';
        entry.uncertainty_reason = 'Insufficient evidence to resolve conflict';
        break;
      case 'escalate_for_human_review':
        entry.truth_confidence = 0;
        entry.uncertainty_reason = 'Escalated to human for resolution';
        break;
    }

    entry.conflict_resolved = true;
    entry.trace.push({ timestamp: new Date().toISOString(), action: 'conflict_resolved_final', details: { final_confidence: entry.truth_confidence } });

    return entry;
  }

  private determineResolutionMethod(entry: TruthEntry): 'prefer_high_trust' | 'mark_uncertain' | 'require_more_evidence' | 'escalate_for_human_review' {
    // Check if any source has very low calibration
    for (const src of entry.sources) {
      const source = this.sources.get(src.source_id);
      if (source && source.calibration_score < 0.5) {
        return 'require_more_evidence';
      }
    }

    // Check trust spread
    const trusts = entry.sources.map(s => this.sources.get(s.source_id)?.trust_level || 0.5);
    const maxTrust = Math.max(...trusts);
    const minTrust = Math.min(...trusts);
    if (maxTrust - minTrust > 0.4) {
      return 'prefer_high_trust';
    }

    return 'mark_uncertain';
  }

  /**
   * ★ Round 18: 校正旧 memory
   */
  correctMemory(truthId: string, memoryId: string, correctionStrength: number): boolean {
    const entry = this.truths.get(truthId);
    if (!entry || !entry.conflict_resolved) return false;

    entry.memory_corrected = true;
    entry.trace.push({ timestamp: new Date().toISOString(), action: 'memory_corrected_by_truth', details: { memory_id: memoryId, correction_strength: correctionStrength } });

    this.log('memory_corrected_by_truth', truthId, { memory_id: memoryId, correction_strength: correctionStrength });

    // Learn from this correction - update source calibration
    if (entry.resolved_by_source) {
      const source = this.sources.get(entry.resolved_by_source);
      if (source) {
        source.calibration_score = (source.calibration_score * source.total_count + entry.truth_confidence) / (source.total_count + 1);
        if (entry.truth_confidence > 0.7) {
          source.correct_count++;
        }
        // Update reliability trend
        if (source.correct_count / source.total_count > 0.8) {
          source.reliability_trend = 'improving';
        } else if (source.correct_count / source.total_count < 0.5) {
          source.reliability_trend = 'degrading';
        }
      }
    }

    return true;
  }

  /**
   * ★ Round 18: 更新 source 可靠性
   */
  updateSourceReliability(sourceId: string, wasCorrect: boolean): void {
    const source = this.sources.get(sourceId);
    if (!source) return;

    source.total_count++;
    if (wasCorrect) source.correct_count++;

    // Update trust level based on performance
    const accuracy = source.correct_count / source.total_count;
    source.trust_level = 0.5 + (accuracy * 0.4); // Scale between 0.5-0.9

    // Update reliability trend
    if (accuracy > 0.8) {
      source.reliability_trend = 'improving';
    } else if (accuracy < 0.5) {
      source.reliability_trend = 'degrading';
    } else {
      source.reliability_trend = 'stable';
    }

    this.log('source_reliability_updated', undefined, { source_id: sourceId, trust_level: source.trust_level, accuracy });
  }

  /**
   * ★ Round 18: 获取 truth
   */
  getTruth(truthId: string): TruthEntry | undefined {
    return this.truths.get(truthId);
  }

  /**
   * ★ Round 18: 获取所有 source
   */
  getAllSources(): TruthSource[] {
    return Array.from(this.sources.values());
  }

  /**
   * ★ Round 18: 获取 trace
   */
  getTrace(): Array<{ timestamp: string; action: string; truth_id?: string; details: any }> {
    return [...this.truthTrace];
  }

  private log(action: string, truthId: string | undefined, details: any): void {
    this.truthTrace.push({ timestamp: new Date().toISOString(), action, truth_id: truthId, details });
  }
}

// ============================================
// PART 2: STAKEHOLDER NEGOTIATION LAYER
// ============================================

/**
 * ★ Round 18: Stakeholder 类型
 */
export type StakeholderType = 'user' | 'mission_owner' | 'executive_control' | 'governance' | 'long_term_system' | 'external_party';

/**
 * ★ Round 18: Stakeholder Entry
 */
export interface Stakeholder {
  id: string;
  type: StakeholderType;
  name: string;
  goals: string[];
  constraints: string[];
  risk_tolerance: number;        // 0-1
  veto_power: boolean;
  priority_weight: number;       // 0-1
  satisfaction_level: number;    // 0-1
}

/**
 * ★ Round 18: Negotiation Issue
 */
export interface NegotiationIssue {
  issue_id: string;
  description: string;
  stakeholders_involved: string[];
  current_positions: Map<string, number>; // stakeholder -> preferred value
  compromise_range: { min: number; max: number };
  priority: number;
}

/**
 * ★ Round 18: Negotiation Result
 */
export interface NegotiationResult {
  decision: string;
  chosen_compromise: string;
  sacrificed_interest: string;
  explanation: string;
  stakeholder_satisfactions: Map<string, number>;
  escalated_to_human: boolean;
  escalation_reason?: string;
}

/**
 * ★ Round 18: 多利益相关方谈判层
 */
export class StakeholderNegotiationLayer {
  private stakeholders: Map<string, Stakeholder> = new Map();
  private issues: Map<string, NegotiationIssue> = new Map();
  private negotiationTrace: Array<{ timestamp: string; action: string; details: any }> = [];

  constructor() {
    this.initializeDefaultStakeholders();
  }

  private initializeDefaultStakeholders(): void {
    const defaults: Stakeholder[] = [
      {
        id: 'user',
        type: 'user',
        name: 'User',
        goals: ['fast_delivery', 'high_quality', 'low_cost'],
        constraints: ['maximum_budget', 'deadline'],
        risk_tolerance: 0.3,
        veto_power: true,
        priority_weight: 1.0,
        satisfaction_level: 0.8,
      },
      {
        id: 'mission_owner',
        type: 'mission_owner',
        name: 'Mission Owner',
        goals: ['mission_success', 'resource_availability', 'timeline_adherence'],
        constraints: ['resource_limits', 'technical_constraints'],
        risk_tolerance: 0.5,
        veto_power: false,
        priority_weight: 0.8,
        satisfaction_level: 0.7,
      },
      {
        id: 'executive_control',
        type: 'executive_control',
        name: 'Executive Control',
        goals: ['budget_discipline', 'efficiency', 'commitment_fulfillment'],
        constraints: ['budget_ceiling', 'resource_capacity'],
        risk_tolerance: 0.4,
        veto_power: false,
        priority_weight: 0.7,
        satisfaction_level: 0.75,
      },
      {
        id: 'governance',
        type: 'governance',
        name: 'Governance',
        goals: ['risk_management', 'compliance', 'safety'],
        constraints: ['approval_requirements', 'risk_thresholds'],
        risk_tolerance: 0.2,
        veto_power: true,
        priority_weight: 0.9,
        satisfaction_level: 0.85,
      },
      {
        id: 'long_term_system',
        type: 'long_term_system',
        name: 'Long-term System Interest',
        goals: ['accumulated_learning', 'sustainable_growth', 'capability_building'],
        constraints: ['minimum_learning_rate', 'strategy_patch_quality'],
        risk_tolerance: 0.7,
        veto_power: false,
        priority_weight: 0.6,
        satisfaction_level: 0.6,
      },
    ];

    for (const s of defaults) {
      this.stakeholders.set(s.id, s);
    }
  }

  /**
   * ★ Round 18: 注册新的 negotiation issue
   */
  registerIssue(description: string, priority: number, stakeholderIds: string[]): NegotiationIssue {
    const id = `issue_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const issue: NegotiationIssue = {
      issue_id: id,
      description,
      stakeholders_involved: stakeholderIds,
      current_positions: new Map(),
      compromise_range: { min: 0, max: 1 },
      priority,
    };

    this.issues.set(id, issue);
    this.log('issue_registered', { issue_id: id, stakeholders: stakeholderIds });

    return issue;
  }

  /**
   * ★ Round 18: 设置 stakeholder position
   */
  setPosition(issueId: string, stakeholderId: string, position: number): void {
    const issue = this.issues.get(issueId);
    if (!issue) return;

    issue.current_positions.set(stakeholderId, position);
  }

  /**
   * ★ Round 18: 执行 negotiation
   */
  negotiate(issueId: string): NegotiationResult {
    const issue = this.issues.get(issueId);
    if (!issue) {
      return {
        decision: 'no_issue_found',
        chosen_compromise: 'N/A',
        sacrificed_interest: 'N/A',
        explanation: 'Issue not found',
        stakeholder_satisfactions: new Map(),
        escalated_to_human: false,
      };
    }

    // Check for veto power
    const vetoStakeholders = Array.from(this.stakeholders.values()).filter(s => s.veto_power);
    for (const veto of vetoStakeholders) {
      if (issue.stakeholders_involved.includes(veto.id)) {
        const vetoPosition = issue.current_positions.get(veto.id);
        if (vetoPosition !== undefined && vetoPosition < 0.3) {
          this.log('stakeholder_conflict_detected', { issue_id: issueId, veto_stakeholder: veto.id });
          return {
            decision: 'escalate_to_human',
            chosen_compromise: 'Governance veto triggered',
            sacrificed_interest: 'All parties',
            explanation: `Stakeholder ${veto.name} has veto power and rejects this proposal (position: ${vetoPosition})`,
            stakeholder_satisfactions: new Map(),
            escalated_to_human: true,
            escalation_reason: `Veto from ${veto.name} on ${issue.description}`,
          };
        }
      }
    }

    // Calculate weighted compromise
    let weightedSum = 0;
    let totalWeight = 0;

    for (const [stakeholderId, position] of issue.current_positions) {
      const stakeholder = this.stakeholders.get(stakeholderId);
      if (stakeholder) {
        weightedSum += position * stakeholder.priority_weight;
        totalWeight += stakeholder.priority_weight;
      }
    }

    const compromise = totalWeight > 0 ? weightedSum / totalWeight : 0.5;

    // Determine which interest gets sacrificed
    let sacrificedInterest = 'lowest_priority_stakeholder';
    let lowestSatisfaction = 1.0;

    const satisfactions = new Map<string, number>();
    for (const stakeholderId of issue.stakeholders_involved) {
      const stakeholder = this.stakeholders.get(stakeholderId);
      if (stakeholder) {
        const position = issue.current_positions.get(stakeholderId) || 0.5;
        const satisfaction = 1 - Math.abs(position - compromise);
        satisfactions.set(stakeholderId, satisfaction);
        if (satisfaction < lowestSatisfaction && stakeholder.veto_power === false) {
          lowestSatisfaction = satisfaction;
          sacrificedInterest = stakeholder.name;
        }
      }
    }

    this.log('negotiation_result', { issue_id: issueId, compromise, satisfactions: Object.fromEntries(satisfactions) });

    return {
      decision: 'compromise_reached',
      chosen_compromise: `Compromise position: ${compromise.toFixed(2)}`,
      sacrificed_interest: sacrificedInterest,
      explanation: `Negotiated compromise at ${(compromise * 100).toFixed(0)}% based on weighted stakeholder priorities`,
      stakeholder_satisfactions: satisfactions,
      escalated_to_human: false,
    };
  }

  /**
   * ★ Round 18: 更新 stakeholder satisfaction
   */
  updateSatisfaction(stakeholderId: string, delta: number): void {
    const stakeholder = this.stakeholders.get(stakeholderId);
    if (!stakeholder) return;

    stakeholder.satisfaction_level = Math.max(0, Math.min(1, stakeholder.satisfaction_level + delta));
    this.log('stakeholder_satisfaction_updated', { stakeholder_id: stakeholderId, new_satisfaction: stakeholder.satisfaction_level });
  }

  /**
   * ★ Round 18: 获取所有 stakeholder
   */
  getAllStakeholders(): Stakeholder[] {
    return Array.from(this.stakeholders.values());
  }

  /**
   * ★ Round 18: 获取冲突 map
   */
  getConflictMap(): Array<{ issue_id: string; stakeholders: string[]; description: string }> {
    const conflicts: Array<{ issue_id: string; stakeholders: string[]; description: string }> = [];

    for (const [issueId, issue] of this.issues) {
      if (issue.current_positions.size >= 2) {
        const positions = Array.from(issue.current_positions.values());
        const max = Math.max(...positions);
        const min = Math.min(...positions);
        if (max - min > 0.3) {
          conflicts.push({
            issue_id: issueId,
            stakeholders: issue.stakeholders_involved,
            description: issue.description,
          });
        }
      }
    }

    return conflicts;
  }

  /**
   * ★ Round 18: 获取 trace
   */
  getTrace(): Array<{ timestamp: string; action: string; details: any }> {
    return [...this.negotiationTrace];
  }

  private log(action: string, details: any): void {
    this.negotiationTrace.push({ timestamp: new Date().toISOString(), action, details });
  }
}

// ============================================
// PART 3: STRATEGIC FORESIGHT & SCENARIO LAYER
// ============================================

/**
 * ★ Round 18: Horizon 类型
 */
export type HorizonLevel = 'short' | 'medium' | 'long';

/**
 * ★ Round 18: Scenario Entry
 */
export interface Scenario {
  scenario_id: string;
  mission_id?: string;
  description: string;
  time_horizon: HorizonLevel;
  time_horizon_years: number;
  assumptions: string[];
  risk_profile: { probability: number; impact: number };
  expected_value: number;
  contingency_actions: string[];
  contingency_reserved: boolean;
  created_at: string;
}

/**
 * ★ Round 18: Future Branch
 */
export interface FutureBranch {
  branch_id: string;
  scenario_id: string;
  branch_name: string;
  probability: number;
  expected_gain: number;
  expected_risk: number;
  confidence: number;
  reversibility: number;  // 0-1, how hard to undo if wrong
  present_decision_changed: boolean;
  trigger_conditions: string[];
}

/**
 * ★ Round 18: Foresight Result
 */
export interface ForesightResult {
  recommended_present_action: string;
  alternative_actions: string[];
  reserved_contingency?: string;
  reasoning: string;
  horizon_level: HorizonLevel;
}

/**
 * ★ Round 18: 战略前瞻层
 */
export class StrategicForesightLayer {
  private scenarios: Map<string, Scenario> = new Map();
  private branches: Map<string, FutureBranch> = new Map();
  private foresightTrace: Array<{ timestamp: string; action: string; details: any }> = [];

  /**
   * ★ Round 18: 创建 scenario
   */
  createScenario(
    missionId: string | undefined,
    description: string,
    horizon: HorizonLevel,
    assumptions: string[],
    riskProbability: number,
    riskImpact: number,
    expectedValue: number
  ): Scenario {
    const id = `scenario_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const horizonYears = horizon === 'short' ? 0.25 : horizon === 'medium' ? 1 : 3;

    const scenario: Scenario = {
      scenario_id: id,
      mission_id: missionId,
      description,
      time_horizon: horizon,
      time_horizon_years: horizonYears,
      assumptions,
      risk_profile: { probability: riskProbability, impact: riskImpact },
      expected_value: expectedValue,
      contingency_actions: [],
      contingency_reserved: false,
      created_at: new Date().toISOString(),
    };

    this.scenarios.set(id, scenario);
    this.log('scenario_generated', { scenario_id: id, horizon, expected_value: expectedValue });

    return scenario;
  }

  /**
   * ★ Round 18: 添加 future branch
   */
  addBranch(
    scenarioId: string,
    branchName: string,
    probability: number,
    expectedGain: number,
    expectedRisk: number,
    confidence: number,
    reversibility: number,
    triggerConditions: string[]
  ): FutureBranch | null {
    const scenario = this.scenarios.get(scenarioId);
    if (!scenario) return null;

    const id = `branch_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const branch: FutureBranch = {
      branch_id: id,
      scenario_id: scenarioId,
      branch_name: branchName,
      probability,
      expected_gain: expectedGain,
      expected_risk: expectedRisk,
      confidence,
      reversibility,
      present_decision_changed: false,
      trigger_conditions: triggerConditions,
    };

    this.branches.set(id, branch);
    this.log('branch_created', { scenario_id: scenarioId, branch_id: id, probability });

    return branch;
  }

  /**
   * ★ Round 18: 比较 branches
   */
  compareBranches(scenarioId: string): ForesightResult | null {
    const scenario = this.scenarios.get(scenarioId);
    if (!scenario) return null;

    const scenarioBranches = Array.from(this.branches.values()).filter(b => b.scenario_id === scenarioId);
    if (scenarioBranches.length === 0) return null;

    // Calculate net expected value for each branch
    const branchScores = scenarioBranches.map(b => ({
      branch: b,
      net_value: b.expected_gain * b.probability - b.expected_risk * b.probability,
    }));

    branchScores.sort((a, b) => b.net_value - a.net_value);

    const best = branchScores[0].branch;
    const worst = branchScores[branchScores.length - 1].branch;

    // Check if high-risk branch should influence present decision
    let recommendedAction = 'continue_current_path';
    let reservedContingency: string | undefined;

    if (worst.expected_risk > 0.5 && worst.probability > 0.2) {
      // High risk branch detected - reserve contingency
      recommendedAction = 'proceed_with_caution';
      reservedContingency = `If ${worst.branch_name} materializes: ${worst.trigger_conditions.join(', ')}`;

      // Mark this branch as influencing present decision
      worst.present_decision_changed = true;
      this.log('present_decision_changed_by_foresight', { branch_id: worst.branch_id, reason: 'high_risk_branch' });
    }

    this.log('branch_compared', { scenario_id: scenarioId, best_branch: best.branch_id, recommended_action: recommendedAction });

    return {
      recommended_present_action: recommendedAction,
      alternative_actions: scenarioBranches.map(b => {
        const score = branchScores.find(s => s.branch.branch_id === b.branch_id);
        const netVal = score ? score.net_value.toFixed(2) : 'N/A';
        return `${b.branch_name} (EV: ${netVal})`;
      }),
      reserved_contingency: reservedContingency,
      reasoning: `Best branch: ${best.branch_name} (EV: ${branchScores[0].net_value.toFixed(2)}). ${reservedContingency ? 'Contingency reserved for ' + worst.branch_name : 'No contingency needed.'}`,
      horizon_level: scenario.time_horizon,
    };
  }

  /**
   * ★ Round 18: 添加 contingency action
   */
  addContingencyAction(scenarioId: string, action: string): boolean {
    const scenario = this.scenarios.get(scenarioId);
    if (!scenario) return false;

    scenario.contingency_actions.push(action);
    scenario.contingency_reserved = true;
    this.log('contingency_reserved', { scenario_id: scenarioId, action });

    return true;
  }

  /**
   * ★ Round 18: 获取 foresight 影响 present decision 的记录
   */
  getForesightInfluencedDecisions(): FutureBranch[] {
    return Array.from(this.branches.values()).filter(b => b.present_decision_changed);
  }

  /**
   * ★ Round 18: 获取所有 scenario
   */
  getAllScenarios(): Scenario[] {
    return Array.from(this.scenarios.values());
  }

  /**
   * ★ Round 18: 获取所有 branches
   */
  getAllBranches(): FutureBranch[] {
    return Array.from(this.branches.values());
  }

  /**
   * ★ Round 18: 获取 trace
   */
  getTrace(): Array<{ timestamp: string; action: string; details: any }> {
    return [...this.foresightTrace];
  }

  private log(action: string, details: any): void {
    this.foresightTrace.push({ timestamp: new Date().toISOString(), action, details });
  }
}

// ============================================
// PART 4: INTEGRATED COGNITIVE INTELLIGENCE ENGINE
// ============================================

/**
 * ★ Round 18: 认知智能引擎（整合三层子系统）
 */
export class CognitiveIntelligenceEngine {
  epistemic: EpistemicGovernanceLayer;
  stakeholder: StakeholderNegotiationLayer;
  foresight: StrategicForesightLayer;

  constructor() {
    this.epistemic = new EpistemicGovernanceLayer();
    this.stakeholder = new StakeholderNegotiationLayer();
    this.foresight = new StrategicForesightLayer();
  }

  /**
   * ★ Round 18: 处理冲突 truth 并影响决策
   */
  processConflictingTruth(fact: string, sourceA: { id: string; value: number; confidence: number }, sourceB: { id: string; value: number; confidence: number }): { truth: TruthEntry; decisionImpact: string } {
    // Register first source
    const truth = this.epistemic.registerTruth(fact, sourceA.id, sourceA.value, sourceA.confidence);

    // Add conflicting source
    const resolved = this.epistemic.addConflictingSource(truth.id, sourceB.id, sourceB.value, sourceB.confidence);

    if (resolved && resolved.conflict_resolved) {
      // Determine decision impact based on confidence
      if (resolved.truth_confidence < 0.3) {
        return { truth: resolved, decisionImpact: 'defer_decision_until_more_evidence' };
      } else if (resolved.truth_confidence < 0.6) {
        return { truth: resolved, decisionImpact: 'proceed_with_low_confidence_flagged' };
      } else {
        return { truth: resolved, decisionImpact: 'proceed_with_confidence' };
      }
    }

    return { truth: resolved || truth, decisionImpact: 'unable_to_resolve' };
  }

  /**
   * ★ Round 18: 执行 stakeholder negotiation 并返回结果
   */
  negotiateWithStakeholders(description: string, positions: Map<string, number>): NegotiationResult {
    const issue = this.stakeholder.registerIssue(description, 0.7, Array.from(positions.keys()));

    for (const [stakeholderId, position] of positions) {
      this.stakeholder.setPosition(issue.issue_id, stakeholderId, position);
    }

    return this.stakeholder.negotiate(issue.issue_id);
  }

  /**
   * ★ Round 18: 生成并分析 scenario
   */
  analyzeScenarioWithForesight(
    missionId: string | undefined,
    description: string,
    horizon: HorizonLevel,
    branches: Array<{ name: string; probability: number; gain: number; risk: number; confidence: number; reversibility: number; triggers: string[] }>
  ): ForesightResult | null {
    const assumptions = branches.map(b => `${b.name}: P=${b.probability}`);
    const avgRisk = branches.reduce((sum, b) => sum + b.risk * b.probability, 0);
    const avgValue = branches.reduce((sum, b) => sum + b.gain * b.probability, 0);

    const scenario = this.foresight.createScenario(
      missionId,
      description,
      horizon,
      assumptions,
      avgRisk,
      avgRisk,
      avgValue
    );

    for (const branch of branches) {
      this.foresight.addBranch(
        scenario.scenario_id,
        branch.name,
        branch.probability,
        branch.gain,
        branch.risk,
        branch.confidence,
        branch.reversibility,
        branch.triggers
      );
    }

    return this.foresight.compareBranches(scenario.scenario_id);
  }

  /**
   * ★ Round 18: 获取完整追踪
   */
  getFullTrace(): {
    epistemic_trace: ReturnType<EpistemicGovernanceLayer['getTrace']>;
    stakeholder_trace: ReturnType<StakeholderNegotiationLayer['getTrace']>;
    foresight_trace: ReturnType<StrategicForesightLayer['getTrace']>;
  } {
    return {
      epistemic_trace: this.epistemic.getTrace(),
      stakeholder_trace: this.stakeholder.getTrace(),
      foresight_trace: this.foresight.getTrace(),
    };
  }
}

// ============================================
// 单例
// ============================================
export const cognitiveIntelligenceEngine = new CognitiveIntelligenceEngine();
