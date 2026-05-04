/**
 * @file approval_tier.ts
 * @description U6: 审批分级
 * 将候选分为T0/T1/T2/T3四级
 */

import {
  SandboxPlanResult,
  ApprovalTierResult,
  TieredCandidate,
  SandboxPlan,
  ApprovalTier,
} from './types';

export class ApprovalTierClassifier {
  /**
   * 确定审批分级
   */
  public async determine(sandboxResult: SandboxPlanResult): Promise<ApprovalTierResult> {
    console.log('[ApprovalTier] 确定审批分级...');

    const candidates: TieredCandidate[] = [];

    for (const plan of sandboxResult.plans) {
      const tiered = this.createTieredCandidate(plan);
      candidates.push(tiered);
    }

    console.log(`[ApprovalTier] 分级完成: ${candidates.length} 个候选`);

    return {
      date: new Date().toISOString().split('T')[0],
      candidates,
    };
  }

  /**
   * 创建分级候选
   * R179: Injects ROI signals into TieredCandidate so U7 report can see them
   */
  private createTieredCandidate(plan: SandboxPlan): TieredCandidate {
    // R34 fix: deep_analysis_pool items bypass approval even if T2 — they go to experiment_queue
    const isDeepAnalysis = (plan as any)._deepAnalysisItem === true;
    console.log(`[ApprovalTier] createTieredCandidate: ${plan.candidate_id} _deepAnalysisItem=${isDeepAnalysis}`);
    const tier = this.determineTierFromPlan(plan, isDeepAnalysis);
    console.log(`[ApprovalTier] → tier=${tier}, requiresApproval override=${isDeepAnalysis ? 'false' : 'normal'}`);
    const requiresApproval = isDeepAnalysis ? false : this.requiresApproval(tier);
    const approvalType = this.getApprovalType(tier, plan);
    const riskLevel = this.assessRiskLevel(plan, tier);
    const backoutPlan = this.generateBackoutPlan(plan, riskLevel);

    // R179: Detect ROI leniency was applied in determineTierFromPlan
    // ltvBonus < 0 means tier was upgraded (tightened approval bar) via high ROI history
    const ltvBonus = this.computeLtvBonus(plan);
    const roiLeniencyApplied = ltvBonus < 0;

    // R179: Detect experiment_access via ROI leniency (U178 canProceed logic)
    // High LTV (>=12) T1 candidates get canProceed=true even when prior_score < 50
    const bd = plan.score_breakdown;
    const highLtvT1 = bd && bd.long_term_value >= 12 && tier === 'T1';
    const experimentAccessViaRoi = isDeepAnalysis || highLtvT1;

    // R204-K: Compute predicted_value conditioned on filter_result (U2 pool分流).
    // This replaces the hardcoded 0.9 in the Python backflow script.
    // observation_pool → 0.6 (中性不确定，需要观察，实际 typically 0.5)
    // experiment_pool / deep_analysis / bypass → 0.9 (信号充分，实际 typically 1.0)
    // excluded / rejected → 0.3 (信号负面)
    let predictedValue = 0.9; // default
    const fr = (plan as any).filter_result;
    if (fr === 'observation_pool') {
      predictedValue = plan.can_proceed_to_experiment ? 0.75 : 0.6;
    } else if (fr === 'excluded') {
      predictedValue = 0.3;
    }

    return {
      candidate_id: plan.candidate_id,
      project: plan.candidate_id.replace(/^demand-/, '').replace(/-[^-]*$/, ''),
      tier,
      requires_approval: requiresApproval,
      approval_type: approvalType,
      items_requiring_approval: requiresApproval ? this.getApprovalItems(tier, plan) : undefined,
      risk_level: riskLevel,
      backout_plan: backoutPlan,
      // R179: ROI signals for report visibility
      long_term_value: bd?.long_term_value,
      can_proceed_to_experiment: plan.can_proceed_to_experiment,
      experiment_access_via_roi_leniency: experimentAccessViaRoi,
      roi_leniency_applied: roiLeniencyApplied,
      score_breakdown: bd,
      filter_result: (plan as any).filter_result,
      // R204-K: predicted_value conditioned on U2 filter_result pool分流
      predicted_value: predictedValue,
    };
  }

  /**
   * R179: Extract LTV bonus value for ROI leniency detection
   * Mirrors the same logic used in determineTierFromPlan
   */
  private computeLtvBonus(plan: SandboxPlan): number {
    const bd = plan.score_breakdown;
    if (!bd) return 0;
    if (bd.long_term_value >= 12) return -1;
    if (bd.long_term_value >= 8) return 0;
    return 1;
  }

