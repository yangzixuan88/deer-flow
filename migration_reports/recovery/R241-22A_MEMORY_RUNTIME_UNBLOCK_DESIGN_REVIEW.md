# R241-22A Memory Runtime Unblock Design Review

**报告ID**: R241-22A_MEMORY_RUNTIME_UNBLOCK_DESIGN_REVIEW
**生成时间**: 2026-04-29T13:00:00+08:00
**阶段**: Phase 22A — Memory Runtime Unblock Design Review
**前置条件**: R241-21G Unified Dependency Matrix Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: surface010_unblock_design_completed_evidence_matrix_defined
**surface010_unblock_design_completed**: true
**surface010_unblocked**: false (design only, no implementation)
**implementation_allowed**: false

**关键结论**：
- SURFACE-010 有两个直接触发器：`user_context.py` (ContextVar) 和 `persistence/engine.py` (init_engine)
- 5 个 Evidence Gates 必须全部通过才能解除 SURFACE-010
- 解除后，12 个 candidates 将被解锁（Auth Sub-Bundle C + D, Persistence Layer 3-5, Gateway Layer 6-8）
- 当前仅完成 design review，不实现任何 runtime
- GSIC-003 和 GSIC-004 在 SURFACE-010 解除后仍然存在

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. SURFACE-010 Blocker Definition

### Blocker Definition

| Property | Value |
|----------|-------|
| **Blocker ID** | SURFACE-010 |
| **Description** | memory runtime BLOCKED CRITICAL |
| **Root Cause** | 两个直接触发器都使用需要运行时初始化的内存数据结构 |
| **直接触发器数** | 2 |
| **间接依赖数** | 10 |
| **总影响数** | 12/17 candidates |

### 直接触发器 (Direct Triggers)

| Trigger ID | File | Mechanism | Write Operation |
|------------|------|-----------|------------------|
| **DT-001** | `deerflow/runtime/user_context.py` | `ContextVar[CurrentUser \| None]` | `set_current_user()` stores user in ContextVar memory |
| **DT-002** | `deerflow/persistence/engine.py` | `init_engine()` | `CREATE DATABASE`, `PRAGMA WAL`, `schema create_all` |

### 为什么被 BLOCKED

```
Both triggers involve in-memory state that could:
1. Leak if not properly initialized before first use
2. Cause undefined behavior if context is not isolated between requests
3. Lead to data corruption if startup DB writes are not safe

The blocker is "memory runtime BLOCKED CRITICAL" because:
- user_context.py uses ContextVar (asyncio task-local memory)
- engine.py performs startup writes to the database
- Both require verification before production use
```

---

## 4. Direct Trigger Analysis

### DT-001: user_context.py / ContextVar Per-Request State

**文件**: `backend/packages/harness/deerflow/runtime/user_context.py`
**行数**: 147 LOC
**机制**: `ContextVar[CurrentUser | None]` with Token-based reset pattern

```
_current_user: Final[ContextVar[CurrentUser | None]] = ContextVar(
    'deerflow_current_user', default=None
)

Key Functions:
├── set_current_user(user: CurrentUser) -> Token[CurrentUser | None]
├── reset_current_user(token: Token[CurrentUser | None]) -> None
├── get_current_user() -> CurrentUser | None
├── require_current_user() -> CurrentUser (raises RuntimeError if None)
└── resolve_user_id(value: str | None | _AutoSentinel) -> str | None
```

#### Asyncio Task-Local Isolation

| Property | Value |
|----------|-------|
| **Mechanism** | ContextVar is task-local under asyncio, not thread-local |
| **Guarantee** | Each `asyncio.create_task()` gets its own copy of the context |
| **Inheritance** | Parent task's context is inherited by child tasks (intended behavior) |
| **Explicit Isolation** | `contextvars.copy_context()` can create clean copy for background tasks |

#### Current Implementation Safety

```python
# auth_middleware.py pattern (safe):
token = set_current_user(user)
try:
    ...  # use user context
finally:
    reset_current_user(token)  # Always reset
```

**当前实现正确使用了 token reset pattern** — 这是 safe 的。

#### Memory Risk Model

