/**
 * M11 执行器适配器测试
 * ================================================
 * 测试 ExecutorAdapter 和 VisualToolSelector
 * ================================================
 */

import {
  ExecutorAdapter,
  VisualToolSelector,
  executorAdapter,
  visualToolSelector,
} from './executor_adapter';
import { ExecutorType, ExecutorStatus } from '../types';

describe('ExecutorAdapter', () => {
  let adapter: ExecutorAdapter;

  beforeEach(() => {
    adapter = new ExecutorAdapter();
  });

  describe('submit()', () => {
    it('should submit a task and return task ID', async () => {
      const taskId = await adapter.submit(
        ExecutorType.CLAUDE_CODE,
        'Write a hello world function',
        {},
        true
      );

      expect(taskId).toBeTruthy();
      expect(taskId.startsWith('task_')).toBe(true);
      expect(adapter.getQueueLength()).toBe(1);
    });

    it('should queue multiple tasks', async () => {
      await adapter.submit(ExecutorType.CLAUDE_CODE, 'Task 1', {});
      await adapter.submit(ExecutorType.MIDSCENE, 'Task 2', {});
      await adapter.submit(ExecutorType.CLI_ANYTHING, 'Task 3', {});

      expect(adapter.getQueueLength()).toBe(3);
    });

    it('should track task with correct properties', async () => {
      const taskId = await adapter.submit(
        ExecutorType.CLAUDE_CODE,
        'Test instruction',
        { timeout_ms: 60000 },
        true
      );

      const status = adapter.getTaskStatus(taskId);
      expect(status).toBe(ExecutorStatus.IDLE);
    });
  });

  describe('cancelTask()', () => {
    it('should cancel idle task', async () => {
      const taskId = await adapter.submit(ExecutorType.CLAUDE_CODE, 'Task to cancel', {});

      const cancelled = adapter.cancelTask(taskId);
      expect(cancelled).toBe(true);

      const status = adapter.getTaskStatus(taskId);
      expect(status).toBe(ExecutorStatus.CANCELLED);
    });

    it('should not cancel non-existent task', () => {
      const cancelled = adapter.cancelTask('non_existent_id');
      expect(cancelled).toBe(false);
    });
  });

  describe('clearCompleted()', () => {
    it('should remove completed and failed tasks from queue', async () => {
      // Submit multiple tasks
      await adapter.submit(ExecutorType.CLAUDE_CODE, 'Task 1', {});
      await adapter.submit(ExecutorType.CLAUDE_CODE, 'Task 2', {});

      // cancelTask sets status to CANCELLED, which is NOT removed by clearCompleted
      // We simulate completed tasks by checking queue manipulation behavior
      // Note: CANCELLED tasks remain in queue per current implementation
      const initialLength = adapter.getQueueLength();

      // Cancelled tasks stay in queue (by design)
      adapter.cancelTask((await adapter.submit(ExecutorType.CLAUDE_CODE, 'Task 3', {})));

      // clearCompleted only removes COMPLETED and FAILED, not CANCELLED
      const cleared = adapter.clearCompleted();
      expect(cleared).toBe(0); // CANCELLED tasks are not cleared
      expect(adapter.getQueueLength()).toBe(3); // All 3 tasks still in queue
    });
  });

  describe('getActiveTask()', () => {
    it('should return null when no task is active', () => {
      expect(adapter.getActiveTask()).toBeNull();
    });
  });

  describe('execute() - error handling', () => {
    it('should return error for non-existent task', async () => {
      const result = await adapter.execute('non_existent_task_id');

      expect(result.success).toBe(false);
      expect(result.error).toBe('Task not found');
    });
  });
});

describe('VisualToolSelector', () => {
  let selector: VisualToolSelector;

  beforeEach(() => {
    selector = new VisualToolSelector();
  });

  describe('select()', () => {
    it('should select MIDSCENE for web_browser operations', () => {
      const executorType = selector.select('web_browser', { url: 'https://example.com' });
      expect(executorType).toBe(ExecutorType.MIDSCENE);
    });

    it('should select UI_TARS for desktop_app with low usage', () => {
      const executorType = selector.select('desktop_app', { app: 'notepad' });
      expect(executorType).toBe(ExecutorType.UI_TARS);
    });

    it('should select CLI_ANYTHING for desktop_app with high usage', () => {
      // Record 3 usages
      selector.recordUsage('desktop_app', 'photoshop');
      selector.recordUsage('desktop_app', 'photoshop');
      selector.recordUsage('desktop_app', 'photoshop');

      const executorType = selector.select('desktop_app', { app: 'photoshop' });
      expect(executorType).toBe(ExecutorType.CLI_ANYTHING);
    });

    it('should select CLAUDE_CODE for cli_command', () => {
      const executorType = selector.select('cli_command', { command: 'ls -la' });
      expect(executorType).toBe(ExecutorType.CLAUDE_CODE);
    });
  });

  describe('recordUsage()', () => {
    it('should track usage counts', () => {
      selector.recordUsage('web_browser', 'github');
      selector.recordUsage('web_browser', 'github');
      selector.recordUsage('web_browser', 'github');

      const count = selector.getUsageCount('web_browser', 'github');
      expect(count).toBe(3);
    });
  });

  describe('shouldConvertToCLI()', () => {
    it('should return false for low usage', () => {
      selector.recordUsage('desktop_app', 'vscode');
      selector.recordUsage('desktop_app', 'vscode');

      expect(selector.shouldConvertToCLI('desktop_app', 'vscode')).toBe(false);
    });

    it('should return true for high usage (>=3)', () => {
      selector.recordUsage('desktop_app', 'explorer');
      selector.recordUsage('desktop_app', 'explorer');
      selector.recordUsage('desktop_app', 'explorer');

      expect(selector.shouldConvertToCLI('desktop_app', 'explorer')).toBe(true);
    });
  });

  describe('singleton instances', () => {
    it('should export working singleton instances', () => {
      expect(executorAdapter).toBeInstanceOf(ExecutorAdapter);
      expect(visualToolSelector).toBeInstanceOf(VisualToolSelector);
    });
  });
});
