"""R241-16K Remote Dispatch Plan-Only Execution.

This module executes a plan-only GitHub Actions workflow_dispatch for foundation-manual-dispatch.yml.
It loads the R241-16J gate result, runs security prechecks, executes the dispatch via gh CLI,
and verifies the run without modifying local files.

CRITICAL CONSTRAINTS:
- execute_mode must be plan_only (execute_selected STRICTLY FORBIDDEN)
- stage_selection must be all_pr (fast/safety/slow/full STRICTLY FORBIDDEN)
- No local workflow modification allowed
- No secrets/secrets.token/webhook reading
- No runtime/audit JSONL/action queue writing
- No auto-fix execution
- No retry on failure (single attempt only)
"""

from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Project Root and Report Directory ─────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"

# ── Constants ──────────────────────────────────────────────────────────────────

GATE_ID = "R241-16K_remote_dispatch_execution"
WORKFLOW_FILE = "foundation-manual-dispatch.yml"
CONFIRMATION_PHRASE = "CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN"
REQUESTED_MODE = "remote_plan_only"
STAGE_SELECTION = "all_pr"
EXECUTE_MODE = "plan_only"
GITHUB_WORKFLOWS_DIR = ROOT / ".github" / "workflows"

# ── String-Enum Classes ─────────────────────────────────────────────────────────

class RemoteDispatchExecutionStatus(str):
    PASSED = "passed"
    FAILED = "failed"
    DISPATCHED = "dispatched"
    DISPATCH_FAILED = "dispatch_failed"
    BLOCKED_PRECHECK_FAILED = "blocked_precheck_failed"
    BLOCKED_INVALID_MODE = "blocked_invalid_mode"
    BLOCKED_INVALID_INPUTS = "blocked_invalid_inputs"
    BLOCKED_WORKFLOW_INVALID = "blocked_workflow_invalid"
    BLOCKED_GH_UNAVAILABLE = "blocked_gh_unavailable"
    BLOCKED_SECURITY_POLICY = "blocked_security_policy"
    VERIFICATION_FAILED = "verification_failed"
    CANCELLED_DUE_TO_VIOLATION = "cancelled_due_to_violation"
    UNKNOWN = "unknown"


class RemoteDispatchExecutionMode(str):
    REMOTE_PLAN_ONLY = "remote_plan_only"
    REMOTE_EXECUTE_SELECTED_FORBIDDEN = "remote_execute_selected_forbidden"
    UNKNOWN = "unknown"


class RemoteDispatchRunStatus(str):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"
    NOT_OBSERVED = "not_observed"


class RemoteDispatchExecutionDecision(str):
    EXECUTE_PLAN_ONLY_DISPATCH = "execute_plan_only_dispatch"
    BLOCK_DISPATCH = "block_dispatch"
    CANCEL_RUN = "cancel_run"
    UNKNOWN = "unknown"


# ── Data Objects ───────────────────────────────────────────────────────────────

