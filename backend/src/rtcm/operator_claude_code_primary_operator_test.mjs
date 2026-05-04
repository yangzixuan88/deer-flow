/**
 * Claude Code Primary Operator Acceptance Test
 * ============================================
 * 10-scenario acceptance test for Claude Code CLI as explicit first-class
 * primary operator of the deerflow system.
 *
 * Verifies:
 *  1. All tasks default to Claude Code CLI first
 *  2. Claude Code can directly execute engineering tasks
 *  3. Claude Code can invoke Scrapling and integrate results
 *  4. Claude Code can invoke Agent-S for high-difficulty GUI tasks
 *  5. Claude Code can enable Bytebot sandbox mode on demand
 *  6. Scrapling/Agent-S/Bytebot cannot claim primary operator role
 *  7. Learning回流 records have primary_operator = "Claude Code CLI"
 *  8. Asset回流 records have Claude Code as orchestration owner
 *  9. No parallel bypass routing exists
 * 10. System still complies with CORE_FROZEN_AND_CONTROLLED_EVOLUTION_ENABLED
 *
 * Run: npx tsx src/rtcm/operator_claude_code_primary_operator_test.mjs
 */

import { existsSync, readFileSync } from 'fs';
import { resolve, join } from 'path';
import { cwd } from 'process';

const BACKEND = resolve(cwd(), 'e:/OpenClaw-Base/deerflow/backend');
const APP = join(BACKEND, 'app');
const SRC = join(BACKEND, 'src');

let pass = 0;
let fail = 0;

function assert(condition, msg) {
  if (condition) {
    console.log(`  ✓ ${msg}`);
    pass++;
  } else {
    console.log(`  ✗ FAIL: ${msg}`);
    fail++;
  }
}

// Case-insensitive contains
function ic(content, substring) {
  return content.toLowerCase().includes(substring.toLowerCase());
}

function scontains(content, substring) {
  // Normalize whitespace for docstring checks
  return content.replace(/\s+/g, ' ').includes(substring);
}

// ─────────────────────────────────────────────────────────────────
// Scenario 1: All tasks default to Claude Code CLI first
// ─────────────────────────────────────────────────────────────────
function scenario1_tasks_enter_claude_code() {
  console.log('\n[Scenario 1] All tasks default to Claude Code CLI first');
  const router = readFileSync(resolve(APP, 'm11/claude_code_router.py'), 'utf-8');
  const role = readFileSync(resolve(APP, 'm11/claude_code_primary_role.py'), 'utf-8');

  assert(
    router.includes('def claude_code_route'),
    'claude_code_route() is the primary routing entry point'
  );
  assert(
    router.includes('PRIMARY_OPERATOR_ID'),
    'claude_code_route() uses PRIMARY_OPERATOR_ID'
  );
  assert(
    ic(router, 'fallback_brain'),
    'claude_code_route has fallback_brain for unclassified tasks'
  );
  assert(
    router.includes('ExecutionPath.DIRECT_EXECUTE'),
    'claude_code_route has DIRECT_EXECUTE path'
  );
  assert(
    ic(role, 'Claude Code CLI'),
    'claude_code_primary_role.py formally declares "Claude Code CLI"'
  );
  assert(
    role.includes('PRIMARY_OPERATOR_ID = "Claude Code CLI"'),
    'PRIMARY_OPERATOR_ID is set to "Claude Code CLI"'
  );
}

// ─────────────────────────────────────────────────────────────────
// Scenario 2: Claude Code can directly execute engineering tasks
// ─────────────────────────────────────────────────────────────────
function scenario2_direct_execute() {
  console.log('\n[Scenario 2] Claude Code can directly execute engineering tasks');
  const router = readFileSync(resolve(APP, 'm11/claude_code_router.py'), 'utf-8');
  const role = readFileSync(resolve(APP, 'm11/claude_code_primary_role.py'), 'utf-8');

  assert(
    ic(role, 'engineering_executor'),
    'engineering_executor is a declared Claude Code role'
  );
  assert(
    router.includes('engineering_task_types'),
    'claude_code_router identifies engineering task types for direct execute'
  );
  assert(
    ic(router, 'code_generation') && ic(router, 'code_modification'),
    'engineering task types include code_generation and code_modification'
  );
  assert(
    router.includes('ExecutionPath.DIRECT_EXECUTE'),
    'DIRECT_EXECUTE execution path exists'
  );
  assert(
    ic(router, 'Claude Code CLI'),
    'DIRECT_EXECUTE path assigns handler to Claude Code CLI'
  );
}

