# R240-4.5 Foundation Readiness Report

**Generated**: 2026-04-24
**Scope**: Full project discovery — 8 output files
**Verdict**: **B — 需要 Truth/State Contract（需要先建立真值/状态契约）**

---

## Executive Summary

DeerFlow has two completely independent request paths that bypass M01/M04 orchestration entirely (Gateway HTTP API and channel integrations). Mode Router must therefore understand both paths to be effective. The current governance state system conflates **actual outcomes** (already happened) with **predicted/success state** (expected to happen), creating semantic confusion that will corrupt Mode Router's state tracking. Memory scope enforcement is planning-only. Asset is an event-byproduct with no bidirectional reference. RTCM has an independent state machine invisible to Mode Router.

**Verdict: B. Mode Router implementation requires a Truth/State Contract first.**

---

## Q1: Gateway bypass M01/M04 — Mode Router covers both?

**Answer**: **YES — but must handle two independent paths.**

| Entry Point | Path | Mode Router Coverage |
|-------------|------|----------------------|
| `frontend_http` | Frontend → LangGraph SDK → Gateway → DeerFlow | **NOT covered** — no ModeDecision injected |
| `channel_*` (Feishu/Slack/Telegram/Discord) | Channel → MessageBus → ChannelManager → Gateway → DeerFlow | **NOT covered** — no ModeDecision injected |
| `gateway_thread_runs` | POST /api/threads/{id}/runs → Gateway → DeerFlow | **NOT covered** — no ModeDecision injected |
| `gateway_stateless_runs` | POST /api/runs/stream → Gateway → DeerFlow | **NOT covered** — no ModeDecision injected |
| `mcp_api_server` | POST /api/v1/orchestrate → M01 | **Covered** — M01 Orchestrator gets ModeDecision |

**Critical finding**: 13 of 16 entry points bypass M01 entirely. ModeDecision is injected in `services.py:start_run()` (R240-5), but **no downstream component reads it yet**.

**Architecture implication**: Mode Router's `mode_restriction` and `allowed_states` must be enforced at the Gateway layer (services.py), not just M01. Currently the field is injected but never acted upon.

---

## Q2: Governance actual vs. predicted vs. success state?

**Answer**: **CONFLATED — critical semantic confusion.**

In `governance_bridge.py` `record_outcome()`, all outcomes are stored with `outcome_type` string + `outcome` dict. But the system uses the same field names for fundamentally different concepts:

| Field | Used for "actual" | Used for "predicted" | Used for "success_state" |
|-------|-------------------|----------------------|--------------------------|
| `candidate_id` | Source demand ID (actual execution) | Proposed candidate (predicted) | N/A |
| `score` | Binding quality (actual) | Expected quality (predicted) | N/A |
| `status` | "executed" (actual) | "proposed" (predicted) | N/A |

### The Core Problem

`governance_state.json` stores **all outcomes in one array** regardless of temporal stage:

```
Decision made (predicted)
  → UC executes (actual)
  → Outcome recorded (actual)
```

But Mode Router needs to track:
1. **What we expect** (predicted state)
2. **What actually happened** (actual state)
3. **Whether they match** (success state)

Currently: `governance_trace_id` carries M01's `requestId`, but M04's `task_id` (which equals `request_id`) is NOT carried forward to governance. Mode Router cannot correlate predicted vs. actual without this lineage.

**Blocking issue**: The governance outcome record conflates "this candidate was proposed" with "this candidate was executed and succeeded/failed". Mode Router cannot compute success_rate without disambiguating these.

---

## Q3: Memory scope enforcement at storage layer?

**Answer**: **PLANNING_ONLY — not enforced.**

`memory_scope` field exists in:
- `ContextEnvelope.memory_scope` (Python)
- `ContextEnvelopeLike.memoryScope` (TypeScript)
- `ModeStateScope.memory_scope`

But enforcement is **not implemented** at storage layer:

