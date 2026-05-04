/**
 * @file prior_scorer.ts
 * @description U4: 先验分析评分
 * 计算先验分析分，为本地验证提供输入
 */

import {
  LocalMappingReport,
  PriorScoreResult,
  CandidateScore,
  ScoreBreakdown,
  ApprovalTier,
} from './types';
import { ROIEngine } from '../domain/roi_engine';

export class PriorScorer {
  private roiEngine: ROIEngine;

  constructor() {
    this.roiEngine = new ROIEngine();
  }
  /**
   * 对映射报告进行先验评分
   */
  public async score(mappingReport: LocalMappingReport): Promise<PriorScoreResult> {
    console.log('[PriorScorer] 开始先验分析评分...');

    const scores: CandidateScore[] = [];

    for (const mapping of mappingReport.mappings) {
      const score = this.calculateScore(mapping);
      scores.push(score);
    }

    console.log(`[PriorScorer] 完成 ${scores.length} 个候选评分`);

    return {
      date: new Date().toISOString().split('T')[0],
      scores,
    };
  }

  /**
   * 计算单个候选的评分
   */
  private calculateScore(mapping: LocalMapping): CandidateScore {
    const breakdown = this.calculateBreakdown(mapping);
    let totalScore = this.sumBreakdown(breakdown);

    // R205-B FIX: Governance-origin observation candidates should not be inflated in U4.
    // governance_priority=observation_pool means U2 already classified this as a conservative
    // signal — it should stay in the observation/conservative path through U4/U5/U6.
    // Apply a fixed penalty so these candidates don't get re-elevated to T1 via prior_score.
    // Penalty of -15: prior_score 57 → 42 (T2), ensuring can_proceed=false in U5.
    const gp = (mapping as any).governance_priority;
    if (gp === 'observation_pool') {
      totalScore -= 15;
      console.log(`[PriorScorer] R205-B: governance_priority=observation_pool → prior_score penalty ${totalScore + 15} → ${totalScore}`);
    }

    const tier = this.determineTier(totalScore, mapping);
    const localValidationRequired = this.requiresLocalValidation(totalScore, tier);

    return {
      candidate_id: mapping.candidate_id,
      prior_score: totalScore,
      breakdown,
      tier,
      local_validation_required: localValidationRequired,
      // R206-B fix: propagate governance_priority from LocalMapping through U4→U5
      governance_priority: gp,
    };
  }

  /**
   * 计算各维度分项
   */
  private calculateBreakdown(mapping: LocalMapping): ScoreBreakdown {
    return {
      long_term_value: this.scoreLongTermValue(mapping),
      capability_ceiling: this.scoreCapabilityCeiling(mapping),
      gap_filling: this.scoreGapFilling(mapping),
      engineering_maturity: this.scoreEngineeringMaturity(mapping),
      architecture_compatibility: this.scoreArchitectureCompatibility(mapping),
      code_quality: this.scoreCodeQuality(mapping),
      deployment_control: this.scoreDeploymentControl(mapping),
      risk_complexity: this.scoreRiskComplexity(mapping),
    };
  }

  /**
   * 长期价值评分 (0-15)
   */
  private scoreLongTermValue(mapping: LocalMapping): number {
    const foundational = this.isFoundationalCapability(mapping);
    const strategic = this.isStrategicDirection(mapping);

    // R174 FIX: Module-targeted ROI bonus (replaces R173 coarse-grained global bonus)
    // Only candidates with module overlap to ROI history get the bonus.
    // This makes ROI correction candidate-specific, not system-wide.
    const candidateModules = mapping.target_modules || [];
    let roiBonus = 0;

    if (candidateModules.length > 0) {
      const roiWall = this.roiEngine.loadROIWall();
      if (roiWall && roiWall.profits.length > 0) {
        // Filter ROI profits that touched the same modules as this candidate
        const relevantProfits = roiWall.profits.filter(p =>
          p.targetModules && p.targetModules.some(m => candidateModules.includes(m))
        );

        if (relevantProfits.length > 0) {
          // R175 FIX: Time-weighted averaging (replaces R174 equal-weight average)
          // Recent ROI profits get higher weight via exponential decay.
          // Half-life = 7 days: weight = exp(-ln(2)/7 * ageInDays)
          // This prevents stale high-ROI records from permanently biasing current scores.
          const now = Date.now();
          const HALF_LIFE_DAYS = 7;
          const decayRate = Math.LN2 / HALF_LIFE_DAYS;

          let weightedSavingsSum = 0;
          let weightedQualitySum = 0;
          let totalWeight = 0;

          for (const p of relevantProfits) {
            const ageMs = now - new Date(p.timestamp).getTime();
            const ageDays = ageMs / (1000 * 60 * 60 * 24);
            const weight = Math.exp(-decayRate * ageDays);
            weightedSavingsSum += p.savingsUsd * weight;
            weightedQualitySum += p.qualityScore * weight;
            totalWeight += weight;
          }

          const avgSavings = totalWeight > 0 ? weightedSavingsSum / totalWeight : 0;
          const avgQuality = totalWeight > 0 ? weightedQualitySum / totalWeight : 0;
          if (avgSavings > 0.01 && avgQuality > 0.7) roiBonus = 1;
          if (avgSavings > 0.05 && avgQuality > 0.85) roiBonus = 2;
        }
      }
    }

    let base: number;
    if (foundational && strategic) base = 15;
    else if (foundational) base = 12;
    else if (strategic) base = 10;
    else base = 5;

    return Math.min(15, base + roiBonus);
  }

