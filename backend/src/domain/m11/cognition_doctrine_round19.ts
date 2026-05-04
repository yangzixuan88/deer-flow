/**
 * Round 19 身份声誉层 + 规范传播层 + 长期教义演化层
 * ================================================
 * 三大根因治理维度：
 * - Root Cause 1: 身份与声誉未被追踪（Identity & Reputation）
 * - Root Cause 2: 规范/教义未通过实践验证传播（Norm/Doctrine Propagation）
 * - Root Cause 3: 长期战略规则未随环境演化（Long-Horizon Doctrine Evolution）
 * ================================================
 */

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

export type IdentityStatus = 'active' | 'suspended' | 'deprecated';
export type ReputationLevel = 'trusted' | 'neutral' | 'uncertain' | 'untrusted' | 'suppressed';
export type DecisionWeightMode = 'reputation_only' | 'reputation_plus_role' | 'balanced';
export type NormStatus = 'draft' | 'candidate' | 'promoted' | 'active' | 'violated' | 'retired';
export type NormCompliance = 'compliant' | 'partial' | 'violation' | 'unknown';
export type DoctrineStatus = 'candidate' | 'reviewing' | 'accepted' | 'active' | 'superseded' | 'rejected';
export type DriftStatus = 'stable' | 'drifting' | 'significant_drift' | 'unknown';
export type DoctrineInfluence = 'directly_influences' | 'background_context' | 'historical_reference';

export interface IdentityEntry {
  identity_id: string;
  source_type: 'user' | 'agent' | 'system' | 'external';
  label: string;
  created_at: number;
  last_active_at: number;
  status: IdentityStatus;
  metadata: Record<string, any>;
}

export interface ReputationEntry {
  identity_id: string;
  source_id: string;
  trust_score: number;           // 0-1, empirical trust derived from outcome accuracy
  decision_weight: number;       // 0-1, how much this source's input is weighted
  role_trust: number;           // 0-1, trust based on role correctness
  calibration_score: number;     // 0-1, how well stated confidence matches reality
  conflict_history: number;      // how many conflicts this source was involved in
  outcome_accuracy: number;      // 0-1, historical accuracy of this source's predictions
  total_decisions: number;      // number of decisions involving this source
  last_updated_at: number;
  reputation_level: ReputationLevel;
  suppressed_until: number | null;
  decay_history: number[];      // track decay events
}

export interface ReputationUpdateRule {
  rule_id: string;
  trigger: 'outcome_confirmed' | 'outcome_refuted' | 'conflict_detected' | 'confidence_mismatch' | 'time_based_decay';
  adjustment_method: 'incremental' | 'boltzmann' | 'honeymoon' | 'punishment';
  adjustment_factor: number;    // magnitude of adjustment
  conditions: Record<string, any>;
  description: string;
}

export interface NormEntry {
  norm_id: string;
  name: string;
  description: string;
  source_pattern: string;       // what behavior pattern this norm encodes
  source_identity_id: string;   // who/what generated this norm
  status: NormStatus;
  confidence: number;           // 0-1
  success_count: number;        // times this norm was cited in successful decisions
  failure_count: number;        // times following this norm led to failure
  compliance_rate: number;      // 0-1
  created_at: number;
  promoted_at: number | null;
  activated_at: number | null;
  violated_count: number;
  trace: NormTraceEntry[];
}

export interface NormTraceEntry {
  action: string;
  norm_id: string;
  timestamp: number;
  details: Record<string, any>;
}

export interface NormViolation {
  norm_id: string;
  violating_identity_id: string;
  detected_at: number;
  severity: 'minor' | 'major' | 'critical';
  description: string;
}

export interface DoctrineEntry {
  doctrine_id: string;
  name: string;
  description: string;
  norm_ids: string[];           // norms that compose this doctrine
  status: DoctrineStatus;
  candidate_generated_at: number;
  reviewed_at: number | null;
  accepted_at: number | null;
  supersedes_doctrine_id: string | null;
  influence: DoctrineInfluence;
  drift_status: DriftStatus;
  drift_score: number;          // 0-1, how much the doctrine's effectiveness has drifted
  evidence_count: number;        // supporting evidence for this doctrine
  challenge_count: number;       // challenges filed against this doctrine
  trace: DoctrineTraceEntry[];
}

