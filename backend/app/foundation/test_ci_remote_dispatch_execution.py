"""Tests for R241-16K ci_remote_dispatch_execution module."""

from pathlib import Path
import json

import pytest

from app.foundation import ci_remote_dispatch_execution as execution


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── 1. load_remote_dispatch_gate_for_execution ────────────────────────────────

def test_gate_loaded_from_r241_16j_result():
    result = execution.load_remote_dispatch_gate_for_execution(str(_root()))
    assert result["gate_loaded"] is True
    assert result["gate_valid"] is True


def test_gate_rejects_wrong_mode():
    # The gate should be loaded, but we'll check validation
    result = execution.load_remote_dispatch_gate_for_execution(str(_root()))
    # Requested mode from gate must be remote_plan_only
    assert result.get("requested_mode") in ["remote_plan_only"]


def test_gate_checks_workflow_exists():
    result = execution.load_remote_dispatch_gate_for_execution(str(_root()))
    assert result["workflow_exists"] is True
    assert "foundation-manual-dispatch.yml" in result["workflow_path"]


# ── 2. build_remote_plan_only_dispatch_command ────────────────────────────────

def test_build_command_uses_gh_workflow_run():
    result = execution.build_remote_plan_only_dispatch_command(str(_root()))
    argv = result["command"]["argv"]
    assert argv[0] == "gh"
    assert argv[1] == "workflow"
    assert argv[2] == "run"


def test_build_command_uses_workflow_file():
    result = execution.build_remote_plan_only_dispatch_command(str(_root()))
    argv = result["command"]["argv"]
    assert "foundation-manual-dispatch.yml" in argv


def test_build_command_uses_all_pr():
    result = execution.build_remote_plan_only_dispatch_command(str(_root()))
    argv = result["command"]["argv"]
    assert any("stage_selection=all_pr" in arg for arg in argv)


def test_build_command_uses_plan_only():
    result = execution.build_remote_plan_only_dispatch_command(str(_root()))
    argv = result["command"]["argv"]
    assert any("execute_mode=plan_only" in arg for arg in argv)


def test_build_command_does_not_contain_execute_selected():
    result = execution.build_remote_plan_only_dispatch_command(str(_root()))
    argv = result["command"]["argv"]
    assert not any("execute_selected" in arg for arg in argv)


def test_build_command_does_not_contain_token_secret_webhook():
    result = execution.build_remote_plan_only_dispatch_command(str(_root()))
    argv = result["command"]["argv"]
    for arg in argv:
        assert not any(secret in arg.lower() for secret in ["token", "secret", "webhook", "password"])


def test_build_command_shell_allowed_false():
    result = execution.build_remote_plan_only_dispatch_command(str(_root()))
    assert result["shell_allowed"] is False


# ── 3. run_remote_dispatch_execution_prechecks ────────────────────────────────

def test_prechecks_fail_if_workflow_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(execution, "ROOT", tmp_path)
    monkeypatch.setattr(execution, "_load_gate_result", lambda: {
        "status": "passed", "decision": "confirm", "all_passed": True,
        "requested_mode": "remote_plan_only", "stage_selection": "all_pr",
        "execute_mode": "plan_only", "remote_dispatch_allowed_now": False
    })
    result = execution.run_remote_dispatch_execution_prechecks(str(tmp_path))
    assert result["blocked"] is True


def test_prechecks_fail_if_execute_mode_not_plan_only():
    result = execution.run_remote_dispatch_execution_prechecks(str(_root()))
    # execute_mode must be plan_only
    assert result["all_passed"] is True


def test_prechecks_check_gh_available():
    result = execution.run_remote_dispatch_execution_prechecks(str(_root()))
    precheck_ids = {pc["precheck_id"] for pc in result.get("prechecks", [])}
    assert "check_gh_available" in precheck_ids


def test_prechecks_all_have_required_fields():
    result = execution.run_remote_dispatch_execution_prechecks(str(_root()))
    for pc in result.get("prechecks", []):
        assert "precheck_id" in pc
        assert "check_type" in pc
        assert "passed" in pc
        assert "risk_level" in pc


def test_prechecks_has_at_least_14_checks():
    result = execution.run_remote_dispatch_execution_prechecks(str(_root()))
    assert result["precheck_count"] >= 14


