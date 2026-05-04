import json
from pathlib import Path

import pytest

from app.audit import audit_trend_cli_guard as guard


def _report_dir(root: Path) -> Path:
    return root / "migration_reports" / "foundation_audit"


def _audit_dir(root: Path) -> Path:
    return _report_dir(root) / "audit_trail"


def _record(record_id: str = "r1") -> str:
    return json.dumps({
        "audit_record_id": record_id,
        "event_type": "nightly_health_review",
        "source_command": "nightly",
        "status": "ok",
        "generated_at": "2026-04-25T00:00:00Z",
        "payload_hash": f"hash-{record_id}",
    })


def _trend_report() -> dict:
    return {
        "trend_report_id": "trend_guard_test",
        "status": "ok",
        "window": "all_available",
        "total_records_analyzed": 1,
        "series": [],
        "regression_signals": [],
        "warnings": [],
        "errors": [],
    }
    @pytest.mark.slow
    def test_capture_line_counts_missing_dir_does_not_create_directory(tmp_path):
        result = guard.capture_audit_jsonl_line_counts(str(tmp_path))
        assert result["line_counts"] == {}
        assert result["missing_files"]
        assert not _audit_dir(tmp_path).exists()
    @pytest.mark.slow
    def test_capture_line_counts_counts_tmp_jsonl(tmp_path):
        audit_dir = _audit_dir(tmp_path)
        audit_dir.mkdir(parents=True)
        target = audit_dir / "foundation_diagnostic_runs.jsonl"
        target.write_text(_record("a") + "\n" + _record("b") + "\n", encoding="utf-8")
        result = guard.capture_audit_jsonl_line_counts(str(tmp_path))
        assert result["line_counts"][str(target)] == 2


def test_compare_line_counts_unchanged_true(tmp_path):
        before = {"line_counts": {"a.jsonl": 1}}
        after = {"line_counts": {"a.jsonl": 1}}
        result = guard.compare_audit_jsonl_line_counts(before, after)
        assert result["unchanged"] is True


def test_compare_line_counts_changed_file():
        result = guard.compare_audit_jsonl_line_counts({"line_counts": {"a": 1}}, {"line_counts": {"a": 2}})
        assert result["unchanged"] is False
        assert result["changed_files"][0]["path"] == "a"


def test_output_safety_detects_webhook_url():
        result = guard.validate_trend_cli_output_safety("https://open.feishu.cn/webhook/abc")
        assert result["safe"] is False
        assert "webhook_url" in result["detected_patterns"]


def test_output_safety_detects_token_secret_api_key():
        result = guard.validate_trend_cli_output_safety({"token": "x", "secret": "y", "api_key": "z"})
        assert result["safe"] is False
        assert {"token", "secret", "api_key"}.issubset(set(result["detected_patterns"]))


def test_output_safety_detects_prompt_memory_rtcm_bodies():
        result = guard.validate_trend_cli_output_safety({"prompt_body": "x", "memory_body": "y", "rtcm_artifact_body": "z"})
        assert result["safe"] is False
        assert "prompt_body" in result["detected_patterns"]
        assert "memory_body" in result["detected_patterns"]
        assert "rtcm_artifact_body" in result["detected_patterns"]


def test_output_safety_safe_output_passes():
        result = guard.validate_trend_cli_output_safety({"status": "ok", "summary": {"series_count": 1}})
        assert result["safe"] is True


def test_artifact_paths_accepts_r241_12d_formats(tmp_path):
        paths = [
        _report_dir(tmp_path) / "R241-12D_TREND_REPORT_ARTIFACT.json",
        _report_dir(tmp_path) / "R241-12D_TREND_REPORT_ARTIFACT.md",
        _report_dir(tmp_path) / "R241-12D_TREND_REPORT_ARTIFACT.txt",
        ]
        result = guard.validate_trend_cli_artifact_paths([str(path) for path in paths], root=str(tmp_path))
        assert result["valid"] is True


