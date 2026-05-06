# Deferred Features Register

Features that are **not yet available** in the tracked codebase. These are not release blockers — they represent work planned for future iterations.

---

## 1. Nightly Review Scheduler

**Status**: AVAILABLE_WITH_LIMITS (dry-run pipeline exists)

**What exists after PR #9**:
- `NightlyReviewItem` / `ReviewPayload` models
- `NightlyReviewStore` with JSONL persistence
- `NightlyReviewReporter` (dry-run only)
- `mode_decision_to_review_item()` integration helper
- CLI: `deerflow nightreview list | dry-run | export | clear`
- 18 focused tests

**What does NOT exist**:
- No scheduler daemon (no cron, no background worker)
- No automatic trigger from mode_router
- No real Feishu/Lark send (`--real` raises `NotImplementedError`)

**Next steps**:
1. Design explicit scheduler entry point (CLI-first)
2. Scheduler must not auto-start on import
3. Real-send must remain opt-in (`--real` flag)
4. Consider cron / CLI-driven invocation before daemon

**Estimated effort**: Medium
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

**Next steps**:
1. Decide between: keep external / add tracked adapter / migrate minimal runtime
2. Do not commit `external/Agent-S/`
3. Do not mix Asset work with Nightly Review work
4. Do not claim Asset is implemented before decision

**Estimated effort**: High
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

**Next steps**:
1. Design tracked RTCM runtime architecture
2. Do not read operational logs as implementation guide
3. No token dependency
4. No Feishu real-send

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