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

## Non-Goals (Hard Constraints)

- **Do not** commit `external/Agent-S/` to git
- **Do not** import untracked asset payloads as if they were tracked runtime
- **Do not** mix Asset runtime work with Nightly Review work
- **Do not** claim Asset is implemented before a decision is made and documented
- **Do not** use `result_sink.asset` as evidence of a working runtime — it is only a routing hint

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial — decision options documented |