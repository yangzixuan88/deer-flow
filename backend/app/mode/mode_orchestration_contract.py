"""Read-only/append-only ModeInvocation and ModeCallGraph instrumentation.

This module records mode relationships as data structures only. It does not
route requests, execute tools, switch modes, or modify M01/M04/RTCM/Gateway.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


MODES = {
    "search",
    "task",
    "workflow",
    "autonomous_agent",
    "roundtable",
    "direct_answer",
    "clarification",
    "governance_review",
    "mixed_mode",
    "unknown",
}

INVOCATION_STATUSES = {
    "planned",
    "started",
    "completed",
    "failed",
    "skipped",
    "cancelled",
}

RETURN_POLICIES = {
    "return_to_parent",
    "switch_primary_mode",
    "no_return",
    "user_decides",
}

RESULT_TYPES = {
    "evidence_summary",
    "execution_result",
    "verification_result",
    "verdict",
    "plan",
    "artifact",
    "followup",
    "clarification",
    "error",
    "unknown",
}

DEFAULT_SAMPLE_PATH = Path(
    r"E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit\R241-4A_MODE_CALLGRAPH_RUNTIME_SAMPLE.json"
)


@dataclass(frozen=True)
class ModeSession:
    mode_session_id: str
    primary_mode: str
    active_modes: List[str]
    status: str
    owner_system: str
    created_at: str
    updated_at: str
    warnings: List[str]
    context_id: Optional[str] = None
    request_id: Optional[str] = None
    thread_id: Optional[str] = None


@dataclass(frozen=True)
class ModeInvocation:
    mode_invocation_id: str
    mode_session_id: str
    from_mode: str
    to_mode: str
    reason: str
    return_policy: str
    requires_user_confirmation: bool
    status: str
    warnings: List[str]
    parent_context_id: Optional[str] = None
    child_context_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    result_ref: Optional[str] = None
    executor: Optional[str] = None


@dataclass(frozen=True)
class ModeResult:
    mode_result_id: str
    mode_invocation_id: str
    from_mode: str
    to_mode: str
    result_type: str
    output_refs: List[str]
    truth_event_refs: List[str]
    state_event_refs: List[str]
    asset_candidate_refs: List[str]
    memory_refs: List[str]
    created_at: str
    warnings: List[str]


@dataclass(frozen=True)
class ModeCallGraph:
    mode_session_id: str
    primary_mode: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    invocations: List[Dict[str, Any]]
    results: List[Dict[str, Any]]
    created_at: str
    updated_at: str
    warnings: List[str]


def create_mode_session(
    primary_mode: str,
    active_modes: Optional[List[str]] = None,
    context_id: Optional[str] = None,
    request_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    owner_system: str = "mode_instrumentation",
) -> Dict[str, Any]:
    warnings: List[str] = []
    normalized_primary = _normalize_mode(primary_mode, warnings, "primary_mode")
    modes = [normalized_primary] + list(active_modes or [])
    normalized_active = _dedupe([_normalize_mode(mode, warnings, "active_mode") for mode in modes])
    now = _now()
    return asdict(
        ModeSession(
            mode_session_id=f"modesess_{uuid4().hex}",
            context_id=context_id,
            request_id=request_id,
            thread_id=thread_id,
            primary_mode=normalized_primary,
            active_modes=normalized_active,
            status="started",
            owner_system=owner_system,
            created_at=now,
            updated_at=now,
            warnings=_dedupe(warnings),
        )
    )


def create_mode_invocation(
    mode_session_id: str,
    from_mode: str,
    to_mode: str,
    reason: str,
    return_policy: str = "return_to_parent",
    requires_user_confirmation: bool = False,
    executor: Optional[str] = None,
    parent_context_id: Optional[str] = None,
    child_context_id: Optional[str] = None,
) -> Dict[str, Any]:
    warnings: List[str] = []
    normalized_from = _normalize_mode(from_mode, warnings, "from_mode")
    normalized_to = _normalize_mode(to_mode, warnings, "to_mode")
    normalized_return_policy = _normalize_return_policy(return_policy, warnings)
    return asdict(
        ModeInvocation(
            mode_invocation_id=f"modeinv_{uuid4().hex}",
            mode_session_id=mode_session_id,
            from_mode=normalized_from,
            to_mode=normalized_to,
            reason=reason or "",
            parent_context_id=parent_context_id,
            child_context_id=child_context_id,
            return_policy=normalized_return_policy,
            requires_user_confirmation=bool(requires_user_confirmation),
            status="planned",
            started_at=None,
            finished_at=None,
            result_ref=None,
            executor=executor,
            warnings=_dedupe(warnings),
        )
    )


def complete_mode_invocation(
    invocation: Dict[str, Any],
    result_type: str,
    output_refs: Optional[List[str]] = None,
    truth_event_refs: Optional[List[str]] = None,
    state_event_refs: Optional[List[str]] = None,
    asset_candidate_refs: Optional[List[str]] = None,
    memory_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    warnings = list(invocation.get("warnings") or [])
    normalized_result_type = _normalize_result_type(result_type, warnings)
    mode_result_id = f"moderes_{uuid4().hex}"
    now = _now()
    updated_invocation = dict(invocation)
    updated_invocation["status"] = "completed"
    updated_invocation["finished_at"] = now
    updated_invocation["result_ref"] = mode_result_id
    updated_invocation["warnings"] = _dedupe(warnings)
    mode_result = asdict(
        ModeResult(
            mode_result_id=mode_result_id,
            mode_invocation_id=str(invocation.get("mode_invocation_id")),
            from_mode=str(invocation.get("from_mode", "unknown")),
            to_mode=str(invocation.get("to_mode", "unknown")),
            result_type=normalized_result_type,
            output_refs=list(output_refs or []),
            truth_event_refs=list(truth_event_refs or []),
            state_event_refs=list(state_event_refs or []),
            asset_candidate_refs=list(asset_candidate_refs or []),
            memory_refs=list(memory_refs or []),
            created_at=now,
            warnings=_dedupe(warnings),
        )
    )
    return {"updated_invocation": updated_invocation, "mode_result": mode_result}


def build_mode_call_graph(
    session: Dict[str, Any],
    invocations: List[Dict[str, Any]],
    results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    results = results or []
    warnings = list(session.get("warnings") or [])
    primary_mode = session.get("primary_mode", "unknown")
    node_modes = {primary_mode}
    edges: List[Dict[str, Any]] = []

    for invocation in invocations:
        node_modes.add(invocation.get("from_mode", "unknown"))
        node_modes.add(invocation.get("to_mode", "unknown"))
        edges.append(
            {
                "edge_id": f"edge_{invocation.get('mode_invocation_id')}",
                "from_mode": invocation.get("from_mode", "unknown"),
                "to_mode": invocation.get("to_mode", "unknown"),
                "mode_invocation_id": invocation.get("mode_invocation_id"),
                "return_policy": invocation.get("return_policy"),
                "executor": invocation.get("executor"),
                "status": invocation.get("status"),
            }
        )
        policy = validate_mode_invocation_policy(invocation)
        warnings.extend(policy.get("warnings") or [])

    nodes = [
        {
            "mode": mode,
            "is_primary": mode == primary_mode,
            "is_active": mode in set(session.get("active_modes") or []),
        }
        for mode in sorted(node_modes)
    ]
    now = _now()
    return asdict(
        ModeCallGraph(
            mode_session_id=session.get("mode_session_id"),
            primary_mode=primary_mode,
            nodes=nodes,
            edges=edges,
            invocations=list(invocations),
            results=list(results),
            created_at=session.get("created_at") or now,
            updated_at=now,
            warnings=_dedupe(warnings),
        )
    )


def validate_mode_invocation_policy(invocation: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    required_followups: List[str] = []
    from_mode = invocation.get("from_mode")
    to_mode = invocation.get("to_mode")
    return_policy = invocation.get("return_policy")
    reason = invocation.get("reason")

    if from_mode not in MODES or to_mode not in MODES or from_mode == "unknown" or to_mode == "unknown":
        warnings.append("invalid_mode")
        required_followups.append("review_mode_values")
    if to_mode == "roundtable" and not invocation.get("executor"):
        warnings.append("roundtable_executor_missing_when_to_mode_roundtable")
        required_followups.append("set_roundtable_executor_or_confirm_manual_roundtable")
    if not return_policy:
        warnings.append("child_mode_without_return_policy")
        required_followups.append("set_return_policy")
    elif return_policy not in RETURN_POLICIES:
        warnings.append("unknown_return_policy")
        required_followups.append("review_return_policy")
    if return_policy == "switch_primary_mode" and not reason:
        warnings.append("switch_primary_mode_requires_reason")
        required_followups.append("record_primary_mode_switch_reason")
    if to_mode == "autonomous_agent" and invocation.get("requires_user_confirmation"):
        warnings.append("autonomous_agent_high_risk_requires_review")
        required_followups.append("route_high_risk_autonomous_agent_to_review")
    if to_mode == "governance_review" and not (
        invocation.get("parent_context_id") or invocation.get("child_context_id")
    ):
        warnings.append("governance_review_requires_context")
        required_followups.append("attach_context_id")
    if from_mode == "clarification" and to_mode == "autonomous_agent":
        warnings.append("clarification_should_not_call_autonomous_agent")
        required_followups.append("return_to_user_or_task_before_autonomous_agent")

    return {
        "allowed": not warnings,
        "warnings": _dedupe(warnings),
        "required_followups": _dedupe(required_followups),
    }


def summarize_mode_call_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    edges = graph.get("edges") or []
    invocations = graph.get("invocations") or []
    return {
        "mode_session_id": graph.get("mode_session_id"),
        "primary_mode": graph.get("primary_mode"),
        "active_modes": sorted({node["mode"] for node in graph.get("nodes", []) if node.get("is_active")}),
        "node_count": len(graph.get("nodes") or []),
        "edge_count": len(edges),
        "by_from_mode": dict(Counter(edge.get("from_mode", "unknown") for edge in edges)),
        "by_to_mode": dict(Counter(edge.get("to_mode", "unknown") for edge in edges)),
        "roundtable_invocation_count": sum(1 for invocation in invocations if invocation.get("to_mode") == "roundtable"),
        "autonomous_agent_invocation_count": sum(1 for invocation in invocations if invocation.get("to_mode") == "autonomous_agent"),
        "warnings": graph.get("warnings") or [],
    }


def generate_mode_callgraph_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    session = create_mode_session("task", active_modes=["search", "roundtable", "workflow", "autonomous_agent"])
    invocations = [
        create_mode_invocation(session["mode_session_id"], "task", "search", "collect evidence"),
        create_mode_invocation(session["mode_session_id"], "task", "roundtable", "multi-party review", executor="rtcm"),
        create_mode_invocation(session["mode_session_id"], "roundtable", "search", "verify claims"),
        create_mode_invocation(session["mode_session_id"], "roundtable", "task", "create followup task"),
        create_mode_invocation(session["mode_session_id"], "workflow", "autonomous_agent", "delegate bounded execution"),
    ]
    completed = [
        complete_mode_invocation(invocations[0], "evidence_summary", output_refs=["sample://search-evidence"]),
        complete_mode_invocation(invocations[1], "verdict", output_refs=["sample://rtcm-verdict"]),
    ]
    updated_invocations = [completed[0]["updated_invocation"], completed[1]["updated_invocation"]] + invocations[2:]
    results = [completed[0]["mode_result"], completed[1]["mode_result"]]
    graph = build_mode_call_graph(session, updated_invocations, results)
    summary = summarize_mode_call_graph(graph)
    report = {
        "generated_at": _now(),
        "content_policy": "sample instrumentation only; not production runtime state",
        "session": session,
        "graph": graph,
        "summary": summary,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "output_path": str(target),
        "written": True,
        "summary": summary,
        "warnings": graph.get("warnings") or [],
    }


def _normalize_mode(mode: str, warnings: List[str], field_name: str) -> str:
    if mode in MODES:
        return mode
    warnings.append(f"invalid_mode:{field_name}:{mode}")
    return "unknown"


def _normalize_return_policy(return_policy: str, warnings: List[str]) -> str:
    if return_policy in RETURN_POLICIES:
        return return_policy
    warnings.append(f"unknown_return_policy:{return_policy}")
    return "user_decides"


def _normalize_result_type(result_type: str, warnings: List[str]) -> str:
    if result_type in RESULT_TYPES:
        return result_type
    warnings.append(f"unknown_result_type:{result_type}")
    return "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe(items: List[Any]) -> List[str]:
    return list(dict.fromkeys(str(item) for item in items))
