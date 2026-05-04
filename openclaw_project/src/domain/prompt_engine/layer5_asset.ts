/**
 * M09 Layer5 固化层
 * ================================================
 * 与九类数字资产体系对接
 * 职责：
 * 1. 提示词资产固化
 * 2. 四级分级体系
 * 3. 晋升与淘汰机制
 * ================================================
 */

import {
  PromptFragment,
  PromptAssetExtension,
  SolidificationTrigger as SolidificationTriggerInterface,
  SolidificationTriggerType,
  VerificationStatus,
  TaskType,
  AssetTier,
} from './types';

// ============================================
// 资产分级阈值
// ============================================

export const ASSET_TIER_THRESHOLDS: Record<AssetTier, { min: number; max: number }> = {
  'record': { min: 0, max: 29 },
  'general': { min: 30, max: 59 },
  'available': { min: 60, max: 74 },
  'premium': { min: 75, max: 89 },
  'core': { min: 90, max: 100 },
};

// ============================================
// 固化触发器
// ============================================

/**
 * 固化触发器
 * 检测三种固化触发条件
 */
export class SolidificationChecker {
  // 触发1: 连续高质量阈值
  private consecutiveHighQualityThreshold = 5;
  private consecutiveHighQualityMinScore = 0.85;

  // 触发2: 救场成功标记
  private saveTheDayScoreImprovement = 0.3;

  // 触发3: 跨场景复用阈值
  private crossScenarioMinCount = 3;

  /**
   * 检测触发1: 连续高质量
   */
  checkConsecutiveHighQuality(scoreHistory: number[]): boolean {
    if (scoreHistory.length < this.consecutiveHighQualityThreshold) {
      return false;
    }

    const recentScores = scoreHistory.slice(-this.consecutiveHighQualityThreshold);
    return recentScores.every(score => score >= this.consecutiveHighQualityMinScore);
  }

  /**
   * 检测触发2: 救场成功
   */
  checkSaveTheDay(
    previousScore: number,
    currentScore: number,
    previousAttempts: number
  ): boolean {
    return (
      previousAttempts >= 2 &&
      currentScore >= previousScore + this.saveTheDayScoreImprovement &&
      currentScore >= 0.7
    );
  }

  /**
   * 检测触发3: 跨场景复用
   */
  checkCrossScenarioReuse(
    scenarioCount: number,
    totalPositiveEffect: number
  ): boolean {
    return (
      scenarioCount >= this.crossScenarioMinCount &&
      totalPositiveEffect / scenarioCount >= 0.6
    );
  }

  /**
   * 综合检查所有触发条件
   */
  checkTriggers(params: {
    fragment: PromptFragment;
    previousScore?: number;
    currentScore?: number;
    previousAttempts?: number;
    scenarioTypes?: TaskType[];
    positiveEffectCount?: number;
  }): SolidificationTriggerInterface[] {
    const triggers: SolidificationTriggerInterface[] = [];

    // 触发1: 连续高质量
    if (this.checkConsecutiveHighQuality(params.fragment.quality_score_history)) {
      triggers.push({
        type: SolidificationTriggerType.CONSECUTIVE_HIGH_QUALITY,
        condition_description: `连续${this.consecutiveHighQualityThreshold}次质量分≥${this.consecutiveHighQualityMinScore}`,
        fragment_id: params.fragment.id,
        triggered_at: new Date().toISOString(),
        verification_status: VerificationStatus.PENDING,
      });
    }

    // 触发2: 救场成功
    if (
      params.previousScore !== undefined &&
      params.currentScore !== undefined &&
      params.previousAttempts !== undefined &&
      this.checkSaveTheDay(params.previousScore, params.currentScore, params.previousAttempts)
    ) {
      triggers.push({
        type: SolidificationTriggerType.SAVE_THE_DAY,
        condition_description: `第${params.previousAttempts}次尝试成功，质量提升${(params.currentScore - params.previousScore).toFixed(2)}`,
        fragment_id: params.fragment.id,
        triggered_at: new Date().toISOString(),
        verification_status: VerificationStatus.PENDING,
      });
    }

    // 触发3: 跨场景复用
    if (
      params.scenarioTypes !== undefined &&
      params.positiveEffectCount !== undefined &&
      this.checkCrossScenarioReuse(
        new Set(params.scenarioTypes).size,
        params.positiveEffectCount
      )
    ) {
      triggers.push({
        type: SolidificationTriggerType.CROSS_SCENARIO_REUSE,
        condition_description: `在${new Set(params.scenarioTypes).size}种场景产生正向效果`,
        fragment_id: params.fragment.id,
        triggered_at: new Date().toISOString(),
        verification_status: VerificationStatus.PENDING,
      });
    }

    return triggers;
  }
}

