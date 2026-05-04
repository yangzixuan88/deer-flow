"""Feishu/Lark trend manual send policy design contract (R241-13D).

This module is design-only. It defines the policy contracts for future manual
Feishu/Lark trend card sending. It never sends messages, never calls
webhooks/network, never writes audit JSONL, and never writes runtime/action queue state.

This module is NOT responsible for implementing real Feishu send.
It ONLY defines the policy/validation/confirmation/audit contracts.

Design principles:
  - webhook URL must never be inline — must come from allowlist or secret manager
  - user confirmation is always required before sending
  - pre-send and post-send audit records are always required
  - raw webhook payload/response must never be logged
  - scheduler auto-send is forbidden without separate review
  - auto-fix is always forbidden during manual send flow
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
DEFAULT_CONTRACT_PATH = REPORT_DIR / "R241-13D_MANUAL_SEND_POLICY_CONTRACT.json"

_WEBHOOK_RE = re.compile(r"https?://[^\s\"']*(?:webhook|hook|open\.feishu|larksuite)[^\s\"']*", re.IGNORECASE)
_SENSITIVE_KEY_RE = re.compile(
    r"\b(webhook_url|api_key|token|secret|password|secret_key|access_token|secret_manager)\b",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class FeishuManualSendPolicyStatus(str, Enum):
    DESIGN_ONLY = "design_only"
    POLICY_READY = "policy_ready"
    BLOCKED_MISSING_WEBHOOK_POLICY = "blocked_missing_webhook_policy"
    BLOCKED_MISSING_USER_CONFIRMATION = "blocked_missing_user_confirmation"
    BLOCKED_SENSITIVE_PAYLOAD = "blocked_sensitive_payload"
    BLOCKED_INVALID_PAYLOAD = "blocked_invalid_payload"
    BLOCKED_AUDIT_REQUIRED = "blocked_audit_required"
    UNKNOWN = "unknown"


class FeishuManualSendPermission(str, Enum):
    FORBIDDEN = "forbidden"
    DRY_RUN_ONLY = "dry_run_only"
    MANUAL_SEND_ALLOWED_LATER = "manual_send_allowed_later"
    REQUIRES_USER_CONFIRMATION = "requires_user_confirmation"
    REQUIRES_WEBHOOK_ALLOWLIST = "requires_webhook_allowlist"
    REQUIRES_PAYLOAD_VALIDATION = "requires_payload_validation"
    REQUIRES_AUDIT_RECORD = "requires_audit_record"
    UNKNOWN = "unknown"


class FeishuWebhookPolicyType(str, Enum):
    ALLOWLIST_ONLY = "allowlist_only"
    ENVIRONMENT_VARIABLE_REFERENCE = "environment_variable_reference"
    SECRET_MANAGER_REFERENCE = "secret_manager_reference"
    FORBIDDEN_INLINE_SECRET = "forbidden_inline_secret"
    UNKNOWN = "unknown"


class FeishuManualSendAuditMode(str, Enum):
    NO_SEND_NO_AUDIT = "no_send_no_audit"
    DRY_RUN_AUDIT_ONLY = "dry_run_audit_only"
    PRE_SEND_AUDIT_REQUIRED = "pre_send_audit_required"
    POST_SEND_AUDIT_REQUIRED = "post_send_audit_required"
    APPEND_ONLY_SEND_AUDIT_LATER = "append_only_send_audit_later"
    UNKNOWN = "unknown"


class FeishuManualSendRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FeishuWebhookPolicy:
    policy_id: str
    policy_type: str
    webhook_ref_name: Optional[str] = None
    webhook_url_allowed_inline: bool = False
    secret_inline_allowed: bool = False
    allowlist_required: bool = True
    allowed_domain_patterns: List[str] = field(default_factory=list)
    allowed_bot_names: List[str] = field(default_factory=list)
    environment_variable_names: List[str] = field(default_factory=list)
    secret_manager_refs: List[str] = field(default_factory=list)
    rotation_required: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class FeishuManualSendConfirmationPolicy:
    confirmation_policy_id: str
    user_confirmation_required: bool = True
    confirmation_phrase_required: bool = True
    required_confirmation_phrase: str = "CONFIRM_FEISHU_TREND_SEND"
    confirm_after_preview_required: bool = True
    confirm_after_validation_required: bool = True
    confirm_after_audit_preview_required: bool = True
    max_payload_age_minutes: int = 60
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class FeishuPayloadPreSendValidationPolicy:
    validation_policy_id: str
    require_projection_validation_valid: bool = True
    require_send_allowed_transition_review: bool = True
    require_no_sensitive_content: bool = True
    require_no_webhook_url_in_payload: bool = True
    require_no_token_secret_api_key: bool = True
    require_no_runtime_write: bool = True
    require_no_action_queue_write: bool = True
    require_no_auto_fix: bool = True
    require_guard_jsonl_unchanged: bool = True
    require_card_json_serializable: bool = True
    require_artifact_links_only_report_artifacts: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class FeishuManualSendAuditPolicy:
    audit_policy_id: str
    pre_send_audit_required: bool = True
    post_send_audit_required: bool = True
    audit_event_type: str = "feishu_trend_manual_send_attempt"
    audit_result_event_type: str = "feishu_trend_manual_send_result"
    audit_write_mode: str = "append_only"
    append_only_required: bool = True
    payload_hash_required: bool = True
    redaction_required: bool = True
    raw_webhook_never_logged: bool = True
    send_result_metadata_only: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class FeishuManualSendPolicyDesign:
    design_id: str
    generated_at: str
    status: str
    webhook_policy: Dict[str, Any]
    confirmation_policy: Dict[str, Any]
    pre_send_validation_policy: Dict[str, Any]
    send_audit_policy: Dict[str, Any]
    blocked_send_paths: List[Dict[str, Any]]
    allowed_future_send_flow: List[Dict[str, Any]]
    implementation_phases: List[Dict[str, Any]]
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# 1. build_feishu_webhook_policy
# ─────────────────────────────────────────────────────────────────────────────

def build_feishu_webhook_policy() -> Dict[str, Any]:
    """Build the default Feishu webhook policy.

    Key constraints enforced:
      - webhook_url_allowed_inline = False (never inline)
      - secret_inline_allowed = False (never inline)
      - allowlist_required = True
      - FORBIDDEN_INLINE_SECRET policy type
      - Allowed future types: ALLOWLIST_ONLY, ENVIRONMENT_VARIABLE_REFERENCE,
        SECRET_MANAGER_REFERENCE (but no actual reading of env/secrets here)

    Returns:
        dict representation of FeishuWebhookPolicy

    No network calls. No secret reading. No webhook calls.
    """
    policy = FeishuWebhookPolicy(
        policy_id=_new_id("feishu_webhook_policy"),
        policy_type=FeishuWebhookPolicyType.FORBIDDEN_INLINE_SECRET.value,
        webhook_ref_name=None,
        webhook_url_allowed_inline=False,
        secret_inline_allowed=False,
        allowlist_required=True,
        allowed_domain_patterns=[
            "*.open.feishu.cn",
            "*.larksuite.com",
        ],
        allowed_bot_names=[
            "DeerFlow-Assistant",
        ],
        environment_variable_names=[
            "FEISHU_WEBHOOK_URL",
            "FEISHU_WEBHOOK_SECRET",
        ],
        secret_manager_refs=[
            "deerflow/secrets/feishu/webhook_url",
            "deerflow/secrets/feishu/webhook_secret",
        ],
        rotation_required=True,
        warnings=[
            "inline_webhook_url_forbidden",
            "inline_secret_forbidden",
            "webhook_url_must_come_from_allowlist_or_secret_manager",
            "secret_must_come_from_environment_or_secret_manager",
        ],
        errors=[],
    )
    return asdict(policy)


# ─────────────────────────────────────────────────────────────────────────────
# 2. build_manual_send_confirmation_policy
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_send_confirmation_policy() -> Dict[str, Any]:
    """Build the manual send confirmation policy.

    Key constraints enforced:
      - user_confirmation_required = True
      - confirmation_phrase_required = True
      - confirm_after_preview_required = True
      - confirm_after_validation_required = True
      - confirm_after_audit_preview_required = True
      - max_payload_age_minutes = 60 (must re-preview if older)

    Returns:
        dict representation of FeishuManualSendConfirmationPolicy

    No writes. No network calls.
    """
    policy = FeishuManualSendConfirmationPolicy(
        confirmation_policy_id=_new_id("feishu_confirmation_policy"),
        user_confirmation_required=True,
        confirmation_phrase_required=True,
        required_confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        confirm_after_preview_required=True,
        confirm_after_validation_required=True,
        confirm_after_audit_preview_required=True,
        max_payload_age_minutes=60,
        warnings=[
            "confirmation_required_before_any_send",
            "payload_age_expiry_requires_new_preview",
            "phrase_must_be_exact_match",
        ],
        errors=[],
    )
    return asdict(policy)


# ─────────────────────────────────────────────────────────────────────────────
# 3. build_pre_send_validation_policy
# ─────────────────────────────────────────────────────────────────────────────

def build_pre_send_validation_policy() -> Dict[str, Any]:
    """Build the pre-send payload validation policy.

    Validates that a payload is safe to send before any send operation:
      - projection validation must be valid
      - no sensitive content in payload
      - no webhook URL in card JSON
      - no token/secret/api_key in payload
      - no runtime write risk
      - no action queue write risk
      - no auto-fix
      - guard audit_jsonl_unchanged must be True
      - card_json must be JSON serializable
      - artifact links must only point to report artifacts

    Returns:
        dict representation of FeishuPayloadPreSendValidationPolicy

    No writes. No network calls.
    """
    policy = FeishuPayloadPreSendValidationPolicy(
        validation_policy_id=_new_id("feishu_pre_send_validation_policy"),
        require_projection_validation_valid=True,
        require_send_allowed_transition_review=True,
        require_no_sensitive_content=True,
        require_no_webhook_url_in_payload=True,
        require_no_token_secret_api_key=True,
        require_no_runtime_write=True,
        require_no_action_queue_write=True,
        require_no_auto_fix=True,
        require_guard_jsonl_unchanged=True,
        require_card_json_serializable=True,
        require_artifact_links_only_report_artifacts=True,
        warnings=[
            "all_pre_send_checks_required",
            "payload_must_pass_all_validation_rules",
            "guard_line_count_must_be_unchanged",
        ],
        errors=[],
    )
    return asdict(policy)


# ─────────────────────────────────────────────────────────────────────────────
# 4. build_manual_send_audit_policy
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_send_audit_policy() -> Dict[str, Any]:
    """Build the manual send audit policy.

    Key constraints enforced:
      - pre_send_audit_required = True (before any send attempt)
      - post_send_audit_required = True (after send result)
      - append_only_required = True (never modify existing audit records)
      - payload_hash_required = True (hash of payload for integrity)
      - redaction_required = True (sensitive fields redacted before logging)
      - raw_webhook_never_logged = True (webhook URL/response never in audit)
      - send_result_metadata_only = True (only outcome metadata, not full content)

    Event types:
      - feishu_trend_manual_send_attempt (pre-send, recording intent)
      - feishu_trend_manual_send_result (post-send, recording outcome)

    Returns:
        dict representation of FeishuManualSendAuditPolicy

    This is design-only — this phase does NOT write any audit JSONL.
    """
    policy = FeishuManualSendAuditPolicy(
        audit_policy_id=_new_id("feishu_send_audit_policy"),
        pre_send_audit_required=True,
        post_send_audit_required=True,
        audit_event_type="feishu_trend_manual_send_attempt",
        audit_result_event_type="feishu_trend_manual_send_result",
        audit_write_mode="append_only",
        append_only_required=True,
        payload_hash_required=True,
        redaction_required=True,
        raw_webhook_never_logged=True,
        send_result_metadata_only=True,
        warnings=[
            "pre_send_audit_record_required_before_any_send",
            "post_send_audit_record_required_after_every_send",
            "raw_webhook_url_and_response_never_in_audit",
            "only_metadata_in_audit_not_full_payload",
        ],
        errors=[],
    )
    return asdict(policy)


# ─────────────────────────────────────────────────────────────────────────────
# 5. design_allowed_manual_send_flow
# ─────────────────────────────────────────────────────────────────────────────

def design_allowed_manual_send_flow() -> List[Dict[str, Any]]:
    """Define the 12-step allowed manual send flow.

    Each step has: phase, allowed_now, required_checks, forbidden_actions.

    Current state: allowed_now is True only through step 6 (webhook resolution).
    Steps 7-12 (actual send) are blocked pending Phase 5 implementation.

    Returns:
        list of 12 flow step dicts

    No writes. No network calls.
    """
    return [
        {
            "phase": 1,
            "step": "Generate trend report dry-run",
            "allowed_now": True,
            "required_checks": ["run_guarded_audit_trend_cli_projection(write_report=False)"],
            "forbidden_actions": [
                "write_audit_jsonl",
                "write_runtime",
                "write_action_queue",
                "network_call",
                "webhook_call",
            ],
        },
        {
            "phase": 2,
            "step": "Generate Feishu payload projection",
            "allowed_now": True,
            "required_checks": ["build_feishu_trend_payload_projection()"],
            "forbidden_actions": [
                "send_allowed=true",
                "write_audit_jsonl",
                "webhook_call",
            ],
        },
        {
            "phase": 3,
            "step": "Validate payload projection",
            "allowed_now": True,
            "required_checks": ["validate_feishu_trend_payload_projection() returns valid=True"],
            "forbidden_actions": [
                "send_allowed=true",
                "write_audit_jsonl",
                "webhook_call",
            ],
        },
        {
            "phase": 4,
            "step": "Render CLI preview",
            "allowed_now": True,
            "required_checks": ["format_feishu_trend_payload_preview()"],
            "forbidden_actions": [
                "send_allowed=true",
                "write_audit_jsonl",
                "webhook_call",
            ],
        },
        {
            "phase": 5,
            "step": "Validate output safety",
            "allowed_now": True,
            "required_checks": [
                "validate_trend_cli_output_safety()",
                "no webhook URL in preview",
                "no sensitive content in preview",
            ],
            "forbidden_actions": [
                "send_allowed=true",
                "write_audit_jsonl",
                "webhook_call",
            ],
        },
        {
            "phase": 6,
            "step": "Resolve webhook from allowlist / secret manager reference",
            "allowed_now": True,
            "required_checks": [
                "webhook_url_from_allowlist_only",
                "no inline webhook URL",
                "FEISHU_WEBHOOK_URL env var or secret manager reference",
            ],
            "forbidden_actions": [
                "inline_webhook_url",
                "inline_secret",
                "write_audit_jsonl",
                "send_allowed=true",
            ],
        },
        {
            "phase": 7,
            "step": "Require user confirmation phrase",
            "allowed_now": False,
            "required_checks": [
                "user must type CONFIRM_FEISHU_TREND_SEND",
                "payload age must be < 60 minutes",
            ],
            "forbidden_actions": [
                "auto_send_without_confirmation",
                "scheduler_triggered_send",
                "write_audit_jsonl",
            ],
        },
        {
            "phase": 8,
            "step": "Create pre-send audit record projection",
            "allowed_now": False,
            "required_checks": [
                "pre_send_audit_record with feishu_trend_manual_send_attempt",
                "append_only mode",
                "payload_hash recorded",
            ],
            "forbidden_actions": [
                "write_audit_jsonl (before audit record)",
                "raw_webhook_in_audit",
                "full_payload_body_in_audit",
            ],
        },
        {
            "phase": 9,
            "step": "Send manually through dedicated send function",
            "allowed_now": False,
            "required_checks": [
                "Phase 5 implementation complete",
                "webhook resolver implemented",
                "confirmation handler implemented",
            ],
            "forbidden_actions": [
                "scheduler_auto_send",
                "write_runtime",
                "write_action_queue",
            ],
        },
        {
            "phase": 10,
            "step": "Create post-send audit record",
            "allowed_now": False,
            "required_checks": [
                "post_send_audit_record with feishu_trend_manual_send_result",
                "append_only mode",
                "only metadata (not raw response)",
            ],
            "forbidden_actions": [
                "raw_webhook_response_in_audit",
                "modify_existing_audit_record",
            ],
        },
        {
            "phase": 11,
            "step": "Never auto-fix",
            "allowed_now": False,
            "required_checks": ["auto_fix always forbidden in manual send flow"],
            "forbidden_actions": [
                "auto_fix",
                "auto_remediation",
                "auto_correct",
            ],
        },
        {
            "phase": 12,
            "step": "Never scheduler-send without separate review",
            "allowed_now": False,
            "required_checks": [
                "scheduler send requires Phase 6 separate review",
                "no scheduler integration in main send flow",
            ],
            "forbidden_actions": [
                "scheduler_triggered_send",
                "cron_based_auto_send",
                "watchdog_triggered_send",
            ],
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 6. build_manual_send_blocked_paths
# ─────────────────────────────────────────────────────────────────────────────

def build_manual_send_blocked_paths() -> List[Dict[str, Any]]:
    """List all explicitly blocked send paths.

    These paths must NEVER be allowed in any implementation phase.

    Returns:
        list of blocked path dicts with reason and severity

    No writes. No network calls.
    """
    return [
        {
            "path": "inline_webhook_url",
            "description": "Inline webhook URL in payload or config",
            "reason": "webhook_url_allowed_inline=false by policy",
            "severity": "critical",
            "blocked_phase": "all",
        },
        {
            "path": "inline_token_secret_api_key",
            "description": "Inline token, secret, or API key in payload",
            "reason": "secret_inline_allowed=false by policy",
            "severity": "critical",
            "blocked_phase": "all",
        },
        {
            "path": "send_without_confirmation",
            "description": "Send without user typing confirmation phrase",
            "reason": "user_confirmation_required=true by policy",
            "severity": "critical",
            "blocked_phase": "all",
        },
        {
            "path": "send_without_payload_validation",
            "description": "Send without passing pre-send validation",
            "reason": "require_projection_validation_valid=true by policy",
            "severity": "high",
            "blocked_phase": "all",
        },
        {
            "path": "send_with_sensitive_payload",
            "description": "Send when payload contains sensitive content",
            "reason": "require_no_sensitive_content=true by policy",
            "severity": "critical",
            "blocked_phase": "all",
        },
        {
            "path": "send_with_guard_line_count_changed",
            "description": "Send when audit JSONL line count has changed",
            "reason": "require_guard_jsonl_unchanged=true by policy",
            "severity": "high",
            "blocked_phase": "all",
        },
        {
            "path": "scheduler_auto_send",
            "description": "Scheduler-triggered automatic send without review",
            "reason": "scheduler send requires Phase 6 separate review",
            "severity": "critical",
            "blocked_phase": "all",
        },
        {
            "path": "auto_send_without_review",
            "description": "Auto-send without human in the loop",
            "reason": "manual send always requires human confirmation",
            "severity": "critical",
            "blocked_phase": "all",
        },
        {
            "path": "send_plus_auto_fix",
            "description": "Send combined with auto-fix execution",
            "reason": "auto_fix always forbidden in manual send flow",
            "severity": "critical",
            "blocked_phase": "all",
        },
        {
            "path": "runtime_write_during_send",
            "description": "Write to runtime during send operation",
            "reason": "require_no_runtime_write=true by policy",
            "severity": "high",
            "blocked_phase": "all",
        },
        {
            "path": "action_queue_write_during_send",
            "description": "Write to action queue during send operation",
            "reason": "require_no_action_queue_write=true by policy",
            "severity": "high",
            "blocked_phase": "all",
        },
        {
            "path": "raw_webhook_in_audit",
            "description": "Log raw webhook URL or response in audit record",
            "reason": "raw_webhook_never_logged=true by policy",
            "severity": "critical",
            "blocked_phase": "all",
        },
        {
            "path": "full_payload_body_in_audit",
            "description": "Log full webhook request/response body in audit",
            "reason": "send_result_metadata_only=true by policy",
            "severity": "high",
            "blocked_phase": "all",
        },
        {
            "path": "webhook_call_without_allowlist",
            "description": "Call webhook not in allowlist",
            "reason": "allowlist_required=true by policy",
            "severity": "critical",
            "blocked_phase": "all",
        },
        {
            "path": "modify_existing_audit_record",
            "description": "Modify or delete existing audit record",
            "reason": "append_only_required=true by policy",
            "severity": "critical",
            "blocked_phase": "all",
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 7. build_feishu_manual_send_policy_design
# ─────────────────────────────────────────────────────────────────────────────

def build_feishu_manual_send_policy_design(
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the complete Feishu manual send policy design.

    Aggregates:
      - webhook policy
      - confirmation policy
      - pre-send validation policy
      - send audit policy
      - allowed future send flow
      - blocked send paths
      - implementation phases

    Args:
        root: optional root path override (not used for any file writes here)

    Returns:
        dict representation of FeishuManualSendPolicyDesign

    No writes. No network calls. No secret reading.
    """
    webhook_policy = build_feishu_webhook_policy()
    confirmation_policy = build_manual_send_confirmation_policy()
    pre_send_validation_policy = build_pre_send_validation_policy()
    send_audit_policy = build_manual_send_audit_policy()
    allowed_flow = design_allowed_manual_send_flow()
    blocked_paths = build_manual_send_blocked_paths()

    implementation_phases = [
        {
            "phase": 1,
            "name": "Manual Send Policy Design",
            "description": "Define policy/validation/confirmation/audit contract (R241-13D — this phase)",
            "status": "current",
            "allowed_now": True,
            "deliverables": [
                "FeishuWebhookPolicy contract",
                "FeishuManualSendConfirmationPolicy contract",
                "FeishuPayloadPreSendValidationPolicy contract",
                "FeishuManualSendAuditPolicy contract",
                "Blocked paths list",
                "Allowed flow (12 steps)",
            ],
            "forbidden": [
                "real_feishu_send",
                "webhook_network_call",
                "audit_jsonl_write",
                "runtime_write",
                "scheduler_integration",
            ],
        },
        {
            "phase": 2,
            "name": "Pre-send Policy Validator",
            "description": "Validate payload + confirmation without sending",
            "status": "future",
            "allowed_now": False,
            "deliverables": [
                "validate_pre_send_payload()",
                "validate_confirmation_phrase()",
                "CLI --dry-run --validate-only flag",
            ],
            "forbidden": [
                "real_feishu_send",
                "webhook_network_call",
            ],
        },
        {
            "phase": 3,
            "name": "Manual Send Dry-run Command",
            "description": "CLI showing 'what would be sent' without sending",
            "status": "future",
            "allowed_now": False,
            "deliverables": [
                "audit-trend-feishu --dry-run --send preview",
                "Shows webhook target, payload hash, confirmation required",
            ],
            "forbidden": [
                "actual_webhook_call",
                "audit_jsonl_write",
            ],
        },
        {
            "phase": 4,
            "name": "Webhook Resolver Design",
            "description": "Define allowlist / secret manager reference resolution",
            "status": "future",
            "allowed_now": False,
            "deliverables": [
                "resolve_webhook_from_allowlist()",
                "resolve_secret_from_secret_manager()",
                "validate_webhook_against_policy()",
            ],
            "forbidden": [
                "reading_inline_webhook_url",
                "reading_inline_secret",
                "actual_send",
            ],
        },
        {
            "phase": 5,
            "name": "Manual Send Implementation",
            "description": "Actual Feishu send with full policy enforcement",
            "status": "future",
            "allowed_now": False,
            "deliverables": [
                "send_feishu_trend_card() with full policy checks",
                "pre_send_audit_record creation",
                "post_send_audit_record creation",
                "confirmation phrase handler",
            ],
            "forbidden": [
                "auto_fix",
                "scheduler_auto_send",
                "runtime_write",
            ],
        },
        {
            "phase": 6,
            "name": "Scheduler Send Review",
            "description": "Separate review for scheduler-triggered sends",
            "status": "future",
            "allowed_now": False,
            "deliverables": [
                "scheduler send requires explicit approval workflow",
                "separate audit trail for scheduler sends",
                "no scheduler integration in main send flow",
            ],
            "forbidden": [
                "scheduler_auto_approval",
                "scheduler_auto_send_without_review",
            ],
        },
    ]

    design = FeishuManualSendPolicyDesign(
        design_id=_new_id("feishu_manual_send_policy_design"),
        generated_at=_now(),
        status=FeishuManualSendPolicyStatus.DESIGN_ONLY.value,
        webhook_policy=webhook_policy,
        confirmation_policy=confirmation_policy,
        pre_send_validation_policy=pre_send_validation_policy,
        send_audit_policy=send_audit_policy,
        blocked_send_paths=blocked_paths,
        allowed_future_send_flow=allowed_flow,
        implementation_phases=implementation_phases,
        warnings=[
            "phase_1_is_design_only",
            "no_real_send_in_phase_1",
            "webhook_url_must_never_be_inline",
            "user_confirmation_always_required",
            "pre_and_post_audit_always_required",
        ],
        errors=[],
    )
    return asdict(design)


