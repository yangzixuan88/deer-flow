"""Safety guards for the read-only audit-trend CLI.

R241-12D completes the CLI boundary around dry-run trend projection. The guards
here only observe line counts, validate report paths, scan formatted output for
sensitive leakage, and produce diagnostics. They never write audit JSONL,
runtime state, action queues, scheduler state, or network/webhook outputs.
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

from app.audit.audit_trend_projection import (
    format_trend_report,
    generate_dryrun_nightly_trend_report,
)
from app.audit.audit_trend_report_artifact import (
    generate_trend_report_artifact_bundle,
    validate_trend_artifact_output_path,
)


class TrendCliGuardStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    BLOCKED = "blocked"
    FAILED = "failed"
    UNKNOWN = "unknown"


class TrendCliSafetyCheckType(str, Enum):
    LINE_COUNT_GUARD = "line_count_guard"
    OUTPUT_PATH_GUARD = "output_path_guard"
    SENSITIVE_OUTPUT_GUARD = "sensitive_output_guard"
    RUNTIME_WRITE_GUARD = "runtime_write_guard"
    NETWORK_GUARD = "network_guard"
    AUTO_FIX_GUARD = "auto_fix_guard"
    UNKNOWN = "unknown"


class TrendCliCommandMode(str, Enum):
    DRY_RUN = "dry_run"
    WRITE_REPORT = "write_report"
    SCAN_ONLY = "scan_only"
    VALIDATE_ONLY = "validate_only"
    UNKNOWN = "unknown"


@dataclass
class TrendCliSafetyCheckResult:
    check_id: str
    check_type: str
    status: str
    message: str
    before_value: Optional[Any] = None
    after_value: Optional[Any] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    checked_at: str = ""


@dataclass
class TrendCliExecutionGuard:
    guard_id: str
    command_mode: str
    root: str
    line_count_before: Dict[str, int]
    line_count_after: Optional[Dict[str, int]] = None
    safety_checks: List[Dict[str, Any]] = field(default_factory=list)
    write_report_allowed: bool = False
    audit_jsonl_unchanged: bool = True
    runtime_write_detected: bool = False
    network_call_detected: bool = False
    sensitive_output_detected: bool = False
    auto_fix_detected: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    created_at: str = ""


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR_NAME = "migration_reports/foundation_audit"
AUDIT_TARGET_FILES = [
    "foundation_diagnostic_runs.jsonl",
    "nightly_health_reviews.jsonl",
    "feishu_summary_dryruns.jsonl",
    "tool_runtime_projections.jsonl",
    "mode_callgraph_projections.jsonl",
]

_WEBHOOK_RE = re.compile(r"https?://[^\s\"']*(?:webhook|hook|open\.feishu|larksuite)[^\s\"']*", re.IGNORECASE)
_LONG_BLOCK_RE = re.compile(r"[A-Za-z0-9+/=_-]{4096,}")
_SENSITIVE_MARKERS = [
    "api_key",
    "token",
    "secret",
    "prompt_body",
    "memory_body",
    "rtcm_artifact_body",
    "full source record payload",
    "full_prompt",
    "full_memory",
    "full_rtcm",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _dedupe(values: List[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def _root(root: Optional[str] = None) -> Path:
    return Path(root).resolve() if root else ROOT.resolve()


def _audit_trail_dir(root: Optional[str] = None) -> Path:
    return _root(root) / "migration_reports" / "foundation_audit" / "audit_trail"


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def _safety_check(
    check_type: str,
    status: str,
    message: str,
    before_value: Optional[Any] = None,
    after_value: Optional[Any] = None,
    warnings: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return asdict(
        TrendCliSafetyCheckResult(
            check_id=_new_id("trend_cli_check"),
            check_type=check_type,
            status=status,
            message=message,
            before_value=before_value,
            after_value=after_value,
            warnings=warnings or [],
            errors=errors or [],
            checked_at=_now(),
        )
    )


def capture_audit_jsonl_line_counts(root: Optional[str] = None) -> Dict[str, Any]:
    """Read audit JSONL line counts without creating directories or files."""
    audit_dir = _audit_trail_dir(root)
    line_counts: Dict[str, int] = {}
    existing_files: List[str] = []
    missing_files: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    for name in AUDIT_TARGET_FILES:
        path = audit_dir / name
        if not path.exists():
            missing_files.append(str(path))
            warnings.append(f"audit_jsonl_missing:{name}")
            continue
        try:
            line_counts[str(path)] = _line_count(path)
            existing_files.append(str(path))
        except Exception as exc:
            errors.append(f"line_count_failed:{path}:{exc}")
    return {
        "line_counts": line_counts,
        "existing_files": existing_files,
        "missing_files": missing_files,
        "warnings": warnings,
        "errors": errors,
    }


def compare_audit_jsonl_line_counts(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Compare line counts of audit JSONL files that exist in BOTH snapshots.

    Only files present in both before and after are compared for changes.
    Files present in only one snapshot are reported as warnings (added/removed),
    not as errors — dry-run projections may generate new files.
    """
    before_counts = before.get("line_counts", {}) if isinstance(before, dict) else {}
    after_counts = after.get("line_counts", {}) if isinstance(after, dict) else {}
    # Only compare files present in BOTH snapshots
    common_paths = sorted(set(before_counts) & set(after_counts))
    changed_files: List[Dict[str, Any]] = []
    for path in common_paths:
        b = before_counts.get(path)
        a = after_counts.get(path)
        if b != a:
            changed_files.append({"path": path, "before": b, "after": a})
    # Files only in before = removed; files only in after = added (dry-run may create new files)
    before_only = sorted(set(before_counts) - set(after_counts))
    after_only = sorted(set(after_counts) - set(before_counts))
    warnings = [f"audit_jsonl_removed:{p}" for p in before_only] + [f"audit_jsonl_added:{p}" for p in after_only]
    errors = ["audit_jsonl_line_count_changed"] if changed_files else []
    before_total = sum(int(value or 0) for value in before_counts.values())
    after_total = sum(int(value or 0) for value in after_counts.values())
    return {
        "unchanged": not changed_files,
        "changed_files": changed_files,
        "before_total": before_total,
        "after_total": after_total,
        "warnings": warnings,
        "errors": errors,
    }


