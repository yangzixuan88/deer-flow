/**
 * M09 提示词工程系统 - 类型定义
 * ================================================
 * 五层提示词架构的类型系统
 * Layer1: 路由层类型
 * Layer2: 监控层类型
 * Layer3: 反馈层类型
 * Layer4: 进化层类型
 * Layer5: 固化层类型
 * ================================================
 */

// ============================================
// 九大任务类型
// ============================================

export enum TaskType {
  /** 信息搜索 - 搜索+综合 */
  SEARCH_SYNTH = 'search_synth',
  /** 代码生成 - 代码编写+测试 */
  CODE_GEN = 'code_gen',
  /** 文档写作 - 文档创作+编辑 */
  DOC_WRITE = 'doc_write',
  /** 数据分析 - 数据处理+洞察 */
  DATA_ANALYSIS = 'data_analysis',
  /** 问题诊断 - 故障排查+解决 */
  DIAGNOSIS = 'diagnosis',
  /** 规划制定 - 计划编排+资源分配 */
  PLANNING = 'planning',
  /** 创意生成 - 创意发散+方案设计 */
  CREATIVE = 'creative',
  /** 系统配置 - 系统配置+参数调优 */
  SYS_CONFIG = 'sys_config',
  /** 自主决策 - AAL决策+风险评估 */
  AAL_DECISION = 'aal_decision',
}

// ============================================
// P1-P6 优先级层级
// ============================================

export enum PromptPriority {
  /** P1 安全约束层 - 不可覆盖 */
  P1_SAFETY = 'p1_safety',
  /** P2 用户偏好层 - 高优先级 */
  P2_USER_PREFERENCE = 'p2_user_preference',
  /** P3 任务专用层 - 任务感知 */
  P3_TASK_SPECIFIC = 'p3_task_specific',
  /** P4 Few-shot示例层 - 历史最优 */
  P4_FEW_SHOT = 'p4_few_shot',
  /** P5 上下文信息层 - 实时补充 */
  P5_CONTEXT = 'p5_context',
  /** P6 基础系统层 - 兜底 */
  P6_BASE = 'p6_base',
}

// ============================================
// Signature 定义 (DSPy风格)
// ============================================

export interface DspySignature {
  /** Signature 名称 */
  name: string;
  /** 输入字段定义 */
  input_fields: string[];
  /** 输出字段定义 */
  output_fields: string[];
  /** 描述 */
  description: string;
  /** 关联的任务类型 */
  task_types: TaskType[];
  /** 编译状态 */
  is_compiled: boolean;
  /** 最后编译时间 */
  last_compiled?: string;
  /** 编译的目标模型 */
  compiled_for?: string;
}

// ============================================
// 提示词片段
// ============================================

export interface PromptFragment {
  /** 片段ID */
  id: string;
  /** 片段类型 */
  type: PromptFragmentType;
  /** 内容 */
  content: string;
  /** 关联的 Signature */
  signature?: string;
  /** 优先级 */
  priority: PromptPriority;
  /** 质量评分历史 */
  quality_score_history: number[];
  /** GEPA 版本号 */
  gepa_version: number;
  /** 来源 */
  source?: string;
  /** 创建时间 */
  created_at: string;
  /** 最后使用时间 */
  last_used_at?: string;
}

export enum PromptFragmentType {
  /** 系统级提示词 */
  SYSTEM = 'system',
  /** 任务级提示词 */
  TASK = 'task',
  /** Few-shot 示例 */
  FEW_SHOT = 'few_shot',
  /** 思维链 */
  CHAIN_OF_THOUGHT = 'chain_of_thought',
  /** 输出格式 */
  OUTPUT_FORMAT = 'output_format',
}

// ============================================
// 上下文组装
// ============================================

export interface AssembledPrompt {
  /** 完整组装后的 prompt */
  content: string;
  /** 使用的片段列表 */
  fragments_used: string[];
  /** 任务类型 */
  task_type: TaskType;
  /** 激活的 Signature */
  signatures_used: string[];
  /** Few-shot 示例IDs */
  few_shot_ids: string[];
  /** 组装时间戳 */
  assembled_at: string;
  /** token 消耗估算 */
  estimated_tokens: number;
}

// ============================================
// 执行轨迹记录
// ============================================

export interface ExecutionTrace {
  /** 轨迹ID */
  id: string;
  /** 时间戳 */
  timestamp: string;
  /** 任务类型 */
  task_type: TaskType;
  /** 使用的提示词片段 */
  fragments_used: string[];
  /** 质量评分 */
  quality_score: number;
  /** token 消耗 */
  token_consumed: number;
  /** 执行结果 */
  result: ExecutionResult;
  /** 失败原因（如有） */
  failure_reason?: string;
  /** 重试次数 */
  retry_count: number;
}

