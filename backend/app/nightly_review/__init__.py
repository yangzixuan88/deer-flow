"""Nightly Review dry-run pipeline.

This package provides a minimal, dry-run-first execution pipeline for
Nightly Review. It is independent of mode_router, requires no credentials,
and makes no network calls by default.

Scope (R208):
- NightlyReviewItem / ReviewPayload models
- JSONL-backed NightlyReviewStore
- dry-run NightlyReviewReporter
- mode_decision_to_review_item integration helper
- CLI entry point (dry-run only; real send = NotImplementedError)

Out of scope for R208:
- Scheduler daemon
- Background worker
- Real Feishu/Lark send (--real not implemented)
- RTCM integration
- Asset integration
"""

from __future__ import annotations

from .integration import mode_decision_to_review_item
from .models import NightlyReviewItem, ReviewPayload
from .reporter import NightlyReviewReporter
from .store import NightlyReviewStore

__all__ = [
    "NightlyReviewItem",
    "NightlyReviewReporter",
    "NightlyReviewStore",
    "ReviewPayload",
    "mode_decision_to_review_item",
]
