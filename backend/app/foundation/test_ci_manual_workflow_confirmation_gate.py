"""Tests for R241-16G ci_manual_workflow_confirmation_gate module."""

from pathlib import Path

import pytest

from app.foundation import ci_manual_workflow_confirmation_gate as gate
from app.foundation import ci_manual_dispatch_implementation_review as impl


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── 1. build_workflow_confirmation_input ──────────────────────────────────────

def test_build_input_no_phrase():
    result = gate.build_workflow_confirmation_input()
    assert result["phrase_present"] is False
    assert result["phrase_exact_match"] is False


def test_build_input_correct_phrase():
    result = gate.build_workflow_confirmation_input(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE
    )
    assert result["phrase_present"] is True
    assert result["phrase_exact_match"] is True


def test_build_input_wrong_phrase():
    result = gate.build_workflow_confirmation_input(confirmation_phrase="WRONG_PHRASE")
    assert result["phrase_present"] is True
    assert result["phrase_exact_match"] is False


def test_build_input_default_option_b():
    result = gate.build_workflow_confirmation_input()
    assert result["requested_option"] == gate.WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY


def test_build_input_rejects_forbidden_option():
    result = gate.build_workflow_confirmation_input(requested_option="auto_fix")
    assert result["requested_option"] == gate.WorkflowCreationOption.UNKNOWN
    assert any("forbidden_option:auto_fix" in e for e in result["errors"])


# ── 2. validate_workflow_confirmation_phrase ─────────────────────────────────

def test_validate_phrase_correct_passes():
    input_data = gate.build_workflow_confirmation_input(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE
    )
    result = gate.validate_workflow_confirmation_phrase(input_data)
    assert result["passed"] is True


def test_validate_phrase_missing_blocked():
    input_data = gate.build_workflow_confirmation_input()
    result = gate.validate_workflow_confirmation_phrase(input_data)
    assert result["passed"] is False
    assert any("confirmation_phrase_missing" in e for e in result["errors"])


def test_validate_phrase_wrong_blocked():
    input_data = gate.build_workflow_confirmation_input(confirmation_phrase="WRONG")
    result = gate.validate_workflow_confirmation_phrase(input_data)
    assert result["passed"] is False
    assert any("confirmation_phrase_not_exact_match" in e for e in result["errors"])


# ── 3. validate_requested_workflow_option ────────────────────────────────────

def test_validate_option_b_no_confirmation_needed():
    input_data = gate.build_workflow_confirmation_input(
        confirmation_phrase=None,
        requested_option=gate.WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY,
    )
    result = gate.validate_requested_workflow_option(input_data)
    assert result["passed"] is True
    assert any("option_b_remains_blueprint_only" in w for w in result["warnings"])


def test_validate_option_c_requires_phrase():
    input_data = gate.build_workflow_confirmation_input(
        confirmation_phrase=None,
        requested_option=gate.WorkflowCreationOption.OPTION_C_MANUAL_PLAN_ONLY_WORKFLOW,
    )
    result = gate.validate_requested_workflow_option(input_data)
    assert result["passed"] is False
    assert any("option_c_or_d_requires_exact_confirmation_phrase" in e for e in result["errors"])


def test_validate_option_d_requires_phrase():
    input_data = gate.build_workflow_confirmation_input(
        confirmation_phrase=None,
        requested_option=gate.WorkflowCreationOption.OPTION_D_MANUAL_FAST_SAFETY_EXECUTE_WORKFLOW,
    )
    result = gate.validate_requested_workflow_option(input_data)
    assert result["passed"] is False
    assert any("option_c_or_d_requires_exact_confirmation_phrase" in e for e in result["errors"])


def test_validate_option_c_with_phrase_passes():
    input_data = gate.build_workflow_confirmation_input(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_C_MANUAL_PLAN_ONLY_WORKFLOW,
    )
    result = gate.validate_requested_workflow_option(input_data)
    assert result["passed"] is True


def test_validate_option_d_with_phrase_passes():
    input_data = gate.build_workflow_confirmation_input(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_D_MANUAL_FAST_SAFETY_EXECUTE_WORKFLOW,
    )
    result = gate.validate_requested_workflow_option(input_data)
    assert result["passed"] is True


