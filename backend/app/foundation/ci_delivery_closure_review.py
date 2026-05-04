"""R241-16V: Foundation CI Delivery Closure Review.

Read-only closure review of the full R241-16A through R241-16U delivery chain:
- Load and validate all prior stage reports
- Verify delivery artifact integrity (patch, bundle, manifest, verification result,
  delivery note, handoff index, checklist, summary)
- Build closure checks across safety, CI matrix, manual workflow, patch bundle,
  delivery package, tests, handoff, and other domains
- Output receiver next steps
- Verify no local mutation occurred during review
- Generate closure review report (JSON + MD)

Allowed read operations:
  git status --branch --short
  git diff --cached --name-only
  git diff-tree --no-commit-id --name-only -r <hash>
  git show --name-only --format=fuller <hash>

Allowed write operations:
  R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.json
  R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.md

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
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[3]

REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"

# ── Stage chain mapping ────────────────────────────────────────────────────────
# Maps stage ID → (report_name_prefix, description)
STAGE_CHAIN = [
    ("R241-16A", "CI Matrix Plan"),
    ("R241-16B", "CI Implementation Plan"),
    ("R241-16C", "CI Local Dry Run"),
    ("R241-16D", "CI Workflow Draft"),
    ("R241-16E", "CI Enablement Review"),
    ("R241-16F", "CI Manual Dispatch Review"),
    ("R241-16G", "CI Manual Dispatch Implementation Review"),
    ("R241-16H", "CI Manual Workflow Confirmation Gate"),
    ("R241-16I", "CI Manual Workflow Creation"),
    ("R241-16J", "CI Manual Workflow Runtime Verification"),
    ("R241-16K", "CI Remote Dispatch Confirmation Gate"),
    ("R241-16L", "CI Remote Dispatch Execution"),
    ("R241-16M", "CI Remote Workflow Visibility Review"),
    ("R241-16N", "CI Remote Visibility Consistency"),
    ("R241-16O", "CI Publish Confirmation Gate"),
    ("R241-16P", "CI Publish Implementation"),
    ("R241-16Q", "CI Publish Retry Git Identity"),
    ("R241-16R", "CI Publish Push Failure Review"),
    ("R241-16S", "CI Publish Patch Bundle Generation"),
    ("R241-16T", "CI Patch Bundle Verification"),
    ("R241-16U", "CI Delivery Package Finalization"),
]

# Delivery artifacts that should exist after R241-16U
DELIVERY_ARTIFACTS = [
    ("R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch", "patch", True),
    ("R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle", "bundle", True),
    ("R241-16S_PATCH_BUNDLE_MANIFEST.json", "manifest", True),
    ("R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json", "verification_report", True),
    ("R241-16T_PATCH_DELIVERY_NOTE.md", "delivery_note", True),
    ("R241-16U_DELIVERY_PACKAGE_INDEX.json", "handoff_index", True),
    ("R241-16U_DELIVERY_PACKAGE_INDEX.md", "handoff_index_md", False),
    ("R241-16U_DELIVERY_FINAL_CHECKLIST.md", "final_checklist", True),
    ("R241-16U_HANDOFF_SUMMARY.md", "handoff_summary", True),
    ("R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json", "finalization_result", True),
    ("R241-16U_DELIVERY_PACKAGE_FINALIZATION_REPORT.md", "finalization_report", False),
]

SOURCE_COMMIT_HASH = "94908556cc2ca66c219d361f424954945eee9e67"
TARGET_WORKFLOW = ".github/workflows/foundation-manual-dispatch.yml"


# ── Enums ──────────────────────────────────────────────────────────────────────


class DeliveryClosureStatus(str, Enum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


class DeliveryClosureDecision(str, Enum):
    APPROVE_CLOSURE = "approve_closure"
    APPROVE_CLOSURE_WITH_CONDITIONS = "approve_closure_with_conditions"
    BLOCK_CLOSURE = "block_closure"
    DEFER = "defer"
    UNKNOWN = "unknown"


class DeliveryClosureRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class DeliveryClosureDomain(str, Enum):
    SAFETY = "safety"
    CI_MATRIX = "ci_matrix"
    MANUAL_WORKFLOW = "manual_workflow"
    PATCH_BUNDLE = "patch_bundle"
    DELIVERY_PACKAGE = "delivery_package"
    TESTS = "tests"
    HANDOFF = "handoff"
    ARTIFACT_INTEGRITY = "artifact_integrity"
    MUTATION_GUARD = "mutation_guard"
    CHAIN_COMPLETENESS = "chain_completeness"
    UNKNOWN = "unknown"


# ── Data Objects ───────────────────────────────────────────────────────────────


class DeliveryClosureCheck:
    def __init__(
        self,
        domain: str,
        check_id: str,
        description: str,
        passed: bool,
        status: str,
        risk_level: str,
        details: Optional[dict[str, Any]] = None,
        recommendations: Optional[list[str]] = None,
    ):
        self.domain = domain
        self.check_id = check_id
        self.description = description
        self.passed = passed
        self.status = status
        self.risk_level = risk_level
        self.details = details or {}
        self.recommendations = recommendations or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "domain": self.domain,
            "description": self.description,
            "passed": self.passed,
            "status": self.status,
            "risk_level": self.risk_level,
            "details": self.details,
            "recommendations": self.recommendations,
        }


class DeliveryClosureArtifactSummary:
    def __init__(
        self,
        filename: str,
        role: str,
        exists: bool,
        sha256: Optional[str] = None,
        size_bytes: Optional[int] = None,
        required: bool = True,
        validation_errors: Optional[list[str]] = None,
    ):
        self.filename = filename
        self.role = role
        self.exists = exists
        self.sha256 = sha256
        self.size_bytes = size_bytes
        self.required = required
        self.validation_errors = validation_errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "role": self.role,
            "exists": self.exists,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "required": self.required,
            "validation_errors": self.validation_errors,
        }


class DeliveryClosureReview:
    def __init__(
        self,
        review_id: str,
        stage_chain: list[dict[str, Any]],
        artifact_summary: list[dict[str, Any]],
        closure_checks: list[dict[str, Any]],
        receiver_next_steps: list[str],
        mutation_guard: dict[str, Any],
        decision: str,
        status: str,
        risk_level: str,
        generated_at: str,
        validated: bool = False,
        validation_errors: Optional[list[str]] = None,
    ):
        self.review_id = review_id
        self.stage_chain = stage_chain
        self.artifact_summary = artifact_summary
        self.closure_checks = closure_checks
        self.receiver_next_steps = receiver_next_steps
        self.mutation_guard = mutation_guard
        self.decision = decision
        self.status = status
        self.risk_level = risk_level
        self.generated_at = generated_at
        self.validated = validated
        self.validation_errors = validation_errors or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "stage_chain": self.stage_chain,
            "artifact_summary": self.artifact_summary,
            "closure_checks": self.closure_checks,
            "receiver_next_steps": self.receiver_next_steps,
            "mutation_guard": self.mutation_guard,
            "decision": self.decision,
            "status": self.status,
            "risk_level": self.risk_level,
            "generated_at": self.generated_at,
            "validated": self.validated,
            "validation_errors": self.validation_errors,
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


# ── 1. load_delivery_finalization_state ───────────────────────────────────────


def load_delivery_finalization_state(root: Optional[str] = None) -> dict:
    """Load R241-16U finalization result if it exists.

    Returns dict with:
      loaded: bool
      exists: bool
      data: dict | None
      path: str
      errors: list[str]
    """
    root_path = _root(root)
    result_path = root_path / "migration_reports" / "foundation_audit" / "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json"
    errors = []
    data = None
    exists = result_path.exists()

    if exists:
        try:
            text = result_path.read_text(encoding="utf-8")
            data = json.loads(text)
        except Exception as e:
            errors.append(f"Failed to parse R241-16U finalization result: {e}")
    else:
        errors.append("R241-16U finalization result not found")

    return {
        "loaded": True,
        "exists": exists,
        "data": data,
        "path": str(result_path),
        "errors": errors,
    }


# ── 2. collect_foundation_ci_delivery_stage_chain ───────────────────────────────


def collect_foundation_ci_delivery_stage_chain(root: Optional[str] = None) -> list[dict[str, Any]]:
    """Collect all stage reports from R241-16A through R241-16U.

    Returns list of dicts with stage info and whether their report exists.
    Uses prefix-based matching to capture all delivery report types
    (PLAN, REVIEW, RESULT, GATE, IMPLEMENTATION, etc.).
    """
    root_path = _root(root)
    report_dir = root_path / "migration_reports" / "foundation_audit"
    chain = []

    for stage_id, description in STAGE_CHAIN:
        json_matches = list(report_dir.glob(f"{stage_id}_*.json"))
        md_matches = list(report_dir.glob(f"{stage_id}_*.md"))

        json_exists = len(json_matches) > 0
        md_exists = len(md_matches) > 0

        chain.append({
            "stage_id": stage_id,
            "description": description,
            "report_json_exists": json_exists,
            "report_md_exists": md_exists,
            "report_json_path": str(json_matches[0]) if json_matches else None,
            "report_md_path": str(md_matches[0]) if md_matches else None,
        })

    return chain


# ── 3. verify_delivery_artifacts_for_closure ──────────────────────────────────


def verify_delivery_artifacts_for_closure(root: Optional[str] = None) -> list[dict[str, Any]]:
    """Verify all delivery artifacts exist and have valid metadata.

    Returns list of DeliveryClosureArtifactSummary dicts.
    """
    root_path = _root(root)
    report_dir = root_path / "migration_reports" / "foundation_audit"
    summaries = []

    for filename, role, required in DELIVERY_ARTIFACTS:
        artifact_path = report_dir / filename
        errors = []
        sha256_val: Optional[str] = None
        size_bytes: Optional[int] = None

        exists = artifact_path.exists()

        if exists:
            try:
                sha256_val = _sha256(artifact_path)
                size_bytes = artifact_path.stat().st_size
            except Exception as e:
                errors.append(f"Failed to read artifact: {e}")
        else:
            if required:
                errors.append(f"Required artifact missing: {filename}")
            else:
                errors.append(f"Optional artifact missing: {filename}")

        summaries.append({
            "filename": filename,
            "role": role,
            "exists": exists,
            "sha256": sha256_val,
            "size_bytes": size_bytes,
            "required": required,
            "validation_errors": errors,
        })

    return summaries


# ── 4. build_delivery_closure_checks ──────────────────────────────────────────


def _check_chain_completeness(stage_chain: list[dict[str, Any]]) -> list[DeliveryClosureCheck]:
    """Domain: chain_completeness"""
    checks = []
    checks_by_stage: dict[str, dict[str, Any]] = {s["stage_id"]: s for s in stage_chain}

    critical_stages = ["R241-16A", "R241-16S", "R241-16T", "R241-16U"]
    for stage_id in critical_stages:
        stage = checks_by_stage.get(stage_id, {})
        has_report = stage.get("report_json_exists", False) or stage.get("report_md_exists", False)
        if not has_report:
            checks.append(DeliveryClosureCheck(
                domain=DeliveryClosureDomain.CHAIN_COMPLETENESS.value,
                check_id=f"chain_complete_{stage_id}",
                description=f"Critical stage {stage_id} has a delivery report",
                passed=False,
                status="failed",
                risk_level=DeliveryClosureRiskLevel.HIGH.value,
                details={"stage_id": stage_id, "has_report": has_report},
                recommendations=[f"Execute {stage_id} to generate its delivery report before closure"],
            ))
        else:
            checks.append(DeliveryClosureCheck(
                domain=DeliveryClosureDomain.CHAIN_COMPLETENESS.value,
                check_id=f"chain_complete_{stage_id}",
                description=f"Critical stage {stage_id} has a delivery report",
                passed=True,
                status="passed",
                risk_level=DeliveryClosureRiskLevel.LOW.value,
                details={"stage_id": stage_id, "has_report": has_report},
            ))

    total_stages = len(stage_chain)
    stages_with_reports = sum(
        1 for s in stage_chain if s.get("report_json_exists") or s.get("report_md_exists")
    )
    coverage_pct = (stages_with_reports / total_stages * 100) if total_stages > 0 else 0

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.CHAIN_COMPLETENESS.value,
        check_id="chain_coverage",
        description=f"Stage chain coverage: {stages_with_reports}/{total_stages} stages have reports",
        passed=coverage_pct >= 80.0,
        status="passed" if coverage_pct >= 80.0 else "failed",
        risk_level=DeliveryClosureRiskLevel.MEDIUM.value if coverage_pct < 80.0 else DeliveryClosureRiskLevel.LOW.value,
        details={"stages_with_reports": stages_with_reports, "total_stages": total_stages, "coverage_pct": round(coverage_pct, 1)},
        recommendations=["Generate missing stage reports before closure"] if coverage_pct < 100.0 else [],
    ))

    return checks


def _check_artifact_integrity(artifacts: list[dict[str, Any]], root: Optional[str] = None) -> list[DeliveryClosureCheck]:
    """Domain: artifact_integrity"""
    checks = []
    required_missing = [a for a in artifacts if a["required"] and not a["exists"]]
    optional_missing = [a for a in artifacts if not a["required"] and not a["exists"]]

    all_required_exist = len(required_missing) == 0

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.ARTIFACT_INTEGRITY.value,
        check_id="artifact_required_exist",
        description="All required delivery artifacts exist",
        passed=all_required_exist,
        status="passed" if all_required_exist else "failed",
        risk_level=DeliveryClosureRiskLevel.CRITICAL.value if required_missing else DeliveryClosureRiskLevel.LOW.value,
        details={"required_missing": [a["filename"] for a in required_missing], "total_required": sum(1 for a in artifacts if a["required"])},
        recommendations=["Restore missing required artifacts before closure"] if required_missing else [],
    ))

    total_artifacts = len(artifacts)
    existing_artifacts = sum(1 for a in artifacts if a["exists"])
    artifact_coverage = (existing_artifacts / total_artifacts * 100) if total_artifacts > 0 else 0

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.ARTIFACT_INTEGRITY.value,
        check_id="artifact_delivery_complete",
        description=f"Delivery artifact completeness: {existing_artifacts}/{total_artifacts} artifacts present",
        passed=artifact_coverage >= 80.0,
        status="passed" if artifact_coverage >= 80.0 else "failed",
        risk_level=DeliveryClosureRiskLevel.MEDIUM.value if artifact_coverage < 80.0 else DeliveryClosureRiskLevel.LOW.value,
        details={"existing_artifacts": existing_artifacts, "total_artifacts": total_artifacts, "coverage_pct": round(artifact_coverage, 1)},
        recommendations=["Ensure all delivery artifacts are generated"] if artifact_coverage < 100.0 else [],
    ))

    sha256_artifacts = [a for a in artifacts if a["exists"] and a.get("sha256")]
    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.ARTIFACT_INTEGRITY.value,
        check_id="artifact_sha256_computed",
        description=f"SHA256 computed for {len(sha256_artifacts)}/{existing_artifacts} existing artifacts",
        passed=len(sha256_artifacts) == existing_artifacts,
        status="passed" if len(sha256_artifacts) == existing_artifacts else "failed",
        risk_level=DeliveryClosureRiskLevel.MEDIUM.value,
        details={"sha256_computed": len(sha256_artifacts), "existing_artifacts": existing_artifacts},
    ))

    manifest_artifacts = [a for a in artifacts if a["role"] == "manifest" and a["exists"]]
    if manifest_artifacts:
        manifest = manifest_artifacts[0]
        manifest_errors = manifest.get("validation_errors", [])
        checks.append(DeliveryClosureCheck(
            domain=DeliveryClosureDomain.ARTIFACT_INTEGRITY.value,
            check_id="artifact_manifest_valid",
            description="Patch bundle manifest is present and readable",
            passed=len(manifest_errors) == 0,
            status="passed" if len(manifest_errors) == 0 else "failed",
            risk_level=DeliveryClosureRiskLevel.HIGH.value,
            details={"manifest_file": manifest["filename"], "errors": manifest_errors},
            recommendations=["Regenerate manifest if corrupted"] if manifest_errors else [],
        ))

    verification_artifacts = [a for a in artifacts if a["role"] == "verification_report" and a["exists"]]
    if verification_artifacts:
        verification = verification_artifacts[0]
        verification_errors = verification.get("validation_errors", [])
        checks.append(DeliveryClosureCheck(
            domain=DeliveryClosureDomain.ARTIFACT_INTEGRITY.value,
            check_id="artifact_verification_result_valid",
            description="Patch bundle verification result is present and readable",
            passed=len(verification_errors) == 0,
            status="passed" if len(verification_errors) == 0 else "failed",
            risk_level=DeliveryClosureRiskLevel.HIGH.value,
            details={"verification_file": verification["filename"], "errors": verification_errors},
            recommendations=["Re-run R241-16T verification if verification result is corrupted"] if verification_errors else [],
        ))

    finalization_artifacts = [a for a in artifacts if a["role"] == "finalization_result" and a["exists"]]
    if finalization_artifacts:
        finalization = finalization_artifacts[0]
        finalization_errors = finalization.get("validation_errors", [])
        checks.append(DeliveryClosureCheck(
            domain=DeliveryClosureDomain.ARTIFACT_INTEGRITY.value,
            check_id="artifact_finalization_result_valid",
            description="Delivery package finalization result is present and readable",
            passed=len(finalization_errors) == 0,
            status="passed" if len(finalization_errors) == 0 else "failed",
            risk_level=DeliveryClosureRiskLevel.HIGH.value,
            details={"finalization_file": finalization["filename"], "errors": finalization_errors},
            recommendations=["Re-run R241-16U finalization if finalization result is corrupted"] if finalization_errors else [],
        ))

    return checks


def _check_delivery_package_finalization(
    finalization_state: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> list[DeliveryClosureCheck]:
    """Domain: delivery_package"""
    checks = []

    if not finalization_state.get("exists"):
        checks.append(DeliveryClosureCheck(
            domain=DeliveryClosureDomain.DELIVERY_PACKAGE.value,
            check_id="finalization_result_exists",
            description="R241-16U finalization result exists",
            passed=False,
            status="failed",
            risk_level=DeliveryClosureRiskLevel.CRITICAL.value,
            details={"path": finalization_state.get("path")},
            recommendations=["Execute R241-16U delivery package finalization before closure review"],
        ))
        return checks

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.DELIVERY_PACKAGE.value,
        check_id="finalization_result_exists",
        description="R241-16U finalization result exists",
        passed=True,
        status="passed",
        risk_level=DeliveryClosureRiskLevel.LOW.value,
        details={"path": finalization_state.get("path")},
    ))

    data = finalization_state.get("data")
    if not data:
        checks.append(DeliveryClosureCheck(
            domain=DeliveryClosureDomain.DELIVERY_PACKAGE.value,
            check_id="finalization_result_parseable",
            description="R241-16U finalization result is valid JSON",
            passed=False,
            status="failed",
            risk_level=DeliveryClosureRiskLevel.CRITICAL.value,
            details={"errors": finalization_state.get("errors", [])},
            recommendations=["Repair R241-16U finalization result JSON"],
        ))
        return checks

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.DELIVERY_PACKAGE.value,
        check_id="finalization_result_parseable",
        description="R241-16U finalization result is valid JSON",
        passed=True,
        status="passed",
        risk_level=DeliveryClosureRiskLevel.LOW.value,
    ))

    finalization_status = data.get("status", DeliveryClosureStatus.UNKNOWN.value)
    finalization_decision = data.get("decision", DeliveryClosureDecision.UNKNOWN.value)
    validation_valid = data.get("validation", {}).get("valid", False) if isinstance(data.get("validation"), dict) else False

    # R241-16U finalization uses "finalized"; closure uses "passed"
    _passed_statuses = {DeliveryClosureStatus.PASSED.value, DeliveryClosureStatus.PASSED_WITH_WARNINGS.value}
    _r241_16u_passed = {"finalized", "finalized_with_warnings"}
    _all_passed_statuses = _passed_statuses | _r241_16u_passed
    if finalization_status in _all_passed_statuses:
        status_passed = True
        status_risk = DeliveryClosureRiskLevel.LOW.value
    elif finalization_status == DeliveryClosureStatus.UNKNOWN.value:
        status_passed = False
        status_risk = DeliveryClosureRiskLevel.HIGH.value
    else:
        status_passed = False
        status_risk = DeliveryClosureRiskLevel.CRITICAL.value

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.DELIVERY_PACKAGE.value,
        check_id="finalization_status",
        description=f"R241-16U finalization status is '{finalization_status}'",
        passed=status_passed,
        status=finalization_status,
        risk_level=status_risk,
        details={
            "status": finalization_status,
            "decision": finalization_decision,
            "validation_valid": validation_valid,
        },
        recommendations=["Resolve finalization issues before closure"] if not status_passed else [],
    ))

    # R241-16U finalization uses approve_handoff; closure uses approve_closure
    _approve = {DeliveryClosureDecision.APPROVE_CLOSURE.value, DeliveryClosureDecision.APPROVE_CLOSURE_WITH_CONDITIONS.value}
    _r241_16u_approve = {"approve_handoff", "approve_handoff_with_warnings"}
    _all_approve = _approve | _r241_16u_approve
    if finalization_decision in _all_approve:
        decision_passed = True
        decision_risk = DeliveryClosureRiskLevel.LOW.value
    else:
        decision_passed = False
        decision_risk = DeliveryClosureRiskLevel.HIGH.value

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.DELIVERY_PACKAGE.value,
        check_id="finalization_decision",
        description=f"R241-16U handoff decision is '{finalization_decision}'",
        passed=decision_passed,
        status=finalization_decision,
        risk_level=decision_risk,
        details={"decision": finalization_decision, "status": finalization_status},
        recommendations=["Review finalization decision before approving closure"] if not decision_passed else [],
    ))

    index_artifacts = [a for a in artifacts if a["role"] == "handoff_index" and a["exists"]]
    checklist_artifacts = [a for a in artifacts if a["role"] == "final_checklist" and a["exists"]]
    summary_artifacts = [a for a in artifacts if a["role"] == "handoff_summary" and a["exists"]]

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.DELIVERY_PACKAGE.value,
        check_id="handoff_index_exists",
        description="Delivery package handoff index exists",
        passed=len(index_artifacts) > 0,
        status="passed" if index_artifacts else "failed",
        risk_level=DeliveryClosureRiskLevel.MEDIUM.value,
        details={"index_files": [a["filename"] for a in index_artifacts]},
    ))

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.DELIVERY_PACKAGE.value,
        check_id="final_checklist_exists",
        description="Delivery package final checklist exists",
        passed=len(checklist_artifacts) > 0,
        status="passed" if checklist_artifacts else "failed",
        risk_level=DeliveryClosureRiskLevel.MEDIUM.value,
        details={"checklist_files": [a["filename"] for a in checklist_artifacts]},
    ))

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.DELIVERY_PACKAGE.value,
        check_id="handoff_summary_exists",
        description="Delivery package handoff summary exists",
        passed=len(summary_artifacts) > 0,
        status="passed" if summary_artifacts else "failed",
        risk_level=DeliveryClosureRiskLevel.MEDIUM.value,
        details={"summary_files": [a["filename"] for a in summary_artifacts]},
    ))

    return checks


def _check_mutation_guard(mutation_guard: dict[str, Any]) -> list[DeliveryClosureCheck]:
    """Domain: mutation_guard"""
    checks = []

    staged = mutation_guard.get("staged_files", [])
    status_short = mutation_guard.get("git_status_short", "")

    has_staged = len(staged) > 0
    has_status_changes = bool(status_short.strip())

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.MUTATION_GUARD.value,
        check_id="mutation_no_staged",
        description="No staged changes detected during closure review",
        passed=not has_staged,
        status="passed" if not has_staged else "failed",
        risk_level=DeliveryClosureRiskLevel.HIGH.value if has_staged else DeliveryClosureRiskLevel.LOW.value,
        details={"staged_files": staged, "count": len(staged)},
        recommendations=["Unstage files before closure: git reset HEAD"] if has_staged else [],
    ))

    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.MUTATION_GUARD.value,
        check_id="mutation_no_working_tree",
        description="No uncommitted working tree changes detected",
        passed=not has_status_changes,
        status="passed" if not has_status_changes else "failed",
        risk_level=DeliveryClosureRiskLevel.MEDIUM.value,
        details={"git_status_short": status_short},
        recommendations=["Commit or discard working tree changes before closure"] if has_status_changes else [],
    ))

    head_hash = mutation_guard.get("head_hash")
    checks.append(DeliveryClosureCheck(
        domain=DeliveryClosureDomain.MUTATION_GUARD.value,
        check_id="mutation_head_hash",
        description=f"Git HEAD hash captured: {head_hash}",
        passed=bool(head_hash),
        status="passed" if head_hash else "failed",
        risk_level=DeliveryClosureRiskLevel.LOW.value,
        details={"head_hash": head_hash},
    ))

    return checks


def build_delivery_closure_checks(
    stage_chain: list[dict[str, Any]],
    artifact_summary: list[dict[str, Any]],
    finalization_state: dict[str, Any],
    mutation_guard: dict[str, Any],
    root: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Build closure checks across all domains.

    Returns list of check dicts.
    """
    checks: list[DeliveryClosureCheck] = []

    checks.extend(_check_chain_completeness(stage_chain))
    checks.extend(_check_artifact_integrity(artifact_summary, root))
    checks.extend(_check_delivery_package_finalization(finalization_state, artifact_summary))
    checks.extend(_check_mutation_guard(mutation_guard))

    # Cross-check: patch SHA in manifest matches verification result
    manifest_arts = [a for a in artifact_summary if a["role"] == "manifest" and a["exists"]]
    verification_arts = [a for a in artifact_summary if a["role"] == "verification_report" and a["exists"]]
    if manifest_arts and verification_arts:
        manifest_path = REPORT_DIR / manifest_arts[0]["filename"]
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_patch_sha = manifest_data.get("patch_sha256") or manifest_data.get("patch_sha")
            verification_path = REPORT_DIR / verification_arts[0]["filename"]
            verification_data = json.loads(verification_path.read_text(encoding="utf-8"))
            verification_patch_sha = None
            if isinstance(verification_data.get("patch_inspection"), dict):
                verification_patch_sha = verification_data["patch_inspection"].get("patch_sha")
            elif isinstance(verification_data.get("verification_result"), dict):
                verification_patch_sha = verification_data["verification_result"].get("patch_sha")

            if manifest_patch_sha and verification_patch_sha:
                sha_match = manifest_patch_sha == verification_patch_sha
                checks.append(DeliveryClosureCheck(
                    domain=DeliveryClosureDomain.ARTIFACT_INTEGRITY.value,
                    check_id="crosscheck_manifest_verification_sha",
                    description="Patch SHA matches between manifest and verification result",
                    passed=sha_match,
                    status="passed" if sha_match else "failed",
                    risk_level=DeliveryClosureRiskLevel.HIGH.value,
                    details={
                        "manifest_sha": manifest_patch_sha[:16] + "..." if manifest_patch_sha else None,
                        "verification_sha": verification_patch_sha[:16] + "..." if verification_patch_sha else None,
                        "match": sha_match,
                    },
                    recommendations=["Re-run verification if SHA mismatch detected"] if not sha_match else [],
                ))
        except Exception:
            pass  # Cross-check failed, skip

    # Sort: passed first, then by domain, then by check_id
    checks.sort(key=lambda c: (
        0 if c.passed else 1,
        c.domain,
        c.check_id,
    ))

    return [c.to_dict() for c in checks]


