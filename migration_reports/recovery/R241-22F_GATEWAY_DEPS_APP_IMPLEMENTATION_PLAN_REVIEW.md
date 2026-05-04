# R241-22F Gateway Deps + App Implementation Plan Review

**报告ID**: R241-22F_GATEWAY_DEPS_APP_IMPLEMENTATION_PLAN_REVIEW
**生成时间**: 2026-04-29T15:30:00+08:00
**阶段**: Phase 22F — Gateway Deps + App Implementation Plan Review
**前置条件**: R241-22E GSIC-003/GSIC-004 Unblock Sequence Design Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: gateway_deps_app_plan_completed_gsic003_004_deferred_to_22g
**deps_py_plan_completed**: true
**app_py_plan_completed**: true
**gsic003_deferred**: true
**gsic004_deferred**: true
**feature_flag_strategy_completed**: true

**关键结论**：
- `deps.py` 和 `app.py` 实现计划完成
- GSIC-003（middleware chain）和 GSIC-004（route registration）推至 R241-22G 耦合解除
- R241-22G 需要 SURFACE-010 + Auth Bundle C + Persistence Stage 3+4 全部完成
- 当前代码库状态：**不适合激活 gateway**（MAINLINE_GATEWAY_ACTIVATION=false）

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. 文件清单

### deps.py

| 文件 | 路径 | LOC | GSIC-003 | GSIC-004 | SURFACE-010 |
|------|------|-----|----------|----------|-------------|
| `deps.py` | `app/gateway/deps.py` | ~300 | ✅ 直接依赖 | ✅ 直接依赖 | ✅ 间接依赖 |

### app.py

| 文件 | 路径 | LOC | GSIC-003 | GSIC-004 | SURFACE-010 |
|------|------|-----|----------|----------|-------------|
| `app.py` | `app/gateway/app.py` | ~350 | ✅ 直接操作 | ✅ 直接操作 | ❌ |

**无路由文件修改**（routers/auth.py 属于 GSIC-004）
**无 middleware 文件创建**（auth_middleware.py 属于 Auth Bundle C）

---

## 4. deps.py langgraph_runtime() 契约

### Enter Sequence（9 步）

```
1. init_engine_from_config() — CAND-009
   └── 获取 session_factory（可能为 None）

2. make_checkpointer(config, session_factory)
   └── MemoryCheckpointer 或 SqliteCheckpointer

3. make_store(config)
   └── MemoryStore 或 SqliteStore

4. RunRepository(session_factory) 或 MemoryRunStore()
   └── 条件分支：sf is None → MemoryRunStore()

5. FeedbackRepository(session_factory) 或 None
   └── ⚠️ 无 MemoryFeedbackStore 等效物；sf is None → None

6. make_thread_store(config)
   └── JsonlThreadStore 或 DbThreadStore

7. make_run_event_store(config, session_factory)
   └── 条件分支：sf is None → JsonlRunEventStore()

8. RunManager(checkpointer, store, run_store, event_store, ...)
   └── 组合所有组件

9. yield（控制权给 FastAPI）
```

### Exit Sequence（1 步）

```
finally:
    close_engine() — 释放所有连接
```

### app.state 初始化属性（9 个）

| 属性 | 类型 | 条件 |
|------|------|------|
| `app.state.config` | AppConfig | 无条件 |
| `app.state.stream_bridge` | StreamBridge | 无条件 |
| `app.state.checkpointer` | Checkpointer | 无条件 |
| `app.state.store` | Store | 无条件 |
| `app.state.run_store` | RunStore | sf=None 时为 MemoryRunStore |
| `app.state.feedback_repo` | FeedbackRepository \| None | sf=None 时为 None |
| `app.state.thread_store` | ThreadStore | 无条件 |
| `app.state.run_event_store` | RunEventStore | sf=None 时为 JsonlRunEventStore |
| `app.state.run_manager` | RunManager | 无条件 |

---

## 5. get_local_provider() 契约

### 签名

```python
def get_local_provider() -> LocalAuthProvider:
    ...
```

### 行为

| 条件 | 行为 |
|------|------|
| `session_factory is not None` | 返回 `LocalAuthProvider(session_factory)` 单例 |
| `session_factory is None` | **raise RuntimeError("session_factory is None, cannot create LocalAuthProvider")** |

### 单例模式

```python
_local_provider: LocalAuthProvider | None = None

def get_local_provider() -> LocalAuthProvider:
    if _local_provider is None:
        sf = get_session_factory()
        if sf is None:
            raise RuntimeError(...)
        _local_provider = LocalAuthProvider(sf)
    return _local_provider
```

---

## 6. get_current_user_from_request() 契约

### 6 步验证链

