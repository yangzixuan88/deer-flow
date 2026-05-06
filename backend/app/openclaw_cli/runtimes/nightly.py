"""Nightly runtime wrapper for OpenClaw operator CLI.

Dry-run only — delegates to NightlyReviewScheduler and NightlyReviewReporter
without starting daemons, accessing credentials, or making network calls.
"""

from __future__ import annotations

from pathlib import Path

from app.nightly_review import NightlyReviewReporter, NightlyReviewScheduler, NightlyReviewStore

from ..commands import OperatorCommandResult


def run_nightly_dry_run(
    *,
    store_path: str | Path | None = None,
    limit: int | None = None,
) -> OperatorCommandResult:
    """Run a Nightly Review dry-run.

    Args:
        store_path: Optional path to NightlyReviewStore JSONL.
                    If None, uses empty in-memory pending list.
        limit: Optional limit on number of items to return.

    Returns:
        OperatorCommandResult with dry_run=True and review payload.
    """
    warnings: list[str] = []

    if store_path is not None:
        store = NightlyReviewStore(storage_path=str(store_path))
    else:
        store = NightlyReviewStore(storage_path=":memory:")

    reporter = NightlyReviewReporter()
    scheduler = NightlyReviewScheduler(store=store, reporter=reporter)

    if store_path is not None:
        warnings.append("Using persisted store — dry-run results may persist to store")

    payload = scheduler.build_review_payload(limit=limit)

    return OperatorCommandResult(
        command="nightly-dry-run",
        status="success",
        dry_run=True,
        payload={
            "store_path": str(store_path) if store_path else ":memory:",
            "item_count": len(payload.items) if payload else 0,
            "pending_items": payload.items if payload else [],
        },
        warnings=warnings,
    )


def preview_nightly_schedule() -> OperatorCommandResult:
    """Preview Nightly schedule capability — no daemon, no cron, no real send.

    Returns a capability summary for the Nightly Review manual scheduler.
    """
    return OperatorCommandResult(
        command="nightly-schedule-preview",
        status="success",
        dry_run=True,
        payload={
            "scheduler_type": "manual",
            "daemon_supported": False,
            "dry_run_supported": True,
            "real_send_supported": False,
            "capabilities": [
                "dry-run review pipeline",
                "manual scheduler (CLI-triggered)",
                "JSONL store persistence",
                "capability summary export",
                "explicit store/output required",
            ],
            "limitations": [
                "no background daemon",
                "no automatic cron trigger",
                "real send = NotImplementedError",
            ],
        },
        warnings=[],
    )


def run_nightly_export(
    *,
    store: str | Path | None = None,
    output: str | Path,
    limit: int | None = None,
) -> OperatorCommandResult:
    """Export Nightly Review as a markdown report to an explicit path.

    Args:
        store: Optional explicit path to NightlyReviewStore JSONL.
               If None, uses empty in-memory store.
        output: Required explicit output path for the markdown report.
        limit: Optional limit on number of items.

    Returns:
        OperatorCommandResult with output_path, item_count, dry_run=True.
    """
    if store is not None:
        store_obj = NightlyReviewStore(storage_path=str(store))
    else:
        store_obj = NightlyReviewStore(storage_path=":memory:")

    reporter = NightlyReviewReporter()
    scheduler = NightlyReviewScheduler(store=store_obj, reporter=reporter)

    written = scheduler.export_markdown_report(output, limit=limit)
    payload = scheduler.build_review_payload(limit=limit)

    warnings: list[str] = []
    if store is not None:
        warnings.append("Using persisted store — dry-run results may persist to store")

    return OperatorCommandResult(
        command="nightly-export",
        status="success",
        dry_run=True,
        payload={
            "store_path": str(store) if store else ":memory:",
            "output_path": str(written),
            "item_count": payload.total if payload else 0,
            "pending_items": payload.items if payload else [],
        },
        warnings=warnings,
    )


def run_nightly_run_once_preview(
    *,
    store: str | Path | None = None,
    limit: int | None = None,
) -> OperatorCommandResult:
    """Build Nightly Review payload without sending — dry-run preview.

    Does NOT mark items as reviewed unless explicitly requested.

    Args:
        store: Optional explicit path to NightlyReviewStore JSONL.
               If None, uses empty in-memory store.
        limit: Optional limit on number of items.

    Returns:
        OperatorCommandResult with payload summary, dry_run=True, no send.
    """
    if store is not None:
        store_obj = NightlyReviewStore(storage_path=str(store))
    else:
        store_obj = NightlyReviewStore(storage_path=":memory:")

    reporter = NightlyReviewReporter()
    scheduler = NightlyReviewScheduler(store=store_obj, reporter=reporter)

    payload = scheduler.run_once(limit=limit, mark_reviewed=False)

    warnings: list[str] = ["Dry-run only — no message will be sent"]
    if store is not None:
        warnings.append("Using persisted store — dry-run results may persist to store")

    return OperatorCommandResult(
        command="nightly-run-once-preview",
        status="success",
        dry_run=True,
        payload={
            "store_path": str(store) if store else ":memory:",
            "total": payload.total,
            "pending": payload.pending,
            "reviewed": payload.reviewed,
            "item_count": len(payload.items),
            "dry_run": True,
        },
        warnings=warnings,
    )
