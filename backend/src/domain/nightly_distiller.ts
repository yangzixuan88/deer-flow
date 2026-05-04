/**
 * @file nightly_distiller.ts
 * @description Implementation of the Nightly Distiller (Action 019).
 * Performs GEPA (Generative Experience Patching Architecture) reflection on trace logs.
 * Triggers at 02:00 to convert Intent-Action pairs into L3 assets.
 * Reference: docs/08_Learning_System.md - Six-Stage Nightly Review
 */

import { PostToolUseData, HookContext } from './hooks';
import { EvolutionPatch } from './optimizer';

// =============================================================================
// 完整经验包 JSONL 格式 (Reference: docs/08_Learning_System.md §2.2)
// =============================================================================

export interface ExperiencePackage {
  id: string;                    // "exp-20260407-001"
  timestamp: string;             // "2026-04-07T14:32:00Z"
  session_id: string;             // session UUID
  task_goal: string;             // 任务目标描述
  category: string;               // task/search/workflow/aal
  model_used: string;             // 模型标识
  tool_calls: ToolCall[];         // 工具调用序列
  total_tokens: number;           // 总token消耗
  total_duration_ms: number;      // 总耗时
  result_quality: number;          // 0-1质量评分
  reusable_patterns: ReusablePattern[];  // 可复用模式
  failure_info: FailureInfo | null;      // 失败信息
  search_triggers: string[];       // 搜索触发词
  asset_hits: string[];           // 命中的资产ID
}

export interface ToolCall {
  tool: string;                  // 工具名
  input: string;                 // 输入摘要
  output_summary: string;         // 输出摘要
  success: boolean;              // 是否成功
  duration_ms: number;            // 耗时
}

export interface ReusablePattern {
  pattern: string;               // 模式标识
  description: string;           // 模式描述
  confidence: number;             // 置信度
}

export interface FailureInfo {
  error: string;                 // 错误描述
  step: string;                  // 失败步骤
  recovery: string;               // 恢复方式
}

// =============================================================================
// 六阶段夜间复盘输出结构
// =============================================================================

export interface NightlyReviewReport {
  date: string;
  stage1_summary: Stage1AggregateStats;
  stage2_bottlenecks: Stage2Bottlenecks;
  stage3_extractions: Stage3PathExtractions;
  stage4_assets: Stage4AssetChanges;
  stage5_config_updates: Stage5ConfigUpdates;
  stage6_report: Stage6DailyReport;
}

export interface Stage1AggregateStats {
  total_tasks: number;
  success_count: number;
  failure_count: number;
  success_rate: number;
  total_tokens: number;
  total_duration_ms: number;
  model_distribution: Record<string, number>;
  tool_usage_stats: Record<string, number>;
}

export interface Stage2Bottlenecks {
  slowest_tasks: Array<{ task: string; duration_ms: number }>;
  most_failed_tools: Array<{ tool: string; failure_count: number }>;
  highest_token_steps: Array<{ step: string; tokens: number }>;
  redundant_searches: string[];
  improvement_priorities: Array<{ item: string; priority: 'high' | 'medium' | 'low' }>;
}

export interface Stage3PathExtractions {
  optimal_paths: Array<{
    task: string;
    tools: string[];
    success_rate: number;
    avg_duration_ms: number;
  }>;
  candidates_captured: string[];   // CAPTURED候选
  candidates_derived: string[];    // DERIVED候选
  candidates_fix: string[];       // FIX候选
}

export interface Stage4AssetChanges {
  promotions: Array<{ asset_id: string; from_tier: string; to_tier: string }>;
  demotions: Array<{ asset_id: string; from_tier: string; to_tier: string }>;
  new_candidates: string[];
  fixed_assets: string[];
}

export interface Stage5ConfigUpdates {
  low_risk_changes: Array<{ config: string; old_value: any; new_value: any }>;
  high_risk_changes: Array<{ config: string; old_value: any; new_value: any; requires_approval: boolean }>;
}

export interface Stage6DailyReport {
  report_date: string;
  execution_summary: {
    total_tasks: number;
    success_rate: number;
    token_consumed: number;
    total_duration_ms: number;
  };
  asset_dynamics: {
    new_candidates: number;
    promotions: number;
    fixes: number;
    tier_distribution: Record<string, number>;
  };
  bottlenecks: string[];
  auto_adjustments: string[];
  pending_approvals: string[];
}

