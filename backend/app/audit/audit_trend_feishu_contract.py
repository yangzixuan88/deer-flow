"""Feishu/Lark trend summary dry-run design contract (R241-13A).

This module is design-only. It defines how a NightlyTrendReport plus CLI guard
result can later be projected into a Feishu/Lark card payload. It never sends
messages, never calls webhooks/network, never writes audit JSONL, and never
writes runtime/action queue state.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class FeishuTrendPayloadStatus(str, Enum):
    DESIGN_ONLY = "design_only"
    PROJECTION_ONLY = "projection_only"
    READY_FOR_DRY_RUN = "ready_for_dry_run"
    BLOCKED_NO_WEBHOOK_POLICY = "blocked_no_webhook_policy"
    BLOCKED_SENSITIVE_CONTENT = "blocked_sensitive_content"
    BLOCKED_LINE_COUNT_CHANGED = "blocked_line_count_changed"
    BLOCKED_RUNTIME_WRITE_RISK = "blocked_runtime_write_risk"
    UNKNOWN = "unknown"


class FeishuTrendCardSectionType(str, Enum):
    HEADLINE = "headline"
    TREND_OVERVIEW = "trend_overview"
    REGRESSION_SUMMARY = "regression_summary"
    GUARD_SUMMARY = "guard_summary"
    ARTIFACT_LINKS = "artifact_links"
    WARNINGS = "warnings"
    NEXT_STEP = "next_step"
    SAFETY_NOTICE = "safety_notice"
    UNKNOWN = "unknown"


class FeishuTrendSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class FeishuTrendSendPermission(str, Enum):
    FORBIDDEN = "forbidden"
    PROJECTION_ONLY = "projection_only"
    MANUAL_SEND_LATER = "manual_send_later"
    REQUIRES_WEBHOOK_POLICY = "requires_webhook_policy"
    REQUIRES_USER_CONFIRMATION = "requires_user_confirmation"
    UNKNOWN = "unknown"


@dataclass
class FeishuTrendCardSection:
    section_id: str
    section_type: str
    title: str
    content: str
    severity: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    source_metric_names: List[str] = field(default_factory=list)
    source_regression_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class FeishuTrendPayloadProjection:
    payload_id: str
    generated_at: str
    status: str
    title: str
    template: str
    source_trend_report_id: Optional[str]
    source_window: str
    source_record_count: int
    regression_count: int
    by_severity: Dict[str, int]
    sections: List[Dict[str, Any]]
    card_json: Dict[str, Any]
    send_permission: str
    send_allowed: bool = False
    webhook_required: bool = True
    no_webhook_call: bool = True
    no_runtime_write: bool = True
    no_action_queue_write: bool = True
    no_auto_fix: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class FeishuTrendValidationResult:
    validation_id: str
    valid: bool
    status: str
    send_allowed_is_false: bool
    no_webhook_call_is_true: bool
    no_runtime_write_is_true: bool
    no_action_queue_write_is_true: bool
    no_auto_fix_is_true: bool
    sensitive_content_detected: bool
    line_count_changed: bool
    blocked_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    validated_at: str = ""


class FeishuTrendPreviewFormat(str, Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    JSON = "json"


class FeishuTrendPreviewStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    NO_DATA = "no_data"
    VALIDATION_ERROR = "validation_error"


@dataclass
class FeishuTrendDryRunDesign:
    design_id: str
    generated_at: str
    input_sources: List[Dict[str, Any]]
    payload_schema: Dict[str, Any]
    card_section_schema: Dict[str, Any]
    validation_rules: List[Dict[str, Any]]
    blocked_send_paths: List[Dict[str, Any]]
    future_integration_points: List[Dict[str, Any]]
    implementation_phases: List[Dict[str, Any]]
    warnings: List[str] = field(default_factory=list)


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_CONTRACT_JSON = REPORT_DIR / "R241-13A_FEISHU_TREND_SUMMARY_DRYRUN_CONTRACT.json"
DEFAULT_DESIGN_MD = REPORT_DIR / "R241-13A_FEISHU_TREND_SUMMARY_DRYRUN_DESIGN.md"

_SENSITIVE_KEYS = {"webhook_url", "api_key", "token", "secret"}
_FORBIDDEN_TRUE_KEYS = {"runtime_write", "action_queue_write", "auto_fix_enabled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _enum_values(enum_cls: Any) -> List[str]:
    return [item.value for item in enum_cls]


def _schema_fields(cls: Any) -> List[str]:
    return list(getattr(cls, "__dataclass_fields__", {}).keys())


def _dedupe(values: List[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def build_feishu_trend_section_catalog() -> Dict[str, Any]:
    sections = [
        {
            "section_type": FeishuTrendCardSectionType.HEADLINE.value,
            "source_fields": ["trend_report.status", "trend_report.window", "regression_count"],
            "max_item_count": 1,
            "redaction_rule": "metadata_only_no_raw_records",
            "display purpose": "One-line trend health headline for operators.",
        },
        {
            "section_type": FeishuTrendCardSectionType.TREND_OVERVIEW.value,
            "source_fields": ["total_records_analyzed", "series_count", "by_severity"],
            "max_item_count": 6,
            "redaction_rule": "counts_only",
            "display purpose": "Show current trend window and aggregate counts.",
        },
        {
            "section_type": FeishuTrendCardSectionType.REGRESSION_SUMMARY.value,
            "source_fields": ["top_regressions", "metric_name", "severity", "current_value"],
            "max_item_count": 5,
            "redaction_rule": "no_evidence_payload_body",
            "display purpose": "Highlight strongest regression signals without raw evidence bodies.",
        },
        {
            "section_type": FeishuTrendCardSectionType.GUARD_SUMMARY.value,
            "source_fields": ["guard.audit_jsonl_unchanged", "guard.sensitive_output_detected", "guard.network_call_detected"],
            "max_item_count": 8,
            "redaction_rule": "booleans_only",
            "display purpose": "Show safety guard results for the dry-run command.",
        },
        {
            "section_type": FeishuTrendCardSectionType.ARTIFACT_LINKS.value,
            "source_fields": ["artifact_bundle.artifacts.output_path"],
            "max_item_count": 5,
            "redaction_rule": "report_artifact_paths_only",
            "display purpose": "Reference local report artifacts; never include webhook or runtime paths.",
        },
        {
            "section_type": FeishuTrendCardSectionType.WARNINGS.value,
            "source_fields": ["trend_report.warnings", "guard.warnings"],
            "max_item_count": 10,
            "redaction_rule": "truncate_and_redact_sensitive_markers",
            "display purpose": "Show non-fatal warnings that need operator review.",
        },
        {
            "section_type": FeishuTrendCardSectionType.NEXT_STEP.value,
            "source_fields": ["recommended_next_step"],
            "max_item_count": 3,
            "redaction_rule": "static_policy_text_only",
            "display purpose": "Suggest next dry-run or manual review step.",
        },
        {
            "section_type": FeishuTrendCardSectionType.SAFETY_NOTICE.value,
            "source_fields": ["send_allowed", "no_webhook_call", "no_auto_fix"],
            "max_item_count": 1,
            "redaction_rule": "policy_flags_only",
            "display purpose": "Make it explicit that the payload is projection-only.",
        },
    ]
    return {"sections": sections, "section_count": len(sections), "warnings": []}


def design_feishu_trend_payload_from_trend_report() -> Dict[str, Any]:
    mapping = {
        "input_sources": [
            {
                "module": "backend/app/audit/audit_trend_projection.py",
                "functions": ["summarize_trend_report", "format_trend_report"],
                "read_only": True,
            },
            {
                "module": "backend/app/audit/audit_trend_cli_guard.py",
                "functions": ["run_guarded_audit_trend_cli_projection", "validate_trend_cli_output_safety"],
                "read_only": True,
            },
            {
                "module": "backend/app/nightly/foundation_health_summary.py",
                "functions": ["build_feishu_card_payload_projection", "validate_feishu_payload_projection"],
                "reference_only": True,
            },
        ],
        "field_mapping": {
            "status": "trend_report.status",
            "window": "trend_report.window",
            "source_record_count": "trend_report.total_records_analyzed",
            "series_count": "summary.series_count",
            "regression_count": "summary.regression_count",
            "by_severity": "summary.by_severity",
            "top_regressions": "summary.top_regressions",
            "audit_jsonl_unchanged": "guard.audit_jsonl_unchanged",
            "sensitive_output_detected": "guard.sensitive_output_detected",
            "network_call_detected": "guard.network_call_detected",
            "artifact_paths": "artifact_bundle.artifacts.output_path",
        },
        "payload_policy": {
            "send_allowed": False,
            "send_permission": FeishuTrendSendPermission.PROJECTION_ONLY.value,
            "webhook_required": True,
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "default_status": FeishuTrendPayloadStatus.DESIGN_ONLY.value,
        },
        "card_json_shape": {
            "config": {"wide_screen_mode": True},
            "header": {"title": "Nightly Trend Summary", "template": "blue"},
            "elements": "projection_only_sections",
            "safety_notice": "projection_only_no_webhook_no_auto_fix",
        },
        "warnings": [],
    }
    return mapping


def build_feishu_trend_validation_rules() -> Dict[str, Any]:
    rules = [
        {"rule_id": "send_allowed_false", "condition": "send_allowed is false", "severity": "critical"},
        {"rule_id": "status_projection_only", "condition": "status in design_only/projection_only", "severity": "high"},
        {"rule_id": "webhook_url_forbidden", "condition": "webhook URL must not appear", "severity": "critical"},
        {"rule_id": "token_secret_api_key_forbidden", "condition": "token/secret/api_key must not appear", "severity": "critical"},
        {"rule_id": "no_webhook_call_true", "condition": "no_webhook_call is true", "severity": "critical"},
        {"rule_id": "no_runtime_write_true", "condition": "no_runtime_write is true", "severity": "critical"},
        {"rule_id": "no_action_queue_write_true", "condition": "no_action_queue_write is true", "severity": "critical"},
        {"rule_id": "no_auto_fix_true", "condition": "no_auto_fix is true", "severity": "critical"},
        {"rule_id": "line_count_changed_false", "condition": "line_count_changed is false", "severity": "high"},
        {"rule_id": "sensitive_output_detected_false", "condition": "sensitive_output_detected is false", "severity": "high"},
        {"rule_id": "card_json_serializable", "condition": "card_json can be JSON serialized", "severity": "medium"},
        {"rule_id": "artifact_links_report_only", "condition": "artifact links must be migration report artifacts only", "severity": "high"},
    ]
    return {"rules": rules, "rule_count": len(rules), "warnings": []}


def _blocked_send_paths() -> List[Dict[str, Any]]:
    return [
        {"path": "real_feishu_send", "blocked": True, "reason": "webhook_policy_not_designed"},
        {"path": "webhook_call", "blocked": True, "reason": "network_forbidden_in_r241_13a"},
        {"path": "scheduler_push", "blocked": True, "reason": "scheduler_integration_requires_separate_review"},
        {"path": "action_queue_write", "blocked": True, "reason": "trend_summary_must_not_create_actions"},
        {"path": "auto_fix", "blocked": True, "reason": "trend summary is diagnostic_only"},
    ]


def _future_integration_points() -> List[Dict[str, Any]]:
    return [
        {"phase": "payload_projection", "description": "Generate FeishuTrendPayloadProjection from trend report and guard result.", "send_enabled": False},
        {"phase": "cli_dry_run_preview", "description": "Add audit-trend-feishu preview command.", "send_enabled": False},
        {"phase": "manual_send_policy", "description": "Design webhook policy and user confirmation gate.", "send_enabled": False},
        {"phase": "manual_send_implementation", "description": "Optional later manual send implementation, disabled by default.", "send_enabled": False},
        {"phase": "scheduler_review", "description": "Separate review before any scheduler integration.", "send_enabled": False},
    ]


def _implementation_phases() -> List[Dict[str, Any]]:
    return [
        {"phase": "Phase 1", "name": "Design-only Contract", "scope": "Current R241-13A schema/mapping/validation only.", "writes_runtime": False, "sends_feishu": False},
        {"phase": "Phase 2", "name": "Payload Projection", "scope": "Build FeishuTrendPayloadProjection from trend report plus guard.", "writes_runtime": False, "sends_feishu": False},
        {"phase": "Phase 3", "name": "CLI Dry-run Preview", "scope": "Add audit-trend-feishu CLI preview output.", "writes_runtime": False, "sends_feishu": False},
        {"phase": "Phase 4", "name": "Manual Send Policy Design", "scope": "Define webhook policy, user confirmation, redaction review.", "writes_runtime": False, "sends_feishu": False},
        {"phase": "Phase 5", "name": "Manual Send Implementation", "scope": "Separate implementation, disabled by default.", "writes_runtime": False, "sends_feishu": False},
        {"phase": "Phase 6", "name": "Scheduler Integration Review", "scope": "Separate review before any scheduler/watchdog integration.", "writes_runtime": False, "sends_feishu": False},
    ]


def _payload_schema() -> Dict[str, Any]:
    return {
        "dataclass": "FeishuTrendPayloadProjection",
        "fields": _schema_fields(FeishuTrendPayloadProjection),
        "status_values": _enum_values(FeishuTrendPayloadStatus),
        "send_permission_values": _enum_values(FeishuTrendSendPermission),
    }


def _section_schema() -> Dict[str, Any]:
    return {
        "dataclass": "FeishuTrendCardSection",
        "fields": _schema_fields(FeishuTrendCardSection),
        "section_type_values": _enum_values(FeishuTrendCardSectionType),
        "severity_values": _enum_values(FeishuTrendSeverity),
    }


def build_feishu_trend_dryrun_design(root: Optional[str] = None) -> Dict[str, Any]:
    warnings: List[str] = []
    try:
        from app.audit.audit_trend_projection import summarize_trend_report, format_trend_report  # noqa: F401
        from app.audit.audit_trend_cli_guard import run_guarded_audit_trend_cli_projection, validate_trend_cli_output_safety  # noqa: F401
        from app.nightly.foundation_health_summary import build_feishu_card_payload_projection, validate_feishu_payload_projection  # noqa: F401
    except Exception as exc:
        warnings.append(f"reference_import_warning:{exc}")
    design = FeishuTrendDryRunDesign(
        design_id=_new_id("feishu_trend_design"),
        generated_at=_now(),
        input_sources=design_feishu_trend_payload_from_trend_report()["input_sources"],
        payload_schema=_payload_schema(),
        card_section_schema=_section_schema(),
        validation_rules=build_feishu_trend_validation_rules()["rules"],
        blocked_send_paths=_blocked_send_paths(),
        future_integration_points=_future_integration_points(),
        implementation_phases=_implementation_phases(),
        warnings=warnings,
    )
    result = asdict(design)
    result["section_catalog"] = build_feishu_trend_section_catalog()["sections"]
    result["payload_mapping"] = design_feishu_trend_payload_from_trend_report()
    result["root"] = str(Path(root).resolve()) if root else str(ROOT)
    return result


def validate_feishu_trend_dryrun_design(design: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    text = json.dumps(design, ensure_ascii=False).lower()
    if "send_enabled\": true" in text or "sends_feishu\": true" in text or "real_webhook_send_enabled" in text:
        errors.append("real_webhook_send_forbidden")
    if "http://" in text or "https://" in text:
        errors.append("webhook_or_network_url_forbidden")
    sensitive_keys = _find_sensitive_keys(design)
    for marker in sensitive_keys:
        errors.append(f"sensitive_marker_forbidden:{marker}")
    for marker in _find_forbidden_true_keys(design):
        errors.append(f"forbidden_runtime_or_autofix_marker:{marker}")
    if not design.get("validation_rules"):
        errors.append("validation_rules_empty")
    if not design.get("section_catalog"):
        errors.append("section_catalog_empty")
    phases = design.get("implementation_phases") or []
    phase_names = {str(item.get("phase")) for item in phases}
    for idx in range(1, 7):
        if f"Phase {idx}" not in phase_names:
            errors.append(f"missing_phase_{idx}")
    return {
        "valid": not errors,
        "warnings": _dedupe(warnings),
        "errors": _dedupe(errors),
    }


def _find_sensitive_keys(value: Any) -> List[str]:
    found: List[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lower = str(key).lower()
            if lower in _SENSITIVE_KEYS:
                found.append(lower)
            found.extend(_find_sensitive_keys(child))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_sensitive_keys(item))
    return _dedupe(found)


def _find_forbidden_true_keys(value: Any) -> List[str]:
    found: List[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lower = str(key).lower()
            if lower in _FORBIDDEN_TRUE_KEYS and child is True:
                found.append(lower)
            found.extend(_find_forbidden_true_keys(child))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_forbidden_true_keys(item))
    return _dedupe(found)


def _render_markdown(design: Dict[str, Any], validation: Dict[str, Any]) -> str:
    sections = design.get("section_catalog", [])
    rules = design.get("validation_rules", [])
    phases = design.get("implementation_phases", [])
    lines = [
        "# R241-13A Feishu Trend Summary Dry-run Design",
        "",
        "This is design-only. It does not send Feishu/Lark messages, does not call webhooks/network, does not write audit JSONL/runtime/action queue, and does not execute auto-fix.",
        "",
        "## Data Structures",
        "",
        f"- FeishuTrendCardSection fields: `{_schema_fields(FeishuTrendCardSection)}`",
        f"- FeishuTrendPayloadProjection fields: `{_schema_fields(FeishuTrendPayloadProjection)}`",
        f"- FeishuTrendValidationResult fields: `{_schema_fields(FeishuTrendValidationResult)}`",
        f"- FeishuTrendDryRunDesign fields: `{_schema_fields(FeishuTrendDryRunDesign)}`",
        "",
        "## Section Catalog",
    ]
    lines.extend(f"- `{item.get('section_type')}`: {item.get('display purpose')}" for item in sections)
    lines.extend(["", "## Payload Mapping"])
    mapping = design.get("payload_mapping", {}).get("field_mapping", {})
    lines.extend(f"- `{key}` <- `{value}`" for key, value in mapping.items())
    lines.extend(["", "## Validation Rules"])
    lines.extend(f"- `{item.get('rule_id')}`: {item.get('condition')}" for item in rules)
    lines.extend(["", "## Blocked Send Paths"])
    lines.extend(f"- `{item.get('path')}`: {item.get('reason')}" for item in design.get("blocked_send_paths", []))
    lines.extend(["", "## Implementation Phases"])
    lines.extend(f"- `{item.get('phase')}` {item.get('name')}: {item.get('scope')}" for item in phases)
    lines.extend(["", "## Validation Result", f"- valid: `{validation.get('valid')}`", f"- errors: `{validation.get('errors')}`"])
    return "\n".join(lines) + "\n"


def generate_feishu_trend_dryrun_design(output_path: Optional[str] = None) -> Dict[str, Any]:
    json_path = Path(output_path) if output_path else DEFAULT_CONTRACT_JSON
    md_path = json_path.with_name("R241-13A_FEISHU_TREND_SUMMARY_DRYRUN_DESIGN.md")
    design = build_feishu_trend_dryrun_design(root=str(ROOT))
    validation = validate_feishu_trend_dryrun_design(design)
    payload = {
        "design": design,
        "validation": validation,
        "generated_at": _now(),
        "warnings": _dedupe(design.get("warnings", []) + validation.get("warnings", [])),
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(design, validation), encoding="utf-8")
    return {
        "output_path": str(json_path),
        "markdown_path": str(md_path),
        **payload,
    }


__all__ = [
    "FeishuTrendPayloadStatus",
    "FeishuTrendCardSectionType",
    "FeishuTrendSeverity",
    "FeishuTrendSendPermission",
    "FeishuTrendCardSection",
    "FeishuTrendPayloadProjection",
    "FeishuTrendValidationResult",
    "FeishuTrendDryRunDesign",
    "build_feishu_trend_section_catalog",
    "design_feishu_trend_payload_from_trend_report",
    "build_feishu_trend_validation_rules",
    "build_feishu_trend_dryrun_design",
    "validate_feishu_trend_dryrun_design",
    "generate_feishu_trend_dryrun_design",
]