```
1. 从请求头提取 Authorization: Bearer <token>
   └── 失败 → raise HTTPException(401, "Missing authorization header")

2. 验证 token 格式（JWT 结构检查）
   └── 失败 → raise HTTPException(401, "Invalid token format")

3. 解码 JWT（不验证签名，先提取 payload）
   └── 失败 → raise HTTPException(401, "Token decode failed")

4. 检查 token 类型是否为 access
   └── 失败 → raise HTTPException(401, "Invalid token type")

5. 调用 get_optional_user_from_request(request) 获取用户
   └── 返回 None → raise HTTPException(401, "User not found")

6. 返回 User 对象
```

### get_optional_user_from_request() 行为

```
1. 从请求 cookie 读取 session_id
2. 从请求头读取 X-CSRF-Token
3. 调用 is_valid_internal_auth_token(session_id, csrf_token)
   └── 返回 False → return None
4. 从 session_id 查找 session
5. 返回 session.user 或 None
```

---

## 7. _ensure_admin_user() 契约

### 首次启动检查

```python
async def _ensure_admin_user():
    sf = get_session_factory()
    if sf is None:
        logger.warning("session_factory is None, skipping admin user check")
        return

    async with sf() as session:
        result = await session.execute(select(User).where(User.is_admin == True))
        admin = result.scalar_one_or_none()

    if admin is None:
        # 需要初始化管理员
        provider = get_local_provider()
        await provider.create_user(...)  # 或 setup endpoint
```

### Orphan Thread Migration（无认证→有认证升级）

```python
async def _migrate_orphaned_threads():
    """将无 user_id 的 thread 迁移到系统用户"""
    # 查找 thread_id WHERE user_id IS NULL
    # 为每个 thread 设置 system user_id
    # 不删除任何数据
```

---

## 8. GSIC-003 实现计划（app.py）

### Middleware Chain Order

```
1. CORSMiddleware (FastAPI built-in, from .add_middleware)
2. CSRFMiddleware (custom, from .add_middleware)
3. AuthMiddleware (custom, from .add_middleware) ← sets/resets CurrentUser ContextVar
```

### app.py 修改清单

| 操作 | 位置 | 目的 |
|------|------|------|
| `app.add_middleware(CSRFMiddleware)` | app.py | CSRF 保护 |
| `app.add_middleware(AuthMiddleware)` | app.py | 认证 enforcement |
| `lifespan=lifespan` | app.py | 启动/关闭钩子 |

### GSIC-003 状态：**推至 R241-22G**

| 原因 | 说明 |
|------|------|
| SURFACE-010 未解除 | DT-001 (user_context) 和 DT-002 (engine.py) 均未完成 |
| Auth Bundle C 未完成 | auth_middleware.py 属于 Sub-Bundle C |
| Persistence Stage 3 未完成 | session_factory 来源未确认 |

---

## 9. GSIC-004 实现计划（app.py）

### app.py 修改

```python
app.include_router(auth.router)  # 9 routes at /api/v1/auth/*
```

### 9 Auth Routes

| Method | Path | Auth Required | Public |
|--------|------|--------------|--------|
| POST | `/login/local` | ❌ | ✅ |
| POST | `/register` | ❌ | ✅ |
| POST | `/logout` | ❌ | ✅ |
| POST | `/change-password` | ✅ | |
| GET | `/me` | ✅ | |
| GET | `/setup-status` | ❌ | ✅ |
| POST | `/initialize` | ❌ | ✅ |
| GET | `/oauth/{provider}` | ❌ | ✅ |
| GET | `/callback/{provider}` | ❌ | ✅ |

### GSIC-004 状态：**推至 R241-22G（与 GSIC-003 耦合）**

---

## 10. GW-START-01~06 实现映射

| Gate ID | Name | 实现位置 | 条件 |
|---------|------|----------|------|
| **GW-START-01** | Persistence engine before middleware | deps.py langgraph_runtime() → app.py lifespan | ✅ 已在序列中 |
| **GW-START-02** | Memory fallback when sf=None | deps.py langgraph_runtime() 第 4/5/7 步 | ✅ 已在序列中 |
| **GW-START-03** | Admin bootstrap graceful | app.py _ensure_admin_user() 第 1 步 | ✅ 已有 early return |
| **GW-START-04** | Middleware chain order | app.py add_middleware 顺序 | ✅ 已规划 |
| **GW-START-05** | Public path bypass | auth_middleware.py _is_public() | ⚠️ Auth Bundle C |
| **GW-START-06** | Provider error if sf=None | deps.py get_local_provider() | ✅ 已有 raise |

---

## 11. RR-01~05 依赖映射

| Gate ID | Name | 依赖 |
|---------|------|------|
| **RR-01** | All 9 routes unique | routers/auth.py 静态检查 |
| **RR-02** | Protected routes use auth | routers/auth.py @require_auth |
| **RR-03** | Public routes bypass auth | auth_middleware.py _is_public() |
| **RR-04** | Rate limiting on login/register | routers/auth.py rate_limit decorator |
| **RR-05** | No route registration outside app.py | 代码审查 |

---

## 12. Feature Flag 实现策略

### MAINLINE_GATEWAY_ACTIVATION

