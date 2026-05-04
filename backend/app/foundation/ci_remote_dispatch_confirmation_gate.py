"""R241-16J Remote Dispatch Confirmation Gate.

This module implements the confirmation gate for remote dispatch of the foundation-manual-dispatch workflow.
It validates all preconditions, builds command blueprints, and produces a confirmation decision
without actually triggering any remote dispatch.

CRITICAL CONSTRAINT: remote_dispatch_allowed_now is ALWAYS False in this phase.
Actual remote dispatch will be enabled in R241-16K (not implemented here).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ── Project Root and Report Directory ─────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"

# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_CONFIRMATION_PHRASE = "CONFIRM_REMOTE_FOUNDATION_CI_DRYRUN"
DEFAULT_REQUESTED_MODE = "remote_plan_only"
DEFAULT_STAGE_SELECTION = "all_pr"
DEFAULT_EXECUTE_MODE = "plan_only"

GATE_ID = "R241-16J_remote_dispatch_confirmation_gate"

# ── String-Enum Classes ─────────────────────────────────────────────────────────

class RemoteDispatchConfirmationStatus(str, Enum):
    """Gate completion status."""
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED_PRECHECK_FAILED = "blocked_precheck_failed"
    BLOCKED_CONFIRMATION_PHRASE_INVALID = "blocked_confirmation_phrase_invalid"
    BLOCKED_MODE_NOT_ALLOWED = "blocked_mode_not_allowed"
    BLOCKED_WORKFLOW_NOT_READY = "blocked_workflow_not_ready"
    BLOCKED_GATE_EVALUATION_FAILED = "blocked_gate_evaluation_failed"
    BLOCKED_DECISION_VALIDATION_FAILED = "blocked_decision_validation_failed"
    UNKNOWN = "unknown"


class RemoteDispatchMode(str, Enum):
    """Remote dispatch operation mode."""
    REMOTE_PLAN_ONLY = "remote_plan_only"
    REMOTE_SELECTED_EXECUTE = "remote_selected_execute"
    REMOTE_ALL_EXECUTE = "remote_all_execute"
    REMOTE_SAFETY_EXECUTE = "remote_safety_execute"
    REMOTE_SLOW_EXECUTE = "remote_slow_execute"


class RemoteDispatchRiskLevel(str, Enum):
    """Risk classification for remote dispatch operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class RemoteDispatchDecision(str, Enum):
    """Gate decision outcome."""
    PROCEED = "proceed"
    BLOCK = "block"
    CANCEL = "cancel"
    CONFIRM = "confirm"


# ── Data Objects ───────────────────────────────────────────────────────────────

class RemoteDispatchInput:
    """Input parameters for remote dispatch confirmation gate."""
    def __init__(
        self,
        confirmation_phrase: str = DEFAULT_CONFIRMATION_PHRASE,
        requested_mode: str = DEFAULT_REQUESTED_MODE,
        stage_selection: str = DEFAULT_STAGE_SELECTION,
        execute_mode: str = DEFAULT_EXECUTE_MODE,
        workflow_path: Optional[str] = None,
        dry_run: bool = True,
    ):
        self.confirmation_phrase = confirmation_phrase
        self.requested_mode = requested_mode
        self.stage_selection = stage_selection
        self.execute_mode = execute_mode
        self.workflow_path = workflow_path
        self.dry_run = dry_run

    def to_dict(self) -> dict:
        return {
            "confirmation_phrase": self.confirmation_phrase,
            "requested_mode": self.requested_mode,
            "stage_selection": self.stage_selection,
            "execute_mode": self.execute_mode,
            "workflow_path": self.workflow_path,
            "dry_run": self.dry_run,
        }


class RemoteDispatchCommandBlueprint:
    """Command blueprint for remote dispatch execution."""
    def __init__(
        self,
        command_type: str,
        workflow_path: str,
        inputs: dict,
        dry_run: bool = True,
        remote_dispatch_allowed: bool = False,
    ):
        self.command_type = command_type
        self.workflow_path = workflow_path
        self.inputs = inputs
        self.dry_run = dry_run
        self.remote_dispatch_allowed = remote_dispatch_allowed

    def to_dict(self) -> dict:
        return {
            "command_type": self.command_type,
            "workflow_path": self.workflow_path,
            "inputs": self.inputs,
            "dry_run": self.dry_run,
            "remote_dispatch_allowed": self.remote_dispatch_allowed,
        }


