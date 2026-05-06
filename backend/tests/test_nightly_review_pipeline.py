from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from app.nightly_review import (
    NightlyReviewItem,
    NightlyReviewReporter,
    NightlyReviewStore,
    ReviewPayload,
    mode_decision_to_review_item,
)

# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


@pytest.fixture
def tmp_store(tmp_path: Path) -> NightlyReviewStore:
    return NightlyReviewStore(storage_path=tmp_path / "store.jsonl")


@pytest.fixture
def sample_item() -> NightlyReviewItem:
    return NightlyReviewItem.new(
        thread_id="thread-abc",
        run_id="run-123",
        user_id="user-1",
        mode="autonomous_agent",
        reason="autonomous keyword match",
        source="mode_router",
        payload_summary="keep working on the analysis",
    )


@pytest.fixture
def another_item() -> NightlyReviewItem:
    return NightlyReviewItem.new(
        thread_id="thread-xyz",
        run_id="run-456",
        user_id="user-2",
        mode="autonomous_agent",
        reason="autonomous keyword match",
        source="explicit_flag",
        payload_summary="monitor the pipeline status",
    )


# -------------------------------------------------------------------------
# Test 1: import has no side effects
# -------------------------------------------------------------------------


def test_import_has_no_side_effects() -> None:
    before = threading.enumerate()
    from app import nightly_review as nr_module  # noqa: F401

    after = threading.enumerate()
    new_threads = [t for t in after if t not in before]
    assert len(new_threads) == 0, f"Import started threads: {[t.name for t in new_threads]}"


# -------------------------------------------------------------------------
# Test 2: NightlyReviewItem.new creates valid item
# -------------------------------------------------------------------------


def test_review_item_new_creates_valid_item(sample_item: NightlyReviewItem) -> None:
    assert sample_item.id is not None
    assert len(sample_item.id) == 36
    assert sample_item.mode == "autonomous_agent"
    assert sample_item.reason == "autonomous keyword match"
    assert sample_item.status == "pending"
    assert sample_item.dry_run is True
    assert "keep working" in sample_item.payload_summary


# -------------------------------------------------------------------------
# Test 3: mode_decision_to_review_item returns None when flag is False
# -------------------------------------------------------------------------


def test_no_review_item_when_flag_false() -> None:
    result = mode_decision_to_review_item(
        _make_mode_result(nightly_review=False),
        thread_id="t1",
        run_id="r1",
    )
    assert result is None


# -------------------------------------------------------------------------
# Test 4: mode_decision_to_review_item returns item when flag is True
# -------------------------------------------------------------------------


def test_review_item_from_mode_result_sink() -> None:
    mode_result = _make_mode_result(
        nightly_review=True,
        selected_mode="autonomous_agent",
        decision_reason="autonomous keyword match",
        context_id="thread-abc",
        request_id="run-123",
    )

    item = mode_decision_to_review_item(
        mode_result,
        payload_summary="keep working on the analysis",
    )

    assert item is not None
    assert item.mode == "autonomous_agent"
    assert item.reason == "autonomous keyword match"
    assert item.status == "pending"
    assert item.dry_run is True
    assert item.thread_id == "thread-abc"
    assert item.run_id == "run-123"
    assert "keep working" in item.payload_summary


# -------------------------------------------------------------------------
# Test 5: store append and list pending
# -------------------------------------------------------------------------


def test_store_append_and_list_pending(
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
    another_item: NightlyReviewItem,
) -> None:
    id1 = tmp_store.append(sample_item)
    id2 = tmp_store.append(another_item)

    pending = tmp_store.list_pending()
    assert len(pending) == 2
    ids = {p.id for p in pending}
    assert id1 in ids
    assert id2 in ids


# -------------------------------------------------------------------------
# Test 6: store mark reviewed
# -------------------------------------------------------------------------


def test_store_mark_reviewed(
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
) -> None:
    item_id = tmp_store.append(sample_item)
    result = tmp_store.mark_reviewed(item_id)

    assert result is True
    pending = tmp_store.list_pending()
    assert item_id not in {p.id for p in pending}


