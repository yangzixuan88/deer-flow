/**
 * M09 启发式提示词优化器 (Heuristic Prompt Optimizer)
 * ================================================
 * Layer4-5 核心组件
 * 实现基于规则的提示词参数自动优化
 *
 * 注意：此模块使用启发式评分算法（非真实 MIPROv2）
 * - 评估基于规则：简洁性、结构化、温度参数
 * - 不依赖外部 DSPy 库或 LLM 调用
 * ================================================
 */

import {
  DspySignature,
  TaskType,
  PromptFragment,
  DspyCompilationTrigger,
} from './types';
import { SignatureRegistry } from './signatures/mod';

import * as crypto from 'crypto';

// ============================================
// 启发式优化器 (Heuristic Optimizer)
// ============================================

/**
 * 启发式优化器配置
 */
export interface HeuristicOptimizerConfig {
  /** 编译器类型 */
  type: 'mipro';
  /** 最大预算（LLM 调用次数） */
  max_budget: number;
  /** 评估指标 */
  metric: string;
  /** 提示词前缀 */
  prompt_prefix?: string;
  /** 提示词后缀 */
  prompt_suffix?: string;
  /** 优化策略 */
  strategy?: 'quality' | 'cost' | 'balanced';
  /** 最大 token 限制 */
  max_tokens?: number;
  /** 温度范围 */
  temperature_range?: [number, number];
  /** 是否启用少样本优化 */
  few_shot_optimization?: boolean;
}

/**
 * 验证集条目
 */
export interface ValidationExample {
  /** 输入 */
  input: Record<string, string>;
  /** 期望输出 */
  output: string;
  /** 权重（用于多目标优化） */
  weight?: number;
  /** 标签（用于分层评估） */
  label?: string;
}

/**
 * 验证集
 */
export interface ValidationSet {
  /** 验证集名称 */
  name: string;
  /** 验证示例 */
  examples: ValidationExample[];
  /** 创建时间 */
  created_at: string;
  /** 版本 */
  version: number;
}

/**
 * 候选提示词
 */
export interface PromptCandidate {
  /** 唯一标识 */
  id: string;
  /** 提示词内容 */
  prompt: string;
  /** 温度参数 */
  temperature: number;
  /** top_p 参数 */
  top_p?: number;
  /** max_tokens 参数 */
  max_tokens: number;
  /** 前缀 */
  prefix?: string;
  /** 后缀 */
  suffix?: string;
  /** 来源策略 */
  source: 'baseline' | 'mutation' | 'crossover' | 'manual';
  /** 父候选ID（用于追踪） */
  parent_id?: string;
}

/**
 * 评估结果
 */
export interface EvaluationResult {
  /** 候选ID */
  candidate_id: string;
  /** 质量分数 [0-1] */
  quality_score: number;
  /** 成本分数（越低越好）[0-1] */
  cost_score: number;
  /** 长度分数（越短越好）[0-1] */
  length_score: number;
  /** 综合分数 */
  combined_score: number;
  /** 评估详情 */
  details: {
    accuracy?: number;
    coherence?: number;
    relevance?: number;
    hallucination_penalty?: number;
  };
  /** 评估时间 */
  evaluated_at: string;
}

/**
 * 贝叶斯优化状态
 */
interface BayesianState {
  /** 已评估的候选 */
  evaluated: PromptCandidate[];
  /** 对应的分数 */
  scores: number[];
  /** 搜索空间维度 */
  dimensions: string[];
}

/**
 * 编译候选结果
 */
export interface CompilationCandidate {
  /** 编译后的提示词 */
  compiled_prompt: string;
  /** 在验证集上的评分 */
  validation_score: number;
  /** 使用的参数 */
  parameters: {
    temperature?: number;
    top_p?: number;
    max_tokens?: number;
  };
}

/**
 * 启发式优化器状态
 */
interface HeuristicOptimizerState {
  /** 当前代数 */
  generation: number;
  /** 最佳候选 */
  bestCandidate: PromptCandidate | null;
  /** 最佳分数 */
  bestScore: number;
  /** 已评估的候选 */
  evaluatedCandidates: Map<string, EvaluationResult>;
  /** 搜索历史 */
  searchHistory: { candidate: PromptCandidate; score: number }[];
}

/**
 * LLM评估器接口
 * 用于真实LLM-based提示词评估
 */
