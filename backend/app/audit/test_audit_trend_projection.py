import json
from pathlib import Path

import pytest

from app.audit.audit_trend_contract import build_trend_metric_catalog, design_regression_detection_rules
from app.audit import audit_trend_projection as projection


def _record(record_id="r1", status="ok", source_command="truth-state", event_type="diagnostic_domain_result", warnings=None, summary=None):
    return {
        "audit_record_id": record_id,
        "payload_hash": f"hash-{record_id}",
        "source_command": source_command,
        "event_type": event_type,
        "status": status,
        "generated_at": "2026-04-25T00:00:00+00:00",
        "warnings": warnings or [],
        "errors": [],
        "summary": summary or {},
    }


def _metric(name):
    for metric in build_trend_metric_catalog()["metrics"]:
        if metric["metric_name"] == name:
            return metric
    raise AssertionError(f"missing metric {name}")


def test_load_trend_design_contract_missing_file_warning(tmp_path):
    result = projection.load_trend_design_contract(str(tmp_path / "missing.json"))
    assert result["exists"] is False
    assert result["warnings"]


def test_resolve_trend_window_all_available():
    result = projection.resolve_trend_window("all_available")
    assert result["window"] == "all_available"
    assert result["start_time"] is None
    assert result["end_time"] is None


def test_resolve_trend_window_custom_missing_start_end_warning():
    result = projection.resolve_trend_window("custom")
    assert "custom_window_missing_start_or_end" in result["warnings"]


def test_fetch_audit_records_for_trend_monkeypatch_no_jsonl_write(monkeypatch):
    monkeypatch.setattr(projection, "query_audit_trail", lambda **kwargs: {
        "query_id": "q1", "status": "ok", "records": [_record()], "file_summaries": [], "warnings": [], "errors": []
    })
    monkeypatch.setattr(projection, "scan_append_only_audit_trail", lambda **kwargs: {
        "total_invalid_lines": 0, "file_summaries": [], "warnings": [], "errors": []
    })
    result = projection.fetch_audit_records_for_trend(root="ignored")
    assert result["total_records"] == 1
    assert result["errors"] == []


def test_extract_partial_warning_rate():
    records = [_record("a", "partial_warning"), _record("b", "ok")]
    result = projection.extract_metric_value_from_records(records, _metric("partial_warning_rate"))
    assert result["metric_value"] == 0.5


def test_extract_failed_rate():
    records = [_record("a", "failed"), _record("b", "ok")]
    result = projection.extract_metric_value_from_records(records, _metric("failed_rate"))
    assert result["metric_value"] == 0.5


def test_extract_queue_missing_warning_count():
    records = [_record("a", warnings=["queue_missing:C:/x"]), _record("b")]
    result = projection.extract_metric_value_from_records(records, _metric("queue_missing_warning_count"))
    assert result["metric_value"] == 1


def test_extract_feishu_dry_run_count():
    records = [_record("a", source_command="feishu-summary"), _record("b", event_type="feishu_summary_dry_run")]
    result = projection.extract_metric_value_from_records(records, _metric("feishu_dry_run_count"))
    assert result["metric_value"] == 2


def test_extract_nightly_review_count():
    records = [_record("a", source_command="nightly"), _record("b", event_type="nightly_health_review")]
    result = projection.extract_metric_value_from_records(records, _metric("nightly_review_count"))
    assert result["metric_value"] == 2


def test_extract_invalid_jsonl_line_count():
    result = projection.extract_metric_value_from_records([], _metric("invalid_jsonl_line_count"), {"total_invalid_lines": 3})
    assert result["metric_value"] == 3


def test_build_trend_points_for_each_metric():
    catalog = build_trend_metric_catalog()["metrics"]
    result = projection.build_trend_points([_record()], catalog, "all_available")
    assert result["point_count"] == len(catalog)


def test_build_trend_series_insufficient_data():
    points = projection.build_trend_points([_record()], [_metric("total_audit_records")], "all_available")["points"]
    result = projection.build_trend_series(points, "all_available")
    assert result["series"][0]["direction"] == "insufficient_data"


def test_detect_regressions_invalid_line_count():
    point = {
        "metric_name": "invalid_jsonl_line_count",
        "metric_type": "invalid_line_count",
        "metric_value": 1,
        "timestamp": "2026-04-25T00:00:00+00:00",
        "source_record_refs": [],
    }
    series = projection.build_trend_series([point], "all_available")["series"]
    result = projection.detect_trend_regressions(series, design_regression_detection_rules()["rules"])
    assert any(s["metric_name"] == "invalid_jsonl_line_count" for s in result["regression_signals"])


def test_detect_regressions_no_nightly_record():
    point = {
        "metric_name": "nightly_review_count",
        "metric_type": "command_run_count",
        "metric_value": 0,
        "timestamp": "2026-04-25T00:00:00+00:00",
        "source_record_refs": [],
    }
    series = projection.build_trend_series([point], "all_available")["series"]
    result = projection.detect_trend_regressions(series, design_regression_detection_rules()["rules"])
    assert any(s["metric_name"] == "nightly_review_count" for s in result["regression_signals"])