def test_artifact_paths_rejects_audit_trail(tmp_path):
        path = _audit_dir(tmp_path) / "R241-12D_bad.json"
        result = guard.validate_trend_cli_artifact_paths([str(path)], root=str(tmp_path))
        assert result["valid"] is False
        assert "audit_trail_path_forbidden" in result["errors"]


def test_artifact_paths_rejects_parent_traversal(tmp_path):
        path = _report_dir(tmp_path) / ".." / "R241-12D_bad.json"
        result = guard.validate_trend_cli_artifact_paths([str(path)], root=str(tmp_path))
        assert result["valid"] is False
        assert "path_traversal_not_allowed" in result["errors"]
@pytest.mark.slow
def test_guarded_write_report_false_does_not_write_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr(guard, "format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    result = guard.run_guarded_audit_trend_cli_projection(root=str(tmp_path), write_report=False)
    assert result["artifact_bundle"] is None
    assert not list(_report_dir(tmp_path).glob("R241-12D_*"))


@pytest.mark.slow
def test_guarded_write_report_true_only_writes_r241_12d_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr(guard, "format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    result = guard.run_guarded_audit_trend_cli_projection(root=str(tmp_path), write_report=True, report_format="all")
    paths = [Path(item["output_path"]) for item in result["artifact_bundle"]["artifacts"]]
    assert all(path.name.startswith("R241-12D_") for path in paths)
    assert {path.suffix for path in paths} == {".json", ".md", ".txt"}


@pytest.mark.slow
def test_guarded_line_count_unchanged(tmp_path, monkeypatch):
    audit_dir = _audit_dir(tmp_path)
    audit_dir.mkdir(parents=True)
    target = audit_dir / "foundation_diagnostic_runs.jsonl"
    target.write_text(_record("a") + "\n", encoding="utf-8")
    before = target.read_text(encoding="utf-8")
    monkeypatch.setattr(guard, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr(guard, "format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    result = guard.run_guarded_audit_trend_cli_projection(root=str(tmp_path), write_report=True, report_format="json")
    assert result["guard"]["audit_jsonl_unchanged"] is True
    assert target.read_text(encoding="utf-8") == before


@pytest.mark.slow
def test_generate_completion_sample_only_writes_tmp_path_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr(guard, "format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    sample = _report_dir(tmp_path) / "R241-12D_NIGHTLY_TREND_CLI_COMPLETION_SAMPLE.json"
    result = guard.generate_trend_cli_completion_sample(str(sample), root=str(tmp_path))
    assert sample.exists()
    assert result["output_path"] == str(sample)


@pytest.mark.slow
def test_no_audit_jsonl_write_runtime_network_or_autofix(tmp_path, monkeypatch):
    audit_dir = _audit_dir(tmp_path)
    audit_dir.mkdir(parents=True)
    target = audit_dir / "foundation_diagnostic_runs.jsonl"
    target.write_text(_record("a") + "\n", encoding="utf-8")
    before = target.read_text(encoding="utf-8")
    monkeypatch.setattr(guard, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr(guard, "format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    result = guard.run_guarded_audit_trend_cli_projection(root=str(tmp_path), write_report=True, report_format="all")
    dumped = json.dumps(result, ensure_ascii=False).lower()
    assert target.read_text(encoding="utf-8") == before
    assert "auto_fix_detected\": true" not in dumped
    assert "network_call_detected\": true" not in dumped
    assert "runtime_write_detected\": true" not in dumped


@pytest.mark.slow
def test_no_secret_token_body_in_safe_output(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    monkeypatch.setattr(guard, "format_trend_report", lambda report, fmt: {"status": report.get("status"), "summary": "safe"})
    result = guard.run_guarded_audit_trend_cli_projection(root=str(tmp_path), output_format="json")
    dumped = json.dumps(result["formatted_output"], ensure_ascii=False).lower()
    assert "secret" not in dumped
    assert "token" not in dumped
    assert "full body" not in dumped
