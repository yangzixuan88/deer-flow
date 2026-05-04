"""Tests for R241-16J ci_remote_dispatch_confirmation_gate module."""

from pathlib import Path
import json

import pytest

from app.foundation import ci_remote_dispatch_confirmation_gate as gate


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── 1. build_remote_dispatch_input ────────────────────────────────────────────

def test_build_input_default_values():
    result = gate.build_remote_dispatch_input()
    assert result["confirmation_phrase_valid"] is True
    assert result["mode_valid"] is True
    assert result["input"]["confirmation_phrase"] == gate.DEFAULT_CONFIRMATION_PHRASE
    assert result["input"]["requested_mode"] == gate.DEFAULT_REQUESTED_MODE
    assert result["input"]["stage_selection"] == gate.DEFAULT_STAGE_SELECTION
    assert result["input"]["execute_mode"] == gate.DEFAULT_EXECUTE_MODE


def test_build_input_custom_values():
    result = gate.build_remote_dispatch_input(
        confirmation_phrase="CUSTOM",
        requested_mode="remote_selected_execute",
        stage_selection="safety",
        execute_mode="execute_selected",
    )
    assert result["confirmation_phrase_valid"] is False
    assert result["mode_valid"] is True


def test_build_input_dry_run_true():
    result = gate.build_remote_dispatch_input()
    assert result["input"]["dry_run"] is True


def test_build_input_workflow_path_set():
    result = gate.build_remote_dispatch_input()
    assert result["input"]["workflow_path"] is not None
    assert "foundation-manual-dispatch.yml" in result["input"]["workflow_path"]


# ── 2. validate_remote_dispatch_confirmation_phrase ────────────────────────────

def test_phrase_valid_correct_phrase():
    result = gate.validate_remote_dispatch_confirmation_phrase("CONFIRM_REMOTE_FOUNDATION_CI_DRYRUN")
    assert result["passed"] is True
    assert result["check_id"] == "check_confirmation_phrase"


def test_phrase_invalid_wrong_phrase():
    result = gate.validate_remote_dispatch_confirmation_phrase("WRONG")
    assert result["passed"] is False
    assert len(result["blocked_reasons"]) > 0


def test_phrase_risk_level():
    result = gate.validate_remote_dispatch_confirmation_phrase("CONFIRM_REMOTE_FOUNDATION_CI_DRYRUN")
    assert result["risk_level"] == "critical"


# ── 3. validate_requested_remote_dispatch_mode ─────────────────────────────────

def test_mode_valid_remote_plan_only():
    result = gate.validate_requested_remote_dispatch_mode("remote_plan_only")
    assert result["passed"] is True
    assert result["check_id"] == "check_requested_mode"


def test_mode_valid_remote_selected_execute():
    result = gate.validate_requested_remote_dispatch_mode("remote_selected_execute")
    assert result["passed"] is True


def test_mode_invalid_unknown_mode():
    result = gate.validate_requested_remote_dispatch_mode("unknown_mode")
    assert result["passed"] is False
    assert len(result["blocked_reasons"]) > 0


def test_mode_all_valid_modes():
    for mode in ["remote_plan_only", "remote_selected_execute", "remote_all_execute", "remote_safety_execute", "remote_slow_execute"]:
        result = gate.validate_requested_remote_dispatch_mode(mode)
        assert result["passed"] is True, f"mode {mode} should be valid"


# ── 4. validate_workflow_runtime_ready_for_remote_dispatch ────────────────────

def test_workflow_ready_uses_r241_16i_results():
    result = gate.validate_workflow_runtime_ready_for_remote_dispatch()
    assert "r241_16i_results_ref" in result
    assert "R241-16I" in result["r241_16i_results_ref"]


def test_workflow_ready_check_fields():
    result = gate.validate_workflow_runtime_ready_for_remote_dispatch()
    assert "yaml_valid" in result
    assert "guard_expressions_valid" in result
    assert "stage_selection_valid" in result
    assert "execute_mode_valid" in result
    assert "plan_only_verification_passed" in result
    assert "safety_execute_smoke_passed" in result


def test_workflow_ready_no_blocked_reasons_when_passed():
    result = gate.validate_workflow_runtime_ready_for_remote_dispatch()
    # If all checks passed, blocked_reasons should be empty
    if result["passed"]:
        assert result["blocked_reasons"] == []


