"""ToolRuntime instrumentation contract.

User permission model: high autonomy, high delegation, fewer interruptions.
Normal operations should be automatic; risk control is provided by RootGuard,
backup, rollback, audit, and nightly review rather than frequent confirmation.

This module only creates policy/event projections. It does not execute tools,
enforce permissions, mutate executors, or write runtime state.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


RISK_LEVELS = {
    "level_0_free_readonly",
    "level_1_standard_auto",
    "level_2_protected_auto",
    "level_3_confirm_or_archive",
    "unknown",
}

OPERATION_TYPES = {
    "read_file",
    "list_files",
    "search",
    "static_analysis",
    "write_file",
    "edit_code",
    "create_file",
    "run_test",
    "run_build",
    "shell_command",
    "package_manager",
    "modify_config",
    "delete_file",
    "archive_file",
    "migrate_schema",
    "external_api_call",
    "mcp_tool_call",
    "claude_code_call",
    "sandbox_verify",
    "sandbox_rollback",
    "prompt_replace",
    "memory_cleanup",
    "asset_promotion",
    "asset_elimination",
    "unknown",
}

EXECUTION_STATUSES = {
    "planned",
    "started",
    "completed",
    "failed",
    "skipped",
    "blocked",
    "requires_confirmation",
    "rollback_available",
    "rollback_invoked",
    "unknown",
}

DEFAULT_SAMPLE_PATH = Path(
    r"E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit\R241-5A_TOOL_RUNTIME_SAMPLE.json"
)

LEVEL_0_OPERATIONS = {"read_file", "list_files", "search", "static_analysis"}
LEVEL_1_OPERATIONS = {
    "write_file",
    "edit_code",
    "create_file",
    "run_test",
    "run_build",
    "shell_command",
    "sandbox_verify",
    "archive_file",
    "sandbox_rollback",
    "claude_code_call",
    "mcp_tool_call",
}
LEVEL_2_OPERATIONS = {"modify_config", "package_manager", "asset_promotion"}
LEVEL_3_OPERATIONS = {
    "delete_file",
    "migrate_schema",
    "external_api_call",
    "prompt_replace",
    "memory_cleanup",
    "asset_elimination",
}

CONFIG_NAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
    "pytest.ini",
    "pyproject.toml",
    "jest.config.cjs",
}
PROTECTED_STATE_MARKERS = {
    "governance_state.json",
    "asset_registry.json",
    "memory.json",
    "qdrant",
    "sqlite",
    ".sqlite",
    ".db",
    "checkpoints.db",
}
PROMPT_MARKERS = {"prompt", "soul.md", "gepa", "dspy"}
ROOT_GUARD_MARKERS = {"root_guard.py", "root_guard.ps1"}
REGISTRY_MARKERS = {"tool_registry", "skill_registry", "workflow_registry", "registry.json"}


@dataclass(frozen=True)
class ToolPolicy:
    tool_id: str
    tool_type: str
    owner_system: str
    default_risk_level: str
    allowed_modes: List[str]
    denied_modes: List[str]
    requires_root_guard: bool
    requires_backup_for: List[str]
    supports_dry_run: bool
    supports_rollback: bool
    can_read_files: bool
    can_write_files: bool
    can_execute_shell: bool
    can_access_network: bool
    audit_required: bool
    warnings: List[str]


@dataclass(frozen=True)
class ToolExecutionEvent:
    tool_execution_id: str
    caller_system: str
    tool_id: str
    tool_type: str
    operation_type: str
    risk_level: str
    root_guard_required: bool
    status: str
    backup_refs: List[str]
    rollback_refs: List[str]
    modified_files: List[str]
    artifact_refs: List[str]
    truth_event_refs: List[str]
    state_event_refs: List[str]
    asset_candidate_refs: List[str]
    warnings: List[str]
    context_id: Optional[str] = None
    request_id: Optional[str] = None
    mode_session_id: Optional[str] = None
    mode_invocation_id: Optional[str] = None
    caller_mode: Optional[str] = None
    cwd: Optional[str] = None
    root_guard_passed: Optional[bool] = None
    success: Optional[bool] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass(frozen=True)
class ProtectedOperationDecision:
    operation_type: str
    risk_level: str
    auto_allowed: bool
    requires_backup: bool
    requires_rollback: bool
    requires_confirmation: bool
    should_archive_instead_of_delete: bool
    requires_root_guard: bool
    requires_nightly_review: bool
    required_followups: List[str]
    warnings: List[str]


def classify_tool_operation(
    operation_type: str,
    target_path: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Classify tool operation risk without executing anything."""
    metadata = dict(metadata or {})
    warnings: List[str] = []
    op = _normalize_operation(operation_type, warnings)
    path_text = str(target_path or metadata.get("target_path") or "").replace("\\", "/").lower()
    path_name = Path(path_text).name.lower() if path_text else ""

    risk_level = "unknown"
    reasons: List[str] = []

    if op in LEVEL_0_OPERATIONS:
        risk_level = "level_0_free_readonly"
        reasons.append("readonly_operation")
    elif op in LEVEL_1_OPERATIONS:
        risk_level = "level_1_standard_auto"
        reasons.append("standard_auto_operation")
    elif op in LEVEL_2_OPERATIONS:
        risk_level = "level_2_protected_auto"
        reasons.append("protected_operation")
    elif op in LEVEL_3_OPERATIONS:
        risk_level = "level_3_confirm_or_archive"
        reasons.append("confirm_or_archive_operation")
    else:
        warnings.append(f"unknown_operation_type:{operation_type}")

    if path_text:
        if "migration_reports/foundation_audit" in path_text and op in {"write_file", "create_file"}:
            risk_level = "level_1_standard_auto"
            reasons.append("foundation_audit_report_write")
        if path_name in CONFIG_NAMES or _contains_any(path_text, CONFIG_NAMES):
            if op == "delete_file":
                risk_level = "level_3_confirm_or_archive"
                reasons.append("delete_critical_config")
            elif op not in LEVEL_0_OPERATIONS:
                risk_level = "level_2_protected_auto"
                reasons.append("critical_config_path")
        if _contains_any(path_text, PROTECTED_STATE_MARKERS):
            if op in {"delete_file", "memory_cleanup", "migrate_schema"}:
                risk_level = "level_3_confirm_or_archive"
                reasons.append("destructive_runtime_state_operation")
            elif op not in LEVEL_0_OPERATIONS:
                risk_level = "level_2_protected_auto"
                reasons.append("protected_runtime_state_path")
        if _contains_any(path_text, ROOT_GUARD_MARKERS | REGISTRY_MARKERS):
            if op not in LEVEL_0_OPERATIONS:
                risk_level = "level_2_protected_auto"
                reasons.append("protected_registry_or_root_guard")
        if _contains_any(path_text, PROMPT_MARKERS) and op not in LEVEL_0_OPERATIONS:
            risk_level = "level_2_protected_auto"
            reasons.append("prompt_core_path")

    if op == "prompt_replace" and not _has_refs(metadata, "rollback_refs"):
        risk_level = "level_3_confirm_or_archive"
        reasons.append("prompt_replace_without_rollback")
    if op == "external_api_call" and metadata.get("irreversible"):
        risk_level = "level_3_confirm_or_archive"
        reasons.append("irreversible_external_side_effect")
    if op == "asset_elimination" and str(metadata.get("asset_tier", "")).lower() in {"core", "premium"}:
        risk_level = "level_3_confirm_or_archive"
        reasons.append("premium_or_core_asset_elimination")
    if op == "memory_cleanup":
        risk_level = "level_3_confirm_or_archive"
        reasons.append("memory_cleanup_requires_quarantine")

    return {
        "operation_type": op,
        "target_path": target_path,
        "risk_level": risk_level,
        "reasons": _dedupe(reasons),
        "warnings": _dedupe(warnings),
    }


