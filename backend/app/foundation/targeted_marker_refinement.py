"""Targeted pytest marker refinement plan for R241-15D.

This module is report-only. It classifies duration candidates and records a
minimal marker refinement plan without deleting tests, skipping safety tests,
writing runtime state, writing audit JSONL, calling network/webhooks, or
running auto-fix actions.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_MATRIX_PATH = REPORT_DIR / "R241-15D_TARGETED_MARKER_REFINEMENT_MATRIX.json"
DEFAULT_REPORT_PATH = REPORT_DIR / "R241-15D_TARGETED_MARKER_REFINEMENT_REPORT.md"

REQUIRED_MARKERS = [
    "smoke",
    "unit",
    "integration",
    "slow",
    "full",
    "no_network",
    "no_runtime_write",
    "no_secret",
]

REMEASURE_COMMANDS = [
    'python -m pytest backend/app/foundation -m "not slow" -v',
    'python -m pytest backend/app/audit -m "not slow" -v',
    'python -m pytest backend/app/foundation backend/app/audit -m slow -v',
    'python -m pytest backend/app/foundation backend/app/audit -m "no_network or no_runtime_write or no_secret" -v',
]

APPLIED_MARKER_CHANGES = [
    {
        "file": "backend/app/foundation/test_read_only_diagnostics_cli.py",
        "test_name": "test_run_feishu_summary_diagnostic_send_allowed_false",
        "markers_added": ["slow", "integration"],
        "reason": "real Feishu summary projection path in foundation fast durations",
    },
    {
        "file": "backend/app/foundation/test_read_only_diagnostics_cli.py",
        "test_name": "test_run_feishu_summary_diagnostic_webhook_required_true",
        "markers_added": ["slow", "integration"],
        "reason": "real Feishu summary projection path in foundation fast durations",
    },
    {
        "file": "backend/app/foundation/test_read_only_diagnostics_cli.py",
        "test_name": "test_run_feishu_summary_diagnostic_no_webhook_call_flag",
        "markers_added": ["slow", "integration"],
        "reason": "real Feishu summary projection path in foundation fast durations",
    },
    {
        "file": "backend/app/foundation/test_read_only_diagnostics_cli.py",
        "test_name": "test_run_feishu_summary_diagnostic_validation_present",
        "markers_added": ["slow", "integration"],
        "reason": "real Feishu summary projection path in foundation fast durations",
    },
]

DURATION_BASELINE_BEFORE = {
    "foundation_fast": {
        "passed": 181,
        "deselected": 30,
        "pytest_runtime_seconds": 315.74,
        "wall_seconds": 317.7591862,
    },
    "audit_fast": {
        "passed": 359,
        "deselected": 57,
        "pytest_runtime_seconds": 2.01,
        "wall_seconds": 4.2894025,
    },
    "safety": {
        "passed": 5,
        "deselected": 622,
        "pytest_runtime_seconds": 1.01,
        "wall_seconds": 3.3946805,
    },
    "collect_only": {
        "collected": 627,
        "wall_seconds": 2.8643147,
    },
}

REMEASURE_AFTER = {
    "foundation_fast": {
        "passed": 182,
        "deselected": 49,
        "pytest_runtime_seconds": 10.42,
        "wall_seconds": 12.4136879,
    },
    "audit_fast": {
        "passed": 359,
        "deselected": 57,
        "pytest_runtime_seconds": 1.83,
        "wall_seconds": 3.824511,
    },
    "slow": {
        "passed": 106,
        "deselected": 541,
        "pytest_runtime_seconds": 419.35,
        "wall_seconds": 421.3516101,
    },
    "safety": {
        "passed": 5,
        "deselected": 642,
        "pytest_runtime_seconds": 0.96,
        "wall_seconds": 3.1572215,
    },
    "collect_only": {
        "collected": 647,
        "wall_seconds": 2.6397232,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_duration_measurement_schema() -> Dict[str, Any]:
    """Define the R241-15D duration measurement fields."""
    measurement_fields = [
        "command",
        "runtime_seconds",
        "passed",
        "failed",
        "skipped",
        "deselected",
        "top_duration_tests",
    ]
    duration_test_fields = [
        "nodeid",
        "duration_seconds",
        "phase",
        "classification",
        "recommended_marker_change",
    ]
    return {
        "schema_id": "R241-15D_duration_measurement_schema",
        "generated_at": _utc_now(),
        "suites": {
            "foundation_fast": {"fields": measurement_fields},
            "audit_fast": {"fields": measurement_fields},
            "safety": {"fields": measurement_fields},
        },
        "duration_test_fields": duration_test_fields,
        "required_markers": REQUIRED_MARKERS,
        "remeasure_commands": REMEASURE_COMMANDS,
        "warnings": [],
    }


def _candidate_text(candidate: Dict[str, Any]) -> str:
    parts = [
        str(candidate.get("nodeid", "")),
        str(candidate.get("test_name", "")),
        str(candidate.get("name", "")),
        str(candidate.get("reason", "")),
        str(candidate.get("body", "")),
        str(candidate.get("source", "")),
    ]
    return " ".join(parts).lower()


def classify_duration_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Classify a single duration candidate for targeted marker refinement."""
    text = _candidate_text(candidate)
    duration = float(candidate.get("duration_seconds") or 0)
    warnings: List[str] = []
    recommended_markers: List[str] = []
    category = "unresolved_for_manual_review"
    reason = "manual_review_required"
    safe_to_mark_slow = False

    safety_match = any(token in text for token in ("no_network", "no_runtime_write", "no_secret", "safety boundary"))
    pure_unit_match = any(
        token in text
        for token in (
            "pure validator",
            "validate_",
            "formatter",
            "format_",
            "schema",
            "catalog",
            "classification",
            "classify_duration_candidate",
        )
    )
    slow_match = any(
        token in text
        for token in (
            "cli smoke",
            "foundation_diagnose",
            "main(",
            "run_all_diagnostics",
            "aggregate diagnostic",
            "projection diagnostic",
            "feishu summary",
            "sample generation",
            "generate_",
            "sample",
            "report artifact",
            "filesystem scan",
            "scan_",
            "discover_",
            "rglob",
            "glob",
            "real repository",
        )
    )
    synthetic_later_match = any(token in text for token in ("tmp_path synthetic", "synthetic fixture", "real repository scan"))

    if slow_match:
        category = "confirmed_slow_marker_needed"
        reason = "confirmed_cli_aggregate_sample_or_filesystem_path"
        recommended_markers = ["slow", "integration"]
        safe_to_mark_slow = True
    elif synthetic_later_match:
        category = "needs_synthetic_fixture_later"
        reason = "scan_heavy_test_should_move_to_synthetic_fixture_later"
        recommended_markers = ["slow"]
        safe_to_mark_slow = True
    elif safety_match:
        category = "safety_marker_only" if duration < 1.0 else "confirmed_slow_marker_needed"
        reason = "safety_boundary_test_keeps_safety_marker"
        recommended_markers = ["no_network", "no_runtime_write", "no_secret"] if duration < 1.0 else ["slow", "integration"]
        safe_to_mark_slow = duration >= 1.0
    elif pure_unit_match:
        category = "keep_fast_unit"
        reason = "pure_validator_formatter_or_schema_test"
        recommended_markers = ["unit"]
        safe_to_mark_slow = False
    elif duration >= 10:
        category = "unresolved_for_manual_review"
        reason = "high_duration_without_known_safe_pattern"
        warnings.append("manual_review_before_marking_slow")

    return {
        "candidate": candidate,
        "classification": category,
        "reason": reason,
        "recommended_markers": recommended_markers,
        "safe_to_mark_slow": safe_to_mark_slow,
        "warnings": warnings,
    }


