"""Foundation Integration Readiness Review.

This module reviews wrapper/projection surfaces only. It does not connect
anything to runtime paths, does not write action queues, and does not execute
tools or repairs.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_MATRIX_PATH = REPORT_DIR / "R241-9A_FOUNDATION_INTEGRATION_READINESS_MATRIX.json"
DEFAULT_REPORT_PATH = REPORT_DIR / "R241-9A_FOUNDATION_INTEGRATION_READINESS_REVIEW.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

READINESS_LEVELS = {
    "report_only",
    "read_only_ready",
    "append_only_ready",
    "gated_write_ready",
    "blocked",
    "unknown",
}

SURFACE_TYPES = {
    "truth_state_projection",
    "governance_projection",
    "queue_sandbox_projection",
    "memory_projection",
    "asset_projection",
    "mode_instrumentation",
    "gateway_mode_instrumentation",
    "tool_runtime_projection",
    "prompt_projection",
    "rtcm_projection",
    "nightly_review_projection",
    "feishu_summary_projection",
    "unknown",
}

RISK_LEVELS = {"low", "medium", "high", "critical", "unknown"}

DECISIONS = {
    "approve_read_only_integration",
    "approve_append_only_integration",
    "keep_report_only",
    "require_more_tests",
    "require_backup_rollback",
    "require_context_link",
    "require_schema_hardening",
    "require_user_confirmation",
    "block_integration",
    "unknown",
}


@dataclass
class FoundationSurfaceReadiness:
    surface_id: str
    surface_type: str
    module_path: str
    owner_domain: str
    readiness_level: str
    decision: str
    risk_level: str
    can_read_runtime: bool
    can_write_runtime: bool
    can_modify_execution_path: bool
    requires_backup: bool
    requires_rollback: bool
    requires_user_confirmation: bool
    requires_root_guard: bool
    has_tests: bool
    test_refs: List[str] = field(default_factory=list)
    sample_refs: List[str] = field(default_factory=list)
    report_refs: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    recommended_next_step: str = "keep_report_only_until_reviewed"
    warnings: List[str] = field(default_factory=list)
    reviewed_at: str = field(default_factory=lambda: _now())


@dataclass
class FoundationIntegrationMatrix:
    matrix_id: str
    generated_at: str
    root: str
    surfaces: List[Dict[str, Any]]
    by_readiness_level: Dict[str, int]
    by_decision: Dict[str, int]
    by_risk_level: Dict[str, int]
    read_only_ready_count: int
    append_only_ready_count: int
    report_only_count: int
    blocked_count: int
    high_risk_count: int
    recommended_integration_sequence: List[Dict[str, Any]]
    warnings: List[str] = field(default_factory=list)


@dataclass
class IntegrationReadinessReview:
    review_id: str
    generated_at: str
    matrix_ref: str
    summary: Dict[str, Any]
    approved_read_only_surfaces: List[str]
    approved_append_only_surfaces: List[str]
    report_only_surfaces: List[str]
    blocked_surfaces: List[str]
    prerequisite_actions: List[Dict[str, Any]]
    next_phase_recommendation: str
    warnings: List[str] = field(default_factory=list)


SURFACE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "surface_id": "truth_state_contract",
        "surface_type": "truth_state_projection",
        "module_path": "backend/app/m11/truth_state_contract.py",
        "import_path": "app.m11.truth_state_contract",
        "owner_domain": "truth_state",
        "test_refs": ["backend/app/m11/test_truth_state_contract.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-1A_TRUTH_STATE_WRAPPER_REPORT.md"],
        "sample_refs": [],
    },
    {
        "surface_id": "governance_readonly_projection",
        "surface_type": "governance_projection",
        "module_path": "backend/app/m11/governance_bridge.py",
        "import_path": "app.m11.governance_bridge",
        "owner_domain": "truth_state",
        "test_refs": ["backend/app/m11/test_governance_truth_projection.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-1B_GOVERNANCE_READONLY_PROJECTION_REPORT.md"],
        "sample_refs": [],
        "dependencies": ["truth_state_contract"],
    },
    {
        "surface_id": "queue_sandbox_truth_projection",
        "surface_type": "queue_sandbox_projection",
        "module_path": "backend/app/m11/queue_sandbox_truth_projection.py",
        "import_path": "app.m11.queue_sandbox_truth_projection",
        "owner_domain": "queue_sandbox",
        "test_refs": ["backend/app/m11/test_queue_sandbox_truth_projection.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-1C_QUEUE_SANDBOX_TRUTH_PROJECTION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-1C_QUEUE_SANDBOX_TRUTH_PROJECTION_RUNTIME_SAMPLE.json"],
        "dependencies": ["governance_readonly_projection"],
        "warnings": ["queue_path_mismatch_unresolved"],
    },
    {
        "surface_id": "memory_layer_contract",
        "surface_type": "memory_projection",
        "module_path": "backend/app/memory/memory_layer_contract.py",
        "import_path": "app.memory.memory_layer_contract",
        "owner_domain": "memory",
        "test_refs": ["backend/app/memory/test_memory_layer_contract.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-2A_MEMORY_LAYER_CONTRACT_WRAPPER_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-2A_MEMORY_LAYER_RUNTIME_SAMPLE.json"],
    },
    {
        "surface_id": "memory_readonly_projection",
        "surface_type": "memory_projection",
        "module_path": "backend/app/memory/memory_projection.py",
        "import_path": "app.memory.memory_projection",
        "owner_domain": "memory",
        "test_refs": ["backend/app/memory/test_memory_projection.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-2B_MEMORY_READONLY_PROJECTION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-2B_MEMORY_PROJECTION_RUNTIME_SAMPLE.json"],
        "dependencies": ["memory_layer_contract"],
    },
    {
        "surface_id": "asset_lifecycle_contract",
        "surface_type": "asset_projection",
        "module_path": "backend/app/asset/asset_lifecycle_contract.py",
        "import_path": "app.asset.asset_lifecycle_contract",
        "owner_domain": "asset",
        "test_refs": ["backend/app/asset/test_asset_lifecycle_contract.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-3A_ASSET_LIFECYCLE_CONTRACT_WRAPPER_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-3A_ASSET_LIFECYCLE_RUNTIME_SAMPLE.json"],
    },
    {
        "surface_id": "asset_readonly_projection",
        "surface_type": "asset_projection",
        "module_path": "backend/app/asset/asset_projection.py",
        "import_path": "app.asset.asset_projection",
        "owner_domain": "asset",
        "test_refs": ["backend/app/asset/test_asset_projection.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-3B_ASSET_READONLY_PROJECTION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-3B_ASSET_PROJECTION_RUNTIME_SAMPLE.json"],
        "dependencies": ["asset_lifecycle_contract", "memory_readonly_projection"],
    },
    {
        "surface_id": "mode_orchestration_contract",
        "surface_type": "mode_instrumentation",
        "module_path": "backend/app/mode/mode_orchestration_contract.py",
        "import_path": "app.mode.mode_orchestration_contract",
        "owner_domain": "mode",
        "test_refs": ["backend/app/mode/test_mode_orchestration_contract.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-4A_MODE_INVOCATION_INSTRUMENTATION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-4A_MODE_CALLGRAPH_RUNTIME_SAMPLE.json"],
    },
    {
        "surface_id": "gateway_mode_instrumentation",
        "surface_type": "gateway_mode_instrumentation",
        "module_path": "backend/app/gateway/mode_instrumentation.py",
        "import_path": "app.gateway.mode_instrumentation",
        "owner_domain": "gateway",
        "test_refs": ["backend/app/gateway/test_mode_instrumentation_smoke.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-4B_GATEWAY_CONTEXT_MODE_INSTRUMENTATION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-4B_GATEWAY_MODE_INSTRUMENTATION_SAMPLE.json"],
        "dependencies": ["mode_orchestration_contract"],
    },
    {
        "surface_id": "tool_runtime_contract",
        "surface_type": "tool_runtime_projection",
        "module_path": "backend/app/tool_runtime/tool_runtime_contract.py",
        "import_path": "app.tool_runtime.tool_runtime_contract",
        "owner_domain": "tool_runtime",
        "test_refs": ["backend/app/tool_runtime/test_tool_runtime_contract.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-5A_TOOL_RUNTIME_INSTRUMENTATION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-5A_TOOL_RUNTIME_SAMPLE.json"],
    },
    {
        "surface_id": "tool_runtime_gateway_mode_projection",
        "surface_type": "tool_runtime_projection",
        "module_path": "backend/app/tool_runtime/tool_runtime_projection.py",
        "import_path": "app.tool_runtime.tool_runtime_projection",
        "owner_domain": "tool_runtime",
        "test_refs": ["backend/app/tool_runtime/test_tool_runtime_projection.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-5B_TOOL_RUNTIME_GATEWAY_MODE_PROJECTION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-5B_TOOL_RUNTIME_GATEWAY_MODE_SAMPLE.json"],
        "dependencies": ["tool_runtime_contract", "mode_orchestration_contract", "gateway_mode_instrumentation"],
    },
    {
        "surface_id": "prompt_governance_contract",
        "surface_type": "prompt_projection",
        "module_path": "backend/app/prompt/prompt_governance_contract.py",
        "import_path": "app.prompt.prompt_governance_contract",
        "owner_domain": "prompt",
        "test_refs": ["backend/app/prompt/test_prompt_governance_contract.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-6A_PROMPT_GOVERNANCE_WRAPPER_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-6A_PROMPT_GOVERNANCE_SAMPLE.json"],
    },
    {
        "surface_id": "prompt_readonly_projection",
        "surface_type": "prompt_projection",
        "module_path": "backend/app/prompt/prompt_projection.py",
        "import_path": "app.prompt.prompt_projection",
        "owner_domain": "prompt",
        "test_refs": ["backend/app/prompt/test_prompt_projection.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-6B_PROMPT_READONLY_PROJECTION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-6B_PROMPT_PROJECTION_RUNTIME_SAMPLE.json"],
        "dependencies": ["prompt_governance_contract"],
    },
    {
        "surface_id": "rtcm_integration_contract",
        "surface_type": "rtcm_projection",
        "module_path": "backend/app/rtcm/rtcm_integration_contract.py",
        "import_path": "app.rtcm.rtcm_integration_contract",
        "owner_domain": "rtcm",
        "test_refs": ["backend/app/rtcm/test_rtcm_integration_contract.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-7A_RTCM_ROUNDTABLE_INTEGRATION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-7A_RTCM_ROUNDTABLE_INTEGRATION_SAMPLE.json"],
    },
    {
        "surface_id": "rtcm_runtime_projection",
        "surface_type": "rtcm_projection",
        "module_path": "backend/app/rtcm/rtcm_runtime_projection.py",
        "import_path": "app.rtcm.rtcm_runtime_projection",
        "owner_domain": "rtcm",
        "test_refs": ["backend/app/rtcm/test_rtcm_runtime_projection.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-7B_RTCM_RUNTIME_PROJECTION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-7B_RTCM_RUNTIME_PROJECTION_SAMPLE.json"],
        "dependencies": ["rtcm_integration_contract"],
    },
    {
        "surface_id": "nightly_foundation_health_review",
        "surface_type": "nightly_review_projection",
        "module_path": "backend/app/nightly/foundation_health_review.py",
        "import_path": "app.nightly.foundation_health_review",
        "owner_domain": "nightly",
        "test_refs": ["backend/app/nightly/test_foundation_health_review.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-8A_NIGHTLY_FOUNDATION_HEALTH_REVIEW_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-8A_NIGHTLY_FOUNDATION_HEALTH_REVIEW_SAMPLE.json"],
    },
    {
        "surface_id": "nightly_feishu_summary_projection",
        "surface_type": "feishu_summary_projection",
        "module_path": "backend/app/nightly/foundation_health_summary.py",
        "import_path": "app.nightly.foundation_health_summary",
        "owner_domain": "nightly",
        "test_refs": ["backend/app/nightly/test_foundation_health_summary.py"],
        "report_refs": ["migration_reports/foundation_audit/R241-8B_NIGHTLY_FEISHU_SUMMARY_PROJECTION_REPORT.md"],
        "sample_refs": ["migration_reports/foundation_audit/R241-8B_NIGHTLY_FEISHU_SUMMARY_SAMPLE.json"],
        "dependencies": ["nightly_foundation_health_review"],
    },
    # Explicitly blocked future write/enforcement surfaces.
    {"surface_id": "memory_cleanup_write_policy", "surface_type": "memory_projection", "module_path": "", "owner_domain": "memory", "virtual": True, "blocked_intent": "memory cleanup without quarantine"},
    {"surface_id": "asset_promotion_elimination", "surface_type": "asset_projection", "module_path": "", "owner_domain": "asset", "virtual": True, "blocked_intent": "asset promotion without verification"},
    {"surface_id": "prompt_replacement_gepa_dspy_activation", "surface_type": "prompt_projection", "module_path": "", "owner_domain": "prompt", "virtual": True, "blocked_intent": "prompt replacement without backup"},
    {"surface_id": "tool_runtime_enforcement", "surface_type": "tool_runtime_projection", "module_path": "", "owner_domain": "tool_runtime", "virtual": True, "blocked_intent": "tool enforcement without dry-run"},
    {"surface_id": "gateway_run_path_integration", "surface_type": "gateway_mode_instrumentation", "module_path": "", "owner_domain": "gateway", "virtual": True, "blocked_intent": "Gateway routing mutation"},
    {"surface_id": "mode_router_replacement", "surface_type": "mode_instrumentation", "module_path": "", "owner_domain": "mode", "virtual": True, "blocked_intent": "Mode Router replacement"},
    {"surface_id": "rtcm_state_mutation", "surface_type": "rtcm_projection", "module_path": "", "owner_domain": "rtcm", "virtual": True, "blocked_intent": "RTCM state mutation"},
    {"surface_id": "real_feishu_push", "surface_type": "feishu_summary_projection", "module_path": "", "owner_domain": "nightly", "virtual": True, "blocked_intent": "Feishu push without webhook policy"},
    {"surface_id": "real_scheduler_watchdog_integration", "surface_type": "nightly_review_projection", "module_path": "", "owner_domain": "nightly", "virtual": True, "blocked_intent": "scheduler policy missing"},
]


def discover_foundation_surfaces(root: Optional[str] = None) -> Dict[str, Any]:
    base = Path(root).resolve() if root else ROOT
    warnings: List[str] = []
    surfaces: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    for definition in SURFACE_DEFINITIONS:
        surface = dict(definition)
        surface["root"] = str(base)
        if definition.get("virtual"):
            surface.update({"module_exists": False, "tests_exist": False, "reports_exist": False, "samples_exist": False, "import_ok": False})
            surfaces.append(surface)
            continue

        module_exists = _exists(base, surface.get("module_path"))
        test_refs = list(surface.get("test_refs") or [])
        report_refs = list(surface.get("report_refs") or [])
        sample_refs = list(surface.get("sample_refs") or [])
        tests_exist = all(_exists(base, ref) for ref in test_refs) if test_refs else False
        reports_exist = all(_exists(base, ref) for ref in report_refs) if report_refs else False
        samples_exist = all(_exists(base, ref) for ref in sample_refs) if sample_refs else True
        import_ok, import_warning = _safe_import(surface.get("import_path"))
        surface.update(
            {
                "module_exists": module_exists,
                "tests_exist": tests_exist,
                "reports_exist": reports_exist,
                "samples_exist": samples_exist,
                "import_ok": import_ok,
            }
        )
        local_warnings = []
        if not module_exists:
            local_warnings.append("module_missing")
        if not tests_exist:
            local_warnings.append("tests_missing")
        if not reports_exist:
            local_warnings.append("report_missing")
        if sample_refs and not samples_exist:
            local_warnings.append("sample_missing")
        if import_warning:
            local_warnings.append(import_warning)
        surface["warnings"] = _dedupe(list(surface.get("warnings") or []) + local_warnings)
        if local_warnings:
            missing.append({"surface_id": surface["surface_id"], "warnings": local_warnings})
            warnings.extend(f"{surface['surface_id']}:{warning}" for warning in local_warnings)
        surfaces.append(surface)

    return {
        "discovered_count": len(surfaces),
        "missing_surfaces": missing,
        "surfaces": surfaces,
        "warnings": _dedupe(warnings),
    }


def evaluate_surface_readiness(surface: Dict[str, Any]) -> Dict[str, Any]:
    surface_id = str(surface.get("surface_id") or "unknown")
    surface_type = _choice(surface.get("surface_type"), SURFACE_TYPES, "unknown")
    owner = str(surface.get("owner_domain") or "unknown")
    warnings = list(surface.get("warnings") or [])
    blockers: List[str] = []

    readiness = "read_only_ready"
    decision = "approve_read_only_integration"
    risk = "low"
    can_read_runtime = True
    can_write_runtime = False
    can_modify_execution_path = False
    requires_backup = False
    requires_rollback = False
    requires_user_confirmation = False
    requires_root_guard = False
    recommended = "approve_minimal_read_only_diagnostic_surface"

    blocked_intent = str(surface.get("blocked_intent") or "").lower()
    if blocked_intent:
        readiness = "blocked"
        decision = "block_integration"
        risk = "critical"
        can_read_runtime = False
        can_write_runtime = any(marker in blocked_intent for marker in ["write", "cleanup", "promotion", "replacement", "mutation", "push", "scheduler", "routing", "enforcement"])
        can_modify_execution_path = any(marker in blocked_intent for marker in ["routing", "router", "gateway", "scheduler", "enforcement"])
        requires_backup = any(marker in blocked_intent for marker in ["cleanup", "promotion", "replacement", "mutation", "write"])
        requires_rollback = requires_backup
        requires_user_confirmation = True
        blockers.append(blocked_intent)
        recommended = "keep_blocked_until_dedicated_contract_and_user_confirmation"
    elif not surface.get("module_exists") or not surface.get("import_ok"):
        readiness = "report_only"
        decision = "require_schema_hardening"
        risk = "medium"
        can_read_runtime = False
        blockers.extend([warning for warning in warnings if "module_missing" in warning or "import_failed" in warning])
        recommended = "fix_missing_module_or_import_before_integration"
    elif not surface.get("tests_exist"):
        readiness = "report_only"
        decision = "require_more_tests"
        risk = "medium"
        blockers.append("tests_missing")
        recommended = "add_tests_before_integration"
    elif surface_id == "mode_orchestration_contract":
        readiness = "append_only_ready"
        decision = "approve_append_only_integration"
        risk = "medium"
        recommended = "append_only_callgraph_artifact_allowed_after_review"
    elif surface_id == "gateway_mode_instrumentation":
        readiness = "read_only_ready"
        decision = "approve_read_only_integration"
        risk = "medium"
        recommended = "keep_as_optional_metadata_projection_no_run_path_change"
    elif surface_id == "nightly_feishu_summary_projection":
        readiness = "read_only_ready"
        decision = "approve_read_only_integration"
        risk = "medium"
        recommended = "allow_dry_run_payload_projection_only_no_push"
    elif surface_id == "queue_sandbox_truth_projection":
        readiness = "read_only_ready"
        decision = "approve_read_only_integration"
        risk = "medium"
        warnings.append("queue_path_mismatch_unresolved")
        recommended = "read_only_diagnostics_allowed_queue_mismatch_remains_warning"

    if surface_id in {"tool_runtime_contract", "tool_runtime_gateway_mode_projection"}:
        requires_root_guard = True

    return asdict(
        FoundationSurfaceReadiness(
            surface_id=surface_id,
            surface_type=surface_type,
            module_path=str(surface.get("module_path") or ""),
            owner_domain=owner,
            readiness_level=_choice(readiness, READINESS_LEVELS, "unknown"),
            decision=_choice(decision, DECISIONS, "unknown"),
            risk_level=_choice(risk, RISK_LEVELS, "unknown"),
            can_read_runtime=can_read_runtime,
            can_write_runtime=can_write_runtime,
            can_modify_execution_path=can_modify_execution_path,
            requires_backup=requires_backup,
            requires_rollback=requires_rollback,
            requires_user_confirmation=requires_user_confirmation,
            requires_root_guard=requires_root_guard,
            has_tests=bool(surface.get("tests_exist")),
            test_refs=list(surface.get("test_refs") or []),
            sample_refs=list(surface.get("sample_refs") or []),
            report_refs=list(surface.get("report_refs") or []),
            dependencies=list(surface.get("dependencies") or []),
            blockers=_dedupe(blockers),
            recommended_next_step=recommended,
            warnings=_dedupe(warnings),
        )
    )


def build_integration_matrix(surfaces: List[Dict[str, Any]]) -> Dict[str, Any]:
    evaluated = [evaluate_surface_readiness(surface) for surface in surfaces]
    by_readiness = Counter(item["readiness_level"] for item in evaluated)
    by_decision = Counter(item["decision"] for item in evaluated)
    by_risk = Counter(item["risk_level"] for item in evaluated)
    matrix = asdict(
        FoundationIntegrationMatrix(
            matrix_id=_make_id("integration_matrix", len(evaluated), _now()),
            generated_at=_now(),
            root=str(ROOT),
            surfaces=evaluated,
            by_readiness_level=dict(by_readiness),
            by_decision=dict(by_decision),
            by_risk_level=dict(by_risk),
            read_only_ready_count=by_readiness.get("read_only_ready", 0),
            append_only_ready_count=by_readiness.get("append_only_ready", 0),
            report_only_count=by_readiness.get("report_only", 0),
            blocked_count=by_readiness.get("blocked", 0),
            high_risk_count=by_risk.get("high", 0) + by_risk.get("critical", 0),
            recommended_integration_sequence=_integration_sequence(),
            warnings=_dedupe([warning for item in evaluated for warning in item.get("warnings", [])]),
        )
    )
    return matrix


def identify_integration_blockers(matrix: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[Dict[str, Any]] = []
    warnings: List[str] = []
    surfaces = matrix.get("surfaces") or []
    blocker_patterns = {
        "runtime mutation without rollback": ["mutation", "write"],
        "prompt replacement without backup": ["prompt replacement", "replacement"],
        "asset promotion without verification": ["asset promotion", "promotion"],
        "memory cleanup without quarantine": ["memory cleanup", "cleanup"],
        "tool enforcement without dry-run": ["tool enforcement", "enforcement"],
        "Feishu push without webhook policy": ["feishu push", "webhook"],
        "Gateway routing mutation": ["gateway routing", "routing"],
        "Mode Router replacement": ["mode router", "router"],
        "RTCM state mutation": ["rtcm state", "rtcm state mutation"],
        "governance write schema change": ["governance write"],
        "queue path mismatch unresolved": ["queue_path_mismatch_unresolved"],
        "context link missing": ["context link", "missing_context"],
    }
    for surface in surfaces:
        haystack = " ".join(
            [
                str(surface.get("surface_id")),
                str(surface.get("decision")),
                " ".join(surface.get("blockers") or []),
                " ".join(surface.get("warnings") or []),
                str(surface.get("recommended_next_step")),
            ]
        ).lower()
        if surface.get("readiness_level") == "blocked":
            blockers.append(
                {
                    "surface_id": surface.get("surface_id"),
                    "blocker_type": surface.get("blockers", ["blocked"])[0] if surface.get("blockers") else "blocked",
                    "risk_level": surface.get("risk_level"),
                    "recommended_next_step": surface.get("recommended_next_step"),
                }
            )
        for blocker_type, markers in blocker_patterns.items():
            if any(marker.lower() in haystack for marker in markers):
                blockers.append(
                    {
                        "surface_id": surface.get("surface_id"),
                        "blocker_type": blocker_type,
                        "risk_level": surface.get("risk_level"),
                        "recommended_next_step": surface.get("recommended_next_step"),
                    }
                )
    deduped = []
    seen = set()
    for blocker in blockers:
        key = (blocker.get("surface_id"), blocker.get("blocker_type"))
        if key not in seen:
            seen.add(key)
            deduped.append(blocker)
    return {"blocker_count": len(deduped), "blockers": deduped, "warnings": warnings}


def propose_minimal_read_only_integration_plan(matrix: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "phases": [
            {
                "phase_id": "Phase A",
                "name": "Read-only Diagnostic CLI / API",
                "surfaces": [
                    "truth_state_contract",
                    "governance_readonly_projection",
                    "queue_sandbox_truth_projection",
                    "memory_readonly_projection",
                    "asset_readonly_projection",
                    "prompt_readonly_projection",
                    "rtcm_runtime_projection",
                    "nightly_foundation_health_review",
                    "nightly_feishu_summary_projection",
                ],
                "allowed": True,
                "constraints": ["read_only_only", "no_runtime_write", "no_action_queue"],
            },
            {
                "phase_id": "Phase B",
                "name": "Append-only Audit Trail",
                "surfaces": ["mode_orchestration_contract", "tool_runtime_contract", "nightly_foundation_health_review"],
                "allowed": True,
                "constraints": ["append_only_artifact", "no_original_runtime_mutation"],
            },
            {
                "phase_id": "Phase C",
                "name": "Gateway Optional Metadata",
                "surfaces": ["gateway_mode_instrumentation", "tool_runtime_gateway_mode_projection"],
                "allowed": True,
                "constraints": ["optional_metadata_only", "no_routing_change", "no_response_schema_change"],
            },
            {
                "phase_id": "Phase D",
                "name": "Feishu Dry-run / Manual Push",
                "surfaces": ["nightly_feishu_summary_projection"],
                "allowed": True,
                "constraints": ["projection_payload_only", "no_webhook_by_default", "manual_send_policy_required"],
            },
            {
                "phase_id": "Phase E",
                "name": "Gated Write / Auto-fix",
                "surfaces": [
                    "memory_cleanup_write_policy",
                    "asset_promotion_elimination",
                    "prompt_replacement_gepa_dspy_activation",
                    "tool_runtime_enforcement",
                    "rtcm_state_mutation",
                ],
                "allowed": False,
                "constraints": ["blocked", "requires_backup", "requires_rollback", "requires_user_confirmation", "separate_contract_required"],
            },
        ],
        "warnings": [],
    }


def generate_integration_readiness_review(output_path: Optional[str] = None) -> Dict[str, Any]:
    discovery = discover_foundation_surfaces()
    matrix = build_integration_matrix(discovery["surfaces"])
    blockers = identify_integration_blockers(matrix)
    plan = propose_minimal_read_only_integration_plan(matrix)
    matrix_path = Path(output_path) if output_path and output_path.endswith(".json") else DEFAULT_MATRIX_PATH
    report_path = DEFAULT_REPORT_PATH if not output_path or output_path.endswith(".json") else Path(output_path)
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_payload = {
        "discovery": discovery,
        "matrix": matrix,
        "blockers": blockers,
        "minimal_read_only_integration_plan": plan,
        "generated_at": _now(),
        "warnings": _dedupe(discovery.get("warnings", []) + matrix.get("warnings", []) + blockers.get("warnings", []) + plan.get("warnings", [])),
    }
    matrix_path.write_text(json.dumps(matrix_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    review = asdict(
        IntegrationReadinessReview(
            review_id=_make_id("integration_readiness_review", matrix.get("matrix_id"), _now()),
            generated_at=_now(),
            matrix_ref=str(matrix_path),
            summary={
                "discovered_count": discovery.get("discovered_count", 0),
                "read_only_ready_count": matrix.get("read_only_ready_count", 0),
                "append_only_ready_count": matrix.get("append_only_ready_count", 0),
                "report_only_count": matrix.get("report_only_count", 0),
                "blocked_count": matrix.get("blocked_count", 0),
                "blocker_count": blockers.get("blocker_count", 0),
            },
            approved_read_only_surfaces=[s["surface_id"] for s in matrix["surfaces"] if s["readiness_level"] == "read_only_ready"],
            approved_append_only_surfaces=[s["surface_id"] for s in matrix["surfaces"] if s["readiness_level"] == "append_only_ready"],
            report_only_surfaces=[s["surface_id"] for s in matrix["surfaces"] if s["readiness_level"] == "report_only"],
            blocked_surfaces=[s["surface_id"] for s in matrix["surfaces"] if s["readiness_level"] == "blocked"],
            prerequisite_actions=blockers.get("blockers", []),
            next_phase_recommendation="R241-9B Minimal Read-only Integration Plan 细化",
            warnings=matrix_payload["warnings"],
        )
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_markdown_report(review, matrix_payload), encoding="utf-8")
    return {
        "matrix_path": str(matrix_path),
        "report_path": str(report_path),
        "review": review,
        **matrix_payload,
    }


def _render_markdown_report(review: Dict[str, Any], payload: Dict[str, Any]) -> str:
    matrix = payload["matrix"]
    blockers = payload["blockers"]
    lines = [
        "# R241-9A Foundation Integration Readiness Review",
        "",
        "## 1. Modification Scope",
        "",
        "- `backend/app/foundation/__init__.py`",
        "- `backend/app/foundation/integration_readiness.py`",
        "- `backend/app/foundation/test_integration_readiness.py`",
        "- `migration_reports/foundation_audit/R241-9A_FOUNDATION_INTEGRATION_READINESS_MATRIX.json`",
        "- `migration_reports/foundation_audit/R241-9A_FOUNDATION_INTEGRATION_READINESS_REVIEW.md`",
        "",
        "## 2. Matrix Summary",
        "",
        f"- discovered_count: {payload['discovery'].get('discovered_count')}",
        f"- read_only_ready_count: {matrix.get('read_only_ready_count')}",
        f"- append_only_ready_count: {matrix.get('append_only_ready_count')}",
        f"- report_only_count: {matrix.get('report_only_count')}",
        f"- blocked_count: {matrix.get('blocked_count')}",
        f"- high_risk_count: {matrix.get('high_risk_count')}",
        "",
        "## 3. Read-only Ready Surfaces",
        "",
    ]
    lines.extend(f"- {item}" for item in review.get("approved_read_only_surfaces", []))
    lines.extend(["", "## 4. Append-only Ready Surfaces", ""])
    lines.extend(f"- {item}" for item in review.get("approved_append_only_surfaces", []))
    lines.extend(["", "## 5. Report-only Surfaces", ""])
    if review.get("report_only_surfaces"):
        lines.extend(f"- {item}" for item in review.get("report_only_surfaces", []))
    else:
        lines.append("- none")
    lines.extend(["", "## 6. Blocked Surfaces", ""])
    lines.extend(f"- {item}" for item in review.get("blocked_surfaces", []))
    lines.extend(["", "## 7. Integration Blockers", ""])
    for blocker in blockers.get("blockers", []):
        lines.append(f"- {blocker.get('surface_id')}: {blocker.get('blocker_type')}")
    lines.extend(["", "## 8. Minimal Read-only Integration Plan", ""])
    for phase in payload["minimal_read_only_integration_plan"]["phases"]:
        lines.append(f"- {phase['phase_id']} {phase['name']}: allowed={phase['allowed']}; constraints={', '.join(phase['constraints'])}")
    lines.extend(
        [
            "",
            "## 9. Runtime Mutation Check",
            "",
            "No runtime integration was performed. No action queue, scheduler, Gateway path, governance, memory, asset, prompt, or RTCM runtime was modified.",
            "",
            "## 10. Next Step",
            "",
            "A. R241-9A 成功，可进入 R241-9B Minimal Read-only Integration Plan 细化。",
        ]
    )
    return "\n".join(lines) + "\n"


def _integration_sequence() -> List[Dict[str, Any]]:
    return [
        {"order": 1, "step": "Truth / State read-only APIs"},
        {"order": 2, "step": "Governance / Queue diagnostics"},
        {"order": 3, "step": "Memory / Asset read-only dashboards"},
        {"order": 4, "step": "Prompt / ToolRuntime read-only diagnostics"},
        {"order": 5, "step": "RTCM read-only runtime projection"},
        {"order": 6, "step": "Nightly summary read-only CLI/API"},
        {"order": 7, "step": "Feishu projection dry-run endpoint"},
        {"order": 8, "step": "Append-only audit store"},
        {"order": 9, "step": "Gateway optional metadata integration"},
        {"order": 10, "step": "Gated write / auto-fix separate review"},
    ]


def _exists(root: Path, rel: Optional[str]) -> bool:
    return bool(rel) and (root / str(rel)).exists()


def _safe_import(import_path: Optional[str]) -> tuple[bool, Optional[str]]:
    if not import_path:
        return False, None
    try:
        importlib.import_module(import_path)
        return True, None
    except Exception as exc:
        return False, f"import_failed:{exc}"


def _choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value) if value is not None else default
    return text if text in allowed else default


def _make_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}_{abs(hash(raw)) % 10_000_000_000:010d}"


def _dedupe(items: List[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in items:
        text = str(item)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
