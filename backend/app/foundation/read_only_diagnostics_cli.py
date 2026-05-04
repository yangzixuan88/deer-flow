"""Internal read-only foundation diagnostics CLI helpers.

This module binds diagnostic commands without registering a global CLI, opening HTTP
endpoints, touching Gateway, writing runtime state, or executing repairs/tools.
Phase B expands Phase A (truth-state/queue-sandbox/nightly) to include
memory/asset/prompt/rtcm diagnostics.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_SAMPLE_PATH_PHASE_A = REPORT_DIR / "R241-10A_READONLY_DIAGNOSTIC_CLI_SAMPLE.json"
DEFAULT_SAMPLE_PATH_PHASE_B = REPORT_DIR / "R241-10B_READONLY_DIAGNOSTIC_CLI_EXPANSION_SAMPLE.json"
DEFAULT_SAMPLE_PATH_PHASE_C = REPORT_DIR / "R241-10C_FEISHU_SUMMARY_DRYRUN_CLI_SAMPLE.json"
DEFAULT_SAMPLE_PATH_PHASE_D = REPORT_DIR / "R241-11B_DRYRUN_AUDIT_RECORD_PROJECTION_SAMPLE.json"
DEFAULT_SAMPLE_PATH_PHASE_13C = REPORT_DIR / "R241-13C_AUDIT_TREND_FEISHU_CLI_PREVIEW_SAMPLE.json"
SOURCE_PLAN_REF = str(REPORT_DIR / "R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.json")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DIAGNOSTIC_COMMANDS = {
    "truth-state",
    "queue-sandbox",
    "memory",
    "asset",
    "prompt",
    "rtcm",
    "nightly",
    "feishu-summary",
    "audit-trend",
    "audit-trend-feishu",
    "audit-trend-feishu-presend",
    "all",
    "unknown",
}
OUTPUT_FORMATS = {"json", "markdown", "text"}
EXIT_STATUSES = {"ok", "partial_warning", "failed", "projection_only"}
IMPLEMENTED_COMMANDS = ["truth-state", "queue-sandbox", "memory", "asset", "prompt", "rtcm", "nightly", "feishu-summary", "audit-trend", "audit-trend-feishu", "audit-trend-feishu-presend", "all"]
DISABLED_COMMANDS: List[str] = []


@dataclass
class DiagnosticRunResult:
    command: str
    status: str
    generated_at: str
    root: str
    format: str
    summary: Dict[str, Any]
    payload: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    report_path: Optional[str] = None


@dataclass
class DiagnosticCommandRegistry:
    available_commands: List[str]
    disabled_commands: List[str]
    source_plan_ref: str
    warnings: List[str] = field(default_factory=list)


def get_diagnostic_command_registry() -> Dict[str, Any]:
    return asdict(
        DiagnosticCommandRegistry(
            available_commands=IMPLEMENTED_COMMANDS[:],
            disabled_commands=DISABLED_COMMANDS[:],
            source_plan_ref=SOURCE_PLAN_REF,
            warnings=[
                "feishu_summary_projection_only",
                "no_real_feishu_push",
                "no_webhook_call",
            ],
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Audit Record Projection Helper (Phase D / R241-11B)
# ─────────────────────────────────────────────────────────────────────────────


_COMMAND_TO_EVENT_TYPE = {
    "feishu-summary": "feishu_summary_dry_run",
    "nightly": "nightly_health_review",
    "all": "diagnostic_cli_run",
}


def add_audit_record_to_diagnostic_result(result: Dict[str, Any], command: str = "unknown") -> Dict[str, Any]:
    """Add audit_record and audit_validation to a diagnostic result dict.

    R241-11B Phase 2: generates AuditTrailRecord from diagnostic result
    without writing any JSONL files.
    """
    event_type = _COMMAND_TO_EVENT_TYPE.get(command, "diagnostic_domain_result")
    diagnostic_input = {
        "command": command,
        "status": result.get("status", "unknown"),
        "generated_at": result.get("generated_at", _now()),
        "root": result.get("root", str(ROOT)),
        "summary": result.get("summary", {}),
        "payload": result.get("payload", {}),
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
    }
    try:
        from app.audit import create_audit_record_from_diagnostic_result, validate_audit_record
        audit_record = create_audit_record_from_diagnostic_result(diagnostic_input, event_type=event_type)
        audit_validation = validate_audit_record(audit_record)
    except Exception as exc:
        audit_record = {
            "error": str(exc),
            "event_type": event_type,
            "write_mode": "design_only",
        }
        audit_validation = {"valid": False, "errors": [f"audit_record_generation_failed:{exc}"]}
    result["audit_record"] = audit_record
    result["audit_validation"] = audit_validation
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Truth-State Diagnostic (Phase A)
# ─────────────────────────────────────────────────────────────────────────────


def run_truth_state_diagnostic(format: str = "json", limit: int = 100) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    payload: Dict[str, Any] = {}
    try:
        from app.m11.governance_bridge import get_success_rate_candidates, project_recent_outcomes
    except Exception as exc:
        errors.append(f"truth_state_import_failed:{exc}")
        return _run_result("truth-state", "failed", format, {}, payload, warnings, errors)

    recent = _safe_call(project_recent_outcomes, warnings, limit=limit)
    candidates = _safe_call(get_success_rate_candidates, warnings, metric_scope="execution_success_rate", limit=limit)
    truth_events_count = int(recent.get("truth_events_count") or 0)
    state_events_count = int(recent.get("state_events_count") or 0)
    eligible_count = int(candidates.get("eligible_count") or 0)
    ineligible_count = int(candidates.get("ineligible_count") or 0)
    excluded = _excluded_governance_or_observation_count(candidates)
    warnings.extend(recent.get("warnings", []) + candidates.get("warnings", []))
    payload = {
        "recent_outcomes_projection": recent,
        "execution_success_candidates": candidates,
    }
    summary = {
        "truth_events_count": truth_events_count,
        "state_events_count": state_events_count,
        "execution_success_candidates_count": eligible_count,
        "ineligible_count": ineligible_count,
        "excluded_governance_or_observation_count": excluded,
    }
    result = _run_result("truth-state", _status(warnings, errors), format, summary, payload, warnings, errors)
    return add_audit_record_to_diagnostic_result(result, "truth-state")


# ─────────────────────────────────────────────────────────────────────────────
# Queue-Sandbox Diagnostic (Phase A)
# ─────────────────────────────────────────────────────────────────────────────


def run_queue_sandbox_diagnostic(format: str = "json", limit: int = 100) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    try:
        from app.m11.queue_sandbox_truth_projection import (
            correlate_queue_with_sandbox_truth,
            get_sandbox_execution_success_candidates,
            load_experiment_queue_snapshot,
            project_sandbox_outcomes,
        )
    except Exception as exc:
        errors.append(f"queue_sandbox_import_failed:{exc}")
        return _run_result("queue-sandbox", "failed", format, {}, {}, warnings, errors)

    queue_snapshot = _safe_call(load_experiment_queue_snapshot, warnings)
    sandbox = _safe_call(project_sandbox_outcomes, warnings, limit=limit)
    candidates = _safe_call(get_sandbox_execution_success_candidates, warnings, limit=limit)
    correlation = _safe_call(correlate_queue_with_sandbox_truth, warnings, limit=limit)
    all_warnings = _dedupe(
        warnings
        + queue_snapshot.get("warnings", [])
        + sandbox.get("warnings", [])
        + candidates.get("warnings", [])
        + correlation.get("warnings", [])
    )
    summary = {
        "queue_snapshot": {
            "exists": queue_snapshot.get("exists"),
            "task_count": queue_snapshot.get("task_count", 0),
            "status_counts": queue_snapshot.get("status_counts", {}),
            "with_verify_script_count": queue_snapshot.get("with_verify_script_count", 0),
        },
        "sandbox_records_count": sandbox.get("sandbox_records_count", 0),
        "actual_pass_count": sandbox.get("actual_pass_count", candidates.get("pass_count", 0)),
        "actual_fail_count": sandbox.get("actual_fail_count", candidates.get("fail_count", 0)),
        "simple_success_rate": candidates.get("simple_success_rate"),
        "correlation_warnings": correlation.get("warnings", []),
        "queue_path_mismatch_warning": _find_queue_warning(all_warnings),
    }
    payload = {
        "queue_snapshot": queue_snapshot,
        "sandbox_projection": sandbox,
        "execution_success_candidates": candidates,
        "queue_truth_correlation": correlation,
    }
    result = _run_result("queue-sandbox", _status(all_warnings, errors), format, summary, payload, all_warnings, errors)
    return add_audit_record_to_diagnostic_result(result, "queue-sandbox")


# ─────────────────────────────────────────────────────────────────────────────
# Nightly Diagnostic (Phase A)
# ─────────────────────────────────────────────────────────────────────────────


def run_nightly_diagnostic(format: str = "json", max_files: int = 500) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    try:
        from app.nightly.foundation_health_review import aggregate_nightly_foundation_health
        from app.nightly.foundation_health_summary import build_plaintext_nightly_summary, summarize_review_for_user
    except Exception as exc:
        errors.append(f"nightly_import_failed:{exc}")
        return _run_result("nightly", "failed", format, {}, {}, warnings, errors)

    review = _safe_call(aggregate_nightly_foundation_health, warnings, root=str(ROOT), max_files=max_files)
    user_summary = _safe_call(summarize_review_for_user, warnings, review=review) if review else {}
    text_summary = _safe_call(build_plaintext_nightly_summary, warnings, review=review) if review else {}
    all_warnings = _dedupe(warnings + review.get("warnings", []) + user_summary.get("warnings", []) + text_summary.get("warnings", []))
    summary = {
        "total_signals": review.get("total_signals", 0),
        "by_severity": review.get("by_severity", {}),
        "action_candidate_count": review.get("action_candidate_count", 0),
        "blocked_high_risk_count": review.get("blocked_high_risk_count", 0),
        "requires_confirmation_count": review.get("requires_confirmation_count", 0),
        "headline": user_summary.get("headline"),
    }
    payload = {
        "review": review,
        "user_summary": user_summary,
        "plaintext_summary": text_summary,
    }
    result = _run_result("nightly", _status(all_warnings, errors), format, summary, payload, all_warnings, errors)
    return add_audit_record_to_diagnostic_result(result, "nightly")


# ─────────────────────────────────────────────────────────────────────────────
# Memory Diagnostic (Phase B)
# ─────────────────────────────────────────────────────────────────────────────


def run_memory_diagnostic(format: str = "json", max_files: int = 500) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    try:
        from app.memory.memory_projection import (
            detect_memory_risk_signals,
            get_long_term_memory_candidates,
            get_memory_asset_candidates,
            project_memory_roots,
        )
    except Exception as exc:
        errors.append(f"memory_import_failed:{exc}")
        return _run_result("memory", "failed", format, {}, {}, warnings, errors)

    scan_root = str(ROOT)
    roots = _safe_call(project_memory_roots, warnings, root=scan_root, max_files=max_files)
    lt_candidates = _safe_call(get_long_term_memory_candidates, warnings, root=scan_root, max_files=max_files)
    asset_candidates = _safe_call(get_memory_asset_candidates, warnings, root=scan_root, max_files=max_files)
    risks = _safe_call(detect_memory_risk_signals, warnings, root=scan_root, max_files=max_files)

    all_warnings = _dedupe(
        warnings
        + roots.get("warnings", [])
        + lt_candidates.get("warnings", [])
        + asset_candidates.get("warnings", [])
        + risks.get("warnings", [])
    )
    risk_by_type = risks.get("risk_by_type") or {}
    top_risks = sorted(risk_by_type.items(), key=lambda x: x[1], reverse=True)[:5] if risk_by_type else []

    summary = {
        "scanned_count": roots.get("scanned_count", 0),
        "classified_count": roots.get("classified_count", 0),
        "long_term_eligible_count": roots.get("long_term_eligible_count", 0),
        "asset_candidate_eligible_count": roots.get("asset_candidate_eligible_count", 0),
        "risk_count": risks.get("risk_count", 0),
        "top_risk_types": top_risks,
    }
    payload = {
        "memory_roots": _compact_payload(roots, max_items=20),
        "long_term_candidates": _compact_payload(lt_candidates, max_items=20),
        "asset_candidates": _compact_payload(asset_candidates, max_items=20),
        "risk_signals": _compact_payload(risks, max_items=20),
    }
    result = _run_result("memory", _status(all_warnings, errors), format, summary, payload, all_warnings, errors)
    return add_audit_record_to_diagnostic_result(result, "memory")


# ─────────────────────────────────────────────────────────────────────────────
# Asset Diagnostic (Phase B)
# ─────────────────────────────────────────────────────────────────────────────


def run_asset_diagnostic(format: str = "json", limit: int = 200) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    try:
        from app.asset.asset_projection import aggregate_asset_projection, detect_asset_projection_risks
    except Exception as exc:
        errors.append(f"asset_import_failed:{exc}")
        return _run_result("asset", "failed", format, {}, {}, warnings, errors)

    aggregate = _safe_call(aggregate_asset_projection, warnings, limit=limit)
    risk_signals = _safe_call(detect_asset_projection_risks, warnings, projection=aggregate)

    all_warnings = _dedupe(warnings + aggregate.get("warnings", []) + risk_signals.get("warnings", []))
    risk_by_type = risk_signals.get("risk_by_type") or {}
    top_risks = sorted(risk_by_type.items(), key=lambda x: x[1], reverse=True)[:5] if risk_by_type else []

    summary = {
        "total_projected": aggregate.get("total_projected", 0),
        "candidate_count": aggregate.get("candidate_count", 0),
        "formal_asset_count": aggregate.get("formal_asset_count", 0),
        "by_asset_category": aggregate.get("by_asset_category", {}),
        "by_lifecycle_tier": aggregate.get("by_lifecycle_tier", {}),
        "risk_count": risk_signals.get("risk_count", 0),
        "top_risk_types": top_risks,
    }
    payload = {
        "aggregate_projection": _compact_payload(aggregate, max_items=20),
        "risk_signals": _compact_payload(risk_signals, max_items=20),
    }
    result = _run_result("asset", _status(all_warnings, errors), format, summary, payload, all_warnings, errors)
    return add_audit_record_to_diagnostic_result(result, "asset")


# ─────────────────────────────────────────────────────────────────────────────
# Prompt Diagnostic (Phase B)
# ─────────────────────────────────────────────────────────────────────────────


def run_prompt_diagnostic(format: str = "json", max_files: int = 500) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    try:
        from app.prompt.prompt_projection import aggregate_prompt_projection, detect_prompt_governance_risks
    except Exception as exc:
        errors.append(f"prompt_import_failed:{exc}")
        return _run_result("prompt", "failed", format, {}, {}, warnings, errors)

    aggregate = _safe_call(aggregate_prompt_projection, warnings, root=str(ROOT), max_files=max_files)
    source_projection = aggregate.get("source_projection") or {}
    replacement_risks = aggregate.get("replacement_risks") or {}
    asset_candidates = aggregate.get("asset_candidates") or {}
    risk_signals = _safe_call(
        detect_prompt_governance_risks,
        warnings,
        projection={
            "source_projection": source_projection,
            "replacement_risks": replacement_risks,
            "asset_candidates": asset_candidates,
        },
    )

    all_warnings = _dedupe(
        warnings
        + aggregate.get("warnings", [])
        + risk_signals.get("warnings", [])
    )
    risk_by_type = risk_signals.get("risk_by_type") or {}
    top_risks = sorted(risk_by_type.items(), key=lambda x: x[1], reverse=True)[:5] if risk_by_type else []

    summary = {
        "scanned_count": source_projection.get("scanned_count", 0),
        "classified_count": source_projection.get("classified_count", 0),
        "by_layer": source_projection.get("by_layer", {}),
        "by_source_type": source_projection.get("by_source_type", {}),
        "asset_candidate_count": asset_candidates.get("candidate_count", 0),
        "critical_sources_count": source_projection.get("critical_sources_count", 0),
        "replacement_risk_count": replacement_risks.get("total", 0),
        "risk_count": risk_signals.get("risk_count", 0),
        "top_risk_types": top_risks,
    }
    payload = {
        "source_projection": _compact_payload(source_projection, max_items=20),
        "replacement_risks": _compact_payload(replacement_risks, max_items=20),
        "asset_candidates": _compact_payload(asset_candidates, max_items=20),
        "risk_signals": _compact_payload(risk_signals, max_items=20),
    }
    result = _run_result("prompt", _status(all_warnings, errors), format, summary, payload, all_warnings, errors)
    return add_audit_record_to_diagnostic_result(result, "prompt")


# ─────────────────────────────────────────────────────────────────────────────
# RTCM Diagnostic (Phase B)
# ─────────────────────────────────────────────────────────────────────────────


def run_rtcm_diagnostic(format: str = "json", max_files: int = 1000) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    try:
        from app.rtcm.rtcm_runtime_projection import (
            detect_rtcm_runtime_projection_risks,
            scan_rtcm_runtime_projection,
        )
    except Exception as exc:
        errors.append(f"rtcm_import_failed:{exc}")
        return _run_result("rtcm", "failed", format, {}, {}, warnings, errors)

    scan = _safe_call(scan_rtcm_runtime_projection, warnings, root=str(ROOT), max_files=max_files)
    risk_signals = _safe_call(detect_rtcm_runtime_projection_risks, warnings, projection={"runtime_path_projection": scan})

    all_warnings = _dedupe(warnings + scan.get("warnings", []) + risk_signals.get("warnings", []))
    risk_by_type = risk_signals.get("risk_by_type") or {}
    top_risks = sorted(risk_by_type.items(), key=lambda x: x[1], reverse=True)[:5] if risk_by_type else []

    summary = {
        "scanned_count": scan.get("scanned_count", 0),
        "classified_count": scan.get("classified_count", 0),
        "unknown_count": scan.get("unknown_count", 0),
        "session_count": scan.get("session_count", 0),
        "truth_candidate_count": scan.get("truth_candidate_count", 0),
        "asset_candidate_count": scan.get("asset_candidate_count", 0),
        "memory_candidate_count": scan.get("memory_candidate_count", 0),
        "followup_candidate_count": scan.get("followup_candidate_count", 0),
        "risk_count": risk_signals.get("risk_count", 0),
        "top_risk_types": top_risks,
    }
    payload = {
        "runtime_scan": _compact_payload(scan, max_items=20),
        "risk_signals": _compact_payload(risk_signals, max_items=20),
    }
    result = _run_result("rtcm", _status(all_warnings, errors), format, summary, payload, all_warnings, errors)
    return add_audit_record_to_diagnostic_result(result, "rtcm")


# ─────────────────────────────────────────────────────────────────────────────
# Feishu-Summary Diagnostic (Phase C)
# ─────────────────────────────────────────────────────────────────────────────


def run_feishu_summary_diagnostic(format: str = "json") -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    try:
        from app.nightly.foundation_health_review import aggregate_nightly_foundation_health
        from app.nightly.foundation_health_summary import (
            build_feishu_card_payload_projection,
            build_plaintext_nightly_summary,
            load_latest_nightly_review_sample,
            select_top_action_candidates,
            summarize_review_by_domain,
            summarize_review_for_user,
            validate_feishu_payload_projection,
        )
    except Exception as exc:
        errors.append(f"feishu_summary_import_failed:{exc}")
        return _run_result("feishu-summary", "failed", format, {}, {}, warnings, errors)

    review_data = _safe_call(aggregate_nightly_foundation_health, warnings, root=str(ROOT), max_files=500)
    loaded = _safe_call(load_latest_nightly_review_sample, warnings)
    review = loaded.get("review") or {}
    user_summary = _safe_call(summarize_review_for_user, warnings, review=review) if review else {}
    domain_summary = _safe_call(summarize_review_by_domain, warnings, review=review) if review else {}
    top_actions = _safe_call(select_top_action_candidates, warnings, review=review, max_items=10) if review else {}
    feishu_payload = _safe_call(build_feishu_card_payload_projection, warnings, review=review, summary=user_summary) if review else {}
    plaintext = _safe_call(build_plaintext_nightly_summary, warnings, review=review) if review else {}
    validation = _safe_call(validate_feishu_payload_projection, warnings, payload=feishu_payload) if feishu_payload else {}

    all_warnings = _dedupe(
        warnings
        + review_data.get("warnings", [])
        + loaded.get("warnings", [])
        + user_summary.get("warnings", [])
        + domain_summary.get("warnings", [])
        + top_actions.get("warnings", [])
        + feishu_payload.get("warnings", [])
        + plaintext.get("warnings", [])
        + validation.get("warnings", [])
        + validation.get("blocked_reasons", [])
    )

    summary = {
        "review_loaded": loaded.get("exists", False),
        "source_review_id": review.get("review_id"),
        "total_signals": review.get("total_signals", 0),
        "critical_count": user_summary.get("critical_count", 0),
        "high_count": user_summary.get("high_count", 0),
        "action_candidate_count": user_summary.get("action_candidate_count", 0),
        "top_action_count": top_actions.get("selected_count", 0),
        "feishu_payload_status": feishu_payload.get("status", "unknown"),
        "send_allowed": feishu_payload.get("send_allowed", False),
        "webhook_required": feishu_payload.get("webhook_required", True),
        "validation_valid": validation.get("valid", False),
        "no_webhook_call": feishu_payload.get("no_webhook_call", False),
        "no_runtime_write": feishu_payload.get("no_runtime_write", False),
    }
    payload = {
        "feishu_payload_projection": _compact_payload(feishu_payload, max_items=20),
        "plaintext_summary": plaintext,
        "validation": validation,
    }
    result = _run_result("feishu-summary", _status(all_warnings, errors), format, summary, payload, all_warnings, errors)
    return add_audit_record_to_diagnostic_result(result, "feishu-summary")


# ─────────────────────────────────────────────────────────────────────────────
# All Diagnostics (Phase A + B + C)
# ─────────────────────────────────────────────────────────────────────────────


def run_all_diagnostics(
    format: str = "json",
    limit: int = 100,
    max_files: int = 500,
    write_report: bool = False,
    output_path: Optional[str] = None,
    append_audit: bool = False,
) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    results: Dict[str, Any] = {}
    for name, func, kwargs in [
        ("truth-state", run_truth_state_diagnostic, {"format": "json", "limit": limit}),
        ("queue-sandbox", run_queue_sandbox_diagnostic, {"format": "json", "limit": limit}),
        ("memory", run_memory_diagnostic, {"format": "json", "max_files": max_files}),
        ("asset", run_asset_diagnostic, {"format": "json", "limit": limit}),
        ("prompt", run_prompt_diagnostic, {"format": "json", "max_files": max_files}),
        ("rtcm", run_rtcm_diagnostic, {"format": "json", "max_files": max_files * 2}),
        ("nightly", run_nightly_diagnostic, {"format": "json", "max_files": max_files}),
        ("feishu-summary", run_feishu_summary_diagnostic, {"format": "json"}),
    ]:
        try:
            result = func(**kwargs)
        except Exception as exc:
            result = _run_result(name, "failed", "json", {}, {}, [], [f"{name}_diagnostic_failed:{exc}"])
        results[name] = result
        warnings.extend(result.get("warnings", []))
        errors.extend(result.get("errors", []))

    child_statuses = [result.get("status") for result in results.values()]
    overall = (
        "failed"
        if all(status == "failed" for status in child_statuses)
        else "partial_warning"
        if warnings or errors or any(status != "ok" for status in child_statuses)
        else "ok"
    )
    summary = {
        "commands_run": list(results.keys()),
        "child_statuses": {name: result.get("status") for name, result in results.items()},
        "disabled_commands": DISABLED_COMMANDS[:],
        "write_report": bool(write_report),
        "append_audit": bool(append_audit),
    }
    payload = {
        "command_registry": get_diagnostic_command_registry(),
        "diagnostics": results,
    }
    report_path = None
    result = _run_result("all", overall, format, summary, payload, _dedupe(warnings), _dedupe(errors))
    result = add_audit_record_to_diagnostic_result(result, "all")
    if append_audit:
        append_result = _append_audit_to_trail(result)
        result["audit_append_result"] = append_result
    if write_report:
        target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH_PHASE_C
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path = str(target)
        result["report_path"] = report_path
    return result


def _append_audit_to_trail(all_result: Dict[str, Any]) -> Dict[str, Any]:
    """Append all audit records from all_result to audit trail JSONL files."""
    try:
        from app.audit import append_all_diagnostic_audit_records
        return append_all_diagnostic_audit_records(all_result, root=str(ROOT), dry_run=False)
    except Exception as exc:
        return {
            "total_records": 0,
            "appended_count": 0,
            "skipped_count": 0,
            "failed_count": 1,
            "results": [],
            "warnings": [f"append_audit_failed:{exc}"],
            "errors": [f"append_audit_failed:{exc}"],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Formatters
# ─────────────────────────────────────────────────────────────────────────────


def format_diagnostic_result(result: Dict[str, Any], format: str) -> Any:
    fmt = _format(format)
    if fmt == "json":
        return result
    if fmt == "markdown":
        return _format_markdown(result)
    if fmt == "text":
        return _format_text(result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Audit Query CLI Helpers (R241-11D)
# ─────────────────────────────────────────────────────────────────────────────


def _run_audit_scan(args: Any) -> int:
    """Run audit-scan: scan existing audit_trail JSONL files, print summary."""
    try:
        from app.audit import (
            discover_audit_trail_files,
            scan_append_only_audit_trail,
            format_audit_query_result,
        )
    except Exception as exc:
        print(json.dumps({"error": f"import_failed:{exc}"}))
        return 1

    discovery = discover_audit_trail_files(root=str(ROOT))
    scan = scan_append_only_audit_trail(root=str(ROOT))

    query_result = {
        "query_id": "audit_scan",
        "status": "ok",
        "generated_at": _now(),
        "root": str(ROOT),
        "filters": {},
        "total_scanned": scan.get("total_valid_records", 0),
        "total_matched": scan.get("total_valid_records", 0),
        "returned_count": scan.get("existing_files", 0),
        "records": [],
        "file_summaries": scan.get("file_summaries", []),
        "warnings": scan.get("warnings", []),
        "errors": scan.get("errors", []),
    }

    formatted = format_audit_query_result(query_result, args.format)
    if args.format == "json":
        print(json.dumps(formatted, ensure_ascii=False, indent=2))
    else:
        print(formatted)
    return 0


def _run_audit_query(args: Any) -> int:
    """Run audit-query: query audit_trail JSONL with filters, print results."""
    try:
        from app.audit import (
            build_audit_query_filter,
            query_audit_trail,
            format_audit_query_result,
        )
    except Exception as exc:
        print(json.dumps({"error": f"import_failed:{exc}"}))
        return 1

    # Build filter from CLI args
    filters = build_audit_query_filter(
        event_type=args.event_type,
        source_command=args.source_command,
        status=args.status,
        write_mode=args.write_mode,
        sensitivity_level=args.sensitivity_level,
        payload_hash=args.payload_hash,
        audit_record_id=args.audit_record_id,
        start_time=args.start_time,
        end_time=args.end_time,
        limit=args.limit,
        offset=0,
        order=args.order,
    )

    query_result = query_audit_trail(
        root=str(ROOT),
        target_id=args.target_id,
        filters=filters,
        output_format=args.format,
    )

    formatted = format_audit_query_result(query_result, args.format)
    if args.format == "json":
        print(json.dumps(formatted, ensure_ascii=False, indent=2))
    else:
        print(formatted)

    if query_result.get("status") in ("no_records", "ok", "partial_warning"):
        return 0
    return 1


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def _run_audit_trend(args: Any) -> int:
    """Run guarded audit-trend: dry-run trend projection from existing audit JSONL."""
    try:
        from app.audit import format_trend_report, run_guarded_audit_trend_cli_projection
    except Exception as exc:
        print(json.dumps({"error": f"import_failed:{exc}"}))
        return 1

    guarded = run_guarded_audit_trend_cli_projection(
        root=str(ROOT),
        window=args.window,
        output_format=args.format,
        write_report=args.write_trend_report,
        report_format=args.report_format,
        output_prefix=args.output_prefix,
        start_time=args.start_time,
        end_time=args.end_time,
        limit=args.limit,
    )
    report = guarded.get("trend_report", {})
    formatted = guarded.get("formatted_output")
    guard = guarded.get("guard", {})
    guard_summary = {
        "guard_id": guard.get("guard_id"),
        "command_mode": guard.get("command_mode"),
        "audit_jsonl_unchanged": guard.get("audit_jsonl_unchanged"),
        "write_report_allowed": guard.get("write_report_allowed"),
        "runtime_write_detected": guard.get("runtime_write_detected"),
        "network_call_detected": guard.get("network_call_detected"),
        "sensitive_output_detected": guard.get("sensitive_output_detected"),
        "auto_fix_detected": guard.get("auto_fix_detected"),
        "warnings": guard.get("warnings", []),
        "errors": guard.get("errors", []),
    }
    if args.format == "json":
        print(json.dumps({
            "trend_report": formatted,
            "guard_summary": guard_summary,
            "artifact_bundle": guarded.get("artifact_bundle"),
        }, ensure_ascii=False, indent=2))
    else:
        print(formatted)
        print(f"guard_summary={json.dumps(guard_summary, ensure_ascii=False)}")
        if guarded.get("artifact_bundle"):
            statuses = [artifact.get("status") for artifact in guarded.get("artifact_bundle", {}).get("artifacts", [])]
            print(f"trend_report_artifact_bundle statuses={statuses}")
    if guard.get("errors"):
        return 1
    return 0 if report.get("status") in ("ok", "partial_warning", "insufficient_data") else 1


def _run_audit_trend_feishu(args: Any) -> int:
    """Run guarded audit-trend-feishu: dry-run Feishu trend payload preview.

    This command generates a Feishu card payload projection from the trend report
    and guard results, formats it for human review, and prints it.
    No Feishu message is sent. No webhook is called. No audit JSONL is written.
    """
    try:
        from app.audit import run_feishu_trend_preview_diagnostic
    except Exception as exc:
        print(json.dumps({"error": f"import_failed:{exc}"}))
        return 1

    diagnostic = run_feishu_trend_preview_diagnostic(
        window=args.window,
        format=args.format,
        root=str(ROOT),
    )
    status = diagnostic.get("status", "failed")
    preview = diagnostic.get("preview", "")
    validation = diagnostic.get("validation") or {}

    if args.format == "json":
        output = {
            "status": status,
            "preview": preview,
            "payload_id": diagnostic.get("payload_id"),
            "validation": validation,
            "preview_format": diagnostic.get("preview_format"),
            "generated_at": diagnostic.get("generated_at"),
            "warnings": diagnostic.get("warnings", []),
            "errors": diagnostic.get("errors", []),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(preview)

    if status in ("success", "no_data"):
        return 0
    return 1


def _run_audit_trend_feishu_presend(args: Any) -> int:
    """Run audit-trend-feishu-presend --validate-only: pre-send policy validation.

    R241-14C: Wraps run_feishu_presend_validate_only_cli() and formats output.
    This command validates a Feishu trend payload against the manual send policy
    without sending any Feishu message, calling webhooks, or reading secrets.

    This command ALWAYS requires --validate-only (implied by the command name).
    Does NOT accept: --send, --push, --webhook-url, --token, --secret, --auto-fix.
    """
    try:
        from app.audit import run_feishu_presend_validate_only_cli, format_presend_validation_result
    except Exception as exc:
        print(json.dumps({"error": f"import_failed:{exc}"}))
        return 1

    # Force preview_first based on whether we want to generate payload first
    preview_first = True  # Always generate preview for validate-only context

    cli_result = run_feishu_presend_validate_only_cli(
        window=args.window,
        confirmation_phrase=args.confirmation,
        webhook_ref_type=args.webhook_ref_type,
        webhook_ref_name=args.webhook_ref_name,
        output_format=args.format,
        preview_first=preview_first,
    )
    formatted = format_presend_validation_result(cli_result, args.format)
    if args.format == "json":
        print(json.dumps(formatted, ensure_ascii=False, indent=2))
    else:
        print(formatted)

    status = cli_result.get("status", "unknown")
    if status in ("valid", "partial_warning"):
        return 0
    if status == "blocked":
        return 2  # blocked but valid structure
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Internal read-only foundation diagnostics (Phase A+B+C+D)")
    parser.add_argument("command", choices=["truth-state", "queue-sandbox", "memory", "asset", "prompt", "rtcm", "nightly", "feishu-summary", "audit-trend", "audit-trend-feishu", "audit-trend-feishu-presend", "all", "audit-scan", "audit-query"])
    parser.add_argument("--format", choices=["json", "jsonl", "csv", "text", "markdown"], default="json")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-files", type=int, default=500)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--append-audit", action="store_true")
    # audit-query/scan filters
    parser.add_argument("--event-type", type=str, default=None)
    parser.add_argument("--source-command", type=str, default=None)
    parser.add_argument("--status", type=str, default=None)
    parser.add_argument("--write-mode", type=str, default=None)
    parser.add_argument("--sensitivity-level", type=str, default=None)
    parser.add_argument("--payload-hash", type=str, default=None)
    parser.add_argument("--audit-record-id", type=str, default=None)
    parser.add_argument("--start-time", type=str, default=None)
    parser.add_argument("--end-time", type=str, default=None)
    parser.add_argument("--target-id", type=str, default=None)
    parser.add_argument("--order", choices=["asc", "desc"], default="asc")
    parser.add_argument("--window", choices=["last_24h", "last_7d", "last_30d", "all_available", "custom"], default="all_available")
    parser.add_argument("--write-trend-report", action="store_true")
    parser.add_argument("--report-format", choices=["json", "markdown", "text", "all"], default="json")
    parser.add_argument("--output-prefix", type=str, default="R241-12D_TREND_REPORT_ARTIFACT")
    # audit-trend-feishu-presend (R241-14C)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--confirmation", type=str, default=None)
    parser.add_argument("--webhook-ref-type", choices=["env", "secret_manager"], default=None)
    parser.add_argument("--webhook-ref-name", type=str, default=None)
    args = parser.parse_args(argv)

    # audit-scan: scan existing JSONL files, print summary, exit
    if args.command == "audit-scan":
        return _run_audit_scan(args)

    # audit-query: query JSONL with filters, print results, exit
    if args.command == "audit-query":
        return _run_audit_query(args)

    # audit-trend: dry-run trend projection, no JSONL append and no runtime writes
    if args.command == "audit-trend":
        return _run_audit_trend(args)

    # audit-trend-feishu: dry-run Feishu trend payload preview, no send, no webhook
    if args.command == "audit-trend-feishu":
        return _run_audit_trend_feishu(args)

    # audit-trend-feishu-presend: validate-only pre-send policy check (R241-14C)
    if args.command == "audit-trend-feishu-presend":
        return _run_audit_trend_feishu_presend(args)

    if args.command == "truth-state":
        result = run_truth_state_diagnostic(format=args.format, limit=args.limit)
    elif args.command == "queue-sandbox":
        result = run_queue_sandbox_diagnostic(format=args.format, limit=args.limit)
    elif args.command == "memory":
        result = run_memory_diagnostic(format=args.format, max_files=args.max_files)
    elif args.command == "asset":
        result = run_asset_diagnostic(format=args.format, limit=args.limit)
    elif args.command == "prompt":
        result = run_prompt_diagnostic(format=args.format, max_files=args.max_files)
    elif args.command == "rtcm":
        result = run_rtcm_diagnostic(format=args.format, max_files=args.max_files * 2)
    elif args.command == "nightly":
        result = run_nightly_diagnostic(format=args.format, max_files=args.max_files)
    elif args.command == "feishu-summary":
        result = run_feishu_summary_diagnostic(format=args.format)
    elif args.command == "all":
        result = run_all_diagnostics(
            format=args.format,
            limit=args.limit,
            max_files=args.max_files,
            write_report=args.write_report,
            append_audit=args.append_audit,
        )
    else:
        return 1

    formatted = format_diagnostic_result(result, args.format)
    if args.format == "json":
        print(json.dumps(formatted, ensure_ascii=False, indent=2))
    else:
        print(formatted)
    return 0 if result.get("status") in {"ok", "partial_warning", "projection_only"} else 1


# ─────────────────────────────────────────────────────────────────────────────
# Sample Generator (Phase B)
# ─────────────────────────────────────────────────────────────────────────────


def generate_readonly_diagnostic_cli_expansion_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH_PHASE_B
    truth = run_truth_state_diagnostic(limit=20)
    queue = run_queue_sandbox_diagnostic(limit=20)
    memory = run_memory_diagnostic(max_files=100)
    asset = run_asset_diagnostic(limit=50)
    prompt = run_prompt_diagnostic(max_files=100)
    rtcm = run_rtcm_diagnostic(max_files=200)
    nightly = run_nightly_diagnostic(max_files=100)
    all_result = run_all_diagnostics(limit=20, max_files=100, write_report=False)

    all_warnings = _dedupe(
        truth.get("warnings", [])
        + queue.get("warnings", [])
        + memory.get("warnings", [])
        + asset.get("warnings", [])
        + prompt.get("warnings", [])
        + rtcm.get("warnings", [])
        + nightly.get("warnings", [])
        + all_result.get("warnings", [])
    )
    payload = {
        "command_registry": get_diagnostic_command_registry(),
        "truth_state_diagnostic": truth,
        "queue_sandbox_diagnostic": queue,
        "memory_diagnostic": memory,
        "asset_diagnostic": asset,
        "prompt_diagnostic": prompt,
        "rtcm_diagnostic": rtcm,
        "nightly_diagnostic": nightly,
        "all_diagnostics": all_result,
        "generated_at": _now(),
        "warnings": all_warnings,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(target), **payload}


# ─────────────────────────────────────────────────────────────────────────────
# Sample Generator (Phase C)
# ─────────────────────────────────────────────────────────────────────────────


def generate_feishu_summary_dryrun_cli_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH_PHASE_C
    feishu = run_feishu_summary_diagnostic()
    all_result = run_all_diagnostics(limit=20, max_files=100, write_report=False)

    all_warnings = _dedupe(feishu.get("warnings", []) + all_result.get("warnings", []))
    payload = {
        "command_registry": get_diagnostic_command_registry(),
        "feishu_summary_diagnostic": feishu,
        "all_diagnostics": all_result,
        "generated_at": _now(),
        "warnings": all_warnings,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(target), **payload}


# ─────────────────────────────────────────────────────────────────────────────
# Sample Generator (Phase D / R241-11B)
# ─────────────────────────────────────────────────────────────────────────────


def generate_dryrun_audit_record_projection_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate sample output with audit_record and audit_validation fields.

    R241-11B Phase 2: verifies audit record projection without writing JSONL.
    """
    target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH_PHASE_D
    truth = run_truth_state_diagnostic(limit=20)
    queue = run_queue_sandbox_diagnostic(limit=20)
    memory = run_memory_diagnostic(max_files=100)
    asset = run_asset_diagnostic(limit=50)
    prompt = run_prompt_diagnostic(max_files=100)
    rtcm = run_rtcm_diagnostic(max_files=200)
    nightly = run_nightly_diagnostic(max_files=100)
    feishu = run_feishu_summary_diagnostic()
    all_result = run_all_diagnostics(limit=20, max_files=100, write_report=False)

    all_warnings = _dedupe(
        truth.get("warnings", [])
        + queue.get("warnings", [])
        + memory.get("warnings", [])
        + asset.get("warnings", [])
        + prompt.get("warnings", [])
        + rtcm.get("warnings", [])
        + nightly.get("warnings", [])
        + feishu.get("warnings", [])
        + all_result.get("warnings", [])
    )
    payload = {
        "command_registry": get_diagnostic_command_registry(),
        "truth_state_diagnostic": truth,
        "queue_sandbox_diagnostic": queue,
        "memory_diagnostic": memory,
        "asset_diagnostic": asset,
        "prompt_diagnostic": prompt,
        "rtcm_diagnostic": rtcm,
        "nightly_diagnostic": nightly,
        "feishu_summary_diagnostic": feishu,
        "all_diagnostics": all_result,
        "generated_at": _now(),
        "warnings": all_warnings,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(target), **payload}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _run_result(
    command: str,
    status: str,
    format: str,
    summary: Dict[str, Any],
    payload: Dict[str, Any],
    warnings: List[str],
    errors: List[str],
) -> Dict[str, Any]:
    return asdict(
        DiagnosticRunResult(
            command=command if command in DIAGNOSTIC_COMMANDS else "unknown",
            status=status if status in EXIT_STATUSES else "failed",
            generated_at=_now(),
            root=str(ROOT),
            format=_format(format),
            summary=summary,
            payload=payload,
            warnings=_dedupe(warnings),
            errors=_dedupe(errors),
        )
    )


