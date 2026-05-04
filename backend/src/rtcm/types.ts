/**
 * @file types.ts
 * @description RTCM 共享类型定义
 * 圆桌讨论机制的核心类型
 */

// ============================================================================
// 角色定义
// ============================================================================

export interface Role {
  id: string;
  name: string;
  title: string;
  role_type: 'chair' | 'supervisor' | 'member';
  identity: string;
  mission: string;
  core_responsibilities: string[];
  non_responsibilities: string[];
  personality: {
    temperament: string;
    tone: string;
    decision_style: string;
    conflict_style: string;
  };
  default_bias: string;
  debate_functions: string[];
  evidence_preferences: string[];
  permissions: {
    speak: boolean;
    propose: boolean;
    challenge: boolean;
    execute: boolean;
    validate: boolean;
    pause?: boolean;
    abort?: boolean;
    rollback?: boolean;
    escalate?: boolean;
    assign_execution_lease?: boolean;
    close_issue?: boolean;
    close_project?: boolean;
  };
}

export interface Agent {
  id: string;
  name: string;
  group: string;
  category: string;
  role_ref: string;
  model_policy: {
    primary: string;
    fallback: string;
  };
  capabilities: string[];
  hooks: string[];
  max_concurrent: number;
  priority: number;
  tool_access_profile?: Record<string, string>;
  signals?: string[];
}

// ============================================================================
// 运行时状态
// ============================================================================

export type SessionStatus =
  | 'init'
  | 'archive_lookup'
  | 'issue_definition'
  | 'debate'
  | 'solution_convergence'
  | 'execution'
  | 'validation'
  | 'reopen'
  | 'user_acceptance'
  | 'archived';

