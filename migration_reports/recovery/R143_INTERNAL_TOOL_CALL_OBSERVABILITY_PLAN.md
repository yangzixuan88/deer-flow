# R143: Internal Tool Call Observability Plan

## Status: PLANNING COMPLETE

## Preceded By: R142C_RESULT_PERSISTENCE_PATCH
## Proceeding To: R144_INTERNAL_TOOL_CALL_OBSERVABILITY_SMOKE

## Pressure: XXL

---

## Summary

R143 is a read-only design phase (no code execution, no model calls, no MCP startup). Goal: map the tool binding path, MCP lazy-init boundary, and internal no-op tool design for the R144 authorization package. All findings are derived from code inspection across 6 key files.

**Primary output**: `run_r144.py` — the internal tool call smoke harness that injects `echo_tool` via `create_deerflow_agent(tools=[echo_tool])` without triggering MCP.

---

## LANE 3: MCP Lazy Init Boundary Mapping

| Check | Result |
|---|---|
| MCP init entry point | `get_available_tools()` [tools.py:36] |
| Cache lookup | `get_cached_mcp_tools()` [cache.py:82] |
| Lazy init trigger | `initialize_mcp_tools()` [cache.py:56] |
| Actual MCP client | `get_mcp_tools()` [tools.py:57] → `MultiServerMCPClient(servers_config).get_tools()` |
| Can disable via config | ✅ Yes |
| Disable mechanism | No enabled servers in `extensions_config.json` OR `include_mcp=False` in `get_available_tools()` |
| Can avoid by injecting tools | ✅ Yes |
| Avoidance mechanism | `create_deerflow_agent(tools=[echo_tool])` [factory.py:61] bypasses `get_available_tools()` entirely |
| MCP will start for internal tool smoke | ❌ No — not if tools are injected directly |
| Risk | **LOW** |

### Key Finding: Two Distinct Tool Paths

```
Path 1 (MCP-dependent): make_lead_agent → get_available_tools → get_cached_mcp_tools → MCP init
Path 2 (Direct injection): create_deerflow_agent(tools=[...]) → deduplicates + appends to feature tools
```

`make_lead_agent()` at [agent.py:317](backend/packages/harness/deerflow/agents/lead_agent/agent.py) has **NO** `tools=` parameter. Tools come from internal `get_available_tools()` call at lines 395-400.

`create_deerflow_agent()` at [factory.py:61](backend/packages/harness/deerflow/agents/factory.py) **DOES** accept `tools: list[BaseTool] | None = None`. Deduplication logic at lines 119-136 ensures user-injected tools take priority over feature-injected tools.

### `get_available_tools()` MCP Trigger Path

```
tools.py:36 get_available_tools(include_mcp=True, ...)
  → tools.py:113 if include_mcp:
  → cache.py:82 get_cached_mcp_tools()
    → cache.py:103 if not _cache_initialized:
    → cache.py:56 initialize_mcp_tools()
      → tools.py:57 get_mcp_tools()
        → tools.py:120 MultiServerMCPClient(servers_config).get_tools()
          → MCP server connections (stdio, HTTP, SSE)
```

### Disabling MCP

MCP can be disabled via:
1. `include_mcp=False` in `get_available_tools()` call — but `make_lead_agent` has no parameter to control this
2. No enabled servers in `extensions_config.json` — MCP init becomes a no-op
3. **Best approach**: Inject tools directly via `create_deerflow_agent(tools=[...])` — completely bypasses `get_available_tools()`

### MCP Config Reading Pattern

Both `get_available_tools()` [tools.py:118] and `get_mcp_tools()` [tools.py:73] use `ExtensionsConfig.from_file()` directly rather than the cached singleton `get_extensions_config()`. This ensures they read the latest config from disk, but also means they can trigger MCP initialization even when MCP is nominally "disabled" in the singleton.

---

## LANE 5: Tool Event Surface Mapping

| Surface | Location | What appears |
|---|---|---|
| values snapshot | `channel_values['messages']` after tool node | `AIMessage` with `.tool_calls` list |
| SSE event type | `worker.py:485` `_lg_mode_to_sse_event` | `'messages'` (maps from LangGraph `'messages'` mode) |
| StreamBridge publish | `worker.py:241` `bridge.publish(run_id, 'messages', serialize(chunk, mode='messages'))` | Serialized message tuples |
| RunStore persistence | `worker.py:341-344` `journal.get_completion_data()` + `update_run_completion(result=...)` | Token usage + serialize_channel_values snapshot |
| RunRecord.result | `worker.py:328` `serialize_channel_values(channel_values)` captured in finally block | Dict with keys: `messages`, `thread_data`, `title` |
| RunEventStore | `worker.py:185` journal registered as callback | `on_llm_end` / `on_chain_start_end` events |

