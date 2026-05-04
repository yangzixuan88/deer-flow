/**
 * M09 与 M10/M08 集成适配器
 * ================================================
 * 实现 M09 与现有系统的联动：
 * - M10 (ICEEngine): IntentProfile → 任务类型识别
 * - M08 (NightlyDistiller): 夜间复盘 → GEPA 进化数据
 * ================================================
 */

import {
  TaskType,
  PromptFragment,
  PromptFragmentType,
  PromptPriority,
  ExecutionResult,
  ExecutionTrace,
} from './types';

// 从 M10 导入（类型兼容）
export interface M10_IntentProfile {
  goal?: string;
  deliverable?: string;
  quality_bar?: string;
  constraints?: string[];
  deadline?: string;
  budget_tokens?: number | null;
  task_category?: string;
  execution_mode?: 'search' | 'task' | 'workflow' | 'aal';
}

export interface M10_ClarificationQuestion {
  question: string;
  dimension: 'goal' | 'deliverable' | 'quality_bar' | 'constraints' | 'deadline';
  type: 'open' | 'choice' | 'scale';
}

// 从 M08 导入（类型兼容）
export interface M08_ExperiencePackage {
  session_id: string;
  timestamp: string;
  task_type: string;
  intent_profile: M10_IntentProfile;
  tool_calls: {
    tool: string;
    input: string;
    output: string;
    duration_ms: number;
    success: boolean;
  }[];
  final_output: string;
  quality_score: number;
  token_cost: number;
  ge_path: string; // Generative Evolution path
  patterns: {
    pattern_id: string;
    description: string;
    reusable: boolean;
  }[];
  failures?: {
    step: number;
    error: string;
    recovery: string;
  }[];
}

// ============================================
// M10 意图澄清引擎 → M09 路由层 适配器
// ============================================

/**
 * M10-M09 意图映射器
 * 将 IntentProfile 映射为 M09 可用的任务类型和上下文
 */
export class M10ToM09Adapter {
  /**
   * 从 IntentProfile 推断 M09 任务类型
   */
  mapTaskType(profile: M10_IntentProfile): TaskType {
    // 基于 goal 和 task_category 推断
    const goal = (profile.goal || '').toLowerCase();
    const category = (profile.task_category || '').toLowerCase();
    const combined = goal + ' ' + category;

    // 代码生成
    if (
      combined.includes('code') ||
      combined.includes('function') ||
      combined.includes('程序') ||
      combined.includes('代码')
    ) {
      return TaskType.CODE_GEN;
    }

    // 文档写作
    if (
      combined.includes('document') ||
      combined.includes('doc') ||
      combined.includes('write') ||
      combined.includes('文档') ||
      combined.includes('文章')
    ) {
      return TaskType.DOC_WRITE;
    }

    // 数据分析
    if (
      combined.includes('data') ||
      combined.includes('analytics') ||
      combined.includes('分析') ||
      combined.includes('统计')
    ) {
      return TaskType.DATA_ANALYSIS;
    }

    // 问题诊断
    if (
      combined.includes('debug') ||
      combined.includes('fix') ||
      combined.includes('error') ||
      combined.includes('bug') ||
      combined.includes('诊断') ||
      combined.includes('修复')
    ) {
      return TaskType.DIAGNOSIS;
    }

    // 规划制定
    if (
      combined.includes('plan') ||
      combined.includes('schedule') ||
      combined.includes('规划') ||
      combined.includes('计划')
    ) {
      return TaskType.PLANNING;
    }

    // 创意生成
    if (
      combined.includes('creative') ||
      combined.includes('idea') ||
      combined.includes('创意') ||
      combined.includes('设计')
    ) {
      return TaskType.CREATIVE;
    }

    // 系统配置
    if (
      combined.includes('config') ||
      combined.includes('setup') ||
      combined.includes('install') ||
      combined.includes('配置') ||
      combined.includes('部署')
    ) {
      return TaskType.SYS_CONFIG;
    }

    // AAL 决策
    if (
      combined.includes('decision') ||
      combined.includes('aal') ||
      combined.includes('决策')
    ) {
      return TaskType.AAL_DECISION;
    }

    // 默认：信息搜索
    return TaskType.SEARCH_SYNTH;
  }

