/**
 * @file rtcm_entry_adapter.ts
 * @description RTCM 入口适配器 - 主系统模式切换的安全接入层
 */

import { SessionState, Issue, Hypothesis } from './types';
import { runtimeState } from './runtime_state';
import { roundOrchestrator } from './round_orchestrator';

// ============================================================================
// Feature Flags
// ============================================================================

export const RTCM_FLAGS = {
  RTCM_ENABLED: process.env.RTCM_ENABLED !== 'false', // 默认开启
  RTCM_SUGGEST_ONLY: process.env.RTCM_SUGGEST_ONLY === 'true', // 建议模式，不阻塞主流程
  RTCM_AUTO_REOPEN: process.env.RTCM_AUTO_REOPEN !== 'false', // 自动重新打开
  RTCM_CONFLICT_DETECTION: process.env.RTCM_CONFLICT_DETECTION !== 'false', // 证据冲突检测
} as const;

// ============================================================================
// Types
// ============================================================================

export enum RTCMSessionMode {
  NEW = 'new', // 新会议
  CONTINUE = 'continue', // 续会
  REOPEN = 'reopen', // 基于旧会话重开
}

export interface RTCMSessionHandle {
  sessionId: string;
  mode: RTCMSessionMode;
  projectId: string;
  createdAt: string;
  canResume: boolean;
  parentSessionId?: string;
}

export interface EntryRequest {
  projectId: string;
  projectName: string;
  trigger: 'user_action' | 'scheduled' | 'conflict_detected' | 'manual';
  parentSessionId?: string;
  existingState?: SessionState;
}

export interface EntryResponse {
  handle: RTCMSessionHandle;
  flagStatus: {
    enabled: boolean;
    suggestOnly: boolean;
  };
  error?: string;
}

// ============================================================================
// RTCM Entry Adapter
// ============================================================================

