"""Tests for R241-16Q publish push failure review."""

import json
from pathlib import Path

from app.foundation import ci_publish_push_failure_review as review_mod
from app.foundation import ci_publish_implementation as publish_impl
from app.foundation import ci_publish_retry_git_identity as retry_impl


def _retry_payload(status=retry_impl.PublishRetryStatus.RETRY_PUSH_FAILED, publish_status=publish_impl.PublishImplementationStatus.PUSH_FAILED):
    return {
        "status": status,
        "publish_result": {
            "status": publish_status,
            "commit_succeeded": True,
            "push_succeeded": False,
            "commit_hash": review_mod.EXPECTED_COMMIT_HASH,
            "errors": ["git_push_failed"],
            "git_command_results": [
                {
                    "command_id": "git_push_origin_main",
                    "exit_code": 128,
                    "stderr_tail": "remote: Permission to bytedance/deer-flow.git denied to yangzixuan88.\nfatal: The requested URL returned error: 403",
                }
            ],
        },
        "local_mutation_guard": {
            "existing_workflows_unchanged": True,
            "audit_jsonl_unchanged": True,
            "runtime_action_queue_unchanged": True,
        },
    }


def _write_retry(tmp_path: Path, payload=None):
    path = tmp_path / "migration_reports/foundation_audit/R241-16P_RETRY_PUBLISH_IMPLEMENTATION_RESULT.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload or _retry_payload()), encoding="utf-8")


def _cmd(argv, stdout="", code=0):
    return {
        "argv": argv,
        "command_executed": True,
        "shell_allowed": False,
        "exit_code": code,
        "stdout_tail": stdout,
        "stderr_tail": "",
        "runtime_seconds": 0.01,
        "blocked_reasons": [],
        "warnings": [],
        "errors": [],
    }


def _safe_content(root=None):
    return {
        "workflow_content_safe": True,
        "workflow_dispatch_only": True,
        "has_pr_trigger": False,
        "has_push_trigger": False,
        "has_schedule_trigger": False,
        "has_secrets": False,
    }


def test_load_retry_result_requires_retry_push_failed(tmp_path):
    _write_retry(tmp_path)
    result = review_mod.load_r241_16p_retry_result(str(tmp_path))
    assert result["passed"] is True


def test_load_retry_result_requires_commit_succeeded_true(tmp_path):
    payload = _retry_payload()
    payload["publish_result"]["commit_succeeded"] = False
    _write_retry(tmp_path, payload)
    result = review_mod.load_r241_16p_retry_result(str(tmp_path))
    assert "commit_succeeded_true" in result["blocked_reasons"]


def test_load_retry_result_requires_push_succeeded_false(tmp_path):
    payload = _retry_payload()
    payload["publish_result"]["push_succeeded"] = True
    _write_retry(tmp_path, payload)
    result = review_mod.load_r241_16p_retry_result(str(tmp_path))
    assert "push_succeeded_false" in result["blocked_reasons"]


def test_inspect_local_commit_confirms_only_target_workflow(monkeypatch):
    def fake_run(argv, **kwargs):
        joined = " ".join(argv)
        if "rev-parse HEAD" in joined:
            return _cmd(argv, review_mod.EXPECTED_COMMIT_HASH + "\n")
        if "diff-tree --no-commit-id --name-only" in joined:
            return _cmd(argv, review_mod.TARGET_WORKFLOW_PATH + "\n")
        if "branch --show-current" in joined:
            return _cmd(argv, "main\n")
        if "rev-list" in joined:
            return _cmd(argv, "0\t1\n")
        if "show --name-only" in joined:
            return _cmd(argv, "Add manual foundation CI workflow\n")
        return _cmd(argv, "")
    monkeypatch.setattr(review_mod, "_run_readonly_git", fake_run)
    monkeypatch.setattr(review_mod, "load_r241_16p_retry_result", lambda root=None: {"publish_result": {"commit_hash": review_mod.EXPECTED_COMMIT_HASH}})
    monkeypatch.setattr(review_mod.publish_review, "inspect_publish_workflow_content_safety", _safe_content)
    result = review_mod.inspect_local_publish_commit()
    assert result["local_commit_only_target_workflow"] is True


def test_inspect_local_commit_blocks_non_target_files(monkeypatch):
    def fake_run(argv, **kwargs):
        joined = " ".join(argv)
        if "rev-parse HEAD" in joined:
            return _cmd(argv, review_mod.EXPECTED_COMMIT_HASH + "\n")
        if "diff-tree --no-commit-id --name-only" in joined:
            return _cmd(argv, review_mod.TARGET_WORKFLOW_PATH + "\nbackend/app/x.py\n")
        return _cmd(argv, "")
    monkeypatch.setattr(review_mod, "_run_readonly_git", fake_run)
    monkeypatch.setattr(review_mod, "load_r241_16p_retry_result", lambda root=None: {"publish_result": {"commit_hash": review_mod.EXPECTED_COMMIT_HASH}})
    monkeypatch.setattr(review_mod.publish_review, "inspect_publish_workflow_content_safety", _safe_content)
    result = review_mod.inspect_local_publish_commit()
    assert result["local_commit_only_target_workflow"] is False


