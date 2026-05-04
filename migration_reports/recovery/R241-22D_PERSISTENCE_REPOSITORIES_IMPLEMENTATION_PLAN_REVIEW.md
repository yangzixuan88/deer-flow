# R241-22D Persistence Repositories Implementation Plan Review

**报告ID**: R241-22D_PERSISTENCE_REPOSITORIES_IMPLEMENTATION_PLAN_REVIEW
**生成时间**: 2026-04-29T14:30:00+08:00
**阶段**: Phase 22D — Persistence Repositories Implementation Plan Review
**前置条件**: R241-22C Persistence Stage 3 Plan Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: persistence_repositories_plan_completed_four_store_contracts_defined
**persistence_repositories_plan_completed**: true
**implementation_allowed**: false
**surface010_unblocked**: false

**关键结论**：
- 4 个文件：FeedbackRepository（CAND-010）、RunRepository（CAND-011）、DbRunEventStore（CAND-012）、JsonlRunEventStore（CAND-013）
- CAND-010/011/012 依赖 `session_factory`；CAND-013（JsonlRunEventStore）无 DB 依赖
- CAND-013（JSONL）是 memory backend 的天然候选——不依赖 SQLAlchemy
- FeedbackRepository 无上游 MemoryFeedbackStore 等效物；memory fallback 需要 deps.py 决策
- 实现顺序：FeedbackRepository + RunRepository（并行）→ DbRunEventStore → JsonlRunEventStore

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. Repository / Event Store File Inventory

### Files Overview

| File | Candidate | Type | LOC | SURFACE-010 | Route Reg | Gateway Mod |
|------|----------|------|-----|-------------|-----------|-------------|
| `persistence/feedback/sql.py` | CAND-010 | SQLAlchemy FeedbackRepository | ~200 | indirect | ❌ | ❌ |
| `persistence/run/sql.py` | CAND-011 | SQLAlchemy RunRepository | ~300 | indirect | ❌ | ❌ |
| `runtime/events/store/db.py` | CAND-012 | SQLAlchemy DbRunEventStore | ~250 | indirect | ❌ | ❌ |
| `runtime/events/store/jsonl.py` | CAND-013 | JSONL JsonlRunEventStore | ~160 | ❌ | ❌ | ❌ |

**Total**: 4 files, ~850 LOC
**No route registration**: ✅ guaranteed
**No gateway main path modification**: ✅ guaranteed
**CAND-013 memory backend compatible**: ✅ DB-independent

---

## 4. CAND-010 FeedbackRepository Contract

**文件**: `backend/packages/harness/deerflow/persistence/feedback/sql.py`
**行数**: ~200 LOC
**验证**: 上游内容已读取确认

### Init

```python
def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
    self._sf = session_factory
```

### Methods

| Method | user_id 来源 | 说明 |
|--------|-------------|------|
| `create(run_id, thread_id, rating, user_id=AUTO, ...)` | `resolve_user_id()` | rating must be +1 or -1 |
| `get(feedback_id, user_id=AUTO)` | `resolve_user_id()` | Returns None if not found or user mismatch |
| `list_by_run(thread_id, run_id, limit=100, user_id=AUTO)` | `resolve_user_id()` | — |
| `list_by_thread(thread_id, limit=100, user_id=AUTO)` | `resolve_user_id()` | — |
| `delete(feedback_id, user_id=AUTO)` | `resolve_user_id()` | Returns bool |
| `upsert(run_id, thread_id, rating, user_id=AUTO, comment=None)` | `resolve_user_id()` | Idempotent create/update |
| `delete_by_run(thread_id, run_id, user_id=AUTO)` | `resolve_user_id()` | Returns bool |
| `list_by_thread_grouped(thread_id, user_id=AUTO)` | `resolve_user_id()` | Returns dict[run_id, dict] |
| `aggregate_by_run(thread_id, run_id)` | None | SQL COUNT/SUM aggregation |

### Memory Backend Handling

- **无上游 MemoryFeedbackStore 等效物**
- `session_factory=None` 时，所有方法会 `AttributeError`
- **需要 deps.py 决策**：返回 None（no-op）还是实现内存版本

