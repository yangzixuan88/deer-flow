# R150: Mainline System Acceptance Map

## Status: PASSED

## Preceded By: R149
## Proceeding To: R151_PATH_A_LOCAL_ORCHESTRATION_ACCEPTANCE

## Pressure: L

---

## Summary

R150 closes the R144–R149 MCP Tavily debugging branch and re-enters the mainline system acceptance map. It catalogs the current status of all mainline subsystems (Path A / Path B / MCP / Auth / Result persistence), updates the blocker matrix, designs the system acceptance matrix across 10 functional domains, and formalizes the R151–R155 roadmap.

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R149 |
| current_phase | R150 |
| recommended_pressure | L |
| reason | Mainline acceptance mapping; no runtime execution required; no model API calls; no MCP runtime activation |

---

## LANE 1: Commit / Evidence Reconciliation

| Commit | SHA | Message | Confirmed |
|---|---|---|---|
| R140 inline fix | `f480fec1` | `feat(gateway): add run_in_background=False to start_run for inline test execution` | **true** |
| R142C result persistence | `bc3c0670` | `feat(runs): persist final result snapshot to RunRecord via checkpointer` | **true** |
| R147K Tavily stdio | `da4b7565` | `chore(mcp): switch Tavily from SSE to stdio transport` | **true** |
| R148 smoke (not production code) | — | R148 was smoke test only, not a code commit | **true** |
| R149 R148 field correction | logged | R149 corrected R148's `mcp_runtime_called=false` to `true` | **true** |

**Dirty files classification:** `expected_untracked_reports_and_new_modules` — all dirty files are report artifacts (`migration_reports/recovery/`) or new modules (`backend/app/m*/`). No tracked production code modified.

---

## LANE 2: Path B Gateway Runtime Status Map

| Subsystem | Status | Evidence |
|---|---|---|
| **Auth / CSRF** | ✅ clear | R241 foundation repair; `internal_auth.py` honored before session cookie (`2e1a69da`); auth-disabled wiring in `r241/auth-disabled-wiring-v2` branch |
| **Thread CRUD** | ✅ clear | `ContextEnvelope` (context.py) provides minimal `thread_id`/`run_id` passthrough; no structural blockers in R128 |
| **start_run** | ✅ clear | R140 adds `run_in_background=False` for inline test execution (`f480fec1`); default preserved |
| **worker run_agent** | ✅ clear | `worker.py:236` `agent.astream()` chain confirmed in R127/R128; BP-01 passes Level 0+1 (R130) |
| **No-tool model run** | ✅ clear | BP-01 Level 2 cheap ping PASSED via R131B-C1: 7087ms, 846 chars response |
| **Result persistence** | ✅ clear | R142C (`bc3c0670`) persists final result snapshot to RunRecord via checkpointer |
| **Internal tool-call** | ✅ clear | `get_cached_mcp_tools()` path viable (R147L); `create_deerflow_agent(tools=[tavily_tool])` direct injection works (R148) |
| **Tavily tool-call** | ✅ clear | R148 PASSED: `model_call_count=2`, `tavily_call_count=1`, `tool_call=true`, `tool_result=true`, `final_answer=true`, 27.22s |

**Path B verdict: ALL CLEAR** — no structural blockers remain in the Python/Gateway runtime path.

---

## LANE 3: Path A TypeScript / Local Orchestration Status Map

| Component | Status | Evidence |
|---|---|---|
| **M01 Orchestrator** | ✅ structural clear | `backend/src/domain/m01/orchestrator.ts`; `deerflowEnabled` flag check intact (line 189); healthCheck probe intact (line 208–218); local fallback on timeout intact (line 231–233) |
| **M04 Coordinator** | ✅ structural clear | `backend/src/domain/m04/coordinator.ts`; system-type switch intact (line 146); never calls Python directly |
| **M11 Executor Adapter** | ✅ structural clear | `backend/src/domain/m11/adapters/executor_adapter.ts`; `executorReadinessGate` present (line 241); `not_ready → skip` action intact (line 282); OpenCLI fallback intact |
| **TS layer touched by R241** | **false** | R128 confirmed: TypeScript orchestrator path completely untouched by R241 auth-disabled wiring |
| **Local orchestration acceptance** | **runtime pending** | Path A structurally verified but runtime acceptance was deferred; R151 is the proper phase |

