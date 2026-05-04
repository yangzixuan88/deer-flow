"""Nightly Trend Report design contract (R241-12A).

This module is design-only. It defines schemas, metric catalogs, trend windows,
and regression rules for future read-only trend projection from audit_trail
query results.

Security invariants:
- Never writes audit_trail JSONL.
- Never modifies existing JSONL files.
- Never calls network, webhooks, scheduler, Gateway, or auto-fix flows.
- Only writes design artifacts under migration_reports/foundation_audit.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TrendMetricType(str, Enum):
    DIAGNOSTIC_STATUS_RATE = "diagnostic_status_rate"
    WARNING_COUNT = "warning_count"
    ERROR_COUNT = "error_count"
    SEVERITY_COUNT = "severity_count"
    EVENT_TYPE_COUNT = "event_type_count"
    COMMAND_RUN_COUNT = "command_run_count"
    DOMAIN_SIGNAL_COUNT = "domain_signal_count"
    CRITICAL_COUNT = "critical_count"
    HIGH_COUNT = "high_count"
    BLOCKED_ACTION_COUNT = "blocked_action_count"
    REQUIRES_CONFIRMATION_COUNT = "requires_confirmation_count"
    QUEUE_MISSING_COUNT = "queue_missing_count"
    UNKNOWN_TAXONOMY_COUNT = "unknown_taxonomy_count"
    ROLLBACK_MISSING_COUNT = "rollback_missing_count"
    BACKUP_MISSING_COUNT = "backup_missing_count"
    APPEND_RECORD_COUNT = "append_record_count"
    INVALID_LINE_COUNT = "invalid_line_count"
    UNKNOWN = "unknown"


class TrendDirection(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"
    UNKNOWN = "unknown"


class TrendSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class TrendWindow(str, Enum):
    LAST_24H = "last_24h"
    LAST_7D = "last_7d"
    LAST_30D = "last_30d"
    CUSTOM = "custom"
    ALL_AVAILABLE = "all_available"


class TrendReportStatus(str, Enum):
    DESIGN_ONLY = "design_only"
    READY_FOR_DRY_RUN = "ready_for_dry_run"
    BLOCKED_INSUFFICIENT_DATA = "blocked_insufficient_data"
    BLOCKED_QUERY_ERROR = "blocked_query_error"
    UNKNOWN = "unknown"


@dataclass
class AuditTrendPoint:
    point_id: str
    timestamp: str
    window: str
    metric_type: str
    metric_name: str
    metric_value: float
    source_command: Optional[str] = None
    event_type: Optional[str] = None
    domain: Optional[str] = None
    severity: Optional[str] = None
    source_record_refs: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class AuditTrendSeries:
    series_id: str
    metric_type: str
    metric_name: str
    window: str
    points: List[Dict[str, Any]] = field(default_factory=list)
    direction: str = TrendDirection.INSUFFICIENT_DATA.value
    latest_value: Optional[float] = None
    previous_value: Optional[float] = None
    delta: Optional[float] = None
    delta_percent: Optional[float] = None
    sample_count: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class TrendRegressionSignal:
    regression_id: str
    metric_type: str
    metric_name: str
    severity: str
    direction: str
    current_value: float
    baseline_value: Optional[float] = None
    threshold: Optional[float] = None
    affected_commands: List[str] = field(default_factory=list)
    affected_domains: List[str] = field(default_factory=list)
    evidence_record_refs: List[str] = field(default_factory=list)
    recommended_action: str = "diagnostic_only"
    warnings: List[str] = field(default_factory=list)


@dataclass
class NightlyTrendReport:
    trend_report_id: str
    generated_at: str
    status: str
    window: str
    source_query_refs: List[str] = field(default_factory=list)
    total_records_analyzed: int = 0
    series: List[Dict[str, Any]] = field(default_factory=list)
    regression_signals: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class NightlyTrendDesign:
    design_id: str
    generated_at: str
    input_sources: List[Dict[str, Any]] = field(default_factory=list)
    metric_catalog: List[Dict[str, Any]] = field(default_factory=list)
    trend_windows: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    regression_rules: List[Dict[str, Any]] = field(default_factory=list)
    output_formats: List[str] = field(default_factory=list)
    future_integration_points: List[Dict[str, Any]] = field(default_factory=list)
    blocked_actions: List[Dict[str, Any]] = field(default_factory=list)
    implementation_phases: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTRACT_JSON = (
    ROOT
    / "migration_reports"
    / "foundation_audit"
    / "R241-12A_NIGHTLY_TREND_REPORT_CONTRACT.json"
)
DEFAULT_DESIGN_MD = (
    ROOT
    / "migration_reports"
    / "foundation_audit"
    / "R241-12A_NIGHTLY_TREND_REPORT_DESIGN.md"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _enum_values(enum_cls: Any) -> List[str]:
    return [item.value for item in enum_cls]


def _safe_query_input_sources() -> List[Dict[str, Any]]:
    """Return query engine references without invoking read/write behavior."""
    input_sources = [
        {
            "module": "backend/app/audit/audit_trail_query.py",
            "functions": [
                "query_audit_trail",
                "scan_append_only_audit_trail",
                "summarize_audit_query_result",
                "build_audit_query_filter",
            ],
            "read_only": True,
            "writes_audit_jsonl": False,
        }
    ]
    try:
        from app.audit import audit_trail_query as query_module  # noqa: F401
    except Exception as exc:
        input_sources[0]["import_warning"] = f"audit_query_import_failed:{exc}"
    return input_sources


def build_trend_metric_catalog() -> Dict[str, Any]:
    """Build the design catalog of supported trend metrics."""
    metrics = [
        {
            "metric_type": TrendMetricType.DIAGNOSTIC_STATUS_RATE.value,
            "metric_name": "partial_warning_rate",
            "description": "Ratio of diagnostic audit records whose status is partial_warning.",
            "source_field": "status",
            "aggregation_method": "count(status=partial_warning)/count(all diagnostic records)",
            "severity_mapping": {"lt_0_25": "low", "gte_0_25": "medium", "gte_0_5": "high"},
            "recommended_action_type": "diagnostic_only",
        },
        {
            "metric_type": TrendMetricType.DIAGNOSTIC_STATUS_RATE.value,
            "metric_name": "failed_rate",
            "description": "Ratio of diagnostic audit records whose status is failed.",
            "source_field": "status",
            "aggregation_method": "count(status=failed)/count(all diagnostic records)",
            "severity_mapping": {"gt_0": "high", "gte_0_2": "critical"},
            "recommended_action_type": "review_tool_policy",
        },
        {
            "metric_type": TrendMetricType.APPEND_RECORD_COUNT.value,
            "metric_name": "total_audit_records",
            "description": "Total valid append-only audit records in the selected window.",
            "source_field": "audit_record_id",
            "aggregation_method": "count(valid records)",
            "severity_mapping": {"zero": "medium", "positive": "info"},
            "recommended_action_type": "diagnostic_only",
        },
        {
            "metric_type": TrendMetricType.CRITICAL_COUNT.value,
            "metric_name": "critical_signal_count",
            "description": "Number of critical health or summary signals.",
            "source_field": "summary.by_severity.critical",
            "aggregation_method": "sum critical count",
            "severity_mapping": {"gt_0": "critical"},
            "recommended_action_type": "requires_user_confirmation",
        },
        {
            "metric_type": TrendMetricType.HIGH_COUNT.value,
            "metric_name": "high_signal_count",
            "description": "Number of high-severity health or summary signals.",
            "source_field": "summary.by_severity.high",
            "aggregation_method": "sum high count",
            "severity_mapping": {"gt_0": "high", "increasing": "high"},
            "recommended_action_type": "diagnostic_only",
        },
        {
            "metric_type": TrendMetricType.QUEUE_MISSING_COUNT.value,
            "metric_name": "queue_missing_warning_count",
            "description": "Occurrences of queue_missing warnings in diagnostics.",
            "source_field": "warnings",
            "aggregation_method": "count warning contains queue_missing",
            "severity_mapping": {"persistent": "medium"},
            "recommended_action_type": "diagnostic_only",
        },
        {
            "metric_type": TrendMetricType.UNKNOWN_TAXONOMY_COUNT.value,
            "metric_name": "unknown_taxonomy_count",
            "description": "Unknown taxonomy warnings across Memory, Prompt, RTCM, Asset, and Truth projections.",
            "source_field": "warnings",
            "aggregation_method": "count warning contains unknown",
            "severity_mapping": {"persistent": "medium", "increasing": "high"},
            "recommended_action_type": "refine_taxonomy",
        },
        {
            "metric_type": TrendMetricType.ROLLBACK_MISSING_COUNT.value,
            "metric_name": "rollback_missing_count",
            "description": "Missing rollback warning count from Prompt/ToolRuntime/Health signals.",
            "source_field": "warnings",
            "aggregation_method": "count warning contains rollback_missing",
            "severity_mapping": {"gt_0": "high"},
            "recommended_action_type": "add_rollback",
        },
        {
            "metric_type": TrendMetricType.BACKUP_MISSING_COUNT.value,
            "metric_name": "backup_missing_count",
            "description": "Missing backup warning count from Prompt/ToolRuntime/Health signals.",
            "source_field": "warnings",
            "aggregation_method": "count warning contains backup_missing",
            "severity_mapping": {"gt_0": "high"},
            "recommended_action_type": "add_backup",
        },
        {
            "metric_type": TrendMetricType.COMMAND_RUN_COUNT.value,
            "metric_name": "feishu_dry_run_count",
            "description": "Count of Feishu summary dry-run projection records.",
            "source_field": "source_command,event_type",
            "aggregation_method": "count source_command contains feishu or event_type is feishu_summary_dryrun",
            "severity_mapping": {"zero_after_nightly": "medium"},
            "recommended_action_type": "diagnostic_only",
        },
        {
            "metric_type": TrendMetricType.COMMAND_RUN_COUNT.value,
            "metric_name": "nightly_review_count",
            "description": "Count of Nightly Foundation Health Review records.",
            "source_field": "source_command,event_type",
            "aggregation_method": "count nightly health review records",
            "severity_mapping": {"zero_in_expected_window": "high"},
            "recommended_action_type": "diagnostic_only",
        },
        {
            "metric_type": TrendMetricType.INVALID_LINE_COUNT.value,
            "metric_name": "invalid_jsonl_line_count",
            "description": "Invalid JSONL line count reported by scan_append_only_audit_trail.",
            "source_field": "file_summaries.invalid_line_count",
            "aggregation_method": "sum invalid line count",
            "severity_mapping": {"gt_0": "high"},
            "recommended_action_type": "diagnostic_only",
        },
    ]
    return {
        "metric_count": len(metrics),
        "metrics": metrics,
        "warnings": [],
    }


def build_trend_window_spec() -> Dict[str, Any]:
    """Build supported trend window specifications."""
    windows = {
        TrendWindow.LAST_24H.value: {
            "start_time_rule": "now - 24 hours",
            "end_time_rule": "now",
            "minimum_required_points": 2,
            "expected_use": "Daily regression and nightly health drift detection.",
        },
        TrendWindow.LAST_7D.value: {
            "start_time_rule": "now - 7 days",
            "end_time_rule": "now",
            "minimum_required_points": 3,
            "expected_use": "Short-term trend smoothing and persistent warning detection.",
        },
        TrendWindow.LAST_30D.value: {
            "start_time_rule": "now - 30 days",
            "end_time_rule": "now",
            "minimum_required_points": 5,
            "expected_use": "Longer baseline comparison and recurring regression detection.",
        },
        TrendWindow.ALL_AVAILABLE.value: {
            "start_time_rule": "first available audit record",
            "end_time_rule": "last available audit record",
            "minimum_required_points": 1,
            "expected_use": "Bootstrap baseline when insufficient historical data exists.",
        },
        TrendWindow.CUSTOM.value: {
            "start_time_rule": "caller supplied start_time",
            "end_time_rule": "caller supplied end_time",
            "minimum_required_points": 1,
            "expected_use": "Manual investigation and targeted incident review.",
        },
    }
    return {"windows": windows, "warnings": []}


def design_trend_extraction_from_audit_query() -> Dict[str, Any]:
    """Describe how future dry-run projection extracts trend points."""
    extraction_fields = [
        {
            "field": "source_command",
            "usage": "Group trend points by CLI command or dry-run command surface.",
        },
        {
            "field": "event_type",
            "usage": "Separate diagnostic_run, nightly_health_review, feishu_summary_dryrun, and append events.",
        },
        {
            "field": "status",
            "usage": "Compute ok / partial_warning / failed rates.",
        },
        {
            "field": "warnings",
            "usage": "Count queue_missing, unknown taxonomy, backup_missing, rollback_missing, and policy warnings.",
        },
        {
            "field": "errors",
            "usage": "Compute hard failure trends and query/runtime design errors.",
        },
        {
            "field": "summary",
            "usage": "Extract total_signals, by_severity, action_candidate_count, blocked_high_risk_count, requires_confirmation_count.",
        },
        {
            "field": "summary.by_severity",
            "usage": "Compute critical/high/medium/low severity series.",
        },
        {
            "field": "summary.action_candidate_count",
            "usage": "Track action candidate volume over time.",
        },
        {
            "field": "summary.blocked_high_risk_count",
            "usage": "Track blocked high-risk action trend.",
        },
        {
            "field": "payload_hash",
            "usage": "Detect repeated identical payloads and de-duplicate trend evidence.",
        },
        {
            "field": "generated_at",
            "usage": "Primary event timestamp for trend bucketing.",
        },
        {
            "field": "observed_at",
            "usage": "Fallback source observation timestamp.",
        },
        {
            "field": "appended_at",
            "usage": "Append-only record timestamp and fallback ordering key.",
        },
    ]
    return {
        "source": "AuditQueryResult.records from query_audit_trail() and file_summaries from scan_append_only_audit_trail()",
        "extraction_fields": extraction_fields,
        "time_precedence": ["generated_at", "observed_at", "appended_at"],
        "record_reference_fields": ["audit_record_id", "payload_hash", "source_command", "event_type"],
        "warnings": [],
    }


def design_regression_detection_rules() -> Dict[str, Any]:
    """Define design-only regression detection rules."""
    def rule(
        rule_id: str,
        metric_name: str,
        trigger_condition: str,
        severity: str,
        required_evidence: List[str],
        recommended_action: str,
    ) -> Dict[str, Any]:
        return {
            "rule_id": rule_id,
            "metric_name": metric_name,
            "trigger_condition": trigger_condition,
            "severity": severity,
            "required_evidence": required_evidence,
            "recommended_action": recommended_action,
            "auto_fix_allowed": False,
        }

    rules = [
        rule(
            "partial_warning_rate_increases",
            "partial_warning_rate",
            "current window rate exceeds baseline by >= 20% or crosses 0.5",
            TrendSeverity.MEDIUM.value,
            ["status counts", "baseline rate", "current rate"],
            "diagnostic_only",
        ),
        rule(
            "critical_count_increases",
            "critical_signal_count",
            "critical count is greater than previous comparable window",
            TrendSeverity.CRITICAL.value,
            ["by_severity.critical", "source record refs"],
            "requires_user_confirmation",
        ),
        rule(
            "high_count_increases",
            "high_signal_count",
            "high count is greater than previous comparable window",
            TrendSeverity.HIGH.value,
            ["by_severity.high", "source record refs"],
            "diagnostic_only",
        ),
        rule(
            "queue_missing_persists",
            "queue_missing_warning_count",
            "queue_missing appears in two or more consecutive nightly windows",
            TrendSeverity.MEDIUM.value,
            ["warning refs", "source_command queue-sandbox/nightly"],
            "diagnostic_only",
        ),
        rule(
            "unknown_taxonomy_persists",
            "unknown_taxonomy_count",
            "unknown taxonomy warning count remains > 0 across configured window",
            TrendSeverity.MEDIUM.value,
            ["warning refs", "affected domains"],
            "refine_taxonomy",
        ),
        rule(
            "backup_missing_persists",
            "backup_missing_count",
            "backup_missing remains > 0 across configured window",
            TrendSeverity.HIGH.value,
            ["warning refs", "affected commands/domains"],
            "add_backup",
        ),
        rule(
            "rollback_missing_persists",
            "rollback_missing_count",
            "rollback_missing remains > 0 across configured window",
            TrendSeverity.HIGH.value,
            ["warning refs", "affected commands/domains"],
            "add_rollback",
        ),
        rule(
            "invalid_line_count_gt_zero",
            "invalid_jsonl_line_count",
            "scan_append_only_audit_trail reports invalid_line_count > 0",
            TrendSeverity.HIGH.value,
            ["file_summaries.invalid_line_count", "target file refs"],
            "diagnostic_only",
        ),
        rule(
            "no_nightly_record_in_expected_window",
            "nightly_review_count",
            "nightly health review record count is 0 in expected nightly window",
            TrendSeverity.HIGH.value,
            ["time window", "query result count"],
            "diagnostic_only",
        ),
        rule(
            "feishu_dry_run_missing_after_nightly",
            "feishu_dry_run_count",
            "nightly record exists but no Feishu summary dry-run record follows it in window",
            TrendSeverity.MEDIUM.value,
            ["nightly record refs", "feishu dry-run query result"],
            "diagnostic_only",
        ),
    ]
    return {"rules": rules, "warnings": []}


def build_nightly_trend_report_design(root: Optional[str] = None) -> Dict[str, Any]:
    """Build the full design-only Nightly Trend contract."""
    warnings: List[str] = []
    root_path = str(Path(root).resolve()) if root else str(ROOT)

    metric_catalog = build_trend_metric_catalog()["metrics"]
    trend_windows = build_trend_window_spec()["windows"]
    extraction_design = design_trend_extraction_from_audit_query()
    regression_rules = design_regression_detection_rules()["rules"]

    future_integration_points = [
        {
            "name": "audit_trend_cli",
            "description": "Future read-only audit-trend CLI powered by audit query engine.",
            "runtime_write_allowed": False,
            "network_allowed": False,
        },
        {
            "name": "feishu_trend_summary_dry_run",
            "description": "Future Feishu card payload projection for trend summary; no webhook send by default.",
            "send_allowed": False,
            "webhook_call_allowed": False,
        },
        {
            "name": "long_term_dashboard",
            "description": "Future dashboard design, separate from Gateway main run path.",
            "gateway_mutation_allowed": False,
        },
    ]

    blocked_actions = [
        {"action": "write_audit_jsonl", "blocked": True, "reason": "R241-12A is design-only"},
        {"action": "modify_existing_jsonl", "blocked": True, "reason": "append-only integrity"},
        {"action": "runtime_write", "blocked": True, "reason": "trend design cannot mutate runtime"},
        {"action": "action_queue_write", "blocked": True, "reason": "no action queue in design phase"},
        {"action": "feishu_send", "blocked": True, "reason": "dry-run only"},
        {"action": "network_call", "blocked": True, "reason": "no webhook or network"},
        {"action": "auto_fix", "blocked": True, "reason": "trend report only creates future action candidates"},
        {"action": "gateway_mutation", "blocked": True, "reason": "no Gateway/M01/M04/DeerFlow main path mutation"},
    ]

    implementation_phases = [
        {
            "phase": "Phase 1",
            "name": "Design-only Contract",
            "scope": "Current R241-12A; define schema, metrics, windows, extraction rules, and regression rules.",
            "runtime_write_allowed": False,
        },
        {
            "phase": "Phase 2",
            "name": "Dry-run Trend Projection",
            "scope": "Call audit query engine to generate trend points without writing trend runtime.",
            "runtime_write_allowed": False,
        },
        {
            "phase": "Phase 3",
            "name": "Trend Report Artifact",
            "scope": "Write report artifacts to migration_reports/foundation_audit only.",
            "runtime_write_allowed": False,
        },
        {
            "phase": "Phase 4",
            "name": "Nightly Trend CLI",
            "scope": "Add read-only audit-trend CLI; no scheduler coupling.",
            "runtime_write_allowed": False,
        },
        {
            "phase": "Phase 5",
            "name": "Feishu Trend Summary Dry-run",
            "scope": "Generate Feishu trend payload projection, do not send.",
            "runtime_write_allowed": False,
            "send_allowed": False,
        },
        {
            "phase": "Phase 6",
            "name": "Long-term Trend Dashboard",
            "scope": "Future separate design; not connected to Gateway main path.",
            "runtime_write_allowed": False,
            "gateway_mutation_allowed": False,
        },
    ]

    design = NightlyTrendDesign(
        design_id=_new_id("nightly_trend_design"),
        generated_at=_now(),
        input_sources=_safe_query_input_sources(),
        metric_catalog=metric_catalog,
        trend_windows=trend_windows,
        regression_rules=regression_rules,
        output_formats=["json", "markdown", "text"],
        future_integration_points=future_integration_points,
        blocked_actions=blocked_actions,
        implementation_phases=implementation_phases,
        warnings=warnings,
    )

    result = asdict(design)
    result["root"] = root_path
    result["status"] = TrendReportStatus.DESIGN_ONLY.value
    result["extraction_design"] = extraction_design
    result["schema_objects"] = {
        "AuditTrendPoint": list(AuditTrendPoint.__dataclass_fields__.keys()),
        "AuditTrendSeries": list(AuditTrendSeries.__dataclass_fields__.keys()),
        "TrendRegressionSignal": list(TrendRegressionSignal.__dataclass_fields__.keys()),
        "NightlyTrendReport": list(NightlyTrendReport.__dataclass_fields__.keys()),
        "NightlyTrendDesign": list(NightlyTrendDesign.__dataclass_fields__.keys()),
    }
    result["enum_values"] = {
        "TrendMetricType": _enum_values(TrendMetricType),
        "TrendDirection": _enum_values(TrendDirection),
        "TrendSeverity": _enum_values(TrendSeverity),
        "TrendWindow": _enum_values(TrendWindow),
        "TrendReportStatus": _enum_values(TrendReportStatus),
    }
    return result


def _walk_values(obj: Any, path: str = "") -> List[tuple[str, Any]]:
    values: List[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            next_path = f"{path}.{key}" if path else str(key)
            values.append((next_path, value))
            values.extend(_walk_values(value, next_path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            next_path = f"{path}[{index}]"
            values.extend(_walk_values(value, next_path))
    return values


def validate_trend_report_design(design: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the design-only contract safety constraints."""
    warnings: List[str] = []
    errors: List[str] = []

    if not design.get("metric_catalog"):
        errors.append("metric_catalog_empty")
    if not design.get("regression_rules"):
        errors.append("regression_rules_empty")

    output_formats = set(design.get("output_formats") or [])
    for required_format in ("json", "markdown", "text"):
        if required_format not in output_formats:
            errors.append(f"missing_output_format:{required_format}")

    phase_names = " ".join(
        f"{phase.get('phase', '')} {phase.get('name', '')}"
        for phase in design.get("implementation_phases") or []
        if isinstance(phase, dict)
    )
    for phase_number in range(1, 7):
        if f"Phase {phase_number}" not in phase_names:
            errors.append(f"missing_phase:{phase_number}")

    for path, value in _walk_values(design):
        key = path.split(".")[-1].lower()
        if key.endswith("auto_fix_allowed") and value is True:
            errors.append(f"auto_fix_enabled:{path}")
        if key in {"runtime_write_allowed", "writes_runtime", "runtime_write"} and value is True:
            errors.append(f"runtime_write_enabled:{path}")
        if key in {"send_allowed", "webhook_call_allowed", "feishu_send_enabled", "network_allowed"} and value is True:
            errors.append(f"external_send_or_network_enabled:{path}")
        if key in {"gateway_mutation_allowed", "gateway_mutation"} and value is True:
            errors.append(f"gateway_mutation_enabled:{path}")

    return {
        "valid": not errors,
        "warnings": warnings,
        "errors": errors,
    }


