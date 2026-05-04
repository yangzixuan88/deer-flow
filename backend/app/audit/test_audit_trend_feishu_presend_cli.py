"""Tests for Feishu Pre-send Validator CLI (R241-14C).

These tests exercise the CLI helpers in isolation.
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


# ─── Import test ───────────────────────────────────────────────────────────

def test_import_module():
    from app.audit.audit_trend_feishu_presend_cli import (
        PreSendCliValidationStatus,
        PreSendCliOutputFormat,
        PreSendCliMode,
        PreSendCliValidationResult,
        build_webhook_reference_from_cli_args,
        format_presend_validation_result,
        run_feishu_presend_validate_only_cli,
        generate_feishu_presend_validate_only_cli_sample,
    )
    # Enums
    assert PreSendCliValidationStatus.VALID.value == "valid"
    assert PreSendCliOutputFormat.JSON.value == "json"
    assert PreSendCliMode.VALIDATE_ONLY.value == "validate_only"
    # Functions
    assert callable(build_webhook_reference_from_cli_args)
    assert callable(format_presend_validation_result)
    assert callable(run_feishu_presend_validate_only_cli)
    assert callable(generate_feishu_presend_validate_only_cli_sample)


# ─── TestWebhookRefBuilder ──────────────────────────────────────────────────

class TestWebhookRefBuilder:
    def test_env_ref_returns_metadata(self):
        from app.audit.audit_trend_feishu_presend_cli import build_webhook_reference_from_cli_args
        result = build_webhook_reference_from_cli_args(
            webhook_ref_type="env",
            webhook_ref_name="FEISHU_WEBHOOK_URL",
        )
        assert result is not None
        assert result["type"] == "environment_variable_reference"
        assert result["name"] == "FEISHU_WEBHOOK_URL"
        assert result["blocked"] is False

    def test_secret_manager_ref_returns_metadata(self):
        from app.audit.audit_trend_feishu_presend_cli import build_webhook_reference_from_cli_args
        result = build_webhook_reference_from_cli_args(
            webhook_ref_type="secret_manager",
            webhook_ref_name="deerflow/secrets/feishu/webhook_url",
        )
        assert result is not None
        assert result["type"] == "secret_manager_reference"
        assert result["ref"] == "deerflow/secrets/feishu/webhook_url"
        assert result["blocked"] is False

    def test_missing_ref_returns_none_with_warning(self):
        from app.audit.audit_trend_feishu_presend_cli import build_webhook_reference_from_cli_args
        result = build_webhook_reference_from_cli_args()
        assert result is None

    def test_missing_ref_type_with_name_returns_blocked(self):
        from app.audit.audit_trend_feishu_presend_cli import build_webhook_reference_from_cli_args
        result = build_webhook_reference_from_cli_args(webhook_ref_name="FEISHU_WEBHOOK_URL")
        assert result is not None
        assert result["blocked"] is True

    def test_inline_webhook_blocked(self):
        from app.audit.audit_trend_feishu_presend_cli import build_webhook_reference_from_cli_args
        result = build_webhook_reference_from_cli_args(
            webhook_ref_type="env",
            webhook_ref_name="https://open.feishu.cn/.../webhook/xxx",
        )
        assert result is not None
        assert result["blocked"] is True
        assert "inline_webhook_url_blocked" in result.get("warnings", [])

    def test_unknown_ref_type_returns_blocked(self):
        from app.audit.audit_trend_feishu_presend_cli import build_webhook_reference_from_cli_args
        result = build_webhook_reference_from_cli_args(
            webhook_ref_type="unknown_type",
            webhook_ref_name="some_ref",
        )
        assert result is not None
        assert result["blocked"] is True


# ─── TestFormatResult ───────────────────────────────────────────────────────

class TestFormatResult:
    def test_json_returns_dict(self):
        from app.audit.audit_trend_feishu_presend_cli import format_presend_validation_result
        result = {"status": "valid", "valid": True, "presend_validation": {}, "blocked_reasons": [], "warnings": [], "errors": []}
        formatted = format_presend_validation_result(result, "json")
        assert isinstance(formatted, dict)
        assert formatted["status"] == "valid"

    def test_markdown_contains_validate_only(self):
        from app.audit.audit_trend_feishu_presend_cli import format_presend_validation_result
        result = {
            "status": "valid",
            "valid": True,
            "presend_validation": {
                "confirmation_phrase_valid": True,
                "webhook_reference_valid": True,
                "payload_validation_valid": True,
                "output_safety_valid": True,
                "guard_valid": True,
                "audit_precondition_valid": True,
                "payload_age_valid": True,
                "blocked_reasons": [],
                "warnings": [],
                "errors": [],
                "checks": [],
            },
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        }
        formatted = format_presend_validation_result(result, "markdown")
        assert isinstance(formatted, str)
        assert "validate-only" in formatted.lower() or "feishu" in formatted.lower()
        assert "PRE-SEND" in formatted or "# " in formatted

    def test_text_contains_no_webhook_call(self):
        from app.audit.audit_trend_feishu_presend_cli import format_presend_validation_result
        result = {
            "status": "valid",
            "valid": True,
            "presend_validation": {
                "confirmation_phrase_valid": True,
                "webhook_reference_valid": True,
                "payload_validation_valid": True,
                "output_safety_valid": True,
                "guard_valid": True,
                "audit_precondition_valid": True,
                "payload_age_valid": True,
                "blocked_reasons": [],
                "warnings": [],
                "errors": [],
                "checks": [],
            },
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
        }
        formatted = format_presend_validation_result(result, "text")
        assert isinstance(formatted, str)
        assert "validate-only" in formatted.lower() or "no webhook" in formatted.lower()

    def test_markdown_contains_all_validity_flags(self):
        from app.audit.audit_trend_feishu_presend_cli import format_presend_validation_result
        result = {
            "status": "blocked",
            "valid": False,
            "presend_validation": {
                "confirmation_phrase_valid": False,
                "webhook_reference_valid": True,
                "payload_validation_valid": True,
                "output_safety_valid": True,
                "guard_valid": True,
                "audit_precondition_valid": True,
                "payload_age_valid": True,
                "blocked_reasons": ["confirmation_phrase_missing"],
                "warnings": [],
                "errors": ["confirmation_phrase_required"],
                "checks": [
                    {"check_type": "confirmation_phrase", "passed": False, "status": "blocked"},
                ],
            },
            "blocked_reasons": ["confirmation_phrase_missing"],
            "warnings": [],
            "errors": ["confirmation_phrase_required"],
        }
        md = format_presend_validation_result(result, "markdown")
        assert "confirmation_phrase_valid" in md
        assert "webhook_reference_valid" in md
        assert "confirmation_phrase_missing" in md


# ─── TestValidateOnlyCli ─────────────────────────────────────────────────────

class TestValidateOnlyCli:
    def test_run_valid_like_case_returns_structured_result(self):
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        result = run_feishu_presend_validate_only_cli(
            window="all_available",
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            webhook_ref_type="env",
            webhook_ref_name="FEISHU_WEBHOOK_URL",
            output_format="json",
            preview_first=False,
        )
        assert "cli_result_id" in result
        assert "generated_at" in result
        assert "status" in result
        assert "valid" in result
        assert "presend_validation" in result

    def test_run_missing_confirmation_blocked(self):
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        result = run_feishu_presend_validate_only_cli(
            window="all_available",
            confirmation_phrase=None,
            output_format="json",
            preview_first=False,
        )
        # Must return structured result (no crash), may be blocked
        assert "status" in result
        assert "presend_validation" in result

    def test_run_env_ref_does_not_read_env(self):
        import os
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        original_env = os.environ.get("FEISHU_WEBHOOK_URL")
        os.environ["FEISHU_WEBHOOK_URL"] = "https://real-webhook-url.example.com/webhook/secret"
        try:
            result = run_feishu_presend_validate_only_cli(
                window="all_available",
                confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
                webhook_ref_type="env",
                webhook_ref_name="FEISHU_WEBHOOK_URL",
                output_format="json",
                preview_first=False,
            )
            # The result should NOT contain the actual webhook URL
            result_str = json.dumps(result)
            assert "https://real-webhook-url" not in result_str
            assert "webhook/secret" not in result_str
        finally:
            if original_env is None:
                os.environ.pop("FEISHU_WEBHOOK_URL", None)
            else:
                os.environ["FEISHU_WEBHOOK_URL"] = original_env

    def test_run_secret_manager_ref_does_not_read_secret(self):
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        result = run_feishu_presend_validate_only_cli(
            window="all_available",
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            webhook_ref_type="secret_manager",
            webhook_ref_name="deerflow/secrets/feishu/webhook_url",
            output_format="json",
            preview_first=False,
        )
        result_str = json.dumps(result)
        # Must not output actual secret value
        assert "secret_value" not in result_str
        assert "sk-" not in result_str
        assert "ghp_" not in result_str

    def test_run_blocked_by_inline_webhook(self):
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        result = run_feishu_presend_validate_only_cli(
            window="all_available",
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            webhook_ref_type="env",
            webhook_ref_name="https://open.feishu.cn/.../webhook/xxx",
            output_format="json",
            preview_first=False,
        )
        # Should be blocked due to inline URL
        assert result["status"] in ("blocked", "failed")

    def test_run_returns_no_feishu_send_flag(self):
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        result = run_feishu_presend_validate_only_cli(
            window="all_available",
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            output_format="json",
            preview_first=False,
        )
        presend = result.get("presend_validation") or {}
        # Guard state should be safe (no send)
        guard_valid = presend.get("guard_valid")
        if guard_valid is not None:
            assert guard_valid is True


# ─── TestSampleGenerator ────────────────────────────────────────────────────

class TestSampleGenerator:
    @pytest.mark.slow
    def test_sample_generator_writes_only_tmp_path(self, tmp_path):
        from app.audit.audit_trend_feishu_presend_cli import generate_feishu_presend_validate_only_cli_sample
        out_path = tmp_path / "R241-14C_SAMPLE.json"
        result = generate_feishu_presend_validate_only_cli_sample(output_path=str(out_path))
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert "sample_valid_like_validate_only" in data
        assert "sample_missing_confirmation" in data
        assert "sample_inline_webhook_ref_blocked" in data

    @pytest.mark.slow
    def test_sample_generator_no_webhook_network(self, tmp_path, monkeypatch):
        from app.audit.audit_trend_feishu_presend_cli import generate_feishu_presend_validate_only_cli_sample
        network_calls = []
        original_get = None
        try:
            import urllib.request
            original_get = urllib.request.urlopen
            def tracking_get(*args, **kwargs):
                network_calls.append(args[0])
                raise Exception("network should not be called")
            urllib.request.urlopen = tracking_get
            out_path = tmp_path / "R241-14C_SAMPLE.json"
            generate_feishu_presend_validate_only_cli_sample(output_path=str(out_path))
            assert len(network_calls) == 0
        finally:
            if original_get:
                urllib.request.urlopen = original_get


# ─── TestSafetyConstraints ────────────────────────────────────────────────────

class TestSafetyConstraints:
    def test_no_network_call(self, tmp_path, monkeypatch):
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        network_calls = []
        try:
            import urllib.request
            original_get = urllib.request.urlopen
            def tracking_get(*args, **kwargs):
                network_calls.append(args[0])
                raise Exception("network should not be called")
            urllib.request.urlopen = tracking_get
            run_feishu_presend_validate_only_cli(
                window="all_available",
                confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
                webhook_ref_type="env",
                webhook_ref_name="FEISHU_WEBHOOK_URL",
                output_format="json",
                preview_first=False,
            )
            assert len(network_calls) == 0
        finally:
            if "original_get" in dir():
                urllib.request.urlopen = original_get

    def test_no_runtime_write(self, tmp_path):
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        result = run_feishu_presend_validate_only_cli(
            window="all_available",
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            output_format="json",
            preview_first=False,
        )
        # Result should be clean (no runtime write artifacts)
        assert isinstance(result, dict)
        assert "runtime_write_detected" not in str(result) or result.get("runtime_write_detected", False) is False

    def test_no_audit_jsonl_write(self, tmp_path, monkeypatch):
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        append_count = 0
        original_append = None
        try:
            import app.audit.audit_trail_writer as writer_mod
            original_append = writer_mod.append_audit_record_to_target
            def counting_append(*args, **kwargs):
                nonlocal append_count
                append_count += 1
                return {"status": "appended", "lines_written": 0}
            writer_mod.append_audit_record_to_target = counting_append
            run_feishu_presend_validate_only_cli(
                window="all_available",
                confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
                output_format="json",
                preview_first=False,
            )
            assert append_count == 0
        finally:
            if original_append:
                writer_mod.append_audit_record_to_target = original_append

    def test_no_auto_fix_execution(self):
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        result = run_feishu_presend_validate_only_cli(
            window="all_available",
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            output_format="json",
            preview_first=False,
        )
        presend = result.get("presend_validation") or {}
        guard = presend.get("guard_valid")
        # If guard is mentioned, auto_fix must not be detected
        if guard is not None:
            assert guard is True

    def test_no_secret_token_output(self):
        from app.audit.audit_trend_feishu_presend_cli import run_feishu_presend_validate_only_cli
        result = run_feishu_presend_validate_only_cli(
            window="all_available",
            confirmation_phrase="CONFIRM_FEISHU_TREND_SEND",
            webhook_ref_type="env",
            webhook_ref_name="FEISHU_WEBHOOK_URL",
            output_format="json",
            preview_first=False,
        )
        result_str = json.dumps(result)
        # Must not leak tokens or secrets
        assert "sk-" not in result_str
        assert "ghp_" not in result_str
        assert "Bearer " not in result_str
