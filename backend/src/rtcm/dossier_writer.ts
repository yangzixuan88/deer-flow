/**
 * @file dossier_writer.ts
 * @description U3: RTCM Project Dossier Writer
 * 写入和管理项目档案 (完整版 - JSONL + Markdown)
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import {
  Manifest,
  Issue,
  IssueGraph,
  IssueGraphNode,
  IssueGraphEdge,
  EvidenceLedgerEntry,
  ValidationResult,
  ProjectDossier,
  CouncilLogEntry,
  CouncilLogEventType,
  BriefReport,
  FinalReport,
  ResolvedIssueSummary,
  PendingIssueSummary,
  DissentRecord,
  UncertaintyRecord,
} from './types';

const RTCM_DOSSIER_DIR = runtimePath('rtcm', 'dossiers');

export class DossierWriter {
  private dossierRoot: string;
  private currentProjectSlug: string | null = null;
  private sessionId: string | null = null;

  constructor(dossierRoot: string = RTCM_DOSSIER_DIR) {
    this.dossierRoot = dossierRoot;
  }

  /**
   * 初始化项目档案
   */
  public async initProjectDossier(
    projectId: string,
    projectName: string,
    projectSlug: string,
    userGoal: string,
    createdBy: string
  ): Promise<ProjectDossier> {
    console.log(`[DossierWriter] 初始化项目档案: ${projectSlug}`);

    this.currentProjectSlug = projectSlug;
    this.sessionId = `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    const projectDir = path.join(this.dossierRoot, projectSlug);

    // 创建目录结构
    this.ensureDirectory(projectDir);
    this.ensureDirectory(path.join(projectDir, 'issue_cards'));
    this.ensureDirectory(path.join(projectDir, 'validation_runs'));
    this.ensureDirectory(path.join(projectDir, 'plan_versions'));

    // 创建清单
    const manifest: Manifest = {
      project_id: projectId,
      project_name: projectName,
      project_slug: projectSlug,
      mode: 'rtcm_v2',
      status: 'active',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      created_by: createdBy,
      chair_agent_id: 'rtcm-chair-agent',
      member_agent_ids: [
        'rtcm-trend-agent',
        'rtcm-value-agent',
        'rtcm-architecture-agent',
        'rtcm-automation-agent',
        'rtcm-quality-agent',
        'rtcm-efficiency-agent',
        'rtcm-challenger-agent',
        'rtcm-validator-agent',
      ],
      user_goal: userGoal,
      acceptance_status: 'pending',
      current_round: 0,
      current_issue_id: null,
    };

    // 创建初始议题图
    const issueGraph: IssueGraph = {
      project_id: projectId,
      nodes: [],
      edges: [],
    };

    // 保存清单
    await this.writeManifest(manifest);
    await this.writeIssueGraph(issueGraph);

    // 初始化空的 evidence_ledger.json
    await this.writeEvidenceLedger([]);

    // 记录 session_created 事件
    await this.appendCouncilLog(
      'session_created',
      'system',
      `Session 创建: ${this.sessionId}, 项目: ${projectName}`,
      0,
      'init'
    );

    console.log(`[DossierWriter] 项目档案初始化完成: ${projectSlug}`);
    return {
      manifest,
      issue_graph: issueGraph,
      evidence_ledger: [],
      issue_cards: new Map(),
      validation_runs: [],
    };
  }

  /**
   * 加载项目档案
   */
  public async loadProjectDossier(projectSlug: string): Promise<ProjectDossier | null> {
    const projectDir = path.join(this.dossierRoot, projectSlug);
    const manifestPath = path.join(projectDir, 'manifest.json');

    if (!fs.existsSync(manifestPath)) {
      console.warn(`[DossierWriter] 项目不存在: ${projectSlug}`);
      return null;
    }

    try {
      const manifestContent = fs.readFileSync(manifestPath, 'utf-8');
      const manifest: Manifest = JSON.parse(manifestContent);

      const issueGraph = await this.readIssueGraph(projectSlug);
      const issueCards = await this.readAllIssueCards(projectSlug);
      const validationRuns = await this.readAllValidationRuns(projectSlug);
      const evidenceLedger = await this.readEvidenceLedger(projectSlug);

      this.currentProjectSlug = projectSlug;

      return {
        manifest,
        issue_graph: issueGraph ?? { project_id: projectSlug, nodes: [], edges: [] },
        evidence_ledger: evidenceLedger,
        issue_cards: issueCards,
        validation_runs: validationRuns,
      };
    } catch (error) {
      console.error(`[DossierWriter] 加载项目失败:`, error);
      return null;
    }
  }

  // ============================================================================
  // Council Log 方法 (JSONL 格式)
  // ============================================================================

  /**
   * 添加 Council Log 条目 (JSONL 格式)
   */
  public async appendCouncilLog(
    eventType: CouncilLogEventType,
    actor: string,
    details: string,
    round: number,
    stage: string,
    options?: {
      blockedReason?: string;
      regenerationApplied?: boolean;
    }
  ): Promise<void> {
    if (!this.currentProjectSlug) {
      throw new Error('[DossierWriter] 未设置当前项目');
    }

    const entry: CouncilLogEntry = {
      entry_id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: new Date().toISOString(),
      round,
      stage,
      event_type: eventType,
      actor,
      details,
      blocked_reason: options?.blockedReason,
      regeneration_applied: options?.regenerationApplied,
    };

    // JSONL 格式：每行一个 JSON 对象
    const line = JSON.stringify(entry) + '\n';
    const filePath = path.join(this.dossierRoot, this.currentProjectSlug, 'council_log.jsonl');

    fs.appendFileSync(filePath, line, 'utf-8');
    console.log(`[DossierWriter] Council Log: [${eventType}] ${actor}`);
  }

  /**
   * 读取 Council Log (从 JSONL)
   */
  public async readCouncilLog(projectSlug: string): Promise<CouncilLogEntry[]> {
    const filePath = path.join(this.dossierRoot, projectSlug, 'council_log.jsonl');

    if (!fs.existsSync(filePath)) {
      return [];
    }

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const lines = content.trim().split('\n').filter(line => line.trim());
      return lines.map(line => JSON.parse(line));
    } catch (error) {
      console.error(`[DossierWriter] 读取 Council Log 失败:`, error);
      return [];
    }
  }

  // ============================================================================
  // Brief Report 方法
  // ============================================================================

  /**
   * 生成并写入 Brief Report (JSON + Markdown)
   */
  public async writeBriefReport(
    projectId: string,
    projectName: string,
    lastIssueId: string | null,
    lastStage: string,
    lastRound: number,
    keyOutcomes: string[],
    pendingIssues: PendingIssueSummary[],
    unresolvedDissents: string[],
    openUncertainties: string[],
    nextRecommendedAction: string
  ): Promise<BriefReport> {
    if (!this.currentProjectSlug) {
      throw new Error('[DossierWriter] 未设置当前项目');
    }

    const briefReport: BriefReport = {
      report_id: `brief-${Date.now()}`,
      project_id: projectId,
      project_name: projectName,
      generated_at: new Date().toISOString(),
      last_issue_id: lastIssueId,
      last_stage: lastStage,
      last_round: lastRound,
      key_outcomes: keyOutcomes,
      pending_issues: pendingIssues,
      unresolved_dissents: unresolvedDissents,
      open_uncertainties: openUncertainties,
      next_recommended_action: nextRecommendedAction,
      user_acceptance_status: 'pending',
    };

    // 写入 JSON (内部中间态)
    const jsonPath = path.join(this.dossierRoot, this.currentProjectSlug, 'brief_report.json');
    fs.writeFileSync(jsonPath, JSON.stringify(briefReport, null, 2), 'utf-8');

    // 写入 Markdown (交付文件)
    const mdPath = path.join(this.dossierRoot, this.currentProjectSlug, 'brief_report.md');
    fs.writeFileSync(mdPath, this.generateBriefReportMarkdown(briefReport), 'utf-8');

    // 记录事件
    await this.appendCouncilLog(
      'brief_report_generated',
      'system',
      `Brief Report 生成: ${briefReport.report_id}`,
      lastRound,
      lastStage
    );

    console.log(`[DossierWriter] 写入 Brief Report: ${briefReport.report_id}`);
    return briefReport;
  }

  /**
   * 生成 Brief Report Markdown
   */
  private generateBriefReportMarkdown(report: BriefReport): string {
    return `# Brief Report

**Report ID**: ${report.report_id}
**Project**: ${report.project_name}
**Generated**: ${report.generated_at}
**Last Issue**: ${report.last_issue_id || 'N/A'}
**Last Stage**: ${report.last_stage}
**Last Round**: ${report.last_round}

## Key Outcomes

${report.key_outcomes.map(o => `- ${o}`).join('\n') || '- (none)'}

## Pending Issues

${report.pending_issues.length > 0 ? report.pending_issues.map(i =>
`### ${i.issue_title} (${i.status})

- **ID**: ${i.issue_id}
- **Blocking**: ${i.blocking_item}
`).join('\n') : '- (none)'}

## Unresolved Dissents

${report.unresolved_dissents.length > 0 ? report.unresolved_dissents.map(d => `- ${d}`).join('\n') : '- (none)'}

## Open Uncertainties

${report.open_uncertainties.length > 0 ? report.open_uncertainties.map(u => `- ${u}`).join('\n') : '- (none)'}

## Next Recommended Action

${report.next_recommended_action}

---
**User Acceptance Status**: ${report.user_acceptance_status}
`;
  }

  /**
   * 读取 Brief Report
   */
  public async readBriefReport(projectSlug: string): Promise<BriefReport | null> {
    const filePath = path.join(this.dossierRoot, projectSlug, 'brief_report.json');

    if (!fs.existsSync(filePath)) {
      return null;
    }

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content);
    } catch (error) {
      console.error(`[DossierWriter] 读取 Brief Report 失败:`, error);
      return null;
    }
  }

  // ============================================================================
  // Final Report 方法
  // ============================================================================

  /**
   * 生成并写入 Final Report (JSON + Markdown)
   */
  public async writeFinalReport(
    projectId: string,
    projectName: string,
    userGoal: string,
    resolvedIssues: ResolvedIssueSummary[],
    unresolvedIssues: PendingIssueSummary[],
    allDissents: DissentRecord[],
    allUncertainties: UncertaintyRecord[],
    evidenceLedgerSummary: { totalEntries: number; evidenceBySource: Record<string, number>; mostUsedEvidence: string[] },
    acceptanceRecommendation: 'accept' | 'reject' | 'needs_revision'
  ): Promise<FinalReport> {
    if (!this.currentProjectSlug) {
      throw new Error('[DossierWriter] 未设置当前项目');
    }

    const finalReport: FinalReport = {
      report_id: `final-${Date.now()}`,
      project_id: projectId,
      project_name: projectName,
      user_goal: userGoal,
      generated_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      summary: this.generateExecutiveSummary(resolvedIssues, unresolvedIssues),
      resolved_issues: resolvedIssues,
      unresolved_issues: unresolvedIssues,
      all_dissents_recorded: allDissents,
      all_uncertainties_recorded: allUncertainties,
      evidence_ledger_summary: {
        total_entries: evidenceLedgerSummary.totalEntries,
        evidence_by_source: evidenceLedgerSummary.evidenceBySource,
        most_used_evidence: evidenceLedgerSummary.mostUsedEvidence,
      },
      acceptance_recommendation: acceptanceRecommendation,
      chair_sign_off: null,  // 可选：后续增强项
      supervisor_sign_off: null,  // 可选：后续增强项
    };

    // 写入 JSON (内部中间态)
    const jsonPath = path.join(this.dossierRoot, this.currentProjectSlug, 'final_report.json');
    fs.writeFileSync(jsonPath, JSON.stringify(finalReport, null, 2), 'utf-8');

    // 写入 Markdown (交付文件)
    const mdPath = path.join(this.dossierRoot, this.currentProjectSlug, 'final_report.md');
    fs.writeFileSync(mdPath, this.generateFinalReportMarkdown(finalReport), 'utf-8');

    // 记录事件
    await this.appendCouncilLog(
      'final_report_generated',
      'system',
      `Final Report 生成: ${finalReport.report_id}, 建议: ${acceptanceRecommendation}`,
      0,
      'completed'
    );

    console.log(`[DossierWriter] 写入 Final Report: ${finalReport.report_id}`);
    return finalReport;
  }

  /**
   * 生成 Final Report Markdown
   */
  private generateFinalReportMarkdown(report: FinalReport): string {
    return `# Final Report

**Report ID**: ${report.report_id}
**Project**: ${report.project_name}
**Generated**: ${report.generated_at}
**Completed**: ${report.completed_at || 'In Progress'}

## Executive Summary

${report.summary}

## User Goal

${report.user_goal}

## Resolved Issues (${report.resolved_issues.length})

${report.resolved_issues.length > 0 ? report.resolved_issues.map(i =>
`### ${i.issue_title}

- **ID**: ${i.issue_id}
- **Verdict**: ${i.verdict}
- **Reasoning**: ${i.key_reasoning}
- **Dissent**: ${i.dissent_summary}
`).join('\n') : '- (none)'}

## Unresolved Issues (${report.unresolved_issues.length})

${report.unresolved_issues.length > 0 ? report.unresolved_issues.map(i =>
`### ${i.issue_title}

- **ID**: ${i.issue_id}
- **Status**: ${i.status}
- **Blocking**: ${i.blocking_item}
`).join('\n') : '- (none)'}

## All Dissents Recorded (${report.all_dissents_recorded.length})

${report.all_dissents_recorded.length > 0 ? report.all_dissents_recorded.map(d =>
`- [${d.dissenter}] ${d.dissent_note} (Issue: ${d.issue_id})`).join('\n') : '- (none)'}

## All Uncertainties Recorded (${report.all_uncertainties_recorded.length})

${report.all_uncertainties_recorded.length > 0 ? report.all_uncertainties_recorded.map(u =>
`- ${u.uncertainty} → Impact: ${u.impact} (Issue: ${u.issue_id})`).join('\n') : '- (none)'}

## Evidence Ledger Summary

- **Total Entries**: ${report.evidence_ledger_summary.total_entries}
- **By Source**: ${Object.entries(report.evidence_ledger_summary.evidence_by_source).map(([k, v]) => `${k}: ${v}`).join(', ') || 'N/A'}
- **Most Used**: ${report.evidence_ledger_summary.most_used_evidence.join(', ') || 'N/A'}

## Acceptance Recommendation

**${report.acceptance_recommendation.toUpperCase()}**

${report.acceptance_recommendation === 'accept' ? '✅ 项目已通过所有验证，建议接受。' :
  report.acceptance_recommendation === 'reject' ? '❌ 项目未达到验收标准，建议拒绝。' :
  '⚠️ 项目需要修改后重新评审。'}

${report.chair_sign_off ? `\n**Chair Sign-off**: ${report.chair_sign_off}` : ''}
${report.supervisor_sign_off ? `\n**Supervisor Sign-off**: ${report.supervisor_sign_off}` : ''}

---
*Note: chair_sign_off 和 supervisor_sign_off 是可选的后续增强项，当前最小闭环版本不强制要求。*
`;
  }

  /**
   * 生成执行摘要
   */
  private generateExecutiveSummary(
    resolved: ResolvedIssueSummary[],
    unresolved: PendingIssueSummary[]
  ): string {
    const resolvedCount = resolved.length;
    const unresolvedCount = unresolved.length;

    let summary = `本项目共解决 ${resolvedCount} 个议题`;
    if (unresolvedCount > 0) {
      summary += `，尚有 ${unresolvedCount} 个议题待处理`;
    }
    summary += '。';

    if (resolvedCount > 0) {
      summary += ` 已解决议题包括: ${resolved.map(r => r.issue_title).join('; ')}。`;
    }

    return summary;
  }

  /**
   * 读取 Final Report
   */
  public async readFinalReport(projectSlug: string): Promise<FinalReport | null> {
    const filePath = path.join(this.dossierRoot, projectSlug, 'final_report.json');

    if (!fs.existsSync(filePath)) {
      return null;
    }

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content);
    } catch (error) {
      console.error(`[DossierWriter] 读取 Final Report 失败:`, error);
      return null;
    }
  }

  /**
   * 签署 Final Report (Chair/Supervisor) - 可选后续增强项
   */
  public async signFinalReport(
    projectSlug: string,
    signer: 'chair' | 'supervisor',
    signature: string
  ): Promise<void> {
    const report = await this.readFinalReport(projectSlug);
    if (!report) {
      throw new Error('[DossierWriter] Final Report 不存在');
    }

    if (signer === 'chair') {
      report.chair_sign_off = signature;
    } else {
      report.supervisor_sign_off = signature;
    }

    const jsonPath = path.join(this.dossierRoot, projectSlug, 'final_report.json');
    const mdPath = path.join(this.dossierRoot, projectSlug, 'final_report.md');

    fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2), 'utf-8');
    fs.writeFileSync(mdPath, this.generateFinalReportMarkdown(report), 'utf-8');
  }

  // ============================================================================
  // Issue Card 方法
  // ============================================================================

  /**
   * 写入议题卡
   */
  public async writeIssueCard(issue: Issue): Promise<void> {
    if (!this.currentProjectSlug) {
      throw new Error('[DossierWriter] 未设置当前项目');
    }

    const filePath = path.join(
      this.dossierRoot,
      this.currentProjectSlug,
      'issue_cards',
      `${issue.issue_id}.json`
    );

    fs.writeFileSync(filePath, JSON.stringify(issue, null, 2), 'utf-8');
    console.log(`[DossierWriter] 写入议题卡: ${issue.issue_id}`);

    await this.addIssueToGraph(issue);
  }

  /**
   * 读取议题卡
   */
  public async readIssueCard(projectSlug: string, issueId: string): Promise<Issue | null> {
    const filePath = path.join(
      this.dossierRoot,
      projectSlug,
      'issue_cards',
      `${issueId}.json`
    );

    if (!fs.existsSync(filePath)) {
      return null;
    }

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content);
    } catch (error) {
      console.error(`[DossierWriter] 读取议题卡失败:`, error);
      return null;
    }
  }

  /**
   * 读取所有议题卡
   */
  private async readAllIssueCards(projectSlug: string): Promise<Map<string, Issue>> {
    const issueCards = new Map<string, Issue>();
    const cardsDir = path.join(this.dossierRoot, projectSlug, 'issue_cards');

    if (!fs.existsSync(cardsDir)) {
      return issueCards;
    }

    const files = fs.readdirSync(cardsDir).filter((f) => f.endsWith('.json'));

    for (const file of files) {
      const issueId = file.replace('.json', '');
      const issue = await this.readIssueCard(projectSlug, issueId);
      if (issue) {
        issueCards.set(issueId, issue);
      }
    }

    return issueCards;
  }

  // ============================================================================
  // Validation Run 方法
  // ============================================================================

  /**
   * 写入验证记录
   */
  public async writeValidationRun(run: ValidationResult): Promise<void> {
    if (!this.currentProjectSlug) {
      throw new Error('[DossierWriter] 未设置当前项目');
    }

    const filePath = path.join(
      this.dossierRoot,
      this.currentProjectSlug,
      'validation_runs',
      `${run.run_id}.json`
    );

    fs.writeFileSync(filePath, JSON.stringify(run, null, 2), 'utf-8');
    console.log(`[DossierWriter] 写入验证记录: ${run.run_id}`);

    // 记录验证事件
    await this.appendCouncilLog(
      'validation_run_completed',
      run.executor,
      `验证完成: ${run.run_id}, 结果: ${run.pass_fail_summary}`,
      0,
      'validation_execution'
    );
  }

  /**
   * 读取所有验证记录
   */
  private async readAllValidationRuns(projectSlug: string): Promise<ValidationResult[]> {
    const runsDir = path.join(this.dossierRoot, projectSlug, 'validation_runs');
    const runs: ValidationResult[] = [];

    if (!fs.existsSync(runsDir)) {
      return runs;
    }

    const files = fs.readdirSync(runsDir).filter((f) => f.endsWith('.json'));

    for (const file of files) {
      const filePath = path.join(runsDir, file);
      try {
        const content = fs.readFileSync(filePath, 'utf-8');
        runs.push(JSON.parse(content));
      } catch (error) {
        console.error(`[DossierWriter] 读取验证记录失败:`, error);
      }
    }

    return runs;
  }

  // ============================================================================
  // Evidence Ledger 方法
  // ============================================================================

  /**
   * 添加证据到账本
   */
  public async addEvidenceEntry(entry: EvidenceLedgerEntry): Promise<void> {
    if (!this.currentProjectSlug) {
      throw new Error('[DossierWriter] 未设置当前项目');
    }

    const ledger = await this.readEvidenceLedger(this.currentProjectSlug);
    ledger.push(entry);
    await this.writeEvidenceLedger(ledger);

    console.log(`[DossierWriter] 添加证据: ${entry.evidence_id}`);
  }

  /**
   * 读取证据账本
   */
  public async readEvidenceLedger(projectSlug: string): Promise<EvidenceLedgerEntry[]> {
    const filePath = path.join(this.dossierRoot, projectSlug, 'evidence_ledger.json');

    if (!fs.existsSync(filePath)) {
      return [];
    }

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content);
    } catch (error) {
      console.error(`[DossierWriter] 读取证据账本失败:`, error);
      return [];
    }
  }

  /**
   * 写入证据账本
   */
  private async writeEvidenceLedger(ledger: EvidenceLedgerEntry[]): Promise<void> {
    if (!this.currentProjectSlug) {
      return;
    }

    const filePath = path.join(
      this.dossierRoot,
      this.currentProjectSlug,
      'evidence_ledger.json'
    );

    fs.writeFileSync(filePath, JSON.stringify(ledger, null, 2), 'utf-8');
  }

  // ============================================================================
  // Issue Graph 方法
  // ============================================================================

  /**
   * 更新议题图
   */
  private async addIssueToGraph(issue: Issue): Promise<void> {
    if (!this.currentProjectSlug) return;

    const graph = await this.readIssueGraph(this.currentProjectSlug);
    if (!graph) return;

    const node: IssueGraphNode = {
      issue_id: issue.issue_id,
      issue_title: issue.issue_title,
      status: issue.status,
    };

    const existingNodeIndex = graph.nodes.findIndex((n) => n.issue_id === issue.issue_id);
    if (existingNodeIndex >= 0) {
      graph.nodes[existingNodeIndex] = node;
    } else {
      graph.nodes.push(node);
    }

    await this.writeIssueGraph(graph);
  }

  /**
   * 读取议题图
   */
  private async readIssueGraph(projectSlug: string): Promise<IssueGraph | null> {
    const filePath = path.join(this.dossierRoot, projectSlug, 'issue_graph.json');

    if (!fs.existsSync(filePath)) {
      return null;
    }

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content);
    } catch (error) {
      console.error(`[DossierWriter] 读取议题图失败:`, error);
      return null;
    }
  }

  /**
   * 写入议题图
   */
  private async writeIssueGraph(graph: IssueGraph): Promise<void> {
    if (!this.currentProjectSlug) return;

    const filePath = path.join(
      this.dossierRoot,
      this.currentProjectSlug,
      'issue_graph.json'
    );

    fs.writeFileSync(filePath, JSON.stringify(graph, null, 2), 'utf-8');
  }

  // ============================================================================
  // Manifest 方法
  // ============================================================================

  /**
   * 写入清单
   */
  private async writeManifest(manifest: Manifest): Promise<void> {
    if (!this.currentProjectSlug) return;

    const filePath = path.join(
      this.dossierRoot,
      this.currentProjectSlug,
      'manifest.json'
    );

    fs.writeFileSync(filePath, JSON.stringify(manifest, null, 2), 'utf-8');
  }

  // ============================================================================
  // 工具方法
  // ============================================================================

  /**
   * 确保目录存在
   */
  private ensureDirectory(dirPath: string): void {
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }
  }

  /**
   * 获取当前项目slug
   */
  public getCurrentProjectSlug(): string | null {
    return this.currentProjectSlug;
  }

  /**
   * 列出所有项目
   */
  public listProjects(): string[] {
    if (!fs.existsSync(this.dossierRoot)) {
      return [];
    }

    return fs.readdirSync(this.dossierRoot).filter((f) => {
      const manifestPath = path.join(this.dossierRoot, f, 'manifest.json');
      return fs.existsSync(manifestPath);
    });
  }
}

// 单例导出
export const dossierWriter = new DossierWriter();