  /**
   * 从 IntentProfile 生成安全约束片段
   */
  mapSafetyConstraints(profile: M10_IntentProfile): PromptFragment[] {
    const fragments: PromptFragment[] = [];

    // 截止日期约束
    if (profile.deadline) {
      fragments.push({
        id: `safety_deadline_${Date.now()}`,
        type: PromptFragmentType.SYSTEM,
        content: `【截止时间】任务必须在 ${profile.deadline} 前完成`,
        priority: PromptPriority.P1_SAFETY,
        quality_score_history: [],
        gepa_version: 0,
        created_at: new Date().toISOString(),
      });
    }

    // Token 预算约束
    if (profile.budget_tokens !== null && profile.budget_tokens !== undefined) {
      fragments.push({
        id: `safety_budget_${Date.now()}`,
        type: PromptFragmentType.SYSTEM,
        content: `【Token预算】总消耗不超过 ${profile.budget_tokens} tokens，保持高效`,
        priority: PromptPriority.P1_SAFETY,
        quality_score_history: [],
        gepa_version: 0,
        created_at: new Date().toISOString(),
      });
    }

    // 质量标准约束
    if (profile.quality_bar) {
      fragments.push({
        id: `safety_quality_${Date.now()}`,
        type: PromptFragmentType.SYSTEM,
        content: `【质量标准】${profile.quality_bar}`,
        priority: PromptPriority.P1_SAFETY,
        quality_score_history: [],
        gepa_version: 0,
        created_at: new Date().toISOString(),
      });
    }

    return fragments;
  }

  /**
   * 从 IntentProfile 生成约束片段
   */
  mapConstraints(profile: M10_IntentProfile): PromptFragment[] {
    if (!profile.constraints || profile.constraints.length === 0) {
      return [];
    }

    return profile.constraints.map((constraint, i) => ({
      id: `constraint_${i}_${Date.now()}`,
      type: PromptFragmentType.SYSTEM,
      content: `【约束条件】${constraint}`,
      priority: PromptPriority.P3_TASK_SPECIFIC,
      quality_score_history: [],
      gepa_version: 0,
      created_at: new Date().toISOString(),
    }));
  }

  /**
   * 从 IntentProfile 推断执行模式
   */
  mapExecutionMode(mode: string): string {
    const modeMap: Record<string, string> = {
      search: 'SEARCH_SYNTH',
      task: 'CODE_GEN',
      workflow: 'PLANNING',
      aal: 'AAL_DECISION',
    };
    return modeMap[mode] || 'SEARCH_SYNTH';
  }
}

// ============================================
// M08 夜间复盘 → M09 GEPA 进化数据适配器
// ============================================

/**
 * M08-M09 经验包转换器
 * 将 NightlyDistiller 的 ExperiencePackage 转换为 M09 GEPA 可用的格式
 */
export class M08ToM09Adapter {
  /**
   * 将 ExperiencePackage 转换为执行轨迹
   */
  convertToExecutionTrace(exp: M08_ExperiencePackage): ExecutionTrace {
    // 确定执行结果
    let result: ExecutionResult;
    if (exp.quality_score >= 0.85) {
      result = ExecutionResult.SUCCESS;
    } else if (exp.quality_score >= 0.5) {
      result = ExecutionResult.PARTIAL;
    } else {
      result = exp.failures && exp.failures.length > 0
        ? ExecutionResult.FAILED
        : ExecutionResult.PARTIAL;
    }

    // 提取片段 ID（从 tool_calls 提取）
    const fragmentIds = exp.tool_calls.map((tc, i) =>
      `tool_${tc.tool}_${i}_${exp.session_id}`
    );

    return {
      id: `trace_${exp.session_id}_${Date.now()}`,
      timestamp: exp.timestamp,
      task_type: this.mapTaskType(exp.task_type),
      fragments_used: fragmentIds,
      quality_score: exp.quality_score,
      token_consumed: exp.token_cost,
      result,
      failure_reason: exp.failures?.[0]?.error,
      retry_count: exp.failures?.length || 0,
    };
  }