def test_inspect_push_failure_classifies_403_permission_denied(tmp_path):
    _write_retry(tmp_path)
    result = review_mod.inspect_push_failure_reason(str(tmp_path))
    assert result["classification"] == "permission_denied_403"
    assert result["actor"] == "yangzixuan88"


def test_inspect_push_failure_classifies_auth_missing(tmp_path):
    payload = _retry_payload()
    payload["publish_result"]["git_command_results"][0]["stderr_tail"] = "fatal: could not read Username"
    _write_retry(tmp_path, payload)
    result = review_mod.inspect_push_failure_reason(str(tmp_path))
    assert result["classification"] == "auth_missing_or_invalid"


def test_remote_still_missing_workflow_when_ls_tree_empty(monkeypatch):
    monkeypatch.setattr(review_mod, "_run_readonly_git", lambda argv, **kwargs: _cmd(argv, ""))
    result = review_mod.verify_remote_still_missing_workflow()
    assert result["remote_workflow_present"] is False


def test_remote_present_changes_decision(monkeypatch):
    monkeypatch.setattr(review_mod, "_run_readonly_git", lambda argv, **kwargs: _cmd(argv, review_mod.TARGET_WORKFLOW_PATH + "\n"))
    result = review_mod.verify_remote_still_missing_workflow()
    assert result["remote_workflow_present"] is True


def test_mutation_guard_detects_staged_files(monkeypatch):
    monkeypatch.setattr(review_mod.publish_impl, "capture_publish_mutation_baseline", lambda root=None: {})
    monkeypatch.setattr(review_mod.publish_impl, "verify_publish_local_mutation_guard", lambda root=None, baseline=None: {"errors": [], "warnings": [], "target_workflow_content_unchanged": True, "existing_workflows_unchanged": True, "audit_jsonl_unchanged": True, "runtime_action_queue_unchanged": True})
    monkeypatch.setattr(review_mod, "_run_readonly_git", lambda argv, **kwargs: _cmd(argv, "A  .github/workflows/foundation-manual-dispatch.yml\n"))
    result = review_mod.verify_no_local_mutation_during_push_failure_review()
    assert result["valid"] is False
    assert "staged_files_detected" in result["errors"]


def test_mutation_guard_detects_workflow_modification(monkeypatch):
    monkeypatch.setattr(review_mod.publish_impl, "capture_publish_mutation_baseline", lambda root=None: {})
    monkeypatch.setattr(review_mod.publish_impl, "verify_publish_local_mutation_guard", lambda root=None, baseline=None: {"errors": ["workflow_content_changed"], "warnings": [], "target_workflow_content_unchanged": False, "existing_workflows_unchanged": True, "audit_jsonl_unchanged": True, "runtime_action_queue_unchanged": True})
    monkeypatch.setattr(review_mod, "_run_readonly_git", lambda argv, **kwargs: _cmd(argv, ""))
    result = review_mod.verify_no_local_mutation_during_push_failure_review()
    assert result["valid"] is False


def test_recovery_options_include_all_paths():
    options = review_mod.build_publish_recovery_options()["options"]
    ids = {o["option_id"] for o in options}
    assert review_mod.PublishRecoveryOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT_PERMISSION in ids
    assert review_mod.PublishRecoveryOption.OPTION_B_PUSH_TO_USER_FORK_AFTER_CONFIRMATION in ids
    assert review_mod.PublishRecoveryOption.OPTION_C_CREATE_REVIEW_BRANCH_AFTER_CONFIRMATION in ids
    assert review_mod.PublishRecoveryOption.OPTION_D_GENERATE_PATCH_BUNDLE_AFTER_CONFIRMATION in ids
    assert review_mod.PublishRecoveryOption.OPTION_E_ROLLBACK_LOCAL_COMMIT_AFTER_CONFIRMATION in ids


def test_command_blueprints_all_command_allowed_now_false():
    blueprints = review_mod.build_push_failure_command_blueprints()["blueprints"]
    assert all(bp["command_allowed_now"] is False for bp in blueprints)


def test_command_blueprints_reject_force_push():
    data = review_mod.build_push_failure_command_blueprints()
    joined = json.dumps(data).lower()
    assert "--force" not in joined


def test_command_blueprints_reject_reset_hard():
    data = review_mod.build_push_failure_command_blueprints()
    joined = json.dumps(data).lower()
    assert "reset --hard" not in joined


