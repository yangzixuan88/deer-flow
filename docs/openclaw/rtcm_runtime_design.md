# RTCM Runtime Design

## Current State

- **Phase 7 Classification**: DEFERRED
- **mode_router.py** has `SelectedMode.ROUNDTABLE` and `DelegatedTo.RTCM_MAIN_AGENT_HANDOFF`
- The delegation string points to a target that does not exist in tracked code
- **`.deerflow/rtcm/`** is a 230-file untracked operational data directory — this is session telemetry, budgets, Feishu tokens, and working logs. It is **NOT** runtime source code and must not be used as such.
- **No tracked Python runtime** for: council, deliberation, vote, consensus, decision record, or report generation

---

## Problem Statement

The mode router can route to `ROUNDTABLE` mode, but there is no tracked implementation that:
1. Creates a council / roundtable session
2. Collects agent inputs
3. Runs a deliberation or voting mechanism
4. Reaches consensus
5. Records the decision
6. Produces a report

---

## Proposed Package Structure

```
backend/app/rtcm/
├── __init__.py           # public API exports
├── models.py             # RTCMSession, Vote, ConsensusRecord
├── council.py            # CouncilOrchestrator
├── vote.py               # VoteCollector, voting strategies
├── consensus.py          # ConsensusEngine
├── store.py              # RTCMStore (JSONL, like NightlyReviewStore)
├── reporter.py           # RTCMReporter (dry-run report builder)
└── integration.py        # mode_router integration helper
```

---

## Design Principles

1. **Router does not execute** — `mode_router.py` produces delegation metadata only; it must never import or call `app.rtcm`.
2. **Operational data is not runtime** — `.deerflow/rtcm/` must not be imported or used as if it contains implementation code.
3. **Dry-run by default** — Report generation must not call Feishu/Lark APIs without explicit opt-in.
4. **No token access** — Credentials must come from `app_config.lark`, never from `.deerflow/rtcm/token_cache.json`.
5. **No external network** — All network operations must be mockable in tests.
6. **Scheduler is explicit** — No auto-start on import; CLI or function-call driven only.
7. **Testable with tmp_path** — All persistence uses `tmp_path` in tests.

---

## Safety Requirements (Hard Constraints)

- No access to `.deerflow/rtcm/` operational data directory
- No reading of `.deerflow/rtcm/token_cache.json`
- No Feishu real-send without explicit `--real` opt-in
- No dependency on Agent-S runtime
- No scheduler daemon auto-starting on import
- All runtime state must be testable with `tmp_path`

---

## Minimal Future Tests

| Test | Purpose |
|------|---------|
| `test_import_has_no_side_effects` | No threads / daemons start on import |
| `test_create_council_session` | Can create a new council |
| `test_cast_vote` | Vote recorded correctly |
| `test_compute_consensus` | Consensus reached on majority |
| `test_store_decision` | Decision persisted to JSONL |
| `test_build_dry_run_report` | Report generated without network |
| `test_no_token_path_access` | `.deerflow/rtcm/token_cache.json` not accessed |
| `test_real_send_requires_opt_in` | `--real` flag required for actual send |

---

## Non-Goals (Hard Constraints)

- No real Feishu/Lark send in initial implementation
- No use of `.deerflow/rtcm/` operational logs as implementation reference
- No migration of `.deerflow/rtcm/` into tracked code
- No scheduler daemon
- No dependency on Asset runtime

---

## Relationship to Nightly Review

RTCM and Nightly Review share structural patterns:
- Both use a JSONL-backed store
- Both have a reporter with dry-run default
- Both integrate via a `mode_X_to_review_item()`-style helper

If RTCM design proceeds after Nightly Review scheduler, consider extracting a shared `ReviewReporter` base class.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial — proposed architecture documented |