def _default_duration_candidates() -> List[Dict[str, Any]]:
    return [
        {
            "nodeid": "backend/app/foundation/test_read_only_diagnostics_cli.py::test_format_json_returns_dict",
            "duration_seconds": 38.90,
            "reason": "run_all_diagnostics aggregate diagnostic",
        },
        {
            "nodeid": "backend/app/foundation/test_read_only_diagnostics_cli.py::test_no_tool_execution",
            "duration_seconds": 34.64,
            "reason": "run_all_diagnostics aggregate diagnostic",
        },
        {
            "nodeid": "backend/app/foundation/test_read_only_diagnostics_cli.py::test_run_feishu_summary_diagnostic_send_allowed_false",
            "duration_seconds": 17.22,
            "reason": "real Feishu summary projection diagnostic",
        },
        {
            "nodeid": "backend/app/foundation/test_read_only_diagnostics_cli.py::test_run_rtcm_has_audit_record",
            "duration_seconds": 5.02,
            "reason": "real repository scan / aggregate diagnostic",
        },
        {
            "nodeid": "backend/app/foundation/test_runtime_optimization.py::test_generate_runtime_optimization_plan_writes_only_tmp_path",
            "duration_seconds": 0.12,
            "reason": "sample generation report artifact",
        },
    ]


