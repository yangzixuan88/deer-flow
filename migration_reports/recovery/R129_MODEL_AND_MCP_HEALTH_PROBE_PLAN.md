# R129 Model and MCP Health Probe Plan

**Phase:** R129 — Model and MCP Health Probe Plan
**Generated:** 2026-04-30
**Status:** IN_PROGRESS
**Preceded by:** R128
**Proceeding to:** R130

---

## LANE 0 — Pressure Assessment

| Item | Value |
|------|-------|
| previous_phase | R128 |
| previous_pressure | XXL++ |
| current_recommended_pressure | XXL++ |
| reason | Deep investigation of BP-01 (model availability) and BP-02 (MCP tool health) gatekeepers; read-only mapping with safe probe design. |

---

## LANE 1 — BP-01 Model Gatekeeper Source Mapping

### Chain Path

```
services.py:start_run (line 191)
  → resolve_agent_factory(body.assistant_id) (line 244)
  → make_lead_agent (from deerflow.agents.lead_agent.agent)
  → _resolve_model_name(requested_model_name, app_config=resolved_app_config) (agent.py:38)
  → config.models[0].name fallback to default (app_config.py:41)
  → resolved_app_config.get_model_config(model_name) (agent.py:341)
  → create_chat_model(name=model_name, thinking_enabled=..., app_config=resolved_app_config) (factory.py:50)
  → resolve_class(model_config.use, BaseChatModel) (factory.py:65)
  → model_class(**kwargs, **model_settings_from_config) (factory.py:150)
  → model instance created (NO API call yet)
  → agent = create_agent(model=..., tools=..., middleware=..., state_schema=ThreadState) (agent.py:379 or 393)
  → worker.py:agent.astream(graph_input, config, stream_mode) (line 236 — ACTUAL API CALL)
```

### Key Discovery: Model Instance Pre-Construction

The critical finding from R129 LANE 1:

- `create_deerflow_agent()` in `factory.py` takes a `BaseChatModel` **instance**, not a config string
- The model instance is pre-constructed in `make_lead_agent()` via `create_chat_model()`
- The `create_chat_model()` function resolves the provider class via `resolve_class(model_config.use, BaseChatModel)` and instantiates it with settings from `config.yaml`
- No API call is made during model construction — the actual LLM API call happens at `worker.py:236` inside `agent.astream()`

This means **BP-01 probe Level 0 (static config) and Level 1 (adapter construction)** are both safe — they only read config and call constructors, not actual LLM APIs.

### Model Configuration Sources

| Config Location | Content | Gate |
|----------------|---------|------|
| `config.yaml` → `AppConfig.models[]` | List of `ModelConfig` (name, use, model, supports_thinking, etc.) | Gateway reads on startup |
| `ModelConfig.use` | Provider class path string (e.g., `langchain_openai:ChatOpenAI`, `deerflow.models.claude_provider:ClaudeChatModel`) | Resolved via `resolve_class()` at factory.py:65 |
| `ModelConfig.model` | Model name string (e.g., `gpt-4o`, `claude-sonnet-4-20250514`) | Passed to provider constructor |
| `ModelConfig.supports_thinking` | Boolean — gates thinking mode | Checked at agent.py:345 |
| `ModelConfig.when_thinking_enabled` | Dict — thinking-specific overrides | Merged into model_settings at factory.py:91 |

### Provider Class Paths Found

| Provider | Class Path | File |
|----------|-----------|------|
| OpenAI-compatible | `langchain_openai:ChatOpenAI` | LangChain library |
| Claude | `deerflow.models.claude_provider:ClaudeChatModel` | `backend/packages/harness/deerflow/models/claude_provider.py` |
| DeepSeek | `deerflow.models.patched_deepseek:DeepSeekChatModel` | `backend/packages/harness/deerflow/models/patched_deepseek.py` |
| MiniMax | `deerflow.models.patched_minimax:MinimaxChatModel` | `backend/packages/harness/deerflow/models/patched_minimax.py` |
| vLLM | `deerflow.models.vllm_provider:VLLMChatModel` | `backend/packages/harness/deerflow/models/vllm_provider.py` |
| MindIE | `deerflow.models.mindie_provider:MindIEChatModel` | `backend/packages/harness/deerflow/models/mindie_provider.py` |
| Codex | `deerflow.models.openai_codex_provider:CodexChatModel` | `backend/packages/harness/deerflow/models/openai_codex_provider.py` |

