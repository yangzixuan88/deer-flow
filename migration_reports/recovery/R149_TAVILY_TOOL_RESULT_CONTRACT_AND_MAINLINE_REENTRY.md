# R149: Tavily Tool Result Contract and Mainline Re-entry

## Status: PASSED

## Preceded By: R148
## Proceeding To: R150_MAINLINE_SYSTEM_ACCEPTANCE_MAP

## Pressure: L

---

## Summary

R149 closes the R148 Tavily agent smoke test by defining the tool-call result contract, correcting R148's own audit classification, finalizing MCP server status, and authorizing mainline re-entry. All documentation lanes complete. R150 (mainline system acceptance map) is authorized.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R148 |
| current_phase | R149 |
| recommended_pressure | L |
| reason | R148 passed with full validation; R149 is documentation and contract definition phase — no execution risk |

---

## LANE 1: Workspace Guard

| Check | Result |
|---|---|
| workspace_dirty | true |
| r148_commit_present | **true** (`f480fec1`) |
| r148_report_present | **true** |
| recommended_next_phase_from_r148 | R149_TAVILY_TOOL_RESULT_CONTRACT_AND_MAINLINE_REENTRY |
| safe_to_continue | **true** |

---

## LANE 2: R148 Evidence Reconciliation

R148's own audit classification contained two fields requiring correction:

| Field | R148 Raw | Corrected | Reason |
|---|---|---|---|
| `mcp_runtime_called` | `false` | `true` | Tavily stdio MCP server was invoked via `tavily_tavily_search` tool-call |
| `external_tool_called` | `false` | `external_readonly_tool_called: true` | Tavily search is read-only; no write performed |

**R148 Corrected Classification:**

| Metric | Value |
|---|---|
| model_api_called | **true** |
| model_api_call_count | **2** |
| mcp_runtime_called | **true** |
| external_readonly_tool_called | **true** |
| external_write_performed | **false** |
| code_modified | **false** |
| env_modified | **false** |
| db_written | **false** |
| jsonl_written | **false** |
| safety_violations | `[]` |
| blockers_preserved | **true** |

---

## LANE 3: Tavily Tool-Call Contract Definition

| Field | Value |
|---|---|
| contract_name | `TavilyReadonlySearchContract` |
| tool_name | `tavily_tavily_search` |
| transport | `stdio` |
| auth_method | `env var (TAVILY_API_KEY)` |
| call_pattern | `agent.astream() → AIMessage.tool_calls[0] → tool.invoke(input) → ToolMessage.content` |
| input_schema | `{ query: string }` |
| output_schema | `{ results: array<{url, title, description}> }` |
| contract_validated | **true** |
| validated_by | R148 (PASSED, 27.22s, 1 call) |

**Result format consumed by model:**
- `url`: string (e.g. `https://reddit.com/r/OpenAI`)
- `title`: string
- `description`: string

---

## LANE 4: Result Persistence Contract

| Field | Value |
|---|---|
| contract_name | `TavilyToolResultPersistenceContract` |
| what_persists | `ToolMessage.content` from `tavily_tavily_search` call |
| where_persists | `run_meta` message history (`AIMessage.tool_calls` + `ToolMessage` chain) |
| persistence_mechanism | LangGraph `InMemorySaver` or configured checkpointer |
| persistence_ready | **true** |
| persistence_validated_by | R148 (`tool_result_detected=true`) |
| db_write_expected | **false** |
| note | Production persistence via configured checkpointer; InMemorySaver used in smoke |

**Run record fields:**
- `thread_id`: string (e.g. `r148-78728f1c`)
- `run_id`: string
- `tool_calls`: list of `AIMessage.tool_calls`
- `tool_results`: list of `ToolMessage.content`
- `final_answer`: `AIMessage.content` (final)
- `model_call_count`: integer
- `tavily_call_count`: integer

---

## LANE 5: MCP Server Status Finalization

| Server | Status | Transport | Auth | Next / Blocker |
|---|---|---|---|---|
| **tavily** | ✅ working | stdio | env var | mainline production (R150) |
| **lark** | ❌ paused | stdio | — | SDK token attach bug (99991661) |
| **exa** | ❌ disabled | stdio | — | EXA_API_KEY missing |

**Lark blocker detail:** SDK's `Client.request()` does not automatically attach tenant token in stdio MCP tool calls. Fix requires SDK patch to attach tenant token. Estimated effort: unknown.