def decide_protected_operation(
    operation_type: str,
    target_path: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return projected protection requirements; does not enforce anything."""
    metadata = dict(metadata or {})
    classification = classify_tool_operation(operation_type, target_path, metadata)
    op = classification["operation_type"]
    risk_level = classification["risk_level"]
    warnings = list(classification.get("warnings") or [])
    followups: List[str] = []

    requires_backup = False
    requires_rollback = False
    requires_confirmation = False
    should_archive = False
    requires_root_guard = False
    requires_nightly = False
    auto_allowed = False

    if risk_level == "level_0_free_readonly":
        auto_allowed = True
    elif risk_level == "level_1_standard_auto":
        auto_allowed = True
        requires_root_guard = op not in LEVEL_0_OPERATIONS
    elif risk_level == "level_2_protected_auto":
        auto_allowed = True
        requires_backup = True
        requires_rollback = True
        requires_root_guard = True
        requires_nightly = True
        followups.extend(["backup_required", "rollback_ref_required", "audit_required"])
    elif risk_level == "level_3_confirm_or_archive":
        should_archive = op == "delete_file" or metadata.get("archive_strategy") is True
        requires_backup = True
        requires_rollback = True
        requires_root_guard = True
        requires_nightly = True
        confirmation_or_archive = metadata.get("confirmation_provided") is True or metadata.get("archive_strategy") is True
        auto_allowed = bool(confirmation_or_archive)
        requires_confirmation = not confirmation_or_archive
        followups.extend(["confirmation_or_archive_required", "backup_required", "rollback_ref_required"])
    else:
        warnings.append(f"unknown_risk_level:{risk_level}")
        requires_confirmation = True
        followups.append("manual_review_required")

    if op == "prompt_replace":
        requires_backup = True
        requires_rollback = True
        followups.append("prompt_rollback_required")
    if op == "memory_cleanup":
        followups.append("quarantine_or_observation_required")
        warnings.append("memory_cleanup_requires_quarantine")
    if op == "asset_elimination" and str(metadata.get("asset_tier", "")).lower() in {"core", "premium"}:
        requires_confirmation = True
        auto_allowed = False
        followups.append("premium_or_core_asset_elimination_requires_user_confirmation")
        warnings.append("premium_or_core_auto_elimination_forbidden")
    if op == "delete_file":
        should_archive = True
        warnings.append("delete_should_archive")

    return asdict(
        ProtectedOperationDecision(
            operation_type=op,
            risk_level=risk_level,
            auto_allowed=auto_allowed,
            requires_backup=requires_backup,
            requires_rollback=requires_rollback,
            requires_confirmation=requires_confirmation,
            should_archive_instead_of_delete=should_archive,
            requires_root_guard=requires_root_guard,
            requires_nightly_review=requires_nightly,
            required_followups=_dedupe(followups),
            warnings=_dedupe(warnings),
        )
    )


def create_tool_policy(
    tool_id: str,
    tool_type: str,
    owner_system: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    normalized_type = str(tool_type or "unknown").lower()
    warnings: List[str] = []

    default_risk = "level_1_standard_auto"
    requires_root_guard = normalized_type in {"shell", "python", "file_system", "claude_code", "opencli"}
    supports_dry_run = bool(metadata.get("supports_dry_run"))
    supports_rollback = bool(metadata.get("supports_rollback") or metadata.get("rollback_script_exists"))
    can_read = normalized_type in {"shell", "python", "file_system", "mcp", "claude_code", "opencli", "sandbox", "browser", "search", "unknown"}
    can_write = normalized_type in {"shell", "python", "file_system", "claude_code", "opencli", "sandbox"}
    can_shell = normalized_type in {"shell", "python", "claude_code", "opencli", "sandbox"}
    can_network = normalized_type in {"mcp", "feishu", "browser", "search", "external_api"}

    if normalized_type in {"search", "browser"} and metadata.get("readonly", True):
        default_risk = "level_0_free_readonly"
        can_write = False
        can_shell = False
    elif normalized_type == "sandbox":
        default_risk = "level_1_standard_auto"
        supports_rollback = bool(supports_rollback or metadata.get("rollback_refs"))
        requires_root_guard = True
    elif normalized_type == "mcp":
        capabilities = metadata.get("capabilities") or []
        can_write = "write" in capabilities or bool(metadata.get("can_write_files"))
        can_network = True
        default_risk = "level_1_standard_auto" if can_write else "level_0_free_readonly"
    elif normalized_type not in {
        "shell",
        "python",
        "file_system",
        "mcp",
        "claude_code",
        "opencli",
        "sandbox",
        "feishu",
        "browser",
        "search",
        "unknown",
    }:
        normalized_type = "unknown"
        default_risk = "unknown"
        warnings.append(f"unknown_tool_type:{tool_type}")

    return asdict(
        ToolPolicy(
            tool_id=tool_id,
            tool_type=normalized_type,
            owner_system=owner_system,
            default_risk_level=default_risk,
            allowed_modes=list(metadata.get("allowed_modes") or []),
            denied_modes=list(metadata.get("denied_modes") or []),
            requires_root_guard=requires_root_guard,
            requires_backup_for=["level_2_protected_auto", "level_3_confirm_or_archive"],
            supports_dry_run=supports_dry_run,
            supports_rollback=supports_rollback,
            can_read_files=can_read,
            can_write_files=can_write,
            can_execute_shell=can_shell,
            can_access_network=can_network,
            audit_required=default_risk != "level_0_free_readonly",
            warnings=_dedupe(warnings),
        )
    )


def create_tool_execution_event(
    tool_id: str,
    operation_type: str,
    caller_system: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    tool_type = str(metadata.get("tool_type") or "unknown")
    target_path = metadata.get("target_path")
    decision = decide_protected_operation(operation_type, target_path, metadata)
    warnings = list(decision.get("warnings") or [])
    event = ToolExecutionEvent(
        tool_execution_id=f"toolexec_{uuid4().hex}",
        context_id=metadata.get("context_id"),
        request_id=metadata.get("request_id"),
        mode_session_id=metadata.get("mode_session_id"),
        mode_invocation_id=metadata.get("mode_invocation_id"),
        caller_mode=metadata.get("caller_mode"),
        caller_system=caller_system,
        tool_id=tool_id,
        tool_type=tool_type,
        operation_type=decision["operation_type"],
        risk_level=decision["risk_level"],
        cwd=metadata.get("cwd"),
        root_guard_required=bool(decision["requires_root_guard"]),
        root_guard_passed=metadata.get("root_guard_passed"),
        status="planned",
        success=None,
        backup_refs=list(metadata.get("backup_refs") or []),
        rollback_refs=list(metadata.get("rollback_refs") or []),
        modified_files=list(metadata.get("modified_files") or []),
        artifact_refs=list(metadata.get("artifact_refs") or []),
        truth_event_refs=list(metadata.get("truth_event_refs") or []),
        state_event_refs=list(metadata.get("state_event_refs") or []),
        asset_candidate_refs=list(metadata.get("asset_candidate_refs") or []),
        warnings=_dedupe(warnings),
        started_at=metadata.get("started_at"),
        finished_at=metadata.get("finished_at"),
    )
    result = asdict(event)
    result["policy_decision"] = decision
    result["confirmation_provided"] = bool(metadata.get("confirmation_provided"))
    result["archive_strategy"] = bool(metadata.get("archive_strategy"))
    result["target_path"] = target_path
    return result


def complete_tool_execution_event(
    event: Dict[str, Any],
    success: bool,
    artifact_refs: Optional[List[str]] = None,
    modified_files: Optional[List[str]] = None,
    rollback_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    updated = dict(event)
    updated["success"] = bool(success)
    updated["status"] = "completed" if success else "failed"
    updated["finished_at"] = _now()
    updated["artifact_refs"] = _dedupe(list(updated.get("artifact_refs") or []) + list(artifact_refs or []))
    updated["modified_files"] = _dedupe(list(updated.get("modified_files") or []) + list(modified_files or []))
    updated["rollback_refs"] = _dedupe(list(updated.get("rollback_refs") or []) + list(rollback_refs or []))
    return updated


def validate_tool_event_policy(event: Dict[str, Any]) -> Dict[str, Any]:
    warnings = list(event.get("warnings") or [])
    followups: List[str] = []
    risk = event.get("risk_level", "unknown")
    op = event.get("operation_type", "unknown")

    if op == "unknown":
        warnings.append("unknown_operation_type")
        followups.append("manual_operation_classification_required")
    if event.get("root_guard_required") and event.get("root_guard_passed") is not True:
        warnings.append("root_guard_required_but_missing")
        followups.append("run_root_guard_before_execution")
    if risk == "level_2_protected_auto":
        if not event.get("backup_refs"):
            warnings.append("level_2_missing_backup")
            followups.append("create_backup_ref")
        if not event.get("rollback_refs"):
            warnings.append("level_2_missing_rollback")
            followups.append("create_rollback_ref")
    if risk == "level_3_confirm_or_archive":
        if not event.get("confirmation_provided") and not event.get("archive_strategy"):
            warnings.append("level_3_requires_confirmation")
            followups.append("obtain_confirmation_or_archive_strategy")
    if op == "delete_file":
        warnings.append("delete_should_archive")
        followups.append("archive_instead_of_delete")
    if op == "prompt_replace" and not event.get("rollback_refs"):
        warnings.append("prompt_replace_missing_rollback")
        followups.append("provide_prompt_rollback_ref")
    if op == "memory_cleanup":
        warnings.append("memory_cleanup_requires_quarantine")
        followups.append("quarantine_or_observation_before_cleanup")
    if op == "asset_elimination" and event.get("risk_level") == "level_3_confirm_or_archive":
        warnings.append("asset_core_elimination_forbidden")
        followups.append("require_user_confirmation_and_nightly_review")
    if op == "external_api_call" and event.get("risk_level") == "level_3_confirm_or_archive":
        warnings.append("external_side_effect_requires_confirmation")
        followups.append("confirm_external_side_effect")

    warnings = _dedupe(warnings)
    followups = _dedupe(followups)
    blocking = {
        "root_guard_required_but_missing",
        "level_2_missing_backup",
        "level_2_missing_rollback",
        "level_3_requires_confirmation",
        "prompt_replace_missing_rollback",
        "memory_cleanup_requires_quarantine",
        "asset_core_elimination_forbidden",
        "external_side_effect_requires_confirmation",
        "unknown_operation_type",
    }
    return {
        "policy_ok": not any(warning in blocking for warning in warnings),
        "warnings": warnings,
        "required_followups": followups,
    }


def summarize_tool_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_tool_id = Counter(str(event.get("tool_id", "unknown")) for event in events)
    by_tool_type = Counter(str(event.get("tool_type", "unknown")) for event in events)
    by_operation = Counter(str(event.get("operation_type", "unknown")) for event in events)
    by_risk = Counter(str(event.get("risk_level", "unknown")) for event in events)
    by_status = Counter(str(event.get("status", "unknown")) for event in events)
    warnings: List[str] = []
    for event in events:
        warnings.extend(event.get("warnings") or [])
    return {
        "total": len(events),
        "by_tool_id": dict(by_tool_id),
        "by_tool_type": dict(by_tool_type),
        "by_operation_type": dict(by_operation),
        "by_risk_level": dict(by_risk),
        "by_status": dict(by_status),
        "high_risk_count": by_risk.get("level_2_protected_auto", 0) + by_risk.get("level_3_confirm_or_archive", 0),
        "missing_backup_count": sum(1 for event in events if event.get("risk_level") == "level_2_protected_auto" and not event.get("backup_refs")),
        "missing_rollback_count": sum(1 for event in events if event.get("risk_level") == "level_2_protected_auto" and not event.get("rollback_refs")),
        "root_guard_required_count": sum(1 for event in events if event.get("root_guard_required")),
        "warnings": dict(Counter(warnings)),
    }


def generate_tool_runtime_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate report-directory sample events without executing tools."""
    events = [
        create_tool_execution_event("fs.read", "read_file", "sample", {"tool_type": "file_system", "target_path": "README.md"}),
        create_tool_execution_event("fs.edit", "edit_code", "sample", {"tool_type": "file_system", "target_path": "backend/app/foo.py", "root_guard_passed": True}),
        create_tool_execution_event(
            "fs.config",
            "modify_config",
            "sample",
            {
                "tool_type": "file_system",
                "target_path": "package.json",
                "backup_refs": ["backup/package.json.bak"],
                "rollback_refs": ["rollback/package-json.patch"],
                "root_guard_passed": True,
            },
        ),
        create_tool_execution_event("fs.delete", "delete_file", "sample", {"tool_type": "file_system", "target_path": "important.md"}),
        create_tool_execution_event("prompt.replace", "prompt_replace", "sample", {"tool_type": "file_system", "target_path": "prompts/SOUL.md"}),
        create_tool_execution_event("memory.cleanup", "memory_cleanup", "sample", {"tool_type": "python", "target_path": "backend/.deer-flow/.openclaw/memory.json"}),
        create_tool_execution_event(
            "claude.code",
            "claude_code_call",
            "sample",
            {"tool_type": "claude_code", "mode_invocation_id": "modeinv_sample", "root_guard_passed": True},
        ),
        create_tool_execution_event(
            "sandbox.verify",
            "sandbox_verify",
            "sample",
            {"tool_type": "sandbox", "rollback_refs": ["rollback/sample.ps1"], "root_guard_passed": True},
        ),
    ]
    validations = [validate_tool_event_policy(event) for event in events]
    result = {
        "events": events,
        "validations": validations,
        "summary": summarize_tool_events(events),
        "generated_at": _now(),
        "notes": [
            "sample_only_no_tool_execution",
            "high_autonomy_controlled_by_backup_rollback_audit_review",
        ],
    }
    path = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(path), **result}


def _normalize_operation(operation_type: str, warnings: List[str]) -> str:
    normalized = str(operation_type or "unknown").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in OPERATION_TYPES:
        return normalized
    warnings.append(f"unknown_operation_type:{operation_type}")
    return "unknown"


def _contains_any(text: str, markers: set[str]) -> bool:
    return any(marker.lower() in text for marker in markers)


def _has_refs(metadata: Dict[str, Any], key: str) -> bool:
    value = metadata.get(key)
    return bool(value) if isinstance(value, list) else bool(value)


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
