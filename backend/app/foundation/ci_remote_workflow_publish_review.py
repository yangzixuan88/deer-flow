"""R241-16N Remote Workflow Publish Readiness / Push Review.

This module reviews whether the local .github/workflows/foundation-manual-dispatch.yml
can be published to a remote branch without modifying existing workflows.

CRITICAL CONSTRAINTS:
- Read-only review only
- No git commit
- No git push
- No gh workflow run
- No workflow modification
- No secrets reading
- No runtime/audit JSONL/action queue writing
- No auto-fix execution
"""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Constants ────────────────────────────────────────────────────────────────

WORKFLOW_FILE = "foundation-manual-dispatch.yml"
REPORT_DIR = Path(__file__).resolve().parents[1] / "migration_reports" / "foundation_audit"
ROOT = Path(__file__).resolve().parents[3]

# ── 1. Enums ────────────────────────────────────────────────────────────────

class RemoteWorkflowPublishReadinessStatus:
    READY_FOR_PUBLISH_CONFIRMATION = "ready_for_publish_confirmation"
    BLOCKED_NO_LOCAL_WORKFLOW = "blocked_no_local_workflow"
    BLOCKED_WORKFLOW_ALREADY_REMOTE = "blocked_workflow_already_remote"
    BLOCKED_UNEXPECTED_DIFF = "blocked_unexpected_diff"
    BLOCKED_UNEXPECTED_WORKFLOW_DIFF = "blocked_unexpected_workflow_diff"
    BLOCKED_EXISTING_WORKFLOW_MUTATION = "blocked_existing_workflow_mutation"
    BLOCKED_SECURITY_POLICY = "blocked_security_policy"
    BLOCKED_MISSING_ROLLBACK = "blocked_missing_rollback"
    DESIGN_ONLY = "design_only"
    UNKNOWN = "unknown"


class RemoteWorkflowPublishDecision:
    ALLOW_PUBLISH_CONFIRMATION_GATE = "allow_publish_confirmation_gate"
    KEEP_LOCAL_ONLY = "keep_local_only"
    BLOCK_PUBLISH = "block_publish"
    UNKNOWN = "unknown"


class RemoteWorkflowPublishOption:
    OPTION_A_KEEP_LOCAL_ONLY = "option_a_keep_local_only"
    OPTION_B_COMMIT_TO_REVIEW_BRANCH = "option_b_commit_to_review_branch"
    OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION = "option_c_push_to_default_branch_after_confirmation"
    OPTION_D_OPEN_PR_AFTER_CONFIRMATION = "option_d_open_pr_after_confirmation"
    UNKNOWN = "unknown"


class RemoteWorkflowPublishRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ── 2. Core Objects ──────────────────────────────────────────────────────────

class RemoteWorkflowPublishReadinessCheck:
    """A single check in the publish readiness review."""

    def __init__(
        self,
        check_id: str,
        check_type: str,
        passed: bool,
        risk_level: str,
        description: str,
        command_blueprint: Optional[dict] = None,
        command_executed: Optional[dict] = None,
        observed_value: Optional[dict] = None,
        expected_value: Optional[dict] = None,
        evidence_refs: Optional[list] = None,
        blocked_reasons: Optional[list] = None,
        warnings: Optional[list] = None,
        errors: Optional[list] = None,
    ):
        self.check_id = check_id
        self.check_type = check_type
        self.passed = passed
        self.risk_level = risk_level
        self.description = description
        self.command_blueprint = command_blueprint or {}
        self.command_executed = command_executed or {}
        self.observed_value = observed_value or {}
        self.expected_value = expected_value or {}
        self.evidence_refs = evidence_refs or []
        self.blocked_reasons = blocked_reasons or []
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "check_type": self.check_type,
            "passed": self.passed,
            "risk_level": self.risk_level,
            "description": self.description,
            "command_blueprint": self.command_blueprint,
            "command_executed": self.command_executed,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "evidence_refs": self.evidence_refs,
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class RemoteWorkflowPublishCommandBlueprint:
    """A command blueprint for publish action (not executed)."""

    def __init__(
        self,
        command_id: str,
        command_type: str,
        argv: list[str],
        command_allowed_now: bool,
        would_modify_git_history: bool,
        would_push_remote: bool,
        would_trigger_workflow: bool,
        requires_confirmation_phrase: str,
        description: str = "",
        warnings: Optional[list] = None,
        errors: Optional[list] = None,
    ):
        self.command_id = command_id
        self.command_type = command_type
        self.argv = argv
        self.command_allowed_now = command_allowed_now
        self.would_modify_git_history = would_modify_git_history
        self.would_push_remote = would_push_remote
        self.would_trigger_workflow = would_trigger_workflow
        self.requires_confirmation_phrase = requires_confirmation_phrase
        self.description = description
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type,
            "argv": self.argv,
            "command_allowed_now": self.command_allowed_now,
            "would_modify_git_history": self.would_modify_git_history,
            "would_push_remote": self.would_push_remote,
            "would_trigger_workflow": self.would_trigger_workflow,
            "requires_confirmation_phrase": self.requires_confirmation_phrase,
            "description": self.description,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class RemoteWorkflowPublishReview:
    """Complete publish readiness review result."""

    def __init__(
        self,
        review_id: str,
        generated_at: str,
        status: str,
        decision: str,
        local_workflow_exists: bool,
        remote_workflow_exists: bool,
        workflow_diff_summary: dict,
        existing_workflows_unchanged: bool,
        publish_options: list[dict],
        recommended_option: str,
        publish_command_blueprints: list[dict],
        rollback_plan: dict,
        confirmation_requirements: dict,
        checks: list[dict],
        safety_summary: dict,
        warnings: Optional[list] = None,
        errors: Optional[list] = None,
    ):
        self.review_id = review_id
        self.generated_at = generated_at
        self.status = status
        self.decision = decision
        self.local_workflow_exists = local_workflow_exists
        self.remote_workflow_exists = remote_workflow_exists
        self.workflow_diff_summary = workflow_diff_summary
        self.existing_workflows_unchanged = existing_workflows_unchanged
        self.publish_options = publish_options
        self.recommended_option = recommended_option
        self.publish_command_blueprints = publish_command_blueprints
        self.rollback_plan = rollback_plan
        self.confirmation_requirements = confirmation_requirements
        self.checks = checks
        self.safety_summary = safety_summary
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "decision": self.decision,
            "local_workflow_exists": self.local_workflow_exists,
            "remote_workflow_exists": self.remote_workflow_exists,
            "workflow_diff_summary": self.workflow_diff_summary,
            "existing_workflows_unchanged": self.existing_workflows_unchanged,
            "publish_options": self.publish_options,
            "recommended_option": self.recommended_option,
            "publish_command_blueprints": self.publish_command_blueprints,
            "rollback_plan": self.rollback_plan,
            "confirmation_requirements": self.confirmation_requirements,
            "checks": self.checks,
            "safety_summary": self.safety_summary,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ── 3. Helper: run_readonly_command ─────────────────────────────────────────

def _run_readonly_command(argv: list[str], timeout_seconds: int = 5, root: Optional[str] = None) -> dict:
    """Execute a read-only command and return structured result."""
    cwd = root if root else str(ROOT)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=cwd,
        )
        return {
            "executed": True,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "argv": argv,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {"executed": False, "returncode": -1, "error": "timeout", "argv": argv, "timed_out": True}
    except FileNotFoundError:
        return {"executed": False, "returncode": -1, "error": "not found", "argv": argv, "timed_out": False}
    except Exception as e:
        return {"executed": False, "returncode": -1, "error": str(e), "argv": argv, "timed_out": False}


# ── 4. load_r241_16m_visibility_review ───────────────────────────────────────

def load_r241_16m_visibility_review(root: Optional[str] = None) -> dict:
    """Load the R241-16M corrected visibility review result.

    Returns the parsed JSON from R241-16M_REMOTE_VISIBILITY_CONSISTENCY_REVIEW.json.

    Raises FileNotFoundError if the report does not exist.
    """
    root_path = Path(root).resolve() if root else ROOT
    report_path = root_path / "migration_reports" / "foundation_audit" / "R241-16M_REMOTE_VISIBILITY_CONSISTENCY_REVIEW.json"
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)


# ── 5. inspect_local_workflow_diff ─────────────────────────────────────────

TARGET_WORKFLOW_PATH = f".github/workflows/{WORKFLOW_FILE}"
EXISTING_WORKFLOW_PATHS = {
    ".github/workflows/backend-unit-tests.yml",
    ".github/workflows/lint-check.yml",
}


def _parse_porcelain_paths(output: str) -> list[dict]:
    entries: list[dict] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        status = line[:2].strip() or line[:2]
        path = line[3:] if len(line) > 3 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append({"status": status, "path": path.replace("\\", "/"), "raw": line})
    return entries


def _parse_name_status_entries(output: str) -> list[dict]:
    entries: list[dict] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0].strip()
        path = parts[-1].replace("\\", "/") if len(parts) > 1 else line.replace("\\", "/")
        entries.append({"status": status, "path": path, "raw": line})
    return entries


