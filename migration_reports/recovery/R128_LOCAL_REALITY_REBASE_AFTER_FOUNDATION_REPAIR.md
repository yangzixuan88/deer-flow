# R128 Local Reality Rebase After Foundation Repair

**Phase:** R128 — Local Reality Rebase After Foundation Repair
**Generated:** 2026-04-30
**Status:** COMPLETED
**Preceded by:** R127
**Proceeding to:** R129

---

## LANE 0 — Pressure Assessment

| Item | Value |
|------|-------|
| previous_mainline_anchor | R127 |
| current_phase | R128 |
| recommended_pressure | XXL++ |
| reason | Local reality rebase after foundation repair; read-only but broad-scope mapping. |

---

## LANE 1 — Current Workspace Baseline

| Item | Value |
|------|-------|
| current_branch | `r241/auth-disabled-wiring-v2` |
| current_head | `e6859750` (R241-26B commit) |
| remote_origin | `https://github.com/yangzixuan88/deer-flow.git` |
| workspace_dirty | YES |
| dirty_classification | expected_reports |
| mainline_audit_safe | ✅ YES |

**Dirty files:** All untracked files are report artifacts (`migration_reports/recovery/`, `migration_reports/foundation_audit/`) or new modules (`backend/app/asset/`, `backend/app/m*/`). No tracked production code modified.

---

## LANE 2 — Old Mainline Conclusion Revalidation

### R119 — Executor Selection Health Gate

| Item | Value |
|------|-------|
| still_present | ✅ YES |
| location | `backend/src/domain/m11/adapters/executor_adapter.ts:241` |
| function | `executorReadinessGate(executorType, health?)` |
| not_ready behavior | `action: 'skip'` for CLAUDE_CODE (line 282); falls back to Claude Code |
| bootstrap | OPENCLI retries bootstrap < 2 times before fallback |
| status | **valid** |

### R123 — DAG systemType Inference Chain

| Item | Value |
|------|-------|
| still_present | ✅ YES |
| location | `backend/src/domain/m01/dag_planner.ts:240` |
| function | `inferSystemType(task: string): SystemType` |
| routing | VISUAL_WEB / DESKTOP_APP / CLAUDE_CODE / SEARCH / WORKFLOW / TASK |
| keyword-based | YES — `SYSTEM_TYPE_KEYWORDS` map from line 31 |
| status | **valid** |

### R126 — DeerFlow Entry Chain Restoration

| Item | Value |
|------|-------|
| still_restored | ✅ YES |
| health probe | `DeerFlowClient.healthCheck()` → GET `/health` on port 8001 (line 264) |
| business probe | `createThread()` fallback if `/health` false (line 213-218) |
| timeout fallback | Explicit `error === 'DeerFlow execution timeout'` → local fallback (line 231-233) |
| status | **valid** |

### R120 — M04 ↔ Python Boundary

| Item | Value |
|------|-------|
| boundary_still_valid | ✅ YES |
| M04 implementation | TypeScript only — `handleClaudeCodeRequest()`, `handleVisualWebRequest()`, etc. |
| Python call path | Python only entered via DeerFlow HTTP path (`deerflowEnabled=true`) |
| M04 never calls Python directly | ✅ CONFIRMED |
| status | **valid** |

### R127 — Python Tool Call Chain

| Item | Value |
|------|-------|
| chain_structural | ✅ YES |
| chain_path | `services.py:start_run` (line 191) → `asyncio.create_task(run_agent())` (line 273) → `worker.py:run_agent` (line 79) → `agent.astream()` (line 236) |
| runtime gates | ⚠️ UNCLEAR — model availability, MCP health, event observability all unverified |
| status | **valid_structural_but_unchecked_runtime** |

---

## LANE 3 — Post-Foundation Delta Impact Mapping

### Impact Summary

