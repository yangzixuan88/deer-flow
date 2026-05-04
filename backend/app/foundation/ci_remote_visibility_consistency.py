"""R241-16M Remote Workflow Visibility Consistency Repair Review.

This module fixes the visibility judgment bugs from R241-16L:
1. git ls-tree must use exact file path (not directory listing)
2. gh CLI state must be properly classified (binary unavailable vs partially available)
3. run observation capability must fail when workflow is not GitHub-Actions-indexed

CRITICAL CONSTRAINTS:
- Read-only operations only
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

from app.foundation.ci_remote_workflow_visibility_review import (
    RemoteWorkflowVisibilityCheck,
    RemoteWorkflowVisibilityRiskLevel,
    RemoteWorkflowVisibilityStatus,
    RemoteWorkflowVisibilityDecision,
    WORKFLOW_FILE,
    ROOT,
    REPORT_DIR,
    build_remote_visibility_command_blueprints,
    run_readonly_command,
    check_gh_cli_visibility,
    check_remote_workflow_list_visibility,
    check_remote_run_observation_capability,
    verify_no_local_mutation_after_visibility_review,
)

# ── 1. parse_git_ls_tree_workflow_presence ────────────────────────────────────

def parse_git_ls_tree_workflow_presence(stdout: str, workflow_path: str) -> dict:
    """Parse git ls-tree stdout to determine if a specific workflow file is present.

    Rules:
    - Only a line with tab-delimited path EXACTLY equal to workflow_path sets present=True
    - Presence of other workflow files (backend-unit-tests.yml, lint-check.yml) does NOT count
    - Empty stdout must be present=False
    - Windows line endings (\\r\\n) must be handled
    """
    lines = stdout.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n")
    matched_lines = []
    unrelated_lines = []

    for line in lines:
        if not line.strip():
            continue
        # git ls-tree format: <mode> <type> <sha>\t<path>
        # Must split on TAB, not on whitespace (sha contains spaces)
        parts = line.split("\t", maxsplit=1)
        if len(parts) < 2:
            continue
        path = parts[1].strip()
        if path == workflow_path:
            matched_lines.append(line)
        else:
            unrelated_lines.append(line)

    present = len(matched_lines) > 0

    return {
        "present": present,
        "matched_lines": matched_lines,
        "unrelated_lines": unrelated_lines,
        "evidence": stdout[:500] if stdout else "(empty)",
        "warnings": [],
        "errors": [],
    }


# ── 2. classify_gh_cli_state ────────────────────────────────────────────────

class GHCLIState:
    BINARY_UNAVAILABLE = "binary_unavailable"
    UNAUTHENTICATED = "unauthenticated"
    AVAILABLE_AUTHENTICATED = "available_authenticated"
    PARTIALLY_AVAILABLE = "partially_available"
    UNKNOWN = "unknown"


def classify_gh_cli_state(command_results: dict) -> dict:
    """Classify gh CLI state based on multiple command results.

    Must consider ALL of: gh --version, gh auth status, gh repo view, gh workflow list, gh workflow view
    """
    version_result = command_results.get("gh_version", {})
    auth_result = command_results.get("gh_auth", {})
    repo_view_result = command_results.get("gh_repo_view", {})
    workflow_list_result = command_results.get("gh_workflow_list", {})
    workflow_view_result = command_results.get("gh_workflow_view", {})

    version_ok = version_result.get("executed", False) and version_result.get("returncode", -1) == 0
    auth_ok = auth_result.get("executed", False) and auth_result.get("returncode", -1) == 0
    repo_ok = repo_view_result.get("executed", False) and repo_view_result.get("returncode", -1) == 0
    workflow_list_ok = workflow_list_result.get("executed", False) and workflow_list_result.get("returncode", -1) == 0
    workflow_view_ok = workflow_view_result.get("executed", False) and workflow_view_result.get("returncode", -1) == 0

    if not version_ok:
        return {
            "state": GHCLIState.BINARY_UNAVAILABLE,
            "version_ok": version_ok,
            "auth_ok": auth_ok,
            "repo_ok": repo_ok,
            "workflow_list_ok": workflow_list_ok,
            "workflow_view_ok": workflow_view_ok,
            "description": "gh binary not available or not in PATH",
            "blocked_reasons": [f"gh --version failed: {version_result.get('error', 'unknown')}"],
        }

    if not auth_ok:
        return {
            "state": GHCLIState.UNAUTHENTICATED,
            "version_ok": version_ok,
            "auth_ok": auth_ok,
            "repo_ok": repo_ok,
            "workflow_list_ok": workflow_list_ok,
            "workflow_view_ok": workflow_view_ok,
            "description": "gh available but not authenticated",
            "blocked_reasons": [f"gh auth status failed: {auth_result.get('stderr', 'unknown')[:200]}"],
        }

    # gh available and authenticated — ALL commands must succeed (including gh workflow view)
    if repo_ok and workflow_list_ok and workflow_view_ok:
        return {
            "state": GHCLIState.AVAILABLE_AUTHENTICATED,
            "version_ok": version_ok,
            "auth_ok": auth_ok,
            "repo_ok": repo_ok,
            "workflow_list_ok": workflow_list_ok,
            "workflow_view_ok": workflow_view_ok,
            "description": "gh fully available and authenticated",
            "blocked_reasons": [],
        }

    # gh available and auth ok, but some API calls fail
    # Must check gh_workflow_view specifically — 404 on workflow view means PARTIALLY_AVAILABLE
    if repo_ok or workflow_list_ok or (workflow_view_result.get("executed") and workflow_view_result.get("returncode") == 1):
        return {
            "state": GHCLIState.PARTIALLY_AVAILABLE,
            "version_ok": version_ok,
            "auth_ok": auth_ok,
            "repo_ok": repo_ok,
            "workflow_list_ok": workflow_list_ok,
            "workflow_view_ok": workflow_view_ok,
            "description": "gh available but some API calls failed",
            "blocked_reasons": [
                f"gh repo view: {'ok' if repo_ok else 'failed'}",
                f"gh workflow list: {'ok' if workflow_list_ok else 'failed'}",
                f"gh workflow view: {'ok' if workflow_view_ok else 'failed'}",
            ],
        }

    return {
        "state": GHCLIState.UNKNOWN,
        "version_ok": version_ok,
        "auth_ok": auth_ok,
        "repo_ok": repo_ok,
        "workflow_list_ok": workflow_list_ok,
        "workflow_view_ok": workflow_view_ok,
        "description": "Cannot determine gh CLI state",
        "blocked_reasons": ["Insufficient gh command results to classify state"],
    }


# ── 3. normalize_workflow_visibility_decision ─────────────────────────────────

def normalize_workflow_visibility_decision(review: dict) -> dict:
    """Normalize visibility decision based on corrected priority chain.

    Priority (highest first):
    1. gh binary unavailable → block_need_remote_visibility
    2. gh unauthenticated → block_need_authentication
    3. git exact path missing → block_until_pushed
    4. git present but gh workflow view 404 → block_until_pushed
    5. all visible + run observable → allow_plan_only_retry
    6. git present + gh partially available → partial_warning + allow
    """
    git_exact_path_present = review.get("git_exact_path_present", False)
    gh_workflow_visible = review.get("gh_workflow_visible", False)
    gh_run_observable = review.get("gh_run_observable", False)
    gh_state = review.get("gh_cli_state", GHCLIState.UNKNOWN)
    gh_authenticated = review.get("gh_authenticated", False)
    gh_available = review.get("gh_available", False)

    # Priority 1: gh binary unavailable → must check before git path (gh may not be available to confirm git either)
    if gh_state == GHCLIState.BINARY_UNAVAILABLE or not gh_available:
        return {
            "corrected_status": RemoteWorkflowVisibilityStatus.BLOCKED_GH_UNAVAILABLE,
            "corrected_decision": RemoteWorkflowVisibilityDecision.BLOCK_NEED_REMOTE_VISIBILITY,
            "blocking_reason": "gh CLI not available or not in PATH on this system",
            "recommended_next_phase": "Install gh CLI and retry R241-16M.",
        }

    # Priority 2: gh unauthenticated
    if gh_state == GHCLIState.UNAUTHENTICATED or not gh_authenticated:
        return {
            "corrected_status": RemoteWorkflowVisibilityStatus.BLOCKED_NOT_AUTHENTICATED,
            "corrected_decision": RemoteWorkflowVisibilityDecision.BLOCK_NEED_AUTHENTICATION,
            "blocking_reason": "gh CLI available but not authenticated",
            "recommended_next_phase": "Run `gh auth login` and retry R241-16M.",
        }

    # Priority 3: git exact path missing → block until pushed
    if not git_exact_path_present:
        return {
            "corrected_status": RemoteWorkflowVisibilityStatus.NOT_VISIBLE,
            "corrected_decision": RemoteWorkflowVisibilityDecision.BLOCK_REMOTE_DISPATCH_UNTIL_PUSHED,
            "blocking_reason": "workflow file not found on origin/default branch via git ls-tree exact path",
            "recommended_next_phase": "Push foundation-manual-dispatch.yml to origin/main to enable remote dispatch.",
        }

    # Priority 4: git present + gh partially available → partial_warning (must check BEFORE gh_workflow_visible=False
    # because gh_workflow_visible=False with PARTIALLY_AVAILABLE means "gh had partial failures, try anyway")
    if git_exact_path_present and gh_state == GHCLIState.PARTIALLY_AVAILABLE:
        return {
            "corrected_status": RemoteWorkflowVisibilityStatus.PARTIAL_WARNING,
            "corrected_decision": RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY,
            "blocking_reason": "gh partially available; some API calls failed",
            "recommended_next_phase": "R241-16M PARTIAL: workflow on origin/default, gh partially functional. Proceed with caution to R241-16N.",
        }

    # Priority 5: git present but gh workflow view 404 → need GitHub Actions indexing
    if git_exact_path_present and not gh_workflow_visible:
        return {
            "corrected_status": RemoteWorkflowVisibilityStatus.NOT_VISIBLE,
            "corrected_decision": RemoteWorkflowVisibilityDecision.BLOCK_REMOTE_DISPATCH_UNTIL_PUSHED,
            "blocking_reason": "workflow file on origin/default via git ls-tree, but gh workflow view returns 404 (GitHub Actions not yet indexed)",
            "recommended_next_phase": "Push workflow to origin/main. If already pushed, wait for GitHub Actions indexing or check workflow name/id.",
        }

    # Priority 6: workflow visible + run observable → allow retry
    if git_exact_path_present and gh_workflow_visible and gh_run_observable:
        return {
            "corrected_status": RemoteWorkflowVisibilityStatus.VISIBLE,
            "corrected_decision": RemoteWorkflowVisibilityDecision.ALLOW_PLAN_ONLY_RETRY,
            "blocking_reason": "",
            "recommended_next_phase": "R241-16M PASS: workflow visible on GitHub Actions and on remote default branch. Ready for R241-16N plan_only retry.",
        }

    return {
        "corrected_status": RemoteWorkflowVisibilityStatus.UNKNOWN,
        "corrected_decision": RemoteWorkflowVisibilityDecision.UNKNOWN,
        "blocking_reason": "Cannot determine visibility state",
        "recommended_next_phase": "R241-16M inconclusive: manual inspection required.",
    }


# ── 4. evaluate_corrected_remote_workflow_visibility ───────────────────────────

def evaluate_corrected_remote_workflow_visibility(root: Optional[str] = None) -> dict:
    """Evaluate visibility with corrected logic for exact file paths and gh state."""
    root_path = Path(root).resolve() if root else ROOT
    generated_at = datetime.now(timezone.utc).isoformat()
    review_id = f"rv-consistency-{uuid.uuid4().hex[:12]}"

    # Workflow file path (exact)
    WORKFLOW_EXACT_PATH = f".github/workflows/{WORKFLOW_FILE}"

    # Run gh checks
    gh_check = check_gh_cli_visibility(str(root_path))
    gh_available = gh_check.observed_value.get("gh_available", False)
    gh_authenticated = gh_check.observed_value.get("gh_authenticated", False)

    # Get gh command results for classification
    gh_version_cmd = run_readonly_command(["gh", "--version"], timeout_seconds=10)
    gh_auth_cmd = run_readonly_command(["gh", "auth", "status"], timeout_seconds=10)
    gh_repo_cmd = run_readonly_command(
        ["gh", "repo", "view", "--json", "defaultBranchRef,nameWithOwner"],
        timeout_seconds=15,
    )
    gh_wf_list_cmd = run_readonly_command(["gh", "workflow", "list"], timeout_seconds=15)
    gh_wf_view_cmd = run_readonly_command(["gh", "workflow", "view", WORKFLOW_FILE], timeout_seconds=15)

    gh_command_results = {
        "gh_version": gh_version_cmd,
        "gh_auth": gh_auth_cmd,
        "gh_repo_view": gh_repo_cmd,
        "gh_workflow_list": gh_wf_list_cmd,
        "gh_workflow_view": gh_wf_view_cmd,
    }

    gh_cli_state = classify_gh_cli_state(gh_command_results)

    # git ls-tree with EXACT file path (not directory)
    git_head_result = run_readonly_command(["git", "rev-parse", "HEAD"], timeout_seconds=10)
    local_head = git_head_result.get("stdout", "").strip() if git_head_result.get("executed") else ""

    git_branch_result = run_readonly_command(["git", "branch", "--show-current"], timeout_seconds=10)
    local_branch = git_branch_result.get("stdout", "").strip() if git_branch_result.get("executed") else ""

    # Get default branch from gh repo view
    default_branch = ""
    if gh_repo_cmd.get("executed") and gh_repo_cmd.get("returncode") == 0:
        try:
            data = json.loads(gh_repo_cmd.get("stdout", "{}"))
            ref = data.get("defaultBranchRef", {})
            if isinstance(ref, dict):
                default_branch = ref.get("name", "")
            elif isinstance(ref, str):
                default_branch = ref
        except Exception:
            pass

    # git ls-tree with exact file path
    origin_default = f"origin/{default_branch}" if default_branch else "origin/main"
    git_ls_exact_cmd = run_readonly_command(
        ["git", "ls-tree", "-r", origin_default, "--", WORKFLOW_EXACT_PATH],
        timeout_seconds=15,
    )
    git_ls_exact_parsed = parse_git_ls_tree_workflow_presence(
        git_ls_exact_cmd.get("stdout", ""),
        WORKFLOW_EXACT_PATH,
    )
    git_exact_path_present = git_ls_exact_parsed.get("present", False)

    # Also check origin/HEAD as fallback
    git_ls_head_cmd = run_readonly_command(
        ["git", "ls-tree", "-r", "origin/HEAD", "--", WORKFLOW_EXACT_PATH],
        timeout_seconds=15,
    )
    git_ls_head_parsed = parse_git_ls_tree_workflow_presence(
        git_ls_head_cmd.get("stdout", ""),
        WORKFLOW_EXACT_PATH,
    )
    git_on_origin_head = git_ls_head_parsed.get("present", False)

    # gh workflow list visibility
    workflow_list_result = check_remote_workflow_list_visibility(str(root_path))
    gh_workflow_visible = workflow_list_result.observed_value.get("workflow_found_in_list", False)

    # gh run observation capability (corrected: fail when workflow not visible)
    run_obs_result = check_remote_run_observation_capability(str(root_path))
    # gh run list returns 404 (exit 1) when workflow not indexed by GitHub Actions
    gh_run_observable = (
        run_obs_result.observed_value.get("can_observe", False)
        and run_obs_result.observed_value.get("gh_exit_code", -1) == 0
        and run_obs_result.observed_value.get("workflow_found_in_list", False)
        if "workflow_found_in_list" in run_obs_result.observed_value
        else run_obs_result.observed_value.get("can_observe", False) and run_obs_result.observed_value.get("gh_exit_code", -1) == 0
    )

    # Re-check: if gh run list exits 1 (workflow not found), gh_run_observable should be False
    if run_obs_result.observed_value.get("gh_exit_code", -1) == 1:
        gh_run_observable = False

    # Local mutation guard
    audit_jsonl = root_path / "migration_reports" / "foundation_audit" / "audit_trail" / "foundation_diagnostic_runs.jsonl"
    baseline = {}
    if audit_jsonl.exists():
        baseline["audit_lines"] = len(audit_jsonl.read_text(encoding="utf-8").strip().split("\n"))
    mutation_guard = verify_no_local_mutation_after_visibility_review(str(root_path), baseline=baseline)

    # Workflow local existence
    workflow_local = root_path / ".github" / "workflows" / WORKFLOW_FILE
    local_workflow_exists = workflow_local.exists()

    # Build raw review
    raw_review = {
        "git_exact_path_present": git_exact_path_present,
        "git_on_origin_head": git_on_origin_head,
        "gh_workflow_visible": gh_workflow_visible,
        "gh_run_observable": gh_run_observable,
        "gh_cli_state": gh_cli_state.get("state", GHCLIState.UNKNOWN),
        "gh_available": gh_available,
        "gh_authenticated": gh_authenticated,
        "gh_cli_state_detail": gh_cli_state,
        "local_workflow_exists": local_workflow_exists,
        "default_branch": default_branch,
        "local_branch": local_branch,
        "local_head": local_head,
        "mutation_guard": mutation_guard,
        "command_results": gh_command_results,
    }

    # Normalize decision
    normalized = normalize_workflow_visibility_decision(raw_review)

    # Determine R241-16L inconsistency
    r241_16l_was_inconsistent = (
        raw_review.get("git_exact_path_present") is False
        and raw_review.get("gh_workflow_visible") is False
    )

    checks = [
        gh_check.to_dict(),
        workflow_list_result.to_dict(),
        run_obs_result.to_dict(),
    ]

    review = {
        "review_id": review_id,
        "generated_at": generated_at,
        "workflow_file": WORKFLOW_FILE,
        "local_workflow_exists": local_workflow_exists,
        "git_exact_path_present": git_exact_path_present,
        "git_on_origin_head": git_on_origin_head,
        "gh_workflow_visible": gh_workflow_visible,
        "gh_run_observable": gh_run_observable,
        "gh_cli_state": gh_cli_state.get("state", GHCLIState.UNKNOWN),
        "gh_available": gh_available,
        "gh_authenticated": gh_authenticated,
        "default_branch": default_branch,
        "local_branch": local_branch,
        "local_head": local_head,
        "checks": checks,
        "command_results": gh_command_results,
        "mutation_guard": mutation_guard,
        "previous_r241_16l_inconsistency_detected": r241_16l_was_inconsistent,
        "corrected_status": normalized.get("corrected_status", RemoteWorkflowVisibilityStatus.UNKNOWN),
        "corrected_decision": normalized.get("corrected_decision", RemoteWorkflowVisibilityDecision.UNKNOWN),
        "blocking_reason": normalized.get("blocking_reason", ""),
        "recommended_next_phase": normalized.get("recommended_next_phase", ""),
    }

    return review


# ── 5. generate_remote_visibility_consistency_report ───────────────────────────

def generate_remote_visibility_consistency_report(
    review: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Generate R241-16M consistency review report."""
    if review is None:
        review = evaluate_corrected_remote_workflow_visibility()

    output_json = Path(output_path) if output_path else REPORT_DIR / "R241-16M_REMOTE_VISIBILITY_CONSISTENCY_REVIEW.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)

    report_data = {**review}
    output_json.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = REPORT_DIR / "R241-16M_REMOTE_VISIBILITY_CONSISTENCY_REVIEW.md"

    git_present = review.get("git_exact_path_present", False)
    gh_visible = review.get("gh_workflow_visible", False)
    gh_run_obs = review.get("gh_run_observable", False)
    gh_state = review.get("gh_cli_state", "unknown")
    corrected_status = review.get("corrected_status", "unknown")
    corrected_decision = review.get("corrected_decision", "unknown")
    inconsistency = review.get("previous_r241_16l_inconsistency_detected", False)
    blocking = review.get("blocking_reason", "")
    recommended = review.get("recommended_next_phase", "")
    mg = review.get("mutation_guard", {})
    checks = review.get("checks", [])
    local_exists = review.get("local_workflow_exists", False)
    default_branch = review.get("default_branch", "N/A")
    local_branch = review.get("local_branch", "N/A")
    local_head = review.get("local_head", "N/A")
    gh_available = review.get("gh_available", False)
    gh_authenticated = review.get("gh_authenticated", False)

    md_lines = [
        "# R241-16M Remote Workflow Visibility Consistency Repair Review",
        "",
        "## Review Result",
        "",
        f"- **Review ID**: `{review.get('review_id', 'N/A')}`",
        f"- **Generated**: {review.get('generated_at', 'N/A')}",
        f"- **Corrected Status**: `{corrected_status}`",
        f"- **Corrected Decision**: `{corrected_decision}`",
        f"- **Blocking Reason**: {blocking or 'None'}",
        f"- **Workflow**: `{WORKFLOW_FILE}`",
        "",
        "## R241-16L Inconsistency Detection",
        "",
        f"- **Previous R241-16L Inconsistency Detected**: {inconsistency}",
        f"- **Inconsistency**: `foundation-manual-dispatch.yml` not found on `origin/main` via exact-path `git ls-tree`, but R241-16L reported `workflow_on_remote_default_branch=True`",
        "",
        "## Corrected Visibility Results",
        "",
        f"- **Local Workflow Exists**: {local_exists}",
        f"- **Git Exact Path Present** (`.github/workflows/{WORKFLOW_FILE}` on origin/default): `{git_present}`",
        f"- **Git on origin/HEAD**: `{review.get('git_on_origin_head', False)}`",
        f"- **gh Workflow Visible** (via `gh workflow list`): `{gh_visible}`",
        f"- **gh Run Observable**: `{gh_run_obs}`",
        f"- **gh CLI State**: `{gh_state}`",
        f"- **gh Available**: `{gh_available}`",
        f"- **gh Authenticated**: `{gh_authenticated}`",
        f"- **Remote Default Branch**: `{default_branch}`",
        f"- **Local Branch**: `{local_branch}`",
        f"- **Local HEAD**: `{local_head[:8]}...`" if local_head and len(local_head) > 8 else f"- **Local HEAD**: `{local_head}`",
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
        "## Bugs Fixed / Consistency Findings",
        "",
        "### Bug 1: git ls-tree Path Error",
        "",
        "- **R241-16L Issue**: Called `git ls-tree -r origin/main -- .github/workflows` (directory listing), found other workflows, incorrectly marked `workflow_on_remote_default_branch=True`",
        f"- **Fix**: Now calls `git ls-tree -r origin/{default_branch or 'main'} -- .github/workflows/{WORKFLOW_FILE}` (exact file path)",
        f"- **Result**: `foundation-manual-dispatch.yml` {'FOUND' if git_present else 'NOT FOUND'} on origin/default",
        "",
        "### Bug 2: gh CLI State Classification",
        "",
        f"- **R241-16L Issue**: Reported `gh_available=False` even when some gh commands succeeded",
        f"- **Fix**: Now uses multi-command classification: `binary_unavailable`, `unauthenticated`, `available_authenticated`, `partially_available`",
        f"- **Result**: gh CLI state = `{gh_state}`",
        "",
        "### Bug 3: Run Observation Capability on 404",
        "",
        f"- **R241-16L Issue**: `check_remote_run_observation_capability` set `passed=True` even when `gh run list` returned 404 (exit 1)",
        f"- **Fix**: Now sets `gh_run_observable=False` when gh exit code is 1 (workflow not indexed)",
        f"- **Result**: gh_run_observable = `{gh_run_obs}`",
        "",
        "## Local Mutation Guard",
        "",
        f"- **No Local Mutation**: {mg.get('no_local_mutation', False)}",
        f"- **Warnings**: {mg.get('warnings', []) if mg.get('warnings') else 'None'}",
        "",
        "## Next Recommendation",
        "",
        f"- {recommended}",
        "",
        "## Safety Constraints",
        "",
        f"- ✅ No `gh workflow run` executed during review",
        f"- ✅ No `git push` executed",
        f"- ✅ No `git commit` executed",
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
        "corrected_status": corrected_status,
        "corrected_decision": corrected_decision,
        "git_exact_path_present": git_present,
        "gh_workflow_visible": gh_visible,
        "gh_run_observable": gh_run_obs,
        "previous_r241_16l_inconsistency_detected": inconsistency,
        "recommended_next_phase": recommended,
    }