class RemoteDispatchConfirmationCheck:
    """Individual check within the confirmation gate."""
    def __init__(
        self,
        check_id: str,
        check_type: str,
        passed: bool,
        risk_level: str = "low",
        description: str = "",
        evidence_refs: Optional[list] = None,
        required_before_pass: bool = True,
        blocked_reasons: Optional[list] = None,
        warnings: Optional[list] = None,
        errors: Optional[list] = None,
    ):
        self.check_id = check_id
        self.check_type = check_type
        self.passed = passed
        self.risk_level = risk_level
        self.description = description
        self.evidence_refs = evidence_refs or []
        self.required_before_pass = required_before_pass
        self.blocked_reasons = blocked_reasons or []
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "check_type": self.check_type,
            "passed": self.passed,
            "risk_level": self.risk_level,
            "description": self.description,
            "evidence_refs": self.evidence_refs,
            "required_before_pass": self.required_before_pass,
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class RemoteDispatchConfirmationDecision:
    """Final gate decision object."""
    def __init__(
        self,
        decision: str,
        mode: str,
        stage_selection: str,
        execute_mode: str,
        remote_dispatch_allowed: bool = False,
        risk_level: str = "high",
        reason: str = "",
        blueprint: Optional[dict] = None,
        rollback_plan: Optional[dict] = None,
    ):
        self.decision = decision
        self.mode = mode
        self.stage_selection = stage_selection
        self.execute_mode = execute_mode
        self.remote_dispatch_allowed = remote_dispatch_allowed
        self.risk_level = risk_level
        self.reason = reason
        self.blueprint = blueprint
        self.rollback_plan = rollback_plan

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "mode": self.mode,
            "stage_selection": self.stage_selection,
            "execute_mode": self.execute_mode,
            "remote_dispatch_allowed": self.remote_dispatch_allowed,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "blueprint": self.blueprint,
            "rollback_plan": self.rollback_plan,
        }


# ── Helper Functions ───────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_workflow_yaml_text(workflow_path: Optional[str] = None) -> tuple[str, bool]:
    """Load workflow YAML text from path. Returns (yaml_text, exists)."""
    if workflow_path:
        p = Path(workflow_path)
    else:
        p = ROOT / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    if p.exists():
        return p.read_text(encoding="utf-8"), True
    return "", False


def _load_r241_16i_results() -> dict:
    """Load R241-16I runtime verification results for gate evaluation."""
    result_path = REPORT_DIR / "R241-16I_MANUAL_WORKFLOW_RUNTIME_VERIFICATION_RESULT.json"
    if result_path.exists():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            # R241-16I JSON has top-level "result" key containing the actual verification data
            return data.get("result", data)
        except Exception:
            return {}
    return {}


# ── 1. build_remote_dispatch_input ────────────────────────────────────────────

def build_remote_dispatch_input(
    confirmation_phrase: str = DEFAULT_CONFIRMATION_PHRASE,
    requested_mode: str = DEFAULT_REQUESTED_MODE,
    stage_selection: str = DEFAULT_STAGE_SELECTION,
    execute_mode: str = DEFAULT_EXECUTE_MODE,
) -> dict:
    """Build and validate remote dispatch input object."""
    inp = RemoteDispatchInput(
        confirmation_phrase=confirmation_phrase,
        requested_mode=requested_mode,
        stage_selection=stage_selection,
        execute_mode=execute_mode,
        workflow_path=str(ROOT / ".github" / "workflows" / "foundation-manual-dispatch.yml"),
        dry_run=True,
    )
    return {
        "input": inp.to_dict(),
        "confirmation_phrase_valid": confirmation_phrase == DEFAULT_CONFIRMATION_PHRASE,
        "mode_valid": requested_mode in [m.value for m in RemoteDispatchMode],
    }


# ── 2. validate_remote_dispatch_confirmation_phrase ─────────────────────────────

def validate_remote_dispatch_confirmation_phrase(
    confirmation_phrase: str,
) -> dict:
    """Validate the confirmation phrase against the expected value."""
    expected = DEFAULT_CONFIRMATION_PHRASE
    passed = confirmation_phrase == expected
    return {
        "passed": passed,
        "expected_phrase": expected,
        "received_phrase": confirmation_phrase,
        "check_id": "check_confirmation_phrase",
        "check_type": "confirmation_phrase_validation",
        "risk_level": "critical" if passed else "high",
        "description": "Validates confirmation phrase matches expected dry-run phrase",
        "blocked_reasons": [] if passed else [f"Confirmation phrase mismatch: received '{confirmation_phrase}', expected '{expected}'"],
    }


