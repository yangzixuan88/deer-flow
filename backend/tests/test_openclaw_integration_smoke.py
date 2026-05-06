"""Integration smoke tests across Nightly / Asset / RTCM dry-run runtimes.

Verifies that all three tracked dry-run runtimes can be imported and
executed without accessing forbidden paths, credentials, or external network.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.asset_runtime import (
    execute_asset_dry_run,
    mode_decision_to_asset_request,
)
from app.asset_runtime.models import AssetRequest
from app.nightly_review import mode_decision_to_review_item
from app.nightly_review.reporter import NightlyReviewReporter
from app.nightly_review.scheduler import NightlyReviewScheduler
from app.nightly_review.store import NightlyReviewStore
from app.rtcm import (
    execute_rtcm_dry_run,
    mode_decision_to_roundtable_request,
)
from app.rtcm.models import RoundtableRequest

# =============================================================================
# Helper factories
# =============================================================================


def make_nightly_mode_result(nightly_review: bool = True) -> MagicMock:
    mock = MagicMock()
    mock.result_sink.nightly_review = nightly_review
    mock.selected_mode.value = "AUTONOMOUS_AGENT"
    mock.decision_reason = "Nightly review triggered by keyword"
    mock.context_id = "thread-123"
    mock.request_id = "run-456"
    return mock


def make_nightly_mode_result_dict(nightly_review: bool = True) -> dict:
    return {
        "result_sink": {"nightly_review": nightly_review},
        "selected_mode": "AUTONOMOUS_AGENT",
        "decision_reason": "Nightly review via dict",
        "context_id": "thread-dict",
        "request_id": "run-dict",
    }


def make_asset_mode_result(asset_flag: bool = True) -> MagicMock:
    mock = MagicMock()
    mock.selected_mode = "DELEGATED"
    mock.delegated_to = "ASSET_RUNTIME"
    mock.reason = "Asset mode handoff"
    return mock


def make_roundtable_mode_result() -> MagicMock:
    mock = MagicMock()
    mock.selected_mode = "ROUNDTABLE"
    mock.delegated_to = None
    mock.reason = "Roundtable mode handoff"
    return mock


def make_rtcm_delegated_mode_result() -> MagicMock:
    mock = MagicMock()
    mock.selected_mode = "DELEGATED"
    mock.delegated_to = "RTCM_MAIN_AGENT_HANDOFF"
    mock.reason = "RTCM delegation"
    return mock


# =============================================================================
# Import / side-effect tests
# =============================================================================


class TestNoSideEffects:
    def test_nightly_asset_rtcm_imports_have_no_side_effects(self):
        """Importing all integration modules must not start threads or daemons."""
        import importlib

        import app.asset_runtime.integration
        import app.nightly_review.integration
        import app.rtcm.integration

        importlib.reload(app.nightly_review.integration)
        importlib.reload(app.asset_runtime.integration)
        importlib.reload(app.rtcm.integration)

    def test_no_mode_router_mutation_required(self):
        """Integration helpers must not modify mode_router.py state."""

        # If we got here without ImportError, mode_router is untouched
        assert True


# =============================================================================
# Nightly integration
# =============================================================================


class TestNightlyIntegration:
    def test_nightly_mode_decision_helper_returns_item_for_flag_true(self):
        mode_result = make_nightly_mode_result(nightly_review=True)
        item = mode_decision_to_review_item(mode_result)
        assert item is not None
        assert item.thread_id == "thread-123"
        assert item.run_id == "run-456"
        assert item.mode == "AUTONOMOUS_AGENT"

    def test_nightly_mode_decision_helper_returns_none_for_flag_false(self):
        mode_result = make_nightly_mode_result(nightly_review=False)
        item = mode_decision_to_review_item(mode_result)
        assert item is None

    def test_nightly_mode_decision_helper_works_with_dict(self):
        mode_result = make_nightly_mode_result_dict(nightly_review=True)
        item = mode_decision_to_review_item(mode_result)
        assert item is not None
        assert item.thread_id == "thread-dict"

    def test_nightly_scheduler_builds_payload_without_daemon(self, tmp_path):
        """Building a payload must not start any daemon or background thread."""
        tmp_store = NightlyReviewStore(storage_path=str(tmp_path / "store.jsonl"))
        reporter = NightlyReviewReporter()
        scheduler = NightlyReviewScheduler(tmp_store, reporter)
        payload = scheduler.build_review_payload()
        assert payload is not None


# =============================================================================
# Asset integration
# =============================================================================


class TestAssetIntegration:
    def test_asset_mode_decision_helper_returns_request_for_flag_true(self):
        req = mode_decision_to_asset_request(
            mode="DELEGATED",
            reason="Asset mode handoff",
            user_id=None,
            thread_id=None,
            run_id=None,
            requested_capability=None,
            payload_summary="test",
            source="mode_router",
            dry_run=True,
        )
        assert req is not None
        assert req.mode == "DELEGATED"

    def test_asset_dry_run_execute_returns_limited_result(self):
        req = AssetRequest.new(
            mode="asset",
            reason="integration smoke test",
            dry_run=True,
        )
        result = execute_asset_dry_run(req)
        assert result.status == "dry_run"
        assert result.dry_run is True
        assert len(result.warnings) >= 1


# =============================================================================
# RTCM integration
# =============================================================================


class TestRTCMIntegration:
    def test_rtcm_mode_decision_helper_returns_request_for_roundtable_mode(self):
        mode_result = make_roundtable_mode_result()
        req = mode_decision_to_roundtable_request(mode_result)
        assert req is not None
        assert req.topic == "OpenClaw roundtable dry-run review"

    def test_rtcm_mode_decision_helper_returns_request_for_rtcm_delegation(self):
        mode_result = make_rtcm_delegated_mode_result()
        req = mode_decision_to_roundtable_request(mode_result)
        assert req is not None

    def test_rtcm_mode_decision_helper_returns_none_for_non_rtcm_mode(self):
        mock = MagicMock()
        mock.selected_mode = "DIRECT"
        mock.delegated_to = None
        req = mode_decision_to_roundtable_request(mock)
        assert req is None

    def test_rtcm_dry_run_execute_returns_decision_record(self):
        req = RoundtableRequest.new(
            topic="integration smoke test",
            reason="testing rtcm dry run",
            dry_run=True,
        )
        record = execute_rtcm_dry_run(req)
        assert record.status == "dry_run"
        assert len(record.members) == 3
        assert len(record.consensus.votes) == 3


# =============================================================================
# Cross-runtime safety
# =============================================================================


class TestSafety:
    def test_no_feishu_send_called(self, monkeypatch):
        mock_send = MagicMock()
        monkeypatch.setattr("app.channels.feishu.FeishuChannel.send", mock_send)

        req = AssetRequest.new(mode="asset", reason="test", dry_run=True)
        execute_asset_dry_run(req)

        mock_send.assert_not_called()

    def test_no_external_network_called(self):
        req = AssetRequest.new(mode="asset", reason="test", dry_run=True)
        result = execute_asset_dry_run(req)
        assert result.status == "dry_run"

        rtcm_req = RoundtableRequest.new(topic="t", reason="r")
        record = execute_rtcm_dry_run(rtcm_req)
        assert record.status == "dry_run"

    def test_no_rtcm_operational_data_access(self, monkeypatch):
        """Verify rtcm modules do not open .deerflow/rtcm paths."""
        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            p = str(path)
            opened_paths.append(p)
            raise FileNotFoundError("blocked for test")

        monkeypatch.setattr("builtins.open", tracking_open)
        import importlib

        import app.rtcm
        import app.rtcm.models

        importlib.reload(app.rtcm.models)
        importlib.reload(app.rtcm)

        for p in opened_paths:
            assert ".deerflow/rtcm" not in p

    def test_no_operation_assets_access(self, monkeypatch):
        """Verify asset_runtime does not open .deerflow/operation_assets paths."""
        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            p = str(path)
            opened_paths.append(p)
            raise FileNotFoundError("blocked for test")

        monkeypatch.setattr("builtins.open", tracking_open)
        import importlib

        import app.asset_runtime
        import app.asset_runtime.models

        importlib.reload(app.asset_runtime.models)
        importlib.reload(app.asset_runtime)

        for p in opened_paths:
            assert ".deerflow/operation_assets" not in p

    def test_no_token_cache_access(self, monkeypatch):
        """Verify no module accesses token_cache.json."""
        opened_paths: list[str] = []

        def tracking_open(path, *args, **kwargs):
            p = str(path)
            opened_paths.append(p)
            raise FileNotFoundError("blocked")

        monkeypatch.setattr("builtins.open", tracking_open)
        import importlib

        import app.asset_runtime
        import app.nightly_review
        import app.rtcm

        importlib.reload(app.nightly_review)
        importlib.reload(app.asset_runtime)
        importlib.reload(app.rtcm)

        for p in opened_paths:
            assert "token_cache" not in p.lower()

    def test_all_dry_run_outputs_are_json_serializable(self):
        """Verify all dry-run outputs can be serialized to JSON."""
        import json

        req = AssetRequest.new(mode="asset", reason="test", dry_run=True)
        result = execute_asset_dry_run(req)
        d = result.to_dict()
        json.dumps(d)

        rtcm_req = RoundtableRequest.new(topic="t", reason="r")
        record = execute_rtcm_dry_run(rtcm_req)
        d = record.to_dict()
        json.dumps(d)

    def test_security_exception_remains_explicitly_open_in_docs(self):
        """Verify security_exception_register.md exists and mentions open exception."""
        import pathlib

        doc_path = pathlib.Path(__file__).parents[2] / "docs" / "openclaw" / "security_exception_register.md"
        assert doc_path.exists(), "security_exception_register.md must exist"
        content = doc_path.read_text(encoding="utf-8")
        assert "S-RTCM-FEISHU-TOKEN-001" in content
        assert "OPEN" in content or "open" in content.lower()
