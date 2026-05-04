import json
from pathlib import Path

from app.audit.audit_trend_contract import (
    build_nightly_trend_report_design,
    build_trend_metric_catalog,
    build_trend_window_spec,
    design_regression_detection_rules,
    design_trend_extraction_from_audit_query,
    generate_nightly_trend_report_design,
    validate_trend_report_design,
)


def _metric_names(catalog):
    return {metric["metric_name"] for metric in catalog["metrics"]}


def _rule_ids(rules):
    return {rule["rule_id"] for rule in rules["rules"]}


def test_build_trend_metric_catalog_returns_non_empty_metrics():
    catalog = build_trend_metric_catalog()
    assert catalog["metric_count"] > 0
    assert catalog["metrics"]


def test_catalog_contains_partial_warning_rate():
    catalog = build_trend_metric_catalog()
    assert "partial_warning_rate" in _metric_names(catalog)


def test_catalog_contains_invalid_line_count():
    catalog = build_trend_metric_catalog()
    assert "invalid_jsonl_line_count" in _metric_names(catalog)


def test_build_trend_window_spec_contains_required_windows():
    windows = build_trend_window_spec()["windows"]
    assert "last_24h" in windows
    assert "last_7d" in windows
    assert "last_30d" in windows


def test_extraction_design_contains_status_warnings_generated_at():
    extraction = design_trend_extraction_from_audit_query()
    fields = {item["field"] for item in extraction["extraction_fields"]}
    assert "status" in fields
    assert "warnings" in fields
    assert "generated_at" in fields


def test_regression_rules_include_queue_missing_persists():
    rules = design_regression_detection_rules()
    assert "queue_missing_persists" in _rule_ids(rules)


def test_regression_rules_include_no_nightly_record():
    rules = design_regression_detection_rules()
    assert "no_nightly_record_in_expected_window" in _rule_ids(rules)


def test_regression_rules_auto_fix_false():
    rules = design_regression_detection_rules()["rules"]
    assert rules
    assert all(rule["auto_fix_allowed"] is False for rule in rules)


def test_build_nightly_trend_report_design_contains_phase_1_to_6():
    design = build_nightly_trend_report_design()
    phase_labels = {phase["phase"] for phase in design["implementation_phases"]}
    assert {f"Phase {idx}" for idx in range(1, 7)} <= phase_labels


def test_validate_trend_report_design_valid_true():
    design = build_nightly_trend_report_design()
    validation = validate_trend_report_design(design)
    assert validation["valid"] is True
    assert validation["errors"] == []


def test_validate_trend_report_design_rejects_auto_fix_enabled():
    design = build_nightly_trend_report_design()
    design["regression_rules"][0]["auto_fix_allowed"] = True
    validation = validate_trend_report_design(design)
    assert validation["valid"] is False
    assert any("auto_fix_enabled" in error for error in validation["errors"])


def test_validate_trend_report_design_rejects_feishu_send_enabled():
    design = build_nightly_trend_report_design()
    design["future_integration_points"].append({
        "name": "bad_feishu_sender",
        "send_allowed": True,
    })
    validation = validate_trend_report_design(design)
    assert validation["valid"] is False
    assert any("external_send_or_network_enabled" in error for error in validation["errors"])


def test_generate_nightly_trend_report_design_writes_only_tmp_path(tmp_path):
    output_path = tmp_path / "trend_contract.json"
    result = generate_nightly_trend_report_design(str(output_path))

    assert Path(result["json_path"]) == output_path
    assert output_path.exists()
    assert output_path.with_suffix(".md").exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["validation"]["valid"] is True


def test_does_not_write_audit_jsonl(tmp_path):
    output_path = tmp_path / "trend_contract.json"
    generate_nightly_trend_report_design(str(output_path))
    assert list(tmp_path.glob("*.jsonl")) == []


def test_does_not_modify_audit_trail_line_count(tmp_path):
    audit_dir = tmp_path / "audit_trail"
    audit_dir.mkdir()
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"a":1}\n{"b":2}\n', encoding="utf-8")
    before = len(jsonl.read_text(encoding="utf-8").splitlines())

    generate_nightly_trend_report_design(str(tmp_path / "trend_contract.json"))

    after = len(jsonl.read_text(encoding="utf-8").splitlines())
    assert after == before


def test_does_not_call_network_or_webhook():
    design = build_nightly_trend_report_design()
    text = json.dumps(design, ensure_ascii=False)
    assert '"send_allowed": true' not in text.lower()
    assert '"webhook_call_allowed": true' not in text.lower()
    assert '"network_allowed": true' not in text.lower()


def test_does_not_modify_runtime_or_action_queue():
    design = build_nightly_trend_report_design()
    blocked = {item["action"]: item["blocked"] for item in design["blocked_actions"]}
    assert blocked["runtime_write"] is True
    assert blocked["action_queue_write"] is True
    assert blocked["auto_fix"] is True
