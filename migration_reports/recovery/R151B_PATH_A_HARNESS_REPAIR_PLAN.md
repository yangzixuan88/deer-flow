# R151B: Path A Harness Repair Plan

## Status: PASSED

## Preceded By: R151
## Proceeding To: R151C_PATH_A_TEMP_HARNESS_SMOKE

## Pressure: M

---

## Summary

R151B diagnoses the root cause of R151's PARTIAL status (smoke blocked by missing test infrastructure in backend/) and finds that the issue is a **configuration mismatch**, not a missing dependency. Root repo has `jest.config.cjs` + `node_modules/` + working jest binary — the problem is root `package.json` incorrectly `cd`s to `backend/` before running jest, while the actual jest infrastructure lives at repo root. R151B authorizes R151C to run M01 orchestrator smoke from repo root using direct jest invocation, no dependency install required.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R151 |
| current_phase | R151B |
| recommended_pressure | M |
| reason | R151 completed PARTIAL due to infrastructure block; R151B is harness diagnosis with no dependency install allowed; static analysis only |

---

## LANE 1: Workspace / Baseline Guard

| Check | Result |
|---|---|
| workspace_dirty | true |
| dirty_files_count | many untracked (report artifacts + new modules) |
| f480fec1 (R140 inline fix) | **true** |
| bc3b0670 (R142C result persistence) | **true** |
| da4b7565 (R147K Tavily stdio) | **true** |
| unexpected_production_dirty_files | `[]` |
| safe_to_continue | **true** |
| r151_reports_present | **true** |

---

## LANE 2: Root TS Project Layout

| Component | Path | Status |
|---|---|---|
| jest.config.cjs | `jest.config.cjs` | ✅ **present** at repo root |
| vitest.config.ts | `vitest.config.ts` | ✅ **present** at repo root |
| package.json | `package.json` | ✅ **present** at repo root |
| node_modules/ | `node_modules/` | ✅ **present** at repo root |
| jest binary | `node_modules/.bin/jest` | ✅ **present** |
| ts-jest | `node_modules/ts-jest` | ✅ **present** |
| tsconfig.json | `tsconfig.json` | ✅ **present** |

**jest.config.cjs key settings:**
- `preset: 'ts-jest/presets/default-esm'` — ESM transform
- `testMatch: ['**/*.test.ts', '**/*.spec.ts']` — covers `backend/src/domain/m01/` and `backend/src/domain/m04/`
- `testPathIgnorePatterns: ['/node_modules/', '/frontend/', '/src/m11/']` — m11 excluded (old duplicate code)
- `testTimeout: 60000`

**Root package.json scripts (problematic):**
```json
"test": "cd backend && jest --runInBand",
"test:m04": "cd backend && NODE_OPTIONS='--experimental-vm-modules' jest src/domain/m04",
"test:m11": "cd backend && NODE_OPTIONS='--experimental-vm-modules' jest src/domain/m11"
```

**Critical finding:** Root has BOTH jest.config.cjs AND node_modules/ with jest binary. Root package.json scripts incorrectly `cd backend && jest` but the jest binary and config are at repo root, NOT in backend/. Tests can be run from repo root without any dependency install.

---

## LANE 3: Backend Project Layout

| Component | Path | Status |
|---|---|---|
| package.json | `backend/package.json` | ❌ **not found** |
| jest.config.ts | `backend/jest.config.ts` | ❌ **not found** |
| node_modules/ | `backend/node_modules/` | ❌ **not found** |
| tsconfig.json | `backend/tsconfig.json` | ✅ present |
| m01 source | `backend/src/domain/m01/` | ✅ present (orchestrator.ts + orchestrator.test.ts) |
| m04 source | `backend/src/domain/m04/` | ✅ present (coordinator.ts + 4 test files) |
| m11 source | `backend/src/domain/m11/` | ✅ present (executor_adapter.ts + 3 test files) |

**Note:** backend/ lacks all test infrastructure (package.json, jest.config.ts, node_modules) but contains the actual TypeScript source files and tests. R151's LANE 3 correctly identified this gap — but the fix is not to install dependencies in backend/, it's to run jest from repo root.

---

## LANE 4: Dependency-Free Execution Paths

| Check | Result |
|---|---|
| jest binary in root node_modules | ✅ `node_modules/.bin/jest` |
| root jest.config.cjs covers m01/m04 tests | ✅ `testMatch: ['**/*.test.ts']` finds `backend/src/domain/m01/orchestrator.test.ts` |
| test files use jest globals | ✅ `describe/it/beforeEach/expect` confirmed in orchestrator.test.ts |
| npx --no-install works | ✅ can query binary versions without auto-install |
| no network required | ✅ true — existing node_modules used |
| no new install needed | ✅ true |

**Path A test files confirmed to use jest globals:**
- `orchestrator.test.ts` — `describe/it/beforeEach/expect` from `@jest/globals`
- `coordinator.test.ts` — jest globals confirmed
- `executor_adapter.test.ts` — jest globals confirmed

**Alternative runners checked:**
| Runner | Available | Verdict |
|---|---|---|
| jest (root) | ✅ yes | **Recommended** — test files use jest globals |
| vitest | ✅ yes | Available but test files use jest not vitest globals; not recommended |
| ts-node / tsx | ❌ not found | Not in root node_modules |
| esbuild-register | ❌ not found | Not in root node_modules |