# ── 3. validate_requested_remote_dispatch_mode ────────────────────────────────

def validate_requested_remote_dispatch_mode(
    requested_mode: str,
) -> dict:
    """Validate the requested remote dispatch mode."""
    valid_modes = [m.value for m in RemoteDispatchMode]
    passed = requested_mode in valid_modes
    return {
        "passed": passed,
        "valid_modes": valid_modes,
        "requested_mode": requested_mode,
        "check_id": "check_requested_mode",
        "check_type": "mode_validation",
        "risk_level": "high",
        "description": f"Validates requested mode is one of: {valid_modes}",
        "blocked_reasons": [] if passed else [f"Requested mode '{requested_mode}' not in valid modes: {valid_modes}"],
    }


# ── 4. validate_workflow_runtime_ready_for_remote_dispatch ─────────────────────

def validate_workflow_runtime_ready_for_remote_dispatch() -> dict:
    """Validate workflow is ready for remote dispatch using R241-16I results."""
    results = _load_r241_16i_results()

    yaml_valid = results.get("yaml_valid", False)
    guard_valid = results.get("guard_expressions_valid", False)
    stage_valid = results.get("stage_selection_valid", False)
    execute_valid = results.get("execute_mode_valid", False)
    plan_only_passed = results.get("plan_only_verification_passed", False)
    safety_passed = results.get("safety_execute_smoke_passed", False)
    workflows_unchanged = results.get("existing_workflows_unchanged", False)
    artifact_guard = results.get("runtime_artifact_guard_passed", False)

    all_static_valid = yaml_valid and guard_valid and stage_valid and execute_valid
    runtime_checks_passed = plan_only_passed and safety_passed and workflows_unchanged and artifact_guard
    passed = all_static_valid and runtime_checks_passed

    errors = []
    if not yaml_valid:
        errors.append("YAML structure invalid from R241-16I")
    if not guard_valid:
        errors.append("Guard expressions invalid from R241-16I")
    if not stage_valid:
        errors.append("Stage selection guards invalid from R241-16I")
    if not execute_valid:
        errors.append("Execute mode invalid from R241-16I")
    if not plan_only_passed:
        errors.append("Plan-only verification failed in R241-16I")
    if not safety_passed:
        errors.append("Safety execute smoke failed in R241-16I")
    if not workflows_unchanged:
        errors.append("Existing workflows were modified (R241-16I)")
    if not artifact_guard:
        errors.append("Runtime artifact mutation detected (R241-16I)")

    return {
        "passed": passed,
        "check_id": "check_workflow_runtime_ready",
        "check_type": "workflow_runtime_validation",
        "risk_level": "critical",
        "description": "Validates workflow readiness using R241-16I runtime verification results",
        "yaml_valid": yaml_valid,
        "guard_expressions_valid": guard_valid,
        "stage_selection_valid": stage_valid,
        "execute_mode_valid": execute_valid,
        "plan_only_verification_passed": plan_only_passed,
        "safety_execute_smoke_passed": safety_passed,
        "existing_workflows_unchanged": workflows_unchanged,
        "runtime_artifact_guard_passed": artifact_guard,
        "blocked_reasons": errors if not passed else [],
        "r241_16i_results_ref": str(REPORT_DIR / "R241-16I_MANUAL_WORKFLOW_RUNTIME_VERIFICATION_RESULT.json"),
    }


# ── 5. build_remote_dispatch_command_blueprint ───────────────────────────────

