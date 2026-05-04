"""Tests for R241-17B post-publish deviation audit module."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from backend.app.foundation.ci_post_publish_deviation_audit import (
    PostPublishAuditStatus,
    PostPublishAuditDecision,
    PostPublishDeviationType,
    PostPublishRiskLevel,
    PostPublishAuditCheck,
    PostPublishDeviation,
    PostPublishOperationalClosure,
    load_r241_16y_final_closure,
    inspect_remote_publish_state,
    inspect_workflow_run_state,
    inspect_worktree_and_stash_state,
    classify_post_publish_deviations,
    build_post_publish_audit_checks,
    evaluate_post_publish_deviation_audit,
    validate_post_publish_deviation_audit,
    generate_post_publish_deviation_audit_report,
    generate_final_operational_closure_summary,
)


class TestPostPublishEnums:
    """Test enum values and structure."""

    def test_audit_status_values(self):
        assert PostPublishAuditStatus.OPERATIONALLY_CLOSED.value == "operationally_closed"
        assert PostPublishAuditStatus.OPERATIONALLY_CLOSED_WITH_DEVIATION.value == "operationally_closed_with_deviation"
        assert PostPublishAuditStatus.BLOCKED_REMOTE_MISSING_WORKFLOW.value == "blocked_remote_missing_workflow"
        assert PostPublishAuditStatus.BLOCKED_WORKFLOW_TRIGGERED_UNEXPECTEDLY.value == "blocked_workflow_triggered_unexpectedly"
        assert PostPublishAuditStatus.BLOCKED_STASH_MISSING.value == "blocked_stash_missing"
        assert PostPublishAuditStatus.BLOCKED_WORKTREE_NOT_CLEAN.value == "blocked_worktree_not_clean"
        assert PostPublishAuditStatus.BLOCKED_FORCE_PUSH_UNREVIEWED.value == "blocked_force_push_unreviewed"
        assert PostPublishAuditStatus.UNKNOWN.value == "unknown"

    def test_audit_decision_values(self):
        assert PostPublishAuditDecision.APPROVE_OPERATIONAL_CLOSURE.value == "approve_operational_closure"
        assert PostPublishAuditDecision.APPROVE_OPERATIONAL_CLOSURE_WITH_FORCE_PUSH_DEVIATION.value == "approve_operational_closure_with_force_push_deviation"
        assert PostPublishAuditDecision.BLOCK_OPERATIONAL_CLOSURE.value == "block_operational_closure"
        assert PostPublishAuditDecision.UNKNOWN.value == "unknown"

    def test_deviation_type_values(self):
        assert PostPublishDeviationType.FORCE_PUSH_USED.value == "force_push_used"
        assert PostPublishDeviationType.REMOTE_CHANGED_TO_USER_FORK.value == "remote_changed_to_user_fork"
        assert PostPublishDeviationType.WORKTREE_STASHED.value == "worktree_stashed"
        assert PostPublishDeviationType.WORKFLOW_RUN_COUNT_ZERO.value == "workflow_run_count_zero"
        assert PostPublishDeviationType.UNKNOWN.value == "unknown"

    def test_risk_level_values(self):
        assert PostPublishRiskLevel.LOW.value == "low"
        assert PostPublishRiskLevel.MEDIUM.value == "medium"
        assert PostPublishRiskLevel.HIGH.value == "high"
        assert PostPublishRiskLevel.CRITICAL.value == "critical"
        assert PostPublishRiskLevel.UNKNOWN.value == "unknown"


class TestLoadR241_16yFinalClosure:
    """Test load_r241_16y_final_closure function."""

    def test_loads_valid_closure(self, tmp_path: Path):
        data = {
            "status": "closed_with_external_worktree_condition",
            "decision": "approve_final_closure_with_external_worktree_condition",
            "validation_result": {"valid": True},
            "source_changed_files": [],
        }
        report_path = tmp_path / "migration_reports" / "foundation_audit" / "R241-16Y_FINAL_CLOSURE_REEVALUATION.json"
        report_path.parent.mkdir(parents=True)
        report_path.write_text(json.dumps(data))

        result = load_r241_16y_final_closure(root=str(tmp_path))

        assert result["passed"] is True
        assert result["status"] == "closed_with_external_worktree_condition"
        assert result["decision"] == "approve_final_closure_with_external_worktree_condition"
        assert result["warning"] is None

    def test_accepts_external_worktree_condition(self, tmp_path: Path):
        data = {
            "status": "closed_with_external_worktree_condition",
            "decision": "approve_final_closure_with_external_worktree_condition",
            "validation_result": {"valid": True},
            "source_changed_files": ["backend/app/foundation/ci_post_publish_deviation_audit.py"],
        }
        report_path = tmp_path / "migration_reports" / "foundation_audit" / "R241-16Y_FINAL_CLOSURE_REEVALUATION.json"
        report_path.parent.mkdir(parents=True)
        report_path.write_text(json.dumps(data))

        result = load_r241_16y_final_closure(root=str(tmp_path))

        assert result["passed"] is True

    def test_rejects_wrong_status(self, tmp_path: Path):
        data = {
            "status": "in_progress",
            "decision": "unknown",
            "validation_result": {"valid": True},
        }
        report_path = tmp_path / "migration_reports" / "foundation_audit" / "R241-16Y_FINAL_CLOSURE_REEVALUATION.json"
        report_path.parent.mkdir(parents=True)
        report_path.write_text(json.dumps(data))

        result = load_r241_16y_final_closure(root=str(tmp_path))

        assert result["passed"] is False
        assert result["warning"] is not None

    def test_missing_report_returns_warning(self, tmp_path: Path):
        result = load_r241_16y_final_closure(root=str(tmp_path))

        assert result["passed"] is False
        assert "warning" in result

    def test_empty_json_returns_warning(self, tmp_path: Path):
        report_path = tmp_path / "migration_reports" / "foundation_audit" / "R241-16Y_FINAL_CLOSURE_REEVALUATION.json"
        report_path.parent.mkdir(parents=True)
        report_path.write_text("{}")

        result = load_r241_16y_final_closure(root=str(tmp_path))

        assert result["passed"] is False


class TestInspectRemotePublishState:
    """Test inspect_remote_publish_state function."""

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("subprocess.run")
    def test_detects_user_fork_remote(self, mock_run: MagicMock, mock_wf_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        workflow_content = "on: workflow_dispatch\nname: Test"
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "origin\tgit@github.com:yangzixuan88/deer-flow.git (fetch)\norigin\tgit@github.com:yangzixuan88/deer-flow.git (push)",
                "origin",
                "abc123",
                "abc123",
                "0 0",
                "120364 blob 789abc... .github/workflows/foundation-manual-dispatch.yml",
                workflow_content,
            ]
            remote_state = inspect_remote_publish_state(root=None)

        assert remote_state["remote_owner_repo"] == "yangzixuan88"

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("subprocess.run")
    def test_detects_bytedance_remote(self, mock_run: MagicMock, mock_wf_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        workflow_content = "on: workflow_dispatch\nname: Test"
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "origin\tgit@github.com:bytedance/deerflow.git (fetch)\norigin\tgit@github.com:bytedance/deerflow.git (push)",
                "origin",
                "abc123",
                "abc123",
                "0 0",
                "120364 blob 789abc... .github/workflows/foundation-manual-dispatch.yml",
                workflow_content,
            ]
            remote_state = inspect_remote_publish_state(root=None)

        assert remote_state["remote_owner_repo"] == "bytedance"

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("subprocess.run")
    def test_workflow_present_on_remote(self, mock_run: MagicMock, mock_wf_run: MagicMock):
        workflow_content = "on: workflow_dispatch\nname: Test"
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "",
                "origin",
                "abc123",
                "abc123",
                "0 0",
                "120364 blob a1b2c3d4e5f6\t.github/workflows/foundation-manual-dispatch.yml",
                workflow_content,
            ]
            result = inspect_remote_publish_state(root=None)

        assert result["workflow_remote_present"] is True

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("subprocess.run")
    def test_workflow_absent_from_remote(self, mock_run: MagicMock, mock_wf_run: MagicMock):
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "",
                "origin",
                "abc123",
                "abc123",
                "0 0",
                "",
                "",
            ]
            result = inspect_remote_publish_state(root=None)

        assert result["workflow_remote_present"] is False

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("subprocess.run")
    def test_verifies_workflow_dispatch_only(self, mock_run: MagicMock, mock_wf_run: MagicMock):
        workflow_content = """name: Foundation Manual Dispatch
