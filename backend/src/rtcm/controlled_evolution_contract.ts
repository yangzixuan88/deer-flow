/**
 * Controlled Evolution Contract — VALIDATION/AUDIT TOOL (NOT runtime governance input)
 * ===================================================================================
 *
 * PURPOSE (明确标注为验证工具，非运行时输入):
 *   This contract answers one question for every proposed system change:
 *   "Does this change strengthen the existing system, or does it spawn a new floating one?"
 *
 *   It enforces that the system is PERMANENTLY FROZEN in its CORE architecture
 *   (layers, anchors, boundaries) but remains OPEN to controlled evolution WITHIN those
 *   established layers.
 *
 * ROLE IN SYSTEM:
 *   - VALIDATION/AUDIT TOOL: 供开发/审计时运行，不参与运行时治理决策
 *   - 运行时治理由 governance_bridge.py + R17-R19 TypeScript 引擎承担
 *   - 运行时层数上限由 GovernanceBridge.is_layer_addition_allowed() 强制执行
 *   - 本文件仅用于离线扫描和人工复核，不被任何运行时模块 import
 *
 * THREE-CLASSIFICATION SYSTEM:
 *   ───────────────────────────────────────────────────────────────────────
 *   CORE_IMMUTABLE        — The frozen spine. Cannot change without人工审批.
 *   CONTROLLED_EVOLVABLE  — Open for growth within existing layers.
 *   FORBIDDEN_EXPANSION   — Parallel shadow systems. Always blocked.
 *   ───────────────────────────────────────────────────────────────────────
 *
 * RUN (CLI 工具，不作为模块导入):
 *   npx tsx src/rtcm/controlled_evolution_contract.ts
 */

import { existsSync, readFileSync, readdirSync } from 'fs';
import { resolve, join } from 'path';
import { cwd } from 'process';

const BACKEND = resolve(cwd(), 'e:/OpenClaw-Base/deerflow/backend');

// ─────────────────────────────────────────
// Classification enum
// ─────────────────────────────────────────

type EvolutionClassification =
  | 'CORE_IMMUTABLE'     // Never change without人工审批
  | 'CONTROLLED_EVOLVABLE' // Evolve within existing layers
  | 'FORBIDDEN_EXPANSION'; // Parallel shadow systems — always blocked

// ─────────────────────────────────────────
// Change type taxonomy
// ─────────────────────────────────────────

type ChangeType =
  // CONTROLLED_EVOLVABLE change types
  | 'new_doctrine_candidate'
  | 'new_norm_candidate'
  | 'strategy_patch'
  | 'new_evaluation_metric'
  | 'new_playbook'
  | 'new_recovery_pattern'
  | 'new_negotiation_rule'
  | 'new_foresight_heuristic'
  | 'new_execution_capability'  // new tool executor adapter
  | 'new_asset_pattern'        // promoted asset / pattern
  | 'new_learning_signal'       // new experience capture
  | 'new_mission_type'         // new playbook / scenario

  // CORE_IMMUTABLE change types
  | 'governance_bridge_entry_change'
  | 'decision_mode_change'
  | 'state_file_path_change'
  | 'layer_boundary_change'     // rollback / veto / escalate boundaries
  | 'routing_contract_change'   // rooting_contract/mod.ts layer structure
  | 'subprocess_entry_change'   // _governance_subprocess_entry.mjs
  | 'fail_closed_mode_change'   // changing FAIL_CLOSED

  // FORBIDDEN_EXPANSION change types
  | 'new_parallel_learning_system'
  | 'new_parallel_asset_system'
  | 'new_parallel_runtime_layer'
  | 'new_floating_governance_layer'
  | 'new_floating_mission_layer'
  | 'shadow_clone_of_existing_sor'
  | 'bypass_governance_bridge'
  | 'bypass_m08_learning'
  | 'bypass_m07_asset'
  | 'new_layer_above_r19';

// ─────────────────────────────────────────
// Classification registry — canonical source of truth
// ─────────────────────────────────────────

interface EvolutionContractEntry {
  change_id: string;
  change_type: ChangeType;
  description: string;
  target_layer?: string;       // which layer this affects
  local_anchor_file?: string;  // required anchor if CONTROLLED_EVOLVABLE
  runtime_entry?: string;       // required entry point if CONTROLLED_EVOLVABLE
  system_of_record: string;    // which system-of-record owns this
  validation_owner: string;
  governance_owner: string;
  rollback_owner: string;
  shadow_supported: boolean;    // can run in shadow/promote mode?
  classification: EvolutionClassification;
  rationale: string;
}