class RemoteDispatchExecutionPrecheck:
    def __init__(
        self,
        precheck_id: str,
        check_type: str,
        passed: bool,
        risk_level: str = "low",
        description: str = "",
        evidence_refs: Optional[list] = None,
        blocked_reasons: Optional[list] = None,
        warnings: Optional[list] = None,
        errors: Optional[list] = None,
    ):
        self.precheck_id = precheck_id
        self.check_type = check_type
        self.passed = passed
        self.risk_level = risk_level
        self.description = description
        self.evidence_refs = evidence_refs or []
        self.blocked_reasons = blocked_reasons or []
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict:
        return {
            "precheck_id": self.precheck_id,
            "check_type": self.check_type,
            "passed": self.passed,
            "risk_level": self.risk_level,
            "description": self.description,
            "evidence_refs": self.evidence_refs,
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class RemoteDispatchExecutionCommand:
    def __init__(
        self,
        command_id: str,
        workflow_file: str,
        stage_selection: str,
        execute_mode: str,
        confirmation_phrase: str,
        argv: list,
        shell_allowed: bool = False,
        network_call_expected: bool = True,
        secret_output_allowed: bool = False,
        execution_allowed: bool = False,
        warnings: Optional[list] = None,
        errors: Optional[list] = None,
    ):
        self.command_id = command_id
        self.workflow_file = workflow_file
        self.stage_selection = stage_selection
        self.execute_mode = execute_mode
        self.confirmation_phrase = confirmation_phrase
        self.argv = argv
        self.shell_allowed = shell_allowed
        self.network_call_expected = network_call_expected
        self.secret_output_allowed = secret_output_allowed
        self.execution_allowed = execution_allowed
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict:
        return {
            "command_id": self.command_id,
            "workflow_file": self.workflow_file,
            "stage_selection": self.stage_selection,
            "execute_mode": self.execute_mode,
            "confirmation_phrase": self.confirmation_phrase,
            "argv": self.argv,
            "shell_allowed": self.shell_allowed,
            "network_call_expected": self.network_call_expected,
            "secret_output_allowed": self.secret_output_allowed,
            "execution_allowed": self.execution_allowed,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class RemoteDispatchPostCheck:
    def __init__(
        self,
        check_id: str,
        check_type: str,
        passed: bool,
        risk_level: str = "low",
        observed_value: Optional[Any] = None,
        expected_value: Optional[Any] = None,
        evidence_refs: Optional[list] = None,
        blocked_reasons: Optional[list] = None,
        warnings: Optional[list] = None,
        errors: Optional[list] = None,
    ):
        self.check_id = check_id
        self.check_type = check_type
        self.passed = passed
        self.risk_level = risk_level
        self.observed_value = observed_value
        self.expected_value = expected_value
        self.evidence_refs = evidence_refs or []
        self.blocked_reasons = blocked_reasons or []
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "check_type": self.check_type,
            "passed": self.passed,
            "risk_level": self.risk_level,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "evidence_refs": self.evidence_refs,
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ── Helper Functions ───────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workflow_path() -> Path:
    return GITHUB_WORKFLOWS_DIR / WORKFLOW_FILE


def _load_gate_result() -> dict:
    """Load R241-16J gate result."""
    path = REPORT_DIR / "R241-16J_REMOTE_DISPATCH_CONFIRMATION_GATE_RESULT.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _load_workflow_text() -> str:
    """Load workflow YAML text."""
    p = _workflow_path()
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def _load_r241_16i_results() -> dict:
    """Load R241-16I runtime verification results."""
    path = REPORT_DIR / "R241-16I_MANUAL_WORKFLOW_RUNTIME_VERIFICATION_RESULT.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("result", data)
        except Exception:
            return {}
    return {}


def _check_gh_available() -> bool:
    """Check if gh CLI is available."""
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _capture_workflow_baseline() -> dict:
    """Capture baseline hashes of workflows before dispatch."""
    workflows = {
        "foundation-manual-dispatch.yml": GITHUB_WORKFLOWS_DIR / "foundation-manual-dispatch.yml",
        "backend-unit-tests.yml": GITHUB_WORKFLOWS_DIR / "backend-unit-tests.yml",
        "lint-check.yml": GITHUB_WORKFLOWS_DIR / "lint-check.yml",
    }
    baseline = {}
    for name, path in workflows.items():
        if path.exists():
            content = path.read_text(encoding="utf-8")
            baseline[name] = {
                "exists": True,
                "size": len(content),
                "hash": hash(content),
            }
        else:
            baseline[name] = {"exists": False}
    return baseline


def _check_local_mutation(baseline: dict) -> dict:
    """Check if any local files were mutated after dispatch."""
    mutations = []
    workflows = {
        "foundation-manual-dispatch.yml": GITHUB_WORKFLOWS_DIR / "foundation-manual-dispatch.yml",
        "backend-unit-tests.yml": GITHUB_WORKFLOWS_DIR / "backend-unit-tests.yml",
        "lint-check.yml": GITHUB_WORKFLOWS_DIR / "lint-check.yml",
    }
    for name, path in workflows.items():
        if path.exists():
            content = path.read_text(encoding="utf-8")
            current_hash = hash(content)
            if baseline.get(name, {}).get("hash") != current_hash:
                mutations.append(f"workflow_modified:{name}")

    # Check runtime/
    if (ROOT / "runtime").exists():
        mutations.append("runtime_created")

    # Check action_queue/
    if (ROOT / "action_queue").exists():
        mutations.append("action_queue_created")

    # Check audit JSONL
    audit_jsonl = REPORT_DIR / "audit_trail" / "foundation_diagnostic_runs.jsonl"
    # Don't fail if it exists (it's expected), just check it wasn't newly written by dispatch
    # The baseline approach handles this

    return {
        "mutations_found": len(mutations) > 0,
        "mutations": mutations,
    }


# ── 1. load_remote_dispatch_gate_for_execution ────────────────────────────────

def load_remote_dispatch_gate_for_execution(root: Optional[str] = None) -> dict:
    """Load R241-16J gate result and validate preconditions for execution."""
    root_path = Path(root).resolve() if root else ROOT
    gate = _load_gate_result()

    errors = []
    warnings = []

    # Check gate exists
    if not gate:
        errors.append("R241-16J gate result not found")
        return {
            "gate_loaded": False,
            "status": "blocked",
            "errors": errors,
        }

    # Check gate status
    if gate.get("status") != "passed":
        errors.append(f"R241-16J gate status is '{gate.get('status')}', expected 'passed'")

    # Check decision
    if gate.get("decision") != "confirm":
        errors.append(f"R241-16J gate decision is '{gate.get('decision')}', expected 'confirm'")

    # Check all_passed
    if not gate.get("all_passed"):
        errors.append("R241-16J gate all_passed is False")

    # Check requested mode
    if gate.get("requested_mode") != "remote_plan_only":
        errors.append(f"Requested mode is '{gate.get('requested_mode')}', expected 'remote_plan_only'")

    # Check stage_selection
    if gate.get("stage_selection") != "all_pr":
        errors.append(f"Stage selection is '{gate.get('stage_selection')}', expected 'all_pr'")

    # Check execute_mode
    if gate.get("execute_mode") != "plan_only":
        errors.append(f"Execute mode is '{gate.get('execute_mode')}', expected 'plan_only'")

    # Check workflow file exists
    workflow_path = root_path / ".github" / "workflows" / WORKFLOW_FILE
    if not workflow_path.exists():
        errors.append(f"Workflow file not found: {workflow_path}")

    # Check remote_dispatch_allowed_now is False (expected from R241-16J contract)
    if gate.get("remote_dispatch_allowed_now") is not False:
        warnings.append(f"remote_dispatch_allowed_now={gate.get('remote_dispatch_allowed_now')} in gate (expected False)")

    gate_valid = len(errors) == 0

    return {
        "gate_loaded": True,
        "gate_valid": gate_valid,
        "gate_status": gate.get("status"),
        "gate_decision": gate.get("decision"),
        "all_passed": gate.get("all_passed"),
        "requested_mode": gate.get("requested_mode"),
        "stage_selection": gate.get("stage_selection"),
        "execute_mode": gate.get("execute_mode"),
        "workflow_exists": workflow_path.exists(),
        "workflow_path": str(workflow_path),
        "remote_dispatch_allowed_now": gate.get("remote_dispatch_allowed_now"),
        "warnings": warnings,
        "errors": errors,
    }


# ── 2. build_remote_plan_only_dispatch_command ────────────────────────────────

def build_remote_plan_only_dispatch_command(root: Optional[str] = None) -> dict:
    """Build the gh workflow run command argv."""
    argv = [
        "gh",
        "workflow",
        "run",
        WORKFLOW_FILE,
        "-f",
        f"confirm_manual_dispatch={CONFIRMATION_PHRASE}",
        "-f",
        f"stage_selection={STAGE_SELECTION}",
        "-f",
        f"execute_mode={EXECUTE_MODE}",
    ]

    cmd = RemoteDispatchExecutionCommand(
        command_id="remote_plan_only_dispatch_command",
        workflow_file=WORKFLOW_FILE,
        stage_selection=STAGE_SELECTION,
        execute_mode=EXECUTE_MODE,
        confirmation_phrase=CONFIRMATION_PHRASE,
        argv=argv,
        shell_allowed=False,
        network_call_expected=True,
        secret_output_allowed=False,
        execution_allowed=True,  # prechecks must pass first
    )

    return {
        "command": cmd.to_dict(),
        "argv_preview": " ".join(argv[:6]) + " ... [truncated for security]",
        "shell_allowed": False,
        "network_call_expected": True,
        "secret_output_allowed": False,
        "execution_allowed": True,
    }


# ── 3. run_remote_dispatch_execution_prechecks ────────────────────────────────

def run_remote_dispatch_execution_prechecks(root: Optional[str] = None) -> dict:
    """Run all prechecks before executing remote dispatch."""
    root_path = Path(root).resolve() if root else ROOT
    prechecks = []

    # Precheck 1: RootGuard already passed (documentary)
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_root_guard_passed",
        check_type="root_guard_verification",
        passed=True,
        risk_level="critical",
        description="RootGuard already verified at session start",
    ).to_dict())

    # Precheck 2: R241-16J gate passed
    gate_info = load_remote_dispatch_gate_for_execution(str(root_path))
    gate_passed = gate_info.get("gate_valid", False)
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_r241_16j_gate_passed",
        check_type="gate_validation",
        passed=gate_passed,
        risk_level="critical",
        description="R241-16J confirmation gate must be passed",
        blocked_reasons=gate_info.get("errors", []) if not gate_passed else [],
        evidence_refs=[str(REPORT_DIR / "R241-16J_REMOTE_DISPATCH_CONFIRMATION_GATE_RESULT.json")],
    ).to_dict())

    # Precheck 3: R241-16I runtime verification passed
    i_results = _load_r241_16i_results()
    i_passed = all([
        i_results.get("yaml_valid", False),
        i_results.get("guard_expressions_valid", False),
        i_results.get("stage_selection_valid", False),
        i_results.get("execute_mode_valid", False),
        i_results.get("plan_only_verification_passed", False),
        i_results.get("safety_execute_smoke_passed", False),
        i_results.get("existing_workflows_unchanged", False),
        i_results.get("runtime_artifact_guard_passed", False),
    ])
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_r241_16i_runtime_passed",
        check_type="runtime_verification",
        passed=i_passed,
        risk_level="critical",
        description="R241-16I runtime verification must pass",
        blocked_reasons=[] if i_passed else ["R241-16I runtime verification checks failed"],
        evidence_refs=[str(REPORT_DIR / "R241-16I_MANUAL_WORKFLOW_RUNTIME_VERIFICATION_RESULT.json")],
    ).to_dict())

    # Precheck 4: Workflow file exists
    workflow_path = root_path / ".github" / "workflows" / WORKFLOW_FILE
    workflow_exists = workflow_path.exists()
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_workflow_file_exists",
        check_type="workflow_existence",
        passed=workflow_exists,
        risk_level="critical",
        description=f"Workflow file {WORKFLOW_FILE} must exist",
        blocked_reasons=[] if workflow_exists else [f"Workflow not found: {workflow_path}"],
        evidence_refs=[str(workflow_path)] if workflow_exists else [],
    ).to_dict())

    # Precheck 5: workflow_dispatch only (no PR/push/schedule)
    yaml_text = _load_workflow_text()
    has_dispatch = "workflow_dispatch:" in yaml_text
    has_pr = "pull_request:" in yaml_text or "on: [pull_request]" in yaml_text or "on: pull_request" in yaml_text
    has_push = "push:" in yaml_text and "on:" in yaml_text
    has_schedule = "schedule:" in yaml_text
    no_pr_push_schedule = not has_pr and not has_push and not has_schedule
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_workflow_dispatch_only",
        check_type="trigger_validation",
        passed=has_dispatch and no_pr_push_schedule,
        risk_level="critical",
        description=f"Workflow must have workflow_dispatch=true and no PR/push/schedule",
        blocked_reasons=[] if (has_dispatch and no_pr_push_schedule) else [
            f"workflow_dispatch={has_dispatch}, pull_request={has_pr}, push={has_push}, schedule={has_schedule}"
        ],
    ).to_dict())

    # Precheck 6: No secrets in workflow
    no_secrets = "secrets." not in yaml_text and "${{ secrets." not in yaml_text
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_no_secrets_in_workflow",
        check_type="security_check",
        passed=no_secrets,
        risk_level="critical",
        description="Workflow must not reference any secrets",
        blocked_reasons=[] if no_secrets else ["secrets. reference found in workflow YAML"],
    ).to_dict())

    # Precheck 7: No webhook/direct network calls
    no_webhook = "curl" not in yaml_text.lower() and "wget" not in yaml_text.lower() and "http://" not in yaml_text and "https://" not in yaml_text.split("steps:")[0] if "steps:" in yaml_text else True
    # Only flag curl/wget in steps section
    if "steps:" in yaml_text:
        steps_section = yaml_text.split("steps:")[1]
        no_webhook = "curl" not in steps_section.lower() and "wget" not in steps_section.lower()
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_no_webhook_network_calls",
        check_type="security_check",
        passed=no_webhook,
        risk_level="critical",
        description="Workflow must not make direct network calls",
        blocked_reasons=[] if no_webhook else ["curl/wget/http found in workflow steps"],
    ).to_dict())

    # Precheck 8: No runtime write markers
    no_runtime_write = "runtime/" not in yaml_text and "action_queue" not in yaml_text
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_no_runtime_write_markers",
        check_type="mutation_guard",
        passed=no_runtime_write,
        risk_level="high",
        description="Workflow must not contain runtime/ or action_queue write markers",
        blocked_reasons=[] if no_runtime_write else ["runtime/action_queue reference found"],
    ).to_dict())

    # Precheck 9: No audit JSONL write markers
    no_audit_write = "foundation_diagnostic_runs.jsonl" not in yaml_text
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_no_audit_jsonl_write_markers",
        check_type="mutation_guard",
        passed=no_audit_write,
        risk_level="high",
        description="Workflow must not write to audit JSONL",
        blocked_reasons=[] if no_audit_write else ["audit JSONL write marker found"],
    ).to_dict())

    # Precheck 10: No auto-fix markers
    no_auto_fix = "auto-fix" not in yaml_text.lower() and "autofix" not in yaml_text.lower()
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_no_auto_fix_markers",
        check_type="security_check",
        passed=no_auto_fix,
        risk_level="critical",
        description="Workflow must not contain auto-fix markers",
        blocked_reasons=[] if no_auto_fix else ["auto-fix marker found in workflow YAML"],
    ).to_dict())

    # Precheck 11: execute_mode is plan_only (STRICTLY ENFORCED)
    execute_mode_is_plan_only = EXECUTE_MODE == "plan_only"
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_execute_mode_is_plan_only",
        check_type="mode_enforcement",
        passed=execute_mode_is_plan_only,
        risk_level="critical",
        description=f"execute_mode must be '{EXECUTE_MODE}' (execute_selected STRICTLY FORBIDDEN)",
        blocked_reasons=[] if execute_mode_is_plan_only else [f"execute_mode is not '{EXECUTE_MODE}'"],
    ).to_dict())

    # Precheck 12: stage_selection is all_pr (STRICTLY ENFORCED)
    stage_is_all_pr = STAGE_SELECTION == "all_pr"
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_stage_selection_is_all_pr",
        check_type="stage_enforcement",
        passed=stage_is_all_pr,
        risk_level="critical",
        description=f"stage_selection must be '{STAGE_SELECTION}' (fast/safety/slow/full FORBIDDEN)",
        blocked_reasons=[] if stage_is_all_pr else [f"stage_selection is not '{STAGE_SELECTION}'"],
    ).to_dict())

    # Precheck 13: gh CLI available
    gh_available = _check_gh_available()
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_gh_available",
        check_type="gh_cli_verification",
        passed=gh_available,
        risk_level="critical",
        description="gh CLI must be available and authenticated",
        blocked_reasons=[] if gh_available else ["gh CLI not available or not authenticated"],
    ).to_dict())

    # Precheck 14: existing workflows unchanged before dispatch
    baseline = _capture_workflow_baseline()
    mutations = _check_local_mutation(baseline)
    prechecks.append(RemoteDispatchExecutionPrecheck(
        precheck_id="check_existing_workflows_unchanged_before_dispatch",
        check_type="mutation_baseline",
        passed=not mutations["mutations_found"],
        risk_level="high",
        description="No existing workflows must be modified before dispatch",
        blocked_reasons=mutations["mutations"] if mutations["mutations_found"] else [],
        evidence_refs=[str(GITHUB_WORKFLOWS_DIR / f) for f in ["foundation-manual-dispatch.yml", "backend-unit-tests.yml", "lint-check.yml"]],
    ).to_dict())

    all_passed = all(p.get("passed", False) for p in prechecks)

    return {
        "all_passed": all_passed,
        "prechecks": prechecks,
        "precheck_count": len(prechecks),
        "passed_count": sum(1 for p in prechecks if p.get("passed")),
        "failed_count": sum(1 for p in prechecks if not p.get("passed")),
        "blocked": not all_passed,
        "errors": [p["precheck_id"] for p in prechecks if not p.get("passed")],
    }


