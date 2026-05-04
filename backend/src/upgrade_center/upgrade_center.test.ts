/**
 * 夜间升级中枢 单元测试
 * ================================================
 * 测试 U0-U8 各阶段核心功能
 * ================================================
 */

import { jest } from '@jest/globals';
import {
  UpgradeCenter,
  upgradeCenter,
} from './index';
import { ConstitutionLoader } from './constitution_loader';
import { DemandSampler } from './demand_sampler';
import { ExternalScout } from './external_scout';
import { ConstitutionFilter } from './constitution_filter';
import { LocalMapper } from './local_mapper';
import { PriorScorer } from './prior_scorer';
import { SandboxPlanner } from './sandbox_planner';
import { ApprovalTierClassifier } from './approval_tier';
import { ReportGenerator } from './report_generator';
import { QueueManager } from './queue_manager';

describe('升级中枢 U0-U8 单元测试', () => {
  let upgradeCenterInstance: UpgradeCenter;

  beforeEach(() => {
    upgradeCenterInstance = new UpgradeCenter();
  });

  describe('U0: 宪法装载 (ConstitutionLoader)', () => {
    it('应成功加载宪法状态', async () => {
      const loader = new ConstitutionLoader();
      const state = await loader.load();

      expect(state).toBeDefined();
      expect(state.constitution_loaded).toBe(true);
      expect(state.immutable_zones).toBeDefined();
      expect(Array.isArray(state.immutable_zones)).toBe(true);
      expect(state.last_updated).toBeDefined();
    });

    it('应有默认不可变区配置', async () => {
      const loader = new ConstitutionLoader();
      const state = await loader.load();

      expect(state.immutable_zones.length).toBeGreaterThan(0);
      const zoneIds = state.immutable_zones.map(z => z.zone_id);
      expect(zoneIds).toContain('M01_coordinator');
      expect(zoneIds).toContain('M03_hooks');
    });
  });

  describe('U1: 需求采样 (DemandSampler + ExternalScout)', () => {
    it('应能采样内部瓶颈需求', async () => {
      const sampler = new DemandSampler();
      const demands = await sampler.sampleFromInternalBottlenecks();

      expect(demands).toBeDefined();
      expect(Array.isArray(demands)).toBe(true);
      expect(demands.length).toBeGreaterThan(0);
      expect(demands[0].source).toBe('internal_bottleneck');
    });

    it('应能采样资产退化需求', async () => {
      const sampler = new DemandSampler();
      const demands = await sampler.sampleFromAssetDegradation();

      expect(demands).toBeDefined();
      expect(Array.isArray(demands)).toBe(true);
    });

    it('应能采集外部情报', async () => {
      const scout = new ExternalScout();
      const demands = await scout.scout();

      expect(demands).toBeDefined();
      expect(Array.isArray(demands)).toBe(true);
      expect(demands.length).toBeGreaterThan(0);
      expect(demands[0].source).toBe('external_scout');
    });

    it('应能合并多源需求', async () => {
      const sampler = new DemandSampler();
      const demands1 = await sampler.sampleFromInternalBottlenecks();
      const demands2 = await sampler.sampleFromAssetDegradation();

      const pool = sampler.mergeDemands([demands1, demands2]);

      expect(pool).toBeDefined();
      expect(pool.demands).toBeDefined();
      expect(pool.demands.length).toBeGreaterThan(0);
      expect(pool.date).toBeDefined();
    });
  });

  describe('U2: 宪法筛选 (ConstitutionFilter)', () => {
    it('应能过滤需求', async () => {
      const sampler = new DemandSampler();
      const demands = await sampler.sampleFromInternalBottlenecks();
      const pool = sampler.mergeDemands([demands]);

      const filter = new ConstitutionFilter();
      const result = await filter.filter(pool);

      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
      expect(result.pool_counts).toBeDefined();
      expect(typeof result.pool_counts.excluded).toBe('number');
      expect(typeof result.pool_counts.observation).toBe('number');
      expect(typeof result.pool_counts.experiment).toBe('number');
      expect(typeof result.pool_counts.deep_analysis).toBe('number');
    });
  });

  describe('U3: 本地映射 (LocalMapper)', () => {
    it('应能生成本地映射', async () => {
      const sampler = new DemandSampler();
      const demands = await sampler.sampleFromInternalBottlenecks();
      const pool = sampler.mergeDemands([demands]);

      const filter = new ConstitutionFilter();
      const filterResult = await filter.filter(pool);

      const mapper = new LocalMapper();
      const report = await mapper.map(filterResult);

      expect(report).toBeDefined();
      expect(report.mappings).toBeDefined();
      expect(report.date).toBeDefined();
    });
  });

  describe('U4: 先验评分 (PriorScorer)', () => {
    it('应能计算先验分', async () => {
      // 创建可通过宪法过滤的测试需求
      const scorer = new PriorScorer();
      const mockMappingReport = {
        date: new Date().toISOString().split('T')[0],
        mappings: [{
          candidate_id: 'test-agent-upgrade',
          target_modules: ['M04_unified_executor'],
          capability_gain: ['autonomous learning', 'agent execution'],
          integration_type: 'adapter' as const,
          risk_zone_touches: [],
          immutable_zone_touches: [],
          affected_call_chains: ['M01→M04→M05'],
          estimated_token_overhead: 2000,
        }],
      };

      const scoreResult = await scorer.score(mockMappingReport);

      expect(scoreResult).toBeDefined();
      expect(scoreResult.scores).toBeDefined();
      expect(scoreResult.scores.length).toBeGreaterThan(0);

      const firstScore = scoreResult.scores[0];
      expect(typeof firstScore.prior_score).toBe('number');
      expect(firstScore.prior_score).toBeGreaterThanOrEqual(0);
      expect(firstScore.prior_score).toBeLessThanOrEqual(100);
      expect(firstScore.breakdown).toBeDefined();
      expect(firstScore.tier).toBeDefined();
    });
  });

  describe('U5: 沙盒计划 (SandboxPlanner)', () => {
    it('应能生成沙盒计划', async () => {
      const scorer = new PriorScorer();
      const mockMappingReport = {
        date: new Date().toISOString().split('T')[0],
        mappings: [{
          candidate_id: 'test-candidate-001',
          target_modules: ['M04_unified_executor'],
          capability_gain: ['test capability'],
          integration_type: 'adapter' as const,
          risk_zone_touches: [],
          immutable_zone_touches: [],
          affected_call_chains: [],
          estimated_token_overhead: 2000,
        }],
      };

      const mockScoreResult = await scorer.score(mockMappingReport);
      const planner = new SandboxPlanner();
      const planResult = await planner.plan(mockScoreResult);

      expect(planResult).toBeDefined();
      expect(planResult.plans).toBeDefined();
    });
  });

  describe('U6: 审批分级 (ApprovalTierClassifier)', () => {
    it('应能正确分级候选', async () => {
      const classifier = new ApprovalTierClassifier();
      const mockSandboxResult = {
        date: new Date().toISOString().split('T')[0],
        plans: [{
          candidate_id: 'test-candidate-001',
          deployment_type: 'docker_compose_separate' as const,
          env_vars_required: ['NODE_ENV'],
          dependencies: [],
          verification_script: '/tmp/verify.sh',
          rollback_script: '/tmp/rollback.sh',
          risk_observations: ['高风险变更'],
          can_proceed_to_experiment: false,
        }],
      };

      const tierResult = await classifier.determine(mockSandboxResult);

      expect(tierResult).toBeDefined();
      expect(tierResult.candidates).toBeDefined();
      expect(tierResult.candidates.length).toBeGreaterThan(0);

      const candidate = tierResult.candidates[0];
      expect(candidate.tier).toBeDefined();
      expect(['T0', 'T1', 'T2', 'T3']).toContain(candidate.tier);
      expect(candidate.risk_level).toBeDefined();
    });
  });

  describe('U7: 报告生成 (ReportGenerator)', () => {
    it('应能生成升级中枢报告', async () => {
      const classifier = new ApprovalTierClassifier();
      const mockSandboxResult = {
        date: new Date().toISOString().split('T')[0],
        plans: [{
          candidate_id: 'test-candidate-001',
          deployment_type: 'docker_compose_separate' as const,
          env_vars_required: ['NODE_ENV'],
          dependencies: [],
          verification_script: '/tmp/verify.sh',
          rollback_script: '/tmp/rollback.sh',
          risk_observations: [],
          can_proceed_to_experiment: true,
        }],
      };

      const tierResult = await classifier.determine(mockSandboxResult);

      const generator = new ReportGenerator();
      const report = await generator.generate(tierResult);

      expect(report).toBeDefined();
      expect(report.date).toBeDefined();
      expect(report.run_type).toBe('full');
      expect(report.stages_completed).toContain('U0');
      expect(report.stages_completed).toContain('U7');
      expect(report.summary).toBeDefined();
    });
  });

  describe('U8: 队列管理 (QueueManager)', () => {
    it('应能获取队列状态', async () => {
      const queueManager = new QueueManager();
      const status = await queueManager.getQueueStatus();

      expect(status).toBeDefined();
      expect(typeof status.pending_approvals).toBe('number');
      expect(typeof status.experiment_queue_size).toBe('number');
      expect(typeof status.observation_pool_size).toBe('number');
    });

    it('应能检查冷静期', async () => {
      const queueManager = new QueueManager();
      await queueManager.checkCooldowns();
    });
  });

  describe('UpgradeCenter 集成', () => {
    it('应能获取升级中枢状态', async () => {
      const status = await upgradeCenterInstance.getStatus();

      expect(status).toBeDefined();
      expect(typeof status.pending_approvals).toBe('number');
      expect(typeof status.experiment_queue_size).toBe('number');
      expect(typeof status.observation_pool_size).toBe('number');
    });
  });
});
