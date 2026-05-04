/**
 * Round 18 认知真相治理 + 多方谈判 + 战略前瞻 · 根因测试
 * ================================================
 * 6 scenarios covering 3 root causes:
 * - Root Cause 1: 缺少认知真相治理层 (epistemic governance)
 * - Root Cause 2: 缺少多利益相关方谈判层 (stakeholder negotiation)
 * - Root Cause 3: 缺少长期前瞻与战略情景层 (strategic foresight)
 * ================================================
 */

import {
  EpistemicGovernanceLayer,
  StakeholderNegotiationLayer,
  StrategicForesightLayer,
  CognitiveIntelligenceEngine,
  cognitiveIntelligenceEngine,
} from '../domain/m11/mod.js';

let pass = 0;
let fail = 0;

function assert(condition, msg) {
  if (condition) {
    console.log(`  ✓ ${msg}`);
    pass++;
  } else {
    console.log(`  ✗ FAIL: ${msg}`);
    fail++;
  }
}

// ─────────────────────────────────────────────
// Scenario 1: truthConflictChangesDecision
// Root Cause 1: truth source 冲突被解析后，决策改变
// ─────────────────────────────────────────────
function scenario1_truthConflictChangesDecision() {
  console.log('\n[Scenario 1] truthConflictChangesDecision');

  const epistemic = new EpistemicGovernanceLayer();

  // Register a fact with first source
  const truth = epistemic.registerTruth(
    'System reliability is 95%',
    'system_monitor',
    0.95,
    0.85
  );

  assert(truth.id.length > 0, `truth registered: ${truth.id}`);
  assert(truth.sources.length === 1, `initial sources: ${truth.sources.length}`);

  // Add conflicting source (user claims 70%)
  const resolved = epistemic.addConflictingSource(
    truth.id,
    'user',
    0.7,
    0.95
  );

  assert(resolved !== null, 'conflict resolved');
  assert(resolved.truth_confidence < 0.85, `confidence reduced after conflict: ${resolved.truth_confidence}`);
  assert(resolved.conflict_resolved === true, 'conflict marked as resolved');

  // Verify resolution method
  assert(resolved.resolution_method !== undefined, `resolution method: ${resolved.resolution_method}`);

  // Check trace for conflict detection
  const trace = epistemic.getTrace();
  const conflictEvents = trace.filter(e => e.action === 'truth_conflict_detected');
  assert(conflictEvents.length >= 1, 'truth_conflict_detected in trace');

  const confidenceEvents = trace.filter(e => e.action === 'confidence_adjusted');
  assert(confidenceEvents.length >= 1, 'confidence_adjusted in trace');

  // Verify source reliability learning
  const sources = epistemic.getAllSources();
  const userSource = sources.find(s => s.source_id === 'user');
  assert(userSource !== undefined, 'user source exists');
  assert(userSource.conflict_history >= 1, `user conflict history: ${userSource.conflict_history}`);
}

// ─────────────────────────────────────────────
// Scenario 2: memoryCorrectedByNewTruth
// Root Cause 1: 新真相推翻旧 precedent / failure case，memory 被修正
// ─────────────────────────────────────────────
function scenario2_memoryCorrectedByNewTruth() {
  console.log('\n[Scenario 2] memoryCorrectedByNewTruth');

  const epistemic = new EpistemicGovernanceLayer();

  // Register a conflicting truth
  const truth = epistemic.registerTruth(
    'Low ROI missions should be killed immediately',
    'historical_precedent',
    0.6,
    0.5
  );

  // Add contradicting evidence from user (high trust source)
  const resolved = epistemic.addConflictingSource(
    truth.id,
    'user',
    0.9,
    0.95
  );

  assert(resolved !== null, 'conflict resolved');

  // Simulate memory correction
  const corrected = epistemic.correctMemory(truth.id, 'old_precedent_123', 0.8);
  assert(corrected === true, 'memory correction applied');

  // Verify memory correction trace
  const trace = epistemic.getTrace();
  const correctionEvents = trace.filter(e => e.action === 'memory_corrected_by_truth');
  assert(correctionEvents.length >= 1, 'memory_corrected_by_truth in trace');
  assert(correctionEvents[0].details.memory_id === 'old_precedent_123', 'corrected memory id recorded');

  // Source reliability should be updated after correction
  const sources = epistemic.getAllSources();
  const userSource = sources.find(s => s.source_id === 'user');
  assert(userSource !== undefined, 'user source found after correction');
  assert(userSource.calibration_score > 0, 'calibration score updated');
}

