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

**Phase 7 Classification**: AVAILABLE_WITH_LIMITS (tracked dry-run adapter implemented)

**What exists after R221/R220X**:
- `ModeResultSink.asset` metadata flag (default `False`)
- `app.asset_runtime` package with models, adapter, dry_run, integration
- `execute_asset_dry_run()` — no external agent calls
- 25 focused tests

**What does NOT exist**:
- No real Agent-S invocation
- No production asset lifecycle verified
- Runtime lives in untracked `external/Agent-S/` (off-limits to tracked code)

**Architecture decision (R216X)**: Option B — tracked adapter selected.
- R220: Asset adapter API design — **done**
- R221: Asset dry-run adapter + tests — **done (R220X)**
- R222: External Agent-S adapter spike — deferred
- R223: Asset runtime decision review — deferred

**Next steps**:
1. ~~Decide between adapter / migration / external~~ — **done (R216X: Option B selected)**
2. ~~Implement dry-run adapter + tests~~ — **done (R221)**
3. R222: Spike external Agent-S adapter (research only, no production claim)
4. R223: Decide — keep adapter or migrate minimal runtime

**Estimated effort**: High (R220–R223)
**Main-chain blocker**: No

---

## 3. RTCM Roundtable

**Phase 7 Classification**: AVAILABLE_WITH_LIMITS (tracked dry-run runtime implemented)

**What exists after R224X**:
- `SelectedMode.ROUNDTABLE` in `mode_router.py`
- `DelegatedTo.RTCM_MAIN_AGENT_HANDOFF` (untracked string constant)
- ROUNDTABLE keyword detection: "roundtable", "council", "debate", "讨论", "评审", "会议", "圆桌"
- `app.rtcm` package with models, council, vote, consensus, reporter, store, integration
- `execute_rtcm_dry_run()` — deterministic dry-run with no network calls
- 33 focused tests

**What does NOT exist**:
- No real agent handoff (agent-s or external)
- No Feishu/Lark real-send
- No production consensus verified against live agents
- `.deerflow/rtcm/` operational data not used by tracked runtime

**Architecture decision (R216X)**: Tracked dry-run runtime first — completely independent of `.deerflow/rtcm` operational data.
- R224: RTCM dry-run runtime + tests — **done (R224X)**
- R225: RTCM store + export — **done (R224X)**
- R226: Integration helpers — **done (R224X)**
- R227: RTCM real integration decision — deferred

**Next steps**:
1. ~~Design tracked RTCM runtime architecture~~ — **done (R216X)**
2. ~~Implement dry-run runtime (council/vote/consensus/reporter)~~ — **done (R224X)**
3. ~~Add store persistence + report export~~ — **done (R224X)**
4. ~~Integration helpers~~ — **done (R224X)**
5. R227: Decide — keep dry-run only or connect to external agents

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
| Asset Runtime | AVAILABLE_WITH_LIMITS | No | High |
| RTCM Roundtable | AVAILABLE_WITH_LIMITS | No | High |
| Security Hygiene | DEFERRED_BY_OPERATOR | No | Low (operator) |

**None of these block the main development line or Phase 8 acceptance testing.**

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | R216X — Asset: Option B selected (R220–R223); RTCM: dry-run runtime confirmed (R224–R227) |
| 2026-05-06 | R220X — Asset dry-run adapter implemented (R221); R224X — RTCM dry-run runtime implemented (R224); Asset + RTCM status updated to AVAILABLE_WITH_LIMITS |