| Risk | Description | Severity |
|------|-------------|----------|
| MEM-001 | set_current_user called but token not reset → GC retention | MEDIUM |
| MEM-002 | ContextVar not isolated → user A sees user B's data | CRITICAL |
| MEM-003 | asyncio.create_task inherits polluted context | CRITICAL |

### DT-002: persistence/engine.py / init_engine_from_config

**文件**: `backend/packages/harness/deerflow/persistence/engine.py`
**行数**: 140 LOC
**机制**: async SQLAlchemy engine with init/shutdown lifecycle

#### Startup Write Sequence

```
Step 1: if backend == 'memory': logger.info + return (no-op)
Step 2: if backend == 'postgres': check asyncpg import
Step 3: if backend == 'sqlite': create directory, create engine, attach WAL listeners
Step 4: else if backend == 'postgres': create engine with pool_size
Step 5: _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
Step 6: try import deerflow.persistence.models
Step 7: async with _engine.begin(): conn.run_sync(Base.metadata.create_all)
Step 8: if postgres + 'does not exist': auto-create DB, retry create_all
```

#### Memory Backend Contract

```python
if backend == "memory":
    logger.info("Persistence backend=memory -- ORM engine not initialized")
    return  # No engine, no factory

def get_session_factory() -> async_sessionmaker | None:
    return _session_factory  # Returns None if memory
```

**Repositories 必须检查 None 并 fallback 到 in-memory**

---

## 5. Memory Runtime Risk Model

| Risk ID | Name | Severity | Likelihood | Mitigation |
|---------|------|----------|------------|------------|
| **MEM-001** | ContextVar memory leak | MEDIUM | LOW | Always use token pattern with finally |
| **MEM-002** | Cross-request user contamination | CRITICAL | LOW | ContextVar is task-local by asyncio design |
| **MEM-003** | Background task context pollution | CRITICAL | MEDIUM | Use `contextvars.copy_context()` for isolated tasks |
| **MEM-004** | Connection pool exhaustion | HIGH | MEDIUM | pool_size tuning, pool_pre_ping=True |
| **MEM-005** | Startup DB write failure | HIGH | LOW | memory fallback, try/except graceful degradation |
| **MEM-006** | SQLite WAL corruption | HIGH | MEDIUM | synchronous=NORMAL, periodic checkpoint |

---

## 6. ContextVar Isolation Test Design

### Test Suite: CV-ISO (10 test cases)

| Test ID | Name | Description | Pass Criteria |
|---------|------|-------------|---------------|
| **CV-ISO-01** | Sequential set/reset | set → get → reset → get=None | Correct state transitions |
| **CV-ISO-02** | Concurrent tasks no cross-contamination | Task1 sets A, Task2 sets B, each sees own | No contamination |
| **CV-ISO-03** | Background task inheritance | Parent sets A, child sees A (inherited) | Intentional behavior |
| **CV-ISO-04** | Background task explicit isolation | Parent sets A, child with copy_context sees None | Clean slate |
| **CV-ISO-05** | Token reset restores previous | set A → token → set B → reset A → sees A | Previous state restored |
| **CV-ISO-06** | require_current_user raises when unset | Call without context | RuntimeError raised |
| **CV-ISO-07** | resolve_user_id AUTO sentinel | set A → resolve_user_id(AUTO) | Returns user A's ID |
| **CV-ISO-08** | resolve_user_id explicit str | set A → resolve_user_id('explicit') | Returns 'explicit' |
| **CV-ISO-09** | resolve_user_id None bypass | set A → resolve_user_id(None) | Returns None (migration path) |
| **CV-ISO-10** | DEFAULT_USER_ID fallback | No context → get_effective_user_id() | Returns 'default' |

**Pass Criteria**: All 10 pass with no cross-contamination
**Framework**: pytest + pytest-asyncio
**Duration**: ~5 seconds

---

## 7. Memory Leak Test Design

### Test Suite: MEM-LEAK (4 test cases)

| Test ID | Name | Metric | Threshold |
|---------|------|--------|-----------|
| **MEM-LEAK-01** | 10k sequential set/reset | Memory delta | < 5MB |
| **MEM-LEAK-02** | 10k users without reset | Growth rate | Should plateau |
| **MEM-LEAK-03** | 100 concurrent tasks 30s | Memory stable | < 10MB growth |
| **MEM-LEAK-04** | Error path no leak | Memory stable | No growth |

