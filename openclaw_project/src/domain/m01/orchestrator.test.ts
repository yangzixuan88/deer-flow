/**
 * M01 编排引擎单元测试
 * ================================================
 * 意图分类、DAG规划、编排执行测试
 * ================================================
 */

import {
  IntentClassifier,
  DAGPlanner,
  Orchestrator,
  IntentRoute,
  DAGNodeStatus,
} from './mod';

import { SystemType } from '../m04/types';

describe('M01 IntentClassifier', () => {
  let classifier: IntentClassifier;

  beforeEach(() => {
    classifier = new IntentClassifier();
  });

  describe('classify()', () => {
    it('should classify short query as direct answer', () => {
      const result = classifier.classify('今天天气怎么样');

      expect(result.route).toBe(IntentRoute.DIRECT_ANSWER);
      expect(result.confidence).toBeGreaterThan(0.8);
    });

    it('should classify complex task as orchestration', () => {
      const result = classifier.classify('帮我搜索最新的React技术文章，然后总结关键点，最后保存到笔记中');

      expect(result.route).toBe(IntentRoute.ORCHESTRATION);
      expect(result.complexity.score).toBeGreaterThanOrEqual(5);
    });

    it('should classify vague input as clarification', () => {
      const result = classifier.classify('帮我看看这个');

      expect(result.route).toBe(IntentRoute.CLARIFICATION);
      expect(result.confidence).toBeGreaterThan(0.5);
    });

    it('should detect search intent', () => {
      const result = classifier.classify('搜索关于TypeScript类型系统的文档');

      expect(result.route).toBe(IntentRoute.ORCHESTRATION);
      expect(result.suggestedSystem).toBe(SystemType.SEARCH);
    });
  });

  describe('estimateComplexity()', () => {
    it('should return low complexity for simple queries', () => {
      const result = classifier.estimateComplexity('你好');

      expect(result.score).toBeLessThan(3);
      expect(result.needsTools).toBe(false);
      expect(result.needsFileOps).toBe(false);
    });

    it('should return high complexity for multi-step tasks', () => {
      const result = classifier.estimateComplexity('首先搜索最新的AI新闻，然后分析趋势，最后生成报告');

      expect(result.score).toBeGreaterThan(5);
      expect(result.needsSearch).toBe(true);
    });

    it('should detect tool requirements', () => {
      const result = classifier.estimateComplexity('运行这个脚本并部署到服务器');

      expect(result.needsTools).toBe(true);
      expect(result.riskLevel).toBe('medium');
    });

    it('should detect file operations', () => {
      const result = classifier.estimateComplexity('创建一个新的项目文件夹并写入配置文件');

      expect(result.needsFileOps).toBe(true);
    });
  });

  describe('needsSearch()', () => {
    it('should return true for search queries', () => {
      expect(classifier.needsSearch('搜索JavaScript相关资料')).toBe(true);
    });

    it('should return false for non-search queries', () => {
      expect(classifier.needsSearch('帮我写一段代码')).toBe(false);
    });
  });

  describe('needsTools()', () => {
    it('should return true for execution tasks', () => {
      expect(classifier.needsTools('运行测试用例')).toBe(true);
    });

    it('should return false for read-only tasks', () => {
      expect(classifier.needsTools('查看日志内容')).toBe(false);
    });
  });
});

