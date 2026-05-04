/**
 * @file upgrade_center_runner.ts
 * @description Minimal CLI entry point for Upgrade Center U0-U8 pipeline.
 *
 * ROLE: Standalone subprocess invoked by watchdog.py at 03:00 AM.
 * Reads governance demands from governance_state.json (written by Python UEF),
 * executes U0-U8 pipeline via upgradeCenter.executeFullRun(),
 * writes structured result to upgrade_center_result.json (readable by watchdog/Python).
 *
 * Usage: npx tsx upgrade_center_runner.ts
 *   (run from deerflow root: E:/OpenClaw-Base/deerflow/)
 *
 * MINIMUM CLOSED LOOP (Round 4-5):
 *   watchdog.py → spawns this via npx tsx
 *   → governance_state.json (Python UEF writes demands here)
 *   → U1 sampleFromGovernanceState() reads demands
 *   → U2-U8 pipeline executes
 *   → writes upgrade_center_result.json
 *   → watchdog reads result.json to verify execution happened
 */

import * as fs from 'fs';
import * as path from 'path';
import { spawn } from 'child_process';
import { UpgradeCenter } from './index';
import { QueueManager } from './queue_manager';
import { UpgradeCenterReport } from './types';

// Handle both run locations: deerflow/ root and deerflow/backend/
// If running from deerflow/backend/, DEERFLOW_ROOT + 'backend' would double-path, so detect and avoid
const rawRoot = process.cwd();  // e.g. E:/OpenClaw-Base/deerflow/backend
const DEERFLOW_ROOT = rawRoot.endsWith('backend') ? path.dirname(rawRoot) : rawRoot;
const GOVERNANCE_STATE_PATH = path.join(DEERFLOW_ROOT, 'backend', 'app', 'm11', 'governance_state.json');
const RESULT_PATH = path.join(DEERFLOW_ROOT, 'backend', 'src', 'infrastructure', 'upgrade_center_result.json');

async function main() {
  console.log('[Runner] Upgrade Center Runner starting...');
  console.log(`[Runner] DeerFlow root: ${DEERFLOW_ROOT}`);
  console.log(`[Runner] Governance state: ${GOVERNANCE_STATE_PATH}`);
  console.log(`[Runner] Result output: ${RESULT_PATH}`);

  // Verify governance_state.json exists (sanity check before running)
  if (!fs.existsSync(GOVERNANCE_STATE_PATH)) {
    console.warn('[Runner] governance_state.json not found — will proceed with empty governance demands');
  }

  try {
    // Pass DEERFLOW_ROOT so ReportGenerator can read real boulder.json state (Round 9 U7)
    const upgradeCenter = new UpgradeCenter(DEERFLOW_ROOT);
    console.log('[Runner] Calling upgradeCenter.executeFullRun()...');
    const report: UpgradeCenterReport = await upgradeCenter.executeFullRun();

    // Round 10: Get Top-N queue candidates for main-chain consumption
    const queueManager = new QueueManager();
    const topCandidates = await queueManager.getTopCandidates(5);

    console.log(`[Runner] U0-U8 pipeline complete. Demands scanned: ${report.summary.demands_scanned}`);
    console.log(`[Runner] Experiment pool: ${report.summary.experiment_pool}`);
    console.log(`[Runner] Observation pool: ${report.summary.observation_pool}`);
    console.log(`[Runner] Pending approvals: ${report.pending_approvals}`);
    console.log(`[Runner] Top queue candidates: ${topCandidates.length}`);

    // Write structured result to a watchdog-readable JSON file
    // Includes upgrade_center_summary and upgrade_queue_snapshot for main-chain consumption (Round 10)
    const resultRecord = {
      executed_at: new Date().toISOString(),
      success: true,
      report,
      upgrade_center_summary: {
        demands_scanned: report.summary.demands_scanned,
        experiment_pool_size: report.summary.experiment_pool,
        observation_pool_size: report.summary.observation_pool,
        pending_approvals: report.pending_approvals,
        candidates_for_approval: report.candidates_for_approval.map((c) => ({
          candidate_id: c.candidate_id,
          tier: c.tier,
          risk_level: c.risk_level,
          requires_approval: c.requires_approval,
          can_proceed_to_experiment: c.can_proceed_to_experiment,
          long_term_value: c.long_term_value,
          experiment_access_via_roi_leniency: c.experiment_access_via_roi_leniency,
          roi_leniency_applied: c.roi_leniency_applied,
          // R204-K: real predicted_value from TieredCandidate (U6), replacing hardcoded 0.9
          predicted_value: (c as any).predicted_value,
          // R217: filter_result for governance provenance backtrack
          filter_result: (c as any).filter_result,
        })),
        // R204-E: T1 bypass candidates (experiment_queue) for governance backflow
        experiment_queue_candidates: (report.experiment_queue_candidates || []).map((c) => ({
          candidate_id: c.candidate_id,
          tier: c.tier,
          risk_level: c.risk_level,
          requires_approval: c.requires_approval,
          can_proceed_to_experiment: c.can_proceed_to_experiment,
          long_term_value: c.long_term_value,
          experiment_access_via_roi_leniency: c.experiment_access_via_roi_leniency,
          roi_leniency_applied: c.roi_leniency_applied,
          // R204-K: real predicted_value from TieredCandidate (U6)
          predicted_value: (c as any).predicted_value,
          // R215: filter_result enables governance to verify predicted_value source
          filter_result: (c as any).filter_result,
        })),
        // R204-H: R170 intercept candidates (governance_priority=observation_pool)
        observation_pool_candidates: (report.observation_pool_candidates || []).map((c) => ({
          candidate_id: c.candidate_id,
          tier: c.tier,
          risk_level: c.risk_level,
          requires_approval: c.requires_approval,
          can_proceed_to_experiment: c.can_proceed_to_experiment,
          long_term_value: c.long_term_value,
          experiment_access_via_roi_leniency: c.experiment_access_via_roi_leniency,
          roi_leniency_applied: c.roi_leniency_applied,
          // R206-B fix: include filter_result for governance backflow
          filter_result: c.filter_result,
          // R204-K: real predicted_value from TieredCandidate (U6)
          predicted_value: (c as any).predicted_value,
        })),
      },
      upgrade_queue_snapshot: topCandidates,
    };

    fs.writeFileSync(RESULT_PATH, JSON.stringify(resultRecord, null, 2), 'utf-8');
    console.log(`[Runner] Result written to ${RESULT_PATH}`);

    // R132: Backflow to governance_state.json directly (no watchdog dependency)
    // UC is the producer of the result — it is responsible for closing the loop.
    // This ensures upgrade_center_* outcomes reach governance even if watchdog is offline.
    await backflowToGovernance(resultRecord);

    // Also update boulder.json with current state
    updateBoulderState(report);

    console.log('[Runner] Upgrade Center Runner finished successfully.');
    process.exit(0);
  } catch (err) {
    console.error(`[Runner] Upgrade Center execution failed: ${err}`);
    // Write error result so watchdog can see what went wrong
    const errorRecord = {
      executed_at: new Date().toISOString(),
      success: false,
      error: String(err),
    };
    try {
      fs.writeFileSync(RESULT_PATH, JSON.stringify(errorRecord, null, 2), 'utf-8');
    } catch {}
    process.exit(1);
  }
}