  /**
   * 映射任务类型
   */
  private mapTaskType(taskType: string): TaskType {
    const typeMap: Record<string, TaskType> = {
      search: TaskType.SEARCH_SYNTH,
      code_gen: TaskType.CODE_GEN,
      doc_write: TaskType.DOC_WRITE,
      data_analysis: TaskType.DATA_ANALYSIS,
      diagnosis: TaskType.DIAGNOSIS,
      planning: TaskType.PLANNING,
      creative: TaskType.CREATIVE,
      sys_config: TaskType.SYS_CONFIG,
      aal_decision: TaskType.AAL_DECISION,
    };

    return typeMap[taskType.toLowerCase()] || TaskType.SEARCH_SYNTH;
  }

  /**
   * 提取低分轨迹（供 GEPA 分析）
   */
  extractLowScoreTraces(experiences: M08_ExperiencePackage[], threshold: number = 0.7): M08_ExperiencePackage[] {
    return experiences.filter(exp => exp.quality_score < threshold);
  }

  /**
   * 提取高分轨迹（供 GEPA 分析）
   */
  extractHighScoreTraces(experiences: M08_ExperiencePackage[], threshold: number = 0.9): M08_ExperiencePackage[] {
    return experiences.filter(exp => exp.quality_score >= threshold);
  }

  /**
   * 提取可复用的模式
   */
  extractReusablePatterns(exp: M08_ExperiencePackage): PromptFragment[] {
    return exp.patterns
      .filter(p => p.reusable)
      .map((p, i) => ({
        id: `pattern_${p.pattern_id}_${Date.now()}`,
        type: PromptFragmentType.CHAIN_OF_THOUGHT,
        content: p.description,
        priority: PromptPriority.P4_FEW_SHOT,
        quality_score_history: [exp.quality_score],
        gepa_version: 0,
        source: `session_${exp.session_id}`,
        created_at: new Date().toISOString(),
        last_used_at: exp.timestamp,
      }));
  }
}

// ============================================
// M09 PromptRouter → M10 意图澄清联动
// ============================================

/**
 * M09-M10 联动协调器
 * 实现 PromptRouter 与 ICEEngine 的双向联动
 */
export class M09M10Coordinator {
  private m10Adapter: M10ToM09Adapter;

  constructor() {
    this.m10Adapter = new M10ToM09Adapter();
  }

  /**
   * 当 M09 无法确定任务类型时，请求 M10 澄清
   */
  requestClarification(userInput: string): {
    question: string;
    dimension: string;
    type: string;
  }[] {
    // 基于关键词推断可能缺失的维度
    const questions: {
      question: string;
      dimension: string;
      type: 'open' | 'choice' | 'scale';
    }[] = [];

    const lowerInput = userInput.toLowerCase();

    // 检查 goal
    if (!lowerInput.includes('什么') && !lowerInput.includes('how') && !lowerInput.includes('怎么')) {
      questions.push({
        question: '你的最终目标是什么？',
        dimension: 'goal',
        type: 'open',
      });
    }

    // 检查 deliverable
    if (!lowerInput.includes('输出') && !lowerInput.includes('结果') && !lowerInput.includes(' deliverable')) {
      questions.push({
        question: '你期望的产出是什么？',
        dimension: 'deliverable',
        type: 'choice',
      });
    }

    // 检查 deadline
    if (!lowerInput.includes('时间') && !lowerInput.includes('之前') && !lowerInput.includes('截止')) {
      questions.push({
        question: '有截止时间要求吗？',
        dimension: 'deadline',
        type: 'scale',
      });
    }

    return questions.slice(0, 3); // 最多3个问题
  }