**Next required phase: `R151_PATH_A_LOCAL_ORCHESTRATION_ACCEPTANCE`**

---

## LANE 4: MCP Status Final Map

| Server | Status | Transport | Auth | Next / Blocker | Mainline Blocker |
|---|---|---|---|---|---|
| **tavily** | ✅ working | stdio | env var | mainline production | **false** |
| **lark** | ❌ paused | stdio | — | SDK token attach bug (99991661) | **false** (deferred) |
| **exa** | ❌ disabled | stdio | — | EXA_API_KEY missing | **false** (deferred) |

**Lark blocker detail:** SDK's `Client.request()` does not automatically attach tenant token in stdio MCP tool calls. Fix requires SDK patch to attach tenant token. Estimated effort: unknown. **Deferred — does not block mainline.**

**Exa blocker detail:** `EXA_API_KEY` not present in environment. Fix: provide env var. Estimated effort: low (config only). **Deferred — does not block mainline.**

---

## LANE 5: Remaining Blocker Matrix

| ID | Title | Category | Blocks Mainline | Deferred | Detail | Next Action |
|---|---|---|---|---|---|---|
| BM-01 | Lark MCP SDK token attach bug | critical | **false** | **true** | SDK `Client.request()` does not attach tenant token; ticket 99991661 | Await Tavily validation success before investing in SDK fix |
| BM-02 | Exa EXA_API_KEY missing | minor | **false** | **true** | env var not present; config only | Provide `EXA_API_KEY` when Exa re-enabled |
| BM-03 | config.yaml version outdated | minor | **false** | **true** | R130 found config version 6, latest is 8 | Upgrade config version in future maintenance window |
| BM-04 | Tavily API key in URL | minor | **false** | **true** | R130 noted exposure pre-R147K | Already addressed in R147K stdio fix |
| BM-05 | PR CI baseline lint errors | minor | **false** | **true** | 255 lint errors are baseline, not main chain | Separate track from mainline acceptance |
| BM-06 | No structural mainline blocker | info | **false** | **false** | All critical paths clear | Proceed to R151 acceptance per domain |

**Key finding: No structural mainline blocker identified.** All Path B subsystems are clear.

---

## LANE 6: System Acceptance Matrix Design

| # | Domain | Current Status | Acceptance Test | Required Phase | Pass Criteria |
|---|---|---|---|---|---|
| 1 | **Gateway Runtime** | clear | Gateway starts, `/health` returns 200, auth middleware does not block Path B | R150 (commit reconciliation) | `f480fec1`, `2e1a69da`, `550b541f` present |
| 2 | **Agent No-Tool** | clear | MiniMax model responds to `invoke()` without tools | R131B-C1 (PASSED: 7087ms) | BP-01 Level 2 ping success |
| 3 | **Result Persistence** | clear | `RunRecord.persist_result_snapshot` called via checkpointer | R142C (PASSED: `bc3c0670`) | Result persisted in checkpointer, not JSONL |
| 4 | **Internal Tool-Call** | clear | `create_deerflow_agent(tools=[tavily_tool])` bypasses MCP lazy init | R148 (PASSED: 27.22s) | `tool_call=true`, `tool_result=true`, `final_answer=true` |
| 5 | **Tavily MCP Tool-Call** | clear | `tavily_tavily_search` called exactly once, result consumed | R148 (PASSED) | `model_call_count=2`, `tavily_call_count=1` |
| 6 | **TypeScript Local Orchestration** | structural clear, runtime pending | M01→M04→M11 chain produces valid execution | R151 | `deerflowEnabled=false` path produces valid execution |
| 7 | **Cross-Layer Handoff** | structural clear, runtime pending | M01→DeerFlowClient→Python gateway handoff works | R152 | healthCheck probe succeeds, createThread succeeds |
| 8 | **Safety / No Write Side Effects** | clear | No external write, no DB write, no JSONL write | R144–R150 (all passed) | `safety_violations=[]`, `external_write_performed=false` |
| 9 | **Config / Env Hygiene** | minor issues, non-blocking | config.yaml version 8, no secrets in URLs | R154 | Config version upgraded, no embedded secrets |
| 10 | **Report / Memory Continuity** | clear | MEMORY.md updated after each phase | R144–R150 (done) | MEMORY.md current, all reports present |

