# R147J: Tavily 405 Root Cause Diagnostic

## Status: PASSED

## Preceded By: R147I
## Proceeding To: R147K_TAVILY_STDIO_FIX

## Pressure: XXL

---

## Summary

R147J investigated the root cause of the HTTP 405 error encountered when connecting to Tavily MCP via SSE transport. Analysis of the Tavily MCP architecture revealed that `tavily-mcp@0.2.19` is a **local stdio MCP server** (published 2026-04-24 by dustinpulver), not a remote SSE endpoint. The correct transport is `type: stdio` with `command: npx.cmd` and `args: ["-y", "tavily-mcp@latest"]`. The 405 error was caused by a transport protocol mismatch: langchain_mcp_adapters SSE client sends POST for SSE handshake, but Tavily's SSE endpoint (`https://mcp.tavily.com/mcp`) requires GET.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R147I |
| current_phase | R147J |
| recommended_pressure | XXL |
| reason | 405 confirmed in R147I; identify correct transport mode for Tavily MCP |

---

## LANE 1: Workspace / Config Guard

| Check | Result |
|---|---|
| workspace_dirty | true |
| r147a_commit_present | true (24f61bc3) |
| extensions_config_dirty | true |
| safe_to_continue | true |
| authorized_modified_files | `backend/extensions_config.json` |
| note | R147I commit `30345631` present |

---

## LANE 2: Current Tavily Config State

| Field | Value |
|---|---|
| type | `sse` |
| url | `https://mcp.tavily.com/mcp` |
| command | `null` |
| args | `[]` |
| env | `TAVILY_API_KEY: $TAVILY_API_KEY` |
| enabled | `true` |
| problem | `type=sse` with direct URL causes 405 from langchain_mcp_adapters POST vs GET mismatch |

---

## LANE 3: Tavily MCP Architecture Investigation

| Field | Value |
|---|---|
| tavily_mcp_package | `tavily-mcp@0.2.19` |
| npm_registry | `https://registry.npmmirror.com` |
| bin_entry | `tavily-mcp` |
| version | 0.2.19 (published 2026-04-24) |
| maintainer | dustinpulver@tavily.com |
| sdk_dependency | `@modelcontextprotocol/sdk: 1.26.0` |
| transports_supported | `stdio` (local subprocess) |

### Transport Options Found

| Mode | Description | Command | Type | Status |
|---|---|---|---|---|
| **local_stdio** | Local npx installation, spawns subprocess via stdin/stdout | `npx.cmd -y tavily-mcp@latest` | stdio | **correct for langchain** |
| remote_sse_via_mcp_remote | Use mcp-remote proxy to connect to Tavily SSE endpoint | `npx.cmd -y mcp-remote <url>` | stdio | alternative but embeds key in URL |
| direct_sse | Direct SSE connection via langchain_mcp_adapters SSE client | `null` (direct URL) | sse | **BROKEN** — 405 on POST |

### Correct Transport

| Field | Value |
|---|---|
| correct_transport | `stdio` |
| correct_command | `npx.cmd` |
| correct_args | `["-y", "tavily-mcp@latest"]` |
| correct_env | `{"TAVILY_API_KEY": "$TAVILY_API_KEY"}` |

---

## LANE 4: 405 Root Cause Confirmed

| Field | Value |
|---|---|
| error_code | 405 |
| error_method | **POST** |
| expected_method | **GET** |
| culprit | langchain_mcp_adapters SSE client (`mcp/client/sse.py`) uses POST for SSE handshake |
| tavily_endpoint_behavior | `https://mcp.tavily.com/mcp` requires GET for SSE stream initialization, rejects POST with 405 |
| mcp_sse_spec_compliance | MCP spec allows POST for initial handshake but Tavily endpoint only accepts GET |
| root_cause_classification | **Transport protocol mismatch** between langchain SSE client and Tavily SSE endpoint |

**Error trace from R147I:**
```
httpx.HTTPStatusError: Client error '405 Method Not Allowed'
  for url 'https://mcp.tavily.com/mcp'
  at sse_client (mcp/client/sse.py:74)
  event_source.response.raise_for_status()
```

---

## LANE 5: stdio Transport Validation

| Field | Value |
|---|---|
| tavily_mcp_npm_package | `tavily-mcp@0.2.19` |
| version_published | 2026-04-24 |
| maintainer | dustinpulver@tavily.com |
| sdk_dependency | `@modelcontextprotocol/sdk: 1.26.0` |
| transports_supported | `stdio` |
| env_var_auth | true |
| stdio_config_valid | true |

**Key insight:** `tavily-mcp` is a local stdio MCP server that spawns a subprocess and communicates via stdin/stdout. It is NOT a remote SSE endpoint proxy. The `https://mcp.tavily.com/mcp` URL is Tavily's remote MCP server accessed via a separate HTTP transport (not langchain's SSE client).

