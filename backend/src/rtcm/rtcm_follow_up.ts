/**
 * @file rtcm_follow_up.ts
 * @description RTCM FOLLOW_UP 与 stage_closed_but_thread_open - Delta 生产验证态核心
 * 同线程内基于旧成果继续推进新会议任务
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import * as crypto from 'crypto';
import { Issue, SessionState } from './types';
import { threadAdapter } from './rtcm_thread_adapter';

// ============================================================================
// Types
// ============================================================================

export enum ExtendedSessionStatus {
  ACTIVE_DISCUSSION = 'active_discussion',
  WAITING_FOR_USER = 'waiting_for_user',
  PAUSED = 'paused',
  STAGE_CLOSED_BUT_THREAD_OPEN = 'stage_closed_but_thread_open',
  REOPENED = 'reopened',
  ARCHIVED = 'archived',
}

export interface FollowUpIssue extends Issue {
  isFollowUp: boolean;
  parentIssueId: string | null;
  inheritedAssets: string[];  // 从旧 issue 继承的证据/结论
  followUpRequestText: string;
}

export interface FollowUpRequest {
  requestId: string;
  threadId: string;
  sessionId: string;
  parentIssueId: string;
  newIssueTitle: string;
  newIssueDescription: string;
  inheritedAssets: string[];
  createdAt: string;
  followUpType: 'continue_discussion' | 'deep_dive' | 'new_topic_based_on_conclusion';
}

export interface SessionContinuationContext {
  sessionId: string;
  threadId: string;
  previousIssues: Issue[];
  inheritedConclusions: string[];
  inheritedEvidence: string[];
  unresolvedUncertainties: string[];
  activeProjectStatus: ExtendedSessionStatus;
}

// ============================================================================
// Follow-Up Manager
// ============================================================================

export class FollowUpManager {
  private followUpDir: string;

  constructor() {
    this.followUpDir = runtimePath('rtcm', 'followups');
    this.ensureDir(this.followUpDir);
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  // ===========================================================================
  // Session Status Management
  // ===========================================================================

  /**
   * 检查是否应该进入 stage_closed_but_thread_open 状态
   */
  shouldEnterStageClosedButThreadOpen(session: SessionState): boolean {
    // 当 issue verdict 已达成且用户接受后
    return session.pending_user_acceptance === false &&
           session.status === 'validation' &&
           session.reopen_flag === false;
  }

  /**
   * 将 session 设为 stage_closed_but_thread_open
   */
  enterStageClosedButThreadOpen(sessionId: string, threadId: string): void {
    // 更新 thread 状态
    threadAdapter.closeStageButKeepThreadOpen(threadId);

    // 记录状态变更
    const statusFile = path.join(this.followUpDir, `${sessionId}_status.json`);
    fs.writeFileSync(statusFile, JSON.stringify({
      sessionId,
      threadId,
      previousStatus: 'active',
      newStatus: ExtendedSessionStatus.STAGE_CLOSED_BUT_THREAD_OPEN,
      changedAt: new Date().toISOString(),
    }, null, 2), 'utf-8');
  }

  /**
   * 检查线程是否处于 stage_closed_but_thread_open 状态
   */
  isStageClosedButThreadOpen(threadId: string): boolean {
    const binding = threadAdapter.getThreadBinding(threadId);
    return binding?.status === 'stage_closed_but_thread_open';
  }

  /**
   * 从 stage_closed_but_thread_open 恢复
   */
  exitStageClosedButThreadOpen(threadId: string): void {
    const binding = threadAdapter.getThreadBinding(threadId);
    if (binding && binding.status === 'stage_closed_but_thread_open') {
      binding.status = 'active';
      binding.updatedAt = new Date().toISOString();
    }
  }

  // ===========================================================================
  // Follow-Up Issue Creation
  // ===========================================================================

  /**
   * 创建 FOLLOW_UP issue
   */
  createFollowUpIssue(params: {
    threadId: string;
    sessionId: string;
    parentIssueId: string;
    parentIssueTitle: string;
    newIssueTitle: string;
    newIssueDescription: string;
    inheritedAssets: string[];
    followUpRequestText: string;
    followUpType: FollowUpRequest['followUpType'];
  }): FollowUpIssue {
    const issueId = `followup-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;

    const followUpIssue: FollowUpIssue = {
      issue_id: issueId,
      issue_title: params.newIssueTitle,
      problem_statement: params.newIssueDescription,
      why_it_matters: `基于旧议题 "${params.parentIssueTitle}" 的 FOLLOW_UP`,
      candidate_hypotheses: [],
      evidence_summary: '',
      challenge_log: [],
      response_summary: '',
      known_gaps: [],
      validation_plan_or_result: null as any,
      verdict: null,
      status: 'created',
      strongest_dissent: '',
      confidence_interval: '',
      unresolved_uncertainties: [],
      conditions_to_reopen: [],
      evidence_ledger_refs: [],
      // Follow-up specific fields
      isFollowUp: true,
      parentIssueId: params.parentIssueId,
      inheritedAssets: params.inheritedAssets,
      followUpRequestText: params.followUpRequestText,
    };

    // 记录 FOLLOW_UP 请求
    const request: FollowUpRequest = {
      requestId: `req-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`,
      threadId: params.threadId,
      sessionId: params.sessionId,
      parentIssueId: params.parentIssueId,
      newIssueTitle: params.newIssueTitle,
      newIssueDescription: params.newIssueDescription,
      inheritedAssets: params.inheritedAssets,
      createdAt: new Date().toISOString(),
      followUpType: params.followUpType,
    };

    this.logFollowUpRequest(request);

    // 如果线程处于 stage_closed_but_thread_open，需要恢复为 active
    if (this.isStageClosedButThreadOpen(params.threadId)) {
      this.exitStageClosedButThreadOpen(params.threadId);
    }

    return followUpIssue;
  }

  /**
   * 确定 FOLLOW_UP 类型
   */
  determineFollowUpType(userMessage: string): FollowUpRequest['followUpType'] {
    const lower = userMessage.toLowerCase();

    if (lower.includes('继续讨论') || lower.includes('接着')) {
      return 'continue_discussion';
    }
    if (lower.includes('深挖') || lower.includes('详细')) {
      return 'deep_dive';
    }
    // 默认基于结论的新议题
    return 'new_topic_based_on_conclusion';
  }

  /**
   * 从旧 issue 提取可继承的资产
   */
  extractInheritedAssets(parentIssue: Issue): string[] {
    const assets: string[] = [];

    // 继承结论
    if (parentIssue.verdict) {
      assets.push(`verdict:${parentIssue.verdict}`);
    }

    // 继承最强支持证据
    if (parentIssue.strongest_dissent) {
      assets.push(`dissent:${parentIssue.strongest_dissent}`);
    }

    // 继承置信区间
    if (parentIssue.confidence_interval) {
      assets.push(`confidence:${parentIssue.confidence_interval}`);
    }

    // 继承证据引用
    assets.push(...parentIssue.evidence_ledger_refs);

    // 继承未决不确定性（需要在新议题中继续处理）
    for (const uncertainty of parentIssue.unresolved_uncertainties) {
      assets.push(`unresolved:${uncertainty}`);
    }

    return assets;
  }

  // ===========================================================================
  // Session Continuation Context
  // ===========================================================================

  /**
   * 构建续会上下文
   */
  buildContinuationContext(sessionId: string, threadId: string): SessionContinuationContext {
    // 读取会话目录中的 issues
    const issuesDir = runtimePath('rtcm', 'dossiers', sessionId, 'issues');
    const previousIssues: Issue[] = [];

    if (fs.existsSync(issuesDir)) {
      const files = fs.readdirSync(issuesDir).filter(f => f.endsWith('.json'));
      for (const file of files) {
        const issue = JSON.parse(fs.readFileSync(path.join(issuesDir, file), 'utf-8'));
        previousIssues.push(issue);
      }
    }

    // 提取已完成的结论
    const inheritedConclusions: string[] = [];
    const inheritedEvidence: string[] = [];
    const unresolvedUncertainties: string[] = [];

    for (const issue of previousIssues) {
      if (issue.verdict) {
        inheritedConclusions.push(`[${issue.issue_id}] ${issue.verdict}: ${issue.issue_title}`);
      }
      if (issue.strongest_dissent) {
        inheritedEvidence.push(issue.strongest_dissent);
      }
      unresolvedUncertainties.push(...(issue.unresolved_uncertainties || []));
    }

    return {
      sessionId,
      threadId,
      previousIssues,
      inheritedConclusions,
      inheritedEvidence,
      unresolvedUncertainties: [...new Set(unresolvedUncertainties)],
      activeProjectStatus: ExtendedSessionStatus.ACTIVE_DISCUSSION,
    };
  }

  /**
   * 获取项目的 FOLLOW_UP 历史
   */
  getFollowUpHistory(sessionId: string): {
    totalFollowUps: number;
    followUpIssues: FollowUpIssue[];
  } {
    const followUpFile = path.join(this.followUpDir, `${sessionId}_followups.jsonl`);
    const followUpIssues: FollowUpIssue[] = [];

    if (fs.existsSync(followUpFile)) {
      const lines = fs.readFileSync(followUpFile, 'utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        const req = JSON.parse(line) as FollowUpRequest;
        // 这里简化处理，实际应该读取 issue 数据
        followUpIssues.push({
          issue_id: req.requestId,
          issue_title: req.newIssueTitle,
          problem_statement: req.newIssueDescription,
          why_it_matters: '',
          candidate_hypotheses: [],
          evidence_summary: '',
          challenge_log: [],
          response_summary: '',
          known_gaps: [],
          validation_plan_or_result: null as any,
          verdict: null,
          status: 'created',
          strongest_dissent: '',
          confidence_interval: '',
          unresolved_uncertainties: [],
          conditions_to_reopen: [],
          evidence_ledger_refs: [],
          isFollowUp: true,
          parentIssueId: req.parentIssueId,
          inheritedAssets: req.inheritedAssets,
          followUpRequestText: req.newIssueTitle,
        });
      }
    }

    return {
      totalFollowUps: followUpIssues.length,
      followUpIssues,
    };
  }

  // ===========================================================================
  // Persistence
  // ===========================================================================

  private logFollowUpRequest(request: FollowUpRequest): void {
    const filePath = path.join(this.followUpDir, `${request.sessionId}_followups.jsonl`);
    fs.appendFileSync(filePath, JSON.stringify(request) + '\n', 'utf-8');
  }

  /**
   * 获取可续会的项目列表
   */
  listResumableProjects(): Array<{
    sessionId: string;
    threadId: string;
    status: ExtendedSessionStatus;
    lastActivity: string;
  }> {
    const projects: Array<{
      sessionId: string;
      threadId: string;
      status: ExtendedSessionStatus;
      lastActivity: string;
    }> = [];

    if (!fs.existsSync(this.followUpDir)) return projects;

    const files = fs.readdirSync(this.followUpDir).filter(f => f.endsWith('_status.json'));
    for (const file of files) {
      const content = fs.readFileSync(path.join(this.followUpDir, file), 'utf-8');
      const status = JSON.parse(content);
      projects.push({
        sessionId: status.sessionId,
        threadId: status.threadId,
        status: status.newStatus,
        lastActivity: status.changedAt,
      });
    }

    return projects;
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const followUpManager = new FollowUpManager();
