/**
 * M01 编排引擎
 * ================================================
 * 统一入口：意图分类 → DAG规划 → 执行调度
 * ================================================
 */

import { Coordinator, coordinator } from '../m04/coordinator';
import { IntentClassifier, intentClassifier } from './intent_classifier';
import { DAGPlanner, dagPlanner } from './dag_planner';
import { DeerFlowClient, deerflowClient, DEFAULT_DEERFLOW_CONFIG } from './deerflow_client';
import {
  OrchestrationRequest,
  OrchestrationResult,
  IntentRoute,
  DAGNode,
  DAGNodeStatus,
  M01Config,
  DEFAULT_M01_CONFIG,
} from './types';

// ============================================
// 编排引擎
// ============================================

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
      // 步骤1: 意图分类
      const classification = this.intentClassifier.classify(request.userInput);
      console.log(`[Orchestrator] Classified as ${classification.route} (confidence: ${classification.confidence})`);

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
      // 检查 DeerFlow 是否可用
      const isHealthy = await this.deerflowClient.healthCheck();
      if (!isHealthy) {
        console.warn('[Orchestrator] DeerFlow unavailable, falling back to local execution');
        return this.handleLocalExecution(request, dagPlan, startTime);
      }

      // 委托给 DeerFlow 执行
      const result = await this.deerflowClient.executeUntilComplete(dagPlan, {
        session_id: request.sessionId,
        request_id: request.requestId,
        priority: request.priority || 'normal',
      });

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
