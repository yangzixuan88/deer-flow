"""Synthetic fixture replacement plan for R241-15E.

This report-only helper documents replacing real repository scans and aggregate
diagnostics in slow tests with tmp_path/monkeypatch synthetic fixtures. It does
not alter production runtime logic, write audit JSONL, call network/webhooks, or
execute auto-fix actions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_MATRIX_PATH = REPORT_DIR / "R241-15E_SYNTHETIC_FIXTURE_REPLACEMENT_MATRIX.json"
DEFAULT_REPORT_PATH = REPORT_DIR / "R241-15E_SYNTHETIC_FIXTURE_REPLACEMENT_REPORT.md"

SLOW_DURATIONS_BEFORE = {
    "passed": 106,
    "deselected": 541,
    "pytest_runtime_seconds": 423.18,
    "wall_seconds": 425.410884,
    "top_duration_tests": [
        {"nodeid": "test_run_all_diagnostics_disabled_commands_empty", "duration_seconds": 38.69},
        {"nodeid": "test_format_markdown_returns_string", "duration_seconds": 34.77},
        {"nodeid": "test_run_all_has_audit_record_event_type_diagnostic_cli_run", "duration_seconds": 34.75},
        {"nodeid": "test_run_all_diagnostics_write_report_false_no_file", "duration_seconds": 34.71},
        {"nodeid": "test_format_text_returns_string", "duration_seconds": 34.61},
        {"nodeid": "test_no_tool_execution", "duration_seconds": 34.60},
        {"nodeid": "test_format_json_returns_dict", "duration_seconds": 34.53},
        {"nodeid": "test_audit_record_payload_hash_present", "duration_seconds": 34.52},
        {"nodeid": "test_run_all_diagnostics_write_report_true_writes_tmp_path", "duration_seconds": 34.47},
        {"nodeid": "test_run_feishu_summary_diagnostic_send_allowed_false", "duration_seconds": 18.02},
        {"nodeid": "test_run_feishu_summary_diagnostic_validation_present", "duration_seconds": 13.25},
        {"nodeid": "test_audit_record_redaction_applied_for_sensitive_payload", "duration_seconds": 13.12},
        {"nodeid": "test_run_nightly_has_audit_record_event_type_nightly_health_review", "duration_seconds": 13.06},
        {"nodeid": "test_run_feishu_summary_diagnostic_webhook_required_true", "duration_seconds": 13.04},
        {"nodeid": "test_run_feishu_summary_diagnostic_no_webhook_call_flag", "duration_seconds": 12.96},
        {"nodeid": "test_run_feishu_summary_has_audit_record_event_type_feishu_summary_dry_run", "duration_seconds": 12.95},
        {"nodeid": "test_run_rtcm_has_audit_record", "duration_seconds": 5.09},
        {"nodeid": "test_run_prompt_has_audit_record", "duration_seconds": 2.82},
    ],
}

REMEASURE_AFTER = {
    "slow": {
        "passed": 106,
        "deselected": 563,
        "pytest_runtime_seconds": 6.84,
        "wall_seconds": 9.0965092,
    },
    "foundation_fast": {
        "passed": 204,
        "deselected": 49,
        "pytest_runtime_seconds": 11.33,
        "wall_seconds": 13.6681695,
    },
    "audit_fast": {
        "passed": 359,
        "deselected": 57,
        "pytest_runtime_seconds": 2.37,
        "wall_seconds": 4.6760956,
    },
    "safety": {
        "passed": 5,
        "deselected": 664,
        "pytest_runtime_seconds": 1.07,
        "wall_seconds": 3.5364314,
    },
    "collect_only": {
        "collected": 669,
        "wall_seconds": 2.8567081,
    },
}

APPLIED_REPLACEMENTS = [
    {
        "file": "backend/app/foundation/test_read_only_diagnostics_cli.py",
        "tests": [
            "test_run_all_diagnostics_disabled_commands_empty",
            "test_run_all_diagnostics_write_report_false_no_file",
            "test_run_all_diagnostics_write_report_true_writes_tmp_path",
            "test_format_json_returns_dict",
            "test_format_markdown_returns_string",
            "test_format_text_returns_string",
            "test_no_tool_execution",
            "test_run_memory_has_audit_record",
            "test_run_asset_has_audit_record",
            "test_run_prompt_has_audit_record",
            "test_run_rtcm_has_audit_record",
            "test_run_nightly_has_audit_record_event_type_nightly_health_review",
            "test_run_feishu_summary_has_audit_record_event_type_feishu_summary_dry_run",
            "test_run_all_has_audit_record_event_type_diagnostic_cli_run",
            "test_audit_record_payload_hash_present",
            "test_audit_record_redaction_applied_for_sensitive_payload",
            "test_run_feishu_summary_diagnostic_send_allowed_false",
            "test_run_feishu_summary_diagnostic_webhook_required_true",
            "test_run_feishu_summary_diagnostic_no_webhook_call_flag",
            "test_run_feishu_summary_diagnostic_validation_present",
        ],
        "replacement": "monkeypatch synthetic diagnostic results with real audit_record helper",
        "preserved_semantics": [
            "command status aggregation",
            "report_path write to tmp_path",
            "format json/markdown/text contract",
            "audit_record event_type and payload_hash assertions",
            "Feishu projection safety flags",
        ],
    }
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_synthetic_fixture_schema() -> Dict[str, Any]:
    return {
        "schema_id": "R241-15E_synthetic_fixture_schema",
        "generated_at": _utc_now(),
        "fixture_types": [
            "tmp_path_artifact",
            "monkeypatch_diagnostic_result",
            "synthetic_audit_record",
            "synthetic_scan_summary",
        ],
        "required_fields": [
            "target_test",
            "original_slow_reason",
            "replacement_type",
            "semantic_assertions_preserved",
            "runtime_write_allowed",
            "network_allowed",
        ],
        "warnings": [],
    }


def classify_synthetic_fixture_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    text = " ".join(str(candidate.get(key, "")) for key in ("nodeid", "reason", "body")).lower()
    if any(token in text for token in ("run_all_diagnostics", "aggregate diagnostic", "diagnostic aggregation")):
        category = "replace_with_synthetic_diagnostic"
        replacement = "monkeypatch all child diagnostics"
    elif any(token in text for token in ("feishu summary", "nightly", "prompt", "rtcm")):
        category = "replace_with_synthetic_projection"
        replacement = "synthetic projection result with audit_record"
    elif any(token in text for token in ("sample", "report artifact", "write_report")):
        category = "replace_with_tmp_path_artifact"
        replacement = "tmp_path output and synthetic children"
    elif any(token in text for token in ("scan", "discover", "rglob", "filesystem")):
        category = "replace_with_synthetic_scan_fixture"
        replacement = "small tmp_path filesystem tree"
    else:
        category = "keep_real_boundary"
        replacement = "manual review before replacement"
    return {
        "candidate": candidate,
        "classification": category,
        "recommended_replacement": replacement,
        "safe_to_replace": category != "keep_real_boundary",
        "warnings": [] if category != "keep_real_boundary" else ["manual_review_required"],
    }


def build_synthetic_fixture_replacement_plan(candidates: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    candidates = candidates or SLOW_DURATIONS_BEFORE["top_duration_tests"]
    classified = [classify_synthetic_fixture_candidate(candidate) for candidate in candidates]
    return {
        "plan_id": "R241-15E_synthetic_fixture_replacement_plan",
        "generated_at": _utc_now(),
        "duration_baseline_before": SLOW_DURATIONS_BEFORE,
        "remeasure_after": REMEASURE_AFTER,
        "performance_delta": {
            "slow_pytest_delta_seconds": round(
                SLOW_DURATIONS_BEFORE["pytest_runtime_seconds"] - REMEASURE_AFTER["slow"]["pytest_runtime_seconds"],
                2,
            ),
            "slow_percent_improvement": round(
                (
                    SLOW_DURATIONS_BEFORE["pytest_runtime_seconds"]
                    - REMEASURE_AFTER["slow"]["pytest_runtime_seconds"]
                )
                / SLOW_DURATIONS_BEFORE["pytest_runtime_seconds"]
                * 100,
                2,
            ),
            "foundation_fast_pytest_runtime_seconds": REMEASURE_AFTER["foundation_fast"]["pytest_runtime_seconds"],
            "audit_fast_pytest_runtime_seconds": REMEASURE_AFTER["audit_fast"]["pytest_runtime_seconds"],
            "safety_pytest_runtime_seconds": REMEASURE_AFTER["safety"]["pytest_runtime_seconds"],
        },
        "synthetic_fixture_schema": build_synthetic_fixture_schema(),
        "candidate_classification": {
            "total_candidates": len(classified),
            "replace_with_synthetic_diagnostic": sum(
                1 for item in classified if item["classification"] == "replace_with_synthetic_diagnostic"
            ),
            "replace_with_synthetic_projection": sum(
                1 for item in classified if item["classification"] == "replace_with_synthetic_projection"
            ),
            "replace_with_tmp_path_artifact": sum(
                1 for item in classified if item["classification"] == "replace_with_tmp_path_artifact"
            ),
            "replace_with_synthetic_scan_fixture": sum(
                1 for item in classified if item["classification"] == "replace_with_synthetic_scan_fixture"
            ),
            "keep_real_boundary": sum(1 for item in classified if item["classification"] == "keep_real_boundary"),
            "classified_candidates": classified,
        },
        "applied_replacements": APPLIED_REPLACEMENTS,
        "preserved_coverage": [
            "audit_record generation still uses add_audit_record_to_diagnostic_result",
            "formatters still operate on DiagnosticRunResult-like structures",
            "write_report tests still write only tmp_path files",
            "Feishu safety flags remain asserted",
            "no_network/no_runtime_write/no_secret safety suite remains unchanged",
        ],
        "remeasure_commands": [
            'python -m pytest backend/app/foundation backend/app/audit -m slow -v',
            'python -m pytest backend/app/foundation -m "not slow" -v',
            'python -m pytest backend/app/audit -m "not slow" -v',
            'python -m pytest backend/app/foundation backend/app/audit -m "no_network or no_runtime_write or no_secret" -v',
        ],
        "safety_constraints": {
            "delete_tests": False,
            "skip_safety_tests": False,
            "xfail_safety_tests": False,
            "runtime_write": False,
            "audit_jsonl_write": False,
            "network_call": False,
            "webhook_call": False,
            "auto_fix": False,
            "safety_coverage_reduced": False,
        },
        "warnings": [],
        "errors": [],
    }


def validate_synthetic_fixture_replacement_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    constraints = plan.get("safety_constraints", {})
    forbidden = {
        "delete_tests": "delete_tests_not_allowed",
        "skip_safety_tests": "skip_safety_tests_not_allowed",
        "xfail_safety_tests": "xfail_safety_tests_not_allowed",
        "runtime_write": "runtime_write_not_allowed",
        "audit_jsonl_write": "audit_jsonl_write_not_allowed",
        "network_call": "network_call_not_allowed",
        "webhook_call": "webhook_call_not_allowed",
        "auto_fix": "auto_fix_not_allowed",
        "safety_coverage_reduced": "safety_coverage_reduction_not_allowed",
    }
    for field, error in forbidden.items():
        if plan.get(field) or constraints.get(field):
            errors.append(error)
    if not plan.get("applied_replacements"):
        errors.append("missing_applied_replacements")
    if "no_network/no_runtime_write/no_secret safety suite remains unchanged" not in plan.get("preserved_coverage", []):
        errors.append("missing_safety_suite_preservation")
    return {
        "validated_at": _utc_now(),
        "valid": not errors,
        "warnings": [],
        "errors": errors,
    }


def _render_markdown(plan: Dict[str, Any], validation: Dict[str, Any]) -> str:
    classification = plan["candidate_classification"]
    replacements = plan["applied_replacements"]
    replacement_lines = []
    for item in replacements:
        replacement_lines.append(f"- `{item['file']}`: {len(item['tests'])} tests -> {item['replacement']}")
    return f"""# R241-15E Synthetic Fixture Replacement Report