export interface DoctrineTraceEntry {
  action: string;
  doctrine_id: string;
  timestamp: number;
  details: Record<string, any>;
}

export interface DoctrineDriftSignal {
  doctrine_id: string;
  detected_at: number;
  drift_score: number;
  reason: string;
  affected_norm_ids: string[];
}

export interface NormFeedbackLoop {
  norm_id: string;
  feedback_source: 'outcome' | 'stakeholder' | 'self_reflection' | 'drift_detection';
  feedback_data: Record<string, any>;
  loop_closed: boolean;
  closed_at: number | null;
}

// ─────────────────────────────────────────────
// Identity & Reputation Layer
// ─────────────────────────────────────────────

export class IdentityReputationLayer {
  private identities: Map<string, IdentityEntry> = new Map();
  private reputations: Map<string, ReputationEntry> = new Map();
  private reputationRules: Map<string, ReputationUpdateRule> = new Map();
  private trace: any[] = [];

  private idCounter = 0;
  private ruleIdCounter = 0;

  constructor() {
    this.initializeDefaultRules();
    this.registerDefaultIdentities();
  }

  private initializeDefaultRules() {
    const rules: Omit<ReputationUpdateRule, 'rule_id'>[] = [
      {
        trigger: 'outcome_confirmed',
        adjustment_method: 'incremental',
        adjustment_factor: 0.05,
        conditions: {},
        description: 'When an outcome confirms a source prediction, incrementally increase trust'
      },
      {
        trigger: 'outcome_refuted',
        adjustment_method: 'punishment',
        adjustment_factor: 0.10,
        conditions: {},
        description: 'When an outcome refutes a source prediction, apply stronger punishment'
      },
      {
        trigger: 'conflict_detected',
        adjustment_method: 'incremental',
        adjustment_factor: 0.03,
        conditions: {},
        description: 'Conflict detection reduces trust slightly'
      },
      {
        trigger: 'confidence_mismatch',
        adjustment_method: 'boltzmann',
        adjustment_factor: 0.07,
        conditions: {},
        description: 'When stated confidence differs from actual accuracy, apply Boltzmann adjustment'
      },
      {
        trigger: 'time_based_decay',
        adjustment_method: 'incremental',
        adjustment_factor: 0.01,
        conditions: { inactive_days: 30 },
        description: 'Reduce trust for sources inactive for 30+ days'
      }
    ];

    for (const r of rules) {
      const rule: ReputationUpdateRule = { ...r, rule_id: `rule_${++this.ruleIdCounter}` };
      this.reputationRules.set(rule.rule_id, rule);
    }
  }

  private registerDefaultIdentities() {
    const defaults = [
      { source_type: 'system' as const, label: 'system_monitor' },
      { source_type: 'user' as const, label: 'user' },
      { source_type: 'agent' as const, label: 'governance' },
      { source_type: 'agent' as const, label: 'executive_control' },
      { source_type: 'agent' as const, label: 'long_term_system' },
    ];

    for (const d of defaults) {
      const identity = this.registerIdentity(d.source_type, d.label, {});
      this.initializeReputation(identity.identity_id, d.label);
    }
  }

  private generateId(prefix: string): string {
    return `${prefix}_${++this.idCounter}_${Date.now()}`;
  }

  private logAction(action: string, identityId: string | undefined, details: any) {
    this.trace.push({ action, identity_id: identityId, timestamp: Date.now(), details });
  }

  registerIdentity(sourceType: IdentityReputationLayer extends { identities: Map<string, infer E> } ? never : 'user' | 'agent' | 'system' | 'external', label: string, metadata: Record<string, any>): IdentityEntry {
    const existing = Array.from(this.identities.values()).find(i => i.label === label);
    if (existing) {
      existing.last_active_at = Date.now();
      this.logAction('identity_reactivated', existing.identity_id, { label });
      return existing;
    }

    const identity: IdentityEntry = {
      identity_id: this.generateId('id'),
      source_type: sourceType,
      label,
      created_at: Date.now(),
      last_active_at: Date.now(),
      status: 'active',
      metadata
    };

    this.identities.set(identity.identity_id, identity);
    this.logAction('identity_registered', identity.identity_id, { label, sourceType });
    return identity;
  }