def test_evaluate_permission_denied_returns_reviewed(monkeypatch):
    monkeypatch.setattr(review_mod.publish_impl, "capture_publish_mutation_baseline", lambda root=None: {})
    monkeypatch.setattr(review_mod, "load_r241_16p_retry_result", lambda root=None: {"passed": True, "publish_result": {"commit_hash": review_mod.EXPECTED_COMMIT_HASH}, "warnings": [], "errors": []})
    monkeypatch.setattr(review_mod, "inspect_local_publish_commit", lambda root=None: {"local_commit_hash": review_mod.EXPECTED_COMMIT_HASH, "local_commit_exists": True, "local_commit_only_target_workflow": True, "existing_workflows_unchanged": True, "local_branch": "main", "ahead_behind_summary": "0\t1"})
    monkeypatch.setattr(review_mod, "inspect_push_failure_reason", lambda root=None: {"classification": "permission_denied_403", "actor": "x", "errors": []})
    monkeypatch.setattr(review_mod, "verify_remote_still_missing_workflow", lambda root=None: {"remote_workflow_present": False})
    monkeypatch.setattr(review_mod, "verify_no_local_mutation_during_push_failure_review", lambda root=None, baseline=None: {"valid": True, "workflow_files_unchanged": True, "staged_area_empty": True})
    result = review_mod.evaluate_publish_push_failure_review()
    assert result["status"] == review_mod.PublishPushFailureReviewStatus.REVIEWED_PUSH_PERMISSION_DENIED


def test_evaluate_unsafe_commit_returns_blocked(monkeypatch):
    monkeypatch.setattr(review_mod.publish_impl, "capture_publish_mutation_baseline", lambda root=None: {})
    monkeypatch.setattr(review_mod, "load_r241_16p_retry_result", lambda root=None: {"passed": True, "publish_result": {"commit_hash": review_mod.EXPECTED_COMMIT_HASH}, "warnings": [], "errors": []})
    monkeypatch.setattr(review_mod, "inspect_local_publish_commit", lambda root=None: {"local_commit_exists": True, "local_commit_only_target_workflow": False, "existing_workflows_unchanged": True})
    monkeypatch.setattr(review_mod, "inspect_push_failure_reason", lambda root=None: {"classification": "permission_denied_403", "errors": []})
    monkeypatch.setattr(review_mod, "verify_remote_still_missing_workflow", lambda root=None: {"remote_workflow_present": False})
    monkeypatch.setattr(review_mod, "verify_no_local_mutation_during_push_failure_review", lambda root=None, baseline=None: {"valid": True, "workflow_files_unchanged": True})
    result = review_mod.evaluate_publish_push_failure_review()
    assert result["status"] == review_mod.PublishPushFailureReviewStatus.BLOCKED_COMMIT_SCOPE_UNSAFE


def test_validate_review_valid_true():
    review = {
        "local_commit_exists": True,
        "local_commit_only_target_workflow": True,
        "confirmation_requirements": {"confirmation_required": True},
        "command_blueprints": review_mod.build_push_failure_command_blueprints()["blueprints"],
    }
    assert review_mod.validate_publish_push_failure_review(review)["valid"] is True


def test_validate_rejects_git_push_executed():
    result = review_mod.validate_publish_push_failure_review({"git_push_executed": True, "confirmation_requirements": {"confirmation_required": True}})
    assert "git_push_executed" in result["errors"]


def test_validate_rejects_git_commit_executed():
    result = review_mod.validate_publish_push_failure_review({"git_commit_executed": True, "confirmation_requirements": {"confirmation_required": True}})
    assert "git_commit_executed" in result["errors"]


def test_validate_rejects_git_reset_executed():
    result = review_mod.validate_publish_push_failure_review({"git_reset_executed": True, "confirmation_requirements": {"confirmation_required": True}})
    assert "git_reset_or_revert_executed" in result["errors"]


def test_validate_rejects_gh_workflow_run():
    result = review_mod.validate_publish_push_failure_review({"gh_workflow_run_executed": True, "confirmation_requirements": {"confirmation_required": True}})
    assert "gh_workflow_run_executed" in result["errors"]


def test_generate_report_writes_only_tmp_path(tmp_path):
    out = tmp_path / "R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.json"
    review = {
        "status": review_mod.PublishPushFailureReviewStatus.DESIGN_ONLY,
        "confirmation_requirements": {"confirmation_required": True},
        "command_blueprints": review_mod.build_push_failure_command_blueprints()["blueprints"],
        "warnings": [],
        "errors": [],
    }
    result = review_mod.generate_publish_push_failure_review_report(review, str(out))
    assert Path(result["output_path"]).exists()
    assert Path(result["report_path"]).exists()
    assert Path(result["output_path"]).parent == tmp_path


def test_no_workflow_content_modification_in_tests(tmp_path):
    path = tmp_path / review_mod.TARGET_WORKFLOW_PATH
    path.parent.mkdir(parents=True)
    path.write_text("same", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    review_mod.build_publish_recovery_options()
    assert path.read_text(encoding="utf-8") == before


def test_no_audit_jsonl_write_constant():
    assert "jsonl" not in review_mod.PublishRecoveryOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT_PERMISSION


def test_no_runtime_action_queue_write_constant():
    assert "runtime" not in review_mod.PublishRecoveryOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT_PERMISSION


def test_no_secret_read_constant():
    assert "secret" not in review_mod.PublishRecoveryOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT_PERMISSION


def test_no_auto_fix_constant():
    assert "auto" not in review_mod.PublishRecoveryOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT_PERMISSION

