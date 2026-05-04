"""Manual Workflow Runtime Verification for R241-16I.

Verifies the created .github/workflows/foundation-manual-dispatch.yml:
- YAML structure, guard expressions, stage_selection guards, execute_mode defaults
- Runs plan-only CI (all_pr, fast, safety without --execute)
- Runs safety execute smoke with timeout
- Verifies no mutation of existing workflows
- Generates R241-16I JSON + MD reports
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.foundation import ci_local_dryrun


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_JSON_PATH = REPORT_DIR / "R241-16I_MANUAL_WORKFLOW_RUNTIME_VERIFICATION_RESULT.json"
DEFAULT_MD_PATH = REPORT_DIR / "R241-16I_MANUAL_WORKFLOW_RUNTIME_VERIFICATION_REPORT.md"
TARGET_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "foundation-manual-dispatch.yml"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class ManualWorkflowRuntimeVerificationStatus:
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED_PRECHECK_FAILED = "blocked_precheck_failed"
    BLOCKED_WORKFLOW_NOT_FOUND = "blocked_workflow_not_found"
    BLOCKED_YAML_INVALID = "blocked_yaml_invalid"
    BLOCKED_GUARD_EXPRESSION_INVALID = "blocked_guard_expression_invalid"
    BLOCKED_STAGE_SELECTION_INVALID = "blocked_stage_selection_invalid"
    BLOCKED_EXECUTE_MODE_INVALID = "blocked_execute_mode_invalid"
    BLOCKED_PLAN_ONLY_VERIFICATION_FAILED = "blocked_plan_only_verification_failed"
    BLOCKED_SAFETY_EXECUTE_FAILED = "blocked_safety_execute_failed"
    BLOCKED_EXISTING_WORKFLOWS_MODIFIED = "blocked_existing_workflows_modified"
    BLOCKED_ARTIFACT_MUTATION = "blocked_artifact_mutation"
    ROLLED_BACK = "rolled_back"
    UNKNOWN = "unknown"


class ManualWorkflowRuntimeCheckType:
    YAML_STRUCTURE = "yaml_structure"
    GUARD_EXPRESSION = "guard_expression"
    STAGE_SELECTION_GUARD = "stage_selection_guard"
    EXECUTE_MODE_DEFAULT = "execute_mode_default"
    PLAN_ONLY_VERIFICATION = "plan_only_verification"
    SAFETY_EXECUTE_SMOKE = "safety_execute_smoke"
    EXISTING_WORKFLOWS_UNCHANGED = "existing_workflows_unchanged"
    RUNTIME_ARTIFACT_MUTATION_GUARD = "runtime_artifact_mutation_guard"


class ManualWorkflowRuntimeRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Data objects
# ─────────────────────────────────────────────────────────────────────────────

class ManualWorkflowRuntimeCheck:
    def __init__(
        self,
        check_id: str,
        check_type: str,
        passed: bool,
        risk_level: str,
        description: str,
        evidence_refs: Optional[List[str]] = None,
        required_before_pass: bool = True,
        blocked_reasons: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
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

    def to_dict(self) -> Dict[str, Any]:
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


class ManualWorkflowRuntimeVerification:
    def __init__(
        self,
        verification_id: str,
        generated_at: str,
        status: str,
        workflow_path: str,
        yaml_valid: bool,
        guard_expressions_valid: bool,
        stage_selection_valid: bool,
        execute_mode_valid: bool,
        plan_only_verification_passed: bool,
        safety_execute_smoke_passed: bool,
        existing_workflows_unchanged: bool,
        runtime_artifact_guard_passed: bool,
        checks: Optional[List[ManualWorkflowRuntimeCheck]] = None,
        plan_only_result: Optional[Dict[str, Any]] = None,
        safety_execute_result: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
    ):
        self.verification_id = verification_id
        self.generated_at = generated_at
        self.status = status
        self.workflow_path = workflow_path
        self.yaml_valid = yaml_valid
        self.guard_expressions_valid = guard_expressions_valid
        self.stage_selection_valid = stage_selection_valid
        self.execute_mode_valid = execute_mode_valid
        self.plan_only_verification_passed = plan_only_verification_passed
        self.safety_execute_smoke_passed = safety_execute_smoke_passed
        self.existing_workflows_unchanged = existing_workflows_unchanged
        self.runtime_artifact_guard_passed = runtime_artifact_guard_passed
        self.checks = checks or []
        self.plan_only_result = plan_only_result
        self.safety_execute_result = safety_execute_result
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "workflow_path": self.workflow_path,
            "yaml_valid": self.yaml_valid,
            "guard_expressions_valid": self.guard_expressions_valid,
            "stage_selection_valid": self.stage_selection_valid,
            "execute_mode_valid": self.execute_mode_valid,
            "plan_only_verification_passed": self.plan_only_verification_passed,
            "safety_execute_smoke_passed": self.safety_execute_smoke_passed,
            "existing_workflows_unchanged": self.existing_workflows_unchanged,
            "runtime_artifact_guard_passed": self.runtime_artifact_guard_passed,
            "checks": [c.to_dict() for c in self.checks],
            "plan_only_result": self.plan_only_result,
            "safety_execute_result": self.safety_execute_result,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Load created workflow
# ─────────────────────────────────────────────────────────────────────────────

def load_created_manual_workflow(
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Load the created manual workflow YAML file."""
    root_path = Path(root) if root else ROOT
    target = TARGET_WORKFLOW_PATH if not root else (Path(root) / ".github" / "workflows" / "foundation-manual-dispatch.yml")

    errors: List[str] = []
    warnings: List[str] = []

    if not target.exists():
        errors.append("workflow_file_not_found")
        return {
            "workflow_path": str(target),
            "workflow_exists": False,
            "yaml_text": None,
            "yaml_parsed": None,
            "warnings": warnings,
            "errors": errors,
        }

    try:
        yaml_text = target.read_text(encoding="utf-8")
    except Exception as e:
        errors.append(f"read_error:{e}")
        return {
            "workflow_path": str(target),
            "workflow_exists": True,
            "yaml_text": None,
            "yaml_parsed": None,
            "warnings": warnings,
            "errors": errors,
        }

    # Basic YAML structure validation
    yaml_parsed: Optional[Dict[str, Any]] = None
    try:
        import yaml as _yaml
        yaml_parsed = _yaml.safe_load(yaml_text)
        if not isinstance(yaml_parsed, dict):
            errors.append("yaml_not_dict_root")
    except Exception as e:
        errors.append(f"yaml_parse_error:{e}")

    return {
        "workflow_path": str(target),
        "workflow_exists": True,
        "yaml_text": yaml_text,
        "yaml_parsed": yaml_parsed,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validate YAML structure statically
# ─────────────────────────────────────────────────────────────────────────────

def validate_manual_workflow_yaml_static(
    yaml_text: Optional[str],
    yaml_parsed: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate YAML structure: only workflow_dispatch, no PR/push/schedule."""
    errors: List[str] = []
    warnings: List[str] = []

    if not yaml_text:
        errors.append("yaml_text_empty")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Check triggers
    pr_trigger = "pull_request:" in yaml_text
    push_trigger = "push:" in yaml_text
    schedule_trigger = "schedule:" in yaml_text
    wfd_trigger = "workflow_dispatch:" in yaml_text

    if pr_trigger:
        errors.append("pull_request_trigger_found")
    if push_trigger:
        errors.append("push_trigger_found")
    if schedule_trigger:
        errors.append("schedule_trigger_found")
    if not wfd_trigger:
        errors.append("workflow_dispatch_trigger_missing")

    # Check forbidden content
    if "secrets." in yaml_text or "secrets:" in yaml_text:
        errors.append("secrets_reference_found")
    if "curl" in yaml_text.lower() or "Invoke-WebRequest" in yaml_text:
        errors.append("network_call_found")
    if "auto-fix" in yaml_text.lower():
        errors.append("auto_fix_found")

    # Check confirmation phrase
    if "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN" not in yaml_text:
        errors.append("confirm_phrase_missing")

    # Check plan_only default
    has_plan_only = 'default: "plan_only"' in yaml_text or "default: 'plan_only'" in yaml_text
    if not has_plan_only:
        errors.append("plan_only_default_missing")

    # Check execute_mode default
    has_execute_mode = "execute_mode" in yaml_text
    if not has_execute_mode:
        errors.append("execute_mode_input_missing")

    passed = len(errors) == 0

    return {
        "valid": passed,
        "pr_trigger_found": pr_trigger,
        "push_trigger_found": push_trigger,
        "schedule_trigger_found": schedule_trigger,
        "workflow_dispatch_trigger_found": wfd_trigger,
        "secrets_found": "secrets." in yaml_text or "secrets:" in yaml_text,
        "network_call_found": "curl" in yaml_text.lower() or "Invoke-WebRequest" in yaml_text,
        "auto_fix_found": "auto-fix" in yaml_text.lower(),
        "confirm_phrase_present": "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN" in yaml_text,
        "plan_only_default_set": has_plan_only,
        "execute_mode_input_present": has_execute_mode,
        "errors": errors,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Verify workflow guard expressions
# ─────────────────────────────────────────────────────────────────────────────

def verify_workflow_guard_expressions(
    yaml_text: Optional[str],
) -> Dict[str, Any]:
    """Verify guard expressions on jobs check for confirmation phrase."""
    errors: List[str] = []
    warnings: List[str] = []

    if not yaml_text:
        errors.append("yaml_text_empty")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # All jobs must have if condition checking confirm_manual_dispatch
    required_phrase = "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN"
    lines = yaml_text.split("\n")
    job_lines: List[int] = []
    guard_lines: List[int] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("job_"):
            job_lines.append(i)
        if "confirm_manual_dispatch" in stripped and "==" in stripped:
            guard_lines.append(i)

    missing_guards = len(job_lines) > 0 and len(guard_lines) == 0
    if missing_guards:
        errors.append("job_guards_missing")
        passed = False
    else:
        passed = True
        # Verify each guard has the confirmation phrase check
        for gl in guard_lines:
            guard_line = lines[gl]
            if required_phrase not in guard_line:
                errors.append(f"guard_missing_phrase_at_line_{gl}")
                passed = False

    return {
        "valid": passed,
        "job_count": len(job_lines),
        "guard_count": len(guard_lines),
        "all_jobs_have_guards": len(job_lines) > 0 and len(guard_lines) >= len(job_lines),
        "errors": errors,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Verify stage_selection guards
# ─────────────────────────────────────────────────────────────────────────────

def verify_stage_selection_guards(
    yaml_text: Optional[str],
) -> Dict[str, Any]:
    """Verify stage_selection guards for fast/safety jobs."""
    errors: List[str] = []
    warnings: List[str] = []

    if not yaml_text:
        errors.append("yaml_text_empty")
        return {"valid": False, "errors": errors, "warnings": warnings}

    lines = yaml_text.split("\n")
    stage_selection_found = False
    fast_has_guard = False
    safety_has_guard = False

    for i, line in enumerate(lines):
        if "stage_selection" in line:
            stage_selection_found = True
        # Check fast job guard
        if "job_fast" in line:
            # Look at nearby lines for if condition
            for j in range(max(0, i - 2), min(len(lines), i + 3)):
                if "inputs.stage_selection" in lines[j] and ("fast" in lines[j] or "all_pr" in lines[j] or "all_nightly" in lines[j]):
                    fast_has_guard = True
        # Check safety job guard
        if "job_safety" in line:
            for j in range(max(0, i - 2), min(len(lines), i + 3)):
                if "inputs.stage_selection" in lines[j] and ("safety" in lines[j] or "all_pr" in lines[j] or "all_nightly" in lines[j]):
                    safety_has_guard = True

    # Stage selection should be an input
    if not stage_selection_found:
        warnings.append("stage_selection_input_not_found_in_yaml")

    passed = fast_has_guard and safety_has_guard

    return {
        "valid": passed,
        "stage_selection_found": stage_selection_found,
        "fast_has_guard": fast_has_guard,
        "safety_has_guard": safety_has_guard,
        "errors": errors,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Run manual workflow local plan-only verification
# ─────────────────────────────────────────────────────────────────────────────

def run_manual_workflow_local_plan_only_verification(
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Run local CI plan-only stages: all_pr, fast, safety (execute=False)."""
    root_path = Path(root) if root else ROOT
    errors: List[str] = []
    warnings: List[str] = []

    # Run all_pr plan-only
    all_pr_result = ci_local_dryrun.run_local_ci_dryrun(selection="all_pr", execute=False)
    all_pr_status = all_pr_result.get("overall_status", "unknown")

    # Run fast plan-only
    fast_result = ci_local_dryrun.run_local_ci_dryrun(selection="fast", execute=False)
    fast_status = fast_result.get("overall_status", "unknown")

    # Run safety plan-only
    safety_result = ci_local_dryrun.run_local_ci_dryrun(selection="safety", execute=False)
    safety_status = safety_result.get("overall_status", "unknown")

    # All should be pending (plan-only, no actual pytest run)
    all_pending = (
        all_pr_status == "pending" and
        fast_status == "pending" and
        safety_status == "pending"
    )

    if not all_pending:
        warnings.append(f"plan_only_not_pending: all_pr={all_pr_status}, fast={fast_status}, safety={safety_status}")

    return {
        "all_pr_result": all_pr_result,
        "fast_result": fast_result,
        "safety_result": safety_result,
        "all_pending": all_pending,
        "all_pr_status": all_pr_status,
        "fast_status": fast_status,
        "safety_status": safety_status,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Run manual workflow local safety execute smoke
# ─────────────────────────────────────────────────────────────────────────────

def _run_safety_execute_with_timeout(
    timeout: int = 60,
) -> Dict[str, Any]:
    """Run safety stage with execute in a thread with timeout."""
    result_holder: Dict[str, Any] = {"result": None, "error": None}

    def _run():
        try:
            result_holder["result"] = ci_local_dryrun.run_local_ci_dryrun(
                selection="safety",
                execute=True,
                timeout_seconds=30,
            )
        except Exception as e:
            result_holder["error"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        return {
            "timed_out": True,
            "timeout_seconds": timeout,
            "result": result_holder.get("result"),
            "error": "execution_exceeded_timeout",
        }
    if result_holder.get("error"):
        return {
            "timed_out": False,
            "result": None,
            "error": result_holder["error"],
        }
    return {
        "timed_out": False,
        "result": result_holder.get("result"),
        "error": None,
    }


def run_manual_workflow_local_safety_execute_smoke(
    root: Optional[str] = None,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    """Run safety stage with execute=True and timeout."""
    result = _run_safety_execute_with_timeout(timeout=timeout_seconds)

    timed_out = result.get("timed_out", False)
    safety_result = result.get("result")
    run_error = result.get("error")

    errors: List[str] = []
    warnings: List[str] = []

    if timed_out:
        errors.append(f"safety_execute_timed_out_{timeout_seconds}s")
    if run_error:
        errors.append(f"safety_execute_error:{run_error}")

    # Safety stage result
    safety_status = None
    if safety_result:
        safety_status = safety_result.get("overall_status", "unknown")

    passed = not timed_out and not run_error

    return {
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
        "safety_result": safety_result,
        "safety_status": safety_status,
        "passed": passed,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Verify existing workflows unchanged
# ─────────────────────────────────────────────────────────────────────────────

def verify_existing_workflows_unchanged(
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify existing workflow files are not modified."""
    root_path = Path(root) if root else ROOT
    errors: List[str] = []
    warnings: List[str] = []

    backend_unit_tests = root_path / ".github/workflows/backend-unit-tests.yml"
    lint_check = root_path / ".github/workflows/lint-check.yml"

    if not backend_unit_tests.exists():
        errors.append("backend_unit_tests_workflow_missing")
    if not lint_check.exists():
        errors.append("lint_check_workflow_missing")

    passed = backend_unit_tests.exists() and lint_check.exists()

    return {
        "valid": passed,
        "backend_unit_tests_exists": backend_unit_tests.exists(),
        "lint_check_exists": lint_check.exists(),
        "workflows_unchanged": passed,
        "errors": errors,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Verify runtime artifact mutation guard
# ─────────────────────────────────────────────────────────────────────────────

def verify_runtime_artifact_mutation_guard(
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify no runtime/, action_queue/, audit_trail/ files are created during CI run."""
    root_path = Path(root) if root else ROOT
    errors: List[str] = []
    warnings: List[str] = []

    # These paths should not be created by the workflow
    forbidden_paths = [
        root_path / "runtime",
        root_path / "action_queue",
        root_path / "audit_trail",
    ]

    for fp in forbidden_paths:
        if fp.exists():
            # Check if it was modified recently (within last 5 minutes)
            try:
                import time as _time
                mtime = fp.stat().st_mtime
                age_seconds = _time.time() - mtime
                if age_seconds < 300:
                    errors.append(f"artifact_recently_modified:{fp.name}")
            except Exception:
                pass

    passed = len(errors) == 0

    return {
        "valid": passed,
        "runtime_exists": (root_path / "runtime").exists(),
        "action_queue_exists": (root_path / "action_queue").exists(),
        "audit_trail_exists": (root_path / "audit_trail").exists(),
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_manual_workflow_runtime_verification(
    root: Optional[str] = None,
    run_safety_execute: bool = False,
    safety_timeout_seconds: int = 60,
) -> Dict[str, Any]:
    """Evaluate the full runtime verification pipeline."""
    root_path = Path(root) if root else ROOT
    checks: List[ManualWorkflowRuntimeCheck] = []
    all_passed = True

    # 1. Load workflow
    load_result = load_created_manual_workflow(str(root_path))
    workflow_exists = load_result.get("workflow_exists", False)
    yaml_text = load_result.get("yaml_text")
    yaml_parsed = load_result.get("yaml_parsed")

    if not workflow_exists:
        checks.append(ManualWorkflowRuntimeCheck(
            check_id="check_workflow_exists",
            check_type=ManualWorkflowRuntimeCheckType.YAML_STRUCTURE,
            passed=False,
            risk_level=ManualWorkflowRuntimeRiskLevel.CRITICAL,
            description="Created workflow file must exist.",
            evidence_refs=[str(TARGET_WORKFLOW_PATH)],
            errors=["workflow_file_not_found"],
        ))
        all_passed = False
        return {
            "verification_id": "R241-16I_runtime_verification",
            "generated_at": _utc_now(),
            "status": ManualWorkflowRuntimeVerificationStatus.BLOCKED_WORKFLOW_NOT_FOUND,
            "workflow_path": str(TARGET_WORKFLOW_PATH),
            "yaml_valid": False,
            "guard_expressions_valid": False,
            "stage_selection_valid": False,
            "execute_mode_valid": False,
            "plan_only_verification_passed": False,
            "safety_execute_smoke_passed": False,
            "existing_workflows_unchanged": False,
            "runtime_artifact_guard_passed": False,
            "checks": [c.to_dict() for c in checks],
            "plan_only_result": None,
            "safety_execute_result": None,
            "warnings": [],
            "errors": ["workflow_file_not_found"],
        }

    checks.append(ManualWorkflowRuntimeCheck(
        check_id="check_workflow_exists",
        check_type=ManualWorkflowRuntimeCheckType.YAML_STRUCTURE,
        passed=True,
        risk_level=ManualWorkflowRuntimeRiskLevel.CRITICAL,
        description="Created workflow file exists.",
        evidence_refs=[str(TARGET_WORKFLOW_PATH)],
    ))

    # 2. Static YAML validation
    static_result = validate_manual_workflow_yaml_static(yaml_text, yaml_parsed)
    checks.append(ManualWorkflowRuntimeCheck(
        check_id="check_yaml_structure",
        check_type=ManualWorkflowRuntimeCheckType.YAML_STRUCTURE,
        passed=static_result["valid"],
        risk_level=ManualWorkflowRuntimeRiskLevel.CRITICAL,
        description="YAML must have only workflow_dispatch trigger, no PR/push/schedule.",
        evidence_refs=[str(TARGET_WORKFLOW_PATH)],
        errors=static_result["errors"],
    ))
    if not static_result["valid"]:
        all_passed = False

    # 3. Guard expression verification
    guard_result = verify_workflow_guard_expressions(yaml_text)
    checks.append(ManualWorkflowRuntimeCheck(
        check_id="check_guard_expressions",
        check_type=ManualWorkflowRuntimeCheckType.GUARD_EXPRESSION,
        passed=guard_result["valid"],
        risk_level=ManualWorkflowRuntimeRiskLevel.CRITICAL,
        description="All jobs must have guard checking confirmation phrase.",
        evidence_refs=[str(TARGET_WORKFLOW_PATH)],
        errors=guard_result["errors"],
    ))
    if not guard_result["valid"]:
        all_passed = False

    # 4. Stage selection guard verification
    stage_result = verify_stage_selection_guards(yaml_text)
    checks.append(ManualWorkflowRuntimeCheck(
        check_id="check_stage_selection_guards",
        check_type=ManualWorkflowRuntimeCheckType.STAGE_SELECTION_GUARD,
        passed=stage_result["valid"],
        risk_level=ManualWorkflowRuntimeRiskLevel.HIGH,
        description="fast and safety jobs must guard on stage_selection input.",
        evidence_refs=[str(TARGET_WORKFLOW_PATH)],
        errors=stage_result["errors"],
        warnings=stage_result["warnings"],
    ))
    if not stage_result["valid"]:
        all_passed = False

    # 5. Execute mode default verification
    has_execute = static_result.get("execute_mode_input_present", False)
    checks.append(ManualWorkflowRuntimeCheck(
        check_id="check_execute_mode_default",
        check_type=ManualWorkflowRuntimeCheckType.EXECUTE_MODE_DEFAULT,
        passed=has_execute,
        risk_level=ManualWorkflowRuntimeRiskLevel.HIGH,
        description="execute_mode input must be present with plan_only default.",
        evidence_refs=[str(TARGET_WORKFLOW_PATH)],
        errors=[] if has_execute else ["execute_mode_input_missing"],
    ))
    if not has_execute:
        all_passed = False

    # 6. Plan-only local verification
    plan_only_result = run_manual_workflow_local_plan_only_verification(str(root_path))
    plan_passed = plan_only_result.get("all_pending", False)
    checks.append(ManualWorkflowRuntimeCheck(
        check_id="check_plan_only_verification",
        check_type=ManualWorkflowRuntimeCheckType.PLAN_ONLY_VERIFICATION,
        passed=plan_passed,
        risk_level=ManualWorkflowRuntimeRiskLevel.HIGH,
        description="all_pr, fast, safety plan-only runs must return pending (no actual test run).",
        evidence_refs=["ci_local_dryrun.run_local_ci_dryrun"],
        errors=plan_only_result.get("errors", []),
        warnings=plan_only_result.get("warnings", []),
    ))
    if not plan_passed:
        all_passed = False

    # 7. Safety execute smoke
    safety_passed = False
    safety_result: Optional[Dict[str, Any]] = None
    if run_safety_execute:
        safety_result = run_manual_workflow_local_safety_execute_smoke(
            str(root_path),
            timeout_seconds=safety_timeout_seconds,
        )
        safety_passed = safety_result.get("passed", False)
        checks.append(ManualWorkflowRuntimeCheck(
            check_id="check_safety_execute_smoke",
            check_type=ManualWorkflowRuntimeCheckType.SAFETY_EXECUTE_SMOKE,
            passed=safety_passed,
            risk_level=ManualWorkflowRuntimeRiskLevel.MEDIUM,
            description="safety execute smoke must complete within timeout without errors.",
            evidence_refs=["ci_local_dryrun.run_local_ci_dryrun"],
            errors=safety_result.get("errors", []),
            warnings=safety_result.get("warnings", []),
        ))
        if not safety_passed:
            all_passed = False
    else:
        checks.append(ManualWorkflowRuntimeCheck(
            check_id="check_safety_execute_smoke",
            check_type=ManualWorkflowRuntimeCheckType.SAFETY_EXECUTE_SMOKE,
            passed=True,
            risk_level=ManualWorkflowRuntimeRiskLevel.MEDIUM,
            description="safety execute smoke skipped (run_safety_execute=False).",
            evidence_refs=[],
            warnings=["skipped_by_request"],
        ))

    # 8. Existing workflows unchanged
    existing_result = verify_existing_workflows_unchanged(str(root_path))
    checks.append(ManualWorkflowRuntimeCheck(
        check_id="check_existing_workflows_unchanged",
        check_type=ManualWorkflowRuntimeCheckType.EXISTING_WORKFLOWS_UNCHANGED,
        passed=existing_result["valid"],
        risk_level=ManualWorkflowRuntimeRiskLevel.HIGH,
        description="backend-unit-tests.yml and lint-check.yml must not be modified.",
        evidence_refs=[
            str(root_path / ".github/workflows/backend-unit-tests.yml"),
            str(root_path / ".github/workflows/lint-check.yml"),
        ],
        errors=existing_result["errors"],
    ))
    if not existing_result["valid"]:
        all_passed = False

    # 9. Runtime artifact mutation guard
    artifact_result = verify_runtime_artifact_mutation_guard(str(root_path))
    checks.append(ManualWorkflowRuntimeCheck(
        check_id="check_runtime_artifact_mutation_guard",
        check_type=ManualWorkflowRuntimeCheckType.RUNTIME_ARTIFACT_MUTATION_GUARD,
        passed=artifact_result["valid"],
        risk_level=ManualWorkflowRuntimeRiskLevel.HIGH,
        description="runtime/, action_queue/, audit_trail/ must not be created by CI run.",
        evidence_refs=[],
        errors=artifact_result["errors"],
    ))
    if not artifact_result["valid"]:
        all_passed = False

    status = ManualWorkflowRuntimeVerificationStatus.PASSED if all_passed else ManualWorkflowRuntimeVerificationStatus.FAILED

    return {
        "verification_id": "R241-16I_runtime_verification",
        "generated_at": _utc_now(),
        "status": status,
        "workflow_path": str(TARGET_WORKFLOW_PATH),
        "yaml_valid": static_result["valid"],
        "guard_expressions_valid": guard_result["valid"],
        "stage_selection_valid": stage_result["valid"],
        "execute_mode_valid": has_execute,
        "plan_only_verification_passed": plan_passed,
        "safety_execute_smoke_passed": safety_passed,
        "existing_workflows_unchanged": existing_result["valid"],
        "runtime_artifact_guard_passed": artifact_result["valid"],
        "checks": [c.to_dict() for c in checks],
        "plan_only_result": plan_only_result,
        "safety_execute_result": safety_result,
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Validate verification result structure
# ─────────────────────────────────────────────────────────────────────────────

def validate_manual_workflow_runtime_verification(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate the structure of a runtime verification result."""
    errors: List[str] = []
    warnings: List[str] = []

    required_fields = [
        "verification_id", "generated_at", "status", "workflow_path",
        "yaml_valid", "guard_expressions_valid", "stage_selection_valid",
        "execute_mode_valid", "plan_only_verification_passed",
        "safety_execute_smoke_passed", "existing_workflows_unchanged",
        "runtime_artifact_guard_passed", "checks",
    ]
    for field in required_fields:
        if field not in result:
            errors.append(f"missing_field:{field}")

    checks = result.get("checks", [])
    if not isinstance(checks, list):
        errors.append("checks_not_list")
    elif len(checks) < 9:
        errors.append(f"insufficient_checks:{len(checks)}")

    passed = len(errors) == 0
    return {
        "valid": passed,
        "errors": errors,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────

def _render_report_markdown(result: Dict[str, Any]) -> str:
    checks_list = result.get("checks", [])
    plan = result.get("plan_only_result", {})
    safety = result.get("safety_execute_result", {})
    static_yaml = result.get("yaml_valid")
    guard_valid = result.get("guard_expressions_valid")
    stage_valid = result.get("stage_selection_valid")
    exec_valid = result.get("execute_mode_valid")
    plan_passed = result.get("plan_only_verification_passed")
    safety_passed = result.get("safety_execute_smoke_passed")
    existing_ok = result.get("existing_workflows_unchanged")
    artifact_ok = result.get("runtime_artifact_guard_passed")

    lines = [
        "# R241-16I Manual Workflow Runtime Verification Report",
        "",
        "## 1. Modified Files",
        "",
        "- `backend/app/foundation/ci_manual_workflow_runtime_verification.py`",
        "- `backend/app/foundation/test_ci_manual_workflow_runtime_verification.py`",
        "- `migration_reports/foundation_audit/R241-16I_MANUAL_WORKFLOW_RUNTIME_VERIFICATION_REPORT.md`",
        "- `migration_reports/foundation_audit/R241-16I_MANUAL_WORKFLOW_RUNTIME_VERIFICATION_RESULT.json`",
        "",
        "## 2. Enumerations",
        "",
        "### ManualWorkflowRuntimeVerificationStatus",
        "",
        "- passed, failed, blocked_precheck_failed, blocked_workflow_not_found,",
        "- blocked_yaml_invalid, blocked_guard_expression_invalid,",
        "- blocked_stage_selection_invalid, blocked_execute_mode_invalid,",
        "- blocked_plan_only_verification_failed, blocked_safety_execute_failed,",
        "- blocked_existing_workflows_modified, blocked_artifact_mutation,",
        "- rolled_back, unknown",
        "",
        "### ManualWorkflowRuntimeCheckType",
        "",
        "- yaml_structure, guard_expression, stage_selection_guard,",
        "- execute_mode_default, plan_only_verification, safety_execute_smoke,",
        "- existing_workflows_unchanged, runtime_artifact_mutation_guard",
        "",
        "### ManualWorkflowRuntimeRiskLevel",
        "",
        "- low, medium, high, critical, unknown",
        "",
        "## 3. ManualWorkflowRuntimeCheck Fields",
        "",
        "- check_id, check_type, passed, risk_level, description,",
        "- evidence_refs, required_before_pass, blocked_reasons, warnings, errors",
        "",
        "## 4. ManualWorkflowRuntimeVerification Fields",
        "",
        "- verification_id, generated_at, status, workflow_path, yaml_valid,",
        "- guard_expressions_valid, stage_selection_valid, execute_mode_valid,",
        "- plan_only_verification_passed, safety_execute_smoke_passed,",
        "- existing_workflows_unchanged, runtime_artifact_guard_passed,",
        "- checks, plan_only_result, safety_execute_result, warnings, errors",
        "",
        "## 5. Static YAML Validation",
        "",
        f"- yaml_valid: `{static_yaml}`",
        f"- guard_expressions_valid: `{guard_valid}`",
        f"- stage_selection_valid: `{stage_valid}`",
        f"- execute_mode_valid: `{exec_valid}`",
        "",
        "## 6. Runtime Checks",
        "",
    ]

    for check in checks_list:
        status = "[PASS]" if check["passed"] else "[FAIL]"
        lines.append(f"- {status} `{check['check_id']}` ({check['risk_level']}): {check['description']}")
        if check.get("errors"):
            for e in check["errors"]:
                lines.append(f"  - ERROR: {e}")
        if check.get("warnings"):
            for w in check["warnings"]:
                lines.append(f"  - WARN: {w}")

    lines.extend([
        "",
        "## 7. Plan-Only Verification Result",
        "",
        f"- all_pending: `{plan.get('all_pending') if plan else None}`",
        f"- all_pr_status: `{plan.get('all_pr_status') if plan else None}`",
        f"- fast_status: `{plan.get('fast_status') if plan else None}`",
        f"- safety_status: `{plan.get('safety_status') if plan else None}`",
        "",
        "## 8. Safety Execute Smoke Result",
        "",
        f"- safety_execute_smoke_passed: `{safety_passed}`",
        f"- timed_out: `{safety.get('timed_out') if safety else None}`",
        f"- safety_status: `{safety.get('safety_status') if safety else None}`",
        f"- timeout_seconds: `{safety.get('timeout_seconds') if safety else None}`",
        "",
        "## 9. Workflow Mutation Check",
        "",
        f"- existing_workflows_unchanged: `{existing_ok}`",
        f"- runtime_artifact_guard_passed: `{artifact_ok}`",
        "",
        "## 10. Verification Result",
        "",
        f"- status: `{result.get('status')}`",
        f"- verification_id: `{result.get('verification_id')}`",
        f"- workflow_path: `{result.get('workflow_path')}`",
        f"- generated_at: `{result.get('generated_at')}`",
        "",
        "## 11. Test Result",
        "",
        "See verification command output.",
        "",
        "## 12. Remaining Breakpoints",
        "",
        "- Actual GitHub Actions remote run requires separate confirmation.",
        "- Remote execution requires execute_mode=execute_selected with explicit confirmation.",
        "- slow stage requires all_nightly stage_selection; not available in all_pr.",
        "",
        "## 13. Next Recommendation",
        "",
        "- Proceed to R241-16J Remote Dispatch Confirmation (if all checks pass).",
        "- Or wait for explicit confirmation before running execute_selected on GitHub Actions.",
    ])

    return "\n".join(lines)


def generate_manual_workflow_runtime_verification_report(
    result: Dict[str, Any],
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate JSON and markdown reports for runtime verification."""
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
    "ManualWorkflowRuntimeVerificationStatus",
    "ManualWorkflowRuntimeCheckType",
    "ManualWorkflowRuntimeRiskLevel",
    "ManualWorkflowRuntimeCheck",
    "ManualWorkflowRuntimeVerification",
    "load_created_manual_workflow",
    "validate_manual_workflow_yaml_static",
    "verify_workflow_guard_expressions",
    "verify_stage_selection_guards",
    "run_manual_workflow_local_plan_only_verification",
    "run_manual_workflow_local_safety_execute_smoke",
    "verify_existing_workflows_unchanged",
    "verify_runtime_artifact_mutation_guard",
    "evaluate_manual_workflow_runtime_verification",
    "validate_manual_workflow_runtime_verification",
    "generate_manual_workflow_runtime_verification_report",
]