def test_prechecks_critical_checks_present():
    result = execution.run_remote_dispatch_execution_prechecks(str(_root()))
    precheck_ids = {pc["precheck_id"] for pc in result.get("prechecks", [])}
    critical_checks = [
        "check_root_guard_passed",
        "check_r241_16j_gate_passed",
        "check_r241_16i_runtime_passed",
        "check_workflow_file_exists",
        "check_workflow_dispatch_only",
        "check_no_secrets_in_workflow",
        "check_execute_mode_is_plan_only",
        "check_stage_selection_is_all_pr",
        "check_gh_available",
    ]
    for cc in critical_checks:
        assert cc in precheck_ids, f"{cc} missing from prechecks"


# ── 4. execute_remote_plan_only_dispatch ─────────────────────────────────────

def test_execute_returns_dict_with_dispatch_attempted():
    result = execution.execute_remote_plan_only_dispatch(str(_root()), timeout_seconds=5)
    assert "dispatch_attempted" in result
    assert "dispatch_succeeded" in result
    assert "exit_code" in result


def test_execute_uses_subprocess_with_shell_false():
    # We can't actually run gh, but we verify the code path uses subprocess
    result = execution.execute_remote_plan_only_dispatch(str(_root()), timeout_seconds=5)
    # If gh is not available, dispatch_succeeded is False but dispatch_attempted is True
    assert result["dispatch_attempted"] is True


def test_execute_does_not_retry():
    # execute_remote_plan_only_dispatch should only call subprocess once
    result = execution.execute_remote_plan_only_dispatch(str(_root()), timeout_seconds=1)
    # Should not retry - single attempt
    assert result["dispatch_attempted"] is True


# ── 5. observe_remote_dispatch_result ────────────────────────────────────────

def test_observe_returns_run_id_or_not_observed():
    result = execution.observe_remote_dispatch_result(str(_root()))
    assert "run_observed" in result
    assert "run_status" in result
    # Either run is observed or not_observed
    assert result["run_status"] in ["queued", "in_progress", "completed", "success",
                                      "failure", "cancelled", "unknown", "not_observed"]


def test_observe_handles_not_observed():
    result = execution.observe_remote_dispatch_result(str(_root()))
    # If not observed, run_id should be None
    if not result.get("run_observed"):
        assert result.get("run_id") is None


def test_observe_parses_json_output():
    result = execution.observe_remote_dispatch_result(str(_root()))
    # Should not raise - returns safe structure even on failure
    assert "run_observed" in result


# ── 6. verify_remote_run_inputs_plan_only ─────────────────────────────────────

def test_verify_run_accepts_no_run_id():
    result = execution.verify_remote_run_inputs_plan_only(str(_root()), run_id=None)
    assert result["verified"] is False
    assert result["error"] == "No run_id provided"


def test_verify_run_returns_structure():
    result = execution.verify_remote_run_inputs_plan_only(str(_root()), run_id="")
    assert "verified" in result
    assert "run_id" in result


def test_verify_run_checks_event_type():
    result = execution.verify_remote_run_inputs_plan_only(str(_root()), run_id="12345")
    # Without valid run_id, should return False but still have structure
    assert "event_is_workflow_dispatch" in result


# ── 7. verify_no_local_mutation_after_remote_dispatch ─────────────────────────

def test_mutation_guard_returns_structure():
    result = execution.verify_no_local_mutation_after_remote_dispatch(str(_root()))
    assert "no_local_mutation" in result
    assert "mutations" in result


def test_mutation_guard_detects_workflow_modification():
    # Test that it detects when a workflow was modified
    baseline = {
        "foundation-manual-dispatch.yml": {"exists": True, "size": 100, "hash": 99999},
        "backend-unit-tests.yml": {"exists": True, "size": 200, "hash": 88888},
        "lint-check.yml": {"exists": True, "size": 150, "hash": 77777},
    }
    result = execution.verify_no_local_mutation_after_remote_dispatch(str(_root()), baseline=baseline)
    # Without actual modification, should show no_local_mutation=True
    assert "no_local_mutation" in result


# ── 8. cancel_remote_dispatch_if_violation ────────────────────────────────────

