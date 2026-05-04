/**
 * M09 提示词工程系统 - 模块导出
 * ================================================
 * 五层提示词架构
 * Layer1: 路由层 (layer1_router.ts)
 * Layer2: 监控层 (layer2_monitor.ts)
 * Layer3: 反馈层 (layer3_feedback.ts)
 * Layer4: 进化层 (layer4_nightly.ts)
 * Layer5: 固化层 (layer5_asset.ts)
 * ================================================
 */

export * from './types';

// Layer1: 路由层
export { PromptRouter } from './layer1_router';
export { TaskTypeRecognizer } from './layer1_router';
export { AssetRetriever } from './layer1_router';
export { ContextAssembler } from './layer1_router';
export { PriorityAssembler } from './layer1_router';

// Layer2: 监控层
export { LLMWatchdog } from './layer2_monitor';
export { ExecutionTracker } from './layer2_monitor';
export { LLMJudge } from './layer2_monitor';

// Layer3: 反馈层
export { FeedbackCollector } from './layer3_feedback';
export { UserFeedbackParser } from './layer3_feedback';
export { ContributionAttributor } from './layer3_feedback';
export { AutoQualitySignal } from './layer3_feedback';

// Layer4: 进化层
export { GepaEngine } from './layer4_nightly';
export { HeuristicCompiler } from './layer4_nightly';
export { NightlyEvolutionScheduler } from './layer4_nightly';

// Layer5: 固化层
export { PromptAssetManager } from './layer5_asset';
export { SolidificationChecker } from './layer5_asset';
export { TierClassifier } from './layer5_asset';

// Signature 注册表
export { SignatureRegistry } from './signatures/mod';
export * from './signatures/mod';

// 配方注册表
export { RecipeRegistry } from './recipes/mod';
export * from './recipes/mod';

// 组装模块
export * from './assembly/mod';

// GEPA 模块
export * from './gepa/mod';

// 启发式优化器模块 (原 DSPy 模块)
export * from './dspy/mod';
export * from './dspy_compiler';
export {
  HeuristicOptimizer,
  PromptModule,
  createHeuristicOptimizer,
  createPromptModule,
  // 兼容性别名 (已弃用) — type-only re-export since dspy_compiler.ts only has `export type`
  type DspyMiproCompiler,
  createDspyCompiler,
} from './dspy_compiler';

// 搜索模块
export { TriggerDetector } from './search/mod';
export { ResultProcessor } from './search/mod';
export { AssetConverter } from './search/mod';

// M09-M10/M08 集成
export * from './integration';
