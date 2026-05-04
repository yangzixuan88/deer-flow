# R140: start_run Inline Execution Mode Fix

## Status: PASSED ✅

## Preceded By: R139C_INTERRUPT_CAUSAL_CHAIN_TEST
## Proceeding To: R141_AUTH_WIRING_REGRESSION_CHECK

## Pressure: XXL

---

## Summary

R140 adds `run_in_background: bool = True` parameter to `services.start_run()`. When `False`, the function awaits `run_agent` inline instead of via `asyncio.create_task`. This prevents TestClient context teardown from cancelling the background task and causing `status=interrupted`. Inline smoke test: **PASSED** — `final_status=success`.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| Previous phase | R139C |
| Current phase | R140 |
| Recommended pressure | XXL |
| Pressure check | PASS |

---

## LANE 1: Scope Gate

| Check | Result |
|---|---|
| `start_run` signature | `async def start_run(body, thread_id, request, run_in_background=True)` |
| `asyncio.create_task` location | `services.py:272` |
| HTTP endpoints calling `start_run` | `create_run` (line 97), `stream_run` (line 105) |
| `run_agent` signature confirmed | worker.py:79 |
| Only `services.py` modified | ✅ |
| Production default preserved | ✅ |

---

## LANE 2: Pre-fix Baseline

| Check | Result |
|---|---|
| `run_in_background` already exists | False |
| `asyncio.create_task` present | True |
| `await run_agent` inline present | False |
| Baseline confirmed | ✅ |

---

## LANE 3: Minimal Patch

**Modified file:** `app/gateway/services.py`

**Change 1 — signature (line 195):**
```python
async def start_run(body, thread_id, request, run_in_background: bool = True) -> RunRecord:
```

**Change 2 — docstring (lines 208-214):**
```python
run_in_background : bool, default True
    When True, runs ``run_agent`` as a background task (via
    ``asyncio.create_task``) and returns immediately. When False,
    awaits ``run_agent`` inline — the record is not returned until
    the agent completes. Use ``run_in_background=False`` in test
    harnesses to avoid TestClient context teardown cancelling the
    background task and causing ``status=interrupted``.
```

**Change 3 — conditional execution (lines 280-310):**
```python
if run_in_background:
    task = asyncio.create_task(
        run_agent(bridge, run_mgr, record, ctx=run_ctx, ...)
    )
    record.task = task
else:
    await run_agent(bridge, run_mgr, record, ctx=run_ctx, ...)
```

**Lines added:** 28 | **Lines removed:** 5

---

## LANE 4: Static Validation

| Check | Result |
|---|---|
| `py_compile` | PASS |
| `ast.parse` | PASS |
| Signature check | PASS (params: body, thread_id, request, run_in_background) |
| Imports | PASS |
| `run_in_background` default | `True` |

---

## LANE 5: Background Mode Regression

| Check | Result |
|---|---|
| Default path still uses `asyncio.create_task` | ✅ |
| `await run_agent` in `else` block | ✅ |
| Production default unchanged | ✅ |

---

## LANE 6: Inline Smoke Test

| Check | Result |
|---|---|
| Test script | `run_r139c.py` (R139C harness with `run_in_background=False`) |
| Run ID | `05b4665e-b00f-4f6d-9a95-f5a787709f31` |
| `final_status` | **success** |
| `final_error` | None |
| `worker_started` | True |
| `worker_completed` | True |
| `worker_error` | None |
| StreamBridge events | 5 |
| Model response detected | True (length=103) |

`★ Insight ─────────────────────────────────────`
**关键差异**：R139 中 `start_run` 用 `asyncio.create_task` 创建后台任务后立即返回 record（task 在后台运行）。当 TestClient context 退出时，task 被 cancel → `CancelledError` → `status=interrupted`。R140 的 `run_in_background=False` 跳过 `create_task`，直接在 `start_run` 内 `await run_agent`，等 agent 完成后 record 才返回给调用方。context 退出时 task 已完成，没有东西可以 cancel。
`─────────────────────────────────────────────────`

---

## LANE 7: Result Classification

| Classification | Value |
|---|---|
| Result | **passed** |
| Outcome | inline execution works correctly — `status=success` |
| Production path regression | none |
| `run_in_background=True` path | unaffected (still uses `asyncio.create_task`) |

---

## LANE 8: Commit

| Field | Value |
|---|---|
| SHA | `f480fec1` |
| Message | `feat(gateway): add run_in_background=False to start_run for inline test execution` |

---

## Cause Chain

| Phase | Finding |
|---|---|
| **R139** | `status=interrupted` despite model API call succeeding. `task.cancel()` called (`CancelledError` caught). `abort_event` set AFTER model response. |
| **R139B** | Neither `manager.cancel()` nor `create_or_reject` interrupt/rollback in R139 call path. `POST /runs` returns plain JSON (not `StreamingResponse`). |
| **R139C** | Inline `await run_agent` (no `asyncio.create_task`) → `status=success`. Cause A (TestClient lifecycle) confirmed. |
| **R140** | Added `run_in_background=False` to `start_run`. Inline smoke test PASSED. Default `True` preserves production behavior. |

---

## Implications

1. **Test harness fix**: Callers can use `start_run(..., run_in_background=False)` to run agents inline in test context
2. **Production unchanged**: Default `run_in_background=True` means all existing HTTP endpoints behave identically
3. **No auth changes**: CSRF/auth middleware untouched — only task execution path modified

---

## Unknowns Resolved

| ID | Description | Resolution |
|---|---|---|
| U-interrupt-source-still-unknown | Interrupt source unclear after R139 | **RESOLVED**: TestClient lifecycle cancellation (Cause A) |
| U-task-cancel-source-unknown | `task.cancel()` called but not from manager paths | **RESOLVED**: Confirmed via inline await test |
| U-post-runs-response-type | Confirmed plain JSON (not StreamingResponse) | **RESOLVED**: Not relevant to interrupt |

---

## Recommended Next Phase

**R141_AUTH_WIRING_REGRESSION_CHECK** (Pressure: M)

After fixing the interrupt root cause, verify that auth wiring changes from `r241/auth-disabled-wiring-v2` branch haven't regressed any authentication or authorization paths. This is a low-pressure validation phase since the main issue is resolved.

Reason: R139 interrupt chain is closed (Cause A confirmed, R140 fix deployed). Next priority is validating the auth-disabled wiring changes don't break existing auth flows.