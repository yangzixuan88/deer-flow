"""R241-16Q Publish Push Failure / Remote Permission Path Review.

This module is strictly read-only with respect to git history. It reviews the
local commit-ahead / push-403 state and proposes recovery paths without running
push, commit, reset, revert, branch, checkout, gh, or workflow commands.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from app.foundation import ci_publish_implementation as publish_impl
    from app.foundation import ci_publish_retry_git_identity as retry_impl
    from app.foundation import ci_remote_workflow_publish_review as publish_review
except ModuleNotFoundError:  # pragma: no cover
    from backend.app.foundation import ci_publish_implementation as publish_impl
    from backend.app.foundation import ci_publish_retry_git_identity as retry_impl
    from backend.app.foundation import ci_remote_workflow_publish_review as publish_review


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
TARGET_WORKFLOW_PATH = ".github/workflows/foundation-manual-dispatch.yml"
EXPECTED_COMMIT_HASH = "94908556cc2ca66c219d361f424954945eee9e67"


class PublishPushFailureReviewStatus:
    REVIEWED_PUSH_PERMISSION_DENIED = "reviewed_push_permission_denied"
    REVIEWED_BRANCH_PROTECTION_OR_AUTH_UNKNOWN = "reviewed_branch_protection_or_auth_unknown"
    BLOCKED_MISSING_LOCAL_COMMIT = "blocked_missing_local_commit"
    BLOCKED_COMMIT_SCOPE_UNSAFE = "blocked_commit_scope_unsafe"
    BLOCKED_UNEXPECTED_WORKFLOW_MUTATION = "blocked_unexpected_workflow_mutation"
    BLOCKED_REMOTE_ALREADY_CONTAINS_WORKFLOW = "blocked_remote_already_contains_workflow"
    DESIGN_ONLY = "design_only"
    UNKNOWN = "unknown"


class PublishPushFailureDecision:
    WAIT_FOR_PUSH_PERMISSION = "wait_for_push_permission"
    PREPARE_REVIEW_BRANCH_PATH = "prepare_review_branch_path"
    PREPARE_PATCH_OR_BUNDLE_PATH = "prepare_patch_or_bundle_path"
    PREPARE_MANUAL_ROLLBACK_CONFIRMATION = "prepare_manual_rollback_confirmation"
    KEEP_LOCAL_COMMIT = "keep_local_commit"
    BLOCK_NEXT_ACTION = "block_next_action"
    UNKNOWN = "unknown"


class PublishRecoveryOption:
    OPTION_A_KEEP_LOCAL_COMMIT_WAIT_PERMISSION = "option_a_keep_local_commit_wait_permission"
    OPTION_B_PUSH_TO_USER_FORK_AFTER_CONFIRMATION = "option_b_push_to_user_fork_after_confirmation"
    OPTION_C_CREATE_REVIEW_BRANCH_AFTER_CONFIRMATION = "option_c_create_review_branch_after_confirmation"
    OPTION_D_GENERATE_PATCH_BUNDLE_AFTER_CONFIRMATION = "option_d_generate_patch_bundle_after_confirmation"
    OPTION_E_ROLLBACK_LOCAL_COMMIT_AFTER_CONFIRMATION = "option_e_rollback_local_commit_after_confirmation"
    UNKNOWN = "unknown"


class PublishPushFailureRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(root: Optional[str] = None) -> Path:
    return Path(root).resolve() if root else ROOT


def _tail(text: str, limit: int = 4000) -> str:
    return (text or "")[-limit:]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _run_readonly_git(argv: list[str], root: Optional[str] = None, timeout_seconds: int = 30) -> dict:
    """Run an allow-listed read-only git command with shell=False."""
    allowed_prefixes = [
        ["git", "status", "--short"],
        ["git", "status", "--branch", "--short"],
        ["git", "log", "-1", "--oneline"],
        ["git", "show", "--name-only", "--format=fuller"],
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r"],
        ["git", "diff-tree", "--stat"],
        ["git", "remote", "-v"],
        ["git", "branch", "--show-current"],
        ["git", "rev-parse"],
        ["git", "rev-list", "--left-right", "--count"],
        ["git", "ls-tree", "-r", "origin/main", "--", TARGET_WORKFLOW_PATH],
    ]
    if not any(argv[: len(prefix)] == prefix for prefix in allowed_prefixes):
        return {
            "argv": argv,
            "command_executed": False,
            "shell_allowed": False,
            "exit_code": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "runtime_seconds": 0.0,
            "blocked_reasons": ["readonly_git_command_not_allowlisted"],
            "warnings": [],
            "errors": ["readonly_git_command_not_allowlisted"],
        }
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(_root(root)),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
        return {
            "argv": argv,
            "command_executed": True,
            "shell_allowed": False,
            "exit_code": proc.returncode,
            "stdout_tail": _tail(proc.stdout),
            "stderr_tail": _tail(proc.stderr),
            "runtime_seconds": round(time.perf_counter() - started, 4),
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        }
    except FileNotFoundError as exc:
        return {
            "argv": argv,
            "command_executed": False,
            "shell_allowed": False,
            "exit_code": -1,
            "stdout_tail": "",
            "stderr_tail": "",
            "runtime_seconds": round(time.perf_counter() - started, 4),
            "blocked_reasons": ["git_unavailable"],
            "warnings": [],
            "errors": [str(exc)],
        }


def _check(
    check_type: str,
    passed: bool,
    risk_level: str,
    description: str,
    observed_value: Any = None,
    expected_value: Any = None,
    evidence_refs: Optional[list[str]] = None,
    blocked_reasons: Optional[list[str]] = None,
    warnings: Optional[list[str]] = None,
    errors: Optional[list[str]] = None,
    command_blueprint: Optional[dict] = None,
    command_executed: Optional[dict] = None,
) -> dict:
    return {
        "check_id": f"push-failure-check-{uuid.uuid4().hex[:10]}",
        "check_type": check_type,
        "passed": bool(passed),
        "risk_level": risk_level,
        "description": description,
        "command_blueprint": command_blueprint or {},
        "command_executed": command_executed or {},
        "observed_value": observed_value,
        "expected_value": expected_value,
        "evidence_refs": evidence_refs or [],
        "blocked_reasons": blocked_reasons or [],
        "warnings": warnings or [],
        "errors": errors or [],
    }


def load_r241_16p_retry_result(root: str | None = None) -> dict:
    """Load and validate R241-16P-Retry result artifact."""
    path = _root(root) / "migration_reports" / "foundation_audit" / "R241-16P_RETRY_PUBLISH_IMPLEMENTATION_RESULT.json"
    errors: list[str] = []
    blocked: list[str] = []
    payload: dict[str, Any] = {}
    if not path.exists():
        return {
            "loaded": False,
            "path": str(path),
            "payload": {},
            "passed": False,
            "blocked_reasons": ["retry_result_missing"],
            "warnings": [],
            "errors": [f"missing:{path}"],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(str(exc))
        blocked.append("retry_result_malformed")
    publish = payload.get("publish_result", {})
    checks = {
        "status_retry_push_failed": payload.get("status") == retry_impl.PublishRetryStatus.RETRY_PUSH_FAILED,
        "publish_status_push_failed": publish.get("status") == publish_impl.PublishImplementationStatus.PUSH_FAILED,
        "commit_succeeded_true": publish.get("commit_succeeded") is True,
        "push_succeeded_false": publish.get("push_succeeded") is False,
        "commit_hash_exists": bool(publish.get("commit_hash")),
        "errors_include_git_push_failed": "git_push_failed" in publish.get("errors", []),
        "existing_workflows_unchanged": payload.get("local_mutation_guard", {}).get("existing_workflows_unchanged") is True,
        "audit_jsonl_unchanged": payload.get("local_mutation_guard", {}).get("audit_jsonl_unchanged") is True,
        "runtime_action_queue_unchanged": payload.get("local_mutation_guard", {}).get("runtime_action_queue_unchanged") is True,
    }
    text = _json(payload).lower()
    checks["no_gh_workflow_run"] = "gh workflow run" not in text
    for name, passed in checks.items():
        if not passed:
            blocked.append(name)
    return {
        "loaded": not errors,
        "path": str(path),
        "payload": payload,
        "publish_result": publish,
        "checks": checks,
        "passed": not blocked and not errors,
        "blocked_reasons": blocked,
        "warnings": [],
        "errors": errors,
    }


def _lines(output: str) -> list[str]:
    return [line.strip().replace("\\", "/") for line in (output or "").splitlines() if line.strip()]


def _staged_files_from_status(status_output: str) -> list[str]:
    staged: list[str] = []
    for line in (status_output or "").splitlines():
        if not line:
            continue
        if line[0] not in {" ", "?", "!"}:
            staged.append(line[3:].strip().replace("\\", "/"))
    return staged


def inspect_local_publish_commit(root: str | None = None) -> dict:
    """Read-only inspection of HEAD local publish commit and current branch state."""
    retry_result = load_r241_16p_retry_result(root)
    expected_hash = retry_result.get("publish_result", {}).get("commit_hash") or EXPECTED_COMMIT_HASH
    head = _run_readonly_git(["git", "rev-parse", "HEAD"], root=root)
    origin = _run_readonly_git(["git", "rev-parse", "origin/main"], root=root)
    current_branch = _run_readonly_git(["git", "branch", "--show-current"], root=root)
    ahead_behind = _run_readonly_git(["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"], root=root)
    changed = _run_readonly_git(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", expected_hash], root=root)
    stat = _run_readonly_git(["git", "diff-tree", "--stat", expected_hash], root=root)
    show = _run_readonly_git(["git", "show", "--name-only", "--format=fuller", expected_hash], root=root)
    status = _run_readonly_git(["git", "status", "--short"], root=root)
    workflow_status = _run_readonly_git(["git", "status", "--short", "--", ".github/workflows/"], root=root)
    safety = publish_review.inspect_publish_workflow_content_safety(root)

    head_hash = head.get("stdout_tail", "").strip()
    changed_files = _lines(changed.get("stdout_tail", ""))
    staged_files = _staged_files_from_status(status.get("stdout_tail", ""))
    workflow_status_text = workflow_status.get("stdout_tail", "")
    existing_workflows_unchanged = (
        ".github/workflows/backend-unit-tests.yml" not in workflow_status_text
        and ".github/workflows/lint-check.yml" not in workflow_status_text
    )
    local_commit_exists = head_hash == expected_hash
    only_target = changed_files == [TARGET_WORKFLOW_PATH]
    return {
        "local_commit_hash": expected_hash,
        "head_hash": head_hash,
        "head_equals_publish_commit": local_commit_exists,
        "origin_main_hash": origin.get("stdout_tail", "").strip(),
        "local_commit_exists": local_commit_exists,
        "commit_changed_files": changed_files,
        "local_commit_only_target_workflow": only_target,
        "commit_message": "Add manual foundation CI workflow" if "Add manual foundation CI workflow" in show.get("stdout_tail", "") else "",
        "local_branch": current_branch.get("stdout_tail", "").strip(),
        "ahead_behind_summary": ahead_behind.get("stdout_tail", "").strip(),
        "staged_area_empty": staged_files == [],
        "staged_files": staged_files,
        "workflow_content_safe": safety.get("workflow_content_safe"),
        "workflow_dispatch_only": safety.get("workflow_dispatch_only"),
        "existing_workflows_unchanged": existing_workflows_unchanged,
        "workflow_status": workflow_status_text,
        "stat": stat.get("stdout_tail", ""),
        "status": PublishPushFailureReviewStatus.DESIGN_ONLY
        if local_commit_exists and only_target and existing_workflows_unchanged
        else PublishPushFailureReviewStatus.BLOCKED_COMMIT_SCOPE_UNSAFE,
        "warnings": [],
        "errors": head.get("errors", []) + changed.get("errors", []) + status.get("errors", []),
    }


def inspect_push_failure_reason(root: str | None = None) -> dict:
    """Classify the push failure stderr from R241-16P-Retry."""
    retry_result = load_r241_16p_retry_result(root)
    publish = retry_result.get("publish_result", {})
    stderr = "\n".join(cmd.get("stderr_tail", "") for cmd in publish.get("git_command_results", []))
    lowered = stderr.lower()
    actor = None
    match = re.search(r"denied to ([A-Za-z0-9_.-]+)", stderr)
    if match:
        actor = match.group(1).rstrip(".")
    if "403" in lowered or "permission to" in lowered and "denied" in lowered:
        classification = "permission_denied_403"
    elif "authentication" in lowered or "could not read username" in lowered or "access denied" in lowered:
        classification = "auth_missing_or_invalid"
    elif "protected branch" in lowered or "branch protection" in lowered:
        classification = "branch_protection"
    elif "could not resolve host" in lowered or "timed out" in lowered or "network" in lowered:
        classification = "network_failure"
    else:
        classification = "unknown"
    return {
        "classification": classification,
        "actor": actor,
        "stderr_tail": stderr[-4000:],
        "push_exit_code": next(
            (cmd.get("exit_code") for cmd in publish.get("git_command_results", []) if cmd.get("command_id") == "git_push_origin_main"),
            None,
        ),
        "warnings": [],
        "errors": [] if classification != "unknown" else ["push_failure_classification_unknown"],
    }


def verify_remote_still_missing_workflow(root: str | None = None) -> dict:
    result = _run_readonly_git(["git", "ls-tree", "-r", "origin/main", "--", TARGET_WORKFLOW_PATH], root=root)
    present = TARGET_WORKFLOW_PATH in result.get("stdout_tail", "")
    return {
        "remote_workflow_present": present,
        "exact_path_present": present,
        "command_result": result,
        "warnings": [],
        "errors": result.get("errors", []),
    }


def verify_no_local_mutation_during_push_failure_review(root: str | None = None, baseline: dict | None = None) -> dict:
    baseline = baseline or publish_impl.capture_publish_mutation_baseline(root)
    guard = publish_impl.verify_publish_local_mutation_guard(root, baseline)
    status = _run_readonly_git(["git", "status", "--short"], root=root)
    staged_files = _staged_files_from_status(status.get("stdout_tail", ""))
    errors = list(guard.get("errors", []))
    if staged_files:
        errors.append("staged_files_detected")
    return {
        "valid": not errors,
        "workflow_files_unchanged": guard.get("target_workflow_content_unchanged") and guard.get("existing_workflows_unchanged"),
        "audit_jsonl_unchanged": guard.get("audit_jsonl_unchanged"),
        "runtime_action_queue_unchanged": guard.get("runtime_action_queue_unchanged"),
        "staged_area_empty": staged_files == [],
        "staged_files": staged_files,
        "no_auto_fix": True,
        "branch_unchanged": True,
        "warnings": guard.get("warnings", []),
        "errors": errors,
    }


def build_publish_recovery_options() -> dict:
    options = [
        {
            "option_id": PublishRecoveryOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT_PERMISSION,
            "label": "Keep local commit and wait for upstream permission",
            "risk_level": PublishPushFailureRiskLevel.LOW,
            "recommended_when": ["permission_denied_403"],
            "recommended": True,
            "description": "Keep the safe local commit ahead 1 and retry push only after upstream permission is granted.",
        },
        {
            "option_id": PublishRecoveryOption.OPTION_B_PUSH_TO_USER_FORK_AFTER_CONFIRMATION,
            "label": "Push to user fork after confirmation",
            "risk_level": PublishPushFailureRiskLevel.MEDIUM,
            "recommended": False,
            "description": "Requires an explicit fork remote or confirmation of an existing fork remote.",
        },
        {
            "option_id": PublishRecoveryOption.OPTION_C_CREATE_REVIEW_BRANCH_AFTER_CONFIRMATION,
            "label": "Create review branch after confirmation",
            "risk_level": PublishPushFailureRiskLevel.MEDIUM,
            "recommended": False,
            "description": "Requires branch creation and push; may still fail without remote permission.",
        },
        {
            "option_id": PublishRecoveryOption.OPTION_D_GENERATE_PATCH_BUNDLE_AFTER_CONFIRMATION,
            "label": "Generate patch or bundle after confirmation",
            "risk_level": PublishPushFailureRiskLevel.LOW,
            "recommended": False,
            "description": "Creates a handoff artifact under migration_reports/foundation_audit without remote push.",
        },
        {
            "option_id": PublishRecoveryOption.OPTION_E_ROLLBACK_LOCAL_COMMIT_AFTER_CONFIRMATION,
            "label": "Rollback local commit after confirmation",
            "risk_level": PublishPushFailureRiskLevel.HIGH,
            "recommended": False,
            "description": "Requires explicit confirmation; this review does not reset/revert.",
        },
    ]
    return {"options": options, "recommended_option": PublishRecoveryOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT_PERMISSION}


def _blueprint(command_id: str, option: str, argv: list[str], **flags: bool) -> dict:
    return {
        "command_id": command_id,
        "recovery_option": option,
        "argv": argv,
        "command_allowed_now": False,
        "would_modify_git_history": bool(flags.get("would_modify_git_history", False)),
        "would_push_remote": bool(flags.get("would_push_remote", False)),
        "would_create_branch": bool(flags.get("would_create_branch", False)),
        "would_create_pr": bool(flags.get("would_create_pr", False)),
        "requires_confirmation_phrase": "CONFIRM_PUBLISH_RECOVERY_PATH",
        "warnings": [],
        "errors": [],
    }


def build_push_failure_command_blueprints() -> dict:
    blueprints = [
        _blueprint("wait_for_permission_no_command", PublishRecoveryOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT_PERMISSION, []),
        _blueprint(
            "push_to_user_fork_after_confirmation",
            PublishRecoveryOption.OPTION_B_PUSH_TO_USER_FORK_AFTER_CONFIRMATION,
            ["git", "push", "user-fork", "main"],
            would_push_remote=True,
        ),
        _blueprint(
            "create_review_branch_after_confirmation",
            PublishRecoveryOption.OPTION_C_CREATE_REVIEW_BRANCH_AFTER_CONFIRMATION,
            ["git", "branch", "foundation-manual-workflow-review"],
            would_modify_git_history=True,
            would_create_branch=True,
        ),
        _blueprint(
            "generate_patch_bundle_after_confirmation",
            PublishRecoveryOption.OPTION_D_GENERATE_PATCH_BUNDLE_AFTER_CONFIRMATION,
            ["git", "format-patch", "-1", "HEAD", "-o", "migration_reports/foundation_audit"],
        ),
        _blueprint(
            "rollback_local_commit_after_confirmation",
            PublishRecoveryOption.OPTION_E_ROLLBACK_LOCAL_COMMIT_AFTER_CONFIRMATION,
            ["git", "reset", "--soft", "HEAD~1"],
            would_modify_git_history=True,
        ),
    ]
    forbidden = ("--force", "reset --hard", "gh workflow run", "secret", "token", "auto-fix", "auto_fix")
    errors: list[str] = []
    for bp in blueprints:
        joined = " ".join(bp.get("argv", [])).lower()
        for token in forbidden:
            if token in joined:
                errors.append(f"forbidden_blueprint_token:{bp['command_id']}:{token}")
    return {"blueprints": blueprints, "warnings": [], "errors": errors}


def evaluate_publish_push_failure_review(root: str | None = None) -> dict:
    baseline = publish_impl.capture_publish_mutation_baseline(root)
    retry_result = load_r241_16p_retry_result(root)
    local_commit = inspect_local_publish_commit(root)
    failure = inspect_push_failure_reason(root)
    remote = verify_remote_still_missing_workflow(root)
    options = build_publish_recovery_options()
    blueprints = build_push_failure_command_blueprints()
    mutation_guard = verify_no_local_mutation_during_push_failure_review(root, baseline)
    rollback_plan = publish_review.build_publish_rollback_plan()
    confirmation_requirements = {
        "confirmation_required": True,
        "confirmation_phrase": "CONFIRM_PUBLISH_RECOVERY_PATH",
        "applies_to": [
            PublishRecoveryOption.OPTION_B_PUSH_TO_USER_FORK_AFTER_CONFIRMATION,
            PublishRecoveryOption.OPTION_C_CREATE_REVIEW_BRANCH_AFTER_CONFIRMATION,
            PublishRecoveryOption.OPTION_D_GENERATE_PATCH_BUNDLE_AFTER_CONFIRMATION,
            PublishRecoveryOption.OPTION_E_ROLLBACK_LOCAL_COMMIT_AFTER_CONFIRMATION,
        ],
    }

    checks = [
        _check(
            "r241_16p_retry_result",
            retry_result.get("passed", False),
            PublishPushFailureRiskLevel.CRITICAL,
            "R241-16P-Retry result must be retry_push_failed with safe local commit.",
            observed_value=retry_result.get("checks"),
            expected_value="retry_push_failed",
            evidence_refs=[retry_result.get("path", "")],
            blocked_reasons=retry_result.get("blocked_reasons", []),
            errors=retry_result.get("errors", []),
        ),
        _check(
            "local_commit_scope",
            local_commit.get("local_commit_exists") and local_commit.get("local_commit_only_target_workflow"),
            PublishPushFailureRiskLevel.CRITICAL,
            "Local HEAD must be the publish commit and include only target workflow.",
            observed_value=local_commit.get("commit_changed_files"),
            expected_value=[TARGET_WORKFLOW_PATH],
            evidence_refs=["git diff-tree --no-commit-id --name-only -r HEAD"],
            blocked_reasons=[] if local_commit.get("local_commit_only_target_workflow") else ["commit_scope_unsafe"],
        ),
        _check(
            "remote_workflow_missing",
            remote.get("remote_workflow_present") is False,
            PublishPushFailureRiskLevel.HIGH,
            "origin/main should still miss the target workflow after push failure.",
            observed_value=remote.get("remote_workflow_present"),
            expected_value=False,
            evidence_refs=["git ls-tree -r origin/main -- .github/workflows/foundation-manual-dispatch.yml"],
            blocked_reasons=[] if remote.get("remote_workflow_present") is False else ["remote_already_contains_workflow"],
        ),
        _check(
            "mutation_guard",
            mutation_guard.get("valid", False),
            PublishPushFailureRiskLevel.CRITICAL,
            "Review must not stage files or mutate workflow/runtime/audit/action queue.",
            observed_value=mutation_guard,
            expected_value={"valid": True, "staged_area_empty": True},
            blocked_reasons=mutation_guard.get("errors", []),
        ),
    ]

    if not local_commit.get("local_commit_exists"):
        status = PublishPushFailureReviewStatus.BLOCKED_MISSING_LOCAL_COMMIT
        decision = PublishPushFailureDecision.BLOCK_NEXT_ACTION
    elif not local_commit.get("local_commit_only_target_workflow"):
        status = PublishPushFailureReviewStatus.BLOCKED_COMMIT_SCOPE_UNSAFE
        decision = PublishPushFailureDecision.BLOCK_NEXT_ACTION
    elif not local_commit.get("existing_workflows_unchanged") or not mutation_guard.get("workflow_files_unchanged"):
        status = PublishPushFailureReviewStatus.BLOCKED_UNEXPECTED_WORKFLOW_MUTATION
        decision = PublishPushFailureDecision.BLOCK_NEXT_ACTION
    elif remote.get("remote_workflow_present"):
        status = PublishPushFailureReviewStatus.BLOCKED_REMOTE_ALREADY_CONTAINS_WORKFLOW
        decision = PublishPushFailureDecision.BLOCK_NEXT_ACTION
    elif failure.get("classification") == "permission_denied_403":
        status = PublishPushFailureReviewStatus.REVIEWED_PUSH_PERMISSION_DENIED
        decision = PublishPushFailureDecision.KEEP_LOCAL_COMMIT
    else:
        status = PublishPushFailureReviewStatus.REVIEWED_BRANCH_PROTECTION_OR_AUTH_UNKNOWN
        decision = PublishPushFailureDecision.WAIT_FOR_PUSH_PERMISSION

    return {
        "review_id": f"push-failure-review-{uuid.uuid4().hex[:12]}",
        "generated_at": _now(),
        "status": status,
        "decision": decision,
        "local_commit_hash": local_commit.get("local_commit_hash"),
        "local_commit_exists": local_commit.get("local_commit_exists"),
        "local_commit_only_target_workflow": local_commit.get("local_commit_only_target_workflow"),
        "local_branch": local_commit.get("local_branch"),
        "ahead_behind_summary": local_commit.get("ahead_behind_summary"),
        "remote_url_summary": _run_readonly_git(["git", "remote", "-v"], root=root).get("stdout_tail", ""),
        "push_failure_summary": failure,
        "remote_workflow_present": remote.get("remote_workflow_present"),
        "existing_workflows_unchanged": local_commit.get("existing_workflows_unchanged") and mutation_guard.get("workflow_files_unchanged"),
        "local_mutation_guard": mutation_guard,
        "local_commit_inspection": local_commit,
        "remote_missing_workflow_check": remote,
        "recovery_options": options.get("options", []),
        "recommended_option": options.get("recommended_option"),
        "command_blueprints": blueprints.get("blueprints", []),
        "rollback_plan": rollback_plan,
        "confirmation_requirements": confirmation_requirements,
        "checks": checks,
        "warnings": blueprints.get("warnings", []) + retry_result.get("warnings", []),
        "errors": blueprints.get("errors", []) + retry_result.get("errors", []) + failure.get("errors", []),
    }


def validate_publish_push_failure_review(review: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    text = _json(review).lower()
    if "git push executed" in text:
        errors.append("git_push_executed")
    if review.get("git_push_executed") is True:
        errors.append("git_push_executed")
    if review.get("git_commit_executed") is True:
        errors.append("git_commit_executed")
    if review.get("git_reset_executed") is True or review.get("git_revert_executed") is True:
        errors.append("git_reset_or_revert_executed")
    if review.get("gh_workflow_run_executed") is True:
        errors.append("gh_workflow_run_executed")
    if review.get("workflow_modified") is True:
        errors.append("workflow_modified")
    if review.get("secret_read") is True:
        errors.append("secret_read")
    if review.get("runtime_write") is True:
        errors.append("runtime_write")
    if review.get("audit_jsonl_write") is True:
        errors.append("audit_jsonl_write")
    if review.get("action_queue_write") is True:
        errors.append("action_queue_write")
    if review.get("auto_fix_executed") is True:
        errors.append("auto_fix_executed")
    if review.get("local_commit_exists") and review.get("local_commit_only_target_workflow") is not True:
        errors.append("commit_scope_unsafe")
    for bp in review.get("command_blueprints", []):
        if bp.get("command_allowed_now") is not False:
            errors.append(f"command_blueprint_allowed_now:{bp.get('command_id')}")
        joined = " ".join(bp.get("argv", [])).lower()
        if "--force" in joined:
            errors.append("force_push_blueprint_forbidden")
        if "reset --hard" in joined:
            errors.append("reset_hard_blueprint_forbidden")
        if "gh workflow run" in joined:
            errors.append("gh_workflow_run_blueprint_forbidden")
    if not review.get("confirmation_requirements", {}).get("confirmation_required"):
        errors.append("rollback_confirmation_missing")
    return {"valid": not errors, "warnings": warnings, "errors": errors}


def _render_report(review: dict, validation: dict) -> str:
    checks = [
        f"- `{c.get('check_type')}` passed=`{c.get('passed')}` blocked=`{c.get('blocked_reasons')}`"
        for c in review.get("checks", [])
    ]
    options = [
        f"- `{o.get('option_id')}` risk=`{o.get('risk_level')}` recommended=`{o.get('recommended')}`"
        for o in review.get("recovery_options", [])
    ]
    blueprints = [
        f"- `{b.get('command_id')}` allowed=`{b.get('command_allowed_now')}` argv=`{' '.join(b.get('argv', []))}`"
        for b in review.get("command_blueprints", [])
    ]
    return "\n".join(
        [
            "# R241-16Q Publish Push Failure Review",
            "",
            "## 1. 修改文件清单",
            "- `backend/app/foundation/ci_publish_push_failure_review.py`",
            "- `backend/app/foundation/test_ci_publish_push_failure_review.py`",
            "- `migration_reports/foundation_audit/R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.json`",
            "- `migration_reports/foundation_audit/R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.md`",
            "",
            "## 2. PublishPushFailureReviewStatus / Decision / Option / RiskLevel",
            "- Status: `reviewed_push_permission_denied`, `reviewed_branch_protection_or_auth_unknown`, `blocked_missing_local_commit`, `blocked_commit_scope_unsafe`, `blocked_unexpected_workflow_mutation`, `blocked_remote_already_contains_workflow`, `design_only`, `unknown`",
            "- Decision: `wait_for_push_permission`, `prepare_review_branch_path`, `prepare_patch_or_bundle_path`, `prepare_manual_rollback_confirmation`, `keep_local_commit`, `block_next_action`, `unknown`",
            "- Options: `option_a_keep_local_commit_wait_permission`, `option_b_push_to_user_fork_after_confirmation`, `option_c_create_review_branch_after_confirmation`, `option_d_generate_patch_bundle_after_confirmation`, `option_e_rollback_local_commit_after_confirmation`",
            "- Risk: `low`, `medium`, `high`, `critical`, `unknown`",
            "",
            "## 3. PublishPushFailureCheck 字段",
            "`check_id`, `check_type`, `passed`, `risk_level`, `description`, `command_blueprint`, `command_executed`, `observed_value`, `expected_value`, `evidence_refs`, `blocked_reasons`, `warnings`, `errors`",
            "",
            "## 4. PublishRecoveryCommandBlueprint 字段",
            "`command_id`, `recovery_option`, `argv`, `command_allowed_now`, `would_modify_git_history`, `would_push_remote`, `would_create_branch`, `would_create_pr`, `requires_confirmation_phrase`, `warnings`, `errors`",
            "",
            "## 5. PublishPushFailureReview 字段",
            "`review_id`, `generated_at`, `status`, `decision`, `local_commit_hash`, `local_commit_exists`, `local_commit_only_target_workflow`, `local_branch`, `ahead_behind_summary`, `remote_url_summary`, `push_failure_summary`, `remote_workflow_present`, `existing_workflows_unchanged`, `local_mutation_guard`, `recovery_options`, `recommended_option`, `command_blueprints`, `rollback_plan`, `confirmation_requirements`, `checks`, `warnings`, `errors`",
            "",
            "## 6. R241-16P-Retry loading result",
            f"- status: `{review.get('status')}`",
            f"- local_commit_hash: `{review.get('local_commit_hash')}`",
            "",
            "## 7. local commit inspection result",
            f"- local_commit_exists: `{review.get('local_commit_exists')}`",
            f"- local_commit_only_target_workflow: `{review.get('local_commit_only_target_workflow')}`",
            f"- local_branch: `{review.get('local_branch')}`",
            f"- ahead_behind_summary: `{review.get('ahead_behind_summary')}`",
            "",
            "## 8. push failure reason classification",
            f"- classification: `{review.get('push_failure_summary', {}).get('classification')}`",
            f"- actor: `{review.get('push_failure_summary', {}).get('actor')}`",
            "",
            "## 9. remote still missing workflow result",
            f"- remote_workflow_present: `{review.get('remote_workflow_present')}`",
            "",
            "## 10. recovery options",
            *(options or ["- No options recorded."]),
            "",
            "## 11. command blueprints",
            *(blueprints or ["- No blueprints recorded."]),
            "",
            "## 12. rollback plan",
            f"- rollback_plan_present: `{bool(review.get('rollback_plan'))}`",
            "",
            "## 13. mutation guard result",
            f"- valid: `{review.get('local_mutation_guard', {}).get('valid')}`",
            f"- staged_area_empty: `{review.get('local_mutation_guard', {}).get('staged_area_empty')}`",
            f"- audit_jsonl_unchanged: `{review.get('local_mutation_guard', {}).get('audit_jsonl_unchanged')}`",
            f"- runtime_action_queue_unchanged: `{review.get('local_mutation_guard', {}).get('runtime_action_queue_unchanged')}`",
            "",
            "## 14. validation result",
            f"- valid: `{validation.get('valid')}`",
            f"- errors: `{validation.get('errors')}`",
            "",
            "## 15. 测试结果",
            "- See final assistant response for executed validation commands.",
            "",
            "## 16. 是否执行 git commit",
            "- `false`",
            "## 17. 是否执行 git push",
            "- `false`",
            "## 18. 是否执行 git reset/revert",
            "- `false`",
            "## 19. 是否执行 gh workflow run",
            "- `false`",
            "## 20. 是否读取 secret",
            "- `false`",
            "## 21. 是否修改 workflow",
            "- `false`",
            "## 22. 是否写 runtime / audit JSONL / action queue",
            "- `false`",
            "## 23. 是否执行 auto-fix",
            "- `false`",
            "## 24. 当前剩余断点",
            f"- errors: `{review.get('errors')}`",
            "",
            "## 25. 下一轮建议",
            "- Prefer Option A if upstream permission can be granted.",
            "- Otherwise proceed to R241-16R for Fork/PR path confirmation or Patch Bundle generation gate.",
            "",
            "## 26. Checks",
            *(checks or ["- No checks recorded."]),
        ]
    )


def generate_publish_push_failure_review_report(review: dict | None = None, output_path: str | None = None) -> dict:
    if review is None:
        review = evaluate_publish_push_failure_review()
    validation = validate_publish_push_failure_review(review)
    output_dir = REPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = Path(output_path) if output_path else output_dir / "R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.json"
    md_path = json_path.with_suffix(".md") if output_path else output_dir / "R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.md"
    payload = {
        "generated_at": _now(),
        "review": review,
        "validation": validation,
        "warnings": review.get("warnings", []) + validation.get("warnings", []),
        "errors": review.get("errors", []) + validation.get("errors", []),
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(_json(payload), encoding="utf-8")
    md_path.write_text(_render_report(review, validation), encoding="utf-8")
    return {
        "output_path": str(json_path),
        "report_path": str(md_path),
        "review": review,
        "validation": validation,
        "warnings": payload["warnings"],
        "errors": payload["errors"],
    }
