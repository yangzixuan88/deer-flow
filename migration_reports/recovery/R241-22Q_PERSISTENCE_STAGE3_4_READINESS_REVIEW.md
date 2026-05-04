# R241-22Q Persistence Stage 3+4 Readiness Review

**报告ID**: R241-22Q_PERSISTENCE_STAGE3_4_READINESS_REVIEW
**生成时间**: 2026-04-29T19:30:00+08:00
**阶段**: Phase 22Q — Persistence Stage 3+4 Readiness Review
**前置条件**: R241-22K Mainline Parallel Candidate Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: persistence_stage3_4_readiness_confirmed_dt002_unblock_required
**DT-001 resolved**: true (user_context.py — R241-22O confirmed)
**DT-002 still blocking**: true (engine.py — blocks SQLiteUserRepository, reset_admin, OAuth, FeedbackRepository)

**关键结论**：
- Stage 3+4 共 20 个 upstream 文件，结构清晰
- `engine.py` 是 DT-002 根源，必须先于任何数据库操作被 port
- `feedback/sql.py` 依赖 `resolve_user_id`（user_context.py / DT-001），但 DT-001 已确认 resolved
- `FeedbackRepository` 9 个方法全部使用 `resolve_user_id`，session-per-method 模式
- Memory backend 可独立验证；SQLite/Postgres 必须等 DT-002
- 并行化可行：5 个 model 文件可独立 port，1 个 memory.py 可独立 port

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. Stage 3+4 Complete File Inventory

### Upstream File Tree (20 files)

```
persistence/
├── __init__.py
├── base.py                          ← Base(DeclarativeBase) + to_dict()
├── engine.py                        ← DT-002 根源: init_engine/get_session_factory
├── feedback/
│   ├── __init__.py
│   ├── model.py                     ← FeedbackRow
│   └── sql.py                       ← FeedbackRepository (9 methods, depends on resolve_user_id)
├── migrations/
│   └── env.py
├── models/
│   ├── __init__.py
│   └── run_event.py                ← RunEventRow
├── run/
│   ├── __init__.py
│   ├── model.py                    ← RunRow
│   └── sql.py                      ← RunRepository (CRUD)
├── thread_meta/
│   ├── __init__.py
│   ├── base.py                     ← ThreadMetaStore (abstract)
│   ├── memory.py                   ← InMemoryThreadMetaStore
│   ├── model.py                    ← ThreadMetaRow + partial unique idx
│   └── sql.py                      ← SQLThreadMetaStore
└── user/
    ├── __init__.py
    └── model.py                    ← UserRow + partial unique idx (oauth)
```

### File Classification

| 文件 | Stage | 运行时依赖 | 可独立测试 |
|------|-------|-----------|-----------|
| `persistence/base.py` | 3 | None | ✅ |
| `persistence/engine.py` | 3 | None (DT-002 root) | ⚠️ blocked |
| `persistence/user/model.py` | 3 | None | ✅ |
| `persistence/user/__init__.py` | 3 | None | ✅ |
| `persistence/thread_meta/base.py` | 3 | None | ✅ |
| `persistence/thread_meta/model.py` | 3 | None | ✅ |
| `persistence/thread_meta/memory.py` | 3 | thread_store (mock) | ✅ |
| `persistence/thread_meta/sql.py` | 3 | engine | ⚠️ blocked |
| `persistence/run/model.py` | 4 | None | ✅ |
| `persistence/run/sql.py` | 4 | engine | ⚠️ blocked |
| `persistence/models/run_event.py` | 4 | None | ✅ |
| `persistence/run_event.py` | 4 | None | ✅ |
| `persistence/feedback/model.py` | 4 | None | ✅ |
| `persistence/feedback/sql.py` | 4 | engine + resolve_user_id | ⚠️ blocked |
| `persistence/migrations/env.py` | 4 | engine | ⚠️ blocked |

---

## 4. DT-002 Unblock Dependency Chain

### DT-002 Root Cause

`backend/packages/harness/deerflow/persistence/engine.py`:
- `get_session_factory()` → `async_sessionmaker` or `None`
- Memory backend: returns early, `get_session_factory()` returns `None`
- SQLite backend: initializes `create_async_engine` with WAL
- Postgres backend: initializes `create_async_engine` with pool

### Dependency Tree

