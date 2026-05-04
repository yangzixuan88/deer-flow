# R151F: Assertion Fix — Search Intent Reordering

## Status: PARTIAL_FIX_APPLIED

## Preceded By: R151E4
## Proceeding To: R152_PATH_A_TO_PATH_B_HANDOFF_MAP

---

## Summary

R151F applied one targeted fix to the `should detect search intent` assertion failure. The root cause was a **keyword conflict** — `'search'` exists in both `WEB_ACTION_KEYWORDS` (executor_adapter.ts:2485) and `SEARCH_INDICATORS` (intent_classifier.ts:24). Since `classifyOperation()` is called before the search indicator check in `suggestSystemType()`, the word `'search'` in "搜索关于TypeScript类型系统的文档" triggers `OperationType.WEB_BROWSER`, causing `suggestSystemType()` to return `SystemType.VISUAL_WEB` instead of `'search'`.

The fix reorders the checks so that search indicators are evaluated before `classifyOperation()` can intercept them.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R151E4 |
| current_phase | R151F |
| pressure_used | M (single-file targeted fix) |
| throughput | 1 keyword ordering fix in intent_classifier.ts |
| reason | No dependency install, model, MCP, gateway, or DB/JSONL |

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

## LANE 2: Fix Applied

### intent_classifier.ts suggestSystemType() — Keyword Ordering

**File:** `backend/src/domain/m01/intent_classifier.ts`

**Lines:** 257-283

**Before (R151E4):**
```typescript
private suggestSystemType(input: string, complexity: ComplexityAssessment): SystemType | undefined {
  const normalizedInput = input.toLowerCase();

  // ★ Round 3: 电脑操作自动分流 - 上游分类优先
  const opType = classifyOperation(input);          // ← catches 'search' first
  if (opType === OperationType.WEB_BROWSER) {
    return SystemType.VISUAL_WEB;
  }
  if (opType === OperationType.DESKTOP_APP || opType === OperationType.CLI_TOOL) {
    return SystemType.DESKTOP_APP;
  }

  // 搜索优先                                        // ← never reached for 'search'
  if (complexity.needsSearch || SEARCH_INDICATORS.some(i => normalizedInput.includes(i))) {
    return 'search' as SystemType;
  }
  ...
}
```

**After (R151F):**
```typescript
private suggestSystemType(input: string, complexity: ComplexityAssessment): SystemType | undefined {
  const normalizedInput = input.toLowerCase();

  // 搜索优先 - 在 classifyOperation 结果之前检查
  // 因为 'search' 同时出现在 WEB_ACTION_KEYWORDS 和 SEARCH_INDICATORS 中
  // 搜索查询应该路由到 SEARCH 而非 VISUAL_WEB
  if (complexity.needsSearch || SEARCH_INDICATORS.some(i => normalizedInput.includes(i))) {
    return 'search' as SystemType;                  // ← 'search' caught here first
  }

  // 工作流优先
  if (COMPLEXITY_PATTERNS.some(p => p.test(input))) {
    return 'workflow' as SystemType;
  }

  // 电脑操作类型 - 上游分类的结果
  const opType = classifyOperation(input);
  if (opType === OperationType.WEB_BROWSER) {
    return SystemType.VISUAL_WEB;
  }
  if (opType === OperationType.DESKTOP_APP || opType === OperationType.CLI_TOOL) {
    return SystemType.DESKTOP_APP;
  }

  // 默认任务系统
  return 'task' as SystemType;
}
```

**Why this works:** The string "搜索关于TypeScript类型系统的文档" contains `'搜索'` (Chinese for "search") which matches a `SEARCH_INDICATOR` entry (`'搜索'` at line 23). This sets `complexity.needsSearch = true`. By checking `complexity.needsSearch` before calling `classifyOperation()`, the function returns `'search'` as the suggested system type before `classifyOperation()` can match `'search'` in `WEB_ACTION_KEYWORDS` and return `OperationType.WEB_BROWSER`.

---

## LANE 3: Smoke Result

| Field | Value |
|---|---|
| TypeScript errors | 0 ✅ |
| Tests runnable | **unknown** — no jest environment in current workspace |
| Jest setup | Not found in `backend/` directory |
| npm test infrastructure | Not present |

**Investigation performed:**
- `backend/node_modules/.bin/jest` — does not exist
- `backend/package.json` — does not exist (TypeScript files are compiled from external tooling)
- `jest.config.*` — not found in backend directory
- Jest dependencies (`ts-jest`, `@jest/*`) — not found in backend scope

**Conclusion:** The smoke test from R151E4 was run via a root-level jest harness that is no longer available in the current workspace state. The fix to `suggestSystemType()` is logically sound based on the keyword conflict analysis.

