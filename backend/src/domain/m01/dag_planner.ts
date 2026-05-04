/**
 * M01 DAG 规划器
 * ================================================
 * 多步骤任务分解为有向无环图
 * ================================================
 */

import {
  DAGNode,
  DAGPlan,
  OrchestrationRequest,
  DAGNodeStatus,
  DEFAULT_M01_CONFIG,
} from './types';

import { SystemType } from '../m04/types';

// ============================================
// 任务分解关键词
// ============================================

const TASK_SEPARATORS = [
  { pattern: /首先/g, next: '第一步' },
  { pattern: /然后|接着|之后/g, next: '下一步' },
  { pattern: /最后/g, next: '最终' },
  { pattern: /第一步|第二|第三/g, next: '步骤' },
];

// ★ R122: 扩展 systemType 推断关键词，修复 VISUAL_WEB/DESKTOP_APP/CLAUDE_CODE 不可达问题
// 优先级：从具体到宽泛，具体类别先于 task 默认值
const SYSTEM_TYPE_KEYWORDS: Record<string, string[]> = {
  // 1. 视觉网页自动化（最具体，优先检查）
  visual_web: [
    // URL / 域名模式（优先，避免被 desktop_app 截流）
    '.com', '.cn', '.org', '.net', '.io', '.dev', '.app',
    // 导航/打开
    '打开网站', '打开网页', '浏览网页', '访问网页', '进入网页',
    'go to', 'navigate', 'open url', 'visit',
    // 浏览器操作
    '点击', '点击链接', '网页点击', '浏览器点击',
    '填写', '输入框', '登录网站',
    // 网页相关实体
    '网页', '网站', '页面',
    // URL 前缀
    'http://', 'https://',
  ],
  // 2. 桌面应用控制
  desktop_app: [
    // 明确应用名（精确优先，不含 '用' 等泛化操作）
    'gimp', 'photoshop', 'excel', 'word', 'vscode', 'terminal', '终端',
    'blender', 'audacity', 'inkscape', 'libreoffice', 'zotero', 'imagemagick',
    // 操作指示
    '修图', '编辑图', '处理图', '画图',
    '用一下', '打开应用', '桌面软件', '本地软件',
    '启动', '运行',
  ],
  // 3. Claude Code 代码任务
  claude_code: [
    // 代码动作（优先检查，避免被 desktop_app 的 '用 ' 截流）
    '用 typescript', '用 python', '用 javascript', '用 java',
    '写代码', '写 python', '写 javascript', '写 typescript', '写代码',
    '编写', '编写代码', '写程序', '编程',
    '改代码', '修代码', '重构', '重构代码', 'debug',
    '实现', '实现一个', '写一个函数', '写一个脚本',
    // 代码相关实体
    'typescript', 'javascript', 'python', 'java', 'rust', 'go ', 'c++',
    'function', 'class ', 'script', '模块', 'api', '脚本',
    'git commit', 'git push', 'clone', 'repository', '代码', 'bug',
  ],
  // 4. 搜索
  search: ['搜索', '查找', '查询', '研究', '分析'],
  // 5. 工作流
  workflow: ['流程', '多步', '自动化', '编排'],
  // 6. task 作为默认 fallback
  task: ['执行', '完成', '实现', '构建', '创建', '修复'],
};

// ============================================
// DAG 规划器
// ============================================

export class DAGPlanner {
  private config: typeof DEFAULT_M01_CONFIG;

  constructor(config: Partial<typeof DEFAULT_M01_CONFIG> = {}) {
    this.config = { ...DEFAULT_M01_CONFIG, ...config };
  }

  /**
   * 从编排请求构建DAG计划
   */
  buildPlan(request: OrchestrationRequest): DAGPlan {
    const nodes = this.decomposeTask(request);
    const executionOrder = this.topologicalSort(nodes);

    const plan: DAGPlan = {
      id: `dag_${request.requestId}_${Date.now()}`,
      rootTask: request.userInput,
      nodes,
      executionOrder,
      estimatedDuration: this.estimateDuration(nodes),
      createdAt: new Date().toISOString(),
    };

    return plan;
  }

