/**
 * M09 Layer1 路由层实现
 * ================================================
 * 每次 LLM 调用前触发
 * 职责：
 * 1. 任务类型识别器 - 分析当前任务路由到九大类型
 * 2. 资产检索器 - 语义检索相似度≥0.85直接复用
 * 3. 上下文组装器 - P1-P6优先级组装
 * ================================================
 */

import {
  TaskType,
  PromptPriority,
  PromptFragment,
  PromptFragmentType,
  AssembledPrompt,
  ExecutionTrace,
  TaskTypeRecognizer as ITaskTypeRecognizer,
  AssetRetriever as IAssetRetriever,
  ContextAssembler as IContextAssembler,
  PromptEngineConfig,
  DEFAULT_PROMPT_ENGINE_CONFIG,
} from './types';

// ============================================
// 任务类型识别器
// ============================================

/**
 * 从用户输入/IntentProfile 识别任务类型
 */
export class TaskTypeRecognizer implements ITaskTypeRecognizer {
  private taskTypeKeywords: Map<TaskType, string[]>;

  constructor() {
    this.taskTypeKeywords = new Map([
      [TaskType.SEARCH_SYNTH, [
        '搜索', '查找', '查询', '搜', '找', 'search', 'find', 'lookup',
        '信息', '资料', '文档', '了解', '知道', 'what is', 'how to',
        '为什么', '原因', '解释', '说明', '告诉我关于',
      ]],
      [TaskType.CODE_GEN, [
        '代码', '程序', '写代码', '生成代码', 'code', 'script', 'function',
        '实现', '开发', '编程', '编写', 'create function', 'def ', 'class ',
        'import ', 'package ', 'npm ', 'pip ', 'git',
      ]],
      [TaskType.DOC_WRITE, [
        '文档', '文章', '写作', '撰写', '写', 'doc', 'write', 'document',
        '报告', '总结', '说明', 'readme', 'markdown', '笔记', '日志',
        '起草', '编辑', '修改', '润色',
      ]],
      [TaskType.DATA_ANALYSIS, [
        '分析', '统计', '数据', '分析', 'analytics', 'data', 'statistics',
        '图表', '可视化', '表格', '计算', '汇总', '趋势', '洞察',
        '对比', '排名', '占比',
      ]],
      [TaskType.DIAGNOSIS, [
        '诊断', '排查', '解决', '修复', '错误', 'bug', '问题', 'issue',
        '故障', '排除', 'diagnose', 'fix', 'debug', 'error', 'failed',
        '不能', '无法', '失败', '不对',
      ]],
      [TaskType.PLANNING, [
        '规划', '计划', '安排', '策划', '方案', 'strategy', 'plan', 'schedule',
        '项目', '任务分解', '里程碑', '时间表', 'roadmap', 'timeline',
        '下一步', '怎么做', '如何开始',
      ]],
      [TaskType.CREATIVE, [
        '创意', '创新', '设计', '头脑风暴', '想法', 'creative', 'idea', 'design',
        '方案', '建议', '优化', '改进', '新颖', '独特',
        '如果', '想象', '假设',
      ]],
      [TaskType.SYS_CONFIG, [
        '配置', '设置', '安装', '部署', '环境', 'config', 'setup', 'install',
        '部署', '启动', '运行', '环境变量', 'nginx', 'docker', 'kubernetes',
        '服务器', '集群', '端口', '域名', 'ssl', '证书',
      ]],
      [TaskType.AAL_DECISION, [
        '决策', '决定', '判断', '选择', '评估', '风险', '决策', 'decision',
        '应该', '是否', '利弊', '权衡', '推荐', '建议', 'opinion',
        '你觉得', '你认为', '哪个好',
      ]],
    ]);
  }