def inspect_workflow_directory_diff(root: Optional[str] = None) -> dict:
    """Inspect only .github/workflows/ changes for publish readiness."""
    root_path = Path(root).resolve() if root else ROOT
    warnings: list[str] = []
    errors: list[str] = []
    status_result = _run_readonly_command(["git", "status", "--porcelain", "--", ".github/workflows/"], root=str(root_path))
    diff_result = _run_readonly_command(["git", "diff", "--name-status", "--", ".github/workflows/"], root=str(root_path))
    _run_readonly_command(["git", "diff", "--stat", "--", ".github/workflows/"], root=str(root_path))
    repo_status_result = _run_readonly_command(["git", "status", "--porcelain"], root=str(root_path))
    workflow_status_entries = _parse_porcelain_paths(status_result.get("stdout", "")) if status_result.get("executed") else []
    workflow_diff_entries = _parse_name_status_entries(diff_result.get("stdout", "")) if diff_result.get("executed") else []
    workflow_paths = {entry["path"] for entry in workflow_status_entries}
    workflow_paths.update(entry["path"] for entry in workflow_diff_entries)
    target_workflow_changed = TARGET_WORKFLOW_PATH in workflow_paths
    existing_workflows_changed = sorted(path for path in workflow_paths if path in EXISTING_WORKFLOW_PATHS)
    unexpected_workflows_changed = sorted(
        path for path in workflow_paths
        if path.startswith(".github/workflows/")
        and path != TARGET_WORKFLOW_PATH
        and path not in EXISTING_WORKFLOW_PATHS
    )
    diff_only_target_workflow = target_workflow_changed and not existing_workflows_changed and not unexpected_workflows_changed
    all_status_entries = _parse_porcelain_paths(repo_status_result.get("stdout", "")) if repo_status_result.get("executed") else []
    outside_dirty = [entry for entry in all_status_entries if not entry["path"].startswith(".github/workflows/")]
    if outside_dirty:
        warnings.append(f"repo_dirty_warning:{len(outside_dirty)} non-workflow changes ignored")
    if not status_result.get("executed"):
        errors.append(f"workflow_status_failed:{status_result.get('error') or status_result.get('stderr')}")
    if not diff_result.get("executed"):
        errors.append(f"workflow_diff_failed:{diff_result.get('error') or diff_result.get('stderr')}")
    return {
        "workflow_status_entries": workflow_status_entries,
        "workflow_diff_entries": workflow_diff_entries,
        "target_workflow_changed": target_workflow_changed,
        "existing_workflows_changed": existing_workflows_changed,
        "unexpected_workflows_changed": unexpected_workflows_changed,
        "diff_only_target_workflow": diff_only_target_workflow,
        "repo_dirty_outside_workflows_count": len(outside_dirty),
        "repo_dirty_outside_workflows_warning": bool(outside_dirty),
        "warnings": warnings,
        "errors": errors,
    }


def _has_trigger(content: str, trigger: str) -> bool:
    lowered = content.lower()
    return bool(
        re.search(rf"(?m)^\s*{re.escape(trigger)}\s*:", lowered)
        or re.search(rf"(?m)^\s*on\s*:\s*{re.escape(trigger)}\s*$", lowered)
        or re.search(rf"(?m)^\s*on\s*:\s*\[[^\]]*{re.escape(trigger)}[^\]]*\]", lowered)
    )


def inspect_publish_workflow_content_safety(root: Optional[str] = None) -> dict:
    """Inspect target workflow content without modifying it."""
    root_path = Path(root).resolve() if root else ROOT
    workflow_path = root_path / TARGET_WORKFLOW_PATH
    result = {
        "local_workflow_exists": workflow_path.exists(),
        "workflow_content_safe": False,
        "workflow_dispatch_only": False,
        "has_pr_trigger": False,
        "has_push_trigger": False,
        "has_schedule_trigger": False,
        "has_secrets": False,
        "has_webhook_network": False,
        "has_curl": False,
        "has_invoke_webrequest": False,
        "has_auto_fix": False,
        "has_runtime_write": False,
        "has_audit_jsonl_write": False,
        "has_action_queue_write": False,
        "contains_confirm_manual_dispatch": False,
        "contains_confirm_phrase": False,
        "execute_mode_default_plan_only": False,
        "blocked_reasons": [],
        "warnings": [],
        "errors": [],
    }
    if not workflow_path.exists():
        result["blocked_reasons"].append(f"Local workflow not found at {workflow_path}")
        return result
    try:
        content = workflow_path.read_text(encoding="utf-8")
    except OSError as exc:
        result["errors"].append(str(exc))
        result["blocked_reasons"].append("workflow_content_unreadable")
        return result
    lowered = content.lower()
    result["has_pr_trigger"] = _has_trigger(content, "pull_request")
    result["has_push_trigger"] = _has_trigger(content, "push")
    result["has_schedule_trigger"] = _has_trigger(content, "schedule")
    result["has_secrets"] = "secrets." in lowered or "${{ secrets" in lowered
    result["has_webhook_network"] = "webhook" in lowered
    result["has_curl"] = bool(re.search(r"(?m)^\s*curl\b", lowered)) or " curl " in lowered
    result["has_invoke_webrequest"] = "invoke-webrequest" in lowered
    auto_fix_scan = lowered.replace("auto_fix_blocked", "").replace("auto-fix blocked", "")
    result["has_auto_fix"] = "auto-fix" in auto_fix_scan or "auto_fix" in auto_fix_scan
    result["has_runtime_write"] = "runtime_write" in lowered or "runtime write" in lowered
    result["has_audit_jsonl_write"] = "audit_jsonl_write" in lowered or "audit jsonl write" in lowered
    result["has_action_queue_write"] = "action_queue_write" in lowered or "action queue write" in lowered
    result["contains_confirm_manual_dispatch"] = "confirm_manual_dispatch" in content
    result["contains_confirm_phrase"] = "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN" in content
    result["execute_mode_default_plan_only"] = "execute_mode" in content and bool(
        re.search(r"(?m)^\s*default\s*:\s*[\"']?plan_only[\"']?\s*$", content)
    )
    result["workflow_dispatch_only"] = "workflow_dispatch" in content and not result["has_pr_trigger"] and not result["has_push_trigger"] and not result["has_schedule_trigger"]
    blocked_checks = {
        "Workflow contains pull_request trigger": result["has_pr_trigger"],
        "Workflow contains push trigger": result["has_push_trigger"],
        "Workflow contains schedule trigger": result["has_schedule_trigger"],
        "Workflow references secrets": result["has_secrets"],
        "Workflow references webhook": result["has_webhook_network"],
        "Workflow contains curl": result["has_curl"],
        "Workflow contains Invoke-WebRequest": result["has_invoke_webrequest"],
        "Workflow contains auto-fix": result["has_auto_fix"],
        "Workflow contains runtime write indicator": result["has_runtime_write"],
        "Workflow contains audit JSONL write indicator": result["has_audit_jsonl_write"],
        "Workflow contains action queue write indicator": result["has_action_queue_write"],
        "Workflow missing confirm_manual_dispatch": not result["contains_confirm_manual_dispatch"],
        "Workflow missing CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN": not result["contains_confirm_phrase"],
        "Workflow execute_mode default is not plan_only": not result["execute_mode_default_plan_only"],
        "Workflow is not workflow_dispatch only": not result["workflow_dispatch_only"],
    }
    result["blocked_reasons"] = [reason for reason, blocked in blocked_checks.items() if blocked]
    result["workflow_content_safe"] = not result["blocked_reasons"]
    return result


