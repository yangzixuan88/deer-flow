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

    def list_records(self) -> list[DecisionRecord]:
        """Load all decision records from the store.

        Returns:
            List of DecisionRecord objects. Empty list if file does not exist.
        """
        if not self.path.exists():
            return []
        records: list[DecisionRecord] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                records.append(DecisionRecord.from_dict(d))
        return records

    def clear(self) -> None:
        """Remove the store file if it exists."""
        if self.path.exists():
            self.path.unlink()
