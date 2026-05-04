# R147D: Lark MCP Token Infrastructure Diagnostic and Repair Plan

## Status: PASSED

## Preceded By: R147C
## Proceeding To: R147E_LARK_TENANT_TOKEN_SMOKE

## Pressure: XXL

---

## Summary

R147D performed a deep diagnostic of the Lark MCP token infrastructure after R147C's `lark_im_v1_chat_list` smoke call returned error `99991661 "Missing access token for authorization"`.

R147D's key finding: **The Lark SDK's token acquisition chain is broken at two levels:**
1. `keytar.node` missing → `AuthStore` cannot persist tokens to disk → tokens lost on process restart
2. Lark MCP in `tokenMode='auto'` (default) uses OAuth user token path → SDK tried to call Lark API without any access token attached

R147D's recommended fix: **Switch to `tenant_access_token` mode** — this bypasses keytar dependency entirely because the SDK fetches a tenant-level token per-request using appId+appSecret via HTTP.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R147C |
| current_phase | R147D |
| recommended_pressure | XXL |
| reason | Lark runtime loads tools but API call fails with missing access token (99991661); token infrastructure broken — diagnose before retry |

---

## LANE 1: R147C Failure Evidence

| Field | Value |
|---|---|
| tool_smoke_attempted | true |
| tool_name | lark_im_v1_chat_list |
| error_code | **99991661** |
| error_message | **"Missing access token for authorization"** |
| lark_runtime_started | true |
| tools_listed | true |
| tool_count | 19 |
| tool_call_failed_before_business_logic | true |
| blocker_class | missing_access_token |
| blocker_location | token_acquisition / token_storage / token_injection |

---

## LANE 2: Token Requirement Mapping

### Lark MCP Token Modes

The Lark MCP CLI (`pnpm dlx @larksuiteoapi/lark-mcp mcp`) supports three token modes:

| Mode | CLI Flag | Token Source | OAuth Needed |
|---|---|---|---|
| `auto` (default) | default | `LarkAuthHandlerLocal.getLocalAccessToken(appId)` | No (but falls back to nothing) |
| `user_access_token` | `--token-mode user_access_token` | Explicit user token via env or OAuth | Only if env not set |
| `tenant_access_token` | `--token-mode tenant_access_token` | SDK fetches via `/open-apis/auth/v3/tenant_access_token/internal` | No |

### Token Acquisition Paths

**Path 1 — `auto` mode (current, broken):**
1. `LarkAuthHandlerLocal.getLocalAccessToken(appId)` reads from `AuthStore`
2. `AuthStore` uses `StorageManager` to load/save encrypted tokens to disk
3. `StorageManager.encrypt()` requires `keytar.node` → fails silently → `isInitializedStorageSuccess=false`
4. `saveStorageData()` returns early without writing → token never persisted
5. Memory store holds token only within stdio process lifetime
6. Process exits → token lost → next call has no token → API error `99991661`

**Path 2 — `tenant_access_token` mode (proposed fix):**
1. SDK's `Client` uses `appId + appSecret` directly
2. Fetches `tenant_access_token` from `/open-apis/auth/v3/tenant_access_token/internal`
3. No `keytar` dependency, no disk storage, no OAuth
4. Token cached in-memory for session lifetime (but re-fetched per-request if needed)

### Answers to Key Questions

| Question | Answer |
|---|---|
| Does `LARK_APP_ID` + `LARK_APP_SECRET` suffice? | **Yes** for `tenant_access_token` mode — SDK fetches tenant token directly |
| Is OAuth required? | **No** for `tenant_access_token` mode — no browser login needed |
| Does `keytar.node` block tenant token? | **No** — tenant token is fetched per-request via HTTP, no storage involved |
| What is `99991661`? | Lark API error: request sent without Authorization header |

---

## LANE 3: keytar Dependency Analysis

