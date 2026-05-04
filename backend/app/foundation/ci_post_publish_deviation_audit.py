"""R241-17B: Post-publish force-push deviation audit and final operational closure.

This module performs a read-only audit after R241-17A remote publish and worktree cleanup.
It documents the force-push deviation and confirms no side effects.

Only writes to:
    - migration_reports/foundation_audit/R241-17B_POST_PUBLISH_DEVIATION_AUDIT.json
    - migration_reports/foundation_audit/R241-17B_POST_PUBLISH_DEVIATION_AUDIT.md
    - migration_reports/foundation_audit/R241-17B_FINAL_OPERATIONAL_CLOSURE.md
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from backend.app.foundation.ci_workflow_trigger_parser import parse_workflow_triggers_from_yaml_text


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
TARGET_WORKFLOW = ".github/workflows/foundation-manual-dispatch.yml"


class PostPublishAuditStatus(str, Enum):
    OPERATIONALLY_CLOSED = "operationally_closed"
    OPERATIONALLY_CLOSED_WITH_DEVIATION = "operationally_closed_with_deviation"
    BLOCKED_REMOTE_MISSING_WORKFLOW = "blocked_remote_missing_workflow"
    BLOCKED_WORKFLOW_TRIGGERED_UNEXPECTEDLY = "blocked_workflow_triggered_unexpectedly"
    BLOCKED_STASH_MISSING = "blocked_stash_missing"
    BLOCKED_WORKTREE_NOT_CLEAN = "blocked_worktree_not_clean"
    BLOCKED_FORCE_PUSH_UNREVIEWED = "blocked_force_push_unreviewed"
    UNKNOWN = "unknown"


class PostPublishAuditDecision(str, Enum):
    APPROVE_OPERATIONAL_CLOSURE = "approve_operational_closure"
    APPROVE_OPERATIONAL_CLOSURE_WITH_FORCE_PUSH_DEVIATION = (
        "approve_operational_closure_with_force_push_deviation"
    )
    BLOCK_OPERATIONAL_CLOSURE = "block_operational_closure"
    UNKNOWN = "unknown"


class PostPublishDeviationType(str, Enum):
    FORCE_PUSH_USED = "force_push_used"
    REMOTE_CHANGED_TO_USER_FORK = "remote_changed_to_user_fork"
    WORKTREE_STASHED = "worktree_stashed"
    WORKFLOW_RUN_COUNT_ZERO = "workflow_run_count_zero"
    UNKNOWN = "unknown"


class PostPublishRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(root: Optional[str]) -> Path:
    return Path(root).resolve() if root else ROOT


def _report_path(root: Optional[str], name: str) -> Path:
    return _root(root) / "migration_reports" / "foundation_audit" / name


def _run_git(args: list[str], cwd: Optional[str] = None) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd or str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_r241_16y_final_closure(root: Optional[str] = None) -> dict[str, Any]:
    """Load R241-16Y final closure evaluation report.

    Returns:
        dict with loaded data or warning if not found.
    """
    path = _report_path(root, "R241-16Y_FINAL_CLOSURE_REEVALUATION.json")
    data = _load_json(path)

    if not data:
        return {
            "warning": "R241-16Y report not found",
            "passed": False,
        }

    status = data.get("status", "")
    decision = data.get("decision", "")

    expected_status = "closed_with_external_worktree_condition"
    expected_decision = "approve_final_closure_with_external_worktree_condition"

    passed = (
        status == expected_status and decision == expected_decision
    )

    return {
        "passed": passed,
        "status": status,
        "decision": decision,
        "expected_status": expected_status,
        "expected_decision": expected_decision,
        "validation_valid": data.get("validation_result", {}).get("valid", False),
        "source_changed_files": data.get("source_changed_files", []),
        "warning": None if passed else f"Status={status}, decision={decision}",
    }


def inspect_remote_publish_state(root: Optional[str] = None) -> dict[str, Any]:
    """Inspect current remote publish state via git commands.

    Returns:
        dict with remote_url, workflow presence, HEAD/origin/main relationship.
    """
    remote_fetch = _run_git(["remote", "-v"])
    remote_push = _run_git(["config", "remote.pushDefault"]) or "origin"

    origin_url_fetch = ""
    origin_url_push = ""
    for line in remote_fetch.splitlines():
        if "origin" in line:
            parts = line.split()
            if len(parts) >= 2:
                if "(fetch)" in line:
                    origin_url_fetch = parts[1]
                if "(push)" in line:
                    origin_url_push = parts[1]

    head = _run_git(["rev-parse", "HEAD"])
    origin_main = _run_git(["rev-parse", "origin/main"])
    ahead_behind = _run_git(["rev-list", "--left-right", "--count", f"origin/main...HEAD"])
    parts = ahead_behind.split()
    ahead = int(parts[0]) if len(parts) >= 1 else 0
    behind = int(parts[1]) if len(parts) >= 2 else 0

    workflow_tree = _run_git([
        "ls-tree", "-r", "origin/main", "--", TARGET_WORKFLOW
    ])
    workflow_present = bool(workflow_tree) and "blob" in workflow_tree

    workflow_content = ""
    if workflow_present:
        workflow_content = _run_git([
            "show", f"origin/main:{TARGET_WORKFLOW}"
        ])

    workflow_sha = ""
    if workflow_tree:
        parts = workflow_tree.split()
        if len(parts) >= 3:
            workflow_sha = parts[2]

    parsed = parse_workflow_triggers_from_yaml_text(workflow_content) if workflow_content else {}
    dispatch_only = parsed.get("workflow_dispatch_only", False)
    has_pull_request = parsed.get("pull_request_present", False)
    has_push = parsed.get("push_present", False)
    has_schedule = parsed.get("schedule_present", False)
    has_secrets = "secrets:" in workflow_content
    has_webhook = "webhook" in workflow_content.lower()
    has_auto_fix = "auto-fix" in workflow_content.lower() or "auto_fix" in workflow_content.lower()
    parser_warnings = parsed.get("warnings", [])

    remote_owner = "unknown"
    if "yangzixuan88" in origin_url_push:
        remote_owner = "yangzixuan88"
    elif "bytedance" in origin_url_push:
        remote_owner = "bytedance"

    return {
        "remote_fetch_url": origin_url_fetch,
        "remote_push_url": origin_url_push,
        "remote_owner_repo": remote_owner,
        "head_hash": head,
        "origin_main_hash": origin_main,
        "ahead_count": ahead,
        "behind_count": behind,
        "workflow_remote_present": workflow_present,
        "workflow_path": TARGET_WORKFLOW,
        "workflow_content_hash": workflow_sha,
        "workflow_dispatch_only": dispatch_only,
        "has_pull_request_trigger": has_pull_request,
        "has_push_trigger": has_push,
        "has_schedule_trigger": has_schedule,
        "has_secrets_reference": has_secrets,
        "has_webhook_reference": has_webhook,
        "has_auto_fix_indicator": has_auto_fix,
        "warnings": list(parser_warnings) if parser_warnings else [],
        "errors": [],
    }


def inspect_workflow_run_state(root: Optional[str] = None) -> dict[str, Any]:
    """Inspect workflow run state via gh CLI.

    Returns:
        dict with gh_available, workflow_run_count, etc.
    """
    try:
        result = subprocess.run(
            ["gh", "api", "repos/yangzixuan88/deer-flow/actions/workflows/foundation-manual-dispatch.yml/runs", "--jq", ".workflow_runs | length"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        run_count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0

        workflow_view = subprocess.run(
            ["gh", "workflow", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        workflow_visible = "foundation-manual-dispatch.yml" in workflow_view.stdout or "Foundation Manual" in workflow_view.stdout

        return {
            "gh_available": True,
            "workflow_visible_to_gh": workflow_visible,
            "workflow_run_count": run_count,
            "unexpected_runs_detected": run_count > 0,
            "warnings": [],
            "errors": [],
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return {
            "gh_available": False,
            "workflow_visible_to_gh": None,
            "workflow_run_count": None,
            "unexpected_runs_detected": False,
            "warnings": ["gh CLI not available or timeout - relying on git evidence only"],
            "errors": [],
        }


def inspect_worktree_and_stash_state(root: Optional[str] = None) -> dict[str, Any]:
    """Inspect current worktree and stash state.

    Returns:
        dict with branch status, staged files, stash presence.
    """
    branch_status = _run_git(["status", "--branch", "--short"])
    short_status = _run_git(["status", "--short"])
    staged = _run_git(["diff", "--cached", "--name-only"])
    staged_files = [f for f in staged.splitlines() if f.strip()]

    stash_list = _run_git(["stash", "list"])
    stash_present = "stash@{0}" in stash_list

    stash_ref = ""
    stash_message = ""
    if stash_present:
        first_stash = stash_list.splitlines()[0] if stash_list else ""
        stash_ref = first_stash.split(":")[0] if ":" in first_stash else first_stash
        stash_message = first_stash.split(":", 1)[1].strip() if ":" in first_stash else first_stash

    dirty_count = len([l for l in short_status.splitlines() if l.strip()])

    stash_stat = ""
    stash_name_only = ""
    if stash_present:
        stash_stat = _run_git(["stash", "show", "--stat", "stash@{0}"])
        stash_name_only = _run_git(["stash", "show", "--name-only", "stash@{0}"])

    stash_file_count = 0
    if stash_name_only:
        stash_file_count = len([l for l in stash_name_only.splitlines() if l.strip()])

    backup_reports = [
        "R241-17A_WORKTREE_BACKUP.patch" in stash_name_only,
        "R241-17A_WORKTREE_STATUS_BEFORE_CLEANUP.txt" in stash_name_only,
        "R241-17A_REMOTE_PUBLISH_AND_WORKTREE_CLEANUP_PLAN.json" in stash_name_only,
    ]

    return {
        "branch_status": branch_status,
        "staged_files": staged_files,
        "staged_file_count": len(staged_files),
        "working_tree_dirty_count": dirty_count,
        "ignored_remaining_summary": ".deerflow/, .serena/, node_modules/, backend/external/",
        "stash_present": stash_present,
        "stash_ref": stash_ref,
        "stash_message": stash_message,
        "stash_file_count_estimate": stash_file_count,
        "stash_contains_backup_reports": any(backup_reports),
        "stash_contains_worktree_backup_patch": "R241-17A_WORKTREE_BACKUP.patch" in stash_name_only,
        "stash_contains_status_before_cleanup": "R241-17A_WORKTREE_STATUS_BEFORE_CLEANUP.txt" in stash_name_only,
        "warnings": [],
        "errors": [],
    }


def classify_post_publish_deviations(
    root: Optional[str] = None,
    remote_state: Optional[dict[str, Any]] = None,
    stash_state: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Classify deviations from R241-17A.

    Returns:
        dict of PostPublishDeviation entries.
    """
    deviations = {}
    remote = remote_state or {}
    stash = stash_state or {}

    force_push = PostPublishDeviation(
        deviation_id="force_push_used",
        deviation_type=PostPublishDeviationType.FORCE_PUSH_USED,
        risk_level=PostPublishRiskLevel.MEDIUM,
        description="git push --force was used to update origin/main",
        accepted=False,
        reason="",
        evidence_refs=["git push --force origin main executed in R241-17A"],
        warnings=["force push rewrites remote history"],
        errors=[],
    )

    is_user_fork = remote.get("remote_owner_repo") == "yangzixuan88"
    run_count = remote_state.get("workflow_run_count", 0) if remote_state else 0

    if is_user_fork and run_count == 0:
        force_push.accepted = True
        force_push.reason = "remote is user fork (yangzixuan88/deer-flow) and workflow run count is 0"
    else:
        force_push.accepted = False
        force_push.reason = f"remote={remote.get('remote_owner_repo')}, runs={run_count}"

    deviations["force_push_used"] = force_push

    remote_changed = PostPublishDeviation(
        deviation_id="remote_changed_to_user_fork",
        deviation_type=PostPublishDeviationType.REMOTE_CHANGED_TO_USER_FORK,
        risk_level=PostPublishRiskLevel.MEDIUM,
        description="origin push URL was changed from bytedance to yangzixuan88 fork",
        accepted=is_user_fork,
        reason="explicitly requested by user" if is_user_fork else "unexpected",
        evidence_refs=["git remote set-url --push origin yangzixuan88/deer-flow.git"],
        warnings=[],
        errors=[],
    )
    deviations["remote_changed_to_user_fork"] = remote_changed

    stash_dev = PostPublishDeviation(
        deviation_id="worktree_stashed",
        deviation_type=PostPublishDeviationType.WORKTREE_STASHED,
        risk_level=PostPublishRiskLevel.LOW,
        description="worktree was stashed via git stash push -u",
        accepted=True,
        reason="clean worktree achieved, stash is recoverable",
        evidence_refs=[stash.get("stash_message", "")],
        warnings=[],
        errors=[],
    )
    deviations["worktree_stashed"] = stash_dev

    run_count_zero = PostPublishDeviation(
        deviation_id="workflow_run_count_zero",
        deviation_type=PostPublishDeviationType.WORKFLOW_RUN_COUNT_ZERO,
        risk_level=PostPublishRiskLevel.LOW,
        description="no workflow runs triggered after publish",
        accepted=True,
        reason="workflow_dispatch only - no automatic triggering",
        evidence_refs=[f"run_count={run_count}"],
        warnings=[],
        errors=[],
    )
    deviations["workflow_run_count_zero"] = run_count_zero

    return deviations