  /**
   * 从计划确定级别
   * Real input: score_breakdown.risk_complexity and score_breakdown.deployment_control
   * Falls back to string matching on risk_observations only if score_breakdown unavailable.
   * R34 fix: deep_analysis_pool items always get T1 (experiment access) regardless of breakdown
   */
  private determineTierFromPlan(plan: SandboxPlan, isDeepAnalysis: boolean = false): ApprovalTier {
    // R34 fix: deep_analysis_pool items get T1 directly — immutable zone already validated
    if (isDeepAnalysis) {
      console.log(`[ApprovalTier] R34 fix: deep_analysis item ${plan.candidate_id} → T1`);
      return 'T1';
    }

    if (!plan.can_proceed_to_experiment) {
      return 'T3';
    }

    // Real: use structured score_breakdown from U4/U5
    const bd = plan.score_breakdown;
    if (bd) {
      // R176 FIX: ROI-backed long_term_value adjusts approval tier
      // Strong ROI history (high LTV) → more lenient tier (lower T number = less approval)
      // Low LTV → tighter tier (higher T number = more approval required)
      const ltvBonus: number = bd.long_term_value >= 12 ? -1   // foundational/strategic: upgrade one tier
        : bd.long_term_value >= 8 ? 0                           // moderate LTV: normal tier
        : 1;                                                   // low LTV: tighten tier

      // High risk: low risk_complexity (<=3) AND low deployment_control (<=2)
      if (bd.risk_complexity <= 3 && bd.deployment_control <= 2) {
        return ltvBonus < 0 ? 'T1' : 'T2';
      }
      // Medium-high: low risk_complexity OR low deployment_control
      // R176: high LTV can offset some risk → bump to T1 even in medium-high risk
      if (bd.risk_complexity <= 5 || bd.deployment_control <= 2) {
        return ltvBonus < 0 ? 'T1' : 'T2';
      }
      // Medium risk: low risk_complexity <=7 AND deployment_control <=3
      // R176: high LTV with medium risk → leniency → T1
      if (bd.risk_complexity <= 7 && bd.deployment_control <= 3) {
        return ltvBonus < 0 ? 'T1' : (ltvBonus === 0 ? 'T2' : 'T2');
      }
      return 'T1';
    }

    // Fallback: string matching only if score_breakdown unavailable (degraded mode)
    const riskObservations = plan.risk_observations || [];
    const hasHighRisk = riskObservations.some((obs) =>
      obs.includes('高风险') || obs.includes('核心模块')
    );
    if (hasHighRisk) {
      return 'T2';
    }

    return 'T1';
  }

  /**
   * 判断是否需要审批
   * R34 fix: deep_analysis_pool items bypass approval — they go directly to experiment_queue
   */
  private requiresApproval(tier: ApprovalTier): boolean {
    // deep_analysis_pool items (marked via score._deepAnalysisItem) don't need approval
    // They were already validated by U2's immutable zone logic and deserve experiment access
    return tier === 'T2' || tier === 'T3';
  }

  /**
   * 获取审批类型
   */
  private getApprovalType(
    tier: ApprovalTier,
    plan: SandboxPlan
  ): 'feishu_card' | 'none' {
    if (tier === 'T0' || tier === 'T1') {
      return 'none';
    }

    if (tier === 'T2' || tier === 'T3') {
      return 'feishu_card';
    }

    return 'none';
  }

  /**
   * 评估风险等级
   * Real input: score_breakdown.risk_complexity and score_breakdown.deployment_control (2D matrix)
   * Falls back to string matching on risk_observations only if score_breakdown unavailable.
   */
  private assessRiskLevel(
    plan: SandboxPlan,
    tier: ApprovalTier
  ): 'low' | 'medium' | 'high' | 'critical' {
    if (tier === 'T3') return 'critical';
    if (tier === 'T2') return 'high';

    // Real: 2D risk matrix from score_breakdown
    const bd = plan.score_breakdown;
    if (bd) {
      // Critical: both very low
      if (bd.risk_complexity <= 2 && bd.deployment_control <= 1) return 'critical';
      // High: low risk_complexity + low deployment_control
      if (bd.risk_complexity <= 4 && bd.deployment_control <= 2) return 'high';
      // Medium: moderate risk complexity OR low deployment control
      if (bd.risk_complexity <= 6 || bd.deployment_control <= 3) return 'medium';
      return 'low';
    }

    // Fallback: string matching only if score_breakdown unavailable (degraded mode)
    const touchesCore = plan.risk_observations?.some((obs) =>
      obs.includes('核心模块')
    );
    if (touchesCore) return 'high';

    const hasHighRiskObs = plan.risk_observations?.some((obs) =>
      obs.includes('高风险')
    );
    if (hasHighRiskObs) return 'medium';

    return 'low';
  }

  /**
   * 生成回退计划
   */
  private generateBackoutPlan(plan: SandboxPlan, riskLevel: string): string {
    const steps = [
      '1. 执行回滚脚本',
      '2. 验证服务恢复',
      '3. 检查指标回归',
    ];

    if (riskLevel === 'critical' || riskLevel === 'high') {
      steps.unshift('0. 通知相关人员');
      steps.push('4. 发送事后报告');
    }

    return steps.join('\n');
  }

  /**
   * 获取需要审批的项目
   */
  private getApprovalItems(tier: ApprovalTier, plan: SandboxPlan): string[] {
    const items: string[] = [];

    if (tier === 'T2') {
      items.push('依赖安装');
      items.push('服务启动');
      items.push('正式patch');
    }

    if (tier === 'T3') {
      items.push('触碰核心不可变区');
      items.push('核心逻辑变更');
      items.push('回滚方案审批');
    }

    if (plan.dependencies && plan.dependencies.length > 0) {
      items.push(`依赖: ${plan.dependencies.join(', ')}`);
    }

    if (plan.env_vars_required && plan.env_vars_required.length > 0) {
      items.push(`环境变量: ${plan.env_vars_required.join(', ')}`);
    }

    return items;
  }

  /**
   * 按级别分组候选
   */
  public groupByTier(result: ApprovalTierResult): Map<ApprovalTier, TieredCandidate[]> {
    const groups = new Map<ApprovalTier, TieredCandidate[]>();

    groups.set('T0', []);
    groups.set('T1', []);
    groups.set('T2', []);
    groups.set('T3', []);

    for (const candidate of result.candidates) {
      const list = groups.get(candidate.tier) || [];
      list.push(candidate);
      groups.set(candidate.tier, list);
    }

    return groups;
  }
}
