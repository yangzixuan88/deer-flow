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
| R212 | ~~Run full test suite~~ | `pytest backend/ -q --tb=short` | In progress (PR #11) |
| R213 | Smoke-test run route | `curl localhost:PORT/api/threads/{id}/runs` | 200 OK |

**Exit criteria**: Mainline CI green, smoke endpoint returns 200.

---

## Stage 2 — Nightly Review Enhancement (R214–R215)

**Goal**: Add scheduler daemon (CLI-triggered or cron, no auto-start on import).

| # | Task | Target File | Safety Requirement |
|---|------|-------------|-------------------|
| R214 | ~~Design scheduler entry point~~ | `app/nightly_review/scheduler.py` | ~~No daemon auto-start on import~~ |
| R215 | ~~Implement cron-compatible CLI~~ | `nightly_review/cli.py` | ~~`--real` flag still required~~ |

**Status**: R214 + R215 implemented in PR #11 — manual scheduler done. Daemon deferred to R218.

**Next**: R218 — scheduler daemon design + cron integration

---

## Stage 3 — Feishu Real-Send Gate (R216)

**Goal**: Implement real Feishu/Lark send with `--real` opt-in.

| # | Task | Constraint |
|---|------|------------|
| R216 | Wire `FeishuChannel.send` into `NightlyReviewReporter` behind `--real` | Token must come from `app_config.lark`, never from `.deerflow/rtcm/token_cache.json` |

**Dependency**: R212 (Feishu token rotation) must be closed (`FEISHU_TOKEN_ROTATION_ACK=true`).

**Exit criteria**: `deerflow nightreview send --real` sends actual Feishu card to configured channel.

---

## Stage 4 — Scheduler Daemon (R218)

**Goal**: Add cron/timer-based scheduler daemon for automated nightly execution.

| # | Task | Constraint |
|---|------|------------|
| R218 | Design and implement scheduler daemon | No auto-start on import; CLI-triggered; cron or timer unit |

**Dependency**: R216 (Feishu real-send) complete.

**Exit criteria**: `cron` or `systemd timer` invokes scheduler without daemon auto-start.

---

## Stage 5 — Asset Runtime (R220–R223)

**Architecture decision (R216X)**: Option B — tracked adapter selected.

**Goal**: Implement tracked asset adapter with dry-run first, completely independent of untracked `external/Agent-S/`.

| # | Task | Type | Constraint |
|---|------|------|------------|
| R220 | Asset adapter API design | docs-only | Finalize `AssetRequest` / `AssetResult` contract |
| R221 | Asset dry-run adapter | code + tests | `models.py`, `adapter.py`, `dry_run.py`; no real Agent-S call |
| R222 | External Agent-S adapter spike | research | Evaluate whether Agent-S can be wrapped; no production claim |
| R223 | Asset runtime decision review | decision | Decide: keep adapter or migrate minimal runtime |

**Dependency**: None (parallel to Stage 3/4).

**Exit criteria**: `backend/app/asset_runtime/` implemented; 0 external network calls in tests.

---

## Stage 6 — RTCM Runtime (R224–R227)

**Architecture decision (R216X)**: Tracked dry-run runtime first, completely independent of `.deerflow/rtcm` operational data.

**Goal**: Implement tracked RTCM runtime with no dependency on operational data or Feishu token.

| # | Task | Type | Constraint |
|---|------|------|------------|
| R224 | RTCM dry-run runtime | code + tests | `council.py`, `vote.py`, `consensus.py`, `reporter.py`; no `.deerflow/rtcm/` read |
| R225 | RTCM store + export | code + tests | `store.py` JSONL; tmp_path tests; no `.deerflow/rtcm/` read |
| R226 | Integration helpers | code + tests | `mode_decision_to_rtcm_request()`; `mode_router.py` unchanged |
| R227 | RTCM real integration decision | decision | Decide: connect to external agents or remain dry-run only |

**Dependency**: None (parallel to Stage 3/4/5).

**Exit criteria**: `backend/app/rtcm/` implemented; `test_no_rtcm_token_path_access` passes.

---

## P0 Blocker — Feishu Token Rotation

**R212** remains open until the operator:
1. Rotates the token via open.feishu.cn → credentials → revoke
2. Stores new token in operator-managed vault
3. Sets `FEISHU_TOKEN_ROTATION_ACK=true`

This unblocks **R216** and full public security claims.

---

## Non-Goals (Hard Constraints)

- No scheduler daemon auto-starting on import
- No commit of `.deerflow/rtcm/` operational data
- No Asset runtime claiming full implementation before R223 review
- No RTCM runtime claiming full implementation before R227 review
- No real Feishu/Lark send before R216/R212 closure
- Do not commit `external/Agent-S/`
- Do not read `.deerflow/rtcm/` or `.deerflow/operation_assets/` as runtime source

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial — R210–R217 roadmap documented |
| 2026-05-06 | R212X batch: R214+R215 manual scheduler done; R218 daemon deferred; R219 asset decision renumbered |
| 2026-05-06 | R216X batch: R220–R223 (Asset adapter) and R224–R227 (RTCM runtime) stages defined; parallel to R216/R218 |