  /**
   * 从用户输入识别任务类型
   * @param userInput 用户输入
   * @returns 识别到的任务类型及置信度
   */
  recognizeFromInput(userInput: string): { taskType: TaskType; confidence: number }[] {
    const normalizedInput = userInput.toLowerCase();
    const scores: { taskType: TaskType; score: number }[] = [];

    for (const [taskType, keywords] of this.taskTypeKeywords) {
      let matchCount = 0;
      for (const keyword of keywords) {
        if (normalizedInput.includes(keyword.toLowerCase())) {
          matchCount++;
        }
      }
      const confidence = Math.min(matchCount / 3, 1.0); // 3个关键词匹配为满置信度
      scores.push({ taskType, score: confidence });
    }

    // 按置信度排序
    return scores
      .filter(s => s.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map(s => ({ taskType: s.taskType, confidence: s.score }));
  }

  /**
   * 根据 IntentProfile 识别任务类型
   * @param profile IntentProfile 对象
   * @returns 任务类型
   */
  recognizeFromProfile(profile: {
    goal?: string;
    deliverable?: string;
    task_category?: string;
  }): TaskType {
    const combined = [
      profile.goal || '',
      profile.deliverable || '',
      profile.task_category || '',
    ].join(' ').toLowerCase();

    const results = this.recognizeFromInput(combined);
    return results.length > 0 ? results[0].taskType : TaskType.SEARCH_SYNTH;
  }
}

// ============================================
// 资产检索器
// ============================================

/**
 * 提示词资产检索器
 * 语义检索相似度≥0.85时直接复用历史优质提示词
 */
export class AssetRetriever implements IAssetRetriever {
  private config: PromptEngineConfig;
  private assetCache: Map<string, PromptFragment[]>;
  private readonly CACHE_MAX_PER_TYPE = 50; // PERFORMANCE: 每类资产最大数量

  constructor(config: PromptEngineConfig = DEFAULT_PROMPT_ENGINE_CONFIG) {
    this.config = config;
    this.assetCache = new Map();
  }

  /**
   * 语义检索提示词资产
   * @param query 查询文本
   * @param taskType 任务类型
   * @param limit 返回数量限制
   * @returns 检索到的资产列表（按相似度排序）
   */
  async retrieve(
    query: string,
    taskType: TaskType,
    limit: number = 5
  ): Promise<{ fragment: PromptFragment; similarity: number }[]> {
    // 实际实现应调用向量数据库或语义搜索服务
    // 这里使用简化的关键词匹配模拟
    const cached = this.assetCache.get(taskType);
    if (!cached) return [];

    const normalizedQuery = query.toLowerCase();
    const results: { fragment: PromptFragment; similarity: number }[] = [];

    for (const fragment of cached) {
      const similarity = this.calculateSimilarity(normalizedQuery, fragment.content.toLowerCase());
      if (similarity >= this.config.asset_retrieval_threshold) {
        results.push({ fragment, similarity });
      }
    }

    return results
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, limit);
  }

  /**
   * 注册资产到缓存（带LRU驱逐）
   */
  registerAsset(fragment: PromptFragment): void {
    const taskType = this.getFragmentTaskType(fragment);
    const cached = this.assetCache.get(taskType) || [];

    // PERFORMANCE: 如果超过每类最大数量，移除最旧的
    if (cached.length >= this.CACHE_MAX_PER_TYPE) {
      cached.shift(); // 移除最旧的
    }
    cached.push(fragment);
    this.assetCache.set(taskType, cached);
  }

  /**
   * 计算相似度（简化版，实际应使用向量嵌入）
   */
  private calculateSimilarity(query: string, content: string): number {
    const queryWords = new Set(query.split(/\s+/).filter(w => w.length > 2));
    const contentWords = new Set(content.split(/\s+/).filter(w => w.length > 2));

    if (queryWords.size === 0) return 0;

    let matchCount = 0;
    for (const word of queryWords) {
      if (contentWords.has(word)) {
        matchCount++;
      }
    }

    return matchCount / queryWords.size;
  }

  private getFragmentTaskType(fragment: PromptFragment): TaskType {
    // 从 fragment 中推断任务类型
    return TaskType.SEARCH_SYNTH;
  }
}

// ============================================
// P1-P6 优先级组装器
// ============================================

/**
 * P1-P6 优先级组装器
 * 按优先级顺序组装提示词上下文
 */
export class PriorityAssembler {
  private config: PromptEngineConfig;

  constructor(config: PromptEngineConfig = DEFAULT_PROMPT_ENGINE_CONFIG) {
    this.config = config;
  }

