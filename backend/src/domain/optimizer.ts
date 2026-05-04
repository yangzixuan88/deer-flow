/**
 * @file optimizer.ts
 * @description Optimizer即时优化模块 - 每次任务成功后100ms内触发
 * Reference: docs/08_Learning_System.md §5
 */

import { PostToolUseData, HookContext } from './hooks';
import { ROIEngine, AlchemyProfit } from './roi_engine';

export interface EvolutionPatch {
  originalPath: string[];
  optimizedPath: string[];
  reductionRate: number; // 0-1
  reasoning: string;
  appliedDate: string;
  task_type: string;
  confidence: number;
  // R174 FIX: target_modules enables candidate-level ROI targeting in U4 PriorScorer
  // Modules touched by this patch allow PriorScorer to match candidate.target_modules
  // against ROI history by task_type (which carries module context from the optimizer)
  targetModules?: string[];
}

export interface TaskMetrics {
  total_steps: number;
  total_tokens: number;
  total_duration_ms: number;
  parallelizable_steps: number[];
  redundant_steps: number[];
}

export interface OptimizationResult {
  patch: EvolutionPatch | null;
  metrics: TaskMetrics;
  histCompare: {
    avg_steps: number;
    avg_tokens: number;
    avg_duration: number;
    isAboveAverage: boolean;
  };
}

/**
 * Optimizer Node (GEPA Evolution)
 * 触发条件: 每次任务成功完成 + Sandbox验证通过后
 * 执行时机: 100ms内
 * Reference: docs/08_Learning_System.md §5
 */
export class OptimizerNode {
  private readonly OPTIMIZATION_THRESHOLD = 0.2; // 20% reduction required (0.8x factor from design doc)
  private readonly TRIGGER_DELAY_MS = 100; // 100ms内触发
  private roiEngine: ROIEngine;

  constructor() {
    this.roiEngine = new ROIEngine();
  }

  /**
   * 即时优化主入口
   * 读取本次完整执行轨迹 → 计算指标 → 比对历史均值 → 标记冗余/可并行 → 生成精简路径
   */
  public async optimize(
    actualTrace: PostToolUseData[],
    originalPlan: string[],
    context: HookContext,
    taskGoal?: string
  ): Promise<OptimizationResult> {
    console.log(`[Optimizer] Starting immediate optimization for Session: ${context.sessionId}`);

    // 1. 计算本次任务的指标
    const metrics = this.calculateMetrics(actualTrace);

    // 2. 比对同类任务历史均值（简化实现）
    const histCompare = this.compareToHistory(metrics, taskGoal);

    // 3. 识别冗余步骤和可并行步骤
    const redundantSteps = this.identifyRedundantSteps(actualTrace);
    const parallelizableSteps = this.identifyParallelizable(actualTrace);

    // 4. 生成精简路径
    const optimizedPath = this.generateOptimizedPath(
      actualTrace.map(t => t.toolName),
      redundantSteps,
      parallelizableSteps
    );

    const reductionRate = (actualTrace.length - optimizedPath.length) / actualTrace.length;

    // 精简后步骤数 < 原步骤数×0.8 时写入工作流资产
    if (reductionRate >= this.OPTIMIZATION_THRESHOLD) {
      const patch: EvolutionPatch = {
        originalPath: actualTrace.map(t => t.toolName),
        optimizedPath,
        reductionRate: parseFloat(reductionRate.toFixed(2)),
        reasoning: this.generateReasoning(actualTrace, redundantSteps, parallelizableSteps, reductionRate),
        appliedDate: new Date().toISOString(),
        task_type: taskGoal || 'unknown',
        confidence: histCompare.isAboveAverage ? 0.7 : 0.9,
        // R174 FIX: Extract unique target modules from the trace as patch context
        // Enables candidate-level ROI targeting in U4 PriorScorer
        targetModules: this.extractTargetModules(actualTrace),
      };

      console.log(`[Optimizer] Evolution Patch Generated! Reduction: ${patch.reductionRate * 100}%`);
      return { patch, metrics, histCompare };
    }

    console.log(`[Optimizer] Path already optimal (reduction ${(reductionRate * 100).toFixed(1)}% < 20%). No evolution required.`);
    return { patch: null, metrics, histCompare };
  }