  initializeReputation(identityId: string, sourceId: string): ReputationEntry {
    const rep: ReputationEntry = {
      identity_id: identityId,
      source_id: sourceId,
      trust_score: 0.5,
      decision_weight: 0.5,
      role_trust: 0.5,
      calibration_score: 0.5,
      conflict_history: 0,
      outcome_accuracy: 0.5,
      total_decisions: 0,
      last_updated_at: Date.now(),
      reputation_level: 'neutral',
      suppressed_until: null,
      decay_history: []
    };

    this.reputations.set(sourceId, rep);
    this.logAction('reputation_initialized', identityId, { sourceId, initial_trust: 0.5 });
    return rep;
  }

  getReputation(sourceId: string): ReputationEntry | null {
    return this.reputations.get(sourceId) || null;
  }

  getIdentity(identityId: string): IdentityEntry | null {
    return this.identities.get(identityId) || null;
  }

  getIdentityByLabel(label: string): IdentityEntry | null {
    return Array.from(this.identities.values()).find(i => i.label === label) || null;
  }

  updateReputation(sourceId: string, trigger: ReputationUpdateRule['trigger'], outcomeConfidence?: number): ReputationEntry | null {
    const rep = this.reputations.get(sourceId);
    if (!rep) return null;

    // Check suppression
    if (rep.suppressed_until !== null && Date.now() < rep.suppressed_until) {
      return rep;
    }

    const rule = Array.from(this.reputationRules.values()).find(r => r.trigger === trigger);
    if (!rule) return rep;

    let newTrust = rep.trust_score;
    let newAccuracy = rep.outcome_accuracy;
    let newCalibration = rep.calibration_score;

    switch (rule.adjustment_method) {
      case 'incremental':
        if (trigger === 'outcome_confirmed') {
          newTrust = Math.min(1, rep.trust_score + rule.adjustment_factor);
          newAccuracy = Math.min(1, rep.outcome_accuracy + rule.adjustment_factor * 0.5);
        } else if (trigger === 'outcome_refuted') {
          newTrust = Math.max(0, rep.trust_score - rule.adjustment_factor);
          newAccuracy = Math.max(0, rep.outcome_accuracy - rule.adjustment_factor * 0.5);
        } else if (trigger === 'time_based_decay') {
          newTrust = Math.max(0.1, rep.trust_score - rule.adjustment_factor);
          rep.decay_history.push(newTrust);
        } else {
          newTrust = Math.max(0, rep.trust_score - rule.adjustment_factor * 0.5);
        }
        break;

      case 'punishment':
        newTrust = Math.max(0, rep.trust_score - rule.adjustment_factor * 1.5);
        newAccuracy = Math.max(0, rep.outcome_accuracy - rule.adjustment_factor);
        break;

      case 'boltzmann':
        if (outcomeConfidence !== undefined) {
          const delta = Math.abs(rep.calibration_score - outcomeConfidence);
          const boltzmannFactor = Math.exp(-delta * 5) * rule.adjustment_factor;
          if (outcomeConfidence > rep.calibration_score) {
            newTrust = Math.min(1, rep.trust_score + boltzmannFactor);
          } else {
            newTrust = Math.max(0, rep.trust_score - boltzmannFactor);
          }
          newCalibration = rep.calibration_score + (outcomeConfidence - rep.calibration_score) * 0.2;
        }
        break;

      case 'honeymoon':
        if (trigger === 'outcome_confirmed') {
          newTrust = Math.min(1, rep.trust_score + rule.adjustment_factor * 1.5);
        } else {
          newTrust = Math.max(0, rep.trust_score - rule.adjustment_factor * 0.5);
        }
        break;
    }

    rep.trust_score = newTrust;
    rep.outcome_accuracy = newAccuracy;
    rep.calibration_score = newCalibration;
    rep.last_updated_at = Date.now();
    rep.total_decisions += 1;
    rep.reputation_level = this.computeReputationLevel(newTrust, rep.suppressed_until);

    this.logAction('reputation_updated', rep.identity_id, {
      sourceId,
      trigger,
      old_trust: rep.trust_score,
      new_trust: newTrust,
      adjustment_method: rule.adjustment_method
    });

    return rep;
  }

