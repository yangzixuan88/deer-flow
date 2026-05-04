/**
 * M04 任务系统适配器
 * ================================================
 * DAG分解 · 节点执行 · Checkpoint恢复
 * ================================================
 */

import {
  Task,
  TaskDAG,
  TaskNode,
  TaskStatus,
  NodeStatus,
  TaskCategory,
  TaskResult,
} from '../types';

import * as crypto from 'crypto';

// ============================================
// 任务系统适配器
// ============================================

/**
 * 任务系统适配器
 *
 * 封装任务系统的核心能力：
 * - DAG自动分解
 * - 节点执行与熔断
 * - Checkpoint恢复
 * - 经验包生成
 */
export class TaskAdapter {
  private taskStore: Map<string, Task>;

  constructor() {
    this.taskStore = new Map();
  }

  /**
   * 创建并执行任务
   */
  async execute(goal: string, priority: 'high' | 'normal' | 'low' = 'normal'): Promise<TaskResult> {
    const taskId = `task_${Date.now()}_${crypto.randomUUID().replace(/-/g, '').substring(0, 9)}`;
    const startTime = Date.now();

    // 生成DAG
    const dag = this.decomposeDAG(goal);

    // 创建任务
    const task: Task = {
      task_id: taskId,
      goal,
      status: TaskStatus.PENDING,
      created_at: new Date().toISOString(),
      dag,
      total_tokens: 0,
      checkpoints: [],
    };

    this.taskStore.set(taskId, task);

    // 执行DAG
    await this.executeDAG(task);

    // 生成结果
    const result: TaskResult = {
      task_id: taskId,
      status: task.status,
      result: this.generateTaskSummary(task),
      tokens_used: task.total_tokens,
      execution_time_ms: Date.now() - startTime,
      nodes_executed: task.dag.nodes.filter(n => n.status === NodeStatus.COMPLETED).length,
    };

    // 生成经验包ID
    if (task.status === TaskStatus.COMPLETED) {
      result.experience_id = `exp_${taskId}`;
    }

    return result;
  }

  /**
   * DAG分解
   */
  decomposeDAG(goal: string): TaskDAG {
    const nodes: TaskNode[] = [];
    const edges: [string, string][] = [];

    // 分析目标类型
    const categories = this.detectCategories(goal);

    // 根节点
    const rootId = 'n_root';
    nodes.push({
      id: rootId,
      name: goal,
      category: TaskCategory.PLANNING,
      status: NodeStatus.PENDING,
      depends_on: [],
      timeout_min: 10,
      retry_count: 0,
    });

    // 根据检测到的类别添加节点
    let prevNodeId = rootId;

    for (const category of categories) {
      const nodeId = `n_${category}_${nodes.length}`;

      const node: TaskNode = {
        id: nodeId,
        name: this.getCategoryName(category),
        category,
        status: NodeStatus.PENDING,
        depends_on: category === TaskCategory.SEARCH ? [rootId] : [prevNodeId],
        timeout_min: this.getCategoryTimeout(category),
        retry_count: 0,
      };

      nodes.push(node);
      edges.push(...node.depends_on.map(dep => [dep, nodeId] as [string, string]));

      prevNodeId = nodeId;
    }

    return { nodes, edges };
  }

  /**
   * 检测目标类别
   */
  private detectCategories(goal: string): TaskCategory[] {
    const categories: TaskCategory[] = [];
    const lowerGoal = goal.toLowerCase();

    if (/搜索|调研|查找|调查/.test(lowerGoal)) {
      categories.push(TaskCategory.SEARCH);
    }

    if (/分析|对比|评估/.test(lowerGoal)) {
      categories.push(TaskCategory.ANALYSIS);
    }

    if (/代码|实现|开发|编程/.test(lowerGoal)) {
      categories.push(TaskCategory.CODE_GEN);
    }

    if (/计划|规划|设计|方案/.test(lowerGoal)) {
      categories.push(TaskCategory.PLANNING);
    }

    if (/创意|创作|生成/.test(lowerGoal)) {
      categories.push(TaskCategory.CREATIVE);
    }

    if (/配置|安装|部署|系统/.test(lowerGoal)) {
      categories.push(TaskCategory.SYS_CONFIG);
    }

    if (/数据|处理|转换|清洗/.test(lowerGoal)) {
      categories.push(TaskCategory.DATA_PROCESSING);
    }

    if (/决策|选择|判断/.test(lowerGoal)) {
      categories.push(TaskCategory.DECISION);
    }

    // 默认至少有一个
    if (categories.length === 0) {
      categories.push(TaskCategory.RESEARCH);
    }

    return categories;
  }

