/**
 * M09 集成测试
 * ================================================
 * 测试 M09 与 M10/M08 的适配器联动
 * ================================================
 */

import { TaskType, PromptPriority, PromptFragmentType, ExecutionResult } from './types';
import {
  M10ToM09Adapter,
  M08ToM09Adapter,
  M09M10Coordinator,
  M09M08Coordinator,
  M09Integrator,
  type M10_IntentProfile,
  type M08_ExperiencePackage,
} from './integration';

describe('M09 M10ToM09Adapter', () => {
  let adapter: M10ToM09Adapter;

  beforeEach(() => {
    adapter = new M10ToM09Adapter();
  });

  describe('mapTaskType()', () => {
    it('should map code generation intent', () => {
      const profile: M10_IntentProfile = {
        goal: '帮我写一段代码',
        task_category: 'code_gen',
      };
      expect(adapter.mapTaskType(profile)).toBe(TaskType.CODE_GEN);
    });

    it('should map document writing intent', () => {
      const profile: M10_IntentProfile = {
        goal: '写一个文档',
        task_category: 'doc_write',
      };
      expect(adapter.mapTaskType(profile)).toBe(TaskType.DOC_WRITE);
    });

    it('should map search intent', () => {
      const profile: M10_IntentProfile = {
        goal: '搜索一些信息',
        task_category: 'search',
      };
      expect(adapter.mapTaskType(profile)).toBe(TaskType.SEARCH_SYNTH);
    });

    it('should map debugging intent', () => {
      const profile: M10_IntentProfile = {
        goal: '修复这个bug',
        task_category: 'diagnosis',
      };
      expect(adapter.mapTaskType(profile)).toBe(TaskType.DIAGNOSIS);
    });

    it('should default to search for unknown intent', () => {
      const profile: M10_IntentProfile = {
        goal: '随便看看',
        task_category: 'unknown',
      };
      expect(adapter.mapTaskType(profile)).toBe(TaskType.SEARCH_SYNTH);
    });
  });

  describe('mapSafetyConstraints()', () => {
    it('should map deadline constraint', () => {
      const profile: M10_IntentProfile = {
        deadline: '2026-04-20',
      };
      const fragments = adapter.mapSafetyConstraints(profile);
      expect(fragments.length).toBeGreaterThan(0);
      expect(fragments[0].content).toContain('2026-04-20');
    });

    it('should map token budget constraint', () => {
      const profile: M10_IntentProfile = {
        budget_tokens: 5000,
      };
      const fragments = adapter.mapSafetyConstraints(profile);
      expect(fragments.length).toBeGreaterThan(0);
      expect(fragments[0].content).toContain('5000');
    });

    it('should map quality bar constraint', () => {
      const profile: M10_IntentProfile = {
        quality_bar: '高质量',
      };
      const fragments = adapter.mapSafetyConstraints(profile);
      expect(fragments.some(f => f.content.includes('高质量'))).toBe(true);
    });
  });

  describe('mapConstraints()', () => {
    it('should map multiple constraints', () => {
      const profile: M10_IntentProfile = {
        constraints: ['使用 TypeScript', '遵守 ESLint 规则'],
      };
      const fragments = adapter.mapConstraints(profile);
      expect(fragments.length).toBe(2);
    });

    it('should return empty for no constraints', () => {
      const profile: M10_IntentProfile = {};
      const fragments = adapter.mapConstraints(profile);
      expect(fragments.length).toBe(0);
    });
  });

  describe('mapExecutionMode()', () => {
    it('should map search mode', () => {
      expect(adapter.mapExecutionMode('search')).toBe('SEARCH_SYNTH');
    });

    it('should map task mode', () => {
      expect(adapter.mapExecutionMode('task')).toBe('CODE_GEN');
    });

    it('should map workflow mode', () => {
      expect(adapter.mapExecutionMode('workflow')).toBe('PLANNING');
    });

    it('should map aal mode', () => {
      expect(adapter.mapExecutionMode('aal')).toBe('AAL_DECISION');
    });

    it('should default to search synth', () => {
      expect(adapter.mapExecutionMode('unknown')).toBe('SEARCH_SYNTH');
    });
  });
});

