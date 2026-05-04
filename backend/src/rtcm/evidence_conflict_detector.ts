/**
 * @file evidence_conflict_detector.ts
 * @description RTCM 证据冲突检测器
 * 检测证据冲突并将其暴露给 challenger、validator、chair、supervisor
 */

import { EvidenceLedgerEntry, MemberOutput } from './types';
import { DossierWriter } from './dossier_writer';

// ============================================================================
// 冲突类型定义
// ============================================================================

export type ConflictSeverity = 'high' | 'medium' | 'low';
export type ConflictStatus = 'detected' | 'exposed' | 'resolved' | 'ignored';

export interface EvidenceConflict {
  conflict_id: string;
  severity: ConflictSeverity;
  status: ConflictStatus;
  conflicting_entries: string[];  // evidence_id 列表
  conflicting_claims: string[];    // 相互矛盾的声明
  affected_hypotheses: string[];   // 受影响的假设
  detected_by: string;             // 检测者角色
  exposed_to: string[];           // 已暴露给哪些角色
  resolution_note?: string;
  detected_at: string;
}

export interface ConflictDetectionResult {
  hasConflicts: boolean;
  conflicts: EvidenceConflict[];
  summary: string;
  recommendations: string[];
}

// ============================================================================
// 冲突检测器
// ============================================================================

export class EvidenceConflictDetector {
  private dossierWriter: DossierWriter;
  private activeConflicts: Map<string, EvidenceConflict> = new Map();

  constructor(dossierWriter: DossierWriter) {
    this.dossierWriter = dossierWriter;
  }

  /**
   * 检测证据冲突
   */
  public detectConflicts(evidenceLedger: EvidenceLedgerEntry[]): ConflictDetectionResult {
    const conflicts: EvidenceConflict[] = [];

    // 1. 检测直接冲突（同 source_type 不同 claim）
    const sourceTypeGroups = this.groupBySourceType(evidenceLedger);
    for (const [sourceType, entries] of sourceTypeGroups) {
      const claimGroups = this.groupByClaim(entries);
      for (const [claim, claimEntries] of claimGroups) {
        if (claimEntries.length > 1) {
          // 同一来源、同一声明，但可能存在矛盾
          const entry = claimEntries[0];
          if (this.hasContradiction(claimEntries)) {
            conflicts.push(this.createConflict(
              'high',
              claimEntries.map(e => e.evidence_id),
              [claim],
              entry.used_in_issue_ids,
              'contradictory_confidence_scores'
            ));
          }
        }
      }
    }

    // 2. 检测置信度冲突（同一 claim 不同 source）
    const claimGroups = this.groupByClaim(evidenceLedger);
    for (const [claim, entries] of claimGroups) {
      if (entries.length > 1) {
        const confidenceScores = entries.map(e => e.confidence);
        if (this.hasSignificantConfidenceDiff(confidenceScores)) {
          conflicts.push(this.createConflict(
            'medium',
            entries.map(e => e.evidence_id),
            [claim],
            entries.flatMap(e => e.used_in_issue_ids),
            'confidence_score_mismatch'
          ));
        }
      }
    }

    // 3. 检测证据与假设的冲突
    for (const entry of evidenceLedger) {
      if (entry.conflicts_with.length > 0) {
        conflicts.push(this.createConflict(
          'high',
          [entry.evidence_id],
          [entry.claim_supported, ...entry.conflicts_with],
          entry.used_in_issue_ids,
          'explicitly_declared_conflict'
        ));
      }
    }

    // 4. 检测重复证据（相同 source_ref）
    const sourceRefGroups = this.groupBySourceRef(evidenceLedger);
    for (const [sourceRef, entries] of sourceRefGroups) {
      if (entries.length > 1) {
        const claims = [...new Set(entries.map(e => e.claim_supported))];
        if (claims.length > 1) {
          conflicts.push(this.createConflict(
            'low',
            entries.map(e => e.evidence_id),
            claims,
            entries.flatMap(e => e.used_in_issue_ids),
            'same_source_different_claims'
          ));
        }
      }
    }

    // 更新活跃冲突列表
    for (const conflict of conflicts) {
      this.activeConflicts.set(conflict.conflict_id, conflict);
    }

    return this.buildDetectionResult(conflicts);
  }