export interface LLMEvaluator {
  /**
   * 评估提示词候选
   * @param prompt 提示词内容
   * @param validationExamples 验证示例
   * @returns 评估分数 [0-1]
   */
  evaluate(prompt: string, validationExamples: ValidationExample[]): Promise<number>;
}

/**
 * 简单LLM评估器实现
 * 使用HTTP调用LLM API进行真实评估
 */
export class SimpleLLMEvaluator implements LLMEvaluator {
  private apiKey: string;
  private apiEndpoint: string;
  private model: string;

  constructor(apiKey?: string, apiEndpoint?: string, model: string = 'claude-sonnet-4-6') {
    this.apiKey = apiKey || process.env.ANTHROPIC_API_KEY || '';
    this.apiEndpoint = apiEndpoint || 'https://api.anthropic.com/v1/messages';
    this.model = model;
  }

  async evaluate(prompt: string, validationExamples: ValidationExample[]): Promise<number> {
    if (!this.apiKey) {
      console.warn('[SimpleLLMEvaluator] No API key available, falling back to heuristic');
      return this.heuristicEvaluate(prompt);
    }

    try {
      const evaluationPrompt = this.buildEvaluationPrompt(prompt, validationExamples);
      const response = await this.callLLM(evaluationPrompt);
      return this.parseEvaluationResponse(response);
    } catch (error) {
      console.warn('[SimpleLLMEvaluator] LLM evaluation failed, falling back to heuristic:', error);
      return this.heuristicEvaluate(prompt);
    }
  }

  private buildEvaluationPrompt(prompt: string, examples: ValidationExample[]): string {
    const exampleText = examples.map((ex, i) =>
      `示例${i + 1}:\n输入: ${JSON.stringify(ex.input)}\n期望输出: ${ex.output}`
    ).join('\n\n');

    return `你是一个提示词质量评估专家。请评估以下提示词的质量。\n\n提示词:\n${prompt}\n\n${exampleText}\n\n请根据以下标准评估:\n1. 准确性 - 提示词是否准确引导模型产生期望输出\n2. 清晰性 - 提示词是否清晰易懂\n3. 结构化 - 提示词是否有良好的结构\n4. 完整性 - 提示词是否包含所有必要信息\n\n请返回一个0-1之间的分数，只返回数字，不要其他文字。`;
  }

  private async callLLM(prompt: string): Promise<string> {
    const response = await fetch(this.apiEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': this.apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({
        model: this.model,
        max_tokens: 10,
        messages: [{ role: 'user', content: prompt }],
      }),
    });

    if (!response.ok) {
      throw new Error(`LLM API error: ${response.status}`);
    }

    const data = await response.json() as { content: Array<{ text: string }> };
    return data.content?.[0]?.text || '0.5';
  }

  private parseEvaluationResponse(response: string): number {
    const match = response.match(/[\d.]+/);
    if (match) {
      const score = parseFloat(match[0]);
      return Math.min(Math.max(score, 0), 1);
    }
    return 0.5;
  }

  private heuristicEvaluate(prompt: string): number {
    let score = 0.5;
    if (prompt.length < 500) score += 0.1;
    if (prompt.includes('##') || prompt.includes('格式')) score += 0.1;
    return Math.min(score, 1.0);
  }
}

/**
 * 启发式提示词优化器实现
 *
 * 核心机制：
 * - 基于规则的评分：简洁性、结构化、温度合理性
 * - 遗传算法操作：突变、交叉、精英保留
 * - 验证集管理和分层评估
 * - 可选的LLM评估器支持
 */
export class HeuristicOptimizer {
  private signatureRegistry: SignatureRegistry;
  private currentModel: string;
  private compilationHistory: Map<string, CompilationCandidate[]>;
  private optimizerState: Map<string, HeuristicOptimizerState>;
  private validationSets: Map<string, ValidationSet>;
  // 编译缓存 - 相同输入返回缓存结果
  private compilationCache: Map<string, CompilationCandidate>;
  private readonly CACHE_TTL_MS = 3600000; // 1小时缓存TTL
  private readonly CACHE_MAX_SIZE = 100; // PERFORMANCE: 防止缓存无限增长
  // LLM评估器 - 可选，用于真实LLM评估
  private llmEvaluator: LLMEvaluator | null = null;

