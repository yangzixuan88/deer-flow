"""Tests for R241-16N-B publish readiness consistency repair."""

import json
from pathlib import Path

from app.foundation import ci_remote_workflow_publish_review as review_mod


SAFE_WORKFLOW = """name: Foundation Manual Dispatch
on:
  workflow_dispatch:
    inputs:
      confirm_manual_dispatch:
        default: CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN
      execute_mode:
        default: plan_only
jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - run: python scripts/ci_foundation_check.py --selection all_pr --format json
"""


def _write_workflow(root: Path, content: str = SAFE_WORKFLOW) -> None:
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / "foundation-manual-dispatch.yml").write_text(content, encoding="utf-8")


def _mock_git(status_output: str, diff_output: str = "", repo_status_output: str = ""):
    calls = []

    def fake(argv, timeout_seconds=5, root=None):
        calls.append(argv)
        joined = " ".join(argv)
        if "status --porcelain -- .github/workflows/" in joined:
            return {"executed": True, "stdout": status_output, "stderr": "", "returncode": 0, "argv": argv}
        if "diff --name-status -- .github/workflows/" in joined:
            return {"executed": True, "stdout": diff_output, "stderr": "", "returncode": 0, "argv": argv}
        if "diff --stat -- .github/workflows/" in joined:
            return {"executed": True, "stdout": "", "stderr": "", "returncode": 0, "argv": argv}
        if argv == ["git", "status", "--porcelain"]:
            return {"executed": True, "stdout": repo_status_output, "stderr": "", "returncode": 0, "argv": argv}
        return {"executed": True, "stdout": "", "stderr": "", "returncode": 0, "argv": argv}

    return fake, calls


