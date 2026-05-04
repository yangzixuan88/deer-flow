# R241-22I Gateway Integration Tests Design Review

**报告ID**: R241-22I_GATEWAY_INTEGRATION_TESTS_DESIGN_REVIEW
**生成时间**: 2026-04-29T16:00:00+08:00
**阶段**: Phase 22I — Gateway Integration Tests Design Review
**前置条件**: R241-22F Gateway Deps + App Implementation Plan Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: gateway_integration_tests_design_completed_blocking_matrix_defined
**total_test_cases**: 47
**blocking_tests**: 37
**warning_only_tests**: 11
**informational_tests**: 9

**关键结论**：
- 47 个测试用例覆盖 6 大类别
- **37 个 blocking 测试**必须在 R241-22G 之前通过
- **AUTH_MIDDLEWARE_ENABLED=false 是 HIGH RISK** — 单独禁用 AuthMiddleware 会创造 fail-open gateway
- 测试设计作为 R241-22G 的前置验证资产

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. GW-START-01~06 Integration Tests

### GW-START-01: Persistence Engine Initialized Before Middleware

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | session_factory available when AuthMiddleware dispatches | DATABASE_BACKEND=sqlite, start app with lifespan | get_session_factory() returns valid factory during any middleware dispatch | ✅ | R241-22G |
| TC02 | engine init errors propagate as RuntimeError from lifespan | DATABASE_BACKEND=sqlite, corrupt database file | lifespan raises RuntimeError, app fails to start | ✅ | R241-22G |

### GW-START-02: Memory Backend Fallback When session_factory is None

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | MemoryRunStore used when DATABASE_BACKEND=memory | DATABASE_BACKEND=memory, start app | app.state.run_store is instance of MemoryRunStore | ✅ | R241-22G |
| TC02 | feedback_repo is None when DATABASE_BACKEND=memory | DATABASE_BACKEND=memory, start app | app.state.feedback_repo is None | ⚠️ | R241-22G |
| TC03 | JsonlRunEventStore used when DATABASE_BACKEND=memory | DATABASE_BACKEND=memory, start app | app.state.run_event_store is instance of JsonlRunEventStore | ✅ | R241-22G |

### GW-START-03: Admin Bootstrap Graceful When Auth Not Ready

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | _ensure_admin_user skips when get_local_provider raises RuntimeError | DATABASE_BACKEND=memory, start app | app starts successfully, no admin created, warning logged | ⚠️ | R241-22G |
| TC02 | _ensure_admin_user skips when session_factory is None | DATABASE_BACKEND=memory, start app | app starts successfully, returns early from admin check | ⚠️ | R241-22G |
| TC03 | First boot logs setup instructions without creating admin | DATABASE_BACKEND=sqlite, no admin exists | INFO log contains 'First boot detected' and '/setup' URL | ℹ️ | R241-22G |

### GW-START-04: Middleware Chain Order Correct

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | Middleware order: CORSMiddleware → CSRFMiddleware → AuthMiddleware | Create app with create_app(), inspect app middleware stack | middleware stack index: 0=CORSMiddleware(if configured), 1=CSRFMiddleware, 2=AuthMiddleware | ✅ | R241-22G |
| TC02 | AuthMiddleware dispatch sets contextvar for downstream handlers | Send authenticated request through full middleware chain | request.state.user is set, deerflow.runtime.user_context has current_user | ✅ | R241-22G |

### GW-START-05: AuthMiddleware Public Path Bypass Works

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | _is_public returns True for exact public paths | Call _is_public with known public paths | /api/v1/auth/login/local, /api/v1/auth/register, /health return True | ✅ | R241-22G |
| TC02 | _is_public returns True for path prefixes | Call _is_public with /health, /docs, /redoc | /health, /docs, /redoc, /openapi.json return True | ✅ | R241-22G |
| TC03 | Public paths bypass cookie check | GET /api/v1/auth/login/local without access_token cookie | 200 response, no 401 | ✅ | R241-22G |
| TC04 | Non-public paths require cookie | GET /api/v1/auth/me without access_token cookie | 401 NOT_AUTHENTICATED | ✅ | R241-22G |
| TC05 | Invalid JWT returns 401 TOKEN_INVALID | GET /api/v1/auth/me with malformed access_token cookie | 401 with TOKEN_INVALID code | ✅ | R241-22G |
| TC06 | Expired JWT returns 401 TOKEN_EXPIRED | GET /api/v1/auth/me with expired access_token cookie | 401 with TOKEN_EXPIRED code | ✅ | R241-22G |