def _safe_call(func: Any, warnings: List[str], **kwargs: Any) -> Dict[str, Any]:
    try:
        result = func(**kwargs)
        return result if isinstance(result, dict) else {"warnings": [f"{getattr(func, '__name__', 'call')}_returned_non_dict"]}
    except Exception as exc:
        warning = f"{getattr(func, '__name__', 'call')}_failed:{exc}"
        warnings.append(warning)
        return {"warnings": [warning]}


def _status(warnings: List[str], errors: List[str]) -> str:
    if errors:
        return "failed"
    if warnings:
        return "partial_warning"
    return "ok"


def _format(format: str) -> str:
    return format if format in OUTPUT_FORMATS else "json"


def _excluded_governance_or_observation_count(candidates: Dict[str, Any]) -> int:
    excluded = candidates.get("excluded_reasons")
    if isinstance(excluded, dict):
        total = 0
        for key, value in excluded.items():
            text = str(key)
            if any(marker in text for marker in ["observation", "approval", "governance", "asset", "rtcm"]):
                try:
                    total += int(value)
                except Exception:
                    pass
        return total
    return int(candidates.get("ineligible_count") or 0)


def _find_queue_warning(warnings: List[str]) -> Optional[str]:
    for warning in warnings:
        text = str(warning).lower()
        if "queue" in text and ("missing" in text or "mismatch" in text or "does_not_exist" in text):
            return str(warning)
    return None