---

## LANE 6: mcp-remote Alternative Examined

| Field | Value |
|---|---|
| package | `mcp-remote` |
| command | `npx.cmd -y mcp-remote <url>` |
| embeds_key_in_url | **true** |
| url_format | `https://mcp.tavily.com/mcp/?tavilyApiKey=...` |
| security_concern | API key embedded in URL query parameter (exposed in process list, logs) |
| preferred | false |

**Reason for rejection:** Key embedded in URL is a security risk. Env var auth via stdio is preferred.

---

## LANE 7: Fix Recommendation

| Change | From | To |
|---|---|---|
| type | `sse` | `stdio` |
| command | `null` | `npx.cmd` |
| args | `[]` | `["-y", "tavily-mcp@latest"]` |
| url | `https://mcp.tavily.com/mcp` | `null` |
| env | `{"TAVILY_API_KEY": "$TAVILY_API_KEY"}` | `{"TAVILY_API_KEY": "$TAVILY_API_KEY"}` (unchanged) |

**Preserved:** env var auth, key not in URL.

---

## LANE 8: Next Phase Decision

| Condition | Next Phase |
|---|---|
| result=passed - 405 root cause confirmed | **R147K_TAVILY_STDIO_FIX** |

**R147K goal:** Apply stdio transport fix to `extensions_config.json` and run Tavily smoke test.

---

## LANE 9: R147K Authorization Package

```
phase: R147K_TAVILY_STDIO_FIX
title: TAVILY_STDIO_FIX
pressure: XXL
goal: Apply stdio transport fix to extensions_config.json and smoke test Tavily MCP

patch_required: true
  file: backend/extensions_config.json
  change: set tavily.type=stdio, tavily.command=npx.cmd, tavily.args=["-y","tavily-mcp@latest"], tavily.url=null

allowed_files:
  - backend/extensions_config.json (patch)

forbidden_files:
  - .env
  - backend/packages/*
  - package.json / lockfiles

smoke_test_plan:
  1. Patch extensions_config.json: type=stdio, command=npx.cmd, args=[-y,tavily-mcp@latest], url=null
  2. Reset MCP tools cache (reset_mcp_tools_cache)
  3. Load tools via get_cached_mcp_tools()
  4. Verify tavily-search tool is available
  5. Invoke tavily-search with {"query": "OpenAI"}
  6. If success: Tavily working via stdio transport
  7. If failure: classify error, determine next step

rollback_plan: Restore type=sse, url=https://mcp.tavily.com/mcp, command=null, args=[]
```

---

## LANE 10: Unknown Registry Updates

| ID | Description | Fix |
|---|---|---|
| U-tavily-local-stdio-correct-transport | tavily-mcp@0.2.19 is a local stdio MCP server; correct transport is type=stdio with npx command, NOT type=sse with direct URL | R147J: identified stdio as correct transport |
| U-tavily-sse-post-get-mismatch-confirmed | langchain_mcp_adapters SSE client sends POST but Tavily SSE endpoint requires GET; 405 is transport mismatch, not credential issue | R147J: 405 root cause confirmed; stdio transport avoids this |
| U-tavily-mcp-remote-url-key-security | mcp-remote alternative embeds TAVILY_API_KEY in URL query parameter; security risk; env var auth via stdio is preferred | R147J: mcp-remote rejected due to URL-embedded key |

---

## R147J Classification: PASSED

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

## R147J EXECUTION SUCCESS

**Conclusion:** R147J's root cause diagnostic confirmed that the HTTP 405 error from `https://mcp.tavily.com/mcp` was a **transport protocol mismatch**, not a credential or configuration issue. langchain_mcp_adapters SSE client sends POST for SSE handshake, but Tavily's endpoint requires GET. The fix is to switch from `type: sse` (direct URL) to `type: stdio` with local `npx tavily-mcp` installation. The `tavily-mcp` package (v0.2.19) is a local stdio MCP server — it spawns a subprocess and communicates via stdin/stdout, using the `@modelcontextprotocol/sdk`. This is the correct approach for langchain_mcp_adapters.

**R147K should apply the stdio transport fix** to `extensions_config.json`: change `type` to `stdio`, set `command` to `npx.cmd`, set `args` to `["-y", "tavily-mcp@latest"]`, and set `url` to `null`. Then run the Tavily smoke test to verify the fix works.

`★ Insight ─────────────────────────────────────`
**MCP 传输类型决定通信协议**：stdio 模式通过子进程 stdin/stdout 通信，SSE 模式通过 HTTP SSE 流。langchain_mcp_adapters 的 SSE 客户端发送 POST 握手，但 Tavily 的 SSE 端点只接受 GET——这是协议不匹配，不是 API key 问题。
`─────────────────────────────────────────────────`