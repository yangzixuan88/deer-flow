/**
 * M11 超人运营智能 - 世界模型·动态重规划·并行仲裁
 * ================================================
 * Round 11: 从"超人能力基线"到"超人运营智能基线"
 * ================================================
 */

import { ExecutorType } from './types';

/**
 * ★ Round 11: 操作步骤输入
 */
export type StepInput = {
  instruction: string;
  goal_description: string;
  executor?: ExecutorType;
  params?: Record<string, any>;
};

/**
 * ★ Round 11: 统一世界模型 - 实体
 */
export interface WorldEntity {
  id: string;
  type: 'window' | 'tab' | 'element' | 'app' | 'process' | 'goal_object' | 'task' | 'unknown';
  state: 'active' | 'inactive' | 'unknown' | 'disappeared';
  label?: string;       // 可读名称
  source: 'dom_observed' | 'desk_observed' | 'system' | 'goal_linked' | 'inferred';
  url?: string;        // browser tab / window URL
  app_name?: string;    // desktop app name
  position?: { x: number; y: number; width: number; height: number };
  metadata: Record<string, any>;
  observed_at: string;
}

/**
 * ★ Round 11: 统一世界状态
 */
export interface WorldState {
  active_windows: WorldEntity[];
  browser_tabs: WorldEntity[];
  current_app?: WorldEntity;
  focused_target?: WorldEntity;
  observed_entities: Map<string, WorldEntity>;
  running_tasks: WorldEntity[];
  goal_linked_entities: WorldEntity[];
  last_snapshot_id: string;
  updated_at: string;
}

/**
 * ★ Round 11: 世界差异
 */
export interface WorldDelta {
  snapshot_id: string;
  previous_snapshot_id?: string;
  timestamp: string;
  added: WorldEntity[];
  removed: WorldEntity[];
  changed: Array<{ entity_id: string; before: Partial<WorldEntity>; after: Partial<WorldEntity> }>;
  goal_gap?: {
    expected_entities: string[];
    missing_entities: string[];
    unexpected_entities: string[];
  };
}

/**
 * ★ Round 11: 世界快照
 */
export interface WorldSnapshot {
  id: string;
  timestamp: string;
  state: WorldState;
  step_index: number;
  chain_id: string;
}

/**
 * ★ Round 11: 重规划触发器
 */
export interface ReplanTrigger {
  reason: 'world_delta_anomaly' | 'goal_not_progressing' | 'entity_disappeared' | 'unexpected_state' | 'resource_conflict' | 'step_timeout';
  step_index: number;
  description: string;
  world_delta?: WorldDelta;
  goal_gap?: { missing: string[]; unexpected: string[] };
}

/**
 * ★ Round 11: 重规划决策
 */
export type ReplanDecisionType = 'keep_plan' | 'local_repair' | 'replan_remaining_steps' | 'abort';

/**
 * ★ Round 11: 重规划决策
 */
export interface ReplanDecision {
  type: ReplanDecisionType;
  reason: string;
  changed_steps?: Array<{ index: number; new_instruction: string; new_goal: string; change_type: 'replace' | 'remove' | 'insert' }>;
  abort_reason?: string;
}

/**
 * ★ Round 11: 重规划轨迹
 */
export interface ReplanTrace {
  trigger: ReplanTrigger;
  decision: ReplanDecision;
  old_remaining_steps: Array<{ instruction: string; goal_description: string }>;
  new_remaining_steps: Array<{ instruction: string; goal_description: string }>;
  step_index: number;
  timestamp: string;
}

/**
 * ★ Round 11: 资源冲突
 */
export interface ResourceConflict {
  type: 'focus_steal' | 'browser_exclusive' | 'desktop_foreground' | 'executor_mutex' | 'tab_switch';
  involved_steps: number[];
  involved_entities: string[];
  description: string;
  severity: 'high' | 'medium' | 'low';
}

/**
 * ★ Round 11: 仲裁决策
 */
