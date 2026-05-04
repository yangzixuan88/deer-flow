/**
 * M09 Layer2-3 联动测试
 * ================================================
 * 测试 M09 与 M10/M08 的集成
 * Layer2: 监控层 - LLM-Judge 评分 + 执行轨迹记录
 * Layer3: 反馈层 - 质量信号 + 用户反馈 + 贡献归因
 * ================================================
 */

import {
  TaskType,
  PromptPriority,
  PromptFragment,
  PromptFragmentType,
  ExecutionResult,
} from './types';
import {
  LLMWatchdog,
  ExecutionTracker,
  LLMJudge,
} from './layer2_monitor';
import {
  FeedbackCollector,
  UserFeedbackParser,
  ContributionAttributor,
} from './layer3_feedback';
import {
  M10ToM09Adapter,
  M08ToM09Adapter,
  M09M10Coordinator,
  M09M08Coordinator,
} from './integration';

// ============================================
// 测试配置
// ============================================

const TEST_CONFIG = {
  qualityThreshold: 0.7,
  maxRetries: 3,
};

// ============================================
// 辅助函数
// ============================================

function createTestFragment(id: string, content: string, priority: PromptPriority): PromptFragment {
  return {
    id,
    type: PromptFragmentType.TASK,
    content,
    priority,
    quality_score_history: [],
    gepa_version: 0,
    created_at: new Date().toISOString(),
  };
}

// ============================================
// Layer2 监控层测试
// ============================================

export async function testLayer2_Monitor(): Promise<{
  passed: boolean;
  results: { name: string; passed: boolean; error?: string }[];
}> {
  const results: { name: string; passed: boolean; error?: string }[] = [];

  // 测试 1: LLMJudge 评分
  try {
    const judge = new LLMJudge(TEST_CONFIG.qualityThreshold);

    const score = await judge.evaluate(
      '这是一个测试输出，包含了一些有用的信息。',
      {
        taskType: TaskType.SEARCH_SYNTH,
        userInput: '搜索一些信息',
        constraints: ['简洁', '准确'],
      }
    );

    const passed = score.overall >= 0 && score.overall <= 1;
    results.push({
      name: 'LLMJudge 评分',
      passed,
      error: passed ? undefined : `评分异常: ${score.overall}`,
    });
  } catch (e) {
    results.push({ name: 'LLMJudge 评分', passed: false, error: String(e) });
  }

  // 测试 2: LLMJudge shouldRetry 判断
  try {
    const judge = new LLMJudge(0.7);

    const shouldRetryLow = judge.shouldRetry({ overall: 0.5 } as any);
    const shouldRetryHigh = judge.shouldRetry({ overall: 0.85 } as any);

    const passed = shouldRetryLow === true && shouldRetryHigh === false;
    results.push({
      name: 'LLMJudge shouldRetry',
      passed,
      error: passed ? undefined : `重试判断异常: 低分=${shouldRetryLow}, 高分=${shouldRetryHigh}`,
    });
  } catch (e) {
    results.push({ name: 'LLMJudge shouldRetry', passed: false, error: String(e) });
  }

  // 测试 3: ExecutionTracker 轨迹记录
  try {
    const tracker = new ExecutionTracker();

    await tracker.record({
      taskType: TaskType.CODE_GEN,
      fragmentsUsed: ['frag1', 'frag2'],
      qualityScore: 0.85,
      tokenConsumed: 500,
      result: ExecutionResult.SUCCESS,
    });

    await tracker.record({
      taskType: TaskType.DOC_WRITE,
      fragmentsUsed: ['frag3'],
      qualityScore: 0.65,
      tokenConsumed: 300,
      result: ExecutionResult.PARTIAL,
    });

    const stats = tracker.getStats();

    const passed = stats.totalTraces === 2 &&
      stats.avgQualityScore === 0.75 &&
      stats.successRate === 0.5;

    results.push({
      name: 'ExecutionTracker 轨迹记录',
      passed,
      error: passed ? undefined : `统计数据异常: ${JSON.stringify(stats)}`,
    });
  } catch (e) {
    results.push({ name: 'ExecutionTracker 轨迹记录', passed: false, error: String(e) });
  }

  // 测试 4: LLMWatchdog 评估并记录
  try {
    const watchdog = new LLMWatchdog({ qualityThreshold: 0.7, maxRetries: 3 });

    const result = await watchdog.evaluateAndRecord({
      output: '这是高质量的测试输出。',
      taskType: TaskType.SEARCH_SYNTH,
      fragmentsUsed: ['test_frag'],
      tokenConsumed: 200,
      result: ExecutionResult.SUCCESS,
      userInput: '测试输入',
    });

    const passed = result.score.overall > 0 &&
      result.trace.quality_score === result.score.overall &&
      result.shouldRetry === false;

    results.push({
      name: 'LLMWatchdog 评估并记录',
      passed,
      error: passed ? undefined : `评估异常: ${JSON.stringify(result)}`,
    });
  } catch (e) {
    results.push({ name: 'LLMWatchdog 评估并记录', passed: false, error: String(e) });
  }

  return {
    passed: results.every(r => r.passed),
    results,
  };
}

