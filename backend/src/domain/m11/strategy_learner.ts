/**
 * M11 超人化系统 - 策略学习·资产化·效率化
 * ================================================
 * Round 10: 从"稳定类人操作"到"超人化学习+资产+效率"
 * ================================================
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../../runtime_paths';
import { ExecutorType } from './types';
import { classifyOperation, OperationType } from './adapters/executor_adapter';

/**
 * ★ Round 10: 策略历史记录结构
 */
export interface StrategyHistoryRecord {
  id: string;
  task_type: OperationType;
  app_type?: string;         // desktop app name, e.g. 'gimp', 'notepad'
  web_target?: string;        // URL pattern, e.g. 'github.com'
  instruction_hash: string;  // 指令摘要（用于相似度匹配）
  instruction: string;
  executor_used: ExecutorType;
  executor_backup?: ExecutorType;   // 如果发生了 fallback
  fallback_triggered: boolean;
  success: boolean;
  goal_achieved: boolean;
  goal_description: string;
  execution_time_ms?: number;
  timestamp: string;
}

/**
 * ★ Round 10: 执行器成功率统计
 */
export interface ExecutorSuccessStats {
  executor: ExecutorType;
  attempts: number;
  successes: number;
  failures: number;
  success_rate: number;          // 0-1
  consecutive_failures: number;
  last_success?: string;
  last_failure?: string;
}

/**
 * ★ Round 10: 策略学习结果（选择解释）
 */
export interface StrategySelectionResult {
  executor_selected: ExecutorType;
  backup_executor?: ExecutorType;
  selection_reason: string;
  strategy_history_used: boolean;
  historical_success_rate?: number;   // 该执行器对此类任务的历史成功率
  executor_preference_shift?: string; // 如果发生了偏好转移，说明原因
  confidence: 'high' | 'medium' | 'low';
  asset_hit?: {
    asset_id: string;
    similarity: number;
    reuse_recommended: boolean;
  };
}

/**
 * ★ Round 10: 操作资产（成功链路沉淀）
 */
export interface OperationAsset {
  id: string;
  name: string;
  task_signature: string;         // 任务签名（instruction 的 hash）
  task_type: OperationType;
  app_type?: string;
  web_target?: string;
  instruction_pattern: string;     // 原始指令模式
  executor_sequence: ExecutorType[]; // 执行器序列
  verification_pattern: string;     // 目标验证模式
  fallback_pattern?: string;       // fallback 模式描述
  steps: Array<{
    instruction: string;
    goal_description: string;
    executor: ExecutorType;
  }>;
  // 资产元数据
  metadata: {
    created_at: string;
    last_used_at: string;
    use_count: number;
    success_count: number;
    success_rate: number;          // 0-1
    environment_tags: string[];    // e.g. ['windows', 'gimp-2.10']
    version: number;
  };
}

/**
 * ★ Round 10: 超人效率指标
 */
export interface SuperhumanMetrics {
  time_saved_estimate_ms: number;
  reused_steps: number;
  shortcut_used: boolean;
  shortcut_reason?: string;
  parallelizable_segments: string[];
  batch_size?: number;
  compression_ratio?: number;      // 重复操作被压缩的比例
  efficiency_gain?: number;        // 综合效率提升 (0-1)
}

/**
 * ============================================
 * ★ Round 10: 策略学习器 (StrategyLearner)
 * ============================================
 *
 * 核心功能：
 * 1. 记录每次执行的策略选择和结果
 * 2. 统计各执行器在不同任务类型上的成功率
 * 3. 基于历史调整执行器选择偏好
 * 4. 输出可解释的策略决策
 */
export class StrategyLearner {
  private strategyHistory: StrategyHistoryRecord[] = [];
  private executorStats: Map<string /* task_type:executor */, ExecutorSuccessStats> = new Map();
  private assetDir: string;
  private historyFile: string;

  constructor(assetDir?: string) {
    this.assetDir = assetDir || runtimePath('strategy_learner');
    this.historyFile = path.join(this.assetDir, 'strategy_history.json');
    this.ensureDir();
    this.loadHistory();
  }

