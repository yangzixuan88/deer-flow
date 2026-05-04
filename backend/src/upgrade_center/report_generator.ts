/**
 * @file report_generator.ts
 * @description U7: 鍙屾姤鍛婄敓鎴? * 鐢熸垚鍐呴儴澶滈棿鎶ュ憡鍜岄涔︽櫒鎶? */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import { spawn } from 'child_process';
import {
  ApprovalTierResult,
  UpgradeCenterReport,
  TieredCandidate,
} from './types';

const REPORTS_DIR = runtimePath('upgrade-center', 'reports');
const INTERNAL_DIR = path.join(REPORTS_DIR, 'nightly_internal');
const FEISHU_DIR = path.join(REPORTS_DIR, 'morning_feishu');

export class ReportGenerator {
  private deerflowRoot: string;

  constructor(deerflowRoot?: string) {
    this.deerflowRoot = deerflowRoot || process.cwd();
  }

  /**
   * 鐢熸垚鍙屾姤鍛?   * @param tierResult ApprovalTier result from U6
   * @param poolCounts Optional pool_counts from U2 ConstitutionFilter 鈥?enables report summary to reflect real filter output (deep_analysis_pool, excluded, etc.)
   */
  /**
   * R198: Approver open_id for Feishu approval cards.
   * Configure via environment variable FEISHU_APPROVER_OPEN_ID
   * or pass directly via FEISHU_APPROVER_OPEN_ID env var.
   */
  private getApproverOpenId(): string | undefined {
    return process.env.FEISHU_APPROVER_OPEN_ID;
  }

  private getLarkCliPath(): string {
    const npmRoot = 'E:\\OpenClaw-Base\\npm';
    const candidates = [
      path.join(npmRoot, 'lark-cli.cmd'),
      path.join(npmRoot, 'lark-cli'),
      path.join(os.homedir(), 'npm', 'node_modules', '@larksuite', 'cli', 'bin', 'lark-cli.cmd'),
      path.join(this.deerflowRoot, 'node_modules', '@larksuite', 'cli', 'bin', 'lark-cli.cmd'),
    ];
    for (const c of candidates) {
      if (fs.existsSync(c)) return c;
    }
    return 'lark-cli';
  }

  public async generate(tierResult: ApprovalTierResult, poolCounts?: { excluded: number; observation: number; experiment: number; deep_analysis: number }): Promise<UpgradeCenterReport> {
    console.log('[ReportGenerator] 鐢熸垚鎶ュ憡...');

    const internalReport = this.generateInternalReport(tierResult);
    const feishuReport = this.generateFeishuReport(tierResult);

    await this.saveReports(internalReport, feishuReport);

    const candidatesForApproval = tierResult.candidates.filter((c) => c.requires_approval);
    const experimentQueue = tierResult.candidates
      .filter((c) => !c.requires_approval && (c.tier === 'T0' || c.tier === 'T1'))
      .map((c) => c.candidate_id);
    const observationPool = tierResult.candidates
      .filter((c) => !c.requires_approval && c.tier === 'T2')
      .map((c) => c.candidate_id);

    // R198: Send Feishu approval cards for T2/T3 candidates
    // Cards contain approve/reject/observe action buttons.
    // Button clicks send callbacks to approval_webhook.py 鈫?governance_state.json.
    const approverOpenId = this.getApproverOpenId();
    if (approverOpenId && candidatesForApproval.length > 0) {
      console.log(`[ReportGenerator] R198: Sending ${candidatesForApproval.length} Feishu approval cards to ${approverOpenId}`);
      const sent = await this.sendFeishuApprovalCards(candidatesForApproval, approverOpenId);
      console.log(`[ReportGenerator] R198: Feishu cards sent = ${sent}`);
    } else if (candidatesForApproval.length > 0) {
      console.log(`[ReportGenerator] R198: FEISHU_APPROVER_OPEN_ID not set 鈥?skipping Feishu card send (${candidatesForApproval.length} cards not sent)`);
    }

    // Use real U2 pool_counts if provided, otherwise fall back to counting tierResult.candidates
    const realPoolCounts = poolCounts || {
      excluded: 0,
      experiment: experimentQueue.length,
      observation: observationPool.length,
      deep_analysis: 0,
    };

    console.log(`[ReportGenerator] 鎶ュ憡鐢熸垚瀹屾垚: ${candidatesForApproval.length} 涓緟瀹℃壒`);

    return {
      date: new Date().toISOString().split('T')[0],
      run_type: 'full',
      stages_completed: ['U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U7'],
      summary: {
        demands_scanned: tierResult.candidates.length,
        deep_analysis_pool: realPoolCounts.deep_analysis,
        experiment_pool: realPoolCounts.experiment,
        observation_pool: realPoolCounts.observation,
        excluded: realPoolCounts.excluded,
      },
      candidates_for_approval: candidatesForApproval,
      // R204-E: T1 bypass candidates for governance backflow
      experiment_queue_candidates: tierResult.candidates.filter(
        (c) => !c.requires_approval && (c.tier === 'T0' || c.tier === 'T1')
      ),
      experiment_queue: experimentQueue,
      // R204-H: R170 intercept candidates (governance_priority=observation_pool)
      // R206-B FIX: was `!c.requires_approval && c.tier === 'T2'` 鈥?wrong filter.
      // R170 intercept sets filter_result='observation_pool' (requires_approval=true, tier=T2).
      // Correct filter: check the filter_result field that propagates from U2.
      observation_pool_candidates: tierResult.candidates.filter(
        (c) => c.filter_result === 'observation_pool'
      ),
      observation_pool: observationPool,
      pending_approvals: candidatesForApproval.length,
    };
  }

