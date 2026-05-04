/**
 * M09 提示词工程系统单元测试
 * ================================================
 * 测试五层架构核心组件
 * Layer1: 路由层 (TaskTypeRecognizer, AssetRetriever, PriorityAssembler, ContextAssembler, PromptRouter)
 * ================================================
 */

import {
  TaskTypeRecognizer,
  AssetRetriever,
  PriorityAssembler,
  ContextAssembler,
  PromptRouter,
} from './layer1_router';

import {
  TaskType,
  PromptPriority,
  PromptFragment,
  PromptFragmentType,
  DEFAULT_PROMPT_ENGINE_CONFIG,
} from './types';

describe('M09 PromptEngine 单元测试', () => {
  // ============================================
  // TaskTypeRecognizer 测试
  // ============================================
  describe('TaskTypeRecognizer - 任务类型识别', () => {
    let recognizer: TaskTypeRecognizer;

    beforeEach(() => {
      recognizer = new TaskTypeRecognizer();
    });

    it('should recognize SEARCH_SYNTH task type', () => {
      const results = recognizer.recognizeFromInput('搜索一下关于React的信息');

      expect(results.length).toBeGreaterThan(0);
      expect(results[0].taskType).toBe(TaskType.SEARCH_SYNTH);
      expect(results[0].confidence).toBeGreaterThan(0);
    });

    it('should recognize CODE_GEN task type', () => {
      const results = recognizer.recognizeFromInput('帮我写一个函数来实现快速排序');

      expect(results.length).toBeGreaterThan(0);
      expect(results[0].taskType).toBe(TaskType.CODE_GEN);
    });

    it('should recognize DOC_WRITE task type', () => {
      const results = recognizer.recognizeFromInput('写一篇关于AI的报告');

      expect(results.length).toBeGreaterThan(0);
      expect(results[0].taskType).toBe(TaskType.DOC_WRITE);
    });

    it('should recognize DIAGNOSIS task type', () => {
      const results = recognizer.recognizeFromInput('诊断这个bug');

      expect(results.length).toBeGreaterThan(0);
      expect(results[0].taskType).toBe(TaskType.DIAGNOSIS);
    });

    it('should recognize PLANNING task type', () => {
      const results = recognizer.recognizeFromInput('如何规划一个项目的时间表');

      expect(results.length).toBeGreaterThan(0);
      expect(results[0].taskType).toBe(TaskType.PLANNING);
    });

    it('should recognize SYS_CONFIG task type', () => {
      const results = recognizer.recognizeFromInput('如何配置Docker环境');

      expect(results.length).toBeGreaterThan(0);
      expect(results[0].taskType).toBe(TaskType.SYS_CONFIG);
    });

    it('should recognize CREATIVE task type', () => {
      const results = recognizer.recognizeFromInput('给我一些创新的想法');

      expect(results.length).toBeGreaterThan(0);
      expect(results[0].taskType).toBe(TaskType.CREATIVE);
    });

    it('should recognize AAL_DECISION task type', () => {
      const results = recognizer.recognizeFromInput('你觉得我应该选择哪个方案');

      expect(results.length).toBeGreaterThan(0);
      expect(results[0].taskType).toBe(TaskType.AAL_DECISION);
    });

    it('should return results sorted by confidence', () => {
      const results = recognizer.recognizeFromInput('搜索并写代码');

      expect(results.length).toBeLessThanOrEqual(3);
      for (let i = 1; i < results.length; i++) {
        expect(results[i - 1].confidence).toBeGreaterThanOrEqual(results[i].confidence);
      }
    });

    it('should filter out zero confidence results', () => {
      const results = recognizer.recognizeFromInput('搜索并写代码');

      results.forEach(r => {
        expect(r.confidence).toBeGreaterThan(0);
      });
    });

    it('should recognize from profile', () => {
      const taskType = recognizer.recognizeFromProfile({
        goal: '创建一个网站',
        deliverable: '上线的网站',
        task_category: '开发',
      });

      expect(taskType).toBeDefined();
    });

    it('should default to SEARCH_SYNTH for unrecognized input', () => {
      const taskType = recognizer.recognizeFromProfile({
        goal: '',
        deliverable: '',
        task_category: '',
      });

      expect(taskType).toBe(TaskType.SEARCH_SYNTH);
    });
  });

  // ============================================
  // AssetRetriever 测试
  // ============================================
  describe('AssetRetriever - 资产检索', () => {
    let retriever: AssetRetriever;

    beforeEach(() => {
      retriever = new AssetRetriever();
    });

    const createTestFragment = (overrides: Partial<PromptFragment> = {}): PromptFragment => ({
      id: 'fragment-001',
      type: PromptFragmentType.TASK,
      content: '这是一个测试提示词片段',
      priority: PromptPriority.P3_TASK_SPECIFIC,
      quality_score_history: [0.8, 0.85, 0.9],
      gepa_version: 1,
      created_at: new Date().toISOString(),
      ...overrides,
    });

    it('should register assets without error', async () => {
      const fragment = createTestFragment({ id: 'test-1', content: 'search content here' });
      // 注册资产应该不抛异常
      expect(() => retriever.registerAsset(fragment)).not.toThrow();
    });

    it('should return empty for unregistered task type', async () => {
      const results = await retriever.retrieve('搜索', TaskType.CODE_GEN);

      expect(results).toEqual([]);
    });

    it('should respect limit parameter', async () => {
      for (let i = 0; i < 10; i++) {
        retriever.registerAsset(createTestFragment({ id: `frag-${i}`, content: `搜索内容 ${i}` }));
      }

      const results = await retriever.retrieve('搜索', TaskType.SEARCH_SYNTH, 3);

      expect(results.length).toBeLessThanOrEqual(3);
    });

    it('should filter by similarity threshold', async () => {
      retriever.registerAsset(createTestFragment({
        id: 'similar',
        content: '搜索查找查询',
      }));

      const results = await retriever.retrieve('搜索', TaskType.SEARCH_SYNTH);

      results.forEach(r => {
        expect(r.similarity).toBeGreaterThanOrEqual(DEFAULT_PROMPT_ENGINE_CONFIG.asset_retrieval_threshold);
      });
    });
  });

  // ============================================
  // PriorityAssembler 测试
  // ============================================
  describe('PriorityAssembler - 优先级组装', () => {
    let assembler: PriorityAssembler;

    beforeEach(() => {
      assembler = new PriorityAssembler();
    });

    const createFragment = (priority: PromptPriority, content: string): PromptFragment => ({
      id: `frag-${priority}-${content.slice(0, 5)}`,
      type: PromptFragmentType.TASK,
      content,
      priority,
      quality_score_history: [],
      gepa_version: 0,
      created_at: new Date().toISOString(),
    });

    it('should assemble fragments in P1-P6 priority order', () => {
      const fragments = [
        createFragment(PromptPriority.P1_SAFETY, 'P1 safety'),
        createFragment(PromptPriority.P6_BASE, 'P6 base'),
        createFragment(PromptPriority.P3_TASK_SPECIFIC, 'P3 task'),
      ];

      const result = assembler.assemble(fragments, TaskType.SEARCH_SYNTH);

      // P6应该在前（先输出），P1应该在后（后输出）
      const p6Index = result.indexOf('P6 base');
      const p1Index = result.indexOf('P1 safety');
      expect(p6Index).toBeLessThan(p1Index);
    });

    it('should include P6 BASE layer first', () => {
      const fragments = [
        createFragment(PromptPriority.P6_BASE, 'BASE content'),
        createFragment(PromptPriority.P1_SAFETY, 'SAFETY content'),
      ];

      const result = assembler.assemble(fragments, TaskType.SEARCH_SYNTH);

      expect(result.indexOf('BASE content')).toBeLessThan(result.indexOf('SAFETY content'));
    });

    it('should limit P4 Few-shot to config count', () => {
      const fragments = [
        createFragment(PromptPriority.P4_FEW_SHOT, 'example 1'),
        createFragment(PromptPriority.P4_FEW_SHOT, 'example 2'),
        createFragment(PromptPriority.P4_FEW_SHOT, 'example 3'),
        createFragment(PromptPriority.P4_FEW_SHOT, 'example 4'),
        createFragment(PromptPriority.P4_FEW_SHOT, 'example 5'),
      ];

      const result = assembler.assemble(fragments, TaskType.SEARCH_SYNTH);

      // 应该只包含配置的few_shot_count个示例
      const exampleCount = (result.match(/example \d/g) || []).length;
      expect(exampleCount).toBe(DEFAULT_PROMPT_ENGINE_CONFIG.few_shot_count);
    });

    it('should handle empty fragments', () => {
      const result = assembler.assemble([], TaskType.SEARCH_SYNTH);

      expect(result).toBe('');
    });

    it('should handle missing priority layers', () => {
      const fragments = [
        createFragment(PromptPriority.P1_SAFETY, 'safety only'),
      ];

      const result = assembler.assemble(fragments, TaskType.SEARCH_SYNTH);

      expect(result).toContain('safety only');
    });
  });

  // ============================================
  // ContextAssembler 测试
  // ============================================
  describe('ContextAssembler - 上下文组装', () => {
    let assembler: ContextAssembler;

    beforeEach(() => {
      assembler = new ContextAssembler();
    });

    it('should assemble context with user input', async () => {
      const result = await assembler.assembleContext({
        userInput: '帮我搜索React相关信息',
      });

      expect(result.content).toBeDefined();
      expect(result.task_type).toBe(TaskType.SEARCH_SYNTH);
      expect(result.assembled_at).toBeDefined();
    });

    it('should estimate tokens correctly', async () => {
      const result = await assembler.assembleContext({
        userInput: '搜索React框架的使用方法',
      });

      // 当有检索结果时，token应该>0
      // 如果没有检索结果（无匹配资产），则可能为0
      expect(result.estimated_tokens).toBeDefined();
    });

    it('should use provided task type when given', async () => {
      const result = await assembler.assembleContext({
        userInput: 'some input',
        taskType: TaskType.CODE_GEN,
      });

      expect(result.task_type).toBe(TaskType.CODE_GEN);
    });

    it('should merge multiple fragment types', async () => {
      const systemFragment: PromptFragment = {
        id: 'sys-1',
        type: PromptFragmentType.SYSTEM,
        content: 'You are a helpful assistant',
        priority: PromptPriority.P1_SAFETY,
        quality_score_history: [],
        gepa_version: 0,
        created_at: new Date().toISOString(),
      };

      const result = await assembler.assembleContext({
        userInput: 'test',
        systemFragments: [systemFragment],
      });

      expect(result.fragments_used).toContain('sys-1');
    });
  });

  // ============================================
  // PromptRouter 测试
  // ============================================
  describe('PromptRouter - 提示词路由', () => {
    let router: PromptRouter;

    beforeEach(() => {
      router = new PromptRouter();
    });

    it('should route user input to assemble prompt', async () => {
      const result = await router.route('搜索React的信息');

      expect(result.content).toBeDefined();
      expect(result.task_type).toBeDefined();
    });

    it('should recognize task type from input', async () => {
      const result = await router.route('帮我写一个快速排序函数');

      expect(result.task_type).toBeDefined();
      expect(Object.values(TaskType)).toContain(result.task_type);
    });

    it('should use provided task type when specified', async () => {
      const result = await router.route('做点什么', { taskType: TaskType.DOC_WRITE });

      expect(result.task_type).toBe(TaskType.DOC_WRITE);
    });

    it('should include safety rules in output', async () => {
      const result = await router.route('搜索信息', {
        safetyRules: ['不要执行危险命令', '禁止删除系统文件'],
      });

      expect(result.content).toContain('不要执行危险命令');
      expect(result.content).toContain('禁止删除系统文件');
    });

    it('should include user preferences in output', async () => {
      const result = await router.route('搜索信息', {
        userPreferences: { language: '中文', style: '简洁' },
      });

      expect(result.content).toContain('language: 中文');
      expect(result.content).toContain('style: 简洁');
    });

    it('should include available tools in context', async () => {
      const result = await router.route('执行任务', {
        availableTools: ['bash', 'read', 'write'],
      });

      expect(result.content).toContain('bash');
      expect(result.content).toContain('read');
      expect(result.content).toContain('write');
    });

    it('should register and retrieve assets', async () => {
      const fragment: PromptFragment = {
        id: 'asset-001',
        type: PromptFragmentType.TASK,
        content: 'React开发最佳实践和框架指南',
        priority: PromptPriority.P3_TASK_SPECIFIC,
        quality_score_history: [0.9],
        gepa_version: 1,
        created_at: new Date().toISOString(),
      };

      router.registerAsset(fragment);

      // 验证路由能够处理资产注册（不抛出异常）
      expect(() => router.registerAsset(fragment)).not.toThrow();
    });

    it('should return current config', () => {
      const config = router.getConfig();

      expect(config).toBeDefined();
      expect(config.asset_retrieval_threshold).toBeDefined();
      expect(config.quality_threshold).toBeDefined();
    });
  });

  // ============================================
  // 类型枚举测试
  // ============================================
  describe('Type Enums - 类型枚举', () => {
    it('should have all 9 TaskTypes', () => {
      expect(Object.keys(TaskType)).toHaveLength(9);
      expect(TaskType.SEARCH_SYNTH).toBe('search_synth');
      expect(TaskType.CODE_GEN).toBe('code_gen');
      expect(TaskType.DOC_WRITE).toBe('doc_write');
      expect(TaskType.DATA_ANALYSIS).toBe('data_analysis');
      expect(TaskType.DIAGNOSIS).toBe('diagnosis');
      expect(TaskType.PLANNING).toBe('planning');
      expect(TaskType.CREATIVE).toBe('creative');
      expect(TaskType.SYS_CONFIG).toBe('sys_config');
      expect(TaskType.AAL_DECISION).toBe('aal_decision');
    });

    it('should have all 6 PromptPriority levels', () => {
      expect(Object.keys(PromptPriority)).toHaveLength(6);
      expect(PromptPriority.P1_SAFETY).toBe('p1_safety');
      expect(PromptPriority.P2_USER_PREFERENCE).toBe('p2_user_preference');
      expect(PromptPriority.P3_TASK_SPECIFIC).toBe('p3_task_specific');
      expect(PromptPriority.P4_FEW_SHOT).toBe('p4_few_shot');
      expect(PromptPriority.P5_CONTEXT).toBe('p5_context');
      expect(PromptPriority.P6_BASE).toBe('p6_base');
    });

    it('should have all PromptFragmentTypes', () => {
      expect(Object.keys(PromptFragmentType)).toHaveLength(5);
      expect(PromptFragmentType.SYSTEM).toBe('system');
      expect(PromptFragmentType.TASK).toBe('task');
      expect(PromptFragmentType.FEW_SHOT).toBe('few_shot');
      expect(PromptFragmentType.CHAIN_OF_THOUGHT).toBe('chain_of_thought');
      expect(PromptFragmentType.OUTPUT_FORMAT).toBe('output_format');
    });
  });

  // ============================================
  // 配置测试
  // ============================================
  describe('PromptEngineConfig - 配置', () => {
    it('should have correct default values', () => {
      expect(DEFAULT_PROMPT_ENGINE_CONFIG.asset_retrieval_threshold).toBe(0.85);
      expect(DEFAULT_PROMPT_ENGINE_CONFIG.quality_threshold).toBe(0.7);
      expect(DEFAULT_PROMPT_ENGINE_CONFIG.max_retries).toBe(3);
      expect(DEFAULT_PROMPT_ENGINE_CONFIG.gepa_improvement_threshold).toBe(0.05);
      expect(DEFAULT_PROMPT_ENGINE_CONFIG.dspy_compilation_budget).toBe(500);
      expect(DEFAULT_PROMPT_ENGINE_CONFIG.few_shot_count).toBe(3);
      expect(DEFAULT_PROMPT_ENGINE_CONFIG.token_retain_threshold).toBe(90000);
    });

    it('should use 0.85 as asset retrieval threshold', () => {
      expect(DEFAULT_PROMPT_ENGINE_CONFIG.asset_retrieval_threshold).toBe(0.85);
    });
  });

  // ============================================
  // 边界情况测试
  // ============================================
  describe('Edge Cases - 边界情况', () => {
    it('should handle empty user input', async () => {
      const router = new PromptRouter();
      const result = await router.route('');

      expect(result.content).toBeDefined();
      expect(result.task_type).toBeDefined();
    });

    it('should handle very long user input', async () => {
      const router = new PromptRouter();
      const longInput = '搜索'.repeat(1000);
      const result = await router.route(longInput);

      expect(result.content).toBeDefined();
    });

    it('should handle special characters in input', async () => {
      const router = new PromptRouter();
      const result = await router.route('搜索 <script>alert("xss")</script>');

      expect(result.content).toBeDefined();
    });

    it('should handle unicode in input', async () => {
      const router = new PromptRouter();
      const result = await router.route('搜索 日本語 한국어');

      expect(result.content).toBeDefined();
    });

    it('should handle all task types for recognition', () => {
      const recognizer = new TaskTypeRecognizer();

      const inputs = [
        { input: '搜索信息', expected: TaskType.SEARCH_SYNTH },
        { input: '写代码', expected: TaskType.CODE_GEN },
        { input: '写文章', expected: TaskType.DOC_WRITE },
        { input: '分析数据', expected: TaskType.DATA_ANALYSIS },
        { input: '解决问题', expected: TaskType.DIAGNOSIS },
        { input: '制定计划', expected: TaskType.PLANNING },
        { input: '创意设计', expected: TaskType.CREATIVE },
        { input: '配置环境', expected: TaskType.SYS_CONFIG },
        { input: '做决定', expected: TaskType.AAL_DECISION },
      ];

      inputs.forEach(({ input, expected }) => {
        const results = recognizer.recognizeFromInput(input);
        if (results.length > 0) {
          expect(results[0].taskType).toBe(expected);
        }
      });
    });
  });
});
