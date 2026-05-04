/**
 * M10 Intent Clarification Engine 单元测试
 * ================================================
 * 测试ICEEngine的clarity评估、3+1问题生成
 * 五维评分算法 (§5) 和四模式差异化策略 (§8)
 * ================================================
 */

import { jest } from '@jest/globals';
import {
  ICEEngine,
  IntentClarity,
  IntentProfile,
  FiveDimensionalInput,
  FiveDimensionalScore,
} from './ice_engine';

describe('ICEEngine 单元测试', () => {
  let engine: ICEEngine;

  beforeEach(() => {
    engine = new ICEEngine();
  });

  // 创建测试用的 IntentClarity
  const createIntentClarity = (overrides: Partial<IntentClarity> = {}): IntentClarity => ({
    score: 0.5,
    missingParams: ['goal', 'deliverable'],
    ambiguities: ['audience'],
    ...overrides,
  });

  // ============================================
  // 清晰度阈值测试
  // ============================================
  describe('Clarity Threshold', () => {
    it('should use 0.85 as clarity threshold', () => {
      expect((engine as any).CLARITY_THRESHOLD).toBe(0.85);
    });
  });

  // ============================================
  // evaluate - 快速清晰度评估
  // ============================================
  describe('evaluate - 快速清晰度评估', () => {
    it('should return shouldClarify=false when score >= 0.85', () => {
      const clarity = createIntentClarity({ score: 0.9, missingParams: [], ambiguities: [] });

      const result = engine.evaluate('test query', clarity);

      expect(result.shouldClarify).toBe(false);
      expect(result.questions).toHaveLength(0);
    });

    it('should return shouldClarify=true when score < 0.85', () => {
      const clarity = createIntentClarity({ score: 0.5 });

      const result = engine.evaluate('test query', clarity);

      expect(result.shouldClarify).toBe(true);
    });

    it('should generate questions in 3+1 pattern', () => {
      const clarity = createIntentClarity({
        score: 0.5,
        missingParams: ['goal', 'deliverable'],
        ambiguities: ['audience'],
      });

      const result = engine.evaluate('test query', clarity);

      // 3 specific + 1 divergent = 4 questions
      expect(result.questions.length).toBeGreaterThanOrEqual(3);
    });

    it('should generate 4 questions when all gaps are filled', () => {
      const clarity = createIntentClarity({
        score: 0.6,
        missingParams: ['goal', 'deliverable', 'audience'],
        ambiguities: [],
      });

      const result = engine.evaluate('test query', clarity);

      // 3 from gaps + 1 divergent = 4
      expect(result.questions.length).toBe(4);
    });

    it('should limit questions to 3 specific + 1 divergent', () => {
      const clarity = createIntentClarity({
        score: 0.5,
        missingParams: ['p1', 'p2', 'p3', 'p4', 'p5'],
        ambiguities: ['a1', 'a2'],
      });

      const result = engine.evaluate('test query', clarity);

      // Only top 3 from gaps + 1 divergent = 4
      expect(result.questions.length).toBe(4);
    });

    it('should handle empty missingParams and ambiguities', () => {
      const clarity = createIntentClarity({
        score: 0.6,
        missingParams: [],
        ambiguities: [],
      });

      const result = engine.evaluate('test query', clarity);

      // Only the divergent question
      expect(result.questions.length).toBe(1);
    });

    it('should include divergent question as last question', () => {
      const clarity = createIntentClarity({
        score: 0.5,
        missingParams: ['goal'],
        ambiguities: [],
      });

      const result = engine.evaluate('test query', clarity);

      const lastQuestion = result.questions[result.questions.length - 1];
      expect(lastQuestion).toContain('老板');
    });
  });

  // ============================================
  // 问题格式测试
  // ============================================
  describe('Question Format - 问题格式', () => {
    it('should ask about specific gaps with details request', () => {
      const clarity = createIntentClarity({
        score: 0.5,
        missingParams: ['goal'],
        ambiguities: [],
      });

      const result = engine.evaluate('test query', clarity);

      // First question should be about the gap
      expect(result.questions[0]).toContain('goal');
      expect(result.questions[0]).toContain('细节');
    });

    it('should have divergent fallback question in Chinese', () => {
      const clarity = createIntentClarity({
        score: 0.5,
        missingParams: [],
        ambiguities: [],
      });

      const result = engine.evaluate('test query', clarity);

      const lastQuestion = result.questions[result.questions.length - 1];
      expect(lastQuestion).toContain('老板');
      expect(lastQuestion).toContain('本地环境');
    });
  });

  // ============================================
  // 边界情况测试
  // ============================================
  describe('Edge Cases - 边界情况', () => {
    it('should handle score exactly at threshold (0.85)', () => {
      const clarity = createIntentClarity({ score: 0.85 });

      const result = engine.evaluate('test query', clarity);

      expect(result.shouldClarify).toBe(false);
    });

    it('should handle score slightly below threshold (0.84)', () => {
      const clarity = createIntentClarity({ score: 0.84 });

      const result = engine.evaluate('test query', clarity);

      expect(result.shouldClarify).toBe(true);
    });

    it('should handle zero score', () => {
      const clarity = createIntentClarity({ score: 0 });

      const result = engine.evaluate('test query', clarity);

      expect(result.shouldClarify).toBe(true);
      expect(result.questions.length).toBeGreaterThan(0);
    });

    it('should handle max score (1.0)', () => {
      const clarity = createIntentClarity({ score: 1.0, missingParams: [], ambiguities: [] });

      const result = engine.evaluate('test query', clarity);

      expect(result.shouldClarify).toBe(false);
      expect(result.questions).toHaveLength(0);
    });

    it('should handle very long gap descriptions', () => {
      const longGap = 'a'.repeat(100);
      const clarity = createIntentClarity({
        score: 0.5,
        missingParams: [longGap],
        ambiguities: [],
      });

      const result = engine.evaluate('test query', clarity);

      expect(result.questions.length).toBeGreaterThan(0);
    });

    it('should handle unicode in query', () => {
      const clarity = createIntentClarity({ score: 0.5 });

      const result = engine.evaluate('搜索 日本語 한국어', clarity);

      expect(result.shouldClarify).toBe(true);
    });

    it('should handle empty query string', () => {
      const clarity = createIntentClarity({ score: 0.5 });

      const result = engine.evaluate('', clarity);

      expect(result.shouldClarify).toBe(true);
    });
  });

  // ============================================
  // 日志输出测试
  // ============================================
  describe('Logging - 日志输出', () => {
    it('should log clarity evaluation', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
      const clarity = createIntentClarity({ score: 0.5 });

      engine.evaluate('test query', clarity);

      expect(consoleSpy).toHaveBeenCalled();
      const logCall = consoleSpy.mock.calls[0][0] as string;
      expect(logCall).toContain('[ICE]');
      expect(logCall).toContain('0.5');
      expect(logCall).toContain('0.85');

      consoleSpy.mockRestore();
    });
  });

  // ============================================
  // 五维评分算法测试 (§5)
  // ============================================
  describe('Five-Dimensional Scoring - 五维评分算法 §5', () => {
    // 权重验证
    describe('Weights - 权重验证', () => {
      it('should have correct weights: goal=0.30', () => {
        expect((engine as any).WEIGHTS.goal).toBe(0.30);
      });
      it('should have correct weights: deliverable=0.25', () => {
        expect((engine as any).WEIGHTS.deliverable).toBe(0.25);
      });
      it('should have correct weights: quality_bar=0.20', () => {
        expect((engine as any).WEIGHTS.quality_bar).toBe(0.20);
      });
      it('should have correct weights: constraints=0.15', () => {
        expect((engine as any).WEIGHTS.constraints).toBe(0.15);
      });
      it('should have correct weights: deadline=0.10', () => {
        expect((engine as any).WEIGHTS.deadline).toBe(0.10);
      });
      it('should have total weight = 1.0', () => {
        const weights = (engine as any).WEIGHTS;
        const total = weights.goal + weights.deliverable + weights.quality_bar + weights.constraints + weights.deadline;
        expect(total).toBe(1.0);
      });
    });

    // 全填充 = 1.0
    describe('Full Input - 全填充', () => {
      it('should return 1.0 when all 5 dimensions filled', () => {
        const input: FiveDimensionalInput = {
          goal: '我要学习TypeScript',
          deliverable: '一份技术文档',
          quality_bar: '详细且准确',
          constraints: ['不能太啰嗦'],
          deadline: '2026-04-30',
          budget_tokens: 10000,
        };

        const score = engine.calculateFiveDimensionalScore(input);

        expect(score.overall_score).toBe(1.0);
        expect(score.is_clear).toBe(true);
        expect(score.missing_dimensions).toHaveLength(0);
      });
    });

    // 部分填充测试
    describe('Partial Input - 部分填充', () => {
      it('should return 0.30 when only goal filled', () => {
        const input: FiveDimensionalInput = {
          goal: '我要学习TypeScript',
          deliverable: null,
          quality_bar: null,
          constraints: null,
          deadline: null,
          budget_tokens: null,
        };

        const score = engine.calculateFiveDimensionalScore(input);

        expect(score.overall_score).toBe(0.30);
        expect(score.goal_score).toBe(1);
        expect(score.deliverable_score).toBe(0);
        expect(score.missing_dimensions).toContain('deliverable');
      });

      it('should return 0.55 when goal+deliverable filled', () => {
        const input: FiveDimensionalInput = {
          goal: '我要学习TypeScript',
          deliverable: '一份技术文档',
          quality_bar: null,
          constraints: null,
          deadline: null,
          budget_tokens: null,
        };

        const score = engine.calculateFiveDimensionalScore(input);

        expect(score.overall_score).toBe(0.55); // 0.30 + 0.25
        expect(score.is_clear).toBe(false); // < 0.85
      });

      it('should return 0.75 when goal+deliverable+quality_bar filled', () => {
        const input: FiveDimensionalInput = {
          goal: '我要学习TypeScript',
          deliverable: '一份技术文档',
          quality_bar: '详细且准确',
          constraints: null,
          deadline: null,
          budget_tokens: null,
        };

        const score = engine.calculateFiveDimensionalScore(input);

        expect(score.overall_score).toBe(0.75); // 0.30 + 0.25 + 0.20
        expect(score.is_clear).toBe(false); // < 0.85
      });

      it('should return 0.90 when goal+deliverable+quality_bar+constraints filled', () => {
        const input: FiveDimensionalInput = {
          goal: '我要学习TypeScript',
          deliverable: '一份技术文档',
          quality_bar: '详细且准确',
          constraints: ['不能太啰嗦'],
          deadline: null,
          budget_tokens: null,
        };

        const score = engine.calculateFiveDimensionalScore(input);

        expect(score.overall_score).toBe(0.90); // 0.30 + 0.25 + 0.20 + 0.15
        expect(score.is_clear).toBe(true); // >= 0.85
      });

      it('should count budget_tokens as deadline dimension', () => {
        const input: FiveDimensionalInput = {
          goal: '我要学习TypeScript',
          deliverable: '一份技术文档',
          quality_bar: '详细且准确',
          constraints: ['不能太啰嗦'],
          deadline: null,
          budget_tokens: 10000,
        };

        const score = engine.calculateFiveDimensionalScore(input);

        // All 5 dimensions filled: goal(0.30) + deliverable(0.25) + quality_bar(0.20) + constraints(0.15) + deadline via budget(0.10) = 1.0
        expect(score.overall_score).toBe(1.0);
        expect(score.deadline_score).toBe(1);
      });
    });

    // 边界情况
    describe('Edge Cases - 边界情况', () => {
      it('should return 0.85 exactly when 4 dimensions filled (goal+deliverable+quality_bar+deadline)', () => {
        const input: FiveDimensionalInput = {
          goal: '我要学习TypeScript',
          deliverable: '一份技术文档',
          quality_bar: '详细且准确',
          constraints: null, // NOT filled
          deadline: '2026-04-30', // filled via deadline
          budget_tokens: null,
        };

        const score = engine.calculateFiveDimensionalScore(input);

        // 4 dimensions: goal(0.30) + deliverable(0.25) + quality_bar(0.20) + deadline(0.10) = 0.85
        expect(score.overall_score).toBe(0.85);
        expect(score.is_clear).toBe(true);
      });

      it('should handle empty string as not filled', () => {
        const input: FiveDimensionalInput = {
          goal: '  ',
          deliverable: '',
          quality_bar: null,
          constraints: null,
          deadline: null,
          budget_tokens: null,
        };

        const score = engine.calculateFiveDimensionalScore(input);

        expect(score.overall_score).toBe(0);
        expect(score.goal_score).toBe(0);
      });

      it('should handle undefined values', () => {
        const input: FiveDimensionalInput = {
          goal: null,
          deliverable: null,
          quality_bar: null,
          constraints: null,
          deadline: null,
          budget_tokens: null,
        };

        const score = engine.calculateFiveDimensionalScore(input);

        expect(score.overall_score).toBe(0);
        expect(score.missing_dimensions).toHaveLength(5);
      });
    });
  });

  // ============================================
  // IntentProfile 构建测试
  // ============================================
  describe('IntentProfile Building - IntentProfile构建', () => {
    it('should build complete IntentProfile', () => {
      const input: FiveDimensionalInput = {
        goal: '学习TypeScript',
        deliverable: '技术文档',
        quality_bar: '详细',
        constraints: ['不能太短'],
        deadline: '2026-04-30',
        budget_tokens: 5000,
      };

      const profile = engine.buildIntentProfile(input, 'doc_write', 'task');

      expect(profile.goal).toBe('学习TypeScript');
      expect(profile.deliverable).toBe('技术文档');
      expect(profile.quality_bar).toBe('详细');
      expect(profile.constraints).toEqual(['不能太短']);
      expect(profile.deadline).toBe('2026-04-30');
      expect(profile.budget_tokens).toBe(5000);
      expect(profile.task_type).toBe('doc_write');
      expect(profile.mode).toBe('task');
      expect(profile.filled_fields).toContain('goal');
      expect(profile.filled_fields).toContain('deliverable');
      expect(profile.filled_fields).toContain('quality_bar');
      expect(profile.filled_fields).toContain('constraints');
      expect(profile.filled_fields).toContain('deadline');
    });
  });

  // ============================================
  // 四模式差异化追问测试 (§8)
  // ============================================
  describe('Four-Mode Differentiated Questions - 四模式差异化追问 §8', () => {
    describe('Search Mode - 搜索模式 §8.1', () => {
      it('should generate search-specific questions', () => {
        const profile: IntentProfile = {
          goal: '',
          deliverable: '',
          audience: '',
          quality_bar: '',
          constraints: [],
          dependencies: [],
          deadline: null,
          budget_tokens: null,
          domain: '',
          task_type: 'search_synth',
          mode: 'search',
          related_assets: [],
          clarity_score: 0,
          questions_asked: 0,
          filled_fields: [],
          missing_critical: ['goal', 'deliverable'],
        };

        const result = engine.evaluateProfile(profile);

        expect(result.shouldClarify).toBe(true);
        expect(result.questions.length).toBeGreaterThan(0);
        // Search mode should ask about information scope
        const firstQuestion = result.questions[0];
        expect(firstQuestion).toMatch(/了解|最新|系统|来源|搜索结果/);
      });
    });

    describe('Task Mode - 任务模式 §8.2', () => {
      it('should generate task-specific questions', () => {
        const profile: IntentProfile = {
          goal: '',
          deliverable: '',
          audience: '',
          quality_bar: '',
          constraints: [],
          dependencies: [],
          deadline: null,
          budget_tokens: null,
          domain: '',
          task_type: 'code_gen',
          mode: 'task',
          related_assets: [],
          clarity_score: 0,
          questions_asked: 0,
          filled_fields: [],
          missing_critical: ['goal', 'deliverable'],
        };

        const result = engine.evaluateProfile(profile);

        expect(result.shouldClarify).toBe(true);
        // Task mode should ask about deliverable format
        const questionsText = result.questions.join('');
        expect(questionsText).toMatch(/做完|长什么样|产出|格式|代码|编程语言/);
      });
    });

    describe('Workflow Mode - 工作流模式 §8.3', () => {
      it('should generate workflow-specific questions', () => {
        const profile: IntentProfile = {
          goal: '',
          deliverable: '',
          audience: '',
          quality_bar: '',
          constraints: [],
          dependencies: [],
          deadline: null,
          budget_tokens: null,
          domain: '',
          task_type: 'workflow',
          mode: 'workflow',
          related_assets: [],
          clarity_score: 0,
          questions_asked: 0,
          filled_fields: [],
          missing_critical: ['goal', 'constraints'],
        };

        const result = engine.evaluateProfile(profile);

        expect(result.shouldClarify).toBe(true);
        // Workflow mode should ask about trigger conditions and failure handling
        const questionsText = result.questions.join('');
        expect(questionsText).toMatch(/触发|失败|工作流|重试|停止|退出/);
      });
    });

    describe('AAL Mode - AAL模式 §8.4', () => {
      it('should generate AAL-specific questions', () => {
        const profile: IntentProfile = {
          goal: '',
          deliverable: '',
          audience: '',
          quality_bar: '',
          constraints: [],
          dependencies: [],
          deadline: null,
          budget_tokens: null,
          domain: '',
          task_type: 'aal',
          mode: 'aal',
          related_assets: [],
          clarity_score: 0,
          questions_asked: 0,
          filled_fields: [],
          missing_critical: ['constraints', 'deadline'],
        };

        const result = engine.evaluateProfile(profile);

        expect(result.shouldClarify).toBe(true);
        // AAL mode should ask about autonomy and token budget
        const questionsText = result.questions.join('');
        expect(questionsText).toMatch(/自主|确认|token|预算|容错/);
      });
    });

    // 任务类型专项问题测试 (§7)
    describe('Type-Specific Questions - 任务类型专项问题 §7', () => {
      const typeSpecificTests: { type: string; expectedKeyword: string }[] = [
        { type: 'search_synth', expectedKeyword: '最新|历史|来源' },
        { type: 'code_gen', expectedKeyword: '编程语言|代码风格|测试用例' },
        { type: 'doc_write', expectedKeyword: '技术团队|普通用户|字数' },
        { type: 'diagnosis', expectedKeyword: '报错|解决方法|问题' },
        { type: 'sys_config', expectedKeyword: '系统版本|配置|成功标准' },
        { type: 'planning', expectedKeyword: '时间|资源约束|风险' },
        { type: 'workflow', expectedKeyword: '触发|失败|退出' },
        { type: 'creative', expectedKeyword: '风格|案例|元素' },
      ];

      typeSpecificTests.forEach(({ type, expectedKeyword }) => {
        it(`should generate correct question for ${type}`, () => {
          const profile: IntentProfile = {
            goal: 'test',
            deliverable: 'test',
            audience: '',
            quality_bar: '',
            constraints: [], // missing constraints to trigger type-specific question
            dependencies: [],
            deadline: null,
            budget_tokens: null,
            domain: '',
            task_type: type,
            mode: 'task',
            related_assets: [],
            clarity_score: 0.55, // goal+deliverable = 0.55
            questions_asked: 0,
            filled_fields: ['goal', 'deliverable'],
            missing_critical: ['constraints'],
          };

          const result = engine.evaluateProfile(profile);

          const questionsText = result.questions.join('');
          expect(questionsText).toMatch(new RegExp(expectedKeyword));
        });
      });
    });
  });

  // ============================================
  // evaluateProfile 新接口测试
  // ============================================
  describe('evaluateProfile - 基于IntentProfile的评估', () => {
    it('should return shouldClarify=false when clarity >= 0.85', () => {
      const profile: IntentProfile = {
        goal: 'test',
        deliverable: 'test',
        audience: '',
        quality_bar: 'test',
        constraints: ['test'],
        dependencies: [],
        deadline: '2026-04-30',
        budget_tokens: null,
        domain: '',
        task_type: 'test',
        mode: 'task',
        related_assets: [],
        clarity_score: 0,
        questions_asked: 0,
        filled_fields: [],
        missing_critical: [],
      };

      const result = engine.evaluateProfile(profile);

      // All 5 dimensions filled → clarity_score = 1.0, shouldClarify = false
      expect(result.shouldClarify).toBe(false);
      expect(result.questions).toHaveLength(0);
      expect(result.profile.clarity_score).toBe(1.0);
    });

    it('should return shouldClarify=true and generate questions when clarity < 0.85', () => {
      const profile: IntentProfile = {
        goal: '',
        deliverable: '',
        audience: '',
        quality_bar: '',
        constraints: [],
        dependencies: [],
        deadline: null,
        budget_tokens: null,
        domain: '',
        task_type: 'test',
        mode: 'task',
        related_assets: [],
        clarity_score: 0,
        questions_asked: 0,
        filled_fields: [],
        missing_critical: ['goal', 'deliverable', 'quality_bar'],
      };

      const result = engine.evaluateProfile(profile);

      expect(result.shouldClarify).toBe(true);
      expect(result.questions.length).toBeGreaterThan(0);
      expect(result.profile.questions_asked).toBe(1);
    });

    it('should update missing_critical in profile', () => {
      const profile: IntentProfile = {
        goal: 'test',
        deliverable: '',
        audience: '',
        quality_bar: '',
        constraints: [],
        dependencies: [],
        deadline: null,
        budget_tokens: null,
        domain: '',
        task_type: 'test',
        mode: 'task',
        related_assets: [],
        clarity_score: 0,
        questions_asked: 0,
        filled_fields: [],
        missing_critical: [],
      };

      const result = engine.evaluateProfile(profile);

      expect(result.profile.missing_critical).toContain('deliverable');
    });
  });
});