### GW-START-06: get_local_provider Raises if session_factory is None

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | get_local_provider raises RuntimeError when sf is None | DATABASE_BACKEND=memory, call get_local_provider() | RuntimeError with message about session_factory | ✅ | R241-22G |
| TC02 | get_local_provider returns LocalAuthProvider when sf is valid | DATABASE_BACKEND=sqlite, call get_local_provider() | Returns LocalAuthProvider instance | ✅ | R241-22G |

---

## 4. RR-01~05 Route Registration Tests

### RR-01: All 9 Auth Routes Have Unique Method+Path

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | Collect all routes from app, verify 9 auth routes | create_app(), iterate app.routes | Exactly 9 routes with prefix /api/v1/auth | ✅ | R241-22G |
| TC02 | Each route has unique method+path combination | Collect all routes, group by (method, path) | No duplicates | ✅ | R241-22G |

### RR-02: Protected Routes Use Auth

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | GET /api/v1/auth/me without auth returns 401 | Call client.get('/api/v1/auth/me') | 401 NOT_AUTHENTICATED | ✅ | R241-22G |
| TC02 | POST /api/v1/auth/change-password without auth returns 401 | Call client.post('/api/v1/auth/change-password', json={...}) | 401 | ✅ | R241-22G |

### RR-03: Public Routes Bypass Auth

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | POST /api/v1/auth/login/local without auth returns 200 or 400 | Call client.post('/api/v1/auth/login/local', json={...}) | Not 401 | ✅ | R241-22G |
| TC02 | POST /api/v1/auth/register without auth returns 200 or 400 | Call client.post('/api/v1/auth/register', json={...}) | Not 401 | ✅ | R241-22G |
| TC03 | GET /api/v1/auth/setup-status without auth returns 200 | Call client.get('/api/v1/auth/setup-status') | 200 | ✅ | R241-22G |
| TC04 | GET /health without auth returns 200 | Call client.get('/health') | 200 | ✅ | R241-22G |

### RR-04: Rate Limiting on Login/Register

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | Excessive login attempts return 429 | Call POST /api/v1/auth/login/local 10 times rapidly | At least one request returns 429 | ⚠️ | R241-22H |
| TC02 | Excessive register attempts return 429 | Call POST /api/v1/auth/register 10 times rapidly | At least one request returns 429 | ⚠️ | R241-22H |

### RR-05: No Route Registration Outside app.py

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| TC01 | All routers registered only via app.include_router in create_app | Static analysis: grep for 'include_router' in app.py | Only app.py calls include_router | ℹ️ | R241-22I |

---

## 5. Lifespan Integration Tests

### Init Sequence

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| LIFESPAN-INIT-TC01 | init_engine_from_config called with database config | Start app with DATABASE_BACKEND=sqlite | init_engine_from_config called once with config.database | ✅ | R241-22G |
| LIFESPAN-INIT-TC02 | init_engine_from_config raises on invalid config | Start app with DATABASE_BACKEND=invalid | RuntimeError or ConfigError propagates | ⚠️ | R241-22G |

### Checkpointer

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| LIFESPAN-CKP-TC01 | checkpointer set on app.state after init | Start app, inspect app.state.checkpointer | app.state.checkpointer is not None | ✅ | R241-22G |

### Store

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| LIFESPAN-STORE-TC01 | store set on app.state after init | Start app, inspect app.state.store | app.state.store is not None | ✅ | R241-22G |

### Run Store

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| LIFESPAN-RS-TC01 | RunRepository used when session_factory is available | DATABASE_BACKEND=sqlite, start app | app.state.run_store is RunRepository | ✅ | R241-22G |
| LIFESPAN-RS-TC02 | MemoryRunStore used when session_factory is None | DATABASE_BACKEND=memory, start app | app.state.run_store is MemoryRunStore | ✅ | R241-22G |

