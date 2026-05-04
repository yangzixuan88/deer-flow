# R153: Handoff Contract Patch — Test Infrastructure Recovery

## Status: COMPLETED

## Preceded By: R152
## Proceeding To: R154_SAFETY_AND_CONFIG_HYGIENE_PASS

---

## Summary

R153 applied targeted test infrastructure fixes to recover the orchestrator test suite. Two root causes were identified and fixed:

1. **`should detect search intent`** — `classify()` in `intent_classifier.ts` had an early-return path that called `classifyOperation()` BEFORE `suggestSystemType()`, causing search queries containing `'search'` to be caught by `WEB_ACTION_KEYWORDS` and routed to `VISUAL_WEB`. Fix: added a search-indicator fast-path before `classifyOperation()` in `classify()`.

2. **Orchestrator execute tests failing** — `orchestrator.ts` used `require('./context_envelope')` inside `execute()`, which throws `require is not defined` in Jest ESM mode (`--experimental-vm-modules`). Fix: converted to static ESM `import` at module scope.

3. **`ensureContextEnvelope` returning undefined** — Mock returned `undefined` from `jest.fn()` without a return value, causing `ctx.request_id = ...` to throw `TypeError: Cannot set properties of undefined`. Fix: `ensureContextEnvelope` mock now returns a proper object.

**Result: 25/25 tests passing.**

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R152 |
| current_phase | R153 |
| pressure_used | M (targeted fixes) |
| throughput | 2 mock patches + 1 ESM import fix |
| reason | No dependency install, model, MCP, gateway, or DB/JSONL |

---

## LANE 1: Workspace Guard

| Check | Result |
|---|---|
| workspace_dirty | true |
| m01_m04_m11_untracked_preserved | ✅ true |
| no_git_clean_performed | ✅ true |
| no_git_reset_performed | ✅ true |
| r151f_search_order_fix_present | ✅ true (in intent_classifier.ts) |
| safe_to_continue | **true** |

---

## LANE 2: Root Causes Found

### Root Cause 1: classify() search fast-path gap

**File:** `backend/src/domain/m01/intent_classifier.ts`

**Problem:** `classify()` at line 59 had a check at line 65 calling `classifyOperation(trimmedInput)`. If that returned `WEB_BROWSER`, it returned early with `suggestedSystem: SystemType.VISUAL_WEB` — never reaching `suggestSystemType()`. The R151F fix in `suggestSystemType()` was therefore unreachable for queries where `classifyOperation()` matched first.

**Fix:** Added a search-indicator fast-path BEFORE `classifyOperation()` in `classify()`:

```typescript
// 搜索拦截优先 — 在 classifyOperation 之前拦截搜索操作
// 因为 'search' 同时出现在 WEB_ACTION_KEYWORDS 和 SEARCH_INDICATORS 中
// 搜索查询应该路由到 SEARCH 而非 VISUAL_WEB (R151F fix)
if (complexity.needsSearch || SEARCH_INDICATORS.some(i => trimmedInput.toLowerCase().includes(i))) {
  return {
    route: IntentRoute.ORCHESTRATION,
    complexity,
    confidence: 0.85,
    suggestedSystem: 'search' as SystemType,
    reasoning: '搜索任务，需要DAG规划和搜索系统协同',
  };
}
```

### Root Cause 2: require() in ESM mode

**File:** `backend/src/domain/m01/orchestrator.ts`

**Problem:** `execute()` at line 69 used `const { ... } = require('./context_envelope')` inside the function body. In Jest's `--experimental-vm-modules` mode (ESM), `require` is undefined. This caused `require is not defined` at runtime.

**Fix:** Converted to static ESM `import` at module scope:

```typescript
// Before (line 69):
const { ensureContextEnvelope, injectEnvelopeIntoContext } = require('./context_envelope');

// After (line 17):
import { ensureContextEnvelope, injectEnvelopeIntoContext } from './context_envelope';
```

### Root Cause 3: Mock returning undefined

**File:** `backend/src/domain/m01/orchestrator.test.ts`

**Problem:** `ensureContextEnvelope: jest.fn()` returned `undefined`. Then `ctx.request_id = request.requestId` in orchestrator.ts threw `TypeError: Cannot set properties of undefined`. Caught by the try/catch, returned `{ success: false }`.

**Fix:**
```typescript
ensureContextEnvelope: jest.fn((req: any) => ({
  ...req,
  context_id: 'test-context-id',
  request_id: req.requestId,
  session_id: req.sessionId,
})),
```

---

## LANE 3: Test Doubles Applied

### context_envelope mock (R153-3)