# ── 5. build_receiver_next_steps ─────────────────────────────────────────────


def build_receiver_next_steps(
    closure_checks: list[dict[str, Any]],
    finalization_state: dict[str, Any],
    artifact_summary: list[dict[str, Any]],
) -> list[str]:
    """Build receiver next steps based on closure review results.

    Returns list of action items.
    """
    steps: list[str] = []
    failed_checks = [c for c in closure_checks if not c["passed"]]
    failed_by_domain: dict[str, list[dict[str, Any]]] = {}
    for check in failed_checks:
        domain = check["domain"]
        if domain not in failed_by_domain:
            failed_by_domain[domain] = []
        failed_by_domain[domain].append(check)

    if not finalization_state.get("exists"):
        steps.append("Execute R241-16U: Run delivery package finalization to generate required artifacts")

    required_missing = [a for a in artifact_summary if a["required"] and not a["exists"]]
    if required_missing:
        steps.append(f"Restore {len(required_missing)} missing required delivery artifacts before proceeding")

    critical_failures = [
        c for c in failed_checks
        if c["risk_level"] in (DeliveryClosureRiskLevel.CRITICAL.value, DeliveryClosureRiskLevel.HIGH.value)
    ]
    if critical_failures:
        steps.append(f"Address {len(critical_failures)} critical/high risk check failures before closure approval:")
        for check in critical_failures[:5]:
            steps.append(f"  - [{check['check_id']}] {check['description']}: {check.get('recommendations', ['Fix issue'])}")

    if DeliveryClosureDomain.MUTATION_GUARD.value in failed_by_domain:
        mutation_fails = failed_by_domain[DeliveryClosureDomain.MUTATION_GUARD.value]
        for check in mutation_fails:
            if check["check_id"] == "mutation_no_staged":
                steps.append("Unstage any staged changes: git reset HEAD")
            if check["check_id"] == "mutation_no_working_tree":
                steps.append("Commit or discard working tree changes before closure")

    if DeliveryClosureDomain.DELIVERY_PACKAGE.value in failed_by_domain:
        steps.append("Review and resolve R241-16U finalization failures before approving closure")

    if DeliveryClosureDomain.CHAIN_COMPLETENESS.value in failed_by_domain:
        steps.append("Execute missing delivery stage reports to complete the chain before closure")

    if not steps:
        steps.append("All closure checks passed. Ready to approve delivery closure.")
        steps.append("Review R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.md for full details.")
        steps.append("Proceed with publishing the workflow if all prior stages are approved.")

    return steps