  /**
   * 整合 IntentProfile 到提示词组装
   */
  integrateIntentProfile(
    profile: M10_IntentProfile,
    fragments: PromptFragment[]
  ): PromptFragment[] {
    const safetyFragments = this.m10Adapter.mapSafetyConstraints(profile);
    const constraintFragments = this.m10Adapter.mapConstraints(profile);

    return [
      ...safetyFragments,    // P1 安全约束（最高优先）
      ...fragments,         // 原有片段
      ...constraintFragments, // P3 任务约束
    ];
  }
}

// ============================================
// M09 PromptRouter → M08 夜间复盘联动
// ============================================

/**
 * M09-M08 联动协调器
 * 实现 PromptRouter 与 NightlyDistiller 的数据流动
 */
export class M09M08Coordinator {
  private m08Adapter: M08ToM09Adapter;

  constructor() {
    this.m08Adapter = new M08ToM09Adapter();
  }

  /**
   * 准备 GEPA 进化数据
   */
  prepareGepaData(experiences: M08_ExperiencePackage[]): {
    lowScoreTraces: ExecutionTrace[];
    highScoreTraces: ExecutionTrace[];
    reusablePatterns: PromptFragment[];
  } {
    const lowScoreExps = this.m08Adapter.extractLowScoreTraces(experiences);
    const highScoreExps = this.m08Adapter.extractHighScoreTraces(experiences);

    const lowScoreTraces = lowScoreExps.map(e => this.m08Adapter.convertToExecutionTrace(e));
    const highScoreTraces = highScoreExps.map(e => this.m08Adapter.convertToExecutionTrace(e));

    // 提取所有可复用模式
    const allPatterns = experiences.flatMap(e => this.m08Adapter.extractReusablePatterns(e));

    return {
      lowScoreTraces,
      highScoreTraces,
      reusablePatterns: allPatterns,
    };
  }

  /**
   * 从 GEPA 进化结果更新经验包
   */
  applyGepaResults(
    experiences: M08_ExperiencePackage[],
    evolvedFragments: PromptFragment[]
  ): M08_ExperiencePackage[] {
    // 为每个高分经验包添加进化后的片段
    return experiences.map(exp => {
      const relevantFragments = evolvedFragments.filter(f =>
        f.source && f.source.includes(exp.session_id)
      );

      if (relevantFragments.length === 0) {
        return exp;
      }

      // 更新经验包的 ge_path
      return {
        ...exp,
        ge_path: `evolved_${relevantFragments[0].gepa_version}`,
      };
    });
  }
}

// ============================================
// 集成主入口
// ============================================

/**
 * M09 系统集成器
 * 统一管理 M09 与 M10/M08 的联动
 */
export class M09Integrator {
  private m09m10: M09M10Coordinator;
  private m09m08: M09M08Coordinator;
  private m10Adapter: M10ToM09Adapter;
  private m08Adapter: M08ToM09Adapter;

  constructor() {
    this.m09m10 = new M09M10Coordinator();
    this.m09m08 = new M09M08Coordinator();
    this.m10Adapter = new M10ToM09Adapter();
    this.m08Adapter = new M08ToM09Adapter();
  }

  /**
   * 获取 M10 适配器
   */
  getM10Adapter(): M10ToM09Adapter {
    return this.m10Adapter;
  }

  /**
   * 获取 M08 适配器
   */
  getM08Adapter(): M08ToM09Adapter {
    return this.m08Adapter;
  }

  /**
   * 获取 M10 协调器
   */
  getM10Coordinator(): M09M10Coordinator {
    return this.m09m10;
  }

  /**
   * 获取 M08 协调器
   */
  getM08Coordinator(): M09M08Coordinator {
    return this.m09m08;
  }
}

// 导出单例
export const m09Integrator = new M09Integrator();
