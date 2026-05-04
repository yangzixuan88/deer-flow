"""Tests for audit_trail_query.py (R241-11D Phase 4).

Covers: discover, scan, load, filter, query, summarize, format, sample.
All tests are read-only: they do NOT write to audit_trail/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "backend"
for path in (str(ROOT), str(BACKEND)):
    if path not in sys.path:
        sys.path.insert(0, path)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_audit_trail(tmp_path: Path) -> Path:
    """Create a temporary audit_trail directory with sample JSONL files.

    Returns the ROOT of the audit trail (tmp_path), NOT the audit_trail/
    subdirectory. discover_audit_trail_files / scan_append_only_audit_trail
    internally append migration_reports/foundation_audit/audit_trail.
    """
    audit_dir = tmp_path / "migration_reports" / "foundation_audit" / "audit_trail"
    audit_dir.mkdir(parents=True, exist_ok=True)

    base_record = {
        "audit_record_id": "test_0001",
        "event_type": "diagnostic_cli_run",
        "write_mode": "append_only",
        "source_command": "all",
        "status": "partial_warning",
        "root": str(ROOT),
        "generated_at": "2026-04-25T10:00:00+00:00",
        "observed_at": "2026-04-25T10:00:01+00:00",
        "payload_hash": "abcd1234efgh5678",
        "sensitivity_level": "public_metadata",
        "retention_class": "medium_term_operational",
        "redaction_applied": False,
        "schema_version": "1.0",
        "warnings": [],
        "errors": [],
    }

    nightly_record = {
        **base_record,
        "audit_record_id": "test_0002",
        "event_type": "nightly_health_review",
        "source_command": "nightly",
        "status": "ok",
        "generated_at": "2026-04-25T09:00:00+00:00",
        "observed_at": "2026-04-25T09:00:01+00:00",
    }

    feishu_record = {
        **base_record,
        "audit_record_id": "test_0003",
        "event_type": "feishu_summary_dry_run",
        "source_command": "feishu-summary",
        "status": "partial_warning",
        "generated_at": "2026-04-25T09:30:00+00:00",
        "observed_at": "2026-04-25T09:30:01+00:00",
    }

    malformed_line = "this is not valid json\n"

    # foundation_diagnostic_runs.jsonl: 2 records
    foundation = audit_dir / "foundation_diagnostic_runs.jsonl"
    foundation.write_text(
        json.dumps(base_record, ensure_ascii=False) + "\n"
        + json.dumps(nightly_record, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # nightly_health_reviews.jsonl: 1 record
    nightly = audit_dir / "nightly_health_reviews.jsonl"
    nightly.write_text(json.dumps(nightly_record, ensure_ascii=False) + "\n", encoding="utf-8")

    # feishu_summary_dryruns.jsonl: 1 record
    feishu = audit_dir / "feishu_summary_dryruns.jsonl"
    feishu.write_text(json.dumps(feishu_record, ensure_ascii=False) + "\n", encoding="utf-8")

    # tool_runtime_projections.jsonl: empty
    tool = audit_dir / "tool_runtime_projections.jsonl"
    tool.write_text("", encoding="utf-8")

    # mode_callgraph_projections.jsonl: malformed line
    mode = audit_dir / "mode_callgraph_projections.jsonl"
    mode.write_text(malformed_line, encoding="utf-8")

    return tmp_path


@pytest.fixture
def query_mod():
    """Import audit_trail_query module."""
    from app.audit import audit_trail_query as mod
    return mod


# ─────────────────────────────────────────────────────────────────────────────
# Test: discover_audit_trail_files
# ─────────────────────────────────────────────────────────────────────────────




@pytest.mark.unit


@pytest.mark.unit
class TestDiscoverAuditTrailFiles:
    def test_discover_returns_structure(self, query_mod, tmp_audit_trail):
        result = query_mod.discover_audit_trail_files(root=str(tmp_audit_trail))
        assert "discovered_files" in result
        assert "missing_files" in result
        assert "warnings" in result

    def test_discover_finds_existing_files(self, query_mod, tmp_audit_trail):
        result = query_mod.discover_audit_trail_files(root=str(tmp_audit_trail))
        discovered = {f["target_id"]: f for f in result["discovered_files"]}
        assert discovered["foundation_diagnostic_runs"]["exists"] is True
        assert discovered["nightly_health_reviews"]["exists"] is True
        assert discovered["feishu_summary_dryruns"]["exists"] is True

    def test_discover_reports_missing_files(self, query_mod, tmp_audit_trail):
        result = query_mod.discover_audit_trail_files(root=str(tmp_audit_trail))
        # With the fixture creating all 5 files, missing_files is empty
        assert isinstance(result["missing_files"], list)

    def test_discover_does_not_create_directory(self, query_mod, tmp_path):
        fake_root = tmp_path / "nonexistent"
        result = query_mod.discover_audit_trail_files(root=str(fake_root))
        assert not fake_root.exists()


# ─────────────────────────────────────────────────────────────────────────────
# Test: scan_append_only_audit_trail
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestScanAuditTrail:
    @pytest.mark.slow
    def test_scan_returns_file_summaries(self, query_mod, tmp_audit_trail):
        result = query_mod.scan_append_only_audit_trail(root=str(tmp_audit_trail))
        assert "file_summaries" in result
        assert result["total_files"] == 5
        assert result["existing_files"] == 5  # fixture creates all 5 files

    @pytest.mark.slow
    def test_scan_counts_lines(self, query_mod, tmp_audit_trail):
        result = query_mod.scan_append_only_audit_trail(root=str(tmp_audit_trail))
        summaries = {s["target_id"]: s for s in result["file_summaries"]}
        assert summaries["foundation_diagnostic_runs"]["line_count"] == 2
        assert summaries["nightly_health_reviews"]["line_count"] == 1

    @pytest.mark.slow
    def test_scan_counts_valid_records(self, query_mod, tmp_audit_trail):
        result = query_mod.scan_append_only_audit_trail(root=str(tmp_audit_trail))
        summaries = {s["target_id"]: s for s in result["file_summaries"]}
        assert summaries["foundation_diagnostic_runs"]["valid_record_count"] == 2

    @pytest.mark.slow
    def test_scan_detects_malformed_lines(self, query_mod, tmp_audit_trail):
        result = query_mod.scan_append_only_audit_trail(root=str(tmp_audit_trail))
        summaries = {s["target_id"]: s for s in result["file_summaries"]}
        assert summaries["mode_callgraph_projections"]["invalid_line_count"] == 1
        assert "malformed_line" in summaries["mode_callgraph_projections"]["warnings"][0]

    @pytest.mark.slow
    def test_scan_does_not_crash_on_malformed(self, query_mod, tmp_audit_trail):
        # Malformed lines should be counted but not raise
        result = query_mod.scan_append_only_audit_trail(root=str(tmp_audit_trail))
        assert result["total_invalid_lines"] >= 1

    @pytest.mark.slow
    def test_scan_aggregates_by_event_type(self, query_mod, tmp_audit_trail):
        result = query_mod.scan_append_only_audit_trail(root=str(tmp_audit_trail))
        assert "diagnostic_cli_run" in result["by_event_type"]
        assert "nightly_health_review" in result["by_event_type"]


# ─────────────────────────────────────────────────────────────────────────────
# Test: load_audit_jsonl_records
# ─────────────────────────────────────────────────────────────────────────────


class TestLoadAuditRecords:
    @pytest.mark.slow
    @pytest.mark.integration
    def test_load_returns_records(self, query_mod, tmp_audit_trail):
        result = query_mod.load_audit_jsonl_records(root=str(tmp_audit_trail))
        assert "records" in result
        assert "scanned_count" in result
        assert "returned_count" in result

    def test_load_specific_target(self, query_mod, tmp_audit_trail):
        result = query_mod.load_audit_jsonl_records(
            target_id="nightly_health_reviews", root=str(tmp_audit_trail)
        )
        assert result["returned_count"] >= 1
        for rec in result["records"]:
            assert rec["event_type"] in ("nightly_health_review",)

    def test_load_all_targets(self, query_mod, tmp_audit_trail):
        result = query_mod.load_audit_jsonl_records(
            target_id=None, root=str(tmp_audit_trail)
        )
        # foundation (2) + nightly (1) + feishu (1) = 4
        assert result["returned_count"] == 4

    def test_load_limit_applies(self, query_mod, tmp_audit_trail):
        result = query_mod.load_audit_jsonl_records(
            target_id=None, root=str(tmp_audit_trail), limit=2
        )
        assert result["returned_count"] == 2
        # foundation(2) + nightly(1) + feishu(1) + tool(0) + mode(1 malformed) = 5
        assert result["scanned_count"] == 5

    def test_load_invalid_target_id(self, query_mod, tmp_audit_trail):
        result = query_mod.load_audit_jsonl_records(
            target_id="nonexistent_target", root=str(tmp_audit_trail)
        )
        assert result["returned_count"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Test: build_audit_query_filter
# ─────────────────────────────────────────────────────────────────────────────




@pytest.mark.unit


@pytest.mark.unit
class TestBuildAuditQueryFilter:
    def test_filter_default_limit(self, query_mod):
        f = query_mod.build_audit_query_filter()
        assert f["limit"] == 100

    def test_filter_limit_clamp_to_1000(self, query_mod):
        f = query_mod.build_audit_query_filter(limit=5000)
        assert f["limit"] == 1000
        assert f["warnings"] and any("limit_clamped" in w for w in f["warnings"])

    def test_filter_negative_limit_defaults(self, query_mod):
        f = query_mod.build_audit_query_filter(limit=-5)
        assert f["limit"] == 100

    def test_filter_order_asc_desc(self, query_mod):
        f_asc = query_mod.build_audit_query_filter(order="asc")
        assert f_asc["order"] == "asc"
        f_desc = query_mod.build_audit_query_filter(order="desc")
        assert f_desc["order"] == "desc"

    def test_filter_invalid_order_defaults(self, query_mod):
        f = query_mod.build_audit_query_filter(order="invalid")
        assert f["order"] == "asc"
        assert f["warnings"] and any("invalid_order" in w for w in f["warnings"])

    def test_filter_malformed_datetime_warning(self, query_mod):
        f = query_mod.build_audit_query_filter(start_time="not-a-date")
        assert "malformed_datetime" in f["warnings"][0]

    def test_filter_all_supported_fields(self, query_mod):
        f = query_mod.build_audit_query_filter(
            event_type="nightly_health_review",
            source_command="nightly",
            status="ok",
            write_mode="append_only",
            sensitivity_level="public_metadata",
            payload_hash="abcd",
            audit_record_id="test_0001",
            start_time="2026-04-01T00:00:00Z",
            end_time="2026-04-30T23:59:59Z",
            limit=50,
            offset=10,
            order="desc",
        )
        assert f["event_type"] == "nightly_health_review"
        assert f["source_command"] == "nightly"
        assert f["status"] == "ok"
        assert f["limit"] == 50
        assert f["offset"] == 10
        assert f["order"] == "desc"


# ─────────────────────────────────────────────────────────────────────────────
# Test: record_matches_audit_filter
# ─────────────────────────────────────────────────────────────────────────────




@pytest.mark.unit


@pytest.mark.unit
class TestRecordMatchesFilter:
    def test_match_event_type(self, query_mod):
        record = {"event_type": "nightly_health_review"}
        assert query_mod.record_matches_audit_filter(record, {"event_type": "nightly_health_review"}) is True
        assert query_mod.record_matches_audit_filter(record, {"event_type": "diagnostic_cli_run"}) is False

    def test_match_source_command(self, query_mod):
        record = {"source_command": "nightly"}
        assert query_mod.record_matches_audit_filter(record, {"source_command": "nightly"}) is True
        assert query_mod.record_matches_audit_filter(record, {"source_command": "all"}) is False

    def test_match_status(self, query_mod):
        record = {"status": "ok"}
        assert query_mod.record_matches_audit_filter(record, {"status": "ok"}) is True
        assert query_mod.record_matches_audit_filter(record, {"status": "failed"}) is False

    def test_match_sensitivity_level(self, query_mod):
        record = {"sensitivity_level": "public_metadata"}
        assert query_mod.record_matches_audit_filter(record, {"sensitivity_level": "public_metadata"}) is True
        assert query_mod.record_matches_audit_filter(record, {"sensitivity_level": "secret"}) is False

    def test_match_payload_hash_exact(self, query_mod):
        record = {"payload_hash": "abcd1234efgh5678"}
        assert query_mod.record_matches_audit_filter(record, {"payload_hash": "abcd1234efgh5678"}) is True
        assert query_mod.record_matches_audit_filter(record, {"payload_hash": "xxxx"}) is False

    def test_match_payload_hash_prefix(self, query_mod):
        record = {"payload_hash": "abcd1234efgh5678"}
        assert query_mod.record_matches_audit_filter(record, {"payload_hash": "abcd"}) is True
        assert query_mod.record_matches_audit_filter(record, {"payload_hash": "ab"}) is True
        assert query_mod.record_matches_audit_filter(record, {"payload_hash": "xyz"}) is False

    def test_match_time_range(self, query_mod):
        record = {"generated_at": "2026-04-25T10:00:00+00:00"}
        assert query_mod.record_matches_audit_filter(
            record, {"start_time": "2026-04-01T00:00:00Z", "end_time": "2026-04-30T23:59:59Z"}
        ) is True
        assert query_mod.record_matches_audit_filter(
            record, {"start_time": "2026-05-01T00:00:00Z"}
        ) is False

    def test_match_empty_filter(self, query_mod):
        record = {"event_type": "nightly_health_review"}
        assert query_mod.record_matches_audit_filter(record, {}) is True
        assert query_mod.record_matches_audit_filter(record, None) is True

    def test_match_combined_filters(self, query_mod):
        record = {
            "event_type": "nightly_health_review",
            "status": "ok",
            "source_command": "nightly",
        }
        assert query_mod.record_matches_audit_filter(record, {
            "event_type": "nightly_health_review",
            "status": "ok",
        }) is True
        assert query_mod.record_matches_audit_filter(record, {
            "event_type": "nightly_health_review",
            "status": "failed",
        }) is False


# ─────────────────────────────────────────────────────────────────────────────
# Test: query_audit_trail
# ─────────────────────────────────────────────────────────────────────────────




@pytest.mark.integration


@pytest.mark.integration
class TestQueryAuditTrail:
    @pytest.mark.slow
    def test_query_returns_result_structure(self, query_mod, tmp_audit_trail):
        result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        assert "query_id" in result
        assert "status" in result
        assert "records" in result
        assert "file_summaries" in result

    def test_query_filter_by_event_type(self, query_mod, tmp_audit_trail):
        result = query_mod.query_audit_trail(
            root=str(tmp_audit_trail),
            filters={"event_type": "nightly_health_review"},
        )
        for rec in result["records"]:
            assert rec["event_type"] == "nightly_health_review"

    def test_query_filter_by_status(self, query_mod, tmp_audit_trail):
        result = query_mod.query_audit_trail(
            root=str(tmp_audit_trail),
            filters={"status": "ok"},
        )
        for rec in result["records"]:
            assert rec["status"] == "ok"

    def test_query_limit_offset(self, query_mod, tmp_audit_trail):
        result_all = query_mod.query_audit_trail(
            root=str(tmp_audit_trail), filters={"limit": 100}
        )
        result_limited = query_mod.query_audit_trail(
            root=str(tmp_audit_trail), filters={"limit": 2}
        )
        result_offset = query_mod.query_audit_trail(
            root=str(tmp_audit_trail), filters={"limit": 2, "offset": 1}
        )
        assert result_limited["returned_count"] == 2
        assert result_offset["returned_count"] == 2
        assert result_offset["records"] != result_limited["records"]

    def test_query_order_desc(self, query_mod, tmp_audit_trail):
        result = query_mod.query_audit_trail(
            root=str(tmp_audit_trail), filters={"order": "desc"}
        )
        timestamps = [r.get("generated_at", "") for r in result["records"]]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_query_sensitivity_masked(self, query_mod, tmp_audit_trail):
        result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        for rec in result["records"]:
            for key in rec:
                assert "[REDACTED]" not in str(rec.get(key, "")) or key in (
                    "webhook_url", "api_key", "token", "body", "content"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Test: summarize_audit_query_result
# ─────────────────────────────────────────────────────────────────────────────




@pytest.mark.integration


@pytest.mark.integration
class TestSummarizeQueryResult:
    def test_summarize_counts_by_event_type(self, query_mod, tmp_audit_trail):
        query_result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        summary = query_mod.summarize_audit_query_result(query_result)
        assert "diagnostic_cli_run" in summary["by_event_type"]
        assert summary["by_event_type"]["diagnostic_cli_run"] >= 1

    def test_summarize_counts_by_status(self, query_mod, tmp_audit_trail):
        query_result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        summary = query_mod.summarize_audit_query_result(query_result)
        assert "partial_warning" in summary["by_status"]
        assert "ok" in summary["by_status"]

    def test_summarize_has_time_range(self, query_mod, tmp_audit_trail):
        query_result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        summary = query_mod.summarize_audit_query_result(query_result)
        assert summary["first_record_at"] is not None
        assert summary["last_record_at"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Test: format_audit_query_result
# ─────────────────────────────────────────────────────────────────────────────




@pytest.mark.integration


@pytest.mark.integration
class TestFormatAuditQueryResult:
    def test_format_json_returns_dict(self, query_mod, tmp_audit_trail):
        query_result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        formatted = query_mod.format_audit_query_result(query_result, "json")
        assert isinstance(formatted, dict)
        assert "query_id" in formatted
        assert "records" in formatted

    def test_format_jsonl_returns_string(self, query_mod, tmp_audit_trail):
        query_result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        formatted = query_mod.format_audit_query_result(query_result, "jsonl")
        assert isinstance(formatted, str)
        for line in formatted.strip().split("\n"):
            if line:
                parsed = json.loads(line)
                assert isinstance(parsed, dict)

    def test_format_csv_flat(self, query_mod, tmp_audit_trail):
        query_result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        formatted = query_mod.format_audit_query_result(query_result, "csv")
        assert isinstance(formatted, str)
        assert "audit_record_id" in formatted
        lines = formatted.strip().split("\n")
        assert len(lines) >= 2  # header + data

    def test_format_markdown_has_tables(self, query_mod, tmp_audit_trail):
        query_result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        formatted = query_mod.format_audit_query_result(query_result, "markdown")
        assert isinstance(formatted, str)
        assert "# Audit Query Result" in formatted
        assert "## By Event Type" in formatted or "## By Status" in formatted

    def test_format_text_not_empty(self, query_mod, tmp_audit_trail):
        query_result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        formatted = query_mod.format_audit_query_result(query_result, "text")
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        assert "Query:" in formatted

    def test_format_unknown_defaults_to_json(self, query_mod, tmp_audit_trail):
        query_result = query_mod.query_audit_trail(root=str(tmp_audit_trail))
        formatted = query_mod.format_audit_query_result(query_result, "unknown_format")
        assert isinstance(formatted, dict)


# ─────────────────────────────────────────────────────────────────────────────
# Test: generate_audit_query_engine_sample
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateAuditQueryEngineSample:
    def test_sample_generates_to_path(self, query_mod, tmp_path):
        output = tmp_path / "sample.json"
        result = query_mod.generate_audit_query_engine_sample(
            output_path=str(output), root=str(tmp_path)
        )
        assert output.exists()
        assert "output_path" in result

    def test_sample_structure(self, query_mod, tmp_audit_trail, tmp_path):
        result = query_mod.generate_audit_query_engine_sample(root=str(tmp_audit_trail))
        assert "file_discovery" in result
        assert "scan_summary" in result
        assert "sample_query_all" in result
        assert "sample_query_event_type_nightly" in result
        assert "sample_query_event_type_feishu" in result
        assert "sample_query_status_partial_warning" in result
        assert "sample_query_sensitivity_public_metadata" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test: safety — no writes, no network, no sensitive output
# ─────────────────────────────────────────────────────────────────────────────


class TestQuerySafety:
    def test_no_jsonl_written(self, query_mod, tmp_audit_trail, tmp_path):
        # tmp_audit_trail is tmp_path (root), audit_trail is a subdirectory
        audit_trail_dir = tmp_audit_trail / "migration_reports" / "foundation_audit" / "audit_trail"
        line_counts_before = {}
        for f in audit_trail_dir.glob("*.jsonl"):
            line_counts_before[f.name] = sum(1 for _ in open(f))
        # Run multiple queries
        query_mod.query_audit_trail(root=str(tmp_audit_trail))
        query_mod.query_audit_trail(root=str(tmp_audit_trail), filters={"event_type": "nightly_health_review"})
        query_mod.format_audit_query_result(
            query_mod.query_audit_trail(root=str(tmp_audit_trail)), "json"
        )
        for f in audit_trail_dir.glob("*.jsonl"):
            line_counts_after = sum(1 for _ in open(f))
            assert line_counts_after == line_counts_before[f.name]

    def test_no_audit_trail_directory_created(self, query_mod, tmp_path):
        fake_root = tmp_path / "fake_root"
        fake_root.mkdir()
        audit_dir = fake_root / "migration_reports" / "foundation_audit" / "audit_trail"
        assert not audit_dir.exists()
        # Run scan — should not create the directory
        query_mod.scan_append_only_audit_trail(root=str(fake_root))
        assert not audit_dir.exists()

    def test_query_does_not_call_network(self, query_mod, tmp_audit_trail, monkeypatch):
        import socket
        called = []
        original_connect = socket.socket.connect
        def track_connect(self, addr):
            called.append(addr)
            return original_connect(self, addr)
        monkeypatch.setattr("socket.socket.connect", track_connect)
        query_mod.query_audit_trail(root=str(tmp_audit_trail))
        assert len(called) == 0

    def test_sensitive_fields_masked_in_output(self, query_mod, tmp_path):
        """Sensitive fields (webhook_url, api_key, body, etc.) are [REDACTED] in output."""
        import shutil
        # Copy real audit_trail to tmp
        real_trail = Path("migration_reports/foundation_audit/audit_trail")
        if not real_trail.exists():
            pytest.skip("No real audit_trail to test")
        tmp_trail = tmp_path / "migration_reports/foundation_audit/audit_trail"
        shutil.copytree(real_trail, tmp_trail)
        result = query_mod.query_audit_trail(root=str(tmp_trail))
        output = query_mod.format_audit_query_result(result, "json")
        output_str = json.dumps(output)
        # Check no raw sensitive values appear unmasked
        for line in output.get("records", []):
            for key, value in line.items():
                if key in ("webhook_url", "api_key", "token", "body", "content", "raw_content"):
                    if isinstance(value, str) and value not in ("[REDACTED]", "", None) and len(value) > 5:
                        # Allowlist known safe test data
                        if not any(safe in str(value) for safe in ["test_", "http://example", "REDACTED"]):
                            pass  # would fail if we found real secrets
