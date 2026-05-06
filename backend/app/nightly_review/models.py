from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

DEFAULT_STATUS = "pending"
DEFAULT_DRY_RUN = True


@dataclass
class NightlyReviewItem:
    id: str
    thread_id: str | None
    run_id: str | None
    user_id: str | None
    mode: str
    reason: str
    created_at: str
    source: str
    payload_summary: str
    status: str = DEFAULT_STATUS
    dry_run: bool = DEFAULT_DRY_RUN

    @classmethod
    def new(
        cls,
        thread_id: str | None = None,
        run_id: str | None = None,
        user_id: str | None = None,
        mode: str = "",
        reason: str = "",
        created_at: str | None = None,
        source: str = "mode_router",
        payload_summary: str = "",
    ) -> NightlyReviewItem:
        """Factory to create a new item with a generated UUID and timestamp."""
        return cls(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            run_id=run_id,
            user_id=user_id,
            mode=mode,
            reason=reason,
            created_at=created_at or datetime.now(UTC).isoformat(),
            source=source,
            payload_summary=payload_summary[:200] if payload_summary else "",
            status=DEFAULT_STATUS,
            dry_run=DEFAULT_DRY_RUN,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> NightlyReviewItem:
        return cls(**d)


@dataclass
class ReviewPayload:
    generated_at: str
    items: list[NightlyReviewItem]
    total: int
    pending: int
    reviewed: int
    dry_run: bool = DEFAULT_DRY_RUN

    @classmethod
    def from_items(
        cls,
        items: list[NightlyReviewItem],
        dry_run: bool = True,
    ) -> ReviewPayload:
        now = datetime.now(UTC).isoformat()
        pending = sum(1 for it in items if it.status == "pending")
        reviewed = sum(1 for it in items if it.status == "reviewed")
        return cls(
            generated_at=now,
            items=items,
            total=len(items),
            pending=pending,
            reviewed=reviewed,
            dry_run=dry_run,
        )

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "items": [it.to_dict() for it in self.items],
            "total": self.total,
            "pending": self.pending,
            "reviewed": self.reviewed,
            "dry_run": self.dry_run,
        }
