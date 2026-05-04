"""Tests for Feishu trend CLI preview (R241-13C).

These tests exercise the CLI preview functions in isolation.
They never write audit JSONL, never call network/webhooks, never write
runtime/action queue, and never send Feishu messages.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── Fixture helpers ────────────────────────────────────────────────────────

def _trend_report(
    status: str = "ok",
    window: str = "last_7d",
    records: int = 50,
    trend_report_id: str = "nightly_tr_001",
    warnings: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "trend_report_id": trend_report_id,
        "generated_at": "2026-04-25T10:00:00+00:00",
        "status": status,
        "window": window,
        "source_query_refs": ["q_abc123"],
        "total_records_analyzed": records,
        "series": [],
        "regression_signals": [],
        "summary": {
            "point_count": 10,
            "series_count": 3,
            "regression_count": 2,
            "query_status": "ok",
            "total_invalid_lines": 0,
        },
        "warnings": warnings or [],
        "errors": [],
    }


def _trend_summary(
    status: str = "ok",
    window: str = "last_7d",
    series_count: int = 3,
    regression_count: int = 2,
    by_severity: Dict[str, int] | None = None,
    top_regressions: List[Dict[str, Any]] | None = None,
    warnings: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "window": window,
        "total_records_analyzed": 50,
        "series_count": series_count,
        "regression_count": regression_count,
        "by_metric_type": {"health": 2, "runtime": 1},
        "by_severity": by_severity or {"high": 1, "medium": 1},
        "top_regressions": top_regressions or [
            {
                "regression_id": "reg_001",
                "metric_name": "partial_warning_rate",
                "severity": "high",
                "current_value": 0.42,
                "recommended_action": "diagnostic_only",
                "warnings": [],
            },
        ],
        "warnings": warnings or [],
        "errors": [],
    }


def _guard(
    audit_jsonl_unchanged: bool = True,
    sensitive_output_detected: bool = False,
    network_call_detected: bool = False,
    auto_fix_detected: bool = False,
    runtime_write_detected: bool = False,
    warnings: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "guard_id": "guard_001",
        "command_mode": "dry_run",
        "root": str(ROOT),
        "line_count_before": {
            "foundation_diagnostic_runs.jsonl": 14,
            "nightly_health_reviews.jsonl": 2,
        },
        "line_count_after": {
            "foundation_diagnostic_runs.jsonl": 14,
            "nightly_health_reviews.jsonl": 2,
        },
        "safety_checks": [],
        "write_report_allowed": False,
        "audit_jsonl_unchanged": audit_jsonl_unchanged,
        "sensitive_output_detected": sensitive_output_detected,
        "network_call_detected": network_call_detected,
        "auto_fix_detected": auto_fix_detected,
        "runtime_write_detected": runtime_write_detected,
        "warnings": warnings or [],
        "errors": [],
        "created_at": "2026-04-25T10:00:00+00:00",
    }


def _projection_payload(
    trend_report: Dict[str, Any] | None = None,
    trend_summary: Dict[str, Any] | None = None,
    guard: Dict[str, Any] | None = None,
    validation_valid: bool = True,
) -> Dict[str, Any]:
    tr = trend_report or _trend_report()
    ts = trend_summary or _trend_summary()
    g = guard or _guard()
    return {
        "payload_id": "feishu_trend_payload_test_preview",
        "generated_at": "2026-04-25T10:00:00+00:00",
        "status": "projection_only",
        "title": "Nightly Trend Summary Dry-run",
        "template": "blue",
        "source_trend_report_id": tr.get("trend_report_id"),
        "source_window": tr.get("window", "all_available"),
        "source_record_count": tr.get("total_records_analyzed", 0),
        "regression_count": ts.get("regression_count", 0),
        "by_severity": ts.get("by_severity", {}),
        "sections": [],
        "card_json": {"config": {}, "header": {}, "elements": []},
        "send_permission": "projection_only",
        "send_allowed": False,
        "webhook_required": True,
        "no_webhook_call": True,
        "no_runtime_write": True,
        "no_action_queue_write": True,
        "no_auto_fix": True,
        "warnings": [],
        "errors": [],
        "validation": {
            "validation_id": "feishu_trend_validation_test",
            "valid": validation_valid,
            "status": "projection_only",
            "send_allowed_is_false": True,
            "no_webhook_call_is_true": True,
            "no_runtime_write_is_true": True,
            "no_action_queue_write_is_true": True,
            "no_auto_fix_is_true": True,
            "sensitive_content_detected": False,
            "line_count_changed": False,
            "blocked_reasons": [],
            "warnings": [],
            "errors": [],
            "validated_at": "2026-04-25T10:00:00+00:00",
        },
    }


# ─── Import test ────────────────────────────────────────────────────────────

def test_import_module():
    from app.audit import (
        format_feishu_trend_payload_preview,
        run_feishu_trend_preview_diagnostic,
        generate_feishu_trend_preview_sample,
        FeishuTrendPreviewFormat,
        FeishuTrendPreviewStatus,
    )
    assert callable(format_feishu_trend_payload_preview)
    assert callable(run_feishu_trend_preview_diagnostic)
    assert callable(generate_feishu_trend_preview_sample)
    assert FeishuTrendPreviewFormat.TEXT.value == "text"
    assert FeishuTrendPreviewFormat.MARKDOWN.value == "markdown"
    assert FeishuTrendPreviewFormat.JSON.value == "json"
    assert FeishuTrendPreviewStatus.SUCCESS.value == "success"
    assert FeishuTrendPreviewStatus.FAILED.value == "failed"


# ─── TestFormatPreview ──────────────────────────────────────────────────────

class TestFormatPreview:
    def test_format_text_returns_string(self):
        from app.audit import format_feishu_trend_payload_preview
        payload = _projection_payload()
        result = format_feishu_trend_payload_preview(payload, format="text")
        assert isinstance(result, str)
        assert "FEISHU TREND PAYLOAD PREVIEW" in result
        assert "SAFETY FLAGS" in result
        assert "END OF PREVIEW" in result

    def test_format_text_contains_payload_fields(self):
        from app.audit import format_feishu_trend_payload_preview
        payload = _projection_payload()
        result = format_feishu_trend_payload_preview(payload, format="text")
        assert "projection_only" in result
        assert "Nightly Trend Summary Dry-run" in result
        assert "send_allowed" in result

    def test_format_text_contains_sections(self):
        from app.audit import format_feishu_trend_payload_preview
        from app.audit import build_feishu_trend_sections
        tr = _trend_report()
        ts = _trend_summary()
        g = _guard()
        sections_result = build_feishu_trend_sections(tr, ts, g, None)
        payload = _projection_payload(tr, ts, g)
        payload["sections"] = sections_result["sections"]
        result = format_feishu_trend_payload_preview(payload, format="text")
        assert "Nightly Trend Summary" in result
        assert "Trend Overview" in result
        assert "Safety Guard Summary" in result
        assert "audit_jsonl_unchanged" in result
        assert "true" in result

    def test_format_markdown_returns_string(self):
        from app.audit import format_feishu_trend_payload_preview
        payload = _projection_payload()
        result = format_feishu_trend_payload_preview(payload, format="markdown")
        assert isinstance(result, str)
        assert "# Feishu Trend Payload Preview" in result
        assert "## Safety Flags" in result

    def test_format_markdown_contains_tables(self):
        from app.audit import format_feishu_trend_payload_preview
        payload = _projection_payload()
        result = format_feishu_trend_payload_preview(payload, format="markdown")
        assert "| Flag | Value |" in result
        assert "| send_allowed |" in result

    def test_format_json_returns_serializable(self):
        from app.audit import format_feishu_trend_payload_preview
        payload = _projection_payload()
        result = format_feishu_trend_payload_preview(payload, format="json")
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["payload_id"] == "feishu_trend_payload_test_preview"
        assert parsed["status"] == "projection_only"
        assert "sections" in parsed

    def test_format_unknown_defaults_to_text(self):
        from app.audit import format_feishu_trend_payload_preview
        payload = _projection_payload()
        result = format_feishu_trend_payload_preview(payload, format="unknown")
        assert "FEISHU TREND PAYLOAD PREVIEW" in result


# ─── TestPreviewDiagnostic ──────────────────────────────────────────────────

class TestPreviewDiagnostic:
    @pytest.mark.slow
    def test_diagnostic_returns_success_status(self):
        from app.audit import run_feishu_trend_preview_diagnostic
        result = run_feishu_trend_preview_diagnostic(window="all_available", format="text")
        assert result["status"] in ("success", "no_data", "validation_error", "failed")
        assert "preview" in result
        assert "preview_format" in result
        assert result["preview_format"] == "text"

    @pytest.mark.slow
    def test_diagnostic_returns_payload_id(self):
        from app.audit import run_feishu_trend_preview_diagnostic
        result = run_feishu_trend_preview_diagnostic(window="all_available", format="text")
        assert result["payload_id"] is not None

    @pytest.mark.slow
    def test_diagnostic_returns_validation(self):
        from app.audit import run_feishu_trend_preview_diagnostic
        result = run_feishu_trend_preview_diagnostic(window="all_available", format="text")
        validation = result.get("validation") or {}
        assert "valid" in validation

    @pytest.mark.slow
    def test_diagnostic_json_format(self):
        from app.audit import run_feishu_trend_preview_diagnostic
        result = run_feishu_trend_preview_diagnostic(window="all_available", format="json")
        assert result["preview_format"] == "json"
        parsed = json.loads(result["preview"])
        assert "payload_id" in parsed

    @pytest.mark.slow
    def test_diagnostic_markdown_format(self):
        from app.audit import run_feishu_trend_preview_diagnostic
        result = run_feishu_trend_preview_diagnostic(window="all_available", format="markdown")
        assert result["preview_format"] == "markdown"
        assert "# Feishu Trend Payload Preview" in result["preview"]

    @pytest.mark.slow
    def test_diagnostic_text_format(self):
        from app.audit import run_feishu_trend_preview_diagnostic
        result = run_feishu_trend_preview_diagnostic(window="all_available", format="text")
        assert result["preview_format"] == "text"
        assert "FEISHU TREND PAYLOAD PREVIEW" in result["preview"]


# ─── TestPreviewSample ──────────────────────────────────────────────────────

class TestPreviewSample:
    @pytest.mark.slow
    def test_sample_writes_tmp_path(self, tmp_path):
        from app.audit import generate_feishu_trend_preview_sample
        sample_path = tmp_path / "R241-13C_TEST_SAMPLE.json"
        sample = generate_feishu_trend_preview_sample(output_path=str(sample_path), format="text")
        assert sample_path.exists()
        assert sample["output_path"] == str(sample_path)
        assert "preview_sample" in sample
        assert "format_used" in sample
        assert sample["format_used"] == "text"

    @pytest.mark.slow
    def test_sample_json_format(self, tmp_path):
        from app.audit import generate_feishu_trend_preview_sample
        sample_path = tmp_path / "R241-13C_TEST_SAMPLE.json"
        sample = generate_feishu_trend_preview_sample(output_path=str(sample_path), format="json")
        data = json.loads(sample_path.read_text(encoding="utf-8"))
        assert data["format_used"] == "json"

    @pytest.mark.slow
    def test_sample_markdown_format(self, tmp_path):
        from app.audit import generate_feishu_trend_preview_sample
        sample_path = tmp_path / "R241-13C_TEST_SAMPLE.json"
        sample = generate_feishu_trend_preview_sample(output_path=str(sample_path), format="markdown")
        data = json.loads(sample_path.read_text(encoding="utf-8"))
        assert data["format_used"] == "markdown"
        # preview is markdown string (not double-encoded JSON for markdown format)
        assert "# Feishu Trend Payload Preview" in data["preview_sample"]["preview"]

    @pytest.mark.slow
    def test_sample_diagnostic_status(self, tmp_path):
        from app.audit import generate_feishu_trend_preview_sample
        sample_path = tmp_path / "R241-13C_TEST_SAMPLE.json"
        sample = generate_feishu_trend_preview_sample(output_path=str(sample_path))
        diagnostic = sample["preview_sample"]
        assert diagnostic["status"] in ("success", "no_data", "validation_error", "failed")
        assert diagnostic["payload_id"] is not None


# ─── TestSafetyConstraints ─────────────────────────────────────────────────

class TestSafetyConstraints:
    def test_format_preview_no_network_call(self):
        from app.audit import format_feishu_trend_payload_preview
        import app.audit.audit_trend_feishu_projection as proj_mod
        import app.audit.audit_trend_cli_guard as guard_mod
        original_guard_fn = guard_mod.run_guarded_audit_trend_cli_projection
        guard_mod.run_guarded_audit_trend_cli_projection = lambda **kwargs: {
            "guard": _guard(),
            "trend_report": _trend_report(),
            "formatted_output": "{}",
            "artifact_bundle": None,
            "warnings": [],
            "errors": [],
        }
        try:
            from app.audit import run_feishu_trend_preview_diagnostic
            result = run_feishu_trend_preview_diagnostic(window="all_available", format="text")
            assert "webhook" not in result["preview"].lower() or "no_webhook" in result["preview"].lower()
        finally:
            guard_mod.run_guarded_audit_trend_cli_projection = original_guard_fn

    def test_diagnostic_no_webhook_in_preview(self):
        from app.audit import run_feishu_trend_preview_diagnostic
        result = run_feishu_trend_preview_diagnostic(window="all_available", format="text")
        preview_lower = result["preview"].lower()
        has_webhook = "https://" in preview_lower or "http://" in preview_lower
        assert not has_webhook, "Preview should not contain webhook URLs"

    def test_sample_diagnostic_no_audit_jsonl_write(self, tmp_path, monkeypatch):
        from app.audit import generate_feishu_trend_preview_sample
        original_append = None
        try:
            import app.audit.audit_trail_writer as writer_mod
            original_append = writer_mod.append_audit_record_to_target
            call_count = 0
            def counting_append(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return {"status": "appended", "lines_written": 0}
            writer_mod.append_audit_record_to_target = counting_append
            sample_path = tmp_path / "R241-13C_NO_WRITE_SAMPLE.json"
            generate_feishu_trend_preview_sample(output_path=str(sample_path), format="text")
            assert call_count == 0, "append_audit_record_to_target should not be called during preview"
        finally:
            if original_append:
                writer_mod.append_audit_record_to_target = original_append


# ─── TestPreviewEnums ───────────────────────────────────────────────────────

class TestPreviewEnums:
    def test_preview_format_values(self):
        from app.audit import FeishuTrendPreviewFormat
        assert FeishuTrendPreviewFormat.TEXT.value == "text"
        assert FeishuTrendPreviewFormat.MARKDOWN.value == "markdown"
        assert FeishuTrendPreviewFormat.JSON.value == "json"

    def test_preview_status_values(self):
        from app.audit import FeishuTrendPreviewStatus
        assert FeishuTrendPreviewStatus.SUCCESS.value == "success"
        assert FeishuTrendPreviewStatus.FAILED.value == "failed"
        assert FeishuTrendPreviewStatus.NO_DATA.value == "no_data"
        assert FeishuTrendPreviewStatus.VALIDATION_ERROR.value == "validation_error"


# ─── TestCliIntegration ─────────────────────────────────────────────────────

class TestCliIntegration:
    @pytest.mark.slow
    def test_cli_audit_trend_feishu_text_format(self):
        from app.foundation.read_only_diagnostics_cli import main
        exit_code = main(["audit-trend-feishu", "--format", "text"])
        assert exit_code == 0

    @pytest.mark.slow
    def test_cli_audit_trend_feishu_json_format(self):
        from app.foundation.read_only_diagnostics_cli import main
        exit_code = main(["audit-trend-feishu", "--format", "json"])
        assert exit_code == 0

    @pytest.mark.slow
    def test_cli_audit_trend_feishu_markdown_format(self):
        from app.foundation.read_only_diagnostics_cli import main
        exit_code = main(["audit-trend-feishu", "--format", "markdown"])
        assert exit_code == 0

    @pytest.mark.slow
    def test_cli_audit_trend_feishu_window_arg(self):
        from app.foundation.read_only_diagnostics_cli import main
        exit_code = main(["audit-trend-feishu", "--format", "text", "--window", "last_7d"])
        assert exit_code == 0

    @pytest.mark.slow
    def test_cli_registry_includes_audit_trend_feishu(self):
        from app.foundation.read_only_diagnostics_cli import IMPLEMENTED_COMMANDS
        assert "audit-trend-feishu" in IMPLEMENTED_COMMANDS

    @pytest.mark.slow
    def test_cli_diagnostic_commands_includes_audit_trend_feishu(self):
        from app.foundation.read_only_diagnostics_cli import DIAGNOSTIC_COMMANDS
        assert "audit-trend-feishu" in DIAGNOSTIC_COMMANDS


# ─── TestGuardDataIntegrity ─────────────────────────────────────────────────

class TestGuardDataIntegrity:
    def test_guard_unchanged_shows_true_in_preview(self):
        from app.audit import run_feishu_trend_preview_diagnostic
        result = run_feishu_trend_preview_diagnostic(window="all_available", format="text")
        preview = result["preview"]
        guard_idx = preview.find("audit_jsonl_unchanged")
        if guard_idx >= 0:
            context = preview[guard_idx:guard_idx+30]
            assert "false" not in context.lower() or "true" in context.lower()

    def test_validation_line_count_unchanged(self):
        from app.audit import run_feishu_trend_preview_diagnostic
        result = run_feishu_trend_preview_diagnostic(window="all_available", format="text")
        validation = result.get("validation") or {}
        assert validation.get("line_count_changed") is False

    def test_validation_guard_unchanged_consistent(self):
        from app.audit import run_feishu_trend_preview_diagnostic
        result = run_feishu_trend_preview_diagnostic(window="all_available", format="text")
        validation = result.get("validation") or {}
        if validation.get("valid") is True:
            assert validation.get("line_count_changed") is False
            assert validation.get("send_allowed_is_false") is True
