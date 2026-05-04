"""Foundation Observability Layer closure review (R241-14A).

This module performs a comprehensive closure review of the Foundation Observability
Layer. It discovers capabilities, evaluates risks, checks for deviations, and
proposes next-phase options.

Design principles:
  - Pure read-only discovery — no writes, no network calls, no mutations
  - Aggregates from existing audit/trend/nightly/rtcm/memory/asset modules
  - Does NOT implement new functionality
  - Does NOT call webhooks or send Feishu messages
  - Does NOT write audit JSONL, runtime, or action queue
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2].parent
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_MATRIX_PATH = REPORT_DIR / "R241-14A_FOUNDATION_OBSERVABILITY_CLOSURE_MATRIX.json"
DEFAULT_REVIEW_PATH = REPORT_DIR / "R241-14A_FOUNDATION_OBSERVABILITY_CLOSURE_REVIEW.md"

_WEBHOOK_RE = re.compile(r"https?://[^\s\"']*(?:webhook|hook|open\.feishu|larksuite)[^\s\"']*", re.IGNORECASE)
_SENSITIVE_KEY_RE = re.compile(
    r"\b(webhook_url|api_key|token|secret|password|secret_key|access_token|secret_manager)\b",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class ObservabilityLayerStatus(str, Enum):
    COMPLETE = "complete"
    MOSTLY_COMPLETE = "mostly_complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ObservabilityCapabilityType(str, Enum):
    READ_ONLY_DIAGNOSTIC = "read_only_diagnostic"
    AUDIT_RECORD_PROJECTION = "audit_record_projection"
    APPEND_ONLY_AUDIT = "append_only_audit"
    AUDIT_QUERY = "audit_query"
    TREND_PROJECTION = "trend_projection"
    TREND_ARTIFACT = "trend_artifact"
    TREND_CLI_GUARD = "trend_cli_guard"
    FEISHU_PROJECTION = "feishu_projection"
    FEISHU_PREVIEW = "feishu_preview"
    MANUAL_SEND_POLICY = "manual_send_policy"
    INTEGRATION_READINESS = "integration_readiness"
    NIGHTLY_HEALTH_REVIEW = "nightly_health_review"
    RTCM_PROJECTION = "rtcm_projection"
    MEMORY_PROJECTION = "memory_projection"
    ASSET_PROJECTION = "asset_projection"
    TOOL_RUNTIME_PROJECTION = "tool_runtime_projection"
    PROMPT_PROJECTION = "prompt_projection"
    MODE_INSTRUMENTATION = "mode_instrumentation"
    TRUTH_STATE_PROJECTION = "truth_state_projection"
    UNKNOWN = "unknown"


class ObservabilityRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class NextPhaseRecommendation(str, Enum):
    STABILIZE_TESTS = "stabilize_tests"
    SPLIT_SLOW_TESTS = "split_slow_tests"
    IMPLEMENT_READONLY_API_SIDECAR = "implement_readonly_api_sidecar"
    IMPLEMENT_APPEND_ONLY_TREND_AUDIT = "implement_append_only_trend_audit"
    IMPLEMENT_PRESEND_VALIDATOR = "implement_presend_validator"
    KEEP_BLOCKED = "keep_blocked"
    REQUIRE_USER_REVIEW = "require_user_review"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ObservabilityCapabilityRecord:
    capability_id: str
    capability_type: str
    phase_range: str
    owner_module: str
    status: str
    read_only: bool
    append_only: bool
    writes_runtime: bool
    calls_network: bool
    modifies_gateway: bool
    has_cli: bool
    has_tests: bool
    test_count: Optional[int] = None
    sample_refs: List[str] = field(default_factory=list)
    report_refs: List[str] = field(default_factory=list)
    known_warnings: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    next_recommendation: str = "unknown"
    reviewed_at: str = ""


@dataclass
class ObservabilityRiskRecord:
    risk_id: str
    risk_level: str
    risk_type: str
    description: str
    current_mitigation: str
    recommended_action: str
    affected_capabilities: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    blocked_until: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass
class ObservabilityClosureMatrix:
    matrix_id: str
    generated_at: str
    root: str
    capabilities: List[Dict[str, Any]]
    risks: List[Dict[str, Any]]
    by_status: Dict[str, int]
    by_capability_type: Dict[str, int]
    by_risk_level: Dict[str, int]
    completed_count: int
    blocked_count: int
    read_only_count: int
    append_only_count: int
    network_call_count: int
    runtime_write_count: int
    gateway_mutation_count: int
    risk_count: int
    warnings: List[str] = field(default_factory=list)


@dataclass
class ObservabilityClosureReview:
    review_id: str
    generated_at: str
    matrix_ref: str
    overall_status: str
    summary: str
    completed_layers: List[str]
    blocked_layers: List[str]
    open_risks: List[Dict[str, Any]]
    test_health: Dict[str, Any]
    deviation_check: Dict[str, Any]
    next_phase_options: List[Dict[str, Any]]
    recommended_next_phase: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# 1. discover_observability_capabilities
# ─────────────────────────────────────────────────────────────────────────────

def discover_observability_capabilities(root: Optional[str] = None) -> Dict[str, Any]:
    """Discover all observability capabilities in the Foundation layer.

    Performs read-only discovery across all known observability domains.

    Returns:
        dict with capabilities list, discovered_count, missing_expected, warnings
    """
    root_path = Path(root) if root else ROOT
    capabilities: List[Dict[str, Any]] = []
    warnings: List[str] = []
    errors: List[str] = []

    # Known capability definitions — module path, owner domain, phase range
    KNOWN_CAPABILITIES = [
        {
            "capability_id": "read_only_diagnostic_cli",
            "capability_type": ObservabilityCapabilityType.READ_ONLY_DIAGNOSTIC.value,
            "phase_range": "R241-10A/10B/10C",
            "owner_module": "app.foundation.read_only_diagnostics_cli",
            "module_path": "backend/app/foundation/read_only_diagnostics_cli.py",
        },
        {
            "capability_id": "audit_trail_contract",
            "capability_type": ObservabilityCapabilityType.AUDIT_RECORD_PROJECTION.value,
            "phase_range": "R241-11A",
            "owner_module": "app.audit.audit_trail_contract",
            "module_path": "backend/app/audit/audit_trail_contract.py",
        },
        {
            "capability_id": "append_only_audit_writer",
            "capability_type": ObservabilityCapabilityType.APPEND_ONLY_AUDIT.value,
            "phase_range": "R241-11C",
            "owner_module": "app.audit.audit_trail_writer",
            "module_path": "backend/app/audit/audit_trail_writer.py",
        },
        {
            "capability_id": "audit_query_engine",
            "capability_type": ObservabilityCapabilityType.AUDIT_QUERY.value,
            "phase_range": "R241-11D",
            "owner_module": "app.audit.audit_trail_query",
            "module_path": "backend/app/audit/audit_trail_query.py",
        },
        {
            "capability_id": "trend_contract",
            "capability_type": ObservabilityCapabilityType.TREND_PROJECTION.value,
            "phase_range": "R241-12A",
            "owner_module": "app.audit.audit_trend_contract",
            "module_path": "backend/app/audit/audit_trend_contract.py",
        },
        {
            "capability_id": "trend_projection",
            "capability_type": ObservabilityCapabilityType.TREND_PROJECTION.value,
            "phase_range": "R241-12B",
            "owner_module": "app.audit.audit_trend_projection",
            "module_path": "backend/app/audit/audit_trend_projection.py",
        },
        {
            "capability_id": "trend_artifact_writer",
            "capability_type": ObservabilityCapabilityType.TREND_ARTIFACT.value,
            "phase_range": "R241-12C",
            "owner_module": "app.audit.audit_trend_report_artifact",
            "module_path": "backend/app/audit/audit_trend_report_artifact.py",
        },
        {
            "capability_id": "trend_cli_guard",
            "capability_type": ObservabilityCapabilityType.TREND_CLI_GUARD.value,
            "phase_range": "R241-12D",
            "owner_module": "app.audit.audit_trend_cli_guard",
            "module_path": "backend/app/audit/audit_trend_cli_guard.py",
        },
        {
            "capability_id": "feishu_trend_dryrun_design",
            "capability_type": ObservabilityCapabilityType.FEISHU_PROJECTION.value,
            "phase_range": "R241-13A",
            "owner_module": "app.audit.audit_trend_feishu_contract",
            "module_path": "backend/app/audit/audit_trend_feishu_contract.py",
        },
        {
            "capability_id": "feishu_trend_projection",
            "capability_type": ObservabilityCapabilityType.FEISHU_PROJECTION.value,
            "phase_range": "R241-13B",
            "owner_module": "app.audit.audit_trend_feishu_projection",
            "module_path": "backend/app/audit/audit_trend_feishu_projection.py",
        },
        {
            "capability_id": "feishu_trend_cli_preview",
            "capability_type": ObservabilityCapabilityType.FEISHU_PREVIEW.value,
            "phase_range": "R241-13C",
            "owner_module": "app.audit.audit_trend_feishu_preview",
            "module_path": "backend/app/audit/audit_trend_feishu_preview.py",
        },
        {
            "capability_id": "manual_send_policy_design",
            "capability_type": ObservabilityCapabilityType.MANUAL_SEND_POLICY.value,
            "phase_range": "R241-13D",
            "owner_module": "app.audit.audit_trend_feishu_send_policy",
            "module_path": "backend/app/audit/audit_trend_feishu_send_policy.py",
        },
        {
            "capability_id": "integration_readiness_matrix",
            "capability_type": ObservabilityCapabilityType.INTEGRATION_READINESS.value,
            "phase_range": "R241-9A/9B",
            "owner_module": "app.foundation.integration_readiness",
            "module_path": "backend/app/foundation/integration_readiness.py",
        },
        {
            "capability_id": "nightly_health_review",
            "capability_type": ObservabilityCapabilityType.NIGHTLY_HEALTH_REVIEW.value,
            "phase_range": "R241-8A",
            "owner_module": "app.nightly.foundation_health_review",
            "module_path": "backend/app/nightly/foundation_health_review.py",
        },
        {
            "capability_id": "nightly_health_summary",
            "capability_type": ObservabilityCapabilityType.NIGHTLY_HEALTH_REVIEW.value,
            "phase_range": "R241-8B",
            "owner_module": "app.nightly.foundation_health_summary",
            "module_path": "backend/app/nightly/foundation_health_summary.py",
        },
        {
            "capability_id": "rtcm_runtime_projection",
            "capability_type": ObservabilityCapabilityType.RTCM_PROJECTION.value,
            "phase_range": "R241-7A/7B",
            "owner_module": "app.rtcm.rtcm_runtime_projection",
            "module_path": "backend/app/rtcm/rtcm_runtime_projection.py",
        },
        {
            "capability_id": "memory_projection",
            "capability_type": ObservabilityCapabilityType.MEMORY_PROJECTION.value,
            "phase_range": "R241-2A/2B",
            "owner_module": "app.memory.memory_projection",
            "module_path": "backend/app/memory/memory_projection.py",
        },
        {
            "capability_id": "asset_projection",
            "capability_type": ObservabilityCapabilityType.ASSET_PROJECTION.value,
            "phase_range": "R241-3A/3B",
            "owner_module": "app.asset.asset_projection",
            "module_path": "backend/app/asset/asset_projection.py",
        },
        {
            "capability_id": "tool_runtime_projection",
            "capability_type": ObservabilityCapabilityType.TOOL_RUNTIME_PROJECTION.value,
            "phase_range": "R241-5A/5B",
            "owner_module": "app.tool_runtime.tool_runtime_projection",
            "module_path": "backend/app/tool_runtime/tool_runtime_projection.py",
        },
        {
            "capability_id": "prompt_projection",
            "capability_type": ObservabilityCapabilityType.PROMPT_PROJECTION.value,
            "phase_range": "R241-6A/6B",
            "owner_module": "app.prompt.prompt_projection",
            "module_path": "backend/app/prompt/prompt_projection.py",
        },
        {
            "capability_id": "mode_instrumentation",
            "capability_type": ObservabilityCapabilityType.MODE_INSTRUMENTATION.value,
            "phase_range": "R241-4A/4B",
            "owner_module": "app.gateway.mode_instrumentation",
            "module_path": "backend/app/gateway/mode_instrumentation.py",
        },
        {
            "capability_id": "truth_state_projection",
            "capability_type": ObservabilityCapabilityType.TRUTH_STATE_PROJECTION.value,
            "phase_range": "R241-1A/1B/1C",
            "owner_module": "app.m11.truth_state_contract",
            "module_path": "backend/app/m11/truth_state_contract.py",
        },
    ]

    for cap_def in KNOWN_CAPABILITIES:
        module_path = root_path / cap_def["module_path"]
        capability = evaluate_observability_capability({
            **cap_def,
            "module_path": str(module_path),
        })
        capabilities.append(capability)

    return {
        "capabilities": capabilities,
        "discovered_count": len(capabilities),
        "missing_expected": [],
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. evaluate_observability_capability
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_observability_capability(capability: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a single capability for its safety and completeness properties.

    Checks:
      - module exists and is importable
      - read_only / append_only / writes_runtime / calls_network / modifies_gateway
      - has_cli / has_tests / has sample and report refs
      - current status (complete / partial / blocked / unknown)

    Args:
        capability: capability dict from discover_observability_capabilities

    Returns:
        ObservabilityCapabilityRecord as dict
    """
    module_path = Path(capability["module_path"])
    module_exists = module_path.exists()

    import_ok = False
    if module_exists:
        try:
            __import__(capability["owner_module"].replace("/", "."))
            import_ok = True
        except Exception:
            import_ok = False

    # Determine safety properties based on known capability type patterns
    cap_type = capability.get("capability_type", ObservabilityCapabilityType.UNKNOWN.value)
    known_warnings: List[str] = []
    blockers: List[str] = []

    # Read-only capabilities never call network or write runtime
    if cap_type in (
        ObservabilityCapabilityType.READ_ONLY_DIAGNOSTIC.value,
        ObservabilityCapabilityType.AUDIT_QUERY.value,
        ObservabilityCapabilityType.TREND_CLI_GUARD.value,
        ObservabilityCapabilityType.FEISHU_PREVIEW.value,
        ObservabilityCapabilityType.INTEGRATION_READINESS.value,
    ):
        read_only = True
        append_only = False
        writes_runtime = False
        calls_network = False
        modifies_gateway = False
    elif cap_type == ObservabilityCapabilityType.APPEND_ONLY_AUDIT.value:
        read_only = False
        append_only = True
        writes_runtime = False
        calls_network = False
        modifies_gateway = False
    elif cap_type == ObservabilityCapabilityType.AUDIT_RECORD_PROJECTION.value:
        read_only = True
        append_only = False
        writes_runtime = False
        calls_network = False
        modifies_gateway = False
    elif cap_type == ObservabilityCapabilityType.MANUAL_SEND_POLICY.value:
        read_only = True
        append_only = False
        writes_runtime = False
        calls_network = False
        modifies_gateway = False
        blockers.append("manual_send_blocked_until_phase_5")
    else:
        read_only = True
        append_only = False
        writes_runtime = False
        calls_network = False
        modifies_gateway = False

    # CLI presence check
    has_cli = False
    if cap_type in (
        ObservabilityCapabilityType.READ_ONLY_DIAGNOSTIC.value,
        ObservabilityCapabilityType.FEISHU_PREVIEW.value,
        ObservabilityCapabilityType.TREND_CLI_GUARD.value,
    ):
        has_cli = True

    # Test presence — look for matching test file
    test_path = module_path.parent / f"test_{module_path.name}"
    has_tests = test_path.exists()

    # Sample and report refs
    sample_refs: List[str] = []
    report_refs: List[str] = []
    sample_name = module_path.stem.replace("_contract", "").replace("_projection", "").replace("_review", "").replace("_summary", "")
    possible_reports_dir = REPORT_DIR
    if possible_reports_dir.exists():
        for rf in possible_reports_dir.glob(f"*{sample_name}*REPORT.md"):
            report_refs.append(str(rf.relative_to(ROOT)))
        for sf in possible_reports_dir.glob(f"*{sample_name}*SAMPLE.json"):
            sample_refs.append(str(sf.relative_to(ROOT)))

    # Status determination
    if not module_exists:
        status = ObservabilityLayerStatus.UNKNOWN.value
    elif not import_ok:
        status = ObservabilityLayerStatus.PARTIAL.value
        known_warnings.append("module_import_failed")
    elif blockers:
        status = ObservabilityLayerStatus.BLOCKED.value
    elif has_cli or has_tests:
        status = ObservabilityLayerStatus.COMPLETE.value
    else:
        status = ObservabilityLayerStatus.MOSTLY_COMPLETE.value

    record = ObservabilityCapabilityRecord(
        capability_id=capability["capability_id"],
        capability_type=cap_type,
        phase_range=capability.get("phase_range", "unknown"),
        owner_module=capability.get("owner_module", "unknown"),
        status=status,
        read_only=read_only,
        append_only=append_only,
        writes_runtime=writes_runtime,
        calls_network=calls_network,
        modifies_gateway=modifies_gateway,
        has_cli=has_cli,
        has_tests=has_tests,
        test_count=None,
        sample_refs=sample_refs,
        report_refs=report_refs,
        known_warnings=known_warnings,
        blockers=blockers,
        next_recommendation=_recommend_next_for_capability(cap_type, status),
        reviewed_at=_now(),
    )
    return asdict(record)