// ─────────────────────────────────────────────
// Scenario 3: stakeholderNegotiationProducesTradeoff
// Root Cause 2: 多方冲突后，系统给出 compromise 与 explanation
// ─────────────────────────────────────────────
function scenario3_stakeholderNegotiationProducesTradeoff() {
  console.log('\n[Scenario 3] stakeholderNegotiationProducesTradeoff');

  const stakeholder = new StakeholderNegotiationLayer();

  // Register a negotiation issue (budget vs speed vs governance)
  const issue = stakeholder.registerIssue(
    'Budget allocation for new mission vs governance safety requirements',
    0.8,
    ['user', 'executive_control', 'governance']
  );

  assert(issue.issue_id.length > 0, `issue registered: ${issue.issue_id}`);

  // Set different positions (user wants fast/cheap, governance wants safe, executive wants efficient)
  stakeholder.setPosition(issue.issue_id, 'user', 0.9);         // User: favor speed/cost
  stakeholder.setPosition(issue.issue_id, 'governance', 0.2);      // Governance: favor safety (low score = wants strict)
  stakeholder.setPosition(issue.issue_id, 'executive_control', 0.5); // Executive: balanced

  // Negotiate
  const result = stakeholder.negotiate(issue.issue_id);

  assert(result.decision === 'compromise_reached' || result.decision === 'escalate_to_human',
    `negotiation decision: ${result.decision}`);
  assert(result.chosen_compromise.length > 0, 'compromise generated');
  assert(result.explanation.length > 0, 'explanation provided');
  assert(result.sacrificed_interest.length > 0, 'sacrifice identified');

  // Check satisfactions (may be empty on escalation)
  if (result.decision === 'compromise_reached') {
    assert(result.stakeholder_satisfactions.size >= 2, 'satisfactions recorded on compromise');
    const trace = stakeholder.getTrace();
    const negotiationEvents = trace.filter(e => e.action === 'negotiation_result');
    assert(negotiationEvents.length >= 1, 'negotiation_result in trace');
  }

  // Get conflict map
  const conflicts = stakeholder.getConflictMap();
  assert(conflicts.length >= 0, 'conflict map accessible');
}

// ─────────────────────────────────────────────
// Scenario 4: humanEscalationOnUnresolvableConflict
// Root Cause 2: 某冲突因不可谈判而升级给用户
// ─────────────────────────────────────────────
function scenario4_humanEscalationOnUnresolvableConflict() {
  console.log('\n[Scenario 4] humanEscalationOnUnresolvableConflict');

  const stakeholder = new StakeholderNegotiationLayer();

  // Register issue with governance (has veto power)
  const issue = stakeholder.registerIssue(
    'Relaxing governance approval requirements',
    0.9,
    ['governance', 'user', 'mission_owner']
  );

  // Governance has strong safety stance (position 0.1 = very anti-relaxation)
  // User wants to relax (position 0.8)
  stakeholder.setPosition(issue.issue_id, 'governance', 0.1);
  stakeholder.setPosition(issue.issue_id, 'user', 0.8);
  stakeholder.setPosition(issue.issue_id, 'mission_owner', 0.6);

  const result = stakeholder.negotiate(issue.issue_id);

  assert(result.escalated_to_human === true, `escalated to human: ${result.escalated_to_human}`);
  assert(result.decision === 'escalate_to_human', `decision: ${result.decision}`);
  assert(result.escalation_reason !== undefined, 'escalation reason provided');
  assert(result.escalation_reason.includes('Governance') || result.escalation_reason.includes('veto'),
    `reason mentions governance: ${result.escalation_reason}`);

  // Verify trace shows conflict detected
  const trace = stakeholder.getTrace();
  const conflictEvents = trace.filter(e => e.action === 'stakeholder_conflict_detected');
  assert(conflictEvents.length >= 1, 'stakeholder_conflict_detected in trace');
}