export enum ExecutionResult {
  SUCCESS = 'success',
  PARTIAL = 'partial',
  FAILED = 'failed',
  RETRY = 'retry',
}

// ============================================
// LLM-Judge 评分
// ============================================

export interface LLMJudgeScore {
  /** 综合评分 (0-1) */
  overall: number;
  /** 完整性评分 */
  completeness: number;
  /** 准确性评分 */
  accuracy: number;
  /** 格式合规评分 */
  format_compliance: number;
  /** 用户偏好匹配评分 */
  preference_match: number;
  /** 评估时间 */
  evaluated_at: string;
}

// ============================================
// 反馈采集
// ============================================

export interface FeedbackSignal {
  /** 信号来源 */
  source: FeedbackSource;
  /** 任务完成度 (0-1) */
  task_completion?: number;
  /** 后续任务成功率 (0-1) */
  follow_up_success_rate?: number;
  /** 用户是否要求重做 */
  user_requested_redo?: boolean;
  /** 搜索引用置信度 (0-1) */
  search_citation_confidence?: number;
  /** 显式用户反馈文本 */
  explicit_feedback?: string;
  /** 捕获时间 */
  captured_at: string;
}

export enum FeedbackSource {
  /** 自动质量信号 */
  AUTO_QUALITY = 'auto_quality',
  /** 显式用户反馈 */
  EXPLICIT_USER = 'explicit_user',
  /** 任务成功率 */
  TASK_SUCCESS = 'task_success',
  /** 搜索置信度 */
  SEARCH_CONFIDENCE = 'search_confidence',
}

// ============================================
// GEPA 进化
// ============================================

export interface GepaCandidate {
  /** 候选ID */
  id: string;
  /** 原始片段ID */
  original_fragment_id: string;
  /** 候选内容 */
  content: string;
  /** 候选版本号 */
  version: number;
  /** Pareto 前沿排名 */
  pareto_rank?: number;
  /** 生成时间 */
  generated_at: string;
  /** 生成原因 */
  generation_reason: string;
}

export interface GepaEvolutionResult {
  /** 原始片段 */
  original_fragment: PromptFragment;
  /** 候选列表 */
  candidates: GepaCandidate[];
  /** 选中的最佳候选 */
  selected_candidate?: GepaCandidate;
  /** 进化是否成功 */
  evolution_success: boolean;
  /** 质量提升分数 */
  quality_improvement?: number;
  /** 执行时间 */
  executed_at: string;
}

// ============================================
// DSPy 编译
// ============================================

export interface DspyCompilationConfig {
  /** 触发条件 */
  trigger: DspyCompilationTrigger;
  /** 目标模型 */
  target_model: string;
  /** 要编译的 Signatures */
  signatures: string[];
  /** 编译预算 (LLM调用次数上限) */
  budget: number;
  /** 执行中 */
  is_running: boolean;
  /** 开始时间 */
  started_at?: string;
}

export enum DspyCompilationTrigger {
  /** 模型版本更新 */
  MODEL_UPDATE = 'model_update',
  /** 持续质量下降 */
  QUALITY_DECAY = 'quality_decay',
  /** 用户主动触发 */
  USER_TRIGGERED = 'user_triggered',
}

// ============================================
// 提示词资产扩展 (第7类资产)
// ============================================

export interface PromptAssetExtension {
  /** 提示词类型 */
  prompt_type: PromptFragmentType;
  /** 关联的任务类型列表 */
  task_types: TaskType[];
  /** DSPy 编译目标模型 */
  model_compiled_for?: string;
  /** 质量评分历史 */
  quality_score_history: number[];
  /** GEPA 版本号 */
  gepa_version: number;
  /** 搜索来源 */
  search_source?: string;
  /** DSPy Signature 名称 */
  dspy_signature?: string;
  /** 平均 token 消耗 */
  avg_token_cost: number;
  /** 最后编译时间 */
  last_compiled?: string;
}

// ============================================
// SharedContext 扩展字段
// ============================================

export interface PromptContext {
  /** 当前任务类型 */
  task_type: TaskType;
  /** 激活的配方ID */
  active_recipe: string;
  /** 使用的 Signatures */
  signatures_used: string[];
  /** Few-shot 示例IDs */
  few_shot_ids: string[];
  /** 质量评分历史 */
  quality_scores: number[];
  /** 重试次数 */
  retry_count: number;
  /** 重试原因 */
  retry_reason?: string;
  /** 最终评分 */
  final_score?: number;
  /** 晋升候选 */
  promote_candidate: boolean;
  /** GEPA 触发标志 */
  gepa_trigger: boolean;
}

