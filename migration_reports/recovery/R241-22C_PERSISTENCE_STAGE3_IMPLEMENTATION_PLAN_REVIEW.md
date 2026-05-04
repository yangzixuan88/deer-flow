# R241-22C Persistence Stage 3 Implementation Plan Review

**报告ID**: R241-22C_PERSISTENCE_STAGE3_IMPLEMENTATION_PLAN_REVIEW
**生成时间**: 2026-04-29T14:00:00+08:00
**阶段**: Phase 22C — Persistence Stage 3 Implementation Plan Review
**前置条件**: R241-22A Memory Runtime Unblock Design Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: persistence_stage3_plan_completed_engine_and_userrow_contracts_defined
**persistence_stage3_plan_completed**: true
**implementation_allowed**: false
**surface010_unblocked**: false

**关键结论**：
- Stage 3 包含 5 个文件：`base.py`, `user/model.py`, `models/__init__.py`, `engine.py`, `__init__.py`
- `engine.py` 是 SURFACE-010 的**主要直接触发器**（DT-002）— 执行 startup DB writes
- `user/model.py`（CAND-024）通过 `Base.metadata` 间接依赖 engine
- 3  backend 支持：`memory`（no-op）、`sqlite`（WAL）、`postgres`（auto-CREATE DATABASE）
- SDB-01 through SDB-09 全部映射完成
- POOL-01 through POOL-05 全部映射完成

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. Stage 3 File Inventory

### Files Overview

| File | Candidate | Type | LOC | SURFACE-010 | Route Reg | Gateway Mod |
|------|----------|------|-----|-------------|-----------|-------------|
| `persistence/engine.py` | CAND-009 | Async engine lifecycle | 140 | **DIRECT** (DT-002) | ❌ | ❌ |
| `persistence/user/model.py` | CAND-024 | ORM model | 70 | indirect | ❌ | ❌ |
| `persistence/base.py` | N/A | DeclarativeBase | 50 | ❌ | ❌ | ❌ |
| `persistence/models/__init__.py` | N/A | Model registration | 20 | ❌ | ❌ | ❌ |
| `persistence/__init__.py` | N/A | Aggregate exports | ~20 | ❌ | ❌ | ❌ |

**Total**: 5 files, ~280 LOC
**No route registration**: ✅ guaranteed
**No gateway main path modification**: ✅ guaranteed
**No DB write at import**: ✅ guaranteed

---

## 4. CAND-009 engine.py Implementation Contract

**文件**: `backend/packages/harness/deerflow/persistence/engine.py`
**行数**: 140 LOC
**验证**: 上游内容已读取确认

### Core Functions

| Function | Signature | Contract |
|----------|-----------|----------|
| `init_engine` | `(backend, url, echo, pool_size, sqlite_dir)` | Creates AsyncEngine + async_sessionmaker; runs backend-specific setup; create_all |
| `init_engine_from_config` | `(config: DatabaseConfig)` | Convenience wrapper |
| `get_session_factory` | `() -> async_sessionmaker \| None` | Returns None if backend=memory |
| `get_engine` | `() -> AsyncEngine \| None` | Returns None if not initialized |
| `close_engine` | `()` | Disposes engine, resets to None |

### Global State

```python
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None
```

### Three-Backend Support

| Backend | Behavior |
|---------|----------|
| `memory` | Returns early — no engine, no factory, no DB operation |
| `sqlite` | Creates dir, engine, WAL PRAGMAs per-connection, create_all |
| `postgres` | Creates engine, checks asyncpg, create_all (with auto-create DB retry) |

### SQLite WAL PRAGMA Sequence

```python
# Per-connection via event listener
PRAGMA journal_mode=WAL        # Write-Ahead Logging
PRAGMA synchronous=NORMAL      # Periodic fsync only
PRAGMA foreign_keys=ON         # Enforce FK constraints
```

**Mechanism**: `event.listens_for(_engine.sync_engine, 'connect')` — runs on every new connection

### Postgres Auto-CREATE DATABASE Sequence

```
1. Create engine to 'postgres' maintenance DB (AUTOCOMMIT)
2. Execute: CREATE DATABASE "{db_name}"
3. Dispose maintenance engine
4. Retry init_engine with target DB
```

---

## 5. CAND-024 UserRow Model Contract

**文件**: `backend/packages/harness/deerflow/persistence/user/model.py`
**行数**: 70 LOC
**验证**: 上游内容已读取确认

### Table Definition

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | String(36) | PK, UUID stored as string |
| `email` | String(320) | UNIQUE, INDEX |
| `password_hash` | String(128) | NULLABLE |
| `system_role` | String(16) | DEFAULT 'user' |
| `created_at` | DateTime(timezone=True) | DEFAULT datetime.now(UTC) |
| `oauth_provider` | String(32) | NULLABLE |
| `oauth_id` | String(128) | NULLABLE |
| `needs_setup` | Boolean | DEFAULT False |
| `token_version` | Integer | DEFAULT 0 |

### Table Args

```python
Index('idx_users_oauth_identity', oauth_provider, oauth_id, unique=True,
      sqlite_where=oauth_provider IS NOT NULL AND oauth_id IS NOT NULL)
```

### Usage

- `app.py _ensure_admin_user()` — queries for admin user row
- `auth/repositories/sqlite.py` — user CRUD operations

---

## 6. database.backend=memory Contract

**Contract ID**: MEMORY_NOOP

| Call | Backend=memory | Backend=sqlite/postgres |
|------|---------------|------------------------|
| `init_engine()` | Returns immediately, logs info | Creates engine |
| `get_session_factory()` | Returns **None** | Returns factory |
| `get_engine()` | Returns **None** | Returns engine |
| `close_engine()` | No-op | Disposes engine |

