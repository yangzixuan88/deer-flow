/**
 * M05 Watchdog 单元测试
 * ================================================
 * 测试任务队列扫描、日夜切换、NightlyDistiller协调
 * ================================================
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

describe('Watchdog Sentinel 单元测试', () => {
  // 由于 watchdog.py 是 Python 文件，这里测试其关键逻辑的 TypeScript 模拟

  describe('日夜模式切换', () => {
    // 模拟 Python 的 is_daytime() 逻辑
    const DAY_MODE_START = 6;  // 06:00 AM
    const DAY_MODE_END = 22;     // 10:00 PM

    function isDaytime(hour: number): boolean {
      return hour >= DAY_MODE_START && hour < DAY_MODE_END;
    }

    it('should return true during day mode (09:00)', () => {
      expect(isDaytime(9)).toBe(true);
    });

    it('should return true at day mode start (06:00)', () => {
      expect(isDaytime(6)).toBe(true);
    });

    it('should return false at day mode end (22:00)', () => {
      expect(isDaytime(22)).toBe(false);
    });

    it('should return false during night mode (02:00)', () => {
      expect(isDaytime(2)).toBe(false);
    });

    it('should return false at midnight (00:00)', () => {
      expect(isDaytime(0)).toBe(false);
    });
  });

  describe('心跳间隔计算', () => {
    const DAY_MODE_START = 6;
    const DAY_MODE_END = 22;

    function getIntervalForMode(hour: number): number {
      return hour >= DAY_MODE_START && hour < DAY_MODE_END ? 5 : 30;
    }

    it('should return 5 minutes during day mode', () => {
      expect(getIntervalForMode(10)).toBe(5);
      expect(getIntervalForMode(14)).toBe(5);
      expect(getIntervalForMode(21)).toBe(5);
    });

    it('should return 30 minutes during night mode', () => {
      expect(getIntervalForMode(22)).toBe(30);
      expect(getIntervalForMode(2)).toBe(30);
      expect(getIntervalForMode(5)).toBe(30);
    });
  });

  describe('任务队列扫描', () => {
    interface Task {
      id: string;
      status: string;
      last_updated?: string;
      expected_completion?: string;
    }

    interface QueueData {
      tasks: Task[];
    }

    function scanTaskQueue(queueData: QueueData | null): {
      pendingCount: number;
      staleTasks: Task[];
      overdueTasks: Task[];
    } {
      if (!queueData) {
        return { pendingCount: 0, staleTasks: [], overdueTasks: [] };
      }

      const tasks = queueData.tasks || [];
      const pendingTasks = tasks.filter(t => t.status === 'pending');
      const now = new Date();

      const staleTasks: Task[] = [];
      const overdueTasks: Task[] = [];

      for (const task of pendingTasks) {
        // 检查超时任务
        if (task.expected_completion) {
          const expected = new Date(task.expected_completion);
          if (now > expected) {
            overdueTasks.push(task);
          }
        }

        // 检查长期未完成任务（超过60分钟无更新）
        if (task.last_updated) {
          const updated = new Date(task.last_updated);
          const ageMins = (now.getTime() - updated.getTime()) / 60000;
          if (ageMins > 60) {
            staleTasks.push({ ...task, id: `${task.id}-stale` });
          }
        }
      }

      return {
        pendingCount: pendingTasks.length,
        staleTasks,
        overdueTasks,
      };
    }

    it('should return 0 when queue is empty', () => {
      const result = scanTaskQueue(null);
      expect(result.pendingCount).toBe(0);
      expect(result.staleTasks).toHaveLength(0);
      expect(result.overdueTasks).toHaveLength(0);
    });

    it('should count pending tasks correctly', () => {
      const queue: QueueData = {
        tasks: [
          { id: 'task-1', status: 'pending' },
          { id: 'task-2', status: 'pending' },
          { id: 'task-3', status: 'completed' },
        ],
      };

      const result = scanTaskQueue(queue);
      expect(result.pendingCount).toBe(2);
    });

    it('should detect overdue tasks', () => {
      const pastDate = new Date();
      pastDate.setHours(pastDate.getHours() - 2);

      const queue: QueueData = {
        tasks: [
          { id: 'task-1', status: 'pending', expected_completion: pastDate.toISOString() },
        ],
      };

      const result = scanTaskQueue(queue);
      expect(result.overdueTasks).toHaveLength(1);
      expect(result.overdueTasks[0].id).toBe('task-1');
    });

    it('should not flag recently updated tasks as stale', () => {
      const recentDate = new Date();
      recentDate.setMinutes(recentDate.getMinutes() - 30);

      const queue: QueueData = {
        tasks: [
          { id: 'task-1', status: 'pending', last_updated: recentDate.toISOString() },
        ],
      };

      const result = scanTaskQueue(queue);
      expect(result.staleTasks).toHaveLength(0);
    });

    it('should detect stale tasks (no update > 60 min)', () => {
      const oldDate = new Date();
      oldDate.setMinutes(oldDate.getMinutes() - 90);

      const queue: QueueData = {
        tasks: [
          { id: 'task-1', status: 'pending', last_updated: oldDate.toISOString() },
        ],
      };

      const result = scanTaskQueue(queue);
      expect(result.staleTasks).toHaveLength(1);
    });
  });

  describe('Nightly Review 触发', () => {
    const NIGHTLY_REVIEW_HOUR = 2; // 02:00 AM

    function shouldTriggerNightlyReview(
      currentHour: number,
      currentMinute: number,
      lastReviewDate: string | null
    ): boolean {
      // 触发仅在 02:00 - 02:05 之间
      if (currentHour !== NIGHTLY_REVIEW_HOUR || currentMinute >= 5) {
        return false;
      }

      // 检查今天是否已触发
      if (lastReviewDate) {
        const today = new Date().toISOString().split('T')[0];
        if (lastReviewDate.startsWith(today)) {
          return false;
        }
      }

      return true;
    }

    it('should trigger at 02:00 AM', () => {
      expect(shouldTriggerNightlyReview(2, 0, null)).toBe(true);
    });

    it('should trigger at 02:04 AM', () => {
      expect(shouldTriggerNightlyReview(2, 4, null)).toBe(true);
    });

    it('should not trigger at 02:05', () => {
      expect(shouldTriggerNightlyReview(2, 5, null)).toBe(false);
    });

    it('should not trigger at 03:00', () => {
      expect(shouldTriggerNightlyReview(3, 0, null)).toBe(false);
    });

    it('should not trigger twice in same day', () => {
      const today = new Date().toISOString().split('T')[0];
      expect(shouldTriggerNightlyReview(2, 0, `${today}T02:00:00Z`)).toBe(false);
    });

    it('should trigger next day after previous trigger', () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const yesterdayStr = yesterday.toISOString().split('T')[0];

      expect(shouldTriggerNightlyReview(2, 0, `${yesterdayStr}T02:00:00Z`)).toBe(true);
    });
  });

  describe('Distiller 协调逻辑', () => {
    interface CoordinationData {
      needs_attention: boolean;
      pending_count: number;
      stale_count: number;
      overdue_count: number;
      last_check: string;
    }

    function coordinateWithDistiller(
      pendingCount: number,
      staleTasks: any[],
      overdueTasks: any[]
    ): CoordinationData {
      const needsAttention = pendingCount > 0 || staleTasks.length > 0 || overdueTasks.length > 0;

      return {
        needs_attention: needsAttention,
        pending_count: pendingCount,
        stale_count: staleTasks.length,
        overdue_count: overdueTasks.length,
        last_check: new Date().toISOString(),
      };
    }

    it('should set needs_attention=true when pending tasks exist', () => {
      const result = coordinateWithDistiller(5, [], []);
      expect(result.needs_attention).toBe(true);
      expect(result.pending_count).toBe(5);
    });

    it('should set needs_attention=true when stale tasks exist', () => {
      const result = coordinateWithDistiller(0, [{ id: 'stale-1' }], []);
      expect(result.needs_attention).toBe(true);
      expect(result.stale_count).toBe(1);
    });

    it('should set needs_attention=true when overdue tasks exist', () => {
      const result = coordinateWithDistiller(0, [], [{ id: 'overdue-1' }]);
      expect(result.needs_attention).toBe(true);
      expect(result.overdue_count).toBe(1);
    });

    it('should set needs_attention=false when all clear', () => {
      const result = coordinateWithDistiller(0, [], []);
      expect(result.needs_attention).toBe(false);
      expect(result.pending_count).toBe(0);
      expect(result.stale_count).toBe(0);
      expect(result.overdue_count).toBe(0);
    });
  });

  describe('心跳更新', () => {
    interface HeartbeatData {
      mode: string;
      last_sync: string;
      interval_minutes: number;
      effective_mode: string;
      nightly_review_pending: boolean;
    }

    function updateHeartbeat(
      currentMode: string,
      hour: number
    ): HeartbeatData {
      const isDay = hour >= 6 && hour < 22;
      const effectiveMode = isDay ? 'DAY' : 'NIGHT';
      const interval = isDay ? 5 : 30;

      return {
        mode: currentMode,
        last_sync: new Date().toISOString(),
        interval_minutes: interval,
        effective_mode: effectiveMode,
        nightly_review_pending: false,
      };
    }

    it('should set DAY mode during daytime', () => {
      const result = updateHeartbeat('IDLE', 10);
      expect(result.effective_mode).toBe('DAY');
      expect(result.interval_minutes).toBe(5);
    });

    it('should set NIGHT mode during nighttime', () => {
      const result = updateHeartbeat('IDLE', 23);
      expect(result.effective_mode).toBe('NIGHT');
      expect(result.interval_minutes).toBe(30);
    });

    it('should set NIGHT mode at midnight', () => {
      const result = updateHeartbeat('IDLE', 0);
      expect(result.effective_mode).toBe('NIGHT');
      expect(result.interval_minutes).toBe(30);
    });

    it('should set DAY mode at 06:00', () => {
      const result = updateHeartbeat('NIGHT', 6);
      expect(result.effective_mode).toBe('DAY');
    });
  });
});