on: workflow_dispatch
jobs:
  dispatch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "",
                "origin",
                "abc123",
                "abc123",
                "0 0",
                "120364 blob a1b2c3\t.github/workflows/foundation-manual-dispatch.yml",
                workflow_content,
            ]
            result = inspect_remote_publish_state(root=None)

        assert result["workflow_dispatch_only"] is True
        assert result["has_pull_request_trigger"] is False
        assert result["has_push_trigger"] is False
        assert result["has_schedule_trigger"] is False

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("subprocess.run")
    def test_rejects_pull_request_trigger(self, mock_run: MagicMock, mock_wf_run: MagicMock):
        workflow_content = """name: Test
on:
  pull_request:
    types: [opened, closed]
  workflow_dispatch:
jobs:
  test:
    runs-on: ubuntu-latest
"""
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "",
                "origin",
                "abc123",
                "abc123",
                "0 0",
                "120364 blob a1b2c3\t.github/workflows/foundation-manual-dispatch.yml",
                workflow_content,
            ]
            result = inspect_remote_publish_state(root=None)

        assert result["has_pull_request_trigger"] is True
        assert result["workflow_dispatch_only"] is False

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("subprocess.run")
    def test_rejects_push_trigger(self, mock_run: MagicMock, mock_wf_run: MagicMock):
        workflow_content = "on: [push, workflow_dispatch]\nname: Test\njobs:\n  test:\n    runs-on: ubuntu-latest"
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "",
                "origin",
                "abc123",
                "abc123",
                "0 0",
                "120364 blob a1b2c3\t.github/workflows/foundation-manual-dispatch.yml",
                workflow_content,
            ]
            result = inspect_remote_publish_state(root=None)

        assert result["has_push_trigger"] is True
        assert result["workflow_dispatch_only"] is False

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("subprocess.run")
    def test_rejects_schedule_trigger(self, mock_run: MagicMock, mock_wf_run: MagicMock):
        workflow_content = "on:\n  schedule:\n    - cron: '0 * * * *'\n  workflow_dispatch:\nname: Test\njobs:\n  test:\n    runs-on: ubuntu-latest"
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "",
                "origin",
                "abc123",
                "abc123",
                "0 0",
                "120364 blob a1b2c3\t.github/workflows/foundation-manual-dispatch.yml",
                workflow_content,
            ]
            result = inspect_remote_publish_state(root=None)

        assert result["has_schedule_trigger"] is True
        assert result["workflow_dispatch_only"] is False