  private computeReputationLevel(trust: number, suppressedUntil: number | null): ReputationLevel {
    if (suppressedUntil !== null && Date.now() < suppressedUntil) return 'suppressed';
    if (trust >= 0.8) return 'trusted';
    if (trust >= 0.6) return 'neutral';
    if (trust >= 0.4) return 'uncertain';
    return 'untrusted';
  }

  applyDecisionWeight(sourceId: string, baseWeight: number, mode: DecisionWeightMode): number {
    const rep = this.reputations.get(sourceId);
    if (!rep) return baseWeight;

    // Check suppression
    if (rep.suppressed_until !== null && Date.now() < rep.suppressed_until) {
      return 0;
    }

    switch (mode) {
      case 'reputation_only':
        return rep.decision_weight;
      case 'reputation_plus_role':
        return (rep.decision_weight + rep.role_trust) / 2;
      case 'balanced':
        return (baseWeight * 0.4 + rep.decision_weight * 0.6);
      default:
        return baseWeight;
    }
  }

  suppressBadActor(sourceId: string, durationMs: number, reason: string): boolean {
    const rep = this.reputations.get(sourceId);
    if (!rep) return false;

    rep.suppressed_until = Date.now() + durationMs;
    rep.reputation_level = 'suppressed';
    rep.trust_score = Math.max(0, rep.trust_score - 0.3);

    this.logAction('bad_actor_suppressed', rep.identity_id, {
      sourceId,
      duration_ms: durationMs,
      reason,
      new_trust: rep.trust_score
    });

    return true;
  }

  applyTimeBasedDecay(inactiveThresholdDays: number = 30): number {
    const now = Date.now();
    const threshold = inactiveThresholdDays * 24 * 60 * 60 * 1000;
    let decayed = 0;

    for (const [sourceId, rep] of this.reputations) {
      const inactiveTime = now - rep.last_updated_at;
      if (inactiveTime > threshold) {
        const rule = Array.from(this.reputationRules.values()).find(r => r.trigger === 'time_based_decay');
        if (rule) {
          const decayAmount = rule.adjustment_factor * Math.floor(inactiveTime / threshold);
          rep.trust_score = Math.max(0.1, rep.trust_score - decayAmount);
          rep.decay_history.push(rep.trust_score);
          decayed++;
        }
      }
    }

    this.logAction('time_based_decay_applied', undefined, { identities_decayed: decayed });
    return decayed;
  }

  getAllIdentities(): IdentityEntry[] {
    return Array.from(this.identities.values());
  }

  getAllReputations(): ReputationEntry[] {
    return Array.from(this.reputations.values());
  }

  getTrace(): any[] {
    return [...this.trace];
  }

  getSuppressedIdentities(): ReputationEntry[] {
    return Array.from(this.reputations.values()).filter(r => r.reputation_level === 'suppressed');
  }

  // Record outcome for reputation update
  recordOutcome(sourceId: string, predictedValue: number, actualValue: number): ReputationEntry | null {
    const rep = this.reputations.get(sourceId);
    if (!rep) return null;

    const delta = Math.abs(predictedValue - actualValue);
    const isCorrect = delta < 0.2;
    const confidenceMatch = delta < 0.1;

    if (isCorrect) {
      this.updateReputation(sourceId, 'outcome_confirmed');
    } else {
      this.updateReputation(sourceId, 'outcome_refuted');
    }

    if (confidenceMatch) {
      this.updateReputation(sourceId, 'confidence_mismatch', predictedValue);
    }

    this.logAction('outcome_recorded', rep.identity_id, {
      sourceId,
      predicted: predictedValue,
      actual: actualValue,
      correct: isCorrect
    });

    return rep;
  }
}

// ─────────────────────────────────────────────
// Norm & Doctrine Propagation Layer
// ─────────────────────────────────────────────