# -------------------------------------------------------------------------
# Test 7: store clear
# -------------------------------------------------------------------------


def test_store_clear(
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
    another_item: NightlyReviewItem,
) -> None:
    tmp_store.append(sample_item)
    tmp_store.append(another_item)

    count = tmp_store.clear()

    assert count == 2
    assert tmp_store.list_pending() == []


# -------------------------------------------------------------------------
# Test 8: reporter builds dry-run payload
# -------------------------------------------------------------------------


def test_reporter_builds_dry_run_payload(
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
    another_item: NightlyReviewItem,
) -> None:
    tmp_store.append(sample_item)
    tmp_store.append(another_item)

    reporter = NightlyReviewReporter()
    pending = tmp_store.list_pending()
    payload = reporter.build_payload(pending, dry_run=True)

    assert isinstance(payload, ReviewPayload)
    assert payload.total == 2
    assert payload.pending == 2
    assert payload.reviewed == 0
    assert payload.dry_run is True
    assert len(payload.items) == 2


# -------------------------------------------------------------------------
# Test 9: reporter does NOT call feishu send by default
# -------------------------------------------------------------------------


def test_reporter_does_not_call_feishu_send_by_default(
    tmp_path: Path,
) -> None:
    with patch("app.channels.feishu.FeishuChannel.send") as mock_send:
        reporter = NightlyReviewReporter()
        item = NightlyReviewItem.new(
            mode="autonomous_agent",
            reason="test",
            source="test",
        )
        payload = reporter.build_payload([item], dry_run=True)
        reporter.build_feishu_card_payload(payload)
        mock_send.assert_not_called()


# -------------------------------------------------------------------------
# Test 10: missing credentials do not fail dry-run
# -------------------------------------------------------------------------


def test_missing_credentials_do_not_fail_dry_run(
    tmp_path: Path,
) -> None:
    store = NightlyReviewStore(storage_path=tmp_path / "store.jsonl")
    item = NightlyReviewItem.new(
        mode="autonomous_agent",
        reason="test",
        source="test",
    )
    store.append(item)

    reporter = NightlyReviewReporter()
    pending = store.list_pending()
    payload = reporter.build_payload(pending, dry_run=True)

    assert payload.total == 1
    assert payload.dry_run is True


# -------------------------------------------------------------------------
# Test 11: no .deerflow/rtcm/ path access
# -------------------------------------------------------------------------


def test_no_rtcm_token_path_access(tmp_path: Path) -> None:
    checked_paths: list[str] = []

    original_exists = Path.exists

    def tracked_exists(self: Path) -> bool:
        checked_paths.append(str(self))
        return original_exists(self)

    with patch.object(Path, "exists", tracked_exists):
        store = NightlyReviewStore(storage_path=tmp_path / "store.jsonl")
        reporter = NightlyReviewReporter()
        item = NightlyReviewItem.new(mode="test", reason="test", source="test")
        store.append(item)
        pending = store.list_pending()
        reporter.build_payload(pending)

    for p in checked_paths:
        assert ".deerflow/rtcm" not in p, f"Path accessed .deerflow/rtcm/: {p}"


# -------------------------------------------------------------------------
# Test 12: real send requires explicit opt-in
# -------------------------------------------------------------------------


def test_real_send_requires_explicit_opt_in(
    tmp_path: Path,
) -> None:
    store = NightlyReviewStore(storage_path=tmp_path / "store.jsonl")
    item = NightlyReviewItem.new(mode="test", reason="test", source="test")
    store.append(item)

    reporter = NightlyReviewReporter()
    pending = store.list_pending()
    reporter.build_payload(pending, dry_run=True)

    with patch("app.channels.feishu.FeishuChannel.send") as mock_send:
        mock_send.return_value = True
        from app.nightly_review.cli import main as cli_main

        cli_main(["send"])
        mock_send.assert_not_called()


