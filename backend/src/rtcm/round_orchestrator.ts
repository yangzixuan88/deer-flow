/**
 * @file round_orchestrator.ts
 * @description U4: RTCM Round Orchestrator - Full Participation Enforced
 * 实现全员硬约束的轮次编排器
 */

import {
  FIXED_SPEAKING_ORDER,
  MANDATORY_STAGES,
  GLOBAL_HARD_RULES,
  Issue,
  MemberOutput,
  ChairSummary,
  SupervisorCheck,
} from './types';
import { PromptLoader } from './prompt_loader';
import { RuntimeStateManager } from './runtime_state';
import { DossierWriter } from './dossier_writer';
import { rtcmModelAdapter, RTCMModelAdapter } from './llm_adapter';
import {
  AutoReopenHandler,
  ReopenReason,
  ReopenResult,
  getAutoReopenHandler,
} from './auto_reopen';
import {
  parseWithRegeneration,
  validateRoundOutputs,
  RoundValidationResult,
  ParserConfig,
  RegenerationReason,
  getRegenerationReasonDescription,
} from './output_parser';

// 议员角色ID（不含 chair 和 supervisor）
const MEMBER_AGENTS = FIXED_SPEAKING_ORDER.slice(0, 8);

// 所有必须参与的角色 (8 议员 + 主持官 + 监督官)
const ALL_PARTICIPANTS = FIXED_SPEAKING_ORDER;

export interface RoundResult {
  roundNumber: number;
  stage: string;
  memberOutputs: Map<string, MemberOutput>;
  chairSummary: ChairSummary | null;
  supervisorCheck: SupervisorCheck | null;
  stageComplete: boolean;
  nextStage: string | null;
  validation: RoundValidationResult;
  blockedReason: string | null;
  regenerationEvents: RegenerationEvent[];
}

export interface RegenerationEvent {
  roleId: string;
  reason: RegenerationReason;
  description: string;
  timestamp: string;
}

export interface OrchestratorConfig {
  projectId: string;
  projectName: string;
  userGoal: string;
  maxRoundsPerIssue?: number;
  parserConfig?: ParserConfig;
}

export class RoundOrchestrator {
  private promptLoader: PromptLoader;
  private runtimeManager: RuntimeStateManager;
  private dossierWriter: DossierWriter;
  private llmAdapter: RTCMModelAdapter;
  private autoReopenHandler: AutoReopenHandler;
  private config: OrchestratorConfig | null = null;
  private currentIssue: Issue | null = null;
  private roundHistory: RoundResult[] = [];
  private regenerationEvents: RegenerationEvent[] = [];

  constructor() {
    this.promptLoader = new PromptLoader();
    this.runtimeManager = new RuntimeStateManager();
    this.dossierWriter = new DossierWriter();
    this.llmAdapter = rtcmModelAdapter;
    this.autoReopenHandler = getAutoReopenHandler(this.runtimeManager, this.dossierWriter);
  }

  /**
   * 初始化编排器
   */
  public async initialize(config: OrchestratorConfig): Promise<void> {
    console.log('[RoundOrchestrator] 初始化...');

    this.config = config;

    // 1. 加载所有Prompt
    await this.promptLoader.loadAllPrompts();

    if (!this.promptLoader.validateAllPromptsLoaded()) {
      throw new Error('[RoundOrchestrator] Prompt加载不完整');
    }

    // 2. 创建运行时会话
    await this.runtimeManager.createSession(
      config.projectId,
      config.projectName,
      config.userGoal
    );

    // 3. 初始化项目档案
    const projectSlug = config.projectId.replace(/[^a-zA-Z0-9]/g, '-').toLowerCase();
    await this.dossierWriter.initProjectDossier(
      config.projectId,
      config.projectName,
      projectSlug,
      config.userGoal,
      'system'
    );

    console.log('[RoundOrchestrator] 初始化完成');
  }

