/**
 * @file runtime_state.ts
 * @description U2: RTCM Runtime State Initializer
 * 初始化和管理会话状态
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import {
  SessionState,
  SessionStatus,
  ChairSummary,
  SupervisorCheck,
  FIXED_SPEAKING_ORDER,
} from './types';

const RTCM_RUNTIME_DIR = runtimePath('rtcm', 'runtime');

export interface RuntimeStateSnapshot {
  session: SessionState;
  currentIssueId: string | null;
  currentStage: string;
  roundNumber: number;
}

export class RuntimeStateManager {
  private session: SessionState | null = null;
  private runtimeDir: string;

  constructor(runtimeDir: string = RTCM_RUNTIME_DIR) {
    this.runtimeDir = runtimeDir;
    this.ensureRuntimeDir();
  }

  /**
   * 确保运行时目录存在
   */
  private ensureRuntimeDir(): void {
    if (!fs.existsSync(this.runtimeDir)) {
      fs.mkdirSync(this.runtimeDir, { recursive: true });
      console.log(`[RuntimeState] 创建运行时目录: ${this.runtimeDir}`);
    }
  }

  /**
   * 创建新会话
   */
  public async createSession(
    projectId: string,
    projectName: string,
    userGoal: string,
    createdBy: string = 'system'
  ): Promise<SessionState> {
    console.log('[RuntimeState] 创建新会话...');

    const sessionId = `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const now = new Date().toISOString();

    // 获取8个成员（不含chair和supervisor）
    const memberIds = FIXED_SPEAKING_ORDER.filter(
      (id) => id !== 'rtcm-chair-agent' && id !== 'rtcm-supervisor-agent'
    );

    this.session = {
      session_id: sessionId,
      project_id: projectId,
      project_name: projectName,
      mode: 'rtcm_v2',
      status: 'init',
      current_issue_id: null,
      current_stage: 'issue_definition',
      current_round: 0,
      active_members: [...memberIds, 'rtcm-chair-agent', 'rtcm-supervisor-agent'],
      lease_state: {
        granted: false,
        granted_by: null,
        granted_at: null,
      },
      latest_chair_summary: null,
      latest_supervisor_check: null,
      user_presence_status: 'present',
      pending_user_acceptance: false,
      reopen_flag: false,
      created_at: now,
      updated_at: now,
    };

    await this.saveSessionState();

    console.log(`[RuntimeState] 会话创建成功: ${sessionId}`);
    return this.session;
  }

  /**
   * 获取当前会话
   */
  public getSession(): SessionState | null {
    return this.session;
  }

  /**
   * 从磁盘加载会话
   */
  public async loadSession(sessionId: string): Promise<SessionState | null> {
    const filePath = path.join(this.runtimeDir, `${sessionId}.json`);

    if (!fs.existsSync(filePath)) {
      console.warn(`[RuntimeState] 会话文件不存在: ${filePath}`);
      return null;
    }

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      this.session = JSON.parse(content);
      console.log(`[RuntimeState] 会话加载成功: ${sessionId}`);
      return this.session;
    } catch (error) {
      console.error(`[RuntimeState] 加载会话失败:`, error);
      return null;
    }
  }

  /**
   * 保存会话状态到磁盘
   */
  public async saveSessionState(): Promise<void> {
    if (!this.session) {
      console.warn('[RuntimeState] 没有活动的会话');
      return;
    }

    this.session.updated_at = new Date().toISOString();
    const filePath = path.join(this.runtimeDir, `${this.session.session_id}.json`);

    try {
      fs.writeFileSync(filePath, JSON.stringify(this.session, null, 2), 'utf-8');
    } catch (error) {
      console.error(`[RuntimeState] 保存会话失败:`, error);
    }
  }

  /**
   * 更新会话状态
   */
  public async updateStatus(status: SessionStatus): Promise<void> {
    if (!this.session) {
      throw new Error('[RuntimeState] 没有活动的会话');
    }

    this.session.status = status;
    await this.saveSessionState();
    console.log(`[RuntimeState] 会话状态更新: ${status}`);
  }

  /**
   * 更新当前议题
   */
  public async updateCurrentIssue(issueId: string | null): Promise<void> {
    if (!this.session) {
      throw new Error('[RuntimeState] 没有活动的会话');
    }

    this.session.current_issue_id = issueId;
    await this.saveSessionState();
  }

  /**
   * 更新当前阶段
   */
  public async updateCurrentStage(stage: string): Promise<void> {
    if (!this.session) {
      throw new Error('[RuntimeState] 没有活动的会话');
    }

    this.session.current_stage = stage;
    await this.saveSessionState();
  }

  /**
   * 进入下一轮
   */
  public async advanceRound(): Promise<number> {
    if (!this.session) {
      throw new Error('[RuntimeState] 没有活动的会话');
    }

    this.session.current_round++;
    await this.saveSessionState();
    console.log(`[RuntimeState] 进入第 ${this.session.current_round} 轮`);
    return this.session.current_round;
  }

  /**
   * 更新主持官摘要
   */
  public async updateChairSummary(summary: ChairSummary): Promise<void> {
    if (!this.session) {
      throw new Error('[RuntimeState] 没有活动的会话');
    }

    this.session.latest_chair_summary = summary;
    await this.saveSessionState();
  }

  /**
   * 更新监督官检查结果
   */
  public async updateSupervisorCheck(check: SupervisorCheck): Promise<void> {
    if (!this.session) {
      throw new Error('[RuntimeState] 没有活动的会话');
    }

    this.session.latest_supervisor_check = check;
    await this.saveSessionState();
  }

  /**
   * 授予执行租约
   */
  public async grantLease(grantedBy: string): Promise<void> {
    if (!this.session) {
      throw new Error('[RuntimeState] 没有活动的会话');
    }

    this.session.lease_state = {
      granted: true,
      granted_by: grantedBy,
      granted_at: new Date().toISOString(),
    };
    await this.saveSessionState();
    console.log(`[RuntimeState] 执行租约已授予: ${grantedBy}`);
  }

  /**
   * 撤销执行租约
   */
  public async revokeLease(): Promise<void> {
    if (!this.session) {
      throw new Error('[RuntimeState] 没有活动的会话');
    }

    this.session.lease_state = {
      granted: false,
      granted_by: null,
      granted_at: null,
    };
    await this.saveSessionState();
    console.log('[RuntimeState] 执行租约已撤销');
  }

  /**
   * 检查租约是否有效
   */
  public isLeaseValid(): boolean {
    if (!this.session) return false;
    return this.session.lease_state.granted;
  }

  /**
   * 设置用户干预标记
   */
  public async setReopenFlag(flag: boolean): Promise<void> {
    if (!this.session) {
      throw new Error('[RuntimeState] 没有活动的会话');
    }

    this.session.reopen_flag = flag;
    await this.saveSessionState();
  }

  /**
   * 设置用户存在状态
   */
  public async setUserPresence(present: boolean): Promise<void> {
    if (!this.session) {
      throw new Error('[RuntimeState] 没有活动的会话');
    }

    this.session.user_presence_status = present ? 'present' : 'absent';
    await this.saveSessionState();
  }

  /**
   * 获取运行时状态快照
   */
  public getSnapshot(): RuntimeStateSnapshot | null {
    if (!this.session) return null;

    return {
      session: this.session,
      currentIssueId: this.session.current_issue_id,
      currentStage: this.session.current_stage,
      roundNumber: this.session.current_round,
    };
  }

  /**
   * 列出所有运行时会话
   */
  public listSessions(): string[] {
    if (!fs.existsSync(this.runtimeDir)) {
      return [];
    }

    return fs.readdirSync(this.runtimeDir)
      .filter((f) => f.endsWith('.json'))
      .map((f) => f.replace('.json', ''));
  }
}

// 单例导出
export const runtimeStateManager = new RuntimeStateManager();
