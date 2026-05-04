# R147H: Lark Keytar OAuth Feasibility and Token Mode Reset

## Status: PASSED

## Preceded By: R147G
## Proceeding To: R147I_LARK_DISABLE_AND_TAVILY_405_DIAGNOSTIC

## Pressure: XXL

---

## Summary

R147H performed a feasibility diagnostic on the keytar rebuild and OAuth login route for the Lark MCP 99991661 issue. The analysis revealed that **keytar is irrelevant in tenant_access_token mode** — it only stores OAuth user tokens. To use the keytar route, the config must simultaneously: (1) switch to `user_access_token` mode, (2) add `--oauth` flag, (3) rebuild keytar, and (4) complete browser-based OAuth login. These are tightly coupled requirements that cannot be achieved independently. The recommended strategy is to **pause Lark MCP, enable Tavily MCP, and investigate the R131A Tavily 405 error**.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R147G |
| current_phase | R147H |
| recommended_pressure | XXL |
| reason | NO_PROXY failed; evaluate keytar/OAuth route; keytar only relevant after token-mode reset to user_access_token |

---

## LANE 1: Workspace / Config Guard

| Check | Result |
|---|---|
| workspace_dirty | true (many untracked files) |
| r147a_commit_present | true (24f61bc3) |
| extensions_config_dirty | true (R147G authorized patch) |
| safe_to_continue | true |
| authorized_modified_files | `backend/extensions_config.json` |

---

## LANE 2: Current Lark Config State

| Field | Value |
|---|---|
| lark_enabled | true |
| tavily_disabled | true |
| exa_disabled | true |
| token_mode_cli_arg | `--token-mode tenant_access_token` (R147E) |
| env_lark_token_mode | `tenant_access_token` (R147G) |
| env_no_proxy | `open.feishu.cn` (R147G) |
| config_state | `tenant_mode` |

**Critical insight:** In `tenant_access_token` mode, the SDK uses `Client.request()` to auto-fetch tenant tokens. keytar is **completely irrelevant** to this flow — keytar only stores OAuth user tokens, not tenant tokens.

---

## LANE 3: Token Mode Reset Analysis

### Token Mode Reset Options

| Option | Change | OAuth | keytar | User Action | Risk | Expected |
|---|---|---|---|---|---|---|
| A — Remove CLI arg, keep env | Remove `--token-mode` | no | no | none | low | Behavior unchanged; 99991661 persists |
| **B — Switch to user_access_token** | `--token-mode user_access_token --oauth` | **required** | **required** | **browser login** | **medium** | OAuth flow activated; keytar must work |
| C — Set to auto | Remove both CLI and env mode | no | no | none | low | May fall back to tenant; 99991661 persists |
| D — Keep tenant mode | No change | no | no | none | none | 99991661 persists |

### Key Findings

1. **keytar is irrelevant in tenant mode**: keytar stores OAuth user tokens; tenant tokens are fetched via `Client.request()` using `appId+appSecret` — no keytar involved

2. **Token mode + OAuth are coupled**: To use the keytar route, you must simultaneously:
   - Switch `--token-mode` to `user_access_token`
   - Add `--oauth` flag
   - Complete OAuth login (browser required)
   - Have working keytar

3. **These cannot be done independently**: You cannot "just rebuild keytar" to fix 99991661 in the current tenant mode config

---

## LANE 4: keytar Native Module Feasibility

| Field | Value |
|---|---|
| node_version | v24.14.0 |
| platform | win32/x64 |
| keytar_package_found | true (v7.9.0 in pnpm cache) |
| keytar_node_exists | **false** |
| missing_binary | `keytar/build/Release/keytar.node` |
| prebuild_found | false |
| build.gyp found | true |
| rebuild_tools_present | **unknown** |

**Feasibility assessment:** Rebuild is **medium risk** — requires node-gyp, Python, and C++ compiler. Even if rebuild succeeds, it only enables OAuth token storage. It does NOT fix the SDK's tenant token auto-attach behavior.

---

## LANE 5: OAuth / User Token Feasibility

| Field | Value |
|---|---|
| OAuth supported | **yes** |
| login command | `npx -y @larksuiteoapi/lark-mcp login -a <app_id> -s <app_secret> --oauth` |
| browser required | **yes** (localhost:3000 redirect) |
| user action required | **yes** |
| existing user token | false |
| user_access_token in env | false |
| keytar store existing data | false |

**OAuth flow:** Lark MCP starts a local HTTP server on `localhost:3000`, opens browser for OAuth, callback to `localhost:3000/callback` with auth code, token stored via keytar.

**Critical blocker:** OAuth login requires human browser interaction on `localhost:3000` — cannot be automated in current phase constraints.

---

## LANE 6: Repair Route Comparison

