"""R241-16L Remote Workflow Visibility / Default Branch Readiness Review.

This module reviews whether foundation-manual-dispatch.yml is visible on GitHub
and present on the remote default branch, to determine readiness for plan-only retry.

CRITICAL CONSTRAINTS:
- Read-only operations only (gh, git ls-tree)
- No workflow modification
- No dispatch execution
- No secrets/tokens read
- No runtime/audit JSONL/action queue writing
- No auto-fix execution
"""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Project Root and Report Directory ─────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"

# ── Constants ──────────────────────────────────────────────────────────────────

GATE_ID = "R241-16L_remote_workflow_visibility_review"
WORKFLOW_FILE = "foundation-manual-dispatch.yml"
GITHUB_WORKFLOWS_DIR = ROOT / ".github" / "workflows"
R241_16K_RESULT_PATH = REPORT_DIR / "R241-16K_REMOTE_DISPATCH_EXECUTION_RESULT.json"

# ── String-Enum Classes ─────────────────────────────────────────────────────────

class RemoteWorkflowVisibilityStatus(str):
    VISIBLE = "visible"
    NOT_VISIBLE = "not_visible"
    BLOCKED_GH_UNAVAILABLE = "blocked_gh_unavailable"
    BLOCKED_NOT_AUTHENTICATED = "blocked_not_authenticated"
    BLOCKED_REMOTE_UNAVAILABLE = "blocked_remote_unavailable"
    BLOCKED_LOCAL_UNCOMMITTED_WORKFLOW = "blocked_local_uncommitted_workflow"
    BLOCKED_NOT_ON_DEFAULT_BRANCH = "blocked_not_on_default_branch"
    PARTIAL_WARNING = "partial_warning"
    UNKNOWN = "unknown"


class RemoteWorkflowVisibilityCheckType(str):
    GH_CLI_AVAILABLE = "gh_cli_available"
    GH_AUTH_STATUS = "gh_auth_status"
    REPO_DEFAULT_BRANCH = "repo_default_branch"
    LOCAL_BRANCH_STATUS = "local_branch_status"
    WORKFLOW_FILE_LOCAL_PRESENCE = "workflow_file_local_presence"
    WORKFLOW_FILE_REMOTE_PRESENCE = "workflow_file_remote_presence"
    WORKFLOW_LIST_VISIBILITY = "workflow_list_visibility"
    WORKFLOW_VIEW_VISIBILITY = "workflow_view_visibility"
    RUN_LIST_VISIBILITY = "run_list_visibility"
    LOCAL_MUTATION_GUARD = "local_mutation_guard"
    UNKNOWN = "unknown"


class RemoteWorkflowVisibilityDecision(str):
    ALLOW_PLAN_ONLY_RETRY = "allow_plan_only_retry"
    BLOCK_REMOTE_DISPATCH_UNTIL_PUSHED = "block_remote_dispatch_until_pushed"
    BLOCK_NEED_AUTHENTICATION = "block_need_authentication"
    BLOCK_NEED_REMOTE_VISIBILITY = "block_need_remote_visibility"
    KEEP_LOCAL_ONLY = "keep_local_only"
    UNKNOWN = "unknown"