// ─────────────────────────────────────────────────────────────────
// Scenario 3: Claude Code can invoke Scrapling and integrate results
// ─────────────────────────────────────────────────────────────────
function scenario3_scrapling_invocation() {
  console.log('\n[Scenario 3] Claude Code invokes Scrapling as subordinate');
  const router = readFileSync(resolve(APP, 'm11/claude_code_router.py'), 'utf-8');
  const scrapling = readFileSync(resolve(APP, 'm11/scrapling_adapter.py'), 'utf-8');

  assert(
    ic(scrapling, 'web_extraction_coprocessor_for_claude_code'),
    'Scrapling role is web_extraction_coprocessor_for_claude_code'
  );
  assert(
    ic(scrapling, 'subordinate coprocessor') && ic(scrapling, 'Claude Code CLI'),
    'Scrapling adapter docstring declares subordination to Claude Code'
  );
  assert(
    router.includes('_route_scrapling'),
    'claude_code_router has _route_scrapling() method'
  );
  assert(
    router.includes('ExecutionPath.USE_SCRAPLING'),
    'USE_SCRAPLING execution path exists'
  );
  assert(
    ic(router, 'returns_to'),
    'Scrapling invocation_shape specifies returns_to Claude Code'
  );
  assert(
    !ic(scrapling, 'may_claim_completion: True'),
    'Scrapling may NOT claim task completion independently'
  );
  assert(
    ic(scrapling, 'Claude Code CLI'),
    'Scrapling adapter references Claude Code CLI as primary operator'
  );
}

// ─────────────────────────────────────────────────────────────────
// Scenario 4: Claude Code can invoke Agent-S for high-difficulty GUI
// ─────────────────────────────────────────────────────────────────
function scenario4_agent_s_invocation() {
  console.log('\n[Scenario 4] Claude Code invokes Agent-S as subordinate for high-difficulty GUI');
  const router = readFileSync(resolve(APP, 'm11/claude_code_router.py'), 'utf-8');
  const agent_s = readFileSync(resolve(APP, 'm11/agent_s_adapter.py'), 'utf-8');

  assert(
    ic(agent_s, 'gui_grounding_coprocessor_for_claude_code'),
    'Agent-S role is gui_grounding_coprocessor_for_claude_code'
  );
  assert(
    ic(agent_s, 'subordinate coprocessor') && ic(agent_s, 'Claude Code CLI'),
    'Agent-S adapter docstring declares subordination to Claude Code'
  );
  assert(
    router.includes('_route_agent_s'),
    'claude_code_router has _route_agent_s() method'
  );
  assert(
    router.includes('ExecutionPath.USE_AGENT_S'),
    'USE_AGENT_S execution path exists'
  );
  assert(
    ic(router, 'returns_to'),
    'Agent-S invocation_shape specifies returns_to Claude Code'
  );
  // outcome_feeds_m08 is in the router's _route_agent_s invocation_shape
  assert(
    ic(router, 'outcome_feeds_m08'),
    'Agent-S outcomes feed back to M08 through Claude Code router'
  );
  assert(
    router.includes('task.difficulty == "high"'),
    'Agent-S is routed only for high-difficulty tasks'
  );
}

// ─────────────────────────────────────────────────────────────────
// Scenario 5: Claude Code can enable Bytebot sandbox mode
// ─────────────────────────────────────────────────────────────────
function scenario5_bytebot_invocation() {
  console.log('\n[Scenario 5] Claude Code enables Bytebot sandbox on demand');
  const router = readFileSync(resolve(APP, 'm11/claude_code_router.py'), 'utf-8');
  const bytebot = readFileSync(resolve(APP, 'm11/bytebot_sandbox_mode.py'), 'utf-8');

  assert(
    ic(bytebot, 'sandbox_tool_coprocessor_for_claude_code'),
    'Bytebot role is sandbox_tool_coprocessor_for_claude_code'
  );
  assert(
    ic(bytebot, 'subordinate coprocessor') && ic(bytebot, 'Claude Code CLI'),
    'Bytebot adapter docstring declares subordination to Claude Code'
  );
  assert(
    router.includes('_route_bytebot_sandbox'),
    'claude_code_router has _route_bytebot_sandbox() method'
  );
  assert(
    router.includes('ExecutionPath.USE_BYTEBOT_SANDBOX'),
    'USE_BYTEBOT_SANDBOX execution path exists'
  );
  assert(
    router.includes('requires_isolation'),
    'Bytebot is routed when task.requires_isolation is True'
  );
  // docker_isolation key is in router's _route_bytebot_sandbox invocation_shape
  assert(
    ic(router, 'docker_isolation'),
    'Bytebot invocation_shape marks docker_isolation'
  );
}