### Repository Fallback Requirement

```python
# When session_factory is None:
if sf is None:
    from deerflow.runtime.runs.store.memory import MemoryRunStore
    app.state.run_store = MemoryRunStore()
    app.state.feedback_repo = None
```

---

## 7. SDB-01 through SDB-09 Mapping

| Gate | Name | Contract File |
|------|------|---------------|
| **SDB-01** | memory backend no-op | engine.py |
| **SDB-02** | sqlite directory creation | engine.py |
| **SDB-03** | sqlite WAL mode enabled | engine.py |
| **SDB-04** | sqlite synchronous NORMAL | engine.py |
| **SDB-05** | sqlite foreign keys ON | engine.py |
| **SDB-06** | postgres database auto-create | engine.py |
| **SDB-07** | schema create_all runs | engine.py + models/__init__.py |
| **SDB-08** | close_engine cleanup | engine.py |
| **SDB-09** | graceful degradation on failure | engine.py |

---

## 8. POOL-01 through POOL-05 Mapping

| Gate | Name | Contract File |
|------|------|---------------|
| **POOL-01** | 50 concurrent DB reads | engine.py |
| **POOL-02** | 100 concurrent DB operations | engine.py |
| **POOL-03** | Pool exhaustion recovery | engine.py |
| **POOL-04** | Pool recycle on error | engine.py (pool_pre_ping=True) |
| **POOL-05** | close_engine releases all | engine.py |

---

## 9. Rollback / Disable Switch Mapping

**Switch**: `database.backend`
**Values**: `memory`, `sqlite`, `postgres`

### Rollback Procedure

```
1. Set database.backend=memory in config.yaml
2. Restart gateway
3. init_engine returns early, no engine created
4. Repositories fall back to in-memory
5. Existing SQLite/Postgres data preserved on disk
```

**No data loss**: memory fallback does not delete SQLite/Postgres files

---

## 10. Test File Plan

| File ID | Test File | Cases | Framework | Duration |
|---------|-----------|-------|----------|----------|
| TF-05 | `tests/unit/persistence/test_engine.py` | init_engine all backends, get_session_factory, close_engine | pytest-asyncio | 30s |
| TF-06 | `tests/unit/persistence/test_user_row.py` | UserRow columns, to_dict(), inspection | pytest | 5s |
| TF-07 | `tests/unit/persistence/test_sqlite_wal.py` | SDB-02 through SDB-05 | pytest + aiosqlite | 10s |
| TF-08 | `tests/unit/persistence/test_postgres_auto_create.py` | SDB-06 | pytest + asyncpg | 20s |
| TF-09 | `tests/unit/persistence/test_pool_stability.py` | POOL-01 through POOL-05 | pytest + sqlalchemy async | 1min |

**Total**: 5 test files, ~30 test cases, ~2 minutes (excluding postgres)

---

## 11. Implementation Order (If Authorization Granted)

| Step | File | Reason | Can Parallelize |
|------|------|--------|-----------------|
| **1** | `persistence/base.py` | Foundation — Base class required for all ORM models | ✅ with step 2 |
| **2** | `persistence/user/model.py` | UserRow ORM model | ✅ with step 1 |
| **3** | `persistence/models/__init__.py` | Model registration — imports all models for Base.metadata discovery | After steps 1+2 |
| **4** | `persistence/engine.py` | **CRITICAL** — init_engine/close_engine/session_factory; SURFACE-010 primary trigger | After steps 1+2+3 |
| **5** | `persistence/__init__.py` | Aggregate exports — re-exports init_engine, close_engine, get_session_factory | After step 4 |

**Parallelization**: Step 1 + Step 2 can run in parallel (Base and UserRow independent)
**Critical path**: Step 4 (engine.py) is the primary SURFACE-010 trigger and must be last in this sequence

---

## 12. Explicit Stop Conditions

| Condition | Action |
|-----------|--------|
| SURFACE-010 not yet unblocked | Do not implement Stage 3 — engine.py triggers SURFACE-010 |
| Authorization scope does not expand | Design only, no file creation |
| SDB gates (01-09) not all passed | Do not proceed to implementation |
| POOL gates (01-05) not all passed | Do not proceed to implementation |
| Code modification detected during review | Abort and report safety violation |

---

## 13. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| persistence_dir_created | ❌ false |
| engine_created | ❌ false |
| userrow_created | ❌ false |
| base_created | ❌ false |
| db_written | ❌ false |
| patch_applied | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

---

## 14. Carryover Blockers (8 preserved)

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

## R241_22C_PERSISTENCE_STAGE3_IMPLEMENTATION_PLAN_REVIEW_DONE

```
status=passed_with_warnings
persistence_stage3_plan_completed=true
implementation_allowed=false
surface010_unblocked=false
files_planned=5
sdb_mapping_completed=true
pool_mapping_completed=true
rollback_mapping_completed=true
memory_backend_contract_completed=true
no_route_registration=true
no_gateway_modification=true
db_written_at_import=false
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-22D
next_prompt_needed=user_selection
```

---

## 选项

**A.** R241-22D — Persistence Bundle Repositories (CAND-010/011/012/013) implementation plan
**B.** R241-22E — GSIC-003 / GSIC-004 unblock sequence design
**C.** R241-22F — Continue Auth Bundle Sub-Bundle D (CAND-004 reset_admin.py)
**D.** Pause R241-22, return to R241 mainline for CAND-016/CAND-017/CAND-020