  private ensureDir(): void {
    try {
      if (!fs.existsSync(this.assetDir)) {
        fs.mkdirSync(this.assetDir, { recursive: true });
      }
    } catch { /* ignore */ }
  }

  private loadHistory(): void {
    try {
      if (fs.existsSync(this.historyFile)) {
        const data = JSON.parse(fs.readFileSync(this.historyFile, 'utf-8'));
        this.strategyHistory = data.history || [];
        if (data.executorStats) {
          for (const [key, val] of Object.entries(data.executorStats)) {
            this.executorStats.set(key, val as ExecutorSuccessStats);
          }
        }
      }
    } catch { /* ignore */ }
  }

  private saveHistory(): void {
    try {
      const executorStatsObj: Record<string, ExecutorSuccessStats> = {};
      for (const [k, v] of this.executorStats) {
        executorStatsObj[k] = v;
      }
      fs.writeFileSync(this.historyFile, JSON.stringify({
        history: this.strategyHistory.slice(-500), // 只保留最近 500 条
        executorStats: executorStatsObj,
        saved_at: new Date().toISOString(),
      }, null, 2));
    } catch { /* ignore */ }
  }

  /**
   * ★ Round 10: 基于历史选择执行器
   *
   * @param instruction 指令
   * @param params 执行参数
   * @returns 策略选择结果（含解释）
   */
  selectWithLearning(
    instruction: string,
    params: Record<string, any> = {}
  ): StrategySelectionResult {
    const taskType = classifyOperation(instruction);
    const appType = params.appName;
    const webTarget = this.extractWebTarget(params.url || instruction);

    // 查询历史成功率
    const stats = this.getExecutorStats(taskType, appType);
    const defaultExecutor = this.getDefaultExecutor(taskType);

    // 如果有足够的历史数据（>=2次），根据成功率调整
    if (stats.length >= 2) {
      const bestExecutor = this.selectBestExecutor(stats, taskType);
      if (bestExecutor && bestExecutor.executor !== defaultExecutor) {
        const defaultStat = defaultExecutor ? (stats.find(s => s.executor === defaultExecutor) ?? null) : null;
        const shift = this.describePreferenceShift(defaultStat, bestExecutor, stats);
        return {
          executor_selected: bestExecutor.executor,
          selection_reason: `Historical success rate: ${(bestExecutor.success_rate * 100).toFixed(0)}% vs default ${(defaultStat ? defaultStat.success_rate : 0) * 100}%`,
          strategy_history_used: true,
          historical_success_rate: bestExecutor.success_rate,
          executor_preference_shift: shift,
          confidence: bestExecutor.success_rate >= 0.7 ? 'high' : bestExecutor.success_rate >= 0.4 ? 'medium' : 'low',
        };
      }
    }

    // 无历史数据或数据不足，使用默认选择
    return {
      executor_selected: defaultExecutor,
      selection_reason: `Default selection (no sufficient history for task_type=${taskType})`,
      strategy_history_used: false,
      historical_success_rate: stats.length > 0 ? stats[0]?.success_rate : undefined,
      confidence: 'low',
    };
  }

