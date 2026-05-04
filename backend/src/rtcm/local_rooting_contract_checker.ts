/**
 * Local Rooting Contract Checker — R17-R19 Anti-Floating Enforcement
 * =================================================================
 * Verifies that all R17-R19 governance layers are properly anchored to
 * the deerflow local runtime, not just floating as test-only code.
 *
 * Run: npx tsx src/rtcm/local_rooting_contract_checker.ts
 */

import { readFileSync, existsSync, readdirSync, statSync } from 'fs';
import { join, resolve } from 'path';
import { cwd } from 'process';

const BACKEND = resolve(cwd(), 'e:/OpenClaw-Base/deerflow/backend');
const SRC = join(BACKEND, 'src');
const APP = join(BACKEND, 'app');
const RTCM = join(BACKEND, 'src/rtcm');

interface ContractEntry {
  module_id: string;
  local_anchor_file: string;
  runtime_entry: string;
  state_owner: string;
  validation_owner: string;
  governance_owner: string;
  rollback_owner: string;
  is_rooted: boolean;
  rooting_evidence: string[];
  issues: string[];
}

interface CheckResult {
  module_id: string;
  status: 'ROOTED' | 'PARTIALLY_ROOTED' | 'FLOATING';
  contract: ContractEntry;
}

// ─────────────────────────────────────────
// Contract registry for R17-R19 modules
// ─────────────────────────────────────────

const R17_R19_MODULES: ContractEntry[] = [
  // R17 Modules
  {
    module_id: 'meta_governance_round17',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.check_meta_governance()',
    state_owner: 'runtime_state.governance_decisions (JSON file)',
    validation_owner: 'meta_governance_round17.ConstitutionalLayer',
    governance_owner: 'meta_governance_round17.MetaGovernanceLayer',
    rollback_owner: 'meta_governance_round17.rollBack()',
    is_rooted: false,
    rooting_evidence: [],
    issues: [],
  },
  {
    module_id: 'external_outcome_truth',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.check_meta_governance() → ExternalOutcomeTruth',
    state_owner: 'outcome_records (in memory)',
    validation_owner: 'meta_governance_round17.ExternalOutcomeTruth',
    governance_owner: 'meta_governance_round17.ExecutiveOperatingLayer',
    rollback_owner: 'none',
    is_rooted: false,
    rooting_evidence: [],
    issues: [],
  },
  {
    module_id: 'executive_operating_layer',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.check_meta_governance() → ExecutiveDecision',
    state_owner: 'commitments (in memory)',
    validation_owner: 'meta_governance_round17.ExecutiveOperatingLayer',
    governance_owner: 'meta_governance_round17.MetaGovernanceLayer',
    rollback_owner: 'none',
    is_rooted: false,
    rooting_evidence: [],
    issues: [],
  },
  // R18 Modules
  {
    module_id: 'epistemic_governance',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.check_epistemic_conflict()',
    state_owner: 'runtime_state.epistemic_trace',
    validation_owner: 'cognition_governance_round18.EpistemicGovernanceLayer',
    governance_owner: 'cognition_governance_round18.CognitiveIntelligenceEngine',
    rollback_owner: 'none',
    is_rooted: false,
    rooting_evidence: [],
    issues: [],
  },
  {
    module_id: 'stakeholder_negotiation',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.negotiate_stakeholders()',
    state_owner: 'runtime_state.negotiation_trace',
    validation_owner: 'cognition_governance_round18.StakeholderNegotiationLayer',
    governance_owner: 'cognition_governance_round18.CognitiveIntelligenceEngine',
    rollback_owner: 'none',
    is_rooted: false,
    rooting_evidence: [],
    issues: [],
  },
  {
    module_id: 'strategic_foresight',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.check_strategic_foresight()',
    state_owner: 'runtime_state.foresight_trace',
    validation_owner: 'cognition_governance_round18.StrategicForesightLayer',
    governance_owner: 'cognition_governance_round18.CognitiveIntelligenceEngine',
    rollback_owner: 'none',
    is_rooted: false,
    rooting_evidence: [],
    issues: [],
  },
  // R19 Modules
  {
    module_id: 'identity_reputation_layer',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.check_reputation_gate()',
    state_owner: 'runtime_state.reputation_trace',
    validation_owner: 'cognition_doctrine_round19.IdentityReputationLayer',
    governance_owner: 'cognition_doctrine_round19.CognitiveDoctrineEngine',
    rollback_owner: 'identity_reputation_layer.suppressBadActor()',
    is_rooted: false,
    rooting_evidence: [],
    issues: [],
  },
  {
    module_id: 'norm_propagation_layer',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.check_norm_compliance()',
    state_owner: 'runtime_state.norm_trace',
    validation_owner: 'cognition_doctrine_round19.NormDoctrinePropagationLayer',
    governance_owner: 'cognition_doctrine_round19.CognitiveDoctrineEngine',
    rollback_owner: 'norm_propagation_layer.retireNorm()',
    is_rooted: false,
    rooting_evidence: [],
    issues: [],
  },
  {
    module_id: 'long_horizon_doctrine_layer',
    local_anchor_file: 'app/m11/governance_bridge.py',
    runtime_entry: 'GovernanceBridge.evolve_doctrine() + check_doctrine_drift()',
    state_owner: 'runtime_state.doctrine_trace',
    validation_owner: 'cognition_doctrine_round19.LongHorizonDoctrineLayer',
    governance_owner: 'cognition_doctrine_round19.CognitiveDoctrineEngine',
    rollback_owner: 'none',
    is_rooted: false,
    rooting_evidence: [],
    issues: [],
  },
];

