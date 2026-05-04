"""CI Implementation Plan for R241-16A.

This module designs how R241-15F CI stage catalog, markers, and baselines
are connected to actual CI infrastructure (GitHub Actions, local scripts,
or generic CI).

This module is report-only. It does not:
- Create real workflow files
- Enable CI provider
- Write runtime state
- Write audit JSONL
- Call network/webhooks
- Execute auto-fix
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_PLAN_PATH = REPORT_DIR / "R241-16A_CI_IMPLEMENTATION_PLAN.json"
DEFAULT_REPORT_PATH = REPORT_DIR / "R241-16A_CI_IMPLEMENTATION_REPORT.md"

# ─────────────────────────────────────────────────────────────────────────────
# Enumerations (as string constants)
# ─────────────────────────────────────────────────────────────────────────────

class CIExecutionStageType:
    SMOKE = "smoke"
    FAST = "fast"
    SAFETY = "safety"
    SLOW = "slow"
    FULL = "full"
    COLLECT_ONLY = "collect_only"
    UNKNOWN = "unknown"

    @classmethod
    def all(cls) -> List[str]:
        return [getattr(cls, a) for a in dir(cls) if not a.startswith("_") and a not in ("all", "values")]


class CIGatingPolicy:
    PR_BLOCKING = "pr_blocking"
    PR_WARNING = "pr_warning"
    NIGHTLY_REQUIRED = "nightly_required"
    MANUAL_ONLY = "manual_only"
    REPORT_ONLY = "report_only"
    UNKNOWN = "unknown"


class CIArtifactType:
    JUNIT_XML = "junit_xml"
    PYTEST_LOG = "pytest_log"
    COVERAGE_REPORT = "coverage_report"
    FOUNDATION_AUDIT_REPORT = "foundation_audit_report"
    CI_MATRIX_REPORT = "ci_matrix_report"
    UNKNOWN = "unknown"


class CIProviderTarget:
    GITHUB_ACTIONS = "github_actions"
    LOCAL_SCRIPT = "local_script"
    GENERIC_CI = "generic_ci"
    FUTURE_UNKNOWN = "future_unknown"


class CIImplementationStatus:
    DESIGN_ONLY = "design_only"
    READY_FOR_DRY_RUN = "ready_for_dry_run"
    BLOCKED_NEEDS_CONFIRMATION = "blocked_needs_confirmation"
    BLOCKED_PATH_INCONSISTENCY = "blocked_path_inconsistency"
    BLOCKED_MISSING_CI_PROVIDER = "blocked_missing_ci_provider"
    UNKNOWN = "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Core object builders
# ─────────────────────────────────────────────────────────────────────────────

def build_ci_stage_implementation_specs() -> Dict[str, Any]:
    """Generate CI stage implementation specs based on R241-15F stage catalog."""

    forbidden_actions = [
        "network_call",
        "webhook_call",
        "runtime_write",
        "action_queue_write",
        "auto_fix",
        "feishu_send",
        "secret_read",
        "audit_jsonl_write",
        "audit_jsonl_delete",
    ]

    stages = [
        # ── Smoke ──────────────────────────────────────────────────────────
        {
            "stage_id": "impl_stage_smoke",
            "stage_type": CIExecutionStageType.SMOKE,
            "name": "Smoke",
            "description": "Minimal health checks: import, registry, marker, root guard.",
            "command": "python -m pytest -m smoke -v",
            "provider_target": CIProviderTarget.GITHUB_ACTIONS,
            "gating_policy": CIGatingPolicy.PR_WARNING,
            "expected_runtime_seconds": 60,
            "warning_threshold_seconds": 45,
            "blocker_threshold_seconds": None,
            "required_on_pr": False,
            "required_on_nightly": False,
            "produces_artifacts": True,
            "artifact_types": [CIArtifactType.PYTEST_LOG],
            "environment_requirements": [],
            "forbidden_actions": forbidden_actions,
            "marker_expression": "smoke",
            "warnings": ["smoke stage is pr_warning only — does not block merge"],
            "errors": [],
        },
        # ── Fast ────────────────────────────────────────────────────────────
        {
            "stage_id": "impl_stage_fast",
            "stage_type": CIExecutionStageType.FAST,
            "name": "Fast Unit + Fast Integration",
            "description": "Default local developer regression excluding slow tests. PR blocking.",
            "command": "python -m pytest backend/app/foundation backend/app/audit -m \"not slow\" -v",
            "provider_target": CIProviderTarget.GITHUB_ACTIONS,
            "gating_policy": CIGatingPolicy.PR_BLOCKING,
            "expected_runtime_seconds": 30,
            "warning_threshold_seconds": 30,
            "blocker_threshold_seconds": 60,
            "required_on_pr": True,
            "required_on_nightly": True,
            "produces_artifacts": True,
            "artifact_types": [CIArtifactType.PYTEST_LOG, CIArtifactType.COVERAGE_REPORT],
            "environment_requirements": [],
            "forbidden_actions": forbidden_actions,
            "marker_expression": "not slow",
            "warnings": [],
            "errors": [],
        },
        # ── Safety ───────────────────────────────────────────────────────────
        {
            "stage_id": "impl_stage_safety",
            "stage_type": CIExecutionStageType.SAFETY,
            "name": "Safety Boundaries",
            "description": "Run no_network / no_runtime_write / no_secret boundaries independently. PR blocking.",
            "command": "python -m pytest backend/app/foundation backend/app/audit -m \"no_network or no_runtime_write or no_secret\" -v",
            "provider_target": CIProviderTarget.GITHUB_ACTIONS,
            "gating_policy": CIGatingPolicy.PR_BLOCKING,
            "expected_runtime_seconds": 10,
            "warning_threshold_seconds": 10,
            "blocker_threshold_seconds": 20,
            "required_on_pr": True,
            "required_on_nightly": True,
            "produces_artifacts": True,
            "artifact_types": [CIArtifactType.PYTEST_LOG],
            "environment_requirements": [],
            "forbidden_actions": forbidden_actions,
            "marker_expression": "no_network or no_runtime_write or no_secret",
            "warnings": [],
            "errors": [],
        },
        # ── Slow ────────────────────────────────────────────────────────────
        {
            "stage_id": "impl_stage_slow",
            "stage_type": CIExecutionStageType.SLOW,
            "name": "Slow Integration",
            "description": "Real boundary, real repo scan, aggregate diagnostic, append/query/trend/Feishu preview smoke. Nightly required, not direct PR block.",
            "command": "python -m pytest backend/app/foundation backend/app/audit -m slow -v",
            "provider_target": CIProviderTarget.GITHUB_ACTIONS,
            "gating_policy": CIGatingPolicy.NIGHTLY_REQUIRED,
            "expected_runtime_seconds": 60,
            "warning_threshold_seconds": 60,
            "blocker_threshold_seconds": 120,
            "required_on_pr": False,
            "required_on_nightly": True,
            "produces_artifacts": True,
            "artifact_types": [CIArtifactType.PYTEST_LOG, CIArtifactType.FOUNDATION_AUDIT_REPORT],
            "environment_requirements": [],
            "forbidden_actions": forbidden_actions,
            "marker_expression": "slow",
            "warnings": ["slow stage is nightly_required — creates stabilization ticket on warning but does not block PR"],
            "errors": [],
        },
        # ── Full ────────────────────────────────────────────────────────────
        {
            "stage_id": "impl_stage_full",
            "stage_type": CIExecutionStageType.FULL,
            "name": "Full Regression",
            "description": "Pre-release or large-change regression across all foundation surfaces. Manual only.",
            "command": (
                "python -m pytest backend/app/foundation backend/app/audit backend/app/nightly "
                "backend/app/rtcm backend/app/prompt backend/app/tool_runtime backend/app/mode "
                "backend/app/gateway backend/app/asset backend/app/memory backend/app/m11 -v"
            ),
            "provider_target": CIProviderTarget.GITHUB_ACTIONS,
            "gating_policy": CIGatingPolicy.MANUAL_ONLY,
            "expected_runtime_seconds": None,
            "warning_threshold_seconds": 300,
            "blocker_threshold_seconds": None,
            "required_on_pr": False,
            "required_on_nightly": False,
            "produces_artifacts": True,
            "artifact_types": [CIArtifactType.PYTEST_LOG, CIArtifactType.FOUNDATION_AUDIT_REPORT, CIArtifactType.COVERAGE_REPORT],
            "environment_requirements": [],
            "forbidden_actions": forbidden_actions,
            "marker_expression": None,
            "warnings": ["full stage is manual_only — not required on PR or nightly"],
            "errors": [],
        },
        # ── Collect-only ─────────────────────────────────────────────────────
        {
            "stage_id": "impl_stage_collect_only",
            "stage_type": CIExecutionStageType.COLLECT_ONLY,
            "name": "Collection Check",
            "description": "Verify pytest can collect all tests without running them. PR warning.",
            "command": "python -m pytest backend/app/foundation backend/app/audit --collect-only -q",
            "provider_target": CIProviderTarget.GITHUB_ACTIONS,
            "gating_policy": CIGatingPolicy.PR_WARNING,
            "expected_runtime_seconds": 10,
            "warning_threshold_seconds": 10,
            "blocker_threshold_seconds": 20,
            "required_on_pr": False,
            "required_on_nightly": False,
            "produces_artifacts": True,
            "artifact_types": [CIArtifactType.PYTEST_LOG],
            "environment_requirements": [],
            "forbidden_actions": forbidden_actions,
            "marker_expression": None,
            "warnings": ["collect-only stage is pr_warning only — catches collection errors without running tests"],
            "errors": [],
        },
    ]

    return {
        "specs": stages,
        "stage_count": len(stages),
        "fast_pr_blocking": True,
        "safety_pr_blocking": True,
        "slow_pr_blocking": False,
        "full_pr_blocking": False,
    }


def build_ci_artifact_collection_specs(root: Optional[str] = None) -> Dict[str, Any]:
    """Define artifact collection specifications.

    Handles path inconsistency:
    - primary: migration_reports/foundation_audit/ (relative to project root)
    - secondary: backend/migration_reports/foundation_audit/ (from backend/)
    """
    root_path = Path(root) if root else ROOT
    primary_report_path = root_path / "migration_reports" / "foundation_audit"
    secondary_report_path = root_path / "backend" / "migration_reports" / "foundation_audit"

    # Check actual existence
    primary_exists = primary_report_path.exists()
    secondary_exists = secondary_report_path.exists()
    path_inconsistency = primary_exists and secondary_exists

    specs = [
        {
            "artifact_spec_id": "art_spec_foundation_reports",
            "artifact_type": CIArtifactType.FOUNDATION_AUDIT_REPORT,
            "source_paths": [
                str(primary_report_path.relative_to(root_path)) if primary_exists else None,
                str(secondary_report_path.relative_to(root_path)) if secondary_exists else None,
            ],
            "destination_name": "foundation_audit_reports",
            "include_patterns": ["*.json", "*.md"],
            "exclude_patterns": [
                "**/audit_trail/*.jsonl",
                "**/runtime/**",
                "**/action_queue/**",
                "**/.secret/**",
                "**/webhook_url*",
                "**/*token*",
                "**/*secret*",
            ],
            "retention_days": 30,
            "path_inconsistency_handling": "collect_both_report_warning",
            "secrets_allowed": False,
            "runtime_files_allowed": False,
            "warnings": [
                f"primary path: {primary_report_path.relative_to(root_path) if primary_exists else 'not found'}",
                f"secondary path: {secondary_report_path.relative_to(root_path) if secondary_exists else 'not found'}",
                "path_inconsistency: both paths exist — no migration, no deletion in this phase",
            ],
            "errors": [],
        },
        {
            "artifact_spec_id": "art_spec_ci_matrix",
            "artifact_type": CIArtifactType.CI_MATRIX_REPORT,
            "source_paths": [
                str(primary_report_path.relative_to(root_path)) if primary_exists else None,
            ],
            "destination_name": "ci_matrix_reports",
            "include_patterns": ["R241-15*", "R241-16*"],
            "exclude_patterns": [],
            "retention_days": 90,
            "path_inconsistency_handling": "primary_only",
            "secrets_allowed": False,
            "runtime_files_allowed": False,
            "warnings": [],
            "errors": [],
        },
        {
            "artifact_spec_id": "art_spec_pytest_logs",
            "artifact_type": CIArtifactType.PYTEST_LOG,
            "source_paths": [],
            "destination_name": "pytest_logs",
            "include_patterns": ["**/pytest.log", "**/.pytest_cache/**", "**/tmp/**/pytest*.log"],
            "exclude_patterns": ["**/audit_trail/**"],
            "retention_days": 7,
            "path_inconsistency_handling": "none",
            "secrets_allowed": False,
            "runtime_files_allowed": False,
            "warnings": ["pytest logs are temp — only collect if explicitly enabled"],
            "errors": [],
        },
        {
            "artifact_spec_id": "art_spec_junit_xml",
            "artifact_type": CIArtifactType.JUNIT_XML,
            "source_paths": [],
            "destination_name": "junit_reports",
            "include_patterns": ["**/junit*.xml", "**/test-results/**/*.xml"],
            "exclude_patterns": [],
            "retention_days": 14,
            "path_inconsistency_handling": "none",
            "secrets_allowed": False,
            "runtime_files_allowed": False,
            "warnings": ["junit xml is optional — requires --junit-xml flag in pytest command"],
            "errors": [],
        },
    ]

    return {
        "artifact_specs": specs,
        "spec_count": len(specs),
        "primary_report_path": str(primary_report_path.relative_to(root_path)) if primary_exists else str(primary_report_path),
        "secondary_report_path": str(secondary_report_path.relative_to(root_path)) if secondary_exists else str(secondary_report_path),
        "primary_exists": primary_exists,
        "secondary_exists": secondary_exists,
        "path_inconsistency": path_inconsistency,
        "path_inconsistency_action": "report_only_no_migration_no_deletion",
    }


def build_ci_threshold_policy() -> Dict[str, Any]:
    """Build threshold policy using R241-15C/R241-15F baselines."""
    return {
        "threshold_policy_id": "R241-16A_threshold_policy",
        "generated_at": _utc_now(),
        # Foundation fast
        "foundation_fast_warning_threshold_seconds": 30,
        "foundation_fast_blocker_threshold_seconds": 60,
        # Audit fast
        "audit_fast_warning_threshold_seconds": 15,
        "audit_fast_blocker_threshold_seconds": 30,
        # Slow suite
        "slow_suite_warning_threshold_seconds": 60,
        "slow_suite_blocker_threshold_seconds": 120,
        # Safety suite
        "safety_suite_warning_threshold_seconds": 10,
        "safety_suite_blocker_threshold_seconds": 20,
        # Collect-only
        "collect_only_warning_threshold_seconds": 10,
        "collect_only_blocker_threshold_seconds": 20,
        # Failure handling
        "failure_handling": {
            "smoke_failure": "pr_warning_only",
            "fast_failure": "pr_block",
            "safety_failure": "pr_block",
            "slow_failure": "create_stabilization_ticket_warning",
            "full_failure": "manual_review_required",
        },
        "warning_handling": {
            "fast_warning": "log_and_warn_pr_comment",
            "slow_warning": "log_and_create_stabilization_ticket",
            "safety_warning": "log_and_notify_channel",
        },
        "warn_does_not_block_pr_unless_configured": True,
        "blocker_blocks_pr_for_pr_blocking_stages": True,
        "slow_warning_creates_stabilization_ticket_not_auto_fix": True,
        "warnings": [],
        "errors": [],
    }


def build_ci_path_compatibility_policy(root: Optional[str] = None) -> Dict[str, Any]:
    """Handle report path inconsistency (primary vs secondary).

    primary: migration_reports/foundation_audit/
    secondary: backend/migration_reports/foundation_audit/
    """
    root_path = Path(root) if root else ROOT
    primary = root_path / "migration_reports" / "foundation_audit"
    secondary = root_path / "backend" / "migration_reports" / "foundation_audit"

    primary_exists = primary.exists()
    secondary_exists = secondary.exists()

    return {
        "path_compatibility_policy_id": "R241-16A_path_compatibility",
        "generated_at": _utc_now(),
        "primary_report_path": str(primary),
        "secondary_report_path": str(secondary),
        "primary_exists": primary_exists,
        "secondary_exists": secondary_exists,
        "path_inconsistency": primary_exists and secondary_exists,
        "action_now": "report_only",
        "future_options": [
            "unify_report_root_under_migration_reports_only",
            "add_compatibility_note_in_ci_config",
            "migrate_old_backend_reports_in_phase_6",
            "ci_collect_both_paths_temporarily",
        ],
        "migration_allowed_now": False,
        "deletion_allowed_now": False,
        "rewriting_allowed_now": False,
        "warnings": [
            "No migration, deletion, or rewriting in this phase",
            "CI should collect from both paths when both exist",
            "Future Phase 6 will address path cleanup",
        ],
        "errors": [],
    }


def build_ci_implementation_phases() -> Dict[str, Any]:
    """Define 7 implementation phases."""
    phases = [
        {
            "phase_id": "phase_1",
            "phase_name": "Design-only Plan",
            "phase_goal": "Generate CI implementation plan, validate structure, document gating/phases.",
            "duration_estimate": "Current (R241-16A)",
            "deliverable": "ci_implementation_plan.py + R241-16A report",
            "blocks_real_ci": True,
            "creates_workflow": False,
            "requires_review": False,
            "risks": [],
            "status": "design_only",
        },
        {
            "phase_id": "phase_2",
            "phase_name": "Local Script Dry-run",
            "phase_goal": "Create scripts/ci_foundation_check.py local script to mimic CI stages locally.",
            "duration_estimate": "1 week",
            "deliverable": "scripts/ci_foundation_check.py",
            "blocks_real_ci": False,
            "creates_workflow": False,
            "requires_review": True,
            "risks": ["local script may drift from real CI syntax"],
            "status": "blocked_needs_confirmation",
        },
        {
            "phase_id": "phase_3",
            "phase_name": "CI Workflow Draft (disabled)",
            "phase_goal": "Generate .github/workflows/foundation-check.yml draft, default disabled, no active enforcement.",
            "duration_estimate": "1 week",
            "deliverable": ".github/workflows/foundation-check.yml (disabled)",
            "blocks_real_ci": False,
            "creates_workflow": True,
            "requires_review": True,
            "risks": ["draft workflow may accidentally trigger if not properly disabled"],
            "status": "blocked_needs_confirmation",
        },
        {
            "phase_id": "phase_4",
            "phase_name": "PR Blocking Fast + Safety",
            "phase_goal": "Enable fast + safety stages as pr_blocking. Smoke + collect-only as pr_warning.",
            "duration_estimate": "2 days after phase 3",
            "deliverable": "Workflow with fast/safety enforced",
            "blocks_real_ci": True,
            "creates_workflow": True,
            "requires_review": True,
            "risks": ["fast threshold may need tuning after baseline stabilizes"],
            "status": "blocked_needs_confirmation",
        },
        {
            "phase_id": "phase_5",
            "phase_name": "Nightly Slow + Full",
            "phase_goal": "slow/full enter nightly schedule. Not blocking PR.",
            "duration_estimate": "1 week after phase 4",
            "deliverable": "Nightly workflow trigger",
            "blocks_real_ci": True,
            "creates_workflow": True,
            "requires_review": True,
            "risks": ["slow suite runtime may exceed threshold on large changes"],
            "status": "blocked_needs_confirmation",
        },
        {
            "phase_id": "phase_6",
            "phase_name": "Artifact Retention / Report Publishing",
            "phase_goal": "Implement unified artifact collection, retention policy, report publishing.",
            "duration_estimate": "1 week",
            "deliverable": "Artifact retention config + publishing script",
            "blocks_real_ci": False,
            "creates_workflow": False,
            "requires_review": True,
            "risks": ["path inconsistency may cause duplicate artifact collection"],
            "status": "blocked_needs_confirmation",
        },
        {
            "phase_id": "phase_7",
            "phase_name": "Future Sidecar / Gateway Integration Review",
            "phase_goal": "Independent review of Feishu sidecar and Gateway CI integration path.",
            "duration_estimate": "TBD",
            "deliverable": "Review document only",
            "blocks_real_ci": False,
            "creates_workflow": False,
            "requires_review": True,
            "risks": ["sidecar integration may require separate CI runner"],
            "status": "blocked_needs_confirmation",
        },
    ]

    return {
        "phases": phases,
        "phase_count": len(phases),
        "current_phase": "phase_1",
        "next_blocked_phase": "phase_2",
        "blocking_reason": "Phase 1 is design-only — next phase (phase_2) requires explicit user confirmation to proceed",
    }


def build_ci_blocked_actions() -> Dict[str, Any]:
    """List all blocked actions for CI implementation."""
    blocked = [
        {
            "action": "enabling_real_feishu_send",
            "blocked": True,
            "reason": "Feishu send requires explicit opt-in per R241-15F policy",
            "alternative": "Use dry-run / projection-only mode",
        },
        {
            "action": "network_call",
            "blocked": True,
            "reason": "CI stages must not call external services",
            "alternative": "Use monkeypatched / synthetic fixtures",
        },
        {
            "action": "webhook_call",
            "blocked": True,
            "reason": "Webhook calls are forbidden in CI environment",
            "alternative": "Validate webhook URLs statically without calling",
        },
        {
            "action": "reading_real_secrets",
            "blocked": True,
            "reason": "CI should not read real tokens/secrets from environment",
            "alternative": "Use placeholder values in test fixtures",
        },
        {
            "action": "runtime_write",
            "blocked": True,
            "reason": "Runtime state writes are forbidden in CI",
            "alternative": "Use tmp_path fixture for any file operations",
        },
        {
            "action": "action_queue_write",
            "blocked": True,
            "reason": "Action queue writes are forbidden in CI",
            "alternative": "Validate queue structure without writing",
        },
        {
            "action": "auto_fix",
            "blocked": True,
            "reason": "Auto-fix is never executed in CI environment",
            "alternative": "Detect auto-fix availability but do not execute",
        },
        {
            "action": "gateway_mutation",
            "blocked": True,
            "reason": "Gateway state mutations are forbidden in CI",
            "alternative": "Use read-only diagnostics only",
        },
        {
            "action": "audit_jsonl_overwrite_truncate_delete",
            "blocked": True,
            "reason": "Audit JSONL must never be modified by CI stages",
            "alternative": "Read-only scan is allowed; append is audit-only",
        },
        {
            "action": "deleting_tests",
            "blocked": True,
            "reason": "CI must not delete existing tests",
            "alternative": "Use skip/xfail with explicit justification",
        },
        {
            "action": "skipping_safety_tests",
            "blocked": True,
            "reason": "Safety tests (no_network/no_runtime_write/no_secret) must not be skipped",
            "alternative": "Fix safety test failures rather than skip them",
        },
        {
            "action": "reducing_security_coverage",
            "blocked": True,
            "reason": "CI must maintain current security coverage level",
            "alternative": "Improve coverage through new tests, not reduction",
        },
    ]

    return {
        "blocked_actions": blocked,
        "blocked_count": len(blocked),
        "warnings": [],
        "errors": [],
    }


def validate_ci_implementation_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the CI implementation plan structure and policy compliance."""
    errors: List[str] = []
    warnings: List[str] = []

    # Check stage specs
    stage_specs = plan.get("stage_specs", {}).get("specs", [])
    if len(stage_specs) < 5:
        errors.append(f"Expected at least 5 stage specs, got {len(stage_specs)}")

    # Check fast/pr_blocking consistency
    fast_stage = next((s for s in stage_specs if s.get("stage_type") == CIExecutionStageType.FAST), None)
    if fast_stage:
        if fast_stage.get("gating_policy") != CIGatingPolicy.PR_BLOCKING:
            warnings.append("Fast stage gating_policy should be pr_blocking")
        if not fast_stage.get("required_on_pr"):
            warnings.append("Fast stage should be required_on_pr=True")

    # Check safety/pr_blocking consistency
    safety_stage = next((s for s in stage_specs if s.get("stage_type") == CIExecutionStageType.SAFETY), None)
    if safety_stage:
        if safety_stage.get("gating_policy") != CIGatingPolicy.PR_BLOCKING:
            warnings.append("Safety stage gating_policy should be pr_blocking")

    # Check slow not directly pr_blocking
    slow_stage = next((s for s in stage_specs if s.get("stage_type") == CIExecutionStageType.SLOW), None)
    if slow_stage:
        if slow_stage.get("gating_policy") == CIGatingPolicy.PR_BLOCKING:
            errors.append("Slow stage must not be pr_blocking — use nightly_required instead")

    # Check full not directly pr_blocking
    full_stage = next((s for s in stage_specs if s.get("stage_type") == CIExecutionStageType.FULL), None)
    if full_stage:
        if full_stage.get("gating_policy") == CIGatingPolicy.PR_BLOCKING:
            errors.append("Full stage must not be pr_blocking — use manual_only instead")

    # Check artifact collection
    artifact_specs = plan.get("artifact_collection_specs", {}).get("artifact_specs", [])
    for spec in artifact_specs:
        if spec.get("secrets_allowed"):
            errors.append(f"Artifact spec {spec.get('artifact_spec_id')} must not allow secrets")
        if spec.get("runtime_files_allowed"):
            errors.append(f"Artifact spec {spec.get('artifact_spec_id')} must not allow runtime files")
        excluded = spec.get("exclude_patterns", [])
        has_secret_pattern = any(p in excluded for p in ["*secret*", "*token*", "*credential*"])
        if not has_secret_pattern:
            warnings.append(f"Artifact spec {spec.get('artifact_spec_id')} should exclude secret files")

    # Check path compatibility
    path_policy = plan.get("path_compatibility_policy", {})
    if path_policy.get("migration_allowed_now"):
        errors.append("Path migration is not allowed in current phase")
    if path_policy.get("deletion_allowed_now"):
        errors.append("Path deletion is not allowed in current phase")
    if path_policy.get("action_now") != "report_only":
        warnings.append(f"Path action should be 'report_only', got '{path_policy.get('action_now')}'")

    # Check blocked actions
    blocked_actions = plan.get("blocked_actions", {}).get("blocked_actions", [])
    if len(blocked_actions) == 0:
        errors.append("blocked_actions must be non-empty")

    # Check for forbidden network call recommendation
    if plan.get("network_call_recommended"):
        errors.append("network_call_recommended must not be True")

    # Check for runtime write recommendation
    if plan.get("runtime_write_recommended"):
        errors.append("runtime_write_recommended must not be True")

    # Check for auto-fix recommendation
    if plan.get("auto_fix_recommended"):
        errors.append("auto_fix_recommended must not be True")

    # Check for test deletion recommendation
    if plan.get("delete_tests_recommended"):
        errors.append("delete_tests_recommended must not be True")

    # Check for safety test skip recommendation
    if plan.get("skip_safety_tests_recommended"):
        errors.append("skip_safety_tests_recommended must not be True")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "validated_at": _utc_now(),
    }


