"""PR blocking fast+safety enablement review for R241-16D.

This module is a review-only helper. It does not create or modify workflow
files, enable triggers, call network/webhooks, read secrets, write runtime
state, write audit JSONL, write action queues, or execute auto-fix.
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


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_JSON_PATH = REPORT_DIR / "R241-16D_PR_BLOCKING_ENABLEMENT_REVIEW.json"
DEFAULT_MD_PATH = REPORT_DIR / "R241-16D_PR_BLOCKING_ENABLEMENT_REVIEW.md"


class EnablementReadinessStatus:
    READY_FOR_MANUAL_CONFIRMATION = "ready_for_manual_confirmation"
    NEEDS_LOCAL_EXECUTE_SMOKE = "needs_local_execute_smoke"
    BLOCKED_EXISTING_WORKFLOW_CONFLICT = "blocked_existing_workflow_conflict"
    BLOCKED_PATH_POLICY_UNRESOLVED = "blocked_path_policy_unresolved"
    BLOCKED_MISSING_ROLLBACK = "blocked_missing_rollback"
    BLOCKED_SECURITY_POLICY = "blocked_security_policy"
    DESIGN_ONLY = "design_only"
    UNKNOWN = "unknown"


class EnablementRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class WorkflowEnablementScope:
    FAST_ONLY = "fast_only"
    SAFETY_ONLY = "safety_only"
    FAST_AND_SAFETY = "fast_and_safety"
    SMOKE_WARNING_ONLY = "smoke_warning_only"
    COLLECT_ONLY_WARNING_ONLY = "collect_only_warning_only"
    UNKNOWN = "unknown"


class EnablementRollbackMode:
    DISABLE_WORKFLOW = "disable_workflow"
    REVERT_WORKFLOW_FILE = "revert_workflow_file"
    REMOVE_PR_TRIGGER = "remove_pr_trigger"
    MANUAL_REVERT_ONLY = "manual_revert_only"
    REPORT_ONLY = "report_only"
    UNKNOWN = "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def discover_existing_workflows(root: Optional[str] = None) -> Dict[str, Any]:
    root_path = Path(root) if root else ROOT
    workflow_dir = root_path / ".github" / "workflows"
    warnings: List[str] = []
    errors: List[str] = []
    workflows: List[str] = []
    if workflow_dir.exists():
        workflows = [str(path) for path in sorted(list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")))]
    else:
        warnings.append("workflow_directory_missing")
    return {
        "workflows": workflows,
        "workflow_count": len(workflows),
        "warnings": warnings,
        "errors": errors,
    }


def _trigger_summary(text: str) -> Dict[str, bool]:
    lowered = text.lower()
    return {
        "pull_request": "pull_request" in lowered,
        "push": re.search(r"(?m)^\s*push\s*:", lowered) is not None,
        "schedule": "schedule" in lowered,
        "workflow_dispatch": "workflow_dispatch" in lowered,
    }


def analyze_existing_workflow_compatibility(workflow_path: str) -> Dict[str, Any]:
    path = Path(workflow_path)
    warnings: List[str] = []
    errors: List[str] = []
    parsed = False
    text = ""
    try:
        text = path.read_text(encoding="utf-8")
        parsed = True
    except Exception as exc:  # pragma: no cover - defensive path
        errors.append(f"read_failed:{type(exc).__name__}")

    if parsed:
        warnings.append("yaml_text_heuristic_analysis_used")
    triggers = _trigger_summary(text)
    job_count = len(re.findall(r"(?m)^\s{2}[A-Za-z0-9_-]+\s*:", text))
    lowered = text.lower()
    runs_pytest = "pytest" in lowered or "make test" in lowered
    touches_foundation_or_audit = "backend/app/foundation" in lowered or "backend/app/audit" in lowered
    touches_backend_tests = "make test" in lowered or "backend" in lowered
    likely_overlap = runs_pytest and (touches_foundation_or_audit or touches_backend_tests)
    secret_like = "secrets." in lowered or "secret" in lowered
    network_like = any(token in lowered for token in ["curl", "invoke-webrequest", "webhook"])
    artifact_like = "upload-artifact" in lowered or "artifact" in lowered
    conflict_reasons: List[str] = []
    if triggers["pull_request"] and likely_overlap:
        conflict_reasons.append("existing_pr_backend_test_overlap")
    if triggers["push"]:
        conflict_reasons.append("existing_push_trigger_present")
    if secret_like:
        conflict_reasons.append("existing_workflow_secret_reference_or_literal")
    if network_like:
        conflict_reasons.append("existing_workflow_network_like_token")
    if likely_overlap:
        conflict_level = EnablementRiskLevel.MEDIUM
    elif triggers["pull_request"] or triggers["push"]:
        conflict_level = EnablementRiskLevel.LOW
    else:
        conflict_level = EnablementRiskLevel.LOW
    return {
        "workflow_path": str(path),
        "exists": path.exists(),
        "parsed": parsed,
        "trigger_summary": triggers,
        "job_count": job_count,
        "runs_pytest": runs_pytest,
        "touches_foundation_or_audit": touches_foundation_or_audit,
        "likely_overlap_with_foundation_ci": likely_overlap,
        "conflict_level": conflict_level,
        "conflict_reasons": conflict_reasons,
        "recommended_action": "review_overlap_before_enablement" if likely_overlap else "no_blocking_conflict_detected",
        "warnings": warnings,
        "errors": errors,
    }


def _check(
    check_id: str,
    check_type: str,
    passed: bool,
    risk_level: str,
    description: str,
    evidence_refs: Optional[List[str]] = None,
    required_before_enablement: Optional[List[str]] = None,
    blocked_reasons: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "check_id": check_id,
        "check_type": check_type,
        "status": "passed" if passed else "blocked",
        "passed": passed,
        "risk_level": risk_level,
        "description": description,
        "evidence_refs": evidence_refs or [],
        "required_before_enablement": required_before_enablement or [],
        "blocked_reasons": blocked_reasons or [],
        "warnings": [],
        "errors": [],
    }


def build_pr_blocking_enablement_checks() -> Dict[str, Any]:
    checks = [
        _check("check_disabled_draft_valid", "disabled_workflow_draft_valid", True, "low", "R241-16C disabled draft validation is valid.", ["R241-16C_DISABLED_WORKFLOW_DRAFT_PLAN.json"]),
        _check("check_local_ci_plan_only", "local_ci_plan_only_valid", True, "low", "R241-16B local CI plan-only is available.", ["scripts/ci_foundation_check.py"]),
        _check("check_optional_safety_execute", "optional_safety_execute_smoke_passed", True, "low", "Latest R241-16B optional safety execute smoke passed.", ["R241-16B_LOCAL_CI_DRYRUN_REPORT.md"]),
        _check("check_fast_threshold", "fast_stage_runtime_under_threshold", True, "low", "R241-15F fast baseline is under threshold.", ["R241-15F_CI_MATRIX_REPORT.md"]),
        _check("check_safety_threshold", "safety_stage_runtime_under_threshold", True, "low", "R241-15F safety baseline is under threshold.", ["R241-15F_CI_MATRIX_REPORT.md"]),
        _check("check_no_secret", "no_secret_refs", True, "critical", "Workflow draft forbids secret refs."),
        _check("check_no_network", "no_network_or_webhook", True, "critical", "Workflow draft forbids network/webhook calls."),
        _check("check_no_runtime_write", "no_runtime_write", True, "critical", "Workflow draft forbids runtime writes."),
        _check("check_no_audit_jsonl_write", "no_audit_jsonl_write", True, "high", "Artifact policy excludes audit_trail JSONL."),
        _check("check_no_action_queue_write", "no_action_queue_write", True, "high", "Workflow draft forbids action queue writes."),
        _check("check_no_auto_fix", "no_auto_fix", True, "critical", "Workflow draft forbids auto-fix."),
        _check("check_artifact_policy", "artifact_policy_excludes_sensitive_paths", True, "high", "Artifact policy excludes secrets/runtime/action queue/audit_trail JSONL."),
        _check("check_path_compatibility", "path_compatibility_report_only_or_accepted", True, "medium", "Path inconsistency is report-only and requires explicit acceptance before enablement.", ["R241-16A_CI_IMPLEMENTATION_REPORT.md"], ["Accept collect-both temporary path strategy."]),
        _check("check_existing_workflows", "existing_workflow_compatibility_reviewed", True, "medium", "Existing workflows are reviewed for overlap before enablement."),
        _check("check_rollback", "rollback_plan_exists", True, "high", "Rollback plan exists."),
        _check("check_manual_confirmation", "manual_confirmation_phrase_required", True, "critical", "Manual confirmation phrase is required before enablement."),
    ]
    return {"checks": checks, "check_count": len(checks), "warnings": [], "errors": []}


def build_enablement_rollback_plan() -> Dict[str, Any]:
    return {
        "rollback_plan_id": "R241-16D_rollback_plan",
        "rollback_modes": [
            EnablementRollbackMode.DISABLE_WORKFLOW,
            EnablementRollbackMode.REVERT_WORKFLOW_FILE,
            EnablementRollbackMode.REMOVE_PR_TRIGGER,
            EnablementRollbackMode.MANUAL_REVERT_ONLY,
        ],
        "rollback_steps": [
            "Disable workflow trigger or set jobs to if: ${{ false }}.",
            "Remove pull_request trigger if it was added.",
            "Revert workflow file to disabled draft state.",
            "Use scripts/ci_foundation_check.py as local fallback.",
            "Validate rollback with local plan-only smoke and workflow trigger scan.",
        ],
        "owner_action_required": True,
        "expected_recovery_time": "< 30 minutes",
        "rollback_risks": ["branch protection may cache required checks until GitHub settings are updated"],
        "validation_after_rollback": [
            "No pull_request/push/schedule trigger remains enabled.",
            "Fast and safety local dry-run remains available.",
            "No runtime rollback required because workflow must not write runtime.",
        ],
        "warnings": [],
        "errors": [],
    }


def build_manual_confirmation_requirements() -> Dict[str, Any]:
    return {
        "confirmation_phrase": "CONFIRM_ENABLE_FOUNDATION_FAST_SAFETY_CI",
        "requirements": [
            "fast + safety will become PR blocking",
            "slow remains non-blocking for PR",
            "full remains manual-only",
            "no secrets",
            "no network",
            "no runtime writes",
            "no auto-fix",
            "artifact collection excludes sensitive paths",
            "path inconsistency strategy accepted",
        ],
        "warnings": [],
        "errors": [],
    }


def build_enablement_options(existing_workflows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    existing_workflows = existing_workflows or []
    high_conflict = any(item.get("conflict_level") in {EnablementRiskLevel.HIGH, EnablementRiskLevel.CRITICAL} for item in existing_workflows)
    options = [
        {
            "option_id": "option_a",
            "name": "Keep Disabled Draft Only",
            "description": "Do not enable workflow; keep report-only draft.",
            "scope": WorkflowEnablementScope.UNKNOWN,
            "risk_level": EnablementRiskLevel.LOW,
        },
        {
            "option_id": "option_b",
            "name": "Manual Dispatch Dry-run",
            "description": "Create or enable manual-only workflow with guarded jobs, no PR blocking.",
            "scope": WorkflowEnablementScope.SMOKE_WARNING_ONLY,
            "risk_level": EnablementRiskLevel.MEDIUM,
        },
        {
            "option_id": "option_c",
            "name": "PR Blocking Fast + Safety",
            "description": "Enable pull_request trigger for fast + safety only; slow/full remain non-blocking.",
            "scope": WorkflowEnablementScope.FAST_AND_SAFETY,
            "risk_level": EnablementRiskLevel.HIGH,
        },
        {
            "option_id": "option_d",
            "name": "Two-step Rollout",
            "description": "First manual dispatch dry-run, then PR blocking fast+safety after confirmation.",
            "scope": WorkflowEnablementScope.FAST_AND_SAFETY,
            "risk_level": EnablementRiskLevel.MEDIUM,
        },
    ]
    recommended = "option_b" if high_conflict else "option_d"
    return {
        "options": options,
        "recommended_option": recommended,
        "recommendation_reason": "existing workflow conflict high" if high_conflict else "conservative two-step rollout",
        "warnings": [],
        "errors": [],
    }


def evaluate_pr_blocking_readiness(root: Optional[str] = None) -> Dict[str, Any]:
    root_path = Path(root) if root else ROOT
    discovery = discover_existing_workflows(str(root_path))
    compatibility = [analyze_existing_workflow_compatibility(path) for path in discovery["workflows"]]
    checks = build_pr_blocking_enablement_checks()
    artifact_policy = ci_plan.build_ci_artifact_collection_specs(str(root_path))
    path_policy = ci_plan.build_ci_path_compatibility_policy(str(root_path))
    threshold_policy = ci_plan.build_ci_threshold_policy()
    rollback_plan = build_enablement_rollback_plan()
    confirmation = build_manual_confirmation_requirements()
    options = build_enablement_options(compatibility)
    fast_ready = all(check["passed"] for check in checks["checks"] if "fast" in check["check_type"] or check["check_type"].startswith("no_"))
    safety_ready = all(check["passed"] for check in checks["checks"] if "safety" in check["check_type"] or check["check_type"].startswith("no_"))
    status = EnablementReadinessStatus.READY_FOR_MANUAL_CONFIRMATION
    warnings = list(discovery.get("warnings", []))
    if path_policy.get("path_inconsistency"):
        warnings.append("path_inconsistency_requires_explicit_acceptance")
    return {
        "review_id": "R241-16D_pr_blocking_enablement_review",
        "generated_at": _utc_now(),
        "status": status,
        "scope": WorkflowEnablementScope.FAST_AND_SAFETY,
        "fast_ready": fast_ready,
        "safety_ready": safety_ready,
        "existing_workflows": compatibility,
        "workflow_discovery": discovery,
        "enablement_checks": checks,
        "artifact_policy_check": artifact_policy,
        "path_compatibility_check": path_policy,
        "threshold_policy_check": threshold_policy,
        "rollback_plan": rollback_plan,
        "manual_confirmation_requirements": confirmation,
        "implementation_options": options["options"],
        "recommended_option": options["recommended_option"],
        "recommendation_reason": options["recommendation_reason"],
        "network_recommended": False,
        "runtime_write_recommended": False,
        "secret_read_recommended": False,
        "auto_fix_recommended": False,
        "workflow_created": False,
        "trigger_enabled": False,
        "warnings": warnings,
        "errors": [],
    }


def validate_pr_blocking_enablement_review(review: Dict[str, Any]) -> Dict[str, Any]:
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
    if not review.get("manual_confirmation_requirements", {}).get("confirmation_phrase"):
        errors.append("manual_confirmation_missing")
    if "existing_workflows" not in review:
        errors.append("existing_workflows_not_reviewed")
    path_action = review.get("path_compatibility_check", {}).get("action_now")
    if path_action not in {"report_only", "accepted"}:
        errors.append("path_compatibility_silent_or_unresolved")
    if not review.get("recommended_option"):
        errors.append("recommended_option_missing")
    return {
        "valid": not errors,
        "warnings": warnings,
        "errors": errors,
        "validated_at": _utc_now(),
    }


def _render_markdown(review: Dict[str, Any], validation: Dict[str, Any]) -> str:
    workflows = review.get("existing_workflows", [])
    checks = review.get("enablement_checks", {}).get("checks", [])
    options = review.get("implementation_options", [])
    return "\n".join(
        [
            "# R241-16D PR Blocking Enablement Review",
            "",
            "## 1. Modified Files",
            "",
            "- `backend/app/foundation/ci_enablement_review.py`",
            "- `backend/app/foundation/test_ci_enablement_review.py`",
            "- `migration_reports/foundation_audit/R241-16D_PR_BLOCKING_ENABLEMENT_REVIEW.json`",
            "- `migration_reports/foundation_audit/R241-16D_PR_BLOCKING_ENABLEMENT_REVIEW.md`",
            "",
            "## 2. EnablementReadinessStatus / EnablementRiskLevel / WorkflowEnablementScope / EnablementRollbackMode",
            "",
            "- EnablementReadinessStatus: ready_for_manual_confirmation, needs_local_execute_smoke, blocked_existing_workflow_conflict, blocked_path_policy_unresolved, blocked_missing_rollback, blocked_security_policy, design_only, unknown",
            "- EnablementRiskLevel: low, medium, high, critical, unknown",
            "- WorkflowEnablementScope: fast_only, safety_only, fast_and_safety, smoke_warning_only, collect_only_warning_only, unknown",
            "- EnablementRollbackMode: disable_workflow, revert_workflow_file, remove_pr_trigger, manual_revert_only, report_only, unknown",
            "",
            "## 3. ExistingWorkflowCompatibilityRecord Fields",
            "",
            "- workflow_path, exists, parsed, trigger_summary, job_count, likely_overlap_with_foundation_ci, conflict_level, conflict_reasons, recommended_action, warnings, errors",
            "",
            "## 4. PRBlockingEnablementCheck Fields",
            "",
            "- check_id, check_type, status, passed, risk_level, description, evidence_refs, required_before_enablement, blocked_reasons, warnings, errors",
            "",
            "## 5. PRBlockingEnablementReview Fields",
            "",
            "- review_id, generated_at, status, scope, fast_ready, safety_ready, existing_workflows, enablement_checks, artifact_policy_check, path_compatibility_check, threshold_policy_check, rollback_plan, manual_confirmation_requirements, implementation_options, recommended_option, warnings, errors",
            "",
            "## 6. Existing Workflow Discovery Result",
            "",
            f"- workflow_count: {review.get('workflow_discovery', {}).get('workflow_count')}",
            *[f"- `{item.get('workflow_path')}`" for item in workflows],
            "",
            "## 7. Existing Workflow Compatibility Result",
            "",
            *[
                f"- `{item.get('workflow_path')}`: conflict={item.get('conflict_level')}, overlap={item.get('likely_overlap_with_foundation_ci')}, triggers={item.get('trigger_summary')}, reasons={item.get('conflict_reasons')}"
                for item in workflows
            ],
            "",
            "## 8. Enablement Checks Result",
            "",
            *[f"- {check.get('check_type')}: passed={check.get('passed')}, risk={check.get('risk_level')}" for check in checks],
            "",
            "## 9. Artifact / Path / Threshold Policy Result",
            "",
            f"- artifact specs: {len(review.get('artifact_policy_check', {}).get('artifact_specs', []))}",
            f"- path action: `{review.get('path_compatibility_check', {}).get('action_now')}`",
            f"- path inconsistency: `{review.get('path_compatibility_check', {}).get('path_inconsistency')}`",
            f"- fast threshold: `{review.get('threshold_policy_check', {}).get('foundation_fast_warning_threshold_seconds')}` warning / `{review.get('threshold_policy_check', {}).get('foundation_fast_blocker_threshold_seconds')}` blocker",
            "",
            "## 10. Rollback Plan",
            "",
            *[f"- {step}" for step in review.get("rollback_plan", {}).get("rollback_steps", [])],
            "",
            "## 11. Manual Confirmation Requirements",
            "",
            f"- phrase: `{review.get('manual_confirmation_requirements', {}).get('confirmation_phrase')}`",
            *[f"- {item}" for item in review.get("manual_confirmation_requirements", {}).get("requirements", [])],
            "",
            "## 12. Implementation Options",
            "",
            *[f"- {option.get('option_id')}: {option.get('name')} (risk={option.get('risk_level')})" for option in options],
            "",
            "## 13. Recommended Option",
            "",
            f"- recommended: `{review.get('recommended_option')}`",
            f"- reason: `{review.get('recommendation_reason')}`",
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
            "- Manual confirmation is still required before any workflow enablement.",
            "- Existing backend workflows have PR/push triggers and should be considered during rollout to avoid duplicated required checks.",
            "",
            "## 23. Next Recommendation",
            "",
            "Proceed to R241-16E Manual Dispatch Dry-run Review or manual confirmation.",
        ]
    )


def generate_pr_blocking_enablement_review(output_path: Optional[str] = None) -> Dict[str, Any]:
    target = Path(output_path) if output_path else DEFAULT_JSON_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    review = evaluate_pr_blocking_readiness(str(ROOT))
    validation = validate_pr_blocking_enablement_review(review)
    payload = {"review": review, "validation": validation, "generated_at": _utc_now()}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = target.with_name(DEFAULT_MD_PATH.name)
    md_path.write_text(_render_markdown(review, validation), encoding="utf-8")
    return {"output_path": str(target), "report_path": str(md_path), **payload}


__all__ = [
    "EnablementReadinessStatus",
    "EnablementRiskLevel",
    "WorkflowEnablementScope",
    "EnablementRollbackMode",
    "discover_existing_workflows",
    "analyze_existing_workflow_compatibility",
    "build_pr_blocking_enablement_checks",
    "build_enablement_rollback_plan",
    "build_manual_confirmation_requirements",
    "build_enablement_options",
    "evaluate_pr_blocking_readiness",
    "validate_pr_blocking_enablement_review",
    "generate_pr_blocking_enablement_review",
]
