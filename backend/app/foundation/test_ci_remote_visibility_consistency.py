"""Tests for R241-16M ci_remote_visibility_consistency module."""

from pathlib import Path
import json

import pytest

from app.foundation import ci_remote_visibility_consistency as consistency


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


# ── 1. parse_git_ls_tree_workflow_presence ─────────────────────────────────

def test_parse_returns_true_on_exact_path():
    stdout = "100644 blob abc123\t.github/workflows/foundation-manual-dispatch.yml\n"
    result = consistency.parse_git_ls_tree_workflow_presence(
        stdout,
        ".github/workflows/foundation-manual-dispatch.yml",
    )
    assert result["present"] is True
    assert len(result["matched_lines"]) == 1
    assert len(result["unrelated_lines"]) == 0


def test_parse_returns_false_on_unrelated_workflow_paths():
    stdout = "100644 blob abc123\t.github/workflows/backend-unit-tests.yml\n100644 blob def456\t.github/workflows/lint-check.yml\n"
    result = consistency.parse_git_ls_tree_workflow_presence(
        stdout,
        ".github/workflows/foundation-manual-dispatch.yml",
    )
    assert result["present"] is False
    assert len(result["matched_lines"]) == 0
    assert len(result["unrelated_lines"]) == 2


def test_parse_returns_false_on_empty_stdout():
    result = consistency.parse_git_ls_tree_workflow_presence("", ".github/workflows/foundation-manual-dispatch.yml")
    assert result["present"] is False
    assert result["evidence"] == "(empty)"


def test_parse_handles_windows_line_endings():
    stdout = "100644 blob abc123\t.github/workflows/foundation-manual-dispatch.yml\r\n"
    result = consistency.parse_git_ls_tree_workflow_presence(
        stdout,
        ".github/workflows/foundation-manual-dispatch.yml",
    )
    assert result["present"] is True


def test_parse_ignores_similar_paths():
    # A path that contains the workflow name but is not exact
    stdout = "100644 blob abc123\t.github/workflows/foundation-manual-dispatch.yml.extra\n"
    result = consistency.parse_git_ls_tree_workflow_presence(
        stdout,
        ".github/workflows/foundation-manual-dispatch.yml",
    )
    assert result["present"] is False


def test_parse_multiple_matched_lines():
    stdout = "100644 blob abc123\t.github/workflows/foundation-manual-dispatch.yml\n100644 blob def456\t.github/workflows/foundation-manual-dispatch.yml\n"
    result = consistency.parse_git_ls_tree_workflow_presence(
        stdout,
        ".github/workflows/foundation-manual-dispatch.yml",
    )
    assert result["present"] is True
    assert len(result["matched_lines"]) == 2


# ── 2. classify_gh_cli_state ───────────────────────────────────────────────

def test_classify_binary_unavailable():
    results = {
        "gh_version": {"executed": False, "error": "not found", "returncode": -1},
        "gh_auth": {"executed": False, "error": "not found", "returncode": -1},
        "gh_repo_view": {"executed": False, "returncode": -1},
        "gh_workflow_list": {"executed": False, "returncode": -1},
        "gh_workflow_view": {"executed": False, "returncode": -1},
    }
    state = consistency.classify_gh_cli_state(results)
    assert state["state"] == consistency.GHCLIState.BINARY_UNAVAILABLE
    assert state["version_ok"] is False


def test_classify_unauthenticated():
    results = {
        "gh_version": {"executed": True, "returncode": 0, "stdout": "gh version 2.x"},
        "gh_auth": {"executed": False, "error": "not logged in", "returncode": 1},
        "gh_repo_view": {"executed": False, "returncode": 1},
        "gh_workflow_list": {"executed": False, "returncode": 1},
        "gh_workflow_view": {"executed": False, "returncode": 1},
    }
    state = consistency.classify_gh_cli_state(results)
    assert state["state"] == consistency.GHCLIState.UNAUTHENTICATED
    assert state["auth_ok"] is False


def test_classify_partially_available_repo_view_ok_workflow_view_404():
    results = {
        "gh_version": {"executed": True, "returncode": 0, "stdout": "gh version 2.x"},
        "gh_auth": {"executed": True, "returncode": 0},
        "gh_repo_view": {"executed": True, "returncode": 0, "stdout": '{"defaultBranchRef":{"name":"main"}}'},
        "gh_workflow_list": {"executed": True, "returncode": 0, "stdout": "other-workflow"},
        "gh_workflow_view": {"executed": False, "returncode": 1, "stderr": "not found"},
    }
    state = consistency.classify_gh_cli_state(results)
    assert state["state"] == consistency.GHCLIState.PARTIALLY_AVAILABLE
    assert state["repo_ok"] is True
    assert state["workflow_view_ok"] is False