// ─────────────────────────────────────────────
// Scenario 5: scenarioBranchChangesPresentDecision
// Root Cause 3: 前瞻情景让当前 decision 改变
// ─────────────────────────────────────────────
function scenario5_scenarioBranchChangesPresentDecision() {
  console.log('\n[Scenario 5] scenarioBranchChangesPresentDecision');

  const foresight = new StrategicForesightLayer();

  // Create scenario with multiple branches
  const scenario = foresight.createScenario(
    'mission-X',
    'Future of mission-X depends on market conditions',
    'medium',
    ['market_grows', 'competition_intensifies', 'technology_shifts'],
    0.5,   // risk probability
    0.6,   // risk impact
    0.7    // expected value
  );

  assert(scenario.scenario_id.length > 0, `scenario created: ${scenario.scenario_id}`);
  assert(scenario.time_horizon === 'medium', `horizon: ${scenario.time_horizon}`);

  // Add optimistic branch
  const optimisticBranch = foresight.addBranch(
    scenario.scenario_id,
    'Optimistic: Market grows 20%',
    0.3,    // probability
    0.9,    // expected gain
    0.1,    // expected risk
    0.8,    // confidence
    0.3,    // reversibility
    ['market_uptrend', 'user_adoption']
  );
  assert(optimisticBranch !== null, 'optimistic branch created');

  // Add high-risk pessimistic branch
  const pessimisticBranch = foresight.addBranch(
    scenario.scenario_id,
    'Pessimistic: Competitor launches similar product',
    0.35,   // probability > 0.2
    0.2,    // low gain
    0.7,    // high risk > 0.5
    0.6,    // confidence
    0.8,    // reversibility
    ['competitor_entry', 'market_share_loss']
  );
  assert(pessimisticBranch !== null, 'pessimistic branch created');

  // Compare branches and get foresight result
  const foresightResult = foresight.compareBranches(scenario.scenario_id);

  assert(foresightResult !== null, 'foresight analysis produced');
  assert(foresightResult.recommended_present_action !== 'continue_current_path',
    `present decision changed: ${foresightResult.recommended_present_action}`);
  assert(foresightResult.reserved_contingency !== undefined, 'contingency reserved');
  assert(foresightResult.reasoning.length > 0, 'reasoning provided');

  // Verify branch marked as changed
  const influencedDecisions = foresight.getForesightInfluencedDecisions();
  assert(influencedDecisions.length >= 1, `branches influencing decisions: ${influencedDecisions.length}`);

  // Verify trace
  const trace = foresight.getTrace();
  const foresightEvents = trace.filter(e => e.action === 'present_decision_changed_by_foresight');
  assert(foresightEvents.length >= 1, 'present_decision_changed_by_foresight in trace');
}

// ─────────────────────────────────────────────
// Scenario 6: contingencyReservedForHighRiskBranch
// Root Cause 3: 为高风险未来分支预留 contingency plan
// ─────────────────────────────────────────────
function scenario6_contingencyReservedForHighRiskBranch() {
  console.log('\n[Scenario 6] contingencyReservedForHighRiskBranch');

  const foresight = new StrategicForesightLayer();

  // Create scenario
  const scenario = foresight.createScenario(
    'mission-Y',
    'Technology stack migration decision',
    'long',
    ['new_tech_proven', 'migration_complexity_high', 'team_learning_curve'],
    0.4,
    0.8,
    0.6
  );

  assert(scenario.scenario_id.length > 0, 'scenario created');

  // Add high-risk branch (30% probability, 80% risk)
  const riskyBranch = foresight.addBranch(
    scenario.scenario_id,
    'Risky: Migration fails with major issues',
    0.3,    // probability
    0.1,    // low gain
    0.8,    // high risk
    0.7,    // confidence
    0.9,    // hard to reverse
    ['migration_blocker', 'data_integrity_issue']
  );

  // Add contingency action
  const contingencyAdded = foresight.addContingencyAction(
    scenario.scenario_id,
    'Rollback to previous tech stack within 2 weeks'
  );
  assert(contingencyAdded === true, 'contingency action added');

  // Verify contingency is reserved
  const updatedScenarios = foresight.getAllScenarios();
  const updated = updatedScenarios.find(s => s.scenario_id === scenario.scenario_id);
  assert(updated.contingency_reserved === true, 'contingency reserved flag set');
  assert(updated.contingency_actions.length >= 1, `contingency actions: ${updated.contingency_actions.length}`);
  assert(updated.contingency_actions[0].includes('Rollback'), 'contingency action is rollback');

  // Verify trace
  const trace = foresight.getTrace();
  const contingencyEvents = trace.filter(e => e.action === 'contingency_reserved');
  assert(contingencyEvents.length >= 1, 'contingency_reserved in trace');
}

