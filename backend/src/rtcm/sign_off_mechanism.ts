/**
 * @file sign_off_mechanism.ts
 * @description RTCM 签署机制 - 正式的多方确认流程
 * 支持 Chair、Supervisor、User 三方签署
 */

import { SessionState, Issue, Verdict, FinalizeIssue } from './types';

// ============================================================================
// Types
// ============================================================================

export enum SignOffRole {
  CHAIR = 'chair',
  SUPERVISOR = 'supervisor',
  USER = 'user',
}

export interface SignOffRecord {
  role: SignOffRole;
  signedBy: string;
  signedAt: string;
  comment?: string;
  signature: string; // 签名哈希
}

export interface SignOffRequest {
  issueId: string;
  issueTitle: string;
  verdict: Verdict;
  requiredSigners: SignOffRole[];
  deadline?: string;
}

export interface SignOffResult {
  success: boolean;
  requiredSigners: SignOffRole[];
  completedSigners: SignOffRole[];
  pendingSigners: SignOffRole[];
  signOffRecords: SignOffRecord[];
  finalVerdict?: Verdict;
  error?: string;
}

// ============================================================================
// Sign-Off Mechanism
// ============================================================================

export class SignOffMechanism {
  private signOffRecords: Map<string, SignOffRecord[]> = new Map();

  /**
   * 发起签署请求
   */
  initiateSignOff(request: SignOffRequest): string {
    const key = `signoff-${request.issueId}-${Date.now()}`;
    const records: SignOffRecord[] = [];

    for (const role of request.requiredSigners) {
      records.push({
        role,
        signedBy: '',
        signedAt: '',
        signature: '',
      });
    }

    this.signOffRecords.set(key, records);
    return key;
  }

  /**
   * 执行签署
   */
  async sign(
    signOffKey: string,
    role: SignOffRole,
    signedBy: string,
    comment?: string
  ): Promise<boolean> {
    const records = this.signOffRecords.get(signOffKey);
    if (!records) {
      return false;
    }

    const record = records.find(r => r.role === role);
    if (!record) {
      return false;
    }

    // 生成签名（简化版：使用 role + signedBy + timestamp）
    const signature = this.generateSignature(role, signedBy);

    record.signedBy = signedBy;
    record.signedAt = new Date().toISOString();
    record.comment = comment;
    record.signature = signature;

    return true;
  }

  /**
   * 检查签署状态
   */
  checkSignOffStatus(signOffKey: string): SignOffResult {
    const records = this.signOffRecords.get(signOffKey);
    if (!records) {
      return {
        success: false,
        requiredSigners: [],
        completedSigners: [],
        pendingSigners: [],
        signOffRecords: [],
        error: 'Sign-off key not found',
      };
    }

    const completedSigners: SignOffRole[] = [];
    const pendingSigners: SignOffRole[] = [];

    for (const record of records) {
      if (record.signedBy) {
        completedSigners.push(record.role);
      } else {
        pendingSigners.push(record.role);
      }
    }

    return {
      success: pendingSigners.length === 0,
      requiredSigners: records.map(r => r.role),
      completedSigners,
      pendingSigners,
      signOffRecords: records,
    };
  }

  /**
   * 批量签署（适用于简单场景）
   */
  async batchSign(
    signOffKey: string,
    signerMap: Map<SignOffRole, string>
  ): Promise<boolean> {
    for (const [role, signedBy] of signerMap) {
      const success = await this.sign(signOffKey, role, signedBy);
      if (!success) {
        return false;
      }
    }
    return true;
  }