export type ArbitrationAction = 'postpone' | 'serialize' | 'parallel_safe' | 'abort';

/**
 * ★ Round 11: 仲裁决策
 */
export interface ArbitrationDecision {
  action: ArbitrationAction;
  conflicts: ResourceConflict[];
  serialized_steps: number[];
  postponed_steps: number[];
  parallel_segments: Array<{ steps: number[]; reason: string }>;
  reason: string;
}

/**
 * ★ Round 11: 并行跟踪
 */
export interface ParallelTrace {
  original_steps: number;
  parallel_segments: Array<{ steps: number[]; reason: string; parallelized: boolean }>;
  blocked_steps: number[];
  serialized_steps: number[];
  arbitration_decisions: ArbitrationDecision[];
  total_steps_after: number;
}

/**
 * ★ Round 11: 超人运营效率指标
 */
export interface SuperhumanOperationalMetrics {
  world_model_active: boolean;
  replanner_triggered_count: number;
  replanner_change_count: number;
  parallel_time_saved_ms: number;
  resource_conflicts_detected: number;
  serialized_due_to_conflict: number;
  world_delta_processed: boolean;
  last_world_snapshot_id?: string;
  entity_count: number;
}

// ============================================
// ★ Round 11: 统一世界模型 (WorldModel)
// ============================================
export class WorldModel {
  private snapshots: Map<string, WorldSnapshot> = new Map();
  private currentState: WorldState;
  private snapshotCounter = 0;

  constructor() {
    this.currentState = this.createEmptyState();
  }

  private createEmptyState(): WorldState {
    return {
      active_windows: [],
      browser_tabs: [],
      current_app: undefined,
      focused_target: undefined,
      observed_entities: new Map(),
      running_tasks: [],
      goal_linked_entities: [],
      last_snapshot_id: '',
      updated_at: new Date().toISOString(),
    };
  }

  private newSnapshotId(): string {
    return `snap_${Date.now()}_${++this.snapshotCounter}`;
  }

  /**
   * ★ Round 11: 纳入 DOM 观测
   */
  mergeDomObservation(domObserved: Array<{ id: string; tag: string; text?: string; href?: string; src?: string; rect?: any; visible?: boolean }>): void {
    for (const el of domObserved) {
      if (!el.visible) continue;
      const entity: WorldEntity = {
        id: el.id || `dom_${el.tag}_${Math.random().toString(36).slice(2, 6)}`,
        type: 'element',
        state: 'active',
        label: el.text?.substring(0, 100) || el.tag,
        source: 'dom_observed',
        url: el.href,
        metadata: { tag: el.tag, href: el.href, src: el.src, rect: el.rect },
        observed_at: new Date().toISOString(),
      };
      this.currentState.observed_entities.set(entity.id, entity);
    }
  }

  /**
   * ★ Round 11: 纳入桌面观测
   */
  mergeDeskObservation(deskObserved: Array<{ window_id: string; title: string; app_name: string; rect?: any; focused?: boolean; pid?: number }>): void {
    for (const win of deskObserved) {
      const entity: WorldEntity = {
        id: win.window_id,
        type: win.app_name.toLowerCase().includes('browser') || win.title.includes('/') ? 'tab' : 'window',
        state: win.focused ? 'active' : 'inactive',
        label: win.title,
        source: 'desk_observed',
        app_name: win.app_name,
        position: win.rect,
        metadata: { pid: win.pid, title: win.title },
        observed_at: new Date().toISOString(),
      };
      this.currentState.observed_entities.set(entity.id, entity);
      if (win.focused) {
        this.currentState.focused_target = entity;
        this.currentState.current_app = entity;
      }
    }
    this.currentState.active_windows = deskObserved.filter(w => w.focused).map(w => ({
      id: w.window_id,
      type: 'window' as const,
      state: 'active' as const,
      label: w.title,
      source: 'desk_observed' as const,
      app_name: w.app_name,
      position: w.rect,
      metadata: {},
      observed_at: new Date().toISOString(),
    }));
  }

