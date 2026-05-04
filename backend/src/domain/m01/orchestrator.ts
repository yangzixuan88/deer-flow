/**
 * M01 编排引擎
 * ================================================
 * 统一入口：意图分类 → DAG规划 → 执行调度
 * ================================================
 */

import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';
import { runtimePath } from '../../runtime_paths';
import { Coordinator, coordinator } from '../m04/coordinator';
import { IntentClassifier, intentClassifier } from './intent_classifier';
import { DAGPlanner, dagPlanner } from './dag_planner';
import { DeerFlowClient, deerflowClient, DEFAULT_DEERFLOW_CONFIG } from './deerflow_client';
import { ensureContextEnvelope, injectEnvelopeIntoContext } from './context_envelope';
import {
  OrchestrationRequest,
  OrchestrationResult,
  IntentRoute,
  DAGNode,
  DAGNodeStatus,
  M01Config,
  DEFAULT_M01_CONFIG,
} from './types';

// ============================================================================
// RTCM Integration - Main Agent Handoff
// ============================================================================
import { mainAgentHandoff, HandoffRequest } from '../../rtcm/rtcm_main_agent_handoff';
import { feishuApiAdapter } from '../../rtcm/rtcm_feishu_api_adapter';
import { feishuCardRenderer } from '../../rtcm/feishu_card_renderer';
import { threadAdapter } from '../../rtcm/rtcm_thread_adapter';
import { userInterventionClassifier } from '../../rtcm/rtcm_user_intervention';
import { followUpManager } from '../../rtcm/rtcm_follow_up';

// ============================================================================
// Orchestration Engine
// ============================================================================

export class Orchestrator {
  private config: M01Config;
  private intentClassifier: IntentClassifier;
  private dagPlanner: DAGPlanner;
  private coordinator: Coordinator;
  private deerflowClient: DeerFlowClient;

  constructor(
    config: Partial<M01Config> = {},
    classifier?: IntentClassifier,
    planner?: DAGPlanner,
    dfClient?: DeerFlowClient,
  ) {
    this.config = { ...DEFAULT_M01_CONFIG, ...config };
    this.intentClassifier = classifier || intentClassifier;
    this.dagPlanner = planner || dagPlanner;
    this.coordinator = coordinator;
    this.deerflowClient = dfClient || deerflowClient;
  }

  /**
   * 执行编排请求
   */
  async execute(request: OrchestrationRequest): Promise<OrchestrationResult> {
    const startTime = Date.now();

    try {
      // R240-4: ContextEnvelope — inject into request if not already present.
      // Does NOT change any business logic. Only adds context_id/request_id.
      const ctx = ensureContextEnvelope(request as any, 'm01', 'm01');
      ctx.request_id = request.requestId;
      ctx.session_id = request.sessionId;
      injectEnvelopeIntoContext(request as any, ctx);

      // =======================================================================
      // Task 2: 检查是否存在活跃 RTCM 会话，优先拦截
      // =======================================================================
      if (mainAgentHandoff.hasActiveRTCMSession()) {
        console.log('[Orchestrator] Active RTCM session found, intercepting message');
        return this.handleRTCMIntercept(request, startTime);
      }

      // =======================================================================
      // Task 1: 意图分类 + RTCM 触发检测
      // =======================================================================
      const classification = this.intentClassifier.classify(request.userInput);
      console.log(`[Orchestrator] Classified as ${classification.route} (confidence: ${classification.confidence})`);

      // =======================================================================
      // Task 1: 检查是否触发 RTCM（显式或建议）
      // =======================================================================
      const rtcmTrigger = this.intentClassifier.needsRTCM(request.userInput);
      if (rtcmTrigger.needed) {
        console.log(`[Orchestrator] RTCM trigger detected: ${rtcmTrigger.type} (confidence: ${rtcmTrigger.confidence})`);
        return this.handleRTCMTrigger(request, rtcmTrigger, startTime);
      }

      // 步骤2: 根据路由处理
      switch (classification.route) {
        case IntentRoute.DIRECT_ANSWER:
          return this.handleDirectAnswer(request, classification, startTime);

        case IntentRoute.CLARIFICATION:
          return this.handleClarification(request, classification, startTime);

        case IntentRoute.ORCHESTRATION:
          return this.handleOrchestration(request, classification, startTime);

        default:
          throw new Error(`Unknown route: ${classification.route}`);
      }
    } catch (error) {
      return {
        requestId: request.requestId,
        success: false,
        route: IntentRoute.ORCHESTRATION,
        error: error instanceof Error ? error.message : 'Unknown error',
        executionTime: Date.now() - startTime,
      };
    }
  }