// ============================================
// Layer3 反馈层测试
// ============================================

export async function testLayer3_Feedback(): Promise<{
  passed: boolean;
  results: { name: string; passed: boolean; error?: string }[];
}> {
  const results: { name: string; passed: boolean; error?: string }[] = [];

  // 测试 1: UserFeedbackParser 负面反馈
  try {
    const parser = new UserFeedbackParser();

    const parsed = parser.parse('这个回答太啰嗦了，请简洁点');
    const passed = parsed.sentiment === 'negative' &&
      parsed.improvementDirection === '需要更简洁';

    results.push({
      name: 'UserFeedbackParser 负面反馈解析',
      passed,
      error: passed ? undefined : `解析异常: ${JSON.stringify(parsed)}`,
    });
  } catch (e) {
    results.push({ name: 'UserFeedbackParser 负面反馈解析', passed: false, error: String(e) });
  }

  // 测试 2: UserFeedbackParser 正面反馈
  try {
    const parser = new UserFeedbackParser();

    const parsed = parser.parse('很好，这正是我想要的');
    const passed = parsed.sentiment === 'positive';

    results.push({
      name: 'UserFeedbackParser 正面反馈解析',
      passed,
      error: passed ? undefined : `解析异常: ${JSON.stringify(parsed)}`,
    });
  } catch (e) {
    results.push({ name: 'UserFeedbackParser 正面反馈解析', passed: false, error: String(e) });
  }

  // 测试 3: ContributionAttributor 归因
  try {
    const attributor = new ContributionAttributor();

    const fragments = [
      createTestFragment('frag1', '这是第一个片段', PromptPriority.P3_TASK_SPECIFIC),
      createTestFragment('frag2', '这是第二个片段', PromptPriority.P3_TASK_SPECIFIC),
    ];

    const attributions = attributor.attribute(fragments, 0.85, TaskType.CODE_GEN);

    const passed = attributions.length === 2 &&
      attributions.every(a => a.fragment_id && a.contribution_score > 0);

    results.push({
      name: 'ContributionAttributor 贡献归因',
      passed,
      error: passed ? undefined : `归因异常: ${JSON.stringify(attributions)}`,
    });
  } catch (e) {
    results.push({ name: 'ContributionAttributor 贡献归因', passed: false, error: String(e) });
  }

  // 测试 4: FeedbackCollector 综合采集
  try {
    const collector = new FeedbackCollector();

    // 采集自动信号
    const autoSignals = collector.collectAutoSignal({
      followUpSuccessRate: 0.8,
      userRequestedRedo: false,
    });

    // 采集用户反馈
    const userSignal = collector.collectUserFeedback('格式不太对');

    const passed = autoSignals.length === 2 && userSignal !== undefined;

    results.push({
      name: 'FeedbackCollector 综合采集',
      passed,
      error: passed ? undefined : `采集异常: auto=${autoSignals.length}, user=${userSignal}`,
    });
  } catch (e) {
    results.push({ name: 'FeedbackCollector 综合采集', passed: false, error: String(e) });
  }

  return {
    passed: results.every(r => r.passed),
    results,
  };
}