  /**
   * ★ Round 10: 记录执行结果（每次执行后调用）
   */
  recordOutcome(
    instruction: string,
    executorUsed: ExecutorType,
    success: boolean,
    goalAchieved: boolean,
    fallbackTriggered: boolean = false,
    backupExecutor?: ExecutorType,
    params: Record<string, any> = {},
    goalDescription: string = '',
    executionTimeMs?: number
  ): void {
    const taskType = classifyOperation(instruction);
    const appType = params.appName;
    const webTarget = this.extractWebTarget(params.url || instruction);

    const record: StrategyHistoryRecord = {
      id: `sh_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      task_type: taskType,
      app_type: appType,
      web_target: webTarget,
      instruction_hash: this.hashInstruction(instruction),
      instruction,
      executor_used: executorUsed,
      executor_backup: backupExecutor,
      fallback_triggered: fallbackTriggered,
      success,
      goal_achieved: goalAchieved,
      goal_description: goalDescription,
      execution_time_ms: executionTimeMs,
      timestamp: new Date().toISOString(),
    };

    this.strategyHistory.push(record);

    // 更新执行器统计
    this.updateStats(taskType, appType, executorUsed, success);

    // 保存
    this.saveHistory();
  }

  /**
   * ★ Round 10: 获取某任务类型的历史记录
   */
  getHistory(taskType?: OperationType, limit: number = 10): StrategyHistoryRecord[] {
    let records = this.strategyHistory;
    if (taskType) {
      records = records.filter(r => r.task_type === taskType);
    }
    return records.slice(-limit);
  }

  /**
   * ★ Round 10: 获取执行器成功率统计
   */
  getExecutorStats(taskType: OperationType, appType?: string): ExecutorSuccessStats[] {
    const stats: ExecutorSuccessStats[] = [];
    const prefix = appType ? `${taskType}:${appType}:` : `${taskType}:_default_:`;

    // Find all stats entries matching this taskType and appType (keys are taskType:appType:executor)
    for (const [key, stat] of this.executorStats.entries()) {
      if (key.startsWith(prefix) && stat.attempts > 0) {
        stats.push(stat);
      }
    }

    return stats;
  }

  private getDefaultExecutor(taskType: OperationType): ExecutorType {
    switch (taskType) {
      case OperationType.WEB_BROWSER: return ExecutorType.OPENCLI;
      case OperationType.DESKTOP_APP: return ExecutorType.CLI_ANYTHING;
      case OperationType.CLI_TOOL: return ExecutorType.CLI_ANYTHING;
      default: return ExecutorType.CLAUDE_CODE;
    }
  }

  private extractWebTarget(urlOrInstruction: string): string | undefined {
    try {
      const match = urlOrInstruction.match(/https?:\/\/([^\/]+)/);
      return match ? match[1] : undefined;
    } catch {
      return undefined;
    }
  }

  private hashInstruction(instruction: string): string {
    // 简单的哈希用于相似度匹配
    const normalized = instruction.toLowerCase().replace(/[^\w]/g, '').slice(0, 50);
    let hash = 0;
    for (let i = 0; i < normalized.length; i++) {
      hash = ((hash << 5) - hash) + normalized.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash).toString(36);
  }

  private updateStats(taskType: OperationType, appType: string | undefined, executor: ExecutorType, success: boolean): void {
    // Key includes executor so each executor has separate stats
    const key = appType ? `${taskType}:${appType}:${executor}` : `${taskType}:_default_:${executor}`;
    let stats = this.executorStats.get(key);

    if (!stats) {
      stats = {
        executor,
        attempts: 0,
        successes: 0,
        failures: 0,
        success_rate: 0,
        consecutive_failures: 0,
      };
      this.executorStats.set(key, stats);
    }

    stats.executor = executor;
    stats.attempts++;
    if (success) {
      stats.successes++;
      stats.consecutive_failures = 0;
      stats.last_success = new Date().toISOString();
    } else {
      stats.failures++;
      stats.consecutive_failures++;
      stats.last_failure = new Date().toISOString();
    }
    stats.success_rate = stats.attempts > 0 ? stats.successes / stats.attempts : 0;
  }

  private selectBestExecutor(stats: ExecutorSuccessStats[], taskType: OperationType): ExecutorSuccessStats | null {
    if (stats.length === 0) return null;

    // 优先选择：成功率高且最近成功过的
    // 连续失败 >= 3 次的执行器降权
    const viable = stats.filter(s => s.consecutive_failures < 3);
    if (viable.length === 0) return null;

    // 按成功率排序
    viable.sort((a, b) => b.success_rate - a.success_rate);
    return viable[0];
  }

  private describePreferenceShift(from: ExecutorSuccessStats | null, to: ExecutorSuccessStats | null, stats: ExecutorSuccessStats[]): string {
    if (!from || !to) return 'Executor shift: insufficient data';

    const fromRate = (from.success_rate * 100).toFixed(0);
    const toRate = (to.success_rate * 100).toFixed(0);
    return `Executor preference shifted from ${from.executor}(${fromRate}% hist) to ${to.executor}(${toRate}% hist)`;
  }
}

// ============================================
// ★ Round 10: 操作资产注册表
// ============================================

/**
 * 操作资产注册表
 * 负责：
 * 1. 从成功链路提取结构化资产
 * 2. 存储和版本管理
 * 3. 相似任务检索和复用
 */
export class OperationAssetRegistry {
  private assets: Map<string, OperationAsset> = new Map();
  private assetDir: string;
  private registryFile: string;
  private learner: StrategyLearner;

  constructor(assetDir?: string, learner?: StrategyLearner) {
    this.assetDir = assetDir || runtimePath('operation_assets');
    this.registryFile = path.join(this.assetDir, 'asset_registry.json');
    this.learner = learner || new StrategyLearner();
    this.ensureDir();
    this.loadRegistry();
  }

  private ensureDir(): void {
    try {
      if (!fs.existsSync(this.assetDir)) {
        fs.mkdirSync(this.assetDir, { recursive: true });
      }
    } catch { /* ignore */ }
  }

  private loadRegistry(): void {
    try {
      if (fs.existsSync(this.registryFile)) {
        const data = JSON.parse(fs.readFileSync(this.registryFile, 'utf-8'));
        for (const asset of (data.assets || [])) {
          this.assets.set(asset.id, asset);
        }
      }
    } catch { /* ignore */ }
  }

  private saveRegistry(): void {
    try {
      fs.writeFileSync(this.registryFile, JSON.stringify({
        assets: Array.from(this.assets.values()),
        saved_at: new Date().toISOString(),
      }, null, 2));
    } catch { /* ignore */ }
  }

  /**
   * ★ Round 10: 从成功链路提取操作资产
   */
  extractFromChain(
    taskId: string,
    steps: Array<{ instruction: string; goal_description: string; executor: ExecutorType }>,
    params: Record<string, any> = {}
  ): OperationAsset | null {
    if (steps.length === 0) return null;

    const firstStep = steps[0];
    const taskType = classifyOperation(firstStep.instruction);

    const asset: OperationAsset = {
      id: `asset_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      name: this.generateAssetName(firstStep.instruction, taskType),
      task_signature: this.computeSignature(steps),
      task_type: taskType,
      app_type: params.appName,
      web_target: this.extractWebTarget(params.url || firstStep.instruction),
      instruction_pattern: this.normalizeInstruction(firstStep.instruction),
      executor_sequence: steps.map(s => s.executor),
      verification_pattern: firstStep.goal_description,
      steps: steps.map(s => ({
        instruction: s.instruction,
        goal_description: s.goal_description,
        executor: s.executor,
      })),
      metadata: {
        created_at: new Date().toISOString(),
        last_used_at: new Date().toISOString(),
        use_count: 0,
        success_count: 0,
        success_rate: 0,
        environment_tags: this.inferEnvironmentTags(params),
        version: 1,
      },
    };

    return asset;
  }

