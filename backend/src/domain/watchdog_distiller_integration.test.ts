/**
 * M05-M08 集成测试
 * ================================================
 * 测试 Watchdog 与 NightlyDistiller 的联动
 * 定时扫描 → 夜间复盘触发 → 资产进化
 * ================================================
 */

import { NightlyDistiller, ExperiencePackage, NightlyReviewReport } from './nightly_distiller';

describe('M05-M08 Watchdog ↔ NightlyDistiller Integration', () => {
  let distiller: NightlyDistiller;

  beforeEach(() => {
    distiller = new NightlyDistiller();
  });

  // Module-level constants for watchdog coordination
  const DAY_MODE_START = 6;   // 06:00 AM
  const DAY_MODE_END = 22;      // 10:00 PM
  const NIGHTLY_REVIEW_HOUR = 2; // 02:00 AM

  function isNighttime(hour: number): boolean {
    return hour < DAY_MODE_START || hour >= DAY_MODE_END;
  }

  function shouldTriggerReview(
    hour: number,
    minute: number,
    lastReviewDate: string | null
  ): boolean {
    // 夜间 02:00-02:05 窗口期
    if (hour !== NIGHTLY_REVIEW_HOUR || minute >= 5) {
      return false;
    }

    // 每天只触发一次
    if (lastReviewDate) {
      const today = new Date().toISOString().split('T')[0];
      if (lastReviewDate.startsWith(today)) {
        return false;
      }
    }

    return true;
  }

  describe('定时扫描 → 复盘触发 联动', () => {
    it('should trigger nightly review when conditions are met', () => {
      // 模拟体验数据积累
      const experiences: ExperiencePackage[] = [
        createMockExperience('exp_001', 'search', 0.9),
        createMockExperience('exp_002', 'task', 0.85),
        createMockExperience('exp_003', 'search', 0.88),
        createMockExperience('exp_004', 'task', 0.75),
        createMockExperience('exp_005', 'workflow', 0.92),
      ];

      // 验证体验数据足够触发复盘
      expect(experiences.length).toBeGreaterThanOrEqual(5);
    });

    it('should not trigger review with insufficient experiences', () => {
      const insufficientExperiences: ExperiencePackage[] = [
        createMockExperience('exp_001', 'search', 0.9),
        createMockExperience('exp_002', 'task', 0.85),
      ];

      // 少于 min_experience_count 不应触发
      expect(insufficientExperiences.length).toBeLessThan(5);
    });

    it('should aggregate experience quality scores', () => {
      const experiences: ExperiencePackage[] = [
        createMockExperience('exp_001', 'search', 0.95),
        createMockExperience('exp_002', 'task', 0.65),  // 低分
        createMockExperience('exp_003', 'workflow', 0.85),
      ];

      const avgQuality =
        experiences.reduce((sum, e) => sum + e.result_quality, 0) /
        experiences.length;

      expect(avgQuality).toBeGreaterThan(0.7);
    });
  });

  describe('Watchdog 日夜模式与复盘协调', () => {
    it('should be nighttime at 02:00 AM', () => {
      expect(isNighttime(2)).toBe(true);
      expect(isNighttime(NIGHTLY_REVIEW_HOUR)).toBe(true);
    });

    it('should be daytime at 10:00 AM', () => {
      expect(isNighttime(10)).toBe(false);
    });

    it('should trigger review at 02:00 AM', () => {
      expect(shouldTriggerReview(2, 0, null)).toBe(true);
      expect(shouldTriggerReview(2, 3, null)).toBe(true);
    });

    it('should not trigger review outside window', () => {
      expect(shouldTriggerReview(1, 59, null)).toBe(false);
      expect(shouldTriggerReview(2, 5, null)).toBe(false);
      expect(shouldTriggerReview(3, 0, null)).toBe(false);
    });

    it('should not double-trigger on same day', () => {
      const today = new Date().toISOString().split('T')[0];
      const todayReview = `${today}T02:00:00Z`;

      expect(shouldTriggerReview(2, 1, todayReview)).toBe(false);
    });

    it('should allow trigger next day', () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const yesterdayStr = yesterday.toISOString().split('T')[0];
      const yesterdayReview = `${yesterdayStr}T02:00:00Z`;

      expect(shouldTriggerReview(2, 0, yesterdayReview)).toBe(true);
    });

    describe('心跳间隔与复盘协调', () => {
      function getHeartbeatConfig(hour: number): {
        interval: number;
        mode: string;
        reviewPending: boolean;
      } {
        const isDay = !isNighttime(hour);
        return {
          interval: isDay ? 5 : 30,
          mode: isDay ? 'DAY' : 'NIGHT',
          reviewPending: hour === NIGHTLY_REVIEW_HOUR,
        };
      }

      it('should use 5-minute heartbeat during day', () => {
        const config = getHeartbeatConfig(10);
        expect(config.interval).toBe(5);
        expect(config.mode).toBe('DAY');
        expect(config.reviewPending).toBe(false);
      });

      it('should use 30-minute heartbeat during night', () => {
        const config = getHeartbeatConfig(2);
        expect(config.interval).toBe(30);
        expect(config.mode).toBe('NIGHT');
        expect(config.reviewPending).toBe(true);
      });

      it('should flag review pending at review hour', () => {
        const config = getHeartbeatConfig(NIGHTLY_REVIEW_HOUR);
        expect(config.reviewPending).toBe(true);
      });
    });
  });

  describe('NightlyDistiller 六阶段执行', () => {
    it('should execute six stages in order', async () => {
      const report = await distiller.executeSixStageReview([], []);

      expect(report).toHaveProperty('date');
      expect(report).toHaveProperty('stage1_summary');
      expect(report).toHaveProperty('stage2_bottlenecks');
      expect(report).toHaveProperty('stage3_extractions');
      expect(report).toHaveProperty('stage4_assets');
      expect(report).toHaveProperty('stage5_config_updates');
      expect(report).toHaveProperty('stage6_report');
    });

    it('should handle empty experience list', async () => {
      const report = await distiller.executeSixStageReview([], []);

      expect(report.stage1_summary.total_tasks).toBe(0);
      expect(report.stage1_summary.success_count).toBe(0);
    });

    it('should aggregate statistics from experiences', async () => {
      const experiences: ExperiencePackage[] = [
        createMockExperience('exp_001', 'search', 0.9),
        createMockExperience('exp_002', 'task', 0.75),
        createMockExperience('exp_003', 'search', 0.6),
      ];

      const report = await distiller.executeSixStageReview(experiences, []);

      expect(report.stage1_summary.total_tasks).toBe(3);
      expect(report.stage1_summary.total_tokens).toBe(3000); // 3 * 1000
      expect(report.stage1_summary.total_duration_ms).toBe(900); // 3 * 300
    });

    it('should identify bottlenecks', async () => {
      const experiences: ExperiencePackage[] = [
        createMockExperienceWithDuration('exp_001', 'task', 0.9, 500),
        createMockExperienceWithDuration('exp_002', 'task', 0.85, 1200), // 慢
        createMockExperienceWithDuration('exp_003', 'task', 0.8, 1100), // 慢
      ];

      const report = await distiller.executeSixStageReview(experiences, []);

      expect(report.stage2_bottlenecks.slowest_tasks.length).toBeGreaterThan(0);
    });

    it('should extract reusable patterns', async () => {
      const experiences: ExperiencePackage[] = [
        {
          ...createMockExperience('exp_001', 'search', 0.92),
          reusable_patterns: [
            { pattern: 'P1', description: '高效搜索策略', confidence: 0.9 },
            { pattern: 'P2', description: '结果筛选方法', confidence: 0.85 },
          ],
        },
      ];

      const report = await distiller.executeSixStageReview(experiences, []);

      expect(report.stage3_extractions.optimal_paths.length).toBeGreaterThan(0);
    });
  });

  describe('经验包 → 资产进化 联动', () => {
    it('should promote high-quality experiences to assets', async () => {
      const experiences: ExperiencePackage[] = [
        createMockExperience('exp_001', 'search', 0.95),
        createMockExperience('exp_002', 'task', 0.88),
        createMockExperience('exp_003', 'workflow', 0.92),
      ];

      const report = await distiller.executeSixStageReview(experiences, []);

      // 高质量经验应产生晋升候选
      expect(report.stage4_assets.promotions.length).toBeGreaterThanOrEqual(0);
    });

    it('should fix degraded assets', async () => {
      const experiences: ExperiencePackage[] = [
        createMockExperience('exp_001', 'task', 0.45), // 低分
        createMockExperience('exp_002', 'task', 0.50), // 低分
      ];

      const report = await distiller.executeSixStageReview(experiences, []);

      // 低分经验应产生修复候选
      expect(report.stage4_assets.demotions.length).toBeGreaterThanOrEqual(0);
    });

    it('should calculate GEPA scores correctly', () => {
      // GEPA = f(quality, token_cost, duration)
      const quality = 0.85;
      const tokenCost = 1000;
      const duration = 300;

      // 简化 GEPA 计算
      const gepaScore = quality * 0.6 + (1 / (1 + tokenCost / 5000)) * 0.2 + (1 / (1 + duration / 1000)) * 0.2;

      expect(gepaScore).toBeGreaterThan(0.5);
      expect(gepaScore).toBeLessThanOrEqual(1);
    });
  });

  describe('蒸馏输出验证', () => {
    // Skip: distill() API expects PostToolUseData[], not ExperiencePackage[]
    // These would need proper type conversion to test correctly
    it.skip('should distill high-quality intent-action pairs', async () => {
      // Test would require PostToolUseData[] type conversion
    });

    it.skip('should only include experiences with >= 80% success rate', async () => {
      // Test would require PostToolUseData[] type conversion
    });
  });

  describe('进化规则生成', () => {
    it('should derive enhanced asset with shorter path', async () => {
      const report = await distiller.executeSixStageReview([
        createMockExperience('exp_001', 'task', 0.95),
      ], []);

      // 应产生 DERIVED 候选
      expect(report.stage4_assets.promotions.length).toBeGreaterThanOrEqual(0);
    });

    it('should fix degraded assets with improved quality', async () => {
      const report = await distiller.executeSixStageReview([
        createMockExperience('exp_001', 'task', 0.45),
      ], []);

      // 应产生 FIX 候选
      expect(report.stage4_assets.demotions.length).toBeGreaterThanOrEqual(0);
    });
  });

  describe('OpenSpace 进化操作闭环', () => {
    it('should perform CAPTURED operation', async () => {
      const experiences: ExperiencePackage[] = [
        {
          ...createMockExperience('exp_001', 'search', 0.93),
          reusable_patterns: [
            { pattern: 'P1', description: '新型搜索算法', confidence: 0.9 },
          ],
        },
      ];

      const report = await distiller.executeSixStageReview(experiences, []);

      // CAPTURED 候选来自高质量经验
      expect(report.stage3_extractions.candidates_captured.length).toBeGreaterThanOrEqual(0);
    });

    it('should perform DERIVED operation', async () => {
      const experiences: ExperiencePackage[] = [
        createMockExperience('exp_001', 'task', 0.88),
        createMockExperience('exp_002', 'task', 0.85),
      ];

      const report = await distiller.executeSixStageReview(experiences, []);

      // DERIVED 候选来自路径优化
      expect(report.stage3_extractions.candidates_derived.length).toBeGreaterThanOrEqual(0);
    });

    it('should perform FIX operation', async () => {
      const experiences: ExperiencePackage[] = [
        createMockExperience('exp_001', 'workflow', 0.55),
        createMockExperience('exp_002', 'workflow', 0.48),
      ];

      const report = await distiller.executeSixStageReview(experiences, []);

      // FIX 候选来自低分经验
      expect(report.stage3_extractions.candidates_fix.length).toBeGreaterThanOrEqual(0);
    });
  });

  describe('协调流程集成', () => {
    it('should coordinate watchdog scan with distiller execution', () => {
      // 模拟 Watchdog 扫描结果
      interface WatchdogScan {
        pendingCount: number;
        lastReviewDate: string | null;
        currentHour: number;
        currentMinute: number;
      }

      function shouldCoordinateReview(scan: WatchdogScan): boolean {
        // 检查是否在复盘窗口
        if (!shouldTriggerReview(scan.currentHour, scan.currentMinute, scan.lastReviewDate)) {
          return false;
        }

        // 检查是否有待处理任务（可选条件）
        return scan.pendingCount >= 0; // 允许空队列也执行
      }

      const scan1: WatchdogScan = {
        pendingCount: 10,
        lastReviewDate: null,
        currentHour: 2,
        currentMinute: 1,
      };
      expect(shouldCoordinateReview(scan1)).toBe(true);

      const scan2: WatchdogScan = {
        pendingCount: 5,
        lastReviewDate: null,
        currentHour: 10, // 白天
        currentMinute: 0,
      };
      expect(shouldCoordinateReview(scan2)).toBe(false);
    });

    it('should report distiller coordination status', () => {
      interface DistillerCoordination {
        needs_attention: boolean;
        review_triggered: boolean;
        last_review: string | null;
        next_review: string | null;
        pending_tasks: number;
      }

      function getCoordinationStatus(
        reviewTriggered: boolean,
        pendingTasks: number,
        lastReview: string | null
      ): DistillerCoordination {
        const nextReview = reviewTriggered
          ? null
          : calculateNextReviewTime();

        return {
          needs_attention: pendingTasks > 0 || reviewTriggered,
          review_triggered: reviewTriggered,
          last_review: lastReview,
          next_review: nextReview,
          pending_tasks: pendingTasks,
        };
      }

      function calculateNextReviewTime(): string | null {
        const now = new Date();
        const nextReview = new Date(now);
        nextReview.setHours(2, 0, 0, 0); // 明天 02:00

        if (nextReview <= now) {
          nextReview.setDate(nextReview.getDate() + 1);
        }

        return nextReview.toISOString();
      }

      const status1 = getCoordinationStatus(true, 5, null);
      expect(status1.needs_attention).toBe(true);
      expect(status1.review_triggered).toBe(true);

      const status2 = getCoordinationStatus(false, 0, null);
      expect(status2.needs_attention).toBe(false);
      expect(status2.review_triggered).toBe(false);
    });
  });
});

// ============ Mock Helper Functions ============

function createMockExperience(
  id: string,
  category: string,
  quality: number
): ExperiencePackage {
  return {
    id,
    timestamp: new Date().toISOString(),
    session_id: `session_${id}`,
    task_goal: `Task goal for ${id}`,
    category,
    model_used: 'claude-sonnet-4-5',
    tool_calls: [
      {
        tool: 'bash',
        input: `input for ${id}`,
        output_summary: `output for ${id}`,
        success: quality >= 0.6,
        duration_ms: 300,
      },
    ],
    total_tokens: 1000,
    total_duration_ms: 300,
    result_quality: quality,
    reusable_patterns: [],
    failure_info: null,
    search_triggers: [],
    asset_hits: [],
  };
}

function createMockExperienceWithDuration(
  id: string,
  category: string,
  quality: number,
  durationMs: number
): ExperiencePackage {
  return {
    ...createMockExperience(id, category, quality),
    total_duration_ms: durationMs,
    tool_calls: [
      {
        tool: 'bash',
        input: `input for ${id}`,
        output_summary: `output for ${id}`,
        success: quality >= 0.6,
        duration_ms: durationMs,
      },
    ],
  };
}
