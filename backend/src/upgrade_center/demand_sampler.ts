/**
 * @file demand_sampler.ts
 * @description U1: Demand Sampler
 * Aggregates upgrade demands from internal sources (bottlenecks + asset degradation + governance state)
 *
 * MINIMUM CLOSED LOOP WIRING (Round 4):
 * - governance_state.json path: {cwd}/backend/app/m11/governance_state.json
 * - Reads outcome_records of type nightly_evolution / doctrine_drift_detected
 * - Extracts next_actions / drift_signals as UpgradeDemand entries
 * - Falls back to empty array if file missing or parse fails (preserves mock paths)
 */

import * as fs from 'fs';
import * as path from 'path';
import { runtimePath } from '../runtime_paths';
import { NightlyDistiller, Stage2Bottlenecks, Stage4AssetChanges } from '../domain/nightly_distiller';
import { UpgradeDemandPool, UpgradeDemand } from './types';

export class DemandSampler {
  private distiller: NightlyDistiller;

  constructor() {
    this.distiller = new NightlyDistiller();
  }

  /**
   * Path to governance_state.json — populated by Python governance_bridge.py
   * Writes from Python UEF evolve() and drift_check() flow through governance_bridge.record_outcome()
   * into governance_state.json, which this method reads to close the Python→TS loop.
   */
  private getGovernanceStatePath(): string {
    // Handle both run locations: deerflow/ root and deerflow/backend/
    const rawRoot = process.cwd();
    const deerflowRoot = rawRoot.endsWith('backend') ? path.dirname(rawRoot) : rawRoot;
    return path.join(deerflowRoot, 'backend', 'app', 'm11', 'governance_state.json');
  }