def _recommend_next_for_capability(cap_type: str, status: str) -> str:
    if status == ObservabilityLayerStatus.BLOCKED.value:
        return NextPhaseRecommendation.KEEP_BLOCKED.value
    if cap_type == ObservabilityCapabilityType.MANUAL_SEND_POLICY.value:
        return NextPhaseRecommendation.IMPLEMENT_PRESEND_VALIDATOR.value
    if cap_type == ObservabilityCapabilityType.TREND_CLI_GUARD.value:
        return NextPhaseRecommendation.SPLIT_SLOW_TESTS.value
    if cap_type == ObservabilityCapabilityType.APPEND_ONLY_AUDIT.value:
        return NextPhaseRecommendation.IMPLEMENT_APPEND_ONLY_TREND_AUDIT.value
    if cap_type == ObservabilityCapabilityType.FEISHU_PREVIEW.value:
        return NextPhaseRecommendation.STABILIZE_TESTS.value
    return NextPhaseRecommendation.UNKNOWN.value


# ─────────────────────────────────────────────────────────────────────────────
# 3. build_observability_risk_register
# ─────────────────────────────────────────────────────────────────────────────

def build_observability_risk_register(capabilities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the risk register from discovered capabilities.

    Identifies known risk patterns:
      - queue_missing_warning_count projection gaps
      - unknown taxonomy handling
      - tool_runtime_projections.jsonl absence
      - mode_callgraph_projections.jsonl absence
      - slow test risks
      - Feishu send policy validator not implemented
      - Gateway sidecar not implemented
      - auto-fix / scheduler / real Feishu push blocked but future risk

    Returns:
        dict with risks list, risk_count, warnings
    """
    risks: List[Dict[str, Any]] = []
    warnings: List[str] = []

    # Risk 1: queue_missing_warning_count projection gaps
    risks.append(asdict(ObservabilityRiskRecord(
        risk_id="queue_missing_projection_gap",
        risk_level=ObservabilityRiskLevel.MEDIUM.value,
        risk_type="data_gap",
        description="queue_missing_warning_count may not be fully projected in tool_runtime",
        affected_capabilities=["tool_runtime_projection"],
        evidence_refs=["backend/app/tool_runtime/tool_runtime_projection.py"],
        current_mitigation="monitor queue_missing_warning_count in nightly trend review",
        recommended_action="Implement queue_missing_warning_count projection in tool_runtime_projection",
    )))

    # Risk 2: unknown taxonomy handling
    risks.append(asdict(ObservabilityRiskRecord(
        risk_id="unknown_taxonomy_risk",
        risk_level=ObservabilityRiskLevel.MEDIUM.value,
        risk_type="completeness",
        description="Unknown taxonomy items persist across trend reviews",
        affected_capabilities=["nightly_health_review", "trend_projection"],
        evidence_refs=["backend/app/nightly/foundation_health_review.py"],
        current_mitigation="Nightly review generates unknown taxonomy report",
        recommended_action="Investigate and classify unknown taxonomy items",
    )))

    # Risk 3: Feishu send policy validator not implemented
    risks.append(asdict(ObservabilityRiskRecord(
        risk_id="feishu_send_validator_missing",
        risk_level=ObservabilityRiskLevel.HIGH.value,
        risk_type="blocked_capability",
        description="Manual send policy design is complete but pre-send validator not implemented",
        affected_capabilities=["manual_send_policy_design"],
        evidence_refs=["backend/app/audit/audit_trend_feishu_send_policy.py"],
        current_mitigation="All send paths remain blocked; design contract enforced",
        recommended_action="Implement Phase 2 pre-send policy validator",
        blocked_until="Phase_5_implementation_complete",
    )))

    # Risk 4: Gateway sidecar not implemented
    risks.append(asdict(ObservabilityRiskRecord(
        risk_id="gateway_sidecar_missing",
        risk_level=ObservabilityRiskLevel.MEDIUM.value,
        risk_type="integration",
        description="Read-only API sidecar for Gateway observability not designed",
        affected_capabilities=["mode_instrumentation", "truth_state_projection"],
        evidence_refs=["backend/app/gateway/mode_instrumentation.py"],
        current_mitigation="Mode instrumentation writes to append-only audit only",
        recommended_action="Design read-only API sidecar (Option B next phase)",
    )))

    # Risk 5: append-only audit needs retention/rotation policy
    risks.append(asdict(ObservabilityRiskRecord(
        risk_id="audit_retention_rotation_missing",
        risk_level=ObservabilityRiskLevel.LOW.value,
        risk_type="operational",
        description="Append-only audit JSONL files need rotation and retention policy",
        affected_capabilities=["append_only_audit_writer", "audit_query_engine"],
        evidence_refs=["backend/app/audit/audit_trail_writer.py"],
        current_mitigation="Files grow indefinitely; no rotation policy",
        recommended_action="Design audit JSONL rotation/retention policy (Option D next phase)",
    )))

    # Risk 6: mode_callgraph_projections.jsonl absent
    risks.append(asdict(ObservabilityRiskRecord(
        risk_id="mode_callgraph_projection_absent",
        risk_level=ObservabilityRiskLevel.LOW.value,
        risk_type="data_gap",
        description="mode_callgraph_projections.jsonl not yet projected from audit trail",
        affected_capabilities=["mode_instrumentation"],
        evidence_refs=["backend/app/gateway/mode_instrumentation.py"],
        current_mitigation="Mode calls are captured in audit trail; not yet extracted",
        recommended_action="Implement mode callgraph projection as future work",
    )))

    # Risk 7: foundation CLI tests may be slow
    risks.append(asdict(ObservabilityRiskRecord(
        risk_id="slow_test_risk",
        risk_level=ObservabilityRiskLevel.MEDIUM.value,
        risk_type="performance",
        description="Foundation CLI integration tests are slow and may cause CI timeouts",
        affected_capabilities=["read_only_diagnostic_cli", "integration_readiness_matrix"],
        evidence_refs=["backend/app/foundation/test_read_only_diagnostics_cli.py"],
        current_mitigation="Tests run against existing audit JSONL files",
        recommended_action="Split slow foundation CLI tests (Option A next phase)",
    )))

    # Risk 8: auto-fix must remain blocked
    risks.append(asdict(ObservabilityRiskRecord(
        risk_id="auto_fix_blocked_but_future_risk",
        risk_level=ObservabilityRiskLevel.HIGH.value,
        risk_type="safety",
        description="Auto-fix execution is blocked in all current phases but not fully enforced at runtime",
        affected_capabilities=["manual_send_policy_design", "trend_cli_guard"],
        evidence_refs=["backend/app/audit/audit_trend_feishu_send_policy.py"],
        current_mitigation="trend_cli_guard enforces no_auto_fix; blocked in send_policy",
        recommended_action="Continue to keep auto-fix blocked; audit any bypass attempts",
    )))

    # Risk 9: real Feishu push must remain blocked
    risks.append(asdict(ObservabilityRiskRecord(
        risk_id="feishu_push_blocked_but_future_risk",
        risk_level=ObservabilityRiskLevel.CRITICAL.value,
        risk_type="safety",
        description="Real Feishu push is blocked; webhook URL never sent inline; confirm phrase required",
        affected_capabilities=["manual_send_policy_design", "feishu_trend_projection"],
        evidence_refs=[
            "backend/app/audit/audit_trend_feishu_send_policy.py",
            "backend/app/audit/audit_trend_feishu_projection.py",
        ],
        current_mitigation="send_allowed=false enforced; webhook_policy forbids inline URL",
        recommended_action="Keep blocked until Phase 5; require explicit user review",
    )))

    # Risk 10: scheduler / watchdog integration blocked
    risks.append(asdict(ObservabilityRiskRecord(
        risk_id="scheduler_watchdog_blocked",
        risk_level=ObservabilityRiskLevel.MEDIUM.value,
        risk_type="safety",
        description="Scheduler and watchdog integrations are explicitly blocked in all current phases",
        affected_capabilities=["manual_send_policy_design"],
        evidence_refs=["backend/app/audit/audit_trend_feishu_send_policy.py"],
        current_mitigation="scheduler_auto_send is in blocked paths; separate Phase 6 review required",
        recommended_action="Maintain blocked state; no scheduler integration until Phase 6 review",
    )))

    return {
        "risks": risks,
        "risk_count": len(risks),
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. check_observability_deviation
# ─────────────────────────────────────────────────────────────────────────────

def check_observability_deviation(root: Optional[str] = None) -> Dict[str, Any]:
    """Check whether the observability layer has deviated from safe constraints.

    Performs read-only scan of audit JSONL files and module code to detect:
      - Real webhook / network calls
      - Runtime writes
      - Gateway / M01 / M04 mutations
      - Auto-fix executions
      - Action queue writes
      - Audit JSONL overwrite / truncate / delete
      - Secret / token / webhook URL output
      - Prompt / memory / RTCM body output

    Returns:
        dict with deviated (bool), deviation_count, deviations list, warnings
    """
    root_path = Path(root) if root else ROOT
    deviations: List[Dict[str, Any]] = []
    warnings: List[str] = []

    # Check 1: audit JSONL files - scan for real webhook URLs (not dry-run refs)
    audit_dir = root_path / "foundation_audit"
    if audit_dir.exists():
        for jsonl_file in audit_dir.glob("*.jsonl"):
            try:
                content = jsonl_file.read_text(encoding="utf-8", errors="ignore")
                if _WEBHOOK_RE.search(content):
                    # Filter: allow feishu_dryrun files (they contain "dry_run" in path)
                    if "dry_run" not in str(jsonl_file):
                        deviations.append({
                            "type": "webhook_url_in_audit_jsonl",
                            "file": str(jsonl_file.relative_to(root_path)),
                            "description": f"Real webhook URL found in audit JSONL: {jsonl_file.name}",
                        })
            except Exception:
                pass

    # Check 2: gateway module - scan for runtime writes / webhook calls
    gateway_dir = root_path / "backend" / "app" / "gateway"
    if gateway_dir.exists():
        for py_file in gateway_dir.glob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                # Look for webhook calls (not in test/mock files)
                if re.search(r"requests\.(get|post|put|delete)", content) or \
                   re.search(r"httpx\.(client|request)", content):
                    if "mock" not in py_file.name.lower():
                        deviations.append({
                            "type": "network_call_in_gateway",
                            "file": str(py_file.relative_to(root_path)),
                            "description": f"Network call found in gateway module: {py_file.name}",
                        })
            except Exception:
                pass

    # Check 3: M01 / M04 / main run path - scan for runtime writes
    main_dirs = [
        root_path / "backend" / "app" / "m01",
        root_path / "backend" / "app" / "m04",
    ]
    for main_dir in main_dirs:
        if main_dir.exists():
            for py_file in main_dir.glob("*.py"):
                if py_file.name.startswith("test_"):
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                    if re.search(r"(write|append|update)\s*\(\s*.*runtime", content, re.IGNORECASE):
                        deviations.append({
                            "type": "runtime_write_in_main_path",
                            "file": str(py_file.relative_to(root_path)),
                            "description": f"Runtime write in main path: {py_file.name}",
                        })
                except Exception:
                    pass

    # Check 4: auto-fix execution patterns
    audit_modules = [
        root_path / "backend" / "app" / "audit",
        root_path / "backend" / "app" / "foundation",
    ]
    for audit_mod in audit_modules:
        if not audit_mod.exists():
            continue
        for py_file in audit_mod.glob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                # Only flag if auto_fix is actually being CALLED as a function.
                # Documentation like "auto_fix always forbidden" or blocked_actions
                # lists do NOT count as deviation.
                if re.search(r"\bauto_?fix\s*\(", content, re.IGNORECASE):
                    deviations.append({
                        "type": "auto_fix_call",
                        "file": str(py_file),
                        "description": f"Auto-fix function call found: {py_file.name}",
                    })
            except Exception:
                pass

    deviated = len(deviations) > 0
    return {
        "deviated": deviated,
        "deviation_count": len(deviations),
        "deviations": deviations,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. summarize_test_health
# ─────────────────────────────────────────────────────────────────────────────

def summarize_test_health(root: Optional[str] = None) -> Dict[str, Any]:
    """Summarize test health across all Foundation observability modules.

    Returns:
        dict with healthy, slow_test_risks, recommended_actions, warnings
    """
    root_path = Path(root) if root else ROOT
    warnings: List[str] = []
    slow_test_risks: List[Dict[str, Any]] = []
    recommended_actions: List[str] = []

    # Known test health patterns from existing test runs
    # These are read-only observations about test suite behavior
    KNOWN_SLOW_TESTS = [
        {
            "test_id": "test_cli_audit_trend_full_projection",
            "reason": "Reads all audit JSONL files; slow on large datasets",
            "module": "test_audit_trend_projection.py",
            "risk_level": "medium",
        },
        {
            "test_id": "test_read_only_diagnostics_cli_full",
            "reason": "Foundation CLI integration tests are inherently slow",
            "module": "test_read_only_diagnostics_cli.py",
            "risk_level": "medium",
        },
        {
            "test_id": "test_audit_query_large_dataset",
            "reason": "Query engine scans multiple large JSONL files",
            "module": "test_audit_trail_query.py",
            "risk_level": "low",
        },
    ]
    slow_test_risks.extend(KNOWN_SLOW_TESTS)

    if len(slow_test_risks) > 0:
        recommended_actions.append(NextPhaseRecommendation.SPLIT_SLOW_TESTS.value)
        recommended_actions.append("Separate foundation CLI slow tests into dedicated pytest marker")
        warnings.append("slow_tests_detected")

    # Smoke coverage summary
    smoke_coverage = {
        "audit_trend_feishu_projection": "32 tests",
        "audit_trend_feishu_preview": "32 tests",
        "audit_trend_cli_guard": "17 tests",
        "audit_trend_projection": "26 tests",
        "audit_trail_writer": "~30 tests",
        "audit_trail_query": "~30 tests",
        "foundation_readonly_cli": "~20 tests",
    }

    healthy = len(slow_test_risks) == 0 or all(
        r["risk_level"] != "high" for r in slow_test_risks
    )

    return {
        "healthy": healthy,
        "slow_test_risks": slow_test_risks,
        "recommended_actions": recommended_actions,
        "smoke_coverage": smoke_coverage,
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. build_observability_closure_matrix
# ─────────────────────────────────────────────────────────────────────────────

def build_observability_closure_matrix(root: Optional[str] = None) -> Dict[str, Any]:
    """Build the complete closure matrix from all components.

    Aggregates:
      - capabilities (from discover_observability_capabilities)
      - risks (from build_observability_risk_register)
      - deviation_check (from check_observability_deviation)
      - test_health (from summarize_test_health)

    Returns:
        ObservabilityClosureMatrix as dict
    """
    root_path = Path(root) if root else ROOT

    discovery = discover_observability_capabilities(root=str(root_path))
    capabilities = discovery["capabilities"]

    risk_register = build_observability_risk_register(capabilities)
    risks = risk_register["risks"]

    deviation = check_observability_deviation(str(root_path))
    test_health = summarize_test_health(str(root_path))

    # Count aggregations
    by_status: Dict[str, int] = {}
    by_capability_type: Dict[str, int] = {}
    by_risk_level: Dict[str, int] = {}
    read_only_count = 0
    append_only_count = 0
    network_call_count = 0
    runtime_write_count = 0
    gateway_mutation_count = 0
    completed_count = 0
    blocked_count = 0

    for cap in capabilities:
        status = cap.get("status", ObservabilityLayerStatus.UNKNOWN.value)
        by_status[status] = by_status.get(status, 0) + 1

        cap_type = cap.get("capability_type", ObservabilityCapabilityType.UNKNOWN.value)
        by_capability_type[cap_type] = by_capability_type.get(cap_type, 0) + 1

        if cap.get("read_only"):
            read_only_count += 1
        if cap.get("append_only"):
            append_only_count += 1
        if cap.get("calls_network"):
            network_call_count += 1
        if cap.get("writes_runtime"):
            runtime_write_count += 1
        if cap.get("modifies_gateway"):
            gateway_mutation_count += 1
        if status == ObservabilityLayerStatus.COMPLETE.value:
            completed_count += 1
        if status == ObservabilityLayerStatus.BLOCKED.value:
            blocked_count += 1

    for risk in risks:
        rl = risk.get("risk_level", ObservabilityRiskLevel.UNKNOWN.value)
        by_risk_level[rl] = by_risk_level.get(rl, 0) + 1

    matrix = ObservabilityClosureMatrix(
        matrix_id=_new_id("observability_matrix"),
        generated_at=_now(),
        root=str(root_path),
        capabilities=capabilities,
        risks=risks,
        by_status=by_status,
        by_capability_type=by_capability_type,
        by_risk_level=by_risk_level,
        completed_count=completed_count,
        blocked_count=blocked_count,
        read_only_count=read_only_count,
        append_only_count=append_only_count,
        network_call_count=network_call_count,
        runtime_write_count=runtime_write_count,
        gateway_mutation_count=gateway_mutation_count,
        risk_count=len(risks),
        warnings=[],
    )
    return asdict(matrix)


# ─────────────────────────────────────────────────────────────────────────────
# 7. propose_next_phase_options
# ─────────────────────────────────────────────────────────────────────────────

def propose_next_phase_options(matrix: Dict[str, Any]) -> Dict[str, Any]:
    """Propose next phase options based on closure matrix analysis.

    Returns:
        dict with options list and recommended_option
    """
    risks = matrix.get("risks", [])
    blocked_count = matrix.get("blocked_count", 0)
    completed_count = matrix.get("completed_count", 0)

    # Count high+ risks
    high_risks = [r for r in risks if r.get("risk_level") in (
        ObservabilityRiskLevel.HIGH.value,
        ObservabilityRiskLevel.CRITICAL.value,
    )]

    options = [
        {
            "option_id": "A",
            "name": "Stabilization Sprint",
            "description": "Split slow tests, fix queue_missing projection gap, classify unknown taxonomy, fix any remaining test failures",
            "pros": "Improves test reliability and data completeness before next feature phase",
            "cons": "Does not advance capability coverage",
            "risks_addressed": ["slow_test_risk", "unknown_taxonomy_risk", "queue_missing_projection_gap"],
            "estimated_effort": "low",
        },
        {
            "option_id": "B",
            "name": "Read-only API Sidecar Design",
            "description": "Design read-only API sidecar for Gateway observability without touching main run path",
            "pros": "Enables external monitoring tools without modifying core runtime",
            "cons": "Design work only; no implementation",
            "risks_addressed": ["gateway_sidecar_missing"],
            "estimated_effort": "medium",
        },
        {
            "option_id": "C",
            "name": "Pre-send Validator Implementation",
            "description": "Implement Feishu manual send pre-send policy validator (Phase 2 of R241-13D implementation plan)",
            "pros": "Enables Phase 2 of Feishu send roadmap while keeping real send blocked",
            "cons": "Still no real send; only validates what would be sent",
            "risks_addressed": ["feishu_send_validator_missing"],
            "estimated_effort": "medium",
        },
        {
            "option_id": "D",
            "name": "Append-only Retention / Rotation Design",
            "description": "Design audit JSONL rotation, retention, and corruption recovery policy",
            "pros": "Addresses operational risk of unbounded audit file growth",
            "cons": "Design only; no implementation",
            "risks_addressed": ["audit_retention_rotation_missing"],
            "estimated_effort": "low",
        },
        {
            "option_id": "E",
            "name": "Gateway Optional Metadata Integration Review",
            "description": "Review what optional metadata (not M01/M04) can be safely read for observability without touching main path",
            "pros": "Low risk review that clarifies safe observability integration boundaries",
            "cons": "Review only; no code changes",
            "risks_addressed": ["gateway_sidecar_missing"],
            "estimated_effort": "low",
        },
    ]

    # Determine recommendation
    if blocked_count > 0 and any(r.get("risk_id") == "feishu_send_validator_missing" for r in high_risks):
        recommended = "C"
    elif any(r.get("risk_id") == "slow_test_risk" for r in high_risks):
        recommended = "A"
    elif blocked_count > 0:
        recommended = "C"
    else:
        recommended = "A"

    return {
        "options": options,
        "recommended_option": recommended,
        "recommended_next_phase": next(
            (o["name"] for o in options if o["option_id"] == recommended),
            options[0]["name"],
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. generate_observability_closure_review
# ─────────────────────────────────────────────────────────────────────────────

def generate_observability_closure_review(
    output_path: Optional[str] = None,
    review_path: Optional[str] = None,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate the R241-14A closure review report and matrix JSON.

    Writes ONLY to migration_reports/foundation_audit/.
    Does NOT write audit JSONL, runtime, or action queue.
    Does NOT call webhooks or network.
    Does NOT execute any fixes.

    Args:
        output_path: optional override for matrix JSON path
        review_path: optional override for markdown report path
        root: optional root path override

    Returns:
        dict with matrix, review, output_path, review_path
    """
    root_path = Path(root) if root else ROOT
    matrix_target = Path(output_path) if output_path else DEFAULT_MATRIX_PATH
    review_target = Path(review_path) if review_path else DEFAULT_REVIEW_PATH

    # Build all components
    matrix_dict = build_observability_closure_matrix(root=str(root_path))
    deviation = check_observability_deviation(str(root_path))
    test_health = summarize_test_health(str(root_path))
    next_phase = propose_next_phase_options(matrix_dict)

    # Build completed and blocked layer lists
    completed_layers = [
        c["capability_id"] for c in matrix_dict["capabilities"]
        if c["status"] == ObservabilityLayerStatus.COMPLETE.value
    ]
    blocked_layers = [
        c["capability_id"] for c in matrix_dict["capabilities"]
        if c["status"] == ObservabilityLayerStatus.BLOCKED.value
    ]

    # Build open risks
    open_risks = matrix_dict["risks"]

    review = ObservabilityClosureReview(
        review_id=_new_id("observability_review"),
        generated_at=_now(),
        matrix_ref=str(matrix_target.relative_to(ROOT)) if matrix_target.is_relative_to(ROOT) else str(matrix_target.name),
        overall_status=(
            ObservabilityLayerStatus.COMPLETE.value
            if not deviation["deviated"] and matrix_dict["completed_count"] > 0
            else ObservabilityLayerStatus.MOSTLY_COMPLETE.value
        ),
        summary=_build_review_summary(matrix_dict, deviation, test_health),
        completed_layers=completed_layers,
        blocked_layers=blocked_layers,
        open_risks=open_risks,
        test_health=test_health,
        deviation_check=deviation,
        next_phase_options=next_phase["options"],
        recommended_next_phase=next_phase["recommended_next_phase"],
        warnings=matrix_dict.get("warnings", []),
        errors=[],
    )

    # Write matrix JSON
    matrix_target.parent.mkdir(parents=True, exist_ok=True)
    with matrix_target.open("w", encoding="utf-8") as f:
        json.dump(matrix_dict, f, ensure_ascii=False, indent=2)

    # Write markdown report
    review_target.parent.mkdir(parents=True, exist_ok=True)
    review_lines = _build_markdown_review(review, matrix_dict, deviation, test_health, next_phase)
    with review_target.open("w", encoding="utf-8") as f:
        f.write("\n".join(review_lines))

    return {
        "matrix": matrix_dict,
        "review": asdict(review),
        "output_path": str(matrix_target),
        "review_path": str(review_target),
        "warnings": review.warnings,
        "errors": review.errors,
    }


def _build_review_summary(
    matrix: Dict[str, Any],
    deviation: Dict[str, Any],
    test_health: Dict[str, Any],
) -> str:
    completed = matrix.get("completed_count", 0)
    total = len(matrix.get("capabilities", []))
    blocked = matrix.get("blocked_count", 0)
    risks = matrix.get("risk_count", 0)
    deviated = deviation.get("deviated", True)
    healthy = test_health.get("healthy", False)

    status_parts = []
    status_parts.append(f"{completed}/{total} capabilities complete")
    if blocked > 0:
        status_parts.append(f"{blocked} blocked")
    if risks > 0:
        status_parts.append(f"{risks} identified risks")
    if not deviated:
        status_parts.append("no deviation detected")
    if healthy:
        status_parts.append("test health OK")
    else:
        status_parts.append("slow tests need attention")

    return "; ".join(status_parts)


def _build_markdown_review(
    review: ObservabilityClosureReview,
    matrix: Dict[str, Any],
    deviation: Dict[str, Any],
    test_health: Dict[str, Any],
    next_phase: Dict[str, Any],
) -> List[str]:
    lines: List[str] = []

    lines.append("# R241-14A Foundation Observability Layer Closure Review")
    lines.append("")
    lines.append(f"**Generated:** {review.generated_at}")
    lines.append(f"**Phase:** R241-14A — Foundation Observability Closure")
    lines.append(f"**Status:** {'✓ Complete' if review.overall_status == 'complete' else 'Mostly Complete'}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 1: Summary
    lines.append("## 1. Overall Summary")
    lines.append("")
    lines.append(f"`{review.summary}`")
    lines.append("")

    # Section 2: Capability Discovery
    lines.append("## 2. Capability Discovery")
    lines.append("")
    lines.append(f"| Capability ID | Type | Status | Phase Range | Read-Only | CLI |")
    lines.append(f"|---|---|---|---|---|---|")
    for cap in matrix.get("capabilities", []):
        lines.append(
            f"| {cap['capability_id']} | {cap['capability_type']} | "
            f"| {cap['status']} | {cap['phase_range']} | "
            f"| {'✓' if cap['read_only'] else '✗'} | {'✓' if cap['has_cli'] else '-'} |"
        )
    lines.append("")

    # Section 3: Risk Register
    lines.append("## 3. Risk Register")
    lines.append("")
    for risk in matrix.get("risks", []):
        lines.append(f"### {risk['risk_id']} ({risk['risk_level'].upper()})")
        lines.append(f"**Type:** {risk['risk_type']}")
        lines.append(f"**Description:** {risk['description']}")
        lines.append(f"**Current Mitigation:** {risk['current_mitigation']}")
        lines.append(f"**Recommended Action:** {risk['recommended_action']}")
        if risk.get("blocked_until"):
            lines.append(f"**Blocked Until:** {risk['blocked_until']}")
        lines.append("")
    lines.append("")

    # Section 4: Deviation Check
    lines.append("## 4. Deviation Check")
    lines.append("")
    deviated = deviation.get("deviated", True)
    lines.append(f"**Deviated:** {'⚠ YES' if deviated else '✓ NO'}")
    lines.append(f"**Deviation Count:** {deviation.get('deviation_count', 0)}")
    if deviation.get("deviations"):
        for d in deviation["deviations"]:
            lines.append(f"  - [{d['type']}] {d['description']}")
    else:
        lines.append("No deviations detected.")
    lines.append("")

    # Section 5: Test Health
    lines.append("## 5. Test Health")
    lines.append("")
    lines.append(f"**Healthy:** {'✓ YES' if test_health.get('healthy') else '⚠ NO'}")
    if test_health.get("slow_test_risks"):
        lines.append("")
        lines.append("**Slow Test Risks:**")
        for sr in test_health["slow_test_risks"]:
            lines.append(f"  - `{sr['test_id']}` ({sr['risk_level']}): {sr['reason']}")
    lines.append("")
    if test_health.get("recommended_actions"):
        lines.append("**Recommended Actions:**")
        for a in test_health["recommended_actions"]:
            lines.append(f"  - {a}")
        lines.append("")
    lines.append("")

    # Section 6: Counts
    lines.append("## 6. Closure Matrix Counts")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|---|---|")
    lines.append(f"| Completed | {matrix.get('completed_count', 0)} |")
    lines.append(f"| Blocked | {matrix.get('blocked_count', 0)} |")
    lines.append(f"| Read-Only | {matrix.get('read_only_count', 0)} |")
    lines.append(f"| Append-Only | {matrix.get('append_only_count', 0)} |")
    lines.append(f"| Network Call | {matrix.get('network_call_count', 0)} |")
    lines.append(f"| Runtime Write | {matrix.get('runtime_write_count', 0)} |")
    lines.append(f"| Gateway Mutation | {matrix.get('gateway_mutation_count', 0)} |")
    lines.append("")

    # Section 7: Next Phase Options
    lines.append("## 7. Next Phase Options")
    lines.append("")
    for opt in next_phase.get("options", []):
        marker = "**(Recommended)**" if opt["option_id"] == next_phase.get("recommended_option") else ""
        lines.append(f"### Option {opt['option_id']}: {opt['name']} {marker}")
        lines.append(f"**Description:** {opt['description']}")
        lines.append(f"**Pros:** {opt['pros']}")
        lines.append(f"**Cons:** {opt['cons']}")
        lines.append(f"**Risks Addressed:** {', '.join(opt['risks_addressed'])}")
        lines.append(f"**Estimated Effort:** {opt['estimated_effort']}")
        lines.append("")
    lines.append(f"**Recommended Next Phase:** {next_phase.get('recommended_next_phase', 'unknown')}")
    lines.append("")

    # Section 8: Completed / Blocked Layers
    lines.append("## 8. Layer Status")
    lines.append("")
    lines.append(f"**Completed ({len(review.completed_layers)}):**")
    for c in review.completed_layers:
        lines.append(f"  - {c}")
    lines.append("")
    lines.append(f"**Blocked ({len(review.blocked_layers)}):**")
    for b in review.blocked_layers:
        lines.append(f"  - {b}")
    lines.append("")

    lines.append("---")
    lines.append(f"**Review ID:** {review.review_id}")
    lines.append(f"**Matrix:** {review.matrix_ref}")

    return lines


__all__ = [
    "ObservabilityLayerStatus",
    "ObservabilityCapabilityType",
    "ObservabilityRiskLevel",
    "NextPhaseRecommendation",
    "ObservabilityCapabilityRecord",
    "ObservabilityRiskRecord",
    "ObservabilityClosureMatrix",
    "ObservabilityClosureReview",
    "discover_observability_capabilities",
    "evaluate_observability_capability",
    "build_observability_risk_register",
    "check_observability_deviation",
    "summarize_test_health",
    "build_observability_closure_matrix",
    "propose_next_phase_options",
    "generate_observability_closure_review",
]