describe('M01 DAGPlanner', () => {
  let planner: DAGPlanner;

  beforeEach(() => {
    planner = new DAGPlanner();
  });

  describe('buildPlan()', () => {
    it('should create single node for simple task', () => {
      const plan = planner.buildPlan({
        requestId: 'test-001',
        sessionId: 'session-001',
        userInput: '搜索天气',
        priority: 'normal',
      });

      expect(plan.nodes.length).toBe(1);
      expect(plan.nodes[0].task).toBe('搜索天气');
    });

    it('should create multiple nodes for multi-step task', () => {
      const plan = planner.buildPlan({
        requestId: 'test-002',
        sessionId: 'session-001',
        userInput: '首先搜索，然后保存，最后通知',
        priority: 'normal',
      });

      expect(plan.nodes.length).toBeGreaterThanOrEqual(3);
    });

    it('should set correct dependencies', () => {
      const plan = planner.buildPlan({
        requestId: 'test-003',
        sessionId: 'session-001',
        userInput: '首先搜索相关内容，然后分析数据，最后生成报告',
        priority: 'normal',
      });

      // 后续节点应该依赖前置节点
      for (let i = 1; i < plan.nodes.length; i++) {
        expect(plan.nodes[i].dependencies.length).toBeGreaterThan(0);
      }
    });

    it('should generate valid topological order', () => {
      const plan = planner.buildPlan({
        requestId: 'test-004',
        sessionId: 'session-001',
        userInput: '搜索并分析数据，然后生成报告',
        priority: 'normal',
      });

      expect(plan.executionOrder.length).toBe(plan.nodes.length);
    });
  });

  describe('validateNoCycle()', () => {
    it('should return true for acyclic graph', () => {
      const nodes = [
        { id: 'a', task: 'Task A', systemType: 'task' as SystemType, dependencies: [], timeout: 1000, expectedOutput: '', priority: 'normal' as const, status: DAGNodeStatus.PENDING },
        { id: 'b', task: 'Task B', systemType: 'task' as SystemType, dependencies: ['a'], timeout: 1000, expectedOutput: '', priority: 'normal' as const, status: DAGNodeStatus.PENDING },
      ];

      expect(planner.validateNoCycle(nodes)).toBe(true);
    });

    it('should return false for cyclic graph', () => {
      const nodes = [
        { id: 'a', task: 'Task A', systemType: 'task' as SystemType, dependencies: ['b'], timeout: 1000, expectedOutput: '', priority: 'normal' as const, status: DAGNodeStatus.PENDING },
        { id: 'b', task: 'Task B', systemType: 'task' as SystemType, dependencies: ['a'], timeout: 1000, expectedOutput: '', priority: 'normal' as const, status: DAGNodeStatus.PENDING },
      ];

      expect(planner.validateNoCycle(nodes)).toBe(false);
    });
  });

  describe('topologicalSort()', () => {
    it('should return correct execution order', () => {
      const nodes = [
        { id: 'a', task: 'A', systemType: 'task' as SystemType, dependencies: [], timeout: 1000, expectedOutput: '', priority: 'normal' as const, status: DAGNodeStatus.PENDING },
        { id: 'b', task: 'B', systemType: 'task' as SystemType, dependencies: ['a'], timeout: 1000, expectedOutput: '', priority: 'normal' as const, status: DAGNodeStatus.PENDING },
        { id: 'c', task: 'C', systemType: 'task' as SystemType, dependencies: ['b'], timeout: 1000, expectedOutput: '', priority: 'normal' as const, status: DAGNodeStatus.PENDING },
      ];

      const order = planner.topologicalSort(nodes);

      expect(order[0]).toBe('a');
      expect(order.indexOf('b')).toBeGreaterThan(order.indexOf('a'));
      expect(order.indexOf('c')).toBeGreaterThan(order.indexOf('b'));
    });
  });

  describe('estimateDuration()', () => {
    it('should sum all node timeouts', () => {
      const nodes = [
        { id: 'a', task: 'A', systemType: 'task' as SystemType, dependencies: [], timeout: 10000, expectedOutput: '', priority: 'normal' as const, status: DAGNodeStatus.PENDING },
        { id: 'b', task: 'B', systemType: 'task' as SystemType, dependencies: [], timeout: 20000, expectedOutput: '', priority: 'normal' as const, status: DAGNodeStatus.PENDING },
      ];

      const duration = planner.estimateDuration(nodes);

      expect(duration).toBe(30000);
    });
  });
});

describe('M01 Orchestrator', () => {
  let orchestrator: Orchestrator;

  beforeEach(() => {
    orchestrator = new Orchestrator();
  });

  describe('execute()', () => {
    it('should route simple query to direct answer', async () => {
      const result = await orchestrator.execute({
        requestId: 'exec-001',
        sessionId: 'session-001',
        userInput: '你好',
        priority: 'normal',
      });

      expect(result.success).toBe(true);
      expect(result.route).toBe(IntentRoute.DIRECT_ANSWER);
      expect(result.directAnswer).toBeDefined();
    });

    it('should route vague query to clarification', async () => {
      const result = await orchestrator.execute({
        requestId: 'exec-002',
        sessionId: 'session-001',
        userInput: '帮我看看这个',
        priority: 'normal',
      });

      expect(result.success).toBe(true);
      expect(result.route).toBe(IntentRoute.CLARIFICATION);
      expect(result.clarification).toBeDefined();
      expect(result.clarification!.question).toBeTruthy();
    });

    it('should route complex task to orchestration', async () => {
      const result = await orchestrator.execute({
        requestId: 'exec-003',
        sessionId: 'session-001',
        userInput: '搜索最新的AI新闻并保存到文件',
        priority: 'normal',
      });

      expect(result.success).toBe(true);
      expect(result.route).toBe(IntentRoute.ORCHESTRATION);
      expect(result.execution).toBeDefined();
      expect(result.execution!.dagPlan).toBeDefined();
    });

    it('should include execution time', async () => {
      const result = await orchestrator.execute({
        requestId: 'exec-004',
        sessionId: 'session-001',
        userInput: '你好',
        priority: 'normal',
      });

      expect(result.executionTime).toBeGreaterThanOrEqual(0);
    });
  });

  describe('getConfig()', () => {
    it('should return configuration', () => {
      const config = orchestrator.getConfig();

      expect(config).toBeDefined();
      expect(config.deerflowEnabled).toBeDefined();
      expect(config.defaultTimeout).toBeDefined();
    });
  });
});