// ============================================
// 搜索触发场景
// ============================================

export interface SearchTrigger {
  /** 场景类型 */
  scenario: SearchScenario;
  /** 触发条件描述 */
  condition_description: string;
  /** 搜索关键词 */
  search_query?: string;
  /** 触发时间 */
  triggered_at?: string;
  /** 执行状态 */
  status: SearchTriggerStatus;
}

export enum SearchScenario {
  /** 新任务类型出现 */
  NEW_TASK_TYPE = 'new_task_type',
  /** 现有提示词质量下降 */
  QUALITY_DECLINE = 'quality_decline',
  /** 模型更新 */
  MODEL_UPDATE = 'model_update',
  /** 夜间情报侦察 */
  NIGHTLY_INTEL = 'nightly_intel',
}

export enum SearchTriggerStatus {
  PENDING = 'pending',
  EXECUTING = 'executing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

// ============================================
// 固化触发条件
// ============================================

export interface SolidificationTrigger {
  /** 触发类型 */
  type: SolidificationTriggerType;
  /** 触发条件描述 */
  condition_description: string;
  /** 关联的片段ID */
  fragment_id: string;
  /** 触发时间 */
  triggered_at: string;
  /** 验证状态 */
  verification_status: VerificationStatus;
}

export enum SolidificationTriggerType {
  /** 连续高质量 */
  CONSECUTIVE_HIGH_QUALITY = 'consecutive_high_quality',
  /** 救场成功 */
  SAVE_THE_DAY = 'save_the_day',
  /** 跨场景复用 */
  CROSS_SCENARIO_REUSE = 'cross_scenario_reuse',
}

export enum VerificationStatus {
  PENDING = 'pending',
  VERIFYING = 'verifying',
  PASSED = 'passed',
  FAILED = 'failed',
}

// ============================================
// 资产分级 (与M07 AssetManager对齐)
// ============================================

export type AssetTier = 'record' | 'general' | 'available' | 'premium' | 'core';

// 运行时表示（用于枚举式访问）
export const AssetTier = {
  RECORD: 'record',
  GENERAL: 'general',
  AVAILABLE: 'available',
  PREMIUM: 'premium',
  CORE: 'core',
} as const;

// ============================================
// 提示词系统配置
// ============================================

export interface PromptEngineConfig {
  /** 资产检索相似度阈值 */
  asset_retrieval_threshold: number;
  /** 质量评分阈值 */
  quality_threshold: number;
  /** 重试次数上限 */
  max_retries: number;
  /** GEPA 质量提升阈值 */
  gepa_improvement_threshold: number;
  /** DSPy 编译预算 */
  dspy_compilation_budget: number;
  /** Few-shot 示例数量 */
  few_shot_count: number;
  /** Token 保留阈值 */
  token_retain_threshold: number;
}

// ============================================
// 默认配置
// ============================================

export const DEFAULT_PROMPT_ENGINE_CONFIG: PromptEngineConfig = {
  asset_retrieval_threshold: 0.85,
  quality_threshold: 0.7,
  max_retries: 3,
  gepa_improvement_threshold: 0.05,
  dspy_compilation_budget: 500,
  few_shot_count: 3,
  token_retain_threshold: 90000,
};

// ============================================
// 缺失的类型定义
// ============================================

export interface ContributionAttribution {
  fragment_id: string;
  contribution_score: number;
  is_promotion_candidate: boolean;
  attribution_reason: string;
}

// 质量评分接口
export interface QualityScore {
  score: number;
  dimension: string;
  reason: string;
}

// Layer1 接口定义
export interface TaskTypeRecognizer {
  recognizeFromInput(userInput: string): { taskType: TaskType; confidence: number }[];
  recognizeFromProfile(profile: { goal?: string; deliverable?: string; task_category?: string }): TaskType;
}

export interface AssetRetriever {
  retrieve(query: string, taskType: TaskType, limit?: number): Promise<{ fragment: PromptFragment; similarity: number }[]>;
  registerAsset(fragment: PromptFragment): void;
}

export interface ContextAssembler {
  assembleContext(params: {
    userInput: string;
    taskType?: TaskType;
    systemFragments?: PromptFragment[];
    userPreferenceFragments?: PromptFragment[];
    fewShotExamples?: PromptFragment[];
    contextFragments?: PromptFragment[];
    safetyFragments?: PromptFragment[];
  }): Promise<AssembledPrompt>;
}
