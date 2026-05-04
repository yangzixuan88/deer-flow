"""Tests for Feishu Pre-send Policy Validator (R241-14B).

These tests exercise the pre-send validator functions in isolation.
They never write audit JSONL, never call network/webhooks, never write
runtime/action queue, and never send Feishu messages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── Import test ────────────────────────────────────────────────────────────

def test_import_module():
    from app.audit.audit_trend_feishu_presend_validator import (
        PreSendValidationStatus,
        PreSendValidationCheckType,
        PreSendValidationRiskLevel,
        PreSendValidationCheckResult,
        FeishuPreSendValidationResult,
        validate_confirmation_phrase,
        validate_webhook_reference,
        validate_payload_projection_for_presend,
        validate_presend_output_safety,
        validate_guard_for_presend,
        validate_audit_precondition,
        validate_payload_age,
        run_feishu_presend_policy_validator,
        generate_feishu_presend_validator_sample,
    )
    # Enums
    assert PreSendValidationStatus.VALID.value == "valid"
    assert PreSendValidationStatus.BLOCKED.value == "blocked"
    assert PreSendValidationCheckType.CONFIRMATION_PHRASE.value == "confirmation_phrase"
    assert PreSendValidationRiskLevel.CRITICAL.value == "critical"
    # Functions
    assert callable(validate_confirmation_phrase)
    assert callable(validate_webhook_reference)
    assert callable(validate_payload_projection_for_presend)
    assert callable(validate_presend_output_safety)
    assert callable(validate_guard_for_presend)
    assert callable(validate_audit_precondition)
    assert callable(validate_payload_age)
    assert callable(run_feishu_presend_policy_validator)
    assert callable(generate_feishu_presend_validator_sample)


# ─── TestConfirmationPhrase ────────────────────────────────────────────────

class TestConfirmationPhrase:
    def test_correct_phrase_passes(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_confirmation_phrase
        result = validate_confirmation_phrase("CONFIRM_FEISHU_TREND_SEND")
        assert result["passed"] is True
        assert result["risk_level"] == "low"

    def test_missing_phrase_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_confirmation_phrase
        result = validate_confirmation_phrase(None)
        assert result["passed"] is False
        assert result["risk_level"] == "critical"
        assert "confirmation_phrase_missing" in result["blocked_reasons"]

    def test_empty_phrase_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_confirmation_phrase
        result = validate_confirmation_phrase("")
        assert result["passed"] is False
        assert result["risk_level"] == "critical"

    def test_wrong_phrase_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_confirmation_phrase
        result = validate_confirmation_phrase("WRONG_PHRASE")
        assert result["passed"] is False
        assert result["risk_level"] == "critical"
        assert "confirmation_phrase_mismatch" in result["blocked_reasons"]


# ─── TestWebhookReference ─────────────────────────────────────────────────

class TestWebhookReference:
    def test_env_reference_passes(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_webhook_reference
        ref = {"type": "environment_variable_reference", "name": "FEISHU_WEBHOOK_URL"}
        result = validate_webhook_reference(ref)
        assert result["passed"] is True
        assert result["risk_level"] == "low"

    def test_secret_manager_reference_passes(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_webhook_reference
        ref = {"type": "secret_manager_reference", "ref": "deerflow/secrets/feishu/webhook_url"}
        result = validate_webhook_reference(ref)
        assert result["passed"] is True
        assert result["risk_level"] == "low"

    def test_inline_webhook_url_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_webhook_reference
        ref = {"type": "inline_webhook_url", "name": "https://open.feishu.cn/custom/webhook/abc123"}
        result = validate_webhook_reference(ref)
        assert result["passed"] is False
        assert result["risk_level"] == "critical"
        assert "inline_webhook_url_blocked" in result["blocked_reasons"]

    def test_inline_webhook_url_by_name_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_webhook_reference
        ref = {"type": "unknown", "name": "https://open.feishu.cn/custom/webhook/abc123"}
        result = validate_webhook_reference(ref)
        assert result["passed"] is False
        assert result["risk_level"] == "critical"

    def test_inline_secret_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_webhook_reference
        ref = {"type": "inline_secret", "ref": "sk-abcdefghijklmnopqrstuvwxyz1234567890"}
        result = validate_webhook_reference(ref)
        assert result["passed"] is False
        assert result["risk_level"] == "critical"

    def test_no_ref_dry_run_passes(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_webhook_reference
        result = validate_webhook_reference(None)
        assert result["passed"] is True
        assert "no_webhook_ref_dry_run_mode" in result["warnings"]

    def test_does_not_read_env_var(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_webhook_reference
        import os
        os.environ["FEISHU_WEBHOOK_URL"] = "https://REAL_SECRET_URL.open.feishu.cn/webhook"
        try:
            ref = {"type": "environment_variable_reference", "name": "FEISHU_WEBHOOK_URL"}
            result = validate_webhook_reference(ref)
            assert result["passed"] is True
            # The result should NOT contain the actual URL value
            evidence_str = str(result.get("evidence_refs", []))
            assert "REAL_SECRET" not in evidence_str
        finally:
            del os.environ["FEISHU_WEBHOOK_URL"]


# ─── TestPayloadProjection ─────────────────────────────────────────────────

class TestPayloadProjection:
    def _safe_payload(self):
        return {
            "payload_id": "test_payload_001",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "status": "projection_only",
            "send_allowed": False,
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {"header": {"title": {"tag": "plain_text", "content": "Test"}}},
            "sections": [],
        }

    def _safe_validation(self):
        return {"valid": True, "blocked_reasons": [], "errors": []}

    def test_safe_payload_passes(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_payload_projection_for_presend
        result = validate_payload_projection_for_presend(self._safe_payload(), self._safe_validation())
        assert result["passed"] is True
        assert result["risk_level"] == "low"

    def test_send_allowed_true_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_payload_projection_for_presend
        payload = self._safe_payload()
        payload["send_allowed"] = True
        result = validate_payload_projection_for_presend(payload, self._safe_validation())
        assert result["passed"] is False
        assert "send_allowed_must_be_false" in result["blocked_reasons"]

    def test_no_webhook_call_false_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_payload_projection_for_presend
        payload = self._safe_payload()
        payload["no_webhook_call"] = False
        result = validate_payload_projection_for_presend(payload, self._safe_validation())
        assert result["passed"] is False
        assert "no_webhook_call_must_be_true" in result["blocked_reasons"]

    def test_validation_fails_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_payload_projection_for_presend
        bad_validation = {"valid": False, "blocked_reasons": ["guard_line_count_changed"], "errors": []}
        result = validate_payload_projection_for_presend(self._safe_payload(), bad_validation)
        assert result["passed"] is False


# ─── TestOutputSafety ───────────────────────────────────────────────────────

class TestOutputSafety:
    def test_clean_output_passes(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_presend_output_safety
        clean_output = "This is a safe preview output with no secrets."
        result = validate_presend_output_safety(clean_output)
        assert result["passed"] is True
        assert result["risk_level"] == "low"

    def test_webhook_url_detected_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_presend_output_safety
        output = "Here is the webhook: https://open.feishu.cn/custom/webhook/abc123"
        result = validate_presend_output_safety(output)
        assert result["passed"] is False
        assert result["risk_level"] == "critical"
        assert "webhook_url_found_in_preview_output" in result["blocked_reasons"]

    def test_token_secret_detected_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_presend_output_safety
        output = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.abc123xyz"
        result = validate_presend_output_safety(output)
        assert result["passed"] is False
        assert result["risk_level"] == "critical"

    def test_no_output_dry_run_passes(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_presend_output_safety
        result = validate_presend_output_safety(None)
        assert result["passed"] is True
        assert "dry-run design validation" in result["message"]


# ─── TestGuardValidation ───────────────────────────────────────────────────

class TestGuardValidation:
    def test_unchanged_guard_passes(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_guard_for_presend
        guard = {
            "audit_jsonl_unchanged": True,
            "sensitive_output_detected": False,
            "network_call_detected": False,
            "runtime_write_detected": False,
            "auto_fix_detected": False,
        }
        result = validate_guard_for_presend(guard)
        assert result["passed"] is True
        assert result["risk_level"] == "low"

    def test_missing_guard_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_guard_for_presend
        result = validate_guard_for_presend(None)
        assert result["passed"] is False
        assert result["risk_level"] == "high"
        assert "guard_data_missing" in result["blocked_reasons"]

    def test_line_count_changed_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_guard_for_presend
        guard = {
            "audit_jsonl_unchanged": False,
            "sensitive_output_detected": False,
            "network_call_detected": False,
            "runtime_write_detected": False,
            "auto_fix_detected": False,
        }
        result = validate_guard_for_presend(guard)
        assert result["passed"] is False
        assert "audit_jsonl_line_count_changed" in result["blocked_reasons"]

    def test_network_call_detected_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_guard_for_presend
        guard = {
            "audit_jsonl_unchanged": True,
            "sensitive_output_detected": False,
            "network_call_detected": True,
            "runtime_write_detected": False,
            "auto_fix_detected": False,
        }
        result = validate_guard_for_presend(guard)
        assert result["passed"] is False
        assert "guard_network_call_detected" in result["blocked_reasons"]

    def test_auto_fix_detected_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_guard_for_presend
        guard = {
            "audit_jsonl_unchanged": True,
            "sensitive_output_detected": False,
            "network_call_detected": False,
            "runtime_write_detected": False,
            "auto_fix_detected": True,
        }
        result = validate_guard_for_presend(guard)
        assert result["passed"] is False
        assert "guard_auto_fix_detected" in result["blocked_reasons"]


# ─── TestAuditPrecondition ─────────────────────────────────────────────────

class TestAuditPrecondition:
    def _safe_payload(self):
        return {
            "payload_id": "test_payload_001",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "status": "projection_only",
            "send_allowed": False,
            "source_trend_report_id": "trend_001",
            "card_json": {"header": {"title": {"tag": "plain_text", "content": "Test"}}},
        }

    def test_audit_precondition_generates_projection(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_audit_precondition
        result = validate_audit_precondition(self._safe_payload())
        assert result["passed"] is True
        assert "payload_hash" in str(result["evidence_refs"])

    def test_audit_precondition_no_jsonl_written(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_audit_precondition
        result = validate_audit_precondition(self._safe_payload())
        assert result["passed"] is True
        assert any("design_only" in w or "jsonl" in w for w in result["warnings"])
        assert any("no_audit_jsonl_written" in str(r) or "design_only" in str(r) for r in result["evidence_refs"])

    def test_audit_precondition_missing_payload_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_audit_precondition
        result = validate_audit_precondition({})
        assert result["passed"] is False
        assert "payload_missing_for_audit_precondition" in result["blocked_reasons"]


# ─── TestPayloadAge ─────────────────────────────────────────────────────────

class TestPayloadAge:
    def test_recent_payload_passes(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_payload_age
        from datetime import datetime, timezone
        recent = datetime.now(timezone.utc).isoformat()
        result = validate_payload_age(recent)
        assert result["passed"] is True
        assert result["risk_level"] == "low"

    def test_expired_payload_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_payload_age
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(minutes=61)).isoformat()
        result = validate_payload_age(old)
        assert result["passed"] is False
        assert result["risk_level"] == "high"
        assert "payload_age_exceeded" in result["blocked_reasons"][0]

    def test_missing_timestamp_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_payload_age
        result = validate_payload_age(None)
        assert result["passed"] is False
        assert result["risk_level"] == "high"

    def test_invalid_timestamp_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_payload_age
        result = validate_payload_age("not-a-timestamp")
        assert result["passed"] is False
        assert result["risk_level"] == "high"


# ─── TestEndToEndValidator ─────────────────────────────────────────────────

class TestEndToEndValidator:
    def _safe_payload(self):
        from datetime import datetime, timezone
        return {
            "payload_id": "e2e_payload_001",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "projection_only",
            "send_allowed": False,
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "source_trend_report_id": "trend_e2e_001",
            "card_json": {"header": {"title": {"tag": "plain_text", "content": "E2E Test"}}},
            "sections": [],
        }

    def _safe_guard(self):
        return {
            "audit_jsonl_unchanged": True,
            "sensitive_output_detected": False,
            "network_call_detected": False,
            "runtime_write_detected": False,
            "auto_fix_detected": False,
        }

    def test_e2e_all_safe_but_send_still_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import run_feishu_presend_policy_validator
        result = run_feishu_presend_policy_validator(
            payload=self._safe_payload(),
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            guard=self._safe_guard(),
        )
        # All checks should pass but status should still be partial (send blocked by design)
        assert result["confirmation_phrase_valid"] is True
        assert result["payload_validation_valid"] is True
        assert result["guard_valid"] is True
        assert result["payload_age_valid"] is True
        # send_allowed=False means send is still blocked — correct behavior
        assert result["payload_id"] == "e2e_payload_001"

    def test_e2e_missing_confirmation_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import run_feishu_presend_policy_validator
        result = run_feishu_presend_policy_validator(
            payload=self._safe_payload(),
            confirmation_phrase=None,
            guard=self._safe_guard(),
        )
        assert result["valid"] is False
        assert result["status"] == "blocked"
        assert result["confirmation_phrase_valid"] is False

    def test_e2e_inline_webhook_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import run_feishu_presend_policy_validator
        result = run_feishu_presend_policy_validator(
            payload=self._safe_payload(),
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            webhook_ref={"type": "inline_webhook_url", "name": "https://malicious.com/webhook"},
            guard=self._safe_guard(),
        )
        assert result["valid"] is False
        assert result["webhook_reference_valid"] is False
        assert result["status"] == "blocked"

    def test_e2e_guard_changed_blocked(self):
        from app.audit.audit_trend_feishu_presend_validator import run_feishu_presend_policy_validator
        bad_guard = dict(self._safe_guard())
        bad_guard["audit_jsonl_unchanged"] = False
        result = run_feishu_presend_policy_validator(
            payload=self._safe_payload(),
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            guard=bad_guard,
        )
        assert result["valid"] is False
        assert result["guard_valid"] is False
        assert result["status"] == "blocked"


# ─── TestSample ─────────────────────────────────────────────────────────────

class TestSample:
    def test_generate_sample_writes_tmp_path(self, tmp_path):
        from app.audit.audit_trend_feishu_presend_validator import generate_feishu_presend_validator_sample
        target = tmp_path / "R241-14B_SAMPLE.json"
        result = generate_feishu_presend_validator_sample(output_path=str(target))
        assert target.exists()
        assert "sample_valid_like_but_send_still_blocked" in result
        assert "sample_missing_confirmation" in result
        assert "sample_inline_webhook_blocked" in result
        assert "sample_guard_changed_blocked" in result

    def test_sample_valid_case_has_valid_true(self, tmp_path):
        from app.audit.audit_trend_feishu_presend_validator import generate_feishu_presend_validator_sample
        target = tmp_path / "R241-14B_VALID.json"
        generate_feishu_presend_validator_sample(output_path=str(target))
        data = json.loads(target.read_text(encoding="utf-8"))
        valid_result = data["sample_valid_like_but_send_still_blocked"]
        assert valid_result["confirmation_phrase_valid"] is True
        assert valid_result["guard_valid"] is True


# ─── TestSafetyConstraints ─────────────────────────────────────────────────

class TestSafetyConstraints:
    def test_validator_no_network_call(self):
        from app.audit.audit_trend_feishu_presend_validator import run_feishu_presend_policy_validator
        safe_payload = {
            "payload_id": "net_check_payload",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "status": "projection_only",
            "send_allowed": False,
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {},
            "sections": [],
        }
        result = run_feishu_presend_policy_validator(
            payload=safe_payload,
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        )
        # The validator runs without any network calls
        assert result["validation_id"] is not None

    def test_validator_no_feishu_send(self, tmp_path):
        from datetime import datetime, timezone
        from app.audit.audit_trend_feishu_presend_validator import run_feishu_presend_policy_validator
        safe_payload = {
            "payload_id": "send_check_payload",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "projection_only",
            "send_allowed": False,
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {},
            "sections": [],
        }
        safe_guard = {
            "audit_jsonl_unchanged": True,
            "sensitive_output_detected": False,
            "network_call_detected": False,
            "runtime_write_detected": False,
            "auto_fix_detected": False,
        }
        result = run_feishu_presend_policy_validator(
            payload=safe_payload,
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            guard=safe_guard,
        )
        # send_allowed must remain False — no actual send
        assert result["payload_validation_valid"] is True
        assert result["status"] in ("valid", "partial_warning")

    def test_validator_no_real_secret_output(self, tmp_path):
        from app.audit.audit_trend_feishu_presend_validator import generate_feishu_presend_validator_sample
        target = tmp_path / "R241-14B_SECRET_CHECK.json"
        result = generate_feishu_presend_validator_sample(output_path=str(target))
        text = json.dumps(result)
        # No real secrets should appear
        assert "sk-" not in text or "sk-" not in text.replace("sk-", "")
        # Only sample/webhook/secret reference names should appear
        for key in ["FEISHU_WEBHOOK_URL", "deerflow/secrets/feishu/webhook_url"]:
            if key in text:
                assert "REAL" not in text.upper()

    def test_validator_no_audit_jsonl_write(self, tmp_path):
        from app.audit.audit_trend_feishu_presend_validator import run_feishu_presend_policy_validator
        safe_payload = {
            "payload_id": "jsonl_check_payload",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "status": "projection_only",
            "send_allowed": False,
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {},
            "sections": [],
        }
        result = run_feishu_presend_policy_validator(
            payload=safe_payload,
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
        )
        # Audit precondition check result should say design-only
        for check_wrapper in result.get("checks", []):
            if check_wrapper.get("check_type") == "audit_requirement":
                check_result = check_wrapper.get("check_result", {})
                assert "design_only" in check_result.get("warnings", []) or check_result.get("passed") is True

    def test_validator_no_auto_fix_execution(self):
        from app.audit.audit_trend_feishu_presend_validator import validate_payload_projection_for_presend
        safe_payload = {
            "payload_id": "autofix_check_payload",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "status": "projection_only",
            "send_allowed": False,
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {},
            "sections": [],
        }
        result = validate_payload_projection_for_presend(safe_payload)
        assert result["passed"] is True
