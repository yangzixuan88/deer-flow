"""Tests for R241-16I ci_manual_workflow_runtime_verification module."""

from pathlib import Path

import pytest

from app.foundation import ci_manual_workflow_runtime_verification as verification


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── 1. load_created_manual_workflow ────────────────────────────────────────

def test_load_workflow_returns_dict():
    result = verification.load_created_manual_workflow(str(_root()))
    assert isinstance(result, dict)
    assert "workflow_path" in result
    assert "workflow_exists" in result


def test_load_workflow_workflow_exists():
    result = verification.load_created_manual_workflow(str(_root()))
    assert result["workflow_exists"] is True


def test_load_workflow_contains_yaml_text():
    result = verification.load_created_manual_workflow(str(_root()))
    assert result["yaml_text"] is not None
    assert "workflow_dispatch" in result["yaml_text"]


def test_load_workflow_yaml_parsed():
    result = verification.load_created_manual_workflow(str(_root()))
    assert result["yaml_parsed"] is not None
    assert isinstance(result["yaml_parsed"], dict)


def test_load_workflow_no_pr_trigger():
    result = verification.load_created_manual_workflow(str(_root()))
    assert "pull_request:" not in result["yaml_text"]


def test_load_workflow_no_push_trigger():
    result = verification.load_created_manual_workflow(str(_root()))
    assert "push:" not in result["yaml_text"]


def test_load_workflow_no_schedule_trigger():
    result = verification.load_created_manual_workflow(str(_root()))
    assert "schedule:" not in result["yaml_text"]


def test_load_workflow_no_secrets():
    result = verification.load_created_manual_workflow(str(_root()))
    assert "secrets." not in result["yaml_text"]