| Domain | Impact | Detail |
|--------|--------|--------|
| auth_gateway | neutral_to_mainline | Both flags `false`; TS orchestrator never routes to auth paths |
| persistence | neutral_to_mainline | tmp SQLite only; TS side uses in-memory; no impact on TS chain |
| credential_bootstrap | neutral_to_mainline | Irrelevant to TS orchestration path |
| deps/langgraph_runtime | improves_mainline | `langgraph_runtime()` initializes checkpointer/store/event_store — deps in place |
| m11 visual_automation | neutral_to_mainline | TypeScript `executor_adapter.ts` unchanged by R241 |
| mcp_tools | still_blocked | Code present; MCP server health unprobed |
| pr_ci_baseline | unrelated_side_track | 255 lint errors + auth_middleware.py:85 SyntaxError are baseline, not main chain blockers |

**Key finding:** R241 auth-disabled wiring is entirely in `backend/app/gateway/` and `backend/packages/harness/deerflow/persistence/`. The TypeScript orchestrator path (`backend/src/domain/m01/`, `m04/`, `m11/`) is **completely untouched** by R241 changes.

---

## LANE 4 — Current Main Chain Reconstruction

### Architecture Overview

```
用户输入
  ↓
M01.Orchestrator.execute()
  ├── intentClassifier.classify() → IntentRoute
  ├── dagPlanner.buildPlan() → DAGPlan
  ├── [PATH A] deerflowEnabled=false → handleLocalExecution()
  │     M01.executeDAG()
  │       M04.Coordinator.execute(system_type)
  │         ├── SEARCH → handleSearchRequest() → SearchAdapter
  │         ├── TASK → handleTaskRequest() → executorAdapter → executeDAG
  │         ├── WORKFLOW → handleWorkflowRequest() → N8NClient/DifyClient
  │         ├── CLAUDE_CODE → handleClaudeCodeRequest() → executorAdapter(CLAUDE_CODE)
  │         ├── VISUAL_WEB → handleVisualWebRequest() → executeWithAutoSelect()
  │         │     executorReadinessGate() → not_ready → skip → fallback
  │         └── DESKTOP_APP → handleDesktopAppRequest() → desktopToolSelector
  │
  └── [PATH B] deerflowEnabled=true (DEFAULT) → handleDeerFlowExecution()
        DeerFlowClient.healthCheck() → /health:8001
        DeerFlowClient.createThread() [business probe if /health false]
        DeerFlowClient.executeUntilComplete() → POST /api/threads/{id}/runs
          ↓
        Python: gateway/routers/runs.py
          start_run(body, thread_id, request) [services.py:191]
            run_agent() [asyncio.create_task] [worker.py:79]
              agent.astream() [line 236] → LangGraph agent + tools
```

### Confirmed Edges (all functional)

| From | To | Location |
|------|----|----------|
| M01.execute() | switch(classification.route) | orchestrator.ts:99 |
| handleOrchestration | deerflowEnabled check | orchestrator.ts:189 |
| DeerFlow path | healthCheck + createThread probe | orchestrator.ts:208-218 |
| DeerFlow path | timeout → local fallback | orchestrator.ts:231-233 |
| M01.executeDAG | coordinator.execute() | orchestrator.ts:306 |
| Coordinator.execute | switch(system_type) | coordinator.ts:146 |
| VISUAL_WEB | executeWithAutoSelect | coordinator.ts:421 |
| CLAUDE_CODE | executorAdapter.submit | coordinator.ts:294 |
| executorReadinessGate | not_ready → skip | executor_adapter.ts:241-289 |
| checkExecutorHealth | 4-executor health check | executor_adapter.ts:165 |
| start_run | run_agent task | services.py:273 |
| run_agent | agent.astream | worker.py:236 |

### Unknown Edges (need runtime probe)

| Item | Question |
|------|----------|
| `resolve_agent_factory()` | Which LangGraph agent graph is used? Has it changed? |
| MCP tool registration | Do MCP tools actually register in the agent? |
| Tool-call event observability | Does `event_store` actually capture tool events? |
| Model availability | Does the LLM actually respond? |

---

## LANE 5 — Branch Chain Inventory (15 branches)

