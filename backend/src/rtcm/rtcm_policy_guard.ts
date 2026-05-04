/**
 * @file rtcm_policy_guard.ts
 * @description RTCM 协议与权限硬化 - Gamma 可运营态核心
 * 确保 lease 边界、sign-off 边界、execution scope、用户主权
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';
import * as crypto from 'crypto';

// ============================================================================
// Types
// ============================================================================

// 高风险动作定义
export enum HighRiskAction {
  FILE_OVERWRITE = 'file_overwrite',
  FILE_DELETE = 'file_delete',
  INSTALL_DEPENDENCY = 'install_dependency',
  MODIFY_MAIN_ENTRY = 'modify_main_entry',
  BATCH_SCRIPT_OVERWRITE = 'batch_script_overwrite',
  EXTERNAL_PUSH_SENSITIVE = 'external_push_sensitive',
  SYSTEM_CONFIG_OVERWRITE = 'system_config_overwrite',
  RTCM_PROTOCOL_MODIFY = 'rtcm_protocol_modify',
}

// 执行范围校验
export interface ExecutionScope {
  actionId: string;
  action: string;
  initiatedBy: string; // 谁发起
  targetScope: string; // 影响的范围
  requiresLease: boolean;
  requiresSignOff: boolean;
  isHighRisk: boolean;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
}

// Lease 状态
export interface LeaseState {
  granted: boolean;
  grantedBy: string | null;
  grantedAt: string | null;
  expiresAt: string | null;
  scope: string | null;
}

// Sign-off 状态
export interface SignOffStatus {
  issueId: string;
  chairSigned: boolean;
  supervisorSigned: boolean;
  userSigned: boolean;
  allSigned: boolean;
}

// Policy Violation
export interface PolicyViolation {
  violationId: string;
  sessionId: string;
  timestamp: string;
  attemptedAction: string;
  violatedRule: string;
  severity: 'warning' | 'error' | 'critical';
  blocked: boolean;
  initiator: string;
  details: string;
}

// User Sovereignty Actions (必须明确需要用户许可)
export const USER_SOVEREIGN_ACTIONS = [
  HighRiskAction.SYSTEM_CONFIG_OVERWRITE,
  HighRiskAction.RTCM_PROTOCOL_MODIFY,
  HighRiskAction.INSTALL_DEPENDENCY,
  HighRiskAction.FILE_DELETE,
];

// ============================================================================
// Policy Guard
// ============================================================================

export class PolicyGuard {
  private policyDir: string;
  private violations: PolicyViolation[] = [];

  constructor() {
    this.policyDir = runtimePath('rtcm', 'policy');
    this.ensureDir(this.policyDir);
    this.ensureDir(path.join(this.policyDir, 'violations'));
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  // ===========================================================================
  // Lease Boundary Enforcement
  // ===========================================================================

  /**
   * 检查执行请求是否有有效 lease
   */
  checkLease(
    sessionId: string,
    action: string,
    initiator: string,
    scope: string
  ): { allowed: boolean; reason?: string; violationId?: string } {
    const leaseFile = path.join(this.policyDir, `${sessionId}_lease.json`);
    let lease: LeaseState | null = null;

    if (fs.existsSync(leaseFile)) {
      lease = JSON.parse(fs.readFileSync(leaseFile, 'utf-8'));
    }

    // 没有 lease 的敏感动作必须被阻断
    if (!lease || !lease.granted) {
      const isHighRisk = this.isHighRiskAction(action);
      if (isHighRisk) {
        const violation = this.logViolation({
          sessionId,
          attemptedAction: action,
          violatedRule: 'No valid lease for high-risk action',
          severity: 'error',
          blocked: true,
          initiator,
          details: `Action '${action}' requires lease but none found`,
        });
        return { allowed: false, reason: 'No lease', violationId: violation.violationId };
      }
    }

    // 检查 lease 是否过期
    if (lease && lease.expiresAt) {
      if (new Date(lease.expiresAt) < new Date()) {
        const violation = this.logViolation({
          sessionId,
          attemptedAction: action,
          violatedRule: 'Lease expired',
          severity: 'error',
          blocked: true,
          initiator,
          details: `Lease expired at ${lease.expiresAt}`,
        });
        return { allowed: false, reason: 'Lease expired', violationId: violation.violationId };
      }
    }

    // 检查 lease scope
    if (lease && lease.scope && lease.scope !== scope && lease.scope !== '*') {
      const violation = this.logViolation({
        sessionId,
        attemptedAction: action,
        violatedRule: 'Lease scope mismatch',
        severity: 'warning',
        blocked: false,
        initiator,
        details: `Action scope '${scope}' not in lease scope '${lease.scope}'`,
      });
      return { allowed: true, reason: 'Scope mismatch - proceed with caution' };
    }

    return { allowed: true };
  }

  /**
   * 授权 lease
   */
  grantLease(
    sessionId: string,
    grantedBy: string,
    scope: string,
    durationMs: number = 3600000
  ): LeaseState {
    const lease: LeaseState = {
      granted: true,
      grantedBy,
      grantedAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + durationMs).toISOString(),
      scope,
    };

    const leaseFile = path.join(this.policyDir, `${sessionId}_lease.json`);
    fs.writeFileSync(leaseFile, JSON.stringify(lease, null, 2), 'utf-8');

    return lease;
  }

  /**
   * 撤销 lease
   */
  revokeLease(sessionId: string): void {
    const leaseFile = path.join(this.policyDir, `${sessionId}_lease.json`);
    if (fs.existsSync(leaseFile)) {
      fs.unlinkSync(leaseFile);
    }
  }

  // ===========================================================================
  // High Risk Action Detection
  // ===========================================================================

  private highRiskPatterns: RegExp[] = [
    /overwrite/i,
    /delete/i,
    /install/i,
    /rm\s/i,
    /chmod/i,
    /sudo/i,
    /exec.*rm/i,
  ];

  isHighRiskAction(action: string): boolean {
    for (const pattern of this.highRiskPatterns) {
      if (pattern.test(action)) return true;
    }
    return Object.values(HighRiskAction).some(hra => action.includes(hra));
  }

  // ===========================================================================
  // Sign-Off Boundary Enforcement
  // ===========================================================================

  /**
   * 检查高风险动作是否有足够 sign-off
   */
  checkSignOff(
    issueId: string,
    action: string,
    initiator: string
  ): { allowed: boolean; reason?: string; violationId?: string } {
    const isHighRisk = this.isHighRiskAction(action);

    // 高风险动作必须有 sign-off
    if (isHighRisk) {
      const signOffFile = path.join(this.policyDir, `${issueId}_signoff.json`);
      if (!fs.existsSync(signOffFile)) {
        const violation = this.logViolation({
          sessionId: 'unknown',
          attemptedAction: action,
          violatedRule: 'High-risk action requires sign-off',
          severity: 'critical',
          blocked: true,
          initiator,
          details: `Issue '${issueId}' has no sign-off record`,
        });
        return { allowed: false, reason: 'No sign-off', violationId: violation.violationId };
      }

      const signOff = JSON.parse(fs.readFileSync(signOffFile, 'utf-8')) as SignOffStatus;
      if (!signOff.allSigned) {
        const missing = [];
        if (!signOff.chairSigned) missing.push('chair');
        if (!signOff.supervisorSigned) missing.push('supervisor');
        if (!signOff.userSigned) missing.push('user');

        const violation = this.logViolation({
          sessionId: 'unknown',
          attemptedAction: action,
          violatedRule: 'Sign-off incomplete',
          severity: 'error',
          blocked: true,
          initiator,
          details: `Missing sign-offs: ${missing.join(', ')}`,
        });
        return { allowed: false, reason: `Missing sign-offs: ${missing.join(', ')}`, violationId: violation.violationId };
      }
    }

    return { allowed: true };
  }

  /**
   * 写入 sign-off 记录
   */
  writeSignOff(issueId: string, signOff: SignOffStatus): void {
    const signOffFile = path.join(this.policyDir, `${issueId}_signoff.json`);
    fs.writeFileSync(signOffFile, JSON.stringify(signOff, null, 2), 'utf-8');
  }

  // ===========================================================================
  // User Sovereignty Protection
  // ===========================================================================

  /**
   * 检查是否需要用户明确许可
   */
  requiresUserConsent(action: string): boolean {
    return USER_SOVEREIGN_ACTIONS.some(sovereignAction => action.includes(sovereignAction));
  }

  /**
   * 检查用户是否已拒绝
   * 用户拒绝后系统不能绕过继续执行
   */
  checkUserRejection(sessionId: string): { rejected: boolean; reason?: string } {
    const rejectionFile = path.join(this.policyDir, `${sessionId}_rejection.json`);

    if (fs.existsSync(rejectionFile)) {
      const rejection = JSON.parse(fs.readFileSync(rejectionFile, 'utf-8'));
      return { rejected: true, reason: rejection.reason };
    }

    return { rejected: false };
  }

  /**
   * 记录用户拒绝
   */
  recordUserRejection(sessionId: string, reason: string): void {
    const rejectionFile = path.join(this.policyDir, `${sessionId}_rejection.json`);
    fs.writeFileSync(rejectionFile, JSON.stringify({
      sessionId,
      reason,
      rejectedAt: new Date().toISOString(),
    }, null, 2), 'utf-8');
  }

  /**
   * 清除用户拒绝（用于续会场景）
   */
  clearUserRejection(sessionId: string): void {
    const rejectionFile = path.join(this.policyDir, `${sessionId}_rejection.json`);
    if (fs.existsSync(rejectionFile)) {
      fs.unlinkSync(rejectionFile);
    }
  }

  // ===========================================================================
  // Execution Scope Validation
  // ===========================================================================

  /**
   * 验证执行范围
   */
  validateExecutionScope(scope: ExecutionScope): {
    valid: boolean;
    warnings: string[];
    blocked: boolean;
  } {
    const warnings: string[] = [];
    let blocked = false;

    // 高风险动作需要额外验证
    if (scope.isHighRisk) {
      if (!scope.requiresLease) {
        warnings.push('High-risk action should require lease');
      }
      if (!scope.requiresSignOff) {
        warnings.push('High-risk action should require sign-off');
      }
      if (scope.riskLevel === 'critical') {
        blocked = true;
        warnings.push('Critical risk action blocked until reviewed');
      }
    }

    return { valid: !blocked, warnings, blocked };
  }

  // ===========================================================================
  // Policy Violation Logging
  // ===========================================================================

  private logViolation(params: {
    sessionId: string;
    attemptedAction: string;
    violatedRule: string;
    severity: 'warning' | 'error' | 'critical';
    blocked: boolean;
    initiator: string;
    details: string;
  }): PolicyViolation {
    const violation: PolicyViolation = {
      violationId: `pv-${Date.now()}-${crypto.randomBytes(4).toString('hex')}`,
      timestamp: new Date().toISOString(),
      ...params,
    };

    this.violations.push(violation);
    this.saveViolation(violation);

    return violation;
  }

  private saveViolation(violation: PolicyViolation): void {
    const filePath = path.join(this.policyDir, 'violations', `${violation.sessionId}_violations.jsonl`);
    fs.appendFileSync(filePath, JSON.stringify(violation) + '\n', 'utf-8');
  }

  /**
   * 获取违规历史
   */
  getViolations(sessionId?: string): PolicyViolation[] {
    if (sessionId) {
      const filePath = path.join(this.policyDir, 'violations', `${sessionId}_violations.jsonl`);
      if (!fs.existsSync(filePath)) return [];
      const lines = fs.readFileSync(filePath, 'utf-8').split('\n').filter(Boolean);
      return lines.map(line => JSON.parse(line));
    }
    return [...this.violations];
  }

  // ===========================================================================
  // Main Guard Entry Point
  // ===========================================================================

  /**
   * 主入口：检查是否允许执行
   * 综合 lease、sign-off、user sovereignty 检查
   */
  canExecute(params: {
    sessionId: string;
    action: string;
    initiator: string;
    scope: string;
    issueId?: string;
  }): { allowed: boolean; reason?: string; violations: PolicyViolation[] } {
    const violations: PolicyViolation[] = [];

    // 1. 检查用户是否已拒绝
    const rejectionCheck = this.checkUserRejection(params.sessionId);
    if (rejectionCheck.rejected) {
      const pv = this.logViolation({
        sessionId: params.sessionId,
        attemptedAction: params.action,
        violatedRule: 'User rejection',
        severity: 'critical',
        blocked: true,
        initiator: params.initiator,
        details: `User rejected: ${rejectionCheck.reason}`,
      });
      violations.push(pv);
      return { allowed: false, reason: `User rejected: ${rejectionCheck.reason}`, violations };
    }

    // 2. 检查是否需要用户同意
    if (this.requiresUserConsent(params.action)) {
      // 需要用户明确同意才能执行
      return {
        allowed: false,
        reason: `Action '${params.action}' requires explicit user consent`,
        violations,
      };
    }

    // 3. 检查 lease
    const leaseCheck = this.checkLease(params.sessionId, params.action, params.initiator, params.scope);
    if (!leaseCheck.allowed && leaseCheck.violationId) {
      const pv = this.violations.find(v => v.violationId === leaseCheck.violationId);
      if (pv) violations.push(pv);
      return { allowed: false, reason: leaseCheck.reason, violations };
    }

    // 4. 检查 sign-off
    if (params.issueId) {
      const signOffCheck = this.checkSignOff(params.issueId, params.action, params.initiator);
      if (!signOffCheck.allowed && signOffCheck.violationId) {
        const pv = this.violations.find(v => v.violationId === signOffCheck.violationId);
        if (pv) violations.push(pv);
        return { allowed: false, reason: signOffCheck.reason, violations };
      }
    }

    return { allowed: true, violations: [] };
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

export const policyGuard = new PolicyGuard();