```typescript
jest.mock('./context_envelope', () => ({
  ensureContextEnvelope: jest.fn((req: any) => ({
    ...req,
    context_id: 'test-context-id',
    request_id: req.requestId,
    session_id: req.sessionId,
  })),
  injectEnvelopeIntoContext: jest.fn(),
  generateContextId: jest.fn(() => 'test-context-id'),
  generateRequestId: jest.fn(() => 'test-request-id'),
  generateLinkId: jest.fn(() => 'test-link-id'),
  extractEnvelopeFromContext: jest.fn(),
}));
```

### DeerFlowClient mock (R153-4)

```typescript
class MockDeerFlowClient {
  healthCheck: () => Promise<boolean> = jest.fn<() => Promise<boolean>>().mockResolvedValue(true);
  createThread: () => Promise<{ thread_id: string }> = jest.fn<() => Promise<{ thread_id: string }>>().mockResolvedValue({ thread_id: 'test-thread-001' });
  executeUntilComplete: () => Promise<{...}> = jest.fn<() => Promise<{...}>>().mockResolvedValue({
    request_id: 'test-request-id',
    success: true,
    dag_plan: mockDagPlan,
    completed_nodes: 1,
    total_nodes: 2,
    duration: 1234,
  });
}

// Injected via constructor DI
beforeEach(() => {
  const mockClient = new MockDeerFlowClient();
  orchestrator = new Orchestrator(
    { deerflowEnabled: true },
    undefined,
    undefined,
    mockClient as any,
  );
});
```

---

## LANE 4: Smoke Result

```
NODE_OPTIONS='--experimental-vm-modules' node_modules/.bin/jest backend/src/domain/m01/orchestrator.test.ts --config jest.config.cjs --no-coverage

Test Suites: 1 passed, 1 total
Tests:       25 passed, 25 total
```

**All 25 tests passing** (previously 22 passed, 3 failed).

| Test | Before | After |
|---|---|---|
| M01 IntentClassifier (13 tests) | ✅ all pass | ✅ all pass |
| M01 DAGPlanner (9 tests) | ✅ all pass | ✅ all pass |
| M01 Orchestrator execute() | ❌ 3 FAIL | ✅ all pass |
| M01 Orchestrator getConfig() | ✅ pass | ✅ pass |

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

## LANE 6: Key Technical Patterns

| Pattern | Description |
|---|---|
| **ESM `require()` incompatibility** | Jest's `--experimental-vm-modules` runs TypeScript as true ESM where `require` is undefined. `jest.mock()` is hoisted at load time but `require()` inside function bodies executes at runtime — failing silently in the try/catch. Solution: static ESM `import` at module scope, which Jest intercepts correctly via `jest.mock()`. |
| **Search keyword conflict by ordering** | `'search'` appears in both `WEB_ACTION_KEYWORDS` and `SEARCH_INDICATORS`. `classifyOperation()` catches it first, returning `WEB_BROWSER`. Fast-path in `classify()` (before `classifyOperation()`) routes correctly. |
| **Mock return value correctness** | `jest.fn()` without return returns `undefined`. Code that sets properties on the mock result throws `TypeError`. Mock must return a proper object when the code under test reads/writes properties. |
| **Constructor DI for DeerFlowClient** | `Orchestrator` accepts optional `dfClient` parameter. In test, inject `new MockDeerFlowClient()` directly — bypasses the `require()` issue and gives precise control. |

---

## LANE 7: Files Modified

| File | Change |
|---|---|
| `backend/src/domain/m01/intent_classifier.ts` | Added search-indicator fast-path before `classifyOperation()` in `classify()` (R151F incomplete fix completed) |
| `backend/src/domain/m01/orchestrator.ts` | Converted `require('./context_envelope')` to static ESM `import` |
| `backend/src/domain/m01/orchestrator.test.ts` | Added context_envelope mock, DeerFlowClient mock class, DI in beforeEach |

---

## LANE 8: Next Phase Recommendation

| Recommended Phase | Rationale |
|---|---|
| `R154_SAFETY_AND_CONFIG_HYGIENE_PASS` | All 3 assertion failures are now resolved. Next: verify configuration hygiene, security settings, and environment isolation before final functional acceptance sweep (R155). |

---

## R153 Classification: COMPLETED

| Metric | Value |
|---|---|
| pressure_used | **M** |
| throughput | targeted_fixes |
| tests_passed_before | 22 |
| tests_passed_after | **25** |
| root_causes_fixed | 3 (search fast-path gap, require in ESM, mock return value) |
| contract_map_preserved | **true** (0 mismatches from R152) |
| recommended_next_phase | `R154_SAFETY_AND_CONFIG_HYGIENE_PASS` |

---

```
R153_DONE
status=completed
pressure_used=M
tests_passed=25/25
root_causes_fixed=3
contract_map_preserved=true
recommended_next_phase=R154_SAFETY_AND_CONFIG_HYGIENE_PASS
```