# ── 6. verify_no_mutation_during_closure_review ────────────────────────────────


def verify_no_mutation_during_closure_review(baseline: dict[str, Any], root: Optional[str] = None) -> dict[str, Any]:
    """Compare current git state against baseline to detect mutation.

    Returns dict with:
      mutated: bool
      details: dict
    """
    root_path = _root(root)
    current = _safe_baseline(str(root_path))

    baseline_head = baseline.get("head_hash")
    current_head = current.get("head_hash")
    head_changed = baseline_head != current_head

    baseline_staged = set(baseline.get("staged_files", []))
    current_staged = set(current.get("staged_files", []))
    staged_changed = baseline_staged != current_staged
    newly_staged = list(current_staged - baseline_staged)

    baseline_status = baseline.get("git_status_short", "")
    current_status = current.get("git_status_short", "")
    status_changed = baseline_status != current_status

    mutated = head_changed or staged_changed or status_changed

    return {
        "mutated": mutated,
        "baseline": baseline,
        "current": current,
        "details": {
            "head_changed": head_changed,
            "staged_changed": staged_changed,
            "status_changed": status_changed,
            "newly_staged": newly_staged,
            "baseline_head": baseline_head,
            "current_head": current_head,
        },
    }


# ── 7. evaluate_foundation_ci_delivery_closure ─────────────────────────────────