def _compact_payload(data: Dict[str, Any], max_items: int = 20) -> Dict[str, Any]:
    """Remove large list fields from payload for compact output."""
    compact = dict(data)
    for key in ("records", "candidates", "risk_records", "eligible_events", "representative_records"):
        if key in compact and isinstance(compact[key], list):
            items = compact[key]
            compact[f"{key}_total_count"] = len(items)
            compact[key] = items[:max_items]
    return compact


def _format_markdown(result: Dict[str, Any]) -> str:
    command = result.get("command")
    lines = [
        f"# foundation diagnose {command}",
        "",
        f"- status: `{result.get('status')}`",
        f"- generated_at: `{result.get('generated_at')}`",
        f"- warnings: `{len(result.get('warnings') or [])}`",
        f"- errors: `{len(result.get('errors') or [])}`",
        "",
        "## Summary",
    ]
    summary = result.get("summary") or {}
    for key, value in summary.items():
        if isinstance(value, dict):
            lines.append(f"- `{key}`:")
            for sub_key, sub_value in value.items():
                lines.append(f"  - `{sub_key}`: `{sub_value}`")
        elif isinstance(value, list):
            lines.append(f"- `{key}`: `{len(value)} items`")
            for item in value[:10]:
                lines.append(f"  - `{item}`")
        else:
            lines.append(f"- `{key}`: `{value}`")

    # Feishu-specific projection fields
    if command == "feishu-summary":
        feishu_keys = ["send_allowed", "webhook_required", "feishu_payload_status", "validation_valid", "no_webhook_call", "no_runtime_write"]
        for key in feishu_keys:
            if key in summary:
                lines.append(f"- `{key}`: `{summary[key]}`")

    if result.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in result.get("warnings", [])[:20])
    if result.get("errors"):
        lines.extend(["", "## Errors"])
        lines.extend(f"- {error}" for error in result.get("errors", [])[:20])
    if result.get("audit_record"):
        audit = result["audit_record"]
        lines.extend(["", "## Audit Record"])
        lines.append(f"- event_type: `{audit.get('event_type', 'unknown')}`")
        lines.append(f"- write_mode: `{audit.get('write_mode', 'unknown')}`")
        lines.append(f"- sensitivity_level: `{audit.get('sensitivity_level', 'unknown')}`")
        lines.append(f"- payload_hash: `{audit.get('payload_hash', 'none')[:16]}...`")
        lines.append(f"- redaction_applied: `{audit.get('redaction_applied', False)}`")
        validation = result.get("audit_validation") or {}
        lines.append(f"- audit_valid: `{validation.get('valid', 'unknown')}`")
    return "\n".join(lines)