---

## LANE 7: R151+ Roadmap

| Phase | Purpose | Pressure | Model/Tool Calls | Expected Output |
|---|---|---|---|---|
| **R151** | Accept TypeScript local orchestration (`deerflowEnabled=false` path); M01→M04→M11 chain | M | no | Path A smoke report |
| **R152** | Validate M01↔DeerFlowClient↔Python gateway handoff | M | limited (health check) | Cross-layer handoff report |
| **R153** | Full end-to-end mainline dry-run with real model, real tools | XL | yes (smoke) | Mainline dry-run report |
| **R154** | Config version upgrade, secret hygiene audit | S | no | Config hygiene report |
| **R155** | Final sweep of all 10 acceptance matrix domains | M | yes (smoke) | Final acceptance matrix, all PASS |

---

## LANE 8: Mainline Re-entry Decision

| Condition | Result |
|---|---|
| MCP branch closed for now | **true** |
| Return to mainline | **true** |
| Tavily as active external tool | **true** |
| Lark deferred | **true** |
| Exa deferred | **true** |

**Rationale:** R144–R149 MCP支线 (Tavily调试) is now closed. Tavily MCP is working and validated via R148. Lark/Exa blockers are deferred non-blocking issues. R150 is the formal re-entry point to mainline system acceptance.

---

## LANE 9: Report Generation

| Field | Value |
|---|---|
| reports_written | **true** |
| md_report | `R150_MAINLINE_SYSTEM_ACCEPTANCE_MAP.md` |
| json_report | `R150_MAINLINE_SYSTEM_ACCEPTANCE_MAP.json` |

---

## R150 Classification: PASSED

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

## R150 EXECUTION SUCCESS

**Conclusion:** R150 formally closes the R144–R149 MCP debugging branch and re-enters mainline system acceptance.

**R144–R150 Journey Summary:**

| Phase | Key Achievement |
|---|---|
| R144 | LangGraph `__pregel_runtime` context injection pattern discovered |
| R147I | Lark disabled; Tavily enabled → HTTP 405 (SSE transport mismatch) |
| R147J | Root cause confirmed: `tavily-mcp` is local stdio, not remote SSE |
| R147K | stdio fix applied; Tavily smoke PASSED (8.80s) |
| R147L | MCP status summary; agent integration gate PASSED |
| R148 | Agent Tavily tool-call smoke PASSED (27.22s, 2 model calls, 1 search) |
| R149 | Tool-call contract defined; mainline re-entry authorized |
| **R150** | **Mainline system acceptance map; all Path B clear; R151–R155 roadmap defined** |

---

## R150 EXECUTION SUCCESS

```
R150_MAINLINE_SYSTEM_ACCEPTANCE_MAP_DONE
status=passed
recommended_next_phase=R151_PATH_A_LOCAL_ORCHESTRATION_ACCEPTANCE
mcp_branch_closed_for_now=true
return_to_mainline=true
path_b_all_clear=true
no_structural_mainline_blocker=true
```

`★ Insight ─────────────────────────────────────`
**主链回归路径**：R150 确认了 R241 地基修复后所有 Path B 关键路径（auth、thread CRUD、start_run、result persistence、Tavily tool-call）全部 clear。但 Path A（TypeScript 本地编排）的运行时验收尚未完成，R151 才是 TS 本地路径的正式验收点。
`─────────────────────────────────────────────────`