  /**
   * 开始议题讨论
   */
  public async startIssue(issue: Issue): Promise<void> {
    console.log(`[RoundOrchestrator] 开始议题: ${issue.issue_id}`);

    this.currentIssue = issue;
    this.roundHistory = [];
    this.regenerationEvents = [];

    // 更新运行时状态
    await this.runtimeManager.updateCurrentIssue(issue.issue_id);
    await this.runtimeManager.updateCurrentStage('issue_definition');
    await this.runtimeManager.updateStatus('issue_definition');

    // 写入议题卡
    await this.dossierWriter.writeIssueCard(issue);

    // 记录到 Council Log
    await this.dossierWriter.appendCouncilLog(
      'issue_started',
      'system',
      `议题开始: ${issue.issue_title}`,
      0,
      'issue_definition'
    );
  }

  /**
   * 执行一轮讨论 - 强制全员参与
   */
  public async executeRound(stage: string): Promise<RoundResult> {
    if (!this.config || !this.currentIssue) {
      throw new Error('[RoundOrchestrator] 未初始化或没有活动议题');
    }

    const session = this.runtimeManager.getSession();
    if (!session) {
      throw new Error('[RoundOrchestrator] 没有活动会话');
    }

    const currentRound = session.current_round;
    console.log(`[RoundOrchestrator] 执行第 ${currentRound} 轮 - 阶段: ${stage}`);

    // 记录轮次开始
    await this.dossierWriter.appendCouncilLog(
      'round_started',
      'system',
      `第 ${currentRound} 轮开始 - 阶段: ${stage}`,
      currentRound,
      stage
    );

    // 1. 强制按固定轮序收集所有 8 位议员输出
    const memberOutputs = await this.collectAllMemberOutputs(stage, currentRound);

    // 2. 收集主持官和监督官输出
    const chairOutput = await this.collectChairOutput(stage, currentRound);
    const supervisorOutput = await this.collectSupervisorOutput(stage, currentRound);

    // 3. 合并所有输出
    const allOutputs = new Map<string, MemberOutput>();
    memberOutputs.forEach((v, k) => allOutputs.set(k, v));
    if (chairOutput) allOutputs.set('rtcm-chair-agent', chairOutput);
    if (supervisorOutput) allOutputs.set('rtcm-supervisor-agent', supervisorOutput);

    // 4. 严格验证全员参与 (数量 + role_id 集合 + 顺序)
    const validation = validateRoundOutputs(allOutputs, ALL_PARTICIPANTS);

    // 记录成员输出
    for (const [roleId, output] of allOutputs) {
      await this.dossierWriter.appendCouncilLog(
        'member_output_received',
        roleId,
        `输出完成: ${output.current_position.substring(0, 50)}...`,
        currentRound,
        stage
      );
    }

    // 5. 主持官汇总
    const chairSummary = this.buildChairSummary(allOutputs, stage);

    await this.dossierWriter.appendCouncilLog(
      'chair_summary_published',
      'rtcm-chair-agent',
      `汇总完成 - 共识: ${chairSummary.current_consensus.length}, 分歧: ${chairSummary.current_conflicts.length}`,
      currentRound,
      stage
    );

    // 6. 监督官检查
    const supervisorCheck = this.buildSupervisorCheck(allOutputs, validation);

    await this.dossierWriter.appendCouncilLog(
      'supervisor_check_completed',
      'rtcm-supervisor-agent',
      `检查完成 - 全员到场: ${supervisorCheck.all_members_present}, 违规: ${supervisorCheck.protocol_violations.length}`,
      currentRound,
      stage
    );

    // 7. 更新运行时状态
    await this.runtimeManager.updateChairSummary(chairSummary);
    await this.runtimeManager.updateSupervisorCheck(supervisorCheck);

    // 8. 判断阶段是否完成（全员到齐、顺序正确才能关闭）
    const stageComplete = this.evaluateStageCompletion(
      stage,
      allOutputs,
      supervisorCheck,
      validation
    );

    if (stageComplete) {
      await this.dossierWriter.appendCouncilLog(
        'stage_completed',
        'system',
        `阶段 ${stage} 关闭，下一阶段: ${this.getNextStage(stage) || '无'}`,
        currentRound,
        stage
      );
    } else {
      await this.dossierWriter.appendCouncilLog(
        'stage_blocked',
        'system',
        `阶段 ${stage} 被阻断: ${validation.blockingReason}`,
        currentRound,
        stage,
        { blockedReason: validation.blockingReason || undefined }
      );
    }

    // 9. 确定下一阶段
    const nextStage = stageComplete ? this.getNextStage(stage) : null;

    const result: RoundResult = {
      roundNumber: currentRound,
      stage,
      memberOutputs: allOutputs,
      chairSummary,
      supervisorCheck,
      stageComplete,
      nextStage,
      validation,
      blockedReason: validation.blockingReason,
      regenerationEvents: [...this.regenerationEvents],
    };

    this.roundHistory.push(result);

    // 推进到下一阶段
    if (stageComplete && nextStage) {
      await this.runtimeManager.updateCurrentStage(nextStage);
      await this.runtimeManager.advanceRound();
    }

    return result;
  }

