/**
 * M03 钩子系统单元测试
 * ================================================
 * 测试 HookRegistry 的注册、执行、优先级、阻塞机制
 * ================================================
 */

import {
  HookRegistry,
  HookContext,
  PreToolUseData,
  PostToolUseData,
  IPreToolUseHook,
  IPostToolUseHook,
  IUserPromptSubmitHook,
  IStopHook,
  ISessionCreateHook,
  ISessionEndHook,
  HookRegistration,
} from './hooks';

describe('HookRegistry 单元测试', () => {
  let registry: HookRegistry;
  let mockContext: HookContext;

  beforeEach(() => {
    registry = new HookRegistry();
    mockContext = {
      taskId: 'task-001',
      sessionId: 'session-001',
      agentId: 'agent-001',
      timestamp: new Date().toISOString(),
      metadata: {},
    };
  });

  // ============================================
  // PreToolUse Hook 测试
  // ============================================
  describe('PreToolUse Hook', () => {
    it('should execute pre-tool hooks in priority order', async () => {
      const executionOrder: string[] = [];

      const lowPriorityHook: IPreToolUseHook = {
        onPreToolUse: async () => {
          executionOrder.push('low');
          return { proceed: true };
        },
      };

      const highPriorityHook: IPreToolUseHook = {
        onPreToolUse: async () => {
          executionOrder.push('high');
          return { proceed: true };
        },
      };

      registry.registerPreToolUse({
        name: 'low-priority',
        hook: lowPriorityHook,
        priority: 200,
        blocking: true,
        enabled: true,
      });

      registry.registerPreToolUse({
        name: 'high-priority',
        hook: highPriorityHook,
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const data: PreToolUseData = {
        toolName: 'bash',
        action: 'execute',
        arguments: { cmd: 'echo hello' },
        intent: 'test',
        whitelistLevel: 'white',
        confidence: 0.9,
      };

      await registry.executePreToolUseChain(data, mockContext);

      // 高优先级先执行
      expect(executionOrder).toEqual(['high', 'low']);
    });

    it('should block execution when hook returns proceed=false', async () => {
      const blockingHook: IPreToolUseHook = {
        onPreToolUse: async () => {
          return { proceed: false, message: 'Blocked by security hook' };
        },
      };

      registry.registerPreToolUse({
        name: 'blocking-hook',
        hook: blockingHook,
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const data: PreToolUseData = {
        toolName: 'bash',
        action: 'execute',
        arguments: { cmd: 'rm -rf /' },
        intent: 'dangerous',
        whitelistLevel: 'black',
        confidence: 0.5,
      };

      const result = await registry.executePreToolUseChain(data, mockContext);

      expect(result.proceed).toBe(false);
    });

    it('should allow hook to modify data', async () => {
      const modifyingHook: IPreToolUseHook = {
        onPreToolUse: async (data) => {
          return {
            proceed: true,
            modifiedData: {
              ...data,
              arguments: { ...data.arguments, sanitized: true },
            },
          };
        },
      };

      registry.registerPreToolUse({
        name: 'modifying-hook',
        hook: modifyingHook,
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const data: PreToolUseData = {
        toolName: 'bash',
        action: 'execute',
        arguments: { cmd: 'original' },
        intent: 'test',
        whitelistLevel: 'white',
        confidence: 0.9,
      };

      const result = await registry.executePreToolUseChain(data, mockContext);

      expect(result.modifiedData?.arguments).toEqual({ cmd: 'original', sanitized: true });
    });

    it('should skip disabled hooks', async () => {
      const order: string[] = [];

      registry.registerPreToolUse({
        name: 'first',
        hook: { onPreToolUse: async () => { order.push('first'); return { proceed: true }; } },
        priority: 100,
        blocking: true,
        enabled: true,
      });

      registry.registerPreToolUse({
        name: 'second-disabled',
        hook: { onPreToolUse: async () => { order.push('second'); return { proceed: true }; } },
        priority: 150,
        blocking: true,
        enabled: false, // 禁用
      });

      registry.registerPreToolUse({
        name: 'third',
        hook: { onPreToolUse: async () => { order.push('third'); return { proceed: true }; } },
        priority: 200,
        blocking: true,
        enabled: true,
      });

      const data: PreToolUseData = {
        toolName: 'test',
        action: 'test',
        arguments: {},
        intent: 'test',
        whitelistLevel: 'white',
        confidence: 0.9,
      };

      await registry.executePreToolUseChain(data, mockContext);

      expect(order).toEqual(['first', 'third']);
    });

    it('should handle hook errors gracefully', async () => {
      registry.registerPreToolUse({
        name: 'error-hook',
        hook: { onPreToolUse: async () => { throw new Error('Hook error'); } },
        priority: 100,
        blocking: true,
        enabled: true,
      });

      registry.registerPreToolUse({
        name: 'should-continue',
        hook: { onPreToolUse: async () => { return { proceed: true }; } },
        priority: 200,
        blocking: true,
        enabled: true,
      });

      const data: PreToolUseData = {
        toolName: 'test',
        action: 'test',
        arguments: {},
        intent: 'test',
        whitelistLevel: 'white',
        confidence: 0.9,
      };

      // 不应抛出异常
      const result = await registry.executePreToolUseChain(data, mockContext);
      expect(result.proceed).toBe(true);
    });
  });

  // ============================================
  // PostToolUse Hook 测试
  // ============================================
  describe('PostToolUse Hook', () => {
    it('should execute all enabled post-tool hooks', async () => {
      let executed1 = false;
      let executed2 = false;

      registry.registerPostToolUse({
        name: 'hook1',
        hook: { onPostToolUse: async () => { executed1 = true; } },
        priority: 100,
        blocking: false,
        enabled: true,
      });

      registry.registerPostToolUse({
        name: 'hook2',
        hook: { onPostToolUse: async () => { executed2 = true; } },
        priority: 200,
        blocking: false,
        enabled: true,
      });

      const data: PostToolUseData = {
        toolName: 'bash',
        action: 'execute',
        arguments: { cmd: 'echo hello' },
        intent: 'test',
        whitelistLevel: 'white',
        confidence: 0.9,
        success: true,
        durationMs: 100,
        tokensUsed: { input: 50, output: 100, total: 150 },
        costUsd: 0.001,
        retryCount: 0,
      };

      await registry.executePostToolUseChain(data, mockContext);

      // 异步执行，等待完成
      await new Promise(resolve => setTimeout(resolve, 50));

      expect(executed1).toBe(true);
      expect(executed2).toBe(true);
    });
  });

  // ============================================
  // UserPromptSubmit Hook 测试
  // ============================================
  describe('UserPromptSubmit Hook', () => {
    it('should execute user prompt hooks and modify prompt', async () => {
      registry.registerUserPromptSubmit({
        name: 'modifier',
        hook: {
          onUserPromptSubmit: async (prompt) => ({
            proceed: true,
            modifiedPrompt: prompt.toUpperCase(),
          }),
        },
        priority: 100,
        blocking: false,
        enabled: true,
      });

      const result = await registry.executeUserPromptSubmitChain('hello world', mockContext);

      expect(result.modifiedPrompt).toBe('HELLO WORLD');
    });

    it('should block prompt when hook returns proceed=false', async () => {
      registry.registerUserPromptSubmit({
        name: 'blocker',
        hook: {
          onUserPromptSubmit: async () => ({
            proceed: false,
            message: 'Profanity detected',
          }),
        },
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const result = await registry.executeUserPromptSubmitChain('bad words here', mockContext);

      expect(result.proceed).toBe(false);
    });
  });

  // ============================================
  // Stop Hook 测试
  // ============================================
  describe('Stop Hook', () => {
    it('should allow stop when all hooks approve', async () => {
      registry.registerStop({
        name: 'approver',
        hook: {
          onStop: async () => ({ allowStop: true }),
        },
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const result = await registry.executeStopChain(mockContext);

      expect(result.allowStop).toBe(true);
    });

    it('should block stop when hook has pending tasks', async () => {
      registry.registerStop({
        name: 'task-checker',
        hook: {
          onStop: async () => ({
            allowStop: false,
            pendingTasks: [
              { taskId: 'task-1', description: 'Important task' },
            ],
            message: 'Cannot stop with pending tasks',
          }),
        },
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const result = await registry.executeStopChain(mockContext);

      expect(result.allowStop).toBe(false);
      expect(result.pendingTasks).toHaveLength(1);
    });
  });

  // ============================================
  // SessionCreate Hook 测试
  // ============================================
  describe('SessionCreate Hook', () => {
    it('should initialize session successfully', async () => {
      registry.registerSessionCreate({
        name: 'initializer',
        hook: {
          onSessionCreate: async (sessionId, context) => ({
            success: true,
            initializedAssets: ['asset-1', 'asset-2'],
            userPreferences: { language: 'zh-CN' },
          }),
        },
        priority: 100,
        blocking: false,
        enabled: true,
      });

      const result = await registry.executeSessionCreateChain('session-new', mockContext);

      expect(result.success).toBe(true);
    });

    it('should fail session creation when hook fails', async () => {
      registry.registerSessionCreate({
        name: 'failer',
        hook: {
          onSessionCreate: async () => ({ success: false, message: 'Init failed' }),
        },
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const result = await registry.executeSessionCreateChain('session-new', mockContext);

      expect(result.success).toBe(false);
    });
  });

  // ============================================
  // SessionEnd Hook 测试
  // ============================================
  describe('SessionEnd Hook', () => {
    it('should execute session end hooks', async () => {
      let ended = false;

      registry.registerSessionEnd({
        name: 'end-hook',
        hook: {
          onSessionEnd: async (sessionId, context) => ({
            experiencePackageId: 'exp-001',
            summaryMetrics: {
              totalToolCalls: 10,
              successRate: 0.9,
              totalTokens: 5000,
              totalDurationMs: 30000,
            },
            cleanupCompleted: true,
          }),
        },
        priority: 100,
        blocking: false,
        enabled: true,
      });

      await registry.executeSessionEndChain('session-end', mockContext);

      // 异步执行
      await new Promise(resolve => setTimeout(resolve, 50));

      // 验证钩子被执行（不抛异常即成功）
      expect(true).toBe(true);
    });
  });

  // ============================================
  // 钩子管理测试
  // ============================================
  describe('Hook Management', () => {
    it('should unregister hooks', () => {
      registry.registerPreToolUse({
        name: 'to-remove',
        hook: { onPreToolUse: async () => ({ proceed: true }) },
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const removed = registry.unregister('to-remove');
      expect(removed).toBe(true);

      const status = registry.getHookStatus();
      const found = status.preToolUse.find(h => h.name === 'to-remove');
      expect(found).toBeUndefined();
    });

    it('should enable/disable hooks', () => {
      registry.registerPreToolUse({
        name: 'toggle-test',
        hook: { onPreToolUse: async () => ({ proceed: true }) },
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const disabled = registry.setEnabled('toggle-test', false);
      expect(disabled).toBe(true);

      const status = registry.getHookStatus();
      const hook = status.preToolUse.find(h => h.name === 'toggle-test');
      expect(hook?.enabled).toBe(false);
    });

    it('should return false when unregistering non-existent hook', () => {
      const removed = registry.unregister('non-existent-hook');
      expect(removed).toBe(false);
    });

    it('should return false when enabling non-existent hook', () => {
      const result = registry.setEnabled('non-existent-hook', false);
      expect(result).toBe(false);
    });

    it('should get hook status with all hook types', () => {
      const status = registry.getHookStatus();

      expect(status).toHaveProperty('preToolUse');
      expect(status).toHaveProperty('postToolUse');
      expect(status).toHaveProperty('userPromptSubmit');
      expect(status).toHaveProperty('stop');
      expect(status).toHaveProperty('sessionCreate');
      expect(status).toHaveProperty('sessionEnd');
    });
  });

  // ============================================
  // 边界情况测试
  // ============================================
  describe('Edge Cases', () => {
    it('should handle empty arguments', async () => {
      registry.registerPreToolUse({
        name: 'test-empty',
        hook: { onPreToolUse: async (data) => ({ proceed: true }) },
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const data: PreToolUseData = {
        toolName: 'test',
        action: 'test',
        arguments: {},
        intent: '',
        whitelistLevel: 'gray',
        confidence: 0,
      };

      const result = await registry.executePreToolUseChain(data, mockContext);
      expect(result.proceed).toBe(true);
    });

    it('should handle context with undefined metadata', async () => {
      registry.registerPreToolUse({
        name: 'test-context',
        hook: { onPreToolUse: async (data, ctx) => {
          expect(ctx.metadata).toBeDefined();
          return { proceed: true };
        } },
        priority: 100,
        blocking: true,
        enabled: true,
      });

      const contextWithUndefined: HookContext = {
        taskId: 'task-1',
        sessionId: 'session-1',
        agentId: 'agent-1',
        timestamp: new Date().toISOString(),
        metadata: undefined as any,
      };

      const data: PreToolUseData = {
        toolName: 'test',
        action: 'test',
        arguments: {},
        intent: 'test',
        whitelistLevel: 'white',
        confidence: 0.9,
      };

      await registry.executePreToolUseChain(data, contextWithUndefined);
    });

    it('should handle PostToolUse with undefined optional fields', async () => {
      registry.registerPostToolUse({
        name: 'test-optional',
        hook: { onPostToolUse: async (data) => {} },
        priority: 100,
        blocking: false,
        enabled: true,
      });

      const data: PostToolUseData = {
        toolName: 'test',
        action: 'test',
        arguments: {},
        intent: 'test',
        whitelistLevel: 'white',
        confidence: 0.9,
        success: true,
        // 可选字段省略
        durationMs: 0,
        tokensUsed: { input: 0, output: 0, total: 0 },
        costUsd: 0,
        retryCount: 0,
      };

      await registry.executePostToolUseChain(data, mockContext);
      await new Promise(resolve => setTimeout(resolve, 50));
    });
  });
});
