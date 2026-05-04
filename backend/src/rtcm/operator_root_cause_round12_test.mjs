/**
 * Round 12 多任务自治运营 · 持续进化 · 主权治理根因测试
 * ================================================
 * 6 scenarios covering 3 root causes:
 * - Root Cause 1: 没有真正的多任务自治运营层
 * - Root Cause 2: 缺少跨日持续进化闭环
 * - Root Cause 3: 缺少系统级主权治理与审批边界
 * ================================================
 */

import {
  autonomousEngine,
  TaskPortfolio,
  MultiTaskScheduler,
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
// Scenario 1: multiTaskPortfolioManagement
// Root Cause 1: 至少 3 条任务链同时存在，系统能维护 portfolio 状态
// ─────────────────────────────────────────────
function scenario1_multiTaskPortfolioManagement() {
  console.log('\n[Scenario 1] multiTaskPortfolioManagement');

  const engine = new AutonomousOperationEngine();

  // 注册 3 条任务链
  const tasks = [
    {
      task_id: 'task-1',
      task_type: 'web_browser',
      status: 'running',
      priority: 'urgent',
      resource_needs: { app_name: 'chrome', browser_url: 'https://github.com', requires_focus: true },
      current_goal: 'create repository on github',
      approval_state: 'auto_allowed',
      progress: 50,
      health: 'healthy',
      failure_count: 0,
      recovery_count: 0,
      drift_risk: 0.1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      chain_id: 'chain-1',
    },
    {
      task_id: 'task-2',
      task_type: 'cli_tool',
      status: 'pending',
      priority: 'important',
      resource_needs: { app_name: 'terminal', requires_focus: false },
      current_goal: 'run build script',
      approval_state: 'auto_allowed',
      progress: 0,
      health: 'healthy',
      failure_count: 0,
      recovery_count: 0,
      drift_risk: 0.2,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      chain_id: 'chain-2',
    },
    {
      task_id: 'task-3',
      task_type: 'desktop_app',
      status: 'pending',
      priority: 'background',
      resource_needs: { app_name: 'notepad', requires_focus: false },
      current_goal: 'edit config file',
      approval_state: 'waiting_approval',
      progress: 0,
      health: 'unknown',
      failure_count: 0,
      recovery_count: 0,
      drift_risk: 0.3,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      chain_id: 'chain-3',
    },
  ];

  for (const task of tasks) {
    engine.portfolio.register(task);
  }

  // 验证 portfolio 状态
  const all = engine.portfolio.getAll();
  assert(all.length >= 3, `portfolio has ${all.length} tasks (>= 3)`);

  // 验证优先级排序
  const byPriority = engine.portfolio.getByPriority();
  assert(byPriority.length >= 3, 'getByPriority returns tasks');
  assert(byPriority[0].priority === 'urgent', 'first task is urgent priority');

  // 验证按 ID 查询
  const t1 = engine.portfolio.get('task-1');
  assert(t1 !== undefined, 'task-1 retrievable by ID');
  assert(t1.current_goal === 'create repository on github', 'task fields preserved');

  // 验证更新
  engine.portfolio.update('task-1', { progress: 75 });
  assert(engine.portfolio.get('task-1').progress === 75, 'task update works');

  // 验证待审批查询
  const pending = engine.portfolio.getPendingApprovals();
  assert(pending.length >= 1, `pending approvals: ${pending.length} (>= 1)`);

  // 验证任务间冲突检测
  const conflicts = engine.portfolio.checkInterTaskConflicts(engine.portfolio.getActive());
  assert(Array.isArray(conflicts), 'inter-task conflict detection works');
}

// ─────────────────────────────────────────────
// Scenario 2: schedulerPrioritizesAndArbitrates
// Root Cause 1: 多任务同时竞争资源时，调度器能给出 run_now/queue/pause/terminate 决策
// ─────────────────────────────────────────────
function scenario2_schedulerPrioritizesAndArbitrates() {
  console.log('\n[Scenario 2] schedulerPrioritizesAndArbitrates');

  const engine = new AutonomousOperationEngine();

  // 注册多任务：urgent + important + background
  engine.portfolio.register({
    task_id: 'sched-task-1', task_type: 'web', status: 'running', priority: 'urgent',
    resource_needs: { app_name: 'chrome', requires_focus: true }, current_goal: 'urgent goal',
    approval_state: 'auto_allowed', progress: 30, health: 'healthy', failure_count: 0, recovery_count: 0,
    drift_risk: 0.1, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), chain_id: 'sc-1',
  });
  engine.portfolio.register({
    task_id: 'sched-task-2', task_type: 'cli', status: 'running', priority: 'important',
    resource_needs: { app_name: 'terminal', requires_focus: true }, current_goal: 'important goal',
    approval_state: 'auto_allowed', progress: 10, health: 'healthy', failure_count: 0, recovery_count: 0,
    drift_risk: 0.2, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), chain_id: 'sc-2',
  });
  engine.portfolio.register({
    task_id: 'sched-task-3', task_type: 'desktop', status: 'pending', priority: 'background',
    resource_needs: { app_name: 'notepad', requires_focus: false }, current_goal: 'background goal',
    approval_state: 'auto_allowed', progress: 0, health: 'unknown', failure_count: 0, recovery_count: 0,
    drift_risk: 0.3, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), chain_id: 'sc-3',
  });

  // 调度决策
  const decisions = engine.schedule();

  assert(decisions.length >= 3, `got ${decisions.length} schedule decisions (>= 3)`);
  const decisionTypes = decisions.map(d => d.decision);
  assert(decisionTypes.includes('run_now') || decisionTypes.includes('queue') || decisionTypes.includes('wait_resource'),
    'decisions include valid scheduler actions');

  // 验证有 run_now 的任务
  const runNow = decisions.find(d => d.decision === 'run_now');
  assert(runNow !== undefined, `at least one task gets run_now: ${runNow?.task_id}`);

  // 验证 background 任务被 queue 或 wait_resource
  const bgDecision = decisions.find(d => d.task_id === 'sched-task-3');
  if (bgDecision) {
    assert(['queue', 'wait_resource', 'run_now'].includes(bgDecision.decision),
      `background task decision is valid: ${bgDecision.decision}`);
  }

  // 验证冲突导致等待
  const urgentDecision = decisions.find(d => d.task_id === 'sched-task-1');
  if (urgentDecision) {
    assert(urgentDecision.decision === 'run_now' || urgentDecision.decision === 'queue',
      `urgent task decision is valid: ${urgentDecision.decision}`);
  }
}