  /**
   * 收集所有 8 位议员输出 - 按固定轮序（真实 LLM 调用）
   */
  private async collectAllMemberOutputs(
    stage: string,
    round: number
  ): Promise<Map<string, MemberOutput>> {
    const outputs = new Map<string, MemberOutput>();
    const parserConfig = this.config?.parserConfig || { maxRegenerations: 1 };

    // 按固定轮序收集每位议员输出
    for (let i = 0; i < MEMBER_AGENTS.length; i++) {
      const roleId = MEMBER_AGENTS[i];

      console.log(`[RoundOrchestrator] [${i + 1}/${MEMBER_AGENTS.length}] ${roleId} 发言中...`);

      // 调用真实 LLM
      const prompt = this.buildPromptForRole(roleId, stage);
      const llmResult = await this.llmAdapter.generateMemberOutput(
        roleId,
        prompt,
        round,
        roleId
      );

      if (!llmResult.success) {
        console.warn(`[RoundOrchestrator] ⚠️ ${roleId} LLM 调用失败: ${llmResult.error}，使用 fallback`);
      }

      // 解析并验证输出（支持 regeneration）
      const parseResult = await parseWithRegeneration(
        llmResult.parsed.output || llmResult.raw,
        roleId,
        round,
        {
          ...parserConfig,
          onRegeneration: async (rId, reason, missingFields) => {
            const event: RegenerationEvent = {
              roleId: rId,
              reason,
              description: `Regeneration 触发: ${getRegenerationReasonDescription(reason)} - 缺失: ${missingFields.join(', ')}`,
              timestamp: new Date().toISOString(),
            };
            this.regenerationEvents.push(event);

            await this.dossierWriter.appendCouncilLog(
              'regeneration_triggered',
              rId,
              event.description,
              round,
              stage,
              { regenerationApplied: true }
            );

            console.warn(`[RoundOrchestrator] ⚠️ ${rId} Regeneration: ${reason}`);
          },
          onEscalation: async (rId, reason, attempts) => {
            await this.dossierWriter.appendCouncilLog(
              'escalation_triggered',
              rId,
              `Escalation: ${reason}`,
              round,
              stage
            );
            console.error(`[RoundOrchestrator] 🚨 ${rId} Escalation: ${reason}`);
          },
        }
      );

      if (parseResult.valid && parseResult.output) {
        outputs.set(roleId, parseResult.output);
        if (parseResult.regenerated) {
          console.warn(`[RoundOrchestrator] ⚠️ ${roleId} 输出已重新生成`);
        }
      } else {
        // Regeneration 全部失败后，抛出错误
        throw new Error(
          `[RoundOrchestrator] ${roleId} 输出解析在 ${parserConfig.maxRegenerations + 1} 次尝试后仍失败`
        );
      }
    }

    return outputs;
  }

