/**
 * @file ice_engine.ts
 * @description Implementation of the 3+1 Intent Clarification Engine (ICE).
 * Reference: Super Constitution §1.0 & §38 (ICE_Engine Module) + docs/10_Intent_Clarification_Engine.md
 *
 * 五维评分算法 (§5):
 *   goal           x 0.30 (最重要·不清楚就不知道做什么)
 *   deliverable    x 0.25 (不知道产出什么就无法验收)
 *   quality_bar    x 0.20 (不知道好坏标准就无法优化)
 *   constraints    x 0.15 (不知道边界可能做错方向)
 *   deadline/budget x 0.10 (影响策略选择)
 *
 * 评分达到0.85即可开始执行
 */

// ============================================
// IntentProfile 结构 (§4)
// ============================================

export interface IntentProfile {
  // 核心意图
  goal: string;
  deliverable: string;
  audience: string;
  quality_bar: string;

  // 约束条件
  constraints: string[];
  dependencies: string[];
  deadline: string | null;
  budget_tokens: number | null;

  // 路由信息
  domain: string;
  task_type: string;
  mode: 'search' | 'task' | 'workflow' | 'aal';

  // 状态
  related_assets: string[];
  clarity_score: number;
  questions_asked: number;
  filled_fields: string[];
  missing_critical: string[];
}

// 五维评分输入
export interface FiveDimensionalInput {
  goal: string | null;
  deliverable: string | null;
  quality_bar: string | null;
  constraints: string[] | null;
  deadline: string | null;
  budget_tokens: number | null;
}

// 五维评分结果
export interface FiveDimensionalScore {
  overall_score: number;  // 0-1
  goal_score: number;     // 0.30 weight
  deliverable_score: number; // 0.25 weight
  quality_bar_score: number; // 0.20 weight
  constraints_score: number; // 0.15 weight
  deadline_score: number; // 0.10 weight
  is_clear: boolean;     // >= 0.85
  missing_dimensions: string[];
}

// 兼容旧接口
export interface IntentClarity {
  score: number; // 0-1
  missingParams: string[];
  ambiguities: string[];
}

// ============================================
// ICE 引擎
// ============================================

/**
 * Intent Clarification Engine (ICE)
 * 实现五维加权评分算法 (§5)
 * 四种模式差异化追问策略 (§8)
 */
export class ICEEngine {
  private readonly CLARITY_THRESHOLD = 0.85;

  // 五维评分权重 (§5)
  private readonly WEIGHTS = {
    goal: 0.30,
    deliverable: 0.25,
    quality_bar: 0.20,
    constraints: 0.15,
    deadline: 0.10,
  } as const;

  // ========================================
  // 五维评分算法 (§5)
  // ========================================

  /**
   * 计算五维清晰度评分
   * @param input 五维输入
   * @returns 五维评分结果
   */
  public calculateFiveDimensionalScore(input: FiveDimensionalInput): FiveDimensionalScore {
    const missing_dimensions: string[] = [];

    // Goal 评分 (0.30)
    const goal_score = this.isFieldFilled(input.goal) ? 1 : 0;
    if (goal_score === 0) missing_dimensions.push('goal');

    // Deliverable 评分 (0.25)
    const deliverable_score = this.isFieldFilled(input.deliverable) ? 1 : 0;
    if (deliverable_score === 0) missing_dimensions.push('deliverable');

    // Quality Bar 评分 (0.20)
    const quality_bar_score = this.isFieldFilled(input.quality_bar) ? 1 : 0;
    if (quality_bar_score === 0) missing_dimensions.push('quality_bar');

    // Constraints 评分 (0.15)
    const constraints_score = this.isConstraintsFilled(input.constraints) ? 1 : 0;
    if (constraints_score === 0) missing_dimensions.push('constraints');

    // Deadline/Budget 评分 (0.10)
    const deadline_score = this.isDeadlineFilled(input.deadline, input.budget_tokens) ? 1 : 0;
    if (deadline_score === 0) missing_dimensions.push('deadline/budget');

    // 加权求和
    const overall_score =
      goal_score * this.WEIGHTS.goal +
      deliverable_score * this.WEIGHTS.deliverable +
      quality_bar_score * this.WEIGHTS.quality_bar +
      constraints_score * this.WEIGHTS.constraints +
      deadline_score * this.WEIGHTS.deadline;

    const result: FiveDimensionalScore = {
      overall_score: Math.round(overall_score * 100) / 100,
      goal_score,
      deliverable_score,
      quality_bar_score,
      constraints_score,
      deadline_score,
      is_clear: overall_score >= this.CLARITY_THRESHOLD,
      missing_dimensions,
    };

    console.log(`[ICE] Five-Dim Score: ${result.overall_score} (${JSON.stringify(result.missing_dimensions)})`);

    return result;
  }

