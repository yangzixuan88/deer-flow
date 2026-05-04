/**
 * @file types.ts
 * @description Upgrade Center shared type definitions
 * U0-U8 stages use these types for inter-module communication
 */

import { Stage2Bottlenecks, Stage4AssetChanges } from '../domain/nightly_distiller';

// ============================================================================
// Observation Pool
// ============================================================================

export interface ObservationCandidate {
  candidate_id: string;
  project?: string;
  source: 'external_scout' | 'internal_bottleneck' | 'asset_degradation';
  capability_gain: string[];
  added_at: string;
  last_reviewed_at?: string;
  review_count: number;
  status: 'active' | 'promoted' | 'rejected' | 'expired';
}

// ============================================================================
// Constitution State (U0)
// ============================================================================

export interface ConstitutionState {
  constitution_loaded: boolean;
  immutable_zones: ImmutableZone[];
  pending_approvals: PendingApproval[];
  observation_pool_snapshot: ObservationCandidate[];
  last_updated: string;
}

export interface ImmutableZone {
  zone_id: string;
  description: string;
  protection_level: 'absolute' | 'high' | 'medium' | 'low';
}

export interface PendingApproval {
  id: string;
  candidate_id: string;
  tier: ApprovalTier;
  submitted_at: string;
  expires_at: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  items: string[];
}

// ============================================================================
// Upgrade Demand (U1)
// ============================================================================

export interface UpgradeDemandPool {
  date: string;
  demands: UpgradeDemand[];
}

export interface UpgradeDemand {
  id: string;
  source: 'internal_bottleneck' | 'asset_degradation' | 'external_scout'
         | 'governance_nightly_evolution' | 'governance_doctrine_drift'
         | 'governance_asset_promotion';  // R181 fix: DPBS asset_promotion signal into Upgrade Center
  description: string;
  related_module?: string;
  detected_at: string;
  /** R170 fix: governance_priority routing hint for ConstitutionFilter */
  governance_priority?: 'observation_pool' | 'experiment_pool' | 'deep_analysis_pool' | 'excluded';
  // External scout specific
  project?: string;
  github?: string;
  capability_gain?: string[];
  // Internal bottleneck specific
  bottleneck_data?: Stage2Bottlenecks;
  // Asset degradation specific
  asset_data?: Stage4AssetChanges;
  // Governance backflow specific (Python UEF evolve / drift_check / R165 DPBS asset_promotion)
  governance_data?: {
    outcome_type: string;
    action_type?: string;
    target?: string;
    reason?: string;
    doctrine_id?: string;
    severity?: string;
    // R181 fix: asset_promotion fields — R169 Path B + R165 M07 bind_platform signal
    asset_id?: string;
    asset_name?: string;
    asset_category?: string;
    risk_level?: string;
    decision_id?: string;
    tool_name?: string;
    asset_source?: string;
  };
}

// ============================================================================
// Constitution Filter Result (U2)
// ============================================================================

export type FilterResult = 'excluded' | 'observation_pool' | 'experiment_pool' | 'deep_analysis_pool';

export interface ConstitutionFilterResult {
  date: string;
  results: FilterResultItem[];
  pool_counts: {
    excluded: number;
    observation: number;
    experiment: number;
    deep_analysis: number;
  };
}

export interface FilterResultItem {
  demand_id: string;
  project?: string;
  filter_result: FilterResult;
  reason: string;
  /** U3 LocalMapper reads this to preserve demand_sampler's enriched capability_gain (Round 34 fix) */
  capability_gain?: string[];
}

// ============================================================================
// Local Mapping (U3)
// ============================================================================

export interface LocalMappingReport {
  date: string;
  mappings: LocalMapping[];
}

export interface LocalMapping {
  candidate_id: string;
  target_modules: string[];
  capability_gain: string[];
  integration_type: 'adapter' | 'patch' | 'replace' | 'fork_refactor';
  risk_zone_touches: string[];
  immutable_zone_touches: string[];
  affected_call_chains: string[];
  estimated_token_overhead: number;
  /** R206-B fix: governance_priority propagated from GovernanceFilter.FilterResultItem through U3→U4→U5 */
  governance_priority?: string;
}

// ============================================================================
// Prior Score (U4)
// ============================================================================

export interface PriorScoreResult {
  date: string;
  scores: CandidateScore[];
}

export interface CandidateScore {
  candidate_id: string;
  prior_score: number;
  breakdown: ScoreBreakdown;
  tier: ApprovalTier;
  local_validation_required: boolean;
  /** R206-B fix: governance_priority propagated from LocalMapping through U4→U5 */
  governance_priority?: string;
}

export interface ScoreBreakdown {
  long_term_value: number;      // 0-15
  capability_ceiling: number;   // 0-20
  gap_filling: number;         // 0-15
  engineering_maturity: number; // 0-10
  architecture_compatibility: number; // 0-15
  code_quality: number;         // 0-10
  deployment_control: number;   // 0-5
  risk_complexity: number;     // 0-10 (inverse)
}

export type ApprovalTier = 'T0' | 'T1' | 'T2' | 'T3';

// ============================================================================
// Sandbox Plan (U5)
// ============================================================================

