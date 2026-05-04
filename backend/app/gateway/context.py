"""
ContextEnvelope — R240-4 Minimal Wrapper
========================================
不承载执行状态，只负责携带跨系统上下文 ID 包。

约束（绝对禁止改变）：
- 任何 routing / execution 逻辑
- 任何现有的 thread_id / run_id / session_id 行为
- 任何 governance outcome 语义
- 任何 request/response 结构

设计原则：只包裹，不抢权。
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Path constants
# ─────────────────────────────────────────────────────────────────────────────

# Derive DEERFLOW_RUNTIME_ROOT — mirrors runtime_paths.ts logic
_BACKEND_DIR = Path(__file__).parent.parent.parent  # app/gateway/context.py → app → backend
_DEERFLOW_ROOT = os.environ.get(
    "DEERFLOW_RUNTIME_ROOT",
    _BACKEND_DIR / ".deerflow",
)
_CONTEXT_DIR = _DEERFLOW_ROOT / "context"
_CONTEXT_LINKS_FILE = _CONTEXT_DIR / "context_links.jsonl"


# ─────────────────────────────────────────────────────────────────────────────
# ID generators
# ─────────────────────────────────────────────────────────────────────────────

def generate_context_id() -> str:
    return str(uuid.uuid4())


def generate_request_id() -> str:
    return str(uuid.uuid4())


def generate_link_id() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# ContextEnvelope — minimal dataclass
# ─────────────────────────────────────────────────────────────────────────────

class TruthScope:
    SANDBOX = "sandbox"
    PRODUCTION = "production"
    GOVERNANCE = "governance"
    MEMORY = "memory"
    UNKNOWN = "unknown"


class StateScope:
    IDLE = "idle"
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContextEnvelope:
    """
    统一上下文包 — 跨 M01/M04/RTCM/Gateway/DeerFlow/Governance 的上下文传递载体。

    最小字段（必须）：context_id, request_id, created_at, source_system
    所有其他字段 optional，默认 None。

    约束：
    - 不承载执行状态，只携带 ID 关系
    - 不修改任何现有业务逻辑
    - 所有字段 optional，向后兼容旧请求
    """

    def __init__(
        self,
        context_id: str | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        workflow_id: str | None = None,
        dag_id: str | None = None,
        rtcm_session_id: str | None = None,
        rtcm_project_id: str | None = None,
        governance_trace_id: str | None = None,
        governance_decision_id: str | None = None,
        candidate_id: str | None = None,
        asset_id: str | None = None,
        checkpoint_id: str | None = None,
        parent_checkpoint_id: str | None = None,
        memory_scope: str | None = None,
        runtime_artifact_root: str | None = None,
        parent_context_id: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        source_system: str | None = None,
        owner_system: str | None = None,
        task_origin: str | None = None,
        truth_scope: str | None = None,
        state_scope: str | None = None,
        execution_permissions: dict | None = None,
        # Extra fields passthrough
        **extra: Any,
    ):
        self.context_id = context_id or generate_context_id()
        self.request_id = request_id or generate_request_id()
        self.session_id = session_id
        self.thread_id = thread_id
        self.run_id = run_id
        self.task_id = task_id
        self.workflow_id = workflow_id
        self.dag_id = dag_id
        self.rtcm_session_id = rtcm_session_id
        self.rtcm_project_id = rtcm_project_id
        self.governance_trace_id = governance_trace_id
        self.governance_decision_id = governance_decision_id
        self.candidate_id = candidate_id
        self.asset_id = asset_id
        self.checkpoint_id = checkpoint_id
        self.parent_checkpoint_id = parent_checkpoint_id
        self.memory_scope = memory_scope
        self.runtime_artifact_root = runtime_artifact_root
        self.parent_context_id = parent_context_id
        self.created_at = created_at or datetime.now(UTC).isoformat()
        self.updated_at = updated_at or datetime.now(UTC).isoformat()
        self.source_system = source_system or "gateway"
        self.owner_system = owner_system or "gateway"
        self.task_origin = task_origin
        self.truth_scope = truth_scope or TruthScope.UNKNOWN
        self.state_scope = state_scope or StateScope.IDLE
        self.execution_permissions = execution_permissions or {}
        # Capture extra passthrough fields
        self._extra = extra

    def to_dict(self) -> dict:
        return {
            "context_id": self.context_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "thread_id": self.thread_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "dag_id": self.dag_id,
            "rtcm_session_id": self.rtcm_session_id,
            "rtcm_project_id": self.rtcm_project_id,
            "governance_trace_id": self.governance_trace_id,
            "governance_decision_id": self.governance_decision_id,
            "candidate_id": self.candidate_id,
            "asset_id": self.asset_id,
            "checkpoint_id": self.checkpoint_id,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "memory_scope": self.memory_scope,
            "runtime_artifact_root": self.runtime_artifact_root,
            "parent_context_id": self.parent_context_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_system": self.source_system,
            "owner_system": self.owner_system,
            "task_origin": self.task_origin,
            "truth_scope": self.truth_scope,
            "state_scope": self.state_scope,
            "execution_permissions": self.execution_permissions,
            **self._extra,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ContextEnvelope:
        if data is None:
            return cls()
        known_keys = {
            "context_id", "request_id", "session_id", "thread_id", "run_id",
            "task_id", "workflow_id", "dag_id", "rtcm_session_id", "rtcm_project_id",
            "governance_trace_id", "governance_decision_id", "candidate_id", "asset_id",
            "checkpoint_id", "parent_checkpoint_id", "memory_scope", "runtime_artifact_root",
            "parent_context_id", "created_at", "updated_at", "source_system", "owner_system",
            "task_origin", "truth_scope", "state_scope", "execution_permissions",
        }
        known = {k: v for k, v in data.items() if k in known_keys}
        extra = {k: v for k, v in data.items() if k not in known_keys}
        return cls(**known, **extra)

    def __repr__(self) -> str:
        return (
            f"ContextEnvelope(context_id={self.context_id[:8]}..., "
            f"request_id={self.request_id[:8]}..., "
            f"thread_id={self.thread_id[:8] if self.thread_id else None}..., "
            f"run_id={self.run_id[:8] if self.run_id else None}...)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# ContextLink — relationship record
# ─────────────────────────────────────────────────────────────────────────────

class RelationType:
    DERIVED_FROM = "derived_from"
    DELEGATES_TO = "delegates_to"
    EXECUTES_AS = "executes_as"
    RECORDS_OUTCOME_FOR = "records_outcome_for"
    WRITES_MEMORY_FOR = "writes_memory_for"
    PROMOTES_ASSET_FOR = "promotes_asset_for"
    BELONGS_TO_SESSION = "belongs_to_session"
    BELONGS_TO_THREAD = "belongs_to_thread"
    BELONGS_TO_WORKFLOW = "belongs_to_workflow"
    BELONGS_TO_RTCM = "belongs_to_rtcm"
    SUPERSEDES = "supersedes"
    INTERCEPTS = "intercepts"
    SPAWNS = "spawns"


class ContextLink:
    """表达不同系统 ID 之间关系的链接记录。"""

    def __init__(
        self,
        link_id: str | None = None,
        from_context_id: str | None = None,
        to_context_id: str | None = None,
        relation_type: str | None = None,
        source_system: str | None = None,
        confidence: float = 1.0,
        metadata: dict | None = None,
        created_at: str | None = None,
    ):
        self.link_id = link_id or generate_link_id()
        self.from_context_id = from_context_id
        self.to_context_id = to_context_id
        self.relation_type = relation_type
        self.source_system = source_system or "gateway"
        self.confidence = confidence
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now(UTC).isoformat()

    def to_dict(self) -> dict:
        return {
            "link_id": self.link_id,
            "from_context_id": self.from_context_id,
            "to_context_id": self.to_context_id,
            "relation_type": self.relation_type,
            "source_system": self.source_system,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ContextLink:
        if data is None:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in {
            "link_id", "from_context_id", "to_context_id", "relation_type",
            "source_system", "confidence", "metadata", "created_at",
        }})


# ─────────────────────────────────────────────────────────────────────────────
# ContextLink storage (jsonl append-only)
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_context_dir() -> Path:
    try:
        _CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"[ContextEnvelope] Cannot create context dir {_CONTEXT_DIR}: {e}")
    return _CONTEXT_DIR


def append_context_link(link: ContextLink) -> bool:
    """
    Append a ContextLink to the jsonl file.
    Returns True on success, False on failure.
    Failure is non-fatal — logs warning, does not raise.
    """
    try:
        _ensure_context_dir()
        record = link.to_dict()
        line = json.dumps(record, ensure_ascii=False, default=str)
        with open(_CONTEXT_LINKS_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        logger.debug(f"[ContextEnvelope] ContextLink appended: {link.link_id}")
        return True
    except Exception as e:
        logger.warning(f"[ContextEnvelope] Failed to append ContextLink: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Core helpers
# ─────────────────────────────────────────────────────────────────────────────

def ensure_context_envelope(
    payload: dict | None,
    source_system: str = "gateway",
    owner_system: str = "gateway",
) -> ContextEnvelope:
    """
    从 payload 中提取或生成 ContextEnvelope。

    如果 payload 中已有 context_envelope（dict 或 ContextEnvelope 实例），
    则校验并保留（不覆盖已有字段）。

    如果没有，则生成最小 ContextEnvelope。

    约束：
    - 不修改 payload 本身
    - 不改变任何现有业务逻辑
    - 始终返回有效 ContextEnvelope（never None）
    """
    if payload is None:
        payload = {}

    # Case 1: payload 中已有 context_envelope
    existing = payload.get("context_envelope")
    if existing is not None:
        if isinstance(existing, ContextEnvelope):
            return existing
        if isinstance(existing, dict):
            try:
                return ContextEnvelope.from_dict(existing)
            except Exception:
                logger.warning("[ContextEnvelope] Invalid context_envelope in payload, regenerating")
                return ContextEnvelope(source_system=source_system, owner_system=owner_system)

    # Case 2: 从顶级字段提取（如 thread_id, run_id 已在 payload 顶层）
    thread_id = payload.get("thread_id")
    run_id = payload.get("run_id")
    session_id = payload.get("session_id")
    request_id = payload.get("request_id")
    task_id = payload.get("task_id")

    # Case 3: 没有 envelope，生成最小 envelope
    envelope = ContextEnvelope(
        source_system=source_system,
        owner_system=owner_system,
        request_id=request_id,
        session_id=session_id,
        thread_id=thread_id,
        run_id=run_id,
        task_id=task_id,
    )
    return envelope


def inject_envelope_into_context(
    context: dict | None,
    envelope: ContextEnvelope,
) -> dict:
    """
    将 envelope 注入到 context dict 中（不修改原始 context 结构）。
    context 可能是 RunCreateRequest.context 字段。

    不返回值，直接修改传入的 dict（调用方需自行复制保护）。
    """
    if context is None:
        context = {}
    context["context_envelope"] = envelope.to_dict()
    return context


def extract_envelope_from_context(context: dict | None) -> ContextEnvelope | None:
    """从 context dict 中提取 ContextEnvelope（如果存在）。"""
    if context is None:
        return None
    raw = context.get("context_envelope")
    if raw is None:
        return None
    if isinstance(raw, ContextEnvelope):
        return raw
    if isinstance(raw, dict):
        try:
            return ContextEnvelope.from_dict(raw)
        except Exception:
            return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Logging helper — safe, no sensitive data
# ─────────────────────────────────────────────────────────────────────────────

def envelope_summary(envelope: ContextEnvelope) -> str:
    """返回可用于日志的 envelope 摘要（不泄露敏感内容）。"""
    def _mask(s: str | None, chars: int = 8) -> str:
        if s is None:
            return "None"
        return f"{s[:chars]}..."
    return (
        f"context_id={_mask(envelope.context_id)} "
        f"request_id={_mask(envelope.request_id)} "
        f"thread_id={_mask(envelope.thread_id)} "
        f"run_id={_mask(envelope.run_id)} "
        f"source={envelope.source_system}"
    )