  /**
   * ★ Round 11: 纳入目标链接实体
   */
  linkGoalEntities(goalDescription: string, expectedEntities: string[]): void {
    this.currentState.goal_linked_entities = expectedEntities.map((name, i) => ({
      id: `goal_entity_${i}`,
      type: 'goal_object',
      state: 'unknown' as const,
      label: name,
      source: 'goal_linked',
      metadata: { goal_description: goalDescription },
      observed_at: new Date().toISOString(),
    }));
  }

  /**
   * ★ Round 11: 快照世界状态
   */
  snapshot(stepIndex: number, chainId: string): WorldSnapshot {
    const id = this.newSnapshotId();
    const snapshot: WorldSnapshot = {
      id,
      timestamp: new Date().toISOString(),
      state: JSON.parse(JSON.stringify({
        ...this.currentState,
        observed_entities: Array.from(this.currentState.observed_entities.entries()),
      })),
      step_index: stepIndex,
      chain_id: chainId,
    };
    // Reconstruct Map from array
    if (Array.isArray(snapshot.state.observed_entities)) {
      snapshot.state.observed_entities = new Map(snapshot.state.observed_entities as any);
    }
    this.snapshots.set(id, snapshot);
    const prevId = this.currentState.last_snapshot_id;
    this.currentState.last_snapshot_id = id;
    this.currentState.updated_at = new Date().toISOString();
    return snapshot;
  }

  /**
   * ★ Round 11: 计算世界差异
   */
  computeDelta(previousSnapshotId: string): WorldDelta {
    const prev = this.snapshots.get(previousSnapshotId);
    const current = this.currentState;
    const added: WorldEntity[] = [];
    const removed: WorldEntity[] = [];
    const changed: Array<{ entity_id: string; before: Partial<WorldEntity>; after: Partial<WorldEntity> }> = [];

    const prevEntities = prev ? new Map(
      prev.state.observed_entities instanceof Map
        ? prev.state.observed_entities
        : new Map(prev.state.observed_entities as any)
    ) : new Map<string, WorldEntity>();

    const currEntities = current.observed_entities;

    // Find added and changed
    for (const [id, entity] of currEntities) {
      const prevEntity = prevEntities.get(id);
      if (!prevEntity) {
        added.push(entity);
      } else {
        const diffs: Partial<WorldEntity> = {};
        const beforeDiffs: Partial<WorldEntity> = {};
        let hasDiff = false;
        for (const key of ['state', 'label', 'url', 'app_name'] as const) {
          if ((prevEntity as any)[key] !== (entity as any)[key]) {
            (beforeDiffs as any)[key] = (prevEntity as any)[key];
            (diffs as any)[key] = (entity as any)[key];
            hasDiff = true;
          }
        }
        if (hasDiff) changed.push({ entity_id: id, before: beforeDiffs, after: diffs });
      }
    }

    // Find removed
    for (const [id, entity] of prevEntities) {
      if (!currEntities.has(id as string)) {
        removed.push(entity as WorldEntity);
      }
    }

    // Goal gap analysis
    let goalGap: WorldDelta['goal_gap'] | undefined;
    if (current.goal_linked_entities.length > 0) {
      const expectedIds = new Set(current.goal_linked_entities.map(e => e.label ?? ''));
      const missing: string[] = [];
      const unexpected: string[] = [];
      for (const expected of expectedIds) {
        if (!expected) continue;
        const found = Array.from(currEntities.values()).some(
          e => e.label?.toLowerCase().includes(expected.toLowerCase())
        );
        if (!found) missing.push(expected);
      }
      for (const [id, entity] of currEntities) {
        if (entity.source === 'goal_linked' && !expectedIds.has(entity.label || '')) {
          // Already removed, skip
        }
      }
      if (missing.length > 0 || unexpected.length > 0) {
        goalGap = { expected_entities: Array.from(expectedIds) as string[], missing_entities: missing.filter((s): s is string => !!s), unexpected_entities: unexpected };
      }
    }

    return {
      snapshot_id: current.last_snapshot_id,
      previous_snapshot_id: previousSnapshotId,
      timestamp: new Date().toISOString(),
      added,
      removed,
      changed,
      goal_gap: goalGap,
    };
  }

