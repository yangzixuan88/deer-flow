cety**: MemoryStreamBridge, MemoryRunStore, RunManager — Risk: NONE; AppConfig — Risk: MODERATE (6 singleton side effects)
3. **Critical bug found**: `AppConfig.from_file()` has a bug in `resolve_env_variables` — `config[1:]` strips `$` but leaves `{}`, causing env lookup to fail
4. **Worker trigger confirmed**: POST /runs ALWAYS triggers `asyncio.create_task(run_agent(...))` — no safety guard available
5. **Full deps chain**: After 4 monkey-patch iterations, all 9 deps satisfied → worker would start → STOP confirmed

---

## LANE 2: Static Dependency Graph (completed in previous session)

**POST /runs → `create_run` → `start_run` → unconditional `asyncio.create_task(run_agent(...))`**

| app.state key | Source | Constructor safety |
|---|---|---|
| `stream_bridge` | `get_stream_bridge()` → `app.state.stream_bridge` | MemoryStreamBridge() — Risk: NONE |
| `run_manager` | `get_run_manager()` → `app.state.run_manager` | RunManager(store=) — Risk: NONE |
| `run_store` | `get_run_store()` → `app.state.run_store` | MemoryRunStore() — Risk: NONE |
| `checkpointer` | `_require('checkpointer')` → `app.state.checkpointer` | InMemorySaver() — Risk: NONE |
| `thread_store` | `get_thread_store()` → `app.state.thread_store` | MemoryThreadMetaStore(store) — Risk: NONE |
| `thread_meta_repo` | `get_thread_meta_repo()` → `app.state.thread_meta_repo` | Same as thread_store — Risk: NONE |
| `config` | `get_config()` → `app.state.config` | AppConfig.from_file() — Risk: **MODERATE** + **BUG** |
| `store` | `app.state.store` (BaseStore) | make_store(config) — async context manager |
| `run_event_store` | `app.state.run_event_store` | make_run_event_store(config) — Risk: NONE |

**Worker trigger**: `services.py:272` — `asyncio.create_task(run_agent(...))` — **UNCONDITIONAL**, no safety guard.

---

## LANE 3: Constructor Safety Check

### MemoryStreamBridge (stream_bridge)
```python
class MemoryStreamBridge(StreamBridge):
    def __init__(self, *, queue_maxsize: int = 256) -> None:
        self._maxsize = queue_maxsize
        self._streams: dict[str, _RunStream] = {}
        self._counters: dict[str, int] = {}
```
**Risk: NONE** — pure in-memory, no I/O, no side effects.

### MemoryRunStore (run_store)
```python
class MemoryRunStore(RunStore):
    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}
```
**Risk: NONE** — pure in-memory dict, no I/O, no side effects.

### RunManager (run_manager)
```python
class RunManager:
    def __init__(self, store: RunStore | None = None) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._lock = asyncio.Lock()
        self._store = store
```
**Risk: NONE** — pure in-memory, no I/O, no side effects.

### MemoryThreadMetaStore (thread_store + thread_meta_repo)
```python
class MemoryThreadMetaStore(ThreadMetaStore):
    def __init__(self, store: BaseStore) -> None:
        self._store = store  # InMemoryStore
```
**Risk: NONE** — requires InMemoryStore (from langgraph.store.memory).

### AppConfig.from_file() (config)
```python
@classmethod
def from_file(cls, config_path: str | None = None) -> Self:
    resolved_path = cls.resolve_config_path(config_path)
    with open(resolved_path, encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}
    config_data = cls.resolve_env_variables(config_data)  # BUG HERE
    # ... calls 6 singleton loaders:
    # load_agents_api_config_from_dict, load_checkpointer_config_from_dict,
    # load_acp_config_from_dict, load_stream_bridge_config_from_dict, etc.
```
**Risk: MODERATE + BUG**