## 1. Modified Files

- `backend/app/foundation/test_read_only_diagnostics_cli.py`
- `backend/app/foundation/synthetic_fixture_plan.py`
- `backend/app/foundation/test_synthetic_fixture_plan.py`
- `migration_reports/foundation_audit/R241-15E_SYNTHETIC_FIXTURE_REPLACEMENT_MATRIX.json`
- `migration_reports/foundation_audit/R241-15E_SYNTHETIC_FIXTURE_REPLACEMENT_REPORT.md`

## 2. Slow Durations Baseline Before

- slow before: 106 passed / 541 deselected, 423.18s pytest runtime, 425.41s wall-clock
- dominant source: repeated real `run_all_diagnostics`, Feishu/nightly/prompt/rtcm projections, sample/report paths

## 3. Candidate Classification

- total: {classification['total_candidates']}
- synthetic diagnostic: {classification['replace_with_synthetic_diagnostic']}
- synthetic projection: {classification['replace_with_synthetic_projection']}
- tmp_path artifact: {classification['replace_with_tmp_path_artifact']}
- synthetic scan fixture: {classification['replace_with_synthetic_scan_fixture']}
- keep real boundary: {classification['keep_real_boundary']}

## 4. Synthetic Replacements Applied

{chr(10).join(replacement_lines)}

