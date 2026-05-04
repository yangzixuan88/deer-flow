/**
 * @file nightly_export_adapter.ts
 * @description 夜间学习导出适配器 - RTCM → GEPA 的最小循环
 * 将 RTCM 结论导出为 NightlyDistiller 可消费的 ExperiencePackage 格式
 */

import { SessionState, Issue, Verdict } from './types';
// 导入 NightlyDistiller 和 GEPAExperience
import { NightlyDistiller, ExperiencePackage, GEPAExperience } from '../domain/nightly_distiller';

// ============================================================================
// Types
// ============================================================================

export interface RTCMSessionExport {
  sessionId: string;
  projectId: string;
  projectName: string;
  completedIssues: Issue[];
  unresolvedIssues: Issue[];
  chairSummaries: string[];
  totalRounds: number;
  duration: number;
}

export interface ExportResult {
  exportedCount: number;
  experiencePackages: ExperiencePackage[];
  gepaExperiences: GEPAExperience[];
  errors: string[];
}

// ============================================================================
// Nightly Export Adapter
// ============================================================================

export class NightlyExportAdapter {
  private distiller: NightlyDistiller;

  constructor() {
    this.distiller = new NightlyDistiller();
  }

  /**
   * 将 RTCM 会话状态转换为 ExperiencePackage
   */
  sessionToExperiencePackages(session: SessionState, issues: Issue[]): ExperiencePackage[] {
    const packages: ExperiencePackage[] = [];

    for (const issue of issues) {
      const pkg = this.issueToExperiencePackage(session, issue);
      packages.push(pkg);
    }

    return packages;
  }

  /**
   * 将单个 Issue 转换为 ExperiencePackage
   */
  private issueToExperiencePackage(session: SessionState, issue: Issue): ExperiencePackage {
    const hasVerdict = issue.verdict !== null;
    const qualityScore = hasVerdict ? 0.85 : 0.5;

    // 从议程标题提取 intent
    const intent = issue.issue_title;

    // 构建 tool_calls 序列（模拟）
    const toolCalls = this.buildToolCalls(issue);

    return {
      id: `exp-${session.session_id.slice(-8)}-${issue.issue_id.slice(-4)}`,
      timestamp: session.updated_at,
      session_id: session.session_id,
      task_goal: issue.problem_statement,
      category: 'workflow',
      model_used: 'rtcm-multiple',
      tool_calls: toolCalls,
      total_tokens: this.estimateTokens(issue),
      total_duration_ms: this.estimateDuration(session),
      result_quality: qualityScore,
      reusable_patterns: this.extractPatterns(issue),
      failure_info: hasVerdict ? null : {
        error: 'Verdict not reached',
        step: 'hypothesis_building',
        recovery: 'Needs more evidence or user intervention'
      },
      search_triggers: this.extractSearchTriggers(issue),
      asset_hits: this.extractAssetRefs(issue),
    };
  }

  /**
   * 构建工具调用序列
   */
  private buildToolCalls(issue: Issue): ExperiencePackage['tool_calls'] {
    const calls: ExperiencePackage['tool_calls'] = [];

    // 模拟各阶段的工具调用
    calls.push({
      tool: 'define_issue',
      input: issue.issue_title,
      output_summary: issue.problem_statement,
      success: true,
      duration_ms: 100
    });

    calls.push({
      tool: 'build_hypotheses',
      input: `${issue.candidate_hypotheses.length} hypotheses`,
      output_summary: issue.candidate_hypotheses.map(h => h.id).join(', '),
      success: true,
      duration_ms: 500
    });

    if (issue.validation_plan_or_result) {
      calls.push({
        tool: 'validate_evidence',
        input: 'validation_plan',
        output_summary: 'validation_completed',
        success: issue.verdict !== null,
        duration_ms: 300
      });
    }

    return calls;
  }

  /**
   * 估算 token 消耗
   */
  private estimateTokens(issue: Issue): number {
    // 简单估算：基于假设数量和证据长度
    const baseTokens = 500;
    const hypothesisTokens = issue.candidate_hypotheses.length * 100;
    const evidenceTokens = issue.evidence_summary.length / 2;
    return Math.floor(baseTokens + hypothesisTokens + evidenceTokens);
  }

  /**
   * 估算会话时长
   */
  private estimateDuration(session: SessionState): number {
    const created = new Date(session.created_at).getTime();
    const updated = new Date(session.updated_at).getTime();
    return updated - created;
  }