  /**
   * ★ Round 11: 获取当前状态
   */
  getCurrentState(): WorldState {
    return this.currentState;
  }

  /**
   * ★ Round 11: 获取实体数
   */
  getEntityCount(): number {
    return this.currentState.observed_entities.size;
  }

  /**
   * ★ Round 11: 清理旧快照（保留最近 N 个）
   */
  pruneSnapshots(keep: number = 10): void {
    const all = Array.from(this.snapshots.entries()).sort((a, b) => a[1].timestamp.localeCompare(b[1].timestamp));
    if (all.length > keep) {
      for (const [id] of all.slice(0, all.length - keep)) {
        this.snapshots.delete(id);
      }
    }
  }
}

// ============================================
// ★ Round 11: 动态重规划器 (DynamicReplanner)
// ============================================
export class DynamicReplanner {
  private replanHistory: ReplanTrace[] = [];
  private triggerCount = 0;

  /**
   * ★ Round 11: 评估是否需要重规划
   */
  evaluateReplan(
    trigger: ReplanTrigger,
    currentSteps: Array<{ instruction: string; goal_description: string }>,
    currentStepIndex: number,
    worldDelta?: WorldDelta
  ): ReplanDecision {
    this.triggerCount++;

    const remainingSteps = currentSteps.slice(currentStepIndex);

    // Rule-based replan decisions
    if (trigger.reason === 'entity_disappeared' || trigger.reason === 'world_delta_anomaly') {
      const missingGoal = trigger.goal_gap?.missing;
      const removedCount = worldDelta?.removed.length || 0;

      if (removedCount > 2 || (missingGoal && missingGoal.length > 0)) {
        // Abort - target disappeared
        return { type: 'abort', reason: `Entity disappeared: ${trigger.description}`, abort_reason: trigger.description };
      }

      if (worldDelta?.changed.length && worldDelta.changed.length <= 2) {
        // Local repair - only a few things changed
        const repaired = this.localRepair(remainingSteps, worldDelta);
        return {
          type: 'local_repair',
          reason: `Local repair: ${worldDelta.changed.length} entities changed`,
          changed_steps: repaired,
        };
      }

      // Replan remaining
      const newSteps = this.replanRemaining(remainingSteps, trigger);
      return {
        type: 'replan_remaining_steps',
        reason: `Replan remaining: ${trigger.description}`,
        changed_steps: newSteps,
      };
    }

    if (trigger.reason === 'resource_conflict') {
      return { type: 'local_repair', reason: 'Resource conflict - local repair', changed_steps: [] };
    }

    // Default: keep plan
    return { type: 'keep_plan', reason: 'No significant deviation detected' };
  }

  private localRepair(
    steps: Array<{ instruction: string; goal_description: string }>,
    delta: WorldDelta
  ): Array<{ index: number; new_instruction: string; new_goal: string; change_type: 'replace' | 'remove' | 'insert' }> {
    // Simple repair: if entities changed, try to find replacement steps
    const repairs: Array<{ index: number; new_instruction: string; new_goal: string; change_type: 'replace' }> = [];
    for (const change of delta.changed.slice(0, 1)) {
      const entity = delta.added.find(e => e.id === change.entity_id) || delta.removed[0];
      if (entity) {
        repairs.push({
          index: 0,
          new_instruction: `navigate to ${entity.url || entity.label || 'target'}`,
          new_goal: entity.label || 'target visible',
          change_type: 'replace',
        });
      }
    }
    return repairs;
  }