---

## 5. CAND-011 RunRepository Contract

**文件**: `backend/packages/harness/deerflow/persistence/run/sql.py`
**行数**: ~300 LOC
**验证**: 上游内容已读取确认

### Init

```python
def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
    self._sf = session_factory
```

### Key Methods

| Method | user_id 来源 | 说明 |
|--------|-------------|------|
| `put(run_id, thread_id, ..., user_id=AUTO)` | `resolve_user_id()` | metadata/kwargs JSON-serialized |
| `get(run_id, user_id=AUTO)` | `resolve_user_id()` | Returns None if not found |
| `list_by_thread(thread_id, user_id=AUTO, limit=100)` | `resolve_user_id()` | — |
| `update_status(run_id, status, error=None)` | **None** | Background worker path |
| `delete(run_id, user_id=AUTO)` | `resolve_user_id()` | — |
| `list_pending(before=None)` | **None** | Scheduler path |
| `update_run_completion(run_id, status, ...)` | **None** | Worker path |
| `aggregate_tokens_by_thread(thread_id)` | None | GROUP BY model_name |

### Memory Backend Handling

- **MemoryRunStore 已存在于** `runtime/runs/store/memory.py`
- deps.py 模式：`if sf is None: app.state.run_store = MemoryRunStore()`
- ✅ 天然兼容

---

## 6. CAND-012 DbRunEventStore Contract

**文件**: `backend/packages/harness/deerflow/runtime/events/store/db.py`
**行数**: ~250 LOC
**验证**: 上游内容已读取确认

### Init

```python
def __init__(self, session_factory: async_sessionmaker[AsyncSession], *, max_trace_content: int = 10240) -> None:
    self._sf = session_factory
    self._max_trace_content = max_trace_content
```

### Seq Assignment Contract

```
put() / put_batch():
  async with session.begin():
    max_seq = SELECT MAX(seq) WHERE thread_id FOR UPDATE
    seq = (max_seq or 0) + 1
    INSERT RunEventRow with seq
```

**SQLite 注意**: `with_for_update()` 是 no-op；依赖 `UNIQUE(thread_id, seq)` 约束 catch races

### User ID Stamp Contract

```python
_user_id_from_context():
  user = get_current_user()  # from ContextVar
  return str(user.id) if user is not None else None
```

- Background workers → `None`（无 contextvar）
- HTTP requests → `str(user.id)`（auth middleware 设置）

### Trace Truncation

```python
if category == 'trace' and len(encoded) > 10240:
    content = encoded[:10240].decode('utf-8', errors='ignore')
    metadata['content_truncated'] = True
```

### Memory Backend Handling

- 无内置 memory fallback
- **Memory backend 选择**：使用 JsonlRunEventStore（CAND-013）代替

---

## 7. CAND-013 JsonlRunEventStore Contract

**文件**: `backend/packages/harness/deerflow/runtime/events/store/jsonl.py`
**行数**: ~160 LOC
**验证**: 上游内容已读取确认

### Init

```python
def __init__(self, base_dir: str | Path | None = None) -> None:
    self._base_dir = Path(base_dir) if base_dir else Path('.deer-flow')
    self._seq_counters: dict[str, int] = {}  # thread_id → max seq
```

### File Path

```
.deer-flow/threads/{thread_id}/runs/{run_id}.jsonl
```

### Seq Management

| Method | Behavior |
|--------|----------|
| `_ensure_seq_loaded(thread_id)` | 首次访问时扫描所有 `*.jsonl` 文件，恢复 max seq |
| `_next_seq(thread_id)` | 进程内计数器 +1，无锁，无跨进程安全 |
| **多进程风险** | 每个进程独立计数器；可能产生重复 seq |

### Known Trade-off

```
list_messages(thread_id) — 必须扫描所有 run 文件（跨 run seq 排序）
list_events(thread_id, run_id) — 只读单个文件（快速路径）
```

### Memory Backend Compatibility

✅ **CAND-013 是 memory backend 的推荐 event store**

---

## 8. session_factory Dependency Contract

