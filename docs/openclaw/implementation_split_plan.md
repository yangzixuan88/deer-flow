# OpenClaw Implementation Split Plan

## Principle

One PR = one independently testable runtime boundary.
Avoid mega-PRs for runtime implementation.
Each PR must pass CI independently.

---

## Completed High-Pressure Batches

| PR | Scope | Type |
|----|-------|------|
| PR #8 | `.gitignore` hygiene guard for operational data | security |
| PR #9 | Nightly Review dry-run pipeline + 18 tests | feature |
| PR #10 | Capability matrix, deferred register, Asset/RTCM/ security docs | docs |
| PR #11 | Nightly Review manual scheduler + 11 tests | feature |

---

## Implementation Queue

### R220 — Asset Adapter API Design

**Type**: docs-only (or tests-first if scope is small)
**Next PR**: `asset_runtime_decision.md` update with finalized API contract
**Scope**:
- Finalize `AssetRequest`, `AssetResult`, `AssetCapability` model fields
- Define `AssetRuntimeAdapter` interface signature
- No runtime execution code

**Exit criteria**: API contract documented and reviewed; no implementation code

---

### R221 — Asset Dry-Run Adapter

**Type**: code + tests
**Next PR**: `backend/app/asset_runtime/` package
**Scope**:
- `backend/app/asset_runtime/__init__.py`
- `backend/app/asset_runtime/models.py` — `AssetRequest`, `AssetResult`, `AssetCapability`, `AssetRuntimeStatus`
- `backend/app/asset_runtime/adapter.py` — `AssetRuntimeAdapter` interface; `NoOpAdapter` as first implementation
- `backend/app/asset_runtime/dry_run.py` — simulate asset operation, return structured result
- `backend/tests/test_asset_runtime_dry_run.py` — unit tests for adapter and models

**Forbidden**:
- `external/Agent-S/`
- `.deerflow/operation_assets/` untracked data
- Real external calls
- Credentials / tokens

**Exit criteria**: All tests pass; no external network calls; CI green

---

### R224 — RTCM Dry-Run Runtime

**Type**: code + tests
**Next PR**: `backend/app/rtcm/` package (dry-run core)
**Scope**:
- `backend/app/rtcm/__init__.py`
- `backend/app/rtcm/models.py` — `RoundtableRequest`, `CouncilMember`, `Vote`, `ConsensusResult`, `DecisionRecord`
- `backend/app/rtcm/council.py` — `CouncilOrchestrator`
- `backend/app/rtcm/vote.py` — `VoteCollector`, voting strategies
- `backend/app/rtcm/consensus.py` — `ConsensusEngine`, majority/weighted/unanimous strategies
- `backend/app/rtcm/reporter.py` — `RTCMReporter`, dry-run Markdown/JSON report builder
- `backend/tests/test_rtcm_dry_run_runtime.py`

**Forbidden**:
- `.deerflow/rtcm/` operational data
- Feishu token access
- Real-send Feishu/Lark
- `external/Agent-S/`

**Exit criteria**: All tests pass; `test_no_rtcm_token_path_access` passes; CI green

---

### R225 — RTCM Store + Export

**Type**: code + tests
**Next PR**: `backend/app/rtcm/store.py` + reporter export enhancements
**Scope**:
- `backend/app/rtcm/store.py` — `RTCMStore` with JSONL persistence
- `backend/app/rtcm/reporter.py` — export to file (markdown / JSON)
- `backend/tests/test_rtcm_store.py`

**Constraints**: Same as R224; tmp_path used in all tests

---

### R226 — Integration Helpers

**Type**: code + tests
**Next PR**: `backend/app/asset_runtime/integration.py` + `backend/app/rtcm/integration.py`
**Scope**:
- `backend/app/asset_runtime/integration.py` — `mode_decision_to_asset_request()`
- `backend/app/rtcm/integration.py` — `roundtable_to_rtcm_request()`
- `mode_router.py` remains unchanged (no side effects)

**Forbidden**: Both integration helpers must not modify `mode_router.py`

---

## Security Queue

### R212 — Feishu Credential Rotation (Still Open)

**Status**: P0 blocker — operator action required

**Still required**:
- Rotate/revoke Feishu bot token via open.feishu.cn developer console
- Store new token in operator-managed vault (not `.deerflow/rtcm/token_cache.json`)
- Set `FEISHU_TOKEN_ROTATION_ACK=true` env var

**Unblocks**:
- R216 (Feishu real-send wiring)
- Full public security claims

---

## Non-Goals (Hard Constraints)

- No mega-PRs combining Asset + RTCM + Nightly Review in one PR
- No PR that modifies both `mode_router.py` and a runtime package
- No commitment of `external/Agent-S/`
- No reading of `.deerflow/rtcm/` or `.deerflow/operation_assets/` as runtime source
- No credential-dependent implementation in early stages

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial — R220–R227 queue defined |