# R147B: Lark MCP Tool List and Safe Smoke Plan

## Status: PASSED

## Preceded By: R147A
## Proceeding To: R147C_LARK_READONLY_TOOL_SMOKE

## Pressure: XXL

---

## Summary

R147B executed two goals:
1. **Tool schema inspection** — list all 19 Lark MCP tools and inspect their risk categories
2. **Safe smoke planning** — classify each tool by side-effect risk and select the safest read-only candidate

Both goals **PASSED**. All 19 tools classified. `lark_im_v1_chat_list` selected as the safe smoke target for R147C.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R147A |
| current_phase | R147B |
| recommended_pressure | XXL |
| reason | Lark MCP runtime health passed; classify tools and choose safe read-only smoke target |

---

## LANE 1: Workspace / Dirty Guard

| Check | Result |
|---|---|
| workspace_dirty | true |
| dirty_files_count | 412 |
| r147a_commit_present | true |
| r147a_commit_sha | `24f61bc3` |
| unexpected_production_dirty_files | [] |
| safe_to_continue | true |

---

## LANE 2: Lark Runtime Tool List

| Metric | Result |
|---|---|
| lark_runtime_started | true |
| tool_list_loaded | true |
| tool_count | **19** |
| tavily_runtime_called | false |
| exa_runtime_called | false |
| external_tool_called | false |

**Tools loaded** (19 total):
```
lark_bitable_v1_app_create              [CREATE — HIGH RISK]
lark_bitable_v1_appTable_create        [CREATE — HIGH RISK]
lark_bitable_v1_appTableField_list     [READ — safe ✓]
lark_bitable_v1_appTable_list          [READ — safe ✓]
lark_bitable_v1_appTableRecord_create  [CREATE — HIGH RISK]
lark_bitable_v1_appTableRecord_search  [READ/SEARCH — safe ✓]
lark_bitable_v1_appTableRecord_update  [UPDATE — HIGH RISK]
lark_contact_v3_user_batchGetId        [READ — safe ✓]
lark_docx_v1_document_rawContent       [READ — safe ✓]
lark_drive_v1_permissionMember_create  [PERMISSION — HIGH RISK]
lark_im_v1_chat_create                [CREATE — HIGH RISK]
lark_im_v1_chat_list                  [READ — safe ✓ — SELECTED]
lark_im_v1_chatMembers_get            [READ — safe ✓]
lark_im_v1_message_create             [SEND — HIGH RISK]
lark_im_v1_message_list               [READ — safe ✓]
lark_wiki_v1_node_search              [READ/SEARCH — safe ✓]
lark_wiki_v2_space_getNode            [READ — safe ✓]
lark_docx_builtin_search              [READ/SEARCH — safe ✓]
lark_docx_builtin_import              [IMPORT — HIGH RISK]
```

---

## LANE 3: Tool Risk Matrix

### HIGH RISK — NOT safe for smoke (13 tools)

| Tool | Category | Side Effect | Reason |
|---|---|---|---|
| lark_bitable_v1_app_create | create | high | Creates a Base App in user-defined folder |
| lark_bitable_v1_appTable_create | create | high | Creates a new table in Base |
| lark_bitable_v1_appTableRecord_create | create | high | Creates a record in Base table |
| lark_bitable_v1_appTableRecord_update | update | high | Updates a record — write operation |
| lark_drive_v1_permissionMember_create | permission | high | Adds collaborator permissions to a doc |
| lark_im_v1_chat_create | create | high | Creates a group chat — bot joins as side effect |
| lark_im_v1_message_create | send | high | Sends a message to user/chat |
| lark_docx_builtin_import | import | high | Imports a markdown file as cloud document |

### SAFE — Read-only, low/medium side-effect risk (11 tools)

| Tool | Category | Side Effect | Safe | Reason |
|---|---|---|---|---|
| lark_bitable_v1_appTableField_list | read | low | ✅ | List fields — read-only |
| lark_bitable_v1_appTable_list | read | low | ✅ | List all tables under app — read-only |
| lark_bitable_v1_appTableRecord_search | read/search | medium | ✅ | Searches existing records only |
| lark_contact_v3_user_batchGetId | read | low | ✅ | Look up user ID by email/mobile |
| lark_docx_v1_document_rawContent | read | medium | ✅ | Reads plain text content of document |
| lark_im_v1_chat_list | read | **none** | ✅ **SELECTED** | Lists groups bot is member of — no params |
| lark_im_v1_chatMembers_get | read | medium | ✅ | Gets group member list — read-only |
| lark_im_v1_message_list | read | medium | ✅ | Gets chat history — read-only |
| lark_wiki_v1_node_search | read/search | medium | ✅ | Searches wiki nodes — read-only |
| lark_wiki_v2_space_getNode | read | medium | ✅ | Gets wiki node information — read-only |
| lark_docx_builtin_search | read/search | medium | ✅ | Searches cloud documents — read-only |