export class NormDoctrinePropagationLayer {
  private norms: Map<string, NormEntry> = new Map();
  private violations: NormViolation[] = [];
  private feedbackLoops: Map<string, NormFeedbackLoop> = new Map();
  private trace: any[] = [];

  private normIdCounter = 0;

  private generateId(prefix: string): string {
    return `${prefix}_${++this.normIdCounter}_${Date.now()}`;
  }

  private logAction(action: string, normId: string | undefined, details: any) {
    this.trace.push({ action, norm_id: normId, timestamp: Date.now(), details });
  }

  registerNorm(pattern: string, sourceIdentityId: string, description: string): NormEntry {
    const existing = Array.from(this.norms.values()).find(n => n.source_pattern === pattern);
    if (existing) {
      this.logAction('norm_reregistered', existing.norm_id, { pattern });
      return existing;
    }

    const norm: NormEntry = {
      norm_id: this.generateId('norm'),
      name: pattern.substring(0, 50),
      description,
      source_pattern: pattern,
      source_identity_id: sourceIdentityId,
      status: 'draft',
      confidence: 0.3,
      success_count: 0,
      failure_count: 0,
      compliance_rate: 1.0,
      created_at: Date.now(),
      promoted_at: null,
      activated_at: null,
      violated_count: 0,
      trace: []
    };

    this.norms.set(norm.norm_id, norm);
    this.logAction('norm_registered', norm.norm_id, { pattern, sourceIdentityId });
    return norm;
  }

  promoteNorm(normId: string, targetStatus: NormStatus = 'candidate'): NormEntry | null {
    const norm = this.norms.get(normId);
    if (!norm) return null;

    if (targetStatus === 'candidate' && norm.status === 'draft') {
      norm.status = 'candidate';
      norm.confidence = Math.min(0.6, norm.confidence + 0.1);
      this.logAction('norm_promoted_to_candidate', normId, { old_status: 'draft' });
    } else if (targetStatus === 'promoted' && norm.status === 'candidate') {
      norm.status = 'promoted';
      norm.promoted_at = Date.now();
      norm.confidence = Math.min(0.8, norm.confidence + 0.15);
      this.logAction('norm_promoted', normId, { old_status: 'candidate' });
    } else if (targetStatus === 'active' && norm.status === 'promoted') {
      norm.status = 'active';
      norm.activated_at = Date.now();
      norm.confidence = Math.min(0.95, norm.confidence + 0.1);
      this.logAction('norm_activated', normId, { old_status: 'promoted' });
    }

    norm.trace.push({
      action: `status_change_to_${norm.status}`,
      norm_id: normId,
      timestamp: Date.now(),
      details: { targetStatus }
    });

    return norm;
  }

  recordNormCompliance(normId: string, compliant: boolean, context: Record<string, any>): NormEntry | null {
    const norm = this.norms.get(normId);
    if (!norm) return null;

    if (compliant) {
      norm.success_count += 1;
      norm.compliance_rate = (norm.compliance_rate * (norm.success_count + norm.failure_count - 1) + 1) / (norm.success_count + norm.failure_count);
    } else {
      norm.failure_count += 1;
      norm.violated_count += 1;
      norm.compliance_rate = (norm.compliance_rate * (norm.success_count + norm.failure_count - 1)) / (norm.success_count + norm.failure_count);

      const violation: NormViolation = {
        norm_id: normId,
        violating_identity_id: context.identity_id || 'unknown',
        detected_at: Date.now(),
        severity: norm.compliance_rate < 0.5 ? 'critical' : (norm.compliance_rate < 0.7 ? 'major' : 'minor'),
        description: `Compliance rate dropped to ${norm.compliance_rate}`
      };
      this.violations.push(violation);
      this.logAction('norm_violated', normId, { violation, context });
    }

    this.logAction('norm_compliance_recorded', normId, {
      compliant,
      new_compliance_rate: norm.compliance_rate,
      success_count: norm.success_count,
      failure_count: norm.failure_count
    });

    return norm;
  }