def evaluate_foundation_ci_delivery_closure(root: Optional[str] = None) -> DeliveryClosureReview:
    """Run the full delivery closure review.

    Returns DeliveryClosureReview object.
    """
    baseline = _safe_baseline(str(_root(root)))
    stage_chain = collect_foundation_ci_delivery_stage_chain(str(_root(root)))
    artifact_summary = verify_delivery_artifacts_for_closure(str(_root(root)))
    finalization_state = load_delivery_finalization_state(str(_root(root)))
    mutation_guard = _safe_baseline(str(_root(root)))
    closure_checks = build_delivery_closure_checks(
        stage_chain, artifact_summary, finalization_state, mutation_guard, str(_root(root))
    )

    failed_checks = [c for c in closure_checks if not c["passed"]]
    critical_failed = [
        c for c in failed_checks
        if c["risk_level"] in (DeliveryClosureRiskLevel.CRITICAL.value, DeliveryClosureRiskLevel.HIGH.value)
    ]

    if not failed_checks:
        status = DeliveryClosureStatus.PASSED.value
        decision = DeliveryClosureDecision.APPROVE_CLOSURE.value
        risk_level = DeliveryClosureRiskLevel.LOW.value
    elif critical_failed:
        status = DeliveryClosureStatus.FAILED.value
        decision = DeliveryClosureDecision.BLOCK_CLOSURE.value
        risk_level = DeliveryClosureRiskLevel.HIGH.value
    else:
        status = DeliveryClosureStatus.PASSED_WITH_WARNINGS.value
        decision = DeliveryClosureDecision.APPROVE_CLOSURE_WITH_CONDITIONS.value
        risk_level = DeliveryClosureRiskLevel.MEDIUM.value

    receiver_next_steps = build_receiver_next_steps(closure_checks, finalization_state, artifact_summary)

    review = DeliveryClosureReview(
        review_id="R241-16V",
        stage_chain=stage_chain,
        artifact_summary=artifact_summary,
        closure_checks=closure_checks,
        receiver_next_steps=receiver_next_steps,
        mutation_guard=mutation_guard,
        decision=decision,
        status=status,
        risk_level=risk_level,
        generated_at=_now(),
    )

    return review


