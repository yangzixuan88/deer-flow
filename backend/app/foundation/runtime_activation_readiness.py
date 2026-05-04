"""
R241-18A: Runtime Activation Readiness Review

Read-only review module — does NOT activate any runtime.
Does NOT enable scheduler, auto-fix, Feishu send, webhook call, secret read,
runtime write, memory cleanup, asset promotion, prompt replacement, or
Gateway main path replacement.

This module classifies each R241 surface domain into:
  - ready_for_runtime_activation_design
  - ready_for_guarded_dryrun_activation
  - read_only_only
  - append_only_only
  - manual_only
  - report_only
  - blocked
  - unknown

Outputs R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json + .md
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RuntimeActivationStatus(str, Enum):
    READY_FOR_RUNTIME_ACTIVATION_DESIGN = "ready_for_runtime_activation_design"
    READY_FOR_GUARDED_DRYRUN_ACTIVATION = "ready_for_guarded_dryrun_activation"
    READ_ONLY_ONLY = "read_only_only"
    APPEND_ONLY_ONLY = "append_only_only"
    MANUAL_ONLY = "manual_only"
    REPORT_ONLY = "report_only"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class RuntimeActivationDecision(str, Enum):
    APPROVE_ACTIVATION_DESIGN = "approve_activation_design"
    APPROVE_GUARDED_DRYRUN = "approve_guarded_dryrun"
    KEEP_READ_ONLY = "keep_read_only"
    KEEP_APPEND_ONLY = "keep_append_only"
    KEEP_MANUAL_ONLY = "keep_manual_only"
    KEEP_REPORT_ONLY = "keep_report_only"
    BLOCK_RUNTIME_ACTIVATION = "block_runtime_activation"
    UNKNOWN = "unknown"


class RuntimeActivationRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class RuntimeSurfaceDomain(str, Enum):
    FOUNDATION_DIAGNOSTIC_CLI = "foundation_diagnostic_cli"
    READ_ONLY_DIAGNOSTIC_API = "read_only_diagnostic_api"
    APPEND_ONLY_AUDIT = "append_only_audit"
    AUDIT_QUERY = "audit_query"
    TREND_REPORT = "trend_report"
    FEISHU_SUMMARY_DRYRUN = "feishu_summary_dryrun"
    FEISHU_PRESEND_VALIDATOR = "feishu_presend_validator"
    FEISHU_MANUAL_SEND = "feishu_manual_send"
    CI_MANUAL_WORKFLOW = "ci_manual_workflow"
    UPSTREAM_ADAPTER_PATCH = "upstream_adapter_patch"
    TRUTH_STATE = "truth_state"
    MEMORY = "memory"
    ASSET = "asset"
    PROMPT = "prompt"
    TOOL_RUNTIME = "tool_runtime"
    RTCM = "rtcm"
    GATEWAY = "gateway"
    MODE_ROUTER = "mode_router"
    SCHEDULER = "scheduler"
    AUTO_FIX = "auto_fix"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Prohibited-action sentinel
# ---------------------------------------------------------------------------

_ACTIONS_EXECUTED: list[str] = []


def _record_action(action: str) -> None:
    _ACTIONS_EXECUTED.append(action)


def get_actions_record() -> list[str]:
    return list(_ACTIONS_EXECUTED)


# ---------------------------------------------------------------------------
# Data objects
# ---------------------------------------------------------------------------


class RuntimeActivationSurface:
    def __init__(
        self,
        surface_id: str,
        domain: RuntimeSurfaceDomain,
        name: str,
        source_stage: str,
        current_state: str,
        proposed_activation_state: str,
        activation_status: RuntimeActivationStatus,
        decision: RuntimeActivationDecision,
        risk_level: RuntimeActivationRiskLevel,
        read_only_safe: bool = False,
        append_only_safe: bool = False,
        writes_runtime: bool = False,
        requires_auth: bool = False,
        requires_rate_limit: bool = False,
        requires_user_confirmation: bool = False,
        requires_backup: bool = False,
        requires_rollback: bool = False,
        requires_dryrun: bool = False,
        requires_manual_review: bool = False,
        blocked_reasons: list[str] | None = None,
        required_tests: list[str] | None = None,
        rollback_plan: str | None = None,
        evidence_refs: list[str] | None = None,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ):
        self.surface_id = surface_id
        self.domain = domain
        self.name = name
        self.source_stage = source_stage
        self.current_state = current_state
        self.proposed_activation_state = proposed_activation_state
        self.activation_status = activation_status
        self.decision = decision
        self.risk_level = risk_level
        self.read_only_safe = read_only_safe
        self.append_only_safe = append_only_safe
        self.writes_runtime = writes_runtime
        self.requires_auth = requires_auth
        self.requires_rate_limit = requires_rate_limit
        self.requires_user_confirmation = requires_user_confirmation
        self.requires_backup = requires_backup
        self.requires_rollback = requires_rollback
        self.requires_dryrun = requires_dryrun
        self.requires_manual_review = requires_manual_review
        self.blocked_reasons = blocked_reasons or []
        self.required_tests = required_tests or []
        self.rollback_plan = rollback_plan
        self.evidence_refs = evidence_refs or []
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        def _v(val: Any) -> str:
            if hasattr(val, "value"):
                return val.value
            if isinstance(val, Enum):
                return val.value
            return str(val)

        return {
            "surface_id": self.surface_id,
            "domain": _v(self.domain),
            "name": self.name,
            "source_stage": self.source_stage,
            "current_state": self.current_state,
            "proposed_activation_state": self.proposed_activation_state,
            "activation_status": _v(self.activation_status),
            "decision": _v(self.decision),
            "risk_level": _v(self.risk_level),
            "read_only_safe": self.read_only_safe,
            "append_only_safe": self.append_only_safe,
            "writes_runtime": self.writes_runtime,
            "requires_auth": self.requires_auth,
            "requires_rate_limit": self.requires_rate_limit,
            "requires_user_confirmation": self.requires_user_confirmation,
            "requires_backup": self.requires_backup,
            "requires_rollback": self.requires_rollback,
            "requires_dryrun": self.requires_dryrun,
            "requires_manual_review": self.requires_manual_review,
            "blocked_reasons": self.blocked_reasons,
            "required_tests": self.required_tests,
            "rollback_plan": self.rollback_plan,
            "evidence_refs": self.evidence_refs,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class RuntimeActivationBlocker:
    def __init__(
        self,
        blocker_id: str,
        domain: RuntimeSurfaceDomain,
        blocker_type: str,
        risk_level: RuntimeActivationRiskLevel,
        description: str,
        affected_surfaces: list[str],
        required_resolution: str,
        can_be_deferred: bool = False,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ):
        self.blocker_id = blocker_id
        self.domain = domain
        self.blocker_type = blocker_type
        self.risk_level = risk_level
        self.description = description
        self.affected_surfaces = affected_surfaces
        self.required_resolution = required_resolution
        self.can_be_deferred = can_be_deferred
        self.warnings = warnings or []
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        def _v(val: Any) -> str:
            return val.value if hasattr(val, "value") else str(val)

        return {
            "blocker_id": self.blocker_id,
            "domain": _v(self.domain),
            "blocker_type": self.blocker_type,
            "risk_level": _v(self.risk_level),
            "description": self.description,
            "affected_surfaces": self.affected_surfaces,
            "required_resolution": self.required_resolution,
            "can_be_deferred": self.can_be_deferred,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# 1. Load Runtime Activation Sources
# ---------------------------------------------------------------------------


def load_runtime_activation_sources(root: str | None = None) -> dict[str, Any]:
    """
    Load all prior R241 reports needed for activation readiness review.
    Missing optional reports are recorded as warnings, not errors.
    Raises if R241-17D mainline_resume_allowed is not True.
    """
    if root is None:
        root = os.getcwd()

    reports_dir = os.path.join(root, "backend", "migration_reports", "foundation_audit")

    sources: dict[str, Any] = {
        "loaded_reports": {},
        "missing_reports": [],
        "warnings": [],
        "errors": [],
    }

    # Required report files
    required = {
        "R241-17D": "R241-17D_MAINLINE_RESUME_GATE.json",
        "R241-17C": "R241-17C_UPSTREAM_OPTIMIZATION_INTAKE_MATRIX.json",
        "R241-17B-C": "R241-17B_C_POST_PUBLISH_AUDIT_CONSISTENCY_REPAIR.json",
    }

    # Optional report files
    optional = {
        "R241-9A": "R241-9A_FOUNDATION_INTEGRATION_READINESS_MATRIX.json",
        "R241-9B": "R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.json",
        "R241-10C": "R241-10C_FEISHU_SUMMARY_DRYRUN_CLI_SAMPLE.json",
        "R241-11C": "R241-11D_AUDIT_QUERY_ENGINE_REPORT.md",
        "R241-11D": "R241-11C_APPEND_ONLY_JSONL_WRITER_REPORT.md",
        "R241-12D": "R241-12D_NIGHTLY_TREND_CLI_COMPLETION_REPORT.md",
        "R241-13D": "R241-13D_MANUAL_SEND_POLICY_DESIGN.md",
        "R241-14B": "R241-14B_FEISHU_PRESEND_VALIDATOR_REPORT.md",
        "R241-14C": "R241-14C_FEISHU_PRESEND_VALIDATE_ONLY_CLI_REPORT.md",
        "R241-15F": "R241-15F_CI_MATRIX_REPORT.md",
    }

    # Load required reports
    for key, filename in required.items():
        path = os.path.join(reports_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    sources["loaded_reports"][key] = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                sources["errors"].append(f"Failed to load {filename}: {e}")
        else:
            sources["errors"].append(f"Required report missing: {filename}")

    # Load optional reports
    for key, filename in optional.items():
        path = os.path.join(reports_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    sources["loaded_reports"][key] = json.load(f)
            except (OSError, json.JSONDecodeError):
                sources["warnings"].append(f"Optional report corrupted, skipping: {filename}")
        else:
            sources["warnings"].append(f"Optional report not found (skipping): {filename}")
            sources["missing_reports"].append(key)

    # Validate mainline resume gate
    gate = sources["loaded_reports"].get("R241-17D", {})
    if not gate.get("mainline_resume_allowed"):
        sources["errors"].append(
            f"mainline_resume_allowed is not True in R241-17D: {gate.get('blocked_reasons')}"
        )

    # Validate upstream matrix
    matrix = sources["loaded_reports"].get("R241-17C", {})
    if matrix.get("forbidden_candidates_count", 0) > 0:
        sources["warnings"].append(
            f"Upstream matrix has {matrix.get('forbidden_candidates_count')} forbidden candidates"
        )

    # Validate post-publish audit
    audit = sources["loaded_reports"].get("R241-17B-C", {})
    audit_status = audit.get("audit_result", {}).get("status", "unknown")
    if audit_status != "operationally_closed_with_deviation":
        sources["warnings"].append(
            f"Post-publish audit status is '{audit_status}', expected operationally_closed_with_deviation"
        )

    return sources


# ---------------------------------------------------------------------------
# 2. Discover Runtime Activation Surfaces
# ---------------------------------------------------------------------------


def discover_runtime_activation_surfaces(root: str | None = None) -> list[dict[str, Any]]:
    """
    Discover all surface domains from prior reports and module existence.
    Returns a list of surface dicts ready for classification.
    """
    if root is None:
        root = os.getcwd()

    surfaces: list[dict[str, Any]] = []
    surface_id = 1

    def make_surface(
        domain: RuntimeSurfaceDomain,
        name: str,
        source_stage: str,
        current_state: str,
        proposed: str,
        evidence_refs: list[str],
    ) -> dict[str, Any]:
        nonlocal surface_id
        s = {
            "surface_id": f"SURFACE-{surface_id:03d}",
            "domain": domain.value,
            "name": name,
            "source_stage": source_stage,
            "current_state": current_state,
            "proposed_activation_state": proposed,
            "evidence_refs": evidence_refs,
        }
        surface_id += 1
        return s

    # ---- A. Read-only diagnostic surfaces (low risk) ----

    surfaces.append(make_surface(
        RuntimeSurfaceDomain.FOUNDATION_DIAGNOSTIC_CLI,
        "Foundation Diagnose CLI",
        "R241-9A/9B",
        "read_only CLI, no runtime write",
        "read_only CLI only",
        ["R241-9A", "R241-9B"],
    ))

    surfaces.append(make_surface(
        RuntimeSurfaceDomain.AUDIT_QUERY,
        "Audit Query Engine",
        "R241-11D",
        "read_only JSONL query, no write",
        "read_only only",
        ["R241-11D"],
    ))

    surfaces.append(make_surface(
        RuntimeSurfaceDomain.TREND_REPORT,
        "Nightly Trend Report CLI",
        "R241-12D",
        "read_only CLI, generates report artifact",
        "read_only report artifact",
        ["R241-12D"],
    ))

    surfaces.append(make_surface(
        RuntimeSurfaceDomain.FEISHU_SUMMARY_DRYRUN,
        "Feishu Summary Dry-run Preview",
        "R241-10C",
        "dry-run CLI, no real send",
        "read_only dry-run preview only",
        ["R241-10C"],
    ))

    surfaces.append(make_surface(
        RuntimeSurfaceDomain.FEISHU_PRESEND_VALIDATOR,
        "Feishu Pre-send Validate-only CLI",
        "R241-14B/14C",
        "validate-only CLI, no send",
        "validate-only read_only CLI",
        ["R241-14B", "R241-14C"],
    ))

    # ---- B. Append-only surfaces ----

    surfaces.append(make_surface(
        RuntimeSurfaceDomain.APPEND_ONLY_AUDIT,
        "Audit JSONL Append-only Writer",
        "R241-11C",
        "append-only JSONL writer, no overwrite",
        "append_only with retention policy",
        ["R241-11C"],
    ))

    # ---- C. Manual-only surfaces ----

    surfaces.append(make_surface(
        RuntimeSurfaceDomain.FEISHU_MANUAL_SEND,
        "Feishu Manual Send (future path)",
        "R241-13D",
        "policy designed but not active",
        "manual_only with webhook allowlist + confirmation",
        ["R241-13D"],
    ))

    surfaces.append(make_surface(
        RuntimeSurfaceDomain.CI_MANUAL_WORKFLOW,
        "CI Manual Workflow Dispatch",
        "R241-15F",
        "CI matrix exists, dispatch is manual",
        "manual_only dispatch",
        ["R241-15F"],
    ))

    # ---- D. Upstream adapter patch candidates ----

    surfaces.append(make_surface(
        RuntimeSurfaceDomain.UPSTREAM_ADAPTER_PATCH,
        "Upstream Adapter Patch Integration",
        "R241-17C",
        "4 adapter patch candidates identified",
        "guarded_dryrun adapter patch",
        ["R241-17C"],
    ))

    # ---- E. Blocked runtime mutation surfaces ----

    blocked_runtime_surfaces = [
        (RuntimeSurfaceDomain.MEMORY, "Memory Runtime", "memory cleanup"),
        (RuntimeSurfaceDomain.ASSET, "Asset Registry", "asset promotion/elimination"),
        (RuntimeSurfaceDomain.PROMPT, "Prompt Governance", "prompt replacement"),
        (RuntimeSurfaceDomain.TOOL_RUNTIME, "Tool Runtime Enforcement", "tool enforcement on main path"),
        (RuntimeSurfaceDomain.GATEWAY, "Gateway Main Run Path", "gateway main path replacement"),
        (RuntimeSurfaceDomain.MODE_ROUTER, "Mode Router", "mode router replacement"),
        (RuntimeSurfaceDomain.RTCM, "RTCM State Mutation", "rtcm state mutation"),
        (RuntimeSurfaceDomain.SCHEDULER, "Scheduler / Watchdog", "scheduler/watchdog activation"),
        (RuntimeSurfaceDomain.AUTO_FIX, "Auto-fix", "auto-fix activation"),
    ]

    for domain, name, blocked_reason in blocked_runtime_surfaces:
        surfaces.append(make_surface(
            domain,
            name,
            "R241-17D blocker list",
            "blocked — runtime mutation risk",
            "BLOCKED — no activation",
            [],
        ))
        # Annotate blocked reason in the dict
        surfaces[-1]["_blocked_reason"] = blocked_reason

    # ---- F. Truth state (read-only projection) ----

    surfaces.append(make_surface(
        RuntimeSurfaceDomain.TRUTH_STATE,
        "Truth State Projection",
        "R241-16Y",
        "read_only projection, no state write",
        "read_only_only",
        ["R241-16Y"],
    ))

    return surfaces


# ---------------------------------------------------------------------------
# 3. Classify Runtime Activation Surface
# ---------------------------------------------------------------------------


def classify_runtime_activation_surface(surface: dict[str, Any]) -> dict[str, Any]:
    """
    Classify a surface into RuntimeActivationStatus and RuntimeActivationDecision
    based on domain, current_state, and blocked_reason annotation.
    """
    domain = surface.get("domain", "unknown")
    current = surface.get("current_state", "")
    proposed = surface.get("proposed_activation_state", "")
    blocked_reason = surface.get("_blocked_reason", "")
    evidence_refs = surface.get("evidence_refs", [])

    result = dict(surface)

    # ---- Blocked runtime mutation surfaces ----
    blocked_domains = {
        "memory": "Memory cleanup is a runtime mutation — blocked per R241 mandate",
        "asset": "Asset promotion/elimination is a runtime mutation — blocked",
        "prompt": "Prompt replacement is a runtime mutation — blocked",
        "tool_runtime": "Tool runtime enforcement on main path is blocked",
        "gateway": "Gateway main run path replacement is forbidden",
        "mode_router": "Mode router replacement is forbidden",
        "rtcm": "RTCM state mutation is forbidden",
        "scheduler": "Scheduler/watchdog activation is forbidden",
        "auto_fix": "Auto-fix activation is forbidden",
    }

    if domain in blocked_domains or blocked_reason:
        result["activation_status"] = RuntimeActivationStatus.BLOCKED.value
        result["decision"] = RuntimeActivationDecision.BLOCK_RUNTIME_ACTIVATION.value
        result["risk_level"] = RuntimeActivationRiskLevel.CRITICAL.value
        result["read_only_safe"] = False
        result["append_only_safe"] = False
        result["writes_runtime"] = True
        result["requires_dryrun"] = False
        result["requires_manual_review"] = True
        result["blocked_reasons"] = [blocked_domains.get(domain, blocked_reason or "Runtime mutation blocked")]
        result["warnings"] = ["High risk — runtime mutation could destabilize R241 foundation"]
        return result

    # ---- Read-only diagnostic surfaces ----
    readonly_domains = {
        "foundation_diagnostic_cli",
        "audit_query",
        "trend_report",
        "feishu_summary_dryrun",
        "feishu_presend_validator",
        "truth_state",
    }

    if domain in readonly_domains:
        result["activation_status"] = RuntimeActivationStatus.READY_FOR_RUNTIME_ACTIVATION_DESIGN.value
        result["decision"] = RuntimeActivationDecision.APPROVE_ACTIVATION_DESIGN.value
        result["risk_level"] = RuntimeActivationRiskLevel.LOW.value
        result["read_only_safe"] = True
        result["append_only_safe"] = False
        result["writes_runtime"] = False
        result["requires_dryrun"] = False
        result["requires_manual_review"] = False
        result["blocked_reasons"] = []
        result["required_tests"] = ["read_only_validation", "output_format_validation"]
        return result

    # ---- Append-only surfaces ----
    if domain == "append_only_audit":
        result["activation_status"] = RuntimeActivationStatus.APPEND_ONLY_ONLY.value
        result["decision"] = RuntimeActivationDecision.KEEP_APPEND_ONLY.value
        result["risk_level"] = RuntimeActivationRiskLevel.MEDIUM.value
        result["read_only_safe"] = False
        result["append_only_safe"] = True
        result["writes_runtime"] = True  # appends to audit log
        result["requires_auth"] = True
        result["requires_rate_limit"] = True
        result["requires_backup"] = True
        result["requires_rollback"] = True
        result["requires_dryrun"] = True
        result["blocked_reasons"] = []
        result["required_tests"] = ["append_only_guard", "retention_policy_validation"]
        result["rollback_plan"] = "Truncate last N lines of JSONL; rehydrate from backup"
        return result

    # ---- Manual-only surfaces ----
    manual_domains = {"feishu_manual_send", "ci_manual_workflow"}

    if domain in manual_domains:
        result["activation_status"] = RuntimeActivationStatus.MANUAL_ONLY.value
        result["decision"] = RuntimeActivationDecision.KEEP_MANUAL_ONLY.value
        result["risk_level"] = RuntimeActivationRiskLevel.HIGH.value
        result["read_only_safe"] = False
        result["append_only_safe"] = False
        result["writes_runtime"] = True
        result["requires_auth"] = True
        result["requires_user_confirmation"] = True
        result["requires_dryrun"] = True
        result["requires_manual_review"] = True
        result["blocked_reasons"] = []
        result["required_tests"] = ["webhook_allowlist_validation", "presend_validation", "dry_run_confirmation"]
        result["rollback_plan"] = "Delete message via API; revoke webhook token"
        return result

    # ---- Guarded dry-run surfaces ----
    guarded_domains = {"upstream_adapter_patch"}

    if domain in guarded_domains:
        result["activation_status"] = RuntimeActivationStatus.READY_FOR_GUARDED_DRYRUN_ACTIVATION.value
        result["decision"] = RuntimeActivationDecision.APPROVE_GUARDED_DRYRUN.value
        result["risk_level"] = RuntimeActivationRiskLevel.MEDIUM.value
        result["read_only_safe"] = False
        result["append_only_safe"] = False
        result["writes_runtime"] = False
        result["requires_dryrun"] = True
        result["requires_manual_review"] = True
        result["requires_rollback"] = True
        result["blocked_reasons"] = []
        result["required_tests"] = ["dry_run_validation", "adapter_shadow_test", "rollback_test"]
        result["rollback_plan"] = "Revert adapter patch; restore original upstream reference"
        return result

    # ---- Report-only (high-risk upstream candidates) ----
    if domain == "report_only":
        result["activation_status"] = RuntimeActivationStatus.REPORT_ONLY.value
        result["decision"] = RuntimeActivationDecision.KEEP_REPORT_ONLY.value
        result["risk_level"] = RuntimeActivationRiskLevel.HIGH.value
        result["blocked_reasons"] = ["High risk — report-only until manual review complete"]
        return result

    # ---- Unknown ----
    result["activation_status"] = RuntimeActivationStatus.UNKNOWN.value
    result["decision"] = RuntimeActivationDecision.UNKNOWN.value
    result["risk_level"] = RuntimeActivationRiskLevel.UNKNOWN.value
    result["warnings"] = ["Could not auto-classify — needs manual review"]
    return result


# ---------------------------------------------------------------------------
# 4. Build Runtime Activation Blockers
# ---------------------------------------------------------------------------


def build_runtime_activation_blockers(surfaces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Generate blockers based on surface classification.
    """
    blockers: list[dict[str, Any]] = []
    blocker_id = 1

    def add_blocker(
        domain: RuntimeSurfaceDomain,
        blocker_type: str,
        risk: RuntimeActivationRiskLevel,
        description: str,
        affected: list[str],
        resolution: str,
        can_defer: bool = False,
    ) -> None:
        nonlocal blocker_id
        blockers.append({
            "blocker_id": f"BLOCKER-{blocker_id:03d}",
            "domain": domain.value,
            "blocker_type": blocker_type,
            "risk_level": risk.value,
            "description": description,
            "affected_surfaces": affected,
            "required_resolution": resolution,
            "can_be_deferred": can_defer,
            "warnings": [],
            "errors": [],
        })
        blocker_id += 1

    # Auth / rate-limit blockers for API surfaces
    api_surfaces = [s["surface_id"] for s in surfaces if s.get("domain") in (
        "feishu_manual_send", "audit_query", "append_only_audit"
    )]
    if api_surfaces:
        add_blocker(
            RuntimeSurfaceDomain.UNKNOWN,
            "missing_auth_policy",
            RuntimeActivationRiskLevel.HIGH,
            "API surfaces lack auth policy and rate-limit configuration",
            api_surfaces,
            "Define auth policy and rate-limit before any runtime activation",
        )

    # Webhook allowlist blocker for Feishu
    feishu_surfaces = [s["surface_id"] for s in surfaces if s.get("domain") == "feishu_manual_send"]
    if feishu_surfaces:
        add_blocker(
            RuntimeSurfaceDomain.FEISHU_MANUAL_SEND,
            "missing_webhook_allowlist",
            RuntimeActivationRiskLevel.CRITICAL,
            "Feishu manual send has no webhook allowlist — real push would be unconstrained",
            feishu_surfaces,
            "Define webhook URL allowlist and confirmation phrase before any send",
        )

    # Backup/rollback blocker for append-only and upstream adapter
    append_surfaces = [s["surface_id"] for s in surfaces if s.get("domain") == "append_only_audit"]
    if append_surfaces:
        add_blocker(
            RuntimeSurfaceDomain.APPEND_ONLY_AUDIT,
            "missing_backup_rollback",
            RuntimeActivationRiskLevel.MEDIUM,
            "Append-only audit lacks verified backup and rollback plan",
            append_surfaces,
            "Establish backup schedule and test rollback procedure",
        )

    # Runtime mutation blocker for all blocked surfaces
    mutation_surfaces = [s["surface_id"] for s in surfaces if s.get("activation_status") == "blocked"]
    if mutation_surfaces:
        add_blocker(
            RuntimeSurfaceDomain.UNKNOWN,
            "runtime_mutation_risk",
            RuntimeActivationRiskLevel.CRITICAL,
            "Multiple surfaces have runtime mutation risk — must remain blocked",
            mutation_surfaces,
            "Do not activate runtime mutation surfaces until explicit R241 design review",
            can_defer=False,
        )

    # Upstream adapter not reviewed
    adapter_surfaces = [s["surface_id"] for s in surfaces if s.get("domain") == "upstream_adapter_patch"]
    if adapter_surfaces:
        add_blocker(
            RuntimeSurfaceDomain.UPSTREAM_ADAPTER_PATCH,
            "upstream_adapter_not_reviewed",
            RuntimeActivationRiskLevel.MEDIUM,
            "4 upstream adapter patch candidates need manual review before dry-run",
            adapter_surfaces,
            "Manual review of adapter patch candidates required before guarded dry-run",
        )

    # No auto-fix enforcement
    auto_fix_surfaces = [s["surface_id"] for s in surfaces if s.get("domain") == "auto_fix"]
    if auto_fix_surfaces:
        add_blocker(
            RuntimeSurfaceDomain.AUTO_FIX,
            "auto_fix_not_approved",
            RuntimeActivationRiskLevel.CRITICAL,
            "Auto-fix is forbidden per R241 mandate",
            auto_fix_surfaces,
            "Keep auto-fix blocked — no activation path",
        )

    return blockers