  checkCompliance(normId: string, behavior: string): boolean {
    const norm = this.norms.get(normId);
    if (!norm || norm.status !== 'active') return true;

    // Simple pattern matching for compliance check
    const compliant = behavior.includes(norm.source_pattern) ||
                       norm.source_pattern === 'default' ||
                       norm.source_pattern.length === 0;

    this.recordNormCompliance(normId, compliant, { behavior });
    return compliant;
  }

  closeFeedbackLoop(normId: string, feedbackSource: NormFeedbackLoop['feedback_source'], feedbackData: Record<string, any>): boolean {
    const norm = this.norms.get(normId);
    if (!norm) return false;

    const loop: NormFeedbackLoop = {
      norm_id: normId,
      feedback_source: feedbackSource,
      feedback_data: feedbackData,
      loop_closed: true,
      closed_at: Date.now()
    };

    this.feedbackLoops.set(normId, loop);

    // Adjust norm confidence based on feedback
    if (feedbackSource === 'outcome' || feedbackSource === 'stakeholder') {
      norm.confidence = Math.min(0.95, norm.confidence + 0.05);
    } else if (feedbackSource === 'drift_detection') {
      norm.confidence = Math.max(0.1, norm.confidence - 0.1);
    }

    this.logAction('feedback_loop_closed', normId, { feedbackSource, feedback_data: feedbackData });
    return true;
  }

  getActiveNorms(): NormEntry[] {
    return Array.from(this.norms.values()).filter(n => n.status === 'active');
  }

  getNormViolations(): NormViolation[] {
    return [...this.violations];
  }

  getNormsByStatus(status: NormStatus): NormEntry[] {
    return Array.from(this.norms.values()).filter(n => n.status === status);
  }

  getNormById(normId: string): NormEntry | undefined {
    return this.norms.get(normId);
  }

  getTrace(): any[] {
    return [...this.trace];
  }

  retireNorm(normId: string, reason: string): boolean {
    const norm = this.norms.get(normId);
    if (!norm) return false;

    norm.status = 'retired';
    this.logAction('norm_retired', normId, { reason, final_compliance_rate: norm.compliance_rate });
    return true;
  }
}

// ─────────────────────────────────────────────
// Long-Horizon Doctrine Layer
// ─────────────────────────────────────────────

export class LongHorizonDoctrineLayer {
  private doctrines: Map<string, DoctrineEntry> = new Map();
  private driftSignals: DoctrineDriftSignal[] = [];
  private trace: any[] = [];

  private doctrineIdCounter = 0;

  private generateId(prefix: string): string {
    return `${prefix}_${++this.doctrineIdCounter}_${Date.now()}`;
  }

  private logAction(action: string, doctrineId: string | undefined, details: any) {
    this.trace.push({ action, doctrine_id: doctrineId, timestamp: Date.now(), details });
  }

  generateDoctrineCandidate(normIds: string[], name: string, description: string, influencedBy: DoctrineInfluence = 'directly_influences'): DoctrineEntry | null {
    if (normIds.length === 0) return null;

    const doctrine: DoctrineEntry = {
      doctrine_id: this.generateId('doc'),
      name,
      description,
      norm_ids: normIds,
      status: 'candidate',
      candidate_generated_at: Date.now(),
      reviewed_at: null,
      accepted_at: null,
      supersedes_doctrine_id: null,
      influence: influencedBy,
      drift_status: 'unknown',
      drift_score: 0.0,
      evidence_count: 0,
      challenge_count: 0,
      trace: []
    };

    this.doctrines.set(doctrine.doctrine_id, doctrine);
    this.logAction('doctrine_candidate_generated', doctrine.doctrine_id, { name, norm_ids: normIds, influencedBy });

    return doctrine;
  }

  submitForReview(doctrineId: string): DoctrineEntry | null {
    const doctrine = this.doctrines.get(doctrineId);
    if (!doctrine || doctrine.status !== 'candidate') return null;

    doctrine.status = 'reviewing';
    doctrine.reviewed_at = Date.now();
    this.logAction('doctrine_submitted_for_review', doctrineId, {});
    return doctrine;
  }