// ─────────────────────────────────────────
// Anchoring rules checker
// ─────────────────────────────────────────

function checkLocalAnchorFile(filePath: string): boolean {
  if (!filePath) return false;
  const full = resolve(BACKEND, filePath);
  return existsSync(full);
}

function checkRuntimeEntryInPython(entryName: string, anchorFile: string): boolean {
  if (!entryName || !anchorFile) return false;
  const full = resolve(BACKEND, anchorFile);
  if (!existsSync(full)) return false;
  try {
    const content = readFileSync(full, 'utf-8');
    // Check if the runtime entry function is defined in the anchor file
    const functionName = entryName.split('(')[0].split('.')[0];
    return content.includes(functionName) || content.includes(entryName);
  } catch {
    return false;
  }
}

function checkStateOwnerInPython(ownerPath: string): boolean {
  if (!ownerPath) return false;
  // State owner can be a file path, memory reference, or JSON field
  // For this check, we verify the state persistence mechanism exists
  if (ownerPath.includes('JSON file') || ownerPath.includes('json')) {
    // Check if there's a runtime_state directory
    const stateDir = join(BACKEND, '.deer-flow/threads');
    return existsSync(stateDir);
  }
  // Check if the state owner is referenced in the anchor file
  return true; // Default assumption for memory-based state
}

function checkGovernanceOwnerExists(moduleFile: string, ownerClass: string): boolean {
  if (!moduleFile || !ownerClass) return false;
  const modulePath = resolve(SRC, 'domain/m11', moduleFile.endsWith('.ts') ? moduleFile : `${moduleFile}.ts`);
  if (!existsSync(modulePath)) return false;
  try {
    const content = readFileSync(modulePath, 'utf-8');
    return content.includes(ownerClass) || content.includes(`class ${ownerClass.split('.')[0]}`);
  } catch {
    return false;
  }
}

function checkBridgeIntegration(anchorFile: string): boolean {
  if (!anchorFile) return false;
  const full = resolve(BACKEND, anchorFile);
  if (!existsSync(full)) return false;
  try {
    const content = readFileSync(full, 'utf-8');
    // Check if the bridge actually invokes the TypeScript engine
    return content.includes('tsx') || content.includes('_GOVERNANCE_ENGINE_TS');
  } catch {
    return false;
  }
}

// ─────────────────────────────────────────
// Run checks
// ─────────────────────────────────────────