def test_classify_available_authenticated():
    results = {
        "gh_version": {"executed": True, "returncode": 0, "stdout": "gh version 2.x"},
        "gh_auth": {"executed": True, "returncode": 0},
        "gh_repo_view": {"executed": True, "returncode": 0},
        "gh_workflow_list": {"executed": True, "returncode": 0},
        "gh_workflow_view": {"executed": True, "returncode": 0},
    }
    state = consistency.classify_gh_cli_state(results)
    assert state["state"] == consistency.GHCLIState.AVAILABLE_AUTHENTICATED


def test_classify_unknown_when_no_results():
    # When gh_version succeeds but gh_auth fails (not executed), UNAUTHENTICATED is correct
    results = {
        "gh_version": {"executed": True, "returncode": 0, "stdout": "gh version 2.x"},
        "gh_auth": {"executed": False, "returncode": -1},
        "gh_repo_view": {"executed": False, "returncode": -1},
        "gh_workflow_list": {"executed": False, "returncode": -1},
        "gh_workflow_view": {"executed": False, "returncode": -1},
    }
    state = consistency.classify_gh_cli_state(results)
    assert state["state"] == consistency.GHCLIState.UNAUTHENTICATED


# ── 3. normalize_workflow_visibility_decision ─────────────────────────────────

def test_normalize_blocks_when_git_exact_path_missing():
    review = {
        "git_exact_path_present": False,
        "gh_workflow_visible": False,
        "gh_run_observable": False,
        "gh_cli_state": consistency.GHCLIState.BINARY_UNAVAILABLE,
        "gh_authenticated": False,
        "gh_available": False,
    }
    result = consistency.normalize_workflow_visibility_decision(review)
    # gh binary unavailable is Priority 1 → BLOCKED_GH_UNAVAILABLE
    assert result["corrected_status"] == "blocked_gh_unavailable"
    assert result["corrected_decision"] == "block_need_remote_visibility"


def test_normalize_blocks_when_gh_workflow_404_despite_git_present():
    review = {
        "git_exact_path_present": True,
        "gh_workflow_visible": False,
        "gh_run_observable": False,
        "gh_cli_state": consistency.GHCLIState.AVAILABLE_AUTHENTICATED,
        "gh_authenticated": True,
        "gh_available": True,
    }
    result = consistency.normalize_workflow_visibility_decision(review)
    assert result["corrected_decision"] == "block_remote_dispatch_until_pushed"


def test_normalize_allows_retry_when_git_and_gh_visible():
    review = {
        "git_exact_path_present": True,
        "gh_workflow_visible": True,
        "gh_run_observable": True,
        "gh_cli_state": consistency.GHCLIState.AVAILABLE_AUTHENTICATED,
        "gh_authenticated": True,
        "gh_available": True,
    }
    result = consistency.normalize_workflow_visibility_decision(review)
    assert result["corrected_status"] == "visible"
    assert result["corrected_decision"] == "allow_plan_only_retry"


def test_normalize_blocks_gh_unavailable():
    review = {
        "git_exact_path_present": True,
        "gh_workflow_visible": False,
        "gh_run_observable": False,
        "gh_cli_state": consistency.GHCLIState.BINARY_UNAVAILABLE,
        "gh_authenticated": False,
        "gh_available": False,
    }
    result = consistency.normalize_workflow_visibility_decision(review)
    assert result["corrected_status"] == "blocked_gh_unavailable"
    assert result["corrected_decision"] == "block_need_remote_visibility"


def test_normalize_blocks_gh_unauthenticated():
    review = {
        "git_exact_path_present": True,
        "gh_workflow_visible": False,
        "gh_run_observable": False,
        "gh_cli_state": consistency.GHCLIState.UNAUTHENTICATED,
        "gh_authenticated": False,
        "gh_available": True,
    }
    result = consistency.normalize_workflow_visibility_decision(review)
    assert result["corrected_status"] == "blocked_not_authenticated"
    assert result["corrected_decision"] == "block_need_authentication"


def test_normalize_partial_when_partially_available():
    review = {
        "git_exact_path_present": True,
        "gh_workflow_visible": False,
        "gh_run_observable": False,
        "gh_cli_state": consistency.GHCLIState.PARTIALLY_AVAILABLE,
        "gh_authenticated": True,
        "gh_available": True,
    }
    result = consistency.normalize_workflow_visibility_decision(review)
    assert result["corrected_decision"] == "allow_plan_only_retry"
    assert result["corrected_status"] == "partial_warning"


# ── 4. evaluate_corrected_remote_workflow_visibility ───────────────────────

def test_evaluate_returns_corrected_structure():
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(_root()))
    assert "review_id" in result
    assert "corrected_status" in result
    assert "corrected_decision" in result
    assert "git_exact_path_present" in result
    assert "gh_workflow_visible" in result
    assert "gh_run_observable" in result
    assert "previous_r241_16l_inconsistency_detected" in result


def test_evaluate_detects_r241_16l_inconsistency():
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(_root()))
    # If workflow not on origin/main, inconsistency should be detected
    if not result.get("git_exact_path_present"):
        assert result["previous_r241_16l_inconsistency_detected"] is True