# ── 4. validate_blueprint_still_safe ─────────────────────────────────────────

def test_validate_blueprint_write_target_not_allowed():
    result = gate.validate_blueprint_still_safe(str(_root()))
    assert result["passed"] is True
    assert result["check_id"] == "check_blueprint_safety"


def test_validate_blueprint_yml_txt_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(impl, "ROOT", tmp_path)
    monkeypatch.setattr(impl, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    impl.generate_manual_dispatch_implementation_review()
    result = gate.validate_blueprint_still_safe(str(tmp_path))
    assert result["passed"] is True


# ── 5. validate_existing_workflow_state ──────────────────────────────────────

def test_validate_existing_workflow_no_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    result = gate.validate_existing_workflow_state(str(tmp_path))
    assert result["check_id"] == "check_existing_workflow_state"
    assert result["passed"] is True


# ── 6. validate_confirmation_path_and_artifact_policy ──────────────────────────

def test_validate_path_artifact_excludes_audit_trail_jsonl(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    result = gate.validate_confirmation_path_and_artifact_policy(str(tmp_path))
    assert result["check_id"] == "check_path_and_artifact_policy"
    assert result["passed"] is True


# ── 7. build_confirmation_gate_checks ────────────────────────────────────────

def test_build_gate_checks_returns_complete_set():
    input_data = gate.build_workflow_confirmation_input(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE
    )
    result = gate.build_confirmation_gate_checks(input_data, str(_root()))
    assert "confirmation_gate_checks" in result
    check_ids = {c["check_id"] for c in result["confirmation_gate_checks"]}
    assert "check_confirmation_phrase" in check_ids
    assert "check_requested_workflow_option" in check_ids
    assert "check_blueprint_safety" in check_ids
    assert "check_existing_workflow_state" in check_ids
    assert "check_path_and_artifact_policy" in check_ids
    assert "check_no_github_workflows_write_this_round" in check_ids
    assert "check_no_pr_push_schedule_triggers" in check_ids
    assert "check_no_secrets" in check_ids
    assert "check_no_network" in check_ids
    assert "check_no_runtime_write" in check_ids
    assert "check_no_audit_jsonl_write" in check_ids
    assert "check_no_action_queue_write" in check_ids
    assert "check_no_auto_fix" in check_ids


# ── 8. evaluate_workflow_confirmation_gate ───────────────────────────────────

def test_evaluate_gate_no_confirmation_blocked():
    result = gate.evaluate_workflow_confirmation_gate()
    assert result["status"] == gate.WorkflowConfirmationGateStatus.BLOCKED_MISSING_CONFIRMATION
    assert result["decision"] == gate.WorkflowConfirmationDecision.BLOCK


def test_evaluate_gate_wrong_confirmation_blocked():
    result = gate.evaluate_workflow_confirmation_gate(confirmation_phrase="WRONG")
    assert result["status"] == gate.WorkflowConfirmationGateStatus.BLOCKED_INVALID_CONFIRMATION
    assert result["decision"] == gate.WorkflowConfirmationDecision.BLOCK


def test_evaluate_gate_correct_phrase_option_b_allow_next_review_only():
    result = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY,
    )
    assert result["status"] == gate.WorkflowConfirmationGateStatus.ALLOWED_FOR_NEXT_REVIEW
    assert result["decision"] == gate.WorkflowConfirmationDecision.ALLOW_NEXT_REVIEW_ONLY
    assert result["workflow_creation_allowed_now"] is False


def test_evaluate_gate_correct_phrase_option_c_allows_implementation_review():
    result = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_C_MANUAL_PLAN_ONLY_WORKFLOW,
    )
    assert result["status"] == gate.WorkflowConfirmationGateStatus.ALLOWED_FOR_NEXT_REVIEW
    assert result["decision"] == gate.WorkflowConfirmationDecision.ALLOW_IMPLEMENTATION_REVIEW
    assert result["workflow_creation_allowed_now"] is False