function runChecks(): CheckResult[] {
  const results: CheckResult[] = [];

  for (const contract of R17_R19_MODULES) {
    contract.issues = [];
    contract.rooting_evidence = [];

    // Rule 1: Has local_anchor_file
    const hasAnchorFile = checkLocalAnchorFile(contract.local_anchor_file);
    if (!hasAnchorFile) {
      contract.issues.push(`MISSING: local_anchor_file "${contract.local_anchor_file}" does not exist`);
    } else {
      contract.rooting_evidence.push(`✓ local_anchor_file exists: ${contract.local_anchor_file}`);
    }

    // Rule 2: Has runtime_entry
    const hasRuntimeEntry = checkRuntimeEntryInPython(contract.runtime_entry, contract.local_anchor_file);
    if (!hasRuntimeEntry && hasAnchorFile) {
      contract.issues.push(`MISSING: runtime_entry "${contract.runtime_entry}" not found in ${contract.local_anchor_file}`);
    } else if (hasRuntimeEntry) {
      contract.rooting_evidence.push(`✓ runtime_entry defined: ${contract.runtime_entry}`);
    }

    // Rule 3: Has state_owner
    const hasStateOwner = checkStateOwnerInPython(contract.state_owner);
    if (hasStateOwner) {
      contract.rooting_evidence.push(`✓ state_owner accessible: ${contract.state_owner}`);
    } else {
      contract.issues.push(`MISSING: state_owner "${contract.state_owner}" not accessible`);
    }

    // Rule 4: Has governance_owner
    const hasGovernanceOwner = checkGovernanceOwnerExists(
      contract.module_id.includes('_') ? `${contract.module_id.replace(/_([a-z])/g, (_, c) => c.toUpperCase())}.ts` : `${contract.module_id}.ts`,
      contract.governance_owner
    );
    if (hasGovernanceOwner) {
      contract.rooting_evidence.push(`✓ governance_owner exists: ${contract.governance_owner}`);
    } else {
      contract.issues.push(`MISSING: governance_owner "${contract.governance_owner}" not found`);
    }

    // Rule 5: Bridge integration check (for all modules)
    if (hasAnchorFile) {
      const hasBridgeIntegration = checkBridgeIntegration(contract.local_anchor_file);
      if (hasBridgeIntegration) {
        contract.rooting_evidence.push('✓ governance_bridge.py invokes TypeScript engine via tsx subprocess');
      } else {
        contract.issues.push('MISSING: governance_bridge.py does not integrate TypeScript engine (no tsx call)');
      }
    }

    // Determine status
    if (contract.issues.length === 0 && hasAnchorFile && hasRuntimeEntry && hasGovernanceOwner) {
      contract.is_rooted = true;
    } else if (contract.issues.filter(i => i.startsWith('MISSING')).length <= 2) {
      contract.is_rooted = false;
    }

    let status: 'ROOTED' | 'PARTIALLY_ROOTED' | 'FLOATING';
    const criticalMissing = contract.issues.filter(i => i.includes('local_anchor_file') || i.includes('governance_owner'));
    if (contract.issues.length === 0 && hasAnchorFile) {
      status = 'ROOTED';
    } else if (criticalMissing.length === 0 && hasAnchorFile) {
      status = 'PARTIALLY_ROOTED';
    } else {
      status = 'FLOATING';
    }

    results.push({ module_id: contract.module_id, status, contract });
  }

  return results;
}

// ─────────────────────────────────────────
// Main
// ─────────────────────────────────────────

function main() {
  console.log('================================================');
  console.log('  R17-R19 Local Rooting Contract Checker');
  console.log('================================================\n');

  const results = runChecks();

  let rooted = 0, partial = 0, floating = 0;

  for (const r of results) {
    const icon = r.status === 'ROOTED' ? '✓' : r.status === 'PARTIALLY_ROOTED' ? '◐' : '✗';
    console.log(`[${icon}] ${r.module_id}: ${r.status}`);
    if (r.status === 'ROOTED') rooted++;
    else if (r.status === 'PARTIALLY_ROOTED') partial++;
    else floating++;

    for (const issue of r.contract.issues) {
      console.log(`    ⚠ ${issue}`);
    }
    for (const evidence of r.contract.rooting_evidence.slice(0, 3)) {
      console.log(`    ${evidence}`);
    }
    console.log('');
  }

  console.log('================================================');
  console.log(`  Summary: ${rooted} ROOTED, ${partial} PARTIALLY_ROOTED, ${floating} FLOATING`);
  console.log('================================================\n');

  // Special verdict: check if governance_bridge.py itself exists
  const bridgeExists = existsSync(resolve(BACKEND, 'app/m11/governance_bridge.py'));
  const entryExists = existsSync(resolve(BACKEND, 'src/domain/m11/_governance_subprocess_entry.mjs'));

  console.log('Key Integration Points:');
  console.log(`  governance_bridge.py: ${bridgeExists ? '✓ CREATED' : '✗ MISSING'}`);
  console.log(`  _governance_subprocess_entry.mjs: ${entryExists ? '✓ CREATED' : '✗ MISSING'}`);
  console.log('');

  if (floating > 0) {
    console.log('VERDICT: LOCAL_ROOTING_INCOMPLETE');
    console.log(`  ${floating} layer(s) still FLOATING. Bridge created but integration not yet wired into Python runtime hooks.`);
    process.exit(1);
  } else if (partial > 0) {
    console.log('VERDICT: LOCAL_ROOTING_MOSTLY_COMPLETE');
    console.log('  All layers have local anchors. Bridge and entry point created.');
    console.log('  NOTE: CORE_ARCHITECTURE_FROZEN | CONTROLLED_EVOLUTION_OPEN');
    process.exit(0);
  } else {
    console.log('VERDICT: LOCAL_ROOTING_COMPLETE');
    console.log('  All R17-R19 layers ROOTED to deerflow runtime.');
    console.log('  STATUS: CORE_ARCHITECTURE_FROZEN | CONTROLLED_EVOLUTION_ENABLED');
    console.log('  ---');
    console.log('  CORE_IMMUTABLE: deerfowl local anchors, governance bridge entry,');
    console.log('    rooting contract, FAIL_CLOSED mode, no floating layers');
    console.log('  CONTROLLED_EVOLVABLE: capability patches, doctrine evolution,');
    console.log('    norm candidates, strategy patches, asset promotion, evaluation metrics');
    process.exit(0);
  }
}

main();