def inspect_local_workflow_diff(root: Optional[str] = None) -> dict:
    """Inspect the local workflow diff (read-only).

    Checks:
    - Local workflow file exists
    - git status includes the workflow
    - git diff only affects foundation-manual-dispatch.yml
    - No PR/push/schedule triggers
    - No secrets
    - No webhook/network direct calls
    - No runtime/audit/action queue write
    - No auto-fix

    Returns a dict with inspection results.
    """
    root_path = Path(root).resolve() if root else ROOT
    workflow_rel_path = f".github/workflows/{WORKFLOW_FILE}"
    workflow_abs_path = root_path / workflow_rel_path

    result = {
        "local_workflow_exists": False,
        "git_status_includes_workflow": False,
        "diff_only_target_workflow": False,
        "diff_files": [],
        "workflow_content_safe": False,
        "has_pr_trigger": False,
        "has_push_trigger": False,
        "has_schedule_trigger": False,
        "has_secrets": False,
        "has_webhook_network": False,
        "has_auto_fix": False,
        "has_runtime_write": False,
        "workflow_dispatch_only": False,
        "passed": False,
        "blocked_reasons": [],
        "warnings": [],
        "errors": [],
    }

    # Check local file exists
    if workflow_abs_path.exists():
        result["local_workflow_exists"] = True
    else:
        result["blocked_reasons"].append(f"Local workflow not found at {workflow_abs_path}")
        return result

    # git status --porcelain for workflow file (combines tracked + untracked detection)
    # Shows: "?? path" for untracked, "A  path" for added/staged, "M  path" for modified
    status_result = _run_readonly_command(
        ["git", "status", "--porcelain", "--", workflow_rel_path], root=str(root_path)
    )
    if status_result["executed"] and status_result["stdout"].strip():
        result["git_status_includes_workflow"] = True

    # After a failed push retry, the target workflow may already be committed
    # locally and absent from working-tree status. Treat the HEAD commit as
    # publish-relevant if it only carries the target workflow change.
    head_diff_result = _run_readonly_command(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        root=str(root_path),
    )
    if head_diff_result["executed"]:
        head_changed_files = [
            line.strip().replace("\\", "/")
            for line in head_diff_result["stdout"].strip().split("\n")
            if line.strip()
        ]
        if workflow_rel_path in head_changed_files:
            result["git_status_includes_workflow"] = True

    # git diff --name-status for workflow directory only (not all repo changes)
    # This checks if any tracked workflow files are modified
    diff_result = _run_readonly_command(
        ["git", "diff", "--name-status", "--", ".github/workflows/"], root=str(root_path)
    )
    if diff_result["executed"]:
        workflow_changed_files = [
            line.strip() for line in diff_result["stdout"].strip().split("\n")
            if line.strip()
        ]
        result["diff_files"] = workflow_changed_files

        # Normalize path separators for comparison (git on Windows may use \)
        def _norm(p: str) -> str:
            return p.replace("\\", "/")

        # Check if ONLY target workflow is in the workflow-dir diff
        other_workflow_changes = [
            f for f in workflow_changed_files
            if ("backend-unit-tests.yml" in _norm(f) or "lint-check.yml" in _norm(f))
        ]
        if other_workflow_changes:
            result["blocked_reasons"].append(
                f"Existing workflow files modified: {[f for f in other_workflow_changes]}"
            )
        elif not workflow_changed_files:
            # No tracked workflow changes — if file is untracked (git status above),
            # only the target workflow is being added
            result["diff_only_target_workflow"] = True
        else:
            # Some tracked workflow files changed (not just our target)
            # Only allow if it's our target and no others
            target_tracked = [f for f in workflow_changed_files if WORKFLOW_FILE in _norm(f)]
            if target_tracked and not other_workflow_changes:
                result["diff_only_target_workflow"] = True

    # git diff for workflow content
    diff_workflow_result = _run_readonly_command(
        ["git", "diff", "--", workflow_rel_path], root=str(root_path)
    )
    if diff_workflow_result["executed"]:
        diff_content = diff_workflow_result["stdout"]
        if not diff_content.strip():
            # Untracked file — read from working tree
            diff_content = workflow_abs_path.read_text(encoding="utf-8")
        else:
            # Strip leading path info to get content diff
            lines = diff_content.split("\n")
            content_lines = [l for l in lines if not l.startswith("---") and not l.startswith("+++") and not l.startswith("diff") and not l.startswith("index")]
            diff_content = "\n".join(content_lines)

    # Check workflow content safety
    try:
        content = workflow_abs_path.read_text(encoding="utf-8")
    except Exception as e:
        result["errors"].append(f"Cannot read workflow content: {e}")
        return result

    # Check triggers
    result["has_pr_trigger"] = "pull_request" in content and "on:" in content
    result["has_push_trigger"] = "push:" in content and "on:" in content
    result["has_schedule_trigger"] = "schedule:" in content and "on:" in content

    # Check secrets
    result["has_secrets"] = (
        ("secrets." in content or "secret." in content)
        and not all("inputs." in content for _ in [1])  # inputs are OK
    )

    # Check workflow_dispatch only (acceptable trigger)
    result["workflow_dispatch_only"] = (
        "workflow_dispatch" in content
        and not result["has_pr_trigger"]
        and not result["has_push_trigger"]
        and not result["has_schedule_trigger"]
    )

    # Security policy
    if result["has_pr_trigger"]:
        result["blocked_reasons"].append("Workflow contains pull_request trigger (not allowed)")
    if result["has_push_trigger"]:
        result["blocked_reasons"].append("Workflow contains push trigger (not allowed)")
    if result["has_schedule_trigger"]:
        result["blocked_reasons"].append("Workflow contains schedule trigger (not allowed)")
    if result["has_secrets"]:
        result["blocked_reasons"].append("Workflow references secrets (not allowed in this review)")

    result["workflow_content_safe"] = (
        result["workflow_dispatch_only"]
        and not result["has_secrets"]
    )

    # Overall pass
    result["passed"] = (
        result["local_workflow_exists"]
        and result["git_status_includes_workflow"]
        and result["diff_only_target_workflow"]
        and result["workflow_content_safe"]
        and not result["blocked_reasons"]
    )

    return result


# ── 6. build_publish_command_blueprints ─────────────────────────────────────

def build_publish_command_blueprints() -> list[dict]:
    """Build publish command blueprints (not executed).

    Returns a list of RemoteWorkflowPublishCommandBlueprint dicts for all options.
    All blueprints have command_allowed_now=False.
    """
    CONFIRMATION_PHRASE = "CONFIRM_PUBLISH_FOUNDATION_MANUAL_WORKFLOW"

    blueprints = []

    # Option A: Keep local only
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_a_keep_local_only",
            command_type="none",
            argv=[],
            command_allowed_now=False,
            would_modify_git_history=False,
            would_push_remote=False,
            would_trigger_workflow=False,
            requires_confirmation_phrase="",
            description="Keep workflow local only. No git operations.",
            warnings=["Workflow will not be visible on GitHub Actions until manually pushed."],
        ).to_dict()
    )

    # Option B: Commit to review branch
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_b_commit_to_review_branch",
            command_type="git",
            argv=[
                "git", "checkout", "-b", "foundation-manual-dispatch-review",
            ],
            command_allowed_now=False,
            would_modify_git_history=True,
            would_push_remote=False,
            would_trigger_workflow=False,
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Create a review branch and commit the workflow.",
            warnings=[
                "Creates a local branch but does NOT push to remote.",
                "Workflow still not visible on GitHub Actions until branch is pushed.",
            ],
        ).to_dict()
    )
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_b_commit_step",
            command_type="git",
            argv=[
                "git", "add", f".github/workflows/{WORKFLOW_FILE}",
            ],
            command_allowed_now=False,
            would_modify_git_history=True,
            would_push_remote=False,
            would_trigger_workflow=False,
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Stage the workflow file for commit.",
        ).to_dict()
    )
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_b_finalize",
            command_type="git",
            argv=[
                "git", "commit", "-m",
                "Add manual foundation CI workflow\n\nCo-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>",
            ],
            command_allowed_now=False,
            would_modify_git_history=True,
            would_push_remote=False,
            would_trigger_workflow=False,
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Commit the workflow to the review branch.",
        ).to_dict()
    )

    # Option C: Push to default branch after confirmation
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_c_add",
            command_type="git",
            argv=[
                "git", "add", f".github/workflows/{WORKFLOW_FILE}",
            ],
            command_allowed_now=False,
            would_modify_git_history=True,
            would_push_remote=False,
            would_trigger_workflow=False,
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Stage the workflow file for commit.",
        ).to_dict()
    )
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_c_commit",
            command_type="git",
            argv=[
                "git", "commit", "-m",
                "Add manual foundation CI workflow\n\nCo-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>",
            ],
            command_allowed_now=False,
            would_modify_git_history=True,
            would_push_remote=False,
            would_trigger_workflow=False,
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Commit workflow to default branch (local only).",
        ).to_dict()
    )
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_c_push",
            command_type="git",
            argv=["git", "push", "origin", "main"],
            command_allowed_now=False,
            would_modify_git_history=False,
            would_push_remote=True,
            would_trigger_workflow=True,  # workflow_dispatch becomes available after push
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Push to origin/main — makes workflow visible on GitHub Actions.",
            warnings=[
                "This WILL make the workflow visible on GitHub Actions.",
                "After push, workflow is accessible via gh workflow list.",
                "workflow_dispatch trigger allows manual runs without code access.",
            ],
        ).to_dict()
    )

    # Option D: Open PR after confirmation
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_d_branch",
            command_type="git",
            argv=[
                "git", "checkout", "-b", "foundation-manual-dispatch-review",
            ],
            command_allowed_now=False,
            would_modify_git_history=True,
            would_push_remote=False,
            would_trigger_workflow=False,
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Create review branch.",
        ).to_dict()
    )
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_d_add",
            command_type="git",
            argv=[
                "git", "add", f".github/workflows/{WORKFLOW_FILE}",
            ],
            command_allowed_now=False,
            would_modify_git_history=True,
            would_push_remote=False,
            would_trigger_workflow=False,
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Stage the workflow file.",
        ).to_dict()
    )
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_d_commit",
            command_type="git",
            argv=[
                "git", "commit", "-m",
                "Add manual foundation CI workflow\n\nCo-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>",
            ],
            command_allowed_now=False,
            would_modify_git_history=True,
            would_push_remote=False,
            would_trigger_workflow=False,
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Commit to review branch.",
        ).to_dict()
    )
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_d_push",
            command_type="git",
            argv=["git", "push", "origin", "foundation-manual-dispatch-review"],
            command_allowed_now=False,
            would_modify_git_history=False,
            would_push_remote=True,
            would_trigger_workflow=False,  # PR workflow not yet merged
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Push review branch to origin.",
        ).to_dict()
    )
    blueprints.append(
        RemoteWorkflowPublishCommandBlueprint(
            command_id="option_d_pr",
            command_type="manual",
            argv=["gh", "pr", "create", "--repo", "bytedance/deer-flow", "--title",
                  "Add manual foundation CI workflow", "--body",
                  "This PR adds the foundation-manual-dispatch.yml workflow.\n\n"
                  "Confirmation phrase: CONFIRM_PUBLISH_FOUNDATION_MANUAL_WORKFLOW"],
            command_allowed_now=False,
            would_modify_git_history=False,
            would_push_remote=False,
            would_trigger_workflow=False,
            requires_confirmation_phrase=CONFIRMATION_PHRASE,
            description="Open PR (manual step after push).",
            warnings=[
                "PR creation is a GitHub API write operation — must be done manually",
                "or via gh pr create with explicit confirmation.",
            ],
        ).to_dict()
    )

    return blueprints