  /**
   * 收集主持官输出（真实 LLM 调用）
   */
  private async collectChairOutput(
    stage: string,
    round: number
  ): Promise<MemberOutput | null> {
    const roleId = 'rtcm-chair-agent';
    const prompt = this.buildPromptForRole(roleId, stage);
    const llmResult = await this.llmAdapter.generateMemberOutput(roleId, prompt, round, roleId);

    const parseResult = await parseWithRegeneration(
      llmResult.parsed.output || llmResult.raw,
      roleId,
      round,
      { maxRegenerations: 0 }
    );

    return parseResult.valid ? parseResult.output! : null;
  }

  /**
   * 收集监督官输出（真实 LLM 调用）
   */
  private async collectSupervisorOutput(
    stage: string,
    round: number
  ): Promise<MemberOutput | null> {
    const roleId = 'rtcm-supervisor-agent';
    const prompt = this.buildPromptForRole(roleId, stage);
    const llmResult = await this.llmAdapter.generateMemberOutput(roleId, prompt, round, roleId);

    const parseResult = await parseWithRegeneration(
      llmResult.parsed.output || llmResult.raw,
      roleId,
      round,
      { maxRegenerations: 0 }
    );

    return parseResult.valid ? parseResult.output! : null;
  }

  /**
   * 为角色构建 Prompt（用于真实 LLM 调用）
   */
  private buildPromptForRole(roleId: string, stage: string): string {
    const basePrompt = this.promptLoader.getPrompt(roleId) || '';
    const outputContract = this.getStageOutputContract(stage);

    const parts: string[] = [];

    // 1. 模式声明
    parts.push('## RTCM 圆桌讨论模式\n所有成员必须按协议参与讨论，严格输出结构化 JSON。');

    // 2. 全局硬规则
    parts.push('## 全局硬规则');
    GLOBAL_HARD_RULES.forEach((rule, i) => {
      parts.push(`${i + 1}. ${rule}`);
    });

    // 3. 角色特定 Prompt
    if (basePrompt) {
      parts.push('## 角色Prompt');
      parts.push(basePrompt);
    }

    // 4. 当前议题卡
    if (this.currentIssue) {
      parts.push('## 当前议题');
      parts.push(`议题ID: ${this.currentIssue.issue_id}`);
      parts.push(`议题标题: ${this.currentIssue.issue_title}`);
      parts.push(`问题陈述: ${this.currentIssue.problem_statement}`);
    }

    // 5. 输出契约
    parts.push('## 输出要求');
    parts.push(outputContract);

    return parts.join('\n\n');
  }