| File | `__init__` 参数 | `None` 时行为 |
|------|---------------|--------------|
| CAND-010 FeedbackRepository | `session_factory: async_sessionmaker` | AttributeError（无 fallback） |
| CAND-011 RunRepository | `session_factory: async_sessionmaker` | 用 MemoryRunStore 替代 ✅ |
| CAND-012 DbRunEventStore | `session_factory: async_sessionmaker` | 用 JsonlRunEventStore 替代 ✅ |
| CAND-013 JsonlRunEventStore | `base_dir: str \| Path` | 无 DB 依赖 |

### deps.py Pattern

```python
sf = get_session_factory()

if sf is None:
    # memory backend
    app.state.run_store = MemoryRunStore()
    app.state.feedback_repo = None  # decision needed
    app.state.event_store = JsonlRunEventStore()
else:
    app.state.run_store = RunRepository(sf)
    app.state.feedback_repo = FeedbackRepository(sf)
    app.state.event_store = DbRunEventStore(sf)
```

---

## 9. database.backend=memory Fallback Behavior

| Component | `backend=memory` 行为 | Memory 等效 |
|-----------|----------------------|-------------|
| **RunStore** | `get_session_factory() → None` | `MemoryRunStore()` ✅ |
| **FeedbackRepository** | `get_session_factory() → None` | ❌ 无等效物 |
| **EventStore** | 选择 JsonlRunEventStore | `.deer-flow/` 文件系统 |

### Open Decision: FeedbackRepository Memory Fallback

| Option | Description |
|--------|-------------|
| **Option 1（推荐）** | `feedback_repo = None` — feedback 操作 no-op |
| **Option 2** | 实现 `MemoryFeedbackStore`（dict） |
| **Option 3** | `raise NotImplementedError` |

---

## 10. JSONL Write Path and Retention Contract

### Write Path

```python
def _write_record(self, record: dict) -> None:
    path = self._run_file(record["thread_id"], record["run_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", ...) as f:
        f.write(json.dumps(record) + "\n")
```

- **Append mode** — 只追加，不截断
- **每行一条 JSON 记录**
- **无事务** — 进程崩溃可能产生 partial line

### Retention

| 方面 | 状态 |
|------|------|
| 自动清理 | ❌ 无 |
| 磁盘空间风险 | ⚠️ 无界增长 |
| 截断机制 | ❌ JsonlRunEventStore 不截断（DbRunEventStore 截断 trace） |

### Deletion Triggers

```
delete_by_thread(thread_id) → 删除 thread 下所有 run 文件
delete_by_run(thread_id, run_id) → 删除单个 run 文件
```

---

## 11. DB Event Write Transaction Contract

### Seq Assignment Atomicity

| Backend | Lock Mechanism | Race Protection |
|---------|---------------|-----------------|
| **Postgres** | `FOR UPDATE` on `SELECT MAX(seq)` | Serialized within thread |
| **SQLite** | `with_for_update()` is no-op | `UNIQUE(thread_id, seq)` catches races |

### Transaction Boundaries

| Operation | Scope |
|-----------|-------|
| `put()` | `session.begin()` — single event |
| `put_batch()` | `session.begin()` — all events in batch |
| Read operations | Per-call session — no long transactions |

### Write Paths Without User Filter

- `put()` — user_id from contextvar (None for workers)
- `put_batch()` — user_id from contextvar (None for workers)

---

## 12. Repository Read/Write Safety Model

### User Isolation

| Path | Write Stamp | Read Filter |
|------|------------|-------------|
| HTTP request | `str(user.id)` from contextvar | `resolve_user_id(param)` |
| Background worker | `None` (contextvar unset) | — |

### Concurrent Write Safety

| Store | Mechanism | Multi-Process Safe |
|-------|-----------|-------------------|
| DbRunEventStore | `FOR UPDATE` + `UNIQUE` constraint | ✅ |
| JsonlRunEventStore | In-process `_seq_counters` | ❌ |

### Data Corruption

| Store | Prevention |
|-------|------------|
| DbRunEventStore | `session.commit()` atomic; partial writes rollback |
| JsonlRunEventStore | Append-only; crash mid-write → partial JSON line |

