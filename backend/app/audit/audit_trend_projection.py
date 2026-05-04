"""Dry-run Nightly Trend projection from append-only audit trail (R241-12B).

This module reads audit_trail JSONL through the read-only query engine and
projects trend points, series, regression signals, and a NightlyTrendReport.

Security invariants:
- Never writes audit_trail JSONL.
- Never modifies existing JSONL files or line counts.
- Never writes trend runtime, action queue, governance, queue, memory, asset,
  prompt, RTCM, or Gateway state.
- Never calls network, webhooks, Feishu/Lark, tools, scheduler, or auto-fix.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.audit.audit_trail_query import (
    build_audit_query_filter,
    query_audit_trail,
    scan_append_only_audit_trail,
    summarize_audit_query_result,
)
from app.audit.audit_trend_contract import (
    DEFAULT_CONTRACT_JSON,
    AuditTrendPoint,
    AuditTrendSeries,
    NightlyTrendReport,
    TrendDirection,
    TrendMetricType,
    TrendRegressionSignal,
    TrendSeverity,
    TrendWindow,
    build_trend_metric_catalog,
    build_trend_window_spec,
    design_regression_detection_rules,
)


class TrendProjectionStatus(str, Enum):
    OK = "ok"
    PARTIAL_WARNING = "partial_warning"
    INSUFFICIENT_DATA = "insufficient_data"
    QUERY_ERROR = "query_error"
    FAILED = "failed"


class TrendAggregationMethod(str, Enum):
    COUNT = "count"
    SUM = "sum"
    RATE = "rate"
    LATEST = "latest"
    DELTA = "delta"
    WARNING_CONTAINS = "warning_contains"
    SUMMARY_FIELD_SUM = "summary_field_sum"
    UNKNOWN = "unknown"


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SAMPLE_PATH = (
    ROOT
    / "migration_reports"
    / "foundation_audit"
    / "R241-12B_DRYRUN_TREND_PROJECTION_SAMPLE.json"
)

_SENSITIVE_WORDS = ("secret", "token", "password", "api_key", "webhook_url", "body", "full_content")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _record_time(record: Dict[str, Any]) -> Optional[datetime]:
    for key in ("generated_at", "observed_at", "appended_at"):
        parsed = _parse_dt(record.get(key))
        if parsed:
            return parsed
    return None


def _latest_timestamp(records: List[Dict[str, Any]]) -> str:
    parsed = [_record_time(record) for record in records]
    parsed = [item for item in parsed if item is not None]
    if not parsed:
        return _now()
    return max(parsed).isoformat()


def _record_ref(record: Dict[str, Any]) -> str:
    for key in ("audit_record_id", "payload_hash", "source_command"):
        value = record.get(key)
        if value:
            return str(value)
    return "unknown_record_ref"


def _source_record_refs(records: List[Dict[str, Any]], limit: int = 50) -> List[str]:
    refs: List[str] = []
    for record in records[:limit]:
        ref = _record_ref(record)
        if ref not in refs:
            refs.append(ref)
    return refs


def _flatten_warnings(record: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for key in ("warnings", "redaction_warnings"):
        raw = record.get(key) or []
        if isinstance(raw, list):
            values.extend(str(item) for item in raw)
        elif raw:
            values.append(str(raw))
    return values


def _warning_count(records: List[Dict[str, Any]], needle: str) -> tuple[int, List[str]]:
    needle_lower = needle.lower()
    count = 0
    matched: List[Dict[str, Any]] = []
    for record in records:
        warnings = _flatten_warnings(record)
        if any(needle_lower in warning.lower() for warning in warnings):
            count += sum(1 for warning in warnings if needle_lower in warning.lower())
            matched.append(record)
    return count, _source_record_refs(matched)


def _summary_int(record: Dict[str, Any], *paths: str) -> int:
    summary = record.get("summary") or {}
    total = 0
    for path in paths:
        cur: Any = summary
        for part in path.split("."):
            if not isinstance(cur, dict):
                cur = None
                break
            cur = cur.get(part)
        if isinstance(cur, (int, float)):
            total += int(cur)
    return total


def _scan_invalid_lines(scan_summary: Optional[Dict[str, Any]]) -> int:
    if not scan_summary:
        return 0
    total = scan_summary.get("total_invalid_lines")
    if isinstance(total, int):
        return total
    file_summaries = scan_summary.get("file_summaries") or []
    count = 0
    for summary in file_summaries:
        if isinstance(summary, dict):
            count += int(summary.get("invalid_line_count") or 0)
    return count


def _sanitize_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Defensive redaction for formatted output."""
    def sanitize(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            result = {}
            for child_key, child_value in value.items():
                key_lower = str(child_key).lower()
                if any(word in key_lower for word in _SENSITIVE_WORDS):
                    result[child_key] = "[REDACTED]"
                else:
                    result[child_key] = sanitize(child_value, key_lower)
            return result
        if isinstance(value, list):
            return [sanitize(item, key) for item in value]
        return value
    return sanitize(report)


def load_trend_design_contract(path: Optional[str] = None) -> Dict[str, Any]:
    """Read R241-12A trend design contract without writing files."""
    warnings: List[str] = []
    errors: List[str] = []
    target = Path(path) if path else DEFAULT_CONTRACT_JSON
    if not target.exists():
        warnings.append(f"trend_design_contract_missing:{target}")
        return {"exists": False, "design": {}, "warnings": warnings, "errors": errors}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        design = raw.get("design", raw) if isinstance(raw, dict) else {}
        return {"exists": True, "design": design, "warnings": warnings, "errors": errors}
    except json.JSONDecodeError as exc:
        warnings.append(f"trend_design_contract_malformed:{target}:{exc}")
        return {"exists": True, "design": {}, "warnings": warnings, "errors": errors}
    except OSError as exc:
        errors.append(f"trend_design_contract_read_failed:{target}:{exc}")
        return {"exists": True, "design": {}, "warnings": warnings, "errors": errors}


def resolve_trend_window(
    window: str = TrendWindow.ALL_AVAILABLE.value,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve named trend windows into optional query start/end time bounds."""
    warnings: List[str] = []
    window_specs = build_trend_window_spec().get("windows", {})
    if window not in window_specs:
        warnings.append(f"unknown_trend_window:{window}")
        window = TrendWindow.ALL_AVAILABLE.value

    now = datetime.now(timezone.utc)
    resolved_start: Optional[str] = None
    resolved_end: Optional[str] = None

    if window == TrendWindow.LAST_24H.value:
        resolved_start = (now - timedelta(hours=24)).isoformat()
        resolved_end = now.isoformat()
    elif window == TrendWindow.LAST_7D.value:
        resolved_start = (now - timedelta(days=7)).isoformat()
        resolved_end = now.isoformat()
    elif window == TrendWindow.LAST_30D.value:
        resolved_start = (now - timedelta(days=30)).isoformat()
        resolved_end = now.isoformat()
    elif window == TrendWindow.CUSTOM.value:
        if not start_time or not end_time:
            warnings.append("custom_window_missing_start_or_end")
        if start_time and not _parse_dt(start_time):
            warnings.append(f"custom_window_malformed_start_time:{start_time}")
        if end_time and not _parse_dt(end_time):
            warnings.append(f"custom_window_malformed_end_time:{end_time}")
        resolved_start = start_time if _parse_dt(start_time) else None
        resolved_end = end_time if _parse_dt(end_time) else None
    else:
        if start_time and not _parse_dt(start_time):
            warnings.append(f"malformed_start_time_ignored:{start_time}")
        if end_time and not _parse_dt(end_time):
            warnings.append(f"malformed_end_time_ignored:{end_time}")
        resolved_start = start_time if _parse_dt(start_time) else None
        resolved_end = end_time if _parse_dt(end_time) else None

    spec = window_specs.get(window, {})
    return {
        "window": window,
        "start_time": resolved_start,
        "end_time": resolved_end,
        "minimum_required_points": spec.get("minimum_required_points", 1),
        "warnings": warnings,
    }


def fetch_audit_records_for_trend(
    root: Optional[str] = None,
    window: str = TrendWindow.ALL_AVAILABLE.value,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """Read audit records through the audit query engine only."""
    warnings: List[str] = []
    errors: List[str] = []
    resolved = resolve_trend_window(window, start_time, end_time)
    warnings.extend(resolved.get("warnings", []))

    try:
        filters = build_audit_query_filter(
            start_time=resolved.get("start_time"),
            end_time=resolved.get("end_time"),
            limit=limit,
            order="asc",
        )
        warnings.extend(filters.get("warnings", []))
        query_result = query_audit_trail(root=root, filters=filters, output_format="json")
        scan_summary = scan_append_only_audit_trail(root=root)
        records = query_result.get("records") or []
        warnings.extend(query_result.get("warnings") or [])
        warnings.extend(scan_summary.get("warnings") or [])
        errors.extend(query_result.get("errors") or [])
        errors.extend(scan_summary.get("errors") or [])
    except Exception as exc:
        query_result = {
            "status": TrendProjectionStatus.QUERY_ERROR.value,
            "records": [],
            "file_summaries": [],
            "warnings": [],
            "errors": [f"audit_query_failed:{exc}"],
        }
        scan_summary = {"file_summaries": [], "total_invalid_lines": 0, "warnings": [], "errors": []}
        records = []
        errors.append(f"audit_query_failed:{exc}")

    return {
        "query_result": query_result,
        "scan_summary": scan_summary,
        "records": records,
        "total_records": len(records),
        "warnings": warnings,
        "errors": errors,
    }


def extract_metric_value_from_records(
    records: List[Dict[str, Any]],
    metric_spec: Dict[str, Any],
    scan_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract one metric value from audit records."""
    warnings: List[str] = []
    metric_name = metric_spec.get("metric_name", "unknown")
    metric_type = metric_spec.get("metric_type", TrendMetricType.UNKNOWN.value)
    total = len(records)
    value: float = 0.0
    refs: List[str] = []

    if metric_name == "partial_warning_rate":
        value = (sum(1 for record in records if record.get("status") == "partial_warning") / total) if total else 0.0
        refs = _source_record_refs([record for record in records if record.get("status") == "partial_warning"])
    elif metric_name == "failed_rate":
        value = (sum(1 for record in records if record.get("status") == "failed") / total) if total else 0.0
        refs = _source_record_refs([record for record in records if record.get("status") == "failed"])
    elif metric_name == "total_audit_records":
        value = float(total)
        refs = _source_record_refs(records)
    elif metric_name == "critical_signal_count":
        value = float(sum(_summary_int(record, "by_severity.critical", "critical_count") for record in records))
        refs = _source_record_refs([record for record in records if _summary_int(record, "by_severity.critical", "critical_count") > 0])
    elif metric_name == "high_signal_count":
        value = float(sum(_summary_int(record, "by_severity.high", "high_count") for record in records))
        refs = _source_record_refs([record for record in records if _summary_int(record, "by_severity.high", "high_count") > 0])
    elif metric_name == "queue_missing_warning_count":
        count, refs = _warning_count(records, "queue_missing")
        value = float(count)
    elif metric_name == "unknown_taxonomy_count":
        count, refs = _warning_count(records, "unknown")
        value = float(count)
    elif metric_name == "rollback_missing_count":
        count, refs = _warning_count(records, "rollback_missing")
        value = float(count)
    elif metric_name == "backup_missing_count":
        count, refs = _warning_count(records, "backup_missing")
        value = float(count)
    elif metric_name == "feishu_dry_run_count":
        matched = [
            record for record in records
            if record.get("event_type") == "feishu_summary_dry_run"
            or record.get("source_command") == "feishu-summary"
        ]
        value = float(len(matched))
        refs = _source_record_refs(matched)
    elif metric_name == "nightly_review_count":
        matched = [
            record for record in records
            if record.get("event_type") == "nightly_health_review"
            or record.get("source_command") == "nightly"
        ]
        value = float(len(matched))
        refs = _source_record_refs(matched)
    elif metric_name == "invalid_jsonl_line_count":
        value = float(_scan_invalid_lines(scan_summary))
        refs = []
    else:
        warnings.append(f"unsupported_metric:{metric_name}")

    return {
        "metric_name": metric_name,
        "metric_type": metric_type,
        "metric_value": value,
        "source_record_refs": refs,
        "warnings": warnings,
    }


def build_trend_points(
    records: List[Dict[str, Any]],
    metric_catalog: List[Dict[str, Any]],
    window: str,
    scan_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build AuditTrendPoint for every metric in the catalog."""
    warnings: List[str] = []
    timestamp = _latest_timestamp(records)
    points: List[Dict[str, Any]] = []
    for metric_spec in metric_catalog:
        metric = extract_metric_value_from_records(records, metric_spec, scan_summary)
        warnings.extend(metric.get("warnings", []))
        point = AuditTrendPoint(
            point_id=_new_id("trend_point"),
            timestamp=timestamp,
            window=window,
            metric_type=metric.get("metric_type", TrendMetricType.UNKNOWN.value),
            metric_name=metric.get("metric_name", "unknown"),
            metric_value=float(metric.get("metric_value") or 0.0),
            source_record_refs=metric.get("source_record_refs", []),
            warnings=metric.get("warnings", []),
        )
        points.append(asdict(point))
    return {"points": points, "point_count": len(points), "warnings": warnings}


def build_trend_series(points: List[Dict[str, Any]], window: str) -> Dict[str, Any]:
    """Group trend points into per-metric series."""
    warnings: List[str] = []
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for point in points:
        grouped.setdefault(point.get("metric_name", "unknown"), []).append(point)

    series_list: List[Dict[str, Any]] = []
    for metric_name, metric_points in grouped.items():
        metric_points = sorted(metric_points, key=lambda p: p.get("timestamp") or "")
        latest = float(metric_points[-1].get("metric_value") or 0.0)
        previous = float(metric_points[-2].get("metric_value")) if len(metric_points) > 1 else None
        delta = latest - previous if previous is not None else None
        delta_percent = None
        direction = TrendDirection.INSUFFICIENT_DATA.value
        if previous is not None:
            if delta == 0:
                direction = TrendDirection.STABLE.value
            elif delta and delta > 0:
                direction = TrendDirection.WORSENING.value
            else:
                direction = TrendDirection.IMPROVING.value
            if previous != 0:
                delta_percent = delta / previous
        series = AuditTrendSeries(
            series_id=_new_id("trend_series"),
            metric_type=metric_points[-1].get("metric_type", TrendMetricType.UNKNOWN.value),
            metric_name=metric_name,
            window=window,
            points=metric_points,
            direction=direction,
            latest_value=latest,
            previous_value=previous,
            delta=delta,
            delta_percent=delta_percent,
            sample_count=len(metric_points),
            warnings=["insufficient_data_for_direction"] if len(metric_points) < 2 else [],
        )
        series_list.append(asdict(series))
    return {"series": series_list, "series_count": len(series_list), "warnings": warnings}


def _series_by_name(series: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {item.get("metric_name", "unknown"): item for item in series}


def _signal(
    rule: Dict[str, Any],
    series_item: Dict[str, Any],
    severity: Optional[str] = None,
    current_value: Optional[float] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    points = series_item.get("points") or []
    evidence: List[str] = []
    for point in points:
        for ref in point.get("source_record_refs") or []:
            if ref not in evidence:
                evidence.append(ref)
    regression = TrendRegressionSignal(
        regression_id=_new_id("trend_regression"),
        metric_type=series_item.get("metric_type", TrendMetricType.UNKNOWN.value),
        metric_name=series_item.get("metric_name", rule.get("metric_name", "unknown")),
        severity=severity or rule.get("severity", TrendSeverity.MEDIUM.value),
        direction=series_item.get("direction", TrendDirection.INSUFFICIENT_DATA.value),
        current_value=float(current_value if current_value is not None else series_item.get("latest_value") or 0.0),
        baseline_value=series_item.get("previous_value"),
        threshold=None,
        affected_commands=[],
        affected_domains=[],
        evidence_record_refs=evidence,
        recommended_action=rule.get("recommended_action", "diagnostic_only"),
        warnings=warnings or [],
    )
    return asdict(regression)


def detect_trend_regressions(
    series: List[Dict[str, Any]],
    regression_rules: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate regression signals from trend series and design rules."""
    warnings: List[str] = []
    signals: List[Dict[str, Any]] = []
    by_name = _series_by_name(series)
    rules = {rule.get("rule_id"): rule for rule in regression_rules}

    def latest(name: str) -> float:
        item = by_name.get(name) or {}
        return float(item.get("latest_value") or 0.0)

    def add(rule_id: str, metric_name: str, severity: Optional[str] = None, warn: Optional[str] = None) -> None:
        rule = rules.get(rule_id)
        item = by_name.get(metric_name)
        if not rule or not item:
            return
        signal_warnings = [warn] if warn else []
        signals.append(_signal(rule, item, severity=severity, warnings=signal_warnings))

    partial = by_name.get("partial_warning_rate")
    if partial and partial.get("direction") == TrendDirection.WORSENING.value:
        add("partial_warning_rate_increases", "partial_warning_rate")

    critical = by_name.get("critical_signal_count")
    if critical and critical.get("direction") == TrendDirection.WORSENING.value:
        add("critical_count_increases", "critical_signal_count")

    high = by_name.get("high_signal_count")
    if high and high.get("direction") == TrendDirection.WORSENING.value:
        add("high_count_increases", "high_signal_count")

    persist_specs = [
        ("queue_missing_persists", "queue_missing_warning_count"),
        ("unknown_taxonomy_persists", "unknown_taxonomy_count"),
        ("backup_missing_persists", "backup_missing_count"),
        ("rollback_missing_persists", "rollback_missing_count"),
    ]
    for rule_id, metric_name in persist_specs:
        item = by_name.get(metric_name)
        if item and float(item.get("latest_value") or 0.0) > 0:
            add(rule_id, metric_name, warn="insufficient_data_for_persistence_window")

    if latest("invalid_jsonl_line_count") > 0:
        add("invalid_line_count_gt_zero", "invalid_jsonl_line_count", severity=TrendSeverity.HIGH.value)

    if latest("nightly_review_count") == 0:
        add("no_nightly_record_in_expected_window", "nightly_review_count", severity=TrendSeverity.HIGH.value)

    if latest("nightly_review_count") > 0 and latest("feishu_dry_run_count") == 0:
        add("feishu_dry_run_missing_after_nightly", "feishu_dry_run_count", severity=TrendSeverity.MEDIUM.value)

    return {
        "regression_signals": signals,
        "regression_count": len(signals),
        "warnings": warnings,
    }


def generate_dryrun_nightly_trend_report(
    root: Optional[str] = None,
    window: str = TrendWindow.ALL_AVAILABLE.value,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """Generate dry-run NightlyTrendReport projection without writing runtime."""
    warnings: List[str] = []
    errors: List[str] = []
    design_load = load_trend_design_contract()
    warnings.extend(design_load.get("warnings", []))
    errors.extend(design_load.get("errors", []))

    design = design_load.get("design") or {}
    metric_catalog = design.get("metric_catalog") or build_trend_metric_catalog().get("metrics", [])
    regression_rules = design.get("regression_rules") or design_regression_detection_rules().get("rules", [])

    resolved_window = resolve_trend_window(window, start_time, end_time)
    warnings.extend(resolved_window.get("warnings", []))

    fetched = fetch_audit_records_for_trend(
        root=root,
        window=resolved_window.get("window", window),
        start_time=resolved_window.get("start_time"),
        end_time=resolved_window.get("end_time"),
        limit=limit,
    )
    warnings.extend(fetched.get("warnings", []))
    errors.extend(fetched.get("errors", []))
    records = fetched.get("records") or []
    scan_summary = fetched.get("scan_summary") or {}

    points_result = build_trend_points(records, metric_catalog, resolved_window.get("window", window), scan_summary)
    series_result = build_trend_series(points_result.get("points", []), resolved_window.get("window", window))
    regression_result = detect_trend_regressions(series_result.get("series", []), regression_rules)
    warnings.extend(points_result.get("warnings", []))
    warnings.extend(series_result.get("warnings", []))
    warnings.extend(regression_result.get("warnings", []))

    if errors:
        status = TrendProjectionStatus.QUERY_ERROR.value
    elif not records:
        status = TrendProjectionStatus.INSUFFICIENT_DATA.value
        warnings.append("insufficient_audit_records_for_trend")
    elif warnings:
        status = TrendProjectionStatus.PARTIAL_WARNING.value
    else:
        status = TrendProjectionStatus.OK.value

    query_summary = summarize_audit_query_result(fetched.get("query_result", {}))
    report = NightlyTrendReport(
        trend_report_id=_new_id("nightly_trend_report"),
        generated_at=_now(),
        status=status,
        window=resolved_window.get("window", window),
        source_query_refs=[fetched.get("query_result", {}).get("query_id", "unknown_query")],
        total_records_analyzed=len(records),
        series=series_result.get("series", []),
        regression_signals=regression_result.get("regression_signals", []),
        summary={
            "point_count": points_result.get("point_count", 0),
            "series_count": series_result.get("series_count", 0),
            "regression_count": regression_result.get("regression_count", 0),
            "query_status": fetched.get("query_result", {}).get("status"),
            "total_invalid_lines": _scan_invalid_lines(scan_summary),
        },
        warnings=_dedupe(warnings),
        errors=_dedupe(errors),
    )

    return {
        "trend_report": asdict(report),
        "design_ref": {
            "exists": design_load.get("exists", False),
            "path": str(DEFAULT_CONTRACT_JSON),
        },
        "query_summary": query_summary,
        "warnings": _dedupe(warnings),
        "errors": _dedupe(errors),
    }


def _dedupe(values: List[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def summarize_trend_report(trend_report: Dict[str, Any]) -> Dict[str, Any]:
    series = trend_report.get("series") or []
    regressions = trend_report.get("regression_signals") or []
    by_metric_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    for item in series:
        metric_type = item.get("metric_type", TrendMetricType.UNKNOWN.value)
        by_metric_type[metric_type] = by_metric_type.get(metric_type, 0) + 1
    for signal in regressions:
        severity = signal.get("severity", TrendSeverity.UNKNOWN.value)
        by_severity[severity] = by_severity.get(severity, 0) + 1
    top_regressions = sorted(
        regressions,
        key=lambda item: ["critical", "high", "medium", "low", "info", "unknown"].index(
            item.get("severity", "unknown") if item.get("severity", "unknown") in ["critical", "high", "medium", "low", "info", "unknown"] else "unknown"
        ),
    )[:10]
    return {
        "status": trend_report.get("status"),
        "window": trend_report.get("window"),
        "total_records_analyzed": trend_report.get("total_records_analyzed", 0),
        "series_count": len(series),
        "regression_count": len(regressions),
        "by_metric_type": by_metric_type,
        "by_severity": by_severity,
        "top_regressions": [
            {
                "metric_name": item.get("metric_name"),
                "severity": item.get("severity"),
                "current_value": item.get("current_value"),
                "recommended_action": item.get("recommended_action"),
                "warnings": item.get("warnings", []),
            }
            for item in top_regressions
        ],
        "warnings": trend_report.get("warnings", []),
        "errors": trend_report.get("errors", []),
    }


def format_trend_report(trend_report: Dict[str, Any], output_format: str = "json") -> Any:
    """Format report without expanding raw records or sensitive payloads."""
    safe_report = _sanitize_report(trend_report)
    fmt = (output_format or "json").lower()
    if fmt == "json":
        return safe_report
    summary = summarize_trend_report(safe_report)
    lines = [
        "Nightly Trend Report Dry-run",
        f"status={summary['status']}",
        f"window={summary['window']}",
        f"total_analyzed={summary['total_records_analyzed']}",
        f"series_count={summary['series_count']}",
        f"regression_count={summary['regression_count']}",
        f"by_severity={summary['by_severity']}",
    ]
    if summary["top_regressions"]:
        lines.append("top_regressions:")
        for regression in summary["top_regressions"]:
            lines.append(
                f"- {regression['severity']} {regression['metric_name']}="
                f"{regression['current_value']} action={regression['recommended_action']}"
            )
    if summary["warnings"]:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in summary["warnings"][:20])
    if summary["errors"]:
        lines.append("errors:")
        lines.extend(f"- {error}" for error in summary["errors"][:20])
    if fmt == "markdown":
        return "\n".join(["# Nightly Trend Report Dry-run", ""] + lines[1:])
    return "\n".join(lines)


def generate_dryrun_trend_projection_sample(
    output_path: Optional[str] = None,
    root: Optional[str] = None,
    window: str = TrendWindow.ALL_AVAILABLE.value,
) -> Dict[str, Any]:
    """Write dry-run trend sample to audit report directory only."""
    target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    dryrun = generate_dryrun_nightly_trend_report(root=root, window=window)
    report = dryrun.get("trend_report", {})
    payload = {
        "dryrun_trend_report": report,
        "trend_summary": summarize_trend_report(report),
        "sample_formatted_markdown": format_trend_report(report, "markdown"),
        "sample_formatted_text": format_trend_report(report, "text"),
        "generated_at": _now(),
        "warnings": dryrun.get("warnings", []),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["output_path"] = str(target)
    return payload


__all__ = [
    "TrendProjectionStatus",
    "TrendAggregationMethod",
    "load_trend_design_contract",
    "resolve_trend_window",
    "fetch_audit_records_for_trend",
    "extract_metric_value_from_records",
    "build_trend_points",
    "build_trend_series",
    "detect_trend_regressions",
    "generate_dryrun_nightly_trend_report",
    "summarize_trend_report",
    "format_trend_report",
    "generate_dryrun_trend_projection_sample",
]
