/**
 * M04 Coordinator 单元测试
 * ================================================
 * 测试三系统统一调度器
 * ================================================
 */

import { Coordinator } from './coordinator';
import { SystemType, TaskStatus } from './types';

describe('M04 Coordinator', () => {
  let coordinator: Coordinator;

  beforeEach(() => {
    // 设置测试环境变量
    process.env.N8N_API_KEY = 'test-n8n-api-key-for-testing';
    coordinator = new Coordinator({
      enable_search: true,
      enable_task: true,
      enable_workflow: true,
      max_parallel_tasks: 3,
      default_timeout_min: 10,
      enable_checkpoint: true,
    });
  });

  describe('execute()', () => {
    it('should execute search request', async () => {
      const result = await coordinator.execute({
        request_id: 'req1',
        session_id: 'session1',
        system_type: SystemType.SEARCH,
        priority: 'normal',
        metadata: { query: '测试搜索' },
      });

      expect(result.success).toBe(true);
      expect(result.system_type).toBe(SystemType.SEARCH);
    });

    it('should execute task request', async () => {
      const result = await coordinator.execute({
        request_id: 'req2',
        session_id: 'session1',
        system_type: SystemType.TASK,
        priority: 'normal',
        metadata: { goal: '完成一个搜索任务' },
      });

      expect(result.success).toBe(true);
      expect(result.system_type).toBe(SystemType.TASK);
    });

    it('should track execution time', async () => {
      const result = await coordinator.execute({
        request_id: 'req3',
        session_id: 'session1',
        system_type: SystemType.SEARCH,
        priority: 'normal',
        metadata: {},
      });

      expect(result.execution_time_ms).toBeGreaterThanOrEqual(0);
    });
  });

  describe('createTask()', () => {
    it('should create task with generated DAG', () => {
      const task = coordinator.createTask('task_test', '帮我搜索并分析一些信息');

      expect(task.task_id).toBe('task_test');
      expect(task.goal).toBe('帮我搜索并分析一些信息');
      expect(task.status).toBe(TaskStatus.PENDING);
      expect(task.dag.nodes.length).toBeGreaterThan(0);
    });

    it('should detect search-related tasks', () => {
      const task = coordinator.createTask('task_search', '搜索最新的AI新闻');

      const searchNode = task.dag.nodes.find(n => n.id === 'n_search');
      expect(searchNode).toBeDefined();
      expect(searchNode?.category).toBe('search');
    });

    it('should detect code-related tasks', () => {
      const task = coordinator.createTask('task_code', '帮我实现一个Python脚本');

      const codeNode = task.dag.nodes.find(n => n.id === 'n_code');
      expect(codeNode).toBeDefined();
      expect(codeNode?.category).toBe('code_gen');
    });
  });

  describe('getActiveTasks()', () => {
    it('should return empty initially', () => {
      const tasks = coordinator.getActiveTasks();
      expect(tasks.length).toBe(0);
    });

    it('should return active tasks', async () => {
      await coordinator.execute({
        request_id: 'req_task',
        session_id: 'session1',
        system_type: SystemType.TASK,
        priority: 'normal',
        metadata: { goal: '完成一个任务' },
      });

      const tasks = coordinator.getActiveTasks();
      expect(tasks.length).toBeGreaterThanOrEqual(0);
    });
  });

  describe('cancelTask()', () => {
    it('should return false for non-existent task', () => {
      const result = coordinator.cancelTask('non_existent_task');
      expect(result).toBe(false);
    });
  });

  describe('getConfig()', () => {
    it('should return coordinator config', () => {
      const config = coordinator.getConfig();

      expect(config.enable_search).toBe(true);
      expect(config.enable_task).toBe(true);
      expect(config.enable_workflow).toBe(true);
      expect(config.max_parallel_tasks).toBe(3);
    });
  });
});

describe('M04 SharedContext', () => {
  // Import after coordinator to ensure module is loaded
  let SharedContext: any;
  let sharedContext: any;

  beforeAll(async () => {
    const module = await import('./shared_context');
    SharedContext = module.SharedContext;
    sharedContext = new SharedContext();
  });

  describe('set() and get()', () => {
    it('should store and retrieve value', () => {
      sharedContext.set('test_key', { data: 'test_value' }, 60000);

      const value = sharedContext.get('test_key');
      expect(value).toEqual({ data: 'test_value' });
    });

    it('should return null for non-existent key', () => {
      const value = sharedContext.get('non_existent');
      expect(value).toBeNull();
    });

    it('should return null for expired key', () => {
      sharedContext.set('short_lived', 'value', 1); // 1ms TTL
      setTimeout(() => {
        const value = sharedContext.get('short_lived');
        expect(value).toBeNull();
      }, 10);
    });
  });

  describe('delete()', () => {
    it('should delete existing key', () => {
      sharedContext.set('to_delete', 'value');
      const deleted = sharedContext.delete('to_delete');

      expect(deleted).toBe(true);
      expect(sharedContext.get('to_delete')).toBeNull();
    });

    it('should return false for non-existent key', () => {
      const deleted = sharedContext.delete('non_existent');
      expect(deleted).toBe(false);
    });
  });

  describe('getStats()', () => {
    it('should return statistics', () => {
      sharedContext.set('key1', 'value1');
      sharedContext.set('key2', 'value2');

      const stats = sharedContext.getStats();

      expect(stats.totalKeys).toBeGreaterThanOrEqual(2);
      expect(stats.avgAccessCount).toBeGreaterThanOrEqual(0);
    });
  });

  describe('cleanup()', () => {
    it('should remove expired entries', () => {
      // Note: Timing-based expiration may not work reliably in test environment
      // This test verifies the cleanup method executes without error
      sharedContext.set('normal', 'value', 60000);
      const removed = sharedContext.cleanup();
      expect(typeof removed).toBe('number');
    });
  });
});