def test_detect_regressions_feishu_missing_after_nightly():
    points = [
        {"metric_name": "nightly_review_count", "metric_type": "command_run_count", "metric_value": 1, "timestamp": "2026-04-25T00:00:00+00:00", "source_record_refs": ["n1"]},
        {"metric_name": "feishu_dry_run_count", "metric_type": "command_run_count", "metric_value": 0, "timestamp": "2026-04-25T00:00:00+00:00", "source_record_refs": []},
    ]
    series = projection.build_trend_series(points, "all_available")["series"]
    result = projection.detect_trend_regressions(series, design_regression_detection_rules()["rules"])
    assert any(s["metric_name"] == "feishu_dry_run_count" for s in result["regression_signals"])


def test_generate_dryrun_report_empty_records_insufficient_data(monkeypatch):
    monkeypatch.setattr(projection, "fetch_audit_records_for_trend", lambda **kwargs: {
        "query_result": {"query_id": "q1", "records": [], "warnings": [], "errors": []},
        "scan_summary": {"total_invalid_lines": 0, "file_summaries": [], "warnings": [], "errors": []},
        "records": [], "total_records": 0, "warnings": [], "errors": [],
    })
    result = projection.generate_dryrun_nightly_trend_report()
    assert result["trend_report"]["status"] == "insufficient_data"


def test_generate_dryrun_report_normal(monkeypatch):
    monkeypatch.setattr(projection, "fetch_audit_records_for_trend", lambda **kwargs: {
        "query_result": {"query_id": "q1", "records": [_record("n", source_command="nightly")], "warnings": [], "errors": []},
        "scan_summary": {"total_invalid_lines": 0, "file_summaries": [], "warnings": [], "errors": []},
        "records": [_record("n", source_command="nightly")], "total_records": 1, "warnings": [], "errors": [],
    })
    result = projection.generate_dryrun_nightly_trend_report()
    report = result["trend_report"]
    assert report["summary"]["series_count"] > 0
    assert "regression_signals" in report


def test_summarize_trend_report_counts_by_metric_type_and_severity():
    report = {
        "status": "partial_warning",
        "window": "all_available",
        "total_records_analyzed": 1,
        "series": [{"metric_type": "warning_count", "metric_name": "x"}],
        "regression_signals": [{"severity": "high", "metric_name": "x"}],
        "warnings": [],
        "errors": [],
    }
    summary = projection.summarize_trend_report(report)
    assert summary["by_metric_type"]["warning_count"] == 1
    assert summary["by_severity"]["high"] == 1


def test_format_markdown_does_not_expand_records():
    report = projection.generate_dryrun_nightly_trend_report(limit=1)["trend_report"]
    md = projection.format_trend_report(report, "markdown")
    assert isinstance(md, str)
    assert "records" not in md.lower()


def test_format_text_does_not_expand_records():
    report = projection.generate_dryrun_nightly_trend_report(limit=1)["trend_report"]
    text = projection.format_trend_report(report, "text")
    assert isinstance(text, str)
    assert "records" not in text.lower()


    def test_generate_sample_writes_only_tmp_path(tmp_path):
        output = tmp_path / "trend_sample.json"
        result = projection.generate_dryrun_trend_projection_sample(str(output), root=str(tmp_path))
        assert output.exists()
        assert result["output_path"] == str(output)


def test_cli_audit_trend_command_exists():
    from app.foundation.read_only_diagnostics_cli import main
    assert callable(main)


@pytest.mark.slow
def test_audit_trend_does_not_write_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text(json.dumps(_record()) + "\n", encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    projection.generate_dryrun_nightly_trend_report(root=str(tmp_path))
    assert jsonl.read_text(encoding="utf-8") == before


@pytest.mark.slow
def test_audit_trend_does_not_modify_line_count(tmp_path):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text(json.dumps(_record("a")) + "\n" + json.dumps(_record("b")) + "\n", encoding="utf-8")
    before = len(jsonl.read_text(encoding="utf-8").splitlines())
    projection.generate_dryrun_nightly_trend_report(root=str(tmp_path))
    after = len(jsonl.read_text(encoding="utf-8").splitlines())
    assert after == before


@pytest.mark.slow
def test_no_runtime_action_queue_network_or_autofix():
    result = projection.generate_dryrun_nightly_trend_report(limit=1)
    text = json.dumps(result, ensure_ascii=False).lower()
    assert "auto_fix_allowed\": true" not in text
    assert "send_allowed\": true" not in text
    assert "webhook_call_allowed\": true" not in text
    assert "action_queue_write" not in text


@pytest.mark.slow
def test_no_secret_token_full_body_in_formatted_output():
    report = {
        "status": "ok",
        "window": "all_available",
        "total_records_analyzed": 1,
        "series": [],
        "regression_signals": [],
        "warnings": ["safe"],
        "errors": [],
        "body": "secret token full body",
    }
    text = projection.format_trend_report(report, "json")
    dumped = json.dumps(text, ensure_ascii=False).lower()
    assert "secret token full body" not in dumped
