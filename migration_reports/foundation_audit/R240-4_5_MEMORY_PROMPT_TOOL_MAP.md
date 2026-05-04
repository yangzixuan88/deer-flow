# R240-4.5 Memory / Prompt / Tool Deep Map

## 1. Memory System

### 1.1 Storage Architecture

| Layer | Technology | Path | Scope Key | Enforced By |
|-------|-----------|------|-----------|-------------|
| Primary | FileMemoryStorage (JSON) | `~/.deerflow/memory/{agent_name}.json` | `agent_name` (path segment) | File system only |
| Secondary | Qdrant Vector DB | `memory` collection | `agent_name` (payload field) | Application logic |

**Scope enforcement**: `memory_scope` field exists in ContextEnvelope and ModeStateScope, but **MemoryMiddleware and QdrantStorage do NOT enforce scope boundaries at storage layer**.

### 1.2 Memory Write Path

```
DeerFlow runtime (after_agent)
  → MemoryMiddleware.after_agent()
  → MemoryUpdateQueue.add(conversation)
  → MemoryUpdater.update_memory()
  → LLM generates structured memory facts
  → FileMemoryStorage.save() [JSON]
  → QdrantStorage.upsert() [vector sync]
```

**Key files**:
- `backend/packages/harness/deerflow/agents/memory/middleware.py` — `MemoryMiddleware.after_agent()` queues update
- `backend/packages/harness/deerflow/agents/memory/queue.py` — `MemoryUpdateQueue.add()`
- `backend/packages/harness/deerflow/agents/memory/updater.py` — `MemoryUpdater.update_memory()` calls LLM
- `backend/packages/harness/deerflow/agents/memory/storage.py` — `FileMemoryStorage.save()` + `QdrantStorage.upsert()`

### 1.3 Memory Read Path

```
DeerFlow runtime (before_agent)
  → MemoryMiddleware.before_agent()
  → MemoryUpdater.search(query, agent_name, top_k)
  → FileMemoryStorage.search() [fallback]
  → QdrantStorage.search() [primary, semantic]
  → Retrieved facts injected into agent context
```

**Semantic search**: Qdrant stores `agent_name` as a payload filter. Query retrieves facts scoped to `agent_name`.

### 1.4 Memory Scope Status: PLANNING_ONLY

| Component | Has `memory_scope`? | Enforces It? |
|-----------|---------------------|--------------|
| ContextEnvelope (Python) | Yes — `memory_scope` field | No |
| ContextEnvelope (TypeScript) | Yes — `memoryScope` field | No |
| ModeStateScope | Yes — `memory_scope` field | No |
| MemoryMiddleware | Reads it from envelope | No — queries all agents |
| QdrantStorage | Stores `agent_name` in payload | Partial — filter by agent_name, not ModeStateScope |
| FileMemoryStorage | `agent_name` in path | No — no access control |

**Gap**: Even when `memory_scope` restricts to a specific agent, MemoryMiddleware performs a global semantic search across all agents' memories and returns all results above threshold.

---

## 2. Prompt System

### 2.1 Prompt Templates

| Agent | Path | Dynamic Slots |
|-------|------|--------------|
| Lead Agent | `backend/packages/harness/deerflow/agents/lead_agent/prompt.py` | `{{agent_name}}`, `{{user_name}}`, `{{current_time}}` |
| Memory Agent | `backend/packages/harness/deerflow/agents/memory/prompt.py` | `{{agent_name}}`, `{{session_summary}}` |
| Clarification Middleware | `backend/packages/harness/deerflow/agents/middlewares/clarification_middleware.py` | User-provided |

### 2.2 Prompt Injection Points

- **Lead Agent**: `make_lead_agent()` reads `SOUL.md` from `agents/{agent_name}/SOUL.md`
- **Memory**: `MemoryUpdater` prompt includes retrieved facts + conversation history
- **Clarification**: `ClarificationMiddleware` generates clarifying questions on loop detection

### 2.3 SOUL.md Loading

```
make_lead_agent(configurable["agent_name"])
  → load SOUL.md from agents/{agent_name}/SOUL.md
  → load config from agents/{agent_name}/config.py
  → compile prompt with agent_name/user_name/time
```

Custom agent names are normalized to lowercase with hyphens converted to underscores.

---

## 3. Tool System

### 3.1 Tool Registry (MCP Tools)

**Path**: `backend/packages/harness/deerflow/mcp/tools.py`

Tools are registered via `@tool_registry.register` decorator. Registry is loaded at startup.

### 3.2 Tool Execution Path

```
Agent calls tool
  → MiddlewareChain.before_tool()
  → ToolErrorHandlingMiddleware catches errors
  → LoopDetectionMiddleware checks frequency
  → Actual tool function executes
  → MiddlewareChain.after_tool()
  → Response returned to agent
```

### 3.3 Tool Types

| Type | Executor | Spawn Method |
|------|----------|-------------|
| `mcp__xxx` | MCP Server | `subprocess.Popen` + stdio communication |
| `claude_code` | Claude Code CLI | `subprocess.Popen` + `--print` flag |
| `midscene` | Midscene process | `subprocess.Popen` |
| `ui_tars` | UI-TARS process | `subprocess.Popen` |
| `python` | Inline Python | Direct function call |
| `function` | Python function | Direct function call |

### 3.4 Tool Error Handling

| Middleware | Purpose |
|------------|---------|
| `ToolErrorHandlingMiddleware` | Catches exceptions, returns formatted error to agent |
| `LoopDetectionMiddleware` | Detects repeated tool calls (per-tool-type frequency tracking) |
| `DanglingToolCallMiddleware` | Cleans up incomplete tool call states |

### 3.5 Tool Naming Convention

MCP tools follow `mcp__{server}__{tool_name}` pattern (double underscore). Example: `mcp__filesystem__read_file`.

---

## 4. Cross-Cutting Concerns

### 4.1 Memory-Prompt-Tool Interaction

```
Memory (read) → injected into agent context
       ↓
Prompt rendered with context + memory facts
       ↓
Agent decides tool call
       ↓
Tool executes → result returned to agent
       ↓
Memory (write) → after agent, conversation queued for memory update
```

### 4.2 Governance Integration

Tools do **not** directly write governance. Tool execution outcomes flow through:

```
Tool result → agent reasoning → GovernanceBridge.record_outcome()
```

Via `sandbox_execution_result` outcome type (QueueConsumer) or direct `record_outcome()` (Watchdog).

### 4.3 Mode Router Integration

Mode Router does **not** currently modify tool selection behavior. Future `tool_restriction` field in `ModeDecision` would filter available tools per mode, but this is **not yet implemented**.

---

## 5. Key Gaps and Risks

| ID | Gap | Severity | Blocking R240-5? |
|----|-----|----------|------------------|
| MG-1 | `memory_scope` not enforced at storage layer | High | Yes — scope leakage across modes |
| MG-2 | Qdrant filter by `agent_name` but no `memory_scope` field in vectors | Medium | Yes — semantic search returns cross-scope facts |
| MG-3 | Tool restrictions not integrated with ModeDecision | Medium | No — future work |
| MG-4 | No tool audit trail (who called what, when) | Low | No |
| MG-5 | Prompt templates not versioned | Low | No |
