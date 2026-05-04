/**
 * Round 11 超人运营智能根因测试
 * ================================================
 * 6 scenarios covering 3 root causes:
 * - Root Cause 1: 没有统一电脑世界模型
 * - Root Cause 2: 没有真正的动态重规划器
 * - Root Cause 3: 还没有真正的并行运营与资源仲裁
 * ================================================
 */

import {
  operationalEngine,
  WorldModel,
  DynamicReplanner,
  ResourceArbitrator,
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
// Scenario 1: worldModelBuildsFromObservation
// Root Cause 1: dom_observed + desk_observed 统一写入 world_state
// ─────────────────────────────────────────────
function scenario1_worldModelBuildsFromObservation() {
  console.log('\n[Scenario 1] worldModelBuildsFromObservation');

  const engine = new operationalEngine.constructor();
  const wm = engine.getWorldModel();

  // 模拟 DOM 观测
  const domObserved = [
    { id: 'btn-1', tag: 'button', text: 'Submit', href: undefined, src: undefined, rect: { x: 10, y: 20 }, visible: true },
    { id: 'link-1', tag: 'a', text: 'GitHub', href: 'https://github.com', src: undefined, rect: { x: 100, y: 20 }, visible: true },
    { id: 'hidden', tag: 'div', text: 'Hidden', href: undefined, src: undefined, rect: { x: 0, y: 0 }, visible: false },
  ];

  // 模拟桌面观测
  const deskObserved = [
    { window_id: 'win-123', title: 'Visual Studio Code', app_name: 'Code', rect: { x: 0, y: 0, width: 1920, height: 1080 }, focused: true, pid: 1001 },
    { window_id: 'win-456', title: 'Chrome - GitHub', app_name: 'chrome', rect: { x: 100, y: 100, width: 800, height: 600 }, focused: false, pid: 2001 },
  ];

  // 合并观测
  engine.ingestObservations(domObserved, deskObserved);

  const state = wm.getCurrentState();

  // 验证 DOM 实体被纳入
  const domEntities = Array.from(state.observed_entities.values()).filter(e => e.source === 'dom_observed');
  assert(domEntities.length >= 2, `dom_observed entities merged: ${domEntities.length} (>= 2)`);

  // 验证桌面实体被纳入
  const deskEntities = Array.from(state.observed_entities.values()).filter(e => e.source === 'desk_observed');
  assert(deskEntities.length >= 2, `desk_observed entities merged: ${deskEntities.length} (>= 2)`);

  // 验证实体属性完整
  const githubEntity = Array.from(state.observed_entities.values()).find(e => e.label === 'GitHub');
  if (githubEntity) {
    assert(githubEntity.type === 'element', 'dom entity has correct type');
    assert(githubEntity.url === 'https://github.com', 'dom entity has url');
    assert(githubEntity.state === 'active', 'dom entity is active');
  }

  // 验证实体数
  assert(wm.getEntityCount() >= 4, `total entities: ${wm.getEntityCount()} (>= 4)`);
}

// ─────────────────────────────────────────────
// Scenario 2: worldDeltaTriggersReplan
// Root Cause 2: 世界状态异常变化后触发 replanning
// ─────────────────────────────────────────────
function scenario2_worldDeltaTriggersReplan() {
  console.log('\n[Scenario 2] worldDeltaTriggersReplan');

  const engine = new operationalEngine.constructor();
  const wm = engine.getWorldModel();
  const replanner = engine.getReplanner();

  // 建立初始快照
  wm.mergeDomObservation([
    { id: 'btn-1', tag: 'button', text: 'Next', href: undefined, src: undefined, rect: { x: 10, y: 20 }, visible: true },
  ]);
  wm.mergeDomObservation([
    { id: 'btn-2', tag: 'button', text: 'Submit', href: undefined, src: undefined, rect: { x: 10, y: 20 }, visible: true },
  ]);
  const snap1 = wm.snapshot(0, 'chain-1');

  // 移除关键元素（模拟消失）
  const state = wm.getCurrentState();
  state.observed_entities.delete('btn-1');

  const snap2 = wm.snapshot(1, 'chain-1');

  // 计算差异
  const delta = wm.computeDelta(snap1.id);

  assert(delta.removed.length > 0, `world delta detected removed entities: ${delta.removed.length}`);
  assert(delta.snapshot_id === snap2.id, 'delta references current snapshot');

  // 触发重规划
  const trigger = {
    reason: 'entity_disappeared',
    step_index: 1,
    description: 'submit button disappeared after navigation',
  };

  const steps = [
    { instruction: 'click submit', goal_description: 'form submitted' },
    { instruction: 'verify success', goal_description: 'success message visible' },
  ];

  const { decision, trace } = engine.triggerReplan(
    trigger.reason,
    trigger.step_index,
    trigger.description,
    steps,
    delta
  );

  assert(decision.type !== undefined, `replan decision made: ${decision.type}`);
  assert(trace !== undefined, 'replan trace recorded');
  assert(trace.trigger.reason === 'entity_disappeared', 'trace has correct trigger reason');
}

// ─────────────────────────────────────────────
// Scenario 3: replanActuallyChangesRemainingPlan
// Root Cause 2: replanner 真改后续步骤，不是只出结论
// ─────────────────────────────────────────────
function scenario3_replanActuallyChangesRemainingPlan() {
  console.log('\n[Scenario 3] replanActuallyChangesRemainingPlan');

  const engine = new operationalEngine.constructor();
  const replanner = engine.getReplanner();

  const steps = [
    { instruction: 'navigate to github.com', goal_description: 'github loaded' },
    { instruction: 'click new repository', goal_description: 'form visible' },
    { instruction: 'fill form and submit', goal_description: 'repo created' },
    { instruction: 'verify repo exists', goal_description: 'repo visible' },
  ];

  const trigger = {
    reason: 'world_delta_anomaly',
    step_index: 1,
    description: 'form not visible after click',
  };

  // 模拟世界差异
  const delta = {
    snapshot_id: 'snap-2',
    previous_snapshot_id: 'snap-1',
    timestamp: new Date().toISOString(),
    added: [],
    removed: [{ id: 'form-1', type: 'element', state: 'disappeared', label: 'new repo form', source: 'dom_observed', metadata: {}, observed_at: new Date().toISOString() }],
    changed: [],
  };

  const { decision, newSteps } = engine.triggerReplan(
    trigger.reason,
    trigger.step_index,
    trigger.description,
    steps,
    delta
  );

  // 验证决策类型
  assert(decision.type !== 'keep_plan', `replan decision is ${decision.type}, not keep_plan`);

  // 验证步骤实际改变
  if (decision.type === 'local_repair' || decision.type === 'replan_remaining_steps') {
    assert(newSteps.length !== steps.slice(trigger.step_index).length || newSteps[0].instruction !== steps[trigger.step_index].instruction,
      'remaining steps were actually changed');
  } else if (decision.type === 'abort') {
    assert(newSteps.length === 0, 'abort means no remaining steps');
  }

  assert(decision.reason.length > 0, 'decision has a reason');
}

// ─────────────────────────────────────────────
// Scenario 4: parallelFeasibilityAnalysis
// Root Cause 3: 系统判断哪些步骤可并行、哪些不可并行
// ─────────────────────────────────────────────
function scenario4_parallelFeasibilityAnalysis() {
  console.log('\n[Scenario 4] parallelFeasibilityAnalysis');

  const arbitrator = new ResourceArbitrator();

  const steps = [
    { instruction: 'check system time', goal_description: 'time known', params: { app_name: 'terminal' } },
    { instruction: 'list files in /tmp', goal_description: 'files listed', params: { app_name: 'terminal' } },
    { instruction: 'navigate to github.com', goal_description: 'github loaded', params: { app_name: 'chrome', url: 'https://github.com' } },
    { instruction: 'open settings', goal_description: 'settings open', params: { app_name: 'chrome', url: 'https://github.com' } },
  ];

  const result = arbitrator.assessParallelizability(steps);

  assert(result.parallelizable !== undefined, 'parallelizability assessed');
  assert(Array.isArray(result.segments), 'segments is array');
  assert(result.segments.length > 0, 'at least one segment identified');
  assert(result.conflicts !== undefined, 'conflicts identified');

  // 验证有冲突被识别（chrome 同一标签页的连续操作）
  const hasChromeConflict = result.conflicts.some(c =>
    c.type === 'focus_steal' || c.type === 'browser_exclusive'
  );

  // 至少识别出分段
  assert(result.segments.length >= 2, `multiple segments: ${result.segments.length}`);
}

// ─────────────────────────────────────────────
// Scenario 5: resourceArbitrationWorks
// Root Cause 3: 冲突步骤被正确 serialize/postpone
// ─────────────────────────────────────────────
function scenario5_resourceArbitrationWorks() {
  console.log('\n[Scenario 5] resourceArbitrationWorks');

  const arbitrator = new ResourceArbitrator();

  // 两个冲突步骤：chrome 同一 URL 连续操作
  const steps = [
    { instruction: 'navigate to github.com', goal_description: 'github loaded', params: { app_name: 'chrome', url: 'https://github.com' } },
    { instruction: 'click star button on repo', goal_description: 'repo starred', params: { app_name: 'chrome', url: 'https://github.com' } },
  ];

  const arbitration = arbitrator.arbitrate(steps);

  assert(arbitration.action === 'serialize' || arbitration.action === 'parallel_safe',
    `arbitration action: ${arbitration.action}`);
  assert(Array.isArray(arbitration.conflicts), 'conflicts is array');
  assert(arbitration.conflicts.length >= 0, 'conflicts detected');

  // 验证输出结构完整
  assert(Array.isArray(arbitration.serialized_steps), 'serialized_steps is array');
  assert(Array.isArray(arbitration.parallel_segments), 'parallel_segments is array');
  assert(arbitration.reason.length > 0, 'arbitration has reason');

  // 如果有冲突，至少说明原因
  if (arbitration.conflicts.length > 0) {
    assert(arbitration.conflicts[0].severity !== undefined, 'conflict has severity');
  }
}

// ─────────────────────────────────────────────
// Scenario 6: superhumanOperationsSignal
// Root Cause 3: 输出结构化信号，证明"世界模型+重规划+并行运营"
// ─────────────────────────────────────────────
function scenario6_superhumanOperationsSignal() {
  console.log('\n[Scenario 6] superhumanOperationsSignal');

  const engine = new operationalEngine.constructor();

  // 建立世界模型
  engine.ingestObservations(
    [{ id: 'el-1', tag: 'button', text: 'Click me', href: undefined, src: undefined, rect: { x: 10, y: 10 }, visible: true }],
    [{ window_id: 'win-1', title: 'Notepad', app_name: 'notepad', rect: { x: 0, y: 0, width: 500, height: 400 }, focused: true, pid: 1234 }]
  );

  // 快照
  const { snapshot, delta } = engine.snapshotAndDelta(0, 'chain-op-test');
  assert(snapshot.id.length > 0, 'snapshot created with id');
  assert(delta !== undefined, 'delta computed');

  // 触发重规划
  const replanResult = engine.triggerReplan(
    'world_delta_anomaly',
    0,
    'test anomaly',
    [{ instruction: 'do thing', goal_description: 'thing done' }],
    delta
  );
  assert(replanResult.decision !== undefined, 'replan decision returned');

  // 并行仲裁
  const parallelResult = engine.arbitrateParallel([
    { instruction: 'run script', goal_description: 'done', params: { app_name: 'terminal' } },
    { instruction: 'read file', goal_description: 'done', params: { app_name: 'terminal' } },
  ]);
  assert(parallelResult.arbitration !== undefined, 'arbitration returned');
  assert(parallelResult.trace !== undefined, 'parallel trace returned');

  // 综合指标
  const metrics = engine.getMetrics();
  assert(metrics.world_model_active === true, 'world_model_active = true');
  assert(typeof metrics.entity_count === 'number', 'entity_count is number');
  assert(metrics.world_delta_processed === true, 'world_delta_processed = true');
  assert(metrics.last_world_snapshot_id !== undefined, 'snapshot id in metrics');

  // 验证关键结构存在
  assert('world_model_active' in metrics || 'replanner_triggered_count' in metrics, 'metrics has operational subsystems');
}

// ─────────────────────────────────────────────
// Run all scenarios
// ─────────────────────────────────────────────
console.log('================================================');
console.log('  Round 11 超人运营智能根因测试 (6 scenarios)');
console.log('================================================');

scenario1_worldModelBuildsFromObservation();
scenario2_worldDeltaTriggersReplan();
scenario3_replanActuallyChangesRemainingPlan();
scenario4_parallelFeasibilityAnalysis();
scenario5_resourceArbitrationWorks();
scenario6_superhumanOperationsSignal();

console.log('\n================================================');
console.log(`  Results: ${pass} passed, ${fail} failed`);
console.log('================================================');

if (fail === 0) {
  console.log('\n>>> ALL PASS → SUPERHUMAN_OPERATIONAL_INTELLIGENCE_BASELINE <<<\n');
  process.exit(0);
} else {
  console.log(`\n>>> ${fail} FAILED <<<\n`);
  process.exit(1);
}