  /**
   * Sample demands from internal bottleneck data
   * Source: NightlyDistiller Stage 2 output in the project-local .deerflow/upgrade-center/state directory.
   *
   * MINIMUM CLOSED LOOP: NightlyDistiller (Python) → Stage2 JSON → here
   * Falls back to sample data if file missing (degraded mode, clearly labeled).
   */
  public async sampleFromInternalBottlenecks(): Promise<UpgradeDemand[]> {
    console.log('[DemandSampler] Sampling from internal bottlenecks...');

    const demands: UpgradeDemand[] = [];
    const stateDir = runtimePath('upgrade-center', 'state');
    const bottleneckPath = path.join(stateDir, 'nightly_review_stage2_bottlenecks.json');

    // Try to load real Stage2 bottleneck data from NightlyDistiller
    let realDataFound = false;
    if (fs.existsSync(bottleneckPath)) {
      try {
        const raw = fs.readFileSync(bottleneckPath, 'utf-8');
        const data = JSON.parse(raw);
        const stage2: Stage2Bottlenecks = data;

        // Generate one demand per high-priority improvement item
        // R33: Enrich with capability_gain from bottleneck evidence so U4 PriorScorer can score meaningfully.
        const priorities = stage2.improvement_priorities || [];
        const hasSlowTasks = (stage2.slowest_tasks || []).some((t: any) => t.duration_ms > 1000);
        const hasFailedTools = (stage2.most_failed_tools || []).some((t: any) => t.failure_count >= 2);
        const hasHighToken = (stage2.highest_token_steps || []).some((t: any) => t.tokens > 5000);

        // Build capability_gain from concrete bottleneck evidence
        const bottleneckCapabilityGain: string[] = [];
        if (hasSlowTasks) {
          bottleneckCapabilityGain.push('execution_efficiency', 'performance');
        }
        if (hasFailedTools) {
          bottleneckCapabilityGain.push('reliability', 'fault_tolerance');
        }
        if (hasHighToken) {
          bottleneckCapabilityGain.push('token_efficiency');
        }

        for (const item of priorities) {
          if (item.priority !== 'high') continue;
          demands.push({
            id: `demand-${Date.now()}-bottleneck-${item.item.replace(/[^a-zA-Z0-9]/g, '-')}`,
            source: 'internal_bottleneck',
            description: item.item,
            related_module: this.inferModuleFromBottleneckItem(item.item),
            detected_at: new Date().toISOString(),
            bottleneck_data: stage2,
            capability_gain: [...bottleneckCapabilityGain],
          });
        }

        // Also generate demands for most-failed tools
        const failedTools = stage2.most_failed_tools || [];
        for (const ft of failedTools.slice(0, 3)) {
          if (ft.failure_count < 2) continue;
          demands.push({
            id: `demand-${Date.now()}-failed-tool-${ft.tool.replace(/[^a-zA-Z0-9]/g, '-')}`,
            source: 'internal_bottleneck',
            description: `高频失败工具 [${ft.tool}] 需要可靠性增强 (失败次数: ${ft.failure_count})`,
            related_module: this.inferModuleFromTool(ft.tool),
            detected_at: new Date().toISOString(),
            bottleneck_data: stage2,
            capability_gain: ['reliability', 'fault_tolerance', 'tool_reliability'],
          });
        }

        if (demands.length > 0 || priorities.length > 0 || failedTools.length > 0) {
          realDataFound = true;
          console.log(`[DemandSampler] Found ${demands.length} real internal bottleneck demands from Stage2`);
        }

        // R167 FIX: "no high-priority items" is NORMAL when system is healthy — NOT degraded mode.
        // Deprioritize the high-priority filter: emit demands for any real bottleneck evidence,
        // so that a "low priority, no significant bottlenecks" NightlyDistiller result
        // still generates real demands (even low-priority ones) instead of falling back to sample.
        if (demands.length === 0 && realDataFound) {
          const desc = priorities[0]?.item || (failedTools.length > 0 ? `高频失败工具: ${failedTools[0].tool}` : '系统运行平稳');
          const capGain = failedTools.length > 0 ? ['reliability', 'fault_tolerance'] : ['execution_efficiency'];
          demands.push({
            id: `demand-${Date.now()}-bottleneck-healthy`,
            source: 'internal_bottleneck',
            description: `[NightlyDistiller] ${desc}`,
            related_module: 'M04_unified_executor',
            detected_at: new Date().toISOString(),
            bottleneck_data: stage2,
            capability_gain: capGain,
          });
          console.log(`[DemandSampler] R167: emitted demand for healthy-system result (no high-priority items)`);
        }
      } catch (err) {
        console.warn(`[DemandSampler] Failed to read Stage2 bottleneck data: ${err}`);
      }
    }

    // Fallback: sample data (degraded mode — only when file truly does not exist)
    if (!realDataFound) {
      console.log('[DemandSampler] WARNING: Stage2 file does not exist — using SAMPLE bottleneck data (degraded mode)');
      const sampleDemand: UpgradeDemand = {
        id: `demand-${Date.now()}-internal-001`,
        source: 'internal_bottleneck',
        description: 'High failure rate detected in search tool - needs reliability enhancement',
        related_module: 'M04_unified_executor',
        detected_at: new Date().toISOString(),
        bottleneck_data: this.getSampleBottleneckData(),
      };
      demands.push(sampleDemand);
    }

    console.log(`[DemandSampler] Internal bottleneck demands: ${demands.length}`);
    return demands;
  }

  /**
   * Infer module from bottleneck item description (best-effort)
   */
  private inferModuleFromBottleneckItem(item: string): string {
    const lower = item.toLowerCase();
    if (lower.includes('search')) return 'M04_unified_executor';
    if (lower.includes('memory') || lower.includes('working')) return 'M05_memory_l1';
    if (lower.includes('asset')) return 'M07_asset_manager';
    if (lower.includes('ui') || lower.includes('render')) return 'M09_ui_evolution';
    if (lower.includes('hook')) return 'M03_hooks';
    return 'M04_unified_executor';
  }

  /**
   * Infer module from tool name (best-effort)
   */
  private inferModuleFromTool(tool: string): string {
    const lower = tool.toLowerCase();
    if (lower.includes('search')) return 'M04_unified_executor';
    if (lower.includes('memory') || lower.includes('working')) return 'M05_memory_l1';
    if (lower.includes('asset')) return 'M07_asset_manager';
    if (lower.includes('ui') || lower.includes('render')) return 'M09_ui_evolution';
    if (lower.includes('file') || lower.includes('write')) return 'M04_unified_executor';
    return 'M04_unified_executor';
  }

