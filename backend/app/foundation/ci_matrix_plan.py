"""CI matrix and test contribution policy for R241-15F.

This module is a report-only planning helper. It does not delete tests, skip
safety tests, write runtime state, write audit JSONL, call network/webhooks, or
execute auto-fix actions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_PLAN_PATH = REPORT_DIR / "R241-15F_CI_MATRIX_PLAN.json"
DEFAULT_REPORT_PATH = REPORT_DIR / "R241-15F_CI_MATRIX_REPORT.md"

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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_ci_stage_catalog() -> Dict[str, Any]:
    """Return the fixed fast/slow/safety/full CI stage catalog."""
    stages = [
        {
            "stage_id": "stage_1_smoke",
            "name": "Smoke",
            "goal": "Minimal health checks: import, registry, marker, root guard style checks.",
            "command": "python -m pytest -m smoke -v",
            "target_runtime_seconds": 60,
            "required": True,
            "writes_runtime": False,
            "network_allowed": False,
        },
        {
            "stage_id": "stage_2_fast",
            "name": "Fast Unit + Fast Integration",
            "goal": "Default local developer regression excluding slow tests.",
            "command": 'python -m pytest backend/app/foundation backend/app/audit -m "not slow" -v',
            "target_runtime_seconds": 60,
            "required": True,
            "writes_runtime": False,
            "network_allowed": False,
        },
        {
            "stage_id": "stage_3_safety",
            "name": "Safety",
            "goal": "Run no_network / no_runtime_write / no_secret boundaries independently.",
            "command": 'python -m pytest backend/app/foundation backend/app/audit -m "no_network or no_runtime_write or no_secret" -v',
            "target_runtime_seconds": 10,
            "required": True,
            "writes_runtime": False,
            "network_allowed": False,
        },
        {
            "stage_id": "stage_4_slow",
            "name": "Slow Integration",
            "goal": "Real boundary, real repo scan, aggregate diagnostic, append/query/trend/Feishu preview smoke.",
            "command": "python -m pytest backend/app/foundation backend/app/audit -m slow -v",
            "target_runtime_seconds": 60,
            "required": True,
            "writes_runtime": False,
            "network_allowed": False,
        },
        {
            "stage_id": "stage_5_full",
            "name": "Full Regression",
            "goal": "Pre-release or large-change regression across foundation surfaces.",
            "command": (
                "python -m pytest backend/app/foundation backend/app/audit backend/app/nightly "
                "backend/app/rtcm backend/app/prompt backend/app/tool_runtime backend/app/mode "
                "backend/app/gateway backend/app/asset backend/app/memory backend/app/m11 -v"
            ),
            "target_runtime_seconds": None,
            "required": True,
            "writes_runtime": False,
            "network_allowed": False,
        },
    ]
    return {
        "catalog_id": "R241-15F_ci_stage_catalog",
        "generated_at": _utc_now(),
        "stages": stages,
        "stage_count": len(stages),
        "warnings": [],
    }


def build_marker_usage_policy() -> Dict[str, Any]:
    """Return usage rules for the 8 pytest markers."""
    marker_rules = {
        "smoke": {
            "use_for": "Minimal import/registry/root health tests expected to finish quickly.",
            "do_not_use_for": "Deep scans, real aggregate diagnostics, or report generation.",
            "examples": ["module import", "command registry shape", "root guard wrapper smoke"],
            "combinable_with": ["unit", "integration", "no_network", "no_runtime_write", "no_secret"],
            "fast_lane_allowed": True,
        },
        "unit": {
            "use_for": "Pure functions: validators, formatters, classifiers, schema builders.",
            "do_not_use_for": "Tests that scan the repo, call CLI aggregate helpers, or write reports.",
            "examples": ["validate_ci_matrix_plan", "format markdown from synthetic result"],
            "combinable_with": ["smoke", "no_network", "no_runtime_write", "no_secret"],
            "fast_lane_allowed": True,
        },
        "integration": {
            "use_for": "Cross-module helpers, CLI wrappers, projections, query helpers.",
            "do_not_use_for": "Pure unit tests that should stay simple and isolated.",
            "examples": ["diagnostic helper with monkeypatch", "audit query projection"],
            "combinable_with": ["slow", "smoke", "no_network", "no_runtime_write", "no_secret"],
            "fast_lane_allowed": True,
        },
        "slow": {
            "use_for": "Real repo scan, real aggregate diagnostic, real CLI smoke, sample/report generation.",
            "do_not_use_for": "Pure validators, small formatters, or schema-only tests.",
            "examples": ["run_all_diagnostics real boundary", "audit-trend CLI smoke"],
            "combinable_with": ["integration", "full", "no_network", "no_runtime_write", "no_secret"],
            "fast_lane_allowed": False,
        },
        "full": {
            "use_for": "Full regression-only cases or broad coverage groups.",
            "do_not_use_for": "Marker replacement for slow or safety; keep semantics explicit.",
            "examples": ["pre-release matrix coverage"],
            "combinable_with": ["slow", "integration"],
            "fast_lane_allowed": False,
        },
        "no_network": {
            "use_for": "Tests proving no webhook/network calls happen.",
            "do_not_use_for": "Tests that require real network access; such tests are not allowed in this foundation suite.",
            "examples": ["Feishu dry-run no webhook call", "network monkeypatch guard"],
            "combinable_with": ["smoke", "unit", "integration", "slow"],
            "fast_lane_allowed": True,
            "must_not_delete": True,
        },
        "no_runtime_write": {
            "use_for": "Tests proving no runtime/action queue/governance writes happen.",
            "do_not_use_for": "Append-only audit writer tests unless the assertion explicitly checks dry-run or tmp_path.",
            "examples": ["runtime write guard", "report-only helper"],
            "combinable_with": ["smoke", "unit", "integration", "slow"],
            "fast_lane_allowed": True,
            "must_not_delete": True,
        },
        "no_secret": {
            "use_for": "Tests proving no token/secret/webhook URL/full private body is output.",
            "do_not_use_for": "Tests requiring real secrets; real secrets must not be read.",
            "examples": ["redaction guard", "payload safety validator"],
            "combinable_with": ["smoke", "unit", "integration", "slow"],
            "fast_lane_allowed": True,
            "must_not_delete": True,
        },
    }
    return {
        "policy_id": "R241-15F_marker_usage_policy",
        "generated_at": _utc_now(),
        "marker_count": len(marker_rules),
        "markers": marker_rules,
        "required_markers": REQUIRED_MARKERS,
        "warnings": [],
    }


def build_synthetic_fixture_policy() -> Dict[str, Any]:
    """Return when to use synthetic fixtures and when to keep real boundaries."""
    should_use = [
        "formatter structure only",
        "payload schema only",
        "projection aggregation shape",
        "report/sample JSON shape",
        "path validation",
        "audit_record field existence",
        "repeated run_all_diagnostics without validating real repo state",
    ]
    must_keep_real_boundary = [
        "RootGuard",
        "append-only audit JSONL invariant",
        "audit query real JSONL read smoke",
        "trend CLI guard line count",
        "no network / no webhook / no secret / no runtime write safety",
        "Feishu preview / pre-send validator real CLI smoke",
        "at least one real repo scan slow smoke",
        "Gateway smoke",
    ]
    forbidden = [
        "safety redline tests",
        "real boundary invariant",
        "user confirmation / webhook policy / secret redaction critical paths",
        "audit JSONL append-only line count verification",
        "runtime write detection",
    ]
    return {
        "policy_id": "R241-15F_synthetic_fixture_policy",
        "generated_at": _utc_now(),
        "should_use_synthetic_fixture": should_use,
        "must_keep_real_boundary": must_keep_real_boundary,
        "forbidden_to_syntheticize": forbidden,
        "required_synthetic_fixture_properties": [
            "preserve asserted schema",
            "preserve safety flags",
            "write only tmp_path artifacts",
            "avoid real repo scan unless explicitly testing boundary",
        ],
        "warnings": [],
    }


def build_test_contribution_checklist() -> Dict[str, Any]:
    questions = [
        "Is this unit / integration / slow / safety / full?",
        "Does it read the real repository?",
        "Does it scan many files?",
        "Does it generate sample/report artifacts?",
        "Does it call CLI aggregate diagnostics?",
        "Does it involve network/webhook/secret/runtime write boundaries?",
        "Can it use a synthetic fixture?",
        "Must it keep a real boundary?",
        "Does it need no_network / no_runtime_write / no_secret marker?",
        "Will it pollute the fast lane?",
    ]
    return {
        "checklist_id": "R241-15F_test_contribution_checklist",
        "generated_at": _utc_now(),
        "questions": questions,
        "question_count": len(questions),
        "default_rule": "Prefer synthetic fixtures unless the test is explicitly a real boundary invariant.",
        "warnings": [],
    }


def check_report_path_consistency(root: Optional[str] = None) -> Dict[str, Any]:
    root_path = Path(root) if root else ROOT
    primary = root_path / "migration_reports" / "foundation_audit"
    backend_path = root_path / "backend" / "migration_reports" / "foundation_audit"
    warnings: List[str] = []
    if backend_path.exists():
        warnings.append("path_inconsistency:backend/migration_reports/foundation_audit_exists")
    if not primary.exists():
        warnings.append("primary_report_path_missing:migration_reports/foundation_audit")
    return {
        "checked_at": _utc_now(),
        "primary_report_path": str(primary),
        "primary_exists": primary.exists(),
        "backend_report_path": str(backend_path),
        "backend_path_exists": backend_path.exists(),
        "path_inconsistency": backend_path.exists(),
        "action_taken": "reported_only_no_migration_no_delete",
        "recommendation": "Unify report root or add a compatibility note in a future cleanup.",
        "warnings": warnings,
    }


def build_runtime_regression_thresholds() -> Dict[str, Any]:
    return {
        "threshold_id": "R241-15F_runtime_regression_thresholds",
        "generated_at": _utc_now(),
        "baselines": {
            "foundation_fast_baseline": 11.33,
            "audit_fast_baseline": 2.37,
            "slow_baseline": 6.84,
            "safety_baseline": 1.07,
            "collect_only_baseline": 2.86,
        },
        "thresholds": {
            "foundation_fast_warning_threshold": 30,
            "foundation_fast_blocker_threshold": 60,
            "audit_fast_warning_threshold": 15,
            "slow_suite_warning_threshold": 60,
            "safety_suite_warning_threshold": 10,
            "collect_only_warning_threshold": 10,
        },
        "warnings": [],
    }


def validate_ci_matrix_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    stage_names = {stage.get("name") for stage in plan.get("ci_stage_catalog", {}).get("stages", [])}
    for name in {"Smoke", "Fast Unit + Fast Integration", "Safety", "Slow Integration", "Full Regression"}:
        if name not in stage_names:
            errors.append(f"missing_stage:{name}")
    marker_names = set(plan.get("marker_usage_policy", {}).get("markers", {}).keys())
    for marker in REQUIRED_MARKERS:
        if marker not in marker_names:
            errors.append(f"missing_marker:{marker}")
    synthetic = plan.get("synthetic_fixture_policy", {})
    if not synthetic.get("should_use_synthetic_fixture"):
        errors.append("missing_synthetic_fixture_policy")
    if not synthetic.get("must_keep_real_boundary"):
        errors.append("missing_real_boundary_keep_rules")
    constraints = plan.get("safety_constraints", {})
    forbidden = {
        "delete_tests": "delete_tests_not_allowed",
        "skip_safety_tests": "skip_safety_tests_not_allowed",
        "xfail_safety_tests": "xfail_safety_tests_not_allowed",
        "network_call": "network_call_not_allowed",
        "runtime_write": "runtime_write_not_allowed",
        "audit_jsonl_overwrite": "audit_jsonl_overwrite_not_allowed",
        "auto_fix": "auto_fix_not_allowed",
        "safety_coverage_reduced": "safety_coverage_reduction_not_allowed",
    }
    for field, error in forbidden.items():
        if plan.get(field) or constraints.get(field):
            errors.append(error)
    return {
        "validated_at": _utc_now(),
        "valid": not errors,
        "warnings": [],
        "errors": errors,
    }


def _render_markdown(plan: Dict[str, Any], validation: Dict[str, Any]) -> str:
    stages = plan["ci_stage_catalog"]["stages"]
    markers = plan["marker_usage_policy"]["markers"]
    synthetic = plan["synthetic_fixture_policy"]
    checklist = plan["test_contribution_checklist"]["questions"]
    paths = plan["report_path_consistency"]
    thresholds = plan["runtime_regression_thresholds"]
    return f"""# R241-15F CI Matrix Report

