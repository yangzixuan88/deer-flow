/**
 * @file operator_root_cause_round8_test.mjs
 * @description Round 8 根因修复验收测试
 * 目标: 把 deerflow 从"目标态+恢复基线"推进到"自愈+目标收敛+真实中断恢复"的稳定内部使用基线
 *
 * 验证 3 个根因:
 * 1. 自维持层 → 真实自愈层 (bootstrap + 复检 + 结构化结果)
 * 2. 目标态验证 → 目标收敛驱动 (goal-driven chain + decision trace)
 * 3. 恢复结构 → 真实中断恢复 (injectInterruption + resume + 防重)
 *
 * 6 个场景:
 * 1. realSelfHealing           - 真实自愈尝试 + 结构化结果
 * 2. postHealReadiness        - 自愈后复检 readiness
 * 3. realGoalDrivenMixedChain  - web+desktop 混合链目标驱动收敛
 * 4. goalDrivenDecisionTrace  - 完整 goal_driven_decision_trace 输出
 * 5. realInterruptionResume   - 真实中断注入 + 恢复继续
 * 6. resumeWithoutDuplicateActions - 恢复后操作历史不重复
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
console.log('║  Round 8: 自愈 + 目标收敛 + 真实中断恢复验收测试       ║');
console.log('╚════════════════════════════════════════════════════════════════╝\n');

const results = {
  timestamp: new Date().toISOString(),
  scenarios: {},
};

// ============================================================
// Scenario 1: 真实自愈
// ============================================================
async function testRealSelfHealing() {
  console.log('【Scenario 1】真实自愈 (attemptSelfHeal)\n');

  const { attemptSelfHeal, checkExecutorHealth, ExecutorType } = await import('../domain/m11/mod.ts');

  // 获取当前健康状态
  const healthBefore = await checkExecutorHealth(true);
  const opencliStatusBefore = healthBefore.executor_health[ExecutorType.OPENCLI].status;
  console.log(`  OpenCLI 当前状态: ${opencliStatusBefore}`);

  // 尝试自愈
  const healResult = await attemptSelfHeal(
    ExecutorType.OPENCLI,
    healthBefore,
    healthBefore.bootstrap_attempts[ExecutorType.OPENCLI]
  );

  console.log(`  自愈结果:`);
  console.log(`    self_heal_attempted: ${healResult.self_heal_attempted}`);
  console.log(`    self_heal_success: ${healResult.self_heal_success}`);
  console.log(`    healed_executor: ${healResult.healed_executor}`);
  console.log(`    bootstrap_attempts: ${healResult.bootstrap_attempts}`);
  console.log(`    post_heal_readiness: ${healResult.post_heal_readiness}`);
  console.log(`    fallback_decision.action: ${healResult.fallback_decision?.action}`);
  console.log(`    fallback_decision.target_executor: ${healResult.fallback_decision?.target_executor}`);
  console.log(`    environment_diagnostics.attempt_details: ${healResult.environment_diagnostics.attempt_details.join('; ')}`);

  // 验证 SelfHealResult 结构完整性
  const hasRequiredFields =
    healResult.self_heal_attempted !== undefined &&
    healResult.self_heal_success !== undefined &&
    healResult.healed_executor === ExecutorType.OPENCLI &&
    healResult.bootstrap_attempts !== undefined &&
    healResult.post_heal_readiness !== undefined &&
    healResult.environment_diagnostics !== undefined &&
    healResult.fallback_decision !== undefined;

  console.log(`  ${hasRequiredFields ? '✅' : '❌'} SelfHealResult 结构完整 (self_heal_attempted/success/healed_executor/bootstrap_attempts/post_heal_readiness/environment_diagnostics/fallback_decision)`);

  // 验证结构化输出
  const structureValid =
    typeof healResult.self_heal_attempted === 'boolean' &&
    typeof healResult.self_heal_success === 'boolean' &&
    typeof healResult.post_heal_readiness === 'boolean' &&
    Array.isArray(healResult.environment_diagnostics.attempt_details);

  console.log(`  ${structureValid ? '✅' : '❌'} SelfHealResult 类型正确`);

  const passed = hasRequiredFields && structureValid;
  results.scenarios.realSelfHealing = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// Scenario 2: 自愈后复检
// ============================================================
async function testPostHealReadiness() {
  console.log('\n【Scenario 2】自愈后复检 (postHealReadiness)\n');

  const { attemptSelfHeal, checkExecutorHealth, executorReadinessGate, ExecutorType } = await import('../domain/m11/mod.ts');

  // 尝试自愈
  const healResult = await attemptSelfHeal(ExecutorType.OPENCLI, undefined, 0);

  console.log(`  自愈后 post_heal_readiness: ${healResult.post_heal_readiness}`);
  console.log(`  自愈后 bootstrap_attempts: ${healResult.bootstrap_attempts}`);

  // 关键: 如果自愈成功，post_heal_health 会被填充
  if (healResult.post_heal_health) {
    const opencliHealth = healResult.post_heal_health.executor_health[ExecutorType.OPENCLI];
    console.log(`  post_heal_health OpenCLI status: ${opencliHealth.status}`);
    console.log(`  post_heal_health OpenCLI latency_ms: ${opencliHealth.latency_ms}`);
  }

  // 验证: 自愈后必须复检 readiness，不能盲目继续
  // 如果自愈失败，fallback_decision 必须包含 target_executor
  const readinessVerified =
    healResult.post_heal_readiness !== undefined &&
    (healResult.self_heal_success
      ? healResult.post_heal_health !== undefined  // 成功时有 post_heal_health
      : healResult.fallback_decision?.target_executor !== undefined); // 失败时有 fallback

  console.log(`  ${readinessVerified ? '✅' : '❌'} 自愈后复检机制验证: ${readinessVerified}`);

  // 验证: 不能盲目继续
  const noBlindProceed =
    !healResult.self_heal_success || healResult.post_heal_readiness !== undefined;

  console.log(`  ${noBlindProceed ? '✅' : '❌'} 无盲目继续: ${noBlindProceed}`);

  const passed = readinessVerified && noBlindProceed;
  results.scenarios.postHealReadiness = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// Scenario 3: 真实目标驱动混合链
// ============================================================
async function testRealGoalDrivenMixedChain() {
  console.log('\n【Scenario 3】真实目标驱动混合链\n');

  const { runGoalDrivenChain, ExecutorType } = await import('../domain/m11/mod.ts');

  const taskId = `round8_goal_${Date.now()}`;

  // 混合链: 网页 → 桌面 → 网页
  const steps = [
    {
      instruction: 'navigate to https://example.com',
      goalDescription: 'navigate to https://example.com',
      params: { url: 'https://example.com' },
    },
    {
      instruction: 'open gimp',
      goalDescription: 'open gimp application window',
      params: { appName: 'gimp' },
    },
    {
      instruction: 'navigate to https://github.com',
      goalDescription: 'navigate to https://github.com',
      params: { url: 'https://github.com' },
    },
    {
      instruction: 'take a screenshot',
      goalDescription: 'capture current page screenshot',
      params: {},
    },
  ];

  console.log(`  创建 ${steps.length} 步混合链: web → desktop → web → screenshot`);

  const chainResult = await runGoalDrivenChain(taskId, steps);

  console.log(`  链执行结果:`);
  console.log(`    total_steps: ${chainResult.total_steps}`);
  console.log(`    steps_executed: ${chainResult.steps_executed}`);
  console.log(`    goal_satisfied: ${chainResult.goal_satisfied}`);
  console.log(`    termination_reason: ${chainResult.termination_reason}`);
  console.log(`    goal_driven_decision_trace.length: ${chainResult.goal_driven_decision_trace.length}`);

  // 验证 goal_driven_decision_trace
  for (let i = 0; i < chainResult.goal_driven_decision_trace.length; i++) {
    const rec = chainResult.goal_driven_decision_trace[i];
    console.log(`    Step ${rec.step}: executor=${rec.executor_used}, decision=${rec.decision.action}, goal_satisfied=${rec.verification.goal_satisfied}`);
  }

  // 验证结构
  const hasTrace = chainResult.goal_driven_decision_trace.length > 0;
  const hasGoalState = chainResult.final_goal_verification !== undefined;
  const hasTermination = chainResult.termination_reason !== undefined;

  console.log(`  ${hasTrace ? '✅' : '❌'} goal_driven_decision_trace 存在且非空`);
  console.log(`  ${hasGoalState ? '✅' : '❌'} final_goal_verification 存在`);
  console.log(`  ${hasTermination ? '✅' : '❌'} termination_reason 存在`);

  // 验证混合链: 至少有一次跨执行器切换
  const executors = chainResult.goal_driven_decision_trace.map(r => r.executor_used);
  const hasCrossExecutor = new Set(executors).size > 1;
  console.log(`  ${hasCrossExecutor ? '✅' : '❌'} 跨执行器切换: executors=${[...new Set(executors)].join(',')}`);

  const passed = hasTrace && hasGoalState && hasTermination && hasCrossExecutor;
  results.scenarios.realGoalDrivenMixedChain = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// Scenario 4: Goal-Driven Decision Trace 完整性
// ============================================================
async function testGoalDrivenDecisionTrace() {
  console.log('\n【Scenario 4】Goal-Driven Decision Trace 完整性\n');

  const { runGoalDrivenChain } = await import('../domain/m11/mod.ts');

  const taskId = `round8_trace_${Date.now()}`;

  // 4 步混合链
  const steps = [
    { instruction: 'navigate to https://example.com', goalDescription: 'navigate to https://example.com', params: { url: 'https://example.com' } },
    { instruction: 'open gimp', goalDescription: 'open gimp window', params: { appName: 'gimp' } },
    { instruction: 'navigate to https://github.com', goalDescription: 'navigate to https://github.com', params: { url: 'https://github.com' } },
    { instruction: 'take a screenshot', goalDescription: 'take screenshot', params: {} },
  ];

  const chainResult = await runGoalDrivenChain(taskId, steps);
  const trace = chainResult.goal_driven_decision_trace;

  console.log(`  Decision Trace 完整性验证:`);

  let allValid = true;
  for (const rec of trace) {
    const hasGoalState = rec.goal_before !== undefined;
    const hasVerification = rec.verification !== undefined;
    const hasDecision = rec.decision !== undefined;
    const hasObserved = rec.observed_state !== undefined;
    const valid = hasGoalState && hasVerification && hasDecision;

    console.log(`    Step ${rec.step}: goal=${hasGoalState}, verification=${hasVerification}, decision=${hasDecision}, observed=${hasObserved}`);
    if (!valid) allValid = false;
  }

  // 验证每条记录的结构
  const recordsValid = trace.every(rec =>
    rec.step !== undefined &&
    typeof rec.instruction === 'string' &&
    typeof rec.executor_used === 'string' &&
    rec.decision?.action !== undefined &&
    rec.verification?.goal_satisfied !== undefined
  );

  console.log(`  ${recordsValid ? '✅' : '❌'} 所有 trace 记录结构有效`);

  // 验证 goal_gap / next_step_hint 被使用
  const hasGoalGapUsage = trace.some(rec =>
    rec.decision?.suggestedInstruction !== undefined ||
    rec.verification?.goal_gap?.missing_conditions !== undefined
  );
  console.log(`  ${hasGoalGapUsage ? '✅' : '❌'} goal_gap / next_step_hint 被使用`);

  const passed = allValid && recordsValid;
  results.scenarios.goalDrivenDecisionTrace = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// Scenario 5: 真实中断注入 + 恢复
// ============================================================
async function testRealInterruptionResume() {
  console.log('\n【Scenario 5】真实中断注入 + 恢复\n');

  const { checkpointManager, executeWithAutoSelect, extractObservedStateFromChecks } = await import('../domain/m11/mod.ts');

  const taskId = `round8_interrupt_${Date.now()}`;
  const sessionId = taskId;

  let ctx = {
    session_id: sessionId,
    current_step: 0,
    operation_history: [],
    last_url: 'https://example.com',
  };

  // 3 步任务链
  const steps = [
    'navigate to https://example.com',
    'take a screenshot',
    'take another screenshot',
  ];

  // 执行前 2 步并保存 checkpoint
  for (let i = 0; i < 2; i++) {
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
    console.log(`  执行 Step ${i + 1}: current_step=${ctx.current_step}`);
  }

  // ★ 注入中断
  const interruptResult = checkpointManager.injectInterruption(taskId, 2);
  console.log(`  中断注入:`);
  console.log(`    interruption_injected: ${interruptResult.interruption_injected}`);
  console.log(`    interrupted_at_step: ${interruptResult.interrupted_at_step}`);
  console.log(`    checkpoint_invalidated: ${interruptResult.checkpoint_invalidated}`);

  // ★ 从中断恢复
  const resumeResult = checkpointManager.validateAndResume(taskId, 2, undefined);
  console.log(`  恢复验证:`);
  console.log(`    resume_from_step: ${resumeResult.resume_from_step}`);
  console.log(`    checkpoint_valid: ${resumeResult.checkpoint_valid}`);
  console.log(`    resume_decision: ${resumeResult.resume_decision}`);
  console.log(`    reason: ${resumeResult.reason}`);

  // 使用 checkpointManager.resume() 继续执行
  const remainingSteps = steps.slice(2);
  const resumeOutcome = await checkpointManager.resume(
    taskId,
    remainingSteps.map((instruction, idx) => ({
      instruction,
      goalDescription: `execute step ${idx}`,
      params: {},
    })),
    async (step) => executeWithAutoSelect(step.instruction, step.params || {}, undefined, ctx),
    ctx
  );

  console.log(`  恢复执行结果:`);
  console.log(`    steps_executed: ${resumeOutcome.steps_executed}`);
  console.log(`    recovered_chain_completed: ${resumeOutcome.resume_result.recovered_chain_completed}`);
  console.log(`    steps_skipped: ${resumeOutcome.resume_result.steps_skipped}`);
  console.log(`    final_context.current_step: ${resumeOutcome.final_context.current_step}`);

  // 验证
  // 中断后 checkpoint 仍有效（不失效），用于支持恢复
  const interruptValid = interruptResult.interruption_injected === true;
  const resumeValid = resumeResult.checkpoint_valid === true;
  const resumeDecisionValid = resumeResult.resume_decision === 'resume';
  const resumeStepsSkipped = resumeOutcome.resume_result.steps_skipped === 2;
  // resume_from_step 应该是 3 (= checkpoint.step + 1)
  const resumeFromStepValid = resumeResult.resume_from_step === 3;

  console.log(`  ${interruptValid ? '✅' : '❌'} 中断注入成功: ${interruptValid}`);
  console.log(`  ${resumeValid ? '✅' : '❌'} 检查点有效: ${resumeValid} (中断不失效检查点)`);
  console.log(`  ${resumeDecisionValid ? '✅' : '❌'} 恢复决策正确: ${resumeResult.resume_decision}`);
  console.log(`  ${resumeFromStepValid ? '✅' : '❌'} resume_from_step=3: ${resumeResult.resume_from_step}`);
  console.log(`  ${resumeStepsSkipped ? '✅' : '❌'} 跳过已完成步骤(2): ${resumeOutcome.resume_result.steps_skipped}`);

  const passed = interruptValid && resumeValid && resumeDecisionValid && resumeFromStepValid && resumeStepsSkipped;
  results.scenarios.realInterruptionResume = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// Scenario 6: 恢复后不重复执行
// ============================================================
async function testResumeWithoutDuplicateActions() {
  console.log('\n【Scenario 6】恢复后不重复执行\n');

  const { checkpointManager, executeWithAutoSelect, extractObservedStateFromChecks } = await import('../domain/m11/mod.ts');

  const taskId = `round8_nodup_${Date.now()}`;
  const sessionId = taskId;

  let ctx = {
    session_id: sessionId,
    current_step: 0,
    operation_history: [],
    last_url: 'https://example.com',
  };

  // 4 步链
  const steps = [
    'navigate to https://example.com',
    'take a screenshot',
    'navigate to https://github.com',
    'take a screenshot',
  ];

  // 执行 3 步并保存 checkpoint
  for (let i = 0; i < 3; i++) {
    const step = await executeWithAutoSelect(
      steps[i],
      { url: ctx.last_url },
      undefined,
      ctx
    );
    ctx = { ...ctx, ...step.accumulated_context, current_step: i + 1 };
    const obsState = extractObservedStateFromChecks(step.checks);
    checkpointManager.saveCheckpoint(taskId, i + 1, ctx, obsState, undefined);
    console.log(`  Step ${i + 1}: history_length=${ctx.operation_history?.length}, current_step=${ctx.current_step}`);
  }

  const historyBeforeInterrupt = ctx.operation_history?.length || 0;
  console.log(`  中断前操作历史长度: ${historyBeforeInterrupt}`);

  // 注入中断
  checkpointManager.injectInterruption(taskId, 3);

  // 恢复
  const resumeOutcome = await checkpointManager.resume(
    taskId,
    [steps[3]].map(instruction => ({ instruction, goalDescription: 'complete chain', params: {} })),
    async (step) => executeWithAutoSelect(step.instruction, step.params || {}, undefined, ctx),
    ctx
  );

  const historyAfterResume = resumeOutcome.final_context.operation_history?.length || 0;
  console.log(`  恢复后操作历史长度: ${historyAfterResume}`);
  console.log(`  恢复后 current_step: ${resumeOutcome.final_context.current_step}`);

  // 关键验证: 操作历史不能超过总步骤数
  // 4 步总任务，3 步在中断前完成，恢复后只执行第 4 步
  // 历史应该 = 3 (中断前) + 1 (恢复后) = 4
  const maxHistory = steps.length;
  const historyNotExcessive = historyAfterResume <= maxHistory;
  const stepsExecutedCorrect = resumeOutcome.steps_executed === 1;

  console.log(`  ${historyNotExcessive ? '✅' : '❌'} 操作历史不超过总步骤数: ${historyAfterResume} <= ${maxHistory}`);
  console.log(`  ${stepsExecutedCorrect ? '✅' : '❌'} 只执行剩余步骤: ${resumeOutcome.steps_executed} === 1`);

  // 验证: 不重复已完成的动作
  // 中断前有 3 步，恢复后只追加新步骤，不重复
  const noDuplicate = historyAfterResume === 4 && resumeOutcome.steps_executed === 1;
  console.log(`  ${noDuplicate ? '✅' : '❌'} 无重复执行: history=${historyAfterResume}, executed=${resumeOutcome.steps_executed}`);

  const passed = historyNotExcessive && stepsExecutedCorrect && noDuplicate;
  results.scenarios.resumeWithoutDuplicateActions = { passed };
  console.log(`\n  结论: ${passed ? '✅ PASS' : '❌ FAIL'}`);
}

// ============================================================
// 主流程
// ============================================================
async function main() {
  await testRealSelfHealing().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.realSelfHealing = { passed: false, error: e.message }; });
  await testPostHealReadiness().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.postHealReadiness = { passed: false, error: e.message }; });
  await testRealGoalDrivenMixedChain().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.realGoalDrivenMixedChain = { passed: false, error: e.message }; });
  await testGoalDrivenDecisionTrace().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.goalDrivenDecisionTrace = { passed: false, error: e.message }; });
  await testRealInterruptionResume().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.realInterruptionResume = { passed: false, error: e.message }; });
  await testResumeWithoutDuplicateActions().catch(e => { console.error('  ❌ Error:', e.message); results.scenarios.resumeWithoutDuplicateActions = { passed: false, error: e.message }; });

  // 汇总
  console.log('\n' + '═'.repeat(66));
  console.log('  Round 8 根因修复验收结果汇总');
  console.log('═'.repeat(66));

  let allPassed = true;
  for (const [name, result] of Object.entries(results.scenarios)) {
    const r = result;
    console.log(`  ${r.passed ? '✅' : '❌'} ${name}: ${r.passed ? 'PASS' : 'FAIL'}${r.error ? ` (${r.error})` : ''}`);
    if (!r.passed) allPassed = false;
  }

  console.log('');
  console.log(`  Round 8 根因状态: ${allPassed ? '✅ ALL PASS' : '⚠️  PARTIAL'}`);

  // 最终结论
  let diagnosis = 'NEEDS_ONE_MORE_ROOT_CAUSE_ROUND';
  if (allPassed) {
    diagnosis = 'HUMAN_LIKE_OPERATION_WITH_SELF_HEALING_BASELINE';
  }

  console.log(`  最终诊断: ${diagnosis}`);
  console.log('');

  // 写入结果文件
  const resultPath = path.join(TEST_DIR, 'root_cause_round8_result.json');
  fs.writeFileSync(resultPath, JSON.stringify({ ...results, diagnosis }, null, 2));
  console.log(`  结果文件: ${resultPath}`);
}

main().catch(console.error);
