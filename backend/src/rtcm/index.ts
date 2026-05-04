/**
 * @file index.ts
 * @description RTCM 圆桌讨论机制 - 主入口
 * 提供最小可运行的RTCM骨架
 */

export * from './types';
export * from './config_loader';
export * from './prompt_loader';
export * from './runtime_state';
export * from './dossier_writer';
export * from './round_orchestrator';
export * from './output_parser';
export * from './llm_adapter';
export * from './auto_reopen';
export * from './evidence_conflict_detector';

// ============================================================================
// 快速启动函数
// ============================================================================

import { RoundOrchestrator, OrchestratorConfig } from './round_orchestrator';
import { Issue } from './types';

/**
 * 创建并初始化RTCM编排器
 */
export async function createRTCMSession(config: OrchestratorConfig): Promise<RoundOrchestrator> {
  const orchestrator = new RoundOrchestrator();
  await orchestrator.initialize(config);
  return orchestrator;
}

/**
 * 创建示例议题
 */
export function createSampleIssue(
  issueId: string,
  title: string,
  problemStatement: string
): Issue {
  return {
    issue_id: issueId,
    issue_title: title,
    problem_statement: problemStatement,
    why_it_matters: '这是需要解决的关键问题',
    candidate_hypotheses: [],
    evidence_summary: '',
    challenge_log: [],
    response_summary: '',
    known_gaps: [],
    validation_plan_or_result: {
      type: 'design_only',
      plan: '待设计验证方案',
    },
    verdict: null,
    status: 'created',
    strongest_dissent: '',
    confidence_interval: '',
    unresolved_uncertainties: [],
    conditions_to_reopen: [],
    evidence_ledger_refs: [],
  };
}

// ============================================================================
// 版本信息
// ============================================================================

export const RTCM_VERSION = '1.1';
export const RTCM_MODE_ID = 'rtcm_v2';

/**
 * RTCM模块信息
 */
export const rtcmModuleInfo = {
  version: RTCM_VERSION,
  mode_id: RTCM_MODE_ID,
  description: '圆桌讨论机制 - 多角色协作决策系统',
  components: [
    'ConfigLoader - YAML配置加载 (js-yaml)',
    'PromptLoader - Prompt模板加载与组装',
    'RuntimeStateManager - 会话状态管理',
    'DossierWriter - 项目档案持久化 (完整版)',
    'RoundOrchestrator - 轮次编排器 (全员硬约束)',
    'OutputParser - 结构化输出解析器',
    'RTCMModelAdapter - LLM调用适配器 (Anthropic/OpenAI/Mock)',
    'AutoReopenHandler - 自动Reopen机制 (状态迁移+裁决映射)',
    'EvidenceConflictDetector - 证据冲突检测器 (4角色gate曝光)',
  ],
  status: 'alpha_integrable',
};
