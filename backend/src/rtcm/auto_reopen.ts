/**
 * @file auto_reopen.ts
 * @description RTCM 自动 Reopen 机制
 * 处理 validation 失败和用户干预触发的自动状态迁移
 */

import { Issue, Verdict } from './types';
import { RuntimeStateManager } from './runtime_state';
import { DossierWriter } from './dossier_writer';

// ============================================================================
// Reopen 原因类型
// ============================================================================

export type ReopenReason =
  | 'hypothesis_wrong'
  | 'evidence_insufficient'
  | 'solution_not_feasible'
  | 'quality_insufficient'
  | 'user_intervention'
  | 'new_information_emerged'
  | 'validation_failed';

export interface ReopenResult {
  shouldReopen: boolean;
  targetStage: string | null;
  reason: ReopenReason;
  message: string;
  previousIssueStatus: string;
}

// ============================================================================
// Stage 映射表
// ============================================================================

/**
 * Verdict → 目标阶段 映射
 * 当裁决为特定结果时，reopen 应回退到对应阶段
 */
const VERDICT_TO_STAGE: Record<string, string> = {
  'hypothesis_confirmed': 'issue_definition',           // 假设被证实 → 重新定义问题
  'partially_confirmed': 'hypothesis_building',          // 部分证实 → 重新构建假设
  'evidence_insufficient': 'evidence_search',           // 证据不足 → 重新搜索证据
  'solution_not_feasible': 'solution_generation',       // 方案不可行 → 重新生成方案
  'solution_feasible_but_quality_insufficient': 'solution_generation', // 方案可行但质量不足 → 重新生成
};

/**
 * ReopenReason → 目标阶段 映射
 */
const REOPEN_REASON_TO_STAGE: Record<ReopenReason, string> = {
  'hypothesis_wrong': 'hypothesis_building',            // 假设错误 → 重新构建假设
  'evidence_insufficient': 'evidence_search',           // 证据不足 → 重新搜索证据
  'solution_not_feasible': 'solution_generation',       // 方案不可行 → 重新生成方案
  'quality_insufficient': 'solution_generation',        // 质量不足 → 重新生成方案
  'user_intervention': 'issue_definition',               // 用户干预 → 从头开始
  'new_information_emerged': 'evidence_search',         // 新信息出现 → 重新搜索证据
  'validation_failed': 'minimum_validation_design',      // 验证失败 → 重新设计验证
};

// ============================================================================
// Issue Status 映射
// ============================================================================

/**
 * 阶段 → Issue Status 映射
 */
const STAGE_TO_ISSUE_STATUS: Record<string, string> = {
  'issue_definition': 'problem_defined',
  'hypothesis_building': 'hypotheses_built',
  'evidence_search': 'evidence_collected',
  'solution_generation': 'solutions_generated',
  'counterargument': 'challenged',
  'response': 'responses_recorded',
  'gap_exposure': 'gaps_exposed',
  'minimum_validation_design': 'validation_designed',
  'validation_execution': 'validation_executed',
  'verdict': 'verdict_emitted',
};

// ============================================================================
// Auto Reopen Handler
// ============================================================================

export class AutoReopenHandler {
  private runtimeManager: RuntimeStateManager;
  private dossierWriter: DossierWriter;

  constructor(runtimeManager: RuntimeStateManager, dossierWriter: DossierWriter) {
    this.runtimeManager = runtimeManager;
    this.dossierWriter = dossierWriter;
  }

  /**
   * 根据 Verdict 判断是否需要 Reopen
   */
  public determineReopenFromVerdict(verdict: Verdict | null): ReopenResult {
    if (!verdict) {
      return {
        shouldReopen: false,
        targetStage: null,
        reason: 'validation_failed',
        message: '无 verdict，无法判断是否需要 reopen',
        previousIssueStatus: 'unknown',
      };
    }

    const verdictStr = String(verdict);
    const targetStage = VERDICT_TO_STAGE[verdictStr];

    if (!targetStage) {
      return {
        shouldReopen: false,
        targetStage: null,
        reason: 'validation_failed',
        message: `Verdict "${verdictStr}" 不需要 reopen`,
        previousIssueStatus: 'unknown',
      };
    }

    // 判断是否需要 reopen（部分裁决不需要）
    const noReopenVerdicts = ['hypothesis_confirmed'];
    if (noReopenVerdicts.includes(verdictStr)) {
      return {
        shouldReopen: false,
        targetStage: null,
        reason: 'validation_failed',
        message: `Verdict "${verdictStr}" 确认通过，无需 reopen`,
        previousIssueStatus: 'unknown',
      };
    }

    return {
      shouldReopen: true,
      targetStage,
      reason: this.verdictToReopenReason(verdictStr),
      message: `Verdict "${verdictStr}" 触发 reopen，回归阶段: ${targetStage}`,
      previousIssueStatus: STAGE_TO_ISSUE_STATUS[targetStage] || 'unknown',
    };
  }

