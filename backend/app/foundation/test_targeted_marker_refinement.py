"""Tests for R241-15D targeted marker refinement planning."""

from pathlib import Path

import pytest

from app.foundation import targeted_marker_refinement as refinement


def test_build_duration_measurement_schema_contains_foundation_audit_safety():
    schema = refinement.build_duration_measurement_schema()
    assert "foundation_fast" in schema["suites"]
    assert "audit_fast" in schema["suites"]
    assert "safety" in schema["suites"]


def test_classify_duration_candidate_cli_smoke_confirmed_slow():
    result = refinement.classify_duration_candidate(
        {"nodeid": "test_cli_smoke", "reason": "CLI smoke via foundation_diagnose", "duration_seconds": 12}
    )
    assert result["classification"] == "confirmed_slow_marker_needed"
    assert result["safe_to_mark_slow"] is True


def test_classify_duration_candidate_sample_generation_confirmed_slow():
    result = refinement.classify_duration_candidate(
        {"nodeid": "test_generate_sample", "reason": "sample generation report artifact", "duration_seconds": 3}
    )
    assert result["classification"] == "confirmed_slow_marker_needed"


def test_classify_duration_candidate_filesystem_scan_confirmed_slow():
    result = refinement.classify_duration_candidate(
        {"nodeid": "test_scan_repo", "reason": "filesystem scan using rglob", "duration_seconds": 2}
    )
    assert result["classification"] == "confirmed_slow_marker_needed"


def test_classify_duration_candidate_pure_validator_kept_fast_unit():
    result = refinement.classify_duration_candidate(
        {"nodeid": "test_validate_marker_refinement_plan", "reason": "pure validator", "duration_seconds": 0.01}
    )
    assert result["classification"] == "keep_fast_unit"
    assert result["safe_to_mark_slow"] is False


def test_classify_duration_candidate_safety_boundary_marker_only_or_fast():
    result = refinement.classify_duration_candidate(
        {"nodeid": "test_no_network_boundary", "reason": "safety boundary no_network", "duration_seconds": 0.02}
    )
    assert result["classification"] in {"safety_marker_only", "keep_fast_unit"}


def test_build_marker_refinement_plan_returns_proposed_marker_changes():
    plan = refinement.build_marker_refinement_plan(
        heuristic_candidates=[
            {"nodeid": "test_cli_smoke", "reason": "CLI smoke", "duration_seconds": 10},
        ]
    )
    assert plan["proposed_marker_changes"]


def test_build_marker_refinement_plan_returns_keep_fast_tests():
    plan = refinement.build_marker_refinement_plan(
        heuristic_candidates=[
            {"nodeid": "test_validate_schema", "reason": "pure validator", "duration_seconds": 0.01},
        ]
    )
    assert plan["keep_fast_tests"]


def test_build_marker_refinement_plan_returns_synthetic_fixture_later():
    plan = refinement.build_marker_refinement_plan(
        heuristic_candidates=[
            {"nodeid": "test_repo_scan", "reason": "synthetic fixture candidate", "duration_seconds": 5},
        ]
    )
    assert plan["synthetic_fixture_later"]


def test_validate_marker_refinement_plan_valid_true():
    plan = refinement.build_marker_refinement_plan()
    validation = refinement.validate_marker_refinement_plan(plan)
    assert validation["valid"] is True


@pytest.mark.parametrize(
    ("field", "expected_error"),
    [
        ("delete_tests", "delete_tests_not_allowed"),
        ("skip_safety_tests", "skip_safety_tests_not_allowed"),
        ("xfail_safety_tests", "xfail_safety_tests_not_allowed"),
        ("network_call", "network_call_not_allowed"),
        ("runtime_write", "runtime_write_not_allowed"),
    ],
)
def test_validate_marker_refinement_plan_rejects_forbidden_actions(field, expected_error):
    plan = refinement.build_marker_refinement_plan()
    plan["safety_constraints"][field] = True
    validation = refinement.validate_marker_refinement_plan(plan)
    assert validation["valid"] is False
    assert expected_error in validation["errors"]


def test_generate_targeted_marker_refinement_report_writes_only_tmp_path(tmp_path):
    output_path = tmp_path / "R241-15D_TARGETED_MARKER_REFINEMENT_MATRIX.json"
    result = refinement.generate_targeted_marker_refinement_report(str(output_path))
    assert Path(result["output_path"]).exists()
    assert Path(result["markdown_path"]).exists()
    assert str(tmp_path) in result["output_path"]
    assert result["validation"]["valid"] is True


def test_no_audit_jsonl_written(tmp_path):
    output_path = tmp_path / "R241-15D_TARGETED_MARKER_REFINEMENT_MATRIX.json"
    refinement.generate_targeted_marker_refinement_report(str(output_path))
    assert not list(tmp_path.rglob("*.jsonl"))


def test_no_runtime_or_action_queue_written(tmp_path):
    output_path = tmp_path / "R241-15D_TARGETED_MARKER_REFINEMENT_MATRIX.json"
    refinement.generate_targeted_marker_refinement_report(str(output_path))
    written = {p.name for p in tmp_path.iterdir()}
    assert "governance_state.json" not in written
    assert "experiment_queue.json" not in written
    assert "action_queue.json" not in written


def test_no_network_or_webhook_called(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr("urllib.request.urlopen", fail_network)
    plan = refinement.build_marker_refinement_plan()
    validation = refinement.validate_marker_refinement_plan(plan)
    assert validation["valid"] is True


def test_no_auto_fix():
    plan = refinement.build_marker_refinement_plan()
    assert plan["safety_constraints"]["auto_fix"] is False