  /**
   * 路径A: 直接回答
   */
  private async handleDirectAnswer(
    request: OrchestrationRequest,
    classification: ReturnType<IntentClassifier['classify']>,
    startTime: number,
  ): Promise<OrchestrationResult> {
    // 对于简单查询，直接调用LLM回答
    // 这里简化处理，实际应该调用LLM
    return {
      requestId: request.requestId,
      success: true,
      route: IntentRoute.DIRECT_ANSWER,
      directAnswer: `已理解您的查询: ${request.userInput}。这是一个简单的直接回答场景。`,
      executionTime: Date.now() - startTime,
    };
  }

  /**
   * 路径B: 追问澄清
   */
  private async handleClarification(
    request: OrchestrationRequest,
    classification: ReturnType<IntentClassifier['classify']>,
    startTime: number,
  ): Promise<OrchestrationResult> {
    // 生成澄清问题
    const question = this.generateClarificationQuestion(request.userInput, classification);

    return {
      requestId: request.requestId,
      success: true,
      route: IntentRoute.CLARIFICATION,
      clarification: {
        question: question.question,
        dimension: question.dimension,
      },
      executionTime: Date.now() - startTime,
    };
  }

  /**
   * 路径C: 编排执行
   */
  private async handleOrchestration(
    request: OrchestrationRequest,
    classification: ReturnType<IntentClassifier['classify']>,
    startTime: number,
  ): Promise<OrchestrationResult> {
    // 构建DAG计划
    const dagPlan = this.dagPlanner.buildPlan(request);
    console.log(`[Orchestrator] Built DAG with ${dagPlan.nodes.length} nodes`);

    // 验证DAG
    if (!this.dagPlanner.validateNoCycle(dagPlan.nodes)) {
      return {
        requestId: request.requestId,
        success: false,
        route: IntentRoute.ORCHESTRATION,
        error: 'DAG contains circular dependencies',
        executionTime: Date.now() - startTime,
      };
    }

    // 根据配置选择 DeerFlow 或本地执行
    if (this.config.deerflowEnabled) {
      return this.handleDeerFlowExecution(request, dagPlan, startTime);
    } else {
      return this.handleLocalExecution(request, dagPlan, startTime);
    }
  }

  /**
   * DeerFlow 委托执行
   */
  private async handleDeerFlowExecution(
    request: OrchestrationRequest,
    dagPlan: ReturnType<DAGPlanner['buildPlan']>,
    startTime: number,
  ): Promise<OrchestrationResult> {
    console.log(`[Orchestrator] Delegating to DeerFlow (${DEFAULT_DEERFLOW_CONFIG.host}:${DEFAULT_DEERFLOW_CONFIG.port})`);

    try {
      // 检查 DeerFlow 是否可用（快速探针）
      const isHealthy = await this.deerflowClient.healthCheck();
      if (!isHealthy) {
        console.warn('[Orchestrator] DeerFlow /health not ready, probing business API...');
        // R125 Fix: /health may return false when governance bridge is down but business API is up.
        // Do a minimum business probe before falling back: try creating a thread.
        try {
          await this.deerflowClient.createThread();
          console.log('[Orchestrator] Business API probe succeeded, proceeding with DeerFlow');
        } catch {
          console.warn('[Orchestrator] Business API probe failed, falling back to local execution');
          return this.handleLocalExecution(request, dagPlan, startTime);
        }
      }

      // 委托给 DeerFlow 执行
      const result = await this.deerflowClient.executeUntilComplete(dagPlan, {
        session_id: request.sessionId,
        request_id: request.requestId,
        priority: request.priority || 'normal',
      });

      // R126 Fix: Explicit timeout fallback — timeout is not a plain failure,
      // it's a signal that DeerFlow couldn't complete in time → fallback to local.
      if (result.error === 'DeerFlow execution timeout') {
        console.warn('[Orchestrator] DeerFlow timeout, falling back to local execution');
        return this.handleLocalExecution(request, dagPlan, startTime);
      }

      return {
        requestId: request.requestId,
        success: result.success,
        route: IntentRoute.ORCHESTRATION,
        execution: {
          dagPlan: result.dag_plan,
          completedNodes: result.completed_nodes,
          totalNodes: result.total_nodes,
          duration: result.duration,
        },
        executionTime: Date.now() - startTime,
        error: result.error,
      };
    } catch (error) {
      console.error('[Orchestrator] DeerFlow execution failed, falling back:', error);
      // 网络错误时降级到本地执行
      return this.handleLocalExecution(request, dagPlan, startTime);
    }
  }

