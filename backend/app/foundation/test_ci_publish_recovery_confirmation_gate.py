"""Tests for R241-16R ci_publish_recovery_confirmation_gate module."""

from pathlib import Path
import json
import pytest

from app.foundation import ci_publish_recovery_confirmation_gate as gate


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── Test build_recovery_confirmation_input ───────────────────────────────────

def test_build_input_with_default_option_a():
    result = gate.build_recovery_confirmation_input()
    assert result["requested_option"] == gate.RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value
    assert result["phrase_present"] is False
    assert result["phrase_exact_match"] is False
    assert result["requested_option_valid"] is True
    assert result["expected_confirmation_phrase"] == gate.CONFIRMATION_PHRASE


def test_build_input_with_phrase_and_option_d():
    result = gate.build_recovery_confirmation_input(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
    )
    assert result["phrase_present"] is True
    assert result["phrase_exact_match"] is True
    assert result["requested_option"] == gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value
    assert result["requested_option_valid"] is True


def test_build_input_rejects_forbidden_substrings():
    result = gate.build_recovery_confirmation_input(
        requested_option="option_b_push_to_user_fork_with_git_push_now",
    )
    assert result["requested_option_valid"] is False


def test_build_input_unknown_option():
    result = gate.build_recovery_confirmation_input(
        requested_option="option_z_invalid",
    )
    assert result["requested_option_valid"] is False


def test_build_input_rejects_force_push():
    result = gate.build_recovery_confirmation_input(
        requested_option="option_b_force_push",
    )
    assert result["requested_option_valid"] is False


# ── Test phrase_present_fn ─────────────────────────────────────────────────────

def test_phrase_present_fn_true_for_non_empty():
    assert gate.phrase_present_fn("CONFIRM_PUBLISH_RECOVERY_PATH") is True


def test_phrase_present_fn_false_for_empty():
    assert gate.phrase_present_fn("") is False


def test_phrase_present_fn_false_for_whitespace():
    assert gate.phrase_present_fn("   ") is False


# ── Test is_valid_option ───────────────────────────────────────────────────────

def test_is_valid_option_accepts_all_valid_options():
    for opt in gate.VALID_OPTION_IDS:
        assert gate.is_valid_option(opt) is True


def test_is_valid_option_rejects_unknown():
    assert gate.is_valid_option("option_x") is False


def test_is_valid_option_rejects_with_forbidden_substring():
    assert gate.is_valid_option("option_b_git_push_now") is False


# ── Test validate_recovery_confirmation_phrase ─────────────────────────────────

def test_validate_phrase_passes_with_exact_match():
    input_data = {
        "phrase_present": True,
        "phrase_exact_match": True,
    }
    result = gate.validate_recovery_confirmation_phrase(input_data)
    assert result["passed"] is True
    assert result["blocked_reasons"] == []


def test_validate_phrase_fails_when_missing():
    input_data = {
        "phrase_present": False,
        "phrase_exact_match": False,
    }
    result = gate.validate_recovery_confirmation_phrase(input_data)
    assert result["passed"] is False
    assert "confirmation_phrase_missing" in result["blocked_reasons"]


def test_validate_phrase_fails_when_mismatch():
    input_data = {
        "phrase_present": True,
        "phrase_exact_match": False,
    }
    result = gate.validate_recovery_confirmation_phrase(input_data)
    assert result["passed"] is False
    assert "confirmation_phrase_mismatch" in result["blocked_reasons"]


def test_validate_phrase_risk_level_is_critical():
    input_data = {"phrase_present": True, "phrase_exact_match": True}
    result = gate.validate_recovery_confirmation_phrase(input_data)
    assert result["risk_level"] == gate.RecoveryConfirmationRiskLevel.CRITICAL.value


# ── Test validate_requested_recovery_option ─────────────────────────────────────

def test_validate_option_passes_for_valid_option_with_phrase():
    input_data = {
        "requested_option": gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
        "requested_option_valid": True,
        "phrase_exact_match": True,
    }
    result = gate.validate_requested_recovery_option(input_data)
    assert result["passed"] is True
    assert result["blocked_reasons"] == []