def _markdown_report(design: Dict[str, Any], validation: Dict[str, Any], json_path: Path) -> str:
    schema = design.get("schema_objects", {})
    metrics = design.get("metric_catalog", [])
    windows = design.get("trend_windows", {})
    extraction = design.get("extraction_design", {})
    rules = design.get("regression_rules", [])
    phases = design.get("implementation_phases", [])

    def bullet(items: List[str]) -> str:
        return "\n".join(f"- `{item}`" for item in items)

    metric_lines = [
        f"- `{metric.get('metric_name')}` / `{metric.get('metric_type')}`: {metric.get('description')}"
        for metric in metrics
    ]
    window_lines = [
        f"- `{name}`: {spec.get('start_time_rule')} -> {spec.get('end_time_rule')}, min_points={spec.get('minimum_required_points')}"
        for name, spec in windows.items()
    ]
    extraction_lines = [
        f"- `{field.get('field')}`: {field.get('usage')}"
        for field in extraction.get("extraction_fields", [])
    ]
    rule_lines = [
        f"- `{rule.get('rule_id')}`: {rule.get('trigger_condition')}; severity=`{rule.get('severity')}`; auto_fix_allowed={rule.get('auto_fix_allowed')}"
        for rule in rules
    ]
    phase_lines = [
        f"- `{phase.get('phase')}` {phase.get('name')}: {phase.get('scope')}"
        for phase in phases
    ]

    return "\n".join([
        "# R241-12A Nightly Trend Report Design",
        "",
        "## 1. 修改文件清单",
        "",
        "- `backend/app/audit/audit_trend_contract.py`",
        "- `backend/app/audit/test_audit_trend_contract.py`",
        "- `backend/app/audit/__init__.py`",
        "- `migration_reports/foundation_audit/R241-12A_NIGHTLY_TREND_REPORT_CONTRACT.json`",
        "- `migration_reports/foundation_audit/R241-12A_NIGHTLY_TREND_REPORT_DESIGN.md`",
        "",
        "## 2. AuditTrendPoint 字段",
        "",
        bullet(schema.get("AuditTrendPoint", [])),
        "",
        "## 3. AuditTrendSeries 字段",
        "",
        bullet(schema.get("AuditTrendSeries", [])),
        "",
        "## 4. TrendRegressionSignal 字段",
        "",
        bullet(schema.get("TrendRegressionSignal", [])),
        "",
        "## 5. NightlyTrendReport 字段",
        "",
        bullet(schema.get("NightlyTrendReport", [])),
        "",
        "## 6. NightlyTrendDesign 字段",
        "",
        bullet(schema.get("NightlyTrendDesign", [])),
        "",
        "## 7. metric catalog",
        "",
        "\n".join(metric_lines),
        "",
        "## 8. trend window specs",
        "",
        "\n".join(window_lines),
        "",
        "## 9. extraction design",
        "",
        f"- source: `{extraction.get('source')}`",
        "\n".join(extraction_lines),
        "",
        "## 10. regression detection rules",
        "",
        "\n".join(rule_lines),
        "",
        "## 11. implementation phases",
        "",
        "\n".join(phase_lines),
        "",
        "## 12. validation result",
        "",
        f"- valid: `{validation.get('valid')}`",
        f"- warnings: `{validation.get('warnings')}`",
        f"- errors: `{validation.get('errors')}`",
        f"- json_contract: `{json_path}`",
        "",
        "## 13. 测试结果",
        "",
        "待执行后更新：RootGuard / compile / pytest / regression suites。",
        "",
        "## 14. 是否写 audit JSONL / runtime / action queue",
        "",
        "否。本轮只写审计设计 JSON 与 Markdown，不写 audit_trail JSONL，不修改已有 JSONL，不写 runtime，不写 action queue。",
        "",
        "## 15. 是否调用 Feishu / network",
        "",
        "否。Feishu trend summary 仅作为未来 dry-run projection，不调用 webhook，不进行网络访问。",
        "",
        "## 16. 当前剩余断点",
        "",
        "- R241-12A 只完成 design-only contract，尚未执行 audit query trend projection。",
        "- 趋势点生成、序列计算、baseline 比较和 Feishu trend payload 将在后续阶段单独实现。",
        "- 当前 audit_trail 样本数量有限，真实 regression detection 需要 R241-12B dry-run projection 验证。",
        "",
        "## 17. 下一轮建议",
        "",
        "A. R241-12A 成功后，可进入 R241-12B Dry-run Trend Projection 实现：只读调用 audit query engine，生成趋势点与 regression projection，不写 audit JSONL/runtime/action queue。",
        "",
    ])