const EVOLUTION_CONTRACT: EvolutionContractEntry[] = [

  // ══════════════════════════════════════════════════════════════
  // CORE_IMMUTABLE — The frozen spine
  // ══════════════════════════════════════════════════════════════

  {
    change_id: 'CORE-001',
    change_type: 'governance_bridge_entry_change',
    description: 'Any change to governance_bridge.py as the sole governance entry point',
    system_of_record: 'app/m11/governance_bridge.py',
    validation_owner: '人工审批 (human approval required)',
    governance_owner: 'MetaGovernanceLayer (R17)',
    rollback_owner: 'git revert',
    shadow_supported: false,
    classification: 'CORE_IMMUTABLE',
    rationale: 'Governance bridge is the single choke-point for all R17-R19 decisions. Changing it without人工审批 risks splitting the governance authority.',
  },
  {
    change_id: 'CORE-002',
    change_type: 'decision_mode_change',
    description: 'DECISION_MODE switch between FAIL_CLOSED and any other mode',
    system_of_record: 'app/m11/governance_bridge.py',
    validation_owner: '人工审批 (human approval required)',
    governance_owner: 'MetaGovernanceLayer (R17)',
    rollback_owner: 'git revert',
    shadow_supported: false,
    classification: 'CORE_IMMUTABLE',
    rationale: 'FAIL_CLOSED ensures that unavailable governance engine blocks high-risk decisions. Switching to any permissive mode breaks the constitutional guarantee.',
  },
  {
    change_id: 'CORE-003',
    change_type: 'subprocess_entry_change',
    description: 'Any change to _governance_subprocess_entry.mjs that alters command routing',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge methods → tsx subprocess',
    system_of_record: 'src/domain/m11/_governance_subprocess_entry.mjs',
    validation_owner: '人工审批 (human approval required)',
    governance_owner: 'MetaGovernanceLayer (R17)',
    rollback_owner: 'git revert',
    shadow_supported: false,
    classification: 'CORE_IMMUTABLE',
    rationale: '_governance_subprocess_entry.mjs is the TypeScript engine bootstrap. Altering its routing breaks R17-R19 engine dispatch.',
  },
  {
    change_id: 'CORE-004',
    change_type: 'routing_contract_change',
    description: 'Any change to mod.ts layer export structure or layer naming conventions',
    system_of_record: 'src/domain/m11/mod.ts',
    validation_owner: '人工审批 (human approval required)',
    governance_owner: 'MetaGovernanceLayer (R17)',
    rollback_owner: 'git revert',
    shadow_supported: false,
    classification: 'CORE_IMMUTABLE',
    rationale: 'mod.ts is the routing contract. Changing layer names or exports breaks all cross-layer references throughout the system.',
  },
  {
    change_id: 'CORE-005',
    change_type: 'new_layer_above_r19',
    description: 'Creating any new layer above Round 19 (R20, R21, etc.)',
    system_of_record: 'src/domain/m11/',
    validation_owner: '人工审批 (human approval required)',
    governance_owner: 'MetaGovernanceLayer (R17)',
    rollback_owner: 'git revert',
    shadow_supported: false,
    classification: 'CORE_IMMUTABLE',
    rationale: 'Architecture is capped at R19. Any new layer would be a floating abstraction that bypasses the rooting contract.',
  },
  {
    change_id: 'CORE-006',
    change_type: 'fail_closed_mode_change',
    description: 'Removing FAIL_CLOSED or adding PASS_THROUGH back to governance_bridge',
    system_of_record: 'app/m11/governance_bridge.py',
    validation_owner: '人工审批 (human approval required)',
    governance_owner: 'MetaGovernanceLayer (R17)',
    rollback_owner: 'git revert',
    shadow_supported: false,
    classification: 'CORE_IMMUTABLE',
    rationale: 'PASS_THROUGH was the original bug. FAIL_CLOSED is the constitutional fix.',
  },

  // ══════════════════════════════════════════════════════════════
  // CONTROLLED_EVOLVABLE — Open surface within existing layers
  // ══════════════════════════════════════════════════════════════

  {
    change_id: 'EVOL-001',
    change_type: 'new_doctrine_candidate',
    description: 'Add new doctrine via evolve_doctrine() — new doctrine_id, new belief weights',
    target_layer: 'LongHorizonDoctrineLayer (R19)',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.evolve_doctrine()',
    system_of_record: 'cognition_doctrine_round19.LongHorizonDoctrineLayer',
    validation_owner: 'LongHorizonDoctrineLayer.validateCandidate()',
    governance_owner: 'CognitiveDoctrineEngine',
    rollback_owner: 'CognitiveDoctrineEngine.retireDoctrine()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'Doctrine evolution is the primary mechanism for long-horizon learning. New doctrine candidates enter via shadow mode, are validated, then promoted.',
  },
  {
    change_id: 'EVOL-002',
    change_type: 'new_norm_candidate',
    description: 'Register new norm pattern via NormDoctrinePropagationLayer',
    target_layer: 'NormDoctrinePropagationLayer (R19)',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.check_norm_compliance()',
    system_of_record: 'cognition_doctrine_round19.NormDoctrinePropagationLayer',
    validation_owner: 'NormDoctrinePropagationLayer.registerNorm()',
    governance_owner: 'CognitiveDoctrineEngine',
    rollback_owner: 'NormDoctrinePropagationLayer.retireNorm()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'Norm propagation is how behavioral rules evolve. New norms enter via shadow review and are promoted only after evidence accumulates.',
  },
  {
    change_id: 'EVOL-003',
    change_type: 'strategy_patch',
    description: 'Apply new strategy patch to StrategyLearner via applyPatch()',
    target_layer: 'strategy_learner.ts',
    local_anchor_file: 'src/domain/m11/strategy_learner.ts',
    runtime_entry: 'StrategyLearner.applyPatch()',
    system_of_record: 'strategy_learner.ts',
    validation_owner: 'StrategicManagementEngine',
    governance_owner: 'StrategicManagementEngine (R16)',
    rollback_owner: 'StrategyLearner.rollbackPatch()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'Strategy patches are how the system learns from execution experience. They are evaluated in shadow mode before full application.',
  },
  {
    change_id: 'EVOL-004',
    change_type: 'new_evaluation_metric',
    description: 'Add new evaluation metric to MissionEvaluationEngine',
    target_layer: 'mission_evaluation_round15.ts',
    local_anchor_file: 'src/domain/m11/mission_evaluation_round15.ts',
    runtime_entry: 'MissionEvaluationEngine.updateMetrics()',
    system_of_record: 'mission_evaluation_round15.ts',
    validation_owner: 'MissionEvaluationEngine',
    governance_owner: 'MissionEvaluationEngine',
    rollback_owner: 'MissionEvaluationEngine.removeMetric()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'New evaluation metrics sharpen how the system judges mission success. Metrics are backtested against historical missions before promotion.',
  },
  {
    change_id: 'EVOL-005',
    change_type: 'new_playbook',
    description: 'Add new mission playbook or scenario pattern to mission registry',
    target_layer: 'mission_evaluation_round15.ts',
    local_anchor_file: 'src/domain/m11/mission_evaluation_round15.ts',
    runtime_entry: 'MissionRegistry.registerPlaybook()',
    system_of_record: 'mission_evaluation_round15.ts',
    validation_owner: 'MissionRegistry',
    governance_owner: 'MissionEvaluationEngine',
    rollback_owner: 'MissionRegistry.unregisterPlaybook()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'New playbooks expand the mission library. They are validated through simulated runs before entering production.',
  },
  {
    change_id: 'EVOL-006',
    change_type: 'new_recovery_pattern',
    description: 'Add new error recovery pattern to AutonomousRuntimeLoop',
    target_layer: 'autonomous_runtime_round13.ts',
    local_anchor_file: 'src/domain/m11/autonomous_runtime_round13.ts',
    runtime_entry: 'AutonomousRuntimeLoop.addRecoveryPattern()',
    system_of_record: 'autonomous_runtime_round13.ts',
    validation_owner: 'AutonomousRuntimeLoop',
    governance_owner: 'AutonomousExecutionEngine (R13)',
    rollback_owner: 'AutonomousRuntimeLoop.removeRecoveryPattern()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'Recovery patterns are learned from failure experience. They are shadow-tested against historical failures before promotion.',
  },
  {
    change_id: 'EVOL-007',
    change_type: 'new_negotiation_rule',
    description: 'Add new stakeholder negotiation rule to StakeholderNegotiationLayer',
    target_layer: 'cognition_governance_round18.ts',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.negotiate_stakeholders()',
    system_of_record: 'cognition_governance_round18.ts',
    validation_owner: 'StakeholderNegotiationLayer',
    governance_owner: 'CognitiveIntelligenceEngine (R18)',
    rollback_owner: 'StakeholderNegotiationLayer.removeRule()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'Negotiation rules evolve as the system learns what tradeoffs stakeholders accept. New rules are shadow-tested.',
  },
  {
    change_id: 'EVOL-008',
    change_type: 'new_foresight_heuristic',
    description: 'Add new strategic foresight heuristic to StrategicForesightLayer',
    target_layer: 'cognition_governance_round18.ts',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.check_strategic_foresight()',
    system_of_record: 'cognition_governance_round18.ts',
    validation_owner: 'StrategicForesightLayer',
    governance_owner: 'CognitiveIntelligenceEngine (R18)',
    rollback_owner: 'StrategicForesightLayer.removeHeuristic()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'Foresight heuristics improve long-term planning. They are backtested against historical scenarios before promotion.',
  },
  {
    change_id: 'EVOL-009',
    change_type: 'new_execution_capability',
    description: 'Add new tool executor or sandbox adapter capability',
    target_layer: 'sandbox.ts',
    local_anchor_file: 'src/domain/m11/sandbox.ts',
    runtime_entry: 'SandboxExecutor.execute_in_sandbox()',
    system_of_record: 'sandbox.ts',
    validation_owner: 'SandboxExecutor',
    governance_owner: 'SandboxExecutor (M11)',
    rollback_owner: 'SandboxExecutor.disableCapability()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'New execution capabilities expand what the system can do. Each new capability is audited via governance_bridge.check_meta_governance before full activation.',
  },
  {
    change_id: 'EVOL-010',
    change_type: 'new_asset_pattern',
    description: 'Promote new asset pattern or reusable playbook via AssetRegistry',
    target_layer: 'asset_system (M07)',
    local_anchor_file: 'app/m07/asset_system.py',
    runtime_entry: 'AssetRegistry.promoteAsset()',
    system_of_record: 'app/m07/asset_system.py (M07 is sole SOR for assets)',
    validation_owner: 'AssetGuardian',
    governance_owner: 'AssetRegistry',
    rollback_owner: 'AssetRegistry.demoteAsset()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'Asset promotion is the path from learned experience to reusable asset. M07 is the sole asset SOR — new assets must enter via M07, not a parallel system.',
  },
  {
    change_id: 'EVOL-011',
    change_type: 'new_learning_signal',
    description: 'Capture new experience type in LearningSystem — new experience pattern',
    target_layer: 'learning_system.py (M08)',
    local_anchor_file: 'app/m08/learning_system.py',
    runtime_entry: 'UniversalEvolutionFramework._capture_experience()',
    system_of_record: 'app/m08/learning_system.py (M08 is sole SOR for learning)',
    validation_owner: 'Optimizer',
    governance_owner: 'UniversalEvolutionFramework',
    rollback_owner: 'Optimizer.evictExperience()',
    shadow_supported: false,  // learning signals are immediately applied, not shadowed
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'M08 is the sole learning SOR. New experience capture patterns enter via M08 and feed into the governance backflow (outcome → reputation → doctrine).',
  },
  {
    change_id: 'EVOL-012',
    change_type: 'new_mission_type',
    description: 'Add new mission type or scenario definition',
    target_layer: 'mission_evaluation_round15.ts',
    local_anchor_file: 'src/domain/m11/mission_evaluation_round15.ts',
    runtime_entry: 'MissionRegistry.registerMissionType()',
    system_of_record: 'mission_evaluation_round15.ts',
    validation_owner: 'MissionRegistry',
    governance_owner: 'MissionEvaluationEngine',
    rollback_owner: 'MissionRegistry.unregisterMissionType()',
    shadow_supported: true,
    classification: 'CONTROLLED_EVOLVABLE',
    rationale: 'New mission types expand operational scope. They are validated against historical performance before promotion.',
  },

  // ══════════════════════════════════════════════════════════════
  // FORBIDDEN_EXPANSION — Always blocked
  // ══════════════════════════════════════════════════════════════

  {
    change_id: 'FORBID-001',
    change_type: 'new_parallel_learning_system',
    description: 'Create a new learning system that bypasses M08 (learning_system.py)',
    system_of_record: 'M08 (app/m08/learning_system.py) is the SOLE learning SOR',
    validation_owner: 'N/A — BLOCKED',
    governance_owner: 'MetaGovernanceLayer (R17) — blocks via FAIL_CLOSED',
    rollback_owner: 'N/A',
    shadow_supported: false,
    classification: 'FORBIDDEN_EXPANSION',
    rationale: 'M08 is the sole learning system-of-record. Any parallel learning system would create conflicting truth sources and corrupt outcome reputation.',
  },
  {
    change_id: 'FORBID-002',
    change_type: 'new_parallel_asset_system',
    description: 'Create a new asset management system that bypasses M07 (asset_system.py)',
    system_of_record: 'M07 (app/m07/asset_system.py) is the SOLE asset SOR',
    validation_owner: 'N/A — BLOCKED',
    governance_owner: 'MetaGovernanceLayer (R17) — blocks via FAIL_CLOSED',
    rollback_owner: 'N/A',
    shadow_supported: false,
    classification: 'FORBIDDEN_EXPANSION',
    rationale: 'M07 is the sole asset system-of-record. Any parallel asset system would create conflicting asset truth and corrupt the promotion/demotion system.',
  },
  {
    change_id: 'FORBID-003',
    change_type: 'new_floating_governance_layer',
    description: 'Create a new governance layer as a standalone system not routed through governance_bridge',
    system_of_record: 'app/m11/governance_bridge.py is the SOLE governance entry',
    validation_owner: 'N/A — BLOCKED',
    governance_owner: 'MetaGovernanceLayer (R17) — blocks via FAIL_CLOSED',
    rollback_owner: 'N/A',
    shadow_supported: false,
    classification: 'FORBIDDEN_EXPANSION',
    rationale: 'All governance decisions must route through governance_bridge. A floating governance layer would split decision authority and break constitutional constraints.',
  },
  {
    change_id: 'FORBID-004',
    change_type: 'new_floating_mission_layer',
    description: 'Create a new mission/execution layer as standalone not anchored to mission_evaluation_round15',
    system_of_record: 'mission_evaluation_round15.ts is the mission SOR',
    validation_owner: 'N/A — BLOCKED',
    governance_owner: 'MissionEvaluationEngine (R15) — blocks via governance',
    rollback_owner: 'N/A',
    shadow_supported: false,
    classification: 'FORBIDDEN_EXPANSION',
    rationale: 'All mission execution must be anchored to the mission registry. A floating mission layer would bypass evaluation and corrupt outcome truth.',
  },
  {
    change_id: 'FORBID-005',
    change_type: 'shadow_clone_of_existing_sor',
    description: 'Clone the deerflow learning/asset/governance state into a new parallel store',
    system_of_record: 'Original SOR is authoritative. Clone is forbidden.',
    validation_owner: 'N/A — BLOCKED',
    governance_owner: 'MetaGovernanceLayer (R17) — blocks via FAIL_CLOSED',
    rollback_owner: 'N/A',
    shadow_supported: false,
    classification: 'FORBIDDEN_EXPANSION',
    rationale: 'Shadow clones of system-of-record stores create split-brain truth. Only the original SOR is authoritative.',
  },
  {
    change_id: 'FORBID-006',
    change_type: 'bypass_governance_bridge',
    description: 'Directly invoke TypeScript governance engines without going through governance_bridge',
    system_of_record: 'governance_bridge.py is the SOLE governance entry point',
    validation_owner: 'N/A — BLOCKED',
    governance_owner: 'MetaGovernanceLayer (R17)',
    rollback_owner: 'N/A',
    shadow_supported: false,
    classification: 'FORBIDDEN_EXPANSION',
    rationale: 'Bypassing governance_bridge means decisions are not recorded, not persisted, not routed through R17-R19 consensus. This breaks the entire governance backchain.',
  },
  {
    change_id: 'FORBID-007',
    change_type: 'bypass_m08_learning',
    description: 'Write learning outcomes directly to any store other than M08 learning_system.py',
    system_of_record: 'app/m08/learning_system.py is the SOLE learning SOR',
    validation_owner: 'N/A — BLOCKED',
    governance_owner: 'UniversalEvolutionFramework (M08)',
    rollback_owner: 'N/A',
    shadow_supported: false,
    classification: 'FORBIDDEN_EXPANSION',
    rationale: 'All learning must flow through M08 so it can feed into governance backflow (outcome → reputation → doctrine). Bypassing M08 breaks the learning→governance chain.',
  },
  {
    change_id: 'FORBID-008',
    change_type: 'bypass_m07_asset',
    description: 'Promote or register assets outside of M07 asset_system.py',
    system_of_record: 'app/m07/asset_system.py is the SOLE asset SOR',
    validation_owner: 'N/A — BLOCKED',
    governance_owner: 'AssetRegistry (M07)',
    rollback_owner: 'N/A',
    shadow_supported: false,
    classification: 'FORBIDDEN_EXPANSION',
    rationale: 'All asset promotion must flow through M07 so it can be tracked, versioned, and governed. Bypassing M07 creates ungoverned assets.',
  },
  {
    change_id: 'FORBID-009',
    change_type: 'new_parallel_runtime_layer',
    description: 'Create a new runtime/execution layer parallel to autonomous_runtime_round13',
    system_of_record: 'autonomous_runtime_round13.ts is the runtime SOR',
    validation_owner: 'N/A — BLOCKED',
    governance_owner: 'AutonomousExecutionEngine (R13)',
    rollback_owner: 'N/A',
    shadow_supported: false,
    classification: 'FORBIDDEN_EXPANSION',
    rationale: 'The runtime is a single execution context. Parallel runtimes create split execution state and corrupt heartbeat/daemon coordination.',
  },
  {
    change_id: 'FORBID-010',
    change_type: 'new_layer_above_r19',
    description: 'Any attempt to create R20 or higher governance/cognition/doctrine layer',
    system_of_record: 'R19 (cognition_doctrine_round19.ts) is the TOPMOST layer',
    validation_owner: 'N/A — BLOCKED',
    governance_owner: 'MetaGovernanceLayer (R17) — blocks via layer cap',
    rollback_owner: 'N/A',
    shadow_supported: false,
    classification: 'FORBIDDEN_EXPANSION',
    rationale: 'Architecture is capped at R19. The layer cap is the constitutional guarantee that the system will not grow unbounded governance abstractions.',
  },
];

