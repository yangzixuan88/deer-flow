"""Tests for R241-15E synthetic fixture replacement planning."""

from pathlib import Path

import pytest

from app.foundation import synthetic_fixture_plan as plan


def test_build_synthetic_fixture_schema_contains_fixture_types():
    schema = plan.build_synthetic_fixture_schema()
    assert "monkeypatch_diagnostic_result" in schema["fixture_types"]
    assert "tmp_path_artifact" in schema["fixture_types"]


def test_classify_run_all_as_synthetic_diagnostic():
    result = plan.classify_synthetic_fixture_candidate({"nodeid": "test_run_all", "reason": "run_all_diagnostics"})
    assert result["classification"] == "replace_with_synthetic_diagnostic"
    assert result["safe_to_replace"] is True


def test_classify_feishu_as_synthetic_projection():
    result = plan.classify_synthetic_fixture_candidate({"nodeid": "test_feishu", "reason": "Feishu summary projection"})
    assert result["classification"] == "replace_with_synthetic_projection"


def test_classify_sample_as_tmp_path_artifact():
    result = plan.classify_synthetic_fixture_candidate({"nodeid": "test_sample", "reason": "sample report artifact"})
    assert result["classification"] == "replace_with_tmp_path_artifact"


def test_classify_scan_as_synthetic_scan_fixture():
    result = plan.classify_synthetic_fixture_candidate({"nodeid": "test_scan", "reason": "filesystem scan rglob"})
    assert result["classification"] == "replace_with_synthetic_scan_fixture"


def test_classify_unknown_keeps_real_boundary():
    result = plan.classify_synthetic_fixture_candidate({"nodeid": "test_unknown", "reason": "manual boundary"})
    assert result["classification"] == "keep_real_boundary"
    assert result["safe_to_replace"] is False


def test_build_replacement_plan_has_applied_replacements():
    result = plan.build_synthetic_fixture_replacement_plan()
    assert result["applied_replacements"]
    assert result["candidate_classification"]["total_candidates"] > 0


def test_build_replacement_plan_preserves_safety_coverage():
    result = plan.build_synthetic_fixture_replacement_plan()
    assert any("safety suite remains unchanged" in item for item in result["preserved_coverage"])


def test_validate_replacement_plan_valid_true():
    result = plan.build_synthetic_fixture_replacement_plan()
    validation = plan.validate_synthetic_fixture_replacement_plan(result)
    assert validation["valid"] is True


@pytest.mark.parametrize(
    ("field", "expected_error"),
    [
        ("delete_tests", "delete_tests_not_allowed"),
        ("skip_safety_tests", "skip_safety_tests_not_allowed"),
        ("xfail_safety_tests", "xfail_safety_tests_not_allowed"),
        ("runtime_write", "runtime_write_not_allowed"),
        ("audit_jsonl_write", "audit_jsonl_write_not_allowed"),
        ("network_call", "network_call_not_allowed"),
        ("webhook_call", "webhook_call_not_allowed"),
        ("auto_fix", "auto_fix_not_allowed"),
    ],
)
def test_validate_replacement_plan_rejects_forbidden_actions(field, expected_error):
    result = plan.build_synthetic_fixture_replacement_plan()
    result["safety_constraints"][field] = True
    validation = plan.validate_synthetic_fixture_replacement_plan(result)
    assert validation["valid"] is False
    assert expected_error in validation["errors"]


def test_generate_synthetic_fixture_report_writes_only_tmp_path(tmp_path):
    output = tmp_path / "R241-15E_SYNTHETIC_FIXTURE_REPLACEMENT_MATRIX.json"
    result = plan.generate_synthetic_fixture_replacement_report(str(output))
    assert Path(result["output_path"]).exists()
    assert Path(result["markdown_path"]).exists()
    assert str(tmp_path) in result["output_path"]
    assert result["validation"]["valid"] is True


def test_no_audit_jsonl_written(tmp_path):
    output = tmp_path / "R241-15E_SYNTHETIC_FIXTURE_REPLACEMENT_MATRIX.json"
    plan.generate_synthetic_fixture_replacement_report(str(output))
    assert not list(tmp_path.rglob("*.jsonl"))


def test_no_runtime_or_action_queue_written(tmp_path):
    output = tmp_path / "R241-15E_SYNTHETIC_FIXTURE_REPLACEMENT_MATRIX.json"
    plan.generate_synthetic_fixture_replacement_report(str(output))
    names = {path.name for path in tmp_path.iterdir()}
    assert "governance_state.json" not in names
    assert "experiment_queue.json" not in names
    assert "action_queue.json" not in names


def test_no_network_or_webhook_called(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr("urllib.request.urlopen", fail_network)
    result = plan.build_synthetic_fixture_replacement_plan()
    validation = plan.validate_synthetic_fixture_replacement_plan(result)
    assert validation["valid"] is True


def test_no_auto_fix():
    result = plan.build_synthetic_fixture_replacement_plan()
    assert result["safety_constraints"]["auto_fix"] is False
