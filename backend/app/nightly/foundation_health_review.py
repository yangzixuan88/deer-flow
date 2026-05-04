"""Read-only Nightly Foundation Health Review aggregation.

This module aggregates projection surfaces only. It does not write runtime
state, create real action queues, execute tools, or repair anything.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_SAMPLE_PATH = REPORT_DIR / "R241-8A_NIGHTLY_FOUNDATION_HEALTH_REVIEW_SAMPLE.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HEALTH_DOMAINS = {
    "truth_state",
    "queue_sandbox",
    "memory",
    "asset",
    "mode",
    "tool_runtime",
    "prompt",
    "rtcm",
    "gateway",
    "root_guard",
    "unknown",
}

HEALTH_SEVERITIES = {"info", "low", "medium", "high", "critical", "unknown"}

ACTION_CANDIDATE_TYPES = {
    "diagnostic_only",
    "add_test",
    "refine_taxonomy",
    "add_context_link",
    "add_backup",
    "add_rollback",
    "review_prompt",
    "review_asset_candidate",
    "review_memory_candidate",
    "review_rtcm_session",
    "review_tool_policy",
    "fix_low_risk",
    "requires_user_confirmation",
    "blocked_high_risk",
    "unknown",
}

NIGHTLY_ACTION_PERMISSIONS = {
    "report_only",
    "auto_allowed_low_risk",
    "requires_backup",
    "requires_rollback",
    "requires_user_confirmation",
    "forbidden_auto",
    "unknown",
}


@dataclass
class FoundationHealthSignal:
    signal_id: str
    domain: str
    severity: str
    signal_type: str
    message: str
    source_system: str
    source_ref: Optional[str] = None
    affected_refs: List[str] = field(default_factory=list)
    metric_name: Optional[str] = None
    metric_value: Optional[Any] = None
    evidence_refs: List[str] = field(default_factory=list)
    recommended_action_type: str = "diagnostic_only"
    action_permission: str = "report_only"
    requires_user_confirmation: bool = False
    requires_backup: bool = False
    requires_rollback: bool = False
    warnings: List[str] = field(default_factory=list)
    observed_at: str = field(default_factory=lambda: _now())


@dataclass
class FoundationActionCandidate:
    action_candidate_id: str
    domain: str
    action_type: str
    title: str
    description: str
    severity: str
    permission: str
    source_signal_ids: List[str] = field(default_factory=list)
    target_refs: List[str] = field(default_factory=list)
    auto_executable: bool = False
    requires_user_confirmation: bool = False
    requires_backup: bool = False
    requires_rollback: bool = False
    blocked_reason: Optional[str] = None
    suggested_next_step: str = "review_signal"
    warnings: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now())


@dataclass
class NightlyFoundationHealthReview:
    review_id: str
    generated_at: str
    root: str
    domain_summaries: Dict[str, Any]
    total_signals: int
    by_severity: Dict[str, int]
    critical_count: int
    high_count: int
    action_candidate_count: int
    auto_allowed_count: int
    requires_confirmation_count: int
    blocked_high_risk_count: int
    signals: List[Dict[str, Any]]
    action_candidates: List[Dict[str, Any]]
    warnings: List[str]


def collect_truth_state_health(root: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    warnings: List[str] = []
    signals: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {"domain": "truth_state"}
    try:
        from app.m11.queue_sandbox_truth_projection import (
            correlate_queue_with_sandbox_truth,
            get_sandbox_execution_success_candidates,
            load_experiment_queue_snapshot,
            project_sandbox_outcomes,
        )
    except Exception as exc:  # pragma: no cover - covered via aggregate safe path
        return _collector_import_failure("truth_state", exc)

    queue_snapshot = _safe_call(
        load_experiment_queue_snapshot,
        "truth_state",
        warnings,
    )
    sandbox_projection = _safe_call(
        project_sandbox_outcomes,
        "truth_state",
        warnings,
        limit=limit,
    )
    success_candidates = _safe_call(
        get_sandbox_execution_success_candidates,
        "truth_state",
        warnings,
        limit=limit,
    )
    correlation = _safe_call(
        correlate_queue_with_sandbox_truth,
        "truth_state",
        warnings,
        limit=limit,
    )

    summary.update(
        {
            "queue_exists": queue_snapshot.get("exists"),
            "queue_task_count": queue_snapshot.get("task_count"),
            "sandbox_records_count": sandbox_projection.get("sandbox_records_count", 0),
            "execution_truth_count": sandbox_projection.get("execution_truth_count", 0),
            "eligible_execution_truth_count": success_candidates.get("eligible_count", 0),
            "simple_success_rate": success_candidates.get("simple_success_rate"),
            "queue_truth_correlation_warnings": correlation.get("warnings", []),
        }
    )

    for warning in queue_snapshot.get("warnings", []):
        if "missing" in str(warning).lower() or "does_not_exist" in str(warning).lower():
            signals.append(
                normalize_health_signal(
                    {
                        "domain": "queue_sandbox",
                        "signal_type": "queue_missing",
                        "message": f"Experiment queue warning: {warning}",
                        "severity": "medium",
                        "source_system": "queue_sandbox_truth_projection",
                        "recommended_action_type": "diagnostic_only",
                    }
                )
            )

    eligible_count = success_candidates.get("eligible_count", 0)
    if eligible_count == 0:
        signals.append(
            normalize_health_signal(
                {
                    "domain": "truth_state",
                    "signal_type": "no_execution_truth_candidates",
                    "message": "No execution_truth candidates available for execution_success_rate.",
                    "severity": "high",
                    "source_system": "queue_sandbox_truth_projection",
                    "metric_name": "eligible_execution_truth_count",
                    "metric_value": 0,
                    "recommended_action_type": "diagnostic_only",
                }
            )
        )

    success_rate = success_candidates.get("simple_success_rate")
    if isinstance(success_rate, (int, float)):
        severity = "high" if success_rate < 0.2 else "medium" if success_rate < 0.5 else "info"
        if severity != "info":
            signals.append(
                normalize_health_signal(
                    {
                        "domain": "truth_state",
                        "signal_type": "raw_execution_success_rate_low",
                        "message": "Raw execution truth success rate is below threshold.",
                        "severity": severity,
                        "source_system": "queue_sandbox_truth_projection",
                        "metric_name": "simple_success_rate",
                        "metric_value": success_rate,
                        "recommended_action_type": "diagnostic_only",
                    }
                )
            )

    for warning in correlation.get("warnings", []):
        warning_text = str(warning)
        signal_type = (
            "sandbox_truth_without_queue_task"
            if "truth_without_queue" in warning_text or "sandbox_truth" in warning_text
            else "queue_sandbox_mismatch"
        )
        signals.append(
            normalize_health_signal(
                {
                    "domain": "queue_sandbox",
                    "signal_type": signal_type,
                    "message": f"Queue/sandbox correlation warning: {warning_text}",
                    "severity": "medium",
                    "source_system": "queue_sandbox_truth_projection",
                    "recommended_action_type": "diagnostic_only",
                }
            )
        )

    warnings.extend(_dedupe(queue_snapshot.get("warnings", []) + sandbox_projection.get("warnings", []) + success_candidates.get("warnings", []) + correlation.get("warnings", [])))
    return {"signals": signals, "summary": summary, "warnings": _dedupe(warnings)}


def collect_memory_health(root: Optional[str] = None, max_files: int = 500) -> Dict[str, Any]:
    warnings: List[str] = []
    try:
        from app.memory.memory_projection import (
            detect_memory_risk_signals,
            get_long_term_memory_candidates,
            get_memory_asset_candidates,
            project_memory_roots,
        )
    except Exception as exc:
        return _collector_import_failure("memory", exc)

    projection = _safe_call(project_memory_roots, "memory", warnings, root=root, max_files=max_files)
    long_term = _safe_call(get_long_term_memory_candidates, "memory", warnings, root=root, max_files=max_files)
    asset_candidates = _safe_call(get_memory_asset_candidates, "memory", warnings, root=root, max_files=max_files)
    risks = _safe_call(detect_memory_risk_signals, "memory", warnings, root=root, max_files=max_files)

    signals = _signals_from_risk_counts(
        "memory",
        "memory_projection",
        risks.get("risk_by_type", {}),
        default_action="review_memory_candidate",
        default_severity="medium",
    )
    summary = {
        "domain": "memory",
        "classified_count": projection.get("classified_count", 0),
        "long_term_candidate_count": long_term.get("candidate_count", 0),
        "asset_candidate_count": asset_candidates.get("candidate_count", 0),
        "risk_count": risks.get("risk_count", 0),
        "risk_by_type": risks.get("risk_by_type", {}),
    }
    warnings.extend(projection.get("warnings", []) + long_term.get("warnings", []) + asset_candidates.get("warnings", []) + risks.get("warnings", []))
    return {"signals": signals, "summary": summary, "warnings": _dedupe(warnings)}


def collect_asset_health(root: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    warnings: List[str] = []
    try:
        from app.asset.asset_projection import aggregate_asset_projection, detect_asset_projection_risks
    except Exception as exc:
        return _collector_import_failure("asset", exc)

    projection = _safe_call(aggregate_asset_projection, "asset", warnings, limit=limit)
    risks = _safe_call(detect_asset_projection_risks, "asset", warnings, projection=projection)
    signals = _signals_from_risk_counts(
        "asset",
        "asset_projection",
        risks.get("risk_by_type", {}),
        default_action="review_asset_candidate",
        default_severity="medium",
    )
    summary = {
        "domain": "asset",
        "total_projected": projection.get("total_projected", 0),
        "candidate_count": projection.get("candidate_count", 0),
        "formal_asset_count": projection.get("formal_asset_count", 0),
        "risk_count": risks.get("risk_count", 0),
        "risk_by_type": risks.get("risk_by_type", {}),
    }
    warnings.extend(projection.get("warnings", []) + risks.get("warnings", []))
    return {"signals": signals, "summary": summary, "warnings": _dedupe(warnings)}


def collect_mode_health(root: Optional[str] = None) -> Dict[str, Any]:
    warnings: List[str] = []
    try:
        from app.mode.mode_orchestration_contract import (
            build_mode_call_graph,
            create_mode_invocation,
            create_mode_session,
        )
    except Exception as exc:
        return _collector_import_failure("mode", exc)

    session = create_mode_session("task", active_modes=["task", "search", "roundtable"], owner_system="nightly_health_review")
    invocations = [
        create_mode_invocation(session["mode_session_id"], "task", "search", "nightly sample evidence lookup"),
        create_mode_invocation(session["mode_session_id"], "task", "roundtable", "nightly sample review", executor="rtcm"),
    ]
    graph = build_mode_call_graph(session, invocations)

    signals = [
        normalize_health_signal(
            {
                "domain": "mode",
                "signal_type": "mode_instrumentation_standalone",
                "message": "Mode instrumentation remains a standalone helper and does not replace routing.",
                "severity": "info",
                "source_system": "mode_orchestration_contract",
                "recommended_action_type": "diagnostic_only",
            }
        ),
        normalize_health_signal(
            {
                "domain": "mode",
                "signal_type": "mode_callgraph_not_runtime_integrated",
                "message": "ModeCallGraph exists as projection/sample, not real runtime invocation graph.",
                "severity": "medium",
                "source_system": "mode_orchestration_contract",
                "recommended_action_type": "add_context_link",
            }
        ),
    ]
    summary = {
        "domain": "mode",
        "sample_generated": True,
        "invocation_count": len(invocations),
        "roundtable_projection_available": True,
        "gateway_run_path_modified": False,
    }
    warnings.extend(graph.get("warnings", []))
    return {"signals": signals, "summary": summary, "warnings": _dedupe(warnings)}


def collect_tool_runtime_health(root: Optional[str] = None) -> Dict[str, Any]:
    warnings: List[str] = []
    try:
        from app.tool_runtime.tool_runtime_contract import create_tool_execution_event, summarize_tool_events, validate_tool_event_policy
        from app.tool_runtime.tool_runtime_projection import (
            detect_tool_mode_risks,
            project_tool_events_for_mode_callgraph,
        )
    except Exception as exc:
        return _collector_import_failure("tool_runtime", exc)

    events = [
        create_tool_execution_event("fs.read", "read_file", "nightly_health_review", {"tool_type": "file_system"}),
        create_tool_execution_event(
            "fs.config",
            "modify_config",
            "nightly_health_review",
            {"tool_type": "file_system", "target_path": "package.json"},
        ),
        create_tool_execution_event(
            "fs.delete",
            "delete_file",
            "nightly_health_review",
            {"tool_type": "file_system", "target_path": "important.md"},
        ),
    ]
    validations = [validate_tool_event_policy(event) for event in events]
    summary_from_events = summarize_tool_events(events)
    mode_summary = project_tool_events_for_mode_callgraph(events)
    risks = detect_tool_mode_risks({"tool_events": events, "policy_validations": validations, "summary": mode_summary, "warnings": []})
    signals = _signals_from_risk_counts(
        "tool_runtime",
        "tool_runtime_projection",
        risks.get("risk_by_type", {}),
        default_action="review_tool_policy",
        default_severity="high",
    )
    summary = {
        "domain": "tool_runtime",
        "event_count": len(events),
        "summary": summary_from_events,
        "risk_count": risks.get("risk_count", 0),
        "risk_by_type": risks.get("risk_by_type", {}),
    }
    warnings.extend(mode_summary.get("warnings", []) + risks.get("warnings", []))
    return {"signals": signals, "summary": summary, "warnings": _dedupe(warnings)}


def collect_prompt_health(root: Optional[str] = None, max_files: int = 500) -> Dict[str, Any]:
    warnings: List[str] = []
    try:
        from app.prompt.prompt_projection import aggregate_prompt_projection, detect_prompt_governance_risks
    except Exception as exc:
        return _collector_import_failure("prompt", exc)

    projection = _safe_call(aggregate_prompt_projection, "prompt", warnings, root=root, max_files=max_files)
    risks = projection.get("risk_signals") or _safe_call(detect_prompt_governance_risks, "prompt", warnings, projection=projection)
    signals = _signals_from_risk_counts(
        "prompt",
        "prompt_projection",
        risks.get("risk_by_type", {}),
        default_action="review_prompt",
        default_severity="high",
    )
    source_projection = projection.get("source_projection", {})
    asset_candidates = projection.get("asset_candidates", {})
    summary = {
        "domain": "prompt",
        "classified_count": source_projection.get("classified_count", 0),
        "asset_candidate_count": asset_candidates.get("candidate_count", 0),
        "risk_count": risks.get("risk_count", 0),
        "risk_by_type": risks.get("risk_by_type", {}),
    }
    warnings.extend(projection.get("warnings", []) + risks.get("warnings", []))
    return {"signals": signals, "summary": summary, "warnings": _dedupe(warnings)}


def collect_rtcm_health(root: Optional[str] = None, max_files: int = 1000) -> Dict[str, Any]:
    warnings: List[str] = []
    try:
        from app.rtcm.rtcm_integration_contract import aggregate_rtcm_roundtable_projection
        from app.rtcm.rtcm_runtime_projection import (
            detect_rtcm_runtime_projection_risks,
            scan_rtcm_runtime_projection,
        )
    except Exception as exc:
        return _collector_import_failure("rtcm", exc)

    runtime_projection = _safe_call(scan_rtcm_runtime_projection, "rtcm", warnings, root=root, max_files=max_files)
    runtime_risks = _safe_call(detect_rtcm_runtime_projection_risks, "rtcm", warnings, projection=runtime_projection)
    integration_projection = _safe_call(aggregate_rtcm_roundtable_projection, "rtcm", warnings, root=root, max_files=max_files)
    signals = _signals_from_risk_counts(
        "rtcm",
        "rtcm_runtime_projection",
        runtime_risks.get("risk_by_type", {}),
        default_action="review_rtcm_session",
        default_severity="medium",
    )
    summary = {
        "domain": "rtcm",
        "classified_count": runtime_projection.get("classified_count", 0),
        "unknown_count": runtime_projection.get("unknown_count", 0),
        "session_count": runtime_projection.get("session_count", 0),
        "truth_candidate_count": runtime_projection.get("truth_candidate_count", 0),
        "asset_candidate_count": runtime_projection.get("asset_candidate_count", 0),
        "memory_candidate_count": runtime_projection.get("memory_candidate_count", 0),
        "followup_candidate_count": runtime_projection.get("followup_candidate_count", 0),
        "integration_truth_candidates": integration_projection.get("truth_candidates", {}).get("candidate_count", 0),
        "risk_count": runtime_risks.get("risk_count", 0),
        "risk_by_type": runtime_risks.get("risk_by_type", {}),
    }
    warnings.extend(runtime_projection.get("warnings", []) + runtime_risks.get("warnings", []) + integration_projection.get("warnings", []))
    return {"signals": signals, "summary": summary, "warnings": _dedupe(warnings)}


def normalize_health_signal(raw_signal: Dict[str, Any]) -> Dict[str, Any]:
    warnings = list(raw_signal.get("warnings", []))
    signal_type = str(raw_signal.get("signal_type") or raw_signal.get("type") or "unknown")
    domain = _normalize_choice(raw_signal.get("domain"), HEALTH_DOMAINS, "unknown")
    severity = _normalize_choice(raw_signal.get("severity"), HEALTH_SEVERITIES, _infer_severity(signal_type))
    action_type = _normalize_choice(
        raw_signal.get("recommended_action_type") or _infer_action_type(signal_type),
        ACTION_CANDIDATE_TYPES,
        "diagnostic_only",
    )
    permission = _normalize_choice(
        raw_signal.get("action_permission") or _infer_permission(signal_type, severity, action_type),
        NIGHTLY_ACTION_PERMISSIONS,
        "report_only",
    )

    requires_user_confirmation = bool(raw_signal.get("requires_user_confirmation", permission in {"requires_user_confirmation", "forbidden_auto"}))
    requires_backup = bool(raw_signal.get("requires_backup", permission in {"requires_backup", "requires_rollback"} or action_type == "add_backup"))
    requires_rollback = bool(raw_signal.get("requires_rollback", permission == "requires_rollback" or action_type == "add_rollback"))

    return asdict(
        FoundationHealthSignal(
            signal_id=str(raw_signal.get("signal_id") or _make_id("health_signal", domain, signal_type, raw_signal.get("source_ref"))),
            domain=domain,
            severity=severity,
            signal_type=signal_type,
            message=str(raw_signal.get("message") or signal_type),
            source_system=str(raw_signal.get("source_system") or "nightly_foundation_health_review"),
            source_ref=raw_signal.get("source_ref"),
            affected_refs=_listify(raw_signal.get("affected_refs")),
            metric_name=raw_signal.get("metric_name"),
            metric_value=raw_signal.get("metric_value"),
            evidence_refs=_listify(raw_signal.get("evidence_refs")),
            recommended_action_type=action_type,
            action_permission=permission,
            requires_user_confirmation=requires_user_confirmation,
            requires_backup=requires_backup,
            requires_rollback=requires_rollback,
            warnings=_dedupe(warnings),
        )
    )


def create_action_candidate_from_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_health_signal(signal)
    action_type = normalized["recommended_action_type"]
    severity = normalized["severity"]
    permission = normalized["action_permission"]
    warnings = list(normalized.get("warnings", []))

    high_risk_types = {
        "prompt_replace",
        "prompt_replacement",
        "memory_cleanup",
        "asset_elimination",
        "asset_core_elimination_attempt",
        "rtcm_state_mutation",
        "governance_write",
        "level_3_requires_confirmation",
    }
    if normalized["signal_type"] in high_risk_types or action_type in {"requires_user_confirmation", "blocked_high_risk"}:
        permission = "forbidden_auto" if severity == "critical" else "requires_user_confirmation"

    if severity == "critical" and permission not in {"forbidden_auto", "requires_user_confirmation"}:
        permission = "forbidden_auto"
    elif severity == "high" and permission == "report_only":
        permission = "requires_user_confirmation" if normalized.get("requires_user_confirmation") else "requires_backup"
    elif severity in {"info", "low"} and permission == "unknown":
        permission = "report_only"

    auto_executable = permission == "auto_allowed_low_risk" and severity in {"info", "low"}
    blocked_reason = None
    if permission == "forbidden_auto":
        blocked_reason = "high_risk_or_runtime_mutation_forbidden_auto"
        warnings.append("forbidden_auto_candidate_not_executed")

    return asdict(
        FoundationActionCandidate(
            action_candidate_id=_make_id("action_candidate", normalized["domain"], normalized["signal_type"], normalized["signal_id"]),
            domain=normalized["domain"],
            action_type=action_type,
            title=f"{normalized['domain']}: {normalized['signal_type']}",
            description=normalized["message"],
            severity=severity,
            permission=permission,
            source_signal_ids=[normalized["signal_id"]],
            target_refs=normalized.get("affected_refs", []),
            auto_executable=auto_executable,
            requires_user_confirmation=bool(normalized.get("requires_user_confirmation") or permission in {"requires_user_confirmation", "forbidden_auto"}),
            requires_backup=bool(normalized.get("requires_backup") or permission in {"requires_backup", "requires_rollback"}),
            requires_rollback=bool(normalized.get("requires_rollback") or permission == "requires_rollback"),
            blocked_reason=blocked_reason,
            suggested_next_step=_suggest_next_step(action_type, permission),
            warnings=_dedupe(warnings),
        )
    )


def aggregate_nightly_foundation_health(root: Optional[str] = None, max_files: int = 500) -> Dict[str, Any]:
    root_path = str(Path(root).resolve()) if root else str(ROOT)
    collectors: List[Tuple[str, Callable[..., Dict[str, Any]], Dict[str, Any]]] = [
        ("truth_state", collect_truth_state_health, {"root": root, "limit": 200}),
        ("memory", collect_memory_health, {"root": root, "max_files": max_files}),
        ("asset", collect_asset_health, {"root": root, "limit": 200}),
        ("mode", collect_mode_health, {"root": root}),
        ("tool_runtime", collect_tool_runtime_health, {"root": root}),
        ("prompt", collect_prompt_health, {"root": root, "max_files": max_files}),
        ("rtcm", collect_rtcm_health, {"root": root, "max_files": max(max_files, 1000)}),
    ]

    all_signals: List[Dict[str, Any]] = []
    warnings: List[str] = []
    domain_summaries: Dict[str, Any] = {}

    for domain, collector, kwargs in collectors:
        try:
            result = collector(**kwargs)
        except Exception as exc:
            result = _collector_import_failure(domain, exc)
        signals = [normalize_health_signal(signal) for signal in result.get("signals", [])]
        all_signals.extend(signals)
        domain_summaries[domain] = result.get("summary", {"domain": domain, "collector_failed": True})
        warnings.extend(result.get("warnings", []))

    action_candidates = [create_action_candidate_from_signal(signal) for signal in all_signals]
    severity_counts = Counter(signal.get("severity", "unknown") for signal in all_signals)
    permission_counts = Counter(action.get("permission", "unknown") for action in action_candidates)

    review = asdict(
        NightlyFoundationHealthReview(
            review_id=_make_id("nightly_review", root_path, str(len(all_signals)), _now()),
            generated_at=_now(),
            root=root_path,
            domain_summaries=domain_summaries,
            total_signals=len(all_signals),
            by_severity=dict(severity_counts),
            critical_count=severity_counts.get("critical", 0),
            high_count=severity_counts.get("high", 0),
            action_candidate_count=len(action_candidates),
            auto_allowed_count=permission_counts.get("auto_allowed_low_risk", 0),
            requires_confirmation_count=permission_counts.get("requires_user_confirmation", 0),
            blocked_high_risk_count=permission_counts.get("forbidden_auto", 0),
            signals=all_signals,
            action_candidates=action_candidates,
            warnings=_dedupe(warnings),
        )
    )
    return review


def generate_nightly_foundation_health_review(
    output_path: Optional[str] = None,
    root: Optional[str] = None,
    max_files: int = 500,
) -> Dict[str, Any]:
    review = aggregate_nightly_foundation_health(root=root, max_files=max_files)
    target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"review": review, "generated_at": _now(), "warnings": review.get("warnings", [])}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(target), **payload}


def _collector_import_failure(domain: str, exc: Exception) -> Dict[str, Any]:
    warning = f"{domain}_collector_failed: {exc}"
    signal = normalize_health_signal(
        {
            "domain": domain,
            "severity": "high",
            "signal_type": "collector_failure",
            "message": warning,
            "source_system": "nightly_foundation_health_review",
            "recommended_action_type": "diagnostic_only",
            "warnings": [warning],
        }
    )
    return {"signals": [signal], "summary": {"domain": domain, "collector_failed": True}, "warnings": [warning]}


def _safe_call(func: Callable[..., Dict[str, Any]], domain: str, warnings: List[str], **kwargs: Any) -> Dict[str, Any]:
    try:
        result = func(**kwargs)
        return result if isinstance(result, dict) else {"warnings": [f"{func.__name__}_returned_non_dict"]}
    except Exception as exc:
        warning = f"{domain}_{func.__name__}_failed: {exc}"
        warnings.append(warning)
        return {"warnings": [warning]}


def _signals_from_risk_counts(
    domain: str,
    source_system: str,
    risk_by_type: Dict[str, int],
    default_action: str,
    default_severity: str,
) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    for risk_type, count in sorted((risk_by_type or {}).items()):
        severity = _infer_severity(risk_type, fallback=default_severity)
        action = _infer_action_type(risk_type, fallback=default_action)
        signals.append(
            normalize_health_signal(
                {
                    "domain": domain,
                    "severity": severity,
                    "signal_type": str(risk_type),
                    "message": f"{risk_type}: {count}",
                    "source_system": source_system,
                    "metric_name": str(risk_type),
                    "metric_value": count,
                    "recommended_action_type": action,
                }
            )
        )
    return signals


def _infer_severity(signal_type: str, fallback: str = "medium") -> str:
    text = str(signal_type).lower()
    if any(marker in text for marker in ["critical", "forbidden", "core", "external_side_effect"]):
        return "critical"
    if any(marker in text for marker in ["missing_rollback", "rollback_missing", "missing_backup", "backup_missing", "without_test", "level_3", "requires_confirmation", "no_execution_truth"]):
        return "high"
    if any(marker in text for marker in ["unknown", "missing_context", "candidate", "mismatch", "queue_missing", "not_long_term"]):
        return "medium"
    if any(marker in text for marker in ["info", "standalone"]):
        return "info"
    return fallback if fallback in HEALTH_SEVERITIES else "medium"


def _infer_action_type(signal_type: str, fallback: str = "diagnostic_only") -> str:
    text = str(signal_type).lower()
    if "taxonomy" in text or "unknown" in text:
        return "refine_taxonomy"
    if "context_link" in text:
        return "add_context_link"
    if "missing_backup" in text or "without_backup" in text:
        return "add_backup"
    if "missing_rollback" in text or "without_rollback" in text:
        return "add_rollback"
    if "without_test" in text or "add_test" in text:
        return "add_test"
    if "prompt" in text:
        return "review_prompt"
    if "asset" in text:
        return "review_asset_candidate"
    if "memory" in text:
        return "review_memory_candidate"
    if "rtcm" in text or "session" in text or "followup" in text:
        return "review_rtcm_session"
    if "tool" in text or "root_guard" in text or "level_3" in text:
        return "review_tool_policy"
    if "requires_confirmation" in text or "forbidden" in text:
        return "requires_user_confirmation"
    return fallback if fallback in ACTION_CANDIDATE_TYPES else "diagnostic_only"


def _infer_permission(signal_type: str, severity: str, action_type: str) -> str:
    text = str(signal_type).lower()
    if any(marker in text for marker in ["prompt_replace", "memory_cleanup", "asset_elimination", "governance_write", "rtcm_state_mutation", "core"]):
        return "forbidden_auto"
    if "missing_rollback" in text or "rollback_missing" in text or action_type == "add_rollback":
        return "requires_rollback"
    if "missing_backup" in text or "backup_missing" in text or action_type == "add_backup":
        return "requires_backup"
    if severity == "critical":
        return "forbidden_auto"
    if severity == "high":
        return "requires_user_confirmation"
    if severity in {"info", "low"} and action_type == "fix_low_risk":
        return "auto_allowed_low_risk"
    return "report_only"


def _suggest_next_step(action_type: str, permission: str) -> str:
    if permission == "forbidden_auto":
        return "user_review_required_before_any_action"
    if permission == "requires_user_confirmation":
        return "prepare_review_packet_for_user_confirmation"
    if permission in {"requires_backup", "requires_rollback"}:
        return "prepare_backup_and_rollback_plan"
    if action_type == "refine_taxonomy":
        return "refine_readonly_taxonomy"
    return "keep_report_only_until_reviewed"


def _normalize_choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value) if value is not None else default
    return text if text in allowed else default


def _listify(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    return [str(value)]


def _make_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}_{abs(hash(raw)) % 10_000_000_000:010d}"


def _dedupe(items: List[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in items:
        text = str(item)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
