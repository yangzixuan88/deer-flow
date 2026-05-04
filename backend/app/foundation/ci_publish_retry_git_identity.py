"""R241-16P-Retry publish implementation after repo-local Git identity setup."""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from app.foundation import ci_publish_implementation as publish_impl
except ModuleNotFoundError:  # pragma: no cover
    from backend.app.foundation import ci_publish_implementation as publish_impl


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_NAME = "OpenClaw Foundation CI"
DEFAULT_EMAIL = "openclaw-foundation-ci@example.local"


class PublishRetryStatus:
    IDENTITY_CONFIGURED = "identity_configured"
    IDENTITY_ALREADY_PRESENT = "identity_already_present"
    IDENTITY_CONFIGURATION_FAILED = "identity_configuration_failed"
    RETRY_PUBLISHED = "retry_published"
    RETRY_COMMIT_FAILED = "retry_commit_failed"
    RETRY_PUSH_FAILED = "retry_push_failed"
    RETRY_PRECHECK_FAILED = "retry_precheck_failed"
    RETRY_REMOTE_VERIFICATION_FAILED = "retry_remote_verification_failed"
    RETRY_BLOCKED = "retry_blocked"
    UNKNOWN = "unknown"


class GitIdentityScope:
    REPO_LOCAL = "repo_local"
    GLOBAL_FORBIDDEN = "global_forbidden"
    ALREADY_CONFIGURED = "already_configured"
    UNKNOWN = "unknown"


class PublishRetryDecision:
    CONFIGURE_IDENTITY_AND_RETRY = "configure_identity_and_retry"
    RETRY_PUBLISH_ONLY = "retry_publish_only"
    BLOCK_RETRY = "block_retry"
    UNKNOWN = "unknown"


class PublishRetryRiskLevel:
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


def _run_git(argv: list[str], root: Optional[str] = None, timeout_seconds: int = 30) -> dict:
    started = time.perf_counter()
    if not argv or argv[0] != "git":
        return {
            "argv": argv,
            "command_executed": False,
            "shell_allowed": False,
            "exit_code": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "runtime_seconds": 0.0,
            "warnings": [],
            "errors": ["non_git_command_rejected"],
        }
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
            "warnings": [],
            "errors": [str(exc)],
        }


def _load_previous_publish_result(root: Optional[str] = None) -> dict:
    path = _root(root) / "migration_reports" / "foundation_audit" / "R241-16P_PUBLISH_IMPLEMENTATION_RESULT.json"
    if not path.exists():
        return {"exists": False, "path": str(path), "payload": {}, "warnings": [], "errors": ["previous_publish_result_missing"]}
    try:
        return {
            "exists": True,
            "path": str(path),
            "payload": json.loads(path.read_text(encoding="utf-8")),
            "warnings": [],
            "errors": [],
        }
    except json.JSONDecodeError as exc:
        return {"exists": True, "path": str(path), "payload": {}, "warnings": [], "errors": [str(exc)]}


def _previous_failure_identity_related(previous: dict) -> bool:
    payload = previous.get("payload", {})
    result = payload.get("result", {})
    if result.get("status") != publish_impl.PublishImplementationStatus.COMMIT_FAILED:
        return False
    text = json.dumps(result.get("git_command_results", []), ensure_ascii=False).lower()
    return "author identity unknown" in text or "unable to auto-detect email" in text


def check_git_author_identity(root: str | None = None) -> dict:
    """Check repo-effective Git author identity without reading secrets."""
    name_result = _run_git(["git", "config", "user.name"], root=root)
    email_result = _run_git(["git", "config", "user.email"], root=root)
    name = name_result.get("stdout_tail", "").strip()
    email = email_result.get("stdout_tail", "").strip()
    name_present = name_result.get("exit_code") == 0 and bool(name)
    email_present = email_result.get("exit_code") == 0 and bool(email)
    return {
        "check_id": f"git-identity-{uuid.uuid4().hex[:10]}",
        "name_present": name_present,
        "email_present": email_present,
        "current_name": name if name_present else "",
        "current_email": email if email_present else "",
        "scope": GitIdentityScope.ALREADY_CONFIGURED if name_present and email_present else GitIdentityScope.REPO_LOCAL,
        "needs_configuration": not (name_present and email_present),
        "allowed_to_configure": True,
        "configured_this_round": False,
        "command_results": [name_result, email_result],
        "warnings": [],
        "errors": [],
    }