  /**
   * 分解任务为DAG节点
   */
  private decomposeTask(request: OrchestrationRequest): DAGNode[] {
    const nodes: DAGNode[] = [];
    const input = request.userInput;

    // 简单任务 - 单节点
    if (input.length < 50 && !this.containsMultipleSteps(input)) {
      nodes.push(this.createNode({
        id: 'task-1',
        task: input,
        systemType: this.inferSystemType(input),
        dependencies: [],
        timeout: this.config.defaultTimeout,
        expectedOutput: '任务完成',
      }));
      return nodes;
    }

    // 多步骤任务 - 分解
    const steps = this.splitIntoSteps(input);
    const stepNodes = this.createStepNodes(steps, request);

    // 添加搜索节点（如果需要）
    if (request.intentProfile?.task_category === 'search' || this.needsSearch(input)) {
      const searchNode = this.createNode({
        id: 'search-1',
        task: `搜索: ${this.extractSearchQuery(input)}`,
        systemType: 'search' as SystemType,
        dependencies: [],
        timeout: 60000,
        expectedOutput: '搜索结果',
      });
      nodes.push(searchNode);

      // 搜索节点作为第一个任务的前置
      for (const stepNode of stepNodes) {
        if (stepNode.dependencies.length === 0) {
          stepNode.dependencies.push(searchNode.id);
        }
      }
    }

    nodes.push(...stepNodes);

    return nodes;
  }

  /**
   * 分割为步骤
   */
  private splitIntoSteps(input: string): string[] {
    const steps: string[] = [];

    // 按常见分隔符分割
    let current = input;

    // 移除"首先"、"然后"等前缀
    for (const { pattern, next } of TASK_SEPARATORS) {
      current = current.replace(pattern, next);
    }

    // 按标点和步骤关键词分割
    const separators = /[。\n；；然后接着最后]|(?<=\d)。(?=\D)|(?<=[吗呢吧])\s*(?=\d|首先|然后)/;
    const parts = current.split(separators).filter(p => p.trim().length > 0);

    // 进一步分解
    for (const part of parts) {
      const subSteps = part.split(/(?<=[，,])\s*(?=\S)/).filter(s => s.trim().length > 0);
      steps.push(...subSteps);
    }

    // 如果没有分出步骤，把整个输入作为一个步骤
    if (steps.length === 0) {
      steps.push(input);
    }

    return steps;
  }

  /**
   * 检查是否包含多步骤
   */
  private containsMultipleSteps(input: string): boolean {
    for (const indicator of ['首先', '然后', '接着', '最后', '第一步', '第二', '第三']) {
      if (input.includes(indicator)) {
        return true;
      }
    }
    return false;
  }

  /**
   * 从步骤创建节点
   */
  private createStepNodes(steps: string[], request: OrchestrationRequest): DAGNode[] {
    const nodes: DAGNode[] = [];

    for (let i = 0; i < steps.length; i++) {
      const step = steps[i].trim();
      if (!step) continue;

      const systemType = this.inferSystemType(step);
      const dependencies: string[] = [];

      // 第一个任务依赖搜索（如果存在）
      if (i === 0 && request.intentProfile?.task_category === 'search') {
        dependencies.push('search-1');
      }

      // 后续任务依赖前一个
      if (i > 0) {
        dependencies.push(`task-${i}`);
      }

      nodes.push(this.createNode({
        id: `task-${i + 1}`,
        task: step,
        systemType,
        dependencies,
        timeout: this.estimateStepTimeout(step),
        expectedOutput: `步骤${i + 1}完成`,
      }));
    }

    return nodes;
  }

  /**
   * 推断系统类型
   */
  private inferSystemType(task: string): SystemType {
    const normalizedTask = task.toLowerCase();

    for (const [type, keywords] of Object.entries(SYSTEM_TYPE_KEYWORDS)) {
      for (const keyword of keywords) {
        if (normalizedTask.includes(keyword)) {
          return type as SystemType;
        }
      }
    }

    return 'task' as SystemType;
  }

