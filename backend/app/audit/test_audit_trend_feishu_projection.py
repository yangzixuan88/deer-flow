"""Tests for Feishu trend payload projection (R241-13B).

These tests use only fixture data and tmp paths. They never write audit JSONL,
never call network/webhooks, never write runtime/action queue, and never
execute auto-fix.
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
            {
                "regression_id": "reg_002",
                "metric_name": "queue_missing_warning_count",
                "severity": "medium",
                "current_value": 3.0,
                "recommended_action": "diagnostic_only",
                "warnings": ["insufficient_data_for_persistence_window"],
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


def _artifact_bundle() -> Dict[str, Any]:
    return {
        "artifacts": [
            {
                "artifact_id": "art_001",
                "artifact_type": "nightly_trend_report",
                "output_path": "migration_reports/foundation_audit/R241-12B_DRYRUN_TREND_PROJECTION_SAMPLE.json",
                "generated_at": "2026-04-25T10:00:00+00:00",
            },
            {
                "artifact_id": "art_002",
                "artifact_type": "nightly_trend_markdown",
                "output_path": "migration_reports/foundation_audit/R241-12B_DRYRUN_TREND_PROJECTION_REPORT.md",
                "generated_at": "2026-04-25T10:00:00+00:00",
            },
        ],
        "warnings": [],
        "errors": [],
    }


# ─── Import test ────────────────────────────────────────────────────────────

def test_import_module():
    from app.audit import (
        build_feishu_trend_sections,
        build_feishu_trend_card_json,
        build_feishu_trend_payload_projection,
        validate_feishu_trend_payload_projection,
        generate_feishu_trend_payload_projection,
        generate_feishu_trend_payload_projection_sample,
    )
    assert callable(build_feishu_trend_sections)
    assert callable(build_feishu_trend_card_json)
    assert callable(build_feishu_trend_payload_projection)
    assert callable(validate_feishu_trend_payload_projection)
    assert callable(generate_feishu_trend_payload_projection)
    assert callable(generate_feishu_trend_payload_projection_sample)


# ─── build_feishu_trend_sections tests ─────────────────────────────────────

class TestBuildSections:
    def test_sections_returns_8_sections(self):
        from app.audit import build_feishu_trend_sections
        result = build_feishu_trend_sections(_trend_report(), _trend_summary())
        sections = result["sections"]
        assert result["section_count"] == 8
        assert len(sections) == 8

    def test_required_sections_present(self):
        from app.audit import build_feishu_trend_sections
        result = build_feishu_trend_sections(_trend_report(), _trend_summary())
        section_types = {s["section_type"] for s in result["sections"]}
        required = {"headline", "trend_overview", "regression_summary", "guard_summary", "safety_notice"}
        assert required.issubset(section_types)

    def test_regression_summary_max_5(self):
        from app.audit import build_feishu_trend_sections
        many_regressions = _trend_summary(
            top_regressions=[
                {"regression_id": f"reg_{i}", "metric_name": f"metric_{i}", "severity": "medium", "current_value": float(i), "recommended_action": "diagnostic_only"}
                for i in range(10)
            ]
        )
        result = build_feishu_trend_sections(_trend_report(), many_regressions)
        regression_sections = [s for s in result["sections"] if s["section_type"] == "regression_summary"]
        total_items = sum(len(s.get("items") or []) + (1 if s.get("content") and not s.get("items") else 0) for s in regression_sections)
        assert total_items <= 5

    def test_warnings_max_8(self):
        from app.audit import build_feishu_trend_sections
        report = _trend_report(warnings=[f"warn_{i}_very_long_warning_text_to_test_truncation" for i in range(15)])
        result = build_feishu_trend_sections(report, _trend_summary())
        warning_sections = [s for s in result["sections"] if s["section_type"] == "warnings"]
        assert len(warning_sections) == 1
        items = warning_sections[0].get("items") or []
        assert len(items) <= 8

    def test_artifact_links_accepts_report_artifact(self):
        from app.audit import build_feishu_trend_sections
        result = build_feishu_trend_sections(
            _trend_report(),
            _trend_summary(),
            _guard(),
            _artifact_bundle(),
        )
        artifact_sections = [s for s in result["sections"] if s["section_type"] == "artifact_links"]
        assert len(artifact_sections) == 1
        items = artifact_sections[0].get("items") or []
        assert len(items) == 2

    def test_artifact_links_rejects_audit_trail_path(self):
        from app.audit import build_feishu_trend_sections
        bad_bundle = {
            "artifacts": [
                {
                    "artifact_id": "bad_art",
                    "artifact_type": "forbidden",
                    "output_path": "migration_reports/foundation_audit/audit_trail/foundation_diagnostic_runs.jsonl",
                }
            ]
        }
        result = build_feishu_trend_sections(_trend_report(), _trend_summary(), _guard(), bad_bundle)
        warning_text = json.dumps(result["warnings"])
        assert "artifact_path_rejected" in warning_text or any("rejected" in w for w in result["warnings"])

    def test_guard_summary_with_guard_data(self):
        from app.audit import build_feishu_trend_sections
        result = build_feishu_trend_sections(_trend_report(), _trend_summary(), _guard())
        guard_sections = [s for s in result["sections"] if s["section_type"] == "guard_summary"]
        assert len(guard_sections) == 1
        items = guard_sections[0].get("items") or []
        labels = {item["label"] for item in items}
        assert "audit_jsonl_unchanged" in labels
        assert "sensitive_output_detected" in labels


# ─── build_feishu_trend_card_json tests ────────────────────────────────────

class TestBuildCardJson:
    def test_card_json_serializable(self):
        from app.audit import build_feishu_trend_sections, build_feishu_trend_card_json
        sections_result = build_feishu_trend_sections(_trend_report(), _trend_summary())
        result = build_feishu_trend_card_json(sections_result["sections"])
        card = result["card_json"]
        serialized = json.dumps(card)
        assert len(serialized) > 0

    def test_card_json_has_header(self):
        from app.audit import build_feishu_trend_sections, build_feishu_trend_card_json
        sections_result = build_feishu_trend_sections(_trend_report(), _trend_summary())
        result = build_feishu_trend_card_json(sections_result["sections"], title="Test Title")
        card = result["card_json"]
        assert "header" in card
        assert card["header"]["template"] == "blue"

    def test_card_json_has_projection_meta(self):
        from app.audit import build_feishu_trend_sections, build_feishu_trend_card_json
        sections_result = build_feishu_trend_sections(_trend_report(), _trend_summary())
        result = build_feishu_trend_card_json(sections_result["sections"])
        card = result["card_json"]
        assert card["_safety"]["projection_only"] is True
        assert card["_safety"]["send_allowed"] is False
        assert card["_safety"]["no_network_call"] is True


# ─── build_feishu_trend_payload_projection tests ────────────────────────────

class TestPayloadProjection:
    def test_send_allowed_false(self):
        from app.audit import build_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(_trend_report(), _trend_summary())
        assert payload["send_allowed"] is False

    def test_status_projection_only(self):
        from app.audit import build_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(_trend_report(), _trend_summary())
        assert payload["status"] == "projection_only"

    def test_no_webhook_call_true(self):
        from app.audit import build_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(_trend_report(), _trend_summary())
        assert payload["no_webhook_call"] is True

    def test_no_runtime_write_true(self):
        from app.audit import build_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(_trend_report(), _trend_summary())
        assert payload["no_runtime_write"] is True

    def test_no_action_queue_write_true(self):
        from app.audit import build_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(_trend_report(), _trend_summary())
        assert payload["no_action_queue_write"] is True

    def test_no_auto_fix_true(self):
        from app.audit import build_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(_trend_report(), _trend_summary())
        assert payload["no_auto_fix"] is True

    def test_payload_has_required_fields(self):
        from app.audit import build_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(_trend_report(), _trend_summary())
        assert "payload_id" in payload
        assert "generated_at" in payload
        assert "sections" in payload
        assert "card_json" in payload
        assert "send_permission" in payload

    def test_guard_data_integrated(self):
        from app.audit import build_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(
            _trend_report(), _trend_summary(), _guard(), _artifact_bundle()
        )
        guard_section = next(
            (s for s in payload["sections"] if s["section_type"] == "guard_summary"), None
        )
        assert guard_section is not None
        items = {item["label"] for item in guard_section.get("items") or []}
        assert "audit_jsonl_unchanged" in items


# ─── validate_feishu_trend_payload_projection tests ───────────────────────

class TestValidation:
    def test_valid_payload_passes(self):
        from app.audit import build_feishu_trend_payload_projection, validate_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(_trend_report(), _trend_summary())
        result = validate_feishu_trend_payload_projection(payload, _guard())
        assert result["valid"] is True
        assert result["send_allowed_is_false"] is True

    def test_rejects_send_allowed_true(self):
        from app.audit import validate_feishu_trend_payload_projection
        bad_payload = {
            "send_allowed": True,
            "status": "projection_only",
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {},
            "sections": [],
        }
        result = validate_feishu_trend_payload_projection(bad_payload, _guard())
        assert result["valid"] is False
        assert result["send_allowed_is_false"] is False

    def test_rejects_webhook_url(self):
        from app.audit import validate_feishu_trend_payload_projection
        bad_payload = {
            "send_allowed": False,
            "status": "projection_only",
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {"elements": [{"content": "check https://open.feishu.cn/webhook/bot?webhook=secret"}]},
            "sections": [],
        }
        result = validate_feishu_trend_payload_projection(bad_payload, _guard())
        assert result["valid"] is False
        assert any("webhook" in r.lower() for r in result["blocked_reasons"])

    def test_rejects_token_secret_api_key(self):
        from app.audit import validate_feishu_trend_payload_projection
        bad_payload = {
            "send_allowed": False,
            "status": "projection_only",
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {"elements": [{"content": "api_key=sk-1234567890abcdef"}]},
            "sections": [],
        }
        result = validate_feishu_trend_payload_projection(bad_payload, _guard())
        assert result["valid"] is False
        assert any("token" in r.lower() or "api_key" in r.lower() for r in result["blocked_reasons"])

    def test_rejects_guard_line_count_changed(self):
        from app.audit import validate_feishu_trend_payload_projection
        payload = {
            "send_allowed": False,
            "status": "projection_only",
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {},
            "sections": [],
        }
        bad_guard = _guard(audit_jsonl_unchanged=False)
        result = validate_feishu_trend_payload_projection(payload, bad_guard)
        assert result["valid"] is False
        assert result["line_count_changed"] is True

    def test_rejects_sensitive_output_detected(self):
        from app.audit import validate_feishu_trend_payload_projection
        payload = {
            "send_allowed": False,
            "status": "projection_only",
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {},
            "sections": [],
        }
        bad_guard = _guard(sensitive_output_detected=True)
        result = validate_feishu_trend_payload_projection(payload, bad_guard)
        assert result["valid"] is False
        assert result["sensitive_content_detected"] is True

    def test_rejects_network_call_detected(self):
        from app.audit import validate_feishu_trend_payload_projection
        payload = {
            "send_allowed": False,
            "status": "projection_only",
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {},
            "sections": [],
        }
        bad_guard = _guard(network_call_detected=True)
        result = validate_feishu_trend_payload_projection(payload, bad_guard)
        assert result["valid"] is False

    def test_rejects_forbidden_artifact_path(self):
        from app.audit import validate_feishu_trend_payload_projection
        payload = {
            "send_allowed": False,
            "status": "projection_only",
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {},
            "sections": [
                {
                    "section_type": "artifact_links",
                    "items": [
                        {"label": "forbidden", "value": "migration_reports/foundation_audit/audit_trail/foundation_diagnostic_runs.jsonl"}
                    ]
                }
            ],
        }
        result = validate_feishu_trend_payload_projection(payload, _guard())
        assert result["valid"] is False
        assert any("forbidden_artifact_path" in r for r in result["blocked_reasons"])


# ─── generate_feishu_trend_payload_projection tests ───────────────────────

class TestGenerateProjection:
    def test_returns_projection_payload_with_safety_flags(self, monkeypatch):
        from app.audit import audit_trend_cli_guard as guard_module
        import app.audit.audit_trend_projection as trend_proj_mod

        def fake_run_guard(**kwargs):
            return _guard()

        def fake_trend_report(**kwargs):
            return {
                "trend_report": _trend_report(),
                "warnings": [],
                "errors": [],
            }

        monkeypatch.setattr(guard_module, "run_guarded_audit_trend_cli_projection", fake_run_guard)
        monkeypatch.setattr(trend_proj_mod, "generate_dryrun_nightly_trend_report", fake_trend_report)

        from app.audit import generate_feishu_trend_payload_projection
        result = generate_feishu_trend_payload_projection(root=str(ROOT), window="all_available")

        assert result["send_allowed"] is False
        assert result["no_webhook_call"] is True
        assert result["no_auto_fix"] is True
        assert result["no_runtime_write"] is True
        assert result["no_action_queue_write"] is True


# ─── generate_feishu_trend_payload_projection_sample tests ─────────────────

class TestSample:
    def test_sample_writes_tmp_path(self, tmp_path):
        from app.audit import generate_feishu_trend_payload_projection_sample
        sample = generate_feishu_trend_payload_projection_sample(
            output_path=str(tmp_path / "sample.json"),
            root=str(ROOT),
        )
        assert Path(sample["output_path"]).exists()
        data = json.loads(Path(sample["output_path"]).read_text(encoding="utf-8"))
        assert "feishu_trend_payload_projection" in data
        assert "validation" in data
        assert data["generated_at"]

    def test_sample_not_write_audit_jsonl(self, tmp_path, monkeypatch):
        # Verify append functions are never invoked (reads via query engine are OK)
        from app.audit import append_audit_record_to_target
        append_called = []
        orig_fn = append_audit_record_to_target

        def track_append(*args, **kwargs):
            append_called.append((args, kwargs))
            return orig_fn(*args, **kwargs)

        monkeypatch.setattr("app.audit.audit_trail_writer.append_audit_record_to_target", track_append)

        from app.audit import generate_feishu_trend_payload_projection_sample
        sample = generate_feishu_trend_payload_projection_sample(
            output_path=str(tmp_path / "sample.json"),
            root=str(ROOT),
        )
        assert len(append_called) == 0


# ─── Safety constraint tests ──────────────────────────────────────────────

class TestSafetyConstraints:
    def test_no_webhook_url_in_payload(self):
        from app.audit import build_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(_trend_report(), _trend_summary())
        # Only check for URL patterns; "webhook" in "no_webhook_call" is legitimate
        payload_str = json.dumps(payload)
        assert "http://" not in payload_str
        assert "https://" not in payload_str

    def test_no_secret_token_in_payload(self):
        from app.audit import build_feishu_trend_payload_projection
        payload = build_feishu_trend_payload_projection(_trend_report(), _trend_summary())
        payload_str = json.dumps(payload)
        assert not any(x in payload_str.lower() for x in ["api_key", "secret", "token", "password"])

    def test_guard_rejects_runtime_path_in_artifact(self):
        from app.audit import validate_feishu_trend_payload_projection
        payload = {
            "send_allowed": False,
            "status": "projection_only",
            "no_webhook_call": True,
            "no_runtime_write": True,
            "no_action_queue_write": True,
            "no_auto_fix": True,
            "card_json": {},
            "sections": [
                {
                    "section_type": "artifact_links",
                    "items": [{"label": "runtime", "value": ".deerflow/runtime/some_state.json"}]
                }
            ],
        }
        result = validate_feishu_trend_payload_projection(payload, _guard())
        assert result["valid"] is False
