# R241-21G Unified Dependency Matrix Review

**报告ID**: R241-21G_UNIFIED_DEPENDENCY_MATRIX_REVIEW
**生成时间**: 2026-04-29T12:30:00+08:00
**阶段**: Phase 21G — Unified Dependency Matrix Review
**前置条件**: R241-21D + R241-21E + R241-21F (all passed_with_warnings)
**状态**: ✅ PASSED_WITH_WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED_WITH_WARNINGS
**decision**: unified_matrix_completed_all_bundles_cross_dependent_on_surface010
**unified_matrix_completed**: true
**bundles_merged**: [AUTH, PERSISTENCE, GATEWAY]
**total_candidates**: 17
**root_blocker**: SURFACE-010
**implementation_allowed**: false
**all_candidates_blocked**: true

**关键结论**：
- 3 个 bundles（Auth, Persistence, Gateway）全部交叉依赖 SURFACE-010
- 17 个 candidates 中：3 个 safe design-only，12 个 blocked，2 个 blocked by memory_read_binding
- CAND-009 (persistence/engine.py) 和 CAND-005 (auth_middleware) 是 SURFACE-010 的两个直接触发器
- 所有 7 stages 必须串行执行，impossible parallelization 列表为空
- **推荐 R241-22A 入口点：内存 runtime unblock**

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

---

## 3. Unified Dependency Graph

### Layer Architecture

```
Layer 0: DESIGN ONLY (3 candidates)
├── CAND-001 auth/__init__.py + 8 submodules (~388 LOC)
├── CAND-006 langgraph_auth.py (~100 LOC)
└── CAND-019 services.py (~247 LOC)
    └── No runtime activation, no SURFACE-010, no GSIC

Layer 1: AUTH INTERFACE (2 candidates)
├── CAND-002 jwt.py — blocked by CAND-002_memory_read_binding
└── CAND-023 local_provider.py — depends on Layer 0 + Layer 1

Layer 2: AUTH IMPLEMENTATION (2 candidates) ← SURFACE-010
├── CAND-005 auth_middleware.py — SURFACE-010 DIRECT (user_context)
└── CAND-004 reset_admin.py — SURFACE-010 indirect + privileged

Layer 3: PERSISTENCE ENGINE (2 candidates) ← SURFACE-010
├── CAND-009 engine.py — SURFACE-010 PRIMARY TRIGGER
└── CAND-024 user/model.py — depends on engine.py

Layer 4: PERSISTENCE REPOSITORIES (4 candidates)
├── CAND-010 feedback/sql.py — depends on engine.py
├── CAND-011 run/sql.py — depends on engine.py
├── CAND-012 runtime/events/store/db.py — depends on engine + user_context
└── CAND-013 runtime/events/store/jsonl.py — depends on engine.py

Layer 5: PERSISTENCE ENTRY (1 candidate)
└── CAND-008 persistence/__init__.py — triggers init_engine at startup

Layer 6: GATEWAY DEPS (implicit) ← GSIC-003 + SURFACE-010
└── deps.py langgraph_runtime() — initializes all persistence + auth middleware

Layer 7: GATEWAY APP (1 candidate) ← GSIC-003 + SURFACE-010
└── CAND-018 app.py — middleware chain + lifespan hooks

Layer 8: GATEWAY ROUTES (1 candidate) ← GSIC-004 + SURFACE-010
└── CAND-007 routers/auth.py — 9 routes at /api/v1/auth/*
```

---

## 4. Bundle Dependency Matrix

### Auth Bundle (6 candidates)

| ID | Path | Layer | SURFACE-010 | GSIC | Blocked By |
|----|------|-------|-------------|------|-----------|
| CAND-001 | auth/__init__.py + 8 submodules | 0 | ❌ | ❌ | Authorization |
| CAND-002 | auth/jwt.py | 1 | ❌ | ❌ | CAND-002_memory_read_binding |
| CAND-006 | langgraph_auth.py | 0 | ❌ | ❌ | CAND-002 blocked |
| CAND-023 | auth/local_provider.py | 1 | ❌ | ❌ | Sub-Bundle A |
| CAND-005 | auth_middleware.py | 2 | ⚠️ **DIRECT** | indirect | **SURFACE-010** |
| CAND-004 | auth/reset_admin.py | 2 | indirect | ❌ | **SURFACE-010** + privileged |