```python
# app.py
if os.getenv("MAINLINE_GATEWAY_ACTIVATION", "false").lower() == "true":
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(AuthMiddleware)
    app.include_router(auth.router)
```

### AUTH_ROUTES_ENABLED

```python
# app.py
if os.getenv("AUTH_ROUTES_ENABLED", "true").lower() == "true":
    app.include_router(auth.router)
```

### AUTH_MIDDLEWARE_ENABLED

```python
# app.py
if os.getenv("AUTH_MIDDLEWARE_ENABLED", "true").lower() == "true":
    app.add_middleware(AuthMiddleware)
    app.add_middleware(CSRFMiddleware)
```

### DATABASE_BACKEND

```python
# engine.py / deps.py
backend = os.getenv("DATABASE_BACKEND", "memory")
# memory → get_session_factory() returns None
# sqlite/postgres → get_session_factory() returns real factory
```

---

## 13. Rollback 计划

### Middleware Rollback

```python
# 注释掉：
# app.add_middleware(AuthMiddleware)
# app.add_middleware(CSRFMiddleware)
# app.state 中的 9 个属性仍存在但未使用
```

### Route Registration Rollback

```python
# 注释掉：
# app.include_router(auth.router)
# 结果：所有 /api/v1/auth/* → 404
```

### Full Rollback

```python
# 注释掉 lifespan=lifespan
# 恢复原来的简短 lifespan
# 移除所有 app.state 初始化
```

---

## 14. R241-22G 前置条件

| 前置 | 状态 | 说明 |
|------|------|------|
| SURFACE-010 unblocked | ❌ BLOCKED | DT-001 (user_context.py) + DT-002 (engine.py) |
| Auth Bundle C 完成 | ❌ | user_context, authz, internal_auth, auth_middleware |
| Persistence Stage 3 完成 | ❌ | engine.py, UserRow, base.py, models |
| Persistence Stage 4 完成 | ❌ | FeedbackRepository, RunRepository, DbRunEventStore |
| MemoryRunStore 可用 | ✅ | 已存在于 `runtime/runs/store/memory.py` |
| JsonlRunEventStore 可用 | ✅ | CAND-013 已规划 |

---

## 15. 依赖链总结

```
SURFACE-010 (unblock)
    │
    ├── DT-001: user_context.py ──────────────────────────────┐
    │    └── auth_middleware.py ──────────────────────────────┤
    │         └── app.py add_middleware(AuthMiddleware) ───────┼── GSIC-003
    │
    └── DT-002: engine.py ───────────────────────────────────┘
         └── get_session_factory()
              └── LocalAuthProvider
                   └── get_local_provider() ──────────────────┤
                        └── auth routes ──────────────────────┼── GSIC-004
                             └── app.py include_router ───────┘

Auth Bundle (Sub-Bundle C) ─────────────────┐
                                            ├──→ Gateway (R241-22G)
Persistence Bundle (Stage 3+4) ────────────┘
```

**关键**：Auth Bundle 和 Persistence Bundle 可并行开发，都完成后才能激活 Gateway

---

## 16. Explicit Stop Conditions

| Condition | Action |
|-----------|--------|
| SURFACE-010 not yet unblocked | Do not activate gateway |
| Auth Sub-Bundle C not complete | auth_middleware not available |
| Persistence Stage 3+4 not complete | session_factory not available |
| GSIC-003/GSIC-004 not both unblocked | Do not do partial activation |
| MAINLINE_GATEWAY_ACTIVATION != "true" | Gateway stays inactive |
| Code modification detected during review | Abort and report safety violation |

---

## 17. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| deps_py_modified | ❌ false |
| app_py_modified | ❌ false |
| gateway_app_modified | ❌ false |
| middleware_added | ❌ false |
| route_registered | ❌ false |
| db_written | ❌ false |
| jsonl_written | ❌ false |
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

## R241_22F_GATEWAY_DEPS_APP_IMPLEMENTATION_PLAN_REVIEW_DONE

```
status=passed_with_warnings
deps_py_plan_completed=true
app_py_plan_completed=true
langgraph_runtime_contract_completed=true
get_local_provider_contract_completed=true
get_current_user_from_request_contract_completed=true
ensure_admin_user_contract_completed=true
gsic003_deferred=true
gsic004_deferred=true
gsic003_004_coupled_confirmed=true
feature_flag_strategy_completed=true
rollback_plan_completed=true
gw_start_gate_mapping_completed=true
rr_gate_mapping_completed=true
r241_22g_prerequisites_confirmed=true
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

**A.** R241-22G — GSIC-003 + GSIC-004 COUPLED unblock design（需要 SURFACE-010 + Auth Bundle C + Persistence Stage 3+4）
**B.** R241-22H — Auth Bundle Sub-Bundle D (CAND-004 reset_admin.py) implementation plan
**C.** R241-22I — Gateway integration tests design
**D.** Pause R241-22, return to R241 mainline for CAND-016/CAND-017/CAND-020