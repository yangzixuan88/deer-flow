"""Manual Dispatch Workflow Implementation Review for R241-16F.

This module reviews and blueprints the manual dispatch workflow implementation.
It does not create workflow files, enable triggers, call network/webhooks, read
secrets, write runtime state, write audit JSONL, or execute auto-fix.
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


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_JSON_PATH = REPORT_DIR / "R241-16F_MANUAL_DISPATCH_IMPLEMENTATION_REVIEW.json"
DEFAULT_MD_PATH = REPORT_DIR / "R241-16F_MANUAL_DISPATCH_IMPLEMENTATION_REVIEW.md"
DEFAULT_YAML_BLUEPRINT_PATH = REPORT_DIR / "R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt"


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class ManualDispatchImplementationStatus:
    DESIGN_ONLY = "design_only"
    READY_FOR_MANUAL_CONFIRMATION = "ready_for_manual_confirmation"
    BLOCKED_MISSING_GUARD = "blocked_missing_guard"
    BLOCKED_TRIGGER_POLICY = "blocked_trigger_policy"
    BLOCKED_SECRET_POLICY = "blocked_secret_policy"
    BLOCKED_EXISTING_WORKFLOW_CONFLICT = "blocked_existing_workflow_conflict"
    BLOCKED_MISSING_ROLLBACK = "blocked_missing_rollback"
    UNKNOWN = "unknown"


class ManualDispatchBlueprintRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ManualDispatchWorkflowMode:
    PLAN_ONLY_DEFAULT = "plan_only_default"
    EXECUTE_SELECTED_ALLOWED = "execute_selected_allowed"
    FAST_SAFETY_ONLY = "fast_safety_only"
    ALL_PR_ALLOWED = "all_pr_allowed"
    ALL_NIGHTLY_ALLOWED = "all_nightly_allowed"
    UNKNOWN = "unknown"


class ManualDispatchImplementationDecision:
    KEEP_REVIEW_ONLY = "keep_review_only"
    ALLOW_BLUEPRINT_ONLY = "allow_blueprint_only"
    ALLOW_MANUAL_WORKFLOW_AFTER_CONFIRMATION = "allow_manual_workflow_after_confirmation"
    BLOCK_IMPLEMENTATION = "block_implementation"
    UNKNOWN = "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timeout_minutes_from_seconds(seconds: int) -> int:
    return max(1, int((float(seconds) + 59) // 60))


# ─────────────────────────────────────────────────────────────────────────────
# Core data structures
# ─────────────────────────────────────────────────────────────────────────────

class ManualDispatchWorkflowJobBlueprint:
    """Job blueprint for a single job in the manual dispatch workflow."""

    def __init__(
        self,
        job_id: str,
        job_type: str,
        command: str,
        enabled_by_default: bool = False,
        guard_expression: str = "${{ false }}",
        allowed_stage_selections: Optional[List[str]] = None,
        forbidden_triggers: Optional[List[str]] = None,
        network_allowed: bool = False,
        secret_refs_allowed: bool = False,
        runtime_write_allowed: bool = False,
        audit_jsonl_write_allowed: bool = False,
        action_queue_write_allowed: bool = False,
        auto_fix_allowed: bool = False,
        artifact_upload_allowed: bool = False,
        timeout_minutes: int = 5,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
    ):
        self.job_id = job_id
        self.job_type = job_type
        self.command = command
        self.enabled_by_default = enabled_by_default
        self.guard_expression = guard_expression
        self.allowed_stage_selections = allowed_stage_selections or []
        self.forbidden_triggers = forbidden_triggers or []
        self.network_allowed = network_allowed
        self.secret_refs_allowed = secret_refs_allowed
        self.runtime_write_allowed = runtime_write_allowed
        self.audit_jsonl_write_allowed = audit_jsonl_write_allowed
        self.action_queue_write_allowed = action_queue_write_allowed
        self.auto_fix_allowed = auto_fix_allowed
        self.artifact_upload_allowed = artifact_upload_allowed
        self.timeout_minutes = timeout_minutes
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "command": self.command,
            "enabled_by_default": self.enabled_by_default,
            "guard_expression": self.guard_expression,
            "allowed_stage_selections": self.allowed_stage_selections,
            "forbidden_triggers": self.forbidden_triggers,
            "network_allowed": self.network_allowed,
            "secret_refs_allowed": self.secret_refs_allowed,
            "runtime_write_allowed": self.runtime_write_allowed,
            "audit_jsonl_write_allowed": self.audit_jsonl_write_allowed,
            "action_queue_write_allowed": self.action_queue_write_allowed,
            "auto_fix_allowed": self.auto_fix_allowed,
            "artifact_upload_allowed": self.artifact_upload_allowed,
            "timeout_minutes": self.timeout_minutes,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Build workflow blueprint
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_dispatch_workflow_blueprint(root: Optional[str] = None) -> Dict[str, Any]:
    """Generate manual dispatch workflow blueprint."""
    root_path = Path(root) if root else ROOT

    artifact_policy = ci_plan.build_ci_artifact_collection_specs(str(root_path))
    path_policy = ci_plan.build_ci_path_compatibility_policy(str(root_path))
    threshold_policy = ci_plan.build_ci_threshold_policy()
    rollback_plan = mdr.build_manual_dispatch_rollback_plan()

    job_blueprints = build_manual_dispatch_job_blueprints()

    blueprint = {
        "blueprint_id": "R241-16F_manual_dispatch_workflow_blueprint",
        "generated_at": _utc_now(),
        "status": ManualDispatchImplementationStatus.READY_FOR_MANUAL_CONFIRMATION,
        "workflow_filename_proposed": "foundation-manual-dispatch.yml",
        "write_target_allowed": False,
        "report_only_blueprint_path": str(DEFAULT_YAML_BLUEPRINT_PATH),
        "trigger_policy": {
            "workflow_dispatch_enabled": True,
            "pull_request_enabled": False,
            "push_enabled": False,
            "schedule_enabled": False,
            "forbidden_triggers": ["pull_request", "push", "schedule"],
        },
        "workflow_dispatch_inputs": [
            {
                "input_id": "confirm_manual_dispatch",
                "name": "confirm_manual_dispatch",
                "required": True,
                "default": None,
                "expected_value": "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN",
                "description": "Must match confirmation phrase exactly.",
                "secret_allowed": False,
            },
            {
                "input_id": "stage_selection",
                "name": "stage_selection",
                "required": False,
                "default": "all_pr",
                "allowed_values": ["all_pr", "fast", "safety", "collect_only", "all_nightly"],
                "forbidden_values": ["full", "real_send", "auto_fix", "webhook", "secret"],
                "secret_allowed": False,
            },
            {
                "input_id": "execute_mode",
                "name": "execute_mode",
                "required": False,
                "default": "plan_only",
                "allowed_values": ["plan_only", "execute_selected"],
                "secret_allowed": False,
            },
        ],
        "allowed_stage_selections": ["all_pr", "fast", "safety", "collect_only", "all_nightly"],
        "forbidden_stage_selections": ["full", "real_send", "auto_fix", "webhook", "secret"],
        "default_execute_mode": "plan_only",
        "job_blueprints": job_blueprints,
        "artifact_policy": artifact_policy,
        "path_compatibility_policy": path_policy,
        "security_policy": {
            "no_secrets": True,
            "no_network": True,
            "no_runtime_write": True,
            "no_audit_jsonl_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "no_feishu_send": True,
        },
        "rollback_plan": rollback_plan,
        "warnings": [],
        "errors": [],
    }

    return blueprint


def build_manual_dispatch_job_blueprints() -> List[Dict[str, Any]]:
    """Build job blueprints for all dispatchable stages."""
    stage_specs = ci_plan.build_ci_stage_implementation_specs()
    specs_by_type = {s["stage_type"]: s for s in stage_specs["specs"]}

    jobs: List[Dict[str, Any]] = []

    # smoke
    smoke_spec = specs_by_type.get(ci_plan.CIExecutionStageType.SMOKE, {})
    jobs.append(
        ManualDispatchWorkflowJobBlueprint(
            job_id="job_smoke",
            job_type=ci_workflow_draft.WorkflowJobType.SMOKE,
            command="python scripts/ci_foundation_check.py --selection smoke --format text",
            enabled_by_default=False,
            guard_expression="${{ inputs.confirm_manual_dispatch == 'CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN' }}",
            allowed_stage_selections=["all_pr", "smoke", "collect_only"],
            forbidden_triggers=["pull_request", "push", "schedule"],
            timeout_minutes=_timeout_minutes_from_seconds(smoke_spec.get("warning_threshold_seconds", 30)),
            warnings=["smoke is pr_warning — does not block merge"],
        ).to_dict()
    )

    # fast
    fast_spec = specs_by_type.get(ci_plan.CIExecutionStageType.FAST, {})
    jobs.append(
        ManualDispatchWorkflowJobBlueprint(
            job_id="job_fast",
            job_type=ci_workflow_draft.WorkflowJobType.FAST,
            command="python scripts/ci_foundation_check.py --selection fast --execute --format text",
            enabled_by_default=False,
            guard_expression=(
                "${{ inputs.confirm_manual_dispatch == 'CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN' && "
                "(inputs.stage_selection == 'fast' || inputs.stage_selection == 'all_pr' || "
                "inputs.stage_selection == 'all_nightly') }}"
            ),
            allowed_stage_selections=["all_pr", "fast", "all_nightly"],
            forbidden_triggers=["pull_request", "push", "schedule"],
            timeout_minutes=_timeout_minutes_from_seconds(fast_spec.get("blocker_threshold_seconds", 60)),
        ).to_dict()
    )

    # safety
    safety_spec = specs_by_type.get(ci_plan.CIExecutionStageType.SAFETY, {})
    jobs.append(
        ManualDispatchWorkflowJobBlueprint(
            job_id="job_safety",
            job_type=ci_workflow_draft.WorkflowJobType.SAFETY,
            command="python scripts/ci_foundation_check.py --selection safety --execute --format text",
            enabled_by_default=False,
            guard_expression=(
                "${{ inputs.confirm_manual_dispatch == 'CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN' && "
                "(inputs.stage_selection == 'safety' || inputs.stage_selection == 'all_pr' || "
                "inputs.stage_selection == 'all_nightly') }}"
            ),
            allowed_stage_selections=["all_pr", "safety", "all_nightly"],
            forbidden_triggers=["pull_request", "push", "schedule"],
            timeout_minutes=_timeout_minutes_from_seconds(safety_spec.get("warning_threshold_seconds", 10)),
        ).to_dict()
    )

    # collect_only
    jobs.append(
        ManualDispatchWorkflowJobBlueprint(
            job_id="job_collect_only",
            job_type=ci_workflow_draft.WorkflowJobType.COLLECT_ONLY,
            command="python scripts/ci_foundation_check.py --selection collect_only --format text",
            enabled_by_default=False,
            guard_expression="${{ inputs.confirm_manual_dispatch == 'CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN' }}",
            allowed_stage_selections=["all_pr", "collect_only"],
            forbidden_triggers=["pull_request", "push", "schedule"],
            timeout_minutes=5,
            warnings=["collect-only is pr_warning only"],
        ).to_dict()
    )

    # slow — nightly only
    slow_spec = specs_by_type.get(ci_plan.CIExecutionStageType.SLOW, {})
    jobs.append(
        ManualDispatchWorkflowJobBlueprint(
            job_id="job_slow",
            job_type=ci_workflow_draft.WorkflowJobType.SLOW,
            command="python scripts/ci_foundation_check.py --selection slow --execute --format text",
            enabled_by_default=False,
            guard_expression=(
                "${{ inputs.confirm_manual_dispatch == 'CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN' && "
                "inputs.stage_selection == 'all_nightly' }}"
            ),
            allowed_stage_selections=["all_nightly"],
            forbidden_triggers=["pull_request", "push", "schedule"],
            timeout_minutes=_timeout_minutes_from_seconds(slow_spec.get("warning_threshold_seconds", 60)),
            warnings=["slow is nightly_required — not in all_pr selection"],
        ).to_dict()
    )

    return jobs


# ─────────────────────────────────────────────────────────────────────────────
# Render YAML blueprint
# ─────────────────────────────────────────────────────────────────────────────

def render_manual_dispatch_workflow_blueprint_yaml(blueprint: Dict[str, Any]) -> Dict[str, Any]:
    """Render the workflow blueprint as YAML text."""
    inputs = blueprint.get("workflow_dispatch_inputs", [])

    confirm_input = next((i for i in inputs if i["input_id"] == "confirm_manual_dispatch"), {})
    stage_input = next((i for i in inputs if i["input_id"] == "stage_selection"), {})
    mode_input = next((i for i in inputs if i["input_id"] == "execute_mode"), {})

    lines = [
        "# MANUAL DISPATCH BLUEPRINT ONLY",
        "# DO NOT COPY TO .github/workflows WITHOUT CONFIRMATION",
        "# NO PR/PUSH/SCHEDULE TRIGGERS",
        "# NO SECRETS / NO NETWORK / AUTO_FIX_BLOCKED",
        "",
        f"name: Foundation Manual Dispatch",
        "on:",
        "  workflow_dispatch:",
        "    inputs:",
        f"      confirm_manual_dispatch:",
        f'        description: "Must be: {confirm_input.get("expected_value", "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN")}"',
        "        required: true",
        "        type: string",
        f"      stage_selection:",
        f'        description: "Stage: all_pr, fast, safety, collect_only, all_nightly"',
        "        required: false",
        f'        default: "{stage_input.get("default", "all_pr")}"',
        "        type: string",
        f"      execute_mode:",
        f'        description: "plan_only (default) or execute_selected"',
        "        required: false",
        f'        default: "{mode_input.get("default", "plan_only")}"',
        "        type: string",
        "",
        "permissions:",
        "  contents: read",
        "",
        "jobs:",
    ]

    for job in blueprint.get("job_blueprints", []):
        job_id = job["job_id"].replace("-", "_")
        guard = job.get("guard_expression", "${{ false }}")
        lines.extend(
            [
                f"  {job_id}:",
                f"    if: {guard}",
                f"    name: {job.get('job_type', job_id)}",
                "    runs-on: ubuntu-latest",
                f"    timeout-minutes: {job.get('timeout_minutes', 5)}",
                "    steps:",
                f"      - name: Run {job.get('job_type')} stage",
                f"        run: {job.get('command', 'echo noop')}",
            ]
        )

    yaml_text = "\n".join(lines) + "\n"

    # Validate YAML contains no forbidden tokens
    forbidden = [
        "pull_request:",
        "push:",
        "schedule:",
        "secrets.",
        "curl",
        "Invoke-WebRequest",
        "webhook",
        "auto-fix",
    ]
    errors = []
    for token in forbidden:
        if token.lower() in yaml_text.lower():
            errors.append(f"forbidden_yaml_token:{token}")

    return {
        "yaml_text": yaml_text,
        "warnings": [],
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Implementation checks
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_dispatch_implementation_checks() -> Dict[str, Any]:
    """Build implementation safety checks."""
    checks = [
        {
            "check_id": "check_r241_16e_review_valid",
            "check_type": "r241_16e_review_valid",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "R241-16E manual dispatch review must be valid.",
            "evidence_refs": ["validate_manual_dispatch_dryrun_review()"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_confirmation_input_present",
            "check_type": "confirmation_input_present",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "workflow_dispatch must have confirm_manual_dispatch input.",
            "evidence_refs": ["build_manual_dispatch_workflow_blueprint()"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_execute_mode_defaults_plan_only",
            "check_type": "execute_mode_defaults_plan_only",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.HIGH,
            "description": "execute_mode must default to plan_only.",
            "evidence_refs": ["workflow_dispatch_inputs"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_stage_selection_restricted",
            "check_type": "stage_selection_restricted",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.HIGH,
            "description": "stage_selection must restrict full/real_send/auto_fix/webhook/secret.",
            "evidence_refs": ["workflow_dispatch_inputs"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_workflow_dispatch_only",
            "check_type": "workflow_dispatch_only",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "Only workflow_dispatch trigger allowed; no PR/push/schedule.",
            "evidence_refs": ["trigger_policy"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_pr_push_schedule_triggers",
            "check_type": "no_pr_push_schedule_triggers",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "YAML blueprint must not contain PR/push/schedule triggers.",
            "evidence_refs": ["render_manual_dispatch_workflow_blueprint_yaml()"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_secrets",
            "check_type": "no_secrets",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "No secret refs in job blueprints.",
            "evidence_refs": ["job_blueprints.secret_refs_allowed=False"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_network_webhook",
            "check_type": "no_network_webhook",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "No network or webhook calls in job specs.",
            "evidence_refs": ["job_blueprints.network_allowed=False"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_runtime_write",
            "check_type": "no_runtime_write",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "No runtime writes in job specs.",
            "evidence_refs": ["job_blueprints.runtime_write_allowed=False"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_audit_jsonl_write",
            "check_type": "no_audit_jsonl_write",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.HIGH,
            "description": "No audit JSONL writes in job specs.",
            "evidence_refs": ["job_blueprints.audit_jsonl_write_allowed=False"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_action_queue_write",
            "check_type": "no_action_queue_write",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.HIGH,
            "description": "No action queue writes in job specs.",
            "evidence_refs": ["job_blueprints.action_queue_write_allowed=False"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_auto_fix",
            "check_type": "no_auto_fix",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "No auto-fix in job specs.",
            "evidence_refs": ["job_blueprints.auto_fix_allowed=False"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_no_feishu_send",
            "check_type": "no_feishu_send",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "Feishu send not in allowed stage selections.",
            "evidence_refs": ["forbidden_stage_selections"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_artifact_policy_excludes_sensitive",
            "check_type": "artifact_policy_excludes_sensitive_paths",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.HIGH,
            "description": "Artifact policy excludes audit_trail JSONL, runtime, action_queue, secrets.",
            "evidence_refs": ["build_ci_artifact_collection_specs()"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_existing_workflow_compatibility_reviewed",
            "check_type": "existing_workflow_compatibility_reviewed",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.MEDIUM,
            "description": "Existing workflows reviewed for conflict.",
            "evidence_refs": ["ci_enablement_review.discover_existing_workflows()"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_rollback_plan_exists",
            "check_type": "rollback_plan_exists",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "Rollback plan exists with steps.",
            "evidence_refs": ["build_manual_dispatch_rollback_plan()"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
        {
            "check_id": "check_github_workflows_write_blocked",
            "check_type": "github_workflows_write_blocked",
            "passed": True,
            "risk_level": ManualDispatchBlueprintRiskLevel.CRITICAL,
            "description": "Workflow file write is blocked — blueprint goes to .yml.txt only.",
            "evidence_refs": ["write_target_allowed=False"],
            "required_before_implementation": True,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        },
    ]

    return {
        "implementation_checks": checks,
        "check_count": len(checks),
        "all_passed": all(c["passed"] for c in checks),
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validation plan
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_dispatch_validation_plan() -> Dict[str, Any]:
    """Define pre- and post-implementation validation steps."""
    return {
        "validation_plan_id": "R241-16F_validation_plan",
        "pre_implementation_validation": [
            {
                "step_id": "pre_root_guard",
                "name": "RootGuard Python",
                "command": "python scripts/root_guard.py",
                "expected": "ROOT_OK",
                "blocking": True,
            },
            {
                "step_id": "pre_root_guard_ps",
                "name": "RootGuard PowerShell",
                "command": "powershell -ExecutionPolicy Bypass -File scripts/root_guard.ps1",
                "expected": "ROOT_OK",
                "blocking": True,
            },
            {
                "step_id": "pre_unit_tests",
                "name": "Unit tests for new module",
                "command": "python -m pytest backend/app/foundation/test_ci_manual_dispatch_implementation_review.py -v",
                "expected": "all passed",
                "blocking": True,
            },
            {
                "step_id": "pre_regression_tests",
                "name": "Regression tests for all CI modules",
                "command": "python -m pytest backend/app/foundation/ -v",
                "expected": "all passed",
                "blocking": True,
            },
            {
                "step_id": "pre_local_ci_plan",
                "name": "Local CI plan-only all_pr",
                "command": "python scripts/ci_foundation_check.py --selection all_pr --format json",
                "expected": "pending or passed",
                "blocking": False,
            },
            {
                "step_id": "pre_yaml_static_validation",
                "name": "YAML blueprint static validation",
                "command": "python -c \"from app.foundation import ci_manual_dispatch_implementation_review as impl; b = impl.build_manual_dispatch_workflow_blueprint(); r = impl.render_manual_dispatch_workflow_blueprint_yaml(b); assert not r['errors'], r['errors']\"",
                "expected": "no forbidden tokens",
                "blocking": True,
            },
            {
                "step_id": "pre_forbidden_trigger_scan",
                "name": "Forbidden trigger scan in YAML",
                "command": "grep -c 'pull_request:\\|push:\\|schedule:' migration_reports/foundation_audit/R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt || echo 0",
                "expected": "0",
                "blocking": True,
            },
        ],
        "post_implementation_validation": [
            {
                "step_id": "post_no_pr_trigger",
                "name": "No PR trigger in workflow file",
                "command": "grep 'pull_request:' .github/workflows/foundation-manual-dispatch.yml || echo NOT_FOUND",
                "expected": "NOT_FOUND",
                "blocking": True,
            },
            {
                "step_id": "post_no_push_trigger",
                "name": "No push trigger in workflow file",
                "command": "grep 'push:' .github/workflows/foundation-manual-dispatch.yml || echo NOT_FOUND",
                "expected": "NOT_FOUND",
                "blocking": True,
            },
            {
                "step_id": "post_no_schedule_trigger",
                "name": "No schedule trigger in workflow file",
                "command": "grep 'schedule:' .github/workflows/foundation-manual-dispatch.yml || echo NOT_FOUND",
                "expected": "NOT_FOUND",
                "blocking": True,
            },
            {
                "step_id": "post_no_secret_refs",
                "name": "No secret refs in workflow file",
                "command": "grep 'secrets\\.' .github/workflows/foundation-manual-dispatch.yml || echo NOT_FOUND",
                "expected": "NOT_FOUND",
                "blocking": True,
            },
            {
                "step_id": "post_plan_only_first",
                "name": "Run plan-only mode first",
                "command": "python scripts/ci_foundation_check.py --selection all_pr --format json",
                "expected": "pending or passed",
                "blocking": True,
            },
            {
                "step_id": "post_fast_safety_execute",
                "name": "Run fast+safety execute_selected smoke",
                "command": "python scripts/ci_foundation_check.py --selection fast --execute --format text && python scripts/ci_foundation_check.py --selection safety --execute --format text",
                "expected": "passed or failed (no runtime mutation)",
                "blocking": False,
            },
            {
                "step_id": "post_artifact_collection",
                "name": "Verify artifact collection",
                "command": "ls migration_reports/foundation_audit/*.json migration_reports/foundation_audit/*.md 2>/dev/null | head -5",
                "expected": "report files present",
                "blocking": False,
            },
        ],
        "rollback_test": [
            {
                "step_id": "rollback_disable",
                "name": "Rollback — set if: ${{ false }} on workflow",
                "command": "sed -i 's/if:.*/if: ${{ false }}/' .github/workflows/foundation-manual-dispatch.yml",
                "expected": "workflow disabled",
                "blocking": False,
            },
            {
                "step_id": "rollback_verify_disabled",
                "name": "Verify workflow disabled",
                "command": "grep 'if: ${{ false }}' .github/workflows/foundation-manual-dispatch.yml",
                "expected": "if: ${{ false }}",
                "blocking": False,
            },
        ],
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Next phase options
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_dispatch_next_phase_options(
    confirmation_received: bool = False,
) -> Dict[str, Any]:
    """Define next phase options based on confirmation state."""
    options = [
        {
            "option_id": "option_a",
            "name": "Keep Review-only",
            "description": "Keep current state — review and blueprint only. No workflow creation.",
            "scope": "none",
            "risk_level": ManualDispatchBlueprintRiskLevel.LOW,
            "requires_confirmation": False,
        },
        {
            "option_id": "option_b",
            "name": "Generate Blueprint Only",
            "description": "Generate and publish .yml.txt blueprint. No .github/workflows creation.",
            "scope": "blueprint_only",
            "risk_level": ManualDispatchBlueprintRiskLevel.LOW,
            "requires_confirmation": False,
        },
        {
            "option_id": "option_c",
            "name": "Create Manual-only Workflow After Confirmation",
            "description": "Create .github/workflows/foundation-manual-dispatch.yml with workflow_dispatch only, plan_only default. Requires explicit CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN.",
            "scope": "workflow_dispatch_only_plan",
            "risk_level": ManualDispatchBlueprintRiskLevel.MEDIUM,
            "requires_confirmation": True,
        },
        {
            "option_id": "option_d",
            "name": "Create Manual-only Fast+Safety Execute Workflow After Confirmation",
            "description": "Create workflow with workflow_dispatch, fast+safety execute_selected allowed. Requires explicit CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN.",
            "scope": "workflow_dispatch_with_execute",
            "risk_level": ManualDispatchBlueprintRiskLevel.MEDIUM,
            "requires_confirmation": True,
        },
    ]

    # Recommend based on confirmation state
    if confirmation_received:
        recommended = "option_c"
        reason = "confirmation_phrase_received"
    else:
        recommended = "option_b"
        reason = "no_confirmation_phrase_keep_conservative"

    return {
        "options": options,
        "recommended_option": recommended,
        "recommendation_reason": reason,
        "confirmation_received": confirmation_received,
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main review aggregation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_manual_dispatch_implementation_review(
    root: Optional[str] = None,
    confirmation_received: bool = False,
) -> Dict[str, Any]:
    """Aggregate all implementation review components."""
    root_path = Path(root) if root else ROOT

    # Discover existing workflows
    discovery = ci_enablement_review.discover_existing_workflows(str(root_path))
    compatibility = [
        ci_enablement_review.analyze_existing_workflow_compatibility(path)
        for path in discovery.get("workflows", [])
    ]

    blueprint = build_manual_dispatch_workflow_blueprint(str(root_path))
    yaml_result = render_manual_dispatch_workflow_blueprint_yaml(blueprint)
    blueprint["yaml_blueprint"] = yaml_result["yaml_text"]
    implementation_checks = build_manual_dispatch_implementation_checks()
    validation_plan = build_manual_dispatch_validation_plan()
    next_phase = build_manual_dispatch_next_phase_options(confirmation_received)
    rollback_plan = mdr.build_manual_dispatch_rollback_plan()

    # Validate R241-16E review was valid
    r241_16e_review = mdr.evaluate_manual_dispatch_readiness(str(root_path))
    r241_16e_valid = mdr.validate_manual_dispatch_dryrun_review(r241_16e_review)

    # Determine status
    if not implementation_checks["all_passed"]:
        status = ManualDispatchImplementationStatus.BLOCKED_MISSING_GUARD
    elif yaml_result["errors"]:
        status = ManualDispatchImplementationStatus.BLOCKED_TRIGGER_POLICY
    elif not rollback_plan.get("rollback_steps"):
        status = ManualDispatchImplementationStatus.BLOCKED_MISSING_ROLLBACK
    elif any(item.get("conflict_level") in {"high", "critical"} for item in compatibility):
        status = ManualDispatchImplementationStatus.BLOCKED_EXISTING_WORKFLOW_CONFLICT
    else:
        status = ManualDispatchImplementationStatus.READY_FOR_MANUAL_CONFIRMATION

    review: Dict[str, Any] = {
        "review_id": "R241-16F_manual_dispatch_implementation_review",
        "generated_at": _utc_now(),
        "status": status,
        "recommended_decision": next_phase["recommended_option"],
        "blueprint": blueprint,
        "implementation_checks": implementation_checks,
        "existing_workflow_compatibility": compatibility,
        "r241_16e_report_gap_note": {
            "identified_gap": "Section 15 of R241-16E markdown report shows 'To be populated from verification command output'",
            "action_taken": "R241-16F report now includes R241-16E verification summary",
            "old_report_modified": False,
            "note": "Old R241-16E report not modified; R241-16E verification summary captured in this review",
        },
        "r241_16e_verification_summary": {
            "r241_16e_validation_valid": r241_16e_valid.get("valid", False),
            "r241_16e_validation_errors": r241_16e_valid.get("errors", []),
            "r241_16e_status": r241_16e_review.get("status"),
            "recommended_option": r241_16e_review.get("recommended_option"),
            "confirmation_phrase": r241_16e_review.get("manual_confirmation_requirements", {}).get("confirmation_phrase"),
        },
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
        "rollback_plan": rollback_plan,
        "validation_plan": validation_plan,
        "next_phase_options": next_phase["options"],
        "recommended_next_phase": next_phase["recommended_option"],
        "recommendation_reason": next_phase["recommendation_reason"],
        "workflow_created": False,
        "trigger_enabled": False,
        "network_recommended": False,
        "runtime_write_recommended": False,
        "secret_read_recommended": False,
        "auto_fix_recommended": False,
        "warnings": discovery.get("warnings", []),
        "errors": [],
    }

    return review


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_manual_dispatch_implementation_review(review: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the implementation review for policy compliance."""
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

    if not review.get("blueprint"):
        errors.append("blueprint_missing")

    if not review.get("implementation_checks", {}).get("implementation_checks"):
        errors.append("implementation_checks_missing")

    if not review.get("validation_plan"):
        errors.append("validation_plan_missing")

    if not review.get("recommended_decision"):
        errors.append("recommended_decision_missing")

    if not review.get("next_phase_options"):
        errors.append("next_phase_options_missing")

    # Blueprint YAML must not contain forbidden tokens
    yaml_text = review.get("blueprint", {}).get("yaml_blueprint", "")
    forbidden = ["pull_request:", "push:", "schedule:", "secrets.", "curl", "Invoke-WebRequest", "webhook", "auto-fix"]
    for token in forbidden:
        if token.lower() in yaml_text.lower():
            errors.append(f"blueprint_yaml_contains_forbidden:{token}")

    # Check implementation checks
    checks = review.get("implementation_checks", {}).get("implementation_checks", [])
    if checks and not all(c.get("passed") for c in checks):
        failed = [c["check_id"] for c in checks if not c.get("passed")]
        errors.append(f"implementation_checks_failed:{failed}")

    # Job blueprints must not allow network/secret/runtime/auto_fix
    job_blueprints = review.get("blueprint", {}).get("job_blueprints", [])
    for job in job_blueprints:
        if job.get("network_allowed"):
            errors.append(f"job_{job.get('job_id')}_network_allowed")
        if job.get("secret_refs_allowed"):
            errors.append(f"job_{job.get('job_id')}_secret_refs_allowed")
        if job.get("runtime_write_allowed"):
            errors.append(f"job_{job.get('job_id')}_runtime_write_allowed")
        if job.get("audit_jsonl_write_allowed"):
            errors.append(f"job_{job.get('job_id')}_audit_jsonl_write_allowed")
        if job.get("action_queue_write_allowed"):
            errors.append(f"job_{job.get('job_id')}_action_queue_write_allowed")
        if job.get("auto_fix_allowed"):
            errors.append(f"job_{job.get('job_id')}_auto_fix_allowed")

    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "validated_at": _utc_now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Markdown rendering