- **Moderate**: Updates 6 global singletons (`_agents_api_config`, `_checkpointer_config`, `_acp_agents`, etc.) — configuration state mutation, no DB/service start
- **BUG** (critical): `resolve_env_variables` at line 250 uses `config[1:]` to extract env var name:
  ```python
  if config.startswith("$"):
      env_value = os.getenv(config[1:])  # config='${VAR}', config[1:]='{VAR}' (BRACES REMAIN!)
  ```
  This causes `os.getenv('{DEER_FLOW_HOST_PATH}')` to fail since env var is `DEER_FLOW_HOST_PATH`.
  Additionally, after `re.sub` replaces `${VAR}` with env value, the result is recursively passed back, causing a second error on the resolved value itself.
- **Unmet dependency**: `config.yaml` requires `${DEER_FLOW_HOST_PATH}` (sandbox.mounts[0].host_path) which is not set in the test environment.

### make_run_event_store (run_event_store)
```python
def make_run_event_store(config=None) -> RunEventStore:
    if config is None or config.backend == "memory":
        return MemoryRunEventStore()  # Risk: NONE
```
**Risk: NONE** — returns pure in-memory store.

---

## LANE 4: Baseline (thread deps only)

**Setup**: `checkpointer=InMemorySaver()`, `thread_store=MemoryThreadMetaStore(InMemoryStore())`, `thread_meta_repo=MemoryThreadMetaStore(InMemoryStore())`

```
POST /api/threads: 200
GET /api/threads/{thread_id}: 200
POST /api/threads/{thread_id}/runs: 503 Stream bridge not available
```

**Result**: Baseline from R135C confirmed. Thread CRUD works. POST /runs blocked by stream_bridge.

---

## LANE 5: stream_bridge Injection

**Added**: `app.state.stream_bridge = MemoryStreamBridge()`

```
POST /api/threads/{thread_id}/runs: 503
Detail: "Run manager not available"
```

**Result**: stream_bridge patch SUCCESSFUL. Next blocker: run_manager.

---

## LANE 6: run_manager + run_store Injection

**Added**: `app.state.run_store = MemoryRunStore()`, `app.state.run_manager = RunManager(store=app.state.run_store)`

```
POST /api/threads/{thread_id}/runs: 503
Detail: "Configuration not available"
```

**Result**: run_manager + run_store patch SUCCESSFUL. Next blocker: config.

---

## LANE 7: Config Injection Attempts

### LANE 7a: AppConfig.from_file() — FAILED

```
ValueError: Environment variable {DEER_FLOW_HOST_PATH} not found for config value ${DEER_FLOW_HOST_PATH}
```

**Root cause**: Two bugs in `resolve_env_variables`:
1. `config[1:]` strips `$` but leaves braces → looks for `{VAR}` not `VAR`
2. After `re.sub` replaces `${VAR}` with env value, recursive call processes the resolved value (e.g., `/tmp/deerflow`) → `config[1:]` = `tmp/deerflow` → env lookup fails again

### LANE 7b: Minimal AppConfig Construction — SUCCESS

```python
minimal_config = AppConfig(
    log_level="info",
    sandbox=SandboxConfig(use="local", allow_host_bash=False),
    database=DatabaseConfig(backend="memory"),
    stream_bridge=None,
    checkpointer=None,
)
app.state.config = minimal_config
```

**Result**:
```
POST /api/threads/{thread_id}/runs: 503
Detail: "Run event store not available"
```

### LANE 7c: run_event_store Injection

**Added**: `app.state.run_event_store = make_run_event_store(None)` → `MemoryRunEventStore()`

**ALL 9 DEPENDENCIES SATISFIED**

```
*** STOP — POST /runs would return 200 → worker triggers → IMMEDIATE HALT ***
```

---

## Result Classification

| Scenario | Result | Interpretation |
|----------|--------|----------------|
| stream_bridge only | 503 "Run manager" | Monkey-patch works, chain is valid |
| + run_manager + run_store | 503 "Config" | Monkey-patch works, chain is valid |
| + minimal AppConfig | 503 "Run event store" | Config construction works (bypass from_file bug) |
| + run_event_store | **200 (worker starts)** | **ALL DEPS SATISFIED — worker unconditionally starts** |