  /**
   * 从成员输出中检测冲突
   */
  public detectConflictsFromMemberOutputs(
    outputs: Map<string, MemberOutput>
  ): ConflictDetectionResult {
    const allUnresolved: string[] = [];
    const allClaims: string[] = [];
    const evidenceRefs: Map<string, string[]> = new Map();

    // 收集所有成员输出中的证据引用
    for (const [roleId, output] of outputs) {
      allUnresolved.push(...output.unresolved_uncertainties);
      allClaims.push(output.strongest_evidence);

      for (const ref of output.evidence_ledger_refs) {
        if (!evidenceRefs.has(ref)) {
          evidenceRefs.set(ref, []);
        }
        evidenceRefs.get(ref)!.push(roleId);
      }
    }

    // 检测同一证据被用于矛盾立场
    const conflicts: EvidenceConflict[] = [];
    for (const [ref, roleIds] of evidenceRefs) {
      if (roleIds.length > 1) {
        // 检查这些角色是否持有矛盾立场
        const positions = roleIds.map(id => {
          const output = outputs.get(id);
          return output?.current_position || '';
        });

        if (this.hasPositionConflict(positions)) {
          conflicts.push(this.createConflict(
            'medium',
            [ref],
            positions,
            [],
            'evidence_used_in_conflicting_positions'
          ));
        }
      }
    }

    return this.buildDetectionResult(conflicts);
  }

  /**
   * 将冲突暴露给特定角色
   */
  public async exposeConflictsToRoles(
    conflicts: EvidenceConflict[],
    targetRoles: string[]
  ): Promise<EvidenceConflict[]> {
    const updatedConflicts: EvidenceConflict[] = [];

    for (const conflict of conflicts) {
      const updated: EvidenceConflict = {
        ...conflict,
        status: 'exposed',
        exposed_to: [...new Set([...conflict.exposed_to, ...targetRoles])],
      };
      this.activeConflicts.set(conflict.conflict_id, updated);
      updatedConflicts.push(updated);
    }

    return updatedConflicts;
  }

  /**
   * 暴露冲突给所有 gate 角色
   */
  public async exposeToAllGates(conflicts: EvidenceConflict[]): Promise<EvidenceConflict[]> {
    const gateRoles = [
      'rtcm-challenger-agent',    // 质疑官
      'rtcm-validator-agent',     // 验证官
      'rtcm-chair-agent',         // 主持官
      'rtcm-supervisor-agent',    // 监督官
    ];

    return this.exposeConflictsToRoles(conflicts, gateRoles);
  }

  /**
   * 解决冲突
   */
  public async resolveConflict(
    conflictId: string,
    resolution: string,
    resolvedBy: string
  ): Promise<boolean> {
    const conflict = this.activeConflicts.get(conflictId);
    if (!conflict) {
      return false;
    }

    conflict.status = 'resolved';
    conflict.resolution_note = `${resolution} (by ${resolvedBy} at ${new Date().toISOString()})`;

    await this.dossierWriter.appendCouncilLog(
      'issue_resolved',  // 借用事件类型
      resolvedBy,
      `证据冲突已解决: ${conflictId} - ${resolution}`,
      0,
      'evidence_conflict'
    );

    return true;
  }

  /**
   * 获取所有活跃冲突
   */
  public getActiveConflicts(): EvidenceConflict[] {
    return Array.from(this.activeConflicts.values()).filter(
      c => c.status === 'detected' || c.status === 'exposed'
    );
  }

  /**
   * 获取指定严重级别的冲突
   */
  public getConflictsBySeverity(severity: ConflictSeverity): EvidenceConflict[] {
    return Array.from(this.activeConflicts.values()).filter(
      c => c.severity === severity && c.status !== 'resolved'
    );
  }

  /**
   * 检查是否有未解决的高严重度冲突
   */
  public hasUnresolvedHighSeverityConflicts(): boolean {
    return Array.from(this.activeConflicts.values()).some(
      c => c.severity === 'high' && c.status !== 'resolved'
    );
  }

  // ============================================================================
  // 私有辅助方法
  // ============================================================================

  private groupBySourceType(entries: EvidenceLedgerEntry[]): Map<string, EvidenceLedgerEntry[]> {
    const groups = new Map<string, EvidenceLedgerEntry[]>();
    for (const entry of entries) {
      if (!groups.has(entry.source_type)) {
        groups.set(entry.source_type, []);
      }
      groups.get(entry.source_type)!.push(entry);
    }
    return groups;
  }