  /**
   * 获取阶段输出契约
   */
  private getStageOutputContract(stage: string): string {
    const contracts: Record<string, string> = {
      problem_statement: `必须输出包含以下字段的JSON：
- current_position: 问题定义
- supported_or_opposed_hypotheses: 支持或反对的假设
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步
- should_enter_validation: 是否进入验证
- confidence_interval: 置信区间
- dissent_note_if_any: 异议（如无则填 "none"）
- unresolved_uncertainties: 未决不确定性
- evidence_ledger_refs: 证据引用`,

      hypothesis_building: `必须输出包含以下字段的JSON：
- current_position: 假设构建立场
- supported_or_opposed_hypotheses: 支持或反对的假设列表
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步
- should_enter_validation: 是否进入验证
- confidence_interval: 置信区间
- dissent_note_if_any: 异议（如无则填 "none"）
- unresolved_uncertainties: 未决不确定性
- evidence_ledger_refs: 证据引用`,

      evidence_search: `必须输出包含以下字段的JSON：
- current_position: 证据搜索立场
- supported_or_opposed_hypotheses: 支持或反对的假设
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步
- should_enter_validation: 是否进入验证
- confidence_interval: 置信区间
- dissent_note_if_any: 异议（如无则填 "none"）
- unresolved_uncertainties: 未决不确定性
- evidence_ledger_refs: 证据引用`,

      solution_generation: `必须输出包含以下字段的JSON：
- current_position: 方案生成立场
- supported_or_opposed_hypotheses: 支持或反对的假设
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步
- should_enter_validation: 是否进入验证
- confidence_interval: 置信区间
- dissent_note_if_any: 异议（如无则填 "none"）
- unresolved_uncertainties: 未决不确定性
- evidence_ledger_refs: 证据引用`,

      counterargument: `必须输出包含以下字段的JSON：
- current_position: 当前立场
- supported_or_opposed_hypotheses: 支持或反对的假设
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步
- should_enter_validation: 是否进入验证
- confidence_interval: 置信区间
- dissent_note_if_any: 异议（如无则填 "none"）
- unresolved_uncertainties: 未决不确定性
- evidence_ledger_refs: 证据引用`,

      response: `必须输出包含以下字段的JSON：
- current_position: 回应立场
- supported_or_opposed_hypotheses: 支持或反对的假设
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步
- should_enter_validation: 是否进入验证
- confidence_interval: 置信区间
- dissent_note_if_any: 异议（如无则填 "none"）
- unresolved_uncertainties: 未决不确定性
- evidence_ledger_refs: 证据引用`,

      gap_exposure: `必须输出包含以下字段的JSON：
- current_position: 差距暴露立场
- supported_or_opposed_hypotheses: 支持或反对的假设
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步
- should_enter_validation: 是否进入验证
- confidence_interval: 置信区间
- dissent_note_if_any: 异议（如无则填 "none"）
- unresolved_uncertainties: 未决不确定性
- evidence_ledger_refs: 证据引用`,

      minimum_validation_design: `必须输出包含以下字段的JSON：
- current_position: 验证设计立场
- supported_or_opposed_hypotheses: 支持或反对的假设
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步
- should_enter_validation: 是否进入验证
- confidence_interval: 置信区间
- dissent_note_if_any: 异议（如无则填 "none"）
- unresolved_uncertainties: 未决不确定性
- evidence_ledger_refs: 证据引用`,

      validation_execution: `必须输出包含以下字段的JSON：
- current_position: 验证执行立场
- supported_or_opposed_hypotheses: 支持或反对的假设
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步
- should_enter_validation: 是否进入验证
- confidence_interval: 置信区间
- dissent_note_if_any: 异议（如无则填 "none"）
- unresolved_uncertainties: 未决不确定性
- evidence_ledger_refs: 证据引用`,

      verdict: `必须输出包含以下字段的JSON：
- current_position: 裁决立场
- supported_or_opposed_hypotheses: 支持或反对的假设
- strongest_evidence: 最强证据
- largest_vulnerability: 最大弱点
- recommended_next_step: 建议下一步
- should_enter_validation: 是否进入验证
- confidence_interval: 置信区间
- dissent_note_if_any: 异议（如无则填 "none"）
- unresolved_uncertainties: 未决不确定性
- evidence_ledger_refs: 证据引用`,
    };

    return contracts[stage] || contracts['counterargument'];
  }