---

## LANE 4: Safe Tool Candidates

| Tool | Required Params | Smoke Query | Recommended |
|---|---|---|---|
| **lark_im_v1_chat_list** | **none** | `{}` | **✅ YES** |
| lark_contact_v3_user_batchGetId | data.emails OR data.mobiles | `{"data": {"emails": ["test@example.com"]}}` | ❌ extra param complexity |
| lark_wiki_v1_node_search | data.query | `{"data": {"query": "test"}}` | ❌ query string needed |
| lark_docx_builtin_search | data.search_key | `{"data": {"search_key": "test"}}` | ❌ search_key + validation |

**Winner**: `lark_im_v1_chat_list` — no required params, purely read-only, zero side effects.

---

## LANE 5: Selected Tool Schema

**Tool**: `lark_im_v1_chat_list`

| Field | Value |
|---|---|
| category | read |
| required_params | **none** |
| optional_params | user_id_type, sort_type, page_token, page_size, useUAT |
| harmless_test_params | `{}` |
| expected_result_type | list of chat objects (or `[]` if bot in no groups) |
| failure_modes | Permission denied → empty list (not error); network timeout → exception |
| timeout_risk | low |

---

## LANE 6: Safe Smoke Decision

| Field | Value |
|---|---|
| safe_smoke_allowed | true |
| external_side_effect_risk | **none** |
| r147c_tool_call_allowed | true |
| r147c_model_call_allowed | false |
| selected_tool | `lark_im_v1_chat_list` |
| rationale | No required params, read-only, zero side effects, returns group membership list or empty list |

---

## LANE 7: R147C Authorization Package

```
recommended_phase: R147C_LARK_READONLY_TOOL_SMOKE
selected_tool: lark_im_v1_chat_list
allowed_tool_calls: 1
model_call_allowed: false
write_tool_allowed: false
params: {}
timeout_seconds: 60

validation_plan:
  1. Lark MCP runtime already started in R147A
  2. Call lark_im_v1_chat_list with empty params {}
  3. Expect: empty list [] or list of chat objects — both are valid success
  4. Verify: no message sent, no group created, no permission changed
  5. Record: tool execution success, response shape, elapsed time

rollback_plan: No rollback needed — read-only tool with no side effects.
               If tool fails, the failure itself is the observation.
```

---

## LANE 8: Unknown Registry Updates

| ID | Description | Fix Applied |
|---|---|---|
| U-lark-tool-risk-matrix | All 19 Lark MCP tools classified: 6 read/low-risk safe, 13 create/send/update/permission/import high-risk | ✅ R147B compiled |
| U-lark-safe-smoke-candidate | lark_im_v1_chat_list is safest smoke target — no required params, read-only, zero side effects | ✅ R147B selected |
| U-lark-tool-schema | lark_im_v1_chat_list: no required params, optional user_id_type/sort_type/page_size | ✅ R147B inspected |
| U-lark-readonly-smoke-readiness | R147C authorized to execute lark_im_v1_chat_list as single read-only smoke call | ✅ R147B decided |
| U-lark-permission-scope | lark_im_v1_chat_list returns groups bot is member of; empty list if none; permission-denied returns empty | ✅ Noted |
| U-lark-builtin-tools | lark_docx_builtin_search (read) and lark_docx_builtin_import (high-risk write) classified separately | ✅ R147B separated |

---

## R147B Classification: PASSED

| Metric | Value |
|---|---|
| code_modified | false |
| db_written | false |
| jsonl_written | false |
| gateway_started | false |
| model_api_called | false |
| tavily_runtime_called | false |
| exa_runtime_called | false |
| external_tool_called | false |
| push_executed | false |
| merge_executed | false |
| safety_violations | [] |

---

## R147B EXECUTION SUCCESS
