"""Trend report artifact writer for R241-12C.

This module writes only explicit R241-12C trend report artifacts under
migration_reports/foundation_audit. It never writes audit_trail JSONL, runtime
state, action queue, or scheduler/Feishu/network outputs.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.audit.audit_trend_projection import (
    format_trend_report,
    generate_dryrun_nightly_trend_report,
    summarize_trend_report,
)


class TrendArtifactFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"
    TEXT = "text"
    ALL = "all"
    UNKNOWN = "unknown"


class TrendArtifactWriteStatus(str, Enum):
    WRITTEN = "written"
    SKIPPED_DRY_RUN = "skipped_dry_run"
    BLOCKED_INVALID_PATH = "blocked_invalid_path"
    FAILED = "failed"
    UNKNOWN = "unknown"


class TrendArtifactType(str, Enum):
    TREND_REPORT_JSON = "trend_report_json"
    TREND_REPORT_MARKDOWN = "trend_report_markdown"
    TREND_REPORT_TEXT = "trend_report_text"
    TREND_REPORT_BUNDLE_SAMPLE = "trend_report_bundle_sample"
    UNKNOWN = "unknown"


@dataclass
class TrendReportArtifactWriteResult:
    artifact_result_id: str
    artifact_type: str
    format: str
    status: str
    output_path: str
    bytes_written: int
    source_trend_report_id: Optional[str] = None
    source_window: Optional[str] = None
    source_record_count: int = 0
    series_count: int = 0
    regression_count: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    written_at: Optional[str] = None


@dataclass
class TrendReportArtifactBundle:
    bundle_id: str
    generated_at: str
    root: str
    window: str
    source_trend_report_id: str
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_JSON_ARTIFACT = REPORT_DIR / "R241-12C_TREND_REPORT_ARTIFACT.json"
DEFAULT_MD_ARTIFACT = REPORT_DIR / "R241-12C_TREND_REPORT_ARTIFACT.md"
DEFAULT_TEXT_ARTIFACT = REPORT_DIR / "R241-12C_TREND_REPORT_ARTIFACT.txt"
DEFAULT_SAMPLE_ARTIFACT = REPORT_DIR / "R241-12C_TREND_REPORT_ARTIFACT_SAMPLE.json"

_SENSITIVE_WORDS = (
    "secret",
    "token",
    "password",
    "api_key",
    "webhook",
    "webhook_url",
    "authorization",
    "body",
    "full_body",
    "full_content",
    "prompt_body",
    "memory_body",
    "rtcm_body",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _dedupe(values: List[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def _format_to_suffix(output_format: str) -> str:
    fmt = (output_format or "").lower()
    if fmt == TrendArtifactFormat.JSON.value:
        return ".json"
    if fmt == TrendArtifactFormat.MARKDOWN.value:
        return ".md"
    if fmt == TrendArtifactFormat.TEXT.value:
        return ".txt"
    return ""


def _artifact_type(output_format: str) -> str:
    fmt = (output_format or "").lower()
    if fmt == TrendArtifactFormat.JSON.value:
        return TrendArtifactType.TREND_REPORT_JSON.value
    if fmt == TrendArtifactFormat.MARKDOWN.value:
        return TrendArtifactType.TREND_REPORT_MARKDOWN.value
    if fmt == TrendArtifactFormat.TEXT.value:
        return TrendArtifactType.TREND_REPORT_TEXT.value
    return TrendArtifactType.UNKNOWN.value


def _sanitize(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for child_key, child_value in value.items():
            lower = str(child_key).lower()
            if any(word in lower for word in _SENSITIVE_WORDS):
                result[child_key] = "[REDACTED]"
            elif lower == "source_record_refs":
                refs = child_value if isinstance(child_value, list) else []
                result[child_key] = refs[:20]
                if len(refs) > 20:
                    result["source_record_refs_truncated"] = True
                    result["source_record_refs_total"] = len(refs)
            else:
                result[child_key] = _sanitize(child_value, lower)
        return result
    if isinstance(value, list):
        return [_sanitize(item, key) for item in value]
    if isinstance(value, str) and any(word in value.lower() for word in ("secret=", "token=", "webhook_url=", "authorization:")):
        return "[REDACTED]"
    return value


def _report_dir_for_root(root: Optional[str] = None) -> Path:
    root_path = Path(root).resolve() if root else ROOT.resolve()
    return root_path / "migration_reports" / "foundation_audit"


def _safe_output_prefix(output_prefix: Optional[str] = None) -> str:
    prefix = output_prefix or "R241-12C_TREND_REPORT_ARTIFACT"
    if prefix not in {"R241-12C_TREND_REPORT_ARTIFACT", "R241-12D_TREND_REPORT_ARTIFACT"}:
        return "R241-12C_TREND_REPORT_ARTIFACT"
    return prefix


def _default_path_for_format(output_format: str, root: Optional[str] = None, output_prefix: Optional[str] = None) -> Path:
    report_dir = _report_dir_for_root(root)
    prefix = _safe_output_prefix(output_prefix)
    fmt = (output_format or "").lower()
    if fmt == TrendArtifactFormat.JSON.value:
        return report_dir / f"{prefix}.json"
    if fmt == TrendArtifactFormat.MARKDOWN.value:
        return report_dir / f"{prefix}.md"
    if fmt == TrendArtifactFormat.TEXT.value:
        return report_dir / f"{prefix}.txt"
    return report_dir / f"{prefix}.json"


def validate_trend_artifact_output_path(path: str, root: Optional[str] = None) -> Dict[str, Any]:
    """Validate that an artifact path is inside the R241-12C report boundary."""
    warnings: List[str] = []
    errors: List[str] = []
    try:
        root_path = Path(root).resolve() if root else ROOT.resolve()
        report_dir = _report_dir_for_root(str(root_path)).resolve()
        raw = Path(path)
        if ".." in raw.parts:
            errors.append("path_traversal_not_allowed")
        target = raw if raw.is_absolute() else root_path / raw
        resolved = target.resolve(strict=False)
        try:
            resolved.relative_to(report_dir)
        except ValueError:
            errors.append("path_not_under_foundation_audit")
        if "audit_trail" in [part.lower() for part in resolved.parts]:
            errors.append("audit_trail_path_forbidden")
        if resolved.suffix.lower() not in {".json", ".md", ".txt"}:
            errors.append("invalid_artifact_suffix")
        if not (resolved.name.startswith("R241-12C_") or resolved.name.startswith("R241-12D_")):
            errors.append("filename_must_start_with_R241-12C_or_R241-12D")
        lower_path = str(resolved).lower()
        forbidden_terms = (
            "governance_state",
            "experiment_queue",
            "memory.json",
            "asset_registry",
            "latest_binding_report",
            "checkpoints.db",
            "\\.deerflow\\rtcm",
            "\\backend\\.deer-flow",
            "\\runtime\\",
            "\\action_queue",
        )
        if any(term in lower_path for term in forbidden_terms):
            errors.append("runtime_path_forbidden")
        if resolved.exists() and resolved.is_symlink():
            errors.append("symlink_artifact_path_forbidden")
    except Exception as exc:
        errors.append(f"path_validation_failed:{exc}")
        resolved = Path(path)

    return {
        "valid": not errors,
        "resolved_path": str(resolved),
        "warnings": warnings,
        "errors": _dedupe(errors),
    }


def render_trend_report_artifact_content(
    trend_report: Dict[str, Any],
    output_format: str = TrendArtifactFormat.JSON.value,
) -> Dict[str, Any]:
    """Render trend report artifact content without exposing raw records."""
    warnings: List[str] = []
    errors: List[str] = []
    fmt = (output_format or TrendArtifactFormat.JSON.value).lower()
    safe_report = _sanitize(trend_report)
    summary = summarize_trend_report(safe_report)

    if fmt == TrendArtifactFormat.JSON.value:
        content: Any = {
            "artifact_notice": "projection_only_no_auto_fix",
            "trend_report": safe_report,
            "summary": summary,
            "warnings": warnings,
            "errors": errors,
        }
        try:
            json.dumps(content, ensure_ascii=False)
        except TypeError as exc:
            errors.append(f"json_render_not_serializable:{exc}")
    elif fmt == TrendArtifactFormat.MARKDOWN.value:
        top_lines = [
            f"- `{item.get('severity')}` `{item.get('metric_name')}` = `{item.get('current_value')}`; action=`{item.get('recommended_action')}`"
            for item in summary.get("top_regressions", [])
        ] or ["- none"]
        content = "\n".join([
            "# R241-12C Trend Report Artifact",
            "",
            "> projection-only artifact. No audit JSONL write. No runtime write. No action queue. No network. no-auto-fix.",
            "",
            f"- trend_report_id: `{safe_report.get('trend_report_id')}`",
            f"- status: `{summary.get('status')}`",
            f"- window: `{summary.get('window')}`",
            f"- total_records_analyzed: `{summary.get('total_records_analyzed')}`",
            f"- series_count: `{summary.get('series_count')}`",
            f"- regression_count: `{summary.get('regression_count')}`",
            f"- by_severity: `{summary.get('by_severity')}`",
            "",
            "## Top Regressions",
            "",
            "\n".join(top_lines),
            "",
            "## Warnings / Errors",
            "",
            f"- warnings: `{summary.get('warnings')}`",
            f"- errors: `{summary.get('errors')}`",
            "",
        ])
    elif fmt == TrendArtifactFormat.TEXT.value:
        top = summary.get("top_regressions", [])
        top_text = "; ".join(
            f"{item.get('severity')} {item.get('metric_name')}={item.get('current_value')}"
            for item in top
        ) or "none"
        content = "\n".join([
            "R241-12C Trend Report Artifact",
            "projection-only; no-auto-fix; no audit JSONL write; no runtime write",
            f"trend_report_id={safe_report.get('trend_report_id')}",
            f"status={summary.get('status')}",
            f"window={summary.get('window')}",
            f"total_records_analyzed={summary.get('total_records_analyzed')}",
            f"series_count={summary.get('series_count')}",
            f"regression_count={summary.get('regression_count')}",
            f"by_severity={summary.get('by_severity')}",
            f"regression_summary={top_text}",
            f"warnings={summary.get('warnings')}",
            f"errors={summary.get('errors')}",
        ])
    else:
        errors.append(f"unsupported_artifact_format:{output_format}")
        content = ""

    return {
        "content": content,
        "format": fmt,
        "warnings": warnings,
        "errors": errors,
    }


def _content_to_text(content: Any, output_format: str) -> str:
    if output_format == TrendArtifactFormat.JSON.value:
        return json.dumps(content, ensure_ascii=False, indent=2)
    return str(content)


def write_trend_report_artifact(
    trend_report: Dict[str, Any],
    output_path: str,
    output_format: str = TrendArtifactFormat.JSON.value,
    dry_run: bool = False,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate, render, and optionally write a single trend report artifact."""
    fmt = (output_format or TrendArtifactFormat.JSON.value).lower()
    validation = validate_trend_artifact_output_path(output_path, root=root)
    summary = summarize_trend_report(trend_report)
    result = TrendReportArtifactWriteResult(
        artifact_result_id=_new_id("trend_artifact_result"),
        artifact_type=_artifact_type(fmt),
        format=fmt,
        status=TrendArtifactWriteStatus.UNKNOWN.value,
        output_path=validation.get("resolved_path", output_path),
        bytes_written=0,
        source_trend_report_id=trend_report.get("trend_report_id"),
        source_window=trend_report.get("window"),
        source_record_count=int(trend_report.get("total_records_analyzed") or 0),
        series_count=int(summary.get("series_count") or 0),
        regression_count=int(summary.get("regression_count") or 0),
        warnings=list(validation.get("warnings", [])),
        errors=list(validation.get("errors", [])),
        written_at=None,
    )
    if not validation.get("valid"):
        result.status = TrendArtifactWriteStatus.BLOCKED_INVALID_PATH.value
        return asdict(result)

    rendered = render_trend_report_artifact_content(trend_report, fmt)
    result.warnings.extend(rendered.get("warnings", []))
    result.errors.extend(rendered.get("errors", []))
    if result.errors:
        result.status = TrendArtifactWriteStatus.FAILED.value
        return asdict(result)

    text = _content_to_text(rendered.get("content"), fmt)
    if dry_run:
        result.status = TrendArtifactWriteStatus.SKIPPED_DRY_RUN.value
        result.bytes_written = len(text.encode("utf-8"))
        return asdict(result)

    try:
        target = Path(result.output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        result.status = TrendArtifactWriteStatus.WRITTEN.value
        result.bytes_written = len(text.encode("utf-8"))
        result.written_at = _now()
    except Exception as exc:
        result.status = TrendArtifactWriteStatus.FAILED.value
        result.errors.append(f"artifact_write_failed:{exc}")
    return asdict(result)


def generate_trend_report_artifact_bundle(
    root: Optional[str] = None,
    window: str = "all_available",
    output_format: str = TrendArtifactFormat.ALL.value,
    dry_run: bool = False,
    output_prefix: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """Generate trend report artifacts under migration_reports/foundation_audit."""
    dryrun = generate_dryrun_nightly_trend_report(root=root, window=window, start_time=start_time, end_time=end_time, limit=limit)
    trend_report = dryrun.get("trend_report", {})
    summary = summarize_trend_report(trend_report)
    fmt = (output_format or TrendArtifactFormat.ALL.value).lower()
    formats = [fmt] if fmt in {TrendArtifactFormat.JSON.value, TrendArtifactFormat.MARKDOWN.value, TrendArtifactFormat.TEXT.value} else [
        TrendArtifactFormat.JSON.value,
        TrendArtifactFormat.MARKDOWN.value,
        TrendArtifactFormat.TEXT.value,
    ]

    artifacts = [
        write_trend_report_artifact(
            trend_report,
            str(_default_path_for_format(item, root=root, output_prefix=output_prefix)),
            item,
            dry_run=dry_run,
            root=root,
        )
        for item in formats
    ]
    warnings = _dedupe(list(dryrun.get("warnings", [])) + [w for artifact in artifacts for w in artifact.get("warnings", [])])
    errors = _dedupe(list(dryrun.get("errors", [])) + [e for artifact in artifacts for e in artifact.get("errors", [])])

    bundle = TrendReportArtifactBundle(
        bundle_id=_new_id("trend_artifact_bundle"),
        generated_at=_now(),
        root=str(Path(root).resolve()) if root else str(ROOT),
        window=window,
        source_trend_report_id=trend_report.get("trend_report_id", "unknown_trend_report"),
        artifacts=artifacts,
        summary=summary,
        warnings=warnings,
        errors=errors,
    )
    return asdict(bundle)


def generate_trend_report_artifact_sample(
    output_path: Optional[str] = None,
    root: Optional[str] = None,
    window: str = "all_available",
) -> Dict[str, Any]:
    """Generate R241-12C audit sample JSON under foundation_audit."""
    target = Path(output_path) if output_path else _report_dir_for_root(root) / "R241-12C_TREND_REPORT_ARTIFACT_SAMPLE.json"
    dryrun_bundle = generate_trend_report_artifact_bundle(root=root, window=window, output_format=TrendArtifactFormat.ALL.value, dry_run=True)
    real_bundle = generate_trend_report_artifact_bundle(root=root, window=window, output_format=TrendArtifactFormat.ALL.value, dry_run=False)
    payload = {
        "dryrun_bundle": dryrun_bundle,
        "real_artifact_bundle_summary": {
            "bundle_id": real_bundle.get("bundle_id"),
            "artifact_count": len(real_bundle.get("artifacts", [])),
            "artifact_statuses": [artifact.get("status") for artifact in real_bundle.get("artifacts", [])],
            "summary": real_bundle.get("summary", {}),
            "warnings": real_bundle.get("warnings", []),
            "errors": real_bundle.get("errors", []),
        },
        "generated_at": _now(),
        "warnings": _dedupe(list(dryrun_bundle.get("warnings", [])) + list(real_bundle.get("warnings", []))),
    }
    validation = validate_trend_artifact_output_path(str(target), root=root)
    if not validation.get("valid"):
        payload["warnings"].extend(validation.get("errors", []))
        payload["output_path"] = str(target)
        return payload
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["output_path"] = str(target)
    return payload


__all__ = [
    "TrendArtifactFormat",
    "TrendArtifactWriteStatus",
    "TrendArtifactType",
    "TrendReportArtifactWriteResult",
    "TrendReportArtifactBundle",
    "validate_trend_artifact_output_path",
    "render_trend_report_artifact_content",
    "write_trend_report_artifact",
    "generate_trend_report_artifact_bundle",
    "generate_trend_report_artifact_sample",
]