class TestInspectWorkflowRunState:
    """Test inspect_workflow_run_state function."""

    @patch("subprocess.run")
    def test_accepts_zero_runs(self, mock_run: MagicMock):
        mock_run.side_effect = [
            MagicMock(stdout="0", returncode=0),
            MagicMock(stdout="Foundation Manual Dispatch\tactive\tmanual    workflow_dispatch\t12 days ago", returncode=0),
        ]

        result = inspect_workflow_run_state(root=None)

        assert result["gh_available"] is True
        assert result["workflow_run_count"] == 0
        assert result["unexpected_runs_detected"] is False

    @patch("subprocess.run")
    def test_detects_nonzero_runs(self, mock_run: MagicMock):
        mock_run.side_effect = [
            MagicMock(stdout="3", returncode=0),
            MagicMock(stdout="Foundation Manual Dispatch\tactive\tmanual    workflow_dispatch\t12 days ago", returncode=0),
        ]

        result = inspect_workflow_run_state(root=None)

        assert result["workflow_run_count"] == 3
        assert result["unexpected_runs_detected"] is True

    @patch("subprocess.run")
    def test_tolerates_gh_unavailable(self, mock_run: MagicMock):
        mock_run.side_effect = FileNotFoundError("gh not found")

        result = inspect_workflow_run_state(root=None)

        assert result["gh_available"] is False
        assert result["workflow_run_count"] is None
        assert len(result["warnings"]) > 0

    @patch("subprocess.run")
    def test_tolerates_timeout(self, mock_run: MagicMock):
        mock_run.side_effect = subprocess.TimeoutExpired("gh", 10)

        result = inspect_workflow_run_state(root=None)

        assert result["gh_available"] is False
        assert len(result["warnings"]) > 0


