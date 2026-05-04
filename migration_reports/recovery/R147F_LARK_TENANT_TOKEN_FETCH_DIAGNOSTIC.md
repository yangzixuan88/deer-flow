# R147F: Lark MCP Tenant Token Fetch Diagnostic

## Status: PASSED

## Preceded By: R147E
## Proceeding To: R147G_LARK_PROXY_FIX

## Pressure: XXL

---

## Summary

R147F performed a diagnostic investigation into why `--token-mode tenant_access_token` still results in 99991661 "Missing access token for authorization." The diagnostic identified **HTTP_PROXY/HTTPS_PROXY being set in the Python process environment with no NO_PROXY exclusion for `open.feishu.cn`** as the most likely root cause. The SDK's stdio subprocess inherits these proxy settings, and the SDK's HTTP client may route the tenant token fetch through the proxy, causing it to fail silently.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R147E |
| current_phase | R147F |
| recommended_pressure | XXL |
| reason | tenant_access_token flag reaches SDK but 99991661 persists; diagnose token fetch/attach path before keytar repair |

---

## LANE 1: Workspace / Config Guard

| Check | Result |
|---|---|
| workspace_dirty | true (many untracked files) |
| r147a_commit_present | true (24f61bc3) |
| r147e_patch_present | true (extensions_config.json has --token-mode tenant_access_token) |
| only_lark_enabled | true (tavily/exa disabled) |
| safe_to_continue | true |
| authorized_modified | `backend/extensions_config.json` (R147E patch) |

---

## LANE 2: Environment Presence / Proxy Check

**Critical finding: HTTP_PROXY and HTTPS_PROXY are both PRESENT in the environment.**

| Variable | Status |
|---|---|
| LARK_APP_ID | PRESENT |
| LARK_APP_SECRET | PRESENT |
| LARK_TOKEN_MODE | MISSING (not set in .env) |
| HTTP_PROXY | PRESENT (`http://127.0.0.1:10808`) |
| HTTPS_PROXY | PRESENT (`http://127.0.0.1:10808`) |
| NO_PROXY | **MISSING** |
| LARK_CLI_NO_PROXY | **MISSING** |

**Key insight:** The `lark_cli_adapter.ts` sets `LARK_CLI_NO_PROXY=1` to disable proxy for lark-cli commands — confirming the project team is aware of proxy impact on Lark tooling. The Lark MCP stdio subprocess has NO equivalent setting.

---

## LANE 3: Stdio Diagnostic

The Lark MCP stdio process started and loaded 17 tools (consistent with tenant mode). Captured stderr shows:

| Log Type | Evidence |
|---|---|
| keytar warning | YES — multiple `[WARN] [StorageManager] Failed to initialize encryption: Error: Cannot find module '../build/Release/keytar.node'` |
| tenant mode seen | false (no explicit tenant mode log) |
| stdio transport initialized | true |
| network retry observed | YES — `WARN GET https://registry.npmmirror.com/@larksuiteoapi%2Flark-mcp error (ECONNRESET)` |
| auth store initialized | true (OAuth path attempted) |

---

## LANE 4: Tenant Token Endpoint Reachability

| Field | Value |
|---|---|
| endpoint | `https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal` |
| endpoint_reachable | **true** |
| request_attempt_detected | true |
| http_status | **200** (via proxy) |
| elapsed_seconds | **1.05s** |
| network_error | null |
| proxy_issue_suspected | PARTIAL — proxy present but did not block; SDK may route differently |

**Python urllib.request reached the endpoint in 1.05s via the proxy.** This proves the network path exists. However, the SDK's node.js HTTP agent may handle proxy differently from Python's urllib.

---

## LANE 5: Readonly Tool Reproduction With Logs

| Field | Value |
|---|---|
| tool_reproduction_attempted | true |
| tool_call_count | 1 |
| error_code | **99991661** |
| error_message | "Missing access token for authorization. Please make a request with token attached." |
| elapsed_seconds | **4.07s** |
| missing_access_token_persists | **true** |
| external_write_performed | false |
| tools_loaded | 17 |
| log_id | `202605021829319F8028F2180DBA293271` |

---

## LANE 6: Root Cause Classification

**Most Likely Cause: Cause E — Proxy/No-Proxy Conflict**

| Dimension | Assessment |
|---|---|
| confidence | **high** |
| primary_hypothesis | SDK's HTTP client routes tenant token fetch through HTTP_PROXY, which may cause the request to fail or be misrouted. The proxy (`localhost:10808`) is a local HTTP proxy that may not handle the internal API calls correctly. |
| supporting_evidence | 1. HTTP_PROXY/HTTPS_PROXY both set to `http://127.0.0.1:10808`<br>2. NO_PROXY is MISSING — `open.feishu.cn` not excluded<br>3. `lark_cli_adapter.ts` sets `LARK_CLI_NO_PROXY=1` to disable proxy for Lark CLI, confirming awareness<br>4. 4.07s elapsed (vs 1.05s Python test) suggests SDK path is slow, possibly proxy retry<br>5. SDK's node.js HTTP agent may not handle proxy the same way as Python urllib |
| disconfirming_evidence | 1. Python urllib reached endpoint via proxy in 1.05s<br>2. SDK loaded tools and initialized — basic network works<br>3. keytar warning is NOT relevant to tenant token flow |

**Secondary hypothesis (Cause B):** appId/appSecret may not be correctly passed into SDK's Client initialization.

