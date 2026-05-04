/**
 * @file claude_code_adapter.ts
 * @description Adapter for Claude Code CLI v2.1.92+ (Agentic CLI Assistant).
 *
 * 适配 Claude Code v2.1.92 版本的正确 CLI 标志：
 * - v2.1.92 不支持 --task (不存在)
 * - 使用 -p/--print 进行非交互执行
 * - 使用 --agent <name> 指定代理角色
 * - 使用 --agents <json> 定义内联代理
 *
 * Reference: Super Constitution §5.1 & §13.6
 */

import { BaseExecutionAdapter } from './base_adapter';
import { HookContext } from '../../domain/hooks';

/**
 * Master Agent 配置 - 赋予 Claude Code CLI 与本 Agent 同等能力
 * 定义执行复杂任务所需的系统上下文和工具权限
 */
const MASTER_AGENT_CONFIG = {
  description: "Master Agent - 通用任务执行代理",
  prompt: `你是 OpenClaw 的核心执行代理，拥有完整的工具访问权限和高级推理能力。

核心能力：
- 系统操作：文件读写、bash命令执行、进程管理
- 代码编写：多语言代码生成、重构、调试
- 架构设计：系统设计、模式选择、最佳实践
- 安全执行：命令验证、沙箱隔离、权限检查

执行原则：
1. 理解任务意图，选择最优工具组合
2. 分步执行，每步验证结果
3. 遇到错误时主动调试而非放弃
4. 完成后提供清晰的执行报告

工具集：Bash, Read, Write, Edit, Glob, Grep, Agent, TaskOutput, TaskStop, CronCreate, CronList, LSP

当任务需要多步骤时，使用 Agent 工具创建子任务并行执行。
当任务涉及危险操作时，进行命令注入检测和路径安全校验。`
};

export class ClaudeCodeAdapter extends BaseExecutionAdapter {
  private readonly toolName = "Claude Code";
  private readonly masterAgentName = "openclaw-master";

  constructor() {
    super();
  }

  /**
   * 初始化 Master Agent 配置
   * 在首次执行前设置代理配置
   */
  public async initialize(): Promise<void> {
    // Agent 配置已内联定义，无需额外初始化
    // 如果需要持久化配置，可以使用 claude agents add 命令
    console.log(`[ClaudeCodeAdapter] Initialized with master agent: ${this.masterAgentName}`);
  }

  /**
   * Executes an automated task via Claude Code CLI.
   *
   * 使用正确的 v2.1.92 CLI 标志：
   * claude -p --agent openclaw-master -- "<task>"
   *
   * Reference: Super Constitution §5.1 & §13.6
   */
  public async executeTask(
    task: string,
    context: HookContext
  ): Promise<string> {
    // 使用 v2.1.92 支持的标志组合:
    // -p (--print): 非交互模式，输出到 stdout
    // --agent: 指定代理角色
    // --: 分隔标志和参数
    const command = `claude -p --agent ${this.masterAgentName} -- "${this.escapeTask(task)}"`;

    return this.executeCLI(
      this.toolName,
      "automated-task",
      { task, mode: "autonomous", agent: this.masterAgentName },
      command,
      context
    );
  }

  /**
   * 执行技能任务 (通过 GStack Skills)
   * 使用 /skill-name 语法调用技能
   */
  public async executeSkillTask(
    skill: string,
    task: string,
    context: HookContext
  ): Promise<string> {
    // 通过 slash command 调用技能
    // Claude Code CLI 会解析 /skill-name 并加载对应技能
    const skillCommand = `使用 ${skill} 技能完成以下任务: ${task}`;
    const command = `claude -p --agent ${this.masterAgentName} -- "${this.escapeTask(skillCommand)}"`;

    return this.executeCLI(
      this.toolName,
      "skill-task",
      { skill, task, mode: "skill-execution" },
      command,
      context
    );
  }

  /**
   * Interactive mode: Passes a single prompt.
   * 使用 --print 模式执行单次提示
   */
  public async executePrompt(
    prompt: string,
    context: HookContext
  ): Promise<string> {
    const command = `claude -p -- "${this.escapeTask(prompt)}"`;

    return this.executeCLI(
      this.toolName,
      "prompt-action",
      { prompt, mode: "interactive" },
      command,
      context
    );
  }

  /**
   * 定义自定义代理并执行任务
   * 用于需要特定角色或专业能力的任务
   */
  public async executeWithCustomAgent(
    task: string,
    agentName: string,
    agentDescription: string,
    agentPrompt: string,
    context: HookContext
  ): Promise<string> {
    // 构建内联代理配置 (JSON 格式)
    const agentsJson = JSON.stringify({
      [agentName]: {
        description: agentDescription,
        prompt: agentPrompt
      }
    }).replace(/"/g, '\\"');

    const command = `claude -p --agents "${agentsJson}" --agent ${agentName} -- "${this.escapeTask(task)}"`;

    return this.executeCLI(
      this.toolName,
      "custom-agent-task",
      { task, agentName, mode: "custom-agent" },
      command,
      context
    );
  }

  /**
   * 获取 Claude Code CLI 版本信息
   */
  public async getVersion(): Promise<string> {
    return new Promise((resolve) => {
      const { exec } = require('child_process');
      exec('claude --version', (error: Error | null, stdout: string) => {
        if (error) {
          resolve(`unknown: ${error.message}`);
        } else {
          resolve(stdout.trim());
        }
      });
    });
  }

  /**
   * 检查 Claude Code 是否可用
   */
  public async isAvailable(): Promise<boolean> {
    try {
      const version = await this.getVersion();
      return version.includes('claude');
    } catch {
      return false;
    }
  }

  /**
   * 转义任务字符串，防止命令注入
   */
  private escapeTask(task: string): string {
    // 移除潜在的命令注入字符
    return task
      .replace(/\\/g, '\\\\')
      .replace(/"/g, '\\"')
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r')
      .replace(/\t/g, '\\t');
  }
}
