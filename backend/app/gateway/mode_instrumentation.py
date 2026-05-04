"""Gateway boundary ModeInstrumentation helpers.

This module projects request/context metadata into ModeSession and
ModeCallGraph structures. It does not route requests, execute modes, call
M01/M04/RTCM, or mutate Gateway runtime state.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.mode.mode_orchestration_contract import (
    MODES,
    build_mode_call_graph,
    create_mode_session,
    summarize_mode_call_graph,
)


DEFAULT_SAMPLE_PATH = Path(
    r"E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit\R241-4B_GATEWAY_MODE_INSTRUMENTATION_SAMPLE.json"
)


@dataclass(frozen=True)
class ModeInstrumentationEnvelope:
    context_id: Optional[str]
    request_id: Optional[str]
    thread_id: Optional[str]
    mode_session: Dict[str, Any]
    primary_mode: str
    active_modes: List[str]
    instrumentation_only: bool = True
    warnings: List[str] = field(default_factory=list)
    mode_call_graph: Optional[Dict[str, Any]] = None
    selected_mode_hint: Optional[str] = None


def infer_primary_mode_hint(
    payload: Optional[Dict[str, Any]] = None,
    context_envelope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Infer a non-binding primary mode hint from request metadata."""
    payload_dict = _as_dict(payload)
    context_dict = _as_dict(context_envelope)
    warnings: List[str] = []

    explicit_hint = _first_present(
        payload_dict,
        context_dict,
        keys=[
            "selected_mode_hint",
            "selected_mode",
            "requested_mode_hint",
            "requested_mode",
            "primary_mode",
            "mode",
        ],
    )
    if explicit_hint:
        normalized = _normalize_mode_hint(str(explicit_hint), warnings)
        return {
            "primary_mode": normalized,
            "confidence": 0.95 if normalized != "unknown" else 0.35,
            "evidence": [f"explicit_mode_hint:{explicit_hint}"],
            "warnings": warnings,
        }

    text = _searchable_text(payload_dict, context_dict)
    checks = [
        ("roundtable", 0.86, ["roundtable", "rtcm", "council", "debate", "meeting"]),
        ("workflow", 0.82, ["workflow", "dag", "pipeline", "automation", "sop"]),
        ("autonomous_agent", 0.8, ["autonomous", "agent", "long-running", "long running", "delegate"]),
        ("search", 0.78, ["search", "research", "evidence", "citation", "find"]),
        ("task", 0.76, ["task", "execute", "fix", "build", "test", "implement"]),
    ]
    for mode, confidence, keywords in checks:
        matched = [keyword for keyword in keywords if keyword in text]
        if matched:
            return {
                "primary_mode": mode,
                "confidence": confidence,
                "evidence": [f"keyword:{keyword}" for keyword in matched],
                "warnings": warnings,
            }

    return {
        "primary_mode": "direct_answer",
        "confidence": 0.25,
        "evidence": [],
        "warnings": ["low_confidence_mode_hint"],
    }


