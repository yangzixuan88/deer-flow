# R241-22J Auth Sub-Bundle D (reset_admin.py) Implementation Plan Review

**报告ID**: R241-22J_AUTH_SUB_BUNDLE_D_RESET_ADMIN_IMPLEMENTATION_PLAN_REVIEW
**生成时间**: 2026-04-29T16:30:00+08:00
**阶段**: Phase 22J — Auth Sub-Bundle D reset_admin.py Implementation Plan Review
**前置条件**: R241-22I Gateway Integration Tests Design Review (passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: reset_admin_plan_completed_cli_only_no_http_exposure_confirmed
**reset_admin_plan_completed**: true
**privileged_auth_risk_matrix_completed**: true
**implementation_allowed**: false
**surface010_unblocked**: false

**关键结论**：
- `reset_admin.py` 是 **CLI 专用工具**（`python -m app.gateway.auth.reset_admin`），不是 HTTP 端点
- 不注册任何 FastAPI route，不修改 gateway main path
- 凭证文件通过原子 O_CREAT|O_TRUNC + mode 0600 写入，防止凭证泄露
- `SURFACE-010 DT-002`（engine.py）必须先解除才能运行 reset_admin.py
- `DAT-001`（user_context.py）不需要 —— reset_admin.py 不走 FastAPI 中间件链

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. reset_admin.py 文件清单

### 核心文件

| 文件 | 路径 | LOC | HTTP 暴露 | Route 注册 | Gateway 修改 |
|------|------|-----|----------|------------|--------------|
| `reset_admin.py` | `app/gateway/auth/reset_admin.py` | ~80 | ❌ | ❌ | ❌ |
| `credential_file.py` | `app/gateway/auth/credential_file.py` | ~70 | ❌ | ❌ | ❌ |
| `local_provider.py` | `app/gateway/auth/local_provider.py` | ~120 | ❌ | ❌ | ❌ |
| `sqlite.py` (repository) | `app/gateway/auth/repositories/sqlite.py` | ~200 | ❌ | ❌ | ❌ |
| `user/model.py` (UserRow) | `packages/harness/deerflow/persistence/user/model.py` | ~70 | ❌ | ❌ | ❌ |
| `engine.py` | `packages/harness/deerflow/persistence/engine.py` | ~180 | ❌ | ❌ | ❌ |

**结论**：无 HTTP 暴露，无 route 注册，无 gateway main path 修改

---

## 4. Privileged Operation Inventory

| ID | 操作 | 位置 | 严重性 | 威胁 | 缓解 |
|----|------|------|--------|------|------|
| PRIV-01 | Password hash write | `reset_admin.py: user.password_hash = hash_password(new_password)` | HIGH | 内存中明文密码 | 立即用 dfv2 哈希，不存储/不记录明文 |
| PRIV-02 | Token version increment | `reset_admin.py: user.token_version += 1` | HIGH | 所有现有 JWT 立即失效 | 意图行为——强制重新认证 |
| PRIV-03 | needs_setup flag set | `reset_admin.py: user.needs_setup = True` | MEDIUM | 用户下次登录必须完成 setup | 操作员通过日志获知 |
| PRIV-04 | Credential file write | `credential_file.py: write_initial_credentials()` | HIGH | 密码写入磁盘 | 原子 O_CREAT\|O_TRUNC + mode 0600 |
| PRIV-05 | Database user lookup | `reset_admin.py: repo.get_user_by_email()` | LOW | 邮箱枚举 | 仅本地 shell 访问可用 |
| PRIV-06 | Persistence engine init | `reset_admin.py: init_engine_from_config()` | MEDIUM | 创建/修改 SQLite 数据库文件 | 预期行为——reset 必须有数据库 |

---

## 5. Admin Reset Threat Model

### Attack Vectors

| 向量 | 风险 | 场景 | 现有缓解 | 残余风险 |
|------|------|------|----------|----------|
| 本地 CLI 访问 | HIGH | 攻击者运行 `reset_admin.py` | 需要认证的 shell 会话，文件 mode 0600 | 操作员必须保护 shell |
| 日志注入 | LOW | 密码打印到 stdout/stderr | 从不打印密码——只写入文件 | 无 |
| 凭证文件窃取 | MEDIUM | 读取 `.deer-flow/admin_initial_credentials.txt` | mode 0600，操作员登录后应删除 | 操作员可能忘记删除 |
| 内存暴露 | LOW | 明文密码在进程内存中 | 哈希后立即丢弃 | 短暂窗口 |
| JWT 重用 | LOW | reset 后使用旧 JWT | `token_version` 检查强制使旧 token 失效 | 无 |

### 风险总结

| 风险 | 状态 |
|------|------|
| 关键凭证泄露 | 已缓解 — file mode 0600 |
| 日志暴露 | 已缓解 — 不打印密码 |
| reset 后 JWT 重用 | 已缓解 — token_version increment |
| 未授权 reset | 部分缓解 — 需要本地 shell 访问 |

---

## 6. Required Persistence Dependencies

| 依赖 | 状态 | 用途 | Blocking |
|------|------|------|----------|
| `engine.py` (DT-002) | SURFACE-010 BLOCKED | `init_engine_from_config()` | ✅ Yes |
| `UserRow` (CAND-024) | R241-22C | SQLiteUserRepository 映射 | ❌ |
| `SQLiteUserRepository` | Auth Bundle C | reset_admin.py 直接使用 | ❌ |
| `session_factory` | SURFACE-010 BLOCKED | `get_session_factory()` 返回 None 则 exit | ✅ Yes |

### 关键发现

```
reset_admin.py 依赖 DT-002 (engine.py)：
    └── init_engine_from_config() — SURFACE-010 DT-002 解除后可用

reset_admin.py 不依赖 DT-001 (user_context.py)：
    └── CLI 工具不走 FastAPI 中间件链

Auth Bundle C 可以与 reset_admin 并行开发（无相互依赖）
```

---

## 7. Password Reset Flow Contract

### 入口

```bash
python -m app.gateway.auth.reset_admin [--email EMAIL]
```

### 执行流程（10 步）

```
Step 1: init_engine_from_config(config.database)
        用途：初始化 SQLAlchemy 引擎
        阻塞：SURFACE-010 DT-002 必须解除

Step 2: get_session_factory()
        错误处理：sf is None → "persistence engine not available"

Step 3: 用户查找
        --email 提供 → repo.get_user_by_email(email)
        无 --email → SELECT first admin (system_role='admin' LIMIT 1)
        错误处理：not found → exit code 1

Step 4: new_password = secrets.token_urlsafe(16)
        用途：生成 16 字节安全随机密码

Step 5: user.password_hash = hash_password(new_password)
        算法：dfv2 (SHA-256 + bcrypt)

Step 6: user.token_version += 1
        用途：使该用户所有现有 JWT 立即失效

Step 7: user.needs_setup = True
        用途：强制用户下次登录完成 setup

Step 8: await repo.update_user(user)
        用途：持久化到数据库

Step 9: write_initial_credentials(user.email, new_password, label='reset')
        路径：.deer-flow/admin_initial_credentials.txt
        模式：O_WRONLY|O_CREAT|O_TRUNC, mode 0600

Step 10: close_engine()
         用途：释放连接
```

### Exit Codes

| Code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 错误（用户不存在、引擎不可用等） |

---

## 8. Token Version Invalidation Contract

### 机制

```python
user.token_version += 1  # 在 reset_admin.py 中
```

### JWT 验证位置

```python
# app/gateway/deps.py:get_current_user_from_request()
if user.token_version != payload.ver:
    raise HTTPException(401, "Token revoked (password changed)")
```

### JWT Payload

```python
TokenPayload(sub=user_id, exp=exp, iat=iat, ver=token_version)
```

### 注意事项

- `token_version` 单调递增，无法回滚
- 如果意外执行 reset，所有 token 保持无效状态

---

## 9. needs_setup / system_role Handling

### needs_setup Flag

| 属性 | 值 |
|------|---|
| 字段 | `User.needs_setup` (bool) |
| reset_admin.py 设置 | `True` |
| 首次 admin 创建 | `False` (via /setup endpoint) |
| 效果 | 用户下次登录必须完成 setup |
| 清除时机 | 用户完成 setup 后 |

### system_role Field

| 属性 | 值 |
|------|---|
| 字段 | `User.system_role` (Literal['admin', 'user']) |
| reset_admin.py 修改 | **不修改** |
| reset_admin.py 查找 | `WHERE system_role == 'admin' LIMIT 1` |

### 决策边界

```
reset_admin.py 作用：
    - 重置现有 admin 的密码
    - 不创建第一个 admin
    - 不修改 system_role

第一个 admin 创建：
    - 通过 POST /api/v1/auth/initialize
    - 需要 count_admin_users() == 0
    - 设置 system_role='admin', needs_setup=False
```

---

## 10. First-Admin / Existing-Admin Decision Boundary

### 首次 Admin 创建

| 方面 | 值 |
|------|---|
| 机制 | `POST /api/v1/auth/initialize` |
| 条件 | `count_admin_users() == 0` |
| 设置 | `system_role='admin'`, `needs_setup=False` |
| Gateway 保护 | 无（未激活时也可调用） |

### 现有 Admin Reset

| 方面 | 值 |
|------|---|
| 机制 | `python -m app.gateway.auth.reset_admin` |
| 条件 | admin 已存在 |
| 修改 | `password_hash` (新), `token_version+=1`, `needs_setup=True` |
| 不修改 | `system_role` |
| Gateway 保护 | 无（CLI 工具） |

### 无自动 Admin 创建

```python
# _ensure_admin_user() in app.py
if admin_count == 0:
    logger.info("First boot detected — visit /setup")
    return  # 不自动创建！
```

---

## 11. CLI-Only vs HTTP-Exposed Boundary

### reset_admin CLI

| 方面 | 值 |
|------|---|
| 接口 | `python -m app.gateway.auth.reset_admin` |
| 执行上下文 | 本地 shell，不是 HTTP |
| 无 route 注册 | ✅ guaranteed |
| 无 FastAPI router | ✅ guaranteed |
| 调用方式 | 操作员手动在 host 上运行 |

### 无 HTTP 等价物

| 方面 | 值 |
|------|---|
| HTTP reset 端点 | **不存在** |
| 原因 | Admin password reset 是特权操作，需要 host 访问权限 |
| 替代方案 | 操作员 SSH 到 host 运行 CLI 工具 |

---

## 12. No-Route-Registration Guarantee

### 验证证据

```
✅ reset_admin.py 无 app.add_route() 调用
✅ reset_admin.py 无 app.include_router() 调用
✅ reset_admin.py 无 FastAPI router 对象
✅ reset_admin.py 不在 app/gateway/routers/ 目录
✅ app.py 不导入 reset_admin
✅ deps.py 不导入 reset_admin
```

### 结论

**GUARANTEED**: `reset_admin.py` 不注册任何 FastAPI route

---

## 13. No-Gateway-Main-Path-Modification Guarantee

### 验证证据

```
✅ app.py 不导入 reset_admin
✅ deps.py 不导入 reset_admin
✅ lifespan 函数不调用 reset_admin
✅ 无 middleware chain 修改
```

### 结论

**GUARANTEED**: `reset_admin.py` 不修改 gateway main path

---

## 14. SURFACE-010 Dependency Mapping

### 依赖链

```
reset_admin.py 运行
    │
    └── init_engine_from_config() — 需要 DT-002 (engine.py)
         │
         └── get_session_factory() — 需要 engine.py
              │
              └── SQLiteUserRepository — 需要 session_factory
                   │
                   └── UserRow — 需要 CAND-024 (R241-22C)
```

### DT-001 不需要

```
reset_admin.py 不使用 user_context.py (ContextVar)
原因：CLI 工具不经过 FastAPI 中间件链
```

### Memory Backend 处理

```python
sf = get_session_factory()
if sf is None:
    print("Error: persistence engine not available...", file=sys.stderr)
    return 1
```

---

## 15. Privileged Audit Evidence Requirements

### 必需审计轨迹

| 事件 | 操作员操作 | 记录到 | 凭证文件 | DB 变更 |
|------|-----------|--------|----------|---------|
| admin_password_reset | `python -m app.gateway.auth.reset_admin [--email EMAIL]` | stdout/stderr（仅路径，非密码） | `.deer-flow/admin_initial_credentials.txt` | password_hash, token_version, needs_setup |

### reset_admin.py 无审计日志

```
注意：reset_admin.py 不写入审计日志
stdout 消息：仅打印 "Password reset for: EMAIL" 和 "Credentials written to: PATH"
改进机会：可添加 syslog/journald 集成
```

### DB 审计

| 变更 | 审计等效 |
|------|----------|
| token_version increment | DB 写操作是审计等效——所有旧 token 失效 |
| timestamp | created_at 不变——reset 事件不在 DB 中时间戳 |

---

## 16. Test File Plan

### test_reset_admin.py

```python
# tests/unit/auth/test_reset_admin.py
# Cases:
# - reset with --email flag finds correct user
# - reset without --email finds first admin
# - reset with non-existent email exits with error
# - reset when no admin exists exits with error
# - password_hash is updated after reset
# - token_version incremented after reset
# - needs_setup set to True after reset
# - credential file written with correct content
# - credential file mode is 0600
# - exit code 0 on success
# - exit code 1 on user not found
```

### test_credential_file.py

```python
# tests/unit/auth/test_credential_file.py
# Cases:
# - write_initial_credentials creates file
# - file mode is 0600
# - file contains correct email and password
# - label='reset' appears in header
# - label='initial' appears in header
# - atomic write — partial content not visible
# - overwrites existing file
```

### Summary

| Files | Cases | Duration |
|-------|-------|----------|
| 2 | 17 | ~15s |

---

## 17. Implementation Order If Authorized

### Current Blockers

| Blocker | Status |
|---------|--------|
| SURFACE-010 DT-002 (engine.py) | BLOCKED — reset_admin.py 依赖 init_engine_from_config |
| SURFACE-010 DT-001 (user_context.py) | NOT REQUIRED — reset_admin.py 不走 middleware |

### Recommended Sequence

```
1. 验证 persistence/engine.py (DT-002) 实现完成
2. 验证 UserRow model 存在于 deerflow.persistence.user.model
3. 验证 SQLiteUserRepository 已实现
4. 读取 reset_admin.py 上游源码（已验证）
5. 创建 tests/unit/auth/test_reset_admin.py
6. 实现测试 — 全部通过后再创建 reset_admin.py
7. 如果所有 blocker 清除，实现 reset_admin.py
```

### 与 Auth Bundle C 的关系

```
reset_admin.py 依赖：engine.py (DT-002)
Auth Bundle C 依赖：user_context.py (DT-001)
两者可以并行开发，无相互依赖
```

---

## 18. Danger Zones

### Credential File Permissions (MEDIUM)

```
风险：Windows 上 atomic mode 0600 可能不生效
注意：Windows ACL 与 Unix 权限不同
建议：在 Windows 上测试验证
```

### No Audit Log (LOW)

```
风险：reset_admin.py 不写入审计日志
影响：无法追踪谁在何时运行了 reset
缓解：凭证文件路径可作为部分审计
```

### Token Version Monotonic (LOW)

```
风险：token_version 只能增加，无法回滚
影响：意外 reset 后所有 token 保持无效
缓解：仔细确认目标用户后再执行
```

### Memory Backend Exit (MEDIUM)

```
风险：database.backend=memory 时 reset_admin.py 静默退出
影响：操作员可能以为 reset 成功了
缓解：错误消息清晰说明 "persistence engine not available"
```

---

## 19. Explicit Stop Conditions

| Condition | Action |
|-----------|--------|
| SURFACE-010 DT-002 not yet unblocked | reset_admin.py will exit with error — operation fails safely |
| `init_engine_from_config()` raises | Exits with error code 1 |
| `get_session_factory()` returns None | Exits with: "persistence engine not available" |
| User not found | Exits with error message, exit code 1 |
| Code modification detected during review | Abort and report safety violation |

---

## 20. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| reset_admin_created | ❌ false |
| db_written | ❌ false |
| jsonl_written | ❌ false |
| admin_modified | ❌ false |
| password_reset_executed | ❌ false |
| route_registered | ❌ false |
| gateway_app_modified | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

---

## 21. Carryover Blockers (8 preserved)

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

## R241_22J_AUTH_SUB_BUNDLE_D_RESET_ADMIN_IMPLEMENTATION_PLAN_REVIEW_DONE

```
status=passed_with_warnings
reset_admin_plan_completed=true
privileged_auth_risk_matrix_completed=true
implementation_allowed=false
surface010_unblocked=false
route_registration_allowed=false
gateway_activation_allowed=false
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
db_written=false
jsonl_written=false
admin_modified=false
password_reset_executed=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-22G_or_R241-22K
next_prompt_needed=user_selection
```

---

## 选项

**A.** R241-22G — GSIC-003 + GSIC-004 COUPLED unblock design（需要 SURFACE-010 + Auth Bundle C + Persistence Stage 3+4 全部完成）

**B.** R241-22K — Continue with CAND-016/CAND-017/CAND-020 on R241 mainline

**C.** R241-22L — Auth Bundle Sub-Bundle E (remaining authz/permissions) implementation plan

**D.** Pause R241-22 entirely, return when SURFACE-010 is unblocked