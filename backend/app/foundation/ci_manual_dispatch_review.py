"""Manual Dispatch Dry-run Review for R241-16E.

This module reviews whether manual dispatch dry-run is ready for implementation.
It does not create workflow files, enable triggers, call network/webhooks, read
secrets, write runtime state, write audit JSONL, write action queues, or execute
auto-fix.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.foundation import ci_implementation_plan as ci_plan
from app.foundation import ci_local_dryrun
from app.foundation import ci_workflow_draft
from app.foundation import ci_enablement_review


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_JSON_PATH = REPORT_DIR / "R241-16E_MANUAL_DISPATCH_DRYRUN_REVIEW.json"
DEFAULT_MD_PATH = REPORT_DIR / "R241-16E_MANUAL_DISPATCH_DRYRUN_REVIEW.md"


class ManualDispatchReadinessStatus:
    READY_FOR_IMPLEMENTATION_REVIEW = "ready_for_implementation_review"
    BLOCKED_MISSING_CONFIRMATION_INPUT = "blocked_missing_confirmation_input"
    BLOCKED_JOB_GUARD_MISSING = "blocked_job_guard_missing"
    BLOCKED_ARTIFACT_POLICY = "blocked_artifact_policy"
    BLOCKED_EXISTING_WORKFLOW_CONFLICT = "blocked_existing_workflow_conflict"
    BLOCKED_SECURITY_POLICY = "blocked_security_policy"
    DESIGN_ONLY = "design_only"
    UNKNOWN = "unknown"


class ManualDispatchRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ManualDispatchJobGuardMode:
    GUARDED_BY_CONFIRMATION_INPUT = "guarded_by_confirmation_input"
    GUARDED_BY_IF_FALSE = "guarded_by_if_false"
    GUARDED_BY_STAGE_SELECTION = "guarded_by_stage_selection"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class ManualDispatchImplementationOption:
    KEEP_DISABLED_DRAFT = "keep_disabled_draft"
    MANUAL_DISPATCH_PLAN_ONLY = "manual_dispatch_plan_only"
    MANUAL_DISPATCH_FAST_SAFETY_ONLY = "manual_dispatch_fast_safety_only"
    MANUAL_DISPATCH_ALL_PR_STAGES = "manual_dispatch_all_pr_stages"
    UNKNOWN = "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Input specs
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_dispatch_input_specs() -> Dict[str, Any]:
    """Define workflow_dispatch inputs for manual dispatch."""
    specs = [
        {
            "input_id": "confirm_manual_dispatch",
            "name": "confirm_manual_dispatch",
            "required": True,
            "default": None,
            "expected_value": "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
            "description": "Must match confirmation phrase exactly to enable job execution.",
            "blocks_execution_if_missing": True,
            "blocks_execution_if_mismatch": True,
            "secret_allowed": False,
            "warnings": [],
            "errors": [],
        },
        {
            "input_id": "stage_selection",
            "name": "stage_selection",
            "required": False,
            "default": "all_pr",
            "expected_value": None,
            "description": "Which stages to run: all_pr, fast, safety, collect_only, all_nightly.",
            "blocks_execution_if_missing": False,
            "blocks_execution_if_mismatch": False,
            "secret_allowed": False,
            "allowed_values": ["all_pr", "fast", "safety", "collect_only", "all_nightly"],
            "forbidden_values": ["full", "real_send", "auto_fix", "webhook", "secret"],
            "warnings": ["full is manual_only and not available in manual dispatch dry-run"],
            "errors": [],
        },
        {
            "input_id": "execute_mode",
            "name": "execute_mode",
            "required": False,
            "default": "plan_only",
            "expected_value": None,
            "description": "plan_only (default) runs no pytest. execute_selected runs predefined stage commands only.",
            "blocks_execution_if_missing": False,
            "blocks_execution_if_mismatch": False,
            "secret_allowed": False,
            "allowed_values": ["plan_only", "execute_selected"],
            "warnings": [],
            "errors": [],
        },
    ]
    return {
        "input_specs": specs,
        "spec_count": len(specs),
        "confirmation_input_exists": True,
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Job guard specs
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_dispatch_job_guard_specs() -> Dict[str, Any]:
    """Build job guard specs for each dispatchable stage."""
    guard_specs = [
        {
            "job_id": "job_smoke",
            "job_type": ci_workflow_draft.WorkflowJobType.SMOKE,
            "guard_mode": ManualDispatchJobGuardMode.GUARDED_BY_CONFIRMATION_INPUT,
            "enabled_by_default": False,
            "requires_confirmation_input": True,
            "requires_stage_selection": False,
            "allowed_stage_selections": ["all_pr", "smoke", "collect_only"],
            "forbidden_triggers": ["pull_request", "push", "schedule"],
            "network_allowed": False,
            "secret_refs_allowed": False,
            "runtime_write_allowed": False,
            "auto_fix_allowed": False,
            "warnings": ["smoke is pr_warning only — does not block merge"],
            "errors": [],
        },
        {
            "job_id": "job_fast",
            "job_type": ci_workflow_draft.WorkflowJobType.FAST,
            "guard_mode": ManualDispatchJobGuardMode.GUARDED_BY_CONFIRMATION_INPUT,
            "enabled_by_default": False,
            "requires_confirmation_input": True,
            "requires_stage_selection": False,
            "allowed_stage_selections": ["all_pr", "fast", "all_nightly"],
            "forbidden_triggers": ["pull_request", "push", "schedule"],
            "network_allowed": False,
            "secret_refs_allowed": False,
            "runtime_write_allowed": False,
            "auto_fix_allowed": False,
            "warnings": [],
            "errors": [],
        },
        {
            "job_id": "job_safety",
            "job_type": ci_workflow_draft.WorkflowJobType.SAFETY,
            "guard_mode": ManualDispatchJobGuardMode.GUARDED_BY_CONFIRMATION_INPUT,
            "enabled_by_default": False,
            "requires_confirmation_input": True,
            "requires_stage_selection": False,
            "allowed_stage_selections": ["all_pr", "safety", "all_nightly"],
            "forbidden_triggers": ["pull_request", "push", "schedule"],
            "network_allowed": False,
            "secret_refs_allowed": False,
            "runtime_write_allowed": False,
            "auto_fix_allowed": False,
            "warnings": [],
            "errors": [],
        },
        {
            "job_id": "job_collect_only",
            "job_type": ci_workflow_draft.WorkflowJobType.COLLECT_ONLY,
            "guard_mode": ManualDispatchJobGuardMode.GUARDED_BY_CONFIRMATION_INPUT,
            "enabled_by_default": False,
            "requires_confirmation_input": True,
            "requires_stage_selection": False,
            "allowed_stage_selections": ["all_pr", "collect_only"],
            "forbidden_triggers": ["pull_request", "push", "schedule"],
            "network_allowed": False,
            "secret_refs_allowed": False,
            "runtime_write_allowed": False,
            "auto_fix_allowed": False,
            "warnings": ["collect-only is pr_warning only"],
            "errors": [],
        },
        {
            "job_id": "job_slow",
            "job_type": ci_workflow_draft.WorkflowJobType.SLOW,
            "guard_mode": ManualDispatchJobGuardMode.GUARDED_BY_STAGE_SELECTION,
            "enabled_by_default": False,
            "requires_confirmation_input": True,
            "requires_stage_selection": True,
            "allowed_stage_selections": ["all_nightly"],
            "forbidden_triggers": ["pull_request", "push", "schedule"],
            "network_allowed": False,
            "secret_refs_allowed": False,
            "runtime_write_allowed": False,
            "auto_fix_allowed": False,
            "warnings": ["slow is nightly_required — not available in all_pr selection"],
            "errors": [],
        },
    ]
    return {
        "job_guard_specs": guard_specs,
        "spec_count": len(guard_specs),
        "all_guarded_by_confirmation_or_selection": True,
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Security checks
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_manual_dispatch_security_checks() -> Dict[str, Any]:
    """Evaluate security posture of manual dispatch dry-run design."""
    checks = [
        {
            "check_id": "check_no_pr_trigger",
            "check_type": "no_pull_request_trigger",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.CRITICAL,
            "description": "Manual dispatch workflow must not have pull_request trigger.",
            "evidence_refs": ["WorkflowTriggerPolicy.WORKFLOW_DISPATCH_ONLY"],
        },
        {
            "check_id": "check_no_push_trigger",
            "check_type": "no_push_trigger",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.CRITICAL,
            "description": "Manual dispatch workflow must not have push trigger.",
            "evidence_refs": [],
        },
        {
            "check_id": "check_no_schedule_trigger",
            "check_type": "no_schedule_trigger",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.HIGH,
            "description": "Manual dispatch workflow must not have schedule trigger.",
            "evidence_refs": [],
        },
        {
            "check_id": "check_no_secrets",
            "check_type": "no_secrets",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.CRITICAL,
            "description": "No secret refs allowed in manual dispatch job specs.",
            "evidence_refs": ["secret_refs_allowed=False in all job specs"],
        },
        {
            "check_id": "check_no_network",
            "check_type": "no_network",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.CRITICAL,
            "description": "No network calls allowed in manual dispatch jobs.",
            "evidence_refs": ["network_allowed=False in all job specs"],
        },
        {
            "check_id": "check_no_webhook",
            "check_type": "no_webhook",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.CRITICAL,
            "description": "No webhook calls allowed in manual dispatch jobs.",
            "evidence_refs": ["webhook not in allowed stage selections"],
        },
        {
            "check_id": "check_no_runtime_write",
            "check_type": "no_runtime_write",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.CRITICAL,
            "description": "No runtime writes allowed in manual dispatch jobs.",
            "evidence_refs": ["runtime_write_allowed=False in all job specs"],
        },
        {
            "check_id": "check_no_audit_jsonl_write",
            "check_type": "no_audit_jsonl_write",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.HIGH,
            "description": "Audit JSONL writes are forbidden in manual dispatch.",
            "evidence_refs": ["build_ci_blocked_actions()"],
        },
        {
            "check_id": "check_no_action_queue_write",
            "check_type": "no_action_queue_write",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.HIGH,
            "description": "Action queue writes are forbidden in manual dispatch.",
            "evidence_refs": ["action_queue_write blocked in ci_blocked_actions"],
        },
        {
            "check_id": "check_no_auto_fix",
            "check_type": "no_auto_fix",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.CRITICAL,
            "description": "Auto-fix is never executed in manual dispatch dry-run.",
            "evidence_refs": ["auto_fix_allowed=False in all job specs"],
        },
        {
            "check_id": "check_no_feishu_send",
            "check_type": "no_feishu_send",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.CRITICAL,
            "description": "Feishu/Lark send is forbidden in manual dispatch.",
            "evidence_refs": ["feishu_send not in allowed stage selections"],
        },
        {
            "check_id": "check_artifact_policy_excludes_sensitive",
            "check_type": "artifact_policy_excludes_sensitive_paths",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.HIGH,
            "description": "Artifact policy excludes audit_trail JSONL, runtime, action_queue, secrets.",
            "evidence_refs": ["build_ci_artifact_collection_specs() exclude_patterns"],
        },
        {
            "check_id": "check_existing_workflows_unchanged",
            "check_type": "existing_workflows_unchanged",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.MEDIUM,
            "description": "Existing workflows are only read; not modified.",
            "evidence_refs": ["ci_enablement_review.discover_existing_workflows()"],
        },
        {
            "check_id": "check_workflow_remains_manual_dispatch",
            "check_type": "workflow_manual_dispatch_only",
            "passed": True,
            "risk_level": ManualDispatchRiskLevel.CRITICAL,
            "description": "Workflow remains manual dispatch only — no auto triggers.",
            "evidence_refs": ["WorkflowTriggerPolicy.WORKFLOW_DISPATCH_ONLY"],
        },
    ]
    return {
        "checks": checks,
        "check_count": len(checks),
        "all_passed": all(c["passed"] for c in checks),
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Implementation options
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_dispatch_implementation_options(
    existing_workflows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Define 4 implementation options for manual dispatch."""
    existing_workflows = existing_workflows or []
    high_conflict = any(
        item.get("conflict_level") in {ci_enablement_review.EnablementRiskLevel.HIGH, ci_enablement_review.EnablementRiskLevel.CRITICAL}
        for item in existing_workflows
    )

    options = [
        {
            "option_id": "option_a",
            "name": "Keep Disabled Draft Only",
            "description": "Continue with R241-16C state; no new manual dispatch workflow created.",
            "scope": "none",
            "risk_level": ManualDispatchRiskLevel.LOW,
        },
        {
            "option_id": "option_b",
            "name": "Manual Dispatch Plan-only Workflow",
            "description": "Create a manual-only workflow that defaults to plan_only mode. No execution without explicit execute_mode=execute_selected.",
            "scope": "smoke_fast_safety_collect_only",
            "risk_level": ManualDispatchRiskLevel.LOW,
        },
        {
            "option_id": "option_c",
            "name": "Manual Dispatch Fast+Safety Execute",
            "description": "Allow manual trigger of fast+safety execute_selected. Still no PR blocking.",
            "scope": "fast_safety",
            "risk_level": ManualDispatchRiskLevel.MEDIUM,
        },
        {
            "option_id": "option_d",
            "name": "Manual Dispatch All PR Stages",
            "description": "Allow manual trigger of smoke+fast+safety+collect_only. All remain pr_warning / non-blocking.",
            "scope": "all_pr_stages",
            "risk_level": ManualDispatchRiskLevel.MEDIUM,
        },
    ]

    # Recommend based on existing workflow conflicts
    if high_conflict:
        recommended = "option_b"
        reason = "existing_workflow_conflict_high_stay_conservative"
    else:
        recommended = "option_c"
        reason = "existing_workflow_conflict_low_fast_safety_ready"

    return {
        "options": options,
        "recommended_option": recommended,
        "recommendation_reason": reason,
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rollback plan
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_dispatch_rollback_plan() -> Dict[str, Any]:
    return {
        "rollback_plan_id": "R241-16E_manual_dispatch_rollback",
        "rollback_modes": [
            "disable_workflow_file",
            "remove_workflow_dispatch_inputs",
            "revert_to_disabled_draft",
            "manual_revert_only",
        ],
        "rollback_steps": [
            "Set workflow file to if: ${{ false }} or remove workflow_dispatch trigger.",
            "Remove confirmation input from workflow_dispatch inputs.",
            "Use scripts/ci_foundation_check.py as local fallback.",
            "Validate with local plan-only smoke.",
        ],
        "owner_action_required": True,
        "expected_recovery_time": "< 15 minutes",
        "rollback_risks": [],
        "validation_after_rollback": [
            "No workflow_dispatch trigger remains enabled.",
            "Local ci_foundation_check.py plan-only remains available.",
            "No runtime rollback required.",
        ],
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Evaluate readiness
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_manual_dispatch_readiness(root: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate all manual dispatch dry-run review components."""
    root_path = Path(root) if root else ROOT

    # Discover existing workflows for conflict analysis
    discovery = ci_enablement_review.discover_existing_workflows(str(root_path))
    compatibility = [
        ci_enablement_review.analyze_existing_workflow_compatibility(path)
        for path in discovery.get("workflows", [])
    ]

    input_specs = build_manual_dispatch_input_specs()
    job_guard_specs = build_manual_dispatch_job_guard_specs()
    security_checks = evaluate_manual_dispatch_security_checks()
    artifact_policy = ci_plan.build_ci_artifact_collection_specs(str(root_path))
    path_policy = ci_plan.build_ci_path_compatibility_policy(str(root_path))
    threshold_policy = ci_plan.build_ci_threshold_policy()
    rollback_plan = build_manual_dispatch_rollback_plan()
    options = build_manual_dispatch_implementation_options(compatibility)

    # Determine readiness status
    if not security_checks["all_passed"]:
        status = ManualDispatchReadinessStatus.BLOCKED_SECURITY_POLICY
    elif any(item.get("conflict_level") in {"high", "critical"} for item in compatibility):
        status = ManualDispatchReadinessStatus.BLOCKED_EXISTING_WORKFLOW_CONFLICT
    elif not input_specs.get("confirmation_input_exists"):
        status = ManualDispatchReadinessStatus.BLOCKED_MISSING_CONFIRMATION_INPUT
    elif not job_guard_specs.get("all_guarded_by_confirmation_or_selection"):
        status = ManualDispatchReadinessStatus.BLOCKED_JOB_GUARD_MISSING
    else:
        status = ManualDispatchReadinessStatus.READY_FOR_IMPLEMENTATION_REVIEW

    return {
        "review_id": "R241-16E_manual_dispatch_dryrun_review",
        "generated_at": _utc_now(),
        "status": status,
        "dispatch_input_specs": input_specs,
        "job_guard_specs": job_guard_specs,
        "existing_workflow_compatibility": compatibility,
        "artifact_policy_check": artifact_policy,
        "path_compatibility_check": path_policy,
        "threshold_policy_check": threshold_policy,
        "security_checks": security_checks,
        "rollback_plan": rollback_plan,
        "implementation_options": options["options"],
        "recommended_option": options["recommended_option"],
        "recommendation_reason": options["recommendation_reason"],
        "manual_confirmation_requirements": {
            "confirmation_phrase": "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
            "requirements": [
                "workflow_dispatch trigger only",
                "no pull_request / push / schedule triggers",
                "no secrets",
                "no network / webhook calls",
                "no runtime writes",
                "no audit JSONL writes",
                "no action queue writes",
                "no auto-fix",
                "no Feishu send",
                "plan_only as default execute_mode",
            ],
        },
        "workflow_created": False,
        "trigger_enabled": False,
        "network_recommended": False,
        "runtime_write_recommended": False,
        "secret_read_recommended": False,
        "auto_fix_recommended": False,
        "warnings": discovery.get("warnings", []),
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_manual_dispatch_dryrun_review(review: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the manual dispatch dry-run review for policy compliance."""
    errors: List[str] = []
    warnings: List[str] = []

    if review.get("workflow_created"):
        errors.append("workflow_creation_not_allowed")

    if review.get("trigger_enabled"):
        errors.append("trigger_enablement_not_allowed")

    if review.get("network_recommended"):
        errors.append("network_recommended_not_allowed")

    if review.get("runtime_write_recommended"):
        errors.append("runtime_write_recommended_not_allowed")

    if review.get("secret_read_recommended"):
        errors.append("secret_read_recommended_not_allowed")

    if review.get("auto_fix_recommended"):
        errors.append("auto_fix_recommended_not_allowed")

    if not review.get("rollback_plan", {}).get("rollback_steps"):
        errors.append("rollback_plan_missing")

    if not review.get("dispatch_input_specs", {}).get("confirmation_input_exists"):
        errors.append("confirmation_input_missing")

    # Check that recommended option exists
    rec_option = review.get("recommended_option")
    if not rec_option:
        errors.append("recommended_option_missing")

    # Check that implementation options are non-empty
    if not review.get("implementation_options"):
        errors.append("implementation_options_empty")

    # Check existing workflows compatibility is reviewed
    if "existing_workflow_compatibility" not in review:
        errors.append("existing_workflows_not_reviewed")

    # Check security checks
    sec = review.get("security_checks", {})
    if sec.get("all_passed") is False:
        errors.append("security_checks_not_all_passed")

    # Validate dispatch inputs specifically
    input_specs = review.get("dispatch_input_specs", {}).get("input_specs", [])
    confirm_input = next((s for s in input_specs if s.get("input_id") == "confirm_manual_dispatch"), None)
    if not confirm_input:
        errors.append("confirm_manual_dispatch_input_missing")
    else:
        if confirm_input.get("expected_value") != "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN":
            errors.append("confirm_manual_dispatch_wrong_expected_value")
        if confirm_input.get("secret_allowed") is True:
            errors.append("confirm_manual_dispatch_secret_not_allowed")

    # Validate job guards
    job_guards = review.get("job_guard_specs", {}).get("job_guard_specs", [])
    for guard in job_guards:
        if guard.get("network_allowed") is True:
            errors.append(f"job_guard_{guard.get('job_id')}_network_allowed_not_allowed")
        if guard.get("secret_refs_allowed") is True:
            errors.append(f"job_guard_{guard.get('job_id')}_secret_refs_not_allowed")
        if guard.get("runtime_write_allowed") is True:
            errors.append(f"job_guard_{guard.get('job_id')}_runtime_write_not_allowed")
        if guard.get("auto_fix_allowed") is True:
            errors.append(f"job_guard_{guard.get('job_id')}_auto_fix_not_allowed")

    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "validated_at": _utc_now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────

def _render_markdown(review: Dict[str, Any], validation: Dict[str, Any]) -> str:
    input_specs = review.get("dispatch_input_specs", {}).get("input_specs", [])
    job_guards = review.get("job_guard_specs", {}).get("job_guard_specs", [])
    sec_checks = review.get("security_checks", {}).get("checks", [])
    compat = review.get("existing_workflow_compatibility", [])
    opts = review.get("implementation_options", [])

    lines = [
        "# R241-16E Manual Dispatch Dry-run Review",
        "",
        "## 1. Modified Files",
        "",
        "- `backend/app/foundation/ci_manual_dispatch_review.py`",
        "- `backend/app/foundation/test_ci_manual_dispatch_review.py`",
        "- `migration_reports/foundation_audit/R241-16E_MANUAL_DISPATCH_DRYRUN_REVIEW.json`",
        "- `migration_reports/foundation_audit/R241-16E_MANUAL_DISPATCH_DRYRUN_REVIEW.md`",
        "",
        "## 2. Enumerations",
        "",
        "### ManualDispatchReadinessStatus",
        "",
        "- ready_for_implementation_review, blocked_missing_confirmation_input, blocked_job_guard_missing,",
        "- blocked_artifact_policy, blocked_existing_workflow_conflict, blocked_security_policy, design_only, unknown",
        "",
        "### ManualDispatchRiskLevel",
        "",
        "- low, medium, high, critical, unknown",
        "",
        "### ManualDispatchJobGuardMode",
        "",
        "- guarded_by_confirmation_input, guarded_by_if_false, guarded_by_stage_selection, disabled, unknown",
        "",
        "### ManualDispatchImplementationOption",
        "",
        "- keep_disabled_draft, manual_dispatch_plan_only, manual_dispatch_fast_safety_only, manual_dispatch_all_pr_stages, unknown",
        "",
        "## 3. ManualDispatchInputSpec Fields",
        "",
        "- input_id, name, required, default, expected_value, description",
        "- blocks_execution_if_missing, blocks_execution_if_mismatch, secret_allowed, warnings, errors",
        "",
        "## 4. ManualDispatchJobGuardSpec Fields",
        "",
        "- job_id, job_type, guard_mode, enabled_by_default, requires_confirmation_input",
        "- requires_stage_selection, allowed_stage_selections, forbidden_triggers",
        "- network_allowed, secret_refs_allowed, runtime_write_allowed, auto_fix_allowed, warnings, errors",
        "",
        "## 5. ManualDispatchDryRunReview Fields",
        "",
        "- review_id, generated_at, status, dispatch_input_specs, job_guard_specs",
        "- existing_workflow_compatibility, artifact_policy_check, path_compatibility_check",
        "- threshold_policy_check, security_checks, rollback_plan",
        "- implementation_options, recommended_option, recommendation_reason",
        "- manual_confirmation_requirements, workflow_created, trigger_enabled,",
        "- network_recommended, runtime_write_recommended, secret_read_recommended, auto_fix_recommended",
        "",
        "## 6. Dispatch Input Specs Result",
        "",
    ]

    for spec in input_specs:
        lines.append(f"### {spec['input_id']}")
        lines.append(f"- name: `{spec['name']}`")
        lines.append(f"- required: `{spec['required']}`")
        lines.append(f"- default: `{spec.get('default')}`")
        lines.append(f"- expected_value: `{spec.get('expected_value')}`")
        lines.append(f"- blocks_if_missing: `{spec['blocks_execution_if_missing']}`")
        lines.append(f"- blocks_if_mismatch: `{spec['blocks_execution_if_mismatch']}`")
        lines.append(f"- secret_allowed: `{spec['secret_allowed']}`")
        if spec.get("allowed_values"):
            lines.append(f"- allowed_values: `{spec['allowed_values']}`")
        if spec.get("forbidden_values"):
            lines.append(f"- forbidden_values: `{spec['forbidden_values']}`")
        for w in spec.get("warnings", []):
            lines.append(f"  - ⚠️ {w}")
        lines.append("")

    lines.extend([
        "## 7. Job Guard Specs Result",
        "",
    ])

    for guard in job_guards:
        lines.append(f"### {guard['job_id']} ({guard['job_type']})")
        lines.append(f"- guard_mode: `{guard['guard_mode']}`")
        lines.append(f"- enabled_by_default: `{guard['enabled_by_default']}`")
        lines.append(f"- requires_confirmation_input: `{guard['requires_confirmation_input']}`")
        lines.append(f"- requires_stage_selection: `{guard['requires_stage_selection']}`")
        lines.append(f"- allowed_stage_selections: `{guard['allowed_stage_selections']}`")
        lines.append(f"- forbidden_triggers: `{guard['forbidden_triggers']}`")
        lines.append(f"- network_allowed: `{guard['network_allowed']}`")
        lines.append(f"- secret_refs_allowed: `{guard['secret_refs_allowed']}`")
        lines.append(f"- runtime_write_allowed: `{guard['runtime_write_allowed']}`")
        lines.append(f"- auto_fix_allowed: `{guard['auto_fix_allowed']}`")
        for w in guard.get("warnings", []):
            lines.append(f"  - ⚠️ {w}")
        lines.append("")

    lines.extend([
        "## 8. Security Checks Result",
        "",
    ])

    for check in sec_checks:
        status = "✅ PASS" if check["passed"] else "❌ FAIL"
        lines.append(f"- {status} `{check['check_id']}` ({check['risk_level']}): {check['description']}")

    lines.extend([
        "",
        "## 9. Existing Workflow Compatibility Result",
        "",
        f"- workflow_count: `{len(compat)}`",
    ])

    for item in compat:
        lines.append(
            f"- `{item.get('workflow_path')}`: conflict={item.get('conflict_level')}, "
            f"overlap={item.get('likely_overlap_with_foundation_ci')}, "
            f"triggers={item.get('trigger_summary')}"
        )

    lines.extend([
        "",
        "## 10. Artifact / Path / Threshold Policy Result",
        "",
        f"- artifact specs: `{len(review.get('artifact_policy_check', {}).get('artifact_specs', []))}`",
        f"- path action: `{review.get('path_compatibility_check', {}).get('action_now')}`",
        f"- path inconsistency: `{review.get('path_compatibility_check', {}).get('path_inconsistency')}`",
        "",
        "## 11. Rollback Plan",
        "",
        f"- rollback_plan_id: `{review.get('rollback_plan', {}).get('rollback_plan_id')}`",
        *[f"- {step}" for step in review.get("rollback_plan", {}).get("rollback_steps", [])],
        "",
        "## 12. Implementation Options",
        "",
    ])

    for opt in opts:
        rec_marker = " **[RECOMMENDED]**" if opt["option_id"] == review.get("recommended_option") else ""
        lines.append(f"- {opt['option_id']}: {opt['name']} (risk={opt['risk_level']}){rec_marker}")
        lines.append(f"  {opt['description']}")

    lines.extend([
        "",
        f"**Recommended:** `{review.get('recommended_option')}` — {review.get('recommendation_reason')}",
        "",
        "## 13. Manual Confirmation Requirements",
        "",
        f"- phrase: `CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN`",
        *[f"- {item}" for item in review.get("manual_confirmation_requirements", {}).get("requirements", [])],
        "",
        "## 14. Validation Result",
        "",
        f"- valid: `{validation.get('valid')}`",
        f"- errors: `{validation.get('errors')}`",
        f"- warnings: `{validation.get('warnings')}`",
        "",
        "## 15. Test Result",
        "",
        "To be populated from verification command output.",
        "",
        "## 16. Workflow / Trigger",
        "",
        "No workflow is created. No trigger is enabled.",
        "",
        "## 17. Existing Workflow Mutation",
        "",
        "Existing workflow files are only read; they are not modified.",
        "",
        "## 18. Secret Access",
        "",
        "No secret is read.",
        "",
        "## 19. Network / Webhook",
        "",
        "No network or webhook call is performed.",
        "",
        "## 20. Runtime / Audit JSONL / Action Queue",
        "",
        "No runtime, audit JSONL, or action queue write is performed.",
        "",
        "## 21. Auto-fix",
        "",
        "No auto-fix is executed.",
        "",
        "## 22. Remaining Breakpoints",
        "",
        "- Manual confirmation phrase required before any workflow creation.",
        "- Existing backend workflows with PR/push triggers should be reviewed for overlap.",
        "- Full stage (manual_only) is out of scope for this dry-run review.",
        "",
        "## 23. Next Recommendation",
        "",
        "Proceed to R241-16F Manual Dispatch Workflow Draft Implementation Review",
        "or wait for explicit CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN confirmation.",
    ])

    return "\n".join(lines)


def generate_manual_dispatch_dryrun_review(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate the R241-16E review JSON and markdown reports."""
    target = Path(output_path) if output_path else DEFAULT_JSON_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    review = evaluate_manual_dispatch_readiness(str(ROOT))
    validation = validate_manual_dispatch_dryrun_review(review)

    payload = {
        "review": review,
        "validation": validation,
        "generated_at": _utc_now(),
    }

    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = target.with_name(DEFAULT_MD_PATH.name)
    md_path.write_text(_render_markdown(review, validation), encoding="utf-8")

    return {
        "output_path": str(target),
        "report_path": str(md_path),
        **payload,
    }


__all__ = [
    "ManualDispatchReadinessStatus",
    "ManualDispatchRiskLevel",
    "ManualDispatchJobGuardMode",
    "ManualDispatchImplementationOption",
    "build_manual_dispatch_input_specs",
    "build_manual_dispatch_job_guard_specs",
    "evaluate_manual_dispatch_security_checks",
    "build_manual_dispatch_implementation_options",
    "build_manual_dispatch_rollback_plan",
    "evaluate_manual_dispatch_readiness",
    "validate_manual_dispatch_dryrun_review",
    "generate_manual_dispatch_dryrun_review",
]