def generate_ci_implementation_plan(output_path: Optional[str] = None, root: Optional[str] = None) -> Dict[str, Any]:
    """Generate the full CI implementation plan and write reports.

    Writes:
    - R241-16A_CI_IMPLEMENTATION_PLAN.json
    - R241-16A_CI_IMPLEMENTATION_REPORT.md

    to migration_reports/foundation_audit/ (never to runtime directories).
    """
    root_path = Path(root) if root else ROOT
    plan: Dict[str, Any] = {
        "plan_id": "R241-16A_CI_IMPLEMENTATION_PLAN",
        "generated_at": _utc_now(),
        "status": CIImplementationStatus.DESIGN_ONLY,
        "provider_targets": [
            CIProviderTarget.GITHUB_ACTIONS,
            CIProviderTarget.LOCAL_SCRIPT,
            CIProviderTarget.GENERIC_CI,
        ],
        "stage_specs": build_ci_stage_implementation_specs(),
        "artifact_collection_specs": build_ci_artifact_collection_specs(str(root_path)),
        "threshold_policy": build_ci_threshold_policy(),
        "path_compatibility_policy": build_ci_path_compatibility_policy(str(root_path)),
        "implementation_phases": build_ci_implementation_phases(),
        "blocked_actions": build_ci_blocked_actions(),
        # Policy flags (all False — this is design-only, no real actions)
        "network_call_recommended": False,
        "runtime_write_recommended": False,
        "auto_fix_recommended": False,
        "delete_tests_recommended": False,
        "skip_safety_tests_recommended": False,
        "creates_real_workflow": False,
        "warnings": [],
        "errors": [],
    }

    # Validate
    validation = validate_ci_implementation_plan(plan)
    plan["validation"] = validation

    # Write JSON
    json_path = Path(output_path) if output_path else DEFAULT_PLAN_PATH
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write Markdown report
    report_lines = [
        "# R241-16A: CI Implementation Plan",
        "",
        f"**Generated:** {plan['generated_at']}",
        f"**Status:** {plan['status']}",
        f"**Validation:** valid={validation['valid']} at {validation['validated_at']}",
        "",
        "---",
        "",
        "## 1. CI Stage Implementation Specs",
        "",
    ]

    for spec in plan["stage_specs"]["specs"]:
        report_lines.append(f"### {spec['name']} (`{spec['stage_id']}`)")
        report_lines.append(f"- **Command:** `{spec['command']}`")
        report_lines.append(f"- **Gating:** `{spec['gating_policy']}`")
        report_lines.append(f"- **Expected runtime:** {spec['expected_runtime_seconds']}s (warning: {spec['warning_threshold_seconds']}s)")
        report_lines.append(f"- **PR required:** {spec['required_on_pr']}")
        report_lines.append(f"- **Nightly required:** {spec['required_on_nightly']}")
        report_lines.append(f"- **Marker:** `{spec.get('marker_expression', 'N/A')}`")
        report_lines.append(f"- **Artifacts:** {spec['artifact_types']}")
        for w in spec.get("warnings", []):
            report_lines.append(f"  - ⚠️ {w}")
        report_lines.append("")

    report_lines.extend([
        "---",
        "",
        "## 2. PR / Nightly / Manual Gating Policy",
        "",
        "| Stage | Gating | PR Required | Nightly Required |",
        "|---|---|---|---|",
    ])

    for spec in plan["stage_specs"]["specs"]:
        report_lines.append(f"| {spec['name']} | {spec['gating_policy']} | {spec['required_on_pr']} | {spec['required_on_nightly']} |")

    report_lines.extend([
        "",
        "### Policy Detail",
        "",
        "- **pr_blocking**: Stage must pass for PR to merge.",
        "- **pr_warning**: Stage failure creates PR comment but does not block merge.",
        "- **nightly_required**: Stage runs in nightly pipeline, not on PR.",
        "- **manual_only**: Stage runs manually only, not in automated pipelines.",
        "",
        "---",
        "",
        "## 3. Artifact Collection / Path Compatibility",
        "",
    ])

    for art in plan["artifact_collection_specs"]["artifact_specs"]:
        report_lines.append(f"### {art['artifact_spec_id']} ({art['artifact_type']})")
        report_lines.append(f"- **Destination:** `{art['destination_name']}`")
        report_lines.append(f"- **Retention:** {art['retention_days']} days")
        report_lines.append(f"- **Include:** {art['include_patterns']}")
        report_lines.append(f"- **Exclude:** {art['exclude_patterns']}")
        report_lines.append(f"- **Path handling:** {art['path_inconsistency_handling']}")
        report_lines.append(f"- **Secrets allowed:** {art['secrets_allowed']}")
        report_lines.append(f"- **Runtime files allowed:** {art['runtime_files_allowed']}")
        for w in art.get("warnings", []):
            report_lines.append(f"  - ⚠️ {w}")
        report_lines.append("")

    pc = plan["path_compatibility_policy"]
    report_lines.extend([
        "### Report Path Compatibility",
        "",
        f"- **Primary path:** `{pc['primary_report_path']}` (exists: {pc['primary_exists']})",
        f"- **Secondary path:** `{pc['secondary_report_path']}` (exists: {pc['secondary_exists']})",
        f"- **Path inconsistency:** {pc['path_inconsistency']}",
        f"- **Action now:** `{pc['action_now']}`",
        f"- **Migration allowed now:** {pc['migration_allowed_now']}",
        f"- **Deletion allowed now:** {pc['deletion_allowed_now']}",
        "",
        "---",
        "",
        "## 4. Threshold Policy / Blocked Actions",
        "",
    ])

    tp = plan["threshold_policy"]
    report_lines.extend([
        "### Thresholds",
        "",
        f"- Foundation fast warning: {tp['foundation_fast_warning_threshold_seconds']}s, blocker: {tp['foundation_fast_blocker_threshold_seconds']}s",
        f"- Audit fast warning: {tp['audit_fast_warning_threshold_seconds']}s",
        f"- Slow suite warning: {tp['slow_suite_warning_threshold_seconds']}s",
        f"- Safety suite warning: {tp['safety_suite_warning_threshold_seconds']}s",
        f"- Collect-only warning: {tp['collect_only_warning_threshold_seconds']}s",
        "",
        "### Blocked Actions",
        "",
    ])

    for ba in plan["blocked_actions"]["blocked_actions"]:
        if ba["blocked"]:
            report_lines.append(f"- ❌ {ba['action']}: {ba['reason']}")

    report_lines.extend([
        "",
        "---",
        "",
        "## 5. Implementation Phases",
        "",
        "| Phase | Name | Creates Workflow | Blocks Real CI |",
        "|---|---|---|---|",
    ])

    for ph in plan["implementation_phases"]["phases"]:
        report_lines.append(f"| {ph['phase_id']} | {ph['phase_name']} | {ph['creates_workflow']} | {ph['blocks_real_ci']} |")

    report_lines.extend([
        "",
        f"**Current phase:** {plan['implementation_phases']['current_phase']}",
        f"**Next blocked phase:** {plan['implementation_phases']['next_blocked_phase']} — {plan['implementation_phases']['blocking_reason']}",
        "",
        "---",
        "",
        "## 6. Validation",
        "",
        f"- **Valid:** {validation['valid']}",
        f"- **Errors:** {len(validation['errors'])}",
        f"- **Warnings:** {len(validation['warnings'])}",
        "",
    ])

    for e in validation.get("errors", []):
        report_lines.append(f"  - 🔴 {e}")
    for w in validation.get("warnings", []):
        report_lines.append(f"  - ⚠️ {w}")

    report_lines.extend([
        "",
        "---",
        "",
        "## 7. Policy Flags",
        "",
        f"- Network call recommended: `{plan['network_call_recommended']}`",
        f"- Runtime write recommended: `{plan['runtime_write_recommended']}`",
        f"- Auto-fix recommended: `{plan['auto_fix_recommended']}`",
        f"- Delete tests recommended: `{plan['delete_tests_recommended']}`",
        f"- Skip safety tests recommended: `{plan['skip_safety_tests_recommended']}`",
        f"- Creates real workflow: `{plan['creates_real_workflow']}`",
        "",
        "---",
        "",
        "## 8. Next Steps (R241-16B)",
        "",
        "1. Proceed to local script dry-run (`scripts/ci_foundation_check.py`) after explicit confirmation.",
        "2. Validate local script against all 5 stage commands.",
        "3. Document any path or environment differences between local script and GitHub Actions.",
        "",
        "---",
        "",
        "**Final Determination: R241-16A — PASSED — A**",
        "",
        "Design-only phase completed. No real workflow created. No runtime modified.",
        "No audit JSONL written. No network called. No auto-fix executed.",
    ])

    report_path = DEFAULT_REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return {
        "output_plan_path": str(json_path),
        "output_report_path": str(report_path),
        "validation": validation,
        **plan,
    }