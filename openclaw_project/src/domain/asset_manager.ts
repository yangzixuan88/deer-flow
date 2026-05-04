/**
 * @module asset_manager
 * @description Implementation of the Phase 5 Wealth Layer (Asset Management).
 * Manages digital assets with ROI scoring and Five-Tier Classification.
 * @see docs/07_Digital_Asset_System.md
 */

export type AssetCategory =
  | 'search'
  | 'task'
  | 'tool'
  | 'cognitive'
  | 'network'
  | 'combined'
  | 'skill'
  | 'document'
  | 'metadata';

export type AssetStatus = 'active' | 'degraded' | 'archived' | 'retired';

export type AssetTier = 'record' | 'general' | 'available' | 'premium' | 'core';

/**
 * 资产淘汰状态（快速淘汰机制）
 */
export type EliminationStatus =
  | 'normal'           // 正常状态
  | 'observation'      // 观察期
  | 'eliminated'       // 已淘汰
  | 'whitelist_3month'; // 3个月无条件使用权

export interface DigitalAsset {
  id: string;
  name: string;
  category: AssetCategory;
  description: string;
  status: AssetStatus;
  tier: AssetTier;  // 五级分级

  // Scoring Metrics - Five-Dimensional Scoring Formula
  // S_total = S_f * 0.25 + S_s * 0.30 + S_t * 0.20 + S_c * 0.15 + S_u * 0.10
  metrics: {
    // S_f (Frequency): Usage frequency factor - 25% weight
    usageCount: number;
    // S_s (Success Rate): Task success rate - 30% weight
    successRate: number; // 0-1
    // S_t (Timeliness): How recent/fresh the asset is - 20% weight
    lastUsedDate: string; // ISO8601
    // S_c (Coverage): Scene/scenario coverage breadth - 15% weight
    coverageScore: number; // 0-1, how many use cases this asset covers
    // S_u (Uniqueness): Solution uniqueness factor - 10% weight
    uniquenessScore: number; // 0-1, how unique/distinctive is this solution
  };

  // 快速淘汰机制字段
  consecutive_failures: number;  // 连续失败次数
  elimination_status: EliminationStatus;
  observation_end_date?: string; // 观察期结束日期
  whitelist_end_date?: string;   // 白名单到期日期

  qualityScore: number;
  metadata: Record<string, any>;
  isWhiteListed: boolean; // Unique solution protection (3-month whitelist)
}

/**
 * 五级资产分级定义
 * Reference: docs/07_Digital_Asset_System.md §2
 */
export const ASSET_TIER_THRESHOLDS = {
  record: { min: 0, max: 30, name: 'record', nameCN: '记录层' },
  general: { min: 30, max: 60, name: 'general', nameCN: '一般' },
  available: { min: 60, max: 75, name: 'available', nameCN: '可用' },
  premium: { min: 75, max: 90, name: 'premium', nameCN: '优质' },
  core: { min: 90, max: 100, name: 'core', nameCN: '核心' }
} as const;

/**
 * Phase 5: Wealth Layer - Digital Asset Manager
 * Implements Five-Tier Classification and Quick Elimination Mechanism
 */
export class AssetManager {
  private readonly PROMOTION_QUALITY_THRESHOLD = 0.85;
  private readonly PROMOTION_USAGE_THRESHOLD = 3;
  private readonly DEGRADATION_INACTIVE_DAYS = 30;
  private readonly OBSERVATION_PERIOD_DAYS = 7;   // 可用资产观察期
  private readonly OBSERVATION_PERIOD_PREMIUM_DAYS = 14; // 优质资产观察期
  private readonly ELIMINATION_SUCCESS_RATE = 0.5; // 50%成功率阈值

  constructor() {}

  // =========================================================================
  // 五级分级逻辑
  // Reference: docs/07_Digital_Asset_System.md §2
  // =========================================================================

  /**
   * 根据质量评分计算资产等级
   * 记录层(<30), 一般(30-59), 可用(60-74), 优质(75-89), 核心(≥90)
   */
  public calculateTier(qualityScore: number): AssetTier {
    const score = qualityScore * 100; // 转换为百分制
    if (score < 30) return 'record';
    if (score < 60) return 'general';
    if (score < 75) return 'available';
    if (score < 90) return 'premium';
    return 'core';
  }