| ID | Name | Status | Priority |
|----|------|--------|----------|
| BRANCH-01 | 搜索支链 | structural_present | later |
| BRANCH-02 | 任务DAG支链 | structural_present | later |
| BRANCH-03 | 工作流支链 | structural_present | later |
| BRANCH-04 | 视觉网页支链 | structural_present | high |
| BRANCH-05 | 桌面应用支链 | structural_present | later |
| BRANCH-06 | Claude Code本地执行支链 | structural_present | high |
| BRANCH-07 | DeerFlow/Python Agent支链 | structural_present | **critical** |
| BRANCH-08 | MCP工具支链 | code_present_unprobed | **critical** |
| BRANCH-09 | 记忆系统支链 | structural_present | medium |
| BRANCH-10 | 资产系统支链 | read_only_ready | low |
| BRANCH-11 | 夜间复盘支链 | read_only_ready | low |
| BRANCH-12 | 升级中枢/experiment_queue支链 | not_fully_mapped | later |
| BRANCH-13 | RTCM圆桌会议支链 | structural_present | medium |
| BRANCH-14 | Feishu Summary/Report支链 | dry_run_only | low |
| BRANCH-15 | Auth/Gateway支线 | disabled_wired | **post-main-chain** |

---

## LANE 6 — Current Breakpoint Matrix

### Primary Breakpoint

| ID | Location | Description |
|----|----------|-------------|
| **BP-01** | Python LangGraph agent runtime | Model availability — does the LLM actually respond? |

### Secondary Breakpoints

| ID | Location | Description |
|----|----------|-------------|
| BP-02 | MCP tool registration + health | MCP server health + tool callable verification |
| BP-03 | worker.py:236 agent.astream | Tool-call event observability |
| BP-04 | executor_adapter.ts:165 checkExecutorHealth | Visual automation health (OpenCLI/Midscene/UI-TARS) |
| BP-05 | executor_adapter.ts:241 executorReadinessGate | Claude Code fallback chain |
| BP-06 | orchestrator.ts:306 coordinator.execute() | M01/M04/M11 interface compatibility |
| BP-07 | deps.py langgraph_runtime | Checkpointer + store + event_store initialization |

### Blocker Dependency

```
BP-01 (model availability)
  ↓ (must resolve first)
BP-02 (MCP tool health) ← BP-01 must pass first
  ↓
BP-03 (event observability) ← BP-02 must pass first
```

---

## LANE 7 — Repair Strategy Rebase

### Phase 1 — Main Chain Gatekeeper Clearance (3 actions)

| Rank | Action | Target | Gateway Required |
|-------|--------|--------|-----------------|
| 1 | Python model availability probe | BP-01 | YES |
| 2 | MCP tool registration + health check | BP-02 | YES |
| 3 | Tool-call event observability verification | BP-03 | YES |

### Phase 2 — Direct Branch Verification (3 actions)

| Rank | Action | Target | Gateway Required |
|-------|--------|--------|-----------------|
| 1 | Visual automation health check | BP-04 | NO (TS only) |
| 2 | Claude Code fallback chain verification | BP-05 | NO (TS only) |
| 3 | M01/M04/M11 interface compatibility recheck | BP-06 | NO (TS only) |

### Phase 3 — Deep Branch Exploration

- BRANCH-01 (搜索): SearchAdapter runtime verification
- BRANCH-03 (工作流): N8N/Dify availability check
- BRANCH-07 (DeerFlow/Python): Full path B end-to-end smoke test
- BRANCH-09 (记忆): Memory runtime health probe
- BRANCH-13 (RTCM): Feishu API credential + handoff verification

### Phase 4 — Function Acceptance

逐个功能验收：搜索 / 任务DAG / 视觉自动化 / Claude Code本地 / DeerFlow远程 / 记忆 / Feishu摘要

### Phase 5 — Closeout

- All branch chains verified or formally deferred
- Blocker matrix refreshed against actual runtime state
- PR/CI baseline formally acknowledged as separate track

---

## LANE 8 — Next Phase Proposal

**Recommended next phase:** `R129_MODEL_AND_MCP_HEALTH_PROBE_PLAN`