# ─────────────────────────────────────────────────────────────────────────────
# 8. validate_feishu_manual_send_policy_design
# ─────────────────────────────────────────────────────────────────────────────

def validate_feishu_manual_send_policy_design(
    design: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate a FeishuManualSendPolicyDesign against required constraints.

    Checks:
      - No real webhook URL in any policy field
      - No token/secret/api_key in any policy field
      - webhook_url_allowed_inline must be False
      - secret_inline_allowed must be False
      - user_confirmation_required must be True
      - pre_send_audit_required must be True
      - post_send_audit_required must be True
      - append_only_required must be True
      - raw_webhook_never_logged must be True
      - No scheduler auto-send in blocked paths
      - No auto-fix in blocked paths
      - Implementation phases must include Phase 1-6
      - blocked paths must not be empty

    Args:
        design: FeishuManualSendPolicyDesign dict

    Returns:
        dict with valid, warnings, errors

    No writes. No network calls.
    """
    validation_warnings: List[str] = []
    validation_errors: List[str] = []

    design_str = json.dumps(design, ensure_ascii=False)

    # Check: no real webhook URL
    if _WEBHOOK_RE.search(design_str):
        validation_errors.append("real_webhook_url_found_in_design")

    # Check: no sensitive KEY VALUES (not policy field names).
    # We look for actual secret values — strings matching sensitive patterns
    # that appear as JSON string VALUES (not as field name keys or reference paths).
    # Known safe reference strings (FEISHU_WEBHOOK_URL, secret_manager paths) are
    # policy metadata and do NOT constitute sensitive data leakage.
    _KNOWN_SAFE_VALUES = {
        "FEISHU_WEBHOOK_URL",
        "FEISHU_WEBHOOK_SECRET",
        "deerflow/secrets/feishu/webhook_url",
        "deerflow/secrets/feishu/webhook_secret",
        "inline_webhook_url_forbidden",
        "inline_secret_forbidden",
        "webhook_url_must_come_from_allowlist_or_secret_manager",
        "secret_must_come_from_environment_or_secret_manager",
        "webhook_url_allowed_inline",
        "secret_inline_allowed",
    }
    for policy_key in ("webhook_policy", "confirmation_policy",
                       "pre_send_validation_policy", "send_audit_policy"):
        policy_val = design.get(policy_key)
        if not policy_val:
            continue
        policy_str = json.dumps(policy_val, ensure_ascii=False)
        # Strip JSON key names (quoted strings followed by colon)
        values_only = re.sub(r'"[^"]*"\s*:', '', policy_str)
        # Remove known-safe value strings to avoid false positives on policy metadata
        for safe in _KNOWN_SAFE_VALUES:
            values_only = values_only.replace(f'"{safe}"', '""')
        if _SENSITIVE_KEY_RE.search(values_only):
            validation_errors.append("sensitive_key_found_in_design")

    # Check: webhook_url_allowed_inline = False
    webhook_policy = design.get("webhook_policy") or {}
    if webhook_policy.get("webhook_url_allowed_inline") is not False:
        validation_errors.append("webhook_url_allowed_inline_must_be_false")

    # Check: secret_inline_allowed = False
    if webhook_policy.get("secret_inline_allowed") is not False:
        validation_errors.append("secret_inline_allowed_must_be_false")

    # Check: user_confirmation_required = True
    confirmation_policy = design.get("confirmation_policy") or {}
    if confirmation_policy.get("user_confirmation_required") is not True:
        validation_errors.append("user_confirmation_required_must_be_true")

    # Check: pre_send_audit_required = True
    audit_policy = design.get("send_audit_policy") or {}
    if audit_policy.get("pre_send_audit_required") is not True:
        validation_errors.append("pre_send_audit_required_must_be_true")

    # Check: post_send_audit_required = True
    if audit_policy.get("post_send_audit_required") is not True:
        validation_errors.append("post_send_audit_required_must_be_true")

    # Check: append_only_required = True
    if audit_policy.get("append_only_required") is not True:
        validation_errors.append("append_only_required_must_be_true")

    # Check: raw_webhook_never_logged = True
    if audit_policy.get("raw_webhook_never_logged") is not True:
        validation_errors.append("raw_webhook_never_logged_must_be_true")

    # Check: blocked paths contains scheduler auto-send
    blocked_paths = design.get("blocked_send_paths") or []
    scheduler_blocked = any(
        bp.get("path") == "scheduler_auto_send" for bp in blocked_paths
    )
    if not scheduler_blocked:
        validation_errors.append("scheduler_auto_send_not_blocked")

    # Check: blocked paths contains auto-fix
    auto_fix_blocked = any(
        bp.get("path") == "send_plus_auto_fix" for bp in blocked_paths
    )
    if not auto_fix_blocked:
        validation_errors.append("auto_fix_not_blocked_in_send_flow")

    # Check: implementation phases includes Phase 1-6
    phases = design.get("implementation_phases") or []
    phase_numbers = {p.get("phase") for p in phases}
    for i in range(1, 7):
        if i not in phase_numbers:
            validation_errors.append(f"implementation_phase_{i}_missing")

    # Check: blocked paths not empty
    if not blocked_paths:
        validation_errors.append("blocked_paths_cannot_be_empty")

    valid = len(validation_errors) == 0

    return {
        "valid": valid,
        "webhook_url_allowed_inline_is_false": webhook_policy.get("webhook_url_allowed_inline") is False,
        "secret_inline_allowed_is_false": webhook_policy.get("secret_inline_allowed") is False,
        "user_confirmation_required_is_true": confirmation_policy.get("user_confirmation_required") is True,
        "pre_send_audit_required_is_true": audit_policy.get("pre_send_audit_required") is True,
        "post_send_audit_required_is_true": audit_policy.get("post_send_audit_required") is True,
        "append_only_required_is_true": audit_policy.get("append_only_required") is True,
        "raw_webhook_never_logged_is_true": audit_policy.get("raw_webhook_never_logged") is True,
        "scheduler_auto_send_blocked": scheduler_blocked,
        "auto_fix_blocked": auto_fix_blocked,
        "implementation_phases_complete": len(phase_numbers) >= 6,
        "blocked_paths_count": len(blocked_paths),
        "warnings": validation_warnings,
        "errors": validation_errors,
        "validated_at": _now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9. generate_feishu_manual_send_policy_design
# ─────────────────────────────────────────────────────────────────────────────

def generate_feishu_manual_send_policy_design(
    output_path: Optional[str] = None,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate the R241-13D policy design JSON and markdown reports.

    Writes ONLY to migration_reports/foundation_audit/.
    Does NOT write audit JSONL, runtime, or action queue.
    Does NOT call webhooks or network.
    Does NOT send Feishu messages.

    Args:
        output_path: optional override for JSON contract path
        root: optional root path override

    Returns:
        dict with design, validation, and output_path
    """
    target_json = Path(output_path) if output_path else DEFAULT_CONTRACT_PATH

    design = build_feishu_manual_send_policy_design(root=root)
    validation = validate_feishu_manual_send_policy_design(design)

    design["validation"] = validation

    target_json.parent.mkdir(parents=True, exist_ok=True)
    target_json.write_text(
        json.dumps(design, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "design": design,
        "validation": validation,
        "output_path": str(target_json),
        "generated_at": _now(),
        "warnings": design.get("warnings", []),
        "errors": design.get("errors", []),
    }


__all__ = [
    # enums
    "FeishuManualSendPolicyStatus",
    "FeishuManualSendPermission",
    "FeishuWebhookPolicyType",
    "FeishuManualSendAuditMode",
    "FeishuManualSendRiskLevel",
    # policy builders
    "build_feishu_webhook_policy",
    "build_manual_send_confirmation_policy",
    "build_pre_send_validation_policy",
    "build_manual_send_audit_policy",
    "design_allowed_manual_send_flow",
    "build_manual_send_blocked_paths",
    "build_feishu_manual_send_policy_design",
    "validate_feishu_manual_send_policy_design",
    "generate_feishu_manual_send_policy_design",
]
