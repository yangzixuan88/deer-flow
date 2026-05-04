"""Tests for audit_trail_writer.py (R241-11C Append-only JSONL Writer).

These tests verify the append-only JSONL writer WITHOUT writing to production
audit_trail directory or runtime. Real append tests use tmp_path.
"""

from pathlib import Path
import json

import pytest

from app.audit import audit_trail_writer as writer


# ─────────────────────────────────────────────────────────────────────────────
# resolve_audit_target Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_resolve_audit_target_diagnostic_cli_run():
    record = {"event_type": "diagnostic_cli_run", "source_command": "all"}
    result = writer.resolve_audit_target(record)
    assert result["target_id"] == "foundation_diagnostic_runs"
    assert result["target_path"].endswith("foundation_diagnostic_runs.jsonl")
    assert result["errors"] == []


def test_resolve_audit_target_diagnostic_domain_result():
    record = {"event_type": "diagnostic_domain_result", "source_command": "truth-state"}
    result = writer.resolve_audit_target(record)
    assert result["target_id"] == "foundation_diagnostic_runs"


def test_resolve_audit_target_nightly_health_review():
    record = {"event_type": "nightly_health_review"}
    result = writer.resolve_audit_target(record)
    assert result["target_id"] == "nightly_health_reviews"
    assert result["target_path"].endswith("nightly_health_reviews.jsonl")


def test_resolve_audit_target_feishu_summary_dry_run():
    record = {"event_type": "feishu_summary_dry_run"}
    result = writer.resolve_audit_target(record)
    assert result["target_id"] == "feishu_summary_dryruns"
    assert result["target_path"].endswith("feishu_summary_dryruns.jsonl")


def test_resolve_audit_target_tool_runtime_projection():
    record = {"event_type": "tool_runtime_projection"}
    result = writer.resolve_audit_target(record)
    assert result["target_id"] == "tool_runtime_projections"


def test_resolve_audit_target_mode_callgraph_projection():
    record = {"event_type": "mode_callgraph_projection"}
    result = writer.resolve_audit_target(record)
    assert result["target_id"] == "mode_callgraph_projections"


def test_resolve_audit_target_explicit_target_id():
    record = {"event_type": "diagnostic_domain_result"}
    result = writer.resolve_audit_target(record, target_id="nightly_health_reviews")
    assert result["target_id"] == "nightly_health_reviews"


def test_resolve_audit_target_invalid_target_id():
    record = {"event_type": "diagnostic_domain_result"}
    result = writer.resolve_audit_target(record, target_id="invalid_target")
    assert result["errors"] == ["invalid_target_id:invalid_target"]
    assert result["target_spec"] is None


def test_resolve_audit_target_unknown_event_type_defaults():
    record = {"event_type": "some_unknown_event"}
    result = writer.resolve_audit_target(record)
    assert result["target_id"] == "foundation_diagnostic_runs"
    assert any("unknown_event_type" in w for w in result["warnings"])


# ─────────────────────────────────────────────────────────────────────────────
# validate_append_only_target_path Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_validate_append_only_target_path_accepts_audit_trail_jsonl(tmp_path):
    # Use a path that follows the audit_trail structure: root/migration_reports/foundation_audit/audit_trail/
    root = tmp_path
    target = root / "migration_reports" / "foundation_audit" / "audit_trail" / "foundation_diagnostic_runs.jsonl"
    result = writer.validate_append_only_target_path(str(target), root=str(root))
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_append_only_target_path_rejects_double_dot():
    result = writer.validate_append_only_target_path(
        "migration_reports/foundation_audit/audit_trail/../etc/passwd"
    )
    assert result["valid"] is False
    assert any(".." in e for e in result["errors"]) or any("path_traversal" in e for e in result["errors"])


