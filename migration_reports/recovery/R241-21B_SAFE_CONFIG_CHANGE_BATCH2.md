# R241-21B Safe Config Change Batch 2

**报告ID**: R241-21B_SAFE_CONFIG_CHANGE_BATCH2
**生成时间**: 2026-04-29T10:50:00+08:00
**阶段**: Phase 21B — Safe Config Change Batch 2
**前置条件**: R241-21A Parallel Migration Acceleration Batch 1 (passed)
**状态**: ⚠️ BLOCKED_BY_UPSTREAM_AUTH_REFERENCE

---

## 1. Executive Conclusion

**状态**: ⚠️ BLOCKED_BY_UPSTREAM_AUTH_REFERENCE
**decision**: cannot_apply_upstream_langgraph_json
**reason**: upstream auth.path references non-existent local file

---

## 2. RootGuard / Git Baseline

### RootGuard

| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

### Git State

| 字段 | 值 |
|------|-----|
| **branch** | main |
| **HEAD** | 0bb97b51a5cea3b57a13188900c118faeb01c000 |
| **dirty_tracked** | 329 (pre-existing) |
| **staged** | 0 |

---

## 3. CAND-022 Source Diff Verification

### Upstream `origin/release/2.0-rc:backend/langgraph.json`

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "python_version": "3.12",
  "dependencies": ["."],
  "env": ".env",
  "graphs": {
    "lead_agent": "deerflow.agents:make_lead_agent"
  },
  "auth": {
    "path": "./app/gateway/langgraph_auth.py:auth"
  },
  "checkpointer": {
    "path": "./packages/harness/deerflow/runtime/checkpointer/async_provider.py:make_checkpointer"
  }
}
```

### Local `backend/langgraph.json` (current)

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "python_version": "3.12",
  "dependencies": ["."],
  "env": ".env",
  "graphs": {
    "lead_agent": "deerflow.agents:make_lead_agent"
  },
  "checkpointer": {
    "path": "./packages/harness/deerflow/agents/checkpointer/async_provider.py:make_checkpointer"
  }
}
```

### Diff Summary

| Field | Upstream | Local | Change |
|-------|---------|-------|--------|
| **auth** | `./app/gateway/langgraph_auth.py:auth` | (removed) | ❌ **BLOCKING** |
| **checkpointer** | `runtime/checkpointer/...` | `agents/checkpointer/...` | ✅ adapted |

---

## 4. Blocking Finding

### auth.path References Non-Existent Local File

| Check | Result |
|-------|--------|
| `backend/app/gateway/langgraph_auth.py` exists locally | ❌ **NOT FOUND** |
| `backend/app/gateway/auth/` directory exists locally | ❌ **NOT FOUND** |
| `backend/app/gateway/auth/jwt.py` exists locally | ❌ **NOT FOUND** |
| Upstream `langgraph_auth.py` exists | ✅ 106 lines in upstream |
| Upstream auth references valid path | ❌ **INVALID for local** |

### Why This Blocks Apply

If we apply the upstream `langgraph.json` with auth section, LangGraph Server would try to load `./app/gateway/langgraph_auth.py:auth` which **does not exist** in the local workspace. This would cause a **runtime import failure**.

**Conclusion**: CAND-022 is **NOT safe to port-back** as-is.

---

## 5. Safety Verification

### Runtime Activation Check

| 检查项 | 状态 | 说明 |
|--------|------|------|
| triggers persistence activation | ❌ false | config only |
| triggers memory initialization | ❌ false | no runtime init |
| triggers gateway registration | ❌ false | no route changes |
| triggers FastAPI registration | ❌ false | no API surface change |
| triggers MCP activation | ❌ false | no MCP tools |
| triggers DSRT | ❌ false | no DSRT config |
| triggers SURFACE-010 | ❌ false | no memory runtime |

### Blocker Impact Check

| 检查项 | 状态 |
|--------|------|
| SURFACE-010 modified | ❌ false |
| CAND-002 blocker impacted | ❌ false |
| CAND-003 blocker impacted | ❌ false |
| GSIC-003 blocker impacted | ❌ false |
| GSIC-004 blocker impacted | ❌ false |
| any blocker overridden | ❌ false |

### Pyproject / Dependency Check

| 检查项 | 状态 |
|--------|------|
| pyproject.toml modified | ❌ false |
| dependency added/removed | ❌ false |
| install triggered | ❌ false |

---

## 6. Structural Analysis

### Why Local Has No Auth Section

The `backend/app/gateway/auth/` directory does not exist in the local workspace. This is consistent with the R241-18/R241-19 refactoring that:
1. Split backend into `harness` (deerflow.*) and `app` (app.*) packages
2. Moved auth-related code to `deerflow.agents` namespace
3. Did NOT port the upstream auth module structure

### checkpointer Path Adaptation

The `agents/checkpointer/async_provider.py` path is the **local adaptation** of the upstream `runtime/checkpointer/async_provider.py` — reflecting the package split. This is correct and safe.

---

## 7. Decision

**status**: blocked_by_upstream_auth_reference
**decision**: cannot_apply_upstream_langgraph_json
**cand022_safe_to_apply**: false
**reason**: upstream auth.path references non-existent local file
**local_langgraph_json**: already adapted (auth removed, checkpointer path updated)
**runtime_activation_risk**: none
**blocker_impact**: none

---

## 8. Next Safe Subset (Revised)

Based on CAND-022 being blocked, the revised safe subset is:

| ID | 路径 | 状态 | 说明 |
|----|------|------|------|
| **CAND-001** | `auth/__init__.py` | ⚠️ verify | needs local auth dir check |
| **CAND-005** | `auth_middleware.py` | ⚠️ verify | needs gateway dir check |
| **CAND-006** | `langgraph_auth.py` | ❌ blocked | upstream auth module |

**CAND-022 (langgraph.json)** — local version is already correct adaptation, no action needed.

---

## 9. Carryover Blockers (8 preserved)

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

## R241_21B_SAFE_CONFIG_CHANGE_BATCH2_DONE

```
status=blocked_by_upstream_auth_reference
decision=cannot_apply_upstream_langgraph_json
cand022_safe_to_apply=false
reason=upstream auth.path references non-existent local file
upstream_auth_path=./app/gateway/langgraph_auth.py:auth
local_auth_dir_exists=false
local_langgraph_json=already adapted (auth removed)
checkpointer_path_adaptation=safe (agents vs runtime)
runtime_activation_risk=none
blocker_impact=none
pyproject_modified=false
dependency_installed=false
blockers_preserved=true
safety_violations=[]
recommended_resume_point=R241-21B
next_cand_candidates=[CAND-001,CAND-005]
```