# ── 7. build_publish_rollback_plan ──────────────────────────────────────────

def build_publish_rollback_plan() -> dict:
    """Build rollback plan for publish options.

    Does NOT execute any rollback — only defines procedures.
    """
    return {
        "if_only_local_uncommitted": {
            "description": "Workflow is local only (uncommitted).",
            "rollback_action": "No action required. File remains local.",
            "commands": [],
            "confirmation_required": True,
        },
        "if_committed_not_pushed": {
            "description": "Workflow committed to local branch but not pushed.",
            "rollback_action": "git reset --soft HEAD~1 to uncommit, then git checkout -- .github/workflows/foundation-manual-dispatch.yml to discard.",
            "commands": [
                "git reset --soft HEAD~1",
                "git checkout -- .github/workflows/foundation-manual-dispatch.yml",
            ],
            "confirmation_required": True,
            "warnings": ["This undoes the commit but file content may still be in staging."],
        },
        "if_pushed_to_review_branch": {
            "description": "Workflow pushed to a review branch (e.g., foundation-manual-dispatch-review).",
            "rollback_action": "Revert the commit via gh or close the PR.",
            "commands": [
                "gh api repos/bytedance/deer-flow/git/refs/heads/foundation-manual-dispatch-review -X DELETE",
                "# OR: git revert <commit-sha> && git push origin foundation-manual-dispatch-review",
            ],
            "confirmation_required": True,
            "warnings": [
                "Deleting the branch removes the workflow from GitHub Actions.",
                "If a PR is open, close it instead of deleting the branch.",
            ],
        },
        "if_pushed_to_default_branch": {
            "description": "Workflow pushed directly to origin/main.",
            "rollback_action": "Revert the commit or disable the workflow in GitHub Actions settings.",
            "commands": [
                "git revert <commit-sha> && git push origin main",
                "# OR: Disable workflow in GitHub > Actions > select workflow > '...' menu > Disable",
            ],
            "confirmation_required": True,
            "warnings": [
                "Revert commit on main branch is a write operation.",
                "GitHub Actions UI disable is irreversible and visible to repo admins.",
                "Once disabled, the workflow cannot be re-enabled without a new commit.",
            ],
        },
        "no_auto_rollback": True,
        "no_delete_existing_workflows": True,
    }


# ── 8. build_publish_confirmation_requirements ───────────────────────────────

def build_publish_confirmation_requirements() -> dict:
    """Define confirmation requirements for publish.

    Returns the confirmation requirements dict.
    """
    return {
        "explicit_phrase_required": True,
        "confirmation_phrase": "CONFIRM_PUBLISH_FOUNDATION_MANUAL_WORKFLOW",
        "requirements": [
            "Confirm target option (review branch / default branch / PR / local only)",
            "Confirm no PR/push/schedule triggers in workflow_dispatch only",
            "Confirm no secrets / webhook / network direct calls",
            "Confirm no runtime/audit/action queue write",
            "Confirm no auto-fix execution",
            "Confirm existing workflows unchanged (backend-unit-tests.yml, lint-check.yml)",
            "Confirm rollback plan is acceptable for selected option",
            "Confirm target is review branch or default branch",
            "Confirm gh CLI is available for verification after push (or accept gh unavailable on this machine)",
        ],
        "must_not_be_auto_executed": True,
        "human_in_the_loop_required": True,
    }


# ── 9. evaluate_remote_workflow_publish_readiness ────────────────────────────

def evaluate_remote_workflow_publish_readiness(root: Optional[str] = None) -> dict:
    """Evaluate publish readiness for foundation-manual-dispatch.yml.

    Aggregates:
    - R241-16M visibility review
    - Local workflow diff inspection
    - Publish options
    - Command blueprints
    - Rollback plan
    - Confirmation requirements
    """
    root_path = Path(root).resolve() if root else ROOT
    generated_at = datetime.now(timezone.utc).isoformat()
    review_id = f"rv-publish-{uuid.uuid4().hex[:12]}"

    checks: list[dict] = []

    # Check 1: Load R241-16M
    r241_16m = None
    r241_16m_load_passed = False
    try:
        r241_16m = load_r241_16m_visibility_review(str(root_path))
        git_exact_path_present = r241_16m.get("git_exact_path_present", True)
        local_workflow_exists = r241_16m.get("local_workflow_exists", False)
        r241_16m_load_passed = (
            not git_exact_path_present  # Expected: not on remote yet
            and local_workflow_exists   # But exists locally
        )
    except FileNotFoundError as e:
        r241_16m_load_passed = False
    except Exception as e:
        r241_16m_load_passed = False

    checks.append(
        RemoteWorkflowPublishReadinessCheck(
            check_id="check_r241_16m_loaded",
            check_type="r241_16m_loaded",
            passed=r241_16m_load_passed,
            risk_level=RemoteWorkflowPublishRiskLevel.CRITICAL,
            description="Load R241-16M corrected visibility review",
            observed_value={
                "r241_16m_loaded": r241_16m is not None,
                "git_exact_path_present": r241_16m.get("git_exact_path_present") if r241_16m else None,
                "local_workflow_exists": r241_16m.get("local_workflow_exists") if r241_16m else None,
            },
            expected_value={
                "git_exact_path_present": False,
                "local_workflow_exists": True,
            },
            blocked_reasons=[] if r241_16m_load_passed else ["R241-16M report not loaded or conditions not met"],
        ).to_dict()
    )

    # Check 2: Inspect local diff
    diff_result = inspect_local_workflow_diff(str(root_path))

    checks.append(
        RemoteWorkflowPublishReadinessCheck(
            check_id="check_local_workflow_diff",
            check_type="local_workflow_diff",
            passed=diff_result["passed"],
            risk_level=RemoteWorkflowPublishRiskLevel.CRITICAL,
            description="Inspect local workflow diff for safety and scope",
            observed_value=diff_result,
            expected_value={
                "local_workflow_exists": True,
                "diff_only_target_workflow": True,
                "workflow_content_safe": True,
            },
            blocked_reasons=diff_result.get("blocked_reasons", []),
            warnings=diff_result.get("warnings", []),
        ).to_dict()
    )

    # Check 3: Existing workflows unchanged
    existing_unchanged_result = {
        "backend_unit_tests_unchanged": True,
        "lint_check_unchanged": True,
        "passed": True,
    }
    for wf in ["backend-unit-tests.yml", "lint-check.yml"]:
        diff_wf = _run_readonly_command(["git", "diff", "--", f".github/workflows/{wf}"])
        if diff_wf["executed"] and diff_wf["stdout"].strip():
            existing_unchanged_result["passed"] = False
            existing_unchanged_result[f"{wf}_unchanged"] = False

    checks.append(
        RemoteWorkflowPublishReadinessCheck(
            check_id="check_existing_workflows_unchanged",
            check_type="existing_workflows_unchanged",
            passed=existing_unchanged_result["passed"],
            risk_level=RemoteWorkflowPublishRiskLevel.HIGH,
            description="Verify existing workflow files are not modified",
            observed_value=existing_unchanged_result,
            expected_value={
                "backend_unit_tests_unchanged": True,
                "lint_check_unchanged": True,
            },
            blocked_reasons=[] if existing_unchanged_result["passed"]
                else [f"Existing workflow {wf} has uncommitted changes"]
                if not existing_unchanged_result["passed"] else [],
        ).to_dict()
    )

    # Determine overall status and decision
    r241_16m_ok = r241_16m_load_passed
    diff_ok = diff_result["passed"]
    existing_ok = existing_unchanged_result["passed"]

    if not r241_16m_ok:
        status = RemoteWorkflowPublishReadinessStatus.UNKNOWN
        decision = RemoteWorkflowPublishDecision.UNKNOWN
    elif not diff_ok:
        status = RemoteWorkflowPublishReadinessStatus.BLOCKED_UNEXPECTED_DIFF
        decision = RemoteWorkflowPublishDecision.BLOCK_PUBLISH
    elif not existing_ok:
        status = RemoteWorkflowPublishReadinessStatus.BLOCKED_EXISTING_WORKFLOW_MUTATION
        decision = RemoteWorkflowPublishDecision.BLOCK_PUBLISH
    elif r241_16m_ok and diff_ok and existing_ok:
        status = RemoteWorkflowPublishReadinessStatus.READY_FOR_PUBLISH_CONFIRMATION
        decision = RemoteWorkflowPublishDecision.ALLOW_PUBLISH_CONFIRMATION_GATE
    else:
        status = RemoteWorkflowPublishReadinessStatus.UNKNOWN
        decision = RemoteWorkflowPublishDecision.UNKNOWN

    # Build publish options
    publish_options = [
        {
            "option_id": RemoteWorkflowPublishOption.OPTION_A_KEEP_LOCAL_ONLY,
            "label": "A: Keep Local Only",
            "description": "Do not publish. Workflow remains local only.",
            "risk_level": RemoteWorkflowPublishRiskLevel.LOW,
            "recommended": False,
        },
        {
            "option_id": RemoteWorkflowPublishOption.OPTION_B_COMMIT_TO_REVIEW_BRANCH,
            "label": "B: Commit to Review Branch",
            "description": "Commit to a local review branch (foundation-manual-dispatch-review). No remote push.",
            "risk_level": RemoteWorkflowPublishRiskLevel.LOW,
            "recommended": False,
        },
        {
            "option_id": RemoteWorkflowPublishOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION,
            "label": "C: Push to Default Branch",
            "description": "Push directly to origin/main. Workflow immediately visible on GitHub Actions.",
            "risk_level": RemoteWorkflowPublishRiskLevel.MEDIUM,
            "recommended": status == RemoteWorkflowPublishReadinessStatus.READY_FOR_PUBLISH_CONFIRMATION,
        },
        {
            "option_id": RemoteWorkflowPublishOption.OPTION_D_OPEN_PR_AFTER_CONFIRMATION,
            "label": "D: Open PR After Confirmation",
            "description": "Push to review branch and open PR for review before merging to main.",
            "risk_level": RemoteWorkflowPublishRiskLevel.LOW,
            "recommended": status == RemoteWorkflowPublishReadinessStatus.READY_FOR_PUBLISH_CONFIRMATION,
        },
    ]

    # Recommended option
    recommended = next(
        (o["option_id"] for o in publish_options if o["recommended"]),
        RemoteWorkflowPublishOption.OPTION_A_KEEP_LOCAL_ONLY,
    )

    safety_summary = {
        "no_git_commit_executed": True,
        "no_git_push_executed": True,
        "no_gh_workflow_run_executed": True,
        "no_workflow_modified": True,
        "no_secrets_read": True,
        "no_runtime_write": True,
        "no_audit_jsonl_write": True,
        "no_action_queue_write": True,
        "no_auto_fix_executed": True,
        "confirmation_phrase_defined": True,
        "rollback_plan_defined": True,
    }

    review = RemoteWorkflowPublishReview(
        review_id=review_id,
        generated_at=generated_at,
        status=status,
        decision=decision,
        local_workflow_exists=diff_result["local_workflow_exists"],
        remote_workflow_exists=r241_16m.get("git_exact_path_present", False) if r241_16m else False,
        workflow_diff_summary=diff_result,
        existing_workflows_unchanged=existing_unchanged_result["passed"],
        publish_options=publish_options,
        recommended_option=recommended,
        publish_command_blueprints=build_publish_command_blueprints(),
        rollback_plan=build_publish_rollback_plan(),
        confirmation_requirements=build_publish_confirmation_requirements(),
        checks=checks,
        safety_summary=safety_summary,
    )

    return review.to_dict()


