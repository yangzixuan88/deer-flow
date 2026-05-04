# R144: Internal Tool Call Observability Smoke

## Status: PASSED

## Preceded By: R143
## Proceeding To: R145

## Pressure: XXL

---

## Summary

R144 smoke test using `create_deerflow_agent(tools=[echo_tool])` — the internal tool call path that bypasses `get_available_tools()` and avoids MCP initialization.

- **Agent build path**: `create_deerflow_agent(tools=[echo_tool])` ✅
- **MCP triggered**: No ✅
- **Tool calls detected**: True (names: ['echo', 'unknown'])
- **Tool messages detected**: True
- **Model call count**: 2
- **RunRecord.result non-null**: True
- **Result has messages**: True

---

## LANE 0: Pre-flight

| Check | Result |
|---|---|
| workspace_clean | False |
| dirty_files | 43 |
| r142c_commit_confirmed | True |
| minimax_api_key_present | True |
| preflight_passed | True |

---

## LANE 5: Agent Build

| Check | Result |
|---|---|
| path | `create_deerflow_agent(tools=[echo_tool])` |
| bypasses get_available_tools | True |
| mcp_triggered | False |
| agent_tools | ['echo'] |

---

## LANE 7: Tool Call Detection

| Check | Result |
|---|---|
| tool_calls_detected | True |
| tool_call_names | ['echo', 'unknown'] |
| tool_messages_detected | True |
| elapsed | 16.3s |

---

## LANE 8: RunRecord Result

| Check | Result |
|---|---|
| record_result non-null | True |
| result keys | ['messages', 'thread_data'] |
| messages count | 4 |

---

## LANE 9: Store Record

| Check | Result |
|---|---|
| store has result | False |
| store result keys | None |

---

## LANE 10: Classification

**Result: PASSED**

| Metric | Value |
|---|---|
| tool_calls_detected | True |
| echo_tool_called | True |
| tool_messages_detected | True |
| record_result_non_null | True |
| result_has_messages | True |

---

## R144 EXECUTION SUCCESS
