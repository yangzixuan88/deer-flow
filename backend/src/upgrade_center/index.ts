/**
 * @file index.ts
 * @description Upgrade Center main orchestrator
 * Coordinates U0-U8 stages for nightly upgrade governance
 */

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
import {
  UpgradeCenterReport,
  ConstitutionState,
  UpgradeDemandPool,
  ConstitutionFilterResult,
  LocalMappingReport,
  PriorScoreResult,
  SandboxPlanResult,
  ApprovalTierResult,
} from './types';

export class UpgradeCenter {
  private constitutionLoader: ConstitutionLoader;
  private demandSampler: DemandSampler;
  private externalScout: ExternalScout;
  private constitutionFilter: ConstitutionFilter;
  private localMapper: LocalMapper;
  private priorScorer: PriorScorer;
  private sandboxPlanner: SandboxPlanner;
  private approvalTier: ApprovalTierClassifier;
  private reportGenerator: ReportGenerator;
  private queueManager: QueueManager;
  private deerflowRoot: string;

  constructor(deerflowRoot?: string) {
    this.deerflowRoot = deerflowRoot || process.cwd();
    this.constitutionLoader = new ConstitutionLoader();
    this.demandSampler = new DemandSampler();
    this.externalScout = new ExternalScout();
    this.constitutionFilter = new ConstitutionFilter();
    this.localMapper = new LocalMapper();
    this.priorScorer = new PriorScorer();
    this.sandboxPlanner = new SandboxPlanner();
    this.approvalTier = new ApprovalTierClassifier();
    this.reportGenerator = new ReportGenerator(this.deerflowRoot);
    this.queueManager = new QueueManager();
  }

  /**
   * Execute the full U0-U8 upgrade governance pipeline
   */
  public async executeFullRun(): Promise<UpgradeCenterReport> {
    console.log('[UpgradeCenter] Starting full U0-U8 governance run');

    // U0: Constitution Load
    const constitutionState = await this.u0_constitutionLoad();

    // U1: Demand Sampling
    const demandPool = await this.u1_sampleDemands();

    // U2: Constitution Filter
    const filterResult = await this.u2_constitutionFilter(demandPool);

    // U3: Local Mapping
    const mappingReport = await this.u3_localMapping(filterResult);

    // U4: Prior Scoring
    const scoreResult = await this.u4_priorScoring(mappingReport);

    // U5: Sandbox Planning
    const sandboxResult = await this.u5_sandboxPlanning(scoreResult, filterResult);

    // U6: Approval Tiers
    const tierResult = await this.u6_approvalTiers(sandboxResult);

    // U7: Report Generation
    const report = await this.u7_generateReports(tierResult);

    // U8: Queue & Cooldown
    await this.u8_queueTasks(report);

    console.log('[UpgradeCenter] Full governance run complete');
    return report;
  }

  /**
   * U0: Constitution Load
   * Load constitutional rules and state at review start
   */
  private async u0_constitutionLoad(): Promise<ConstitutionState> {
    console.log('[UpgradeCenter] U0: Loading constitution...');
    return this.constitutionLoader.load();
  }

  /**
   * U1: Demand Sampling
   * Aggregate upgrade demands from three sources
   */
  private async u1_sampleDemands(): Promise<UpgradeDemandPool> {
    console.log('[UpgradeCenter] U1: Sampling upgrade demands...');

    // Sample from internal bottleneck data (from NightlyDistiller Stage 2)
    const internalDemands = await this.demandSampler.sampleFromInternalBottlenecks();

    // Sample from asset degradation data (from NightlyDistiller Stage 4)
    const assetDemands = await this.demandSampler.sampleFromAssetDegradation();

    // Sample from external intel
    const externalDemands = await this.externalScout.scout();

    // Sample from governance outcome records written by Python UEF evolve() / drift_check()
    // Closes Python→TS loop: governance_bridge._outcome_records → governance_state.json → here
    const governanceDemands = await this.demandSampler.sampleFromGovernanceState();

    // R201: Process approval_result demands for immediate state migration
    // Feishu approval results should trigger enqueue/cooldown/observation without waiting for nightly cycle
    const approvalResultDemands = governanceDemands.filter(
      (d: any) => d.source === 'governance_upgrade_center_approval_result'
    );
    if (approvalResultDemands.length > 0) {
      console.log(`[UpgradeCenter] R201: Processing ${approvalResultDemands.length} approval_result demands for state migration`);
      await this.queueManager.handleApprovalResultDemands(approvalResultDemands as any);
    }

    return this.demandSampler.mergeDemands([internalDemands, assetDemands, externalDemands, governanceDemands]);
  }

