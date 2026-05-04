# R151E: Path A Jest ESM Config Fix

## Status: PARTIAL_WITH_NEW_TS_BLOCKERS

## Preceded By: R151D
## Proceeding To: R151E2_JEST_ESM_DEEP_FIX

## Pressure: H

---

## Summary

R151E's primary goal was to fix TS1343 (`import.meta.url` not allowed with current ts-jest module config) in `runtime_paths.ts:4`. **TS1343 was resolved** by running jest with `NODE_OPTIONS='--experimental-vm-modules'`. However, this revealed **6 pre-existing type errors in `coordinator.ts`** that were previously masked by TS1343. The smoke still cannot execute tests, but the blocker changed from an infrastructure issue to pre-existing business code type errors.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R151D |
| current_phase | R151E |
| pressure_used | H |
| reason | Config-only fix; no dependency install, model, MCP, gateway, or DB/JSONL |

---

## LANE 1: Workspace Guard

| Check | Result |
|---|---|
| workspace_dirty | true |
| m01_m04_m11_untracked_preserved | ✅ true |
| no_git_clean_performed | ✅ true |
| no_git_reset_performed | ✅ true |
| safe_to_continue | **true** |

---

## LANE 2: Config Fixes Applied

### tsconfig.jest.json (created)

```json
{
  "compilerOptions": {
    "module": "ES2022",
    "target": "ESNext",
    "moduleResolution": "node",
    "lib": ["ES2022"],
    "isolatedModules": true,
    "standalone": true
  },
  "include": ["backend/src/**/*"]
}
```

Key design decisions:
- **Standalone** (no `extends`) — avoids inheriting problematic settings from root `tsconfig.json`
- **module: 'ES2022'** — explicitly covers `import.meta.url` per TypeScript module options
- **isolatedModules: true** — per ts-jest recommendation for ESM
- **No `types` exclusion** — allows jest/node types to resolve properly

### jest.config.cjs (modified transform)

```javascript
// Before:
transform: {
  '^.+\\.tsx?$': ['ts-jest', { useESM: true, tsconfig: { module: 'ESNext', ... } }],
}

// After:
transform: {
  '^.+\\.tsx?$': ['ts-jest', { useESM: true, tsconfig: 'tsconfig.jest.json' }],
},
```

---

## LANE 3: Targeted Smoke Results

| Attempt | Command | TS1343 | TS2345 | Tests Run | Exit Code |
|---|---|---|---|---|---|
| 1 | `jest ... --config jest.config.cjs` | **Failed** | — | false | 1 |
| 2 | Same + `isolatedModules: true` | SyntaxError | — | false | 1 |
| 3 | Same + `NODE_OPTIONS='--experimental-vm-modules'` | **Fixed** ✅ | Not regressed | false | 1 |

**Attempt 3 errors (new blockers in coordinator.ts):**
```
TS2304: Cannot find name 'classifyOperation' (coordinator.ts:443, 872)
TS2551: Property 'claude_code' does not exist on type 'typeof ExecutorType' (coordinator.ts:508, 929, 934, 941)
TS18048: 'node.operator_context' is possibly 'undefined' (coordinator.ts:911, 913, 978, 986)
```

---

## LANE 4: Error Classification

| Error | Status | Type |
|---|---|---|
| TS1343 (runtime_paths.ts:4) | **FIXED** ✅ | Infrastructure |
| TS2345 (orchestrator.ts:405) | **NOT REGRESSED** ✅ | Business code (already fixed in R151D) |
| TS2304 in coordinator.ts:443 | **NEW BLOCKER** ❌ | Pre-existing business code error |
| TS2551 in coordinator.ts:508 etc. | **NEW BLOCKER** ❌ | Pre-existing business code error |
| TS18048 in coordinator.ts:911 etc. | **NEW BLOCKER** ❌ | Pre-existing business code error |

**Key discovery:** When `NODE_OPTIONS='--experimental-vm-modules'` is set, ts-jest's diagnostics engine properly resolves `import.meta.url` type — TS1343 disappears. The coordinator.ts errors existed before but were masked behind TS1343.

---

## LANE 5: Key Insight — How TS1343 Was Fixed

