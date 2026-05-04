"""Tests for R241-16P publish implementation."""

from pathlib import Path

from app.foundation import ci_publish_implementation as impl


def _confirmation_payload(status="allowed_for_next_review", decision="allow_publish_implementation_review"):
    return {
        "decision": {
            "status": status,
            "decision": decision,
            "allowed_next_phase": "R241-16P_publish_implementation",
            "requested_option": impl.EXPECTED_OPTION,
            "publish_allowed_now": False,
            "confirmation_input": {"phrase_exact_match": True},
            "publish_review_ref": {"status": "ready_for_publish_confirmation"},
            "blocked_reasons": [],
        },
        "validation": {"valid": True},
    }


def _ready_review():
    return {
        "status": "ready_for_publish_confirmation",
        "decision": "allow_publish_confirmation_gate",
        "local_workflow_exists": True,
        "remote_workflow_exists": False,
        "existing_workflows_unchanged": True,
        "workflow_diff_summary": {
            "diff_only_target_workflow": True,
            "workflow_content_safe": True,
            "workflow_dispatch_only": True,
            "has_pr_trigger": False,
            "has_push_trigger": False,
            "has_schedule_trigger": False,
            "has_secrets": False,
            "has_webhook_network": False,
            "has_runtime_write": False,
            "has_audit_jsonl_write": False,
            "has_action_queue_write": False,
            "has_auto_fix": False,
        },
        "rollback_plan": {"no_auto_rollback": True},
        "warnings": [],
        "errors": [],
    }


def _safe_content():
    return {
        "local_workflow_exists": True,
        "workflow_content_safe": True,
        "workflow_dispatch_only": True,
        "has_pr_trigger": False,
        "has_push_trigger": False,
        "has_schedule_trigger": False,
        "has_secrets": False,
        "has_webhook_network": False,
        "has_runtime_write": False,
        "has_audit_jsonl_write": False,
        "has_action_queue_write": False,
    }


def _git_result(command_id, argv, exit_code=0, stdout="", stderr=""):
    return {
        "command_id": command_id,
        "argv": argv,
        "command_executed": True,
        "shell_allowed": False,
        "exit_code": exit_code,
        "stdout_tail": stdout,
        "stderr_tail": stderr,
        "runtime_seconds": 0.01,
        "would_modify_git_history": False,
        "would_push_remote": False,
        "blocked_reasons": [],
        "warnings": [],
        "errors": [],
    }


def _write_confirmation(tmp_path: Path, payload=None):
    path = tmp_path / "migration_reports" / "foundation_audit"
    path.mkdir(parents=True)
    (path / "R241-16O_PUBLISH_CONFIRMATION_GATE.json").write_text(
        impl._json(payload or _confirmation_payload()),
        encoding="utf-8",
    )


def test_load_confirmation_requires_allowed_for_next_review(tmp_path):
    _write_confirmation(tmp_path)
    result = impl.load_publish_confirmation_for_implementation(str(tmp_path))
    assert result["passed"] is True


def test_load_confirmation_rejects_blocked_gate(tmp_path):
    _write_confirmation(tmp_path, _confirmation_payload("blocked_missing_confirmation", "block"))
    result = impl.load_publish_confirmation_for_implementation(str(tmp_path))
    assert result["passed"] is False
    assert "status_allowed" in result["blocked_reasons"]


def test_prechecks_require_r241_16n_ready(tmp_path, monkeypatch):
    _write_confirmation(tmp_path)
    review = _ready_review()
    review["status"] = "blocked_unexpected_diff"
    monkeypatch.setattr(impl.publish_review, "evaluate_canonical_publish_readiness", lambda root=None: review)
    monkeypatch.setattr(impl.publish_review, "validate_canonical_publish_readiness", lambda review: {"valid": False, "violations": ["readiness_not_ready"]})
    monkeypatch.setattr(impl, "_remote_exact_path_present", lambda root=None: {"present": False, "command_result": _git_result("ls", ["git"])})
    monkeypatch.setattr(impl, "_cached_files", lambda root=None: [])
    monkeypatch.setattr(impl.publish_review, "inspect_workflow_directory_diff", lambda root=None: {"target_workflow_changed": True, "warnings": [], "errors": []})
    monkeypatch.setattr(impl, "_run_git", lambda *args, **kwargs: _git_result(args[0], args[1], stdout="main" if args[0] == "git_branch_show_current" else "git version"))
    result = impl.run_publish_implementation_prechecks(str(tmp_path))
    assert result["passed"] is False


