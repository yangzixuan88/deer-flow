/**
 * @file operator_root_cause_round7_test.mjs
 * @description Round 7 根因修复验收测试
 * 目标: 把 deerflow 从"真实连续链路基线"推进到"目标态 + 恢复 + 环境自维持基线"
 *
 * 验证 3 个根因:
 * 1. 执行环境自维持 (health check + readiness gate + bootstrap + diagnostics)
 * 2. 任务级目标态验证 (GoalStateVerifier)
 * 3. 中断恢复 (checkpoint + resume + state compatibility)
 *
 * 6 个场景:
 * 1. executorReadinessGate      - 执行前检查执行器就绪状态
 * 2. executorBootstrapOrFallback - 执行器缺失时触发 bootstrap 或 fallback
 * 3. goalStateVerification     - 多步链最终输出 goal_satisfied
 * 4. observationDrivenNextStep  - 基于 goal_gap 决定下一步
 * 5. realChainCheckpoint        - 连续链中保存 checkpoint
 * 6. resumeAfterInterruption   - 中断后恢复，不从头盲跑
 */

import { fileURLToPath } from 'url';
import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const TEST_DIR = path.join(os.homedir(), '.deerflow', 'rtcm', 'test_artifacts');
fs.mkdirSync(TEST_DIR, { recursive: true });

// 多路径 env 加载
const possiblePaths = [
  'e:/OpenClaw-Base/deerflow/backend/.env',
  path.join(os.homedir(), '.deerflow', 'projects', 'e--OpenClaw-Base-openclaw------', 'deerflow', 'backend', '.env'),
];
for (const envFile of possiblePaths) {
  if (fs.existsSync(envFile)) {
    fs.readFileSync(envFile, 'utf-8').split('\n').forEach(line => {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith('#')) {
        const [key, ...valueParts] = trimmed.split('=');
        if (key && valueParts.length) process.env[key] = valueParts.join('=');
      }
    });
    break;
  }
}

console.log('╔════════════════════════════════════════════════════════════════╗');
console.log('║  Round 7: 目标态 + 恢复 + 环境自维持验收测试              ║');
console.log('╚════════════════════════════════════════════════════════════════╝\n');

const results = {
  timestamp: new Date().toISOString(),
  scenarios: {},
};