  private replanRemaining(
    steps: Array<{ instruction: string; goal_description: string }>,
    trigger: ReplanTrigger
  ): Array<{ index: number; new_instruction: string; new_goal: string; change_type: 'replace' | 'remove' | 'insert' }> {
    // Replace first remaining step with a more generic "observe" step
    const patch: Array<{ index: number; new_instruction: string; new_goal: string; change_type: 'replace' }> = [];
    if (steps.length > 0) {
      patch.push({
        index: 0,
        new_instruction: `observe current state and verify ${trigger.description}`,
        new_goal: 'current state observed and verified',
        change_type: 'replace',
      });
    }
    return patch;
  }

  /**
   * ★ Round 11: 执行重规划并记录轨迹
   */
  replan(
    trigger: ReplanTrigger,
    currentSteps: Array<{ instruction: string; goal_description: string }>,
    currentStepIndex: number,
    worldDelta?: WorldDelta
  ): { decision: ReplanDecision; trace: ReplanTrace } {
    const decision = this.evaluateReplan(trigger, currentSteps, currentStepIndex, worldDelta);
    const oldSteps = currentSteps.slice(currentStepIndex);

    let newSteps = oldSteps;
    if (decision.type === 'local_repair' && decision.changed_steps && decision.changed_steps.length > 0) {
      newSteps = [...oldSteps];
      for (const change of decision.changed_steps) {
        if (newSteps[change.index]) {
          newSteps[change.index] = { instruction: change.new_instruction, goal_description: change.new_goal };
        }
      }
    } else if (decision.type === 'replan_remaining_steps' && decision.changed_steps && decision.changed_steps.length > 0) {
      newSteps = [...oldSteps];
      for (const change of decision.changed_steps) {
        if (newSteps[change.index]) {
          newSteps[change.index] = { instruction: change.new_instruction, goal_description: change.new_goal };
        }
      }
    } else if (decision.type === 'abort') {
      newSteps = [];
    }

    const trace: ReplanTrace = {
      trigger,
      decision,
      old_remaining_steps: oldSteps,
      new_remaining_steps: newSteps,
      step_index: currentStepIndex,
      timestamp: new Date().toISOString(),
    };

    this.replanHistory.push(trace);
    return { decision, trace };
  }

  /**
   * ★ Round 11: 获取重规划历史
   */
  getHistory(): ReplanTrace[] {
    return this.replanHistory;
  }

  /**
   * ★ Round 11: 获取触发次数
   */
  getTriggerCount(): number {
    return this.triggerCount;
  }
}

// ============================================
// ★ Round 11: 资源仲裁器 (ResourceArbitrator)
// ============================================
export class ResourceArbitrator {
  /**
   * ★ Round 11: 分析并行可行性
   */
  assessParallelizability(steps: StepInput[]): {
    parallelizable: boolean;
    segments: Array<{ steps: number[]; reason: string; parallelized: boolean }>;
    conflicts: ResourceConflict[];
  } {
    const segments: Array<{ steps: number[]; reason: string; parallelized: boolean }> = [];
    const conflicts: ResourceConflict[] = [];
    let currentGroup: number[] = [];
    let lastApp = '';
    let lastBrowserUrl = '';

    const classifyStep = (step: typeof steps[0]): { app: string; isBrowser: boolean; url: string; executor: string } => {
      const instr = step.instruction.toLowerCase();
      const params = step.params || {};
      const isBrowser = instr.includes('navigate') || instr.includes('browser') || instr.includes('tab') || instr.includes('go to') || instr.includes('click') && !instr.includes('app');
      const app = params.app_name || (isBrowser ? 'browser' : 'cli');
      const url = params.url || '';
      const executor = step.executor || 'claude_code';
      return { app, isBrowser, url, executor };
    };

    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      const { app, isBrowser, url } = classifyStep(step);

      // Check conflict with current group
      const hasFocusConflict = currentGroup.length > 0 && isBrowser && app === lastApp;
      const hasBrowserExclusiveConflict = currentGroup.some(idx => {
        const prev = steps[idx];
        const prevClass = classifyStep(prev);
        return prevClass.isBrowser && app === 'browser' && prevClass.url !== url;
      });

      if (hasFocusConflict || hasBrowserExclusiveConflict) {
        // Save current group
        if (currentGroup.length > 0) {
          segments.push({ steps: [...currentGroup], reason: 'same focus group', parallelized: true });
        }
        currentGroup = [i];
        lastApp = app;
        lastBrowserUrl = url;

        if (hasFocusConflict) {
          conflicts.push({
            type: 'focus_steal',
            involved_steps: [currentGroup[0] || 0, i],
            involved_entities: [],
            description: `Focus conflict between step ${currentGroup[0] || 0} and ${i}`,
            severity: 'high',
          });
        }
      } else if (app !== lastApp || (isBrowser && url !== lastBrowserUrl)) {
        // Same group - can parallelize
        currentGroup.push(i);
        lastApp = app;
        lastBrowserUrl = url;
      } else {
        // Different group - end current
        if (currentGroup.length > 0) {
          segments.push({ steps: [...currentGroup], reason: 'parallel group complete', parallelized: true });
        }
        currentGroup = [i];
        lastApp = app;
        lastBrowserUrl = url;
      }
    }

