/**
 * 压力测试
 * ================================================
 * 压力测试
 * - 并发任务处理 (目标 50+ concurrent)
 * - 大规模记忆检索 (目标 10k+ 记忆条目)
 * - 长时间运行稳定性测试
 * ================================================
 */

import { WorkingMemory } from '../memory/layer1/working_memory';
import { Coordinator } from '../m04/coordinator';
import { GVisorSandbox, RiskAssessor, SandboxType } from '../m11/sandbox';
import { SystemType } from '../m04/types';

describe('Stress Tests', () => {
  describe('Concurrent Task Processing', () => {
    it('should handle 50+ concurrent tasks', async () => {
      const coordinator = new Coordinator({
        enable_search: true,
        enable_task: true,
        enable_workflow: true,
        max_parallel_tasks: 50,
        default_timeout_min: 5,
        enable_checkpoint: false,
      });

      const concurrentCount = 50;
      const promises: Promise<any>[] = [];

      for (let i = 0; i < concurrentCount; i++) {
        promises.push(
          coordinator.execute({
            request_id: `stress_task_${i}`,
            session_id: 'stress_session',
            system_type: SystemType.TASK,
            priority: i % 3 === 0 ? 'high' : 'normal',
            metadata: { goal: `压力测试任务${i}` },
          })
        );
      }

      const results = await Promise.all(promises);
      const successCount = results.filter(r => r.success).length;

      console.log(`${concurrentCount} concurrent tasks: ${successCount} succeeded`);
      expect(successCount).toBeGreaterThanOrEqual(concurrentCount * 0.9); // 至少90%成功
    });

    it('should handle burst traffic', async () => {
      const coordinator = new Coordinator({
        enable_search: true,
        enable_task: true,
        enable_workflow: true,
        max_parallel_tasks: 100,
        default_timeout_min: 5,
        enable_checkpoint: false,
      });

      const burstSize = 100;
      const batchCount = 3;

      for (let batch = 0; batch < batchCount; batch++) {
        const promises: Promise<any>[] = [];

        for (let i = 0; i < burstSize; i++) {
          promises.push(
            coordinator.execute({
              request_id: `burst_${batch}_${i}`,
              session_id: `burst_session_${batch}`,
              system_type: SystemType.TASK,
              priority: 'normal',
              metadata: { goal: `批量任务${batch}-${i}` },
            })
          );
        }

        const results = await Promise.all(promises);
        const successRate = results.filter(r => r.success).length / results.length;

        console.log(`Burst ${batch + 1}: ${successRate * 100}% success rate`);
        expect(successRate).toBeGreaterThanOrEqual(0.85);
      }
    });

    it('should handle 100+ concurrent tasks', async () => {
      const coordinator = new Coordinator({
        enable_search: true,
        enable_task: true,
        enable_workflow: true,
        max_parallel_tasks: 120,
        default_timeout_min: 5,
        enable_checkpoint: false,
      });

      const concurrentCount = 100;
      const promises: Promise<any>[] = [];

      for (let i = 0; i < concurrentCount; i++) {
        promises.push(
          coordinator.execute({
            request_id: `stress_100_${i}`,
            session_id: 'stress_100_session',
            system_type: SystemType.TASK,
            priority: i % 3 === 0 ? 'high' : 'normal',
            metadata: { goal: `100并发测试任务${i}` },
          })
        );
      }

      const results = await Promise.all(promises);
      const successCount = results.filter(r => r.success).length;

      console.log(`${concurrentCount} concurrent tasks: ${successCount} succeeded`);
      expect(successCount).toBeGreaterThanOrEqual(concurrentCount * 0.9); // 至少90%成功
    });
  });

  describe('Large-Scale Memory', () => {
    it('should handle 10k+ memory entries', () => {
      const memory = new WorkingMemory({
        max_tokens: 500000,
        retain_recent_tokens: 100000,
        summary_model: 'test',
        contradiction_check: false, // 关闭矛盾检测提升性能
        flush_before_compact: false,
      });

      const entryCount = 10000;

      // 分批添加避免内存峰值
      const batchSize = 1000;
      for (let batch = 0; batch < entryCount / batchSize; batch++) {
        for (let i = 0; i < batchSize; i++) {
          const idx = batch * batchSize + i;
          memory.add(
            `stress_entry_${idx}`,
            `这是第${idx}条记忆内容，用于大规模压力测试。`.repeat(3),
            50 + (idx % 50)
          );
        }
      }

      const stats = memory.getStats();
      console.log(`Created ${entryCount} entries, stats:`, stats);
      expect(stats.entryCount).toBe(entryCount);

      // 检索性能测试
      const start = Date.now();
      const results = memory.retrieve('压力测试', 10);
      const retrievalTime = Date.now() - start;

      console.log(`Retrieval time for ${entryCount} entries: ${retrievalTime}ms`);
      expect(retrievalTime).toBeLessThan(100); // 10k数据下检索应<100ms
    });

    it('should handle 1000+ memory entries', () => {
      const memory = new WorkingMemory({
        max_tokens: 100000,
        retain_recent_tokens: 50000,
        summary_model: 'test',
        contradiction_check: true,
        flush_before_compact: true,
      });

      const entryCount = 1000;

      for (let i = 0; i < entryCount; i++) {
        memory.add(
          `stress_entry_${i}`,
          `这是第${i}条记忆内容，用于压力测试。包含一些文本以增加token数量。`.repeat(5),
          50 + (i % 50)
        );
      }

      const stats = memory.getStats();
      console.log(`Created ${entryCount} entries, stats:`, stats);
      expect(stats.entryCount).toBe(entryCount);

      // 检索性能测试
      const start = Date.now();
      const results = memory.retrieve('压力测试', 10);
      const retrievalTime = Date.now() - start;

      console.log(`Retrieval time for ${entryCount} entries: ${retrievalTime}ms`);
      expect(retrievalTime).toBeLessThan(500); // 大量数据下检索应<500ms

      // 压缩测试
      const summary = memory.compact();
      expect(summary).toContain('工作记忆压缩摘要');
    });

    it('should handle memory with frequent updates', () => {
      const memory = new WorkingMemory({
        max_tokens: 5000,
        retain_recent_tokens: 2000,
        summary_model: 'test',
        contradiction_check: true,
        flush_before_compact: true,
      });

      const updateCount = 100;

      for (let i = 0; i < updateCount; i++) {
        memory.add(`update_${i}`, `更新内容${i}`, 70 + (i % 30));
      }

      const stats = memory.getStats();
      console.log(`After ${updateCount} updates: entryCount=${stats.entryCount}`);
      expect(stats.entryCount).toBe(updateCount);
    });
  });

  describe('Long-Running Stability', () => {
    it('should remain stable over repeated operations', async () => {
      const memory = new WorkingMemory({
        max_tokens: 5000,
        retain_recent_tokens: 2000,
        summary_model: 'test',
        contradiction_check: true,
        flush_before_compact: true,
      });

      const coordinator = new Coordinator({
        enable_search: true,
        enable_task: true,
        enable_workflow: true,
        max_parallel_tasks: 5,
        default_timeout_min: 5,
        enable_checkpoint: false,
      });

      const iterations = 50;
      let memoryErrorCount = 0;
      let coordinatorErrorCount = 0;

      for (let i = 0; i < iterations; i++) {
        try {
          memory.add(`stability_${i}`, `稳定性测试${i}`, 80);
        } catch (e) {
          memoryErrorCount++;
        }

        try {
          await coordinator.execute({
            request_id: `stability_task_${i}`,
            session_id: 'stability_session',
            system_type: SystemType.TASK,
            priority: 'normal',
            metadata: { goal: `稳定性测试${i}` },
          });
        } catch (e) {
          coordinatorErrorCount++;
        }
      }

      console.log(`After ${iterations} iterations: memory errors=${memoryErrorCount}, coordinator errors=${coordinatorErrorCount}`);
      expect(memoryErrorCount).toBe(0);
      expect(coordinatorErrorCount).toBe(0);
    });

    it('should handle rapid context switches', async () => {
      // Increase timeout for this test as it involves network operations
      jest.setTimeout(60000);

      // On Windows, network operations may be slower, so use fewer iterations
      const switchCount = process.platform === 'win32' ? 10 : 30;

      const coordinator = new Coordinator({
        enable_search: true,
        enable_task: true,
        enable_workflow: true,
        max_parallel_tasks: 10,
        default_timeout_min: 5,
        enable_checkpoint: false,
      });

      const systemTypes = [SystemType.SEARCH, SystemType.TASK, SystemType.WORKFLOW];

      for (let i = 0; i < switchCount; i++) {
        const systemType = systemTypes[i % systemTypes.length];
        const result = await coordinator.execute({
          request_id: `switch_${i}`,
          session_id: 'switch_session',
          system_type: systemType,
          priority: 'normal',
          metadata: { goal: `上下文切换测试${i}` },
        });

        expect(result.success).toBe(true);
        expect(result.system_type).toBe(systemType);
      }

      console.log(`Completed ${switchCount} context switches successfully`);
    });
  });

  describe('Resource Cleanup', () => {
    it('should properly cleanup resources', async () => {
      const memory = new WorkingMemory({
        max_tokens: 5000,
        retain_recent_tokens: 2000,
        summary_model: 'test',
        contradiction_check: true,
        flush_before_compact: true,
      });

      memory.add('cleanup_1', '测试清理', 80);

      const flushed = memory.flushToSession();
      expect(flushed.length).toBe(1);

      const stats = memory.getStats();
      expect(stats.entryCount).toBe(0);

      // 验证清理后可以正常添加新数据
      memory.add('new_entry', '新条目', 90);
      const newStats = memory.getStats();
      expect(newStats.entryCount).toBe(1);
    });

    it('should handle task cancellation under load', async () => {
      const coordinator = new Coordinator({
        enable_search: true,
        enable_task: true,
        enable_workflow: true,
        max_parallel_tasks: 20,
        default_timeout_min: 5,
        enable_checkpoint: false,
      });

      const taskId = 'cancel_test_task';

      await coordinator.execute({
        request_id: taskId,
        session_id: 'cancel_session',
        system_type: SystemType.TASK,
        priority: 'normal',
        metadata: { goal: '可取消的任务' },
      });

      const cancelled = coordinator.cancelTask(taskId);
      expect(cancelled).toBe(true);

      const nonExistent = coordinator.cancelTask('non_existent_task');
      expect(nonExistent).toBe(false);
    });
  });
});
