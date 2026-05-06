# Deferred Features Register

Features that are **not yet available** in the tracked codebase. These are not release blockers — they represent work planned for future iterations.

---

## 1. Nightly Review Scheduler

**Status**: AVAILABLE_WITH_LIMITS (dry-run pipeline + manual scheduler exists)

**What exists after PR #11**:
- `NightlyReviewItem` / `ReviewPayload` models
- `NightlyReviewStore` with JSONL persistence
- `NightlyReviewReporter` (dry-run only)
- `NightlyReviewScheduler` (manual, no daemon)
- `mode_decision_to_review_item()` integration helper
- CLI: `deerflow nightreview list | dry-run | export | clear | send | schedule-dry-run | run-once`
- 29 focused tests (18 pipeline + 11 scheduler)

**What does NOT exist**:
- No scheduler daemon (no cron, no background worker)
- No automatic trigger from mode_router
- No real Feishu/Lark send (`--real` raises `NotImplementedError`)

**Next steps**:
1. ~~Design explicit scheduler entry point~~ — **done (PR #11)**
2. ~~Implement manual scheduler~~ — **done (PR #11)**
3. Design and implement scheduler daemon (cron/timer, not daemon auto-start)
4. Real-send opt-in after credential rotation

**Estimated effort**: Medium (daemon) + Low (real-send wiring)
**Main-chain blocker**: No

---

## 2. Asset Runtime

**Phase 7 Classification**: DEFERRED

**What exists**:
- `ModeResultSink.asset` metadata flag (default `False`)
- `asset_registry.json` in `.deerflow/operation_assets/` — untracked JSON data (12 assets, 0 secrets)

**What does NOT exist**:
- No tracked Python runtime for asset lifecycle
- No `app.asset` module
- Runtime lives in untracked `external/Agent-S/` (off-limits to tracked code)

**Architecture decision (R216X)**: Option B — tracked adapter selected.
- R220: Asset adapter API design
- R221: Asset dry-run adapter + tests
- R222: External Agent-S adapter spike
- R223: Asset runtime decision review

**Next steps**:
1. ~~Decide between adapter / migration / external~~ — **done (R216X: Option B selected)**
2. R220: Design adapter API contract
3. R221: Implement dry-run adapter + tests
4. Do not commit `external/Agent-S/`
5. Do not mix Asset work with RTCM work
6. Do not claim Asset is fully implemented before R223 review

**Estimated effort**: High (R220–R223)
**Main-chain blocker**: No

---

## 3. RTCM Roundtable

**Phase 7 Classification**: DEFERRED

**What exists**:
- `SelectedMode.ROUNDTABLE` in `mode_router.py`
- `DelegatedTo.RTCM_MAIN_AGENT_HANDOFF` (untracked string constant)
- ROUNDTABLE keyword detection: "roundtable", "council", "debate", "讨论", "评审", "会议", "圆桌"

**What does NOT exist**:
- No tracked Python runtime for council / deliberation / vote / consensus
- No `app.rtcm` module
- `.deerflow/rtcm/` is 230-file untracked operational data directory — NOT runtime source

**Architecture decision (R216X)**: Tracked dry-run runtime first — completely independent of `.deerflow/rtcm` operational data.
- R224: RTCM dry-run runtime + tests
- R225: RTCM store + export
- R226: Integration helpers (mode_router unchanged)
- R227: RTCM real integration decision

**Next steps**:
1. ~~Design tracked RTCM runtime architecture~~ — **done (R216X)**
2. R224: Implement dry-run runtime (council/vote/consensus/reporter)
3. R225: Add store persistence + report export
4. Do not read `.deerflow/rtcm/` operational data
5. No Feishu token access; no real-send

**Estimated effort**: High
**Main-chain blocker**: No

---

## 4. Security Hygiene — Feishu Token Rotation

**Status**: DEFERRED_BY_OPERATOR

**What exists**: Live Feishu bot token in `.deerflow/rtcm/feishu/token_cache.json` (untracked)

**What is deferred**: Token rotation / revoke via open.feishu.cn developer console

**Next steps**:
1. Operator rotates token via open.feishu.cn → credentials → revoke
2. Add committed `.gitignore` protection for `.deerflow/rtcm/` — **done (PR #8)**
3. Move sensitive operational data outside Git repo workspace
4. Keep token_cache ignored

**Estimated effort**: Low (operator action) + Low (data migration)
**Main-chain blocker**: No

---

## Summary Table

| Feature | Status | Main-Chain Blocker | Estimated Effort |
|---------|--------|--------------------|------------------|
| Nightly Review Scheduler | AVAILABLE_WITH_LIMITS | No | Medium |
| Asset Runtime | DEFERRED | No | High |
| RTCM Roundtable | DEFERRED | No | High |
| Security Hygiene | DEFERRED_BY_OPERATOR | No | Low (operator) |

**None of these block the main development line or Phase 8 acceptance testing.**

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | R216X — Asset: Option B selected (R220–R223); RTCM: dry-run runtime confirmed (R224–R227) |