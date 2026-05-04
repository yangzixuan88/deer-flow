/**
 * M11 执行层与守护进程 - 类型定义
 * ================================================
 * 四大执行器 · Dapr DurableAgent · gVisor沙盒
 * 守护进程 · 视觉自动化 · 修正项落地
 * ================================================
 */

// ============================================
// 执行器枚举
// ============================================

export enum ExecutorType {
  CLAUDE_CODE = 'claude_code',
  CLI_ANYTHING = 'cli_anything',
  MIDSCENE = 'midscene',
  UI_TARS = 'ui_tars',
  OPENCLI = 'opencli', // 浏览器自动化首选 (CDP协议·会话复用)
}

export enum ExecutorStatus {
  IDLE = 'idle',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

// ============================================
// 执行任务
// ============================================

export interface ExecutorTask {
  id: string;
  type: ExecutorType;
  instruction: string;
  params: Record<string, any>;
  status: ExecutorStatus;
  sandboxed: boolean;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  result?: any;
  error?: string;
  retry_count: number;
  max_retries: number;
}

export interface ExecutorResult {
  success: boolean;
  task_id: string;
  result?: any;
  error?: string;
  execution_time_ms: number;
  tokens_used?: number;
}

// ============================================
// gVisor沙盒
// ============================================

export enum SandboxType {
  DOCKER = 'docker',
  GVISOR = 'gvisor',
  NATIVE = 'native',
}

export interface SandboxConfig {
  type: SandboxType;
  image?: string;
  memory_limit_mb?: number;
  cpu_limit?: number;
  network_enabled: boolean;
  read_only_fs: boolean;
  timeout_ms: number;
}

export interface SandboxResult {
  sandbox_id: string;
  success: boolean;
  stdout?: string;
  stderr?: string;
  exit_code: number;
  execution_time_ms: number;
}

// ============================================
// Daemon守护进程
// ============================================

export enum DaemonStatus {
  STOPPED = 'stopped',
  RUNNING = 'running',
  FAILED = 'failed',
  PAUSED = 'paused',
}

export interface DaemonConfig {
  name: string;
  script_path: string;
  cron_expression: string;
  enabled: boolean;
  sandbox: boolean;
  notify_on_failure: boolean;
  notification_channel?: string;
  max_consecutive_failures: number;
}

export interface DaemonInstance {
  name: string;
  status: DaemonStatus;
  last_run_at?: string;
  last_success_at?: string;
  last_failure_at?: string;
  consecutive_failures: number;
  pid?: number;
}

// ============================================
// DurableAgent持久化
// ============================================

export interface DurableExecutionState {
  execution_id: string;
  task_id: string;
  current_step: number;
  total_steps: number;
  steps_completed: string[];
  steps_failed: string[];
  checkpoint_id?: string;
  created_at: string;
  updated_at: string;
}

export interface Checkpoint {
  id: string;
  execution_id: string;
  step: number;
  state: Record<string, any>;
  created_at: string;
}

// ============================================
// 修正项类型
// ============================================

export interface HallucinationCircuitBreakerConfig {
  enabled: boolean;
  similarity_threshold: number; // 0-1, default 0.9
  window_size: number; // 过去N轮
  max_consecutive_triggers: number;
}

export interface ShadowModeConfig {
  enabled: boolean;
  sandbox_config: SandboxConfig;
  max_execution_time_ms: number;
}

export interface LATSConfig {
  enabled: boolean;
  max_depth: number;
  backtrack_steps: number;
  exploration_factor: number;
}

export interface ZeroTrustVaultConfig {
  enabled: boolean;
  vault_url?: string;
  token_ttl_seconds: number;
  require_manual_approval: boolean;
}

// ============================================
// Crontab配置
// ============================================

export interface CrontabEntry {
  daemon_name: string;
  cron: string;
  script: string;
  sandbox: boolean;
  notify?: string;
}

export interface CrontabConfig {
  version: string;
  updated_at: string;
  daemons: CrontabEntry[];
}

// ============================================
// 默认配置
// ============================================

export const DEFAULT_SANDBOX_CONFIG: SandboxConfig = {
  type: SandboxType.GVISOR,
  memory_limit_mb: 512,
  cpu_limit: 1,
  network_enabled: false,
  read_only_fs: true,
  timeout_ms: 300000, // 5分钟
};

export const DEFAULT_HALLUCINATION_BREAKER_CONFIG: HallucinationCircuitBreakerConfig = {
  enabled: true,
  similarity_threshold: 0.9,
  window_size: 3,
  max_consecutive_triggers: 3,
};

export const DEFAULT_SHADOW_MODE_CONFIG: ShadowModeConfig = {
  enabled: true,
  sandbox_config: DEFAULT_SANDBOX_CONFIG,
  max_execution_time_ms: 60000,
};

export const DEFAULT_LATS_CONFIG: LATSConfig = {
  enabled: true,
  max_depth: 10,
  backtrack_steps: 5,
  exploration_factor: 1.4,
};

export const DEFAULT_ZERO_TRUST_VAULT_CONFIG: ZeroTrustVaultConfig = {
  enabled: false,
  token_ttl_seconds: 300,
  require_manual_approval: false,
};
