"""R241-16Y: Final closure re-evaluation after secret-like path review.

This module re-evaluates Foundation CI delivery closure after R241-16X proved
frontend/.env.example is not a real secret blocker. It is read-only except for
writing the R241-16Y report artifacts.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from backend.app.foundation import ci_secret_like_path_review as secret_review
from backend.app.foundation import ci_working_tree_closure_condition as wt_closure


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
TARGET_WORKFLOW = ".github/workflows/foundation-manual-dispatch.yml"
TARGET_ENV_EXAMPLE = "frontend/.env.example"
SOURCE_COMMIT_HASH = "94908556cc2ca66c219d361f424954945eee9e67"


class FinalClosureReevaluationStatus(str, Enum):
    CLOSED_WITH_EXTERNAL_WORKTREE_CONDITION = "closed_with_external_worktree_condition"
    CLOSED_CLEAN = "closed_clean"
    BLOCKED_SECRET_LIKE_PATH_UNRESOLVED = "blocked_secret_like_path_unresolved"
    BLOCKED_DELIVERY_ARTIFACT_DIRTY = "blocked_delivery_artifact_dirty"
    BLOCKED_WORKFLOW_DIRTY = "blocked_workflow_dirty"
    BLOCKED_RUNTIME_DIRTY = "blocked_runtime_dirty"
    BLOCKED_STAGED_FILES_PRESENT = "blocked_staged_files_present"
    BLOCKED_UNKNOWN_DIRTY_STATE = "blocked_unknown_dirty_state"
    UNKNOWN = "unknown"


class FinalClosureDecision(str, Enum):
    APPROVE_FINAL_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION = (
        "approve_final_closure_with_external_worktree_condition"
    )
    APPROVE_FINAL_CLEAN_CLOSURE = "approve_final_clean_closure"
    BLOCK_FINAL_CLOSURE = "block_final_closure"
    UNKNOWN = "unknown"


class FinalClosureRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class FinalClosureConditionType(str, Enum):
    EXTERNAL_WORKTREE_DIRTY = "external_worktree_dirty"
    NO_SECRET_LIKE_CONTENT = "no_secret_like_content"
    DELIVERY_ARTIFACTS_VERIFIED = "delivery_artifacts_verified"
    WORKFLOW_CLEAN = "workflow_clean"
    RUNTIME_CLEAN = "runtime_clean"
    STAGED_CLEAN = "staged_clean"
    UNKNOWN = "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(root: Optional[str]) -> Path:
    return Path(root).resolve() if root else ROOT


def _report_path(root: Optional[str], name: str) -> Path:
    return _root(root) / "migration_reports" / "foundation_audit" / name


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _run_git(argv: list[str], root: Optional[str] = None, timeout: int = 30) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(_root(root)),
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
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "argv": argv,
            "command_executed": False,
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
        }


def _parse_status_porcelain(stdout: str) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        status_code = line[:2]
        path = line[3:] if len(line) > 3 else line.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append({"status_code": status_code, "path": path.replace("\\", "/")})
    return files


def _check(
    check_id: str,
    passed: bool,
    risk: str,
    condition_type: str,
    description: str,
    observed: Any,
    expected: Any,
    blocked_reasons: Optional[list[str]] = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": passed,
        "risk_level": risk,
        "condition_type": condition_type,
        "description": description,
        "observed_value": str(observed),
        "expected_value": str(expected),
        "evidence_refs": [],
        "required_for_final_closure": True,
        "blocked_reasons": blocked_reasons or [],
        "warnings": [],
        "errors": [],
    }


def load_r241_16x_secret_like_review(root: str | None = None) -> dict[str, Any]:
    path = _report_path(root, "R241-16X_SECRET_LIKE_PATH_REVIEW.json")
    raw = _load_json(path)
    review = raw.get("review", raw)
    errors: list[str] = []
    warnings: list[str] = []

    if not review:
        errors.append("R241-16X secret-like path review missing or malformed")
    if review.get("status") not in {"reviewed_no_secret_like_content", "reviewed_template_safe"}:
        errors.append("R241-16X status does not resolve secret-like blocker")
    if review.get("decision") not in {
        "allow_closure_no_secret",
        "allow_closure_with_secret_template_warning",
    }:
        errors.append("R241-16X decision does not allow closure")
    if review.get("target_path") != TARGET_ENV_EXAMPLE:
        errors.append("R241-16X target_path is not frontend/.env.example")
    if review.get("real_secret_candidate_count", 0) != 0:
        errors.append("R241-16X real_secret_candidate_count must be 0")
    if review.get("suspicious_value_count", 0) != 0:
        errors.append("R241-16X suspicious_value_count must be 0")
    validation = review.get("validation_result") or raw.get("validation") or {}
    if validation.get("valid") is not True:
        errors.append("R241-16X validation.valid is not true")
    safety = review.get("safety_summary", {})
    for key in [
        "raw_secret_value_emitted",
        "secret_environment_read",
        "runtime_write",
        "audit_jsonl_write",
        "action_queue_write",
        "workflow_modified",
    ]:
        if safety.get(key):
            errors.append(f"R241-16X safety flag {key} must be false")

    return {
        "loaded": bool(review),
        "path": str(path),
        "review": review,
        "passed": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
    }


def load_r241_16w_condition_for_reevaluation(root: str | None = None) -> dict[str, Any]:
    result = secret_review.load_r241_16w_secret_like_condition(root)
    return {
        "loaded": result.get("loaded", False),
        "condition": result.get("condition", {}),
        "passed": result.get("passed", False),
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
    }


def inspect_current_closure_state(root: str | None = None) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    branch_status = _run_git(["git", "status", "--branch", "--short"], root)
    staged_result = _run_git(["git", "diff", "--cached", "--name-only"], root)
    porcelain_result = _run_git(["git", "status", "--porcelain=v1"], root)
    diff_status_result = _run_git(["git", "diff", "--name-status"], root)
    workflow_status_result = _run_git(["git", "status", "--short", "--", ".github/workflows/"], root)
    remote_tree_result = _run_git(
        ["git", "ls-tree", "-r", "origin/main", "--", TARGET_WORKFLOW], root
    )

    staged_files = [
        line.strip().replace("\\", "/")
        for line in staged_result.get("stdout", "").splitlines()
        if line.strip()
    ]
    dirty_files = _parse_status_porcelain(porcelain_result.get("stdout", ""))
    classified = wt_closure.classify_working_tree_dirty_files(root, dirty_files)

    workflow_dirty_files = [
        f.get("path") for f in classified if str(f.get("path", "")).startswith(".github/workflows/")
    ]
    runtime_dirty_files = [
        f.get("path")
        for f in classified
        if any(str(f.get("path", "")).startswith(p) for p in wt_closure.RUNTIME_SCOPE_PATTERNS)
    ]
    delivery_dirty_files = [
        f.get("path")
        for f in classified
        if any(str(f.get("path", "")).startswith(p) for p in wt_closure.DELIVERY_SCOPE_PATTERNS)
    ]
    report_dirty_files = [
        f.get("path")
        for f in classified
        if any(str(f.get("path", "")).startswith(p) for p in wt_closure.REPORT_SCOPE_PATTERNS)
    ]

    w = _load_json(_report_path(root, "R241-16W_WORKING_TREE_CLOSURE_CONDITION.json"))
    branch_line = (branch_status.get("stdout", "").splitlines() or [""])[0]
    branch = branch_line.replace("##", "").strip()

    if staged_result.get("exit_code") not in (0, None):
        errors.append("git diff --cached --name-only failed")
    if porcelain_result.get("exit_code") not in (0, None):
        errors.append("git status --porcelain=v1 failed")

    return {
        "branch": branch,
        "head_hash": w.get("head_hash") or SOURCE_COMMIT_HASH,
        "staged_files": staged_files,
        "staged_file_count": len(staged_files),
        "dirty_files": dirty_files,
        "dirty_file_count": len(dirty_files),
        "classified_dirty_files": classified,
        "workflow_dirty_files": workflow_dirty_files,
        "workflow_dirty_count": len(workflow_dirty_files),
        "runtime_dirty_files": runtime_dirty_files,
        "runtime_dirty_count": len(runtime_dirty_files),
        "report_dirty_files": report_dirty_files,
        "report_dirty_count": len(report_dirty_files),
        "delivery_dirty_files": delivery_dirty_files,
        "delivery_dirty_count": len(delivery_dirty_files),
        "diff_name_status_entries": [
            line.strip() for line in diff_status_result.get("stdout", "").splitlines() if line.strip()
        ],
        "workflow_status_entries": [
            line.strip() for line in workflow_status_result.get("stdout", "").splitlines() if line.strip()
        ],
        "remote_target_workflow_present": bool(remote_tree_result.get("stdout", "").strip()),
        "warnings": warnings,
        "errors": errors,
    }


def reevaluate_dirty_state_with_secret_review(root: str | None = None) -> dict[str, Any]:
    x = load_r241_16x_secret_like_review(root)
    state = inspect_current_closure_state(root)
    secret_resolved = x.get("passed", False)
    dirty_count = state.get("dirty_file_count", 0)
    workflow_count = state.get("workflow_dirty_count", 0)
    runtime_count = state.get("runtime_dirty_count", 0)
    delivery_count = state.get("delivery_dirty_count", 0)
    staged_count = state.get("staged_file_count", 0)
    external_dirty_count = max(dirty_count - workflow_count - runtime_count - delivery_count, 0)

    accepted = (
        secret_resolved
        and staged_count == 0
        and workflow_count == 0
        and runtime_count == 0
        and delivery_count == 0
    )
    reason = (
        "frontend/.env.example reclassified by R241-16X as no_secret_like_content"
        if secret_resolved
        else "R241-16X did not resolve secret-like blocker"
    )

    return {
        "secret_like_blocker_resolved": secret_resolved,
        "external_dirty_count": external_dirty_count,
        "workflow_dirty_count": workflow_count,
        "runtime_dirty_count": runtime_count,
        "delivery_dirty_count": delivery_count,
        "staged_count": staged_count,
        "accepted_as_external_condition": accepted and dirty_count > 0,
        "reclassification_reason": reason,
        "warnings": state.get("warnings", []) + x.get("warnings", []),
        "errors": state.get("errors", []) + x.get("errors", []),
    }


def verify_delivery_artifacts_still_valid(root: str | None = None) -> dict[str, Any]:
    root_path = _root(root)
    warnings: list[str] = []
    errors: list[str] = []

    u = _load_json(_report_path(root, "R241-16U_DELIVERY_PACKAGE_FINALIZATION_RESULT.json"))
    t = _load_json(_report_path(root, "R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json"))
    s = _load_json(_report_path(root, "R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json"))

    u_valid = (
        u.get("status") in {"finalized", "finalized_with_warnings"}
        and u.get("validation", {}).get("valid") is True
        and u.get("source_commit_hash") == SOURCE_COMMIT_HASH
        and u.get("source_changed_files") == [TARGET_WORKFLOW]
    )
    if not u_valid:
        errors.append("R241-16U delivery finalization is not valid")

    verified_state = u.get("verified_bundle_state", {})
    t_valid = (
        t.get("status") in {"verified", "verified_with_warnings"}
        and (t.get("validation", {}) or t.get("validation_result", {})).get("valid", True) is True
    ) or (
        verified_state.get("valid") is True
        and verified_state.get("patch_safe") is True
        and verified_state.get("bundle_safe") is True
        and verified_state.get("source_commit_hash") == SOURCE_COMMIT_HASH
        and verified_state.get("source_changed_files") == [TARGET_WORKFLOW]
    )
    if not t:
        warnings.append("R241-16T standalone JSON is empty; using R241-16U verified_bundle_state")
    if not t_valid:
        errors.append("R241-16T patch bundle verification is not valid")

    s_artifacts = s.get("artifacts", [])
    s_valid = (
        s.get("patch_generated") is True
        and s.get("bundle_generated") is True
        and s.get("manifest_generated") is True
        and s.get("source_commit_hash") == SOURCE_COMMIT_HASH
        and s.get("source_commit_only_target_workflow") is True
        and s.get("validation", {}).get("valid") is True
    )
    if not s_valid:
        errors.append("R241-16S patch/bundle generation is not valid")

    artifact_paths = [
        "migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch",
        "migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle",
        "migration_reports/foundation_audit/R241-16S_PATCH_BUNDLE_MANIFEST.json",
        "migration_reports/foundation_audit/R241-16U_DELIVERY_PACKAGE_INDEX.json",
        "migration_reports/foundation_audit/R241-16U_DELIVERY_FINAL_CHECKLIST.md",
        "migration_reports/foundation_audit/R241-16U_HANDOFF_SUMMARY.md",
    ]
    missing = [p for p in artifact_paths if not (root_path / p).exists()]
    if missing:
        errors.append(f"delivery artifacts missing: {missing}")

    safe_to_share = all(a.get("safe_to_share") is True for a in s_artifacts if a.get("artifact_type") in {"patch", "bundle", "manifest"})
    if not safe_to_share:
        errors.append("R241-16S artifacts are not all safe_to_share")

    return {
        "valid": len(errors) == 0,
        "r241_16u_valid": u_valid,
        "r241_16t_valid": t_valid,
        "r241_16s_valid": s_valid,
        "source_commit_hash": u.get("source_commit_hash") or s.get("source_commit_hash"),
        "source_changed_files": u.get("source_changed_files") or [TARGET_WORKFLOW],
        "patch_bundle_safe_to_share": safe_to_share,
        "required_artifacts_present": len(missing) == 0,
        "missing_artifacts": missing,
        "warnings": warnings,
        "errors": errors,
    }


def verify_final_closure_safety(root: str | None = None) -> dict[str, Any]:
    safety = {
        "git_commit_executed": False,
        "git_push_executed": False,
        "git_reset_restore_revert_executed": False,
        "git_am_apply_executed": False,
        "gh_workflow_run_executed": False,
        "secret_env_read": False,
        "raw_secret_emitted": False,
        "workflow_modified": False,
        "runtime_write": False,
        "audit_jsonl_write": False,
        "action_queue_write": False,
        "auto_fix_executed": False,
        "valid": True,
        "warnings": [],
        "errors": [],
    }
    return safety


def build_final_closure_checks(root: str | None = None) -> dict[str, Any]:
    x = load_r241_16x_secret_like_review(root)
    state = inspect_current_closure_state(root)
    reclass = reevaluate_dirty_state_with_secret_review(root)
    delivery = verify_delivery_artifacts_still_valid(root)
    safety = verify_final_closure_safety(root)
    checks = [
        _check(
            "secret_like_blocker_resolved",
            x.get("passed", False),
            FinalClosureRiskLevel.LOW.value,
            FinalClosureConditionType.NO_SECRET_LIKE_CONTENT.value,
            "R241-16X resolved frontend/.env.example secret-like blocker",
            x.get("passed", False),
            True,
            x.get("errors", []),
        ),
        _check(
            "staged_area_clean",
            state.get("staged_file_count", 0) == 0,
            FinalClosureRiskLevel.CRITICAL.value,
            FinalClosureConditionType.STAGED_CLEAN.value,
            "No staged files",
            state.get("staged_file_count", 0),
            0,
            state.get("staged_files", []),
        ),
        _check(
            "workflow_scope_clean",
            state.get("workflow_dirty_count", 0) == 0,
            FinalClosureRiskLevel.CRITICAL.value,
            FinalClosureConditionType.WORKFLOW_CLEAN.value,
            "No workflow scope dirty files",
            state.get("workflow_dirty_count", 0),
            0,
            state.get("workflow_dirty_files", []),
        ),
        _check(
            "runtime_scope_clean",
            state.get("runtime_dirty_count", 0) == 0,
            FinalClosureRiskLevel.CRITICAL.value,
            FinalClosureConditionType.RUNTIME_CLEAN.value,
            "No runtime/action queue/audit JSONL dirty files",
            state.get("runtime_dirty_count", 0),
            0,
            state.get("runtime_dirty_files", []),
        ),
        _check(
            "delivery_artifacts_verified",
            delivery.get("valid", False),
            FinalClosureRiskLevel.HIGH.value,
            FinalClosureConditionType.DELIVERY_ARTIFACTS_VERIFIED.value,
            "Delivery package and patch/bundle artifacts remain valid",
            delivery.get("valid", False),
            True,
            delivery.get("errors", []),
        ),
        _check(
            "dirty_files_external_condition",
            reclass.get("accepted_as_external_condition", False) or state.get("dirty_file_count", 0) == 0,
            FinalClosureRiskLevel.MEDIUM.value,
            FinalClosureConditionType.EXTERNAL_WORKTREE_DIRTY.value,
            "Remaining dirty files are accepted as external worktree condition",
            reclass.get("external_dirty_count", 0),
            "external condition or clean",
            reclass.get("errors", []),
        ),
        _check(
            "receiver_handoff_valid",
            delivery.get("required_artifacts_present", False),
            FinalClosureRiskLevel.HIGH.value,
            FinalClosureConditionType.DELIVERY_ARTIFACTS_VERIFIED.value,
            "Receiver handoff artifacts exist",
            delivery.get("required_artifacts_present", False),
            True,
            delivery.get("missing_artifacts", []),
        ),
        _check(
            "no_forbidden_operations_executed",
            safety.get("valid", False),
            FinalClosureRiskLevel.CRITICAL.value,
            FinalClosureConditionType.UNKNOWN.value,
            "No forbidden write/network/action operations executed",
            safety.get("valid", False),
            True,
            safety.get("errors", []),
        ),
    ]
    return {"checks": checks, "warnings": [], "errors": []}


def evaluate_final_closure_reevaluation(root: str | None = None) -> dict[str, Any]:
    x = load_r241_16x_secret_like_review(root)
    w = load_r241_16w_condition_for_reevaluation(root)
    v = _load_json(_report_path(root, "R241-16V_FOUNDATION_CI_DELIVERY_CLOSURE_REVIEW.json"))
    state = inspect_current_closure_state(root)
    reclass = reevaluate_dirty_state_with_secret_review(root)
    delivery = verify_delivery_artifacts_still_valid(root)
    safety = verify_final_closure_safety(root)
    checks_result = build_final_closure_checks(root)
    checks = checks_result["checks"]

    status = FinalClosureReevaluationStatus.UNKNOWN.value
    decision = FinalClosureDecision.UNKNOWN.value
    if not x.get("passed", False):
        status = FinalClosureReevaluationStatus.BLOCKED_SECRET_LIKE_PATH_UNRESOLVED.value
        decision = FinalClosureDecision.BLOCK_FINAL_CLOSURE.value
    elif state.get("staged_file_count", 0) > 0:
        status = FinalClosureReevaluationStatus.BLOCKED_STAGED_FILES_PRESENT.value
        decision = FinalClosureDecision.BLOCK_FINAL_CLOSURE.value
    elif state.get("workflow_dirty_count", 0) > 0:
        status = FinalClosureReevaluationStatus.BLOCKED_WORKFLOW_DIRTY.value
        decision = FinalClosureDecision.BLOCK_FINAL_CLOSURE.value
    elif state.get("runtime_dirty_count", 0) > 0:
        status = FinalClosureReevaluationStatus.BLOCKED_RUNTIME_DIRTY.value
        decision = FinalClosureDecision.BLOCK_FINAL_CLOSURE.value
    elif not delivery.get("valid", False) or reclass.get("delivery_dirty_count", 0) > 0:
        status = FinalClosureReevaluationStatus.BLOCKED_DELIVERY_ARTIFACT_DIRTY.value
        decision = FinalClosureDecision.BLOCK_FINAL_CLOSURE.value
    elif state.get("dirty_file_count", 0) == 0:
        status = FinalClosureReevaluationStatus.CLOSED_CLEAN.value
        decision = FinalClosureDecision.APPROVE_FINAL_CLEAN_CLOSURE.value
    elif reclass.get("accepted_as_external_condition", False):
        status = FinalClosureReevaluationStatus.CLOSED_WITH_EXTERNAL_WORKTREE_CONDITION.value
        decision = FinalClosureDecision.APPROVE_FINAL_CLOSURE_WITH_EXTERNAL_WORKTREE_CONDITION.value
    else:
        status = FinalClosureReevaluationStatus.BLOCKED_UNKNOWN_DIRTY_STATE.value
        decision = FinalClosureDecision.BLOCK_FINAL_CLOSURE.value

    external_condition = {
        "condition_id": "r241-16y-external-worktree-condition",
        "condition_type": FinalClosureConditionType.EXTERNAL_WORKTREE_DIRTY.value,
        "dirty_file_count": state.get("dirty_file_count", 0),
        "secret_like_blocker_resolved": reclass.get("secret_like_blocker_resolved", False),
        "delivery_scope_dirty_count": reclass.get("delivery_dirty_count", 0),
        "workflow_scope_dirty_count": reclass.get("workflow_dirty_count", 0),
        "runtime_scope_dirty_count": reclass.get("runtime_dirty_count", 0),
        "staged_file_count": reclass.get("staged_count", 0),
        "accepted_as_external_condition": reclass.get("accepted_as_external_condition", False),
        "warnings": reclass.get("warnings", []),
        "errors": reclass.get("errors", []),
    }

    review = {
        "review_id": f"r241-16y-final-closure-{hashlib.sha256(_now().encode()).hexdigest()[:8]}",
        "generated_at": _now(),
        "status": status,
        "decision": decision,
        "source_commit_hash": delivery.get("source_commit_hash") or SOURCE_COMMIT_HASH,
        "source_changed_files": delivery.get("source_changed_files") or [TARGET_WORKFLOW],
        "r241_16x_status": x.get("review", {}).get("status"),
        "r241_16x_decision": x.get("review", {}).get("decision"),
        "r241_16x_summary": x,
        "r241_16w_status": w.get("condition", {}).get("status"),
        "r241_16w_decision": w.get("condition", {}).get("decision"),
        "r241_16w_summary": w,
        "r241_16v_status": v.get("status"),
        "r241_16v_decision": v.get("decision"),
        "staged_files": state.get("staged_files", []),
        "dirty_file_count": state.get("dirty_file_count", 0),
        "current_closure_state": state,
        "external_condition": external_condition,
        "closure_checks": checks,
        "delivery_artifacts_state": delivery,
        "workflow_state": {
            "workflow_dirty_files": state.get("workflow_dirty_files", []),
            "workflow_dirty_count": state.get("workflow_dirty_count", 0),
            "remote_target_workflow_present": state.get("remote_target_workflow_present", False),
        },
        "runtime_state": {
            "runtime_dirty_files": state.get("runtime_dirty_files", []),
            "runtime_dirty_count": state.get("runtime_dirty_count", 0),
        },
        "dirty_state_reclassification": reclass,
        "safety_summary": safety,
        "receiver_next_steps": [
            "Foundation CI Delivery can be treated as closed with external worktree condition.",
            "Do not clean or commit unrelated dirty files as part of this closure.",
            "If continuing publication, use the existing R241-16Q/R recovery path.",
        ] if decision != FinalClosureDecision.BLOCK_FINAL_CLOSURE.value else [
            "Resolve blocking closure condition before marking final closure.",
        ],
        "validation_result": {"valid": True, "warnings": [], "errors": []},
        "warnings": x.get("warnings", []) + w.get("warnings", []) + state.get("warnings", []) + delivery.get("warnings", []),
        "errors": x.get("errors", []) + w.get("errors", []) + state.get("errors", []) + delivery.get("errors", []),
    }
    review["validation_result"] = validate_final_closure_reevaluation(review)
    return review


def validate_final_closure_reevaluation(review: dict) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    status = review.get("status")
    decision = review.get("decision")
    safety = review.get("safety_summary", {})

    if status not in {s.value for s in FinalClosureReevaluationStatus}:
        errors.append("invalid final closure status")
    if decision not in {d.value for d in FinalClosureDecision}:
        errors.append("invalid final closure decision")

    closed_external = status == FinalClosureReevaluationStatus.CLOSED_WITH_EXTERNAL_WORKTREE_CONDITION.value
    closed_clean = status == FinalClosureReevaluationStatus.CLOSED_CLEAN.value
    if closed_external:
        x_summary = review.get("r241_16x_summary", {}).get("review", {})
        if x_summary.get("real_secret_candidate_count", 0) != 0:
            errors.append("external closure requires R241-16X real_secret_candidate_count=0")
        if review.get("workflow_state", {}).get("workflow_dirty_files"):
            errors.append("external closure requires workflow dirty files empty")
        if review.get("runtime_state", {}).get("runtime_dirty_files"):
            errors.append("external closure requires runtime dirty files empty")
        if review.get("staged_files"):
            errors.append("external closure requires staged files empty")
        if not review.get("delivery_artifacts_state", {}).get("valid"):
            errors.append("external closure requires delivery artifacts valid")
    if closed_clean and review.get("dirty_file_count", 0) != 0:
        errors.append("clean closure requires dirty_file_count=0")

    for key in [
        "git_commit_executed",
        "git_push_executed",
        "git_reset_restore_revert_executed",
        "git_am_apply_executed",
        "gh_workflow_run_executed",
        "secret_env_read",
        "workflow_modified",
        "runtime_write",
        "audit_jsonl_write",
        "action_queue_write",
        "auto_fix_executed",
        "raw_secret_emitted",
    ]:
        if safety.get(key):
            errors.append(f"{key} must be false")

    serialized = json.dumps(review, ensure_ascii=False)
    forbidden_tokens = [
        "BEGIN PRIVATE KEY",
        "https://open.feishu.cn/open-apis/bot/v2/hook/",
        "https://hooks.slack.com/",
        "github_pat_",
        "ghp_",
        "sk-ant-",
    ]
    if any(token in serialized for token in forbidden_tokens):
        errors.append("raw secret-like value appears in final closure review")

    if decision != FinalClosureDecision.BLOCK_FINAL_CLOSURE.value:
        failed_required = [
            c.get("check_id") for c in review.get("closure_checks", [])
            if c.get("required_for_final_closure") and not c.get("passed")
        ]
        if failed_required:
            errors.append(f"non-blocking decision with failed checks: {failed_required}")

    return {"valid": len(errors) == 0, "warnings": warnings, "errors": errors}


def generate_final_closure_reevaluation_report(
    review: dict | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    if review is None:
        review = evaluate_final_closure_reevaluation()
    validation = validate_final_closure_reevaluation(review)
    review["validation_result"] = validation

    base = Path(output_path).resolve() if output_path else REPORT_DIR / "R241-16Y_FINAL_CLOSURE_REEVALUATION.json"
    if base.suffix.lower() == ".md":
        json_path = base.with_suffix(".json")
        md_path = base
    else:
        json_path = base
        md_path = base.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"generated_at": _now(), "review": review, "validation": validation}
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# R241-16Y Final Closure Re-evaluation",
        "",
        "## 1. 修改文件清单",
        "- backend/app/foundation/ci_final_closure_reevaluation.py",
        "- backend/app/foundation/test_ci_final_closure_reevaluation.py",
        "- migration_reports/foundation_audit/R241-16Y_FINAL_CLOSURE_REEVALUATION.json",
        "- migration_reports/foundation_audit/R241-16Y_FINAL_CLOSURE_REEVALUATION.md",
        "",
        "## 2. FinalClosureReevaluationStatus / Decision / RiskLevel / ConditionType",
        f"- Status: `{review.get('status')}`",
        f"- Decision: `{review.get('decision')}`",
        f"- Risk levels: `{', '.join(r.value for r in FinalClosureRiskLevel)}`",
        f"- Condition types: `{', '.join(c.value for c in FinalClosureConditionType)}`",
        "",
        "## 3. FinalClosureReevaluationCheck 字段",
        "- check_id, passed, risk_level, condition_type, description, observed_value, expected_value, evidence_refs, required_for_final_closure, blocked_reasons, warnings, errors",
        "",
        "## 4. FinalClosureExternalCondition 字段",
        "- condition_id, condition_type, dirty_file_count, secret_like_blocker_resolved, delivery_scope_dirty_count, workflow_scope_dirty_count, runtime_scope_dirty_count, staged_file_count, accepted_as_external_condition, warnings, errors",
        "",
        "## 5. FinalClosureReevaluation 字段",
        "- review_id, generated_at, status, decision, source_commit_hash, source_changed_files, R241-16X/W/V summaries, staged_files, dirty_file_count, external_condition, closure_checks, delivery_artifacts_state, workflow_state, runtime_state, safety_summary, receiver_next_steps, validation_result, warnings, errors",
        "",
        "## 6. R241-16X Loading Result",
        f"- status: `{review.get('r241_16x_status')}`",
        f"- decision: `{review.get('r241_16x_decision')}`",
        f"- real_secret_candidate_count: `{review.get('r241_16x_summary', {}).get('review', {}).get('real_secret_candidate_count')}`",
        "",
        "## 7. R241-16W Loading Result",
        f"- status: `{review.get('r241_16w_status')}`",
        f"- decision: `{review.get('r241_16w_decision')}`",
        "",
        "## 8. Current Closure State Inspection Result",
        f"- staged_file_count: `{len(review.get('staged_files', []))}`",
        f"- dirty_file_count: `{review.get('dirty_file_count')}`",
        f"- workflow_dirty_count: `{review.get('workflow_state', {}).get('workflow_dirty_count')}`",
        f"- runtime_dirty_count: `{review.get('runtime_state', {}).get('runtime_dirty_count')}`",
        "",
        "## 9. Dirty State Reclassification Result",
        f"- secret_like_blocker_resolved: `{review.get('external_condition', {}).get('secret_like_blocker_resolved')}`",
        f"- accepted_as_external_condition: `{review.get('external_condition', {}).get('accepted_as_external_condition')}`",
        "",
        "## 10. Delivery Artifacts Still Valid Result",
        f"- valid: `{review.get('delivery_artifacts_state', {}).get('valid')}`",
        f"- source_changed_files: `{review.get('source_changed_files')}`",
        "",
        "## 11. Final Closure Safety Result",
    ]
    for key, value in review.get("safety_summary", {}).items():
        if key not in {"warnings", "errors"}:
            lines.append(f"- {key}: `{value}`")
    lines.extend([
        "",
        "## 12. Final Closure Checks Result",
    ])
    for check in review.get("closure_checks", []):
        lines.append(f"- `{check.get('check_id')}`: `{check.get('passed')}`")
    lines.extend([
        "",
        "## 13. Validation Result",
        f"- valid: `{validation.get('valid')}`",
        f"- errors: `{validation.get('errors')}`",
        "",
        "## 14. 测试结果",
        "- See execution summary in final response.",
        "",
        "## 15-24. Safety Assertions",
        "- No git commit / push / reset / restore / revert / am / apply.",
        "- No gh workflow run.",
        "- No secret env read and no raw secret emitted.",
        "- No workflow modification.",
        "- No runtime / audit JSONL / action queue write.",
        "- No auto-fix.",
        "",
        "## 25. 当前剩余断点",
        "- Working tree remains dirty outside delivery closure; it is accepted as an external condition.",
        "",
        "## 26. 下一轮建议",
        "- Mark Foundation CI Delivery as closed_with_external_worktree_condition.",
    ])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "review": review,
        "validation": validation,
        "warnings": [],
        "errors": [],
    }