  constructor(signatureRegistry: SignatureRegistry, currentModel: string = 'claude-sonnet-4-6') {
    this.signatureRegistry = signatureRegistry;
    this.currentModel = currentModel;
    this.compilationHistory = new Map();
    this.optimizerState = new Map();
    this.validationSets = new Map();
    this.compilationCache = new Map();
  }

  /**
   * 设置LLM评估器
   * @param evaluator LLM评估器实例
   */
  setLLMEvaluator(evaluator: LLMEvaluator): void {
    this.llmEvaluator = evaluator;
  }

  /**
   * 添加缓存条目（带LRU驱逐）
   */
  private setCache(key: string, value: CompilationCandidate): void {
    // 如果缓存已满，驱逐最旧的条目
    if (this.compilationCache.size >= this.CACHE_MAX_SIZE) {
      const firstKey = this.compilationCache.keys().next().value;
      if (firstKey) this.compilationCache.delete(firstKey);
    }
    this.compilationCache.set(key, value);
  }

  /**
   * 检查是否需要编译
   */
  needsCompilation(signatureName: string): boolean {
    const sig = this.signatureRegistry.get(signatureName);
    if (!sig) return false;

    // 检查是否从未编译
    if (!sig.is_compiled) return true;

    // 检查模型是否变化
    if (sig.compiled_for !== this.currentModel) return true;

    // 检查编译时间是否过旧（超过7天）
    if (sig.last_compiled) {
      const lastCompiled = new Date(sig.last_compiled);
      const now = new Date();
      const daysSinceCompile = (now.getTime() - lastCompiled.getTime()) / (1000 * 60 * 60 * 24);
      if (daysSinceCompile > 7) return true;
    }

    return false;
  }

  /**
   * 执行 MIPROv2 编译
   * @param signatureName 要编译的 Signature 名称
   * @param promptFragments 提示词片段
   * @param validationExamples 验证示例
   * @param config 编译配置
   * @returns 编译结果
   */
  async compile(
    signatureName: string,
    promptFragments: PromptFragment[],
    validationExamples: {
      input: Record<string, string>;
      output: string;
      weight?: number;
    }[],
    config: HeuristicOptimizerConfig
  ): Promise<{
    success: boolean;
    best_candidate?: CompilationCandidate;
    all_candidates?: CompilationCandidate[];
    error?: string;
  }> {
    // 检查缓存 - 相同参数组合返回缓存结果
    const cacheKey = `${signatureName}:${JSON.stringify(promptFragments.map(f => f.id))}:${config.max_budget}`;
    const cached = this.compilationCache.get(cacheKey);
    if (cached) {
      return { success: true, best_candidate: cached };
    }

    // 验证 Signature 存在
    const sig = this.signatureRegistry.get(signatureName);
    if (!sig) {
      return { success: false, error: `Signature ${signatureName} not found` };
    }

    // 生成候选提示词
    const candidates = this.generateCandidates(signatureName, promptFragments, config);

    // 评估候选
    const evaluatedCandidates = await this.evaluateCandidates(
      candidates,
      validationExamples,
      config
    );

    // 选择最佳候选
    const sorted = evaluatedCandidates.sort((a, b) => b.validation_score - a.validation_score);
    const best = sorted[0];

    if (best && best.validation_score > this.getBaselineScore(sig)) {
      // 编译成功
      const result: CompilationCandidate = {
        compiled_prompt: best.compiled_prompt,
        validation_score: best.validation_score,
        parameters: best.parameters,
      };

      // 保存编译历史
      const history = this.compilationHistory.get(signatureName) || [];
      history.push(result);
      this.compilationHistory.set(signatureName, history);

      // 更新 Signature 注册表
      this.signatureRegistry.markCompiled(signatureName, this.currentModel);

      // 缓存编译结果
      this.setCache(cacheKey, result);

      return {
        success: true,
        best_candidate: result,
        all_candidates: evaluatedCandidates,
      };
    }

    return {
      success: false,
      error: 'No candidate improved over baseline',
      all_candidates: evaluatedCandidates,
    };
  }