**Pass Criteria**: No leak detected, all deltas < threshold
**Framework**: pytest + memory_profiler or tracemalloc
**Duration**: ~2 minutes

---

## 8. Connection Pool Stability Test Design

### Test Suite: POOL (5 test cases)

| Test ID | Name | Metric | Threshold |
|---------|------|--------|-----------|
| **POOL-01** | 50 concurrent reads | All complete | < 30s |
| **POOL-02** | 100 concurrent ops | Max wait | < 5s |
| **POOL-03** | Pool exhaustion recovery | Graceful rejection | 503 or timeout |
| **POOL-04** | Pool recycle on error | Subsequent success | Recovers |
| **POOL-05** | close_engine cleanup | Connections = 0 | No lingering |

**Pass Criteria**: Exhaustion < 1%, all recover gracefully
**Framework**: pytest + sqlalchemy async
**Duration**: ~1 minute

---

## 9. Startup DB Write Safety Gate

### Gate: SDB (9 checks)

| Check ID | Name | Verification |
|----------|------|--------------|
| **SDB-01** | memory backend no-op | engine=None, factory=None |
| **SDB-02** | sqlite directory creation | Path exists |
| **SDB-03** | sqlite WAL mode | PRAGMA journal_mode='wal' |
| **SDB-04** | sqlite synchronous NORMAL | PRAGMA synchronous='normal' |
| **SDB-05** | sqlite foreign keys ON | PRAGMA foreign_keys='on' |
| **SDB-06** | postgres auto-create | DB exists after init |
| **SDB-07** | schema create_all | All tables exist |
| **SDB-08** | close_engine cleanup | Engine disposed |
| **SDB-09** | graceful degradation | Error not catastrophic |

**Pass Criteria**: All 9 checks pass
**Precondition**: Database backup verified before any write

---

## 10. Database.backend=memory Fallback Contract

### Engine Behavior

| Call | Backend=memory | Backend=sqlite/postgres |
|------|---------------|------------------------|
| `init_engine()` | Returns immediately, logs info | Creates engine |
| `get_session_factory()` | Returns **None** | Returns factory |
| `get_engine()` | Returns **None** | Returns engine |
| `close_engine()` | No-op | Disposes engine |

### Repository Behavior

```python
# When session_factory is None:
if sf is None:
    from deerflow.runtime.runs.store.memory import MemoryRunStore
    app.state.run_store = MemoryRunStore()  # Fallback!
    app.state.feedback_repo = None  # No-op
```

### Gateway Behavior

```python
# _ensure_admin_user skips if auth not ready:
try:
    provider = get_local_provider()
except RuntimeError:
    logger.warning("Auth persistence not ready; skipping admin bootstrap check")
    return
```

---

## 11. Rollback / Disable Switch Design

### Switch: DATABASE_BACKEND_FALLBACK

| Property | Value |
|----------|-------|
| **Location** | `config.yaml` or environment variable |
| **Key** | `database.backend` |
| **Values** | `memory`, `sqlite`, `postgres` |
| **Runtime Switch** | Not hot-swap — requires restart |

### Rollback Procedure

```
1. Set database.backend=memory in config.yaml
2. Restart gateway
3. init_engine is no-op → get_session_factory=None
4. Repositories fall back to memory implementations
5. No data loss — SQLite/Postgres data still on disk
```

### Recovery Procedure

```
1. Fix root cause (memory leak, pool exhaustion, etc.)
2. Set database.backend=sqlite or postgres
3. Restart gateway
4. init_engine recreates engine, repos use disk-backed stores
5. Existing data accessible again
```

---

## 12. Evidence Required Before Unblock

### SURFACE-010 Unblock Checklist