  acceptDoctrine(doctrineId: string, supersedesId?: string): DoctrineEntry | null {
    const doctrine = this.doctrines.get(doctrineId);
    if (!doctrine || doctrine.status !== 'reviewing') return null;

    doctrine.status = 'accepted';
    doctrine.accepted_at = Date.now();

    if (supersedesId) {
      const old = this.doctrines.get(supersedesId);
      if (old) {
        old.status = 'superseded';
        doctrine.supersedes_doctrine_id = supersedesId;
        this.logAction('doctrine_supersedes_old', doctrineId, { superseded_id: supersedesId });
      }
    }

    doctrine.evidence_count += 1;
    this.logAction('doctrine_accepted', doctrineId, { supersedesId });
    return doctrine;
  }

  rejectDoctrine(doctrineId: string, reason: string): boolean {
    const doctrine = this.doctrines.get(doctrineId);
    if (!doctrine) return false;

    doctrine.status = 'rejected';
    doctrine.challenge_count += 1;
    this.logAction('doctrine_rejected', doctrineId, { reason });
    return true;
  }

  activateDoctrine(doctrineId: string): DoctrineEntry | null {
    const doctrine = this.doctrines.get(doctrineId);
    if (!doctrine || doctrine.status !== 'accepted') return null;

    doctrine.status = 'active';
    this.logAction('doctrine_activated', doctrineId, {});
    return doctrine;
  }

  fileChallenge(doctrineId: string, challengerIdentity: string, reason: string): boolean {
    const doctrine = this.doctrines.get(doctrineId);
    if (!doctrine) return false;

    doctrine.challenge_count += 1;
    this.logAction('doctrine_challenge_filed', doctrineId, { challengerIdentity, reason });
    return true;
  }

  detectDrift(doctrineId: string, currentComplianceRate: number, expectedComplianceRate: number): DoctrineDriftSignal | null {
    const doctrine = this.doctrines.get(doctrineId);
    if (!doctrine) return null;

    const driftScore = Math.abs(currentComplianceRate - expectedComplianceRate);
    let driftStatus: DriftStatus = 'stable';

    if (driftScore > 0.3) {
      driftStatus = 'significant_drift';
    } else if (driftScore > 0.15) {
      driftStatus = 'drifting';
    } else if (driftScore > 0.05) {
      driftStatus = 'drifting';
    } else {
      driftStatus = 'stable';
    }

    doctrine.drift_score = driftScore;
    doctrine.drift_status = driftStatus;

    if (driftStatus !== 'stable') {
      const signal: DoctrineDriftSignal = {
        doctrine_id: doctrineId,
        detected_at: Date.now(),
        drift_score: driftScore,
        reason: `Compliance rate ${currentComplianceRate} differs from expected ${expectedComplianceRate}`,
        affected_norm_ids: doctrine.norm_ids
      };
      this.driftSignals.push(signal);
      this.logAction('doctrine_drift_detected', doctrineId, { driftScore, driftStatus });
      return signal;
    }

    this.logAction('doctrine_drift_checked', doctrineId, { driftScore, driftStatus });
    return null;
  }

  getActiveDoctrines(): DoctrineEntry[] {
    return Array.from(this.doctrines.values()).filter(d => d.status === 'active');
  }

  getDoctrinesByStatus(status: DoctrineStatus): DoctrineEntry[] {
    return Array.from(this.doctrines.values()).filter(d => d.status === status);
  }

  getDoctrineById(doctrineId: string): DoctrineEntry | undefined {
    return this.doctrines.get(doctrineId);
  }

  getDriftSignals(): DoctrineDriftSignal[] {
    return [...this.driftSignals];
  }

  getTrace(): any[] {
    return [...this.trace];
  }

  getDoctrine(docrineId: string): DoctrineEntry | null {
    return this.doctrines.get(docrineId) || null;
  }

  // Get doctrine influence on a decision
  getDoctrineInfluence(doctrineId: string): DoctrineInfluence | null {
    const doctrine = this.doctrines.get(doctrineId);
    return doctrine ? doctrine.influence : null;
  }
}

// ─────────────────────────────────────────────
// Integrated Doctrine Intelligence Engine
// ─────────────────────────────────────────────

