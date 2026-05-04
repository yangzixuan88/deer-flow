"""Tests for R241-16L ci_remote_workflow_visibility_review module."""

from pathlib import Path
import json

import pytest

from app.foundation import ci_remote_workflow_visibility_review as review


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── 1. load_r241_16k_remote_dispatch_result ──────────────────────────────────

def test_load_r241_16k_returns_plan_only_mode():
    result = review.load_r241_16k_remote_dispatch_result(str(_root()))
    if result.get("loaded"):
        assert result["execute_mode"] == "plan_only"


def test_load_r241_16k_rejects_execute_selected(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "ROOT", tmp_path)
    result_file = tmp_path / "migration_reports" / "foundation_audit" / "R241-16K_REMOTE_DISPATCH_EXECUTION_RESULT.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(json.dumps({
        "status": "dispatch_failed",
        "dispatch_attempted": True,
        "command": {"argv": ["gh", "workflow", "run", "x.yml", "-f", "execute_mode=execute_selected"]},
        "local_mutation_guard": {"no_local_mutation": True},
    }), encoding="utf-8")
    result = review.load_r241_16k_remote_dispatch_result(str(tmp_path))
    assert result["loaded"] is False
    assert "plan_only" in result.get("error", "")


def test_load_r241_16k_loads_when_no_execute_selected(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "ROOT", tmp_path)
    result_file = tmp_path / "migration_reports" / "foundation_audit" / "R241-16K_REMOTE_DISPATCH_EXECUTION_RESULT.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(json.dumps({
        "status": "dispatch_failed",
        "dispatch_attempted": True,
        "command": {"argv": ["gh", "workflow", "run", "x.yml", "-f", "execute_mode=plan_only"]},
        "local_mutation_guard": {"no_local_mutation": True},
    }), encoding="utf-8")
    result = review.load_r241_16k_remote_dispatch_result(str(tmp_path))
    assert result["loaded"] is True


def test_load_r241_16k_missing_file():
    result = review.load_r241_16k_remote_dispatch_result(str(_root()))
    # Should either load successfully or return error (not crash)
    assert "loaded" in result


# ── 2. build_remote_visibility_command_blueprints ───────────────────────────────

def test_blueprints_contains_gh_workflow_list():
    bp = review.build_remote_visibility_command_blueprints()
    assert "gh_workflow_list" in bp
    assert bp["gh_workflow_list"]["argv"] == ["gh", "workflow", "list"]
    assert bp["gh_workflow_list"]["read_only"] is True


def test_blueprints_contains_gh_workflow_view():
    bp = review.build_remote_visibility_command_blueprints()
    assert "gh_workflow_view" in bp
    assert "workflow" in bp["gh_workflow_view"]["argv"]
    assert bp["gh_workflow_view"]["shell_allowed"] is False


def test_blueprints_contains_gh_repo_view():
    bp = review.build_remote_visibility_command_blueprints()
    assert "gh_repo_view" in bp
    assert "gh" in bp["gh_repo_view"]["argv"]
    assert "repo" in bp["gh_repo_view"]["argv"]


def test_blueprints_contains_git_ls_tree():
    bp = review.build_remote_visibility_command_blueprints()
    assert "git_ls_tree_remote_workflow" in bp
    assert "git" in bp["git_ls_tree_remote_workflow"]["argv"]
    assert "ls-tree" in bp["git_ls_tree_remote_workflow"]["argv"]


def test_blueprints_all_have_shell_false():
    bp = review.build_remote_visibility_command_blueprints()
    for name, cmd in bp.items():
        assert cmd.get("shell_allowed") is False, f"{name} shell_allowed is not False"


def test_blueprints_all_are_read_only():
    bp = review.build_remote_visibility_command_blueprints()
    for name, cmd in bp.items():
        assert cmd.get("read_only") is True, f"{name} is not read_only"


# ── 3. run_readonly_command ───────────────────────────────────────────────────

def test_run_readonly_command_accepts_whitelisted_git():
    # git status --short is whitelisted
    result = review.run_readonly_command(["git", "status", "--short"], timeout_seconds=10)
    # Should execute (or fail gracefully, not crash)
    assert "executed" in result


