"""Tests for RTCM dry-run roundtable runtime.

No .deerflow/rtcm access, no token_cache.json, no network, no credentials.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.rtcm import (
    ConsensusResult,
    CouncilMember,
    DecisionRecord,
    RoundtableRequest,
    RTCMDecisionStore,
    Vote,
    build_council,
    build_decision_record,
    build_default_council,
    build_json_report,
    build_markdown_report,
    cast_dry_run_votes,
    compute_majority_consensus,
    execute_rtcm_dry_run,
    mode_decision_to_roundtable_request,
)

# =============================================================================
# Models
# =============================================================================


class TestModels:
    def test_council_member_to_dict_roundtrip(self):
        m = CouncilMember(id="test", name="Test Member", role="reviewer", weight=2.0)
        d = m.to_dict()
        r = CouncilMember.from_dict(d)
        assert r.id == m.id
        assert r.name == m.name
        assert r.role == m.role
        assert r.weight == m.weight

    def test_roundtable_request_new_generates_uuid(self):
        r1 = RoundtableRequest.new(topic="A", reason="B")
        r2 = RoundtableRequest.new(topic="A", reason="B")
        assert r1.id != r2.id

    def test_roundtable_request_to_dict_roundtrip(self):
        r = RoundtableRequest.new(topic="topic", reason="reason", dry_run=False)
        d = r.to_dict()
        r2 = RoundtableRequest.from_dict(d)
        assert r2.id == r.id
        assert r2.topic == r.topic
        assert r2.dry_run is False

    def test_vote_to_dict_roundtrip(self):
        v = Vote(member_id="m1", decision="approve", rationale="looks good", weight=1.5)
        d = v.to_dict()
        v2 = Vote.from_dict(d)
        assert v2.member_id == v.member_id
        assert v2.decision == v.decision
        assert v2.rationale == v.rationale
        assert v2.weight == v.weight

    def test_consensus_result_to_dict_roundtrip(self):
        votes = [Vote(member_id="m1", decision="yes", rationale="ok", weight=1.0)]
        c = ConsensusResult(
            request_id="r1",
            strategy="majority_weighted",
            decision="yes",
            confidence=0.8,
            votes=votes,
            dry_run=True,
            warnings=["warn1"],
        )
        d = c.to_dict()
        c2 = ConsensusResult.from_dict(d)
        assert c2.request_id == c.request_id
        assert c2.decision == c.decision
        assert len(c2.votes) == 1
        assert c2.warnings == ["warn1"]

    def test_decision_record_to_dict_roundtrip(self):
        req = RoundtableRequest.new(topic="t", reason="r")
        members = [CouncilMember(id="a", name="A", role="x")]
        votes = [Vote(member_id="a", decision="yes", rationale="ok", weight=1.0)]
        consensus = ConsensusResult(
            request_id=req.id,
            strategy="majority_weighted",
            decision="yes",
            confidence=1.0,
            votes=votes,
            dry_run=True,
        )
        record = DecisionRecord(request=req, members=members, consensus=consensus)
        d = record.to_dict()
        r2 = DecisionRecord.from_dict(d)
        assert r2.request.id == req.id
        assert len(r2.members) == 1
        assert r2.consensus.decision == "yes"


# =============================================================================
# Council
# =============================================================================


class TestCouncil:
    def test_build_default_council(self):
        council = build_default_council()
        assert len(council) == 3
        ids = {m.id for m in council}
        assert "architect" in ids
        assert "safety_reviewer" in ids
        assert "implementation_reviewer" in ids

    def test_build_custom_council(self):
        custom = [CouncilMember(id="c1", name="Custom", role="extra")]
        result = build_council(custom)
        assert result == custom
        assert len(result) == 1

    def test_build_council_with_none_returns_default(self):
        result = build_council(None)
        assert len(result) == 3

    def test_council_weights_are_one(self):
        council = build_default_council()
        for m in council:
            assert m.weight == 1.0


# =============================================================================
# Vote
# =============================================================================


class TestVote:
    def test_cast_dry_run_votes_is_deterministic(self):
        req = RoundtableRequest.new(topic="test topic", reason="testing")
        v1 = cast_dry_run_votes(req, None)
        v2 = cast_dry_run_votes(req, None)
        assert len(v1) == len(v2)
        assert all(a.decision == b.decision for a, b in zip(v1, v2))

    def test_cast_dry_run_votes_count_matches_council(self):
        req = RoundtableRequest.new(topic="test", reason="reason")
        custom = [CouncilMember(id="x", name="X", role="y")]
        votes = cast_dry_run_votes(req, custom)
        assert len(votes) == 1

    def test_cast_dry_run_votes_contain_approve_decision(self):
        req = RoundtableRequest.new(topic="t", reason="r")
        votes = cast_dry_run_votes(req, None)
        assert all(v.decision == "approve_dry_run" for v in votes)

    def test_cast_dry_run_votes_mention_no_external_agents(self):
        req = RoundtableRequest.new(topic="t", reason="r")
        votes = cast_dry_run_votes(req, None)
        for v in votes:
            assert "dry-run" in v.rationale.lower() or "no external" in v.rationale.lower()


# =============================================================================
# Consensus
# =============================================================================


class TestConsensus:
    def test_compute_majority_consensus_single_decision(self):
        req = RoundtableRequest.new(topic="t", reason="r")
        votes = [
            Vote(member_id="m1", decision="yes", rationale="ok", weight=1.0),
            Vote(member_id="m2", decision="yes", rationale="ok", weight=1.0),
            Vote(member_id="m3", decision="no", rationale="not ok", weight=1.0),
        ]
        result = compute_majority_consensus(req, votes)
        assert result.decision == "yes"
        assert result.confidence == pytest.approx(2 / 3)

    def test_compute_consensus_no_votes(self):
        req = RoundtableRequest.new(topic="t", reason="r")
        result = compute_majority_consensus(req, [])
        assert result.decision == "no_votes"
        assert result.confidence == 0.0
        assert len(result.warnings) == 2

    def test_compute_consensus_warnings_present(self):
        req = RoundtableRequest.new(topic="t", reason="r")
        votes = [Vote(member_id="m1", decision="x", rationale="y", weight=1.0)]
        result = compute_majority_consensus(req, votes)
        assert len(result.warnings) == 2
        assert any("operational logs" in w for w in result.warnings)
        assert any("external messages" in w for w in result.warnings)

    def test_compute_consensus_weighted(self):
        req = RoundtableRequest.new(topic="t", reason="r")
        votes = [
            Vote(member_id="m1", decision="yes", rationale="ok", weight=3.0),
            Vote(member_id="m2", decision="no", rationale="not ok", weight=1.0),
        ]
        result = compute_majority_consensus(req, votes)
        assert result.decision == "yes"
        assert result.confidence == pytest.approx(0.75)


# =============================================================================
# Reporter
# =============================================================================


class TestReporter:
    def test_build_decision_record(self):
        req = RoundtableRequest.new(topic="t", reason="r")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        assert record.request == req
        assert record.members == members
        assert record.consensus == consensus
        assert record.status == "dry_run"

    def test_build_markdown_report(self):
        req = RoundtableRequest.new(topic="Test Topic", reason="test reason")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        md = build_markdown_report(record)
        assert "# RTCM Roundtable Decision Report" in md
        assert "Test Topic" in md
        assert "architect" in md
        assert "approve_dry_run" in md

    def test_build_json_report(self):
        req = RoundtableRequest.new(topic="t", reason="r")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        j = build_json_report(record)
        assert isinstance(j, dict)
        assert j["request"]["topic"] == "t"
        assert j["status"] == "dry_run"

    def test_build_markdown_index_empty(self):
        from app.rtcm import build_markdown_index

        md = build_markdown_index([])
        assert "# RTCM Roundtable Decision Index" in md
        assert "*No records.*" in md

    def test_build_markdown_index_single_record(self):
        from app.rtcm import build_markdown_index

        req = RoundtableRequest.new(topic="Test Topic", reason="test reason")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        md = build_markdown_index([record])
        assert "# RTCM Roundtable Decision Index" in md
        assert "Test Topic" in md
        assert "**Count**: 1" in md

    def test_build_json_index_multiple_records(self):
        from app.rtcm import build_json_index

        records = []
        for i in range(3):
            req = RoundtableRequest.new(topic=f"Topic-{i}", reason=f"Reason-{i}")
            members = build_default_council()
            votes = cast_dry_run_votes(req, members)
            consensus = compute_majority_consensus(req, votes)
            record = build_decision_record(req, members, votes, consensus)
            records.append(record)

        idx = build_json_index(records)
        assert idx["count"] == 3
        assert len(idx["request_ids"]) == 3
        assert all(s == "dry_run" for s in idx["statuses"])
        assert idx["dry_run"] is True
        assert len(idx["records"]) == 3


# =============================================================================
# Store
# =============================================================================


class TestStore:
    def test_store_append_and_list_records(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)

        req = RoundtableRequest.new(topic="t1", reason="r1")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        store.append(record)

        records = store.list_records()
        assert len(records) == 1
        assert records[0].request.topic == "t1"

    def test_store_clear(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)

        req = RoundtableRequest.new(topic="t", reason="r")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        store.append(record)
        store.clear()

        assert store.list_records() == []

    def test_store_list_empty_when_no_file(self, tmp_path):
        store_path = tmp_path / "nonexistent.jsonl"
        store = RTCMDecisionStore(store_path)
        assert store.list_records() == []

    def test_store_get_record_by_id(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)

        req = RoundtableRequest.new(topic="t1", reason="r1")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        store.append(record)

        found = store.get(record.request.id)
        assert found is not None
        assert found.request.topic == "t1"

    def test_store_get_unknown_id_returns_none(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)
        assert store.get("nonexistent-id") is None

    def test_store_latest_record(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)

        for i in range(3):
            req = RoundtableRequest.new(topic=f"topic-{i}", reason=f"reason-{i}")
            members = build_default_council()
            votes = cast_dry_run_votes(req, members)
            consensus = compute_majority_consensus(req, votes)
            record = build_decision_record(req, members, votes, consensus)
            store.append(record)

        latest = store.latest()
        assert latest is not None
        assert latest.request.topic == "topic-2"

    def test_store_latest_when_empty(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)
        assert store.latest() is None

    def test_store_list_records_limit(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)

        for i in range(5):
            req = RoundtableRequest.new(topic=f"topic-{i}", reason=f"reason-{i}")
            members = build_default_council()
            votes = cast_dry_run_votes(req, members)
            consensus = compute_majority_consensus(req, votes)
            record = build_decision_record(req, members, votes, consensus)
            store.append(record)

        records = store.list_records(limit=3)
        # Most-recent-first
        assert len(records) == 3
        assert records[0].request.topic == "topic-4"

    def test_store_list_records_limit_zero(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)

        req = RoundtableRequest.new(topic="t", reason="r")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        store.append(record)

        records = store.list_records(limit=0)
        assert len(records) == 1  # limit=0 means no limit

    def test_store_export_json(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)

        req = RoundtableRequest.new(topic="t1", reason="r1")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        store.append(record)

        out_path = tmp_path / "export.json"
        result = store.export_json(out_path)

        assert result == out_path.resolve()
        import json

        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["request"]["topic"] == "t1"

    def test_store_export_json_with_limit(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)

        for i in range(3):
            req = RoundtableRequest.new(topic=f"topic-{i}", reason=f"reason-{i}")
            members = build_default_council()
            votes = cast_dry_run_votes(req, members)
            consensus = compute_majority_consensus(req, votes)
            record = build_decision_record(req, members, votes, consensus)
            store.append(record)

        out_path = tmp_path / "export.json"
        store.export_json(out_path, limit=2)

        import json

        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert len(data) == 2

    def test_store_export_markdown(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)

        req = RoundtableRequest.new(topic="Test Topic", reason="test reason")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        store.append(record)

        out_path = tmp_path / "report.md"
        result = store.export_markdown(out_path)

        assert result == out_path.resolve()
        text = out_path.read_text(encoding="utf-8")
        assert "# RTCM Roundtable Decision Index" in text
        assert "Test Topic" in text

    def test_store_malformed_line_skipped(self, tmp_path):
        import json

        store_path = tmp_path / "decisions.jsonl"
        # First line is valid, second is malformed, third is valid
        req1 = RoundtableRequest.new(topic="valid1", reason="r1")
        members = build_default_council()
        votes = cast_dry_run_votes(req1, members)
        consensus = compute_majority_consensus(req1, votes)
        record1 = build_decision_record(req1, members, votes, consensus)
        req2 = RoundtableRequest.new(topic="valid2", reason="r2")
        votes2 = cast_dry_run_votes(req2, members)
        consensus2 = compute_majority_consensus(req2, votes2)
        record2 = build_decision_record(req2, members, votes2, consensus2)
        lines = [
            json.dumps(record1.to_dict(), ensure_ascii=False),
            "{broken json",
            json.dumps(record2.to_dict(), ensure_ascii=False),
        ]
        store_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        store = RTCMDecisionStore(store_path)
        records = store.list_records()

        assert len(records) == 2

    def test_store_export_creates_parent_dirs(self, tmp_path):
        store_path = tmp_path / "decisions.jsonl"
        store = RTCMDecisionStore(store_path)

        req = RoundtableRequest.new(topic="t", reason="r")
        members = build_default_council()
        votes = cast_dry_run_votes(req, members)
        consensus = compute_majority_consensus(req, votes)
        record = build_decision_record(req, members, votes, consensus)
        store.append(record)

        nested = tmp_path / "nested" / "deep" / "export.json"
        store.export_json(nested)

        assert nested.exists()


# =============================================================================
# Integration
# =============================================================================


class TestIntegration:
    def test_returns_request_for_roundtable_mode(self):
        mode_result = MagicMock()
        mode_result.selected_mode = "ROUNDTABLE"
        mode_result.delegated_to = None
        mode_result.reason = "roundtable handoff"

        req = mode_decision_to_roundtable_request(mode_result)
        assert req is not None
        assert req.topic == "OpenClaw roundtable dry-run review"

    def test_returns_request_for_rtcm_delegation(self):
        mode_result = MagicMock()
        mode_result.selected_mode = "DELEGATED"
        mode_result.delegated_to = "RTCM_MAIN_AGENT_HANDOFF"
        mode_result.reason = "agent handoff"

        req = mode_decision_to_roundtable_request(mode_result)
        assert req is not None

    def test_returns_none_for_non_rtcm_mode(self):
        mode_result = MagicMock()
        mode_result.selected_mode = "DIRECT"
        mode_result.delegated_to = None

        req = mode_decision_to_roundtable_request(mode_result)
        assert req is None

    def test_returns_none_for_dict_roundtable(self):
        mode_result = {"selected_mode": "ROUNDTABLE", "delegated_to": None}

        req = mode_decision_to_roundtable_request(mode_result)
        assert req is not None

    def test_execute_rtcm_dry_run_returns_record(self):
        req = RoundtableRequest.new(topic="test", reason="testing")
        record = execute_rtcm_dry_run(req)
        assert isinstance(record, DecisionRecord)
        assert record.status == "dry_run"
        assert len(record.members) == 3
        assert len(record.consensus.votes) == 3


# =============================================================================
# Safety / Security
# =============================================================================


class TestSafety:
    def test_no_rtcm_operational_data_access(self, monkeypatch):
        """Verify the rtcm package does not read .deerflow/rtcm."""
        import app.rtcm  # noqa: F401

        opened_paths: list[str] = []

        def track_open(path, *args, **kwargs):
            opened_paths.append(str(path))
            raise FileNotFoundError("blocked")

        monkeypatch.setattr("builtins.open", track_open)
        # Re-import to catch any at-import reads (none expected)
        import importlib

        importlib.reload(importlib.import_module("app.rtcm.models"))
        importlib.reload(importlib.import_module("app.rtcm"))

        for p in opened_paths:
            assert ".deerflow/rtcm" not in p

    def test_no_token_cache_access(self, monkeypatch):
        """Verify no token_cache.json access."""
        opened_paths: list[str] = []

        def track_open(path, *args, **kwargs):
            opened_paths.append(str(path))
            raise FileNotFoundError("blocked")

        monkeypatch.setattr("builtins.open", track_open)
        import importlib

        importlib.reload(importlib.import_module("app.rtcm"))

        for p in opened_paths:
            assert "token_cache" not in p.lower()

    def test_no_external_network_or_credentials_required(self):
        """Verify dry-run execution works without any credentials."""
        req = RoundtableRequest.new(topic="t", reason="r")
        record = execute_rtcm_dry_run(req)
        assert record.status == "dry_run"
        # No credentials, no network — just pure computation
        assert len(record.consensus.warnings) >= 2

    def test_no_feishu_send_called(self, monkeypatch):
        """Verify FeishuChannel.send is not called during dry-run."""
        mock_send = MagicMock()
        monkeypatch.setattr("app.channels.feishu.FeishuChannel.send", mock_send)

        req = RoundtableRequest.new(topic="t", reason="r")
        execute_rtcm_dry_run(req)

        mock_send.assert_not_called()