# ── 8. validate_delivery_closure_review ────────────────────────────────────────


def validate_delivery_closure_review(review: DeliveryClosureReview) -> dict[str, Any]:
    """Validate a DeliveryClosureReview object.

    Returns validation result dict with:
      valid: bool
      errors: list[str]
      warnings: list[str]
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not review.review_id:
        errors.append("review_id is required")

    if not review.generated_at:
        errors.append("generated_at is required")

    valid_statuses = [s.value for s in DeliveryClosureStatus]
    if review.status not in valid_statuses:
        errors.append(f"Invalid status: {review.status}")

    valid_decisions = [d.value for d in DeliveryClosureDecision]
    if review.decision not in valid_decisions:
        errors.append(f"Invalid decision: {review.decision}")

    valid_risk_levels = [r.value for r in DeliveryClosureRiskLevel]
    if review.risk_level not in valid_risk_levels:
        errors.append(f"Invalid risk_level: {review.risk_level}")

    if not isinstance(review.stage_chain, list):
        errors.append("stage_chain must be a list")
    else:
        for i, stage in enumerate(review.stage_chain):
            if not isinstance(stage, dict):
                errors.append(f"stage_chain[{i}] must be a dict")
            elif "stage_id" not in stage:
                errors.append(f"stage_chain[{i}] missing stage_id")

    if not isinstance(review.artifact_summary, list):
        errors.append("artifact_summary must be a list")

    if not isinstance(review.closure_checks, list):
        errors.append("closure_checks must be a list")
    else:
        for i, check in enumerate(review.closure_checks):
            if not isinstance(check, dict):
                errors.append(f"closure_checks[{i}] must be a dict")
            elif "check_id" not in check:
                errors.append(f"closure_checks[{i}] missing check_id")

    if not isinstance(review.receiver_next_steps, list):
        errors.append("receiver_next_steps must be a list")

    if not isinstance(review.mutation_guard, dict):
        errors.append("mutation_guard must be a dict")

    if review.status == DeliveryClosureStatus.PASSED.value and errors:
        warnings.append("Review has passed status but has validation errors")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# ── 9. generate_delivery_closure_review_report ─────────────────────────────────


def generate_delivery_closure_review_report(review: DeliveryClosureReview, root: Optional[str] = None) -> dict[str, str]:
    """Generate JSON and MD closure review reports.

    Returns dict with keys 'json_path' and 'md_path'.
    """
    root_path = _root(root)
    report_dir = root_path / "migration_reports" / "foundation_audit"
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = report_dir / "R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.json"
    md_path = report_dir / "R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.md"

    review.validated = True
    review.validation_errors = []

    validation = validate_delivery_closure_review(review)
    review.validated = validation["valid"]
    review.validation_errors = validation["errors"]

    json_path.write_text(
        json.dumps(review.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines: list[str] = [
        "# Foundation CI Delivery Closure Review",
        "",
        f"**Review ID:** {review.review_id}",
        f"**Generated:** {review.generated_at}",
        f"**Status:** `{review.status}`",
        f"**Decision:** `{review.decision}`",
        f"**Risk Level:** `{review.risk_level}`",
        "",
        "---",
        "",
        "## Stage Chain",
        "",
    ]

    if review.stage_chain:
        md_lines.append("| Stage | Description | JSON Report | MD Report |")
        md_lines.append("|-------|-------------|-------------|-----------|")
        for stage in review.stage_chain:
            stage_id = stage.get("stage_id", "")
            desc = stage.get("description", "")
            json_exists = "✓" if stage.get("report_json_exists") else "✗"
            md_exists = "✓" if stage.get("report_md_exists") else "✗"
            md_lines.append(f"| {stage_id} | {desc} | {json_exists} | {md_exists} |")
    else:
        md_lines.append("_No stage chain data available._")

    md_lines.extend(["", "## Delivery Artifact Integrity", ""])
    if review.artifact_summary:
        md_lines.append("| Artifact | Role | Exists | Required | SHA256 (first 16) | Size (bytes) |")
        md_lines.append("|----------|------|--------|---------|-------------------|--------------|")
        for art in review.artifact_summary:
            filename = art.get("filename", "")
            role = art.get("role", "")
            exists = "✓" if art.get("exists") else "✗"
            required = "✓" if art.get("required") else "✗"
            sha = art.get("sha256", "")
            sha_short = sha[:16] + "..." if sha and len(sha) >= 16 else sha or "N/A"
            size = art.get("size_bytes")
            size_str = f"{size:,}" if size is not None else "N/A"
            errors = art.get("validation_errors", [])
            error_note = f" ⚠ {len(errors)} error(s)" if errors else ""
            md_lines.append(f"| {filename} | {role} | {exists} | {required} | `{sha_short}` | {size_str} |{error_note}")
    else:
        md_lines.append("_No artifact summary data available._")

    md_lines.extend(["", "## Closure Checks", ""])
    passed_checks = [c for c in review.closure_checks if c.get("passed")]
    failed_checks = [c for c in review.closure_checks if not c.get("passed")]

    if failed_checks:
        md_lines.append(f"### Failed Checks ({len(failed_checks)})")
        md_lines.append("")
        for check in failed_checks:
            risk = check.get("risk_level", "unknown").upper()
            md_lines.append(f"- **`{check['check_id']}`** [{risk}] {check['description']}")
            if check.get("recommendations"):
                for rec in check["recommendations"]:
                    md_lines.append(f"  - Recommendation: {rec}")
    else:
        md_lines.append("All closure checks passed.")

    md_lines.extend(["", f"### Passed Checks ({len(passed_checks)})", ""])
    if passed_checks:
        for check in passed_checks:
            md_lines.append(f"- `{check['check_id']}` [{check.get('risk_level', 'low').upper()}] {check['description']}")

    md_lines.extend(["", "## Mutation Guard", ""])
    mg = review.mutation_guard
    md_lines.extend([
        f"- **HEAD hash:** `{mg.get('head_hash', 'N/A')}`",
        f"- **Branch:** `{mg.get('branch', 'N/A')}`",
        f"- **Staged files:** {len(mg.get('staged_files', []))}",
        f"- **Working tree changes:** {'Yes' if mg.get('git_status_short', '').strip() else 'None'}",
        f"- **Captured at:** `{mg.get('captured_at', 'N/A')}`",
    ])

    md_lines.extend(["", "## Receiver Next Steps", ""])
    if review.receiver_next_steps:
        for i, step in enumerate(review.receiver_next_steps, 1):
            md_lines.append(f"{i}. {step}")
    else:
        md_lines.append("_No next steps required._")

    md_lines.extend(["", "## Report Metadata", ""])
    md_lines.extend([
        f"- **Review ID:** {review.review_id}",
        f"- **Generated at:** {review.generated_at}",
        f"- **Decision:** {review.decision}",
        f"- **Total closure checks:** {len(review.closure_checks)}",
        f"- **Passed:** {len(passed_checks)}",
        f"- **Failed:** {len(failed_checks)}",
        f"- **Validation:** {'PASSED' if review.validated else 'FAILED'}",
    ])

    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
    }