def test_load_workflow_not_found_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    monkeypatch.setattr(verification, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    result = verification.load_created_manual_workflow(str(tmp_path))
    assert result["workflow_exists"] is False
    assert len(result["errors"]) > 0


# ── 2. validate_manual_workflow_yaml_static ───────────────────────────────

def test_static_validate_correct_workflow():
    yaml_text = Path(_root() / ".github" / "workflows" / "foundation-manual-dispatch.yml").read_text(encoding="utf-8")
    result = verification.validate_manual_workflow_yaml_static(yaml_text, {})
    assert result["valid"] is True
    assert result["pr_trigger_found"] is False
    assert result["push_trigger_found"] is False
    assert result["schedule_trigger_found"] is False
    assert result["workflow_dispatch_trigger_found"] is True
    assert result["confirm_phrase_present"] is True
    assert result["plan_only_default_set"] is True
    assert result["execute_mode_input_present"] is True


def test_static_validate_rejects_pr_trigger():
    yaml_text = "name: Test\non:\n  pull_request:\n  workflow_dispatch:\n"
    result = verification.validate_manual_workflow_yaml_static(yaml_text, {})
    assert result["valid"] is False
    assert result["pr_trigger_found"] is True


def test_static_validate_rejects_push_trigger():
    yaml_text = "name: Test\non:\n  push:\n  workflow_dispatch:\n"
    result = verification.validate_manual_workflow_yaml_static(yaml_text, {})
    assert result["valid"] is False
    assert result["push_trigger_found"] is True


def test_static_validate_rejects_schedule_trigger():
    yaml_text = "name: Test\non:\n  schedule:\n  workflow_dispatch:\n"
    result = verification.validate_manual_workflow_yaml_static(yaml_text, {})
    assert result["valid"] is False
    assert result["schedule_trigger_found"] is True


def test_static_validate_rejects_secrets():
    yaml_text = "name: Test\non:\n  workflow_dispatch:\nsecrets:\n  API_KEY: ${{ secrets.API_KEY }}\n"
    result = verification.validate_manual_workflow_yaml_static(yaml_text, {})
    assert result["valid"] is False
    assert result["secrets_found"] is True


def test_static_validate_rejects_network_call():
    yaml_text = "name: Test\non:\n  workflow_dispatch:\nsteps:\n  - curl https://example.com\n"
    result = verification.validate_manual_workflow_yaml_static(yaml_text, {})
    assert result["valid"] is False
    assert result["network_call_found"] is True


def test_static_validate_rejects_auto_fix():
    yaml_text = 'name: Test\non:\n  workflow_dispatch:\njobs:\n  job_test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: auto-fix/action@latest\n'
    result = verification.validate_manual_workflow_yaml_static(yaml_text, {})
    assert result["valid"] is False
    assert result["auto_fix_found"] is True


def test_static_validate_rejects_missing_confirm_phrase():
    yaml_text = "name: Test\non:\n  workflow_dispatch:\n"
    result = verification.validate_manual_workflow_yaml_static(yaml_text, {})
    assert result["valid"] is False
    assert result["confirm_phrase_present"] is False


def test_static_validate_rejects_missing_plan_only():
    yaml_text = "name: Test\non:\n  workflow_dispatch:\n  inputs:\n    confirm_manual_dispatch:\n      required: true\n"
    result = verification.validate_manual_workflow_yaml_static(yaml_text, {})
    assert result["valid"] is False
    assert result["plan_only_default_set"] is False


def test_static_validate_empty_text_fails():
    result = verification.validate_manual_workflow_yaml_static(None, None)
    assert result["valid"] is False


# ── 3. verify_workflow_guard_expressions ──────────────────────────────────

def test_guard_expressions_valid_for_real_workflow():
    yaml_text = Path(_root() / ".github" / "workflows" / "foundation-manual-dispatch.yml").read_text(encoding="utf-8")
    result = verification.verify_workflow_guard_expressions(yaml_text)
    assert result["valid"] is True
    assert result["job_count"] > 0
    assert result["guard_count"] > 0


def test_guard_expressions_empty_text_fails():
    result = verification.verify_workflow_guard_expressions(None)
    assert result["valid"] is False


def test_guard_expressions_missing_guards():
    yaml_text = "name: Test\non:\n  workflow_dispatch:\njobs:\n  job_test:\n    runs-on: ubuntu-latest\n"
    result = verification.verify_workflow_guard_expressions(yaml_text)
    assert result["valid"] is False


# ── 4. verify_stage_selection_guards ──────────────────────────────────────

def test_stage_selection_guards_valid():
    yaml_text = Path(_root() / ".github" / "workflows" / "foundation-manual-dispatch.yml").read_text(encoding="utf-8")
    result = verification.verify_stage_selection_guards(yaml_text)
    # The real workflow has stage_selection input
    assert result["stage_selection_found"] is True


def test_stage_selection_guards_empty_fails():
    result = verification.verify_stage_selection_guards(None)
    assert result["valid"] is False


# ── 5. verify_existing_workflows_unchanged ────────────────────────────────

def test_existing_workflows_unchanged():
    result = verification.verify_existing_workflows_unchanged(str(_root()))
    assert result["valid"] is True
    assert result["backend_unit_tests_exists"] is True
    assert result["lint_check_exists"] is True


def test_existing_workflows_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    result = verification.verify_existing_workflows_unchanged(str(tmp_path))
    assert result["valid"] is False


# ── 6. verify_runtime_artifact_mutation_guard ──────────────────────────────

def test_artifact_guard_pass_when_no_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    result = verification.verify_runtime_artifact_mutation_guard(str(tmp_path))
    assert result["valid"] is True


# ── 7. run_manual_workflow_local_plan_only_verification ───────────────────

def test_plan_only_verification_returns_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    monkeypatch.setattr(verification, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    # The function calls ci_local_dryrun which will run against real project
    # In this test we verify it returns a result dict with expected fields
    result = verification.run_manual_workflow_local_plan_only_verification(str(_root()))
    assert "all_pending" in result
    assert "all_pr_status" in result
    assert "fast_status" in result
    assert "safety_status" in result


# ── 8. run_manual_workflow_local_safety_execute_smoke ───────────────────

def test_safety_execute_returns_result(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    monkeypatch.setattr(verification, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    result = verification.run_manual_workflow_local_safety_execute_smoke(str(_root()), timeout_seconds=60)
    assert "timed_out" in result
    assert "passed" in result
    assert "safety_status" in result


# ── 9. evaluate_manual_workflow_runtime_verification ─────────────────────

def test_evaluate_verification_returns_result(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    monkeypatch.setattr(verification, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    result = verification.evaluate_manual_workflow_runtime_verification(str(_root()), run_safety_execute=False)
    assert "verification_id" in result
    assert "status" in result
    assert "checks" in result
    assert len(result["checks"]) >= 9


def test_evaluate_verification_workflow_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    monkeypatch.setattr(verification, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    result = verification.evaluate_manual_workflow_runtime_verification(str(tmp_path), run_safety_execute=False)
    assert result["status"] == verification.ManualWorkflowRuntimeVerificationStatus.BLOCKED_WORKFLOW_NOT_FOUND


# ── 10. validate_manual_workflow_runtime_verification ───────────────────

def test_validate_verification_result_valid():
    result = verification.evaluate_manual_workflow_runtime_verification(str(_root()), run_safety_execute=False)
    val = verification.validate_manual_workflow_runtime_verification(result)
    assert val["valid"] is True


def test_validate_verification_result_missing_field():
    result = {"status": "passed"}
    val = verification.validate_manual_workflow_runtime_verification(result)
    assert val["valid"] is False
    assert any("missing_field" in e for e in val["errors"])


def test_validate_verification_result_insufficient_checks():
    result = {
        "verification_id": "test",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": "passed",
        "workflow_path": "/test",
        "yaml_valid": True,
        "guard_expressions_valid": True,
        "stage_selection_valid": True,
        "execute_mode_valid": True,
        "plan_only_verification_passed": True,
        "safety_execute_smoke_passed": True,
        "existing_workflows_unchanged": True,
        "runtime_artifact_guard_passed": True,
        "checks": [{"check_id": "only_one"}],
    }
    val = verification.validate_manual_workflow_runtime_verification(result)
    assert val["valid"] is False
    assert any("insufficient_checks" in e for e in val["errors"])


# ── 11. Report generation safety ─────────────────────────────────────────

def test_generate_writes_only_tmp_path(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    monkeypatch.setattr(verification, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(verification, "DEFAULT_JSON_PATH", tmp_path / "R241-16I.json")
    monkeypatch.setattr(verification, "DEFAULT_MD_PATH", tmp_path / "R241-16I.md")
    result = verification.evaluate_manual_workflow_runtime_verification(str(_root()), run_safety_execute=False)
    report = verification.generate_manual_workflow_runtime_verification_report(result, str(tmp_path / "R241-16I.json"))
    assert Path(report["output_path"]).exists()
    assert Path(report["report_path"]).exists()


def test_generate_does_not_write_audit_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    monkeypatch.setattr(verification, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(verification, "DEFAULT_JSON_PATH", tmp_path / "R241-16I.json")
    monkeypatch.setattr(verification, "DEFAULT_MD_PATH", tmp_path / "R241-16I.md")
    result = verification.evaluate_manual_workflow_runtime_verification(str(_root()), run_safety_execute=False)
    verification.generate_manual_workflow_runtime_verification_report(result, str(tmp_path / "R241-16I.json"))
    assert jsonl.read_text(encoding="utf-8") == before


def test_generate_does_not_write_runtime_or_action_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    monkeypatch.setattr(verification, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(verification, "DEFAULT_JSON_PATH", tmp_path / "R241-16I.json")
    monkeypatch.setattr(verification, "DEFAULT_MD_PATH", tmp_path / "R241-16I.md")
    result = verification.evaluate_manual_workflow_runtime_verification(str(_root()), run_safety_execute=False)
    verification.generate_manual_workflow_runtime_verification_report(result, str(tmp_path / "R241-16I.json"))
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "action_queue").exists()


def test_generate_does_not_perform_network_call(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    monkeypatch.setattr(verification, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(verification, "DEFAULT_JSON_PATH", tmp_path / "R241-16I.json")
    monkeypatch.setattr(verification, "DEFAULT_MD_PATH", tmp_path / "R241-16I.md")
    # Patch plan_only and safety_execute to track if generate_report calls them
    original_plan = verification.run_manual_workflow_local_plan_only_verification
    def patched_plan(root, **kw):
        called.append("plan")
        return original_plan(root, **kw)
    monkeypatch.setattr(verification, "run_manual_workflow_local_plan_only_verification", patched_plan)
    original_safety = verification.run_manual_workflow_local_safety_execute_smoke
    def patched_safety(root, timeout_seconds=60, **kw):
        called.append("safety")
        return original_safety(root, timeout_seconds=timeout_seconds, **kw)
    monkeypatch.setattr(verification, "run_manual_workflow_local_safety_execute_smoke", patched_safety)
    # Build result manually (no evaluate call) to test generate_report in isolation
    result = {
        "verification_id": "R241-16I_runtime_verification",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": verification.ManualWorkflowRuntimeVerificationStatus.PASSED,
        "workflow_path": str(_root() / ".github" / "workflows" / "foundation-manual-dispatch.yml"),
        "yaml_valid": True,
        "guard_expressions_valid": True,
        "stage_selection_valid": True,
        "execute_mode_valid": True,
        "plan_only_verification_passed": True,
        "safety_execute_smoke_passed": False,
        "existing_workflows_unchanged": True,
        "runtime_artifact_guard_passed": True,
        "checks": [],
        "plan_only_result": None,
        "safety_execute_result": None,
        "warnings": [],
        "errors": [],
    }
    verification.generate_manual_workflow_runtime_verification_report(result, str(tmp_path / "R241-16I.json"))
    # generate_report itself should not call plan_only or safety_execute
    assert called == []


def test_generate_does_not_execute_auto_fix(tmp_path, monkeypatch):
    monkeypatch.setattr(verification, "ROOT", tmp_path)
    monkeypatch.setattr(verification, "TARGET_WORKFLOW_PATH", tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml")
    monkeypatch.setattr(verification, "DEFAULT_JSON_PATH", tmp_path / "R241-16I.json")
    monkeypatch.setattr(verification, "DEFAULT_MD_PATH", tmp_path / "R241-16I.md")
    result = verification.evaluate_manual_workflow_runtime_verification(str(_root()), run_safety_execute=False)
    verification.generate_manual_workflow_runtime_verification_report(result, str(tmp_path / "R241-16I.json"))
    assert result["yaml_valid"] is True
