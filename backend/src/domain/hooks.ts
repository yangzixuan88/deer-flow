/**
 * @file hooks.ts
 * @description Defines the core lifecycle hooks for OpenHarness based on the "Super Constitution" (OpenClaw超级工程项目.docx).
 * These hooks are critical for the learning system (LS) and supervision agent (Oracle) to intercept,
 * monitor, and record tool executions.
 */

/**
 * Hook context provided to every lifecycle hook.
 */
export interface HookContext {
  taskId: string;
  sessionId: string;
  agentId: string;
  timestamp: string; // ISO8601
  metadata: Record<string, any>;
}

/**
 * Data captured before a tool execution.
 * Based on the "超级宪法" §3.3 & §4.3 definitions.
 */
export interface PreToolUseData {
  toolName: string;
  action: string;
  arguments: Record<string, any>;
  intent: string; // The specific intent behind this tool call
  whitelistLevel: 'white' | 'gray' | 'black';
  confidence: number; // 0-1
}

/**
 * Data captured after a tool execution.
 * Used for the Learning System's "Experience Package" (经验包).
 */
export interface PostToolUseData extends PreToolUseData {
  success: boolean;
  result?: any;
  error?: string;
  durationMs: number;
  tokensUsed: {
    input: number;
    output: number;
    total: number;
  };
  costUsd: number;
  gitSnapshot?: string; // Git commit hash for rollback
  retryCount: number;
  supervisorEvents?: Array<{
    type: string;
    actionTaken: string;
  }>;
}

/**
 * PreToolUse Hook Interface
 * Triggered BEFORE a tool is executed.
 * Can be used for:
 * 1. Intent deep diving (意图深挖)
 * 2. Whitelist/Security check (安全审查)
 * 3. Token budget estimation (预算评估)
 */
export interface IPreToolUseHook {
  onPreToolUse(data: PreToolUseData, context: HookContext): Promise<{
    proceed: boolean;
    modifiedData?: PreToolUseData;
    message?: string; // Reason for blocking or modification
  }>;
}

/**
 * PostToolUse Hook Interface
 * Triggered AFTER a tool is executed.
 * Can be used for:
 * 1. Experience Package generation (经验包生成)
 * 2. Hallucination verification (Executor->Validator->Critic)
 * 3. Learning and evolution (自进化)
 */
export interface IPostToolUseHook {
  onPostToolUse(data: PostToolUseData, context: HookContext): Promise<void>;
}

/**
 * UserPromptSubmit Hook Interface
 * Triggered WHEN a user submits a prompt/query.
 * Can be used for:
 * 1. Intent capture and classification (意图捕获)
 * 2. Pre-processing and context injection (上下文注入)
 * 3. Clarity scoring (清晰度评分)
 * Reference: Super Constitution §3.2 & D-028
 */
export interface IUserPromptSubmitHook {
  onUserPromptSubmit(prompt: string, context: HookContext): Promise<{
    proceed: boolean;
    modifiedPrompt?: string;
    intentClassification?: string;
    clarityScore?: number;
    message?: string;
  }>;
}

/**
 * Stop Hook Interface
 * Triggered WHEN the session is being stopped (manual or automatic).
 * Can be used for:
 * 1. Graceful shutdown of resources
 * 2. Final state persistence
 * 3. Todo/LongTask continuation check (待办强制延续检查)
 * Reference: Super Constitution §3.5 & M03 Design
 */
export interface IStopHook {
  onStop(context: HookContext): Promise<{
    allowStop: boolean;
    pendingTasks?: Array<{
      taskId: string;
      description: string;
      estimatedCompletion?: string;
    }>;
    message?: string;
  }>;
}

/**
 * SessionCreate Hook Interface
 * Triggered WHEN a new session is created.
 * Can be used for:
 * 1. Session initialization and context loading
 * 2. Asset library warm-up
 * 3. User preference injection
 * Reference: Super Constitution §3.1 & D-028
 */
export interface ISessionCreateHook {
  onSessionCreate(sessionId: string, context: HookContext): Promise<{
    success: boolean;
    initializedAssets?: string[];
    userPreferences?: Record<string, any>;
    message?: string;
  }>;
}