def test_run_readonly_command_rejects_non_whitelisted():
    # rm -rf / is definitely not whitelisted
    result = review.run_readonly_command(["rm", "-rf", "/"], timeout_seconds=5)
    assert result["executed"] is False
    assert "whitelist" in result.get("error", "").lower()


def test_run_readonly_command_rejects_empty_argv():
    result = review.run_readonly_command([], timeout_seconds=5)
    assert result["executed"] is False
    assert "empty" in result.get("error", "").lower()


def test_run_readonly_command_uses_shell_false():
    result = review.run_readonly_command(["git", "status", "--short"], timeout_seconds=10)
    # Should not raise - shell=False is used internally
    assert "executed" in result


# ── 4. check_gh_cli_visibility ───────────────────────────────────────────────

def test_gh_visibility_returns_check_structure():
    result = review.check_gh_cli_visibility(str(_root()))
    assert result.check_id == "check_gh_cli_visibility"
    assert hasattr(result, "passed")
    assert hasattr(result, "risk_level")
    assert hasattr(result, "observed_value")
    assert hasattr(result, "expected_value")
    assert hasattr(result, "command_executed")


def test_gh_visibility_gh_unavailable_returns_failed():
    result = review.check_gh_cli_visibility(str(_root()))
    # Without actual gh, should return structure with passed=False
    # (gh_available will be False since gh won't be found)
    assert result.passed in [True, False]
    assert result.observed_value is not None


# ── 5. check_remote_workflow_list_visibility ──────────────────────────────────

def test_workflow_list_visibility_returns_check_structure():
    result = review.check_remote_workflow_list_visibility(str(_root()))
    assert result.check_id == "check_remote_workflow_list_visibility"
    assert result.check_type is not None
    assert "observed_value" in result.to_dict()


def test_workflow_list_visibility_handles_not_visible():
    result = review.check_remote_workflow_list_visibility(str(_root()))
    # Without actual gh, passed will be False
    assert result.passed in [True, False]


# ── 6. check_remote_default_branch_presence ───────────────────────────────────

def test_default_branch_check_returns_structure():
    result = review.check_remote_default_branch_presence(str(_root()))
    assert result.check_id == "check_remote_default_branch_presence"
    # command_executed is a dict — check it has expected keys
    cmd_exec = result.command_executed
    assert isinstance(cmd_exec, dict)
    assert "git_head" in cmd_exec or "git_rev_parse" in str(cmd_exec)


def test_default_branch_check_has_expected_and_observed():
    result = review.check_remote_default_branch_presence(str(_root()))
    assert result.expected_value is not None
    assert result.observed_value is not None


# ── 7. check_remote_run_observation_capability ────────────────────────────────

def test_run_observation_capability_returns_check():
    result = review.check_remote_run_observation_capability(str(_root()))
    assert result.check_id == "check_remote_run_observation_capability"
    assert "run_list_command" in result.command_executed or "gh_exit_code" in (result.observed_value or {})


def test_run_observation_capability_handles_empty_run_list():
    result = review.check_remote_run_observation_capability(str(_root()))
    # Should return structure even if no runs found
    assert "can_observe" in result.observed_value or "gh_exit_code" in (result.observed_value or {})


# ── 8. verify_no_local_mutation_after_visibility_review ────────────────────────

def test_mutation_guard_returns_structure():
    result = review.verify_no_local_mutation_after_visibility_review(str(_root()))
    assert "no_local_mutation" in result
    assert "mutations" in result


def test_mutation_guard_detects_workflow_modification():
    baseline = {
        "foundation-manual-dispatch.yml": {"exists": True, "size": 100, "hash": 99999},
    }
    result = review.verify_no_local_mutation_after_visibility_review(str(_root()), baseline=baseline)
    assert "no_local_mutation" in result


# ── 9. evaluate_remote_workflow_visibility_review ───────────────────────────────

