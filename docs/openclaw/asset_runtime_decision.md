# Asset Runtime Decision

## Current State

- **Phase 7 Classification**: DEFERRED
- **result_sink.asset**: Metadata flag only (`False` by default); no tracked code reads or acts on it
- **Asset registry**: `asset_registry.json` in `.deerflow/operation_assets/` — untracked JSON data (12 assets, 0 secrets)
- **Runtime location**: Appears to live in untracked `external/Agent-S/` — this directory is not tracked in git
- **No tracked runtime**: No `app.asset`, `deerflow.asset`, or equivalent Python module exists in tracked code

---

## Decision Options

### Option A — Keep Agent-S External (Status Quo)

**Pros**:
- No migration risk
- Agent-S can evolve independently
- Tracked repo stays clean

**Cons**:
- Tracked code cannot claim "asset runtime implemented"
- Requires clear documentation that runtime is external
- Interface stability depends on external project

**Verdict**: Safe default if implementation cost is prohibitive.

---

### Option B — Add Tracked Adapter

**Pros**:
- Stable interface defined inside `deerflow` tracked code
- Adapter can wrap the external Agent-S runtime
- Tracked code can claim asset lifecycle management

**Cons**:
- Still depends on external Agent-S binary/process
- Adapter must handle version skew

**Verdict**: Good balance if some integration is desired.

---

### Option C — Migrate Minimal Runtime Into Tracked Code

**Pros**:
- Fully testable in CI
- No external dependency for core functionality
- Tracked code owns the asset lifecycle

**Cons**:
- Largest implementation cost
- Risk of carrying over Agent-S assumptions
- May duplicate functionality already in Agent-S

**Verdict**: Highest investment; only if asset lifecycle is core to product.

---

### Option D — Retire Asset Flag Until Runtime Exists

**Pros**:
- No false capability signal
- Clean state until decision is made
- Forces explicit decision before any claim

**Cons**:
- Removes planned-capability signal from `ModeResultSink`

**Verdict**: Conservative; appropriate if timeline is uncertain.

---

## Recommendation

**Do not implement Asset runtime in the current batch.**

Before implementation, complete a dedicated design phase that chooses between **Option B** (tracked adapter) and **Option C** (minimal tracked migration).

If the decision is Option B: define the adapter interface first, then implement.
If the decision is Option C: scope the minimal runtime (which entities, which lifecycle events) before migrating.

---

## Final Decision for Next Implementation Cycle

**Decision: Choose Option B first — tracked adapter over external Agent-S.**

**Rationale:**

- Option A (keep Agent-S external) preserves current behavior but cannot claim a tracked runtime.
- Option C (migrate full runtime) has high scope and high regression risk.
- Option D (retire flag) loses the planned capability signal.
- **Option B** creates a stable tracked interface while deferring deep Agent-S migration.

---

## Selected Architecture: Tracked Adapter Boundary

**Proposed future package:**

```
backend/app/asset_runtime/
├── __init__.py        # public API exports
├── models.py          # AssetRequest, AssetResult, AssetCapability
├── adapter.py         # AssetRuntimeAdapter interface + implementations
├── registry.py        # load tracked asset capability metadata
├── planner.py         # convert result_sink.asset into AssetRequest
├── dry_run.py         # simulate asset operation, no external calls
└── integration.py     # mode_decision_to_asset_request helper
```

**Responsibilities by module:**

| Module | Responsibility | Constraints |
|--------|--------------|------------|
| `models.py` | `AssetRequest`, `AssetResult`, `AssetCapability`, `AssetRuntimeStatus` | No external I/O |
| `adapter.py` | `AssetRuntimeAdapter` interface; `NoOpAdapter` first; `ExternalAgentSAdapter` later | No real Agent-S call in dry-run |
| `registry.py` | Load tracked asset capability metadata | Must not read untracked `operation_assets/` by default; no token dependency |
| `planner.py` | Convert `result_sink.asset` into `AssetRequest` | No execution side effects |
| `dry_run.py` | Simulate asset operation, return structured `AssetResult` | No external process |
| `integration.py` | Helper: `mode_decision_to_asset_request()` | Must not modify `mode_router.py` |

**Implementation stages:**

| Phase | Task | Type | Exit Criteria |
|-------|------|------|---------------|
| R220 | Asset adapter API design | docs-only | API contract finalized in `asset_runtime_decision.md` |
| R221 | Asset dry-run adapter | code + tests | `models.py`, `adapter.py`, `dry_run.py` implemented; tests pass |
| R222 | External Agent-S adapter spike | research | Evaluate whether Agent-S can be wrapped; no production claim |
| R223 | Asset runtime decision review | decision | Decide: keep adapter or migrate minimal runtime |

---

## Explicit Non-Goals (Hard Constraints)

- **Do not** commit `external/Agent-S/` to git
- **Do not** import untracked asset payloads as if they were tracked runtime
- **Do not** read `.deerflow/operation_assets/` by default
- **Do not** claim Asset runtime is fully implemented before R223 review
- **Do not** use `result_sink.asset` as evidence of a working runtime — it is only a routing hint
- **Do not** require credentials for dry-run adapter
- **Do not** mix Asset implementation with RTCM implementation

---

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial — decision options documented |
| 2026-05-06 | R216X — Option B selected; adapter architecture and R220–R223 stages defined |
| 2026-05-06 | R221 — `models.py`, `adapter.py`, `dry_run.py`, `integration.py` implemented; 25 tests passing; no external network calls |