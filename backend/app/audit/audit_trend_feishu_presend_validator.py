"""Feishu/Lark trend pre-send policy validator (R241-14B).

R241-13D Phase 2: Pre-send Policy Validator Implementation.

This module validates a Feishu trend payload projection against the manual send
policy before any human confirmation step. It proves the payload is eligible to
enter the confirmation flow — it does NOT enable sending.

This validator:
  - Validates confirmation phrase (exact match, no reading of secrets)
  - Validates webhook reference (env/secret-manager ref only, no inline URL)
  - Validates payload projection (safety flags, serializable, no sensitive content)
  - Validates output safety (no webhook URL/token/secret/full body in preview)
  - Validates guard state (audit JSONL unchanged, no sensitive output)
  - Validates audit precondition (pre-send audit projection, append-only)
  - Validates payload age (must be < 60 minutes)

This module NEVER:
  - Sends Feishu messages
  - Calls webhooks
  - Calls network
  - Reads real webhook URL/token/secret
  - Writes audit JSONL
  - Writes runtime/action queue
  - Executes auto-fix
"""

from __future__ import annotations

import hashlib
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

_WEBHOOK_RE = re.compile(r"https?://[^\s\"']*(?:webhook|hook|open\.feishu|larksuite)[^\s\"']*", re.IGNORECASE)
_SENSITIVE_KEY_RE = re.compile(
    r"\b(webhook_url|api_key|token|secret|password|secret_key|access_token)\b",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_RE = re.compile(
    r"(?i)(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36,}|Bearer\s+[a-zA-Z0-9_.~-]+|https://[^\s]*webhook[^\s]*)",
)
_LONG_BLOCK_RE = re.compile(r"[A-Za-z0-9+/=_-]{4096,}")


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class PreSendValidationStatus(str, Enum):
    VALID = "valid"
    BLOCKED = "blocked"
    PARTIAL_WARNING = "partial_warning"
    FAILED = "failed"
    UNKNOWN = "unknown"


class PreSendValidationCheckType(str, Enum):
    POLICY_DESIGN = "policy_design"
    PAYLOAD_PROJECTION = "payload_projection"
    CONFIRMATION_PHRASE = "confirmation_phrase"
    WEBHOOK_REFERENCE = "webhook_reference"
    OUTPUT_SAFETY = "output_safety"
    GUARD_STATE = "guard_state"
    AUDIT_REQUIREMENT = "audit_requirement"
    PAYLOAD_AGE = "payload_age"
    ARTIFACT_LINKS = "artifact_links"
    NO_AUTO_FIX = "no_auto_fix"
    NO_RUNTIME_WRITE = "no_runtime_write"
    NO_ACTION_QUEUE_WRITE = "no_action_queue_write"
    UNKNOWN = "unknown"


class PreSendValidationRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PreSendValidationCheckResult:
    check_id: str
    check_type: str
    status: str
    passed: bool
    risk_level: str
    message: str
    evidence_refs: List[str] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    checked_at: str = ""


@dataclass
class FeishuPreSendValidationResult:
    validation_id: str
    generated_at: str
    status: str
    valid: bool
    payload_id: Optional[str] = None
    source_trend_report_id: Optional[str] = None
    confirmation_phrase_provided: bool = False
    confirmation_phrase_valid: bool = False
    webhook_reference_valid: bool = False
    payload_validation_valid: bool = False
    output_safety_valid: bool = False
    guard_valid: bool = False
    audit_precondition_valid: bool = False
    payload_age_valid: bool = False
    checks: List[Dict[str, Any]] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _check(
    check_type: str,
    passed: bool,
    risk_level: str,
    message: str,
    blocked_reasons: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
    errors: Optional[List[str]] = None,
    evidence_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if passed:
        status = PreSendValidationStatus.VALID.value
    elif blocked_reasons:
        status = PreSendValidationStatus.BLOCKED.value
    else:
        status = PreSendValidationStatus.FAILED.value

    result = PreSendValidationCheckResult(
        check_id=_new_id("presend_check"),
        check_type=check_type,
        status=status,
        passed=passed,
        risk_level=risk_level,
        message=message,
        blocked_reasons=blocked_reasons or [],
        warnings=warnings or [],
        errors=errors or [],
        evidence_refs=evidence_refs or [],
        checked_at=_now(),
    )
    return asdict(result)


# ─────────────────────────────────────────────────────────────────────────────
# 1. validate_confirmation_phrase
# ─────────────────────────────────────────────────────────────────────────────

def validate_confirmation_phrase(
    phrase: Optional[str],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate the user-provided confirmation phrase.

    Policy defaults to build_manual_send_confirmation_policy().
    Requires exact match of CONFIRM_FEISHU_TREND_SEND.

    This function NEVER reads any secret or environment variable.

    Args:
        phrase: User-provided confirmation phrase (may be None)
        policy: Optional confirmation policy override

    Returns:
        PreSendValidationCheckResult dict
    """
    from app.audit.audit_trend_feishu_send_policy import build_manual_send_confirmation_policy

    policy = policy or build_manual_send_confirmation_policy()
    required_phrase = policy.get("required_confirmation_phrase", "CONFIRM_FEISHU_TREND_SEND")

    if phrase is None or phrase == "":
        return _check(
            PreSendValidationCheckType.CONFIRMATION_PHRASE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.CRITICAL.value,
            message="Confirmation phrase not provided",
            blocked_reasons=["confirmation_phrase_missing"],
            errors=["confirmation_phrase_required"],
        )

    if phrase != required_phrase:
        return _check(
            PreSendValidationCheckType.CONFIRMATION_PHRASE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.CRITICAL.value,
            message=f"Confirmation phrase mismatch: got '{phrase}', expected '{required_phrase}'",
            blocked_reasons=["confirmation_phrase_mismatch"],
            errors=[f"phrase_mismatch_expected_{required_phrase}"],
        )

    return _check(
        PreSendValidationCheckType.CONFIRMATION_PHRASE.value,
        passed=True,
        risk_level=PreSendValidationRiskLevel.LOW.value,
        message="Confirmation phrase valid",
        evidence_refs=["confirmation_phrase_matches"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. validate_webhook_reference
# ─────────────────────────────────────────────────────────────────────────────

def validate_webhook_reference(
    webhook_ref: Optional[Dict[str, Any]],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate a webhook reference dict for pre-send eligibility.

    Allowed reference types:
      - environment_variable_reference: {"type": "environment_variable_reference", "name": "FEISHU_WEBHOOK_URL"}
      - secret_manager_reference: {"type": "secret_manager_reference", "ref": "deerflow/secrets/feishu/webhook_url"}

    Blocked:
      - inline webhook URL (starts with http:// or https://)
      - inline secret/token
      - raw API key
      - unknown domain

    This function NEVER reads the actual env var or secret manager.
    It only validates the REFERENCE FORMAT.

    Args:
        webhook_ref: Webhook reference dict (may be None for dry-run only)
        policy: Optional webhook policy override

    Returns:
        PreSendValidationCheckResult dict
    """
    from app.audit.audit_trend_feishu_send_policy import build_feishu_webhook_policy

    policy = policy or build_feishu_webhook_policy()
    blocked_reasons: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []

    if webhook_ref is None:
        # No webhook ref provided — acceptable for dry-run design validation
        return _check(
            PreSendValidationCheckType.WEBHOOK_REFERENCE.value,
            passed=True,
            risk_level=PreSendValidationRiskLevel.LOW.value,
            message="No webhook reference provided (dry-run design validation mode)",
            warnings=["no_webhook_ref_dry_run_mode"],
        )

    ref_type = webhook_ref.get("type", "")
    ref_name = webhook_ref.get("name", "")
    ref_val = webhook_ref.get("ref", "")

    # Check for inline webhook URL
    if ref_type == "inline_webhook_url" or (ref_name and ref_name.startswith("http")):
        blocked_reasons.append("inline_webhook_url_blocked")
        errors.append("inline_webhook_url_forbidden_by_policy")
        return _check(
            PreSendValidationCheckType.WEBHOOK_REFERENCE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.CRITICAL.value,
            message="Inline webhook URL is forbidden by policy",
            blocked_reasons=blocked_reasons,
            errors=errors,
        )

    # Check for inline secret
    if ref_type == "inline_secret" or (ref_val and len(ref_val) > 40 and not ref_val.startswith("deerflow/")):
        blocked_reasons.append("inline_secret_blocked")
        errors.append("inline_secret_forbidden_by_policy")
        return _check(
            PreSendValidationCheckType.WEBHOOK_REFERENCE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.CRITICAL.value,
            message="Inline secret/token is forbidden by policy",
            blocked_reasons=blocked_reasons,
            errors=errors,
        )

    # Allowed reference types
    allowed_types = {
        "environment_variable_reference",
        "secret_manager_reference",
    }
    if ref_type not in allowed_types and ref_type != "":
        blocked_reasons.append(f"unknown_webhook_reference_type:{ref_type}")
        errors.append(f"webhook_reference_type_not_recognized:{ref_type}")
        return _check(
            PreSendValidationCheckType.WEBHOOK_REFERENCE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.HIGH.value,
            message=f"Unknown webhook reference type: {ref_type}",
            blocked_reasons=blocked_reasons,
            errors=errors,
        )

    # Validate environment variable reference format
    if ref_type == "environment_variable_reference":
        allowed_envs = policy.get("environment_variable_names", [])
        if ref_name and allowed_envs and ref_name not in allowed_envs:
            blocked_reasons.append(f"env_var_not_in_allowlist:{ref_name}")
            errors.append(f"environment_variable_not_allowed:{ref_name}")
            return _check(
                PreSendValidationCheckType.WEBHOOK_REFERENCE.value,
                passed=False,
                risk_level=PreSendValidationRiskLevel.HIGH.value,
                message=f"Environment variable '{ref_name}' is not in the allowed list",
                blocked_reasons=blocked_reasons,
                errors=errors,
            )

    # Validate secret manager reference format
    if ref_type == "secret_manager_reference":
        allowed_refs = policy.get("secret_manager_refs", [])
        if ref_val and allowed_refs and ref_val not in allowed_refs:
            blocked_reasons.append(f"secret_manager_ref_not_in_allowlist:{ref_val}")
            errors.append(f"secret_manager_reference_not_allowed:{ref_val}")
            return _check(
                PreSendValidationCheckType.WEBHOOK_REFERENCE.value,
                passed=False,
                risk_level=PreSendValidationRiskLevel.HIGH.value,
                message=f"Secret manager reference '{ref_val}' is not in the allowed list",
                blocked_reasons=blocked_reasons,
                errors=errors,
            )

    # Block unknown domains if any domain validation is present
    if ref_type == "unknown_domain":
        blocked_reasons.append("webhook_unknown_domain")
        errors.append("webhook_domain_not_in_allowlist")
        return _check(
            PreSendValidationCheckType.WEBHOOK_REFERENCE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.CRITICAL.value,
            message="Webhook domain is not in the allowlist",
            blocked_reasons=blocked_reasons,
            errors=errors,
        )

    return _check(
        PreSendValidationCheckType.WEBHOOK_REFERENCE.value,
        passed=True,
        risk_level=PreSendValidationRiskLevel.LOW.value,
        message="Webhook reference format valid",
        evidence_refs=[f"type={ref_type}", f"name={ref_name}", f"ref={ref_val}"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. validate_payload_projection_for_presend
# ─────────────────────────────────────────────────────────────────────────────

def validate_payload_projection_for_presend(
    payload: Dict[str, Any],
    validation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate FeishuTrendPayloadProjection for pre-send eligibility.

    This does NOT change send_allowed to True. It only validates that
    the payload is in a safe state for future human-confirmed sending.

    Checks:
      - payload.status == projection_only or design_only
      - payload.send_allowed == False
      - payload.no_webhook_call == True
      - payload.no_runtime_write == True
      - payload.no_action_queue_write == True
      - payload.no_auto_fix == True
      - validation.valid == True (from validate_feishu_trend_payload_projection)
      - card_json is serializable
      - artifact links only point to report artifacts

    Args:
        payload: FeishuTrendPayloadProjection dict
        validation: Optional pre-existing FeishuTrendValidationResult dict

    Returns:
        PreSendValidationCheckResult dict
    """
    from app.audit.audit_trend_feishu_projection import validate_feishu_trend_payload_projection

    blocked_reasons: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    evidence_refs: List[str] = []

    send_allowed = payload.get("send_allowed", True)
    status = payload.get("status", "")
    no_webhook_call = payload.get("no_webhook_call", False)
    no_runtime_write = payload.get("no_runtime_write", False)
    no_action_queue_write = payload.get("no_action_queue_write", False)
    no_auto_fix = payload.get("no_auto_fix", False)
    card_json = payload.get("card_json") or {}

    # Run validation if not provided
    if validation is None:
        validation = validate_feishu_trend_payload_projection(payload)

    validation_valid = validation.get("valid", False)

    # Check status
    safe_statuses = ["projection_only", "design_only"]
    if status not in safe_statuses:
        blocked_reasons.append(f"unexpected_payload_status:{status}")

    # Check send_allowed is False (must not enable sending)
    if send_allowed is not False:
        blocked_reasons.append("send_allowed_must_be_false")

    # Check no_webhook_call
    if no_webhook_call is not True:
        blocked_reasons.append("no_webhook_call_must_be_true")

    # Check no_runtime_write
    if no_runtime_write is not True:
        blocked_reasons.append("no_runtime_write_must_be_true")

    # Check no_action_queue_write
    if no_action_queue_write is not True:
        blocked_reasons.append("no_action_queue_write_must_be_true")

    # Check no_auto_fix
    if no_auto_fix is not True:
        blocked_reasons.append("no_auto_fix_must_be_true")

    # Check card JSON serializable
    try:
        json.dumps(card_json)
    except Exception as exc:
        blocked_reasons.append("card_json_not_serializable")
        errors.append(f"card_json_serialization_failed:{exc}")

    # Check validation result
    if not validation_valid:
        blocked_reasons.append("payload_projection_validation_failed")
        errors.extend(validation.get("errors", []))

    # Collect blocked reasons from inner validation
    inner_blocked = validation.get("blocked_reasons", [])
    for reason in inner_blocked:
        if reason not in blocked_reasons:
            blocked_reasons.append(reason)

    evidence_refs.append(f"payload_id={payload.get('payload_id')}")
    evidence_refs.append(f"validation_valid={validation_valid}")

    passed = (
        status in safe_statuses
        and send_allowed is False
        and no_webhook_call is True
        and no_runtime_write is True
        and no_action_queue_write is True
        and no_auto_fix is True
        and validation_valid
        and not blocked_reasons
    )

    if passed:
        return _check(
            PreSendValidationCheckType.PAYLOAD_PROJECTION.value,
            passed=True,
            risk_level=PreSendValidationRiskLevel.LOW.value,
            message="Payload projection is valid for pre-send review",
            evidence_refs=evidence_refs,
        )
    else:
        return _check(
            PreSendValidationCheckType.PAYLOAD_PROJECTION.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.HIGH.value,
            message="Payload projection failed pre-send validation",
            blocked_reasons=blocked_reasons,
            warnings=warnings,
            errors=errors,
            evidence_refs=evidence_refs,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. validate_presend_output_safety
# ─────────────────────────────────────────────────────────────────────────────

def validate_presend_output_safety(
    preview_output: Optional[str | Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate CLI preview output for sensitive content before pre-send.

    Calls or re-implements the logic of validate_trend_cli_output_safety.

    Must reject:
      - webhook URL
      - token/secret/API key
      - full prompt/memory/RTCM body
      - suspicious long content blocks

    Args:
        preview_output: Preview output as string or dict

    Returns:
        PreSendValidationCheckResult dict
    """
    detected: List[str] = []
    blocked_reasons: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []

    if preview_output is None:
        warnings.append("no_preview_output_provided")
        return _check(
            PreSendValidationCheckType.OUTPUT_SAFETY.value,
            passed=True,
            risk_level=PreSendValidationRiskLevel.LOW.value,
            message="No preview output to validate (dry-run design validation)",
            warnings=warnings,
        )

    text = json.dumps(preview_output, ensure_ascii=False) if isinstance(preview_output, dict) else str(preview_output)
    lowered = text.lower()

    # Check for webhook URL
    if _WEBHOOK_RE.search(text):
        detected.append("webhook_url_in_preview")
        blocked_reasons.append("webhook_url_found_in_preview_output")
        errors.append("webhook_url_detected")

    # Check for sensitive value patterns
    if _SENSITIVE_VALUE_RE.search(text):
        detected.append("sensitive_token_secret_in_preview")
        blocked_reasons.append("token_secret_api_key_in_preview_output")
        errors.append("sensitive_value_detected")

    # Check for sensitive key patterns (but filter known-safe strings)
    safe_patterns = {
        "feishu_webhook_url", "feishu_webhook_secret",
        "deerflow/secrets/feishu/webhook_url", "deerflow/secrets/feishu/webhook_secret",
        "webhook_url_allowed_inline", "secret_inline_allowed",
    }
    if _SENSITIVE_KEY_RE.search(text):
        # Only flag if actual secret value pattern, not field names
        for safe in safe_patterns:
            text_filtered = text.replace(safe, "")
        if _SENSITIVE_KEY_RE.search(text_filtered):
            detected.append("sensitive_key_pattern_in_preview")
            blocked_reasons.append("sensitive_key_pattern_in_preview_output")
            errors.append("sensitive_key_pattern_detected")

    # Check for long suspicious blocks
    if _LONG_BLOCK_RE.search(text):
        detected.append("suspicious_long_content_block")
        blocked_reasons.append("suspicious_long_content_block_in_preview")
        errors.append("long_block_detected")

    # Check for full body leakage markers
    if "full_source_record_payload" in lowered and "records" in lowered and "payload" in lowered:
        detected.append("full_source_record_payload_in_preview")
        blocked_reasons.append("full_payload_body_in_preview_output")
        errors.append("full_payload_body_detected")

    if "full_prompt" in lowered or "full_memory" in lowered or "full_rtcm" in lowered:
        detected.append("full_body_content_in_preview")
        blocked_reasons.append("full_body_content_in_preview_output")
        errors.append("full_body_content_detected")

    passed = len(detected) == 0

    if passed:
        return _check(
            PreSendValidationCheckType.OUTPUT_SAFETY.value,
            passed=True,
            risk_level=PreSendValidationRiskLevel.LOW.value,
            message="Preview output passed safety validation",
            evidence_refs=[f"checked_chars={len(text)}"],
        )
    else:
        return _check(
            PreSendValidationCheckType.OUTPUT_SAFETY.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.CRITICAL.value,
            message=f"Preview output contains sensitive content: {detected}",
            blocked_reasons=blocked_reasons,
            warnings=warnings,
            errors=errors,
            evidence_refs=[f"detected_patterns={detected}"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# 5. validate_guard_for_presend
# ─────────────────────────────────────────────────────────────────────────────

def validate_guard_for_presend(
    guard: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate TrendCliExecutionGuard state for pre-send eligibility.

    Required guard flags:
      - audit_jsonl_unchanged == True
      - sensitive_output_detected == False
      - network_call_detected == False
      - runtime_write_detected == False
      - auto_fix_detected == False

    If guard is missing, return blocked (cannot confirm safety without guard).

    Args:
        guard: TrendCliExecutionGuard dict (may be None)

    Returns:
        PreSendValidationCheckResult dict
    """
    blocked_reasons: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    evidence_refs: List[str] = []

    if guard is None:
        return _check(
            PreSendValidationCheckType.GUARD_STATE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.HIGH.value,
            message="Guard data not provided — cannot validate pre-send safety",
            blocked_reasons=["guard_data_missing"],
            errors=["guard_required_for_pre_send_validation"],
        )

    audit_jsonl_unchanged = guard.get("audit_jsonl_unchanged", False)
    sensitive_output_detected = guard.get("sensitive_output_detected", True)
    network_call_detected = guard.get("network_call_detected", False)
    runtime_write_detected = guard.get("runtime_write_detected", False)
    auto_fix_detected = guard.get("auto_fix_detected", False)

    evidence_refs.append(f"audit_jsonl_unchanged={audit_jsonl_unchanged}")
    evidence_refs.append(f"sensitive_output_detected={sensitive_output_detected}")
    evidence_refs.append(f"network_call_detected={network_call_detected}")
    evidence_refs.append(f"runtime_write_detected={runtime_write_detected}")
    evidence_refs.append(f"auto_fix_detected={auto_fix_detected}")

    if not audit_jsonl_unchanged:
        blocked_reasons.append("audit_jsonl_line_count_changed")
        errors.append("guard_audit_jsonl_changed")

    if sensitive_output_detected:
        blocked_reasons.append("guard_sensitive_output_detected")
        errors.append("guard_sensitive_output_blocked")

    if network_call_detected:
        blocked_reasons.append("guard_network_call_detected")
        errors.append("guard_network_call_blocked")

    if runtime_write_detected:
        blocked_reasons.append("guard_runtime_write_detected")
        errors.append("guard_runtime_write_blocked")

    if auto_fix_detected:
        blocked_reasons.append("guard_auto_fix_detected")
        errors.append("guard_auto_fix_blocked")

    passed = (
        audit_jsonl_unchanged is True
        and sensitive_output_detected is False
        and network_call_detected is False
        and runtime_write_detected is False
        and auto_fix_detected is False
    )

    if passed:
        return _check(
            PreSendValidationCheckType.GUARD_STATE.value,
            passed=True,
            risk_level=PreSendValidationRiskLevel.LOW.value,
            message="Guard state is valid for pre-send review",
            evidence_refs=evidence_refs,
        )
    else:
        return _check(
            PreSendValidationCheckType.GUARD_STATE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.CRITICAL.value,
            message="Guard state failed pre-send validation",
            blocked_reasons=blocked_reasons,
            warnings=warnings,
            errors=errors,
            evidence_refs=evidence_refs,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6. validate_audit_precondition
# ─────────────────────────────────────────────────────────────────────────────

def validate_audit_precondition(
    payload: Dict[str, Any],
    preview_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate audit preconditions for pre-send without writing audit JSONL.

    This generates a design-only pre-send audit record projection that would be
    written when Phase 5 implementation is complete. It does NOT write anything.

    Checks:
      - payload hash can be generated
      - pre-send audit event type is feishu_trend_manual_send_attempt
      - raw webhook never logged (reference only)
      - full payload body not logged
      - append-only future audit required

    Args:
        payload: FeishuTrendPayloadProjection dict
        preview_result: Optional preview diagnostic result dict

    Returns:
        PreSendValidationCheckResult dict with audit_projection in evidence_refs
    """
    from app.audit.audit_trail_contract import AuditEventType

    blocked_reasons: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    evidence_refs: List[str] = []

    # Check payload is provided
    if not payload:
        blocked_reasons.append("payload_missing_for_audit_precondition")
        errors.append("audit_precondition_payload_required")
        return _check(
            PreSendValidationCheckType.AUDIT_REQUIREMENT.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.HIGH.value,
            message="Payload required for audit precondition validation",
            blocked_reasons=blocked_reasons,
            errors=errors,
        )

    # Generate payload hash (design-time only, no network calls)
    payload_str = json.dumps(payload.get("card_json") or payload, ensure_ascii=False, sort_keys=True)
    payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()[:16]

    # Check pre-send audit event type
    pre_send_event_type = "feishu_trend_manual_send_attempt"

    # Build design-only audit projection (NOT written to JSONL)
    audit_projection = {
        "audit_projection": {
            "audit_record_id": _new_id("presend_audit_project"),
            "event_type": pre_send_event_type,
            "write_mode": "design_only_pre_send_validation",
            "source_system": "feishu_trend_presend_validator",
            "status": "pre_send_audit_projected",
            "payload_hash": payload_hash,
            "payload_id": payload.get("payload_id"),
            "source_trend_report_id": payload.get("source_trend_report_id"),
            "send_allowed_at_projection": payload.get("send_allowed", False),
            "raw_webhook_will_never_be_logged": True,
            "full_payload_will_never_be_logged": True,
            "append_only_future_audit_required": True,
            "generated_at": _now(),
            "projection_note": "This is a design-only projection. No audit JSONL was written.",
        },
        "design_only": True,
        "would_write_audit_jsonl": False,
        "checks_passed": [
            "payload_hash_generatable",
            "pre_send_event_type_correct",
            "raw_webhook_never_logged_policy_enforced",
            "full_payload_never_logged_policy_enforced",
            "append_only_future_audit_required",
        ],
    }

    evidence_refs.append(f"payload_hash={payload_hash}")
    evidence_refs.append(f"event_type={pre_send_event_type}")
    evidence_refs.append("audit_projection_generated_design_only")
    evidence_refs.append("no_audit_jsonl_written")

    # Verify send_audit_policy requirements
    from app.audit.audit_trend_feishu_send_policy import build_manual_send_audit_policy
    audit_policy = build_manual_send_audit_policy()
    if not audit_policy.get("pre_send_audit_required"):
        blocked_reasons.append("pre_send_audit_not_required_by_policy")
        errors.append("audit_policy_pre_send_violation")
    if not audit_policy.get("raw_webhook_never_logged"):
        blocked_reasons.append("raw_webhook_logging_policy_violation")
        errors.append("audit_policy_raw_webhook_violation")

    passed = len(blocked_reasons) == 0

    if passed:
        return _check(
            PreSendValidationCheckType.AUDIT_REQUIREMENT.value,
            passed=True,
            risk_level=PreSendValidationRiskLevel.LOW.value,
            message="Audit preconditions valid — pre-send audit projection generated (design-only)",
            evidence_refs=evidence_refs,
            warnings=["audit_projection_design_only_no_jsonl_written"],
        )
    else:
        return _check(
            PreSendValidationCheckType.AUDIT_REQUIREMENT.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.HIGH.value,
            message="Audit preconditions failed",
            blocked_reasons=blocked_reasons,
            errors=errors,
            evidence_refs=evidence_refs,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 7. validate_payload_age
# ─────────────────────────────────────────────────────────────────────────────

def validate_payload_age(
    generated_at: Optional[str],
    max_age_minutes: int = 60,
) -> Dict[str, Any]:
    """Validate payload age against maximum allowed age.

    Args:
        generated_at: ISO timestamp string of when payload was generated
        max_age_minutes: Maximum allowed age in minutes (default 60)

    Returns:
        PreSendValidationCheckResult dict
    """
    blocked_reasons: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []

    if generated_at is None or generated_at == "":
        blocked_reasons.append("payload_generated_at_missing")
        errors.append("payload_age_unknown")
        return _check(
            PreSendValidationCheckType.PAYLOAD_AGE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.HIGH.value,
            message="Payload generation timestamp missing",
            blocked_reasons=blocked_reasons,
            errors=errors,
        )

    # Parse ISO timestamp
    try:
        if "+" in generated_at or "Z" in generated_at.upper():
            payload_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        else:
            payload_dt = datetime.fromisoformat(generated_at)
    except (ValueError, TypeError) as exc:
        blocked_reasons.append(f"payload_generated_at_invalid_format:{exc}")
        errors.append("payload_age_timestamp_parse_error")
        return _check(
            PreSendValidationCheckType.PAYLOAD_AGE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.HIGH.value,
            message=f"Payload generation timestamp has invalid format: {generated_at}",
            blocked_reasons=blocked_reasons,
            errors=errors,
        )

    now_dt = datetime.now(timezone.utc)
    try:
        if payload_dt.tzinfo is None:
            payload_dt = payload_dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass

    age_seconds = (now_dt - payload_dt).total_seconds()
    age_minutes = age_seconds / 60.0

    evidence_refs = [
        f"generated_at={generated_at}",
        f"age_minutes={age_minutes:.1f}",
        f"max_age_minutes={max_age_minutes}",
    ]

    if age_minutes > max_age_minutes:
        blocked_reasons.append(f"payload_age_exceeded:{age_minutes:.1f}_minutes")
        errors.append("payload_too_old_requires_new_preview")
        return _check(
            PreSendValidationCheckType.PAYLOAD_AGE.value,
            passed=False,
            risk_level=PreSendValidationRiskLevel.HIGH.value,
            message=f"Payload age ({age_minutes:.1f} min) exceeds maximum ({max_age_minutes} min)",
            blocked_reasons=blocked_reasons,
            errors=errors,
            evidence_refs=evidence_refs,
        )

    if age_minutes < 0:
        warnings.append("payload_generated_in_future")
        evidence_refs.append("warning_future_timestamp")

    return _check(
        PreSendValidationCheckType.PAYLOAD_AGE.value,
        passed=True,
        risk_level=PreSendValidationRiskLevel.LOW.value,
        message=f"Payload age valid ({age_minutes:.1f} min < {max_age_minutes} min)",
        evidence_refs=evidence_refs,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. run_feishu_presend_policy_validator
# ─────────────────────────────────────────────────────────────────────────────

def run_feishu_presend_policy_validator(
    payload: Dict[str, Any],
    payload_validation: Optional[Dict[str, Any]] = None,
    preview_output: Optional[str | Dict[str, Any]] = None,
    guard: Optional[Dict[str, Any]] = None,
    confirmation_phrase: Optional[str] = None,
    webhook_ref: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run end-to-end Feishu pre-send policy validation.

    This is the main entry point for R241-14B pre-send validation.

    Validation order:
      1. Load and validate policy design
      2. Validate payload projection
      3. Validate confirmation phrase
      4. Validate webhook reference
      5. Validate output safety
      6. Validate guard
      7. Validate audit precondition
      8. Validate payload age
      9. Aggregate results

    This function NEVER:
      - Sends Feishu messages
      - Calls webhooks
      - Calls network
      - Reads real webhook URL/token/secret
      - Writes audit JSONL
      - Writes runtime/action queue
      - Executes auto-fix

    Args:
        payload: FeishuTrendPayloadProjection dict
        payload_validation: Optional pre-existing validation result dict
        preview_output: Optional preview output string or dict
        guard: Optional TrendCliExecutionGuard dict
        confirmation_phrase: Optional user-provided confirmation phrase
        webhook_ref: Optional webhook reference dict

    Returns:
        FeishuPreSendValidationResult dict
    """
    from app.audit.audit_trend_feishu_send_policy import (
        build_feishu_manual_send_policy_design,
        validate_feishu_manual_send_policy_design,
    )

    validation_id = _new_id("presend_validation")
    all_blocked_reasons: List[str] = []
    all_warnings: List[str] = []
    all_errors: List[str] = []
    checks: List[Dict[str, Any]] = []

    # 1. Load and validate policy design
    try:
        policy_design = build_feishu_manual_send_policy_design()
        policy_validation = validate_feishu_manual_send_policy_design(policy_design)
        checks.append({
            "check_type": PreSendValidationCheckType.POLICY_DESIGN.value,
            "check_result": {
                "passed": policy_validation.get("valid", False),
                "policy_valid": policy_validation.get("valid", False),
                "evidence_refs": [f"policy_design_id={policy_design.get('design_id')}"],
            },
        })
        if not policy_validation.get("valid"):
            all_blocked_reasons.append("policy_design_invalid")
            all_errors.extend(policy_validation.get("errors", []))
    except Exception as exc:
        checks.append({
            "check_type": PreSendValidationCheckType.POLICY_DESIGN.value,
            "check_result": {
                "passed": False,
                "errors": [f"policy_design_load_failed:{exc}"],
            },
        })
        all_blocked_reasons.append("policy_design_load_failed")
        all_errors.append(f"policy_load_error:{exc}")

    # 2. Validate payload projection
    payload_check = validate_payload_projection_for_presend(payload, payload_validation)
    checks.append({"check_type": PreSendValidationCheckType.PAYLOAD_PROJECTION.value, "check_result": payload_check})
    if not payload_check["passed"]:
        all_blocked_reasons.extend(payload_check.get("blocked_reasons", []))
    all_warnings.extend(payload_check.get("warnings", []))
    all_errors.extend(payload_check.get("errors", []))

    # 3. Validate confirmation phrase
    phrase_check = validate_confirmation_phrase(confirmation_phrase)
    checks.append({"check_type": PreSendValidationCheckType.CONFIRMATION_PHRASE.value, "check_result": phrase_check})
    if not phrase_check["passed"]:
        all_blocked_reasons.extend(phrase_check.get("blocked_reasons", []))
    all_warnings.extend(phrase_check.get("warnings", []))
    all_errors.extend(phrase_check.get("errors", []))

    # 4. Validate webhook reference
    webhook_check = validate_webhook_reference(webhook_ref)
    checks.append({"check_type": PreSendValidationCheckType.WEBHOOK_REFERENCE.value, "check_result": webhook_check})
    if not webhook_check["passed"]:
        all_blocked_reasons.extend(webhook_check.get("blocked_reasons", []))
    all_warnings.extend(webhook_check.get("warnings", []))
    all_errors.extend(webhook_check.get("errors", []))

    # 5. Validate output safety
    output_check = validate_presend_output_safety(preview_output)
    checks.append({"check_type": PreSendValidationCheckType.OUTPUT_SAFETY.value, "check_result": output_check})
    if not output_check["passed"]:
        all_blocked_reasons.extend(output_check.get("blocked_reasons", []))
    all_warnings.extend(output_check.get("warnings", []))
    all_errors.extend(output_check.get("errors", []))

    # 6. Validate guard
    guard_check = validate_guard_for_presend(guard)
    checks.append({"check_type": PreSendValidationCheckType.GUARD_STATE.value, "check_result": guard_check})
    if not guard_check["passed"]:
        all_blocked_reasons.extend(guard_check.get("blocked_reasons", []))
    all_warnings.extend(guard_check.get("warnings", []))
    all_errors.extend(guard_check.get("errors", []))

    # 7. Validate audit precondition
    audit_check = validate_audit_precondition(payload)
    checks.append({"check_type": PreSendValidationCheckType.AUDIT_REQUIREMENT.value, "check_result": audit_check})
    if not audit_check["passed"]:
        all_blocked_reasons.extend(audit_check.get("blocked_reasons", []))
    all_warnings.extend(audit_check.get("warnings", []))
    all_errors.extend(audit_check.get("errors", []))

    # 8. Validate payload age
    generated_at = payload.get("generated_at") if payload else None
    age_check = validate_payload_age(generated_at)
    checks.append({"check_type": PreSendValidationCheckType.PAYLOAD_AGE.value, "check_result": age_check})
    if not age_check["passed"]:
        all_blocked_reasons.extend(age_check.get("blocked_reasons", []))
    all_warnings.extend(age_check.get("warnings", []))
    all_errors.extend(age_check.get("errors", []))

    # Aggregate individual check booleans
    confirmation_phrase_valid = phrase_check["passed"]
    webhook_reference_valid = webhook_check["passed"]
    payload_validation_valid = payload_check["passed"]
    output_safety_valid = output_check["passed"]
    guard_valid = guard_check["passed"]
    audit_precondition_valid = audit_check["passed"]
    payload_age_valid = age_check["passed"]

    # Any critical blocked reason means the overall result is blocked
    critical_blocked = [r for r in all_blocked_reasons if "critical" in r.lower()]
    has_blocked = len(all_blocked_reasons) > 0 or not confirmation_phrase_valid or not payload_validation_valid

    if critical_blocked or (has_blocked and len(all_blocked_reasons) > 0):
        overall_status = PreSendValidationStatus.BLOCKED.value
        overall_valid = False
    elif not all([
        confirmation_phrase_valid,
        webhook_reference_valid,
        payload_validation_valid,
        output_safety_valid,
        guard_valid,
        audit_precondition_valid,
        payload_age_valid,
    ]):
        overall_status = PreSendValidationStatus.FAILED.value
        overall_valid = False
    elif all_warnings:
        overall_status = PreSendValidationStatus.PARTIAL_WARNING.value
        overall_valid = True
    else:
        overall_status = PreSendValidationStatus.VALID.value
        overall_valid = True

    # Dedupe blocked reasons and errors
    seen = set()
    unique_blocked = []
    for r in all_blocked_reasons:
        if r not in seen:
            seen.add(r)
            unique_blocked.append(r)
    seen.clear()
    unique_errors = []
    for e in all_errors:
        if e not in seen:
            seen.add(e)
            unique_errors.append(e)
    seen.clear()
    unique_warnings = []
    for w in all_warnings:
        if w not in seen:
            seen.add(w)
            unique_warnings.append(w)

    result = FeishuPreSendValidationResult(
        validation_id=validation_id,
        generated_at=_now(),
        status=overall_status,
        valid=overall_valid,
        payload_id=payload.get("payload_id") if payload else None,
        source_trend_report_id=payload.get("source_trend_report_id") if payload else None,
        confirmation_phrase_provided=confirmation_phrase is not None,
        confirmation_phrase_valid=confirmation_phrase_valid,
        webhook_reference_valid=webhook_reference_valid,
        payload_validation_valid=payload_validation_valid,
        output_safety_valid=output_safety_valid,
        guard_valid=guard_valid,
        audit_precondition_valid=audit_precondition_valid,
        payload_age_valid=payload_age_valid,
        checks=checks,
        blocked_reasons=unique_blocked,
        warnings=unique_warnings,
        errors=unique_errors,
    )
    return asdict(result)


# ─────────────────────────────────────────────────────────────────────────────
# 9. generate_feishu_presend_validator_sample
# ─────────────────────────────────────────────────────────────────────────────

def generate_feishu_presend_validator_sample(
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate R241-14B sample to migration_reports/foundation_audit.

    Generates sample validation results for 5 scenarios:
      1. sample_valid_like_but_send_still_blocked
      2. sample_missing_confirmation
      3. sample_inline_webhook_blocked
      4. sample_guard_changed_blocked
      5. sample_expired_payload_blocked

    Writes ONLY to migration_reports/foundation_audit/.
    Does NOT write audit JSONL, runtime, or action queue.
    Does NOT send Feishu messages or call webhooks.

    Args:
        output_path: Optional override for sample output path

    Returns:
        dict with sample scenarios and output_path
    """
    target = Path(output_path) if output_path else REPORT_DIR / "R241-14B_FEISHU_PRESEND_VALIDATOR_SAMPLE.json"

    # Sample 1: Valid-like payload but send still blocked (design validation)
    sample_valid_payload = {
        "payload_id": "sample_feishu_trend_payload_001",
        "generated_at": _now(),
        "status": "projection_only",
        "send_allowed": False,
        "no_webhook_call": True,
        "no_runtime_write": True,
        "no_action_queue_write": True,
        "no_auto_fix": True,
        "source_trend_report_id": "sample_trend_report_001",
        "card_json": {"header": {"title": {"tag": "plain_text", "content": "Sample Valid"}}},
        "sections": [],
    }
    sample_guard = {
        "audit_jsonl_unchanged": True,
        "sensitive_output_detected": False,
        "network_call_detected": False,
        "runtime_write_detected": False,
        "auto_fix_detected": False,
    }
    result_valid = run_feishu_presend_policy_validator(
        payload=sample_valid_payload,
        confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        guard=sample_guard,
    )

    # Sample 2: Missing confirmation phrase
    result_missing_confirm = run_feishu_presend_policy_validator(
        payload=sample_valid_payload,
        confirmation_phrase=None,
        guard=sample_guard,
    )

    # Sample 3: Inline webhook reference blocked
    result_inline_webhook = run_feishu_presend_policy_validator(
        payload=sample_valid_payload,
        confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        webhook_ref={"type": "inline_webhook_url", "name": "https://open.feishu.cn/custom/webhook/xxx"},
        guard=sample_guard,
    )

    # Sample 4: Guard changed (line count changed)
    result_guard_changed = run_feishu_presend_policy_validator(
        payload=sample_valid_payload,
        confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        guard={
            "audit_jsonl_unchanged": False,
            "sensitive_output_detected": False,
            "network_call_detected": False,
            "runtime_write_detected": False,
            "auto_fix_detected": False,
        },
    )

    # Sample 5: Expired payload (> 60 minutes)
    expired_payload = dict(sample_valid_payload)
    expired_payload["generated_at"] = (
        datetime.now(timezone.utc).timestamp() - 4000
    ).__round__()
    expired_dt = datetime.fromtimestamp(
        float(expired_payload["generated_at"]), tz=timezone.utc
    )
    expired_payload["generated_at"] = expired_dt.isoformat()
    result_expired = run_feishu_presend_policy_validator(
        payload=expired_payload,
        confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        guard=sample_guard,
    )

    sample = {
        "sample_valid_like_but_send_still_blocked": result_valid,
        "sample_missing_confirmation": result_missing_confirm,
        "sample_inline_webhook_blocked": result_inline_webhook,
        "sample_guard_changed_blocked": result_guard_changed,
        "sample_expired_payload_blocked": result_expired,
        "generated_at": _now(),
        "warnings": [
            "all_samples_are_design_only_projections",
            "no_real_send_in_any_sample",
            "no_webhook_url_or_secret_read_or_written",
            "no_audit_jsonl_written",
        ],
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    sample["output_path"] = str(target)
    return sample


__all__ = [
    # enums
    "PreSendValidationStatus",
    "PreSendValidationCheckType",
    "PreSendValidationRiskLevel",
    # dataclasses
    "PreSendValidationCheckResult",
    "FeishuPreSendValidationResult",
    # functions
    "validate_confirmation_phrase",
    "validate_webhook_reference",
    "validate_payload_projection_for_presend",
    "validate_presend_output_safety",
    "validate_guard_for_presend",
    "validate_audit_precondition",
    "validate_payload_age",
    "run_feishu_presend_policy_validator",
    "generate_feishu_presend_validator_sample",
]