def test_prechecks_reject_unsafe_workflow(tmp_path, monkeypatch):
    _write_confirmation(tmp_path)
    review = _ready_review()
    review["workflow_diff_summary"]["workflow_content_safe"] = False
    monkeypatch.setattr(impl.publish_review, "evaluate_canonical_publish_readiness", lambda root=None: review)
    monkeypatch.setattr(impl.publish_review, "validate_canonical_publish_readiness", lambda review: {"valid": True, "violations": []})
    monkeypatch.setattr(impl, "_remote_exact_path_present", lambda root=None: {"present": False, "command_result": _git_result("ls", ["git"])})
    monkeypatch.setattr(impl, "_cached_files", lambda root=None: [])
    monkeypatch.setattr(impl.publish_review, "inspect_workflow_directory_diff", lambda root=None: {"target_workflow_changed": True, "warnings": [], "errors": []})
    monkeypatch.setattr(impl, "_run_git", lambda *args, **kwargs: _git_result(args[0], args[1], stdout="main" if args[0] == "git_branch_show_current" else "git version"))
    result = impl.run_publish_implementation_prechecks(str(tmp_path))
    assert result["passed"] is False


def test_prechecks_reject_existing_workflow_mutation(tmp_path, monkeypatch):
    _write_confirmation(tmp_path)
    review = _ready_review()
    review["existing_workflows_unchanged"] = False
    monkeypatch.setattr(impl.publish_review, "evaluate_canonical_publish_readiness", lambda root=None: review)
    monkeypatch.setattr(impl.publish_review, "validate_canonical_publish_readiness", lambda review: {"valid": True, "violations": []})
    monkeypatch.setattr(impl, "_remote_exact_path_present", lambda root=None: {"present": False, "command_result": _git_result("ls", ["git"])})
    monkeypatch.setattr(impl, "_cached_files", lambda root=None: [])
    monkeypatch.setattr(impl.publish_review, "inspect_workflow_directory_diff", lambda root=None: {"target_workflow_changed": True, "warnings": [], "errors": []})
    monkeypatch.setattr(impl, "_run_git", lambda *args, **kwargs: _git_result(args[0], args[1], stdout="main" if args[0] == "git_branch_show_current" else "git version"))
    result = impl.run_publish_implementation_prechecks(str(tmp_path))
    assert result["passed"] is False


def test_prechecks_allow_non_workflow_dirty_warning(tmp_path, monkeypatch):
    _write_confirmation(tmp_path)
    monkeypatch.setattr(impl.publish_review, "evaluate_canonical_publish_readiness", lambda root=None: _ready_review())
    monkeypatch.setattr(impl.publish_review, "validate_canonical_publish_readiness", lambda review: {"valid": True, "violations": []})
    monkeypatch.setattr(impl, "_remote_exact_path_present", lambda root=None: {"present": False, "command_result": _git_result("ls", ["git"])})
    monkeypatch.setattr(impl, "_cached_files", lambda root=None: [])
    monkeypatch.setattr(impl.publish_review, "inspect_workflow_directory_diff", lambda root=None: {"target_workflow_changed": True, "repo_dirty_outside_workflows_warning": True, "warnings": ["repo_dirty_warning"], "errors": []})
    monkeypatch.setattr(impl, "_run_git", lambda *args, **kwargs: _git_result(args[0], args[1], stdout="main" if args[0] == "git_branch_show_current" else "git version"))
    result = impl.run_publish_implementation_prechecks(str(tmp_path))
    assert result["passed"] is True
    assert "non_workflow_dirty_files_ignored_for_publish_commit" in result["warnings"]


def test_capture_baseline_captures_workflow_hashes(tmp_path):
    workflow = tmp_path / impl.TARGET_WORKFLOW_PATH
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: x\non: workflow_dispatch\n", encoding="utf-8")
    result = impl.capture_publish_mutation_baseline(str(tmp_path))
    assert result["workflow_file_states"][impl.TARGET_WORKFLOW_PATH]["sha256"]


