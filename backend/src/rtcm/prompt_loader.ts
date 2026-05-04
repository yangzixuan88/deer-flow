/**
 * @file prompt_loader.ts
 * @description U1: RTCM Prompt Loader
 * 加载角色Prompt模板并按规则组装
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  RTCM_PROMPTS_ROOT,
  FIXED_SPEAKING_ORDER,
  GLOBAL_HARD_RULES,
  MANDATORY_STAGES,
} from './types';

export interface PromptContext {
  mode_declaration?: string;
  global_hard_rules?: string[];
  role_specific_prompt?: string;
  project_manifest_brief?: string;
  current_issue_card?: string;
  chair_summary_last_round?: string;
  user_constraints_and_interventions?: string;
  output_contract?: string;
  role_specific_evidence_extract?: string;
  issue_graph_local_branch?: string;
  latest_validation_delta?: string;
}

export interface AssembledPrompt {
  role_id: string;
  prompt: string;
  context_profile: string;
}

export class PromptLoader {
  private promptsRoot: string;
  private promptsCache: Map<string, string> = new Map();

  constructor(promptsRoot: string = RTCM_PROMPTS_ROOT) {
    this.promptsRoot = promptsRoot;
  }

  /**
   * 加载所有角色Prompt
   */
  public async loadAllPrompts(): Promise<Map<string, string>> {
    console.log('[PromptLoader] 加载所有角色Prompt...');

    const promptFiles = [
      'chair.md',
      'supervisor.md',
      'trend.md',
      'value.md',
      'architecture.md',
      'automation.md',
      'quality.md',
      'efficiency.md',
      'challenger.md',
      'validator.md',
    ];

    for (const file of promptFiles) {
      await this.loadPrompt(file);
    }

    console.log(`[PromptLoader] 已加载 ${this.promptsCache.size} 个角色Prompt`);
    return this.promptsCache;
  }

  /**
   * 加载单个Prompt文件
   */
  public async loadPrompt(filename: string): Promise<string | null> {
    const roleId = this.filenameToRoleId(filename);
    const filePath = path.join(this.promptsRoot, filename);

    if (!fs.existsSync(filePath)) {
      console.warn(`[PromptLoader] Prompt文件不存在: ${filePath}`);
      return null;
    }

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      this.promptsCache.set(roleId, content);
      return content;
    } catch (error) {
      console.error(`[PromptLoader] 加载Prompt失败 ${filename}:`, error);
      return null;
    }
  }

  /**
   * 获取角色Prompt
   */
  public getPrompt(roleId: string): string | null {
    return this.promptsCache.get(roleId) || null;
  }

  /**
   * 按阶段组装Prompt
   */
  public assemblePrompt(
    roleId: string,
    stage: string,
    context: PromptContext
  ): AssembledPrompt {
    const basePrompt = this.getPrompt(roleId) || '';
    const contextProfile = this.getContextProfile(roleId);

    const assembled = this.buildPrompt(basePrompt, stage, context, contextProfile);

    return {
      role_id: roleId,
      prompt: assembled,
      context_profile: contextProfile,
    };
  }

  /**
   * 为所有成员组装当前轮次Prompt
   */
  public assembleRoundPrompts(
    stage: string,
    context: PromptContext
  ): AssembledPrompt[] {
    const prompts: AssembledPrompt[] = [];

    for (const roleId of FIXED_SPEAKING_ORDER) {
      if (roleId === 'rtcm-chair-agent' || roleId === 'rtcm-supervisor-agent') {
        continue; // chair和supervisor单独处理
      }
      prompts.push(this.assemblePrompt(roleId, stage, context));
    }

    return prompts;
  }

  /**
   * 构建完整Prompt
   */
  private buildPrompt(
    basePrompt: string,
    stage: string,
    context: PromptContext,
    contextProfile: string
  ): string {
    const parts: string[] = [];

    // 1. 模式声明
    if (context.mode_declaration) {
      parts.push(`## 模式声明\n${context.mode_declaration}`);
    } else {
      parts.push('## RTCM 圆桌讨论模式\n这是一个多角色协作决策系统，所有成员必须按协议参与讨论。');
    }

    // 2. 全局硬规则
    if (context.global_hard_rules) {
      parts.push('## 全局硬规则');
      context.global_hard_rules.forEach((rule, i) => {
        parts.push(`${i + 1}. ${rule}`);
      });
    }

    // 3. 角色特定Prompt
    if (basePrompt) {
      parts.push('## 角色Prompt');
      parts.push(basePrompt);
    }

    // 4. 当前议题卡
    if (context.current_issue_card) {
      parts.push('## 当前议题');
      parts.push(context.current_issue_card);
    }

    // 5. 主持官上一轮摘要
    if (context.chair_summary_last_round) {
      parts.push('## 上一轮摘要');
      parts.push(context.chair_summary_last_round);
    }

    // 6. 用户约束和干预
    if (context.user_constraints_and_interventions) {
      parts.push('## 用户输入');
      parts.push(context.user_constraints_and_interventions);
    }

    // 7. 阶段特定输出契约
    parts.push('## 输出要求');
    parts.push(this.getStageOutputContract(stage));

    return parts.join('\n\n');
  }

  /**
   * 获取阶段输出契约
   */
  private getStageOutputContract(stage: string): string {
    const contracts: Record<string, string> = {
      problem_statement: `必须输出包含以下字段的JSON：
- issue_title: 议题标题
- problem_statement: 问题陈述
- why_it_matters: 为什么重要
- relationship_to_project_goal: 与项目目标的关系
- blocking_risk_if_unsolved: 如果未解决会造成的阻塞风险`,

      hypothesis_building: `必须输出包含以下字段的JSON：
- hypotheses: 至少2个假设
- 每个假设包含: hypothesis_id, statement, why_it_may_hold, falsification_conditions`,

      evidence_search: `必须输出包含以下字段的JSON：
- evidence_summary: 证据摘要
- source_index: 来源索引
- reality_constraints: 现实约束
- evidence_ledger_entries: 证据账本条目`,

      solution_generation: `必须输出包含以下字段的JSON：
- candidate_solutions: 至少2个候选方案
- 每个方案包含: solution_id, description, pros, cons, estimated_cost`,

      counterargument: `必须输出包含以下字段的JSON：
- current_position: 当前立场
- supported_or_opposed_hypotheses: 支持或反对的假设
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步`,

      verdict: `必须输出包含以下字段的JSON：
- verdict: 裁决结果 (hypothesis_confirmed/partially_confirmed/solution_feasible_but_quality_insufficient/solution_not_feasible/evidence_insufficient)
- reasoning: 推理过程
- next_action: 下一步行动
- confidence_interval: 置信区间
- dissent_summary: 异议摘要
- unresolved_uncertainties: 未决不确定性
- conditions_to_reopen: 重开条件`,
    };

    return contracts[stage] || contracts['counterargument'];
  }

  /**
   * 根据角色ID获取上下文profile
   */
  private getContextProfile(roleId: string): string {
    const profiles: Record<string, string> = {
      'rtcm-chair-agent': 'full_control_profile',
      'rtcm-supervisor-agent': 'full_audit_profile',
      'rtcm-trend-agent': 'member_profile_trend',
      'rtcm-value-agent': 'member_profile_value',
      'rtcm-architecture-agent': 'member_profile_architecture',
      'rtcm-automation-agent': 'member_profile_automation',
      'rtcm quality-agent': 'member_profile_quality',
      'rtcm-efficiency-agent': 'member_profile_efficiency',
      'rtcm-challenger-agent': 'member_profile_challenger',
      'rtcm-validator-agent': 'member_profile_validator',
    };

    // 修复ID中的空格问题
    const normalizedRoleId = roleId.replace(/\s+/g, '-').toLowerCase();
    for (const [key, value] of Object.entries(profiles)) {
      if (key.replace(/\s+/g, '-').toLowerCase() === normalizedRoleId) {
        return value;
      }
    }

    return 'member_profile_generic';
  }

  /**
   * 将文件名转换为角色ID
   */
  private filenameToRoleId(filename: string): string {
    const base = path.basename(filename, path.extname(filename));
    const mapping: Record<string, string> = {
      'chair': 'rtcm-chair-agent',
      'supervisor': 'rtcm-supervisor-agent',
      'trend': 'rtcm-trend-agent',
      'value': 'rtcm-value-agent',
      'architecture': 'rtcm-architecture-agent',
      'automation': 'rtcm-automation-agent',
      'quality': 'rtcm quality-agent', // 注意原始名称有空格
      'efficiency': 'rtcm-efficiency-agent',
      'challenger': 'rtcm-challenger-agent',
      'validator': 'rtcm-validator-agent',
    };

    return mapping[base] || `rtcm-${base}-agent`;
  }

  /**
   * 验证所有必需的Prompt是否已加载
   */
  public validateAllPromptsLoaded(): boolean {
    const required = [
      'rtcm-chair-agent',
      'rtcm-supervisor-agent',
      'rtcm-trend-agent',
      'rtcm-value-agent',
      'rtcm-architecture-agent',
      'rtcm-automation-agent',
      'rtcm quality-agent',
      'rtcm-efficiency-agent',
      'rtcm-challenger-agent',
      'rtcm-validator-agent',
    ];

    const missing = required.filter((id) => !this.promptsCache.has(id));

    if (missing.length > 0) {
      console.warn(`[PromptLoader] 缺失的Prompt: ${missing.join(', ')}`);
      return false;
    }

    return true;
  }
}

// 单例导出
export const promptLoader = new PromptLoader();