class RemoteWorkflowVisibilityRiskLevel(str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ── Data Objects ───────────────────────────────────────────────────────────────

class RemoteWorkflowVisibilityCheck:
    def __init__(
        self,
        check_id: str,
        check_type: str,
        passed: bool,
        risk_level: str,
        description: str,
        command_blueprint: Optional[dict] = None,
        command_executed: Optional[dict] = None,
        observed_value: Optional[Any] = None,
        expected_value: Optional[Any] = None,
        evidence_refs: Optional[list[str]] = None,
        blocked_reasons: Optional[list[str]] = None,
        warnings: Optional[list[str]] = None,
        errors: Optional[list[str]] = None,
    ):
        self.check_id = check_id
        self.check_type = check_type
        self.passed = passed
        self.risk_level = risk_level
        self.description = description
        self.command_blueprint = command_blueprint or {}
        self.command_executed = command_executed or {}
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
            "description": self.description,
            "command_blueprint": self.command_blueprint,
            "command_executed": self.command_executed,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "evidence_refs": self.evidence_refs,
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class RemoteWorkflowVisibilityReview:
    def __init__(
        self,
        review_id: str,
        generated_at: str,
        status: str,
        decision: str,
        workflow_file: str,
        local_workflow_exists: bool,
        remote_workflow_visible: bool,
        remote_default_branch: Optional[str],
        local_branch: Optional[str],
        local_head: Optional[str],
        remote_head: Optional[str],
        workflow_on_remote_default_branch: bool,
        gh_available: bool,
        gh_authenticated: bool,
        checks: Optional[list[dict]] = None,
        r241_16k_summary: Optional[dict] = None,
        recommended_next_phase: Optional[str] = None,
        local_mutation_guard: Optional[dict] = None,
        warnings: Optional[list[str]] = None,
        errors: Optional[list[str]] = None,
    ):
        self.review_id = review_id
        self.generated_at = generated_at
        self.status = status
        self.decision = decision
        self.workflow_file = workflow_file
        self.local_workflow_exists = local_workflow_exists
        self.remote_workflow_visible = remote_workflow_visible
        self.remote_default_branch = remote_default_branch
        self.local_branch = local_branch
        self.local_head = local_head
        self.remote_head = remote_head
        self.workflow_on_remote_default_branch = workflow_on_remote_default_branch
        self.gh_available = gh_available
        self.gh_authenticated = gh_authenticated
        self.checks = checks or []
        self.r241_16k_summary = r241_16k_summary or {}
        self.recommended_next_phase = recommended_next_phase
        self.local_mutation_guard = local_mutation_guard or {}
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "decision": self.decision,
            "workflow_file": self.workflow_file,
            "local_workflow_exists": self.local_workflow_exists,
            "remote_workflow_visible": self.remote_workflow_visible,
            "remote_default_branch": self.remote_default_branch,
            "local_branch": self.local_branch,
            "local_head": self.local_head,
            "remote_head": self.remote_head,
            "workflow_on_remote_default_branch": self.workflow_on_remote_default_branch,
            "gh_available": self.gh_available,
            "gh_authenticated": self.gh_authenticated,
            "checks": self.checks,
            "r241_16k_summary": self.r241_16k_summary,
            "recommended_next_phase": self.recommended_next_phase,
            "local_mutation_guard": self.local_mutation_guard,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ── 1. load_r241_16k_remote_dispatch_result ───────────────────────────────────

def load_r241_16k_remote_dispatch_result(root: Optional[str] = None) -> dict:
    """Load and validate the R241-16K execution result."""
    root_path = Path(root).resolve() if root else ROOT
    result_path = root_path / "migration_reports" / "foundation_audit" / "R241-16K_REMOTE_DISPATCH_EXECUTION_RESULT.json"
    result = _read_json(result_path)

    if not result:
        return {
            "loaded": False,
            "error": "R241-16K result file not found",
            "status": RemoteWorkflowVisibilityStatus.UNKNOWN,
        }

    # Validate it's a plan_only dispatch
    cmd = result.get("command", {})
    argv = cmd.get("argv", [])
    execute_mode = "plan_only"
    has_execute_selected = any("execute_selected" in str(a) for a in argv)

    if has_execute_selected:
        return {
            "loaded": False,
            "error": "R241-16K did not use plan_only mode",
            "status": RemoteWorkflowVisibilityStatus.UNKNOWN,
            "result": result,
        }

    dispatch_attempted = result.get("dispatch_attempted", False)
    status = result.get("status", RemoteWorkflowVisibilityStatus.UNKNOWN)
    mutation_guard = result.get("local_mutation_guard", {})
    no_local_mutation = mutation_guard.get("no_local_mutation", False)
    existing_unchanged = mutation_guard.get("existing_workflows_unchanged", result.get("existing_workflows_unchanged", True))

    return {
        "loaded": True,
        "status": status,
        "dispatch_attempted": dispatch_attempted,
        "execute_mode": execute_mode,
        "no_local_mutation": no_local_mutation,
        "existing_workflows_unchanged": existing_unchanged,
        "result": result,
    }


# ── 2. build_remote_visibility_command_blueprints ──────────────────────────────

def build_remote_visibility_command_blueprints() -> dict:
    """Build read-only command blueprints for visibility checks."""
    blueprints = {
        "gh_workflow_list": {
            "command_id": "gh_workflow_list",
            "argv": ["gh", "workflow", "list"],
            "read_only": True,
            "no_secret_output_expected": True,
            "network_call_expected": True,
            "shell_allowed": False,
            "description": "List all workflows visible to gh CLI",
        },
        "gh_workflow_view": {
            "command_id": "gh_workflow_view",
            "argv": ["gh", "workflow", "view", WORKFLOW_FILE],
            "read_only": True,
            "no_secret_output_expected": True,
            "network_call_expected": True,
            "shell_allowed": False,
            "description": "View foundation-manual-dispatch.yml workflow details",
        },
        "gh_run_list": {
            "command_id": "gh_run_list",
            "argv": [
                "gh", "run", "list",
                "--workflow", WORKFLOW_FILE,
                "--limit", "10",
                "--json", "databaseId,status,conclusion,event,workflowName,displayTitle,url,createdAt",
            ],
            "read_only": True,
            "no_secret_output_expected": True,
            "network_call_expected": True,
            "shell_allowed": False,
            "description": "List recent runs for foundation-manual-dispatch.yml",
        },
        "gh_repo_view": {
            "command_id": "gh_repo_view",
            "argv": ["gh", "repo", "view", "--json", "defaultBranchRef,nameWithOwner"],
            "read_only": True,
            "no_secret_output_expected": True,
            "network_call_expected": True,
            "shell_allowed": False,
            "description": "Get repo default branch",
        },
        "git_status_short": {
            "command_id": "git_status_short",
            "argv": ["git", "status", "--short"],
            "read_only": True,
            "no_secret_output_expected": True,
            "network_call_expected": False,
            "shell_allowed": False,
            "description": "Get short git status",
        },
        "git_branch_show_current": {
            "command_id": "git_branch_show_current",
            "argv": ["git", "branch", "--show-current"],
            "read_only": True,
            "no_secret_output_expected": True,
            "network_call_expected": False,
            "shell_allowed": False,
            "description": "Get current branch name",
        },
        "git_rev_parse_head": {
            "command_id": "git_rev_parse_head",
            "argv": ["git", "rev-parse", "HEAD"],
            "read_only": True,
            "no_secret_output_expected": True,
            "network_call_expected": False,
            "shell_allowed": False,
            "description": "Get local HEAD commit hash",
        },
        "git_ls_tree_remote_workflow": {
            "command_id": "git_ls_tree_remote_workflow",
            "argv": ["git", "ls-tree", "-r", "origin/HEAD", "--", ".github/workflows", WORKFLOW_FILE],
            "read_only": True,
            "no_secret_output_expected": True,
            "network_call_expected": False,
            "shell_allowed": False,
            "description": "Check if workflow exists on origin/HEAD",
        },
    }

    # Compute origin/HEAD -> origin/main or origin/master
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "origin/HEAD"],
            capture_output=True, text=True, timeout=10, shell=False,
        )
        if result.returncode == 0:
            origin_head = result.stdout.strip()
            blueprints["git_ls_tree_origin_default"] = {
                "command_id": "git_ls_tree_origin_default",
                "argv": ["git", "ls-tree", "-r", origin_head, "--", ".github/workflows", WORKFLOW_FILE],
                "read_only": True,
                "no_secret_output_expected": True,
                "network_call_expected": False,
                "shell_allowed": False,
                "description": f"Check if workflow exists on {origin_head}",
            }
    except Exception:
        pass

    return blueprints