  /**
   * ★ Round 10: 保存操作资产
   */
  registerAsset(asset: OperationAsset): void {
    // 检查是否已存在相似资产（增加版本）
    const hit = this.findSimilarAsset(asset.instruction_pattern, { appName: asset.app_type, url: asset.web_target });
    if (hit) {
      const existing = hit.asset;
      // 合并到现有资产
      existing.metadata.version++;
      existing.metadata.last_used_at = new Date().toISOString();
      // 更新步骤（如果新资产更长）
      if (asset.steps.length > existing.steps.length) {
        existing.steps = asset.steps;
        existing.executor_sequence = asset.executor_sequence;
      }
      this.assets.set(existing.id, existing);
    } else {
      this.assets.set(asset.id, asset);
    }
    this.saveRegistry();
  }

  /**
   * ★ Round 10: 查找相似资产
   *
   * @param instruction 任务指令
   * @param params 执行参数
   * @param minSimilarity 最小相似度阈值
   * @returns 相似资产列表（按相似度降序）
   */
  findSimilarAsset(
    instruction: string,
    params: Record<string, any> = {},
    minSimilarity: number = 0.3
  ): { asset: OperationAsset; similarity: number } | null {
    const taskType = classifyOperation(instruction);
    const appType = params.appName;
    const webTarget = this.extractWebTarget(params.url || instruction);
    const sig = this.computeSignature([{ instruction, goal_description: '', executor: ExecutorType.CLAUDE_CODE }]);

    const candidates: { asset: OperationAsset; similarity: number }[] = [];

    for (const asset of this.assets.values()) {
      // 类型必须匹配
      if (asset.task_type !== taskType) continue;

      let similarity = 0;
      let factors = 0;

      // 1. 指令相似度
      const instructionSim = this.computeInstructionSimilarity(
        this.normalizeInstruction(instruction),
        asset.instruction_pattern
      );
      similarity += instructionSim * 0.5;
      factors++;

      // 2. 目标相似度
      if (asset.web_target && webTarget) {
        const targetSim = asset.web_target === webTarget ? 1.0 :
          (asset.web_target.includes(webTarget) || webTarget.includes(asset.web_target)) ? 0.8 : 0;
        similarity += targetSim * 0.3;
        factors++;
      }

      // 3. App type 匹配
      if (asset.app_type && appType) {
        const appSim = asset.app_type === appType ? 1.0 :
          (asset.app_type.includes(appType) || appType.includes(asset.app_type)) ? 0.7 : 0;
        similarity += appSim * 0.2;
        factors++;
      }

      if (factors > 0) similarity /= factors;

      if (similarity >= minSimilarity) {
        candidates.push({ asset, similarity });
      }
    }

    candidates.sort((a, b) => b.similarity - a.similarity);
    return candidates.length > 0 ? candidates[0] : null;
  }

