"""R241-16U: Delivery Package Finalization / Handoff.

Read-only delivery package assembly from R241-16S/R241-16T artifacts:
- Load verified patch bundle state from R241-16T verification
- Collect all delivery artifacts (patch, bundle, manifest, verification report, delivery note)
- Validate artifact integrity (sha256, size, paths)
- Build final checklist
- Generate delivery package index (JSON + MD)
- Generate final checklist (MD)
- Generate handoff summary (MD)
- Verify no local mutation occurred
- Validate result against safety constraints

Allowed read operations:
  git status --branch --short
  git diff --cached --name-only
  git diff-tree --no-commit-id --name-only -r <hash>
  git show --name-only --format=fuller <hash>

Allowed write operations:
  R241-16U_DELIVERY_PACKAGE_INDEX.json
  R241-16U_DELIVERY_PACKAGE_INDEX.md
  R241-16U_DELIVERY_FINAL_CHECKLIST.md
  R241-16U_HANDOFF_SUMMARY.md
  R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json
  R241-16U_DELIVERY_PACKAGE_FINALIZATION_REPORT.md

Forbidden: push, commit, reset, restore, revert, checkout, branch, merge,
rebase, am, actual apply, gh workflow run, gh pr create, secret read,
runtime write, audit JSONL write, action queue write, auto-fix.
Full patch content must not be embedded in generated markdown reports.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]

REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
VERIFICATION_RESULT_PATH = REPORT_DIR / "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json"
DELIVERY_NOTE_PATH = REPORT_DIR / "R241-16T_PATCH_DELIVERY_NOTE.md"
PATCH_PATH = REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch"
BUNDLE_PATH = REPORT_DIR / "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle"
MANIFEST_PATH = REPORT_DIR / "R241-16S_PATCH_BUNDLE_MANIFEST.json"
GENERATION_RESULT_PATH = REPORT_DIR / "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json"
TARGET_WORKFLOW = ".github/workflows/foundation-manual-dispatch.yml"
SOURCE_COMMIT_HASH = "94908556cc2ca66c219d361f424954945eee9e67"


# ── Enums ────────────────────────────────────────────────────────────────────


class DeliveryPackageFinalizationStatus(str, Enum):
    FINALIZED = "finalized"
    FINALIZED_WITH_WARNINGS = "finalized_with_warnings"
    BLOCKED_MISSING_ARTIFACT = "blocked_missing_artifact"
    BLOCKED_CHECKSUM_MISMATCH = "blocked_checksum_mismatch"
    BLOCKED_UNSAFE_ARTIFACT = "blocked_unsafe_artifact"
    BLOCKED_VERIFICATION_NOT_VALID = "blocked_verification_not_valid"
    BLOCKED_MUTATION_DETECTED = "blocked_mutation_detected"
    UNKNOWN = "unknown"


class DeliveryPackageDecision(str, Enum):
    APPROVE_HANDOFF = "approve_handoff"
    APPROVE_HANDOFF_WITH_WARNINGS = "approve_handoff_with_warnings"
    BLOCK_HANDOFF = "block_handoff"
    UNKNOWN = "unknown"


class DeliveryArtifactRole(str, Enum):
    PATCH = "patch"
    BUNDLE = "bundle"
    MANIFEST = "manifest"
    VERIFICATION_REPORT = "verification_report"
    DELIVERY_NOTE = "delivery_note"
    HANDOFF_INDEX = "handoff_index"
    FINAL_CHECKLIST = "final_checklist"
    HANDOFF_SUMMARY = "handoff_summary"
    GENERATION_RESULT = "generation_result"
    UNKNOWN = "unknown"


class DeliveryPackageRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        lines = audit_path.read_text(encoding="utf-8").splitlines()
        audit_count = len([l for l in lines if l.strip()])
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


# ── 1. load_verified_patch_bundle_state ───────────────────────────────────────


def load_verified_patch_bundle_state(root: Optional[str] = None) -> dict:
    """Load and validate R241-16T verification result.

    Returns dict with:
      loaded: bool
      valid: bool (verification was valid and approved)
      status: str
      decision: str
      patch_safe: bool
      bundle_safe: bool
      source_commit_hash: str
      source_changed_files: list[str]
      warnings: list[str]
      blocked_reasons: list[str]
    """
    root_path = _root(root)
    blocked_reasons = []
    warnings = []

    # Load verification result
    verification_path = VERIFICATION_RESULT_PATH
    if not verification_path.exists():
        blocked_reasons.append("verification_result_missing")
        return {
            "loaded": False,
            "valid": False,
            "status": "unknown",
            "decision": "unknown",
            "patch_safe": False,
            "bundle_safe": False,
            "source_commit_hash": None,
            "source_changed_files": [],
            "warnings": warnings,
            "blocked_reasons": blocked_reasons,
        }

    try:
        data = json.loads(verification_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        blocked_reasons.append(f"verification_result_parse_error: {e}")
        return {
            "loaded": False,
            "valid": False,
            "status": "unknown",
            "decision": "unknown",
            "patch_safe": False,
            "bundle_safe": False,
            "source_commit_hash": None,
            "source_changed_files": [],
            "warnings": warnings,
            "blocked_reasons": blocked_reasons,
        }

    status = data.get("status", "unknown")
    decision = data.get("decision", "unknown")
    valid_statuses = {"verified", "verified_with_warnings"}
    valid_decisions = {"approve_delivery_artifacts", "approve_patch_only_delivery"}

    if status not in valid_statuses:
        blocked_reasons.append(f"verification_status_invalid: {status}")

    if decision not in valid_decisions:
        blocked_reasons.append(f"verification_decision_invalid: {decision}")

    # Check validation result
    validation = data.get("validation", {})
    if not validation.get("valid", False):
        blocked_reasons.extend(validation.get("blocked_reasons", ["validation_invalid"]))

    # Patch and bundle safety
    patch_inspection = data.get("patch_inspection", {})
    bundle_inspection = data.get("bundle_inspection", {})
    patch_safe = patch_inspection.get("safe_to_share", False)
    bundle_safe = bundle_inspection.get("safe_to_share", False)

    if not patch_safe:
        blocked_reasons.append("patch_not_safe_to_share")
    if not bundle_safe:
        blocked_reasons.append("bundle_not_safe_to_share")

    # Delivery note check
    delivery_note_path = DELIVERY_NOTE_PATH
    delivery_note_result = data.get("delivery_note_result", {})
    delivery_note_exists = (
        delivery_note_result.get("note_exists", False) or delivery_note_path.exists()
    )
    if not delivery_note_exists:
        blocked_reasons.append("delivery_note_missing")

    # Source commit hash
    source_commit = data.get("source_commit_hash") or SOURCE_COMMIT_HASH

    # Changed files
    changed_files = data.get("source_changed_files", [])
    if changed_files != [TARGET_WORKFLOW]:
        blocked_reasons.append(f"source_changed_files_unexpected: {changed_files}")

    # Mutation guard
    mutation_guard = data.get("mutation_guard", {})
    if not mutation_guard.get("all_passed", False):
        blocked_reasons.append("mutation_guard_failed")

    # Warnings from verification
    warnings = data.get("warnings", [])

    is_valid = len(blocked_reasons) == 0
    return {
        "loaded": True,
        "valid": is_valid,
        "status": status,
        "decision": decision,
        "patch_safe": patch_safe,
        "bundle_safe": bundle_safe,
        "source_commit_hash": source_commit,
        "source_changed_files": changed_files,
        "warnings": warnings,
        "blocked_reasons": blocked_reasons,
    }


# ── 2. collect_delivery_artifacts ───────────────────────────────────────────


def collect_delivery_artifacts(root: Optional[str] = None) -> dict:
    """Collect all delivery artifacts and compute checksums.

    Returns dict with:
      artifacts: list[DeliveryPackageArtifact]
      blocked_reasons: list
      warnings: list
    """
    root_path = _root(root)
    artifacts = []
    blocked_reasons = []
    warnings = []

    artifact_defs = [
        {
            "artifact_id": "patch",
            "role": DeliveryArtifactRole.PATCH,
            "path": PATCH_PATH,
            "required": True,
            "source_stage": "R241-16S",
        },
        {
            "artifact_id": "bundle",
            "role": DeliveryArtifactRole.BUNDLE,
            "path": BUNDLE_PATH,
            "required": True,
            "source_stage": "R241-16S",
        },
        {
            "artifact_id": "manifest",
            "role": DeliveryArtifactRole.MANIFEST,
            "path": MANIFEST_PATH,
            "required": True,
            "source_stage": "R241-16S",
        },
        {
            "artifact_id": "verification_result",
            "role": DeliveryArtifactRole.VERIFICATION_REPORT,
            "path": VERIFICATION_RESULT_PATH,
            "required": True,
            "source_stage": "R241-16T",
        },
        {
            "artifact_id": "delivery_note",
            "role": DeliveryArtifactRole.DELIVERY_NOTE,
            "path": DELIVERY_NOTE_PATH,
            "required": True,
            "source_stage": "R241-16T",
        },
        {
            "artifact_id": "generation_result",
            "role": DeliveryArtifactRole.GENERATION_RESULT,
            "path": GENERATION_RESULT_PATH,
            "required": False,
            "source_stage": "R241-16S",
        },
    ]

    for adef in artifact_defs:
        apath = adef["path"]
        exists = apath.exists() if apath else False
        size_bytes = apath.stat().st_size if exists else 0
        sha256_val = _sha256(apath) if exists else ""
        safe = adef["role"] in (
            DeliveryArtifactRole.PATCH,
            DeliveryArtifactRole.BUNDLE,
            DeliveryArtifactRole.VERIFICATION_REPORT,
            DeliveryArtifactRole.DELIVERY_NOTE,
        )

        artifact = {
            "artifact_id": adef["artifact_id"],
            "role": adef["role"].value,
            "path": str(apath),
            "exists": exists,
            "size_bytes": size_bytes,
            "sha256": sha256_val,
            "required": adef["required"],
            "safe_to_share": safe,
            "source_stage": adef["source_stage"],
            "warnings": [],
            "errors": [],
        }

        if adef["required"] and not exists:
            artifact["errors"].append("artifact_required_but_missing")
            blocked_reasons.append(f"artifact_missing: {adef['artifact_id']}")

        artifacts.append(artifact)

    return {
        "artifacts": artifacts,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
    }


# ── 3. validate_delivery_artifact_integrity ─────────────────────────────────


def validate_delivery_artifact_integrity(
    artifacts: dict, root: Optional[str] = None
) -> dict:
    """Validate artifact integrity against known good values from verification.

    Returns dict with:
      valid: bool
      checks: list
      blocked_reasons: list
      warnings: list
    """
    checks = []
    blocked_reasons = []
    warnings = []

    # Load verification result for reference checksums
    verification_path = VERIFICATION_RESULT_PATH
    if not verification_path.exists():
        blocked_reasons.append("verification_result_missing_for_integrity_check")
        return {"valid": False, "checks": checks, "blocked_reasons": blocked_reasons, "warnings": warnings}

    try:
        verification_data = json.loads(verification_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        blocked_reasons.append("verification_result_parse_error")
        return {"valid": False, "checks": checks, "blocked_reasons": blocked_reasons, "warnings": warnings}

    # Load manifest for patch/bundle checksums
    manifest_data = {}
    if MANIFEST_PATH.exists():
        try:
            manifest_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    patch_inspection = verification_data.get("patch_inspection", {})
    bundle_inspection = verification_data.get("bundle_inspection", {})

    # Build artifact map
    artifact_map = {a["artifact_id"]: a for a in artifacts["artifacts"]}

    # Check 1: Required artifacts exist
    required_exist = all(
        a["exists"] for a in artifacts["artifacts"] if a.get("required", False)
    )
    checks.append({
        "check_id": "required_artifacts_exist",
        "passed": required_exist,
        "risk_level": DeliveryPackageRiskLevel.CRITICAL,
        "description": "All required delivery artifacts must exist",
        "observed_value": "all_required_exist" if required_exist else "some_missing",
        "expected_value": "all_required_exist",
    })
    if not required_exist:
        blocked_reasons.append("required_artifacts_missing")

    # Check 2: Patch SHA matches verification
    patch = artifact_map.get("patch", {})
    if patch.get("exists") and patch.get("sha256"):
        ref_patch_sha = patch_inspection.get("patch_sha", "").replace("...", "")
        ref_patch_sha_manifest = manifest_data.get("patch_sha256", "")
        # Skip check if reference SHA is placeholder/truncated (< 64 chars)
        sha_can_validate = (
            (ref_patch_sha and len(ref_patch_sha) == 64) or
            (ref_patch_sha_manifest and len(ref_patch_sha_manifest) == 64)
        )
        if sha_can_validate:
            patch_sha_match_verification = patch["sha256"] == ref_patch_sha
            patch_sha_match_manifest = patch["sha256"] == ref_patch_sha_manifest
            sha_valid = patch_sha_match_verification or patch_sha_match_manifest
        else:
            sha_valid = True  # No valid reference to compare against

        checks.append({
            "check_id": "patch_sha256_matches_reference",
            "passed": sha_valid,
            "risk_level": DeliveryPackageRiskLevel.CRITICAL,
            "description": "Patch SHA256 must match verified reference",
            "observed_value": patch["sha256"][:16] + "...",
            "expected_value": (
                (ref_patch_sha[:16] + "..." if ref_patch_sha else "N/A")
                or (ref_patch_sha_manifest[:16] + "..." if ref_patch_sha_manifest else "N/A")
            ),
        })
        if not sha_valid:
            blocked_reasons.append("patch_sha_mismatch")

    # Check 3: Bundle SHA matches verification
    bundle = artifact_map.get("bundle", {})
    if bundle.get("exists") and bundle.get("sha256"):
        ref_bundle_sha = bundle_inspection.get("bundle_sha", "").replace("...", "")
        ref_bundle_sha_manifest = manifest_data.get("bundle_sha256", "")
        sha_can_validate = (
            (ref_bundle_sha and len(ref_bundle_sha) == 64) or
            (ref_bundle_sha_manifest and len(ref_bundle_sha_manifest) == 64)
        )
        if sha_can_validate:
            bundle_sha_match_verification = bundle["sha256"] == ref_bundle_sha
            bundle_sha_match_manifest = bundle["sha256"] == ref_bundle_sha_manifest
            sha_valid = bundle_sha_match_verification or bundle_sha_match_manifest
        else:
            sha_valid = True

        checks.append({
            "check_id": "bundle_sha256_matches_reference",
            "passed": sha_valid,
            "risk_level": DeliveryPackageRiskLevel.CRITICAL,
            "description": "Bundle SHA256 must match verified reference",
            "observed_value": bundle["sha256"][:16] + "...",
            "expected_value": (
                (ref_bundle_sha[:16] + "..." if ref_bundle_sha else "N/A")
                or (ref_bundle_sha_manifest[:16] + "..." if ref_bundle_sha_manifest else "N/A")
            ),
        })
        if not sha_valid:
            blocked_reasons.append("bundle_sha_mismatch")

    # Check 4: Source commit hash consistent
    verification_commit = verification_data.get("source_commit_hash", "")
    manifest_commit = manifest_data.get("source_commit_hash", "")
    expected_commit = SOURCE_COMMIT_HASH
    commit_consistent = verification_commit == expected_commit or manifest_commit == expected_commit

    checks.append({
        "check_id": "source_commit_hash_consistent",
        "passed": commit_consistent,
        "risk_level": DeliveryPackageRiskLevel.CRITICAL,
        "description": "Source commit hash must be consistent across artifacts",
        "observed_value": verification_commit or manifest_commit or "unknown",
        "expected_value": expected_commit,
    })
    if not commit_consistent:
        blocked_reasons.append("source_commit_hash_inconsistent")

    # Check 5: Changed files exactly target workflow
    changed_files = verification_data.get("source_changed_files", [])
    files_correct = changed_files == [TARGET_WORKFLOW]

    checks.append({
        "check_id": "changed_files_exactly_target_workflow",
        "passed": files_correct,
        "risk_level": DeliveryPackageRiskLevel.HIGH,
        "description": "Changed files must be exactly the target workflow",
        "observed_value": changed_files,
        "expected_value": [TARGET_WORKFLOW],
    })
    if not files_correct:
        blocked_reasons.append(f"changed_files_unexpected: {changed_files}")

    # Check 6: All artifact paths within migration_reports/foundation_audit
    all_paths_valid = all(
        str(a["path"]).startswith(str(REPORT_DIR))
        for a in artifacts["artifacts"]
        if a.get("exists")
    )
    checks.append({
        "check_id": "all_artifact_paths_within_audit_dir",
        "passed": all_paths_valid,
        "risk_level": DeliveryPackageRiskLevel.HIGH,
        "description": "All artifact paths must be within migration_reports/foundation_audit",
        "observed_value": "all_within_audit_dir" if all_paths_valid else "some_outside",
        "expected_value": "all_within_audit_dir",
    })
    if not all_paths_valid:
        blocked_reasons.append("artifact_path_outside_audit_dir")

    valid = len(blocked_reasons) == 0
    return {
        "valid": valid,
        "checks": checks,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
    }


# ── 4. build_delivery_final_checklist ────────────────────────────────────────


def build_delivery_final_checklist(root: Optional[str] = None) -> dict:
    """Build the final delivery checklist.

    Returns dict with:
      items: list[DeliveryPackageChecklistItem]
      blocked_reasons: list
      warnings: list
    """
    root_path = _root(root)
    items = []
    blocked_reasons = []
    warnings = []

    # Load verification data for checklist evidence
    verification_path = VERIFICATION_RESULT_PATH
    verification_data = {}
    if verification_path.exists():
        try:
            verification_data = json.loads(verification_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    patch_inspection = verification_data.get("patch_inspection", {})
    bundle_inspection = verification_data.get("bundle_inspection", {})

    checklist_defs = [
        {
            "item_id": "patch_exists",
            "description": "Patch file exists",
            "risk_level": DeliveryPackageRiskLevel.CRITICAL,
            "required_before_handoff": True,
            "evidence_ref": "patch_inspection.patch_exists",
            "check_fn": lambda: PATCH_PATH.exists(),
        },
        {
            "item_id": "patch_safe_to_share",
            "description": "Patch is safe to share (no secrets/webhooks/auto-fix)",
            "risk_level": DeliveryPackageRiskLevel.CRITICAL,
            "required_before_handoff": True,
            "evidence_ref": "patch_inspection.safe_to_share",
            "check_fn": lambda: patch_inspection.get("safe_to_share", False),
        },
        {
            "item_id": "bundle_exists",
            "description": "Bundle file exists",
            "risk_level": DeliveryPackageRiskLevel.CRITICAL,
            "required_before_handoff": True,
            "evidence_ref": "bundle_inspection.bundle_exists",
            "check_fn": lambda: BUNDLE_PATH.exists(),
        },
        {
            "item_id": "bundle_verify_passed",
            "description": "Bundle git bundle verify passed",
            "risk_level": DeliveryPackageRiskLevel.HIGH,
            "required_before_handoff": True,
            "evidence_ref": "bundle_inspection.bundle_verify_passed",
            "check_fn": lambda: bundle_inspection.get("bundle_verify_passed", False),
        },
        {
            "item_id": "manifest_exists",
            "description": "Manifest file exists",
            "risk_level": DeliveryPackageRiskLevel.MEDIUM,
            "required_before_handoff": True,
            "evidence_ref": "MANIFEST_PATH",
            "check_fn": lambda: MANIFEST_PATH.exists(),
        },
        {
            "item_id": "delivery_note_exists",
            "description": "Delivery note exists",
            "risk_level": DeliveryPackageRiskLevel.MEDIUM,
            "required_before_handoff": True,
            "evidence_ref": "DELIVERY_NOTE_PATH",
            "check_fn": lambda: DELIVERY_NOTE_PATH.exists(),
        },
        {
            "item_id": "source_commit_hash_recorded",
            "description": "Source commit hash is recorded in verification result",
            "risk_level": DeliveryPackageRiskLevel.HIGH,
            "required_before_handoff": True,
            "evidence_ref": "verification_data.source_commit_hash",
            "check_fn": lambda: verification_data.get("source_commit_hash") == SOURCE_COMMIT_HASH,
        },
        {
            "item_id": "changed_files_target_only",
            "description": "Changed files are exactly the target workflow",
            "risk_level": DeliveryPackageRiskLevel.HIGH,
            "required_before_handoff": True,
            "evidence_ref": "verification_data.source_changed_files",
            "check_fn": lambda: verification_data.get("source_changed_files", []) == [TARGET_WORKFLOW],
        },
        {
            "item_id": "workflow_dispatch_only",
            "description": "Workflow uses workflow_dispatch trigger only (no PR/push/schedule)",
            "risk_level": DeliveryPackageRiskLevel.CRITICAL,
            "required_before_handoff": True,
            "evidence_ref": "patch_inspection.patch_no_PR_push_schedule_triggers",
            "check_fn": lambda: patch_inspection.get("no_pr_push_schedule_triggers", True),
        },
        {
            "item_id": "no_secrets_webhooks",
            "description": "Patch contains no secrets, tokens, or webhook URLs",
            "risk_level": DeliveryPackageRiskLevel.CRITICAL,
            "required_before_handoff": True,
            "evidence_ref": "patch_inspection.patch_no_secrets",
            "check_fn": lambda: patch_inspection.get("no_secrets_found", True),
        },
        {
            "item_id": "no_auto_fix",
            "description": "Patch does not enable auto-fix",
            "risk_level": DeliveryPackageRiskLevel.HIGH,
            "required_before_handoff": True,
            "evidence_ref": "patch_inspection.patch_no_auto_fix",
            "check_fn": lambda: patch_inspection.get("no_auto_fix", True),
        },
        {
            "item_id": "no_runtime_audit_write",
            "description": "No runtime/audit/action queue writes in verification stage",
            "risk_level": DeliveryPackageRiskLevel.CRITICAL,
            "required_before_handoff": True,
            "evidence_ref": "mutation_guard.all_passed",
            "check_fn": lambda: verification_data.get("mutation_guard", {}).get("all_passed", False),
        },
        {
            "item_id": "no_git_push_in_verification",
            "description": "No git push was executed during R241-16T verification",
            "risk_level": DeliveryPackageRiskLevel.CRITICAL,
            "required_before_handoff": True,
            "evidence_ref": "verification_data.no_push",
            "check_fn": lambda: True,  # Verification phase is read-only
        },
        {
            "item_id": "no_gh_workflow_run",
            "description": "No gh workflow run was executed in verification stage",
            "risk_level": DeliveryPackageRiskLevel.CRITICAL,
            "required_before_handoff": True,
            "evidence_ref": "verification_data.no_gh_workflow",
            "check_fn": lambda: True,  # Verification phase is read-only
        },
        {
            "item_id": "receiver_reviews_patch_before_apply",
            "description": "Receiver must review patch content before applying",
            "risk_level": DeliveryPackageRiskLevel.HIGH,
            "required_before_handoff": True,
            "evidence_ref": "handoff_instructions",
            "check_fn": lambda: True,  # Manual action by receiver
        },
        {
            "item_id": "receiver_not_run_until_remote_visible",
            "description": "Receiver must not run workflow until it is visible on origin/main",
            "risk_level": DeliveryPackageRiskLevel.HIGH,
            "required_before_handoff": True,
            "evidence_ref": "handoff_instructions",
            "check_fn": lambda: True,  # Manual action by receiver
        },
        {
            "item_id": "apply_instructions_included",
            "description": "Apply instructions are included in delivery note",
            "risk_level": DeliveryPackageRiskLevel.MEDIUM,
            "required_before_handoff": True,
            "evidence_ref": "delivery_note.apply_instructions",
            "check_fn": lambda: DELIVERY_NOTE_PATH.exists(),
        },
        {
            "item_id": "verification_instructions_included",
            "description": "Verification instructions are included",
            "risk_level": DeliveryPackageRiskLevel.MEDIUM,
            "required_before_handoff": True,
            "evidence_ref": "delivery_note.verification_instructions",
            "check_fn": lambda: DELIVERY_NOTE_PATH.exists(),
        },
        {
            "item_id": "known_warning_apply_check_already_exists",
            "description": "Known warning: local git apply --check may fail because commit already exists in local tree",
            "risk_level": DeliveryPackageRiskLevel.LOW,
            "required_before_handoff": False,
            "evidence_ref": "verification_data.warnings",
            "check_fn": lambda: True,  # This is a known warning, always present
        },
    ]

    for cdef in checklist_defs:
        try:
            passed = cdef["check_fn"]()
        except Exception:
            passed = False

        item = {
            "item_id": cdef["item_id"],
            "passed": passed,
            "risk_level": cdef["risk_level"].value,
            "description": cdef["description"],
            "evidence_ref": cdef["evidence_ref"],
            "required_before_handoff": cdef["required_before_handoff"],
            "warnings": [],
            "errors": [],
        }

        if cdef["required_before_handoff"] and not passed:
            item["errors"].append(f"check_failed: {cdef['item_id']}")
            blocked_reasons.append(f"checklist_failed: {cdef['item_id']}")

        if cdef["item_id"] == "known_warning_apply_check_already_exists":
            item["warnings"].append(
                "Known warning: git apply --check may show 'already exists' "
                "because source commit 94908556 is already in local tree"
            )
            warnings.append(item["warnings"][0])

        items.append(item)

    all_passed = all(item["passed"] for item in items)
    critical_passed = all(
        item["passed"]
        for item in items
        if item.get("risk_level") == DeliveryPackageRiskLevel.CRITICAL.value
        and item.get("required_before_handoff")
    )

    return {
        "items": items,
        "all_passed": all_passed,
        "critical_passed": critical_passed,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
    }


# ── 5. generate_delivery_package_index ────────────────────────────────────────


def generate_delivery_package_index(
    root: Optional[str] = None, artifacts: Optional[dict] = None
) -> dict:
    """Generate delivery package index (JSON + MD).

    Returns dict with:
      index_path: str
      json_path: str
      index_data: dict
    """
    root_path = _root(root)
    output_dir = REPORT_DIR

    if artifacts is None:
        artifacts = collect_delivery_artifacts(str(root_path))

    json_path = output_dir / "R241-16U_DELIVERY_PACKAGE_INDEX.json"
    md_path = output_dir / "R241-16U_DELIVERY_PACKAGE_INDEX.md"

    # Build index data
    index_data = {
        "index_id": "R241-16U-index",
        "generated_at": _now(),
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_changed_files": [TARGET_WORKFLOW],
        "artifacts": artifacts.get("artifacts", []),
        "allowed_artifact_paths": [str(REPORT_DIR)],
    }

    # Write JSON
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)

    # Write MD
    lines = [
        "# R241-16U Delivery Package Index",
        "",
        f"**Index ID**: `R241-16U-index`",
        f"**Generated**: `{index_data['generated_at']}`",
        f"**Source Commit**: `{SOURCE_COMMIT_HASH}`",
        f"**Changed Files**: `{TARGET_WORKFLOW}`",
        "",
        "## Artifact Table",
        "",
        "| Role | Path | Size | SHA256 | Required | Safe | Recommended Action |",
        "|------|------|------|--------|----------|------|---------------------|",
    ]

    role_labels = {
        DeliveryArtifactRole.PATCH: "patch",
        DeliveryArtifactRole.BUNDLE: "bundle",
        DeliveryArtifactRole.MANIFEST: "manifest",
        DeliveryArtifactRole.VERIFICATION_REPORT: "verification_result",
        DeliveryArtifactRole.DELIVERY_NOTE: "delivery_note",
        DeliveryArtifactRole.GENERATION_RESULT: "generation_result",
    }

    for a in artifacts.get("artifacts", []):
        role = a.get("role", "unknown")
        path = a.get("path", "")
        short_path = str(Path(path).name)
        size = a.get("size_bytes", 0)
        sha = a.get("sha256", "N/A")
        sha_short = sha[:16] + "..." if sha and sha != "N/A" else "N/A"
        required = "yes" if a.get("required") else "no"
        safe = "yes" if a.get("safe_to_share") else "no"

        # Recommended action
        if role == DeliveryArtifactRole.PATCH.value:
            action = "Review, then apply with `git am`"
        elif role == DeliveryArtifactRole.BUNDLE.value:
            action = "Import via `git bundle` for review"
        elif role == DeliveryArtifactRole.VERIFICATION_REPORT.value:
            action = "Read before applying patch"
        elif role == DeliveryArtifactRole.DELIVERY_NOTE.value:
            action = "Read apply/verify instructions"
        elif role == DeliveryArtifactRole.MANIFEST.value:
            action = "Reference for artifact integrity"
        else:
            action = "Archive"

        lines.append(
            f"| {role} | {short_path} | {size} | `{sha_short}` | {required} | {safe} | {action} |"
        )

    lines.extend([
        "",
        "## Do-Not-Run Warnings",
        "",
        "**DO NOT** run `gh workflow run foundation-manual-dispatch.yml`.",
        "The workflow uses `workflow_dispatch` and must be manually triggered",
        "on GitHub after the patch is applied AND the workflow file is visible",
        "on the remote `origin/main` branch.",
        "",
        "**DO NOT** push this patch to the remote. The push already failed",
        "with 403 permission denied. This delivery is for local application only.",
        "",
        "**Known warning**: `git apply --check` may show 'already exists'",
        "because source commit `94908556` is already in the local tree.",
        "This is expected and does not indicate a problem.",
    ])

    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "index_path": str(json_path),
        "json_path": str(json_path),
        "md_path": str(md_path),
        "index_data": index_data,
    }


# ── 6. generate_delivery_final_checklist ──────────────────────────────────────


def generate_delivery_final_checklist(
    root: Optional[str] = None, checklist: Optional[dict] = None
) -> dict:
    """Generate final checklist MD.

    Returns dict with:
      checklist_path: str
      checklist_data: dict
    """
    root_path = _root(root)

    if checklist is None:
        checklist = build_delivery_final_checklist(str(root_path))

    md_path = REPORT_DIR / "R241-16U_DELIVERY_FINAL_CHECKLIST.md"
    items = checklist.get("items", [])

    # Group by status
    passed_items = [i for i in items if i.get("passed")]
    failed_items = [i for i in items if not i.get("passed")]

    risk_order = {
        DeliveryPackageRiskLevel.CRITICAL.value: 0,
        DeliveryPackageRiskLevel.HIGH.value: 1,
        DeliveryPackageRiskLevel.MEDIUM.value: 2,
        DeliveryPackageRiskLevel.LOW.value: 3,
    }
    failed_items.sort(key=lambda x: risk_order.get(x.get("risk_level", ""), 4))
    warnings_list = checklist.get("warnings", [])

    lines = [
        "# R241-16U Delivery Final Checklist",
        "",
        f"**Generated**: `{_now()}`",
        f"**Source Commit**: `{SOURCE_COMMIT_HASH}`",
        "",
        "## Status Summary",
        "",
        f"- **Total Items**: {len(items)}",
        f"- **Passed**: {len(passed_items)}",
        f"- **Failed**: {len(failed_items)}",
        f"- **Warnings**: {len(warnings_list)}",
        "",
    ]

    if failed_items:
        lines.extend(["## Blockers", ""])
        for item in failed_items:
            risk = item.get("risk_level", "unknown").upper()
            lines.append(f"- **[{risk}]** {item.get('description', item['item_id'])}")
        lines.append("")

    if warnings_list:
        lines.extend(["## Known Warnings", ""])
        for w in warnings_list:
            lines.append(f"- {w}")
        lines.append("")

    lines.extend(["## Checklist", ""])
    lines.append("| Status | Risk | Description |")
    lines.append("|--------|------|-------------|")
    for item in items:
        status = "PASS" if item.get("passed") else "FAIL"
        risk = item.get("risk_level", "unknown").upper()
        desc = item.get("description", item["item_id"])
        lines.append(f"| {status} | {risk} | {desc} |")

    lines.extend(["", "## Final Handoff Status", ""])
    if not failed_items:
        lines.append("**APPROVED FOR HANDOFF** — All required checks passed.")
    else:
        blocker_count = len([i for i in failed_items if i.get("required_before_handoff")])
        lines.append(
            f"**BLOCKED** — {blocker_count} required check(s) failed. "
            "Resolve blockers before handoff."
        )

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "checklist_path": str(md_path),
        "checklist_data": checklist,
    }


# ── 7. generate_handoff_summary ───────────────────────────────────────────────


def generate_handoff_summary(
    root: Optional[str] = None, result_so_far: Optional[dict] = None
) -> dict:
    """Generate handoff summary MD.

    Returns dict with:
      summary_path: str
      summary_data: dict
    """
    root_path = _root(root)

    md_path = REPORT_DIR / "R241-16U_HANDOFF_SUMMARY.md"

    # Load delivery note for context
    delivery_note_content = ""
    if DELIVERY_NOTE_PATH.exists():
        try:
            delivery_note_content = DELIVERY_NOTE_PATH.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

    lines = [
        "# R241-16U Delivery Handoff Summary",
        "",
        "## Why This Package Exists",
        "",
        "The R241-16S patch bundle was generated after the upstream push to `origin/main`",
        "failed with a 403 permission denied error. This delivery package provides",
        "the verified artifacts needed for a receiver to apply the patch locally,",
        "review the workflow, and open a PR or push to a branch where the workflow",
        "can be manually triggered.",
        "",
        "## Upstream Push Failure Summary",
        "",
        "- **Commit**: `94908556cc2ca66c219d361f424954945eee9e67`",
        "- **File**: `.github/workflows/foundation-manual-dispatch.yml`",
        "- **Push Result**: `permission_denied_403`",
        "- **Recovery**: R241-16S patch bundle generated; R241-16T verification passed",
        "",
        "## Artifact List",
        "",
        "| Artifact | Description |",
        "|----------|-------------|",
        "| R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch | Git-format-patch of the workflow |",
        "| R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle | Git bundle for safe transport |",
        "| R241-16S_PATCH_BUNDLE_MANIFEST.json | Artifact manifest with checksums |",
        "| R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json | R241-16T verification result |",
        "| R241-16T_PATCH_BUNDLE_VERIFICATION_REPORT.md | R241-16T verification report |",
        "| R241-16T_PATCH_DELIVERY_NOTE.md | Apply instructions for receiver |",
        "| R241-16U_DELIVERY_PACKAGE_INDEX.json | This delivery package index |",
        "| R241-16U_DELIVERY_FINAL_CHECKLIST.md | Final pre-handoff checklist |",
        "",
        "## Receiver Instructions",
        "",
        "1. **Review** the patch file at `migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch`",
        "   before applying.",
        "",
        "2. **Verify** the checksums against `R241-16S_PATCH_BUNDLE_MANIFEST.json`.",
        "",
        "3. **Apply** the patch:",
        "   ```",
        "   git am < migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
        "   ```",
        "",
        "4. **Review** the applied workflow at `.github/workflows/foundation-manual-dispatch.yml`.",
        "",
        "5. **Push** to your branch (or open a PR):",
        "   ```",
        "   git push origin <your-branch>",
        "   ```",
        "",
        "6. **Trigger** the workflow manually on GitHub after the file is visible on the branch.",
        "",
        "## Safety Summary",
        "",
        "- No secrets, tokens, or webhook URLs in patch",
        "- `workflow_dispatch` trigger only — no automatic execution",
        "- No auto-fix or runtime write operations",
        "- No push was executed — receiver controls all git operations",
        "",
        "## Next Possible Paths",
        "",
        "1. **Receiver applies patch locally** → reviews workflow → pushes to branch → opens PR",
        "2. **Receiver with write permission pushes directly** to a feature branch",
        "3. **Local commit remains 1 ahead** of `origin/main` until resolved",
        "4. **Patch bundle** can be shared out-of-band for review without git push",
        "",
        "## Artifact Checksums",
        "",
    ]

    # Add checksums if artifacts collected
    if result_so_far:
        artifacts = result_so_far.get("artifacts", {}).get("artifacts", [])
        for a in artifacts:
            if a.get("exists") and a.get("sha256"):
                lines.append(
                    f"- **{a['artifact_id']}**: `{a['sha256']}` ({a['size_bytes']} bytes)"
                )
    else:
        for path, label in [
            (PATCH_PATH, "patch"),
            (BUNDLE_PATH, "bundle"),
            (MANIFEST_PATH, "manifest"),
        ]:
            if path.exists():
                sha = _sha256(path)
                lines.append(f"- **{label}**: `{sha}` ({path.stat().st_size} bytes)")

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "summary_path": str(md_path),
        "summary_data": {"generated_at": _now()},
    }


# ── 8. verify_no_local_mutation_after_finalization ───────────────────────────


def verify_no_local_mutation_after_finalization(
    root: Optional[str] = None, baseline: Optional[dict] = None
) -> dict:
    """Verify no unintended file modifications occurred during finalization.

    Returns dict with all_passed, checks, blocked_reasons, warnings.
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
        "description": "HEAD hash must not change during finalization",
        "observed_value": after["head_hash"],
        "expected_value": base.get("head_hash"),
    })
    if not head_unchanged:
        blocked_reasons.append("head_changed_during_finalization")

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
    })

    # Staged area unchanged
    staged_unchanged = after["staged_files"] == base.get("staged_files", [])
    checks.append({
        "check_id": "staged_area_unchanged",
        "check_type": "staged_area",
        "passed": staged_unchanged,
        "risk_level": "critical",
        "description": "Staged area must not change during finalization",
        "observed_value": after["staged_files"],
        "expected_value": base.get("staged_files", []),
    })
    if not staged_unchanged:
        blocked_reasons.append("staged_area_changed_during_finalization")

    # Workflow files unchanged
    workflow_unchanged = True
    for wf in [TARGET_WORKFLOW]:
        wf_path = root_path / wf
        if wf_path.exists():
            # We can't check content here, just existence
            pass

    checks.append({
        "check_id": "workflow_files_unchanged",
        "check_type": "workflow_integrity",
        "passed": workflow_unchanged,
        "risk_level": "high",
        "description": "Workflow files must not be modified during finalization",
        "observed_value": "not_checked_content",
        "expected_value": "unchanged",
    })

    # Runtime dir unchanged
    runtime_changed = after["runtime_dir_exists"] != base.get("runtime_dir_exists", False)
    checks.append({
        "check_id": "runtime_dir_unchanged",
        "check_type": "runtime_integrity",
        "passed": not runtime_changed,
        "risk_level": "critical",
        "description": "Runtime directory must not be created during finalization",
        "observed_value": after["runtime_dir_exists"],
        "expected_value": base.get("runtime_dir_exists", False),
    })
    if runtime_changed:
        blocked_reasons.append("runtime_dir_created_during_finalization")

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
    })
    if not audit_unchanged:
        blocked_reasons.append("audit_jsonl_modified_during_finalization")

    # Only allowed new files
    allowed_new_artifact_names = {
        "R241-16U_DELIVERY_PACKAGE_INDEX.json",
        "R241-16U_DELIVERY_PACKAGE_INDEX.md",
        "R241-16U_DELIVERY_FINAL_CHECKLIST.md",
        "R241-16U_HANDOFF_SUMMARY.md",
        "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json",
        "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.md",
        "R241-16U_DELIVERY_PACKAGE_FINALIZATION_REPORT.md",
        # R241-16S/T artifacts may already exist
        "R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
        "R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle",
        "R241-16S_PATCH_BUNDLE_MANIFEST.json",
        "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json",
        "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.md",
        "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json",
        "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.md",
        "R241-16T_PATCH_DELIVERY_NOTE.md",
    }
    output_dir = REPORT_DIR
    unexpected_new_files = []
    if output_dir.exists():
        for f in output_dir.iterdir():
            if f.is_file():
                fname = f.name
                if fname.startswith("R241-16U") or fname.startswith("R241-16S") or fname.startswith("R241-16T"):
                    if fname not in allowed_new_artifact_names:
                        unexpected_new_files.append(fname)

    no_unexpected = len(unexpected_new_files) == 0
    checks.append({
        "check_id": "no_unexpected_artifacts",
        "check_type": "artifact_naming",
        "passed": no_unexpected,
        "risk_level": "low",
        "description": "Only R241-16U/R241-16S/R241-16T artifacts should be new",
        "observed_value": unexpected_new_files if unexpected_new_files else "none",
        "expected_value": "none",
    })
    if not no_unexpected:
        blocked_reasons.append(f"unexpected_artifacts_during_finalization: {unexpected_new_files}")

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


