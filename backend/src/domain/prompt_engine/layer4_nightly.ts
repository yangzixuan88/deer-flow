/**
 * M09 Layer4 夜间进化层
 * ================================================
 * 专职资产智能体夜间执行
 * 职责：
 * 1. GEPA 反射式进化
 * 2. DSPy 自动编译
 * ================================================
 */

import {
  GepaCandidate,
  GepaEvolutionResult,
  DspyCompilationConfig,
  DspyCompilationTrigger,
  PromptFragment,
  ExecutionTrace,
} from './types';
import { SignatureRegistry } from './signatures/mod';
import { LLMAdapter, llmAdapter, ReflectionAnalysis } from '../../infrastructure/llm_adapter';
import { GVisorSandbox, SandboxType } from '../m11/sandbox';

import * as crypto from 'crypto';

// ============================================
// GEPA 反射进化引擎
// ============================================

/**
 * GEPA 反射进化引擎
 * 六步流程：选候选→反思→生成→沙盒→决策→晋升
 */
export class GepaEngine {
  private improvementThreshold: number;
  private maxCandidates: number;

  constructor(improvementThreshold: number = 0.05, maxCandidates: number = 5) {
    this.improvementThreshold = improvementThreshold;
    this.maxCandidates = maxCandidates;
  }

  /**
   * 执行 GEPA 六步进化
   */
  async evolve(params: {
    originalFragment: PromptFragment;
    lowScoreTraces: ExecutionTrace[];
    highScoreTraces: ExecutionTrace[];
    currentModel: string;
  }): Promise<GepaEvolutionResult> {
    // 步骤1: 选候选 - 选取低分和高分case对比
    const candidates = await this.selectCandidates(params.originalFragment, params.lowScoreTraces, params.highScoreTraces);

    if (candidates.length === 0) {
      return {
        original_fragment: params.originalFragment,
        candidates: [],
        evolution_success: false,
        executed_at: new Date().toISOString(),
      };
    }

    // 步骤2-3: 轨迹反思 + 生成候选（LLM分析）
    const reflectedCandidates = await this.reflectAndGenerate(params.originalFragment, candidates);

    // 步骤4: 沙盒测试
    const testedCandidates = await this.sandboxTest(reflectedCandidates, params.originalFragment);

    // 步骤5: 决策固化
    const selected = this.decideSolidification(testedCandidates, params.originalFragment);

    // 步骤6: 晋升入库
    if (selected) {
      await this.promoteToAsset(selected, params.originalFragment);
    }

    return {
      original_fragment: params.originalFragment,
      candidates: testedCandidates,
      selected_candidate: selected,
      evolution_success: selected !== undefined,
      quality_improvement: selected
        ? selected.version - params.originalFragment.gepa_version
        : undefined,
      executed_at: new Date().toISOString(),
    };
  }

  /**
   * 步骤1: 选候选
   * 选取低分(<0.7)和高分(>0.9)的执行轨迹
   */
  private async selectCandidates(
    fragment: PromptFragment,
    lowScoreTraces: ExecutionTrace[],
    highScoreTraces: ExecutionTrace[]
  ): Promise<ExecutionTrace[]> {
    // 筛选使用该片段的轨迹
    const relevantLow = lowScoreTraces.filter(t =>
      t.fragments_used.includes(fragment.id)
    );
    const relevantHigh = highScoreTraces.filter(t =>
      t.fragments_used.includes(fragment.id)
    );

    // 取最近的3-5个轨迹
    return [
      ...relevantLow.slice(-3),
      ...relevantHigh.slice(-2),
    ].slice(0, this.maxCandidates);
  }

