"""Tests for R241-16H ci_manual_workflow_creation module."""

from pathlib import Path

import pytest

from app.foundation import ci_manual_workflow_creation as creation
from app.foundation import ci_manual_dispatch_implementation_review as impl


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── 1. load_manual_workflow_blueprint_for_creation ─────────────────────────────

def test_load_blueprint_returns_text():
    result = creation.load_manual_workflow_blueprint_for_creation(str(_root()))
    assert result["blueprint_text"] is not None
    assert "workflow_dispatch" in result["blueprint_text"]


def test_load_blueprint_contains_workflow_dispatch():
    result = creation.load_manual_workflow_blueprint_for_creation(str(_root()))
    assert "workflow_dispatch:" in result["blueprint_text"]


def test_load_blueprint_no_pr_trigger():
    result = creation.load_manual_workflow_blueprint_for_creation(str(_root()))
    assert "pull_request:" not in result["blueprint_text"]


def test_load_blueprint_no_push_trigger():
    result = creation.load_manual_workflow_blueprint_for_creation(str(_root()))
    assert "push:" not in result["blueprint_text"]


def test_load_blueprint_no_schedule_trigger():
    result = creation.load_manual_workflow_blueprint_for_creation(str(_root()))
    assert "schedule:" not in result["blueprint_text"]


def test_load_blueprint_no_secrets():
    result = creation.load_manual_workflow_blueprint_for_creation(str(_root()))
    assert "secrets." not in result["blueprint_text"]


# ── 2. run_manual_workflow_creation_prechecks ───────────────────────────────

def test_prechecks_fail_without_phrase():
    result = creation.run_manual_workflow_creation_prechecks(str(_root()))
    assert result["all_passed"] is False


def test_prechecks_pass_with_valid_phrase_and_option_c(tmp_path, monkeypatch):
    # Monkeypatch TARGET_WORKFLOW_PATH so the "already exists" check passes
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    result = creation.run_manual_workflow_creation_prechecks(
        str(tmp_path),
        confirmation_phrase="CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
        requested_option="option_c_manual_plan_only_workflow",
    )
    assert result["all_passed"] is True


def test_prechecks_fail_with_wrong_option():
    result = creation.run_manual_workflow_creation_prechecks(
        str(_root()),
        confirmation_phrase="CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
        requested_option="option_b_blueprint_only",
    )
    assert result["all_passed"] is False


def test_prechecks_fail_with_wrong_phrase():
    result = creation.run_manual_workflow_creation_prechecks(
        str(_root()),
        confirmation_phrase="WRONG",
        requested_option="option_c_manual_plan_only_workflow",
    )
    assert result["all_passed"] is False


def test_prechecks_includes_all_required_checks():
    result = creation.run_manual_workflow_creation_prechecks(str(_root()))
    check_ids = {c["check_id"] for c in result["prechecks"]}
    assert "check_confirmation_phrase" in check_ids
    assert "check_requested_option" in check_ids
    assert "check_blueprint_exists" in check_ids
    assert "check_target_not_exists" in check_ids
    assert "check_existing_workflows_unchanged" in check_ids
    assert "check_rollback_plan_exists" in check_ids


# ── 3. create_manual_dispatch_workflow_file ───────────────────────────────

def test_create_allow_false_does_not_write(tmp_path, monkeypatch):
    # Use tmp_path as root so the derived target path (under tmp_path) won't exist
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    result = creation.create_manual_dispatch_workflow_file(str(tmp_path), allow_create=False)
    assert result["file_written"] is False
    assert result["passed"] is True


def test_create_writes_only_target_file(tmp_path, monkeypatch):
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    result = creation.create_manual_dispatch_workflow_file(str(tmp_path), allow_create=True)
    assert result["file_written"] is True
    assert result["workflow_created"] is True
    assert result["workflow_path"].endswith("foundation-manual-dispatch.yml")


def test_create_refuses_overwrite(tmp_path, monkeypatch):
    target = tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("existing content", encoding="utf-8")
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", target)
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    result = creation.create_manual_dispatch_workflow_file(str(tmp_path), allow_create=True)
    assert result["workflow_created"] is False
    assert result["workflow_overwritten"] is False


# ── 4. validate_created_manual_workflow ──────────────────────────────────