// ============================================
// M10 集成测试
// ============================================

export async function testM10_Integration(): Promise<{
  passed: boolean;
  results: { name: string; passed: boolean; error?: string }[];
}> {
  const results: { name: string; passed: boolean; error?: string }[] = [];

  // 测试 1: M10ToM09Adapter 任务类型映射
  try {
    const adapter = new M10ToM09Adapter();

    const codeType = adapter.mapTaskType({
      goal: '帮我写一段代码',
      task_category: 'code_gen',
    });

    const docType = adapter.mapTaskType({
      goal: '写一个文档',
      task_category: 'doc_write',
    });

    const passed = codeType === TaskType.CODE_GEN && docType === TaskType.DOC_WRITE;

    results.push({
      name: 'M10ToM09Adapter 任务类型映射',
      passed,
      error: passed ? undefined : `映射异常: code=${codeType}, doc=${docType}`,
    });
  } catch (e) {
    results.push({ name: 'M10ToM09Adapter 任务类型映射', passed: false, error: String(e) });
  }

  // 测试 2: M10ToM09Adapter 安全约束映射
  try {
    const adapter = new M10ToM09Adapter();

    const fragments = adapter.mapSafetyConstraints({
      deadline: '2026-04-15',
      budget_tokens: 1000,
      quality_bar: '高质量',
    });

    const passed = fragments.length === 3 &&
      fragments.every(f => f.priority === PromptPriority.P1_SAFETY);

    results.push({
      name: 'M10ToM09Adapter 安全约束映射',
      passed,
      error: passed ? undefined : `约束异常: ${fragments.length}`,
    });
  } catch (e) {
    results.push({ name: 'M10ToM09Adapter 安全约束映射', passed: false, error: String(e) });
  }

  // 测试 3: M09M10Coordinator 请求澄清
  try {
    const coordinator = new M09M10Coordinator();

    const questions = coordinator.requestClarification('帮我看看这个错误');

    const passed = questions.length > 0 &&
      questions.every(q => q.dimension && q.question);

    results.push({
      name: 'M09M10Coordinator 请求澄清',
      passed,
      error: passed ? undefined : `澄清异常: ${JSON.stringify(questions)}`,
    });
  } catch (e) {
    results.push({ name: 'M09M10Coordinator 请求澄清', passed: false, error: String(e) });
  }

  return {
    passed: results.every(r => r.passed),
    results,
  };
}

// ============================================
// M08 集成测试
// ============================================