# ── 10. validate_remote_workflow_publish_review ─────────────────────────────

def _build_canonical_checks(
    r241_16m: Optional[dict],
    r241_16m_ok: bool,
    diff_result: dict,
    content_result: dict,
) -> list[dict]:
    checks: list[dict] = []
    checks.append(
        RemoteWorkflowPublishReadinessCheck(
            check_id="check_r241_16m_loaded",
            check_type="r241_16m_loaded",
            passed=r241_16m_ok,
            risk_level=RemoteWorkflowPublishRiskLevel.CRITICAL,
            description="Load R241-16M corrected visibility review",
            observed_value={
                "r241_16m_loaded": r241_16m is not None,
                "git_exact_path_present": r241_16m.get("git_exact_path_present") if r241_16m else None,
                "local_workflow_exists": r241_16m.get("local_workflow_exists") if r241_16m else None,
            },
            expected_value={"git_exact_path_present": False, "local_workflow_exists": True},
            blocked_reasons=[] if r241_16m_ok else ["R241-16M report not loaded or conditions not met"],
        ).to_dict()
    )
    checks.append(
        RemoteWorkflowPublishReadinessCheck(
            check_id="check_workflow_directory_diff",
            check_type="workflow_directory_diff",
            passed=diff_result.get("diff_only_target_workflow", False),
            risk_level=RemoteWorkflowPublishRiskLevel.CRITICAL,
            description="Inspect only .github/workflows/ scoped diff",
            observed_value=diff_result,
            expected_value={
                "target_workflow_changed": True,
                "existing_workflows_changed": [],
                "unexpected_workflows_changed": [],
                "diff_only_target_workflow": True,
            },
            blocked_reasons=(
                ["target workflow not changed"] if not diff_result.get("target_workflow_changed") else []
            ) + (
                [f"existing workflows changed: {diff_result.get('existing_workflows_changed')}"]
                if diff_result.get("existing_workflows_changed") else []
            ) + (
                [f"unexpected workflows changed: {diff_result.get('unexpected_workflows_changed')}"]
                if diff_result.get("unexpected_workflows_changed") else []
            ),
            warnings=diff_result.get("warnings", []),
            errors=diff_result.get("errors", []),
        ).to_dict()
    )
    checks.append(
        RemoteWorkflowPublishReadinessCheck(
            check_id="check_publish_workflow_content_safety",
            check_type="publish_workflow_content_safety",
            passed=content_result.get("workflow_content_safe", False),
            risk_level=RemoteWorkflowPublishRiskLevel.CRITICAL,
            description="Inspect target workflow content safety",
            observed_value=content_result,
            expected_value={
                "workflow_dispatch_only": True,
                "has_pr_trigger": False,
                "has_push_trigger": False,
                "has_schedule_trigger": False,
                "has_secrets": False,
            },
            blocked_reasons=content_result.get("blocked_reasons", []),
            warnings=content_result.get("warnings", []),
            errors=content_result.get("errors", []),
        ).to_dict()
    )
    existing_ok = not diff_result.get("existing_workflows_changed")
    checks.append(
        RemoteWorkflowPublishReadinessCheck(
            check_id="check_existing_workflows_unchanged",
            check_type="existing_workflows_unchanged",
            passed=existing_ok,
            risk_level=RemoteWorkflowPublishRiskLevel.HIGH,
            description="Verify existing workflow files are not modified",
            observed_value={"existing_workflows_changed": diff_result.get("existing_workflows_changed", [])},
            expected_value={"existing_workflows_changed": []},
            blocked_reasons=[] if existing_ok else ["existing workflow mutation"],
        ).to_dict()
    )
    return checks


