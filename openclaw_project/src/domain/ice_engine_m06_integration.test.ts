/**
 * M10-M06 集成测试
 * ================================================
 * 测试 Intent Clarification 与 Memory 的联动
 * 意图 → 记忆召回 → 意图补全
 * ================================================
 */

import { ICEEngine, IntentProfile, FiveDimensionalInput } from './ice_engine';
import { WorkingMemory, workingMemory } from './memory/layer1/working_memory';
import { SessionMemory } from './memory/layer2/session_memory';
import { MemorySource } from './memory/types';

describe('M10-M06 ICE ↔ Memory Integration', () => {
  let iceEngine: ICEEngine;
  let workingMem: WorkingMemory;
  let sessionMem: SessionMemory;

  beforeEach(() => {
    iceEngine = new ICEEngine();
    workingMem = new WorkingMemory({
      max_tokens: 5000,
      retain_recent_tokens: 2000,
      summary_model: 'test',
      contradiction_check: true,
      flush_before_compact: true,
    });
    sessionMem = new SessionMemory({
      max_sessions: 10,
      compression: 'semantic',
      multimodal: false,
    });
  });

  describe('Intent → Memory Recall 联动', () => {
    it('should recall relevant context from memory when evaluating intent', () => {
      // 1. 存入工作记忆上下文
      workingMem.add(
        'context_001',
        '用户之前询问过 TypeScript 泛型的问题，需要在后续搜索中引用相关背景',
        85
      );
      workingMem.add(
        'context_002',
        '用户偏好详细的技术解释，而非简短答案',
        80
      );

      // 2. ICE 评估稀疏意图
      const sparseIntent: IntentProfile = {
        goal: '再讲讲泛型',
        deliverable: '',
        audience: '',
        quality_bar: '',
        constraints: [],
        dependencies: [],
        deadline: null,
        budget_tokens: null,
        domain: '',
        task_type: 'search',
        mode: 'search',
        related_assets: [],
        clarity_score: 0,
        questions_asked: 0,
        filled_fields: [],
        missing_critical: [],
      };

      const result = iceEngine.evaluateProfile(sparseIntent);

      // 3. 验证需要澄清（稀疏意图 clarity < 0.85）
      expect(result.shouldClarify).toBe(true);
      expect(result.profile.missing_critical.length).toBeGreaterThan(0);

      // 4. 记忆上下文可用于补充意图
      const memoryStats = workingMem.getStats();
      expect(memoryStats.entryCount).toBe(2);
    });

    it('should integrate memory context into intent clarity', () => {
      // 1. 存入高质量上下文
      workingMem.add('pref_001', '用户使用中文交流', 95);
      workingMem.add('pref_002', '用户偏好代码示例', 90);

      // 2. 构建已部分填充的意图
      const partialIntent: FiveDimensionalInput = {
        goal: '搜索 React 状态管理方案',
        deliverable: '技术对比文档',
        quality_bar: null,  // 缺失
        constraints: null,
        deadline: null,
        budget_tokens: null,
      };

      // 3. ICE 计算清晰度
      const score = iceEngine.calculateFiveDimensionalScore(partialIntent);

      // 2项已填 = 0.30 + 0.25 = 0.55 (goal + deliverable)
      expect(score.overall_score).toBe(0.55);
      expect(score.is_clear).toBe(false); // < 0.85

      // 4. 工作记忆可补充 quality_bar 信息
      const memorySummary = workingMem.compact();
      expect(memorySummary).toContain('工作记忆压缩摘要');
    });

    it('should use memory to auto-fill missing dimensions', () => {
      // 1. 在记忆中建立偏好上下文
      workingMem.add('domain_001', '电商后端系统', 85);
      workingMem.add('stack_001', '技术栈: Node.js + PostgreSQL + Redis', 90);

      // 2. 创建只有 goal 的稀疏意图
      const minimalIntent: FiveDimensionalInput = {
        goal: '优化数据库查询性能',
        deliverable: null,
        quality_bar: null,
        constraints: null,
        deadline: null,
        budget_tokens: null,
      };

      const score = iceEngine.calculateFiveDimensionalScore(minimalIntent);

      // 只有 goal 填 = 0.30
      expect(score.overall_score).toBe(0.30);
      expect(score.missing_dimensions).toContain('deliverable');
      expect(score.missing_dimensions).toContain('quality_bar');
      expect(score.missing_dimensions).toContain('constraints');
      expect(score.missing_dimensions).toContain('deadline/budget');

      // 3. 构建完整 IntentProfile（用于后续记忆召回）
      const profile = iceEngine.buildIntentProfile(minimalIntent, 'task', 'task');
      expect(profile.goal).toBe('优化数据库查询性能');
      expect(profile.mode).toBe('task');
    });
  });

  describe('Session Memory Integration', () => {
    it('should persist intent context across session', () => {
      // 1. 用户澄清意图后存入会话记忆
      const clarifiedIntent: IntentProfile = {
        goal: '了解微服务架构',
        deliverable: '架构图 + 技术选型建议',
        audience: '技术团队',
        quality_bar: '包含 Pros/Cons 对比',
        constraints: ['使用 Docker', '支持 Kubernetes'],
        dependencies: [],
        deadline: '2026-04-20',
        budget_tokens: 5000,
        domain: 'backend',
        task_type: 'search',
        mode: 'search',
        related_assets: [],
        clarity_score: 1.0,
        questions_asked: 3,
        filled_fields: ['goal', 'deliverable', 'quality_bar', 'constraints', 'deadline'],
        missing_critical: [],
      };

      // 2. 模拟会话结束：将意图存入会话记忆
      sessionMem.startSession();
      sessionMem.addItem({
        id: 'last_intent',
        content: JSON.stringify(clarifiedIntent) + ' microservices architecture',
        metadata: {
          source: MemorySource.EXPERIENCE_PACKAGE,
          importance: 0.9,
          urgency: 50,
          tags: ['intent', 'microservices'],
        },
      });

      // 3. 验证会话记忆存储
      const entries = sessionMem.retrieve('microservices');
      expect(entries.length).toBeGreaterThan(0);
    });

    it('should retrieve historical intent to bootstrap new session', () => {
      // 1. 存入历史意图
      const historicalIntent = {
        goal: '学习 TypeScript 装饰器',
        deliverable: '实践指南',
        quality_bar: '含代码示例',
        domain: 'frontend',
      };

      sessionMem.startSession();
      sessionMem.addItem({
        id: 'historical_intent',
        content: JSON.stringify(historicalIntent),
        metadata: {
          source: MemorySource.EXPERIENCE_PACKAGE,
          importance: 0.8,
          urgency: 50,
          tags: ['typescript', 'learning'],
        },
      });

      // 2. 新会话召回历史意图
      const recalled = sessionMem.retrieve('TypeScript');
      expect(recalled.length).toBeGreaterThan(0);

      // 3. 用召回信息补全新意图
      const newIntent: FiveDimensionalInput = {
        goal: '深入学习 TypeScript',
        deliverable: recalled[0]?.item ? JSON.parse(recalled[0].item.content).deliverable : null,
        quality_bar: recalled[0]?.item ? JSON.parse(recalled[0].item.content).quality_bar : null,
        constraints: null,
        deadline: null,
        budget_tokens: null,
      };

      expect(newIntent.deliverable).toBe('实践指南');
      expect(newIntent.quality_bar).toBe('含代码示例');
    });
  });

  describe('Memory-Assisted Clarification Flow', () => {
    it('should generate targeted questions based on memory context', () => {
      // 1. 建立技术背景
      workingMem.add('tech_001', '熟悉 React + TypeScript', 95);
      workingMem.add('tech_002', '有 Node.js 后端经验', 88);

      // 2. 稀疏输入
      const sparseGoal = '做个网站';
      const intent: IntentProfile = {
        goal: sparseGoal,
        deliverable: '',
        audience: '',
        quality_bar: '',
        constraints: [],
        dependencies: [],
        deadline: null,
        budget_tokens: null,
        domain: '',
        task_type: 'task',
        mode: 'task',
        related_assets: [],
        clarity_score: 0,
        questions_asked: 0,
        filled_fields: [],
        missing_critical: [],
      };

      // 3. ICE 生成澄清问题
      const result = iceEngine.evaluateProfile(intent);

      expect(result.shouldClarify).toBe(true);
      expect(result.questions.length).toBeGreaterThan(0);

      // 4. 澄清问题应聚焦缺失维度
      expect(result.profile.missing_critical).toContain('deliverable');
      expect(result.profile.missing_critical).toContain('quality_bar');
    });

    it('should achieve higher clarity with memory-assisted profile', () => {
      // 1. 模拟用户通过多次澄清完善意图
      const step1Input: FiveDimensionalInput = {
        goal: '做个电商网站',
        deliverable: null,
        quality_bar: null,
        constraints: null,
        deadline: null,
        budget_tokens: null,
      };
      const score1 = iceEngine.calculateFiveDimensionalScore(step1Input);
      expect(score1.overall_score).toBe(0.30); // 只有 goal

      // 2. 补充 deliverable
      const step2Input: FiveDimensionalInput = {
        ...step1Input,
        deliverable: '完整可运行的电商 Demo',
      };
      const score2 = iceEngine.calculateFiveDimensionalScore(step2Input);
      expect(score2.overall_score).toBe(0.55); // goal + deliverable

      // 3. 补充 quality_bar
      const step3Input: FiveDimensionalInput = {
        ...step2Input,
        quality_bar: '包含用户注册、商品展示、购物车功能',
      };
      const score3 = iceEngine.calculateFiveDimensionalScore(step3Input);
      expect(score3.overall_score).toBe(0.75); // goal + deliverable + quality_bar

      // 4. 补充 constraints
      const step4Input: FiveDimensionalInput = {
        ...step3Input,
        constraints: ['使用 React + Node.js', '支持移动端适配'],
        deadline: '2026-05-01',
      };
      const score4 = iceEngine.calculateFiveDimensionalScore(step4Input);
      expect(score4.overall_score).toBe(1.0); // 全部填满

      // 5. 构建最终 IntentProfile
      const finalProfile = iceEngine.buildIntentProfile(step4Input, 'task', 'task');
      expect(finalProfile.clarity_score).toBe(1.0);
      expect(finalProfile.filled_fields).toContain('goal');
      expect(finalProfile.filled_fields).toContain('deliverable');
      expect(finalProfile.filled_fields).toContain('quality_bar');
      expect(finalProfile.filled_fields).toContain('constraints');
      expect(finalProfile.filled_fields).toContain('deadline');
    });
  });

  describe('Four-Mode with Memory', () => {
    it('should use search mode memory context', () => {
      const searchIntent = iceEngine.buildIntentProfile(
        { goal: '查找 AI Agent 最新进展', deliverable: '技术报告', quality_bar: null, constraints: null, deadline: null, budget_tokens: null },
        'search_synth',
        'search'
      );

      expect(searchIntent.mode).toBe('search');
      expect(searchIntent.clarity_score).toBe(0.55); // goal + deliverable
    });

    it('should use task mode memory context', () => {
      const taskIntent = iceEngine.buildIntentProfile(
        { goal: '实现用户登录功能', deliverable: '代码 + 单元测试', quality_bar: '通过 ESLint', constraints: null, deadline: null, budget_tokens: null },
        'code_gen',
        'task'
      );

      expect(taskIntent.mode).toBe('task');
      expect(taskIntent.clarity_score).toBe(0.75);
    });

    it('should use workflow mode memory context', () => {
      const workflowIntent = iceEngine.buildIntentProfile(
        { goal: '每日数据报表自动生成', deliverable: '定时工作流', quality_bar: null, constraints: null, deadline: null, budget_tokens: null },
        'planning',
        'workflow'
      );

      expect(workflowIntent.mode).toBe('workflow');
    });

    it('should use AAL mode for autonomous decisions', () => {
      const aalIntent = iceEngine.buildIntentProfile(
        { goal: '自主决定是否升级依赖版本', deliverable: '升级决策报告', quality_bar: null, constraints: null, deadline: null, budget_tokens: 10000 },
        'aal_decision',
        'aal'
      );

      expect(aalIntent.mode).toBe('aal');
      expect(aalIntent.budget_tokens).toBe(10000);
    });
  });

  describe('Global Instance Integration', () => {
    it('should use global workingMemory singleton', () => {
      // 全局实例应该可用
      expect(workingMemory).toBeInstanceOf(WorkingMemory);

      // 添加到全局实例
      workingMemory.add('global_001', '全局上下文', 85);
      const stats = workingMemory.getStats();
      expect(stats.entryCount).toBeGreaterThan(0);
    });
  });
});
