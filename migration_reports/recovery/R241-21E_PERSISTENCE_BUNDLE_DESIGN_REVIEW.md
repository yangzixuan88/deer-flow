# R241-21E Persistence Bundle Design Review

**报告ID**: R241-21E_PERSISTENCE_BUNDLE_DESIGN_REVIEW
**生成时间**: 2026-04-29T11:50:00+08:00
**阶段**: Phase 21E — Persistence Bundle Design Review
**前置条件**: R241-21D Auth Bundle Design Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: persistence_bundle_design_review_completed_all_candidates_require_surface010_unblock
**persistence_bundle_design_completed**: true
**surface_010_implicated**: true (ALL 7 candidates)
**read_only_adapter_viable**: false (no persistence layer exists locally)
**implementation_allowed**: false
**safe_design_subset**: []
**all_candidates_blocked**: true

**关键结论**：
- 本地 persistence 层完全不存在 — 7 个 SURFACE-010 candidates 全部缺失
- 上游 persistence 模块在 `backend/packages/harness/deerflow/persistence/` 和 `runtime/events/store/`
- 所有 candidates 依赖 SURFACE-010 解除才能激活
- 无 read-only adapter 版本 — persistence 必须完整 port-back，否则无意义
- 无最小可行实现子集 — engine.py 是唯一入口，所有 store 依赖 engine

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. Local vs Upstream State

### Local State

| Path | Status |
|------|--------|
| `backend/packages/harness/deerflow/persistence/` | ❌ **DIR_NOT_FOUND** |
| `backend/packages/harness/deerflow/runtime/events/store/` | ❌ **DIR_NOT_FOUND** |

### Upstream State

| Path | Status | Notes |
|------|--------|-------|
| `backend/packages/harness/deerflow/persistence/__init__.py` | ✅ EXISTS | engine init/shutdown |
| `backend/packages/harness/deerflow/persistence/engine.py` | ✅ EXISTS | async engine lifecycle |
| `backend/packages/harness/deerflow/persistence/feedback/sql.py` | ✅ EXISTS | feedback repository |
| `backend/packages/harness/deerflow/persistence/run/sql.py` | ✅ EXISTS | run repository |
| `backend/packages/harness/deerflow/persistence/user/model.py` | ✅ EXISTS | UserRow ORM |
| `backend/packages/harness/deerflow/runtime/events/store/base.py` | ✅ EXISTS | abstract interface |
| `backend/packages/harness/deerflow/runtime/events/store/db.py` | ✅ EXISTS | DB store |
| `backend/packages/harness/deerflow/runtime/events/store/jsonl.py` | ✅ EXISTS | JSONL store |
| `backend/packages/harness/deerflow/runtime/events/store/memory.py` | ✅ EXISTS | memory store |

---

## 4. Candidate Analysis

### CAND-008: `persistence/__init__.py`

| Field | Value |
|-------|-------|
| **Upstream Content** | Exports `init_engine`, `close_engine`, `get_session_factory` |
| **Purpose** | Persistence layer entry point |
| **Runtime Impact** | Triggers `init_engine()` at startup — **write activation** |
| **Local Exists** | ❌ NO |
| **SURFACE-010** | ⚠️ YES — engine init is the primary SURFACE-010 trigger |
| **Priority** | P0 (root entry, all others depend on this) |

### CAND-009: `persistence/engine.py`

| Field | Value |
|-------|-------|
| **Upstream Content** | `init_engine()`, `get_session_factory()`, `close_engine()`, async SQLAlchemy engine |
| **Purpose** | Async SQLAlchemy engine lifecycle management |
| **Startup Write** | ⚠️ YES — `init_engine()` initializes DB connection at startup |
| **Startup Operations** | CREATE DATABASE (postgres), WAL mode (sqlite), schema create_all |
| **Memory Fallback** | `database.backend="memory"` → no-op, get_session_factory returns None |
| **Local Exists** | ❌ NO |
| **SURFACE-010** | ⚠️ YES — PRIMARY trigger |
| **Priority** | P0 |

### CAND-010: `persistence/feedback/sql.py`