# ---------------------------------------------------------------------------
# 5. Build Runtime Activation Sequence
# ---------------------------------------------------------------------------


def build_runtime_activation_sequence(review: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Build a phased recommended sequence for runtime activation.
    Progressive from read-only → guarded → append-only → manual → blocked design.
    """
    surfaces = review.get("surfaces", [])

    phases = [
        {
            "phase_id": "R241-18A-P1",
            "phase_name": "Read-only Runtime Entry",
            "phase_description": "Activate read-only CLI tools that pose no runtime risk",
            "target_statuses": [
                "ready_for_runtime_activation_design",
            ],
            "allowed_domains": [
                "foundation_diagnostic_cli",
                "audit_query",
                "trend_report",
                "feishu_summary_dryrun",
                "feishu_presend_validator",
                "truth_state",
            ],
            "prohibited_actions": [
                "real send", "scheduler", "runtime write", "webhook call",
            ],
            "required_guards": [
                "read_only_validation",
                "output_format_validation",
            ],
            "surfaces": [],
        },
        {
            "phase_id": "R241-18A-P2",
            "phase_name": "Guarded Dry-run Adapter",
            "phase_description": "Dry-run upstream adapter patches and health check projections",
            "target_statuses": [
                "ready_for_guarded_dryrun_activation",
            ],
            "allowed_domains": [
                "upstream_adapter_patch",
            ],
            "prohibited_actions": [
                "doctor --fix", "gateway restart", "real webhook",
            ],
            "required_guards": [
                "dry_run_validation",
                "adapter_shadow_test",
                "rollback_test",
            ],
            "surfaces": [],
        },
        {
            "phase_id": "R241-18A-P3",
            "phase_name": "Append-only Operational Audit",
            "phase_description": "Enable append-only audit with retention policy and rollback",
            "target_statuses": [
                "append_only_only",
            ],
            "allowed_domains": [
                "append_only_audit",
            ],
            "prohibited_actions": [
                "overwrite", "delete", "truncate without backup",
            ],
            "required_guards": [
                "append_only_guard",
                "retention_policy_validation",
                "backup_verification",
            ],
            "surfaces": [],
        },
        {
            "phase_id": "R241-18A-P4",
            "phase_name": "Manual Action Gate",
            "phase_description": "Design Feishu manual send and CI manual dispatch with explicit confirmation",
            "target_statuses": [
                "manual_only",
            ],
            "allowed_domains": [
                "feishu_manual_send",
                "ci_manual_workflow",
            ],
            "prohibited_actions": [
                "auto dispatch", "real send without confirmation",
            ],
            "required_guards": [
                "webhook_allowlist_validation",
                "presend_validation",
                "dry_run_confirmation",
                "explicit_confirmation_phrase",
            ],
            "surfaces": [],
        },
        {
            "phase_id": "R241-18A-P5",
            "phase_name": "Gated Runtime Mutation Design",
            "phase_description": "Design only — no activation of memory cleanup, asset promotion, prompt replacement, etc.",
            "target_statuses": [
                "blocked",
            ],
            "allowed_domains": [
                "memory", "asset", "prompt", "tool_runtime",
                "gateway", "mode_router", "rtcm", "scheduler", "auto_fix",
            ],
            "prohibited_actions": [
                "any runtime activation",
            ],
            "required_guards": [
                "explicit R241 design review",
                "rollback plan",
                "user confirmation",
            ],
            "surfaces": [],
        },
    ]

    result_phases = []
    for phase in phases:
        phase_surfaces = [
            s["surface_id"] for s in surfaces
            if s.get("domain") in phase["allowed_domains"]
            or s.get("activation_status") in phase["target_statuses"]
        ]
        p = dict(phase)
        p["surfaces"] = phase_surfaces
        p["surface_count"] = len(phase_surfaces)
        result_phases.append(p)

    return result_phases


# ---------------------------------------------------------------------------
# 6. Validate Runtime Activation Readiness
# ---------------------------------------------------------------------------


def validate_runtime_activation_readiness(review: dict[str, Any]) -> dict[str, Any]:
    """
    Validate that no prohibited actions were executed during this review.
    """
    actions_record = get_actions_record()
    issues = []
    warnings = []

    # Check actions record
    if actions_record:
        issues.append(f"Actions executed during review: {actions_record}")

    surfaces = review.get("surfaces", [])
    blockers = review.get("blockers", [])

    # Check high-risk surfaces are not approved for activation
    high_risk_approved = [
        s["surface_id"] for s in surfaces
        if s.get("risk_level") in ("high", "critical", "unknown")
        and s.get("decision") in ("approve_activation_design", "approve_guarded_dryrun")
    ]
    if high_risk_approved:
        issues.append(f"High-risk surfaces approved for activation: {high_risk_approved}")

    # Check blocked surfaces remain blocked
    blocked_mutation = [
        s["surface_id"] for s in surfaces
        if s.get("domain") in (
            "memory", "asset", "prompt", "tool_runtime",
            "gateway", "mode_router", "rtcm", "scheduler", "auto_fix"
        )
        and s.get("activation_status") != "blocked"
    ]
    if blocked_mutation:
        issues.append(f"Runtime mutation surfaces not blocked: {blocked_mutation}")

    # Check manual surfaces require confirmation
    manual_surfaces = [s for s in surfaces if s.get("activation_status") == "manual_only"]
    missing_confirmation = [
        s["surface_id"] for s in manual_surfaces
        if not s.get("requires_user_confirmation")
    ]
    if missing_confirmation:
        warnings.append(f"Manual-only surfaces missing user_confirmation flag: {missing_confirmation}")

    # Check guarded dryrun surfaces have dryrun flag
    guarded = [s for s in surfaces if s.get("activation_status") == "ready_for_guarded_dryrun_activation"]
    missing_dryrun = [s["surface_id"] for s in guarded if not s.get("requires_dryrun")]
    if missing_dryrun:
        warnings.append(f"Guarded dryrun surfaces missing requires_dryrun: {missing_dryrun}")

    # Check upstream adapter has blockers
    adapter_blockers = [b for b in blockers if "upstream_adapter" in b.get("blocker_type", "")]
    if not adapter_blockers:
        warnings.append("No blockers defined for upstream adapter patch surfaces")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "prohibited_actions_check": "pass" if not actions_record else "fail",
        "high_risk_activation_check": "pass" if not high_risk_approved else "fail",
        "blocked_surface_check": "pass" if not blocked_mutation else "fail",
    }


# ---------------------------------------------------------------------------
# 7. Generate Runtime Activation Readiness Report
# ---------------------------------------------------------------------------


def generate_runtime_activation_readiness_report(
    review: dict[str, Any] | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """
    Generate R241-18A report files (JSON + MD).
    """
    if review is None:
        review = {}

    if output_path is None:
        output_path = "backend/migration_reports/foundation_audit"

    os.makedirs(output_path, exist_ok=True)

    json_path = os.path.join(output_path, "R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json")
    md_path = os.path.join(output_path, "R241-18A_RUNTIME_ACTIVATION_READINESS_REVIEW.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(review, f, indent=2, ensure_ascii=False)

    surfaces = review.get("surfaces", [])
    blockers = review.get("blockers", [])
    sequence = review.get("recommended_sequence", [])
    validation = review.get("validation_result", {})

    md_lines = [
        "# R241-18A: Runtime Activation Readiness Review",
        "",
        f"**Generated:** {review.get('generated_at', 'unknown')}",
        f"**Review ID:** {review.get('review_id', 'unknown')}",
        f"**Status:** `{review.get('status', 'unknown')}`",
        f"**Decision:** `{review.get('decision', 'unknown')}`",
        "",
        "## Safety Summary",
        "",
        "| Category | Count |",
        "|---|---|",
        f"| Ready for Activation Design | {sum(1 for s in surfaces if s.get('activation_status') == 'ready_for_runtime_activation_design')} |",
        f"| Guarded Dry-run | {sum(1 for s in surfaces if s.get('activation_status') == 'ready_for_guarded_dryrun_activation')} |",
        f"| Read-only Only | {sum(1 for s in surfaces if s.get('activation_status') == 'read_only_only')} |",
        f"| Append-only Only | {sum(1 for s in surfaces if s.get('activation_status') == 'append_only_only')} |",
        f"| Manual Only | {sum(1 for s in surfaces if s.get('activation_status') == 'manual_only')} |",
        f"| Report Only | {sum(1 for s in surfaces if s.get('activation_status') == 'report_only')} |",
        f"| Blocked | {sum(1 for s in surfaces if s.get('activation_status') == 'blocked')} |",
        "",
        "## Surface Classification Matrix",
        "",
    ]

    for s in surfaces:
        risk_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴", "unknown": "⚪"}.get(
            s.get("risk_level", "unknown"), "⚪"
        )
        status_icon = {
            "ready_for_runtime_activation_design": "✅",
            "ready_for_guarded_dryrun_activation": "🟡",
            "read_only_only": "📋",
            "append_only_only": "📎",
            "manual_only": "🔧",
            "report_only": "📣",
            "blocked": "🚫",
            "unknown": "⚪",
        }.get(s.get("activation_status", ""), "⚪")

        md_lines.append(f"### {s['surface_id']}: {s['name']} {risk_icon} {status_icon}")
        md_lines.append(f"- **Domain:** `{s.get('domain')}`")
        md_lines.append(f"- **Status:** `{s.get('activation_status')}`")
        md_lines.append(f"- **Decision:** `{s.get('decision')}`")
        md_lines.append(f"- **Risk:** `{s.get('risk_level')}`")
        md_lines.append(f"- **Source:** `{s.get('source_stage')}`")
        md_lines.append(f"- **Current:** `{s.get('current_state')}`")
        md_lines.append(f"- **Proposed:** `{s.get('proposed_activation_state')}`")
        if s.get("blocked_reasons"):
            md_lines.append(f"- **Blocked:** {', '.join(s['blocked_reasons'])}")
        if s.get("warnings"):
            md_lines.append(f"- **Warnings:** {', '.join(s['warnings'])}")
        md_lines.append("")

    if blockers:
        md_lines.extend(["## Blockers", ""])
        for b in blockers:
            md_lines.append(f"### {b['blocker_id']}: {b['description']}")
            md_lines.append(f"- **Domain:** `{b.get('domain')}`")
            md_lines.append(f"- **Type:** `{b.get('blocker_type')}`")
            md_lines.append(f"- **Risk:** `{b.get('risk_level')}`")
            md_lines.append(f"- **Affected:** {', '.join(b.get('affected_surfaces', []))}")
            md_lines.append(f"- **Resolution:** {b.get('required_resolution')}")
            md_lines.append(f"- **Deferrable:** {b.get('can_be_deferred')}")
            md_lines.append("")

    if sequence:
        md_lines.extend(["## Recommended Activation Sequence", ""])
        for phase in sequence:
            md_lines.append(f"### {phase['phase_id']}: {phase['phase_name']}")
            md_lines.append(f"{phase['phase_description']}")
            md_lines.append(f"- **Surfaces:** {phase['surface_count']}")
            md_lines.append(f"- **Prohibited:** {', '.join(phase['prohibited_actions'])}")
            md_lines.append(f"- **Required Guards:** {', '.join(phase['required_guards'])}")
            md_lines.append("")

    md_lines.extend([
        "## Prohibited-Action Confirmation",
        "",
        "This review executed **no runtime activation**. The following were NOT executed:",
        "- No scheduler / watchdog enabled",
        "- No auto-fix executed",
        "- No Feishu / Lark webhook push",
        "- No secret / token / webhook read",
        "- No runtime state written",
        "- No memory cleanup",
        "- No asset promotion / elimination",
        "- No prompt replacement",
        "- No DSPy / GEPA activation",
        "- No ToolRuntime enforcement on main path",
        "- No Gateway main run path replacement",
        "- No Mode Router replacement",
        "- No RTCM state mutation",
        "",
    ])

    validation_result = validation.get("valid", False)
    md_lines.append(f"## Validation Result: {'✅ PASS' if validation_result else '❌ FAIL'}")
    if validation.get("issues"):
        md_lines.append("\n**Issues:**")
        for issue in validation.get("issues", []):
            md_lines.append(f"- ❌ {issue}")
    if validation.get("warnings"):
        md_lines.append("\n**Warnings:**")
        for warn in validation.get("warnings", []):
            md_lines.append(f"- ⚠️ {warn}")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return {
        "json_path": json_path,
        "md_path": md_path,
        "review_id": review.get("review_id"),
    }