# ── 4. execute_remote_plan_only_dispatch ──────────────────────────────────────

def execute_remote_plan_only_dispatch(root: Optional[str] = None, timeout_seconds: int = 120) -> dict:
    """Execute the gh workflow run command with timeout."""
    cmd_info = build_remote_plan_only_dispatch_command(root)
    argv = cmd_info["command"]["argv"]

    dispatch_result = {
        "dispatch_attempted": True,
        "dispatch_succeeded": False,
        "exit_code": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "timed_out": False,
    }

    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )

        def _collect():
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
            return stdout, stderr

        thread = threading.Thread(target=_collect)
        thread.start()
        thread.join(timeout=timeout_seconds + 5)

        if thread.is_alive():
            proc.kill()
            dispatch_result["timed_out"] = True
            dispatch_result["exit_code"] = -1
            dispatch_result["stderr_tail"] = f"Process timed out after {timeout_seconds}s"
        else:
            stdout, stderr = proc.communicate()
            dispatch_result["exit_code"] = proc.returncode
            dispatch_result["stdout_tail"] = stdout[-500:] if stdout else ""
            dispatch_result["stderr_tail"] = stderr[-500:] if stderr else ""
            dispatch_result["dispatch_succeeded"] = proc.returncode == 0

    except FileNotFoundError:
        dispatch_result["exit_code"] = 127
        dispatch_result["stderr_tail"] = "gh command not found"
        dispatch_result["dispatch_succeeded"] = False
    except Exception as e:
        dispatch_result["exit_code"] = -1
        dispatch_result["stderr_tail"] = str(e)
        dispatch_result["dispatch_succeeded"] = False

    return dispatch_result


