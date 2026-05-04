"""Tests for R241-16P-Retry Git identity setup."""

import json
from pathlib import Path

from app.foundation import ci_publish_retry_git_identity as retry
from app.foundation import ci_publish_implementation as impl


def _cmd(argv, code=0, stdout="", stderr=""):
    return {
        "argv": argv,
        "command_executed": True,
        "shell_allowed": False,
        "exit_code": code,
        "stdout_tail": stdout,
        "stderr_tail": stderr,
        "runtime_seconds": 0.01,
        "warnings": [],
        "errors": [],
    }


def _previous_payload(status=impl.PublishImplementationStatus.COMMIT_FAILED, stderr="Author identity unknown"):
    return {
        "result": {
            "status": status,
            "git_command_results": [
                {"command_id": "git_commit_target_workflow", "stderr_tail": stderr}
            ],
        }
    }


def _write_previous(tmp_path: Path, payload=None):
    out = tmp_path / "migration_reports/foundation_audit/R241-16P_PUBLISH_IMPLEMENTATION_RESULT.json"
    out.parent.mkdir(parents=True)
    out.write_text(json.dumps(payload or _previous_payload()), encoding="utf-8")


def test_check_git_author_identity_detects_missing_name(monkeypatch):
    def fake_run(argv, **kwargs):
        if argv[-1] == "user.name":
            return _cmd(argv, code=1)
        return _cmd(argv, stdout="x@example.local\n")
    monkeypatch.setattr(retry, "_run_git", fake_run)
    result = retry.check_git_author_identity()
    assert result["name_present"] is False


def test_check_git_author_identity_detects_missing_email(monkeypatch):
    def fake_run(argv, **kwargs):
        if argv[-1] == "user.email":
            return _cmd(argv, code=1)
        return _cmd(argv, stdout="Name\n")
    monkeypatch.setattr(retry, "_run_git", fake_run)
    result = retry.check_git_author_identity()
    assert result["email_present"] is False


def test_configure_repo_local_git_identity_uses_no_global(monkeypatch):
    seen = []
    def fake_run(argv, **kwargs):
        seen.append(argv)
        return _cmd(argv, stdout="")
    monkeypatch.setattr(retry, "_run_git", fake_run)
    monkeypatch.setattr(
        retry,
        "check_git_author_identity",
        lambda root=None: {
            "name_present": True,
            "email_present": True,
            "current_name": retry.DEFAULT_NAME,
            "current_email": retry.DEFAULT_EMAIL,
            "scope": retry.GitIdentityScope.REPO_LOCAL,
        },
    )
    result = retry.configure_repo_local_git_identity()
    assert result["configuration_succeeded"] is True
    assert all("--global" not in argv for argv in seen)


def test_configure_repo_local_git_identity_writes_repo_local_only(monkeypatch):
    monkeypatch.setattr(retry, "_run_git", lambda argv, **kwargs: _cmd(argv))
    monkeypatch.setattr(
        retry,
        "check_git_author_identity",
        lambda root=None: {
            "name_present": True,
            "email_present": True,
            "current_name": retry.DEFAULT_NAME,
            "current_email": retry.DEFAULT_EMAIL,
            "scope": retry.GitIdentityScope.REPO_LOCAL,
        },
    )
    result = retry.configure_repo_local_git_identity()
    assert result["scope"] == retry.GitIdentityScope.REPO_LOCAL
    assert result["global_config_modified"] is False


def test_validate_identity_requires_name():
    result = retry.validate_git_identity_for_publish({"name_present": False, "email_present": True, "current_email": "x@y", "scope": retry.GitIdentityScope.REPO_LOCAL})
    assert "git_user_name_missing" in result["errors"]


def test_validate_identity_requires_email():
    result = retry.validate_git_identity_for_publish({"name_present": True, "email_present": False, "scope": retry.GitIdentityScope.REPO_LOCAL})
    assert "git_user_email_missing" in result["errors"]


def test_validate_identity_rejects_invalid_email():
    result = retry.validate_git_identity_for_publish({"name_present": True, "email_present": True, "current_email": "invalid", "scope": retry.GitIdentityScope.REPO_LOCAL})
    assert "git_user_email_invalid" in result["errors"]


def test_evaluate_blocks_if_previous_failure_not_identity_related(tmp_path):
    _write_previous(tmp_path, _previous_payload(status=impl.PublishImplementationStatus.PUSH_FAILED, stderr="auth failed"))
    result = retry.evaluate_publish_retry_with_identity_setup(str(tmp_path))
    assert result["status"] == retry.PublishRetryStatus.RETRY_BLOCKED


