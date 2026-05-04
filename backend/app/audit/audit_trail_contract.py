"""Append-only Audit Trail Contract.

This module defines the schema, redaction policy, and projection helpers for an
append-only audit trail that records diagnostic CLI run results. It is purely a
design/contract module — it does NOT write files, call webhooks, or modify runtime.

Phase 1 (R241-11A): Design-only contract and schema definitions.
Phase 2 (R241-11B): Dry-run audit record projection from CLI results.
Phase 3 (R241-11C): Append-only JSONL writer (writes to audit_trail/*.jsonl only).
Phase 4 (R241-11D): Audit query helper (reads JSONL, filters by command/status/date).
Phase 5 (R241-11E): Nightly trend report (aggregates historical audit records).
Phase 6 (R241-11F): Feishu audit summary dry-run (generates projection, no push).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────


class AuditEventType(str, Enum):
    DIAGNOSTIC_CLI_RUN = "diagnostic_cli_run"
    DIAGNOSTIC_DOMAIN_RESULT = "diagnostic_domain_result"
    NIGHTLY_HEALTH_REVIEW = "nightly_health_review"
    FEISHU_SUMMARY_DRY_RUN = "feishu_summary_dry_run"
    TOOL_RUNTIME_PROJECTION = "tool_runtime_projection"
    MODE_CALLGRAPH_PROJECTION = "mode_callgraph_projection"
    FOUNDATION_ACTION_CANDIDATE = "foundation_action_candidate"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_ERROR = "system_error"
    UNKNOWN = "unknown"


class AuditWriteMode(str, Enum):
    DESIGN_ONLY = "design_only"  # R241-11A default
    DRY_RUN = "dry_run"
    APPEND_ONLY = "append_only"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class AuditRetentionClass(str, Enum):
    SHORT_TERM_DEBUG = "short_term_debug"
    MEDIUM_TERM_OPERATIONAL = "medium_term_operational"
    LONG_TERM_GOVERNANCE = "long_term_governance"
    PROTECTED_TRACE = "protected_trace"
    UNKNOWN = "unknown"


class AuditSensitivityLevel(str, Enum):
    PUBLIC_METADATA = "public_metadata"
    INTERNAL_METADATA = "internal_metadata"
    SENSITIVE_PATH_METADATA = "sensitive_path_metadata"
    SECRET_OR_TOKEN = "secret_or_token"
    USER_PRIVATE_CONTENT = "user_private_content"
    UNKNOWN = "unknown"


class AuditQueryDimension(str, Enum):
    COMMAND = "command"
    STATUS = "status"
    DOMAIN = "domain"
    SEVERITY = "severity"
    DATE = "date"
    CONTEXT_ID = "context_id"
    REQUEST_ID = "request_id"
    MODE_SESSION_ID = "mode_session_id"
    TOOL_EXECUTION_ID = "tool_execution_id"
    WARNING_TYPE = "warning_type"
    ERROR_TYPE = "error_type"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Core Dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AuditTrailRecord:
    audit_record_id: str
    event_type: str
    write_mode: str
    source_system: str
    source_command: Optional[str] = None
    status: str = "unknown"
    root: str = ""
    generated_at: str = ""
    observed_at: str = ""
    context_id: Optional[str] = None
    request_id: Optional[str] = None
    mode_session_id: Optional[str] = None
    mode_invocation_id: Optional[str] = None
    tool_execution_id: Optional[str] = None
    review_id: Optional[str] = None
    payload_ref: Optional[str] = None
    payload_hash: Optional[str] = None
    summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    sensitivity_level: str = AuditSensitivityLevel.UNKNOWN.value
    retention_class: str = AuditRetentionClass.MEDIUM_TERM_OPERATIONAL.value
    redaction_applied: bool = False
    redaction_warnings: List[str] = field(default_factory=list)
    append_only_target: Optional[str] = None
    schema_version: str = "1.0"


@dataclass
class AuditTrailTargetSpec:
    target_id: str
    target_path: str
    format: str = "jsonl"
    append_only: bool = True
    allow_overwrite: bool = False
    rotation_policy: str = "daily"
    max_file_size_mb: int = 10
    retention_class: str = AuditRetentionClass.MEDIUM_TERM_OPERATIONAL.value
    requires_root_guard: bool = True
    backup_required: bool = False
    corruption_recovery_strategy: str = "recreate"
    warnings: List[str] = field(default_factory=list)


@dataclass
class AuditRedactionPolicy:
    policy_id: str = "default"
    redact_webhook_urls: bool = True
    redact_api_keys: bool = True
    redact_tokens: bool = True
    redact_file_contents: bool = True
    redact_prompt_body: bool = True
    redact_memory_body: bool = True
    redact_rtcm_artifact_body: bool = True
    allow_path_metadata: bool = True
    allow_hashes: bool = True
    allow_counts: bool = True
    allow_first_line_preview: bool = True
    warnings: List[str] = field(default_factory=list)


@dataclass
class AuditQuerySpec:
    query_id: str
    dimensions: List[str]
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 100
    order_by: str = "generated_at"
    supported: bool = True
    blocked_filters: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class AppendOnlyAuditTrailDesign:
    design_id: str
    generated_at: str
    write_mode: str
    target_specs: List[Dict[str, Any]]
    record_schema: Dict[str, Any]
    redaction_policy: Dict[str, Any]
    query_specs: List[Dict[str, Any]]
    integration_points: List[str]
    blocked_write_paths: List[str]
    implementation_phases: List[Dict[str, Any]]
    risks: List[str]
    warnings: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

SENSITIVE_KEY_PATTERNS = [
    re.compile(r"(webhook[_\s]*(url|endpoint))", re.IGNORECASE),
    re.compile(r"(api[_\s]*(key|token|secret))", re.IGNORECASE),
    re.compile(r"(secret|token|password|credential)", re.IGNORECASE),
    re.compile(r"(bearer|auth)", re.IGNORECASE),
]
SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"^https?://[^\s]*webhook[^\s]*", re.IGNORECASE),
    re.compile(r"^https?://[^\s]*hook[^\s]*", re.IGNORECASE),
    re.compile(r"(sk|pk|rk|ak)[-_][a-zA-Z0-9]{10,}", re.IGNORECASE),
    re.compile(r"(bearer|token)['\"]?\\s*[:=]\\s*['\"]?[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
]
PRIVATE_BODY_KEYS = [
    "body", "content", "raw_content", "full_content", "text_content",
    "artifact_body", "memory_body", "prompt_body", "rtcm_body",
    "session_body", "dossier_body", "final_report_body",
]
SENSITIVE_PATH_KEYS = [
    "source_path", "file_path", "artifact_path", "memory_path",
    "checkpoint_path", "registry_path", "runtime_path",
]


def _make_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return f"{prefix}_{abs(hash(raw)) % 10_000_000_000:010d}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_payload(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


# ─────────────────────────────────────────────────────────────────────────────
# Sensitivity Classification
# ─────────────────────────────────────────────────────────────────────────────


def classify_audit_sensitivity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Classify sensitivity level of a payload without modifying it."""
    warnings: List[str] = []
    detected_keys: List[str] = []
    level = AuditSensitivityLevel.PUBLIC_METADATA.value

    for key in payload:
        key_lower = key.lower()
        value_str = str(payload[key]) if payload[key] is not None else ""

        for pattern in SENSITIVE_KEY_PATTERNS:
            if pattern.search(key_lower):
                detected_keys.append(key)
                if level != AuditSensitivityLevel.SECRET_OR_TOKEN.value:
                    level = AuditSensitivityLevel.SECRET_OR_TOKEN.value

        for pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.match(value_str):
                detected_keys.append(key)
                level = AuditSensitivityLevel.SECRET_OR_TOKEN.value

        if key_lower in [k.lower() for k in PRIVATE_BODY_KEYS]:
            detected_keys.append(key)
            level = AuditSensitivityLevel.USER_PRIVATE_CONTENT.value

        if key_lower in [k.lower() for k in SENSITIVE_PATH_KEYS]:
            if level not in (AuditSensitivityLevel.SECRET_OR_TOKEN.value, AuditSensitivityLevel.USER_PRIVATE_CONTENT.value):
                level = AuditSensitivityLevel.SENSITIVE_PATH_METADATA.value

        if any(marker in key_lower for marker in ["_hash", "_sha", "_count", "_total"]):
            if level == AuditSensitivityLevel.PUBLIC_METADATA.value:
                level = AuditSensitivityLevel.INTERNAL_METADATA.value

    if not detected_keys:
        warnings.append("no_sensitive_keys_detected_defaulting_to_public_metadata")

    return {
        "sensitivity_level": level,
        "detected_sensitive_keys": list(dict.fromkeys(detected_keys)),
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Redaction Policy
# ─────────────────────────────────────────────────────────────────────────────


def build_audit_redaction_policy() -> Dict[str, Any]:
    """Return the default redaction policy (read-only, does not modify anything)."""
    return asdict(
        AuditRedactionPolicy(
            policy_id="default",
            redact_webhook_urls=True,
            redact_api_keys=True,
            redact_tokens=True,
            redact_file_contents=True,
            redact_prompt_body=True,
            redact_memory_body=True,
            redact_rtcm_artifact_body=True,
            allow_path_metadata=True,
            allow_hashes=True,
            allow_counts=True,
            allow_first_line_preview=True,
            warnings=["policy_is_read_only_does_not_redact_automatically"],
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Redaction
# ─────────────────────────────────────────────────────────────────────────────


_REDACTED_SECRET = "[REDACTED]"
_REDACTED_CONTENT = "[CONTENT_REDACTED]"


def _is_private_body_key(key: str) -> bool:
    return any(k.lower() == key.lower() for k in PRIVATE_BODY_KEYS)


def _is_sensitive_path_key(key: str) -> bool:
    return any(k.lower() == key.lower() for k in SENSITIVE_PATH_KEYS)


def _match_sensitive_value(value: str) -> bool:
    if not isinstance(value, str):
        return False
    for pattern in SENSITIVE_VALUE_PATTERNS:
        if pattern.match(value):
            return True
    return False


def redact_audit_payload(payload: Dict[str, Any], policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a redacted copy of the payload without modifying the original."""
    policy = policy or {}
    result: Dict[str, Any] = {}

    for key, value in payload.items():
        if value is None:
            result[key] = None
            continue

        key_lower = key.lower()
        value_str = str(value)

        # Secret/token/webhook URL redaction
        if policy.get("redact_tokens", True) or policy.get("redact_api_keys", True) or policy.get("redact_webhook_urls", True):
            if _match_sensitive_value(value_str):
                result[key] = _REDACTED_SECRET
                continue
            for pattern in SENSITIVE_KEY_PATTERNS:
                if pattern.search(key_lower):
                    result[key] = _REDACTED_SECRET
                    continue

        # Private body redaction
        if policy.get("redact_prompt_body", True) or policy.get("redact_memory_body", True) or policy.get("redact_rtcm_artifact_body", True):
            if _is_private_body_key(key):
                result[key] = _REDACTED_CONTENT
                continue

        # Sensitive path — keep path but flag it
        if _is_sensitive_path_key(key):
            if isinstance(value, str) and policy.get("allow_path_metadata", True):
                result[key] = value  # keep path metadata
            else:
                result[key] = _REDACTED_CONTENT
            continue

        # Recurse into dicts
        if isinstance(value, dict):
            result[key] = redact_audit_payload(value, policy)
        elif isinstance(value, list):
            result[key] = [
                redact_audit_payload(item, policy) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Audit Record Projection
# ─────────────────────────────────────────────────────────────────────────────


def create_audit_record_from_diagnostic_result(
    result: Dict[str, Any],
    event_type: str = AuditEventType.DIAGNOSTIC_CLI_RUN.value,
) -> Dict[str, Any]:
    """Project a DiagnosticRunResult dict into an AuditTrailRecord dict (read-only, no file writes)."""
    write_mode = AuditWriteMode.DESIGN_ONLY.value
    summary = result.get("summary") or {}
    payload = result.get("payload") or {}
    warnings = result.get("warnings") or []
    errors = result.get("errors") or []

    # Classify sensitivity before redaction
    sensitivity = classify_audit_sensitivity(payload)
    redacted_payload = redact_audit_payload(payload)
    redaction_applied = sensitivity["sensitivity_level"] != AuditSensitivityLevel.PUBLIC_METADATA.value

    record = AuditTrailRecord(
        audit_record_id=_make_id("audit", event_type, result.get("command"), _now()),
        event_type=event_type,
        write_mode=write_mode,
        source_system="foundation_diagnostics_cli",
        source_command=result.get("command"),
        status=result.get("status") or "unknown",
        root=result.get("root") or "",
        generated_at=result.get("generated_at") or _now(),
        observed_at=_now(),
        summary=summary,
        warnings=warnings,
        errors=errors,
        sensitivity_level=sensitivity["sensitivity_level"],
        retention_class=AuditRetentionClass.MEDIUM_TERM_OPERATIONAL.value,
        redaction_applied=redaction_applied,
        redaction_warnings=sensitivity.get("warnings", []),
        payload_hash=_hash_payload(redacted_payload),
        append_only_target=None,  # design_only: no file written
        schema_version="1.0",
    )
    return asdict(record)


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_audit_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Static validation of an AuditTrailRecord dict (read-only)."""
    warnings: List[str] = []
    errors: List[str] = []
    valid = True

    if not record.get("audit_record_id"):
        errors.append("audit_record_id_missing")
        valid = False
    if not record.get("event_type"):
        errors.append("event_type_missing")
        valid = False
    if record.get("write_mode") != AuditWriteMode.DESIGN_ONLY.value:
        if record.get("write_mode") == AuditWriteMode.UNKNOWN.value:
            warnings.append("write_mode_unknown")
        else:
            warnings.append(f"write_mode_is_{record.get('write_mode')}_not_design_only")
    if not record.get("schema_version"):
        errors.append("schema_version_missing")
        valid = False
    if not record.get("payload_hash"):
        errors.append("payload_hash_missing")
        valid = False

    payload = record.get("payload") or {}
    for key, value in payload.items():
        if value is None:
            continue
        value_str = str(value)
        if _match_sensitive_value(value_str):
            errors.append(f"raw_sensitive_value_detected_in_payload:{key}")
            valid = False
        if _is_private_body_key(key) and isinstance(value, str) and len(value) > 100:
            errors.append(f"unredacted_private_body_key:{key}")
            valid = False

    if not valid and not errors:
        errors.append("record_invalid")

    return {"valid": valid, "warnings": warnings, "errors": errors}


# ─────────────────────────────────────────────────────────────────────────────
# Target Specs
# ─────────────────────────────────────────────────────────────────────────────


def build_audit_target_specs(root: Optional[str] = None) -> Dict[str, Any]:
    """Generate AuditTrailTargetSpec list (design only, no files created)."""
    base = Path(root) if root else Path(__file__).resolve().parents[4]
    audit_dir = base / "migration_reports" / "foundation_audit" / "audit_trail"

    specs = [
        AuditTrailTargetSpec(
            target_id="foundation_diagnostic_runs",
            target_path=str(audit_dir / "foundation_diagnostic_runs.jsonl"),
            format="jsonl",
            append_only=True,
            allow_overwrite=False,
            rotation_policy="daily",
            max_file_size_mb=10,
            retention_class=AuditRetentionClass.MEDIUM_TERM_OPERATIONAL.value,
            requires_root_guard=True,
            backup_required=False,
            corruption_recovery_strategy="recreate",
            warnings=["design_only_no_file_created"],
        ),
        AuditTrailTargetSpec(
            target_id="nightly_health_reviews",
            target_path=str(audit_dir / "nightly_health_reviews.jsonl"),
            format="jsonl",
            append_only=True,
            allow_overwrite=False,
            rotation_policy="daily",
            max_file_size_mb=10,
            retention_class=AuditRetentionClass.LONG_TERM_GOVERNANCE.value,
            requires_root_guard=True,
            backup_required=False,
            corruption_recovery_strategy="recreate",
            warnings=["design_only_no_file_created"],
        ),
        AuditTrailTargetSpec(
            target_id="feishu_summary_dryruns",
            target_path=str(audit_dir / "feishu_summary_dryruns.jsonl"),
            format="jsonl",
            append_only=True,
            allow_overwrite=False,
            rotation_policy="daily",
            max_file_size_mb=5,
            retention_class=AuditRetentionClass.SHORT_TERM_DEBUG.value,
            requires_root_guard=True,
            backup_required=False,
            corruption_recovery_strategy="recreate",
            warnings=["design_only_no_file_created"],
        ),
        AuditTrailTargetSpec(
            target_id="tool_runtime_projections",
            target_path=str(audit_dir / "tool_runtime_projections.jsonl"),
            format="jsonl",
            append_only=True,
            allow_overwrite=False,
            rotation_policy="weekly",
            max_file_size_mb=10,
            retention_class=AuditRetentionClass.MEDIUM_TERM_OPERATIONAL.value,
            requires_root_guard=True,
            backup_required=False,
            corruption_recovery_strategy="recreate",
            warnings=["design_only_no_file_created"],
        ),
        AuditTrailTargetSpec(
            target_id="mode_callgraph_projections",
            target_path=str(audit_dir / "mode_callgraph_projections.jsonl"),
            format="jsonl",
            append_only=True,
            allow_overwrite=False,
            rotation_policy="weekly",
            max_file_size_mb=10,
            retention_class=AuditRetentionClass.MEDIUM_TERM_OPERATIONAL.value,
            requires_root_guard=True,
            backup_required=False,
            corruption_recovery_strategy="recreate",
            warnings=["design_only_no_file_created"],
        ),
    ]

    return {
        "design_id": _make_id("audit_targets", _now()),
        "generated_at": _now(),
        "target_specs": [asdict(s) for s in specs],
        "warnings": ["all_targets_append_only_allow_overwrite_false_design_only"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Query Specs
# ─────────────────────────────────────────────────────────────────────────────


def build_audit_query_specs() -> Dict[str, Any]:
    """Generate AuditQuerySpec list for read-only query definitions."""
    specs = [
        AuditQuerySpec(
            query_id="by_command",
            dimensions=[AuditQueryDimension.COMMAND.value],
            limit=100,
            order_by="generated_at",
            supported=True,
            blocked_filters=[],
        ),
        AuditQuerySpec(
            query_id="by_status",
            dimensions=[AuditQueryDimension.STATUS.value],
            limit=100,
            order_by="generated_at",
            supported=True,
            blocked_filters=[],
        ),
        AuditQuerySpec(
            query_id="by_date_range",
            dimensions=[AuditQueryDimension.DATE.value],
            filters={"gte": "2024-01-01"},
            limit=1000,
            order_by="generated_at",
            supported=True,
            blocked_filters=[],
        ),
        AuditQuerySpec(
            query_id="by_warning_type",
            dimensions=[AuditQueryDimension.WARNING_TYPE.value],
            limit=200,
            order_by="generated_at",
            supported=True,
            blocked_filters=[],
        ),
        AuditQuerySpec(
            query_id="by_error_type",
            dimensions=[AuditQueryDimension.ERROR_TYPE.value],
            limit=200,
            order_by="generated_at",
            supported=True,
            blocked_filters=[],
        ),
        AuditQuerySpec(
            query_id="by_context_id",
            dimensions=[AuditQueryDimension.CONTEXT_ID.value],
            limit=100,
            order_by="generated_at",
            supported=True,
            blocked_filters=[],
        ),
        AuditQuerySpec(
            query_id="by_request_id",
            dimensions=[AuditQueryDimension.REQUEST_ID.value],
            limit=100,
            order_by="generated_at",
            supported=True,
            blocked_filters=[],
        ),
        AuditQuerySpec(
            query_id="by_severity",
            dimensions=[AuditQueryDimension.SEVERITY.value],
            limit=200,
            order_by="generated_at",
            supported=True,
            blocked_filters=[],
        ),
        AuditQuerySpec(
            query_id="by_domain",
            dimensions=[AuditQueryDimension.DOMAIN.value],
            limit=200,
            order_by="generated_at",
            supported=True,
            blocked_filters=[],
        ),
    ]

    return {
        "query_specs": [asdict(s) for s in specs],
        "warnings": ["query_specs_are_design_only_no_index_implemented"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Design Aggregation
# ─────────────────────────────────────────────────────────────────────────────


def build_append_only_audit_trail_design(root: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate all design components into an AppendOnlyAuditTrailDesign dict."""
    targets = build_audit_target_specs(root)
    queries = build_audit_query_specs()
    redaction = build_audit_redaction_policy()

    record_schema = {
        "AuditTrailRecord": {
            "fields": [
                {"name": "audit_record_id", "type": "str", "required": True},
                {"name": "event_type", "type": "str", "required": True},
                {"name": "write_mode", "type": "str", "required": True},
                {"name": "source_system", "type": "str", "required": True},
                {"name": "source_command", "type": "str", "required": False},
                {"name": "status", "type": "str", "required": True},
                {"name": "root", "type": "str", "required": True},
                {"name": "generated_at", "type": "str", "required": True},
                {"name": "observed_at", "type": "str", "required": True},
                {"name": "context_id", "type": "str", "required": False},
                {"name": "request_id", "type": "str", "required": False},
                {"name": "mode_session_id", "type": "str", "required": False},
                {"name": "mode_invocation_id", "type": "str", "required": False},
                {"name": "tool_execution_id", "type": "str", "required": False},
                {"name": "review_id", "type": "str", "required": False},
                {"name": "payload_ref", "type": "str", "required": False},
                {"name": "payload_hash", "type": "str", "required": True},
                {"name": "summary", "type": "dict", "required": True},
                {"name": "warnings", "type": "list", "required": True},
                {"name": "errors", "type": "list", "required": True},
                {"name": "sensitivity_level", "type": "str", "required": True},
                {"name": "retention_class", "type": "str", "required": True},
                {"name": "redaction_applied", "type": "bool", "required": True},
                {"name": "redaction_warnings", "type": "list", "required": False},
                {"name": "append_only_target", "type": "str", "required": False},
                {"name": "schema_version", "type": "str", "required": True},
            ],
            "schema_version": "1.0",
        }
    }

    phases = [
        {
            "phase": 1,
            "name": "Design-only Contract",
            "description": "Define schema, redaction policy, target specs, query specs. R241-11A.",
            "deliverables": ["audit_trail_contract.py", "test_audit_trail_contract.py", "design report"],
            "writes_files": False,
            "writes_runtime": False,
        },
        {
            "phase": 2,
            "name": "Dry-run Audit Record Projection",
            "description": "create_audit_record_from_diagnostic_result() generates records without writing files.",
            "deliverables": ["CLI integration in read_only_diagnostics_cli.py"],
            "writes_files": False,
            "writes_runtime": False,
        },
        {
            "phase": 3,
            "name": "Append-only JSONL Writer",
            "description": "Write audit records to audit_trail/*.jsonl only. No overwrite. No other paths.",
            "deliverables": ["jsonl_writer.py", "rotation_policy"],
            "writes_files": True,
            "writes_runtime": False,
        },
        {
            "phase": 4,
            "name": "Audit Query Helper",
            "description": "Read JSONL, filter by command/status/date/warning/error. No full-text search.",
            "deliverables": ["query_helper.py"],
            "writes_files": False,
            "writes_runtime": False,
        },
        {
            "phase": 5,
            "name": "Nightly Trend Report",
            "description": "Aggregate historical audit records into nightly/daily/weekly trend summary.",
            "deliverables": ["trend_report.py"],
            "writes_files": False,
            "writes_runtime": False,
        },
        {
            "phase": 6,
            "name": "Feishu Audit Summary Dry-run",
            "description": "Project Feishu audit summary from audit trail, generate card without push.",
            "deliverables": ["feishu_audit_summary_projection.py"],
            "writes_files": False,
            "writes_runtime": False,
        },
    ]

    risks = [
        "Append-only enforcement relies on filesystem permissions, not DB constraints.",
        "Redaction is best-effort; keys must follow naming conventions to be detected.",
        "JSONL rotation by size (not time) may cause record fragmentation.",
        "Payload hash does not include schema_version — schema evolution may invalidate hashing.",
        "No query indexing — full scan on large files.",
    ]

    design = AppendOnlyAuditTrailDesign(
        design_id=_make_id("audit_design", "append_only", _now()),
        generated_at=_now(),
        write_mode=AuditWriteMode.DESIGN_ONLY.value,
        target_specs=targets.get("target_specs", []),
        record_schema=record_schema,
        redaction_policy=redaction,
        query_specs=queries.get("query_specs", []),
        integration_points=[
            "foundation_diagnostics_cli.run_all_diagnostics()",
            "foundation_health_review.aggregate_nightly_foundation_health()",
            "foundation_health_summary.build_feishu_card_payload_projection()",
            "tool_runtime_projection.aggregate_tool_runtime_projection()",
            "mode_orchestration_contract.project_mode_callgraph()",
        ],
        blocked_write_paths=[
            str(Path(root or ".").parent / "runtime"),
            str(Path(root or ".").parent / "governance"),
            str(Path(root or ".").parent / "action_queue"),
            "memory.json",
            "qdrant",
            "sqlite",
        ],
        implementation_phases=phases,
        risks=risks,
        warnings=["design_only_phase_1_no_files_written"],
    )
    return asdict(design)


# ─────────────────────────────────────────────────────────────────────────────
# Design Report Generator
# ─────────────────────────────────────────────────────────────────────────────


REPORT_DIR = Path(__file__).resolve().parents[4] / "migration_reports" / "foundation_audit"


def generate_append_only_audit_trail_design(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate the design report and JSON contract (design only, no runtime writes)."""
    design = build_append_only_audit_trail_design()

    json_path = Path(output_path) if output_path else REPORT_DIR / "R241-11A_APPEND_ONLY_AUDIT_TRAIL_CONTRACT.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(design, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {**design, "json_output_path": str(json_path)}
