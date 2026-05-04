"""Append-only JSONL Audit Trail Writer (R241-11C Phase 3).

This module appends AuditTrailRecord entries to JSONL files under
migration_reports/foundation_audit/audit_trail/ following the append-only
contract defined in audit_trail_contract.py.

SECURITY INVARIANTS:
- Files are ONLY opened in append ("a") mode — never write ("w") or truncate ("w+")
- Path validation rejects any path containing "..", or pointing outside audit_trail/
- Dry-run mode (default) performs all validation but writes no bytes
- No network calls, no webhook calls, no runtime writes
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class AuditAppendStatus(str, Enum):
    APPENDED = "appended"
    SKIPPED_DRY_RUN = "skipped_dry_run"
    BLOCKED_INVALID_RECORD = "blocked_invalid_record"
    BLOCKED_INVALID_TARGET = "blocked_invalid_target"
    BLOCKED_OVERWRITE_RISK = "blocked_overwrite_risk"
    FAILED = "failed"


class AuditWriterMode(str, Enum):
    DRY_RUN = "dry_run"
    APPEND_ONLY = "append_only"
    BLOCKED = "blocked"


# ─────────────────────────────────────────────────────────────────────────────
# AuditAppendResult
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AuditAppendResult:
    append_result_id: str
    status: AuditAppendStatus
    target_id: str
    target_path: str
    record_id: Optional[str]
    event_type: Optional[str]
    write_mode: str
    bytes_written: int = 0
    line_count_before: Optional[int] = None
    line_count_after: Optional[int] = None
    payload_hash: Optional[str] = None
    validation_valid: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    appended_at: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


_AUDIT_TRAIL_REL = Path("migration_reports/foundation_audit/audit_trail")
_RESTRICTED_PATHS = frozenset({
    "memory.json",
    "governance_state",
    "experiment_queue",
    "action_queue",
    "qdrant",
    "sqlite",
    "memory",
    "asset",
    "prompt",
    "rtcm",
    "gateway",
    "m01",
    "m04",
})
_ALLOWED_TARGET_IDS = frozenset({
    "foundation_diagnostic_runs",
    "nightly_health_reviews",
    "feishu_summary_dryruns",
    "tool_runtime_projections",
    "mode_callgraph_projections",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in open(path, "rb"))
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# 1. resolve_audit_target
# ─────────────────────────────────────────────────────────────────────────────


def resolve_audit_target(
    record: Dict[str, Any],
    target_id: Optional[str] = None,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Select target based on record event_type.

    event_type → target_id mapping:
      diagnostic_cli_run / diagnostic_domain_result → foundation_diagnostic_runs
      nightly_health_review                      → nightly_health_reviews
      feishu_summary_dry_run                    → feishu_summary_dryruns
      tool_runtime_projection                    → tool_runtime_projections
      mode_callgraph_projection                 → mode_callgraph_projections
    """
    errors: List[str] = []
    warnings: List[str] = []

    root_path = Path(root) if root else _get_default_root()
    audit_trail_dir = root_path / _AUDIT_TRAIL_REL

    if target_id and target_id not in _ALLOWED_TARGET_IDS:
        return {
            "target_spec": None,
            "target_path": None,
            "target_id": target_id,
            "warnings": warnings,
            "errors": [f"invalid_target_id:{target_id}"],
        }

    event_type = record.get("event_type", "")
    source = record.get("source_command", "")

    if target_id:
        resolved_target_id = target_id
    elif event_type in ("nightly_health_review",):
        resolved_target_id = "nightly_health_reviews"
    elif event_type in ("feishu_summary_dry_run",):
        resolved_target_id = "feishu_summary_dryruns"
    elif event_type in ("tool_runtime_projection",):
        resolved_target_id = "tool_runtime_projections"
    elif event_type in ("mode_callgraph_projection",):
        resolved_target_id = "mode_callgraph_projections"
    elif event_type in ("diagnostic_cli_run", "diagnostic_domain_result"):
        resolved_target_id = "foundation_diagnostic_runs"
    else:
        resolved_target_id = "foundation_diagnostic_runs"
        if event_type:
            warnings.append(f"unknown_event_type:{event_type}, defaulting to foundation_diagnostic_runs")

    target_path = str(audit_trail_dir / f"{resolved_target_id}.jsonl")

    target_spec = {
        "target_id": resolved_target_id,
        "target_path": target_path,
        "format": "jsonl",
        "append_only": True,
        "allow_overwrite": False,
        "rotation_policy": "daily",
        "max_file_size_mb": 100,
        "retention_class": "medium_term_operational",
        "requires_root_guard": True,
        "backup_required": False,
        "corruption_recovery_strategy": "append_only_recovery",
        "warnings": warnings,
    }

    return {
        "target_spec": target_spec,
        "target_path": target_path,
        "target_id": resolved_target_id,
        "warnings": warnings,
        "errors": errors,
    }