def test_stage_only_target_workflow_runs_git_add_target(monkeypatch):
    seen = []
    monkeypatch.setattr(impl, "_run_git", lambda command_id, argv, **kwargs: seen.append(argv) or _git_result(command_id, argv))
    monkeypatch.setattr(impl, "_cached_files", lambda root=None: [impl.TARGET_WORKFLOW_PATH])
    result = impl.stage_only_target_workflow()
    assert result["status"] == impl.PublishImplementationStepStatus.PASSED
    assert ["git", "add", impl.TARGET_WORKFLOW_PATH] in seen


def test_stage_rejects_extra_staged_files(monkeypatch):
    monkeypatch.setattr(impl, "_run_git", lambda command_id, argv, **kwargs: _git_result(command_id, argv))
    monkeypatch.setattr(impl, "_cached_files", lambda root=None: [impl.TARGET_WORKFLOW_PATH, "migration_reports/report.md"])
    result = impl.stage_only_target_workflow()
    assert result["status"] == impl.PublishImplementationStepStatus.BLOCKED


def test_commit_requires_only_target_staged(monkeypatch):
    monkeypatch.setattr(impl, "_cached_files", lambda root=None: ["backend/app/code.py"])
    result = impl.commit_target_workflow()
    assert result["status"] == impl.PublishImplementationStepStatus.BLOCKED


def test_commit_records_commit_hash(monkeypatch):
    def fake_run(command_id, argv, **kwargs):
        if command_id == "git_rev_parse_head":
            return _git_result(command_id, argv, stdout="abc123\n")
        if command_id == "git_diff_tree_publish_commit":
            return _git_result(command_id, argv, stdout=f"{impl.TARGET_WORKFLOW_PATH}\n")
        return _git_result(command_id, argv)
    monkeypatch.setattr(impl, "_cached_files", lambda root=None: [impl.TARGET_WORKFLOW_PATH])
    monkeypatch.setattr(impl, "_run_git", fake_run)
    result = impl.commit_target_workflow()
    assert result["commit_hash"] == "abc123"
    assert result["status"] == impl.PublishImplementationStepStatus.PASSED


def test_commit_rejects_commit_containing_report_files(monkeypatch):
    def fake_run(command_id, argv, **kwargs):
        if command_id == "git_rev_parse_head":
            return _git_result(command_id, argv, stdout="abc123\n")
        if command_id == "git_diff_tree_publish_commit":
            return _git_result(command_id, argv, stdout=f"{impl.TARGET_WORKFLOW_PATH}\nmigration_reports/x.md\n")
        return _git_result(command_id, argv)
    monkeypatch.setattr(impl, "_cached_files", lambda root=None: [impl.TARGET_WORKFLOW_PATH])
    monkeypatch.setattr(impl, "_run_git", fake_run)
    result = impl.commit_target_workflow()
    assert result["status"] == impl.PublishImplementationStepStatus.BLOCKED


def test_push_only_after_commit_success():
    result = impl.validate_publish_implementation_result({"push_attempted": True, "commit_succeeded": False, "prechecks": []})
    assert "push_attempted_before_commit_success" in result["errors"]


def test_push_uses_origin_main_only(monkeypatch):
    monkeypatch.setattr(impl, "_run_git", lambda command_id, argv, **kwargs: _git_result(command_id, argv))
    result = impl.push_publish_commit(branch="main")
    assert result["command_result"]["argv"] == ["git", "push", "origin", "main"]


def test_verify_remote_exact_path_present(monkeypatch):
    monkeypatch.setattr(impl, "_remote_exact_path_present", lambda root=None: {"present": True, "command_result": _git_result("ls", ["git"])})
    monkeypatch.setattr(impl.publish_review, "inspect_publish_workflow_content_safety", lambda root=None: _safe_content())
    monkeypatch.setattr(impl.shutil, "which", lambda name: None)
    result = impl.verify_remote_workflow_after_publish()
    assert result["valid"] is True
    assert result["remote_workflow_exact_path_present"] is True