  /**
   * 本地执行（默认）
   */
  private async handleLocalExecution(
    request: OrchestrationRequest,
    dagPlan: ReturnType<DAGPlanner['buildPlan']>,
    startTime: number,
  ): Promise<OrchestrationResult> {
    console.log('[Orchestrator] Executing locally');
    const completedNodes = await this.executeDAG(dagPlan);

    return {
      requestId: request.requestId,
      success: true,
      route: IntentRoute.ORCHESTRATION,
      execution: {
        dagPlan,
        completedNodes,
        totalNodes: dagPlan.nodes.length,
        duration: Date.now() - startTime,
      },
      executionTime: Date.now() - startTime,
    };
  }

  /**
   * 执行DAG
   */
  private async executeDAG(dagPlan: ReturnType<DAGPlanner['buildPlan']>): Promise<number> {
    let completedCount = 0;

    // 按拓扑顺序执行节点
    for (const nodeId of dagPlan.executionOrder) {
      const node = dagPlan.nodes.find(n => n.id === nodeId);
      if (!node) continue;

      // 检查依赖是否都已完成
      const depsCompleted = node.dependencies.every(depId => {
        const depNode = dagPlan.nodes.find(n => n.id === depId);
        return depNode?.status === DAGNodeStatus.COMPLETED;
      });

      if (!depsCompleted) {
        node.status = DAGNodeStatus.SKIPPED;
        continue;
      }

      // 执行节点
      try {
        node.status = DAGNodeStatus.RUNNING;
        const result = await this.coordinator.execute({
          request_id: node.id,
          session_id: `dag_${dagPlan.id}`,
          system_type: node.systemType as any,
          priority: node.priority as any,
          metadata: {
            task: node.task,
            expectedOutput: node.expectedOutput,
          },
        });

        node.result = result;
        node.status = result.success ? DAGNodeStatus.COMPLETED : DAGNodeStatus.FAILED;
        if (!result.success) {
          node.error = result.error;
        }
      } catch (error) {
        node.status = DAGNodeStatus.FAILED;
        node.error = error instanceof Error ? error.message : 'Execution error';
      }

      if (node.status === DAGNodeStatus.COMPLETED) {
        completedCount++;
      }
    }

    return completedCount;
  }

  /**
   * 生成澄清问题
   */
  private generateClarificationQuestion(
    input: string,
    classification: ReturnType<IntentClassifier['classify']>,
  ): { question: string; dimension: string } {
    // 基于复杂度评估生成问题
    const complexity = classification.complexity;

    if (input.length < 5) {
      return {
        question: '您想要完成什么具体任务？',
        dimension: 'goal',
      };
    }

    if (complexity.needsSearch && !complexity.needsTools) {
      return {
        question: '您想搜索哪个具体领域或主题？',
        dimension: 'search_scope',
      };
    }

    if (complexity.needsTools) {
      return {
        question: '这个任务需要在哪个环境或系统上执行？',
        dimension: 'execution_context',
      };
    }

    return {
      question: '您能详细说明一下具体需求吗？',
      dimension: 'details',
    };
  }

  // ===========================================================================
  // Task 1 & 2: RTCM Trigger & Intercept Handlers
  // ===========================================================================