  /**
   * 根据 ReopenReason 判断目标阶段
   */
  public determineReopenFromReason(reason: ReopenReason): ReopenResult {
    const targetStage = REOPEN_REASON_TO_STAGE[reason];

    return {
      shouldReopen: true,
      targetStage,
      reason,
      message: `ReopenReason "${reason}" 触发 reopen，回归阶段: ${targetStage}`,
      previousIssueStatus: STAGE_TO_ISSUE_STATUS[targetStage] || 'unknown',
    };
  }

  /**
   * 执行 Reopen 操作
   */
  public async executeReopen(
    issue: Issue,
    result: ReopenResult,
    triggeredBy: 'validation' | 'user' | 'system'
  ): Promise<Issue> {
    console.log(`[AutoReopen] 执行 reopen: ${result.reason} → ${result.targetStage}`);

    // 1. 更新 Issue 状态
    const updatedIssue: Issue = {
      ...issue,
      status: 'reopened',
      conditions_to_reopen: [
        ...(issue.conditions_to_reopen || []),
        `reopen_reason: ${result.reason}`,
        `triggered_by: ${triggeredBy}`,
        `timestamp: ${new Date().toISOString()}`,
      ],
    };

    // 2. 写入档案
    await this.dossierWriter.writeIssueCard(updatedIssue);

    // 3. 记录 Council Log
    await this.dossierWriter.appendCouncilLog(
      'issue_reopened',
      triggeredBy === 'user' ? 'user' : 'system',
      `议题重新打开 - 原因: ${result.reason}, 回归阶段: ${result.targetStage}`,
      this.runtimeManager.getSession()?.current_round || 0,
      this.runtimeManager.getSession()?.current_stage || 'unknown'
    );

    // 4. 更新运行时状态
    await this.runtimeManager.setReopenFlag(true);
    if (result.targetStage) {
      await this.runtimeManager.updateCurrentStage(result.targetStage);
    }

    // 5. 更新 session 状态
    const session = this.runtimeManager.getSession();
    if (session) {
      session.reopen_flag = true;
      session.status = 'reopen';
      if (result.targetStage) {
        session.current_stage = result.targetStage;
      }
      await this.runtimeManager.saveSessionState();
    }

    console.log(`[AutoReopen] Reopen 执行完成，议题状态: ${updatedIssue.status}`);
    return updatedIssue;
  }

  /**
   * 清除 Reopen 标记
   */
  public async clearReopenFlag(): Promise<void> {
    await this.runtimeManager.setReopenFlag(false);

    const session = this.runtimeManager.getSession();
    if (session) {
      session.reopen_flag = false;
      await this.runtimeManager.saveSessionState();
    }
  }

  /**
   * 将 Verdict 转换为 ReopenReason
   */
  private verdictToReopenReason(verdict: string): ReopenReason {
    const mapping: Record<string, ReopenReason> = {
      'partially_confirmed': 'hypothesis_wrong',
      'evidence_insufficient': 'evidence_insufficient',
      'solution_not_feasible': 'solution_not_feasible',
      'solution_feasible_but_quality_insufficient': 'quality_insufficient',
    };
    return mapping[verdict] || 'validation_failed';
  }

  /**
   * 检查是否应该进入验证阶段
   */
  public shouldEnterValidation(issue: Issue): boolean {
    // 如果议题已经过挑战阶段且有未解决的异议，应该进入验证
    return (
      issue.status === 'challenged' ||
      (issue.challenge_log && issue.challenge_log.length > 0)
    );
  }

  /**
   * 获取 Reopen 原因描述
   */
  public getReopenReasonDescription(reason: ReopenReason): string {
    const descriptions: Record<ReopenReason, string> = {
      'hypothesis_wrong': '假设被证伪或存在根本性错误',
      'evidence_insufficient': '现有证据不足以支持决策',
      'solution_not_feasible': '当前方案在技术上不可行',
      'quality_insufficient': '方案质量未达到可接受标准',
      'user_intervention': '用户主动干预要求重新讨论',
      'new_information_emerged': '新的关键信息出现',
      'validation_failed': '验证执行失败或结果不符合预期',
    };
    return descriptions[reason];
  }
}

// ============================================================================
// Singleton Export
// ============================================================================

let autoReopenHandlerInstance: AutoReopenHandler | null = null;

export function getAutoReopenHandler(
  runtimeManager?: RuntimeStateManager,
  dossierWriter?: DossierWriter
): AutoReopenHandler {
  if (!autoReopenHandlerInstance && runtimeManager && dossierWriter) {
    autoReopenHandlerInstance = new AutoReopenHandler(runtimeManager, dossierWriter);
  }
  if (!autoReopenHandlerInstance) {
    throw new Error('[AutoReopen] Handler 未初始化，请先传入 runtimeManager 和 dossierWriter');
  }
  return autoReopenHandlerInstance;
}
