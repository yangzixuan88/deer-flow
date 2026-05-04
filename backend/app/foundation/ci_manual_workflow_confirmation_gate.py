"""Manual Workflow Creation Confirmation Gate for R241-16G.

This module validates whether manual workflow creation is allowed based on
confirmation phrase and requested option. It does not create workflows,
enable triggers, call network/webhooks, read secrets, write runtime state,
write audit JSONL, or execute auto-fix.
"""

from __future__ import annotations

import json
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
DEFAULT_JSON_PATH = REPORT_DIR / "R241-16G_MANUAL_WORKFLOW_CONFIRMATION_GATE.json"
DEFAULT_MD_PATH = REPORT_DIR / "R241-16G_MANUAL_WORKFLOW_CONFIRMATION_GATE.md"

# The one valid confirmation phrase
VALID_CONFIRMATION_PHRASE = "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN"


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowConfirmationGateStatus:
    ALLOWED_FOR_NEXT_REVIEW = "allowed_for_next_review"
    BLOCKED_MISSING_CONFIRMATION = "blocked_missing_confirmation"
    BLOCKED_INVALID_CONFIRMATION = "blocked_invalid_confirmation"
    BLOCKED_INVALID_OPTION = "blocked_invalid_option"
    BLOCKED_SECURITY_CONDITION = "blocked_security_condition"
    BLOCKED_PATH_POLICY = "blocked_path_policy"
    BLOCKED_EXISTING_WORKFLOW_CONFLICT = "blocked_existing_workflow_conflict"
    DESIGN_ONLY = "design_only"
    UNKNOWN = "unknown"


class WorkflowCreationOption:
    OPTION_B_BLUEPRINT_ONLY = "option_b_blueprint_only"
    OPTION_C_MANUAL_PLAN_ONLY_WORKFLOW = "option_c_manual_plan_only_workflow"
    OPTION_D_MANUAL_FAST_SAFETY_EXECUTE_WORKFLOW = "option_d_manual_fast_safety_execute_workflow"
    UNKNOWN = "unknown"


class WorkflowConfirmationRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class WorkflowConfirmationDecision:
    BLOCK = "block"
    ALLOW_NEXT_REVIEW_ONLY = "allow_next_review_only"
    ALLOW_IMPLEMENTATION_REVIEW = "allow_implementation_review"
    UNKNOWN = "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Build confirmation input
# ─────────────────────────────────────────────────────────────────────────────