  /**
   * 计算任务指标：总耗时·总token·步骤数
   */
  private calculateMetrics(trace: PostToolUseData[]): TaskMetrics {
    let totalTokens = 0;
    let totalDuration = 0;

    for (const t of trace) {
      // 从tokensUsed估算token
      totalTokens += t.tokensUsed?.total || 0;
      totalDuration += t.durationMs || 0;
    }

    return {
      total_steps: trace.length,
      total_tokens: totalTokens,
      total_duration_ms: totalDuration,
      parallelizable_steps: [],
      redundant_steps: []
    };
  }

  /**
   * 比对同类任务历史均值
   */
  private compareToHistory(metrics: TaskMetrics, taskGoal?: string): TaskMetrics['total_steps'] extends number ? {
    avg_steps: number;
    avg_tokens: number;
    avg_duration: number;
    isAboveAverage: boolean;
  } : never {
    // 简化的历史均值（实际应从数据库读取）
    const histAvg = {
      avg_steps: 5,
      avg_tokens: 5000,
      avg_duration: 30000,
      isAboveAverage: metrics.total_steps > 5 || metrics.total_duration_ms > 30000
    };
    return histAvg;
  }

  /**
   * 识别冗余步骤（重复搜索·无增量验证）
   */
  private identifyRedundantSteps(trace: PostToolUseData[]): number[] {
    const redundant: number[] = [];
    const seenResults = new Map<string, number>();

    for (let i = 0; i < trace.length; i++) {
      const tool = trace[i].toolName;
      const isSearchTool = tool.includes('search') || tool.includes('Search');

      // 检测重复搜索（相同关键词在短时间间隔内）
      // 使用 arguments 作为搜索关键词的标识
      if (isSearchTool) {
        const searchKey = JSON.stringify(trace[i].arguments);
        if (seenResults.has(searchKey)) {
          // 标记当前的搜索为冗余（保留第一次出现的）
          redundant.push(i);
        } else {
          seenResults.set(searchKey, i);
        }
      }

      // 检测连续重复工具调用（搜索工具除外，大小写不敏感）
      if (i > 0 && !isSearchTool &&
          trace[i].toolName.toLowerCase() === trace[i - 1].toolName.toLowerCase()) {
        redundant.push(i);
      }
    }

    return redundant;
  }

  /**
   * 识别可并行步骤（无依赖的相邻步骤）
   */
  private identifyParallelizable(trace: PostToolUseData[]): number[] {
    const parallelizable: number[] = [];

    // 简化逻辑：连续的独立工具可以并行
    const independentTools = ['read', 'Read', 'bash', 'Bash'];

    for (let i = 1; i < trace.length; i++) {
      const prev = trace[i - 1].toolName.toLowerCase();
      const curr = trace[i].toolName.toLowerCase();

      // 如果两个工具都是独立的，且没有依赖关系
      if (independentTools.some(t => prev.includes(t)) &&
          independentTools.some(t => curr.includes(t))) {
        parallelizable.push(i);
      }
    }

    return parallelizable;
  }

  /**
   * 生成精简路径（去冗余·并行化）
   */
  private generateOptimizedPath(
    originalPath: string[],
    redundantSteps: number[],
    parallelizableSteps: number[]
  ): string[] {
    const optimized: string[] = [];
    const redundantSet = new Set(redundantSteps);

    for (let i = 0; i < originalPath.length; i++) {
      if (!redundantSet.has(i)) {
        optimized.push(originalPath[i]);
      }
    }

    return optimized;
  }