/**
 * SessionEnd Hook Interface
 * Triggered WHEN a session ends (completed, terminated, or timed out).
 * Can be used for:
 * 1. Final experience package generation
 * 2. Session summary and metrics aggregation
 * 3. Resource cleanup and state persistence
 * Reference: Super Constitution §3.4 & D-028
 */
export interface ISessionEndHook {
  onSessionEnd(sessionId: string, context: HookContext): Promise<{
    experiencePackageId?: string;
    summaryMetrics?: {
      totalToolCalls: number;
      successRate: number;
      totalTokens: number;
      totalDurationMs: number;
    };
    cleanupCompleted: boolean;
    message?: string;
  }>;
}

/**
 * JSON Schema for Data Capture (Experience Package)
 * This schema defines the structure for persistent storage and night-time review.
 * Reference: Super Constitution §6.1
 */
export const DataCaptureSchema = {
  $schema: "http://json-schema.org/draft-07/schema#",
  title: "ExperiencePackage",
  type: "object",
  properties: {
    id: { type: "string", format: "uuid" },
    type: { type: "string", enum: ["search", "task", "tool", "combined"] },
    trigger: { type: "string" },
    intent: { type: "object" },
    outcome: { type: "string", enum: ["success", "partial", "failed"] },
    quality_score: { type: "number", minimum: 0, maximum: 1 },
    user_feedback: { type: "string" },
    duration_sec: { type: "number" },
    tokens_used: {
      type: "object",
      properties: {
        input: { type: "integer" },
        output: { type: "integer" },
        total: { type: "integer" }
      }
    },
    cost_usd: { type: "number" },
    models_used: { type: "array", items: { type: "string" } },
    created_at: { type: "string", format: "date-time" },
    reviewed: { type: "boolean", default: false },
    promoted: { type: "boolean", default: false },
    task_trace: {
      type: "object",
      properties: {
        dag_nodes: { type: "array" },
        tool_calls: {
          type: "array",
          items: {
            type: "object",
            properties: {
              tool_name: { type: "string" },
              action: { type: "string" },
              success: { type: "boolean" },
              retry_count: { type: "integer" },
              whitelist_level: { type: "string" }
            }
          }
        },
        git_snapshots: { type: "array", items: { type: "string" } }
      }
    }
  },
  required: ["id", "type", "trigger", "outcome", "created_at"]
};

// =============================================================================
// Hook Registry - 钩子注册与执行引擎
// Reference: docs/03_Harness_Hooks_System.md §2.4
// =============================================================================

export interface HookRegistration {
  name: string;
  hook: IPreToolUseHook | IPostToolUseHook | IUserPromptSubmitHook | IStopHook | ISessionCreateHook | ISessionEndHook;
  priority: number;      // 优先级，数值越小越先执行
  blocking: boolean;      // 是否阻塞执行
  enabled: boolean;       // 是否启用
}

/**
 * Hook Registry - 统一管理所有钩子的注册和分发
 * 实现钩子的优先级排序和阻塞/非阻塞分发机制
 */
export class HookRegistry {
  private preToolUseHooks: HookRegistration[] = [];
  private postToolUseHooks: HookRegistration[] = [];
  private userPromptSubmitHooks: HookRegistration[] = [];
  private stopHooks: HookRegistration[] = [];
  private sessionCreateHooks: HookRegistration[] = [];
  private sessionEndHooks: HookRegistration[] = [];

  constructor() {
    this.registerDefaultHooks();
  }

  /**
   * 注册默认钩子（优先级和blocking配置）
   * PreToolUse: priority=100, blocking=true
   * PostToolUse: priority=50, blocking=false
   */
  private registerDefaultHooks(): void {
    // 默认PreToolUse钩子配置
    this.registerPreToolUse({
      name: 'default-pre-tool',
      hook: {
        onPreToolUse: async (data, context) => ({ proceed: true, modifiedData: data })
      },
      priority: 100,
      blocking: true,
      enabled: true
    });

    // 默认PostToolUse钩子配置
    this.registerPostToolUse({
      name: 'default-post-tool',
      hook: {
        onPostToolUse: async (data, context) => {}
      },
      priority: 50,
      blocking: false,
      enabled: true
    });
  }