def create_gateway_mode_instrumentation(
    payload: Optional[Dict[str, Any]] = None,
    context_envelope: Optional[Dict[str, Any]] = None,
    thread_id: Optional[str] = None,
    selected_mode_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Create Gateway mode metadata without changing run behavior."""
    payload_dict = _as_dict(payload)
    context_dict = _as_dict(context_envelope or payload_dict.get("context_envelope"))
    hint_payload = dict(payload_dict)
    if selected_mode_hint is not None:
        hint_payload["selected_mode_hint"] = selected_mode_hint
    hint = infer_primary_mode_hint(hint_payload, context_dict)
    primary_mode = hint["primary_mode"]
    active_modes = _collect_active_modes(payload_dict, context_dict, primary_mode)
    warnings = list(hint.get("warnings") or [])

    session = create_mode_session(
        primary_mode=primary_mode,
        active_modes=active_modes,
        context_id=context_dict.get("context_id"),
        request_id=context_dict.get("request_id"),
        thread_id=thread_id or context_dict.get("thread_id") or payload_dict.get("thread_id"),
        owner_system="gateway_mode_instrumentation",
    )
    warnings.extend(session.get("warnings") or [])
    envelope = ModeInstrumentationEnvelope(
        context_id=session.get("context_id"),
        request_id=session.get("request_id"),
        thread_id=session.get("thread_id"),
        mode_session=session,
        mode_call_graph=None,
        selected_mode_hint=selected_mode_hint or payload_dict.get("selected_mode_hint"),
        primary_mode=session.get("primary_mode", "unknown"),
        active_modes=list(session.get("active_modes") or []),
        instrumentation_only=True,
        warnings=_dedupe(warnings),
    )
    return asdict(envelope)


def attach_mode_metadata_to_context(
    context_envelope: Dict[str, Any],
    mode_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a context copy with optional mode metadata attached."""
    context_copy = copy.deepcopy(_as_dict(context_envelope))
    metadata_copy = copy.deepcopy(mode_metadata or {})
    mode_session = metadata_copy.get("mode_session") or {}
    context_copy["mode_session_id"] = mode_session.get("mode_session_id")
    context_copy["primary_mode"] = metadata_copy.get("primary_mode") or mode_session.get("primary_mode")
    context_copy["active_modes"] = list(metadata_copy.get("active_modes") or mode_session.get("active_modes") or [])
    context_copy["mode_metadata"] = metadata_copy
    context_copy["mode_instrumentation_ref"] = mode_session.get("mode_session_id")
    return context_copy


def build_gateway_mode_call_graph_projection(
    mode_metadata: Dict[str, Any],
    invocations: Optional[List[Dict[str, Any]]] = None,
    results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a ModeCallGraph projection from Gateway metadata only."""
    metadata = _as_dict(mode_metadata)
    session = metadata.get("mode_session") or {}
    if not session:
        session = create_mode_session(
            primary_mode=metadata.get("primary_mode", "unknown"),
            active_modes=list(metadata.get("active_modes") or []),
            context_id=metadata.get("context_id"),
            request_id=metadata.get("request_id"),
            thread_id=metadata.get("thread_id"),
            owner_system="gateway_mode_instrumentation",
        )
    graph = build_mode_call_graph(session, list(invocations or []), list(results or []))
    metadata["mode_call_graph"] = graph
    return graph


def generate_gateway_mode_instrumentation_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Write a report-directory sample, not production runtime state."""
    payload = {
        "messages": [{"role": "user", "content": "Fix the failing test and search for evidence first."}],
        "active_modes": ["task", "search"],
    }
    context = {
        "context_id": "ctx-r241-4b-sample",
        "request_id": "req-r241-4b-sample",
        "thread_id": "thread-r241-4b-sample",
        "source_system": "gateway",
    }
    hint = infer_primary_mode_hint(payload, context)
    metadata = create_gateway_mode_instrumentation(payload, context, thread_id=context["thread_id"])
    attached_context = attach_mode_metadata_to_context(context, metadata)
    graph = build_gateway_mode_call_graph_projection(metadata)
    summary = summarize_mode_call_graph(graph)
    warnings = _dedupe(
        list(hint.get("warnings") or [])
        + list(metadata.get("warnings") or [])
        + list(graph.get("warnings") or [])
    )
    result = {
        "payload": payload,
        "context_envelope": context,
        "inferred_primary_mode": hint,
        "mode_instrumentation": metadata,
        "attached_context_copy": attached_context,
        "mode_call_graph_projection": graph,
        "summary": summary,
        "warnings": warnings,
        "generated_at": _now(),
    }
    path = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(path), **result}


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if hasattr(value, "to_dict"):
        try:
            converted = value.to_dict()
            return copy.deepcopy(converted if isinstance(converted, dict) else {})
        except Exception:
            return {}
    return {}


def _collect_active_modes(
    payload: Dict[str, Any],
    context: Dict[str, Any],
    primary_mode: str,
) -> List[str]:
    raw_modes: List[Any] = [primary_mode]
    for source in (payload, context):
        value = source.get("active_modes")
        if isinstance(value, list):
            raw_modes.extend(value)
        elif isinstance(value, str):
            raw_modes.append(value)
    warnings: List[str] = []
    return _dedupe([_normalize_mode_hint(str(mode), warnings) for mode in raw_modes])


def _first_present(*sources: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value is not None and value != "":
                return value
    return None


def _normalize_mode_hint(mode: str, warnings: List[str]) -> str:
    normalized = str(mode or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "agent": "autonomous_agent",
        "autonomous": "autonomous_agent",
        "rtcm": "roundtable",
        "council": "roundtable",
        "meeting": "roundtable",
        "answer": "direct_answer",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in MODES:
        return normalized
    warnings.append(f"invalid_mode_hint:{mode}")
    return "unknown"


def _searchable_text(*sources: Dict[str, Any]) -> str:
    parts: List[str] = []
    for source in sources:
        parts.append(_flatten_text(source))
    return " ".join(parts).lower()


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join([str(key) + " " + _flatten_text(item) for key, item in value.items()])
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
