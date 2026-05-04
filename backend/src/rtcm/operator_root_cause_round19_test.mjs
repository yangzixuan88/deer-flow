/**
 * Round 19 身份声誉 + 规范传播 + 长期教义演化 · 根因测试
 * ================================================
 * 6 scenarios covering 3 root causes:
 * - Root Cause 1: 身份与声誉未被追踪 (identity & reputation)
 * - Root Cause 2: 规范/教义未通过实践验证传播 (norm/doctrine propagation)
 * - Root Cause 3: 长期战略规则未随环境演化 (long-horizon doctrine evolution)
 * ================================================
 */

import {
  IdentityReputationLayer,
  NormDoctrinePropagationLayer,
  LongHorizonDoctrineLayer,
  CognitiveDoctrineEngine,
  cognitiveDoctrineEngine,
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
// Scenario 1: reputationAffectsDecisionWeight
// Root Cause 1: 高声誉 source 的决策权重被提升
// ─────────────────────────────────────────────
function scenario1_reputationAffectsDecisionWeight() {
  console.log('\n[Scenario 1] reputationAffectsDecisionWeight');

  const identity = new IdentityReputationLayer();

  // Get default user identity (neutral)
  const userIdentity = identity.getIdentityByLabel('user');

  // Check initial reputation is neutral
  const initialRep = identity.getReputation('user');
  assert(initialRep !== null, 'user reputation exists');
  assert(initialRep.reputation_level === 'neutral', `initial reputation level: ${initialRep.reputation_level}`);

  // Simulate good outcomes to build trust
  identity.recordOutcome('user', 0.9, 0.85);
  identity.recordOutcome('user', 0.8, 0.78);
  identity.recordOutcome('user', 0.85, 0.83);

  const updatedRep = identity.getReputation('user');
  assert(updatedRep !== null, 'updated reputation exists');
  assert(updatedRep.total_decisions >= 3, `decisions recorded: ${updatedRep.total_decisions}`);

  // Check reputation improved above baseline
  assert(updatedRep.trust_score > 0.5, `trust above baseline: ${updatedRep.trust_score}`);

  // Apply decision weight
  const weightedInput = identity.applyDecisionWeight('user', 0.5, 'balanced');
  assert(weightedInput >= 0.5, `weighted input: ${weightedInput}`);

  // Verify trace
  const trace = identity.getTrace();
  const outcomeEvents = trace.filter(e => e.action === 'outcome_recorded');
  assert(outcomeEvents.length >= 3, 'outcome_recorded in trace');
}

// ─────────────────────────────────────────────
// Scenario 2: badActorSuppression
// Root Cause 1: 恶意 source 被抑制，decision weight 归零
// ─────────────────────────────────────────────
function scenario2_badActorSuppression() {
  console.log('\n[Scenario 2] badActorSuppression');

  const identity = new IdentityReputationLayer();

  // Register a bad actor
  const badActorIdentity = identity.registerIdentity('external', 'malicious_agent', { risk_level: 'high' });
  identity.initializeReputation(badActorIdentity.identity_id, 'malicious_agent');

  // Simulate bad outcomes
  identity.recordOutcome('malicious_agent', 0.9, 0.2);
  identity.recordOutcome('malicious_agent', 0.85, 0.15);
  identity.recordOutcome('malicious_agent', 0.8, 0.1);

  // Suppress the bad actor
  const suppressed = identity.suppressBadActor('malicious_agent', 86400000, 'Consistent false predictions detected');
  assert(suppressed === true, 'bad actor suppressed');

  // Verify suppression: decision weight should be 0
  const weightedInput = identity.applyDecisionWeight('malicious_agent', 0.8, 'balanced');
  assert(weightedInput === 0, `suppressed weight: ${weightedInput}`);

  // Verify reputation level is suppressed
  const rep = identity.getReputation('malicious_agent');
  assert(rep !== null, 'suppressed reputation exists');
  assert(rep.reputation_level === 'suppressed', `suppressed level: ${rep.reputation_level}`);
  assert(rep.suppressed_until !== null && rep.suppressed_until > Date.now(), 'suppression timeout set');

  // Verify trace
  const trace = identity.getTrace();
  const suppressEvents = trace.filter(e => e.action === 'bad_actor_suppressed');
  assert(suppressEvents.length >= 1, 'bad_actor_suppressed in trace');
}

// ─────────────────────────────────────────────
// Scenario 3: normPromotedFromCandidate
// Root Cause 2: norm 从 draft -> candidate -> promoted -> active 完整生命周期
// ─────────────────────────────────────────────
function scenario3_normPromotedFromCandidate() {
  console.log('\n[Scenario 3] normPromotedFromCandidate');

  const normLayer = new NormDoctrinePropagationLayer();

  // Register norm in draft status
  const norm = normLayer.registerNorm(
    'verify_before_deploy',
    'user',
    'All deployments must be verified for safety'
  );

  assert(norm !== null, 'norm registered');
  assert(norm.status === 'draft', `initial status: ${norm.status}`);
  assert(norm.confidence < 0.5, `initial confidence: ${norm.confidence}`);

  // Simulate compliance records to build confidence
  normLayer.recordNormCompliance(norm.norm_id, true, { behavior: 'verified' });
  normLayer.recordNormCompliance(norm.norm_id, true, { behavior: 'verified' });
  normLayer.recordNormCompliance(norm.norm_id, true, { behavior: 'verified' });

  // Promote to candidate
  const candidate = normLayer.promoteNorm(norm.norm_id, 'candidate');
  assert(candidate !== null, 'promoted to candidate');
  assert(candidate.status === 'candidate', `candidate status: ${candidate.status}`);
  assert(candidate.confidence >= 0.4, `candidate confidence: ${candidate.confidence}`);

  // Promote to promoted
  const promoted = normLayer.promoteNorm(norm.norm_id, 'promoted');
  assert(promoted !== null, 'promoted');
  assert(promoted.status === 'promoted', `promoted status: ${promoted.status}`);
  assert(promoted.promoted_at !== null, 'promoted_at set');

  // Promote to active
  const active = normLayer.promoteNorm(norm.norm_id, 'active');
  assert(active !== null, 'activated');
  assert(active.status === 'active', `active status: ${active.status}`);
  assert(active.activated_at !== null, 'activated_at set');

  // Verify compliance tracking works
  const compliant = normLayer.checkCompliance(norm.norm_id, 'verify_before_deploy');
  assert(compliant === true, 'compliance check passed');

  // Verify violations are tracked
  const nonCompliant = normLayer.checkCompliance(norm.norm_id, 'skip_verification');
  assert(nonCompliant === false, 'violation detected');

  // Verify trace
  const trace = normLayer.getTrace();
  const promoteEvents = trace.filter(e => e.action.includes('norm_promoted') || e.action.includes('norm_activated'));
  assert(promoteEvents.length >= 3, 'promotion events in trace');

  const violationEvents = trace.filter(e => e.action === 'norm_violated');
  assert(violationEvents.length >= 1, 'norm_violated in trace');
}

// ─────────────────────────────────────────────
// Scenario 4: doctrineDriftDetected
// Root Cause 3: doctrine 的合规率漂移被检测到
// ─────────────────────────────────────────────
function scenario4_doctrineDriftDetected() {
  console.log('\n[Scenario 4] doctrineDriftDetected');

  const doctrineLayer = new LongHorizonDoctrineLayer();

  // Create norm and doctrine
  const normLayer = new NormDoctrinePropagationLayer();
  const norm1 = normLayer.registerNorm('budget_review_required', 'user', 'All budgets require review');
  const norm2 = normLayer.registerNorm('deadline_tracking_required', 'user', 'All deadlines must be tracked');

  // Generate doctrine from norms
  const doctrine = doctrineLayer.generateDoctrineCandidate(
    [norm1.norm_id, norm2.norm_id],
    'Budget and Deadline Governance',
    'Requires budget review and deadline tracking for all missions',
    'directly_influences'
  );

  assert(doctrine !== null, 'doctrine candidate created');
  assert(doctrine.status === 'candidate', `initial status: ${doctrine.status}`);

  // Submit for review
  const reviewing = doctrineLayer.submitForReview(doctrine.doctrine_id);
  assert(reviewing !== null, 'submitted for review');
  assert(reviewing.status === 'reviewing', `reviewing status: ${reviewing.status}`);

  // Accept doctrine
  const accepted = doctrineLayer.acceptDoctrine(doctrine.doctrine_id);
  assert(accepted !== null, 'doctrine accepted');
  assert(accepted.status === 'accepted', `accepted status: ${accepted.status}`);
  assert(accepted.accepted_at !== null, 'accepted_at set');

  // Activate doctrine
  const active = doctrineLayer.activateDoctrine(doctrine.doctrine_id);
  assert(active !== null, 'doctrine activated');
  assert(active.status === 'active', `active status: ${active.status}`);

  // Simulate drift: compliance rate dropped from 0.8 to 0.4
  const driftSignal = doctrineLayer.detectDrift(doctrine.doctrine_id, 0.4, 0.8);

  assert(driftSignal !== null, 'drift detected');
  assert(driftSignal.drift_score > 0.3, `drift score: ${driftSignal.drift_score}`);
  assert(driftSignal.reason.includes('0.4'), 'drift reason mentions actual compliance');

  // Verify doctrine drift status updated
  const updated = doctrineLayer.getDoctrine(doctrine.doctrine_id);
  assert(updated.drift_status !== 'stable', `drift status: ${updated.drift_status}`);

  // Verify trace
  const trace = doctrineLayer.getTrace();
  const driftEvents = trace.filter(e => e.action === 'doctrine_drift_detected');
  assert(driftEvents.length >= 1, 'doctrine_drift_detected in trace');
}

// ─────────────────────────────────────────────
// Scenario 5: doctrineSupersedesOld
// Root Cause 3: 新 doctrine 替代旧 doctrine，继承历史
// ─────────────────────────────────────────────
function scenario5_doctrineSupersedesOld() {
  console.log('\n[Scenario 5] doctrineSupersedesOld');

  const doctrineLayer = new LongHorizonDoctrineLayer();
  const normLayer = new NormDoctrinePropagationLayer();

  // Create a norm to anchor the first doctrine
  const anchorNorm = normLayer.registerNorm('legacy_budget_control', 'user', 'Old budget control approach');

  // Create first doctrine
  const doctrine1 = doctrineLayer.generateDoctrineCandidate(
    [anchorNorm.norm_id],
    'Legacy Budget Control',
    'Old approach to budget control',
    'directly_influences'
  );
  doctrineLayer.submitForReview(doctrine1.doctrine_id);
  doctrineLayer.acceptDoctrine(doctrine1.doctrine_id);
  doctrineLayer.activateDoctrine(doctrine1.doctrine_id);

  assert(doctrine1.status === 'active', 'doctrine1 active');

  // Create new improved doctrine
  const doctrine2 = doctrineLayer.generateDoctrineCandidate(
    doctrine1.norm_ids,
    'Enhanced Budget Control',
    'Improved approach with real-time tracking',
    'directly_influences'
  );
  doctrineLayer.submitForReview(doctrine2.doctrine_id);
  doctrineLayer.acceptDoctrine(doctrine2.doctrine_id, doctrine1.doctrine_id);
  doctrineLayer.activateDoctrine(doctrine2.doctrine_id);

  assert(doctrine2.status === 'active', 'doctrine2 active');
  assert(doctrine2.supersedes_doctrine_id === doctrine1.doctrine_id, 'supersession link set');

  // Verify old doctrine is superseded
  const legacy = doctrineLayer.getDoctrine(doctrine1.doctrine_id);
  assert(legacy.status === 'superseded', `old doctrine superseded: ${legacy.status}`);

  // File a challenge against doctrine2
  const challenged = doctrineLayer.fileChallenge(doctrine2.doctrine_id, 'user', 'Model changed assumptions');
  assert(challenged === true, 'challenge filed');
  assert(doctrine2.challenge_count >= 1, `challenge count: ${doctrine2.challenge_count}`);

  // Verify trace
  const trace = doctrineLayer.getTrace();
  const supersedeEvents = trace.filter(e => e.action === 'doctrine_supersedes_old');
  assert(supersedeEvents.length >= 1, 'doctrine_supersedes_old in trace');

  const challengeEvents = trace.filter(e => e.action === 'doctrine_challenge_filed');
  assert(challengeEvents.length >= 1, 'doctrine_challenge_filed in trace');
}

// ─────────────────────────────────────────────
// Scenario 6: integratedCognitiveDoctrineEngine
// Integration: All three subsystems work together via CognitiveDoctrineEngine
// ─────────────────────────────────────────────
function scenario6_integratedCognitiveDoctrineEngine() {
  console.log('\n[Scenario 6] integratedCognitiveDoctrineEngine');

  const engine = cognitiveDoctrineEngine;

  // Register new identity with reputation
  const { identity, reputation } = engine.registerWithReputation('agent', 'strategic_planner', { role: 'planner' });
  assert(identity !== null, 'identity registered via engine');
  assert(reputation !== null, 'reputation initialized via engine');

  // Record outcomes to build reputation
  engine.processReputationUpdate('strategic_planner', 0.85, 0.82);
  engine.processReputationUpdate('strategic_planner', 0.9, 0.88);

  // Check weighted input improved
  const weighted = engine.getWeightedInput('strategic_planner', 0.5, 'balanced');
  assert(weighted >= 0.5, `weighted input via engine: ${weighted}`);

  // Register norm from observed behavior
  const norm = engine.registerNormFromBehavior(
    'risk_adjusted_deadline',
    'strategic_planner',
    'Deadlines should be adjusted for risk profile'
  );
  assert(norm !== null, 'norm registered via engine');

  // Promote norm
  const promotedNorm = engine.promoteNorm(norm.norm_id);
  assert(promotedNorm !== null, 'norm promoted via engine');

  // Create doctrine from promoted norms
  const doctrine = engine.createDoctrine(
    [norm.norm_id],
    'Risk-Adjusted Planning Doctrine',
    'All plans must account for risk-adjusted timelines'
  );
  assert(doctrine !== null, 'doctrine created via engine');

  // Evolve doctrine to active
  engine.evolveDoctrine(doctrine.doctrine_id); // candidate -> reviewing
  engine.evolveDoctrine(doctrine.doctrine_id); // reviewing -> accepted
  const evolved = engine.evolveDoctrine(doctrine.doctrine_id); // accepted -> active
  assert(evolved !== null, 'doctrine evolved via engine');
  assert(evolved.status === 'active', `evolved status: ${evolved.status}`);

  // Suppress bad actor
  engine.registerWithReputation('external', 'unreliable_source', {});
  const suppressed = engine.suppressBadActor('unreliable_source', 3600000, 'Consistent false predictions');
  assert(suppressed === true, 'bad actor suppressed via engine');

  // Check suppression works
  const suppressedWeight = engine.getWeightedInput('unreliable_source', 0.8, 'balanced');
  assert(suppressedWeight === 0, `suppressed weight: ${suppressedWeight}`);

  // Check drift across doctrines
  const driftSignals = engine.checkDriftAcrossDoctrines();
  assert(Array.isArray(driftSignals), 'drift signals returned');

  // Verify full trace from all subsystems
  const fullTrace = engine.getFullTrace();
  assert(fullTrace.identity_trace.length >= 1, `identity trace: ${fullTrace.identity_trace.length}`);
  assert(fullTrace.norm_trace.length >= 1, `norm trace: ${fullTrace.norm_trace.length}`);
  assert(fullTrace.doctrine_trace.length >= 1, `doctrine trace: ${fullTrace.doctrine_trace.length}`);
}

// ─────────────────────────────────────────────
// Run all scenarios
// ─────────────────────────────────────────────
console.log('================================================');
console.log('  Round 19 身份声誉 + 规范传播 + 长期教义演化根因测试 (6 scenarios)');
console.log('================================================');

scenario1_reputationAffectsDecisionWeight();
scenario2_badActorSuppression();
scenario3_normPromotedFromCandidate();
scenario4_doctrineDriftDetected();
scenario5_doctrineSupersedesOld();
scenario6_integratedCognitiveDoctrineEngine();

console.log('\n================================================');
console.log(`  Results: ${pass} passed, ${fail} failed`);
console.log('================================================');

if (fail === 0) {
  console.log('\n>>> ALL PASS → IDENTITY_AND_DOCTRINE_BASELINE <<<\n');
  process.exit(0);
} else {
  console.log(`\n>>> ${fail} FAILED <<<\n`);
  process.exit(1);
}