  /**
   * 鐢熸垚鍐呴儴澶滈棿鎶ュ憡
   * 娉ㄥ叆鐪熷疄boulder.json鐘舵€?(Round 9 U7 minimum fix)
   */
  private generateInternalReport(tierResult: ApprovalTierResult): string {
    const boulderState = this.loadBoulderState();

    const report = {
      title: '澶滈棿鍗囩骇涓灑鏃ユ姤',
      date: tierResult.date,
      generated_at: new Date().toISOString(),
      execution_status: {
        current_phase: boulderState?.upgrade_center?.current_phase || 'U7',
        current_mode: boulderState?.heartbeat?.mode || 'NIGHT',
        last_sync: boulderState?.heartbeat?.last_sync || null,
        nightly_upgrade_pending: boulderState?.upgrade_center?.nightly_upgrade_pending || false,
      },
      summary: this.generateSummary(tierResult),
      // R179: ROI signals now included in candidate list for report visibility
      candidates: tierResult.candidates.map((c) => ({
        id: c.candidate_id,
        project: c.project,
        tier: c.tier,
        risk_level: c.risk_level,
        requires_approval: c.requires_approval,
        // R179: ROI layer visibility
        long_term_value: c.long_term_value,
        can_proceed_to_experiment: c.can_proceed_to_experiment,
        experiment_access_via_roi_leniency: c.experiment_access_via_roi_leniency,
        roi_leniency_applied: c.roi_leniency_applied,
        score_breakdown: c.score_breakdown,
      })),
      feishu_triggered: tierResult.candidates.some((c) => c.approval_type === 'feishu_card'),
    };

    return JSON.stringify(report, null, 2);
  }

  /**
   * 璇诲彇鐪熷疄boulder.json鐘舵€?(Round 9 U7)
   * 璺緞: {deerflowRoot}/backend/src/infrastructure/boulder.json
   * Falls back to null if file missing (degraded mode).
   */
  private loadBoulderState(): any | null {
    const boulderPath = path.join(this.deerflowRoot, 'backend', 'src', 'infrastructure', 'boulder.json');
    try {
      if (fs.existsSync(boulderPath)) {
        const raw = fs.readFileSync(boulderPath, 'utf-8');
        console.log('[ReportGenerator] Loaded real boulder.json state (degraded mode: no)');
        return JSON.parse(raw);
      }
      console.log('[ReportGenerator] WARNING: boulder.json not found 鈥?using degraded mode');
      return null;
    } catch (err) {
      console.warn(`[ReportGenerator] Failed to read boulder.json: ${err} 鈥?using degraded mode`);
      return null;
    }
  }

  /**
   * 鐢熸垚椋炰功鎶ュ憡
   */
  private generateFeishuReport(tierResult: ApprovalTierResult): string {
    const approvalCandidates = tierResult.candidates.filter(
      (c) => c.approval_type === 'feishu_card'
    );

    if (approvalCandidates.length === 0) {
      return JSON.stringify({
        title: '椋炰功鍗囩骇鏅ㄦ姤',
        date: tierResult.date,
        message: '浠婃棩鏃燭2/T3鍊欓€夛紝鏃犻渶瀹℃壒',
      }, null, 2);
    }

    const report = {
      title: '椋炰功鍗囩骇鏅ㄦ姤',
      date: tierResult.date,
      generated_at: new Date().toISOString(),
      cards: approvalCandidates.map((c) => this.generateFeishuCard(c)),
    };

    return JSON.stringify(report, null, 2);
  }

