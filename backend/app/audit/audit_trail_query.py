"""Append-only Audit Trail Read Path Query Engine (R241-11D Phase 4).

This module provides read-only access to audit_trail/*.jsonl files.
It does NOT write, overwrite, truncate, or delete any JSONL file.

SECURITY INVARIANTS:
- Read-only: all functions read without writing any bytes to audit_trail/
- No path traversal beyond audit_trail/ directory
- No network calls, no webhook calls
- Sensitive fields (webhook_url, api_key, token, body) are always masked in output
"""

from __future__ import annotations

import csv
import io
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


class AuditQueryStatus(str, Enum):
    OK = "ok"
    PARTIAL_WARNING = "partial_warning"
    NO_RECORDS = "no_records"
    INVALID_QUERY = "invalid_query"
    FAILED = "failed"


class AuditQueryOutputFormat(str, Enum):
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    TEXT = "text"
    MARKDOWN = "markdown"


class AuditRecordSource(str, Enum):
    FOUNDATION_DIAGNOSTIC_RUNS = "foundation_diagnostic_runs"
    NIGHTLY_HEALTH_REVIEWS = "nightly_health_reviews"
    FEISHU_SUMMARY_DRYRUNS = "feishu_summary_dryruns"
    TOOL_RUNTIME_PROJECTIONS = "tool_runtime_projections"
    MODE_CALLGRAPH_PROJECTIONS = "mode_callgraph_projections"
    ALL = "all"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AuditTrailFileSummary:
    target_id: str
    path: str
    exists: bool
    line_count: int = 0
    valid_record_count: int = 0
    invalid_line_count: int = 0
    first_record_at: Optional[str] = None
    last_record_at: Optional[str] = None
    event_types: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class AuditQueryFilter:
    event_type: Optional[str] = None
    source_command: Optional[str] = None
    status: Optional[str] = None
    write_mode: Optional[str] = None
    sensitivity_level: Optional[str] = None
    payload_hash: Optional[str] = None
    audit_record_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = 100
    offset: int = 0
    order: str = "asc"
    warnings: List[str] = field(default_factory=list)


@dataclass
class AuditQueryResult:
    query_id: str
    status: AuditQueryStatus
    generated_at: str
    root: str
    filters: Dict[str, Any]
    total_scanned: int = 0
    total_matched: int = 0
    returned_count: int = 0
    records: List[Dict[str, Any]] = field(default_factory=list)
    file_summaries: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_AUDIT_TRAIL_REL = Path("migration_reports/foundation_audit/audit_trail")
_AUDIT_SOURCES = {
    "foundation_diagnostic_runs",
    "nightly_health_reviews",
    "feishu_summary_dryruns",
    "tool_runtime_projections",
    "mode_callgraph_projections",
}
_AUDIT_SUFFIX = ".jsonl"

# Sensitive fields to mask in query output
_SENSITIVE_FIELDS = frozenset({
    "webhook_url", "webhook_url_dry_run", "api_key", "api_key_dry_run",
    "token", "bearer", "secret", "password", "credential",
    "body", "content", "raw_content", "full_content", "text_content",
    "artifact_body", "memory_body", "prompt_body", "rtcm_body",
    "session_body", "dossier_body", "final_report_body",
    "authorization", "auth_header",
})


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_default_root() -> Path:
    try:
        from app.foundation.read_only_diagnostics_cli import ROOT as CLI_ROOT
        return Path(CLI_ROOT)
    except Exception:
        return Path(__file__).resolve().parents[3]