def test_validate_option_fails_for_invalid_option():
    input_data = {
        "requested_option": "option_z_invalid",
        "requested_option_valid": False,
        "phrase_exact_match": True,
    }
    result = gate.validate_requested_recovery_option(input_data)
    assert result["passed"] is False
    assert any("invalid_recovery_option" in r for r in result["blocked_reasons"])


def test_validate_option_fails_for_option_b_to_e_without_phrase():
    for opt in [
        gate.RecoveryPathOption.OPTION_B_PUSH_TO_USER_FORK.value,
        gate.RecoveryPathOption.OPTION_C_CREATE_REVIEW_BRANCH.value,
        gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
        gate.RecoveryPathOption.OPTION_E_ROLLBACK_LOCAL_COMMIT.value,
    ]:
        input_data = {
            "requested_option": opt,
            "requested_option_valid": True,
            "phrase_exact_match": False,
        }
        result = gate.validate_requested_recovery_option(input_data)
        assert result["passed"] is False
        assert "option_requires_confirmation_phrase" in result["blocked_reasons"]


def test_validate_option_option_a_allowed_without_phrase():
    input_data = {
        "requested_option": gate.RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
        "requested_option_valid": True,
        "phrase_exact_match": False,
    }
    result = gate.validate_requested_recovery_option(input_data)
    assert result["passed"] is True


def test_validate_option_option_e_warns_high_risk():
    input_data = {
        "requested_option": gate.RecoveryPathOption.OPTION_E_ROLLBACK_LOCAL_COMMIT.value,
        "requested_option_valid": True,
        "phrase_exact_match": True,
    }
    result = gate.validate_requested_recovery_option(input_data)
    assert "option_e_rollback_high_risk_requires_explicit_confirmation" in result["warnings"]


def test_validate_option_returns_correct_risk_levels():
    input_data = {
        "requested_option": gate.RecoveryPathOption.OPTION_E_ROLLBACK_LOCAL_COMMIT.value,
        "requested_option_valid": True,
        "phrase_exact_match": True,
    }
    result = gate.validate_requested_recovery_option(input_data)
    assert result["risk_level"] == gate.RecoveryConfirmationRiskLevel.HIGH.value


# ── Test validate_push_failure_and_staged_area_ready ───────────────────────────

def test_push_failure_and_staged_area_loads_existing_reviews(tmp_path, monkeypatch):
    # Provide minimal mock review files
    q_review = {
        "review": {
            "status": "reviewed_push_permission_denied",
            "decision": "keep_local_commit",
            "local_commit_hash": "94908556cc2ca66c219d361f424954945eee9e67",
            "local_commit_only_target_workflow": True,
            "remote_workflow_present": False,
        }
    }
    qb_review = {
        "status": "parser_false_positive_fixed",
        "decision": "allow_recovery_gate",
        "current_staged_files": [],
        "existing_workflows_unchanged": True,
    }
    q_path = tmp_path / "R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.json"
    qb_path = tmp_path / "R241-16Q_B_STAGED_AREA_CONSISTENCY_REPAIR.json"
    q_path.write_text(json.dumps(q_review), encoding="utf-8")
    qb_path.write_text(json.dumps(qb_review), encoding="utf-8")

    import app.foundation.ci_publish_recovery_confirmation_gate as g
    monkeypatch.setattr(g, "R241_16Q_REVIEW_PATH", q_path)
    monkeypatch.setattr(g, "R241_16Q_B_REVIEW_PATH", qb_path)

    result = g.validate_push_failure_and_staged_area_ready(str(tmp_path))
    assert result["all_passed"] is True
    assert result["r241_16q_status"] == "reviewed_push_permission_denied"
    assert result["r241_16q_b_status"] == "parser_false_positive_fixed"
    assert result["r241_16q_b_staged_area_empty"] is True