  /**
   * 注册PreToolUse钩子
   */
  public registerPreToolUse(registration: HookRegistration): void {
    this.preToolUseHooks.push(registration);
    this.sortByPriority(this.preToolUseHooks);
  }

  /**
   * 注册PostToolUse钩子
   */
  public registerPostToolUse(registration: HookRegistration): void {
    this.postToolUseHooks.push(registration);
    this.sortByPriority(this.postToolUseHooks);
  }

  /**
   * 注册UserPromptSubmit钩子
   */
  public registerUserPromptSubmit(registration: HookRegistration): void {
    this.userPromptSubmitHooks.push(registration);
    this.sortByPriority(this.userPromptSubmitHooks);
  }

  /**
   * 注册Stop钩子
   */
  public registerStop(registration: HookRegistration): void {
    this.stopHooks.push(registration);
    this.sortByPriority(this.stopHooks);
  }

  /**
   * 注册SessionCreate钩子
   */
  public registerSessionCreate(registration: HookRegistration): void {
    this.sessionCreateHooks.push(registration);
    this.sortByPriority(this.sessionCreateHooks);
  }

  /**
   * 注册SessionEnd钩子
   */
  public registerSessionEnd(registration: HookRegistration): void {
    this.sessionEndHooks.push(registration);
    this.sortByPriority(this.sessionEndHooks);
  }

  /**
   * 按优先级排序
   */
  private sortByPriority(hooks: HookRegistration[]): void {
    hooks.sort((a, b) => a.priority - b.priority);
  }

  /**
   * 注销钩子
   */
  public unregister(hookName: string): boolean {
    const allHooks = [
      this.preToolUseHooks,
      this.postToolUseHooks,
      this.userPromptSubmitHooks,
      this.stopHooks,
      this.sessionCreateHooks,
      this.sessionEndHooks
    ];

    for (const hooks of allHooks) {
      const index = hooks.findIndex(h => h.name === hookName);
      if (index !== -1) {
        hooks.splice(index, 1);
        return true;
      }
    }
    return false;
  }

  /**
   * 启用/禁用钩子
   */
  public setEnabled(hookName: string, enabled: boolean): boolean {
    const allHooks = [
      ...this.preToolUseHooks,
      ...this.postToolUseHooks,
      ...this.userPromptSubmitHooks,
      ...this.stopHooks,
      ...this.sessionCreateHooks,
      ...this.sessionEndHooks
    ];

    const hook = allHooks.find(h => h.name === hookName);
    if (hook) {
      hook.enabled = enabled;
      return true;
    }
    return false;
  }

  /**
   * 执行PreToolUse钩子链（阻塞模式）
   * 优先级高的钩子先执行，如果返回blocking=true则中断执行链
   */
  public async executePreToolUseChain(
    data: PreToolUseData,
    context: HookContext
  ): Promise<{ proceed: boolean; modifiedData?: PreToolUseData }> {
    let currentData = data;

    for (const registration of this.preToolUseHooks) {
      if (!registration.enabled) continue;

      const hook = registration.hook as IPreToolUseHook;
      try {
        const result = await hook.onPreToolUse(currentData, context);

        if (!result.proceed) {
          console.log(`[HookRegistry] PreToolUse "${registration.name}" blocked execution`);
          return { proceed: false, modifiedData: result.modifiedData };
        }

        if (result.modifiedData) {
          currentData = result.modifiedData;
        }

        // blocking=true时继续执行（用于强制检查链）
        if (registration.blocking) {
          continue;
        }
      } catch (error) {
        console.error(`[HookRegistry] PreToolUse "${registration.name}" error:`, error);
      }
    }

    return { proceed: true, modifiedData: currentData };
  }