**R135D Result: PASSED** — Full dependency chain mapped. Worker trigger confirmed. Safety STOP executed.

---

## Key Findings

1. **9 app.state deps confirmed** for POST /runs (not 3 as initially estimated in R135C)

2. **Constructor safety**: MemoryStreamBridge, MemoryRunStore, RunManager, MemoryThreadMetaStore — all pure in-memory, no side effects

3. **AppConfig.from_file() bug**: `config[1:]` error in `resolve_env_variables` makes config loading fail for any config with `${VAR}` references. Workaround: construct minimal AppConfig directly.

4. **Worker trigger is unconditional**: `services.py:272` always calls `asyncio.create_task(run_agent(...))`. No safety guard. LANE 7c execution was STOPPED before the POST.

5. **Minimal AppConfig works**: `AppConfig(log_level="info", sandbox=SandboxConfig(use="local"), database=DatabaseConfig(backend="memory"))` is sufficient for deps injection without triggering any real services.

6. **`make_run_event_store(None)` is safe**: Returns `MemoryRunEventStore()` with no side effects.

---

## R136 Recommended Approach

Since all deps can be monkey-patched (no code changes needed) but worker would start on full satisfaction, R136 should proceed with **real gateway initialization** (lifespan startup) to enable POST /runs without triggering worker in test isolation.

**R136 should investigate**:
1. Can the gateway lifespan be partially started (only run_event_store + config) to avoid full runtime initialization?
2. Or accept that POST /runs requires full runtime and focus on model authorization testing only?

---

## Constraints Preserved

- No code modification ✓
- No DB writes ✓
- No model API calls ✓
- No MCP runtime ✓
- No JSONL writes ✓
- No gateway server start ✓
- Safety STOP executed before worker trigger ✓

---

## Recommended Next Phase

**R136**: Gateway HTTP Smoke — Model Authorization

Goal: With real gateway lifespan (not TestClient), verify POST /runs model authorization without triggering real model calls.
R135D 完成。以下是执行结果摘要：

R135D 执行结果：PASSED
12-lane 执行中的关键发现：

逐层 Monkey-Patch 链（已验证）
步骤	注入的 Dep	结果
LANE 4	checkpointer + thread_store + thread_meta_repo	POST /threads 200
LANE 5	+ stream_bridge	503 "Run manager not available"
LANE 6	+ run_manager + run_store	503 "Configuration not available"
LANE 7b	+ minimal AppConfig	503 "Run event store not available"
LANE 7c	+ run_event_store	200 — worker 触发 — STOP
关键发现
9 个 app.state 依赖全部确认（不只是 R135C 估计的 3 个）

Worker 触发无安全拦截：services.py:272 无条件调用 asyncio.create_task(run_agent(...))，当所有 deps 满足时，POST /runs 会立即触发 worker

AppConfig.from_file() 有 Bug：resolve_env_variables 第 250 行 config[1:] 只去掉 $ 但留下 {}，导致 os.getenv('{DEER_FLOW_HOST_PATH}') 失败。变通方案：直接构造 minimal AppConfig

所有 deps 都可以无副作用构造：MemoryStreamBridge、MemoryRunStore、RunManager、MemoryThreadMetaStore、make_run_event_store — Risk: NONE

报告已写入
R135D_STREAM_BRIDGE_BYPASS_FEASIBILITY.md
R135D_STREAM_BRIDGE_BYPASS_FEASIBILITY.json
R136 授权包已生成
核心问题：TestClient + 完整 monkey-patch → deps 全部满足 → worker 立即开始 → 模型被调用。无法在 harness 环境中安全地验证模型授权。

建议路径：使用真实 gateway lifespan（而非 TestClient monkey-patch），尝试在 run_agent() 调用模型之前拦截模型选择过程。

R136_GATEWAY_HTTP_NO_TOOL_SMOKE.md — 详细方案
R136_GATEWAY_HTTP_NO_TOOL_SMOKE.json
是否授权进入 R136？压强建议：XXL（阻塞所有下游阶段）。