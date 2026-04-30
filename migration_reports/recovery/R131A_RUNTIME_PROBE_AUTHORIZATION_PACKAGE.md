# R131A Runtime Probe Authorization Package

**Phase:** R131A — Runtime Probe Authorization Package
**Generated:** 2026-04-30
**Status:** COMPLETED
**Preceded by:** R130
**Proceeding to:** R131B / R131C / R131D (awaiting user authorization)

---

## LANE 0 — Pressure Assessment

| Item | Value |
|------|-------|
| previous_phase | R130 |
| previous_pressure | XXL++ |
| current_recommended_pressure | XXL++ |
| reason | Runtime probe requires explicit authorization; this round packages risk boundaries only. No execution performed. |

---

## LANE 1 — Runtime Probe Unit Decomposition

R131 runtime readiness probe has been decomposed into 5 units:

### Unit A — Model Cheap Ping

| Property | Value |
|----------|-------|
| unit_id | R131A-UNIT-A |
| action | `create_chat_model("minimax-m2.7")` then `model.invoke("hi")` with single `HumanMessage` |
| real API call | ✅ YES — actual MiniMax API call |
| gateway required | ❌ NO — direct model instance invocation (bypasses gateway path) |
| DB write | ❌ NO |
| JSONL write | ❌ NO |
| expected output | `{success: bool, latency_ms: float, error: string\|null, model_name: string}` |
| risk | Low — single minimal message, no tool calls |
| cost | 1 API request |

### Unit B — MCP Config Credential Presence Check

| Property | Value |
|----------|-------|
| unit_id | R131A-UNIT-B |
| action | Check `os.getenv("EXA_API_KEY")` and `os.getenv("LARK_APP_ID")`, `os.getenv("LARK_APP_SECRET")` presence only |
| real MCP call | ❌ NO |
| gateway required | ❌ NO |
| DB write | ❌ NO |
| JSONL write | ❌ NO |
| expected output | `{exa_key_present: bool, lark_app_id_present: bool, lark_app_secret_present: bool}` |
| risk | None — read-only env var presence check |
| cost | Zero |

### Unit C — MCP Server Launch Health

| Property | Value |
|----------|-------|
| unit_id | R131A-UNIT-C |
| action | Attempt to start enabled MCP stdio servers (exa, lark) or test SSE health (tavily) |
| real network/subprocess | ✅ YES — subprocess spawn (stdio) or HTTP GET (SSE) |
| gateway required | ❌ NO — direct MCP SDK or subprocess test |
| DB write | ❌ NO |
| JSONL write | ❌ NO |
| expected output | `{server: string, status: "started"\|"auth_error"\|"network_error"\|"timeout", latency_ms: float}` |
| risk | Medium — subprocess may linger, SSE may expose API key in URL |
| cost | Up to 3 server probes |

### Unit D — Agent astream Smoke

| Property | Value |
|----------|-------|
| unit_id | R131A-UNIT-D |
| action | `make_lead_agent()` + `agent.astream({"messages": [HumanMessage("hi")]}, config)` |
| real LLM call | ✅ YES |
| tool call | ❌ NO (minimal prompt) |
| gateway required | ❌ NO — can be done with mocked RunContext |
| event_store | ❌ NO (disabled for smoke test) |
| DB write | ❌ NO |
| expected output | `{stream_events: bool, first_token_ms: float, complete: bool, error: string\|null}` |
| risk | Medium — full agent chain with middleware |
| cost | 1 agent run |

### Unit E — Tool-Call Observability (Deferred)

| Property | Value |
|----------|-------|
| unit_id | R131A-UNIT-E |
| action | Agent astream with tool call + event_store verification |
| real LLM call | ✅ YES |
| tool call | ✅ YES |
| event_store | ✅ YES |
| requires agent astream | YES — depends on Unit D |
| defer_reason | Requires BP-01 Level 2 (Unit A) and BP-02 runtime (Unit C) to pass first |

---

## LANE 2 — Safety Ordering

### Recommended Execution Order

| Order | Unit | Reason |
|-------|------|--------|
| 1 | **Unit B (env presence check)** | Zero cost, zero risk — confirms credential presence before Unit C |
| 2 | **Unit A (model cheap ping)** | Low risk, single message — verifies BP-01 Level 2 is passable |
| 3 | **Unit C (MCP server health)** | Medium risk — requires user authorization for subprocess/HTTP |
| 4 | **Unit D (agent astream smoke)** | Medium risk — requires Unit A to pass first |
| 5 | **Unit E (tool-call observability)** | Deferred — depends on Unit D |

### Rationale

```
Unit B (zero cost) → Unit A (single ping) → Unit C (MCP runtime) → Unit D (agent smoke) → Unit E (observability)
         ↓                    ↓                    ↓                    ↓
    credentials         BP-01 Level 2        BP-02 runtime       full chain            deferred
    confirmed           verified              verified             verified
```