  /**
   * 按 P1-P6 优先级组装提示词
   * @param fragments 可用的片段
   * @param taskType 任务类型
   * @returns 组装后的完整 prompt
   */
  assemble(fragments: PromptFragment[], taskType: TaskType): string {
    // 按优先级排序
    const priorityOrder = [
      PromptPriority.P1_SAFETY,
      PromptPriority.P2_USER_PREFERENCE,
      PromptPriority.P3_TASK_SPECIFIC,
      PromptPriority.P4_FEW_SHOT,
      PromptPriority.P5_CONTEXT,
      PromptPriority.P6_BASE,
    ];

    const sortedFragments = [...fragments].sort((a, b) => {
      return priorityOrder.indexOf(a.priority) - priorityOrder.indexOf(b.priority);
    });

    // 按优先级分组
    const grouped = new Map<PromptPriority, PromptFragment[]>();
    for (const fragment of sortedFragments) {
      const existing = grouped.get(fragment.priority) || [];
      existing.push(fragment);
      grouped.set(fragment.priority, existing);
    }

    // 组装
    const parts: string[] = [];

    // P6 基础系统层（最底层，先输出）
    const p6Fragments = grouped.get(PromptPriority.P6_BASE) || [];
    if (p6Fragments.length > 0) {
      parts.push(...p6Fragments.map(f => f.content));
    }

    // P5 上下文信息层
    const p5Fragments = grouped.get(PromptPriority.P5_CONTEXT) || [];
    if (p5Fragments.length > 0) {
      parts.push(...p5Fragments.map(f => f.content));
    }

    // P4 Few-shot示例层
    const p4Fragments = grouped.get(PromptPriority.P4_FEW_SHOT) || [];
    if (p4Fragments.length > 0) {
      parts.push(...p4Fragments.slice(0, this.config.few_shot_count).map(f => f.content));
    }

    // P3 任务专用层
    const p3Fragments = grouped.get(PromptPriority.P3_TASK_SPECIFIC) || [];
    if (p3Fragments.length > 0) {
      parts.push(...p3Fragments.map(f => f.content));
    }

    // P2 用户偏好层
    const p2Fragments = grouped.get(PromptPriority.P2_USER_PREFERENCE) || [];
    if (p2Fragments.length > 0) {
      parts.push(...p2Fragments.map(f => f.content));
    }

    // P1 安全约束层（最高优先级，最后输出）
    const p1Fragments = grouped.get(PromptPriority.P1_SAFETY) || [];
    if (p1Fragments.length > 0) {
      parts.push(...p1Fragments.map(f => f.content));
    }

    return parts.join('\n\n');
  }
}

// ============================================
// 上下文组装器
// ============================================

/**
 * 上下文组装器
 * 整合资产检索和优先级组装，生成最终 prompt
 */
export class ContextAssembler implements IContextAssembler {
  private recognizer: TaskTypeRecognizer;
  private retriever: AssetRetriever;
  private priorityAssembler: PriorityAssembler;
  private config: PromptEngineConfig;

  constructor(config: PromptEngineConfig = DEFAULT_PROMPT_ENGINE_CONFIG) {
    this.config = config;
    this.recognizer = new TaskTypeRecognizer();
    this.retriever = new AssetRetriever(config);
    this.priorityAssembler = new PriorityAssembler(config);
  }

  /**
   * 组装上下文
   */
  async assembleContext(params: {
    userInput: string;
    taskType?: TaskType;
    systemFragments?: PromptFragment[];
    userPreferenceFragments?: PromptFragment[];
    fewShotExamples?: PromptFragment[];
    contextFragments?: PromptFragment[];
    safetyFragments?: PromptFragment[];
  }): Promise<AssembledPrompt> {
    // 1. 确定任务类型
    let taskType = params.taskType;
    if (!taskType) {
      const recognized = this.recognizer.recognizeFromInput(params.userInput);
      taskType = recognized.length > 0 ? recognized[0].taskType : TaskType.SEARCH_SYNTH;
    }

    // 2. 检索资产
    const retrieved = await this.retriever.retrieve(
      params.userInput,
      taskType,
      this.config.few_shot_count
    );

    // 3. 合并片段
    const allFragments: PromptFragment[] = [
      ...(params.systemFragments || []),
      ...(params.userPreferenceFragments || []),
      ...(params.contextFragments || []),
      ...(params.fewShotExamples || []),
      ...retrieved.map(r => r.fragment),
      ...(params.safetyFragments || []),
    ];

    // 4. 按 P1-P6 组装
    const assembledContent = this.priorityAssembler.assemble(allFragments, taskType);

    // 5. 计算 token
    const estimatedTokens = this.estimateTokens(assembledContent);

    return {
      content: assembledContent,
      fragments_used: allFragments.map(f => f.id),
      task_type: taskType,
      signatures_used: [],
      few_shot_ids: retrieved.map(r => r.fragment.id),
      assembled_at: new Date().toISOString(),
      estimated_tokens: estimatedTokens,
    };
  }