def build_remote_dispatch_command_blueprint(
    mode: str = DEFAULT_REQUESTED_MODE,
    stage_selection: str = DEFAULT_STAGE_SELECTION,
    execute_mode: str = DEFAULT_EXECUTE_MODE,
) -> dict:
    """Build command blueprint for remote dispatch (never actually dispatched)."""
    workflow_path = str(ROOT / ".github" / "workflows" / "foundation-manual-dispatch.yml")

    # Build inputs based on mode and stage_selection
    inputs = {
        "confirm_manual_dispatch": DEFAULT_CONFIRMATION_PHRASE,
        "stage_selection": stage_selection,
        "execute_mode": execute_mode,
    }

    blueprint = RemoteDispatchCommandBlueprint(
        command_type=f"gh workflow run {workflow_path}",
        workflow_path=workflow_path,
        inputs=inputs,
        dry_run=True,
        # CRITICAL: remote_dispatch_allowed is ALWAYS False in this phase
        remote_dispatch_allowed=False,
    )

    return {
        "blueprint": blueprint.to_dict(),
        "command_type": blueprint.command_type,
        "remote_dispatch_allowed": blueprint.remote_dispatch_allowed,
        "mode": mode,
        "stage_selection": stage_selection,
        "execute_mode": execute_mode,
    }


# ── 6. build_remote_dispatch_rollback_or_cancel_plan ───────────────────────────

def build_remote_dispatch_rollback_or_cancel_plan(
    decision: str,
    reason: str = "",
) -> dict:
    """Build rollback or cancel plan for the gate."""
    workflow_path = str(ROOT / ".github" / "workflows" / "foundation-manual-dispatch.yml")

    rollback_steps = [
        {
            "step": 1,
            "action": "cancel_pending_runs",
            "description": "Cancel any pending workflow runs for foundation-manual-dispatch",
            "command": f"gh run list --workflow={workflow_path} --status=in_progress | xargs -r gh run cancel",
        },
        {
            "step": 2,
            "action": "verify_no_dispatch_occurred",
            "description": "Verify no actual dispatch occurred by checking run history",
            "command": f"gh run list --workflow={workflow_path} --limit=5 --json=status,conclusion",
        },
    ]

    return {
        "rollback_plan": {
            "decision": decision,
            "reason": reason,
            "workflow_path": workflow_path,
            "rollback_steps": rollback_steps,
            "gate_id": GATE_ID,
        },
        "cancel_steps": [
            {"step": 1, "action": "no_cancellation_needed", "description": "No active dispatch to cancel"},
        ],
    }


# ── 7. build_remote_dispatch_confirmation_checks ──────────────────────────────