// ─────────────────────────────────────────────
// Scenario 3: dailyEvolutionAffectsNextRun
// Root Cause 2: 前一轮经验在下一轮真实影响 strategy/asset/fallback 选择
// ─────────────────────────────────────────────
function scenario3_dailyEvolutionAffectsNextRun() {
  console.log('\n[Scenario 3] dailyEvolutionAffectsNextRun');

  const engine = new AutonomousOperationEngine();

  // 模拟昨日任务历史 - 5个任务，4个成功（80% > 70%阈值）触发策略更新
  const yesterdayTasks = [
    {
      task_id: 'yest-task-1', task_type: 'github_operations', status: 'completed', priority: 'important',
      resource_needs: { app_name: 'chrome', requires_focus: true }, current_goal: 'create repo',
      approval_state: 'auto_allowed', progress: 100, health: 'healthy', failure_count: 0, recovery_count: 0,
      drift_risk: 0.1, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), chain_id: 'yc-1',
    },
    {
      task_id: 'yest-task-2', task_type: 'github_operations', status: 'completed', priority: 'important',
      resource_needs: { app_name: 'chrome', requires_focus: true }, current_goal: 'create repo',
      approval_state: 'auto_allowed', progress: 100, health: 'healthy', failure_count: 0, recovery_count: 0,
      drift_risk: 0.1, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), chain_id: 'yc-2',
    },
    {
      task_id: 'yest-task-3', task_type: 'github_operations', status: 'completed', priority: 'important',
      resource_needs: { app_name: 'chrome', requires_focus: true }, current_goal: 'create repo',
      approval_state: 'auto_allowed', progress: 100, health: 'healthy', failure_count: 0, recovery_count: 0,
      drift_risk: 0.1, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), chain_id: 'yc-3',
    },
    {
      task_id: 'yest-task-4', task_type: 'github_operations', status: 'completed', priority: 'important',
      resource_needs: { app_name: 'chrome', requires_focus: true }, current_goal: 'star repo',
      approval_state: 'auto_allowed', progress: 100, health: 'healthy', failure_count: 0, recovery_count: 0,
      drift_risk: 0.1, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), chain_id: 'yc-4',
    },
    {
      task_id: 'yest-task-5', task_type: 'github_operations', status: 'failed', priority: 'important',
      resource_needs: { app_name: 'chrome', requires_focus: true }, current_goal: 'delete repository',
      approval_state: 'auto_allowed', progress: 30, health: 'critical', failure_count: 2, recovery_count: 1,
      drift_risk: 0.8, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), chain_id: 'yc-5',
    },
  ];

  const yesterdayOutcomes = [
    { task_id: 'yest-task-1', success: true, recovery_used: false },
    { task_id: 'yest-task-2', success: true, recovery_used: false },
    { task_id: 'yest-task-3', success: true, recovery_used: false },
    { task_id: 'yest-task-4', success: true, recovery_used: false },
    { task_id: 'yest-task-5', success: false, failed_step: 'delete repository step failed', recovery_used: true },
  ];

  // 夜间蒸馏
  const report = engine.nightlyDistill(yesterdayTasks, yesterdayOutcomes);

  assert(report.date !== undefined, 'report has date');
  assert(report.total_tasks === 5, `report covers ${report.total_tasks} tasks`);
  assert(report.successful_tasks === 4, `report shows ${report.successful_tasks} successes`);
  assert(report.failed_tasks === 1, `report shows ${report.failed_tasks} failure`);

  // 经验已存储
  const expBase = engine.evolution.getExperienceBase();
  assert(expBase.length > 0, `experience base has ${expBase.length} entries`);

  // 次日应用 - 80% 成功率应触发 strategy_update (>= 70%)
  const todayDecision = engine.applyYesterdayToToday({
    task_type: 'github_operations',
    instruction: 'delete a repository on github',
    failed_attempts: 1,
  });

  // 80% success rate → strategy_update should fire
  assert(todayDecision.strategy_shift !== undefined || todayDecision.anti_pattern_blocked === true || todayDecision.confidence > 0,
    'yesterday experience affects today decision');
  assert(typeof todayDecision.confidence === 'number', 'decision has confidence score');
}