  /**
   * 判断字段是否已填充
   */
  private isFieldFilled(value: string | null | undefined): boolean {
    return value !== null && value !== undefined && value.trim().length > 0;
  }

  /**
   * 判断约束条件是否已填充
   */
  private isConstraintsFilled(constraints: string[] | null | undefined): boolean {
    return constraints !== null && constraints !== undefined && constraints.length > 0;
  }

  /**
   * 判断截止日期/预算是否已填充
   */
  private isDeadlineFilled(deadline: string | null | undefined, budget_tokens: number | null | undefined): boolean {
    return this.isFieldFilled(deadline) || budget_tokens !== null && budget_tokens !== undefined;
  }

  // ========================================
  // IntentProfile 从五维输入构建
  // ========================================

  /**
   * 从五维输入构建 IntentProfile
   */
  public buildIntentProfile(input: FiveDimensionalInput, task_type: string = 'search_synth', mode: 'search' | 'task' | 'workflow' | 'aal' = 'search'): IntentProfile {
    const score = this.calculateFiveDimensionalScore(input);

    const filled_fields: string[] = [];
    if (this.isFieldFilled(input.goal)) filled_fields.push('goal');
    if (this.isFieldFilled(input.deliverable)) filled_fields.push('deliverable');
    if (this.isFieldFilled(input.quality_bar)) filled_fields.push('quality_bar');
    if (this.isConstraintsFilled(input.constraints)) filled_fields.push('constraints');
    if (this.isDeadlineFilled(input.deadline, input.budget_tokens)) filled_fields.push('deadline');

    return {
      goal: input.goal || '',
      deliverable: input.deliverable || '',
      audience: '',
      quality_bar: input.quality_bar || '',
      constraints: input.constraints || [],
      dependencies: [],
      deadline: input.deadline || null,
      budget_tokens: input.budget_tokens || null,
      domain: '',
      task_type,
      mode,
      related_assets: [],
      clarity_score: score.overall_score,
      questions_asked: 0,
      filled_fields,
      missing_critical: score.missing_dimensions,
    };
  }

  // ========================================
  // 意图评估 (兼容旧接口)
// ========================================

  /**
   * Evaluates a user query for clarity.
   */
  public evaluate(query: string, clarity: IntentClarity): {
    shouldClarify: boolean;
    questions: string[];
  } {
    console.log(`[ICE] Evaluating clarity: ${clarity.score} (Threshold: ${this.CLARITY_THRESHOLD})`);

    // 1. 0.85 清晰度评分触发逻辑
    if (clarity.score >= this.CLARITY_THRESHOLD) {
      return { shouldClarify: false, questions: [] };
    }

    // 2. Generate "3+1" questions
    const questions = this.generateQuestions(clarity);

    return { shouldClarify: true, questions };
  }

