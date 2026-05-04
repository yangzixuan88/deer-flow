/**
 * @file feishu_card_renderer.ts
 * @description 飞书卡片渲染器 - RTCM 输出到飞书卡片格式的转换
 */

import { SessionState, Issue, ChairSummary } from './types';

// ============================================================================
// Card Types
// ============================================================================

export enum FeishuCardType {
  RED_ALERT = 'red_alert',      // 重新打开/紧急
  YELLOW_MILESTONE = 'yellow_milestone', // 结论达成
  BLUE_PROGRESS = 'blue_progress', // 进展同步
  GRAY_SUMMARY = 'gray_summary',   // 摘要
}

export interface FeishuCard {
  type: FeishuCardType;
  title: string;
  description: string;
  elements: FeishuCardElement[];
  actions?: FeishuCardAction[];
  timestamp: string;
}

export interface FeishuCardElement {
  tag: string; // 'markdown' | 'div' | 'hr' | 'img'
  content?: string;
  href?: string;
}

export interface FeishuCardAction {
  type: 'click' | 'link';
  text: string;
  value: string;
}

// ============================================================================
// Feishu Card Renderer
// ============================================================================

export class FeishuCardRenderer {
  // Feishu API card header template mapping
  private static readonly TEMPLATE_MAP: Record<FeishuCardType, string> = {
    [FeishuCardType.RED_ALERT]: 'red',
    [FeishuCardType.YELLOW_MILESTONE]: 'yellow',
    [FeishuCardType.BLUE_PROGRESS]: 'blue',
    [FeishuCardType.GRAY_SUMMARY]: 'gray',
  };

  private toFeishuCard(type: FeishuCardType, title: string, elements: any[], actions?: FeishuCardAction[]): any {
    return {
      schema: '2.0',
      header: {
        title: { tag: 'plain_text', content: title },
        template: FeishuCardRenderer.TEMPLATE_MAP[type],
      },
      body: { elements },
    };
  }

  /**
   * 渲染重新打开卡片 (RED)
   */
  renderReopenCard(issue: Issue, reason: string): any {
    const elements = [
      { tag: 'markdown', content: `**原因**: ${reason}` },
      { tag: 'markdown', content: `**问题陈述**: ${issue.problem_statement}` },
      { tag: 'markdown', content: `**冲突证据**: ${issue.strongest_dissent}` },
      { tag: 'markdown', content: `**置信区间**: ${issue.confidence_interval}` },
      { tag: 'markdown', content: `**未解决的不确定项**: ${issue.unresolved_uncertainties.join(', ') || '无'}` },
    ];
    return this.toFeishuCard(FeishuCardType.RED_ALERT, `🔴 议题重新打开: ${issue.issue_title}`, elements);
  }

  /**
   * 渲染结论达成卡片 (YELLOW)
   */
  renderConsensusCard(issue: Issue, verdict: string): any {
    const elements = [
      { tag: 'markdown', content: `**裁决**: ${verdict}` },
      { tag: 'markdown', content: `**问题陈述**: ${issue.problem_statement}` },
      { tag: 'markdown', content: `**最强支持**: ${issue.validation_plan_or_result ? '已验证' : '待验证'}` },
      { tag: 'markdown', content: `**最大分歧**: ${issue.strongest_dissent || '无'}` },
      { tag: 'markdown', content: `**重新打开条件**: ${issue.conditions_to_reopen.join(', ') || '无'}` },
    ];
    return this.toFeishuCard(FeishuCardType.YELLOW_MILESTONE, `🟡 议题结论达成: ${issue.issue_title}`, elements);
  }

  /**
   * 渲染进展同步卡片 (BLUE)
   */
  renderProgressCard(session: SessionState, currentTask: string): any {
    const duration = this.calculateDuration(session);
    const elements = [
      { tag: 'markdown', content: `**当前任务**: ${currentTask}` },
      { tag: 'markdown', content: `**轮次**: 第 ${session.current_round} 轮` },
      { tag: 'markdown', content: `**阶段**: ${session.current_stage}` },
      { tag: 'markdown', content: `**议题**: ${session.current_issue_id || '无'}` },
      { tag: 'markdown', content: `**已耗时**: ${duration}` },
      { tag: 'markdown', content: `**活跃成员**: ${session.active_members.join(', ') || '无'}` },
    ];
    return this.toFeishuCard(FeishuCardType.BLUE_PROGRESS, '🔵 RTCM 执行进度同步', elements);
  }

  /**
   * 渲染摘要卡片 (GRAY)
   */
  renderSummaryCard(session: SessionState, chairSummary: ChairSummary | null): any {
    const elements = [
      { tag: 'markdown', content: `**会话ID**: ${session.session_id}` },
      { tag: 'markdown', content: `**当前共识**: ${chairSummary?.current_consensus.join(', ') || '无'}` },
      { tag: 'markdown', content: `**当前冲突**: ${chairSummary?.current_conflicts.join(', ') || '无'}` },
      { tag: 'markdown', content: `**最强支持**: ${chairSummary?.strongest_support || '无'}` },
      { tag: 'markdown', content: `**最强分歧**: ${chairSummary?.strongest_dissent || '无'}` },
      { tag: 'markdown', content: `**推荐下一步**: ${chairSummary?.recommended_state_transition || '无'}` },
    ];
    return this.toFeishuCard(FeishuCardType.GRAY_SUMMARY, '⚪ RTCM 轮次摘要', elements);
  }

  /**
   * 渲染证据冲突告警卡片 (RED - 特殊)
   */
  renderConflictCard(issue: Issue, conflicts: string[]): any {
    const elements = [
      { tag: 'markdown', content: `**检测到 ${conflicts.length} 个证据冲突项**` },
      ...conflicts.map(c => ({ tag: 'markdown', content: c } as any)),
    ];
    return this.toFeishuCard(FeishuCardType.RED_ALERT, `🔴 证据冲突检测: ${issue.issue_title}`, elements);
  }

  /**
   * 批量渲染当前状态
   */
  renderStateSnapshot(session: SessionState, issues: Issue[]): FeishuCard[] {
    const cards: FeishuCard[] = [];

    // 检查是否有 reopen 的议题
    const reopenIssues = issues.filter(i => i.status === 'reopened');
    if (reopenIssues.length > 0) {
      cards.push(this.renderReopenCard(reopenIssues[0], 'auto_reopen triggered'));
    }

    // 检查是否有已完成的议题
    const completedIssues = issues.filter(i => i.verdict !== null);
    if (completedIssues.length > 0) {
      const latest = completedIssues[completedIssues.length - 1];
      cards.push(this.renderConsensusCard(latest, latest.verdict!));
    }

    // 总是添加进展卡片
    cards.push(this.renderProgressCard(session, 'issue_processing'));

    return cards;
  }

  /**
   * 计算已耗时
   */
  private calculateDuration(session: SessionState): string {
    const created = new Date(session.created_at);
    const now = new Date();
    const diffMs = now.getTime() - created.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffSec = Math.floor((diffMs % 60000) / 1000);
    return `${diffMin}分${diffSec}秒`;
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const feishuCardRenderer = new FeishuCardRenderer();