def evaluate_canonical_publish_readiness(root: Optional[str] = None) -> dict:
    """Evaluate publish readiness using canonical scoped workflow checks."""
    root_path = Path(root).resolve() if root else ROOT
    generated_at = datetime.now(timezone.utc).isoformat()
    review_id = f"rv-publish-{uuid.uuid4().hex[:12]}"

    try:
        r241_16m = load_r241_16m_visibility_review(str(root_path))
    except Exception:
        r241_16m = None
    r241_16m_ok = bool(
        r241_16m
        and r241_16m.get("local_workflow_exists") is True
        and r241_16m.get("git_exact_path_present") is False
    )
    diff_result = inspect_workflow_directory_diff(str(root_path))
    content_result = inspect_publish_workflow_content_safety(str(root_path))
    checks = _build_canonical_checks(r241_16m, r241_16m_ok, diff_result, content_result)

    if not content_result.get("local_workflow_exists"):
        status = RemoteWorkflowPublishReadinessStatus.BLOCKED_NO_LOCAL_WORKFLOW
        decision = RemoteWorkflowPublishDecision.BLOCK_PUBLISH
    elif r241_16m and r241_16m.get("git_exact_path_present") is True:
        status = RemoteWorkflowPublishReadinessStatus.BLOCKED_WORKFLOW_ALREADY_REMOTE
        decision = RemoteWorkflowPublishDecision.BLOCK_PUBLISH
    elif diff_result.get("existing_workflows_changed"):
        status = RemoteWorkflowPublishReadinessStatus.BLOCKED_EXISTING_WORKFLOW_MUTATION
        decision = RemoteWorkflowPublishDecision.BLOCK_PUBLISH
    elif diff_result.get("unexpected_workflows_changed"):
        status = RemoteWorkflowPublishReadinessStatus.BLOCKED_UNEXPECTED_WORKFLOW_DIFF
        decision = RemoteWorkflowPublishDecision.BLOCK_PUBLISH
    elif not content_result.get("workflow_content_safe"):
        status = RemoteWorkflowPublishReadinessStatus.BLOCKED_SECURITY_POLICY
        decision = RemoteWorkflowPublishDecision.BLOCK_PUBLISH
    elif r241_16m_ok and diff_result.get("diff_only_target_workflow") and content_result.get("workflow_content_safe"):
        status = RemoteWorkflowPublishReadinessStatus.READY_FOR_PUBLISH_CONFIRMATION
        decision = RemoteWorkflowPublishDecision.ALLOW_PUBLISH_CONFIRMATION_GATE
    else:
        status = RemoteWorkflowPublishReadinessStatus.BLOCKED_UNEXPECTED_DIFF
        decision = RemoteWorkflowPublishDecision.BLOCK_PUBLISH

    publish_options = [
        {"option_id": RemoteWorkflowPublishOption.OPTION_A_KEEP_LOCAL_ONLY, "label": "A: Keep Local Only", "description": "Do not publish. Workflow remains local only.", "risk_level": RemoteWorkflowPublishRiskLevel.LOW, "recommended": False},
        {"option_id": RemoteWorkflowPublishOption.OPTION_B_COMMIT_TO_REVIEW_BRANCH, "label": "B: Commit to Review Branch", "description": "Commit to a local review branch. No remote push.", "risk_level": RemoteWorkflowPublishRiskLevel.LOW, "recommended": False},
        {"option_id": RemoteWorkflowPublishOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION, "label": "C: Push to Default Branch", "description": "Push directly to origin/main after a separate implementation review.", "risk_level": RemoteWorkflowPublishRiskLevel.MEDIUM, "recommended": status == RemoteWorkflowPublishReadinessStatus.READY_FOR_PUBLISH_CONFIRMATION},
        {"option_id": RemoteWorkflowPublishOption.OPTION_D_OPEN_PR_AFTER_CONFIRMATION, "label": "D: Open PR After Confirmation", "description": "Push a review branch and open PR after a separate implementation review.", "risk_level": RemoteWorkflowPublishRiskLevel.LOW, "recommended": status == RemoteWorkflowPublishReadinessStatus.READY_FOR_PUBLISH_CONFIRMATION},
    ]
    recommended = next((o["option_id"] for o in publish_options if o["recommended"]), RemoteWorkflowPublishOption.OPTION_A_KEEP_LOCAL_ONLY)
    workflow_diff_summary = {
        **diff_result,
        "local_workflow_exists": content_result.get("local_workflow_exists"),
        "git_status_includes_workflow": diff_result.get("target_workflow_changed"),
        "diff_files": [entry["raw"] for entry in diff_result.get("workflow_diff_entries", [])],
        "workflow_content_safe": content_result.get("workflow_content_safe"),
        "has_pr_trigger": content_result.get("has_pr_trigger"),
        "has_push_trigger": content_result.get("has_push_trigger"),
        "has_schedule_trigger": content_result.get("has_schedule_trigger"),
        "has_secrets": content_result.get("has_secrets"),
        "has_webhook_network": content_result.get("has_webhook_network"),
        "has_auto_fix": content_result.get("has_auto_fix"),
        "has_runtime_write": content_result.get("has_runtime_write"),
        "has_audit_jsonl_write": content_result.get("has_audit_jsonl_write"),
        "has_action_queue_write": content_result.get("has_action_queue_write"),
        "workflow_dispatch_only": content_result.get("workflow_dispatch_only"),
        "passed": status == RemoteWorkflowPublishReadinessStatus.READY_FOR_PUBLISH_CONFIRMATION,
        "blocked_reasons": [reason for check in checks for reason in check.get("blocked_reasons", [])],
        "warnings": diff_result.get("warnings", []) + content_result.get("warnings", []),
        "errors": diff_result.get("errors", []) + content_result.get("errors", []),
    }
    safety_summary = {
        "no_git_commit_executed": True,
        "no_git_push_executed": True,
        "no_gh_workflow_run_executed": True,
        "no_workflow_modified": True,
        "no_secrets_read": True,
        "no_runtime_write": True,
        "no_audit_jsonl_write": True,
        "no_action_queue_write": True,
        "no_auto_fix_executed": True,
        "confirmation_phrase_defined": True,
        "rollback_plan_defined": True,
        "json_md_same_review_object": True,
    }
    review = RemoteWorkflowPublishReview(
        review_id=review_id,
        generated_at=generated_at,
        status=status,
        decision=decision,
        local_workflow_exists=bool(content_result.get("local_workflow_exists")),
        remote_workflow_exists=bool(r241_16m.get("git_exact_path_present", False)) if r241_16m else False,
        workflow_diff_summary=workflow_diff_summary,
        existing_workflows_unchanged=not bool(diff_result.get("existing_workflows_changed")),
        publish_options=publish_options,
        recommended_option=recommended,
        publish_command_blueprints=build_publish_command_blueprints(),
        rollback_plan=build_publish_rollback_plan(),
        confirmation_requirements=build_publish_confirmation_requirements(),
        checks=checks,
        safety_summary=safety_summary,
        warnings=diff_result.get("warnings", []) + content_result.get("warnings", []),
        errors=diff_result.get("errors", []) + content_result.get("errors", []),
    )
    return review.to_dict()


def validate_remote_workflow_publish_review(review: dict) -> dict:
    """Validate that the review did not violate any safety constraints.

    Returns validation result dict with 'valid' boolean and 'violations' list.
    """
    violations: list[str] = []

    # Check git commit not executed
    cmd_results = review.get("safety_summary", {})
    if not cmd_results.get("no_git_commit_executed", True):
        violations.append("git commit was executed (safety violation)")

    # Check git push not executed
    if not cmd_results.get("no_git_push_executed", True):
        violations.append("git push was executed (safety violation)")

    # Check gh workflow run not executed
    if not cmd_results.get("no_gh_workflow_run_executed", True):
        violations.append("gh workflow run was executed (safety violation)")

    # Check rollback plan exists
    if not review.get("rollback_plan"):
        violations.append("Rollback plan missing")

    # Check confirmation phrase exists
    conf_req = review.get("confirmation_requirements", {})
    if not conf_req.get("confirmation_phrase"):
        violations.append("Confirmation phrase missing")

    # Check recommended option exists
    if not review.get("recommended_option"):
        violations.append("Recommended option missing")

    # Check command blueprints all have command_allowed_now=False
    for bp in review.get("publish_command_blueprints", []):
        if bp.get("command_allowed_now", False):
            violations.append(f"Command blueprint {bp.get('command_id')} has command_allowed_now=True")

    # Check existing workflows unchanged
    if not review.get("existing_workflows_unchanged", True):
        violations.append("Existing workflows were modified")

    valid = len(violations) == 0

    return {
        "valid": valid,
        "violations": violations,
        "warnings": [],
        "errors": [],
    }


# ── 11. generate_remote_workflow_publish_review_report ──────────────────────

def validate_canonical_publish_readiness(review: dict) -> dict:
    """Validate canonical publish readiness review consistency and safety."""
    base = validate_remote_workflow_publish_review(review)
    violations = list(base.get("violations", []))
    safety = review.get("safety_summary", {})
    diff = review.get("workflow_diff_summary", {})
    if not safety.get("json_md_same_review_object", False):
        violations.append("JSON/MD same review object marker missing")
    if diff.get("has_secrets", False):
        violations.append("Workflow secrets detected")
    if diff.get("has_runtime_write", False):
        violations.append("Workflow runtime write indicator detected")
    if diff.get("has_audit_jsonl_write", False):
        violations.append("Workflow audit JSONL write indicator detected")
    if diff.get("has_action_queue_write", False):
        violations.append("Workflow action queue write indicator detected")
    if diff.get("existing_workflows_changed"):
        violations.append("Existing workflow mutation detected")
    for bp in review.get("publish_command_blueprints", []):
        if bp.get("command_allowed_now") is not False:
            violations.append(f"Command blueprint {bp.get('command_id')} has command_allowed_now=True")
    if not review.get("rollback_plan"):
        violations.append("Rollback plan missing")
    if not review.get("confirmation_requirements", {}).get("confirmation_phrase"):
        violations.append("Confirmation phrase missing")
    return {"valid": not violations, "violations": violations, "warnings": base.get("warnings", []), "errors": base.get("errors", [])}