def _get_default_root() -> Path:
    try:
        from app.foundation.read_only_diagnostics_cli import ROOT as CLI_ROOT
        return Path(CLI_ROOT)
    except Exception:
        return Path(__file__).resolve().parents[3]


# ─────────────────────────────────────────────────────────────────────────────
# 2. validate_append_only_target_path
# ─────────────────────────────────────────────────────────────────────────────


def validate_append_only_target_path(
    target_path: str,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate that target_path is a safe append-only audit trail path.

    Checks:
    - Path must be under migration_reports/foundation_audit/audit_trail/
    - Suffix must be .jsonl
    - Must not contain ".." (path traversal)
    - Must not point to runtime directories
    - Symlink escape check
    """
    errors: List[str] = []
    warnings: List[str] = []

    root_path = Path(root) if root else _get_default_root()
    audit_trail_dir = root_path / _AUDIT_TRAIL_REL

    try:
        resolved = Path(target_path).resolve()
    except Exception as exc:
        return {
            "valid": False,
            "target_path": target_path,
            "warnings": warnings,
            "errors": [f"path_resolution_failed:{exc}"],
        }

    normalized = str(resolved).replace("\\", "/")

    if ".." in target_path or ".." in normalized:
        return {
            "valid": False,
            "target_path": target_path,
            "warnings": warnings,
            "errors": ["path_traversal_detected:.. not allowed"],
        }

    audit_trail_prefix = str(audit_trail_dir).replace("\\", "/")
    if not normalized.startswith(audit_trail_prefix):
        return {
            "valid": False,
            "target_path": target_path,
            "warnings": warnings,
            "errors": [f"path_outside_audit_trail:must be under {audit_trail_prefix}"],
        }

    if not target_path.endswith(".jsonl"):
        return {
            "valid": False,
            "target_path": target_path,
            "warnings": warnings,
            "errors": ["invalid_suffix:must be .jsonl"],
        }

    for restricted in _RESTRICTED_PATHS:
        if restricted in normalized:
            return {
                "valid": False,
                "target_path": target_path,
                "warnings": warnings,
                "errors": [f"restricted_path_element:{restricted}"],
            }

    if resolved.is_symlink():
        return {
            "valid": False,
            "target_path": target_path,
            "warnings": warnings,
            "errors": ["symlink_not_allowed"],
        }

    return {
        "valid": True,
        "target_path": target_path,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. serialize_audit_record_jsonl
# ─────────────────────────────────────────────────────────────────────────────


def serialize_audit_record_jsonl(record: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize AuditTrailRecord to a compact JSONL line.

    Returns dict with:
      line: compact JSON string with trailing newline
      payload_hash: SHA256 hash of sorted JSON
      warnings: list
      errors: list
    """
    errors: List[str] = []
    warnings: List[str] = []

    try:
        from app.audit import redact_audit_payload, validate_audit_record

        redacted = redact_audit_payload(dict(record))
        validation = validate_audit_record(redacted)

        if not validation.get("valid", False):
            for err in validation.get("errors", []):
                errors.append(f"validation_failed:{err}")
            return {
                "line": None,
                "payload_hash": None,
                "warnings": warnings,
                "errors": errors,
            }

        payload_hash = redacted.get("payload_hash")
        line = json.dumps(redacted, ensure_ascii=False, separators=(",", ":"))
        if not line.endswith("\n"):
            line += "\n"

        return {
            "line": line,
            "payload_hash": payload_hash,
            "warnings": warnings,
            "errors": errors,
        }

    except Exception as exc:
        return {
            "line": None,
            "payload_hash": None,
            "warnings": warnings,
            "errors": [f"serialization_failed:{exc}"],
        }


# ─────────────────────────────────────────────────────────────────────────────
# 4. append_audit_record_to_target
# ─────────────────────────────────────────────────────────────────────────────


def append_audit_record_to_target(
    record: Dict[str, Any],
    target_id: Optional[str] = None,
    root: Optional[str] = None,
    dry_run: bool = True,
) -> AuditAppendResult:
    """Append a single AuditTrailRecord to the appropriate JSONL target.

    Args:
        record: AuditTrailRecord dict (from create_audit_record_from_diagnostic_result)
        target_id: explicit target override (None = auto-select by event_type)
        root: root path for audit_trail directory
        dry_run: if True, validate but do not write any bytes

    Returns:
        AuditAppendResult with status and details
    """
    append_result_id = f"append_{uuid.uuid4().hex[:16]}"

    resolve_result = resolve_audit_target(record, target_id=target_id, root=root)
    resolved_target_id = resolve_result.get("target_id", target_id or "unknown")
    target_path = resolve_result.get("target_path", "")
    resolve_errors = resolve_result.get("errors", [])
    resolve_warnings = resolve_result.get("warnings", [])

    if resolve_errors:
        return AuditAppendResult(
            append_result_id=append_result_id,
            status=AuditAppendStatus.BLOCKED_INVALID_TARGET,
            target_id=resolved_target_id,
            target_path=target_path,
            record_id=record.get("audit_record_id"),
            event_type=record.get("event_type"),
            write_mode=record.get("write_mode", "unknown"),
            bytes_written=0,
            validation_valid=False,
            warnings=resolve_warnings,
            errors=resolve_errors,
            appended_at=_now(),
        )

    validation_result = validate_append_only_target_path(target_path, root=root)
    if not validation_result.get("valid", False):
        return AuditAppendResult(
            append_result_id=append_result_id,
            status=AuditAppendStatus.BLOCKED_INVALID_TARGET,
            target_id=resolved_target_id,
            target_path=target_path,
            record_id=record.get("audit_record_id"),
            event_type=record.get("event_type"),
            write_mode=record.get("write_mode", "unknown"),
            bytes_written=0,
            validation_valid=False,
            warnings=resolve_warnings,
            errors=validation_result.get("errors", []),
            appended_at=_now(),
        )

    serialization = serialize_audit_record_jsonl(record)
    line = serialization.get("line")
    ser_errors = serialization.get("errors", [])
    ser_warnings = serialization.get("warnings", [])
    payload_hash = serialization.get("payload_hash")

    if ser_errors or line is None:
        return AuditAppendResult(
            append_result_id=append_result_id,
            status=AuditAppendStatus.BLOCKED_INVALID_RECORD,
            target_id=resolved_target_id,
            target_path=target_path,
            record_id=record.get("audit_record_id"),
            event_type=record.get("event_type"),
            write_mode=record.get("write_mode", "unknown"),
            bytes_written=0,
            validation_valid=False,
            warnings=resolve_warnings + ser_warnings,
            errors=resolve_errors + ser_errors,
            appended_at=_now(),
        )

    if dry_run:
        return AuditAppendResult(
            append_result_id=append_result_id,
            status=AuditAppendStatus.SKIPPED_DRY_RUN,
            target_id=resolved_target_id,
            target_path=target_path,
            record_id=record.get("audit_record_id"),
            event_type=record.get("event_type"),
            write_mode=record.get("write_mode", "unknown"),
            bytes_written=0,
            validation_valid=True,
            payload_hash=payload_hash,
            warnings=resolve_warnings + ser_warnings,
            errors=[],
            appended_at=_now(),
        )

    try:
        path = Path(target_path)
        line_count_before = _count_lines(path) if path.exists() else 0

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

        line_count_after = _count_lines(path)
        bytes_written = len(line.encode("utf-8"))

        return AuditAppendResult(
            append_result_id=append_result_id,
            status=AuditAppendStatus.APPENDED,
            target_id=resolved_target_id,
            target_path=target_path,
            record_id=record.get("audit_record_id"),
            event_type=record.get("event_type"),
            write_mode=record.get("write_mode", "unknown"),
            bytes_written=bytes_written,
            line_count_before=line_count_before,
            line_count_after=line_count_after,
            payload_hash=payload_hash,
            validation_valid=True,
            warnings=resolve_warnings + ser_warnings,
            errors=[],
            appended_at=_now(),
        )

    except Exception as exc:
        return AuditAppendResult(
            append_result_id=append_result_id,
            status=AuditAppendStatus.FAILED,
            target_id=resolved_target_id,
            target_path=target_path,
            record_id=record.get("audit_record_id"),
            event_type=record.get("event_type"),
            write_mode=record.get("write_mode", "unknown"),
            bytes_written=0,
            validation_valid=True,
            payload_hash=payload_hash,
            warnings=resolve_warnings + ser_warnings,
            errors=[f"append_failed:{exc}"],
            appended_at=_now(),
        )


# ─────────────────────────────────────────────────────────────────────────────
# 5. append_diagnostic_result_audit_record
# ─────────────────────────────────────────────────────────────────────────────


def append_diagnostic_result_audit_record(
    result: Dict[str, Any],
    root: Optional[str] = None,
    dry_run: bool = True,
) -> AuditAppendResult:
    """Append audit_record from a diagnostic result to its target JSONL.

    Args:
        result: diagnostic result dict (from run_*_diagnostic functions)
        root: root path for audit_trail directory
        dry_run: if True, validate but do not write any bytes

    Returns:
        AuditAppendResult
    """
    audit_record = result.get("audit_record")
    if not audit_record:
        return AuditAppendResult(
            append_result_id=f"append_{uuid.uuid4().hex[:16]}",
            status=AuditAppendStatus.BLOCKED_INVALID_RECORD,
            target_id="unknown",
            target_path="",
            record_id=None,
            event_type=None,
            write_mode="unknown",
            bytes_written=0,
            validation_valid=False,
            warnings=["no_audit_record_in_result"],
            errors=[],
            appended_at=_now(),
        )

    command = result.get("command", "unknown")
    return append_audit_record_to_target(
        audit_record,
        target_id=None,
        root=root,
        dry_run=dry_run,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. append_all_diagnostic_audit_records
# ─────────────────────────────────────────────────────────────────────────────


def append_all_diagnostic_audit_records(
    all_result: Dict[str, Any],
    root: Optional[str] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Append all audit_records from an all-diagnostics run.

    Appends:
      1. The 'all' aggregate audit_record
      2. Each child diagnostic's audit_record (8 commands)

    Args:
        all_result: result dict from run_all_diagnostics()
        root: root path for audit_trail directory
        dry_run: if True, validate but do not write any bytes

    Returns:
        dict with total/appended/skipped/failed counts and per-record results
    """
    results: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []
    appended_count = 0
    skipped_count = 0
    failed_count = 0

    all_audit = all_result.get("audit_record")
    if all_audit:
        all_append = append_audit_record_to_target(
            all_audit,
            target_id=None,
            root=root,
            dry_run=dry_run,
        )
        results.append(asdict(all_append))
        if all_append.status == AuditAppendStatus.APPENDED:
            appended_count += 1
        elif all_append.status == AuditAppendStatus.SKIPPED_DRY_RUN:
            skipped_count += 1
        elif all_append.status == AuditAppendStatus.FAILED:
            failed_count += 1
            errors.extend(all_append.errors)
        errors.extend(all_append.errors)
        warnings.extend(all_append.warnings)

    diagnostics = all_result.get("payload", {}).get("diagnostics", {})
    if isinstance(diagnostics, dict):
        for name, diag_result in diagnostics.items():
            if not isinstance(diag_result, dict):
                continue
            diag_audit = diag_result.get("audit_record")
            if not diag_audit:
                warnings.append(f"no_audit_record:{name}")
                continue
            append_result = append_audit_record_to_target(
                diag_audit,
                target_id=None,
                root=root,
                dry_run=dry_run,
            )
            results.append(asdict(append_result))
            if append_result.status == AuditAppendStatus.APPENDED:
                appended_count += 1
            elif append_result.status == AuditAppendStatus.SKIPPED_DRY_RUN:
                skipped_count += 1
            elif append_result.status == AuditAppendStatus.FAILED:
                failed_count += 1
                errors.extend(append_result.errors)
            errors.extend(append_result.errors)
            warnings.extend(append_result.warnings)

    return {
        "total_records": len(results),
        "appended_count": appended_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "results": results,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. generate_append_only_jsonl_writer_sample
# ─────────────────────────────────────────────────────────────────────────────


def generate_append_only_jsonl_writer_sample(
    output_path: Optional[str] = None,
    tmp_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate sample output demonstrating the append-only JSONL writer.

    Writes to output_path if provided, otherwise DEFAULT_PHASE_D path.
    If tmp_path is provided, uses it as the audit trail root (for testing).
    """
    from pathlib import Path as PP
    from app.audit.audit_trail_contract import build_audit_target_specs, generate_append_only_audit_trail_design

    try:
        from app.foundation import read_only_diagnostics_cli as cli
        use_root = Path(tmp_path) if tmp_path else None
        root_str = str(use_root) if use_root else None
    except Exception:
        root_str = None

    target_specs_result = build_audit_target_specs(root=root_str)
    design_result = generate_append_only_audit_trail_design()

    dry_run_samples: List[Dict[str, Any]] = []
    for spec in target_specs_result.get("target_specs", [])[:3]:
        sample_record = {
            "audit_record_id": f"sample_{uuid.uuid4().hex[:16]}",
            "event_type": "diagnostic_domain_result",
            "write_mode": "dry_run",
            "source_system": "foundation_diagnostics_cli",
            "status": "ok",
            "root": "E:\\OpenClaw-Base\\deerflow",
            "generated_at": _now(),
            "observed_at": _now(),
            "payload_hash": "0" * 32,
            "sensitivity_level": "public_metadata",
            "retention_class": "medium_term_operational",
            "redaction_applied": False,
            "schema_version": "1.0",
        }
        append_res = append_audit_record_to_target(
            sample_record,
            target_id=spec["target_id"],
            root=root_str,
            dry_run=True,
        )
        dry_run_samples.append(asdict(append_res))

    warnings: List[str] = []
    if tmp_path:
        warnings.append("tmp_path_used_for_testing")
    else:
        warnings.append("production_audit_trail_not_modified")

    output_default = PP(__file__).resolve().parents[4] / "migration_reports" / "foundation_audit" / "R241-11C_APPEND_ONLY_JSONL_WRITER_SAMPLE.json"
    target = PP(output_path) if output_path else output_default
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "target_specs": target_specs_result.get("target_specs", []),
        "design_phases": design_result.get("implementation_phases", []),
        "dry_run_append_samples": dry_run_samples,
        "generated_at": _now(),
        "warnings": warnings,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(target), **payload}