### Persistence Bundle (7 candidates)

| ID | Path | Layer | SURFACE-010 | GSIC | Blocked By |
|----|------|-------|-------------|------|-----------|
| CAND-009 | persistence/engine.py | 3 | ⚠️ **PRIMARY TRIGGER** | ❌ | **SURFACE-010** |
| CAND-024 | persistence/user/model.py | 3 | indirect | ❌ | **SURFACE-010** + CAND-009 |
| CAND-010 | persistence/feedback/sql.py | 4 | indirect | ❌ | **SURFACE-010** + CAND-009 |
| CAND-011 | persistence/run/sql.py | 4 | indirect | ❌ | **SURFACE-010** + CAND-009 |
| CAND-012 | runtime/events/store/db.py | 4 | indirect + user_context | ❌ | **SURFACE-010** + CAND-009 |
| CAND-013 | runtime/events/store/jsonl.py | 4 | indirect | ❌ | **SURFACE-010** + CAND-009 |
| CAND-008 | persistence/__init__.py | 5 | indirect | ❌ | **SURFACE-010** + all above |

### Gateway Bundle (3 candidates)

| ID | Path | Layer | SURFACE-010 | GSIC | Blocked By |
|----|------|-------|-------------|------|-----------|
| CAND-019 | services.py | 0 | indirect | ❌ | Authorization |
| CAND-018 | app.py | 7 | ⚠️ **DIRECT** | ⚠️ **GSIC-003** | **SURFACE-010** + **GSIC-003** |
| CAND-007 | routers/auth.py | 8 | indirect | ⚠️ **GSIC-004** | **SURFACE-010** + **GSIC-003** + **GSIC-004** |

---

## 5. Blocker → Candidate Mapping

| Blocker | Directly Blocks | Indirectly Blocks | Unblock Prerequisite |
|---------|----------------|-------------------|---------------------|
| **SURFACE-010** | CAND-005, CAND-009 | CAND-004, CAND-007, CAND-008, CAND-010, CAND-011, CAND-012, CAND-013, CAND-018, CAND-024 | Memory runtime stable |
| **GSIC-003** | CAND-018 | CAND-007 | SURFACE-010 + persistence engine |
| **GSIC-004** | CAND-007 | — | Auth bundle + GSIC-003 |
| **CAND-002_memory_read_binding** | CAND-002 | CAND-006 | memory_read_binding impl |
| **Authorization** | CAND-001, CAND-019 | CAND-023 | Scope expansion |

---

## 6. Candidate → Required Files Mapping

### Required Files Per Candidate

| Candidate | Required Files | Total | Layer |
|-----------|----------------|-------|-------|
| CAND-001 | auth/__init__.py + 8 submodules | 9 | 0 |
| CAND-002 | jwt.py, config.py, errors.py | 3 | 1 |
| CAND-004 | reset_admin.py, local_provider.py, engine.py, user/model.py | 4 | 2 |
| CAND-005 | auth_middleware.py, authz.py, internal_auth.py, user_context.py | 4 | 2 |
| CAND-006 | langgraph_auth.py, jwt.py, deps.py | 3 | 0 |
| CAND-007 | routers/auth.py, auth/__init__.py, jwt.py, local_provider.py, config.py, errors.py, deps.py | 7 | 8 |
| CAND-008 | persistence/__init__.py, engine.py, user/model.py, feedback/sql.py, run/sql.py | 5 | 5 |
| CAND-009 | engine.py | 1 | 3 |
| CAND-010 | feedback/sql.py, engine.py | 2 | 4 |
| CAND-011 | run/sql.py, engine.py | 2 | 4 |
| CAND-012 | db.py, engine.py, user_context.py | 3 | 4 |
| CAND-013 | jsonl.py, engine.py | 2 | 4 |
| CAND-018 | app.py, auth_middleware.py, deps.py, engine.py, user/model.py | 5 | 7 |
| CAND-019 | services.py, deps.py | 2 | 0 |
| CAND-024 | user/model.py, engine.py | 2 | 3 |