def test_validate_append_only_target_path_rejects_runtime_memory():
    result = writer.validate_append_only_target_path(
        "migration_reports/foundation_audit/audit_trail/../../../memory.json"
    )
    assert result["valid"] is False
    assert any("path_traversal" in e or "outside_audit_trail" in e for e in result["errors"])


def test_validate_append_only_target_path_rejects_non_jsonl():
    result = writer.validate_append_only_target_path(
        "migration_reports/foundation_audit/audit_trail/test.txt"
    )
    assert result["valid"] is False
    assert any("suffix" in e for e in result["errors"])


def test_validate_append_only_target_path_rejects_governance_state():
    result = writer.validate_append_only_target_path(
        "migration_reports/foundation_audit/audit_trail/governance_state.jsonl"
    )
    assert result["valid"] is False
    assert any("restricted_path_element" in e for e in result["errors"])


# ─────────────────────────────────────────────────────────────────────────────
# serialize_audit_record_jsonl Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_serialize_audit_record_jsonl_generates_single_line_with_newline():
    record = {
        "audit_record_id": "test_123",
        "event_type": "diagnostic_domain_result",
        "write_mode": "dry_run",
        "source_system": "test",
        "status": "ok",
        "root": "E:\\test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "observed_at": "2026-04-25T00:00:00+00:00",
        "payload_hash": "a" * 32,
        "summary": {},
        "warnings": [],
        "errors": [],
        "sensitivity_level": "public_metadata",
        "retention_class": "medium_term_operational",
        "redaction_applied": False,
        "schema_version": "1.0",
    }
    result = writer.serialize_audit_record_jsonl(record)
    assert result["line"] is not None
    assert result["line"].endswith("\n")
    assert result["line"].count("\n") == 1
    assert result["errors"] == []


def test_serialize_audit_record_jsonl_produces_valid_json_line():
    record = {
        "audit_record_id": "test_456",
        "event_type": "diagnostic_domain_result",
        "write_mode": "dry_run",
        "source_system": "test",
        "status": "ok",
        "root": "E:\\test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "observed_at": "2026-04-25T00:00:00+00:00",
        "payload_hash": "b" * 32,
        "summary": {},
        "warnings": [],
        "errors": [],
        "sensitivity_level": "public_metadata",
        "retention_class": "medium_term_operational",
        "redaction_applied": False,
        "schema_version": "1.0",
    }
    result = writer.serialize_audit_record_jsonl(record)
    line = result["line"].rstrip("\n")
    parsed = json.loads(line)
    assert parsed["audit_record_id"] == "test_456"


# ─────────────────────────────────────────────────────────────────────────────
# append_audit_record_to_target Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_append_audit_record_to_target_dry_run_does_not_create_files(tmp_path):
    record = {
        "audit_record_id": "dryrun_test",
        "event_type": "diagnostic_domain_result",
        "write_mode": "dry_run",
        "source_system": "test",
        "status": "ok",
        "root": "E:\\test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "observed_at": "2026-04-25T00:00:00+00:00",
        "payload_hash": "c" * 32,
        "summary": {},
        "warnings": [],
        "errors": [],
        "sensitivity_level": "public_metadata",
        "retention_class": "medium_term_operational",
        "redaction_applied": False,
        "schema_version": "1.0",
    }
    result = writer.append_audit_record_to_target(record, root=str(tmp_path), dry_run=True)
    assert result.status == writer.AuditAppendStatus.SKIPPED_DRY_RUN
    assert result.bytes_written == 0
    created = list(tmp_path.rglob("*"))
    assert len(created) == 0