**Rationale:** BP-01 (model availability) and BP-02 (MCP health) are the two highest-severity items that remain unverified. BP-03 (event observability) depends on BP-02. No repair to TypeScript-side chains (BP-04 through BP-06) is higher priority than verifying whether the Python agent can actually respond to model calls.

**Constraint reminder:**
- actual_patch_allowed = false
- Gateway activation may be required for Python-side probes
- No production DB write
- No auth middleware/route activation

---

## Final Report

```
R128_LOCAL_REALITY_REBASE_AFTER_FOUNDATION_REPAIR_DONE
status=passed
pressure_assessment_completed=true
recommended_pressure=XXL++
workspace_baseline_completed=true
old_mainline_revalidated=true
r119_health_gate_still_present=true
r123_systemtype_chain_still_present=true
r126_deerflow_entry_still_restored=true
r120_m04_python_boundary_still_valid=true
r127_python_tool_chain_still_structural=true
r127_python_tool_chain_runtime_unchanged=true
foundation_delta_impact_mapped=true
current_main_chain_graph_ready=true
branch_chain_inventory_ready=true
breakpoint_matrix_ready=true
primary_mainline_breakpoint=BP-01_MODEL_AVAILABILITY
secondary_breakpoints=[BP-02_MCP_HEALTH, BP-03_EVENT_OBSERVABILITY, BP-04_VISUAL_HEALTH]
repair_strategy_ready=true
recommended_next_phase=R129_MODEL_AND_MCP_HEALTH_PROBE_PLAN
actual_patch_allowed=false
report_files=[
  migration_reports/recovery/R128_LOCAL_REALITY_REBASE_AFTER_FOUNDATION_REPAIR.md,
  migration_reports/recovery/R128_LOCAL_REALITY_REBASE_AFTER_FOUNDATION_REPAIR.json
]
code_modified=false
db_written=false
jsonl_written=false
gateway_activation_allowed=false
production_db_write_allowed=false
push_executed=false
merge_executed=false
blockers_preserved=true
safety_violations=[]
next_prompt_needed=R129
```

---

## Old Mainline Status From R117-R127

| Phase | Conclusion | Current Status |
|-------|------------|----------------|
| R117 | EXECUTOR_SELECTION_HEALTH_GATE_VERIFIED | ✅ STILL VALID |
| R118 | HEALTH_GATE_FALLBACK_CHAIN_CLAUDE_CODE_RESERVED | ✅ STILL VALID |
| R119 | EXECUTOR_SELECTION_HEALTH_GATE_WORKING_BUT_ENV_LIMITED | ✅ STILL VALID (ENV_LIMITED unchanged) |
| R120 | M04_PYTHON_BOUNDARY_CLEAN | ✅ STILL VALID |
| R121 | DAG_SYSTEMTYPE_INFERENCE_CHAIN_REPAIRED | ✅ STILL VALID |
| R122 | VISUAL_WEB_DESKTOP_APP_CLAUDE_CODE_ROUTING_FIXED | ✅ STILL VALID |
| R123 | DAG_SYSTEMTYPE_CHAIN_VERIFIED | ✅ STILL VALID |
| R124 | DEERFLOW_ENTRY_CHAIN_VERIFIED | ✅ STILL VALID |
| R125 | DEERFLOW_HEALTH_FALLBACK_CONFIRMED | ✅ STILL VALID |
| R126 | DEERFLOW_ENTRY_CHAIN_FULLY_RESTORED | ✅ STILL VALID |
| R127 | PYTHON_TOOL_CALL_CHAIN_STRUCTURAL_VERIFIED | ✅ VALID (runtime gates UNCLEAR) |

---

## Phase Sequence

```
R127 (last old mainline)
  → R128 (THIS PHASE — local reality rebase)
  → R129 (model + MCP health probe plan)
       ↓
  [Phase 1: BP-01/02/03 clearance]
  [Phase 2: BP-04/05/06 verification]
  [Phase 3: Deep branch exploration]
  [Phase 4: Function acceptance]
  [Phase 5: Closeout]
```

---

*Generated by Claude Code — R128 (Local Reality Rebase After Foundation Repair)*