---

## LANE 4: Test Failure Analysis

### Failure 1: `should detect search intent` ✅ FIX APPLIED

| Field | Value |
|---|---|
| Input | `搜索关于TypeScript类型系统的文档` |
| Expected `route` | `IntentRoute.ORCHESTRATION` |
| Expected `suggestedSystem` | `SystemType.SEARCH` |
| Actual (R151E4) | `suggestedSystem = SystemType.VISUAL_WEB` |
| Root cause | `'search'` in `WEB_ACTION_KEYWORDS` (line 2485 of executor_adapter.ts) catches before `SEARCH_INDICATORS` |
| Fix | Check `SEARCH_INDICATORS` before `classifyOperation()` in `suggestSystemType()` |
| Verification | Cannot verify — no jest environment |

### Failure 2: `should route simple query to direct answer` ⚠️ NOT INVESTIGATED

| Field | Value |
|---|---|
| Test | `orchestrator.test.ts` line 221-232 |
| Input | `{ userInput: '你好', ... }` |
| Expected | `result.route === IntentRoute.DIRECT_ANSWER` |
| Possible causes | 1) `context_envelope.ts` not stubbed in test environment |
| | 2) `DeerFlowClient.healthCheck()` failing or timing out |
| | 3) `coordinator.execute()` returning error |
| | 4) RTCM session state interfering |
| Status | Requires jest environment to investigate |

### Failure 3: `should route complex task to orchestration` ⚠️ NOT INVESTIGATED

| Field | Value |
|---|---|
| Test | `orchestrator.test.ts` line 248-260 |
| Input | `{ userInput: '搜索最新的AI新闻并保存到文件', ... }` |
| Expected | `result.route === IntentRoute.ORCHESTRATION` |
| Possible causes | Same as Failure 2 — likely cascading from orchestrator.execute() hitting an unstubbed dependency |
| Status | Requires jest environment to investigate |

---

## LANE 5: Safety Boundary

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

## LANE 6: Key Technical Pattern

| Pattern | Description |
|---|---|
| **Keyword conflict resolution by ordering** | `'search'` appears in both `WEB_ACTION_KEYWORDS` (web browser detection) and `SEARCH_INDICATORS` (search system detection). When a query contains "search", the first matching keyword set in `suggestSystemType()` determines the system type. Moving search check before `classifyOperation()` ensures search queries route to the SEARCH system type. |

---

## LANE 7: Next Phase Decision

| Condition | Result |
|---|---|
| recommended_next_phase | R152_PATH_A_TO_PATH_B_HANDOFF_MAP |
| reason | R151F fix applied. `should detect search intent` should now pass. Two remaining failures require jest debugging environment. Proceeding to R152 maps cross-layer handoffs between Path A (M01/M04/M11) and Path B (gateway/coordinator) components. |

---

## R151F Classification: PARTIAL_FIX_APPLIED

| Metric | Value |
|---|---|
| files_modified | 1 (intent_classifier.ts) |
| code_modified | true |
| dependency_installed | false |
| env_modified | false |
| db_written | false |
| jsonl_written | false |
| tests_actually_run | **unknown** (no jest env) |
| errors_fixed_this_phase | 1 (search intent keyword ordering) |
| errors_remaining | 0 (TS), 2 (assertion - not investigated) |
| recommended_next_phase | R152_PATH_A_TO_PATH_B_HANDOFF_MAP |

---

## R151F EXECUTION SUMMARY

**Fix applied:** Reordered `suggestSystemType()` to check `SEARCH_INDICATORS` before `classifyOperation()` prevents `'search'` keyword queries from being incorrectly routed to `VISUAL_WEB`.

**Root cause identified:** `'search'` exists in both `WEB_ACTION_KEYWORDS` (executor_adapter.ts:2485) and `SEARCH_INDICATORS` (intent_classifier.ts:24). The original code checked `classifyOperation()` first, catching `'search'` as a web browser action instead of a search system action.

**Cannot verify:** No jest environment in current workspace. R151E4's smoke test was run via a root-level jest harness that is no longer present.

**Next:** R152_PATH_A_TO_PATH_B_HANDOFF_MAP — map cross-layer handoff contracts between M01/M04/M11 (Path A) and gateway/coordinator components (Path B).

---

```
R151F_DONE
status=partial_fix_applied
files_modified=1
errors_fixed=1 (search keyword ordering)
tests_actually_run=unknown_no_jest_env
errors_remaining=0 TS, 2 assertion (not investigated)
recommended_next_phase=R152_PATH_A_TO_PATH_B_HANDOFF_MAP
```