  /**
   * U2: Constitution Filter
   * First-layer filtering per constitutional rules
   */
  private async u2_constitutionFilter(demandPool: UpgradeDemandPool): Promise<ConstitutionFilterResult> {
    console.log('[UpgradeCenter] U2: Filtering demands per constitution...');
    const result = await this.constitutionFilter.filter(demandPool);
    // Capture pool_counts so U7 report can use real U2 filter output
    this.lastPoolCounts = result.pool_counts;
    return result;
  }

  /**
   * U3: Local System Mapping
   * Translate external projects into local module enhancement value
   */
  private async u3_localMapping(filterResult: ConstitutionFilterResult): Promise<LocalMappingReport> {
    console.log('[UpgradeCenter] U3: Mapping to local system...');
    return this.localMapper.map(filterResult);
  }

  /**
   * U4: Prior Analysis Scoring
   * Calculate prior analysis score for local validation input
   */
  private async u4_priorScoring(mappingReport: LocalMappingReport): Promise<PriorScoreResult> {
    console.log('[UpgradeCenter] U4: Calculating prior scores...');
    return this.priorScorer.score(mappingReport);
  }

  /**
   * U5: Sandbox Validation Plan
   * Generate sandbox validation plan for experiment pool candidates
   * R34 fix: also generates plans for deep_analysis_pool items so they can reach U6/experiment_queue
   */
  private async u5_sandboxPlanning(scoreResult: PriorScoreResult, filterResult: ConstitutionFilterResult): Promise<SandboxPlanResult> {
    console.log('[UpgradeCenter] U5: Generating sandbox plans...');
    return this.sandboxPlanner.plan(scoreResult, filterResult);
  }

  /**
   * U6: Approval Tiers
   * Classify candidates into T0/T1/T2/T3 tiers
   */
  private async u6_approvalTiers(sandboxResult: SandboxPlanResult): Promise<ApprovalTierResult> {
    console.log('[UpgradeCenter] U6: Determining approval tiers...');
    return this.approvalTier.determine(sandboxResult);
  }

  /**
   * U7: Dual Report Generation
   * Generate internal report and Feishu morning report
   */
  private async u7_generateReports(tierResult: ApprovalTierResult): Promise<UpgradeCenterReport> {
    console.log('[UpgradeCenter] U7: Generating reports...');
    // Pass pool_counts from U2 (ConstitutionFilter) so report summary reflects real U2 state
    return this.reportGenerator.generate(tierResult, this.lastPoolCounts);
  }

  private lastPoolCounts: { excluded: number; observation: number; experiment: number; deep_analysis: number } | undefined = undefined;

  /**
   * U8: Queue & Cooldown
   * Write results to queues and execute cooldown checks
   */
  private async u8_queueTasks(report: UpgradeCenterReport): Promise<void> {
    console.log('[UpgradeCenter] U8: Managing queues and cooldowns...');
    await this.queueManager.enqueue(report);
    await this.queueManager.checkCooldowns();
  }

  /**
   * Get current upgrade center status
   */
  public async getStatus(): Promise<{
    pending_approvals: number;
    experiment_queue_size: number;
    observation_pool_size: number;
  }> {
    return this.queueManager.getQueueStatus();
  }
}

// Singleton export
export const upgradeCenter = new UpgradeCenter();