  /**
   * 获取类别名称
   */
  private getCategoryName(category: TaskCategory): string {
    const names: Record<TaskCategory, string> = {
      [TaskCategory.SEARCH]: '搜索与信息获取',
      [TaskCategory.CODE_GEN]: '代码生成与实现',
      [TaskCategory.RESEARCH]: '研究与调研',
      [TaskCategory.ANALYSIS]: '分析与对比',
      [TaskCategory.PLANNING]: '规划与设计',
      [TaskCategory.CREATIVE]: '创意与创作',
      [TaskCategory.SYS_CONFIG]: '系统配置',
      [TaskCategory.DATA_PROCESSING]: '数据处理',
      [TaskCategory.DECISION]: '决策支持',
    };
    return names[category] || '未知任务';
  }

  /**
   * 获取类别超时时间
   */
  private getCategoryTimeout(category: TaskCategory): number {
    const timeouts: Record<TaskCategory, number> = {
      [TaskCategory.SEARCH]: 5,
      [TaskCategory.CODE_GEN]: 10,
      [TaskCategory.RESEARCH]: 8,
      [TaskCategory.ANALYSIS]: 8,
      [TaskCategory.PLANNING]: 5,
      [TaskCategory.CREATIVE]: 10,
      [TaskCategory.SYS_CONFIG]: 15,
      [TaskCategory.DATA_PROCESSING]: 10,
      [TaskCategory.DECISION]: 5,
    };
    return timeouts[category] || 10;
  }

  /**
   * 执行DAG
   */
  private async executeDAG(task: Task): Promise<void> {
    task.status = TaskStatus.IN_PROGRESS;

    // 拓扑排序
    const order = this.topologicalSort(task.dag);

    for (const nodeId of order) {
      const node = task.dag.nodes.find(n => n.id === nodeId);
      if (!node) continue;

      // 检查依赖
      const depsOk = task.dag.edges
        .filter(([_, to]) => to === nodeId)
        .every(([from]) => {
          const dep = task.dag.nodes.find(n => n.id === from);
          return dep?.status === NodeStatus.COMPLETED;
        });

      if (!depsOk) {
        node.status = NodeStatus.SKIPPED;
        continue;
      }

      // 执行节点
      node.status = NodeStatus.RUNNING;
      task.current_node_id = nodeId;

      try {
        await this.executeNode(node, task);
        node.status = NodeStatus.COMPLETED;
      } catch (error) {
        node.status = NodeStatus.FAILED;
        node.error = error instanceof Error ? error.message : 'Unknown error';

        // 熔断检查
        if (node.retry_count >= 3) {
          task.status = TaskStatus.FAILED;
          return;
        }
        node.retry_count++;
      }
    }

    task.status = TaskStatus.COMPLETED;
  }

  /**
   * 执行单个节点
   */
  private async executeNode(node: TaskNode, task: Task): Promise<void> {
    // 模拟执行
    await new Promise(resolve => setTimeout(resolve, 50));

    node.result_summary = `Completed: ${node.name}`;
    node.tokens_used = crypto.randomInt(200, 701);
    task.total_tokens += node.tokens_used || 0;
  }

  /**
   * 拓扑排序
   */
  private topologicalSort(dag: TaskDAG): string[] {
    const inDegree = new Map<string, number>();
    const adjList = new Map<string, string[]>();

    for (const node of dag.nodes) {
      inDegree.set(node.id, 0);
      adjList.set(node.id, []);
    }

    for (const [from, to] of dag.edges) {
      inDegree.set(to, (inDegree.get(to) || 0) + 1);
      adjList.get(from)?.push(to);
    }

    const queue = Array.from(inDegree.entries())
      .filter(([_, d]) => d === 0)
      .map(([id]) => id);

    const result: string[] = [];
    while (queue.length > 0) {
      const id = queue.shift()!;
      result.push(id);

      for (const neighbor of adjList.get(id) || []) {
        inDegree.set(neighbor, inDegree.get(neighbor)! - 1);
        if (inDegree.get(neighbor) === 0) {
          queue.push(neighbor);
        }
      }
    }

    return result;
  }

  /**
   * 生成任务摘要
   */
  private generateTaskSummary(task: Task): string {
    const completed = task.dag.nodes.filter(n => n.status === NodeStatus.COMPLETED).length;
    const total = task.dag.nodes.length;
    const failed = task.dag.nodes.filter(n => n.status === NodeStatus.FAILED).length;

    return `Task ${task.task_id}: ${completed}/${total} nodes completed, ${failed} failed`;
  }

  /**
   * 获取任务
   */
  getTask(taskId: string): Task | undefined {
    return this.taskStore.get(taskId);
  }

  /**
   * 列出所有任务
   */
  listTasks(): Task[] {
    return Array.from(this.taskStore.values());
  }

  /**
   * 删除任务
   */
  deleteTask(taskId: string): boolean {
    return this.taskStore.delete(taskId);
  }
}

// ============================================
// 单例导出
// ============================================

export const taskAdapter = new TaskAdapter();