  /**
   * Sample demands from asset degradation data
   * Source: NightlyDistiller Stage 4 output in the project-local .deerflow/upgrade-center/state directory.
   *
   * MINIMUM CLOSED LOOP: NightlyDistiller (Python) → Stage4 JSON → here
   * Falls back to sample data if file missing (degraded mode, clearly labeled).
   */
  public async sampleFromAssetDegradation(): Promise<UpgradeDemand[]> {
    console.log('[DemandSampler] Sampling from asset degradation...');

    const demands: UpgradeDemand[] = [];
    const stateDir = runtimePath('upgrade-center', 'state');
    const assetPath = path.join(stateDir, 'nightly_review_stage4_assets.json');

    // Try to load real Stage4 asset data from NightlyDistiller
    let realDataFound = false;
    if (fs.existsSync(assetPath)) {
      try {
        const raw = fs.readFileSync(assetPath, 'utf-8');
        const data = JSON.parse(raw);
        const stage4: Stage4AssetChanges = data;

        // Generate demands from FIX candidates
        const fixCandidates = stage4.fixed_assets || [];
        for (const assetId of fixCandidates) {
          demands.push({
            id: `demand-${Date.now()}-asset-fix-${assetId.replace(/[^a-zA-Z0-9]/g, '-')}`,
            source: 'asset_degradation',
            description: `资产修复需求 [${assetId}] — 来自 NightlyDistiller Stage4 FIX 候选`,
            related_module: this.inferModuleFromAssetId(assetId),
            detected_at: new Date().toISOString(),
            asset_data: stage4,
          });
        }

        // Generate demands from new candidate assets needing review
        const newCandidates = stage4.new_candidates || [];
        for (const assetId of newCandidates) {
          demands.push({
            id: `demand-${Date.now()}-asset-new-${assetId.replace(/[^a-zA-Z0-9]/g, '-')}`,
            source: 'asset_degradation',
            description: `新资产候选 [${assetId}] — 需要评审是否纳入观察池`,
            related_module: 'M07_asset_manager',
            detected_at: new Date().toISOString(),
            asset_data: stage4,
          });
        }

        if (demands.length > 0 || fixCandidates.length > 0 || newCandidates.length > 0) {
          realDataFound = true;
          console.log(`[DemandSampler] Found ${demands.length} real asset degradation demands from Stage4`);
        }

        // R167 FIX: Empty Stage4 is NORMAL when system is healthy — NOT degraded mode.
        // When file exists and is valid but all arrays are empty, emit a real demand
        // instead of falling back to sample data.
        if (demands.length === 0 && realDataFound) {
          demands.push({
            id: `demand-${Date.now()}-asset-healthy`,
            source: 'asset_degradation',
            description: '[NightlyDistiller] 资产状态正常，无显著变更',
            related_module: 'M07_asset_manager',
            detected_at: new Date().toISOString(),
            asset_data: stage4,
            capability_gain: ['asset_tracking', 'registry_maintenance'],
          });
          console.log(`[DemandSampler] R167: emitted demand for healthy-system Stage4 result`);
        }
      } catch (err) {
        console.warn(`[DemandSampler] Failed to read Stage4 asset data: ${err}`);
      }

      // R167 FIX: File exists and is valid — mark realDataFound=true even if empty.
      // Empty Stage4 is NORMAL when system is healthy, NOT degraded mode.
      // This ensures we never fall back to sample data when the file is present.
      realDataFound = true;
    }

    // Fallback: sample data (degraded mode — only when file truly does not exist)
    if (!realDataFound) {
      console.log('[DemandSampler] WARNING: Stage4 file does not exist — using SAMPLE asset degradation data (degraded mode)');
      const sampleDemand: UpgradeDemand = {
        id: `demand-${Date.now()}-asset-001`,
        source: 'asset_degradation',
        description: 'Asset degraded - needs replacement or fix',
        related_module: 'M06_L1_working_memory',
        detected_at: new Date().toISOString(),
        asset_data: this.getSampleAssetData(),
      };
      demands.push(sampleDemand);
    }

    console.log(`[DemandSampler] Asset degradation demands: ${demands.length}`);
    return demands;
  }

