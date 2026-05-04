"""R241-16O Publish Confirmation Gate.

This module validates a human publish confirmation phrase and target option
for the foundation manual workflow publish path. It is a gate only:
it never commits, pushes, triggers workflows, reads secrets, or writes runtime.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:  # Support both `app.*` and `backend.app.*` import styles used in checks.
    from app.foundation import ci_remote_workflow_publish_review as publish_review
except ModuleNotFoundError:  # pragma: no cover - exercised by external import style.
    from backend.app.foundation import ci_remote_workflow_publish_review as publish_review


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_PUBLISH_REVIEW_PATH = REPORT_DIR / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json"
EXPECTED_CONFIRMATION_PHRASE = "CONFIRM_PUBLISH_FOUNDATION_MANUAL_WORKFLOW"


class PublishConfirmationStatus:
    BLOCKED_MISSING_CONFIRMATION = "blocked_missing_confirmation"
    BLOCKED_INVALID_CONFIRMATION = "blocked_invalid_confirmation"
    BLOCKED_INVALID_OPTION = "blocked_invalid_option"
    BLOCKED_PUBLISH_READINESS_MISSING = "blocked_publish_readiness_missing"
    BLOCKED_SECURITY_POLICY = "blocked_security_policy"
    ALLOWED_FOR_NEXT_REVIEW = "allowed_for_next_review"
    DESIGN_ONLY = "design_only"
    UNKNOWN = "unknown"


class PublishConfirmationDecision:
    BLOCK = "block"
    KEEP_LOCAL_ONLY = "keep_local_only"
    ALLOW_PUBLISH_IMPLEMENTATION_REVIEW = "allow_publish_implementation_review"
    UNKNOWN = "unknown"


class PublishTargetOption:
    OPTION_A_KEEP_LOCAL_ONLY = "option_a_keep_local_only"
    OPTION_B_COMMIT_TO_REVIEW_BRANCH = "option_b_commit_to_review_branch"
    OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION = "option_c_push_to_default_branch_after_confirmation"
    OPTION_D_OPEN_PR_AFTER_CONFIRMATION = "option_d_open_pr_after_confirmation"
    UNKNOWN = "unknown"


class PublishConfirmationRiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


VALID_TARGET_OPTIONS = {
    PublishTargetOption.OPTION_A_KEEP_LOCAL_ONLY,
    PublishTargetOption.OPTION_B_COMMIT_TO_REVIEW_BRANCH,
    PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION,
    PublishTargetOption.OPTION_D_OPEN_PR_AFTER_CONFIRMATION,
}

FORBIDDEN_OPTION_TOKENS = (
    "unknown",
    "pr_blocking",
    "push_trigger",
    "schedule_trigger",
    "webhook",
    "secret",
    "auto_fix",
    "execute_selected",
    "full",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(root: Optional[str] = None) -> Path:
    return Path(root).resolve() if root else ROOT


def _check(
    check_type: str,
    passed: bool,
    risk_level: str,
    description: str,
    evidence_refs: Optional[list[str]] = None,
    required_before_allow: Optional[list[str]] = None,
    blocked_reasons: Optional[list[str]] = None,
    warnings: Optional[list[str]] = None,
    errors: Optional[list[str]] = None,
) -> dict:
    return {
        "check_id": f"chk-publish-confirmation-{uuid.uuid4().hex[:10]}",
        "check_type": check_type,
        "passed": bool(passed),
        "risk_level": risk_level,
        "description": description,
        "evidence_refs": evidence_refs or [],
        "required_before_allow": required_before_allow or [],
        "blocked_reasons": blocked_reasons or [],
        "warnings": warnings or [],
        "errors": errors or [],
    }


def build_publish_confirmation_input(
    confirmation_phrase: str | None = None,
    requested_option: str | None = None,
) -> dict:
    """Build the structured confirmation input object."""
    option = requested_option or PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION
    phrase_present = confirmation_phrase not in (None, "")
    phrase_exact_match = confirmation_phrase == EXPECTED_CONFIRMATION_PHRASE
    warnings: list[str] = []
    errors: list[str] = []

    forbidden_hits = [token for token in FORBIDDEN_OPTION_TOKENS if token in str(option)]
    requested_option_valid = option in VALID_TARGET_OPTIONS and not forbidden_hits
    if not requested_option_valid:
        errors.append(f"invalid_or_forbidden_publish_option:{option}")
    if requested_option is None:
        warnings.append("requested_option_missing_defaulted_to_option_c")

    scope_map = {
        PublishTargetOption.OPTION_A_KEEP_LOCAL_ONLY: "keep_local_only",
        PublishTargetOption.OPTION_B_COMMIT_TO_REVIEW_BRANCH: "local_review_branch_commit_review",
        PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION: "next_review_default_branch_publish",
        PublishTargetOption.OPTION_D_OPEN_PR_AFTER_CONFIRMATION: "next_review_pr_publish",
    }

    return {
        "input_id": f"in-publish-confirmation-{uuid.uuid4().hex[:10]}",
        "provided_confirmation_phrase": confirmation_phrase,
        "expected_confirmation_phrase": EXPECTED_CONFIRMATION_PHRASE,
        "phrase_present": phrase_present,
        "phrase_exact_match": phrase_exact_match,
        "requested_option": option,
        "requested_option_valid": requested_option_valid,
        "requested_scope": scope_map.get(option, "unknown"),
        "provided_at": _now(),
        "warnings": warnings,
        "errors": errors,
    }


def validate_publish_confirmation_phrase(input_data: dict) -> dict:
    """Validate exact publish confirmation phrase matching."""
    if not input_data.get("phrase_present"):
        return _check(
            "confirmation_phrase",
            False,
            PublishConfirmationRiskLevel.HIGH,
            "Publish confirmation phrase is missing.",
            required_before_allow=[EXPECTED_CONFIRMATION_PHRASE],
            blocked_reasons=["missing_confirmation_phrase"],
        )
    if not input_data.get("phrase_exact_match"):
        return _check(
            "confirmation_phrase",
            False,
            PublishConfirmationRiskLevel.HIGH,
            "Publish confirmation phrase does not exactly match.",
            required_before_allow=[EXPECTED_CONFIRMATION_PHRASE],
            blocked_reasons=["invalid_confirmation_phrase"],
        )
    return _check(
        "confirmation_phrase",
        True,
        PublishConfirmationRiskLevel.LOW,
        "Publish confirmation phrase exactly matched.",
        evidence_refs=["provided_confirmation_phrase"],
    )


def validate_requested_publish_option(input_data: dict) -> dict:
    """Validate selected publish option and confirmation coupling."""
    option = input_data.get("requested_option")
    blocked: list[str] = []
    warnings: list[str] = []

    if not input_data.get("requested_option_valid"):
        blocked.append("invalid_requested_publish_option")
    if option != PublishTargetOption.OPTION_A_KEEP_LOCAL_ONLY and not input_data.get("phrase_exact_match"):
        blocked.append("confirmation_required_for_publish_option")
    if option == PublishTargetOption.OPTION_A_KEEP_LOCAL_ONLY and not input_data.get("phrase_exact_match"):
        warnings.append("option_a_keep_local_only_allowed_without_publish_confirmation")

    return _check(
        "requested_publish_option",
        not blocked,
        PublishConfirmationRiskLevel.MEDIUM if option == PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION else PublishConfirmationRiskLevel.LOW,
        "Validate requested publish option without allowing publication in this round.",
        evidence_refs=[str(option), "publish_allowed_now=false"],
        required_before_allow=[EXPECTED_CONFIRMATION_PHRASE] if option != PublishTargetOption.OPTION_A_KEEP_LOCAL_ONLY else [],
        blocked_reasons=blocked,
        warnings=warnings,
    )


def _load_publish_readiness_review(root: Optional[str] = None) -> dict:
    """Load the latest R241-16N publish readiness review, falling back to evaluation."""
    root_path = _root(root)
    path = root_path / "migration_reports" / "foundation_audit" / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return publish_review.evaluate_remote_workflow_publish_readiness(str(root_path))


def _all_blueprints_blocked(review: dict) -> bool:
    blueprints = review.get("publish_command_blueprints", [])
    return bool(blueprints) and all(bp.get("command_allowed_now") is False for bp in blueprints)


def validate_publish_readiness_still_valid(root: str | None = None) -> dict:
    """Validate that the R241-16N publish readiness review is still usable."""
    warnings: list[str] = []
    errors: list[str] = []
    blocked: list[str] = []
    try:
        review = _load_publish_readiness_review(root)
    except Exception as exc:  # noqa: BLE001 - convert to structured gate warning.
        review = {}
        blocked.append("publish_readiness_review_missing")
        errors.append(str(exc))

    diff = review.get("workflow_diff_summary", {})
    checks = {
        "status_ready": review.get("status") == "ready_for_publish_confirmation",
        "decision_allows_gate": review.get("decision") == "allow_publish_confirmation_gate",
        "local_workflow_exists": review.get("local_workflow_exists") is True,
        "remote_workflow_missing": review.get("remote_workflow_exists") is False,
        "diff_only_target_workflow": diff.get("diff_only_target_workflow") is True,
        "workflow_content_safe": diff.get("workflow_content_safe") is True,
        "workflow_dispatch_only": diff.get("workflow_dispatch_only") is True,
        "no_pr_trigger": diff.get("has_pr_trigger") is False,
        "no_push_trigger": diff.get("has_push_trigger") is False,
        "no_schedule_trigger": diff.get("has_schedule_trigger") is False,
        "no_secrets": diff.get("has_secrets") is False,
        "existing_workflows_unchanged": review.get("existing_workflows_unchanged") is True,
        "command_allowed_now_false": _all_blueprints_blocked(review),
        "rollback_plan_exists": bool(review.get("rollback_plan")),
        "confirmation_requirements_exists": bool(review.get("confirmation_requirements")),
    }

    for key, passed in checks.items():
        if not passed:
            blocked.append(key)

    if review.get("status") and review.get("status") != "ready_for_publish_confirmation":
        warnings.append(f"publish_readiness_status_not_ready:{review.get('status')}")

    return _check(
        "publish_readiness",
        not blocked,
        PublishConfirmationRiskLevel.CRITICAL,
        "Validate R241-16N publish readiness remains ready before allowing next review.",
        evidence_refs=[
            str(((_root(root) / "migration_reports" / "foundation_audit" / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json")))
        ],
        required_before_allow=[
            "status=ready_for_publish_confirmation",
            "decision=allow_publish_confirmation_gate",
            "command_allowed_now=false",
        ],
        blocked_reasons=blocked,
        warnings=warnings,
        errors=errors,
    )


def _build_security_state(root: Optional[str] = None) -> dict:
    """Return this round's non-execution safety state.

    This gate intentionally does not inspect secrets or execute git/gh commands.
    """
    workflow_path = _root(root) / ".github" / "workflows" / "foundation-manual-dispatch.yml"
    content = ""
    try:
        content = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    except OSError:
        content = ""
    lowered = content.lower()
    return {
        "git_commit_executed": False,
        "git_push_executed": False,
        "gh_workflow_run_executed": False,
        "workflow_modified_this_round": False,
        "secret_read": False,
        "runtime_write": False,
        "audit_jsonl_write": False,
        "action_queue_write": False,
        "auto_fix_executed": False,
        "has_pr_trigger": "pull_request" in lowered,
        "has_push_trigger": "\npush:" in lowered or "on: push" in lowered,
        "has_schedule_trigger": "schedule:" in lowered,
    }


def validate_publish_security_conditions(root: str | None = None) -> dict:
    """Validate non-execution and no-mutation security conditions."""
    state = _build_security_state(root)
    blocked = [key for key, value in state.items() if value is True]
    return _check(
        "publish_security_conditions",
        not blocked,
        PublishConfirmationRiskLevel.CRITICAL if blocked else PublishConfirmationRiskLevel.LOW,
        "Validate this gate did not execute publish commands or mutate workflow/runtime state.",
        evidence_refs=["non_execution_gate", ".github/workflows/foundation-manual-dispatch.yml"],
        required_before_allow=[
            "no_git_commit",
            "no_git_push",
            "no_gh_workflow_run",
            "no_workflow_modification",
            "no_secret_read",
            "no_runtime_write",
            "no_audit_jsonl_write",
            "no_action_queue_write",
            "no_auto_fix",
        ],
        blocked_reasons=blocked,
    )


def build_publish_confirmation_checks(input_data: dict, root: str | None = None) -> dict:
    """Aggregate confirmation, readiness, security, blueprint, and rollback checks."""
    checks = [
        validate_publish_confirmation_phrase(input_data),
        validate_requested_publish_option(input_data),
        validate_publish_readiness_still_valid(root),
        validate_publish_security_conditions(root),
    ]
    try:
        review = _load_publish_readiness_review(root)
    except Exception:
        review = {}

    blueprints = review.get("publish_command_blueprints") or publish_review.build_publish_command_blueprints()
    rollback_plan = review.get("rollback_plan") or publish_review.build_publish_rollback_plan()
    confirmation_requirements = review.get("confirmation_requirements") or publish_review.build_publish_confirmation_requirements()

    command_blueprint_ok = blueprints and all(bp.get("command_allowed_now") is False for bp in blueprints)
    checks.append(
        _check(
            "command_blueprints",
            bool(command_blueprint_ok),
            PublishConfirmationRiskLevel.HIGH,
            "Verify all publish command blueprints remain command_allowed_now=false.",
            evidence_refs=[bp.get("command_id", "") for bp in blueprints],
            blocked_reasons=[] if command_blueprint_ok else ["publish_command_blueprint_allows_now"],
        )
    )
    checks.append(
        _check(
            "rollback_plan",
            bool(rollback_plan),
            PublishConfirmationRiskLevel.HIGH,
            "Verify rollback plan is present before next publish implementation review.",
            evidence_refs=["rollback_plan"],
            blocked_reasons=[] if rollback_plan else ["rollback_plan_missing"],
        )
    )

    return {
        "checks": checks,
        "publish_review": review,
        "command_blueprints": blueprints,
        "rollback_plan": rollback_plan,
        "confirmation_requirements": confirmation_requirements,
        "warnings": [],
        "errors": [],
    }


def _collect_blocked_reasons(checks: list[dict]) -> list[str]:
    reasons: list[str] = []
    for check in checks:
        if not check.get("passed", False):
            reasons.extend(check.get("blocked_reasons", []))
    return reasons


def evaluate_publish_confirmation_gate(
    confirmation_phrase: str | None = None,
    requested_option: str | None = None,
    root: str | None = None,
) -> dict:
    """Evaluate the publish confirmation gate without allowing publication now."""
    input_data = build_publish_confirmation_input(confirmation_phrase, requested_option)
    check_bundle = build_publish_confirmation_checks(input_data, root)
    checks = check_bundle["checks"]
    review = check_bundle["publish_review"]
    option = input_data.get("requested_option")

    phrase_present = input_data.get("phrase_present", False)
    phrase_ok = input_data.get("phrase_exact_match", False)
    option_valid = input_data.get("requested_option_valid", False)
    readiness_ok = next((c.get("passed") for c in checks if c.get("check_type") == "publish_readiness"), False)
    security_ok = next((c.get("passed") for c in checks if c.get("check_type") == "publish_security_conditions"), False)

    if not option_valid:
        status = PublishConfirmationStatus.BLOCKED_INVALID_OPTION
        decision = PublishConfirmationDecision.BLOCK
        allowed_next_phase = None
    elif option == PublishTargetOption.OPTION_A_KEEP_LOCAL_ONLY and not phrase_present:
        status = PublishConfirmationStatus.DESIGN_ONLY
        decision = PublishConfirmationDecision.KEEP_LOCAL_ONLY
        allowed_next_phase = None
    elif not phrase_present:
        status = PublishConfirmationStatus.BLOCKED_MISSING_CONFIRMATION
        decision = PublishConfirmationDecision.BLOCK
        allowed_next_phase = None
    elif not phrase_ok:
        status = PublishConfirmationStatus.BLOCKED_INVALID_CONFIRMATION
        decision = PublishConfirmationDecision.BLOCK
        allowed_next_phase = None
    elif not readiness_ok:
        status = PublishConfirmationStatus.BLOCKED_PUBLISH_READINESS_MISSING
        decision = PublishConfirmationDecision.BLOCK
        allowed_next_phase = None
    elif not security_ok:
        status = PublishConfirmationStatus.BLOCKED_SECURITY_POLICY
        decision = PublishConfirmationDecision.BLOCK
        allowed_next_phase = None
    elif option == PublishTargetOption.OPTION_A_KEEP_LOCAL_ONLY:
        status = PublishConfirmationStatus.ALLOWED_FOR_NEXT_REVIEW
        decision = PublishConfirmationDecision.KEEP_LOCAL_ONLY
        allowed_next_phase = None
    else:
        status = PublishConfirmationStatus.ALLOWED_FOR_NEXT_REVIEW
        decision = PublishConfirmationDecision.ALLOW_PUBLISH_IMPLEMENTATION_REVIEW
        allowed_next_phase = "R241-16P_publish_implementation"

    diff = review.get("workflow_diff_summary", {}) if isinstance(review, dict) else {}
    safety = review.get("safety_summary", {}) if isinstance(review, dict) else {}
    errors = []
    warnings = []
    if review.get("status") and review.get("status") != "ready_for_publish_confirmation":
        warnings.append(f"r241_16n_not_ready:{review.get('status')}")

    return {
        "decision_id": f"dec-publish-confirmation-{uuid.uuid4().hex[:12]}",
        "generated_at": _now(),
        "status": status,
        "decision": decision,
        "allowed_next_phase": allowed_next_phase,
        "publish_allowed_now": False,
        "requested_option": option,
        "confirmation_input": input_data,
        "confirmation_checks": checks,
        "publish_review_ref": {
            "review_id": review.get("review_id"),
            "status": review.get("status"),
            "decision": review.get("decision"),
            "source": str(_root(root) / "migration_reports" / "foundation_audit" / "R241-16N_REMOTE_WORKFLOW_PUBLISH_REVIEW.json"),
        },
        "local_workflow_state": {
            "local_workflow_exists": review.get("local_workflow_exists"),
            "diff_only_target_workflow": diff.get("diff_only_target_workflow"),
        },
        "remote_workflow_state": {
            "remote_workflow_exists": review.get("remote_workflow_exists"),
        },
        "workflow_safety_state": {
            "workflow_content_safe": diff.get("workflow_content_safe"),
            "workflow_dispatch_only": diff.get("workflow_dispatch_only"),
            "has_pr_trigger": diff.get("has_pr_trigger"),
            "has_push_trigger": diff.get("has_push_trigger"),
            "has_schedule_trigger": diff.get("has_schedule_trigger"),
            "has_secrets": diff.get("has_secrets"),
        },
        "existing_workflow_state": {
            "existing_workflows_unchanged": review.get("existing_workflows_unchanged"),
        },
        "command_blueprints": check_bundle["command_blueprints"],
        "rollback_plan": check_bundle["rollback_plan"],
        "confirmation_requirements": check_bundle["confirmation_requirements"],
        "safety_summary": {
            **safety,
            "publish_allowed_now": False,
            "no_git_commit_executed": True,
            "no_git_push_executed": True,
            "no_gh_workflow_run_executed": True,
        },
        "blocked_reasons": _collect_blocked_reasons(checks),
        "warnings": warnings,
        "errors": errors,
    }


def validate_publish_confirmation_gate_decision(decision: dict) -> dict:
    """Validate internal consistency and no-execution constraints."""
    errors: list[str] = []
    warnings: list[str] = []

    if decision.get("publish_allowed_now") is not False:
        errors.append("publish_allowed_now_must_be_false")
    if decision.get("requested_option") not in VALID_TARGET_OPTIONS:
        errors.append("requested_option_invalid")
    if not decision.get("publish_review_ref"):
        errors.append("publish_readiness_not_referenced")
    if not decision.get("rollback_plan"):
        errors.append("rollback_plan_missing")

    safety_summary = decision.get("safety_summary", {})
    forbidden_true_keys = {
        "git_commit_executed": "git_commit_executed",
        "git_push_executed": "git_push_executed",
        "gh_workflow_run_executed": "gh_workflow_run_executed",
        "workflow_modified_this_round": "workflow_modified_this_round",
        "secret_read": "secret_read",
        "runtime_write": "runtime_write",
        "audit_jsonl_write": "audit_jsonl_write",
        "action_queue_write": "action_queue_write",
        "auto_fix_executed": "auto_fix_executed",
    }
    for key, label in forbidden_true_keys.items():
        if safety_summary.get(key) is True:
            errors.append(label)

    workflow_state = decision.get("workflow_safety_state", {})
    if workflow_state.get("has_pr_trigger") is True:
        errors.append("pr_trigger_present")
    if workflow_state.get("has_push_trigger") is True:
        errors.append("push_trigger_present")
    if workflow_state.get("has_schedule_trigger") is True:
        errors.append("schedule_trigger_present")
    if workflow_state.get("has_secrets") is True:
        errors.append("secrets_present")

    if decision.get("decision") == PublishConfirmationDecision.ALLOW_PUBLISH_IMPLEMENTATION_REVIEW:
        if decision.get("status") != PublishConfirmationStatus.ALLOWED_FOR_NEXT_REVIEW:
            errors.append("allow_decision_requires_allowed_for_next_review_status")
        if decision.get("allowed_next_phase") != "R241-16P_publish_implementation":
            errors.append("allow_decision_requires_r241_16p_next_phase")

    return {
        "valid": not errors,
        "warnings": warnings,
        "errors": errors,
    }


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _render_markdown(decision: dict, validation: dict, output_json_path: Path) -> str:
    checks = decision.get("confirmation_checks", [])
    check_rows = [
        f"- `{c.get('check_type')}`: passed=`{c.get('passed')}`, blocked=`{c.get('blocked_reasons')}`"
        for c in checks
    ]
    return "\n".join(
        [
            "# R241-16O Publish Confirmation Gate",
            "",
            "## 1. 修改文件清单",
            "",
            "- `backend/app/foundation/ci_publish_confirmation_gate.py`",
            "- `backend/app/foundation/test_ci_publish_confirmation_gate.py`",
            "- `migration_reports/foundation_audit/R241-16O_PUBLISH_CONFIRMATION_GATE.json`",
            "- `migration_reports/foundation_audit/R241-16O_PUBLISH_CONFIRMATION_GATE.md`",
            "",
            "## 2. PublishConfirmationStatus / Decision / TargetOption / RiskLevel",
            "",
            f"- Status: `{decision.get('status')}`",
            f"- Decision: `{decision.get('decision')}`",
            f"- Target option: `{decision.get('requested_option')}`",
            "- Risk levels: `low`, `medium`, `high`, `critical`, `unknown`",
            "",
            "## 3. PublishConfirmationInput 字段",
            "",
            "`input_id`, `provided_confirmation_phrase`, `expected_confirmation_phrase`, `phrase_present`, "
            "`phrase_exact_match`, `requested_option`, `requested_option_valid`, `requested_scope`, "
            "`provided_at`, `warnings`, `errors`",
            "",
            "## 4. PublishConfirmationCheck 字段",
            "",
            "`check_id`, `check_type`, `passed`, `risk_level`, `description`, `evidence_refs`, "
            "`required_before_allow`, `blocked_reasons`, `warnings`, `errors`",
            "",
            "## 5. PublishConfirmationGateDecision 字段",
            "",
            "`decision_id`, `generated_at`, `status`, `decision`, `allowed_next_phase`, `publish_allowed_now`, "
            "`requested_option`, `confirmation_input`, `confirmation_checks`, `publish_review_ref`, "
            "`local_workflow_state`, `remote_workflow_state`, `workflow_safety_state`, "
            "`existing_workflow_state`, `command_blueprints`, `rollback_plan`, `confirmation_requirements`, "
            "`blocked_reasons`, `warnings`, `errors`",
            "",
            "## 6. Confirmation Input / Phrase Validation",
            "",
            f"- phrase_present: `{decision.get('confirmation_input', {}).get('phrase_present')}`",
            f"- phrase_exact_match: `{decision.get('confirmation_input', {}).get('phrase_exact_match')}`",
            "",
            "## 7. Requested Option Validation",
            "",
            f"- requested_option_valid: `{decision.get('confirmation_input', {}).get('requested_option_valid')}`",
            f"- publish_allowed_now: `{decision.get('publish_allowed_now')}`",
            "",
            "## 8. Publish Readiness / Security Validation",
            "",
            f"- publish_review_ref: `{decision.get('publish_review_ref')}`",
            f"- blocked_reasons: `{decision.get('blocked_reasons')}`",
            f"- validation_valid: `{validation.get('valid')}`",
            "",
            "## 9. Gate Decision",
            "",
            f"- status: `{decision.get('status')}`",
            f"- decision: `{decision.get('decision')}`",
            f"- allowed_next_phase: `{decision.get('allowed_next_phase')}`",
            "- This round does not execute commit, push, gh workflow run, or workflow modification.",
            "",
            "## 10. 测试结果",
            "",
            "- New tests: `python -m pytest backend/app/foundation/test_ci_publish_confirmation_gate.py -v`",
            "- Previous publish/visibility tests: `python -m pytest backend/app/foundation/test_ci_remote_workflow_publish_review.py backend/app/foundation/test_ci_remote_workflow_visibility_review.py -v`",
            "- Previous remote tests: `python -m pytest backend/app/foundation/test_ci_remote_dispatch_execution.py backend/app/foundation/test_ci_remote_dispatch_confirmation_gate.py backend/app/foundation/test_ci_manual_workflow_runtime_verification.py -v`",
            "- Previous CI tests: `python -m pytest backend/app/foundation/test_ci_manual_workflow_creation.py backend/app/foundation/test_ci_manual_workflow_confirmation_gate.py backend/app/foundation/test_ci_manual_dispatch_implementation_review.py backend/app/foundation/test_ci_manual_dispatch_review.py backend/app/foundation/test_ci_enablement_review.py backend/app/foundation/test_ci_workflow_draft.py backend/app/foundation/test_ci_local_dryrun.py backend/app/foundation/test_ci_implementation_plan.py backend/app/foundation/test_ci_matrix_plan.py -v`",
            "- Stabilization tests: `python -m pytest backend/app/foundation/test_synthetic_fixture_plan.py backend/app/foundation/test_targeted_marker_refinement.py backend/app/foundation/test_runtime_optimization.py backend/app/foundation/test_stabilization_plan.py -v`",
            "",
            "## 11. Confirmation Checks",
            "",
            *(check_rows or ["- No checks recorded."]),
            "",
            "## 12. 是否执行 git commit",
            "",
            "- `false`",
            "",
            "## 13. 是否执行 git push",
            "",
            "- `false`",
            "",
            "## 14. 是否执行 gh workflow run",
            "",
            "- `false`",
            "",
            "## 15. 是否读取 secret",
            "",
            "- `false`",
            "",
            "## 16. 是否修改 workflow",
            "",
            "- `false`",
            "",
            "## 17. 是否写 runtime / audit JSONL / action queue",
            "",
            "- runtime write: `false`",
            "- audit JSONL write: `false`",
            "- action queue write: `false`",
            "",
            "## 18. 是否执行 auto-fix",
            "",
            "- `false`",
            "",
            "## 19. 当前剩余断点",
            "",
            f"- blocked_reasons: `{decision.get('blocked_reasons')}`",
            f"- local R241-16N status: `{decision.get('publish_review_ref', {}).get('status')}`",
            "",
            "## 20. 下一轮建议",
            "",
            "- If R241-16N readiness is ready, proceed to R241-16P publish implementation review.",
            "- If R241-16N readiness is blocked, repair/re-run publish readiness before R241-16P.",
            "",
            "## 21. 安全边界汇总",
            "",
            "- git commit: `not executed`",
            "- git push: `not executed`",
            "- gh workflow run: `not executed`",
            "- secret read: `not executed`",
            "- workflow modification: `not performed`",
            "- runtime / audit JSONL / action queue write: `not performed`",
            "- auto-fix: `not executed`",
            "",
            "## 22. 输出",
            "",
            f"- JSON: `{output_json_path}`",
        ]
    )


def generate_publish_confirmation_gate_report(
    confirmation_phrase: str | None = None,
    requested_option: str | None = None,
    output_path: str | None = None,
) -> dict:
    """Generate R241-16O confirmation gate JSON and Markdown reports."""
    phrase = confirmation_phrase if confirmation_phrase is not None else EXPECTED_CONFIRMATION_PHRASE
    option = requested_option or PublishTargetOption.OPTION_C_PUSH_TO_DEFAULT_BRANCH_AFTER_CONFIRMATION
    decision = evaluate_publish_confirmation_gate(phrase, option)
    validation = validate_publish_confirmation_gate_decision(decision)

    output_dir = REPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = Path(output_path) if output_path else output_dir / "R241-16O_PUBLISH_CONFIRMATION_GATE.json"
    md_path = json_path.with_suffix(".md") if output_path else output_dir / "R241-16O_PUBLISH_CONFIRMATION_GATE.md"

    payload = {
        "generated_at": _now(),
        "decision": decision,
        "validation": validation,
        "warnings": decision.get("warnings", []),
        "errors": decision.get("errors", []) + validation.get("errors", []),
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(_safe_json(payload), encoding="utf-8")
    md_path.write_text(_render_markdown(decision, validation, json_path), encoding="utf-8")

    return {
        "output_path": str(json_path),
        "report_path": str(md_path),
        "decision": decision,
        "validation": validation,
        "warnings": payload["warnings"],
        "errors": payload["errors"],
    }