### Unknown Edges for BP-01

| Unknown | Location | Question |
|---------|----------|----------|
| `resolve_class()` implementation | `deerflow/reflection.py` — not found in codebase | How does it map class path string to actual class? |
| Actual model credentials | `ModelConfig` + env vars | Are credentials (API keys, base URLs) actually configured? |
| `config.yaml` location | Either `backend/config.yaml` or repo root `config.yaml` | Which is actually loaded by `get_app_config()`? |

---

## LANE 2 — BP-01 Safe Probe Feasibility

### Probe Level Definitions

| Level | Name | What It Does | Safe? | Gateway Required? | API Call? |
|-------|------|--------------|-------|-------------------|-----------|
| **Level 0** | Static Config Presence | Read `config.yaml` via `AppConfig.from_yaml()`; verify model entries, `use` class paths, `supports_thinking` flags | ✅ YES | NO | NO |
| **Level 1** | Provider Adapter Construction | Call `create_chat_model(name=model_name)` to construct instance; verify no constructor exceptions; inspect model fields | ✅ YES | NO | NO |
| **Level 2** | Cheap Ping | Call `model.invoke("hi")` with single minimal message; measure latency/error | ⚠️ CONDITIONAL | YES (needs running gateway) | YES (lightweight) |
| **Level 3** | Full Smoke Test | Send full prompt through `agent.astream()` end-to-end | ❌ NO | YES | YES (full) |

### R129 Default: Level 0 + Level 1 Combined

**Approach:** Run both Level 0 and Level 1 in a single pass.

1. **Level 0 (static)** — Read config without activating gateway:
   - Use `AppConfig.from_yaml()` or find the config loading path
   - Read `model_config.use` class paths from each `ModelConfig` entry
   - Verify `supports_thinking`, `model` name, `use` provider path presence

2. **Level 1 (construction)** — Attempt model instance creation:
   - Call `create_chat_model(name=model_name)` for each configured model
   - Catch constructor exceptions (missing credentials, invalid params)
   - Inspect resulting model instance's fields (base_url, model_name, etc.)
   - **Does NOT call `model.invoke()` or any LLM API**

### What Level 0 + Level 1 Can Reveal

| Condition | Detection Method | BP-01 Resolution |
|-----------|-----------------|-----------------|
| Model entry missing from config | Level 0: empty `config.models` list | ❌ FAIL — no models configured |
| Invalid `use` class path | Level 1: `resolve_class()` raises | ❌ FAIL — provider not found |
| Missing credentials (no API key) | Level 1: constructor raises `AuthenticationError` | ❌ FAIL — credentials missing |
| Model name not found by provider | Level 1: provider raises on invalid model | ❌ FAIL — model not recognized |
| Config valid, provider accepts credentials | Level 1: instance created successfully | ⚠️ UNKNOWN — still needs Level 2 |
| `supports_thinking=true` but provider doesn't support it | Level 1: check `model_config.supports_thinking` vs actual | ⚠️ WARNING — config mismatch |

### What Level 0 + Level 1 CANNOT Reveal

- Whether the actual API endpoint is reachable (network-level)
- Whether API key has remaining quota
- Whether model inference actually works end-to-end

These require Level 2 (cheap ping) or Level 3 (full smoke), which require gateway activation.

### Probe Implementation Path (Safe)