def test_verify_remote_treats_gh_unavailable_as_warning(monkeypatch):
    monkeypatch.setattr(impl, "_remote_exact_path_present", lambda root=None: {"present": True, "command_result": _git_result("ls", ["git"])})
    monkeypatch.setattr(impl.publish_review, "inspect_publish_workflow_content_safety", lambda root=None: _safe_content())
    monkeypatch.setattr(impl.shutil, "which", lambda name: None)
    result = impl.verify_remote_workflow_after_publish()
    assert "gh_unavailable_remote_visibility_checked_by_git_only" in result["warnings"]


def test_mutation_guard_detects_backend_unit_tests_mutation(tmp_path):
    target = tmp_path / impl.TARGET_WORKFLOW_PATH
    existing = tmp_path / " .github"
    target.parent.mkdir(parents=True)
    target.write_text("same", encoding="utf-8")
    backend = tmp_path / ".github/workflows/backend-unit-tests.yml"
    backend.write_text("before", encoding="utf-8")
    baseline = impl.capture_publish_mutation_baseline(str(tmp_path))
    backend.write_text("after", encoding="utf-8")
    result = impl.verify_publish_local_mutation_guard(str(tmp_path), baseline)
    assert result["existing_workflows_unchanged"] is False


def test_mutation_guard_detects_audit_jsonl_append(tmp_path):
    target = tmp_path / impl.TARGET_WORKFLOW_PATH
    target.parent.mkdir(parents=True)
    target.write_text("same", encoding="utf-8")
    audit = tmp_path / "migration_reports/foundation_audit/audit_trail/foundation_diagnostic_runs.jsonl"
    audit.parent.mkdir(parents=True)
    audit.write_text("{}\n", encoding="utf-8")
    baseline = impl.capture_publish_mutation_baseline(str(tmp_path))
    audit.write_text("{}\n{}\n", encoding="utf-8")
    result = impl.verify_publish_local_mutation_guard(str(tmp_path), baseline)
    assert result["audit_jsonl_unchanged"] is False


def test_rollback_unstages_target_if_commit_not_attempted(monkeypatch):
    monkeypatch.setattr(impl, "_run_git", lambda command_id, argv, **kwargs: _git_result(command_id, argv))
    result = impl.rollback_failed_publish(result={"commit_attempted": False}, reason="test")
    assert result["mode"] == "unstage_target_only"
    assert result["command_result"]["argv"] == ["git", "reset", "--", impl.TARGET_WORKFLOW_PATH]


def test_rollback_does_not_reset_hard():
    result = impl.rollback_failed_publish(
        result={"commit_attempted": True, "commit_succeeded": True, "push_attempted": True},
        reason="test",
    )
    assert result["executed"] is False
    assert "force push" in result["warnings"][0].lower()


def test_execute_blocks_on_precheck_failure(monkeypatch):
    monkeypatch.setattr(impl, "run_publish_implementation_prechecks", lambda root=None: {"passed": False, "prechecks": [], "warnings": [], "errors": []})
    result = impl.execute_publish_implementation()
    assert result["status"] == impl.PublishImplementationStatus.BLOCKED_PRECHECK_FAILED


def test_execute_published_when_commit_push_verify_all_pass(monkeypatch):
    monkeypatch.setattr(impl, "run_publish_implementation_prechecks", lambda root=None: {"passed": True, "prechecks": [], "warnings": [], "errors": []})
    monkeypatch.setattr(impl, "capture_publish_mutation_baseline", lambda root=None: {"workflow_file_states": {}, "audit_jsonl_line_counts": {}, "runtime_action_queue_path_states": {}})
    monkeypatch.setattr(impl, "stage_only_target_workflow", lambda root=None: {"status": impl.PublishImplementationStepStatus.PASSED, "command_result": _git_result("add", ["git"])})
    monkeypatch.setattr(impl, "commit_target_workflow", lambda root=None: {"status": impl.PublishImplementationStepStatus.PASSED, "command_result": _git_result("commit", ["git"]), "commit_hash": "abc"})
    monkeypatch.setattr(impl, "push_publish_commit", lambda root=None, branch="main": {"status": impl.PublishImplementationStepStatus.PASSED, "command_result": _git_result("push", ["git"])})
    monkeypatch.setattr(impl, "verify_remote_workflow_after_publish", lambda root=None: {"valid": True})
    monkeypatch.setattr(impl, "verify_publish_local_mutation_guard", lambda root=None, baseline=None: {"valid": True, "existing_workflows_unchanged": True})
    result = impl.execute_publish_implementation()
    assert result["status"] == impl.PublishImplementationStatus.PUBLISHED