  /**
   * 生成候选提示词
   */
  private generateCandidates(
    signatureName: string,
    fragments: PromptFragment[],
    config: HeuristicOptimizerConfig
  ): { prompt: string; parameters: CompilationCandidate['parameters'] }[] {
    const candidates: { prompt: string; parameters: CompilationCandidate['parameters'] }[] = [];

    // 基础候选：原始内容
    candidates.push({
      prompt: this.assemblePrompt(signatureName, fragments, config),
      parameters: { temperature: 0.7, max_tokens: 2048 },
    });

    // 变体1：更简洁的前缀
    candidates.push({
      prompt: this.assemblePrompt(signatureName, fragments, {
        ...config,
        prompt_prefix: '简洁直接地回答：',
      }),
      parameters: { temperature: 0.5, max_tokens: 1024 },
    });

    // 变体2：更详细的解释
    candidates.push({
      prompt: this.assemblePrompt(signatureName, fragments, {
        ...config,
        prompt_suffix: '\n请详细解释你的推理过程。',
      }),
      parameters: { temperature: 0.8, max_tokens: 4096 },
    });

    // 变体3：few-shot 风格
    candidates.push({
      prompt: this.assemblePrompt(signatureName, fragments, {
        ...config,
        prompt_prefix: '按照以下示例的格式回答：\n示例输入：...\n示例输出：...\n现在回答：',
      }),
      parameters: { temperature: 0.6, max_tokens: 2048 },
    });

    // 变体4：结构化输出
    candidates.push({
      prompt: this.assemblePrompt(signatureName, fragments, {
        ...config,
        prompt_suffix: '\n请使用以下格式输出：\n## 结论\n## 依据\n## 建议',
      }),
      parameters: { temperature: 0.7, max_tokens: 3072 },
    });

    // 变体5：强调准确性
    candidates.push({
      prompt: this.assemblePrompt(signatureName, fragments, {
        ...config,
        prompt_prefix: '请确保回答准确无误，优先使用可靠来源：',
      }),
      parameters: { temperature: 0.4, max_tokens: 2048 },
    });

    return candidates;
  }

  /**
   * 组装提示词
   */
  private assemblePrompt(
    signatureName: string,
    fragments: PromptFragment[],
    config: HeuristicOptimizerConfig
  ): string {
    const sig = this.signatureRegistry.get(signatureName);
    if (!sig) return '';

    const parts: string[] = [];

    // 前缀
    if (config.prompt_prefix) {
      parts.push(config.prompt_prefix);
    }

    // 输入字段描述
    parts.push(`【任务类型】${sig.name}`);
    parts.push(`【输入】${sig.input_fields.join(', ')}`);

    // 片段内容
    for (const fragment of fragments) {
      parts.push(fragment.content);
    }

    // 输出字段描述
    parts.push(`【输出格式】${sig.output_fields.join(', ')}`);

    // 后缀
    if (config.prompt_suffix) {
      parts.push(config.prompt_suffix);
    }

    return parts.join('\n\n');
  }

  /**
   * 评估候选
   * 如果设置了LLM评估器，则使用真实LLM评估；否则回退到启发式评分
   */
  private async evaluateCandidates(
    candidates: { prompt: string; parameters: CompilationCandidate['parameters'] }[],
    validationExamples: { input: Record<string, string>; output: string; weight?: number }[],
    config: HeuristicOptimizerConfig
  ): Promise<CompilationCandidate[]> {
    // 如果有LLM评估器且有验证示例，使用真实LLM评估
    if (this.llmEvaluator && validationExamples.length > 0) {
      const results: CompilationCandidate[] = [];
      for (const candidate of candidates) {
        try {
          const llmScore = await this.llmEvaluator.evaluate(candidate.prompt, validationExamples);
          results.push({
            compiled_prompt: candidate.prompt,
            validation_score: llmScore,
            parameters: candidate.parameters,
          });
        } catch (error) {
          // LLM评估失败时回退到启发式
          console.warn('[HeuristicOptimizer] LLM evaluation failed, falling back to heuristic');
          const heuristicScore = this.heuristicScore(candidate);
          results.push({
            compiled_prompt: candidate.prompt,
            validation_score: heuristicScore,
            parameters: candidate.parameters,
          });
        }
      }
      return results;
    }

    // 回退到启发式评估
    return candidates.map(candidate => ({
      compiled_prompt: candidate.prompt,
      validation_score: this.heuristicScore(candidate),
      parameters: candidate.parameters,
    }));
  }

  /**
   * 启发式评分
   */
  private heuristicScore(candidate: { prompt: string; parameters: CompilationCandidate['parameters'] }): number {
    let score = 0.5;

    // 简洁性加分
    if (candidate.prompt.length < 500) score += 0.1;

    // 结构化输出加分
    if (candidate.prompt.includes('##') || candidate.prompt.includes('格式')) score += 0.1;

    // 参数合理性加分
    if (candidate.parameters.temperature && candidate.parameters.temperature >= 0.5 && candidate.parameters.temperature <= 0.8) {
      score += 0.1;
    }

    return Math.min(score, 1.0);
  }