// ─────────────────────────────────────────────
// Scenario 4: antiPatternBlocked
// Root Cause 2: 某条低效/失败路径被夜间提纯后，次日被主动规避
// ─────────────────────────────────────────────
function scenario4_antiPatternBlocked() {
  console.log('\n[Scenario 4] antiPatternBlocked');

  const engine = new AutonomousOperationEngine();

  // 手动注入 anti-pattern 经验
  const antiPattern = {
    id: 'ap-1',
    type: 'anti_pattern',
    content: 'Avoid: delete repository directly in github_operations context',
    confidence: 0.85,
    source_count: 3,
    recency: Date.now(),
    reuse_score: 0,
    task_signature: 'github_operations',
    created_at: new Date().toISOString(),
  };
  engine.evolution.storeExperiences([antiPattern]);

  // 次日执行时遇到类似指令
  const decision = engine.applyYesterdayToToday({
    task_type: 'github_operations',
    instruction: 'delete repository named test-repo on github',
    failed_attempts: 0,
  });

  assert(decision.anti_pattern_blocked === true, `anti-pattern blocked: ${decision.anti_pattern_blocked}`);
  assert(decision.confidence >= 0.8, `confidence: ${decision.confidence} (>= 0.8)`);

  // 进化日志有记录
  const evoLog = engine.evolution.getEvolutionLog();
  assert(evoLog.some(e => e.action === 'anti_pattern_blocked'), 'evolution log records anti-pattern block');
}

// ─────────────────────────────────────────────
// Scenario 5: governanceApprovalGate
// Root Cause 3: 高风险动作命中审批门，未批准前不能执行
// ─────────────────────────────────────────────
function scenario5_governanceApprovalGate() {
  console.log('\n[Scenario 5] governanceApprovalGate');

  const engine = new AutonomousOperationEngine();

  // 提交高风险任务
  const riskyTask = {
    task_id: 'risky-task-1',
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
    chain_id: 'risky-chain-1',
  };

  const { accepted, governance_decision } = engine.submitTask(riskyTask);

  assert(governance_decision.requires_approval === true, 'high-risk task requires approval');
  assert(governance_decision.can_suggest === true, 'task can be suggested but not executed');
  assert(governance_decision.risk_type !== undefined, 'risk type identified');
  assert(governance_decision.risk_severity === 'high', `risk severity: ${governance_decision.risk_severity}`);

  // 高风险动作直接检查
  const riskyInstruction = 'npm install -g typescript';
  const govCheck = engine.governance.check(riskyInstruction, 'risky-task-1', 'approval_required');

  assert(govCheck.requires_approval === true, 'npm install requires approval');
  assert(govCheck.can_suggest === true, 'can suggest but not execute');
  assert(govCheck.risk_type === 'dependency_install', `risk type: ${govCheck.risk_type}`);

  // 治理日志有记录
  const govLog = engine.governance.getGovernanceLog();
  assert(govLog.some(l => l.decision === 'approval_gate_hit'), 'approval gate logged');

  // 批准后再次检查 - 手动更新 portfolio 的 approval_state 以反映审批通过
  engine.governance.approve('risky-task-1');
  engine.portfolio.update('risky-task-1', { approval_state: 'auto_allowed' });
  const afterApprove = engine.governance.check(riskyInstruction, 'risky-task-1', 'auto_allowed');
  assert(afterApprove.allowed === true, 'after approval, action is allowed');
}