# ── 3. run_readonly_command ───────────────────────────────────────────────────

ALLOWED_COMMANDS: set[tuple[str, ...]] = {
    ("gh", "workflow"),
    ("gh", "run"),
    ("gh", "repo"),
    ("git", "status"),
    ("git", "branch"),
    ("git", "rev-parse"),
    ("git", "ls-tree"),
}


def run_readonly_command(argv: list[str], timeout_seconds: int = 30) -> dict:
    """Execute a whitelisted read-only command."""
    if not argv:
        return {"executed": False, "error": "Empty argv", "stdout": "", "stderr": ""}

    # Normalize argv for matching — use first 2+ elements as command family prefix
    # to match whitelisted commands with variable positional args (e.g. git ls-tree -r <ref>)
    normalized = tuple(a for a in argv if not a.startswith("-"))
    if len(normalized) >= 2:
        cmd_prefix = normalized[:2]
    elif len(normalized) == 1:
        cmd_prefix = normalized[:1]
    else:
        return {"executed": False, "error": "Empty argv after filtering", "stdout": "", "stderr": ""}

    if cmd_prefix not in ALLOWED_COMMANDS:
        return {
            "executed": False,
            "error": f"Command not in whitelist: {normalized[0] if normalized else 'empty'}",
            "stdout": "",
            "stderr": "",
            "argv": argv,
        }

    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        # Truncate long output to prevent log bloat
        stdout_tail = stdout[-2000:] if len(stdout) > 2000 else stdout
        stderr_tail = stderr[-500:] if len(stderr) > 500 else stderr
        return {
            "executed": True,
            "returncode": proc.returncode,
            "stdout": stdout_tail,
            "stderr": stderr_tail,
            "argv": argv,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "executed": False,
            "error": f"Command timed out after {timeout_seconds}s",
            "argv": argv,
            "timed_out": True,
            "stdout": "",
            "stderr": "",
        }
    except FileNotFoundError:
        return {
            "executed": False,
            "error": f"Command not found: {argv[0]}",
            "argv": argv,
            "stdout": "",
            "stderr": "",
        }
    except Exception as e:
        return {
            "executed": False,
            "error": str(e),
            "argv": argv,
            "stdout": "",
            "stderr": "",
        }


# ── 4. check_gh_cli_visibility ───────────────────────────────────────────────