| Field | Value |
|-------|-------|
| **Upstream Content** | FeedbackRepository using SQLAlchemy async sessions |
| **Purpose** | Persist feedback data |
| **Runtime Impact** | Read + Write to DB |
| **Startup Write** | ❌ NO |
| **Local Exists** | ❌ NO |
| **SURFACE-010** | ⚠️ YES (indirect — depends on engine.py) |
| **Priority** | P2 |

### CAND-011: `persistence/run/sql.py`

| Field | Value |
|-------|-------|
| **Upstream Content** | RunRepository using SQLAlchemy async sessions |
| **Purpose** | Persist run metadata |
| **Runtime Impact** | Read + Write to DB |
| **Startup Write** | ❌ NO |
| **Local Exists** | ❌ NO |
| **SURFACE-010** | ⚠️ YES (indirect — depends on engine.py) |
| **Priority** | P2 |

### CAND-012: `runtime/events/store/db.py`

| Field | Value |
|-------|-------|
| **Upstream Content** | `DbRunEventStore` — SQLAlchemy-backed RunEventStore |
| **Purpose** | Persist run events to `run_events` table |
| **Runtime Impact** | Write at runtime on every event |
| **Startup Write** | ❌ NO |
| **Event Write** | ⚠️ YES — every event creates DB row |
| **Local Exists** | ❌ NO |
| **SURFACE-010** | ⚠️ YES (indirect — depends on engine.py + user_context) |
| **Priority** | P2 |

### CAND-013: `runtime/events/store/jsonl.py`

| Field | Value |
|-------|-------|
| **Upstream Content** | `JsonlRunEventStore` — JSONL file-backed store |
| **Purpose** | Lightweight file-based event persistence |
| **Runtime Impact** | Write at runtime to `.deer-flow/threads/{thread_id}/runs/{run_id}.jsonl` |
| **Startup Write** | ❌ NO |
| **Event Write** | ⚠️ YES — every event appends to JSONL file |
| **File System** | ⚠️ YES — creates `.deer-flow/` directory structure |
| **Local Exists** | ❌ NO |
| **SURFACE-010** | ⚠️ YES (indirect) |
| **Priority** | P3 (alternative to db.py) |

### CAND-024: `persistence/user/model.py`

| Field | Value |
|-------|-------|
| **Upstream Content** | `UserRow` — SQLAlchemy ORM model for `users` table |
| **Purpose** | User data persistence |
| **Runtime Impact** | Read + Write to DB |
| **Startup Write** | ❌ NO (model definition only) |
| **Auth Dependency** | Used by `auth/repositories/sqlite.py` (reset_admin.py) |
| **Local Exists** | ❌ NO |
| **SURFACE-010** | ⚠️ YES (indirect — depends on engine.py) |
| **Priority** | P2 |

---

## 5. Persistence Bundle Dependency Graph

```
persistence/__init__.py (CAND-008) ← entry point aggregate
└── persistence/engine.py (CAND-009) ← PRIMARY SURFACE-010 TRIGGER
    ├── async SQLAlchemy engine lifecycle
    ├── CREATE DATABASE (postgres)
    ├── schema create_all (Base.metadata.create_all)
    └── Provides: get_session_factory()

runtime/events/store/base.py ← abstract interface (no writes)
    ├── runtime/events/store/db.py (CAND-012) ← DB-backed event store
    │   └── Uses: session_factory, RunEventRow
    ├── runtime/events/store/jsonl.py (CAND-013) ← JSONL-backed event store
    │   └── Uses: Path/.deer-flow filesystem
    └── runtime/events/store/memory.py ← Memory-backed event store
        └── SURFACE-010 DIRECT — memory contextvar per-request

persistence/feedback/sql.py (CAND-010) ← feedback repository
    └── Uses: session_factory

persistence/run/sql.py (CAND-011) ← run repository
    └── Uses: session_factory

persistence/user/model.py (CAND-024) ← UserRow ORM model
    └── Used by: auth/repositories/sqlite.py
```

---

## 6. Write Type Classification

### Startup Writes (Most Dangerous)

| Candidate | Write Type | Risk | Notes |
|-----------|-----------|------|-------|
| CAND-009 engine.py | DB connection init | **HIGH** | Triggers SURFACE-010 |
| CAND-009 | CREATE DATABASE | **HIGH** | Postgres only |
| CAND-009 | schema create_all | **HIGH** | Creates all tables at startup |