  /**
   * 执行PostToolUse钩子链（非阻塞模式，异步执行）
   */
  public async executePostToolUseChain(
    data: PostToolUseData,
    context: HookContext
  ): Promise<void> {
    // 异步执行所有启用的钩子，不等待结果
    const promises = this.postToolUseHooks
      .filter(r => r.enabled)
      .map(async (registration) => {
        const hook = registration.hook as IPostToolUseHook;
        try {
          await hook.onPostToolUse(data, context);
        } catch (error) {
          console.error(`[HookRegistry] PostToolUse "${registration.name}" error:`, error);
        }
      });

    // 不阻塞主流程
    Promise.all(promises).catch(() => {});
  }

  /**
   * 执行UserPromptSubmit钩子链
   */
  public async executeUserPromptSubmitChain(
    prompt: string,
    context: HookContext
  ): Promise<{ proceed: boolean; modifiedPrompt?: string }> {
    let currentPrompt = prompt;

    for (const registration of this.userPromptSubmitHooks) {
      if (!registration.enabled) continue;

      const hook = registration.hook as IUserPromptSubmitHook;
      try {
        const result = await hook.onUserPromptSubmit(currentPrompt, context);

        if (!result.proceed) {
          console.log(`[HookRegistry] UserPromptSubmit "${registration.name}" blocked`);
          return { proceed: false, modifiedPrompt: result.modifiedPrompt };
        }

        if (result.modifiedPrompt) {
          currentPrompt = result.modifiedPrompt;
        }
      } catch (error) {
        console.error(`[HookRegistry] UserPromptSubmit "${registration.name}" error:`, error);
      }
    }

    return { proceed: true, modifiedPrompt: currentPrompt };
  }

  /**
   * 执行Stop钩子链
   */
  public async executeStopChain(context: HookContext): Promise<{
    allowStop: boolean;
    pendingTasks?: Array<{ taskId: string; description: string }>;
  }> {
    for (const registration of this.stopHooks) {
      if (!registration.enabled) continue;

      const hook = registration.hook as IStopHook;
      try {
        const result = await hook.onStop(context);
        if (!result.allowStop) {
          console.log(`[HookRegistry] Stop "${registration.name}" blocked`);
          return { allowStop: false, pendingTasks: result.pendingTasks };
        }
      } catch (error) {
        console.error(`[HookRegistry] Stop "${registration.name}" error:`, error);
      }
    }

    return { allowStop: true };
  }

  /**
   * 执行SessionCreate钩子链
   */
  public async executeSessionCreateChain(sessionId: string, context: HookContext): Promise<{
    success: boolean;
    initializedAssets?: string[];
  }> {
    for (const registration of this.sessionCreateHooks) {
      if (!registration.enabled) continue;

      const hook = registration.hook as ISessionCreateHook;
      try {
        const result = await hook.onSessionCreate(sessionId, context);
        if (!result.success) {
          console.log(`[HookRegistry] SessionCreate "${registration.name}" failed`);
          return { success: false };
        }
      } catch (error) {
        console.error(`[HookRegistry] SessionCreate "${registration.name}" error:`, error);
      }
    }

    return { success: true };
  }

  /**
   * 执行SessionEnd钩子链
   */
  public async executeSessionEndChain(sessionId: string, context: HookContext): Promise<void> {
    const promises = this.sessionEndHooks
      .filter(r => r.enabled)
      .map(async (registration) => {
        const hook = registration.hook as ISessionEndHook;
        try {
          await hook.onSessionEnd(sessionId, context);
        } catch (error) {
          console.error(`[HookRegistry] SessionEnd "${registration.name}" error:`, error);
        }
      });

    Promise.all(promises).catch(() => {});
  }

  /**
   * 获取所有已注册的钩子状态
   */
  public getHookStatus(): Record<string, HookRegistration[]> {
    return {
      preToolUse: [...this.preToolUseHooks],
      postToolUse: [...this.postToolUseHooks],
      userPromptSubmit: [...this.userPromptSubmitHooks],
      stop: [...this.stopHooks],
      sessionCreate: [...this.sessionCreateHooks],
      sessionEnd: [...this.sessionEndHooks]
    };
  }
}

// 默认导出HookRegistry实例
export const hookRegistry = new HookRegistry();