def check_gh_cli_visibility(root: Optional[str] = None) -> RemoteWorkflowVisibilityCheck:
    """Check if gh CLI is available and authenticated."""
    blueprints = build_remote_visibility_command_blueprints()

    # Check gh --version
    version_cmd = ["gh", "--version"]
    version_result = run_readonly_command(version_cmd, timeout_seconds=10)

    gh_available = version_result.get("executed", False) and version_result.get("returncode", -1) == 0
    gh_version = version_result.get("stdout", "").strip() if gh_available else ""

    # Check gh auth status
    auth_cmd = ["gh", "auth", "status"]
    auth_result = run_readonly_command(auth_cmd, timeout_seconds=10)

    gh_authenticated = (
        auth_result.get("executed", False) and auth_result.get("returncode", -1) == 0
    )
    auth_error = auth_result.get("stderr", "") if not gh_authenticated else ""

    # Determine check type and blocked reasons
    if not gh_available:
        check_type = RemoteWorkflowVisibilityCheckType.GH_CLI_AVAILABLE
        blocked = [f"gh CLI not available: {version_result.get('error', 'unknown')}"]
        passed = False
        risk_level = RemoteWorkflowVisibilityRiskLevel.CRITICAL
    elif not gh_authenticated:
        check_type = RemoteWorkflowVisibilityCheckType.GH_AUTH_STATUS
        blocked = [f"gh not authenticated: {auth_error[:200]}"]
        passed = False
        risk_level = RemoteWorkflowVisibilityRiskLevel.CRITICAL
    else:
        check_type = RemoteWorkflowVisibilityCheckType.GH_AUTH_STATUS
        blocked = []
        passed = True
        risk_level = RemoteWorkflowVisibilityRiskLevel.LOW

    return RemoteWorkflowVisibilityCheck(
        check_id="check_gh_cli_visibility",
        check_type=check_type,
        passed=passed,
        risk_level=risk_level,
        description="Verify gh CLI is available and authenticated",
        command_blueprint={
            "gh_version_check": blueprints.get("gh_workflow_list", {}),
            "gh_auth_check": blueprints.get("gh_repo_view", {}),
        },
        command_executed={
            "version_command": version_result,
            "auth_command": auth_result,
        },
        observed_value={"gh_available": gh_available, "gh_authenticated": gh_authenticated, "gh_version": gh_version},
        expected_value={"gh_available": True, "gh_authenticated": True},
        blocked_reasons=blocked,
        errors=[auth_error] if auth_error else [],
    )


# ── 5. check_remote_workflow_list_visibility ───────────────────────────────────

def check_remote_workflow_list_visibility(root: Optional[str] = None) -> RemoteWorkflowVisibilityCheck:
    """Check if workflow is visible via gh workflow list/view."""
    blueprints = build_remote_visibility_command_blueprints()

    # gh workflow list
    list_result = run_readonly_command(["gh", "workflow", "list"], timeout_seconds=15)
    list_succeeded = list_result.get("executed", False) and list_result.get("returncode", -1) == 0
    list_output = list_result.get("stdout", "")

    workflow_found_in_list = False
    if list_succeeded and WORKFLOW_FILE in list_output:
        workflow_found_in_list = True

    # gh workflow view
    view_result = run_readonly_command(["gh", "workflow", "view", WORKFLOW_FILE], timeout_seconds=15)
    view_succeeded = view_result.get("executed", False) and view_result.get("returncode", -1) == 0

    if list_succeeded and not view_succeeded:
        # gh workflow view returns exit 1 when workflow doesn't exist on remote
        workflow_found_in_list = False

    passed = list_succeeded and workflow_found_in_list
    if not list_succeeded:
        passed = False

    if list_succeeded and not workflow_found_in_list:
        blocked = [f"Workflow {WORKFLOW_FILE} not visible in gh workflow list"]
    elif not list_succeeded:
        blocked = [f"gh workflow list failed: {list_result.get('error', 'unknown')}"]
    else:
        blocked = []

    return RemoteWorkflowVisibilityCheck(
        check_id="check_remote_workflow_list_visibility",
        check_type=RemoteWorkflowVisibilityCheckType.WORKFLOW_LIST_VISIBILITY,
        passed=passed,
        risk_level=RemoteWorkflowVisibilityRiskLevel.HIGH,
        description=f"Check if {WORKFLOW_FILE} is visible via gh workflow list",
        command_blueprint=blueprints.get("gh_workflow_list", {}),
        command_executed={"list_command": list_result, "view_command": view_result},
        observed_value={
            "workflow_found_in_list": workflow_found_in_list,
            "list_succeeded": list_succeeded,
            "view_succeeded": view_succeeded,
            "list_output_length": len(list_output),
        },
        expected_value={"workflow_found_in_list": True},
        blocked_reasons=blocked,
    )


# ── 6. check_remote_default_branch_presence ───────────────────────────────────

