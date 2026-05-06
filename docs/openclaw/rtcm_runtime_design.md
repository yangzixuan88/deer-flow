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
├── models.py             # RoundtableRequest, CouncilMember, Vote, ConsensusResult, DecisionRecord
├── council.py            # CouncilOrchestrator
├── vote.py               # VoteCollector, voting strategies
├── consensus.py          # ConsensusEngine
├── store.py              # RTCMStore (JSONL, tmp_path-compatible)
├── reporter.py           # RTCMReporter (dry-run report builder)
└── integration.py        # roundtablesession_to_rtcm_request helper
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

## Final Decision for Next Implementation Cycle

**Decision: Create a tracked dry-run RTCM runtime first, completely independent from `.deerflow/rtcm` operational data.**

**Rationale:**

- Current `ROUNDTABLE` delegation is only a promise marker — no tracked execution exists.
- `.deerflow/rtcm/` is **operational data** containing sensitive local state (tokens, session logs).
- The runtime must be **tracked, tested, and deterministic** — not based on operational logs.
- Do **not** reuse operational logs as source of truth for implementation.

---

## Selected Architecture: Tracked Dry-Run Consensus Runtime

**Proposed package:**

```
backend/app/rtcm/
├── __init__.py        # public API exports
├── models.py          # RoundtableRequest, CouncilMember, Vote, ConsensusResult, DecisionRecord
├── council.py         # CouncilOrchestrator — build council from explicit input
├── vote.py            # VoteCollector — collect deterministic votes
├── consensus.py       # ConsensusEngine — majority / weighted / unanimous strategies
├── store.py           # RTCMStore — JSONL persistence, tmp_path-compatible
├── reporter.py        # RTCMReporter — dry-run Markdown / JSON report
└── integration.py     # roundtablesession_to_rtcm_request helper
```

**Responsibilities by module:**

| Module | Responsibility | Constraints |
|--------|---------------|------------|
| `models.py` | `RoundtableRequest`, `CouncilMember`, `Vote`, `ConsensusResult`, `DecisionRecord` | No external I/O |
| `council.py` | Build council from explicit input; no network; no credentials | No `.deerflow/rtcm/` read |
| `vote.py` | Collect deterministic votes; test fixture support | No external calls |
| `consensus.py` | Majority / weighted / unanimous strategies; deterministic output | No stateful external I/O |
| `store.py` | JSONL persistence; tmp_path-compatible | No `.deerflow/rtcm/` read |
| `reporter.py` | Build dry-run Markdown / JSON report | No Feishu real-send |
| `integration.py` | Convert ROUNDTABLE mode metadata into `RoundtableRequest` | Must not modify `mode_router.py` |

---

## Implementation Stages

| Phase | Task | Type | Exit Criteria |
|-------|------|------|---------------|
| R224 | RTCM dry-run runtime | code + tests | `models.py`, `council.py`, `vote.py`, `consensus.py`, `reporter.py` implemented; tests pass |
| R225 | RTCM store + export | code + tests | `store.py` + reporter export; tmp_path tests pass |
| R226 | Integration helper | code + tests | `roundtable_to_rtcm_request()` helper; `mode_router` unchanged |
| R227 | RTCM real integration decision | decision | Decide: connect to external agents or remain dry-run only |

---

## Relationship to Nightly Review

RTCM and Nightly Review share structural patterns:
- Both use a JSONL-backed store
- Both have a reporter with dry-run default
- Both integrate via a `mode_X_to_review_item()`-style helper

If RTCM design proceeds after Nightly Review scheduler, consider extracting a shared `ReviewReporter` base class.

---

## Explicit Non-Goals (Hard Constraints)

- **Do not** read `.deerflow/rtcm/` — operational data is not runtime source code
- **Do not** read `.deerflow/rtcm/token_cache.json` — token never accessed
- **Do not** use Feishu token — credentials must come from `app_config.lark`
- **Do not** send real Feishu/Lark messages in initial implementation
- **Do not** create a daemon — explicit CLI / function-call only
- **Do not** depend on Agent-S runtime
- **Do not** claim RTCM fully implemented until tracked runtime + tests exist

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial — proposed architecture documented |
| 2026-05-06 | R216X — dry-run first architecture confirmed; R224–R227 stages defined |