# -------------------------------------------------------------------------
# Test 13: CLI dry-run does not send
# -------------------------------------------------------------------------


def test_cli_dry_run_does_not_send(
    tmp_path: Path,
) -> None:
    store = NightlyReviewStore(storage_path=tmp_path / "store.jsonl")
    item = NightlyReviewItem.new(mode="test", reason="test", source="test")
    store.append(item)

    with patch("app.channels.feishu.FeishuChannel.send") as mock_send:
        mock_send.return_value = True
        from app.nightly_review.cli import main as cli_main

        cli_main(["dry-run"])
        mock_send.assert_not_called()


# -------------------------------------------------------------------------
# Test 14: mark_sent works
# -------------------------------------------------------------------------


def test_store_mark_sent(
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
) -> None:
    item_id = tmp_store.append(sample_item)
    result = tmp_store.mark_sent(item_id)

    assert result is True
    pending = tmp_store.list_pending()
    assert item_id not in {p.id for p in pending}


# -------------------------------------------------------------------------
# Test 15: export / import roundtrip
# -------------------------------------------------------------------------


def test_export_import_roundtrip(
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
    another_item: NightlyReviewItem,
    tmp_path: Path,
) -> None:
    tmp_store.append(sample_item)
    tmp_store.append(another_item)

    export_path = tmp_path / "export.jsonl"
    count = tmp_store.export_jsonl(export_path)
    assert count == 2

    new_store = NightlyReviewStore(storage_path=tmp_path / "new_store.jsonl")
    imported = new_store.import_jsonl(export_path)
    assert imported == 2
    assert len(new_store.list_items()) == 2


# -------------------------------------------------------------------------
# Test 16: reporter build_feishu_card_payload returns valid dict
# -------------------------------------------------------------------------


def test_reporter_build_feishu_card_payload(
    tmp_path: Path,
) -> None:
    store = NightlyReviewStore(storage_path=tmp_path / "store.jsonl")
    item = NightlyReviewItem.new(
        mode="autonomous_agent",
        reason="autonomous keyword match",
        source="test",
        payload_summary="keep working",
    )
    store.append(item)

    reporter = NightlyReviewReporter()
    pending = store.list_pending()
    payload = reporter.build_payload(pending, dry_run=True)
    card = reporter.build_feishu_card_payload(payload)

    assert isinstance(card, dict)
    assert card["msg_type"] == "interactive"
    assert "card" in card
    assert "config" in card["card"]
    assert "elements" in card["card"]


# -------------------------------------------------------------------------
# Test 17: store returns empty on missing file
# -------------------------------------------------------------------------


def test_store_empty_on_missing_file(tmp_path: Path) -> None:
    store = NightlyReviewStore(storage_path=tmp_path / "nonexistent.jsonl")
    assert store.list_items() == []
    assert store.list_pending() == []


# -------------------------------------------------------------------------
# Test 18: NightlyReviewItem to_dict / from_dict roundtrip
# -------------------------------------------------------------------------


def test_item_to_dict_from_dict_roundtrip(sample_item: NightlyReviewItem) -> None:
    d = sample_item.to_dict()
    restored = NightlyReviewItem.from_dict(d)
    assert restored.id == sample_item.id
    assert restored.mode == sample_item.mode
    assert restored.status == sample_item.status


# -------------------------------------------------------------------------
# Helper
# -------------------------------------------------------------------------


def _make_mode_result(
    nightly_review: bool = False,
    selected_mode: str = "direct_answer",
    decision_reason: str = "",
    context_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Build a minimal dict that looks like a serialized ModeDecision."""
    return {
        "selected_mode": selected_mode,
        "decision_reason": decision_reason,
        "context_id": context_id,
        "request_id": request_id,
        "created_at": "2026-05-06T00:00:00Z",
        "result_sink": {
            "nightly_review": nightly_review,
            "frontend_thread": True,
            "memory": False,
            "asset": False,
            "governance": False,
            "runtime_artifact": True,
        },
    }