  /**
   * 构建主持官摘要
   */
  private buildChairSummary(
    memberOutputs: Map<string, MemberOutput>,
    stage: string
  ): ChairSummary {
    const outputs = Array.from(memberOutputs.values());

    return {
      round: this.roundHistory.length,
      current_consensus: outputs.map((o) => o.current_position),
      current_conflicts: outputs.map((o) => o.largest_vulnerability),
      strongest_support: outputs[0]?.strongest_evidence || '',
      strongest_dissent: outputs[0]?.dissent_note_if_any || '',
      unresolved_uncertainties: outputs.flatMap((o) => o.unresolved_uncertainties),
      recommended_state_transition: this.getNextStage(stage) ?? '',
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * 构建监督官检查
   */
  private buildSupervisorCheck(
    memberOutputs: Map<string, MemberOutput>,
    validation: RoundValidationResult
  ): SupervisorCheck {
    const outputs = Array.from(memberOutputs.values());
    const allHaveOutput = outputs.length === 10;
    const allParseable = outputs.every(
      (o) => o.current_position && o.recommended_next_step
    );
    const allHaveEvidence = outputs.every(
      (o) => o.strongest_evidence || o.evidence_ledger_refs.length > 0
    );
    const dissentPresent = outputs.some((o) => {
      const d = o.dissent_note_if_any.toLowerCase();
      return d !== 'none' && d !== 'no material dissent' && d !== '无实质异议' && d !== '';
    });
    const uncertaintyPresent = outputs.some(
      (o) => o.unresolved_uncertainties.length > 0
    );

    return {
      round: this.roundHistory.length,
      all_members_present: allHaveOutput && validation.orderCorrect,
      all_outputs_parseable: allParseable,
      critical_claims_have_evidence_refs: allHaveEvidence,
      dissent_present: dissentPresent,
      uncertainty_present: uncertaintyPresent,
      protocol_violations: validation.blockingReason ? [validation.blockingReason] : [],
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * 评估阶段完成情况 - 全员到齐+顺序正确才能关闭
   */
  private evaluateStageCompletion(
    stage: string,
    memberOutputs: Map<string, MemberOutput>,
    supervisorCheck: SupervisorCheck,
    validation: RoundValidationResult
  ): boolean {
    // 监督官检测到协议违规，阶段未完成
    if (supervisorCheck.protocol_violations.length > 0) {
      console.warn('[RoundOrchestrator] ⚠️ 监督官发现协议违规，阶段无法关闭');
      return false;
    }

    // 全员未到齐，阶段不能关闭
    if (!validation.allPresent) {
      return false;
    }

    // 顺序不正确，阶段不能关闭
    if (!validation.orderCorrect) {
      return false;
    }

    // 散文式输出违规，阶段不能关闭
    if (validation.proseViolations.length > 0) {
      return false;
    }

    // 根据阶段特定条件判断
    switch (stage) {
      case 'problem_statement':
        return (this.currentIssue?.problem_statement?.length ?? 0) > 0;

      case 'hypothesis_building':
        const outputs = Array.from(memberOutputs.values());
        return outputs.every((o) => o.supported_or_opposed_hypotheses.length >= 2);

      case 'verdict':
        return memberOutputs.size >= 10 && supervisorCheck.all_members_present;

      default:
        return true;
    }
  }

  /**
   * 获取下一阶段
   */
  private getNextStage(currentStage: string): string | null {
    const currentIndex = MANDATORY_STAGES.indexOf(currentStage);

    if (currentIndex < 0 || currentIndex >= MANDATORY_STAGES.length - 1) {
      return null;
    }

    return MANDATORY_STAGES[currentIndex + 1];
  }

  /**
   * 获取轮次历史
   */
  public getRoundHistory(): RoundResult[] {
    return this.roundHistory;
  }

  /**
   * 获取当前议题
   */
  public getCurrentIssue(): Issue | null {
    return this.currentIssue;
  }

  /**
   * 结束当前议题 - 需要 verdict
   */
  public async endIssue(verdict: string): Promise<void> {
    if (!this.currentIssue) {
      throw new Error('[RoundOrchestrator] 没有活动议题');
    }

    if (!verdict) {
      throw new Error('[RoundOrchestrator] 结束议题必须有 verdict');
    }

    // 更新议题状态
    this.currentIssue.status = 'resolved';
    this.currentIssue.verdict = verdict as Issue['verdict'];
    await this.dossierWriter.writeIssueCard(this.currentIssue);

    await this.dossierWriter.appendCouncilLog(
      'issue_resolved',
      'rtcm-chair-agent',
      `议题结束: ${this.currentIssue.issue_id}, 裁决: ${verdict}`,
      this.roundHistory.length,
      'verdict'
    );

    console.log(`[RoundOrchestrator] 议题结束: ${this.currentIssue.issue_id}, 裁决: ${verdict}`);
    this.currentIssue = null;
  }

  /**
   * 检查执行租约
   */
  public hasExecutionLease(): boolean {
    return this.runtimeManager.isLeaseValid();
  }

  /**
   * 请求执行租约
   */
  public async requestExecutionLease(requestedBy: string): Promise<boolean> {
    if (!this.hasExecutionLease()) {
      await this.runtimeManager.grantLease(requestedBy);
      await this.dossierWriter.appendCouncilLog(
        'lease_granted',
        requestedBy,
        `执行租约已授予`,
        this.roundHistory.length,
        this.runtimeManager.getSession()?.current_stage || 'unknown'
      );
      console.log(`[RoundOrchestrator] 执行租约已授予: ${requestedBy}`);
      return true;
    }
    console.warn('[RoundOrchestrator] 执行租约已被占用');
    return false;
  }

  /**
   * 生成 Brief Report
   */
  public async generateBriefReport(): Promise<void> {
    if (!this.currentIssue) {
      throw new Error('[RoundOrchestrator] 没有活动议题');
    }

    const session = this.runtimeManager.getSession();
    const lastResult = this.roundHistory[this.roundHistory.length - 1];

    await this.dossierWriter.writeBriefReport(
      this.config?.projectId || '',
      this.config?.projectName || '',
      this.currentIssue.issue_id,
      session?.current_stage || 'unknown',
      session?.current_round || 0,
      lastResult?.chairSummary?.current_consensus || [],
      [{ issue_id: this.currentIssue.issue_id, issue_title: this.currentIssue.issue_title, status: this.currentIssue.status, blocking_item: 'N/A' }],
      lastResult?.chairSummary?.strongest_dissent ? [lastResult.chairSummary.strongest_dissent] : [],
      lastResult?.chairSummary?.unresolved_uncertainties || [],
      '继续当前议题或等待用户输入'
    );
  }

  /**
   * 检查验证结果并自动触发 Reopen（如需要）
   */
  public async checkAndHandleValidationFailure(result: RoundResult): Promise<ReopenResult | null> {
    if (!this.currentIssue) {
      return null;
    }

    // 检查是否应该进入验证阶段
    if (this.autoReopenHandler.shouldEnterValidation(this.currentIssue)) {
      const reopenResult = this.autoReopenHandler.determineReopenFromReason('validation_failed');
      await this.autoReopenHandler.executeReopen(this.currentIssue, reopenResult, 'validation');
      return reopenResult;
    }

    return null;
  }

  /**
   * 触发 Reopen（由用户干预或系统判定）
   */
  public async triggerReopen(reason: ReopenReason, details?: string): Promise<ReopenResult> {
    if (!this.currentIssue) {
      throw new Error('[RoundOrchestrator] 没有活动议题');
    }

    const reopenResult = this.autoReopenHandler.determineReopenFromReason(reason);
    await this.autoReopenHandler.executeReopen(this.currentIssue, reopenResult, 'user');

    // 记录详细原因
    if (details) {
      await this.dossierWriter.appendCouncilLog(
        'issue_reopened',
        'user',
        `用户干预: ${details}`,
        this.runtimeManager.getSession()?.current_round || 0,
        this.runtimeManager.getSession()?.current_stage || 'unknown'
      );
    }

    return reopenResult;
  }

  /**
   * 根据 Verdict 判定是否需要 Reopen
   */
  public async handleVerdict(verdict: string): Promise<ReopenResult | null> {
    if (!this.currentIssue) {
      return null;
    }

    const reopenResult = this.autoReopenHandler.determineReopenFromVerdict(verdict as any);

    if (reopenResult.shouldReopen) {
      await this.autoReopenHandler.executeReopen(this.currentIssue, reopenResult, 'validation');
      return reopenResult;
    }

    return null;
  }

  /**
   * 清除 Reopen 标记（议题解决后调用）
   */
  public async clearReopenFlag(): Promise<void> {
    await this.autoReopenHandler.clearReopenFlag();
  }

  /**
   * 获取 Auto Reopen Handler
   */
  public getAutoReopenHandler(): AutoReopenHandler {
    return this.autoReopenHandler;
  }
}

// 单例导出
export const roundOrchestrator = new RoundOrchestrator();