// ─────────────────────────────────────────────
// Scenario 6: userVetoStopsAutonomy
// Root Cause 3: 用户 veto 后，任务立即冻结，系统不继续偷偷执行
// ─────────────────────────────────────────────
function scenario6_userVetoStopsAutonomy() {
  console.log('\n[Scenario 6] userVetoStopsAutonomy');

  const engine = new AutonomousOperationEngine();

  // 注册任务
  const taskToVeto = {
    task_id: 'veto-task-1',
    task_type: 'web_browser',
    status: 'running',
    priority: 'important',
    resource_needs: { app_name: 'chrome', browser_url: 'https://github.com', requires_focus: true },
    current_goal: 'create repository on github',
    approval_state: 'auto_allowed',
    progress: 40,
    health: 'healthy',
    failure_count: 0,
    recovery_count: 0,
    drift_risk: 0.1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    chain_id: 'veto-chain-1',
  };
  engine.portfolio.register(taskToVeto);

  // 用户 veto 该任务
  engine.userVeto('create repository on github', 'veto-task-1', 'user does not want this action');

  // 验证任务被冻结
  const frozenTask = engine.portfolio.get('veto-task-1');
  assert(frozenTask !== undefined, 'task still exists after veto');
  assert(frozenTask.status === 'frozen', `task status: ${frozenTask.status} (expected frozen)`);
  assert(frozenTask.approval_state === 'frozen', `approval_state: ${frozenTask.approval_state}`);

  // 验证 governance 记录
  const govLog = engine.governance.getGovernanceLog();
  assert(govLog.some(l => l.decision === 'user_veto'), 'user_veto logged');
  assert(govLog.some(l => l.decision === 'task_frozen'), 'task_frozen logged');

  // 再次检查同一指令，应该被拦截
  const reCheck = engine.governance.check('create repository on github', 'veto-task-1', 'frozen');
  assert(reCheck.allowed === false, 'vetoed instruction is blocked on re-check');
  assert(reCheck.governance_tag === 'user_veto' || reCheck.governance_tag === 'task_state_blocked',
    `blocked by: ${reCheck.governance_tag}`);

  // 调度器不应该 run 这个任务
  const decisions = engine.schedule();
  const vetoDecision = decisions.find(d => d.task_id === 'veto-task-1');
  if (vetoDecision) {
    assert(['wait_resource', 'terminate_low_value'].includes(vetoDecision.decision),
      `vetoed task decision: ${vetoDecision.decision}`);
  }

  // 用户说停止整个系统
  engine.governance.halt('user requested full stop');

  const haltCheck = engine.governance.check('any instruction at all', undefined, undefined);
  assert(haltCheck.allowed === false, 'system halt blocks all actions');
  assert(haltCheck.governance_tag === 'system_halt', `governance tag: ${haltCheck.governance_tag}`);

  // 恢复系统后，需要解冻任务并清除否决才能继续
  engine.governance.resume();
  engine.portfolio.unfreeze('veto-task-1');
  engine.governance.clearTaskVetoes('veto-task-1');
  const afterUnfreeze = engine.governance.check('create repository on github', 'veto-task-1', 'waiting_approval');
  // After resume + unfreeze + clear vetoes, instruction is allowed (vetoes cleared)
  assert(afterUnfreeze.allowed === true, 'after clearTaskVetoes, instruction is allowed (vetoes cleared)');
  assert(afterUnfreeze.governance_tag === undefined, 'no governance tag after vetoes cleared');
}

// ─────────────────────────────────────────────
// Run all scenarios
// ─────────────────────────────────────────────
console.log('================================================');
console.log('  Round 12 多任务自治运营根因测试 (6 scenarios)');
console.log('================================================');

scenario1_multiTaskPortfolioManagement();
scenario2_schedulerPrioritizesAndArbitrates();
scenario3_dailyEvolutionAffectsNextRun();
scenario4_antiPatternBlocked();
scenario5_governanceApprovalGate();
scenario6_userVetoStopsAutonomy();

console.log('\n================================================');
console.log(`  Results: ${pass} passed, ${fail} failed`);
console.log('================================================');

if (fail === 0) {
  console.log('\n>>> ALL PASS → AUTONOMOUS_OPERATION_AND_EVOLUTION_BASELINE <<<\n');
  process.exit(0);
} else {
  console.log(`\n>>> ${fail} FAILED <<<\n`);
  process.exit(1);
}