// ============================================
// 等级分类器
// ============================================

/**
 * 等级分类器
 * 根据质量评分计算资产等级
 */
export class TierClassifier {
  /**
   * 计算资产等级
   */
  classify(score: number): AssetTier {
    if (score < 30) return AssetTier.RECORD;
    if (score < 60) return AssetTier.GENERAL;
    if (score < 75) return AssetTier.AVAILABLE;
    if (score < 90) return AssetTier.PREMIUM;
    return AssetTier.CORE;
  }

  /**
   * 获取等级名称
   */
  getTierName(tier: AssetTier): string {
    const names: Record<AssetTier, string> = {
      [AssetTier.RECORD]: '记录层',
      [AssetTier.GENERAL]: '一般',
      [AssetTier.AVAILABLE]: '可用',
      [AssetTier.PREMIUM]: '优质',
      [AssetTier.CORE]: '核心',
    };
    return names[tier];
  }

  /**
   * 获取淘汰规则
   */
  getEliminationRule(tier: AssetTier): string {
    const rules: Record<AssetTier, string> = {
      [AssetTier.RECORD]: '直接淘汰',
      [AssetTier.GENERAL]: '3连败<50%直接淘汰',
      [AssetTier.AVAILABLE]: '3连败后进入7天观察期',
      [AssetTier.PREMIUM]: '3连败后进入14天观察期',
      [AssetTier.CORE]: '不参与自动淘汰',
    };
    return rules[tier];
  }
}

// ============================================
// 提示词资产管理器
// ============================================

/**
 * 提示词资产管理器
 * Layer5 主入口，管理提示词资产的固化、分级、晋升
 */
export class PromptAssetManager {
  private trigger: SolidificationChecker;
  private classifier: TierClassifier;
  private assets: Map<string, PromptFragment & { extension: PromptAssetExtension }>;
  private promotionQueue: string[];
  private eliminationWatchlist: Map<string, { consecutiveFails: number; lastScore: number }>;

  constructor() {
    this.trigger = new SolidificationChecker();
    this.classifier = new TierClassifier();
    this.assets = new Map();
    this.promotionQueue = [];
    this.eliminationWatchlist = new Map();
  }

  /**
   * 注册提示词资产
   */
  registerAsset(fragment: PromptFragment, extension?: PromptAssetExtension): void {
    const asset = {
      ...fragment,
      extension: extension || this.createDefaultExtension(fragment),
    };
    this.assets.set(fragment.id, asset);
  }

  /**
   * 创建默认扩展
   */
  private createDefaultExtension(fragment: PromptFragment): PromptAssetExtension {
    return {
      prompt_type: fragment.type,
      task_types: [],
      quality_score_history: fragment.quality_score_history,
      gepa_version: fragment.gepa_version,
      avg_token_cost: 0,
    };
  }