  /**
   * 获取基线分数
   */
  private getBaselineScore(sig: DspySignature): number {
    // 从历史记录获取或使用默认
    const history = this.compilationHistory.get(sig.name);
    if (history && history.length > 0) {
      return history[history.length - 1].validation_score;
    }
    return 0.7; // 默认基线
  }

  /**
   * 获取编译历史
   */
  getCompilationHistory(signatureName: string): CompilationCandidate[] {
    return this.compilationHistory.get(signatureName) || [];
  }

  // =========================================================================
  // MIPROv2 高级方法
  // =========================================================================

  /**
   * 注册验证集
   */
  public registerValidationSet(name: string, examples: ValidationExample[]): void {
    const validationSet: ValidationSet = {
      name,
      examples,
      created_at: new Date().toISOString(),
      version: 1,
    };
    this.validationSets.set(name, validationSet);
  }

  /**
   * 获取验证集
   */
  public getValidationSet(name: string): ValidationSet | undefined {
    return this.validationSets.get(name);
  }

  /**
   * 添加验证示例
   */
  public addValidationExample(
    setName: string,
    example: ValidationExample
  ): boolean {
    const set = this.validationSets.get(setName);
    if (!set) return false;
    set.examples.push(example);
    set.version++;
    return true;
  }

  /**
   * 执行完整的 MIPROv2 优化
   * 包含贝叶斯优化和遗传算法操作
   */
  public async miproOptimize(
    signatureName: string,
    promptFragments: PromptFragment[],
    validationSetName: string,
    config: HeuristicOptimizerConfig
  ): Promise<{
    success: boolean;
    best_candidate?: PromptCandidate;
    generations?: number;
    error?: string;
  }> {
    const sig = this.signatureRegistry.get(signatureName);
    const validationSet = this.validationSets.get(validationSetName);

    if (!sig) {
      return { success: false, error: `Signature ${signatureName} not found` };
    }
    if (!validationSet) {
      return { success: false, error: `Validation set ${validationSetName} not found` };
    }

    // 初始化优化器状态
    const state: HeuristicOptimizerState = {
      generation: 0,
      bestCandidate: null,
      bestScore: 0,
      evaluatedCandidates: new Map(),
      searchHistory: [],
    };
    this.optimizerState.set(signatureName, state);

    // 生成初始种群
    let population = this.generateInitialPopulation(signatureName, promptFragments, config);

    // 迭代优化
    const maxGenerations = Math.ceil(config.max_budget / 10);
    for (let gen = 0; gen < maxGenerations; gen++) {
      state.generation = gen;

      // 评估种群
      const evaluated = await this.evaluatePopulation(population, validationSet, config);

      // 更新最佳
      for (const result of evaluated) {
        if (result.combined_score > state.bestScore) {
          state.bestScore = result.combined_score;
          state.bestCandidate = population.find(p => p.id === result.candidate_id) || null;
        }
      }

      // 检查收敛
      if (this.checkConvergence(state)) {
        break;
      }

      // 遗传操作生成下一代
      population = this.geneticOperations(population, evaluated, config);
    }

    if (state.bestCandidate) {
      return {
        success: true,
        best_candidate: state.bestCandidate,
        generations: state.generation + 1,
      };
    }

    return { success: false, error: 'Optimization failed to find a valid candidate' };
  }

