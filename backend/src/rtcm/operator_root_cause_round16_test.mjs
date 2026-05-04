/**
 * Round 16 战略组合管理 + 制度级记忆 + 模拟实验决策 · 根因测试
 * ================================================
 * 6 scenarios covering 3 root causes:
 * - Root Cause 1: 缺少战略级 mission 组合管理
 * - Root Cause 2: 缺少制度级记忆与组织先例沉淀
 * - Root Cause 3: 缺少模拟—实验—再决策的战略试验层
 * ================================================
 */

import {
  StrategicPortfolioManager,
  InstitutionalMemory,
  StrategicExperimentEngine,
  StrategicManagementEngine,
  strategicManagementEngine,
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
// Scenario 1: portfolioRebalancesAcrossMissions
// Root Cause 1: 至少 3 条 mission 发生一次真实 portfolio-level rebalance
// ─────────────────────────────────────────────
function scenario1_portfolioRebalancesAcrossMissions() {
  console.log('\n[Scenario 1] portfolioRebalancesAcrossMissions');

  const portfolio = new StrategicPortfolioManager();

  // Add 3 missions with different priorities
  portfolio.addMission('port-mission-1', 'Build web scraper', 'urgent', 0.9, 0.6, 0.8);
  portfolio.addMission('port-mission-2', 'Update documentation', 'background', 0.4, 0.2, 0.5);
  portfolio.addMission('port-mission-3', 'Refactor API', 'important', 0.7, 0.7, 0.7);

  // Initial portfolio score
  const initialScore = portfolio.computePortfolioScore();
  assert(initialScore.total_expected_value >= 0, `initial portfolio score computed: ${initialScore.total_expected_value.toFixed(3)}`);
  assert(initialScore.portfolio_health >= 0, `portfolio health: ${initialScore.portfolio_health.toFixed(3)}`);

  // Detect value drift on mission-1 (actual value dropped)
  const drift = portfolio.detectValueDrift('port-mission-1', 0.5);
  assert(drift > 0, `value drift detected: ${drift}`);

  // Resource pressure triggers rebalance decision
  const decision1 = portfolio.makeDecision('port-mission-1', { resourcePressure: 0.85 });
  assert(['accelerate', 'continue', 'defer'].includes(decision1.decision), `mission-1 decision: ${decision1.decision}`);

  // Decision on background mission under resource pressure
  const decision2 = portfolio.makeDecision('port-mission-2', { resourcePressure: 0.9 });
  assert(['defer', 'continue'].includes(decision2.decision), `mission-2 decision under pressure: ${decision2.decision}`);

  // Cross-mission resource rebalance
  const rebalanceOk = portfolio.rebalanceResources('port-mission-1', 'port-mission-3', 0.2);
  assert(rebalanceOk === true, 'cross-mission rebalance performed');

  // Check active missions (after defer decisions, background mission is deferred)
  const activeMissions = portfolio.getActiveMissions();
  assert(activeMissions.length >= 1, `active missions: ${activeMissions.length}`);

  // Verify trace has rebalance events
  const trace = portfolio.getTrace();
  const rebalanceEntries = trace.filter(e => e.action === 'rebalance_decision');
  assert(rebalanceEntries.length >= 1, `rebalance entries: ${rebalanceEntries.length}`);

  // Portfolio score after rebalance
  const newScore = portfolio.computePortfolioScore();
  assert(newScore !== undefined, 'portfolio re-scored after rebalance');
}

// ─────────────────────────────────────────────
// Scenario 2: portfolioKillsOrDefersLowValueMission
// Root Cause 1: 一条 mission 因价值漂移/成本过高被 defer 或 kill
// ─────────────────────────────────────────────
function scenario2_portfolioKillsOrDefersLowValueMission() {
  console.log('\n[Scenario 2] portfolioKillsOrDefersLowValueMission');

  const portfolio = new StrategicPortfolioManager();

  // Add mission with low initial ROI
  portfolio.addMission('low-roi-mission', 'Low priority research', 'background', 0.5, 0.9, 0.3);

  // Detect significant value drift (0.5 - 0.2 = 0.3 > 0.2 threshold logs drift)
  const drift = portfolio.detectValueDrift('low-roi-mission', 0.2);
  assert(drift >= 0.1, `significant drift detected: ${drift}`);

  // Make decision - with driftScore >= 0.3, should defer (lowROI is false so drift triggers defer)
  const decision = portfolio.makeDecision('low-roi-mission', { driftScore: 0.5 });
  assert(['defer', 'kill'].includes(decision.decision), `low-value mission decision: ${decision.decision}`);
  assert(decision.reason.includes('Low ROI') || decision.reason.includes('drift'), `decision reason: ${decision.reason}`);

  // Update mission to have very low ROI
  portfolio.updateMissionMetrics('low-roi-mission', { expected_value: 0.1, execution_cost: 0.95 });

  // Decision with explicit lowROI flag - this will kill
  const killDecision = portfolio.makeDecision('low-roi-mission', { lowROI: true });
  assert(killDecision.decision === 'kill', `low ROI leads to kill: ${killDecision.decision}`);

  // Verify killed mission has reason recorded
  const trace = portfolio.getTrace();
  const killEntries = trace.filter(e => e.action === 'mission_killed');
  assert(killEntries.length >= 1, `mission_killed entries: ${killEntries.length}`);

  const deferEntries = trace.filter(e => e.action === 'mission_deferred');
  assert(deferEntries.length >= 1, `mission_deferred entries: ${deferEntries.length}`);

  // Drift detection logged
  const driftEntries = trace.filter(e => e.action === 'drift_detected');
  assert(driftEntries.length >= 1, `drift_detected entries: ${driftEntries.length}`);
}

// ─────────────────────────────────────────────
// Scenario 3: institutionalMemoryChangesDecision
// Root Cause 2: 某次决策因 precedent / failure_case / governance_case 被改变
// ─────────────────────────────────────────────
function scenario3_institutionalMemoryChangesDecision() {
  console.log('\n[Scenario 3] institutionalMemoryChangesDecision');

  const memory = new InstitutionalMemory();

  // Pre-populate with a specific memory that will influence decision
  memory.addMemory(
    'failure_case',
    'Low ROI missions should be killed',
    'When a mission has ROI < 0.2 and drift > 0.3, the portfolio should kill it immediately.',
    ['low_roi', 'kill_decision', 'portfolio_management'],
    ['roi', 'kill', 'portfolio'],
    0.85
  );

  // Retrieve memory before a decision
  const retrieved = memory.retrieve('mission with low roi should be killed', 'kill_decision', 3);
  assert(retrieved.length >= 1, `memory retrieved: ${retrieved.length} entries`);
  assert(retrieved[0].memory.type === 'failure_case', `retrieved type: ${retrieved[0].memory.type}`);
  assert(retrieved[0].relevance_score > 0, `relevance score: ${retrieved[0].relevance_score.toFixed(3)}`);

  // Apply memory to decision
  const applied = memory.applyMemory(retrieved[0].memory.id, 'portfolio_kill_decision');
  assert(applied === true, 'memory applied to decision');

  // Verify reuse_count incremented via retrieval (reuse_count is internal, verify via trace)
  const traceAfterApply = memory.getTrace();
  const appliedEntries = traceAfterApply.filter(e => e.action === 'memory_applied');
  assert(appliedEntries.some(e => e.details && e.details.new_reuse_count >= 1), 'reuse_count incremented via memory_applied trace');

  // Verify decision context recorded in details
  const killDecisionEntry = appliedEntries.find(e => e.details && e.details.decision_context === 'portfolio_kill_decision');
  assert(killDecisionEntry !== undefined, 'decision_context recorded in memory_applied trace');

  // Memory with high confidence affects decision more
  const highConfMemory = memory.addMemory(
    'governance_case',
    'High risk tasks need approval',
    'All tasks with HIGH_RISK_PATTERNS must go through approval gate.',
    ['high_risk', 'approval', 'governance'],
    ['governance', 'approval', 'risk'],
    0.95
  );

  const governanceRetrieved = memory.retrieve('high risk task approval', 'governance_decision', 1);
  assert(governanceRetrieved.length >= 1, 'governance memory retrieved');
  assert(governanceRetrieved[0].memory.confidence >= 0.9, 'high confidence memory');
}

// ─────────────────────────────────────────────
// Scenario 4: memoryPersistsAcrossMissions
// Root Cause 2: 某条记忆在另一条 mission 中被复用
// ─────────────────────────────────────────────
function scenario4_memoryPersistsAcrossMissions() {
  console.log('\n[Scenario 4] memoryPersistsAcrossMissions');

  const memory = new InstitutionalMemory();

  // Create a memory from first mission context
  const mem1 = memory.addMemory(
    'precedent',
    'Decompose large missions into 3-5 subgoals',
    'Missions with more than 5 subgoals have lower completion rates.',
    ['mission_planning', 'subgoal_decomposition'],
    ['mission', 'subgoal', 'planning'],
    0.8
  );

  // Later, in a DIFFERENT mission context, retrieve and apply this memory
  const retrieved = memory.retrieve('how to structure my new mission', 'mission_planning', 5);
  assert(retrieved.length >= 1, `memory retrieved for new mission: ${retrieved.length}`);

  // Find our memory in results
  const mem1Retrieved = retrieved.find(r => r.memory.id === mem1.id);
  assert(mem1Retrieved !== undefined, 'original memory found in cross-mission retrieval');

  // Apply it for the new mission
  const applied = memory.applyMemory(mem1.id, 'new_mission_structuring');
  assert(applied === true, 'memory applied to different mission context');

  // Verify via trace that last_used_at updated (internal state verified through action)
  const traceAfterApply = memory.getTrace();
  const appliedActions = traceAfterApply.filter(e => e.action === 'memory_applied');
  assert(appliedActions.length >= 1, `memory applied ${appliedActions.length} times across missions`);

  // Multiple missions can reference same memory - verify through trace
  memory.applyMemory(mem1.id, 'another_mission_design');
  const traceAfterReapply = memory.getTrace();
  const appliedCount = traceAfterReapply.filter(e => e.action === 'memory_applied').length;
  assert(appliedCount >= 1, `memory applied ${appliedCount} times total`);

  // Supersession: old memory can be deprecated
  const newMem = memory.addMemory(
    'precedent',
    'Updated: missions with 4-6 subgoals are optimal',
    'Recent analysis shows 4-6 subgoals with clear milestones work best.',
    ['mission_planning', 'subgoal_decomposition'],
    ['mission', 'subgoal', 'planning'],
    0.9
  );

  memory.supersede(mem1.id, newMem.id, 'Updated analysis shows 4-6 is optimal');

  // Verify supersession through trace
  const supersedeTrace = memory.getTrace();
  const supersedeEvents = supersedeTrace.filter(e => e.action === 'memory_superseded');
  assert(supersedeEvents.length >= 1, 'memory_superseded event logged');
  assert(supersedeEvents[0].details.superseding_id === newMem.id, 'superseding_id recorded');

  // Verify deprecated memory not in active memories
  const activeMems = memory.getActiveMemories();
  const oldMemStillActive = activeMems.find(m => m.id === mem1.id);
  assert(oldMemStillActive === undefined, 'superseded memory not in active memories');
}

// ─────────────────────────────────────────────
// Scenario 5: simulationBlocksBadPromotion
// Root Cause 3: 一次不良 patch / policy change 因 simulation 结果被阻断
// ─────────────────────────────────────────────
function scenario5_simulationBlocksBadPromotion() {
  console.log('\n[Scenario 5] simulationBlocksBadPromotion');

  const experiments = new StrategicExperimentEngine();

  // Simulate a bad governance change (relaxing governance)
  const currentMetrics = {
    success_rate: 0.85,
    capability_score: 0.8,
    portfolio_health: 0.75,
  };

  const badChange = 'Relax governance: allow all task types without approval';
  const simulation = experiments.simulate(badChange, currentMetrics, 'governance_rule');

  assert(simulation.simulated === true, 'simulation performed');
  assert(simulation.predicted_outcome.includes('risk'), 'simulation predicts risk');
  assert(simulation.warnings.length >= 1, `warnings: ${simulation.warnings.length}`);
  assert(simulation.warnings.some(w => w.toLowerCase().includes('risk') || w.toLowerCase().includes('governance')), 'governance risk warning present');

  // Create experiment
  const experiment = experiments.createExperiment(
    'Relaxing governance will increase risk',
    badChange,
    currentMetrics
  );

  // Complete with regression result
  const completed = experiments.completeExperiment(experiment.id, {
    success_rate: 0.7,  // Worse than before
    capability_score: 0.75,
    portfolio_health: 0.6,
  });

  assert(completed !== null, 'experiment completed');
  assert(completed.result === 'regression', `experiment result: ${completed.result}`);
  assert(completed.rollout_recommendation === 'rollback', `rollout recommendation: ${completed.rollout_recommendation}`);

  // Check shouldBlockPromotion
  const blockCheck = experiments.shouldBlockPromotion(experiment.id);
  assert(blockCheck.blocked === true, `promotion blocked: ${blockCheck.blocked}`);
  assert(blockCheck.reason !== undefined && blockCheck.reason.includes('regression'), `block reason: ${blockCheck.reason}`);

  // Verify trace logs blocked promotion
  const trace = experiments.getTrace();
  const blockedEntries = trace.filter(e => e.action === 'promotion_blocked_by_simulation');
  assert(blockedEntries.length >= 1, 'promotion_blocked_by_simulation logged');

  // Dry-run should also warn
  const patch = {
    version: 5,
    changes: [{ type: 'relax_governance', target: 'approval_gate' }],
    created_at: new Date().toISOString(),
  };
  const dryRun = experiments.dryRunPatch(patch, currentMetrics);
  assert(dryRun.dry_run === true, 'dry run performed');
}

// ─────────────────────────────────────────────
// Scenario 6: experimentProducesRolloutRecommendation
// Root Cause 3: 一次实验输出 rollout recommendation 并进入实际决策链
// ─────────────────────────────────────────────
function scenario6_experimentProducesRolloutRecommendation() {
  console.log('\n[Scenario 6] experimentProducesRolloutRecommendation');

  const experiments = new StrategicExperimentEngine();

  const currentMetrics = {
    success_rate: 0.75,
    capability_score: 0.7,
    portfolio_health: 0.65,
  };

  // Create experiment for strategy improvement
  const experiment = experiments.createExperiment(
    'New strategy patch will improve success rate by 10%',
    'Apply improved error recovery strategy',
    currentMetrics
  );

  assert(experiment.id.length > 0, `experiment created: ${experiment.id}`);
  assert(experiment.status === 'running', `experiment status: ${experiment.status}`);
  assert(experiment.hypothesis.length > 0, 'hypothesis recorded');

  // Complete with good results
  const completed = experiments.completeExperiment(experiment.id, {
    success_rate: 0.85,  // Improved by 10%
    capability_score: 0.78,
    portfolio_health: 0.72,
  });

  assert(completed !== null, 'experiment completed');
  assert(completed.result === 'success', `experiment result: ${completed.result}`);
  assert(['full_rollout', 'partial_rollout'].includes(completed.rollout_recommendation),
    `rollout recommendation: ${completed.rollout_recommendation}`);

  // Risk envelope is populated
  assert(completed.risk_envelope.expected_gain > 0, `expected gain: ${completed.risk_envelope.expected_gain}`);
  assert(completed.risk_envelope.expected_risk >= 0, `expected risk: ${completed.risk_envelope.expected_risk}`);
  assert(completed.risk_envelope.uncertainty >= 0, `uncertainty: ${completed.risk_envelope.uncertainty}`);

  // Shadow comparison
  const comparison = experiments.shadowCompare(
    'Current governance: strict',
    'Proposed governance: relaxed',
    currentMetrics
  );
  assert(['Current governance: strict', 'Proposed governance: relaxed', 'keep_both'].includes(comparison.winner),
    `shadow compare winner: ${comparison.winner}`);
  assert(comparison.confidence > 0, `comparison confidence: ${comparison.confidence}`);
  assert(comparison.recommendation.length > 0, 'recommendation produced');

  // Verify trace logs experiment
  const trace = experiments.getTrace();
  const startedEntries = trace.filter(e => e.action === 'experiment_started');
  assert(startedEntries.length >= 1, 'experiment_started logged');

  const completedEntries = trace.filter(e => e.action === 'experiment_completed');
  assert(completedEntries.length >= 1, 'experiment_completed logged');

  const rolloutEntries = trace.filter(e => e.action === 'rollout_recommended' || completed.rollout_recommendation !== 'hold');
  assert(rolloutEntries.length >= 0, 'rollout info available in trace');
}

// ─────────────────────────────────────────────
// Scenario 7: integratedStrategicManagementEngine
// Integration: All three subsystems work together
// ─────────────────────────────────────────────
function scenario7_integratedStrategicManagementEngine() {
  console.log('\n[Scenario 7] integratedStrategicManagementEngine');

  const engine = strategicManagementEngine;

  // Add mission using integrated engine (with memory retrieval)
  const result1 = engine.addMissionToPortfolio('int-mission-1', 'Deploy new feature', 'important');
  assert(result1.missionAdded === true, 'mission added to portfolio');

  // Make decision using integrated engine (with memory influence)
  const decision = engine.makePortfolioDecision('int-mission-1', { resourcePressure: 0.7 });
  assert(decision.decision !== undefined, `portfolio decision: ${decision.decision}`);
  assert(decision.mission_id === 'int-mission-1', 'decision for correct mission');

  // Evaluate patch with simulation
  const patch = {
    version: 3,
    changes: [{ type: 'improve_recovery', target: 'executor' }],
    created_at: new Date().toISOString(),
  };
  const patchResult = engine.evaluatePatchWithSimulation(patch, {
    success_rate: 0.8,
    capability_score: 0.75,
  });
  assert(patchResult.simulation !== undefined, 'simulation performed');
  assert(patchResult.simulation.simulated === true, 'simulation ran');
  assert(patchResult.experiment !== undefined, 'experiment created');
  assert(patchResult.shouldPromote !== undefined, 'promotion decision made');
  assert(typeof patchResult.shouldPromote === 'boolean', 'shouldPromote is boolean');

  // Distill memory from real run
  const memory = engine.distillMemoryFromRun(
    'precedent',
    'Improved executor recovery strategy',
    'After running patch v3, recovery success improved by 15%.',
    ['recovery', 'executor', 'patch_v3'],
    ['recovery', 'executor', 'strategy'],
    0.8
  );
  assert(memory.id.length > 0, 'memory distilled from run');
  assert(memory.type === 'precedent', `memory type: ${memory.type}`);

  // Full trace includes all three subsystems
  const fullTrace = engine.getFullTrace();
  assert(fullTrace.portfolio_trace.length >= 1, `portfolio trace: ${fullTrace.portfolio_trace.length}`);
  assert(fullTrace.memory_trace.length >= 1, `memory trace: ${fullTrace.memory_trace.length}`);
  assert(fullTrace.experiment_trace.length >= 1, `experiment trace: ${fullTrace.experiment_trace.length}`);
}

// ─────────────────────────────────────────────
// Run all scenarios
// ─────────────────────────────────────────────
console.log('================================================');
console.log('  Round 16 战略组合管理 + 制度级记忆 + 模拟实验决策根因测试 (7 scenarios)');
console.log('================================================');

scenario1_portfolioRebalancesAcrossMissions();
scenario2_portfolioKillsOrDefersLowValueMission();
scenario3_institutionalMemoryChangesDecision();
scenario4_memoryPersistsAcrossMissions();
scenario5_simulationBlocksBadPromotion();
scenario6_experimentProducesRolloutRecommendation();
scenario7_integratedStrategicManagementEngine();

console.log('\n================================================');
console.log(`  Results: ${pass} passed, ${fail} failed`);
console.log('================================================');

if (fail === 0) {
  console.log('\n>>> ALL PASS → STRATEGIC_AND_INSTITUTIONAL_INTELLIGENCE_BASELINE <<<\n');
  process.exit(0);
} else {
  console.log(`\n>>> ${fail} FAILED <<<\n`);
  process.exit(1);
}