    // Push last group
    if (currentGroup.length > 0) {
      segments.push({ steps: [...currentGroup], reason: 'final group', parallelized: currentGroup.length > 1 });
    }

    const hasConflicts = conflicts.length > 0;
    return { parallelizable: !hasConflicts || conflicts.every(c => c.severity === 'low'), segments, conflicts };
  }

  /**
   * ★ Round 11: 仲裁冲突
   */
  arbitrate(steps: StepInput[]): ArbitrationDecision {
    const { parallelizable, segments, conflicts } = this.assessParallelizability(steps);
    const serializedSteps: number[] = [];
    const postponedSteps: number[] = [];
    const parallelSegments: Array<{ steps: number[]; reason: string }> = [];

    if (parallelizable) {
      // All safe to parallelize
      for (const seg of segments) {
        parallelSegments.push({ steps: seg.steps, reason: seg.reason });
      }
    } else {
      // High severity conflicts - serialize
      for (const conflict of conflicts) {
        if (conflict.severity === 'high') {
          for (const stepIdx of conflict.involved_steps) {
            if (!serializedSteps.includes(stepIdx)) {
              serializedSteps.push(stepIdx);
            }
          }
        }
      }
      // Remaining without conflicts can parallelize
      const safeSteps = steps.map((_, i) => i).filter(i => !serializedSteps.includes(i));
      const safeGroups = this.groupConsecutive(safeSteps);
      for (const group of safeGroups) {
        parallelSegments.push({ steps: group, reason: 'no conflict' });
      }
    }

    return {
      action: serializedSteps.length > 0 ? 'serialize' : 'parallel_safe',
      conflicts,
      serialized_steps: serializedSteps.sort((a, b) => a - b),
      postponed_steps: postponedSteps.sort((a, b) => a - b),
      parallel_segments: parallelSegments,
      reason: serializedSteps.length > 0
        ? `${serializedSteps.length} steps serialized due to resource conflict`
        : 'All steps are parallel-safe',
    };
  }

  private groupConsecutive(numbers: number[]): number[][] {
    const groups: number[][] = [];
    let current: number[] = [];
    for (const n of numbers) {
      if (current.length > 0 && n !== current[current.length - 1] + 1) {
        groups.push(current);
        current = [];
      }
      current.push(n);
    }
    if (current.length > 0) groups.push(current);
    return groups;
  }
}

// ============================================
// ★ Round 11: 超人运营指标
// ============================================
export interface OperationalIntelligenceMetrics {
  world_model: {
    entity_count: number;
    snapshot_count: number;
    last_snapshot_id: string;
    active: boolean;
  };
  replanner: {
    triggered_count: number;
    changes_made: number;
    abort_count: number;
  };
  parallel: {
    parallel_segments: number;
    serialized_steps: number;
    conflicts_detected: number;
  };
}

