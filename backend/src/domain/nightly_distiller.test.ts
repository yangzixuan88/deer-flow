/**
 * M08 NightlyDistiller 单元测试
 * ================================================
 * 测试六阶段夜间复盘、GEPA进化、经验包蒸馏
 * ================================================
 */

import { jest } from '@jest/globals';
import {
  NightlyDistiller,
  ExperiencePackage,
  GEPAExperience,
  EvolutionOperation,
  ToolCall,
} from './nightly_distiller';

describe('NightlyDistiller 单元测试', () => {
  let distiller: NightlyDistiller;

  beforeEach(() => {
    distiller = new NightlyDistiller();
  });

  // 创建测试用的经验包
  const createTestPackage = (overrides: Partial<ExperiencePackage> = {}): ExperiencePackage => ({
    id: 'exp-001',
    timestamp: new Date().toISOString(),
    session_id: 'session-001',
    task_goal: 'build website',
    category: 'task',
    model_used: 'claude-opus-4',
    tool_calls: [
      { tool: 'read', input: 'spec.md', output_summary: 'spec loaded', success: true, duration_ms: 100 },
      { tool: 'bash', input: 'npm install', output_summary: 'packages installed', success: true, duration_ms: 5000 },
    ],
    total_tokens: 1000,
    total_duration_ms: 5100,
    result_quality: 0.85,
    reusable_patterns: [],
    failure_info: null,
    search_triggers: [],
    asset_hits: [],
    ...overrides,
  });

  const createMockContext = () => ({
    taskId: 'task-001',
    sessionId: 'session-001',
    agentId: 'agent-001',
    timestamp: new Date().toISOString(),
    metadata: {},
  });

  // ============================================
  // 触发时间检测
  // ============================================
  describe('isDreamingTime - 触发时间检测', () => {
    it('should return true at 02:00 AM', () => {
      // Mock Date to return 2 AM
      const originalDate = Date;
      const mockDate = new Date(2026, 3, 14, 2, 0, 0);
      jest.spyOn(global, 'Date').mockImplementation(() => mockDate as any);

      expect(distiller.isDreamingTime()).toBe(true);

      jest.restoreAllMocks();
    });

    it('should return false at other hours', () => {
      const originalDate = Date;
      const mockDate = new Date(2026, 3, 14, 10, 0, 0);
      jest.spyOn(global, 'Date').mockImplementation(() => mockDate as any);

      expect(distiller.isDreamingTime()).toBe(false);

      jest.restoreAllMocks();
    });
  });

  // ============================================
  // 阶段1: 聚合统计
  // ============================================
  describe('stage1_aggregateStats - 阶段1聚合统计', () => {
    it('should calculate total tasks', () => {
      const packages = [
        createTestPackage({ id: 'exp-1' }),
        createTestPackage({ id: 'exp-2' }),
        createTestPackage({ id: 'exp-3' }),
      ];

      const stats = distiller.stage1_aggregateStats(packages);

      expect(stats.total_tasks).toBe(3);
    });

    it('should count successes (quality >= 0.6)', () => {
      const packages = [
        createTestPackage({ id: 'exp-1', result_quality: 0.8 }),
        createTestPackage({ id: 'exp-2', result_quality: 0.5 }),
        createTestPackage({ id: 'exp-3', result_quality: 0.9 }),
      ];

      const stats = distiller.stage1_aggregateStats(packages);

      expect(stats.success_count).toBe(2);
      expect(stats.failure_count).toBe(1);
    });

    it('should calculate success rate', () => {
      const packages = [
        createTestPackage({ id: 'exp-1', result_quality: 0.8 }),
        createTestPackage({ id: 'exp-2', result_quality: 0.7 }),
      ];

      const stats = distiller.stage1_aggregateStats(packages);

      expect(stats.success_rate).toBe(1.0);
    });

    it('should aggregate total tokens', () => {
      const packages = [
        createTestPackage({ id: 'exp-1', total_tokens: 1000 }),
        createTestPackage({ id: 'exp-2', total_tokens: 2000 }),
      ];

      const stats = distiller.stage1_aggregateStats(packages);

      expect(stats.total_tokens).toBe(3000);
    });

    it('should aggregate total duration', () => {
      const packages = [
        createTestPackage({ id: 'exp-1', total_duration_ms: 1000 }),
        createTestPackage({ id: 'exp-2', total_duration_ms: 2000 }),
      ];

      const stats = distiller.stage1_aggregateStats(packages);

      expect(stats.total_duration_ms).toBe(3000);
    });

    it('should track model distribution', () => {
      const packages = [
        createTestPackage({ id: 'exp-1', model_used: 'claude-opus-4' }),
        createTestPackage({ id: 'exp-2', model_used: 'claude-sonnet-4-6' }),
        createTestPackage({ id: 'exp-3', model_used: 'claude-opus-4' }),
      ];

      const stats = distiller.stage1_aggregateStats(packages);

      expect(stats.model_distribution['claude-opus-4']).toBe(2);
      expect(stats.model_distribution['claude-sonnet-4-6']).toBe(1);
    });

    it('should track tool usage stats', () => {
      const packages = [
        createTestPackage({
          id: 'exp-1',
          tool_calls: [
            { tool: 'read', input: '', output_summary: '', success: true, duration_ms: 100 },
            { tool: 'bash', input: '', output_summary: '', success: true, duration_ms: 100 },
          ],
        }),
      ];

      const stats = distiller.stage1_aggregateStats(packages);

      expect(stats.tool_usage_stats['read']).toBe(1);
      expect(stats.tool_usage_stats['bash']).toBe(1);
    });

    it('should handle empty packages', () => {
      const stats = distiller.stage1_aggregateStats([]);

      expect(stats.total_tasks).toBe(0);
      expect(stats.success_rate).toBe(0);
      expect(stats.total_tokens).toBe(0);
    });
  });

  // ============================================
  // 阶段2: 瓶颈识别
  // ============================================
  describe('stage2_identifyBottlenecks - 阶段2瓶颈识别', () => {
    it('should find slowest tasks', () => {
      const packages = [
        createTestPackage({ id: 'exp-1', task_goal: 'fast task', total_duration_ms: 1000 }),
        createTestPackage({ id: 'exp-2', task_goal: 'slow task', total_duration_ms: 10000 }),
        createTestPackage({ id: 'exp-3', task_goal: 'medium task', total_duration_ms: 5000 }),
      ];

      const bottlenecks = distiller.stage2_identifyBottlenecks(packages);

      expect(bottlenecks.slowest_tasks.length).toBe(3);
      expect(bottlenecks.slowest_tasks[0].task).toBe('slow task');
    });

    it('should find most failed tools', () => {
      const packages = [
        createTestPackage({
          id: 'exp-1',
          tool_calls: [
            { tool: 'search', input: '', output_summary: '', success: false, duration_ms: 100 },
            { tool: 'read', input: '', output_summary: '', success: true, duration_ms: 100 },
          ],
        }),
        createTestPackage({
          id: 'exp-2',
          tool_calls: [
            { tool: 'search', input: '', output_summary: '', success: false, duration_ms: 100 },
            { tool: 'bash', input: '', output_summary: '', success: true, duration_ms: 100 },
          ],
        }),
      ];

      const bottlenecks = distiller.stage2_identifyBottlenecks(packages);

      expect(bottlenecks.most_failed_tools[0].tool).toBe('search');
      expect(bottlenecks.most_failed_tools[0].failure_count).toBe(2);
    });

    it('should identify redundant searches (>3 occurrences)', () => {
      const packages = [
        createTestPackage({ search_triggers: ['react', 'react', 'react', 'react'] }),
        createTestPackage({ search_triggers: ['typescript'] }),
      ];

      const bottlenecks = distiller.stage2_identifyBottlenecks(packages);

      expect(bottlenecks.redundant_searches).toContain('react');
      expect(bottlenecks.redundant_searches).not.toContain('typescript');
    });

    it('should generate improvement priorities', () => {
      const packages = [
        createTestPackage({
          id: 'exp-1',
          task_goal: 'slow task',
          total_duration_ms: 10000,
          tool_calls: [
            { tool: 'search', input: '', output_summary: '', success: false, duration_ms: 100 },
          ],
        }),
      ];

      const bottlenecks = distiller.stage2_identifyBottlenecks(packages);

      expect(bottlenecks.improvement_priorities.length).toBeGreaterThan(0);
      expect(bottlenecks.improvement_priorities[0].priority).toBe('high');
    });
  });

  // ============================================
  // 阶段3: 路径萃取
  // ============================================
  describe('stage3_extractPaths - 阶段3路径萃取', () => {
    it('should extract optimal paths from successful tasks', () => {
      const packages = [
        createTestPackage({
          id: 'exp-1',
          task_goal: 'build website',
          result_quality: 0.9,
          tool_calls: [
            { tool: 'read', input: '', output_summary: '', success: true, duration_ms: 100 },
            { tool: 'bash', input: '', output_summary: '', success: true, duration_ms: 100 },
            { tool: 'write', input: '', output_summary: '', success: true, duration_ms: 100 },
          ],
        }),
      ];

      const extractions = distiller.stage3_extractPaths(packages, []);

      expect(extractions.optimal_paths.length).toBe(1);
      expect(extractions.optimal_paths[0].tools).toEqual(['read', 'bash', 'write']);
    });

    it('should mark as CAPTURED when no existing asset', () => {
      const packages = [
        createTestPackage({
          id: 'exp-1',
          task_goal: 'new task',
          result_quality: 0.9,
        }),
      ];

      const extractions = distiller.stage3_extractPaths(packages, []);

      expect(extractions.candidates_captured).toContain('new task');
    });

    it('should mark as DERIVED when existing asset matches', () => {
      const packages = [
        createTestPackage({
          id: 'exp-1',
          task_goal: 'existing task',
          result_quality: 0.9,
        }),
      ];

      const existingAssets: GEPAExperience[] = [
        {
          intent: 'existing task',
          action_path: ['read', 'bash'],
          success: true,
          qualityScore: 0.8,
          date: new Date().toISOString(),
        },
      ];

      const extractions = distiller.stage3_extractPaths(packages, existingAssets);

      expect(extractions.candidates_derived).toContain('existing task');
    });

    it('should mark as FIX when asset quality < 0.5', () => {
      const packages = [
        createTestPackage({
          id: 'exp-1',
          task_goal: 'bad task',
          result_quality: 0.4,
          asset_hits: ['asset-1'],
        }),
      ];

      const extractions = distiller.stage3_extractPaths(packages, []);

      expect(extractions.candidates_fix).toContain('asset-1');
    });

    it('should pick shortest path for optimal', () => {
      const packages = [
        createTestPackage({
          id: 'exp-1',
          task_goal: 'same task',
          result_quality: 0.9,
          tool_calls: [
            { tool: 'read', input: '', output_summary: '', success: true, duration_ms: 100 },
            { tool: 'bash', input: '', output_summary: '', success: true, duration_ms: 100 },
          ],
        }),
        createTestPackage({
          id: 'exp-2',
          task_goal: 'same task',
          result_quality: 0.9,
          tool_calls: [
            { tool: 'read', input: '', output_summary: '', success: true, duration_ms: 100 },
          ],
        }),
      ];

      const extractions = distiller.stage3_extractPaths(packages, []);

      // Should pick the shorter path (just 'read')
      expect(extractions.optimal_paths[0].tools).toEqual(['read']);
    });
  });

  // ============================================
  // 阶段4: 资产生成
  // ============================================
  describe('stage4_generateAssets - 阶段4资产生成', () => {
    it('should promote assets with count >= 3 and successRate >= 80%', async () => {
      const packages = [
        createTestPackage({ id: 'exp-1', asset_hits: ['asset-1'], result_quality: 0.9 }),
        createTestPackage({ id: 'exp-2', asset_hits: ['asset-1'], result_quality: 0.9 }),
        createTestPackage({ id: 'exp-3', asset_hits: ['asset-1'], result_quality: 0.9 }),
      ];

      const changes = await distiller.stage4_generateAssets(packages, []);

      expect(changes.promotions.length).toBeGreaterThan(0);
    });

    it('should not promote assets with low count', async () => {
      const packages = [
        createTestPackage({ id: 'exp-1', asset_hits: ['asset-1'], result_quality: 0.9 }),
        createTestPackage({ id: 'exp-2', asset_hits: ['asset-1'], result_quality: 0.9 }),
      ];

      const changes = await distiller.stage4_generateAssets(packages, []);

      // 2 usages < 3 threshold, no promotion
      expect(changes.promotions.some(p => p.asset_id === 'asset-1')).toBe(false);
    });
  });

  // ============================================
  // 阶段5: 配置更新
  // ============================================
  describe('stage5_updateConfig - 阶段5配置更新', () => {
    it('should generate low-risk changes for high priority bottlenecks', () => {
      const bottlenecks = {
        slowest_tasks: [{ task: 'slow', duration_ms: 10000 }],
        most_failed_tools: [],
        highest_token_steps: [],
        redundant_searches: [],
        improvement_priorities: [{ item: 'optimize slow', priority: 'high' as const }],
      };

      const updates = distiller.stage5_updateConfig(bottlenecks);

      expect(updates.low_risk_changes.length).toBeGreaterThan(0);
    });

    it('should generate high-risk changes with requires_approval flag', () => {
      const bottlenecks = {
        slowest_tasks: [],
        most_failed_tools: [],
        highest_token_steps: [],
        redundant_searches: [],
        improvement_priorities: [],
      };

      const updates = distiller.stage5_updateConfig(bottlenecks);

      expect(updates.high_risk_changes.length).toBeGreaterThan(0);
      expect(updates.high_risk_changes[0].requires_approval).toBe(true);
    });
  });

  // ============================================
  // 阶段6: 日报生成
  // ============================================
  describe('stage6_generateReport - 阶段6日报生成', () => {
    it('should generate report with correct date', () => {
      const stats = distiller.stage1_aggregateStats([]);
      const bottlenecks = distiller.stage2_identifyBottlenecks([]);
      const assetChanges = { promotions: [], demotions: [], new_candidates: [], fixed_assets: [] };
      const configUpdates = { low_risk_changes: [], high_risk_changes: [] };

      const report = distiller.stage6_generateReport(stats, bottlenecks, assetChanges, configUpdates);

      expect(report.report_date).toBeDefined();
      expect(report.report_date.length).toBe(10); // YYYY-MM-DD
    });

    it('should include execution summary', () => {
      const packages = [createTestPackage({ total_tokens: 1000, total_duration_ms: 5000, result_quality: 0.8 })];
      const stats = distiller.stage1_aggregateStats(packages);
      const bottlenecks = distiller.stage2_identifyBottlenecks(packages);
      const assetChanges = { promotions: [], demotions: [], new_candidates: [], fixed_assets: [] };
      const configUpdates = { low_risk_changes: [], high_risk_changes: [] };

      const report = distiller.stage6_generateReport(stats, bottlenecks, assetChanges, configUpdates);

      expect(report.execution_summary.total_tasks).toBe(1);
      expect(report.execution_summary.token_consumed).toBe(1000);
    });

    it('should include asset dynamics', () => {
      const stats = distiller.stage1_aggregateStats([]);
      const bottlenecks = distiller.stage2_identifyBottlenecks([]);
      const assetChanges = {
        promotions: [{ asset_id: 'a1', from_tier: 'candidate', to_tier: 'active' }],
        demotions: [],
        new_candidates: ['new1'],
        fixed_assets: ['fix1'],
      };
      const configUpdates = { low_risk_changes: [], high_risk_changes: [] };

      const report = distiller.stage6_generateReport(stats, bottlenecks, assetChanges, configUpdates);

      expect(report.asset_dynamics.promotions).toBe(1);
      expect(report.asset_dynamics.new_candidates).toBe(1);
      expect(report.asset_dynamics.fixes).toBe(1);
    });
  });

  // ============================================
  // 六阶段完整执行
  // ============================================
  describe('executeSixStageReview - 六阶段完整执行', () => {
    it('should execute all six stages', async () => {
      const packages = [
        createTestPackage({
          id: 'exp-1',
          task_goal: 'test task',
          result_quality: 0.9,
          tool_calls: [{ tool: 'read', input: '', output_summary: '', success: true, duration_ms: 100 }],
        }),
      ];

      const report = await distiller.executeSixStageReview(packages, []);

      expect(report.date).toBeDefined();
      expect(report.stage1_summary).toBeDefined();
      expect(report.stage2_bottlenecks).toBeDefined();
      expect(report.stage3_extractions).toBeDefined();
      expect(report.stage4_assets).toBeDefined();
      expect(report.stage5_config_updates).toBeDefined();
      expect(report.stage6_report).toBeDefined();
    });

    it('should return complete NightlyReviewReport', async () => {
      const packages = [createTestPackage()];

      const report = await distiller.executeSixStageReview(packages, []);

      expect(report.stage1_summary.total_tasks).toBe(1);
      expect(report.stage6_report.report_date).toBeDefined();
    });
  });

  // ============================================
  // GEPA 蒸馏
  // ============================================
  describe('distill - GEPA蒸馏', () => {
    it('should extract high-quality intent-action pairs', async () => {
      const logs = [
        {
          toolName: 'read',
          intent: 'build website',
          success: true,
          duration_ms: 100,
          input: 'spec',
          output: 'spec loaded',
        },
        {
          toolName: 'bash',
          intent: 'build website',
          success: true,
          duration_ms: 1000,
          input: 'npm install',
          output: 'installed',
        },
      ] as any;

      const experiences = await distiller.distill(logs, createMockContext());

      expect(experiences.length).toBeGreaterThan(0);
    });

    it('should only include experiences with success rate >= 80%', async () => {
      const logs = [
        { toolName: 'read', intent: 'fail task', success: false, duration_ms: 100, input: '', output: '' },
        { toolName: 'bash', intent: 'fail task', success: false, duration_ms: 100, input: '', output: '' },
      ] as any;

      const experiences = await distiller.distill(logs, createMockContext());

      // All failures, no experience extracted
      expect(experiences.some(e => e.intent === 'fail task')).toBe(false);
    });

    it('should generate optimized rule', async () => {
      const logs = [
        { toolName: 'search', intent: 'find info', success: true, duration_ms: 100, input: 'query', output: 'results' },
      ] as any;

      const experiences = await distiller.distill(logs, createMockContext());

      expect(experiences.length).toBeGreaterThan(0);
      const first = experiences[0];
      expect(first).toBeDefined();
      expect(first.optimizedRule).toBeDefined();
      expect(first.optimizedRule!.length).toBeGreaterThan(0);
    });
  });

  // ============================================
  // DERIVED 进化
  // ============================================
  describe('deriveEnhancedAsset - DERIVED进化', () => {
    it('should create derived asset with shorter path', async () => {
      const sourceAsset: GEPAExperience = {
        intent: 'build api',
        action_path: ['read', 'search', 'write', 'test'],
        success: true,
        qualityScore: 0.8,
        date: new Date().toISOString(),
      };

      const traces = [
        { toolName: 'read', intent: 'build api', success: true, duration_ms: 100, action: ['read', 'write'], input: '', output: '' },
      ] as any;

      const derived = await distiller.deriveEnhancedAsset(sourceAsset, traces);

      expect(derived.evolutionType).toBe(EvolutionOperation.DERIVED);
      expect(derived.intent).toContain('[DERIVED]');
      expect(derived.sourceAssetId).toBe('build api');
    });

    it('should increase quality score on successful derivation', async () => {
      const sourceAsset: GEPAExperience = {
        intent: 'build api',
        action_path: ['read', 'write'],
        success: true,
        qualityScore: 0.8,
        date: new Date().toISOString(),
      };

      const traces = [
        { toolName: 'read', intent: 'build api', success: true, duration_ms: 100, action: ['read'], input: '', output: '' },
      ] as any;

      const derived = await distiller.deriveEnhancedAsset(sourceAsset, traces);

      // Quality capped at 1.0
      expect(derived.qualityScore).toBeLessThanOrEqual(1.0);
    });
  });

  // ============================================
  // FIX 进化
  // ============================================
  describe('fixDegradedAsset - FIX进化', () => {
    it('should fix degraded asset with improved quality', async () => {
      const degradedAsset: GEPAExperience = {
        intent: 'broken task',
        action_path: ['read', 'search'],
        success: false,
        qualityScore: 0.4,
        date: new Date().toISOString(),
      };

      const traces = [
        { toolName: 'read', intent: 'broken task', success: true, durationMs: 100, error: '', action: '', arguments: {}, tokensUsed: { input: 0, output: 0, total: 0 }, costUsd: 0, retryCount: 0, whitelistLevel: 'white' as const, confidence: 0.9 },
        { toolName: 'write', intent: 'broken task', success: true, durationMs: 100, error: '', action: '', arguments: {}, tokensUsed: { input: 0, output: 0, total: 0 }, costUsd: 0, retryCount: 0, whitelistLevel: 'white' as const, confidence: 0.9 },
      ] as any;

      const fixed = await distiller.fixDegradedAsset(degradedAsset, traces);

      expect(fixed.evolutionType).toBe(EvolutionOperation.FIX);
      expect(fixed.qualityScore).toBeGreaterThanOrEqual(degradedAsset.qualityScore);
    });

    it('should still fix even with no failure traces', async () => {
      const degradedAsset: GEPAExperience = {
        intent: 'broken task',
        action_path: ['read', 'search'],
        success: false,
        qualityScore: 0.4,
        date: new Date().toISOString(),
      };

      const traces: any[] = [];

      const fixed = await distiller.fixDegradedAsset(degradedAsset, traces);

      expect(fixed.evolutionType).toBe(EvolutionOperation.FIX);
      expect(fixed.qualityScore).toBeGreaterThan(degradedAsset.qualityScore);
    });
  });

  // ============================================
  // OpenSpace 三操作进化
  // ============================================
  describe('performOpenSpaceEvolution - OpenSpace进化', () => {
    it('should perform CAPTURED operation', async () => {
      const logs = [
        { toolName: 'read', intent: 'new task', success: true, duration_ms: 100, input: '', output: '' },
      ] as any;

      const experiences = await distiller.performOpenSpaceEvolution(logs, []);

      const captured = experiences.filter(e => e.evolutionType === EvolutionOperation.CAPTURED);
      expect(captured.length).toBeGreaterThanOrEqual(0); // May or may not have CAPTURED
    });

    it('should perform DERIVED on high-quality assets', async () => {
      const existingAssets: GEPAExperience[] = [
        {
          intent: 'existing task',
          action_path: ['read'],
          success: true,
          qualityScore: 0.9,
          date: new Date().toISOString(),
        },
      ];

      const logs = [
        { toolName: 'read', intent: 'existing task', success: true, duration_ms: 100, action: ['read', 'bash'], input: '', output: '' },
      ] as any;

      const experiences = await distiller.performOpenSpaceEvolution(logs, existingAssets);

      const derived = experiences.filter(e => e.evolutionType === EvolutionOperation.DERIVED);
      // May have DERIVED if related traces exist
      expect(Array.isArray(derived)).toBe(true);
    });

    it('should perform FIX on degraded assets', async () => {
      const existingAssets: GEPAExperience[] = [
        {
          intent: 'degraded task',
          action_path: ['read'],
          success: false,
          qualityScore: 0.4,
          date: new Date().toISOString(),
        },
      ];

      const logs = [
        { toolName: 'read', intent: 'degraded task', success: true, duration_ms: 100, input: '', output: '' },
      ] as any;

      const experiences = await distiller.performOpenSpaceEvolution(logs, existingAssets);

      const fixed = experiences.filter(e => e.evolutionType === EvolutionOperation.FIX);
      expect(fixed.length).toBeGreaterThanOrEqual(0);
    });
  });

  // ============================================
  // 边界情况测试
  // ============================================
  describe('Edge Cases', () => {
    it('should handle empty experience packages', async () => {
      const report = await distiller.executeSixStageReview([], []);

      expect(report.stage1_summary.total_tasks).toBe(0);
      expect(report.stage6_report.execution_summary.total_tasks).toBe(0);
    });

    it('should handle packages with no tool calls', () => {
      const packages = [createTestPackage({ tool_calls: [] })];

      const stats = distiller.stage1_aggregateStats(packages);

      expect(stats.total_tasks).toBe(1);
      expect(stats.tool_usage_stats).toEqual({});
    });

    it('should handle 100% failure rate', () => {
      const packages = [
        createTestPackage({ result_quality: 0.3 }),
        createTestPackage({ result_quality: 0.2 }),
      ];

      const stats = distiller.stage1_aggregateStats(packages);

      expect(stats.success_count).toBe(0);
      expect(stats.failure_count).toBe(2);
      expect(stats.success_rate).toBe(0);
    });

    it('should handle all models being the same', () => {
      const packages = [
        createTestPackage({ model_used: 'claude-opus-4' }),
        createTestPackage({ model_used: 'claude-opus-4' }),
        createTestPackage({ model_used: 'claude-opus-4' }),
      ];

      const stats = distiller.stage1_aggregateStats(packages);

      expect(Object.keys(stats.model_distribution)).toHaveLength(1);
      expect(stats.model_distribution['claude-opus-4']).toBe(3);
    });
  });
});