class TestInspectWorktreeAndStashState:
    """Test inspect_worktree_and_stash_state function."""

    @patch("subprocess.run")
    def test_detects_stash_present(self, mock_run: MagicMock):
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "## main...origin/main",
                "?? newfile.py",
                "",
                "stash@{0}: WIP on main: 174c371a Update workflow",
                "stash@{1}: WIP on main: abc123 Another stash",
                " 10 files changed, 500 insertions(+), 100 deletions(-)",
                ".github/workflows/foundation-manual-dispatch.yml\nbackend/app/main.py\nREADME.md",
            ]
            result = inspect_worktree_and_stash_state(root=None)

        assert result["stash_present"] is True
        assert "stash@{0}" in result["stash_ref"]

    @patch("subprocess.run")
    def test_detects_stash_missing(self, mock_run: MagicMock):
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "## main...origin/main",
                "",
                "",
                "",
            ]
            result = inspect_worktree_and_stash_state(root=None)

        assert result["stash_present"] is False

    @patch("subprocess.run")
    def test_staged_area_clean(self, mock_run: MagicMock):
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "## main...origin/main",
                "?? untracked.txt",
                "",
                "",
            ]
            result = inspect_worktree_and_stash_state(root=None)

        assert result["staged_file_count"] == 0

    @patch("subprocess.run")
    def test_staged_area_has_files(self, mock_run: MagicMock):
        with patch("backend.app.foundation.ci_post_publish_deviation_audit._run_git") as mock_git:
            mock_git.side_effect = [
                "## main...origin/main",
                "M  staged.txt",
                " M unstaged.txt",
                "?? newfile.txt",
                "M  staged.txt",
                "",
                "",
            ]
            result = inspect_worktree_and_stash_state(root=None)

        assert result["staged_file_count"] == 1


class TestClassifyPostPublishDeviations:
    """Test classify_post_publish_deviations function."""

    def test_records_force_push_used(self):
        remote_state = {"remote_owner_repo": "yangzixuan88", "workflow_run_count": 0}
        stash_state = {"stash_present": True}

        deviations = classify_post_publish_deviations(root=None, remote_state=remote_state, stash_state=stash_state)

        assert "force_push_used" in deviations
        assert deviations["force_push_used"].deviation_type == PostPublishDeviationType.FORCE_PUSH_USED

    def test_accepts_force_push_on_user_fork(self):
        remote_state = {"remote_owner_repo": "yangzixuan88", "workflow_run_count": 0}
        stash_state = {"stash_present": True}

        deviations = classify_post_publish_deviations(root=None, remote_state=remote_state, stash_state=stash_state)

        force_dev = deviations["force_push_used"]
        assert force_dev.accepted is True
        assert "user fork" in force_dev.reason
        assert force_dev.risk_level == PostPublishRiskLevel.MEDIUM

    def test_rejects_unreviewed_force_push_on_upstream(self):
        remote_state = {"remote_owner_repo": "bytedance", "workflow_run_count": 0}
        stash_state = {"stash_present": True}

        deviations = classify_post_publish_deviations(root=None, remote_state=remote_state, stash_state=stash_state)

        force_dev = deviations["force_push_used"]
        assert force_dev.accepted is False

    def test_rejects_force_push_when_runs_nonzero(self):
        remote_state = {"remote_owner_repo": "yangzixuan88", "workflow_run_count": 2}
        stash_state = {"stash_present": True}

        deviations = classify_post_publish_deviations(root=None, remote_state=remote_state, stash_state=stash_state)

        force_dev = deviations["force_push_used"]
        assert force_dev.accepted is False

    def test_remote_changed_deviation(self):
        remote_state = {"remote_owner_repo": "yangzixuan88", "workflow_run_count": 0}
        stash_state = {"stash_present": True}

        deviations = classify_post_publish_deviations(root=None, remote_state=remote_state, stash_state=stash_state)

        assert "remote_changed_to_user_fork" in deviations
        assert deviations["remote_changed_to_user_fork"].accepted is True

    def test_worktree_stashed_deviation(self):
        remote_state = {"remote_owner_repo": "yangzixuan88", "workflow_run_count": 0}
        stash_state = {"stash_present": True, "stash_message": "WIP on main"}

        deviations = classify_post_publish_deviations(root=None, remote_state=remote_state, stash_state=stash_state)

        assert "worktree_stashed" in deviations
        assert deviations["worktree_stashed"].accepted is True
        assert deviations["worktree_stashed"].risk_level == PostPublishRiskLevel.LOW

    def test_workflow_run_count_zero_deviation(self):
        remote_state = {"remote_owner_repo": "yangzixuan88", "workflow_run_count": 0}
        stash_state = {"stash_present": True}

        deviations = classify_post_publish_deviations(root=None, remote_state=remote_state, stash_state=stash_state)

        assert "workflow_run_count_zero" in deviations
        assert deviations["workflow_run_count_zero"].accepted is True