---

## LANE 3 — Authorization Boundaries

### Unit A Authorization Matrix

| Boundary | Value |
|----------|-------|
| allowed_actions | `create_chat_model()`, `model.invoke(HumanMessage("hi"))` |
| forbidden_actions | `model.stream()`, `model.astream()`, tool calls, multi-turn |
| max_request_count | 1 |
| max_timeout | 30 seconds (external watchdog) |
| secret_handling | No printing of API key — only presence confirmed pre-check |
| cleanup | Model instance released after response |
| stop_condition | Error response (auth/connection) counted as result, not failure |
| cost_estimate | ~100-500 tokens (single minimal turn) |

### Unit B Authorization Matrix

| Boundary | Value |
|----------|-------|
| allowed_actions | `os.getenv("EXA_API_KEY")`, `os.getenv("LARK_APP_ID")`, `os.getenv("LARK_APP_SECRET")` |
| forbidden_actions | Any subprocess, network, file write |
| max_request_count | 0 |
| max_timeout | N/A |
| secret_handling | No printing — only presence (true/false) reported |
| cleanup | None |
| stop_condition | Always passes (absence is valid finding) |
| cost_estimate | Zero |

### Unit C Authorization Matrix

| Boundary | Value |
|----------|-------|
| allowed_actions | `subprocess.Popen` for stdio servers, HTTP GET for SSE health |
| forbidden_actions | Real tool calls, long-running process retention, tool invocation |
| max_server_count | 3 (tavily, exa, lark — enabled servers only) |
| max_timeout_per_server | 15 seconds |
| secret_handling | No printing of keys — key in URL is risk flag only |
| cleanup | All subprocesses killed after probe (Popen.terminate()) |
| stop_condition | First server that starts successfully counted; auth errors are valid results |
| cost_estimate | Negligible — no API calls, just connectivity checks |

### Unit D Authorization Matrix

| Boundary | Value |
|----------|-------|
| allowed_actions | `make_lead_agent()`, `agent.astream()` with minimal prompt |
| forbidden_actions | Multi-step conversation, tool calls in prompt, streaming output capture |
| max_request_count | 1 |
| max_timeout | 60 seconds (external watchdog) |
| event_store | Must be disabled for smoke test |
| secret_handling | None |
| cleanup | Agent instance released |
| stop_condition | Stream starts (not completes) counted as partial pass |
| cost_estimate | ~1000-3000 tokens (single agent turn with middleware) |

### Consolidated Guardrails

| Rule | Status |
|------|--------|
| MiniMax API call count limit | ✅ 1 (Unit A + Unit D combined max 2) |
| No secret printing | ✅ Enforced — only presence (bool) reported |
| No DB writes | ✅ Enforced |
| No JSONL writes | ✅ Enforced |
| No gateway activation | ✅ Not required for Units A-D |
| No persistent MCP process | ✅ Enforced — Unit C kills all subprocesses |
| No code modification | ✅ Enforced |
| No push/merge | ✅ Enforced |

---

## LANE 4 — R131B Task Package

### R131B: Model Cheap Ping Execution

**Status: PACKAGE READY — awaiting user authorization**

```
R131B_MODEL_CHEAP_PING_EXECUTION
authorization_required=true
unit=UNIT-A
```

### Allowed Actions

```python
# R131B — Model Cheap Ping (authorization package)
import os
os.environ['DEER_FLOW_HOST_PATH'] = 'dummy'  # bypass mount check

from deerflow.models.factory import create_chat_model

model = create_chat_model(name='minimax-m2.7', thinking_enabled=False)
response = model.invoke("hi")  # single HumanMessage implicitly
# Capture: latency_ms, error_type, error_message, model_name
```

### Output Schema

```json
{
  "phase": "R131B",
  "status": "passed|failed|error",
  "latency_ms": 1234.5,
  "error": null,
  "model_response_length": 50,
  "api_call_count": 1,
  "cost_estimate_tokens": 100
}
```

### Stop Conditions

- Timeout > 30s → kill and report `timeout`
- Auth error → report `auth_error` (counts as valid finding, not block)
- Connection error → report `connection_error`
- Success → report latency + response preview

### Prohibited

- No streaming
- No tool calls
- No multi-turn
- No DB write
- No JSONL write

---

## LANE 5 — R131C Task Package

### R131C: MCP Runtime Health Probe

**Status: PACKAGE READY — requires separate user authorization**

```
R131C_MCP_RUNTIME_HEALTH_PROBE
authorization_required=true
unit=UNIT-B (env only) + UNIT-C (runtime — separate authorization)
```

### Layer 1: Credential Presence (R131C-Level1)

Always safe, can run with Unit B authorization:

```python
# R131C-L1 — env var presence only
results = {
    "EXA_API_KEY": os.getenv("EXA_API_KEY") is not None,
    "LARK_APP_ID": os.getenv("LARK_APP_ID") is not None,
    "LARK_APP_SECRET": os.getenv("LARK_APP_SECRET") is not None
}
```

### Layer 2: MCP Server Health (R131C-Level2)

Requires separate authorization — subprocess/HTTP:

```python
# R131C-L2 — MCP server health (stdio + SSE)
# For each enabled server:
#   tavily: HTTP GET https://mcp.tavily.com/mcp/ (SSE — may fail fast)
#   exa: subprocess.Popen(['npx.cmd', '-y', 'exa-mcp']) + health check
#   lark: subprocess.Popen(['pnpm.cmd', 'dlx', '@larksuiteoapi/lark-mcp', ...])
# Cleanup: Popen.terminate() on all after 15s timeout
```

### Prohibited

- No real tool calls
- No long-running subprocess retention
- No key printing

---

## LANE 6 — R131D Task Package

### R131D: Agent astream Smoke Plan

**Status: PACKAGE READY — requires Unit A + Unit B results first**

```
R131D_AGENT_ASTREAM_SMOKE_PLAN
depends_on=[R131B_pass, R131C-L1_pass]
prerequisite=R131B must pass or show non-auth error (auth errors OK to proceed)
```

### Planned Action

```python
# R131D — Agent astream smoke
from deerflow.agents.lead_agent.agent import make_lead_agent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

config = RunnableConfig(
    configurable={
        "model_name": "minimax-m2.7",
        "thinking_enabled": False,
        "is_plan_mode": False,
        "agent_name": "lead_agent"
    }
)

agent = make_lead_agent(config=config)
# Mock RunContext with null checkpointer/store/event_store
stream_output = list(agent.astream(
    {"messages": [HumanMessage("hello")]},
    config
))
# Capture: first chunk received, latency, completion
```

### Prerequisite Checks

Before running R131D:
1. R131B passed with success OR non-auth error
2. R131C-L1 completed (credential presence)
3. No active DB write locks

---

## LANE 7 — Decision Prompt

### User Authorization Options

**Default recommendation: A then B, staged execution**

| Option | Units Authorized | Risk | Cost |
|--------|------------------|------|------|
| **A. Authorize R131B only** | Unit A (model cheap ping) | Low | ~100-500 tokens |
| **B. Authorize R131B + R131C-L1** | Unit A + Unit B (env presence) | Low | Zero + ~100 tokens |
| **C. Authorize R131B + R131C** | Unit A + Unit B + Unit C (MCP runtime) | Medium | ~100 tokens + 3 server probes |
| **D. Defer runtime calls** | None — continue TS local chain probes | None | Zero |
| **E. Stop and review** | None | None | Zero |

### Authorization Decision Required

**Please select an option (A/B/C/D/E) to proceed.**

If no selection is made within the session, R131A remains in standby and the next prompt can re-enter at any unit.

---

## Final Report

```
R131A_RUNTIME_PROBE_AUTHORIZATION_PACKAGE_DONE
status=passed
pressure_assessment_completed=true
recommended_pressure=XXL++
runtime_probe_units=[UNIT-A, UNIT-B, UNIT-C, UNIT-D, UNIT-E]
recommended_execution_order=[UNIT-B, UNIT-A, UNIT-C, UNIT-D, UNIT-E]
authorization_matrix_ready=true
r131b_package_ready=true
r131c_package_ready=true
r131d_package_ready=true
model_api_called=false
mcp_runtime_called=false
gateway_activation_allowed=false
db_written=false
jsonl_written=false
code_modified=false
push_executed=false
merge_executed=false
blockers_preserved=true
safety_violations=[]
next_prompt_needed=user_authorization_for_R131B_or_R131C
```

---

## Key Insight: Why Staged Authorization Matters

`★ Insight ─────────────────────────────────────`
**运行时探针的分级授权原则：** 静态探测（R130）可以无条件完成，因为它没有任何副作用。但运行时探针涉及真实 API 调用和真实进程启动，必须按风险分级授权。Unit B（零成本）应该与 Unit A（低风险）打包执行，而 Unit C（subprocess/HTTP 风险）需要单独授权窗口。这样即使某个 unit 失败，失败的上下文已经被记录，不会混淆下一个 unit 的结果。

**MCP server probe 的隐蔽成本：** Unit C 中的 stdio MCP server 启动（exa, lark）需要 `npx.cmd` 或 `pnpm.cmd` 执行——这些是真实的子进程，有启动延迟、可能的挂起和需要清理的 PID。如果多个 server 同时探测，需要外部 watchdog 来强制终止。这不是纯网络探测，而是进程级操作，需要单独授权。
`─────────────────────────────────────────────────`

---

*Generated by Claude Code — R131A (Runtime Probe Authorization Package)*