| Route | Description | Dependency | Config | User Action | Code | Risk | Success Prob | Rec |
|---|---|---|---|---|---|---|---|---|
| **A** | keytar rebuild + user mode + OAuth login | rebuild | patch | **browser** | no | medium | medium | **no** |
| B | Env injection USER_ACCESS_TOKEN | none | patch | no | no | **high secret risk** | high | no |
| C | SDK withTenantToken() patch | none | no | no | **yes** | none | unknown | no |
| **D** | **Pause Lark, investigate Tavily 405** | none | patch | no | no | none | unknown | **yes** |
| E | Pause external MCP, return mainline | none | no | no | no | none | high | no |

**Why Route A is not recommended:**
1. keytar rebuild may fail (missing build tools)
2. Even if keytar works, OAuth login requires browser interaction
3. Token mode must also be switched (separate config risk)
4. Root cause (SDK token attach bug) may still cause 99991661 in user mode
5. Too many coupled failure points

---

## LANE 7: Recommended Strategy

**Recommended:** Pause Lark MCP, enable Tavily MCP, investigate Tavily 405.

**Rationale:** The Lark MCP 99991661 issue has persisted across R147D→R147G. The root cause is a deep SDK behavior issue: `handler.js` calls `func(params)` without token when `getShouldUseUAT=false`, and `Client.request()` does not auto-attach tenant tokens for stdio MCP tools. The keytar rebuild route is blocked by multiple coupled requirements (rebuild + token mode switch + OAuth browser login). Meanwhile, the Tavily 405 error was identified in R131A and is completely independent. Investigating Tavily unblocks MCP tool availability while Lark is paused.

---

## LANE 8: R147I Authorization Package

```
recommended_phase: R147I_LARK_DISABLE_AND_TAVILY_405_DIAGNOSTIC

patch_required: true
  file: backend/extensions_config.json
  change: set lark.enabled=false, tavily.enabled=true

dependency_install_required: false
env_update_required: false
user_action_required: false

files_allowed:
  - backend/extensions_config.json (patch)
  - backend/run_r147i.py (temp harness)

files_forbidden:
  - .env
  - backend/packages/*
  - package.json / lockfiles

selected_tool: tavily_search
allowed_tool_calls: 1
model_call_allowed: false
write_tool_allowed: false
params: {"query": "test search"}

validation_plan:
  1. Patch extensions_config.json: lark.enabled=false, tavily.enabled=true
  2. Reset MCP tools cache (reset_mcp_tools_cache)
  3. Load tools via get_cached_mcp_tools()
  4. Verify tavily_search is available
  5. Invoke tavily_search with test query
  6. If 405: Tavily 405 confirmed → investigate R131A notes
  7. If success: Tavily working → Lark paused successfully
  8. If other error: classify and determine next step

rollback_plan: Restore lark.enabled=true, tavily.enabled=false in extensions_config.json
```

---

## LANE 9: Branch Decision

| Decision | Value |
|---|---|
| continue_lark | ❌ false |
| switch_to_tavily | ✅ true |
| pause_external_mcp | false |
| return_to_mainline | false |

**Rationale:** Lark MCP is blocked by a deep SDK token attachment bug. Multiple fix attempts (NO_PROXY, token mode changes) have failed. Pausing Lark and switching to Tavily unblocks MCP tool availability. Lark can be revisited later with more resources for SDK investigation.

---

## LANE 10: Unknown Registry Updates

| ID | Description | Fix |
|---|---|---|
| U-lark-tenant-mode-keytar-irrelevance | keytar only stores OAuth user tokens, NOT tenant tokens; keytar.node missing does NOT cause 99991661 in tenant mode | R147H: correctly classified |
| U-lark-token-mode-oauth-coupling | Switching to user_access_token mode requires --oauth AND OAuth login AND keytar — coupled requirements | R147H: identified coupling |
| U-keytar-rebuild-feasibility | keytar.node binary missing; rebuild requires build tools; success uncertain | R147H: medium risk assessed |
| U-oauth-browser-requirement | OAuth login requires browser redirect to localhost:3000 — cannot be automated | R147H: blocked by constraints |
| U-lark-sdk-token-attach-bug | SDK handler calls func(params) without token when shouldUseUAT=false; Client.request() does not auto-attach | R147H: root cause confirmed |
| U-lark-vs-tavily-branch-decision | Lark tenant token bug is deep SDK issue; Tavily 405 (R131A) is independent | R147H: recommended pause + Tavily |

---

## R147H Classification: PASSED

| Metric | Value |
|---|---|
| code_modified | false |
| dependency_installed | false |
| env_modified | false |
| patch_applied | false (diagnostic only) |
| smoke_executed | false |
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

## R147H EXECUTION SUCCESS

**Conclusion:** R147H's feasibility analysis reveals that the keytar rebuild route is not a viable short-term fix for the Lark MCP 99991661 error because:

1. **keytar is irrelevant in tenant_access_token mode** — it only stores OAuth user tokens
2. **Multiple coupled requirements** — keytar rebuild + token mode switch + OAuth browser login must all succeed together
3. **OAuth login requires human browser interaction** — blocked by current phase constraints
4. **Even if keytar works, root cause (SDK token attach bug) may remain**

**R147I should disable Lark MCP, enable Tavily MCP, and investigate the R131A Tavily 405 error.**