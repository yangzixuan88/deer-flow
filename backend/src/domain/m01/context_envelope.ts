/**
 * ContextEnvelope — R240-4 Minimal TypeScript Wrapper
 * ====================================================
 * 与 Python backend/app/gateway/context.py 保持字段对齐。
 * 所有字段 optional — 向后兼容旧请求。
 */

export interface ContextEnvelopeLike {
  context_id?: string;
  request_id?: string;
  session_id?: string;
  thread_id?: string;
  run_id?: string;
  task_id?: string;
  workflow_id?: string;
  dag_id?: string;
  rtcm_session_id?: string;
  rtcm_project_id?: string;
  governance_trace_id?: string;
  governance_decision_id?: string;
  candidate_id?: string;
  asset_id?: string;
  checkpoint_id?: string;
  parent_checkpoint_id?: string;
  memory_scope?: string;
  runtime_artifact_root?: string;
  parent_context_id?: string;
  created_at?: string;
  updated_at?: string;
  source_system?: string;
  owner_system?: string;
  task_origin?: string;
  truth_scope?: string;
  state_scope?: string;
  execution_permissions?: Record<string, any>;
  [key: string]: any;
}

export enum RelationType {
  DERIVED_FROM = 'derived_from',
  DELEGATES_TO = 'delegates_to',
  EXECUTES_AS = 'executes_as',
  RECORDS_OUTCOME_FOR = 'records_outcome_for',
  WRITES_MEMORY_FOR = 'writes_memory_for',
  PROMOTES_ASSET_FOR = 'promotes_asset_for',
  BELONGS_TO_SESSION = 'belongs_to_session',
  BELONGS_TO_THREAD = 'belongs_to_thread',
  BELONGS_TO_WORKFLOW = 'belongs_to_workflow',
  BELONGS_TO_RTCM = 'belongs_to_rtcm',
  SUPERSEDES = 'supersedes',
  INTERCEPTS = 'intercepts',
  SPAWNS = 'spawns',
}

export interface ContextLink {
  link_id: string;
  from_context_id: string;
  to_context_id: string;
  relation_type: string;
  source_system: string;
  confidence?: number;
  metadata?: Record<string, any>;
  created_at: string;
}

export enum TruthScope {
  SANDBOX = 'sandbox',
  PRODUCTION = 'production',
  GOVERNANCE = 'governance',
  MEMORY = 'memory',
  UNKNOWN = 'unknown',
}

export enum StateScope {
  IDLE = 'idle',
  RUNNING = 'running',
  INTERRUPTED = 'interrupted',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export function generateContextId(): string {
  return crypto.randomUUID();
}

export function generateRequestId(): string {
  return crypto.randomUUID();
}

export function generateLinkId(): string {
  return crypto.randomUUID();
}

export function ensureContextEnvelope(
  payload: Record<string, any> | null | undefined,
  sourceSystem = 'm01',
  ownerSystem = 'm01',
): ContextEnvelopeLike {
  if (!payload) payload = {};

  const existing = payload['context_envelope'];
  if (existing) {
    if (typeof existing === 'object') {
      return existing as ContextEnvelopeLike;
    }
  }

  return {
    context_id: generateContextId(),
    request_id: (payload as any)?.requestId || generateRequestId(),
    session_id: (payload as any)?.sessionId || undefined,
    thread_id: (payload as any)?.thread_id || undefined,
    run_id: undefined,
    task_id: undefined,
    source_system: sourceSystem,
    owner_system: ownerSystem,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    truth_scope: TruthScope.UNKNOWN,
    state_scope: StateScope.IDLE,
  };
}

export function injectEnvelopeIntoContext(
  context: Record<string, any> | null | undefined,
  envelope: ContextEnvelopeLike,
): Record<string, any> {
  if (!context) context = {};
  context['context_envelope'] = envelope;
  return context;
}

export function extractEnvelopeFromContext(
  context: Record<string, any> | null | undefined,
): ContextEnvelopeLike | null {
  if (!context) return null;
  const raw = context['context_envelope'];
  if (!raw) return null;
  if (typeof raw === 'object') return raw as ContextEnvelopeLike;
  return null;
}
