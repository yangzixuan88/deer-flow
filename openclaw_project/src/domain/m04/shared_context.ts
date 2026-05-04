/**
 * M04 共享上下文实现
 * ================================================
 * 跨系统数据共享 · TTL管理 · 原子更新
 * 三系统协同的共享状态中心
 * ================================================
 */

import {
  SharedContextData,
  CrossSystemData,
  SearchResponse,
  TaskResult,
  WorkflowExecution,
} from './types';

// ============================================
// 共享上下文
// ============================================

/**
 * 共享上下文管理器
 *
 * 核心职责：
 * - 存储跨系统共享数据
 * - TTL自动过期
 * - 原子更新操作
 * - 跨Agent通信
 */
export class SharedContext {
  private store: Map<string, SharedContextData>;
  private locks: Map<string, Promise<void>>;

  constructor() {
    this.store = new Map();
    this.locks = new Map();
  }

  /**
   * 设置共享数据
   */
  set(key: string, value: any, ttl_ms: number = 300000): void {
    const data: SharedContextData = {
      key,
      value,
      ttl_ms,
      created_at: new Date().toISOString(),
      access_count: 0,
    };

    this.store.set(key, data);
  }

  /**
   * 获取共享数据
   */
  get(key: string): any | null {
    const data = this.store.get(key);

    if (!data) return null;

    // 检查TTL
    const age = Date.now() - new Date(data.created_at).getTime();
    if (age > data.ttl_ms) {
      this.store.delete(key);
      return null;
    }

    // 更新访问计数
    data.access_count++;
    return data.value;
  }

  /**
   * 删除共享数据
   */
  delete(key: string): boolean {
    return this.store.delete(key);
  }

  /**
   * 更新共享数据（原子操作）
   */
  async update(key: string, updater: (current: any) => any): Promise<boolean> {
    // 简单实现：实际生产环境应使用分布式锁
    const current = this.get(key);
    const updated = updater(current);

    if (updated === null) {
      return false;
    }

    const data = this.store.get(key);
    if (data) {
      data.value = updated;
      data.access_count++;
      return true;
    }

    return false;
  }

  /**
   * 批量设置
   */
  setMany(data: Record<string, any>, ttl_ms: number = 300000): void {
    for (const [key, value] of Object.entries(data)) {
      this.set(key, value, ttl_ms);
    }
  }

  /**
   * 获取所有键
   */
  keys(): string[] {
    this.cleanup();
    return Array.from(this.store.keys());
  }

  /**
   * 获取统计信息
   */
  getStats(): {
    totalKeys: number;
    avgAccessCount: number;
    oldestEntry: string | null;
  } {
    this.cleanup();

    const entries = Array.from(this.store.values());
    let totalAccess = 0;
    let oldest: SharedContextData | null = null;

    for (const entry of entries) {
      totalAccess += entry.access_count;
      if (!oldest || new Date(entry.created_at) < new Date(oldest.created_at)) {
        oldest = entry;
      }
    }

    return {
      totalKeys: entries.length,
      avgAccessCount: entries.length > 0 ? totalAccess / entries.length : 0,
      oldestEntry: oldest?.key || null,
    };
  }

  /**
   * 清理过期数据
   */
  cleanup(): number {
    let removed = 0;
    const now = Date.now();

    for (const [key, data] of this.store.entries()) {
      const age = now - new Date(data.created_at).getTime();
      if (age > data.ttl_ms) {
        this.store.delete(key);
        removed++;
      }
    }

    return removed;
  }

  /**
   * 清空所有数据
   */
  clear(): void {
    this.store.clear();
  }
}

// ============================================
// 跨系统数据聚合器
// ============================================

/**
 * 跨系统数据聚合器
 *
 * 负责聚合三个系统的输出数据，
 * 形成统一的跨系统视图
 */
export class CrossSystemAggregator {
  private searchResults: SearchResponse | null = null;
  private taskResult: TaskResult | null = null;
  private workflowResult: WorkflowExecution | null = null;
  private sharedContext: SharedContext;

  constructor(sharedContext: SharedContext) {
    this.sharedContext = sharedContext;
  }

  /**
   * 设置搜索结果
   */
  setSearchResult(result: SearchResponse): void {
    this.searchResults = result;
    this.sharedContext.set('last_search_result', result, 600000); // 10分钟
  }

  /**
   * 设置任务结果
   */
  setTaskResult(result: TaskResult): void {
    this.taskResult = result;
    this.sharedContext.set('last_task_result', result, 600000);
  }

  /**
   * 设置工作流结果
   */
  setWorkflowResult(result: WorkflowExecution): void {
    this.workflowResult = result;
    this.sharedContext.set('last_workflow_result', result, 600000);
  }

  /**
   * 获取搜索结果
   */
  getSearchResult(): SearchResponse | null {
    return this.searchResults;
  }

  /**
   * 获取任务结果
   */
  getTaskResult(): TaskResult | null {
    return this.taskResult;
  }

  /**
   * 获取工作流结果
   */
  getWorkflowResult(): WorkflowExecution | null {
    return this.workflowResult;
  }

  /**
   * 获取完整跨系统数据
   */
  getCrossSystemData(): CrossSystemData {
    return {
      search_results: this.searchResults || undefined,
      task_result: this.taskResult || undefined,
      workflow_result: this.workflowResult || undefined,
      shared_state: Object.fromEntries(
        this.sharedContext.keys().map(key => [key, this.sharedContext.get(key)])
      ) as Record<string, SharedContextData>,
    };
  }

  /**
   * 获取汇总信息
   */
  getSummary(): {
    searchConfidence: number;
    taskStatus: string;
    workflowStatus: string;
    totalTokens: number;
  } {
    return {
      searchConfidence: this.searchResults?.cross_validation.confidence || 0,
      taskStatus: this.taskResult?.status || 'none',
      workflowStatus: this.workflowResult?.status || 'none',
      totalTokens: (this.searchResults?.results.length || 0) +
                  (this.taskResult?.tokens_used || 0),
    };
  }

  /**
   * 清空所有数据
   */
  clear(): void {
    this.searchResults = null;
    this.taskResult = null;
    this.workflowResult = null;
  }
}

// ============================================
// 单例导出
// ============================================

export const sharedContext = new SharedContext();
export const crossSystemAggregator = new CrossSystemAggregator(sharedContext);