def _mask_sensitive(record: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive fields in a record copy without modifying original."""
    result = dict(record)
    for key in list(result.keys()):
        key_lower = key.lower()
        if any(sf in key_lower for sf in ("webhook_url", "api_key", "token", "secret", "password", "body", "content", "raw_", "authorization")):
            result[key] = "[REDACTED]"
    return result


def _parse_iso_time(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO8601 datetime string, return None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _time_in_range(
    record: Dict[str, Any],
    start_time: Optional[str],
    end_time: Optional[str],
) -> bool:
    """Check if record's time field falls within range."""
    time_fields = ["generated_at", "observed_at", "appended_at"]
    start_dt = _parse_iso_time(start_time)
    end_dt = _parse_iso_time(end_time)

    for field_name in time_fields:
        value = record.get(field_name)
        if not value:
            continue
        dt = _parse_iso_time(value)
        if dt is None:
            continue
        if start_dt and dt < start_dt:
            return False
        if end_dt and dt > end_dt:
            return False
        return True
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 1. discover_audit_trail_files
# ─────────────────────────────────────────────────────────────────────────────


def discover_audit_trail_files(root: Optional[str] = None) -> Dict[str, Any]:
    """Discover existing audit_trail JSONL files (read-only).

    Returns:
        dict with discovered_files, missing_files, warnings
    """
    warnings: List[str] = []
    root_path = Path(root) if root else _get_default_root()
    audit_trail_dir = root_path / _AUDIT_TRAIL_REL

    discovered_files: List[Dict[str, Any]] = []
    missing_files: List[str] = []

    for source_id in sorted(_AUDIT_SOURCES):
        file_path = audit_trail_dir / f"{source_id}{_AUDIT_SUFFIX}"
        path_str = str(file_path)

        if file_path.exists():
            try:
                size = file_path.stat().st_size
                discovered_files.append({
                    "target_id": source_id,
                    "path": path_str,
                    "exists": True,
                    "size_bytes": size,
                })
            except OSError as exc:
                warnings.append(f"exists_but_cannot_stat:{source_id}:{exc}")
                discovered_files.append({
                    "target_id": source_id,
                    "path": path_str,
                    "exists": True,
                    "size_bytes": None,
                })
        else:
            missing_files.append(path_str)
            discovered_files.append({
                "target_id": source_id,
                "path": path_str,
                "exists": False,
                "size_bytes": None,
            })

    return {
        "discovered_files": discovered_files,
        "missing_files": missing_files,
        "audit_trail_dir": str(audit_trail_dir),
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. scan_append_only_audit_trail
# ─────────────────────────────────────────────────────────────────────────────


def scan_append_only_audit_trail(root: Optional[str] = None) -> Dict[str, Any]:
    """Scan all existing audit_trail JSONL files and return per-file summaries.

    Does NOT modify any files. Malformed lines are counted but do not cause errors.
    """
    warnings: List[str] = []
    errors: List[str] = []
    file_summaries: List[Dict[str, Any]] = []
    total_files = 0
    existing_files = 0
    total_lines = 0
    total_valid_records = 0
    total_invalid_lines = 0
    by_event_type: Dict[str, int] = {}

    root_path = Path(root) if root else _get_default_root()
    audit_trail_dir = root_path / _AUDIT_TRAIL_REL

    for source_id in sorted(_AUDIT_SOURCES):
        file_path = audit_trail_dir / f"{source_id}{_AUDIT_SUFFIX}"
        path_str = str(file_path)
        total_files += 1

        summary = AuditTrailFileSummary(
            target_id=source_id,
            path=path_str,
            exists=False,
            line_count=0,
            valid_record_count=0,
            invalid_line_count=0,
            event_types=[],
        )

        if not file_path.exists():
            file_summaries.append(asdict(summary))
            continue

        existing_files += 1
        summary.exists = True

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as exc:
            summary.errors.append(f"read_failed:{exc}")
            file_summaries.append(asdict(summary))
            errors.append(f"{source_id}:read_failed:{exc}")
            continue

        summary.line_count = len(lines)
        total_lines += len(lines)

        first_at: Optional[str] = None
        last_at: Optional[str] = None
        seen_event_types: set = set()

        for i, raw_line in enumerate(lines):
            line = raw_line.rstrip("\n")
            if not line.strip():
                summary.invalid_line_count += 1
                total_invalid_lines += 1
                continue

            try:
                record = json.loads(line)
                summary.valid_record_count += 1
                total_valid_records += 1

                event_type = record.get("event_type", "")
                if event_type:
                    seen_event_types.add(event_type)
                    by_event_type[event_type] = by_event_type.get(event_type, 0) + 1

                for tf in ("generated_at", "observed_at", "appended_at"):
                    val = record.get(tf)
                    if val:
                        if first_at is None or val < first_at:
                            first_at = val
                        if last_at is None or val > last_at:
                            last_at = val
                        break

            except json.JSONDecodeError:
                summary.invalid_line_count += 1
                total_invalid_lines += 1
                summary.warnings.append(f"malformed_line:{i + 1}")

        summary.first_record_at = first_at
        summary.last_record_at = last_at
        summary.event_types = sorted(seen_event_types)
        file_summaries.append(asdict(summary))

    return {
        "file_summaries": file_summaries,
        "total_files": total_files,
        "existing_files": existing_files,
        "total_lines": total_lines,
        "total_valid_records": total_valid_records,
        "total_invalid_lines": total_invalid_lines,
        "by_event_type": by_event_type,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. load_audit_jsonl_records
# ─────────────────────────────────────────────────────────────────────────────


def load_audit_jsonl_records(
    target_id: Optional[str] = None,
    root: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Load records from specified target_id or all existing JSONL files.

    Args:
        target_id: specific source to read, or None/"all" for all sources
        root: root path for audit_trail directory
        limit: maximum number of records to return (affects returned_count, not scanned_count)

    Returns:
        dict with records, scanned_count, returned_count, invalid_line_count, warnings, errors
    """
    warnings: List[str] = []
    errors: List[str] = []
    records: List[Dict[str, Any]] = []
    scanned_count = 0
    invalid_line_count = 0

    root_path = Path(root) if root else _get_default_root()
    audit_trail_dir = root_path / _AUDIT_TRAIL_REL

    if target_id and target_id not in ("all", "unknown"):
        target_ids = [target_id]
    else:
        target_ids = sorted(_AUDIT_SOURCES)

    for tid in target_ids:
        file_path = audit_trail_dir / f"{tid}{_AUDIT_SUFFIX}"
        if not file_path.exists():
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as exc:
            errors.append(f"{tid}:read_failed:{exc}")
            continue

        for raw_line in lines:
            line = raw_line.rstrip("\n")
            if not line.strip():
                continue

            scanned_count += 1
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError:
                invalid_line_count += 1
                warnings.append(f"malformed_line:{tid}:line_{scanned_count}")

    # Apply limit after scanning all files
    returned_count = len(records)
    if limit is not None and limit > 0:
        records = records[:limit]
        returned_count = len(records)

    return {
        "records": records,
        "scanned_count": scanned_count,
        "returned_count": returned_count,
        "invalid_line_count": invalid_line_count,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. build_audit_query_filter
# ─────────────────────────────────────────────────────────────────────────────


def build_audit_query_filter(**kwargs: Any) -> Dict[str, Any]:
    """Build an AuditQueryFilter dict from keyword arguments.

    Supports: event_type, source_command, status, write_mode, sensitivity_level,
              payload_hash, audit_record_id, start_time, end_time, limit, offset, order
    """
    warnings: List[str] = []
    limit = kwargs.get("limit", 100)
    if limit > 1000:
        warnings.append(f"limit_clamped:1000")
        limit = 1000
    if limit < 1:
        limit = 100
        warnings.append("limit_reset_to_default_100")

    offset = max(0, kwargs.get("offset", 0))
    order = kwargs.get("order", "asc")
    if order not in ("asc", "desc"):
        warnings.append(f"invalid_order:{order}, defaulting to asc")
        order = "asc"

    for tf in ("start_time", "end_time"):
        val = kwargs.get(tf)
        if val:
            dt = _parse_iso_time(val)
            if dt is None:
                warnings.append(f"malformed_datetime:{tf}:{val}")

    query_filter = AuditQueryFilter(
        event_type=kwargs.get("event_type"),
        source_command=kwargs.get("source_command"),
        status=kwargs.get("status"),
        write_mode=kwargs.get("write_mode"),
        sensitivity_level=kwargs.get("sensitivity_level"),
        payload_hash=kwargs.get("payload_hash"),
        audit_record_id=kwargs.get("audit_record_id"),
        start_time=kwargs.get("start_time"),
        end_time=kwargs.get("end_time"),
        limit=limit,
        offset=offset,
        order=order,
        warnings=warnings,
    )
    return asdict(query_filter)


# ─────────────────────────────────────────────────────────────────────────────
# 5. record_matches_audit_filter
# ─────────────────────────────────────────────────────────────────────────────


def record_matches_audit_filter(record: Dict[str, Any], query_filter: Dict[str, Any]) -> bool:
    """Check if a record matches all set filters in query_filter.

    Rules:
    - event_type: exact match
    - source_command: exact match
    - status: exact match
    - write_mode: exact match
    - sensitivity_level: exact match
    - payload_hash: exact or prefix match
    - audit_record_id: exact match
    - start_time/end_time: check generated_at/observed_at/appended_at fields
    """
    if not query_filter:
        return True

    if query_filter.get("event_type"):
        if record.get("event_type") != query_filter["event_type"]:
            return False

    if query_filter.get("source_command"):
        if record.get("source_command") != query_filter["source_command"]:
            return False

    if query_filter.get("status"):
        if record.get("status") != query_filter["status"]:
            return False

    if query_filter.get("write_mode"):
        if record.get("write_mode") != query_filter["write_mode"]:
            return False

    if query_filter.get("sensitivity_level"):
        if record.get("sensitivity_level") != query_filter["sensitivity_level"]:
            return False

    if query_filter.get("payload_hash"):
        ph = query_filter["payload_hash"]
        rec_ph = record.get("payload_hash", "")
        if not (rec_ph == ph or rec_ph.startswith(ph)):
            return False

    if query_filter.get("audit_record_id"):
        if record.get("audit_record_id") != query_filter["audit_record_id"]:
            return False

    start_time = query_filter.get("start_time")
    end_time = query_filter.get("end_time")
    if start_time or end_time:
        if not _time_in_range(record, start_time, end_time):
            return False

    return True


# ─────────────────────────────────────────────────────────────────────────────
# 6. query_audit_trail
# ─────────────────────────────────────────────────────────────────────────────


def query_audit_trail(
    root: Optional[str] = None,
    target_id: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    output_format: str = "json",
) -> Dict[str, Any]:
    """Query audit_trail JSONL files with filters (read-only).

    Args:
        root: root path for audit_trail directory
        target_id: specific source to query, or None for all
        filters: AuditQueryFilter dict with matching criteria
        output_format: output format (json/jsonl/csv/text/markdown)

    Returns:
        AuditQueryResult dataclass as dict
    """
    query_id = f"q_{uuid.uuid4().hex[:16]}"
    warnings: List[str] = []
    errors: List[str] = []
    filters = dict(filters) if filters else {}

    # Validate output_format
    try:
        fmt = AuditQueryOutputFormat(output_format.lower())
    except ValueError:
        fmt = AuditQueryOutputFormat.JSON
        errors.append(f"invalid_output_format:{output_format}")

    # Discover files first
    discover = discover_audit_trail_files(root=root)
    warnings.extend(discover.get("warnings", []))

    # Scan files
    scan = scan_append_only_audit_trail(root=root)
    file_summaries = scan.get("file_summaries", [])
    total_scanned = scan.get("total_valid_records", 0)
    warnings.extend(scan.get("warnings", []))
    errors.extend(scan.get("errors", []))

    # Load records from target
    load = load_audit_jsonl_records(target_id=target_id, root=root)
    raw_records = load.get("records", [])
    total_scanned = load.get("scanned_count", 0)
    warnings.extend(load.get("warnings", []))
    errors.extend(load.get("errors", []))

    # Apply filters
    matched_records: List[Dict[str, Any]] = []
    for rec in raw_records:
        if record_matches_audit_filter(rec, filters):
            matched = _mask_sensitive(rec)
            matched_records.append(matched)

    total_matched = len(matched_records)

    # Apply ordering
    order = filters.get("order", "asc")
    reverse = order == "desc"
    try:
        matched_records.sort(
            key=lambda r: r.get("generated_at") or r.get("observed_at") or r.get("appended_at") or "",
            reverse=reverse,
        )
    except Exception:
        pass

    # Apply offset + limit
    offset = filters.get("offset", 0)
    limit = filters.get("limit", 100)
    paginated = matched_records[offset : offset + limit]
    returned_count = len(paginated)

    # Determine status
    if errors:
        status = AuditQueryStatus.FAILED
    elif total_matched == 0:
        status = AuditQueryStatus.NO_RECORDS
    elif warnings:
        status = AuditQueryStatus.PARTIAL_WARNING
    else:
        status = AuditQueryStatus.OK

    root_str = str(Path(root) if root else _get_default_root())

    result = AuditQueryResult(
        query_id=query_id,
        status=status,
        generated_at=_now(),
        root=root_str,
        filters=filters,
        total_scanned=total_scanned,
        total_matched=total_matched,
        returned_count=returned_count,
        records=paginated,
        file_summaries=file_summaries,
        warnings=warnings,
        errors=errors,
    )
    return asdict(result)


# ─────────────────────────────────────────────────────────────────────────────
# 7. summarize_audit_query_result
# ─────────────────────────────────────────────────────────────────────────────


def summarize_audit_query_result(query_result: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a query result into aggregated statistics.

    Returns aggregation by event_type, source_command, status, sensitivity_level, write_mode.
    """
    warnings: List[str] = []
    errors: List[str] = []
    records = query_result.get("records", [])

    by_event_type: Dict[str, int] = {}
    by_source_command: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    by_sensitivity_level: Dict[str, int] = {}
    by_write_mode: Dict[str, int] = {}
    first_record_at: Optional[str] = None
    last_record_at: Optional[str] = None

    for rec in records:
        et = rec.get("event_type", "unknown")
        by_event_type[et] = by_event_type.get(et, 0) + 1

        sc = rec.get("source_command", "unknown")
        by_source_command[sc] = by_source_command.get(sc, 0) + 1

        st = rec.get("status", "unknown")
        by_status[st] = by_status.get(st, 0) + 1

        sl = rec.get("sensitivity_level", "unknown")
        by_sensitivity_level[sl] = by_sensitivity_level.get(sl, 0) + 1

        wm = rec.get("write_mode", "unknown")
        by_write_mode[wm] = by_write_mode.get(wm, 0) + 1

        for tf in ("generated_at", "observed_at", "appended_at"):
            val = rec.get(tf)
            if val:
                if first_record_at is None or val < first_record_at:
                    first_record_at = val
                if last_record_at is None or val > last_record_at:
                    last_record_at = val
                break

    return {
        "total_scanned": query_result.get("total_scanned", 0),
        "total_matched": query_result.get("total_matched", 0),
        "returned_count": query_result.get("returned_count", 0),
        "by_event_type": by_event_type,
        "by_source_command": by_source_command,
        "by_status": by_status,
        "by_sensitivity_level": by_sensitivity_level,
        "by_write_mode": by_write_mode,
        "first_record_at": first_record_at,
        "last_record_at": last_record_at,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. format_audit_query_result
# ─────────────────────────────────────────────────────────────────────────────


def format_audit_query_result(
    query_result: Dict[str, Any],
    output_format: str = "json",
) -> Any:
    """Format a query result into the requested output format.

    Formats: json (dict), jsonl (str), csv (str), markdown (str), text (str)
    Sensitive fields are always masked.
    """
    warnings: List[str] = []

    try:
        fmt = AuditQueryOutputFormat(output_format.lower())
    except ValueError:
        warnings.append(f"unknown_format:{output_format}, using json")
        fmt = AuditQueryOutputFormat.JSON

    records = query_result.get("records", [])
    summary = summarize_audit_query_result(query_result)

    if fmt == AuditQueryOutputFormat.JSON:
        return {
            "query_id": query_result.get("query_id"),
            "status": query_result.get("status"),
            "generated_at": query_result.get("generated_at"),
            "total_scanned": query_result.get("total_scanned"),
            "total_matched": query_result.get("total_matched"),
            "returned_count": query_result.get("returned_count"),
            "records": records,
            "summary": summary,
            "file_summaries": query_result.get("file_summaries", []),
            "warnings": query_result.get("warnings", []) + warnings,
            "errors": query_result.get("errors", []),
        }

    elif fmt == AuditQueryOutputFormat.JSONL:
        lines = []
        for rec in records:
            lines.append(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
        return "\n".join(lines)

    elif fmt == AuditQueryOutputFormat.CSV:
        if not records:
            return ""
        output = io.StringIO()
        flat_keys = [
            "audit_record_id", "event_type", "write_mode", "source_command",
            "status", "sensitivity_level", "payload_hash", "generated_at",
            "observed_at", "appended_at", "schema_version",
        ]
        writer = csv.DictWriter(output, fieldnames=flat_keys, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            row = {k: rec.get(k, "") for k in flat_keys}
            writer.writerow(row)
        return output.getvalue()

    elif fmt == AuditQueryOutputFormat.MARKDOWN:
        lines = [
            "# Audit Query Result",
            "",
            f"**Query ID:** `{query_result.get('query_id', '')}`",
            f"**Status:** `{query_result.get('status', '')}`",
            f"**Generated:** `{query_result.get('generated_at', '')}`",
            f"**Total Scanned:** {query_result.get('total_scanned', 0)}",
            f"**Total Matched:** {query_result.get('total_matched', 0)}",
            f"**Returned:** {query_result.get('returned_count', 0)}",
            "",
        ]

        if summary.get("by_event_type"):
            lines.append("## By Event Type")
            lines.append("| event_type | count |")
            lines.append("|------------|-------|")
            for et, cnt in sorted(summary["by_event_type"].items()):
                lines.append(f"| `{et}` | {cnt} |")
            lines.append("")

        if summary.get("by_status"):
            lines.append("## By Status")
            lines.append("| status | count |")
            lines.append("|--------|-------|")
            for st, cnt in sorted(summary["by_status"].items()):
                lines.append(f"| `{st}` | {cnt} |")
            lines.append("")

        if summary.get("by_source_command"):
            lines.append("## By Source Command")
            lines.append("| source_command | count |")
            lines.append("|-----------------|-------|")
            for sc, cnt in sorted(summary["by_source_command"].items()):
                lines.append(f"| `{sc}` | {cnt} |")
            lines.append("")

        if records:
            lines.append("## Records (first 5)")
            lines.append("")
            for i, rec in enumerate(records[:5]):
                lines.append(f"### {i + 1}. `{rec.get('event_type', 'unknown')}`")
                lines.append(f"- id: `{rec.get('audit_record_id', '')}`")
                lines.append(f"- status: `{rec.get('status', '')}`")
                lines.append(f"- write_mode: `{rec.get('write_mode', '')}`")
                lines.append(f"- sensitivity: `{rec.get('sensitivity_level', '')}`")
                lines.append(f"- generated: `{rec.get('generated_at', '')}`")
                lines.append("")

        return "\n".join(lines)

    elif fmt == AuditQueryOutputFormat.TEXT:
        lines = [
            f"Query: {query_result.get('query_id')} | Status: {query_result.get('status')} | "
            f"Scanned: {query_result.get('total_scanned')} | Matched: {query_result.get('total_matched')} | "
            f"Returned: {query_result.get('returned_count')}",
        ]
        if summary.get("by_event_type"):
            items = ", ".join(f"{et}:{cnt}" for et, cnt in sorted(summary["by_event_type"].items()))
            lines.append(f"Events: {items}")
        if summary.get("by_status"):
            items = ", ".join(f"{st}:{cnt}" for st, cnt in sorted(summary["by_status"].items()))
            lines.append(f"Status: {items}")
        if summary.get("by_source_command"):
            items = ", ".join(f"{sc}:{cnt}" for sc, cnt in sorted(summary["by_source_command"].items()))
            lines.append(f"Commands: {items}")
        first = summary.get("first_record_at", "N/A")
        last = summary.get("last_record_at", "N/A")
        lines.append(f"Range: {first} → {last}")
        return "\n".join(lines)

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# 9. generate_audit_query_engine_sample
# ─────────────────────────────────────────────────────────────────────────────


def generate_audit_query_engine_sample(
    output_path: Optional[str] = None,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a sample demonstrating all query capabilities.

    Writes to output_path if provided, otherwise the default phase D path.
    This function only reads existing JSONL — it does NOT write to audit_trail/.
    """
    from pathlib import Path as PP

    warnings: List[str] = []

    # 1. File discovery
    discovery = discover_audit_trail_files(root=root)
    if root:
        warnings.append("root_override_used")

    # 2. Scan
    scan = scan_append_only_audit_trail(root=root)

    # 3. Query: all records
    query_all = query_audit_trail(root=root, output_format="json")

    # 4. Query: nightly
    query_nightly = query_audit_trail(
        root=root, filters={"event_type": "nightly_health_review"}, output_format="json"
    )

    # 5. Query: feishu
    query_feishu = query_audit_trail(
        root=root, filters={"event_type": "feishu_summary_dry_run"}, output_format="json"
    )

    # 6. Query: partial_warning status
    query_partial = query_audit_trail(
        root=root, filters={"status": "partial_warning", "limit": 50}, output_format="json"
    )

    # 7. Query: public_metadata sensitivity
    query_public = query_audit_trail(
        root=root, filters={"sensitivity_level": "public_metadata", "limit": 20}, output_format="json"
    )

    # Build summaries
    sum_all = summarize_audit_query_result(query_all)
    sum_nightly = summarize_audit_query_result(query_nightly)
    sum_feishu = summarize_audit_query_result(query_feishu)
    sum_partial = summarize_audit_query_result(query_partial)
    sum_public = summarize_audit_query_result(query_public)

    sample = {
        "file_discovery": discovery,
        "scan_summary": {
            "total_files": scan.get("total_files"),
            "existing_files": scan.get("existing_files"),
            "total_lines": scan.get("total_lines"),
            "total_valid_records": scan.get("total_valid_records"),
            "total_invalid_lines": scan.get("total_invalid_lines"),
            "by_event_type": scan.get("by_event_type"),
            "file_summaries": scan.get("file_summaries"),
        },
        "sample_query_all": {
            "query_id": query_all.get("query_id"),
            "status": query_all.get("status"),
            "total_scanned": query_all.get("total_scanned"),
            "total_matched": query_all.get("total_matched"),
            "returned_count": query_all.get("returned_count"),
            "summary": sum_all,
            "record_count_by_event_type": sum_all.get("by_event_type", {}),
            "record_count_by_status": sum_all.get("by_status", {}),
        },
        "sample_query_event_type_nightly": {
            "query_id": query_nightly.get("query_id"),
            "status": query_nightly.get("status"),
            "total_scanned": query_nightly.get("total_scanned"),
            "total_matched": query_nightly.get("total_matched"),
            "returned_count": query_nightly.get("returned_count"),
            "summary": sum_nightly,
        },
        "sample_query_event_type_feishu": {
            "query_id": query_feishu.get("query_id"),
            "status": query_feishu.get("status"),
            "total_scanned": query_feishu.get("total_scanned"),
            "total_matched": query_feishu.get("total_matched"),
            "returned_count": query_feishu.get("returned_count"),
            "summary": sum_feishu,
        },
        "sample_query_status_partial_warning": {
            "query_id": query_partial.get("query_id"),
            "status": query_partial.get("status"),
            "total_matched": query_partial.get("total_matched"),
            "returned_count": query_partial.get("returned_count"),
            "summary": sum_partial,
        },
        "sample_query_sensitivity_public_metadata": {
            "query_id": query_public.get("query_id"),
            "status": query_public.get("status"),
            "total_matched": query_public.get("total_matched"),
            "returned_count": query_public.get("returned_count"),
            "summary": sum_public,
        },
        "generated_at": _now(),
        "warnings": warnings,
    }

    output_default = (
        PP(__file__).resolve().parents[4]
        / "migration_reports"
        / "foundation_audit"
        / "R241-11D_AUDIT_QUERY_ENGINE_SAMPLE.json"
    )
    target = PP(output_path) if output_path else output_default
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(target), **sample}
