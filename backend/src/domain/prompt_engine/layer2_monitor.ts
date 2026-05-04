/**
 * M09 Layer2 执行监控层
 * ================================================
 * LLM 调用中实时监控
 * 职责：
 * 1. LLM-Judge 实时评分
 * 2. 执行轨迹记录
 * ================================================
 */

import {
  LLMJudgeScore,
  ExecutionTrace,
  ExecutionResult,
  TaskType,
  PromptFragment,
  QualityScore,
} from './types';

import * as crypto from 'crypto';

// ============================================
// LLM-Judge 评分器
// ============================================

/**
 * LLM-Judge 实时评分器
 * 对 LLM 输出进行实时质量评估
 */
export class LLMJudge {
  private qualityThreshold: number;

  constructor(qualityThreshold: number = 0.7) {
    this.qualityThreshold = qualityThreshold;
  }

  /**
   * 评估输出质量
   * @param output LLM 输出
   * @param context 评估上下文
   * @returns 质量评分
   */
  async evaluate(
    output: string,
    context: {
      taskType: TaskType;
      userInput: string;
      expectedFormat?: string;
      constraints?: string[];
    }
  ): Promise<LLMJudgeScore> {
    // 基础维度评分
    const completeness = this.evaluateCompleteness(output, context);
    const accuracy = this.evaluateAccuracy(output, context);
    const formatCompliance = this.evaluateFormat(output, context.expectedFormat);
    const preferenceMatch = this.evaluatePreferenceMatch(output, context);

    // 综合评分（加权平均）
    const weights = {
      completeness: 0.3,
      accuracy: 0.35,
      format_compliance: 0.2,
      preference_match: 0.15,
    };

    const overall =
      completeness * weights.completeness +
      accuracy * weights.accuracy +
      formatCompliance * weights.format_compliance +
      preferenceMatch * weights.preference_match;

    return {
      overall,
      completeness,
      accuracy,
      format_compliance: formatCompliance,
      preference_match: preferenceMatch,
      evaluated_at: new Date().toISOString(),
    };
  }

  /**
   * 评估完整性
   */
  private evaluateCompleteness(output: string, context: { constraints?: string[] }): number {
    if (!output || output.trim().length < 10) return 0;
    if (!context.constraints || context.constraints.length === 0) return 0.8;

    let matchCount = 0;
    for (const constraint of context.constraints) {
      if (output.toLowerCase().includes(constraint.toLowerCase())) {
        matchCount++;
      }
    }
    return Math.min(matchCount / context.constraints.length, 1.0);
  }

  /**
   * 评估准确性（简化版，实际应调用外部 LLM Judge）
   */
  private evaluateAccuracy(output: string, _context: { userInput: string }): number {
    // 简化：检查输出是否有明显的逻辑错误指示
    const errorIndicators = ['error', 'incorrect', 'wrong', '不确定', '可能错误'];
    const hasErrors = errorIndicators.some(indicator =>
      output.toLowerCase().includes(indicator)
    );
    return hasErrors ? 0.5 : 0.85;
  }

  /**
   * 评估格式合规性
   */
  private evaluateFormat(output: string, expectedFormat?: string): number {
    if (!expectedFormat) return 0.8;

    // 检查是否包含预期的格式标记
    const formatMarkers = {
      markdown: ['##', '###', '```', '**'],
      json: ['{', '}', '[', ']'],
      table: ['|', '---'],
    };

    for (const [type, markers] of Object.entries(formatMarkers)) {
      if (expectedFormat.toLowerCase().includes(type)) {
        const matchCount = markers.filter(m => output.includes(m)).length;
        return matchCount / markers.length;
      }
    }
    return 0.8;
  }

  /**
   * 评估用户偏好匹配
   */
  private evaluatePreferenceMatch(
    output: string,
    _context: { userInput: string }
  ): number {
    // 简化：检查输出长度是否适中（不太短也不太长）
    const length = output.length;
    if (length < 50) return 0.4;
    if (length < 200) return 0.7;
    if (length < 2000) return 0.9;
    return 0.7;
  }

  /**
   * 检查是否需要重试
   */
  shouldRetry(score: LLMJudgeScore): boolean {
    return score.overall < this.qualityThreshold;
  }

  getQualityThreshold(): number {
    return this.qualityThreshold;
  }
}

// ============================================
// 执行轨迹记录器
// ============================================

/**
 * 执行轨迹记录器
 * 记录完整执行上下文供夜间进化分析
 */
export class ExecutionTracker {
  private traces: ExecutionTrace[];
  private maxTraces: number;

  constructor(maxTraces: number = 10000) {
    this.maxTraces = maxTraces;
    this.traces = [];
  }

  /**
   * 记录执行轨迹
   */
  async record(params: {
    taskType: TaskType;
    fragmentsUsed: string[];
    qualityScore: number;
    tokenConsumed: number;
    result: ExecutionResult;
    failureReason?: string;
    retryCount?: number;
  }): Promise<ExecutionTrace> {
    const trace: ExecutionTrace = {
      id: `trace_${Date.now()}_${crypto.randomUUID().replace(/-/g, '').substring(0, 9)}`,
      timestamp: new Date().toISOString(),
      task_type: params.taskType,
      fragments_used: params.fragmentsUsed,
      quality_score: params.qualityScore,
      token_consumed: params.tokenConsumed,
      result: params.result,
      failure_reason: params.failureReason,
      retry_count: params.retryCount || 0,
    };

    this.traces.push(trace);

    // 限制轨迹数量
    if (this.traces.length > this.maxTraces) {
      this.traces = this.traces.slice(-this.maxTraces);
    }

    return trace;
  }

