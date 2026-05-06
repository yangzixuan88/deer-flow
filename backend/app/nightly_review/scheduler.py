from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ReviewPayload
    from .reporter import NightlyReviewReporter
    from .store import NightlyReviewStore


class NightlyReviewScheduler:
    """Manual scheduler for Nightly Review.

    Does NOT start any daemon, background thread, or timer on construction.
    Does NOT call any Feishu/Lark API.
    Does NOT access .deerflow/rtcm/ or token_cache.json.
    All paths must be explicitly provided by the caller.
    """

    def __init__(self, store: NightlyReviewStore, reporter: NightlyReviewReporter) -> None:
        self._store = store
        self._reporter = reporter

    def build_review_payload(self, *, limit: int | None = None) -> ReviewPayload:
        """Build a ReviewPayload from pending items in the store.

        Args:
            limit: If set, only include up to this many items (oldest first).

        Returns:
            ReviewPayload with items from store.list_pending(), optionally limited.
        """
        items = self._store.list_pending()
        if limit is not None and limit > 0:
            items = items[:limit]
        return self._reporter.build_payload(items, dry_run=True)

    def build_markdown_report(self, *, limit: int | None = None) -> str:
        """Build a human-readable markdown report.

        Args:
            limit: If set, only include up to this many items.

        Returns:
            Markdown string suitable for printing or export.
        """
        payload = self.build_review_payload(limit=limit)
        return self._reporter.build_markdown(payload)

    def export_markdown_report(
        self,
        output_path: str | Path,
        *,
        limit: int | None = None,
    ) -> Path:
        """Write a markdown report to an explicit output path.

        Creates parent directories as needed. Does not append.

        Args:
            output_path: Explicit path to write the report to.
            limit: If set, only include up to this many items.

        Returns:
            The resolved Path that was written.
        """
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        report = self.build_markdown_report(limit=limit)
        p.write_text(report, encoding="utf-8")
        return p.resolve()

    def run_once(
        self,
        *,
        limit: int | None = None,
        mark_reviewed: bool = False,
    ) -> ReviewPayload:
        """Build the review payload, optionally mark items reviewed.

        Does NOT send anything. Does NOT access the network.

        Args:
            limit: If set, only include up to this many items.
            mark_reviewed: If True, mark all items in the payload as reviewed
                          in the store after building the payload.

        Returns:
            The ReviewPayload that was built.
        """
        items = self._store.list_pending()
        if limit is not None and limit > 0:
            items = items[:limit]

        payload = self._reporter.build_payload(items, dry_run=True)

        if mark_reviewed:
            for item in payload.items:
                self._store.mark_reviewed(item.id)

        return payload