  /**
   * ★ Round 10: 命中资产后复用操作链
   *
   * @param asset 要复用的资产
   * @param currentInstruction 当前指令
   * @returns 复用决策
   */
  reuseAsset(
    asset: OperationAsset,
    currentInstruction: string
  ): {
    recommended: boolean;
    reuse_steps: Array<{ instruction: string; goal_description: string; executor: ExecutorType }>;
    shortcut_applied: boolean;
    reason: string;
  } {
    // 高置信度资产（使用次数 >= 3，成功率 >= 0.7）可以直接复用
    const highConfidence = asset.metadata.use_count >= 3 && asset.metadata.success_rate >= 0.7;

    if (highConfidence) {
      // 更新使用统计
      asset.metadata.use_count++;
      asset.metadata.last_used_at = new Date().toISOString();
      this.saveRegistry();

      return {
        recommended: true,
        reuse_steps: asset.steps,
        shortcut_applied: true,
        reason: `High-confidence asset (uses=${asset.metadata.use_count}, rate=${(asset.metadata.success_rate * 100).toFixed(0)}%)`,
      };
    }

    // 中等置信度：复用步骤但需要验证
    if (asset.metadata.use_count >= 1) {
      asset.metadata.use_count++;
      asset.metadata.last_used_at = new Date().toISOString();
      this.saveRegistry();

      return {
        recommended: true,
        reuse_steps: asset.steps,
        shortcut_applied: false,
        reason: `Medium-confidence reuse (uses=${asset.metadata.use_count}, rate=${(asset.metadata.success_rate * 100).toFixed(0)}%)`,
      };
    }

    return {
      recommended: false,
      reuse_steps: [],
      shortcut_applied: false,
      reason: 'Asset confidence too low, will execute from scratch',
    };
  }

  /**
   * ★ Round 10: 标记资产执行结果（用于更新成功率）
   */
  recordAssetOutcome(assetId: string, success: boolean): void {
    const asset = this.assets.get(assetId);
    if (!asset) return;

    asset.metadata.use_count++;
    if (success) {
      asset.metadata.success_count++;
    }
    asset.metadata.success_rate = asset.metadata.success_count / asset.metadata.use_count;
    this.saveRegistry();
  }