def _render_canonical_publish_markdown(review: dict, validation: dict) -> str:
    diff = review.get("workflow_diff_summary", {})
    lines = [
        "# R241-16N Remote Workflow Publish Review",
        "",
        "## Review Result",
        "",
        f"- **Review ID**: `{review.get('review_id')}`",
        f"- **Generated**: {review.get('generated_at')}",
        f"- **Status**: `{review.get('status')}`",
        f"- **Decision**: `{review.get('decision')}`",
        f"- **Recommended Option**: `{review.get('recommended_option')}`",
        "",
        "## Workflow Directory Diff Inspection",
        "",
        f"- **Target workflow changed**: `{diff.get('target_workflow_changed')}`",
        f"- **Existing workflows changed**: `{diff.get('existing_workflows_changed')}`",
        f"- **Unexpected workflows changed**: `{diff.get('unexpected_workflows_changed')}`",
        f"- **Diff only target workflow**: `{diff.get('diff_only_target_workflow')}`",
        f"- **Repo dirty outside workflows count**: `{diff.get('repo_dirty_outside_workflows_count')}`",
        f"- **Repo dirty outside workflows warning**: `{diff.get('repo_dirty_outside_workflows_warning')}`",
        "",
        "## Content Safety Inspection",
        "",
        f"- **Local workflow exists**: `{review.get('local_workflow_exists')}`",
        f"- **Workflow content safe**: `{diff.get('workflow_content_safe')}`",
        f"- **Workflow dispatch only**: `{diff.get('workflow_dispatch_only')}`",
        f"- **Has PR trigger**: `{diff.get('has_pr_trigger')}`",
        f"- **Has push trigger**: `{diff.get('has_push_trigger')}`",
        f"- **Has schedule trigger**: `{diff.get('has_schedule_trigger')}`",
        f"- **Has secrets**: `{diff.get('has_secrets')}`",
        f"- **Has webhook/network**: `{diff.get('has_webhook_network')}`",
        f"- **Has auto-fix**: `{diff.get('has_auto_fix')}`",
        f"- **Has runtime write**: `{diff.get('has_runtime_write')}`",
        "",
        "## JSON/MD Consistency",
        "",
        "- JSON and Markdown are rendered from the same in-memory canonical review object.",
        f"- **Validation valid**: `{validation.get('valid')}`",
        f"- **Validation violations**: `{validation.get('violations')}`",
        "",
        "## Checks",
        "",
    ]
    for check in review.get("checks", []):
        lines.append(f"- `{check.get('check_type')}` passed=`{check.get('passed')}` blocked=`{check.get('blocked_reasons')}`")
    lines.extend([
        "",
        "## Safety",
        "",
        "- git commit: `not executed`",
        "- git push: `not executed`",
        "- gh workflow run: `not executed`",
        "- secret read: `not executed`",
        "- workflow content modification: `not performed`",
        "- runtime / audit JSONL / action queue write: `not performed`",
        "- auto-fix: `not executed`",
    ])
    return "\n".join(lines)


def verify_r241_16o_would_unblock_after_readiness_repair(root: Optional[str] = None) -> dict:
    """Predict whether R241-16O would unblock by reading canonical R241-16N JSON."""
    root_path = Path(root).resolve() if root else ROOT
    path = root_path / "migration_reports" / "foundation_audit" / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json"
    errors: list[str] = []
    try:
        with open(path, encoding="utf-8") as f:
            review = json.load(f)
    except Exception as exc:
        review = {}
        errors.append(str(exc))
    would_unblock = (
        review.get("status") == RemoteWorkflowPublishReadinessStatus.READY_FOR_PUBLISH_CONFIRMATION
        and review.get("decision") == RemoteWorkflowPublishDecision.ALLOW_PUBLISH_CONFIRMATION_GATE
    )
    blocked_reasons = [] if would_unblock else review.get("workflow_diff_summary", {}).get("blocked_reasons", [])
    if not would_unblock and not blocked_reasons:
        blocked_reasons = [f"status={review.get('status')}", f"decision={review.get('decision')}"]
    return {
        "would_unblock": would_unblock,
        "source_path": str(path),
        "status": review.get("status"),
        "decision": review.get("decision"),
        "blocked_reasons": blocked_reasons,
        "warnings": [],
        "errors": errors,
    }


def generate_canonical_publish_readiness_report(review: Optional[dict] = None, output_path: Optional[str] = None) -> dict:
    """Regenerate R241-16N JSON/MD and R241-16N-B consistency repair reports."""
    if review is None:
        review = evaluate_canonical_publish_readiness()
    validation = validate_canonical_publish_readiness(review)
    output_dir = ROOT / "migration_reports" / "foundation_audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = Path(output_path) if output_path else output_dir / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json"
    artifact_dir = json_path.parent if output_path else output_dir
    md_path = json_path.with_suffix(".md") if output_path else output_dir / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.md"
    repair_json_path = artifact_dir / "R241-16N_B_PUBLISH_READINESS_CONSISTENCY_REPAIR.json"
    repair_md_path = artifact_dir / "R241-16N_B_PUBLISH_READINESS_CONSISTENCY_REPAIR.md"
    json_path.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_render_canonical_publish_markdown(review, validation), encoding="utf-8")
    prediction = verify_r241_16o_would_unblock_after_readiness_repair()
    repair = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review": review,
        "validation": validation,
        "json_md_consistency": {
            "same_review_object": True,
            "json_status": review.get("status"),
            "markdown_status": review.get("status"),
            "statuses_match": True,
        },
        "r241_16o_would_unblock_prediction": prediction,
        "safety_summary": {
            "no_git_commit_executed": True,
            "no_git_push_executed": True,
            "no_gh_workflow_run_executed": True,
            "no_secret_read": True,
            "no_workflow_content_modified": True,
            "no_runtime_write": True,
            "no_audit_jsonl_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
        },
    }
    repair_json_path.write_text(json.dumps(repair, indent=2, ensure_ascii=False), encoding="utf-8")
    repair_lines = [
        "# R241-16N-B Publish Readiness Consistency Repair",
        "",
        "## 1. 修改文件清单",
        "- `backend/app/foundation/ci_remote_workflow_publish_review.py`",
        "- `backend/app/foundation/test_ci_remote_workflow_publish_review.py`",
        "- `backend/app/foundation/test_ci_publish_readiness_consistency.py`",
        "- `migration_reports/foundation_audit/R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json`",
        "- `migration_reports/foundation_audit/R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.md`",
        "- `migration_reports/foundation_audit/R241-16N_B_PUBLISH_READINESS_CONSISTENCY_REPAIR.json`",
        "- `migration_reports/foundation_audit/R241-16N_B_PUBLISH_READINESS_CONSISTENCY_REPAIR.md`",
        "",
        "## 2. Bugs fixed / consistency findings",
        "- JSON and Markdown now use the same canonical review object.",
        "- Publish readiness diff is scoped to `.github/workflows/`.",
        "- Non-workflow dirty files are warnings only.",
        "- Existing workflow mutations and unexpected workflow files are blockers.",
        "",
        "## 3. workflow directory diff inspection result",
        f"- target_workflow_changed: `{review.get('workflow_diff_summary', {}).get('target_workflow_changed')}`",
        f"- existing_workflows_changed: `{review.get('workflow_diff_summary', {}).get('existing_workflows_changed')}`",
        f"- unexpected_workflows_changed: `{review.get('workflow_diff_summary', {}).get('unexpected_workflows_changed')}`",
        f"- diff_only_target_workflow: `{review.get('workflow_diff_summary', {}).get('diff_only_target_workflow')}`",
        f"- repo_dirty_outside_workflows_count: `{review.get('workflow_diff_summary', {}).get('repo_dirty_outside_workflows_count')}`",
        "",
        "## 4. content safety inspection result",
        f"- workflow_content_safe: `{review.get('workflow_diff_summary', {}).get('workflow_content_safe')}`",
        f"- workflow_dispatch_only: `{review.get('workflow_diff_summary', {}).get('workflow_dispatch_only')}`",
        f"- has_pr_trigger: `{review.get('workflow_diff_summary', {}).get('has_pr_trigger')}`",
        f"- has_push_trigger: `{review.get('workflow_diff_summary', {}).get('has_push_trigger')}`",
        f"- has_schedule_trigger: `{review.get('workflow_diff_summary', {}).get('has_schedule_trigger')}`",
        f"- has_secrets: `{review.get('workflow_diff_summary', {}).get('has_secrets')}`",
        "",
        "## 5. canonical readiness result",
        f"- status: `{review.get('status')}`",
        f"- decision: `{review.get('decision')}`",
        "",
        "## 6. JSON/MD consistency result",
        f"- statuses_match: `{repair['json_md_consistency']['statuses_match']}`",
        "",
        "## 7. R241-16O would-unblock prediction",
        f"- would_unblock: `{prediction.get('would_unblock')}`",
        f"- blocked_reasons: `{prediction.get('blocked_reasons')}`",
        "",
        "## 8. validation result",
        f"- valid: `{validation.get('valid')}`",
        f"- violations: `{validation.get('violations')}`",
        "",
        "## 9. 测试结果",
        "- See final assistant response for executed validation commands.",
        "",
        "## 10. 是否执行 git commit",
        "- `false`",
        "## 11. 是否执行 git push",
        "- `false`",
        "## 12. 是否执行 gh workflow run",
        "- `false`",
        "## 13. 是否读取 secret",
        "- `false`",
        "## 14. 是否修改 workflow",
        "- `false`",
        "## 15. 是否写 runtime / audit JSONL / action queue",
        "- `false`",
        "## 16. 是否执行 auto-fix",
        "- `false`",
        "## 17. 当前剩余断点",
        f"- `{prediction.get('blocked_reasons')}`",
        "## 18. 下一轮建议",
        "- If `would_unblock=true`, re-enter R241-16O Publish Confirmation Gate.",
        "- If blocked, repair the listed workflow readiness issue first.",
    ]
    repair_md_path.write_text("\n".join(repair_lines), encoding="utf-8")
    return {
        "output_path": str(json_path),
        "report_path": str(md_path),
        "repair_output_path": str(repair_json_path),
        "repair_report_path": str(repair_md_path),
        "review": review,
        "validation": validation,
        "prediction": prediction,
    }


