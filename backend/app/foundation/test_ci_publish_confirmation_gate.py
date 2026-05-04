"""Tests for R241-16O publish confirmation gate."""

from pathlib import Path

from app.foundation import ci_publish_confirmation_gate as gate


def _ready_review() -> dict:
    return {
        "review_id": "rv-ready",
        "status": "ready_for_publish_confirmation",
        "decision": "allow_publish_confirmation_gate",
        "local_workflow_exists": True,
        "remote_workflow_exists": False,
        "workflow_diff_summary": {
            "diff_only_target_workflow": True,
            "workflow_content_safe": True,
            "workflow_dispatch_only": True,
            "has_pr_trigger": False,
            "has_push_trigger": False,
            "has_schedule_trigger": False,
            "has_secrets": False,
        },
        "existing_workflows_unchanged": True,
        "publish_command_blueprints": [
            {"command_id": "option_c_push", "command_allowed_now": False}
        ],
        "rollback_plan": {"no_auto_rollback": True},
        "confirmation_requirements": {
            "confirmation_phrase": gate.EXPECTED_CONFIRMATION_PHRASE
        },
        "safety_summary": {
            "no_git_commit_executed": True,
            "no_git_push_executed": True,
            "no_gh_workflow_run_executed": True,
        },
    }


def _blocked_review() -> dict:
    review = _ready_review()
    review["status"] = "blocked_unexpected_diff"
    review["decision"] = "block_publish"
    review["workflow_diff_summary"]["diff_only_target_workflow"] = False
    return review


def _patch_ready(monkeypatch):
    monkeypatch.setattr(gate, "_load_publish_readiness_review", lambda root=None: _ready_review())