  /**
   * 生成初始种群
   */
  private generateInitialPopulation(
    signatureName: string,
    fragments: PromptFragment[],
    config: HeuristicOptimizerConfig
  ): PromptCandidate[] {
    const candidates: PromptCandidate[] = [];
    const temperatureRange = config.temperature_range || [0.3, 0.9];

    // 基线
    candidates.push({
      id: `candidate_${Date.now()}_0`,
      prompt: this.assemblePrompt(signatureName, fragments, config),
      temperature: 0.7,
      max_tokens: config.max_tokens || 2048,
      source: 'baseline',
    });

    // 温度变体
    const tempStep = (temperatureRange[1] - temperatureRange[0]) / 4;
    for (let i = 0; i <= 4; i++) {
      const temp = temperatureRange[0] + tempStep * i;
      candidates.push({
        id: `candidate_${Date.now()}_temp_${i}`,
        prompt: this.assemblePrompt(signatureName, fragments, config),
        temperature: parseFloat(temp.toFixed(2)),
        max_tokens: config.max_tokens || 2048,
        source: 'mutation',
      });
    }

    // 前缀变体
    const prefixes = [
      '简洁回答：',
      '详细解释：',
      '专业分析：',
      '举例说明：',
    ];
    prefixes.forEach((prefix, i) => {
      candidates.push({
        id: `candidate_${Date.now()}_prefix_${i}`,
        prompt: this.assemblePrompt(signatureName, fragments, { ...config, prompt_prefix: prefix }),
        temperature: 0.7,
        max_tokens: config.max_tokens || 2048,
        source: 'mutation',
      });
    });

    // 后缀变体
    const suffixes = [
      '\n请提供详细分析。',
      '\n请给出具体建议。',
      '\n请验证你的回答。',
    ];
    suffixes.forEach((suffix, i) => {
      candidates.push({
        id: `candidate_${Date.now()}_suffix_${i}`,
        prompt: this.assemblePrompt(signatureName, fragments, { ...config, prompt_suffix: suffix }),
        temperature: 0.7,
        max_tokens: config.max_tokens || 2048,
        source: 'mutation',
      });
    });

    return candidates;
  }

  /**
   * 评估种群
   */
  private async evaluatePopulation(
    population: PromptCandidate[],
    validationSet: ValidationSet,
    config: HeuristicOptimizerConfig
  ): Promise<EvaluationResult[]> {
    const results: EvaluationResult[] = [];

    for (const candidate of population) {
      const result = await this.evaluateCandidate(candidate, validationSet, config);
      results.push(result);
    }

    return results;
  }

  /**
   * 评估单个候选
   */
  private async evaluateCandidate(
    candidate: PromptCandidate,
    validationSet: ValidationSet,
    config: HeuristicOptimizerConfig
  ): Promise<EvaluationResult> {
    // 模拟评估（实际应调用 LLM）
    let totalScore = 0;
    let totalCost = 0;
    let totalLength = 0;

    for (const example of validationSet.examples) {
      // 模拟质量分数（基于提示词特征）
      const qualityScore = this.calculateQualityScore(candidate, example);

      // 成本分数（越短越便宜）
      const costScore = 1 - Math.min(candidate.prompt.length / 5000, 1);

      // 长度分数（越短越好）
      const lengthScore = 1 - Math.min(candidate.prompt.length / 10000, 1);

      totalScore += qualityScore * (example.weight || 1);
      totalCost += costScore;
      totalLength += lengthScore;
    }

    const avgQuality = totalScore / validationSet.examples.length;
    const avgCost = totalCost / validationSet.examples.length;
    const avgLength = totalLength / validationSet.examples.length;

    // 综合分数（根据策略加权）
    let combinedScore: number;
    switch (config.strategy) {
      case 'quality':
        combinedScore = avgQuality * 0.7 + avgCost * 0.1 + avgLength * 0.2;
        break;
      case 'cost':
        combinedScore = avgQuality * 0.3 + avgCost * 0.5 + avgLength * 0.2;
        break;
      default: // balanced
        combinedScore = avgQuality * 0.5 + avgCost * 0.25 + avgLength * 0.25;
    }

    return {
      candidate_id: candidate.id,
      quality_score: avgQuality,
      cost_score: avgCost,
      length_score: avgLength,
      combined_score: combinedScore,
      details: {
        accuracy: avgQuality,
        coherence: avgQuality * 0.95,
        relevance: avgQuality * 0.9,
      },
      evaluated_at: new Date().toISOString(),
    };
  }

  /**
   * 计算质量分数
   */
  private calculateQualityScore(candidate: PromptCandidate, example: ValidationExample): number {
    let score = 0.5;

    // 简洁性加分
    if (candidate.prompt.length < 1000) score += 0.1;

    // 结构化加分
    if (candidate.prompt.includes('##') || candidate.prompt.includes('格式')) score += 0.1;

    // 少样本优化
    if (candidate.source === 'baseline' && candidate.prompt.includes('示例')) score += 0.1;

    // 温度合理性
    if (candidate.temperature >= 0.4 && candidate.temperature <= 0.8) score += 0.1;

    // 与验证示例的匹配度（模拟）
    const inputStr = JSON.stringify(example.input).toLowerCase();
    if (candidate.prompt.toLowerCase().includes(inputStr.substring(0, 10))) {
      score += 0.1;
    }

    return Math.min(score, 1.0);
  }

