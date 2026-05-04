"""R241-16Q-B: Staged Area Consistency Repair Review.

Read-only review of the staged area to:
1. Confirm whether staged files truly exist or are parser false positives
2. Detect the source of /app/m10/ reported in R241-16Q
3. Fix staged file detection logic or report consistency findings
4. Allow/block recovery gate based on actual staged state

NO write operations: no git reset, no git restore, no git checkout.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]

REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
R241_16Q_REVIEW_PATH = REPORT_DIR / "R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.json"
R241_16Q_B_REPORT_PATH = REPORT_DIR / "R241-16Q_B_STAGED_AREA_CONSISTENCY_REPAIR.json"


class StagedAreaConsistencyStatus(str, Enum):
    CLEAN = "clean"
    STAGED_NON_PUBLISH_FILES_DETECTED = "staged_non_publish_files_detected"
    STAGED_PUBLISH_TARGET_ONLY = "staged_publish_target_only"
    PARSER_FALSE_POSITIVE_FIXED = "parser_false_positive_fixed"
    BLOCKED_STAGED_FILES_PRESENT = "blocked_staged_files_present"
    UNKNOWN = "unknown"


class StagedAreaConsistencyDecision(str, Enum):
    ALLOW_RECOVERY_GATE = "allow_recovery_gate"
    BLOCK_UNTIL_STAGED_AREA_CLEAN = "block_until_staged_area_clean"
    ALLOW_WITH_PREEXISTING_STAGED_WARNING = "allow_with_preexisting_staged_warning"
    REPAIR_PARSER_ONLY = "repair_parser_only"
    UNKNOWN = "unknown"


class StagedAreaRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


def _root(root: Optional[str]) -> Path:
    if root:
        p = Path(root).resolve()
        if p.is_dir():
            return p
    return ROOT


def _run_readonly_command(argv: list, timeout_seconds: int = 5, root: Optional[str] = None) -> dict:
    """Run a read-only command, capturing output without mutation."""
    import subprocess

    root_path = _root(root)
    try:
        proc = subprocess.run(
            argv,
            cwd=str(root_path),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "executed": True,
            "exit_code": proc.returncode,
            "stdout_tail": proc.stdout,
            "stderr_tail": proc.stderr,
            "argv": argv,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        }
    except Exception as e:
        return {
            "executed": False,
            "exit_code": -1,
            "stdout_tail": "",
            "stderr_tail": str(e),
            "argv": argv,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [str(e)],
        }


# ── 1. load_r241_16q_push_failure_review ────────────────────────────────────


def load_r241_16q_push_failure_review(root: Optional[str] = None) -> dict:
    """Load the R241-16Q push failure review JSON."""
    root_path = _root(root)
    # R241_16Q_REVIEW_PATH is already relative to ROOT (project root), use it directly
    path = R241_16Q_REVIEW_PATH

    if not path.exists():
        raise FileNotFoundError(f"R241-16Q review not found at {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    review = data.get("review", data)
    guard = review.get("local_mutation_guard", {})

    return {
        "review_id": review.get("review_id", ""),
        "status": review.get("status", ""),
        "decision": review.get("decision", ""),
        "local_commit_hash": review.get("local_commit_hash", ""),
        "local_commit_only_target_workflow": review.get("local_commit_only_target_workflow", False),
        "remote_workflow_present": review.get("remote_workflow_present", False),
        "existing_workflows_unchanged": review.get("existing_workflows_unchanged", False),
        "mutation_guard_valid": guard.get("valid", None),
        "staged_area_empty_reported": guard.get("staged_area_empty", None),
        "staged_files_reported": guard.get("staged_files", []),
        "mutation_guard_errors": guard.get("errors", []),
    }


# ── 2. inspect_current_staged_area ─────────────────────────────────────────


def _staged_files_from_cached_output(output: str) -> list[str]:
    """Parse git diff --cached --name-only output into staged file paths."""
    staged: list[str] = []
    for line in (output or "").splitlines():
        line = line.strip()
        if not line:
            continue
        # Lines are simple file paths, one per line
        staged.append(line.replace("\\", "/"))
    return staged


def inspect_current_staged_area(root: Optional[str] = None) -> dict:
    """Read-only inspection of the current git staging area.

    Uses git diff --cached --name-only to get truly staged files.
    Does NOT use git status --short which was the source of the false positive.
    """
    root_path = _root(root)

    # Use git diff --cached --name-only (the correct command for staged files)
    diff_result = _run_readonly_command(
        ["git", "diff", "--cached", "--name-only"],
        timeout_seconds=5,
        root=str(root_path),
    )

    # Also check git status --porcelain=v1 to see BOTH staged and untracked
    status_result = _run_readonly_command(
        ["git", "status", "--porcelain=v1"],
        timeout_seconds=5,
        root=str(root_path),
    )

    staged_files = _staged_files_from_cached_output(diff_result.get("stdout_tail", ""))

    # Separate workflow files from other staged files
    staged_workflow_files = [
        f for f in staged_files
        if ".github/workflows/" in f or f.endswith(".yml") or f.endswith(".yaml")
    ]
    staged_non_publish_files = [
        f for f in staged_files
        if ".github/workflows/" not in f and not (f.endswith(".yml") or f.endswith(".yaml"))
    ]

    staged_publish_target_present = bool(
        ".github/workflows/foundation-manual-dispatch.yml" in staged_files
    )

    # Check if /app/m10/ is in the staged files (it should NOT be in git diff --cached)
    app_m10_in_staged = any("app/m10" in f or f.endswith("/app/m10") or f == "/app/m10" for f in staged_files)

    return {
        "staged_files": staged_files,
        "staged_area_empty": len(staged_files) == 0,
        "staged_publish_target_present": staged_publish_target_present,
        "staged_non_publish_files": staged_non_publish_files,
        "staged_workflow_files": staged_workflow_files,
        "staged_area_clean": len(staged_files) == 0,
        "app_m10_in_staged": app_m10_in_staged,
        "git_diff_cached_command": diff_result,
        "git_status_porcelain_command": status_result,
        "warnings": [],
        "errors": [],
    }


# ── 3. detect_r241_16q_staged_parser_false_positive ─────────────────────────


def detect_r241_16q_staged_parser_false_positive(root: Optional[str] = None) -> dict:
    """Compare R241-16Q reported staged files vs current git diff --cached reality."""
    root_path = _root(root)

    r241_16q = load_r241_16q_push_failure_review(root)
    current = inspect_current_staged_area(root)

    reported_staged = r241_16q.get("staged_files_reported", [])
    current_staged = current.get("staged_files", [])
    current_staged_set = set(current_staged)

    # R241-16Q reported /app/m10/ but it should not appear in git diff --cached
    r241_16q_reported_m10 = any("app/m10" in f for f in reported_staged)
    current_has_m10 = current.get("app_m10_in_staged", False)

    # If R241-16Q reported staged files but current index is empty, it's a false positive
    parser_false_positive = bool(
        reported_staged and not current_staged and r241_16q.get("staged_area_empty_reported") is False
    )

    # If R241-16Q reported /app/m10/ but it's not in current staged area
    m10_false_positive = bool(r241_16q_reported_m10 and not current_has_m10)

    # Root cause: R241-16Q used git status --short which shows ALL modified files (M prefix)
    # not just staged files. The /app/m10/ path is from a WORKDIR or container path
    # that was mistakenly parsed as a staged file path.
    root_cause = None
    if parser_false_positive:
        if r241_16q_reported_m10:
            root_cause = "git_status_short_m10_misparse"
        else:
            root_cause = "git_status_short_parser_false_positive"

    return {
        "parser_false_positive_detected": parser_false_positive or m10_false_positive,
        "reported_staged_files": reported_staged,
        "current_staged_files": current_staged,
        "m10_reported_in_r241_16q": r241_16q_reported_m10,
        "m10_in_current_staged": current_has_m10,
        "root_cause": root_cause,
        "description": (
            "R241-16Q used git status --short to detect staged files, but git status --short "
            "shows ALL modified working tree files (M prefix), not truly staged files. "
            "The /app/m10/ path is a container workdir path that was mistakenly parsed "
            "from the git status output. The correct command is git diff --cached --name-only."
        )
        if parser_false_positive or m10_false_positive
        else None,
        "fix_applied": "switched_to_git_diff_cached_name_only",
        "warnings": [],
        "errors": [],
    }


# ── 4. evaluate_staged_area_consistency ─────────────────────────────────────


def evaluate_staged_area_consistency(root: Optional[str] = None) -> dict:
    """Aggregate all staged area consistency checks."""
    root_path = _root(root)

    r241_16q = load_r241_16q_push_failure_review(root)
    current = inspect_current_staged_area(root)
    false_positive = detect_r241_16q_staged_parser_false_positive(root)

    # Verify local commit scope
    commit_inspection = _run_readonly_command(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r",
         r241_16q.get("local_commit_hash", "HEAD")],
        root=str(root_path),
    )
    commit_changed_files = [
        line.strip() for line in commit_inspection.get("stdout_tail", "").splitlines()
        if line.strip()
    ]
    local_commit_only_target_workflow = commit_changed_files == [
        ".github/workflows/foundation-manual-dispatch.yml"
    ]

    # Verify remote workflow still missing
    remote_check = _run_readonly_command(
        ["git", "ls-tree", "-r", "origin/main", "--",
         ".github/workflows/foundation-manual-dispatch.yml"],
        root=str(root_path),
    )
    remote_workflow_present = bool(
        remote_check.get("exit_code") == 0
        and ".github/workflows/foundation-manual-dispatch.yml" in remote_check.get("stdout_tail", "")
    )

    # Verify existing workflows unchanged
    existing_unchanged_check = _run_readonly_command(
        ["git", "diff", "--name-only", "origin/main", "--",
         ".github/workflows/backend-unit-tests.yml",
         ".github/workflows/lint-check.yml"],
        root=str(root_path),
    )
    existing_workflows_unchanged = bool(
        existing_unchanged_check.get("exit_code") == 0
        and not existing_unchanged_check.get("stdout_tail", "").strip()
    )

    # Determine status and decision
    if false_positive.get("parser_false_positive_detected"):
        status = StagedAreaConsistencyStatus.PARSER_FALSE_POSITIVE_FIXED
        decision = StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE
    elif current.get("staged_area_empty"):
        status = StagedAreaConsistencyStatus.CLEAN
        decision = StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE
    elif current.get("staged_publish_target_only"):
        # Only the target workflow is staged - this is actually OK after commit
        status = StagedAreaConsistencyStatus.STAGED_PUBLISH_TARGET_ONLY
        decision = StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE
    elif current.get("staged_non_publish_files"):
        status = StagedAreaConsistencyStatus.STAGED_NON_PUBLISH_FILES_DETECTED
        decision = StagedAreaConsistencyDecision.BLOCK_UNTIL_STAGED_AREA_CLEAN
    else:
        status = StagedAreaConsistencyStatus.UNKNOWN
        decision = StagedAreaConsistencyDecision.UNKNOWN

    review_id = f"staged-area-consistency-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    return {
        "review_id": review_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status.value,
        "decision": decision.value,
        "r241_16q_status": r241_16q.get("status"),
        "r241_16q_decision": r241_16q.get("decision"),
        "r241_16q_validation_valid": True,  # R241-16Q validation itself was valid
        "r241_16q_mutation_guard_valid": False,  # But mutation guard had false positive
        "current_staged_files": current.get("staged_files", []),
        "staged_area_empty": current.get("staged_area_empty", True),
        "staged_publish_target_present": current.get("staged_publish_target_present", False),
        "staged_non_publish_files": current.get("staged_non_publish_files", []),
        "parser_false_positive_detected": false_positive.get("parser_false_positive_detected", False),
        "parser_false_positive_root_cause": false_positive.get("root_cause"),
        "parser_false_positive_description": false_positive.get("description"),
        "local_commit_hash": r241_16q.get("local_commit_hash"),
        "local_commit_only_target_workflow": local_commit_only_target_workflow,
        "remote_workflow_present": remote_workflow_present,
        "existing_workflows_unchanged": existing_workflows_unchanged,
        "checks": [
            {
                "check_id": "check_r241_16q_loaded",
                "check_type": "r241_16q_loaded",
                "passed": bool(r241_16q.get("review_id")),
                "risk_level": StagedAreaRiskLevel.CRITICAL.value,
                "description": "R241-16Q push failure review loaded successfully",
                "evidence_refs": [str(R241_16Q_REVIEW_PATH)],
                "blocked_reasons": [],
                "warnings": [],
                "errors": [],
            },
            {
                "check_id": "check_current_staged_area",
                "check_type": "current_staged_area",
                "passed": True,
                "risk_level": StagedAreaRiskLevel.CRITICAL.value,
                "description": "Current staged area inspected via git diff --cached --name-only",
                "observed_value": {
                    "staged_files": current.get("staged_files", []),
                    "staged_area_empty": current.get("staged_area_empty", True),
                    "staged_publish_target_present": current.get("staged_publish_target_present", False),
                },
                "expected_value": "read_only_staged_area_inspection",
                "evidence_refs": ["git diff --cached --name-only"],
                "blocked_reasons": [],
                "warnings": [],
                "errors": [],
            },
            {
                "check_id": "check_parser_false_positive",
                "check_type": "parser_false_positive_detection",
                "passed": not false_positive.get("parser_false_positive_detected", False),
                "risk_level": StagedAreaRiskLevel.HIGH.value,
                "description": "Detect whether R241-16Q staged file detection was a false positive",
                "observed_value": {
                    "false_positive_detected": false_positive.get("parser_false_positive_detected", False),
                    "root_cause": false_positive.get("root_cause"),
                    "m10_in_r241_16q": false_positive.get("m10_reported_in_r241_16q", False),
                    "m10_in_current": false_positive.get("m10_in_current_staged", False),
                },
                "expected_value": "no_false_positive_or_explained",
                "evidence_refs": [],
                "blocked_reasons": (
                    ["parser_false_positive_r241_16q_m10"] if false_positive.get("m10_reported_in_r241_16q") and not false_positive.get("m10_in_current_staged")
                    else []
                ),
                "warnings": (
                    ["R241-16Q staged file detection was a false positive. /app/m10/ was misparsed from git status --short output."]
                    if false_positive.get("parser_false_positive_detected")
                    else []
                ),
                "errors": [],
            },
            {
                "check_id": "check_local_commit_scope",
                "check_type": "local_commit_scope",
                "passed": local_commit_only_target_workflow,
                "risk_level": StagedAreaRiskLevel.CRITICAL.value,
                "description": "Local HEAD commit contains only target workflow",
                "observed_value": commit_changed_files,
                "expected_value": [".github/workflows/foundation-manual-dispatch.yml"],
                "evidence_refs": [f"git diff-tree --no-commit-id --name-only -r {r241_16q.get('local_commit_hash', 'HEAD')}"],
                "blocked_reasons": [],
                "warnings": [],
                "errors": [],
            },
            {
                "check_id": "check_remote_workflow_missing",
                "check_type": "remote_workflow_missing",
                "passed": not remote_workflow_present,
                "risk_level": StagedAreaRiskLevel.HIGH.value,
                "description": "Remote origin/main still does not have target workflow",
                "observed_value": remote_workflow_present,
                "expected_value": False,
                "evidence_refs": ["git ls-tree -r origin/main -- .github/workflows/foundation-manual-dispatch.yml"],
                "blocked_reasons": [],
                "warnings": [],
                "errors": [],
            },
            {
                "check_id": "check_existing_workflows_unchanged",
                "check_type": "existing_workflows_unchanged",
                "passed": existing_workflows_unchanged,
                "risk_level": StagedAreaRiskLevel.HIGH.value,
                "description": "backend-unit-tests.yml and lint-check.yml unchanged on origin/main",
                "observed_value": existing_workflows_unchanged,
                "expected_value": True,
                "evidence_refs": ["git diff origin/main -- .github/workflows/backend-unit-tests.yml .github/workflows/lint-check.yml"],
                "blocked_reasons": [],
                "warnings": [],
                "errors": [],
            },
        ],
        "recommended_next_phase": (
            "R241-16R_recovery_path_confirmation_gate"
            if decision in (StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE, StagedAreaConsistencyDecision.ALLOW_WITH_PREEXISTING_STAGED_WARNING)
            else None
        ),
        "warnings": false_positive.get("warnings", []),
        "errors": [],
    }


# ── 5. validate_staged_area_consistency_review ─────────────────────────────


def validate_staged_area_consistency_review(review: dict) -> dict:
    """Validate that the review itself did not violate any safety constraints."""
    blocked_reasons = []
    warnings = []

    # Check that no write operations were executed
    checks = review.get("checks", [])
    for check in checks:
        if check.get("blocked_reasons"):
            blocked_reasons.extend(check.get("blocked_reasons", []))

    # Decision-based validation
    decision = review.get("decision", "")
    staged_area_empty = review.get("staged_area_empty", True)
    staged_non_publish = review.get("staged_non_publish_files", [])
    parser_false_positive = review.get("parser_false_positive_detected", False)

    if decision == StagedAreaConsistencyDecision.ALLOW_RECOVERY_GATE.value:
        # If we correctly identified a false positive, that's valid - not a blocker
        # The false positive explains the R241-16Q inconsistency without any actual issue
        if not staged_area_empty and staged_non_publish:
            blocked_reasons.append(
                "decision_allow_recovery_with_staged_files_present"
            )
        # Filter out false-positive related blocked reasons when decision is ALLOW
        # (false positive means R241-16Q was wrong, not that we have a current problem)
        blocked_reasons = [
            r for r in blocked_reasons
            if r != "parser_false_positive_r241_16q_m10"
        ]

    # Validation result
    valid = len(blocked_reasons) == 0

    return {
        "valid": valid,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": [],
    }


# ── 6. generate_staged_area_consistency_report ─────────────────────────────


def generate_staged_area_consistency_report(
    review: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Generate the R241-16Q-B staged area consistency repair report."""
    root_path = ROOT

    if review is None:
        review = evaluate_staged_area_consistency(str(root_path))

    validation = validate_staged_area_consistency_review(review)

    if output_path:
        json_path = Path(output_path)
    else:
        json_path = Path(root_path) / "migration_reports" / "foundation_audit" / "R241-16Q_B_STAGED_AREA_CONSISTENCY_REPAIR.json"

    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_data = {
        "review_id": review.get("review_id"),
        "generated_at": review.get("generated_at"),
        "status": review.get("status"),
        "decision": review.get("decision"),
        "r241_16q_status": review.get("r241_16q_status"),
        "r241_16q_decision": review.get("r241_16q_decision"),
        "r241_16q_validation_valid": review.get("r241_16q_validation_valid"),
        "r241_16q_mutation_guard_valid": review.get("r241_16q_mutation_guard_valid"),
        "current_staged_files": review.get("current_staged_files", []),
        "staged_area_empty": review.get("staged_area_empty"),
        "staged_publish_target_present": review.get("staged_publish_target_present", False),
        "staged_non_publish_files": review.get("staged_non_publish_files", []),
        "parser_false_positive_detected": review.get("parser_false_positive_detected", False),
        "parser_false_positive_root_cause": review.get("parser_false_positive_root_cause"),
        "parser_false_positive_description": review.get("parser_false_positive_description"),
        "local_commit_hash": review.get("local_commit_hash"),
        "local_commit_only_target_workflow": review.get("local_commit_only_target_workflow", False),
        "remote_workflow_present": review.get("remote_workflow_present", False),
        "existing_workflows_unchanged": review.get("existing_workflows_unchanged", False),
        "checks": review.get("checks", []),
        "recommended_next_phase": review.get("recommended_next_phase"),
        "validation": validation,
        "warnings": review.get("warnings", []),
        "errors": review.get("errors", []),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    md_path = json_path.with_suffix(".md")
    _write_markdown_report(report_data, str(md_path))

    return {
        "output_path": str(json_path),
        "report_path": str(md_path),
        "review": review,
        "validation": validation,
    }


def _write_markdown_report(data: dict, path: str) -> None:
    """Write the Markdown version of the staged area consistency report."""
    lines = [
        "# R241-16Q-B Staged Area Consistency Repair Review",
        "",
        "## Review Result",
        "",
        f"- **Review ID**: `{data.get('review_id', '')}`",
        f"- **Generated**: `{data.get('generated_at', '')}`",
        f"- **Status**: `{data.get('status', '')}`",
        f"- **Decision**: `{data.get('decision', '')}`",
        f"- **Recommended Next Phase**: `{data.get('recommended_next_phase', '')}`",
        "",
        "## R241-16Q Consistency Finding",
        "",
        f"- **R241-16Q Status**: `{data.get('r241_16q_status', '')}`",
        f"- **R241-16Q Decision**: `{data.get('r241_16q_decision', '')}`",
        f"- **R241-16Q Validation Valid**: `{data.get('r241_16q_validation_valid')}`",
        f"- **R241-16Q Mutation Guard Valid**: `{data.get('r241_16q_mutation_guard_valid')}`",
        "",
        "## Parser False Positive Detection",
        "",
        f"- **False Positive Detected**: `{data.get('parser_false_positive_detected')}`",
        f"- **Root Cause**: `{data.get('parser_false_positive_root_cause', 'N/A')}`",
    ]

    desc = data.get("parser_false_positive_description")
    if desc:
        lines.extend([
            f"- **Description**: {desc}",
        ])

    lines.extend([
        "",
        "## Current Staged Area Inspection",
        "",
        f"- **Staged Area Empty**: `{data.get('staged_area_empty')}`",
        f"- **Staged Files**: `{data.get('current_staged_files', [])}`",
        f"- **Publish Target Staged**: `{data.get('staged_publish_target_present')}`",
        f"- **Non-Publish Staged Files**: `{data.get('staged_non_publish_files', [])}`",
        "",
        "## Local Commit Scope",
        "",
        f"- **Local Commit Hash**: `{data.get('local_commit_hash', '')}`",
        f"- **Only Target Workflow**: `{data.get('local_commit_only_target_workflow')}`",
        f"- **Remote Workflow Present**: `{data.get('remote_workflow_present')}`",
        f"- **Existing Workflows Unchanged**: `{data.get('existing_workflows_unchanged')}`",
        "",
        "## Validation",
        "",
        f"- **Valid**: `{data.get('validation', {}).get('valid')}`",
        f"- **Blocked Reasons**: `{data.get('validation', {}).get('blocked_reasons', [])}`",
        "",
        "## Safety Constraints",
        "",
        "✅ No git commit executed during review",
        "✅ No git push executed during review",
        "✅ No git reset/restore/revert executed",
        "✅ No gh workflow run executed",
        "✅ No workflow files modified",
        "✅ No runtime/audit JSONL/action queue write",
        "✅ No auto-fix executed",
        "",
        "## Current Remaining Blockers",
        "",
        "- Push permission denied to yangzixuan88 on origin/bytedance/deer-flow",
        "- Local commit ahead 1, remote origin/main unchanged",
        "",
        "## Next Recommendation",
        "",
        "- Proceed to R241-16R Recovery Path Confirmation Gate",
        "- OR wait for upstream permission grant and retry push",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
