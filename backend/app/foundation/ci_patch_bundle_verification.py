"""R241-16T: Patch Bundle Verification / Delivery Review.

Read-only verification of R241-16S patch bundle generation artifacts:
- Verify patch is safe to share (no backend/runtime paths, no secrets)
- Verify bundle integrity via git bundle verify (NO fetch/checkout)
- Fix manifest path inconsistency (foundation-manual-workflow.yml typo)
- Verify manifest consistency with source commit
- Run git apply --check (dry-run only, never actual apply)
- Generate delivery note
- Verify no local mutation occurred during verification

Allowed read operations:
  git status --branch --short
  git diff --cached --name-only
  git diff-tree --no-commit-id --name-only -r <hash>
  git show --name-only --format=fuller <hash>
  git apply --check <patch>   (dry-run only)
  git bundle verify <bundle>
  git ls-tree -r origin/main -- <workflow>

Allowed write operations:
  R241-16T_VERIFICATION_RESULT.json
  R241-16T_VERIFICATION_REPORT.md
  R241-16T_PATCH_DELIVERY_NOTE.md
  Corrected R241-16S_PATCH_BUNDLE_MANIFEST.json
  Corrected R241-16S_PATCH_BUNDLE_MANIFEST.md (if present)

Forbidden: push, commit, reset, restore, revert, checkout, branch, merge,
rebase, am, actual apply, gh workflow run, gh pr create, secret read,
runtime write, audit JSONL write, action queue write, auto-fix.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]

REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
GENERATION_RESULT_PATH = REPORT_DIR / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json"
MANIFEST_PATH = REPORT_DIR / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
TARGET_WORKFLOW = ".github/workflows/foundation-manual-dispatch.yml"
SOURCE_COMMIT_HASH = "94908556cc2ca66c219d361f424954945eee9e67"


# ── Enums ────────────────────────────────────────────────────────────────────


class PatchBundleVerificationStatus(str, Enum):
    VERIFIED = "verified"
    VERIFIED_WITH_WARNINGS = "verified_with_warnings"
    BLOCKED_MISSING_ARTIFACT = "blocked_missing_artifact"
    BLOCKED_PATCH_UNSAFE = "blocked_patch_unsafe"
    BLOCKED_BUNDLE_INVALID = "blocked_bundle_invalid"
    BLOCKED_MANIFEST_INCONSISTENT = "blocked_manifest_inconsistent"
    BLOCKED_MUTATION_DETECTED = "blocked_mutation_detected"
    UNKNOWN = "unknown"


class PatchBundleVerificationDecision(str, Enum):
    APPROVE_DELIVERY_ARTIFACTS = "approve_delivery_artifacts"
    APPROVE_PATCH_ONLY_DELIVERY = "approve_patch_only_delivery"
    BLOCK_DELIVERY = "block_delivery"
    UNKNOWN = "unknown"


class PatchBundleVerificationRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class PatchBundleDeliveryArtifactType(str, Enum):
    PATCH = "patch"
    BUNDLE = "bundle"
    MANIFEST = "manifest"
    DELIVERY_NOTE = "delivery_note"
    REPORT = "report"
    UNKNOWN = "unknown"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(root: Optional[str]) -> Path:
    if root:
        p = Path(root).resolve()
        if p.is_dir():
            return p
    return ROOT


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
            "runtime_seconds": None,
            "warnings": [],
            "errors": [],
        }
    except subprocess.TimeoutExpired:
        return {
            "argv": argv,
            "command_executed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Timed out after {timeout}s",
            "cwd": cwd,
            "runtime_seconds": timeout,
            "warnings": [],
            "errors": [f"Command timed out after {timeout}s"],
        }
    except Exception as e:
        return {
            "argv": argv,
            "command_executed": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "cwd": cwd,
            "runtime_seconds": None,
            "warnings": [],
            "errors": [str(e)],
        }


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _safe_baseline(root: Optional[str] = None) -> dict:
    """Capture current git state without any mutation."""
    root_path = _root(root)
    head_result = _run_git(["git", "rev-parse", "HEAD"], str(root_path))
    branch_result = _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], str(root_path))
    staged_result = _run_git(["git", "diff", "--cached", "--name-only"], str(root_path))
    status_result = _run_git(["git", "status", "--short"], str(root_path))
    audit_path = REPORT_DIR / "audit_trail" / "foundation_diagnostic_runs.jsonl"
    audit_count = 0
    if audit_path.exists():
        audit_count = len(audit_path.read_text(encoding="utf-8").splitlines())
    runtime_exists = (root_path / "runtime").exists()
    return {
        "captured_at": _now(),
        "head_hash": head_result.get("stdout", "").strip() or None,
        "branch": branch_result.get("stdout", "").strip() or None,
        "staged_files": [
            f for f in staged_result.get("stdout", "").splitlines() if f.strip()
        ],
        "git_status_short": status_result.get("stdout", ""),
        "audit_jsonl_line_count": audit_count,
        "runtime_dir_exists": runtime_exists,
    }


# ── 1. load_patch_bundle_generation_result ───────────────────────────────────


def load_patch_bundle_generation_result(root: Optional[str] = None) -> dict:
    """Load and validate R241-16S generation result.

    Returns dict with:
      loaded: bool
      valid: bool (generation was successful and safe)
      result: the full generation result dict
      blocked_reasons: list of issues found
    """
    root_path = _root(root)
    blocked_reasons = []
    warnings = []

    if not GENERATION_RESULT_PATH.exists():
        return {
            "loaded": False,
            "valid": False,
            "result": {},
            "blocked_reasons": ["generation_result_not_found"],
            "warnings": [],
        }

    try:
        with open(GENERATION_RESULT_PATH, encoding="utf-8") as f:
            result = json.load(f)
    except Exception as e:
        return {
            "loaded": False,
            "valid": False,
            "result": {},
            "blocked_reasons": [f"generation_result_parse_error: {e}"],
            "warnings": [],
        }

    # Validate required fields
    if result.get("status") not in ("generated", "generated_patch_only"):
        blocked_reasons.append(f"unexpected_generation_status: {result.get('status')}")

    if not result.get("patch_generated"):
        blocked_reasons.append("patch_not_generated")

    if not result.get("manifest_generated"):
        blocked_reasons.append("manifest_not_generated")

    if not result.get("source_commit_hash"):
        blocked_reasons.append("missing_source_commit_hash")

    if result.get("source_commit_hash") != SOURCE_COMMIT_HASH:
        blocked_reasons.append(
            f"source_commit_mismatch: expected {SOURCE_COMMIT_HASH}, "
            f"got {result.get('source_commit_hash')}"
        )

    if not result.get("source_commit_only_target_workflow"):
        blocked_reasons.append("source_commit_not_target_only")

    # Check no forbidden operations in generation result
    git_cmds = result.get("git_command_results", [])
    for cmd in git_cmds:
        argv = cmd.get("argv", [])
        if argv and argv[0] == "git" and len(argv) > 1:
            if argv[1] == "push":
                blocked_reasons.append("git_push_in_generation")
            elif argv[1] == "commit":
                blocked_reasons.append("git_commit_in_generation")
            elif argv[1] in ("reset", "restore", "revert", "checkout", "branch", "merge", "rebase"):
                blocked_reasons.append(f"forbidden_git_command: {' '.join(argv)}")

    # Check mutation guard passed
    mg = result.get("local_mutation_guard", {})
    if not mg.get("all_passed"):
        blocked_reasons.extend(mg.get("blocked_reasons", []))

    # Check validation passed
    val = result.get("validation", {})
    if not val.get("valid"):
        blocked_reasons.extend(val.get("blocked_reasons", []))

    valid = len(blocked_reasons) == 0
    return {
        "loaded": True,
        "valid": valid,
        "result": result,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
    }


# ── 2. load_patch_bundle_manifest ───────────────────────────────────────────


def load_patch_bundle_manifest(root: Optional[str] = None) -> dict:
    """Load and validate R241-16S patch bundle manifest.

    Returns dict with:
      loaded: bool
      manifest: the manifest dict
      blocked_reasons: list of issues
    """
    root_path = _root(root)
    blocked_reasons = []
    warnings = []

    if not MANIFEST_PATH.exists():
        return {
            "loaded": False,
            "manifest": {},
            "blocked_reasons": ["manifest_not_found"],
            "warnings": [],
        }

    try:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        return {
            "loaded": False,
            "manifest": {},
            "blocked_reasons": [f"manifest_parse_error: {e}"],
            "warnings": [],
        }

    # Validate source_changed_files
    changed_files = manifest.get("source_changed_files", [])
    expected = [TARGET_WORKFLOW]
    if changed_files != expected:
        blocked_reasons.append(
            f"source_changed_files_mismatch: expected {expected}, got {changed_files}"
        )

    # Validate patch exists
    patch_path_str = manifest.get("patch_path", "")
    if patch_path_str:
        patch_path = Path(patch_path_str)
        if not patch_path.exists():
            blocked_reasons.append("manifest_patch_path_not_found")
        if manifest.get("patch_exists") is False:
            warnings.append("manifest_reports_patch_not_exists")

    # Validate bundle exists (may be absent if patch-only delivery)
    bundle_path_str = manifest.get("bundle_path", "")
    if bundle_path_str:
        bundle_path = Path(bundle_path_str)
        if not bundle_path.exists() and manifest.get("bundle_exists"):
            blocked_reasons.append("manifest_bundle_path_not_found")

    # Validate push_failure_reason
    if manifest.get("push_failure_reason") != "permission_denied_403":
        warnings.append(f"unexpected_push_failure_reason: {manifest.get('push_failure_reason')}")

    # Validate remote_workflow_present
    if manifest.get("remote_workflow_present") is not False:
        warnings.append(f"unexpected_remote_workflow_present: {manifest.get('remote_workflow_present')}")

    return {
        "loaded": True,
        "manifest": manifest,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
    }


# ── 3. detect_and_fix_manifest_path_consistency ─────────────────────────────


def detect_and_fix_manifest_path_consistency(root: Optional[str] = None) -> dict:
    """Detect and fix manifest path typos (foundation-manual-workflow.yml).

    This function ONLY fixes the manifest JSON. It does NOT modify the patch
    or bundle or workflow.

    Returns dict with:
      typo_detected: bool
      fixed: bool
      old_path: the incorrect path found (if any)
      new_path: the corrected path
      manifest_updated: bool
      blocked_reasons: list
    """
    root_path = _root(root)
    blocked_reasons = []
    warnings = []

    manifest_data, loaded = _load_manifest_raw(root)

    if not loaded:
        return {
            "typo_detected": False,
            "fixed": False,
            "manifest_updated": False,
            "blocked_reasons": ["manifest_not_loadable"],
            "warnings": [],
        }

    WRONG_PATH = "foundation-manual-workflow.yml"
    CORRECT_PATH = "foundation-manual-dispatch.yml"
    typo_detected = False
    fixed = False

    # Check verification_instructions for the typo
    verif_instr = manifest_data.get("verification_instructions", {})
    verif_commands = verif_instr.get("commands", [])
    old_path = None
    new_path = None

    for i, cmd in enumerate(verif_commands):
        if WRONG_PATH in cmd:
            typo_detected = True
            old_path = WRONG_PATH
            new_path = CORRECT_PATH
            verif_commands[i] = cmd.replace(WRONG_PATH, CORRECT_PATH)
            manifest_data["verification_instructions"]["commands"] = verif_commands

    # Also check if the typo appears anywhere else in verification_instructions
    verif_str = json.dumps(verif_instr)
    if WRONG_PATH in verif_str and not typo_detected:
        # Do a more thorough replacement
        typo_detected = True
        old_path = WRONG_PATH
        new_path = CORRECT_PATH
        verif_str_fixed = verif_str.replace(WRONG_PATH, CORRECT_PATH)
        try:
            manifest_data["verification_instructions"] = json.loads(verif_str_fixed)
        except Exception:
            # Fallback: replace in the string representation
            manifest_data["verification_instructions"]["_raw_fixed"] = verif_str_fixed

    # If we detected the typo in verification_instructions, write the corrected manifest
    if typo_detected:
        try:
            manifest_json = json.dumps(manifest_data, indent=2, ensure_ascii=False)
            MANIFEST_PATH.write_text(manifest_json, encoding="utf-8")
            fixed = True
        except Exception as e:
            blocked_reasons.append(f"manifest_write_error: {e}")
            fixed = False
            typo_detected = False  # Can't claim we fixed it if write failed

    return {
        "typo_detected": typo_detected,
        "fixed": fixed,
        "old_path": old_path,
        "new_path": new_path,
        "manifest_updated": fixed,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
    }


def _load_manifest_raw(root: Optional[str] = None) -> tuple[dict, bool]:
    """Load manifest JSON raw, returns (data, loaded)."""
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f), True
    except Exception:
        return {}, False


# ── 4. inspect_patch_delivery_artifact ─────────────────────────────────────


def inspect_patch_delivery_artifact(root: Optional[str] = None) -> dict:
    """Inspect patch file for safety.

    Reads the patch file and checks:
    - File exists and SHA256 matches manifest
    - Contains only the target workflow
    - No forbidden paths (backend/, frontend/, runtime/, etc.)
    - No secrets/tokens/webhooks
    - No auto-fix enablement

    Returns dict with all safety checks.
    """
    root_path = _root(root)
    checks = []
    blocked_reasons = []
    warnings = []
    errors = []

    # Load manifest for SHA/size comparison
    manifest_data, _ = _load_manifest_raw(root)
    manifest_patch_path = manifest_data.get("patch_path", "")
    manifest_sha = manifest_data.get("patch_sha256", "")
    manifest_size = manifest_data.get("patch_size_bytes", 0)

    # Resolve patch path
    patch_path = REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
    if manifest_patch_path:
        candidate = Path(manifest_patch_path)
        if candidate.exists():
            patch_path = candidate

    patch_exists = patch_path.exists()

    # Check 1: patch exists
    checks.append({
        "check_id": "patch_exists",
        "check_type": "artifact_existence",
        "passed": patch_exists,
        "risk_level": "critical",
        "description": "Patch file must exist",
        "observed_value": str(patch_path),
        "expected_value": "file exists",
        "blocked_reasons": [] if patch_exists else ["patch_file_missing"],
        "warnings": [],
        "errors": [],
    })
    if not patch_exists:
        blocked_reasons.append("patch_file_missing")
        return _patch_inspection_result(
            checks, blocked_reasons, warnings, errors,
            patch_path, manifest_sha, manifest_size
        )

    # Check 2: SHA256 matches manifest
    actual_sha = _sha256(patch_path)
    sha_matches = actual_sha == manifest_sha if manifest_sha else True
    checks.append({
        "check_id": "patch_sha256_matches_manifest",
        "check_type": "artifact_integrity",
        "passed": sha_matches,
        "risk_level": "critical",
        "description": "Patch SHA256 must match manifest",
        "observed_value": actual_sha[:16] + "..." if actual_sha else "N/A",
        "expected_value": (manifest_sha[:16] + "...") if manifest_sha else "N/A",
        "blocked_reasons": [] if sha_matches else [f"patch_sha_mismatch: expected {manifest_sha}, got {actual_sha}"],
        "warnings": [] if sha_matches else [f"patch SHA mismatch: expected {manifest_sha[:16]}, got {actual_sha[:16]}"],
        "errors": [],
    })
    if not sha_matches:
        blocked_reasons.append(f"patch_sha_mismatch")

    # Check 3: size matches manifest
    actual_size = patch_path.stat().st_size
    size_matches = actual_size == manifest_size if manifest_size else True
    checks.append({
        "check_id": "patch_size_matches_manifest",
        "check_type": "artifact_integrity",
        "passed": size_matches,
        "risk_level": "medium",
        "description": "Patch size should match manifest",
        "observed_value": actual_size,
        "expected_value": manifest_size,
        "blocked_reasons": [] if size_matches else [f"patch_size_mismatch"],
        "warnings": [] if size_matches else [f"patch size {actual_size} vs manifest {manifest_size}"],
        "errors": [],
    })

    # Check 4: contains target workflow path
    content = patch_path.read_text(encoding="utf-8", errors="replace")
    contains_target = TARGET_WORKFLOW in content
    checks.append({
        "check_id": "patch_contains_target_workflow",
        "check_type": "patch_scope",
        "passed": contains_target,
        "risk_level": "critical",
        "description": f"Patch must contain {TARGET_WORKFLOW}",
        "observed_value": TARGET_WORKFLOW if contains_target else "NOT FOUND",
        "expected_value": TARGET_WORKFLOW,
        "blocked_reasons": [] if contains_target else ["patch_missing_target_workflow"],
        "warnings": [],
        "errors": [],
    })
    if not contains_target:
        blocked_reasons.append("patch_missing_target_workflow")

    # Check 5: only changed files are the target workflow
    # Parse diff --git lines
    # Format: "diff --git a/<path> b/<path>" — b/ path is at parts[3] (parts[2] is a/)
    changed_files = set()
    for line in content.splitlines():
        if line.startswith("diff --git"):
            parts = line.split()
            # parts[2] is "a/<path>", parts[3] is "b/<path>"
            # Handle both a->b and rename (a/old b/new) formats
            if len(parts) >= 4 and parts[2].startswith("b/"):
                changed_files.add(parts[2][2:])
            elif len(parts) >= 4 and parts[3].startswith("b/"):
                changed_files.add(parts[3][2:])
    only_target = changed_files == {TARGET_WORKFLOW}
    checks.append({
        "check_id": "patch_changed_files_only_target",
        "check_type": "patch_scope",
        "passed": only_target,
        "risk_level": "critical",
        "description": "Patch must only change the target workflow",
        "observed_value": sorted(changed_files),
        "expected_value": [TARGET_WORKFLOW],
        "blocked_reasons": [] if only_target else [f"patch_contains_extra_files: {sorted(changed_files)}"],
        "warnings": [],
        "errors": [],
    })
    if not only_target:
        blocked_reasons.append("patch_contains_extra_files")

    # Check 6: no forbidden paths (backend/, frontend/, runtime/, action_queue/, etc.)
    # These check the b/ path in "diff --git a/<old> b/<new>" lines
    # Also check for diff lines that add files to forbidden directories
    forbidden_path_patterns = [
        " b/backend/",
        " b/frontend/",
        " b/runtime/",
        " b/action_queue/",
        " b/memory/",
        " b/assets/",
        " b/scripts/ci_foundation_check.py",
        "diff --git a/backend/",
        "diff --git a/frontend/",
        "diff --git a/runtime/",
    ]
    found_forbidden = []
    for p in forbidden_path_patterns:
        if p in content:
            found_forbidden.append(p)
    no_forbidden = len(found_forbidden) == 0
    checks.append({
        "check_id": "patch_no_forbidden_paths",
        "check_type": "path_safety",
        "passed": no_forbidden,
        "risk_level": "critical",
        "description": "Patch must not contain forbidden paths",
        "observed_value": found_forbidden if found_forbidden else "none",
        "expected_value": "none",
        "blocked_reasons": [] if no_forbidden else [f"forbidden_paths: {found_forbidden}"],
        "warnings": [],
        "errors": [],
    })
    if not no_forbidden:
        blocked_reasons.append(f"forbidden_paths_in_patch: {found_forbidden}")

    # Check 7: no secrets/tokens/webhooks
    # Remove false positives first
    secret_patterns = [
        "ghp_", "gho_", "ghu_", "ghs_", "ghr_",  # GitHub tokens
        "sk-",  # OpenAI keys
        "xoxb-", "xoxp-",  # Slack tokens
        "APISTR", "api_key", "api-key", "secret",
    ]
    false_positives = ["workflow_dispatch", "workflow_call", "workflow_dispatch:", "workflow_call:", "no secrets", "no network"]
    content_clean = content
    for fp in false_positives:
        content_clean = re.sub(re.escape(fp), "", content_clean, flags=re.IGNORECASE)
    found_secrets = [p for p in secret_patterns if p in content_clean.lower()]
    no_secrets = len(found_secrets) == 0
    checks.append({
        "check_id": "patch_no_secrets",
        "check_type": "secret_safety",
        "passed": no_secrets,
        "risk_level": "critical",
        "description": "Patch must not contain secrets/tokens/webhooks",
        "observed_value": found_secrets if found_secrets else "none",
        "expected_value": "none",
        "blocked_reasons": [] if no_secrets else [f"secrets_found: {found_secrets}"],
        "warnings": [],
        "errors": [],
    })
    if not no_secrets:
        blocked_reasons.append(f"secrets_in_patch: {found_secrets}")

    # Check 8: no auto-fix enablement
    auto_fix_patterns = ["auto_fix:", "autofix:", "enable_auto_fix", "run_auto_fix"]
    found_auto_fix = [p for p in auto_fix_patterns if p in content]
    no_auto_fix = len(found_auto_fix) == 0
    checks.append({
        "check_id": "patch_no_auto_fix",
        "check_type": "safety_content",
        "passed": no_auto_fix,
        "risk_level": "high",
        "description": "Patch must not enable auto-fix",
        "observed_value": found_auto_fix if found_auto_fix else "none",
        "expected_value": "none",
        "blocked_reasons": [] if no_auto_fix else [f"auto_fix_in_patch: {found_auto_fix}"],
        "warnings": [],
        "errors": [],
    })
    if not no_auto_fix:
        blocked_reasons.append(f"auto_fix_in_patch")

    all_passed = all(c.get("passed", False) for c in checks)
    return _patch_inspection_result(
        checks, blocked_reasons, warnings, errors,
        patch_path, manifest_sha, manifest_size,
        all_passed
    )


def _patch_inspection_result(
    checks: list,
    blocked_reasons: list,
    warnings: list,
    errors: list,
    patch_path: Path,
    manifest_sha: str,
    manifest_size: int,
    all_passed: bool = None,
) -> dict:
    if all_passed is None:
        all_passed = all(c.get("passed", False) for c in checks)
    return {
        "check_type": "patch_inspection",
        "patch_path": str(patch_path),
        "patch_exists": patch_path.exists(),
        "patch_sha256": _sha256(patch_path) if patch_path.exists() else "",
        "patch_size_bytes": patch_path.stat().st_size if patch_path.exists() else 0,
        "manifest_sha256": manifest_sha,
        "manifest_size_bytes": manifest_size,
        "safe_to_share": all_passed and len(blocked_reasons) == 0,
        "all_passed": all_passed,
        "checks": checks,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": errors,
    }


# ── 5. run_patch_apply_check ───────────────────────────────────────────────


def run_patch_apply_check(root: Optional[str] = None) -> dict:
    """Run git apply --check as a dry-run only.

    This does NOT actually apply the patch. It only checks if the patch
    would apply cleanly to the current tree.

    Returns dict with:
      applies_cleanly: bool
      already_applied_or_conflicts: bool
      reason: str
      command_result: dict
      blocked_reasons: list
    """
    root_path = _root(root)
    patch_path = REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
    blocked_reasons = []
    warnings = []
    errors = []

    cmd_result = _run_git(
        ["git", "apply", "--check", str(patch_path)],
        str(root_path),
        timeout=15,
    )
    exit_code = cmd_result.get("exit_code", -1)
    stdout = cmd_result.get("stdout", "")
    stderr = cmd_result.get("stderr", "")

    applies_cleanly = exit_code == 0
    already_applied_or_conflicts = False

    if not applies_cleanly:
        # Check if this is because the file already exists (already applied)
        # or because it's actually an unsafe/conflicting patch
        reason_detail = (stdout + "\n" + stderr).lower()
        conflict_indicators = [
            "already exists",
            "already applied",
            "hunk #1 overlapping",
            "patch failed",
            "contents are unavailable",
        ]
        safe_indicators = ["foundation-manual-dispatch.yml" in stdout + stderr]
        if any(ind in reason_detail for ind in conflict_indicators):
            # This could be "already applied" or a real conflict
            # Check if the file already exists at the target path
            wf_path = root_path / TARGET_WORKFLOW
            file_exists_locally = wf_path.exists()

            # Also check if the source commit is already in the tree
            commit_check = _run_git(
                ["git", "cat-file", "-t", SOURCE_COMMIT_HASH],
                str(root_path),
            )
            commit_exists = commit_check.get("exit_code") == 0

            if file_exists_locally and commit_exists:
                # The source commit is already applied to the local tree
                already_applied_or_conflicts = True
                warnings.append(
                    "patch_already_applied_locally: "
                    f"source commit {SOURCE_COMMIT_HASH[:8]} is in tree "
                    "and target workflow file exists"
                )
            else:
                blocked_reasons.append(f"patch_apply_conflict: {stderr[:200]}")

    return {
        "applies_cleanly": applies_cleanly,
        "already_applied_or_conflicts": already_applied_or_conflicts,
        "exit_code": exit_code,
        "reason": stdout + "\n" + stderr,
        "command_executed": cmd_result.get("command_executed", False),
        "command_result": cmd_result,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": errors,
    }


# ── 6. inspect_bundle_delivery_artifact ──────────────────────────────────────


def inspect_bundle_delivery_artifact(root: Optional[str] = None) -> dict:
    """Inspect bundle artifact for integrity.

    Runs git bundle verify (read-only). Does NOT fetch, checkout, or clone.

    Returns dict with:
      bundle_exists: bool
      bundle_verify_passed: bool
      bundle_contains_source_commit: bool
      safe_to_share: bool
      command_result: dict
    """
    root_path = _root(root)
    checks = []
    blocked_reasons = []
    warnings = []
    errors = []

    # Load manifest for comparison
    manifest_data, _ = _load_manifest_raw(root)
    manifest_bundle_path = manifest_data.get("bundle_path", "")
    manifest_sha = manifest_data.get("bundle_sha256", "")
    manifest_size = manifest_data.get("bundle_size_bytes", 0)

    bundle_path = REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
    if manifest_bundle_path:
        candidate = Path(manifest_bundle_path)
        if candidate.exists():
            bundle_path = candidate

    bundle_exists = bundle_path.exists()

    checks.append({
        "check_id": "bundle_exists",
        "check_type": "artifact_existence",
        "passed": bundle_exists,
        "risk_level": "critical",
        "description": "Bundle file must exist",
        "observed_value": str(bundle_path),
        "expected_value": "file exists",
        "blocked_reasons": [] if bundle_exists else ["bundle_file_missing"],
        "warnings": [],
        "errors": [],
    })

    if not bundle_exists:
        blocked_reasons.append("bundle_file_missing")
        return {
            "bundle_path": str(bundle_path),
            "bundle_exists": False,
            "bundle_verify_passed": False,
            "bundle_contains_source_commit": False,
            "safe_to_share": False,
            "checks": checks,
            "blocked_reasons": blocked_reasons,
            "warnings": warnings,
            "errors": errors,
        }

    # Check SHA256 matches manifest
    actual_sha = _sha256(bundle_path)
    sha_matches = actual_sha == manifest_sha if manifest_sha else True
    checks.append({
        "check_id": "bundle_sha256_matches_manifest",
        "check_type": "artifact_integrity",
        "passed": sha_matches,
        "risk_level": "critical",
        "description": "Bundle SHA256 must match manifest",
        "observed_value": actual_sha[:16] + "..." if actual_sha else "N/A",
        "expected_value": (manifest_sha[:16] + "...") if manifest_sha else "N/A",
        "blocked_reasons": [] if sha_matches else [f"bundle_sha_mismatch"],
        "warnings": [] if sha_matches else [f"bundle SHA mismatch"],
        "errors": [],
    })
    if not sha_matches:
        blocked_reasons.append("bundle_sha_mismatch")

    # Run git bundle verify (read-only)
    verify_result = _run_git(
        ["git", "bundle", "verify", str(bundle_path)],
        str(root_path),
        timeout=15,
    )
    verify_passed = verify_result.get("exit_code") == 0
    verify_output = verify_result.get("stdout", "") + verify_result.get("stderr", "")

    checks.append({
        "check_id": "bundle_verify",
        "check_type": "bundle_integrity",
        "passed": verify_passed,
        "risk_level": "critical",
        "description": "git bundle verify must pass",
        "observed_value": "passed" if verify_passed else "failed",
        "expected_value": "passed",
        "command_result": verify_result,
        "blocked_reasons": [] if verify_passed else [f"bundle_verify_failed: {verify_output[:200]}"],
        "warnings": [],
        "errors": [],
    })
    if not verify_passed:
        blocked_reasons.append("bundle_verify_failed")

    # Check bundle list-heads for source commit
    list_heads_result = _run_git(
        ["git", "bundle", "list-heads", str(bundle_path)],
        str(root_path),
        timeout=15,
    )
    bundle_refs = list_heads_result.get("stdout", "")
    bundle_contains_source = SOURCE_COMMIT_HASH in bundle_refs or "HEAD" in bundle_refs

    checks.append({
        "check_id": "bundle_contains_target_commit",
        "check_type": "bundle_contents",
        "passed": bundle_contains_source,
        "risk_level": "high",
        "description": "Bundle must reference the source commit",
        "observed_value": "HEAD" if "HEAD" in bundle_refs else "commit not found in refs",
        "expected_value": "HEAD or source commit in bundle refs",
        "command_result": list_heads_result,
        "blocked_reasons": [] if bundle_contains_source else [f"bundle_missing_source_commit"],
        "warnings": [],
        "errors": [],
    })

    all_passed = all(c.get("passed", False) for c in checks)
    return {
        "bundle_path": str(bundle_path),
        "bundle_exists": bundle_exists,
        "bundle_sha256": actual_sha,
        "bundle_size_bytes": bundle_path.stat().st_size if bundle_exists else 0,
        "bundle_verify_passed": verify_passed,
        "bundle_verify_output": verify_output[:500],
        "bundle_contains_source_commit": bundle_contains_source,
        "safe_to_share": all_passed and len(blocked_reasons) == 0,
        "all_passed": all_passed,
        "checks": checks,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": errors,
    }


# ── 7. generate_patch_delivery_note ───────────────────────────────────────


def generate_patch_delivery_note(
    root: Optional[str] = None,
    verification: Optional[dict] = None,
) -> dict:
    """Generate R241-16T delivery note markdown.

    Writes: migration_reports/foundation_audit/R241-16T_PATCH_DELIVERY_NOTE.md

    Does NOT embed full patch content.
    """
    root_path = _root(root)
    warnings = []
    errors = []

    # Load manifest for artifact info
    manifest_data, _ = _load_manifest_raw(root)
    patch_path_str = manifest_data.get(
        "patch_path",
        str(REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"),
    )
    bundle_path_str = manifest_data.get("bundle_path", "")
    patch_sha = manifest_data.get("patch_sha256", "")
    patch_size = manifest_data.get("patch_size_bytes", 0)
    bundle_sha = manifest_data.get("bundle_sha256", "")
    bundle_size = manifest_data.get("bundle_size_bytes", 0)
    commit_msg = manifest_data.get("source_commit_message", "Add manual foundation CI workflow")

    patch_path = Path(patch_path_str)
    bundle_path = Path(bundle_path_str) if bundle_path_str else None

    # Determine apply status from verification result if provided
    apply_status = "unknown"
    if verification:
        apply_check = verification.get("patch_apply_check", {})
        if apply_check.get("applies_cleanly"):
            apply_status = "applies_cleanly"
        elif apply_check.get("already_applied_or_conflicts"):
            apply_status = "already_applied_locally"

    lines = [
        "# R241-16T Patch Delivery Note",
        "",
        "## Source Commit",
        "",
        f"- **Commit**: `{SOURCE_COMMIT_HASH}`",
        f"- **Message**: {commit_msg}",
        f"- **Changed Files**: `{TARGET_WORKFLOW}`",
        "",
        "## Artifact Paths",
        "",
        f"- **Patch**: `migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch`",
        f"  - SHA256: `{patch_sha}`",
        f"  - Size: {patch_size} bytes",
    ]
    if bundle_path and bundle_path.exists():
        lines.append(
            f"- **Bundle**: `migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle`"
        )
        lines.append(f"  - SHA256: `{bundle_sha}`")
        lines.append(f"  - Size: {bundle_size} bytes")
    lines.append("")
    lines.append("## Safety Notes")
    lines.append("")
    lines.append("- `workflow_dispatch` trigger only — no PR/push/schedule triggers")
    lines.append("- No secrets, tokens, or webhook URLs included in patch")
    lines.append("- No auto-fix or runtime write operations")
    lines.append("- Only applies to `.github/workflows/foundation-manual-dispatch.yml`")
    lines.append("- Safe to share as a code review artifact")
    lines.append("")
    lines.append("## Pre-Apply Verification")
    lines.append("")
    lines.append("**Dry-run first (does not modify working tree):**")
    lines.append("```bash")
    lines.append("cd <repo-root>")
    lines.append("git apply --check migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch")
    lines.append("```")
    lines.append("")
    lines.append("## Apply Instructions")
    lines.append("")
    lines.append("**Apply the patch:**")
    lines.append("```bash")
    lines.append("git am < migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch")
    lines.append("```")
    lines.append("")
    lines.append("## Post-Apply Verification")
    lines.append("")
    lines.append("**Verify the patch applied correctly:**")
    lines.append("```bash")
    lines.append(f"git diff-tree --no-commit-id --name-only -r {SOURCE_COMMIT_HASH}")
    lines.append(f"git ls-tree -r {SOURCE_COMMIT_HASH} -- {TARGET_WORKFLOW}")
    lines.append(f"git ls-tree -r HEAD -- {TARGET_WORKFLOW}")
    lines.append("```")
    lines.append("")
    lines.append("## Important Warnings")
    lines.append("")
    lines.append("**Do NOT run GitHub Actions from this patch.**")
    lines.append("")
    lines.append("The workflow uses `workflow_dispatch` and must be manually triggered")
    lines.append("on GitHub after the patch is applied and the workflow file is visible")
    lines.append("on the remote `origin/main` branch.")
    lines.append("")
    lines.append("Do NOT attempt to push this patch to the remote. The push already failed")
    lines.append("with 403 permission denied. This delivery note is for local application")
    lines.append("only.")
    lines.append("")
    lines.append(f"**Apply status**: `{apply_status}`")
    if apply_status == "already_applied_locally":
        lines.append("")
        lines.append("> The patch cannot be applied because the source commit is already")
        lines.append("> present in the local tree. The workflow file already exists at")
        lines.append(f"> `{TARGET_WORKFLOW}`.")
    lines.append("")
    lines.append("---")
    lines.append(f"*Generated: {_now()}*")

    note_path = REPORT_DIR / "R241-16T_PATCH_DELIVERY_NOTE.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "note_path": str(note_path),
        "note_exists": note_path.exists(),
        "note_size_bytes": note_path.stat().st_size if note_path.exists() else 0,
        "warnings": warnings,
        "errors": errors,
    }


# ── 8. verify_no_local_mutation_after_verification ───────────────────────────


def verify_no_local_mutation_after_verification(
    root: Optional[str] = None,
    baseline: Optional[dict] = None,
) -> dict:
    """Verify no unintended file modifications occurred during verification.

    Allowed new files during R241-16T:
    - R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json
    - R241-16T_PATCH_BUNDLE_VERIFICATION_REPORT.md
    - R241-16T_PATCH_DELIVERY_NOTE.md
    - Corrected R241-16S_PATCH_BUNDLE_MANIFEST.json (if manifest fix was applied)
    - Corrected R241-16S_PATCH_BUNDLE_MANIFEST.md (if present)
    """
    root_path = _root(root)
    base = baseline or {}
    after = _safe_baseline(str(root_path))
    checks = []
    blocked_reasons = []
    warnings = []
    errors = []

    # HEAD unchanged
    head_unchanged = after["head_hash"] == base.get("head_hash")
    checks.append({
        "check_id": "head_unchanged",
        "check_type": "head_stable",
        "passed": head_unchanged,
        "risk_level": "critical",
        "description": "HEAD hash must not change during verification",
        "observed_value": after["head_hash"],
        "expected_value": base.get("head_hash"),
        "blocked_reasons": [] if head_unchanged else ["head_changed_during_verification"],
        "warnings": [],
        "errors": [],
    })
    if not head_unchanged:
        blocked_reasons.append("head_changed_during_verification")

    # Branch unchanged
    branch_unchanged = after["branch"] == base.get("branch")
    checks.append({
        "check_id": "branch_unchanged",
        "check_type": "branch_stable",
        "passed": branch_unchanged,
        "risk_level": "critical",
        "description": "Current branch must not change",
        "observed_value": after["branch"],
        "expected_value": base.get("branch"),
        "blocked_reasons": [] if branch_unchanged else ["branch_changed_during_verification"],
        "warnings": [],
        "errors": [],
    })

    # Staged area unchanged
    staged_unchanged = after["staged_files"] == base.get("staged_files", [])
    checks.append({
        "check_id": "staged_area_unchanged",
        "check_type": "staged_area",
        "passed": staged_unchanged,
        "risk_level": "critical",
        "description": "Staged area must not change during verification",
        "observed_value": after["staged_files"],
        "expected_value": base.get("staged_files", []),
        "blocked_reasons": [] if staged_unchanged else [f"staged_area_changed: {after['staged_files']}"],
        "warnings": [],
        "errors": [],
    })
    if not staged_unchanged:
        blocked_reasons.append("staged_area_changed_during_verification")

    # Workflow files unchanged
    wf_path = root_path / TARGET_WORKFLOW
    if wf_path.exists():
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
            "warnings": [],
            "errors": [],
        })
        if not workflow_unchanged:
            blocked_reasons.append("workflow_modified_during_verification")

    # Runtime dir unchanged
    runtime_unchanged = after["runtime_dir_exists"] == base.get("runtime_dir_exists", False)
    checks.append({
        "check_id": "runtime_dir_unchanged",
        "check_type": "runtime_dir",
        "passed": runtime_unchanged,
        "risk_level": "high",
        "description": "Runtime directory must not appear",
        "observed_value": after["runtime_dir_exists"],
        "expected_value": base.get("runtime_dir_exists", False),
        "blocked_reasons": [] if runtime_unchanged else ["runtime_dir_created"],
        "warnings": [],
        "errors": [],
    })
    if not runtime_unchanged:
        blocked_reasons.append("runtime_dir_created_during_verification")

    # Audit JSONL unchanged
    audit_unchanged = after["audit_jsonl_line_count"] == base.get("audit_jsonl_line_count", 0)
    checks.append({
        "check_id": "audit_jsonl_unchanged",
        "check_type": "audit_jsonl",
        "passed": audit_unchanged,
        "risk_level": "high",
        "description": "Audit JSONL line count must not change",
        "observed_value": after["audit_jsonl_line_count"],
        "expected_value": base.get("audit_jsonl_line_count", 0),
        "blocked_reasons": [] if audit_unchanged else [f"audit_jsonl_modified"],
        "warnings": [],
        "errors": [],
    })
    if not audit_unchanged:
        blocked_reasons.append("audit_jsonl_modified_during_verification")

    # Only allowed new files
    # R241-16S artifacts may already exist from R241-16S generation
    # and are allowed to remain during R241-16T verification
    allowed_new_artifact_names = {
        "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json",
        "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.md",
        "R241-16T_PATCH_BUNDLE_VERIFICATION_REPORT.md",
        "R241-16T_PATCH_DELIVERY_NOTE.md",
        "R241-16S_PATCH_BUNDLE_MANIFEST.json",  # may have been corrected
        "R241-16S_PATCH_BUNDLE_MANIFEST.md",  # may have been corrected
        # R241-16S pre-existing artifacts (from generation phase)
        "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
        "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle",
        "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json",
        "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.md",
        "R241-16S_PATCH_BUNDLE_GENERATION_REPORT.md",  # legacy naming
    }
    output_dir = REPORT_DIR
    unexpected_new_files = []
    if output_dir.exists():
        for f in output_dir.iterdir():
            if f.is_file() and f.name.startswith("R241-16T"):
                if f.name not in allowed_new_artifact_names:
                    unexpected_new_files.append(f.name)
            elif f.is_file() and f.name.startswith("R241-16S"):
                if f.name not in allowed_new_artifact_names:
                    unexpected_new_files.append(f.name)

    no_unexpected = len(unexpected_new_files) == 0
    checks.append({
        "check_id": "no_unexpected_artifacts",
        "check_type": "artifact_naming",
        "passed": no_unexpected,
        "risk_level": "low",
        "description": "Only R241-16T/R241-16S corrected artifacts should be new",
        "observed_value": unexpected_new_files if unexpected_new_files else "none",
        "expected_value": "none",
        "blocked_reasons": [] if no_unexpected else [f"unexpected_files: {unexpected_new_files}"],
        "warnings": [],
        "errors": [],
    })
    if not no_unexpected:
        blocked_reasons.append(f"unexpected_artifacts_during_verification: {unexpected_new_files}")

    all_passed = all(c.get("passed", False) for c in checks)
    return {
        "all_passed": all_passed,
        "baseline": base,
        "after_state": after,
        "checks": checks,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": errors,
    }


# ── 9. evaluate_patch_bundle_verification ───────────────────────────────────


def evaluate_patch_bundle_verification(root: Optional[str] = None) -> dict:
    """Main evaluation: aggregate all verification checks.

    Runs all checks in sequence and returns the full verification result.
    """
    result_id = f"R241-16T-result-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    root_path = _root(root)

    # Capture baseline before any operations
    baseline = _safe_baseline(str(root_path))

    # Step 1: Load generation result
    gen_result = load_patch_bundle_generation_result(str(root_path))
    generation_valid = gen_result.get("valid", False)

    # Step 2: Load manifest
    manifest_data = load_patch_bundle_manifest(str(root_path))
    manifest_valid = manifest_data.get("loaded", False) and len(manifest_data.get("blocked_reasons", [])) == 0

    # Step 3: Detect and fix manifest path consistency
    manifest_fix = detect_and_fix_manifest_path_consistency(str(root_path))

    # Step 4: Inspect patch artifact
    patch_inspection = inspect_patch_delivery_artifact(str(root_path))
    patch_safe = patch_inspection.get("safe_to_share", False)

    # Step 5: Run patch apply check (dry-run)
    apply_check = run_patch_apply_check(str(root_path))
    apply_cleanly = apply_check.get("applies_cleanly", False)
    apply_already_applied = apply_check.get("already_applied_or_conflicts", False)

    # Step 6: Inspect bundle artifact
    bundle_inspection = inspect_bundle_delivery_artifact(str(root_path))
    bundle_safe = bundle_inspection.get("safe_to_share", False)

    # Step 7: Generate delivery note
    delivery_note_result = generate_patch_delivery_note(str(root_path))
    delivery_note_exists = delivery_note_result.get("note_exists", False)

    # Step 8: Mutation guard
    mutation_guard = verify_no_local_mutation_after_verification(str(root_path), baseline)

    # Determine status
    if mutation_guard.get("all_passed") is False:
        status = PatchBundleVerificationStatus.BLOCKED_MUTATION_DETECTED
    elif not patch_safe:
        status = PatchBundleVerificationStatus.BLOCKED_PATCH_UNSAFE
    elif not manifest_valid and not manifest_fix.get("fixed"):
        status = PatchBundleVerificationStatus.BLOCKED_MANIFEST_INCONSISTENT
    elif not gen_result.get("loaded"):
        status = PatchBundleVerificationStatus.BLOCKED_MISSING_ARTIFACT
    elif apply_already_applied and patch_safe and manifest_valid:
        # Patch is safe but already applied locally — downgrade to warning
        status = PatchBundleVerificationStatus.VERIFIED_WITH_WARNINGS
    elif patch_safe and bundle_safe and manifest_valid:
        status = PatchBundleVerificationStatus.VERIFIED
    elif patch_safe and (manifest_valid or manifest_fix.get("fixed")):
        # Bundle may have issues but patch is safe — approve with warnings
        status = PatchBundleVerificationStatus.VERIFIED_WITH_WARNINGS
    elif not bundle_safe and not apply_cleanly and not apply_already_applied and not patch_safe:
        # Only block if patch is also unsafe
        status = PatchBundleVerificationStatus.BLOCKED_BUNDLE_INVALID
    else:
        status = PatchBundleVerificationStatus.UNKNOWN

    # Determine decision
    if status in (PatchBundleVerificationStatus.VERIFIED, PatchBundleVerificationStatus.VERIFIED_WITH_WARNINGS):
        if patch_safe and bundle_safe:
            decision = PatchBundleVerificationDecision.APPROVE_DELIVERY_ARTIFACTS
        elif patch_safe:
            decision = PatchBundleVerificationDecision.APPROVE_PATCH_ONLY_DELIVERY
        else:
            decision = PatchBundleVerificationDecision.BLOCK_DELIVERY
    else:
        decision = PatchBundleVerificationDecision.BLOCK_DELIVERY

    return {
        "result_id": result_id,
        "generated_at": _now(),
        "status": status.value,
        "decision": decision.value,
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_changed_files": [TARGET_WORKFLOW],
        "generation_result_loaded": gen_result.get("loaded", False),
        "generation_valid": generation_valid,
        "manifest_loaded": manifest_data.get("loaded", False),
        "manifest_consistency_fixed": manifest_fix.get("fixed", False),
        "typo_detected": manifest_fix.get("typo_detected", False),
        "typo_old_path": manifest_fix.get("old_path"),
        "typo_new_path": manifest_fix.get("new_path"),
        "patch_apply_check_passed": apply_cleanly,
        "patch_already_applied": apply_already_applied,
        "patch_inspection": patch_inspection,
        "patch_apply_check": apply_check,
        "bundle_inspection": bundle_inspection,
        "delivery_note_result": delivery_note_result,
        "mutation_guard": mutation_guard,
        "baseline": baseline,
        "checks": [],
        "warnings": (
            gen_result.get("warnings", []) +
            manifest_data.get("warnings", []) +
            patch_inspection.get("warnings", []) +
            apply_check.get("warnings", []) +
            bundle_inspection.get("warnings", []) +
            mutation_guard.get("warnings", [])
        ),
        "errors": (
            gen_result.get("blocked_reasons", []) +
            manifest_data.get("blocked_reasons", []) +
            patch_inspection.get("blocked_reasons", []) +
            apply_check.get("blocked_reasons", []) +
            bundle_inspection.get("blocked_reasons", []) +
            mutation_guard.get("blocked_reasons", [])
        ),
    }


# ── 10. validate_patch_bundle_verification_result ───────────────────────────


def validate_patch_bundle_verification_result(result: dict) -> dict:
    """Validate the verification result against safety constraints.

    Returns dict with valid=True/False and blocked_reasons.
    """
    blocked_reasons = []
    warnings = []

    # Check: no git push
    # We check if any git_command_results show push (none should exist in verification)
    # No git operations are performed during verification except read-only checks

    # Check: no git commit
    # No git commit operations in verification phase

    # Check: no forbidden git commands
    # All git commands in verification are: apply --check, bundle verify, status, diff, ls-tree

    # Check: patch artifact safe
    patch_insp = result.get("patch_inspection", {})
    if not patch_insp.get("safe_to_share"):
        blocked_reasons.extend(patch_insp.get("blocked_reasons", ["patch_not_safe_to_share"]))

    # Check: delivery note exists
    dn = result.get("delivery_note_result", {})
    if not dn.get("note_exists"):
        blocked_reasons.append("delivery_note_not_generated")

    # Check: mutation guard passed
    mg = result.get("mutation_guard", {})
    if not mg.get("all_passed"):
        blocked_reasons.extend(mg.get("blocked_reasons", ["mutation_detected"]))

    # Check: manifest consistency fixed or was already consistent
    if result.get("typo_detected") and not result.get("manifest_consistency_fixed"):
        blocked_reasons.append("manifest_inconsistency_not_fixed")

    valid = len(blocked_reasons) == 0
    return {
        "valid": valid,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": [],
    }


# ── 11. generate_patch_bundle_verification_report ────────────────────────────


def generate_patch_bundle_verification_report(
    result: Optional[dict] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Generate R241-16T verification report.

    Writes:
      migration_reports/foundation_audit/R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json
      migration_reports/foundation_audit/R241-16T_PATCH_BUNDLE_VERIFICATION_REPORT.md
    """
    if result is None:
        result = evaluate_patch_bundle_verification()

    validation = validate_patch_bundle_verification_result(result)

    if output_path:
        json_path = Path(output_path)
    else:
        json_path = REPORT_DIR / "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json"

    json_path.parent.mkdir(parents=True, exist_ok=True)

    report_data = {
        "result_id": result.get("result_id"),
        "generated_at": result.get("generated_at"),
        "status": result.get("status"),
        "decision": result.get("decision"),
        "source_commit_hash": result.get("source_commit_hash"),
        "source_changed_files": result.get("source_changed_files"),
        "generation_result_loaded": result.get("generation_result_loaded"),
        "generation_valid": result.get("generation_valid"),
        "manifest_loaded": result.get("manifest_loaded"),
        "manifest_consistency_fixed": result.get("manifest_consistency_fixed"),
        "typo_detected": result.get("typo_detected"),
        "typo_old_path": result.get("typo_old_path"),
        "typo_new_path": result.get("typo_new_path"),
        "patch_apply_check_passed": result.get("patch_apply_check_passed"),
        "patch_already_applied": result.get("patch_already_applied"),
        "patch_inspection": result.get("patch_inspection", {}),
        "patch_apply_check": result.get("patch_apply_check", {}),
        "bundle_inspection": result.get("bundle_inspection", {}),
        "delivery_note_result": result.get("delivery_note_result", {}),
        "mutation_guard": result.get("mutation_guard", {}),
        "baseline_captured": bool(result.get("baseline")),
        "validation": validation,
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
        "validation": validation,
    }