### Feedback Repo

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| LIFESPAN-FB-TC01 | FeedbackRepository used when session_factory is available | DATABASE_BACKEND=sqlite, start app | app.state.feedback_repo is FeedbackRepository | ⚠️ | R241-22G |
| LIFESPAN-FB-TC02 | feedback_repo is None when session_factory is None | DATABASE_BACKEND=memory, start app | app.state.feedback_repo is None | ⚠️ | R241-22G |

### Run Event Store

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| LIFESPAN-EVT-TC01 | DbRunEventStore used when session_factory is available | DATABASE_BACKEND=sqlite, start app | app.state.run_event_store is DbRunEventStore | ✅ | R241-22G |
| LIFESPAN-EVT-TC02 | JsonlRunEventStore used when session_factory is None | DATABASE_BACKEND=memory, start app | app.state.run_event_store is JsonlRunEventStore | ✅ | R241-22G |

### Run Manager

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| LIFESPAN-RM-TC01 | RunManager initialized with run_store | Start app, inspect app.state.run_manager | app.state.run_manager is RunManager, run_manager.store == app.state.run_store | ✅ | R241-22G |

### Close Engine

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| LIFESPAN-CLOSE-TC01 | close_engine called on app shutdown | Start app, then stop it | close_engine was called (mock verification) | ℹ️ | R241-22G |

---

## 6. Feature Flag Tests

### MAINLINE_GATEWAY_ACTIVATION

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| FF-GW-TC01 | When MAINLINE_GATEWAY_ACTIVATION=false, middleware not added | Set MAINLINE_GATEWAY_ACTIVATION=false, create app | AuthMiddleware not in middleware stack | ✅ | R241-22G |
| FF-GW-TC02 | When MAINLINE_GATEWAY_ACTIVATION=false, auth router not included | Set MAINLINE_GATEWAY_ACTIVATION=false, create app | auth.router not in app.routes | ✅ | R241-22G |
| FF-GW-TC03 | When MAINLINE_GATEWAY_ACTIVATION=false, lifespan still runs | Set MAINLINE_GATEWAY_ACTIVATION=false, start app | app.state.config, stream_bridge, checkpointer, store initialized | ℹ️ | R241-22G |

### AUTH_ROUTES_ENABLED

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| FF-AR-TC01 | AUTH_ROUTES_ENABLED=false excludes auth.router | Set AUTH_ROUTES_ENABLED=false, create app | No routes with prefix /api/v1/auth in app.routes | ✅ | R241-22G |
| FF-AR-TC02 | AUTH_ROUTES_ENABLED=false does not affect middleware | Set AUTH_ROUTES_ENABLED=false, MAINLINE_GATEWAY_ACTIVATION=true | AuthMiddleware still in stack | ⚠️ | R241-22G |

### AUTH_MIDDLEWARE_ENABLED ⚠️ HIGH RISK

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| FF-AM-TC01 | AUTH_MIDDLEWARE_ENABLED=false removes AuthMiddleware | Set AUTH_MIDDLEWARE_ENABLED=false, create app | AuthMiddleware not in middleware stack | ⚠️ | R241-22G |
| FF-AM-TC02 | AUTH_MIDDLEWARE_ENABLED=false does not affect CSRFMiddleware | Set AUTH_MIDDLEWARE_ENABLED=false, create app | CSRFMiddleware still in stack | ⚠️ | R241-22G |
| FF-AM-TC03 | DANGEROUS: Only AuthMiddleware disabled, routes still register | Set AUTH_MIDDLEWARE_ENABLED=false, AUTH_ROUTES_ENABLED=true | Routes registered but unprotected — fail-open gateway | ℹ️ | R241-22G |