def test_build_input_missing_phrase():
    result = gate.build_publish_confirmation_input(None, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["phrase_present"] is False
    assert result["phrase_exact_match"] is False


def test_build_input_correct_phrase():
    result = gate.build_publish_confirmation_input(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["phrase_present"] is True
    assert result["phrase_exact_match"] is True


def test_build_input_wrong_phrase():
    result = gate.build_publish_confirmation_input("CONFIRM_PUBLISH_FOUNDATION_MANUAL_WORKFLOW ", gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["phrase_exact_match"] is False


def test_build_input_default_option_c():
    result = gate.build_publish_confirmation_input(gate.EXPECTED_CONFIRMATION_PHRASE)
    assert result["requested_option"] == gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION


def test_build_input_rejects_unknown_option():
    result = gate.build_publish_confirmation_input(gate.EXPECTED_CONFIRMATION_PHRASE, "unknown")
    assert result["requested_option_valid"] is False


def test_build_input_rejects_webhook_option():
    result = gate.build_publish_confirmation_input(gate.EXPECTED_CONFIRMATION_PHRASE, "webhook")
    assert result["requested_option_valid"] is False


def test_build_input_rejects_secret_option():
    result = gate.build_publish_confirmation_input(gate.EXPECTED_CONFIRMATION_PHRASE, "secret")
    assert result["requested_option_valid"] is False


def test_build_input_rejects_auto_fix_option():
    result = gate.build_publish_confirmation_input(gate.EXPECTED_CONFIRMATION_PHRASE, "auto_fix")
    assert result["requested_option_valid"] is False


def test_build_input_rejects_execute_selected_option():
    result = gate.build_publish_confirmation_input(gate.EXPECTED_CONFIRMATION_PHRASE, "execute_selected")
    assert result["requested_option_valid"] is False


def test_validate_phrase_correct_passes():
    inp = gate.build_publish_confirmation_input(gate.EXPECTED_CONFIRMATION_PHRASE)
    assert gate.validate_publish_confirmation_phrase(inp)["passed"] is True


def test_validate_phrase_missing_blocked():
    inp = gate.build_publish_confirmation_input(None)
    result = gate.validate_publish_confirmation_phrase(inp)
    assert result["passed"] is False
    assert "missing_confirmation_phrase" in result["blocked_reasons"]


def test_validate_phrase_wrong_blocked():
    inp = gate.build_publish_confirmation_input("WRONG")
    result = gate.validate_publish_confirmation_phrase(inp)
    assert result["passed"] is False
    assert "invalid_confirmation_phrase" in result["blocked_reasons"]


def test_validate_option_a_keep_local_allowed_as_conservative():
    inp = gate.build_publish_confirmation_input(None, gate.PublishTargetOption.OPTION_A_KEEP_LOCAL_ONLY)
    result = gate.validate_requested_publish_option(inp)
    assert result["passed"] is True


def test_validate_option_c_needs_confirmation():
    inp = gate.build_publish_confirmation_input(None, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    result = gate.validate_requested_publish_option(inp)
    assert result["passed"] is False
    assert "confirmation_required_for_publish_option" in result["blocked_reasons"]


def test_validate_readiness_requires_r241_16n_ready(monkeypatch):
    _patch_ready(monkeypatch)
    assert gate.validate_publish_readiness_still_valid()["passed"] is True


def test_validate_readiness_rejects_blocked_unexpected_diff(monkeypatch):
    monkeypatch.setattr(gate, "_load_publish_readiness_review", lambda root=None: _blocked_review())
    result = gate.validate_publish_readiness_still_valid()
    assert result["passed"] is False
    assert "status_ready" in result["blocked_reasons"]
    assert "diff_only_target_workflow" in result["blocked_reasons"]


def test_validate_security_rejects_git_commit_executed(monkeypatch):
    monkeypatch.setattr(gate, "_build_security_state", lambda root=None: {"git_commit_executed": True})
    result = gate.validate_publish_security_conditions()
    assert result["passed"] is False
    assert "git_commit_executed" in result["blocked_reasons"]


def test_validate_security_rejects_git_push_executed(monkeypatch):
    monkeypatch.setattr(gate, "_build_security_state", lambda root=None: {"git_push_executed": True})
    result = gate.validate_publish_security_conditions()
    assert result["passed"] is False
    assert "git_push_executed" in result["blocked_reasons"]


def test_validate_security_rejects_gh_workflow_run_executed(monkeypatch):
    monkeypatch.setattr(gate, "_build_security_state", lambda root=None: {"gh_workflow_run_executed": True})
    result = gate.validate_publish_security_conditions()
    assert result["passed"] is False
    assert "gh_workflow_run_executed" in result["blocked_reasons"]


def test_evaluate_missing_phrase_option_c_blocked(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(None, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["status"] == gate.PublishConfirmationStatus.BLOCKED_MISSING_CONFIRMATION
    assert result["decision"] == gate.PublishConfirmationDecision.BLOCK


def test_evaluate_wrong_phrase_blocked(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate("WRONG", gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["status"] == gate.PublishConfirmationStatus.BLOCKED_INVALID_CONFIRMATION


def test_evaluate_correct_phrase_option_a_keep_local_only(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_A_KEEP_LOCAL_ONLY)
    assert result["decision"] == gate.PublishConfirmationDecision.KEEP_LOCAL_ONLY
    assert result["publish_allowed_now"] is False


def test_evaluate_correct_phrase_option_c_allow_publish_implementation_review(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["status"] == gate.PublishConfirmationStatus.ALLOWED_FOR_NEXT_REVIEW
    assert result["decision"] == gate.PublishConfirmationDecision.ALLOW_PUBLISH_IMPLEMENTATION_REVIEW
    assert result["allowed_next_phase"] == "R241-16P_publish_implementation"


def test_publish_allowed_now_always_false(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_D_OPEN_PR_AFTER_CONFIRMATION)
    assert result["publish_allowed_now"] is False


def test_validate_decision_valid_true(monkeypatch):
    _patch_ready(monkeypatch)
    decision = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert gate.validate_publish_confirmation_gate_decision(decision)["valid"] is True


def test_validate_decision_rejects_publish_allowed_now_true(monkeypatch):
    _patch_ready(monkeypatch)
    decision = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    decision["publish_allowed_now"] = True
    assert gate.validate_publish_confirmation_gate_decision(decision)["valid"] is False


def test_validate_decision_rejects_workflow_modified(monkeypatch):
    _patch_ready(monkeypatch)
    decision = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    decision["safety_summary"]["workflow_modified_this_round"] = True
    assert "workflow_modified_this_round" in gate.validate_publish_confirmation_gate_decision(decision)["errors"]


def test_validate_decision_rejects_runtime_write(monkeypatch):
    _patch_ready(monkeypatch)
    decision = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    decision["safety_summary"]["runtime_write"] = True
    assert "runtime_write" in gate.validate_publish_confirmation_gate_decision(decision)["errors"]


def test_validate_decision_rejects_audit_jsonl_write(monkeypatch):
    _patch_ready(monkeypatch)
    decision = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    decision["safety_summary"]["audit_jsonl_write"] = True
    assert "audit_jsonl_write" in gate.validate_publish_confirmation_gate_decision(decision)["errors"]


def test_validate_decision_rejects_auto_fix(monkeypatch):
    _patch_ready(monkeypatch)
    decision = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    decision["safety_summary"]["auto_fix_executed"] = True
    assert "auto_fix_executed" in gate.validate_publish_confirmation_gate_decision(decision)["errors"]


def test_generate_report_writes_only_tmp_path(tmp_path, monkeypatch):
    _patch_ready(monkeypatch)
    output = tmp_path / "R241-16O_PUBLISH_CONFIRMATION_GATE.json"
    result = gate.generate_publish_confirmation_gate_report(
        confirmation_phrase=gate.EXPECTED_CONFIRMATION_PHRASE,
        requested_option=gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION,
        output_path=str(output),
    )
    assert Path(result["output_path"]).exists()
    assert Path(result["report_path"]).exists()
    assert Path(result["output_path"]).parent == tmp_path


def test_no_git_commit(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["safety_summary"]["no_git_commit_executed"] is True


def test_no_git_push(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["safety_summary"]["no_git_push_executed"] is True


def test_no_gh_workflow_run(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["safety_summary"]["no_gh_workflow_run_executed"] is True


def test_no_workflow_modification(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["safety_summary"].get("workflow_modified_this_round") is not True


def test_no_audit_jsonl_write(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["safety_summary"].get("audit_jsonl_write") is not True


def test_no_runtime_action_queue_write(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["safety_summary"].get("runtime_write") is not True
    assert result["safety_summary"].get("action_queue_write") is not True


def test_no_secret_read(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["safety_summary"].get("secret_read") is not True


def test_no_auto_fix(monkeypatch):
    _patch_ready(monkeypatch)
    result = gate.evaluate_publish_confirmation_gate(gate.EXPECTED_CONFIRMATION_PHRASE, gate.PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION)
    assert result["safety_summary"].get("auto_fix_executed") is not True

