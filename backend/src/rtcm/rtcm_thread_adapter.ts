/**
 * @file rtcm_thread_adapter.ts
 * @description RTCM 飞书线程持续会议适配器 - Delta 生产验证态核心
 * 主会话负责入口，线程负责现场，同线程持续推进
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import * as crypto from 'crypto';
import { SessionState, Issue, ChairSummary, SupervisorCheck } from './types';

// ============================================================================
// Types - Thread & Session Binding
// ============================================================================

export enum ThreadDisplayMode {
  CONCISE = 'concise',     // 简洁视图
  MEMBER = 'member',       // 议员视图
  DEBATE = 'debate',       // 辩论视图
  FULL_LOG = 'full_log',   // 全量纪要视图
}

export enum SessionMode {
  NEW = 'new',
  CONTINUE = 'continue',
  REOPEN = 'reopen',
  FOLLOW_UP = 'follow_up',
}

export interface ThreadBinding {
  threadId: string;
  projectId: string;
  projectName: string;
  sessionId: string;
  createdAt: string;
  updatedAt: string;
  displayMode: ThreadDisplayMode;
  status: 'active' | 'stage_closed_but_thread_open' | 'reopened' | 'archived';
  currentIssueId: string | null;
  currentRound: number;
  mainChatMessageId: string | null; // 主会话中的启动卡片消息 ID
}

export interface ThreadAnchorMessage {
  threadId: string;
  projectId: string;
  projectName: string;
  currentIssueTitle: string;
  currentStage: string;
  currentProblem: string;
  currentRound: number;
  latestConsensus: string[];
  strongestDissent: string;
  unresolvedUncertainties: string[];
  nextAction: string;
  status: string;
  updatedAt: string;
}

export interface RoleMessage {
  round: number;
  stage: string;
  roleId: string;
  roleName: string;
  content: string;
  timestamp: string;
}

export interface ChairSummaryMessage {
  round: number;
  current_consensus: string[];
  current_conflicts: string[];
  strongest_support: string;
  strongest_dissent: string;
  unresolved_uncertainties: string[];
  recommended_state_transition: string;
  timestamp: string;
}

export interface SupervisorGateMessage {
  round: number;
  passed: boolean;
  violations: string[];
  dissent_present: boolean;
  uncertainty_present: boolean;
  recommendation: 'continue' | 'pause' | 'reopen' | 'escalate';
  timestamp: string;
}

// ============================================================================
// Thread Adapter
// ============================================================================

export class ThreadAdapter {
  private baseDir: string;
  private threadBindings: Map<string, ThreadBinding> = new Map();

  constructor() {
    this.baseDir = runtimePath('rtcm', 'threads');
    this.ensureDir(this.baseDir);
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  // ===========================================================================
  // Thread Creation & Binding
  // ===========================================================================

  /**
   * 创建新项目线程
   * 线程标题固定格式：【RTCM】<项目名称>
   */
  createThread(projectId: string, projectName: string, mainChatMessageId?: string): ThreadBinding {
    const threadId = `thread-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
    const sessionId = `rtcm-${projectId}`;

    const binding: ThreadBinding = {
      threadId,
      projectId,
      projectName,
      sessionId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      displayMode: ThreadDisplayMode.CONCISE,
      status: 'active',
      currentIssueId: null,
      currentRound: 0,
      mainChatMessageId: mainChatMessageId || null,
    };

    // 保存线程绑定
    this.threadBindings.set(threadId, binding);
    this.saveThreadBinding(binding);

    // 创建线程目录
    const threadDir = path.join(this.baseDir, threadId);
    this.ensureDir(threadDir);
    this.ensureDir(path.join(threadDir, 'messages'));
    this.ensureDir(path.join(threadDir, 'dossier'));

    return binding;
  }

  /**
   * 绑定已有线程到项目
   */
  bindThread(projectId: string, threadId: string): boolean {
    const binding = this.readThreadBinding(threadId);
    if (!binding) return false;

    binding.projectId = projectId;
    binding.updatedAt = new Date().toISOString();
    this.saveThreadBinding(binding);
    this.threadBindings.set(threadId, binding);

    return true;
  }

  /**
   * 根据 sessionId 查找线程
   */
  findThreadBySession(sessionId: string): ThreadBinding | null {
    for (const [, binding] of this.threadBindings) {
      if (binding.sessionId === sessionId) {
        return binding;
      }
    }
    // 尝试从磁盘加载
    const dirs = fs.readdirSync(this.baseDir).filter(f => !f.startsWith('.'));
    for (const dir of dirs) {
      const binding = this.readThreadBinding(dir);
      if (binding && binding.sessionId === sessionId) {
        this.threadBindings.set(dir, binding);
        return binding;
      }
    }
    return null;
  }

  // ===========================================================================
  // Thread Status Management
  // ===========================================================================

  /**
   * 更新线程状态
   */
  updateThreadStatus(threadId: string, status: ThreadBinding['status']): void {
    const binding = this.getThreadBinding(threadId);
    if (!binding) return;

    binding.status = status;
    binding.updatedAt = new Date().toISOString();
    this.saveThreadBinding(binding);
  }

  /**
   * 设置 stage_closed_but_thread_open 状态
   */
  closeStageButKeepThreadOpen(threadId: string): void {
    this.updateThreadStatus(threadId, 'stage_closed_but_thread_open');
  }

  /**
   * 重开线程
   */
  reopenThread(threadId: string): void {
    const binding = this.getThreadBinding(threadId);
    if (!binding) return;

    binding.status = 'reopened';
    binding.updatedAt = new Date().toISOString();
    this.saveThreadBinding(binding);
  }

  // ===========================================================================
  // Anchor Message
  // ===========================================================================

  /**
   * 生成/更新顶部锚点消息
   */
  updateAnchorMessage(threadId: string, params: {
    currentIssueTitle: string;
    currentStage: string;
    currentProblem: string;
    latestConsensus: string[];
    strongestDissent: string;
    unresolvedUncertainties: string[];
    nextAction: string;
  }): ThreadAnchorMessage {
    const binding = this.getThreadBinding(threadId);
    if (!binding) throw new Error('Thread not found');

    const anchor: ThreadAnchorMessage = {
      threadId,
      projectId: binding.projectId,
      projectName: binding.projectName,
      currentIssueTitle: params.currentIssueTitle,
      currentStage: params.currentStage,
      currentProblem: params.currentProblem,
      currentRound: binding.currentRound,
      latestConsensus: params.latestConsensus,
      strongestDissent: params.strongestDissent,
      unresolvedUncertainties: params.unresolvedUncertainties,
      nextAction: params.nextAction,
      status: binding.status,
      updatedAt: new Date().toISOString(),
    };

    // 保存锚点消息
    const anchorFile = path.join(this.baseDir, threadId, 'anchor_message.json');
    fs.writeFileSync(anchorFile, JSON.stringify(anchor, null, 2), 'utf-8');

    return anchor;
  }

  /**
   * 读取锚点消息
   */
  readAnchorMessage(threadId: string): ThreadAnchorMessage | null {
    const anchorFile = path.join(this.baseDir, threadId, 'anchor_message.json');
    if (!fs.existsSync(anchorFile)) return null;
    return JSON.parse(fs.readFileSync(anchorFile, 'utf-8'));
  }

  // ===========================================================================
  // Message Handling
  // ===========================================================================

  /**
   * 写入角色消息到线程
   */
  appendRoleMessage(threadId: string, message: RoleMessage): void {
    const msgFile = path.join(this.baseDir, threadId, 'messages', 'role_messages.jsonl');
    fs.appendFileSync(msgFile, JSON.stringify(message) + '\n', 'utf-8');
  }

  /**
   * 写入主持官总结
   */
  appendChairSummary(threadId: string, summary: ChairSummaryMessage): void {
    const summaryFile = path.join(this.baseDir, threadId, 'messages', 'chair_summaries.jsonl');
    fs.appendFileSync(summaryFile, JSON.stringify(summary) + '\n', 'utf-8');
  }

  /**
   * 写入监督官 gate 消息
   */
  appendSupervisorGate(threadId: string, gate: SupervisorGateMessage): void {
    const gateFile = path.join(this.baseDir, threadId, 'messages', 'supervisor_gates.jsonl');
    fs.appendFileSync(gateFile, JSON.stringify(gate) + '\n', 'utf-8');
  }

  /**
   * 读取线程消息历史
   */
  readThreadMessages(threadId: string, limit?: number): {
    roleMessages: RoleMessage[];
    chairSummaries: ChairSummaryMessage[];
    supervisorGates: SupervisorGateMessage[];
  } {
    const roleMessages: RoleMessage[] = [];
    const chairSummaries: ChairSummaryMessage[] = [];
    const supervisorGates: SupervisorGateMessage[] = [];

    const msgDir = path.join(this.baseDir, threadId, 'messages');

    // 读取角色消息
    const roleFile = path.join(msgDir, 'role_messages.jsonl');
    if (fs.existsSync(roleFile)) {
      const lines = fs.readFileSync(roleFile, 'utf-8').split('\n').filter(Boolean);
      const filtered = limit ? lines.slice(-limit) : lines;
      filtered.forEach(line => roleMessages.push(JSON.parse(line)));
    }

    // 读取主持官总结
    const summaryFile = path.join(msgDir, 'chair_summaries.jsonl');
    if (fs.existsSync(summaryFile)) {
      const lines = fs.readFileSync(summaryFile, 'utf-8').split('\n').filter(Boolean);
      lines.forEach(line => chairSummaries.push(JSON.parse(line)));
    }

    // 读取监督官 gate
    const gateFile = path.join(msgDir, 'supervisor_gates.jsonl');
    if (fs.existsSync(gateFile)) {
      const lines = fs.readFileSync(gateFile, 'utf-8').split('\n').filter(Boolean);
      lines.forEach(line => supervisorGates.push(JSON.parse(line)));
    }

    return { roleMessages, chairSummaries, supervisorGates };
  }

  // ===========================================================================
  // Display Mode
  // ===========================================================================

  /**
   * 切换显示模式（只改展示，不改状态）
   */
  setDisplayMode(threadId: string, mode: ThreadDisplayMode): void {
    const binding = this.getThreadBinding(threadId);
    if (!binding) return;

    binding.displayMode = mode;
    binding.updatedAt = new Date().toISOString();
    this.saveThreadBinding(binding);
  }

  /**
   * 获取当前显示模式
   */
  getDisplayMode(threadId: string): ThreadDisplayMode {
    const binding = this.getThreadBinding(threadId);
    return binding?.displayMode || ThreadDisplayMode.CONCISE;
  }

  /**
   * 根据显示模式生成视图数据
   */
  generateViewData(threadId: string): {
    displayMode: ThreadDisplayMode;
    anchorMessage: ThreadAnchorMessage | null;
    viewContent: object;
  } {
    const binding = this.getThreadBinding(threadId);
    if (!binding) throw new Error('Thread not found');

    const anchorMessage = this.readAnchorMessage(threadId);
    const { roleMessages, chairSummaries, supervisorGates } = this.readThreadMessages(threadId);

    let viewContent: object;

    switch (binding.displayMode) {
      case ThreadDisplayMode.CONCISE:
        viewContent = {
          currentStage: anchorMessage?.currentStage,
          currentProblem: anchorMessage?.currentProblem,
          chairSummary: chairSummaries[chairSummaries.length - 1],
          nextAction: anchorMessage?.nextAction,
        };
        break;

      case ThreadDisplayMode.MEMBER:
        viewContent = {
          roles: roleMessages.map(m => ({
            roleId: m.roleId,
            roleName: m.roleName,
            content: m.content,
            round: m.round,
          })),
        };
        break;

      case ThreadDisplayMode.DEBATE:
        viewContent = {
          proposals: roleMessages.filter(m => m.stage === 'proposal').map(m => m.content),
          challenges: roleMessages.filter(m => m.stage === 'challenge').map(m => m.content),
          responses: roleMessages.filter(m => m.stage === 'response').map(m => m.content),
          gaps: roleMessages.filter(m => m.stage === 'gap').map(m => m.content),
          verdict: chairSummaries[chairSummaries.length - 1]?.recommended_state_transition,
        };
        break;

      case ThreadDisplayMode.FULL_LOG:
      default:
        viewContent = {
          roleMessages,
          chairSummaries,
          supervisorGates,
        };
        break;
    }

    return {
      displayMode: binding.displayMode,
      anchorMessage,
      viewContent,
    };
  }

  // ===========================================================================
  // Session Update
  // ===========================================================================

  /**
   * 更新当前 issue 和 round
   */
  updateCurrentIssue(threadId: string, issueId: string, round: number): void {
    const binding = this.getThreadBinding(threadId);
    if (!binding) return;

    binding.currentIssueId = issueId;
    binding.currentRound = round;
    binding.updatedAt = new Date().toISOString();
    this.saveThreadBinding(binding);
  }

  // ===========================================================================
  // Persistence
  // ===========================================================================

  private saveThreadBinding(binding: ThreadBinding): void {
    const filePath = path.join(this.baseDir, binding.threadId, 'binding.json');
    const dir = path.dirname(filePath);
    this.ensureDir(dir);
    fs.writeFileSync(filePath, JSON.stringify(binding, null, 2), 'utf-8');
  }

  private readThreadBinding(threadId: string): ThreadBinding | null {
    const filePath = path.join(this.baseDir, threadId, 'binding.json');
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  }

  getThreadBinding(threadId: string): ThreadBinding | null {
    if (this.threadBindings.has(threadId)) {
      return this.threadBindings.get(threadId)!;
    }
    return this.readThreadBinding(threadId);
  }

  // ===========================================================================
  // Thread Listing
  // ===========================================================================

  listActiveThreads(): ThreadBinding[] {
    const threads: ThreadBinding[] = [];
    if (!fs.existsSync(this.baseDir)) return threads;

    const dirs = fs.readdirSync(this.baseDir).filter(f => !f.startsWith('.'));
    for (const dir of dirs) {
      const binding = this.readThreadBinding(dir);
      if (binding && binding.status === 'active') {
        threads.push(binding);
      }
    }
    return threads;
  }

  listStageClosedThreads(): ThreadBinding[] {
    const threads: ThreadBinding[] = [];
    if (!fs.existsSync(this.baseDir)) return threads;

    const dirs = fs.readdirSync(this.baseDir).filter(f => !f.startsWith('.'));
    for (const dir of dirs) {
      const binding = this.readThreadBinding(dir);
      if (binding && binding.status === 'stage_closed_but_thread_open') {
        threads.push(binding);
      }
    }
    return threads;
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const threadAdapter = new ThreadAdapter();