| Component | Reads `memory_scope`? | Enforces It? |
|-----------|----------------------|--------------|
| MemoryMiddleware | Yes — reads from envelope | No — queries all agents |
| QdrantStorage | `agent_name` as payload filter | Partial — filters by agent_name, not ModeStateScope |
| FileMemoryStorage | `agent_name` in path | No — no access control |

**What happens**: Even when `memory_scope = ["memory_agent"]`, MemoryMiddleware performs a global semantic search across ALL agents' memories and returns all results above threshold. No scope boundary is enforced.

**Mode Router impact**: `mode.memory_scope` recommendations in ModeDecision will not be enforced until QdrantStorage and MemoryMiddleware are updated to filter by `memory_scope` field.

---

## Q4: Asset as first-class entity or event byproduct?

**Answer**: **EVENT BYPRODUCT — not a first-class entity.**

Assets emerge from governance outcome events. There is **no bidirectional reference** between `asset_promotion` outcome records and the `asset_registry`:

```
Governance outcome (asset_promotion)
  ↓ DPBS reads outcome_records
Asset candidate derived
  ↓ bind_platform()
Asset bound → binding_report.json written
  ✗ No reference back to governance_state.json
```

**Consequences**:
1. Asset lineage is opaque — cannot trace back to governance decision
2. Asset orphaning possible if governance outcome is lost
3. No asset deregistration path — assets accumulate forever
4. Mode Router cannot restrict asset access by mode — assets are globally shared

**Mode Router impact**: `mode.asset_restriction` is impossible to implement because assets have no mode affinity. All assets are accessible in all modes.

---

## Q5: RTCM state machine vs. Mode Router state machine?

**Answer**: **TWO INDEPENDENT STATE MACHINES — no integration.**

RTCM has its own state machine (`ACTIVE → PAUSED/WAITING_FOR_USER → ARCHIVED/FAILED`) completely independent of Mode Router's state tracking.

| Dimension | RTCM | Mode Router |
|-----------|------|-------------|
| State machine | Own session state | Tracks mode per-context |
| Entry trigger | Keyword (开会/启动rtc) | M01/MCP orchestration |
| Bypass M01/M04 | Yes | Yes (Gateway path) |
| Writes governance | Via Feishu→Channel→DeerFlow | Via M01 context |
| threadId | rtcm thread (different from Gateway) | ContextEnvelope.thread_id |

**Critical conflicts**:
- RTCM activated → Mode Router has no awareness → mode is unknown
- RTCM intercepts user messages → Mode Router state not updated
- RTCM session ID (`rtcm_session_id`) not in ContextEnvelope → lineage broken

**Mode Router impact**: Mode Router cannot track RTCM sessions. If RTCM is active, Mode Router's `current_mode` is stale/invalid for that context.

---

## Q6: UC pipeline governance backflow correctness?

**Answer**: **STRUCTURALLY CORRECT — but semantic confusion persists.**

UC pipeline governance backflow is structurally sound:

```
governance_state.json (demands)
  → UC U0-U8 (observation, experiment, approval)
  → UC backflow → governance_bridge.record_outcome()
  → QueueConsumer reads experiment_queue.json
  → sandbox_execution_result → governance_bridge.record_outcome()
  → Watchdog → governance_bridge.record_outcome()
```

**Issue**: Governance outcome types (`asset_promotion`, `sandbox_execution_result`, `upgrade_center_execution`, `doctrine_drift_detected`) are all **actual outcomes**. But Mode Router needs **predicted outcomes** (what UC *plans* to execute) vs **actual outcomes** (what *actually* happened) to compute success rates.

**The disconnect**: UC's `experiment_pool.json` and `approval_backlog.json` contain predicted state. These are NOT written to governance_state.json — only the actual outcomes after execution. Mode Router cannot compare predicted vs. actual without reading UC state files directly.

---

## Q7: Same-name ID conflicts between systems?

**Answer**: **YES — 4 collision groups identified.**