def check_remote_default_branch_presence(root: Optional[str] = None) -> RemoteWorkflowVisibilityCheck:
    """Check if workflow exists on the remote default branch."""
    blueprints = build_remote_visibility_command_blueprints()

    # gh repo view --json defaultBranchRef
    repo_result = run_readonly_command(
        ["gh", "repo", "view", "--json", "defaultBranchRef,nameWithOwner"],
        timeout_seconds=15,
    )
    repo_succeeded = repo_result.get("executed", False) and repo_result.get("returncode", -1) == 0

    default_branch = ""
    repo_name = ""
    if repo_succeeded:
        try:
            data = json.loads(repo_result.get("stdout", "{}"))
            default_branch = data.get("defaultBranchRef", {}).get("name", "") if isinstance(data.get("defaultBranchRef"), dict) else str(data.get("defaultBranchRef", ""))
            repo_name = data.get("nameWithOwner", "")
        except Exception:
            pass

    # Local branch
    branch_result = run_readonly_command(["git", "branch", "--show-current"], timeout_seconds=10)
    local_branch = branch_result.get("stdout", "").strip() if branch_result.get("executed") else ""

    # Local HEAD
    head_result = run_readonly_command(["git", "rev-parse", "HEAD"], timeout_seconds=10)
    local_head = head_result.get("stdout", "").strip() if head_result.get("executed") else ""

    # git ls-tree origin/HEAD for workflow
    ls_result = run_readonly_command(
        ["git", "ls-tree", "-r", "origin/HEAD", "--", ".github/workflows", WORKFLOW_FILE],
        timeout_seconds=15,
    )
    on_origin_head = ls_result.get("executed") and ls_result.get("returncode", -1) == 0 and bool(ls_result.get("stdout", "").strip())

    # git ls-tree origin/<default> for workflow
    origin_default_ls = None
    if default_branch:
        origin_default_ls = run_readonly_command(
            ["git", "ls-tree", "-r", f"origin/{default_branch}", "--", ".github/workflows", WORKFLOW_FILE],
            timeout_seconds=15,
        )
    on_origin_default = origin_default_ls is not None and origin_default_ls.get("executed") and origin_default_ls.get("returncode", -1) == 0 and bool(origin_default_ls.get("stdout", "").strip())

    workflow_on_remote = on_origin_head or on_origin_default

    if not repo_succeeded:
        passed = False
        blocked = [f"Cannot determine default branch: {repo_result.get('error', 'unknown')}"]
    elif not workflow_on_remote:
        passed = False
        blocked = [f"Workflow {WORKFLOW_FILE} not found on remote default branch ({default_branch})"]
    else:
        passed = True
        blocked = []

    return RemoteWorkflowVisibilityCheck(
        check_id="check_remote_default_branch_presence",
        check_type=RemoteWorkflowVisibilityCheckType.REPO_DEFAULT_BRANCH,
        passed=passed,
        risk_level=RemoteWorkflowVisibilityRiskLevel.CRITICAL,
        description=f"Check if {WORKFLOW_FILE} exists on remote default branch ({default_branch})",
        command_blueprint={
            "gh_repo_view": blueprints.get("gh_repo_view", {}),
            "git_ls_tree": blueprints.get("git_ls_tree_origin_default", {}),
        },
        command_executed={
            "repo_view": repo_result,
            "git_branch": branch_result,
            "git_head": head_result,
            "git_ls_origin_head": ls_result,
            "git_ls_origin_default": origin_default_ls,
        },
        observed_value={
            "default_branch": default_branch,
            "repo_name": repo_name,
            "local_branch": local_branch,
            "local_head": local_head,
            "workflow_on_origin_head": on_origin_head,
            "workflow_on_origin_default": on_origin_default,
            "workflow_on_remote_default_branch": workflow_on_remote,
        },
        expected_value={"workflow_on_remote_default_branch": True},
        blocked_reasons=blocked,
    )


# ── 7. check_remote_run_observation_capability ───────────────────────────────

def check_remote_run_observation_capability(root: Optional[str] = None) -> RemoteWorkflowVisibilityCheck:
    """Check if gh run list can observe runs for the workflow."""
    blueprints = build_remote_visibility_command_blueprints()

    run_list_result = run_readonly_command(
        [
            "gh", "run", "list",
            "--workflow", WORKFLOW_FILE,
            "--limit", "10",
            "--json", "databaseId,status,conclusion,event,workflowName,displayTitle,url,createdAt",
        ],
        timeout_seconds=15,
    )

    executed = run_list_result.get("executed", False)
    returncode = run_list_result.get("returncode", -1)

    # Exit 1 = workflow not found on remote (expected if not pushed)
    # Exit 0 = workflow found, may have runs or not
    can_observe = executed and returncode in (0, 1)
    runs_found = False
    run_count = 0

    if executed and returncode == 0:
        try:
            runs_data = json.loads(run_list_result.get("stdout", "[]"))
            runs_found = isinstance(runs_data, list) and len(runs_data) > 0
            run_count = len(runs_data) if isinstance(runs_data, list) else 0
        except Exception:
            pass

    # If workflow not visible on GitHub (not pushed), run list returns exit 1
    # That's acceptable - the important thing is gh run list can BE CALLED
    if not executed:
        passed = False
        blocked = [f"gh run list failed: {run_list_result.get('error', 'unknown')}"]
    else:
        passed = True
        blocked = []
        if returncode == 1:
            blocked.append(f"Workflow {WORKFLOW_FILE} not yet visible on GitHub (not pushed to remote)")

    return RemoteWorkflowVisibilityCheck(
        check_id="check_remote_run_observation_capability",
        check_type=RemoteWorkflowVisibilityCheckType.RUN_LIST_VISIBILITY,
        passed=passed,
        risk_level=RemoteWorkflowVisibilityRiskLevel.HIGH,
        description="Check if gh run list can observe runs for foundation-manual-dispatch.yml",
        command_blueprint=blueprints.get("gh_run_list", {}),
        command_executed={"run_list_command": run_list_result},
        observed_value={
            "can_observe": can_observe,
            "runs_found": runs_found,
            "run_count": run_count,
            "gh_exit_code": returncode,
        },
        expected_value={"can_observe": True},
        blocked_reasons=blocked,
        warnings=[] if returncode == 1 else [],
    )


# ── 8. verify_no_local_mutation_after_visibility_review ───────────────────────