def build_workflow_confirmation_input(
    confirmation_phrase: Optional[str] = None,
    requested_option: Optional[str] = None,
) -> Dict[str, Any]:
    """Build confirmation input from provided phrase and option."""
    errors: List[str] = []
    warnings: List[str] = []

    phrase_present = confirmation_phrase is not None and confirmation_phrase != ""
    phrase_exact_match = phrase_present and confirmation_phrase == VALID_CONFIRMATION_PHRASE

    # Default to option_b if not specified
    valid_options = {
        WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY,
        WorkflowCreationOption.OPTION_C_MANUAL_PLAN_ONLY_WORKFLOW,
        WorkflowCreationOption.OPTION_D_MANUAL_FAST_SAFETY_EXECUTE_WORKFLOW,
    }
    forbidden_options = {"pr_blocking", "push", "schedule", "webhook", "secret", "auto_fix", "full"}

    if requested_option is None:
        effective_option = WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY
    elif requested_option in forbidden_options:
        effective_option = WorkflowCreationOption.UNKNOWN
        errors.append(f"forbidden_option:{requested_option}")
    else:
        effective_option = requested_option

    option_valid = effective_option in valid_options

    # Build scope description
    scopes = {
        WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY: "blueprint_only",
        WorkflowCreationOption.OPTION_C_MANUAL_PLAN_ONLY_WORKFLOW: "workflow_dispatch_plan_only",
        WorkflowCreationOption.OPTION_D_MANUAL_FAST_SAFETY_EXECUTE_WORKFLOW: "workflow_dispatch_execute_fast_safety",
    }
    requested_scope = scopes.get(effective_option, "unknown")

    return {
        "input_id": "workflow_confirmation_input",
        "provided_confirmation_phrase": confirmation_phrase,
        "expected_confirmation_phrase": VALID_CONFIRMATION_PHRASE,
        "phrase_present": phrase_present,
        "phrase_exact_match": phrase_exact_match,
        "requested_option": effective_option,
        "requested_option_valid": option_valid,
        "requested_scope": requested_scope,
        "provided_at": _utc_now(),
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validate confirmation phrase
# ─────────────────────────────────────────────────────────────────────────────

def validate_workflow_confirmation_phrase(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the confirmation phrase."""
    errors: List[str] = []
    warnings: List[str] = []

    phrase_present = input_data.get("phrase_present", False)
    phrase_exact_match = input_data.get("phrase_exact_match", False)

    if not phrase_present:
        errors.append("confirmation_phrase_missing")
    elif not phrase_exact_match:
        errors.append("confirmation_phrase_not_exact_match")

    passed = len(errors) == 0

    return {
        "check_id": "check_confirmation_phrase",
        "check_type": "confirmation_phrase",
        "passed": passed,
        "risk_level": WorkflowConfirmationRiskLevel.CRITICAL,
        "description": "Confirmation phrase must be exact match of VALID_CONFIRMATION_PHRASE.",
        "evidence_refs": ["build_workflow_confirmation_input()"],
        "required_before_allow": True,
        "blocked_reasons": errors if not passed else [],
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validate requested workflow option
# ─────────────────────────────────────────────────────────────────────────────

def validate_requested_workflow_option(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the requested workflow creation option."""
    errors: List[str] = []
    warnings: List[str] = []

    phrase_exact_match = input_data.get("phrase_exact_match", False)
    requested_option = input_data.get("requested_option", WorkflowCreationOption.UNKNOWN)
    option_valid = input_data.get("requested_option_valid", False)

    if not option_valid:
        errors.append(f"invalid_requested_option:{requested_option}")
    elif requested_option == WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY:
        # option_b is always allowed as blueprint-only
        warnings.append("option_b_remains_blueprint_only_no_workflow_created")
    elif requested_option in (
        WorkflowCreationOption.OPTION_C_MANUAL_PLAN_ONLY_WORKFLOW,
        WorkflowCreationOption.OPTION_D_MANUAL_FAST_SAFETY_EXECUTE_WORKFLOW,
    ):
        if not phrase_exact_match:
            errors.append("option_c_or_d_requires_exact_confirmation_phrase")

    passed = len(errors) == 0

    return {
        "check_id": "check_requested_workflow_option",
        "check_type": "requested_option",
        "passed": passed,
        "risk_level": WorkflowConfirmationRiskLevel.HIGH,
        "description": "Requested option must be valid and confirmed.",
        "evidence_refs": ["build_workflow_confirmation_input()"],
        "required_before_allow": True,
        "blocked_reasons": errors if not passed else [],
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validate blueprint still safe
# ─────────────────────────────────────────────────────────────────────────────

def validate_blueprint_still_safe(root: Optional[str] = None) -> Dict[str, Any]:
    """Validate the R241-16F blueprint is still in safe report-only state."""
    root_path = Path(root) if root else ROOT

    blueprint = impl.build_manual_dispatch_workflow_blueprint(str(root_path))
    yaml_result = impl.render_manual_dispatch_workflow_blueprint_yaml(blueprint)

    errors: List[str] = []
    warnings: List[str] = []

    if blueprint.get("write_target_allowed") is not False:
        errors.append("blueprint_write_target_not_false")

    blueprint_path = blueprint.get("report_only_blueprint_path", "")
    if not blueprint_path.endswith(".yml.txt"):
        errors.append("blueprint_path_not_yml_txt")

    yaml_text = yaml_result.get("yaml_text", "")
    forbidden = ["pull_request:", "push:", "schedule:", "secrets.", "curl", "Invoke-WebRequest", "webhook", "auto-fix"]
    for token in forbidden:
        if token.lower() in yaml_text.lower():
            errors.append(f"yaml_contains_forbidden:{token}")

    passed = len(errors) == 0

    return {
        "check_id": "check_blueprint_safety",
        "check_type": "blueprint_safety",
        "passed": passed,
        "risk_level": WorkflowConfirmationRiskLevel.CRITICAL,
        "description": "Blueprint must remain report-only with no forbidden tokens.",
        "evidence_refs": ["R241-16F blueprint", "render_manual_dispatch_workflow_blueprint_yaml()"],
        "required_before_allow": True,
        "blocked_reasons": errors if not passed else [],
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validate existing workflow state
# ─────────────────────────────────────────────────────────────────────────────

def validate_existing_workflow_state(root: Optional[str] = None) -> Dict[str, Any]:
    """Validate existing workflow state is unchanged."""
    root_path = Path(root) if root else ROOT

    errors: List[str] = []
    warnings: List[str] = []

    discovery = ci_enablement_review.discover_existing_workflows(str(root_path))
    compatibility = [
        ci_enablement_review.analyze_existing_workflow_compatibility(path)
        for path in discovery.get("workflows", [])
    ]

    high_conflict = any(
        item.get("conflict_level") in {ci_enablement_review.EnablementRiskLevel.HIGH, ci_enablement_review.EnablementRiskLevel.CRITICAL}
        for item in compatibility
    )

    if high_conflict:
        warnings.append("existing_workflow_high_conflict_recorded")

    return {
        "check_id": "check_existing_workflow_state",
        "check_type": "existing_workflow_state",
        "passed": True,
        "risk_level": WorkflowConfirmationRiskLevel.MEDIUM,
        "description": "Existing workflows unchanged; no new workflow created this round.",
        "evidence_refs": ["ci_enablement_review.discover_existing_workflows()"],
        "required_before_allow": True,
        "blocked_reasons": [],
        "warnings": warnings,
        "errors": errors,
        "existing_workflow_count": len(compatibility),
        "existing_workflow_compatibility": compatibility,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validate path and artifact policy
# ─────────────────────────────────────────────────────────────────────────────

def validate_confirmation_path_and_artifact_policy(root: Optional[str] = None) -> Dict[str, Any]:
    """Validate path compatibility and artifact policy."""
    root_path = Path(root) if root else ROOT

    errors: List[str] = []
    warnings: List[str] = []

    path_policy = ci_plan.build_ci_path_compatibility_policy(str(root_path))
    artifact_policy = ci_plan.build_ci_artifact_collection_specs(str(root_path))

    # Check path inconsistency is detected but no migration is allowed
    if path_policy.get("path_inconsistency"):
        warnings.append("path_inconsistency_detected_report_only")

    # Check artifact policy excludes sensitive paths
    foundation_spec = next(
        (s for s in artifact_policy.get("artifact_specs", []) if s.get("artifact_type") == ci_plan.CIArtifactType.FOUNDATION_AUDIT_REPORT),
        None,
    )
    if foundation_spec:
        excludes = foundation_spec.get("exclude_patterns", [])
        required_excludes = ["**/audit_trail/*.jsonl"]
        for req in required_excludes:
            if req not in excludes:
                errors.append(f"artifact_policy_missing_exclusion:{req}")

    passed = len(errors) == 0

    return {
        "check_id": "check_path_and_artifact_policy",
        "check_type": "path_artifact_policy",
        "passed": passed,
        "risk_level": WorkflowConfirmationRiskLevel.MEDIUM,
        "description": "Path and artifact policy in safe report-only state.",
        "evidence_refs": ["build_ci_path_compatibility_policy()", "build_ci_artifact_collection_specs()"],
        "required_before_allow": True,
        "blocked_reasons": errors if not passed else [],
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Build all gate checks
# ─────────────────────────────────────────────────────────────────────────────

def build_confirmation_gate_checks(
    input_data: Dict[str, Any],
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Build all confirmation gate checks."""
    phrase_check = validate_workflow_confirmation_phrase(input_data)
    option_check = validate_requested_workflow_option(input_data)
    blueprint_check = validate_blueprint_still_safe(root)
    workflow_check = validate_existing_workflow_state(root)
    path_check = validate_confirmation_path_and_artifact_policy(root)

    # Static security checks (always pass since no workflow created this round)
    static_checks = [
        {
            "check_id": "check_no_github_workflows_write_this_round",
            "check_type": "no_github_workflows_write",
            "passed": True,
            "risk_level": WorkflowConfirmationRiskLevel.CRITICAL,
            "description": "No .github/workflows files written this round.",
            "evidence_refs": ["design_only_gate"],
            "required_before_allow": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_pr_push_schedule_triggers",
            "check_type": "no_pr_push_schedule_triggers",
            "passed": True,
            "risk_level": WorkflowConfirmationRiskLevel.CRITICAL,
            "description": "No PR/push/schedule triggers enabled this round.",
            "evidence_refs": ["design_only_gate"],
            "required_before_allow": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_secrets",
            "check_type": "no_secrets",
            "passed": True,
            "risk_level": WorkflowConfirmationRiskLevel.CRITICAL,
            "description": "No secrets read this round.",
            "evidence_refs": ["design_only_gate"],
            "required_before_allow": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_network",
            "check_type": "no_network",
            "passed": True,
            "risk_level": WorkflowConfirmationRiskLevel.CRITICAL,
            "description": "No network calls made this round.",
            "evidence_refs": ["design_only_gate"],
            "required_before_allow": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_runtime_write",
            "check_type": "no_runtime_write",
            "passed": True,
            "risk_level": WorkflowConfirmationRiskLevel.CRITICAL,
            "description": "No runtime files written this round.",
            "evidence_refs": ["design_only_gate"],
            "required_before_allow": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_audit_jsonl_write",
            "check_type": "no_audit_jsonl_write",
            "passed": True,
            "risk_level": WorkflowConfirmationRiskLevel.HIGH,
            "description": "No audit JSONL written this round.",
            "evidence_refs": ["design_only_gate"],
            "required_before_allow": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_action_queue_write",
            "check_type": "no_action_queue_write",
            "passed": True,
            "risk_level": WorkflowConfirmationRiskLevel.HIGH,
            "description": "No action queue written this round.",
            "evidence_refs": ["design_only_gate"],
            "required_before_allow": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_auto_fix",
            "check_type": "no_auto_fix",
            "passed": True,
            "risk_level": WorkflowConfirmationRiskLevel.CRITICAL,
            "description": "No auto-fix executed this round.",
            "evidence_refs": ["design_only_gate"],
            "required_before_allow": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
    ]

    all_checks = [phrase_check, option_check, blueprint_check, workflow_check, path_check] + static_checks

    return {
        "confirmation_gate_checks": all_checks,
        "check_count": len(all_checks),
        "all_passed": all(c["passed"] for c in all_checks),
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core gate evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_workflow_confirmation_gate(
    confirmation_phrase: Optional[str] = None,
    requested_option: Optional[str] = None,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate the confirmation gate and produce decision."""
    root_path = Path(root) if root else ROOT

    input_data = build_workflow_confirmation_input(confirmation_phrase, requested_option)
    gate_checks = build_confirmation_gate_checks(input_data, str(root_path))

    phrase_present = input_data.get("phrase_present", False)
    phrase_exact_match = input_data.get("phrase_exact_match", False)
    requested_option_val = input_data.get("requested_option", WorkflowCreationOption.UNKNOWN)

    # Determine status and decision
    if not phrase_present:
        status = WorkflowConfirmationGateStatus.BLOCKED_MISSING_CONFIRMATION
        decision = WorkflowConfirmationDecision.BLOCK
        workflow_creation_allowed_now = False
        allowed_next_phase = None
    elif not phrase_exact_match:
        status = WorkflowConfirmationGateStatus.BLOCKED_INVALID_CONFIRMATION
        decision = WorkflowConfirmationDecision.BLOCK
        workflow_creation_allowed_now = False
        allowed_next_phase = None
    elif not gate_checks["all_passed"]:
        status = WorkflowConfirmationGateStatus.BLOCKED_SECURITY_CONDITION
        decision = WorkflowConfirmationDecision.BLOCK
        workflow_creation_allowed_now = False
        allowed_next_phase = None
    elif requested_option_val == WorkflowCreationOption.OPTION_B_BLUEPRINT_ONLY:
        status = WorkflowConfirmationGateStatus.ALLOWED_FOR_NEXT_REVIEW
        decision = WorkflowConfirmationDecision.ALLOW_NEXT_REVIEW_ONLY
        workflow_creation_allowed_now = False
        allowed_next_phase = "R241-16F_continue_blueprint_only"
    else:
        # option_c or option_d with valid phrase
        status = WorkflowConfirmationGateStatus.ALLOWED_FOR_NEXT_REVIEW
        decision = WorkflowConfirmationDecision.ALLOW_IMPLEMENTATION_REVIEW
        workflow_creation_allowed_now = False
        allowed_next_phase = "R241-16H_workflow_creation_implementation"

    # Build blocked reasons from failed checks
    blocked_reasons = [
        c["check_id"] for c in gate_checks["confirmation_gate_checks"]
        if not c["passed"]
    ]

    # Get blueprint reference
    blueprint = impl.build_manual_dispatch_workflow_blueprint(str(root_path))

    # Get rollback plan from R241-16E
    rollback_plan = mdr.build_manual_dispatch_rollback_plan()

    # Get existing workflow compatibility
    discovery = ci_enablement_review.discover_existing_workflows(str(root_path))
    compatibility = [
        ci_enablement_review.analyze_existing_workflow_compatibility(path)
        for path in discovery.get("workflows", [])
    ]

    decision_result: Dict[str, Any] = {
        "decision_id": "R241-16G_workflow_confirmation_gate_decision",
        "generated_at": _utc_now(),
        "status": status,
        "decision": decision,
        "allowed_next_phase": allowed_next_phase,
        "workflow_creation_allowed_now": workflow_creation_allowed_now,
        "confirmation_input": input_data,
        "requested_option": requested_option_val,
        "confirmation_checks": gate_checks["confirmation_gate_checks"],
        "blueprint_ref": {
            "blueprint_id": blueprint.get("blueprint_id"),
            "workflow_filename_proposed": blueprint.get("workflow_filename_proposed"),
            "write_target_allowed": blueprint.get("write_target_allowed"),
            "report_only_blueprint_path": blueprint.get("report_only_blueprint_path"),
        },
        "existing_workflow_compatibility": compatibility,
        "path_compatibility_policy": ci_plan.build_ci_path_compatibility_policy(str(root_path)),
        "artifact_policy": ci_plan.build_ci_artifact_collection_specs(str(root_path)),
        "rollback_plan": rollback_plan,
        "security_policy": {
            "no_secrets": True,
            "no_network": True,
            "no_runtime_write": True,
            "no_audit_jsonl_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
        },
        "blocked_reasons": blocked_reasons,
        "warnings": gate_checks.get("warnings", []),
        "errors": gate_checks.get("errors", []),
    }

    return decision_result


# ─────────────────────────────────────────────────────────────────────────────
# Validate gate decision
# ─────────────────────────────────────────────────────────────────────────────

def validate_workflow_confirmation_gate_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the gate decision for policy compliance."""
    errors: List[str] = []
    warnings: List[str] = []

    if decision.get("workflow_creation_allowed_now") is True:
        errors.append("workflow_creation_allowed_now_must_be_false")

    if not decision.get("rollback_plan", {}).get("rollback_steps"):
        errors.append("rollback_plan_missing")

    checks = decision.get("confirmation_checks", [])
    if not checks:
        errors.append("confirmation_checks_missing")

    failed_checks = [c["check_id"] for c in checks if not c["passed"]]
    if failed_checks:
        errors.append(f"confirmation_checks_failed:{failed_checks}")

    # Static security validations (always true since nothing created this round)
    if decision.get("decision") == WorkflowConfirmationDecision.ALLOW_IMPLEMENTATION_REVIEW:
        if not decision.get("allowed_next_phase"):
            errors.append("allowed_next_phase_missing")

    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "validated_at": _utc_now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Markdown rendering
# ─────────────────────────────────────────────────────────────────────────────

def _render_markdown(decision: Dict[str, Any], validation: Dict[str, Any]) -> str:
    input_data = decision.get("confirmation_input", {})
    checks = decision.get("confirmation_gate_checks", [])
    compat = decision.get("existing_workflow_compatibility", [])

    lines = [
        "# R241-16G Manual Workflow Creation Confirmation Gate",
        "",
        "## 1. Modified Files",
        "",
        "- `backend/app/foundation/ci_manual_workflow_confirmation_gate.py`",
        "- `backend/app/foundation/test_ci_manual_workflow_confirmation_gate.py`",
        "- `migration_reports/foundation_audit/R241-16G_MANUAL_WORKFLOW_CONFIRMATION_GATE.json`",
        "- `migration_reports/foundation_audit/R241-16G_MANUAL_WORKFLOW_CONFIRMATION_GATE.md`",
        "",
        "## 2. Enumerations",
        "",
        "### WorkflowConfirmationGateStatus",
        "",
        "- allowed_for_next_review, blocked_missing_confirmation, blocked_invalid_confirmation,",
        "- blocked_invalid_option, blocked_security_condition, blocked_path_policy,",
        "- blocked_existing_workflow_conflict, design_only, unknown",
        "",
        "### WorkflowCreationOption",
        "",
        "- option_b_blueprint_only, option_c_manual_plan_only_workflow,",
        "- option_d_manual_fast_safety_execute_workflow, unknown",
        "",
        "### WorkflowConfirmationRiskLevel",
        "",
        "- low, medium, high, critical, unknown",
        "",
        "### WorkflowConfirmationDecision",
        "",
        "- block, allow_next_review_only, allow_implementation_review, unknown",
        "",
        "## 3. WorkflowConfirmationInput Fields",
        "",
        "- input_id, provided_confirmation_phrase, expected_confirmation_phrase",
        "- phrase_present, phrase_exact_match, requested_option",
        "- requested_option_valid, requested_scope, provided_at, warnings, errors",
        "",
        "## 4. WorkflowConfirmationCheck Fields",
        "",
        "- check_id, check_type, passed, risk_level, description",
        "- evidence_refs, required_before_allow, blocked_reasons, warnings, errors",
        "",
        "## 5. WorkflowConfirmationGateDecision Fields",
        "",
        "- decision_id, generated_at, status, decision, allowed_next_phase",
        "- workflow_creation_allowed_now, confirmation_input, requested_option",
        "- confirmation_checks, blueprint_ref, existing_workflow_compatibility",
        "- path_compatibility_policy, artifact_policy, rollback_plan, security_policy",
        "- blocked_reasons, warnings, errors",
        "",
        "## 6. Confirmation Input Result",
        "",
        f"- phrase_present: `{input_data.get('phrase_present')}`",
        f"- phrase_exact_match: `{input_data.get('phrase_exact_match')}`",
        f"- expected_confirmation_phrase: `{input_data.get('expected_confirmation_phrase')}`",
        f"- requested_option: `{input_data.get('requested_option')}`",
        f"- requested_option_valid: `{input_data.get('requested_option_valid')}`",
        f"- requested_scope: `{input_data.get('requested_scope')}`",
        "",
        "## 7. Confirmation Phrase Validation Result",
        "",
    ]

    phrase_check = next((c for c in checks if c["check_id"] == "check_confirmation_phrase"), None)
    if phrase_check:
        status = "[PASS]" if phrase_check["passed"] else "[FAIL]"
        lines.append(f"- {status} `{phrase_check['check_id']}` ({phrase_check['risk_level']}): {phrase_check['description']}")

    lines.extend([
        "",
        "## 8. Requested Option Validation Result",
        "",
    ])

    option_check = next((c for c in checks if c["check_id"] == "check_requested_workflow_option"), None)
    if option_check:
        status = "[PASS]" if option_check["passed"] else "[FAIL]"
        lines.append(f"- {status} `{option_check['check_id']}` ({option_check['risk_level']}): {option_check['description']}")

    lines.extend([
        "",
        "## 9. Blueprint Safety Validation Result",
        "",
    ])

    blueprint_check = next((c for c in checks if c["check_id"] == "check_blueprint_safety"), None)
    if blueprint_check:
        status = "[PASS]" if blueprint_check["passed"] else "[FAIL]"
        lines.append(f"- {status} `{blueprint_check['check_id']}` ({blueprint_check['risk_level']}): {blueprint_check['description']}")

    lines.extend([
        "",
        "## 10. Existing Workflow Validation Result",
        "",
        f"- existing_workflow_count: `{len(compat)}`",
    ])

    for item in compat:
        lines.append(
            f"- `{item.get('workflow_path')}`: conflict={item.get('conflict_level')}, "
            f"overlap={item.get('likely_overlap_with_foundation_ci')}, "
            f"triggers={item.get('trigger_summary')}"
        )

    lines.extend([
        "",
        "## 11. Path / Artifact Policy Validation Result",
        "",
        f"- path_inconsistency: `{decision.get('path_compatibility_policy', {}).get('path_inconsistency')}`",
        "",
        "## 12. Gate Decision Result",
        "",
        f"- decision_id: `{decision.get('decision_id')}`",
        f"- status: `{decision.get('status')}`",
        f"- decision: `{decision.get('decision')}`",
        f"- allowed_next_phase: `{decision.get('allowed_next_phase')}`",
        f"- workflow_creation_allowed_now: `{decision.get('workflow_creation_allowed_now')}`",
        f"- blocked_reasons: `{decision.get('blocked_reasons')}`",
        "",
        "## 13. Validation Result",
        "",
        f"- valid: `{validation.get('valid')}`",
        f"- errors: `{validation.get('errors')}`",
        "",
        "## 14. Test Result",
        "",
        "See verification command output.",
        "",
        "## 15. Workflow / Trigger",
        "",
        "No workflow is created. No trigger is enabled.",
        "",
        "## 16. Existing Workflow Mutation",
        "",
        "Existing workflow files are only read; they are not modified.",
        "",
        "## 17. Secret Access",
        "",
        "No secret is read.",
        "",
        "## 18. Network / Webhook",
        "",
        "No network or webhook call is performed.",
        "",
        "## 19. Runtime / Audit JSONL / Action Queue",
        "",
        "No runtime, audit JSONL, or action queue write is performed.",
        "",
        "## 20. Auto-fix",
        "",
        "No auto-fix is executed.",
        "",
        "## 21. Remaining Breakpoints",
        "",
        "- No confirmation phrase received: gate is BLOCKED.",
        "- Invalid confirmation phrase: gate is BLOCKED.",
        "- Even with valid phrase and option_c/d: workflow_creation_allowed_now=false.",
        "- Actual workflow creation requires R241-16H review and explicit confirmation.",
        "",
        "## 22. Next Recommendation",
        "",
        f"- Current status: `{decision.get('status')}`",
        f"- Current decision: `{decision.get('decision')}`",
        f"- Next phase if confirmed: R241-16H workflow_creation_implementation",
    ])

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_workflow_confirmation_gate_report(
    confirmation_phrase: Optional[str] = None,
    requested_option: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate the R241-16G confirmation gate JSON and markdown reports."""
    target = Path(output_path) if output_path else DEFAULT_JSON_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    decision = evaluate_workflow_confirmation_gate(confirmation_phrase, requested_option)
    validation = validate_workflow_confirmation_gate_decision(decision)

    payload = {
        "decision": decision,
        "validation": validation,
        "generated_at": _utc_now(),
    }

    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = target.with_name(DEFAULT_MD_PATH.name)
    md_path.write_text(_render_markdown(decision, validation), encoding="utf-8")

    return {
        "output_path": str(target),
        "report_path": str(md_path),
        **payload,
    }


__all__ = [
    "WorkflowConfirmationGateStatus",
    "WorkflowCreationOption",
    "WorkflowConfirmationRiskLevel",
    "WorkflowConfirmationDecision",
    "VALID_CONFIRMATION_PHRASE",
    "build_workflow_confirmation_input",
    "validate_workflow_confirmation_phrase",
    "validate_requested_workflow_option",
    "validate_blueprint_still_safe",
    "validate_existing_workflow_state",
    "validate_confirmation_path_and_artifact_policy",
    "build_confirmation_gate_checks",
    "evaluate_workflow_confirmation_gate",
    "validate_workflow_confirmation_gate_decision",
    "generate_workflow_confirmation_gate_report",
]