**Grand Total: 55 file dependencies across all 17 candidates**

---

## 7. SURFACE-010 Root Blocker Impact Map

```
                    ┌─────────────────────────────────────┐
                    │      SURFACE-010 memory BLOCKED     │
                    │      CRITICAL — ROOT BLOCKER        │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
┌─────────────────────────────┐         ┌─────────────────────────────┐
│  user_context.py            │         │  persistence/engine.py     │
│  (ContextVar per-request)   │         │  (init_engine startup DB)   │
│                             │         │                             │
│  SURFACE-010 DIRECT         │         │  SURFACE-010 PRIMARY TRIGGER│
│  Used by:                   │         │  Triggers:                  │
│  • auth_middleware.py       │         │  • CREATE DATABASE           │
│  • internal_auth.py         │         │  • WAL mode setup            │
│                             │         │  • schema create_all        │
└──────────────┬──────────────┘         │                             │
               │                        └──────────────┬──────────────┘
               │                                   │
    ┌──────────┴──────────┐           ┌───────────┴───────────┐
    ▼                     ▼           ▼                       ▼
CAND-005           CAND-012     CAND-024              CAND-010
auth_middleware    db.py        user/model.py         feedback/sql
    │                │             │                       │
    │            user_context       │                       │
    │           (circular dep!)     │                       │
    └─────────────────┬─────────────┘                       │
                      │                                     │
              ┌───────┴───────┐                   ┌────────┴────────┐
              ▼               ▼                   ▼                 ▼
          CAND-004      CAND-007           CAND-011            CAND-008
        reset_admin   routers/auth       run/sql.py       persistence/__init__
              │             │                 │                   │
              │        GSIC-004          session_factory      init_engine()
              │        blocked              │                   │
              └──────────────┬─────────────────┘                   │
                             ▼                                     │
                    ┌───────────────┐                             │
                    │  CAND-018     │                             │
                    │  app.py       │                             │
                    │  GSIC-003     │◄────────────────────────────┘
                    │  blocked      │
                    └───────────────┘

TOTAL: 12/17 candidates blocked by SURFACE-010 chain
```

---

## 8. GSIC-003 / GSIC-004 Dependency Map

### GSIC-003: Gateway Main Path

```
Gateway Main Path Modification Chain:
┌──────────────────────────────────────────────────────────────┐
│ app.py                                                      │
│  ├── imports: AuthMiddleware (CAND-005, SURFACE-010)        │
│  ├── imports: CSRFMiddleware                               │
│  ├── imports: deps.langgraph_runtime()                      │
│  └── lifespan: async with langgraph_runtime(app)           │
│       │                                                    │
│       ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ deps.py: langgraph_runtime()                         │   │
│  │  ├── init_engine_from_config() → CAND-009 (S-010)   │   │
│  │  ├── make_checkpointer()                            │   │
│  │  ├── make_store()                                    │   │
│  │  ├── RunRepository(session_factory) → CAND-011       │   │
│  │  ├── FeedbackRepository(session_factory) → CAND-010  │   │
│  │  ├── make_thread_store() → upstream                 │   │
│  │  └── make_run_event_store() → CAND-012/CAND-013     │   │
│  └─────────────────────────────────────────────────────┘   │
│       │                                                    │
│       ▼                                                    │
│  _ensure_admin_user(app)                                   │
│  └── Uses: UserRow (CAND-024) + session_factory            │
└──────────────────────────────────────────────────────────────┘

GSIC-003 Files: [app.py, deps.py]
Blocked By: SURFACE-010
Enables: CAND-018 (app.py), CAND-007 (indirectly)
```

### GSIC-004: FastAPI Route Registration