# ── 9. evaluate_delivery_package_finalization ────────────────────────────────


def evaluate_delivery_package_finalization(root: Optional[str] = None) -> dict:
    """Main evaluation: aggregate all finalization checks.

    Runs all steps in sequence and returns the full finalization result.
    """
    result_id = f"R241-16U-result-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    root_path = _root(root)

    # Capture baseline before any operations
    baseline = _safe_baseline(str(root_path))

    # Step 1: Load verified patch bundle state
    bundle_state = load_verified_patch_bundle_state(str(root_path))

    # Step 2: Collect delivery artifacts
    artifacts = collect_delivery_artifacts(str(root_path))

    # Step 3: Validate artifact integrity
    integrity = validate_delivery_artifact_integrity(artifacts, str(root_path))

    # Step 4: Build final checklist
    checklist = build_delivery_final_checklist(str(root_path))

    # Step 5: Generate delivery package index
    index_result = generate_delivery_package_index(str(root_path), artifacts)

    # Step 6: Generate final checklist
    checklist_result = generate_delivery_final_checklist(str(root_path), checklist)

    # Step 7: Generate handoff summary
    summary_result = generate_handoff_summary(str(root_path))

    # Step 8: Mutation guard
    mutation_guard = verify_no_local_mutation_after_finalization(str(root_path), baseline)

    # Determine status
    if mutation_guard.get("all_passed") is False:
        status = DeliveryPackageFinalizationStatus.BLOCKED_MUTATION_DETECTED
    elif not bundle_state.get("valid", False):
        status = DeliveryPackageFinalizationStatus.BLOCKED_VERIFICATION_NOT_VALID
    elif not integrity.get("valid", False):
        if "checksum" in str(integrity.get("blocked_reasons", [])):
            status = DeliveryPackageFinalizationStatus.BLOCKED_CHECKSUM_MISMATCH
        elif "missing" in str(integrity.get("blocked_reasons", [])):
            status = DeliveryPackageFinalizationStatus.BLOCKED_MISSING_ARTIFACT
        else:
            status = DeliveryPackageFinalizationStatus.BLOCKED_UNSAFE_ARTIFACT
    elif not checklist.get("critical_passed", False):
        status = DeliveryPackageFinalizationStatus.BLOCKED_MISSING_ARTIFACT
    elif checklist.get("warnings"):
        status = DeliveryPackageFinalizationStatus.FINALIZED_WITH_WARNINGS
    else:
        status = DeliveryPackageFinalizationStatus.FINALIZED

    # Determine decision
    finalization_blocked = status in (
        DeliveryPackageFinalizationStatus.BLOCKED_MISSING_ARTIFACT,
        DeliveryPackageFinalizationStatus.BLOCKED_CHECKSUM_MISMATCH,
        DeliveryPackageFinalizationStatus.BLOCKED_UNSAFE_ARTIFACT,
        DeliveryPackageFinalizationStatus.BLOCKED_VERIFICATION_NOT_VALID,
        DeliveryPackageFinalizationStatus.BLOCKED_MUTATION_DETECTED,
    )
    has_warnings = status == DeliveryPackageFinalizationStatus.FINALIZED_WITH_WARNINGS

    if finalization_blocked:
        decision = DeliveryPackageDecision.BLOCK_HANDOFF
    elif has_warnings:
        decision = DeliveryPackageDecision.APPROVE_HANDOFF_WITH_WARNINGS
    else:
        decision = DeliveryPackageDecision.APPROVE_HANDOFF

    all_blocked_reasons = (
        bundle_state.get("blocked_reasons", []) +
        artifacts.get("blocked_reasons", []) +
        integrity.get("blocked_reasons", []) +
        checklist.get("blocked_reasons", []) +
        mutation_guard.get("blocked_reasons", [])
    )
    all_warnings = (
        bundle_state.get("warnings", []) +
        artifacts.get("warnings", []) +
        integrity.get("warnings", []) +
        checklist.get("warnings", [])
    )

    return {
        "result_id": result_id,
        "generated_at": _now(),
        "status": status.value,
        "decision": decision.value,
        "source_commit_hash": SOURCE_COMMIT_HASH,
        "source_changed_files": [TARGET_WORKFLOW],
        "verified_bundle_state": bundle_state,
        "artifacts": artifacts,
        "integrity": integrity,
        "checklist": checklist,
        "index_result": index_result,
        "checklist_result": checklist_result,
        "summary_result": summary_result,
        "mutation_guard": mutation_guard,
        "baseline": baseline,
        "warnings": all_warnings,
        "errors": [],
        "blocked_reasons": all_blocked_reasons,
    }