```
engine.py (DT-002 根源)
├── get_session_factory() — 所有 DB 操作的前置
├── SQLiteUserRepository — 需要 session_factory
│   └── reset_admin() — 依赖 SQLiteUserRepository
├── OAuth integration — 需要 UserRow + SQLiteUserRepository
├── feedback/sql.py — FeedbackRepository
│   └── resolve_user_id() — 来自 user_context.py (DT-001 已 resolved ✅)
├── thread_meta/sql.py — SQLThreadMetaStore
│   └── get_session_factory()
├── run/sql.py — RunRepository
│   └── get_session_factory()
└── persistence/migrations/env.py
    └── 需要 engine 初始化后方可运行
```

### Resolution Order

1. **Step 1**: Port `engine.py` — 解 DT-002
2. **Step 2**: `persistence/user/model.py` + `persistence/user/__init__.py`
3. **Step 3**: `SQLiteUserRepository` + `reset_admin`
4. **Step 4**: OAuth integration (建立在 UserRow 基础上)
5. **Step 5**: `thread_meta/sql.py`, `run/sql.py`, `feedback/sql.py`
6. **Step 6**: Migrations

---

## 5. Minimal Implementation Order

### Phase 1 — Engine Core (DT-002 解锁)

1. `persistence/base.py` — `Base(DeclarativeBase)` + `to_dict()`
2. `persistence/engine.py` — `init_engine`, `get_session_factory`, `close_engine`

### Phase 2 — User Repository (DT-002 解锁后)

3. `persistence/user/model.py` — `UserRow`
4. `persistence/user/__init__.py` — exports
5. `backend/app/gateway/auth/repositories/sqlite.py` — `SQLiteUserRepository`
6. `reset_admin()` function

### Phase 3 — Thread Meta (可并行)

7. `persistence/thread_meta/base.py` — `ThreadMetaStore` abstract
8. `persistence/thread_meta/model.py` — `ThreadMetaRow`
9. `persistence/thread_meta/memory.py` — `InMemoryThreadMetaStore`
10. `persistence/thread_meta/sql.py` — `SQLThreadMetaStore`

### Phase 4 — Run / Feedback (可并行, 依赖 engine)

11. `persistence/run/model.py` — `RunRow`
12. `persistence/run/sql.py` — `RunRepository`
13. `persistence/models/run_event.py` — `RunEventRow`
14. `persistence/feedback/model.py` — `FeedbackRow`
15. `persistence/feedback/sql.py` — `FeedbackRepository` (9 methods)

### Phase 5 — OAuth (DT-002 + User 解锁后)

16. OAuth integration in `routers/auth.py` (501 placeholders → real impl)

### Phase 6 — Migrations

17. `persistence/migrations/env.py` — Alembic setup

---

## 6. Parallelizable Files

以下文件可在 `engine.py` port 之后独立并行进行：

| 文件 | 原因 | 前置 |
|------|------|------|
| `persistence/user/model.py` | 无运行时依赖 | engine.py |
| `persistence/feedback/model.py` | 无运行时依赖 | engine.py |
| `persistence/run/model.py` | 无运行时依赖 | engine.py |
| `persistence/models/run_event.py` | 无运行时依赖 | engine.py |
| `persistence/thread_meta/memory.py` | 仅依赖 `get_thread_store` interface | engine.py + thread_meta/base.py |

**并行策略**: Phase 2+3 并行化 user/thread_meta model 文件，Phase 4+5 并行化 run/feedback model 文件。

---

## 7. Non-Parallelizable Files

| 文件 | 原因 |
|------|------|
| `persistence/engine.py` | DT-002 根源；所有数据库操作都依赖 `get_session_factory()` |
| `persistence/feedback/sql.py` | 所有 9 个方法都调用 `get_session_factory()`；依赖 `resolve_user_id` |
| `persistence/thread_meta/sql.py` | 需要 `get_session_factory()` |
| `persistence/run/sql.py` | 需要 `get_session_factory()` |
| `persistence/migrations/env.py` | 需要 engine 初始化后方可运行 |

---

## 8. Memory Backend Fallback Readiness

### Memory Backend Behavior

```python
# engine.py
def init_engine(backend="memory", url=None, echo=False, pool_size=5, sqlite_dir=None):
    if backend == "memory":
        logger.info("Using in-memory persistence (no database)")
        return  # early return — get_session_factory() returns None
```

### Readiness Assessment

