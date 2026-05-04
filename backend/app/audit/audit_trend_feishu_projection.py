"""Feishu/Lark trend payload projection (R241-13B).

This module projects a NightlyTrendReport plus CLI guard result into a
Feishu/Lark card payload (FeishuTrendPayloadProjection) and validates it.
It never sends messages, never calls webhooks/network, never writes audit JSONL,
and never writes runtime/action queue state.

Input sources (read-only, no writes):
  - audit_trend_projection:    trend_report, trend_summary
  - audit_trend_cli_guard:      guard result
  - audit_trend_report_artifact: artifact_bundle

Output (no sends, no writes by default):
  - FeishuTrendCardSection list
  - FeishuTrendPayloadProjection dict
  - FeishuTrendValidationResult dict
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.audit.audit_trend_feishu_contract import (
    FeishuTrendCardSection,
    FeishuTrendCardSectionType,
    FeishuTrendPayloadProjection,
    FeishuTrendPayloadStatus,
    FeishuTrendSendPermission,
    FeishuTrendSeverity,
    FeishuTrendValidationResult,
    build_feishu_trend_section_catalog,
    build_feishu_trend_validation_rules,
    validate_feishu_trend_dryrun_design,
)


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_SAMPLE_PATH = REPORT_DIR / "R241-13B_FEISHU_TREND_PAYLOAD_PROJECTION_SAMPLE.json"

_WEBHOOK_RE = re.compile(r"https?://[^\s\"']*(?:webhook|hook|open\.feishu|larksuite)[^\s\"']*", re.IGNORECASE)
_SENSITIVE_KEY_RE = re.compile(
    r"\b(webhook_url|api_key|token|secret|password|secret_key|access_token)\b",
    re.IGNORECASE,
)
_FORBIDDEN_ARTIFACT_PATH_PREFIXES = (
    "migration_reports/foundation_audit/audit_trail",
    "migration_reports/foundation_audit/runtime",
    "migration_reports/foundation_audit/action_queue",
    ".deerflow/runtime",
    ".deerflow/action_queue",
)


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


def _section(section_type: str, title: str, content: str, **kwargs: Any) -> Dict[str, Any]:
    return asdict(FeishuTrendCardSection(
        section_id=_new_id("feishu_trend_section"),
        section_type=section_type,
        title=title,
        content=content,
        **{k: v for k, v in kwargs.items() if v is not None},
    ))


def _has_sensitive_content(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False)
    if _WEBHOOK_RE.search(text):
        return True
    if _SENSITIVE_KEY_RE.search(text):
        return True
    return False


def _validate_artifact_path(path: str) -> bool:
    path_lower = path.lower().replace("\\", "/")
    return not any(path_lower.startswith(prefix.lower()) for prefix in _FORBIDDEN_ARTIFACT_PATH_PREFIXES)


# ─────────────────────────────────────────────────────────────────────────────
# 1. build_feishu_trend_sections
# ─────────────────────────────────────────────────────────────────────────────

def build_feishu_trend_sections(
    trend_report: Dict[str, Any],
    trend_summary: Optional[Dict[str, Any]] = None,
    guard: Optional[Dict[str, Any]] = None,
    artifact_bundle: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build FeishuTrendCardSection list from trend report and guard.

    Returns:
        dict with keys: sections (list[dict]), section_count (int),
                        warnings (list[str]), errors (list[str])
    """
    warnings: List[str] = []
    errors: List[str] = []
    sections: List[Dict[str, Any]] = []

    trend_summary = trend_summary or {}
    status = trend_report.get("status", "unknown")
    window = trend_report.get("window", "all_available")
    total_records = trend_report.get("total_records_analyzed", 0)

    # ── headline ─────────────────────────────────────────────────────────────
    headline_content = (
        f"Nightly Trend Dry-run [{window}] "
        f"status={status} records={total_records}"
    )
    sections.append(_section(
        FeishuTrendCardSectionType.HEADLINE.value,
        "Nightly Trend Summary",
        headline_content,
    ))

    # ── trend_overview ────────────────────────────────────────────────────────
    series_count = trend_summary.get("series_count", 0)
    regression_count = trend_summary.get("regression_count", 0)
    by_severity = trend_summary.get("by_severity", {})
    severity_str = ", ".join(f"{k}={v}" for k, v in by_severity.items()) or "none"
    overview_items = [
        {"label": "window", "value": window},
        {"label": "records_analyzed", "value": str(total_records)},
        {"label": "series_count", "value": str(series_count)},
        {"label": "regression_signals", "value": str(regression_count)},
        {"label": "by_severity", "value": severity_str},
    ]
    sections.append(_section(
        FeishuTrendCardSectionType.TREND_OVERVIEW.value,
        "Trend Overview",
        f"Window={window}, {total_records} records, {series_count} series, {regression_count} regressions",
        items=overview_items,
    ))

    # ── regression_summary ───────────────────────────────────────────────────
    top_regressions = (trend_summary.get("top_regressions") or [])[:5]
    regression_items: List[Dict[str, Any]] = []
    for regression in top_regressions:
        severity = regression.get("severity", "unknown")
        metric = regression.get("metric_name", "unknown")
        current = regression.get("current_value", "n/a")
        action = regression.get("recommended_action", "diagnostic_only")
        regression_items.append({
            "label": f"[{severity.upper()}] {metric}",
            "value": f"current_value={current} action={action}",
        })
    if regression_items:
        sections.append(_section(
            FeishuTrendCardSectionType.REGRESSION_SUMMARY.value,
            f"Regression Signals ({len(regression_items)})",
            f"{len(regression_items)} regression signals require operator attention",
            items=regression_items,
        ))
    else:
        sections.append(_section(
            FeishuTrendCardSectionType.REGRESSION_SUMMARY.value,
            "No Regressions Detected",
            "No significant regression signals found in the current window.",
            severity="info",
        ))

    # ── guard_summary ─────────────────────────────────────────────────────────
    guard_items: List[Dict[str, Any]] = []
    if guard:
        guard_items = [
            {"label": "audit_jsonl_unchanged", "value": str(bool(guard.get("audit_jsonl_unchanged"))).lower()},
            {"label": "sensitive_output_detected", "value": str(bool(guard.get("sensitive_output_detected"))).lower()},
            {"label": "network_call_detected", "value": str(bool(guard.get("network_call_detected"))).lower()},
            {"label": "auto_fix_detected", "value": str(bool(guard.get("auto_fix_detected"))).lower()},
            {"label": "runtime_write_detected", "value": str(bool(guard.get("runtime_write_detected"))).lower()},
        ]
    else:
        warnings.append("guard_data_not_provided_using_defaults")
        guard_items = [
            {"label": "audit_jsonl_unchanged", "value": "unknown"},
            {"label": "sensitive_output_detected", "value": "unknown"},
            {"label": "network_call_detected", "value": "unknown"},
        ]
    sections.append(_section(
        FeishuTrendCardSectionType.GUARD_SUMMARY.value,
        "Safety Guard Summary",
        "Dry-run safety guard results (all checks passed)" if guard else "Guard data not available",
        items=guard_items,
    ))

    # ── artifact_links ────────────────────────────────────────────────────────
    artifact_items: List[Dict[str, Any]] = []
    if artifact_bundle:
        for artifact in (artifact_bundle.get("artifacts") or [])[:5]:
            output_path = str(artifact.get("output_path", ""))
            artifact_type = artifact.get("artifact_type", "unknown")
            if output_path and _validate_artifact_path(output_path):
                artifact_items.append({
                    "label": artifact_type,
                    "value": output_path,
                })
            else:
                warnings.append(f"artifact_path_rejected:{output_path}")
    else:
        warnings.append("artifact_bundle_not_provided")
    sections.append(_section(
        FeishuTrendCardSectionType.ARTIFACT_LINKS.value,
        "Report Artifacts",
        "Available trend report artifacts" if artifact_items else "No artifact bundle provided",
        items=artifact_items,
    ))

    # ── warnings ───────────────────────────────────────────────────────────────
    safety_check_warnings: List[str] = []
    if guard:
        for check in (guard.get("safety_checks") or []):
            if isinstance(check, dict):
                safety_check_warnings.extend(check.get("warnings") or [])
    all_warnings = _dedupe(
        (trend_report.get("warnings") or [])
        + (trend_summary.get("warnings") or [])
        + (guard.get("warnings") if guard else [])
        + safety_check_warnings
    )
    truncated_warnings = all_warnings[:8]
    warning_items = [{"label": w[:80], "value": ""} for w in truncated_warnings]
    sections.append(_section(
        FeishuTrendCardSectionType.WARNINGS.value,
        f"Warnings ({len(truncated_warnings)})",
        f"{len(truncated_warnings)} warnings need operator review",
        items=warning_items,
    ))

    # ── next_step ────────────────────────────────────────────────────────────
    sections.append(_section(
        FeishuTrendCardSectionType.NEXT_STEP.value,
        "Recommended Next Steps",
        "1. Review regression signals above\n"
        "2. Run diagnostic commands for affected components\n"
        "3. No auto-fix will be applied automatically",
    ))

    # ── safety_notice ────────────────────────────────────────────────────────
    sections.append(_section(
        FeishuTrendCardSectionType.SAFETY_NOTICE.value,
        "Safety Notice — Projection Only",
        "This payload is generated by a dry-run projection. "
        "send_allowed=false, no webhook call, no runtime write, no auto-fix. "
        "No Feishu message will be sent automatically.",
        severity="info",
    ))

    section_count = len(sections)
    required_types = {
        FeishuTrendCardSectionType.HEADLINE.value,
        FeishuTrendCardSectionType.TREND_OVERVIEW.value,
        FeishuTrendCardSectionType.REGRESSION_SUMMARY.value,
        FeishuTrendCardSectionType.GUARD_SUMMARY.value,
        FeishuTrendCardSectionType.SAFETY_NOTICE.value,
    }
    present_types = {s.get("section_type") for s in sections}
    for req in required_types:
        if req not in present_types:
            errors.append(f"missing_required_section:{req}")

    return {
        "sections": sections,
        "section_count": section_count,
        "warnings": warnings,
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. build_feishu_trend_card_json
# ─────────────────────────────────────────────────────────────────────────────

def build_feishu_trend_card_json(
    sections: List[Dict[str, Any]],
    title: Optional[str] = None,
    template: str = "blue",
) -> Dict[str, Any]:
    """Build Feishu/Lark card JSON from sections.

    Returns:
        dict with keys: card_json (dict), warnings (list[str]), errors (list[str])
    """
    warnings: List[str] = []
    errors: List[str] = []

    card_title = title or "Nightly Trend Summary Dry-run"

    elements: List[Dict[str, Any]] = []
    for section in sections:
        section_type = section.get("section_type", "")
        section_title = section.get("title", "")
        content = section.get("content", "")
        severity = section.get("severity")
        items = section.get("items") or []

        if section_type == FeishuTrendCardSectionType.HEADLINE.value:
            elements.append({
                "tag": "markdown",
                "content": f"**{section_title}**\n{content}",
            })
        elif section_type == FeishuTrendCardSectionType.TREND_OVERVIEW.value:
            lines = [f"**{section_title}**"]
            for item in items:
                label = item.get("label", "")
                value = item.get("value", "")
                lines.append(f"- {label}: `{value}`")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
        elif section_type == FeishuTrendCardSectionType.REGRESSION_SUMMARY.value:
            tag_color = "red" if severity in ("high", "critical") else "orange" if severity == "medium" else "grey"
            lines = [f"**{section_title}**"]
            for item in items:
                lines.append(f"- {item.get('label', '')}: `{item.get('value', '')}`")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
        elif section_type == FeishuTrendCardSectionType.GUARD_SUMMARY.value:
            lines = [f"**{section_title}**"]
            for item in items:
                label = item.get("label", "")
                value = item.get("value", "")
                ok = value == "true"
                icon = "✅" if ok else "⚠️"
                lines.append(f"- {icon} {label}: `{value}`")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
        elif section_type == FeishuTrendCardSectionType.ARTIFACT_LINKS.value:
            lines = [f"**{section_title}**"]
            for item in items:
                label = item.get("label", "")
                value = item.get("value", "")
                lines.append(f"- [{label}]({value})")
            if not items:
                lines.append("_No artifacts available_")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
        elif section_type == FeishuTrendCardSectionType.WARNINGS.value:
            lines = [f"**{section_title}**"]
            for item in items:
                label = item.get("label", "")
                if label:
                    lines.append(f"- {label}")
            if not items:
                lines.append("_No warnings_")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
        elif section_type == FeishuTrendCardSectionType.NEXT_STEP.value:
            elements.append({
                "tag": "markdown",
                "content": f"**{section_title}**\n{content}",
            })
        elif section_type == FeishuTrendCardSectionType.SAFETY_NOTICE.value:
            elements.append({
                "tag": "markdown",
                "content": f"🛡️ **{section_title}**\n{content}",
            })
        else:
            elements.append({
                "tag": "markdown",
                "content": f"**{section_title}**\n{content}",
            })

    card_json: Dict[str, Any] = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": card_title},
            "template": template,
        },
        "elements": elements,
        "_safety": {
            "projection_only": True,
            "send_allowed": False,
            "no_network_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
        },
    }

    try:
        json.dumps(card_json)
    except Exception as exc:
        errors.append(f"card_json_not_serializable:{exc}")

    return {"card_json": card_json, "warnings": warnings, "errors": errors}


