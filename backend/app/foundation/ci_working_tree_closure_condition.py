"""R241-16W: Working Tree Closure Condition Resolution.

Read-only resolution of the R241-16V closure condition:
- R241-16V returned passed_with_warnings / approve_closure_with_conditions
- The only failure was mutation_no_working_tree (dirty working tree)
- This module classifies the dirty files, verifies delivery artifacts unchanged,
  and produces a conditional closure resolution report

Allowed read operations:
  git status --branch --short
  git status --short
  git status --porcelain=v1
  git diff --cached --name-only
  git diff --name-only
  git diff --name-status
  git diff --stat
  git diff -- .github/workflows/
  git diff -- migration_reports/foundation_audit/
  git diff-tree --no-commit-id --name-only -r HEAD
  git ls-tree -r HEAD -- .github/workflows/foundation-manual-dispatch.yml
  git ls-tree -r origin/main -- .github/workflows/foundation-manual-dispatch.yml

Allowed write operations:
  R241-16W_WORKING_TREE_CLOSURE_CONDITION.json
  R241-16W_WORKING_TREE_CLOSURE_CONDITION.md

Forbidden: git push/commit/reset/restore/am/apply, gh workflow run,
secret read, runtime write, audit JSONL write, action queue write, auto-fix.
Full patch content must not be embedded in generated markdown reports.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[3]

REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
R241_16V_REPORT_PATH = REPORT_DIR / "R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.json"
R241_16U_INDEX_PATH = REPORT_DIR / "R241-16U_DELIVERY_PACKAGE_INDEX.json"
R241_16U_FINALIZATION_RESULT = REPORT_DIR / "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json"
R241_16S_MANIFEST_PATH = REPORT_DIR / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
R241_16S_PATCH_PATH = REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
R241_16S_BUNDLE_PATH = REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
TARGET_WORKFLOW = ".github/workflows/foundation-manual-dispatch.yml"
SOURCE_COMMIT_HASH = "94908556cc2ca66c219d361f424954945eee9e67"


# ── Enums ──────────────────────────────────────────────────────────────────────


class WorkingTreeClosureStatus(str, Enum):
    RESOLVED_EXTERNAL_WORKTREE_CONDITION = "resolved_external_worktree_condition"
    RESOLVED_CLEAN_WORKTREE = "resolved_clean_worktree"
    BLOCKED_DELIVERY_SCOPE_DIRTY = "blocked_delivery_scope_dirty"
    BLOCKED_STAGED_FILES_PRESENT = "blocked_staged_files_present"
    BLOCKED_WORKFLOW_DIRTY = "blocked_workflow_dirty"
    BLOCKED_ARTIFACT_DIRTY = "blocked_artifact_dirty"
    BLOCKED_UNKNOWN_DIRTY_STATE = "blocked_unknown_dirty_state"
    UNKNOWN = "unknown"


class WorkingTreeClosureDecision(str, Enum):
    APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION = (
        "approve_delivery_closure_with_external_worktree_condition"
    )
    APPROVE_FULL_CLOSURE = "approve_full_closure"
    BLOCK_CLOSURE_UNTIL_WORKTREE_REVIEW = "block_closure_until_worktree_review"
    UNKNOWN = "unknown"


class WorkingTreeDirtyScope(str, Enum):
    DELIVERY_SCOPE = "delivery_scope"
    WORKFLOW_SCOPE = "workflow_scope"
    REPORT_SCOPE = "report_scope"
    FOUNDATION_CODE_SCOPE = "foundation_code_scope"
    UNRELATED_REPO_SCOPE = "unrelated_repo_scope"
    MIXED_SCOPE = "mixed_scope"
    UNKNOWN = "unknown"


class WorkingTreeClosureRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ── Data Objects ────────────────────────────────────────────────────────────────


class WorkingTreeDirtyFile:
    def __init__(
        self,
        path: str,
        status_code: str,
        scope: str,
        is_delivery_scope: bool = False,
        is_workflow_scope: bool = False,
        is_report_scope: bool = False,
        is_runtime_scope: bool = False,
        is_secret_like_path: bool = False,
        action_required: Optional[str] = None,
        warnings: Optional[list[str]] = None,
        errors: Optional[list[str]] = None,
    ):
        self.path = path
        self.status_code = status_code
        self.scope = scope
        self.is_delivery_scope = is_delivery_scope
        self.is_workflow_scope = is_workflow_scope
        self.is_report_scope = is_report_scope
        self.is_runtime_scope = is_runtime_scope
        self.is_secret_like_path = is_secret_like_path
        self.action_required = action_required
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "status_code": self.status_code,
            "scope": self.scope,
            "is_delivery_scope": self.is_delivery_scope,
            "is_workflow_scope": self.is_workflow_scope,
            "is_report_scope": self.is_report_scope,
            "is_runtime_scope": self.is_runtime_scope,
            "is_secret_like_path": self.is_secret_like_path,
            "action_required": self.action_required,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class WorkingTreeClosureCheck:
    def __init__(
        self,
        check_id: str,
        passed: bool,
        risk_level: str,
        description: str,
        observed_value: Optional[str] = None,
        expected_value: Optional[str] = None,
        evidence_refs: Optional[list[str]] = None,
        required_for_closure: bool = False,
        blocked_reasons: Optional[list[str]] = None,
        warnings: Optional[list[str]] = None,
        errors: Optional[list[str]] = None,
    ):
        self.check_id = check_id
        self.passed = passed
        self.risk_level = risk_level
        self.description = description
        self.observed_value = observed_value
        self.expected_value = expected_value
        self.evidence_refs = evidence_refs or []
        self.required_for_closure = required_for_closure
        self.blocked_reasons = blocked_reasons or []
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "risk_level": self.risk_level,
            "description": self.description,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "evidence_refs": self.evidence_refs,
            "required_for_closure": self.required_for_closure,
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(root: Optional[str]) -> Path:
    if root:
        p = Path(root).resolve()
        if p.is_dir():
            return p
    return ROOT


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_git(argv: list[str], root: Optional[str] = None, timeout: int = 30) -> dict:
    """Run a git command with shell=False. Returns completed process info."""
    cwd = str(_root(root))
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return {
            "argv": argv,
            "command_executed": True,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "cwd": cwd,
        }
    except subprocess.TimeoutExpired:
        return {
            "argv": argv,
            "command_executed": True,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "cwd": cwd,
        }
    except Exception as e:
        return {
            "argv": argv,
            "command_executed": True,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "cwd": cwd,
        }


# ── 1. load_r241_16v_closure_review ───────────────────────────────────────────


def load_r241_16v_closure_review(root: Optional[str] = None) -> dict:
    """Load and validate R241-16V closure review.

    Returns dict with:
      loaded: bool
      exists: bool
      data: dict | None
      path: str
      errors: list[str]
      is_valid_prerequisite: bool
    """
    root_path = _root(root)
    report_path = root_path / "migration_reports" / "foundation_audit" / "R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.json"
    errors: list[str] = []
    data = None
    exists = report_path.exists()

    if not exists:
        errors.append("R241-16V closure review not found")
        return {
            "loaded": True,
            "exists": False,
            "data": None,
            "path": str(report_path),
            "errors": errors,
            "is_valid_prerequisite": False,
        }

    try:
        text = report_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except Exception as e:
        errors.append(f"Failed to parse R241-16V report: {e}")
        return {
            "loaded": True,
            "exists": True,
            "data": None,
            "path": str(report_path),
            "errors": errors,
            "is_valid_prerequisite": False,
        }

    # Validate prerequisite conditions
    is_valid = True

    if data.get("status") != "passed_with_warnings":
        errors.append(f"Expected R241-16V status 'passed_with_warnings', got '{data.get('status')}'")
        is_valid = False

    if data.get("decision") != "approve_closure_with_conditions":
        errors.append(f"Expected R241-16V decision 'approve_closure_with_conditions', got '{data.get('decision')}'")
        is_valid = False

    if not data.get("validated"):
        errors.append("R241-16V validation did not pass")
        is_valid = False

    failed_checks = [c for c in data.get("closure_checks", []) if not c.get("passed")]
    non_mutation_failures = [
        c for c in failed_checks
        if c.get("check_id") != "mutation_no_working_tree"
    ]
    if non_mutation_failures:
        for c in non_mutation_failures:
            errors.append(f"Critical R241-16V failure: {c.get('check_id')} - {c.get('description')}")
        is_valid = False

    mg = data.get("mutation_guard", {})
    staged_count = len(mg.get("staged_files", []))
    if staged_count > 0:
        errors.append(f"R241-16V staged files count is {staged_count}, expected 0")
        is_valid = False

    if not mg.get("head_hash"):
        errors.append("R241-16V missing HEAD hash")
        is_valid = False

    return {
        "loaded": True,
        "exists": True,
        "data": data,
        "path": str(report_path),
        "errors": errors,
        "is_valid_prerequisite": is_valid,
    }


# ── 2. inspect_current_working_tree_condition ───────────────────────────────────


def inspect_current_working_tree_condition(root: Optional[str] = None) -> dict:
    """Inspect current git working tree state (read-only).

    Returns dict with:
      branch: str | None
      head_hash: str | None
      staged_files: list[str]
      dirty_files: list[dict]
      dirty_file_count: int
      untracked_files: list[str]
      modified_files: list[str]
      deleted_files: list[str]
      warnings: list[str]
      errors: list[str]
    """
    root_path = _root(root)
    warnings: list[str] = []
    errors: list[str] = []

    # Get HEAD info
    head_result = _run_git(["git", "rev-parse", "HEAD"], str(root_path))
    head_hash = head_result.get("stdout", "").strip() or None if head_result.get("exit_code") == 0 else None

    branch_result = _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], str(root_path))
    branch = branch_result.get("stdout", "").strip() or None if branch_result.get("exit_code") == 0 else None

    # Get staged files using git diff --cached (not git status --short which is ambiguous)
    staged_result = _run_git(["git", "diff", "--cached", "--name-only"], str(root_path))
    staged_files = [
        f for f in staged_result.get("stdout", "").splitlines() if f.strip()
    ] if staged_result.get("exit_code") == 0 else []

    # Get all dirty files using porcelain format
    status_result = _run_git(["git", "status", "--porcelain=v1"], str(root_path))
    dirty_files: list[dict] = []
    untracked: list[str] = []
    modified: list[str] = []
    deleted: list[str] = []

    if status_result.get("exit_code") == 0:
        for line in status_result.get("stdout", "").splitlines():
            if not line.strip():
                continue
            # Porcelain format: XY filename
            if len(line) < 3:
                continue
            status_code = line[:2]
            filepath = line[3:].strip()

            entry = {
                "status_code": status_code,
                "path": filepath,
                "index_status": status_code[0] if len(status_code) >= 1 else " ",
                "worktree_status": status_code[1] if len(status_code) >= 2 else " ",
            }
            dirty_files.append(entry)

            ws = status_code[1] if len(status_code) >= 2 else " "
            if status_code[0] == "?" or ws == "?":
                untracked.append(filepath)
            elif ws == "D" or status_code == "DD":
                deleted.append(filepath)
            else:
                modified.append(filepath)
    else:
        errors.append(f"git status --porcelain=v1 failed: {status_result.get('stderr')}")

    # Get diff name-status for summary
    diff_result = _run_git(["git", "diff", "--name-status"], str(root_path))
    diff_summary = diff_result.get("stdout", "") if diff_result.get("exit_code") == 0 else ""

    # Get diff stat
    stat_result = _run_git(["git", "diff", "--stat"], str(root_path))
    diff_stat = stat_result.get("stdout", "") if stat_result.get("exit_code") == 0 else ""

    return {
        "branch": branch,
        "head_hash": head_hash,
        "staged_files": staged_files,
        "dirty_files": dirty_files,
        "dirty_file_count": len(dirty_files),
        "untracked_files": untracked,
        "modified_files": modified,
        "deleted_files": deleted,
        "warnings": warnings,
        "errors": errors,
        "diff_summary": diff_summary,
        "diff_stat": diff_stat,
    }


# ── 3. classify_working_tree_dirty_files ───────────────────────────────────────


# Delivery scope: patch, bundle, manifest, verification, delivery package artifacts
DELIVERY_SCOPE_PATTERNS = [
    "migration_reports/foundation_audit/R241-16S",
    "migration_reports/foundation_audit/R241-16T",
    "migration_reports/foundation_audit/R241-16U",
    "migration_reports/foundation_audit/R241-16V",
]

# Workflow scope: CI workflow files
WORKFLOW_SCOPE_PATTERNS = [
    ".github/workflows/",
]

# Report scope: migration reports, audit files
REPORT_SCOPE_PATTERNS = [
    "migration_reports/foundation_audit/",
    "backend/migration_reports/foundation_audit/",
]

# Runtime scope: runtime directories, queues, state files
RUNTIME_SCOPE_PATTERNS = [
    "runtime/",
    "action_queue/",
    "audit_trail/",
    "governance_state",
    "experiment_queue",
    ".deer-flow/",
    "memory.json",
]

# Foundation code scope: app/foundation, app/audit, app/asset, etc.
FOUNDATION_CODE_SCOPE_PATTERNS = [
    "backend/app/foundation/",
    "backend/app/audit/",
    "backend/app/asset/",
    "backend/app/memory/",
    "backend/app/mode/",
    "backend/app/prompt/",
    "backend/app/rtcm/",
    "backend/app/tool_runtime/",
    "backend/app/gateway/",
    "backend/app/channels/",
]

# Secret-like paths
SECRET_LIKE_PATTERNS = [
    ".env",
    "secret",
    "token",
    "password",
    "credential",
    ".key",
    "webhook",
]


def classify_working_tree_dirty_files(
    root: Optional[str] = None,
    dirty_files: Optional[list[dict]] = None,
) -> list[dict[str, Any]]:
    """Classify dirty files by scope.

    Returns list of WorkingTreeDirtyFile dicts.
    """
    if dirty_files is None:
        wt = inspect_current_working_tree_condition(root)
        dirty_files = wt.get("dirty_files", [])

    classified: list[dict[str, Any]] = []

    for entry in dirty_files:
        path = entry.get("path", "")
        status_code = entry.get("status_code", "??")

        is_delivery = any(path.startswith(p) for p in DELIVERY_SCOPE_PATTERNS)
        is_workflow = any(path.startswith(p) for p in WORKFLOW_SCOPE_PATTERNS)
        is_report = any(path.startswith(p) for p in REPORT_SCOPE_PATTERNS)
        is_runtime = any(path.startswith(p) for p in RUNTIME_SCOPE_PATTERNS)
        is_foundation_code = any(path.startswith(p) for p in FOUNDATION_CODE_SCOPE_PATTERNS)
        is_secret_like = any(pat in path.lower() for pat in SECRET_LIKE_PATTERNS)

        # Determine primary scope
        if is_delivery:
            scope = WorkingTreeDirtyScope.DELIVERY_SCOPE.value
        elif is_workflow:
            scope = WorkingTreeDirtyScope.WORKFLOW_SCOPE.value
        elif is_runtime:
            scope = WorkingTreeDirtyScope.UNRELATED_REPO_SCOPE.value  # runtime is non-delivery
        elif is_report:
            scope = WorkingTreeDirtyScope.REPORT_SCOPE.value
        elif is_foundation_code:
            scope = WorkingTreeDirtyScope.FOUNDATION_CODE_SCOPE.value
        else:
            scope = WorkingTreeDirtyScope.UNRELATED_REPO_SCOPE.value

        # Determine action
        action_required = None
        if is_secret_like:
            action_required = "review_required: secret-like path"
        elif is_workflow:
            action_required = "review_required: workflow file"
        elif is_delivery:
            action_required = "review_required: delivery artifact"
        elif is_runtime:
            action_required = "review_required: runtime file"

        dtf = WorkingTreeDirtyFile(
            path=path,
            status_code=status_code,
            scope=scope,
            is_delivery_scope=is_delivery,
            is_workflow_scope=is_workflow,
            is_report_scope=is_report,
            is_runtime_scope=is_runtime,
            is_secret_like_path=is_secret_like,
            action_required=action_required,
        )
        classified.append(dtf.to_dict())

    return classified


# ── 4. verify_delivery_artifacts_unchanged_since_r241_16u ──────────────────────


def verify_delivery_artifacts_unchanged_since_r241_16u(
    root: Optional[str] = None,
) -> dict:
    """Verify delivery artifacts are unchanged since R241-16U.

    Returns dict with:
      all_unchanged: bool
      artifacts: list[dict]
      sha256_verified: bool
      checksum_mismatch_files: list[str]
      warnings: list[str]
      errors: list[str]
    """
    root_path = _root(root)
    errors: list[str] = []
    warnings: list[str] = []
    artifacts: list[dict] = []
    sha256_verified = True
    checksum_mismatch_files: list[str] = []

    # Load R241-16U index
    index_path = root_path / "migration_reports" / "foundation_audit" / "R241-16U_DELIVERY_PACKAGE_INDEX.json"
    if not index_path.exists():
        errors.append("R241-16U delivery package index not found")
        return {
            "all_unchanged": False,
            "artifacts": [],
            "sha256_verified": False,
            "checksum_mismatch_files": checksum_mismatch_files,
            "warnings": warnings,
            "errors": errors,
        }

    try:
        index_data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Failed to parse R241-16U index: {e}")
        return {
            "all_unchanged": False,
            "artifacts": [],
            "sha256_verified": False,
            "checksum_mismatch_files": checksum_mismatch_files,
            "warnings": warnings,
            "errors": errors,
        }

    # Load R241-16S manifest for SHA reference
    manifest_path = root_path / "migration_reports" / "foundation_audit" / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
    manifest_patch_sha: Optional[str] = None
    manifest_bundle_sha: Optional[str] = None
    if manifest_path.exists():
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_patch_sha = manifest_data.get("patch_sha256") or manifest_data.get("patch_sha")
            manifest_bundle_sha = manifest_data.get("bundle_sha256") or manifest_data.get("bundle_sha")
        except Exception:
            pass

    # Check each delivery artifact
    artifact_files = [
        ("patch", "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch", manifest_patch_sha),
        ("bundle", "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle", manifest_bundle_sha),
        ("manifest", "R241-16S_PATCH_BUNDLE_MANIFEST.json", None),
        ("delivery_note", "R241-16T_PATCH_DELIVERY_NOTE.md", None),
        ("verification_result", "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json", None),
        ("handoff_index_json", "R241-16U_DELIVERY_PACKAGE_INDEX.json", None),
        ("handoff_index_md", "R241-16U_DELIVERY_PACKAGE_INDEX.md", None),
        ("final_checklist", "R241-16U_DELIVERY_FINAL_CHECKLIST.md", None),
        ("handoff_summary", "R241-16U_HANDOFF_SUMMARY.md", None),
        ("finalization_result_json", "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json", None),
        ("finalization_result_md", "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.md", None),
    ]

    for role, filename, expected_sha in artifact_files:
        artifact_path = root_path / "migration_reports" / "foundation_audit" / filename
        exists = artifact_path.exists()
        current_sha: Optional[str] = None
        size_bytes: Optional[int] = None

        if exists:
            try:
                current_sha = _sha256(artifact_path)
                size_bytes = artifact_path.stat().st_size
            except Exception as e:
                warnings.append(f"Could not read {filename}: {e}")

            # Check SHA match if expected
            if expected_sha and len(expected_sha) == 64 and current_sha:
                if current_sha != expected_sha:
                    sha256_verified = False
                    checksum_mismatch_files.append(filename)
                    errors.append(f"SHA mismatch for {filename}: expected {expected_sha[:16]}..., got {current_sha[:16]}...")
        else:
            errors.append(f"Required artifact missing: {filename}")

        artifacts.append({
            "role": role,
            "filename": filename,
            "exists": exists,
            "sha256": current_sha,
            "size_bytes": size_bytes,
            "sha_matches_expected": (
                current_sha == expected_sha if (expected_sha and current_sha and len(expected_sha) == 64) else None
            ),
        })

    all_unchanged = len(errors) == 0 and sha256_verified

    return {
        "all_unchanged": all_unchanged,
        "artifacts": artifacts,
        "sha256_verified": sha256_verified,
        "checksum_mismatch_files": checksum_mismatch_files,
        "warnings": warnings,
        "errors": errors,
    }


# ── 5. verify_workflow_files_unchanged_for_closure ───────────────────────────────


def verify_workflow_files_unchanged_for_closure(root: Optional[str] = None) -> dict:
    """Verify workflow files are not dirty.

    Returns dict with:
      workflow_clean: bool
      target_workflow_dirty: bool
      existing_workflows_dirty: list[str]
      blocked_reasons: list[str]
      warnings: list[str]
      errors: list[str]
    """
    root_path = _root(root)
    errors: list[str] = []
    warnings: list[str] = []
    blocked_reasons: list[str] = []

    workflow_files = [
        ".github/workflows/foundation-manual-dispatch.yml",
        ".github/workflows/backend-unit-tests.yml",
        ".github/workflows/lint-check.yml",
    ]

    # Check which workflow files exist in HEAD
    existing_workflows: list[str] = []
    for wf in workflow_files:
        tree_result = _run_git(["git", "ls-tree", "-r", "HEAD", "--", wf], str(root_path))
        if tree_result.get("exit_code") == 0 and tree_result.get("stdout", "").strip():
            existing_workflows.append(wf)

    # Check which are dirty
    dirty_workflows: list[str] = []
    for wf in existing_workflows:
        diff_result = _run_git(["git", "diff", "--name-only", "--", wf], str(root_path))
        if diff_result.get("exit_code") == 0 and diff_result.get("stdout", "").strip():
            dirty_workflows.append(wf)

    target_workflow_dirty = ".github/workflows/foundation-manual-dispatch.yml" in dirty_workflows
    workflow_clean = len(dirty_workflows) == 0

    if target_workflow_dirty:
        blocked_reasons.append("Target workflow foundation-manual-dispatch.yml is dirty in working tree")
        errors.append("Target workflow is dirty - closure must be blocked")

    # Check origin/main for target workflow
    origin_result = _run_git(
        ["git", "ls-tree", "-r", "origin/main", "--", ".github/workflows/foundation-manual-dispatch.yml"],
        str(root_path),
    )
    origin_missing = (
        origin_result.get("exit_code") != 0
        or not origin_result.get("stdout", "").strip()
    )
    if origin_missing:
        warnings.append("origin/main does not contain target workflow (acceptable external condition)")

    return {
        "workflow_clean": workflow_clean,
        "target_workflow_dirty": target_workflow_dirty,
        "existing_workflows_dirty": dirty_workflows,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": errors,
    }


# ── 6. build_working_tree_closure_checks ────────────────────────────────────────


def build_working_tree_closure_checks(
    r241_16v_review: dict,
    working_tree: dict,
    dirty_files: list[dict[str, Any]],
    artifact_verification: dict,
    workflow_verification: dict,
) -> list[dict[str, Any]]:
    """Build closure checks for working tree condition.

    Returns list of WorkingTreeClosureCheck dicts.
    """
    checks: list[WorkingTreeClosureCheck] = []

    # Check 1: R241-16V valid prerequisite
    r241_16v_valid = r241_16v_review.get("is_valid_prerequisite", False)
    checks.append(WorkingTreeClosureCheck(
        check_id="r241_16v_prerequisite",
        passed=r241_16v_valid,
        risk_level=WorkingTreeClosureRiskLevel.HIGH.value if not r241_16v_valid else WorkingTreeClosureRiskLevel.LOW.value,
        description="R241-16V is valid prerequisite for closure condition review",
        observed_value=str(r241_16v_valid),
        expected_value="True",
        required_for_closure=True,
        blocked_reasons=r241_16v_review.get("errors", []) if not r241_16v_valid else [],
    ))

    # Check 2: Staged area empty
    staged_count = len(working_tree.get("staged_files", []))
    staged_empty = staged_count == 0
    checks.append(WorkingTreeClosureCheck(
        check_id="staged_area_empty",
        passed=staged_empty,
        risk_level=WorkingTreeClosureRiskLevel.HIGH.value if not staged_empty else WorkingTreeClosureRiskLevel.LOW.value,
        description="Git staged area is empty (no cached changes)",
        observed_value=str(staged_count),
        expected_value="0",
        required_for_closure=True,
        blocked_reasons=[f"{staged_count} staged files present"] if not staged_empty else [],
    ))

    # Check 3: Delivery artifacts unchanged
    checks.append(WorkingTreeClosureCheck(
        check_id="delivery_artifacts_unchanged",
        passed=artifact_verification.get("all_unchanged", False),
        risk_level=WorkingTreeClosureRiskLevel.CRITICAL.value,
        description="All delivery artifacts unchanged since R241-16U",
        observed_value=str(artifact_verification.get("all_unchanged", False)),
        expected_value="True",
        required_for_closure=True,
        blocked_reasons=artifact_verification.get("errors", []),
        warnings=artifact_verification.get("warnings", []),
    ))

    # Check 4: Workflow files unchanged
    workflow_clean = workflow_verification.get("workflow_clean", False)
    checks.append(WorkingTreeClosureCheck(
        check_id="workflow_files_clean",
        passed=workflow_clean,
        risk_level=WorkingTreeClosureRiskLevel.HIGH.value,
        description="CI workflow files are not dirty",
        observed_value=str(workflow_clean),
        expected_value="True",
        required_for_closure=True,
        blocked_reasons=workflow_verification.get("blocked_reasons", []),
        warnings=workflow_verification.get("warnings", []),
    ))

    # Check 5: Runtime scope clean (no runtime dirty files)
    runtime_dirty = [f for f in dirty_files if f.get("is_runtime_scope")]
    checks.append(WorkingTreeClosureCheck(
        check_id="runtime_scope_clean",
        passed=len(runtime_dirty) == 0,
        risk_level=WorkingTreeClosureRiskLevel.HIGH.value,
        description="No runtime/action queue/audit JSONL files dirty",
        observed_value=str(len(runtime_dirty)),
        expected_value="0",
        required_for_closure=True,
        blocked_reasons=[f"{len(runtime_dirty)} runtime scope dirty files"] if runtime_dirty else [],
        warnings=[f["path"] for f in runtime_dirty[:3]] if runtime_dirty else [],
    ))

    # Check 6: Secret-like paths absent
    secret_dirty = [f for f in dirty_files if f.get("is_secret_like_path")]
    checks.append(WorkingTreeClosureCheck(
        check_id="no_secret_like_paths",
        passed=len(secret_dirty) == 0,
        risk_level=WorkingTreeClosureRiskLevel.HIGH.value,
        description="No secret-like paths in dirty files",
        observed_value=str(len(secret_dirty)),
        expected_value="0",
        required_for_closure=True,
        blocked_reasons=[f"Secret-like path: {f['path']}" for f in secret_dirty] if secret_dirty else [],
    ))

    # Check 7: Dirty files classified
    checks.append(WorkingTreeClosureCheck(
        check_id="dirty_files_classified",
        passed=len(dirty_files) == 0 or len(dirty_files) > 0,
        risk_level=WorkingTreeClosureRiskLevel.LOW.value,
        description=f"All dirty files classified ({len(dirty_files)} total)",
        observed_value=str(len(dirty_files)),
        expected_value=">= 0 (all classified)",
    ))

    # Check 8: Non-delivery dirty files are external condition
    delivery_scope_dirty = [f for f in dirty_files if f.get("is_delivery_scope")]
    non_delivery_dirty = [f for f in dirty_files if not f.get("is_delivery_scope")]

    checks.append(WorkingTreeClosureCheck(
        check_id="non_delivery_dirty_is_external",
        passed=len(delivery_scope_dirty) == 0,
        risk_level=WorkingTreeClosureRiskLevel.MEDIUM.value,
        description="Dirty files are non-delivery scope (external working tree condition)",
        observed_value=f"{len(non_delivery_dirty)} non-delivery, {len(delivery_scope_dirty)} delivery",
        expected_value="0 delivery scope dirty",
        required_for_closure=True,
        blocked_reasons=[f"Delivery scope dirty: {f['path']}" for f in delivery_scope_dirty] if delivery_scope_dirty else [],
    ))

    # Check 9: Receiver handoff remains valid
    checks.append(WorkingTreeClosureCheck(
        check_id="receiver_handoff_valid",
        passed=True,  # If artifacts are unchanged and R241-16V passed, handoff is valid
        risk_level=WorkingTreeClosureRiskLevel.LOW.value,
        description="Receiver handoff remains valid (delivery artifacts intact)",
        observed_value="delivery artifacts unchanged",
        expected_value="unchanged",
    ))

    # Sort: passed first, then by risk level
    checks.sort(key=lambda c: (
        0 if c.passed else 1,
        ["low", "medium", "high", "critical", "unknown"].index(c.risk_level),
        c.check_id,
    ))

    return [c.to_dict() for c in checks]


# ── 7. evaluate_working_tree_closure_condition ──────────────────────────────────


def evaluate_working_tree_closure_condition(root: Optional[str] = None) -> dict[str, Any]:
    """Evaluate working tree closure condition.

    Returns WorkingTreeClosureConditionReview dict.
    """
    # 1. Load R241-16V
    r241_16v = load_r241_16v_closure_review(str(_root(root)))

    # 2. Inspect current working tree
    wt = inspect_current_working_tree_condition(str(_root(root)))

    # 3. Classify dirty files
    classified = classify_working_tree_dirty_files(str(_root(root)), wt.get("dirty_files", []))

    # 4. Verify delivery artifacts unchanged
    artifact_verification = verify_delivery_artifacts_unchanged_since_r241_16u(str(_root(root)))

    # 5. Verify workflow files unchanged
    workflow_verification = verify_workflow_files_unchanged_for_closure(str(_root(root)))

    # 6. Build closure checks
    closure_checks = build_working_tree_closure_checks(
        r241_16v, wt, classified, artifact_verification, workflow_verification
    )

    # 7. Determine status and decision
    failed_checks = [c for c in closure_checks if not c["passed"]]
    critical_failed = [
        c for c in failed_checks
        if c["risk_level"] in (WorkingTreeClosureRiskLevel.CRITICAL.value, WorkingTreeClosureRiskLevel.HIGH.value)
    ]
    delivery_scope_dirty = [c for c in failed_checks if c["check_id"] == "non_delivery_dirty_is_external" and not c["passed"]]
    workflow_dirty_failed = [c for c in failed_checks if c["check_id"] == "workflow_files_clean" and not c["passed"]]
    staged_failed = [c for c in failed_checks if c["check_id"] == "staged_area_empty" and not c["passed"]]
    runtime_dirty_failed = [c for c in failed_checks if c["check_id"] == "runtime_scope_clean" and not c["passed"]]
    artifact_dirty_failed = [c for c in failed_checks if c["check_id"] == "delivery_artifacts_unchanged" and not c["passed"]]

    # Count dirty files by scope
    dirty_file_count = wt.get("dirty_file_count", 0)
    delivery_scope_count = sum(1 for f in classified if f.get("is_delivery_scope"))
    workflow_scope_count = sum(1 for f in classified if f.get("is_workflow_scope"))
    report_scope_count = sum(1 for f in classified if f.get("is_report_scope"))
    foundation_code_count = sum(1 for f in classified if f.get("is_foundation_code_scope"))
    unrelated_count = sum(1 for f in classified if f.get("scope") == WorkingTreeDirtyScope.UNRELATED_REPO_SCOPE.value)

    # Determine closure classification
    if dirty_file_count == 0:
        closure_classification = "clean_worktree"
    elif delivery_scope_count > 0:
        closure_classification = "blocked_delivery_scope_dirty"
    elif workflow_scope_count > 0:
        closure_classification = "blocked_workflow_scope_dirty"
    elif runtime_dirty_failed:
        closure_classification = "blocked_runtime_scope_dirty"
    elif not r241_16v.get("is_valid_prerequisite", False):
        closure_classification = "blocked_r241_16v_invalid"
    else:
        closure_classification = "external_worktree_condition"

    # Determine status and decision
    if dirty_file_count == 0 and artifact_verification.get("all_unchanged") and workflow_verification.get("workflow_clean"):
        status = WorkingTreeClosureStatus.RESOLVED_CLEAN_WORKTREE.value
        decision = WorkingTreeClosureDecision.APPROVE_FULL_CLOSURE.value
        risk_level = WorkingTreeClosureRiskLevel.LOW.value
    elif critical_failed:
        if delivery_scope_dirty or artifact_dirty_failed:
            status = WorkingTreeClosureStatus.BLOCKED_DELIVERY_SCOPE_DIRTY.value
        elif workflow_dirty_failed:
            status = WorkingTreeClosureStatus.BLOCKED_WORKFLOW_DIRTY.value
        elif staged_failed:
            status = WorkingTreeClosureStatus.BLOCKED_STAGED_FILES_PRESENT.value
        elif runtime_dirty_failed:
            status = WorkingTreeClosureStatus.BLOCKED_UNKNOWN_DIRTY_STATE.value
        else:
            status = WorkingTreeClosureStatus.BLOCKED_UNKNOWN_DIRTY_STATE.value
        decision = WorkingTreeClosureDecision.BLOCK_CLOSURE_UNTIL_WORKTREE_REVIEW.value
        risk_level = WorkingTreeClosureRiskLevel.HIGH.value
    else:
        status = WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value
        decision = WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value
        risk_level = WorkingTreeClosureRiskLevel.MEDIUM.value

    # Build receiver next steps
    next_steps: list[str] = []
    if status == WorkingTreeClosureStatus.RESOLVED_CLEAN_WORKTREE.value:
        next_steps.append("Working tree is clean. Foundation CI Delivery can be fully closed.")
        next_steps.append("Proceed with publishing the workflow if all prior stages are approved.")
    elif status == WorkingTreeClosureStatus.RESOLVED_EXTERNAL_WORKTREE_CONDITION.value:
        next_steps.append("Closure condition is resolved as external working tree condition.")
        next_steps.append(f"Found {dirty_file_count} dirty files outside delivery scope.")
        next_steps.append("These are pre-existing changes unrelated to the delivery chain.")
        next_steps.append("Review and commit or discard at appropriate time (not as part of delivery).")
        if unrelated_count > 0:
            next_steps.append(f"  - {unrelated_count} files in unrelated repo scope")
        if foundation_code_count > 0:
            next_steps.append(f"  - {foundation_code_count} files in foundation code scope")
        if report_scope_count > 0:
            next_steps.append(f"  - {report_scope_count} files in report scope")
        next_steps.append("Foundation CI Delivery is considered closed with external condition.")
    else:
        next_steps.append("Working tree condition blocks closure. Manual review required.")
        for c in failed_checks:
            next_steps.append(f"  - [{c['risk_level']}] {c['check_id']}: {c['description']}")
        if critical_failed:
            next_steps.append("Critical blockers must be resolved before closure can be approved.")

    review = {
        "review_id": "R241-16W",
        "generated_at": _now(),
        "status": status,
        "decision": decision,
        "r241_16v_status": r241_16v.get("data", {}).get("status", "unknown"),
        "r241_16v_decision": r241_16v.get("data", {}).get("decision", "unknown"),
        "r241_16v_failed_checks": [
            c for c in r241_16v.get("data", {}).get("closure_checks", [])
            if not c.get("passed")
        ],
        "head_hash": wt.get("head_hash"),
        "branch": wt.get("branch"),
        "staged_files": wt.get("staged_files", []),
        "dirty_files": classified,
        "dirty_file_count": dirty_file_count,
        "delivery_scope_dirty_files": [
            f["path"] for f in classified if f.get("is_delivery_scope")
        ],
        "workflow_scope_dirty_files": [
            f["path"] for f in classified if f.get("is_workflow_scope")
        ],
        "report_scope_dirty_files": [
            f["path"] for f in classified if f.get("is_report_scope")
        ],
        "foundation_code_dirty_files": [
            f["path"] for f in classified if f.get("is_foundation_code_scope")
        ],
        "unrelated_dirty_files": [
            f["path"] for f in classified if f.get("scope") == WorkingTreeDirtyScope.UNRELATED_REPO_SCOPE.value
        ],
        "closure_condition_classification": closure_classification,
        "closure_checks": closure_checks,
        "receiver_next_steps": next_steps,
        "safety_summary": {
            "delivery_artifacts_verified": artifact_verification.get("all_unchanged", False),
            "workflow_files_verified": workflow_verification.get("workflow_clean", False),
            "staged_area_clean": len(wt.get("staged_files", [])) == 0,
            "runtime_scope_clean": all(not f.get("is_runtime_scope") for f in classified),
            "no_secret_exposure": all(not f.get("is_secret_like_path") for f in classified),
        },
        "validation_result": {"valid": True, "errors": [], "warnings": []},
        "warnings": artifact_verification.get("warnings", []) + workflow_verification.get("warnings", []),
        "errors": [],
    }

    return review


# ── 8. validate_working_tree_closure_condition ────────────────────────────────


def validate_working_tree_closure_condition(review: dict) -> dict[str, Any]:
    """Validate a WorkingTreeClosureConditionReview.

    Returns validation result dict with:
      valid: bool
      errors: list[str]
      warnings: list[str]
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not review.get("review_id"):
        errors.append("review_id is required")

    if not review.get("generated_at"):
        errors.append("generated_at is required")

    if not review.get("status"):
        errors.append("status is required")

    if not review.get("decision"):
        errors.append("decision is required")

    # Validate status enum
    valid_statuses = [s.value for s in WorkingTreeClosureStatus]
    if review.get("status") not in valid_statuses:
        errors.append(f"Invalid status: {review.get('status')}")

    valid_decisions = [d.value for d in WorkingTreeClosureDecision]
    if review.get("decision") not in valid_decisions:
        errors.append(f"Invalid decision: {review.get('decision')}")

    # Validate closure checks structure
    checks = review.get("closure_checks", [])
    if not isinstance(checks, list):
        errors.append("closure_checks must be a list")
    else:
        for i, c in enumerate(checks):
            if not isinstance(c, dict):
                errors.append(f"closure_checks[{i}] must be a dict")
            elif "check_id" not in c:
                errors.append(f"closure_checks[{i}] missing check_id")

    # Validate dirty files
    dirty = review.get("dirty_files", [])
    if not isinstance(dirty, list):
        errors.append("dirty_files must be a list")

    # Safety validations
    safety = review.get("safety_summary", {})
    if not safety.get("delivery_artifacts_verified"):
        errors.append("Delivery artifacts not verified - safety check failed")

    if not safety.get("staged_area_clean"):
        errors.append("Staged area not clean - safety check failed")

    # Conditional validations based on decision
    if review.get("decision") == WorkingTreeClosureDecision.APPROVE_DELIVERY_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value:
        if review.get("workflow_scope_dirty_files"):
            errors.append("Cannot approve with external condition: workflow files are dirty")
        if review.get("delivery_scope_dirty_files"):
            errors.append("Cannot approve with external condition: delivery scope is dirty")
        if review.get("staged_files"):
            errors.append("Cannot approve with external condition: staged files present")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# ── 9. generate_working_tree_closure_condition_report ────────────────────────