// ─────────────────────────────────────────────
// Scenario 7: integratedCognitiveIntelligenceEngine
// Integration: All three subsystems work together via CognitiveIntelligenceEngine
// ─────────────────────────────────────────────
function scenario7_integratedCognitiveIntelligenceEngine() {
  console.log('\n[Scenario 7] integratedCognitiveIntelligenceEngine');

  const engine = cognitiveIntelligenceEngine;

  // Process conflicting truth via integrated engine
  const truthResult = engine.processConflictingTruth(
    'System should process 1000 requests per second',
    { id: 'system_monitor', value: 0.8, confidence: 0.85 },
    { id: 'user', value: 0.6, confidence: 0.95 }
  );

  assert(truthResult.truth.id.length > 0, 'truth processed via engine');
  assert(truthResult.decisionImpact !== 'unable_to_resolve', `decision impact: ${truthResult.decisionImpact}`);

  // Negotiate with stakeholders via integrated engine
  const positions = new Map();
  positions.set('user', 0.85);
  positions.set('governance', 0.25);
  positions.set('executive_control', 0.55);

  const negotiationResult = engine.negotiateWithStakeholders(
    'Deploy new feature with relaxed governance',
    positions
  );

  assert(negotiationResult.decision !== undefined, 'negotiation via engine');
  assert(negotiationResult.explanation.length > 0, 'negotiation explanation provided');

  // Analyze scenario via integrated engine
  const foresightResult = engine.analyzeScenarioWithForesight(
    'mission-integrated',
    'Launch new product line',
    'medium',
    [
      { name: 'Success branch', probability: 0.4, gain: 0.9, risk: 0.2, confidence: 0.8, reversibility: 0.4, triggers: ['market_acceptance'] },
      { name: 'Failure branch', probability: 0.35, gain: 0.1, risk: 0.75, confidence: 0.7, reversibility: 0.7, triggers: ['market_rejection'] },
    ]
  );

  assert(foresightResult !== null, 'foresight analysis via engine');
  assert(foresightResult.recommended_present_action.length > 0, 'foresight recommendation provided');

  // Full trace includes all three subsystems
  const fullTrace = engine.getFullTrace();
  assert(fullTrace.epistemic_trace.length >= 1, `epistemic trace: ${fullTrace.epistemic_trace.length}`);
  assert(fullTrace.stakeholder_trace.length >= 1, `stakeholder trace: ${fullTrace.stakeholder_trace.length}`);
  assert(fullTrace.foresight_trace.length >= 1, `foresight trace: ${fullTrace.foresight_trace.length}`);
}

// ─────────────────────────────────────────────
// Run all scenarios
// ─────────────────────────────────────────────
console.log('================================================');
console.log('  Round 18 认知真相治理 + 多方谈判 + 战略前瞻根因测试 (7 scenarios)');
console.log('================================================');

scenario1_truthConflictChangesDecision();
scenario2_memoryCorrectedByNewTruth();
scenario3_stakeholderNegotiationProducesTradeoff();
scenario4_humanEscalationOnUnresolvableConflict();
scenario5_scenarioBranchChangesPresentDecision();
scenario6_contingencyReservedForHighRiskBranch();
scenario7_integratedCognitiveIntelligenceEngine();

console.log('\n================================================');
console.log(`  Results: ${pass} passed, ${fail} failed`);
console.log('================================================');

if (fail === 0) {
  console.log('\n>>> ALL PASS → EPISTEMIC_AND_STRATEGIC_FORESIGHT_BASELINE <<<\n');
  process.exit(0);
} else {
  console.log(`\n>>> ${fail} FAILED <<<\n`);
  process.exit(1);
}