  /**
   * 检查是否需要搜索
   */
  private needsSearch(input: string): boolean {
    const normalizedInput = input.toLowerCase();
    const searchKeywords = ['搜索', '查找', '查询', '了解', '研究', '分析', 'search', 'find'];
    return searchKeywords.some(k => normalizedInput.includes(k));
  }

  /**
   * 提取搜索查询
   */
  private extractSearchQuery(input: string): string {
    // 移除搜索相关的动词，保留核心查询
    let query = input
      .replace(/搜索|查找|查询|了解一下|研究一下|分析一下/gi, '')
      .trim();
    return query || input;
  }

  /**
   * 创建节点
   */
  private createNode(partial: Partial<DAGNode> & { id: string; task: string; systemType: SystemType }): DAGNode {
    return {
      id: partial.id,
      task: partial.task,
      systemType: partial.systemType,
      dependencies: partial.dependencies || [],
      timeout: partial.timeout || this.config.defaultTimeout,
      expectedOutput: partial.expectedOutput || '完成',
      priority: partial.priority || 'normal',
      status: DAGNodeStatus.PENDING,
      result: undefined,
      error: undefined,
    };
  }

  /**
   * 估算步骤超时
   */
  private estimateStepTimeout(step: string): number {
    let timeout = 60000; // 默认1分钟

    if (step.length > 100) timeout += 30000;
    if (step.includes('搜索')) timeout += 30000;
    if (step.includes('执行') || step.includes('运行')) timeout += 60000;

    return Math.min(timeout, this.config.defaultTimeout);
  }

  /**
   * 拓扑排序 - 确定执行顺序
   */
  topologicalSort(nodes: DAGNode[]): string[] {
    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    const inDegree = new Map<string, number>();
    const result: string[] = [];

    // 初始化入度
    for (const node of nodes) {
      inDegree.set(node.id, 0);
    }

    // 计算入度
    for (const node of nodes) {
      for (const depId of node.dependencies) {
        if (nodeMap.has(depId)) {
          inDegree.set(node.id, (inDegree.get(node.id) || 0) + 1);
        }
      }
    }

    // BFS
    const queue: string[] = [];
    for (const [id, degree] of inDegree.entries()) {
      if (degree === 0) {
        queue.push(id);
      }
    }

    while (queue.length > 0) {
      const current = queue.shift()!;
      result.push(current);

      const node = nodeMap.get(current);
      if (!node) continue;

      for (const neighbor of nodes) {
        if (neighbor.dependencies.includes(current)) {
          const newDegree = (inDegree.get(neighbor.id) || 0) - 1;
          inDegree.set(neighbor.id, newDegree);
          if (newDegree === 0) {
            queue.push(neighbor.id);
          }
        }
      }
    }

    // 检查循环依赖
    if (result.length !== nodes.length) {
      console.warn('[DAGPlanner] Circular dependency detected, using fallback order');
      return nodes.map(n => n.id);
    }

    return result;
  }

  /**
   * 估算总耗时
   */
  estimateDuration(nodes: DAGNode[]): number {
    return nodes.reduce((sum, node) => sum + node.timeout, 0);
  }

  /**
   * 验证DAG是否有循环
   */
  validateNoCycle(nodes: DAGNode[]): boolean {
    const visited = new Set<string>();
    const recursionStack = new Set<string>();

    const hasCycle = (nodeId: string): boolean => {
      visited.add(nodeId);
      recursionStack.add(nodeId);

      const node = nodes.find(n => n.id === nodeId);
      if (node) {
        for (const depId of node.dependencies) {
          if (!visited.has(depId)) {
            if (hasCycle(depId)) return true;
          } else if (recursionStack.has(depId)) {
            return true;
          }
        }
      }

      recursionStack.delete(nodeId);
      return false;
    };

    for (const node of nodes) {
      if (!visited.has(node.id)) {
        if (hasCycle(node.id)) {
          return false;
        }
      }
    }

    return true;
  }
}

// ============================================
// 单例导出
// ============================================

export const dagPlanner = new DAGPlanner();