  /**
   * Infer module from asset ID (best-effort)
   */
  private inferModuleFromAssetId(assetId: string): string {
    const lower = assetId.toLowerCase();
    if (lower.includes('memory') || lower.includes('working')) return 'M05_memory_l1';
    if (lower.includes('asset')) return 'M07_asset_manager';
    if (lower.includes('search')) return 'M04_unified_executor';
    if (lower.includes('ui') || lower.includes('render')) return 'M09_ui_evolution';
    return 'M07_asset_manager';
  }

  /**
   * Sample demands from governance outcome records written by Python UEF evolve() / drift_check()
   *
   * MINIMUM CLOSED LOOP: Python governance_bridge._outcome_records → governance_state.json → here
   *
   * Supported outcome_types:
   * - nightly_evolution: extracts evolution_summary.next_actions[]
   * - doctrine_drift_detected: extracts drift_signals[] with action=evolve_doctrine_pending
   *
   * Falls back to [] if governance_state.json does not exist or cannot be parsed.
   * This preserves the existing mock/sample paths and only adds a real data channel.
   */
  public async sampleFromGovernanceState(): Promise<UpgradeDemand[]> {
    console.log('[DemandSampler] Sampling from governance_state.json outcome records...');

    const demands: UpgradeDemand[] = [];
    const statePath = this.getGovernanceStatePath();

    let records: any[] = [];
    let state: any = null;
    try {
      if (fs.existsSync(statePath)) {
        const raw = fs.readFileSync(statePath, 'utf-8');
        state = JSON.parse(raw);
        records = Array.isArray(state.outcome_records) ? state.outcome_records : [];
        console.log(`[DemandSampler] Read ${records.length} outcome records from governance_state.json`);
      } else {
        console.log('[DemandSampler] governance_state.json not found — skipping governance source (fallback)');
        return demands;
      }
    } catch (err) {
      console.warn(`[DemandSampler] Failed to read governance_state.json: ${err} — skipping governance source`);
      return demands;
    }

    // Only consider recent records (last 7 days) to avoid stale demands
    const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;

    for (const record of records) {
      try {
        const ts = record.timestamp ? new Date(record.timestamp).getTime() : 0;
        if (ts < sevenDaysAgo) continue;

        if (record.outcome_type === 'nightly_evolution') {
          const ctx = record.context || {};

          // R162 FIX: Parse embedded stage2_data / stage4_data from R161 Python fix.
          // This打通s the NightlyDistiller→governance→TS consumption chain:
          // Python evolve() now embeds real Stage2/4 data in context.
          const stage2Data = ctx.stage2_data;
          const stage4Data = ctx.stage4_data;

          if (stage2Data && typeof stage2Data === 'object') {
            // Generate demands from real bottleneck evidence
            const priorities = stage2Data.improvement_priorities || [];
            const hasSlowTasks = (stage2Data.slowest_tasks || []).some((t: any) => t.duration_ms > 1000);
            const hasFailedTools = (stage2Data.most_failed_tools || []).some((t: any) => t.failure_count >= 2);
            const hasHighToken = (stage2Data.highest_token_steps || []).some((t: any) => t.tokens > 5000);

            const bottleneckCapabilityGain: string[] = [];
            if (hasSlowTasks) bottleneckCapabilityGain.push('execution_efficiency', 'performance');
            if (hasFailedTools) bottleneckCapabilityGain.push('reliability', 'fault_tolerance');
            if (hasHighToken) bottleneckCapabilityGain.push('token_efficiency');

            for (const item of priorities) {
              if (item.priority !== 'high') continue;
              demands.push({
                id: `demand-${Date.now()}-stage2-bottleneck-${item.item.replace(/[^a-zA-Z0-9]/g, '-')}`,
                source: 'governance_nightly_evolution',
                description: item.item,
                related_module: this.inferModuleFromBottleneckItem(item.item),
                detected_at: record.timestamp || new Date().toISOString(),
                capability_gain: [...bottleneckCapabilityGain],
              });
            }

            const failedTools = stage2Data.most_failed_tools || [];
            for (const ft of failedTools.slice(0, 3)) {
              if (ft.failure_count < 2) continue;
              demands.push({
                id: `demand-${Date.now()}-stage2-failed-tool-${ft.tool.replace(/[^a-zA-Z0-9]/g, '-')}`,
                source: 'governance_nightly_evolution',
                description: `高频失败工具 [${ft.tool}] 需要可靠性增强 (失败次数: ${ft.failure_count})`,
                related_module: this.inferModuleFromTool(ft.tool),
                detected_at: record.timestamp || new Date().toISOString(),
                capability_gain: ['reliability', 'fault_tolerance', 'tool_reliability'],
              });
            }
          }

          if (stage4Data && typeof stage4Data === 'object') {
            // Generate demands from real asset evidence
            const fixCandidates = stage4Data.fixed_assets || [];
            for (const assetId of fixCandidates) {
              demands.push({
                id: `demand-${Date.now()}-stage4-fix-${assetId.replace(/[^a-zA-Z0-9]/g, '-')}`,
                source: 'governance_nightly_evolution',
                description: `资产修复需求 [${assetId}] — 来自 Stage4 FIX 候选`,
                related_module: this.inferModuleFromAssetId(assetId),
                detected_at: record.timestamp || new Date().toISOString(),
              });
            }
            const newCandidates = stage4Data.new_candidates || [];
            for (const assetId of newCandidates) {
              demands.push({
                id: `demand-${Date.now()}-stage4-new-${assetId.replace(/[^a-zA-Z0-9]/g, '-')}`,
                source: 'governance_nightly_evolution',
                description: `新资产候选 [${assetId}] — 需要评审是否纳入观察池`,
                related_module: 'asset_system',
                detected_at: record.timestamp || new Date().toISOString(),
              });
            }
          }

          // Also parse next_actions from evolution_summary (R160 original behavior)
          const summary = ctx.evolution_summary;
          const nextActions: any[] = summary?.next_actions || [];
          for (const action of nextActions) {
            if (action.type === 'no_action') continue;
            demands.push({
              id: `demand-${record.id || Date.now()}-governance-evolve-${action.type}`,
              source: 'governance_nightly_evolution',
              description: `[nightly_evolution] ${action.type}: ${action.reason || 'no reason'}`,
              related_module: this.extractModuleFromActionTarget(action.target),
              detected_at: record.timestamp || new Date().toISOString(),
              governance_data: {
                outcome_type: 'nightly_evolution',
                action_type: action.type,
                target: action.target,
                reason: action.reason,
              },
            });
          }
        }

        if (record.outcome_type === 'doctrine_drift_detected') {
          const signals: any[] = record.context?.drift_signals || [];
          for (const sig of signals) {
            demands.push({
              id: `demand-${record.id || Date.now()}-governance-drift-${sig.doctrine_id || 'unknown'}`,
              source: 'governance_doctrine_drift',
              description: `[doctrine_drift] ${sig.doctrine_id || 'unknown doctrine'}: ${sig.reason || sig.description || 'drift detected'}`,
              related_module: sig.doctrine_id?.split('_')[0] || 'governance',
              detected_at: record.timestamp || new Date().toISOString(),
              governance_data: {
                outcome_type: 'doctrine_drift_detected',
                doctrine_id: sig.doctrine_id,
                severity: sig.severity || 'medium',
                reason: sig.reason || sig.description,
              },
});
          }
        }
        // R20: Map asset_promotion outcomes from M07 bind_platform()
        if (record.outcome_type === 'asset_promotion') {
          const ctx = record.context || {};
          demands.push({
            id: `demand-${record.id || Date.now()}-governance-asset-${ctx.asset_id || 'unknown'}`,
            source: 'governance_asset_promotion',
            description: `[asset_promotion] ${ctx.asset_name || 'unknown asset'} (${ctx.asset_category || 'unknown category'})`,
            related_module: ctx.asset_category || 'asset_system',
            detected_at: record.timestamp || new Date().toISOString(),
            governance_data: {
              outcome_type: 'asset_promotion',
              asset_id: ctx.asset_id,
              asset_name: ctx.asset_name,
              asset_category: ctx.asset_category,
              risk_level: ctx.risk_level || 'medium',
            },
          });
        }
        // R197: Consume upgrade_center_approval records from governance_state.
        // U6 per-candidate decisions carry ROI signals (tier, LTV, ltv_bonus, leniency)
        // that should inform downstream governance demand generation.
        // Generate a governance demand for each candidate that requires approval,
        // so governance can track U6 approval state and route to pending_approval pool.
        if (record.outcome_type === 'upgrade_center_approval') {
          const ctx = record.context || {};
          const candidateId = ctx.candidate_id || 'unknown';
          const tier = ctx.tier || 'T1';
          const ltv = ctx.long_term_value || 0;
          const ltvBonus = ctx.ltv_bonus;
          const leniency = ctx.leniency || 'normal';
          const canProceed = ctx.can_proceed_to_experiment ?? false;
          const requiresApproval = ctx.requires_approval ?? false;
          const riskLevel = ctx.risk_level || 'medium';
          const roiLeniency = ctx.roi_leniency_applied ?? false;

          // R197: Only generate demand when approval is required.
          // Candidates with can_proceed=True + requires_approval=True need Feishu sign-off
          // before entering experiment pool — governance should see this pending state.
          if (requiresApproval) {
            demands.push({
              id: `demand-${Date.now()}-uc-approval-${candidateId.replace(/[^a-zA-Z0-9]/g, '-')}`,
              source: 'governance_upgrade_center_approval',
              description: `[upgrade_center_approval] ${tier} candidate pending Feishu approval: ltv=${ltv}, ltv_bonus=${ltvBonus}, leniency=${leniency}, risk=${riskLevel}`,
              related_module: 'M07_asset_manager',
              detected_at: record.timestamp || new Date().toISOString(),
              governance_priority: 'pending_approval',
              capability_gain: ['governance_observability', 'approval_tracking', 'roi_feedback'],
              governance_data: {
                outcome_type: 'upgrade_center_approval',
                candidate_id: candidateId,
                tier,
                long_term_value: ltv,
                ltv_bonus: ltvBonus,
                leniency,
                can_proceed_to_experiment: canProceed,
                requires_approval: requiresApproval,
                risk_level: riskLevel,
                roi_leniency_applied: roiLeniency,
                // R197: LTV-based leniency guidance for governance reviewer
                governance_guidance: ltv >= 12 ? 'lenient_approved' : ltv >= 8 ? 'normal_review' : 'tighten_denied',
              },
            });
            console.log(`[DemandSampler] R197: Generated upgrade_center_approval demand for ${candidateId} (tier=${tier}, ltv=${ltv}, leniency=${leniency})`);
          }
        }
        // R199: Consume upgrade_center_approval_result to drive state migration.
        // After Feishu approval, the candidate must transition:
        //   approved  → experiment_ready demand (→ UC Runner enqueues to experiment_pool)
        //   rejected  → rejected_approval demand (→ UC Runner registers for cooldown)
        //   observe   → observation_pool demand (→ passive tracking, no execution)
        //
        // Data path differs by governance_state section:
        //   outcome_records: flat structure — record.context.{candidate_id,result,approver_open_id,source}
        //   decisions:    nested structure — record.context.context.{candidate_id,result,...}
        if (record.outcome_type === 'upgrade_center_approval_result') {
          const ctx = record.context || {};
          const innerCtx = ctx.context || {};
          const candidateId = ctx.candidate_id || innerCtx.candidate_id || 'unknown';
          const result = ctx.result || innerCtx.result || 'unknown';
          const approverOpenId = ctx.approver_open_id || innerCtx.approver_open_id || 'unknown';
          const source = ctx.source || innerCtx.source || 'feishu_approval';

          if (result === 'approved') {
            demands.push({
              id: `demand-${Date.now()}-uc-result-approved-${candidateId.replace(/[^a-zA-Z0-9]/g, '-')}`,
              source: 'governance_upgrade_center_approval_result',
              description: `[approval_approved] ${candidateId} approved by Feishu — ready for experiment enqueue`,
              related_module: 'M07_asset_manager',
              detected_at: record.timestamp || new Date().toISOString(),
              governance_priority: 'experiment_ready',
              capability_gain: ['governance_observability', 'approval闭环', 'experiment_trigger'],
              governance_data: {
                outcome_type: 'upgrade_center_approval_result',
                candidate_id: candidateId,
                result,
                approver_open_id: approverOpenId,
                source,
                governance_guidance: 'enqueue_to_experiment',
              },
            });
            console.log(`[DemandSampler] R199: Generated experiment_ready demand for approved candidate ${candidateId}`);
          } else if (result === 'rejected') {
            demands.push({
              id: `demand-${Date.now()}-uc-result-rejected-${candidateId.replace(/[^a-zA-Z0-9]/g, '-')}`,
              source: 'governance_upgrade_center_approval_result',
              description: `[approval_rejected] ${candidateId} rejected by Feishu — entering cooldown`,
              related_module: 'M07_asset_manager',
              detected_at: record.timestamp || new Date().toISOString(),
              governance_priority: 'rejected_approval',
              capability_gain: ['governance_observability', 'cooldown_enforcement'],
              governance_data: {
                outcome_type: 'upgrade_center_approval_result',
                candidate_id: candidateId,
                result,
                approver_open_id: approverOpenId,
                source,
                governance_guidance: 'register_cooldown',
              },
            });
            console.log(`[DemandSampler] R199: Generated rejected_approval demand for rejected candidate ${candidateId}`);
          } else {
            demands.push({
              id: `demand-${Date.now()}-uc-result-observe-${candidateId.replace(/[^a-zA-Z0-9]/g, '-')}`,
              source: 'governance_upgrade_center_approval_result',
              description: `[approval_observed] ${candidateId} moved to observation pool by Feishu`,
              related_module: 'M07_asset_manager',
              detected_at: record.timestamp || new Date().toISOString(),
              governance_priority: 'observation_pool',
              capability_gain: ['governance_observability'],
              governance_data: {
                outcome_type: 'upgrade_center_approval_result',
                candidate_id: candidateId,
                result,
                approver_open_id: approverOpenId,
                source,
                governance_guidance: 'add_to_observation',
              },
            });
            console.log(`[DemandSampler] R199: Generated observation_pool demand for observed candidate ${candidateId}`);
          }
        }
      } catch (err) {
        console.warn(`[DemandSampler] Failed to process governance record: ${err}`);
      }
    }

    // R169 FIX: Scan decisions array for asset_promotion signals.
    // Asset_promotion decisions are written by check_meta_governance() (layer=meta_governance)
    // with context.decision_type="asset_promotion" — NOT outcome_type.
    // Check BOTH fields to be safe: decision_type (meta_governance) or outcome_type (outcome_record).
    const decisions: any[] = (state as any).decisions || [];
    if (decisions.length > 0) {
      console.log(`[DemandSampler] R169: Scanning ${decisions.length} governance decisions for Path B signals...`);
      for (const decision of decisions) {
        const outcomeType = decision.context?.outcome_type || decision.context?.decision_type;
        const timestamp = decision.timestamp || '';

        // R169: Filter by 7-day window on decisions too
        const ts = timestamp ? new Date(timestamp).getTime() : 0;
        if (ts < sevenDaysAgo) continue;

        if (outcomeType === 'asset_promotion') {
          const ctx = decision.context || {};
          // asset_promotion context has: asset_id, asset_name, asset_category, risk_level, source
          const assetId = ctx.asset_id || 'unknown';
          const assetName = ctx.asset_name || 'unknown';
          const assetCategory = ctx.asset_category || 'asset_system';
          const riskLevel = ctx.risk_level || 'medium';
          const assetSource = ctx.source || ctx.asset_source || 'm07_bind_platform';
          // R170 FIX: asset_promotion is an observation signal, not an upgrade directive.
          // Set governance_priority='observation_pool' so U2 can route it appropriately
          // instead of routing it to deep_analysis_pool via immutable-zone bypass.
          demands.push({
            id: `demand-${Date.now()}-governance-decision-asset-${assetId.replace(/[^a-zA-Z0-9]/g, '-')}`,
            source: 'governance_asset_promotion',
            description: `[asset_promotion/decision] ${assetName} (${assetCategory})`,
            related_module: assetCategory === 'tool_execution' ? this.inferModuleFromTool(assetSource) : assetCategory,
            detected_at: timestamp || new Date().toISOString(),
            governance_priority: 'observation_pool',
            capability_gain: ['asset_discovery', 'platform_binding', 'registry_enrichment'],
            governance_data: {
              outcome_type: 'asset_promotion',
              decision_id: decision.decision_id,
              asset_id: assetId,
              asset_name: assetName,
              asset_category: assetCategory,
              risk_level: riskLevel,
              asset_source: assetSource,
            },
          });
          console.log(`[DemandSampler] R169: Generated asset_promotion demand from governance decision (asset=${assetName})`);
        }
      }
    }

    console.log(`[DemandSampler] Generated ${demands.length} governance-based demands`);
    return demands;
  }

