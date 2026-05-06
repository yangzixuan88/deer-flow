from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from app.nightly_review import (
    NightlyReviewItem,
    NightlyReviewReporter,
    NightlyReviewScheduler,
    NightlyReviewStore,
)

# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


@pytest.fixture
def tmp_store(tmp_path: Path) -> NightlyReviewStore:
    return NightlyReviewStore(storage_path=tmp_path / "store.jsonl")


@pytest.fixture
def reporter() -> NightlyReviewReporter:
    return NightlyReviewReporter()


@pytest.fixture
def scheduler(tmp_store: NightlyReviewStore, reporter: NightlyReviewReporter) -> NightlyReviewScheduler:
    return NightlyReviewScheduler(tmp_store, reporter)


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


# -------------------------------------------------------------------------
# Test 1: import has no side effects
# -------------------------------------------------------------------------


def test_scheduler_import_has_no_side_effects() -> None:
    before = threading.enumerate()
    from app.nightly_review import scheduler as sched_module  # noqa: F401

    after = threading.enumerate()
    new_threads = [t for t in after if t not in before]
    assert len(new_threads) == 0, f"Import started threads: {[t.name for t in new_threads]}"


# -------------------------------------------------------------------------
# Test 2: build_review_payload reads pending items
# -------------------------------------------------------------------------


def test_build_review_payload_reads_pending_items(
    scheduler: NightlyReviewScheduler,
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
) -> None:
    tmp_store.append(sample_item)

    payload = scheduler.build_review_payload()

    assert payload.total == 1
    assert payload.pending == 1
    assert payload.items[0].id == sample_item.id


# -------------------------------------------------------------------------
# Test 3: build_review_payload respects limit
# -------------------------------------------------------------------------


def test_build_review_payload_respects_limit(
    scheduler: NightlyReviewScheduler,
    tmp_store: NightlyReviewStore,
) -> None:
    for i in range(5):
        tmp_store.append(
            NightlyReviewItem.new(
                mode="test",
                reason=f"reason-{i}",
                source="test",
            )
        )

    payload = scheduler.build_review_payload(limit=3)

    assert payload.total == 3


# -------------------------------------------------------------------------
# Test 4: build_markdown_report
# -------------------------------------------------------------------------


def test_build_markdown_report(
    scheduler: NightlyReviewScheduler,
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
) -> None:
    tmp_store.append(sample_item)

    report = scheduler.build_markdown_report()

    assert isinstance(report, str)
    assert "Nightly Review Report" in report
    assert "autonomous_agent" in report
    assert "autonomous keyword match" in report


# -------------------------------------------------------------------------
# Test 5: export_markdown_report writes to explicit path
# -------------------------------------------------------------------------


def test_export_markdown_report_writes_explicit_path(
    scheduler: NightlyReviewScheduler,
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
    tmp_path: Path,
) -> None:
    tmp_store.append(sample_item)

    output_path = tmp_path / "report.md"
    result = scheduler.export_markdown_report(output_path)

    assert result == output_path.resolve()
    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "Nightly Review Report" in text


# -------------------------------------------------------------------------
# Test 6: run_once does not mark reviewed by default
# -------------------------------------------------------------------------


def test_run_once_does_not_mark_reviewed_by_default(
    scheduler: NightlyReviewScheduler,
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
) -> None:
    item_id = tmp_store.append(sample_item)

    payload = scheduler.run_once()

    assert payload.items[0].status == "pending"
    pending = tmp_store.list_pending()
    assert len(pending) == 1
    assert pending[0].id == item_id


# -------------------------------------------------------------------------
# Test 7: run_once can mark reviewed when explicit
# -------------------------------------------------------------------------


def test_run_once_can_mark_reviewed_when_explicit(
    scheduler: NightlyReviewScheduler,
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
) -> None:
    _ = tmp_store.append(sample_item)

    payload = scheduler.run_once(mark_reviewed=True)

    assert payload.items[0].status == "pending"
    pending = tmp_store.list_pending()
    assert len(pending) == 0


# -------------------------------------------------------------------------
# Test 8: scheduler does not call feishu send
# -------------------------------------------------------------------------


def test_scheduler_does_not_call_feishu_send(
    scheduler: NightlyReviewScheduler,
    tmp_store: NightlyReviewStore,
    sample_item: NightlyReviewItem,
) -> None:
    tmp_store.append(sample_item)

    with patch("app.channels.feishu.FeishuChannel.send") as mock_send:
        scheduler.build_review_payload()
        scheduler.build_markdown_report()
        scheduler.run_once()
        mock_send.assert_not_called()