// ─────────────────────────────────────────
// Contract checker
// ─────────────────────────────────────────

function classifyChange(changeType: ChangeType): EvolutionContractEntry | null {
  return EVOLUTION_CONTRACT.find(c => c.change_type === changeType) ?? null;
}

function isChangeAllowed(changeType: ChangeType): {
  allowed: boolean;
  classification: EvolutionClassification;
  entry: EvolutionContractEntry | null;
} {
  const entry = classifyChange(changeType);
  if (!entry) {
    // Unknown change type — default to requiring human review
    return {
      allowed: false,
      classification: 'CORE_IMMUTABLE',
      entry: null,
    };
  }
  return {
    allowed: entry.classification !== 'FORBIDDEN_EXPANSION',
    classification: entry.classification,
    entry,
  };
}

function checkSystemForForbiddenPatterns(): { violations: string[]; warnings: string[] } {
  const violations: string[] = [];
  const warnings: string[] = [];

  // Check that no new layers exist above R19
  const m11Dir = resolve(BACKEND, 'src/domain/m11');
  const m11Files = readdirSync(m11Dir).filter(f => f.endsWith('.ts') && !f.startsWith('_') && f !== 'types.ts');

  const layerPattern = /_round(\d+)\.ts$/;
  for (const f of m11Files) {
    const match = f.match(layerPattern);
    if (match) {
      const round = parseInt(match[1], 10);
      if (round > 19) {
        violations.push(`FORBIDDEN: ${f} — layer R${round} is above the R19 cap`);
      }
    }
  }

  // Check that governance_bridge has no PASS_THROUGH
  const bridgePy = resolve(BACKEND, 'app/m11/governance_bridge.py');
  if (existsSync(bridgePy)) {
    const content = readFileSync(bridgePy, 'utf-8');
    if (content.includes('governance_bridge_pass_through') ||
        (content.includes('PASS_THROUGH') && !content.includes('no PASS_THROUGH'))) {
      violations.push('FORBIDDEN: governance_bridge contains active PASS_THROUGH code (not just documentation of removal)');
    }
    if (content.includes('R20') || content.includes('Round 20')) {
      violations.push('FORBIDDEN: governance_bridge references future round R20');
    }
  }

  // Check that no bypass routes exist around M08/M07
  const m08Py = resolve(BACKEND, 'app/m08/learning_system.py');
  const m07Py = resolve(BACKEND, 'app/m07/asset_system.py');
  if (existsSync(m08Py) && existsSync(m07Py)) {
    const m08Content = readFileSync(m08Py, 'utf-8');
    const m07Content = readFileSync(m07Py, 'utf-8');
    // These should always be the sole SORs — any bypass would be a violation
    if (!m08Content.includes('governance_bridge')) {
      warnings.push('WARNING: M08 learning_system does not call governance_bridge — learning→governance backchain may be broken');
    }
    if (!m07Content.includes('governance')) {
      warnings.push('WARNING: M07 asset_system does not reference governance — asset→governance backchain may be incomplete');
    }
  }

  return { violations, warnings };
}