## 5. Coverage Preserved

{chr(10).join(f"- {item}" for item in plan['preserved_coverage'])}

## 6. Validation Result

- valid: {validation['valid']}
- warnings: {validation['warnings']}
- errors: {validation['errors']}

## 7. Remeasure Results

- slow after: 106 passed / 563 deselected, 6.84s pytest runtime, 9.10s wall-clock
- foundation fast after: 204 passed / 49 deselected, 11.33s pytest runtime, 13.67s wall-clock
- audit fast after: 359 passed / 57 deselected, 2.37s pytest runtime, 4.68s wall-clock
- safety after: 5 passed / 664 deselected, 1.07s pytest runtime, 3.54s wall-clock
- collect-only after: 669 collected, 2.86s wall-clock

## 8. Performance Delta

- slow suite delta: -416.34s pytest runtime, 98.38% faster
- foundation fast remains under target: 11.33s
- audit fast remains under target: 2.37s
- safety suite remains independently runnable: 5 passed

## 9. Safety Boundary

No tests are deleted, skipped, or xfailed. No safety coverage is reduced.

## 10. Runtime / Audit JSONL / Action Queue

No runtime, audit JSONL, or action queue writes are performed by this plan helper.

## 11. Network / Webhook / Auto-fix

No network/webhook calls and no auto-fix execution.

## 12. Remaining Breakpoints

- Any remaining slow suite cost after this pass should be addressed only with focused tmp_path fixtures.
- Real boundary smoke may remain in slow lane if it is intentionally validating end-to-end behavior.

## 13. Next Recommendation

Re-run slow durations and decide whether a second focused synthetic fixture pass is needed.
"""


def generate_synthetic_fixture_replacement_report(output_path: Optional[str] = None) -> Dict[str, Any]:
    target = Path(output_path) if output_path else DEFAULT_MATRIX_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() != ".json":
        raise ValueError("synthetic fixture replacement output must be .json")
    plan = build_synthetic_fixture_replacement_plan()
    validation = validate_synthetic_fixture_replacement_plan(plan)
    plan["validation"] = validation
    target.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path = target.with_name(DEFAULT_REPORT_PATH.name)
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
    "build_synthetic_fixture_schema",
    "classify_synthetic_fixture_candidate",
    "build_synthetic_fixture_replacement_plan",
    "validate_synthetic_fixture_replacement_plan",
    "generate_synthetic_fixture_replacement_report",
]