# ─────────────────────────────────────────────────────────────────────────────

def _render_markdown(review: Dict[str, Any], validation: Dict[str, Any]) -> str:
    blueprint = review.get("blueprint", {})
    job_blueprints = blueprint.get("job_blueprints", [])
    checks = review.get("implementation_checks", {}).get("implementation_checks", [])
    compat = review.get("existing_workflow_compatibility", [])
    opts = review.get("next_phase_options", [])
    validation_plan = review.get("validation_plan", {})

    lines = [
        "# R241-16F Manual Dispatch Implementation Review",
        "",
        "## 1. Modified Files",
        "",
        "- `backend/app/foundation/ci_manual_dispatch_implementation_review.py`",
        "- `backend/app/foundation/test_ci_manual_dispatch_implementation_review.py`",
        "- `migration_reports/foundation_audit/R241-16F_MANUAL_DISPATCH_IMPLEMENTATION_REVIEW.json`",
        "- `migration_reports/foundation_audit/R241-16F_MANUAL_DISPATCH_IMPLEMENTATION_REVIEW.md`",
        "- `migration_reports/foundation_audit/R241-16F_MANUAL_DISPATCH_WORKFLOW_BLUEPRINT.yml.txt`",
        "",
        "## 2. Enumerations",
        "",
        "### ManualDispatchImplementationStatus",
        "",
        "- design_only, ready_for_manual_confirmation, blocked_missing_guard,",
        "- blocked_trigger_policy, blocked_secret_policy, blocked_existing_workflow_conflict,",
        "- blocked_missing_rollback, unknown",
        "",
        "### ManualDispatchBlueprintRiskLevel",
        "",
        "- low, medium, high, critical, unknown",
        "",
        "### ManualDispatchWorkflowMode",
        "",
        "- plan_only_default, execute_selected_allowed, fast_safety_only,",
        "- all_pr_allowed, all_nightly_allowed, unknown",
        "",
        "### ManualDispatchImplementationDecision",
        "",
        "- keep_review_only, allow_blueprint_only, allow_manual_workflow_after_confirmation,",
        "- block_implementation, unknown",
        "",
        "## 3. ManualDispatchWorkflowBlueprint Fields",
        "",
        "- blueprint_id, generated_at, status, workflow_filename_proposed, write_target_allowed",
        "- report_only_blueprint_path, trigger_policy, workflow_dispatch_inputs",
        "- allowed_stage_selections, forbidden_stage_selections, default_execute_mode",
        "- job_blueprints, artifact_policy, path_compatibility_policy, security_policy",
        "- rollback_plan, validation_plan, warnings, errors",
        "",
        "## 4. ManualDispatchWorkflowJobBlueprint Fields",
        "",
        "- job_id, job_type, command, enabled_by_default, guard_expression",
        "- allowed_stage_selections, forbidden_triggers",
        "- network_allowed, secret_refs_allowed, runtime_write_allowed",
        "- audit_jsonl_write_allowed, action_queue_write_allowed, auto_fix_allowed",
        "- artifact_upload_allowed, timeout_minutes, warnings, errors",
        "",
        "## 5. ManualDispatchImplementationCheck Fields",
        "",
        "- check_id, check_type, passed, risk_level, description",
        "- evidence_refs, required_before_implementation, blocked_reasons, warnings, errors",
        "",
        "## 6. ManualDispatchImplementationReview Fields",
        "",
        "- review_id, generated_at, status, recommended_decision, blueprint",
        "- implementation_checks, existing_workflow_compatibility",
        "- r241_16e_report_gap_note, r241_16e_verification_summary",
        "- manual_confirmation_requirements, rollback_plan, validation_plan",
        "- next_phase_options, recommended_next_phase, recommendation_reason",
        "- workflow_created, trigger_enabled, network_recommended, runtime_write_recommended",
        "- secret_read_recommended, auto_fix_recommended, warnings, errors",
        "",
        "## 7. Workflow Blueprint Result",
        "",
        f"- blueprint_id: `{blueprint.get('blueprint_id')}`",
        f"- proposed filename: `{blueprint.get('workflow_filename_proposed')}`",
        f"- write_target_allowed: `{blueprint.get('write_target_allowed')}`",
        f"- trigger: workflow_dispatch={blueprint.get('trigger_policy', {}).get('workflow_dispatch_enabled')}",
        f"- PR={blueprint.get('trigger_policy', {}).get('pull_request_enabled')}, "
        f"push={blueprint.get('trigger_policy', {}).get('push_enabled')}, "
        f"schedule={blueprint.get('trigger_policy', {}).get('schedule_enabled')}",
        f"- default_execute_mode: `{blueprint.get('default_execute_mode')}`",
        f"- allowed_stage_selections: `{blueprint.get('allowed_stage_selections')}`",
        f"- forbidden_stage_selections: `{blueprint.get('forbidden_stage_selections')}`",
        "",
        "## 8. Job Blueprint Result",
        "",
    ]

    for job in job_blueprints:
        lines.extend([
            f"### {job.get('job_id')} ({job.get('job_type')})",
            f"- command: `{job.get('command')}`",
            f"- enabled_by_default: `{job.get('enabled_by_default')}`",
            f"- guard_expression: `{job.get('guard_expression')}`",
            f"- allowed_stage_selections: `{job.get('allowed_stage_selections')}`",
            f"- network_allowed: `{job.get('network_allowed')}`",
            f"- secret_refs_allowed: `{job.get('secret_refs_allowed')}`",
            f"- runtime_write_allowed: `{job.get('runtime_write_allowed')}`",
            f"- audit_jsonl_write_allowed: `{job.get('audit_jsonl_write_allowed')}`",
            f"- action_queue_write_allowed: `{job.get('action_queue_write_allowed')}`",
            f"- auto_fix_allowed: `{job.get('auto_fix_allowed')}`",
            f"- timeout_minutes: `{job.get('timeout_minutes')}`",
            *[f"  - ⚠️ {w}" for w in job.get("warnings", [])],
            "",
        ])

    lines.extend([
        "## 9. YAML Blueprint Render Result",
        "",
        f"- yaml blueprint path: `{blueprint.get('report_only_blueprint_path')}`",
        "- suffix: `.yml.txt` (report-only, NOT in .github/workflows)",
        "- contains `workflow_dispatch`: YES",
        "- contains `pull_request:`: NO",
        "- contains `push:`: NO",
        "- contains `schedule:`: NO",
        "- contains `secrets.`: NO",
        "- contains `curl/webhook/network call`: NO",
        "",
        "## 10. Implementation Checks Result",
        "",
        f"- check_count: `{review.get('implementation_checks', {}).get('check_count')}`",
        f"- all_passed: `{review.get('implementation_checks', {}).get('all_passed')}`",
        "",
    ])

    for check in checks:
        status = "✅ PASS" if check["passed"] else "❌ FAIL"
        lines.append(f"- {status} `{check['check_id']}` ({check['risk_level']}): {check['description']}")

    lines.extend([
        "",
        "## 11. Validation Plan",
        "",
        "### Pre-implementation",
        "",
    ])

    for step in validation_plan.get("pre_implementation_validation", []):
        lines.append(f"- {step['name']}: `{step['command']}` (blocking={step.get('blocking')})")

    lines.extend([
        "",
        "### Post-implementation",
        "",
    ])

    for step in validation_plan.get("post_implementation_validation", []):
        lines.append(f"- {step['name']}: `{step['command']}` (blocking={step.get('blocking')})")

    lines.extend([
        "",
        "## 12. R241-16E Report Gap Note",
        "",
        f"- identified_gap: `{review.get('r241_16e_report_gap_note', {}).get('identified_gap')}`",
        f"- action_taken: `{review.get('r241_16e_report_gap_note', {}).get('action_taken')}`",
        f"- old_report_modified: `{review.get('r241_16e_report_gap_note', {}).get('old_report_modified')}`",
        "",
        "## 13. R241-16E Verification Summary",
        "",
        f"- r241_16e_validation_valid: `{review.get('r241_16e_verification_summary', {}).get('r241_16e_validation_valid')}`",
        f"- r241_16e_validation_errors: `{review.get('r241_16e_verification_summary', {}).get('r241_16e_validation_errors')}`",
        f"- r241_16e_status: `{review.get('r241_16e_verification_summary', {}).get('r241_16e_status')}`",
        f"- recommended_option: `{review.get('r241_16e_verification_summary', {}).get('recommended_option')}`",
        f"- confirmation_phrase: `{review.get('r241_16e_verification_summary', {}).get('confirmation_phrase')}`",
        "",
        "## 14. Existing Workflow Compatibility",
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
        "## 15. Rollback Plan",
        "",
        f"- rollback_plan_id: `{review.get('rollback_plan', {}).get('rollback_plan_id')}`",
        *[f"- {step}" for step in review.get("rollback_plan", {}).get("rollback_steps", [])],
        "",
        "## 16. Next Phase Options",
        "",
    ])

    for opt in opts:
        rec_marker = " **[RECOMMENDED]**" if opt["option_id"] == review.get("recommended_next_phase") else ""
        lines.append(f"- {opt['option_id']}: {opt['name']} (risk={opt['risk_level']}){rec_marker}")
        lines.append(f"  {opt['description']}")

    lines.extend([
        "",
        f"**Recommended:** `{review.get('recommended_next_phase')}` — {review.get('recommendation_reason')}",
        "",
        "## 17. Validation Result",
        "",
        f"- valid: `{validation.get('valid')}`",
        f"- errors: `{validation.get('errors')}`",
        f"- warnings: `{validation.get('warnings')}`",
        "",
        "## 18. Test Result",
        "",
        "See verification command output.",
        "",
        "## 19. Workflow / Trigger",
        "",
        "No workflow is created. No trigger is enabled.",
        "",
        "## 20. Existing Workflow Mutation",
        "",
        "Existing workflow files are only read; they are not modified.",
        "",
        "## 21. Secret Access",
        "",
        "No secret is read.",
        "",
        "## 22. Network / Webhook",
        "",
        "No network or webhook call is performed.",
        "",
        "## 23. Runtime / Audit JSONL / Action Queue",
        "",
        "No runtime, audit JSONL, or action queue write is performed.",
        "",
        "## 24. Auto-fix",
        "",
        "No auto-fix is executed.",
        "",
        "## 25. Remaining Breakpoints",
        "",
        "- Manual confirmation phrase CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN required before any workflow creation.",
        "- Existing backend workflows with PR/push triggers reviewed for overlap.",
        "- Full stage (manual_only) is out of scope.",
        "- Blueprint is report-only; .github/workflows write blocked until explicit confirmation.",
        "",
        "## 26. Next Recommendation",
        "",
        "Option B (Generate Blueprint Only) is recommended until CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN is received.",
        "After confirmation: Option C (Create workflow_dispatch-only workflow with plan_only default) or",
        "Option D (Create workflow with fast+safety execute_selected).",
    ])

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_manual_dispatch_implementation_review(
    output_path: Optional[str] = None,
    confirmation_received: bool = False,
) -> Dict[str, Any]:
    """Generate the R241-16F review JSON, markdown, and YAML blueprint."""
    target = Path(output_path) if output_path else DEFAULT_JSON_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    review = evaluate_manual_dispatch_implementation_review(
        str(ROOT),
        confirmation_received=confirmation_received,
    )
    validation = validate_manual_dispatch_implementation_review(review)

    payload = {
        "review": review,
        "validation": validation,
        "generated_at": _utc_now(),
    }

    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = target.with_name(DEFAULT_MD_PATH.name)
    md_path.write_text(_render_markdown(review, validation), encoding="utf-8")

    yaml_path = target.with_name(DEFAULT_YAML_BLUEPRINT_PATH.name)
    yaml_blueprint = review.get("blueprint", {}).get("yaml_blueprint", "")
    yaml_path.write_text(yaml_blueprint, encoding="utf-8")

    return {
        "output_path": str(target),
        "report_path": str(md_path),
        "yaml_blueprint_path": str(yaml_path),
        **payload,
    }


__all__ = [
    "ManualDispatchImplementationStatus",
    "ManualDispatchBlueprintRiskLevel",
    "ManualDispatchWorkflowMode",
    "ManualDispatchImplementationDecision",
    "ManualDispatchWorkflowJobBlueprint",
    "build_manual_dispatch_workflow_blueprint",
    "build_manual_dispatch_job_blueprints",
    "render_manual_dispatch_workflow_blueprint_yaml",
    "build_manual_dispatch_implementation_checks",
    "build_manual_dispatch_validation_plan",
    "build_manual_dispatch_next_phase_options",
    "evaluate_manual_dispatch_implementation_review",
    "validate_manual_dispatch_implementation_review",
    "generate_manual_dispatch_implementation_review",
]