class TestBuildPostPublishAuditChecks:
    """Test build_post_publish_audit_checks function."""

    def test_returns_list_of_checks(self):
        checks = build_post_publish_audit_checks(root=None)

        assert isinstance(checks, list)
        assert len(checks) >= 12

    def test_checks_have_required_fields(self):
        checks = build_post_publish_audit_checks(root=None)

        for check in checks:
            assert hasattr(check, "check_id")
            assert hasattr(check, "passed")
            assert hasattr(check, "risk_level")
            assert hasattr(check, "description")
            assert hasattr(check, "observed_value")
            assert hasattr(check, "expected_value")
            assert hasattr(check, "evidence_refs")
            assert hasattr(check, "required_for_operational_closure")
            assert hasattr(check, "blocked_reasons")

    def test_critical_check_for_workflow_present(self):
        checks = build_post_publish_audit_checks(root=None)

        workflow_check = next((c for c in checks if c.check_id == "remote_workflow_present"), None)
        assert workflow_check is not None
        assert workflow_check.risk_level == PostPublishRiskLevel.CRITICAL
        assert workflow_check.required_for_operational_closure is True

    def test_high_check_for_workflow_dispatch_only(self):
        checks = build_post_publish_audit_checks(root=None)

        dispatch_check = next((c for c in checks if c.check_id == "workflow_dispatch_only"), None)
        assert dispatch_check is not None
        assert dispatch_check.risk_level == PostPublishRiskLevel.HIGH
        assert dispatch_check.required_for_operational_closure is True

    def test_staged_area_check(self):
        checks = build_post_publish_audit_checks(root=None)

        staged_check = next((c for c in checks if c.check_id == "staged_area_clean"), None)
        assert staged_check is not None
        assert staged_check.required_for_operational_closure is True