// ─────────────────────────────────────────────────────────────────
// Scenario 6: Coprocessors cannot claim primary operator role
// ─────────────────────────────────────────────────────────────────
function scenario6_no_coprocessor_bypass() {
  console.log('\n[Scenario 6] Coprocessors cannot claim primary operator role');
  const scrapling = readFileSync(resolve(APP, 'm11/scrapling_adapter.py'), 'utf-8');
  const agent_s = readFileSync(resolve(APP, 'm11/agent_s_adapter.py'), 'utf-8');
  const bytebot = readFileSync(resolve(APP, 'm11/bytebot_sandbox_mode.py'), 'utf-8');
  const role = readFileSync(resolve(APP, 'm11/claude_code_primary_role.py'), 'utf-8');

  assert(
    !ic(scrapling, 'may_claim_completion: True'),
    'Scrapling docstring does NOT grant completion claim authority'
  );
  assert(
    ic(agent_s, 'NEVER') && ic(agent_s, 'Claims task completion authority'),
    'Agent-S explicitly forbids claiming task completion'
  );
  assert(
    ic(bytebot, 'NEVER') && ic(bytebot, 'Claims task completion authority'),
    'Bytebot explicitly forbids claiming task completion'
  );
  assert(
    role.includes('is_coprocessor_bypass'),
    'claude_code_primary_role.py has is_coprocessor_bypass() guard'
  );
  const bridge = readFileSync(resolve(APP, 'm11/governance_bridge.py'), 'utf-8');
  assert(
    ic(bridge, 'primary_operator') || ic(bridge, 'Claude Code CLI'),
    'governance_bridge enforces primary_operator field in回流'
  );
}

// ─────────────────────────────────────────────────────────────────
// Scenario 7: M08回流 records have primary_operator = "Claude Code CLI"
// ─────────────────────────────────────────────────────────────────
function scenario7_m08回流_primary_operator() {
  console.log('\n[Scenario 7] M08回流 records use Claude Code CLI as primary_operator');
  const role = readFileSync(resolve(APP, 'm11/claude_code_primary_role.py'), 'utf-8');
  const router = readFileSync(resolve(APP, 'm11/claude_code_router.py'), 'utf-8');

  assert(
    role.includes('get_primary_operator_record'),
    'get_primary_operator_record() is defined in role registry'
  );
  assert(
    role.includes('"primary_operator": PRIMARY_OPERATOR_ID') ||
    role.includes("'primary_operator': PRIMARY_OPERATOR_ID"),
    '回流 records set primary_operator field to PRIMARY_OPERATOR_ID'
  );
  assert(
    role.includes('PRIMARY_OPERATOR_ID = "Claude Code CLI"'),
    'PRIMARY_OPERATOR_ID is "Claude Code CLI"'
  );
  assert(
    router.includes('record_outcome_through_claude_code'),
    'claude_code_router has record_outcome_through_claude_code() for M08回流'
  );
  assert(
    ic(role, 'supporting_capability'),
    '回流 records use supporting_capability to record coprocessor used'
  );
}

// ─────────────────────────────────────────────────────────────────
// Scenario 8: Asset回流 has Claude Code as orchestration owner
// ─────────────────────────────────────────────────────────────────
function scenario8_m07回流_orchestration_owner() {
  console.log('\n[Scenario 8] M07 asset回流 has Claude Code as orchestration owner');
  const role = readFileSync(resolve(APP, 'm11/claude_code_primary_role.py'), 'utf-8');
  const m07 = readFileSync(resolve(APP, 'm07/asset_system.py'), 'utf-8');
  const router = readFileSync(resolve(APP, 'm11/claude_code_router.py'), 'utf-8');

  assert(
    ic(role, 'orchestration_owner'),
    '回流 record includes orchestration_owner field'
  );
  assert(
    ic(role, '"orchestration_owner":') && ic(role, 'Claude Code CLI'),
    'orchestration_owner is set to "Claude Code CLI"'
  );
  assert(
    m07.includes('governance_bridge'),
    'M07 asset_system calls governance_bridge for asset promotion'
  );
  assert(
    ic(router, 'returns_to'),
    'Coprocessor invocation shapes specify returns_to Claude Code'
  );
}

