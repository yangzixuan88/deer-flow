/**
 * M11 执行层与守护进程 - 模块导出
 * ================================================
 * 四大执行器 · Dapr DurableAgent · gVisor沙盒
 * 守护进程 · 视觉自动化 · 修正项落地
 * ================================================
 */

// 类型导出
export * from './types';

// 沙盒和安全
export { GVisorSandbox, gVisorSandbox, RiskAssessor, riskAssessor, RiskLevel } from './sandbox';

// 执行器
export { ExecutorAdapter, executorAdapter, VisualToolSelector, visualToolSelector, DesktopToolSelector, desktopToolSelector, OperatorStrategySelector, operatorStrategySelector } from './adapters/executor_adapter';
export { executeWithAutoSelect, classifyOperation, OperationType } from './adapters/executor_adapter';
export type { FallbackResult } from './adapters/executor_adapter';

// ★ Round 7/8: 执行器健康检查与自维持
export { checkExecutorHealth, executorReadinessGate } from './adapters/executor_adapter';
export type { ExecutorHealth } from './adapters/executor_adapter';

// ★ Round 8: 自愈层
export { attemptSelfHeal } from './adapters/executor_adapter';
export type { SelfHealResult } from './adapters/executor_adapter';

// ★ Round 7/8: 目标态验证
export { parseGoalState, verifyGoalState, extractObservedStateFromChecks, observationDrivenNextStep } from './adapters/executor_adapter';
export type { GoalVerificationResult } from './adapters/executor_adapter';

// ★ Round 8: 目标驱动链
export { runGoalDrivenChain } from './adapters/executor_adapter';
export type { GoalDrivenStepRecord, GoalDrivenChainResult } from './adapters/executor_adapter';

// ★ Round 7/8: 检查点与恢复
export { CheckpointManager, checkpointManager } from './adapters/executor_adapter.js';
export type { RecoveryCheckpoint, ResumeResult } from './adapters/executor_adapter.js';
// 注: recordRealInterruption, getInterruptionInfo, resumeWithGoalState 是 CheckpointManager 实例方法
// 通过 checkpointManager 实例访问，不作为独立命名导出

export { LarkCLIAdapter, larkCLIAdapter } from './adapters/lark_cli_adapter';

// 守护进程
export { DaemonManager, daemonManager, ScriptCabinet, scriptCabinet } from './daemon_manager';

// ★ Round 10: 超人化系统
export { StrategyLearner, strategyLearner, OperationAssetRegistry, operationAssetRegistry, SuperhumanEfficiencyEngine, superhumanEngine } from './strategy_learner';
export type { StrategyHistoryRecord, ExecutorSuccessStats, StrategySelectionResult, OperationAsset, SuperhumanMetrics } from './strategy_learner';

// ★ Round 11: 超人运营智能系统
export { WorldModel, DynamicReplanner, ResourceArbitrator, SuperhumanOperationalEngine, operationalEngine } from './world_model_round11';
export type {
  WorldEntity, WorldState, WorldDelta, WorldSnapshot,
  ReplanTrigger, ReplanDecision, ReplanDecisionType, ReplanTrace,
  ResourceConflict, ArbitrationDecision, ArbitrationAction, ParallelTrace,
  SuperhumanOperationalMetrics, OperationalIntelligenceMetrics,
} from './world_model_round11';

// ★ Round 12: 多任务自治运营层
export { TaskPortfolio, MultiTaskScheduler, SovereigntyGovernance, DailyEvolutionEngine, AutonomousOperationEngine, autonomousEngine } from './autonomous_governance_round12';
export type {
  TaskChain, TaskPriority, TaskStatus, ApprovalState, SchedulerDecision,
  SovereigntyDecision, ExperienceEntry, DailyEvolutionReport,
} from './autonomous_governance_round12';
export { HIGH_RISK_PATTERNS } from './autonomous_governance_round12';