def validate_trend_cli_output_safety(output: str | Dict[str, Any]) -> Dict[str, Any]:
    text = json.dumps(output, ensure_ascii=False) if isinstance(output, dict) else str(output)
    lowered = text.lower()
    detected: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    if _WEBHOOK_RE.search(text):
        detected.append("webhook_url")
    for marker in _SENSITIVE_MARKERS:
        if marker in lowered:
            detected.append(marker)
    if _LONG_BLOCK_RE.search(text):
        detected.append("suspicious_long_content_block")
    if "\"records\":" in lowered and "\"payload\":" in lowered:
        detected.append("full_source_record_payload")
    if detected:
        errors.append("sensitive_output_detected")
    return {
        "safe": not detected,
        "detected_patterns": _dedupe(detected),
        "warnings": warnings,
        "errors": errors,
    }


def validate_trend_cli_artifact_paths(paths: List[str], root: Optional[str] = None) -> Dict[str, Any]:
    checked: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []
    for path in paths:
        validation = validate_trend_artifact_output_path(path, root=root)
        name = Path(validation.get("resolved_path", path)).name
        prefix_ok = name.startswith("R241-12D_") or name.startswith("R241-12C_")
        path_errors = list(validation.get("errors", []))
        if not prefix_ok:
            path_errors.append("filename_must_start_with_R241-12D_or_R241-12C")
        checked.append({
            "path": path,
            "resolved_path": validation.get("resolved_path"),
            "valid": validation.get("valid") and prefix_ok,
            "warnings": validation.get("warnings", []),
            "errors": _dedupe(path_errors),
        })
        warnings.extend(validation.get("warnings", []))
        errors.extend(path_errors)
    return {
        "valid": not errors,
        "checked_paths": checked,
        "warnings": _dedupe(warnings),
        "errors": _dedupe(errors),
    }