  /**
   * 生成优化推理说明
   */
  private generateReasoning(
    trace: PostToolUseData[],
    redundantSteps: number[],
    parallelizableSteps: number[],
    reductionRate: number
  ): string {
    const parts: string[] = [];

    if (redundantSteps.length > 0) {
      parts.push(`发现${redundantSteps.length}个冗余步骤`);
    }
    if (parallelizableSteps.length > 0) {
      parts.push(`识别${parallelizableSteps.length}个可并行步骤`);
    }
    parts.push(`精简率${(reductionRate * 100).toFixed(0)}%`);

    return parts.join(' · ');
  }

  /**
   * R174 FIX: Extract unique target modules from trace tool arguments.
   * Maps tool calls back to their target modules based on path patterns in arguments.
   * Enables candidate-level ROI targeting in U4 PriorScorer.
   */
  private extractTargetModules(trace: PostToolUseData[]): string[] {
    const modules = new Set<string>();
    const modulePattern = /M\d+_\w+/g;

    for (const step of trace) {
      const argStr = JSON.stringify(step.arguments || {});
      const matches = argStr.match(modulePattern);
      if (matches) {
        matches.forEach(m => modules.add(m));
      }
      // Also check intent for module references
      if (step.intent) {
        const intentMatches = step.intent.match(modulePattern);
        if (intentMatches) {
          intentMatches.forEach(m => modules.add(m));
        }
      }
    }

    return Array.from(modules);
  }

  /**
   * 执行即时优化（供PostToolUse钩子回调）
   */
  public async executeImmediateOptimization(
    trace: PostToolUseData[],
    context: HookContext
  ): Promise<EvolutionPatch | null> {
    // 在100ms内触发
    const startTime = Date.now();

    const result = await this.optimize(trace, [], context);

    const elapsed = Date.now() - startTime;
    console.log(`[Optimizer] Optimization completed in ${elapsed}ms (target: ${this.TRIGGER_DELAY_MS}ms)`);

    if (result.patch && result.patch.reductionRate >= this.OPTIMIZATION_THRESHOLD) {
      // R171 FIX: 调用 ROIEngine 计算本 session 的 Alchemy Profit
      // ROIEngine 此前从未被调用，ROI 链处于断链状态
      // 现在在 patch 生成后立即计算并记录 ROI，实化 ROI 计算链
      const candidateId = context.metadata?.candidateId;
      const roiProfit: AlchemyProfit = this.roiEngine.calculateSessionProfit(
        trace,
        result.patch,
        context,
        candidateId
      );
      console.log(
        `[Optimizer/R171] ROI calculated: session=${roiProfit.sessionId} ` +
        `savings=$${roiProfit.savingsUsd} (${roiProfit.savingsToken} tokens), ` +
        `quality=${roiProfit.qualityScore}, pitfalls_avoided=${roiProfit.pitfallsAvoided}`
      );
      // R172 FIX: Persist ROI result to roi_wall.json so downstream consumers can read it
      this.roiEngine.recordProfit(roiProfit);
      await this.promoteToSkillLibrary(result.patch);
    }

    return result.patch;
  }

  /**
   * 更新SkillLibrary
   * 将精简路径写入工作流资产 → 更新asset-index.json
   */
  public async promoteToSkillLibrary(patch: EvolutionPatch): Promise<void> {
    console.log(`[Optimizer] Promoting optimized path to SkillLibrary: ${patch.reasoning}`);
    // 实际实现：写入 assets/cold_skills/ 和 asset-index.json
  }

  /**
   * PostTaskMetaReasoning (兼容旧接口)
   */
  public async postTaskMetaReasoning(
    actualTrace: PostToolUseData[],
    originalPlan: string[],
    context: HookContext
  ): Promise<EvolutionPatch | null> {
    const result = await this.optimize(actualTrace, originalPlan, context);
    return result.patch;
  }
}