// =============================================================================
// Evolution Operation Types (D-018 & OpenSpace State Machine)
// =============================================================================

export enum EvolutionOperation {
  CAPTURED = 'CAPTURED',   // New skill extraction
  DERIVED = 'DERIVED',      // Enhancement of existing asset
  FIX = 'FIX'               // Repair degraded asset
}

export interface GEPAExperience {
  intent: string;
  action_path: string[];
  success: boolean;
  qualityScore: number;
  optimizedRule?: string; // The "Meta-Rule" generated via reflection
  date: string;
  evolutionType?: EvolutionOperation; // CAPTURED, DERIVED, or FIX
  sourceAssetId?: string; // For DERIVED/FIX operations, the source asset
}

// =============================================================================
// 六阶段夜间复盘引擎 (Nightly Distiller)
// Reference: docs/08_Learning_System.md §3
// =============================================================================

export class NightlyDistiller {
  private readonly TRIGGER_HOUR = 2; // 02:00 AM

  constructor() {}

  /**
   * Check if it's the dreaming time (02:00 AM).
   */
  public isDreamingTime(): boolean {
    const currentHour = new Date().getHours();
    return currentHour === this.TRIGGER_HOUR;
  }

  // ===========================================================================
  // 阶段1: 聚合统计
  // 读取当日所有JSONL经验包，统计任务总数·成功率·总token·总耗时·模型分布
  // ===========================================================================
  public stage1_aggregateStats(experiencePackages: ExperiencePackage[]): Stage1AggregateStats {
    console.log(`[NightlyDistiller] Stage 1: Aggregating statistics from ${experiencePackages.length} packages`);

    const stats: Stage1AggregateStats = {
      total_tasks: experiencePackages.length,
      success_count: 0,
      failure_count: 0,
      success_rate: 0,
      total_tokens: 0,
      total_duration_ms: 0,
      model_distribution: {},
      tool_usage_stats: {}
    };

    for (const pkg of experiencePackages) {
      if (pkg.result_quality >= 0.6) {
        stats.success_count++;
      } else {
        stats.failure_count++;
      }
      stats.total_tokens += pkg.total_tokens;
      stats.total_duration_ms += pkg.total_duration_ms;

      // 模型分布
      stats.model_distribution[pkg.model_used] = (stats.model_distribution[pkg.model_used] || 0) + 1;

      // 工具使用统计
      for (const tc of pkg.tool_calls) {
        stats.tool_usage_stats[tc.tool] = (stats.tool_usage_stats[tc.tool] || 0) + 1;
      }
    }

    stats.success_rate = stats.total_tasks > 0 ? stats.success_count / stats.total_tasks : 0;
    return stats;
  }

  // ===========================================================================
  // 阶段2: 瓶颈识别
  // 找出耗时最长的任务、失败次数最多的工具、token消耗最大的步骤
  // ===========================================================================
  public stage2_identifyBottlenecks(experiencePackages: ExperiencePackage[]): Stage2Bottlenecks {
    console.log(`[NightlyDistiller] Stage 2: Identifying bottlenecks`);

    const bottlenecks: Stage2Bottlenecks = {
      slowest_tasks: [],
      most_failed_tools: [],
      highest_token_steps: [],
      redundant_searches: [],
      improvement_priorities: []
    };

    // 找出耗时最长的任务
    const sortedByDuration = [...experiencePackages]
      .sort((a, b) => b.total_duration_ms - a.total_duration_ms)
      .slice(0, 3);
    bottlenecks.slowest_tasks = sortedByDuration.map(t => ({
      task: t.task_goal,
      duration_ms: t.total_duration_ms
    }));

    // 统计工具失败次数
    const toolFailures: Record<string, number> = {};
    for (const pkg of experiencePackages) {
      for (const tc of pkg.tool_calls) {
        if (!tc.success) {
          toolFailures[tc.tool] = (toolFailures[tc.tool] || 0) + 1;
        }
      }
    }
    bottlenecks.most_failed_tools = Object.entries(toolFailures)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([tool, count]) => ({ tool, failure_count: count }));

    // 识别重复搜索
    const searchCounts: Record<string, number> = {};
    for (const pkg of experiencePackages) {
      for (const trigger of pkg.search_triggers) {
        searchCounts[trigger] = (searchCounts[trigger] || 0) + 1;
      }
    }
    bottlenecks.redundant_searches = Object.entries(searchCounts)
      .filter(([_, count]) => count > 3)
      .map(([trigger]) => trigger);

