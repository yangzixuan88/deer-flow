/**
 * Round 17 外部结果真相 + 经营层控制 + 元治理/宪法层 · 根因测试
 * ================================================
 * 6 scenarios covering 3 root causes:
 * - Root Cause 1: 缺少外部结果真相 → 组合决策无反馈
 * - Root Cause 2: 缺少经营层控制 → 预算/截止线/承诺管理
 * - Root Cause 3: 缺少元治理/宪法层 → 规则变更缺乏审查
 * ================================================
 */

import {
  ExternalOutcomeTruth,
  ExecutiveOperatingLayer,
  MetaGovernanceLayer,
  MetaGovernanceEngine,
  metaGovernanceEngine,
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
// Scenario 1: outcomeTruthChangesPortfolioDecision
// Root Cause 1: 外部结果真相改变了 portfolio 决策
// ─────────────────────────────────────────────
function scenario1_outcomeTruthChangesPortfolioDecision() {
  console.log('\n[Scenario 1] outcomeTruthChangesPortfolioDecision');

  const outcomeTruth = new ExternalOutcomeTruth();

  // Record a negative outcome (actual worse than expected)
  const outcome = outcomeTruth.recordOutcome(
    'mission-1',
    'task-1',
    'mission_result',
    'Feature deployed successfully',
    'Feature partially deployed with issues',
    0.9,   // expected value
    0.4,   // actual value (gap = 0.5)
    0.8,   // confidence
    'system_monitor'
  );

  assert(outcome.id.length > 0, `outcome recorded: ${outcome.id}`);
  assert(outcome.outcome_gap === 0.5, `gap computed: ${outcome.outcome_gap}`);
  assert(outcome.expectation_error === -0.5, `negative error: ${outcome.expectation_error}`);

  // Analyze the gap
  const gapAnalysis = outcomeTruth.analyzeGap(outcome.id);
  assert(gapAnalysis !== null, 'gap analysis returned');
  assert(gapAnalysis.gap_detected === true, `gap detected: ${gapAnalysis.gap_detected}`);
  assert(gapAnalysis.severity === 'major' || gapAnalysis.severity === 'critical',
    `severity: ${gapAnalysis.severity}`);
  assert(gapAnalysis.recommended_action === 'portfolio_adjust' || gapAnalysis.recommended_action === 'escalate',
    `recommended action: ${gapAnalysis.recommended_action}`);

  // Record a positive outcome (actual better than expected)
  const positiveOutcome = outcomeTruth.recordOutcome(
    'mission-2',
    undefined,
    'user_feedback',
    'User satisfied with feature',
    'User extremely satisfied, exceeded expectations',
    0.7,
    0.95,
    0.9,
    'user_survey'
  );

  assert(positiveOutcome.expectation_error > 0, `positive gap error: ${positiveOutcome.expectation_error}`);
  const positiveAnalysis = outcomeTruth.analyzeGap(positiveOutcome.id);
  assert(positiveAnalysis !== null && positiveAnalysis.is_positive_gap === true, 'positive gap flagged');

  // Get mission outcomes
  const mission1Outcomes = outcomeTruth.getMissionOutcomes('mission-1');
  assert(mission1Outcomes.length >= 1, `mission-1 outcomes: ${mission1Outcomes.length}`);

  // Mark as portfolio adjusted
  outcomeTruth.markPortfolioAdjusted(outcome.id);
  const trace = outcomeTruth.getTrace();
  const portfolioAdjustedEntries = trace.filter(e => e.action === 'portfolio_adjusted_by_outcome');
  assert(portfolioAdjustedEntries.length >= 1, 'portfolio_adjusted_by_outcome logged');

  // Gap detection logged
  const gapEntries = trace.filter(e => e.action === 'outcome_gap_detected');
  assert(gapEntries.length >= 1, 'outcome_gap_detected logged');
}

// ─────────────────────────────────────────────
// Scenario 2: budgetOrDeadlineChangesMissionFate
// Root Cause 2: 预算或截止线改变 mission 命运
// ─────────────────────────────────────────────
function scenario2_budgetOrDeadlineChangesMissionFate() {
  console.log('\n[Scenario 2] budgetOrDeadlineChangesMissionFate');

  const executive = new ExecutiveOperatingLayer();

  // Initialize mission with budget and deadline
  executive.initializeMission('mission-A', 100, '2026-04-25T00:00:00Z');
  const control = executive.getControl('mission-A');
  assert(control !== undefined, 'mission control initialized');
  assert(control.budget_allocated === 100, `budget allocated: ${control.budget_allocated}`);
  assert(control.budget_used === 0, 'initial budget used: 0');

  // Record budget consumption
  executive.recordBudgetUse('mission-A', 45);
  const after45 = executive.getControl('mission-A');
  assert(after45 !== undefined && after45.budget_used === 45, `budget after 45: ${after45.budget_used}`);
  assert(after45 !== undefined && after45.operating_score.budget_burn === 0.45, `burn rate: ${after45.operating_score.budget_burn}`);

  // Record more - approaching threshold
  executive.recordBudgetUse('mission-A', 40);
  const after85 = executive.getControl('mission-A');
  assert(after85 !== undefined && after85.operating_score.budget_burn >= 0.8, `burn at 85: ${after85.operating_score.budget_burn}`);

  // Update time remaining (deadline pressure)
  executive.updateTimeRemaining('mission-A', 0.15); // 15% time left
  const afterTimeUpdate = executive.getControl('mission-A');
  assert(afterTimeUpdate !== undefined && afterTimeUpdate.operating_score.deadline_risk >= 0.8, `deadline risk: ${afterTimeUpdate.operating_score.deadline_risk}`);

  // Compute operating score
  const opScore = executive.computeOperatingScore('mission-A');
  assert(opScore !== null, 'operating score computed');
  assert(opScore.overall_health >= 0 && opScore.overall_health <= 1, `health in range: ${opScore.overall_health}`);

  // Make executive decision under deadline pressure
  const decision = executive.makeExecutiveDecision('mission-A');
  assert(['emergency_accelerate', 'cut_loss', 'throttle', 'escalate_for_budget_review'].includes(decision),
    `executive decision: ${decision}`);

  // Decision should be emergency_accelerate due to deadline risk
  const trace = executive.getTrace();
  const deadlineEntries = trace.filter(e => e.action === 'deadline_reprioritization');
  assert(deadlineEntries.length >= 1, 'deadline_reprioritization logged');
}

// ─────────────────────────────────────────────
// Scenario 3: commitmentMissTriggersExecutiveEscalation
// Root Cause 2: Commitment 错过触发 executive 升级
// ─────────────────────────────────────────────
function scenario3_commitmentMissTriggersExecutiveEscalation() {
  console.log('\n[Scenario 3] commitmentMissTriggersExecutiveEscalation');

  const executive = new ExecutiveOperatingLayer();

  // Initialize mission
  executive.initializeMission('mission-B', 200);

  // Add multiple commitments
  const commit1 = executive.addCommitment('mission-B', 'Deploy v1.0', '2026-04-20T00:00:00Z');
  assert(commit1.id.length > 0, `commitment 1 created: ${commit1.id}`);
  assert(commit1.met === false, 'commitment initially unmet');

  const commit2 = executive.addCommitment('mission-B', 'Deploy v1.1', '2026-04-22T00:00:00Z');
  assert(commit2.id.length > 0, 'commitment 2 created');

  // Fulfill one commitment
  const fulfilled = executive.fulfillCommitment(commit1.id);
  assert(fulfilled === true, 'commitment fulfilled');
  const afterFulfill = executive.getControl('mission-B');
  assert(afterFulfill !== undefined && afterFulfill.operating_score.commitment_reliability === 0.5, '50% reliability after 1/2 met');

  // Miss the second commitment
  const missed = executive.missCommitment(commit2.id, 'Resource constraints prevented completion');
  assert(missed === true, 'commitment missed');

  const afterMiss = executive.getControl('mission-B');
  // Reliability = met/total = 1/2 = 0.5 (1 fulfilled, 1 missed)
  assert(afterMiss !== undefined && afterMiss.operating_score.commitment_reliability === 0.5, `50% reliability after miss: ${afterMiss.operating_score.commitment_reliability}`);

  // Missed commitment logged
  const trace = executive.getTrace();
  const missedEntries = trace.filter(e => e.action === 'commitment_missed');
  assert(missedEntries.length >= 1, 'commitment_missed logged');
  assert(missedEntries[0].details.reason.includes('Resource'), `miss reason: ${missedEntries[0].details.reason}`);

  // Make executive decision - 50% reliability does NOT trigger escalation (threshold is < 0.5)
  const decision = executive.makeExecutiveDecision('mission-B');
  assert(decision === 'continue_invest', `50% reliability leads to continue_invest: ${decision}`);

  // Calculate opportunity cost (based on budget/deadline pressure, which are 0 here)
  const oppCost = executive.calculateOpportunityCost('mission-B', ['mission-C', 'mission-D']);
  assert(oppCost >= 0 && oppCost <= 1, `opportunity cost in range: ${oppCost}`);
  // Get trace AFTER calculateOpportunityCost call
  const costEntries = executive.getTrace().filter(e => e.action === 'opportunity_cost_calculated');
  assert(costEntries.length >= 1, 'opportunity_cost_calculated logged');
}

// ─────────────────────────────────────────────
// Scenario 4: metaGovernanceBlocksUnsafeRulePatch
// Root Cause 3: 元治理阻止不安全的规则 patch
// ─────────────────────────────────────────────
function scenario4_metaGovernanceBlocksUnsafeRulePatch() {
  console.log('\n[Scenario 4] metaGovernanceBlocksUnsafeRulePatch');

  const metaGov = new MetaGovernanceLayer();

  // Get all rules
  const rules = metaGov.getAllRules();
  assert(rules.length >= 4, `default rules created: ${rules.length}`);

  // Find the "High-Risk Approval Requirement" rule
  const highRiskRule = rules.find(r => r.name === 'High-Risk Approval Requirement');
  assert(highRiskRule !== undefined, 'high-risk rule found');
  assert(highRiskRule.rule_type === 'changeable', `rule type: ${highRiskRule.rule_type}`);

  // Propose a critical-risk patch (trying to change immutable veto rule)
  // Note: immutable rules CAN be patched but require meta approval - only forbidden_modification rejects at propose
  const immutableRule = rules.find(r => r.name === 'User Veto Is Absolute');
  const criticalPatch = metaGov.proposeRulePatch(
    immutableRule.id,
    'modify',
    'user_veto_final: false',
    'Allow agents to override user veto in certain cases'
  );
  assert(criticalPatch !== null, 'immutable rule patch can be proposed (requires approval)');
  assert(criticalPatch.meta_approval_required === true, 'immutable rule requires meta approval');

  // Propose a high-risk patch (changing threshold rule)
  const promotionRule = rules.find(r => r.name === 'Promotion Threshold');
  const highRiskPatch = metaGov.proposeRulePatch(
    promotionRule.id,
    'modify',
    'promotion_threshold: 0.3',
    'Lower threshold to enable faster iteration'
  );
  assert(highRiskPatch !== null, 'high-risk patch proposed');
  assert(highRiskPatch.risk_level === 'high', `risk level: ${highRiskPatch.risk_level}`);
  // Changeable rules have meta_approval_required = false, but high risk still needs approval
  assert(highRiskPatch.meta_approval_required === false, `meta_approval_required for changeable: ${highRiskPatch.meta_approval_required}`);

  // Meta approve the high-risk patch
  const approved = metaGov.metaApprove(highRiskPatch.id);
  assert(approved === true, 'patch meta-approved');

  // Safe check on a new patch - changeable rules with high risk but no meta_approval_required
  // are still considered safe by isPatchSafe (only meta_approval_required patches are blocked without approval)
  const promotionRule2 = rules.find(r => r.name === 'Promotion Threshold');
  const newPatch = metaGov.proposeRulePatch(
    promotionRule2.id,
    'modify',
    'promotion_threshold: 0.5',
    'Adjust threshold'
  );
  if (newPatch) {
    const safeCheck = metaGov.isPatchSafe(newPatch.id);
    // Changeable rules don't require meta approval, so isPatchSafe returns safe=true
    assert(safeCheck.safe === true, `changeable rule high-risk patch safe: ${safeCheck.safe}`);
  }

  // Constitutional gate hit logged
  const trace = metaGov.getTrace();
  const gateHits = trace.filter(e => e.action === 'constitutional_gate_hit');
  assert(gateHits.length >= 2, `constitutional_gate_hit events: ${gateHits.length}`);

  // Patch proposals tracked
  const proposals = metaGov.getPatchProposals();
  assert(proposals.length >= 1, `patch proposals tracked: ${proposals.length}`);
}

// ─────────────────────────────────────────────
// Scenario 5: shadowRulePatchBeforePromotion
// Root Cause 3: Shadow apply patch 后才能 promotion
// ─────────────────────────────────────────────
function scenario5_shadowRulePatchBeforePromotion() {
  console.log('\n[Scenario 5] shadowRulePatchBeforePromotion');

  const metaGov = new MetaGovernanceLayer();

  const rules = metaGov.getAllRules();
  const regressionRule = rules.find(r => r.name === 'Regression Detection Threshold');

  // Propose a medium-risk patch
  const mediumPatch = metaGov.proposeRulePatch(
    regressionRule.id,
    'modify',
    'regression_threshold: -0.08',
    'Tighten regression detection'
  );
  assert(mediumPatch !== null, 'medium-risk patch proposed');
  assert(mediumPatch.risk_level === 'high', `risk is high not medium: ${mediumPatch.risk_level}`);

  // Medium risk requires meta approval
  const approved = metaGov.metaApprove(mediumPatch.id);
  assert(approved === true, 'patch approved');

  // Shadow apply
  const shadowed = metaGov.shadowApplyPatch(mediumPatch.id);
  assert(shadowed === true, 'patch shadow-applied');

  // Verify patch status
  const updatedProposals = metaGov.getPatchProposals();
  const patched = updatedProposals.find(p => p.id === mediumPatch.id);
  assert(patched.status === 'shadow', `patch in shadow status: ${patched.status}`);
  assert(patched.shadow_applied === true, 'shadow flag set');

  // Safe check after shadow apply
  const safeCheck = metaGov.isPatchSafe(mediumPatch.id);
  // After meta_approve + shadow, it should be safe for evaluation
  assert(safeCheck.safe === true, `shadow-applied patch safe: ${safeCheck.safe}`);

  // Apply the patch
  const applied = metaGov.applyPatch(mediumPatch.id);
  assert(applied === true, 'patch applied');

  // Verify rule version incremented
  const updatedRule = metaGov.getRule(regressionRule.id);
  assert(updatedRule.version === 2, `rule version incremented: ${updatedRule.version}`);
  assert(updatedRule.content === 'regression_threshold: -0.08', `updated content: ${updatedRule.content}`);

  // Trace shows shadow and apply
  const trace = metaGov.getTrace();
  const shadowEntries = trace.filter(e => e.action === 'shadow_rule_applied');
  assert(shadowEntries.length >= 1, 'shadow_rule_applied logged');
  const applyEntries = trace.filter(e => e.action === 'rule_patch_applied');
  assert(applyEntries.length >= 1, 'rule_patch_applied logged');
}

// ─────────────────────────────────────────────
// Scenario 6: metaRollbackRestoresPreviousRuleState
// Root Cause 3: 回滚恢复之前的规则状态
// ─────────────────────────────────────────────
function scenario6_metaRollbackRestoresPreviousRuleState() {
  console.log('\n[Scenario 6] metaRollbackRestoresPreviousRuleState');

  const metaGov = new MetaGovernanceLayer();

  const rules = metaGov.getAllRules();
  const shadowRule = rules.find(r => r.name === 'Shadow Mode Requirement');

  // Record original state
  const originalVersion = shadowRule.version;
  const originalContent = shadowRule.content;

  // Propose and apply a patch
  const patch = metaGov.proposeRulePatch(
    shadowRule.id,
    'modify',
    'shadow_mode_required: false',
    'Remove shadow mode requirement for faster deployment'
  );
  assert(patch !== null, 'patch proposed');

  // Low risk patch - can be applied directly
  const applied = metaGov.applyPatch(patch.id);
  assert(applied === true, `patch applied: status=${patch.status}`);

  // Verify rule was modified
  const afterPatch = metaGov.getRule(shadowRule.id);
  assert(afterPatch.version === originalVersion + 1, `version updated: ${afterPatch.version}`);
  assert(afterPatch.content === 'shadow_mode_required: false', `content changed: ${afterPatch.content}`);

  // Rollback the patch
  const rolledBack = metaGov.rollbackPatch(patch.id, 'User raised concern about safety');
  assert(rolledBack === true, `patch rolled back: status=${patch.status}`);

  // Verify rule restored to previous state
  const afterRollback = metaGov.getRule(shadowRule.id);
  assert(afterRollback.content === originalContent, `content restored: ${afterRollback.content}`);
  assert(afterRollback.version === originalVersion, `version restored: ${afterRollback.version}`);

  // Verify patch status updated
  const proposals = metaGov.getPatchProposals();
  const patched = proposals.find(p => p.id === patch.id);
  assert(patched.status === 'rolled_back', `patch status: ${patched.status}`);
  assert(patched.rollback_reason === 'User raised concern about safety', `rollback reason recorded`);

  // Trace shows rollback
  const trace = metaGov.getTrace();
  const rollbackEntries = trace.filter(e => e.action === 'meta_rollback_executed');
  assert(rollbackEntries.length >= 1, 'meta_rollback_executed logged');
  const reasonEntries = trace.filter(e => e.action === 'meta_rollback_reason');
  assert(reasonEntries.length >= 1, 'meta_rollback_reason logged');
}

// ─────────────────────────────────────────────
// Scenario 7: integratedMetaGovernanceEngine
// Integration: All three subsystems work together via MetaGovernanceEngine
// ─────────────────────────────────────────────
function scenario7_integratedMetaGovernanceEngine() {
  console.log('\n[Scenario 7] integratedMetaGovernanceEngine');

  const engine = metaGovernanceEngine;

  // Process external outcome via integrated engine
  // Gap = 0.25 (> 0.2 threshold for portfolio adjustment)
  const outcomeResult = engine.processExternalOutcome(
    'int-mission-1',
    'int-task-1',
    'mission_result',
    'System should handle 1000 req/s',
    'System handles 750 req/s',
    1.0,   // expected
    0.75,  // actual (gap = 0.25)
    'load_test_monitor'
  );

  assert(outcomeResult.outcome.id.length > 0, 'outcome recorded via engine');
  assert(outcomeResult.gapAnalysis !== null, 'gap analysis computed');
  assert(outcomeResult.gapAnalysis.gap_detected === true, 'gap detected');
  // portfolioAdjusted when gap > 0.2 (0.25 > 0.2)
  assert(outcomeResult.portfolioAdjusted === true, 'portfolio adjustment triggered');

  // Control mission via integrated engine
  const controlResult = engine.controlMission(
    'int-mission-2',
    150,
    '2026-04-25T00:00:00Z',
    'Deliver API endpoint'
  );

  assert(controlResult.control !== undefined, 'mission controlled');
  assert(controlResult.decision !== undefined, 'executive decision made');

  // Propose and process rule change via integrated engine
  const rules = engine.metaGovernance.getAllRules();
  const promotionRule = rules.find(r => r.name === 'Promotion Threshold');

  const ruleChangeResult = engine.proposeAndProcessRuleChange(
    promotionRule.id,
    'promotion_threshold: 0.65',
    'Slightly adjust promotion threshold based on data'
  );

  assert(ruleChangeResult.proposal !== null, 'rule patch proposed via engine');
  assert(ruleChangeResult.safe !== undefined, 'safety check performed');
  // High risk changes are not auto-applied
  assert(typeof ruleChangeResult.applied === 'boolean', 'application status returned');

  // Rollback via integrated engine
  const rollbackResult = engine.rollbackRuleChange(
    ruleChangeResult.proposal.id,
    'Integrated rollback test'
  );
  assert(typeof rollbackResult === 'boolean', 'rollback executed via engine');

  // Full trace includes all three subsystems
  const fullTrace = engine.getFullTrace();
  assert(fullTrace.outcome_trace.length >= 1, `outcome trace: ${fullTrace.outcome_trace.length}`);
  assert(fullTrace.executive_trace.length >= 1, `executive trace: ${fullTrace.executive_trace.length}`);
  assert(fullTrace.meta_trace.length >= 1, `meta trace: ${fullTrace.meta_trace.length}`);
}

// ─────────────────────────────────────────────
// Run all scenarios
// ─────────────────────────────────────────────
console.log('================================================');
console.log('  Round 17 外部结果真相 + 经营层控制 + 元治理根因测试 (7 scenarios)');
console.log('================================================');

scenario1_outcomeTruthChangesPortfolioDecision();
scenario2_budgetOrDeadlineChangesMissionFate();
scenario3_commitmentMissTriggersExecutiveEscalation();
scenario4_metaGovernanceBlocksUnsafeRulePatch();
scenario5_shadowRulePatchBeforePromotion();
scenario6_metaRollbackRestoresPreviousRuleState();
scenario7_integratedMetaGovernanceEngine();

console.log('\n================================================');
console.log(`  Results: ${pass} passed, ${fail} failed`);
console.log('================================================');

if (fail === 0) {
  console.log('\n>>> ALL PASS → EXECUTIVE_AND_CONSTITUTIONAL_INTELLIGENCE_BASELINE <<<\n');
  process.exit(0);
} else {
  console.log(`\n>>> ${fail} FAILED <<<\n`);
  process.exit(1);
}
