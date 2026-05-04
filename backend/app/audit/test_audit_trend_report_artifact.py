import json
from pathlib import Path

import pytest

from app.audit import audit_trend_report_artifact as artifact


def _report_dir(root: Path) -> Path:
    return root / "migration_reports" / "foundation_audit"


def _trend_report() -> dict:
    return {
        "trend_report_id": "trend_report_test",
        "status": "ok",
        "window": "all_available",
        "total_records_analyzed": 2,
        "series": [
            {
                "series_id": "s1",
                "metric_type": "warning_count",
                "metric_name": "queue_missing_warning_count",
                "points": [],
                "latest_value": 2,
                "sample_count": 1,
            }
        ],
        "regression_signals": [
            {
                "regression_id": "r1",
                "metric_type": "warning_count",
                "metric_name": "queue_missing_warning_count",
                "severity": "medium",
                "direction": "insufficient_data",
                "current_value": 2,
                "threshold": ">0",
                "recommended_action": "review_queue_path",
                "evidence_record_refs": ["record_a"],
                "source_record_refs": [f"record_{idx}" for idx in range(40)],
            }
        ],
        }


@pytest.mark.slow
def test_validate_accepts_json_under_foundation_audit(tmp_path):
    path = _report_dir(tmp_path) / "R241-12C_TREND_REPORT_ARTIFACT.json"
    result = artifact.validate_trend_artifact_output_path(str(path), root=str(tmp_path))
    assert result["valid"] is True


@pytest.mark.slow
def test_validate_accepts_markdown_and_text_under_foundation_audit(tmp_path):
    md = _report_dir(tmp_path) / "R241-12C_TREND_REPORT_ARTIFACT.md"
    txt = _report_dir(tmp_path) / "R241-12C_TREND_REPORT_ARTIFACT.txt"
    assert artifact.validate_trend_artifact_output_path(str(md), root=str(tmp_path))["valid"] is True
    assert artifact.validate_trend_artifact_output_path(str(txt), root=str(tmp_path))["valid"] is True


@pytest.mark.slow
def test_validate_rejects_audit_trail_jsonl(tmp_path):
    path = _report_dir(tmp_path) / "audit_trail" / "R241-12C_bad.jsonl"
    result = artifact.validate_trend_artifact_output_path(str(path), root=str(tmp_path))
    assert result["valid"] is False
    assert "audit_trail_path_forbidden" in result["errors"]


@pytest.mark.slow
def test_validate_rejects_parent_traversal(tmp_path):
    path = _report_dir(tmp_path) / ".." / "R241-12C_bad.json"
    result = artifact.validate_trend_artifact_output_path(str(path), root=str(tmp_path))
    assert result["valid"] is False
    assert "path_traversal_not_allowed" in result["errors"]


@pytest.mark.slow
def test_validate_rejects_runtime_path(tmp_path):
    path = _report_dir(tmp_path) / "runtime" / "R241-12C_bad.json"
    result = artifact.validate_trend_artifact_output_path(str(path), root=str(tmp_path))
    assert result["valid"] is False
    assert "runtime_path_forbidden" in result["errors"]


@pytest.mark.slow
def test_validate_rejects_invalid_suffix(tmp_path):
    path = _report_dir(tmp_path) / "R241-12C_bad.jsonl"
    result = artifact.validate_trend_artifact_output_path(str(path), root=str(tmp_path))
    assert result["valid"] is False
    assert "invalid_artifact_suffix" in result["errors"]


@pytest.mark.slow
def test_write_result_contains_required_fields(tmp_path):
    path = _report_dir(tmp_path) / "R241-12C_TREND_REPORT_ARTIFACT.txt"
    result = artifact.write_trend_report_artifact(_trend_report(), str(path), "text", root=str(tmp_path))
    for key in ["artifact_result_id", "artifact_type", "format", "status", "output_path", "bytes_written", "written_at"]:
        assert key in result


@pytest.mark.slow
def test_bundle_contains_required_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    result = artifact.generate_trend_report_artifact_bundle(root=str(tmp_path), output_format="json", dry_run=True)
    for key in ["bundle_id", "generated_at", "root", "window", "source_trend_report_id", "artifacts", "summary"]:
        assert key in result


@pytest.mark.slow
def test_render_json_is_serializable():
    rendered = artifact.render_trend_report_artifact_content(_trend_report(), "json")
    json.dumps(rendered["content"], ensure_ascii=False)
    assert rendered["errors"] == []


@pytest.mark.slow
def test_render_markdown_contains_no_auto_fix_notice():
    rendered = artifact.render_trend_report_artifact_content(_trend_report(), "markdown")
    assert "no-auto-fix" in rendered["content"]
    assert "projection-only" in rendered["content"]


