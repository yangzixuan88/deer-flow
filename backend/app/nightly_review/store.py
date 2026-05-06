from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import NightlyReviewItem


class NightlyReviewStore:
    """In-memory + JSONL-persisted queue for nightly review items.

    The store is append-only for simplicity. Items are never mutated
    by this class except for status transitions via mark_reviewed.

    Persistence: one JSON object per line (JSONL).
    Storage path is configurable; defaults to ~/.deerflow/nightly_review_store.jsonl.
    """

    def __init__(self, storage_path: Path | str | None = None) -> None:
        if storage_path is None:
            home = Path.home()
            store_dir = home / ".deerflow"
            store_dir.mkdir(exist_ok=True)
            storage_path = store_dir / "nightly_review_store.jsonl"
        self._path = Path(storage_path)
        self._items: list[dict] = []
        self._load()

    # -------------------------------------------------------------------------
    # Core operations
    # -------------------------------------------------------------------------

    def append(self, item: NightlyReviewItem) -> str:
        """Add an item to the queue. Returns the item id."""
        d = item.to_dict()
        self._items.append(d)
        self._save()
        return d["id"]

    def list_items(self) -> list[NightlyReviewItem]:
        """Return all items, oldest first."""
        from .models import NightlyReviewItem

        return [NightlyReviewItem.from_dict(d) for d in self._items]

    def list_pending(self) -> list[NightlyReviewItem]:
        """Return pending items, oldest first."""
        return [it for it in self.list_items() if it.status == "pending"]

    def mark_reviewed(self, item_id: str) -> bool:
        """Mark an item as reviewed. Returns False if not found."""
        for d in self._items:
            if d["id"] == item_id:
                d["status"] = "reviewed"
                self._save()
                return True
        return False

    def mark_sent(self, item_id: str) -> bool:
        """Mark an item as sent. Returns False if not found."""
        for d in self._items:
            if d["id"] == item_id:
                d["status"] = "sent"
                self._save()
                return True
        return False

    def clear(self) -> int:
        """Remove all items. Returns count of items cleared."""
        count = len(self._items)
        self._items = []
        self._save()
        return count

    # -------------------------------------------------------------------------
    # Import / export
    # -------------------------------------------------------------------------

    def export_jsonl(self, path: Path | str) -> int:
        """Export all items to a JSONL file. Returns count written."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with p.open("w", encoding="utf-8") as f:
            for d in self._items:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
                written += 1
        return written

    def import_jsonl(self, path: Path | str) -> int:
        """Import items from a JSONL file. Returns count imported."""
        p = Path(path)
        if not p.exists():
            return 0
        imported = 0
        new_items = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    new_items.append(d)
                    imported += 1
                except json.JSONDecodeError:
                    continue
        self._items.extend(new_items)
        self._save()
        return imported

    # -------------------------------------------------------------------------
    # Persistence helpers
    # -------------------------------------------------------------------------

    def _load(self) -> None:
        """Load items from JSONL file. Missing file is not an error."""
        if not self._path.exists():
            return
        self._items = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    self._items.append(d)
                except json.JSONDecodeError:
                    continue

    def _save(self) -> None:
        """Atomically write all items to JSONL file."""
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for d in self._items:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        tmp.replace(self._path)
