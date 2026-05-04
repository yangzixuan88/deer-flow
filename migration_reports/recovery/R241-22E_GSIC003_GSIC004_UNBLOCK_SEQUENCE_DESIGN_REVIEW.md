# R241-22E GSIC-003 / GSIC-004 Unblock Sequence Design Review

**报告ID**: R241-22E_GSIC003_GSIC004_UNBLOCK_SEQUENCE_DESIGN_REVIEW
**生成时间**: 2026-04-29T15:00:00+08:00
**阶段**: Phase 22E — GSIC-003 / GSIC-004 Unblock Sequence Design Review
**前置条件**: R241-22D Persistence Repositories Plan Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: gsic003_gsic004_sequence_design_completed_coupled_unblock_required
**gsic003_sequence_completed**: true
**gsic004_sequence_completed**: true
**surface010_dependency_confirmed**: true

**关键结论**：
- **GSIC-003 和 GSIC-004 必须耦合解除** — 两者在 `app.py` 中同时修改
- `app.py` 既有 `app.add_middleware(AuthMiddleware)`（GSIC-003），又有 `app.include_router(auth.router)`（GSIC-004）
- 部分激活会创造用户可见的不一致状态：只有 middleware 无路由 → 无法登录；只有路由无 middleware → 无认证 enforcement
- **推荐：R241-22G 单阶段同时解除 GSIC-003 和 GSIC-004**
- PR #2645 未找到（无冲突风险可确认）

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. PR #2645 Conflict Check

| 检查项 | 结果 |
|--------|------|
| `gh pr view 2645` | PR_NOT_FOUND_OR_NOT_ACCESSIBLE |
| 冲突风险 | 无法确认，假设 clean |

---

## 4. GSIC-003: Gateway Main Path Blocker

### 涉及文件

| File | GSIC-003 操作 |
|------|-------------|
| `app.py` | `app.add_middleware(AuthMiddleware)` |
| `app.py` | `app.add_middleware(CSRFMiddleware)` |
| `app.py` | `lifespan=lifespan` |
| `app.py` | `app.include_router(auth.router)` (also GSIC-004) |

### Middleware Chain Order

```
1. CORSMiddleware (FastAPI built-in)
2. CSRFMiddleware (custom)
3. AuthMiddleware (custom) ← sets/resets CurrentUser ContextVar
```

### Lifespan Sequence

```
_startup:_
  _ensure_admin_user() — needs session_factory (CAND-009), UserRow
  langgraph_runtime() — AsyncExitStack:
    init_engine_from_config() — CAND-009
    make_checkpointer()
    make_store()
    RunRepository(sf) or MemoryRunStore()
    FeedbackRepository(sf) or None
    make_thread_store()
    make_run_event_store() — config-driven (Jsonl or Db)
    RunManager
    yield
_shutdown:_
  close_engine() in langgraph_runtime finally block
```

### GSIC-003 解除 Gate

| Gate | 前置条件 |
|------|---------|
| **Gate 1** | SURFACE-010 unblocked（CV-ISO, MEM-LEAK, POOL, SDB 全部通过） |
| **Gate 2** | Auth Sub-Bundle C 实现完成（user_context, auth_middleware, authz, internal_auth） |
| **Gate 3** | Persistence Stage 3 实现完成（engine.py, UserRow） |
| **Gate 4** | Persistence Repositories 至少部分实现（MemoryRunStore 可用） |

---

## 5. GSIC-004: Route Registration Blocker

### routers/auth.py 9 Routes

| Method | Path | Auth Required | Public |
|--------|------|--------------|--------|
| POST | `/login/local` | ❌ | ✅ |
| POST | `/register` | ❌ | ✅ |
| POST | `/logout` | ❌ | ✅ |
| POST | `/change-password` | ✅ | |
| GET | `/me` | ✅ | |
| GET | `/setup-status` | ❌ | ✅ |
| POST | `/initialize` | ❌ | ✅ (no admin exists) |
| GET | `/oauth/{provider}` | ❌ | ✅ |
| GET | `/callback/{provider}` | ❌ | ✅ |

### GSIC-004 解除 Gate

| Gate | 前置条件 |
|------|---------|
| **Gate 1** | GSIC-003 同时或先解除（耦合） |
| **Gate 2** | Auth Sub-Bundle C 实现完成（authz 装饰器，get_current_user_from_request） |
| **Gate 3** | Persistence Stage 3 实现完成（get_local_provider 需要 session_factory） |