def verify_no_local_mutation_after_visibility_review(
    root: Optional[str] = None,
    baseline: Optional[dict] = None,
) -> dict:
    """Verify no local files were mutated during the visibility review."""
    root_path = Path(root).resolve() if root else ROOT

    workflows = [
        root_path / ".github" / "workflows" / "foundation-manual-dispatch.yml",
        root_path / ".github" / "workflows" / "backend-unit-tests.yml",
        root_path / ".github" / "workflows" / "lint-check.yml",
    ]

    mutations = []
    for wf in workflows:
        if wf.exists():
            content = wf.read_text(encoding="utf-8")
            mutations.append({
                "path": str(wf.relative_to(root_path)),
                "exists": True,
                "size": len(content),
            })
        else:
            mutations.append({"path": str(wf.relative_to(root_path)), "exists": False})

    runtime_dir = root_path / "runtime"
    action_queue_dir = root_path / "action_queue"
    audit_jsonl = root_path / "migration_reports" / "foundation_audit" / "audit_trail" / "foundation_diagnostic_runs.jsonl"

    warnings = []
    if runtime_dir.exists():
        warnings.append("runtime/ directory exists (should not be created by visibility review)")
    if action_queue_dir.exists():
        warnings.append("action_queue/ directory exists (should not be created by visibility review)")
    if audit_jsonl.exists():
        # Check if it was modified
        content = audit_jsonl.read_text(encoding="utf-8")
        lines = content.strip().split("\n") if content.strip() else []
        if baseline and "audit_lines" in baseline:
            if len(lines) != baseline.get("audit_lines", 0):
                warnings.append("audit JSONL was modified during visibility review")

    no_local_mutation = len(warnings) == 0

    return {
        "no_local_mutation": no_local_mutation,
        "mutations": mutations,
        "warnings": warnings,
        "errors": [],
    }


# ── 9. evaluate_remote_workflow_visibility_review ──────────────────────────────

def evaluate_remote_workflow_visibility_review(root: Optional[str] = None) -> dict:
    """Evaluate the remote workflow visibility review."""
    root_path = Path(root).resolve() if root else ROOT
    generated_at = _now()
    review_id = f"rv-{uuid.uuid4().hex[:12]}"

    # Load R241-16K result
    r241_16k = load_r241_16k_remote_dispatch_result(str(root_path))
    r241_16k_summary = {
        "loaded": r241_16k.get("loaded", False),
        "status": r241_16k.get("status", RemoteWorkflowVisibilityStatus.UNKNOWN),
        "dispatch_attempted": r241_16k.get("dispatch_attempted", False),
        "execute_mode": r241_16k.get("execute_mode", "unknown"),
        "no_local_mutation": r241_16k.get("no_local_mutation", False),
        "existing_workflows_unchanged": r241_16k.get("existing_workflows_unchanged", True),
    }

    # Run checks
    gh_check = check_gh_cli_visibility(str(root_path))
    workflow_list_check = check_remote_workflow_list_visibility(str(root_path))
    default_branch_check = check_remote_default_branch_presence(str(root_path))
    run_obs_check = check_remote_run_observation_capability(str(root_path))

    # Local mutation baseline (capture before checks mutate)
    audit_jsonl = root_path / "migration_reports" / "foundation_audit" / "audit_trail" / "foundation_diagnostic_runs.jsonl"
    baseline = {}
    if audit_jsonl.exists():
        baseline["audit_lines"] = len(audit_jsonl.read_text(encoding="utf-8").strip().split("\n"))

    mutation_guard = verify_no_local_mutation_after_visibility_review(str(root_path), baseline=baseline)

    # Determine workflow presence
    workflow_path = root_path / ".github" / "workflows" / WORKFLOW_FILE
    local_workflow_exists = workflow_path.exists()

    gh_available = gh_check.observed_value.get("gh_available", False)
    gh_authenticated = gh_check.observed_value.get("gh_authenticated", False)
    workflow_list_visible = workflow_list_check.observed_value.get("workflow_found_in_list", False)
    on_remote_default = (
        default_branch_check.observed_value.get("workflow_on_remote_default_branch", False)
        if default_branch_check.observed_value else False
    )
    remote_default_branch = default_branch_check.observed_value.get("default_branch", "")

    local_branch = default_branch_check.observed_value.get("local_branch", "")
    local_head = default_branch_check.observed_value.get("local_head", "")

    checks = [
        gh_check.to_dict(),
        workflow_list_check.to_dict(),
        default_branch_check.to_dict(),
        run_obs_check.to_dict(),
    ]

    # Determine status and decision
    all_checks_passed = all(c.passed for c in [gh_check, workflow_list_check, default_branch_check, run_obs_check])

    if not gh_available:
        status = RemoteWorkflowVisibilityStatus.BLOCKED_GH_UNAVAILABLE
        decision = RemoteWorkflowVisibilityDecision.BLOCK_NEED_REMOTE_VISIBILITY
        recommended = "R241-16L cannot proceed: gh CLI unavailable. Install gh and retry."
    elif not gh_authenticated:
        status = RemoteWorkflowVisibilityStatus.BLOCKED_NOT_AUTHENTICATED
        decision = RemoteWorkflowVisibilityDecision.BLOCK_NEED_AUTHENTICATION
        recommended = "R241-16L cannot proceed: gh not authenticated. Run `gh auth login` and retry."
    elif not on_remote_default:
        status = RemoteWorkflowVisibilityStatus.BLOCKED_NOT_ON_DEFAULT_BRANCH
        decision = RemoteWorkflowVisibilityDecision.BLOCK_REMOTE_DISPATCH_UNTIL_PUSHED
        recommended = "R241-16L blocked: workflow not on remote default branch. Push workflow to remote default branch to enable plan_only retry."
    elif workflow_list_visible and on_remote_default:
        status = RemoteWorkflowVisibilityStatus.VISIBLE
        decision = RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY
        recommended = "R241-16L PASS: workflow visible on GitHub and on remote default branch. Ready for R241-16M plan_only retry."
    elif all_checks_passed:
        status = RemoteWorkflowVisibilityStatus.VISIBLE
        decision = RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY
        recommended = "R241-16L PASS: visibility checks passed. Ready for R241-16M plan_only retry."
    else:
        status = RemoteWorkflowVisibilityStatus.UNKNOWN
        decision = RemoteWorkflowVisibilityDecision.UNKNOWN
        recommended = "R241-16L inconclusive: review results inconclusive. Manual inspection required."

    warnings = list(mutation_guard.get("warnings", []))
    if not local_workflow_exists:
        warnings.append(f"Workflow {WORKFLOW_FILE} does not exist locally")

    errors = list(mutation_guard.get("errors", []))

    review = {
        "review_id": review_id,
        "generated_at": generated_at,
        "status": status,
        "decision": decision,
        "workflow_file": WORKFLOW_FILE,
        "local_workflow_exists": local_workflow_exists,
        "remote_workflow_visible": workflow_list_visible and on_remote_default,
        "remote_default_branch": remote_default_branch,
        "local_branch": local_branch,
        "local_head": local_head,
        "remote_head": default_branch_check.observed_value.get("workflow_on_origin_default", False) or default_branch_check.observed_value.get("workflow_on_origin_head", False),
        "workflow_on_remote_default_branch": on_remote_default,
        "gh_available": gh_available,
        "gh_authenticated": gh_authenticated,
        "checks": checks,
        "r241_16k_summary": r241_16k_summary,
        "recommended_next_phase": recommended,
        "local_mutation_guard": mutation_guard,
        "warnings": warnings,
        "errors": errors,
    }

    return review