  private estimateTokens(text: string): number {
    // 粗略估算：中文约2字符=1 token，英文约4字符=1 token
    const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length;
    const otherChars = text.length - chineseChars;
    return Math.ceil(chineseChars / 2 + otherChars / 4);
  }
}

// ============================================
// 提示词路由器（主入口）
// ============================================

/**
 * 提示词路由器
 * Layer1 的主入口类，协调各组件工作
 */
export class PromptRouter {
  private recognizer: TaskTypeRecognizer;
  private retriever: AssetRetriever;
  private assembler: ContextAssembler;
  private config: PromptEngineConfig;

  constructor(config: PromptEngineConfig = DEFAULT_PROMPT_ENGINE_CONFIG) {
    this.config = config;
    this.recognizer = new TaskTypeRecognizer();
    this.retriever = new AssetRetriever(config);
    this.assembler = new ContextAssembler(config);
  }

  /**
   * 路由并组装提示词
   * @param userInput 用户输入
   * @param context 额外上下文
   * @returns 组装后的提示词
   */
  async route(userInput: string, context?: {
    taskType?: TaskType;
    safetyRules?: string[];
    userPreferences?: Record<string, string>;
    availableTools?: string[];
    searchResults?: string[];
  }): Promise<AssembledPrompt> {
    // 1. 任务类型识别
    const recognized = this.recognizer.recognizeFromInput(userInput);
    const taskType = context?.taskType || (recognized.length > 0 ? recognized[0].taskType : TaskType.SEARCH_SYNTH);

    // 2. 构建各层级片段
    const safetyFragments: PromptFragment[] = (context?.safetyRules || []).map((rule, i) => ({
      id: `safety_${i}`,
      type: PromptFragmentType.SYSTEM,
      content: rule,
      priority: PromptPriority.P1_SAFETY,
      quality_score_history: [],
      gepa_version: 0,
      created_at: new Date().toISOString(),
    }));

    const userPrefFragments: PromptFragment[] = context?.userPreferences
      ? Object.entries(context.userPreferences).map(([key, value], i) => ({
          id: `pref_${i}`,
          type: PromptFragmentType.SYSTEM,
          content: `${key}: ${value}`,
          priority: PromptPriority.P2_USER_PREFERENCE,
          quality_score_history: [],
          gepa_version: 0,
          created_at: new Date().toISOString(),
        }))
      : [];

    const contextFragments: PromptFragment[] = [
      ...(context?.availableTools ? [{
        id: 'tools_context',
        type: PromptFragmentType.SYSTEM as PromptFragmentType,
        content: `可用工具: ${context.availableTools.join(', ')}`,
        priority: PromptPriority.P5_CONTEXT,
        quality_score_history: [],
        gepa_version: 0,
        created_at: new Date().toISOString(),
      }] : []),
      ...(context?.searchResults ? [{
        id: 'search_context',
        type: PromptFragmentType.SYSTEM as PromptFragmentType,
        content: `搜索结果摘要:\n${context.searchResults.join('\n')}`,
        priority: PromptPriority.P5_CONTEXT,
        quality_score_history: [],
        gepa_version: 0,
        created_at: new Date().toISOString(),
      }] : []),
    ];

    // 3. 组装
    return this.assembler.assembleContext({
      userInput,
      taskType,
      safetyFragments,
      userPreferenceFragments: userPrefFragments,
      contextFragments,
    });
  }

  /**
   * 注册提示词资产
   */
  registerAsset(fragment: PromptFragment): void {
    this.retriever.registerAsset(fragment);
  }

  /**
   * 获取当前配置
   */
  getConfig(): PromptEngineConfig {
    return { ...this.config };
  }
}