```
Without NODE_OPTIONS:  ts-jest diagnostics engine → TS1343 at runtime_paths.ts:4 → STOP
With NODE_OPTIONS:      ts-jest diagnostics engine → properly resolves import.meta.url → proceeds to coordinator.ts → finds pre-existing errors
```

The `NODE_OPTIONS='--experimental-vm-modules'` flag is needed because `import.meta.url` is an ESM feature. Without it, Node.js treats `import.meta` as invalid at the type-checking phase even when tsconfig has the correct `module` setting.

---

## LANE 6: Safety / Boundary Verification

| Field | Value |
|---|---|
| dependency_installed | **false** ✅ |
| gateway_started | **false** ✅ |
| model_api_called | **false** ✅ |
| mcp_runtime_called | **false** ✅ |
| db_written | **false** ✅ |
| jsonl_written | **false** ✅ |
| push_executed | **false** ✅ |
| merge_executed | **false** ✅ |
| safety_violations | `[]` ✅ |
| m01_m04_m11_untracked_preserved | **true** ✅ |

---

## LANE 7: Next Phase Decision

| Condition | Result |
|---|---|
| recommended_next_phase | `R151E2_JEST_ESM_DEEP_FIX` |
| reason | TS1343 infrastructure fixed; coordinator.ts has 6+ pre-existing type errors that must be fixed before tests can execute |

---

## LANE 8: Unknown Registry

| Unknown | Detail |
|---|---|
| coordinator.ts 6+ type errors | `classifyOperation` missing, `ExecutorType.claude_code` vs `CLAUDE_CODE`, possibly-undefined operator_context — all pre-existing in untracked coordinator.ts |
| NODE_OPTIONS needed for ESM | The `--experimental-vm-modules` flag must be passed inline to jest; not set persistently |

---

## LANE 9: Report Generation

| Field | Value |
|---|---|
| reports_written | **true** |
| md_report | `R151E_PATH_A_JEST_ESM_CONFIG_FIX.md` |
| json_report | `R151E_PATH_A_JEST_ESM_CONFIG_FIX.json` |

---

## R151E Classification: PARTIAL_WITH_NEW_TS_BLOCKERS

| Metric | Value |
|---|---|
| files_modified | `jest.config.cjs`, `tsconfig.jest.json` |
| code_modified | false |
| dependency_installed | false |
| env_modified | true (NODE_OPTIONS passed inline) |
| db_written | false |
| jsonl_written | false |
| gateway_started | false |
| model_api_called | false |
| mcp_runtime_called | false |
| external_tool_called | false |
| push_executed | false |
| merge_executed | false |
| safety_violations | [] |
| blockers_preserved | true |

---

## R151E EXECUTION SUMMARY

**TS1343 fix: SUCCESS** — `import.meta.url` now type-checks correctly when jest runs with `NODE_OPTIONS='--experimental-vm-modules'`

**New discovery: coordinator.ts type errors** — 6+ pre-existing type errors in untracked `coordinator.ts` (TS2304 `classifyOperation` not found, TS2551 case sensitivity on enum members, TS18048 possibly-undefined properties)

**Progress:** Path A smoke has moved from infrastructure block (TS1343) to business code block (coordinator.ts type errors). Tests still cannot run, but the nature of the blocker is now code quality, not infrastructure.

**Next:** R151E2 must fix coordinator.ts type errors.

---

```
R151E_PATH_A_JEST_ESM_CONFIG_FIX_DONE
status=partial_with_new_ts_blockers
ts1343_fixed=true
ts2345_regression=false
tests_actually_run=false
recommended_next_phase=R151E2_JEST_ESM_DEEP_FIX
```

`★ Insight ─────────────────────────────────────`
**NODE_OPTIONS ESM flag 对 ts-jest 诊断的影响**：在没有 `--experimental-vm-modules` 的情况下，ts-jest 的类型诊断引擎无法正确解析 `import.meta.url` 的类型，即使 `tsconfig.module` 设置正确也会报 TS1343。这个 flag 使得 Node.js 在类型检查阶段正确识别 ESM 上下文，从而使 `import.meta.url` 的类型通过验证。这个问题不是 ts-jest 配置错误，而是 Node.js ESM 类型解析的环境要求。
`─────────────────────────────────────────────────`