| ID Name | Systems Using It | Collision Severity |
|---------|------------------|-------------------|
| `thread_id` | deerflow_thread_state, frontend_thread_state, rtcm_session_state | **HIGH** — RTCM rtcm thread ≠ Gateway thread_id |
| `session_id` | m01_request_state, rtcm_session_state | **HIGH** — M01 sessionId ≠ RTCM rtcm_session_id |
| `task_id` | m04_task_state, governance_state | **MEDIUM** — M04 task_id = request_id; Governance uses task_id differently |
| `request_id` | m01_request_state, governance_state (as governance_trace_id) | **MEDIUM** — M01 requestId carried as governance_trace_id |

**Mode Router impact**: ContextEnvelope carries all four IDs, but components downstream do not consistently propagate them. M04's `task_id` (= `request_id`) does NOT flow to governance outcome — only M01's `requestId` (as `governance_trace_id`) does.

---

## Q8: Components with zero test coverage?

**Answer**: **Several critical paths untested.**

| Component | Path | Test Status |
|-----------|------|-------------|
| GovernanceBridge.record_outcome() | `backend/app/m11/governance_bridge.py` | **NOT directly tested** |
| DPBS discovery_engine() | `backend/app/m07/asset_system.py` | **NOT directly tested** |
| QueueConsumer.write_governance_outcome() | `backend/app/m11/queue_consumer.py` | **NOT directly tested** |
| MemoryMiddleware.before_agent() | `backend/packages/harness/deerflow/agents/memory/middleware.py` | **NOT directly tested** |
| MemoryUpdater.update_memory() | `backend/packages/harness/deerflow/agents/memory/updater.py` | **NOT directly tested** |
| ModeDecision injection (services.py) | `backend/app/gateway/services.py` | **NOT directly tested** |
| R240-5 mode_router module | `backend/app/gateway/mode_router.py` | **NOT directly tested** |

**All 11 tests in `test_context_envelope_smoke.py` pass** (R240-4). But ModeDecision enforcement, governance backflow, and memory scope enforcement have zero test coverage.

---

## Summary: 3 Critical Blockers for R240-5

| Blocker | Description | Fix Required |
|---------|-------------|--------------|
| **B1: Governance semantic confusion** | Actual/predicted/success_state conflated in outcome records | Truth/State Contract: define separate fields for predicted vs. actual outcomes |
| **B2: Memory scope not enforced** | `memory_scope` exists but MemoryMiddleware queries globally | Enforce scope in MemoryMiddleware + QdrantStorage filter |
| **B3: RTCM invisible to Mode Router** | RTCM independent state machine, no ContextEnvelope integration | Add `rtcm_session_id` to ContextEnvelope, track RTCM in ModeDecision |

---

## Recommendation

**Do not proceed with R240-5 Mode Router implementation until:**

1. **Truth/State Contract** (R240-6): Define clear semantics for actual vs. predicted vs. success state in governance outcomes. Add `predicted_outcome` vs. `actual_outcome` separation.

2. **Memory Scope Enforcement** (R240-7): Update MemoryMiddleware and QdrantStorage to enforce `memory_scope` field from ContextEnvelope.

3. **RTCM Integration** (R240-8): Add `rtcm_session_id` to ContextEnvelope; update ModeDecision to track RTCM state.

**After** these three foundations are laid, Mode Router implementation (R240-5) can proceed with clear semantics and testable contracts.

---

## Files Generated

| # | File | Status |
|---|------|--------|
| 1 | `R240-4_5_ENTRY_GRAPH.json` | ✅ Created |
| 2 | `R240-4_5_INVOKE_GRAPH.json` | ✅ Created |
| 3 | `R240-4_5_STATE_GRAPH.json` | ✅ Created |
| 4 | `R240-4_5_RUNTIME_ARTIFACT_GRAPH.json` | ✅ Created |
| 5 | `R240-4_5_MEMORY_PROMPT_TOOL_MAP.md` | ✅ Created |
| 6 | `R240-4_5_ASSET_DEEP_MAP.md` | ✅ Created |
| 7 | `R240-4_5_RTCM_DEEP_MAP.md` | ✅ Created |
| 8 | `R240-4_5_FOUNDATION_READINESS.md` | ✅ Created |