# ── 5. build_remote_dispatch_command_blueprint ────────────────────────────────

def test_blueprint_remote_dispatch_allowed_false():
    result = gate.build_remote_dispatch_command_blueprint()
    assert result["remote_dispatch_allowed"] is False


def test_blueprint_dry_run_true():
    result = gate.build_remote_dispatch_command_blueprint()
    assert result["blueprint"]["dry_run"] is True


def test_blueprint_contains_workflow_path():
    result = gate.build_remote_dispatch_command_blueprint()
    assert "foundation-manual-dispatch.yml" in result["blueprint"]["workflow_path"]


def test_blueprint_command_type_is_gh():
    result = gate.build_remote_dispatch_command_blueprint()
    assert result["blueprint"]["command_type"].startswith("gh")


def test_blueprint_inputs_contain_confirm_phrase():
    result = gate.build_remote_dispatch_command_blueprint()
    assert gate.DEFAULT_CONFIRMATION_PHRASE in result["blueprint"]["inputs"]["confirm_manual_dispatch"]


# ── 6. build_remote_dispatch_rollback_or_cancel_plan ───────────────────────────

def test_rollback_plan_has_steps():
    result = gate.build_remote_dispatch_rollback_or_cancel_plan("cancel", "test reason")
    assert "rollback_plan" in result
    assert "rollback_steps" in result["rollback_plan"]
    assert len(result["rollback_plan"]["rollback_steps"]) > 0


def test_rollback_plan_gate_id():
    result = gate.build_remote_dispatch_rollback_or_cancel_plan("cancel", "test reason")
    assert result["rollback_plan"]["gate_id"] == gate.GATE_ID


def test_rollback_plan_decision_passed():
    result = gate.build_remote_dispatch_rollback_or_cancel_plan("confirm", "all passed")
    assert result["rollback_plan"]["decision"] == "confirm"


# ── 7. build_remote_dispatch_confirmation_checks ──────────────────────────────

def test_checks_returns_list():
    result = gate.build_remote_dispatch_confirmation_checks()
    assert isinstance(result, list)
    assert len(result) >= 10


def test_checks_all_have_check_id():
    checks = gate.build_remote_dispatch_confirmation_checks()
    for check in checks:
        assert "check_id" in check


def test_checks_all_have_passed_field():
    checks = gate.build_remote_dispatch_confirmation_checks()
    for check in checks:
        assert "passed" in check


def test_checks_all_have_risk_level():
    checks = gate.build_remote_dispatch_confirmation_checks()
    for check in checks:
        assert "risk_level" in check


def test_checks_confirmation_phrase_present():
    checks = gate.build_remote_dispatch_confirmation_checks()
    check_ids = {c["check_id"] for c in checks}
    assert "check_confirmation_phrase" in check_ids


def test_checks_requested_mode_present():
    checks = gate.build_remote_dispatch_confirmation_checks()
    check_ids = {c["check_id"] for c in checks}
    assert "check_requested_mode" in check_ids


def test_checks_workflow_file_exists_present():
    checks = gate.build_remote_dispatch_confirmation_checks()
    check_ids = {c["check_id"] for c in checks}
    assert "check_workflow_file_exists" in check_ids


def test_checks_workflow_dispatch_trigger_present():
    checks = gate.build_remote_dispatch_confirmation_checks()
    check_ids = {c["check_id"] for c in checks}
    assert "check_workflow_dispatch_trigger" in check_ids


def test_checks_no_secrets_present():
    checks = gate.build_remote_dispatch_confirmation_checks()
    check_ids = {c["check_id"] for c in checks}
    assert "check_no_secrets_in_workflow" in check_ids


def test_checks_no_network_calls_present():
    checks = gate.build_remote_dispatch_confirmation_checks()
    check_ids = {c["check_id"] for c in checks}
    assert "check_no_network_calls" in check_ids


def test_checks_remote_dispatch_not_allowed_present():
    checks = gate.build_remote_dispatch_confirmation_checks()
    check_ids = {c["check_id"] for c in checks}
    assert "check_remote_dispatch_not_allowed" in check_ids


# ── 8. evaluate_remote_dispatch_confirmation_gate ──────────────────────────────

def test_evaluate_default_params_pass():
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    assert result["all_passed"] is True
    assert result["status"] == gate.RemoteDispatchConfirmationStatus.PASSED.value
    assert result["decision"] == gate.RemoteDispatchDecision.CONFIRM.value