  /**
   * 更新质量评分
   */
  updateQualityScore(fragmentId: string, score: number): void {
    const asset = this.assets.get(fragmentId);
    if (!asset) return;

    asset.quality_score_history.push(score);
    asset.extension.avg_token_cost =
      (asset.extension.avg_token_cost * (asset.extension.quality_score_history.length - 1) + score) /
      asset.extension.quality_score_history.length;

    // 检查固化触发
    const triggers = this.trigger.checkTriggers({
      fragment: asset,
    });

    for (const t of triggers) {
      if (t.verification_status === VerificationStatus.PENDING) {
        this.promotionQueue.push(fragmentId);
      }
    }

    // 更新淘汰观察列表
    this.updateEliminationWatchlist(fragmentId, score);
  }

  /**
   * 更新淘汰观察列表
   */
  private updateEliminationWatchlist(fragmentId: string, score: number): void {
    const tier = this.classifier.classify(score);

    // 核心资产不参与淘汰
    if (tier === AssetTier.CORE) return;

    const current = this.eliminationWatchlist.get(fragmentId) || {
      consecutiveFails: 0,
      lastScore: 0,
    };

    if (score < 0.5) {
      current.consecutiveFails++;
      current.lastScore = score;
    } else {
      current.consecutiveFails = 0;
      current.lastScore = score;
    }

    this.eliminationWatchlist.set(fragmentId, current);
  }

  /**
   * 检查是否应该淘汰
   */
  shouldEliminate(fragmentId: string): boolean {
    const asset = this.assets.get(fragmentId);
    if (!asset) return false;

    const tier = this.classifier.classify(asset.extension.quality_score_history.at(-1) || 0);
    const watch = this.eliminationWatchlist.get(fragmentId);

    if (!watch) return false;

    // 一般资产: 3连败<50%直接淘汰
    if (tier === AssetTier.GENERAL) {
      return watch.consecutiveFails >= 3 && watch.lastScore < 0.5;
    }

    // 可用/优质: 3连败后进入观察期（这里简化处理为暂缓淘汰）
    if (tier === AssetTier.AVAILABLE || tier === AssetTier.PREMIUM) {
      return watch.consecutiveFails >= 5; // 更严格的淘汰条件
    }

    return false;
  }

  /**
   * 获取资产
   */
  getAsset(fragmentId: string): (PromptFragment & { extension: PromptAssetExtension }) | undefined {
    return this.assets.get(fragmentId);
  }

  /**
   * 获取所有资产
   */
  getAllAssets(): (PromptFragment & { extension: PromptAssetExtension })[] {
    return Array.from(this.assets.values());
  }

  /**
   * 获取晋升队列
   */
  getPromotionQueue(): string[] {
    return [...this.promotionQueue];
  }

  /**
   * 处理晋升
   */
  processPromotion(fragmentId: string): boolean {
    const index = this.promotionQueue.indexOf(fragmentId);
    if (index === -1) return false;

    this.promotionQueue.splice(index, 1);

    const asset = this.assets.get(fragmentId);
    if (!asset) return false;

    // 更新 GEPA 版本
    asset.gepa_version++;
    asset.last_used_at = new Date().toISOString();

    return true;
  }

  /**
   * 获取资产报告
   */
  getAssetReport(): {
    totalAssets: number;
    byTier: Record<AssetTier, number>;
    promotionQueueSize: number;
    watchlistSize: number;
    averageQuality: number;
  } {
    const assets = this.getAllAssets();
    const byTier: Record<AssetTier, number> = {
      [AssetTier.RECORD]: 0,
      [AssetTier.GENERAL]: 0,
      [AssetTier.AVAILABLE]: 0,
      [AssetTier.PREMIUM]: 0,
      [AssetTier.CORE]: 0,
    };

    let totalQuality = 0;

    for (const asset of assets) {
      const latestScore = asset.quality_score_history.at(-1) || 0;
      const tier = this.classifier.classify(latestScore);
      byTier[tier]++;
      totalQuality += latestScore;
    }

    return {
      totalAssets: assets.length,
      byTier,
      promotionQueueSize: this.promotionQueue.length,
      watchlistSize: this.eliminationWatchlist.size,
      averageQuality: assets.length > 0 ? totalQuality / assets.length : 0,
    };
  }
}