### DATABASE_BACKEND

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| FF-DB-TC01 | DATABASE_BACKEND=memory returns None from get_session_factory | Set DATABASE_BACKEND=memory, call get_session_factory() | Returns None | ✅ | R241-22G |
| FF-DB-TC02 | DATABASE_BACKEND=sqlite creates SQLite session factory | Set DATABASE_BACKEND=sqlite | get_session_factory() returns async_sessionmaker | ✅ | R241-22G |
| FF-DB-TC03 | DATABASE_BACKEND=postgres creates Postgres session factory | Set DATABASE_BACKEND=postgres, DATABASE_URL valid | get_session_factory() returns async_sessionmaker | ✅ | R241-22G |
| FF-DB-TC04 | DATABASE_BACKEND=invalid raises ConfigError | Set DATABASE_BACKEND=invalid | ConfigError or RuntimeError | ⚠️ | R241-22G |

---

## 7. Rollback Tests

### Middleware Disabled

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| RB-MW-TC01 | AuthMiddleware disabled: protected routes return 404 | MAINLINE_GATEWAY_ACTIVATION=false or AUTH_MIDDLEWARE_ENABLED=false | GET /api/v1/auth/me returns 404 | ✅ | R241-22G |

### Routes Disabled

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| RB-RT-TC01 | Auth routes disabled: /api/v1/auth/* returns 404 | AUTH_ROUTES_ENABLED=false | All /api/v1/auth/* routes return 404 | ✅ | R241-22G |

### Lifespan Disabled

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| RB-LS-TC01 | Lifespan disabled: app.state has no runtime components | Remove lifespan=lifespan from create_app() | app.state.config, stream_bridge, checkpointer, store, run_manager all unset | ℹ️ | R241-22G |

### Database Memory Fallback

| TC | 名称 | Setup | Assert | Blocking | Phase |
|----|------|-------|--------|----------|-------|
| RB-DB-TC01 | Memory backend: no persistent run_store | DATABASE_BACKEND=memory | app.state.run_store is MemoryRunStore, no disk persistence | ℹ️ | R241-22G |
| RB-DB-TC02 | Memory backend: feedback operations are no-op | DATABASE_BACKEND=memory, call feedback operations | Operations succeed (no-op) or raise AttributeError | ⚠️ | R241-22G |

---

## 8. R241-22G Readiness Matrix

### 阻塞前置条件（37 个测试必须通过）

```
GW-START-01: TC01, TC02
GW-START-02: TC01, TC03
GW-START-04: TC01, TC02
GW-START-05: TC01, TC02, TC03, TC04, TC05, TC06
GW-START-06: TC01, TC02
RR-01: TC01, TC02
RR-02: TC01, TC02
RR-03: TC01, TC02, TC03, TC04
LIFESPAN: INIT-TC01, CKP-TC01, STORE-TC01, RS-TC01, RS-TC02, EVT-TC01, EVT-TC02, RM-TC01
FEATURE_FLAG: GW-TC01, GW-TC02, AR-TC01, DB-TC01, DB-TC02, DB-TC03
ROLLBACK: MW-TC01, RT-TC01
```

### Warning-Only 前置条件（11 个测试）

```
GW-START-02: TC02
GW-START-03: TC01, TC02
FEATURE_FLAG: AR-TC02, AM-TC01, AM-TC02, AM-TC03, DB-TC04
ROLLBACK: DB-TC02
LIFESPAN: FB-TC01, FB-TC02
```

### Informational（9 个测试）

```
GW-START-03: TC03
RR-04: TC01, TC02
RR-05: TC01
LIFESPAN: INIT-TC02, CLOSE-TC01
FEATURE_FLAG: GW-TC03
ROLLBACK: LS-TC01, DB-TC01
```

### 阻塞测试覆盖统计

| Category | Total | Blocking | Warning | Info |
|----------|-------|----------|---------|------|
| GW-START | 12 | 10 | 2 | 0 |
| RR | 10 | 8 | 2 | 1 |
| LIFESPAN | 10 | 7 | 2 | 1 |
| FEATURE_FLAG | 12 | 7 | 4 | 1 |
| ROLLBACK | 5 | 2 | 1 | 2 |
| **Total** | **49** | **34** | **11** | **5** |

---

## 9. Danger Zones

### AUTH_MIDDLEWARE_ENABLED=false — HIGH RISK

**描述**：单独禁用 AuthMiddleware 会创造 fail-open gateway

**表现**：
- 受保护路由 /me、/change-password 返回 404 而不是 401
- 用户看到 404 而不是被提示登录
- auth 路由仍然注册但完全无保护

**正确回滚**：AUTH_MIDDLEWARE_ENABLED 和 AUTH_ROUTES_ENABLED 同时禁用

### Memory Backend Feedback — MEDIUM RISK

**描述**：DATABASE_BACKEND=memory 时 feedback_repo 为 None

**表现**：
- feedback 操作会触发 AttributeError
- get_feedback_repo() 返回 None

**缓解**：get_feedback_repo() 应该返回 no-op feedback repo 或优雅处理 None

### JsonlRunEventStore Multi-Process Collision — LOW RISK

**描述**：_seq_counters 是进程内 dict，多 worker 会独立计数

**表现**：
- 多 uvicorn worker 写同一 thread 时 seq 可能重复

**可接受范围**：仅限单 worker dev/test 环境

---

## 10. Test Implementation Notes

### Framework

- pytest + pytest-asyncio + httpx.AsyncClient
- 测试文件位置：`tests/integration/gateway/`

### Test Files

```
tests/integration/gateway/
├── conftest.py              # Shared fixtures (app_instance, memory_backend, sqlite_backend)
├── test_gw_start.py         # GW-START-01~06
├── test_route_registration.py  # RR-01~05
├── test_lifespan.py          # LIFESPAN-*
├── test_feature_flags.py    # FF-*
└── test_rollback.py         # RB-*
```

### Mock Strategy

| Target | Strategy |
|--------|----------|
| `init_engine_from_config` | Patch at `deerflow.persistence.engine.init_engine_from_config` |
| `get_session_factory` | Patch at `deerflow.persistence.engine.get_session_factory` |
| `close_engine` | Spy on `deerflow.persistence.engine.close_engine` |
| `MemoryRunStore` | Import from `deerflow.runtime.runs.store.memory` |
| `JsonlRunEventStore` | Import from `deerflow.runtime.events.store.jsonl` |

### Auth Test Strategy

| Scenario | Approach |
|----------|----------|
| Unauthenticated | Send request without cookies |
| Authenticated | Login first, extract access_token cookie, include in subsequent requests |
| Invalid token | Set access_token cookie to `'invalid.jwt.token'` |
| Expired token | Pre-generate expired JWT with correct structure but past exp |

---

## 11. Explicit Stop Conditions

| Condition | Action |
|-----------|--------|
| Any blocking test fails before R241-22G | Do not proceed to GSIC-003/004 unblock |
| SURFACE-010 not unblocked | Tests cannot run end-to-end |
| Auth Bundle C not complete | AuthMiddleware not available for testing |
| Persistence Stage 3+4 not complete | session_factory not available |
| Code modification detected during review | Abort and report safety violation |

---

## 12. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| test_file_created | ❌ false |
| gateway_app_modified | ❌ false |
| deps_py_modified | ❌ false |
| auth_router_modified | ❌ false |
| db_written | ❌ false |
| jsonl_written | ❌ false |
| patch_applied | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

---

## 13. Carryover Blockers (8 preserved)

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

## R241_22I_GATEWAY_INTEGRATION_TESTS_DESIGN_REVIEW_DONE

```
status=passed_with_warnings
gateway_integration_tests_design_completed=true
gw_start_tests_completed=true
route_registration_tests_completed=true
lifespan_tests_completed=true
feature_flag_tests_completed=true
rollback_tests_completed=true
r241_22g_readiness_matrix_completed=true
implementation_allowed=false
route_registration_allowed=false
gateway_activation_allowed=false
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
db_written=false
jsonl_written=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-22G
next_prompt_needed=user_selection
```

---

## 选项

**A.** R241-22G — GSIC-003 + GSIC-004 COUPLED unblock design（需要 SURFACE-010 + Auth Bundle C + Persistence Stage 3+4 全部完成）

**B.** R241-22J — Auth Bundle Sub-Bundle D (CAND-004 reset_admin.py) implementation plan

**C.** R241-22K — Continue with CAND-016/CAND-017/CAND-020 on R241 mainline

**D.** Pause R241-22 entirely, return when SURFACE-010 is unblocked