| 检查项 | 状态 |
|--------|------|
| memory path 不调用 engine | ✅ true |
| `get_session_factory()` 在 memory mode 返回 None | ✅ confirmed |
| thread_meta/memory.py 可独立工作 | ✅ confirmed |
| 需要 session_factory 的模块在 memory mode 不被调用 | ✅ confirmed |
| **Memory backend ready** | ✅ **true** |

---

## 9. SQLite Backend Readiness

### SQLite Backend Behavior

- Backend: `init_engine(backend="sqlite")`
- URL: `sqlite+aiosqlite:///{sqlite_dir}/deerflow.db` 或自定义 URL
- WAL mode enabled: `connect_args={"check_same_thread": False}` + URL params

### Readiness Assessment

| 检查项 | 状态 |
|--------|------|
| `engine.py` ported | ❌ blocked (DT-002) |
| `create_async_engine` with SQLite | ❌ blocked |
| `async_sessionmaker` configured | ❌ blocked |
| `SQLiteUserRepository` ported | ❌ blocked |
| **SQLite backend ready** | ❌ **false** |

---

## 10. Postgres Backend Readiness

### Postgres Backend Behavior

- URL: `postgresql+asyncpg://{url}`
- Pool: `pool_size` parameter passed to `create_async_engine`
- 尚未确定连接字符串配置方式（环境变量 / config file）

### Readiness Assessment

| 检查项 | 状态 |
|--------|------|
| `engine.py` ported | ❌ blocked (DT-002) |
| `create_async_engine` with asyncpg | ❌ blocked |
| Connection string config | ❌ not designed |
| Pool sizing strategy | ❌ not designed |
| **Postgres backend ready** | ❌ **false** |

---

## 11. DB Write Safety Gates

### Required Gates

| Gate | Condition | Action if Violated |
|------|-----------|-------------------|
| `session_factory is not None` | 所有 DB write 前检查 | Abort — engine not initialized |
| `backend != "memory"` | User/ThreadMeta write 前检查 | Memory backend 不支持持久化写 |
| `resolve_user_id` succeeds | feedback write 前检查 | Raise — invalid user context |
| WAL mode confirmed | SQLite write 前检查 | Abort — unsafe concurrent writes |

### JSONL Safety Gate

```python
# Required check before any JSONL write:
if not os.environ.get("DEERFLOW_JSONL_WRITES_ENABLED", "").lower() in ("1", "true", "yes"):
    raise RuntimeError("JSONL writes are disabled. Set DEERFLOW_JSONL_WRITES_ENABLED=1 to enable.")
```

---

## 12. Repository Transaction Safety Gates

### Session-Per-Method Pattern

每个 repository 方法独立获取 session，commit，close：

```python
async def create(self, obj: FeedbackRow, user_id: str | None = None) -> FeedbackRow:
    user_id = resolve_user_id(user_id, method_name="FeedbackRepository.create")
    async with get_session_factory()() as session:
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
    return obj
```

### Required Gates

| Gate | Location | Condition |
|------|----------|-----------|
| `get_session_factory()()` 非 None | 每个方法 | engine 未初始化则 abort |
| `user_id is not None` | 每个需要 user_id 的方法 | resolve_user_id 失败则 raise |
| Rollback on exception | 每个 `async with` block | `await session.rollback()` |

---

## 13. Test Readiness Matrix

| File | Unit Test Status | Integration Test Status | Notes |
|------|-----------------|------------------------|-------|
| `persistence/base.py` | ✅ ready | ⚠️ blocked | 仅依赖 SQLAlchemy inspect |
| `persistence/engine.py` | ✅ ready | ⚠️ blocked | DT-002 blocks integration |
| `persistence/user/model.py` | ✅ ready | ⚠️ blocked | needs engine for integration |
| `persistence/thread_meta/base.py` | ✅ ready | ⚠️ blocked | needs engine for integration |
| `persistence/thread_meta/memory.py` | ✅ ready | ✅ ready | mock thread_store 即可 |
| `persistence/thread_meta/model.py` | ✅ ready | ⚠️ blocked | needs engine for integration |
| `persistence/thread_meta/sql.py` | ✅ ready | ⚠️ blocked | needs engine for integration |
| `persistence/run/model.py` | ✅ ready | ⚠️ blocked | needs engine for integration |
| `persistence/run/sql.py` | ✅ ready | ⚠️ blocked | needs engine for integration |
| `persistence/models/run_event.py` | ✅ ready | ⚠️ blocked | needs engine for integration |
| `persistence/feedback/model.py` | ✅ ready | ⚠️ blocked | needs engine for integration |
| `persistence/feedback/sql.py` | ✅ ready | ⚠️ blocked | needs engine + resolve_user_id |