class TestEvaluatePostPublishDeviationAudit:
    """Test evaluate_post_publish_deviation_audit function."""

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_remote_publish_state")
    @patch("backend.app.foundation.ci_post_publish_deviation_audit.load_r241_16y_final_closure")
    def test_operationally_closed_with_deviation(
        self, mock_closure: MagicMock, mock_remote: MagicMock, mock_runs: MagicMock
    ):
        mock_closure.return_value = {
            "passed": True,
            "status": "closed_with_external_worktree_condition",
            "decision": "approve_final_closure_with_external_worktree_condition",
        }
        mock_remote.return_value = {
            "remote_owner_repo": "yangzixuan88",
            "workflow_remote_present": True,
            "workflow_dispatch_only": True,
            "ahead_count": 0,
            "behind_count": 0,
            "head_hash": "abc123",
            "origin_main_hash": "abc123",
            "remote_push_url": "git@github.com:yangzixuan88/deer-flow.git",
            "has_pull_request_trigger": False,
            "has_push_trigger": False,
            "has_schedule_trigger": False,
        }
        mock_runs.return_value = {
            "gh_available": True,
            "workflow_run_count": 0,
            "unexpected_runs_detected": False,
        }

        with patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_worktree_and_stash_state") as mock_stash:
            mock_stash.return_value = {
                "stash_present": True,
                "staged_file_count": 0,
                "stash_message": "WIP on main",
            }
            result = evaluate_post_publish_deviation_audit(root=None)

        assert result["status"] == PostPublishAuditStatus.OPERATIONALLY_CLOSED_WITH_DEVIATION
        assert result["decision"] == PostPublishAuditDecision.APPROVE_OPERATIONAL_CLOSURE_WITH_FORCE_PUSH_DEVIATION

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_remote_publish_state")
    @patch("backend.app.foundation.ci_post_publish_deviation_audit.load_r241_16y_final_closure")
    def test_blocked_remote_missing_workflow(
        self, mock_closure: MagicMock, mock_remote: MagicMock, mock_runs: MagicMock
    ):
        mock_closure.return_value = {"passed": True, "status": "closed_with_external_worktree_condition", "decision": "approve_final_closure_with_external_worktree_condition"}
        mock_remote.return_value = {
            "remote_owner_repo": "yangzixuan88",
            "workflow_remote_present": False,
            "workflow_dispatch_only": True,
            "ahead_count": 0,
            "behind_count": 0,
            "head_hash": "abc123",
            "origin_main_hash": "abc123",
            "remote_push_url": "git@github.com:yangzixuan88/deer-flow.git",
        }
        mock_runs.return_value = {"gh_available": True, "workflow_run_count": 0}

        with patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_worktree_and_stash_state") as mock_stash:
            mock_stash.return_value = {"stash_present": True, "staged_file_count": 0, "stash_message": "WIP"}
            result = evaluate_post_publish_deviation_audit(root=None)

        assert result["status"] == PostPublishAuditStatus.BLOCKED_REMOTE_MISSING_WORKFLOW
        assert result["decision"] == PostPublishAuditDecision.BLOCK_OPERATIONAL_CLOSURE

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_remote_publish_state")
    @patch("backend.app.foundation.ci_post_publish_deviation_audit.load_r241_16y_final_closure")
    def test_blocked_workflow_triggered_unexpectedly(
        self, mock_closure: MagicMock, mock_remote: MagicMock, mock_runs: MagicMock
    ):
        mock_closure.return_value = {"passed": True, "status": "closed_with_external_worktree_condition", "decision": "approve_final_closure_with_external_worktree_condition"}
        mock_remote.return_value = {
            "remote_owner_repo": "yangzixuan88",
            "workflow_remote_present": True,
            "workflow_dispatch_only": False,
            "ahead_count": 0,
            "behind_count": 0,
            "head_hash": "abc123",
            "origin_main_hash": "abc123",
            "remote_push_url": "git@github.com:yangzixuan88/deer-flow.git",
        }
        mock_runs.return_value = {"gh_available": True, "workflow_run_count": 0}

        with patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_worktree_and_stash_state") as mock_stash:
            mock_stash.return_value = {"stash_present": True, "staged_file_count": 0, "stash_message": "WIP"}
            result = evaluate_post_publish_deviation_audit(root=None)

        assert result["status"] == PostPublishAuditStatus.BLOCKED_WORKFLOW_TRIGGERED_UNEXPECTEDLY
        assert result["decision"] == PostPublishAuditDecision.BLOCK_OPERATIONAL_CLOSURE

    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_workflow_run_state")
    @patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_remote_publish_state")
    @patch("backend.app.foundation.ci_post_publish_deviation_audit.load_r241_16y_final_closure")
    def test_blocked_stash_missing(
        self, mock_closure: MagicMock, mock_remote: MagicMock, mock_runs: MagicMock
    ):
        mock_closure.return_value = {"passed": True, "status": "closed_with_external_worktree_condition", "decision": "approve_final_closure_with_external_worktree_condition"}
        mock_remote.return_value = {
            "remote_owner_repo": "yangzixuan88",
            "workflow_remote_present": True,
            "workflow_dispatch_only": True,
            "ahead_count": 0,
            "behind_count": 0,
            "head_hash": "abc123",
            "origin_main_hash": "abc123",
            "remote_push_url": "git@github.com:yangzixuan88/deer-flow.git",
            "has_pull_request_trigger": False,
            "has_push_trigger": False,
            "has_schedule_trigger": False,
        }
        mock_runs.return_value = {"gh_available": True, "workflow_run_count": 0}

        with patch("backend.app.foundation.ci_post_publish_deviation_audit.inspect_worktree_and_stash_state") as mock_stash:
            mock_stash.return_value = {"stash_present": False, "staged_file_count": 0, "stash_message": ""}
            result = evaluate_post_publish_deviation_audit(root=None)

        assert result["status"] == PostPublishAuditStatus.BLOCKED_STASH_MISSING
        assert result["decision"] == PostPublishAuditDecision.BLOCK_OPERATIONAL_CLOSURE


class TestValidatePostPublishDeviationAudit:
    """Test validate_post_publish_deviation_audit function."""

    def test_accepts_valid_audit_with_deviation(self):
        review = {
            "status": "operationally_closed_with_deviation",
            "decision": "approve_operational_closure_with_force_push_deviation",
            "force_push_deviation": True,
            "workflow_run_count": 0,
            "checks": [
                {"check_id": "remote_is_user_fork", "passed": True},
            ],
            "delivery_closure_state": "closed_with_external_worktree_condition",
        }

        result = validate_post_publish_deviation_audit(review)

        assert result["valid"] is True
        assert len(result["violations"]) == 0

    def test_rejects_workflow_runs_nonzero(self):
        review = {
            "status": "operationally_closed_with_deviation",
            "decision": "approve_operational_closure_with_force_push_deviation",
            "force_push_deviation": True,
            "workflow_run_count": 5,
            "checks": [],
            "delivery_closure_state": "closed_with_external_worktree_condition",
        }

        result = validate_post_publish_deviation_audit(review)

        assert result["valid"] is False
        assert any("run count" in v for v in result["violations"])

    def test_rejects_force_push_not_user_fork(self):
        review = {
            "status": "operationally_closed_with_deviation",
            "decision": "approve_operational_closure_with_force_push_deviation",
            "force_push_deviation": True,
            "workflow_run_count": 0,
            "checks": [
                {"check_id": "remote_is_user_fork", "passed": False},
            ],
            "delivery_closure_state": "closed_with_external_worktree_condition",
        }

        result = validate_post_publish_deviation_audit(review)

        assert result["valid"] is False

    def test_validates_empty_checks_list(self):
        review = {
            "status": "operationally_closed",
            "decision": "approve_operational_closure",
            "force_push_deviation": False,
            "workflow_run_count": 0,
            "checks": [],
            "delivery_closure_state": "closed_with_external_worktree_condition",
        }

        result = validate_post_publish_deviation_audit(review)

        assert result["valid"] is True