def generate_nightly_trend_report_design(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate the R241-12A design JSON and Markdown artifacts."""
    json_path = Path(output_path) if output_path else DEFAULT_CONTRACT_JSON
    if json_path.suffix.lower() != ".json":
        json_path = json_path.with_suffix(".json")
    md_path = json_path.with_suffix(".md") if output_path else DEFAULT_DESIGN_MD

    design = build_nightly_trend_report_design()
    validation = validate_trend_report_design(design)
    payload = {
        "design": design,
        "validation": validation,
        "generated_at": _now(),
        "warnings": list(design.get("warnings", [])) + list(validation.get("warnings", [])),
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown_report(design, validation, json_path), encoding="utf-8")

    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "design": design,
        "validation": validation,
        "warnings": payload["warnings"],
    }


__all__ = [
    "TrendMetricType",
    "TrendDirection",
    "TrendSeverity",
    "TrendWindow",
    "TrendReportStatus",
    "AuditTrendPoint",
    "AuditTrendSeries",
    "TrendRegressionSignal",
    "NightlyTrendReport",
    "NightlyTrendDesign",
    "build_trend_metric_catalog",
    "build_trend_window_spec",
    "design_trend_extraction_from_audit_query",
    "design_regression_detection_rules",
    "build_nightly_trend_report_design",
    "validate_trend_report_design",
    "generate_nightly_trend_report_design",
]