### Runtime Writes (Event-Level)

| Candidate | Write Type | Risk | Notes |
|-----------|-----------|------|-------|
| CAND-012 db.py | DB row per event | MEDIUM | Every run event → DB write |
| CAND-013 jsonl.py | JSONL append | MEDIUM | File write per event |
| CAND-010 feedback/sql.py | DB write | MEDIUM | User feedback writes |
| CAND-011 run/sql.py | DB write | MEDIUM | Run metadata writes |
| CAND-024 user/model.py | DB write | MEDIUM | Auth/user writes |

### Read-Only (Safe)

| Candidate | Read Type | Risk | Notes |
|-----------|-----------|------|-------|
| runtime/events/store/base.py | Interface only | None | Abstract, no implementation |

---

## 7. SURFACE-010 Unblock Prerequisites

### Why SURFACE-010 Blocks All Candidates

SURFACE-010 (memory BLOCKED CRITICAL) blocks all persistence candidates because:

1. **engine.py**: `init_engine()` requires async SQLAlchemy which uses connection pooling with memory-backed session factories
2. **DbRunEventStore**: Uses `user_context` for per-request user isolation
3. **MemoryRunEventStore**: Explicitly uses in-memory dict storage — **direct SURFACE-010**
4. **jsonl.py**: Writes to `.deer-flow/` directory — filesystem persistence
5. **All repositories**: Depend on `session_factory` from `engine.py`

### Unblock Sequence

| Step | Blocker to Remove | Then Enables |
|------|-------------------|-------------|
| 1 | SURFACE-010 unblock | All 7 persistence candidates |
| 2 | MAINLINE-GATEWAY-ACTIVATION=true | Gateway persistence activation |
| 3 | DSRT-ENABLED=true | DSRT integration |
| 4 | DSRT-IMPLEMENTED=true | DSRT implementation |
| 5 | GSIC-003 + GSIC-004 | Route registration |

### Evidence Required Before SURFACE-010 Unblock

| Evidence | Description |
|----------|-------------|
| Memory leak test | No memory leaks under sustained load |
| Connection pool stability | Pool doesn't exhaust under concurrency |
| Startup time measurement | init_engine completes within threshold |
| Backup verified | Data backup/restore procedure documented |
| Rollback plan | Procedure to disable persistence and revert |

---

## 8. Read-Only / Interface-Only Analysis

### runtime/events/store/base.py (Interface)

| Property | Value |
|----------|-------|
| Is interface | ✅ YES |
| Has implementation | ❌ NO (abstract base class) |
| Can port independently | ❌ NO — useless without concrete store |
| SURFACE-010 impact | None |

**Conclusion**: Interface-only port provides no value without a concrete implementation.

### No Persistence Exists Locally

Since `backend/packages/harness/deerflow/persistence/` does not exist locally, we cannot create a partial port that only has interfaces. A partial port would:
1. Import from non-existent modules → immediate ImportError
2. Provide no functionality → no value
3. Require complete port anyway → no savings

**Read-only adapter viable**: ❌ NO — there is nothing to adapt read-only.

---

## 9. Minimum Viable Implementation Order

Since all candidates are tightly coupled through `engine.py`:

```
Phase 1: CAND-009 (engine.py) ← MUST BE FIRST
    └── init_engine(), get_session_factory(), close_engine()

Phase 2: CAND-024 (user/model.py) + persistence/base.py
    └── ORM models required for schema create_all

Phase 3: CAND-010 + CAND-011 (feedback/sql.py + run/sql.py)
    └── Repositories using session_factory

Phase 4: CAND-012 OR CAND-013 (event stores)
    └── Choose one: db.py (SQL) or jsonl.py (file)

Phase 5: CAND-008 (persistence/__init__.py)
    └── Aggregate exports
```

**Cannot skip phases** — each depends on the previous.

---

## 10. Rollback / Backup / Retention Policy Requirements

### Rollback Conditions

| Condition | Rollback Action |
|-----------|-----------------|
| init_engine fails | Set `database.backend=memory`, no-op |
| DB connection exhaustion | Reduce pool size, restart gateway |
| Schema migration failure | Run alembic downgrade |
| JSONL file corruption | Delete `.deer-flow/`, re-initialize |