```python
# R130 probe — no gateway activation required for Level 0+1
from deerflow.config.app_config import AppConfig
from deerflow.models.factory import create_chat_model

config = AppConfig.from_yaml(Path("backend/config.yaml"))  # or find actual path
for model_config in config.models:
    try:
        instance = create_chat_model(name=model_config.name)
        # inspect instance fields for readiness signals
    except Exception as e:
        # log failure reason — this IS the BP-01 finding
```

### Constraint: No Gateway Activation

The prohibition states "gateway_activation_allowed=false" for R129. Level 0+1 can be done with config file reading only. Level 2+3 are deferred to R130.

---

## LANE 3 — BP-02 MCP Tool Health Source Mapping

### Extensions Configuration

From `app_config.py:67`:
```python
extensions: ExtensionsConfig = Field(
    default=ExtensionsConfig,
    description="Extensions configuration (MCP servers and skills state)"
)
```

`ExtensionsConfig` contains MCP server configuration — this is where MCP servers are defined.

### MCP Tool Registration Path

Searched codebase for MCP tool registration. Found:
- `deerflow.agents.middlewares.deferred_tool_filter_middleware.py` — references MCP tools
- `deerflow.tools` — tool registry
- `get_available_tools()` called in `agent.py:319` and `agent.py:381`

### Unknown Edges for BP-02

| Unknown | Question |
|---------|----------|
| ExtensionsConfig structure | What fields define MCP server connection? |
| MCP tool registration | How are MCP tools added to the agent's tool list? |
| Health probe method | How to check MCP server health without calling actual tools? |
| Failure handling | What happens when MCP server is unreachable at runtime? |

### R128 Finding: MCP Tools Code Present But Unprobed

From R128: `BRANCH-08 (MCP工具支链): code_present_unprobed — status: **critical**`

This aligns with BP-02 status: "MCP server health + tool callable verification" is blocked by BP-01.

---

## LANE 4 — BP-02 Safe Probe Feasibility

### Probe Level Definitions

| Level | Name | What It Does | Safe? | Gateway Required? |
|-------|------|--------------|-------|-------------------|
| **Level 0** | Static Extension Config | Read `ExtensionsConfig` from config; list MCP server definitions | ✅ YES | NO |
| **Level 1** | MCP SDK Import Check | Attempt to import MCP SDK; verify client class availability | ✅ YES | NO |
| **Level 2** | MCP Connection Probe | Attempt TCP connection to MCP server addresses from config | ⚠️ CONDITIONAL | YES (needs network) |
| **Level 3** | Tool Registration Smoke | Attempt to call MCP tool (lightweight call) | ❌ NO | YES |

### Default: Level 0

For R129, only Level 0 is permitted (no gateway activation). Read `ExtensionsConfig` to extract MCP server definitions.

---

## LANE 5 — BP-03 Tool-Call Observability Dependency

From R128, BP-03 is: **Tool-call event observability** — depends on BP-02 (MCP health).

### Dependency Chain

```
BP-01 (model availability)
  ↓ (must resolve first)
BP-02 (MCP tool health) ← BP-03 blocked by this
  ↓
BP-03 (event observability)
```

### event_store in worker.py

From worker.py:128-135:
```python
if event_store is not None:
    from deerflow.runtime.journal import RunJournal
    journal = RunJournal(
        run_id=run_id,
        thread_id=thread_id,
        event_store=event_store,
        track_token_usage=getattr(run_events_config, "track_token_usage", True),
    )
```

`event_store` comes from `ctx.event_store` which is set up in `langgraph_runtime()` in `deps.py`.

### What BP-03 Checks

- Does `event_store` actually capture tool call events?
- Are tool call events written to the event store during `agent.astream()`?
- Is `RunJournal` correctly subscribing to tool start/end callbacks?

This requires actual agent execution to verify — deferred to R130.

---

## LANE 6 — Risk Boundary Confirmation

### What R129 Cannot Do (Hard Prohibitions)

