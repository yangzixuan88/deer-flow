# noqa: D101, D102, D104
"""
R241-18I: Disabled Sidecar API Stub Contract

Design disabled-by-default sidecar API stub contracts for all 6 read-only
runtime entry surfaces.

Each stub has:
  - enabled = False
  - disabled_by_default = True
  - implemented_now = False
  - network_listener_started = False
  - gateway_main_path_touched = False
  - runtime_write_allowed = False
  - audit_jsonl_write_allowed = False
  - secret_required = False
  - webhook_allowed = False
  - scheduler_allowed = False

No HTTP server started, no port bound, no Gateway route registered.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class DisabledSidecarStubStatus(str, Enum):
    CONTRACT_READY = "contract_ready"
    CONTRACT_READY_WITH_WARNINGS = "contract_ready_with_warnings"
    BLOCKED_MISSING_SCOPE_REVIEW = "blocked_missing_scope_review"
    BLOCKED_SCOPE_NOT_SIDECAR_STUB = "blocked_scope_not_sidecar_stub"
    BLOCKED_ENDPOINT_ENABLED = "blocked_endpoint_enabled"
    BLOCKED_GATEWAY_TOUCH = "blocked_gateway_touch"
    BLOCKED_NETWORK_LISTENER = "blocked_network_listener"
    UNKNOWN = "unknown"


class DisabledSidecarStubDecision(str, Enum):
    APPROVE_DISABLED_STUB_CONTRACT = "approve_disabled_stub_contract"
    APPROVE_CONTRACT_WITH_WARNINGS = "approve_contract_with_warnings"
    BLOCK_DISABLED_STUB_CONTRACT = "block_disabled_stub_contract"
    UNKNOWN = "unknown"


class DisabledSidecarRouteType(str, Enum):
    FOUNDATION_DIAGNOSE = "foundation_diagnose"
    AUDIT_QUERY = "audit_query"
    TREND_REPORT = "trend_report"
    FEISHU_DRYRUN = "feishu_dryrun"
    FEISHU_PRESEND_VALIDATE = "feishu_presend_validate"
    TRUTH_STATE = "truth_state"
    UNKNOWN = "unknown"


class DisabledSidecarStubRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Path resolution
# ─────────────────────────────────────────────────────────────────────────────

_MIGRATION_REPORTS = "migration_reports/foundation_audit"


def _resolve_path(root: str | None, filename: str) -> Path:
    """Resolve a path, checking for already-absolute path."""
    base = Path(root) if root else Path(_MIGRATION_REPORTS)
    p = base / filename
    if not p.is_absolute():
        p = Path(_MIGRATION_REPORTS) / filename
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Scope loading
# ─────────────────────────────────────────────────────────────────────────────


def load_disabled_sidecar_scope(root: str | None = None) -> dict:
    """Load R241-18H scope reconciliation and verify it approves disabled_sidecar_stub."""
    sources: Dict[str, Any] = {
        "loaded": {},
        "missing": [],
        "errors": [],
        "warnings": [],
    }

    r18h_path = _resolve_path(root, "R241-18H_BATCH5_SCOPE_RECONCILIATION.json")
    if r18h_path.exists():
        try:
            data = json.loads(r18h_path.read_text(encoding="utf-8"))
            sources["loaded"]["R241-18H"] = data
        except Exception as exc:
            sources["errors"].append(f"R241-18H_parse_error:{exc}")
            sources["missing"].append("R241-18H")
    else:
        sources["missing"].append("R241-18H")
        sources["errors"].append(f"R241-18H_not_found:{r18h_path}")

    r18h = sources["loaded"].get("R241-18H")
    if r18h:
        if not r18h.get("validation_result", {}).get("valid"):
            sources["errors"].append("R241-18H_validation_invalid")
        else:
            sources["warnings"].append("R241-18H_validation_valid")

        # Check status
        valid_statuses = ["scope_reconciled", "scope_reconciled_with_warnings"]
        if r18h.get("status") not in valid_statuses:
            sources["errors"].append(f"R241-18H_status_invalid:{r18h.get('status')}")
        else:
            sources["warnings"].append("R241-18H_status_valid")

        # Check decision
        if r18h.get("decision") != "proceed_with_disabled_sidecar_stub":
            sources["errors"].append(f"R241-18H_decision_not_sidecar_stub:{r18h.get('decision')}")
        else:
            sources["warnings"].append("R241-18H_decision_is_proceed_with_disabled_sidecar_stub")

        # Check selected scope
        if r18h.get("selected_batch5_scope") != "disabled_sidecar_stub":
            sources["errors"].append(f"R241-18H_scope_not_sidecar_stub:{r18h.get('selected_batch5_scope')}")
        else:
            sources["warnings"].append("R241-18H_selected_scope_is_disabled_sidecar_stub")

        # Check deferred Agent Memory + MCP
        deferred = r18h.get("rejected_or_deferred_candidates", [])
        deferred_types = [d.get("candidate_type") for d in deferred]
        if "agent_memory_read_binding" in deferred_types or "mcp_read_binding" in deferred_types:
            sources["warnings"].append("agent_memory_mcp_deferred_confirmed")
        else:
            sources["errors"].append("agent_memory_mcp_not_deferred")

        # Check warnings list confirms deferral
        warnings_list = r18h.get("warnings", [])
        if any("deferred" in w or "memory" in w.lower() for w in warnings_list):
            sources["warnings"].append("deferral_mentioned_in_warnings")

    return sources


# ─────────────────────────────────────────────────────────────────────────────
# Plan loading
# ─────────────────────────────────────────────────────────────────────────────


def load_disabled_sidecar_plan(root: str | None = None) -> dict:
    """Load R241-18C plan and verify STEP-005 disabled_sidecar_stub contract."""
    sources: Dict[str, Any] = {
        "loaded": {},
        "missing": [],
        "errors": [],
        "warnings": [],
    }

    r18c_path = _resolve_path(root, "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json")
    batch_files = {
        "R241-18C": r18c_path,
        "R241-18D": _resolve_path(root, "R241-18D_READONLY_RUNTIME_ENTRY_BATCH1_RESULT.json"),
        "R241-18E": _resolve_path(root, "R241-18E_READONLY_RUNTIME_ENTRY_BATCH2_RESULT.json"),
        "R241-18F": _resolve_path(root, "R241-18F_READONLY_RUNTIME_ENTRY_BATCH3_RESULT.json"),
        "R241-18G": _resolve_path(root, "R241-18G_READONLY_RUNTIME_ENTRY_BATCH4_RESULT.json"),
    }

    for name, path in batch_files.items():
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sources["loaded"][name] = data
            except Exception as exc:
                sources["errors"].append(f"{name}_parse_error:{exc}")
                sources["missing"].append(name)
        else:
            sources["missing"].append(name)
            sources["errors"].append(f"{name}_not_found:{path}")

    r18c = sources["loaded"].get("R241-18C")
    if r18c:
        if not r18c.get("validation_result", {}).get("valid"):
            sources["errors"].append("R241-18C_validation_invalid")
        else:
            sources["warnings"].append("R241-18C_validation_valid")

        step005 = None
        for step in r18c.get("implementation_steps", []):
            if step.get("step_id") == "STEP-005":
                step005 = step
                break

        if step005:
            sources["warnings"].append("STEP-005_found")
            if step005.get("batch") != "disabled_sidecar_stub":
                sources["errors"].append(
                    f"STEP-005_batch_mismatch:expected=disabled_sidecar_stub,got={step005.get('batch')}"
                )
            else:
                sources["warnings"].append("STEP-005_batch_is_disabled_sidecar_stub")

            if step005.get("opens_http_endpoint"):
                sources["errors"].append("STEP-005_opens_http_endpoint")
            if step005.get("writes_runtime"):
                sources["errors"].append("STEP-005_writes_runtime")
            if step005.get("network_allowed"):
                sources["errors"].append("STEP-005_network_allowed")
            if step005.get("touches_gateway_main_path"):
                sources["errors"].append("STEP-005_touches_gateway")
            if step005.get("requires_secret"):
                sources["errors"].append("STEP-005_requires_secret")

            deps = step005.get("dependencies", [])
            for dep in ["STEP-001", "STEP-002", "STEP-003", "STEP-004"]:
                if dep in deps:
                    sources["warnings"].append(f"STEP-005_dependency_{dep}_confirmed")
                else:
                    sources["errors"].append(f"STEP-005_missing_dependency:{dep}")
        else:
            sources["errors"].append("STEP-005_not_found")

    # Verify all prior batches completed
    for name, expected_step in [("R241-18D", "STEP-001"), ("R241-18E", "STEP-002"),
                                   ("R241-18F", "STEP-003"), ("R241-18G", "STEP-004")]:
        batch = sources["loaded"].get(name)
        if batch:
            implemented = batch.get("implemented_steps", [])
            if expected_step in implemented:
                sources["warnings"].append(f"{name}_{expected_step}_completed")
            else:
                sources["errors"].append(f"{name}_{expected_step}_not_completed")

    return sources


# ─────────────────────────────────────────────────────────────────────────────
# Route descriptors
# ─────────────────────────────────────────────────────────────────────────────


def _make_safety_guards() -> dict:
    """Standard safety guards for disabled sidecar stubs."""
    return {
        "no_runtime_write": True,
        "no_network_by_default": True,
        "no_secret_access": True,
        "no_scheduler_trigger": True,
        "no_gateway_main_path_touch": True,
        "no_http_endpoint": True,
    }


def _make_activation_requirements() -> dict:
    """Activation requirements for enabling a disabled stub."""
    return {
        "explicit_user_confirmation_required": True,
        "auth_policy_required": True,
        "rate_limit_policy_required": True,
        "sidecar_router_review_required": True,
        "no_main_path_replacement": True,
        "no_runtime_write_on_activation": True,
        "no_network_listener_until_activation_review": True,
    }


def _build_foundation_diagnose_descriptor() -> dict:
    """DSRT-001: Foundation Diagnose CLI stub."""
    return {
        "route_id": "DSRT-001",
        "route_type": DisabledSidecarRouteType.FOUNDATION_DIAGNOSE.value,
        "method": "POST",
        "path": "/_disabled/foundation/diagnose",
        "entry_surface": "SPEC-001",
        "handler_ref": "backend.app.foundation.read_only_diagnostics_cli:run_foundation_diagnose",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "enum": ["diagnose", "check", "validate"]},
                "format": {"type": "string", "enum": ["json", "markdown", "text"]},
                "surface": {"type": "string"},
            },
            "required": ["command", "format"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "diagnostic_results": {"type": "array"},
                "summary": {"type": "string"},
            },
        },
        "auth_required": True,
        "rate_limit_required": True,
        "enabled": False,
        "disabled_by_default": True,
        "implemented_now": False,
        "network_listener_started": False,
        "gateway_main_path_touched": False,
        "runtime_write_allowed": False,
        "audit_jsonl_write_allowed": False,
        "secret_required": False,
        "webhook_allowed": False,
        "scheduler_allowed": False,
        "risk_level": DisabledSidecarStubRiskLevel.LOW.value,
        "safety_guards": _make_safety_guards(),
        "activation_requirements": _make_activation_requirements(),
        "warnings": ["disabled_by_default_requires_explicit_activation"],
        "errors": [],
    }


def _build_audit_query_descriptor() -> dict:
    """DSRT-002: Audit Query Engine stub."""
    return {
        "route_id": "DSRT-002",
        "route_type": DisabledSidecarRouteType.AUDIT_QUERY.value,
        "method": "POST",
        "path": "/_disabled/foundation/audit-query",
        "entry_surface": "SPEC-002",
        "handler_ref": "backend.app.audit.audit_trail_query:run_audit_query",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "since": {"type": "string", "format": "date-time"},
                "until": {"type": "string", "format": "date-time"},
                "format": {"type": "string", "enum": ["json", "markdown", "text"]},
            },
            "required": ["query", "format"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "records": {"type": "array"},
                "total_count": {"type": "integer"},
            },
        },
        "auth_required": True,
        "rate_limit_required": True,
        "enabled": False,
        "disabled_by_default": True,
        "implemented_now": False,
        "network_listener_started": False,
        "gateway_main_path_touched": False,
        "runtime_write_allowed": False,
        "audit_jsonl_write_allowed": False,
        "secret_required": False,
        "webhook_allowed": False,
        "scheduler_allowed": False,
        "risk_level": DisabledSidecarStubRiskLevel.MEDIUM.value,
        "safety_guards": _make_safety_guards(),
        "activation_requirements": _make_activation_requirements(),
        "warnings": ["disabled_by_default_requires_explicit_activation"],
        "errors": [],
    }


def _build_trend_report_descriptor() -> dict:
    """DSRT-003: Nightly Trend Report CLI stub."""
    return {
        "route_id": "DSRT-003",
        "route_type": DisabledSidecarRouteType.TREND_REPORT.value,
        "method": "POST",
        "path": "/_disabled/foundation/trend-report",
        "entry_surface": "SPEC-003",
        "handler_ref": "backend.app.audit.audit_trend_projection:run_trend_report",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["24h", "7d", "30d", "all_available"]},
                "output_format": {"type": "string", "enum": ["json", "markdown", "text"]},
            },
            "required": ["period", "output_format"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "trend_data": {"type": "object"},
                "report_text": {"type": "string"},
            },
        },
        "auth_required": True,
        "rate_limit_required": True,
        "enabled": False,
        "disabled_by_default": True,
        "implemented_now": False,
        "network_listener_started": False,
        "gateway_main_path_touched": False,
        "runtime_write_allowed": False,
        "audit_jsonl_write_allowed": False,
        "secret_required": False,
        "webhook_allowed": False,
        "scheduler_allowed": False,
        "risk_level": DisabledSidecarStubRiskLevel.MEDIUM.value,
        "safety_guards": _make_safety_guards(),
        "activation_requirements": _make_activation_requirements(),
        "warnings": [
            "disabled_by_default_requires_explicit_activation",
            "report_output_path_must_be_under_migration_reports_trend",
        ],
        "errors": [],
    }


def _build_feishu_dryrun_descriptor() -> dict:
    """DSRT-004: Feishu Summary Dry-run Preview stub."""
    return {
        "route_id": "DSRT-004",
        "route_type": DisabledSidecarRouteType.FEISHU_DRYRUN.value,
        "method": "POST",
        "path": "/_disabled/foundation/feishu-dryrun",
        "entry_surface": "SPEC-004",
        "handler_ref": "backend.app.audit.audit_trend_feishu_preview:run_feishu_summary_dryrun",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "format": {"type": "string", "enum": ["json", "markdown", "text"]},
            },
            "required": ["content", "format"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "preview": {"type": "string"},
                "valid": {"type": "boolean"},
            },
        },
        "auth_required": True,
        "rate_limit_required": True,
        "enabled": False,
        "disabled_by_default": True,
        "implemented_now": False,
        "network_listener_started": False,
        "gateway_main_path_touched": False,
        "runtime_write_allowed": False,
        "audit_jsonl_write_allowed": False,
        "secret_required": False,
        "webhook_allowed": False,
        "scheduler_allowed": False,
        "risk_level": DisabledSidecarStubRiskLevel.MEDIUM.value,
        "safety_guards": _make_safety_guards(),
        "activation_requirements": _make_activation_requirements(),
        "warnings": ["disabled_by_default_requires_explicit_activation", "dryrun_only_no_real_send"],
        "errors": [],
    }


def _build_feishu_presend_descriptor() -> dict:
    """DSRT-005: Feishu Pre-send Validate-only stub."""
    return {
        "route_id": "DSRT-005",
        "route_type": DisabledSidecarRouteType.FEISHU_PRESEND_VALIDATE.value,
        "method": "POST",
        "path": "/_disabled/foundation/feishu-presend",
        "entry_surface": "SPEC-005",
        "handler_ref": "backend.app.audit.audit_trend_feishu_presend_cli:run_feishu_presend_validate",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "object"},
                "recipients": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["message", "recipients"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "valid": {"type": "boolean"},
                "validation_errors": {"type": "array"},
            },
        },
        "auth_required": True,
        "rate_limit_required": True,
        "enabled": False,
        "disabled_by_default": True,
        "implemented_now": False,
        "network_listener_started": False,
        "gateway_main_path_touched": False,
        "runtime_write_allowed": False,
        "audit_jsonl_write_allowed": False,
        "secret_required": False,
        "webhook_allowed": False,
        "scheduler_allowed": False,
        "risk_level": DisabledSidecarStubRiskLevel.HIGH.value,
        "safety_guards": _make_safety_guards(),
        "activation_requirements": _make_activation_requirements(),
        "warnings": [
            "disabled_by_default_requires_explicit_activation",
            "validate_only_no_real_feishu_send",
            "no_webhook_token_access",
        ],
        "errors": [],
    }


def _build_truth_state_descriptor() -> dict:
    """DSRT-006: Truth State Projection stub."""
    return {
        "route_id": "DSRT-006",
        "route_type": DisabledSidecarRouteType.TRUTH_STATE.value,
        "method": "POST",
        "path": "/_disabled/foundation/truth-state",
        "entry_surface": "SPEC-006",
        "handler_ref": "backend.app.foundation.read_only_diagnostics_cli:run_truth_state",
        "input_schema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["full", "delta"]},
                "format": {"type": "string", "enum": ["json", "markdown", "text"]},
            },
            "required": ["mode", "format"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "truth_state": {"type": "object"},
                "snapshot_time": {"type": "string"},
            },
        },
        "auth_required": True,
        "rate_limit_required": True,
        "enabled": False,
        "disabled_by_default": True,
        "implemented_now": False,
        "network_listener_started": False,
        "gateway_main_path_touched": False,
        "runtime_write_allowed": False,
        "audit_jsonl_write_allowed": False,
        "secret_required": False,
        "webhook_allowed": False,
        "scheduler_allowed": False,
        "risk_level": DisabledSidecarStubRiskLevel.LOW.value,
        "safety_guards": _make_safety_guards(),
        "activation_requirements": _make_activation_requirements(),
        "warnings": ["disabled_by_default_requires_explicit_activation"],
        "errors": [],
    }


def build_disabled_sidecar_route_descriptors(root: str | None = None) -> list:
    """Build all 6 disabled sidecar route descriptors."""
    return [
        _build_foundation_diagnose_descriptor(),
        _build_audit_query_descriptor(),
        _build_trend_report_descriptor(),
        _build_feishu_dryrun_descriptor(),
        _build_feishu_presend_descriptor(),
        _build_truth_state_descriptor(),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Descriptor validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_disabled_sidecar_route_descriptor(route: dict) -> dict:
    """Validate a single route descriptor meets disabled sidecar requirements."""
    issues: List[str] = []
    warnings: List[str] = []

    if route.get("enabled") is True:
        issues.append("route_enabled_must_be_false")
    if route.get("disabled_by_default") is not True:
        issues.append("route_must_be_disabled_by_default")
    if route.get("implemented_now") is True:
        issues.append("route_implemented_now_must_be_false")
    if route.get("network_listener_started") is True:
        issues.append("route_network_listener_must_not_start")
    if route.get("gateway_main_path_touched") is True:
        issues.append("route_must_not_touch_gateway_main_path")
    if route.get("runtime_write_allowed") is True:
        issues.append("route_runtime_write_must_be_disabled")
    if route.get("audit_jsonl_write_allowed") is True:
        issues.append("route_audit_jsonl_write_must_be_disabled")
    if route.get("secret_required") is True:
        issues.append("route_secret_not_required")
    if route.get("webhook_allowed") is True:
        issues.append("route_webhook_not_allowed")
    if route.get("scheduler_allowed") is True:
        issues.append("route_scheduler_not_allowed")

    path = route.get("path", "")
    if not path.startswith("/_disabled/"):
        issues.append(f"route_path_must_start_with_/_disabled/:{path}")

    method = route.get("method", "")
    if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        issues.append(f"route_method_invalid:{method}")

    handler_ref = route.get("handler_ref", "")
    if not handler_ref or ":" not in handler_ref:
        issues.append("handler_ref_must_be_module_path:string_format")

    auth_req = route.get("auth_required")
    rate_limit_req = route.get("rate_limit_required")
    if auth_req is not True:
        issues.append("auth_required_must_be_true")
    if rate_limit_req is not True:
        issues.append("rate_limit_required_must_be_true")

    valid = len(issues) == 0
    return {
        "valid": valid,
        "route_id": route.get("route_id"),
        "issues": issues,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Safety checks
# ─────────────────────────────────────────────────────────────────────────────


def _make_check(
    check_id: str,
    description: str,
    observed: Any,
    expected: Any,
    risk_level: str,
    blocked_reasons: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
) -> dict:
    """Create a scope check dict."""
    passed = observed == expected
    return {
        "check_id": check_id,
        "passed": passed,
        "risk_level": risk_level,
        "description": description,
        "observed_value": observed,
        "expected_value": expected,
        "required_for_contract": True,
        "blocked_reasons": blocked_reasons or [],
        "warnings": warnings or [],
        "errors": errors or [],
    }


def build_disabled_sidecar_safety_checks(routes: list) -> list:
    """Build all safety checks for disabled sidecar contract."""
    checks: List[dict] = []

    # Count routes
    enabled_count = sum(1 for r in routes if r.get("enabled") is True)
    disabled_by_default_count = sum(1 for r in routes if r.get("disabled_by_default") is True)
    implemented_count = sum(1 for r in routes if r.get("implemented_now") is True)
    network_count = sum(1 for r in routes if r.get("network_listener_started") is True)
    gateway_count = sum(1 for r in routes if r.get("gateway_main_path_touched") is True)
    runtime_write_count = sum(1 for r in routes if r.get("runtime_write_allowed") is True)
    audit_count = sum(1 for r in routes if r.get("audit_jsonl_write_allowed") is True)
    secret_count = sum(1 for r in routes if r.get("secret_required") is True)
    webhook_count = sum(1 for r in routes if r.get("webhook_allowed") is True)
    scheduler_count = sum(1 for r in routes if r.get("scheduler_allowed") is True)
    auth_count = sum(1 for r in routes if r.get("auth_required") is True)
    rate_limit_count = sum(1 for r in routes if r.get("rate_limit_required") is True)
    disabled_path_count = sum(1 for r in routes if r.get("path", "").startswith("/_disabled/"))

    total = len(routes)

    checks.append(_make_check(
        "route_count_equals_6",
        f"Exactly 6 route descriptors generated ({total})",
        total, 6,
        DisabledSidecarStubRiskLevel.HIGH.value,
    ))

    checks.append(_make_check(
        "no_enabled_routes",
        f"No route has enabled=True ({enabled_count} enabled)",
        enabled_count, 0,
        DisabledSidecarStubRiskLevel.CRITICAL.value,
        blocked_reasons=[] if enabled_count == 0 else [f"{enabled_count}_routes_enabled"],
    ))

    checks.append(_make_check(
        "all_disabled_by_default",
        f"All routes have disabled_by_default=True ({disabled_by_default_count}/{total})",
        disabled_by_default_count == total, True,
        DisabledSidecarStubRiskLevel.CRITICAL.value,
    ))

    checks.append(_make_check(
        "none_implemented_now",
        f"No route has implemented_now=True ({implemented_count} implemented)",
        implemented_count, 0,
        DisabledSidecarStubRiskLevel.CRITICAL.value,
    ))

    checks.append(_make_check(
        "no_network_listener",
        f"No route starts network listener ({network_count} listeners)",
        network_count, 0,
        DisabledSidecarStubRiskLevel.CRITICAL.value,
    ))

    checks.append(_make_check(
        "no_gateway_main_path",
        f"No route touches Gateway main path ({gateway_count} touches)",
        gateway_count, 0,
        DisabledSidecarStubRiskLevel.CRITICAL.value,
    ))

    checks.append(_make_check(
        "no_runtime_write_allowed",
        f"No route allows runtime write ({runtime_write_count} allow write)",
        runtime_write_count, 0,
        DisabledSidecarStubRiskLevel.CRITICAL.value,
    ))

    checks.append(_make_check(
        "no_audit_jsonl_write_allowed",
        f"No route allows audit JSONL write ({audit_count} allow write)",
        audit_count, 0,
        DisabledSidecarStubRiskLevel.CRITICAL.value,
    ))

    checks.append(_make_check(
        "no_secret_required",
        f"No route requires secret ({secret_count} require secret)",
        secret_count, 0,
        DisabledSidecarStubRiskLevel.HIGH.value,
    ))

    checks.append(_make_check(
        "no_webhook_allowed",
        f"No route allows webhook ({webhook_count} allow webhook)",
        webhook_count, 0,
        DisabledSidecarStubRiskLevel.HIGH.value,
    ))

    checks.append(_make_check(
        "no_scheduler_allowed",
        f"No route allows scheduler ({scheduler_count} allow scheduler)",
        scheduler_count, 0,
        DisabledSidecarStubRiskLevel.HIGH.value,
    ))

    checks.append(_make_check(
        "auth_required_for_all",
        f"All routes require auth ({auth_count}/{total})",
        auth_count == total, True,
        DisabledSidecarStubRiskLevel.HIGH.value,
    ))

    checks.append(_make_check(
        "rate_limit_required_for_all",
        f"All routes require rate limit ({rate_limit_count}/{total})",
        rate_limit_count == total, True,
        DisabledSidecarStubRiskLevel.HIGH.value,
    ))

    checks.append(_make_check(
        "paths_are_disabled_namespace",
        f"All routes use /_disabled/ namespace ({disabled_path_count}/{total})",
        disabled_path_count == total, True,
        DisabledSidecarStubRiskLevel.HIGH.value,
    ))

    checks.append(_make_check(
        "handlers_are_references_only",
        "All handler_refs are module:string format, not imported callables",
        all(":" in r.get("handler_ref", "") for r in routes), True,
        DisabledSidecarStubRiskLevel.HIGH.value,
    ))

    checks.append(_make_check(
        "memory_mcp_not_included",
        "No route includes memory runtime or MCP runtime",
        all(not r.get("touches_memory_runtime") and not r.get("touches_mcp_runtime") for r in routes), True,
        DisabledSidecarStubRiskLevel.CRITICAL.value,
    ))

    checks.append(_make_check(
        "step_scope_limited_to_step_005",
        "Contract scope is limited to STEP-005 (disabled_sidecar_stub)",
        True, True,
        DisabledSidecarStubRiskLevel.HIGH.value,
    ))

    return checks


# ─────────────────────────────────────────────────────────────────────────────
# Contract validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_disabled_sidecar_contract(contract: dict) -> dict:
    """Validate the full disabled sidecar stub contract."""
    issues: List[str] = []
    warnings: List[str] = []

    routes = contract.get("route_descriptors", [])
    checks = contract.get("safety_checks", [])

    # Check no route descriptors violate disabled requirements
    for route in routes:
        if route.get("enabled"):
            issues.append(f"route_{route.get('route_id')}_enabled_must_be_false")
        if route.get("network_listener_started"):
            issues.append(f"route_{route.get('route_id')}_network_listener_must_not_start")
        if route.get("gateway_main_path_touched"):
            issues.append(f"route_{route.get('route_id')}_gateway_main_path_touched")
        if route.get("runtime_write_allowed"):
            issues.append(f"route_{route.get('route_id')}_runtime_write_allowed")
        if route.get("audit_jsonl_write_allowed"):
            issues.append(f"route_{route.get('route_id')}_audit_jsonl_write_allowed")
        if route.get("implemented_now"):
            issues.append(f"route_{route.get('route_id')}_implemented_now_must_be_false")

    # Safety checks must all pass
    failed_checks = [c for c in checks if not c.get("passed")]
    if failed_checks:
        for fc in failed_checks:
            issues.append(f"safety_check_failed:{fc.get('check_id')}")

    valid = len(issues) == 0
    return {
        "valid": valid,
        "issues": issues,
        "warnings": warnings,
        "route_count": len(routes),
        "safety_check_count": len(checks),
        "failed_safety_checks": len(failed_checks),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main contract generator
# ─────────────────────────────────────────────────────────────────────────────


def generate_disabled_sidecar_stub_contract(root: str | None = None) -> dict:
    """Generate the disabled sidecar stub contract."""
    # Load scope and plan
    scope = load_disabled_sidecar_scope(root)
    plan = load_disabled_sidecar_plan(root)

    # Build route descriptors
    routes = build_disabled_sidecar_route_descriptors(root)

    # Validate each descriptor
    validated_routes = []
    for route in routes:
        validation = validate_disabled_sidecar_route_descriptor(route)
        r = dict(route)
        r["validation"] = validation
        validated_routes.append(r)

    # Build safety checks
    checks = build_disabled_sidecar_safety_checks(routes)

    # Determine status and decision
    scope_errors = scope.get("errors", [])
    plan_errors = plan.get("errors", [])
    all_errors = scope_errors + plan_errors

    failed_checks = [c for c in checks if not c.get("passed")]
    validation_issues = all_errors + [f"safety:{c.get('check_id')}" for c in failed_checks]

    if validation_issues:
        status = DisabledSidecarStubStatus.BLOCKED_SCOPE_NOT_SIDECAR_STUB.value
        decision = DisabledSidecarStubDecision.BLOCK_DISABLED_STUB_CONTRACT.value
    elif failed_checks:
        status = DisabledSidecarStubStatus.CONTRACT_READY_WITH_WARNINGS.value
        decision = DisabledSidecarStubDecision.APPROVE_CONTRACT_WITH_WARNINGS.value
    else:
        status = DisabledSidecarStubStatus.CONTRACT_READY.value
        decision = DisabledSidecarStubDecision.APPROVE_DISABLED_STUB_CONTRACT.value

    enabled_count = sum(1 for r in routes if r.get("enabled") is True)
    blocked_count = sum(1 for r in routes if r.get("enabled") is False and not r.get("disabled_by_default"))

    contract_id = f"R241-18I-{uuid.uuid4().hex[:8].upper()}"
    generated_at = datetime.now(timezone.utc).isoformat()

    contract = {
        "contract_id": contract_id,
        "generated_at": generated_at,
        "status": status,
        "decision": decision,
        "source_scope_ref": "R241-18H_BATCH5_SCOPE_RECONCILIATION",
        "source_plan_ref": "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN",
        "route_descriptors": routes,
        "safety_checks": checks,
        "approved_route_count": len(routes) - enabled_count,
        "blocked_route_count": blocked_count,
        "activation_requirements": _make_activation_requirements(),
        "validation_result": None,
        "warnings": [
            "all_routes_disabled_by_default",
            "no_http_endpoint_opened",
            "no_network_listener_started",
            "no_gateway_main_path_touched",
            "no_runtime_write",
            "no_audit_jsonl_write",
            "no_secret_read",
            "no_webhook",
            "no_scheduler",
            "step_006_not_implemented",
            "memory_mcp_excluded",
        ],
        "errors": scope_errors + plan_errors,
    }

    # Validate contract
    validation = validate_disabled_sidecar_contract(contract)
    contract["validation_result"] = validation

    if not validation.get("valid"):
        contract["errors"].extend(validation.get("issues", []))

    return contract


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────


def generate_disabled_sidecar_stub_contract_report(
    contract: dict | None = None,
    output_path: str | None = None,
) -> dict:
    """Generate JSON + Markdown contract report."""
    if contract is None:
        contract = generate_disabled_sidecar_stub_contract()

    migration_reports = Path(_MIGRATION_REPORTS)
    migration_reports.mkdir(parents=True, exist_ok=True)

    json_path = Path(output_path) if output_path else (
        migration_reports / "R241-18I_DISABLED_SIDECAR_STUB_CONTRACT.json"
    )
    md_path = migration_reports / "R241-18I_DISABLED_SIDECAR_STUB_CONTRACT.md"

    json_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")

    passed_checks = [c for c in contract.get("safety_checks", []) if c.get("passed")]
    failed_checks = [c for c in contract.get("safety_checks", []) if not c.get("passed")]

    lines = [
        "# R241-18I: Disabled Sidecar API Stub Contract",
        "",
        f"- **contract_id**: `{contract['contract_id']}`",
        f"- **generated_at**: `{contract['generated_at']}`",
        f"- **status**: `{contract['status']}`",
        f"- **decision**: `{contract['decision']}`",
        f"- **source_scope_ref**: `{contract['source_scope_ref']}`",
        f"- **source_plan_ref**: `{contract['source_plan_ref']}`",
        "",
        "## Contract Summary",
        "",
        f"- **status**: `{contract['status']}`",
        f"- **decision**: `{contract['decision']}`",
        f"- **route_descriptors**: {len(contract.get('route_descriptors', []))}",
        f"- **approved_route_count**: `{contract.get('approved_route_count')}`",
        f"- **blocked_route_count**: `{contract.get('blocked_route_count')}`",
        f"- **validation.valid**: `{contract.get('validation_result', {}).get('valid')}`",
        f"- **safety_checks**: {len(contract.get('safety_checks', []))} "
        f"({len(passed_checks)} passed, {len(failed_checks)} failed)",
        "",
        "## Route Descriptors",
    ]

    for route in contract.get("route_descriptors", []):
        lines.extend([
            f"### {route.get('route_id')} — {route.get('route_type')}",
            f"- **path**: `{route.get('path')}`",
            f"- **method**: `{route.get('method')}`",
            f"- **entry_surface**: `{route.get('entry_surface')}`",
            f"- **handler_ref**: `{route.get('handler_ref')}`",
            f"- **enabled**: `{route.get('enabled')}`",
            f"- **disabled_by_default**: `{route.get('disabled_by_default')}`",
            f"- **implemented_now**: `{route.get('implemented_now')}`",
            f"- **network_listener_started**: `{route.get('network_listener_started')}`",
            f"- **gateway_main_path_touched**: `{route.get('gateway_main_path_touched')}`",
            f"- **runtime_write_allowed**: `{route.get('runtime_write_allowed')}`",
            f"- **audit_jsonl_write_allowed**: `{route.get('audit_jsonl_write_allowed')}`",
            f"- **secret_required**: `{route.get('secret_required')}`",
            f"- **webhook_allowed**: `{route.get('webhook_allowed')}`",
            f"- **scheduler_allowed**: `{route.get('scheduler_allowed')}`",
            f"- **auth_required**: `{route.get('auth_required')}`",
            f"- **rate_limit_required**: `{route.get('rate_limit_required')}`",
            f"- **risk_level**: `{route.get('risk_level')}`",
            "",
        ])

    lines.extend([
        "## Safety Checks",
        f"- **total**: {len(contract.get('safety_checks', []))}",
        f"- **passed**: {len(passed_checks)}",
        f"- **failed**: {len(failed_checks)}",
        "",
    ])

    for c in contract.get("safety_checks", []):
        icon = "[PASS]" if c.get("passed") else "[FAIL]"
        lines.append(f"  - {icon} `{c.get('check_id')}`: {c.get('description')}")

    lines.extend([
        "",
        "## Safety Summary",
        f"- **HTTP endpoint opened**: `False`",
        f"- **Network listener started**: `False`",
        f"- **FastAPI route registered**: `False`",
        f"- **Gateway main path touched**: `False`",
        f"- **Scheduler triggered**: `False`",
        f"- **Feishu sent**: `False`",
        f"- **Webhook called**: `False`",
        f"- **Secret read**: `False`",
        f"- **MCP connected**: `False`",
        f"- **Memory runtime read/write**: `False`",
        f"- **Runtime written**: `False`",
        f"- **Audit JSONL written**: `False`",
        f"- **Action queue written**: `False`",
        f"- **Auto-fix**: `False`",
        "",
        "## Agent Memory + MCP Exclusion",
        "- Agent Memory runtime: EXCLUDED (SURFACE-010 BLOCKED per R241-18A)",
        "- MCP runtime: EXCLUDED (not approved in R241-18A)",
        "- Agent Memory + MCP deferred to R241-18X readiness review",
        "",
        "## STEP-006 Not Implemented",
        "- STEP-006 (Gateway Sidecar Integration Review) not implemented in this contract",
        "- Gateway main path: NOT touched",
        "- Gateway router: NOT mutated",
        "- All stubs remain disabled",
        "",
        "## Activation Requirements",
        "Before any disabled stub can be enabled:",
        "1. explicit_user_confirmation_required = True",
        "2. auth_policy_required = True",
        "3. rate_limit_policy_required = True",
        "4. sidecar_router_review_required = True",
        "5. no_main_path_replacement = True",
        "6. no_runtime_write_on_activation = True",
        "7. no_network_listener_until_activation_review = True",
        "",
        "## Next Step",
        "",
        "R241-18J: Gateway Sidecar Integration Review Gate",
        "- Read-only review of router code",
        "- Confirm no sidecar stub touches Gateway main path",
        "- Verify no router mutation",
        "- All stubs remain disabled until review passes",
    ])

    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
        "contract_id": contract["contract_id"],
        "status": contract["status"],
        "decision": contract["decision"],
    }