## 1. Modified Files

- `backend/app/foundation/ci_matrix_plan.py`
- `backend/app/foundation/test_ci_matrix_plan.py`
- `docs/testing/FOUNDATION_TESTING_GUIDE.md`
- `migration_reports/foundation_audit/R241-15F_CI_MATRIX_PLAN.json`
- `migration_reports/foundation_audit/R241-15F_CI_MATRIX_REPORT.md`

## 2. CI stage catalog

{chr(10).join(f"- {stage['name']}: `{stage['command']}`" for stage in stages)}

## 3. marker usage policy

{chr(10).join(f"- `{name}`: {rule['use_for']} Fast lane allowed: {rule['fast_lane_allowed']}" for name, rule in markers.items())}

## 4. synthetic fixture policy

Should use:
{chr(10).join(f"- {item}" for item in synthetic['should_use_synthetic_fixture'])}

## 5. real boundary keep rules

{chr(10).join(f"- {item}" for item in synthetic['must_keep_real_boundary'])}

## 6. test contribution checklist

{chr(10).join(f"- {item}" for item in checklist)}

## 7. report path consistency result

- primary exists: {paths['primary_exists']} at `{paths['primary_report_path']}`
- backend path exists: {paths['backend_path_exists']} at `{paths['backend_report_path']}`
- path inconsistency: {paths['path_inconsistency']}
- action taken: {paths['action_taken']}