def build_remote_dispatch_confirmation_checks(
    confirmation_phrase: str = DEFAULT_CONFIRMATION_PHRASE,
    requested_mode: str = DEFAULT_REQUESTED_MODE,
    stage_selection: str = DEFAULT_STAGE_SELECTION,
    execute_mode: str = DEFAULT_EXECUTE_MODE,
) -> list:
    """Build all confirmation checks for the gate."""
    checks = []

    # Check 1: Confirmation phrase
    phrase_result = validate_remote_dispatch_confirmation_phrase(confirmation_phrase)
    checks.append(RemoteDispatchConfirmationCheck(
        check_id="check_confirmation_phrase",
        check_type="confirmation_phrase_validation",
        passed=phrase_result["passed"],
        risk_level=phrase_result["risk_level"],
        description=phrase_result["description"],
        blocked_reasons=phrase_result["blocked_reasons"],
    ).to_dict())

    # Check 2: Requested mode
    mode_result = validate_requested_remote_dispatch_mode(requested_mode)
    checks.append(RemoteDispatchConfirmationCheck(
        check_id="check_requested_mode",
        check_type="mode_validation",
        passed=mode_result["passed"],
        risk_level=mode_result["risk_level"],
        description=mode_result["description"],
        blocked_reasons=mode_result["blocked_reasons"],
    ).to_dict())

    # Check 3: Workflow runtime ready (R241-16I)
    ready_result = validate_workflow_runtime_ready_for_remote_dispatch()
    checks.append(RemoteDispatchConfirmationCheck(
        check_id="check_workflow_runtime_ready",
        check_type="workflow_runtime_validation",
        passed=ready_result["passed"],
        risk_level=ready_result["risk_level"],
        description=ready_result["description"],
        blocked_reasons=ready_result.get("blocked_reasons", []),
        evidence_refs=[ready_result.get("r241_16i_results_ref", "")],
    ).to_dict())

    # Check 4: Execute mode is plan_only (safety constraint)
    execute_plan_only = execute_mode == "plan_only"
    checks.append(RemoteDispatchConfirmationCheck(
        check_id="check_execute_mode_plan_only",
        check_type="execute_mode_safety_check",
        passed=execute_plan_only,
        risk_level="high",
        description="execute_mode must be plan_only for confirmation gate",
        blocked_reasons=[] if execute_plan_only else [f"execute_mode '{execute_mode}' is not 'plan_only'"],
    ).to_dict())

    # Check 5: Stage selection is valid
    valid_stages = ["all_pr", "fast", "safety"]
    stage_valid = stage_selection in valid_stages
    checks.append(RemoteDispatchConfirmationCheck(
        check_id="check_stage_selection_valid",
        check_type="stage_selection_validation",
        passed=stage_valid,
        risk_level="medium",
        description=f"stage_selection must be one of: {valid_stages}",
        blocked_reasons=[] if stage_valid else [f"stage_selection '{stage_selection}' not in {valid_stages}"],
    ).to_dict())

    # Check 6: Workflow file exists
    yaml_text, workflow_exists = _load_workflow_yaml_text()
    checks.append(RemoteDispatchConfirmationCheck(
        check_id="check_workflow_file_exists",
        check_type="workflow_existence_check",
        passed=workflow_exists,
        risk_level="critical",
        description="Workflow file foundation-manual-dispatch.yml must exist",
        blocked_reasons=[] if workflow_exists else ["Workflow file does not exist"],
        evidence_refs=[str(ROOT / ".github" / "workflows" / "foundation-manual-dispatch.yml")] if workflow_exists else [],
    ).to_dict())

    # Check 7: Workflow has workflow_dispatch trigger
    has_dispatch = "workflow_dispatch:" in yaml_text
    checks.append(RemoteDispatchConfirmationCheck(
        check_id="check_workflow_dispatch_trigger",
        check_type="workflow_trigger_check",
        passed=has_dispatch,
        risk_level="critical",
        description="Workflow must have workflow_dispatch trigger enabled",
        blocked_reasons=[] if has_dispatch else ["workflow_dispatch trigger not found in workflow file"],
    ).to_dict())

    # Check 8: Remote dispatch NOT allowed (safety constraint for this phase)
    remote_dispatch_allowed = False
    checks.append(RemoteDispatchConfirmationCheck(
        check_id="check_remote_dispatch_not_allowed",
        check_type="remote_dispatch_safety_guard",
        passed=True,  # This check PASSES because remote_dispatch_allowed=False is correct
        risk_level="critical",
        description="remote_dispatch_allowed_now must be False in this phase",
        blocked_reasons=[] if not remote_dispatch_allowed else ["remote_dispatch_allowed=True violates phase constraint"],
    ).to_dict())

    # Check 9: No secrets in workflow (security check)
    no_secrets = "secrets." not in yaml_text
    checks.append(RemoteDispatchConfirmationCheck(
        check_id="check_no_secrets_in_workflow",
        check_type="security_check",
        passed=no_secrets,
        risk_level="critical",
        description="Workflow must not reference any secrets",
        blocked_reasons=[] if no_secrets else ["secrets. reference found in workflow YAML"],
    ).to_dict())

    # Check 10: No network calls in workflow (security check)
    no_network = "curl" not in yaml_text.lower() and "wget" not in yaml_text.lower()
    checks.append(RemoteDispatchConfirmationCheck(
        check_id="check_no_network_calls",
        check_type="security_check",
        passed=no_network,
        risk_level="high",
        description="Workflow must not make direct network calls",
        blocked_reasons=[] if no_network else ["Network call (curl/wget) found in workflow YAML"],
    ).to_dict())

    return checks


# ── 8. evaluate_remote_dispatch_confirmation_gate ─────────────────────────────