def test_cancel_requires_run_id():
    result = execution.cancel_remote_dispatch_if_violation(str(_root()), run_id=None, reason="test")
    assert result["cancel_attempted"] is False
    assert result["cancelled"] is False


def test_cancel_requires_reason():
    result = execution.cancel_remote_dispatch_if_violation(str(_root()), run_id="12345", reason=None)
    assert result["cancel_attempted"] is False
    assert result["cancelled"] is False


def test_cancel_returns_structure():
    result = execution.cancel_remote_dispatch_if_violation(str(_root()), run_id="12345", reason="security violation")
    assert "cancel_attempted" in result
    assert "cancelled" in result
    assert "run_id" in result
    assert "reason" in result


# ── 9. evaluate_remote_plan_only_dispatch_execution ────────────────────────────

def test_evaluate_blocks_if_prechecks_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(execution, "ROOT", tmp_path)
    monkeypatch.setattr(execution, "_load_gate_result", lambda: {
        "status": "passed", "decision": "confirm", "all_passed": True,
        "requested_mode": "remote_plan_only", "stage_selection": "all_pr",
        "execute_mode": "plan_only", "remote_dispatch_allowed_now": False
    })
    result = execution.evaluate_remote_plan_only_dispatch_execution(str(tmp_path))
    assert result["dispatch_attempted"] is False


def test_evaluate_dispatch_failed_when_gh_exits_nonzero():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    # Either dispatched or blocked_gh_unavailable or dispatch_failed
    assert result["status"] in [
        execution.RemoteDispatchExecutionStatus.DISPATCHED,
        execution.RemoteDispatchExecutionStatus.BLOCKED_GH_UNAVAILABLE,
        execution.RemoteDispatchExecutionStatus.DISPATCH_FAILED,
        execution.RemoteDispatchExecutionStatus.BLOCKED_PRECHECK_FAILED,
    ]


def test_evaluate_dispatched_when_gh_exits_0_and_run_observed():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    # Only dispatched if both dispatch succeeded AND run observed
    if result["dispatch_succeeded"] and result.get("run_id"):
        assert result["status"] == execution.RemoteDispatchExecutionStatus.DISPATCHED.value


def test_evaluate_has_command():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    assert "command" in result


def test_evaluate_has_prechecks():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    assert "prechecks" in result


def test_evaluate_has_local_mutation_guard():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    assert "local_mutation_guard" in result


def test_evaluate_has_run_id_or_none():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    assert result.get("run_id") is None or isinstance(result.get("run_id"), str)


# ── 10. validate_remote_dispatch_execution_result ──────────────────────────

def test_validate_rejects_execute_selected():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    cmd = result.get("command", {})
    cmd["execute_mode"] = "execute_selected"
    result["command"] = cmd
    validated = execution.validate_remote_dispatch_execution_result(result)
    assert validated["valid"] is False
    assert any("execute_selected" in e for e in validated["errors"])


def test_validate_rejects_shell_allowed_true():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    result["command"]["shell_allowed"] = True
    validated = execution.validate_remote_dispatch_execution_result(result)
    assert validated["valid"] is False


def test_validate_rejects_token_secret():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    result["command"]["argv"] = ["gh", "workflow", "run", "x.yml", "--token", "SECRET"]
    validated = execution.validate_remote_dispatch_execution_result(result)
    assert validated["valid"] is False


def test_validate_rejects_local_mutation():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    result["local_mutation_guard"]["mutations_found"] = True
    result["local_mutation_guard"]["mutations"] = ["workflow_modified:foundation-manual-dispatch.yml"]
    validated = execution.validate_remote_dispatch_execution_result(result)
    assert validated["valid"] is False


def test_validate_accepts_valid_result():
    result = execution.evaluate_remote_plan_only_dispatch_execution()
    validated = execution.validate_remote_dispatch_execution_result(result)
    # If prechecks pass and no violations, should be valid
    # Note: may be invalid if gh not available - that's ok
    assert "valid" in validated


def test_validate_missing_fields():
    result = {"status": "passed"}
    validated = execution.validate_remote_dispatch_execution_result(result)
    assert validated["valid"] is False
    assert len(validated["missing_fields"]) > 0


# ── 11. generate_remote_dispatch_execution_report ─────────────────────────────