  /**
   * 能力上限提升评分 (0-20)
   */
  private scoreCapabilityCeiling(mapping: LocalMapping): number {
    const capabilities = mapping.capability_gain.length;
    const touchesCore = mapping.immutable_zone_touches.length > 0;

    if (capabilities >= 5 && touchesCore) return 20;
    if (capabilities >= 4) return 16;
    if (capabilities >= 3) return 12;
    if (capabilities >= 2) return 8;
    return 4;
  }

  /**
   * 补短板价值评分 (0-15)
   */
  private scoreGapFilling(mapping: LocalMapping): number {
    const gaps = ['reliability', 'performance', 'scalability', 'fault tolerance'];
    const fills = mapping.capability_gain.some((cap) =>
      gaps.some((gap) => cap.toLowerCase().includes(gap))
    );

    if (fills) return 12;
    return 5;
  }

  /**
   * 工程成熟度评分 (0-10)
   */
  private scoreEngineeringMaturity(mapping: LocalMapping): number {
    const project = mapping.candidate_id.toLowerCase();

    if (project.includes('experimental') || project.includes('alpha')) {
      return 3;
    }
    if (project.includes('beta') || project.includes('rc')) {
      return 6;
    }

    return 8;
  }

  /**
   * 架构兼容度评分 (0-15)
   */
  private scoreArchitectureCompatibility(mapping: LocalMapping): number {
    const integrationTypes: Record<string, number> = {
      adapter: 12,
      patch: 10,
      replace: 5,
      fork_refactor: 3,
    };

    return integrationTypes[mapping.integration_type] || 8;
  }

  /**
   * 代码质量评分 (0-10)
   * Real scoring: derives from code complexity signals in the mapping.
   * Higher risk_zone_touches and immutable_zone_touches = lower quality score
   * (indicates higher-risk integration requiring more scrutiny).
   */
  private scoreCodeQuality(mapping: LocalMapping): number {
    let quality = 8; // baseline: decent quality expected

    // More risk zone touches = more integration points = harder to maintain
    if (mapping.risk_zone_touches.length >= 4) quality -= 3;
    else if (mapping.risk_zone_touches.length >= 2) quality -= 2;
    else if (mapping.risk_zone_touches.length >= 1) quality -= 1;

    // Immutable zone touches = core system changes = highest scrutiny
    if (mapping.immutable_zone_touches.length > 0) quality -= 2;

    // Many call chains affected = wide impact = harder to validate
    if (mapping.affected_call_chains.length > 3) quality -= 2;
    else if (mapping.affected_call_chains.length > 1) quality -= 1;

    // Large token overhead suggests complex changes
    if (mapping.estimated_token_overhead > 5000) quality -= 1;

    return Math.max(1, Math.min(10, quality));
  }

  /**
   * 部署可控性评分 (0-5)
   */
  private scoreDeploymentControl(mapping: LocalMapping): number {
    const highRiskModules = ['M01_coordinator', 'M03_hooks'];
    const touchesHighRisk = mapping.immutable_zone_touches.some((m) =>
      highRiskModules.includes(m)
    );

    if (touchesHighRisk) return 1;
    if (mapping.estimated_token_overhead > 5000) return 2;
    return 4;
  }

  /**
   * 风险/回退复杂度评分 (0-10, 越高分越低风险)
   */
  private scoreRiskComplexity(mapping: LocalMapping): number {
    let risk = 5;

    if (mapping.risk_zone_touches.length > 3) risk -= 2;
    if (mapping.immutable_zone_touches.length > 0) risk -= 3;
    if (mapping.affected_call_chains.length > 2) risk -= 2;

    return Math.max(0, Math.min(10, risk));
  }

  /**
   * 计算总分
   */
  private sumBreakdown(breakdown: ScoreBreakdown): number {
    return (
      breakdown.long_term_value +
      breakdown.capability_ceiling +
      breakdown.gap_filling +
      breakdown.engineering_maturity +
      breakdown.architecture_compatibility +
      breakdown.code_quality +
      breakdown.deployment_control +
      breakdown.risk_complexity
    );
  }

  /**
   * 确定审批级别
   */
  private determineTier(totalScore: number, mapping: LocalMapping): ApprovalTier {
    if (totalScore < 20) return 'T3';
    if (totalScore < 50) return 'T2';
    if (totalScore < 75) return 'T1';
    return 'T0';
  }

  /**
   * 判断是否需要本地验证
   */
  private requiresLocalValidation(totalScore: number, tier: ApprovalTier): boolean {
    return tier === 'T0' || tier === 'T1' || totalScore >= 50;
  }

  /**
   * 判断是否为基础能力
   */
  private isFoundationalCapability(mapping: LocalMapping): boolean {
    const foundational = ['llm', 'memory', 'execution', 'reasoning', 'planning'];
    return mapping.capability_gain.some((cap) =>
      foundational.some((f) => cap.toLowerCase().includes(f))
    );
  }

  /**
   * 判断是否符合战略方向
   */
  private isStrategicDirection(mapping: LocalMapping): boolean {
    const strategic = ['autonomous', 'agent', 'learning', 'evolution'];
    return mapping.capability_gain.some((cap) =>
      strategic.some((s) => cap.toLowerCase().includes(s))
    );
  }
}

interface LocalMapping {
  candidate_id: string;
  target_modules: string[];
  capability_gain: string[];
  integration_type: 'adapter' | 'patch' | 'replace' | 'fork_refactor';
  risk_zone_touches: string[];
  immutable_zone_touches: string[];
  affected_call_chains: string[];
  estimated_token_overhead: number;
}