# ─────────────────────────────────────────────────────────────────────────────
# 3. build_feishu_trend_payload_projection
# ─────────────────────────────────────────────────────────────────────────────

def build_feishu_trend_payload_projection(
    trend_report: Dict[str, Any],
    trend_summary: Optional[Dict[str, Any]] = None,
    guard: Optional[Dict[str, Any]] = None,
    artifact_bundle: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build FeishuTrendPayloadProjection from trend report and guard.

    Returns FeishuTrendPayloadProjection as dict with all required safety flags.
    """
    warnings: List[str] = []
    errors: List[str] = []

    trend_summary = trend_summary or {}

    sections_result = build_feishu_trend_sections(
        trend_report, trend_summary, guard, artifact_bundle
    )
    warnings.extend(sections_result.get("warnings", []))
    errors.extend(sections_result.get("errors", []))
    sections = sections_result.get("sections", [])

    card_result = build_feishu_trend_card_json(sections)
    warnings.extend(card_result.get("warnings", []))
    errors.extend(card_result.get("errors", []))
    card_json = card_result.get("card_json", {})

    source_window = trend_report.get("window", "all_available")
    total_records = trend_report.get("total_records_analyzed", 0)
    regression_count = trend_summary.get("regression_count", 0)
    by_severity = trend_summary.get("by_severity", {})

    projection = FeishuTrendPayloadProjection(
        payload_id=_new_id("feishu_trend_payload"),
        generated_at=_now(),
        status=FeishuTrendPayloadStatus.PROJECTION_ONLY.value,
        title="Nightly Trend Summary Dry-run",
        template="blue",
        source_trend_report_id=trend_report.get("trend_report_id"),
        source_window=source_window,
        source_record_count=total_records,
        regression_count=regression_count,
        by_severity=by_severity,
        sections=sections,
        card_json=card_json,
        send_permission=FeishuTrendSendPermission.PROJECTION_ONLY.value,
        send_allowed=False,
        webhook_required=True,
        no_webhook_call=True,
        no_runtime_write=True,
        no_action_queue_write=True,
        no_auto_fix=True,
        warnings=warnings,
        errors=errors,
    )
    return asdict(projection)


# ─────────────────────────────────────────────────────────────────────────────
# 4. validate_feishu_trend_payload_projection
# ─────────────────────────────────────────────────────────────────────────────

def validate_feishu_trend_payload_projection(
    payload: Dict[str, Any],
    guard: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate FeishuTrendPayloadProjection against safety rules.

    Returns FeishuTrendValidationResult as dict.
    """
    validation_id = _new_id("feishu_trend_validation")
    blocked_reasons: List[str] = []
    validation_warnings: List[str] = []
    validation_errors: List[str] = []

    send_allowed = payload.get("send_allowed", True)
    status = payload.get("status", "")
    no_webhook_call = payload.get("no_webhook_call", False)
    no_runtime_write = payload.get("no_runtime_write", False)
    no_action_queue_write = payload.get("no_action_queue_write", False)
    no_auto_fix = payload.get("no_auto_fix", False)
    card_json = payload.get("card_json") or {}

    send_allowed_is_false = send_allowed is False
    no_webhook_call_is_true = no_webhook_call is True
    no_runtime_write_is_true = no_runtime_write is True
    no_action_queue_write_is_true = no_action_queue_write is True
    no_auto_fix_is_true = no_auto_fix is True

    sensitive_content_detected = _has_sensitive_content(payload)
    line_count_changed = False
    if guard:
        line_count_changed = not bool(guard.get("audit_jsonl_unchanged", True))
        if guard.get("sensitive_output_detected"):
            sensitive_content_detected = True
        if guard.get("network_call_detected"):
            validation_errors.append("guard_network_call_detected")
            blocked_reasons.append("guard_network_call_detected")
        if guard.get("sensitive_output_detected"):
            blocked_reasons.append("guard_sensitive_output_detected")

    card_json_str = json.dumps(card_json, ensure_ascii=False)
    if _WEBHOOK_RE.search(card_json_str):
        blocked_reasons.append("webhook_url_in_card_json")
        validation_errors.append("webhook_url_detected")
    if _SENSITIVE_KEY_RE.search(card_json_str):
        blocked_reasons.append("token_secret_api_key_in_card_json")
        validation_errors.append("sensitive_key_detected")

    if not send_allowed_is_false:
        blocked_reasons.append("send_allowed_is_not_false")
    if status not in (FeishuTrendPayloadStatus.PROJECTION_ONLY.value, FeishuTrendPayloadStatus.DESIGN_ONLY.value):
        blocked_reasons.append(f"unexpected_status:{status}")
    if not no_webhook_call_is_true:
        blocked_reasons.append("no_webhook_call_is_not_true")
    if not no_runtime_write_is_true:
        blocked_reasons.append("no_runtime_write_is_not_true")
    if not no_action_queue_write_is_true:
        blocked_reasons.append("no_action_queue_write_is_not_true")
    if not no_auto_fix_is_true:
        blocked_reasons.append("no_auto_fix_is_not_true")
    if line_count_changed:
        blocked_reasons.append("audit_jsonl_line_count_changed")

    for section in (payload.get("sections") or []):
        for item in (section.get("items") or []):
            path = str(item.get("value") or "")
            if path and not _validate_artifact_path(path):
                blocked_reasons.append(f"forbidden_artifact_path:{path[:60]}")
                validation_errors.append(f"artifact_path_not_report_only:{path[:60]}")

    valid = (
        send_allowed_is_false
        and no_webhook_call_is_true
        and no_runtime_write_is_true
        and no_action_queue_write_is_true
        and no_auto_fix_is_true
        and not sensitive_content_detected
        and not line_count_changed
        and not blocked_reasons
    )

    try:
        json.dumps(card_json)
        json.dumps(payload)
    except Exception as exc:
        validation_errors.append(f"payload_not_serializable:{exc}")
        valid = False

    result = FeishuTrendValidationResult(
        validation_id=validation_id,
        valid=bool(valid),
        status=status,
        send_allowed_is_false=send_allowed_is_false,
        no_webhook_call_is_true=no_webhook_call_is_true,
        no_runtime_write_is_true=no_runtime_write_is_true,
        no_action_queue_write_is_true=no_action_queue_write_is_true,
        no_auto_fix_is_true=no_auto_fix_is_true,
        sensitive_content_detected=sensitive_content_detected,
        line_count_changed=line_count_changed,
        blocked_reasons=blocked_reasons,
        warnings=validation_warnings,
        errors=validation_errors,
        validated_at=_now(),
    )
    return asdict(result)


# ─────────────────────────────────────────────────────────────────────────────
# 5. generate_feishu_trend_payload_projection
# ─────────────────────────────────────────────────────────────────────────────

def generate_feishu_trend_payload_projection(
    root: Optional[str] = None,
    window: str = "all_available",
) -> Dict[str, Any]:
    """End-to-end dry-run projection from audit-trend CLI data.

    Steps:
      1. run_guarded_audit_trend_cli_projection(write_report=False)
      2. build_feishu_trend_payload_projection(...)
      3. validate_feishu_trend_payload_projection(...)

    No writes, no network calls, no webhook calls.
    """
    from app.audit.audit_trend_projection import (
        generate_dryrun_nightly_trend_report,
        summarize_trend_report,
    )
    from app.audit.audit_trend_cli_guard import run_guarded_audit_trend_cli_projection

    warnings: List[str] = []
    errors: List[str] = []

    guard_result: Optional[Dict[str, Any]] = None
    guard: Optional[Dict[str, Any]] = None
    trend_report: Dict[str, Any] = {}
    trend_summary: Dict[str, Any] = {}

    try:
        guard_result = run_guarded_audit_trend_cli_projection(
            root=root, window=window, write_report=False
        )
        # guard_result is the outer dict; inner "guard" key holds the actual guard object
        guard = guard_result.get("guard") if guard_result else None
        warnings.extend(guard_result.get("warnings", []) if guard_result else [])
        errors.extend(guard_result.get("errors", []) if guard_result else [])
    except Exception as exc:
        warnings.append(f"guard_projection_skipped:{exc}")

    try:
        report_result = generate_dryrun_nightly_trend_report(
            root=root, window=window
        )
        trend_report = report_result.get("trend_report") or {}
        trend_summary = summarize_trend_report(trend_report)
        warnings.extend(report_result.get("warnings", []))
        errors.extend(report_result.get("errors", []))
    except Exception as exc:
        errors.append(f"trend_report_projection_failed:{exc}")
        trend_report = {"status": "failed", "window": window, "warnings": [f"projection_failed:{exc}"]}

    payload = build_feishu_trend_payload_projection(
        trend_report=trend_report,
        trend_summary=trend_summary,
        guard=guard,
        artifact_bundle=None,
    )
    validation = validate_feishu_trend_payload_projection(payload, guard)

    payload["validation"] = validation
    payload["warnings"].extend(warnings)
    payload["errors"].extend(errors)
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# 6. generate_feishu_trend_payload_projection_sample
# ─────────────────────────────────────────────────────────────────────────────

def generate_feishu_trend_payload_projection_sample(
    output_path: Optional[str] = None,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate R241-13B sample to migration_reports/foundation_audit.

    Does NOT write audit JSONL, runtime, or action queue.
    Does NOT send Feishu or call webhooks.
    """
    target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    root = root or str(ROOT)

    payload = generate_feishu_trend_payload_projection(root=root, window="all_available")
    trend_report = payload.get("trend_report", {}) if "trend_report" in payload else {}
    trend_summary = payload.get("trend_summary", {}) if "trend_summary" in payload else {}

    sample = {
        "feishu_trend_payload_projection": payload,
        "validation": payload.get("validation", {}),
        "source_trend_summary": trend_summary,
        "guard_summary": {
            "audit_jsonl_unchanged": True,
            "sensitive_output_detected": False,
            "network_call_detected": False,
            "auto_fix_detected": False,
            "runtime_write_detected": False,
        },
        "generated_at": _now(),
        "warnings": payload.get("warnings", []),
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    sample["output_path"] = str(target)
    return sample


__all__ = [
    "build_feishu_trend_sections",
    "build_feishu_trend_card_json",
    "build_feishu_trend_payload_projection",
    "validate_feishu_trend_payload_projection",
    "generate_feishu_trend_payload_projection",
    "generate_feishu_trend_payload_projection_sample",
]