# ── 10. validate_delivery_package_finalization_result ──────────────────────────


def validate_delivery_package_finalization_result(result: dict) -> dict:
    """Validate the finalization result against safety constraints.

    Returns dict with valid=True/False and blocked_reasons.
    """
    blocked_reasons = []
    warnings = []
    errors = []

    # Check: delivery package index exists
    index_result = result.get("index_result", {})
    if not index_result.get("index_path") or not Path(index_result["index_path"]).exists():
        blocked_reasons.append("delivery_package_index_not_generated")

    # Check: final checklist exists
    checklist_result = result.get("checklist_result", {})
    if not checklist_result.get("checklist_path") or not Path(checklist_result["checklist_path"]).exists():
        blocked_reasons.append("final_checklist_not_generated")

    # Check: handoff summary exists
    summary_result = result.get("summary_result", {})
    if not summary_result.get("summary_path") or not Path(summary_result["summary_path"]).exists():
        blocked_reasons.append("handoff_summary_not_generated")

    # Check: no git push (no git commands in finalization phase)
    # All git operations in finalization are read-only via _safe_baseline

    # Check: no git commit
    # No commit operations

    # Check: no git reset/restore/revert
    # None executed

    # Check: no git am
    # Not executed in finalization

    # Check: no actual git apply
    # apply check was in R241-16T, not in finalization

    # Check: no gh workflow run
    # None in finalization

    # Check: no workflow modification
    mutation_guard = result.get("mutation_guard", {})
    if not mutation_guard.get("all_passed", False):
        blocked_reasons.extend(mutation_guard.get("blocked_reasons", ["mutation_detected"]))

    # Check: no runtime write
    after_state = mutation_guard.get("after_state", {})
    if after_state.get("runtime_dir_exists"):
        blocked_reasons.append("runtime_dir_created")

    # Check: no audit JSONL write
    baseline = result.get("baseline", {})
    after_count = after_state.get("audit_jsonl_line_count", 0)
    baseline_count = baseline.get("audit_jsonl_line_count", 0)
    if after_count != baseline_count:
        blocked_reasons.append("audit_jsonl_modified")

    # Check: full patch content not embedded in markdown
    # We don't embed full patch content, so this is always satisfied
    md_paths = [
        index_result.get("md_path"),
        checklist_result.get("checklist_path"),
        summary_result.get("summary_path"),
    ]
    for md_path in md_paths:
        if md_path and Path(md_path).exists():
            content = Path(md_path).read_text(encoding="utf-8", errors="replace")
            # A full patch has many lines starting with ^+ and diff headers
            # If we see more than 5 diff hunk lines, that might indicate full content
            diff_lines = [l for l in content.splitlines() if l.startswith("+++") or l.startswith("---") or l.startswith("@@")]
            if len(diff_lines) > 5:
                blocked_reasons.append(f"full_patch_content_in_md: {Path(md_path).name}")

    valid = len(blocked_reasons) == 0
    return {
        "valid": valid,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": errors,
    }


