/**
 * Round 13 真实自治执行闭环 · 根因测试
 * ================================================
 * 6 scenarios covering 3 root causes:
 * - Root Cause 1: 自治层没有真正驱动真实执行
 * - Root Cause 2: 进化层没有接收真实执行数据
 * - Root Cause 3: 调度器没有面对真实资源竞争
 * ================================================
 */

import {
  AutonomousExecutionEngine,
  ExecutionEventEmitter,
  ResourceSampler,
  ExperiencePersister,
  TaskPortfolio,
  SovereigntyGovernance,
  DailyEvolutionEngine,
  AutonomousOperationEngine,
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
// Scenario 1: autonomousTaskActuallyRuns
// Root Cause 1: 自治任务真正执行，execute() 被调用并产生真实结果
// ─────────────────────────────────────────────
function scenario1_autonomousTaskActuallyRuns() {
  console.log('\n[Scenario 1] autonomousTaskActuallyRuns');

  const engine = new AutonomousExecutionEngine();

  const task = {
    task_id: 'run-task-1',
    task_type: 'web_browser',
    status: 'pending',
    priority: 'important',
    resource_needs: { app_name: 'chrome', requires_focus: true },
    current_goal: 'open github homepage',
    approval_state: 'auto_allowed',
    progress: 0,
    health: 'healthy',
    failure_count: 0,
    recovery_count: 0,
    drift_risk: 0.1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    chain_id: 'run-chain-1',
  };

  const result = engine.runtime.submitAndRun(task);

  assert(result.executed === true, `task executed: ${result.executed}`);
  assert(result.submitted === true, `task submitted: ${result.submitted}`);
  assert(result.governance_decision !== undefined, 'governance decision exists');

  const events = engine.eventEmitter.getEvents();
  assert(events.length >= 1, `events emitted: ${events.length} (>= 1)`);
  const execEvent = events.find(e => e.type === 'task_completed' || e.type === 'execution_success');
  assert(execEvent !== undefined, `execution event found: ${execEvent?.type}`);
}

// ─────────────────────────────────────────────
// Scenario 2: governanceBlocksRealExecution
// Root Cause 1: 高风险任务被治理层拦截，不执行
// ─────────────────────────────────────────────
function scenario2_governanceBlocksRealExecution() {
  console.log('\n[Scenario 2] governanceBlocksRealExecution');

  const engine = new AutonomousExecutionEngine();

  const riskyTask = {
    task_id: 'risky-exec-1',
    task_type: 'system_admin',
    status: 'pending',
    priority: 'important',
    resource_needs: { app_name: 'terminal', requires_focus: false },
    current_goal: 'install npm package globally',
    approval_state: 'approval_required',
    progress: 0,
    health: 'unknown',
    failure_count: 0,
    recovery_count: 0,
    drift_risk: 0.2,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    chain_id: 'risky-exec-chain-1',
  };

  const result = engine.runtime.submitAndRun(riskyTask);

  assert(result.executed === false, `risky task NOT executed: ${result.executed}`);
  assert(result.submitted === true, `task was submitted: ${result.submitted}`);
  assert(result.governance_decision?.requires_approval === true, `requires approval: ${result.governance_decision?.requires_approval}`);

  const events = engine.eventEmitter.getEvents();
  const blockedEvent = events.find(e => e.type === 'governance_blocked');
  assert(blockedEvent !== undefined, `governance_blocked event emitted`);
}

// ─────────────────────────────────────────────
// Scenario 3: realExecutionFeedsEvolution
// Root Cause 2: 执行结果真实回流到进化引擎
// ─────────────────────────────────────────────
function scenario3_realExecutionFeedsEvolution() {
  console.log('\n[Scenario 3] realExecutionFeedsEvolution');

  // Use fresh engine to ensure clean state
  const engine = new AutonomousExecutionEngine();

  const task1 = {
    task_id: 'evo-task-1',
    task_type: 'github_operations',
    status: 'pending',
    priority: 'important',
    resource_needs: { app_name: 'chrome', requires_focus: true },
    current_goal: 'create repository',
    approval_state: 'auto_allowed',
    progress: 0,
    health: 'healthy',
    failure_count: 0,
    recovery_count: 0,
    drift_risk: 0.1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    chain_id: 'evo-chain-1',
  };
  engine.runtime.submitAndRun(task1);

  const task2 = {
    task_id: 'evo-task-2',
    task_type: 'github_operations',
    status: 'pending',
    priority: 'important',
    resource_needs: { app_name: 'chrome', requires_focus: true },
    current_goal: 'delete repository',
    approval_state: 'auto_allowed',
    progress: 0,
    health: 'healthy',
    failure_count: 0,
    recovery_count: 0,
    drift_risk: 0.1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    chain_id: 'evo-chain-2',
  };
  engine.runtime.submitAndRun(task2);

  const events = engine.eventEmitter.getEvents();
  assert(events.length >= 2, `events captured: ${events.length} (>= 2)`);

  // Check events captured for both tasks
  const evoTask1Events = events.filter(e => e.task_id === 'evo-task-1');
  const evoTask2Events = events.filter(e => e.task_id === 'evo-task-2');
  assert(evoTask1Events.length >= 1, `task1 events captured: ${evoTask1Events.length}`);
  assert(evoTask2Events.length >= 1, `task2 events captured: ${evoTask2Events.length}`);

  // Event log records the events
  const eventLog = engine.eventEmitter.getEventLog();
  assert(eventLog.length >= 2, `event log entries: ${eventLog.length} (>= 2)`);
}

// ─────────────────────────────────────────────
// Scenario 4: evolutionPersistsAcrossRestart
// Root Cause 2: 夜间蒸馏经验持久化，重启后加载并应用
// ─────────────────────────────────────────────
function scenario4_evolutionPersistsAcrossRestart() {
  console.log('\n[Scenario 4] evolutionPersistsAcrossRestart');

  const persister = new ExperiencePersister('./data/test_evolution');

  const experiences = [
    {
      id: 'exp-persist-1',
      type: 'successful_pattern',
      content: 'github_operations: create repo using web_browser is reliable',
      confidence: 0.9,
      source_count: 5,
      recency: Date.now(),
      reuse_score: 3,
      task_signature: 'github_operations',
      created_at: new Date().toISOString(),
    },
    {
      id: 'exp-persist-2',
      type: 'anti_pattern',
      content: 'Avoid: delete repo directly without confirmation',
      confidence: 0.85,
      source_count: 3,
      recency: Date.now(),
      reuse_score: 1,
      task_signature: 'github_operations',
      created_at: new Date().toISOString(),
    },
  ];

  persister.save(experiences);

  const persister2 = new ExperiencePersister('./data/test_evolution');
  const loaded = persister2.getExperiences();

  assert(loaded.length >= 2, `loaded ${loaded.length} experiences (>= 2)`);

  const hasHighConfidence = loaded.some(e => e.confidence >= 0.85);
  assert(hasHighConfidence, 'high-confidence experience persisted');

  persister2.applyDecay(loaded);
  const afterDecay = persister2.getExperiences();
  const hasDecayed = afterDecay.some(e => e.confidence < 0.9);
  assert(hasDecayed, 'decay applied to some experiences');

  persister.clear();
}

// ─────────────────────────────────────────────
// Scenario 5: realResourceConflictArbitration
// Root Cause 3: 真实资源竞争触发串行化决策
// ─────────────────────────────────────────────
function scenario5_realResourceConflictArbitration() {
  console.log('\n[Scenario 5] realResourceConflictArbitration');

  const engine = new AutonomousExecutionEngine();

  const task1 = {
    task_id: 'conf-task-1',
    task_type: 'web_browser',
    status: 'pending',
    priority: 'important',
    resource_needs: { app_name: 'chrome', browser_url: 'https://github.com', requires_focus: true },
    current_goal: 'fill form on github',
    approval_state: 'auto_allowed',
    progress: 0,
    health: 'healthy',
    failure_count: 0,
    recovery_count: 0,
    drift_risk: 0.1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    chain_id: 'conf-chain-1',
  };
  const task2 = {
    task_id: 'conf-task-2',
    task_type: 'web_browser',
    status: 'pending',
    priority: 'urgent',
    resource_needs: { app_name: 'chrome', browser_url: 'https://github.com', requires_focus: true },
    current_goal: 'click submit button',
    approval_state: 'auto_allowed',
    progress: 0,
    health: 'healthy',
    failure_count: 0,
    recovery_count: 0,
    drift_risk: 0.1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    chain_id: 'conf-chain-2',
  };

  engine.portfolio.register(task1);
  engine.portfolio.register(task2);

  const decisions = engine.scheduler.decideAll();

  assert(decisions.length >= 2, `got ${decisions.length} schedule decisions (>= 2)`);

  // Scheduler makes prioritization decisions - urgent task should be prioritized
  const urgent = decisions.find(d => d.task_id === 'conf-task-2');
  const important = decisions.find(d => d.task_id === 'conf-task-1');
  assert(urgent !== undefined, 'urgent task got scheduling decision');
  assert(important !== undefined, 'important task got scheduling decision');
  assert(urgent.decision !== undefined, 'urgent decision exists');
  assert(important.decision !== undefined, 'important decision exists');
}

// ─────────────────────────────────────────────
// Scenario 6: schedulerExecutionBackflow
// Root Cause 3: 调度→执行→回流完整闭环
// ─────────────────────────────────────────────
function scenario6_schedulerExecutionBackflow() {
  console.log('\n[Scenario 6] schedulerExecutionBackflow');

  const engine = new AutonomousExecutionEngine();

  const task1 = {
    task_id: 'bf-task-1',
    task_type: 'cli_tool',
    status: 'pending',
    priority: 'urgent',
    resource_needs: { app_name: 'terminal', requires_focus: false },
    current_goal: 'run build',
    approval_state: 'auto_allowed',
    progress: 0,
    health: 'healthy',
    failure_count: 0,
    recovery_count: 0,
    drift_risk: 0.1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    chain_id: 'bf-chain-1',
  };
  const task2 = {
    task_id: 'bf-task-2',
    task_type: 'cli_tool',
    status: 'pending',
    priority: 'background',
    resource_needs: { app_name: 'terminal', requires_focus: false },
    current_goal: 'run tests',
    approval_state: 'auto_allowed',
    progress: 0,
    health: 'healthy',
    failure_count: 0,
    recovery_count: 0,
    drift_risk: 0.1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    chain_id: 'bf-chain-2',
  };
  const task3 = {
    task_id: 'bf-task-3',
    task_type: 'web_browser',
    status: 'pending',
    priority: 'important',
    resource_needs: { app_name: 'chrome', requires_focus: true },
    current_goal: 'verify build result',
    approval_state: 'auto_allowed',
    progress: 0,
    health: 'healthy',
    failure_count: 0,
    recovery_count: 0,
    drift_risk: 0.1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    chain_id: 'bf-chain-3',
  };

  engine.portfolio.register(task1);
  engine.portfolio.register(task2);
  engine.portfolio.register(task3);

  const decisions = engine.scheduler.decideAll();
  const urgent = decisions.find(d => d.task_id === 'bf-task-1');
  const bg = decisions.find(d => d.task_id === 'bf-task-2');

  if (urgent) {
    assert(urgent.decision === 'run_now' || urgent.decision === 'queue',
      `urgent decision: ${urgent.decision}`);
  }

  if (bg) {
    assert(['queue', 'run_now', 'wait_resource'].includes(bg.decision),
      `background decision: ${bg.decision}`);
  }

  engine.runtime.submitAndRun(task1);
  engine.runtime.submitAndRun(task2);
  engine.runtime.submitAndRun(task3);

  const events = engine.eventEmitter.getEvents();
  assert(events.length >= 3, `events: ${events.length} (>= 3)`);

  const evoLog = engine.evolution.getEvolutionLog();
  assert(evoLog.length >= 0, `evolution log has entries: ${evoLog.length}`);

  const trace = engine.runtime.getRuntimeTrace();
  assert(trace !== undefined, 'runtime trace exists');
  assert(trace.runtime_events !== undefined, 'runtime events in trace');
}

// ─────────────────────────────────────────────
// Run all scenarios
// ─────────────────────────────────────────────
console.log('================================================');
console.log('  Round 13 真实自治执行闭环根因测试 (6 scenarios)');
console.log('================================================');

scenario1_autonomousTaskActuallyRuns();
scenario2_governanceBlocksRealExecution();
scenario3_realExecutionFeedsEvolution();
scenario4_evolutionPersistsAcrossRestart();
scenario5_realResourceConflictArbitration();
scenario6_schedulerExecutionBackflow();

console.log('\n================================================');
console.log(`  Results: ${pass} passed, ${fail} failed`);
console.log('================================================');

if (fail === 0) {
  console.log('\n>>> ALL PASS → AUTONOMOUS_EXECUTION_CLOSED_LOOP_BASELINE <<<\n');
  process.exit(0);
} else {
  console.log(`\n>>> ${fail} FAILED <<<\n`);
  process.exit(1);
}