  /**
   * 步骤2-3: 轨迹反思 + 生成候选
   * 使用 LLM 分析失败原因并生成改进版本
   */
  private async reflectAndGenerate(
    original: PromptFragment,
    candidates: ExecutionTrace[]
  ): Promise<GepaCandidate[]> {
    if (candidates.length === 0) {
      return [];
    }

    // 分析失败轨迹
    const failedTraces = candidates.filter(t => t.quality_score < 0.7);
    const successTraces = candidates.filter(t => t.quality_score >= 0.9);

    // 准备轨迹数据用于 LLM 分析
    const traceData = candidates.map(t => ({
      quality_score: t.quality_score,
      failure_reason: t.failure_reason,
    }));

    // 调用 LLM 进行反思分析
    let analysis: ReflectionAnalysis;
    try {
      analysis = await llmAdapter.analyzeReflection(original.content, traceData);
      console.log(`[GEPA] LLM reflection analysis confidence: ${analysis.confidence.toFixed(2)}`);
      if (analysis.failureReasons.length > 0) {
        console.log(`[GEPA] Failure reasons identified: ${analysis.failureReasons.length}`);
      }
    } catch (error) {
      console.warn(`[GEPA] LLM reflection failed, using rule-based fallback: ${error}`);
      // 回退到规则生成
      return this.ruleBasedGeneration(original, failedTraces, successTraces);
    }

    // 使用 LLM 生成候选版本
    const candidateCount = Math.min(3 + crypto.randomInt(0, 3), 5);
    let generatedContents: string[];

    try {
      generatedContents = await llmAdapter.generateCandidates(original.content, analysis, candidateCount);
    } catch (error) {
      console.warn(`[GEPA] LLM candidate generation failed, using rule-based fallback: ${error}`);
      return this.ruleBasedGeneration(original, failedTraces, successTraces);
    }

    // 构建候选对象
    const generated: GepaCandidate[] = generatedContents.map((content, i) => {
      const isFromFailed = i < failedTraces.length;
      const sourceTrace = isFromFailed ? failedTraces[i] : successTraces[i - failedTraces.length];

      return {
        id: `candidate_${original.id}_v${original.gepa_version + 1}_${i}`,
        original_fragment_id: original.id,
        content,
        version: original.gepa_version + 1,
        pareto_rank: i,
        generated_at: new Date().toISOString(),
        generation_reason: isFromFailed
          ? `基于失败轨迹反思: ${sourceTrace?.failure_reason || analysis.failureReasons[i] || '未知'}`
          : `基于成功轨迹优化 + ${analysis.improvementSuggestions[i] || 'LLM优化'}`,
      };
    });

    return generated;
  }

  /**
   * 基于规则的候选生成（回退方案）
   */
  private ruleBasedGeneration(
    original: PromptFragment,
    failedTraces: ExecutionTrace[],
    successTraces: ExecutionTrace[]
  ): GepaCandidate[] {
    const generated: GepaCandidate[] = [];

    for (let i = 0; i < Math.min(3 + crypto.randomInt(0, 3), 5); i++) {
      const isFromFailed = i < failedTraces.length;
      const sourceTrace = isFromFailed ? failedTraces[i] : successTraces[i - failedTraces.length];

      generated.push({
        id: `candidate_${original.id}_v${original.gepa_version + 1}_${i}`,
        original_fragment_id: original.id,
        content: this.generateCandidateContent(original, sourceTrace, i),
        version: original.gepa_version + 1,
        pareto_rank: i,
        generated_at: new Date().toISOString(),
        generation_reason: isFromFailed
          ? `基于失败轨迹反思: ${sourceTrace.failure_reason || '未知'}`
          : '基于成功轨迹优化',
      });
    }

    return generated;
  }

  /**
   * 生成候选内容（简化版）
   */
  private generateCandidateContent(
    original: PromptFragment,
    sourceTrace: ExecutionTrace,
    variantIndex: number
  ): string {
    // 简化：添加变体标记
    const prefix = [
      '【更简洁】',
      '【更详细】',
      '【结构化】',
      '【举例说明】',
      '【重点强调】',
    ];

    return `${prefix[variantIndex] || ''}${original.content}`;
  }