def test_validate_rejects_pr_trigger(tmp_path, monkeypatch):
    target = tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("name: Test\non:\n  pull_request:\n  workflow_dispatch:\n", encoding="utf-8")
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", target)
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    result = creation.validate_created_manual_workflow(str(tmp_path))
    assert result["valid"] is False
    assert any("pull_request_trigger_found" in e for e in result["errors"])


def test_validate_rejects_secrets(tmp_path, monkeypatch):
    target = tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("name: Test\non:\n  workflow_dispatch:\n  secrets:\n", encoding="utf-8")
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", target)
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    result = creation.validate_created_manual_workflow(str(tmp_path))
    assert result["valid"] is False
    assert any("secrets_reference_found" in e for e in result["errors"])


def test_validate_rejects_webhook_curl(tmp_path, monkeypatch):
    target = tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("name: Test\non:\n  workflow_dispatch:\nsteps:\n  - curl https://example.com", encoding="utf-8")
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", target)
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    result = creation.validate_created_manual_workflow(str(tmp_path))
    assert result["valid"] is False
    assert any("curl_found" in e or "webhook_found" in e for e in result["errors"])


def test_validate_accepts_correct_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    # Create the workflow file using the creation module
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    creation.create_manual_dispatch_workflow_file(str(tmp_path), allow_create=True)
    result = creation.validate_created_manual_workflow(str(tmp_path))
    assert result["valid"] is True
    assert result["workflow_exists"] is True
    assert result["workflow_dispatch_enabled"] is True
    assert result["pull_request_enabled"] is False
    assert result["push_enabled"] is False
    assert result["schedule_enabled"] is False


def test_validate_plan_only_default(tmp_path, monkeypatch):
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    creation.create_manual_dispatch_workflow_file(str(tmp_path), allow_create=True)
    result = creation.validate_created_manual_workflow(str(tmp_path))
    assert result["plan_only_default_set"] is True
    assert result["confirm_phrase_present"] is True


# ── 5. execute_manual_workflow_creation ──────────────────────────────────

def test_execute_invalid_phrase_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    result = creation.execute_manual_workflow_creation(
        str(tmp_path),
        confirmation_phrase="WRONG",
        requested_option="option_c_manual_plan_only_workflow",
    )
    assert result["workflow_created"] is False
    assert result["status"] == creation.ManualWorkflowCreationStatus.BLOCKED_PRECHECK_FAILED


def test_execute_valid_phrase_creates_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    result = creation.execute_manual_workflow_creation(
        str(tmp_path),
        confirmation_phrase="CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
        requested_option="option_c_manual_plan_only_workflow",
    )
    assert result["workflow_created"] is True
    assert result["status"] == creation.ManualWorkflowCreationStatus.CREATED


def test_execute_does_not_modify_existing_workflows(tmp_path, monkeypatch):
    gh = tmp_path / ".github" / "workflows"
    gh.mkdir(parents=True, exist_ok=True)
    (gh / "backend-unit-tests.yml").write_text("name: Backend Tests", encoding="utf-8")
    (gh / "lint-check.yml").write_text("name: Lint", encoding="utf-8")
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    result = creation.execute_manual_workflow_creation(
        str(tmp_path),
        confirmation_phrase="CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
        requested_option="option_c_manual_plan_only_workflow",
    )
    assert result["existing_workflows_modified"] is False
    assert (gh / "backend-unit-tests.yml").read_text(encoding="utf-8") == "name: Backend Tests"
    assert (gh / "lint-check.yml").read_text(encoding="utf-8") == "name: Lint"


# ── 6. rollback_manual_workflow_creation ───────────────────────────────────

def test_rollback_deletes_only_created_workflow(tmp_path, monkeypatch):
    target = tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("name: Test Workflow", encoding="utf-8")
    gh = tmp_path / ".github" / "workflows"
    (gh / "backend-unit-tests.yml").write_text("name: Backend Tests", encoding="utf-8")
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", target)
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    result = creation.rollback_manual_workflow_creation(str(tmp_path), reason="test")
    assert result["workflow_deleted"] is True
    assert not target.exists()
    assert (gh / "backend-unit-tests.yml").exists()


# ── 7. Report generation safety ─────────────────────────────────────────────