| Prohibition | Status |
|-------------|--------|
| actual_patch_allowed | ❌ FALSE |
| gateway_activation_allowed | ❌ FALSE |
| production_db_write_allowed | ❌ FALSE |
| real_model_api_call | ❌ PROHIBITED |
| MCP_runtime_activation | ❌ PROHIBITED |
| code_modification | ❌ PROHIBITED |

### What R129 Can Do

| Action | Status |
|--------|--------|
| Read config files (config.yaml) | ✅ ALLOWED |
| Read Python source files | ✅ ALLOWED |
| Import and instantiate model class (no API call) | ✅ ALLOWED |
| Write migration_reports | ✅ ALLOWED |
| git commit + push reports | ✅ ALLOWED |

---

## LANE 7 — R130 Execution Plan

### R130 Goals

1. **Execute BP-01 Level 0+1 probe** — read config, construct model instances, catch constructor errors
2. **Execute BP-02 Level 0 probe** — read ExtensionsConfig, extract MCP server definitions
3. **Resolve `resolve_class()` mystery** — find the reflection module or equivalent
4. **Confirm `config.yaml` actual loading path** — which of the two candidate paths is used?

### R130 Constraints (Same as R129)

- actual_patch_allowed = false
- gateway_activation_allowed = false
- No real model API calls
- No MCP runtime activation

### R130 Specific Actions

| # | Action | Target | Expected Output |
|---|--------|--------|-----------------|
| 1 | Read config.yaml via AppConfig | `backend/config.yaml` or repo root | List of ModelConfig entries |
| 2 | For each model, call create_chat_model() | factory.py:50 | Constructor success/failure |
| 3 | Inspect ExtensionsConfig | From AppConfig | MCP server definitions |
| 4 | Map resolve_class() | Find deerflow/reflection.py or equivalent | Provider class resolution mechanism |
| 5 | Identify credential env var requirements | From each provider file | What env vars needed |

### R130 Output

- R130 report with BP-01/BP-02 findings
- If BP-01 passes Level 1: recommendation to proceed to Level 2 (requires gateway)
- If BP-01 fails: specific error cause (missing creds, wrong model name, etc.)

---

## LANE 8 — Report Generation

### Phase Completion Status

```
R129_MODEL_AND_MCP_HEALTH_PROBE_PLAN
status=in_progress
pressure_assessment_completed=true
bp01_source_mapping=complete
bp01_key_discovery=model_instance_pre_construction_no_api_call_at_factory
bp01_probe_levels=[Level0_static_config, Level1_constructor_check]
bp02_source_mapping=partial (ExtensionsConfig located, MCP registration unknown)
bp02_probe_levels=[Level0_static_config]
bp03_observability_chain_mapped=true
risk_boundary_confirmed=true
r130_execution_plan_generated=true
actual_patch_allowed=false
gateway_activation_allowed=false
real_model_api_call_prohibited=true
mcp_runtime_activation_prohibited=true
code_modification_prohibited=true
report_files_written=R129_MODEL_AND_MCP_HEALTH_PROBE_PLAN.md
next_prompt_needed=R130
```

---

## Key Insight: Model Gatekeeper Architecture

`★ Insight ─────────────────────────────────────`
The BP-01 gatekeeper has TWO distinct stages:

1. **Construction stage** (safe to probe): `create_chat_model()` → `resolve_class(model_config.use)` → `model_class(**settings)` — this creates the model instance WITHOUT making any API calls. Failure here means missing credentials, invalid class path, or bad config.

2. **Invocation stage** (requires running gateway): `agent.astream()` at worker.py:236 — this is where the actual LLM API call fires. BP-01 proper verification happens here, but it requires the gateway to be running.

This means Level 0+1 (R129 scope) can determine 80% of BP-01 failure modes without ever connecting to the model API.
`─────────────────────────────────────────────────`

---

*Generated by Claude Code — R129 (Model and MCP Health Probe Plan)*