# Next Iteration Roadmap

Phases R203–R209X completed the Phase 7 close-out work. The next iteration covers Phase 8 acceptance testing and targeted enhancements.

---

## Stage 0 — Immediate Cleanup (R210–R211)

**Goal**: Resolve any remaining Phase 7 loose ends before Phase 8.

| # | Task | Owner | Blocker |
|---|------|-------|---------|
| R210 | Merge docs batch PR #10 (`r209x/public-docs-asset-rtcm-batch`) | Automated | None |
| R211 | Confirm PR #8 hygiene guard in `main` — run `git log --oneline -3` | Operator | None |

**Exit criteria**: All Phase 7 docs committed to `main`.

---

## Stage 1 — Phase 8 Acceptance Gate (R212–R213)

**Goal**: Dynamically validate that all 14 capability matrix features pass in CI.

| # | Task | Evidence | Pass Criteria |
|---|------|----------|---------------|
| R212 | Run full test suite | `pytest backend/ -q --tb=short` | 0 failures |
| R213 | Smoke-test run route | `curl localhost:PORT/api/threads/{id}/runs` | 200 OK |

**Exit criteria**: Mainline CI green, smoke endpoint returns 200.

---

## Stage 2 — Nightly Review Enhancement (R214–R215)

**Goal**: Add scheduler daemon (CLI-triggered or cron, no auto-start on import).

| # | Task | Target File | Safety Requirement |
|---|------|-------------|-------------------|
| R214 | Design scheduler entry point | `app/nightly_review/scheduler.py` | No daemon auto-start on import |
| R215 | Implement cron-compatible CLI | `nightly_review/cli.py` | `--real` flag still required |

**Exit criteria**: `deerflow nightreview send --real` requires explicit flag; dry-run remains default.

---

## Stage 3 — Feishu Real-Send Gate (R216)

**Goal**: Implement real Feishu/Lark send with `--real` opt-in.

| # | Task | Constraint |
|---|------|------------|
| R216 | Wire `FeishuChannel.send` into `NightlyReviewReporter` behind `--real` | Token must come from `app_config.lark`, never from `.deerflow/rtcm/token_cache.json` |

**Dependency**: R206 must be closed (operator rotation + `FEISHU_TOKEN_ROTATION_ACK=true`).

**Exit criteria**: `deerflow nightreview send --real` sends actual Feishu card to configured channel.

---

## Stage 4 — Asset Runtime Decision (R217)

**Goal**: Resolve Asset runtime architecture (Option B or C from `asset_runtime_decision.md`).

| # | Task | Decision Gate |
|---|------|---------------|
| R217 | Dedicated design phase | Choose between tracked adapter (B) and minimal tracked migration (C) |

**Dependency**: R216 complete (real-send baseline established).

**Exit criteria**: Decision documented; adapter interface defined OR minimal runtime scoped.

---

## P0 Blocker — Feishu Token Rotation

**R206** remains open until the operator:
1. Rotates the token via open.feishu.cn → credentials → revoke
2. Stores new token in operator-managed vault
3. Sets `FEISHU_TOKEN_ROTATION_ACK=true`

This unblocks **R216** and full public security claims.

---

## Non-Goals (Hard Constraints)

- No RTCM runtime implementation in this roadmap cycle
- No scheduler daemon auto-starting on import
- No commit of `.deerflow/rtcm/` operational data
- No Asset runtime before R217 decision is made and documented
- No mixing of Asset work with Nightly Review work

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial — R210–R217 roadmap documented |