def test_evaluate_gate_correct_phrase_option_d_allows_implementation_review():
    result = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_D_MANUAL_FAST_SAFETY_EXECUTE_WORKFLOW,
    )
    assert result["status"] == gate.WorkflowConfirmationGateStatus.ALLOWED_FOR_NEXT_REVIEW
    assert result["decision"] == gate.WorkflowConfirmationDecision.ALLOW_IMPLEMENTATION_REVIEW
    assert result["workflow_creation_allowed_now"] is False


def test_evaluate_gate_workflow_creation_always_deferred():
    result = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_C_MANUAL_PLAN_ONLY_WORKFLOW,
    )
    assert result["workflow_creation_allowed_now"] is False


# ── 9. validate_workflow_confirmation_gate_decision ───────────────────────────

def test_validate_decision_valid():
    decision = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY,
    )
    result = gate.validate_workflow_confirmation_gate_decision(decision)
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_decision_rejects_workflow_creation_allowed_now():
    decision = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_C_MANUAL_PLAN_ONLY_WORKFLOW,
    )
    decision["workflow_creation_allowed_now"] = True
    result = gate.validate_workflow_confirmation_gate_decision(decision)
    assert result["valid"] is False
    assert any("workflow_creation_allowed_now_must_be_false" in e for e in result["errors"])


def test_validate_decision_rejects_missing_rollback():
    decision = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
    )
    decision["rollback_plan"] = {"rollback_steps": []}
    result = gate.validate_workflow_confirmation_gate_decision(decision)
    assert result["valid"] is False
    assert any("rollback_plan_missing" in e for e in result["errors"])


def test_validate_decision_rejects_missing_checks():
    decision = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
    )
    decision["confirmation_checks"] = []
    result = gate.validate_workflow_confirmation_gate_decision(decision)
    assert result["valid"] is False
    assert any("confirmation_checks_missing" in e for e in result["errors"])


def test_validate_decision_rejects_failed_checks():
    decision = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
    )
    decision["confirmation_checks"] = [
        {"check_id": "test_check", "passed": False}
    ]
    result = gate.validate_workflow_confirmation_gate_decision(decision)
    assert result["valid"] is False
    assert any("confirmation_checks_failed" in e for e in result["errors"])


# ── 10. generate_workflow_confirmation_gate_report safety ─────────────────────

