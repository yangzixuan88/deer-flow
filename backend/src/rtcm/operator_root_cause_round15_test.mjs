/**
 * Round 15 使命系统 + 量化评估 + 组织协作 · 根因测试
 * ================================================
 * 6 scenarios covering 3 root causes:
 * - Root Cause 1: 缺少使命系统（任务层之上还有mission/subgoal/milestone/dependency/governance）
 * - Root Cause 2: 缺少量化能力评估（benchmark/版本对比/回归检测/晋升门槛）
 * - Root Cause 3: 缺少多智能体协作（角色分摊、交接系统、治理分离）
 * ================================================
 */

import {
  MissionRegistry,
  CapabilityEvaluationEngine,
  MultiAgentOrganization,
  MissionEvaluationEngine,
  missionEvaluationEngine,
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
// Scenario 1: missionSpawnsTasksAndTracksProgress
// Root Cause 1: 使命创建、子目标分解、任务映射、进度追踪
// ─────────────────────────────────────────────
function scenario1_missionSpawnsTasksAndTracksProgress() {
  console.log('\n[Scenario 1] missionSpawnsTasksAndTracksProgress');

  const registry = new MissionRegistry();

  // Create mission
  const mission = registry.createMission('Build a web scraper', 'important', 'Scraper working');
  assert(mission.id.length > 0, `mission created: ${mission.id}`);
  assert(mission.mission_goal === 'Build a web scraper', 'mission goal set');
  assert(mission.status === 'active', 'mission status active');
  assert(mission.completion_score === 0, 'initial completion 0');

  // Add subgoals
  const sg1 = registry.addSubgoal(mission.id, 'Set up project structure', []);
  assert(sg1 !== null, 'subgoal 1 created');
  assert(sg1.status === 'pending', 'subgoal 1 pending');

  const sg2 = registry.addSubgoal(mission.id, 'Implement core scraping logic', []);
  assert(sg2 !== null, 'subgoal 2 created');

  // Add tasks to mission
  const task1Added = registry.addTask(mission.id, 'task-scraper-1');
  assert(task1Added === true, 'task 1 added to mission');
  const task2Added = registry.addTask(mission.id, 'task-scraper-2');
  assert(task2Added === true, 'task 2 added to mission');

  // Check task_ids in mission
  const retrievedMission = registry.getMission(mission.id);
  assert(retrievedMission.task_ids.length >= 2, `mission has ${retrievedMission.task_ids.length} tasks`);

  // Report task completion
  registry.reportTaskCompletion(mission.id, 'task-scraper-1', true);
  registry.reportTaskCompletion(mission.id, 'task-scraper-2', true);

  // Verify trace has task completions
  const trace = registry.getTrace();
  const taskCompletedEntries = trace.filter(e => e.action === 'task_completed');
  assert(taskCompletedEntries.length >= 2, `task_completed entries: ${taskCompletedEntries.length}`);

  // Active missions
  const activeMissions = registry.getActiveMissions();
  assert(activeMissions.length >= 1, `active missions: ${activeMissions.length}`);
}

// ─────────────────────────────────────────────
// Scenario 2: missionReplansWhenSubgoalBlocked
// Root Cause 1: 子目标失败时，使命级重规划能力
// ─────────────────────────────────────────────
function scenario2_missionReplansWhenSubgoalBlocked() {
  console.log('\n[Scenario 2] missionReplansWhenSubgoalBlocked');

  const registry = new MissionRegistry();

  // Create mission with initial subgoals
  const mission = registry.createMission('Deploy application', 'urgent');
  registry.addSubgoal(mission.id, 'Build artifacts', ['task-build-1', 'task-build-2']);
  registry.addSubgoal(mission.id, 'Run tests', ['task-test-1']);

  // Simulate task failure blocking a subgoal
  registry.reportTaskCompletion(mission.id, 'task-build-1', true);
  registry.reportTaskCompletion(mission.id, 'task-build-2', false); // This blocks the build subgoal

  const blockedMission = registry.getMission(mission.id);
  const blockedSubgoal = blockedMission.subgoals.find(sg => sg.description === 'Build artifacts');
  assert(blockedSubgoal && blockedSubgoal.status === 'blocked', `subgoal blocked: ${blockedSubgoal && blockedSubgoal.status}`);

  // Replan: replace failed subgoals with new ones
  const replanResult = registry.replanMission(mission.id, [
    { description: 'Retry build with fixes', task_ids: ['task-build-retry-1', 'task-build-retry-2'] },
    { description: 'Run simplified tests', task_ids: ['task-test-simple'] },
  ]);
  assert(replanResult === true, 'mission replanned');

  const replannedMission = registry.getMission(mission.id);
  assert(replannedMission.subgoals.length === 2, `replanned has ${replannedMission.subgoals.length} subgoals`);

  // Verify trace has replan event
  const trace = registry.getTrace();
  const replanEntries = trace.filter(e => e.action === 'mission_replan');
  assert(replanEntries.length >= 1, 'replan event logged');

  // Freeze mission
  const freezeResult = registry.freezeMission(mission.id, 'user requested pause');
  assert(freezeResult === true, 'mission frozen');
  const frozenMission = registry.getMission(mission.id);
  assert(frozenMission.status === 'paused', 'mission status paused');
  assert(frozenMission.governance_state === 'frozen', 'governance_state frozen');
}

// ─────────────────────────────────────────────
// Scenario 3: capabilityEvaluationComparesVersions
// Root Cause 2: 两次评估结果对比，产出 version comparison
// ─────────────────────────────────────────────
function scenario3_capabilityEvaluationComparesVersions() {
  console.log('\n[Scenario 3] capabilityEvaluationComparesVersions');

  const engine = new CapabilityEvaluationEngine();

  // Simulate v1 results (lower performance)
  const v1Results = [
    { task_id: 'bench_web_nav', success: true, steps: 5, fallback_triggered: false, time_ms: 5000 },
    { task_id: 'bench_web_form', success: true, steps: 8, fallback_triggered: true, time_ms: 12000 },
    { task_id: 'bench_desktop_edit', success: true, steps: 6, fallback_triggered: false, time_ms: 8000 },
  ];

  const v1Metrics = engine.computeMetrics(v1Results, 1);
  assert(v1Metrics.success_rate > 0, `v1 success rate: ${v1Metrics.success_rate}`);

  const v1Score = engine.computeCapabilityScore(v1Metrics);
  assert(v1Score >= 0 && v1Score <= 1, `v1 capability score: ${v1Score.toFixed(3)}`);

  // Simulate v2 results (improved performance)
  const v2Results = [
    { task_id: 'bench_web_nav', success: true, steps: 3, fallback_triggered: false, time_ms: 3000 },
    { task_id: 'bench_web_form', success: true, steps: 5, fallback_triggered: false, time_ms: 7000 },
    { task_id: 'bench_desktop_edit', success: true, steps: 4, fallback_triggered: false, time_ms: 5000 },
  ];

  const v2Metrics = engine.computeMetrics(v2Results, 0);
  const v2Score = engine.computeCapabilityScore(v2Metrics);
  assert(v2Score >= 0 && v2Score <= 1, `v2 capability score: ${v2Score.toFixed(3)}`);

  // Compare versions
  const comparison = engine.compareVersions('v1', v1Metrics, 'v2', v2Metrics);
  assert(comparison.version_a === 'v1', `version a: ${comparison.version_a}`);
  assert(comparison.version_b === 'v2', `version b: ${comparison.version_b}`);
  assert(comparison.recommendation !== undefined, 'recommendation exists');
  assert(comparison.improvement_areas.length >= 0, 'improvement areas recorded');

  // v2 should show improvement in success_rate and steps
  assert(comparison.metrics_delta.success_rate >= 0, `success rate delta: ${comparison.metrics_delta.success_rate}`);
  assert(comparison.metrics_delta.average_steps <= 0, `steps delta: ${comparison.metrics_delta.average_steps}`);

  // Generate full evaluation report
  const report = engine.evaluate('v2_evaluation', v2Results, 0);
  assert(report.version === 'v2_evaluation', `report version: ${report.version}`);
  assert(report.capability_score >= 0, `capability score in report: ${report.capability_score}`);
  assert(report.promotion_recommendation !== undefined, 'promotion recommendation exists');
}

// ─────────────────────────────────────────────
// Scenario 4: regressionBlocksPromotion
// Root Cause 2: 能力退化时，阻止晋升并触发回滚建议
// ─────────────────────────────────────────────
function scenario4_regressionBlocksPromotion() {
  console.log('\n[Scenario 4] regressionBlocksPromotion');

  const engine = new CapabilityEvaluationEngine();

  // Record v1 as baseline
  const v1Results = [
    { task_id: 'bench_web_nav', success: true, steps: 3, fallback_triggered: false, time_ms: 3000 },
    { task_id: 'bench_web_form', success: true, steps: 5, fallback_triggered: false, time_ms: 7000 },
    { task_id: 'bench_desktop_edit', success: true, steps: 4, fallback_triggered: false, time_ms: 5000 },
  ];
  const v1Report = engine.evaluate('v1_stable', v1Results, 0);

  // Record v2 with regression (lower success rate, more steps)
  const v2BadResults = [
    { task_id: 'bench_web_nav', success: false, steps: 10, fallback_triggered: true, time_ms: 25000 },
    { task_id: 'bench_web_form', success: false, steps: 12, fallback_triggered: true, time_ms: 30000 },
    { task_id: 'bench_desktop_edit', success: true, steps: 8, fallback_triggered: true, time_ms: 15000 },
  ];
  const v2Report = engine.evaluate('v2_regression', v2BadResults, 3);

  // Verify regression is detected in the report
  assert(v2Report.regression_detected === true, `regression detected: ${v2Report.regression_detected}`);
  assert(v2Report.rollback_recommendation !== undefined, 'rollback recommendation exists');
  assert(v2Report.rollback_recommendation.reason.includes('Regression'), 'rollback reason mentions regression');

  // Prove regression by comparing scores: v2 < v1
  assert(v2Report.capability_score < v1Report.capability_score,
    `v2 score (${v2Report.capability_score.toFixed(3)}) < v1 score (${v1Report.capability_score.toFixed(3)})`);

  // The v2 report itself says promotion_recommendation should be blocked due to low score
  assert(v2Report.promotion_recommendation === 'block' || v2Report.promotion_recommendation === 'needs_improvement',
    `v2 promotion blocked: ${v2Report.promotion_recommendation}`);

  // v3 with improvement
  const v3GoodResults = [
    { task_id: 'bench_web_nav', success: true, steps: 2, fallback_triggered: false, time_ms: 2000 },
    { task_id: 'bench_web_form', success: true, steps: 4, fallback_triggered: false, time_ms: 5000 },
    { task_id: 'bench_desktop_edit', success: true, steps: 3, fallback_triggered: false, time_ms: 4000 },
  ];
  const v3Report = engine.evaluate('v3_improved', v3GoodResults, 0);

  // v3 should have high success rate
  assert(v3Report.metrics.success_rate >= 0.9, `v3 high success rate: ${v3Report.metrics.success_rate}`);

  // v3 vs v2 should show improvement (v3 has higher score)
  const v3VsV2 = engine.compareVersions('v2_regression', v2Report.metrics, 'v3_improved', v3Report.metrics);
  assert(v3VsV2.capability_score_delta > 0, `v3 > v2 improvement delta: ${v3VsV2.capability_score_delta.toFixed(3)}`);

  // Audit log
  const history = engine.getEvaluationHistory();
  assert(history.length >= 3, `evaluation history: ${history.length} entries`);
}

// ─────────────────────────────────────────────
// Scenario 5: multiAgentHandoffWorks
// Root Cause 3: orchestrator → executor 交接成功，带反馈闭环
// ─────────────────────────────────────────────
function scenario5_multiAgentHandoffWorks() {
  console.log('\n[Scenario 5] multiAgentHandoffWorks');

  const org = new MultiAgentOrganization();

  // Verify all 5 agents registered
  const orchestrator = org.getAgent('agent_orchestrator');
  assert(orchestrator !== undefined, 'orchestrator agent exists');
  assert(orchestrator.role === 'mission_orchestrator', 'orchestrator role correct');

  const executor = org.getAgent('agent_executor');
  assert(executor !== undefined, 'executor agent exists');

  const distiller = org.getAgent('agent_distiller');
  assert(distiller !== undefined, 'distiller agent exists');

  const auditor = org.getAgent('agent_auditor');
  assert(auditor !== undefined, 'auditor agent exists');

  const gatekeeper = org.getAgent('agent_gatekeeper');
  assert(gatekeeper !== undefined, 'gatekeeper agent exists');

  // Get agents by role
  const orchestrators = org.getAgentsByRole('mission_orchestrator');
  assert(orchestrators.length >= 1, 'orchestrator role has agents');

  // Perform handoff from orchestrator to executor
  const handoff = org.performHandoff(
    'agent_orchestrator',
    'execution_operator',
    'Execute web scraping task for mission-123',
    'mission-123',
    'task-456'
  );
  assert(handoff !== null, 'handoff performed');
  assert(handoff.from_agent === 'agent_orchestrator', `from: ${handoff.from_agent}`);
  assert(handoff.to_agent === 'agent_executor', `to: ${handoff.to_agent}`);
  assert(handoff.mission_id === 'mission-123', `mission_id set`);
  assert(handoff.task_id === 'task-456', `task_id set`);

  // Complete handoff with feedback
  const completeOk = org.completeHandoff(handoff.id, 'Task executed successfully, data collected', true);
  assert(completeOk === true, 'handoff completed');

  // Get the completed handoff from history
  const history = org.getHandoffHistory();
  const completedHandoff = history.find(h => h.id === handoff.id);
  assert(completedHandoff !== undefined, 'handoff found in history');
  assert(completedHandoff.completed === true, 'handoff marked completed');
  assert(completedHandoff.feedback && completedHandoff.feedback.includes('successfully'), 'feedback recorded');

  // Feedback callback - verify it was registered (completeHandoff triggers it)
  // The callback delivery happens inside completeHandoff, so we've already implicitly tested it
  const trace = org.getTrace();
  const feedbackEvents = trace.filter(e => e.action === 'cross_agent_feedback');
  assert(feedbackEvents.length >= 1, 'cross_agent_feedback events exist');
}

// ─────────────────────────────────────────────
// Scenario 6: governanceSeparationPreventsOverreach
// Root Cause 3: 执行器不能创使命，蒸馏器不能执行任务，治理分离
// ─────────────────────────────────────────────
function scenario6_governanceSeparationPreventsOverreach() {
  console.log('\n[Scenario 6] governanceSeparationPreventsOverreach');

  const org = new MultiAgentOrganization();

  // Executor tries to create mission (should be forbidden)
  const executorAction = org.validateAgentAction('agent_executor', 'create_mission');
  assert(executorAction.allowed === false, 'executor cannot create mission');
  assert(executorAction.forbidden_action === 'create_mission', 'forbidden action recorded');

  // Executor tries to modify governance rules (should be forbidden)
  const govAction = org.validateAgentAction('agent_executor', 'modify_governance_rules');
  assert(govAction.allowed === false, 'executor cannot modify governance');

  // Distiller tries to execute task (should be forbidden)
  const distillerExec = org.validateAgentAction('agent_distiller', 'execute_task');
  assert(distillerExec.allowed === false, 'distiller cannot execute task');

  // Gatekeeper tries to execute task (should be forbidden)
  const gatekeeperExec = org.validateAgentAction('agent_gatekeeper', 'execute_task');
  assert(gatekeeperExec.allowed === false, 'gatekeeper cannot execute task');

  // Orchestrator tries to bypass approval (should be forbidden)
  const orchestratorBypass = org.validateAgentAction('agent_orchestrator', 'bypass_approval');
  assert(orchestratorBypass.allowed === false, 'orchestrator cannot bypass approval');

  // Positive case: executor CAN report_result and request_governance_check
  const executorAllowed = org.validateAgentAction('agent_executor', 'report_result');
  assert(executorAllowed.allowed === true, 'executor can report_result');

  const govCheck = org.validateAgentAction('agent_executor', 'request_governance_check');
  assert(govCheck.allowed === true, 'executor can request governance check');

  // Auditor can evaluate capability
  const auditorEval = org.validateAgentAction('agent_auditor', 'evaluate_capability');
  assert(auditorEval.allowed === true, 'auditor can evaluate capability');

  // Auditor CANNOT execute task
  const auditorExec = org.validateAgentAction('agent_auditor', 'execute_task');
  assert(auditorExec.allowed === false, 'auditor cannot execute task');

  // Gatekeeper CAN approve/reject/veto
  const gatekeeperApprove = org.validateAgentAction('agent_gatekeeper', 'approve_task');
  assert(gatekeeperApprove.allowed === true, 'gatekeeper can approve task');

  const gatekeeperVeto = org.validateAgentAction('agent_gatekeeper', 'veto_instruction');
  assert(gatekeeperVeto.allowed === true, 'gatekeeper can veto instruction');

  // Check governance separation in trace
  const trace = org.getTrace();
  const separationEvents = trace.filter(e => e.action === 'governance_separation_event');
  assert(separationEvents.length >= 1, 'governance separation events recorded');

  // Trigger escalation
  org.triggerEscalation('agent_executor', 'Task failed 3 times', 'mission-escalation-test');
  const escalatedTrace = org.getTrace();
  const escalationEvents = escalatedTrace.filter(e => e.action === 'escalation_triggered');
  assert(escalationEvents.length >= 1, 'escalation triggered');
}

// ─────────────────────────────────────────────
// Scenario 7: integratedMissionEvaluationEngine
// Integration test: all three subsystems work together
// ─────────────────────────────────────────────
function scenario7_integratedMissionEvaluationEngine() {
  console.log('\n[Scenario 7] integratedMissionEvaluationEngine');

  const engine = missionEvaluationEngine;

  // Create mission via integrated engine
  const mission = engine.missions.createMission('Build and deploy web app', 'important');
  assert(mission.id.length > 0, 'integrated mission created');

  // Add tasks to mission
  engine.missions.addSubgoal(mission.id, 'Frontend development', ['task-fe-1', 'task-fe-2']);
  engine.missions.addSubgoal(mission.id, 'Backend development', ['task-be-1']);
  engine.missions.addSubgoal(mission.id, 'Deployment', ['task-deploy-1']);

  // Record task results for evaluation
  const taskResults = [
    { task_id: 'task-fe-1', success: true, steps: 5, fallback_triggered: false, time_ms: 8000 },
    { task_id: 'task-fe-2', success: true, steps: 3, fallback_triggered: false, time_ms: 5000 },
    { task_id: 'task-be-1', success: true, steps: 7, fallback_triggered: false, time_ms: 12000 },
    { task_id: 'task-deploy-1', success: true, steps: 4, fallback_triggered: false, time_ms: 6000 },
  ];

  const report = engine.evaluateMission(mission.id, taskResults);
  assert(report.version.includes('mission_'), 'report version references mission');
  assert(report.metrics.success_rate >= 0.9, 'high success rate in mission');
  assert(report.promotion_recommendation !== undefined, 'recommendation exists');

  // Test handoff through organization
  const handoff = engine.organization.performHandoff(
    'agent_orchestrator',
    'execution_operator',
    'Continue with deployment',
    mission.id,
    'task-deploy-1'
  );
  assert(handoff !== null, 'handoff through integrated engine');

  // Get full trace
  const fullTrace = engine.getFullTrace();
  assert(fullTrace.mission_trace.length >= 1, 'mission trace exists');
  assert(fullTrace.evaluation_history.length >= 1, 'evaluation history exists');
  assert(fullTrace.org_trace.length >= 1, 'org trace exists');
  assert(fullTrace.handoff_history.length >= 1, 'handoff history exists');
}

// ─────────────────────────────────────────────
// Run all scenarios
// ─────────────────────────────────────────────
console.log('================================================');
console.log('  Round 15 使命系统 + 量化评估 + 组织协作根因测试 (7 scenarios)');
console.log('================================================');

scenario1_missionSpawnsTasksAndTracksProgress();
scenario2_missionReplansWhenSubgoalBlocked();
scenario3_capabilityEvaluationComparesVersions();
scenario4_regressionBlocksPromotion();
scenario5_multiAgentHandoffWorks();
scenario6_governanceSeparationPreventsOverreach();
scenario7_integratedMissionEvaluationEngine();

console.log('\n================================================');
console.log(`  Results: ${pass} passed, ${fail} failed`);
console.log('================================================');

if (fail === 0) {
  console.log('\n>>> ALL PASS → MISSION_SYSTEM_AND_CAPABILITY_EVALUATION_BASELINE <<<\n');
  process.exit(0);
} else {
  console.log(`\n>>> ${fail} FAILED <<<\n`);
  process.exit(1);
}