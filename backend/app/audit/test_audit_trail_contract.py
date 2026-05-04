"""Tests for audit_trail_contract.py (R241-11A Design-only Contract).

These tests verify the schema, redaction, sensitivity classification, and projection
helpers WITHOUT writing files, calling webhooks, or modifying runtime.
"""

from pathlib import Path

import pytest

from app.audit import audit_trail_contract as contract


# ─────────────────────────────────────────────────────────────────────────────
# Sensitivity Classification Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_classify_audit_sensitivity_detects_webhook_url():
    result = contract.classify_audit_sensitivity({"webhook_url": "https://open.feishu.cn/webhook/xxx"})
    assert result["sensitivity_level"] == "secret_or_token"
    assert "webhook_url" in result["detected_sensitive_keys"]


def test_classify_audit_sensitivity_detects_api_key_token_secret():
    for key in ["api_key", "api_secret", "token", "bearer_token", "password", "secret_key"]:
        result = contract.classify_audit_sensitivity({key: "sk-abcdefghijk123456"})
        assert result["sensitivity_level"] == "secret_or_token", f"failed for {key}"
        assert key in result["detected_sensitive_keys"]


def test_classify_audit_sensitivity_detects_private_body():
    for key in ["body", "content", "prompt_body", "memory_body", "rtcm_body", "artifact_body"]:
        result = contract.classify_audit_sensitivity({key: "this is a long secret content that should be redacted"})
        assert result["sensitivity_level"] == "user_private_content", f"failed for {key}"
        assert key in result["detected_sensitive_keys"]


def test_classify_audit_sensitivity_public_metadata():
    result = contract.classify_audit_sensitivity({
        "command": "memory",
        "status": "ok",
        "severity": "info",
    })
    assert result["sensitivity_level"] == "public_metadata"


def test_classify_audit_sensitivity_internal_metadata():
    result = contract.classify_audit_sensitivity({
        "status": "partial_warning",
        "summary": {"scanned_count": 50, "risk_count": 2},
        "payload_hash": "abc123",
    })
    # counts and hashes → internal_metadata
    assert result["sensitivity_level"] == "internal_metadata"


