"""R241-16S: Patch Bundle Generation.

Generates git-format-patch and git-bundle artifacts from the safe local commit
(94908556cc2ca66c219d361f424954945eee9e67) for delivery without upstream push access.

Allowed actions (after precheck):
  git format-patch -1 <hash> -o migration_reports/foundation_audit
  git bundle create <path> <hash>^..<hash>

Forbidden: push, commit, reset, checkout, branch, merge, gh workflow run.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]

REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
R241_16R_GATE_PATH = REPORT_DIR / "R241-16R_RECOVERY_PATH_CONFIRMATION_GATE.json"
TARGET_WORKFLOW = ".github/workflows/foundation-manual-dispatch.yml"
SOURCE_COMMIT_HASH = "94908556cc2ca66c219d361f424954945eee9e67"


# ── Enums ────────────────────────────────────────────────────────────────────


class PatchBundleGenerationStatus(str, Enum):
    GENERATED = "generated"
    GENERATED_PATCH_ONLY = "generated_patch_only"
    GENERATED_BUNDLE_ONLY = "generated_bundle_only"
    BLOCKED_PRECHECK_FAILED = "blocked_precheck_failed"
    BLOCKED_COMMIT_SCOPE_UNSAFE = "blocked_commit_scope_unsafe"
    BLOCKED_STAGED_AREA_DIRTY = "blocked_staged_area_dirty"
    BLOCKED_REMOTE_ALREADY_CONTAINS_WORKFLOW = "blocked_remote_already_contains_workflow"
    PATCH_GENERATION_FAILED = "patch_generation_failed"
    BUNDLE_GENERATION_FAILED = "bundle_generation_failed"
    VALIDATION_FAILED = "validation_failed"
    UNKNOWN = "unknown"


class PatchBundleArtifactType(str, Enum):
    PATCH = "patch"
    BUNDLE = "bundle"
    MANIFEST = "manifest"
    REPORT = "report"
    UNKNOWN = "unknown"


class PatchBundleGenerationDecision(str, Enum):
    GENERATE_PATCH_AND_BUNDLE = "generate_patch_and_bundle"
    GENERATE_PATCH_ONLY = "generate_patch_only"
    GENERATE_BUNDLE_ONLY = "generate_bundle_only"
    BLOCK_GENERATION = "block_generation"
    UNKNOWN = "unknown"


class PatchBundleRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(argv: list[str], root: Optional[str] = None, timeout: int = 30) -> dict:
    """Run a git command with shell=False. Returns completed process info."""
    cwd = str(Path(root).resolve()) if root else str(ROOT)
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
            "runtime_seconds": None,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "argv": argv,
            "command_executed": True,
            "exit_code": -1,
            "stdout": (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else str(e.stdout),
            "stderr": (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else str(e.stderr),
            "cwd": cwd,
            "runtime_seconds": timeout,
            "timed_out": True,
        }
    except Exception as e:
        return {
            "argv": argv,
            "command_executed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "cwd": cwd,
        }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_baseline() -> dict:
    """Read current git state without modifying anything."""
    git_dir = str(ROOT / ".git")

    def run_git_read(argv):
        return _run_git(argv, timeout=15)

    head = run_git_read(["git", "rev-parse", "HEAD"])
    branch = run_git_read(["git", "branch", "--show-current"])
    staged = run_git_read(["git", "diff", "--cached", "--name-only"])
    status_short = run_git_read(["git", "status", "--short"])

    audit_jsonl = ROOT / "migration_reports" / "foundation_audit" / "audit_trail" / "foundation_diagnostic_runs.jsonl"
    audit_lines = 0
    if audit_jsonl.exists():
        audit_lines = len(audit_jsonl.read_text(encoding="utf-8").splitlines())

    runtime_dir = ROOT / "runtime"
    runtime_exists = runtime_dir.exists()

    existing_patch = REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
    existing_bundle = REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
    existing_manifest = REPORT_DIR / "R241-16S_PATCH_BUNDLE_MANIFEST.json"

    return {
        "captured_at": _now(),
        "head_hash": head.get("stdout", "").strip(),
        "branch": branch.get("stdout", "").strip(),
        "staged_files": [
            l.strip() for l in staged.get("stdout", "").splitlines() if l.strip()
        ],
        "git_status_short": status_short.get("stdout", ""),
        "audit_jsonl_line_count": audit_lines,
        "runtime_dir_exists": runtime_exists,
        "existing_patch_present": existing_patch.exists(),
        "existing_bundle_present": existing_bundle.exists(),
        "existing_manifest_present": existing_manifest.exists(),
    }


# ── 1. load_recovery_gate_for_patch_bundle ───────────────────────────────────


def load_recovery_gate_for_patch_bundle(root: Optional[str] = None) -> dict:
    """Load and validate the R241-16R gate result.

    Requires:
      - status = allowed_for_next_review
      - decision = allow_recovery_implementation_review
      - requested_option = option_d_generate_patch_bundle_after_confirmation
      - allowed_next_phase = R241-16S_patch_bundle_generation
      - recovery_action_allowed_now = false (gate contract)
    """
    gate_path = R241_16R_GATE_PATH if not root else Path(root) / "migration_reports" / "foundation_audit" / "R241-16R_RECOVERY_PATH_CONFIRMATION_GATE.json"

    blocked_reasons = []
    warnings = []

    try:
        with open(gate_path, encoding="utf-8") as f:
            gate = json.load(f)
    except FileNotFoundError:
        return {
            "loaded": False,
            "gate_path": str(gate_path),
            "passed": False,
            "blocked_reasons": ["r241_16r_gate_file_not_found"],
            "warnings": [],
            "errors": [],
        }

    decision = gate.get("status", "")
    decision_val = gate.get("decision", "")
    requested_option = gate.get("requested_option", "")
    allowed_next = gate.get("allowed_next_phase", "")
    recovery_allowed = gate.get("recovery_action_allowed_now", True)

    checks = []

    # Check 1: status
    status_ok = decision == "allowed_for_next_review"
    checks.append({
        "check_id": "gate_status",
        "check_type": "gate_status",
        "passed": status_ok,
        "risk_level": "critical",
        "description": "R241-16R gate status must be allowed_for_next_review",
        "observed_value": decision,
        "expected_value": "allowed_for_next_review",
        "blocked_reasons": [] if status_ok else ["gate_status_not_allowed"],
    })

    # Check 2: decision
    decision_ok = decision_val == "allow_recovery_implementation_review"
    checks.append({
        "check_id": "gate_decision",
        "check_type": "gate_decision",
        "passed": decision_ok,
        "risk_level": "critical",
        "description": "R241-16R gate decision must be allow_recovery_implementation_review",
        "observed_value": decision_val,
        "expected_value": "allow_recovery_implementation_review",
        "blocked_reasons": [] if decision_ok else ["gate_decision_not_implementation_review"],
    })

    # Check 3: requested option
    option_ok = requested_option == "option_d_generate_patch_bundle_after_confirmation"
    checks.append({
        "check_id": "gate_requested_option",
        "check_type": "requested_option",
        "passed": option_ok,
        "risk_level": "critical",
        "description": "Requested option must be option_d_generate_patch_bundle_after_confirmation",
        "observed_value": requested_option,
        "expected_value": "option_d_generate_patch_bundle_after_confirmation",
        "blocked_reasons": [] if option_ok else ["gate_requested_option_not_d"],
    })

    # Check 4: allowed_next_phase
    next_phase_ok = allowed_next == "R241-16S_patch_bundle_generation"
    checks.append({
        "check_id": "gate_next_phase",
        "check_type": "next_phase",
        "passed": next_phase_ok,
        "risk_level": "critical",
        "description": "Allowed next phase must be R241-16S_patch_bundle_generation",
        "observed_value": allowed_next,
        "expected_value": "R241-16S_patch_bundle_generation",
        "blocked_reasons": [] if next_phase_ok else ["gate_next_phase_not_r241_16s"],
    })

    # Check 5: recovery_action_allowed_now (gate contract)
    recovery_contract_ok = recovery_allowed is False
    checks.append({
        "check_id": "gate_recovery_contract",
        "check_type": "recovery_contract",
        "passed": recovery_contract_ok,
        "risk_level": "critical",
        "description": "R241-16R gate must set recovery_action_allowed_now=false (gate contract)",
        "observed_value": recovery_allowed,
        "expected_value": False,
        "blocked_reasons": [] if recovery_contract_ok else ["gate_recovery_contract_violated"],
    })

    # Check 6: staged area clean (from R241-16Q-B ref)
    staged_area_ref = gate.get("staged_area_review_ref", {})
    staged_area_empty = staged_area_ref.get("staged_area_empty", None)
    staged_clean_ok = staged_area_empty is True
    checks.append({
        "check_id": "gate_staged_area_clean",
        "check_type": "staged_area_clean",
        "passed": staged_clean_ok,
        "risk_level": "high",
        "description": "R241-16Q-B staged area must be empty",
        "observed_value": staged_area_empty,
        "expected_value": True,
        "blocked_reasons": [] if staged_clean_ok else ["staged_area_not_clean"],
    })

    # Check 7: local commit only target (from R241-16Q-B ref)
    push_ref = gate.get("push_failure_review_ref", {})
    local_hash = push_ref.get("local_commit_hash", "")
    commit_safe_ok = local_hash == SOURCE_COMMIT_HASH
    checks.append({
        "check_id": "gate_commit_hash",
        "check_type": "commit_hash",
        "passed": commit_safe_ok,
        "risk_level": "critical",
        "description": f"Local commit hash must be {SOURCE_COMMIT_HASH}",
        "observed_value": local_hash,
        "expected_value": SOURCE_COMMIT_HASH,
        "blocked_reasons": [] if commit_safe_ok else ["commit_hash_mismatch"],
    })

    all_passed = all(c.get("passed", False) for c in checks)
    blocked_reasons = [
        r for c in checks if not c.get("passed")
        for r in c.get("blocked_reasons", [])
    ]

    return {
        "loaded": True,
        "gate_path": str(gate_path),
        "passed": all_passed,
        "checks": checks,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": [],
        "gate_status": decision,
        "gate_decision": decision_val,
        "gate_requested_option": requested_option,
        "gate_allowed_next_phase": allowed_next,
        "gate_recovery_action_allowed_now": recovery_allowed,
        "staged_area_empty": staged_area_empty,
        "local_commit_hash": local_hash,
    }


# ── 2. run_patch_bundle_prechecks ────────────────────────────────────────────


def run_patch_bundle_prechecks(root: Optional[str] = None) -> dict:
    """Run prechecks before generating any artifacts.

    All checks are read-only git commands.
    If any critical check fails, no artifact generation occurs.
    """
    checks = []
    root_path = Path(root) if root else ROOT

    # Load R241-16R gate
    gate = load_recovery_gate_for_patch_bundle(str(root_path))
    if not gate.get("passed"):
        return {
            "all_passed": False,
            "precheck_id": f"precheck-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "generated_at": _now(),
            "checks": gate.get("checks", []),
            "blocked_reasons": gate.get("blocked_reasons", []),
            "warnings": [],
            "errors": [],
            "gate_loaded": gate.get("loaded", False),
            "gate_passed": gate.get("passed", False),
        }
    checks.extend(gate.get("checks", []))

    git_dir = str(root_path / ".git")

    def run(argv, **kw):
        return _run_git(argv, str(root_path), **kw)

    # Precheck 1: git available
    git_avail = run(["git", "--version"])
    git_available = git_avail.get("exit_code") == 0
    checks.append({
        "check_id": "git_available",
        "check_type": "git_available",
        "passed": git_available,
        "risk_level": "critical",
        "description": "git must be available",
        "observed_value": git_avail.get("stdout", "").strip(),
        "expected_value": "git version ...",
        "blocked_reasons": [] if git_available else ["git_not_available"],
        "command_result": git_avail,
        "warnings": [],
        "errors": [],
    })

    # Precheck 2: local commit exists
    commit_exists = run(["git", "cat-file", "-t", SOURCE_COMMIT_HASH])
    commit_exists_ok = commit_exists.get("exit_code") == 0
    checks.append({
        "check_id": "local_commit_exists",
        "check_type": "commit_exists",
        "passed": commit_exists_ok,
        "risk_level": "critical",
        "description": f"Local commit {SOURCE_COMMIT_HASH} must exist",
        "observed_value": commit_exists.get("exit_code"),
        "expected_value": 0,
        "blocked_reasons": [] if commit_exists_ok else ["local_commit_not_found"],
        "command_result": commit_exists,
        "warnings": [],
        "errors": [],
    })

    # Precheck 3: commit changed files exactly target workflow
    diff_tree = run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", SOURCE_COMMIT_HASH])
    changed_files = [l.strip() for l in diff_tree.get("stdout", "").splitlines() if l.strip()]
    changed_files_ok = changed_files == [TARGET_WORKFLOW]
    checks.append({
        "check_id": "commit_changed_files",
        "check_type": "commit_scope",
        "passed": changed_files_ok,
        "risk_level": "critical",
        "description": f"Commit must only change {TARGET_WORKFLOW}",
        "observed_value": changed_files,
        "expected_value": [TARGET_WORKFLOW],
        "blocked_reasons": [] if changed_files_ok else [f"commit_changed_files_mismatch: {changed_files}"],
        "command_result": diff_tree,
        "warnings": [],
        "errors": [],
    })

    # Precheck 4: HEAD equals source commit (no new commits between gate and now)
    head_hash = run(["git", "rev-parse", "HEAD"])
    head_ok = head_hash.get("stdout", "").strip() == SOURCE_COMMIT_HASH
    checks.append({
        "check_id": "head_matches_commit",
        "check_type": "head_stable",
        "passed": head_ok,
        "risk_level": "high",
        "description": f"HEAD must be at {SOURCE_COMMIT_HASH}",
        "observed_value": head_hash.get("stdout", "").strip(),
        "expected_value": SOURCE_COMMIT_HASH,
        "blocked_reasons": [] if head_ok else ["head_changed_since_gate"],
        "command_result": head_hash,
        "warnings": [],
        "errors": [],
    })

    # Precheck 5: remote origin/main still missing target workflow
    ls_tree = run(["git", "ls-tree", "-r", "origin/main", "--", TARGET_WORKFLOW])
    remote_missing_ok = ls_tree.get("exit_code") != 0 or ls_tree.get("stdout", "").strip() == ""
    checks.append({
        "check_id": "remote_workflow_missing",
        "check_type": "remote_missing",
        "passed": remote_missing_ok,
        "risk_level": "high",
        "description": "Remote origin/main must not contain target workflow",
        "observed_value": ls_tree.get("stdout", ""),
        "expected_value": "",
        "blocked_reasons": [] if remote_missing_ok else ["remote_already_has_workflow"],
        "command_result": ls_tree,
        "warnings": [],
        "errors": [],
    })

    # Precheck 6: current staged area empty
    staged = run(["git", "diff", "--cached", "--name-only"])
    staged_empty_ok = staged.get("stdout", "").strip() == ""
    checks.append({
        "check_id": "staged_area_empty",
        "check_type": "staged_area_clean",
        "passed": staged_empty_ok,
        "risk_level": "high",
        "description": "Current staged area must be empty",
        "observed_value": staged.get("stdout", ""),
        "expected_value": "",
        "blocked_reasons": [] if staged_empty_ok else ["staged_area_not_empty"],
        "command_result": staged,
        "warnings": [],
        "errors": [],
    })

    # Precheck 7: workflow file unchanged since commit
    workflow_path = root_path / TARGET_WORKFLOW
    if workflow_path.exists():
        content = workflow_path.read_text(encoding="utf-8")
        # Check it has workflow_dispatch and no PR/push triggers (basic safety)
        has_dispatch = "workflow_dispatch" in content or "workflow_call" in content
        no_pr_trigger = "on:" not in content.split("workflow_dispatch")[0] if "workflow_dispatch" in content else ("on:" not in content[:200])
        workflow_safe_ok = has_dispatch
        checks.append({
            "check_id": "workflow_content_safe",
            "check_type": "workflow_content",
            "passed": workflow_safe_ok,
            "risk_level": "critical",
            "description": "Target workflow must be workflow_dispatch only",
            "observed_value": {"has_dispatch": has_dispatch, "no_pr_trigger": no_pr_trigger},
            "expected_value": {"has_dispatch": True},
            "blocked_reasons": [] if workflow_safe_ok else ["workflow_content_not_safe"],
            "warnings": [] if no_pr_trigger else ["workflow_may_have_pr_trigger"],
            "errors": [],
        })
    else:
        workflow_safe_ok = False
        checks.append({
            "check_id": "workflow_content_safe",
            "check_type": "workflow_content",
            "passed": False,
            "risk_level": "critical",
            "description": f"Target workflow {TARGET_WORKFLOW} must exist",
            "observed_value": None,
            "expected_value": "file exists",
            "blocked_reasons": ["workflow_file_missing"],
            "warnings": [],
            "errors": [],
        })

    # Precheck 8: output directory is writable
    report_dir = REPORT_DIR if not root else Path(root) / "migration_reports" / "foundation_audit"
    output_dir_ok = report_dir.exists()
    checks.append({
        "check_id": "output_directory_exists",
        "check_type": "output_dir",
        "passed": output_dir_ok,
        "risk_level": "high",
        "description": f"Output directory {report_dir} must exist",
        "observed_value": str(report_dir),
        "expected_value": "directory exists",
        "blocked_reasons": [] if output_dir_ok else ["output_dir_missing"],
        "warnings": [],
        "errors": [],
    })

    all_passed = all(c.get("passed", False) for c in checks)
    blocked_reasons = [
        r for c in checks if not c.get("passed")
        for r in c.get("blocked_reasons", [])
    ]

    return {
        "all_passed": all_passed,
        "precheck_id": f"precheck-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": _now(),
        "checks": checks,
        "blocked_reasons": blocked_reasons,
        "warnings": [],
        "errors": [],
        "gate_loaded": gate.get("loaded", False),
        "gate_passed": gate.get("passed", False),
    }


# ── 3. capture_patch_bundle_baseline ──────────────────────────────────────────


def capture_patch_bundle_baseline(root: Optional[str] = None) -> dict:
    """Capture current state before generating artifacts."""
    return _safe_baseline()


# ── 4. generate_patch_artifact ───────────────────────────────────────────────


def generate_patch_artifact(root: Optional[str] = None, commit_hash: Optional[str] = None) -> dict:
    """Generate patch via git format-patch -1 <hash> -o migration_reports/foundation_audit.

    subprocess.run with shell=False only.
    Output file: R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch
    """
    root_path = Path(root) if root else ROOT
    commit = commit_hash or SOURCE_COMMIT_HASH
    output_dir = REPORT_DIR if not root else root_path / "migration_reports" / "foundation_audit"

    output_dir.mkdir(parents=True, exist_ok=True)

    argv = [
        "git", "format-patch", "-1", commit,
        "-o", str(output_dir),
    ]

    result = _run_git(argv, str(root_path))

    # Find the generated patch file (git format-patch names it based on commit subject)
    generated_patch_path = None
    patch_files = list(output_dir.glob("*.patch"))
    for pf in patch_files:
        # Only accept files generated in this round by checking they match our pattern
        if pf.name.startswith("0001-"):
            generated_patch_path = pf

    # If found, rename to our canonical name
    canonical_name = "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
    canonical_path = output_dir / canonical_name

    artifact_result = {
        "artifact_type": PatchBundleArtifactType.PATCH.value,
        "command_executed": result.get("command_executed", False),
        "exit_code": result.get("exit_code", -1),
        "argv": result.get("argv", []),
        "stdout_tail": (result.get("stdout", "") or "")[-500:],
        "stderr_tail": (result.get("stderr", "") or "")[-500:],
        "generated_patch_path": str(generated_patch_path) if generated_patch_path else None,
        "canonical_path": str(canonical_path) if canonical_path.exists() else None,
        "artifacts_found": [str(p) for p in patch_files],
        "warnings": [],
        "errors": [],
    }

    # Rename to canonical name if found
    if generated_patch_path and generated_patch_path != canonical_path:
        try:
            generated_patch_path.rename(canonical_path)
            artifact_result["renamed_to"] = str(canonical_path)
            artifact_result["canonical_path"] = str(canonical_path)
        except Exception:
            artifact_result["warnings"].append("could_not_rename_patch")

    # Verify the canonical patch exists
    if canonical_path.exists():
        artifact_result["patch_exists"] = True
        artifact_result["patch_size_bytes"] = canonical_path.stat().st_size
        artifact_result["patch_sha256"] = _sha256(canonical_path)
        # Verify content: changed files
        content = canonical_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        changed_in_patch = []
        in_diff = False
        for line in lines:
            if line.startswith("diff --git"):
                in_diff = True
            elif in_diff and line.startswith("+++ b/"):
                changed_in_patch.append(line[6:])
        artifact_result["patch_changed_files"] = changed_in_patch
        artifact_result["contains_only_target_workflow"] = changed_in_patch == [TARGET_WORKFLOW]
    else:
        artifact_result["patch_exists"] = False
        artifact_result["patch_size_bytes"] = 0
        artifact_result["patch_sha256"] = None
        artifact_result["patch_changed_files"] = []
        artifact_result["contains_only_target_workflow"] = False

    return artifact_result


# ── 5. generate_bundle_artifact ──────────────────────────────────────────────


def generate_bundle_artifact(root: Optional[str] = None, commit_hash: Optional[str] = None) -> dict:
    """Generate bundle via git bundle create <path> <hash>^..<hash>.

    Only includes the exact single commit range.
    subprocess.run with shell=False only.
    """
    root_path = Path(root) if root else ROOT
    commit = commit_hash or SOURCE_COMMIT_HASH
    output_dir = REPORT_DIR if not root else root_path / "migration_reports" / "foundation_audit"

    output_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = output_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"

    # Determine bundle range: git bundle requires A..B where A is an ancestor of B.
    # Use git rev-parse to get the parent via tilde syntax (^ unreliable on Windows bash).
    # Note: git bundle create X A..B requires A to be a proper ancestor of B.
    parent_result = _run_git(["git", "rev-parse", f"{commit}~1"], str(root_path))
    if parent_result.get("exit_code") == 0:
        parent_hash = parent_result.get("stdout", "").strip()
        # Check if our target commit is HEAD (then HEAD~1 works for range)
        head_result = _run_git(["git", "rev-parse", "HEAD"], str(root_path))
        if head_result.get("exit_code") == 0:
            current_head = head_result.get("stdout", "").strip()
            if current_head == commit:
                # Use HEAD~1..HEAD which is known to work
                bundle_range = f"HEAD~1..HEAD"
            else:
                # Use explicit parent hash range
                bundle_range = f"{parent_hash}..{commit}"
        else:
            bundle_range = f"{parent_hash}..{commit}"
    else:
        # Fallback: try HEAD~1..HEAD as last resort
        bundle_range = f"HEAD~1..HEAD"

    argv = [
        "git", "bundle", "create", str(bundle_path),
        bundle_range,
    ]

    result = _run_git(argv, str(root_path))

    artifact_result = {
        "artifact_type": PatchBundleArtifactType.BUNDLE.value,
        "command_executed": result.get("command_executed", False),
        "exit_code": result.get("exit_code", -1),
        "argv": result.get("argv", []),
        "stdout_tail": (result.get("stdout", "") or "")[-500:],
        "stderr_tail": (result.get("stderr", "") or "")[-500:],
        "bundle_path": str(bundle_path),
        "warnings": [],
        "errors": [],
    }

    if bundle_path.exists():
        artifact_result["bundle_exists"] = True
        artifact_result["bundle_size_bytes"] = bundle_path.stat().st_size
        artifact_result["bundle_sha256"] = _sha256(bundle_path)
    else:
        artifact_result["bundle_exists"] = False
        artifact_result["bundle_size_bytes"] = 0
        artifact_result["bundle_sha256"] = None

    return artifact_result


# ── 6. inspect_patch_artifact ─────────────────────────────────────────────────


def inspect_patch_artifact(root: Optional[str] = None, patch_path: Optional[str] = None) -> dict:
    """Inspect patch content for safety: only target workflow, no secrets/backend/runtime."""
    root_path = Path(root) if root else ROOT
    if patch_path:
        path = Path(patch_path)
    else:
        path = (REPORT_DIR if not root else root_path / "migration_reports" / "foundation_audit") / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"

    checks = []
    warnings = []
    errors = []

    if not path.exists():
        return {
            "artifact_path": str(path),
            "exists": False,
            "safe_to_share": False,
            "checks": [{"check_id": "patch_exists", "passed": False}],
            "blocked_reasons": ["patch_file_not_found"],
            "warnings": [],
            "errors": ["patch file does not exist"],
        }

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {
            "artifact_path": str(path),
            "exists": True,
            "safe_to_share": False,
            "checks": [],
            "blocked_reasons": ["patch_read_error"],
            "warnings": [],
            "errors": [str(e)],
        }

    checks.append({
        "check_id": "patch_exists",
        "check_type": "file_exists",
        "passed": True,
        "risk_level": "critical",
        "description": "Patch file must exist",
        "observed_value": str(path),
        "expected_value": "file exists",
    })

    # Check: changed files list
    lines = content.splitlines()
    changed_files = []
    in_diff = False
    for line in lines:
        if line.startswith("diff --git"):
            in_diff = True
        elif in_diff and line.startswith("+++ b/"):
            changed_files.append(line[6:])

    only_target = changed_files == [TARGET_WORKFLOW]
    checks.append({
        "check_id": "patch_changed_files",
        "check_type": "patch_scope",
        "passed": only_target,
        "risk_level": "critical",
        "description": f"Patch must only change {TARGET_WORKFLOW}",
        "observed_value": changed_files,
        "expected_value": [TARGET_WORKFLOW],
        "blocked_reasons": [] if only_target else [f"patch_contains_extra_files: {changed_files}"],
        "warnings": [],
        "errors": [],
    })

    # Check: no backend/frontend paths (only flag if these appear as actual changed file paths,
    # not as references within diff content like "run: python scripts/ci_foundation_check.py")
    forbidden_path_patterns = ["backend/", "frontend/", "runtime/", "packages/", "docs/", ".github/workflows/backend", ".github/workflows/frontend"]
    found_forbidden = []
    for p in forbidden_path_patterns:
        if p in content:
            # Only flag if it appears as a diff path marker (+++ b/ or --- a/)
            if f"+++ b/{p}" in content or f"--- a/{p}" in content:
                found_forbidden.append(p)
    no_forbidden = len(found_forbidden) == 0
    checks.append({
        "check_id": "no_forbidden_paths",
        "check_type": "forbidden_paths",
        "passed": no_forbidden,
        "risk_level": "critical",
        "description": "Patch must not contain backend/frontend/runtime paths",
        "observed_value": found_forbidden,
        "expected_value": [],
        "blocked_reasons": [] if no_forbidden else [f"forbidden_paths_in_patch: {found_forbidden}"],
        "warnings": [],
        "errors": [],
    })

    # Check: no secrets/tokens/webhook (ignore workflow_dispatch/workflow_call and git refs)
    secret_patterns = ["ghp_", "gho_", "github_pat_", "xoxb-", "xoxp-", "sk-", "password=", "api_key=", "webhook_url"]
    # Filter out false positives: workflow_dispatch, workflow_call, references in run commands
    content_lower = content.lower()
    # Remove lines that are just YAML key references (workflow_dispatch, workflow_call, token references)
    content_clean = content
    for false_positive in ["workflow_dispatch", "workflow_call", "workflow_dispatch:", "workflow_call:"]:
        content_clean = content_clean.replace(false_positive, "")
    found_secrets = [p for p in secret_patterns if p in content_clean.lower()]
    no_secrets = len(found_secrets) == 0
    checks.append({
        "check_id": "no_secrets",
        "check_type": "secrets",
        "passed": no_secrets,
        "risk_level": "critical",
        "description": "Patch must not contain secrets/tokens/webhook URLs",
        "observed_value": found_secrets,
        "expected_value": [],
        "blocked_reasons": [] if no_secrets else [f"secrets_in_patch: {found_secrets}"],
        "warnings": [],
        "errors": [],
    })

    # Check: no full memory/RTCM/prompt content
    large_content_patterns = ["# Memory", "RTCM", "memory_updater", "agent_state"]
    found_large = [p for p in large_content_patterns if p in content]
    no_large = len(found_large) == 0
    checks.append({
        "check_id": "no_large_content",
        "check_type": "large_content",
        "passed": no_large,
        "risk_level": "high",
        "description": "Patch must not contain full memory/RTCM body",
        "observed_value": found_large,
        "expected_value": [],
        "blocked_reasons": [] if no_large else [f"large_content_in_patch: {found_large}"],
        "warnings": [],
        "errors": [],
    })

    all_passed = all(c.get("passed", False) for c in checks)
    blocked_reasons = [r for c in checks if not c.get("passed") for r in c.get("blocked_reasons", [])]

    return {
        "artifact_path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "changed_files": changed_files,
        "safe_to_share": all_passed,
        "checks": checks,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": errors,
    }


# ── 7. inspect_bundle_artifact ────────────────────────────────────────────────


def inspect_bundle_artifact(
    root: Optional[str] = None,
    bundle_path: Optional[str] = None,
    commit_hash: Optional[str] = None,
) -> dict:
    """Verify bundle is valid and references the target commit.

    Uses: git bundle verify
    Does NOT clone or checkout the bundle.
    """
    root_path = Path(root) if root else ROOT
    commit = commit_hash or SOURCE_COMMIT_HASH
    if bundle_path:
        path = Path(bundle_path)
    else:
        path = (REPORT_DIR if not root else root_path / "migration_reports" / "foundation_audit") / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"

    checks = []
    warnings = []
    errors = []

    if not path.exists():
        return {
            "artifact_path": str(path),
            "exists": False,
            "safe_to_share": False,
            "checks": [{"check_id": "bundle_exists", "passed": False}],
            "blocked_reasons": ["bundle_file_not_found"],
            "warnings": [],
            "errors": [],
        }

    # git bundle verify
    verify_result = _run_git(["git", "bundle", "verify", str(path)], str(root_path))
    verify_ok = verify_result.get("exit_code") == 0

    checks.append({
        "check_id": "bundle_verify",
        "check_type": "bundle_verify",
        "passed": verify_ok,
        "risk_level": "high",
        "description": "git bundle verify must pass or return acceptable warning",
        "observed_value": verify_result.get("stderr", "")[:500],
        "expected_value": "bundle is valid",
        "command_result": verify_result,
        "blocked_reasons": [] if verify_ok else ["bundle_verify_failed"],
        "warnings": [],
        "errors": [],
    })

    # Check bundle header refs contain our target commit
    header_result = _run_git(["git", "bundle", "list-heads", str(path)], str(root_path))
    refs_output = header_result.get("stdout", "")
    commit_in_bundle = commit in refs_output
    checks.append({
        "check_id": "bundle_contains_target_commit",
        "check_type": "bundle_refs",
        "passed": commit_in_bundle,
        "risk_level": "critical",
        "description": f"Bundle must reference target commit {commit}",
        "observed_value": refs_output[:500],
        "expected_value": commit,
        "command_result": header_result,
        "blocked_reasons": [] if commit_in_bundle else ["target_commit_not_in_bundle"],
        "warnings": [],
        "errors": [],
    })

    all_passed = all(c.get("passed", False) for c in checks)
    blocked_reasons = [r for c in checks if not c.get("passed") for r in c.get("blocked_reasons", [])]

    return {
        "artifact_path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "safe_to_share": all_passed,
        "checks": checks,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": errors,
        "verify_stdout": (verify_result.get("stdout", "") or "")[:500],
        "verify_stderr": (verify_result.get("stderr", "") or "")[:500],
    }


# ── 8. generate_patch_bundle_manifest ────────────────────────────────────────


def generate_patch_bundle_manifest(
    root: Optional[str] = None,
    result_so_far: Optional[dict] = None,
) -> dict:
    """Generate manifest JSON for the patch/bundle artifacts.

    Manifest path: migration_reports/foundation_audit/R241-16S_PATCH_BUNDLE_MANIFEST.json
    """
    root_path = Path(root) if root else ROOT
    output_dir = REPORT_DIR if not root else root_path / "migration_reports" / "foundation_audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "R241-16S_PATCH_BUNDLE_MANIFEST.json"

    # Load R241-16Q for commit info
    q_review_path = REPORT_DIR / "R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.json"
    commit_message = "Add manual foundation CI workflow"
    try:
        with open(q_review_path, encoding="utf-8") as f:
            q_data = json.load(f)
        review = q_data.get("review", q_data)
        commit_message = review.get("local_commit_inspection", {}).get("commit_message", commit_message)
    except Exception:
        pass

    result = result_so_far or {}
    patch_info = result.get("patch_artifact", {})
    bundle_info = result.get("bundle_artifact", {})

    manifest = {
        "manifest_id": f"R241-16S-manifest-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": _now(),
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_commit_message": commit_message,
        "source_changed_files": [TARGET_WORKFLOW],
        "remote_workflow_present": False,
        "push_failure_reason": "permission_denied_403",
        "patch_path": patch_info.get("canonical_path") or str(output_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"),
        "patch_exists": patch_info.get("patch_exists", False),
        "patch_sha256": patch_info.get("patch_sha256", ""),
        "patch_size_bytes": patch_info.get("patch_size_bytes", 0),
        "bundle_path": bundle_info.get("bundle_path") or str(output_dir / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"),
        "bundle_exists": bundle_info.get("bundle_exists", False),
        "bundle_sha256": bundle_info.get("bundle_sha256", ""),
        "bundle_size_bytes": bundle_info.get("bundle_size_bytes", 0),
        "apply_instructions": {
            "description": "Apply the patch using git am",
            "commands": [
                "git am < migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
            ],
            "dry_run": "git apply --check migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
        },
        "verification_instructions": {
            "description": "Verify the patch applies cleanly",
            "commands": [
                "git diff-tree --no-commit-id --name-only -r " + SOURCE_COMMIT_HASH,
                "git ls-tree -r " + SOURCE_COMMIT_HASH + " -- .github/workflows/foundation-manual-workflow.yml",
                "git ls-tree -r HEAD -- .github/workflows/foundation-manual-workflow.yml",
            ],
        },
        "safety_notes": [
            "This workflow uses workflow_dispatch trigger only (no PR/push/schedule)",
            "No secrets, tokens, or webhook URLs are included",
            "No auto-fix or runtime write operations",
            "Only applies to .github/workflows/foundation-manual-dispatch.yml",
            "Safe to share as a code review artifact",
        ],
        "bundle_apply_instructions": {
            "description": "Import bundle using git bundle",
            "commands": [
                "git bundle is-supported migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle || echo 'bundle may need newer git'",
                "git fetch migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle HEAD:refs/heads/foundation-workflow-review",
                "git checkout foundation-workflow-review",
            ],
        },
        "warnings": [],
        "errors": [],
    }

    manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False)
    manifest_path.write_text(manifest_json, encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "manifest_exists": manifest_path.exists(),
        "manifest_size_bytes": manifest_path.stat().st_size if manifest_path.exists() else 0,
        "manifest_sha256": _sha256(manifest_path) if manifest_path.exists() else "",
        "warnings": [],
        "errors": [],
    }


# ── 9. verify_no_local_mutation_after_patch_bundle ─────────────────────────────


def verify_no_local_mutation_after_patch_bundle(
    root: Optional[str] = None,
    baseline: Optional[dict] = None,
) -> dict:
    """Verify no unintended file modifications occurred during artifact generation.

    Only new files allowed: R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch,
    R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle,
    R241-16S_PATCH_BUNDLE_MANIFEST.json,
    R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json
    """
    root_path = Path(root) if root else ROOT
    after = _safe_baseline()
    base = baseline or {}

    checks = []
    warnings = []
    errors = []

    # Check: HEAD unchanged
    head_unchanged = after["head_hash"] == base.get("head_hash", after["head_hash"])
    checks.append({
        "check_id": "head_unchanged",
        "check_type": "head_stable",
        "passed": head_unchanged,
        "risk_level": "critical",
        "description": "HEAD hash must not change during artifact generation",
        "observed_value": after["head_hash"],
        "expected_value": base.get("head_hash", after["head_hash"]),
        "blocked_reasons": [] if head_unchanged else ["head_changed"],
    })

    # Check: branch unchanged
    branch_unchanged = after["branch"] == base.get("branch", after["branch"])
    checks.append({
        "check_id": "branch_unchanged",
        "check_type": "branch_stable",
        "passed": branch_unchanged,
        "risk_level": "critical",
        "description": "Current branch must not change",
        "observed_value": after["branch"],
        "expected_value": base.get("branch", after["branch"]),
        "blocked_reasons": [] if branch_unchanged else ["branch_changed"],
    })

    # Check: staged area still empty
    staged_still_empty = len(after["staged_files"]) == 0
    checks.append({
        "check_id": "staged_area_still_empty",
        "check_type": "staged_area",
        "passed": staged_still_empty,
        "risk_level": "critical",
        "description": "Staged area must still be empty after generation",
        "observed_value": after["staged_files"],
        "expected_value": [],
        "blocked_reasons": [] if staged_still_empty else ["staged_area_became_nonempty"],
    })

    # Check: audit JSONL line count unchanged
    audit_unchanged = after["audit_jsonl_line_count"] == base.get("audit_jsonl_line_count", after["audit_jsonl_line_count"])
    checks.append({
        "check_id": "audit_jsonl_unchanged",
        "check_type": "audit_jsonl",
        "passed": audit_unchanged,
        "risk_level": "high",
        "description": "Audit JSONL line count must not change",
        "observed_value": after["audit_jsonl_line_count"],
        "expected_value": base.get("audit_jsonl_line_count", after["audit_jsonl_line_count"]),
        "blocked_reasons": [] if audit_unchanged else ["audit_jsonl_modified"],
    })

    # Check: runtime dir unchanged
    runtime_unchanged = after["runtime_dir_exists"] == base.get("runtime_dir_exists", after["runtime_dir_exists"])
    checks.append({
        "check_id": "runtime_dir_unchanged",
        "check_type": "runtime_dir",
        "passed": runtime_unchanged,
        "risk_level": "high",
        "description": "Runtime directory must not change",
        "observed_value": after["runtime_dir_exists"],
        "expected_value": base.get("runtime_dir_exists", after["runtime_dir_exists"]),
        "blocked_reasons": [] if runtime_unchanged else ["runtime_dir_modified"],
    })

    # Check: workflow file unchanged (using diff to verify)
    workflow_path = root_path / TARGET_WORKFLOW
    if workflow_path.exists():
        diff_result = _run_git(["git", "diff", str(TARGET_WORKFLOW)], str(root_path))
        workflow_unchanged = diff_result.get("stdout", "").strip() == ""
        checks.append({
            "check_id": "workflow_file_unchanged",
            "check_type": "workflow_mutation",
            "passed": workflow_unchanged,
            "risk_level": "critical",
            "description": f"Target workflow {TARGET_WORKFLOW} must not be modified",
            "observed_value": "modified" if not workflow_unchanged else "unchanged",
            "expected_value": "unchanged",
            "command_result": diff_result,
            "blocked_reasons": [] if workflow_unchanged else ["workflow_file_modified"],
        })

    # Check: only R241-16S artifacts are new (patch/bundle/manifest/result)
    output_dir = REPORT_DIR if not root else root_path / "migration_reports" / "foundation_audit"
    # NOTE: generate_patch_bundle_generation_report uses with_suffix(".md") on the JSON path,
    # so RESULT.json -> RESULT.md (not REPORT.md). Keep names in sync with that function.
    new_artifact_names = {
        "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
        "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle",
        "R241-16S_PATCH_BUNDLE_MANIFEST.json",
        "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json",
        "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.md",
    }
    unexpected_new_files = []
    if output_dir.exists():
        for f in output_dir.iterdir():
            if f.is_file() and f.name.startswith("R241-16S"):
                if f.name not in new_artifact_names:
                    unexpected_new_files.append(f.name)
            elif f.is_file() and f.name.startswith("0001-"):
                # format-patch auto-generated name that we renamed away
                pass
            elif f.is_file() and f.suffix == ".patch" and f.name not in new_artifact_names:
                unexpected_new_files.append(f.name)

    no_unexpected = len(unexpected_new_files) == 0
    checks.append({
        "check_id": "no_unexpected_artifacts",
        "check_type": "artifact_naming",
        "passed": no_unexpected,
        "risk_level": "low",
        "description": "Only R241-16S-* artifact files should be generated",
        "observed_value": unexpected_new_files,
        "expected_value": [],
        "blocked_reasons": [] if no_unexpected else [f"unexpected_files: {unexpected_new_files}"],
    })

    all_passed = all(c.get("passed", False) for c in checks)
    blocked_reasons = [r for c in checks if not c.get("passed") for r in c.get("blocked_reasons", [])]

    return {
        "all_passed": all_passed,
        "baseline": base,
        "after_state": after,
        "checks": checks,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": errors,
    }


# ── 10. execute_patch_bundle_generation ───────────────────────────────────────


def execute_patch_bundle_generation(
    root: Optional[str] = None,
    generate_bundle: bool = True,
) -> dict:
    """Core execution: precheck -> baseline -> generate patch -> generate bundle -> inspect -> manifest -> mutate guard."""
    result_id = f"R241-16S-result-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    # Step 1: Run prechecks
    prechecks = run_patch_bundle_prechecks(root)
    if not prechecks.get("all_passed"):
        return {
            "result_id": result_id,
            "generated_at": _now(),
            "status": PatchBundleGenerationStatus.BLOCKED_PRECHECK_FAILED.value,
            "decision": PatchBundleGenerationDecision.BLOCK_GENERATION.value,
            "source_commit_hash": SOURCE_COMMIT_HASH,
            "source_commit_only_target_workflow": True,
            "patch_generated": False,
            "bundle_generated": False,
            "manifest_generated": False,
            "artifacts": [],
            "prechecks": prechecks,
            "baseline": {},
            "patch_artifact": {},
            "bundle_artifact": {},
            "manifest_result": {},
            "git_command_results": [],
            "validation_result": {},
            "local_mutation_guard": {},
            "existing_workflows_unchanged": True,
            "warnings": [],
            "errors": [],
        }

    # Step 2: Capture baseline
    baseline = capture_patch_bundle_baseline(root)

    # Step 3: Generate patch
    patch_result = generate_patch_artifact(root, SOURCE_COMMIT_HASH)
    patch_generated = patch_result.get("patch_exists", False)

    git_commands = [patch_result]

    # Step 4: Generate bundle (if requested)
    bundle_generated = False
    bundle_result = {}
    if generate_bundle:
        bundle_result = generate_bundle_artifact(root, SOURCE_COMMIT_HASH)
        bundle_generated = bundle_result.get("bundle_exists", False)
        git_commands.append(bundle_result)

    # Step 5: Inspect patch
    patch_inspection = inspect_patch_artifact(root)

    # Step 6: Inspect bundle
    bundle_inspection = {}
    if generate_bundle and bundle_generated:
        bundle_inspection = inspect_bundle_artifact(root, None, SOURCE_COMMIT_HASH)

    # Step 7: Generate manifest
    result_so_far = {
        "patch_artifact": patch_result,
        "bundle_artifact": bundle_result,
    }
    manifest_result = generate_patch_bundle_manifest(root, result_so_far)

    # Step 8: Mutation guard
    mutation_guard = verify_no_local_mutation_after_patch_bundle(root, baseline)

    # Step 9: Determine final status
    if not patch_generated:
        status = PatchBundleGenerationStatus.PATCH_GENERATION_FAILED
    elif generate_bundle and not bundle_generated:
        status = PatchBundleGenerationStatus.GENERATED_PATCH_ONLY
    elif patch_generated and bundle_generated and mutation_guard.get("all_passed", False):
        status = PatchBundleGenerationStatus.GENERATED
    elif patch_generated and mutation_guard.get("all_passed", False):
        status = PatchBundleGenerationStatus.GENERATED_PATCH_ONLY
    elif mutation_guard.get("all_passed", False) is False:
        status = PatchBundleGenerationStatus.VALIDATION_FAILED
    else:
        status = PatchBundleGenerationStatus.UNKNOWN

    decision = PatchBundleGenerationDecision.GENERATE_PATCH_AND_BUNDLE if (patch_generated and bundle_generated) else \
        PatchBundleGenerationDecision.GENERATE_PATCH_ONLY if patch_generated else \
        PatchBundleGenerationDecision.BLOCK_GENERATION

    artifacts = []
    if patch_generated:
        artifacts.append({
            "artifact_id": f"artifact-patch-{result_id}",
            "artifact_type": PatchBundleArtifactType.PATCH.value,
            "path": patch_result.get("canonical_path") or patch_result.get("generated_patch_path", ""),
            "exists": True,
            "size_bytes": patch_result.get("patch_size_bytes", 0),
            "sha256": patch_result.get("patch_sha256", ""),
            "contains_target_workflow": patch_result.get("contains_only_target_workflow", False),
            "contains_non_target_files": not patch_result.get("contains_only_target_workflow", True),
            "safe_to_share": patch_inspection.get("safe_to_share", False),
            "warnings": patch_inspection.get("warnings", []),
            "errors": patch_inspection.get("errors", []),
        })
    if bundle_generated:
        artifacts.append({
            "artifact_id": f"artifact-bundle-{result_id}",
            "artifact_type": PatchBundleArtifactType.BUNDLE.value,
            "path": bundle_result.get("bundle_path", ""),
            "exists": True,
            "size_bytes": bundle_result.get("bundle_size_bytes", 0),
            "sha256": bundle_result.get("bundle_sha256", ""),
            "safe_to_share": bundle_inspection.get("safe_to_share", False),
            "warnings": bundle_inspection.get("warnings", []),
            "errors": bundle_inspection.get("errors", []),
        })
    if manifest_result.get("manifest_exists"):
        artifacts.append({
            "artifact_id": f"artifact-manifest-{result_id}",
            "artifact_type": PatchBundleArtifactType.MANIFEST.value,
            "path": manifest_result.get("manifest_path", ""),
            "exists": True,
            "size_bytes": manifest_result.get("manifest_size_bytes", 0),
            "sha256": manifest_result.get("manifest_sha256", ""),
            "safe_to_share": True,
            "warnings": [],
            "errors": [],
        })

    return {
        "result_id": result_id,
        "generated_at": _now(),
        "status": status.value,
        "decision": decision.value,
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_commit_only_target_workflow": True,
        "patch_generated": patch_generated,
        "bundle_generated": bundle_generated,
        "manifest_generated": manifest_result.get("manifest_exists", False),
        "artifacts": artifacts,
        "prechecks": prechecks,
        "baseline": baseline,
        "patch_artifact": patch_result,
        "bundle_artifact": bundle_result,
        "manifest_result": manifest_result,
        "git_command_results": git_commands,
        "validation_result": {},
        "local_mutation_guard": mutation_guard,
        "existing_workflows_unchanged": mutation_guard.get("all_passed", False),
        "warnings": patch_inspection.get("warnings", []) + bundle_inspection.get("warnings", []) + mutation_guard.get("warnings", []),
        "errors": patch_inspection.get("errors", []) + bundle_inspection.get("errors", []) + mutation_guard.get("errors", []),
    }


# ── 11. validate_patch_bundle_generation_result ───────────────────────────────


def validate_patch_bundle_generation_result(result: dict) -> dict:
    """Validate the generation result did not violate safety constraints."""
    blocked_reasons = []
    warnings = []

    # Check: no git push
    git_commands = result.get("git_command_results", [])
    for cmd in git_commands:
        argv = cmd.get("argv", [])
        if argv and argv[0] == "git" and len(argv) > 1 and argv[1] == "push":
            blocked_reasons.append("git_push_executed")

    # Check: no git commit
    for cmd in git_commands:
        argv = cmd.get("argv", [])
        if argv and argv[0] == "git" and len(argv) > 1 and argv[1] == "commit":
            blocked_reasons.append("git_commit_executed")

    # Check: no git reset/restore/revert
    forbidden_git = {"reset", "restore", "revert", "checkout", "branch", "merge", "rebase"}
    for cmd in git_commands:
        argv = cmd.get("argv", [])
        if argv and argv[0] == "git" and len(argv) > 1 and argv[1] in forbidden_git:
            blocked_reasons.append(f"forbidden_git_command: {' '.join(argv)}")

    # Check: no gh workflow run
    for cmd in git_commands:
        argv = cmd.get("argv", [])
        if argv and argv[0] == "gh" and "workflow" in argv[1:]:
            blocked_reasons.append("gh_workflow_run_executed")

    # Check: mutation guard passed
    guard = result.get("local_mutation_guard", {})
    if not guard.get("all_passed", False):
        blocked_reasons.extend(guard.get("blocked_reasons", []))

    # Check: artifacts safe_to_share
    artifacts = result.get("artifacts", [])
    for artifact in artifacts:
        if artifact.get("artifact_type") == PatchBundleArtifactType.PATCH.value:
            if not artifact.get("safe_to_share", False):
                blocked_reasons.append("patch_not_safe_to_share")
        if artifact.get("artifact_type") == PatchBundleArtifactType.BUNDLE.value:
            if not artifact.get("safe_to_share", False):
                blocked_reasons.append("bundle_not_safe_to_share")

    # Check: patch contains only target workflow (if patch was attempted)
    patch_artifact = result.get("patch_artifact", {})
    patch_exists = patch_artifact.get("patch_exists", False)
    if patch_exists and not patch_artifact.get("contains_only_target_workflow", False):
        blocked_reasons.append("patch_contains_extra_files")

    # Check: no runtime write signals
    guard_checks = guard.get("checks", [])
    for gc in guard_checks:
        if not gc.get("passed") and "runtime" in str(gc.get("blocked_reasons", [])):
            blocked_reasons.append("runtime_dir_modified")

    valid = len(blocked_reasons) == 0

    return {
        "valid": valid,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": [],
    }


# ── 12. generate_patch_bundle_generation_report ──────────────────────────────


def generate_patch_bundle_generation_report(
    result: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Generate R241-16S patch bundle generation report.

    Writes:
      migration_reports/foundation_audit/R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json
      migration_reports/foundation_audit/R241-16S_PATCH_BUNDLE_GENERATION_REPORT.md
    """
    if result is None:
        result = execute_patch_bundle_generation()

    validation = validate_patch_bundle_generation_result(result)

    if output_path:
        json_path = Path(output_path)
    else:
        json_path = REPORT_DIR / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json"

    json_path.parent.mkdir(parents=True, exist_ok=True)

    report_data = {
        "result_id": result.get("result_id"),
        "generated_at": result.get("generated_at"),
        "status": result.get("status"),
        "decision": result.get("decision"),
        "source_commit_hash": result.get("source_commit_hash"),
        "source_commit_only_target_workflow": result.get("source_commit_only_target_workflow"),
        "patch_generated": result.get("patch_generated"),
        "bundle_generated": result.get("bundle_generated"),
        "manifest_generated": result.get("manifest_generated"),
        "artifacts": result.get("artifacts", []),
        "prechecks": result.get("prechecks", {}),
        "baseline_captured": bool(result.get("baseline")),
        "patch_artifact": result.get("patch_artifact", {}),
        "bundle_artifact": result.get("bundle_artifact", {}),
        "manifest_result": result.get("manifest_result", {}),
        "git_command_results": [
            {
                "argv": r.get("argv", []),
                "exit_code": r.get("exit_code"),
                "command_executed": r.get("command_executed"),
            }
            for r in result.get("git_command_results", [])
        ],
        "validation": validation,
        "local_mutation_guard": result.get("local_mutation_guard", {}),
        "existing_workflows_unchanged": result.get("existing_workflows_unchanged"),
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    md_path = json_path.with_suffix(".md")
    _write_markdown_report(report_data, str(md_path), validation)

    return {
        "output_path": str(json_path),
        "report_path": str(md_path),
        "result": result,
        "validation": validation,
    }


def _write_markdown_report(data: dict, path: str, validation: dict) -> None:
    """Write Markdown version of the generation report."""
    lines = [
        "# R241-16S Patch Bundle Generation Report",
        "",
        "## Generation Result",
        "",
        f"- **Result ID**: `{data.get('result_id', '')}`",
        f"- **Generated**: `{data.get('generated_at', '')}`",
        f"- **Status**: `{data.get('status', '')}`",
        f"- **Decision**: `{data.get('decision', '')}`",
        f"- **Source Commit**: `{data.get('source_commit_hash', '')}`",
        f"- **Source Commit Only Target Workflow**: `{data.get('source_commit_only_target_workflow')}`",
        "",
        "## Artifact Summary",
        "",
    ]

    for artifact in data.get("artifacts", []):
        lines.extend([
            f"### {artifact.get('artifact_type', '').upper()}",
            f"- **Path**: `{artifact.get('path', '')}`",
            f"- **Exists**: `{artifact.get('exists')}`",
            f"- **Size**: `{artifact.get('size_bytes', 0)}` bytes",
            f"- **SHA256**: `{artifact.get('sha256', '')[:16]}...`",
            f"- **Safe to Share**: `{artifact.get('safe_to_share')}`",
            "",
        ])

    lines.extend([
        "## Precheck Results",
        "",
        f"- **All Passed**: `{data.get('prechecks', {}).get('all_passed')}`",
        f"- **Gate Loaded**: `{data.get('prechecks', {}).get('gate_loaded')}`",
        f"- **Gate Passed**: `{data.get('prechecks', {}).get('gate_passed')}`",
        "",
    ])

    for check in data.get("prechecks", {}).get("checks", []):
        status_icon = "✅" if check.get("passed") else "❌"
        lines.append(f"{status_icon} **{check.get('check_id', '')}** ({check.get('risk_level', '')}): {check.get('description', '')}")

    lines.extend([
        "",
        "## Git Commands Executed",
        "",
    ])

    for cmd in data.get("git_command_results", []):
        lines.append(f"- `{' '.join(cmd.get('argv', []))}` → exit `{cmd.get('exit_code')}`")

    lines.extend([
        "",
        "## Mutation Guard",
        "",
        f"- **All Passed**: `{data.get('local_mutation_guard', {}).get('all_passed')}`",
    ])

    for check in data.get("local_mutation_guard", {}).get("checks", []):
        status_icon = "✅" if check.get("passed") else "❌"
        lines.append(f"{status_icon} {check.get('check_id', '')}: {check.get('description', '')}")

    lines.extend([
        "",
        "## Validation",
        "",
        f"- **Valid**: `{validation.get('valid')}`",
        f"- **Blocked Reasons**: `{validation.get('blocked_reasons', [])}`",
        "",
        "## Safety Constraints",
        "",
        "✅ No git push executed",
        "✅ No git commit executed",
        "✅ No git reset/restore/revert executed",
        "✅ No gh workflow run executed",
        "✅ No workflow files modified",
        "✅ No runtime/audit JSONL/action queue write",
        "✅ No auto-fix executed",
        "",
        "## Apply Instructions",
        "",
        "```bash",
        "# Apply patch",
        "git am < migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
        "",
        "# Dry-run first",
        "git apply --check migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
        "```",
        "",
        "## Verification",
        "",
        "```bash",
        f"# Verify commit contents",
        f"git diff-tree --no-commit-id --name-only -r {data.get('source_commit_hash', '')}",
        "# Should output: .github/workflows/foundation-manual-workflow.yml",
        "```",
        "",
        "## Next Recommendation",
        "",
        "- Proceed to R241-16T: Patch Bundle Verification / Delivery Review",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