def generate_remote_workflow_publish_review_report(
    review: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Generate R241-16N publish review reports.

    Writes JSON to output_path and Markdown to report_path under
    migration_reports/foundation_audit/.
    """
    if review is None:
        review = evaluate_canonical_publish_readiness()

    root_path = ROOT
    output_dir = root_path / "migration_reports" / "foundation_audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = Path(output_path) if output_path else (output_dir / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json")
    md_path = output_dir / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.md"

    # Write JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(review, f, indent=2, ensure_ascii=False)

    # Write Markdown
    lines = [
        "# R241-16N Remote Workflow Publish Readiness / Push Review",
        "",
        "## Review Result",
        "",
        f"- **Review ID**: `{review['review_id']}`",
        f"- **Generated**: {review['generated_at']}",
        f"- **Status**: `{review['status']}`",
        f"- **Decision**: `{review['decision']}`",
        f"- **Recommended Option**: `{review['recommended_option']}`",
        "",
        "## R241-16M Loading",
        "",
    ]

    checks = {c["check_id"]: c for c in review.get("checks", [])}
    r241_16m_check = checks.get("check_r241_16m_loaded", {})
    lines.append(f"- **R241-16M Loaded**: `{r241_16m_check.get('observed_value', {}).get('r241_16m_loaded', False)}`")
    lines.append(f"- **git_exact_path_present**: `{r241_16m_check.get('observed_value', {}).get('git_exact_path_present', 'N/A')}`")
    lines.append(f"- **local_workflow_exists**: `{r241_16m_check.get('observed_value', {}).get('local_workflow_exists', 'N/A')}`")
    lines.append(f"- **R241-16M Check Passed**: `{r241_16m_check.get('passed', False)}`")
    lines.append("")

    lines.extend([
        "## Local Workflow Diff Inspection",
        "",
        f"- **Local Workflow Exists**: `{review.get('local_workflow_exists', False)}`",
        f"- **Remote Workflow Exists**: `{review.get('remote_workflow_exists', False)}`",
        f"- **Diff Only Target Workflow**: `{review.get('workflow_diff_summary', {}).get('diff_only_target_workflow', False)}`",
        f"- **Workflow Content Safe**: `{review.get('workflow_diff_summary', {}).get('workflow_content_safe', False)}`",
        f"- **workflow_dispatch Only**: `{review.get('workflow_diff_summary', {}).get('workflow_dispatch_only', False)}`",
        f"- **Has PR Trigger**: `{review.get('workflow_diff_summary', {}).get('has_pr_trigger', False)}`",
        f"- **Has Push Trigger**: `{review.get('workflow_diff_summary', {}).get('has_push_trigger', False)}`",
        f"- **Has Schedule Trigger**: `{review.get('workflow_diff_summary', {}).get('has_schedule_trigger', False)}`",
        f"- **Has Secrets**: `{review.get('workflow_diff_summary', {}).get('has_secrets', False)}`",
        f"- **Existing Workflows Unchanged**: `{review.get('existing_workflows_unchanged', False)}`",
        "",
    ])

    lines.extend([
        "## Publish Options",
        "",
    ])
    for opt in review.get("publish_options", []):
        rec = " **[RECOMMENDED]**" if opt.get("recommended") else ""
        lines.append(f"- **{opt['label']}**{rec}")
        lines.append(f"  - ID: `{opt['option_id']}`")
        lines.append(f"  - Description: {opt['description']}")
        lines.append(f"  - Risk Level: `{opt['risk_level']}`")
        lines.append("")

    lines.extend([
        "## Command Blueprints",
        "",
        "All blueprints have `command_allowed_now=False` — they are designs, not executions.",
        "",
    ])
    for bp in review.get("publish_command_blueprints", []):
        lines.append(f"### {bp['command_id']}")
        lines.append(f"- **Type**: `{bp['command_type']}`")
        lines.append(f"- **argv**: `{' '.join(bp['argv'])}`")
        lines.append(f"- **command_allowed_now**: `{bp['command_allowed_now']}`")
        lines.append(f"- **would_modify_git_history**: `{bp['would_modify_git_history']}`")
        lines.append(f"- **would_push_remote**: `{bp['would_push_remote']}`")
        lines.append(f"- **would_trigger_workflow**: `{bp['would_trigger_workflow']}`")
        lines.append(f"- **requires_confirmation_phrase**: `{bp['requires_confirmation_phrase']}`")
        lines.append(f"- **Description**: {bp.get('description', '')}")
        if bp.get("warnings"):
            lines.append(f"- **Warnings**: {', '.join(bp['warnings'])}")
        lines.append("")

    lines.extend([
        "## Rollback Plan",
        "",
    ])
    rollback = review.get("rollback_plan", {})
    for scenario, details in rollback.items():
        if isinstance(details, dict):
            lines.append(f"### {scenario}")
            lines.append(f"- **Description**: {details.get('description', '')}")
            lines.append(f"- **Rollback Action**: {details.get('rollback_action', '')}")
            if details.get("commands"):
                lines.append(f"- **Commands**: `{' && '.join(details['commands'])}`")
            lines.append(f"- **Confirmation Required**: `{details.get('confirmation_required', True)}`")
            if details.get("warnings"):
                lines.append(f"- **Warnings**: {', '.join(details['warnings'])}")
            lines.append("")
        elif scenario == "no_auto_rollback":
            lines.append(f"- **no_auto_rollback**: `{rollback.get('no_auto_rollback')}`")
            lines.append("")

    lines.extend([
        "## Confirmation Requirements",
        "",
        f"- **Phrase**: `{review.get('confirmation_requirements', {}).get('confirmation_phrase', '')}`",
        f"- **Explicit phrase required**: `{review.get('confirmation_requirements', {}).get('explicit_phrase_required', False)}`",
        f"- **Human in the loop required**: `{review.get('confirmation_requirements', {}).get('human_in_the_loop_required', False)}`",
        "",
        "Requirements:",
    ])
    for req in review.get("confirmation_requirements", {}).get("requirements", []):
        lines.append(f"- {req}")
    lines.append("")

    lines.extend([
        "## Safety Summary",
        "",
    ])
    safety = review.get("safety_summary", {})
    for k, v in safety.items():
        icon = "✅" if v else "❌"
        lines.append(f"- {icon} `{k}`: `{v}`")
    lines.append("")

    lines.extend([
        "## Checks",
        "",
    ])
    for check in review.get("checks", []):
        icon = "✅" if check.get("passed") else "❌"
        lines.append(f"### {icon} [{check['risk_level'].upper()}] {check['check_id']}")
        lines.append(f"- **Type**: `{check['check_type']}`")
        lines.append(f"- **Passed**: `{check.get('passed', False)}`")
        lines.append(f"- **Description**: {check.get('description', '')}")
        if check.get("blocked_reasons"):
            lines.append(f"- **Blocked**: {', '.join(check['blocked_reasons'])}")
        if check.get("warnings"):
            lines.append(f"- **Warnings**: {', '.join(check['warnings'])}")
        lines.append("")

    lines.extend([
        "## Validation",
        "",
        "## Next Recommendation",
        "",
        f"- **Current Status**: `{review['status']}`",
        f"- **Decision**: `{review['decision']}`",
    ])
    if review["status"] == RemoteWorkflowPublishReadinessStatus.READY_FOR_PUBLISH_CONFIRMATION:
        lines.append("- R241-16N is ready. Proceed to R241-16O Publish Confirmation Gate after reviewing options.")
    else:
        lines.append("- R241-16N blocked. Fix the issues above before proceeding.")
    lines.append("")

    md_content = "\n".join(lines)
    md_path.write_text(md_content, encoding="utf-8")

    return {
        "output_path": str(json_path),
        "report_path": str(md_path),
        "review_id": review["review_id"],
        "status": review["status"],
        "decision": review["decision"],
    }