---

## 13. Test File Plan

| File ID | Test File | Cases | Framework | Duration |
|---------|-----------|-------|----------|----------|
| TF-10 | `tests/unit/persistence/test_feedback_repository.py` | create/get/upsert/delete, user isolation, aggregate | pytest-asyncio | 15s |
| TF-11 | `tests/unit/persistence/test_run_repository.py` | put/get/list, status update, token aggregation, memory fallback | pytest-asyncio | 15s |
| TF-12 | `tests/unit/events/store/test_db_event_store.py` | seq assignment, FOR UPDATE, pagination, truncation, contextvar stamp | pytest-asyncio | 20s |
| TF-13 | `tests/unit/events/store/test_jsonl_event_store.py` | put/list_messages (slow path), list_events (fast path), delete, id validation | pytest-asyncio | 15s |
| TF-14 | `tests/unit/events/store/test_event_store_compatibility.py` | Both implement RunEventStore, interface compliance, backend selection | pytest | 10s |

**Total**: 5 test files, ~40 cases, ~75 seconds

---

## 14. Implementation Order (After CAND-009)

| Step | File | Reason | Parallel |
|------|------|--------|----------|
| **1** | `persistence/feedback/sql.py` (CAND-010) | Depends on FeedbackRow model | ✅ with step 2 |
| **2** | `persistence/run/sql.py` (CAND-011) | Depends on RunRow model; MemoryRunStore fallback available | ✅ with step 1 |
| **3** | `runtime/events/store/db.py` (CAND-012) | Depends on RunEventRow model + session_factory | After 1+2 |
| **4** | `runtime/events/store/jsonl.py` (CAND-013) | No DB dependency; memory backend alternative | Independent |

---

## 15. Explicit Stop Conditions

| Condition | Action |
|-----------|--------|
| SURFACE-010 not yet unblocked | Do not implement repositories |
| CAND-009 (engine.py) not yet implemented | All depend on session_factory |
| Authorization scope does not expand | Design only, no file creation |
| FeedbackRepository memory fallback unresolved | Decision needed before implementation |
| Code modification detected during review | Abort and report safety violation |

---

## 16. Rollback / Cleanup Requirements

| If... | Cleanup |
|-------|---------|
| FeedbackRepository created | No persistent state to clean |
| RunRepository created | No persistent state (MemoryRunStore has no disk state) |
| DbRunEventStore created | No cleanup needed |
| JsonlRunEventStore created | Delete `.deer-flow/` directory if events written |
| session_factory used | `close_engine()` releases all connections |

**No schema migration needed**: `create_all` is idempotent (`CREATE TABLE IF NOT EXISTS`)

---

## 17. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| feedback_repository_created | ❌ false |
| run_repository_created | ❌ false |
| db_event_store_created | ❌ false |
| jsonl_event_store_created | ❌ false |
| db_written | ❌ false |
| jsonl_written | ❌ false |
| gateway_app_modified | ❌ false |
| deps_py_modified | ❌ false |
| patch_applied | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

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

## R241_22D_PERSISTENCE_REPOSITORIES_IMPLEMENTATION_PLAN_REVIEW_DONE

```
status=passed_with_warnings
persistence_repositories_plan_completed=true
implementation_allowed=false
surface010_unblocked=false
files_planned=[feedback/sql.py, run/sql.py, events/store/db.py, events/store/jsonl.py]
repository_contracts_completed=true
event_store_contracts_completed=true
jsonl_retention_contract_completed=true
db_transaction_contract_completed=true
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
db_written=false
jsonl_written=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-22E
next_prompt_needed=user_selection
```

---

## 选项

**A.** R241-22E — GSIC-003 / GSIC-004 unblock sequence design
**B.** R241-22F — Auth Bundle Sub-Bundle D (CAND-004 reset_admin.py) implementation plan
**C.** R241-22G — Gateway Deps (deps.py) + App (CAND-018) implementation plan
**D.** Pause R241-22, return to R241 mainline for CAND-016/CAND-017/CAND-020