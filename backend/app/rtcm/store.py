"""JSONL-backed decision store for RTCM roundtable runtime.

Uses tmp_path-compatible file I/O. No SQLite, no .deerflow/rtcm access.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import DecisionRecord


class RTCMDecisionStore:
    """JSONL store for DecisionRecord persistence.

    Each record is stored as one JSON line (JSONL format).
    File is created on first write if it does not exist.
    Supports explicit-path-only operation — no default .deerflow/rtcm.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: DecisionRecord) -> None:
        """Append a decision record as a JSON line.

        Args:
            record: The DecisionRecord to persist.
        """
        line = json.dumps(record.to_dict(), ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def list_records(self, limit: int | None = None) -> list[DecisionRecord]:
        """Load decision records from the store.

        Args:
            limit: If set, return at most this many records (most recent first).

        Returns:
            List of DecisionRecord objects. Empty list if file does not exist
            or file is empty.
        """
        if not self.path.exists():
            return []
        records: list[DecisionRecord] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    records.append(DecisionRecord.from_dict(d))
                except (json.JSONDecodeError, KeyError):
                    # Skip malformed lines — store must not crash on corruption
                    continue
        # Most-recent-first order
        records.reverse()
        if limit is not None and limit > 0:
            records = records[:limit]
        return records

    def get(self, record_id: str) -> DecisionRecord | None:
        """Get a record by its request ID, or None if not found.

        Args:
            record_id: The request ID to look up.

        Returns:
            DecisionRecord if found, None otherwise.
        """
        for record in self.list_records():
            req_id = getattr(record.request, "id", None)
            if req_id == record_id:
                return record
        return None

    def latest(self) -> DecisionRecord | None:
        """Return the most recently appended record, or None if store is empty."""
        records = self.list_records(limit=1)
        return records[0] if records else None

    def export_json(self, path: str | Path, *, limit: int | None = None) -> Path:
        """Export records as a pretty-printed JSON array to an explicit path.

        Creates parent directories as needed.

        Args:
            path: Explicit output path.
            limit: If set, export at most this many records (most recent first).

        Returns:
            The resolved Path that was written.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        records = self.list_records(limit=limit)
        data = [r.to_dict() for r in records]
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return p.resolve()

    def export_markdown(self, path: str | Path, *, limit: int | None = None) -> Path:
        """Export records as a merged markdown report to an explicit path.

        Creates parent directories as needed.

        Args:
            path: Explicit output path.
            limit: If set, export at most this many records (most recent first).

        Returns:
            The resolved Path that was written.
        """
        from .reporter import build_markdown_index

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        records = self.list_records(limit=limit)
        report = build_markdown_index(records)
        p.write_text(report, encoding="utf-8")
        return p.resolve()

    def clear(self) -> None:
        """Remove the store file if it exists."""
        if self.path.exists():
            self.path.unlink()