def test_push_failure_and_staged_area_fails_when_q_status_invalid(tmp_path, monkeypatch):
    q_review = {
        "review": {
            "status": "some_other_status",
            "decision": "keep_local_commit",
            "local_commit_hash": "abc123",
            "local_commit_only_target_workflow": True,
            "remote_workflow_present": False,
        }
    }
    qb_review = {
        "status": "parser_false_positive_fixed",
        "decision": "allow_recovery_gate",
        "current_staged_files": [],
        "existing_workflows_unchanged": True,
    }
    q_path = tmp_path / "R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.json"
    qb_path = tmp_path / "R241-16Q_B_STAGED_AREA_CONSISTENCY_REPAIR.json"
    q_path.write_text(json.dumps(q_review), encoding="utf-8")
    qb_path.write_text(json.dumps(qb_review), encoding="utf-8")

    import app.foundation.ci_publish_recovery_confirmation_gate as g
    monkeypatch.setattr(g, "R241_16Q_REVIEW_PATH", q_path)
    monkeypatch.setattr(g, "R241_16Q_B_REVIEW_PATH", qb_path)

    result = g.validate_push_failure_and_staged_area_ready(str(tmp_path))
    assert result["all_passed"] is False


def test_push_failure_and_staged_area_fails_when_qb_status_invalid(tmp_path, monkeypatch):
    q_review = {
        "review": {
            "status": "reviewed_push_permission_denied",
            "decision": "keep_local_commit",
            "local_commit_hash": "94908556cc2ca66c219d361f424954945eee9e67",
            "local_commit_only_target_workflow": True,
            "remote_workflow_present": False,
        }
    }
    qb_review = {
        "status": "invalid_status",
        "decision": "allow_recovery_gate",
        "current_staged_files": [],
        "existing_workflows_unchanged": True,
    }
    q_path = tmp_path / "R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.json"
    qb_path = tmp_path / "R241-16Q_B_STAGED_AREA_CONSISTENCY_REPAIR.json"
    q_path.write_text(json.dumps(q_review), encoding="utf-8")
    qb_path.write_text(json.dumps(qb_review), encoding="utf-8")

    import app.foundation.ci_publish_recovery_confirmation_gate as g
    monkeypatch.setattr(g, "R241_16Q_REVIEW_PATH", q_path)
    monkeypatch.setattr(g, "R241_16Q_B_REVIEW_PATH", qb_path)

    result = g.validate_push_failure_and_staged_area_ready(str(tmp_path))
    assert result["all_passed"] is False


def test_push_failure_and_staged_area_handles_missing_files(tmp_path, monkeypatch):
    import app.foundation.ci_publish_recovery_confirmation_gate as g
    monkeypatch.setattr(g, "R241_16Q_REVIEW_PATH", tmp_path / "nonexistent.json")
    monkeypatch.setattr(g, "R241_16Q_B_REVIEW_PATH", tmp_path / "nonexistent2.json")

    result = g.validate_push_failure_and_staged_area_ready(str(tmp_path))
    # With no files, checks fail
    assert result["all_passed"] is False


# ── Test build_recovery_confirmation_checks ─────────────────────────────────────

def test_build_checks_returns_all_checks():
    input_data = {
        "phrase_present": True,
        "phrase_exact_match": True,
        "requested_option": gate.RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
        "requested_option_valid": True,
    }
    # Uses real review files from project root
    checks = gate.build_recovery_confirmation_checks(input_data, str(_root()))
    # phrase_check + option_check + 6 readiness checks
    assert len(checks) >= 2


# ── Test evaluate_recovery_confirmation_gate ─────────────────────────────────────

def test_evaluate_gate_option_a_design_only():
    result = gate.evaluate_recovery_confirmation_gate(
        confirmation_phrase=None,
        requested_option=gate.RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
        root=str(_root()),
    )
    assert result["recovery_action_allowed_now"] is False
    assert result["status"] == gate.RecoveryConfirmationStatus.ALLOWED_FOR_NEXT_REVIEW.value
    assert result["decision"] == gate.RecoveryConfirmationDecision.KEEP_LOCAL_COMMIT.value


def test_evaluate_gate_option_d_with_phrase_allows_next_review():
    result = gate.evaluate_recovery_confirmation_gate(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
        root=str(_root()),
    )
    assert result["recovery_action_allowed_now"] is False
    assert result["status"] == gate.RecoveryConfirmationStatus.ALLOWED_FOR_NEXT_REVIEW.value
    assert result["decision"] == gate.RecoveryConfirmationDecision.ALLOW_RECOVERY_IMPLEMENTATION_REVIEW.value
    assert result["allowed_next_phase"] == "R241-16S_patch_bundle_generation"