  /**
   * Extract a module name string from an action target (e.g. "search" from "web_search")
   */
  private extractModuleFromActionTarget(target: string | null | undefined): string {
    if (!target) return 'unknown';
    // e.g. "web_search" → "M04_search"; "claude_code_adapter" → "M09_claude_code_adapter"
    const known = ['search', 'asset_manager', 'roi_engine', 'shadow_tester', 'claude_code', 'midscene'];
    for (const k of known) {
      if (target.includes(k)) return `M??_${k}`;
    }
    return target.length > 20 ? target.substring(0, 20) : target;
  }

  /**
   * Merge demands from multiple sources
   */
  public mergeDemands(demandArrays: UpgradeDemand[][]): UpgradeDemandPool {
    const allDemands: UpgradeDemand[] = [];

    for (const demands of demandArrays) {
      allDemands.push(...demands);
    }

    // Deduplicate by ID
    // R206-B fix: when a duplicate ID is found, prefer the version with governance_priority
    // (newer governance-based demands may have governance_priority set, older ones don't)
    const seen = new Map<string, UpgradeDemand>();
    for (const d of allDemands) {
      const existing = seen.get(d.id);
      if (!existing) {
        seen.set(d.id, d);
      } else if (!existing.governance_priority && (d as any).governance_priority) {
        // Replace the older version with the newer one that has governance_priority
        seen.set(d.id, d);
      }
    }
    const uniqueDemands = Array.from(seen.values());

    console.log(`[DemandSampler] Merged ${allDemands.length} demands, ${uniqueDemands.length} unique`);

    return {
      date: new Date().toISOString().split('T')[0],
      demands: uniqueDemands,
    };
  }

  /**
   * Generate sample bottleneck data for demonstration
   */
  private getSampleBottleneckData(): Stage2Bottlenecks {
    return {
      slowest_tasks: [
        { task: 'Complex search query', duration_ms: 15000 },
        { task: 'Multi-step workflow', duration_ms: 12000 },
      ],
      most_failed_tools: [
        { tool: 'web_search', failure_count: 5 },
        { tool: 'file_write', failure_count: 2 },
      ],
      highest_token_steps: [
        { step: 'LLM summarization', tokens: 8000 },
      ],
      redundant_searches: ['similar query 1', 'similar query 2'],
      improvement_priorities: [
        { item: 'Optimize search tool reliability', priority: 'high' },
        { item: 'Reduce token consumption', priority: 'medium' },
      ],
    };
  }

  /**
   * Generate sample asset data for demonstration
   */
  private getSampleAssetData(): Stage4AssetChanges {
    return {
      promotions: [
        { asset_id: 'asset-001', from_tier: 'candidate', to_tier: 'active' },
      ],
      demotions: [],
      new_candidates: ['asset-002', 'asset-003'],
      fixed_assets: [],
    };
  }
}