---

## 6. 耦合解除分析

### 为什么必须耦合

```
❌ Partial Activation A: Only GSIC-003 unblocked
   - AuthMiddleware added to chain
   - No auth routes registered
   → User hits /api/v1/auth/login/local → 404
   → No way to authenticate → gateway unusable

❌ Partial Activation B: Only GSIC-004 unblocked
   - Auth routes registered
   - No AuthMiddleware in chain
   → /api/v1/auth/me accessible without auth
   → Auth system visible but unenforced → fail-open

✅ Coupled Activation: GSIC-003 + GSIC-004 together
   - Middleware enforces auth
   - Routes provide login/register
   → Consistent gateway state
```

### 推荐解除顺序

| Phase | Action |
|-------|--------|
| R241-22F | Gateway Deps + App implementation plan |
| R241-22G | **COUPLED** GSIC-003 + GSIC-004 unblock (single phase) |
| R241-22H | Gateway integration + startup validation |

---

## 7. app.py Gateway Main Path Analysis

### GSIC-003 Modifications in app.py

```python
# Line: app.add_middleware(AuthMiddleware)
# Purpose: Fail-closed auth gate for all non-public paths
# Dependency: auth_middleware.py (CAND-005, Sub-Bundle C)

# Line: app.add_middleware(CSRFMiddleware)
# Purpose: CSRF protection for state-changing operations
# Dependency: csrf_middleware.py

# Line: lifespan=lifespan
# Purpose: Startup/shutdown hooks (_ensure_admin_user, langgraph_runtime)
# Dependency: deps.py langgraph_runtime()

# Line: app.include_router(auth.router)
# Also GSIC-004 — registers 9 auth routes
```

### deps.py langgraph_runtime() Prerequisites

| Dependency | Source |
|-----------|--------|
| `init_engine_from_config()` | CAND-009 (engine.py) — SURFACE-010 DT-002 |
| `get_session_factory()` | CAND-009 — returns None if memory |
| `RunRepository(sf)` | CAND-011 |
| `FeedbackRepository(sf)` | CAND-010 |
| `make_run_event_store(config)` | CAND-012/CAND-013 |
| `get_local_provider()` | needs session_factory |

---

## 8. Gateway Startup Safety Gates

| Gate ID | Name | Order Critical |
|---------|------|---------------|
| **GW-START-01** | Persistence engine initialized before middleware | ✅ Yes |
| **GW-START-02** | Memory backend fallback when session_factory is None | No |
| **GW-START-03** | Admin bootstrap graceful when auth not ready | No |
| **GW-START-04** | Middleware chain order correct | ✅ Yes |
| **GW-START-05** | AuthMiddleware public path bypass works | No |
| **GW-START-06** | get_local_provider() raises if session_factory is None | ✅ Yes |

---

## 9. Route Registration Safety Gates

| Gate ID | Name |
|---------|------|
| **RR-01** | All 9 auth routes have unique method+path |
| **RR-02** | Protected routes use @require_auth or get_current_user_from_request |
| **RR-03** | Public routes do NOT require authentication |
| **RR-04** | Rate limiting on login/register |
| **RR-05** | No route registration outside app.py |

---

## 10. Rollback / Feature Flag Strategy

### Gateway Activation Flag

| Env Var | Current | Unlock Condition |
|---------|---------|------------------|
| `MAINLINE_GATEWAY_ACTIVATION` | `false` | SURFACE-010 + GSIC-003 + GSIC-004 all unblocked |

### Auth Routes Flag

| Env Var | Default | Disable Effect |
|---------|---------|----------------|
| `AUTH_ROUTES_ENABLED` | `true` | `app.include_router(auth.router)` skipped |

### Auth Middleware Flag

| Env Var | Default | Disable Effect |
|---------|---------|----------------|
| `AUTH_MIDDLEWARE_ENABLED` | `true` | `app.add_middleware(AuthMiddleware)` skipped |

### Persistence Engine Flag

| Env Var | Values | Memory Effect |
|---------|--------|---------------|
| `DATABASE_BACKEND` | `memory/sqlite/postgres` | `get_session_factory()` returns None |

---

## 11. Rollback Procedure

### If GSIC-003 (middleware) must rollback:

```
1. Remove app.add_middleware(AuthMiddleware)
2. Remove app.add_middleware(CSRFMiddleware)
3. Remove lifespan=lifespan
Result: Gateway starts without auth (fail-open risk)
```