export async function testM08_Integration(): Promise<{
  passed: boolean;
  results: { name: string; passed: boolean; error?: string }[];
}> {
  const results: { name: string; passed: boolean; error?: string }[] = [];

  // 测试 1: M08ToM09Adapter 轨迹转换
  try {
    const adapter = new M08ToM09Adapter();

    const experience = {
      session_id: 'test_session_001',
      timestamp: new Date().toISOString(),
      task_type: 'code_gen',
      intent_profile: { goal: '写代码' },
      tool_calls: [
        { tool: 'bash', input: 'echo test', output: 'test', duration_ms: 100, success: true },
      ],
      final_output: '代码输出',
      quality_score: 0.85,
      token_cost: 500,
      ge_path: 'initial',
      patterns: [],
    };

    const trace = adapter.convertToExecutionTrace(experience);

    const passed = trace.task_type === TaskType.CODE_GEN &&
      trace.quality_score === 0.85 &&
      trace.result === ExecutionResult.SUCCESS;

    results.push({
      name: 'M08ToM09Adapter 轨迹转换',
      passed,
      error: passed ? undefined : `转换异常: ${JSON.stringify(trace)}`,
    });
  } catch (e) {
    results.push({ name: 'M08ToM09Adapter 轨迹转换', passed: false, error: String(e) });
  }

  // 测试 2: M08ToM09Adapter 低分提取
  try {
    const adapter = new M08ToM09Adapter();

    const experiences = [
      { session_id: '1', quality_score: 0.85 } as any,
      { session_id: '2', quality_score: 0.55 } as any,
      { session_id: '3', quality_score: 0.45 } as any,
      { session_id: '4', quality_score: 0.92 } as any,
    ];

    const lowScore = adapter.extractLowScoreTraces(experiences, 0.7);

    const passed = lowScore.length === 2 &&
      lowScore.every(e => e.quality_score < 0.7);

    results.push({
      name: 'M08ToM09Adapter 低分提取',
      passed,
      error: passed ? undefined : `提取异常: ${lowScore.length}`,
    });
  } catch (e) {
    results.push({ name: 'M08ToM09Adapter 低分提取', passed: false, error: String(e) });
  }

  // 测试 3: M09M08Coordinator GEPA数据准备
  try {
    const coordinator = new M09M08Coordinator();

    const experiences = [
      {
        session_id: '1',
        timestamp: new Date().toISOString(),
        task_type: 'search',
        intent_profile: {},
        tool_calls: [],
        final_output: '',
        quality_score: 0.85,
        token_cost: 200,
        ge_path: '',
        patterns: [{ pattern_id: 'p1', description: '测试模式', reusable: true }],
      },
    ] as any;

    const gepaData = coordinator.prepareGepaData(experiences);

    const passed = gepaData.highScoreTraces.length === 1 &&
      gepaData.reusablePatterns.length === 1;

    results.push({
      name: 'M09M08Coordinator GEPA数据准备',
      passed,
      error: passed ? undefined : `数据准备异常: ${JSON.stringify(gepaData)}`,
    });
  } catch (e) {
    results.push({ name: 'M09M08Coordinator GEPA数据准备', passed: false, error: String(e) });
  }

  return {
    passed: results.every(r => r.passed),
    results,
  };
}

// ============================================
// 运行所有测试
// ============================================

export async function runAllTests(): Promise<void> {
  console.log('========================================');
  console.log('M09 Layer2-3 & M10/M08 集成测试');
  console.log('========================================\n');

  const allResults: { category: string; passed: boolean; results: any[] }[] = [];

  // Layer2 测试
  console.log('测试 Layer2 监控层...');
  const layer2Results = await testLayer2_Monitor();
  allResults.push({ category: 'Layer2 监控层', ...layer2Results });
  console.log(`  通过: ${layer2Results.results.filter(r => r.passed).length}/${layer2Results.results.length}\n`);

  // Layer3 测试
  console.log('测试 Layer3 反馈层...');
  const layer3Results = await testLayer3_Feedback();
  allResults.push({ category: 'Layer3 反馈层', ...layer3Results });
  console.log(`  通过: ${layer3Results.results.filter(r => r.passed).length}/${layer3Results.results.length}\n`);

  // M10 集成测试
  console.log('测试 M10 集成...');
  const m10Results = await testM10_Integration();
  allResults.push({ category: 'M10 集成', ...m10Results });
  console.log(`  通过: ${m10Results.results.filter(r => r.passed).length}/${m10Results.results.length}\n`);

  // M08 集成测试
  console.log('测试 M08 集成...');
  const m08Results = await testM08_Integration();
  allResults.push({ category: 'M08 集成', ...m08Results });
  console.log(`  通过: ${m08Results.results.filter(r => r.passed).length}/${m08Results.results.length}\n`);

  // 汇总
  console.log('========================================');
  console.log('测试汇总');
  console.log('========================================');

  for (const result of allResults) {
    const status = result.passed ? '✅' : '❌';
    console.log(`${status} ${result.category}: ${result.results.filter(r => r.passed).length}/${result.results.length}`);
  }

  const totalPassed = allResults.reduce(
    (sum, r) => sum + r.results.filter(r => r.passed).length,
    0
  );
  const totalTests = allResults.reduce((sum, r) => sum + r.results.length, 0);

  console.log(`\n总计: ${totalPassed}/${totalTests} 通过`);

  if (totalPassed === totalTests) {
    console.log('\n🎉 所有测试通过！');
  } else {
    console.log('\n⚠️ 部分测试失败，请检查上方输出。');
  }
}

// 导出测试结果类型
export interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
}

export interface TestCategoryResult {
  category: string;
  passed: boolean;
  results: TestResult[];
}