  /**
   * 基于 IntentProfile 评估 (新接口)
   */
  public evaluateProfile(profile: IntentProfile): {
    shouldClarify: boolean;
    questions: string[];
    profile: IntentProfile;
  } {
    const input: FiveDimensionalInput = {
      goal: profile.goal || null,
      deliverable: profile.deliverable || null,
      quality_bar: profile.quality_bar || null,
      constraints: profile.constraints?.length ? profile.constraints : null,
      deadline: profile.deadline || null,
      budget_tokens: profile.budget_tokens || null,
    };

    const score = this.calculateFiveDimensionalScore(input);
    profile.clarity_score = score.overall_score;
    profile.missing_critical = score.missing_dimensions;

    console.log(`[ICE] Profile clarity: ${score.overall_score} (is_clear: ${score.is_clear})`);

    if (score.is_clear) {
      return { shouldClarify: false, questions: [], profile };
    }

    const questions = this.generateQuestionsFromProfile(profile);
    profile.questions_asked++;

    return { shouldClarify: true, questions, profile };
  }

  /**
   * Generates questions based on the "3+1" pattern.
   * Up to 3 specific questions + 1 mandatory divergent question.
   */
  private generateQuestions(clarity: IntentClarity): string[] {
    const questions: string[] = [];

    // Limit to top 3 specific gaps/ambiguities
    const gaps = [...clarity.missingParams, ...clarity.ambiguities].slice(0, 3);
    gaps.forEach(gap => questions.push(`关于“${gap}”，能否提供更多细节？`));

    // 3. 硬编码第四个“泛相关”兜底问题 (非引导式、发散性)
    // 落地标准: 捕捉本地环境、特殊需求等隐含变量
    questions.push(
      "老板，为了确保万无一失，除了以上细节，您当前的本地环境或特殊需求中，还有什么是我需要额外注意的吗？"
    );

    return questions;
  }

  // ========================================
  // 四种模式差异化追问策略 (§8)
  // ========================================

  /**
   * 根据模式生成差异化追问 (§8)
   * 搜索模式: 重点是信息边界
   * 任务模式: 重点是验收标准
   * 工作流模式: 重点是触发条件和失败处理
   * AAL模式: 重点是自主空间和token预算
   */
  private generateQuestionsFromProfile(profile: IntentProfile): string[] {
    const questions: string[] = [];
    const missing = profile.missing_critical;

    // 按模式选择差异化问题
    switch (profile.mode) {
      case 'search':
        questions.push(...this.generateSearchModeQuestions(missing, profile));
        break;
      case 'task':
        questions.push(...this.generateTaskModeQuestions(missing, profile));
        break;
      case 'workflow':
        questions.push(...this.generateWorkflowModeQuestions(missing, profile));
        break;
      case 'aal':
        questions.push(...this.generateAALModeQuestions(missing, profile));
        break;
      default:
        // 默认通用问题
        questions.push(...this.generateGenericQuestions(missing));
    }

    // 第四问：泛相关兜底问题（仅当三问后仍<0.85）
    if (questions.length < 3) {
      questions.push(
        "老板，为了确保万无一失，除了以上细节，您当前的本地环境或特殊需求中，还有什么是我需要额外注意的吗？"
      );
    } else if (profile.questions_asked < 3) {
      // 确保至少有一个泛相关问题
      questions.push(
        "还有什么你觉得我需要知道的吗？比如偏好、格式、特殊要求？"
      );
    }

    return questions.slice(0, 4); // 最多4个问题
  }

  /**
   * 搜索模式追问策略 (§8.1)
   * 核心是「信息边界」
   */
  private generateSearchModeQuestions(missing: string[], profile: IntentProfile): string[] {
    const questions: string[] = [];

    if (missing.includes('goal')) {
      questions.push("你想了解的是关于什么的方面？是想了解最新进展还是系统性介绍？");
    }
    if (missing.includes('deliverable') && questions.length < 2) {
      questions.push("结果需要引用来源吗？还是只要总结性结论？");
    }
    if (missing.includes('quality_bar') && questions.length < 2) {
      questions.push("这个搜索结果是用来做什么的——直接使用还是作为后续任务的输入？");
    }

    return questions;
  }