def configure_repo_local_git_identity(
    name: str = DEFAULT_NAME,
    email: str = DEFAULT_EMAIL,
    root: str | None = None,
) -> dict:
    """Configure repo-local identity only. Never uses `--global`."""
    command_results = [
        _run_git(["git", "config", "user.name", name], root=root),
        _run_git(["git", "config", "user.email", email], root=root),
    ]
    identity = check_git_author_identity(root)
    success = all(cmd.get("exit_code") == 0 for cmd in command_results) and identity["name_present"] and identity["email_present"]
    return {
        "command_results": command_results,
        "configured_name": identity.get("current_name"),
        "configured_email": identity.get("current_email"),
        "scope": GitIdentityScope.REPO_LOCAL,
        "configuration_succeeded": success,
        "global_config_modified": False,
        "warnings": [] if success else ["repo_local_git_identity_configuration_incomplete"],
        "errors": [] if success else ["git_identity_configuration_failed"],
    }


def validate_git_identity_for_publish(identity: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if identity.get("name_present") is not True:
        errors.append("git_user_name_missing")
    if identity.get("email_present") is not True:
        errors.append("git_user_email_missing")
    if identity.get("current_email") and "@" not in identity.get("current_email", ""):
        errors.append("git_user_email_invalid")
    if identity.get("scope") not in {GitIdentityScope.REPO_LOCAL, GitIdentityScope.ALREADY_CONFIGURED}:
        errors.append("git_identity_scope_invalid")
    if identity.get("global_config_modified") is True:
        errors.append("global_git_config_modified")
    return {"valid": not errors, "warnings": warnings, "errors": errors}


def _status_from_publish_result(publish_result: dict) -> str:
    status = publish_result.get("status")
    if status == publish_impl.PublishImplementationStatus.PUBLISHED:
        return PublishRetryStatus.RETRY_PUBLISHED
    if status == publish_impl.PublishImplementationStatus.COMMIT_FAILED:
        return PublishRetryStatus.RETRY_COMMIT_FAILED
    if status == publish_impl.PublishImplementationStatus.PUSH_FAILED:
        return PublishRetryStatus.RETRY_PUSH_FAILED
    if status == publish_impl.PublishImplementationStatus.BLOCKED_PRECHECK_FAILED:
        return PublishRetryStatus.RETRY_PRECHECK_FAILED
    if status == publish_impl.PublishImplementationStatus.REMOTE_VERIFICATION_FAILED:
        return PublishRetryStatus.RETRY_REMOTE_VERIFICATION_FAILED
    return PublishRetryStatus.RETRY_BLOCKED


def evaluate_publish_retry_with_identity_setup(
    root: str | None = None,
    configure_if_missing: bool = True,
) -> dict:
    """Configure repo-local identity if needed, then retry R241-16P publish."""
    previous = _load_previous_publish_result(root)
    warnings: list[str] = []
    errors: list[str] = []
    if not previous.get("exists") or not _previous_failure_identity_related(previous):
        return {
            "retry_id": f"publish-retry-{uuid.uuid4().hex[:12]}",
            "generated_at": _now(),
            "status": PublishRetryStatus.RETRY_BLOCKED,
            "decision": PublishRetryDecision.BLOCK_RETRY,
            "previous_publish_result": previous,
            "git_identity_check": {},
            "identity_configuration_result": {},
            "publish_result": {},
            "validation_result": {"valid": False, "errors": ["previous_failure_not_identity_related"], "warnings": []},
            "local_mutation_guard": {},
            "existing_workflows_unchanged": None,
            "warnings": warnings,
            "errors": ["previous_failure_not_identity_related"],
        }

    identity = check_git_author_identity(root)
    config_result: dict = {}
    decision = PublishRetryDecision.RETRY_PUBLISH_ONLY
    if identity.get("needs_configuration"):
        if not configure_if_missing:
            return {
                "retry_id": f"publish-retry-{uuid.uuid4().hex[:12]}",
                "generated_at": _now(),
                "status": PublishRetryStatus.IDENTITY_CONFIGURATION_FAILED,
                "decision": PublishRetryDecision.BLOCK_RETRY,
                "previous_publish_result": previous,
                "git_identity_check": identity,
                "identity_configuration_result": {},
                "publish_result": {},
                "validation_result": {"valid": False, "errors": ["git_identity_missing"], "warnings": []},
                "local_mutation_guard": {},
                "existing_workflows_unchanged": None,
                "warnings": [],
                "errors": ["git_identity_missing"],
            }
        decision = PublishRetryDecision.CONFIGURE_IDENTITY_AND_RETRY
        config_result = configure_repo_local_git_identity(root=root)
        if not config_result.get("configuration_succeeded"):
            return {
                "retry_id": f"publish-retry-{uuid.uuid4().hex[:12]}",
                "generated_at": _now(),
                "status": PublishRetryStatus.IDENTITY_CONFIGURATION_FAILED,
                "decision": PublishRetryDecision.BLOCK_RETRY,
                "previous_publish_result": previous,
                "git_identity_check": identity,
                "identity_configuration_result": config_result,
                "publish_result": {},
                "validation_result": {"valid": False, "errors": config_result.get("errors", []), "warnings": []},
                "local_mutation_guard": {},
                "existing_workflows_unchanged": None,
                "warnings": config_result.get("warnings", []),
                "errors": config_result.get("errors", []),
            }
        identity = check_git_author_identity(root)
        identity["configured_this_round"] = True
    else:
        warnings.append("git_identity_already_present")

    identity_validation = validate_git_identity_for_publish(identity)
    if not identity_validation["valid"]:
        return {
            "retry_id": f"publish-retry-{uuid.uuid4().hex[:12]}",
            "generated_at": _now(),
            "status": PublishRetryStatus.IDENTITY_CONFIGURATION_FAILED,
            "decision": PublishRetryDecision.BLOCK_RETRY,
            "previous_publish_result": previous,
            "git_identity_check": identity,
            "identity_configuration_result": config_result,
            "publish_result": {},
            "validation_result": identity_validation,
            "local_mutation_guard": {},
            "existing_workflows_unchanged": None,
            "warnings": warnings,
            "errors": identity_validation.get("errors", []),
        }

    publish_result = publish_impl.execute_publish_implementation(root)
    publish_validation = publish_impl.validate_publish_implementation_result(publish_result)
    local_guard = publish_result.get("local_mutation_guard", {})
    status = _status_from_publish_result(publish_result)
    return {
        "retry_id": f"publish-retry-{uuid.uuid4().hex[:12]}",
        "generated_at": _now(),
        "status": status,
        "decision": decision,
        "previous_publish_result": previous,
        "git_identity_check": identity,
        "identity_configuration_result": config_result,
        "publish_result": publish_result,
        "validation_result": publish_validation,
        "local_mutation_guard": local_guard,
        "existing_workflows_unchanged": local_guard.get("existing_workflows_unchanged"),
        "warnings": warnings + publish_result.get("warnings", []) + publish_validation.get("warnings", []),
        "errors": publish_result.get("errors", []) + publish_validation.get("errors", []),
    }


def _render_report(result: dict) -> str:
    publish = result.get("publish_result", {})
    identity = result.get("git_identity_check", {})
    config = result.get("identity_configuration_result", {})
    remote = publish.get("remote_visibility_after_push", {})
    guard = result.get("local_mutation_guard", {})
    return "\n".join(
        [
            "# R241-16P-Retry Publish Implementation Report",
            "",
            "## 1. 修改文件清单",
            "- `backend/app/foundation/ci_publish_retry_git_identity.py`",
            "- `backend/app/foundation/test_ci_publish_retry_git_identity.py`",
            "- `migration_reports/foundation_audit/R241-16P_RETRY_PUBLISH_IMPLEMENTATION_RESULT.json`",
            "- `migration_reports/foundation_audit/R241-16P_RETRY_PUBLISH_IMPLEMENTATION_REPORT.md`",
            "",
            "## 2. PublishRetryStatus / GitIdentityScope / PublishRetryDecision / PublishRetryRiskLevel",
            "- Status: `identity_configured`, `identity_already_present`, `identity_configuration_failed`, `retry_published`, `retry_commit_failed`, `retry_push_failed`, `retry_precheck_failed`, `retry_remote_verification_failed`, `retry_blocked`, `unknown`",
            "- Identity scope: `repo_local`, `global_forbidden`, `already_configured`, `unknown`",
            "- Decision: `configure_identity_and_retry`, `retry_publish_only`, `block_retry`, `unknown`",
            "- Risk: `low`, `medium`, `high`, `critical`, `unknown`",
            "",
            "## 3. GitIdentityCheck 字段",
            "`check_id`, `name_present`, `email_present`, `current_name`, `current_email`, `scope`, `needs_configuration`, `allowed_to_configure`, `configured_this_round`, `warnings`, `errors`",
            "",
            "## 4. GitIdentityConfigurationResult 字段",
            "`command_results`, `configured_name`, `configured_email`, `scope`, `configuration_succeeded`, `global_config_modified`, `warnings`, `errors`",
            "",
            "## 5. PublishRetryResult 字段",
            "`retry_id`, `generated_at`, `status`, `decision`, `git_identity_check`, `identity_configuration_result`, `publish_result`, `validation_result`, `local_mutation_guard`, `existing_workflows_unchanged`, `warnings`, `errors`",
            "",
            "## 6. previous R241-16P failure summary",
            f"- previous exists: `{result.get('previous_publish_result', {}).get('exists')}`",
            f"- previous status: `{result.get('previous_publish_result', {}).get('payload', {}).get('result', {}).get('status')}`",
            "",
            "## 7. git identity check result",
            f"- name_present: `{identity.get('name_present')}`",
            f"- email_present: `{identity.get('email_present')}`",
            f"- scope: `{identity.get('scope')}`",
            f"- configured_this_round: `{identity.get('configured_this_round')}`",
            "",
            "## 8. repo-local identity configuration result",
            f"- configuration_succeeded: `{config.get('configuration_succeeded')}`",
            f"- global_config_modified: `{config.get('global_config_modified', False)}`",
            "",
            "## 9. identity validation result",
            f"- validation: `{result.get('validation_result')}`",
            "",
            "## 10. publish retry result",
            f"- retry status: `{result.get('status')}`",
            f"- publish status: `{publish.get('status')}`",
            "",
            "## 11. commit / push result",
            f"- commit_succeeded: `{publish.get('commit_succeeded')}`",
            f"- push_succeeded: `{publish.get('push_succeeded')}`",
            f"- commit_hash: `{publish.get('commit_hash')}`",
            "",
            "## 12. remote verification result",
            f"- remote exact path: `{remote.get('remote_workflow_exact_path_present')}`",
            f"- workflow_dispatch_only: `{remote.get('workflow_dispatch_only')}`",
            "",
            "## 13. local mutation guard result",
            f"- valid: `{guard.get('valid')}`",
            f"- existing_workflows_unchanged: `{guard.get('existing_workflows_unchanged')}`",
            f"- audit_jsonl_unchanged: `{guard.get('audit_jsonl_unchanged')}`",
            f"- runtime_action_queue_unchanged: `{guard.get('runtime_action_queue_unchanged')}`",
            "",
            "## 14. validation result",
            f"- valid: `{result.get('validation_result', {}).get('valid')}`",
            f"- errors: `{result.get('validation_result', {}).get('errors')}`",
            "",
            "## 15. 测试结果",
            "- See final assistant response for executed validation commands.",
            "",
            "## 16. 是否修改 global git config",
            f"- `{config.get('global_config_modified', False)}`",
            "## 17. 是否执行 git commit",
            f"- `{publish.get('commit_attempted')}`",
            "## 18. 是否执行 git push",
            f"- `{publish.get('push_attempted')}`",
            "## 19. 是否执行 gh workflow run",
            "- `false`",
            "## 20. 是否启用 PR/push/schedule trigger",
            f"- PR: `{not remote.get('no_pr_trigger') if remote else False}`",
            f"- push: `{not remote.get('no_push_trigger') if remote else False}`",
            f"- schedule: `{not remote.get('no_schedule_trigger') if remote else False}`",
            "## 21. 是否读取 secret",
            "- `false`",
            "## 22. 是否修改 existing workflows",
            f"- `{guard.get('existing_workflows_unchanged') is False}`",
            "## 23. 是否写 runtime / audit JSONL / action queue",
            f"- runtime/action queue changed: `{guard.get('runtime_action_queue_unchanged') is False}`",
            f"- audit JSONL changed: `{guard.get('audit_jsonl_unchanged') is False}`",
            "## 24. 是否执行 auto-fix",
            "- `false`",
            "## 25. 当前剩余断点",
            f"- errors: `{result.get('errors')}`",
            "## 26. 下一轮建议",
            "- If `retry_published`, proceed to R241-16Q Remote Visibility Verification / Plan-only Dispatch Retry.",
            "- If `retry_push_failed`, resolve git auth/permission/branch protection; do not force push.",
        ]
    )


def generate_publish_retry_report(result: dict | None = None, output_path: str | None = None) -> dict:
    if result is None:
        result = evaluate_publish_retry_with_identity_setup()
    output_dir = REPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = Path(output_path) if output_path else output_dir / "R241-16P_RETRY_PUBLISH_IMPLEMENTATION_RESULT.json"
    md_path = json_path.with_suffix(".md") if output_path else output_dir / "R241-16P_RETRY_PUBLISH_IMPLEMENTATION_REPORT.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_report(result), encoding="utf-8")
    return {
        "output_path": str(json_path),
        "report_path": str(md_path),
        "result": result,
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
    }