```
Route Registration Chain:
┌──────────────────────────────────────────────────────────────┐
│ routers/auth.py (CAND-007)                                  │
│  ├── prefix: "/api/v1/auth"                               │
│  ├── routes: 9 endpoints                                   │
│  ├── imports: app.gateway.auth (CAND-001)                  │
│  ├── imports: app.gateway.auth.jwt (CAND-002)              │
│  ├── imports: app.gateway.auth.local_provider (CAND-023)  │
│  ├── imports: app.gateway.deps (GSIC-003)                 │
│  │    └── get_local_provider() → needs persistence         │
│  └── imports: app.gateway.auth.errors                      │
└──────────────────────────────────────────────────────────────┘

GSIC-004 Files: [routers/auth.py]
Blocked By: SURFACE-010 + GSIC-003 + Auth bundle
Enables: CAND-007 (auth routes)
```

### GSIC Cross-Dependency

```
GSIC-003 must resolve BEFORE GSIC-004 because:
1. routers/auth.py imports from app.gateway.deps
2. deps.py requires persistence.engine (SURFACE-010)
3. Without deps.py, get_local_provider() fails
4. Without get_local_provider(), login/logout/register all fail

Sequential: SURFACE-010 → GSIC-003 → GSIC-004
```

---

## 9. Minimum Viable Staged Sequence

| Stage | Name | Candidates | SURFACE-010 | GSIC | Can Implement |
|-------|------|-----------|-------------|------|--------------|
| **1** | Auth Interface Stubs | CAND-001, CAND-006 | ❌ | ❌ | design_only |
| **2** | Memory Runtime Unblock | user_context, auth_middleware | **DIRECT** | ❌ | after evidence |
| **3** | Persistence Engine | CAND-009, CAND-024 | **DIRECT** | ❌ | after stage 2 |
| **4** | Persistence Repositories | CAND-010, CAND-011 | indirect | ❌ | after stage 3 |
| **5** | Event Stores + Entry | CAND-008, CAND-012, CAND-013 | indirect | ❌ | after stage 3 |
| **6** | Gateway Deps + App | CAND-018, deps.py | ⚠️ DIRECT | **GSIC-003** | after stages 2+3+4 |
| **7** | Auth Routes (GSIC-004) | CAND-007 | indirect | **GSIC-004** | after stages 1+2+6 |

**No parallelization possible — all stages are strictly sequential**

---

## 10. Impossible Parallelization List

| Pair | Reason |
|------|--------|
| CAND-005 + CAND-009 | Both SURFACE-010 direct triggers; must be sequential |
| CAND-008 + CAND-007 | CAND-008 must exist before CAND-007 can import |
| CAND-018 + CAND-007 | app.py lifespan init must complete before routes register |
| deps.py + CAND-018 | deps.py is a prerequisite for app.py |
| CAND-009 + CAND-010 | engine.py must init before feedback/sql uses session_factory |
| CAND-009 + CAND-011 | engine.py must init before run/sql uses session_factory |
| CAND-009 + CAND-024 | engine.py must init before UserRow is used |
| CAND-024 + CAND-018 | UserRow must exist before _ensure_admin_user runs |
| CAND-001 + CAND-007 | auth/__init__ exports must exist before routers/auth imports |
| CAND-002 + CAND-006 | jwt.py must exist before langgraph_auth uses create_access_token |

---

## 11. Safe Design-Only Subset

| Candidate | Path | Files | Reason |
|-----------|------|-------|--------|
| CAND-001 | auth/__init__.py + 8 submodules | 9 | No runtime, pure Python, but auth/ dir creation blocked |
| CAND-006 | langgraph_auth.py | 1 | No runtime, but depends on blocked CAND-002 |
| CAND-019 | services.py | 1 | No runtime, but services.py creation blocked |
| **Total** | | **11 files** | **Design viable, apply blocked by authorization** |

**Design viability**: ✅ YES
**Apply viability**: ❌ NO — cannot create auth/ or gateway/ files per authorization

---

## 12. Implementation Forbidden Subset

