# OpenClaw Subsystem Operational Acceptance Result Template

## Usage

This template is filled during R246C–R246H execution by the operator running each acceptance case and recording actual results.

All results are recorded in `subsystem_operational_acceptance_cases.json` with per-case `status` fields updated from `PLANNED` to actual result statuses.

---

## Per-Case Result Fields

For each case, record:

```
Case ID:              <case_id from cases.json>
Layer:                <L0–L5>
System:               <system name>
Function:             <function or endpoint>
Actual Command:       <exact command executed>
Exit Code:            <exit code returned>
Actual Output:        <truncated output or file path>
Parsed JSON:          <if applicable, parsed key fields>
Evidence Path:        <file path or URL showing evidence>
Status:               <PASS | PASS_WITH_LIMITS | FAIL | DEFERRED_EXTERNAL | NOT_FOUND | NEEDS_TARGETED_FIX | NEEDS_SEPARATE_AUTHORIZATION>
Failure Classification: <FAIL_CODE_BUG | FAIL_ENV_DEPENDENCY | FAIL_MISSING_ENTRYPOINT | FAIL_EXTERNAL_CREDENTIAL | FAIL_UNIMPLEMENTED | FAIL_CONTRACT_MISMATCH | FAIL_SAFETY_BOUNDARY | FAIL_UNKNOWN>
Forbidden Side Effects Observed: <list any observed forbidden side effects>
Next Action:          <describe required next action>
```

---

## Status Enum

| Status | Meaning |
|--------|---------|
| PASS | Entry/input correct, output matches expectation, zero forbidden side effects observed |
| PASS_WITH_LIMITS | Function works but has a defined boundary (e.g., dry-run only, no scheduler, not production-verified) |
| FAIL | Function not available or output does not match expectation |
| DEFERRED_EXTERNAL | Depends on external unready credentials or service |
| NOT_FOUND | Entry point does not exist |
| NEEDS_TARGETED_FIX | Found defect; fix required before re-acceptance |
| NEEDS_SEPARATE_AUTHORIZATION | Requires separate authorization (e.g., real-send, Agent-S) |

---

## Failure Classification Enum

| Classification | Meaning |
|---------------|---------|
| FAIL_CODE_BUG | Code has a bug causing incorrect behavior |
| FAIL_ENV_DEPENDENCY | Environment dependency missing or misconfigured |
| FAIL_MISSING_ENTRYPOINT | Entry point (route/function) does not exist |
| FAIL_EXTERNAL_CREDENTIAL | External credential (API key, token) missing or invalid |
| FAIL_UNIMPLEMENTED | Feature not implemented in tracked code |
| FAIL_CONTRACT_MISMATCH | Input/output contract not satisfied |
| FAIL_SAFETY_BOUNDARY | Safety boundary violated (real-send attempted, token accessed, etc.) |
| FAIL_UNKNOWN | Unknown root cause; needs investigation |

---

## Summary Table Template

Fill this table after completing each group's execution:

| System | Cases | PASS | PASS_WITH_LIMITS | FAIL | DEFERRED_EXTERNAL | NOT_FOUND | Verdict |
|--------|------:|-----:|-----------------:|-----:|------------------:|----------:|---------|
| FOUND (Foundation) | N | N | N | N | N | N | PASS/FAIL |
| GW (Gateway) | N | N | N | N | N | N | PASS/FAIL |
| SEARCH (Search) | N | N | N | N | N | N | PASS/FAIL |
| TASK (Task) | N | N | N | N | N | N | PASS/FAIL |
| WF (Workflow) | N | N | N | N | N | N | PASS/FAIL |
| CLAUDE (Claude Code) | N | N | N | N | N | N | PASS/FAIL |
| VW (Visual Web) | N | N | N | N | N | N | PASS/FAIL |
| DESK (Desktop) | N | N | N | N | N | N | PASS/FAIL |
| MCP (MCP Boundary) | N | N | N | N | N | N | PASS/FAIL |
| RTCM (RTCM) | N | N | N | N | N | N | PASS/FAIL |
| AUTO (Autonomous Agent) | N | N | N | N | N | N | PASS/FAIL |
| MEM (Memory) | N | N | N | N | N | N | PASS/FAIL |
| PROMPT (Prompt) | N | N | N | N | N | N | PASS/FAIL |
| EVO (Evolution) | N | N | N | N | N | N | PASS/FAIL |
| ASSET (Asset) | N | N | N | N | N | N | PASS/FAIL |
| TOOL (Tool/Skill) | N | N | N | N | N | N | PASS/FAIL |
| REPORT (Feishu/Report) | N | N | N | N | N | N | PASS/FAIL |
| NIGHTLY (Nightly Review) | N | N | N | N | N | N | PASS/FAIL |
| CLI (Operator CLI) | N | N | N | N | N | N | PASS/FAIL |
| SAFE (Security/Hygiene) | N | N | N | N | N | N | PASS/FAIL |
| **TOTAL** | **N** | **N** | **N** | **N** | **N** | **N** | **PASS/FAIL** |

---

## Verdict Criteria

**System Verdict = PASS**: All cases PASS or PASS_WITH_LIMITS (with documented limits acceptable).

**System Verdict = FAIL**: Any case is FAIL (not deferred, not external).

**Overall Verdict = PASS**: All 20 systems PASS.

**Overall Verdict = PASS_WITH_DEFERRED**: All non-FAIL systems, with DEFERRED_EXTERNAL or NEEDS_SEPARATE_AUTHORIZATION cases documented.

**Overall Verdict = FAIL**: Any NEEDS_TARGETED_FIX or FAIL not resolved.

---

## Forbidden Side Effects Observed Log

If any of the following are observed during a case execution, record the case ID and immediately stop:

| Forbidden Effect | Action |
|-----------------|--------|
| token_cache.json content read | STOP — output all findings, request authorization |
| Token value printed or logged | STOP — output all findings, request authorization |
| Feishu/Lark real-send executed | STOP — not authorized |
| Agent-S invocation | STOP — not authorized |
| daemon or background worker started | STOP — not authorized |
| cron or scheduled task created | STOP — not authorized |
| production DB write | STOP — not authorized |
| external network real call | STOP — not authorized |

---

## R246 Group Results Recording

After each group execution, save results:

| Group | Phase | Result File |
|-------|-------|-------------|
| L0 Foundation + L1 Main Chain | R246C | `docs/openclaw/subsystem_operational_acceptance_results_R246C.md` |
| L2 Path A Local Execution | R246D | `docs/openclaw/subsystem_operational_acceptance_results_R246D.md` |
| L3 MCP External Tools | R246C | (combined with R246C) |
| L4 Deep Systems A (RTCM/AUTO/MEM) | R246D | `docs/openclaw/subsystem_operational_acceptance_results_R246D.md` |
| L4 Deep Systems B (PROMPT/EVO/TOOL) | R246E | `docs/openclaw/subsystem_operational_acceptance_results_R246E.md` |
| L4 Deep Systems C (ASSET/REPORT/NIGHTLY/CLI) | R246F | `docs/openclaw/subsystem_operational_acceptance_results_R246F.md` |
| L5 Security/Hygiene | R246G | `docs/openclaw/subsystem_operational_acceptance_results_R246G.md` |
| Final Analysis | R246H | `docs/openclaw/subsystem_operational_acceptance_final_report.md` |

---

## Next Action After Each Group

After each group execution:

1. Fill summary table
2. For any FAIL or NEEDS_TARGETED_FIX: create separate fix task
3. For any NEEDS_SEPARATE_AUTHORIZATION: document in `future_roadmap.md`
4. Proceed to next group
5. After R246G: create final report (R246H)

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-07 | R246B — result template created |
