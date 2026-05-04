# R147K: Tavily stdio Fix

## Status: PASSED

## Preceded By: R147J
## Proceeding To: R147L_MCP_STATUS_SUMMARY

## Pressure: XXL

---

## Summary

R147K applied the stdio transport fix to the Tavily MCP configuration and ran a successful smoke test. The config patch changed `type` from `sse` to `stdio`, set `command` to `npx.cmd`, set `args` to `["-y", "tavily-mcp@latest"]`, and set `url` to `null`. The smoke test returned real search results (5 high-quality AI articles from SAS, IBM, Wikipedia, Notre Dame, People Powered) in 8.80 seconds. The fix was committed as `da4b7565`.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R147J |
| current_phase | R147K |
| recommended_pressure | XXL |
| reason | Tavily stdio fix ready; apply patch and smoke test |

---

## LANE 1: Workspace / Config Guard

| Check | Result |
|---|---|
| workspace_dirty | true |
| r147a_commit_present | true (24f61bc3) |
| extensions_config_dirty | true |
| safe_to_continue | true |
| authorized_modified_files | `backend/extensions_config.json` |
| note | R147I commit `30345631`, R147J reports written |

---

## LANE 2: Config Patch Applied

| Field | From | To |
|---|---|---|
| type | `sse` | `stdio` |
| url | `https://mcp.tavily.com/mcp` | `null` |
| command | `null` | `npx.cmd` |
| args | `[]` | `["-y", "tavily-mcp@latest"]` |
| env | `{"TAVILY_API_KEY": "$TAVILY_API_KEY"}` | (unchanged) |

**Preserved:** env var auth, key not in URL.

---

## LANE 3: Static Config Validation

| Field | Value |
|---|---|
| JSON parse | PASSED |
| Extensions config load | PASSED |
| Only Tavily enabled | true |
| tavily_type | `stdio` |
| tavily_command | `npx.cmd` |
| tavily_args_correct | true |
| secret_values_printed | false |

---

## LANE 4: Tavily Runtime Tool List

| Field | Value |
|---|---|
| MCP cache reset | true |
| Tools loaded | 5 |
| Tavily tool found | true |
| Tavily tool name | `tavily_tavily_search` |
| Lark called | false |
| Exa called | false |
| startup_error | null |

---

## LANE 5: Smoke Test Execution

| Field | Value |
|---|---|
| smoke_test_invoked | true |
| tool_name | `tavily_tavily_search` |
| params | `{"query": "OpenAI"}` |
| elapsed_seconds | 8.80s |
| result_type | `list` |
| result_count | 1 |
| first_result_keys | `["type", "text", "id"]` |
| smoke_status | **PASSED** |

---

## LANE 6: Result Verification

| Field | Value |
|---|---|
| search_returned_real_results | true |
| result_content_quality | **high** (SAS, IBM, Wikipedia articles) |

**Search results returned:**
1. **SAS** — Artificial Intelligence (AI): What it is and why it matters
2. **IBM** — What Is Artificial Intelligence (AI)?
3. **Wikipedia** — Artificial Intelligence
4. **Notre Dame Learning** — AI Overview and Definitions
5. **People Powered** — What do we mean by AI?

| Field | Value |
|---|---|
| key_in_url | false |
| env_var_auth | true |

---

## LANE 7: Commit

| Field | Value |
|---|---|
| commit_created | true |
| commit_sha | `da4b7565` |
| committed_files | `extensions_config.json` |
| commit_message | `chore(mcp): switch Tavily from SSE to stdio transport` |
| excluded | `run_r147k.py`, reports |

---

## LANE 8: Next Phase Decision

| Condition | Next Phase |
|---|---|
| result=passed - Tavily stdio working | **R147L_MCP_STATUS_SUMMARY** |

**R147L goal:** Summarize MCP status: Lark (SDK bug, paused), Tavily (working via stdio), Exa (missing credentials). Document the full R144-R147K journey.

---

## R147K Classification: PASSED

| Metric | Value |
|---|---|
| code_modified | false |
| dependency_installed | false |
| env_modified | false |
| patch_applied | true |
| db_written | false |
| jsonl_written | false |
| gateway_started | false |
| model_api_called | false |
| mcp_runtime_called | true |
| external_tool_called | false |
| push_executed | false |
| merge_executed | false |
| safety_violations | [] |
| blockers_preserved | true |

---

## R147K EXECUTION SUCCESS

**Conclusion:** R147K successfully applied the stdio transport fix for Tavily MCP. The config change (`type: sse` → `type: stdio`, with `npx.cmd -y tavily-mcp@latest`) resolved the HTTP 405 error from R147I. The smoke test returned 5 high-quality AI search results in 8.80 seconds, confirming that the Tavily MCP is now fully operational via stdio transport. The key is preserved in the environment variable (`TAVILY_API_KEY`), not embedded in any URL.

`★ Insight ─────────────────────────────────────`
**本地 stdio MCP 服务器 vs 远程 SSE 端点**：tavily-mcp 是本地子进程，通过 stdin/stdout 与 langchain 通信；而 `https://mcp.tavily.com/mcp` 是远程 SSE 端点，需要专用 HTTP 客户端。配置时必须区分这两种模式。
`─────────────────────────────────────────────────`