  /**
   * 获取指定时间范围的轨迹
   */
  getTracesByTimeRange(startTime: string, endTime: string): ExecutionTrace[] {
    const start = new Date(startTime).getTime();
    const end = new Date(endTime).getTime();
    return this.traces.filter(t => {
      const time = new Date(t.timestamp).getTime();
      return time >= start && time <= end;
    });
  }

  /**
   * 获取指定任务类型的轨迹
   */
  getTracesByTaskType(taskType: TaskType): ExecutionTrace[] {
    return this.traces.filter(t => t.task_type === taskType);
  }

  /**
   * 获取低分轨迹（供 GEPA 分析）
   */
  getLowScoreTraces(threshold: number = 0.7): ExecutionTrace[] {
    return this.traces.filter(t => t.quality_score < threshold);
  }

  /**
   * 获取高分轨迹（供 GEPA 分析）
   */
  getHighScoreTraces(threshold: number = 0.9): ExecutionTrace[] {
    return this.traces.filter(t => t.quality_score >= threshold);
  }

  /**
   * 获取统计数据
   */
  getStats(): {
    totalTraces: number;
    avgQualityScore: number;
    successRate: number;
    avgTokenConsumed: number;
    byTaskType: Record<TaskType, { count: number; avgScore: number }>;
  } {
    const totalTraces = this.traces.length;
    if (totalTraces === 0) {
      return {
        totalTraces: 0,
        avgQualityScore: 0,
        successRate: 0,
        avgTokenConsumed: 0,
        byTaskType: {} as Record<TaskType, { count: number; avgScore: number }>,
      };
    }

    const avgQualityScore =
      this.traces.reduce((sum, t) => sum + t.quality_score, 0) / totalTraces;
    const successCount = this.traces.filter(
      t => t.result === ExecutionResult.SUCCESS
    ).length;
    const successRate = successCount / totalTraces;
    const avgTokenConsumed =
      this.traces.reduce((sum, t) => sum + t.token_consumed, 0) / totalTraces;

    // 按任务类型分组
    const byTaskType: Record<string, { count: number; totalScore: number }> = {};
    for (const trace of this.traces) {
      const key = trace.task_type;
      if (!byTaskType[key]) {
        byTaskType[key] = { count: 0, totalScore: 0 };
      }
      byTaskType[key].count++;
      byTaskType[key].totalScore += trace.quality_score;
    }

    const byTaskTypeResult = {} as Record<TaskType, { count: number; avgScore: number }>;
    for (const [key, value] of Object.entries(byTaskType)) {
      byTaskTypeResult[key as TaskType] = {
        count: value.count,
        avgScore: value.totalScore / value.count,
      };
    }

    return {
      totalTraces,
      avgQualityScore,
      successRate,
      avgTokenConsumed,
      byTaskType: byTaskTypeResult,
    };
  }

  /**
   * 清除旧轨迹
   */
  clearOlderThan(olderThan: string): number {
    const cutoff = new Date(olderThan).getTime();
    const before = this.traces.length;
    this.traces = this.traces.filter(
      t => new Date(t.timestamp).getTime() >= cutoff
    );
    return before - this.traces.length;
  }
}

// ============================================
// LLM 监控狗（主入口）
// ============================================

/**
 * LLM 监控狗
 * 协调 LLM-Judge 和执行轨迹记录
 */
export class LLMWatchdog {
  private judge: LLMJudge;
  private tracker: ExecutionTracker;
  private config: { maxRetries: number; qualityThreshold: number };

  constructor(config?: { maxRetries?: number; qualityThreshold?: number }) {
    this.config = {
      maxRetries: config?.maxRetries ?? 3,
      qualityThreshold: config?.qualityThreshold ?? 0.7,
    };
    this.judge = new LLMJudge(this.config.qualityThreshold);
    this.tracker = new ExecutionTracker();
  }

  /**
   * 评估并记录
   */
  async evaluateAndRecord(params: {
    output: string;
    taskType: TaskType;
    fragmentsUsed: string[];
    tokenConsumed: number;
    result: ExecutionResult;
    userInput: string;
    expectedFormat?: string;
    constraints?: string[];
    failureReason?: string;
    retryCount?: number;
  }): Promise<{
    score: LLMJudgeScore;
    trace: ExecutionTrace;
    shouldRetry: boolean;
  }> {
    const score = await this.judge.evaluate(params.output, {
      taskType: params.taskType,
      userInput: params.userInput,
      expectedFormat: params.expectedFormat,
      constraints: params.constraints,
    });

    const trace = await this.tracker.record({
      taskType: params.taskType,
      fragmentsUsed: params.fragmentsUsed,
      qualityScore: score.overall,
      tokenConsumed: params.tokenConsumed,
      result: params.result,
      failureReason: params.failureReason,
      retryCount: params.retryCount,
    });

    const shouldRetry = this.judge.shouldRetry(score) &&
      (params.retryCount || 0) < this.config.maxRetries;

    return { score, trace, shouldRetry };
  }

  /**
   * 获取轨迹记录器
   */
  getTracker(): ExecutionTracker {
    return this.tracker;
  }

  /**
   * 获取评分器
   */
  getJudge(): LLMJudge {
    return this.judge;
  }
}