def test_execute_push_failed_when_push_exits_nonzero(monkeypatch):
    monkeypatch.setattr(impl, "run_publish_implementation_prechecks", lambda root=None: {"passed": True, "prechecks": [], "warnings": [], "errors": []})
    monkeypatch.setattr(impl, "capture_publish_mutation_baseline", lambda root=None: {})
    monkeypatch.setattr(impl, "stage_only_target_workflow", lambda root=None: {"status": impl.PublishImplementationStepStatus.PASSED, "command_result": _git_result("add", ["git"])})
    monkeypatch.setattr(impl, "commit_target_workflow", lambda root=None: {"status": impl.PublishImplementationStepStatus.PASSED, "command_result": _git_result("commit", ["git"]), "commit_hash": "abc"})
    monkeypatch.setattr(impl, "push_publish_commit", lambda root=None, branch="main": {"status": impl.PublishImplementationStepStatus.FAILED, "command_result": _git_result("push", ["git"], exit_code=1), "errors": ["git_push_failed"]})
    monkeypatch.setattr(impl, "rollback_failed_publish", lambda root=None, result=None, reason=None: {"mode": "manual_revert"})
    result = impl.execute_publish_implementation()
    assert result["status"] == impl.PublishImplementationStatus.PUSH_FAILED


def test_validate_result_rejects_gh_workflow_run():
    result = {"git_command_results": [{"command_id": "bad", "argv": ["gh", "workflow", "run"], "shell_allowed": False}], "rollback_plan": {"x": True}}
    assert "gh_workflow_run_forbidden" in impl.validate_publish_implementation_result(result)["errors"]


def test_validate_result_rejects_push_branch_not_main():
    result = {"git_command_results": [{"command_id": "push", "argv": ["git", "push", "origin", "dev"], "shell_allowed": False}], "rollback_plan": {"x": True}}
    assert "push_branch_not_origin_main" in impl.validate_publish_implementation_result(result)["errors"]


def test_validate_result_rejects_commit_includes_non_target():
    result = {"commit_changed_files": [impl.TARGET_WORKFLOW_PATH, "backend/app/x.py"], "rollback_plan": {"x": True}}
    assert "commit_includes_non_target" in impl.validate_publish_implementation_result(result)["errors"]


def test_validate_result_rejects_runtime_write():
    result = {"local_mutation_guard": {"runtime_action_queue_unchanged": False}, "rollback_plan": {"x": True}}
    assert "runtime_write_detected" in impl.validate_publish_implementation_result(result)["errors"]


def test_validate_result_rejects_audit_jsonl_write():
    result = {"local_mutation_guard": {"audit_jsonl_unchanged": False}, "rollback_plan": {"x": True}}
    assert "audit_jsonl_write_detected" in impl.validate_publish_implementation_result(result)["errors"]


def test_validate_result_rejects_auto_fix():
    result = {"auto_fix_executed": True, "rollback_plan": {"x": True}}
    assert "auto_fix_executed" in impl.validate_publish_implementation_result(result)["errors"]


def test_generate_report_writes_only_tmp_path(tmp_path):
    out = tmp_path / "R241-16P_PUBLISH_IMPLEMENTATION_RESULT.json"
    result = {"status": impl.PublishImplementationStatus.BLOCKED_PRECHECK_FAILED, "rollback_plan": {"x": True}, "git_command_results": []}
    report = impl.generate_publish_implementation_report(result, str(out))
    assert Path(report["output_path"]).exists()
    assert Path(report["report_path"]).exists()
    assert Path(report["output_path"]).parent == tmp_path


def test_no_secret_read_constant():
    assert "secret" not in impl.COMMIT_MESSAGE.lower()


def test_no_workflow_content_modification_by_tests(tmp_path):
    path = tmp_path / impl.TARGET_WORKFLOW_PATH
    path.parent.mkdir(parents=True)
    path.write_text("same", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    impl.capture_publish_mutation_baseline(str(tmp_path))
    assert path.read_text(encoding="utf-8") == before