  /**
   * 生成签名哈希
   */
  private generateSignature(role: SignOffRole, signedBy: string): string {
    const timestamp = Date.now();
    const data = `${role}:${signedBy}:${timestamp}`;
    // 简化版签名：实际应该使用 crypto module
    let hash = 0;
    for (let i = 0; i < data.length; i++) {
      const char = data.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return `sig-${Math.abs(hash).toString(16)}-${timestamp.toString(16)}`;
  }

  /**
   * 为 Issue 生成签署请求
   */
  createSignOffRequest(issue: Issue, includeUser: boolean = true): SignOffRequest {
    const requiredSigners: SignOffRole[] = [SignOffRole.CHAIR, SignOffRole.SUPERVISOR];
    if (includeUser) {
      requiredSigners.push(SignOffRole.USER);
    }

    return {
      issueId: issue.issue_id,
      issueTitle: issue.issue_title,
      verdict: issue.verdict || 'evidence_insufficient',
      requiredSigners,
    };
  }

  /**
   * 执行完整的签署流程
   */
  async executeSignOffFlow(
    issue: Issue,
    chairSignature: string,
    supervisorSignature: string,
    userSignature?: string
  ): Promise<SignOffResult> {
    // 创建签署请求
    const request = this.createSignOffRequest(issue, !!userSignature);
    const key = this.initiateSignOff(request);

    // Chair 签署
    await this.sign(key, SignOffRole.CHAIR, chairSignature);

    // Supervisor 签署
    await this.sign(key, SignOffRole.SUPERVISOR, supervisorSignature);

    // User 签署（可选）
    if (userSignature) {
      await this.sign(key, SignOffRole.USER, userSignature);
    }

    // 返回最终状态
    return this.checkSignOffStatus(key);
  }

  /**
   * 验证签署是否有效
   */
  verifySignOff(signOffKey: string): boolean {
    const result = this.checkSignOffStatus(signOffKey);
    return result.success;
  }

  /**
   * 获取签署记录
   */
  getSignOffRecords(signOffKey: string): SignOffRecord[] {
    return this.signOffRecords.get(signOffKey) || [];
  }
}

// ============================================================================
// Session-Level Sign-Off
// ============================================================================

export interface SessionSignOff {
  sessionId: string;
  allIssuesSigned: boolean;
  issueSignOffs: Map<string, string>; // issueId -> signOffKey
  createdAt: string;
  expiresAt?: string;
}

export class SessionSignOffManager {
  private sessionSignOffs: Map<string, SessionSignOff> = new Map();
  private signOffMechanism: SignOffMechanism;

  constructor() {
    this.signOffMechanism = new SignOffMechanism();
  }

  /**
   * 为会话创建签署记录
   */
  createSessionSignOff(session: SessionState, issues: Issue[]): string {
    const key = `session-signoff-${session.session_id}`;
    const issueSignOffs = new Map<string, string>();

    for (const issue of issues) {
      if (issue.verdict) {
        const request = this.signOffMechanism.createSignOffRequest(issue, false);
        const signOffKey = this.signOffMechanism.initiateSignOff(request);
        issueSignOffs.set(issue.issue_id, signOffKey);
      }
    }

    const sessionSignOff: SessionSignOff = {
      sessionId: session.session_id,
      allIssuesSigned: false,
      issueSignOffs,
      createdAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(), // 7天后过期
    };

    this.sessionSignOffs.set(key, sessionSignOff);
    return key;
  }

  /**
   * 检查会话是否已完全签署
   */
  isSessionFullySigned(signOffKey: string): boolean {
    const sessionSignOff = this.sessionSignOffs.get(signOffKey);
    if (!sessionSignOff) return false;

    for (const [, key] of sessionSignOff.issueSignOffs) {
      if (!this.signOffMechanism.verifySignOff(key)) {
        return false;
      }
    }

    sessionSignOff.allIssuesSigned = true;
    return true;
  }

  /**
   * 获取会话签署状态摘要
   */
  getSessionSignOffSummary(signOffKey: string): {
    totalIssues: number;
    signedIssues: number;
    pendingIssues: string[];
  } {
    const sessionSignOff = this.sessionSignOffs.get(signOffKey);
    if (!sessionSignOff) {
      return { totalIssues: 0, signedIssues: 0, pendingIssues: [] };
    }

    let signedIssues = 0;
    const pendingIssues: string[] = [];

    for (const [issueId, key] of sessionSignOff.issueSignOffs) {
      if (this.signOffMechanism.verifySignOff(key)) {
        signedIssues++;
      } else {
        pendingIssues.push(issueId);
      }
    }

    return {
      totalIssues: sessionSignOff.issueSignOffs.size,
      signedIssues,
      pendingIssues,
    };
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const signOffMechanism = new SignOffMechanism();
export const sessionSignOffManager = new SessionSignOffManager();