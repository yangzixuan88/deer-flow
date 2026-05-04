# R135C: Auth+CSRF Harness HTTP Endpoint Retry

## Status: PASSED

## Summary

After fixing the AuthMiddleware internal auth ordering (R135B), the HTTP endpoint retry confirms:
- **Auth internal header** bypasses cookie requirement → 200
- **CSRF validation** correctly blocks without matching cookie/header → 403
- **Thread create** with Option C (internal auth + manual CSRF) → 200
- **Thread get** after fixing `app.state.thread_meta_repo` → 200
- **POST /runs** blocked by `stream_bridge not available` (503) → requires R136

## LANE 5: Store Isolation Feasibility

### Finding

The 503 "Thread metadata store not available" on GET /api/threads/{thread_id} was caused by TWO separate attributes:

1. `app.state.thread_store` — returned by `get_thread_store()` (used by create_thread)
2. `app.state.thread_meta_repo` — returned by `get_thread_meta_repo()` (used by authz.py owner_check in GET endpoint)

Both must be set for full endpoint coverage.

### Root Cause Analysis

```python
# deps.py has TWO separate stores:
get_thread_store = _require("thread_store", "Thread metadata store")  # line 140-145
get_thread_meta_repo = _require("thread_meta_repo", "Thread metadata store")  # line 279

# authz.py calls get_thread_meta_repo BEFORE get_thread_store in owner_check:
from app.gateway.deps import get_thread_meta_repo
thread_meta_repo = get_thread_meta_repo(request)  # FIRST call — raises 503!
from app.gateway.deps import get_thread_store
thread_store = get_thread_store(request)
```

### Monkey-Patch Approach (LANE 5 Option A)

```python
# Before TestClient creation:
app.state.checkpointer = InMemorySaver()
app.state.thread_store = InlineMemoryThreadMetaStore()  # For create_thread
app.state.thread_meta_repo = InlineMemoryThreadMetaStore()  # For get_thread owner_check
```

### Results

| Endpoint | Without Fix | With Fix |
|----------|-------------|----------|
| POST /api/threads | 503 | 200 |
| GET /api/threads/{thread_id} | 503 | 200 |
| POST /api/threads/{thread_id}/runs | 503 | 503 (stream_bridge missing) |

## LANE 6: GET /api/threads/{thread_id}

- **Status**: 200
- **Thread ID Reused**: Yes (from LANE 5 creation)
- **Detail**: GET works when both `app.state.thread_store` AND `app.state.thread_meta_repo` are set

## LANE 7: POST /api/threads/{thread_id}/runs

### Error

`Stream bridge not available` (503)

### Source

`get_stream_bridge()` in deps.py → `app.state.stream_bridge`

### Root Cause

`StreamBridge` is initialized inside `langgraph_runtime()` async context manager, which is only invoked during FastAPI lifespan startup. TestClient does not run lifespan.

### Required For

- POST /runs
- POST /runs/stream
- POST /runs/wait

### Next Step

Either:
1. **R135D**: Find if StreamBridge can be constructed without full runtime context
2. **R136**: Accept stream_bridge as a precondition and proceed with model authorization testing

## Constraints

All constraints from R135 specification preserved:

- No code modification
- No DB writes
- No model API calls
- No MCP runtime
- No JSONL writes
- No gateway server start

## Result Classification

| Check | Status |
|-------|--------|
| Auth internal header works | Pass |
| CSRF validation works | Pass |
| Thread create works | Pass |
| Thread get works | Pass |
| POST /runs works | Fail (stream_bridge) |

**R135C Result**: PASSED — Auth and CSRF fixed; thread CRUD works; next blocker is StreamBridge for POST /runs.

## Recommended Next Phase

**R135D**: Stream Bridge Bypass or Isolation Feasibility

- Determine if StreamBridge can be monkey-patched without full runtime
- If not possible, skip to R136 (model authorization with real gateway)

**Primary Blocker for R136**: `app.state.stream_bridge` — StreamBridge not initialized without full lifespan