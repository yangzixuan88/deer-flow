/**
 * @file rtcm_main_agent_handoff.ts
 * @description RTCM 主智能体会话内接管机制 - Delta 生产验证态核心
 * 主智能体识别触发并调用 rtcm_entry_adapter，RTCM 接管后续推进
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import * as crypto from 'crypto';
import { SessionMode } from './rtcm_thread_adapter';
import { threadAdapter } from './rtcm_thread_adapter';
import { userInterventionClassifier, UserInterventionType } from './rtcm_user_intervention';
import { followUpManager } from './rtcm_follow_up';
import { mainSessionCardGenerator } from './rtcm_display_mode';

// ============================================================================
// Types
// ============================================================================

export enum MainChatMode {
  NORMAL = 'normal',
  RTCM = 'rtcm',
  SUSPENDED = 'suspended',
}

export interface ActiveRTCMSession {
  sessionId: string;
  threadId: string;
  mode: MainChatMode;
  activeRtcmSessionId: string;
  activeRtcmThreadId: string;
  triggeredBy: 'explicit_rtcm_start' | 'rtcm_suggested_and_user_accepted' | 'user_request';
  startedAt: string;
  lastActivityAt: string;
}

export interface HandoffRequest {
  trigger: 'explicit_rtcm_start' | 'rtcm_suggested_and_user_accepted' | 'user_request';
  projectId: string;
  projectName: string;
  userMessage?: string;
}

// ============================================================================
// Main Agent Handoff Manager
// ============================================================================

export class MainAgentHandoffManager {
  private handoffDir: string;
  private activeSession: ActiveRTCMSession | null = null;

  // Feature Flags
  private static readonly FEATURE_FLAGS = {
    RTCM_ENABLED: process.env.RTCM_ENABLED !== 'false',
    RTCM_SUGGEST_ONLY: process.env.RTCM_SUGGEST_ONLY === 'true',
    RTCM_THREAD_MODE: process.env.RTCM_THREAD_MODE !== 'false',
    RTCM_FOLLOW_UP_ENABLED: process.env.RTCM_FOLLOW_UP_ENABLED !== 'false',
    RTCM_MAIN_CHAT_HANDOFF: process.env.RTCM_MAIN_CHAT_HANDOFF === 'true',
  };

  // Session TTL: active session expires after this many milliseconds (default 8 hours)
  private static readonly SESSION_TTL_MS = Number(process.env.RTCM_SESSION_TTL_HOURS || '8') * 60 * 60 * 1000;

  constructor() {
    this.handoffDir = runtimePath('rtcm', 'handoff');
    this.ensureDir(this.handoffDir);
    // Restore active session from disk on startup (enables intercept path after restart)
    this.loadPreviousSession();
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  // ===========================================================================
  // Feature Flags
  // ===========================================================================

  isFeatureEnabled(flag: keyof typeof MainAgentHandoffManager.FEATURE_FLAGS): boolean {
    return MainAgentHandoffManager.FEATURE_FLAGS[flag];
  }

  getAllFeatureFlags(): typeof MainAgentHandoffManager.FEATURE_FLAGS {
    return { ...MainAgentHandoffManager.FEATURE_FLAGS };
  }

  // ===========================================================================
  // Session Expiry Helper
  // ===========================================================================

  /**
   * Check if a session has expired based on lastActivityAt and TTL.
   */
  private isSessionExpired(session: ActiveRTCMSession): boolean {
    if (!session.lastActivityAt) return true;
    const lastActivity = new Date(session.lastActivityAt).getTime();
    const now = Date.now();
    return (now - lastActivity) > MainAgentHandoffManager.SESSION_TTL_MS;
  }

  // ===========================================================================
  // Session Activation
  // ===========================================================================

  /**
   * 激活 RTCM 会话
   */
  activateRTCM(request: HandoffRequest): {
    success: boolean;
    sessionId?: string;
    threadId?: string;
    mainSessionCard?: object;
    error?: string;
  } {
    if (!MainAgentHandoffManager.FEATURE_FLAGS.RTCM_ENABLED) {
      return { success: false, error: 'RTCM is disabled' };
    }

    const sessionId = `rtcm-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;

    // 创建线程
    const threadBinding = threadAdapter.createThread(
      request.projectId,
      request.projectName
    );

    // 创建主会话卡片
    const launchCard = mainSessionCardGenerator.generateLaunchCard({
      threadId: threadBinding.threadId,
      projectName: request.projectName,
      issueTitle: request.userMessage || '新议题',
    });

    // 设置活跃 RTCM 会话
    this.activeSession = {
      sessionId,
      threadId: threadBinding.threadId,
      mode: MainChatMode.RTCM,
      activeRtcmSessionId: sessionId,
      activeRtcmThreadId: threadBinding.threadId,
      triggeredBy: request.trigger,
      startedAt: new Date().toISOString(),
      lastActivityAt: new Date().toISOString(),
    };

    this.saveActiveSession();

    return {
      success: true,
      sessionId,
      threadId: threadBinding.threadId,
      mainSessionCard: launchCard,
    };
  }

  /**
   * 检查是否有活跃 RTCM 会话（带 TTL 校验）
   */
  hasActiveRTCMSession(): boolean {
    if (this.activeSession === null || this.activeSession.mode !== MainChatMode.RTCM) {
      return false;
    }
    // TTL check: reject expired sessions
    if (this.isSessionExpired(this.activeSession)) {
      // Clear expired session instead of leaving it dangling
      this.activeSession = null;
      this.deleteActiveSession();
      return false;
    }
    return true;
  }

  /**
   * 获取当前活跃 RTCM 会话
   */
  getActiveSession(): ActiveRTCMSession | null {
    return this.activeSession;
  }

  /**
   * 检查消息是否应该被 RTCM 优先拦截
   */
  shouldInterceptForRTCM(userMessage: string): boolean {
    if (!this.hasActiveRTCMSession()) {
      return false;
    }

    // 检查消息是否是对 RTCM 的直接干预
    const interventionType = userInterventionClassifier.classify(userMessage).type;
    return interventionType !== null;
  }

  /**
   * 处理被拦截的消息
   */
  handleInterceptedMessage(userMessage: string): {
    isIntervention: boolean;
    interventionType?: UserInterventionType;
    sessionId?: string;
    threadId?: string;
  } {
    if (!this.activeSession) {
      return { isIntervention: false };
    }

    const classification = userInterventionClassifier.classify(userMessage);

    return {
      isIntervention: true,
      interventionType: classification.type,
      sessionId: this.activeSession.activeRtcmSessionId,
      threadId: this.activeSession.activeRtcmThreadId,
    };
  }

  // ===========================================================================
  // Session Deactivation
  // ===========================================================================

  /**
   * 完成项目后退出 RTCM
   */
  exitRTCM(sessionId: string, reason: 'completed' | 'user_exit' | 'suspended'): void {
    if (this.activeSession && this.activeSession.sessionId === sessionId) {
      this.activeSession.mode = MainChatMode.SUSPENDED;
      this.activeSession.lastActivityAt = new Date().toISOString();
      this.saveActiveSession();
    }
  }

  /**
   * 暂停项目后退出到普通模式
   */
  exitToNormalMode(sessionId: string): void {
    if (this.activeSession && this.activeSession.sessionId === sessionId) {
      this.activeSession.mode = MainChatMode.NORMAL;
      this.activeSession.lastActivityAt = new Date().toISOString();
      this.saveActiveSession();
    }
  }

  /**
   * 用户强制退出
   */
  forceExit(sessionId: string): void {
    if (this.activeSession && this.activeSession.sessionId === sessionId) {
      this.activeSession = null;
      this.deleteActiveSession();
    }
  }

  // ===========================================================================
  // Session Resume
  // ===========================================================================

  /**
   * 恢复 RTCM 会话（CONTINUE / REOPEN / FOLLOW_UP）
   */
  resumeRTCMSession(params: {
    sessionId: string;
    mode: 'continue' | 'reopen' | 'follow_up';
    userMessage?: string;
  }): {
    success: boolean;
    sessionId?: string;
    threadId?: string;
    error?: string;
  } {
    // 查找对应的 thread
    const binding = threadAdapter.findThreadBySession(params.sessionId);
    if (!binding) {
      return { success: false, error: 'Session not found' };
    }

    // 更新 active session
    this.activeSession = {
      sessionId: params.sessionId,
      threadId: binding.threadId,
      mode: MainChatMode.RTCM,
      activeRtcmSessionId: params.sessionId,
      activeRtcmThreadId: binding.threadId,
      triggeredBy: 'user_request',
      startedAt: this.activeSession?.startedAt || new Date().toISOString(),
      lastActivityAt: new Date().toISOString(),
    };

    // 如果是 FOLLOW_UP，处理创建新 issue
    if (params.mode === 'follow_up' && params.userMessage) {
      const followUpType = followUpManager.determineFollowUpType(params.userMessage);
      // 这里会创建 follow_up issue
      // 详细逻辑在 rtcm_follow_up.ts
    }

    this.saveActiveSession();

    return {
      success: true,
      sessionId: params.sessionId,
      threadId: binding.threadId,
    };
  }

  // ===========================================================================
  // Main Chat Trigger Detection
  // ===========================================================================

  /**
   * 检测用户消息是否应该触发 RTCM
   */
  detectRTCMTrigger(userMessage: string): {
    shouldTrigger: boolean;
    triggerType: 'explicit_rtcm_start' | 'rtcm_suggested_and_user_accepted' | null;
    confidence: number;
  } {
    const lower = userMessage.toLowerCase();

    // 显式启动关键词
    const explicitKeywords = [
      '开会', '启动rtc', 'rtcm', '圆桌会议', '讨论一下',
      '开个会', '启动会议', '开始讨论',
    ];

    const explicitMatch = explicitKeywords.some(kw => lower.includes(kw));
    if (explicitMatch) {
      return {
        shouldTrigger: true,
        triggerType: 'explicit_rtcm_start',
        confidence: 0.9,
      };
    }

    // 建议启动关键词
    const suggestKeywords = [
      '建议', '可以开个会', '要不要讨论', '建议开会',
    ];

    const suggestMatch = suggestKeywords.some(kw => lower.includes(kw));
    if (suggestMatch) {
      return {
        shouldTrigger: true,
        triggerType: 'rtcm_suggested_and_user_accepted',
        confidence: 0.6,
      };
    }

    return {
      shouldTrigger: false,
      triggerType: null,
      confidence: 0,
    };
  }

  // ===========================================================================
  // Persistence
  // ===========================================================================

  private saveActiveSession(): void {
    if (!this.activeSession) return;

    const filePath = path.join(this.handoffDir, 'active_session.json');
    fs.writeFileSync(filePath, JSON.stringify(this.activeSession, null, 2), 'utf-8');
  }

  private deleteActiveSession(): void {
    const filePath = path.join(this.handoffDir, 'active_session.json');
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
    }
  }

  /**
   * 加载之前保存的 active session
   */
  loadPreviousSession(): void {
    const filePath = path.join(this.handoffDir, 'active_session.json');
    if (fs.existsSync(filePath)) {
      try {
        const session = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        // Reject expired sessions during restore to prevent stale intercept
        if (session && this.isSessionExpired(session)) {
          this.activeSession = null;
          this.deleteActiveSession();
          return;
        }
        this.activeSession = session;
      } catch {
        this.activeSession = null;
      }
    }
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const mainAgentHandoff = new MainAgentHandoffManager();
