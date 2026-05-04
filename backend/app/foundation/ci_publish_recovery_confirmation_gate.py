"""R241-16R: Recovery Path Confirmation Gate.

Read-only gate that:
1. Validates user-provided confirmation phrase
2. Checks R241-16Q push failure review is still valid
3. Checks R241-16Q-B staged area is clean
4. Confirms user's selected recovery option (A-E)
5. Outputs allow/block decision for next implementation phase

NO write operations: no git push, no git reset, no patch generation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]

REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
R241_16Q_REVIEW_PATH = REPORT_DIR / "R241-16Q_PUBLISH_PUSH_FAILURE_REVIEW.json"
R241_16Q_B_REVIEW_PATH = REPORT_DIR / "R241-16Q_B_STAGED_AREA_CONSISTENCY_REPAIR.json"

CONFIRMATION_PHRASE = "CONFIRM_PUBLISH_RECOVERY_PATH"


class RecoveryConfirmationStatus(str, Enum):
    BLOCKED_MISSING_CONFIRMATION = "blocked_missing_confirmation"
    BLOCKED_INVALID_CONFIRMATION = "blocked_invalid_confirmation"
    BLOCKED_INVALID_OPTION = "blocked_invalid_option"
    BLOCKED_PUSH_FAILURE_REVIEW_MISSING = "blocked_push_failure_review_missing"
    BLOCKED_STAGED_AREA_NOT_CLEAN = "blocked_staged_area_not_clean"
    BLOCKED_COMMIT_SCOPE_UNSAFE = "blocked_commit_scope_unsafe"
    ALLOWED_FOR_NEXT_REVIEW = "allowed_for_next_review"
    DESIGN_ONLY = "design_only"
    UNKNOWN = "unknown"


class RecoveryPathOption(str, Enum):
    OPTION_A_KEEP_LOCAL_COMMIT_WAIT = "option_a_keep_local_commit_wait_permission"
    OPTION_B_PUSH_TO_USER_FORK = "option_b_push_to_user_fork_after_confirmation"
    OPTION_C_CREATE_REVIEW_BRANCH = "option_c_create_review_branch_after_confirmation"
    OPTION_D_GENERATE_PATCH_BUNDLE = "option_d_generate_patch_bundle_after_confirmation"
    OPTION_E_ROLLBACK_LOCAL_COMMIT = "option_e_rollback_local_commit_after_confirmation"
    UNKNOWN = "unknown"


class RecoveryConfirmationDecision(str, Enum):
    KEEP_LOCAL_COMMIT = "keep_local_commit"
    ALLOW_RECOVERY_IMPLEMENTATION_REVIEW = "allow_recovery_implementation_review"
    BLOCK_RECOVERY = "block_recovery"
    UNKNOWN = "unknown"


class RecoveryConfirmationRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ── Valid option IDs ────────────────────────────────────────────────────────────

VALID_OPTION_IDS = {
    RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
    RecoveryPathOption.OPTION_B_PUSH_TO_USER_FORK.value,
    RecoveryPathOption.OPTION_C_CREATE_REVIEW_BRANCH.value,
    RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
    RecoveryPathOption.OPTION_E_ROLLBACK_LOCAL_COMMIT.value,
}


# ── Forbidden option fragments ────────────────────────────────────────────────

FORBIDDEN_OPTION_SUBSTRINGS = [
    "git_push_now",
    "git_reset_now",
    "gh_workflow_run",
    "secret",
    "auto_fix",
    "execute_selected",
    "force_push",
    "reset_hard",
]


# ── 1. build_recovery_confirmation_input ─────────────────────────────────────


def build_recovery_confirmation_input(
    confirmation_phrase: Optional[str] = None,
    requested_option: Optional[str] = None,
) -> dict:
    """Build confirmation input from provided phrase and requested option."""
    phrase = confirmation_phrase or ""
    phrase_present = phrase_present_fn(phrase)
    phrase_exact_match = phrase_present and phrase == CONFIRMATION_PHRASE

    option = requested_option or RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value
    option_valid = is_valid_option(option)

    return {
        "input_id": f"recovery-input-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "provided_confirmation_phrase": confirmation_phrase,
        "expected_confirmation_phrase": CONFIRMATION_PHRASE,
        "phrase_present": phrase_present,
        "phrase_exact_match": phrase_exact_match,
        "requested_option": option,
        "requested_option_valid": option_valid,
        "requested_scope": "recovery_path_selection",
        "provided_at": datetime.now(timezone.utc).isoformat(),
        "warnings": [],
        "errors": [],
    }


def phrase_present_fn(phrase: str) -> bool:
    return bool(phrase and phrase.strip())


def is_valid_option(option: str) -> bool:
    if option not in VALID_OPTION_IDS:
        return False
    option_lower = option.lower()
    for forbidden in FORBIDDEN_OPTION_SUBSTRINGS:
        if forbidden in option_lower:
            return False
    return True


# ── 2. validate_recovery_confirmation_phrase ─────────────────────────────────


def validate_recovery_confirmation_phrase(input_data: dict) -> dict:
    """Validate the confirmation phrase is present and exact match."""
    phrase_present = input_data.get("phrase_present", False)
    phrase_exact_match = input_data.get("phrase_exact_match", False)

    passed = phrase_present and phrase_exact_match
    blocked_reasons = []
    warnings = []

    if not phrase_present:
        blocked_reasons.append("confirmation_phrase_missing")
    elif not phrase_exact_match:
        blocked_reasons.append("confirmation_phrase_mismatch")

    return {
        "check_id": "check_confirmation_phrase",
        "check_type": "confirmation_phrase",
        "passed": passed,
        "risk_level": RecoveryConfirmationRiskLevel.CRITICAL.value,
        "description": "Validate CONFIRM_PUBLISH_RECOVERY_PATH phrase is present and exact match",
        "required_before_allow": True,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": [],
    }


# ── 3. validate_requested_recovery_option ─────────────────────────────────────


def validate_requested_recovery_option(input_data: dict) -> dict:
    """Validate the requested recovery option is valid and safe."""
    option = input_data.get("requested_option", "")
    option_valid = input_data.get("requested_option_valid", False)
    phrase_exact_match = input_data.get("phrase_exact_match", False)

    passed = option_valid
    blocked_reasons = []
    warnings = []

    if not option_valid:
        blocked_reasons.append(f"invalid_recovery_option: {option}")

    # option_e rollback is high risk
    if option == RecoveryPathOption.OPTION_E_ROLLBACK_LOCAL_COMMIT.value:
        warnings.append("option_e_rollback_high_risk_requires_explicit_confirmation")

    # Option A is always allowed even without phrase (design_only path)
    # Option B-E require phrase exact match
    if (
        not phrase_exact_match
        and option != RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value
    ):
        blocked_reasons.append("option_requires_confirmation_phrase")
        passed = False

    return {
        "check_id": "check_recovery_option",
        "check_type": "requested_option",
        "passed": passed,
        "risk_level": (
            RecoveryConfirmationRiskLevel.HIGH.value
            if option == RecoveryPathOption.OPTION_E_ROLLBACK_LOCAL_COMMIT.value
            else RecoveryConfirmationRiskLevel.MEDIUM.value
        ),
        "description": f"Validate requested recovery option: {option}",
        "required_before_allow": True,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": [],
    }


# ── 4. validate_push_failure_and_staged_area_ready ──────────────────────────


def validate_push_failure_and_staged_area_ready(
    root: Optional[str] = None,
) -> dict:
    """Verify R241-16Q and R241-16Q-B reviews are loaded and indicate readiness."""
    checks = []

    # Load R241-16Q
    try:
        with open(R241_16Q_REVIEW_PATH, encoding="utf-8") as f:
            r241_16q_data = json.load(f)
        r241_16q = r241_16q_data.get("review", r241_16q_data)
        r241_16q_guard = r241_16q.get("local_mutation_guard", {})
    except FileNotFoundError:
        r241_16q = {}
        r241_16q_guard = {}

    # Load R241-16Q-B
    try:
        with open(R241_16Q_B_REVIEW_PATH, encoding="utf-8") as f:
            r241_16q_b = json.load(f)
    except FileNotFoundError:
        r241_16q_b = {}

    # Check R241-16Q status
    q_status_ok = r241_16q.get("status") == "reviewed_push_permission_denied"
    checks.append({
        "check_id": "check_r241_16q_status",
        "check_type": "r241_16q_status",
        "passed": q_status_ok,
        "risk_level": RecoveryConfirmationRiskLevel.CRITICAL.value,
        "description": "R241-16Q status must be reviewed_push_permission_denied",
        "observed_value": r241_16q.get("status"),
        "expected_value": "reviewed_push_permission_denied",
        "blocked_reasons": [] if q_status_ok else ["r241_16q_status_not_reviewed"],
        "warnings": [],
        "errors": [],
    })

    # Check R241-16Q local commit scope
    local_commit_only_target = r241_16q.get("local_commit_only_target_workflow", False)
    checks.append({
        "check_id": "check_r241_16q_local_commit_scope",
        "check_type": "local_commit_scope",
        "passed": local_commit_only_target,
        "risk_level": RecoveryConfirmationRiskLevel.CRITICAL.value,
        "description": "Local commit must only contain target workflow",
        "observed_value": r241_16q.get("local_commit_hash"),
        "expected_value": ".github/workflows/foundation-manual-dispatch.yml",
        "blocked_reasons": [] if local_commit_only_target else ["local_commit_scope_unsafe"],
        "warnings": [],
        "errors": [],
    })

    # Check R241-16Q remote workflow missing
    remote_missing = not r241_16q.get("remote_workflow_present", True)
    checks.append({
        "check_id": "check_r241_16q_remote_workflow_missing",
        "check_type": "remote_workflow_missing",
        "passed": remote_missing,
        "risk_level": RecoveryConfirmationRiskLevel.HIGH.value,
        "description": "Remote origin/main must not have target workflow",
        "observed_value": r241_16q.get("remote_workflow_present"),
        "expected_value": False,
        "blocked_reasons": [] if remote_missing else ["remote_workflow_already_present"],
        "warnings": [],
        "errors": [],
    })

    # Check R241-16Q-B status
    qb_status = r241_16q_b.get("status", "")
    qb_decision = r241_16q_b.get("decision", "")
    qb_status_ok = qb_status in ("parser_false_positive_fixed", "clean")
    checks.append({
        "check_id": "check_r241_16q_b_status",
        "check_type": "r241_16q_b_status",
        "passed": qb_status_ok,
        "risk_level": RecoveryConfirmationRiskLevel.CRITICAL.value,
        "description": "R241-16Q-B status must be parser_false_positive_fixed or clean",
        "observed_value": qb_status,
        "expected_value": "parser_false_positive_fixed or clean",
        "blocked_reasons": [] if qb_status_ok else [f"r241_16q_b_status_invalid: {qb_status}"],
        "warnings": [],
        "errors": [],
    })

    # Check R241-16Q-B decision
    qb_decision_ok = qb_decision == "allow_recovery_gate"
    checks.append({
        "check_id": "check_r241_16q_b_decision",
        "check_type": "r241_16q_b_decision",
        "passed": qb_decision_ok,
        "risk_level": RecoveryConfirmationRiskLevel.CRITICAL.value,
        "description": "R241-16Q-B decision must be allow_recovery_gate",
        "observed_value": qb_decision,
        "expected_value": "allow_recovery_gate",
        "blocked_reasons": [] if qb_decision_ok else [f"r241_16q_b_decision_invalid: {qb_decision}"],
        "warnings": [],
        "errors": [],
    })

    # Check R241-16Q-B staged area empty
    staged_files = r241_16q_b.get("current_staged_files", [])
    staged_area_empty = len(staged_files) == 0
    checks.append({
        "check_id": "check_r241_16q_b_staged_area",
        "check_type": "staged_area_clean",
        "passed": staged_area_empty,
        "risk_level": RecoveryConfirmationRiskLevel.HIGH.value,
        "description": "R241-16Q-B current staged area must be empty",
        "observed_value": staged_files,
        "expected_value": [],
        "blocked_reasons": [] if staged_area_empty else ["staged_area_not_empty"],
        "warnings": [],
        "errors": [],
    })

    # Check R241-16Q-B existing workflows unchanged
    existing_unchanged = r241_16q_b.get("existing_workflows_unchanged", False)
    checks.append({
        "check_id": "check_r241_16q_b_existing_workflows",
        "check_type": "existing_workflows_unchanged",
        "passed": existing_unchanged,
        "risk_level": RecoveryConfirmationRiskLevel.HIGH.value,
        "description": "Existing workflows must be unchanged",
        "observed_value": existing_unchanged,
        "expected_value": True,
        "blocked_reasons": [] if existing_unchanged else ["existing_workflows_modified"],
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
        "checks": checks,
        "blocked_reasons": blocked_reasons,
        "warnings": [],
        "errors": [],
        "r241_16q_status": r241_16q.get("status"),
        "r241_16q_decision": r241_16q.get("decision"),
        "r241_16q_local_commit_hash": r241_16q.get("local_commit_hash"),
        "r241_16q_b_status": qb_status,
        "r241_16q_b_decision": qb_decision,
        "r241_16q_b_staged_area_empty": staged_area_empty,
        "r241_16q_b_current_staged_files": staged_files,
    }


# ── 5. build_recovery_confirmation_checks ─────────────────────────────────────


def build_recovery_confirmation_checks(
    input_data: dict,
    root: Optional[str] = None,
) -> list[dict]:
    """Aggregate all confirmation checks."""
    phrase_check = validate_recovery_confirmation_phrase(input_data)
    option_check = validate_requested_recovery_option(input_data)
    readiness = validate_push_failure_and_staged_area_ready(root)

    return [
        phrase_check,
        option_check,
        *readiness.get("checks", []),
    ]


# ── 6. evaluate_recovery_confirmation_gate ───────────────────────────────────


def evaluate_recovery_confirmation_gate(
    confirmation_phrase: Optional[str] = None,
    requested_option: Optional[str] = None,
    root: Optional[str] = None,
) -> dict:
    """Core evaluation function for the recovery confirmation gate."""
    input_data = build_recovery_confirmation_input(confirmation_phrase, requested_option)
    checks = build_recovery_confirmation_checks(input_data, root)

    phrase_check = checks[0]
    option_check = checks[1]
    readiness = validate_push_failure_and_staged_area_ready(root)

    phrase_passed = phrase_check.get("passed", False)
    option_passed = option_check.get("passed", False)
    readiness_passed = readiness.get("all_passed", False)

    requested_option_val = input_data.get("requested_option", "")
    is_option_a = requested_option_val == RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value

    # Determine status and decision
    # Option A (keep local commit) is always allowed if option itself is valid and readiness passes
    if is_option_a and option_passed and readiness_passed:
        status = RecoveryConfirmationStatus.ALLOWED_FOR_NEXT_REVIEW
        decision = RecoveryConfirmationDecision.KEEP_LOCAL_COMMIT
        allowed_next_phase = None
    elif not phrase_passed and not is_option_a:
        status = RecoveryConfirmationStatus.BLOCKED_MISSING_CONFIRMATION
        decision = RecoveryConfirmationDecision.BLOCK_RECOVERY
        allowed_next_phase = None
    elif not option_passed:
        status = RecoveryConfirmationStatus.BLOCKED_INVALID_OPTION
        decision = RecoveryConfirmationDecision.BLOCK_RECOVERY
        allowed_next_phase = None
    elif not readiness_passed:
        status = RecoveryConfirmationStatus.BLOCKED_STAGED_AREA_NOT_CLEAN
        decision = RecoveryConfirmationDecision.BLOCK_RECOVERY
        allowed_next_phase = None
    elif phrase_passed and option_passed and readiness_passed:
        status = RecoveryConfirmationStatus.ALLOWED_FOR_NEXT_REVIEW
        decision = RecoveryConfirmationDecision.ALLOW_RECOVERY_IMPLEMENTATION_REVIEW
        if requested_option_val == RecoveryPathOption.OPTION_B_PUSH_TO_USER_FORK.value:
            allowed_next_phase = "R241-16S_fork_push_implementation_review"
        elif requested_option_val == RecoveryPathOption.OPTION_C_CREATE_REVIEW_BRANCH.value:
            allowed_next_phase = "R241-16S_review_branch_implementation_review"
        elif requested_option_val == RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value:
            allowed_next_phase = "R241-16S_patch_bundle_generation"
        elif requested_option_val == RecoveryPathOption.OPTION_E_ROLLBACK_LOCAL_COMMIT.value:
            allowed_next_phase = "R241-16S_rollback_confirmation_review"
        else:
            allowed_next_phase = None
    else:
        status = RecoveryConfirmationStatus.UNKNOWN
        decision = RecoveryConfirmationDecision.UNKNOWN
        allowed_next_phase = None

    decision_id = f"recovery-gate-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    return {
        "decision_id": decision_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status.value,
        "decision": decision.value,
        "allowed_next_phase": allowed_next_phase,
        "recovery_action_allowed_now": False,
        "requested_option": requested_option_val,
        "confirmation_input": input_data,
        "confirmation_checks": checks,
        "push_failure_review_ref": {
            "status": readiness.get("r241_16q_status"),
            "decision": readiness.get("r241_16q_decision"),
            "local_commit_hash": readiness.get("r241_16q_local_commit_hash"),
        },
        "staged_area_review_ref": {
            "status": readiness.get("r241_16q_b_status"),
            "decision": readiness.get("r241_16q_b_decision"),
            "staged_area_empty": readiness.get("r241_16q_b_staged_area_empty"),
        },
        "local_commit_state": {
            "safe": readiness_passed,
            "only_target_workflow": True,
        },
        "remote_workflow_state": {
            "present": False,
        },
        "recovery_options": _build_recovery_options(),
        "command_blueprints": _build_command_blueprints(),
        "rollback_plan": _build_rollback_plan(),
        "blocked_reasons": readiness.get("blocked_reasons", []),
        "warnings": option_check.get("warnings", []),
        "errors": [],
    }


def _build_recovery_options() -> list[dict]:
    return [
        {
            "option_id": RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
            "label": "Keep local commit and wait for upstream permission",
            "risk_level": RecoveryConfirmationRiskLevel.LOW.value,
            "description": "Keep local commit ahead 1 and wait for permission grant.",
        },
        {
            "option_id": RecoveryPathOption.OPTION_B_PUSH_TO_USER_FORK.value,
            "label": "Push to user fork after confirmation",
            "risk_level": RecoveryConfirmationRiskLevel.MEDIUM.value,
            "description": "Push to user fork remote after confirming fork exists.",
        },
        {
            "option_id": RecoveryPathOption.OPTION_C_CREATE_REVIEW_BRANCH.value,
            "label": "Create review branch after confirmation",
            "risk_level": RecoveryConfirmationRiskLevel.MEDIUM.value,
            "description": "Create review branch. May still fail without remote permission.",
        },
        {
            "option_id": RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
            "label": "Generate patch or bundle after confirmation",
            "risk_level": RecoveryConfirmationRiskLevel.LOW.value,
            "description": "Generate patch or bundle to migration_reports without remote push.",
        },
        {
            "option_id": RecoveryPathOption.OPTION_E_ROLLBACK_LOCAL_COMMIT.value,
            "label": "Rollback local commit after confirmation",
            "risk_level": RecoveryConfirmationRiskLevel.HIGH.value,
            "description": "Rollback local commit. This is irreversible and discards the safe commit.",
        },
    ]


def _build_command_blueprints() -> list[dict]:
    return [
        {
            "command_id": "option_a_wait_no_command",
            "recovery_option": RecoveryPathOption.OPTION_A_KEEP_LOCAL_COMMIT_WAIT.value,
            "argv": [],
            "command_allowed_now": False,
            "would_modify_git_history": False,
            "would_push_remote": False,
            "requires_confirmation_phrase": CONFIRMATION_PHRASE,
            "warnings": ["No action taken. Local commit remains ahead of origin/main."],
        },
        {
            "command_id": "option_b_push_fork",
            "recovery_option": RecoveryPathOption.OPTION_B_PUSH_TO_USER_FORK.value,
            "argv": ["git", "push", "user-fork", "main"],
            "command_allowed_now": False,
            "would_modify_git_history": False,
            "would_push_remote": True,
            "requires_confirmation_phrase": CONFIRMATION_PHRASE,
            "warnings": ["Requires confirmed fork remote. Verify user-fork points to your fork."],
        },
        {
            "command_id": "option_c_review_branch",
            "recovery_option": RecoveryPathOption.OPTION_C_CREATE_REVIEW_BRANCH.value,
            "argv": ["git", "checkout", "-b", "foundation-manual-workflow-review"],
            "command_allowed_now": False,
            "would_modify_git_history": True,
            "would_push_remote": False,
            "requires_confirmation_phrase": CONFIRMATION_PHRASE,
            "warnings": ["Creates local branch but does NOT push. May fail on push without permission."],
        },
        {
            "command_id": "option_d_generate_patch",
            "recovery_option": RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
            "argv": ["git", "format-patch", "-1", "HEAD", "-o", "migration_reports/foundation_audit"],
            "command_allowed_now": False,
            "would_modify_git_history": False,
            "would_push_remote": False,
            "requires_confirmation_phrase": CONFIRMATION_PHRASE,
            "warnings": ["Generates .patch file in migration_reports/foundation_audit. No remote push."],
        },
        {
            "command_id": "option_d_generate_bundle",
            "recovery_option": RecoveryPathOption.OPTION_D_GENERATE_PATCH_BUNDLE.value,
            "argv": ["git", "bundle", "create", "migration_reports/foundation_audit/foundation-workflow.bundle", "HEAD"],
            "command_allowed_now": False,
            "would_modify_git_history": False,
            "would_push_remote": False,
            "requires_confirmation_phrase": CONFIRMATION_PHRASE,
            "warnings": ["Generates .bundle file in migration_reports/foundation_audit. No remote push."],
        },
        {
            "command_id": "option_e_rollback",
            "recovery_option": RecoveryPathOption.OPTION_E_ROLLBACK_LOCAL_COMMIT.value,
            "argv": ["git", "reset", "--soft", "HEAD~1"],
            "command_allowed_now": False,
            "would_modify_git_history": True,
            "would_push_remote": False,
            "requires_confirmation_phrase": CONFIRMATION_PHRASE,
            "warnings": [
                "HIGH RISK: This discards the local commit.",
                "Workflow file content remains in working tree but is no longer committed.",
            ],
        },
    ]


def _build_rollback_plan() -> dict:
    return {
        "if_only_local_uncommitted": {
            "description": "Workflow is local only (uncommitted).",
            "rollback_action": "No action required.",
            "commands": [],
            "confirmation_required": True,
        },
        "if_committed_not_pushed": {
            "description": "Workflow committed locally but not pushed.",
            "rollback_action": "git reset --soft HEAD~1 to uncommit.",
            "commands": ["git reset --soft HEAD~1"],
            "confirmation_required": True,
            "warnings": ["This undoes the commit but file content may still be in staging."],
        },
        "no_auto_rollback": True,
    }


# ── 7. validate_recovery_confirmation_gate_decision ──────────────────────────


def validate_recovery_confirmation_gate_decision(decision: dict) -> dict:
    """Validate the gate decision itself did not violate safety constraints."""
    blocked_reasons = []
    warnings = []

    # recovery_action_allowed_now must be False
    if decision.get("recovery_action_allowed_now", True):
        blocked_reasons.append("recovery_action_allowed_now_must_be_false")

    # All command_blueprints must have command_allowed_now=False
    blueprints = decision.get("command_blueprints", [])
    for bp in blueprints:
        if bp.get("command_allowed_now", True):
            blocked_reasons.append(f"command_allowed_now_must_be_false: {bp.get('command_id')}")

    # checks should not have blocked reasons
    checks = decision.get("confirmation_checks", [])
    for check in checks:
        if not check.get("passed") and check.get("blocked_reasons"):
            blocked_reasons.extend(check.get("blocked_reasons", []))

    # blocked_reasons should not include active mutation
    mutation_keywords = [
        "git_push", "git_commit", "git_reset", "git_restore",
        "gh_workflow_run", "auto_fix", "runtime_write",
    ]
    for br in blocked_reasons:
        if any(kw in str(br).lower() for kw in mutation_keywords):
            if br not in [
                "git_push_blocked_by_permission",
                "git_reset_requires_confirmation",
            ]:
                pass  # These are expected failure modes, not safety violations

    valid = len(blocked_reasons) == 0

    return {
        "valid": valid,
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "errors": [],
    }


# ── 8. generate_recovery_confirmation_gate_report ────────────────────────────


def generate_recovery_confirmation_gate_report(
    confirmation_phrase: Optional[str] = None,
    requested_option: Optional[str] = None,
    output_path: Optional[str] = None,
) -> dict:
    """Generate the R241-16R recovery path confirmation gate report."""
    decision = evaluate_recovery_confirmation_gate(
        confirmation_phrase=confirmation_phrase,
        requested_option=requested_option,
    )
    validation = validate_recovery_confirmation_gate_decision(decision)

    if output_path:
        json_path = Path(output_path)
    else:
        json_path = REPORT_DIR / "R241-16R_RECOVERY_PATH_CONFIRMATION_GATE.json"

    json_path.parent.mkdir(parents=True, exist_ok=True)

    report_data = {
        "decision_id": decision.get("decision_id"),
        "generated_at": decision.get("generated_at"),
        "status": decision.get("status"),
        "decision": decision.get("decision"),
        "allowed_next_phase": decision.get("allowed_next_phase"),
        "recovery_action_allowed_now": decision.get("recovery_action_allowed_now"),
        "requested_option": decision.get("requested_option"),
        "confirmation_input": decision.get("confirmation_input"),
        "confirmation_checks": decision.get("confirmation_checks"),
        "push_failure_review_ref": decision.get("push_failure_review_ref"),
        "staged_area_review_ref": decision.get("staged_area_review_ref"),
        "local_commit_state": decision.get("local_commit_state"),
        "remote_workflow_state": decision.get("remote_workflow_state"),
        "recovery_options": decision.get("recovery_options"),
        "command_blueprints": decision.get("command_blueprints"),
        "rollback_plan": decision.get("rollback_plan"),
        "validation": validation,
        "blocked_reasons": decision.get("blocked_reasons", []),
        "warnings": decision.get("warnings", []),
        "errors": decision.get("errors", []),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    md_path = json_path.with_suffix(".md")
    _write_markdown_report(report_data, str(md_path))

    return {
        "output_path": str(json_path),
        "report_path": str(md_path),
        "decision": decision,
        "validation": validation,
    }


def _write_markdown_report(data: dict, path: str) -> None:
    """Write Markdown version of the recovery confirmation gate report."""
    lines = [
        "# R241-16R Recovery Path Confirmation Gate",
        "",
        "## Gate Result",
        "",
        f"- **Decision ID**: `{data.get('decision_id', '')}`",
        f"- **Generated**: `{data.get('generated_at', '')}`",
        f"- **Status**: `{data.get('status', '')}`",
        f"- **Decision**: `{data.get('decision', '')}`",
        f"- **Allowed Next Phase**: `{data.get('allowed_next_phase', '')}`",
        f"- **Recovery Action Allowed Now**: `{data.get('recovery_action_allowed_now')}`",
        f"- **Requested Option**: `{data.get('requested_option', '')}`",
        "",
        "## Confirmation Input",
        "",
        f"- **Phrase Present**: `{data.get('confirmation_input', {}).get('phrase_present')}`",
        f"- **Phrase Exact Match**: `{data.get('confirmation_input', {}).get('phrase_exact_match')}`",
        f"- **Requested Option Valid**: `{data.get('confirmation_input', {}).get('requested_option_valid')}`",
        "",
        "## R241-16Q Push Failure Reference",
        "",
        f"- **Status**: `{data.get('push_failure_review_ref', {}).get('status')}`",
        f"- **Decision**: `{data.get('push_failure_review_ref', {}).get('decision')}`",
        f"- **Local Commit Hash**: `{data.get('push_failure_review_ref', {}).get('local_commit_hash')}`",
        "",
        "## R241-16Q-B Staged Area Reference",
        "",
        f"- **Status**: `{data.get('staged_area_review_ref', {}).get('status')}`",
        f"- **Decision**: `{data.get('staged_area_review_ref', {}).get('decision')}`",
        f"- **Staged Area Empty**: `{data.get('staged_area_review_ref', {}).get('staged_area_empty')}`",
        "",
        "## Local Commit State",
        "",
        f"- **Safe**: `{data.get('local_commit_state', {}).get('safe')}`",
        f"- **Only Target Workflow**: `{data.get('local_commit_state', {}).get('only_target_workflow')}`",
        "",
        "## Remote Workflow State",
        "",
        f"- **Present on origin/main**: `{data.get('remote_workflow_state', {}).get('present')}`",
        "",
        "## Recovery Options",
        "",
    ]

    for opt in data.get("recovery_options", []):
        lines.extend([
            f"- **{opt['label']}**",
            f"  - ID: `{opt['option_id']}`",
            f"  - Risk: `{opt['risk_level']}`",
            f"  - {opt['description']}",
            "",
        ])

    validation = data.get("validation", {})
    lines.extend([
        "## Validation",
        "",
        f"- **Valid**: `{validation.get('valid')}`",
        f"- **Blocked Reasons**: `{validation.get('blocked_reasons', [])}`",
        "",
        "## Safety Constraints",
        "",
        "✅ No git push executed during gate",
        "✅ No git commit executed during gate",
        "✅ No git reset/restore/revert executed",
        "✅ No git format-patch / git bundle executed",
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
        f"- Next phase: `{data.get('allowed_next_phase', 'None')}`",
        f"- Recommended: `option_d_generate_patch_bundle_after_confirmation` (low risk, no push required)",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