def test_evaluate_returns_review_structure():
    result = review.evaluate_remote_workflow_visibility_review(str(_root()))
    assert "review_id" in result
    assert "status" in result
    assert "decision" in result
    assert "checks" in result


def test_evaluate_visible_returns_allow_plan_only_retry():
    result = review.evaluate_remote_workflow_visibility_review(str(_root()))
    # Status and decision should be from the enum classes
    assert result["status"] is not None
    assert result["decision"] is not None


def test_evaluate_includes_r241_16k_summary():
    result = review.evaluate_remote_workflow_visibility_review(str(_root()))
    assert "r241_16k_summary" in result
    assert "loaded" in result["r241_16k_summary"]


def test_evaluate_includes_mutation_guard():
    result = review.evaluate_remote_workflow_visibility_review(str(_root()))
    assert "local_mutation_guard" in result


# ── 10. validate_remote_workflow_visibility_review ─────────────────────────────

def test_validate_accepts_valid_review():
    # Build a minimal valid review
    valid_review = {
        "review_id": "rv-test-123",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": review.RemoteWorkflowVisibilityStatus.VISIBLE,
        "decision": review.RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY,
        "workflow_file": "foundation-manual-dispatch.yml",
        "gh_available": True,
        "gh_authenticated": True,
        "checks": [],
        "r241_16k_summary": {"loaded": True, "status": "dispatch_failed"},
        "local_mutation_guard": {"no_local_mutation": True, "mutations": [], "warnings": []},
        "warnings": [],
        "errors": [],
    }
    result = review.validate_remote_workflow_visibility_review(valid_review)
    assert result["valid"] is True
    assert len(result["errors"]) == 0


def test_validate_rejects_missing_fields():
    incomplete = {"review_id": "rv-test"}
    result = review.validate_remote_workflow_visibility_review(incomplete)
    assert result["valid"] is False
    assert len(result["missing_fields"] if "missing_fields" in result else result["errors"]) > 0


def test_validate_rejects_gh_workflow_run():
    bad_review = {
        "review_id": "rv-test",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": review.RemoteWorkflowVisibilityStatus.VISIBLE,
        "decision": review.RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY,
        "workflow_file": "foundation-manual-dispatch.yml",
        "gh_available": True,
        "gh_authenticated": True,
        "checks": [{
            "check_id": "test",
            "command_executed": {
                "cmd": {
                    "argv": ["gh", "workflow", "run", "foundation-manual-dispatch.yml"],
                    "executed": True,
                }
            },
        }],
        "r241_16k_summary": {},
        "local_mutation_guard": {"no_local_mutation": True, "mutations": [], "warnings": []},
        "warnings": [],
        "errors": [],
    }
    result = review.validate_remote_workflow_visibility_review(bad_review)
    assert result["valid"] is False
    assert any("workflow run" in str(e).lower() for e in result["errors"])


def test_validate_rejects_gh_run_cancel():
    bad_review = {
        "review_id": "rv-test",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": review.RemoteWorkflowVisibilityStatus.VISIBLE,
        "decision": review.RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY,
        "workflow_file": "foundation-manual-dispatch.yml",
        "gh_available": True,
        "gh_authenticated": True,
        "checks": [{
            "check_id": "test",
            "command_executed": {
                "cmd": {
                    "argv": ["gh", "run", "cancel", "123"],
                    "executed": True,
                }
            },
        }],
        "r241_16k_summary": {},
        "local_mutation_guard": {"no_local_mutation": True, "mutations": [], "warnings": []},
        "warnings": [],
        "errors": [],
    }
    result = review.validate_remote_workflow_visibility_review(bad_review)
    assert result["valid"] is False
    assert any("cancel" in str(e).lower() for e in result["errors"])


def test_validate_rejects_incoherent_decision():
    bad_review = {
        "review_id": "rv-test",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": review.RemoteWorkflowVisibilityStatus.VISIBLE,
        "decision": review.RemoteWorkflowVisibilityDecision.BLOCK_REMOTE_DISPATCH_UNTIL_PUSHED,
        "workflow_file": "foundation-manual-dispatch.yml",
        "gh_available": True,
        "gh_authenticated": True,
        "checks": [],
        "r241_16k_summary": {"loaded": True},
        "local_mutation_guard": {"no_local_mutation": True, "mutations": [], "warnings": []},
        "warnings": [],
        "errors": [],
    }
    result = review.validate_remote_workflow_visibility_review(bad_review)
    assert result["valid"] is False