### If GSIC-004 (routes) must rollback:

```
1. Comment out app.include_router(auth.router)
Result: Auth routes 404, middleware still enforces 401 for protected paths
```

### If both must rollback:

```
1. Revert all app.py changes to pre-gateway state
Result: No auth, no routes, fail-open gateway
```

---

## 12. SURFACE-010 与 GSIC 依赖顺序

```
SURFACE-010 (unblock)
    │
    ├── DT-001: user_context.py ──────────────────────────────┐
    │    └── auth_middleware.py (sets/reset ContextVar) ───────┤
    │         └── app.py add_middleware(AuthMiddleware) ───────┼── GSIC-003
    │              └── app.py lifespan hook ───────────────────┤
    │                   └── deps.py langgraph_runtime() ───────┤
    │                        └── get_session_factory() ────────┤
    │                                                         │
    └── DT-002: engine.py (init_engine_from_config) ──────────┘
         └── deps.py get_session_factory()
              └── SQLiteUserRepository ─────────────────────────┐
                   └── LocalAuthProvider ──────────────────────┤
                        └── get_local_provider() ──────────────┤
                             └── auth routes ─────────────────┼── GSIC-004
                                  └── app.py include_router ──┘
```

**依赖链**：SURFACE-010 → Auth Bundle → Persistence Bundle → Gateway

---

## 13. Auth Bundle 与 Persistence Bundle 依赖

| Bundle | 前置 | 完成条件 |
|--------|------|---------|
| Auth Bundle (Sub-Bundle C) | SURFACE-010 unblocked | user_context, authz, internal_auth, auth_middleware |
| Persistence Bundle (Stage 3+4) | SURFACE-010 unblocked | engine.py, UserRow, FeedbackRepository, RunRepository, DbRunEventStore, JsonlRunEventStore |
| **Gateway Bundle** | Both above | deps.py + app.py activation |

**关键发现**：Auth Bundle 和 Persistence Bundle 可**并行**开发（无相互依赖）；两者都完成后才能激活 Gateway。

---

## 14. Recommended R241-22 Continuation Sequence

| Phase | Name | Candidates | Depends On |
|-------|------|-----------|------------|
| **R241-22F** | Gateway Deps + App Implementation Plan | CAND-018 (app.py), deps.py, routers/auth.py | R241-22D |
| **R241-22G** | **COUPLED** GSIC-003 + GSIC-004 Unblock | app.py middleware chain + route registration | R241-22F + SURFACE-010 |
| **R241-22H** | Gateway Integration + Startup Validation | E2E integration tests | R241-22G |

---

## 15. Explicit Stop Conditions

| Condition | Action |
|-----------|--------|
| SURFACE-010 not yet unblocked | Do not activate gateway |
| Auth Sub-Bundle C not complete | auth_middleware not available |
| Persistence Stage 3+4 not complete | session_factory not available |
| GSIC-003/GSIC-004 not both unblocked | Do not do partial activation |
| Code modification detected during review | Abort and report safety violation |

---

## 16. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| gateway_app_modified | ❌ false |
| deps_py_modified | ❌ false |
| auth_router_modified | ❌ false |
| middleware_added | ❌ false |
| route_registered | ❌ false |
| db_written | ❌ false |
| jsonl_written | ❌ false |
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

## R241_22E_GSIC003_GSIC004_UNBLOCK_SEQUENCE_DESIGN_REVIEW_DONE

```
status=passed_with_warnings
gsic003_sequence_completed=true
gsic004_sequence_completed=true
surface010_dependency_confirmed=true
gateway_startup_gate_completed=true
route_registration_gate_completed=true
rollback_strategy_completed=true
implementation_allowed=false
route_registration_allowed=false
gateway_activation_allowed=false
coupled_unblock_recommended=true
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
db_written=false
jsonl_written=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-22F
next_prompt_needed=user_selection
```

---

## 选项

**A.** R241-22F — Gateway Deps (deps.py) + App (CAND-018) implementation plan
**B.** R241-22G — GSIC-003 + GSIC-004 COUPLED unblock design (advanced phase, requires SURFACE-010)
**C.** R241-22H — Auth Bundle Sub-Bundle D (CAND-004 reset_admin.py) implementation plan
**D.** Pause R241-22, return to R241 mainline for CAND-016/CAND-017/CAND-020