### Result Field Keys (from R142C)

After a successful run with a tool call, `channel_values` has:
```python
{
  "messages": [...],      # Full message history including tool calls/responses
  "thread_data": {...},   # Thread-scoped data
  "title": "..."          # Auto-generated or user-provided title
}
```

### Tool Call Detection Points

1. **`AIMessage.tool_calls`** — present in message after LLM requests tool invocation
2. **`ToolMessage`** — present after tool completes, in same message sequence
3. **`run_record.result['messages']`** — contains both AIMessage with tool_calls and ToolMessage responses

---

## LANE 6: Patch/Harness Strategy Options

### Option A: Internal No-op Tool via `create_deerflow_agent` ✅ RECOMMENDED

**Description**: Inject a simple built-in `echo_tool` via `create_deerflow_agent(tools=[echo_tool])`.

**Pros**:
- No MCP server connections triggered
- No `get_available_tools()` call reached
- Uses the correct agent factory that accepts `tools=` directly
- Clean, isolated test of tool call → result snapshot path

**Cons**:
- `make_lead_agent()` cannot be used for this test (no tools= parameter)

**Implementation**:
```python
# In run_r144.py
echo_tool = # define simple echo tool
agent = create_deerflow_agent(
    model=create_chat_model(name="minimax-m2.7"),
    tools=[echo_tool],
    ...
)
# Then use agent.astream() directly
```

### Option B: Disable MCP via extensions_config.json

**Status**: Rejected

**Reason**: Requires config file manipulation, cannot fully suppress MCP lazy init in all code paths, and is more invasive than Option A.

### Option C: Use `include_mcp=False` in `get_available_tools`

**Status**: Not applicable

**Reason**: `make_lead_agent()` has no parameter to control `include_mcp` — it's hardcoded to True internally.

---

## LANE 7: R144 Authorization Package

### Patch Files

**None** — R144 is a smoke test harness, not a code modification phase.

### Harness Files

1. `run_r144.py` — Internal tool call smoke harness

### Constraints

| Constraint | Limit |
|---|---|
| model_api_calls | 1 |
| tool_calls | 1 |
| mcp_runtime | false |
| db_writes | limited to test artifacts |

### Echo Tool Design

```python
class EchoToolInput(BaseModel):
    text: str = Field(description="Text to echo back")

def echo_tool(text: str) -> str:
    """Echo the input text back as output. Used for internal smoke testing."""
    return f"echo: {text}"

echo_schema = StructuredTool.from_function(
    name="echo",
    description="Echo the input text back as output. For internal smoke testing.",
    coroutine=echo_tool,
    args_schema=EchoToolInput,
)
```

### R144 Execution Flow

```
1. Create thread via POST /api/threads
2. Build agent via create_deerflow_agent(tools=[echo_tool])
3. Run agent with input "Call the echo tool with: hello"
4. Poll GET /runs/{run_id} for completion
5. Verify:
   - status = success
   - result['messages'] contains AIMessage with tool_calls (echo)
   - result['messages'] contains ToolMessage with echo response
   - run_record.result is non-null
```

---

## Unknown Registry

| ID | Description | Priority |
|---|---|---|
| U-mcp-init-in-get_available_tools | `get_available_tools()` [tools.py:113] calls `get_cached_mcp_tools()` which triggers MCP lazy init if any servers are enabled | medium |
| U-make_lead_agent-tools-inaccessible | `make_lead_agent()` [agent.py:317] has no `tools=` parameter — tools come only from internal `get_available_tools()` call | high |
| U-tools_bound_count-0-reason | R139 logged `tools_bound_count=0` because no `ToolConfig` entries exist in the harness-configured minimal AppConfig | medium |

---

## Key Insight

> `create_deerflow_agent(tools=[echo_tool])` [factory.py:61] is the correct path for internal smoke testing — it accepts tools directly, deduplicates against feature-injected tools, and never reaches `get_available_tools()` when tools are injected.

---

## R143 PLANNING COMPLETE

```
mcp_boundary=low
mcp_init_entry=get_available_tools → get_cached_mcp_tools → initialize_mcp_tools
can_disable_via_config=true
can_avoid_by_injecting_tools=true
mcp_will_start_for_internal_tool_smoke=false
avoidance_mechanism=create_deerflow_agent(tools=[echo_tool])
key_finding=Two paths: make_lead_agent (MCP-dependent) vs create_deerflow_agent (direct tools injection)
recommended_next_phase=R144_INTERNAL_TOOL_CALL_OBSERVABILITY_SMOKE
patch_files=[]
harness_files=[run_r144.py]
```