# -------------------------------------------------------------------------
# Test 9: scheduler does not read rtcm token path
# -------------------------------------------------------------------------


def test_scheduler_does_not_read_rtcm_token_path(
    tmp_store: NightlyReviewStore,
    reporter: NightlyReviewReporter,
    tmp_path: Path,
) -> None:
    checked_paths: list[str] = []

    original_exists = Path.exists

    def tracked_exists(self: Path) -> bool:
        checked_paths.append(str(self))
        return original_exists(self)

    with patch.object(Path, "exists", tracked_exists):
        scheduler = NightlyReviewScheduler(tmp_store, reporter)
        scheduler.build_review_payload()

    for p in checked_paths:
        assert ".deerflow/rtcm" not in p, f"Path accessed .deerflow/rtcm/: {p}"


# -------------------------------------------------------------------------
# Test 10: CLI schedule-dry-run does not send
# -------------------------------------------------------------------------


def test_cli_schedule_dry_run_does_not_send(
    tmp_path: Path,
) -> None:
    store = NightlyReviewStore(storage_path=tmp_path / "store.jsonl")
    item = NightlyReviewItem.new(mode="test", reason="test", source="test")
    store.append(item)

    with patch("app.channels.feishu.FeishuChannel.send") as mock_send:
        from app.nightly_review.cli import main as cli_main

        cli_main(["schedule-dry-run", "--store", str(tmp_path / "store.jsonl")])
        mock_send.assert_not_called()


# -------------------------------------------------------------------------
# Test 11: no background thread started on import
# -------------------------------------------------------------------------


def test_no_background_thread_started_on_import(
    tmp_store: NightlyReviewStore,
    reporter: NightlyReviewReporter,
) -> None:
    before = threading.enumerate()

    NightlyReviewScheduler(tmp_store, reporter)

    after = threading.enumerate()
    new_threads = [t for t in after if t not in before]
    assert len(new_threads) == 0, f"Scheduler created threads: {[t.name for t in new_threads]}"


# -------------------------------------------------------------------------
# R239X: Nightly CLI export and run-once hardening
# -------------------------------------------------------------------------


def test_nightly_export_requires_explicit_output(
    tmp_store: NightlyReviewStore,
    reporter: NightlyReviewReporter,
    tmp_path: Path,
) -> None:
    scheduler = NightlyReviewScheduler(tmp_store, reporter)
    out_path = tmp_path / "report.md"
    result = scheduler.export_markdown_report(out_path)
    assert result == out_path.resolve()
    assert out_path.exists()


def test_nightly_export_writes_markdown(
    tmp_store: NightlyReviewStore,
    reporter: NightlyReviewReporter,
    sample_item: NightlyReviewItem,
    tmp_path: Path,
) -> None:
    tmp_store.append(sample_item)
    scheduler = NightlyReviewScheduler(tmp_store, reporter)
    out_path = tmp_path / "report.md"
    scheduler.export_markdown_report(out_path)
    text = out_path.read_text(encoding="utf-8")
    assert "Nightly Review Report" in text
    assert "autonomous_agent" in text


def test_nightly_run_once_preview_does_not_mark_reviewed(
    tmp_store: NightlyReviewStore,
    reporter: NightlyReviewReporter,
    sample_item: NightlyReviewItem,
) -> None:
    tmp_store.append(sample_item)
    scheduler = NightlyReviewScheduler(tmp_store, reporter)
    payload = scheduler.run_once(limit=None, mark_reviewed=False)
    assert payload.items[0].status == "pending"
    pending = tmp_store.list_pending()
    assert len(pending) == 1


def test_nightly_cli_real_send_still_rejected(
    tmp_path: Path,
) -> None:
    from app.nightly_review.cli import main as cli_main

    with pytest.raises(NotImplementedError, match="--real"):
        cli_main(["send", "--real"])


def test_nightly_cli_no_daemon_started(
    tmp_path: Path,
) -> None:
    from app.nightly_review.cli import main as cli_main

    before = threading.enumerate()
    cli_main(["schedule-dry-run", "--store", str(tmp_path / "store.jsonl")])
    after = threading.enumerate()
    new_threads = [t for t in after if t not in before]
    assert len(new_threads) == 0


def test_nightly_cli_requires_explicit_store_for_export(
    tmp_path: Path,
    sample_item: NightlyReviewItem,
) -> None:
    from app.nightly_review.cli import main as cli_main

    store = NightlyReviewStore(storage_path=tmp_path / "store.jsonl")
    store.append(sample_item)

    cli_main(["export", "--path", str(tmp_path / "export.jsonl"), "--output", str(tmp_path / "report.md")])
    assert (tmp_path / "report.md").exists()