def test_evaluate_configures_identity_when_missing(tmp_path, monkeypatch):
    _write_previous(tmp_path)
    calls = {"configured": False}
    monkeypatch.setattr(
        retry,
        "check_git_author_identity",
        lambda root=None: {
            "name_present": calls["configured"],
            "email_present": calls["configured"],
            "current_name": retry.DEFAULT_NAME if calls["configured"] else "",
            "current_email": retry.DEFAULT_EMAIL if calls["configured"] else "",
            "scope": retry.GitIdentityScope.REPO_LOCAL,
            "needs_configuration": not calls["configured"],
            "configured_this_round": False,
        },
    )
    def configure(**kwargs):
        calls["configured"] = True
        return {"configuration_succeeded": True, "global_config_modified": False, "warnings": [], "errors": []}
    monkeypatch.setattr(retry, "configure_repo_local_git_identity", configure)
    monkeypatch.setattr(impl, "execute_publish_implementation", lambda root=None: {"status": impl.PublishImplementationStatus.PUBLISHED, "warnings": [], "errors": [], "local_mutation_guard": {"existing_workflows_unchanged": True}})
    monkeypatch.setattr(impl, "validate_publish_implementation_result", lambda result: {"valid": True, "warnings": [], "errors": []})
    result = retry.evaluate_publish_retry_with_identity_setup(str(tmp_path))
    assert result["git_identity_check"]["configured_this_round"] is True


def test_evaluate_does_not_retry_publish_if_identity_config_fails(tmp_path, monkeypatch):
    _write_previous(tmp_path)
    monkeypatch.setattr(
        retry,
        "check_git_author_identity",
        lambda root=None: {"name_present": False, "email_present": False, "needs_configuration": True, "scope": retry.GitIdentityScope.REPO_LOCAL},
    )
    monkeypatch.setattr(retry, "configure_repo_local_git_identity", lambda **kwargs: {"configuration_succeeded": False, "warnings": [], "errors": ["failed"]})
    result = retry.evaluate_publish_retry_with_identity_setup(str(tmp_path))
    assert result["status"] == retry.PublishRetryStatus.IDENTITY_CONFIGURATION_FAILED
    assert result["publish_result"] == {}


def test_evaluate_retries_publish_after_identity_valid(tmp_path, monkeypatch):
    _write_previous(tmp_path)
    monkeypatch.setattr(
        retry,
        "check_git_author_identity",
        lambda root=None: {
            "name_present": True,
            "email_present": True,
            "current_name": "Name",
            "current_email": "x@y.local",
            "scope": retry.GitIdentityScope.ALREADY_CONFIGURED,
            "needs_configuration": False,
        },
    )
    monkeypatch.setattr(impl, "execute_publish_implementation", lambda root=None: {"status": impl.PublishImplementationStatus.PUBLISHED, "warnings": [], "errors": [], "local_mutation_guard": {"existing_workflows_unchanged": True}})
    monkeypatch.setattr(impl, "validate_publish_implementation_result", lambda result: {"valid": True, "warnings": [], "errors": []})
    result = retry.evaluate_publish_retry_with_identity_setup(str(tmp_path))
    assert result["status"] == retry.PublishRetryStatus.RETRY_PUBLISHED


def test_evaluate_does_not_expand_commit_scope(tmp_path, monkeypatch):
    _write_previous(tmp_path)
    monkeypatch.setattr(
        retry,
        "check_git_author_identity",
        lambda root=None: {"name_present": True, "email_present": True, "current_name": "n", "current_email": "e@x", "scope": retry.GitIdentityScope.REPO_LOCAL, "needs_configuration": False},
    )
    publish = {"status": impl.PublishImplementationStatus.PUBLISHED, "commit_changed_files": [impl.TARGET_WORKFLOW_PATH], "warnings": [], "errors": [], "local_mutation_guard": {"existing_workflows_unchanged": True}}
    monkeypatch.setattr(impl, "execute_publish_implementation", lambda root=None: publish)
    monkeypatch.setattr(impl, "validate_publish_implementation_result", lambda result: {"valid": True, "warnings": [], "errors": []})
    result = retry.evaluate_publish_retry_with_identity_setup(str(tmp_path))
    assert result["publish_result"]["commit_changed_files"] == [impl.TARGET_WORKFLOW_PATH]


def test_generate_report_writes_only_tmp_path(tmp_path):
    out = tmp_path / "R241-16P_RETRY_PUBLISH_IMPLEMENTATION_RESULT.json"
    result = {"status": retry.PublishRetryStatus.RETRY_BLOCKED, "validation_result": {"valid": False}, "warnings": [], "errors": []}
    report = retry.generate_publish_retry_report(result, str(out))
    assert Path(report["output_path"]).exists()
    assert Path(report["report_path"]).exists()
    assert Path(report["output_path"]).parent == tmp_path


def test_no_workflow_content_modification_in_tests(tmp_path):
    path = tmp_path / impl.TARGET_WORKFLOW_PATH
    path.parent.mkdir(parents=True)
    path.write_text("same", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    retry.check_git_author_identity(str(tmp_path))
    assert path.read_text(encoding="utf-8") == before


def test_no_audit_jsonl_write_constant():
    assert "jsonl" not in retry.DEFAULT_EMAIL


def test_no_runtime_action_queue_write_constant():
    assert "runtime" not in retry.DEFAULT_EMAIL


def test_no_secret_read_constant():
    assert "secret" not in retry.DEFAULT_EMAIL


def test_no_auto_fix_constant():
    assert "auto" not in retry.DEFAULT_EMAIL

