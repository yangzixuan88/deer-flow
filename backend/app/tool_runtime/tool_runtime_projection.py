"""ToolRuntime to Gateway/ModeInvocation projection helpers.

This module links planned tool events to Gateway context and mode metadata.
It does not execute tools, enforce permissions, call Gateway runs, or write
production runtime state.
"""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.gateway.mode_instrumentation import create_gateway_mode_instrumentation
from app.mode.mode_orchestration_contract import create_mode_invocation
from app.tool_runtime.tool_runtime_contract import (
    create_tool_execution_event,
    summarize_tool_events,
    validate_tool_event_policy,
)


DEFAULT_SAMPLE_PATH = Path(
    r"E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit\R241-5B_TOOL_RUNTIME_GATEWAY_MODE_SAMPLE.json"
)


def link_tool_event_to_mode_invocation(
    tool_event: Dict[str, Any],
    mode_invocation: Optional[Dict[str, Any]] = None,
    mode_metadata: Optional[Dict[str, Any]] = None,
    context_envelope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a copy of tool_event linked to mode/context metadata."""
    linked = copy.deepcopy(tool_event or {})
    invocation = _as_dict(mode_invocation)
    metadata = _as_dict(mode_metadata)
    context = _as_dict(context_envelope)
    warnings: List[str] = []

    mode_session = metadata.get("mode_session") or {}
    if invocation:
        linked["mode_invocation_id"] = invocation.get("mode_invocation_id") or linked.get("mode_invocation_id")
        linked["mode_session_id"] = invocation.get("mode_session_id") or linked.get("mode_session_id")
        linked["caller_mode"] = invocation.get("from_mode") or linked.get("caller_mode")
    else:
        warnings.append("missing_mode_invocation")

    linked["mode_session_id"] = linked.get("mode_session_id") or metadata.get("mode_session_id") or mode_session.get("mode_session_id")
    linked["caller_mode"] = linked.get("caller_mode") or metadata.get("primary_mode") or mode_session.get("primary_mode")
    linked["context_id"] = linked.get("context_id") or context.get("context_id") or metadata.get("context_id")
    linked["request_id"] = linked.get("request_id") or context.get("request_id") or metadata.get("request_id")
    linked["thread_id"] = linked.get("thread_id") or context.get("thread_id") or metadata.get("thread_id")

    if not linked.get("context_id"):
        warnings.append("missing_context_id")
    if not linked.get("mode_session_id"):
        warnings.append("missing_mode_session_id")
    if not linked.get("mode_invocation_id"):
        warnings.append("missing_mode_invocation_id")

    linked["warnings"] = _dedupe(list(linked.get("warnings") or []) + warnings)
    return {
        "linked_event": linked,
        "link_summary": {
            "tool_execution_id": linked.get("tool_execution_id"),
            "context_id": linked.get("context_id"),
            "request_id": linked.get("request_id"),
            "thread_id": linked.get("thread_id"),
            "mode_session_id": linked.get("mode_session_id"),
            "mode_invocation_id": linked.get("mode_invocation_id"),
            "caller_mode": linked.get("caller_mode"),
        },
        "warnings": _dedupe(warnings),
    }


def create_contextual_tool_event(
    tool_id: str,
    operation_type: str,
    caller_system: str,
    tool_type: Optional[str] = None,
    mode_invocation: Optional[Dict[str, Any]] = None,
    mode_metadata: Optional[Dict[str, Any]] = None,
    context_envelope: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a planned ToolExecutionEvent with context/mode metadata."""
    metadata_copy = copy.deepcopy(metadata or {})
    if tool_type is not None:
        metadata_copy["tool_type"] = tool_type
    context = _as_dict(context_envelope)
    mode_meta = _as_dict(mode_metadata)
    invocation = _as_dict(mode_invocation)
    mode_session = mode_meta.get("mode_session") or {}

    metadata_copy.setdefault("context_id", context.get("context_id") or mode_meta.get("context_id"))
    metadata_copy.setdefault("request_id", context.get("request_id") or mode_meta.get("request_id"))
    metadata_copy.setdefault("mode_session_id", invocation.get("mode_session_id") or mode_session.get("mode_session_id"))
    metadata_copy.setdefault("mode_invocation_id", invocation.get("mode_invocation_id"))
    metadata_copy.setdefault("caller_mode", invocation.get("from_mode") or mode_meta.get("primary_mode") or mode_session.get("primary_mode"))

    event = create_tool_execution_event(tool_id, operation_type, caller_system, metadata_copy)
    link = link_tool_event_to_mode_invocation(event, invocation or None, mode_meta or None, context or None)
    linked_event = link["linked_event"]
    policy_validation = validate_tool_event_policy(linked_event)
    warnings = _dedupe(list(link.get("warnings") or []) + list(policy_validation.get("warnings") or []))
    return {
        "tool_event": linked_event,
        "policy_validation": policy_validation,
        "warnings": warnings,
    }


def project_tool_events_for_mode_callgraph(
    events: List[Dict[str, Any]],
    mode_call_graph: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Aggregate ToolExecutionEvents by mode/context identifiers."""
    event_copies = [copy.deepcopy(event) for event in events or []]
    by_session = Counter(str(event.get("mode_session_id") or "missing") for event in event_copies)
    by_invocation = Counter(str(event.get("mode_invocation_id") or "missing") for event in event_copies)
    by_caller = Counter(str(event.get("caller_mode") or "missing") for event in event_copies)
    by_risk = Counter(str(event.get("risk_level") or "unknown") for event in event_copies)
    orphan_events = [
        event
        for event in event_copies
        if not event.get("mode_session_id") or not event.get("mode_invocation_id") or not event.get("context_id")
    ]
    high_risk = [
        event
        for event in event_copies
        if event.get("risk_level") in {"level_2_protected_auto", "level_3_confirm_or_archive"}
    ]
    warnings: List[str] = []
    if orphan_events:
        warnings.append("orphan_tool_events_detected")
    if mode_call_graph and not mode_call_graph.get("mode_session_id"):
        warnings.append("mode_call_graph_missing_session")
    return {
        "total_events": len(event_copies),
        "by_mode_session_id": dict(by_session),
        "by_mode_invocation_id": dict(by_invocation),
        "by_caller_mode": dict(by_caller),
        "by_risk_level": dict(by_risk),
        "high_risk_events": high_risk,
        "orphan_tool_events": orphan_events,
        "warnings": warnings,
    }


def project_gateway_tool_runtime(
    payload: Optional[Dict[str, Any]] = None,
    context_envelope: Optional[Dict[str, Any]] = None,
    planned_tool_calls: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Project planned Gateway tool calls into contextual ToolEvents."""
    payload_copy = copy.deepcopy(payload or {})
    context = copy.deepcopy(context_envelope or payload_copy.get("context_envelope") or {})
    mode_metadata = create_gateway_mode_instrumentation(payload_copy, context)
    planned_calls = copy.deepcopy(planned_tool_calls or [])
    tool_events: List[Dict[str, Any]] = []
    validations: List[Dict[str, Any]] = []
    warnings: List[str] = list(mode_metadata.get("warnings") or [])

    for call in planned_calls:
        metadata = copy.deepcopy(call.get("metadata") or {})
        invocation = call.get("mode_invocation")
        if invocation is None and call.get("to_mode"):
            invocation = create_mode_invocation(
                mode_session_id=mode_metadata["mode_session"]["mode_session_id"],
                from_mode=mode_metadata.get("primary_mode", "unknown"),
                to_mode=call.get("to_mode", mode_metadata.get("primary_mode", "unknown")),
                reason="planned_tool_call_projection",
                executor=call.get("executor"),
            )
        projected = create_contextual_tool_event(
            tool_id=call.get("tool_id", "unknown"),
            operation_type=call.get("operation_type", "unknown"),
            caller_system="gateway_tool_runtime_projection",
            tool_type=call.get("tool_type"),
            mode_invocation=invocation,
            mode_metadata=mode_metadata,
            context_envelope=context,
            metadata=metadata,
        )
        tool_events.append(projected["tool_event"])
        validations.append(projected["policy_validation"])
        warnings.extend(projected.get("warnings") or [])

    summary = project_tool_events_for_mode_callgraph(tool_events)
    return {
        "mode_metadata": mode_metadata,
        "tool_events": tool_events,
        "policy_validations": validations,
        "summary": summary,
        "warnings": _dedupe(warnings + summary.get("warnings", [])),
    }


def detect_tool_mode_risks(projection: Dict[str, Any]) -> Dict[str, Any]:
    """Diagnose tool-mode risks without blocking execution."""
    events = [copy.deepcopy(event) for event in projection.get("tool_events") or []]
    validations = projection.get("policy_validations") or []
    validation_by_event = {
        event.get("tool_execution_id"): validation
        for event, validation in zip(events, validations)
    }
    risk_records: List[Dict[str, Any]] = []
    risk_types: List[str] = []

    for event in events:
        event_id = event.get("tool_execution_id")
        validation = validation_by_event.get(event_id, {})
        warnings = set(event.get("warnings") or []) | set(validation.get("warnings") or [])
        risk_level = event.get("risk_level")
        caller_mode = event.get("caller_mode")
        op = event.get("operation_type")

        if risk_level in {"level_2_protected_auto", "level_3_confirm_or_archive"} and (
            not event.get("mode_session_id") or not event.get("mode_invocation_id") or not event.get("context_id")
        ):
            _add_risk(risk_records, risk_types, "high_risk_tool_without_mode_context", event)
        if "level_2_missing_backup" in warnings:
            _add_risk(risk_records, risk_types, "level_2_missing_backup", event)
        if "level_2_missing_rollback" in warnings:
            _add_risk(risk_records, risk_types, "level_2_missing_rollback", event)
        if "level_3_requires_confirmation" in warnings:
            _add_risk(risk_records, risk_types, "level_3_requires_confirmation", event)
        if "root_guard_required_but_missing" in warnings:
            _add_risk(risk_records, risk_types, "root_guard_required_but_missing", event)
        if caller_mode == "autonomous_agent" and risk_level in {"level_2_protected_auto", "level_3_confirm_or_archive"}:
            _add_risk(risk_records, risk_types, "autonomous_agent_high_risk_tool", event)
        if caller_mode == "roundtable" and risk_level in {"level_2_protected_auto", "level_3_confirm_or_archive"}:
            _add_risk(risk_records, risk_types, "roundtable_direct_high_risk_tool", event)
        if op == "prompt_replace" and not event.get("rollback_refs"):
            _add_risk(risk_records, risk_types, "prompt_replace_without_rollback", event)
        if op == "memory_cleanup" and not event.get("quarantine_ref"):
            _add_risk(risk_records, risk_types, "memory_cleanup_without_quarantine", event)
        if op == "asset_elimination" and risk_level == "level_3_confirm_or_archive":
            _add_risk(risk_records, risk_types, "asset_core_elimination_attempt", event)

    return {
        "risk_count": len(risk_records),
        "risk_by_type": dict(Counter(risk_types)),
        "risk_records": risk_records,
        "warnings": _dedupe(list(projection.get("warnings") or [])),
    }


def generate_tool_gateway_mode_projection_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate report sample only; does not execute planned tools."""
    payload = {
        "messages": [{"role": "user", "content": "Use an autonomous agent to implement and test this task."}],
        "active_modes": ["task", "autonomous_agent"],
    }
    context = {
        "context_id": "ctx-r241-5b-sample",
        "request_id": "req-r241-5b-sample",
        "thread_id": "thread-r241-5b-sample",
        "source_system": "gateway",
    }
    planned_tool_calls = [
        {"tool_id": "fs.read", "tool_type": "file_system", "operation_type": "read_file", "metadata": {"target_path": "README.md"}},
        {"tool_id": "claude.code", "tool_type": "claude_code", "operation_type": "claude_code_call", "metadata": {"target_path": "backend/app/foo.py", "root_guard_passed": True}},
        {
            "tool_id": "fs.config",
            "tool_type": "file_system",
            "operation_type": "modify_config",
            "metadata": {
                "target_path": "package.json",
                "backup_refs": ["backup/package.json.bak"],
                "rollback_refs": ["rollback/package-json.patch"],
                "root_guard_passed": True,
            },
        },
        {"tool_id": "fs.delete", "tool_type": "file_system", "operation_type": "delete_file", "metadata": {"target_path": "important.md"}},
        {"tool_id": "prompt.replace", "tool_type": "file_system", "operation_type": "prompt_replace", "metadata": {"target_path": "prompts/SOUL.md"}},
    ]
    projection = project_gateway_tool_runtime(payload, context, planned_tool_calls)
    risks = detect_tool_mode_risks(projection)
    result = {
        "payload": payload,
        "context_envelope": context,
        "planned_tool_calls": planned_tool_calls,
        "mode_metadata": projection["mode_metadata"],
        "contextual_tool_events": projection["tool_events"],
        "policy_validations": projection["policy_validations"],
        "risk_signals": risks,
        "summary": projection["summary"],
        "warnings": _dedupe(list(projection.get("warnings") or []) + list(risks.get("warnings") or [])),
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


def _add_risk(records: List[Dict[str, Any]], types: List[str], risk_type: str, event: Dict[str, Any]) -> None:
    types.append(risk_type)
    records.append(
        {
            "risk_type": risk_type,
            "tool_execution_id": event.get("tool_execution_id"),
            "tool_id": event.get("tool_id"),
            "operation_type": event.get("operation_type"),
            "risk_level": event.get("risk_level"),
            "caller_mode": event.get("caller_mode"),
            "mode_session_id": event.get("mode_session_id"),
            "mode_invocation_id": event.get("mode_invocation_id"),
            "context_id": event.get("context_id"),
        }
    )


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