  /**
   * 获取等级名称（中文）
   */
  public getTierNameCN(tier: AssetTier): string {
    return ASSET_TIER_THRESHOLDS[tier]?.nameCN || '未知';
  }

  /**
   * 五维评分公式计算
   * S_total = S_f * 0.25 + S_s * 0.30 + S_t * 0.20 + S_c * 0.15 + S_u * 0.10
   */
  public calculateQuality(asset: DigitalAsset): number {
    const { usageCount, successRate, lastUsedDate, coverageScore, uniquenessScore } = asset.metrics;

    // S_f: Frequency Factor - capped at 1.0 for high usage (25% weight)
    const S_f = Math.min(usageCount / 10, 1.0);

    // S_s: Success Rate (30% weight)
    const S_s = successRate;

    // S_t: Timeliness Factor - calculated from lastUsedDate (20% weight)
    const S_t = this.calculateTimeliness(lastUsedDate);

    // S_c: Coverage Score (15% weight)
    const S_c = coverageScore;

    // S_u: Uniqueness Score (10% weight)
    const S_u = uniquenessScore;

    // Final weighted score
    const quality = (S_f * 0.25) + (S_s * 0.30) + (S_t * 0.20) + (S_c * 0.15) + (S_u * 0.10);

    return parseFloat(quality.toFixed(4));
  }

  /**
   * 计算时效性评分
   * 0-30天: 1.0-0.5, 30-60天: 0.5-0.1, 60+天: 0
   */
  private calculateTimeliness(lastUsedDate: string): number {
    const lastUsed = new Date(lastUsedDate);
    const daysSinceLastUse = (Date.now() - lastUsed.getTime()) / (1000 * 60 * 60 * 24);

    if (daysSinceLastUse <= 0) return 1.0;
    if (daysSinceLastUse <= 30) {
      return 1.0 - (daysSinceLastUse / 30) * 0.5;
    }
    if (daysSinceLastUse <= 60) {
      return 0.5 - ((daysSinceLastUse - 30) / 30) * 0.4;
    }
    return 0.0;
  }

  // =========================================================================
  // 快速淘汰机制
  // Reference: docs/07_Digital_Asset_System.md §4
  // =========================================================================

  /**
   * 执行快速淘汰检查
   * 一般资产: 3连败<50%直接淘汰
   * 可用/优质资产: 3连败后进入观察期
   * 核心资产: 不参与自动淘汰
   */
  public checkQuickElimination(asset: DigitalAsset): EliminationStatus {
    const tier = this.calculateTier(asset.qualityScore);

    // 核心资产不参与自动淘汰
    if (tier === 'core') {
      return 'normal';
    }

    // 记录层资产直接淘汰
    if (tier === 'record') {
      if (asset.consecutive_failures >= 3) {
        return 'eliminated';
      }
      return 'normal';
    }

    // 一般资产: 3连败<50%直接淘汰
    if (tier === 'general') {
      if (asset.consecutive_failures >= 3 && asset.metrics.successRate < this.ELIMINATION_SUCCESS_RATE) {
        return 'eliminated';
      }
      return 'normal';
    }

    // 可用/优质资产: 3连败后进入观察期
    if (tier === 'available' || tier === 'premium') {
      if (asset.consecutive_failures >= 3) {
        if (asset.elimination_status === 'observation') {
          // 已在观察期，检查是否到期
          if (asset.observation_end_date) {
            const endDate = new Date(asset.observation_end_date);
            if (Date.now() >= endDate.getTime()) {
              // 观察期结束，若无替代品则进入3个月白名单
              return 'whitelist_3month';
            }
          }
          return 'observation';
        }
        // 首次进入观察期
        return 'observation';
      }
      return 'normal';
    }

    return 'normal';
  }