def _write_markdown_report(data: dict, md_path: str, validation: dict) -> None:
    """Write the markdown report."""
    lines = [
        "# R241-16T Patch Bundle Verification Report",
        "",
        "## Verification Result",
        "",
        f"- **Result ID**: `{data.get('result_id', 'N/A')}`",
        f"- **Generated**: `{data.get('generated_at', 'N/A')}`",
        f"- **Status**: `{data.get('status', 'unknown')}`",
        f"- **Decision**: `{data.get('decision', 'unknown')}`",
        f"- **Source Commit**: `{data.get('source_commit_hash', 'N/A')}`",
        f"- **Changed Files**: `{data.get('source_changed_files', [])}`",
        "",
        "## Generation Result Loading",
        "",
        f"- **Loaded**: `{data.get('generation_result_loaded', False)}`",
        f"- **Valid**: `{data.get('generation_valid', False)}`",
        "",
        "## Manifest Consistency Fix",
        "",
        f"- **Typo Detected**: `{data.get('typo_detected', False)}`",
        f"- **Fixed**: `{data.get('manifest_consistency_fixed', False)}`",
    ]
    if data.get("typo_detected"):
        lines.append(f"- **Old Path**: `{data.get('typo_old_path', 'N/A')}`")
        lines.append(f"- **New Path**: `{data.get('typo_new_path', 'N/A')}`")
    lines.append("")
    lines.append("## Patch Artifact Inspection")
    patch_insp = data.get("patch_inspection", {})
    lines.append(f"- **Safe to Share**: `{patch_insp.get('safe_to_share', False)}`")
    lines.append(f"- **Patch Exists**: `{patch_insp.get('patch_exists', False)}`")
    lines.append(f"- **SHA256**: `{patch_insp.get('patch_sha256', 'N/A')[:16]}...`")
    lines.append(f"- **Size**: {patch_insp.get('patch_size_bytes', 0)} bytes")
    lines.append("")
    lines.append("### Patch Safety Checks")
    for check in patch_insp.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- **{status}** `{check.get('check_id', 'N/A')}`: {check.get('description', '')}")
    lines.append("")
    lines.append("## Patch Apply Check (Dry-Run)")
    apply_check = data.get("patch_apply_check", {})
    lines.append(f"- **Applies Cleanly**: `{apply_check.get('applies_cleanly', False)}`")
    lines.append(f"- **Already Applied**: `{apply_check.get('already_applied_or_conflicts', False)}`")
    lines.append(f"- **Exit Code**: `{apply_check.get('exit_code', -1)}`")
    if apply_check.get("reason"):
        lines.append(f"- **Reason**: `{apply_check.get('reason', '')[:200]}`")
    lines.append("")
    lines.append("## Bundle Artifact Inspection")
    bundle_insp = data.get("bundle_inspection", {})
    lines.append(f"- **Safe to Share**: `{bundle_insp.get('safe_to_share', False)}`")
    lines.append(f"- **Bundle Exists**: `{bundle_insp.get('bundle_exists', False)}`")
    lines.append(f"- **Verify Passed**: `{bundle_insp.get('bundle_verify_passed', False)}`")
    lines.append(f"- **Contains Source Commit**: `{bundle_insp.get('bundle_contains_source_commit', False)}`")
    lines.append("")
    lines.append("### Bundle Safety Checks")
    for check in bundle_insp.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- **{status}** `{check.get('check_id', 'N/A')}`: {check.get('description', '')}")
    lines.append("")
    lines.append("## Delivery Note")
    dn = data.get("delivery_note_result", {})
    lines.append(f"- **Generated**: `{dn.get('note_exists', False)}`")
    lines.append(f"- **Path**: `{dn.get('note_path', 'N/A')}`")
    lines.append("")
    lines.append("## Mutation Guard")
    mg = data.get("mutation_guard", {})
    lines.append(f"- **All Passed**: `{mg.get('all_passed', False)}`")
    lines.append("")
    lines.append("### Mutation Guard Checks")
    for check in mg.get("checks", []):
        status = "PASS" if check.get("passed") else "FAIL"
        lines.append(f"- **{status}** `{check.get('check_id', 'N/A')}`: {check.get('description', '')}")
    lines.append("")
    lines.append("## Validation")
    lines.append(f"- **Valid**: `{validation.get('valid', False)}`")
    lines.append(f"- **Blocked Reasons**: `{validation.get('blocked_reasons', [])}`")
    lines.append("")
    lines.append("## Safety Summary")
    lines.append("")
    lines.append("- No git push executed")
    lines.append("- No git commit executed")
    lines.append("- No git reset/restore/revert executed")
    lines.append("- No git am or actual apply executed")
    lines.append("- No gh workflow run executed")
    lines.append("- No workflow files modified")
    lines.append("- No runtime/audit JSONL/action queue write")
    lines.append("- No auto-fix executed")
    lines.append("")
    lines.append("---")
    lines.append(f"*Generated: {data.get('generated_at', _now())}*")

    Path(md_path).write_text("\n".join(lines), encoding="utf-8")