    // 改进优先级
    if (bottlenecks.slowest_tasks.length > 0) {
      bottlenecks.improvement_priorities.push({
        item: `优化"${bottlenecks.slowest_tasks[0].task}"流程（耗时${bottlenecks.slowest_tasks[0].duration_ms}ms）`,
        priority: 'high'
      });
    }
    if (bottlenecks.most_failed_tools.length > 0) {
      bottlenecks.improvement_priorities.push({
        item: `工具${bottlenecks.most_failed_tools[0].tool}失败率过高（${bottlenecks.most_failed_tools[0].failure_count}次）`,
        priority: 'medium'
      });
    }

    return bottlenecks;
  }

  // ===========================================================================
  // 阶段3: 路径萃取
  // 从成功任务中提取最优执行路径，标注CAPTURED/DERIVED/FIX候选
  // ===========================================================================
  public stage3_extractPaths(
    experiencePackages: ExperiencePackage[],
    existingAssets: GEPAExperience[]
  ): Stage3PathExtractions {
    console.log(`[NightlyDistiller] Stage 3: Extracting optimal paths`);

    const extractions: Stage3PathExtractions = {
      optimal_paths: [],
      candidates_captured: [],
      candidates_derived: [],
      candidates_fix: []
    };

    // 按task_goal分组提取最优路径
    const groupedByGoal: Record<string, ExperiencePackage[]> = {};
    for (const pkg of experiencePackages) {
      if (!groupedByGoal[pkg.task_goal]) {
        groupedByGoal[pkg.task_goal] = [];
      }
      groupedByGoal[pkg.task_goal].push(pkg);
    }

    for (const [task, pkgs] of Object.entries(groupedByGoal)) {
      const successPkgs = pkgs.filter(p => p.result_quality >= 0.8);
      if (successPkgs.length === 0) continue;

      // 找出最短成功路径
      let optimalPkg = successPkgs[0];
      for (const pkg of successPkgs) {
        if (pkg.tool_calls.length < optimalPkg.tool_calls.length) {
          optimalPkg = pkg;
        }
      }

      extractions.optimal_paths.push({
        task,
        tools: optimalPkg.tool_calls.map(t => t.tool),
        success_rate: successPkgs.length / pkgs.length,
        avg_duration_ms: pkgs.reduce((sum, p) => sum + p.total_duration_ms, 0) / pkgs.length
      });

      // 判断候选类型
      const hasExistingAsset = existingAssets.some(a =>
        a.intent.toLowerCase().includes(task.toLowerCase())
      );

      if (!hasExistingAsset && successPkgs.length >= 1) {
        extractions.candidates_captured.push(task);
      } else if (hasExistingAsset) {
        extractions.candidates_derived.push(task);
      }
    }

    // FIX候选：失败率高的资产
    const recentAssetQuality: Record<string, number[]> = {};
    for (const pkg of experiencePackages) {
      for (const hit of pkg.asset_hits) {
        if (!recentAssetQuality[hit]) {
          recentAssetQuality[hit] = [];
        }
        recentAssetQuality[hit].push(pkg.result_quality);
      }
    }
    for (const [assetId, qualities] of Object.entries(recentAssetQuality)) {
      const avgQuality = qualities.reduce((a, b) => a + b, 0) / qualities.length;
      if (avgQuality < 0.5) {
        extractions.candidates_fix.push(assetId);
      }
    }

    return extractions;
  }

  // ===========================================================================
  // 阶段4: 资产生成（核心阶段）
  // 执行晋升标准：执行≥3次 + 成功率≥80%
  // 执行CAPTURED/DERIVED/FIX操作
  // ===========================================================================
  public async stage4_generateAssets(
    experiencePackages: ExperiencePackage[],
    existingAssets: GEPAExperience[]
  ): Promise<Stage4AssetChanges> {
    console.log(`[NightlyDistiller] Stage 4: Generating assets`);

    const changes: Stage4AssetChanges = {
      promotions: [],
      demotions: [],
      new_candidates: [],
      fixed_assets: []
    };

    // 统计每个资产的使用情况
    const assetUsage: Record<string, { count: number; successCount: number }> = {};
    for (const pkg of experiencePackages) {
      for (const hit of pkg.asset_hits) {
        if (!assetUsage[hit]) {
          assetUsage[hit] = { count: 0, successCount: 0 };
        }
        assetUsage[hit].count++;
        if (pkg.result_quality >= 0.6) {
          assetUsage[hit].successCount++;
        }
      }
    }

    // 晋升检查：count >= 3 && successRate >= 80%
    for (const [assetId, usage] of Object.entries(assetUsage)) {
      const successRate = usage.successCount / usage.count;
      if (usage.count >= 3 && successRate >= 0.8) {
        changes.promotions.push({
          asset_id: assetId,
          from_tier: 'candidate',
          to_tier: 'active'
        });
      }
    }

    // CAPTURED: 从新候选创建资产（从experiencePackages提取新的asset_hits）
    const existingIntents = new Set(existingAssets.map(a => a.intent));
    for (const pkg of experiencePackages) {
      for (const hit of pkg.asset_hits) {
        if (!existingIntents.has(hit) && !changes.new_candidates.includes(hit)) {
          changes.new_candidates.push(hit);
        }
      }
    }

    // FIX: 修复降级资产
    const degradedAssets = existingAssets.filter(a => a.qualityScore < 0.6);
    for (const asset of degradedAssets) {
      const fixed = await this.fixDegradedAsset(asset, []);
      if (fixed.evolutionType === EvolutionOperation.FIX) {
        changes.fixed_assets.push(asset.intent);
      }
    }

    return changes;
  }

  // ===========================================================================
  // 阶段5: 配置自动更新
  // 低风险配置直接执行，高风险配置推送飞书等确认
  // ===========================================================================
  public stage5_updateConfig(bottlenecks: Stage2Bottlenecks): Stage5ConfigUpdates {
    console.log(`[NightlyDistiller] Stage 5: Updating configurations`);

    const updates: Stage5ConfigUpdates = {
      low_risk_changes: [],
      high_risk_changes: []
    };

    // 低风险：搜索引擎路由权重调整、工具调度优先级
    if (bottlenecks.improvement_priorities.some(p => p.priority === 'high')) {
      updates.low_risk_changes.push({
        config: 'search_engine.weight.ai_tech',
        old_value: 0.5,
        new_value: 0.6
      });
    }

    // 低风险：工具优先级调整
    if (bottlenecks.most_failed_tools.length > 0) {
      const failedTool = bottlenecks.most_failed_tools[0].tool;
      updates.low_risk_changes.push({
        config: `tool.priority.${failedTool}`,
        old_value: 5,
        new_value: 3 // 降低优先级
      });
    }

    // 高风险：安全白名单/灰名单变更、模型路由变更
    updates.high_risk_changes.push({
      config: 'model.route.primary',
      old_value: 'claude-opus-4',
      new_value: 'claude-sonnet-4-6',
      requires_approval: true
    });

    return updates;
  }

  // ===========================================================================
  // 阶段6: 日报生成 + 推送飞书
  // ===========================================================================
  public stage6_generateReport(
    stats: Stage1AggregateStats,
    bottlenecks: Stage2Bottlenecks,
    assetChanges: Stage4AssetChanges,
    configUpdates: Stage5ConfigUpdates
  ): Stage6DailyReport {
    console.log(`[NightlyDistiller] Stage 6: Generating daily report`);

    const report: Stage6DailyReport = {
      report_date: new Date().toISOString().split('T')[0],
      execution_summary: {
        total_tasks: stats.total_tasks,
        success_rate: Math.round(stats.success_rate * 10000) / 100,
        token_consumed: stats.total_tokens,
        total_duration_ms: stats.total_duration_ms
      },
      asset_dynamics: {
        new_candidates: assetChanges.new_candidates.length,
        promotions: assetChanges.promotions.length,
        fixes: assetChanges.fixed_assets.length,
        tier_distribution: {
          core: assetChanges.promotions.filter(p => p.to_tier === 'core').length,
          premium: 0,
          active: 0,
          candidate: assetChanges.new_candidates.length
        }
      },
      bottlenecks: bottlenecks.improvement_priorities.map(p => p.item),
      auto_adjustments: configUpdates.low_risk_changes.map(c => `${c.config}: ${c.old_value} → ${c.new_value}`),
      pending_approvals: configUpdates.high_risk_changes.map(c => `${c.config}: ${c.old_value} → ${c.new_value}`)
    };

    return report;
  }

  // ===========================================================================
  // 六阶段完整执行流程
  // ===========================================================================
  public async executeSixStageReview(
    experiencePackages: ExperiencePackage[],
    existingAssets: GEPAExperience[]
  ): Promise<NightlyReviewReport> {
    console.log(`[NightlyDistiller] Starting six-stage nightly review...`);

    // 阶段1: 聚合统计
    const stats = this.stage1_aggregateStats(experiencePackages);

    // 阶段2: 瓶颈识别
    const bottlenecks = this.stage2_identifyBottlenecks(experiencePackages);

    // 阶段3: 路径萃取
    const extractions = this.stage3_extractPaths(experiencePackages, existingAssets);

    // 阶段4: 资产生成
    const assetChanges = await this.stage4_generateAssets(experiencePackages, existingAssets);

    // 阶段5: 配置更新
    const configUpdates = this.stage5_updateConfig(bottlenecks);

    // 阶段6: 日报生成
    const report = this.stage6_generateReport(stats, bottlenecks, assetChanges, configUpdates);

    console.log(`[NightlyDistiller] Six-stage review complete. Report generated for ${report.report_date}`);

    return {
      date: report.report_date,
      stage1_summary: stats,
      stage2_bottlenecks: bottlenecks,
      stage3_extractions: extractions,
      stage4_assets: assetChanges,
      stage5_config_updates: configUpdates,
      stage6_report: report
    };
  }

  /**
   * Distills trace logs into GEPA Experiences.
   * Logic: Scan L1 trace logs -> Extract high-quality Intent-Action pairs -> Reflect.
   */
  public async distill(logs: PostToolUseData[], context: HookContext): Promise<GEPAExperience[]> {
    console.log(`[NightlyDistiller] Starting GEPA distillation for Session: ${context.sessionId}`);

    const experiences: GEPAExperience[] = [];

    // Group logs by intent (Simplified logic for demonstration)
    const groupedLogs = this.groupByIntent(logs);

    for (const [intent, traces] of Object.entries(groupedLogs)) {
      const successCount = traces.filter(t => t.success).length;
      const successRate = traces.length > 0 ? successCount / traces.length : 0;

      if (successRate >= 0.8) {
        const experience: GEPAExperience = {
          intent,
          action_path: traces.map(t => t.toolName),
          success: true,
          qualityScore: successRate,
          optimizedRule: this.generateOptimizedRule(intent, traces),
          date: new Date().toISOString()
        };
        experiences.push(experience);
        console.log(`[NightlyDistiller] Extracted Skill: "${intent}" | Quality: ${successRate}`);
      }
    }

    return experiences;
  }

  /**
   * GEPA Reflection Engine (Skeleton)
   * In a real system, this would call an LLM with DSPy or similar few-shot optimization.
   */
  private generateOptimizedRule(intent: string, traces: PostToolUseData[]): string {
    // Simulated reflection: Identifies the shortest path and best tools
    const tools = traces.map(t => t.toolName);
    return `For intent "${intent}", prioritize tools [${tools.join(', ')}] and bypass intermediate searches if data is cached.`;
  }

  private groupByIntent(logs: PostToolUseData[]): Record<string, PostToolUseData[]> {
    const groups: Record<string, PostToolUseData[]> = {};
    for (const log of logs) {
      const intent = log.intent || "Unknown";
      if (!groups[intent]) groups[intent] = [];
      groups[intent].push(log);
    }
    return groups;
  }

  /**
   * Promotes the distilled experiences to the SkillLibrary (L3 Asset).
   */
  public async promoteToSkillLibrary(experiences: GEPAExperience[]): Promise<void> {
    console.log(`[NightlyDistiller] Promoting ${experiences.length} skills to SkillLibrary (L3 Asset)...`);
    // Logic: Write to assets/cold_skills/ in JSON format with [ASSET_V1.0] finger-print
  }

  /**
   * DERIVED Evolution Operation (D-018)
   * Creates an enhanced version of an existing high-quality asset.
   */
  public async deriveEnhancedAsset(
    sourceAsset: GEPAExperience,
    enhancementTraces: PostToolUseData[]
  ): Promise<GEPAExperience> {
    console.log(`[NightlyDistiller] Creating DERIVED asset from: ${sourceAsset.intent}`);

    const enhancedTools = this.findOptimalToolSequence(enhancementTraces);
    const originalTools = sourceAsset.action_path;

    if (enhancedTools.length < originalTools.length) {
      const derivedExperience: GEPAExperience = {
        intent: `[DERIVED] ${sourceAsset.intent}`,
        action_path: enhancedTools,
        success: true,
        qualityScore: Math.min(sourceAsset.qualityScore * 1.2, 1.0),
        optimizedRule: this.generateOptimizedRule(sourceAsset.intent, enhancementTraces),
        date: new Date().toISOString(),
        evolutionType: EvolutionOperation.DERIVED,
        sourceAssetId: sourceAsset.intent
      };

      console.log(`[NightlyDistiller] DERIVED asset created: ${derivedExperience.intent}`);
      return derivedExperience;
    }

    return {
      ...sourceAsset,
      evolutionType: EvolutionOperation.DERIVED,
      date: new Date().toISOString()
    };
  }

  /**
   * FIX Evolution Operation (D-018)
   * Repairs/fixes a degraded asset to restore its quality.
   */
  public async fixDegradedAsset(
    degradedAsset: GEPAExperience,
    recentTraces: PostToolUseData[]
  ): Promise<GEPAExperience> {
    console.log(`[NightlyDistiller] FIX operation on degraded asset: ${degradedAsset.intent}`);

    const failurePatterns = recentTraces.filter(t => !t.success);
    const successPatterns = recentTraces.filter(t => t.success);

    if (failurePatterns.length === 0) {
      return {
        ...degradedAsset,
        qualityScore: Math.min(degradedAsset.qualityScore + 0.15, 0.85),
        evolutionType: EvolutionOperation.FIX,
        date: new Date().toISOString()
      };
    }

    const fixRule = this.generateFixRule(degradedAsset.intent, failurePatterns, successPatterns);

    return {
      intent: `[FIX] ${degradedAsset.intent.replace('[DERIVED] ', '')}`,
      action_path: degradedAsset.action_path,
      success: true,
      qualityScore: 0.75,
      optimizedRule: fixRule,
      date: new Date().toISOString(),
      evolutionType: EvolutionOperation.FIX,
      sourceAssetId: degradedAsset.intent
    };
  }

  private findOptimalToolSequence(traces: PostToolUseData[]): string[] {
    const successfulTraces = traces.filter(t => t.success);
    if (successfulTraces.length === 0) return [];

    let optimalPath: string[] = [];
    for (const trace of successfulTraces) {
      const path: string[] = Array.isArray(trace.action) ? trace.action : [trace.action || trace.toolName];
      if (optimalPath.length === 0 || path.length < optimalPath.length) {
        optimalPath = path;
      }
    }
    return optimalPath;
  }

  private generateFixRule(
    intent: string,
    failures: PostToolUseData[],
    successes: PostToolUseData[]
  ): string {
    const failureReasons = failures.map(f => f.error).filter(Boolean);
    const avoidTools = failures.map(f => f.toolName);

    return `FIX Rule for "${intent}": ` +
      `Avoid tools [${avoidTools.join(', ')}]. ` +
      `Failure patterns: ${failureReasons.slice(0, 3).join('; ')}. ` +
      `Use success pattern from ${successes.length} successful runs.`;
  }

  public async performOpenSpaceEvolution(
    logs: PostToolUseData[],
    existingAssets: GEPAExperience[]
  ): Promise<GEPAExperience[]> {
    console.log(`[NightlyDistiller] Starting OpenSpace Three-Operation Evolution...`);

    const allExperiences: GEPAExperience[] = [];

    const captured = await this.distill(logs, {
      taskId: 'opspace-evolution',
      sessionId: `session-${Date.now()}`,
      agentId: 'nightly-distiller',
      timestamp: new Date().toISOString(),
      metadata: {},
    });
    captured.forEach(exp => exp.evolutionType = EvolutionOperation.CAPTURED);
    allExperiences.push(...captured);

    const highQualityAssets = existingAssets.filter(a => a.qualityScore >= 0.8);
    for (const asset of highQualityAssets) {
      const relatedTraces = logs.filter(l => l.intent === asset.intent);
      if (relatedTraces.length > 0) {
        const derived = await this.deriveEnhancedAsset(asset, relatedTraces);
        allExperiences.push(derived);
      }
    }

    const degradedAssets = existingAssets.filter(a => a.qualityScore < 0.6);
    for (const asset of degradedAssets) {
      const relatedTraces = logs.filter(l => l.intent === asset.intent);
      if (relatedTraces.length > 0) {
        const fixed = await this.fixDegradedAsset(asset, relatedTraces);
        allExperiences.push(fixed);
      }
    }

    return allExperiences;
  }
}