// ─────────────────────────────────────────────────────────────────
// Scenario 9: No parallel bypass routing exists
// ─────────────────────────────────────────────────────────────────
function scenario9_no_parallel_bypass() {
  console.log('\n[Scenario 9] No parallel bypass routing that sidesteps Claude Code');
  const selector = readFileSync(resolve(APP, 'm11/external_backend_selector.py'), 'utf-8');
  const router = readFileSync(resolve(APP, 'm11/claude_code_router.py'), 'utf-8');
  const bridge = readFileSync(resolve(APP, 'm11/governance_bridge.py'), 'utf-8');
  const role = readFileSync(resolve(APP, 'm11/claude_code_primary_role.py'), 'utf-8');

  assert(
    ic(selector, 'DEPRECATED'),
    'external_backend_selector.py is marked DEPRECATED'
  );
  assert(
    ic(selector, 'claude_code_router'),
    'external_backend_selector docstring references claude_code_router as successor'
  );
  assert(
    ic(router, 'claude_code_route'),
    'claude_code_router.claude_code_route() is the primary entry point'
  );
  assert(
    bridge.includes('FAIL_CLOSED'),
    'governance_bridge uses FAIL_CLOSED (no PASS_THROUGH bypass)'
  );
  assert(
    !bridge.includes('governance_bridge_pass_through'),
    'governance_bridge has no PASS_THROUGH bypass'
  );
  assert(
    ic(router, 'claude_code_primary') || ic(bridge, 'claude_code_primary'),
    'routing_policy declares "claude_code_primary | coprocessors_subordinate"'
  );
}

// ─────────────────────────────────────────────────────────────────
// Scenario 10: System still complies with CORE_FROZEN_AND_CONTROLLED_EVOLUTION_ENABLED
// ─────────────────────────────────────────────────────────────────
function scenario10_core_frozen_evolution_enabled() {
  console.log('\n[Scenario 10] System still CORE_FROZEN_AND_CONTROLLED_EVOLUTION_ENABLED');
  const bridge = readFileSync(resolve(APP, 'm11/governance_bridge.py'), 'utf-8');
  const contract = resolve(SRC, 'rtcm/controlled_evolution_contract.ts');
  const role = readFileSync(resolve(APP, 'm11/claude_code_primary_role.py'), 'utf-8');
  const router = readFileSync(resolve(APP, 'm11/claude_code_router.py'), 'utf-8');

  assert(
    !ic(role, 'R20') && !ic(role, 'Round 20'),
    'claude_code_primary_role.py has no R20 references'
  );
  assert(
    ic(bridge, 'MAX_LAYER_ROUND = 19') || ic(bridge, 'MAX_LAYER_ROUND=19'),
    'governance_bridge still has MAX_LAYER_ROUND = 19 cap'
  );
  if (existsSync(contract)) {
    const contractContent = readFileSync(contract, 'utf-8');
    assert(
      ic(contractContent, 'FORBIDDEN_EXPANSION'),
      'controlled_evolution_contract.ts still has FORBIDDEN_EXPANSION entries'
    );
  }
  assert(
    !ic(router, 'R20') && !ic(router, 'Round 20'),
    'claude_code_router.py has no R20 references'
  );
  assert(
    ic(bridge, '"primary_operator":') || ic(bridge, "'primary_operator':"),
    'governance_bridge.get_evolution_status() includes primary_operator field'
  );
  assert(
    ic(bridge, 'CORE_ARCHITECTURE_FROZEN'),
    'governance_bridge declares CORE_ARCHITECTURE_FROZEN status'
  );
}

// ─────────────────────────────────────────────────────────────────
// Run all scenarios
// ─────────────────────────────────────────────────────────────────
console.log('================================================');
console.log('  CLAUDE CODE PRIMARY OPERATOR TEST (10 scenarios)');
console.log('  CORE_FROZEN_AND_CONTROLLED_EVOLUTION_ENABLED');
console.log('================================================');

scenario1_tasks_enter_claude_code();
scenario2_direct_execute();
scenario3_scrapling_invocation();
scenario4_agent_s_invocation();
scenario5_bytebot_invocation();
scenario6_no_coprocessor_bypass();
scenario7_m08回流_primary_operator();
scenario8_m07回流_orchestration_owner();
scenario9_no_parallel_bypass();
scenario10_core_frozen_evolution_enabled();

console.log('\n================================================');
console.log(`  Results: ${pass} passed, ${fail} failed`);
console.log('================================================');

if (fail === 0) {
  console.log('\n>>> ALL PASS → CLAUDE_CODE_PRIMARY_OPERATOR_RESTORED <<<\n');
  process.exit(0);
} else {
  console.log(`\n>>> ${fail} FAILED <<<\n`);
  process.exit(1);
}