def _format_text(result: Dict[str, Any]) -> str:
    command = result.get("command")
    lines = [
        f"foundation diagnose {command}",
        f"status={result.get('status')}",
        f"warnings={len(result.get('warnings') or [])}",
        f"errors={len(result.get('errors') or [])}",
        "summary:",
    ]
    summary = result.get("summary") or {}
    for key, value in summary.items():
        if isinstance(value, dict):
            lines.append(f"  {key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"    {sub_key}: {sub_value}")
        elif isinstance(value, list):
            lines.append(f"  {key}: {len(value)} items")
        else:
            lines.append(f"  {key}: {value}")

    # Feishu-specific projection fields
    if command == "feishu-summary":
        feishu_keys = ["send_allowed", "webhook_required", "feishu_payload_status", "validation_valid", "no_webhook_call", "no_runtime_write"]
        for key in feishu_keys:
            if key in summary:
                lines.append(f"  {key}: {summary[key]}")

    if result.get("warnings"):
        lines.append("warnings:")
        lines.extend(f"  - {warning}" for warning in result.get("warnings", [])[:20])
    if result.get("audit_record"):
        audit = result["audit_record"]
        lines.append("audit_record:")
        lines.append(f"  event_type: {audit.get('event_type', 'unknown')}")
        lines.append(f"  write_mode: {audit.get('write_mode', 'unknown')}")
        lines.append(f"  sensitivity_level: {audit.get('sensitivity_level', 'unknown')}")
        lines.append(f"  payload_hash: {str(audit.get('payload_hash', 'none'))[:16]}...")
        lines.append(f"  redaction_applied: {audit.get('redaction_applied', False)}")
        validation = result.get("audit_validation") or {}
        lines.append(f"  audit_valid: {validation.get('valid', 'unknown')}")
    return "\n".join(lines)


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