### Test Strategy

- **Unit tests**: 所有 model 文件 + `base.py` + `memory.py` 可直接写 unit tests
- **Integration tests**: 等待 `engine.py` port 后，使用 SQLite in-memory test database
- **Mock strategy**: `patch("deerflow.persistence.engine.get_session_factory")` 用于隔离测试

---

## 14. Rollback / Cleanup Requirements

| Condition | Action |
|-----------|--------|
| `engine.py` port 失败 | 不需要 rollback；无文件写入 |
| `user/model.py` port 失败 | 不需要 rollback；无 DB 操作 |
| SQLite migration 失败 | 需要 `deerflow.db-journal` 清理脚本 |
| Postgres migration 失败 | 需要 manual `psql` cleanup |

### Cleanup Script Template

```bash
# SQLite rollback
rm -f "$sqlite_dir/deerflow.db"
rm -f "$sqlite_dir/deerflow.db-journal"

# Verify no orphaned WAL files
ls "$sqlite_dir/deerflow.db"*
```

---

## 15. Stop Conditions

| Condition | Action |
|-----------|--------|
| `engine.py` 未 port 情况下任何 DB 操作 | Abort |
| Memory backend 模式下任何持久化写操作 | Abort |
| `get_session_factory()` 返回 None 时 write | Abort |
| JSONL writes 未显式 enable | Abort |
| Migration 在非测试环境运行 | Abort — 需要 explicit auth |

---

## 16. Exact Condition for Future Authorization

**Authorization grants when**:
1. `persistence/engine.py` 已 port 到本地 working tree
2. `backend/app/gateway/auth/repositories/sqlite.py` — `SQLiteUserRepository` 已实现
3. `deerflow.runtime.user_context` — `resolve_user_id()` 已在本地 working tree
4. RootGuard 全部 PASSED
5. 所有 8 carryover blockers 仍然 preserved（未修改）

**Authorization scope**:
- `persistence/engine.py` 的 port（唯一解除 DT-002 的操作）
- 后续 repository port 操作需要独立授权

---

## 17. Parallel Track Summary

| Track | Status | Blocked By |
|-------|--------|------------|
| Auth Bundle A-F design | ✅ 100% complete | SURFACE-010, GSIC-003/004 |
| Auth Bundle E test implementation | ✅ 3 files created (50 test cases) | None |
| CAND-017 PR #2645 | 🔵 OPEN, awaiting review | None |
| CAND-016 quarantine | ✅ Preserved | SURFACE-010 (DT-003) |
| CAND-020/CAND-021 removed | ✅ Confirmed | None |
| **Persistence Stage 3+4** | 🔶 blocked | **DT-002 (engine.py)** |

---

## 18. Carryover Blockers (8 preserved)

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

## R241_22Q_PERSISTENCE_STAGE3_4_READINESS_REVIEW_DONE

```
status=passed_with_warnings
decision=persistence_stage3_4_readiness_confirmed_dt002_unblock_required
dt001_resolved=true
dt002_still_blocking=true
stage3_4_file_count=20
parallelizable_count=5
non_parallelizable_count=5
memory_backend_ready=true
sqlite_backend_ready=false
postgres_backend_ready=false
db_write_gate_required=true
jsonl_write_gate_required=true
repository_transaction_gate_required=true
test_readiness_matrix_complete=true
rollback_required=false
stop_conditions_preserved=true
safety_violations=[]
blockers_preserved=true
recommended_resume_point=R241-22G_when_dt002_cleared
next_prompt_needed=user_selection
```

---

## 选项

**A.** R241-22G — GSIC-003 + GSIC-004 COUPLED unblock design（需要 SURFACE-010 + Auth Bundle C + Persistence Stage 3+4 全部完成）

**B.** R241-22R — R241-22O test files porting guide for Auth Bundle E production modules（将 50 个 test cases 的 import 替换为真实 module path，生成 porting guide）

**C.** R241-22S — Parallel port of parallelizable Stage 3+4 model files（user/model.py, thread_meta/model.py, run/model.py, feedback/model.py, models/run_event.py — 不含 engine.py）

**D.** Pause R241-22 until SURFACE-010 and DT-002 are unblocked