---

## LANE 5: Harness Strategy Comparison

| Option | Strategy | Feasibility | Recommended |
|---|---|---|---|
| **A: Root jest direct** | Run `node_modules/.bin/jest backend/src/domain/m01/orchestrator.test.ts --config jest.config.cjs` | **HIGH** | ✅ **Yes** |
| B: Fix package.json | Edit root `package.json` scripts to remove `cd backend &&` | Medium | ❌ No (not needed) |
| C: vitest alternative | Run via vitest instead of jest | Low | ❌ No (incompatible globals) |

**Option A pros:**
- No dependency install needed (root node_modules already present)
- No code modification required
- Uses existing ts-jest ESM transform
- Test files already use jest globals compatible with ts-jest
- M01/M04 test files discoverable via `testMatch: ['**/*.test.ts']`

**Option A cons:**
- m11 tests excluded by testPathIgnorePatterns (not an issue for R151C target)

---

## LANE 6: R151C Authorization Package

| Field | Value |
|---|---|
| phase_name | `R151C_PATH_A_TEMP_HARNESS_SMOKE` |
| purpose | Run M01 orchestrator test from repo root using existing root jest infrastructure |
| pressure | M |
| execution_risk | M |
| entrypoint | `backend/src/domain/m01/orchestrator.test.ts` |
| execution_command | `node_modules/.bin/jest backend/src/domain/m01/orchestrator.test.ts --config jest.config.cjs --no-coverage` |
| alternative_command | `npx --no-install jest backend/src/domain/m01/orchestrator.test.ts --config jest.config.cjs --no-coverage` |
| env_setup | `NODE_OPTIONS='--experimental-vm-modules'` may be needed for ESM ts-jest |
| forbidden | POST /runs, MiniMax API, MCP runtime, gateway startup, DB/JSONL writes |

**R151C success criteria:**
- jest binary found and config loaded without error
- ts-jest transform handles ESM TypeScript without error
- `orchestrator.test.ts` runs (pass or fail is acceptable — infrastructure vs. test issue distinction)
- Test exercises `deerflowEnabled=false` local orchestration path
- No external calls (python gateway, MiniMax API, MCP servers)
- `python_gateway_called: false` confirmed in smoke audit

**Mocked components in smoke:** M04Coordinator, M11ExecutorAdapter, DeerFlowClient, executorReadinessGate

**If blocked:** Fall back to vitest investigation or report specific error.

---

## LANE 7: R152 Preliminary Authorization

| Field | Value |
|---|---|
| phase_name | `R152_PATH_A_TO_PATH_B_HANDOFF_MAP` |
| purpose | Validate M01→DeerFlowClient→Python gateway handoff; healthCheck + createThread probe |
| pressure | M |
| depends_on | R151C smoke passes (TS infrastructure confirmed functional) |
| deferred | Until R151C confirms jest works |

---

## LANE 8: Unknown Registry

| Unknown | Detail | Blocks R151C |
|---|---|---|
| backend/src/domain/m11/ testPathIgnorePatterns exclusion | Root jest.config.cjs excludes m11 tests (`'/src/m11/'` ignore pattern); m11 tests (executor_adapter.test.ts, sandbox.test.ts) not discoverable via root jest without removing this pattern | ❌ No (R151C targets M01/M04 only) |

---

## LANE 9: Report Generation

| Field | Value |
|---|---|
| reports_written | **true** |
| md_report | `R151B_PATH_A_HARNESS_REPAIR_PLAN.md` |
| json_report | `R151B_PATH_A_HARNESS_REPAIR_PLAN.json` |

---

## R151B Classification: PASSED

| Metric | Value |
|---|---|
| code_modified | false |
| dependency_installed | false |
| env_modified | false |
| patch_applied | false |
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

## R151B EXECUTION SUCCESS

**Key findings:**

1. **Root has complete test infrastructure** — `jest.config.cjs`, `node_modules/`, jest binary all present at repo root
2. **Backend lacks infrastructure** — no package.json, no jest.config.ts, no node_modules in backend/
3. **Root package.json misconfiguration** — `cd backend && jest` is wrong; jest binary and config are at repo root, not backend/
4. **No dependency install needed** — R151C can run immediately using `node_modules/.bin/jest backend/src/domain/m01/orchestrator.test.ts --config jest.config.cjs`
5. **M11 excluded from jest** — `testPathIgnorePatterns: ['/src/m11/']` excludes m11 tests (intentional, old duplicate code)

**R151C authorized:** Run M01 orchestrator smoke via root jest, no dependency install, no code modification.

---

```
R151B_PATH_A_HARNESS_REPAIR_PLAN_DONE
status=passed
recommended_next_phase=R151C_PATH_A_TEMP_HARNESS_SMOKE
```

`★ Insight ─────────────────────────────────────`
**测试基础设施位置陷阱**：Root `package.json` 定义 `test: cd backend && jest` 是错误的——jest 基础设施（binary、config、node_modules）都在 repo 根目录，不在 backend/。正确的做法是直接从 repo 根目录运行 `node_modules/.bin/jest`，无需任何依赖安装，也无需修改任何代码。
`─────────────────────────────────────────────────`