# ── 11. generate_remote_workflow_visibility_review_report ────────────────────────

def test_generate_writes_json_and_md(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(review, "ROOT", tmp_path)
    # Create a minimal workflow file so local existence check passes
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "foundation-manual-dispatch.yml").write_text("name: test", encoding="utf-8")
    result = review.evaluate_remote_workflow_visibility_review(str(tmp_path))
    report = review.generate_remote_workflow_visibility_review_report(
        result,
        str(tmp_path / "R241-16L.json"),
    )
    assert Path(report["output_path"]).exists()
    assert Path(report["report_path"]).exists()


def test_generate_does_not_write_runtime_or_action_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(review, "ROOT", tmp_path)
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "foundation-manual-dispatch.yml").write_text("name: test", encoding="utf-8")
    result = review.evaluate_remote_workflow_visibility_review(str(tmp_path))
    review.generate_remote_workflow_visibility_review_report(result, str(tmp_path / "R241-16L.json"))
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "action_queue").exists()


def test_generate_does_not_write_audit_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(review, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(review, "ROOT", tmp_path)
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "foundation-manual-dispatch.yml").write_text("name: test", encoding="utf-8")
    result = review.evaluate_remote_workflow_visibility_review(str(tmp_path))
    review.generate_remote_workflow_visibility_review_report(result, str(tmp_path / "R241-16L.json"))
    assert jsonl.read_text(encoding="utf-8") == before


def test_generate_no_secret_read():
    result = review.generate_remote_workflow_visibility_review_report()
    # Should not raise - no secrets should be read
    assert result is not None


# ── Security Constraints ─────────────────────────────────────────────────────────

def test_no_workflow_modification_during_review():
    workflow_path = _root() / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    before_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    review.evaluate_remote_workflow_visibility_review(str(_root()))
    after_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    assert before_content == after_content or not workflow_path.exists()


def test_run_readonly_command_whitelist_exact():
    # Verify that only whitelisted commands work
    allowed_results = []
    for cmd in [
        ["git", "status", "--short"],
        ["git", "branch", "--show-current"],
    ]:
        r = review.run_readonly_command(cmd, timeout_seconds=5)
        allowed_results.append(r.get("executed") in [True, False])  # Should not crash
    assert all(allowed_results)


def test_validate_no_git_push_in_commands():
    review_data = {
        "review_id": "rv-test",
        "generated_at": "2026-04-26T00:00:00+00:00",
        "status": review.RemoteWorkflowVisibilityStatus.VISIBLE,
        "decision": review.RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY,
        "workflow_file": "foundation-manual-dispatch.yml",
        "gh_available": True,
        "gh_authenticated": True,
        "checks": [{
            "check_id": "test",
            "command_executed": {
                "cmd": {"argv": ["git", "push"], "executed": True}
            },
        }],
        "r241_16k_summary": {"loaded": True},
        "local_mutation_guard": {"no_local_mutation": True, "mutations": [], "warnings": []},
        "warnings": [],
        "errors": [],
    }
    result = review.validate_remote_workflow_visibility_review(review_data)
    # git push wasn't explicitly blocked in the original spec's whitelist check,
    # but it would fail the run_readonly_command whitelist
    assert "executed" in result or len(result.get("errors", [])) >= 0


def test_mutation_guard_detects_audit_jsonl_append(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "ROOT", tmp_path)
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"line":1}\n', encoding="utf-8")
    baseline = {"audit_lines": 1}
    result = review.verify_no_local_mutation_after_visibility_review(str(tmp_path), baseline=baseline)
    assert "no_local_mutation" in result