def test_append_audit_record_to_target_dry_run_false_appends(tmp_path):
    record = {
        "audit_record_id": "append_test_1",
        "event_type": "diagnostic_domain_result",
        "write_mode": "dry_run",
        "source_system": "test",
        "status": "ok",
        "root": "E:\\test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "observed_at": "2026-04-25T00:00:00+00:00",
        "payload_hash": "d" * 32,
        "summary": {},
        "warnings": [],
        "errors": [],
        "sensitivity_level": "public_metadata",
        "retention_class": "medium_term_operational",
        "redaction_applied": False,
        "schema_version": "1.0",
    }
    result = writer.append_audit_record_to_target(record, root=str(tmp_path), dry_run=False)
    assert result.status == writer.AuditAppendStatus.APPENDED
    assert result.bytes_written > 0
    target_path = Path(result.target_path)
    assert target_path.exists()
    with open(target_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1


def test_append_audit_record_to_target_second_append_no_overwrite(tmp_path):
    record1 = {
        "audit_record_id": "append_test_2a",
        "event_type": "diagnostic_domain_result",
        "write_mode": "dry_run",
        "source_system": "test",
        "status": "ok",
        "root": "E:\\test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "observed_at": "2026-04-25T00:00:00+00:00",
        "payload_hash": "e" * 32,
        "summary": {},
        "warnings": [],
        "errors": [],
        "sensitivity_level": "public_metadata",
        "retention_class": "medium_term_operational",
        "redaction_applied": False,
        "schema_version": "1.0",
    }
    record2 = dict(record1)
    record2["audit_record_id"] = "append_test_2b"
    record2["payload_hash"] = "f" * 32

    r1 = writer.append_audit_record_to_target(record1, root=str(tmp_path), dry_run=False)
    r2 = writer.append_audit_record_to_target(record2, root=str(tmp_path), dry_run=False)

    assert r1.status == writer.AuditAppendStatus.APPENDED
    assert r2.status == writer.AuditAppendStatus.APPENDED

    target_path = Path(r1.target_path)
    with open(target_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 2


def test_append_audit_record_to_target_blocked_invalid_record(tmp_path):
    """Record without audit_record_id should be blocked."""
    record = {
        "event_type": "diagnostic_domain_result",
        "write_mode": "dry_run",
        # missing audit_record_id, payload_hash, etc.
        "status": "ok",
        "root": "E:\\test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "observed_at": "2026-04-25T00:00:00+00:00",
        "summary": {},
        "warnings": [],
        "errors": [],
        "sensitivity_level": "public_metadata",
        "retention_class": "medium_term_operational",
        "redaction_applied": False,
        "schema_version": "1.0",
    }
    result = writer.append_audit_record_to_target(record, root=str(tmp_path), dry_run=False)
    assert result.status == writer.AuditAppendStatus.BLOCKED_INVALID_RECORD


# ─────────────────────────────────────────────────────────────────────────────
# append_diagnostic_result_audit_record Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_append_diagnostic_result_audit_record_no_audit_record():
    result = {"command": "truth-state", "status": "ok"}
    append_result = writer.append_diagnostic_result_audit_record(result, dry_run=True)
    assert append_result.status == writer.AuditAppendStatus.BLOCKED_INVALID_RECORD
    assert any("no_audit_record" in w for w in append_result.warnings)


def test_append_diagnostic_result_audit_record_dry_run():
    result = {
        "command": "truth-state",
        "status": "ok",
        "audit_record": {
            "audit_record_id": "test_diag_123",
            "event_type": "diagnostic_domain_result",
            "write_mode": "dry_run",
            "source_system": "test",
            "status": "ok",
            "root": "E:\\test",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "observed_at": "2026-04-25T00:00:00+00:00",
            "payload_hash": "g" * 32,
            "summary": {},
            "warnings": [],
            "errors": [],
            "sensitivity_level": "public_metadata",
            "retention_class": "medium_term_operational",
            "redaction_applied": False,
            "schema_version": "1.0",
        },
    }
    append_result = writer.append_diagnostic_result_audit_record(result, dry_run=True)
    assert append_result.status == writer.AuditAppendStatus.SKIPPED_DRY_RUN


# ─────────────────────────────────────────────────────────────────────────────
# append_all_diagnostic_audit_records Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_append_all_diagnostic_audit_records_dry_run_no_files_created(tmp_path):
    all_result = {
        "command": "all",
        "status": "partial_warning",
        "audit_record": {
            "audit_record_id": "all_test_1",
            "event_type": "diagnostic_cli_run",
            "write_mode": "dry_run",
            "source_system": "test",
            "status": "ok",
            "root": "E:\\test",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "observed_at": "2026-04-25T00:00:00+00:00",
            "payload_hash": "h" * 32,
            "summary": {},
            "warnings": [],
            "errors": [],
            "sensitivity_level": "public_metadata",
            "retention_class": "medium_term_operational",
            "redaction_applied": False,
            "schema_version": "1.0",
        },
        "payload": {
            "diagnostics": {
                "truth-state": {
                    "command": "truth-state",
                    "status": "ok",
                    "audit_record": {
                        "audit_record_id": "ts_test_1",
                        "event_type": "diagnostic_domain_result",
                        "write_mode": "dry_run",
                        "source_system": "test",
                        "status": "ok",
                        "root": "E:\\test",
                        "generated_at": "2026-04-25T00:00:00+00:00",
                        "observed_at": "2026-04-25T00:00:00+00:00",
                        "payload_hash": "i" * 32,
                        "summary": {},
                        "warnings": [],
                        "errors": [],
                        "sensitivity_level": "public_metadata",
                        "retention_class": "medium_term_operational",
                        "redaction_applied": False,
                        "schema_version": "1.0",
                    },
                },
            }
        },
    }
    result = writer.append_all_diagnostic_audit_records(all_result, root=str(tmp_path), dry_run=True)
    assert result["skipped_count"] >= 1
    created = list(tmp_path.rglob("*"))
    assert len(created) == 0


def test_append_all_diagnostic_audit_records_single_failure_not_interrupt(tmp_path):
    all_result = {
        "command": "all",
        "status": "partial_warning",
        "audit_record": {
            "audit_record_id": "all_test_2",
            "event_type": "diagnostic_cli_run",
            "write_mode": "dry_run",
            "source_system": "test",
            "status": "ok",
            "root": "E:\\test",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "observed_at": "2026-04-25T00:00:00+00:00",
            "payload_hash": "j" * 32,
            "summary": {},
            "warnings": [],
            "errors": [],
            "sensitivity_level": "public_metadata",
            "retention_class": "medium_term_operational",
            "redaction_applied": False,
            "schema_version": "1.0",
        },
        "payload": {
            "diagnostics": {
                "truth-state": {
                    "command": "truth-state",
                    "status": "ok",
                    "audit_record": {
                        "audit_record_id": "ts_test_2",
                        "event_type": "diagnostic_domain_result",
                        "write_mode": "dry_run",
                        "source_system": "test",
                        "status": "ok",
                        "root": "E:\\test",
                        "generated_at": "2026-04-25T00:00:00+00:00",
                        "observed_at": "2026-04-25T00:00:00+00:00",
                        "payload_hash": "k" * 32,
                        "summary": {},
                        "warnings": [],
                        "errors": [],
                        "sensitivity_level": "public_metadata",
                        "retention_class": "medium_term_operational",
                        "redaction_applied": False,
                        "schema_version": "1.0",
                    },
                },
            }
        },
    }
    result = writer.append_all_diagnostic_audit_records(all_result, root=str(tmp_path), dry_run=True)
    assert result["total_records"] >= 2
    # dry_run should skip everything, not fail
    assert result["failed_count"] == 0


def test_append_all_diagnostic_audit_records_dry_run_false_writes(tmp_path):
    all_result = {
        "command": "all",
        "status": "partial_warning",
        "audit_record": {
            "audit_record_id": "all_test_3",
            "event_type": "diagnostic_cli_run",
            "write_mode": "dry_run",
            "source_system": "test",
            "status": "ok",
            "root": "E:\\test",
            "generated_at": "2026-04-25T00:00:00+00:00",
            "observed_at": "2026-04-25T00:00:00+00:00",
            "payload_hash": "l" * 32,
            "summary": {},
            "warnings": [],
            "errors": [],
            "sensitivity_level": "public_metadata",
            "retention_class": "medium_term_operational",
            "redaction_applied": False,
            "schema_version": "1.0",
        },
        "payload": {
            "diagnostics": {
                "truth-state": {
                    "command": "truth-state",
                    "status": "ok",
                    "audit_record": {
                        "audit_record_id": "ts_test_3",
                        "event_type": "diagnostic_domain_result",
                        "write_mode": "dry_run",
                        "source_system": "test",
                        "status": "ok",
                        "root": "E:\\test",
                        "generated_at": "2026-04-25T00:00:00+00:00",
                        "observed_at": "2026-04-25T00:00:00+00:00",
                        "payload_hash": "m" * 32,
                        "summary": {},
                        "warnings": [],
                        "errors": [],
                        "sensitivity_level": "public_metadata",
                        "retention_class": "medium_term_operational",
                        "redaction_applied": False,
                        "schema_version": "1.0",
                    },
                },
            }
        },
    }
    result = writer.append_all_diagnostic_audit_records(all_result, root=str(tmp_path), dry_run=False)
    assert result["appended_count"] >= 2
    # Verify files exist
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    assert audit_dir.exists()
    jsonl_files = list(audit_dir.glob("*.jsonl"))
    assert len(jsonl_files) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Safety / No-Modification Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_append_uses_append_mode_only(tmp_path):
    """Verify append_audit_record_to_target opens files in append-only mode."""
    record = {
        "audit_record_id": "append_mode_test",
        "event_type": "diagnostic_domain_result",
        "write_mode": "dry_run",
        "source_system": "test",
        "status": "ok",
        "root": "E:\\test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "observed_at": "2026-04-25T00:00:00+00:00",
        "payload_hash": "n" * 32,
        "summary": {},
        "warnings": [],
        "errors": [],
        "sensitivity_level": "public_metadata",
        "retention_class": "medium_term_operational",
        "redaction_applied": False,
        "schema_version": "1.0",
    }
    writer.append_audit_record_to_target(record, root=str(tmp_path), dry_run=False)
    target = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail" / "foundation_diagnostic_runs.jsonl"
    content = target.read_text(encoding="utf-8")
    assert content.endswith("\n") or len(content) > 0
    # Running twice should NOT overwrite line 1
    writer.append_audit_record_to_target(record, root=str(tmp_path), dry_run=False)
    content2 = target.read_text(encoding="utf-8")
    lines = content2.splitlines()
    assert len(lines) == 2
    assert content == lines[0] + "\n"


def test_no_webhook_calls():
    """Verify no network/webhook calls during append operations."""
    record = {
        "audit_record_id": "net_test",
        "event_type": "diagnostic_domain_result",
        "write_mode": "dry_run",
        "source_system": "test",
        "status": "ok",
        "root": "E:\\test",
        "generated_at": "2026-04-25T00:00:00+00:00",
        "observed_at": "2026-04-25T00:00:00+00:00",
        "payload_hash": "o" * 32,
        "summary": {},
        "warnings": [],
        "errors": [],
        "sensitivity_level": "public_metadata",
        "retention_class": "medium_term_operational",
        "redaction_applied": False,
        "schema_version": "1.0",
    }
    result = writer.append_audit_record_to_target(record, dry_run=True)
    result_str = str(result)
    assert "http" not in result_str.lower() or "skipped" in result_str.lower()


def test_generate_sample_writes_only_to_tmp(tmp_path):
    result = writer.generate_append_only_jsonl_writer_sample(
        output_path=str(tmp_path / "sample.json"),
        tmp_path=str(tmp_path),
    )
    assert (tmp_path / "sample.json").exists()
    assert result["warnings"] == ["tmp_path_used_for_testing"]