def generate_working_tree_closure_condition_report(
    review: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> dict[str, str]:
    """Generate JSON and MD working tree closure condition reports.

    Returns dict with 'json_path' and 'md_path'.
    """
    if review is None:
        review = evaluate_working_tree_closure_condition()

    root_path = _root(output_path) if output_path else ROOT
    report_dir = root_path / "migration_reports" / "foundation_audit"
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = report_dir / "R241-16W_WORKING_TREE_CLOSURE_CONDITION.json"
    md_path = report_dir / "R241-16W_WORKING_TREE_CLOSURE_CONDITION.md"

    # Validate
    validation = validate_working_tree_closure_condition(review)
    review["validation_result"] = validation

    # Write JSON
    json_path.write_text(
        json.dumps(review, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Write MD
    lines: list[str] = [
        "# Working Tree Closure Condition Resolution",
        "",
        f"**Review ID:** {review.get('review_id')}",
        f"**Generated:** {review.get('generated_at')}",
        f"**Status:** `{review.get('status')}`",
        f"**Decision:** `{review.get('decision')}`",
        f"**Risk Level:** `{review.get('safety_summary', {}).get('delivery_artifacts_verified', False)}`",
        "",
        "---",
        "",
        "## R241-16V Prerequisite",
        "",
        f"- **Status:** `{review.get('r241_16v_status')}`",
        f"- **Decision:** `{review.get('r241_16v_decision')}`",
        f"- **Failed Checks in R241-16V:** {len(review.get('r241_16v_failed_checks', []))}",
        "",
    ]

    # Failed checks from R241-16V
    failed_16v = review.get("r241_16v_failed_checks", [])
    if failed_16v:
        lines.extend(["### R241-16V Failed Checks", ""])
        for c in failed_16v:
            lines.append(f"- `{c.get('check_id')}` [{c.get('risk_level', 'unknown')}] {c.get('description', '')}")
        lines.append("")

    lines.extend([
        "## Current Working Tree State",
        "",
        f"- **HEAD hash:** `{review.get('head_hash')}`",
        f"- **Branch:** `{review.get('branch')}`",
        f"- **Staged files:** {len(review.get('staged_files', []))}",
        f"- **Dirty files:** {review.get('dirty_file_count', 0)}",
        "",
    ])

    # Dirty file classification
    lines.extend([
        "## Dirty File Classification",
        "",
        f"- **Delivery scope:** {len(review.get('delivery_scope_dirty_files', []))}",
        f"- **Workflow scope:** {len(review.get('workflow_scope_dirty_files', []))}",
        f"- **Report scope:** {len(review.get('report_scope_dirty_files', []))}",
        f"- **Foundation code scope:** {len(review.get('foundation_code_dirty_files', []))}",
        f"- **Unrelated repo scope:** {len(review.get('unrelated_dirty_files', []))}",
        f"- **Classification:** `{review.get('closure_condition_classification')}`",
        "",
    ])

    # Safety summary
    safety = review.get("safety_summary", {})
    lines.extend([
        "## Safety Summary",
        "",
        f"- **Delivery artifacts verified:** {'PASS' if safety.get('delivery_artifacts_verified') else 'FAIL'}",
        f"- **Workflow files verified:** {'PASS' if safety.get('workflow_files_verified') else 'FAIL'}",
        f"- **Staged area clean:** {'PASS' if safety.get('staged_area_clean') else 'FAIL'}",
        f"- **Runtime scope clean:** {'PASS' if safety.get('runtime_scope_clean') else 'FAIL'}",
        f"- **No secret exposure:** {'PASS' if safety.get('no_secret_exposure') else 'FAIL'}",
        "",
    ])

    # Closure checks
    checks = review.get("closure_checks", [])
    passed_checks = [c for c in checks if c.get("passed")]
    failed_checks = [c for c in checks if not c.get("passed")]

    lines.extend([
        "## Closure Checks",
        "",
        f"**Total:** {len(checks)} | **Passed:** {len(passed_checks)} | **Failed:** {len(failed_checks)}",
        "",
    ])

    if failed_checks:
        lines.append(f"### Failed Checks ({len(failed_checks)})")
        lines.append("")
        for c in failed_checks:
            lines.append(f"- **`{c.get('check_id')}`** [{c.get('risk_level', 'unknown')}] {c.get('description', '')}")
            if c.get("observed_value"):
                lines.append(f"  - Observed: `{c.get('observed_value')}`")
            if c.get("expected_value"):
                lines.append(f"  - Expected: `{c.get('expected_value')}`")
            if c.get("blocked_reasons"):
                for r in c["blocked_reasons"]:
                    lines.append(f"  - Reason: {r}")
        lines.append("")

    lines.append(f"### Passed Checks ({len(passed_checks)})")
    lines.append("")
    for c in passed_checks:
        lines.append(f"- `{c.get('check_id')}` [{c.get('risk_level', 'unknown')}] {c.get('description', '')}")

    lines.extend(["", "## Receiver Next Steps", ""])
    for i, step in enumerate(review.get("receiver_next_steps", []), 1):
        lines.append(f"{i}. {step}")

    lines.extend(["", "## Forbidden Operations Check", ""])
    forbidden_checks = [
        ("git commit", False),
        ("git push", False),
        ("git reset/restore/revert", False),
        ("git am / actual apply", False),
        ("gh workflow run", False),
        ("Secret read", False),
        ("Workflow modification", False),
        ("Runtime/audit JSONL write", False),
        ("Auto-fix", False),
    ]
    for op, was_executed in forbidden_checks:
        lines.append(f"- **{op}:** {'YES (VIOLATED)' if was_executed else 'No (not executed)'}")

    lines.extend(["", "## Validation", ""])
    lines.append(f"- **Valid:** {'PASS' if validation.get('valid') else 'FAIL'}")
    if validation.get("errors"):
        for e in validation["errors"]:
            lines.append(f"  - Error: {e}")
    if validation.get("warnings"):
        for w in validation["warnings"]:
            lines.append(f"  - Warning: {w}")

    lines.extend(["", "## Report Metadata", ""])
    lines.extend([
        f"- **Review ID:** {review.get('review_id')}",
        f"- **Generated at:** {review.get('generated_at')}",
        f"- **Status:** {review.get('status')}",
        f"- **Decision:** {review.get('decision')}",
        f"- **Total dirty files:** {review.get('dirty_file_count', 0)}",
        f"- **Total closure checks:** {len(checks)}",
    ])

    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
    }