| Check | Result |
|---|---|
| `keytar.node` path | `pnpm-cache\...\keytar@7.9.0\build\Release\keytar.node` — **missing** |
| keytar required for persistent token | **Yes** |
| keytar required for tenant token | **No** |
| Missing binary blocks | OAuth user token persistence only |
| `StorageManager.encrypt()` fails | `isInitializedStorageSuccess = false` |
| `saveStorageData()` behavior | Returns early, data not written to disk |
| `loadStorageData()` when uninitialized | Returns `{}` (empty tokens/clients) |
| Memory store scope | Single stdio process lifetime |
| Token lost on process restart | **Yes** |
| Risk | **HIGH** for OAuth; **NONE** for tenant token mode |

---

## LANE 4: stdio Process Lifecycle

| Check | Result |
|---|---|
| Process reused between R147A list and R147C call? | **No** — each `get_cached_mcp_tools()` starts a fresh stdio process |
| Memory store persistence scope | Single process only |
| Token lost between calls | **Yes** |
| AuthStore tokens lost on restart | **Yes** |
| Explains `99991661`? | **Partially** — OAuth token lost; but SDK in `auto` mode should use tenant token which doesn't need storage |

---

## LANE 5: Credential Presence

| Credential | Status |
|---|---|
| LARK_APP_ID | **PRESENT** |
| LARK_APP_SECRET | **PRESENT** |
| FEISHU_APP_ID | **PRESENT** |
| FEISHU_APP_SECRET | **PRESENT** |
| LARK_ACCESS_TOKEN | MISSING |
| LARK_TENANT_ACCESS_TOKEN | MISSING |
| LARK_USER_ACCESS_TOKEN | MISSING |
| Secret values printed | **false** |

---

## LANE 6: Repair Options

### Option A — Fix keytar native dependency
- **Changes**: None (just rebuild/reinstall)
- **Dependencies**: YES — keytar native rebuild required
- **Env**: None
- **User action**: Maybe (npm rebuild)
- **Risk**: Medium
- **Recommended**: ❌ Not lowest-risk path

### Option B — Provide explicit user_access_token via env
- **Changes**: `extensions_config.json` env field
- **Dependencies**: None
- **Env**: Add `USER_ACCESS_TOKEN` to lark env
- **User action**: YES — must obtain token via `lark-mcp login` (needs keytar working)
- **Risk**: HIGH — long-lived secret as env var
- **Recommended**: ❌ Security risk; blocked by keytar anyway

### Option C — Switch to `tenant_access_token` mode ✅
- **Changes**: `extensions_config.json` env field
- **Dependencies**: None
- **Env**: Add `LARK_TOKEN_MODE=tenant_access_token`
- **User action**: None
- **Risk**: Medium — some tools need user-level context (tenant token covers `lark_im_v1_chat_list`)
- **Recommended**: ✅ **Lowest-risk path — no new deps, no secrets, no user action**

### Option D — Enable `--oauth` with interactive login
- **Changes**: Add `--oauth` to lark args
- **Dependencies**: None
- **User action**: YES — interactive browser login + keytar must work for persistence
- **Risk**: HIGH — interactive flow blocks automation; keytar still broken
- **Recommended**: ❌ Keytar must be fixed first; not automatable

### Option E — Keep Lark MCP disabled
- **Risk**: Low (deferred)
- **Recommended**: ❌ Option C is worth trying first

---

## LANE 7: Recommended Strategy

**Option C — Switch to `tenant_access_token` mode**

**Why this works:**
- SDK's `Client` fetches `tenant_access_token` via `POST /open-apis/auth/v3/tenant_access_token/internal` using `appId + appSecret`
- This HTTP endpoint does NOT use `keytar`, does NOT use OAuth, does NOT require disk storage
- The SDK fetches the token on each API call (or caches in memory for the session)
- Works regardless of `keytar.node` missing

**Why this is safe for `lark_im_v1_chat_list`:**
- Bot group membership (`lark_im_v1_chat_list`) only requires app-level bot permissions
- `tenant_access_token` provides exactly this access
- `tenant_access_token` does NOT need user OAuth — bot's app identity is sufficient

