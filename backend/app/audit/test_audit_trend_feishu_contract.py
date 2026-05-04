import copy
import json
from pathlib import Path

from app.audit import audit_trend_feishu_contract as contract


def test_section_catalog_returns_non_empty_sections():
    result = contract.build_feishu_trend_section_catalog()
    assert result["section_count"] > 0
    assert result["sections"]


def test_section_catalog_contains_required_sections():
    result = contract.build_feishu_trend_section_catalog()
    section_types = {item["section_type"] for item in result["sections"]}
    assert {"headline", "trend_overview", "regression_summary", "guard_summary", "safety_notice"}.issubset(section_types)


def test_payload_mapping_send_allowed_false():
    result = contract.design_feishu_trend_payload_from_trend_report()
    assert result["payload_policy"]["send_allowed"] is False


def test_payload_mapping_no_webhook_call_true():
    result = contract.design_feishu_trend_payload_from_trend_report()
    assert result["payload_policy"]["no_webhook_call"] is True


def test_payload_mapping_no_runtime_write_true():
    result = contract.design_feishu_trend_payload_from_trend_report()
    assert result["payload_policy"]["no_runtime_write"] is True


def test_payload_mapping_no_action_queue_write_true():
    result = contract.design_feishu_trend_payload_from_trend_report()
    assert result["payload_policy"]["no_action_queue_write"] is True


def test_payload_mapping_no_auto_fix_true():
    result = contract.design_feishu_trend_payload_from_trend_report()
    assert result["payload_policy"]["no_auto_fix"] is True


def test_validation_rules_webhook_url_forbidden():
    rules = contract.build_feishu_trend_validation_rules()["rules"]
    assert any("webhook" in rule["rule_id"] and "must not appear" in rule["condition"] for rule in rules)


def test_validation_rules_token_secret_api_key_forbidden():
    rules = contract.build_feishu_trend_validation_rules()["rules"]
    text = json.dumps(rules, ensure_ascii=False)
    assert "token/secret/api_key" in text


def test_validation_rules_line_count_changed_false():
    rules = contract.build_feishu_trend_validation_rules()["rules"]
    assert any(rule["rule_id"] == "line_count_changed_false" for rule in rules)


def test_build_design_contains_phase_1_to_6():
    design = contract.build_feishu_trend_dryrun_design()
    phases = {item["phase"] for item in design["implementation_phases"]}
    assert {f"Phase {idx}" for idx in range(1, 7)}.issubset(phases)


def test_validate_design_valid_true():
    design = contract.build_feishu_trend_dryrun_design()
    result = contract.validate_feishu_trend_dryrun_design(design)
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_design_rejects_webhook_send_enabled():
    design = contract.build_feishu_trend_dryrun_design()
    bad = copy.deepcopy(design)
    bad["future_integration_points"].append({"real_webhook_send_enabled": True})
    result = contract.validate_feishu_trend_dryrun_design(bad)
    assert result["valid"] is False
    assert "real_webhook_send_forbidden" in result["errors"]


def test_validate_design_rejects_webhook_url():
    design = contract.build_feishu_trend_dryrun_design()
    bad = copy.deepcopy(design)
    bad["webhook_url"] = "https://example.invalid/hook"
    result = contract.validate_feishu_trend_dryrun_design(bad)
    assert result["valid"] is False
    assert any("webhook_or_network_url_forbidden" == item or "sensitive_marker_forbidden:webhook_url" == item for item in result["errors"])


def test_validate_design_rejects_token_secret_api_key():
    design = contract.build_feishu_trend_dryrun_design()
    bad = copy.deepcopy(design)
    bad["token"] = "x"
    bad["secret"] = "y"
    bad["api_key"] = "z"
    result = contract.validate_feishu_trend_dryrun_design(bad)
    assert result["valid"] is False
    assert "sensitive_marker_forbidden:token" in result["errors"]
    assert "sensitive_marker_forbidden:secret" in result["errors"]
    assert "sensitive_marker_forbidden:api_key" in result["errors"]


def test_validate_design_rejects_auto_fix_enabled():
    design = contract.build_feishu_trend_dryrun_design()
    bad = copy.deepcopy(design)
    bad["auto_fix_enabled"] = True
    result = contract.validate_feishu_trend_dryrun_design(bad)
    assert result["valid"] is False
    assert any("auto_fix_enabled" in item for item in result["errors"])


def test_generate_design_writes_only_tmp_path(tmp_path):
    output = tmp_path / "migration_reports" / "foundation_audit" / "R241-13A_FEISHU_TREND_SUMMARY_DRYRUN_CONTRACT.json"
    result = contract.generate_feishu_trend_dryrun_design(str(output))
    assert output.exists()
    assert Path(result["markdown_path"]).exists()
    assert str(output) == result["output_path"]


def test_does_not_write_audit_jsonl(tmp_path):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    output = tmp_path / "migration_reports" / "foundation_audit" / "R241-13A_FEISHU_TREND_SUMMARY_DRYRUN_CONTRACT.json"
    contract.generate_feishu_trend_dryrun_design(str(output))
    assert jsonl.read_text(encoding="utf-8") == before


def test_does_not_write_runtime_action_queue(tmp_path):
    output = tmp_path / "migration_reports" / "foundation_audit" / "R241-13A_FEISHU_TREND_SUMMARY_DRYRUN_CONTRACT.json"
    result = contract.generate_feishu_trend_dryrun_design(str(output))
    dumped = json.dumps(result, ensure_ascii=False).lower()
    assert '"no_runtime_write": false' not in dumped
    assert '"no_action_queue_write": false' not in dumped


def test_does_not_call_network_webhook_or_send_feishu():
    design = contract.build_feishu_trend_dryrun_design()
    dumped = json.dumps(design, ensure_ascii=False).lower()
    assert "send_enabled\": true" not in dumped
    assert "sends_feishu\": true" not in dumped
    assert "webhook_call_enabled" not in dumped


def test_does_not_push_feishu():
    mapping = contract.design_feishu_trend_payload_from_trend_report()
    assert mapping["payload_policy"]["send_allowed"] is False
    assert mapping["payload_policy"]["no_webhook_call"] is True