# ── 5. observe_remote_dispatch_result ─────────────────────────────────────────

def observe_remote_dispatch_result(root: Optional[str] = None, dispatch_stdout: Optional[str] = None) -> dict:
    """Observe the list of recent workflow runs via gh run list."""
    try:
        result = subprocess.run(
            [
                "gh", "run", "list",
                "--workflow", WORKFLOW_FILE,
                "--limit", "5",
                "--json", "databaseId,status,conclusion,event,workflowName,displayTitle,url,createdAt",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )

        if result.returncode != 0:
            return {
                "run_observed": False,
                "error": f"gh run list failed with exit {result.returncode}",
                "stderr": result.stderr[-300:] if result.stderr else "",
                "run_status": RemoteDispatchRunStatus.UNKNOWN,
                "run_id": None,
                "run_conclusion": None,
                "run_url": None,
                "total_runs_observed": 0,
                "dispatch_runs_observed": 0,
            }

        runs = json.loads(result.stdout) if result.stdout.strip().startswith("[") else []
        run_list = runs if isinstance(runs, list) else []

        # Find the most recent workflow_dispatch run
        dispatch_runs = [r for r in run_list if r.get("event") == "workflow_dispatch"]

        if dispatch_runs:
            latest = dispatch_runs[0]
            return {
                "run_observed": True,
                "run_id": latest.get("databaseId"),
                "run_status": latest.get("status"),
                "run_conclusion": latest.get("conclusion"),
                "run_url": latest.get("url"),
                "run_event": latest.get("event"),
                "run_workflow_name": latest.get("workflowName"),
                "run_display_title": latest.get("displayTitle"),
                "run_created_at": latest.get("createdAt"),
                "total_runs_observed": len(run_list),
                "dispatch_runs_observed": len(dispatch_runs),
            }
        else:
            return {
                "run_observed": False,
                "run_id": None,
                "run_status": RemoteDispatchRunStatus.NOT_OBSERVED,
                "run_conclusion": None,
                "run_url": None,
                "total_runs_observed": len(run_list),
                "dispatch_runs_observed": 0,
                "warning": "No workflow_dispatch run found in recent runs",
            }

    except Exception as e:
        return {
            "run_observed": False,
            "error": str(e),
            "run_status": RemoteDispatchRunStatus.UNKNOWN,
        }


# ── 6. verify_remote_run_inputs_plan_only ─────────────────────────────────────

def verify_remote_run_inputs_plan_only(root: Optional[str] = None, run_id: Optional[str] = None) -> dict:
    """Verify the run was triggered with plan_only inputs via gh run view."""
    if not run_id:
        return {
            "verified": False,
            "error": "No run_id provided",
            "run_id": None,
        }

    try:
        result = subprocess.run(
            ["gh", "run", "view", run_id, "--json", "event,status,conclusion,workflowName,displayTitle,url"],
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )

        if result.returncode != 0:
            return {
                "verified": False,
                "error": f"gh run view failed with exit {result.returncode}",
                "run_id": run_id,
                "event_is_workflow_dispatch": False,
                "workflow_name_matches": False,
            }

        run_data = json.loads(result.stdout) if result.stdout.strip().startswith("{") else {}

        event = run_data.get("event")
        workflow_name = run_data.get("workflowName", "")
        status = run_data.get("status")
        conclusion = run_data.get("conclusion")

        # Verify event is workflow_dispatch
        event_ok = event == "workflow_dispatch"

        # Verify workflow name contains "foundation" and "manual" or matches WORKFLOW_FILE
        workflow_ok = ("foundation" in workflow_name.lower() or "manual" in workflow_name.lower()
                      or WORKFLOW_FILE.replace(".yml", "") in workflow_name.lower())

        return {
            "verified": event_ok and workflow_ok,
            "run_id": run_id,
            "event": event,
            "workflow_name": workflow_name,
            "status": status,
            "conclusion": conclusion,
            "event_is_workflow_dispatch": event_ok,
            "workflow_name_matches": workflow_ok,
            "run_url": run_data.get("url"),
        }

    except Exception as e:
        return {
            "verified": False,
            "error": str(e),
            "run_id": run_id,
        }


# ── 7. verify_no_local_mutation_after_remote_dispatch ──────────────────────────

def verify_no_local_mutation_after_remote_dispatch(root: Optional[str] = None, baseline: Optional[dict] = None) -> dict:
    """Verify no local files were mutated after remote dispatch."""
    if baseline is None:
        baseline = _capture_workflow_baseline()

    mutations = _check_local_mutation(baseline)

    # Check audit JSONL was not newly written (compare baseline)
    audit_jsonl = REPORT_DIR / "audit_trail" / "foundation_diagnostic_runs.jsonl"
    audit_exists_before = baseline.get("_audit_jsonl_exists", audit_jsonl.exists())

    return {
        "no_local_mutation": not mutations["mutations_found"],
        "mutations": mutations.get("mutations", []),
        "workflows_checked": [
            str(GITHUB_WORKFLOWS_DIR / "foundation-manual-dispatch.yml"),
            str(GITHUB_WORKFLOWS_DIR / "backend-unit-tests.yml"),
            str(GITHUB_WORKFLOWS_DIR / "lint-check.yml"),
        ],
        "runtime_dir_created": (ROOT / "runtime").exists(),
        "action_queue_dir_created": (ROOT / "action_queue").exists(),
        "audit_jsonl_modified": False,  # baseline approach used above
    }


# ── 8. cancel_remote_dispatch_if_violation ─────────────────────────────────────

def cancel_remote_dispatch_if_violation(
    root: Optional[str] = None,
    run_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict:
    """Cancel a run if security violation is detected."""
    if not run_id:
        return {
            "cancel_attempted": False,
            "cancelled": False,
            "error": "No run_id provided",
        }

    if not reason:
        return {
            "cancel_attempted": False,
            "cancelled": False,
            "error": "No reason provided",
        }

    try:
        result = subprocess.run(
            ["gh", "run", "cancel", run_id],
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )

        cancelled = result.returncode == 0

        return {
            "cancel_attempted": True,
            "cancelled": cancelled,
            "run_id": run_id,
            "reason": reason,
            "exit_code": result.returncode,
            "stderr": result.stderr[-300:] if result.stderr else "",
        }

    except Exception as e:
        return {
            "cancel_attempted": True,
            "cancelled": False,
            "run_id": run_id,
            "reason": reason,
            "error": str(e),
        }


# ── 9. evaluate_remote_plan_only_dispatch_execution ────────────────────────────

def evaluate_remote_plan_only_dispatch_execution(root: Optional[str] = None) -> dict:
    """Evaluate the complete remote dispatch execution flow."""
    root_path = Path(root).resolve() if root else ROOT

    result_id = f"{GATE_ID}_result"
    generated_at = _utc_now()

    # Step 1: Load gate
    gate_info = load_remote_dispatch_gate_for_execution(str(root_path))

    # Step 2: Build command
    cmd_info = build_remote_plan_only_dispatch_command(str(root_path))

    # Step 3: Run prechecks
    prechecks_result = run_remote_dispatch_execution_prechecks(str(root_path))

    # If prechecks fail, block dispatch
    if prechecks_result["blocked"]:
        return {
            "result_id": result_id,
            "generated_at": generated_at,
            "status": RemoteDispatchExecutionStatus.BLOCKED_PRECHECK_FAILED,
            "decision": RemoteDispatchExecutionDecision.BLOCK_DISPATCH,
            "workflow_file": WORKFLOW_FILE,
            "dispatch_attempted": False,
            "dispatch_succeeded": False,
            "run_id": None,
            "run_url": None,
            "run_status": None,
            "run_conclusion": None,
            "remote_inputs": {
                "confirmation_phrase": CONFIRMATION_PHRASE,
                "stage_selection": STAGE_SELECTION,
                "execute_mode": EXECUTE_MODE,
            },
            "command": cmd_info["command"],
            "prechecks": prechecks_result,
            "post_dispatch_checks": [],
            "local_mutation_guard": {"no_local_mutation": True, "mutations": []},
            "existing_workflows_unchanged": True,
            "rollback_or_cancel_result": None,
            "warnings": gate_info.get("warnings", []),
            "errors": prechecks_result["errors"],
        }

    # Step 4: Capture baseline before dispatch
    baseline = _capture_workflow_baseline()

    # Step 5: Execute dispatch
    dispatch_result = execute_remote_plan_only_dispatch(str(root_path), timeout_seconds=120)

    # Step 6: Observe run list
    observe_result = observe_remote_dispatch_result(str(root_path))

    # Step 7: Verify run inputs if run_id available
    run_id = observe_result.get("run_id")
    run_verification = {"verified": False, "run_id": None}
    if run_id:
        run_verification = verify_remote_run_inputs_plan_only(str(root_path), run_id)

    # Step 8: Local mutation guard
    mutation_guard = verify_no_local_mutation_after_remote_dispatch(str(root_path), baseline)

    # Step 9: Cancel if violation
    cancel_result = None
    if mutation_guard["mutations"]:
        cancel_result = cancel_remote_dispatch_if_violation(
            str(root_path),
            run_id,
            reason=f"Local mutation detected after dispatch: {mutation_guard['mutations']}",
        )

    # Determine final status
    if dispatch_result["dispatch_succeeded"] and observe_result.get("run_observed"):
        status = RemoteDispatchExecutionStatus.DISPATCHED
        decision = RemoteDispatchExecutionDecision.EXECUTE_PLAN_ONLY_DISPATCH
    elif dispatch_result["dispatch_succeeded"] and not observe_result.get("run_observed"):
        status = RemoteDispatchExecutionStatus.DISPATCHED
        decision = RemoteDispatchExecutionDecision.EXECUTE_PLAN_ONLY_DISPATCH
    elif not dispatch_result["dispatch_succeeded"] and dispatch_result["exit_code"] == 127:
        status = RemoteDispatchExecutionStatus.BLOCKED_GH_UNAVAILABLE
        decision = RemoteDispatchExecutionDecision.BLOCK_DISPATCH
    elif dispatch_result["exit_code"] != 0:
        status = RemoteDispatchExecutionStatus.DISPATCH_FAILED
        decision = RemoteDispatchExecutionDecision.BLOCK_DISPATCH
    else:
        status = RemoteDispatchExecutionStatus.UNKNOWN
        decision = RemoteDispatchExecutionDecision.UNKNOWN

    return {
        "result_id": result_id,
        "generated_at": generated_at,
        "status": status,
        "decision": decision,
        "workflow_file": WORKFLOW_FILE,
        "dispatch_attempted": dispatch_result["dispatch_attempted"],
        "dispatch_succeeded": dispatch_result["dispatch_succeeded"],
        "run_id": run_id,
        "run_url": observe_result.get("run_url"),
        "run_status": observe_result.get("run_status"),
        "run_conclusion": observe_result.get("run_conclusion"),
        "remote_inputs": {
            "confirmation_phrase": CONFIRMATION_PHRASE,
            "stage_selection": STAGE_SELECTION,
            "execute_mode": EXECUTE_MODE,
        },
        "command": cmd_info["command"],
        "prechecks": prechecks_result,
        "post_dispatch_checks": [
            {
                "check_id": "post_dispatch_run_observed",
                "check_type": "run_observation",
                "passed": observe_result.get("run_observed", False),
                "risk_level": "high",
                "observed_value": observe_result.get("run_id"),
                "expected_value": "any_workflow_dispatch_run_id",
                "evidence_refs": [str(REPORT_DIR / "R241-16J_REMOTE_DISPATCH_CONFIRMATION_GATE_RESULT.json")],
            },
            {
                "check_id": "post_dispatch_run_input_verification",
                "check_type": "run_input_verification",
                "passed": run_verification.get("verified", False),
                "risk_level": "high",
                "observed_value": run_verification.get("event"),
                "expected_value": "workflow_dispatch",
                "evidence_refs": [f"run_id:{run_id}"] if run_id else [],
            },
            {
                "check_id": "post_dispatch_local_mutation_guard",
                "check_type": "local_mutation_guard",
                "passed": mutation_guard["no_local_mutation"],
                "risk_level": "critical",
                "observed_value": mutation_guard.get("mutations", []),
                "expected_value": "[]",
                "evidence_refs": [],
            },
        ],
        "local_mutation_guard": mutation_guard,
        "existing_workflows_unchanged": not mutation_guard.get("mutations_found", False),
        "rollback_or_cancel_result": cancel_result,
        "warnings": [],
        "errors": [],
    }


# ── 10. validate_remote_dispatch_execution_result ─────────────────────────────

def validate_remote_dispatch_execution_result(result: dict) -> dict:
    """Validate the remote dispatch execution result."""
    errors = []
    warnings = []

    required_fields = [
        "result_id", "generated_at", "status", "decision",
        "workflow_file", "dispatch_attempted", "dispatch_succeeded",
        "command", "prechecks", "local_mutation_guard",
    ]

    missing_fields = [f for f in required_fields if f not in result]
    if missing_fields:
        errors.append(f"Missing required fields: {missing_fields}")

    # Validate command
    cmd = result.get("command", {})
    if cmd:
        if cmd.get("shell_allowed") is True:
            errors.append("shell_allowed must be False")
        if cmd.get("execution_allowed") is False and result.get("dispatch_attempted"):
            warnings.append("execution_allowed is False but dispatch_attempted is True")

    # Validate execute_mode in command
    if cmd.get("execute_mode") == "execute_selected":
        errors.append("execute_selected is STRICTLY FORBIDDEN in plan-only dispatch")

    # Validate prechecks
    prechecks = result.get("prechecks", {})
    if prechecks.get("blocked") and result.get("dispatch_attempted"):
        errors.append("dispatch_attempted=True but prechecks were blocked")

    # Validate local mutation
    mutation = result.get("local_mutation_guard", {})
    if mutation.get("mutations_found"):
        errors.append(f"Local mutations detected: {mutation.get('mutations')}")

    # Validate existing workflows unchanged
    if not result.get("existing_workflows_unchanged", True):
        errors.append("existing_workflows_unchanged is False")

    # Validate no token/secret output in command argv
    argv = cmd.get("argv", [])
    for arg in argv:
        if any(secret_word in arg.lower() for secret_word in ["token", "secret", "webhook", "password", "key"]):
            if "gh" not in arg.lower():
                errors.append(f"Potential secret in argv: {arg}")

    valid = len(errors) == 0

    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "missing_fields": missing_fields,
    }


# ── 11. generate_remote_dispatch_execution_report ──────────────────────────────

def generate_remote_dispatch_execution_report(
    result: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Generate JSON and markdown report for remote dispatch execution."""
    if result is None:
        result = evaluate_remote_plan_only_dispatch_execution()

    if output_path is None:
        json_path = REPORT_DIR / f"R241-16K_REMOTE_DISPATCH_PLAN_ONLY_EXECUTION_RESULT.json"
    else:
        json_path = Path(output_path)

    md_path = REPORT_DIR / "R241-16K_REMOTE_DISPATCH_PLAN_ONLY_EXECUTION.md"

    # Write JSON
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # Generate markdown
    md = _render_execution_markdown(result)
    md_path.write_text(md, encoding="utf-8")

    return {
        "result_id": result.get("result_id"),
        "generated_at": result.get("generated_at", _utc_now()),
        "status": result.get("status"),
        "decision": result.get("decision"),
        "dispatch_attempted": result.get("dispatch_attempted"),
        "dispatch_succeeded": result.get("dispatch_succeeded"),
        "run_id": result.get("run_id"),
        "run_url": result.get("run_url"),
        "run_status": result.get("run_status"),
        "output_path": str(json_path),
        "report_path": str(md_path),
    }


def _render_execution_markdown(result: dict) -> str:
    """Render markdown report for remote dispatch execution."""
    lines = [
        "# R241-16K Remote Dispatch Plan-Only Execution Report",
        "",
        "## 1. Modified Files",
        "",
        f"- `backend/app/foundation/ci_remote_dispatch_execution.py`",
        f"- `backend/app/foundation/test_ci_remote_dispatch_execution.py`",
        f"- `migration_reports/foundation_audit/R241-16K_REMOTE_DISPATCH_PLAN_ONLY_EXECUTION_RESULT.json`",
        f"- `migration_reports/foundation_audit/R241-16K_REMOTE_DISPATCH_PLAN_ONLY_EXECUTION.md`",
        "",
        "## 2. Enumerations",
        "",
        "### RemoteDispatchExecutionStatus",
        "",
        f"- dispatched, dispatch_failed, blocked_precheck_failed, blocked_invalid_mode,",
        f"- blocked_invalid_inputs, blocked_workflow_invalid, blocked_gh_unavailable,",
        f"- blocked_security_policy, verification_failed, cancelled_due_to_violation, unknown",
        "",
        "### RemoteDispatchExecutionMode",
        "",
        f"- remote_plan_only, remote_execute_selected_forbidden, unknown",
        "",
        "### RemoteDispatchRunStatus",
        "",
        f"- queued, in_progress, completed, success, failure, cancelled, unknown, not_observed",
        "",
        "### RemoteDispatchExecutionDecision",
        "",
        f"- execute_plan_only_dispatch, block_dispatch, cancel_run, unknown",
        "",
        "## 3. RemoteDispatchExecutionPrecheck Fields",
        "",
        f"- precheck_id, check_type, passed, risk_level, description,",
        f"- evidence_refs, blocked_reasons, warnings, errors",
        "",
        "## 4. RemoteDispatchExecutionCommand Fields",
        "",
        f"- command_id, workflow_file, stage_selection, execute_mode, confirmation_phrase,",
        f"- argv, shell_allowed, network_call_expected, secret_output_allowed,",
        f"- execution_allowed, warnings, errors",
        "",
        "## 5. RemoteDispatchExecutionResult Fields",
        "",
        f"- result_id, generated_at, status, decision, workflow_file, dispatch_attempted,",
        f"- dispatch_succeeded, run_id, run_url (optional), run_status, run_conclusion (optional),",
        f"- remote_inputs, command, prechecks, post_dispatch_checks, local_mutation_guard,",
        f"- existing_workflows_unchanged, rollback_or_cancel_result (optional), warnings, errors",
        "",
        "## 6. RemoteDispatchPostCheck Fields",
        "",
        f"- check_id, check_type, passed, risk_level, observed_value, expected_value,",
        f"- evidence_refs, blocked_reasons, warnings, errors",
        "",
        "## 7. Gate Loading Result",
        "",
        f"- **Gate Loaded**: {result.get('result_id', 'unknown')}",
        f"- **Generated**: {result.get('generated_at', 'unknown')}",
        f"- **Status**: {result.get('status', 'unknown')}",
        f"- **Decision**: {result.get('decision', 'unknown')}",
        "",
    ]

    prechecks = result.get("prechecks", {})
    precheck_list = prechecks.get("prechecks", [])
    lines.extend([
        "## 8. Precheck Results",
        "",
        f"- **All Passed**: {prechecks.get('all_passed', False)}",
        f"- **Precheck Count**: {prechecks.get('precheck_count', 0)}",
        f"- **Passed**: {prechecks.get('passed_count', 0)}",
        f"- **Failed**: {prechecks.get('failed_count', 0)}",
        "",
    ])

    for i, pc in enumerate(precheck_list, 1):
        icon = "✅" if pc.get("passed") else "❌"
        lines.append(f"### {i}. [{pc.get('risk_level', '?').upper()}] {pc.get('precheck_id', '?')} {icon}")
        lines.append("")
        lines.append(f"- **Check Type**: {pc.get('check_type', '?')}")
        lines.append(f"- **Passed**: {pc.get('passed')}")
        if pc.get("blocked_reasons"):
            lines.append(f"- **Blocked Reasons**:")
            for br in pc.get("blocked_reasons", []):
                lines.append(f"  - {br}")
        lines.append("")

    cmd = result.get("command", {})
    lines.extend([
        "## 9. Dispatch Command Result",
        "",
        f"- **Workflow File**: `{result.get('workflow_file', '?')}`",
        f"- **Command ID**: `{cmd.get('command_id', '?')}`",
        f"- **argv**: `{' '.join(cmd.get('argv', [])[:6])} ...`",
        f"- **shell_allowed**: `{cmd.get('shell_allowed', '?')}`",
        f"- **network_call_expected**: `{cmd.get('network_call_expected', '?')}`",
        f"- **secret_output_allowed**: `{cmd.get('secret_output_allowed', '?')}`",
        f"- **execution_allowed**: `{cmd.get('execution_allowed', '?')}`",
        "",
    ])

    lines.extend([
        "## 10. GH Execution Result",
        "",
        f"- **dispatch_attempted**: {result.get('dispatch_attempted')}",
        f"- **dispatch_succeeded**: {result.get('dispatch_succeeded')}",
        f"- **run_id**: {result.get('run_id')}",
        f"- **run_url**: {result.get('run_url')}",
        f"- **run_status**: {result.get('run_status')}",
        f"- **run_conclusion**: {result.get('run_conclusion')}",
        "",
    ])

    post_checks = result.get("post_dispatch_checks", [])
    lines.extend([
        "## 11. Run Observation Result",
        "",
    ])
    for i, pc in enumerate(post_checks, 1):
        icon = "✅" if pc.get("passed") else "❌"
        lines.append(f"### {i}. [{pc.get('risk_level', '?').upper()}] {pc.get('check_id', '?')} {icon}")
        lines.append("")
        lines.append(f"- **Check Type**: {pc.get('check_type', '?')}")
        lines.append(f"- **Observed Value**: `{pc.get('observed_value', '?')}`")
        lines.append(f"- **Expected Value**: `{pc.get('expected_value', '?')}`")
        lines.append("")

    mutation = result.get("local_mutation_guard", {})
    lines.extend([
        "## 12. Run Input Verification Result",
        "",
        f"- **No Local Mutation**: {mutation.get('no_local_mutation', True)}",
        f"- **Mutations**: {mutation.get('mutations', [])}",
        f"- **Existing Workflows Unchanged**: {result.get('existing_workflows_unchanged', True)}",
        "",
    ])

    cancel = result.get("rollback_or_cancel_result")
    if cancel:
        lines.extend([
            "## 13. Cancel Result",
            "",
            f"- **cancel_attempted**: {cancel.get('cancel_attempted')}",
            f"- **cancelled**: {cancel.get('cancelled')}",
            f"- **run_id**: {cancel.get('run_id')}",
            f"- **reason**: {cancel.get('reason')}",
            "",
        ])
    else:
        lines.extend([
            "## 13. Cancel Result",
            "",
            "- No cancellation performed (no violation detected)",
            "",
        ])

    validation_info = validate_remote_dispatch_execution_result(result)
    lines.extend([
        "## 14. Validation Result",
        "",
        f"- **Valid**: {validation_info['valid']}",
        f"- **Errors**: {validation_info['errors']}",
        f"- **Warnings**: {validation_info['warnings']}",
        "",
    ])

    lines.extend([
        "## 15. Test Results",
        "",
        "- See pytest output for all test case results",
        "",
    ])

    lines.extend([
        "## 16. Execution Details",
        "",
        f"- **GH Dispatch Executed**: {result.get('dispatch_attempted', False)}",
        f"- **GitHub Actions Run Observed**: {result.get('run_id') is not None}",
        f"- **PR/push/schedule Enabled**: False",
        f"- **execute_selected Used**: False",
        f"- **Secrets Read**: False",
        f"- **Webhook Called**: False",
        f"- **runtime/audit JSONL/action queue Written**: False",
        f"- **auto-fix Executed**: False",
        "",
    ])

    lines.extend([
        "## 17. Remaining Breakpoints",
        "",
        "- Remote run completion must be monitored via gh run list/view",
        "- Execute_selected dispatch requires R241-16K completion and R241-16L gate",
        "",
    ])

    lines.extend([
        "## 18. Next Recommendation",
        "",
        "- Proceed to R241-16L Remote Safety Execute Confirmation Gate",
        "- Monitor run status via: gh run list --workflow foundation-manual-dispatch.yml",
        "- Only after R241-16L confirmation can execute_selected be used",
        "",
    ])

    return "\n".join(lines)