@pytest.mark.slow
def test_render_text_contains_regression_summary():
    rendered = artifact.render_trend_report_artifact_content(_trend_report(), "text")
    assert "regression_summary" in rendered["content"]


@pytest.mark.slow
def test_render_does_not_expand_source_refs_or_sensitive_body():
    report = _trend_report()
    report["body"] = "secret token full body"
    rendered = artifact.render_trend_report_artifact_content(report, "json")
    dumped = json.dumps(rendered["content"], ensure_ascii=False).lower()
    assert "secret token full body" not in dumped
    refs = rendered["content"]["trend_report"]["regression_signals"][0]["source_record_refs"]
    assert len(refs) == 20


@pytest.mark.slow
def test_write_dry_run_true_does_not_write_file(tmp_path):
    path = _report_dir(tmp_path) / "R241-12C_TREND_REPORT_ARTIFACT.json"
    result = artifact.write_trend_report_artifact(_trend_report(), str(path), "json", dry_run=True, root=str(tmp_path))
    assert result["status"] == "skipped_dry_run"
    assert not path.exists()


@pytest.mark.slow
def test_write_dry_run_false_writes_tmp_artifact(tmp_path):
    path = _report_dir(tmp_path) / "R241-12C_TREND_REPORT_ARTIFACT.md"
    result = artifact.write_trend_report_artifact(_trend_report(), str(path), "markdown", dry_run=False, root=str(tmp_path))
    assert result["status"] == "written"
    assert path.exists()
    assert "Trend Report Artifact" in path.read_text(encoding="utf-8")


@pytest.mark.slow
def test_write_rejects_invalid_path(tmp_path):
    path = tmp_path / "audit_trail" / "bad.jsonl"
    result = artifact.write_trend_report_artifact(_trend_report(), str(path), "json", root=str(tmp_path))
    assert result["status"] == "blocked_invalid_path"


@pytest.mark.slow
def test_bundle_dry_run_true_does_not_write_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    result = artifact.generate_trend_report_artifact_bundle(root=str(tmp_path), output_format="all", dry_run=True)
    assert len(result["artifacts"]) == 3
    assert all(item["status"] == "skipped_dry_run" for item in result["artifacts"])
    assert not any(_report_dir(tmp_path).glob("R241-12C_TREND_REPORT_ARTIFACT.*"))


@pytest.mark.slow
def test_bundle_all_generates_three_artifact_results(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    result = artifact.generate_trend_report_artifact_bundle(root=str(tmp_path), output_format="all", dry_run=False)
    assert len(result["artifacts"]) == 3
    assert {item["format"] for item in result["artifacts"]} == {"json", "markdown", "text"}
    assert all(item["status"] == "written" for item in result["artifacts"])


@pytest.mark.slow
def test_generate_sample_writes_only_tmp_path_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    sample = _report_dir(tmp_path) / "R241-12C_TREND_REPORT_ARTIFACT_SAMPLE.json"
    result = artifact.generate_trend_report_artifact_sample(str(sample), root=str(tmp_path))
    assert sample.exists()
    assert result["output_path"] == str(sample)


@pytest.mark.slow
def test_no_audit_jsonl_write_or_line_count_change(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    audit_dir = _report_dir(tmp_path) / "audit_trail"
    audit_dir.mkdir(parents=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"a"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    artifact.generate_trend_report_artifact_bundle(root=str(tmp_path), output_format="all")
    assert jsonl.read_text(encoding="utf-8") == before


@pytest.mark.slow
def test_no_runtime_action_queue_network_or_autofix(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact, "generate_dryrun_nightly_trend_report", lambda **kw: {"trend_report": _trend_report(), "warnings": [], "errors": []})
    result = artifact.generate_trend_report_artifact_bundle(root=str(tmp_path), output_format="json", dry_run=False)
    dumped = json.dumps(result, ensure_ascii=False).lower()
    assert "auto_fix_allowed\": true" not in dumped
    assert "send_allowed\": true" not in dumped
    assert "webhook_call_allowed\": true" not in dumped
    assert "action_queue_write" not in dumped


@pytest.mark.slow
def test_no_secret_token_full_body_in_written_artifact(tmp_path):
    report = _trend_report()
    report["body"] = "secret token full body"
    path = _report_dir(tmp_path) / "R241-12C_TREND_REPORT_ARTIFACT.json"
    artifact.write_trend_report_artifact(report, str(path), "json", root=str(tmp_path))
    dumped = path.read_text(encoding="utf-8").lower()
    assert "secret token full body" not in dumped