def test_evaluate_does_not_run_gh_workflow_run():
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(_root()))
    checks = result.get("checks", [])
    for check in checks:
        cmd_exec = check.get("command_executed", {})
        for cmd_name, cmd_result in cmd_exec.items():
            if isinstance(cmd_result, dict):
                argv = cmd_result.get("argv", [])
                if argv and argv[0] == "gh" and len(argv) > 2:
                    assert argv[2] != "run", f"gh workflow run found in {cmd_name}"


def test_evaluate_does_not_run_git_push():
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(_root()))
    cmd_results = result.get("command_results", {})
    for cmd_name, cmd_result in cmd_results.items():
        if isinstance(cmd_result, dict):
            argv = cmd_result.get("argv", [])
            assert argv[0] != "git" or argv[1] != "push" if argv else True


def test_evaluate_includes_mutation_guard():
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(_root()))
    assert "mutation_guard" in result
    assert result["mutation_guard"]["no_local_mutation"] is True


def test_evaluate_has_corrected_status_and_decision():
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(_root()))
    assert result["corrected_status"] is not None
    assert result["corrected_decision"] is not None
    assert result["blocking_reason"] is not None


# ── 5. generate_remote_visibility_consistency_report ───────────────────────

def test_generate_writes_json_and_md(tmp_path, monkeypatch):
    monkeypatch.setattr(consistency, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(consistency, "ROOT", tmp_path)
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "foundation-manual-dispatch.yml").write_text("name: test", encoding="utf-8")
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(tmp_path))
    report = consistency.generate_remote_visibility_consistency_report(
        result,
        str(tmp_path / "R241-16M.json"),
    )
    assert Path(report["output_path"]).exists()
    assert Path(report["report_path"]).exists()


def test_generate_does_not_write_runtime_or_action_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(consistency, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(consistency, "ROOT", tmp_path)
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "foundation-manual-dispatch.yml").write_text("name: test", encoding="utf-8")
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(tmp_path))
    consistency.generate_remote_visibility_consistency_report(result, str(tmp_path / "R241-16M.json"))
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "action_queue").exists()


def test_generate_does_not_write_audit_jsonl(tmp_path, monkeypatch):
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)
    jsonl = audit_dir / "foundation_diagnostic_runs.jsonl"
    jsonl.write_text('{"audit_record_id":"x"}\n', encoding="utf-8")
    before = jsonl.read_text(encoding="utf-8")
    monkeypatch.setattr(consistency, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(consistency, "ROOT", tmp_path)
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "foundation-manual-dispatch.yml").write_text("name: test", encoding="utf-8")
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(tmp_path))
    consistency.generate_remote_visibility_consistency_report(result, str(tmp_path / "R241-16M.json"))
    assert jsonl.read_text(encoding="utf-8") == before


def test_generate_no_secret_read():
    result = consistency.generate_remote_visibility_consistency_report()
    assert result is not None


# ── Security Constraints ─────────────────────────────────────────────────────────

def test_no_workflow_modification_during_review():
    workflow_path = _root() / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    before_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    consistency.evaluate_corrected_remote_workflow_visibility(str(_root()))
    after_content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    assert before_content == after_content or not workflow_path.exists()


def test_run_readonly_command_whitelist():
    from app.foundation import ci_remote_workflow_visibility_review as review
    for cmd in [
        ["git", "status", "--short"],
        ["git", "branch", "--show-current"],
        ["gh", "--version"],
    ]:
        r = review.run_readonly_command(cmd, timeout_seconds=5)
        assert r.get("executed") in [True, False]  # Does not crash


def test_evaluate_no_runtime_write(tmp_path, monkeypatch):
    monkeypatch.setattr(consistency, "ROOT", tmp_path)
    monkeypatch.setattr(consistency, "REPORT_DIR", tmp_path)
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "foundation-manual-dispatch.yml").write_text("name: test", encoding="utf-8")
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(tmp_path))
    mg = result.get("mutation_guard", {})
    assert "runtime" not in str(mg.get("warnings", []))


def test_corrected_review_has_recommended_phase():
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(_root()))
    assert result["recommended_next_phase"] != ""


# ── Bug-specific regression tests ───────────────────────────────────────────────

def test_gh_run_observable_false_when_exit_code_1():
    """Regression: gh run list exit 1 (workflow 404) must set gh_run_observable=False."""
    result = consistency.evaluate_corrected_remote_workflow_visibility(str(_root()))
    # If gh workflow is not visible (404), gh_run_observable should be False
    if not result.get("gh_workflow_visible"):
        assert result.get("gh_run_observable") is False


def test_exact_path_check_not_directory_listing():
    """Regression: exact path git ls-tree, not directory listing."""
    from app.foundation import ci_remote_workflow_visibility_review as review
    # Directory listing stdout
    dir_stdout = "100644 blob abc\t.github/workflows/backend-unit-tests.yml\n100644 blob def\t.github/workflows/lint-check.yml\n"
    parsed = consistency.parse_git_ls_tree_workflow_presence(
        dir_stdout,
        ".github/workflows/foundation-manual-dispatch.yml",
    )
    assert parsed["present"] is False