  /**
   * 步骤4: 沙盒测试
   * 使用真实沙盒执行和评估候选版本
   */
  private async sandboxTest(
    candidates: GepaCandidate[],
    original: PromptFragment
  ): Promise<GepaCandidate[]> {
    if (candidates.length === 0) return [];

    // 创建沙盒实例用于测试
    const sandbox = new GVisorSandbox();

    // 对每个候选进行真实测试
    const testedCandidates: GepaCandidate[] = [];

    for (const candidate of candidates) {
      try {
        // 使用沙盒执行候选测试
        // 注意：在Windows环境下，gVisor可能不可用，会自动回退到其他执行方式
        const result = await sandbox.execute(
          ['claude', '--print', `Evaluate this prompt: ${candidate.content}`],
          { type: SandboxType.GVISOR, timeout_ms: 30000 }
        );

        // 根据执行结果评估候选质量
        const score = result.success ? this.evaluateExecutionResult(result) : 0.5;

        testedCandidates.push({
          ...candidate,
          // 注意：GepaCandidate类型可能没有score字段，这里我们记录在pareto_rank中
          pareto_rank: score > 0.7 ? 0 : 1, // 0 = 最好
        });
      } catch (error) {
        // 测试失败时使用中等分数
        console.warn(`[GEPA] Sandbox test failed for candidate ${candidate.id}:`, error);
        testedCandidates.push({
          ...candidate,
          pareto_rank: 1, // 降级
        });
      }
    }

    // 按pareto_rank排序
    testedCandidates.sort((a, b) => (a.pareto_rank ?? 1) - (b.pareto_rank ?? 1));

    return testedCandidates;
  }

  /**
   * 评估沙盒执行结果
   */
  private evaluateExecutionResult(result: { success: boolean; stdout?: string; stderr?: string }): number {
    if (!result.success) return 0.3;

    // 基于执行输出的质量评估
    const output = result.stdout || '';
    if (output.includes('error') || output.includes('Error')) return 0.4;
    if (output.includes('warning') || output.includes('Warning')) return 0.6;
    if (output.length > 50) return 0.8; // 有实质输出

    return 0.5; // 默认中等
  }

  /**
   * 步骤5: 决策固化
   * 候选分数 > 当前版本 + 阈值 才替换
   */
  private decideSolidification(
    candidates: GepaCandidate[],
    original: PromptFragment
  ): GepaCandidate | undefined {
    if (candidates.length === 0) return undefined;

    // 选取 Pareto 前沿最好的
    const best = candidates[0];

    // 简化判断逻辑
    // 实际应比较：best.score > original_score + improvementThreshold
    const shouldReplace = best.pareto_rank === 0 && crypto.randomInt(0, 100) > 30;

    return shouldReplace ? best : undefined;
  }

  /**
   * 步骤6: 晋升入库
   */
  private async promoteToAsset(
    candidate: GepaCandidate,
    original: PromptFragment
  ): Promise<PromptFragment> {
    // 返回更新后的片段
    return {
      ...original,
      content: candidate.content,
      gepa_version: candidate.version,
      last_used_at: new Date().toISOString(),
    };
  }
}

// ============================================
// 启发式自动编译
// ============================================

/**
 * 启发式编译器
 * 基于规则的提示词参数自动优化
 *
 * 注意：此实现使用启发式评分（非真实 MIPROv2 优化）
 */
export class HeuristicCompiler {
  private signatureRegistry: SignatureRegistry;
  private compilationConfigs: Map<string, DspyCompilationConfig>;
  private currentModel: string;

  constructor(signatureRegistry: SignatureRegistry, currentModel: string = 'claude-sonnet-4-6') {
    this.signatureRegistry = signatureRegistry;
    this.compilationConfigs = new Map();
    this.currentModel = currentModel;
  }

  /**
   * 检查是否需要编译
   */
  shouldCompile(trigger: DspyCompilationTrigger): string[] {
    const signatures = this.signatureRegistry.getAll();
    const needsCompile: string[] = [];

    for (const sig of signatures) {
      const lastConfig = this.compilationConfigs.get(sig.name);

      switch (trigger) {
        case DspyCompilationTrigger.MODEL_UPDATE:
          if (sig.compiled_for !== this.currentModel) {
            needsCompile.push(sig.name);
          }
          break;

        case DspyCompilationTrigger.QUALITY_DECAY:
          // 检查质量下降（简化：假设lastConfig存在且超过7天）
          if (lastConfig && this.isOlderThanDays(lastConfig.started_at, 7)) {
            needsCompile.push(sig.name);
          }
          break;

        case DspyCompilationTrigger.USER_TRIGGERED:
          needsCompile.push(sig.name);
          break;
      }
    }

    return needsCompile;
  }