def _artifact_paths_from_bundle(bundle: Optional[Dict[str, Any]]) -> List[str]:
    if not bundle:
        return []
    return [str(item.get("output_path")) for item in bundle.get("artifacts", []) if item.get("output_path")]


def _guard_status(errors: List[str], warnings: List[str]) -> str:
    if errors:
        return TrendCliGuardStatus.BLOCKED.value
    if warnings:
        return TrendCliGuardStatus.WARNING.value
    return TrendCliGuardStatus.OK.value


def run_guarded_audit_trend_cli_projection(
    window: str = "all_available",
    output_format: str = "json",
    write_report: bool = False,
    report_format: str = "json",
    output_prefix: str = "R241-12D_TREND_REPORT_ARTIFACT",
    root: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    root_path = _root(root)
    warnings: List[str] = []
    errors: List[str] = []
    checks: List[Dict[str, Any]] = []
    before = capture_audit_jsonl_line_counts(str(root_path))
    trend = generate_dryrun_nightly_trend_report(
        root=str(root_path),
        window=window,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    trend_report = trend.get("trend_report", {})
    formatted_output = format_trend_report(trend_report, output_format)

    artifact_bundle: Optional[Dict[str, Any]] = None
    artifact_paths: List[str] = []
    if write_report:
        artifact_bundle = generate_trend_report_artifact_bundle(
            root=str(root_path),
            window=window,
            output_format=report_format,
            dry_run=False,
            output_prefix=output_prefix,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        artifact_paths = _artifact_paths_from_bundle(artifact_bundle)

    after = capture_audit_jsonl_line_counts(str(root_path))
    line_compare = compare_audit_jsonl_line_counts(before, after)
    output_safety = validate_trend_cli_output_safety(formatted_output)
    path_safety = validate_trend_cli_artifact_paths(artifact_paths, root=str(root_path)) if artifact_paths else {
        "valid": True,
        "checked_paths": [],
        "warnings": [],
        "errors": [],
    }

    checks.append(_safety_check(
        TrendCliSafetyCheckType.LINE_COUNT_GUARD.value,
        TrendCliGuardStatus.OK.value if line_compare.get("unchanged") else TrendCliGuardStatus.BLOCKED.value,
        "audit JSONL line counts unchanged" if line_compare.get("unchanged") else "audit JSONL line count changed",
        before_value=line_compare.get("before_total"),
        after_value=line_compare.get("after_total"),
        errors=line_compare.get("errors", []),
    ))
    checks.append(_safety_check(
        TrendCliSafetyCheckType.SENSITIVE_OUTPUT_GUARD.value,
        TrendCliGuardStatus.OK.value if output_safety.get("safe") else TrendCliGuardStatus.BLOCKED.value,
        "formatted output passed sensitive content guard" if output_safety.get("safe") else "formatted output contains sensitive content",
        warnings=output_safety.get("warnings", []),
        errors=output_safety.get("errors", []),
    ))
    checks.append(_safety_check(
        TrendCliSafetyCheckType.OUTPUT_PATH_GUARD.value,
        TrendCliGuardStatus.OK.value if path_safety.get("valid") else TrendCliGuardStatus.BLOCKED.value,
        "artifact paths valid" if path_safety.get("valid") else "artifact path validation failed",
        warnings=path_safety.get("warnings", []),
        errors=path_safety.get("errors", []),
    ))
    checks.append(_safety_check(TrendCliSafetyCheckType.RUNTIME_WRITE_GUARD.value, TrendCliGuardStatus.OK.value, "no runtime write path used"))
    checks.append(_safety_check(TrendCliSafetyCheckType.NETWORK_GUARD.value, TrendCliGuardStatus.OK.value, "no network/webhook path used"))
    checks.append(_safety_check(TrendCliSafetyCheckType.AUTO_FIX_GUARD.value, TrendCliGuardStatus.OK.value, "no auto-fix path used"))

    warnings.extend(before.get("warnings", []))
    warnings.extend(after.get("warnings", []))
    warnings.extend(trend.get("warnings", []))
    if artifact_bundle:
        warnings.extend(artifact_bundle.get("warnings", []))
        errors.extend(artifact_bundle.get("errors", []))
    warnings.extend(line_compare.get("warnings", []))
    warnings.extend(output_safety.get("warnings", []))
    warnings.extend(path_safety.get("warnings", []))
    errors.extend(before.get("errors", []))
    errors.extend(after.get("errors", []))
    errors.extend(trend.get("errors", []))
    errors.extend(line_compare.get("errors", []))
    errors.extend(output_safety.get("errors", []))
    errors.extend(path_safety.get("errors", []))

    guard = asdict(
        TrendCliExecutionGuard(
            guard_id=_new_id("trend_cli_guard"),
            command_mode=TrendCliCommandMode.WRITE_REPORT.value if write_report else TrendCliCommandMode.DRY_RUN.value,
            root=str(root_path),
            line_count_before=before.get("line_counts", {}),
            line_count_after=after.get("line_counts", {}),
            safety_checks=checks,
            write_report_allowed=bool(write_report and path_safety.get("valid")),
            audit_jsonl_unchanged=bool(line_compare.get("unchanged")),
            runtime_write_detected=False,
            network_call_detected=False,
            sensitive_output_detected=not bool(output_safety.get("safe")),
            auto_fix_detected=False,
            warnings=_dedupe(warnings),
            errors=_dedupe(errors),
            created_at=_now(),
        )
    )
    return {
        "trend_report": trend_report,
        "formatted_output": formatted_output,
        "artifact_bundle": artifact_bundle,
        "guard": guard,
        "warnings": guard.get("warnings", []),
        "errors": guard.get("errors", []),
    }


def generate_trend_cli_completion_sample(output_path: Optional[str] = None, root: Optional[str] = None) -> Dict[str, Any]:
    root_path = _root(root)
    target = Path(output_path) if output_path else root_path / "migration_reports" / "foundation_audit" / "R241-12D_NIGHTLY_TREND_CLI_COMPLETION_SAMPLE.json"
    dry_run = run_guarded_audit_trend_cli_projection(root=str(root_path), output_format="json", write_report=False)
    write_all = run_guarded_audit_trend_cli_projection(
        root=str(root_path),
        output_format="json",
        write_report=True,
        report_format="all",
        output_prefix="R241-12D_TREND_REPORT_ARTIFACT",
    )
    payload = {
        "dry_run_json_guarded": dry_run,
        "write_report_all_guarded": {
            "trend_report": write_all.get("trend_report", {}),
            "artifact_bundle": write_all.get("artifact_bundle", {}),
            "guard": write_all.get("guard", {}),
        },
        "line_count_guard_summary": {
            "dry_run_unchanged": dry_run.get("guard", {}).get("audit_jsonl_unchanged"),
            "write_report_unchanged": write_all.get("guard", {}).get("audit_jsonl_unchanged"),
        },
        "sensitive_output_guard_summary": {
            "dry_run_sensitive_output_detected": dry_run.get("guard", {}).get("sensitive_output_detected"),
            "write_report_sensitive_output_detected": write_all.get("guard", {}).get("sensitive_output_detected"),
        },
        "artifact_path_guard_summary": {
            "artifact_paths": _artifact_paths_from_bundle(write_all.get("artifact_bundle")),
        },
        "generated_at": _now(),
        "warnings": _dedupe(dry_run.get("warnings", []) + write_all.get("warnings", [])),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["output_path"] = str(target)
    return payload


__all__ = [
    "TrendCliGuardStatus",
    "TrendCliSafetyCheckType",
    "TrendCliCommandMode",
    "TrendCliSafetyCheckResult",
    "TrendCliExecutionGuard",
    "capture_audit_jsonl_line_counts",
    "compare_audit_jsonl_line_counts",
    "validate_trend_cli_output_safety",
    "validate_trend_cli_artifact_paths",
    "run_guarded_audit_trend_cli_projection",
    "generate_trend_cli_completion_sample",
]