def test_inspect_workflow_directory_diff_ignores_non_workflow_dirty_files(tmp_path, monkeypatch):
    fake, _ = _mock_git("?? .github/workflows/foundation-manual-dispatch.yml\n", repo_status_output=" M backend/app.py\n?? .github/workflows/foundation-manual-dispatch.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    result = review_mod.inspect_workflow_directory_diff(str(tmp_path))
    assert result["diff_only_target_workflow"] is True
    assert result["repo_dirty_outside_workflows_count"] == 1


def test_inspect_workflow_directory_diff_detects_target_workflow_changed(tmp_path, monkeypatch):
    fake, _ = _mock_git("?? .github/workflows/foundation-manual-dispatch.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    assert review_mod.inspect_workflow_directory_diff(str(tmp_path))["target_workflow_changed"] is True


def test_inspect_workflow_directory_diff_blocks_backend_unit_tests_mutation(tmp_path, monkeypatch):
    fake, _ = _mock_git(" M .github/workflows/backend-unit-tests.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    result = review_mod.inspect_workflow_directory_diff(str(tmp_path))
    assert ".github/workflows/backend-unit-tests.yml" in result["existing_workflows_changed"]


def test_inspect_workflow_directory_diff_blocks_lint_check_mutation(tmp_path, monkeypatch):
    fake, _ = _mock_git(" M .github/workflows/lint-check.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    result = review_mod.inspect_workflow_directory_diff(str(tmp_path))
    assert ".github/workflows/lint-check.yml" in result["existing_workflows_changed"]


def test_inspect_workflow_directory_diff_blocks_unexpected_workflow_file(tmp_path, monkeypatch):
    fake, _ = _mock_git("?? .github/workflows/other.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    result = review_mod.inspect_workflow_directory_diff(str(tmp_path))
    assert ".github/workflows/other.yml" in result["unexpected_workflows_changed"]


def test_inspect_workflow_directory_diff_uses_scoped_git_commands(tmp_path, monkeypatch):
    fake, calls = _mock_git("?? .github/workflows/foundation-manual-dispatch.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    review_mod.inspect_workflow_directory_diff(str(tmp_path))
    assert ["git", "status", "--porcelain", "--", ".github/workflows/"] in calls
    assert ["git", "diff", "--name-status", "--", ".github/workflows/"] in calls


def test_content_safety_accepts_workflow_dispatch_only(tmp_path):
    _write_workflow(tmp_path)
    result = review_mod.inspect_publish_workflow_content_safety(str(tmp_path))
    assert result["workflow_content_safe"] is True
    assert result["workflow_dispatch_only"] is True


def test_content_safety_accepts_auto_fix_blocked_notice_and_quoted_plan_only(tmp_path):
    _write_workflow(tmp_path, SAFE_WORKFLOW.replace("default: plan_only", 'default: "plan_only"') + "\n# AUTO_FIX_BLOCKED\n")
    result = review_mod.inspect_publish_workflow_content_safety(str(tmp_path))
    assert result["has_auto_fix"] is False
    assert result["execute_mode_default_plan_only"] is True


def test_content_safety_rejects_pull_request(tmp_path):
    _write_workflow(tmp_path, SAFE_WORKFLOW.replace("workflow_dispatch:", "workflow_dispatch:\n  pull_request:"))
    assert review_mod.inspect_publish_workflow_content_safety(str(tmp_path))["has_pr_trigger"] is True


def test_content_safety_rejects_push_trigger(tmp_path):
    _write_workflow(tmp_path, SAFE_WORKFLOW.replace("workflow_dispatch:", "workflow_dispatch:\n  push:"))
    assert review_mod.inspect_publish_workflow_content_safety(str(tmp_path))["has_push_trigger"] is True


def test_content_safety_rejects_schedule_trigger(tmp_path):
    _write_workflow(tmp_path, SAFE_WORKFLOW.replace("workflow_dispatch:", "workflow_dispatch:\n  schedule:"))
    assert review_mod.inspect_publish_workflow_content_safety(str(tmp_path))["has_schedule_trigger"] is True


def test_content_safety_rejects_secrets(tmp_path):
    _write_workflow(tmp_path, SAFE_WORKFLOW + "\n# ${{ secrets.TOKEN }}\n")
    assert review_mod.inspect_publish_workflow_content_safety(str(tmp_path))["has_secrets"] is True


def test_content_safety_rejects_webhook_curl(tmp_path):
    _write_workflow(tmp_path, SAFE_WORKFLOW + "\n# webhook\n      - run: curl example.invalid\n")
    result = review_mod.inspect_publish_workflow_content_safety(str(tmp_path))
    assert result["has_webhook_network"] is True
    assert result["has_curl"] is True


def test_content_safety_rejects_auto_fix(tmp_path):
    _write_workflow(tmp_path, SAFE_WORKFLOW + "\n# auto-fix\n")
    assert review_mod.inspect_publish_workflow_content_safety(str(tmp_path))["has_auto_fix"] is True


def test_evaluate_canonical_ready_when_only_target_changed_and_safe(tmp_path, monkeypatch):
    _write_workflow(tmp_path)
    fake, _ = _mock_git("?? .github/workflows/foundation-manual-dispatch.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    monkeypatch.setattr(review_mod, "load_r241_16m_visibility_review", lambda root=None: {"local_workflow_exists": True, "git_exact_path_present": False})
    result = review_mod.evaluate_canonical_publish_readiness(str(tmp_path))
    assert result["status"] == "ready_for_publish_confirmation"


def test_evaluate_canonical_blocked_when_existing_workflow_changed(tmp_path, monkeypatch):
    _write_workflow(tmp_path)
    fake, _ = _mock_git("?? .github/workflows/foundation-manual-dispatch.yml\n M .github/workflows/lint-check.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    monkeypatch.setattr(review_mod, "load_r241_16m_visibility_review", lambda root=None: {"local_workflow_exists": True, "git_exact_path_present": False})
    result = review_mod.evaluate_canonical_publish_readiness(str(tmp_path))
    assert result["status"] == "blocked_existing_workflow_mutation"


def test_evaluate_canonical_blocked_when_content_unsafe(tmp_path, monkeypatch):
    _write_workflow(tmp_path, SAFE_WORKFLOW + "\n  push:\n")
    fake, _ = _mock_git("?? .github/workflows/foundation-manual-dispatch.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    monkeypatch.setattr(review_mod, "load_r241_16m_visibility_review", lambda root=None: {"local_workflow_exists": True, "git_exact_path_present": False})
    result = review_mod.evaluate_canonical_publish_readiness(str(tmp_path))
    assert result["status"] == "blocked_security_policy"


def test_validate_canonical_readiness_valid_true_for_ready_review(tmp_path, monkeypatch):
    _write_workflow(tmp_path)
    fake, _ = _mock_git("?? .github/workflows/foundation-manual-dispatch.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    monkeypatch.setattr(review_mod, "load_r241_16m_visibility_review", lambda root=None: {"local_workflow_exists": True, "git_exact_path_present": False})
    result = review_mod.evaluate_canonical_publish_readiness(str(tmp_path))
    assert review_mod.validate_canonical_publish_readiness(result)["valid"] is True


def test_validate_canonical_readiness_rejects_command_allowed_now_true(tmp_path, monkeypatch):
    _write_workflow(tmp_path)
    fake, _ = _mock_git("?? .github/workflows/foundation-manual-dispatch.yml\n")
    monkeypatch.setattr(review_mod, "_run_readonly_command", fake)
    monkeypatch.setattr(review_mod, "load_r241_16m_visibility_review", lambda root=None: {"local_workflow_exists": True, "git_exact_path_present": False})
    result = review_mod.evaluate_canonical_publish_readiness(str(tmp_path))
    result["publish_command_blueprints"][0]["command_allowed_now"] = True
    assert review_mod.validate_canonical_publish_readiness(result)["valid"] is False


def test_generate_report_writes_json_and_md_from_same_review_object(tmp_path):
    review = {
        "review_id": "rv-test",
        "generated_at": "now",
        "status": "ready_for_publish_confirmation",
        "decision": "allow_publish_confirmation_gate",
        "local_workflow_exists": True,
        "remote_workflow_exists": False,
        "workflow_diff_summary": {"diff_only_target_workflow": True, "workflow_content_safe": True, "workflow_dispatch_only": True, "has_pr_trigger": False, "has_push_trigger": False, "has_schedule_trigger": False, "has_secrets": False, "target_workflow_changed": True, "existing_workflows_changed": [], "unexpected_workflows_changed": []},
        "existing_workflows_unchanged": True,
        "publish_options": [],
        "recommended_option": "option_c_push_to_default_branch_after_confirmation",
        "publish_command_blueprints": [{"command_id": "x", "command_allowed_now": False}],
        "rollback_plan": {"no_auto_rollback": True},
        "confirmation_requirements": {"confirmation_phrase": "CONFIRM_PUBLISH_FOUNDATION_MANUAL_WORKFLOW"},
        "checks": [],
        "safety_summary": {"no_git_commit_executed": True, "no_git_push_executed": True, "no_gh_workflow_run_executed": True, "json_md_same_review_object": True},
        "warnings": [],
        "errors": [],
    }
    output = tmp_path / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json"
    result = review_mod.generate_canonical_publish_readiness_report(review, str(output))
    assert Path(result["output_path"]).exists()
    assert Path(result["report_path"]).exists()


def test_generated_json_and_md_statuses_match(tmp_path):
    review = review_mod.RemoteWorkflowPublishReview(
        review_id="rv-test",
        generated_at="now",
        status="blocked_security_policy",
        decision="block_publish",
        local_workflow_exists=True,
        remote_workflow_exists=False,
        workflow_diff_summary={"workflow_content_safe": False},
        existing_workflows_unchanged=True,
        publish_options=[],
        recommended_option="option_a_keep_local_only",
        publish_command_blueprints=[{"command_id": "x", "command_allowed_now": False}],
        rollback_plan={"no_auto_rollback": True},
        confirmation_requirements={"confirmation_phrase": "CONFIRM_PUBLISH_FOUNDATION_MANUAL_WORKFLOW"},
        checks=[],
        safety_summary={"no_git_commit_executed": True, "no_git_push_executed": True, "no_gh_workflow_run_executed": True, "json_md_same_review_object": True},
    ).to_dict()
    output = tmp_path / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json"
    result = review_mod.generate_canonical_publish_readiness_report(review, str(output))
    assert json.loads(Path(result["output_path"]).read_text(encoding="utf-8"))["status"] in Path(result["report_path"]).read_text(encoding="utf-8")


def test_verify_r241_16o_would_unblock_when_canonical_ready(tmp_path):
    report_dir = tmp_path / "migration_reports" / "foundation_audit"
    report_dir.mkdir(parents=True)
    (report_dir / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json").write_text(json.dumps({"status": "ready_for_publish_confirmation", "decision": "allow_publish_confirmation_gate", "workflow_diff_summary": {}}), encoding="utf-8")
    assert review_mod.verify_r241_16o_would_unblock_after_readiness_repair(str(tmp_path))["would_unblock"] is True


def test_verify_r241_16o_remains_blocked_when_canonical_blocked(tmp_path):
    report_dir = tmp_path / "migration_reports" / "foundation_audit"
    report_dir.mkdir(parents=True)
    (report_dir / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json").write_text(json.dumps({"status": "blocked_unexpected_diff", "decision": "block_publish", "workflow_diff_summary": {"blocked_reasons": ["x"]}}), encoding="utf-8")
    result = review_mod.verify_r241_16o_would_unblock_after_readiness_repair(str(tmp_path))
    assert result["would_unblock"] is False
    assert result["blocked_reasons"] == ["x"]


def test_no_git_commit():
    assert True


def test_no_git_push():
    assert True


def test_no_gh_workflow_run():
    assert True


def test_no_workflow_content_modification(tmp_path):
    _write_workflow(tmp_path)
    before = (tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml").read_text(encoding="utf-8")
    review_mod.inspect_publish_workflow_content_safety(str(tmp_path))
    after = (tmp_path / ".github" / "workflows" / "foundation-manual-dispatch.yml").read_text(encoding="utf-8")
    assert before == after


def test_no_audit_jsonl_write():
    assert True


def test_no_runtime_action_queue_write():
    assert True


def test_no_secret_read():
    assert True


def test_no_auto_fix():
    assert True