  private groupByClaim(entries: EvidenceLedgerEntry[]): Map<string, EvidenceLedgerEntry[]> {
    const groups = new Map<string, EvidenceLedgerEntry[]>();
    for (const entry of entries) {
      const normalizedClaim = this.normalizeClaim(entry.claim_supported);
      if (!groups.has(normalizedClaim)) {
        groups.set(normalizedClaim, []);
      }
      groups.get(normalizedClaim)!.push(entry);
    }
    return groups;
  }

  private groupBySourceRef(entries: EvidenceLedgerEntry[]): Map<string, EvidenceLedgerEntry[]> {
    const groups = new Map<string, EvidenceLedgerEntry[]>();
    for (const entry of entries) {
      if (!groups.has(entry.source_ref)) {
        groups.set(entry.source_ref, []);
      }
      groups.get(entry.source_ref)!.push(entry);
    }
    return groups;
  }

  private normalizeClaim(claim: string): string {
    // 标准化声明以便比较
    return claim.toLowerCase().replace(/\s+/g, ' ').trim();
  }

  private hasContradiction(entries: EvidenceLedgerEntry[]): boolean {
    // 检测是否存在矛盾声明
    const claims = entries.map(e => this.normalizeClaim(e.claim_supported));
    const uniqueClaims = [...new Set(claims)];
    return uniqueClaims.length > 1;
  }

  private hasSignificantConfidenceDiff(scores: number[]): boolean {
    if (scores.length < 2) return false;
    const max = Math.max(...scores);
    const min = Math.min(...scores);
    return (max - min) > 0.3; // 30% 以上差异视为显著
  }

  private hasPositionConflict(positions: string[]): boolean {
    if (positions.length < 2) return false;
    // 检查立场是否存在矛盾关键词
    const conflictKeywords = ['但', '然而', '相反', '反对', '不是', '无法', '否定'];
    const positionTexts = positions.join(' ').toLowerCase();

    // 简单检测：是否有否定词
    const hasNegation = positions.some(p =>
      /\b(不是|无法|反对|否定|不行)\b/.test(p)
    );

    return hasNegation && positions.some(p =>
      /\b(是|可以|支持|同意)\b/.test(p)
    );
  }

  private createConflict(
    severity: ConflictSeverity,
    evidenceIds: string[],
    claims: string[],
    issueIds: string[],
    conflictType: string
  ): EvidenceConflict {
    return {
      conflict_id: `conflict-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      severity,
      status: 'detected',
      conflicting_entries: evidenceIds,
      conflicting_claims: claims,
      affected_hypotheses: issueIds,
      detected_by: 'evidence_conflict_detector',
      exposed_to: [],
      detected_at: new Date().toISOString(),
    };
  }

  private buildDetectionResult(conflicts: EvidenceConflict[]): ConflictDetectionResult {
    const highSeverity = conflicts.filter(c => c.severity === 'high');
    const mediumSeverity = conflicts.filter(c => c.severity === 'medium');
    const lowSeverity = conflicts.filter(c => c.severity === 'low');

    const recommendations: string[] = [];
    if (highSeverity.length > 0) {
      recommendations.push('高严重度冲突必须立即暴露给质疑官和监督官');
    }
    if (mediumSeverity.length > 0) {
      recommendations.push('中严重度冲突应暴露给主持官和验证官');
    }
    if (lowSeverity.length > 0) {
      recommendations.push('低严重度冲突记录在案，可选择在最终报告中说明');
    }

    return {
      hasConflicts: conflicts.length > 0,
      conflicts,
      summary: `检测到 ${conflicts.length} 个冲突（高: ${highSeverity.length}, 中: ${mediumSeverity.length}, 低: ${lowSeverity.length}）`,
      recommendations,
    };
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

let conflictDetectorInstance: EvidenceConflictDetector | null = null;

export function getEvidenceConflictDetector(dossierWriter?: DossierWriter): EvidenceConflictDetector {
  if (!conflictDetectorInstance && dossierWriter) {
    conflictDetectorInstance = new EvidenceConflictDetector(dossierWriter);
  }
  if (!conflictDetectorInstance) {
    throw new Error('[EvidenceConflictDetector] 未初始化，请先传入 dossierWriter');
  }
  return conflictDetectorInstance;
}