export class RTCMEntryAdapter {
  /**
   * 创建新会话
   */
  async createSession(req: EntryRequest): Promise<EntryResponse> {
    if (!RTCM_FLAGS.RTCM_ENABLED) {
      return {
        handle: {
          sessionId: 'rtcm-disabled',
          mode: RTCMSessionMode.NEW,
          projectId: req.projectId,
          createdAt: new Date().toISOString(),
          canResume: false,
        },
        flagStatus: {
          enabled: false,
          suggestOnly: RTCM_FLAGS.RTCM_SUGGEST_ONLY,
        },
        error: 'RTCM is disabled via RTCM_ENABLED=false',
      };
    }

    const sessionId = `rtcm-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    const handle: RTCMSessionHandle = {
      sessionId,
      mode: RTCMSessionMode.NEW,
      projectId: req.projectId,
      createdAt: new Date().toISOString(),
      canResume: true,
    };

    // 初始化运行时状态
    runtimeState.createSession({
      session_id: sessionId,
      project_id: req.projectId,
      project_name: req.projectName,
      mode: 'rtcm',
      status: 'init',
      current_issue_id: null,
      current_stage: 'init',
      current_round: 0,
      active_members: [],
      lease_state: { granted: false, granted_by: null, granted_at: null },
      latest_chair_summary: null,
      latest_supervisor_check: null,
      user_presence_status: 'present',
      pending_user_acceptance: false,
      reopen_flag: false,
      created_at: handle.createdAt,
      updated_at: handle.createdAt,
    });

    return {
      handle,
      flagStatus: {
        enabled: true,
        suggestOnly: RTCM_FLAGS.RTCM_SUGGEST_ONLY,
      },
    };
  }

  /**
   * 续会 - 恢复已存在的会话
   */
  async resumeSession(sessionId: string, round?: number): Promise<EntryResponse> {
    if (!RTCM_FLAGS.RTCM_ENABLED) {
      return {
        handle: {
          sessionId: 'rtcm-disabled',
          mode: RTCMSessionMode.CONTINUE,
          projectId: '',
          createdAt: new Date().toISOString(),
          canResume: false,
        },
        flagStatus: {
          enabled: false,
          suggestOnly: RTCM_FLAGS.RTCM_SUGGEST_ONLY,
        },
        error: 'RTCM is disabled',
      };
    }

    const state = runtimeState.getSession();
    if (!state || state.session_id !== sessionId) {
      return {
        handle: {
          sessionId: 'rtcm-not-found',
          mode: RTCMSessionMode.CONTINUE,
          projectId: '',
          createdAt: new Date().toISOString(),
          canResume: false,
        },
        flagStatus: {
          enabled: true,
          suggestOnly: RTCM_FLAGS.RTCM_SUGGEST_ONLY,
        },
        error: `Session ${sessionId} not found`,
      };
    }

    return {
      handle: {
        sessionId: state.session_id,
        mode: RTCMSessionMode.CONTINUE,
        projectId: state.project_id,
        createdAt: state.created_at,
        canResume: true,
      },
      flagStatus: {
        enabled: true,
        suggestOnly: RTCM_FLAGS.RTCM_SUGGEST_ONLY,
      },
    };
  }

  /**
   * 基于旧会话重新打开
   */
  async reopenFromSession(parentSessionId: string, reason: string): Promise<EntryResponse> {
    if (!RTCM_FLAGS.RTCM_ENABLED || !RTCM_FLAGS.RTCM_AUTO_REOPEN) {
      return {
        handle: {
          sessionId: 'rtcm-reopen-blocked',
          mode: RTCMSessionMode.REOPEN,
          projectId: '',
          createdAt: new Date().toISOString(),
          canResume: false,
          parentSessionId,
        },
        flagStatus: {
          enabled: RTCM_FLAGS.RTCM_ENABLED,
          suggestOnly: RTCM_FLAGS.RTCM_SUGGEST_ONLY,
        },
        error: 'Reopen is blocked (disabled or auto_reopen=false)',
      };
    }

    // 获取父会话状态
    const parentState = runtimeState.getSession();
    if (!parentState || parentState.session_id !== parentSessionId) {
      return {
        handle: {
          sessionId: 'rtcm-parent-not-found',
          mode: RTCMSessionMode.REOPEN,
          projectId: '',
          createdAt: new Date().toISOString(),
          canResume: false,
          parentSessionId,
        },
        flagStatus: {
          enabled: true,
          suggestOnly: RTCM_FLAGS.RTCM_SUGGEST_ONLY,
        },
        error: `Parent session ${parentSessionId} not found`,
      };
    }

    const sessionId = `rtcm-reopen-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const now = new Date().toISOString();

    // 创建新会话，继承父会话的项目信息
    runtimeState.createSession({
      ...parentState,
      session_id: sessionId,
      status: 'reopen',
      current_round: 0,
      reopen_flag: true,
      created_at: now,
      updated_at: now,
    });

    return {
      handle: {
        sessionId,
        mode: RTCMSessionMode.REOPEN,
        projectId: parentState.project_id,
        createdAt: now,
        canResume: true,
        parentSessionId,
      },
      flagStatus: {
        enabled: true,
        suggestOnly: RTCM_FLAGS.RTCM_SUGGEST_ONLY,
      },
    };
  }

  /**
   * 判断入口类型并路由
   */
  async routeEntry(req: EntryRequest): Promise<EntryResponse> {
    // 有父会话ID -> 重开
    if (req.parentSessionId) {
      return this.reopenFromSession(req.parentSessionId, 'user_requested');
    }

    // 有现存状态且状态不是 archived -> 续会
    if (req.existingState && req.existingState.status !== 'archived') {
      return this.resumeSession(req.existingState.session_id);
    }

    // 默认 -> 新建
    return this.createSession(req);
  }

  /**
   * 获取当前标志状态
   */
  getFlagStatus(): typeof RTCM_FLAGS {
    return { ...RTCM_FLAGS };
  }

  /**
   * 动态更新标志（运行时调整）
   */
  updateFlags(flags: Partial<typeof RTCM_FLAGS>): void {
    Object.assign(RTCM_FLAGS, flags);
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const rtcmEntryAdapter = new RTCMEntryAdapter();