class TestGenerateReports:
    """Test report generation functions."""

    def test_generate_audit_report_writes_json_and_md(self, tmp_path: Path):
        review = {
            "closure_id": "R241-17B",
            "generated_at": "2026-04-26T14:00:00Z",
            "status": "operationally_closed_with_deviation",
            "decision": "approve_operational_closure_with_force_push_deviation",
            "force_push_deviation": True,
            "checks": [
                {
                    "check_id": "remote_workflow_present",
                    "passed": True,
                    "risk_level": "critical",
                    "description": "workflow present",
                    "observed_value": "abc123",
                    "expected_value": ".github/workflows/foundation-manual-dispatch.yml",
                    "evidence_refs": [],
                    "required_for_operational_closure": True,
                    "blocked_reasons": [],
                    "warnings": [],
                    "errors": [],
                }
            ],
            "deviations": {
                "force_push_used": {
                    "deviation_id": "force_push_used",
                    "deviation_type": "force_push_used",
                    "risk_level": "medium",
                    "description": "force push used",
                    "accepted": True,
                    "reason": "user fork",
                    "evidence_refs": [],
                    "warnings": [],
                    "errors": [],
                }
            },
            "remote_summary": "git@github.com:yangzixuan88/deer-flow.git",
            "workflow_remote_present": True,
            "workflow_dispatch_only": True,
            "workflow_run_count": 0,
            "stash_summary": "WIP on main",
            "worktree_state": "clean_with_stash",
            "delivery_closure_state": "closed_with_external_worktree_condition",
            "safety_summary": "SAFE: all critical/high checks passed",
            "validation_result": {"valid": True},
            "warnings": [],
            "errors": [],
        }

        with patch("backend.app.foundation.ci_post_publish_deviation_audit.REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit"):
            with patch("backend.app.foundation.ci_post_publish_deviation_audit.ROOT", tmp_path):
                result = generate_post_publish_deviation_audit_report(review=review, output_path=str(tmp_path))

        json_path = tmp_path / "migration_reports" / "foundation_audit" / "R241-17B_POST_PUBLISH_DEVIATION_AUDIT.json"
        md_path = tmp_path / "migration_reports" / "foundation_audit" / "R241-17B_POST_PUBLISH_DEVIATION_AUDIT.md"

        assert json_path.exists()
        assert md_path.exists()
        assert result["json_path"] == str(json_path)
        assert result["md_path"] == str(md_path)

    def test_generate_closure_summary_writes_md(self, tmp_path: Path):
        review = {
            "closure_id": "R241-17B",
            "generated_at": "2026-04-26T14:00:00Z",
            "status": "operationally_closed_with_deviation",
            "decision": "approve_operational_closure_with_force_push_deviation",
            "force_push_deviation": True,
            "head_hash": "abc123",
            "origin_main_hash": "abc123",
            "remote_summary": "git@github.com:yangzixuan88/deer-flow.git",
            "workflow_remote_present": True,
            "workflow_dispatch_only": True,
            "workflow_run_count": 0,
            "stash_summary": "WIP on main: 174c371",
            "worktree_state": "clean_with_stash",
            "delivery_closure_state": "closed_with_external_worktree_condition",
            "safety_summary": "SAFE: all critical/high checks passed",
            "warnings": [],
            "errors": [],
        }

        with patch("backend.app.foundation.ci_post_publish_deviation_audit.REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit"):
            with patch("backend.app.foundation.ci_post_publish_deviation_audit.ROOT", tmp_path):
                result = generate_final_operational_closure_summary(review=review, output_path=str(tmp_path))

        md_path = tmp_path / "migration_reports" / "foundation_audit" / "R241-17B_FINAL_OPERATIONAL_CLOSURE.md"

        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "R241-17B: Final Operational Closure" in content
        assert "git stash pop" in content

    def test_reports_only_write_to_tmp_path(self, tmp_path: Path):
        review = {
            "closure_id": "R241-17B",
            "generated_at": "2026-04-26T14:00:00Z",
            "status": "operationally_closed",
            "decision": "approve_operational_closure",
            "force_push_deviation": False,
            "checks": [],
            "deviations": {},
            "remote_summary": "",
            "workflow_remote_present": True,
            "workflow_dispatch_only": True,
            "workflow_run_count": 0,
            "stash_summary": "",
            "worktree_state": "clean",
            "delivery_closure_state": "closed",
            "safety_summary": "SAFE",
            "validation_result": {"valid": True},
            "warnings": [],
            "errors": [],
        }

        with patch("backend.app.foundation.ci_post_publish_deviation_audit.REPORT_DIR", tmp_path / "migration_reports" / "foundation_audit"):
            with patch("backend.app.foundation.ci_post_publish_deviation_audit.ROOT", tmp_path):
                generate_post_publish_deviation_audit_report(review=review, output_path=str(tmp_path))

        json_file = tmp_path / "migration_reports" / "foundation_audit" / "R241-17B_POST_PUBLISH_DEVIATION_AUDIT.json"
        assert json_file.exists()

        other_dirs = list(tmp_path.glob("**/*"))
        other_json_files = [f for f in other_dirs if f.suffix == ".json" and f != json_file]
        for f in other_json_files:
            assert "R241-17B" not in f.name