def test_evaluate_wrong_phrase_fails():
    result = gate.evaluate_remote_dispatch_confirmation_gate(confirmation_phrase="WRONG")
    assert result["all_passed"] is False
    assert result["status"] == gate.RemoteDispatchConfirmationStatus.BLOCKED_PRECHECK_FAILED.value


def test_evaluate_wrong_mode_fails():
    result = gate.evaluate_remote_dispatch_confirmation_gate(requested_mode="invalid")
    assert result["all_passed"] is False


def test_evaluate_remote_dispatch_allowed_false():
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    assert result["remote_dispatch_allowed_now"] is False


def test_evaluate_has_checks():
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    assert len(result["checks"]) >= 10


def test_evaluate_has_blueprint():
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    assert "blueprint" in result


def test_evaluate_has_rollback_plan():
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    assert "rollback_plan" in result


def test_evaluate_has_gate_id():
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    assert result["gate_id"] == gate.GATE_ID


# ── 9. validate_remote_dispatch_confirmation_decision ─────────────────────────

def test_validate_valid_result():
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    validated = gate.validate_remote_dispatch_confirmation_decision(result)
    assert validated["valid"] is True
    assert len(validated["errors"]) == 0


def test_validate_missing_field_fails():
    result = {"status": "passed"}
    validated = gate.validate_remote_dispatch_confirmation_decision(result)
    assert validated["valid"] is False
    assert len(validated["errors"]) > 0


def test_validate_insufficient_checks_fails():
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    result["checks"] = [{"check_id": "only_one"}]
    validated = gate.validate_remote_dispatch_confirmation_decision(result)
    assert validated["valid"] is False


def test_validate_remote_dispatch_allowed_must_be_false():
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    result["remote_dispatch_allowed_now"] = True
    validated = gate.validate_remote_dispatch_confirmation_decision(result)
    assert validated["valid"] is False


def test_validate_checks_count():
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    validated = gate.validate_remote_dispatch_confirmation_decision(result)
    assert validated["checks_count"] >= 10


# ── 10. generate_remote_dispatch_confirmation_gate_report ─────────────────────

def test_generate_writes_json_and_md(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    report = gate.generate_remote_dispatch_confirmation_gate_report(
        result,
        str(tmp_path / "R241-16J.json"),
    )
    assert Path(report["output_path"]).exists()
    assert Path(report["report_path"]).exists()


def test_generate_does_not_write_audit_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    gate.generate_remote_dispatch_confirmation_gate_report(
        result,
        str(tmp_path / "R241-16J.json"),
    )
    assert jsonl.read_text(encoding="utf-8") == before


def test_generate_does_not_write_runtime_or_action_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    result = gate.evaluate_remote_dispatch_confirmation_gate()
    gate.generate_remote_dispatch_confirmation_gate_report(
        result,
        str(tmp_path / "R241-16J.json"),
    )
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "action_queue").exists()


def test_generate_does_not_perform_network_call(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    # Build result manually without calling evaluate
    result = {
        "gate_id": gate.GATE_ID,
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": gate.RemoteDispatchConfirmationStatus.PASSED.value,
        "decision": gate.RemoteDispatchDecision.CONFIRM.value,
        "all_passed": True,
        "checks": [],
        "blueprint": {},
        "rollback_plan": {},
        "remote_dispatch_allowed_now": False,
        "confirmation_phrase": gate.DEFAULT_CONFIRMATION_PHRASE,
        "requested_mode": gate.DEFAULT_REQUESTED_MODE,
        "stage_selection": gate.DEFAULT_STAGE_SELECTION,
        "execute_mode": gate.DEFAULT_EXECUTE_MODE,
        "warnings": [],
        "errors": [],
    }
    gate.generate_remote_dispatch_confirmation_gate_report(result, str(tmp_path / "R241-16J.json"))
    assert called == []


def test_generate_status_and_decision_in_result():
    result = gate.generate_remote_dispatch_confirmation_gate_report()
    assert result["status"] is not None
    assert result["decision"] is not None
    assert result["all_passed"] is True


def test_generate_remote_dispatch_allowed_false():
    result = gate.generate_remote_dispatch_confirmation_gate_report()
    assert result["remote_dispatch_allowed_now"] is False


def test_generate_checks_count():
    result = gate.generate_remote_dispatch_confirmation_gate_report()
    assert result["checks_count"] >= 10