  /**
   * ★ Round 10: 获取所有资产（用于调试）
   */
  getAllAssets(): OperationAsset[] {
    return Array.from(this.assets.values());
  }

  // ---- private helpers ----

  private generateAssetName(instruction: string, taskType: OperationType): string {
    const keyword = instruction.split(' ').slice(0, 3).join('_').replace(/[^\w]/g, '').slice(0, 30);
    return `${taskType}_${keyword}_${Date.now().toString(36)}`;
  }

  private computeSignature(steps: Array<{ instruction: string; goal_description?: string; executor: ExecutorType }>): string {
    const normalized = steps.map(s => `${s.executor}:${this.normalizeInstruction(s.instruction)}`).join('|');
    let hash = 0;
    for (let i = 0; i < normalized.length; i++) {
      hash = ((hash << 5) - hash) + normalized.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash).toString(36);
  }

  private normalizeInstruction(instruction: string): string {
    // 归一化指令：移除具体值，保留模式
    return instruction
      .toLowerCase()
      .replace(/https?:\/\/[^\s]+/g, '<URL>')
      .replace(/\b\d+\b/g, '<N>')
      .replace(/[^\w\s<>]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 100);
  }

  private computeInstructionSimilarity(a: string, b: string): number {
    if (a === b) return 1.0;
    if (a.includes(b) || b.includes(a)) return 0.8;

    // 简单的 token 重叠率
    const tokensA = new Set(a.split(/\s+/));
    const tokensB = new Set(b.split(/\s+/));
    const intersection = [...tokensA].filter(t => tokensB.has(t)).length;
    const union = new Set([...tokensA, ...tokensB]).size;

    return union > 0 ? intersection / union : 0;
  }

  private extractWebTarget(urlOrInstruction: string): string | undefined {
    try {
      const match = urlOrInstruction.match(/https?:\/\/([^\/]+)/);
      return match ? match[1] : undefined;
    } catch {
      return undefined;
    }
  }

  private inferEnvironmentTags(params: Record<string, any>): string[] {
    const tags: string[] = [];
    if (params.appName) tags.push(`app:${params.appName}`);
    if (params.url) {
      try {
        const hostname = new URL(params.url).hostname;
        tags.push(`web:${hostname}`);
      } catch { /* ignore */ }
    }
    tags.push(`os:${os.platform()}`);
    return tags;
  }
}

// ============================================
// ★ Round 10: 超人效率引擎
// ============================================

/**
 * 超人效率引擎
 * 负责：
 * 1. 批量任务执行
 * 2. 并行可行性判断
 * 3. 重复操作压缩
 * 4. 快速成功路径（shortcut）
 * 5. 效率指标输出
 */
export class SuperhumanEfficiencyEngine {
  private assetRegistry: OperationAssetRegistry;
  private learner: StrategyLearner;

  constructor(assetRegistry?: OperationAssetRegistry, learner?: StrategyLearner) {
    this.assetRegistry = assetRegistry || new OperationAssetRegistry();
    this.learner = learner || new StrategyLearner();
  }

  /**
   * ★ Round 10: 判断任务是否可并行
   *
   * 简单规则：
   * - 不同 URL 的网页操作 → 可并行
   * - 不同 app 的桌面操作 → 可并行
   * - 相同 URL 的操作 → 必须串行
   * - 涉及共享状态（如全局快捷键）的操作 → 必须串行
   */
  assessParallelizability(
    tasks: Array<{ instruction: string; params: Record<string, any> }>
  ): {
    parallelizable: boolean;
    segments: Array<{ tasks: number[]; reason: string }>;
    total_savings_ms: number;
  } {
    if (tasks.length <= 1) {
      return { parallelizable: false, segments: [], total_savings_ms: 0 };
    }

    const segments: Array<{ tasks: number[]; reason: string }> = [];
    let currentGroup: number[] = [];
    let lastType = '';
    let lastTarget = '';

    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i];
      const taskType = classifyOperation(task.instruction);
      const target = task.params.url || task.params.appName || '';