describe('M09 M08ToM09Adapter', () => {
  let adapter: M08ToM09Adapter;

  beforeEach(() => {
    adapter = new M08ToM09Adapter();
  });

  describe('convertToExecutionTrace()', () => {
    it('should convert high quality experience to success', () => {
      const exp: M08_ExperiencePackage = {
        session_id: 'test_001',
        timestamp: new Date().toISOString(),
        task_type: 'code_gen',
        intent_profile: { goal: '写代码' },
        tool_calls: [
          { tool: 'bash', input: 'echo test', output: 'test', duration_ms: 100, success: true },
        ],
        final_output: '代码输出',
        quality_score: 0.9,
        token_cost: 500,
        ge_path: 'initial',
        patterns: [],
      };

      const trace = adapter.convertToExecutionTrace(exp);
      expect(trace.result).toBe(ExecutionResult.SUCCESS);
      expect(trace.quality_score).toBe(0.9);
      expect(trace.task_type).toBe(TaskType.CODE_GEN);
    });

    it('should convert partial quality experience to partial result', () => {
      const exp: M08_ExperiencePackage = {
        session_id: 'test_002',
        timestamp: new Date().toISOString(),
        task_type: 'search',
        intent_profile: {},
        tool_calls: [],
        final_output: '输出',
        quality_score: 0.6,
        token_cost: 300,
        ge_path: 'initial',
        patterns: [],
      };

      const trace = adapter.convertToExecutionTrace(exp);
      expect(trace.result).toBe(ExecutionResult.PARTIAL);
    });

    it('should convert failed experience with failures array', () => {
      const exp: M08_ExperiencePackage = {
        session_id: 'test_003',
        timestamp: new Date().toISOString(),
        task_type: 'planning',
        intent_profile: {},
        tool_calls: [],
        final_output: '输出',
        quality_score: 0.3,
        token_cost: 100,
        ge_path: 'initial',
        patterns: [],
        failures: [
          { step: 1, error: 'timeout', recovery: 'retry' },
        ],
      };

      const trace = adapter.convertToExecutionTrace(exp);
      expect(trace.result).toBe(ExecutionResult.FAILED);
      expect(trace.retry_count).toBe(1);
    });
  });

  describe('extractLowScoreTraces()', () => {
    it('should extract experiences below threshold', () => {
      const experiences: M08_ExperiencePackage[] = [
        { session_id: '1', quality_score: 0.85 } as any,
        { session_id: '2', quality_score: 0.55 } as any,
        { session_id: '3', quality_score: 0.45 } as any,
        { session_id: '4', quality_score: 0.92 } as any,
      ];

      const lowScore = adapter.extractLowScoreTraces(experiences, 0.7);
      expect(lowScore.length).toBe(2);
    });

    it('should return empty for all high scores', () => {
      const experiences: M08_ExperiencePackage[] = [
        { session_id: '1', quality_score: 0.85 } as any,
        { session_id: '2', quality_score: 0.9 } as any,
      ];

      const lowScore = adapter.extractLowScoreTraces(experiences, 0.7);
      expect(lowScore.length).toBe(0);
    });
  });

  describe('extractHighScoreTraces()', () => {
    it('should extract experiences above threshold', () => {
      const experiences: M08_ExperiencePackage[] = [
        { session_id: '1', quality_score: 0.85 } as any,
        { session_id: '2', quality_score: 0.55 } as any,
        { session_id: '3', quality_score: 0.95 } as any,
      ];

      const highScore = adapter.extractHighScoreTraces(experiences, 0.9);
      expect(highScore.length).toBe(1);
    });
  });

  describe('extractReusablePatterns()', () => {
    it('should extract reusable patterns from experience', () => {
      const exp: M08_ExperiencePackage = {
        session_id: 'test_pattern_001',
        timestamp: new Date().toISOString(),
        task_type: 'code_gen',
        intent_profile: {},
        tool_calls: [],
        final_output: '',
        quality_score: 0.85,
        token_cost: 200,
        ge_path: 'initial',
        patterns: [
          { pattern_id: 'p1', description: '使用 TypeScript 泛型', reusable: true },
          { pattern_id: 'p2', description: '错误处理模式', reusable: false },
        ],
      };

      const patterns = adapter.extractReusablePatterns(exp);
      expect(patterns.length).toBe(1);
      expect(patterns[0].content).toContain('TypeScript');
    });
  });
});

describe('M09 M09M10Coordinator', () => {
  let coordinator: M09M10Coordinator;

  beforeEach(() => {
    coordinator = new M09M10Coordinator();
  });

  describe('requestClarification()', () => {
    it('should request goal clarification when missing', () => {
      const questions = coordinator.requestClarification('帮我看看这个错误');
      expect(questions.length).toBeGreaterThan(0);
      expect(questions.some(q => q.dimension === 'goal')).toBe(true);
    });

    it('should limit questions to 3', () => {
      const questions = coordinator.requestClarification('');
      expect(questions.length).toBeLessThanOrEqual(3);
    });
  });

  describe('integrateIntentProfile()', () => {
    it('should integrate safety constraints first', () => {
      const profile: M10_IntentProfile = {
        deadline: '2026-04-20',
        budget_tokens: 5000,
      };
      const fragments: any[] = [];

      const result = coordinator.integrateIntentProfile(profile, fragments);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].priority).toBe(PromptPriority.P1_SAFETY);
    });
  });
});

describe('M09 M09M08Coordinator', () => {
  let coordinator: M09M08Coordinator;

  beforeEach(() => {
    coordinator = new M09M08Coordinator();
  });

  describe('prepareGepaData()', () => {
    it('should prepare GEPA data from experiences', () => {
      const experiences: M08_ExperiencePackage[] = [
        {
          session_id: 'gepa_001',
          timestamp: new Date().toISOString(),
          task_type: 'search',
          intent_profile: {},
          tool_calls: [],
          final_output: '',
          quality_score: 0.95,
          token_cost: 200,
          ge_path: '',
          patterns: [{ pattern_id: 'p1', description: '测试模式', reusable: true }],
        },
      ] as any;

      const gepaData = coordinator.prepareGepaData(experiences);
      expect(gepaData.highScoreTraces.length).toBe(1);
      expect(gepaData.reusablePatterns.length).toBe(1);
    });
  });
});

describe('M09 M09Integrator', () => {
  let integrator: M09Integrator;

  beforeEach(() => {
    integrator = new M09Integrator();
  });

  describe('getM10Adapter()', () => {
    it('should return M10 adapter instance', () => {
      const adapter = integrator.getM10Adapter();
      expect(adapter).toBeInstanceOf(M10ToM09Adapter);
    });
  });

  describe('getM08Adapter()', () => {
    it('should return M08 adapter instance', () => {
      const adapter = integrator.getM08Adapter();
      expect(adapter).toBeInstanceOf(M08ToM09Adapter);
    });
  });

  describe('getM10Coordinator()', () => {
    it('should return M10 coordinator instance', () => {
      const coordinator = integrator.getM10Coordinator();
      expect(coordinator).toBeInstanceOf(M09M10Coordinator);
    });
  });

  describe('getM08Coordinator()', () => {
    it('should return M08 coordinator instance', () => {
      const coordinator = integrator.getM08Coordinator();
      expect(coordinator).toBeInstanceOf(M09M08Coordinator);
    });
  });
});