def test_generate_writes_only_tmp_path(tmp_path, monkeypatch):
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    monkeypatch.setattr(creation, "DEFAULT_JSON_PATH", tmp_path / "R241-16H.json")
    monkeypatch.setattr(creation, "DEFAULT_MD_PATH", tmp_path / "R241-16H.md")
    result = creation.execute_manual_workflow_creation(
        str(tmp_path),
        confirmation_phrase="CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
        requested_option="option_c_manual_plan_only_workflow",
    )
    report = creation.generate_manual_workflow_creation_report(result, str(tmp_path / "R241-16H.json"))
    assert Path(report["output_path"]).exists()
    assert Path(report["report_path"]).exists()


def test_generate_does_not_write_audit_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    monkeypatch.setattr(creation, "DEFAULT_JSON_PATH", tmp_path / "R241-16H.json")
    monkeypatch.setattr(creation, "DEFAULT_MD_PATH", tmp_path / "R241-16H.md")
    result = creation.execute_manual_workflow_creation(
        str(tmp_path),
        confirmation_phrase="CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
        requested_option="option_c_manual_plan_only_workflow",
    )
    creation.generate_manual_workflow_creation_report(result, str(tmp_path / "R241-16H.json"))
    assert jsonl.read_text(encoding="utf-8") == before


def test_generate_does_not_write_runtime_or_action_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    monkeypatch.setattr(creation, "DEFAULT_JSON_PATH", tmp_path / "R241-16H.json")
    monkeypatch.setattr(creation, "DEFAULT_MD_PATH", tmp_path / "R241-16H.md")
    result = creation.execute_manual_workflow_creation(
        str(tmp_path),
        confirmation_phrase="CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
        requested_option="option_c_manual_plan_only_workflow",
    )
    creation.generate_manual_workflow_creation_report(result, str(tmp_path / "R241-16H.json"))
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "action_queue").exists()


def test_generate_does_not_perform_network_call(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    monkeypatch.setattr(creation, "DEFAULT_JSON_PATH", tmp_path / "R241-16H.json")
    monkeypatch.setattr(creation, "DEFAULT_MD_PATH", tmp_path / "R241-16H.md")
    monkeypatch.setattr(creation, "execute_manual_workflow_creation", lambda root, **kw: called.append("exec") or {
        "result_id": "R241-16H_workflow_creation_result",
        "generated_at": "",
        "status": creation.ManualWorkflowCreationStatus.CREATED,
        "decision": creation.ManualWorkflowCreationDecision.CREATE_MANUAL_WORKFLOW,
        "workflow_path": str(tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml"),
        "workflow_created": True,
        "workflow_overwritten": False,
        "existing_workflows_modified": False,
        "trigger_summary": {"pull_request": False, "push": False, "schedule": False, "workflow_dispatch": True},
        "security_summary": {"no_secrets": True, "no_network": True, "no_runtime_write": True, "no_audit_jsonl_write": True, "no_action_queue_write": True, "no_auto_fix": True},
        "prechecks": {"all_passed": True, "prechecks": [], "warnings": [], "errors": []},
        "validation_checks": [{"valid": True}],
        "local_validation": {},
        "rollback_result": None,
        "warnings": [],
        "errors": [],
    })
    creation.generate_manual_workflow_creation_report({"result_id": "test"}, str(tmp_path / "R241-16H.json"))
    assert called == []


def test_generate_does_not_execute_auto_fix(tmp_path, monkeypatch):
    monkeypatch.setattr(creation, "ROOT", tmp_path)
    monkeypatch.setattr(creation, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(creation, "BLUEPRINT_PATH", _root() / "migration_reports" / "foundation_audit" / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt")
    monkeypatch.setattr(creation, "DEFAULT_JSON_PATH", tmp_path / "R241-16H.json")
    monkeypatch.setattr(creation, "DEFAULT_MD_PATH", tmp_path / "R241-16H.md")
    result = creation.execute_manual_workflow_creation(
        str(tmp_path),
        confirmation_phrase="CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
        requested_option="option_c_manual_plan_only_workflow",
    )
    creation.generate_manual_workflow_creation_report(result, str(tmp_path / "R241-16H.json"))
    assert result["security_summary"]["no_auto_fix"] is True