      // 确定当前任务的"域"
      const domain = taskType === OperationType.WEB_BROWSER
        ? `web:${target}`
        : taskType === OperationType.DESKTOP_APP
          ? `app:${target}`
          : `code:${i}`; // 每次代码执行都是独立的

      if (domain !== lastTarget || currentGroup.length === 0) {
        // 新域
        if (currentGroup.length > 0) {
          // 保存当前组
          segments.push({
            tasks: [...currentGroup],
            reason: `Same ${lastType} targeting ${lastTarget} (must be serial)`,
          });
        }
        currentGroup = [i];
        lastType = taskType;
        lastTarget = domain;
      } else {
        // 同域，加入当前组
        currentGroup.push(i);
      }
    }

    // 保存最后一组
    if (currentGroup.length > 0) {
      segments.push({
        tasks: [...currentGroup],
        reason: `Same ${lastType} targeting ${lastTarget} (must be serial)`,
      });
    }

    // 计算并行收益：完全可并行的段可以节省 (n-1)*avg_time
    // 简化：假设每步操作平均 2 秒，并行节省 50%
    const serialGroups = segments.filter(s => s.tasks.length === 1);
    const parallelSavings = segments
      .filter(s => s.tasks.length > 1)
      .reduce((acc, seg) => acc + (seg.tasks.length - 1) * 2000 * 0.5, 0);

    return {
      parallelizable: segments.some(s => s.tasks.length > 1),
      segments,
      total_savings_ms: Math.round(parallelSavings),
    };
  }

  /**
   * ★ Round 10: 检查是否命中高置信资产（shortcut 路径）
   */
  checkShortcutOpportunity(
    instruction: string,
    params: Record<string, any>
  ): {
    shortcut_available: boolean;
    asset_id?: string;
    similarity?: number;
    reuse_reason?: string;
  } {
    const hit = this.assetRegistry.findSimilarAsset(instruction, params, 0.3);

    if (!hit) return { shortcut_available: false };

    const { asset, similarity } = hit;

    // 高置信度：使用次数 >= 3 且成功率 >= 0.7
    const highConfidence = asset.metadata.use_count >= 3 && asset.metadata.success_rate >= 0.7;

    if (highConfidence || similarity >= 0.85) {
      return {
        shortcut_available: true,
        asset_id: asset.id,
        similarity,
        reuse_reason: `Shortcut: ${asset.metadata.success_count}/${asset.metadata.use_count} successes, similarity=${(similarity * 100).toFixed(0)}%`,
      };
    }

    return { shortcut_available: false };
  }

  /**
   * ★ Round 10: 压缩重复操作
   *
   * 识别并合并连续重复的准备/验证步骤
   */
  compressRepeatedOperations(
    steps: Array<{ instruction: string; goal_description: string; params: Record<string, any> }>
  ): {
    compressed_steps: Array<{ instruction: string; goal_description: string; params: Record<string, any> }>;
    compression_ratio: number;
    compressed_count: number;
  } {
    if (steps.length <= 1) {
      return {
        compressed_steps: [...steps],
        compression_ratio: 0,
        compressed_count: 0,
      };
    }

    const compressed: typeof steps = [];
    let skipped = 0;

    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      const prev = i > 0 ? steps[i - 1] : null;

      // 检查是否与上一步完全重复（相同指令 + 相同目标）
      if (prev &&
          this.normalizeForCompression(step.instruction) === this.normalizeForCompression(prev.instruction) &&
          this.normalizeForCompression(step.goal_description) === this.normalizeForCompression(prev.goal_description)) {
        skipped++;
        continue; // 跳过重复步骤
      }

      // 检查是否是重复的准备步骤（如连续多次 readiness 检查）
      if (prev && this.isReadinessCheck(step.instruction) && this.isReadinessCheck(prev.instruction)) {
        skipped++;
        continue;
      }

      compressed.push(step);
    }

    return {
      compressed_steps: compressed,
      compression_ratio: steps.length > 0 ? skipped / steps.length : 0,
      compressed_count: skipped,
    };
  }

  /**
   * ★ Round 10: 执行带效率优化的链
   */
  async executeOptimizedChain(
    taskId: string,
    steps: Array<{ instruction: string; goal_description: string; params: Record<string, any> }>,
    executeFn: (step: { instruction: string; params: Record<string, any> }) => Promise<any>
  ): Promise<{
    results: any[];
    final_context: any;
    superhuman_metrics: SuperhumanMetrics;
  }> {
    const startTime = Date.now();

    // Step 1: 压缩重复操作
    const { compressed_steps, compression_ratio, compressed_count } = this.compressRepeatedOperations(steps);

    // Step 2: 检查 shortcut
    const shortcutOpportunity = compressed_steps.length > 0
      ? this.checkShortcutOpportunity(compressed_steps[0].instruction, compressed_steps[0].params)
      : { shortcut_available: false };

    // Step 3: 检查并行可行性
    const parallelAssessment = this.assessParallelizability(compressed_steps);

    // Step 4: 执行
    const results: any[] = [];
    let ctx: any = {};

    if (shortcutOpportunity.shortcut_available) {
      // Shortcut: 直接复用资产步骤
      const asset = this.assetRegistry.getAllAssets().find(a => a.id === shortcutOpportunity.asset_id);
      if (asset) {
        for (const assetStep of asset.steps) {
          const result = await executeFn({
            instruction: assetStep.instruction,
            params: { ...compressed_steps[0].params },
          });
          results.push(result);
        }
        this.assetRegistry.recordAssetOutcome(asset.id, true);
      }
    } else {
      // 正常执行压缩后的步骤
      for (const step of compressed_steps) {
        const result = await executeFn(step);
        results.push(result);
        ctx = { ...ctx, ...(result.accumulated_context || {}) };
      }
    }

    const elapsed = Date.now() - startTime;
    const reusedSteps = shortcutOpportunity.shortcut_available
      ? compressed_steps.length
      : compressed_count;

    const metrics: SuperhumanMetrics = {
      time_saved_estimate_ms: Math.round(
        (compression_ratio * elapsed) +
        (parallelAssessment.total_savings_ms) +
        (shortcutOpportunity.shortcut_available ? elapsed * 0.5 : 0)
      ),
      reused_steps: reusedSteps,
      shortcut_used: shortcutOpportunity.shortcut_available,
      shortcut_reason: shortcutOpportunity.shortcut_available ? shortcutOpportunity.reuse_reason : undefined,
      parallelizable_segments: parallelAssessment.segments
        .filter(s => s.tasks.length > 1)
        .map(s => `${s.tasks.length} tasks: ${s.reason}`),
      batch_size: steps.length,
      compression_ratio: compression_ratio,
      efficiency_gain: Math.min(1, (compression_ratio * 0.3 + (shortcutOpportunity.shortcut_available ? 0.4 : 0) + (parallelAssessment.parallelizable ? 0.3 : 0))),
    };

    return { results, final_context: ctx, superhuman_metrics: metrics };
  }

  private normalizeForCompression(s: string): string {
    return s.toLowerCase().replace(/\s+/g, ' ').trim();
  }

  private isReadinessCheck(instruction: string): boolean {
    const readinessPatterns = [
      'check', 'verify', 'ready', 'status', 'health',
      'ping', 'echo', 'probe', 'observe desktop', 'check window',
    ];
    const lower = instruction.toLowerCase();
    return readinessPatterns.some(p => lower.includes(p));
  }
}

// ============================================
// 单例
// ============================================

export const strategyLearner = new StrategyLearner();
export const operationAssetRegistry = new OperationAssetRegistry();
export const superhumanEngine = new SuperhumanEfficiencyEngine(operationAssetRegistry, strategyLearner);