| Candidate | Blocked By | Count |
|-----------|-----------|-------|
| CAND-005 | SURFACE-010 (direct) | 1 |
| CAND-009 | SURFACE-010 (direct) | 1 |
| CAND-004 | SURFACE-010 (indirect) + privileged | 1 |
| CAND-007 | SURFACE-010 + GSIC-003 + GSIC-004 | 1 |
| CAND-008 | SURFACE-010 (persistence chain) | 1 |
| CAND-010 | SURFACE-010 (persistence chain) | 1 |
| CAND-011 | SURFACE-010 (persistence chain) | 1 |
| CAND-012 | SURFACE-010 (persistence chain) | 1 |
| CAND-013 | SURFACE-010 (persistence chain) | 1 |
| CAND-018 | SURFACE-010 + GSIC-003 | 1 |
| CAND-024 | SURFACE-010 (persistence chain) | 1 |
| CAND-002 | CAND-002_memory_read_binding | 1 |
| **Total** | | **12** |

---

## 13. Evidence Required Before Unblock

### SURFACE-010 Unblock

| Evidence | Description | Pass Criteria |
|----------|-------------|--------------|
| Memory leak test | 10k sustained requests | No memory growth > 5% |
| ContextVar isolation | Per-request state isolation | No cross-request leakage |
| Connection pool stability | 100 concurrent requests | Pool exhaustion < 1% |
| Startup time | init_engine completion | < 5 second threshold |
| Memory fallback | database.backend=memory | Returns None, no errors |
| Database backup | pg_dump / SQLite copy | Backup successful before any write |

### GSIC-003 Unblock

| Evidence | Description |
|----------|-------------|
| SURFACE-010 resolved | Memory runtime stable |
| CAND-009 initialized | Engine creates DB, runs create_all |
| CAND-024 available | UserRow ORM model usable |
| App state singletons | All 8 app.state initializations succeed |
| Middleware chain | AuthMiddleware + CSRFMiddleware chain works |

### GSIC-004 Unblock

| Evidence | Description |
|----------|-------------|
| SURFACE-010 resolved | Memory runtime stable |
| GSIC-003 resolved | Gateway main path unblocked |
| CAND-001 exists | Auth bundle interface stubs |
| CAND-002 implemented | JWT create/decode working |
| CAND-023 implemented | LocalAuthProvider working |
| Route registration | All 9 routes register without errors |

---

## 14. Final Recommended R241-22A Entry Point

### Recommended Entry Point: R241-22A_MEMORY_RUNTIME_UNBLOCK

| Property | Value |
|----------|-------|
| **Entry Point** | R241-22A_MEMORY_RUNTIME_UNBLOCK |
| **Root Cause** | SURFACE-010 blocks 12/17 candidates |
| **Immediate Action** | Design and implement stable memory runtime with ContextVar |

### Why Memory Runtime?

1. **Root blocker for 12 candidates** — without it, nothing downstream can proceed
2. **Two direct triggers** (user_context + engine.py) both require memory infrastructure
3. **Enables parallelization** of downstream stages once resolved
4. **Self-contained** — can be designed and tested independently

### Alternative Entry Point: R241-22B_AUTH_INTERFACE_STUB_APPLY

| Property | Value |
|----------|-------|
| **Entry Point** | R241-22B_AUTH_INTERFACE_STUB_APPLY |
| **Condition** | If authorization scope expands |
| **Enables** | Design documentation only, not runtime |

---

## 15. Safety Boundary

| 检查项 | 状态 |
|--------|------|
| runtime_touch_detected | ❌ false |
| dependency_execution_executed | ❌ false |
| code_modified | ❌ false |
| auth_dir_created | ❌ false |
| persistence_dir_created | ❌ false |
| gateway_app_modified | ❌ false |
| route_registered | ❌ false |
| patch_applied | ❌ false |
| blockers_preserved | ✅ true |
| safety_violations | [] |

---

## 16. Carryover Blockers (8 preserved)

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

## R241_21G_UNIFIED_DEPENDENCY_MATRIX_REVIEW_DONE

```
status=passed_with_warnings
unified_matrix_completed=true
bundles_merged=[AUTH,PERSISTENCE,GATEWAY]
root_blocker=SURFACE-010
implementation_allowed=false
runtime_touch_detected=false
dependency_execution_executed=false
code_modified=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-22A
next_prompt_needed=user_selection
```