### Backup Requirements

| Component | Backup Method | Frequency |
|-----------|--------------|-----------|
| SQLite DB | File copy | Before migration |
| Postgres DB | pg_dump | Before migration |
| JSONL files | .deer-flow/ directory backup | Before migration |
| User passwords | bcrypt hashes (already in DB) | N/A |

### Retention Policy

| Data Type | Suggested Retention | Implementation |
|-----------|-------------------|----------------|
| Run events (db) | 30 days rolling | `run_events.created_at < NOW() - 30d` |
| Run events (jsonl) | 7 days rolling | File age-based deletion |
| Feedback | 90 days | `feedback.created_at < NOW() - 90d` |

---

## 11. Key Findings

### Finding 1: No Partial Port Possible

**Problem**: Local persistence layer does not exist. Cannot port only interfaces.

**Impact**: Either port the entire persistence layer or none of it.

**Recommendation**: Wait for SURFACE-010 unblock before attempting any persistence port.

### Finding 2: All 7 Candidates Blocked by SURFACE-010

**Problem**: All persistence candidates depend on engine.py which triggers SURFACE-010.

**Impact**: No safe subset for immediate implementation.

**Recommendation**: Treat all 7 as a single atomic bundle.

### Finding 3: Startup Writes are the Primary Risk

**Problem**: `init_engine()` performs write operations at startup.

**Impact**: Cannot activate persistence without verifying stable memory runtime.

**Recommendation**: Ensure `database.backend=memory` fallback works before enabling SQL persistence.

### Finding 4: No Read-Only Adapter Exists

**Problem**: There is no read-only version of persistence that can be safely ported independently.

**Impact**: Must port full persistence stack or nothing.

**Recommendation**: If only read access is needed, consider not using persistence at all.

---

## 12. Carryover Blockers (8 preserved)

| Blocker | 状态 |
|---------|------|
| SURFACE-010 memory BLOCKED CRITICAL | ✅ preserved |
| CAND-002 memory_read_binding BLOCKED | ✅ preserved |
| CAND-003 mcp_read_binding DEFERRED | ✅ preserved |
| GSIC-003 blocking_gateway_main_path BLOCKED | ✅ preserved |
| GSIC-004 blocking_fastapi_route_registration BLOCKED | ✅ preserved |
| MAINLINE-GATEWAY-ACTIVATION=false | ✅ preserved |
| DSRT-ENABLED=false | ✅ preserved |
| DSRT-IMPLEMENTED=false | ✅ preserved |

---

## 13. Final Decision

**status**: passed_with_warnings
**decision**: persistence_bundle_design_review_completed_all_candidates_require_surface010_unblock
**persistence_bundle_design_completed**: true
**bundle_candidates**: [CAND-008, CAND-009, CAND-010, CAND-011, CAND-012, CAND-013, CAND-024]
**required_files**: 7 candidates + dependencies (base.py, models, etc.)
**local_persistence_exists**: false
**surface_010_implicated**: true (ALL 7)
**read_only_adapter_viable**: false (nothing to adapt)
**minimum_viable_order**: [CAND-009, CAND-024, CAND-010+CAND-011, CAND-012|CAND-013, CAND-008]
**all_candidates_blocked**: true
**implementation_allowed**: false
**runtime_touch_detected**: false
**dependency_execution_executed**: false
**code_modified**: false
**blockers_preserved**: true
**safety_violations**: []
**recommended_resume_point**: R241-21E
**next_prompt_needed**: user_selection

---

## R241_21E_PERSISTENCE_BUNDLE_DESIGN_REVIEW_DONE

```
status=passed_with_warnings
decision=persistence_bundle_design_review_completed_all_candidates_require_surface010_unblock
persistence_bundle_design_completed=true
bundle_candidates=[CAND-008,CAND-009,CAND-010,CAND-011,CAND-012,CAND-013,CAND-024]
local_persistence_exists=false
surface_010_implicated=true
read_only_adapter_viable=false
all_candidates_blocked=true
minimum_viable_order=[CAND-009,CAND-024,CAND-010+CAND-011,CAND-012|CAND-013,CAND-008]
implementation_allowed=false
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-21E
next_prompt_needed=user_selection
```