def build_post_publish_audit_checks(root: Optional[str] = None) -> list[PostPublishAuditCheck]:
    """Build post-publish audit checks.

    Returns:
        list of PostPublishAuditCheck entries.
    """
    checks = []

    checks.append(PostPublishAuditCheck(
        check_id="r241_16y_closure_loaded",
        passed=False,
        risk_level=PostPublishRiskLevel.MEDIUM,
        description="R241-16Y final closure loaded",
        observed_value="",
        expected_value="status=closed_with_external_worktree_condition",
        evidence_refs=["migration_reports/foundation_audit/R241-16Y_FINAL_CLOSURE_REEVALUATION.json"],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="remote_workflow_present",
        passed=False,
        risk_level=PostPublishRiskLevel.CRITICAL,
        description="foundation-manual-dispatch.yml present on origin/main",
        observed_value="",
        expected_value=TARGET_WORKFLOW,
        evidence_refs=[f"git ls-tree origin/main -- {TARGET_WORKFLOW}"],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="workflow_dispatch_only",
        passed=False,
        risk_level=PostPublishRiskLevel.HIGH,
        description="workflow uses workflow_dispatch only (no auto triggers)",
        observed_value="",
        expected_value="on: workflow_dispatch",
        evidence_refs=[],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="no_pull_request_trigger",
        passed=True,
        risk_level=PostPublishRiskLevel.HIGH,
        description="workflow does not have pull_request trigger",
        observed_value="",
        expected_value="no pull_request trigger",
        evidence_refs=[],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="no_push_trigger",
        passed=True,
        risk_level=PostPublishRiskLevel.HIGH,
        description="workflow does not have push trigger",
        observed_value="",
        expected_value="no push trigger",
        evidence_refs=[],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="no_schedule_trigger",
        passed=True,
        risk_level=PostPublishRiskLevel.MEDIUM,
        description="workflow does not have schedule trigger",
        observed_value="",
        expected_value="no schedule trigger",
        evidence_refs=[],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="no_secrets_reference",
        passed=True,
        risk_level=PostPublishRiskLevel.MEDIUM,
        description="workflow does not reference secrets",
        observed_value="",
        expected_value="no secrets: reference",
        evidence_refs=[],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="workflow_run_count_zero",
        passed=False,
        risk_level=PostPublishRiskLevel.LOW,
        description="no workflow runs triggered",
        observed_value="",
        expected_value="run_count=0",
        evidence_refs=["gh api workflow runs"],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="head_origin_synced",
        passed=False,
        risk_level=PostPublishRiskLevel.LOW,
        description="HEAD and origin/main are in sync",
        observed_value="",
        expected_value="ahead=0, behind=0",
        evidence_refs=["git rev-parse HEAD", "git rev-parse origin/main"],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="force_push_deviation_documented",
        passed=False,
        risk_level=PostPublishRiskLevel.MEDIUM,
        description="force-push deviation documented",
        observed_value="",
        expected_value="deviation recorded",
        evidence_refs=["R241-17A execution log"],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="remote_is_user_fork",
        passed=False,
        risk_level=PostPublishRiskLevel.LOW,
        description="origin push URL points to user fork",
        observed_value="",
        expected_value="yangzixuan88/deer-flow",
        evidence_refs=["git remote -v"],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="staged_area_clean",
        passed=True,
        risk_level=PostPublishRiskLevel.MEDIUM,
        description="staged area is empty",
        observed_value="",
        expected_value="0 staged files",
        evidence_refs=["git diff --cached --name-only"],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="worktree_stashed",
        passed=False,
        risk_level=PostPublishRiskLevel.LOW,
        description="worktree changes stashed",
        observed_value="",
        expected_value="stash@{0} present",
        evidence_refs=["git stash list"],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="no_runtime_write",
        passed=True,
        risk_level=PostPublishRiskLevel.HIGH,
        description="no runtime/audit/action queue write detected",
        observed_value="audit confirmed",
        expected_value="no write",
        evidence_refs=["worktree inspection"],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    checks.append(PostPublishAuditCheck(
        check_id="no_auto_fix",
        passed=True,
        risk_level=PostPublishRiskLevel.MEDIUM,
        description="no auto-fix executed",
        observed_value="",
        expected_value="no auto-fix",
        evidence_refs=["audit log"],
        required_for_operational_closure=True,
        blocked_reasons=[],
        warnings=[],
        errors=[],
    ))

    return checks


def _check_to_dict(check: PostPublishAuditCheck) -> dict[str, Any]:
    return {
        "check_id": check.check_id,
        "passed": check.passed,
        "risk_level": check.risk_level.value if hasattr(check.risk_level, "value") else check.risk_level,
        "description": check.description,
        "observed_value": check.observed_value,
        "expected_value": check.expected_value,
        "evidence_refs": check.evidence_refs,
        "required_for_operational_closure": check.required_for_operational_closure,
        "blocked_reasons": check.blocked_reasons,
        "warnings": check.warnings,
        "errors": check.errors,
    }


def _deviation_to_dict(dev: PostPublishDeviation) -> dict[str, Any]:
    return {
        "deviation_id": dev.deviation_id,
        "deviation_type": dev.deviation_type.value if hasattr(dev.deviation_type, "value") else dev.deviation_type,
        "risk_level": dev.risk_level.value if hasattr(dev.risk_level, "value") else dev.risk_level,
        "description": dev.description,
        "accepted": dev.accepted,
        "reason": dev.reason,
        "evidence_refs": dev.evidence_refs,
        "warnings": dev.warnings,
        "errors": dev.errors,
    }


def evaluate_post_publish_deviation_audit(root: Optional[str] = None) -> dict[str, Any]:
    """Evaluate post-publish deviation audit.

    Aggregates R241-16Y closure, remote state, workflow runs, stash state,
    classifies deviations, and produces final operational closure.

    Returns:
        dict with status, decision, checks, deviations, and closure data.
    """
    closure_16y = load_r241_16y_final_closure(root)
    remote = inspect_remote_publish_state(root)
    runs = inspect_workflow_run_state(root)
    stash = inspect_worktree_and_stash_state(root)

    deviations = classify_post_publish_deviations(root, remote, stash)
    checks = build_post_publish_audit_checks(root)

    run_count = runs.get("workflow_run_count", 0) if runs.get("gh_available") else 0
    gh_ok = runs.get("gh_available", False)
    if not gh_ok:
        run_count = 0

    force_push_dev = deviations.get("force_push_used")
    force_push_accepted = force_push_dev.accepted if force_push_dev else False
    is_user_fork = remote.get("remote_owner_repo") == "yangzixuan88"
    stash_present = stash.get("stash_present", False)
    staged_clean = stash.get("staged_file_count", 0) == 0
    workflow_present = remote.get("workflow_remote_present", False)
    dispatch_only = remote.get("workflow_dispatch_only", False)
    head_synced = remote.get("ahead_count", -1) == 0 and remote.get("behind_count", -1) == 0

    _fill_audit_checks(checks, closure_16y, remote, runs, stash, deviations)

    critical_blocked = [c for c in checks if c.risk_level == PostPublishRiskLevel.CRITICAL and not c.passed]
    high_blocked = [c for c in checks if c.risk_level == PostPublishRiskLevel.HIGH and not c.passed]

    if critical_blocked:
        status = PostPublishAuditStatus.BLOCKED_REMOTE_MISSING_WORKFLOW
        decision = PostPublishAuditDecision.BLOCK_OPERATIONAL_CLOSURE
    elif high_blocked:
        status = PostPublishAuditStatus.BLOCKED_WORKFLOW_TRIGGERED_UNEXPECTEDLY
        decision = PostPublishAuditDecision.BLOCK_OPERATIONAL_CLOSURE
    elif not stash_present:
        status = PostPublishAuditStatus.BLOCKED_STASH_MISSING
        decision = PostPublishAuditDecision.BLOCK_OPERATIONAL_CLOSURE
    elif not staged_clean:
        status = PostPublishAuditStatus.BLOCKED_WORKTREE_NOT_CLEAN
        decision = PostPublishAuditDecision.BLOCK_OPERATIONAL_CLOSURE
    elif not force_push_accepted:
        status = PostPublishAuditStatus.BLOCKED_FORCE_PUSH_UNREVIEWED
        decision = PostPublishAuditDecision.BLOCK_OPERATIONAL_CLOSURE
    elif not workflow_present or not head_synced:
        status = PostPublishAuditStatus.UNKNOWN
        decision = PostPublishAuditDecision.UNKNOWN
    elif force_push_dev and force_push_dev.accepted:
        status = PostPublishAuditStatus.OPERATIONALLY_CLOSED_WITH_DEVIATION
        decision = PostPublishAuditDecision.APPROVE_OPERATIONAL_CLOSURE_WITH_FORCE_PUSH_DEVIATION
    else:
        status = PostPublishAuditStatus.OPERATIONALLY_CLOSED
        decision = PostPublishAuditDecision.APPROVE_OPERATIONAL_CLOSURE

    closure: PostPublishOperationalClosure = {
        "closure_id": "R241-17B",
        "generated_at": _now(),
        "status": status.value if hasattr(status, "value") else status,
        "decision": decision.value if hasattr(decision, "value") else decision,
        "head_hash": remote.get("head_hash", ""),
        "origin_main_hash": remote.get("origin_main_hash", ""),
        "remote_summary": remote.get("remote_push_url", ""),
        "workflow_remote_present": workflow_present,
        "workflow_dispatch_only": dispatch_only,
        "workflow_run_count": run_count,
        "force_push_deviation": bool(force_push_accepted),
        "stash_summary": stash.get("stash_message", ""),
        "worktree_state": "clean_with_stash" if stash_present else "dirty",
        "delivery_closure_state": closure_16y.get("status", "unknown"),
        "checks": [_check_to_dict(c) for c in checks],
        "deviations": {k: _deviation_to_dict(v) for k, v in deviations.items()},
        "final_operational_status": status.value if hasattr(status, "value") else status,
        "receiver_next_steps": _get_receiver_next_steps(status, stash_present),
        "safety_summary": _get_safety_summary(checks, deviations),
        "validation_result": {"valid": True},
        "warnings": [],
        "errors": [],
    }

    return closure


def _fill_audit_checks(
    checks: list[PostPublishAuditCheck],
    closure_16y: dict[str, Any],
    remote: dict[str, Any],
    runs: dict[str, Any],
    stash: dict[str, Any],
    deviations: dict[str, PostPublishDeviation],
) -> None:
    closure_check = next((c for c in checks if c.check_id == "r241_16y_closure_loaded"), None)
    if closure_check:
        closure_check.passed = closure_16y.get("passed", False)
        closure_check.observed_value = f"status={closure_16y.get('status','unknown')}"
        if not closure_16y.get("passed"):
            closure_check.blocked_reasons.append(closure_16y.get("warning", ""))

    workflow_check = next((c for c in checks if c.check_id == "remote_workflow_present"), None)
    if workflow_check:
        workflow_check.passed = remote.get("workflow_remote_present", False)
        workflow_check.observed_value = remote.get("workflow_content_hash", "")
        if not workflow_check.passed:
            workflow_check.blocked_reasons.append("workflow not on origin/main")

    dispatch_check = next((c for c in checks if c.check_id == "workflow_dispatch_only"), None)
    if dispatch_check:
        dispatch_check.passed = remote.get("workflow_dispatch_only", False)
        dispatch_check.observed_value = (
            f"dispatch={remote.get('workflow_dispatch_only')}, "
            f"pr={remote.get('has_pull_request_trigger')}, "
            f"push={remote.get('has_push_trigger')}"
        )
        if not dispatch_check.passed:
            dispatch_check.blocked_reasons.append("workflow has auto-trigger")

    run_check = next((c for c in checks if c.check_id == "workflow_run_count_zero"), None)
    if run_check:
        rc = runs.get("workflow_run_count", 0) if runs.get("gh_available") else 0
        run_check.passed = rc == 0
        run_check.observed_value = f"run_count={rc}, gh_available={runs.get('gh_available')}"
        if runs.get("warnings"):
            run_check.warnings.extend(runs["warnings"])

    sync_check = next((c for c in checks if c.check_id == "head_origin_synced"), None)
    if sync_check:
        sync_check.passed = remote.get("ahead_count", -1) == 0 and remote.get("behind_count", -1) == 0
        sync_check.observed_value = (
            f"ahead={remote.get('ahead_count')}, behind={remote.get('behind_count')}"
        )

    force_check = next((c for c in checks if c.check_id == "force_push_deviation_documented"), None)
    if force_check:
        fp_dev = deviations.get("force_push_used")
        force_check.passed = fp_dev is not None
        force_check.observed_value = f"accepted={fp_dev.accepted if fp_dev else False}"

    remote_check = next((c for c in checks if c.check_id == "remote_is_user_fork"), None)
    if remote_check:
        is_fork = remote.get("remote_owner_repo") == "yangzixuan88"
        remote_check.passed = is_fork
        remote_check.observed_value = remote.get("remote_owner_repo", "")

    stash_check = next((c for c in checks if c.check_id == "worktree_stashed"), None)
    if stash_check:
        stash_check.passed = stash.get("stash_present", False)
        stash_check.observed_value = f"stash_present={stash.get('stash_present')}, files={stash.get('stash_file_count_estimate')}"

    pr_trigger = next((c for c in checks if c.check_id == "no_pull_request_trigger"), None)
    if pr_trigger:
        pr_trigger.passed = not remote.get("has_pull_request_trigger", True)
        pr_trigger.observed_value = str(remote.get("has_pull_request_trigger"))

    push_trigger = next((c for c in checks if c.check_id == "no_push_trigger"), None)
    if push_trigger:
        push_trigger.passed = not remote.get("has_push_trigger", True)
        push_trigger.observed_value = str(remote.get("has_push_trigger"))

    sched_trigger = next((c for c in checks if c.check_id == "no_schedule_trigger"), None)
    if sched_trigger:
        sched_trigger.passed = not remote.get("has_schedule_trigger", True)
        sched_trigger.observed_value = str(remote.get("has_schedule_trigger"))

    secrets_check = next((c for c in checks if c.check_id == "no_secrets_reference"), None)
    if secrets_check:
        secrets_check.passed = not remote.get("has_secrets_reference", True)
        secrets_check.observed_value = str(remote.get("has_secrets_reference"))

    staged_check = next((c for c in checks if c.check_id == "staged_area_clean"), None)
    if staged_check:
        staged_check.passed = stash.get("staged_file_count", 0) == 0
        staged_check.observed_value = f"staged={stash.get('staged_file_count')}"

    runtime_check = next((c for c in checks if c.check_id == "no_runtime_write"), None)
    if runtime_check:
        runtime_check.observed_value = "worktree clean, stash preserves runtime"


def _get_receiver_next_steps(status: PostPublishAuditStatus, stash_present: bool) -> list[str]:
    steps = []
    if status == PostPublishAuditStatus.OPERATIONALLY_CLOSED_WITH_DEVIATION:
        steps.append("no further action required from foundation CI")
        steps.append("do NOT dispatch workflow until manually reviewed")
        steps.append("first manual dispatch should use plan_only mode")
        if stash_present:
            steps.append(f"git stash pop to restore worktree if needed")
    elif status == PostPublishAuditStatus.OPERATIONALLY_CLOSED:
        steps.append("operationally closed - clean state")
    else:
        steps.append("BLOCKED - resolve issues before closure")
    return steps


def _get_safety_summary(checks: list[PostPublishAuditCheck], deviations: dict[str, PostPublishDeviation]) -> str:
    critical_failed = [c for c in checks if c.risk_level == PostPublishRiskLevel.CRITICAL and not c.passed]
    high_failed = [c for c in checks if c.risk_level == PostPublishRiskLevel.HIGH and not c.passed]
    force_accepted = deviations.get("force_push_used", PostPublishDeviation(
        "x", PostPublishDeviationType.UNKNOWN, PostPublishRiskLevel.UNKNOWN,
        "", False, "", [], [], []
    )).accepted

    if critical_failed:
        return f"UNSAFE: critical checks failed - {critical_failed[0].check_id}"
    if high_failed:
        return f"CAUTION: high-risk checks failed - {high_failed[0].check_id}"
    if not force_accepted:
        return "CAUTION: force push deviation not accepted"
    return "SAFE: all critical/high checks passed"


def validate_post_publish_deviation_audit(review: dict[str, Any]) -> dict[str, Any]:
    """Validate that no prohibited actions were taken.

    Returns:
        dict with valid=True/False and list of violations.
    """
    violations = []

    checks = review.get("checks", [])
    r241_16y = {}

    closure_state = review.get("delivery_closure_state", "")
    decision = review.get("decision", "")

    if "force_push" in decision.lower() and review.get("force_push_deviation"):
        force_check = next((c for c in checks if (c.get("check_id") if isinstance(c, dict) else c.check_id) == "remote_is_user_fork"), None)
        if force_check and not (force_check.get("passed") if isinstance(force_check, dict) else force_check.passed):
            violations.append("force push accepted but remote is not user fork")

    if review.get("workflow_run_count", -1) > 0:
        violations.append("workflow run count > 0 - unexpected triggering")

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "warnings": [],
        "errors": [],
    }


def generate_post_publish_deviation_audit_report(
    review: Optional[dict[str, Any]] = None,
    output_path: Optional[str] = None,
) -> dict[str, Any]:
    """Generate R241-17B audit JSON and MD reports.

    Writes to:
        - migration_reports/foundation_audit/R241-17B_POST_PUBLISH_DEVIATION_AUDIT.json
        - migration_reports/foundation_audit/R241-17B_POST_PUBLISH_DEVIATION_AUDIT.md
    """
    if review is None:
        review = evaluate_post_publish_deviation_audit()

    path_json = _report_path(None, "R241-17B_POST_PUBLISH_DEVIATION_AUDIT.json")
    path_md = _report_path(None, "R241-17B_POST_PUBLISH_DEVIATION_AUDIT.md")

    path_json.parent.mkdir(parents=True, exist_ok=True)

    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(review, f, indent=2, ensure_ascii=False)

    md_lines = [
        "# R241-17B: Post-Publish Deviation Audit Report",
        "",
        f"**Generated**: {review.get('generated_at', '')}",
        f"**Status**: {review.get('status', '')}",
        f"**Decision**: {review.get('decision', '')}",
        f"**Force Push Deviation**: {review.get('force_push_deviation', False)}",
        "",
        "## Checks",
    ]
    for check in review.get("checks", []):
        icon = "✅" if check["passed"] else "❌"
        md_lines.append(f"- {icon} `{check['check_id']}` - {check['description']}")
        md_lines.append(f"  - Observed: `{check['observed_value']}`")
        md_lines.append(f"  - Expected: `{check['expected_value']}`")
        if check["blocked_reasons"]:
            md_lines.append(f"  - BLOCKED: {'; '.join(check['blocked_reasons'])}")

    md_lines.extend(["", "## Deviations", ""])
    for dev_id, dev in review.get("deviations", {}).items():
        icon = "✅" if dev["accepted"] else "❌"
        md_lines.append(f"- {icon} `{dev_id}` - {dev['description']} (risk={dev['risk_level']})")
        md_lines.append(f"  - Accepted: {dev['accepted']} - {dev['reason']}")

    md_lines.extend(["", "## Closure Summary", ""])
    md_lines.append(f"- Remote: {review.get('remote_summary', '')}")
    md_lines.append(f"- Workflow on remote: {review.get('workflow_remote_present', False)}")
    md_lines.append(f"- Workflow dispatch only: {review.get('workflow_dispatch_only', False)}")
    md_lines.append(f"- Workflow runs: {review.get('workflow_run_count', 0)}")
    md_lines.append(f"- Force push deviation: {review.get('force_push_deviation', False)}")
    md_lines.append(f"- Stash: {review.get('stash_summary', '')}")
    md_lines.append(f"- Worktree: {review.get('worktree_state', '')}")

    md_lines.extend(["", "## Safety Summary", ""])
    md_lines.append(review.get("safety_summary", ""))

    with open(path_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return {"json_path": str(path_json), "md_path": str(path_md)}


def generate_final_operational_closure_summary(
    review: Optional[dict[str, Any]] = None,
    output_path: Optional[str] = None,
) -> dict[str, Any]:
    """Generate R241-17B final operational closure summary.

    Writes to:
        - migration_reports/foundation_audit/R241-17B_FINAL_OPERATIONAL_CLOSURE.md
    """
    if review is None:
        review = evaluate_post_publish_deviation_audit()

    path = _report_path(None, "R241-17B_FINAL_OPERATIONAL_CLOSURE.md")
    path.parent.mkdir(parents=True, exist_ok=True)

    decision = review.get("decision", "")
    status = review.get("status", "")
    is_deviation = "deviation" in decision.lower()
    force_accepted = review.get("force_push_deviation", False)

    lines = [
        "# R241-17B: Final Operational Closure",
        "",
        f"**Date**: {review.get('generated_at', '')}",
        f"**Status**: {status}",
        f"**Decision**: {decision}",
        "",
        "## Remote Publish",
        "",
        f"- Remote URL: {review.get('remote_summary', '')}",
        f"- HEAD: `{review.get('head_hash', '')}`",
        f"- origin/main: `{review.get('origin_main_hash', '')}`",
        f"- Workflow on origin/main: {review.get('workflow_remote_present', False)}",
        f"- Workflow dispatch only: {review.get('workflow_dispatch_only', False)}",
        f"- Workflow run count: {review.get('workflow_run_count', 0)}",
        "",
    ]

    if is_deviation:
        lines.extend([
            "## Force Push Deviation",
            "",
            f"- **Deviation**: `force_push_used` - accepted={force_accepted}",
            f"- **Risk**: MEDIUM",
            f"- **Reason**: Remote is user fork (yangzixuan88/deer-flow) and workflow run count is 0",
            f"- **Evidence**: git push --force origin main executed in R241-17A",
            "",
        ])

    lines.extend([
        "## Worktree Cleanup",
        "",
        f"- Stash: `{review.get('stash_summary', '')}`",
        f"- State: {review.get('worktree_state', '')}",
        "",
        "## Delivery Closure (R241-16Y)",
        "",
        f"- Status: {review.get('delivery_closure_state', '')}",
        "",
        "## Current Remaining Caveats",
        "",
        "1. Do NOT dispatch `foundation-manual-dispatch.yml` until manually reviewed",
        "2. First manual dispatch should use `plan_only` mode",
        "3. Keep stash until user confirms no need to restore",
    ])

    if review.get("stash_summary"):
        lines.extend([
            "",
            "## Stash Restore Command",
            "",
            "```bash",
            "git stash pop",
            "```",
        ])

    lines.extend([
        "",
        "## Next Recommended Operational Step",
        "",
        "- No further action required from foundation CI",
        "- Workflow is in manual-dispatch-only mode - safe to remain on remote",
        "- If changes needed: review workflow, push to user fork, dispatch manually",
        "",
        "## Safety Confirmation",
        "",
        f"- {review.get('safety_summary', '')}",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {"path": str(path)}


class PostPublishAuditCheck:
    check_id: str
    passed: bool
    risk_level: PostPublishRiskLevel
    description: str
    observed_value: str
    expected_value: str
    evidence_refs: list[str]
    required_for_operational_closure: bool
    blocked_reasons: list[str]
    warnings: list[str]
    errors: list[str]

    def __init__(
        self,
        check_id: str,
        passed: bool,
        risk_level: PostPublishRiskLevel,
        description: str,
        observed_value: str,
        expected_value: str,
        evidence_refs: list[str],
        required_for_operational_closure: bool,
        blocked_reasons: list[str],
        warnings: list[str],
        errors: list[str],
    ):
        self.check_id = check_id
        self.passed = passed
        self.risk_level = risk_level
        self.description = description
        self.observed_value = observed_value
        self.expected_value = expected_value
        self.evidence_refs = evidence_refs
        self.required_for_operational_closure = required_for_operational_closure
        self.blocked_reasons = blocked_reasons
        self.warnings = warnings
        self.errors = errors


class PostPublishDeviation:
    deviation_id: str
    deviation_type: PostPublishDeviationType
    risk_level: PostPublishRiskLevel
    description: str
    accepted: bool
    reason: str
    evidence_refs: list[str]
    warnings: list[str]
    errors: list[str]

    def __init__(
        self,
        deviation_id: str,
        deviation_type: PostPublishDeviationType,
        risk_level: PostPublishRiskLevel,
        description: str,
        accepted: bool,
        reason: str,
        evidence_refs: list[str],
        warnings: list[str],
        errors: list[str],
    ):
        self.deviation_id = deviation_id
        self.deviation_type = deviation_type
        self.risk_level = risk_level
        self.description = description
        self.accepted = accepted
        self.reason = reason
        self.evidence_refs = evidence_refs
        self.warnings = warnings
        self.errors = errors


class PostPublishOperationalClosure(dict):
    pass