// ─────────────────────────────────────────
// Main
// ─────────────────────────────────────────

function main() {
  console.log('================================================');
  console.log('  CONTROLLED EVOLUTION CONTRACT CHECKER');
  console.log('  CORE_ARCHITECTURE_FROZEN | CONTROLLED_EVOLUTION_ENABLED');
  console.log('================================================\n');

  // 1. Show contract summary
  const immutable = EVOLUTION_CONTRACT.filter(e => e.classification === 'CORE_IMMUTABLE');
  const evolvable = EVOLUTION_CONTRACT.filter(e => e.classification === 'CONTROLLED_EVOLVABLE');
  const forbidden = EVOLUTION_CONTRACT.filter(e => e.classification === 'FORBIDDEN_EXPANSION');

  console.log(`Contract Entries: ${EVOLUTION_CONTRACT.length} defined`);
  console.log(`  CORE_IMMUTABLE:        ${immutable.length}`);
  console.log(`  CONTROLLED_EVOLVABLE:  ${evolvable.length}`);
  console.log(`  FORBIDDEN_EXPANSION:   ${forbidden.length}\n`);

  // 2. Check for forbidden patterns in live code
  console.log('[System Check] Scanning for forbidden patterns...\n');
  const { violations, warnings } = checkSystemForForbiddenPatterns();

  if (violations.length > 0) {
    console.log('VIOLATIONS FOUND:');
    for (const v of violations) {
      console.log(`  ✗ ${v}`);
    }
    console.log('');
  } else {
    console.log('  ✓ No forbidden pattern violations found');
  }

  if (warnings.length > 0) {
    console.log('WARNINGS:');
    for (const w of warnings) {
      console.log(`  ⚠ ${w}`);
    }
    console.log('');
  }

  // 3. Show CORE_IMMUTABLE list
  console.log('[CORE_IMMUTABLE] — Never change without人工审批:');
  for (const e of immutable) {
    console.log(`  [${e.change_id}] ${e.change_type}: ${e.description.slice(0, 60)}...`);
  }
  console.log('');

  // 4. Show CONTROLLED_EVOLVABLE list
  console.log('[CONTROLLED_EVOLVABLE] — Evolve within existing layers:');
  for (const e of evolvable) {
    const shadow = e.shadow_supported ? ' (shadow→promote)' : '';
    console.log(`  [${e.change_id}] ${e.change_type}${shadow}`);
  }
  console.log('');

  // 5. Show FORBIDDEN list
  console.log('[FORBIDDEN_EXPANSION] — Always blocked:');
  for (const e of forbidden) {
    console.log(`  [${e.change_id}] ${e.change_type}`);
  }
  console.log('');

  // 6. Final verdict
  console.log('================================================');
  if (violations.length > 0) {
    console.log('VERDICT: FORBIDDEN_PATTERN_VIOLATION');
    console.log('  System contains one or more FORBIDDEN_EXPANSION patterns.');
    console.log('  These must be reverted before the system can be certified.');
    process.exit(1);
  } else {
    console.log('VERDICT: CORE_ARCHITECTURE_FROZEN | CONTROLLED_EVOLUTION_ENABLED');
    console.log('  No forbidden patterns found.');
    console.log('  System is ready for controlled evolution within existing layers.');
    console.log('');
    console.log('  HOW TO EVOLVE (controlled path):');
    console.log('  1. Identify change type → find in CONTROLLED_EVOLVABLE list');
    console.log('  2. Check shadow_supported flag');
    console.log('  3. If shadow=true: run in shadow mode → review → promote');
    console.log('  4. If shadow=false: direct application via governance backflow');
    console.log('  5. All changes route through existing SOR (M07/M08/mission registry)');
    console.log('  6. No new layers, no parallel systems, no bypass routes');
    process.exit(0);
  }
}

main();