export interface SandboxPlanResult {
  date: string;
  plans: SandboxPlan[];
}

export interface SandboxPlan {
  candidate_id: string;
  deployment_type: 'docker_compose_separate' | 'npm_package' | 'git_clone';
  env_vars_required: string[];
  dependencies: string[];
  verification_script: string;
  rollback_script: string;
  risk_observations: string[];
  can_proceed_to_experiment: boolean;
  /** U4 score breakdown — real scoring data from prior_scorer (Round 7-8) */
  score_breakdown?: ScoreBreakdown;
  /** R34 fix: marks deep_analysis_pool items so U6 bypasses approval and routes to experiment_queue */
  _deepAnalysisItem?: boolean;
  /** R206-B fix: U2 filter_result propagated through U3-U5 pipeline so ReportGenerator can identify observation_pool candidates */
  filter_result?: string;
}

// ============================================================================
// Approval Tiers (U6)
// ============================================================================

export interface ApprovalTierResult {
  date: string;
  candidates: TieredCandidate[];
}

export interface TieredCandidate {
  candidate_id: string;
  project?: string;
  tier: ApprovalTier;
  requires_approval: boolean;
  approval_type?: 'feishu_card' | 'none';
  items_requiring_approval?: string[];
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  backout_plan?: string;
  /** R179: U4 score_breakdown.long_term_value — ROI signal at report layer */
  long_term_value?: number;
  /** R179: Whether candidate can proceed to experiment (U5 canProceedToExperiment output) */
  can_proceed_to_experiment?: boolean;
  /** R179: Tier was upgraded via ROI leniency (ltvBonus=-1 applied in U6) */
  experiment_access_via_roi_leniency?: boolean;
  /** R179: ROI leniency tier adjustment applied (for report visibility) */
  roi_leniency_applied?: boolean;
  /** R179: Full score breakdown for ROI-aware report detail */
  score_breakdown?: ScoreBreakdown;
/** R206-B fix: U2 filter_result propagated from ConstitutionFilter → SandboxPlan → TieredCandidate → ReportGenerator */
  filter_result?: string;
  /**
   * R204-K: PriorScorer predicted_value — conditioned on filter_result (U2 pool分流).
   * - observation_pool → 0.6 (中性不确定，需要观察)
   * - experiment_pool / deep_analysis / bypass → 0.9 (信号充分)
   * - excluded / rejected → 0.3 (信号负面)
   */
  predicted_value?: number;
}

// ============================================================================
// Upgrade Center Report (U7)
// ============================================================================

export interface UpgradeCenterReport {
  date: string;
  run_type: 'full' | 'partial';
  stages_completed: string[];
  summary: {
    demands_scanned: number;
    deep_analysis_pool: number;
    experiment_pool: number;
    observation_pool: number;
    excluded: number;
  };
  candidates_for_approval: TieredCandidate[];
  // R204-E: T1 bypass candidates that go directly to experiment_queue (requires_approval=false)
  experiment_queue_candidates: TieredCandidate[];
  experiment_queue: string[];
  observation_pool: string[];
  // R204-H: Candidates that went to observation_pool (governance_priority=observation_pool intercept)
  observation_pool_candidates: TieredCandidate[];
  pending_approvals: number;
}

// ============================================================================
// Queue & State (U8)
// ============================================================================

export interface UpgradeQueue {
  date: string;
  experiment_tasks: ExperimentTask[];
  pending_verification: string[];
}

export interface ExperimentTask {
  id: string;
  candidate_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  type: 'sandbox_validation';
  created_at: string;
  scheduled_at?: string;
  // R209: script paths for sandbox executor consumption
  // Paths follow sandbox_planner.ts naming: candidate_id with non-alphanumeric → '_'
  verify_script_path?: string;
  rollback_script_path?: string;
  // R227-fix: provenance metadata from pipeline for ground truth segmentation
  filter_result?: string;
  execution_stage?: string;
  predicted?: number;
  tier?: string;
  ltv?: number;
}

export interface ApprovalBacklog {
  date: string;
  pending_approvals: PendingApproval[];
}

export interface CooldownRegistry {
  entries: CooldownEntry[];
}

export interface CooldownEntry {
  candidate_hash: string;
  project: string;
  rejected_at: string;
  cooldown_expires: string;
  reason: string;
}

// ============================================================================
// Baseline Types (for baselines/ refresh)
// ============================================================================

export interface CapabilityTopology {
  nodes: CapabilityNode[];
  edges: CapabilityEdge[];
  last_updated: string;
}

export interface CapabilityNode {
  id: string;
  module: string;
  capability: string;
  level: number;
}

export interface CapabilityEdge {
  from: string;
  to: string;
  weight: number;
}

export interface ModuleTagLibrary {
  modules: ModuleTag[];
  last_updated: string;
}

export interface ModuleTag {
  module_id: string;
  name: string;
  tags: string[];
  language: string;
}

export interface UpgradeMappingIndex {
  mappings: ModuleUpgradeMapping[];
  last_updated: string;
}

export interface ModuleUpgradeMapping {
  external_project: string;
  target_module: string;
  integration_type: 'adapter' | 'patch' | 'replace' | 'fork_refactor';
  confidence: number;
}
