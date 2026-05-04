/**
 * @file rtcm_observability.ts
 * @description RTCM 可观测性与运行遥测层 - Gamma 可运营态核心
 * 提供 round/llm/validation/project 四级遥测
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { runtimePath } from '../runtime_paths';

// ============================================================================
// Types - 四级遥测
// ============================================================================

// A. Round 级遥测
export interface RoundMetrics {
  roundId: string;
  issueId: string;
  stage: string;
  participants: string[];
  startTime: string;
  endTime: string;
  durationMs: number;
  memberMetrics: MemberMetrics[];
  parseSuccess: boolean;
  parseFailures: number;
  regenerationCount: number;
  supervisorGateResult: SupervisorGateResult | null;
  error?: string;
}

export interface MemberMetrics {
  roleId: string;
  callStartTime: string;
  callEndTime: string;
  durationMs: number;
  parseSuccess: boolean;
  fallbackTriggered: boolean;
  tokensUsed?: number;
}

export interface SupervisorGateResult {
  allMembersPresent: boolean;
  allOutputsParseable: boolean;
  criticalClaimsHaveEvidenceRefs: boolean;
  dissentPresent: boolean;
  uncertaintyPresent: boolean;
  violations: string[];
}

// B. LLM 调用级遥测
export interface LLMMetrics {
  callId: string;
  provider: string;
  model: string;
  roundId: string;
  roleId: string;
  startTime: string;
  endTime: string;
  latencyMs: number;
  rawResponseLength: number;
  sanitizedResponseLength: number;
  jsonExtractSuccess: boolean;
  fallbackTriggered: boolean;
  tokensUsed?: { input: number; output: number; total: number };
  error?: string;
}

// C. Validation 级遥测
export interface ValidationMetrics {
  validationRunId: string;
  issueId: string;
  startTime: string;
  endTime: string;
  pass: boolean;
  reopenTriggered: boolean;
  reopenReason?: string;
  reopenTarget?: string;
  evidenceConflictCount: number;
  conflictSeverityDistribution: { high: number; medium: number; low: number };
  verdict?: string;
  error?: string;
}

// D. Project 级遥测
export interface ProjectMetrics {
  projectId: string;
  sessionId: string;
  startTime: string;
  endTime?: string;
  totalRounds: number;
  totalReopenCount: number;
  totalValidationCount: number;
  userAcceptanceCount: number;
  finalStatus: 'active' | 'paused' | 'archived' | 'failed_recoverable' | 'failed_terminal';
  averageIssueDurationMs: number;
  averageRoundCost?: number;
  totalCost?: number;
  issueMetrics: IssueMetricsSummary[];
}

export interface IssueMetricsSummary {
  issueId: string;
  rounds: number;
  reopenCount: number;
  validationAttempts: number;
  finalVerdict?: string;
}

// ============================================================================
// Telemetry Writer
// ============================================================================

export class TelemetryWriter {
  private telemetryDir: string;

  constructor(baseDir?: string) {
    const defaultDir = runtimePath('rtcm', 'telemetry');
    this.telemetryDir = baseDir || process.env.RTCM_TELEMETRY_DIR || defaultDir;
    this.ensureDir(this.telemetryDir);

    // 创建子目录
    this.ensureDir(path.join(this.telemetryDir, 'rounds'));
    this.ensureDir(path.join(this.telemetryDir, 'llm'));
    this.ensureDir(path.join(this.telemetryDir, 'validation'));
    this.ensureDir(path.join(this.telemetryDir, 'project'));
  }

  private ensureDir(dir: string): void {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  private appendJsonl(filePath: string, data: object): void {
    const line = JSON.stringify(data);
    fs.appendFileSync(filePath, line + '\n', 'utf-8');
  }

  // Round Metrics
  writeRoundMetrics(metrics: RoundMetrics): void {
    const filePath = path.join(this.telemetryDir, 'rounds', `${metrics.issueId}_round_${metrics.roundId}.jsonl`);
    this.appendJsonl(filePath, {
      ...metrics,
      _type: 'round_metrics',
      _ts: new Date().toISOString(),
    });
  }

  // LLM Metrics
  writeLLMMetrics(metrics: LLMMetrics): void {
    const filePath = path.join(this.telemetryDir, 'llm', `${metrics.roundId}_${metrics.roleId}.jsonl`);
    this.appendJsonl(filePath, {
      ...metrics,
      _type: 'llm_metrics',
      _ts: new Date().toISOString(),
    });
  }

  // Validation Metrics
  writeValidationMetrics(metrics: ValidationMetrics): void {
    const filePath = path.join(this.telemetryDir, 'validation', `${metrics.issueId}_validation.jsonl`);
    this.appendJsonl(filePath, {
      ...metrics,
      _type: 'validation_metrics',
      _ts: new Date().toISOString(),
    });
  }

  // Project Metrics
  writeProjectMetrics(metrics: ProjectMetrics): void {
    const filePath = path.join(this.telemetryDir, 'project', `${metrics.projectId}_project_metrics.json`);
    fs.writeFileSync(filePath, JSON.stringify({
      ...metrics,
      _type: 'project_metrics',
      _ts: new Date().toISOString(),
    }, null, 2), 'utf-8');
  }

  // 汇总写入
  writeAllMetrics(
    roundMetrics: RoundMetrics[],
    llmMetrics: LLMMetrics[],
    validationMetrics: ValidationMetrics[],
    projectMetrics: ProjectMetrics
  ): void {
    for (const m of roundMetrics) this.writeRoundMetrics(m);
    for (const m of llmMetrics) this.writeLLMMetrics(m);
    for (const m of validationMetrics) this.writeValidationMetrics(m);
    this.writeProjectMetrics(projectMetrics);
  }

  getTelemetryDir(): string {
    return this.telemetryDir;
  }
}

// ============================================================================
// Telemetry Query (用于分析和追踪)
// ============================================================================

export class TelemetryQuery {
  private telemetryDir: string;

  constructor(baseDir?: string) {
    const defaultDir = runtimePath('rtcm', 'telemetry');
    this.telemetryDir = baseDir || process.env.RTCM_TELEMETRY_DIR || defaultDir;
  }

  // 追踪某次 reopen 的因果链
  traceReopenChain(issueId: string): {
    issueId: string;
    validationMetrics: ValidationMetrics[];
    roundMetrics: RoundMetrics[];
   因果链: string[];
  } {
    const validationFile = path.join(this.telemetryDir, 'validation', `${issueId}_validation.jsonl`);
    const roundDir = path.join(this.telemetryDir, 'rounds');

    const validationMetrics: ValidationMetrics[] = [];
    const roundMetrics: RoundMetrics[] = [];
    const 因果链: string[] = [];

    // 读取 validation metrics
    if (fs.existsSync(validationFile)) {
      const lines = fs.readFileSync(validationFile, 'utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        const m = JSON.parse(line) as ValidationMetrics;
        if (m.reopenTriggered) {
          validationMetrics.push(m);
          因果链.push(`[${m.startTime}] Validation failed → reopen: ${m.reopenReason}`);
        }
      }
    }

    // 读取相关 round metrics
    if (fs.existsSync(roundDir)) {
      const files = fs.readdirSync(roundDir).filter(f => f.startsWith(issueId));
      for (const file of files) {
        const content = fs.readFileSync(path.join(roundDir, file), 'utf-8');
        const lines = content.split('\n').filter(Boolean);
        for (const line of lines) {
          roundMetrics.push(JSON.parse(line));
        }
      }
    }

    return { issueId, validationMetrics, roundMetrics, 因果链 };
  }

  // 追踪一次角色输出的失败
  traceRoleFailure(roleId: string, roundId: string): {
    llmMetrics: LLMMetrics[];
    parseFailures: number;
    regenerationCount: number;
    supervisorResult?: SupervisorGateResult;
  } {
    const llmFile = path.join(this.telemetryDir, 'llm', `${roundId}_${roleId}.jsonl`);
    const roundFile = path.join(this.telemetryDir, 'rounds', `*_round_${roundId}.jsonl`);

    const llmMetrics: LLMMetrics[] = [];
    let parseFailures = 0;
    let regenerationCount = 0;
    let supervisorResult: SupervisorGateResult | undefined;

    if (fs.existsSync(llmFile)) {
      const lines = fs.readFileSync(llmFile, 'utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        const m = JSON.parse(line) as LLMMetrics;
        llmMetrics.push(m);
        if (!m.jsonExtractSuccess) parseFailures++;
        if (m.fallbackTriggered) regenerationCount++;
      }
    }

    return { llmMetrics, parseFailures, regenerationCount, supervisorResult };
  }

  // 获取项目汇总
  getProjectSummary(projectId: string): ProjectMetrics | null {
    const filePath = path.join(this.telemetryDir, 'project', `${projectId}_project_metrics.json`);
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  }
}

// ============================================================================
// Telemetry Aggregator (用于实时告警)
// ============================================================================

export class TelemetryAlertThresholds {
  static readonly REGENERATION_WARNING = 3;
  static readonly REGENERATION_CRITICAL = 5;
  static readonly REOPEN_WARNING = 2;
  static readonly REOPEN_CRITICAL = 4;
  static readonly CONFLICT_HIGH_WARNING = 3;
  static readonly LLM_LATENCY_WARNING_MS = 30000;
  static readonly LLM_LATENCY_CRITICAL_MS = 60000;
}

export class TelemetryAggregator {
  private alerts: TelemetryAlert[] = [];

  checkAndAlert(metrics: RoundMetrics | LLMMetrics | ValidationMetrics): TelemetryAlert[] {
    const newAlerts: TelemetryAlert[] = [];

    if ('regenerationCount' in metrics && metrics.regenerationCount > 0) {
      if (metrics.regenerationCount >= TelemetryAlertThresholds.REGENERATION_CRITICAL) {
        newAlerts.push({
          level: 'critical',
          type: 'regeneration_excessive',
          message: `Regeneration count ${metrics.regenerationCount} exceeds critical threshold`,
          timestamp: new Date().toISOString(),
          source: 'round_metrics',
        });
      } else if (metrics.regenerationCount >= TelemetryAlertThresholds.REGENERATION_WARNING) {
        newAlerts.push({
          level: 'warning',
          type: 'regeneration_high',
          message: `Regeneration count ${metrics.regenerationCount} is high`,
          timestamp: new Date().toISOString(),
          source: 'round_metrics',
        });
      }
    }

    if ('reopenTriggered' in metrics && metrics.reopenTriggered) {
      if ('evidenceConflictCount' in metrics && metrics.evidenceConflictCount >= TelemetryAlertThresholds.CONFLICT_HIGH_WARNING) {
        newAlerts.push({
          level: 'warning',
          type: 'evidence_conflict_high',
          message: `Evidence conflict count ${metrics.evidenceConflictCount} is high`,
          timestamp: new Date().toISOString(),
          source: 'validation_metrics',
        });
      }
    }

    if ('latencyMs' in metrics && metrics.latencyMs > 0) {
      if (metrics.latencyMs >= TelemetryAlertThresholds.LLM_LATENCY_CRITICAL_MS) {
        newAlerts.push({
          level: 'critical',
          type: 'llm_latency_critical',
          message: `LLM latency ${metrics.latencyMs}ms exceeds critical threshold`,
          timestamp: new Date().toISOString(),
          source: 'llm_metrics',
        });
      } else if (metrics.latencyMs >= TelemetryAlertThresholds.LLM_LATENCY_WARNING_MS) {
        newAlerts.push({
          level: 'warning',
          type: 'llm_latency_high',
          message: `LLM latency ${metrics.latencyMs}ms is high`,
          timestamp: new Date().toISOString(),
          source: 'llm_metrics',
        });
      }
    }

    this.alerts.push(...newAlerts);
    return newAlerts;
  }

  getAlerts(): TelemetryAlert[] {
    return [...this.alerts];
  }

  clearAlerts(): void {
    this.alerts = [];
  }
}

export interface TelemetryAlert {
  level: 'warning' | 'critical';
  type: string;
  message: string;
  timestamp: string;
  source: string;
}

// ============================================================================
// Singleton Export
// ============================================================================

export const telemetryWriter = new TelemetryWriter();
export const telemetryQuery = new TelemetryQuery();
export const telemetryAggregator = new TelemetryAggregator();