## 8. runtime baseline and thresholds

- baselines: {thresholds['baselines']}
- thresholds: {thresholds['thresholds']}

## 9. validation result

- valid: {validation['valid']}
- warnings: {validation['warnings']}
- errors: {validation['errors']}

## 10. Test Results

To be populated from command output in final response.

## 11. Deleted Or Skipped Tests

No tests are deleted. No tests are skipped or xfailed.

## 12. Safety Coverage

No safety coverage is reduced. Safety markers remain independently runnable.

## 13. Runtime / Audit JSONL / Action Queue

No runtime, audit JSONL, or action queue writes are performed.

## 14. Network / Webhook

No network or webhook calls are performed.

## 15. Auto-fix

No auto-fix is performed.

## 16. Remaining Breakpoints

- Resolve or document the `backend/migration_reports/foundation_audit` compatibility path.
- Add CI configuration only in a future implementation pass.

## 17. Next Recommendation

Proceed to manual confirmation and CI implementation planning.
"""


def generate_ci_matrix_plan(output_path: Optional[str] = None) -> Dict[str, Any]:
    target = Path(output_path) if output_path else DEFAULT_PLAN_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() != ".json":
        raise ValueError("CI matrix plan output must be .json")
    plan = {
        "plan_id": "R241-15F_ci_matrix_plan",
        "generated_at": _utc_now(),
        "root": str(ROOT),
        "ci_stage_catalog": build_ci_stage_catalog(),
        "marker_usage_policy": build_marker_usage_policy(),
        "synthetic_fixture_policy": build_synthetic_fixture_policy(),
        "test_contribution_checklist": build_test_contribution_checklist(),
        "report_path_consistency": check_report_path_consistency(str(ROOT)),
        "runtime_regression_thresholds": build_runtime_regression_thresholds(),
        "safety_constraints": {
            "delete_tests": False,
            "skip_safety_tests": False,
            "xfail_safety_tests": False,
            "network_call": False,
            "runtime_write": False,
            "audit_jsonl_overwrite": False,
            "auto_fix": False,
            "safety_coverage_reduced": False,
        },
        "warnings": [],
        "errors": [],
    }
    validation = validate_ci_matrix_plan(plan)
    plan["validation"] = validation
    target.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path = target.with_name(DEFAULT_REPORT_PATH.name)
    markdown_path.write_text(_render_markdown(plan, validation), encoding="utf-8")
    return {
        "plan": plan,
        "output_path": str(target),
        "markdown_path": str(markdown_path),
        "validation": validation,
        "warnings": plan["warnings"],
        "errors": plan["errors"],
    }


__all__ = [
    "build_ci_stage_catalog",
    "build_marker_usage_policy",
    "build_synthetic_fixture_policy",
    "build_test_contribution_checklist",
    "check_report_path_consistency",
    "build_runtime_regression_thresholds",
    "validate_ci_matrix_plan",
    "generate_ci_matrix_plan",
]
