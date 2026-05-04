"""Tests for R241-15C test runtime optimization plan.

These tests validate report-only helpers. They do not write audit JSONL,
runtime state, or action queue files; they do not call network/webhooks; and
they do not execute auto-fix.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.foundation import runtime_optimization_plan as runtime_plan


def _write_marker_pyproject(root: Path) -> None:
    backend = root / "backend"
    backend.mkdir(parents=True, exist_ok=True)
    (backend / "pyproject.toml").write_text(
        """
[tool.pytest.ini_options]
markers = [
    "smoke: fast health checks",
    "unit: pure unit tests",
    "integration: integration tests",
    "slow: slow tests",
    "full: full regression",
    "no_network: no network",
    "no_runtime_write: no runtime writes",
    "no_secret: no secrets",
]
""",
        encoding="utf-8",
    )


def _write_test_file(root: Path) -> Path:
    test_dir = root / "backend" / "app" / "foundation"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_slow_hints.py"
    test_file.write_text(
        """
import pytest

def test_generate_sample_report():
    assert True

def test_scan_real_tree():
    files = list(Path('.').rglob('*.py'))
    assert files is not None

@pytest.mark.no_network
def test_safety_no_network():
    assert True
""",
        encoding="utf-8",
    )
    return test_file


def test_build_runtime_baseline_summary_contains_original_baseline():
    summary = runtime_plan.build_runtime_baseline_summary()
    assert summary["original_baseline_runtime"] == "6m40s+"
    assert summary["original_baseline_seconds"] >= 400


def test_build_runtime_baseline_summary_contains_foundation_fast_runtime():
    summary = runtime_plan.build_runtime_baseline_summary(
        {"foundation_fast_runtime": {"runtime": "10.0s", "passed": 1, "failed": 0, "skipped": 0}}
    )
    assert "foundation_fast_runtime" in summary
    assert summary["foundation_fast_runtime"]["runtime_seconds"] == 10.0


def test_detect_remaining_slow_in_fast_returns_candidates(tmp_path):
    _write_marker_pyproject(tmp_path)
    _write_test_file(tmp_path)
    result = runtime_plan.detect_remaining_slow_in_fast(str(tmp_path))
    assert isinstance(result["remaining_slow_in_fast"], list)
    assert result["remaining_slow_in_fast_count"] >= 1


def test_detect_remaining_slow_in_fast_marks_sample_generation(tmp_path):
    _write_marker_pyproject(tmp_path)
    _write_test_file(tmp_path)
    result = runtime_plan.detect_remaining_slow_in_fast(str(tmp_path))
    reasons = {c["reason"] for c in result["remaining_slow_in_fast"]}
    assert "sample generation" in reasons


def test_detect_remaining_slow_in_fast_marks_filesystem_scan(tmp_path):
    _write_marker_pyproject(tmp_path)
    _write_test_file(tmp_path)
    result = runtime_plan.detect_remaining_slow_in_fast(str(tmp_path))
    reasons = {c["reason"] for c in result["remaining_slow_in_fast"]}
    assert "filesystem scan" in reasons


def test_audit_marker_quality_checks_8_markers(tmp_path):
    _write_marker_pyproject(tmp_path)
    _write_test_file(tmp_path)
    result = runtime_plan.audit_marker_quality(str(tmp_path))
    assert result["pytest_markers_contains_8_required"] is True
    assert set(runtime_plan.REQUIRED_MARKERS).issubset(set(result["configured_markers"]))


def test_audit_marker_quality_checks_safety_marker(tmp_path):
    _write_marker_pyproject(tmp_path)
    _write_test_file(tmp_path)
    result = runtime_plan.audit_marker_quality(str(tmp_path))
    assert result["safety_markers_runnable"] is True
    assert result["no_network_runnable"] is True


def test_build_runtime_optimization_options_contains_a_to_e():
    result = runtime_plan.build_runtime_optimization_options()
    option_ids = {option["option_id"] for option in result["options"]}
    assert option_ids == {"Option A", "Option B", "Option C", "Option D", "Option E"}


def test_validate_runtime_optimization_plan_valid_true(tmp_path):
    _write_marker_pyproject(tmp_path)
    plan = {
        "runtime_baseline_summary": runtime_plan.build_runtime_baseline_summary(),
        "remaining_slow_in_fast_detection": runtime_plan.detect_remaining_slow_in_fast(str(tmp_path)),
        "marker_quality_audit": runtime_plan.audit_marker_quality(str(tmp_path)),
        "optimization_options": runtime_plan.build_runtime_optimization_options(),
        "deleted_tests": False,
        "safety_coverage_reduced": False,
    }
    result = runtime_plan.validate_runtime_optimization_plan(plan)
    assert result["valid"] is True


def test_validate_runtime_optimization_plan_rejects_delete_tests_suggestion():
    plan = {
        "optimization_options": {"ci_stage_matrix": {"fast": "", "slow": "", "safety": "no_network no_runtime_write no_secret", "full": ""}},
        "recommendation": "delete tests to speed up",
    }
    result = runtime_plan.validate_runtime_optimization_plan(plan)
    assert result["valid"] is False
    assert "plan_must_not_delete_tests" in result["errors"]


def test_validate_runtime_optimization_plan_rejects_skip_safety_tests():
    plan = {
        "optimization_options": {"ci_stage_matrix": {"fast": "", "slow": "", "safety": "no_network no_runtime_write no_secret", "full": ""}},
        "recommendation": "skip safety tests",
    }
    result = runtime_plan.validate_runtime_optimization_plan(plan)
    assert result["valid"] is False
    assert "plan_must_not_skip_safety_tests" in result["errors"]


def test_validate_runtime_optimization_plan_rejects_network_call_suggestion():
    plan = {
        "optimization_options": {"ci_stage_matrix": {"fast": "", "slow": "", "safety": "no_network no_runtime_write no_secret", "full": ""}},
        "recommendation": "call network to verify webhook",
    }
    result = runtime_plan.validate_runtime_optimization_plan(plan)
    assert result["valid"] is False
    assert "plan_must_not_call_network" in result["errors"]


def test_generate_runtime_optimization_plan_writes_only_tmp_path(tmp_path):
    output = tmp_path / "R241-15C_TEST_RUNTIME_OPTIMIZATION_PLAN.json"
    result = runtime_plan.generate_runtime_optimization_plan(str(output))
    markdown = output.with_name("R241-15C_TEST_RUNTIME_OPTIMIZATION_REPORT.md")
    assert output.exists()
    assert markdown.exists()
    assert result["output_path"] == str(output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["plan_id"] == "R241-15C_test_runtime_optimization"


@pytest.mark.no_runtime_write
def test_no_audit_jsonl_written(tmp_path):
    output = tmp_path / "R241-15C_TEST_RUNTIME_OPTIMIZATION_PLAN.json"
    runtime_plan.generate_runtime_optimization_plan(str(output))
    assert list(tmp_path.rglob("*.jsonl")) == []


@pytest.mark.no_runtime_write
def test_no_runtime_or_action_queue_written(tmp_path):
    output = tmp_path / "R241-15C_TEST_RUNTIME_OPTIMIZATION_PLAN.json"
    runtime_plan.generate_runtime_optimization_plan(str(output))
    forbidden = [
        "governance_state.json",
        "experiment_queue.json",
        "action_queue.json",
        "memory.json",
        "asset_registry.json",
    ]
    produced = {p.name for p in tmp_path.rglob("*")}
    assert not produced.intersection(forbidden)


@pytest.mark.no_network
def test_no_network_or_webhook_called(monkeypatch, tmp_path):
    def fail_network(*_args, **_kwargs):
        raise AssertionError("network/webhook should not be called")

    monkeypatch.setattr("urllib.request.urlopen", fail_network)
    output = tmp_path / "R241-15C_TEST_RUNTIME_OPTIMIZATION_PLAN.json"
    result = runtime_plan.generate_runtime_optimization_plan(str(output))
    assert result["validation"]["valid"] is True


@pytest.mark.no_runtime_write
def test_no_auto_fix_executed(tmp_path):
    output = tmp_path / "R241-15C_TEST_RUNTIME_OPTIMIZATION_PLAN.json"
    result = runtime_plan.generate_runtime_optimization_plan(str(output))
    text = json.dumps(result, ensure_ascii=False).lower()
    assert "auto-fix enabled" not in text


@pytest.mark.no_secret
def test_no_secret_token_or_webhook_url_output(tmp_path):
    output = tmp_path / "R241-15C_TEST_RUNTIME_OPTIMIZATION_PLAN.json"
    result = runtime_plan.generate_runtime_optimization_plan(str(output))
    text = json.dumps(result, ensure_ascii=False).lower()
    assert "open.feishu" not in text
    assert "webhook.bot" not in text
    assert "hooks.slack" not in text
    assert "\"token\"" not in text
    assert "\"secret\"" not in text
