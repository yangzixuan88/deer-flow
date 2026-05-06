# Nightly Review Scheduler Design

## Current State

- **Dry-run pipeline**: exists after PR #9 (`90ee98c6`)
- **Components available**: `NightlyReviewStore`, `NightlyReviewReporter`, `NightlyReviewItem`, CLI with `list | dry-run | export | clear | send`
- **No scheduler daemon**: no background worker, no cron integration, no auto-start
- **No real-send**: `--real` flag raises `NotImplementedError`

---

## Design Decision

**R214 implements manual scheduler only.**

Explicit invocation, not daemon:
- Explicit function call or CLI command
- No background thread on import
- No cron integration
- No systemd/timer unit
- No auto-start on module import
- No Feishu real-send in this batch

---

## Components

### `backend/app/nightly_review/scheduler.py`

Primary class: `NightlyReviewScheduler`

```python
class NightlyReviewScheduler:
    def __init__(self, store: NightlyReviewStore, reporter: NightlyReviewReporter): ...

    def build_review_payload(self, *, limit: int | None = None) -> ReviewPayload:
        """Read pending items from store, optionally limit count. No send."""

    def build_markdown_report(self, *, limit: int | None = None) -> str:
        """Build markdown text from payload."""

    def export_markdown_report(self, output_path: str | Path, *, limit: int | None = None) -> Path:
        """Write markdown report to explicit path. Creates parent dirs."""

    def run_once(self, *, limit: int | None = None, mark_reviewed: bool = False) -> ReviewPayload:
        """Build payload, optionally mark items reviewed. No send."""
```

### CLI integration

New subcommands added to existing CLI:

```
nightreview schedule-dry-run --store <path> [--limit N]
nightreview export --store <path> --output <path> [--limit N]
nightreview run-once --store <path> [--mark-reviewed] [--limit N]
```

All default to dry-run (no Feishu send). `--real` still raises `NotImplementedError`.

---

## Safety Rules (Hard Constraints)

- **No scheduler auto-start**: import of `scheduler.py` must not start any thread or timer
- **No external network**: no HTTP calls, no Feishu API calls
- **No token read**: `token_cache.json` must never be accessed
- **No `.deerflow/rtcm/` access**: operational data directory is off-limits
- **tmp_path-compatible**: all persistence uses caller-provided paths
- **Dry-run by default**: no Feishu send without explicit `--real` opt-in
- **Testable**: all behavior verifiable via unit tests with mocks

---

## Data Flow

```
NightlyReviewStore (JSONL)
    └── list_pending()
            │
            ▼
NightlyReviewScheduler.build_review_payload(limit)
            │
            ▼
NightlyReviewReporter.build_payload(items, dry_run=True)
            │
     ┌──────┴──────┐
     ▼             ▼
Markdown report  Feishu card dict
(dry-run)        (build only, not sent)
```

---

## Future Deferred (Not in R214)

- Cron integration (`@daily` or timer unit)
- Daemon mode (background worker)
- Real-send opt-in (after credential rotation + `FEISHU_TOKEN_ROTATION_ACK=true`)
- UI integration (start/stop/status dashboard)
- Automatic scheduling based on time of day
- Retry logic for failed sends

---

## Relationship to Nightly Review Pipeline

The scheduler builds on the existing dry-run pipeline from PR #9:

| Component | PR #9 | R214 |
|-----------|-------|------|
| `NightlyReviewStore` | ✅ | ✅ |
| `NightlyReviewItem` | ✅ | ✅ |
| `NightlyReviewReporter.build_payload` | ✅ | ✅ |
| `NightlyReviewReporter.build_markdown` | ✅ | ✅ |
| `NightlyReviewReporter.build_feishu_card_payload` | ✅ | ✅ |
| `NightlyReviewScheduler` | ❌ | ✅ |
| `mode_decision_to_review_item` | ✅ | ✅ |
| CLI subcommands | `list/dry-run/export/clear/send` | `schedule-dry-run/export/run-once` |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial — manual scheduler design documented |
| 2026-05-06 | R239X — CLI export now supports --output markdown; export_markdown_report in scheduler; run-once-preview does not mark reviewed; all paths explicit; no daemon/cron |