// ★ Round 13: 真实自治执行闭环
export { ExecutionEventEmitter, ResourceSampler, AutonomousRuntimeLoop, ExperiencePersister, AutonomousExecutionEngine, autonomousExecutionEngine } from './autonomous_runtime_round13';
export type {
  ExecutionEvent, ResourceSnapshot,
} from './autonomous_runtime_round13';

// ★ Round 14: 长期自治与可控进化
export type {
  DurableRuntimeState, DurableEventEntry,
  ExperienceLifecycle, GradedExperience, StrategyPatch, EvolutionAuditEntry,
  LockMode, ResourceLock, ResourceSchedulingTrace,
} from './autonomous_durable_round14';
export { DurableEventLog, HeartbeatMonitor, ControlledEvolutionEngine, ResourceLockManager, DurableAutonomousEngine, durableAutonomousEngine } from './autonomous_durable_round14';

// ★ Round 15: 使命系统 + 量化评估 + 组织协作
export { MissionRegistry, CapabilityEvaluationEngine, MultiAgentOrganization, MissionEvaluationEngine, missionEvaluationEngine } from './mission_evaluation_round15';
export type {
  MissionStatus, Milestone, Subgoal, Mission, MissionTraceEntry,
  AgentRole, HandoffRecord, OrgTraceEntry,
  BenchmarkTask, EvaluationReport, CapabilityMetrics, VersionComparison as VersionComparisonResult,
} from './mission_evaluation_round15';

// ★ Round 16: 战略组合管理 + 制度级记忆 + 模拟实验决策
export { StrategicPortfolioManager, InstitutionalMemory, StrategicExperimentEngine, StrategicManagementEngine, strategicManagementEngine } from './strategic_management_round16';
export type {
  PortfolioMission, PortfolioScore, PortfolioDecision, PortfolioTraceEntry, PortfolioMissionStatus, PortfolioDecisionType,
  MemoryEntry, MemoryType, MemoryRetrievalResult,
  Experiment, ExperimentResult, ExperimentStatus, SimulationResult,
} from './strategic_management_round16';

// ★ Round 17: 外部结果真相 + 经营层控制 + 元治理/宪法层
export { ExternalOutcomeTruth, ExecutiveOperatingLayer, MetaGovernanceLayer, MetaGovernanceEngine, metaGovernanceEngine } from './meta_governance_round17';
export type {
  OutcomeEntry as OutcomeRecord, OutcomeGapAnalysis as GapAnalysis,
  Commitment, OperatingScore,
  ConstitutionRule as ConstitutionalRule, RulePatchProposal,
  MetaGovernanceLayer as MetaGovernanceTraceEntry,
} from './meta_governance_round17';

// ★ Round 18: 认知真相治理 + 多方谈判 + 战略前瞻
export { EpistemicGovernanceLayer, StakeholderNegotiationLayer, StrategicForesightLayer, CognitiveIntelligenceEngine, cognitiveIntelligenceEngine } from './cognition_governance_round18';
export type {
  TruthSource, TruthEntry, SourceType,
  Stakeholder, NegotiationIssue, NegotiationResult, StakeholderType,
  Scenario, FutureBranch, ForesightResult, HorizonLevel,
} from './cognition_governance_round18';

// ★ Round 19: 身份声誉层 + 规范传播层 + 长期教义演化层
export { IdentityReputationLayer, NormDoctrinePropagationLayer, LongHorizonDoctrineLayer, CognitiveDoctrineEngine, cognitiveDoctrineEngine } from './cognition_doctrine_round19';
export type {
  IdentityEntry, ReputationEntry, ReputationUpdateRule, ReputationLevel,
  NormEntry, NormViolation, NormTraceEntry, NormCompliance, NormStatus,
  DoctrineEntry, DoctrineTraceEntry, DoctrineDriftSignal, DoctrineStatus, DoctrineInfluence,
  NormFeedbackLoop,
} from './cognition_doctrine_round19';