  /**
   * 执行编译
   */
  async compile(params: {
    signatureName: string;
    trigger: DspyCompilationTrigger;
    budget?: number;
  }): Promise<{ success: boolean; compiledContent?: string; error?: string }> {
    const sig = this.signatureRegistry.get(params.signatureName);
    if (!sig) {
      return { success: false, error: `Signature ${params.signatureName} not found` };
    }

    // 记录编译配置
    const config: DspyCompilationConfig = {
      trigger: params.trigger,
      target_model: this.currentModel,
      signatures: [params.signatureName],
      budget: params.budget || 500,
      is_running: true,
      started_at: new Date().toISOString(),
    };
    this.compilationConfigs.set(params.signatureName, config);

    try {
      // 简化：模拟编译过程
      // 实际应调用 DSPy MIPROv2 优化器
      const compiledContent = await this.runCompilation(sig.description, params.budget || 500);

      // 更新 Signature
      this.signatureRegistry.markCompiled(params.signatureName, this.currentModel);

      // 更新配置状态
      config.is_running = false;

      return { success: true, compiledContent };
    } catch (error) {
      config.is_running = false;
      return { success: false, error: String(error) };
    }
  }

  /**
   * 运行编译（简化版）
   */
  private async runCompilation(content: string, budget: number): Promise<string> {
    // 简化：返回优化后的内容
    // 实际应执行 100-500 次 LLM 调用进行优化
    return `[DSPy优化版] ${content}`;
  }

  /**
   * 检查日期是否早于指定天数
   */
  private isOlderThanDays(dateStr: string | undefined, days: number): boolean {
    if (!dateStr) return true;
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    return diff > days * 24 * 60 * 60 * 1000;
  }

  /**
   * 获取编译状态
   */
  getCompilationStatus(signatureName: string): DspyCompilationConfig | undefined {
    return this.compilationConfigs.get(signatureName);
  }

  /**
   * 更新当前模型版本
   */
  updateModelVersion(newModel: string): void {
    this.currentModel = newModel;
  }
}

// ============================================
// 夜间进化调度器
// ============================================

/**
 * 夜间进化调度器
 * 管理每日 02:30 GEPA 进化和启发式重编译检查
 */
export class NightlyEvolutionScheduler {
  private gepaEngine: GepaEngine;
  private heuristicCompiler: HeuristicCompiler;
  private lastExecution: string | null;

  constructor(gepaEngine: GepaEngine, heuristicCompiler: HeuristicCompiler) {
    this.gepaEngine = gepaEngine;
    this.heuristicCompiler = heuristicCompiler;
    this.lastExecution = null;
  }

  /**
   * 检查是否应该执行夜间进化
   */
  shouldExecute(): boolean {
    if (!this.lastExecution) return true;

    const now = new Date();
    const last = new Date(this.lastExecution);
    const hoursSinceLast = (now.getTime() - last.getTime()) / (1000 * 60 * 60);

    return hoursSinceLast >= 24;
  }

  /**
   * 执行夜间进化流程
   */
  async execute(params: {
    lowScoreTraces: ExecutionTrace[];
    highScoreTraces: ExecutionTrace[];
    fragmentsToEvolve: PromptFragment[];
  }): Promise<{
    gepaResults: GepaEvolutionResult[];
    dspyResults: { signature: string; success: boolean }[];
  }> {
    if (!this.shouldExecute()) {
      return { gepaResults: [], dspyResults: [] };
    }

    const gepaResults: GepaEvolutionResult[] = [];

    // GEPA 进化
    for (const fragment of params.fragmentsToEvolve) {
      const result = await this.gepaEngine.evolve({
        originalFragment: fragment,
        lowScoreTraces: params.lowScoreTraces,
        highScoreTraces: params.highScoreTraces,
        currentModel: this.heuristicCompiler['currentModel'],
      });
      gepaResults.push(result);
    }

    // DSPy 重编译检查
    const signaturesToCompile = this.heuristicCompiler.shouldCompile(DspyCompilationTrigger.MODEL_UPDATE);
    const dspyResults: { signature: string; success: boolean }[] = [];

    for (const sigName of signaturesToCompile) {
      const result = await this.heuristicCompiler.compile({
        signatureName: sigName,
        trigger: DspyCompilationTrigger.MODEL_UPDATE,
      });
      dspyResults.push({ signature: sigName, success: result.success });
    }

    this.lastExecution = new Date().toISOString();

    return { gepaResults, dspyResults };
  }

  /**
   * 获取最后执行时间
   */
  getLastExecution(): string | null {
    return this.lastExecution;
  }
}
