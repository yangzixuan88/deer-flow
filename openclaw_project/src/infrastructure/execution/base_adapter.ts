/**
 * @file base_adapter.ts
 * @description Base class for execution adapters (Claude Code, Midscene, etc.)
 * Integrates with OpenHarness lifecycle hooks.
 */

import { HookContext, PreToolUseData, PostToolUseData, IPreToolUseHook, IPostToolUseHook } from '../../domain/hooks';
import { exec } from 'child_process';
import { promisify } from 'util';

const execPromise = promisify(exec);

export abstract class BaseExecutionAdapter {
  protected hooks: { pre?: IPreToolUseHook; post?: IPostToolUseHook } = {};

  public registerHooks(pre?: IPreToolUseHook, post?: IPostToolUseHook) {
    this.hooks.pre = pre;
    this.hooks.post = post;
  }

  protected async executeCLI(
    toolName: string,
    action: string,
    args: Record<string, any>,
    command: string,
    context: HookContext
  ): Promise<any> {
    const preData: PreToolUseData = {
      toolName,
      action,
      arguments: args,
      intent: context.metadata.intent || "Execution task",
      whitelistLevel: 'white', // Default to white for known tools
      confidence: 1.0,
    };

    // 1. Pre-execution hook
    if (this.hooks.pre) {
      const { proceed, modifiedData, message } = await this.hooks.pre.onPreToolUse(preData, context);
      if (!proceed) {
        throw new Error(`Execution blocked by PreToolUse hook: ${message}`);
      }
      if (modifiedData) Object.assign(preData, modifiedData);
    }

    const startTime = Date.now();
    let result: any;
    let error: string | undefined;

    // SECURITY FIX: 添加命令注入检测
    const dangerousCommandPatterns = [
      /[;&|`$(){}/\\]/,           // Shell 特殊字符
      /\brsync\b/,                // 潜在危险命令
      /\bmount\b/,
      /\bumount\b/,
      /\bchmod\b.*\b777\b/,
      /\bcurl\b.*--upload-file\b/,
      /\bwget\b.*-O\b/,
      /\bnc\b.*-e\b/,
      /\bbash\b.*-i\b/,
      /\bpython\b.*-c\b.*import\b/,
      /\bperl\b.*-e\b/,
      /\bruby\b.*-e\b/,
      /\bnpx\b.*--yes\b.*http/, // 可能的 DNS 重绑定风险
    ];

    for (const pattern of dangerousCommandPatterns) {
      if (pattern.test(command)) {
        const errMsg = `Command blocked by security policy: dangerous pattern detected`;
        console.error(`[CLI Security] ${errMsg}`);
        error = errMsg;
        // 不抛出异常，而是返回错误结果（fail-safe）
        result = undefined;
      }
    }

    // 如果检测到危险命令，跳过执行
    if (error) {
      // 执行后置钩子（记录这个安全拦截事件）
      const postData: PostToolUseData = {
        ...preData,
        success: false,
        result: undefined,
        error,
        durationMs: Date.now() - startTime,
        tokensUsed: { input: 0, output: 0, total: 0 },
        costUsd: 0,
        retryCount: 0,
      };
      if (this.hooks.post) {
        await this.hooks.post.onPostToolUse(postData, context);
      }
      throw new Error(error);
    }

    try {
      console.log(`[CLI Executing] ${command}`);
      const { stdout, stderr } = await execPromise(command);
      result = stdout || stderr;
    } catch (err: any) {
      error = err.message || "Unknown execution error";
      console.error(`[CLI Error] ${error}`);
    }

    const postData: PostToolUseData = {
      ...preData,
      success: !error,
      result,
      error,
      durationMs: Date.now() - startTime,
      tokensUsed: { input: 0, output: 0, total: 0 }, // Placeholder
      costUsd: 0,
      retryCount: 0,
    };

    // 2. Post-execution hook (Learning & Logging)
    if (this.hooks.post) {
      await this.hooks.post.onPostToolUse(postData, context);
    }

    if (error) throw new Error(error);
    return result;
  }
}