  /**
   * 处理 RTCM 触发（显式或建议）
   */
  private async handleRTCMTrigger(
    request: OrchestrationRequest,
    trigger: { needed: boolean; type: 'explicit' | 'suggested' | null; confidence: number },
    startTime: number,
  ): Promise<OrchestrationResult> {
    console.log(`[Orchestrator] Starting RTCM session for: ${request.userInput}`);

    try {
      // 配置飞书 API（如已配置）
      const appId = process.env.FEISHU_APP_ID;
      const appSecret = process.env.FEISHU_APP_SECRET;
      if (appId && appSecret) {
        feishuApiAdapter.configure({ appId, appSecret });
      }

      // 调用 RTCM entry adapter 创建会话
      const projectId = `proj-${Date.now()}`;
      const projectName = request.userInput.slice(0, 50);

      const handoffRequest: HandoffRequest = {
        trigger: trigger.type === 'explicit' ? 'explicit_rtcm_start' : 'rtcm_suggested_and_user_accepted',
        projectId,
        projectName,
        userMessage: request.userInput,
      };

      const result = mainAgentHandoff.activateRTCM(handoffRequest);

      if (!result.success) {
        return {
          requestId: request.requestId,
          success: false,
          route: IntentRoute.ORCHESTRATION,
          error: result.error || 'Failed to activate RTCM',
          executionTime: Date.now() - startTime,
        };
      }

      // 发送飞书启动卡片（如果已配置）
      // receiveId 应该是: 群聊 chat_id 或 用户 open_id/union_id
      // 当前创建飞书群聊，用返回的 chatId 作为 receiveId
      const feishuChatId = process.env.FEISHU_DEFAULT_CHAT_ID;
      if (result.mainSessionCard && appId && appSecret && feishuChatId) {
        try {
          const cardPayload = feishuCardRenderer.renderProgressCard(
            { session_id: result.sessionId!, current_stage: 'issue_definition', current_round: 0, active_members: [], pending_user_acceptance: false, created_at: new Date().toISOString(), current_issue_id: null } as any,
            'RTCM 会议已启动，等待议员发言'
          );

          // 调试日志
          console.log(`[Orchestrator] Feishu sendCardMessage:`);
          console.log(`  receiveId (chat_id): ${feishuChatId}`);
          console.log(`  card schema: ${(cardPayload as any).schema}`);

          const sendResult = await feishuApiAdapter.sendCardMessage(feishuChatId, cardPayload as any);

          console.log(`[Orchestrator] Feishu sendCardMessage result:`);
          console.log(`  success: ${sendResult.message_id ? true : false}`);
          console.log(`  message_id: ${sendResult.message_id}`);
          console.log(`  create_time: ${sendResult.create_time}`);

          // 落盘
          const feishuResultPath = runtimePath('rtcm', 'test_artifacts', 'real_feishu_send.json');
          fs.mkdirSync(path.dirname(feishuResultPath), { recursive: true });
          fs.writeFileSync(feishuResultPath, JSON.stringify({
            timestamp: new Date().toISOString(),
            receiveId: feishuChatId,
            cardType: 'interactive',
            messageId: sendResult.message_id,
            createTime: sendResult.create_time,
            sessionId: result.sessionId,
            threadId: result.threadId,
          }, null, 2));
        } catch (feishuError) {
          console.warn('[Orchestrator] Failed to send Feishu launch card:', feishuError);
        }
      } else {
        console.log('[Orchestrator] Skipping Feishu card send - missing config:');
        if (!appId) console.log('  - FEISHU_APP_ID not set');
        if (!appSecret) console.log('  - FEISHU_APP_SECRET not set');
        if (!feishuChatId) console.log('  - FEISHU_DEFAULT_CHAT_ID not set (required for group chat)');
        console.log('  - Set FEISHU_DEFAULT_CHAT_ID to a real chat_id from your Feishu app');
      }

      console.log(`[Orchestrator] RTCM session created: ${result.sessionId}, thread: ${result.threadId}`);

      return {
        requestId: request.requestId,
        success: true,
        route: IntentRoute.ORCHESTRATION,
        directAnswer: `🎬 RTCM 圆桌讨论已启动\n\n议题: ${request.userInput}\n会话ID: ${result.sessionId}\n\n主持官已就位，等待议员发言。`,
        executionTime: Date.now() - startTime,
      };
    } catch (error) {
      return {
        requestId: request.requestId,
        success: false,
        route: IntentRoute.ORCHESTRATION,
        error: error instanceof Error ? error.message : 'RTCM trigger failed',
        executionTime: Date.now() - startTime,
      };
    }
  }

