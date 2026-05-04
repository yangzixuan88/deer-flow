"""Tests for R241-15F CI matrix and testing contribution policy.

These tests validate report-only planning helpers. They do not delete tests,
skip safety coverage, write audit JSONL/runtime/action queue files, call
network/webhooks, or execute auto-fix.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

from app.foundation import ci_matrix_plan as plan


def _stage(catalog: dict, name: str) -> dict:
    return next(stage for stage in catalog["stages"] if stage["name"] == name)


def _valid_plan() -> dict:
    return {
        "ci_stage_catalog": plan.build_ci_stage_catalog(),
        "marker_usage_policy": plan.build_marker_usage_policy(),
        "synthetic_fixture_policy": plan.build_synthetic_fixture_policy(),
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
    }


def test_build_ci_stage_catalog_contains_smoke_fast_safety_slow_full():
    catalog = plan.build_ci_stage_catalog()
    assert {stage["name"] for stage in catalog["stages"]} == {
        "Smoke",
        "Fast Unit + Fast Integration",
        "Safety",
        "Slow Integration",
        "Full Regression",
    }


def test_fast_stage_uses_not_slow():
    command = _stage(plan.build_ci_stage_catalog(), "Fast Unit + Fast Integration")["command"]
    assert "not slow" in command


def test_safety_stage_uses_safety_markers():
    command = _stage(plan.build_ci_stage_catalog(), "Safety")["command"]
    assert "no_network" in command
    assert "no_runtime_write" in command
    assert "no_secret" in command


def test_slow_stage_uses_slow_marker():
    command = _stage(plan.build_ci_stage_catalog(), "Slow Integration")["command"]
    assert "-m slow" in command


def test_full_stage_contains_all_foundation_domains():
    command = _stage(plan.build_ci_stage_catalog(), "Full Regression")["command"]
    for domain in [
        "foundation",
        "audit",
        "nightly",
        "rtcm",
        "prompt",
        "tool_runtime",
        "mode",
        "gateway",
        "asset",
        "memory",
        "m11",
    ]:
        assert f"backend/app/{domain}" in command


def test_marker_policy_contains_required_8_markers():
    policy = plan.build_marker_usage_policy()
    assert set(policy["markers"]) == set(plan.REQUIRED_MARKERS)
    assert policy["marker_count"] == 8


def test_marker_policy_defines_slow_misuse_forbidden():
    slow = plan.build_marker_usage_policy()["markers"]["slow"]
    assert "Pure validators" in slow["do_not_use_for"]
    assert "schema-only" in slow["do_not_use_for"]


def test_marker_policy_defines_safety_markers_must_not_delete():
    markers = plan.build_marker_usage_policy()["markers"]
    assert markers["no_network"]["must_not_delete"] is True
    assert markers["no_runtime_write"]["must_not_delete"] is True
    assert markers["no_secret"]["must_not_delete"] is True


def test_synthetic_fixture_policy_contains_should_use_scenarios():
    policy = plan.build_synthetic_fixture_policy()
    assert "payload schema only" in policy["should_use_synthetic_fixture"]
    assert "report/sample JSON shape" in policy["should_use_synthetic_fixture"]


def test_synthetic_fixture_policy_contains_real_boundary_rules():
    policy = plan.build_synthetic_fixture_policy()
    assert "RootGuard" in policy["must_keep_real_boundary"]
    assert "Gateway smoke" in policy["must_keep_real_boundary"]


def test_synthetic_fixture_policy_forbids_synthetic_safety_invariants():
    policy = plan.build_synthetic_fixture_policy()
    assert "safety redline tests" in policy["forbidden_to_syntheticize"]
    assert "runtime write detection" in policy["forbidden_to_syntheticize"]


def test_contribution_checklist_contains_10_questions():
    checklist = plan.build_test_contribution_checklist()
    assert checklist["question_count"] == 10
    assert len(checklist["questions"]) == 10


def test_report_path_consistency_normal_returns(tmp_path: Path):
    (tmp_path / "migration_reports" / "foundation_audit").mkdir(parents=True)
    result = plan.check_report_path_consistency(str(tmp_path))
    assert result["primary_exists"] is True
    assert result["backend_path_exists"] is False
    assert result["path_inconsistency"] is False


def test_report_path_consistency_backend_path_warns_without_delete(tmp_path: Path):
    primary = tmp_path / "migration_reports" / "foundation_audit"
    backend = tmp_path / "backend" / "migration_reports" / "foundation_audit"
    primary.mkdir(parents=True)
    backend.mkdir(parents=True)

    result = plan.check_report_path_consistency(str(tmp_path))

    assert result["primary_exists"] is True
    assert result["backend_path_exists"] is True
    assert result["path_inconsistency"] is True
    assert any("path_inconsistency" in warning for warning in result["warnings"])
    assert primary.exists()
    assert backend.exists()


def test_runtime_thresholds_include_foundation_fast_baseline():
    thresholds = plan.build_runtime_regression_thresholds()
    assert thresholds["baselines"]["foundation_fast_baseline"] == 11.33


def test_runtime_thresholds_include_foundation_fast_blocker_threshold():
    thresholds = plan.build_runtime_regression_thresholds()
    assert thresholds["thresholds"]["foundation_fast_blocker_threshold"] == 60


def test_validate_ci_matrix_plan_valid_true():
    validation = plan.validate_ci_matrix_plan(_valid_plan())
    assert validation["valid"] is True
    assert validation["errors"] == []


def test_validate_ci_matrix_plan_rejects_delete_tests():
    candidate = _valid_plan()
    candidate["safety_constraints"]["delete_tests"] = True
    validation = plan.validate_ci_matrix_plan(candidate)
    assert validation["valid"] is False
    assert "delete_tests_not_allowed" in validation["errors"]


def test_validate_ci_matrix_plan_rejects_skip_safety_tests():
    candidate = _valid_plan()
    candidate["safety_constraints"]["skip_safety_tests"] = True
    validation = plan.validate_ci_matrix_plan(candidate)
    assert validation["valid"] is False
    assert "skip_safety_tests_not_allowed" in validation["errors"]


def test_validate_ci_matrix_plan_rejects_network_call():
    candidate = _valid_plan()
    candidate["safety_constraints"]["network_call"] = True
    validation = plan.validate_ci_matrix_plan(candidate)
    assert validation["valid"] is False
    assert "network_call_not_allowed" in validation["errors"]


def test_validate_ci_matrix_plan_rejects_runtime_write():
    candidate = _valid_plan()
    candidate["safety_constraints"]["runtime_write"] = True
    validation = plan.validate_ci_matrix_plan(candidate)
    assert validation["valid"] is False
    assert "runtime_write_not_allowed" in validation["errors"]


def test_validate_ci_matrix_plan_rejects_audit_jsonl_overwrite():
    candidate = _valid_plan()
    candidate["safety_constraints"]["audit_jsonl_overwrite"] = True
    validation = plan.validate_ci_matrix_plan(candidate)
    assert validation["valid"] is False
    assert "audit_jsonl_overwrite_not_allowed" in validation["errors"]


def test_generate_ci_matrix_plan_only_writes_tmp_path(tmp_path: Path):
    output = tmp_path / "R241-15F_CI_MATRIX_PLAN.json"
    result = plan.generate_ci_matrix_plan(str(output))
    markdown = tmp_path / "R241-15F_CI_MATRIX_REPORT.md"
    assert Path(result["output_path"]) == output
    assert output.exists()
    assert markdown.exists()
    assert not list(tmp_path.rglob("*.jsonl"))


def test_helpers_do_not_call_network(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("network call is forbidden")

    monkeypatch.setattr(urllib.request, "urlopen", fail_network)
    validation = plan.validate_ci_matrix_plan(_valid_plan())
    assert validation["valid"] is True


def test_helpers_do_not_write_runtime_action_queue_or_audit_jsonl(tmp_path: Path):
    output = tmp_path / "R241-15F_CI_MATRIX_PLAN.json"
    plan.generate_ci_matrix_plan(str(output))
    forbidden_names = {"governance_state.json", "experiment_queue.json", "action_queue.json"}
    written_names = {path.name for path in tmp_path.rglob("*") if path.is_file()}
    assert forbidden_names.isdisjoint(written_names)
    assert not list(tmp_path.rglob("*.jsonl"))


def test_validate_ci_matrix_plan_rejects_auto_fix():
    candidate = _valid_plan()
    candidate["safety_constraints"]["auto_fix"] = True
    validation = plan.validate_ci_matrix_plan(candidate)
    assert validation["valid"] is False
    assert "auto_fix_not_allowed" in validation["errors"]