/**
 * ★ Round 11: 超人运营智能引擎
 */
export class SuperhumanOperationalEngine {
  private worldModel: WorldModel;
  private replanner: DynamicReplanner;
  private arbitrator: ResourceArbitrator;

  constructor() {
    this.worldModel = new WorldModel();
    this.replanner = new DynamicReplanner();
    this.arbitrator = new ResourceArbitrator();
  }

  // World Model accessors
  getWorldModel(): WorldModel { return this.worldModel; }
  getReplanner(): DynamicReplanner { return this.replanner; }
  getArbitrator(): ResourceArbitrator { return this.arbitrator; }

  /**
   * ★ Round 11: 合并观测数据
   */
  ingestObservations(domObserved?: Array<any>, deskObserved?: Array<any>): void {
    if (domObserved?.length) this.worldModel.mergeDomObservation(domObserved);
    if (deskObserved?.length) this.worldModel.mergeDeskObservation(deskObserved);
  }

  /**
   * ★ Round 11: 快照并获取差异
   */
  snapshotAndDelta(stepIndex: number, chainId: string): { snapshot: WorldSnapshot; delta: WorldDelta } {
    const snapshot = this.worldModel.snapshot(stepIndex, chainId);
    const prevId = snapshot.state.last_snapshot_id;
    const delta = prevId ? this.worldModel.computeDelta(prevId) : {
      snapshot_id: snapshot.id,
      timestamp: snapshot.timestamp,
      added: [],
      removed: [],
      changed: [],
    };
    return { snapshot, delta };
  }

  /**
   * ★ Round 11: 触发重规划
   */
  triggerReplan(
    reason: ReplanTrigger['reason'],
    stepIndex: number,
    description: string,
    steps: Array<{ instruction: string; goal_description: string }>,
    worldDelta?: WorldDelta
  ): { decision: ReplanDecision; trace: ReplanTrace; newSteps: Array<{ instruction: string; goal_description: string }> } {
    const trigger: ReplanTrigger = { reason, step_index: stepIndex, description };
    const { decision, trace } = this.replanner.replan(trigger, steps, stepIndex, worldDelta);
    return {
      decision,
      trace,
      newSteps: trace.new_remaining_steps,
    };
  }

  /**
   * ★ Round 11: 仲裁并行
   */
  arbitrateParallel(steps: StepInput[]): { arbitration: ArbitrationDecision; trace: ParallelTrace } {
    const arbitration = this.arbitrator.arbitrate(steps);
    const trace: ParallelTrace = {
      original_steps: steps.length,
      parallel_segments: arbitration.parallel_segments.map(s => ({
        steps: s.steps,
        reason: s.reason,
        parallelized: s.steps.length > 1,
      })),
      blocked_steps: [],
      serialized_steps: arbitration.serialized_steps,
      arbitration_decisions: [arbitration],
      total_steps_after: steps.length,
    };
    return { arbitration, trace };
  }

  /**
     * ★ Round 11: 获取综合指标
   */
  getMetrics(): SuperhumanOperationalMetrics {
    const state = this.worldModel.getCurrentState();
    const replanHistory = this.replanner.getHistory();
    return {
      world_model_active: true,
      replanner_triggered_count: this.replanner.getTriggerCount(),
      replanner_change_count: replanHistory.filter(t => t.decision.type !== 'keep_plan').length,
      parallel_time_saved_ms: 0,
      resource_conflicts_detected: 0,
      serialized_due_to_conflict: 0,
      world_delta_processed: true,
      last_world_snapshot_id: state.last_snapshot_id,
      entity_count: this.worldModel.getEntityCount(),
    };
  }
}

// ============================================
// 单例
// ============================================
export const operationalEngine = new SuperhumanOperationalEngine();
