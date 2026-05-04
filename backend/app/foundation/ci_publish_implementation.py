"""R241-16P Publish Implementation.

Publishes only `.github/workflows/foundation-manual-dispatch.yml` after the
R241-16O confirmation gate and R241-16N canonical readiness remain valid.
The implementation deliberately keeps all git commands allow-listed and uses
`shell=False`.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from app.foundation import ci_publish_confirmation_gate as confirmation_gate
    from app.foundation import ci_remote_workflow_publish_review as publish_review
except ModuleNotFoundError:  # pragma: no cover - external import style.
    from backend.app.foundation import ci_publish_confirmation_gate as confirmation_gate
    from backend.app.foundation import ci_remote_workflow_publish_review as publish_review


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
TARGET_WORKFLOW_PATH = ".github/workflows/foundation-manual-dispatch.yml"
EXISTING_WORKFLOW_PATHS = [
    ".github/workflows/backend-unit-tests.yml",
    ".github/workflows/lint-check.yml",
]
COMMIT_MESSAGE = "Add manual foundation CI workflow"
EXPECTED_OPTION = "option_c_push_to_default_branch_after_confirmation"


class PublishImplementationStatus:
    PUBLISHED = "published"
    BLOCKED_PRECHECK_FAILED = "blocked_precheck_failed"
    BLOCKED_READINESS_STALE = "blocked_readiness_stale"
    BLOCKED_UNEXPECTED_DIFF = "blocked_unexpected_diff"
    BLOCKED_WORKFLOW_UNSAFE = "blocked_workflow_unsafe"
    BLOCKED_GIT_UNAVAILABLE = "blocked_git_unavailable"
    COMMIT_FAILED = "commit_failed"
    PUSH_FAILED = "push_failed"
    REMOTE_VERIFICATION_FAILED = "remote_verification_failed"
    ROLLBACK_REQUIRED = "rollback_required"
    UNKNOWN = "unknown"


class PublishImplementationDecision:
    EXECUTE_PUBLISH = "execute_publish"
    BLOCK_PUBLISH = "block_publish"
    VERIFY_REMOTE_VISIBILITY = "verify_remote_visibility"
    ROLLBACK_PUBLISH = "rollback_publish"
    UNKNOWN = "unknown"


class PublishImplementationRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class PublishImplementationStepStatus:
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    WARNING = "warning"
    UNKNOWN = "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(root: Optional[str] = None) -> Path:
    return Path(root).resolve() if root else ROOT


def _tail(text: str, limit: int = 4000) -> str:
    if not text:
        return ""
    return text[-limit:]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _new_precheck(
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
) -> dict:
    return {
        "precheck_id": f"precheck-publish-{uuid.uuid4().hex[:10]}",
        "check_type": check_type,
        "passed": bool(passed),
        "risk_level": risk_level,
        "description": description,
        "observed_value": observed_value,
        "expected_value": expected_value,
        "evidence_refs": evidence_refs or [],
        "blocked_reasons": blocked_reasons or [],
        "warnings": warnings or [],
        "errors": errors or [],
    }


def _command_result(
    command_id: str,
    argv: list[str],
    command_executed: bool,
    exit_code: Optional[int],
    stdout: str = "",
    stderr: str = "",
    runtime_seconds: float = 0.0,
    would_modify_git_history: bool = False,
    would_push_remote: bool = False,
    blocked_reasons: Optional[list[str]] = None,
    warnings: Optional[list[str]] = None,
    errors: Optional[list[str]] = None,
) -> dict:
    return {
        "command_id": command_id,
        "argv": argv,
        "command_executed": command_executed,
        "shell_allowed": False,
        "exit_code": exit_code,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "runtime_seconds": round(runtime_seconds, 4),
        "would_modify_git_history": would_modify_git_history,
        "would_push_remote": would_push_remote,
        "blocked_reasons": blocked_reasons or [],
        "warnings": warnings or [],
        "errors": errors or [],
    }


def _run_git(
    command_id: str,
    argv: list[str],
    root: Optional[str] = None,
    timeout_seconds: int = 60,
    would_modify_git_history: bool = False,
    would_push_remote: bool = False,
) -> dict:
    if not argv or argv[0] != "git":
        return _command_result(
            command_id,
            argv,
            False,
            None,
            blocked_reasons=["non_git_command_rejected"],
            errors=["only git commands are allowed in publish implementation helper"],
            would_modify_git_history=would_modify_git_history,
            would_push_remote=would_push_remote,
        )
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
        return _command_result(
            command_id,
            argv,
            True,
            proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            runtime_seconds=time.perf_counter() - started,
            would_modify_git_history=would_modify_git_history,
            would_push_remote=would_push_remote,
        )
    except FileNotFoundError as exc:
        return _command_result(
            command_id,
            argv,
            False,
            -1,
            runtime_seconds=time.perf_counter() - started,
            blocked_reasons=["git_unavailable"],
            errors=[str(exc)],
            would_modify_git_history=would_modify_git_history,
            would_push_remote=would_push_remote,
        )
    except subprocess.TimeoutExpired as exc:
        return _command_result(
            command_id,
            argv,
            True,
            -1,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            runtime_seconds=time.perf_counter() - started,
            blocked_reasons=["git_command_timeout"],
            errors=[f"timeout:{timeout_seconds}s"],
            would_modify_git_history=would_modify_git_history,
            would_push_remote=would_push_remote,
        )


def _file_state(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "sha256": None, "mtime": None, "size": None}
    data = path.read_bytes()
    stat = path.stat()
    return {
        "exists": True,
        "sha256": hashlib.sha256(data).hexdigest(),
        "mtime": stat.st_mtime,
        "size": stat.st_size,
    }


def _jsonl_line_counts(root_path: Path) -> dict:
    base = root_path / "migration_reports" / "foundation_audit" / "audit_trail"
    counts: dict[str, int] = {}
    if not base.exists():
        return counts
    for path in sorted(base.glob("*.jsonl")):
        try:
            counts[str(path.relative_to(root_path)).replace("\\", "/")] = len(
                path.read_text(encoding="utf-8").splitlines()
            )
        except OSError:
            counts[str(path.relative_to(root_path)).replace("\\", "/")] = -1
    return counts


def _path_mtimes(root_path: Path, paths: list[str]) -> dict:
    result: dict[str, dict] = {}
    for rel in paths:
        path = root_path / rel
        result[rel] = {"exists": path.exists(), "mtime": path.stat().st_mtime if path.exists() else None}
    return result


def _cached_files(root: Optional[str] = None) -> list[str]:
    result = _run_git("git_diff_cached_name_only", ["git", "diff", "--cached", "--name-only"], root=root)
    if result.get("exit_code") != 0:
        return []
    return [line.strip().replace("\\", "/") for line in result.get("stdout_tail", "").splitlines() if line.strip()]


def _head_commit_hash(root: Optional[str] = None) -> Optional[str]:
    result = _run_git("git_rev_parse_head", ["git", "rev-parse", "HEAD"], root=root)
    if result.get("exit_code") == 0:
        return result.get("stdout_tail", "").strip()
    return None


def load_publish_confirmation_for_implementation(root: str | None = None) -> dict:
    """Read and validate the R241-16O confirmation gate result."""
    root_path = _root(root)
    path = root_path / "migration_reports" / "foundation_audit" / "R241-16O_PUBLISH_CONFIRMATION_GATE.json"
    errors: list[str] = []
    warnings: list[str] = []
    blocked: list[str] = []
    payload: dict[str, Any] = {}
    if not path.exists():
        return {
            "passed": False,
            "path": str(path),
            "confirmation": {},
            "blocked_reasons": ["publish_confirmation_artifact_missing"],
            "warnings": [],
            "errors": [f"missing:{path}"],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(str(exc))
        blocked.append("publish_confirmation_artifact_malformed")

    decision = payload.get("decision", {}) if isinstance(payload, dict) else {}
    validation = payload.get("validation", {}) if isinstance(payload, dict) else {}
    input_data = decision.get("confirmation_input", {})
    publish_ref = decision.get("publish_review_ref", {})

    checks = {
        "status_allowed": decision.get("status") == "allowed_for_next_review",
        "decision_allows": decision.get("decision") == "allow_publish_implementation_review",
        "allowed_next_phase": decision.get("allowed_next_phase") == "R241-16P_publish_implementation",
        "requested_option": decision.get("requested_option") == EXPECTED_OPTION,
        "publish_allowed_now_false": decision.get("publish_allowed_now") is False,
        "phrase_exact_match": input_data.get("phrase_exact_match") is True,
        "readiness_ready": publish_ref.get("status") == "ready_for_publish_confirmation",
        "validation_valid": validation.get("valid") is True,
        "no_blocked_reasons": decision.get("blocked_reasons", []) == [],
    }
    for key, passed in checks.items():
        if not passed:
            blocked.append(key)
    if decision.get("publish_allowed_now") is False:
        warnings.append("r241_16o_publish_allowed_now_false_is_expected_contract")

    return {
        "passed": not blocked and not errors,
        "path": str(path),
        "confirmation": payload,
        "checks": checks,
        "blocked_reasons": blocked,
        "warnings": warnings,
        "errors": errors,
    }


def _remote_exact_path_present(root: Optional[str] = None) -> dict:
    result = _run_git(
        "git_ls_tree_origin_main_target",
        ["git", "ls-tree", "-r", "origin/main", "--", TARGET_WORKFLOW_PATH],
        root=root,
        timeout_seconds=20,
    )
    present = result.get("exit_code") == 0 and TARGET_WORKFLOW_PATH in result.get("stdout_tail", "")
    return {"present": present, "command_result": result}


def run_publish_implementation_prechecks(root: str | None = None) -> dict:
    """Run all critical prechecks before any publish git write operation."""
    root_path = _root(root)
    prechecks: list[dict] = []
    warnings: list[str] = []
    errors: list[str] = []

    confirmation = load_publish_confirmation_for_implementation(str(root_path))
    prechecks.append(
        _new_precheck(
            "r241_16o_confirmation",
            confirmation.get("passed", False),
            PublishImplementationRiskLevel.CRITICAL,
            "R241-16O confirmation must allow R241-16P implementation review.",
            observed_value=confirmation.get("checks"),
            expected_value={"status": "allowed_for_next_review", "requested_option": EXPECTED_OPTION},
            evidence_refs=[confirmation.get("path", "")],
            blocked_reasons=confirmation.get("blocked_reasons", []),
            warnings=confirmation.get("warnings", []),
            errors=confirmation.get("errors", []),
        )
    )

    readiness = publish_review.evaluate_canonical_publish_readiness(str(root_path))
    readiness_validation = publish_review.validate_canonical_publish_readiness(readiness)
    diff = readiness.get("workflow_diff_summary", {})
    readiness_passed = (
        readiness.get("status") == "ready_for_publish_confirmation"
        and readiness.get("decision") == "allow_publish_confirmation_gate"
        and readiness_validation.get("valid") is True
    )
    prechecks.append(
        _new_precheck(
            "r241_16n_canonical_readiness",
            readiness_passed,
            PublishImplementationRiskLevel.CRITICAL,
            "Canonical R241-16N readiness must remain ready and valid.",
            observed_value={"status": readiness.get("status"), "decision": readiness.get("decision")},
            expected_value={"status": "ready_for_publish_confirmation", "decision": "allow_publish_confirmation_gate"},
            evidence_refs=["R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json"],
            blocked_reasons=[] if readiness_passed else readiness_validation.get("violations", ["readiness_not_ready"]),
            warnings=readiness.get("warnings", []),
            errors=readiness.get("errors", []),
        )
    )

    remote_before = _remote_exact_path_present(str(root_path))
    prechecks.append(
        _new_precheck(
            "remote_workflow_missing_before_push",
            remote_before["present"] is False,
            PublishImplementationRiskLevel.HIGH,
            "Remote origin/main should not already contain the target workflow before publish.",
            observed_value=remote_before["present"],
            expected_value=False,
            evidence_refs=["git ls-tree -r origin/main -- .github/workflows/foundation-manual-dispatch.yml"],
            blocked_reasons=[] if remote_before["present"] is False else ["remote_workflow_already_present"],
            errors=remote_before["command_result"].get("errors", []),
        )
    )

    safety_checks = {
        "local_workflow_exists": readiness.get("local_workflow_exists") is True,
        "diff_only_target_workflow": diff.get("diff_only_target_workflow") is True,
        "existing_workflows_unchanged": readiness.get("existing_workflows_unchanged") is True,
        "workflow_content_safe": diff.get("workflow_content_safe") is True,
        "workflow_dispatch_only": diff.get("workflow_dispatch_only") is True,
        "no_pr_trigger": diff.get("has_pr_trigger") is False,
        "no_push_trigger": diff.get("has_push_trigger") is False,
        "no_schedule_trigger": diff.get("has_schedule_trigger") is False,
        "no_secrets": diff.get("has_secrets") is False,
        "no_webhook": diff.get("has_webhook_network") is False,
        "no_runtime_write": diff.get("has_runtime_write") is False,
        "no_audit_jsonl_write": diff.get("has_audit_jsonl_write") is False,
        "no_action_queue_write": diff.get("has_action_queue_write") is False,
        "no_auto_fix": diff.get("has_auto_fix") is False,
    }
    safety_blocked = [key for key, passed in safety_checks.items() if not passed]
    prechecks.append(
        _new_precheck(
            "workflow_safety_and_diff_scope",
            not safety_blocked,
            PublishImplementationRiskLevel.CRITICAL,
            "Target workflow must be the only workflow diff and remain manual-only/safe.",
            observed_value=safety_checks,
            expected_value="all true",
            evidence_refs=[TARGET_WORKFLOW_PATH],
            blocked_reasons=safety_blocked,
        )
    )

    git_version = _run_git("git_version", ["git", "--version"], root=str(root_path))
    prechecks.append(
        _new_precheck(
            "git_available",
            git_version.get("exit_code") == 0,
            PublishImplementationRiskLevel.CRITICAL,
            "git must be available before publish.",
            observed_value=git_version.get("stdout_tail"),
            expected_value="git available",
            blocked_reasons=[] if git_version.get("exit_code") == 0 else ["git_unavailable"],
            errors=git_version.get("errors", []),
        )
    )

    branch = _run_git("git_branch_show_current", ["git", "branch", "--show-current"], root=str(root_path))
    current_branch = branch.get("stdout_tail", "").strip()
    prechecks.append(
        _new_precheck(
            "current_branch_main",
            current_branch == "main",
            PublishImplementationRiskLevel.CRITICAL,
            "Current branch must be main for option_c direct publish.",
            observed_value=current_branch,
            expected_value="main",
            blocked_reasons=[] if current_branch == "main" else ["not_on_main_branch"],
            errors=branch.get("errors", []),
        )
    )

    staged_files = _cached_files(str(root_path))
    prechecks.append(
        _new_precheck(
            "staged_area_empty_before_publish",
            staged_files == [],
            PublishImplementationRiskLevel.CRITICAL,
            "Staged area must be empty before staging target workflow.",
            observed_value=staged_files,
            expected_value=[],
            blocked_reasons=[] if staged_files == [] else ["staged_area_not_empty"],
        )
    )

    target_status = publish_review.inspect_workflow_directory_diff(str(root_path))
    target_changed = target_status.get("target_workflow_changed") is True
    if target_status.get("repo_dirty_outside_workflows_warning"):
        warnings.append("non_workflow_dirty_files_ignored_for_publish_commit")
    prechecks.append(
        _new_precheck(
            "target_workflow_ready_to_add",
            target_changed,
            PublishImplementationRiskLevel.HIGH,
            "Target workflow must be untracked or changed and ready to add.",
            observed_value=target_status.get("workflow_status_entries"),
            expected_value=TARGET_WORKFLOW_PATH,
            blocked_reasons=[] if target_changed else ["target_workflow_not_changed"],
            warnings=target_status.get("warnings", []),
            errors=target_status.get("errors", []),
        )
    )

    rollback_plan = readiness.get("rollback_plan")
    prechecks.append(
        _new_precheck(
            "rollback_plan_exists",
            bool(rollback_plan),
            PublishImplementationRiskLevel.HIGH,
            "Rollback plan must exist before publish.",
            observed_value=bool(rollback_plan),
            expected_value=True,
            blocked_reasons=[] if rollback_plan else ["rollback_plan_missing"],
        )
    )

    passed = all(check["passed"] for check in prechecks)
    return {
        "passed": passed,
        "status": PublishImplementationStepStatus.PASSED if passed else PublishImplementationStepStatus.BLOCKED,
        "prechecks": prechecks,
        "readiness": readiness,
        "readiness_validation": readiness_validation,
        "remote_before_push": remote_before,
        "warnings": warnings,
        "errors": errors,
    }


def capture_publish_mutation_baseline(root: str | None = None) -> dict:
    """Capture hashes, mtimes, line counts, and git status before publish."""
    root_path = _root(root)
    workflow_states = {
        TARGET_WORKFLOW_PATH: _file_state(root_path / TARGET_WORKFLOW_PATH),
        **{path: _file_state(root_path / path) for path in EXISTING_WORKFLOW_PATHS},
    }
    status_scoped = _run_git(
        "git_status_workflows_baseline",
        ["git", "status", "--porcelain", "--", ".github/workflows/"],
        root=str(root_path),
    )
    staged = _run_git("git_diff_cached_baseline", ["git", "diff", "--cached", "--name-only"], root=str(root_path))
    runtime_states = _path_mtimes(
        root_path,
        [
            "runtime",
            "action_queue",
            "memory",
            "asset_registry",
            "prompt_runtime",
            "rtcm",
            "governance_state.json",
            "experiment_queue.json",
        ],
    )
    return {
        "captured_at": _now(),
        "workflow_file_states": workflow_states,
        "audit_jsonl_line_counts": _jsonl_line_counts(root_path),
        "runtime_action_queue_path_states": runtime_states,
        "workflow_git_status": status_scoped.get("stdout_tail", ""),
        "staged_files": [line.strip().replace("\\", "/") for line in staged.get("stdout_tail", "").splitlines() if line.strip()],
        "warnings": [],
        "errors": status_scoped.get("errors", []) + staged.get("errors", []),
    }


def stage_only_target_workflow(root: str | None = None) -> dict:
    """Stage only the target workflow and verify no other file is staged."""
    root_path = _root(root)
    command = _run_git(
        "git_add_target_workflow",
        ["git", "add", TARGET_WORKFLOW_PATH],
        root=str(root_path),
        would_modify_git_history=True,
    )
    if command.get("exit_code") != 0:
        command["blocked_reasons"].append("git_add_target_failed")
        return {"status": PublishImplementationStepStatus.FAILED, "command_result": command, "staged_files": [], "warnings": [], "errors": command.get("errors", [])}

    staged_files = _cached_files(str(root_path))
    if staged_files != [TARGET_WORKFLOW_PATH]:
        reset = _run_git(
            "git_reset_target_after_extra_staged",
            ["git", "reset", "--", TARGET_WORKFLOW_PATH],
            root=str(root_path),
            would_modify_git_history=True,
        )
        command["blocked_reasons"].append("extra_staged_files_detected")
        return {
            "status": PublishImplementationStepStatus.BLOCKED,
            "command_result": command,
            "rollback_result": reset,
            "staged_files": staged_files,
            "warnings": ["target_unstaged_after_extra_staged_detection"],
            "errors": ["staged_files_must_only_include_target_workflow"],
        }
    return {
        "status": PublishImplementationStepStatus.PASSED,
        "command_result": command,
        "staged_files": staged_files,
        "warnings": [],
        "errors": [],
    }


def commit_target_workflow(root: str | None = None) -> dict:
    """Commit the staged target workflow if and only if it is the sole staged file."""
    root_path = _root(root)
    staged_files = _cached_files(str(root_path))
    if staged_files != [TARGET_WORKFLOW_PATH]:
        return {
            "status": PublishImplementationStepStatus.BLOCKED,
            "command_result": _command_result(
                "git_commit_target_workflow",
                ["git", "commit", "-m", COMMIT_MESSAGE],
                False,
                None,
                would_modify_git_history=True,
                blocked_reasons=["commit_requires_only_target_staged"],
            ),
            "commit_hash": None,
            "changed_files": staged_files,
            "warnings": [],
            "errors": ["commit_requires_only_target_staged"],
        }
    command = _run_git(
        "git_commit_target_workflow",
        ["git", "commit", "-m", COMMIT_MESSAGE],
        root=str(root_path),
        timeout_seconds=120,
        would_modify_git_history=True,
    )
    if command.get("exit_code") != 0:
        return {
            "status": PublishImplementationStepStatus.FAILED,
            "command_result": command,
            "commit_hash": None,
            "changed_files": [],
            "warnings": [],
            "errors": ["git_commit_failed"],
        }
    commit_hash = _head_commit_hash(str(root_path))
    changed = _run_git(
        "git_diff_tree_publish_commit",
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash or "HEAD"],
        root=str(root_path),
    )
    changed_files = [line.strip().replace("\\", "/") for line in changed.get("stdout_tail", "").splitlines() if line.strip()]
    if changed_files != [TARGET_WORKFLOW_PATH]:
        return {
            "status": PublishImplementationStepStatus.BLOCKED,
            "command_result": command,
            "commit_hash": commit_hash,
            "changed_files": changed_files,
            "warnings": [],
            "errors": ["commit_contains_non_target_files"],
        }
    return {
        "status": PublishImplementationStepStatus.PASSED,
        "command_result": command,
        "commit_hash": commit_hash,
        "changed_files": changed_files,
        "warnings": [],
        "errors": [],
    }


def push_publish_commit(root: str | None = None, branch: str = "main") -> dict:
    """Push the publish commit to origin/main only."""
    if branch != "main":
        return {
            "status": PublishImplementationStepStatus.BLOCKED,
            "command_result": _command_result(
                "git_push_origin_main",
                ["git", "push", "origin", branch],
                False,
                None,
                would_push_remote=True,
                blocked_reasons=["push_branch_must_be_main"],
            ),
            "remote_branch": branch,
            "warnings": [],
            "errors": ["push_branch_must_be_main"],
        }
    command = _run_git(
        "git_push_origin_main",
        ["git", "push", "origin", "main"],
        root=root,
        timeout_seconds=180,
        would_push_remote=True,
    )
    if command.get("exit_code") != 0:
        return {
            "status": PublishImplementationStepStatus.FAILED,
            "command_result": command,
            "remote_branch": "origin/main",
            "warnings": [],
            "errors": ["git_push_failed"],
        }
    return {
        "status": PublishImplementationStepStatus.PASSED,
        "command_result": command,
        "remote_branch": "origin/main",
        "warnings": [],
        "errors": [],
    }


def verify_remote_workflow_after_publish(root: str | None = None) -> dict:
    """Verify remote visibility without triggering any workflow run."""
    root_path = _root(root)
    ls_tree = _remote_exact_path_present(str(root_path))
    content = publish_review.inspect_publish_workflow_content_safety(str(root_path))
    gh_visible = None
    warnings: list[str] = []
    errors: list[str] = []
    gh_results: list[dict] = []
    if shutil.which("gh") is None:
        warnings.append("gh_unavailable_remote_visibility_checked_by_git_only")
    else:
        warnings.append("gh_readonly_verification_skipped_to_avoid_secret_access")
    valid = (
        ls_tree["present"] is True
        and content.get("workflow_dispatch_only") is True
        and content.get("has_pr_trigger") is False
        and content.get("has_push_trigger") is False
        and content.get("has_schedule_trigger") is False
        and content.get("has_secrets") is False
        and content.get("has_webhook_network") is False
        and content.get("has_runtime_write") is False
        and content.get("has_audit_jsonl_write") is False
        and content.get("has_action_queue_write") is False
    )
    if not valid:
        errors.append("remote_or_content_verification_failed")
    return {
        "verification_id": f"verify-publish-{uuid.uuid4().hex[:10]}",
        "valid": valid,
        "local_workflow_exists": content.get("local_workflow_exists"),
        "remote_workflow_exact_path_present": ls_tree["present"],
        "gh_workflow_visible": gh_visible,
        "workflow_dispatch_only": content.get("workflow_dispatch_only"),
        "no_pr_trigger": content.get("has_pr_trigger") is False,
        "no_push_trigger": content.get("has_push_trigger") is False,
        "no_schedule_trigger": content.get("has_schedule_trigger") is False,
        "no_secrets": content.get("has_secrets") is False,
        "no_webhook": content.get("has_webhook_network") is False,
        "no_runtime_write": content.get("has_runtime_write") is False,
        "no_audit_jsonl_write": content.get("has_audit_jsonl_write") is False,
        "no_action_queue_write": content.get("has_action_queue_write") is False,
        "existing_workflows_unchanged": True,
        "git_ls_tree_result": ls_tree["command_result"],
        "gh_results": gh_results,
        "warnings": warnings,
        "errors": errors + ls_tree["command_result"].get("errors", []),
    }


def verify_publish_local_mutation_guard(root: str | None = None, baseline: dict | None = None) -> dict:
    """Verify publish did not mutate existing workflows, JSONL, or runtime paths."""
    root_path = _root(root)
    baseline = baseline or capture_publish_mutation_baseline(str(root_path))
    current = capture_publish_mutation_baseline(str(root_path))
    errors: list[str] = []
    warnings: list[str] = []

    for path in [TARGET_WORKFLOW_PATH, *EXISTING_WORKFLOW_PATHS]:
        before = baseline.get("workflow_file_states", {}).get(path, {})
        after = current.get("workflow_file_states", {}).get(path, {})
        if before.get("sha256") != after.get("sha256"):
            errors.append(f"workflow_content_changed:{path}")
    if baseline.get("audit_jsonl_line_counts", {}) != current.get("audit_jsonl_line_counts", {}):
        errors.append("audit_jsonl_line_count_changed")
    for path, before in baseline.get("runtime_action_queue_path_states", {}).items():
        after = current.get("runtime_action_queue_path_states", {}).get(path, {})
        if before.get("mtime") != after.get("mtime"):
            errors.append(f"runtime_or_queue_path_mtime_changed:{path}")

    return {
        "valid": not errors,
        "target_workflow_content_unchanged": TARGET_WORKFLOW_PATH not in " ".join(errors),
        "existing_workflows_unchanged": not any(path in " ".join(errors) for path in EXISTING_WORKFLOW_PATHS),
        "audit_jsonl_unchanged": "audit_jsonl_line_count_changed" not in errors,
        "runtime_action_queue_unchanged": not any(err.startswith("runtime_or_queue_path_mtime_changed") for err in errors),
        "baseline": baseline,
        "current": current,
        "warnings": warnings,
        "errors": errors,
    }


def rollback_failed_publish(root: str | None = None, result: dict | None = None, reason: str | None = None) -> dict:
    """Perform only allowed limited rollback, or report manual rollback guidance."""
    result = result or {}
    commit_succeeded = bool(result.get("commit_succeeded"))
    push_attempted = bool(result.get("push_attempted"))
    if not commit_succeeded:
        reset = _run_git(
            "git_reset_target_workflow_after_failed_publish",
            ["git", "reset", "--", TARGET_WORKFLOW_PATH],
            root=root,
            would_modify_git_history=True,
        )
        return {
            "mode": "unstage_target_only",
            "executed": True,
            "command_result": reset,
            "reason": reason,
            "warnings": ["only target workflow was unstaged; no hard reset used"],
            "errors": [] if reset.get("exit_code") == 0 else ["target_unstage_failed"],
        }
    if commit_succeeded and not push_attempted:
        return {
            "mode": "manual_revert_commit_before_push",
            "executed": False,
            "reason": reason,
            "warnings": ["commit exists locally; manual revert/reset review required"],
            "errors": [],
        }
    return {
        "mode": "manual_remote_rollback_required",
        "executed": False,
        "reason": reason,
        "warnings": ["push may have reached remote; do not force push automatically"],
        "errors": [],
    }


def execute_publish_implementation(root: str | None = None) -> dict:
    """Execute the constrained publish flow."""
    root_path = _root(root)
    result: dict[str, Any] = {
        "result_id": f"publish-impl-{uuid.uuid4().hex[:12]}",
        "generated_at": _now(),
        "status": PublishImplementationStatus.UNKNOWN,
        "decision": PublishImplementationDecision.UNKNOWN,
        "requested_option": EXPECTED_OPTION,
        "workflow_path": TARGET_WORKFLOW_PATH,
        "commit_attempted": False,
        "commit_succeeded": False,
        "push_attempted": False,
        "push_succeeded": False,
        "commit_hash": None,
        "remote_branch": "origin/main",
        "prechecks": [],
        "git_command_results": [],
        "remote_visibility_after_push": {},
        "local_mutation_guard": {},
        "existing_workflows_unchanged": None,
        "rollback_plan": publish_review.build_publish_rollback_plan(),
        "rollback_result": None,
        "warnings": [],
        "errors": [],
    }

    precheck_bundle = run_publish_implementation_prechecks(str(root_path))
    result["prechecks"] = precheck_bundle.get("prechecks", [])
    result["warnings"].extend(precheck_bundle.get("warnings", []))
    result["errors"].extend(precheck_bundle.get("errors", []))
    if not precheck_bundle.get("passed"):
        result["status"] = PublishImplementationStatus.BLOCKED_PRECHECK_FAILED
        result["decision"] = PublishImplementationDecision.BLOCK_PUBLISH
        return result

    baseline = capture_publish_mutation_baseline(str(root_path))
    result["baseline_capture"] = baseline

    stage = stage_only_target_workflow(str(root_path))
    result["git_command_results"].append(stage.get("command_result", {}))
    if stage.get("status") != PublishImplementationStepStatus.PASSED:
        result["status"] = PublishImplementationStatus.BLOCKED_UNEXPECTED_DIFF
        result["decision"] = PublishImplementationDecision.BLOCK_PUBLISH
        result["errors"].extend(stage.get("errors", []))
        result["rollback_result"] = rollback_failed_publish(str(root_path), result, "stage_only_target_failed")
        result["local_mutation_guard"] = verify_publish_local_mutation_guard(str(root_path), baseline)
        return result

    result["commit_attempted"] = True
    commit = commit_target_workflow(str(root_path))
    result["git_command_results"].append(commit.get("command_result", {}))
    result["commit_hash"] = commit.get("commit_hash")
    result["commit_changed_files"] = commit.get("changed_files", [])
    if commit.get("status") != PublishImplementationStepStatus.PASSED:
        result["status"] = PublishImplementationStatus.COMMIT_FAILED
        result["decision"] = PublishImplementationDecision.BLOCK_PUBLISH
        result["errors"].extend(commit.get("errors", []))
        result["rollback_result"] = rollback_failed_publish(str(root_path), result, "commit_failed")
        result["local_mutation_guard"] = verify_publish_local_mutation_guard(str(root_path), baseline)
        result["existing_workflows_unchanged"] = result["local_mutation_guard"].get("existing_workflows_unchanged")
        return result
    result["commit_succeeded"] = True

    result["push_attempted"] = True
    push = push_publish_commit(str(root_path), "main")
    result["git_command_results"].append(push.get("command_result", {}))
    if push.get("status") != PublishImplementationStepStatus.PASSED:
        result["status"] = PublishImplementationStatus.PUSH_FAILED
        result["decision"] = PublishImplementationDecision.BLOCK_PUBLISH
        result["errors"].extend(push.get("errors", []))
        result["rollback_result"] = rollback_failed_publish(str(root_path), result, "push_failed")
        result["local_mutation_guard"] = verify_publish_local_mutation_guard(str(root_path), baseline)
        result["existing_workflows_unchanged"] = result["local_mutation_guard"].get("existing_workflows_unchanged")
        return result
    result["push_succeeded"] = True

    remote = verify_remote_workflow_after_publish(str(root_path))
    result["remote_visibility_after_push"] = remote
    if not remote.get("valid"):
        result["status"] = PublishImplementationStatus.REMOTE_VERIFICATION_FAILED
        result["decision"] = PublishImplementationDecision.VERIFY_REMOTE_VISIBILITY
        result["errors"].extend(remote.get("errors", []))
        result["rollback_result"] = rollback_failed_publish(str(root_path), result, "remote_verification_failed")
        return result

    guard = verify_publish_local_mutation_guard(str(root_path), baseline)
    result["local_mutation_guard"] = guard
    result["existing_workflows_unchanged"] = guard.get("existing_workflows_unchanged")
    if not guard.get("valid"):
        result["status"] = PublishImplementationStatus.ROLLBACK_REQUIRED
        result["decision"] = PublishImplementationDecision.ROLLBACK_PUBLISH
        result["errors"].extend(guard.get("errors", []))
        result["rollback_result"] = rollback_failed_publish(str(root_path), result, "mutation_guard_failed")
        return result

    result["status"] = PublishImplementationStatus.PUBLISHED
    result["decision"] = PublishImplementationDecision.VERIFY_REMOTE_VISIBILITY
    return result


def validate_publish_implementation_result(result: dict) -> dict:
    """Validate the publish result against the R241-16P safety contract."""
    errors: list[str] = []
    warnings: list[str] = []
    command_results = result.get("git_command_results", [])
    command_ids = [cmd.get("command_id") for cmd in command_results]

    if result.get("push_attempted") and not result.get("commit_succeeded"):
        errors.append("push_attempted_before_commit_success")
    if result.get("commit_attempted") and not result.get("prechecks"):
        errors.append("commit_attempted_without_precheck_record")
    for cmd in command_results:
        argv = cmd.get("argv", [])
        joined = " ".join(argv)
        if cmd.get("shell_allowed") is not False:
            errors.append(f"shell_allowed_forbidden:{cmd.get('command_id')}")
        if "workflow run" in joined or "gh run" in joined:
            errors.append("gh_workflow_run_forbidden")
        if argv[:3] == ["git", "push", "origin"] and argv != ["git", "push", "origin", "main"]:
            errors.append("push_branch_not_origin_main")
    if result.get("commit_succeeded"):
        commit_check = next((cmd for cmd in command_results if cmd.get("command_id") == "git_commit_target_workflow"), {})
        if commit_check.get("exit_code") != 0:
            errors.append("commit_succeeded_but_commit_command_failed")
    if result.get("commit_changed_files") and result.get("commit_changed_files") != [TARGET_WORKFLOW_PATH]:
        errors.append("commit_includes_non_target")

    remote = result.get("remote_visibility_after_push", {})
    if remote:
        if remote.get("no_pr_trigger") is not True:
            errors.append("pr_trigger_present")
        if remote.get("no_push_trigger") is not True:
            errors.append("push_trigger_present")
        if remote.get("no_schedule_trigger") is not True:
            errors.append("schedule_trigger_present")
        if remote.get("no_secrets") is not True:
            errors.append("secrets_present")
        if remote.get("no_webhook") is not True:
            errors.append("webhook_present")
    guard = result.get("local_mutation_guard", {})
    if guard:
        if guard.get("runtime_action_queue_unchanged") is False:
            errors.append("runtime_write_detected")
        if guard.get("audit_jsonl_unchanged") is False:
            errors.append("audit_jsonl_write_detected")
        if guard.get("existing_workflows_unchanged") is False:
            errors.append("existing_workflow_modified")
    if result.get("auto_fix_executed") is True:
        errors.append("auto_fix_executed")
    if not result.get("rollback_plan"):
        errors.append("rollback_plan_missing")
    if "auto_fix" in _json(result).lower() and "auto_fix_executed" in _json(result).lower():
        warnings.append("auto_fix_terms_are_reported_as_negative_safety_fields_only")
    return {"valid": not errors, "warnings": warnings, "errors": errors, "command_ids": command_ids}


def _render_report(result: dict, validation: dict) -> str:
    remote = result.get("remote_visibility_after_push", {})
    guard = result.get("local_mutation_guard", {})
    precheck_lines = [
        f"- `{c.get('check_type')}` passed=`{c.get('passed')}` blocked=`{c.get('blocked_reasons')}`"
        for c in result.get("prechecks", [])
    ]
    command_lines = [
        f"- `{c.get('command_id')}` argv=`{' '.join(c.get('argv', []))}` exit=`{c.get('exit_code')}`"
        for c in result.get("git_command_results", [])
    ]
    return "\n".join(
        [
            "# R241-16P Publish Implementation Report",
            "",
            "## 1. 修改文件清单",
            "- `backend/app/foundation/ci_publish_implementation.py`",
            "- `backend/app/foundation/test_ci_publish_implementation.py`",
            "- `migration_reports/foundation_audit/R241-16P_PUBLISH_IMPLEMENTATION_RESULT.json`",
            "- `migration_reports/foundation_audit/R241-16P_PUBLISH_IMPLEMENTATION_REPORT.md`",
            "- Published target, if successful: `.github/workflows/foundation-manual-dispatch.yml`",
            "",
            "## 2. PublishImplementationStatus / Decision / RiskLevel / StepStatus",
            "- Status values: `published`, `blocked_precheck_failed`, `blocked_readiness_stale`, `blocked_unexpected_diff`, `blocked_workflow_unsafe`, `blocked_git_unavailable`, `commit_failed`, `push_failed`, `remote_verification_failed`, `rollback_required`, `unknown`",
            "- Decision values: `execute_publish`, `block_publish`, `verify_remote_visibility`, `rollback_publish`, `unknown`",
            "- Risk levels: `low`, `medium`, `high`, `critical`, `unknown`",
            "- Step status values: `pending`, `passed`, `failed`, `skipped`, `blocked`, `warning`, `unknown`",
            "",
            "## 3. PublishImplementationPrecheck 字段",
            "`precheck_id`, `check_type`, `passed`, `risk_level`, `description`, `observed_value`, `expected_value`, `evidence_refs`, `blocked_reasons`, `warnings`, `errors`",
            "",
            "## 4. PublishGitCommandResult 字段",
            "`command_id`, `argv`, `command_executed`, `shell_allowed`, `exit_code`, `stdout_tail`, `stderr_tail`, `runtime_seconds`, `would_modify_git_history`, `would_push_remote`, `blocked_reasons`, `warnings`, `errors`",
            "",
            "## 5. PublishImplementationResult 字段",
            "`result_id`, `generated_at`, `status`, `decision`, `requested_option`, `workflow_path`, `commit_attempted`, `commit_succeeded`, `push_attempted`, `push_succeeded`, `commit_hash`, `remote_branch`, `prechecks`, `git_command_results`, `remote_visibility_after_push`, `local_mutation_guard`, `existing_workflows_unchanged`, `rollback_plan`, `warnings`, `errors`",
            "",
            "## 6. PublishPostVerification 字段",
            "`verification_id`, `valid`, `local_workflow_exists`, `remote_workflow_exact_path_present`, `gh_workflow_visible`, `workflow_dispatch_only`, `no_pr_trigger`, `no_push_trigger`, `no_schedule_trigger`, `no_secrets`, `no_webhook`, `no_runtime_write`, `no_audit_jsonl_write`, `no_action_queue_write`, `existing_workflows_unchanged`, `warnings`, `errors`",
            "",
            "## 7. confirmation loading 结果",
            f"- requested_option: `{result.get('requested_option')}`",
            "",
            "## 8. precheck 结果",
            *(precheck_lines or ["- No prechecks recorded."]),
            "",
            "## 9. baseline capture 结果",
            f"- baseline captured: `{bool(result.get('baseline_capture'))}`",
            "",
            "## 10. stage only target workflow 结果",
            f"- command ids: `{[c.get('command_id') for c in result.get('git_command_results', [])]}`",
            "",
            "## 11. commit 结果",
            f"- commit_attempted: `{result.get('commit_attempted')}`",
            f"- commit_succeeded: `{result.get('commit_succeeded')}`",
            f"- commit_hash: `{result.get('commit_hash')}`",
            "",
            "## 12. push 结果",
            f"- push_attempted: `{result.get('push_attempted')}`",
            f"- push_succeeded: `{result.get('push_succeeded')}`",
            f"- remote_branch: `{result.get('remote_branch')}`",
            "",
            "## 13. remote verification 结果",
            f"- remote_workflow_exact_path_present: `{remote.get('remote_workflow_exact_path_present')}`",
            f"- workflow_dispatch_only: `{remote.get('workflow_dispatch_only')}`",
            f"- warnings: `{remote.get('warnings')}`",
            f"- errors: `{remote.get('errors')}`",
            "",
            "## 14. local mutation guard 结果",
            f"- valid: `{guard.get('valid')}`",
            f"- existing_workflows_unchanged: `{guard.get('existing_workflows_unchanged')}`",
            f"- audit_jsonl_unchanged: `{guard.get('audit_jsonl_unchanged')}`",
            f"- runtime_action_queue_unchanged: `{guard.get('runtime_action_queue_unchanged')}`",
            "",
            "## 15. rollback result 如有",
            f"- rollback_result: `{result.get('rollback_result')}`",
            "",
            "## 16. validation result",
            f"- valid: `{validation.get('valid')}`",
            f"- errors: `{validation.get('errors')}`",
            "",
            "## 17. 测试结果",
            "- See final assistant response for executed validation commands and results.",
            "",
            "## 18. 是否执行 git commit",
            f"- `{result.get('commit_attempted')}`",
            "",
            "## 19. 是否执行 git push",
            f"- `{result.get('push_attempted')}`",
            "",
            "## 20. 是否执行 gh workflow run",
            "- `false`",
            "",
            "## 21. 是否启用 PR/push/schedule trigger",
            f"- PR: `{not remote.get('no_pr_trigger') if remote else False}`",
            f"- push: `{not remote.get('no_push_trigger') if remote else False}`",
            f"- schedule: `{not remote.get('no_schedule_trigger') if remote else False}`",
            "",
            "## 22. 是否读取 secret",
            "- `false`",
            "",
            "## 23. 是否修改 existing workflows",
            f"- `{guard.get('existing_workflows_unchanged') is False}`",
            "",
            "## 24. 是否写 runtime / audit JSONL / action queue",
            f"- runtime/action queue changed: `{guard.get('runtime_action_queue_unchanged') is False}`",
            f"- audit JSONL changed: `{guard.get('audit_jsonl_unchanged') is False}`",
            "",
            "## 25. 是否执行 auto-fix",
            "- `false`",
            "",
            "## 26. Git command results",
            *(command_lines or ["- No git commands executed."]),
            "",
            "## 27. 当前剩余断点",
            f"- status: `{result.get('status')}`",
            f"- errors: `{result.get('errors')}`",
            "",
            "## 28. 下一轮建议",
            "- If status is `published`, proceed to R241-16Q Remote Visibility Verification / Plan-only Dispatch Retry.",
            "- If status is `push_failed`, resolve git auth/permission/branch protection before retrying; do not force push.",
            "- If status is `remote_verification_failed`, run read-only remote visibility repair/review.",
        ]
    )


def generate_publish_implementation_report(result: dict | None = None, output_path: str | None = None) -> dict:
    """Write R241-16P implementation JSON and Markdown reports."""
    if result is None:
        result = execute_publish_implementation()
    validation = validate_publish_implementation_result(result)
    output_dir = REPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = Path(output_path) if output_path else output_dir / "R241-16P_PUBLISH_IMPLEMENTATION_RESULT.json"
    md_path = json_path.with_suffix(".md") if output_path else output_dir / "R241-16P_PUBLISH_IMPLEMENTATION_REPORT.md"
    payload = {
        "generated_at": _now(),
        "result": result,
        "validation": validation,
        "warnings": result.get("warnings", []) + validation.get("warnings", []),
        "errors": result.get("errors", []) + validation.get("errors", []),
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(_json(payload), encoding="utf-8")
    md_path.write_text(_render_report(result, validation), encoding="utf-8")
    return {
        "output_path": str(json_path),
        "report_path": str(md_path),
        "result": result,
        "validation": validation,
        "warnings": payload["warnings"],
        "errors": payload["errors"],
    }