**Exa blocker detail:** `EXA_API_KEY` not present in environment. Fix: provide env var. Estimated effort: low (config only).

---

## LANE 6: Mainline Re-entry Readiness

| Condition | Result |
|---|---|
| gate_pass | **true** |
| tavily_usable_in_mainline | **true** |
| tavily_integration_route | `create_deerflow_agent(tools=[tavily_tool])` via `get_cached_mcp_tools()` |
| mcp_lazy_init_safe | **true** |
| thread_id_issue_resolved | **true** |
| thread_id_resolution | `__pregel_runtime` context injection (pattern from R144/R148) |
| result_persistence_defined | **true** |
| safety_guard_defined | **true** |
| lark_blocker_acknowledged | **true** |
| exa_blocker_acknowledged | **true** |

**Recommended action:** Authorize `R150_MAINLINE_SYSTEM_ACCEPTANCE_MAP`

---

## LANE 7: Next Phase Design

| Field | Value |
|---|---|
| recommended_next_phase | `R150_MAINLINE_SYSTEM_ACCEPTANCE_MAP` |
| goal | Validate Tavily MCP integration in mainline context; map acceptance criteria for full system readiness |
| pressure_recommended | M |

**Key checks for R150:**
1. Tavily MCP works via mainline `create_deerflow_agent` pipeline
2. Result persistence works via mainline checkpointer
3. Safety guard passes in mainline context
4. `thread_id` context properly set via mainline worker infrastructure
5. No regression in other MCP servers when re-enabled

**Acceptance criteria for R150:**
- `tavily_tavily_search` callable via mainline agent
- Tool result persisted in `run_meta`
- No `ThreadDataMiddleware` crash
- Safety guard (no external write) respected
- Model call budget respected

**Forbidden in R150:**
- no code modification (acceptance mapping only)
- no production DB writes
- no MiniMax API calls beyond smoke level
- no Lark/Exa re-enablement

---

## LANE 8: Unknown Registry Update

No unknown registry entries identified in R149.

---

## LANE 9: Report Generation

| Field | Value |
|---|---|
| reports_written | **true** |
| md_report | `R149_TAVILY_TOOL_RESULT_CONTRACT_AND_MAINLINE_REENTRY.md` |
| json_report | `R149_TAVILY_TOOL_RESULT_CONTRACT_AND_MAINLINE_REENTRY.json` |
| r148_classification_correction_logged | **true** |

---

## R149 Classification: PASSED

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

## R149 EXECUTION SUCCESS

**Conclusion:** R149 closes the R144–R149 migration journey:

1. ✅ R148 evidence reconciled (mcp_runtime_called corrected to true)
2. ✅ Tavily tool-call contract defined and validated by R148
3. ✅ Result persistence contract documented
4. ✅ MCP server status finalized (Tavily ✅, Lark ❌, Exa ❌)
5. ✅ Mainline re-entry readiness confirmed
6. ✅ R150 authorized: `MAINLINE_SYSTEM_ACCEPTANCE_MAP`

---

## R144–R149 Journey Summary

| Phase | Key Achievement |
|---|---|
| R144 | LangGraph `__pregel_runtime` context injection pattern discovered |
| R147I | Lark disabled; Tavily enabled → HTTP 405 (SSE transport mismatch) |
| R147J | Root cause confirmed: `tavily-mcp` is local stdio, not remote SSE |
| R147K | stdio fix applied; Tavily smoke PASSED (8.80s, real results) |
| R147L | MCP status summary; agent integration gate PASSED |
| R148 | Agent Tavily tool-call smoke PASSED (27.22s, 2 model calls, 1 search) |
| R149 | Tool-call contract defined; mainline re-entry authorized |

---

## R149 EXECUTION SUCCESS

```
R149_TAVILY_TOOL_RESULT_CONTRACT_AND_MAINLINE_REENTRY_DONE
status=passed
recommended_next_phase=R150_MAINLINE_SYSTEM_ACCEPTANCE_MAP
```

`★ Insight ─────────────────────────────────────`
**工具调用结果契约**：R149 定义了 `TavilyReadonlySearchContract`，明确了 `ToolMessage.content` 的持久化位置和格式。这使得 R150 的 mainline acceptance mapping 有据可依，而不是盲目回归测试。
`─────────────────────────────────────────────────`