/**
 * R132: Backflow upgrade result to governance_state.json via governance_bridge.
 * Runs as a fire-and-forget async task — result.json write is the primary output.
 * This eliminates the dependency on watchdog being online to call _record_upgrade_outcome().
 */
async function backflowToGovernance(resultRecord: any): Promise<void> {
  const backendRoot = path.join(DEERFLOW_ROOT, 'backend');
  // R196 fix: write JSON to a temp file and have Python read it directly.
  // This physically separates the JSON data boundary from the Python code string,
  // eliminating all quote-escaping issues that plagued the inline approach.
  const tmpJson = path.join(DEERFLOW_ROOT, 'backend', 'tmp_uc_backflow.json');
  const tmpScript = path.join(DEERFLOW_ROOT, 'backend', 'tmp_uc_backflow.py');
  fs.writeFileSync(tmpJson, JSON.stringify(resultRecord), 'utf-8');

  // R207-C FIX: Write Python script to a .py file and spawn it directly.
  // Windows Python 3.13 has a known edge case where `python -c '...'` fails
  // (silent null exit) when the script string contains complex multi-line code
  // with loops, indentation, and template-interpolated paths. Using a real
  // .py file + `python script.py` is a stable alternative.
  const pythonScriptContent = `
import sys, json, asyncio, os
sys.path.insert(0, os.environ.get('DEERFLOW_BACKEND', r'${backendRoot.replace(/\\/g, '\\\\')}'))
from app.m11.governance_bridge import governance_bridge

result = None
payload_path = os.environ.get('UC_BACKFLOW_PAYLOAD', '')
if payload_path and os.path.exists(payload_path):
    with open(payload_path, 'r', encoding='utf-8') as f:
        result = json.load(f)

if result is None:
    print('ERROR: no payload', flush=True)
    sys.exit(1)

async def record_all():
    executed_at = result.get('executed_at', '')
    success = result.get('success', False)

    # 1. upgrade_center_execution
    await governance_bridge.record_outcome(
        outcome_type='upgrade_center_execution',
        actual_result=1.0 if success else 0.0,
        predicted_result=0.9,
        context={
            'source_id': 'upgrade_center_runner',
            'task_goal': 'Upgrade Center U0-U8 nightly execution',
            'success': success,
            'executed_at': executed_at,
            'demands_scanned': result.get('report', {}).get('summary', {}).get('demands_scanned', 0),
        },
    )

    # 2. upgrade_center_summary
    summary = result.get('upgrade_center_summary', {})
    await governance_bridge.record_outcome(
        outcome_type='upgrade_center_summary',
        actual_result=1.0 if success else 0.0,
        predicted_result=0.9,
        context={
            'source_id': 'upgrade_center_runner',
            'demands_scanned': summary.get('demands_scanned', 0),
            'experiment_pool_size': summary.get('experiment_pool_size', 0),
            'observation_pool_size': summary.get('observation_pool_size', 0),
            'pending_approvals': summary.get('pending_approvals', 0),
            'top_candidates_for_approval': summary.get('candidates_for_approval', []),
            'executed_at': executed_at,
            'success': success,
        },
    )

    # 3. upgrade_queue_snapshot
    snapshot = result.get('upgrade_queue_snapshot', [])
    await governance_bridge.record_outcome(
        outcome_type='upgrade_queue_snapshot',
        actual_result=1.0 if success else 0.0,
        predicted_result=0.9,
        context={
            'source_id': 'upgrade_center_runner',
            'top_n_count': len(snapshot),
            'candidates': snapshot,
            'executed_at': executed_at,
            'success': success,
        },
    )

    # 4. R194: Per-candidate U6 approval decisions with ROI signals
    summary = result.get('upgrade_center_summary', {})
    candidates_for_approval = summary.get('candidates_for_approval', [])
    for c in candidates_for_approval:
        ltv = c.get('long_term_value', 0)
        ltv_bonus = -1 if ltv >= 12 else (0 if ltv >= 8 else 1)
        leniency = 'lenient' if ltv_bonus < 0 else ('normal' if ltv_bonus == 0 else 'tighten')

        await governance_bridge.record_outcome(
            outcome_type='upgrade_center_approval',
            actual_result=1.0,
            predicted_result=c.get('predicted_value', 0.9),
            context={
                'candidate_id': c.get('candidate_id', ''),
                'tier': c.get('tier', ''),
                'requires_approval': c.get('requires_approval', False),
                'can_proceed_to_experiment': c.get('can_proceed_to_experiment', False),
                'long_term_value': ltv,
                'ltv_bonus': ltv_bonus,
                'leniency': leniency,
                'experiment_access_via_roi': c.get('experiment_access_via_roi_leniency', False),
                'roi_leniency_applied': c.get('roi_leniency_applied', False),
                'risk_level': c.get('risk_level', ''),
                'executed_at': executed_at,
                'success': success,
                # R217: filter_result proves predicted_value source
                'filter_result': c.get('filter_result'),
            },
        )

    # 5. R207 FIX: Per-candidate execution_result for candidate-level sample alignment
    for c in candidates_for_approval:
        execution_stage = 'queued_for_experiment'
        if c.get('can_proceed_to_experiment', False):
            execution_stage = 'approved_for_experiment'
        elif c.get('requires_approval', False):
            execution_stage = 'awaiting_approval'

        await governance_bridge.record_outcome(
            outcome_type='upgrade_center_execution_result',
            actual_result=1.0 if c.get('can_proceed_to_experiment', False) else 0.5,
            predicted_result=c.get('predicted_value', 0.9),
            context={
                'candidate_id': c.get('candidate_id', ''),
                'tier': c.get('tier', ''),
                'risk_level': c.get('risk_level', ''),
                'long_term_value': c.get('long_term_value', 0),
                'requires_approval': c.get('requires_approval', False),
                'can_proceed_to_experiment': c.get('can_proceed_to_experiment', False),
                'experiment_access_via_roi_leniency': c.get('experiment_access_via_roi_leniency', False),
                'roi_leniency_applied': c.get('roi_leniency_applied', False),
                'execution_stage': execution_stage,
                'target_modules': c.get('target_modules', []),
                'executed_at': executed_at,
                'source': 'upgrade_center_runner',
                'success': success,
                # R217: filter_result proves predicted_value source (not a fallback)
                'filter_result': c.get('filter_result'),
            },
        )

    # R204-E: T1 bypass candidates execution_result (no approval required)
    experiment_queue_candidates = summary.get('experiment_queue_candidates', [])
    for c in experiment_queue_candidates:
        # T1 bypass: goes directly to experiment queue, no approval needed
        execution_stage = 'bypass_to_experiment'
        if not c.get('can_proceed_to_experiment', False):
            execution_stage = 'bypass_rejected'

        await governance_bridge.record_outcome(
            outcome_type='upgrade_center_execution_result',
            actual_result=1.0 if c.get('can_proceed_to_experiment', False) else 0.0,
            predicted_result=c.get('predicted_value', 0.9),
            context={
                'candidate_id': c.get('candidate_id', ''),
                'tier': c.get('tier', ''),
                'risk_level': c.get('risk_level', ''),
                'long_term_value': c.get('long_term_value', 0),
                'requires_approval': False,
                'can_proceed_to_experiment': c.get('can_proceed_to_experiment', False),
                'experiment_access_via_roi_leniency': c.get('experiment_access_via_roi_leniency', False),
                'roi_leniency_applied': c.get('roi_leniency_applied', False),
                'execution_stage': execution_stage,
                'target_modules': c.get('target_modules', []),
                'executed_at': executed_at,
                'source': 'upgrade_center_runner',
                'success': success,
                # R215: filter_result proves predicted_value source (not a fallback)
                'filter_result': c.get('filter_result'),
            },
        )

    # R204-H: observation_pool candidates execution_result (R170 intercept - governance_priority=observation_pool)
    observation_pool_candidates = summary.get('observation_pool_candidates', [])
    for c in observation_pool_candidates:
        # R170 intercept: goes to observation_pool, no experiment, intermediate state
        # actual=0.5 (intermediate/neutral) - not success(1.0) not failure(0.0)
        await governance_bridge.record_outcome(
            outcome_type='upgrade_center_execution_result',
            actual_result=0.5,
            predicted_result=c.get('predicted_value', 0.9),
            context={
                'candidate_id': c.get('candidate_id', ''),
                'tier': c.get('tier', ''),
                'risk_level': c.get('risk_level', ''),
                'long_term_value': c.get('long_term_value', 0),
                'requires_approval': c.get('requires_approval', False),
                'can_proceed_to_experiment': c.get('can_proceed_to_experiment', False),
                'experiment_access_via_roi_leniency': c.get('experiment_access_via_roi_leniency', False),
                'roi_leniency_applied': c.get('roi_leniency_applied', False),
                'execution_stage': 'observation_pool',
                'target_modules': c.get('target_modules', []),
                'executed_at': executed_at,
                'source': 'upgrade_center_runner',
                'success': success,
                # R217: filter_result proves predicted_value source (not a fallback)
                'filter_result': c.get('filter_result'),
            },
        )

    print('OK', flush=True)

asyncio.run(record_all())
`;
  fs.writeFileSync(tmpScript, pythonScriptContent, 'utf-8');

  return new Promise<void>((resolve) => {
    const child = spawn('python', [tmpScript], {
      cwd: DEERFLOW_ROOT,
      timeout: 15000,
      env: {
        ...process.env,
        'DEERFLOW_BACKEND': backendRoot,
        'UC_BACKFLOW_PAYLOAD': tmpJson,
      },
    });

    // R207-C: Close stdin immediately to prevent Python's asyncio from blocking on it.
    // Without this, Python's stdin.read() in async contexts can deadlock on Windows.
    child.stdin.end();

    let stderr = '';
    child.stderr.on('data', (data) => { stderr += data.toString(); });
    child.on('close', (code) => {
      if (code === 0) {
        console.log('[Runner] Governance backflow: SUCCESS (upgrade_center_* outcomes recorded)');
      } else {
        console.warn(`[Runner] Governance backflow: FAILED (exit ${code}) — ${stderr.slice(0, 300)}`);
      }
      resolve();
    });
    child.on('error', (err) => {
      console.warn(`[Runner] Governance backflow: ERROR — ${err.message}`);
      resolve();
    });
  });
}

function updateBoulderState(report: UpgradeCenterReport) {
  const boulderPath = path.join(DEERFLOW_ROOT, 'backend', 'src', 'infrastructure', 'boulder.json');
  try {
    if (fs.existsSync(boulderPath)) {
      const boulder = JSON.parse(fs.readFileSync(boulderPath, 'utf-8'));
      boulder.upgrade_center = {
        ...boulder.upgrade_center,
        last_full_run: new Date().toISOString(),
        pending_approvals: report.pending_approvals,
        experiment_queue_size: report.experiment_queue.length,
        observation_pool_size: report.observation_pool.length,
        nightly_upgrade_pending: false,
      };
      fs.writeFileSync(boulderPath, JSON.stringify(boulder, null, 2), 'utf-8');
      console.log('[Runner] Updated boulder.json with upgrade center state');
    }
  } catch (err) {
    console.warn(`[Runner] Could not update boulder.json: ${err}`);
  }
}

main();