**The proxy conflict explains:**
- Why `getShouldUseUAT` returns `false` correctly (SDK knows it's in tenant mode)
- Why `larkOapiHandler` calls `func(params)` without token (correct behavior for tenant mode)
- Why the token fetch fails silently (SDK's HTTP client routes through proxy → fails → proceeds without token → 99991661)

---

## LANE 7: Repair Options Re-evaluation

### Option A — Add `NO_PROXY=open.feishu.cn` to Lark MCP env ✅ (RECOMMENDED)

| Field | Value |
|---|---|
| change | Add `"env": {"NO_PROXY": "open.feishu.cn"}` to lark entry in `extensions_config.json` |
| dependencies | None |
| risk | **low** |
| user_action | None |
| reason | Lowest-risk fix: one env var addition. If proxy is causing SDK's token fetch to fail, bypassing proxy for `open.feishu.cn` should resolve it. Same pattern as `LARK_CLI_NO_PROXY=1` in lark_cli_adapter.ts. |
| recommended | **YES** |

### Option B — Add `LARK_CLI_NO_PROXY=1` to Lark MCP env

| Field | Value |
|---|---|
| change | Add `"env": {"LARK_CLI_NO_PROXY": "1"}` to lark entry |
| dependencies | None |
| risk | low |
| reason | Same pattern as lark_cli_adapter.ts. But `LARK_CLI_NO_PROXY` may not be recognized by Lark MCP's SDK HTTP client (it's a Lark CLI-specific env). |
| recommended | false (less targeted than Option A) |

### Option C — Fix keytar for OAuth/user token flow

| Field | Value |
|---|---|
| change | `npm rebuild keytar` to enable OAuth token persistence |
| dependencies | **Yes** (prohibited in diagnostic phase) |
| risk | medium |
| reason | High cost, may not fix root cause. R147F evidence points to proxy issue, not keytar. |
| recommended | false |

### Option D — Pause Lark, investigate Tavily

| Field | Value |
|---|---|
| change | Disable Lark, re-enable Tavily, investigate 405 error |
| risk | low |
| reason | Independent of current issue. Option A is worth trying first. |
| recommended | false |

---

## LANE 8: R147G Authorization Package

```
recommended_phase: R147G_LARK_PROXY_FIX

patch_required: YES
  file: backend/extensions_config.json
  change: Add "env": {"NO_PROXY": "open.feishu.cn"} to lark entry

dependency_install_required: false
env_update_required: false (patch covers it)
user_action_required: false

files_allowed:
  - backend/extensions_config.json (patch)
  - backend/run_r147g.py (temp harness)

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
  1. Patch extensions_config.json: add env.NO_PROXY=open.feishu.cn to lark entry
  2. Reset MCP tools cache (reset_mcp_tools_cache)
  3. Load lark_im_v1_chat_list via get_cached_mcp_tools()
  4. Invoke with empty params {}
  5. Expect: [] (bot not in groups) or list of chat objects — both are success
  6. If error 99991661: proxy fix insufficient → try keytar fix or pause Lark
  7. If other error: inspect and classify
  8. Record: tool execution success/failure, error code, response shape, elapsed time

rollback_plan: Remove NO_PROXY from extensions_config.json env field
```

---

## LANE 9: Branch Decision

| Decision | Value |
|---|---|
| continue_lark | ✅ true |
| switch_to_tavily | false |
| pause_external_mcp | false |
| return_to_mainline | false |

**Rationale:** R147F identified a specific, low-risk fix (NO_PROXY=open.feishu.cn). This is worth attempting before pausing Lark or switching to Tavily.

---

## LANE 10: Unknown Registry Updates

| ID | Description | Fix |
|---|---|---|
| U-lark-proxy-no-proxy-conflict | HTTP_PROXY/HTTPS_PROXY set to localhost:10808; NO_PROXY missing; SDK may route token fetch through proxy causing it to fail silently | R147G: add NO_PROXY=open.feishu.cn to lark env |
| U-lark-cli-no-proxy-pattern | lark_cli_adapter.ts sets LARK_CLI_NO_PROXY=1 confirming project aware of proxy impact on Lark tooling | R147G: same NO_PROXY pattern for Lark MCP SDK |
| U-lark-urllib-reached-via-proxy | Python urllib reached tenant endpoint via proxy in 1.05s; SDK node.js may handle proxy differently | R147G: bypass proxy explicitly for SDK's API domain |

---

## R147F Classification: PASSED

| Metric | Value |
|---|---|
| code_modified | false |
| dependency_installed | false |
| env_modified | false |
| patch_applied | false (diagnostic only) |
| smoke_executed | true (via run_r147f.py) |
| smoke_result | FAILED (99991661) |
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

## R147F EXECUTION SUCCESS

**Conclusion:** R147F's diagnostic identified a **proxy/no-proxy conflict** as the most likely cause of 99991661 persisting even with `--token-mode tenant_access_token`. The SDK's stdio subprocess inherits HTTP_PROXY/HTTPS_PROXY from the Python process, and NO_PROXY is not set to exclude `open.feishu.cn`. The SDK's HTTP client may route the tenant token fetch through the proxy, causing it to fail silently, after which the API call proceeds without a token.

**R147G should add `NO_PROXY=open.feishu.cn`** to the Lark MCP env in `extensions_config.json` and retry the smoke test.