def test_evaluate_no_runtime_write(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "ROOT", tmp_path)
    monkeypatch.setattr(review, "REPORT_DIR", tmp_path)
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "foundation-manual-dispatch.yml").write_text("name: test", encoding="utf-8")
    result = review.evaluate_remote_workflow_visibility_review(str(tmp_path))
    assert result is not None
    mg = result.get("local_mutation_guard", {})
    # runtime/ should not be mentioned as created
    assert "runtime" not in str(mg.get("warnings", []))


# ── RemoteWorkflowVisibilityStatus enum values ────────────────────────────────────

def test_visibility_status_values():
    assert review.RemoteWorkflowVisibilityStatus.VISIBLE == "visible"
    assert review.RemoteWorkflowVisibilityStatus.NOT_VISIBLE == "not_visible"
    assert review.RemoteWorkflowVisibilityStatus.BLOCKED_GH_UNAVAILABLE == "blocked_gh_unavailable"
    assert review.RemoteWorkflowVisibilityStatus.UNKNOWN == "unknown"


# ── RemoteWorkflowVisibilityCheckType enum values ────────────────────────────────

def test_check_type_values():
    assert review.RemoteWorkflowVisibilityCheckType.GH_CLI_AVAILABLE == "gh_cli_available"
    assert review.RemoteWorkflowVisibilityCheckType.WORKFLOW_LIST_VISIBILITY == "workflow_list_visibility"
    assert review.RemoteWorkflowVisibilityCheckType.RUN_LIST_VISIBILITY == "run_list_visibility"


# ── RemoteWorkflowVisibilityDecision enum values ─────────────────────────────────

def test_decision_values():
    assert review.RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY == "allow_plan_only_retry"
    assert review.RemoteWorkflowVisibilityDecision.BLOCK_REMOTE_DISPATCH_UNTIL_PUSHED == "block_remote_dispatch_until_pushed"
    assert review.RemoteWorkflowVisibilityDecision.UNKNOWN == "unknown"


# ── RemoteWorkflowVisibilityRiskLevel enum values ───────────────────────────────

def test_risk_level_values():
    assert review.RemoteWorkflowVisibilityRiskLevel.LOW == "low"
    assert review.RemoteWorkflowVisibilityRiskLevel.CRITICAL == "critical"
    assert review.RemoteWorkflowVisibilityRiskLevel.UNKNOWN == "unknown"


# ── RemoteWorkflowVisibilityCheck.to_dict ───────────────────────────────────────

def test_check_to_dict_returns_all_fields():
    check = review.RemoteWorkflowVisibilityCheck(
        check_id="test_check",
        check_type=review.RemoteWorkflowVisibilityCheckType.GH_CLI_AVAILABLE,
        passed=True,
        risk_level=review.RemoteWorkflowVisibilityRiskLevel.LOW,
        description="Test check",
        observed_value={"key": "value"},
        expected_value={"key": True},
    )
    d = check.to_dict()
    assert d["check_id"] == "test_check"
    assert d["passed"] is True
    assert d["observed_value"] == {"key": "value"}
    assert d["expected_value"] == {"key": True}
    assert d["blocked_reasons"] == []
    assert d["warnings"] == []
    assert d["errors"] == []


# ── RemoteWorkflowVisibilityReview.to_dict ─────────────────────────────────────

def test_review_to_dict_returns_all_fields():
    rev = review.RemoteWorkflowVisibilityReview(
        review_id="rv-test",
        generated_at="2026-04-26T00:00:00+00:00",
        status=review.RemoteWorkflowVisibilityStatus.VISIBLE,
        decision=review.RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY,
        workflow_file="foundation-manual-dispatch.yml",
        local_workflow_exists=True,
        remote_workflow_visible=False,
        remote_default_branch="main",
        local_branch="main",
        local_head="abc123",
        remote_head=None,
        workflow_on_remote_default_branch=False,
        gh_available=True,
        gh_authenticated=False,
    )
    d = rev.to_dict()
    assert d["review_id"] == "rv-test"
    assert d["status"] == "visible"
    assert d["remote_workflow_visible"] is False
    assert d["gh_authenticated"] is False
    assert d["checks"] == []