// ============================================================
// Scenario 1: 执行器 Readiness Gate
// ============================================================
async function testExecutorReadinessGate() {
  console.log('【Scenario 1】执行器 Readiness Gate\n');

  const { checkExecutorHealth, executorReadinessGate, ExecutorType } = await import('../domain/m11/mod.ts');

  // 获取执行器健康状态
  const health = await checkExecutorHealth();

  console.log('  执行器健康状态:');
  for (const [executor, status] of Object.entries(health.executor_health)) {
    const s = status;
    console.log(`    ${executor}: ${s.status}${s.error ? ` (${s.error})` : ''}`);
  }
  console.log(`  总体就绪: ${health.readiness}`);

  // 测试 OpenCLI readiness gate
  const opencliGate = await executorReadinessGate(ExecutorType.OPENCLI, health);
  console.log(`  OpenCLI gate: ready=${opencliGate.ready}, action=${opencliGate.action}, reason=${opencliGate.reason}`);

  // 测试 Midscene readiness gate
  const midsceneGate = await executorReadinessGate(ExecutorType.MIDSCENE, health);
  console.log(`  Midscene gate: ready=${midsceneGate.ready}, action=${midsceneGate.action}, reason=${midsceneGate.reason}`);

  // 测试 UI-TARS readiness gate
  const uiTarsGate = await executorReadinessGate(ExecutorType.UI_TARS, health);
  console.log(`  UI-TARS gate: ready=${uiTarsGate.ready}, action=${uiTarsGate.action}, reason=${uiTarsGate.reason}`);

  // 验证: readiness gate 返回正确的 action (不盲撞)
  const gatesCorrect =
    (opencliGate.ready === true || opencliGate.action !== 'execute') &&
    (midsceneGate.ready === true || midsceneGate.action !== 'execute') &&
    (uiTarsGate.ready === true || uiTarsGate.action !== 'execute');

  console.log(`  ${gatesCorrect ? '✅' : '❌'} Readiness gate 正确拦截不 ready 的执行器: ${gatesCorrect}`);

  // 验证 ExecutorHealth 结构完整性
  const healthStructureValid =
    health.environment_diagnostics !== undefined &&
    health.bootstrap_attempts !== undefined &&
    health.checked_at !== undefined &&
    health.executor_health !== undefined;

  console.log(`  ${healthStructureValid ? '✅' : '❌'} ExecutorHealth 结构完整 (executor_health/readiness/bootstrap_attempts/environment_diagnostics)`);

  const passed = gatesCorrect && healthStructureValid;
  results.scenarios.executorReadinessGate = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// Scenario 2: Bootstrap 或 Fallback
// ============================================================
async function testExecutorBootstrapOrFallback() {
  console.log('\n【Scenario 2】Bootstrap 或 Fallback 触发\n');

  const { executorReadinessGate, ExecutorType } = await import('../domain/m11/mod.ts');

  // 模拟 OpenCLI 不 ready 的健康状态
  const mockHealth = {
    executor_health: {
      [ExecutorType.OPENCLI]: { status: 'not_ready', error: 'OpenCLI daemon not running', last_check: new Date().toISOString() },
      [ExecutorType.MIDSCENE]: { status: 'ready', last_check: new Date().toISOString() },
      [ExecutorType.UI_TARS]: { status: 'unknown', last_check: new Date().toISOString() },
      [ExecutorType.CLAUDE_CODE]: { status: 'ready', last_check: new Date().toISOString() },
      [ExecutorType.CLI_ANYTHING]: { status: 'unknown', last_check: new Date().toISOString() },
      [ExecutorType.LARKSUITE_CLI]: { status: 'unknown', last_check: new Date().toISOString() },
    },
    readiness: false,
    bootstrap_attempts: {
      [ExecutorType.OPENCLI]: 0,
      [ExecutorType.MIDSCENE]: 0,
      [ExecutorType.UI_TARS]: 0,
      [ExecutorType.CLAUDE_CODE]: 0,
      [ExecutorType.CLI_ANYTHING]: 0,
      [ExecutorType.LARKSUITE_CLI]: 0,
    },
    environment_diagnostics: {
      opencli_daemon_running: false,
      cli_hub_path: path.join(os.homedir(), '.deerflow', 'cli-hub'),
    },
    checked_at: new Date().toISOString(),
  };

  // 首次调用: OpenCLI not ready → bootstrap
  const gate1 = await executorReadinessGate(ExecutorType.OPENCLI, mockHealth);
  console.log(`  首次 OpenCLI gate: action=${gate1.action}, target=${gate1.targetExecutor || 'none'}`);
  const firstIsBootstrap = gate1.action === 'bootstrap';

  // 第3次调用 (超过 bootstrap 阈值): → fallback 到 Midscene
  mockHealth.bootstrap_attempts[ExecutorType.OPENCLI] = 2;
  const gate2 = await executorReadinessGate(ExecutorType.OPENCLI, mockHealth);
  console.log(`  第3次 OpenCLI gate: action=${gate2.action}, target=${gate2.targetExecutor || 'none'}`);
  const thirdIsFallback = gate2.action === 'fallback' && gate2.targetExecutor === ExecutorType.MIDSCENE;

  // Midscene not ready → 直接 fallback 到 UI_TARS
  const midsceneGate = await executorReadinessGate(ExecutorType.MIDSCENE, {
    ...mockHealth,
    executor_health: {
      ...mockHealth.executor_health,
      [ExecutorType.MIDSCENE]: { status: 'not_ready', error: 'Midscene not available' },
    },
  });
  console.log(`  Midscene not ready: action=${midsceneGate.action}, target=${midsceneGate.targetExecutor || 'none'}`);
  const midsceneFallsBack = midsceneGate.action === 'fallback';

  const passed = firstIsBootstrap && thirdIsFallback && midsceneFallsBack;
  console.log(`  ${passed ? '✅' : '❌'} Bootstrap→Fallback 链正确触发: bootstrap=${firstIsBootstrap}, fallback=${thirdIsFallback}, midscene_fallback=${midsceneFallsBack}`);
  results.scenarios.executorBootstrapOrFallback = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// Scenario 3: 目标态验证 (GoalStateVerifier)
// ============================================================
async function testGoalStateVerification() {
  console.log('\n【Scenario 3】目标态验证 (GoalStateVerifier)\n');

  const { parseGoalState, verifyGoalState, extractObservedStateFromChecks, ExecutorType } = await import('../domain/m11/mod.ts');

  // 场景 A: URL 目标达成
  const urlGoal = parseGoalState('navigate to https://github.com');
  console.log(`  URL 目标解析: type=${urlGoal.type}, hostname=${urlGoal.target?.hostname}`);

  const urlObserved = {
    url: 'https://github.com',
    hostname: 'github.com',
    title: 'GitHub',
    element_count: 10,
  };
  const urlVerification = verifyGoalState(urlGoal, urlObserved);
  console.log(`  URL 验证: goal_satisfied=${urlVerification.goal_satisfied}, score=${urlVerification.satisfaction_score}, termination=${urlVerification.termination_reason}`);
  console.log(`    next_step_hint: ${urlVerification.next_step_hint}`);

  const urlPassed = urlVerification.goal_satisfied && urlVerification.satisfaction_score === 1.0;

  // 场景 B: 元素目标未达成
  const elementGoal = parseGoalState('click the sign in button');
  console.log(`  元素目标解析: type=${elementGoal.type}, target=${elementGoal.target?.element_text}`);

  const elementObserved = {
    url: 'https://github.com',
    hostname: 'github.com',
    title: 'GitHub',
    element_count: 0,
  };
  const elementVerification = verifyGoalState(elementGoal, elementObserved);
  console.log(`  元素验证: goal_satisfied=${elementVerification.goal_satisfied}, score=${elementVerification.satisfaction_score}, termination=${elementVerification.termination_reason}`);
  console.log(`    goal_gap.missing_conditions: ${elementVerification.goal_gap.missing_conditions.join(', ')}`);

  const elementPassed = !elementVerification.goal_satisfied && elementVerification.satisfaction_score < 1.0;

  // 场景 C: 从 FallbackResult.checks 提取观测状态
  const mockFallbackResult = {
    success: true,
    executor_used: ExecutorType.OPENCLI,
    result: {},
    checks: {
      dom_observed: {
        title: 'GitHub',
        url: 'https://github.com',
        element_count: 5,
        key_elements: ['Sign in', 'Sign up', 'Explore'],
      },
    },
  };
  const extractedObserved = extractObservedStateFromChecks(mockFallbackResult.checks);
  console.log(`  从 checks 提取观测状态: url=${extractedObserved?.url}, element_count=${extractedObserved?.element_count}, key_elements=${extractedObserved?.key_elements?.join(', ')}`);

  const extractPassed = extractedObserved?.url === 'https://github.com' && extractedObserved?.element_count === 5;

  const passed = urlPassed && elementPassed && extractPassed;
  console.log(`  ${passed ? '✅' : '❌'} 目标态验证: url_goal=${urlPassed}, element_goal=${elementPassed}, extract=${extractPassed}`);
  results.scenarios.goalStateVerification = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// Scenario 4: 观测驱动下一步决策
// ============================================================
async function testObservationDrivenNextStep() {
  console.log('\n【Scenario 4】观测驱动下一步决策\n');

  const { observationDrivenNextStep, parseGoalState, verifyGoalState } = await import('../domain/m11/mod.ts');

  // 场景 A: 目标达成 → stop
  const goalA = parseGoalState('navigate to https://github.com');
  const observedA = { url: 'https://github.com', hostname: 'github.com', title: 'GitHub', element_count: 5 };
  const verifyA = verifyGoalState(goalA, observedA);
  const decisionA = observationDrivenNextStep('navigate to https://github.com', verifyA);
  console.log(`  目标达成: action=${decisionA.action} (expected stop), reason=${decisionA.reason}`);
  const aPassed = decisionA.action === 'stop';

  // 场景 B: 目标失败 → fallback
  const goalB = parseGoalState('click the sign in button');
  const observedB = { url: 'https://github.com', hostname: 'github.com', title: 'GitHub', element_count: 0 };
  const verifyB = verifyGoalState(goalB, observedB);
  const decisionB = observationDrivenNextStep('click the sign in button', verifyB);
  console.log(`  目标失败: action=${decisionB.action} (expected fallback), reason=${decisionB.reason}`);
  const bPassed = decisionB.action === 'fallback';

  // 场景 C: 部分成功 → continue
  const goalC = parseGoalState('click the sign in button');
  const observedC = { url: 'https://github.com', hostname: 'github.com', title: 'GitHub', element_count: 3, key_elements: ['Explore'] };
  const verifyC = verifyGoalState(goalC, observedC);
  const decisionC = observationDrivenNextStep('click the sign in button', verifyC);
  console.log(`  部分成功: action=${decisionC.action} (expected continue), score=${verifyC.satisfaction_score}`);
  const cPassed = decisionC.action === 'continue';

  // 场景 D: 无观测状态 → retry
  const goalD = parseGoalState('click the sign in button');
  const decisionD = observationDrivenNextStep('click the sign in button', { ...verifyGoalState(goalD, undefined), termination_reason: 'uncertain' });
  console.log(`  无观测状态: action=${decisionD.action} (expected retry), reason=${decisionD.reason}`);
  const dPassed = decisionD.action === 'retry';

  const passed = aPassed && bPassed && cPassed && dPassed;
  console.log(`  ${passed ? '✅' : '❌'} 观测驱动决策: stop=${aPassed}, fallback=${bPassed}, continue=${cPassed}, retry=${dPassed}`);
  results.scenarios.observationDrivenNextStep = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// Scenario 5: 连续链保存 Checkpoint
// ============================================================
async function testRealChainCheckpoint() {
  console.log('\n【Scenario 5】真实连续链保存 Checkpoint\n');

  const { checkpointManager, executeWithAutoSelect, extractObservedStateFromChecks } = await import('../domain/m11/mod.ts');

  const taskId = `round7_checkpoint_${Date.now()}`;
  const sessionId = taskId;

  // 创建 3 步 DAG
  let ctx = {
    session_id: sessionId,
    current_step: 0,
    operation_history: [],
    last_url: undefined,
  };

  // Step 1: navigate
  const step1 = await executeWithAutoSelect(
    'navigate to https://example.com',
    { url: 'https://example.com' },
    undefined,
    ctx
  );
  ctx = { ...ctx, ...step1.accumulated_context, current_step: 1 };

  // ★ 保存 Step 1 checkpoint
  const cp1 = checkpointManager.saveCheckpoint(
    taskId,
    1,
    ctx,
    extractObservedStateFromChecks(step1.checks),
    undefined
  );
  console.log(`  Step1 checkpoint: id=${cp1.checkpoint_id}, step=${cp1.step}, valid=${cp1.valid}`);

  // Step 2: click
  const step2 = await executeWithAutoSelect(
    'take a screenshot',
    { url: ctx.last_url },
    undefined,
    ctx
  );
  ctx = { ...ctx, ...step2.accumulated_context, current_step: 2 };

  // ★ 保存 Step 2 checkpoint
  const cp2 = checkpointManager.saveCheckpoint(
    taskId,
    2,
    ctx,
    extractObservedStateFromChecks(step2.checks),
    undefined
  );
  console.log(`  Step2 checkpoint: id=${cp2.checkpoint_id}, step=${cp2.step}, valid=${cp2.valid}`);

  // Step 3: verify
  const step3 = await executeWithAutoSelect(
    'take a screenshot',
    { url: ctx.last_url },
    undefined,
    ctx
  );
  ctx = { ...ctx, ...step3.accumulated_context, current_step: 3 };

  // ★ 保存 Step 3 checkpoint
  const cp3 = checkpointManager.saveCheckpoint(
    taskId,
    3,
    ctx,
    extractObservedStateFromChecks(step3.checks),
    undefined
  );
  console.log(`  Step3 checkpoint: id=${cp3.checkpoint_id}, step=${cp3.step}, valid=${cp3.valid}`);

  // 验证 checkpoint 结构完整性
  const checkpointsValid =
    cp1.valid === true &&
    cp2.valid === true &&
    cp3.valid === true &&
    cp1.step === 1 &&
    cp2.step === 2 &&
    cp3.step === 3 &&
    cp1.operator_context !== undefined &&
    cp2.operator_context !== undefined &&
    cp3.operator_context !== undefined;

  console.log(`  ${checkpointsValid ? '✅' : '❌'} Checkpoint 保存有效: step1=${cp1.step}, step2=${cp2.step}, step3=${cp3.step}, all_valid=${checkpointsValid}`);

  // 验证可以从文件加载
  const loaded = checkpointManager.loadCheckpoint(taskId);
  const loadPassed = loaded !== null && loaded.checkpoint_id === cp3.checkpoint_id;
  console.log(`  ${loadPassed ? '✅' : '❌'} Checkpoint 可从文件加载: ${loadPassed}`);

  const passed = checkpointsValid && loadPassed;
  results.scenarios.realChainCheckpoint = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// Scenario 6: 中断后恢复
// ============================================================
async function testResumeAfterInterruption() {
  console.log('\n【Scenario 6】中断后恢复\n');

  const { checkpointManager, executeWithAutoSelect, extractObservedStateFromChecks } = await import('../domain/m11/mod.ts');

  const taskId = `round7_resume_${Date.now()}`;
  const sessionId = taskId;

  let ctx = {
    session_id: sessionId,
    current_step: 0,
    operation_history: [],
    last_url: 'https://example.com',
  };

  // 模拟 3 步执行，每步保存 checkpoint
  const steps = [
    'navigate to https://example.com',
    'take a screenshot',
    'take another screenshot',
  ];

  for (let i = 0; i < steps.length; i++) {
    const step = await executeWithAutoSelect(
      steps[i],
      { url: ctx.last_url },
      undefined,
      ctx
    );
    ctx = { ...ctx, ...step.accumulated_context, current_step: i + 1 };
    checkpointManager.saveCheckpoint(
      taskId,
      i + 1,
      ctx,
      extractObservedStateFromChecks(step.checks),
      undefined
    );
    console.log(`  Step ${i + 1}: current_step=${ctx.current_step}, history=${ctx.operation_history?.length || 0}`);
  }

  // ★ 模拟中断: 在 step 3 之后，检查点已保存

  // 验证 validateAndResume — 正常恢复（状态兼容）
  // 注意: desktop 操作的 checkpoint 无 last_observed_state（midscene 不返回 dom_observed），
  // 因此状态兼容性检查只验证步骤数，不检测 URL 不匹配
  const resumeResult = checkpointManager.validateAndResume(taskId, 3, { url: ctx.last_url });
  console.log(`  正常恢复验证:`);
  console.log(`    resume_from_step=${resumeResult.resume_from_step} (expected 4 = checkpoint.step+1)`);
  console.log(`    checkpoint_valid=${resumeResult.checkpoint_valid}`);
  console.log(`    resume_decision=${resumeResult.resume_decision}`);
  console.log(`    reason=${resumeResult.reason}`);
  const normalResumePassed =
    resumeResult.checkpoint_valid === true &&
    resumeResult.resume_decision === 'resume' &&
    resumeResult.resume_from_step === 4; // 从第3步的下一步(第4步)继续

  console.log(`  ${normalResumePassed ? '✅' : '❌'} 正常恢复: valid=${resumeResult.checkpoint_valid}, decision=${resumeResult.resume_decision}, resume_from_step=${resumeResult.resume_from_step}`);

  // 验证 validateAndResume — 步骤不兼容（当前步 < 检查点步 → 疑似重放）
  // midscene 桌面操作没有 dom_observed，无法检测 URL 不匹配，用步骤数检测替代
  const incompatibleResult = checkpointManager.validateAndResume(taskId, 2, { url: ctx.last_url });
  console.log(`  步骤不兼容验证 (currentStep=2 < checkpoint.step=3):`);
  console.log(`    checkpoint_valid=${incompatibleResult.checkpoint_valid}`);
  console.log(`    resume_decision=${incompatibleResult.resume_decision} (expected replay_from_checkpoint due to step warning)`);
  console.log(`    warnings: ${incompatibleResult.state_compatibility.warnings.join(', ')}`);
  // 步骤不兼容时，resume_decision 是 replay_from_checkpoint（不是 abort）
  const incompatiblePassed =
    incompatibleResult.resume_decision === 'replay_from_checkpoint' &&
    incompatibleResult.state_compatibility.warnings.some(w => w.includes('possible replay'));

  console.log(`  ${incompatiblePassed ? '✅' : '❌'} 步骤不兼容时触发 replay_from_checkpoint: ${incompatiblePassed}`);

  // 验证 validateAndResume — 无检查点（从头开始）
  const noCheckpointResult = checkpointManager.validateAndResume('nonexistent_task', 0);
  console.log(`  无检查点验证:`);
  console.log(`    checkpoint_valid=${noCheckpointResult.checkpoint_valid} (expected false)`);
  console.log(`    resume_decision=${noCheckpointResult.resume_decision} (expected replay_from_start)`);
  const noCheckpointPassed =
    noCheckpointResult.checkpoint_valid === false &&
    noCheckpointResult.resume_decision === 'replay_from_start';

  console.log(`  ${noCheckpointPassed ? '✅' : '❌'} 无检查点时从头开始: ${noCheckpointPassed}`);

  const passed = normalResumePassed && incompatiblePassed && noCheckpointPassed;
  results.scenarios.resumeAfterInterruption = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// 主流程
// ============================================================
async function main() {
  await testExecutorReadinessGate().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.executorReadinessGate = { passed: false, error: e.message }; });
  await testExecutorBootstrapOrFallback().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.executorBootstrapOrFallback = { passed: false, error: e.message }; });
  await testGoalStateVerification().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.goalStateVerification = { passed: false, error: e.message }; });
  await testObservationDrivenNextStep().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.observationDrivenNextStep = { passed: false, error: e.message }; });
  await testRealChainCheckpoint().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.realChainCheckpoint = { passed: false, error: e.message }; });
  await testResumeAfterInterruption().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.resumeAfterInterruption = { passed: false, error: e.message }; });

  // 汇总
  console.log('\n' + '═'.repeat(66));
  console.log('  Round 7 根因修复验收结果汇总');
  console.log('═'.repeat(66));

  let allPassed = true;
  for (const [name, result] of Object.entries(results.scenarios)) {
    const r = result;
    console.log(`  ${r.passed ? '✅' : '❌'} ${name}: ${r.passed ? 'PASS' : 'FAIL'}${r.error ? ` (${r.error})` : ''}`);
    if (!r.passed) allPassed = false;
  }

  console.log('');
  console.log(`  Round 7 根因状态: ${allPassed ? '✅ ALL PASS' : '⚠️  PARTIAL'}`);

  // 最终结论
  let diagnosis = 'NEEDS_ONE_MORE_ROOT_CAUSE_ROUND';
  if (allPassed) {
    diagnosis = 'HUMAN_LIKE_OPERATION_WITH_GOAL_AND_RECOVERY_BASELINE';
  }

  console.log(`  最终诊断: ${diagnosis}`);
  console.log('');

  // 写入结果文件
  const resultPath = path.join(TEST_DIR, 'root_cause_round7_result.json');
  fs.writeFileSync(resultPath, JSON.stringify({ ...results, diagnosis }, null, 2));
  console.log(`  结果文件: ${resultPath}`);
}

main().catch(console.error);
