from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import NightlyReviewItem, ReviewPayload


class NightlyReviewReporter:
    """Dry-run report builder.

    Does NOT call any Feishu/Lark API. Does NOT require credentials.
    All methods that could cause external effects require explicit opt-in.
    """

    def build_payload(
        self,
        items: list[NightlyReviewItem],
        dry_run: bool = True,
    ) -> ReviewPayload:
        """Build a ReviewPayload from a list of items."""
        from .models import ReviewPayload

        return ReviewPayload.from_items(items, dry_run=dry_run)

    def build_markdown(self, payload: ReviewPayload) -> str:
        """Build a human-readable plain-text report."""
        lines = [
            "# Nightly Review Report",
            f"Generated: {payload.generated_at}",
            f"Mode: {'DRY-RUN' if payload.dry_run else 'REAL SEND'}",
            "",
            f"Total items: {payload.total}",
            f"  Pending:  {payload.pending}",
            f"  Reviewed: {payload.reviewed}",
            "",
            "## Items",
        ]
        for i, item in enumerate(payload.items, 1):
            lines.append("")
            lines.append(f"### {i}. [{item.status.upper()}] {item.mode}")
            lines.append(f"**Reason**: {item.reason}")
            if item.thread_id:
                lines.append(f"**Thread**: {item.thread_id}")
            if item.created_at:
                lines.append(f"**Time**: {item.created_at}")
            if item.payload_summary:
                lines.append(f"**Summary**: {item.payload_summary}")
        return "\n".join(lines)

    def build_feishu_card_payload(
        self,
        payload: ReviewPayload,
    ) -> dict:
        """Build a Feishu interactive card payload from a ReviewPayload.

        Reuses FeishuChannel._build_card_content (staticmethod) for the
        card body so the format is consistent with existing Feishu sends.

        Does NOT call feishu.send() or require credentials.
        """
        from app.channels.feishu import FeishuChannel

        header = "**Nightly Review Report**"
        subheader = f"Mode: DRY-RUN | Total: {payload.total} | Pending: {payload.pending} | Reviewed: {payload.reviewed}"

        lines = [header, subheader, "", "## Items", ""]
        for i, item in enumerate(payload.items, 1):
            lines.append(f"**{i}. [{item.status.upper()}] {item.mode}**  ")
            lines.append(f"Reason: {item.reason}")
            if item.thread_id:
                lines.append(f"Thread: {item.thread_id}")
            if item.created_at:
                lines.append(f"Time: {item.created_at}")
            if item.payload_summary:
                lines.append(f"Summary: {item.payload_summary[:80]}")
            lines.append("")

        text = "\n".join(lines)
        card_body = FeishuChannel._build_card_content(text)

        return {
            "msg_type": "interactive",
            "card": json.loads(card_body),
        }