  /**
   * 提取可复用模式
   */
  private extractPatterns(issue: Issue): ExperiencePackage['reusable_patterns'] {
    const patterns: ExperiencePackage['reusable_patterns'] = [];

    // 从结论中提取模式
    if (issue.verdict) {
      patterns.push({
        pattern: `verdict_${issue.verdict.toLowerCase()}`,
        description: `达成${issue.verdict}结论的流程`,
        confidence: 0.8
      });
    }

    // 从最强分歧中提取模式
    if (issue.strongest_dissent) {
      patterns.push({
        pattern: 'dissent_handling',
        description: '处理分歧意见的方法',
        confidence: 0.7
      });
    }

    return patterns;
  }

  /**
   * 提取搜索触发词
   */
  private extractSearchTriggers(issue: Issue): string[] {
    const triggers: string[] = [];

    // 从问题陈述中提取关键词
    const words = issue.problem_statement.split(/\s+/);
    triggers.push(...words.slice(0, 3));

    // 从假设中提取
    for (const h of issue.candidate_hypotheses) {
      const titleWords = h.title.split(/\s+/);
      triggers.push(...titleWords.slice(0, 2));
    }

    return [...new Set(triggers)].slice(0, 5);
  }

  /**
   * 提取资产引用
   */
  private extractAssetRefs(issue: Issue): string[] {
    return issue.evidence_ledger_refs.slice(0, 3);
  }

  /**
   * 将 RTCM 会话转换为 GEPA Experience
   */
  sessionToGEPAExperiences(session: SessionState, issues: Issue[]): GEPAExperience[] {
    const experiences: GEPAExperience[] = [];

    for (const issue of issues) {
      if (issue.verdict && issue.confidence_interval) {
        const exp: GEPAExperience = {
          intent: issue.issue_title,
          action_path: this.buildActionPath(issue),
          success: true,
          qualityScore: this.parseConfidence(issue.confidence_interval),
          date: session.updated_at,
        };
        experiences.push(exp);
      }
    }

    return experiences;
  }

  /**
   * 构建动作路径
   */
  private buildActionPath(issue: Issue): string[] {
    const path: string[] = ['define_issue'];

    if (issue.candidate_hypotheses.length > 0) {
      path.push('build_hypotheses');
    }

    if (issue.validation_plan_or_result) {
      path.push('validate_evidence');
    }

    if (issue.verdict) {
      path.push('reach_verdict');
    }

    return path;
  }

  /**
   * 解析置信区间为分数
   */
  private parseConfidence(interval: string): number {
    // 简单解析，如 "85%" -> 0.85
    const match = interval.match(/(\d+)/);
    if (match) {
      return Math.min(parseInt(match[1]) / 100, 1);
    }
    return 0.5;
  }

  /**
   * 执行最小导出循环
   */
  async executeExportLoop(session: SessionState, issues: Issue[]): Promise<ExportResult> {
    const result: ExportResult = {
      exportedCount: 0,
      experiencePackages: [],
      gepaExperiences: [],
      errors: []
    };

    try {
      // 1. 转换为 ExperiencePackage
      result.experiencePackages = this.sessionToExperiencePackages(session, issues);
      result.exportedCount = result.experiencePackages.length;

      // 2. 转换为 GEPA Experience
      result.gepaExperiences = this.sessionToGEPAExperiences(session, issues);

      // 3. 可选：直接调用 NightlyDistiller 的六阶段流程
      if (result.experiencePackages.length > 0) {
        const report = await this.distiller.executeSixStageReview(
          result.experiencePackages,
          result.gepaExperiences
        );
        console.log(`[NightlyExportAdapter] GEPA report generated: ${report.date}`);
      }
    } catch (error) {
      result.errors.push(String(error));
    }

    return result;
  }

  /**
   * 批量导出多个会话
   */
  async exportMultipleSessions(
    exports: RTCMSessionExport[]
  ): Promise<ExportResult[]> {
    const results: ExportResult[] = [];

    for (const exp of exports) {
      // 构建伪 session state
      const session: SessionState = {
        session_id: exp.sessionId,
        project_id: exp.projectId,
        project_name: exp.projectName,
        mode: 'rtcm',
        status: 'archived',
        current_issue_id: null,
        current_stage: 'completed',
        current_round: exp.totalRounds,
        active_members: [],
        lease_state: { granted: false, granted_by: null, granted_at: null },
        latest_chair_summary: null,
        latest_supervisor_check: null,
        user_presence_status: 'absent',
        pending_user_acceptance: false,
        reopen_flag: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };

      const result = await this.executeExportLoop(
        session,
        [...exp.completedIssues, ...exp.unresolvedIssues]
      );
      results.push(result);
    }

    return results;
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const nightlyExportAdapter = new NightlyExportAdapter();