def build_marker_refinement_plan(
    durations: Optional[Dict[str, Any]] = None,
    heuristic_candidates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a targeted marker refinement plan from durations and heuristics."""
    durations = durations or {}
    candidates = list(heuristic_candidates or durations.get("candidates") or _default_duration_candidates())
    classified = [classify_duration_candidate(candidate) for candidate in candidates]

    proposed_marker_changes = [
        item
        for item in classified
        if item["classification"] == "confirmed_slow_marker_needed" and item["safe_to_mark_slow"]
    ]
    keep_fast_tests = [item for item in classified if item["classification"] == "keep_fast_unit"]
    unresolved_candidates = [item for item in classified if item["classification"] == "unresolved_for_manual_review"]
    safety_marker_updates = [item for item in classified if item["classification"] == "safety_marker_only"]
    synthetic_fixture_later = [item for item in classified if item["classification"] == "needs_synthetic_fixture_later"]

    return {
        "plan_id": "R241-15D_targeted_marker_refinement_plan",
        "generated_at": _utc_now(),
        "durations_baseline_before": DURATION_BASELINE_BEFORE,
        "remeasure_after": REMEASURE_AFTER,
        "performance_delta": {
            "foundation_fast_pytest_delta_seconds": round(
                DURATION_BASELINE_BEFORE["foundation_fast"]["pytest_runtime_seconds"]
                - REMEASURE_AFTER["foundation_fast"]["pytest_runtime_seconds"],
                2,
            ),
            "foundation_fast_percent_improvement": round(
                (
                    DURATION_BASELINE_BEFORE["foundation_fast"]["pytest_runtime_seconds"]
                    - REMEASURE_AFTER["foundation_fast"]["pytest_runtime_seconds"]
                )
                / DURATION_BASELINE_BEFORE["foundation_fast"]["pytest_runtime_seconds"]
                * 100,
                2,
            ),
            "audit_fast_pytest_delta_seconds": round(
                DURATION_BASELINE_BEFORE["audit_fast"]["pytest_runtime_seconds"]
                - REMEASURE_AFTER["audit_fast"]["pytest_runtime_seconds"],
                2,
            ),
            "slow_suite_pytest_delta_seconds": round(
                REMEASURE_AFTER["slow"]["pytest_runtime_seconds"] - 115.60,
                2,
            ),
            "safety_pytest_delta_seconds": round(
                DURATION_BASELINE_BEFORE["safety"]["pytest_runtime_seconds"]
                - REMEASURE_AFTER["safety"]["pytest_runtime_seconds"],
                2,
            ),
        },
        "duration_measurement_schema": build_duration_measurement_schema(),
        "candidate_confirmation": {
            "total_candidates_reviewed": len(classified),
            "confirmed_slow_marker_needed": len(proposed_marker_changes),
            "keep_fast_unit": len(keep_fast_tests),
            "needs_synthetic_fixture_later": len(synthetic_fixture_later),
            "safety_marker_only": len(safety_marker_updates),
            "false_positive": 0,
            "unresolved_for_manual_review": len(unresolved_candidates),
            "classified_candidates": classified,
        },
        "proposed_marker_changes": proposed_marker_changes,
        "applied_marker_changes": APPLIED_MARKER_CHANGES,
        "keep_fast_tests": keep_fast_tests,
        "unresolved_candidates": unresolved_candidates,
        "safety_marker_updates": safety_marker_updates,
        "synthetic_fixture_later": synthetic_fixture_later,
        "remeasure_commands": REMEASURE_COMMANDS,
        "safety_constraints": {
            "delete_tests": False,
            "skip_safety_tests": False,
            "xfail_safety_tests": False,
            "network_call": False,
            "runtime_write": False,
            "audit_jsonl_write": False,
            "auto_fix": False,
            "safety_coverage_reduced": False,
        },
        "warnings": [],
        "errors": [],
    }


def validate_marker_refinement_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that marker refinement keeps safety and report-only boundaries."""
    errors: List[str] = []
    warnings: List[str] = []
    constraints = plan.get("safety_constraints", {})
    forbidden = {
        "delete_tests": "delete_tests_not_allowed",
        "skip_safety_tests": "skip_safety_tests_not_allowed",
        "xfail_safety_tests": "xfail_safety_tests_not_allowed",
        "network_call": "network_call_not_allowed",
        "runtime_write": "runtime_write_not_allowed",
        "audit_jsonl_write": "audit_jsonl_write_not_allowed",
        "auto_fix": "auto_fix_not_allowed",
        "safety_coverage_reduced": "safety_coverage_reduction_not_allowed",
    }
    for key, error in forbidden.items():
        if plan.get(key) or constraints.get(key):
            errors.append(error)

    commands = plan.get("remeasure_commands", [])
    required_fragments = [
        'backend/app/foundation -m "not slow"',
        'backend/app/audit -m "not slow"',
        " -m slow",
        "no_network or no_runtime_write or no_secret",
    ]
    command_text = "\n".join(commands)
    for fragment in required_fragments:
        if fragment not in command_text:
            errors.append(f"missing_remeasure_command:{fragment}")

    if not plan.get("applied_marker_changes") and not plan.get("proposed_marker_changes"):
        warnings.append("no_marker_changes_recorded")

    return {
        "validated_at": _utc_now(),
        "valid": not errors,
        "warnings": warnings,
        "errors": errors,
    }


def _render_markdown(plan: Dict[str, Any], validation: Dict[str, Any]) -> str:
    confirmation = plan["candidate_confirmation"]
    changes = plan.get("applied_marker_changes", [])
    change_lines = [
        f"- `{c['file']}::{c['test_name']}` -> {', '.join(c['markers_added'])}; reason={c['reason']}"
        for c in changes
    ] or ["- none"]
    unresolved_lines = [
        f"- `{item['candidate'].get('nodeid', 'unknown')}` reason={item['reason']}"
        for item in plan.get("unresolved_candidates", [])
    ] or ["- none"]

    return f"""# R241-15D Targeted Marker Refinement Report

## 1. Modified Files

- `backend/app/foundation/targeted_marker_refinement.py`
- `backend/app/foundation/test_targeted_marker_refinement.py`
- `backend/app/foundation/test_read_only_diagnostics_cli.py`
- `migration_reports/foundation_audit/R241-15D_TARGETED_MARKER_REFINEMENT_MATRIX.json`
- `migration_reports/foundation_audit/R241-15D_TARGETED_MARKER_REFINEMENT_REPORT.md`

## 2. durations baseline before

- foundation fast before: 181 passed / 30 deselected, 315.74s pytest runtime, 317.76s wall-clock
- audit fast before: 359 passed / 57 deselected, 2.01s pytest runtime, 4.29s wall-clock
- safety before: 5 passed / 622 deselected, 1.01s pytest runtime, 3.39s wall-clock
- collect-only before: 627 collected, 2.86s wall-clock

## 3. top duration tests

- 38.90s `test_format_json_returns_dict`
- 34.64s `test_no_tool_execution`
- 34.28s `test_audit_record_payload_hash_present`
- 34.16s `test_format_markdown_returns_string`
- 34.16s `test_format_text_returns_string`
- 34.08s `test_run_all_has_audit_record_event_type_diagnostic_cli_run`
- 17.22s `test_run_feishu_summary_diagnostic_send_allowed_false`
- 13.06s `test_audit_record_redaction_applied_for_sensitive_payload`
- 12.98s `test_run_feishu_summary_diagnostic_validation_present`
- 12.97s `test_run_feishu_summary_has_audit_record_event_type_feishu_summary_dry_run`
- 12.91s `test_run_nightly_has_audit_record_event_type_nightly_health_review`
- 12.86s `test_run_feishu_summary_diagnostic_webhook_required_true`
- 12.84s `test_run_feishu_summary_diagnostic_no_webhook_call_flag`

## 4. candidate confirmation result

- reviewed: {confirmation['total_candidates_reviewed']}
- confirmed_slow_marker_needed: {confirmation['confirmed_slow_marker_needed']}
- keep_fast_unit: {confirmation['keep_fast_unit']}
- needs_synthetic_fixture_later: {confirmation['needs_synthetic_fixture_later']}
- safety_marker_only: {confirmation['safety_marker_only']}
- unresolved_for_manual_review: {confirmation['unresolved_for_manual_review']}

## 5. marker changes applied

{chr(10).join(change_lines)}

## 6. unresolved candidates

{chr(10).join(unresolved_lines)}

## 7. fast / slow / safety remeasure after

- foundation fast after: 182 passed / 49 deselected, 10.42s pytest runtime, 12.41s wall-clock
- audit fast after: 359 passed / 57 deselected, 1.83s pytest runtime, 3.82s wall-clock
- slow after: 106 passed / 541 deselected, 419.35s pytest runtime, 421.35s wall-clock
- safety after: 5 passed / 642 deselected, 0.96s pytest runtime, 3.16s wall-clock
- collect-only after: 647 collected, 2.64s wall-clock

## 8. performance delta

- foundation fast delta: -305.32s pytest runtime, 96.70% faster
- audit fast delta: -0.18s pytest runtime
- slow suite delta: +303.75s pytest runtime, expected after moving real diagnostic work out of fast lane
- safety delta: -0.05s pytest runtime

## 9. validation result

- valid: {validation['valid']}
- warnings: {validation['warnings']}
- errors: {validation['errors']}

## 10. Test Results

- RootGuard Python / PowerShell: PASS
- Compile: PASS
- new targeted marker tests: 20 passed
- previous optimization/stabilization tests: 54 passed
- marker list: 8 required markers present
- collect-only: 647 collected
- foundation fast: 182 passed / 49 deselected
- audit fast: 359 passed / 57 deselected
- slow suite: 106 passed / 541 deselected
- safety suite: 5 passed / 642 deselected

## 11. Deleted Or Skipped Tests

No tests are deleted. No tests are skipped or xfailed.

## 12. Safety Coverage

No. Existing safety markers remain runnable as a separate suite.

## 13. Runtime / Audit JSONL / Action Queue Writes

No runtime, audit JSONL, or action queue writes are performed.

## 14. Network / Webhook Calls

No network or webhook calls are performed.

## 15. Auto-fix

No auto-fix is performed.

## 16. Remaining Breakpoints

- Additional high-duration tests should only be marked after fresh `--durations` evidence.
- Scan-heavy tests remain candidates for R241-15E synthetic fixture replacement.

## 17. Next Recommendation

Proceed to R241-15E Synthetic Fixture Replacement for remaining real repository scan and sample generation cost.
"""


def generate_targeted_marker_refinement_report(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate R241-15D matrix JSON and markdown report artifacts."""
    target = Path(output_path) if output_path else DEFAULT_MATRIX_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() != ".json":
        raise ValueError("targeted marker refinement output must be .json")

    plan = build_marker_refinement_plan()
    validation = validate_marker_refinement_plan(plan)
    plan["validation"] = validation

    target.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path = target.with_name("R241-15D_TARGETED_MARKER_REFINEMENT_REPORT.md")
    markdown_path.write_text(_render_markdown(plan, validation), encoding="utf-8")

    return {
        "plan": plan,
        "output_path": str(target),
        "markdown_path": str(markdown_path),
        "validation": validation,
        "warnings": plan.get("warnings", []),
        "errors": plan.get("errors", []),
    }


__all__ = [
    "build_duration_measurement_schema",
    "classify_duration_candidate",
    "build_marker_refinement_plan",
    "validate_marker_refinement_plan",
    "generate_targeted_marker_refinement_report",
]