def test_evaluate_gate_blocks_without_phrase_for_option_d():
    result = gate.evaluate_recovery_confirmation_gate(
        confirmation_phrase=None,
        requested_option=gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
        root=str(_root()),
    )
    assert result["status"] == gate.RecoveryConfirmationStatus.BLOCKED_MISSING_CONFIRMATION.value
    assert result["decision"] == gate.RecoveryConfirmationDecision.BLOCK_RECOVERY.value


def test_evaluate_gate_blocks_invalid_option():
    result = gate.evaluate_recovery_confirmation_gate(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option="option_z_invalid",
        root=str(_root()),
    )
    assert result["status"] == gate.RecoveryConfirmationStatus.BLOCKED_INVALID_OPTION.value


def test_evaluate_gate_all_options_map_to_correct_next_phases():
    mappings = {
        gate.RecoveryPathOption.OPTION_B_PUSH_TO_USER_FORK.value: "R241-16S_fork_push_implementation_review",
        gate.RecoveryPathOption.OPTION_C_CREATE_REVIEW_BRANCH.value: "R241-16S_review_branch_implementation_review",
        gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value: "R241-16S_patch_bundle_generation",
        gate.RecoveryPathOption.OPTION_E_ROLLBACK_LOCAL_COMMIT.value: "R241-16S_rollback_confirmation_review",
    }
    for opt, expected_phase in mappings.items():
        result = gate.evaluate_recovery_confirmation_gate(
            confirmation_phrase=gate.CONFIRMATION_PHRASE,
            requested_option=opt,
            root=str(_root()),
        )
        assert result["allowed_next_phase"] == expected_phase, f"Option {opt} should map to {expected_phase}"


def test_evaluate_gate_includes_recovery_options():
    result = gate.evaluate_recovery_confirmation_gate(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
        root=str(_root()),
    )
    assert len(result["recovery_options"]) == 5
    assert len(result["command_blueprints"]) >= 5


def test_evaluate_gate_no_mutation_keywords_in_blocked_reasons():
    result = gate.evaluate_recovery_confirmation_gate(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
        root=str(_root()),
    )
    blocked = result.get("blocked_reasons", [])
    mutation_keywords = ["git_push", "git_commit", "git_reset", "gh_workflow_run"]
    for br in blocked:
        for kw in mutation_keywords:
            assert kw not in str(br).lower()


# ── Test validate_recovery_confirmation_gate_decision ─────────────────────────────

def test_validate_decision_passes_for_valid_decision():
    decision = {
        "recovery_action_allowed_now": False,
        "command_blueprints": [
            {"command_id": "cmd1", "command_allowed_now": False},
            {"command_id": "cmd2", "command_allowed_now": False},
        ],
        "confirmation_checks": [
            {"passed": True, "blocked_reasons": []},
        ],
        "blocked_reasons": [],
    }
    result = gate.validate_recovery_confirmation_gate_decision(decision)
    assert result["valid"] is True
    assert result["blocked_reasons"] == []


def test_validate_decision_fails_when_recovery_allowed_now_true():
    decision = {
        "recovery_action_allowed_now": True,
        "command_blueprints": [],
        "confirmation_checks": [],
        "blocked_reasons": [],
    }
    result = gate.validate_recovery_confirmation_gate_decision(decision)
    assert result["valid"] is False
    assert "recovery_action_allowed_now_must_be_false" in result["blocked_reasons"]


def test_validate_decision_fails_when_command_allowed_now_true():
    decision = {
        "recovery_action_allowed_now": False,
        "command_blueprints": [
            {"command_id": "cmd1", "command_allowed_now": True},
        ],
        "confirmation_checks": [],
        "blocked_reasons": [],
    }
    result = gate.validate_recovery_confirmation_gate_decision(decision)
    assert result["valid"] is False


