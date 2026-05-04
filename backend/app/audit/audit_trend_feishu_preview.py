"""Feishu/Lark trend payload CLI preview (R241-13C).

This module provides CLI-friendly preview functions for the Feishu trend payload.
It formats the projection for human review (TEXT/MARKDOWN/JSON) without writing
artifacts or sending messages.

Input sources (read-only, no writes):
  - audit_trend_feishu_projection: projection + validation
  - audit_trend_projection:         trend_report, trend_summary
  - audit_trend_cli_guard:          guard result

Output (no sends, no writes by default):
  - Formatted preview strings (TEXT/MARKDOWN/JSON)
  - Preview diagnostic result dict
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.audit.audit_trend_feishu_contract import (
    FeishuTrendPreviewFormat,
    FeishuTrendPreviewStatus,
    FeishuTrendPayloadProjection,
    FeishuTrendValidationResult,
)
from app.audit.audit_trend_feishu_projection import (
    build_feishu_trend_payload_projection,
    validate_feishu_trend_payload_projection,
    generate_feishu_trend_payload_projection,
)


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_SAMPLE_PATH = REPORT_DIR / "R241-13C_AUDIT_TREND_FEISHU_CLI_PREVIEW_SAMPLE.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# 1. format_feishu_trend_payload_preview
# ─────────────────────────────────────────────────────────────────────────────

def format_feishu_trend_payload_preview(
    payload: Dict[str, Any],
    format: str = "text",
) -> str:
    """Format a FeishuTrendPayloadProjection for CLI preview.

    Args:
        payload: FeishuTrendPayloadProjection dict
        format: one of "text", "markdown", "json"

    Returns:
        Formatted string for terminal output

    No writes, no network calls, no Feishu sends.
    """
    if format == FeishuTrendPreviewFormat.JSON.value:
        result = {
            "payload_id": payload.get("payload_id"),
            "status": payload.get("status"),
            "title": payload.get("title"),
            "source_window": payload.get("source_window"),
            "source_record_count": payload.get("source_record_count"),
            "regression_count": payload.get("regression_count"),
            "by_severity": payload.get("by_severity", {}),
            "sections": payload.get("sections", []),
            "send_allowed": payload.get("send_allowed"),
            "no_webhook_call": payload.get("no_webhook_call"),
            "no_runtime_write": payload.get("no_runtime_write"),
            "no_auto_fix": payload.get("no_auto_fix"),
            "warnings": payload.get("warnings", []),
            "errors": payload.get("errors", []),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    validation = payload.get("validation") or {}
    sections = payload.get("sections", [])

    if format == FeishuTrendPreviewFormat.TEXT.value:
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append("FEISHU TREND PAYLOAD PREVIEW")
        lines.append("=" * 60)
        lines.append(f"Payload ID  : {payload.get('payload_id', 'N/A')}")
        lines.append(f"Status      : {payload.get('status', 'unknown')}")
        lines.append(f"Title       : {payload.get('title', 'N/A')}")
        lines.append(f"Window      : {payload.get('source_window', 'N/A')}")
        lines.append(f"Records     : {payload.get('source_record_count', 0)}")
        lines.append(f"Regressions : {payload.get('regression_count', 0)}")
        lines.append(f"By Severity : {payload.get('by_severity', {})}")

        lines.append("")
        lines.append("-" * 40)
        lines.append("SAFETY FLAGS")
        lines.append("-" * 40)
        lines.append(f"  send_allowed          : {payload.get('send_allowed')}")
        lines.append(f"  no_webhook_call       : {payload.get('no_webhook_call')}")
        lines.append(f"  no_runtime_write      : {payload.get('no_runtime_write')}")
        lines.append(f"  no_action_queue_write : {payload.get('no_action_queue_write')}")
        lines.append(f"  no_auto_fix           : {payload.get('no_auto_fix')}")

        if sections:
            lines.append("")
            lines.append("-" * 40)
            lines.append("SECTIONS")
            lines.append("-" * 40)
            for section in sections:
                lines.append(f"\n[{section.get('section_type', 'unknown').upper()}] {section.get('title', '')}")
                content = section.get("content", "")
                if content:
                    lines.append(f"  {content}")
                items = section.get("items") or []
                for item in items:
                    label = item.get("label", "")
                    value = item.get("value", "")
                    if value:
                        lines.append(f"  - {label}: {value}")
                    else:
                        lines.append(f"  - {label}")

        if validation:
            lines.append("")
            lines.append("-" * 40)
            lines.append("VALIDATION")
            lines.append("-" * 40)
            lines.append(f"  valid                 : {validation.get('valid')}")
            lines.append(f"  send_allowed_is_false: {validation.get('send_allowed_is_false')}")
            lines.append(f"  no_webhook_call_is_true: {validation.get('no_webhook_call_is_true')}")
            lines.append(f"  sensitive_content_detected: {validation.get('sensitive_content_detected')}")
            lines.append(f"  line_count_changed    : {validation.get('line_count_changed')}")
            blocked = validation.get("blocked_reasons") or []
            if blocked:
                lines.append(f"  blocked_reasons       : {', '.join(blocked)}")
            else:
                lines.append("  blocked_reasons       : (none)")

        warnings = payload.get("warnings") or []
        if warnings:
            lines.append("")
            lines.append("-" * 40)
            lines.append(f"WARNINGS ({len(warnings)})")
            lines.append("-" * 40)
            for w in warnings[:10]:
                lines.append(f"  ! {w}")

        errors = payload.get("errors") or []
        if errors:
            lines.append("")
            lines.append("-" * 40)
            lines.append(f"ERRORS ({len(errors)})")
            lines.append("-" * 40)
            for e in errors:
                lines.append(f"  X {e}")

        lines.append("")
        lines.append("=" * 60)
        lines.append("END OF PREVIEW — dry-run only, no message sent")
        lines.append("=" * 60)
        return "\n".join(lines)

    if format == FeishuTrendPreviewFormat.MARKDOWN.value:
        md_lines: List[str] = []
        md_lines.append("# Feishu Trend Payload Preview")
        md_lines.append("")
        md_lines.append(f"**Payload ID:** `{payload.get('payload_id', 'N/A')}`")
        md_lines.append(f"**Status:** `{payload.get('status', 'unknown')}`")
        md_lines.append(f"**Title:** {payload.get('title', 'N/A')}")
        md_lines.append(f"**Window:** `{payload.get('source_window', 'N/A')}`")
        md_lines.append(f"**Records:** {payload.get('source_record_count', 0)}")
        md_lines.append(f"**Regressions:** {payload.get('regression_count', 0)}")
        md_lines.append(f"**By Severity:** `{payload.get('by_severity', {})}`")
        md_lines.append("")
        md_lines.append("## Safety Flags")
        md_lines.append("")
        md_lines.append("| Flag | Value |")
        md_lines.append("|------|-------|")
        md_lines.append(f"| send_allowed | `{payload.get('send_allowed')}` |")
        md_lines.append(f"| no_webhook_call | `{payload.get('no_webhook_call')}` |")
        md_lines.append(f"| no_runtime_write | `{payload.get('no_runtime_write')}` |")
        md_lines.append(f"| no_action_queue_write | `{payload.get('no_action_queue_write')}` |")
        md_lines.append(f"| no_auto_fix | `{payload.get('no_auto_fix')}` |")

        if sections:
            md_lines.append("")
            md_lines.append("## Sections")
            md_lines.append("")
            for section in sections:
                section_type = section.get("section_type", "unknown")
                title = section.get("title", "")
                content = section.get("content", "")
                items = section.get("items") or []
                md_lines.append(f"### [{section_type.upper()}] {title}")
                if content:
                    md_lines.append(f"\n{content}")
                if items:
                    md_lines.append("")
                    for item in items:
                        label = item.get("label", "")
                        value = item.get("value", "")
                        if value:
                            md_lines.append(f"- **{label}:** `{value}`")
                        else:
                            md_lines.append(f"- {label}")

        if validation:
            md_lines.append("")
            md_lines.append("## Validation")
            md_lines.append("")
            md_lines.append(f"- **Valid:** `{validation.get('valid')}`")
            md_lines.append(f"- **send_allowed_is_false:** `{validation.get('send_allowed_is_false')}`")
            md_lines.append(f"- **no_webhook_call_is_true:** `{validation.get('no_webhook_call_is_true')}`")
            md_lines.append(f"- **sensitive_content_detected:** `{validation.get('sensitive_content_detected')}`")
            md_lines.append(f"- **line_count_changed:** `{validation.get('line_count_changed')}`")
            blocked = validation.get("blocked_reasons") or []
            if blocked:
                for reason in blocked:
                    md_lines.append(f"- blocked: `{reason}`")
            else:
                md_lines.append("- **blocked_reasons:** (none)")

        warnings = payload.get("warnings") or []
        if warnings:
            md_lines.append("")
            md_lines.append(f"## Warnings ({len(warnings)})")
            md_lines.append("")
            for w in warnings[:10]:
                md_lines.append(f"- `{w}`")

        errors = payload.get("errors") or []
        if errors:
            md_lines.append("")
            md_lines.append(f"## Errors ({len(errors)})")
            md_lines.append("")
            for e in errors:
                md_lines.append(f"- `{e}`")

        md_lines.append("")
        md_lines.append("---")
        md_lines.append("*End of preview — dry-run only, no message sent*")
        return "\n".join(md_lines)

    return format_feishu_trend_payload_preview(payload, FeishuTrendPreviewFormat.TEXT.value)


# ─────────────────────────────────────────────────────────────────────────────
# 2. run_feishu_trend_preview_diagnostic
# ─────────────────────────────────────────────────────────────────────────────

def run_feishu_trend_preview_diagnostic(
    window: str = "all_available",
    format: str = "text",
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Run end-to-end Feishu trend preview diagnostic.

    Steps:
      1. generate_feishu_trend_payload_projection(...) — projection + validation
      2. format_feishu_trend_payload_preview(...)      — format for output

    Args:
        window: trend window (last_7d, last_30d, all_available)
        format: output format (text, markdown, json)
        root: optional root path override

    Returns:
        dict with keys:
          - status: FeishuTrendPreviewStatus value
          - preview: formatted string
          - payload: the projection dict
          - validation: the validation result dict
          - preview_format: the format used
          - generated_at: ISO timestamp
          - warnings: list of warnings
          - errors: list of errors

    No writes, no network calls, no Feishu sends.
    """
    errors: List[str] = []
    warnings: List[str] = []

    try:
        payload = generate_feishu_trend_payload_projection(
            root=root,
            window=window,
        )
        warnings.extend(payload.get("warnings") or [])
        errors.extend(payload.get("errors") or [])

        validation = payload.get("validation") or {}
        valid = validation.get("valid", False)

        if not valid:
            status = FeishuTrendPreviewStatus.VALIDATION_ERROR.value
        elif not payload.get("sections"):
            status = FeishuTrendPreviewStatus.NO_DATA.value
        else:
            status = FeishuTrendPreviewStatus.SUCCESS.value

        try:
            preview = format_feishu_trend_payload_preview(payload, format=format)
        except Exception as exc:
            warnings.append(f"preview_format_failed:{exc}")
            preview = format_feishu_trend_payload_preview(payload, format=FeishuTrendPreviewFormat.TEXT.value)

        return {
            "status": status,
            "preview": preview,
            "payload_id": payload.get("payload_id"),
            "validation": validation,
            "preview_format": format,
            "generated_at": payload.get("generated_at", _now()),
            "warnings": warnings,
            "errors": errors,
        }

    except Exception as exc:
        errors.append(f"preview_diagnostic_failed:{exc}")
        return {
            "status": FeishuTrendPreviewStatus.FAILED.value,
            "preview": "",
            "payload_id": None,
            "validation": {},
            "preview_format": format,
            "generated_at": _now(),
            "warnings": warnings,
            "errors": errors,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 3. generate_feishu_trend_preview_sample
# ─────────────────────────────────────────────────────────────────────────────

def generate_feishu_trend_preview_sample(
    output_path: Optional[str] = None,
    root: Optional[str] = None,
    format: str = "text",
) -> Dict[str, Any]:
    """Generate R241-13C preview sample to migration_reports/foundation_audit.

    Writes a sample JSON file only. Does NOT write audit JSONL, runtime,
    action queue, or send Feishu messages.

    Args:
        output_path: optional override for sample output path
        root: optional root path override
        format: preview format for the sample (text/markdown/json)

    Returns:
        dict with all sample fields including output_path
    """
    target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH

    diagnostic = run_feishu_trend_preview_diagnostic(
        window="all_available",
        format=format,
        root=root,
    )

    sample = {
        "preview_sample": diagnostic,
        "format_used": format,
        "generated_at": _now(),
        "output_path": str(target),
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    return sample


__all__ = [
    "format_feishu_trend_payload_preview",
    "run_feishu_trend_preview_diagnostic",
    "generate_feishu_trend_preview_sample",
]