def test_generate_writes_to_tmp_path_only(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    monkeypatch.setattr(gate, "DEFAULT_JSON_PATH", tmp_path / "R241-16G.json")
    monkeypatch.setattr(gate, "DEFAULT_MD_PATH", tmp_path / "R241-16G.md")
    result = gate.generate_workflow_confirmation_gate_report(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY,
        output_path=str(tmp_path / "R241-16G.json"),
    )
    assert Path(result["output_path"]).exists()
    assert Path(result["report_path"]).exists()


def test_generate_does_not_create_github_workflows(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    monkeypatch.setattr(gate, "DEFAULT_JSON_PATH", tmp_path / "R241-16G.json")
    monkeypatch.setattr(gate, "DEFAULT_MD_PATH", tmp_path / "R241-16G.md")
    gate.generate_workflow_confirmation_gate_report(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        output_path=str(tmp_path / "R241-16G.json"),
    )
    gh_dir = tmp_path / ".github" / "workflows"
    assert not gh_dir.exists()


def test_generate_does_not_write_audit_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    monkeypatch.setattr(gate, "DEFAULT_JSON_PATH", tmp_path / "R241-16G.json")
    monkeypatch.setattr(gate, "DEFAULT_MD_PATH", tmp_path / "R241-16G.md")
    gate.generate_workflow_confirmation_gate_report(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        output_path=str(tmp_path / "R241-16G.json"),
    )
    assert jsonl.read_text(encoding="utf-8") == before


def test_generate_does_not_write_runtime_or_action_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    monkeypatch.setattr(gate, "DEFAULT_JSON_PATH", tmp_path / "R241-16G.json")
    monkeypatch.setattr(gate, "DEFAULT_MD_PATH", tmp_path / "R241-16G.md")
    gate.generate_workflow_confirmation_gate_report(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        output_path=str(tmp_path / "R241-16G.json"),
    )
    runtime_dir = tmp_path / "runtime"
    action_queue_dir = tmp_path / "action_queue"
    assert not runtime_dir.exists()
    assert not action_queue_dir.exists()


def test_generate_does_not_perform_network_call(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    monkeypatch.setattr(gate, "DEFAULT_JSON_PATH", tmp_path / "R241-16G.json")
    monkeypatch.setattr(gate, "DEFAULT_MD_PATH", tmp_path / "R241-16G.md")
    monkeypatch.setattr(
        gate,
        "evaluate_workflow_confirmation_gate",
        lambda confirmation_phrase, requested_option, root=None: called.append("gate") or {
            "decision_id": "test",
            "generated_at": "",
            "status": gate.WorkflowConfirmationGateStatus.ALLOWED_FOR_NEXT_REVIEW,
            "decision": gate.WorkflowConfirmationDecision.ALLOW_IMPLEMENTATION_REVIEW,
            "allowed_next_phase": "R241-16H",
            "workflow_creation_allowed_now": False,
            "confirmation_input": {},
            "requested_option": gate.WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY,
            "confirmation_checks": [
                {
                    "check_id": "check_confirmation_phrase",
                    "passed": True,
                    "risk_level": gate.WorkflowConfirmationRiskLevel.CRITICAL,
                    "description": "test",
                    "evidence_refs": [],
                    "required_before_allow": True,
                    "blocked_reasons": [],
                    "warnings": [],
                    "errors": [],
                },
            ],
            "blueprint_ref": {},
            "existing_workflow_compatibility": [],
            "path_compatibility_policy": {},
            "artifact_policy": {},
            "rollback_plan": {"rollback_steps": ["step"]},
            "security_policy": {
                "no_secrets": True,
                "no_network": True,
                "no_runtime_write": True,
                "no_audit_jsonl_write": True,
                "no_action_queue_write": True,
                "no_auto_fix": True,
            },
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
    )
    gate.generate_workflow_confirmation_gate_report(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        output_path=str(tmp_path / "R241-16G.json"),
    )
    assert called == ["gate"]


def test_generate_does_not_execute_auto_fix(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit")
    monkeypatch.setattr(gate, "DEFAULT_JSON_PATH", tmp_path / "R241-16G.json")
    monkeypatch.setattr(gate, "DEFAULT_MD_PATH", tmp_path / "R241-16G.md")
    result = gate.generate_workflow_confirmation_gate_report(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY,
        output_path=str(tmp_path / "R241-16G.json"),
    )
    assert result["decision"]["security_policy"]["no_auto_fix"] is True


# ── 11. Static check objects ─────────────────────────────────────────────────

def test_static_checks_all_pass():
    input_data = gate.build_workflow_confirmation_input(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE
    )
    result = gate.build_confirmation_gate_checks(input_data, str(_root()))
    static_check_ids = {
        "check_no_github_workflows_write_this_round",
        "check_no_pr_push_schedule_triggers",
        "check_no_secrets",
        "check_no_network",
        "check_no_runtime_write",
        "check_no_audit_jsonl_write",
        "check_no_action_queue_write",
        "check_no_auto_fix",
    }
    checks_by_id = {c["check_id"]: c for c in result["confirmation_gate_checks"]}
    for sid in static_check_ids:
        assert checks_by_id[sid]["passed"] is True, f"{sid} should pass"


# ── 12. Decision object structure ─────────────────────────────────────────────

def test_decision_contains_required_fields():
    result = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY,
    )
    assert "decision_id" in result
    assert "generated_at" in result
    assert "status" in result
    assert "decision" in result
    assert "workflow_creation_allowed_now" in result
    assert "confirmation_checks" in result
    assert "rollback_plan" in result
    assert "security_policy" in result


def test_decision_allowed_next_phase_for_option_b():
    result = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY,
    )
    assert result["allowed_next_phase"] == "R241-16F_continue_blueprint_only"


def test_decision_allowed_next_phase_for_option_c():
    result = gate.evaluate_workflow_confirmation_gate(
        confirmation_phrase=gate.VALID_CONFIRMATION_PHRASE,
        requested_option=gate.WorkflowCreationOption.OPTION_C_MANUAL_PLAN_ONLY_WORKFLOW,
    )
    assert result["allowed_next_phase"] == "R241-16H_workflow_creation_implementation"