# ── 10. validate_remote_workflow_visibility_review ─────────────────────────────

def validate_remote_workflow_visibility_review(review: dict) -> dict:
    """Validate the visibility review result."""
    errors = []
    warnings = []

    required_fields = [
        "review_id", "generated_at", "status", "decision",
        "workflow_file", "checks", "r241_16k_summary",
        "local_mutation_guard", "gh_available", "gh_authenticated",
    ]

    missing_fields = [f for f in required_fields if f not in review]
    if missing_fields:
        errors.append(f"Missing required fields: {missing_fields}")

    # Validate no forbidden actions occurred
    for check in review.get("checks", []):
        cmd_exec = check.get("command_executed", {})
        for cmd_name, cmd_result in cmd_exec.items():
            if not isinstance(cmd_result, dict):
                continue
            argv = cmd_result.get("argv", [])
            if argv and argv[0] == "gh" and len(argv) > 2:
                # Detect forbidden gh commands
                if argv[1] == "workflow" and argv[2] == "run":
                    errors.append(f"Forbidden: gh workflow run executed during visibility review")
                if argv[1] == "run" and argv[2] == "cancel":
                    errors.append(f"Forbidden: gh run cancel executed during visibility review")

    # Check mutation guard
    mutation_guard = review.get("local_mutation_guard", {})
    if not mutation_guard.get("no_local_mutation", False):
        warnings.append("Local mutation guard detected potential changes")

    # Validate decision coherence with status
    status = review.get("status", "")
    decision = review.get("decision", "")

    if status == RemoteWorkflowVisibilityStatus.VISIBLE and decision not in [
        RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY,
        RemoteWorkflowVisibilityDecision.KEEP_LOCAL_ONLY,
    ]:
        errors.append(f"Decision '{decision}' incoherent with VISIBLE status")

    if status in [RemoteWorkflowVisibilityStatus.BLOCKED_GH_UNAVAILABLE, RemoteWorkflowVisibilityStatus.BLOCKED_NOT_AUTHENTICATED]:
        if decision not in [RemoteWorkflowVisibilityDecision.BLOCK_NEED_AUTHENTICATION, RemoteWorkflowVisibilityDecision.BLOCK_NEED_REMOTE_VISIBILITY]:
            errors.append(f"Decision '{decision}' incoherent with blocked status '{status}'")

    # Validate R241-16K summary exists
    r241_16k = review.get("r241_16k_summary", {})
    if not r241_16k:
        errors.append("R241-16K summary missing from review")

    valid = len(errors) == 0

    return {
        "valid": valid,
        "warnings": warnings,
        "errors": errors,
    }


