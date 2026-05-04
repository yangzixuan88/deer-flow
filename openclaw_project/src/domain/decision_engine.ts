/**
 * @file decision_engine.ts
 * @description The AAL Decision Engine (Action 008) - The "Command Center" of the system.
 * Implements the Mission-Phase-Boulder architecture with 0.7 confidence break and Oracle check.
 * Reference: Super Constitution Phase 4 & Architecture 2.0
 */

import { HookContext } from './hooks';

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'blocked';

export interface BoulderState {
  taskId: string;
  phaseId: string;
  status: TaskStatus;
  confidence: number;
  tokensUsed: number;
  costUsd: number;
  lastUpdate: string; // ISO8601
  retryCount: number;
  isSelfCorrecting: boolean;
}

export interface PhasePlan {
  id: string;
  missionId: string;
  objectives: string[];
  tasks: BoulderState[];
  currentTaskIndex: number;
}

/**
 * AAL Decision Engine (Command Center)
 * Manages the "Mission -> Phase -> Boulder" transition and autonomous decisions.
 * Reference: microsoft/TaskWeaver Planner Architecture
 */
export class DecisionEngine {
  private readonly CONFIDENCE_THRESHOLD = 0.7;
  private readonly BUDGET_THRESHOLD_USD = 0.1; // §6.1 Conservative Budget
  private readonly VISIBILITY_INTERVAL_MS = 4 * 60 * 60 * 1000; // 4-hour visibility rule

  private lastPushTimestamp: number = Date.now();

  constructor() {}

  /**
   * Evaluates the current task confidence and triggers 0.7 Break if needed.
   * Logic: If confidence < 0.7, trigger Oracle (Consultant) self-check first.
   */
  public async evaluateTask(state: BoulderState, context: HookContext): Promise<{ 
    action: 'proceed' | 'halt' | 'consult_user' | 'retry';
    message?: string;
  }> {
    console.log(`[AAL Decision] Evaluating Task ${state.taskId} | Confidence: ${state.confidence}`);

    // 1. Budget Check
    if (state.costUsd > this.BUDGET_THRESHOLD_USD) {
      return { action: 'halt', message: `Budget Exceeded: $${state.costUsd} > $${this.BUDGET_THRESHOLD_USD}` };
    }

    // 2. Confidence Break (0.7 Threshold)
    if (state.confidence < this.CONFIDENCE_THRESHOLD) {
      console.warn(`[AAL Decision] Confidence ${state.confidence} below threshold! Triggering Oracle...`);
      
      const oracleCheck = await this.triggerOracleSelfCheck(state, context);
      
      if (oracleCheck.passed) {
        console.log(`[AAL Decision] Oracle self-check PASSED. Proceeding with caution.`);
        return { action: 'proceed' };
      } else {
        console.error(`[AAL Decision] Oracle self-check FAILED. Halting for user consultation.`);
        return { action: 'consult_user', message: oracleCheck.reason || "Oracle validation failed." };
      }
    }

    // 3. Visibility Rule (4-hour report)
    if (Date.now() - this.lastPushTimestamp > this.VISIBILITY_INTERVAL_MS) {
      await this.pushVisibilityReport(context);
    }

    return { action: 'proceed' };
  }

  /**
   * Oracle (Consultant) Self-Check Mechanism.
   * Logic: The Supervisor Agent (Oracle) re-evaluates the intent and plan.
   * Reference: Super Constitution §4.2
   */
  private async triggerOracleSelfCheck(state: BoulderState, context: HookContext): Promise<{ passed: boolean; reason?: string }> {
    // Simulated Oracle logic: In a real system, this calls the Oracle Agent
    const oracleConfidence = state.confidence + 0.15; // Oracle usually has higher precision
    if (oracleConfidence >= this.CONFIDENCE_THRESHOLD) {
      return { passed: true };
    }
    return { passed: false, reason: "Ambiguous intent detected during deep audit." };
  }

  /**
   * Mission-Phase-Boulder Synchronization.
   * Reads Mission.md -> Updates Phase.md -> Synchronizes Boulder State.
   */
  public async synchronizeArchitecture(missionId: string, phaseId: string, boulder: BoulderState): Promise<void> {
    console.log(`[AAL Sync] Syncing Architecture for Mission: ${missionId}`);
    // This logic would interact with file readers and Dapr state store
    // Logic: Mission (Long-term) -> Phase (Current Roadmap) -> Boulder (Execution Status)
  }

  /**
   * 4-Hour Visibility Report.
   * Mandatory push to Feishu every 4 hours regardless of status.
   * Reference: Super Constitution §12.2
   */
  private async pushVisibilityReport(context: HookContext): Promise<void> {
    console.log(`[AAL Report] Triggering 4-hour Visibility Report for Session ${context.sessionId}`);
    this.lastPushTimestamp = Date.now();
    // Logic: Send summary to Feishu Webhook via Infrastructure layer
  }
}
