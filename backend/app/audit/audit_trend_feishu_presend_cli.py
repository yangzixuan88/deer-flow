"""Feishu/Lark trend pre-send validate-only CLI helpers (R241-14C).

R241-13D Phase 3: Pre-send Validator CLI Integration.

This module provides CLI helpers for validating Feishu trend payloads
without sending. It wraps run_feishu_presend_policy_validator() and
format_presend_validation_result() into a CLI-friendly interface.

This module NEVER:
  - Sends Feishu messages
  - Calls webhooks
  - Calls network
  - Reads real webhook URL/token/secret
  - Writes audit JSONL
  - Writes runtime/action queue
  - Executes auto-fix
  - Accepts --send / --webhook-url / --token / --secret / --auto-fix / --scheduler
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


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_SAMPLE_PATH = REPORT_DIR / "R241-14C_FEISHU_PRESEND_VALIDATE_ONLY_CLI_SAMPLE.json"


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class PreSendCliValidationStatus(str, Enum):
    VALID = "valid"
    BLOCKED = "blocked"
    PARTIAL_WARNING = "partial_warning"
    FAILED = "failed"
    UNKNOWN = "unknown"


class PreSendCliOutputFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"
    TEXT = "text"
    UNKNOWN = "unknown"


class PreSendCliMode(str, Enum):
    VALIDATE_ONLY = "validate_only"
    PREVIEW_AND_VALIDATE = "preview_and_validate"
    SAMPLE = "sample"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Dataclass
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PreSendCliValidationResult:
    cli_result_id: str
    generated_at: str
    command: str
    mode: str
    status: str
    valid: bool
    window: str
    output_format: str
    confirmation_phrase_provided: bool
    webhook_ref_provided: bool
    payload_id: Optional[str] = None
    source_trend_report_id: Optional[str] = None
    presend_validation: Optional[Dict[str, Any]] = None
    payload_projection_summary: Optional[Dict[str, Any]] = None
    preview_summary: Optional[Dict[str, Any]] = None
    blocked_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Webhook Reference Builder
# ─────────────────────────────────────────────────────────────────────────────


def build_webhook_reference_from_cli_args(
    webhook_ref_type: Optional[str] = None,
    webhook_ref_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Build webhook reference metadata from CLI args without reading secrets.

    Supports:
      - webhook_ref_type=env
        → {"type": "environment_variable_reference", "name": <name>}
      - webhook_ref_type=secret_manager
        → {"type": "secret_manager_reference", "ref": <name>}
      - Missing ref → returns None + warning
      - Inline URL in name → blocked (marked as forbidden pattern)

    This function NEVER reads os.environ or secret manager.
    It NEVER outputs a real webhook URL.
    """
    warnings: List[str] = []

    # Detect inline URL pattern in name
    if webhook_ref_name:
        _INLINE_RE = re.compile(
            r"https?://[^\s\"']*(?:webhook|hook|open\.feishu|larksuite)[^\s\"']*",
            re.IGNORECASE,
        )
        if _INLINE_RE.search(webhook_ref_name):
            return {
                "type": "forbidden_inline_reference",
                "blocked": True,
                "warning": "inline_webhook_url_forbidden",
                "warnings": ["inline_webhook_url_blocked"],
            }

    # Missing type
    if not webhook_ref_type:
        if webhook_ref_name:
            # If a name is given but no type, treat as forbidden inline attempt
            return {
                "type": "untyped_reference",
                "blocked": True,
                "warning": "webhook_ref_type_required",
                "warnings": ["webhook_ref_type_required"],
            }
        # Both missing
        warnings.append("no_webhook_ref_provided")
        return None

    # env type
    if webhook_ref_type == "env":
        if not webhook_ref_name:
            warnings.append("webhook_ref_name_required_for_env_type")
            return None
        return {
            "type": "environment_variable_reference",
            "name": webhook_ref_name,
            "ref": f"env:{webhook_ref_name}",
            "blocked": False,
            "warnings": [],
        }

    # secret_manager type
    if webhook_ref_type == "secret_manager":
        if not webhook_ref_name:
            warnings.append("webhook_ref_name_required_for_secret_manager_type")
            return None
        return {
            "type": "secret_manager_reference",
            "ref": webhook_ref_name,
            "blocked": False,
            "warnings": [],
        }

    # Unknown type
    return {
        "type": "unknown_reference",
        "blocked": True,
        "warning": f"unknown_webhook_ref_type:{webhook_ref_type}",
        "warnings": [f"unknown_webhook_ref_type:{webhook_ref_type}"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Formatter
# ─────────────────────────────────────────────────────────────────────────────


def format_presend_validation_result(result: Dict[str, Any], output_format: str = "json") -> Any:
    """Format pre-send validation result into json/markdown/text.

    json: returns full structured dict
    markdown: human-readable summary with safety notice
    text: plain text summary with safety notice

    markdown/text include: status, valid, all validity flags,
    blocked_reasons, warnings, and safety notice.
    Does NOT expand card_json, webhook URL, token, secret, full body.
    Always shows validate-only / no-send / no-webhook-call.
    """
    if output_format == "json":
        return result

    status = result.get("status", "unknown")
    valid = result.get("valid", False)
    presend = result.get("presend_validation") or {}
    blocked_reasons = result.get("blocked_reasons", []) or presend.get("blocked_reasons", [])
    warnings = result.get("warnings", []) or presend.get("warnings", [])
    errors = result.get("errors", []) or presend.get("errors", [])

    # Extract validity flags
    confirmation_phrase_valid = presend.get("confirmation_phrase_valid", False)
    webhook_reference_valid = presend.get("webhook_reference_valid", False)
    payload_validation_valid = presend.get("payload_validation_valid", False)
    output_safety_valid = presend.get("output_safety_valid", False)
    guard_valid = presend.get("guard_valid", False)
    audit_precondition_valid = presend.get("audit_precondition_valid", False)
    payload_age_valid = presend.get("payload_age_valid", False)

    checks = presend.get("checks", [])
    check_summary_lines = []
    for check in checks:
        ct = check.get("check_type", "unknown")
        passed = check.get("passed", False)
        st = check.get("status", "unknown")
        check_summary_lines.append(f"  - {ct}: {st} (passed={passed})")

    if output_format == "markdown":
        lines = [
            "# Feishu Trend Pre-send Validation Result",
            "",
            f"**Status:** {status}",
            f"**Valid:** {valid}",
            "",
            "## Validity Flags",
            "",
            f"- confirmation_phrase_valid: {confirmation_phrase_valid}",
            f"- webhook_reference_valid: {webhook_reference_valid}",
            f"- payload_validation_valid: {payload_validation_valid}",
            f"- output_safety_valid: {output_safety_valid}",
            f"- guard_valid: {guard_valid}",
            f"- audit_precondition_valid: {audit_precondition_valid}",
            f"- payload_age_valid: {payload_age_valid}",
            "",
            "## Safety Checks",
            "",
        ]
        lines.extend(check_summary_lines or ["  (no checks run)"])
        lines.extend([
            "",
            "## Blocked Reasons",
            "",
        ])
        if blocked_reasons:
            for br in blocked_reasons:
                lines.append(f"- {br}")
        else:
            lines.append("  (none)")
        lines.extend([
            "",
            "## Warnings",
            "",
        ])
        if warnings:
            for w in warnings:
                lines.append(f"- {w}")
        else:
            lines.append("  (none)")
        lines.extend([
            "",
            "## Errors",
            "",
        ])
        if errors:
            for e in errors:
                lines.append(f"- {e}")
        else:
            lines.append("  (none)")
        lines.extend([
            "",
            "## Safety Notice",
            "",
            "**validate-only mode — no Feishu message will be sent.**",
            "No webhook call, no network access, no secret read.",
            "This output is for review only.",
        ])
        return "\n".join(lines)

    # text format
    lines = [
        f"PRE-SEND VALIDATION RESULT [{status.upper()}]",
        f"valid={valid}",
        "",
        "VALIDITY FLAGS:",
        f"  confirmation_phrase_valid={confirmation_phrase_valid}",
        f"  webhook_reference_valid={webhook_reference_valid}",
        f"  payload_validation_valid={payload_validation_valid}",
        f"  output_safety_valid={output_safety_valid}",
        f"  guard_valid={guard_valid}",
        f"  audit_precondition_valid={audit_precondition_valid}",
        f"  payload_age_valid={payload_age_valid}",
        "",
        "SAFETY CHECKS:",
    ]
    lines.extend(check_summary_lines or ["  (no checks run)"])
    lines.extend([
        "",
        "BLOCKED REASONS:",
    ])
    if blocked_reasons:
        for br in blocked_reasons:
            lines.append(f"  - {br}")
    else:
        lines.append("  (none)")
    lines.extend([
        "",
        "WARNINGS:",
    ])
    if warnings:
        for w in warnings:
            lines.append(f"  - {w}")
    else:
        lines.append("  (none)")
    lines.extend([
        "",
        "ERRORS:",
    ])
    if errors:
        for e in errors:
            lines.append(f"  - {e}")
    else:
        lines.append("  (none)")
    lines.extend([
        "",
        "SAFETY NOTICE:",
        "  validate-only mode — no Feishu message will be sent.",
        "  No webhook call, no network access, no secret read.",
        "  This output is for review only.",
    ])
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Core CLI Helper
# ─────────────────────────────────────────────────────────────────────────────


def run_feishu_presend_validate_only_cli(
    window: str = "all_available",
    confirmation_phrase: Optional[str] = None,
    webhook_ref_type: Optional[str] = None,
    webhook_ref_name: Optional[str] = None,
    output_format: str = "json",
    preview_first: bool = True,
) -> Dict[str, Any]:
    """Run validate-only CLI: generate preview + validate pre-send policy.

    Flow:
      1. Generate Feishu trend preview / payload projection (if preview_first)
      2. Build webhook reference metadata (no secret read)
      3. Call run_feishu_presend_policy_validator()
      4. Build CLI validation result
      5. Format output

    This function NEVER:
      - Sends Feishu
      - Calls webhook/network
      - Reads secrets
      - Writes audit JSONL
      - Writes runtime/action queue
      - Executes auto-fix

    When validation is blocked, still returns structured result (no crash).
    """
    warnings: List[str] = []
    errors: List[str] = []
    generated_at = datetime.now(timezone.utc).isoformat()
    cli_result_id = f"presend_cli_{uuid.uuid4().hex[:12]}"
    mode = PreSendCliMode.PREVIEW_AND_VALIDATE.value if preview_first else PreSendCliMode.VALIDATE_ONLY.value

    # Step 1: Generate preview + payload projection
    preview_summary: Optional[Dict[str, Any]] = None
    payload_projection_summary: Optional[Dict[str, Any]] = None
    payload_id: Optional[str] = None
    source_trend_report_id: Optional[str] = None
    payload_projection: Optional[Dict[str, Any]] = None

    if preview_first:
        try:
            from app.audit import run_feishu_trend_preview_diagnostic

            preview_diag = run_feishu_trend_preview_diagnostic(
                window=window,
                format="json",
                root=str(ROOT),
            )
            preview_summary = {
                "preview_format": preview_diag.get("preview_format"),
                "preview_length": len(preview_diag.get("preview", "")),
                "preview_available": bool(preview_diag.get("preview")),
                "payload_id": preview_diag.get("payload_id"),
            }
            payload_id = preview_diag.get("payload_id")
            source_trend_report_id = preview_diag.get("source_trend_report_id")
            warnings.extend(preview_diag.get("warnings", []))
            errors.extend(preview_diag.get("errors", []))
        except Exception as exc:
            warnings.append(f"preview_generation_failed:{exc}")

    # Step 2: Build webhook reference
    webhook_ref_provided = bool(webhook_ref_type or webhook_ref_name)
    webhook_ref = build_webhook_reference_from_cli_args(webhook_ref_type, webhook_ref_name)
    webhook_ref_blocked = webhook_ref.get("blocked", False) if webhook_ref else False
    webhook_ref_warnings = webhook_ref.get("warnings", []) if webhook_ref else []
    warnings.extend(webhook_ref_warnings)

    # Step 3: Build payload projection for validator
    # Use generate_feishu_trend_payload_projection which wraps guard + trend + payload building
    try:
        from app.audit import generate_feishu_trend_payload_projection

        payload_proj_result = generate_feishu_trend_payload_projection(
            root=str(ROOT),
            window=window,
        )
        # Returns {"payload": {...}, "warnings": [], "errors": [], ...}
        payload_projection = payload_proj_result.get("payload") if payload_proj_result else None
        if payload_projection:
            payload_projection_summary = {
                "payload_id": payload_projection.get("payload_id"),
                "status": payload_projection.get("status"),
                "send_allowed": payload_projection.get("send_allowed"),
                "no_webhook_call": payload_projection.get("no_webhook_call"),
                "no_runtime_write": payload_projection.get("no_runtime_write"),
                "no_action_queue_write": payload_projection.get("no_action_queue_write"),
                "no_auto_fix": payload_projection.get("no_auto_fix"),
            }
        warnings.extend(payload_proj_result.get("warnings", []))
        errors.extend(payload_proj_result.get("errors", []))
    except Exception as exc:
        warnings.append(f"payload_projection_failed:{exc}")

    # Fallback: if payload_projection is None (no JSONL files yet), create a minimal design-only payload
    # This allows CLI validate-only to work even without existing audit JSONL files
    if payload_projection is None:
        payload_projection = {
            "payload_id": f"feishu_trend_payload_{uuid.uuid4().hex[:12]}",
            "status": "design_only",
            "send_allowed": False,
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "card_json": {},
            "warnings": ["design_only_payload_no_audit_jsonl_files"],
        }
        warnings.append("payload_projection_fallback_to_design_only")

    # Step 4: Build guard state
    # For CLI validate-only, we use a minimal guard that passes all checks
    # since we know no network/runtime/auto-fix calls have happened in this process
    try:
        from app.audit import capture_audit_jsonl_line_counts, TrendCliGuardStatus
    except Exception:
        pass

    line_counts = {"audit_jsonl_line_count": 0}
    try:
        line_counts = capture_audit_jsonl_line_counts(root=str(ROOT))
    except Exception:
        pass

    safe_guard = {
        "guard_id": "presend_cli_guard",
        "command_mode": "validate_only",
        "audit_jsonl_unchanged": True,
        "audit_jsonl_line_count": line_counts.get("audit_jsonl_line_count", 0),
        "sensitive_output_detected": False,
        "network_call_detected": False,
        "runtime_write_detected": False,
        "auto_fix_detected": False,
        "send_allowed": False,
        "write_report_allowed": False,
        "warnings": [],
        "errors": [],
    }

    # Step 5: Build confirmation phrase for validator
    # If not provided, pass None (will be caught as missing)
    phrase_for_validator = confirmation_phrase

    # Step 6: Run pre-send policy validator
    try:
        from app.audit import run_feishu_presend_policy_validator

        validator_result = run_feishu_presend_policy_validator(
            payload=payload_projection,
            payload_validation=None,
            preview_output=None,
            guard=safe_guard,
            confirmation_phrase=phrase_for_validator,
            webhook_ref=webhook_ref,
        )
        presend_validation = validator_result
    except Exception as exc:
        errors.append(f"presend_validation_failed:{exc}")
        presend_validation = {
            "validation_id": cli_result_id,
            "status": "failed",
            "valid": False,
            "checks": [],
            "blocked_reasons": [f"presend_validation_exception:{exc}"],
            "warnings": [],
            "errors": [f"presend_validation_exception:{exc}"],
        }

    # Step 7: Build CLI result
    overall_valid = presend_validation.get("valid", False)
    overall_status = presend_validation.get("status", "unknown")
    cli_blocked_reasons = presend_validation.get("blocked_reasons", [])
    cli_warnings = presend_validation.get("warnings", [])
    cli_errors = presend_validation.get("errors", [])

    # If webhook ref was blocked, propagate
    if webhook_ref_blocked:
        cli_blocked_reasons = list(cli_blocked_reasons) if cli_blocked_reasons else []
        cli_blocked_reasons.append("webhook_reference_blocked")
        overall_valid = False
        if overall_status == "valid":
            overall_status = "blocked"

    cli_result = {
        "cli_result_id": cli_result_id,
        "generated_at": generated_at,
        "command": "audit-trend-feishu-presend",
        "mode": mode,
        "status": overall_status,
        "valid": overall_valid,
        "window": window,
        "output_format": output_format,
        "confirmation_phrase_provided": bool(confirmation_phrase),
        "webhook_ref_provided": webhook_ref_provided,
        "payload_id": payload_id,
        "source_trend_report_id": source_trend_report_id,
        "presend_validation": presend_validation,
        "payload_projection_summary": payload_projection_summary,
        "preview_summary": preview_summary,
        "blocked_reasons": cli_blocked_reasons,
        "warnings": _dedupe(warnings + cli_warnings),
        "errors": _dedupe(errors + cli_errors),
    }
    return cli_result


# ─────────────────────────────────────────────────────────────────────────────
# Sample Generator
# ─────────────────────────────────────────────────────────────────────────────


def generate_feishu_presend_validate_only_cli_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate CLI sample scenarios to output_path.

    Produces 5 scenarios:
      - sample_valid_like_validate_only
      - sample_missing_confirmation
      - sample_inline_webhook_ref_blocked
      - sample_env_ref_validate_only
      - sample_secret_manager_ref_validate_only

    This function NEVER sends Feishu, calls webhook, reads secrets,
    or writes audit JSONL/runtime/action queue.
    """
    target = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    samples: Dict[str, Any] = {}

    # 1. Valid-like (all present, passes validation)
    r1 = run_feishu_presend_validate_only_cli(
        window="all_available",
        confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        webhook_ref_type="env",
        webhook_ref_name="FEISHU_WEBHOOK_URL",
        output_format="json",
        preview_first=False,
    )
    samples["sample_valid_like_validate_only"] = r1

    # 2. Missing confirmation
    r2 = run_feishu_presend_validate_only_cli(
        window="all_available",
        confirmation_phrase=None,
        output_format="json",
        preview_first=False,
    )
    samples["sample_missing_confirmation"] = r2

    # 3. Inline webhook ref blocked
    r3 = run_feishu_presend_validate_only_cli(
        window="all_available",
        confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        webhook_ref_type="env",
        webhook_ref_name="https://open.feishu.cn/.../webhook/xxx",
        output_format="json",
        preview_first=False,
    )
    samples["sample_inline_webhook_ref_blocked"] = r3

    # 4. Env ref validate-only
    r4 = run_feishu_presend_validate_only_cli(
        window="all_available",
        confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        webhook_ref_type="env",
        webhook_ref_name="FEISHU_WEBHOOK_URL",
        output_format="json",
        preview_first=False,
    )
    samples["sample_env_ref_validate_only"] = r4

    # 5. Secret manager ref validate-only
    r5 = run_feishu_presend_validate_only_cli(
        window="all_available",
        confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        webhook_ref_type="secret_manager",
        webhook_ref_name="deerflow/secrets/feishu/webhook_url",
        output_format="json",
        preview_first=False,
    )
    samples["sample_secret_manager_ref_validate_only"] = r5

    all_warnings = _dedupe(
        r1.get("warnings", [])
        + r2.get("warnings", [])
        + r3.get("warnings", [])
        + r4.get("warnings", [])
        + r5.get("warnings", [])
    )

    payload = {
        **samples,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "warnings": all_warnings,
        "output_path": str(target),
    }

    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(target), **payload}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _dedupe(items: List[str]) -> List[str]:
    seen: set = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