  /**
   * 处理活跃 RTCM 会话的消息拦截
   */
  private async handleRTCMIntercept(
    request: OrchestrationRequest,
    startTime: number,
  ): Promise<OrchestrationResult> {
    console.log(`[Orchestrator] RTCM intercept for: ${request.userInput}`);

    try {
      const session = mainAgentHandoff.getActiveSession();
      if (!session) {
        // 会话已过期，降级到普通处理
        console.log('[Orchestrator] RTCM session expired, falling back to normal');
        const classification = this.intentClassifier.classify(request.userInput);
        return this.handleOrchestration(request, classification, startTime);
      }

      // 调用用户干预分类器
      const intervention = userInterventionClassifier.processIntervention({
        threadId: session.activeRtcmThreadId,
        sessionId: session.activeRtcmSessionId,
        issueId: 'current', // 简化处理
        userMessage: request.userInput,
      });

      const actions = userInterventionClassifier.determineActions(intervention);

      // 根据干预类型处理
      if (actions.shouldCreateFollowUpIssue) {
        // FOLLOW_UP: 创建新议题
        const parentIssue = { issue_id: 'current', issue_title: '当前议题' } as any;
        const followUpIssue = followUpManager.createFollowUpIssue({
          threadId: session.activeRtcmThreadId,
          sessionId: session.activeRtcmSessionId,
          parentIssueId: parentIssue.issue_id,
          parentIssueTitle: parentIssue.issue_title,
          newIssueTitle: actions.newIssueTitle || 'FOLLOW_UP 新议题',
          newIssueDescription: request.userInput,
          inheritedAssets: followUpManager.extractInheritedAssets(parentIssue),
          followUpRequestText: request.userInput,
          followUpType: 'new_topic_based_on_conclusion',
        });

// 更新线程状态（补全所有可用字段，避免 anchor_message.json 内容残缺）
        threadAdapter.updateAnchorMessage(session.activeRtcmThreadId, {
          currentIssueTitle: followUpIssue.issue_title,
          currentStage: 'issue_definition',
          currentProblem: followUpIssue.problem_statement || '',
          latestConsensus: [],
          strongestDissent: followUpIssue.strongest_dissent || '',
          unresolvedUncertainties: followUpIssue.unresolved_uncertainties || [],
          nextAction: followUpIssue.followUpRequestText || '',
        });

        return {
          requestId: request.requestId,
          success: true,
          route: IntentRoute.ORCHESTRATION,
          directAnswer: `📋 FOLLOW_UP 已创建\n\n新议题: ${followUpIssue.issue_title}\n继承资产: ${followUpIssue.inheritedAssets.join(', ')}`,
          executionTime: Date.now() - startTime,
        };
      }

      if (actions.shouldReopenIssue) {
        // REOPEN: 重新打开议题
        mainAgentHandoff.resumeRTCMSession({
          sessionId: session.activeRtcmSessionId,
          mode: 'reopen',
          userMessage: request.userInput,
        });

        return {
          requestId: request.requestId,
          success: true,
          route: IntentRoute.ORCHESTRATION,
          directAnswer: `🔄 议题已重新打开\n\n请继续讨论: ${request.userInput}`,
          executionTime: Date.now() - startTime,
        };
      }

      if (actions.shouldRecomputeCurrentIssue) {
        // CORRECTION/CONSTRAINT/DIRECTION_CHANGE: 重新计算当前议题
        return {
          requestId: request.requestId,
          success: true,
          route: IntentRoute.ORCHESTRATION,
          directAnswer: `✏️ 已收到您的纠正: "${request.userInput}"\n\n主持官正在重新调整议题方向...`,
          executionTime: Date.now() - startTime,
        };
      }

      // 默认：继续当前讨论
      return {
        requestId: request.requestId,
        success: true,
        route: IntentRoute.ORCHESTRATION,
        directAnswer: `💬 已收到: "${request.userInput}"\n\n主持官记录中，等待下一轮议员发言...`,
        executionTime: Date.now() - startTime,
      };
    } catch (error) {
      return {
        requestId: request.requestId,
        success: false,
        route: IntentRoute.ORCHESTRATION,
        error: error instanceof Error ? error.message : 'RTCM intercept failed',
        executionTime: Date.now() - startTime,
      };
    }
  }

  /**
   * 获取配置
   */
  getConfig(): M01Config {
    return { ...this.config };
  }
}

// ============================================
// 单例导出
// ============================================

export const orchestrator = new Orchestrator();

export { IntentClassifier, intentClassifier } from './intent_classifier';
export { DAGPlanner, dagPlanner } from './dag_planner';
export * from './types';