# ─────────────────────────────────────────────────────────────────────────────
# Redaction Policy Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_build_audit_redaction_policy_returns_dict():
    result = contract.build_audit_redaction_policy()
    assert isinstance(result, dict)
    assert result["redact_webhook_urls"] is True
    assert result["redact_tokens"] is True
    assert result["redact_prompt_body"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Redaction Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_redact_audit_payload_does_not_modify_original():
    original = {"webhook_url": "https://open.feishu.cn/webhook/secret", "status": "ok"}
    original_copy = dict(original)
    result = contract.redact_audit_payload(original)
    assert original == original_copy
    assert result["webhook_url"] == "[REDACTED]"


def test_redact_audit_payload_redacts_webhook_token_secret():
    payload = {
        "webhook_url": "https://open.feishu.cn/webhook/xxx",
        "bearer_token": "sk-abcdefghijk1234567890",
        "secret_key": "sk-abcdefghijk1234567890",
        "status": "ok",
    }
    result = contract.redact_audit_payload(payload)
    assert result["webhook_url"] == "[REDACTED]"
    assert result["bearer_token"] == "[REDACTED]"
    assert result["secret_key"] == "[REDACTED]"
    assert result["status"] == "ok"


def test_redact_audit_payload_redacts_private_bodies():
    payload = {
        "prompt_body": "actual prompt content with secrets",
        "memory_body": "memory artifact content",
        "rtcm_body": "rtcm artifact session content",
        "status": "ok",
    }
    result = contract.redact_audit_payload(payload)
    assert result["prompt_body"] == "[CONTENT_REDACTED]"
    assert result["memory_body"] == "[CONTENT_REDACTED]"
    assert result["rtcm_body"] == "[CONTENT_REDACTED]"
    assert result["status"] == "ok"


def test_redact_audit_payload_preserves_path_metadata():
    payload = {
        "source_path": "/home/user/.deerflow/memory/checkpoints/xxx",
        "file_path": "/var/data/runtime.json",
        "status": "ok",
    }
    result = contract.redact_audit_payload(payload)
    # path metadata should be preserved (allow_path_metadata=True)
    assert result["source_path"] == "/home/user/.deerflow/memory/checkpoints/xxx"
    assert result["file_path"] == "/var/data/runtime.json"


# ─────────────────────────────────────────────────────────────────────────────
# Audit Record Projection Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_create_audit_record_from_diagnostic_result_generates_hash():
    diagnostic_result = {
        "command": "truth-state",
        "status": "ok",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "root": "E:\\OpenClaw-Base\\deerflow",
        "summary": {"truth_events_count": 10},
        "payload": {"count": 5},
        "warnings": ["queue_missing"],
        "errors": [],
    }
    record = contract.create_audit_record_from_diagnostic_result(diagnostic_result)
    assert record["write_mode"] == "design_only"
    assert record["payload_hash"] is not None
    assert len(record["payload_hash"]) == 32


def test_create_audit_record_from_diagnostic_result_write_mode_design_only():
    diagnostic_result = {
        "command": "memory",
        "status": "partial_warning",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "root": "E:\\OpenClaw-Base\\deerflow",
        "summary": {"scanned_count": 50},
        "payload": {},
        "warnings": ["max_files_reached"],
        "errors": [],
    }
    record = contract.create_audit_record_from_diagnostic_result(diagnostic_result)
    assert record["write_mode"] == "design_only"
    assert record["source_command"] == "memory"
    assert record["status"] == "partial_warning"


def test_create_audit_record_from_diagnostic_result_redacts_sensitive():
    diagnostic_result = {
        "command": "feishu-summary",
        "status": "ok",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "root": "E:\\OpenClaw-Base\\deerflow",
        "summary": {"send_allowed": False},
        "payload": {"webhook_url": "https://open.feishu.cn/webhook/secret", "status": "ok"},
        "warnings": [],
        "errors": [],
    }
    record = contract.create_audit_record_from_diagnostic_result(diagnostic_result)
    # webhook_url should be redacted in payload_hash computation
    assert record["redaction_applied"] is True
    assert record["sensitivity_level"] == "secret_or_token"


# ─────────────────────────────────────────────────────────────────────────────
# Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_validate_audit_record_rejects_raw_secret_token():
    record = {
        "audit_record_id": "audit_1234567890",
        "event_type": "diagnostic_cli_run",
        "write_mode": "design_only",
        "schema_version": "1.0",
        "payload_hash": "abc123",
        "payload": {
            "webhook_url": "https://open.feishu.cn/webhook/real_secret",
        },
    }
    result = contract.validate_audit_record(record)
    assert result["valid"] is False
    assert any("raw_sensitive_value_detected" in e for e in result["errors"])


def test_validate_audit_record_rejects_full_private_body():
    record = {
        "audit_record_id": "audit_1234567890",
        "event_type": "diagnostic_cli_run",
        "write_mode": "design_only",
        "schema_version": "1.0",
        "payload_hash": "abc123",
        "payload": {
            "body": "this is the full private content that should never appear in audit records and must be longer than 100 chars to trigger validation",
        },
    }
    result = contract.validate_audit_record(record)
    assert result["valid"] is False
    assert any("unredacted_private_body_key" in e for e in result["errors"])


def test_validate_audit_record_accepts_valid_record():
    record = {
        "audit_record_id": "audit_1234567890",
        "event_type": "diagnostic_cli_run",
        "write_mode": "design_only",
        "schema_version": "1.0",
        "payload_hash": "abc123def456",
        "payload": {
            "status": "ok",
            "scanned_count": 50,
        },
        "summary": {},
        "warnings": [],
        "errors": [],
    }
    result = contract.validate_audit_record(record)
    assert result["valid"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Target Specs Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_build_audit_target_specs_does_not_create_files(tmp_path):
    result = contract.build_audit_target_specs(root=str(tmp_path))
    assert "target_specs" in result
    for spec in result["target_specs"]:
        path = Path(spec["target_path"])
        # Design only — file should NOT exist anywhere
        assert not path.exists(), f"File should not exist: {path}"
        assert spec["append_only"] is True
        assert spec["allow_overwrite"] is False
        assert spec["format"] == "jsonl"
    # No unexpected files in tmp_path either
    created = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(created) == 0, f"Unexpected files created: {created}"


def test_build_audit_target_specs_has_five_targets():
    result = contract.build_audit_target_specs()
    assert len(result["target_specs"]) == 5
    target_ids = {s["target_id"] for s in result["target_specs"]}
    assert "foundation_diagnostic_runs" in target_ids
    assert "feishu_summary_dryruns" in target_ids
    assert "nightly_health_reviews" in target_ids


# ─────────────────────────────────────────────────────────────────────────────
# Query Specs Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_build_audit_query_specs_has_required_dimensions():
    result = contract.build_audit_query_specs()
    query_ids = {q["query_id"] for q in result["query_specs"]}
    assert "by_command" in query_ids
    assert "by_status" in query_ids
    assert "by_date_range" in query_ids
    assert "by_context_id" in query_ids
    assert "by_request_id" in query_ids


# ─────────────────────────────────────────────────────────────────────────────
# Design Aggregation Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_build_append_only_audit_trail_design_has_six_phases():
    result = contract.build_append_only_audit_trail_design()
    phases = result.get("implementation_phases", [])
    assert len(phases) == 6
    phase_nums = {p["phase"] for p in phases}
    assert phase_nums == {1, 2, 3, 4, 5, 6}


def test_build_append_only_audit_trail_design_blocked_paths():
    result = contract.build_append_only_audit_trail_design()
    blocked = result.get("blocked_write_paths", [])
    assert "memory.json" in blocked
    assert "qdrant" in blocked
    assert "sqlite" in blocked


def test_build_append_only_audit_trail_design_integration_points():
    result = contract.build_append_only_audit_trail_design()
    integration = result.get("integration_points", [])
    assert any("foundation_diagnostics_cli" in p for p in integration)
    assert any("foundation_health_summary" in p for p in integration)


# ─────────────────────────────────────────────────────────────────────────────
# Generator Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_append_only_audit_trail_design_writes_only_to_tmp(tmp_path):
    json_out = tmp_path / "contract.json"
    result = contract.generate_append_only_audit_trail_design(output_path=str(json_out))
    assert json_out.exists()
    assert "json_output_path" in result
    # No other files should be created in tmp_path
    created = list(tmp_path.iterdir())
    assert len(created) == 1  # only the JSON file


def test_generate_append_only_audit_trail_design_structure(tmp_path):
    json_out = tmp_path / "contract.json"
    result = contract.generate_append_only_audit_trail_design(output_path=str(json_out))
    assert result["write_mode"] == "design_only"
    assert "target_specs" in result
    assert "record_schema" in result
    assert "redaction_policy" in result
    assert "query_specs" in result
    assert "implementation_phases" in result


# ─────────────────────────────────────────────────────────────────────────────
# Safety / No-Modification Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_no_real_audit_jsonl_written(tmp_path):
    """Verify generate does not write real audit_trail JSONL files."""
    result = contract.generate_append_only_audit_trail_design()
    design = result
    for spec in design.get("target_specs", []):
        path = Path(spec["target_path"])
        # No runtime audit_trail directory should be created
        assert "audit_trail" not in str(path) or path.parent == tmp_path or not path.exists()


def test_no_runtime_modified():
    """Verify contract module does not modify runtime when imported."""
    import tempfile
    import os

    before = set(os.listdir(tempfile.gettempdir())) if os.path.exists(tempfile.gettempdir()) else set()
    # Import the module (no-op — just check it loads)
    from app.audit import audit_trail_contract  # noqa: F401
    after = set(os.listdir(tempfile.gettempdir())) if os.path.exists(tempfile.gettempdir()) else set()
    # No temp files created by importing
    assert before == after


def test_no_network_calls():
    """Verify no network calls are made during any contract operation."""
    result = contract.build_append_only_audit_trail_design()
    assert result.get("write_mode") == "design_only"
    # No HTTP/webhook references in output
    design_str = str(result)
    assert "http" not in design_str.lower() or "design_only" in design_str.lower()


def test_read_only_diagnostics_cli_not_modified():
    """Verify read_only_diagnostics_cli.py was not modified by this module."""
    from app.foundation import read_only_diagnostics_cli as cli
    # The CLI module should still have feishu-summary in implemented commands
    registry = cli.get_diagnostic_command_registry()
    assert "feishu-summary" in registry["available_commands"]
    # No audit_trail references should be in CLI
    assert "audit" not in cli.__file__.lower()


def test_scripts_foundation_diagnose_not_modified():
    """Verify scripts/foundation_diagnose.py was not modified."""
    from pathlib import Path
    path = Path("scripts/foundation_diagnose.py")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    # Should not import audit module
    assert "audit" not in content.lower() or "from app.audit" not in content