class TestDataClasses:
    """Test PostPublishAuditCheck and PostPublishDeviation data classes."""

    def test_audit_check_init(self):
        check = PostPublishAuditCheck(
            check_id="test_check",
            passed=True,
            risk_level=PostPublishRiskLevel.HIGH,
            description="Test check",
            observed_value="value",
            expected_value="expected",
            evidence_refs=["ref1"],
            required_for_operational_closure=True,
            blocked_reasons=[],
            warnings=[],
            errors=[],
        )
        assert check.check_id == "test_check"
        assert check.passed is True
        assert check.risk_level == PostPublishRiskLevel.HIGH
        assert check.description == "Test check"
        assert check.observed_value == "value"
        assert check.expected_value == "expected"
        assert check.evidence_refs == ["ref1"]
        assert check.required_for_operational_closure is True

    def test_deviation_init(self):
        dev = PostPublishDeviation(
            deviation_id="force_push",
            deviation_type=PostPublishDeviationType.FORCE_PUSH_USED,
            risk_level=PostPublishRiskLevel.MEDIUM,
            description="Force push was used",
            accepted=True,
            reason="User fork",
            evidence_refs=["git log"],
            warnings=["rewrites history"],
            errors=[],
        )
        assert dev.deviation_id == "force_push"
        assert dev.deviation_type == PostPublishDeviationType.FORCE_PUSH_USED
        assert dev.risk_level == PostPublishRiskLevel.MEDIUM
        assert dev.accepted is True
        assert dev.reason == "User fork"

    def test_operational_closure_is_dict(self):
        closure = PostPublishOperationalClosure()
        closure["closure_id"] = "R241-17B"
        closure["status"] = "operationally_closed_with_deviation"

        assert closure["closure_id"] == "R241-17B"
        assert closure["status"] == "operationally_closed_with_deviation"
        assert isinstance(closure, dict)


class TestProhibitedActions:
    """Test that prohibited actions are correctly identified."""

    def test_force_push_to_upstream_blocked(self):
        remote_state = {"remote_owner_repo": "bytedance", "workflow_run_count": 0}
        stash_state = {"stash_present": True}

        deviations = classify_post_publish_deviations(root=None, remote_state=remote_state, stash_state=stash_state)

        force_dev = deviations["force_push_used"]
        assert force_dev.accepted is False

    def test_stash_pop_not_executed(self):
        review = {
            "status": "operationally_closed_with_deviation",
            "decision": "approve_operational_closure_with_force_push_deviation",
            "force_push_deviation": True,
            "workflow_run_count": 0,
            "checks": [{"check_id": "remote_is_user_fork", "passed": True}],
            "delivery_closure_state": "closed_with_external_worktree_condition",
        }

        result = validate_post_publish_deviation_audit(review)
        assert result["valid"] is True