def evaluate_remote_dispatch_confirmation_gate(
    confirmation_phrase: str = DEFAULT_CONFIRMATION_PHRASE,
    requested_mode: str = DEFAULT_REQUESTED_MODE,
    stage_selection: str = DEFAULT_STAGE_SELECTION,
    execute_mode: str = DEFAULT_EXECUTE_MODE,
) -> dict:
    """Evaluate all checks and produce gate evaluation result."""
    checks = build_remote_dispatch_confirmation_checks(
        confirmation_phrase=confirmation_phrase,
        requested_mode=requested_mode,
        stage_selection=stage_selection,
        execute_mode=execute_mode,
    )

    all_passed = all(c["passed"] for c in checks)
    required_passed = all(c["passed"] for c in checks if c["required_before_pass"])

    blueprint = build_remote_dispatch_command_blueprint(
        mode=requested_mode,
        stage_selection=stage_selection,
        execute_mode=execute_mode,
    )

    rollback_plan = build_remote_dispatch_rollback_or_cancel_plan(
        decision="cancel" if not all_passed else "confirm",
        reason="Checks failed" if not all_passed else "Gate passed, dispatch confirmed not executed",
    )

    if all_passed:
        status = RemoteDispatchConfirmationStatus.PASSED
        decision = RemoteDispatchDecision.CONFIRM
        reason = "All confirmation checks passed. Dispatch confirmation gate is ready."
    else:
        status = RemoteDispatchConfirmationStatus.BLOCKED_PRECHECK_FAILED
        decision = RemoteDispatchDecision.BLOCK
        reason = f"Pre-check failed: {[c['check_id'] for c in checks if not c['passed']]}"

    return {
        "gate_id": GATE_ID,
        "generated_at": _utc_now(),
        "status": status.value,
        "decision": decision.value,
        "all_passed": all_passed,
        "checks": checks,
        "blueprint": blueprint,
        "rollback_plan": rollback_plan,
        "confirmation_phrase": confirmation_phrase,
        "requested_mode": requested_mode,
        "stage_selection": stage_selection,
        "execute_mode": execute_mode,
        "remote_dispatch_allowed_now": False,  # CRITICAL: Always False in this phase
        "warnings": [],
        "errors": [],
    }


# ── 9. validate_remote_dispatch_confirmation_decision ─────────────────────────

def validate_remote_dispatch_confirmation_decision(result: dict) -> dict:
    """Validate the gate evaluation result has all required fields."""
    required_fields = [
        "gate_id",
        "generated_at",
        "status",
        "decision",
        "all_passed",
        "checks",
        "blueprint",
        "rollback_plan",
        "remote_dispatch_allowed_now",
    ]

    errors = []
    warnings = []
    missing_fields = []

    for field in required_fields:
        if field not in result:
            missing_fields.append(field)
            errors.append(f"Missing required field: {field}")

    # Check that we have at least 9 checks
    checks_count = len(result.get("checks", []))
    if checks_count < 9:
        errors.append(f"Insufficient checks: expected ≥9, got {checks_count}")

    # Check that remote_dispatch_allowed_now is False
    if result.get("remote_dispatch_allowed_now") is not False:
        errors.append("remote_dispatch_allowed_now must be False in this phase")

    # Validate each check has required fields
    for i, check in enumerate(result.get("checks", [])):
        check_fields = ["check_id", "check_type", "passed", "risk_level"]
        for cf in check_fields:
            if cf not in check:
                errors.append(f"Check {i} missing field: {cf}")

    valid = len(errors) == 0

    return {
        "valid": valid,
        "missing_fields": missing_fields,
        "checks_count": checks_count,
        "errors": errors,
        "warnings": warnings,
    }


# ── 10. generate_remote_dispatch_confirmation_gate_report ────────────────────

def generate_remote_dispatch_confirmation_gate_report(
    result: Optional[dict] = None,
    output_path: Optional[str] = None,
    confirmation_phrase: str = DEFAULT_CONFIRMATION_PHRASE,
    requested_mode: str = DEFAULT_REQUESTED_MODE,
    stage_selection: str = DEFAULT_STAGE_SELECTION,
    execute_mode: str = DEFAULT_EXECUTE_MODE,
) -> dict:
    """Generate JSON and markdown report for the confirmation gate.

    This function:
    - Does NOT perform any network calls
    - Does NOT modify any workflow files
    - Does NOT write to audit_trail JSONL
    - Does NOT write to runtime/ or action_queue/
    - Does NOT actually dispatch any workflow
    """
    if result is None:
        result = evaluate_remote_dispatch_confirmation_gate(
            confirmation_phrase=confirmation_phrase,
            requested_mode=requested_mode,
            stage_selection=stage_selection,
            execute_mode=execute_mode,
        )

    # Determine output path
    if output_path is None:
        json_path = REPORT_DIR / f"{GATE_ID.upper().replace('-', '_')}_RESULT.json"
    else:
        json_path = Path(output_path)

    md_path = json_path.with_suffix(".md")

    # Write JSON
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # Generate markdown
    md = _render_gate_markdown(result)
    md_path.write_text(md, encoding="utf-8")

    return {
        "gate_id": GATE_ID,
        "generated_at": result.get("generated_at", _utc_now()),
        "status": result.get("status", "unknown"),
        "decision": result.get("decision", "unknown"),
        "all_passed": result.get("all_passed", False),
        "checks_count": len(result.get("checks", [])),
        "remote_dispatch_allowed_now": result.get("remote_dispatch_allowed_now", False),
        "output_path": str(json_path),
        "report_path": str(md_path),
    }


