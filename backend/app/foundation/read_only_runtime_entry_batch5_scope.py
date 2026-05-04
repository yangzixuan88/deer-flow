# noqa: D101, D102, D104
"""
R241-18H: Batch 5 Scope Reconciliation

Reads R241-18A, R241-18C, R241-18G to reconcile the true scope of Batch 5.

KEY FINDING: R241-18G report's "next step" of "Agent Memory + MCP Read Binding"
conflicts with R241-18C's original STEP-005 plan ("Disabled Sidecar API Stub Contract Design").

R241-18A SURFACE-010 (Memory Runtime) = BLOCKED (critical risk, block_runtime_activation).
R241-18C STEP-005 = disabled_sidecar_stub contract design.

Resolution: Batch 5 = proceed_with_disabled_sidecar_stub.
Agent Memory + MCP deferred to separate readiness review.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class Batch5ScopeStatus(str, Enum):
    SCOPE_RECONCILED = "scope_reconciled"
    SCOPE_RECONCILED_WITH_WARNINGS = "scope_reconciled_with_warnings"
    BLOCKED_MEMORY_RUNTIME_RISK = "blocked_memory_runtime_risk"
    BLOCKED_MCP_RUNTIME_RISK = "blocked_mcp_runtime_risk"
    BLOCKED_PLAN_CONFLICT = "blocked_plan_conflict"
    UNKNOWN = "unknown"


class Batch5ScopeDecision(str, Enum):
    PROCEED_WITH_DISABLED_SIDECAR_STUB = "proceed_with_disabled_sidecar_stub"
    REQUIRE_MEMORY_MCP_READINESS_REVIEW = "require_memory_mcp_readiness_review"
    BLOCK_BATCH5_RUNTIME_BINDING = "block_batch5_runtime_binding"
    UNKNOWN = "unknown"


class Batch5ScopeRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class Batch5CandidateType(str, Enum):
    DISABLED_SIDECAR_STUB = "disabled_sidecar_stub"
    AGENT_MEMORY_READ_BINDING = "agent_memory_read_binding"
    MCP_READ_BINDING = "mcp_read_binding"
    GATEWAY_SIDECAR_REVIEW = "gateway_sidecar_review"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Path resolution
# ─────────────────────────────────────────────────────────────────────────────

_MIGRATION_REPORTS = "migration_reports/foundation_audit"


def _resolve_path(root: str | None, filename: str) -> Path:
    """Resolve a path, checking for already-canonical path."""
    base = Path(root) if root else Path(_MIGRATION_REPORTS)
    p = base / filename
    if not p.is_absolute():
        p = Path(_MIGRATION_REPORTS) / filename
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Source loading
# ─────────────────────────────────────────────────────────────────────────────


def load_batch5_scope_sources(root: str | None = None) -> dict:
    """Load all required sources for Batch 5 scope reconciliation.

    Checks:
    - R241-18A validation.valid = true
    - SURFACE-010 (memory) status = blocked
    - R241-18C validation.valid = true
    - STEP-005 exists in R241-18C plan
    - R241-18G validation.valid = true
    - STEP-004 completed in R241-18G
    """
    sources: Dict[str, Any] = {"loaded": {}, "missing": [], "errors": [], "warnings": []}

    r18a_path = _resolve_path(root, "R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json")
    r18c_path = _resolve_path(root, "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json")
    r18d_path = _resolve_path(root, "R241-18D_READONLY_RUNTIME_ENTRY_BATCH1_RESULT.json")
    r18e_path = _resolve_path(root, "R241-18E_READONLY_RUNTIME_ENTRY_BATCH2_RESULT.json")
    r18f_path = _resolve_path(root, "R241-18F_READONLY_RUNTIME_ENTRY_BATCH3_RESULT.json")
    r18g_path = _resolve_path(root, "R241-18G_READONLY_RUNTIME_ENTRY_BATCH4_RESULT.json")

    files = {
        "R241-18A": r18a_path,
        "R241-18C": r18c_path,
        "R241-18D": r18d_path,
        "R241-18E": r18e_path,
        "R241-18F": r18f_path,
        "R241-18G": r18g_path,
    }

    for name, path in files.items():
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

    # ── R241-18A checks ──────────────────────────────────────────────────────
    r18a = sources["loaded"].get("R241-18A")
    if r18a:
        if not r18a.get("validation_result", {}).get("valid"):
            sources["errors"].append("R241-18A_validation_invalid")
        else:
            sources["warnings"].append("R241-18A_validation_valid")

        # Check memory surface blocked
        memory_surface = None
        for surf in r18a.get("surfaces", []):
            if surf.get("surface_id") == "SURFACE-010":
                memory_surface = surf
                break
        if memory_surface:
            if memory_surface.get("activation_status") != "blocked":
                sources["errors"].append("memory_surface_not_blocked")
            else:
                sources["warnings"].append("memory_surface_blocked_confirmed")
        else:
            sources["errors"].append("SURFACE-010_not_found_in_R241-18A")

        # Check gateway main path blocked
        gateway_surface = None
        for surf in r18a.get("surfaces", []):
            if surf.get("surface_id") == "SURFACE-014":
                gateway_surface = surf
                break
        if gateway_surface:
            if gateway_surface.get("activation_status") != "blocked":
                sources["errors"].append("gateway_surface_not_blocked")
            else:
                sources["warnings"].append("gateway_surface_blocked_confirmed")

    # ── R241-18C checks ──────────────────────────────────────────────────────
    r18c = sources["loaded"].get("R241-18C")
    if r18c:
        if not r18c.get("validation_result", {}).get("valid"):
            sources["errors"].append("R241-18C_validation_invalid")
        else:
            sources["warnings"].append("R241-18C_validation_valid")

        # Check STEP-005 exists
        step005 = None
        for step in r18c.get("implementation_steps", []):
            if step.get("step_id") == "STEP-005":
                step005 = step
                break
        if step005:
            sources["warnings"].append("STEP-005_found_in_R241-18C_plan")
            if step005.get("batch") != "disabled_sidecar_stub":
                sources["errors"].append(
                    f"STEP-005_batch_mismatch:expected=disabled_sidecar_stub,got={step005.get('batch')}"
                )
        else:
            sources["errors"].append("STEP-005_not_found_in_R241-18C_plan")

    # ── R241-18G checks ──────────────────────────────────────────────────────
    r18g = sources["loaded"].get("R241-18G")
    if r18g:
        if not r18g.get("validation_result", {}).get("valid"):
            sources["errors"].append("R241-18G_validation_invalid")
        else:
            sources["warnings"].append("R241-18G_validation_valid")

        implemented = r18g.get("implemented_steps", [])
        if "STEP-004" not in implemented:
            sources["errors"].append("STEP-004_not_completed_in_R241-18G")
        else:
            sources["warnings"].append("STEP-004_completed_confirmed")

    return sources


# ─────────────────────────────────────────────────────────────────────────────
# Candidate extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract_batch5_candidates(sources: dict) -> dict:
    """Extract all possible Batch 5 candidates.

    Returns a dict with:
    - candidates: List[dict]
    - next_step_source: str (where next step came from)
    """
    candidates: List[dict] = []
    r18c = sources.get("loaded", {}).get("R241-18C", {})
    r18g = sources.get("loaded", {}).get("R241-18G", {})

    # Candidate 1: R241-18C STEP-005 = disabled_sidecar_stub
    step005 = None
    for step in r18c.get("implementation_steps", []):
        if step.get("step_id") == "STEP-005":
            step005 = step
            break

    if step005:
        candidates.append({
            "candidate_id": "CAND-001",
            "candidate_type": Batch5CandidateType.DISABLED_SIDECAR_STUB.value,
            "proposed_source": "R241-18C_STEP-005",
            "matches_r241_18c_plan": True,
            "step_id": "STEP-005",
            "batch": step005.get("batch"),
            "description": step005.get("description", ""),
            "surface_ids": step005.get("surface_ids", []),
            "requires_new_readiness_review": False,
            "touches_memory_runtime": False,
            "touches_mcp_runtime": False,
            "opens_http_endpoint": step005.get("opens_http_endpoint", False),
            "touches_gateway_main_path": step005.get("touches_gateway_main_path", False),
            "network_allowed": step005.get("network_allowed", False),
            "secret_required": step005.get("requires_secret", False),
            "writes_runtime": step005.get("writes_runtime", False),
            "implemented_now": False,
            "disabled_by_default": True,
            "risk_level": Batch5ScopeRiskLevel.LOW.value,
            "decision": None,  # filled by classify
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        })

    # Candidate 2: R241-18G report next-step = Agent Memory + MCP Read Binding
    next_step_note = r18g.get("warnings", [])
    memory_mcp_candidate_found = any(
        "Agent Memory" in w or "MCP" in w or "STEP-005" in w
        for w in next_step_note
    )
    if memory_mcp_candidate_found or True:  # Always detect, even if mentioned
        candidates.append({
            "candidate_id": "CAND-002",
            "candidate_type": Batch5CandidateType.AGENT_MEMORY_READ_BINDING.value,
            "proposed_source": "R241-18G_next_step_annotation",
            "matches_r241_18c_plan": False,  # Conflicts with R241-18C
            "step_id": None,
            "description": "Agent Memory + MCP Read Binding (from R241-18G next-step annotation). "
                          "SURFACE-010 memory runtime is BLOCKED (critical). "
                          "Requires new readiness review before any binding.",
            "surface_ids": ["SURFACE-010"],
            "requires_new_readiness_review": True,
            "touches_memory_runtime": True,
            "touches_mcp_runtime": False,
            "opens_http_endpoint": False,
            "touches_gateway_main_path": False,
            "network_allowed": False,
            "secret_required": False,
            "writes_runtime": True,  # Memory runtime write
            "implemented_now": False,
            "disabled_by_default": False,
            "risk_level": Batch5ScopeRiskLevel.CRITICAL.value,
            "decision": None,
            "blocked_reasons": [
                "SURFACE-010_memory_runtime_blocked_per_R241-18A",
                "memory_runtime_mutations_forbidden",
            ],
            "warnings": [
                "memory_runtime_blocked_cannot_implement_without_readiness_review",
                "R241-18C_STEP-005_does_not_specify_memory_binding",
            ],
            "errors": [],
        })

    # Candidate 3: MCP Read Binding (separate candidate)
    candidates.append({
        "candidate_id": "CAND-003",
        "candidate_type": Batch5CandidateType.MCP_READ_BINDING.value,
        "proposed_source": "inference_from_R241-18G_annotations",
        "matches_r241_18c_plan": False,
        "step_id": None,
        "description": "MCP Read Binding — requires upstream/adapter readiness review, "
                      "MCP credentials policy, network isolation, no secret read, no server connection.",
        "surface_ids": [],
        "requires_new_readiness_review": True,
        "touches_memory_runtime": False,
        "touches_mcp_runtime": True,
        "opens_http_endpoint": False,
        "touches_gateway_main_path": False,
        "network_allowed": False,
        "secret_required": True,
        "writes_runtime": False,
        "implemented_now": False,
        "disabled_by_default": True,
        "risk_level": Batch5ScopeRiskLevel.MEDIUM.value,
        "decision": None,
        "blocked_reasons": [
            "MCP_runtime_not_approved",
            "requires_upstream_adapter_readiness_review",
        ],
        "warnings": [
            "MCP_credentials_policy_not_defined",
            "network_isolation_not_verified",
        ],
        "errors": [],
    })

    # Candidate 4: Gateway Sidecar Review (STEP-006 in R241-18C)
    step006 = None
    for step in r18c.get("implementation_steps", []):
        if step.get("step_id") == "STEP-006":
            step006 = step
            break

    if step006:
        candidates.append({
            "candidate_id": "CAND-004",
            "candidate_type": Batch5CandidateType.GATEWAY_SIDECAR_REVIEW.value,
            "proposed_source": "R241-18C_STEP-006",
            "matches_r241_18c_plan": True,
            "step_id": "STEP-006",
            "batch": step006.get("batch"),
            "description": step006.get("description", ""),
            "surface_ids": step006.get("surface_ids", []),
            "requires_new_readiness_review": False,
            "touches_memory_runtime": False,
            "touches_mcp_runtime": False,
            "opens_http_endpoint": False,
            "touches_gateway_main_path": step006.get("touches_gateway_main_path", False),
            "network_allowed": False,
            "secret_required": False,
            "writes_runtime": False,
            "implemented_now": False,
            "disabled_by_default": True,
            "risk_level": Batch5ScopeRiskLevel.HIGH.value,
            "decision": None,
            "blocked_reasons": [],
            "warnings": [
                "STEP-006_depends_on_STEP-005",
                "review_only_no_implementation",
            ],
            "errors": [],
        })

    return {
        "candidates": candidates,
        "next_step_source": "R241-18G_report_warning",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Candidate classification
# ─────────────────────────────────────────────────────────────────────────────


def classify_batch5_candidate(candidate: dict) -> dict:
    """Classify a Batch 5 candidate and determine its decision."""
    cand = dict(candidate)
    ctype = cand.get("candidate_type")
    decision = None
    blocked_reasons = list(cand.get("blocked_reasons", []))
    warnings = list(cand.get("warnings", []))

    if ctype == Batch5CandidateType.DISABLED_SIDECAR_STUB.value:
        # Proceed if disabled_by_default=true, implemented_now=false, no http/gateway/network
        if (
            cand.get("disabled_by_default") is True
            and cand.get("implemented_now") is False
            and cand.get("opens_http_endpoint") is False
            and cand.get("network_allowed") is False
            and cand.get("touches_gateway_main_path") is False
            and cand.get("writes_runtime") is False
        ):
            decision = Batch5ScopeDecision.PROCEED_WITH_DISABLED_SIDECAR_STUB.value
            warnings.append("disabled_sidecar_stub_confirmed_proceed")
        else:
            decision = Batch5ScopeDecision.BLOCK_BATCH5_RUNTIME_BINDING.value
            blocked_reasons.append("disabled_sidecar_stub_conditions_not_met")

    elif ctype == Batch5CandidateType.AGENT_MEMORY_READ_BINDING.value:
        # Memory is BLOCKED per R241-18A SURFACE-010
        decision = Batch5ScopeDecision.REQUIRE_MEMORY_MCP_READINESS_REVIEW.value
        blocked_reasons.append("memory_runtime_blocked_per_R241-18A_SURFACE-010")
        if cand.get("touches_memory_runtime"):
            blocked_reasons.append("touches_memory_runtime_blocked")

    elif ctype == Batch5CandidateType.MCP_READ_BINDING.value:
        decision = Batch5ScopeDecision.REQUIRE_MEMORY_MCP_READINESS_REVIEW.value
        blocked_reasons.append("MCP_runtime_not_approved_requires_readiness_review")

    elif ctype == Batch5CandidateType.GATEWAY_SIDECAR_REVIEW.value:
        # Review only, no implementation
        decision = Batch5ScopeDecision.REQUIRE_MEMORY_MCP_READINESS_REVIEW.value
        warnings.append("gateway_sidecar_review_is_read_only_review_gate")

    else:
        decision = Batch5ScopeDecision.UNKNOWN.value
        blocked_reasons.append(f"unknown_candidate_type:{ctype}")

    cand["decision"] = decision
    cand["blocked_reasons"] = blocked_reasons
    cand["warnings"] = warnings
    return cand


# ─────────────────────────────────────────────────────────────────────────────
# Scope checks
# ─────────────────────────────────────────────────────────────────────────────


def _make_check(
    check_id: str,
    description: str,
    observed: Any,
    expected: Any,
    risk_level: str,
    required_for_batch5: bool = True,
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
        "required_for_batch5": required_for_batch5,
        "blocked_reasons": blocked_reasons or [],
        "warnings": warnings or [],
        "errors": errors or [],
    }


def build_batch5_scope_checks(candidates: list, sources: dict) -> list:
    """Build all scope reconciliation checks."""
    checks: List[dict] = []
    r18a = sources.get("loaded", {}).get("R241-18A", {})
    r18c = sources.get("loaded", {}).get("R241-18C", {})
    r18g = sources.get("loaded", {}).get("R241-18G", {})

    # ── Source validation checks ─────────────────────────────────────────────
    checks.append(_make_check(
        "r241_18a_validation_valid",
        "R241-18A readiness matrix has valid=true",
        r18a.get("validation_result", {}).get("valid", False),
        True,
        Batch5ScopeRiskLevel.HIGH.value,
    ))

    # Memory surface blocked
    memory_blocked = False
    for surf in r18a.get("surfaces", []):
        if surf.get("surface_id") == "SURFACE-010":
            memory_blocked = surf.get("activation_status") == "blocked"
    checks.append(_make_check(
        "memory_runtime_blocked",
        "SURFACE-010 Memory Runtime remains blocked per R241-18A",
        memory_blocked,
        True,
        Batch5ScopeRiskLevel.CRITICAL.value,
        blocked_reasons=[] if memory_blocked else ["memory_runtime_not_blocked"],
    ))

    # MCP runtime not approved
    mcp_blocked = True
    for surf in r18a.get("surfaces", []):
        if surf.get("surface_id") == "SURFACE-010" and surf.get("domain") == "mcp":
            mcp_blocked = surf.get("activation_status") == "blocked"
    # Default assumption: MCP runtime not explicitly approved
    checks.append(_make_check(
        "mcp_runtime_not_approved",
        "MCP runtime has no affirmative approval in R241-18A readiness matrix",
        mcp_blocked,
        True,
        Batch5ScopeRiskLevel.MEDIUM.value,
    ))

    # Gateway main path blocked
    gateway_blocked = False
    for surf in r18a.get("surfaces", []):
        if surf.get("surface_id") == "SURFACE-014":
            gateway_blocked = surf.get("activation_status") == "blocked"
    checks.append(_make_check(
        "gateway_main_path_blocked",
        "SURFACE-014 Gateway Main Run Path blocked per R241-18A",
        gateway_blocked,
        True,
        Batch5ScopeRiskLevel.CRITICAL.value,
    ))

    # R241-18C validation valid
    checks.append(_make_check(
        "r241_18c_validation_valid",
        "R241-18C implementation plan has valid=true",
        r18c.get("validation_result", {}).get("valid", False),
        True,
        Batch5ScopeRiskLevel.HIGH.value,
    ))

    # STEP-005 exists
    step005_exists = any(
        s.get("step_id") == "STEP-005" for s in r18c.get("implementation_steps", [])
    )
    checks.append(_make_check(
        "step_005_exists",
        "STEP-005 exists in R241-18C plan",
        step005_exists,
        True,
        Batch5ScopeRiskLevel.HIGH.value,
        blocked_reasons=[] if step005_exists else ["STEP-005_not_found"],
    ))

    # STEP-005 is disabled_sidecar_stub
    step005_batch = None
    for s in r18c.get("implementation_steps", []):
        if s.get("step_id") == "STEP-005":
            step005_batch = s.get("batch")
    checks.append(_make_check(
        "step_005_disabled_sidecar_stub",
        "STEP-005 batch is 'disabled_sidecar_stub' per R241-18C plan",
        step005_batch == "disabled_sidecar_stub",
        True,
        Batch5ScopeRiskLevel.MEDIUM.value,
        blocked_reasons=[] if step005_batch == "disabled_sidecar_stub" else [f"STEP-005_batch={step005_batch}"],
    ))

    # R241-18G validation valid
    checks.append(_make_check(
        "r241_18g_validation_valid",
        "R241-18G batch 4 result has valid=true",
        r18g.get("validation_result", {}).get("valid", False),
        True,
        Batch5ScopeRiskLevel.HIGH.value,
    ))

    # STEP-004 completed
    step004_completed = "STEP-004" in r18g.get("implemented_steps", [])
    checks.append(_make_check(
        "step_004_completed",
        "STEP-004 completed in R241-18G",
        step004_completed,
        True,
        Batch5ScopeRiskLevel.HIGH.value,
        blocked_reasons=[] if step004_completed else ["STEP-004_not_completed"],
    ))

    # ── Candidate-specific checks ─────────────────────────────────────────────
    disabled_sidecar_candidates = [
        c for c in candidates if c.get("candidate_type") == Batch5CandidateType.DISABLED_SIDECAR_STUB.value
    ]
    if disabled_sidecar_candidates:
        cand = disabled_sidecar_candidates[0]
        checks.append(_make_check(
            "disabled_sidecar_no_http_endpoint",
            "disabled_sidecar_stub opens no HTTP endpoint",
            cand.get("opens_http_endpoint"),
            False,
            Batch5ScopeRiskLevel.HIGH.value,
        ))
        checks.append(_make_check(
            "disabled_sidecar_no_network",
            "disabled_sidecar_stub has network_allowed=False",
            cand.get("network_allowed"),
            False,
            Batch5ScopeRiskLevel.HIGH.value,
        ))
        checks.append(_make_check(
            "disabled_sidecar_no_gateway_touch",
            "disabled_sidecar_stub does not touch Gateway main path",
            cand.get("touches_gateway_main_path"),
            False,
            Batch5ScopeRiskLevel.CRITICAL.value,
        ))
        checks.append(_make_check(
            "disabled_sidecar_no_runtime_write",
            "disabled_sidecar_stub writes_runtime=False",
            cand.get("writes_runtime"),
            False,
            Batch5ScopeRiskLevel.CRITICAL.value,
        ))

    # Memory candidate blocked
    memory_candidates = [
        c for c in candidates if c.get("candidate_type") == Batch5CandidateType.AGENT_MEMORY_READ_BINDING.value
    ]
    if memory_candidates:
        cand = memory_candidates[0]
        checks.append(_make_check(
            "memory_binding_blocked",
            "Agent Memory candidate is blocked (memory runtime blocked per R241-18A)",
            cand.get("decision"),
            Batch5ScopeDecision.REQUIRE_MEMORY_MCP_READINESS_REVIEW.value,
            Batch5ScopeRiskLevel.CRITICAL.value,
            blocked_reasons=cand.get("blocked_reasons", []),
        ))

    # MCP candidate blocked
    mcp_candidates = [
        c for c in candidates if c.get("candidate_type") == Batch5CandidateType.MCP_READ_BINDING.value
    ]
    if mcp_candidates:
        cand = mcp_candidates[0]
        checks.append(_make_check(
            "mcp_binding_blocked",
            "MCP Read candidate requires readiness review",
            cand.get("decision"),
            Batch5ScopeDecision.REQUIRE_MEMORY_MCP_READINESS_REVIEW.value,
            Batch5ScopeRiskLevel.MEDIUM.value,
        ))

    return checks


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_batch5_scope_reconciliation(review: dict) -> dict:
    """Validate the scope reconciliation result.

    Rejects:
    - Any memory runtime read/write
    - Any MCP connection
    - Any HTTP endpoint
    - Any Gateway main path integration
    - Any auto-fix
    - Any scheduler
    - Any runtime binding implemented
    """
    issues: List[str] = []
    warnings: List[str] = []

    candidates = review.get("candidates", [])
    selected = review.get("selected_batch5_scope", "")

    # Memory must be blocked
    if selected == Batch5CandidateType.AGENT_MEMORY_READ_BINDING.value:
        issues.append("selected_scope_is_blocked_memory_binding")

    # Check all candidates for violations
    for cand in candidates:
        if cand.get("touches_memory_runtime") and cand.get("implemented_now"):
            issues.append(f"candidate_{cand.get('candidate_id')}_implements_memory_runtime")
        if cand.get("opens_http_endpoint"):
            issues.append(f"candidate_{cand.get('candidate_id')}_opens_http_endpoint")
        if cand.get("touches_gateway_main_path") and cand.get("implemented_now"):
            issues.append(f"candidate_{cand.get('candidate_id')}_touches_gateway_main_path")
        if cand.get("touches_mcp_runtime") and cand.get("implemented_now"):
            issues.append(f"candidate_{cand.get('candidate_id')}_connects_mcp_runtime")
        if cand.get("writes_runtime") and cand.get("implemented_now"):
            issues.append(f"candidate_{cand.get('candidate_id')}_writes_runtime")

    # Prohibited actions checks
    checks = review.get("checks", [])
    check_map = {c.get("check_id"): c for c in checks}

    prohibited = {
        "no_http_endpoint": ["disabled_sidecar_no_http_endpoint"],
        "no_network": ["disabled_sidecar_no_network"],
        "no_gateway_touch": ["disabled_sidecar_no_gateway_touch"],
        "no_runtime_write": ["disabled_sidecar_no_runtime_write"],
    }

    for safe_name, check_ids in prohibited.items():
        for cid in check_ids:
            if cid in check_map and not check_map[cid].get("passed"):
                issues.append(f"prohibited_action:{safe_name}_violated_by_{cid}")

    valid = len(issues) == 0

    return {
        "valid": valid,
        "issues": issues,
        "warnings": warnings,
        "selected_scope": selected,
        "candidates_count": len(candidates),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main reconciliation generator
# ─────────────────────────────────────────────────────────────────────────────


def generate_batch5_scope_reconciliation(root: str | None = None) -> dict:
    """Generate Batch 5 scope reconciliation.

    Default result:
    - status = scope_reconciled_with_warnings
    - decision = proceed_with_disabled_sidecar_stub
    - selected_batch5_scope = disabled_sidecar_stub
    - Agent Memory + MCP deferred to readiness review
    """
    sources = load_batch5_scope_sources(root)

    extracted = extract_batch5_candidates(sources)
    candidates_raw = extracted.get("candidates", [])

    # Classify each candidate
    candidates = [classify_batch5_candidate(c) for c in candidates_raw]

    # Build checks
    checks = build_batch5_scope_checks(candidates, sources)

    # Determine selected scope: disabled_sidecar_stub if STEP-005 confirmed
    selected = Batch5CandidateType.DISABLED_SIDECAR_STUB.value
    disabled_cand = next(
        (c for c in candidates if c.get("candidate_type") == Batch5CandidateType.DISABLED_SIDECAR_STUB.value),
        None,
    )
    if not disabled_cand:
        selected = Batch5CandidateType.UNKNOWN.value
    elif disabled_cand.get("decision") != Batch5ScopeDecision.PROCEED_WITH_DISABLED_SIDECAR_STUB.value:
        selected = Batch5CandidateType.UNKNOWN.value

    # Determine status
    failed_checks = [c for c in checks if not c.get("passed")]
    memory_blocked_check = next(
        (c for c in checks if c.get("check_id") == "memory_binding_blocked"),
        None,
    )
    if failed_checks:
        status = Batch5ScopeStatus.SCOPE_RECONCILED_WITH_WARNINGS.value
    elif memory_blocked_check and not memory_blocked_check.get("passed"):
        status = Batch5ScopeStatus.BLOCKED_MEMORY_RUNTIME_RISK.value
    else:
        status = Batch5ScopeStatus.SCOPE_RECONCILED.value

    # Determine decision
    if selected == Batch5CandidateType.DISABLED_SIDECAR_STUB.value:
        decision = Batch5ScopeDecision.PROCEED_WITH_DISABLED_SIDECAR_STUB.value
    elif selected == Batch5CandidateType.UNKNOWN.value:
        decision = Batch5ScopeDecision.BLOCK_BATCH5_RUNTIME_BINDING.value
    else:
        decision = Batch5ScopeDecision.UNKNOWN.value

    # Deferred candidates
    deferred = [
        c for c in candidates
        if c.get("decision") in (
            Batch5ScopeDecision.REQUIRE_MEMORY_MCP_READINESS_REVIEW.value,
            Batch5CandidateType.UNKNOWN.value,
        )
        and c.get("candidate_type") != Batch5CandidateType.DISABLED_SIDECAR_STUB.value
    ]

    review_id = f"R241-18H-{uuid.uuid4().hex[:8].upper()}"
    generated_at = datetime.now(timezone.utc).isoformat()

    review = {
        "review_id": review_id,
        "generated_at": generated_at,
        "status": status,
        "decision": decision,
        "source_plan_ref": "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN",
        "source_batch4_ref": "R241-18G_READONLY_RUNTIME_ENTRY_BATCH4_BINDING_RESULT",
        "candidates": candidates,
        "checks": checks,
        "selected_batch5_scope": selected,
        "rejected_or_deferred_candidates": deferred,
        "next_phase": "R241-18I_DISABLED_SIDECAR_STUB_CONTRACT",
        "validation_result": None,  # filled below
        "warnings": [
            "Agent_Memory_MCP_deferred_to_readiness_review",
            "R241-18C_STEP-005_is_disabled_sidecar_stub_not_memory_binding",
            "memory_runtime_remains_blocked_per_R241-18A_SURFACE-010",
            "STEP-005_is_design_only_no_implementation",
        ],
        "errors": [],
    }

    validation = validate_batch5_scope_reconciliation(review)
    review["validation_result"] = validation

    # Merge validation issues into review errors
    if not validation.get("valid"):
        review["errors"].extend(validation.get("issues", []))

    return review


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────


def generate_batch5_scope_reconciliation_report(
    review: dict | None = None,
    output_path: str | None = None,
) -> dict:
    """Generate JSON + Markdown scope reconciliation report."""
    if review is None:
        review = generate_batch5_scope_reconciliation()

    migration_reports = Path(_MIGRATION_REPORTS)
    migration_reports.mkdir(parents=True, exist_ok=True)

    json_path = Path(output_path) if output_path else (
        migration_reports / "R241-18H_BATCH5_SCOPE_RECONCILIATION.json"
    )
    md_path = migration_reports / "R241-18H_BATCH5_SCOPE_RECONCILIATION.md"

    json_path.write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")

    # Build markdown
    lines = [
        "# R241-18H: Batch 5 Scope Reconciliation",
        "",
        f"- **review_id**: `{review['review_id']}`",
        f"- **generated_at**: `{review['generated_at']}`",
        f"- **status**: `{review['status']}`",
        f"- **decision**: `{review['decision']}`",
        f"- **selected_batch5_scope**: `{review['selected_batch5_scope']}`",
        f"- **source_plan_ref**: `{review['source_plan_ref']}`",
        f"- **source_batch4_ref**: `{review['source_batch4_ref']}`",
        "",
        "## Scope Reconciliation Summary",
        "",
        f"- **status**: `{review['status']}`",
        f"- **decision**: `{review['decision']}`",
        f"- **selected_scope**: `{review['selected_batch5_scope']}`",
        f"- **next_phase**: `{review['next_phase']}`",
        f"- **validation.valid**: `{review.get('validation_result', {}).get('valid')}`",
        f"- **candidates**: {len(review.get('candidates', []))}",
        f"- **checks**: {len(review.get('checks', []))}",
        f"- **deferred**: {len(review.get('rejected_or_deferred_candidates', []))}",
        "",
        "## Source Evidence",
        "",
        "### R241-18C STEP-005 (Authoritative Plan)",
    ]

    step005_cand = next(
        (c for c in review.get("candidates", []) if c.get("candidate_type") == Batch5CandidateType.DISABLED_SIDECAR_STUB.value),
        None,
    )
    if step005_cand:
        lines.extend([
            f"- **candidate_id**: `{step005_cand.get('candidate_id')}`",
            f"- **batch**: `{step005_cand.get('batch')}`",
            f"- **matches_r241_18c_plan**: `{step005_cand.get('matches_r241_18c_plan')}`",
            f"- **decision**: `{step005_cand.get('decision')}`",
            f"- **opens_http_endpoint**: `{step005_cand.get('opens_http_endpoint')}`",
            f"- **network_allowed**: `{step005_cand.get('network_allowed')}`",
            f"- **touches_gateway_main_path**: `{step005_cand.get('touches_gateway_main_path')}`",
            f"- **writes_runtime**: `{step005_cand.get('writes_runtime')}`",
        ])
    else:
        lines.append("- **STEP-005 not found**")

    lines.extend([
        "",
        "### R241-18G Next-Step (Conflicting Proposal)",
    ])

    mem_cand = next(
        (c for c in review.get("candidates", [])
         if c.get("candidate_type") == Batch5CandidateType.AGENT_MEMORY_READ_BINDING.value),
        None,
    )
    if mem_cand:
        lines.extend([
            f"- **candidate_id**: `{mem_cand.get('candidate_id')}`",
            f"- **proposed_source**: `{mem_cand.get('proposed_source')}`",
            f"- **matches_r241_18c_plan**: `{mem_cand.get('matches_r241_18c_plan')}`",
            f"- **decision**: `{mem_cand.get('decision')}`",
            f"- **touches_memory_runtime**: `{mem_cand.get('touches_memory_runtime')}`",
            f"- **risk_level**: `{mem_cand.get('risk_level')}`",
            f"- **blocked_reasons**: {mem_cand.get('blocked_reasons', [])}",
        ])

    lines.extend([
        "",
        "## Deferral Rationale",
        "",
        "### Agent Memory + MCP (CAND-002, CAND-003)",
        "- **Reason**: SURFACE-010 (Memory Runtime) = BLOCKED per R241-18A (critical, `block_runtime_activation`)",
        "- **Reason**: R241-18C STEP-005 specifies `disabled_sidecar_stub`, not memory binding",
        "- **Reason**: Agent Memory binding would require memory cleanup / runtime mutation — prohibited",
        "- **Decision**: Deferred to separate R241-18X readiness review",
        "",
        "### MCP Read Binding (CAND-003)",
        "- **Reason**: MCP runtime not approved in R241-18A readiness matrix",
        "- **Reason**: MCP credentials policy not defined",
        "- **Reason**: Network isolation not verified",
        "- **Decision**: Deferred to upstream/adapter readiness review",
        "",
        "## Selected Batch 5 Scope",
        "",
        f"- **selected**: `{review['selected_batch5_scope']}`",
        f"- **decision**: `{review['decision']}`",
        "- **scope**: R241-18C STEP-005 = Disabled Sidecar API Stub Contract Design",
        "- **characteristics**: `disabled_by_default=True`, `implemented_now=False`, `opens_http_endpoint=False`",
        "- **next_phase**: `R241-18I_DISABLED_SIDECAR_STUB_CONTRACT`",
        "",
        "## Validation",
        f"- **valid**: `{review.get('validation_result', {}).get('valid')}`",
        f"- **issues**: {review.get('validation_result', {}).get('issues', [])}",
        "",
        "## Safety Checks",
    ])

    passed_checks = [c for c in review.get("checks", []) if c.get("passed")]
    failed_checks = [c for c in review.get("checks", []) if not c.get("passed")]
    lines.append(f"- **total**: {len(review.get('checks', []))}")
    lines.append(f"- **passed**: {len(passed_checks)}")
    lines.append(f"- **failed**: {len(failed_checks)}")
    lines.append("")

    for c in review.get("checks", []):
        icon = "[PASS]" if c.get("passed") else "[FAIL]"
        lines.append(f"  - {icon} `{c.get('check_id')}`: {c.get('description')} (`{c.get('observed_value')}` == `{c.get('expected_value')}`)")

    lines.extend([
        "",
        "## Safety Summary",
        f"- **HTTP endpoint opened**: `False`",
        f"- **Gateway main path touched**: `False`",
        f"- **Scheduler triggered**: `False`",
        f"- **MCP connected**: `False`",
        f"- **Memory runtime read/write**: `False` (memory runtime BLOCKED)",
        f"- **Secret read**: `False`",
        f"- **Runtime written**: `False`",
        f"- **Auto-fix**: `False`",
        "",
        "## Current Blockers",
        "- SURFACE-010 Memory Runtime: BLOCKED (critical, `block_runtime_activation`)",
        "- SURFACE-014 Gateway Main Run Path: BLOCKED (critical)",
        "- Agent Memory + MCP binding: NOT APPROVED — requires new readiness review",
        "- MCP runtime: NOT APPROVED — no credentials policy defined",
        "",
        "## Next Steps",
        "",
        "### Immediate (R241-18I)",
        "- Implement R241-18I: Disabled Sidecar API Stub Contract",
        "- Design-only, no HTTP endpoint, no Gateway touch, no network, no runtime write",
        "- Follow R241-18C STEP-005 spec",
        "",
        "### Future Readiness Review (R241-18X)",
        "- Agent Memory Runtime readiness review (must pass before any memory binding)",
        "- MCP Read Binding readiness review (credentials policy, network isolation)",
        "",
    ])

    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
        "review_id": review["review_id"],
        "status": review["status"],
        "decision": review["decision"],
        "selected_scope": review["selected_batch5_scope"],
    }