  /**
   * 更新资产淘汰状态
   */
  public updateEliminationStatus(asset: DigitalAsset): DigitalAsset {
    const newStatus = this.checkQuickElimination(asset);
    const updated = { ...asset, elimination_status: newStatus };

    // 设置观察期
    if (newStatus === 'observation') {
      const periodDays = asset.tier === 'premium'
        ? this.OBSERVATION_PERIOD_PREMIUM_DAYS
        : this.OBSERVATION_PERIOD_DAYS;
      const endDate = new Date();
      endDate.setDate(endDate.getDate() + periodDays);
      updated.observation_end_date = endDate.toISOString();
    }

    // 设置3个月白名单
    if (newStatus === 'whitelist_3month') {
      const endDate = new Date();
      endDate.setMonth(endDate.getMonth() + 3);
      updated.whitelist_end_date = endDate.toISOString();
      updated.status = 'archived'; // 归档但保留
    }

    // 已淘汰
    if (newStatus === 'eliminated') {
      updated.status = 'retired';
    }

    return updated;
  }

  /**
   * 记录资产使用结果（成功/失败）
   */
  public recordUsageResult(asset: DigitalAsset, success: boolean): DigitalAsset {
    const updated = { ...asset };

    if (success) {
      updated.consecutive_failures = 0;
    } else {
      updated.consecutive_failures = (updated.consecutive_failures || 0) + 1;
    }

    // 更新使用统计
    updated.metrics.usageCount = (updated.metrics.usageCount || 0) + 1;
    updated.metrics.lastUsedDate = new Date().toISOString();

    // 重新计算质量
    updated.qualityScore = this.calculateQuality(updated);

    // 重新计算等级
    updated.tier = this.calculateTier(updated.qualityScore);

    // 检查淘汰状态
    return this.updateEliminationStatus(updated);
  }

  // =========================================================================
  // 晋升/降级逻辑
  // =========================================================================

  /**
   * 晋升检查：执行≥3次 + 成功率≥80%
   */
  public checkPromotion(asset: DigitalAsset): boolean {
    return asset.metrics.usageCount >= 3 && asset.metrics.successRate >= 0.8;
  }

  /**
   * 评估资产生命周期状态
   */
  public evaluateAssetLifecycle(asset: DigitalAsset): AssetStatus {
    const quality = this.calculateQuality(asset);
    const lastUsed = new Date(asset.metrics.lastUsedDate);
    const daysSinceLastUse = (Date.now() - lastUsed.getTime()) / (1000 * 60 * 60 * 24);

    // 1. 晋升准则: 3次成功使用 + Quality > 0.85 -> 激活
    if (asset.metrics.usageCount >= this.PROMOTION_USAGE_THRESHOLD && quality > this.PROMOTION_QUALITY_THRESHOLD) {
      return 'active';
    }

    // 2. 淘汰/降级准则: 30天未使用 -> 降级
    if (daysSinceLastUse > this.DEGRADATION_INACTIVE_DAYS) {
      return 'degraded';
    }

    // 3. 快速淘汰检查
    const elimStatus = this.checkQuickElimination(asset);
    if (elimStatus === 'eliminated') {
      return 'retired';
    }

    return asset.status;
  }

  /**
   * 计算Token节省ROI
   */
  public calculateTokenSavingROI(asset: DigitalAsset): number {
    return asset.qualityScore * 0.72;
  }

  /**
   * 获取资产完整报告
   */
  public getAssetReport(asset: DigitalAsset): {
    qualityScore: number;
    tier: AssetTier;
    tierNameCN: string;
    eliminationStatus: EliminationStatus;
    isHealthy: boolean;
    recommendations: string[];
  } {
    const quality = this.calculateQuality(asset);
    const tier = this.calculateTier(quality);
    const elimStatus = this.checkQuickElimination(asset);

    const recommendations: string[] = [];

    if (tier === 'record') {
      recommendations.push('资产评分过低，建议淘汰');
    }
    if (asset.consecutive_failures >= 2) {
      recommendations.push(`连续失败${asset.consecutive_failures}次，注意监控`);
    }
    if (elimStatus === 'observation') {
      recommendations.push('资产处于观察期，需要替代品或确认');
    }
    if (elimStatus === 'whitelist_3month') {
      recommendations.push('资产获得3个月无条件使用权');
    }

    return {
      qualityScore: quality,
      tier,
      tierNameCN: this.getTierNameCN(tier),
      eliminationStatus: elimStatus,
      isHealthy: elimStatus === 'normal' && tier !== 'record',
      recommendations
    };
  }
}