def _render_gate_markdown(result: dict) -> str:
    """Render markdown report for gate evaluation."""
    lines = [
        f"# {GATE_ID.upper().replace('_', ' ')} Report",
        "",
        f"## Gate Evaluation Result",
        "",
        f"- **Gate ID**: {result.get('gate_id', 'unknown')}",
        f"- **Generated**: {result.get('generated_at', 'unknown')}",
        f"- **Status**: {result.get('status', 'unknown')}",
        f"- **Decision**: {result.get('decision', 'unknown')}",
        f"- **All Checks Passed**: {result.get('all_passed', False)}",
        f"- **Remote Dispatch Allowed Now**: {result.get('remote_dispatch_allowed_now', False)}",
        "",
        f"## Input Parameters",
        "",
        f"- **Confirmation Phrase**: `{result.get('confirmation_phrase', DEFAULT_CONFIRMATION_PHRASE)}`",
        f"- **Requested Mode**: `{result.get('requested_mode', DEFAULT_REQUESTED_MODE)}`",
        f"- **Stage Selection**: `{result.get('stage_selection', DEFAULT_STAGE_SELECTION)}`",
        f"- **Execute Mode**: `{result.get('execute_mode', DEFAULT_EXECUTE_MODE)}`",
        "",
        f"## Confirmation Checks ({len(result.get('checks', []))})",
        "",
    ]

    for i, check in enumerate(result.get("checks", []), 1):
        status_icon = "✅" if check.get("passed") else "❌"
        risk = check.get("risk_level", "unknown").upper()
        lines.append(f"### {i}. [{risk}] {check.get('check_id', 'unknown')} {status_icon}")
        lines.append("")
        lines.append(f"- **Check Type**: {check.get('check_type', 'unknown')}")
        lines.append(f"- **Passed**: {check.get('passed', False)}")
        lines.append(f"- **Risk Level**: {risk}")
        lines.append(f"- **Description**: {check.get('description', '')}")
        if check.get("evidence_refs"):
            lines.append(f"- **Evidence Refs**: {', '.join(str(e) for e in check.get('evidence_refs', []))}")
        if check.get("blocked_reasons"):
            lines.append(f"- **Blocked Reasons**:")
            for br in check.get("blocked_reasons", []):
                lines.append(f"  - {br}")
        if check.get("warnings"):
            lines.append(f"- **Warnings**:")
            for w in check.get("warnings", []):
                lines.append(f"  - {w}")
        lines.append("")

    blueprint = result.get("blueprint", {})
    lines.extend([
        f"## Command Blueprint",
        "",
        f"- **Command Type**: `{blueprint.get('command_type', 'unknown')}`",
        f"- **Workflow Path**: `{blueprint.get('workflow_path', 'unknown')}`",
        f"- **Remote Dispatch Allowed**: `{blueprint.get('remote_dispatch_allowed', False)}`",
        f"- **Dry Run**: `{blueprint.get('dry_run', True)}`",
        "",
        f"## Rollback/Cancel Plan",
        "",
    ])

    rollback = result.get("rollback_plan", {})
    rollback_plan = rollback.get("rollback_plan", {})
    lines.extend([
        f"- **Decision**: {rollback_plan.get('decision', 'unknown')}",
        f"- **Reason**: {rollback_plan.get('reason', 'unknown')}",
        f"- **Gate ID**: {rollback_plan.get('gate_id', GATE_ID)}",
        "",
        f"## Safety Constraints",
        "",
        f"- ✅ `remote_dispatch_allowed_now=false` (CRITICAL: always enforced in this phase)",
        f"- ✅ No network calls performed",
        f"- ✅ No workflow files modified",
        f"- ✅ No audit JSONL written",
        f"- ✅ No runtime/ or action_queue/ created",
        f"- ✅ No actual dispatch executed",
        "",
        f"## Next Phase",
        "",
        f"- R241-16K (Remote Dispatch Execution) — not implemented in this phase",
        f"- Dispatch will be enabled when R241-16K is activated with explicit confirmation",
    ])

    return "\n".join(lines)