  /**
   * 鐢熸垚椋炰功鍗＄墖
   */
  private generateFeishuCard(candidate: TieredCandidate): object {
    return {
      header: {
        title: `${candidate.tier}绾у鎵硅姹俙,
        subtitle: candidate.project || candidate.candidate_id,
      },
      sections: [
        {
          fields: [
            { name: '椋庨櫓绛夌骇', value: candidate.risk_level },
            { name: '闇€瑕佸鎵?, value: candidate.items_requiring_approval?.join(', ') || '鏃? },
          ],
        },
        {
          fields: [
            { name: '鍥炴粴鏂规', value: candidate.backout_plan || '鏍囧噯鍥炴粴娴佺▼' },
          ],
        },
      ],
      actions: candidate.tier === 'T3'
        ? ['鎵瑰噯', '淇敼鍙傛暟', '鍔犲叆瑙傚療姹?, '鍚﹀喅']
        : ['鎵瑰噯', '鍔犲叆瑙傚療姹?, '鍚﹀喅'],
    };
  }

  /**
   * 鐢熸垚鎽樿
   * R179: Adds ROI summary so upgrade decisions are traceable at the report layer
   */
  private generateSummary(tierResult: ApprovalTierResult): object {
    const counts = {
      T0: 0,
      T1: 0,
      T2: 0,
      T3: 0,
      approval_required: 0,
    };

    // R179: ROI-specific counters
    let roiLeniencyCandidates = 0;
    let roiExperimentAccess = 0;
    let highLtvCandidates = 0; // LTV >= 12
    let totalLtvScore = 0;
    let ltvCandidatesWithScore = 0;

    for (const candidate of tierResult.candidates) {
      counts[candidate.tier]++;
      if (candidate.requires_approval) {
        counts.approval_required++;
      }

      // R179: ROI signal tracking
      if (candidate.roi_leniency_applied) roiLeniencyCandidates++;
      if (candidate.experiment_access_via_roi_leniency) roiExperimentAccess++;
      if (candidate.long_term_value !== undefined) {
        if (candidate.long_term_value >= 12) highLtvCandidates++;
        totalLtvScore += candidate.long_term_value;
        ltvCandidatesWithScore++;
      }
    }

    const avgLtv = ltvCandidatesWithScore > 0
      ? parseFloat((totalLtvScore / ltvCandidatesWithScore).toFixed(2))
      : 0;

    return {
      ...counts,
      // R179: ROI summary for report traceability
      roi_summary: {
        candidates_with_roi_leniency: roiLeniencyCandidates,
        candidates_with_roi_experiment_access: roiExperimentAccess,
        high_ltv_candidates: highLtvCandidates,   // LTV >= 12 (foundational/strategic ROI)
        avg_long_term_value: avgLtv,
        total_candidates: tierResult.candidates.length,
        roi_signal_coverage: ltvCandidatesWithScore > 0
          ? `${ltvCandidatesWithScore}/${tierResult.candidates.length} candidates have LTV data`
          : 'no LTV data available',
      },
    };
  }

  /**
   * 淇濆瓨鎶ュ憡
   */
  private async saveReports(internalReport: string, feishuReport: string): Promise<void> {
    this.ensureDirectories();

    const date = new Date().toISOString().split('T')[0];
    const internalPath = path.join(INTERNAL_DIR, `upgrade-center-${date}.json`);
    const feishuPath = path.join(FEISHU_DIR, `feishu-${date}.json`);

    fs.writeFileSync(internalPath, internalReport, 'utf-8');
    fs.writeFileSync(feishuPath, feishuReport, 'utf-8');

    console.log(`[ReportGenerator] 淇濆瓨鍐呴儴鎶ュ憡: ${internalPath}`);
    console.log(`[ReportGenerator] 淇濆瓨椋炰功鎶ュ憡: ${feishuPath}`);
  }

  /**
   * R198: 鍙戦€侀涔﹀鎵瑰崱鐗囩粰鎸囧畾鐢ㄦ埛
   *
   * 浣跨敤 lark-cli 鍙戦€佷氦浜掑紡瀹℃壒鍗＄墖锛岀敤鎴风偣鍑诲崱鐗囨寜閽悗
   * Feishu 浼氬皢 callback 鍙戦€佸埌 approval_webhook.py 鎺ユ敹鍣ㄣ€?   *
   * MINIMUM CLOSED LOOP (Round 198):
   *   generateFeishuReport() 鈫?鏈嚱鏁?鈫?lark-cli 鈫?Feishu
   *     鈫?鐢ㄦ埛鐐瑰嚮 鈫?Feishu callback 鈫?approval_webhook.py
   *     鈫?governance_state.json (upgrade_center_approval_result)
   *     鈫?DemandSampler 鍐嶆秷璐?   *
   * @param candidates 闇€瑕佸彂閫佸鎵硅姹傜殑鍊欓€夊垪琛?   * @param feishuOpenId 鎺ユ敹瀹℃壒鍗＄墖鐨勯涔︾敤鎴?open_id锛坥u_xxx锛?   * @returns 鍙戦€佹槸鍚︽垚鍔?   */
  public async sendFeishuApprovalCards(
    candidates: TieredCandidate[],
    feishuOpenId: string,
  ): Promise<boolean> {
    if (candidates.length === 0) {
      console.log('[ReportGenerator] No approval candidates to send 鈥?skipping Feishu card');
      return true;
    }

    // R198 fix: Use a Python helper script to send Feishu cards.
    // Writing Python script to file and invoking with python.exe avoids
    // all subprocess pipe encoding issues on Windows Python 3.13.
    // Invokes DeerFlow's existing lark_cli_adapter.ts as a module.
    const deerflowRoot = this.deerflowRoot;
    const larkCliPath = this.getLarkCliPath();
    const scriptFile = path.join(os.tmpdir(), `feishu_send_${Date.now()}.py`);

    let allSucceeded = true;

    for (const c of candidates) {
      const candidateId = c.candidate_id;
      const tier = c.tier;
      const risk = c.risk_level || 'unknown';
      const ltv = c.long_term_value ?? 'N/A';
      const ltvBonus = c.roi_leniency_applied !== undefined
        ? (c.roi_leniency_applied ? 'lenient' : 'normal')
        : 'N/A';
      const approvalItems = (c.items_requiring_approval || []).join(', ') || '鏃?;

      const cardContent = JSON.stringify({
        config: { wide_screen_mode: true },
        elements: [
          {
            tag: 'div',
            text: {
              tag: 'lark_md',
              content: `**銆愬崌绾у鎵硅姹傘€慣ier ${tier}**\n\n**鍊欓€塈D**: \`${candidateId}\`\n**椋庨櫓绛夌骇**: ${risk}\n**闀挎湡浠峰€?LTV)**: ${ltv}\n**ROI绛栫暐**: ${ltvBonus}\n**闇€瑕佸鎵?*: ${approvalItems}`,
            },
          },
          {
            tag: 'action',
            layout: 'right',
            children: [
              {
                tag: 'button',
                text: { tag: 'lark_md', content: '**鎵瑰噯**' },
                type: 'primary',
                value: { key: `approval_action_${candidateId}`, value: 'approve' },
              },
              {
                tag: 'button',
                text: { tag: 'lark_md', content: '**鍔犲叆瑙傚療姹?*' },
                type: 'default',
                value: { key: `approval_action_${candidateId}`, value: 'observe' },
              },
              {
                tag: 'button',
                text: { tag: 'lark_md', content: '**鍚﹀喅**' },
                type: 'danger',
                value: { key: `approval_action_${candidateId}`, value: 'reject' },
              },
            ],
          },
        ],
      });

      const messagePayload = JSON.stringify({
        receive_id: feishuOpenId,
        msg_type: 'interactive',
        content: cardContent,
      });

      // Write payload to a separate temp file to completely avoid escaping issues
      const payloadFile = path.join(os.tmpdir(), `feishu_payload_${Date.now()}_${candidateId.replace(/[^a-zA-Z0-9]/g, '_')}.json`);
      fs.writeFileSync(payloadFile, messagePayload, 'utf-8');

      const pythonScript = `
import json, urllib.request, urllib.error, tempfile, os

# Read payload directly from file written by Node.js
_payloadFile = r'${payloadFile}'
with open(_payloadFile, 'rb') as _f:
    _raw = _f.read()
try:
    payload = json.loads(_raw.decode('utf-8'))
except Exception as _e:
    print('DEBUG_PARSE_ERR=' + str(_e), flush=True)
    payload = {'receive_id': 'err'}

feishu_app_id = 'cli_a92772edd278dcc1'
feishu_app_secret = '<FEISHU_APP_SECRET_FROM_ENV>'

# Step 1: Get tenant access token via direct HTTP POST
token_url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
token_payload = json.dumps({'app_id': feishu_app_id, 'app_secret': feishu_app_secret}).encode('utf-8')
token_req = urllib.request.Request(token_url, data=token_payload, method='POST')
token_req.add_header('Content-Type', 'application/json')
try:
    with urllib.request.urlopen(token_req, timeout=15) as token_resp:
        token_data = json.loads(token_resp.read())
        token = token_data.get('tenant_access_token', '')
        if token:
            print('TOKEN_OK', flush=True)
        else:
            print('TOKEN_ERR: ' + str(token_data), flush=True)
except Exception as e:
    token = ''
    print('TOKEN_ERR: ' + str(e), flush=True)

# Step 2: Send interactive card via Feishu REST API
if token:
    url = 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id'
    with open(_payloadFile, 'rb') as _f:
        payload = json.loads(_f.read().decode('utf-8'))
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_data = json.loads(resp.read())
            if resp_data.get('ok') or resp_data.get('code') == 0:
                print('OK')
            else:
                print('FAILED: ' + str(resp_data))
    except Exception as e:
        print('FAILED: ' + str(e))
else:
    print('FAILED: no tenant access token')

# Cleanup
try:
    os.unlink(_payloadFile)
except:
    pass
`;

      // Write Python script to file to avoid subprocess pipe encoding issues
      fs.writeFileSync(scriptFile, pythonScript, 'utf-8');

      console.log(`[ReportGenerator] R198: Sending Feishu card for ${candidateId} to ${feishuOpenId}`);

      try {
        const result = await this.execPythonFile(scriptFile);
        if (result.success) {
          console.log(`[ReportGenerator] R198: Feishu card sent for ${candidateId}`);
        } else {
          console.warn(`[ReportGenerator] R198: Failed to send Feishu card for ${candidateId}: exit=${result.exitCode} stderr=${result.stderr} stdout=${result.stdout.substring(0, 200)}`);
          allSucceeded = false;
        }
      } catch (err) {
        console.warn(`[ReportGenerator] R198: Exception sending Feishu card for ${candidateId}: ${err}`);
        allSucceeded = false;
      } finally {
        try { fs.unlinkSync(scriptFile); } catch {}
      }
    }

    return allSucceeded;
  }

  private execPythonFile(scriptFile: string): Promise<{ success: boolean; stdout: string; stderr: string; exitCode: number }> {
    return new Promise((resolve) => {
      const stdoutFile = path.join(os.tmpdir(), `py_out_${Date.now()}.txt`);
      const stderrFile = path.join(os.tmpdir(), `py_err_${Date.now()}.txt`);
      // R198 fix: write Python script to .py file and invoke with python.exe.
      // Reading from file avoids subprocess pipe GBK issue on Windows Python 3.13.
      const proc = spawn(
        'python',
        [scriptFile],
        {
          shell: false,
          timeout: 20000,
          stdio: ['ignore', 'pipe', 'pipe'],
        }
      );
      let stdout = '';
      let stderr = '';
      proc.stdout?.on('data', (d) => {
        stdout += d instanceof Buffer ? d.toString('utf-8') : String(d);
      });
      proc.stderr?.on('data', (d) => {
        stderr += d instanceof Buffer ? d.toString('utf-8') : String(d);
      });
      proc.on('close', (code) => {
        try { fs.unlinkSync(stdoutFile); } catch {}
        try { fs.unlinkSync(stderrFile); } catch {}
        resolve({
          success: (code === 0) && stdout.includes('OK'),
          stdout,
          stderr,
          exitCode: code || 0,
        });
      });
      proc.on('error', (err) => {
        try { fs.unlinkSync(stdoutFile); } catch {}
        try { fs.unlinkSync(stderrFile); } catch {}
        resolve({ success: false, stdout: '', stderr: err.message, exitCode: -1 });
      });
    });
  }

  /**
   * 纭繚鐩綍瀛樺湪
   */
  private ensureDirectories(): void {
    const dirs = [REPORTS_DIR, INTERNAL_DIR, FEISHU_DIR];
    for (const dir of dirs) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    }
  }
}

