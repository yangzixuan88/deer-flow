/**
 * M07 数字资产管理单元测试
 * ================================================
 * 测试五级分级、五维评分、快速淘汰机制
 * ================================================
 */

import {
  AssetManager,
  DigitalAsset,
  AssetTier,
  AssetCategory,
  EliminationStatus,
  ASSET_TIER_THRESHOLDS,
} from './asset_manager';

describe('AssetManager 单元测试', () => {
  let assetManager: AssetManager;

  beforeEach(() => {
    assetManager = new AssetManager();
  });

  // 创建测试资产
  const createTestAsset = (overrides: Partial<DigitalAsset> = {}): DigitalAsset => ({
    id: 'test-asset-001',
    name: 'Test Asset',
    category: 'task' as AssetCategory,
    description: 'A test asset',
    status: 'active',
    tier: 'general',
    metrics: {
      usageCount: 5,
      successRate: 0.8,
      lastUsedDate: new Date().toISOString(),
      coverageScore: 0.7,
      uniquenessScore: 0.6,
    },
    consecutive_failures: 0,
    elimination_status: 'normal',
    qualityScore: 0.7,
    metadata: {},
    isWhiteListed: false,
    ...overrides,
  });

  // ============================================
  // 五级分级测试
  // ============================================
  describe('calculateTier - 五级分级', () => {
    it('should return record for quality < 0.30', () => {
      expect(assetManager.calculateTier(0.20)).toBe('record');
      expect(assetManager.calculateTier(0.29)).toBe('record');
      expect(assetManager.calculateTier(0.0)).toBe('record');
    });

    it('should return general for quality 0.30-0.59', () => {
      expect(assetManager.calculateTier(0.30)).toBe('general');
      expect(assetManager.calculateTier(0.45)).toBe('general');
      expect(assetManager.calculateTier(0.59)).toBe('general');
    });

    it('should return available for quality 0.60-0.74', () => {
      expect(assetManager.calculateTier(0.60)).toBe('available');
      expect(assetManager.calculateTier(0.70)).toBe('available');
      expect(assetManager.calculateTier(0.74)).toBe('available');
    });

    it('should return premium for quality 0.75-0.89', () => {
      expect(assetManager.calculateTier(0.75)).toBe('premium');
      expect(assetManager.calculateTier(0.85)).toBe('premium');
      expect(assetManager.calculateTier(0.89)).toBe('premium');
    });

    it('should return core for quality >= 0.90', () => {
      expect(assetManager.calculateTier(0.90)).toBe('core');
      expect(assetManager.calculateTier(0.95)).toBe('core');
      expect(assetManager.calculateTier(1.0)).toBe('core');
    });
  });

  describe('getTierNameCN - 等级中文名称', () => {
    it('should return correct Chinese names', () => {
      expect(assetManager.getTierNameCN('record')).toBe('记录层');
      expect(assetManager.getTierNameCN('general')).toBe('一般');
      expect(assetManager.getTierNameCN('available')).toBe('可用');
      expect(assetManager.getTierNameCN('premium')).toBe('优质');
      expect(assetManager.getTierNameCN('core')).toBe('核心');
    });

    it('should return 未知 for invalid tier', () => {
      expect(assetManager.getTierNameCN('invalid' as AssetTier)).toBe('未知');
    });
  });

  // ============================================
  // 五维评分测试
  // ============================================
  describe('calculateQuality - 五维评分', () => {
    it('should calculate quality with full weight = 1.0', () => {
      const asset = createTestAsset({
        metrics: {
          usageCount: 10, // S_f = min(10/10, 1) = 1
          successRate: 1.0, // S_s = 1
          lastUsedDate: new Date().toISOString(), // S_t = 1 (today)
          coverageScore: 1.0, // S_c = 1
          uniquenessScore: 1.0, // S_u = 1
        },
      });

      const quality = assetManager.calculateQuality(asset);

      // Expected: 1*0.25 + 1*0.30 + 1*0.20 + 1*0.15 + 1*0.10 = 1.0
      expect(quality).toBe(1.0);
    });

    it('should apply correct weights', () => {
      const asset = createTestAsset({
        metrics: {
          usageCount: 5, // S_f = 0.5
          successRate: 0.8, // S_s = 0.8
          lastUsedDate: new Date().toISOString(), // S_t = 1
          coverageScore: 0.5, // S_c = 0.5
          uniquenessScore: 0.5, // S_u = 0.5
        },
      });

      const quality = assetManager.calculateQuality(asset);

      // Expected: 0.5*0.25 + 0.8*0.30 + 1*0.20 + 0.5*0.15 + 0.5*0.10
      // = 0.125 + 0.24 + 0.20 + 0.075 + 0.05 = 0.69
      expect(quality).toBeCloseTo(0.69, 1);
    });

    it('should cap usage frequency at 1.0', () => {
      const asset10 = createTestAsset({
        metrics: { usageCount: 10, successRate: 0.8, lastUsedDate: new Date().toISOString(), coverageScore: 0.5, uniquenessScore: 0.5 },
      });
      const asset100 = createTestAsset({
        metrics: { usageCount: 100, successRate: 0.8, lastUsedDate: new Date().toISOString(), coverageScore: 0.5, uniquenessScore: 0.5 },
      });

      const quality10 = assetManager.calculateQuality(asset10);
      const quality100 = assetManager.calculateQuality(asset100);

      // 100 usage should cap at same as 10 usage (both S_f=1.0)
      expect(quality10).toBeCloseTo(quality100, 5);
    });
  });

  describe('Timeliness Calculation - 时效性评分', () => {
    it('should return 1.0 for today', () => {
      const asset = createTestAsset({
        metrics: {
          usageCount: 5,
          successRate: 0.8,
          lastUsedDate: new Date().toISOString(),
          coverageScore: 0.5,
          uniquenessScore: 0.5,
        },
      });

      const quality = assetManager.calculateQuality(asset);
      // Only timeliness differs, should be max
      expect(quality).toBeGreaterThan(0.5);
    });

    it('should return lower score for old assets', () => {
      const recentAsset = createTestAsset({
        metrics: {
          usageCount: 5,
          successRate: 0.8,
          lastUsedDate: new Date().toISOString(),
          coverageScore: 0.5,
          uniquenessScore: 0.5,
        },
      });

      const oldDate = new Date();
      oldDate.setDate(oldDate.getDate() - 45); // 45 days ago

      const oldAsset = createTestAsset({
        metrics: {
          usageCount: 5,
          successRate: 0.8,
          lastUsedDate: oldDate.toISOString(),
          coverageScore: 0.5,
          uniquenessScore: 0.5,
        },
      });

      const recentQuality = assetManager.calculateQuality(recentAsset);
      const oldQuality = assetManager.calculateQuality(oldAsset);

      expect(recentQuality).toBeGreaterThan(oldQuality);
    });
  });

  // ============================================
  // 快速淘汰机制测试
  // ============================================
  describe('checkQuickElimination - 快速淘汰', () => {
    it('should return normal for core tier assets', () => {
      const coreAsset = createTestAsset({
        qualityScore: 0.95,
        tier: 'core',
        consecutive_failures: 10,
      });

      expect(assetManager.checkQuickElimination(coreAsset)).toBe('normal');
    });

    it('should eliminate record tier with 3+ failures', () => {
      const recordAsset = createTestAsset({
        qualityScore: 0.20,
        tier: 'record',
        consecutive_failures: 3,
      });

      expect(assetManager.checkQuickElimination(recordAsset)).toBe('eliminated');
    });

    it('should not eliminate record tier with < 3 failures', () => {
      const recordAsset = createTestAsset({
        qualityScore: 0.20,
        tier: 'record',
        consecutive_failures: 2,
      });

      expect(assetManager.checkQuickElimination(recordAsset)).toBe('normal');
    });

    it('should eliminate general tier with 3 failures and low success rate', () => {
      const generalAsset = createTestAsset({
        qualityScore: 0.45,
        tier: 'general',
        consecutive_failures: 3,
        metrics: { ...createTestAsset().metrics, successRate: 0.4 },
      });

      expect(assetManager.checkQuickElimination(generalAsset)).toBe('eliminated');
    });

    it('should not eliminate general tier with 3 failures but high success rate', () => {
      const generalAsset = createTestAsset({
        qualityScore: 0.45,
        tier: 'general',
        consecutive_failures: 3,
        metrics: { ...createTestAsset().metrics, successRate: 0.6 },
      });

      expect(assetManager.checkQuickElimination(generalAsset)).toBe('normal');
    });

    it('should put available tier into observation on 3 failures', () => {
      const availableAsset = createTestAsset({
        qualityScore: 0.65,
        tier: 'available',
        consecutive_failures: 3,
        elimination_status: 'normal',
      });

      expect(assetManager.checkQuickElimination(availableAsset)).toBe('observation');
    });

    it('should put premium tier into observation on 3 failures', () => {
      const premiumAsset = createTestAsset({
        qualityScore: 0.80,
        tier: 'premium',
        consecutive_failures: 3,
        elimination_status: 'normal',
      });

      expect(assetManager.checkQuickElimination(premiumAsset)).toBe('observation');
    });
  });

  describe('updateEliminationStatus - 淘汰状态更新', () => {
    it('should set observation end date for available tier', () => {
      const availableAsset = createTestAsset({
        qualityScore: 0.65,
        tier: 'available',
        consecutive_failures: 3,
        elimination_status: 'normal',
      });

      const updated = assetManager.updateEliminationStatus(availableAsset);

      expect(updated.elimination_status).toBe('observation');
      expect(updated.observation_end_date).toBeDefined();
    });

    it('should set 7-day observation for available tier', () => {
      const availableAsset = createTestAsset({
        qualityScore: 0.65,
        tier: 'available',
        consecutive_failures: 3,
        elimination_status: 'normal',
      });

      const before = new Date();
      const updated = assetManager.updateEliminationStatus(availableAsset);
      const after = new Date();

      const endDate = new Date(updated.observation_end_date!);
      const daysDiff = (endDate.getTime() - before.getTime()) / (1000 * 60 * 60 * 24);

      expect(daysDiff).toBeGreaterThanOrEqual(7);
      expect(daysDiff).toBeLessThan(8);
    });

    it('should set 14-day observation for premium tier', () => {
      const premiumAsset = createTestAsset({
        qualityScore: 0.80,
        tier: 'premium',
        consecutive_failures: 3,
        elimination_status: 'normal',
      });

      const before = new Date();
      const updated = assetManager.updateEliminationStatus(premiumAsset);
      const after = new Date();

      const endDate = new Date(updated.observation_end_date!);
      const daysDiff = (endDate.getTime() - before.getTime()) / (1000 * 60 * 60 * 24);

      expect(daysDiff).toBeGreaterThanOrEqual(14);
      expect(daysDiff).toBeLessThan(15);
    });

    it('should set retired status when eliminated', () => {
      const recordAsset = createTestAsset({
        qualityScore: 0.20,
        tier: 'record',
        consecutive_failures: 3,
        status: 'active',
      });

      const updated = assetManager.updateEliminationStatus(recordAsset);

      expect(updated.elimination_status).toBe('eliminated');
      expect(updated.status).toBe('retired');
    });
  });

  // ============================================
  // 使用记录测试
  // ============================================
  describe('recordUsageResult - 使用记录', () => {
    it('should reset consecutive failures on success', () => {
      const asset = createTestAsset({ consecutive_failures: 5 });

      const updated = assetManager.recordUsageResult(asset, true);

      expect(updated.consecutive_failures).toBe(0);
    });

    it('should increment consecutive failures on failure', () => {
      const asset = createTestAsset({ consecutive_failures: 2 });

      const updated = assetManager.recordUsageResult(asset, false);

      expect(updated.consecutive_failures).toBe(3);
    });

    it('should update lastUsedDate on any usage', () => {
      const oldDate = new Date();
      oldDate.setDate(oldDate.getDate() - 10);

      const asset = createTestAsset({
        metrics: { ...createTestAsset().metrics, lastUsedDate: oldDate.toISOString() },
      });

      const updated = assetManager.recordUsageResult(asset, true);

      const updatedDate = new Date(updated.metrics.lastUsedDate);
      const diff = updatedDate.getTime() - oldDate.getTime();

      expect(diff).toBeGreaterThan(0); // Newer than old date
    });

    it('should increment usageCount', () => {
      const asset = createTestAsset({ metrics: { ...createTestAsset().metrics, usageCount: 5 } });

      const updated = assetManager.recordUsageResult(asset, true);

      expect(updated.metrics.usageCount).toBe(6);
    });

    it('should recalculate quality after usage', () => {
      const asset = createTestAsset({ qualityScore: 0.5 });

      const updated = assetManager.recordUsageResult(asset, true);

      // Quality should be recalculated
      expect(updated.qualityScore).toBeDefined();
      expect(typeof updated.qualityScore).toBe('number');
    });
  });

  // ============================================
  // 晋升/降级测试
  // ============================================
  describe('checkPromotion - 晋升检查', () => {
    it('should return true when usage >= 3 and success rate >= 0.8', () => {
      const asset = createTestAsset({
        metrics: { ...createTestAsset().metrics, usageCount: 5, successRate: 0.85 },
      });

      expect(assetManager.checkPromotion(asset)).toBe(true);
    });

    it('should return false when usage < 3', () => {
      const asset = createTestAsset({
        metrics: { ...createTestAsset().metrics, usageCount: 2, successRate: 0.9 },
      });

      expect(assetManager.checkPromotion(asset)).toBe(false);
    });

    it('should return false when success rate < 0.8', () => {
      const asset = createTestAsset({
        metrics: { ...createTestAsset().metrics, usageCount: 5, successRate: 0.7 },
      });

      expect(assetManager.checkPromotion(asset)).toBe(false);
    });
  });

  describe('evaluateAssetLifecycle - 生命周期评估', () => {
    it('should return active for high quality asset', () => {
      const asset = createTestAsset({
        metrics: {
          usageCount: 5,
          successRate: 0.9,
          lastUsedDate: new Date().toISOString(),
          coverageScore: 0.8,
          uniquenessScore: 0.7,
        },
        qualityScore: 0.9,
      });

      expect(assetManager.evaluateAssetLifecycle(asset)).toBe('active');
    });

    it('should return degraded for 30+ days inactive asset', () => {
      const oldDate = new Date();
      oldDate.setDate(oldDate.getDate() - 45);

      const asset = createTestAsset({
        metrics: {
          ...createTestAsset().metrics,
          lastUsedDate: oldDate.toISOString(),
          usageCount: 1,
          successRate: 0.5,
        },
        qualityScore: 0.5,
      });

      expect(assetManager.evaluateAssetLifecycle(asset)).toBe('degraded');
    });

    it('should return retired for eliminated asset', () => {
      const asset = createTestAsset({
        qualityScore: 0.2,
        tier: 'record',
        consecutive_failures: 3,
        elimination_status: 'eliminated',
      });

      expect(assetManager.evaluateAssetLifecycle(asset)).toBe('retired');
    });
  });

  // ============================================
  // ROI计算测试
  // ============================================
  describe('calculateTokenSavingROI', () => {
    it('should return quality * 0.72', () => {
      const asset = createTestAsset({ qualityScore: 0.8 });
      expect(assetManager.calculateTokenSavingROI(asset)).toBeCloseTo(0.576, 2);
    });

    it('should return higher ROI for higher quality', () => {
      const lowAsset = createTestAsset({ qualityScore: 0.5 });
      const highAsset = createTestAsset({ qualityScore: 0.9 });

      expect(assetManager.calculateTokenSavingROI(highAsset)).toBeGreaterThan(
        assetManager.calculateTokenSavingROI(lowAsset)
      );
    });
  });

  // ============================================
  // 资产报告测试
  // ============================================
  describe('getAssetReport - 资产报告', () => {
    it('should recommend elimination for record tier', () => {
      // Need to set metrics that produce quality < 0.30 (record tier)
      const asset = createTestAsset({
        metrics: {
          usageCount: 0,
          successRate: 0,
          lastUsedDate: new Date(0).toISOString(), // very old
          coverageScore: 0,
          uniquenessScore: 0,
        },
      });

      const report = assetManager.getAssetReport(asset);

      expect(report.recommendations).toContain('资产评分过低，建议淘汰');
      expect(report.isHealthy).toBe(false);
    });

    it('should warn about consecutive failures', () => {
      const asset = createTestAsset({
        consecutive_failures: 2,
      });

      const report = assetManager.getAssetReport(asset);

      expect(report.recommendations.some(r => r.includes('连续失败'))).toBe(true);
    });

    it('should recommend observation for available tier with 3 failures', () => {
      // For observation status, need available/premium tier + 3 consecutive failures
      const asset = createTestAsset({
        qualityScore: 0.65, // available tier
        tier: 'available',
        consecutive_failures: 3,
        elimination_status: 'observation',
      });

      const report = assetManager.getAssetReport(asset);

      expect(report.eliminationStatus).toBe('observation');
      expect(report.recommendations).toContain('资产处于观察期，需要替代品或确认');
    });

    it('should indicate whitelist_3month status when observation expires', () => {
      // Set up an asset that would be in whitelist_3month state
      // With available tier, 3 failures, and expired observation_end_date
      const expiredDate = new Date(Date.now() - 86400000).toISOString(); // 1 day ago
      const asset = createTestAsset({
        qualityScore: 0.65,
        tier: 'available',
        consecutive_failures: 3,
        elimination_status: 'observation',
        observation_end_date: expiredDate,
      });

      const report = assetManager.getAssetReport(asset);

      // The checkQuickElimination checks if observation_end_date is in the past
      // and if so, returns 'whitelist_3month'
      expect(report.eliminationStatus).toBe('whitelist_3month');
      expect(report.recommendations).toContain('资产获得3个月无条件使用权');
    });
  });

  // ============================================
  // 边界情况测试
  // ============================================
  describe('Edge Cases', () => {
    it('should handle asset with zero usageCount', () => {
      const asset = createTestAsset({
        metrics: { ...createTestAsset().metrics, usageCount: 0 },
      });

      const quality = assetManager.calculateQuality(asset);
      expect(quality).toBeDefined();
      expect(quality).toBeGreaterThanOrEqual(0);
    });

    it('should handle asset with zero successRate', () => {
      const asset = createTestAsset({
        metrics: { ...createTestAsset().metrics, successRate: 0 },
      });

      const quality = assetManager.calculateQuality(asset);
      expect(quality).toBeDefined();
      expect(quality).toBeLessThan(0.5);
    });

    it('should handle future lastUsedDate', () => {
      const futureDate = new Date();
      futureDate.setDate(futureDate.getDate() + 1);

      const asset = createTestAsset({
        metrics: { ...createTestAsset().metrics, lastUsedDate: futureDate.toISOString() },
      });

      const quality = assetManager.calculateQuality(asset);
      expect(quality).toBeDefined();
    });

    it('should handle all zero scores', () => {
      const asset = createTestAsset({
        metrics: {
          usageCount: 0,
          successRate: 0,
          lastUsedDate: new Date(0).toISOString(),
          coverageScore: 0,
          uniquenessScore: 0,
        },
      });

      const quality = assetManager.calculateQuality(asset);
      expect(quality).toBe(0);
    });

    it('should handle all perfect scores', () => {
      const asset = createTestAsset({
        metrics: {
          usageCount: 100,
          successRate: 1.0,
          lastUsedDate: new Date().toISOString(),
          coverageScore: 1.0,
          uniquenessScore: 1.0,
        },
      });

      const quality = assetManager.calculateQuality(asset);
      expect(quality).toBe(1.0);
    });
  });
});