**Why other tools may differ:**
- Some tools that read user-scoped data (messages, docs owned by user) may need `user_access_token`
- The `tokenMode` affects per-tool behavior via `shouldUseUAT` parameter
- Smoke test with `lark_im_v1_chat_list` (bot membership read) is a good proxy

---

## LANE 8: R147E Authorization Package

```
recommended_phase: R147E_LARK_TENANT_TOKEN_SMOKE

patch_required: YES
  file: backend/extensions_config.json
  change: Add "env": {"LARK_TOKEN_MODE": "tenant_access_token"} to lark entry

dependency_install_required: false
env_update_required: false (patch covers it)
user_action_required: false

files_allowed:
  - backend/extensions_config.json (patch)
  - backend/run_r147e.py (temp harness)

files_forbidden:
  - .env
  - backend/packages/*
  - package.json / lockfiles

selected_tool: lark_im_v1_chat_list
allowed_tool_calls: 1
model_call_allowed: false
write_tool_allowed: false
params: {}

validation_plan:
  1. Patch extensions_config.json: add env.LARK_TOKEN_MODE=tenant_access_token
  2. Reset MCP tools cache (reset_mcp_tools_cache)
  3. Load lark_im_v1_chat_list via get_cached_mcp_tools()
  4. Invoke with empty params {}
  5. Expect: [] (bot not in any groups) or list of chat objects
  6. If error 99991661: tenant token also failed → R147F (keytar fix or Lark disable)
  7. If other error: inspect and classify
  8. Record: success/failure, error_code, response_shape, elapsed time

rollback_plan: Remove LARK_TOKEN_MODE from extensions_config.json env field
```

---

## LANE 9: MCP Branch Decision

| Decision | Value |
|---|---|
| continue_lark_now | ✅ true |
| pause_lark_until_token_fixed | false |
| switch_to_tavily_investigation | false |
| return_to_non_mcp_mainline | false |

**Rationale:** R147D identified Option C (a single env var change) as the lowest-risk fix. R147E should attempt this before concluding Lark is blocked. Only if R147E fails should Lark be paused.

---

## LANE 10: Unknown Registry Updates

| ID | Description | Fix Applied |
|---|---|---|
| U-lark-access-token-missing | R147C smoke failed with 99991661 — SDK called API without token | R147D: SDK in auto mode tried user token path; tenant mode bypasses this |
| U-lark-keytar-warning-upgraded | R147A "keytar warning" is actually HIGH blocker for OAuth persistence | R147D: keytar breaks OAuth storage; does NOT block tenant_access_token flow |
| U-lark-token-storage-chain | keytar fail → StorageManager no-op → tokens not persisted → lost on restart | R147D: traced full chain; tenant token mode avoids storage entirely |
| U-lark-oauth-requirement | OAuth requires keytar + browser login + redirect URI config — all broken | R147D: OAuth is NOT the only path; tenant mode requires only appId+appSecret |
| U-lark-stdio-process-token-lifecycle | stdio process restarts per call; memory store tokens lost | R147D: tenant token per-request fetch works with this lifecycle |
| U-lark-repair-path | R147D recommended Option C: LARK_TOKEN_MODE=tenant_access_token | R147D: repair path selected for R147E |
| U-lark-sdk-auto-mode-behavior | tokenMode='auto' uses user token path; does NOT auto-fallback to tenant token | R147D: explicit tokenMode=tenant_access_token required |

---

## R147D Classification: PASSED

| Metric | Value |
|---|---|
| code_modified | false |
| dependency_installed | false |
| env_modified | false |
| db_written | false |
| jsonl_written | false |
| gateway_started | false |
| model_api_called | false |
| mcp_runtime_called | false |
| external_tool_called | false |
| push_executed | false |
| merge_executed | false |
| safety_violations | [] |

---

## R147D EXECUTION SUCCESS