export interface SessionState {
  session_id: string;
  project_id: string;
  project_name: string;
  mode: string;
  status: SessionStatus;
  current_issue_id: string | null;
  current_stage: string;
  current_round: number;
  active_members: string[];
  lease_state: {
    granted: boolean;
    granted_by: string | null;
    granted_at: string | null;
  };
  latest_chair_summary: ChairSummary | null;
  latest_supervisor_check: SupervisorCheck | null;
  user_presence_status: 'present' | 'absent';
  pending_user_acceptance: boolean;
  reopen_flag: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChairSummary {
  round: number;
  current_consensus: string[];
  current_conflicts: string[];
  strongest_support: string;
  strongest_dissent: string;
  unresolved_uncertainties: string[];
  recommended_state_transition: string;
  timestamp: string;
}

export interface SupervisorCheck {
  round: number;
  all_members_present: boolean;
  all_outputs_parseable: boolean;
  critical_claims_have_evidence_refs: boolean;
  dissent_present: boolean;
  uncertainty_present: boolean;
  protocol_violations: string[];
  timestamp: string;
}

// ============================================================================
// 议题与议题卡
// ============================================================================

export interface Issue {
  issue_id: string;
  issue_title: string;
  problem_statement: string;
  why_it_matters: string;
  candidate_hypotheses: Hypothesis[];
  evidence_summary: string;
  challenge_log: string[];
  response_summary: string;
  known_gaps: string[];
  validation_plan_or_result: ValidationPlan | ValidationResult;
  verdict: Verdict | null;
  status: IssueStatus;
  strongest_dissent: string;
  confidence_interval: string;
  unresolved_uncertainties: string[];
  conditions_to_reopen: string[];
  evidence_ledger_refs: string[];
}

export type IssueStatus =
  | 'created'
  | 'problem_defined'
  | 'hypotheses_built'
  | 'evidence_collected'
  | 'solutions_generated'
  | 'challenged'
  | 'responses_recorded'
  | 'gaps_exposed'
  | 'validation_designed'
  | 'validation_executed'
  | 'verdict_emitted'
  | 'resolved'
  | 'reopened'
  | 'aborted';

export interface Hypothesis {
  hypothesis_id: string;
  statement: string;
  owner_role: string;
  why_it_may_hold: string;
  falsification_conditions: string;
}

export type Verdict =
  | 'hypothesis_confirmed'
  | 'partially_confirmed'
  | 'solution_feasible_but_quality_insufficient'
  | 'solution_not_feasible'
  | 'evidence_insufficient';

export interface ValidationPlan {
  type: 'design_only' | 'full_execution';
  plan: string;
}

export interface ValidationResult {
  run_id: string;
  started_at: string;
  ended_at: string;
  executor: string;
  observed_results: string;
  comparison_dimensions: string[];
  acceptance_thresholds: string[];
  pass_fail_summary: string;
  reopen_reason_if_any: string | null;
}

// ============================================================================
// 项目档案
// ============================================================================

export interface ProjectDossier {
  manifest: Manifest;
  issue_graph: IssueGraph;
  evidence_ledger: EvidenceLedgerEntry[];
  issue_cards: Map<string, Issue>;
  validation_runs: ValidationResult[];
}

export interface Manifest {
  project_id: string;
  project_name: string;
  project_slug: string;
  mode: string;
  status: string;
  created_at: string;
  updated_at: string;
  created_by: string;
  chair_agent_id: string;
  member_agent_ids: string[];
  user_goal: string;
  acceptance_status: 'pending' | 'accepted' | 'rejected' | 'needs_revision';
  current_round: number;
  current_issue_id: string | null;
}

export interface IssueGraph {
  project_id: string;
  nodes: IssueGraphNode[];
  edges: IssueGraphEdge[];
}

export interface IssueGraphNode {
  issue_id: string;
  issue_title: string;
  status: IssueStatus;
}

export interface IssueGraphEdge {
  from_issue_id: string;
  to_issue_id: string;
  relationship: string;
}

export interface EvidenceLedgerEntry {
  evidence_id: string;
  source_type: string;
  source_ref: string;
  claim_supported: string;
  confidence: number;
  conflicts_with: string[];
  used_in_issue_ids: string[];
}

// ============================================================================
// Council Log (每轮关键事件记录)
// ============================================================================

export interface CouncilLogEntry {
  entry_id: string;
  timestamp: string;
  round: number;
  stage: string;
  event_type: CouncilLogEventType;
  actor: string;
  details: string;
  blocked_reason?: string;
  regeneration_applied?: boolean;
}

export type CouncilLogEventType =
  | 'session_created'
  | 'issue_created'
  | 'issue_closed'
  | 'issue_started'
  | 'issue_resolved'
  | 'issue_reopened'
  | 'round_started'
  | 'member_output_received'
  | 'chair_summary_published'
  | 'supervisor_check_completed'
  | 'stage_completed'
  | 'stage_blocked'
  | 'regeneration_triggered'
  | 'escalation_triggered'
  | 'pause_triggered'
  | 'lease_granted'
  | 'lease_revoked'
  | 'validation_run_started'
  | 'validation_run_completed'
  | 'brief_report_generated'
  | 'final_report_generated';

export interface CouncilLog {
  project_id: string;
  session_id: string;
  entries: CouncilLogEntry[];
  created_at: string;
  updated_at: string;
}

// ============================================================================
// Brief Report (续会提示)
// ============================================================================

export interface BriefReport {
  report_id: string;
  project_id: string;
  project_name: string;
  generated_at: string;
  last_issue_id: string | null;
  last_stage: string;
  last_round: number;
  key_outcomes: string[];
  pending_issues: PendingIssueSummary[];
  unresolved_dissents: string[];
  open_uncertainties: string[];
  next_recommended_action: string;
  user_acceptance_status: 'pending' | 'accepted' | 'rejected';
}

export interface PendingIssueSummary {
  issue_id: string;
  issue_title: string;
  status: IssueStatus;
  blocking_item: string;
}

// ============================================================================
// Final Report (用户验收报告)
// ============================================================================

export interface FinalReport {
  report_id: string;
  project_id: string;
  project_name: string;
  user_goal: string;
  generated_at: string;
  completed_at: string | null;
  summary: string;
  resolved_issues: ResolvedIssueSummary[];
  unresolved_issues: PendingIssueSummary[];
  all_dissents_recorded: DissentRecord[];
  all_uncertainties_recorded: UncertaintyRecord[];
  evidence_ledger_summary: EvidenceLedgerSummary;
  acceptance_recommendation: 'accept' | 'reject' | 'needs_revision';
  chair_sign_off: string | null;
  supervisor_sign_off: string | null;
}

export interface ResolvedIssueSummary {
  issue_id: string;
  issue_title: string;
  verdict: Verdict;
  key_reasoning: string;
  dissent_summary: string;
}

export interface DissentRecord {
  issue_id: string;
  dissenter: string;
  dissent_note: string;
}

export interface UncertaintyRecord {
  issue_id: string;
  uncertainty: string;
  impact: string;
}

export interface EvidenceLedgerSummary {
  total_entries: number;
  evidence_by_source: Record<string, number>;
  most_used_evidence: string[];
}

// ============================================================================
// 成员输出
// ============================================================================

export interface MemberOutput {
  role_id: string;
  round: number;
  current_position: string;
  supported_or_opposed_hypotheses: string[];
  strongest_evidence: string;
  largest_vulnerability: string;
  recommended_next_step: string;
  should_enter_validation: boolean;
  confidence_interval: string;
  dissent_note_if_any: string;
  unresolved_uncertainties: string[];
  evidence_ledger_refs: string[];
  timestamp: string;
}

// ============================================================================
// 固定发言顺序
// ============================================================================

export const FIXED_SPEAKING_ORDER: string[] = [
  'rtcm-trend-agent',
  'rtcm-value-agent',
  'rtcm-architecture-agent',
  'rtcm-automation-agent',
  'rtcm-quality-agent',
  'rtcm-efficiency-agent',
  'rtcm-challenger-agent',
  'rtcm-validator-agent',
  'rtcm-chair-agent',
  'rtcm-supervisor-agent',
];

// ============================================================================
// 全局规则
// ============================================================================

export const GLOBAL_HARD_RULES = [
  'every_issue_must_follow_issue_debate_protocol',
  'all_8_members_must_participate_in_every_issue_round',
  'chair_and_supervisor_must_be_present_in_every_issue_round',
  'no_issue_may_skip_counterargument_stage',
  'no_issue_may_skip_validation_or_validation_design_stage',
  'all_critical_claims_must_reference_evidence_ledger_entries',
  'all_final_decisions_must_include_dissent_and_uncertainty_fields',
  'all_execution_actions_must_be_leased_via_chair_or_execution_delegate',
  'supervisor_may_pause_abort_rollback_escalate_any_round',
  'user_intervention_has_priority_over_all_member_preferences',
  'discussion_logs_must_be_archived_into_project_dossier',
];

export const ISSUE_GATES = [
  'definition_gate',
  'evidence_gate',
  'challenge_gate',
  'validation_gate',
];

// ============================================================================
// 阶段定义
// ============================================================================

export const MANDATORY_STAGES = [
  'problem_statement',
  'hypothesis_building',
  'evidence_search',
  'solution_generation',
  'counterargument',
  'response',
  'gap_exposure',
  'minimum_validation_design',
  'validation_execution',
  'verdict',
];

// ============================================================================
// 配置文件路径
// ============================================================================

export const RTCM_CONFIG_ROOT = './rtcm/config';
export const RTCM_PROMPTS_ROOT = './rtcm/prompts';
export const RTCM_EXAMPLES_ROOT = './rtcm/examples/ai_manju_project';

export const CONFIG_FILES = {
  roleRegistry: 'role_registry.final.yaml',
  agentRegistry: 'agent_registry.rtcm.final.yaml',
  issueDebateProtocol: 'issue_debate_protocol.final.yaml',
  projectDossierSchema: 'project_dossier_schema.final.yaml',
  promptLoaderSpec: 'prompt_loader_and_assembly_spec.final.yaml',
  runtimeOrchestratorSpec: 'runtime_orchestrator_spec.final.yaml',
  feishuRenderingSpec: 'feishu_rendering_spec.final.yaml',
};