  /**
   * 任务模式追问策略 (§8.2)
   * 核心是「验收标准」
   */
  private generateTaskModeQuestions(missing: string[], profile: IntentProfile): string[] {
    const questions: string[] = [];

    if (missing.includes('goal')) {
      questions.push("做完之后长什么样？产出物是文件、代码、配置还是报告？");
    }
    if (missing.includes('deliverable') && questions.length < 2) {
      questions.push("有没有格式要求？依赖什么已有的东西？");
    }
    if (missing.includes('constraints') && questions.length < 2) {
      // 专项问题根据任务类型动态生成
      questions.push(this.generateTypeSpecificQuestion(profile.task_type));
    }

    return questions;
  }

  /**
   * 工作流模式追问策略 (§8.3)
   * 核心是触发条件和失败处理
   */
  private generateWorkflowModeQuestions(missing: string[], profile: IntentProfile): string[] {
    const questions: string[] = [];

    if (missing.includes('goal')) {
      questions.push("这个工作流的触发条件是什么？手动触发还是自动触发？");
    }
    if (missing.includes('constraints') && questions.length < 2) {
      questions.push("如果工作流中途失败了，应该怎么处理？重试还是直接停止？");
    }
    if (missing.includes('deliverable') && questions.length < 2) {
      questions.push("什么时候可以认为这个工作流完成了？有没有明确的退出条件？");
    }

    return questions;
  }

  /**
   * AAL模式追问策略 (§8.4)
   * 核心是自主空间和token预算
   */
  private generateAALModeQuestions(missing: string[], profile: IntentProfile): string[] {
    const questions: string[] = [];

    if (missing.includes('constraints')) {
      questions.push("你能给我多大的自主空间？哪些操作必须经过你确认？");
    }
    if (missing.includes('deadline') && questions.length < 2) {
      questions.push("这次任务的token预算上限是多少？有没有明确的时间要求？");
    }
    if (missing.includes('goal') && questions.length < 2) {
      questions.push("这次任务的容错边界在哪里？哪些结果是绝对不能接受的？");
    }

    return questions;
  }

  /**
   * 通用追问（当模式未知时）
   */
  private generateGenericQuestions(missing: string[]): string[] {
    const questions: string[] = [];

    if (missing.includes('goal')) {
      questions.push("你最终想达成什么目标？");
    }
    if (missing.includes('deliverable')) {
      questions.push("产出物是什么形态？");
    }
    if (missing.includes('quality_bar')) {
      questions.push("怎样才算完成得好？有什么具体的标准吗？");
    }

    return questions;
  }

  /**
   * 根据任务类型生成专项问题 (§7)
   */
  private generateTypeSpecificQuestion(task_type: string): string {
    const questionMap: Record<string, string> = {
      // 信息搜索
      search_synth: "需要的是最新信息还是历史性系统介绍？",
      // 代码生成
      code_gen: "用什么编程语言？代码风格有要求吗？需要包含测试用例吗？",
      // 文档写作
      doc_write: "文档是给技术团队还是普通用户看的？字数大概多少？",
      // 问题诊断
      diagnosis: "报错信息是什么？之前尝试过什么解决方法？什么时候开始出现这个问题？",
      // 系统配置
      sys_config: "目标系统版本是什么？现有配置有什么？成功与否的判断标准是？",
      // 规划制定
      planning: "时间窗口多长？有哪些资源约束？最不能接受的风险是什么？",
      // 工作流搭建
      workflow: "触发条件是什么？失败时是重试还是回滚？退出条件是什么？",
      // 创意生成
      creative: "有没有参考风格或案例？有哪些不想要的元素？最终用在哪里？",
    };

    return questionMap[task_type] || "这个任务具体有什么特殊要求需要注意的吗？";
  }
}