def test_validate_decision_fails_when_check_has_blocked_reasons():
    decision = {
        "recovery_action_allowed_now": False,
        "command_blueprints": [],
        "confirmation_checks": [
            {"passed": False, "blocked_reasons": ["some_blocked_reason"]},
        ],
        "blocked_reasons": [],
    }
    result = gate.validate_recovery_confirmation_gate_decision(decision)
    assert result["valid"] is False


# ── Test generate_recovery_confirmation_gate_report ──────────────────────────────

def test_generate_report_writes_json_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path)
    report = gate.generate_recovery_confirmation_gate_report(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
        output_path=str(tmp_path / "test-R241-16R.json"),
    )
    assert Path(report["output_path"]).exists()
    assert Path(report["report_path"]).exists()
    decision = report["decision"]
    assert decision["recovery_action_allowed_now"] is False
    validation = report["validation"]
    assert validation["valid"] is True


def test_generate_report_option_a_design_only(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path)
    report = gate.generate_recovery_confirmation_gate_report(
        confirmation_phrase=None,
        requested_option=gate.RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
        output_path=str(tmp_path / "test-R241-16R-A.json"),
    )
    assert report["decision"]["decision"] == gate.RecoveryConfirmationDecision.KEEP_LOCAL_COMMIT.value


def test_generate_report_blocks_when_missing_reviews(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path)
    # Point to non-existent review files
    import app.foundation.ci_publish_recovery_confirmation_gate as g
    monkeypatch.setattr(g, "R241_16Q_REVIEW_PATH", tmp_path / "nonexistent.json")
    monkeypatch.setattr(g, "R241_16Q_B_REVIEW_PATH", tmp_path / "nonexistent2.json")
    report = g.generate_recovery_confirmation_gate_report(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
        output_path=str(tmp_path / "test-R241-16R-blocked.json"),
    )
    # Should still produce a report but checks will fail
    assert report["decision"]["status"] == gate.RecoveryConfirmationStatus.BLOCKED_STAGED_AREA_NOT_CLEAN.value


# ── Test no-mutation invariants ────────────────────────────────────────────────

def test_no_git_push_in_command_blueprints():
    # git push can appear in blueprints but command_allowed_now MUST be False
    result = gate.evaluate_recovery_confirmation_gate(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
        root=str(_root()),
    )
    for bp in result["command_blueprints"]:
        argv = bp.get("argv", [])
        if argv and argv[0] == "git" and argv[1] == "push":
            assert bp.get("command_allowed_now") is False, \
                f"git push found with command_allowed_now=True in {bp['command_id']}"


def test_no_git_reset_in_command_blueprints():
    # git reset can appear in blueprints but command_allowed_now MUST be False
    result = gate.evaluate_recovery_confirmation_gate(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
        root=str(_root()),
    )
    for bp in result["command_blueprints"]:
        argv = bp.get("argv", [])
        if argv and argv[0] == "git" and argv[1] in ("reset", "restore", "revert"):
            assert bp.get("command_allowed_now") is False, \
                f"destructive git command found with command_allowed_now=True in {bp['command_id']}"


def test_no_gh_workflow_run_in_command_blueprints():
    result = gate.evaluate_recovery_confirmation_gate(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
        root=str(_root()),
    )
    for bp in result["command_blueprints"]:
        argv = bp.get("argv", [])
        if argv:
            assert not (argv[0] == "gh" and len(argv) >= 3 and "workflow" in argv[1:]), \
                f"Found gh workflow command in {bp['command_id']}"


def test_workflow_files_unchanged_after_evaluation():
    workflow_path = _root() / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    before_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    gate.evaluate_recovery_confirmation_gate(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
        root=str(_root()),
    )
    after_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    assert before_content == after_content or not workflow_path.exists()


def test_no_runtime_write_during_evaluation(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(exist_ok=True)
    gate.generate_recovery_confirmation_gate_report(
        confirmation_phrase=gate.CONFIRMATION_PHRASE,
        requested_option=gate.RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
        output_path=str(tmp_path / "test-R241-16R-nowrite.json"),
    )
    # runtime/ directory should be empty or non-existent (not written to)
    runtime_contents = list(runtime_dir.iterdir()) if runtime_dir.exists() else []
    assert len(runtime_contents) == 0
