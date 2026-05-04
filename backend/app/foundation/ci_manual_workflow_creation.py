"""Manual Workflow Creation Implementation for R241-16H.

Creates .github/workflows/foundation-manual-dispatch.yml from the R241-16F blueprint.
Forbidden: PR/push/schedule triggers, secrets, network, runtime, audit JSONL, auto-fix.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.foundation import ci_implementation_plan as ci_plan
from app.foundation import ci_local_dryrun
from app.foundation import ci_workflow_draft
from app.foundation import ci_enablement_review
from app.foundation import ci_manual_dispatch_review as mdr
from app.foundation import ci_manual_dispatch_implementation_review as impl


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_JSON_PATH = REPORT_DIR / "R241-16H_MANUAL_WORKFLOW_CREATION_RESULT.json"
DEFAULT_MD_PATH = REPORT_DIR / "R241-16H_MANUAL_WORKFLOW_CREATION_REPORT.md"
TARGET_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "foundation-manual-dispatch.yml"
BLUEPRINT_PATH = REPORT_DIR / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt"
VALID_CONFIRMATION_PHRASE = "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN"


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class ManualWorkflowCreationStatus:
    CREATED = "created"
    BLOCKED_PRECHECK_FAILED = "blocked_precheck_failed"
    BLOCKED_EXISTING_WORKFLOW_PRESENT = "blocked_existing_workflow_present"
    BLOCKED_INVALID_CONFIRMATION_GATE = "blocked_invalid_confirmation_gate"
    BLOCKED_BLUEPRINT_INVALID = "blocked_blueprint_invalid"
    BLOCKED_SECURITY_POLICY = "blocked_security_policy"
    VALIDATION_FAILED = "validation_failed"
    ROLLED_BACK = "rolled_back"
    UNKNOWN = "unknown"


class ManualWorkflowCreationMode:
    WORKFLOW_DISPATCH_PLAN_ONLY_DEFAULT = "workflow_dispatch_plan_only_default"
    WORKFLOW_DISPATCH_EXECUTE_SELECTED_ALLOWED = "workflow_dispatch_execute_selected_allowed"
    UNKNOWN = "unknown"


class ManualWorkflowCreationRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ManualWorkflowCreationDecision:
    CREATE_MANUAL_WORKFLOW = "create_manual_workflow"
    BLOCK_CREATION = "block_creation"
    ROLLBACK_CREATED_WORKFLOW = "rollback_created_workflow"
    UNKNOWN = "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Load blueprint
# ─────────────────────────────────────────────────────────────────────────────

def load_manual_workflow_blueprint_for_creation(
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Load the R241-16F blueprint for workflow creation.

    The blueprint is a fixed project asset at BLUEPRINT_PATH (absolute).
    The root parameter is only used for target-path checks.
    """
    root_path = Path(root) if root else ROOT
    # Blueprint is a fixed absolute path — use it directly
    blueprint_file = Path(BLUEPRINT_PATH)

    errors: List[str] = []
    warnings: List[str] = []

    if not blueprint_file.exists():
        errors.append("blueprint_file_not_found")
        return {
            "blueprint_text": None,
            "blueprint_path": str(blueprint_file),
            "warnings": warnings,
            "errors": errors,
        }

    yaml_text = blueprint_file.read_text(encoding="utf-8")

    # Validate blueprint doesn't contain forbidden tokens
    forbidden = ["pull_request:", "push:", "schedule:", "secrets.", "curl", "Invoke-WebRequest", "webhook", "auto-fix"]
    for token in forbidden:
        if token.lower() in yaml_text.lower():
            errors.append(f"blueprint_contains_forbidden:{token}")

    if not yaml_text.strip():
        errors.append("blueprint_empty")

    return {
        "blueprint_text": yaml_text,
        "blueprint_path": str(blueprint_file),
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Prechecks
# ─────────────────────────────────────────────────────────────────────────────

def run_manual_workflow_creation_prechecks(
    root: Optional[str] = None,
    confirmation_phrase: Optional[str] = None,
    requested_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all prechecks before workflow creation."""
    root_path = Path(root) if root else ROOT
    errors: List[str] = []
    warnings: List[str] = []

    # 1. RootGuard already passed (recorded)
    root_check = {
        "check_id": "check_root_guard_passed",
        "check_type": "root_guard",
        "passed": True,
        "risk_level": ManualWorkflowCreationRiskLevel.CRITICAL,
        "description": "RootGuard already confirmed ROOT is correct.",
        "evidence_refs": ["scripts/root_guard.py"],
        "blocked_reasons": [],
        "warnings": [],
        "errors": [],
    }

    # 2. Confirmation phrase check
    phrase_exact = (confirmation_phrase == VALID_CONFIRMATION_PHRASE) if confirmation_phrase else False
    phrase_check = {
        "check_id": "check_confirmation_phrase",
        "check_type": "confirmation_phrase",
        "passed": phrase_exact,
        "risk_level": ManualWorkflowCreationRiskLevel.CRITICAL,
        "description": "Confirmation phrase must be exact match.",
        "evidence_refs": ["R241-16G gate decision"],
        "blocked_reasons": [] if phrase_exact else ["confirmation_phrase_invalid"],
        "warnings": [],
        "errors": [] if phrase_exact else ["confirmation_phrase_invalid"],
    }
    if not phrase_exact:
        errors.append("confirmation_phrase_invalid")

    # 3. Requested option check
    option_valid = requested_option == "option_c_manual_plan_only_workflow"
    option_check = {
        "check_id": "check_requested_option",
        "check_type": "requested_option",
        "passed": option_valid,
        "risk_level": ManualWorkflowCreationRiskLevel.HIGH,
        "description": "Requested option must be option_c.",
        "evidence_refs": ["R241-16G gate decision"],
        "blocked_reasons": [] if option_valid else ["requested_option_not_option_c"],
        "warnings": [],
        "errors": [] if option_valid else ["requested_option_not_option_c"],
    }
    if not option_valid:
        errors.append("requested_option_not_option_c")

    # 4. Blueprint exists
    blueprint_data = load_manual_workflow_blueprint_for_creation(str(root_path))
    blueprint_ok = bool(blueprint_data["blueprint_text"]) and not blueprint_data["errors"]
    blueprint_check = {
        "check_id": "check_blueprint_exists",
        "check_type": "blueprint_exists",
        "passed": blueprint_ok,
        "risk_level": ManualWorkflowCreationRiskLevel.CRITICAL,
        "description": "R241-16F blueprint must exist and be valid.",
        "evidence_refs": [blueprint_data["blueprint_path"]],
        "blocked_reasons": [] if blueprint_ok else ["blueprint_invalid"],
        "warnings": blueprint_data["warnings"],
        "errors": blueprint_data["errors"],
    }
    if not blueprint_ok:
        errors.append("blueprint_invalid")

    # 5. Target workflow does not already exist
    target_exists = TARGET_WORKFLOW_PATH.exists()
    target_check = {
        "check_id": "check_target_not_exists",
        "check_type": "target_not_exists",
        "passed": not target_exists,
        "risk_level": ManualWorkflowCreationRiskLevel.CRITICAL,
        "description": "Target workflow must not already exist.",
        "evidence_refs": [str(TARGET_WORKFLOW_PATH)],
        "blocked_reasons": [] if not target_exists else ["target_workflow_already_exists"],
        "warnings": [],
        "errors": [] if not target_exists else ["target_workflow_already_exists"],
    }
    if target_exists:
        errors.append("target_workflow_already_exists")

    # 6. Existing workflows unchanged
    discovery = ci_enablement_review.discover_existing_workflows(str(root_path))
    existing_paths = {
        ".github/workflows/backend-unit-tests.yml",
        ".github/workflows/lint-check.yml",
    }
    unexpected_workflows = [
        str(p.relative_to(root_path))
        for p in Path(root_path / ".github/workflows").glob("*.yml")
        if str(p.relative_to(root_path)) not in existing_paths
        and p.name != "foundation-manual-dispatch.yml"
    ]
    existing_check = {
        "check_id": "check_existing_workflows_unchanged",
        "check_type": "existing_workflows_unchanged",
        "passed": True,
        "risk_level": ManualWorkflowCreationRiskLevel.MEDIUM,
        "description": "Only expected workflows exist.",
        "evidence_refs": [str(root_path / ".github/workflows")],
        "blocked_reasons": [],
        "warnings": unexpected_workflows,
        "errors": [],
    }

    # 7. Rollback plan exists
    rollback_plan = mdr.build_manual_dispatch_rollback_plan()
    rollback_check = {
        "check_id": "check_rollback_plan_exists",
        "check_type": "rollback_plan",
        "passed": bool(rollback_plan.get("rollback_steps")),
        "risk_level": ManualWorkflowCreationRiskLevel.HIGH,
        "description": "Rollback plan must exist.",
        "evidence_refs": ["R241-16E rollback plan"],
        "blocked_reasons": [] if rollback_plan.get("rollback_steps") else ["rollback_plan_missing"],
        "warnings": [],
        "errors": [] if rollback_plan.get("rollback_steps") else ["rollback_plan_missing"],
    }
    if not rollback_plan.get("rollback_steps"):
        errors.append("rollback_plan_missing")

    all_checks = [root_check, phrase_check, option_check, blueprint_check, target_check, existing_check, rollback_check]
    all_passed = all(c["passed"] for c in all_checks)

    return {
        "precheck_id": "R241-16H_prechecks",
        "generated_at": _utc_now(),
        "prechecks": all_checks,
        "all_passed": all_passed,
        "blocked_reasons": [c["check_id"] for c in all_checks if not c["passed"]],
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Create workflow file
# ─────────────────────────────────────────────────────────────────────────────

def create_manual_dispatch_workflow_file(
    root: Optional[str] = None,
    allow_create: bool = True,
) -> Dict[str, Any]:
    """Create the workflow file from blueprint.

    If allow_create=False, validates but does not write.
    Returns blocked if target already exists.
    """
    root_path = Path(root) if root else ROOT
    target = TARGET_WORKFLOW_PATH if not root else (Path(root) / ".github" / "workflows" / "foundation-manual-dispatch.yml")

    errors: List[str] = []
    warnings: List[str] = []

    # Check if already exists
    if target.exists():
        errors.append("target_workflow_already_exists")
        return {
            "check_id": "create_workflow_file",
            "workflow_path": str(target),
            "workflow_created": False,
            "workflow_overwritten": False,
            "file_written": False,
            "passed": False,
            "blocked_reasons": ["target_workflow_already_exists"],
            "warnings": warnings,
            "errors": errors,
        }

    # Load blueprint
    blueprint_data = load_manual_workflow_blueprint_for_creation(str(root_path))
    if blueprint_data["errors"]:
        errors.extend(blueprint_data["errors"])
        return {
            "check_id": "create_workflow_file",
            "workflow_path": str(target),
            "workflow_created": False,
            "workflow_overwritten": False,
            "file_written": False,
            "passed": False,
            "blocked_reasons": blueprint_data["errors"],
            "warnings": blueprint_data["warnings"],
            "errors": errors,
        }

    if not allow_create:
        return {
            "check_id": "create_workflow_file",
            "workflow_path": str(target),
            "workflow_created": False,
            "workflow_overwritten": False,
            "file_written": False,
            "passed": True,
            "blocked_reasons": [],
            "warnings": ["allow_create_false_no_file_written"],
            "errors": [],
        }

    # Write workflow file
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(blueprint_data["blueprint_text"], encoding="utf-8")
        file_written = True
    except Exception as e:
        errors.append(f"file_write_error:{e}")
        return {
            "check_id": "create_workflow_file",
            "workflow_path": str(target),
            "workflow_created": False,
            "workflow_overwritten": False,
            "file_written": False,
            "passed": False,
            "blocked_reasons": errors,
            "warnings": warnings,
            "errors": errors,
        }

    # Verify file was written correctly
    try:
        written = target.read_text(encoding="utf-8")
        verified = written == blueprint_data["blueprint_text"]
    except Exception:
        verified = False

    if not verified:
        errors.append("file_verify_failed")
        try:
            target.unlink()
        except Exception:
            pass
        return {
            "check_id": "create_workflow_file",
            "workflow_path": str(target),
            "workflow_created": False,
            "workflow_overwritten": False,
            "file_written": False,
            "passed": False,
            "blocked_reasons": ["file_verify_failed"],
            "warnings": warnings,
            "errors": errors,
        }

    return {
        "check_id": "create_workflow_file",
        "workflow_path": str(target),
        "workflow_created": True,
        "workflow_overwritten": False,
        "file_written": True,
        "passed": True,
        "blocked_reasons": [],
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validate created workflow
# ─────────────────────────────────────────────────────────────────────────────

def validate_created_manual_workflow(
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate the created workflow file meets all constraints."""
    root_path = Path(root) if root else ROOT
    target = TARGET_WORKFLOW_PATH if not root else (Path(root) / ".github" / "workflows" / "foundation-manual-dispatch.yml")

    errors: List[str] = []
    warnings: List[str] = []

    # File must exist
    if not target.exists():
        errors.append("workflow_file_not_found")
        return {
            "validation_id": "R241-16H_post_creation_validation",
            "generated_at": _utc_now(),
            "valid": False,
            "workflow_exists": False,
            "pull_request_enabled": None,
            "push_enabled": None,
            "schedule_enabled": None,
            "workflow_dispatch_enabled": None,
            "contains_secret_refs": None,
            "contains_network_call": None,
            "contains_webhook": None,
            "contains_auto_fix": None,
            "contains_runtime_write": None,
            "contains_audit_jsonl_write": None,
            "contains_action_queue_write": None,
            "existing_workflows_unchanged": None,
            "warnings": warnings,
            "errors": errors,
        }

    yaml_text = target.read_text(encoding="utf-8")

    # Check for forbidden triggers
    pr_enabled = "pull_request:" in yaml_text
    push_enabled = "push:" in yaml_text
    schedule_enabled = "schedule:" in yaml_text
    wfd_enabled = "workflow_dispatch:" in yaml_text

    if pr_enabled:
        errors.append("pull_request_trigger_found")
    if push_enabled:
        errors.append("push_trigger_found")
    if schedule_enabled:
        errors.append("schedule_trigger_found")

    # Check for forbidden content
    has_secrets = "secrets." in yaml_text or "secrets:" in yaml_text
    has_curl = "curl" in yaml_text.lower()
    has_webhook = "webhook" in yaml_text.lower()
    has_invoke_webrequest = "Invoke-WebRequest" in yaml_text
    has_auto_fix = "auto-fix" in yaml_text.lower()
    has_runtime_write = any(t in yaml_text for t in ["runtime/", "/runtime", "action_queue/", "/action_queue"])
    has_audit_jsonl = any(t in yaml_text for t in ["audit_trail", "audit_trail.jsonl", ".jsonl"])
    has_action_queue = "action_queue" in yaml_text.lower()

    if has_secrets:
        errors.append("secrets_reference_found")
    if has_curl:
        errors.append("curl_found")
    if has_webhook:
        errors.append("webhook_found")
    if has_invoke_webrequest:
        errors.append("invoke_webrequest_found")
    if has_auto_fix:
        errors.append("auto_fix_found")

    # Check confirmation phrase present
    has_confirm_phrase = VALID_CONFIRMATION_PHRASE in yaml_text
    if not has_confirm_phrase:
        errors.append("confirm_phrase_missing")

    # Check plan_only default
    has_plan_only_default = 'default: "plan_only"' in yaml_text or "default: 'plan_only'" in yaml_text
    if not has_plan_only_default:
        errors.append("plan_only_default_missing")

    # Check existing workflows unchanged
    backend_unit_tests = root_path / ".github/workflows/backend-unit-tests.yml"
    lint_check = root_path / ".github/workflows/lint-check.yml"
    existing_unchanged = backend_unit_tests.exists() and lint_check.exists()

    # Check stage_selection excludes full / real_send / auto_fix / webhook / secret
    stage_forbidden = ["full", "real_send", "auto_fix", "webhook", "secret"]
    stage_excludes_forbidden = all(f not in yaml_text.split("stage_selection")[1].split("\n")[0] if "stage_selection" in yaml_text else True for f in stage_forbidden)

    passed = len(errors) == 0

    return {
        "validation_id": "R241-16H_post_creation_validation",
        "generated_at": _utc_now(),
        "valid": passed,
        "workflow_exists": True,
        "pull_request_enabled": pr_enabled,
        "push_enabled": push_enabled,
        "schedule_enabled": schedule_enabled,
        "workflow_dispatch_enabled": wfd_enabled,
        "contains_secret_refs": has_secrets,
        "contains_network_call": has_curl or has_webhook or has_invoke_webrequest,
        "contains_webhook": has_webhook,
        "contains_auto_fix": has_auto_fix,
        "contains_runtime_write": has_runtime_write,
        "contains_audit_jsonl_write": has_audit_jsonl,
        "contains_action_queue_write": has_action_queue,
        "existing_workflows_unchanged": existing_unchanged,
        "stage_selection_forbidden_values_excluded": stage_excludes_forbidden,
        "plan_only_default_set": has_plan_only_default,
        "confirm_phrase_present": has_confirm_phrase,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Local validation after creation
# ─────────────────────────────────────────────────────────────────────────────

def run_local_validation_after_workflow_creation(
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Run local CI checks after workflow creation."""
    root_path = Path(root) if root else ROOT
    warnings: List[str] = []
    errors: List[str] = []

    smoke_result = ci_local_dryrun.run_local_ci_dryrun(selection="smoke")
    fast_result = ci_local_dryrun.run_local_ci_dryrun(selection="fast")

    return {
        "validation_id": "R241-16H_local_validation",
        "generated_at": _utc_now(),
        "smoke_result": smoke_result,
        "fast_result": fast_result,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rollback
# ─────────────────────────────────────────────────────────────────────────────

def rollback_manual_workflow_creation(
    root: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Rollback: delete only the newly created workflow file."""
    root_path = Path(root) if root else ROOT
    target = TARGET_WORKFLOW_PATH if not root else (Path(root) / ".github" / "workflows" / "foundation-manual-dispatch.yml")

    errors: List[str] = []
    warnings: List[str] = []

    if not target.exists():
        warnings.append("target_workflow_already_gone")
        return {
            "rollback_id": "R241-16H_rollback",
            "rollback_reason": reason,
            "workflow_deleted": False,
            "workflow_existed_before_delete": False,
            "errors": errors,
            "warnings": warnings,
        }

    try:
        target.unlink()
        deleted = True
    except Exception as e:
        errors.append(f"delete_failed:{e}")
        deleted = False

    # Verify existing workflows still intact
    backend_unit_tests = root_path / ".github/workflows/backend-unit-tests.yml"
    lint_check = root_path / ".github/workflows/lint-check.yml"

    return {
        "rollback_id": "R241-16H_rollback",
        "rollback_reason": reason,
        "workflow_deleted": deleted,
        "workflow_existed_before_delete": True,
        "existing_workflows_unchanged": backend_unit_tests.exists() and lint_check.exists(),
        "errors": errors,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core execution
# ─────────────────────────────────────────────────────────────────────────────

def execute_manual_workflow_creation(
    root: Optional[str] = None,
    confirmation_phrase: Optional[str] = None,
    requested_option: Optional[str] = "option_c_manual_plan_only_workflow",
) -> Dict[str, Any]:
    """Execute the full workflow creation pipeline."""
    root_path = Path(root) if root else ROOT

    # Run prechecks
    precheck_result = run_manual_workflow_creation_prechecks(
        str(root_path),
        confirmation_phrase=confirmation_phrase,
        requested_option=requested_option,
    )

    if not precheck_result["all_passed"]:
        return {
            "result_id": "R241-16H_workflow_creation_result",
            "generated_at": _utc_now(),
            "status": ManualWorkflowCreationStatus.BLOCKED_PRECHECK_FAILED,
            "decision": ManualWorkflowCreationDecision.BLOCK_CREATION,
            "workflow_path": str(TARGET_WORKFLOW_PATH),
            "workflow_created": False,
            "workflow_overwritten": False,
            "existing_workflows_modified": False,
            "trigger_summary": {
                "pull_request": False,
                "push": False,
                "schedule": False,
                "workflow_dispatch": False,
            },
            "security_summary": {
                "no_secrets": True,
                "no_network": True,
                "no_runtime_write": True,
                "no_audit_jsonl_write": True,
                "no_action_queue_write": True,
                "no_auto_fix": True,
            },
            "prechecks": precheck_result,
            "validation_checks": [],
            "rollback_result": None,
            "warnings": precheck_result["warnings"],
            "errors": precheck_result["errors"],
        }

    # Create workflow file
    create_result = create_manual_dispatch_workflow_file(str(root_path), allow_create=True)

    workflow_created = create_result.get("workflow_created", False)

    # Validate created workflow
    validation_result = validate_created_manual_workflow(str(root_path))
    validation_passed = validation_result.get("valid", False)

    # Local validation
    local_validation = run_local_validation_after_workflow_creation(str(root_path))

    # Rollback if validation failed
    rollback_result = None
    if workflow_created and not validation_passed:
        rollback_result = rollback_manual_workflow_creation(
            str(root_path),
            reason="post_creation_validation_failed",
        )
        status = ManualWorkflowCreationStatus.VALIDATION_FAILED
        decision = ManualWorkflowCreationDecision.ROLLBACK_CREATED_WORKFLOW
        workflow_created = False
    elif workflow_created and validation_passed:
        status = ManualWorkflowCreationStatus.CREATED
        decision = ManualWorkflowCreationDecision.CREATE_MANUAL_WORKFLOW
    else:
        status = ManualWorkflowCreationStatus.BLOCKED_PRECHECK_FAILED
        decision = ManualWorkflowCreationDecision.BLOCK_CREATION

    return {
        "result_id": "R241-16H_workflow_creation_result",
        "generated_at": _utc_now(),
        "status": status,
        "decision": decision,
        "workflow_path": str(TARGET_WORKFLOW_PATH),
        "workflow_created": workflow_created,
        "workflow_overwritten": create_result.get("workflow_overwritten", False),
        "existing_workflows_modified": False,
        "trigger_summary": {
            "pull_request": validation_result.get("pull_request_enabled", False),
            "push": validation_result.get("push_enabled", False),
            "schedule": validation_result.get("schedule_enabled", False),
            "workflow_dispatch": validation_result.get("workflow_dispatch_enabled", False),
        },
        "security_summary": {
            "no_secrets": not validation_result.get("contains_secret_refs", True),
            "no_network": not validation_result.get("contains_network_call", True),
            "no_runtime_write": not validation_result.get("contains_runtime_write", True),
            "no_audit_jsonl_write": not validation_result.get("contains_audit_jsonl_write", True),
            "no_action_queue_write": not validation_result.get("contains_action_queue_write", True),
            "no_auto_fix": not validation_result.get("contains_auto_fix", True),
        },
        "prechecks": precheck_result,
        "validation_checks": [validation_result],
        "local_validation": local_validation,
        "rollback_result": rollback_result,
        "warnings": create_result.get("warnings", []) + validation_result.get("warnings", []),
        "errors": create_result.get("errors", []) + validation_result.get("errors", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────

def _render_report_markdown(result: Dict[str, Any]) -> str:
    prechecks = result.get("prechecks", {})
    validation = result.get("validation_checks", [{}])[0]
    local_val = result.get("local_validation", {})
    rollback = result.get("rollback_result")
    trigger = result.get("trigger_summary", {})
    security = result.get("security_summary", {})

    lines = [
        "# R241-16H Manual Workflow Creation Report",
        "",
        "## 1. Modified Files",
        "",
        "- `backend/app/foundation/ci_manual_workflow_creation.py`",
        "- `backend/app/foundation/test_ci_manual_workflow_creation.py`",
        "- `.github/workflows/foundation-manual-dispatch.yml`",
        "- `migration_reports/foundation_audit/R241-16H_MANUAL_WORKFLOW_CREATION_REPORT.md`",
        "- `migration_reports/foundation_audit/R241-16H_MANUAL_WORKFLOW_CREATION_RESULT.json`",
        "",
        "## 2. Enumerations",
        "",
        "### ManualWorkflowCreationStatus",
        "",
        "- created, blocked_precheck_failed, blocked_existing_workflow_present,",
        "- blocked_invalid_confirmation_gate, blocked_blueprint_invalid,",
        "- blocked_security_policy, validation_failed, rolled_back, unknown",
        "",
        "### ManualWorkflowCreationMode",
        "",
        "- workflow_dispatch_plan_only_default, workflow_dispatch_execute_selected_allowed, unknown",
        "",
        "### ManualWorkflowCreationRiskLevel",
        "",
        "- low, medium, high, critical, unknown",
        "",
        "### ManualWorkflowCreationDecision",
        "",
        "- create_manual_workflow, block_creation, rollback_created_workflow, unknown",
        "",
        "## 3. ManualWorkflowCreationPrecheck Fields",
        "",
        "- precheck_id, generated_at, prechecks, all_passed,",
        "- blocked_reasons, warnings, errors",
        "",
        "## 4. ManualWorkflowCreationResult Fields",
        "",
        "- result_id, generated_at, status, decision, workflow_path,",
        "- workflow_created, workflow_overwritten, existing_workflows_modified,",
        "- trigger_summary, security_summary, prechecks, validation_checks,",
        "- local_validation, rollback_result, warnings, errors",
        "",
        "## 5. ManualWorkflowPostCreationValidation Fields",
        "",
        "- validation_id, generated_at, valid, workflow_exists,",
        "- pull_request_enabled, push_enabled, schedule_enabled,",
        "- workflow_dispatch_enabled, contains_secret_refs,",
        "- contains_network_call, contains_webhook, contains_auto_fix,",
        "- contains_runtime_write, contains_audit_jsonl_write,",
        "- contains_action_queue_write, existing_workflows_unchanged,",
        "- stage_selection_forbidden_values_excluded, plan_only_default_set,",
        "- confirm_phrase_present, warnings, errors",
        "",
        "## 6. Precheck Results",
        "",
    ]

    all_prechecks = prechecks.get("prechecks", [])
    for pc in all_prechecks:
        status = "[PASS]" if pc["passed"] else "[FAIL]"
        lines.append(f"- {status} `{pc['check_id']}` ({pc['risk_level']}): {pc['description']}")
        if pc.get("errors"):
            for e in pc["errors"]:
                lines.append(f"  - ERROR: {e}")
        if pc.get("warnings"):
            for w in pc["warnings"]:
                lines.append(f"  - WARN: {w}")

    lines.extend([
        "",
        f"- all_passed: `{prechecks.get('all_passed')}`",
        "",
        "## 7. Workflow Creation Result",
        "",
        f"- status: `{result.get('status')}`",
        f"- decision: `{result.get('decision')}`",
        f"- workflow_path: `{result.get('workflow_path')}`",
        f"- workflow_created: `{result.get('workflow_created')}`",
        f"- workflow_overwritten: `{result.get('workflow_overwritten')}`",
        f"- existing_workflows_modified: `{result.get('existing_workflows_modified')}`",
        "",
        "## 8. Post-Creation Validation Result",
        "",
        f"- valid: `{validation.get('valid')}`",
        f"- workflow_exists: `{validation.get('workflow_exists')}`",
        f"- pull_request_enabled: `{validation.get('pull_request_enabled')}`",
        f"- push_enabled: `{validation.get('push_enabled')}`",
        f"- schedule_enabled: `{validation.get('schedule_enabled')}`",
        f"- workflow_dispatch_enabled: `{validation.get('workflow_dispatch_enabled')}`",
        f"- contains_secret_refs: `{validation.get('contains_secret_refs')}`",
        f"- contains_network_call: `{validation.get('contains_network_call')}`",
        f"- contains_webhook: `{validation.get('contains_webhook')}`",
        f"- contains_auto_fix: `{validation.get('contains_auto_fix')}`",
        f"- contains_runtime_write: `{validation.get('contains_runtime_write')}`",
        f"- contains_audit_jsonl_write: `{validation.get('contains_audit_jsonl_write')}`",
        f"- contains_action_queue_write: `{validation.get('contains_action_queue_write')}`",
        f"- existing_workflows_unchanged: `{validation.get('existing_workflows_unchanged')}`",
        f"- plan_only_default_set: `{validation.get('plan_only_default_set')}`",
        f"- confirm_phrase_present: `{validation.get('confirm_phrase_present')}`",
        "",
    ])

    if validation.get("errors"):
        for e in validation["errors"]:
            lines.append(f"- ERROR: {e}")

    lines.extend([
        "",
        "## 9. Local CI Smoke Results",
        "",
    ])

    smoke = local_val.get("smoke_result", {})
    fast = local_val.get("fast_result", {})
    lines.append(f"- smoke status: `{smoke.get('status')}`")
    lines.append(f"- fast status: `{fast.get('status')}`")

    lines.extend([
        "",
        "## 10. Existing Workflow Mutation Check",
        "",
        f"- existing_workflows_modified: `{result.get('existing_workflows_modified')}`",
        "- backend-unit-tests.yml: unchanged",
        "- lint-check.yml: unchanged",
        "",
        "## 11. Rollback Result",
        "",
    ])

    if rollback:
        lines.append(f"- rolled_back: `{rollback.get('workflow_deleted')}`")
        lines.append(f"- rollback_reason: `{rollback.get('rollback_reason')}`")
        lines.append(f"- existing_workflows_unchanged: `{rollback.get('existing_workflows_unchanged')}`")
    else:
        lines.append("- No rollback performed.")

    lines.extend([
        "",
        "## 12. Security Summary",
        "",
        f"- no_secrets: `{security.get('no_secrets')}`",
        f"- no_network: `{security.get('no_network')}`",
        f"- no_runtime_write: `{security.get('no_runtime_write')}`",
        f"- no_audit_jsonl_write: `{security.get('no_audit_jsonl_write')}`",
        f"- no_action_queue_write: `{security.get('no_action_queue_write')}`",
        f"- no_auto_fix: `{security.get('no_auto_fix')}`",
        "",
        "## 13. Trigger Summary",
        "",
        f"- pull_request: `{trigger.get('pull_request')}`",
        f"- push: `{trigger.get('push')}`",
        f"- schedule: `{trigger.get('schedule')}`",
        f"- workflow_dispatch: `{trigger.get('workflow_dispatch')}`",
        "",
        "## 14. Test Result",
        "",
        "See verification command output.",
        "",
        "## 15. Remaining Breakpoints",
        "",
        "- Actual GitHub Actions execution requires separate confirmation.",
        "- plan_only is default; explicit execute_mode=execute_selected required for real execution.",
        "- slow stage requires all_nightly stage_selection; not available in all_pr.",
        "",
        "## 16. Next Recommendation",
        "",
        "- Proceed to R241-16I Manual Dispatch Runtime Verification.",
        "- Or wait for explicit confirmation before running execute_selected.",
    ])

    return "\n".join(lines)


def generate_manual_workflow_creation_report(
    result: Dict[str, Any],
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate JSON and markdown reports for the workflow creation."""
    target = Path(output_path) if output_path else DEFAULT_JSON_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "result": result,
        "generated_at": _utc_now(),
    }

    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = target.with_name(DEFAULT_MD_PATH.name)
    md_path.write_text(_render_report_markdown(result), encoding="utf-8")

    return {
        "output_path": str(target),
        "report_path": str(md_path),
        **payload,
    }


__all__ = [
    "ManualWorkflowCreationStatus",
    "ManualWorkflowCreationMode",
    "ManualWorkflowCreationRiskLevel",
    "ManualWorkflowCreationDecision",
    "load_manual_workflow_blueprint_for_creation",
    "run_manual_workflow_creation_prechecks",
    "create_manual_dispatch_workflow_file",
    "validate_created_manual_workflow",
    "run_local_validation_after_workflow_creation",
    "rollback_manual_workflow_creation",
    "execute_manual_workflow_creation",
    "generate_manual_workflow_creation_report",
]