export class CognitiveDoctrineEngine {
  identity: IdentityReputationLayer;
  norm: NormDoctrinePropagationLayer;
  doctrine: LongHorizonDoctrineLayer;

  constructor() {
    this.identity = new IdentityReputationLayer();
    this.norm = new NormDoctrinePropagationLayer();
    this.doctrine = new LongHorizonDoctrineLayer();
  }

  // Process reputation update with outcome
  processReputationUpdate(sourceId: string, predictedValue: number, actualValue: number): ReputationEntry | null {
    return this.identity.recordOutcome(sourceId, predictedValue, actualValue);
  }

  // Register identity and create initial reputation
  registerWithReputation(sourceType: 'user' | 'agent' | 'system' | 'external', label: string, metadata: Record<string, any> = {}): { identity: IdentityEntry; reputation: ReputationEntry } {
    const identity = this.identity.registerIdentity(sourceType, label, metadata);
    const reputation = this.identity.initializeReputation(identity.identity_id, label);
    return { identity, reputation };
  }

  // Get weighted decision input
  getWeightedInput(sourceId: string, baseWeight: number, mode: DecisionWeightMode = 'balanced'): number {
    return this.identity.applyDecisionWeight(sourceId, baseWeight, mode);
  }

  // Register norm from observed behavior
  registerNormFromBehavior(pattern: string, identityLabel: string, description: string): NormEntry | null {
    const identity = this.identity.getIdentityByLabel(identityLabel);
    if (!identity) return null;
    return this.norm.registerNorm(pattern, identity.identity_id, description);
  }

  // Promote norm through lifecycle
  promoteNorm(normId: string): NormEntry | null {
    const norm = this.norm.getNormById(normId);
    if (!norm) return null;

    if (norm.status === 'draft') return this.norm.promoteNorm(normId, 'candidate');
    if (norm.status === 'candidate') return this.norm.promoteNorm(normId, 'promoted');
    if (norm.status === 'promoted') return this.norm.promoteNorm(normId, 'active');
    return norm;
  }

  // Create doctrine from norms
  createDoctrine(normIds: string[], name: string, description: string): DoctrineEntry | null {
    return this.doctrine.generateDoctrineCandidate(normIds, name, description);
  }

  // Evolve doctrine through review and activation
  evolveDoctrine(doctrineId: string): DoctrineEntry | null {
    const d = this.doctrine.getDoctrine(doctrineId);
    if (!d) return null;

    if (d.status === 'candidate') {
      this.doctrine.submitForReview(doctrineId);
      return d;
    }
    if (d.status === 'reviewing') {
      this.doctrine.acceptDoctrine(doctrineId);
      return d;
    }
    if (d.status === 'accepted') {
      this.doctrine.activateDoctrine(doctrineId);
      return d;
    }
    return d;
  }

  // Check all active norms for drift
  checkDriftAcrossDoctrines(): DoctrineDriftSignal[] {
    const signals: DoctrineDriftSignal[] = [];
    const activeNorms = this.norm.getActiveNorms();

    for (const norm of activeNorms) {
      const expectedRate = 0.8; // baseline expected compliance
      const currentRate = norm.compliance_rate;

      // Find doctrines that reference this norm
      const referencingDoctrines = Array.from(this.doctrine.getDoctrinesByStatus('active'))
        .filter(d => d.norm_ids.includes(norm.norm_id) && d.status === 'active');

      for (const doc of referencingDoctrines) {
        const signal = this.doctrine.detectDrift(doc.doctrine_id, currentRate, expectedRate);
        if (signal) signals.push(signal);
      }
    }

    return signals;
  }

  // Get full trace from all subsystems
  getFullTrace(): { identity_trace: any[]; norm_trace: any[]; doctrine_trace: any[] } {
    return {
      identity_trace: this.identity.getTrace(),
      norm_trace: this.norm.getTrace(),
      doctrine_trace: this.doctrine.getTrace()
    };
  }

  // Suppress bad actor
  suppressBadActor(sourceId: string, durationMs: number, reason: string): boolean {
    return this.identity.suppressBadActor(sourceId, durationMs, reason);
  }
}

export const cognitiveDoctrineEngine = new CognitiveDoctrineEngine();