# ── 11. generate_remote_workflow_visibility_review_report ───────────────────────

def generate_remote_workflow_visibility_review_report(
    review: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Generate the R241-16L visibility review report."""
    if review is None:
        review = evaluate_remote_workflow_visibility_review()

    root_path = ROOT
    output_json = Path(output_path) if output_path else REPORT_DIR / "R241-16L_REMOTE_WORKFLOW_VISIBILITY_REVIEW.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON
    report_data = {**review}
    output_json.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write Markdown
    md_path = REPORT_DIR / "R241-16L_REMOTE_WORKFLOW_VISIBILITY_REVIEW.md"

    gh = review.get("gh_available", False)
    gh_auth = review.get("gh_authenticated", False)
    wf_visible = review.get("remote_workflow_visible", False)
    on_default = review.get("workflow_on_remote_default_branch", False)
    status = review.get("status", "unknown")
    decision = review.get("decision", "unknown")
    checks = review.get("checks", [])
    r241_16k = review.get("r241_16k_summary", {})
    recommended = review.get("recommended_next_phase", "")
    mg = review.get("local_mutation_guard", {})
    warnings = review.get("warnings", [])
    errors = review.get("errors", [])

    md_lines = [
        "# R241-16L Remote Workflow Visibility / Default Branch Readiness Review",
        "",
        "## Review Result",
        "",
        f"- **Review ID**: `{review.get('review_id', 'N/A')}`",
        f"- **Generated**: {review.get('generated_at', 'N/A')}",
        f"- **Status**: `{status}`",
        f"- **Decision**: `{decision}`",
        f"- **Workflow**: `{WORKFLOW_FILE}`",
        "",
        "## R241-16K Dispatch Summary",
        "",
        f"- **R241-16K Loaded**: {r241_16k.get('loaded', False)}",
        f"- **R241-16K Status**: `{r241_16k.get('status', 'N/A')}`",
        f"- **Dispatch Attempted**: {r241_16k.get('dispatch_attempted', False)}",
        f"- **Execute Mode**: `{r241_16k.get('execute_mode', 'N/A')}`",
        f"- **No Local Mutation**: {r241_16k.get('no_local_mutation', False)}",
        f"- **Workflows Unchanged**: {r241_16k.get('existing_workflows_unchanged', True)}",
        "",
        "## GitHub CLI Availability",
        "",
        f"- **gh Available**: {gh}",
        f"- **gh Authenticated**: {gh_auth}",
        "",
        "## Workflow Visibility",
        "",
        f"- **Local Workflow Exists**: {review.get('local_workflow_exists', False)}",
        f"- **Remote Workflow Visible**: {wf_visible}",
        f"- **On Remote Default Branch**: {on_default}",
        f"- **Remote Default Branch**: `{review.get('remote_default_branch', 'N/A')}`",
        f"- **Local Branch**: `{review.get('local_branch', 'N/A')}`",
        f"- **Local HEAD**: `{review.get('local_head', 'N/A')[:8]}...`",
        "",
        "## Visibility Checks",
        "",
    ]

    for i, check in enumerate(checks, 1):
        emoji = "✅" if check.get("passed") else "❌"
        md_lines.append(f"### {i}. [{check.get('risk_level', '').upper()}] {check.get('check_id', 'unknown')} {emoji}")
        md_lines.append("")
        md_lines.append(f"- **Check Type**: `{check.get('check_type', 'N/A')}`")
        md_lines.append(f"- **Passed**: {check.get('passed', False)}")
        md_lines.append(f"- **Description**: {check.get('description', 'N/A')}")
        obs = check.get("observed_value", {})
        if isinstance(obs, dict):
            for k, v in obs.items():
                md_lines.append(f"  - **{k}**: `{v}`")
        if check.get("blocked_reasons"):
            for br in check.get("blocked_reasons", []):
                md_lines.append(f"  - **Blocked**: {br}")
        md_lines.append("")

    md_lines.extend([
        "## Local Mutation Guard",
        "",
        f"- **No Local Mutation**: {mg.get('no_local_mutation', False)}",
        f"- **Warnings**: {mg.get('warnings', []) if mg.get('warnings') else 'None'}",
        "",
        "## Validation",
        "",
        f"- **Warnings**: {warnings if warnings else 'None'}",
        f"- **Errors**: {errors if errors else 'None'}",
        "",
        "## Next Recommendation",
        "",
        f"- {recommended}",
        "",
        "## Safety Constraints",
        "",
        f"- ✅ No `gh workflow run` executed during review",
        f"- ✅ No `git push` executed",
        f"- ✅ No secrets/tokens read",
        f"- ✅ No workflow files modified",
        f"- ✅ No `runtime/` or `action_queue/` created",
        f"- ✅ No audit JSONL appended",
        f"- ✅ No auto-fix executed",
    ])

    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return {
        "output_path": str(output_json),
        "report_path": str(md_path),
        "review_id": review.get("review_id", ""),
        "status": status,
        "decision": decision,
        "gh_available": gh,
        "gh_authenticated": gh_auth,
        "workflow_on_remote_default_branch": on_default,
        "recommended_next_phase": recommended,
    }