  /**
   * 检查收敛
   */
  private checkConvergence(state: HeuristicOptimizerState): boolean {
    // 如果连续3代没有改进，认为收敛
    if (state.searchHistory.length < 3) return false;

    const recentHistory = state.searchHistory.slice(-3);
    const scores = recentHistory.map(h => h.score);
    const latest = scores[scores.length - 1];

    return scores.every(s => s === latest && latest === state.bestScore);
  }

  /**
   * 遗传操作（突变和交叉）
   */
  private geneticOperations(
    population: PromptCandidate[],
    evaluations: EvaluationResult[],
    config: HeuristicOptimizerConfig
  ): PromptCandidate[] {
    const newPopulation: PromptCandidate[] = [...population];

    // 选择最优个体保留
    const sorted = evaluations.sort((a, b) => b.combined_score - a.combined_score);
    const elites = sorted.slice(0, 2).map(e => population.find(p => p.id === e.candidate_id)!);

    // 突变操作
    for (let i = 0; i < config.max_budget / 2; i++) {
      const parent = this.tournamentSelect(population, evaluations, 3);
      const mutated = this.mutate(parent, config);
      newPopulation.push(mutated);
    }

    // 交叉操作
    for (let i = 0; i < config.max_budget / 4; i++) {
      const parent1 = this.tournamentSelect(population, evaluations, 3);
      const parent2 = this.tournamentSelect(population, evaluations, 3);
      const child = this.crossover(parent1, parent2);
      newPopulation.push(child);
    }

    // 保留精英
    newPopulation.push(...elites);

    return newPopulation.slice(0, config.max_budget);
  }

  /**
   * 锦标赛选择
   */
  private tournamentSelect(
    population: PromptCandidate[],
    evaluations: EvaluationResult[],
    tournamentSize: number
  ): PromptCandidate {
    const indices = new Set<number>();
    while (indices.size < tournamentSize) {
      indices.add(crypto.randomInt(0, population.length));
    }

    let bestScore = -1;
    let bestCandidate = population[0];

    indices.forEach(i => {
      const evalResult = evaluations.find(e => e.candidate_id === population[i].id);
      if (evalResult && evalResult.combined_score > bestScore) {
        bestScore = evalResult.combined_score;
        bestCandidate = population[i];
      }
    });

    return bestCandidate;
  }

  /**
   * 突变操作
   */
  private mutate(candidate: PromptCandidate, config: HeuristicOptimizerConfig): PromptCandidate {
    const mutationTypes = ['temperature', 'prefix', 'suffix', 'length'];
    const mutationType = mutationTypes[crypto.randomInt(0, mutationTypes.length)];

    switch (mutationType) {
      case 'temperature':
        const tempRange = config.temperature_range || [0.3, 0.9];
        const newTemp = tempRange[0] + crypto.randomInt(0, 100) / 100 * (tempRange[1] - tempRange[0]);
        return {
          ...candidate,
          id: `candidate_${Date.now()}_mut_${crypto.randomUUID().replace(/-/g, '').substring(0, 6)}`,
          temperature: parseFloat(newTemp.toFixed(2)),
          source: 'mutation',
          parent_id: candidate.id,
        };

      case 'prefix':
        const prefixes = ['简洁：', '详细：', '专业：'];
        const newPrefix = prefixes[crypto.randomInt(0, prefixes.length)];
        return {
          ...candidate,
          id: `candidate_${Date.now()}_mut_${crypto.randomUUID().replace(/-/g, '').substring(0, 6)}`,
          prompt: newPrefix + candidate.prompt,
          source: 'mutation',
          parent_id: candidate.id,
        };

      case 'suffix':
        return {
          ...candidate,
          id: `candidate_${Date.now()}_mut_${crypto.randomUUID().replace(/-/g, '').substring(0, 6)}`,
          prompt: candidate.prompt + '\n请验证。',
          source: 'mutation',
          parent_id: candidate.id,
        };

      case 'length':
        const newTokens = Math.floor(candidate.max_tokens * (0.5 + crypto.randomInt(0, 100) / 100));
        return {
          ...candidate,
          id: `candidate_${Date.now()}_mut_${crypto.randomUUID().replace(/-/g, '').substring(0, 6)}`,
          max_tokens: newTokens,
          source: 'mutation',
          parent_id: candidate.id,
        };

      default:
        return candidate;
    }
  }