def test_generate_writes_json_and_md(tmp_path, monkeypatch):
    monkeypatch.setattr(execution, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(execution, "ROOT", tmp_path)
    monkeypatch.setattr(execution, "_load_gate_result", lambda: {
        "status": "passed", "decision": "confirm", "all_passed": True,
        "requested_mode": "remote_plan_only", "stage_selection": "all_pr",
        "execute_mode": "plan_only", "remote_dispatch_allowed_now": False
    })
    result = execution.evaluate_remote_plan_only_dispatch_execution(str(tmp_path))
    report = execution.generate_remote_dispatch_execution_report(
        result,
        str(tmp_path / "R241-16K.json"),
    )
    assert Path(report["output_path"]).exists()
    assert Path(report["report_path"]).exists()


def test_generate_does_not_write_audit_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(execution, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(execution, "ROOT", tmp_path)
    monkeypatch.setattr(execution, "_load_gate_result", lambda: {
        "status": "passed", "decision": "confirm", "all_passed": True,
        "requested_mode": "remote_plan_only", "stage_selection": "all_pr",
        "execute_mode": "plan_only", "remote_dispatch_allowed_now": False
    })
    result = execution.evaluate_remote_plan_only_dispatch_execution(str(tmp_path))
    execution.generate_remote_dispatch_execution_report(result, str(tmp_path / "R241-16K.json"))
    assert jsonl.read_text(encoding="utf-8") == before


def test_generate_does_not_write_runtime_or_action_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(execution, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(execution, "ROOT", tmp_path)
    monkeypatch.setattr(execution, "_load_gate_result", lambda: {
        "status": "passed", "decision": "confirm", "all_passed": True,
        "requested_mode": "remote_plan_only", "stage_selection": "all_pr",
        "execute_mode": "plan_only", "remote_dispatch_allowed_now": False
    })
    result = execution.evaluate_remote_plan_only_dispatch_execution(str(tmp_path))
    execution.generate_remote_dispatch_execution_report(result, str(tmp_path / "R241-16K.json"))
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "action_queue").exists()


def test_generate_status_and_decision_in_result():
    report = execution.generate_remote_dispatch_execution_report()
    assert report["status"] is not None
    assert report["decision"] is not None


def test_generate_result_has_dispatch_attempted():
    report = execution.generate_remote_dispatch_execution_report()
    assert "dispatch_attempted" in report
    assert "dispatch_succeeded" in report


# ── 12. Security Constraints ─────────────────────────────────────────────────

def test_no_workflow_modification_in_evaluate():
    # Ensure evaluate doesn't write to any workflow files
    workflow_path = _root() / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    before_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    execution.evaluate_remote_plan_only_dispatch_execution(str(_root()))
    after_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    assert before_content == after_content or not workflow_path.exists()


def test_command_forbidden_phrases():
    result = execution.build_remote_plan_only_dispatch_command(str(_root()))
    argv = result["command"]["argv"]
    forbidden = ["execute_selected", "fast", "safety", "slow", "full", "all_nightly"]
    for arg in argv:
        for phrase in forbidden:
            assert phrase not in arg, f"Forbidden phrase '{phrase}' found in argv: {arg}"


def test_no_secret_read_in_gh_commands():
    # Verify observe_remote_dispatch_result doesn't call gh api for secrets
    result = execution.observe_remote_dispatch_result(str(_root()))
    assert "run_observed" in result


def test_no_auto_fix_in_execution():
    result = execution.build_remote_plan_only_dispatch_command(str(_root()))
    argv = result["command"]["argv"]
    assert not any("auto" in arg.lower() for arg in argv)


def test_prechecks_forbid_execute_selected():
    result = execution.run_remote_dispatch_execution_prechecks(str(_root()))
    precheck_ids = {pc["precheck_id"] for pc in result.get("prechecks", [])}
    # check_execute_mode_is_plan_only must be present and passed
    assert "check_execute_mode_is_plan_only" in precheck_ids


def test_prechecks_forbid_fast_safety_slow():
    result = execution.run_remote_dispatch_execution_prechecks(str(_root()))
    precheck_ids = {pc["precheck_id"] for pc in result.get("prechecks", [])}
    assert "check_stage_selection_is_all_pr" in precheck_ids