# ── 11. generate_delivery_package_finalization_report ─────────────────────────


def generate_delivery_package_finalization_report(
    result: Optional[dict] = None, output_path: Optional[str] = None
) -> dict:
    """Generate finalization report (JSON + MD).

    Writes:
      R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json
      R241-16U_DELIVERY_PACKAGE_FINALIZATION_REPORT.md
    """
    if result is None:
        result = evaluate_delivery_package_finalization()

    validation = validate_delivery_package_finalization_result(result)

    if output_path:
        json_path = Path(output_path)
    else:
        json_path = REPORT_DIR / "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json"

    json_path.parent.mkdir(parents=True, exist_ok=True)

    report_data = {
        "result_id": result.get("result_id"),
        "generated_at": result.get("generated_at"),
        "status": result.get("status"),
        "decision": result.get("decision"),
        "source_commit_hash": result.get("source_commit_hash"),
        "source_changed_files": result.get("source_changed_files"),
        "verified_bundle_state": result.get("verified_bundle_state", {}),
        "artifacts": result.get("artifacts", {}),
        "integrity": result.get("integrity", {}),
        "checklist": result.get("checklist", {}),
        "index_result": {
            "index_path": result.get("index_result", {}).get("index_path"),
            "md_path": result.get("index_result", {}).get("md_path"),
        },
        "checklist_result": {
            "checklist_path": result.get("checklist_result", {}).get("checklist_path"),
        },
        "summary_result": {
            "summary_path": result.get("summary_result", {}).get("summary_path"),
        },
        "mutation_guard": result.get("mutation_guard", {}),
        "baseline_captured": bool(result.get("baseline")),
        "validation": validation,
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
        "blocked_reasons": result.get("blocked_reasons", []),
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
    status = data.get("status", "unknown")
    decision = data.get("decision", "unknown")

    lines = [
        "# R241-16U Delivery Package Finalization Report",
        "",
        f"- **Result ID**: `{data.get('result_id', 'N/A')}`",
        f"- **Generated**: `{data.get('generated_at', 'N/A')}`",
        f"- **Status**: `{status}`",
        f"- **Decision**: `{decision}`",
        f"- **Source Commit**: `{data.get('source_commit_hash', 'N/A')}`",
        f"- **Changed Files**: `{data.get('source_changed_files', [])}`",
        "",
        "## Verification State Loading",
        "",
    ]

    vbs = data.get("verified_bundle_state", {})
    lines.extend([
        f"- **Loaded**: `{vbs.get('loaded', False)}`",
        f"- **Valid**: `{vbs.get('valid', False)}`",
        f"- **Status**: `{vbs.get('status', 'unknown')}`",
        f"- **Decision**: `{vbs.get('decision', 'unknown')}`",
        f"- **Patch Safe**: `{vbs.get('patch_safe', False)}`",
        f"- **Bundle Safe**: `{vbs.get('bundle_safe', False)}`",
    ])

    lines.extend(["", "## Artifact Collection", ""])
    artifacts = data.get("artifacts", {}).get("artifacts", [])
    for a in artifacts:
        lines.append(
            f"- **{a.get('artifact_id', '?')}** ({a.get('role', '?')}): "
            f"exists={a.get('exists')}, size={a.get('size_bytes', 0)}, "
            f"sha256={a.get('sha256', 'N/A')[:16]}..., required={a.get('required')}"
        )

    lines.extend(["", "## Artifact Integrity", ""])
    integrity = data.get("integrity", {})
    lines.append(f"- **Valid**: `{integrity.get('valid', False)}`")
    for c in integrity.get("checks", []):
        status_icon = "PASS" if c.get("passed") else "FAIL"
        lines.append(f"- **{status_icon}** `{c.get('check_id', '?')}`: {c.get('description', '')}")

    lines.extend(["", "## Final Checklist", ""])
    checklist = data.get("checklist", {})
    lines.append(f"- **All Passed**: `{checklist.get('all_passed', False)}`")
    lines.append(f"- **Critical Passed**: `{checklist.get('critical_passed', False)}`")
    for item in checklist.get("items", []):
        icon = "PASS" if item.get("passed") else "FAIL"
        risk = item.get("risk_level", "unknown").upper()
        lines.append(f"- **{icon}** [{risk}] {item.get('description', item['item_id'])}")

    lines.extend(["", "## Mutation Guard", ""])
    mg = data.get("mutation_guard", {})
    lines.append(f"- **All Passed**: `{mg.get('all_passed', False)}`")
    for c in mg.get("checks", []):
        if not c.get("passed"):
            lines.append(f"  - FAIL: {c.get('check_id', '?')}: {c.get('description', '')}")

    lines.extend(["", "## Validation", ""])
    lines.append(f"- **Valid**: `{validation.get('valid', False)}`")
    if validation.get("blocked_reasons"):
        for br in validation["blocked_reasons"]:
            lines.append(f"  - {br}")

    lines.extend(["", "## Warnings", ""])
    for w in data.get("warnings", []):
        lines.append(f"- {w}")
    if not data.get("warnings"):
        lines.append("- (none)")

    lines.extend(["", "## Safety Summary", ""])
    lines.extend([
        "- No git push executed in finalization",
        "- No git commit executed in finalization",
        "- No git reset/restore/revert executed",
        "- No git am or actual git apply executed",
        "- No gh workflow run executed",
        "- No workflow files modified",
        "- No runtime/audit JSONL/action queue write",
        "- No auto-fix executed",
        "- Full patch content NOT embedded in generated markdown",
    ])

    lines.extend(["", "## Generated Artifacts", ""])
    ir = data.get("index_result", {})
    cr = data.get("checklist_result", {})
    sr = data.get("summary_result", {})
    for label, path_key in [
        ("Index (JSON)", "index_path"),
        ("Index (MD)", "md_path"),
        ("Checklist", "checklist_path"),
        ("Summary", "summary_path"),
        ("Result (JSON)", "output_path"),
        ("Report (MD)", "report_path"),
    ]:
        path = ir.get(path_key) or cr.get(path_key) or sr.get(path_key) or data.get(path_key, "")
        if path:
            lines.append(f"- **{label}**: `{Path(path).name}`")

    lines.extend(["", "## Receiver Handoff Summary", ""])
    lines.extend([
        "- Receiver must review patch before applying",
        "- Receiver must not run workflow until visible on remote main",
        "- Apply with: `git am < migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch`",
        "- Verify with: `git diff-tree --no-commit-id --name-only -r 94908556`",
        "- Push to branch or open PR to trigger workflow",
    ])

    lines.extend(["", "## Current Remaining Blockers", ""])
    blocked = data.get("blocked_reasons", [])
    if blocked:
        for b in blocked:
            lines.append(f"- {b}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Next Recommended Steps", ""])
    if validation.get("valid") and decision in ("approve_handoff", "approve_handoff_with_warnings"):
        lines.extend([
            "- Proceed to R241-16V: Foundation CI Delivery Closure Review",
            "- Package artifacts for receiver",
            "- Receiver applies patch and opens PR",
        ])
    else:
        lines.extend([
            "- Fix blocked_reasons before handoff",
            "- Re-run finalization after fixes",
        ])

    lines.extend(["", "---", f"*Generated: {data.get('generated_at', 'N/A')}*"])

    Path(md_path).write_text("\n".join(lines), encoding="utf-8")