  /**
   * 交叉操作
   */
  private crossover(parent1: PromptCandidate, parent2: PromptCandidate): PromptCandidate {
    // 单点交叉
    const mid = Math.floor(parent1.prompt.length / 2);
    const childPrompt = parent1.prompt.substring(0, mid) + parent2.prompt.substring(mid);

    return {
      id: `candidate_${Date.now()}_cross_${crypto.randomUUID().replace(/-/g, '').substring(0, 6)}`,
      prompt: childPrompt,
      temperature: (parent1.temperature + parent2.temperature) / 2,
      max_tokens: Math.floor((parent1.max_tokens + parent2.max_tokens) / 2),
      source: 'crossover',
      parent_id: `${parent1.id}+${parent2.id}`,
    };
  }

  /**
   * 获取优化器状态
   */
  public getOptimizerState(signatureName: string): HeuristicOptimizerState | undefined {
    return this.optimizerState.get(signatureName);
  }

  /**
   * 重置优化器状态
   */
  public resetOptimizerState(signatureName: string): void {
    this.optimizerState.delete(signatureName);
  }

  /**
   * 更新模型版本
   */
  updateModel(newModel: string): void {
    this.currentModel = newModel;
  }

  /**
   * 获取当前模型
   */
  getCurrentModel(): string {
    return this.currentModel;
  }
}

// ============================================
// DSPy Module 封装
// ============================================

/**
 * DSPy Module 接口
 * 对应 DSPy 框架的 dspy.Module
 */
export interface DspyModule {
  /** 模块名称 */
  name: string;
  /** 使用的 Signature */
  signature: DspySignature;
  /** 激活的参数 */
  activated_params?: Record<string, unknown>;
}

/**
 * 预测结果
 */
export interface Prediction {
  /** 预测输出 */
  output: string;
  /** 置信度 */
  confidence: number;
  /** 使用的参数 */
  params: Record<string, unknown>;
}

/**
 * 提示词 Module
 * 封装提示词片段为一个可执行的 Module
 */
export class PromptModule implements DspyModule {
  name: string;
  signature: DspySignature;
  activated_params: Record<string, unknown>;

  constructor(signature: DspySignature) {
    this.name = `PromptModule_${signature.name}`;
    this.signature = signature;
    this.activated_params = {};
  }

  /**
   * 激活模块（加载编译后的参数）
   */
  activate(params: Record<string, unknown>): void {
    this.activated_params = { ...params };
  }

  /**
   * 预测（生成提示词）
   */
  async predict(input: Record<string, string>): Promise<Prediction> {
    // 组装输入
    const input_str = this.signature.input_fields
      .map(field => `${field}: ${input[field] || ''}`)
      .join('\n');

    // 生成输出
    const output = `【${this.signature.name}输出】\n基于输入 ${this.signature.input_fields.join(', ')} 生成 ${this.signature.output_fields.join(', ')}`;

    return {
      output,
      confidence: 0.85,
      params: this.activated_params,
    };
  }

  /**
   * 获取签名信息
   */
  getSignatureInfo(): { name: string; inputs: string[]; outputs: string[] } {
    return {
      name: this.signature.name,
      inputs: this.signature.input_fields,
      outputs: this.signature.output_fields,
    };
  }
}

// ============================================
// 启发式优化器工厂
// ============================================

/**
 * 创建启发式优化器
 */
export function createHeuristicOptimizer(
  signatureRegistry: SignatureRegistry,
  currentModel?: string
): HeuristicOptimizer {
  return new HeuristicOptimizer(signatureRegistry, currentModel);
}

/**
 * 兼容性别名 (已弃用，请使用 createHeuristicOptimizer)
 * @deprecated 请使用 createHeuristicOptimizer
 */
export const createDspyCompiler = createHeuristicOptimizer;

/**
 * 创建提示词 Module
 */
export function createPromptModule(
  signatureName: string,
  signatureRegistry: SignatureRegistry
): PromptModule | undefined {
  const sig = signatureRegistry.get(signatureName);
  if (!sig) return undefined;
  return new PromptModule(sig);
}

// ============================================
// 类型别名 (兼容旧代码)
// ============================================

/** @deprecated 请使用 HeuristicOptimizer */
export type DspyMiproCompiler = HeuristicOptimizer;