| Evidence ID | Name | Status | Pass Criteria |
|-------------|------|--------|---------------|
| **E-01** | ContextVar isolation test | NOT_STARTED | All 10 cases pass |
| **E-02** | Memory leak test | NOT_STARTED | Delta < 5MB |
| **E-03** | Connection pool stability test | NOT_STARTED | Exhaustion < 1% |
| **E-04** | Startup DB write safety gate | NOT_STARTED | All 9 checks pass |
| **E-05** | memory backend fallback contract | NOT_STARTED | factory=None when memory |
| **E-06** | Database backup verified | NOT_STARTED | pg_dump / copy successful |

---

## 13. Unblock Decision Gates

```
Gate 1: GATE-CV-ISO (ContextVar Isolation)
   └── CV-ISO-01 through CV-ISO-10 → ALL PASS

Gate 2: GATE-MEM-LEAK (Memory Leak)
   └── MEM-LEAK-01 through MEM-LEAK-04 → ALL PASS, delta < 5MB

Gate 3: GATE-POOL (Connection Pool)
   └── POOL-01 through POOL-05 → ALL PASS

Gate 4: GATE-SDB (Startup DB Write)
   └── SDB-01 through SDB-09 → ALL PASS

Gate 5: GATE-ROLLBACK (Rollback Disable Switch)
   └── memory fallback verified → WARNING ONLY (non-blocking)

FINAL: GATE-SURFACE-010-UNBLOCK
   └── All GATE-CV-ISO + GATE-MEM-LEAK + GATE-POOL + GATE-SDB passed
   └── Then: SURFACE-010 UNBLOCKED → 12 candidates unblocked
```

---

## 14. Downstream Unlock Map

### After SURFACE-010 Unblock

```
┌─────────────────────────────────────────────────────────────────┐
│                    SURFACE-010 UNBLOCKED                         │
│                    (12 candidates unlock)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ Auth Bundle │    │Persistence │    │  Gateway    │
   │  Sub-B C+D  │    │   Bundle    │    │  Layer 6-8  │
   └─────────────┘    └─────────────┘    └─────────────┘

AUTH BUNDLE:
├── CAND-005 (auth_middleware.py) → UNBLOCKED
└── CAND-004 (reset_admin.py) → UNBLOCKED

PERSISTENCE BUNDLE:
├── CAND-009 (engine.py) → UNBLOCKED
├── CAND-024 (UserRow) → UNBLOCKED
├── CAND-010, CAND-011, CAND-012, CAND-013 → UNBLOCKED
└── CAND-008 (persistence/__init__.py) → UNBLOCKED

GATEWAY BUNDLE:
├── deps.py langgraph_runtime → UNBLOCKED
├── CAND-018 (app.py) → UNBLOCKED (but GSIC-003 still blocks)
└── CAND-007 (routers/auth.py) → UNBLOCKED (but GSIC-003 + GSIC-004 still block)

STILL BLOCKED AFTER SURFACE-010:
├── GSIC-003 (blocking_gateway_main_path)
├── GSIC-004 (blocking_fastapi_route_registration)
└── CAND-002 (memory_read_binding)
```

---

## 15. Recommended Sequence 22B / 22C / 22D

### After SURFACE-010 Unblock

| Phase | Name | Candidates | Depends On |
|-------|------|-----------|------------|
| **R241-22B** | Auth Bundle Sub-Bundle C | CAND-005 (auth_middleware) | SURFACE-010 UNBLOCK |
| **R241-22C** | Persistence Stage 3 | CAND-009 (engine.py), CAND-024 (UserRow) | SURFACE-010 UNBLOCK |
| **R241-22D** | Persistence Repositories | CAND-010, CAND-011, CAND-012, CAND-013 | R241-22C |

---

## 16. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| user_context_created | ❌ false |
| engine_created | ❌ false |
| db_written | ❌ false |
| memory_activated | ❌ false |
| patch_applied | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

---

## 17. Carryover Blockers (8 preserved)

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

## R241_22A_MEMORY_RUNTIME_UNBLOCK_DESIGN_REVIEW_DONE

```
status=passed_with_warnings
surface010_unblock_design_completed=true
surface010_unblocked=false
direct_triggers=[user_context.py (DT-001), persistence/engine.py (DT-002)]
evidence_matrix_completed=true
test_plan_completed=true
rollback_plan_completed=true
downstream_unlock_map_completed=true
implementation_allowed=false
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-22B
next_prompt_needed=user_selection
```