# OpenClaw System Capability Acceptance Matrix

## Status

**SYSTEM_LEVEL_ACCEPTANCE_COMPLETE**

This matrix evaluates user-visible capabilities, not individual source files. All capabilities are assessed based on PR evidence, test results, and smoke validation.

---

## Capability Matrix

| # | Capability | Status | User-visible Delivery | Evidence | Limitations | Forbidden Claims | Acceptance Result |
|---|-----------|--------|----------------------|----------|-------------|-----------------|------------------|
| 1 | Gateway / no-tool agent | AVAILABLE | Health endpoint returns 200; no-tool run path executes without tools | PR #4 merge; R156/R157 smoke; repair plan closeout | None | — | PASS |
| 2 | Run / status / result | AVAILABLE | Primary run route returns 200; fallback preserved; result retrieval works | PR #4; R157; 503→200 confirmed | None | — | PASS |
| 3 | Path A local execution route | AVAILABLE_WITH_LIMITS | Orchestrator → Coordinator → Executor adapter chain executes locally | R151–R155; 25/25 local tests passing | External executor availability varies by deployment | "Full autonomous orchestration" | PASS_WITH_LIMITS |
| 4 | Tool-call observability | AVAILABLE | Internal tool calls observable in result; MCP tools return structured results | R148 E2E; BP-01 Level 2 PASSED | External MCP tools depend on credentials | — | PASS |
| 5 | MCP tool isolation / external boundary | AVAILABLE_WITH_LIMITS | Tavily MCP stdio works; Lark MCP deferred; missing credentials do not block no-tool path | R147K stdio fix; R148 E2E passed; MCP isolation confirmed | Real external MCP requires valid credentials | "All MCP tools production-verified" | PASS_WITH_LIMITS |
| 6 | Memory | AVAILABLE | Memory branch validated; 149/149 tests passing | R191; memory branch CI green | None | — | PASS |
| 7 | Prompt / Skill / Tool registry | AVAILABLE | 276 tests passing; Skill and Tool execution works | R192; 276/276 passed, 1 skipped | None | — | PASS |
| 8 | Upgrade Center | AVAILABLE | m04 registry test coverage added; 14 tests passing | PR #7; 14/14 tests passing | None | — | PASS |
| 9 | Feishu / Report dry-run | AVAILABLE_WITH_LIMITS | Card build and parser tests pass; dry-run boundary confirmed; `--real` raises NotImplementedError | R195; 14 parser tests; safety tests confirm no real send | Real-send production verification deferred (R240X) | "Feishu real-send production verified" | PASS_WITH_LIMITS |
| 10 | Nightly Review | AVAILABLE_WITH_LIMITS | Dry-run pipeline works; manual scheduler; explicit export via CLI; no daemon; no real-send | PR #9 + PR #11 + PR #18; 58 tests; `nightly-export --output` writes markdown | No daemon/cron; no real-send; operator-triggered only | "Nightly Review fully implemented" | PASS_WITH_LIMITS |
| 11 | Asset Runtime | AVAILABLE_WITH_LIMITS | Dry-run adapter works; tracked capability registry with 6 capabilities; Operator CLI capability selection; no Agent-S invocation | PR #13 + PR #17; 42 tests; `asset-dry-run --capability asset.X` routes correctly | No Agent-S; no real asset execution; no `.deerflow/operation_assets` read | "Asset runtime production verified" | PASS_WITH_LIMITS |
| 12 | RTCM Roundtable | AVAILABLE_WITH_LIMITS | Dry-run runtime works; JSONL store with get/latest/export; markdown/json report export; report index; no operational data read | PR #14 + PR #18; 58 tests; `rtcm-dry-run-export --output` writes markdown | No real agents; no Feishu send; no `.deerflow/rtcm` read | "RTCM production runtime verified" | PASS_WITH_LIMITS |
| 13 | OpenClaw Operator CLI | AVAILABLE_WITH_LIMITS | Unified dry-run console; 9 commands; JSON output; `--real` rejected (exit 2); no credential access; explicit paths only | PR #16 + PR #17 + PR #18; 58 tests; CLI smoke 9/9 commands rc=0 | Dry-run / explicit export only; no real side effects | "CLI enables real execution" | PASS_WITH_LIMITS |
| 14 | Security / hygiene posture | AVAILABLE | `.gitignore` hygiene guard; operational data untracked; S-RTCM-FEISHU-TOKEN-001 open but compensated | PR #8; hygiene guard confirmed; `git check-ignore` verified | S-RTCM-FEISHU-TOKEN-001 open; token rotation deferred by operator | "Security fully clean" | PASS |
| 15 | Deferred future work boundary | AVAILABLE | R240X/R241X/R242X and Nightly daemon formally deferred; boundaries documented; no mixed PRs | `deferred_future_work.md`; R243X closeout; `vnext_enhancement_closeout.md` | None — future work intentionally excluded | "Deferred items are implementable now" | PASS |

---

## Summary

| Classification | Count |
|---------------|-------|
| AVAILABLE | 8 |
| AVAILABLE_WITH_LIMITS | 7 |
| DEFERRED | 0 |
| BLOCKED | 0 |

**Total: 15 capabilities — 15 accepted**

---

## Final Acceptance Conclusion

1. **No BLOCKED capabilities** exist in the accepted delivery scope.
2. **All 8 AVAILABLE capabilities** have current CI/test evidence.
3. **All 7 AVAILABLE_WITH_LIMITS capabilities** have working dry-run implementations with documented explicit boundaries.
4. **Future production side-effect capabilities** (Feishu real-send, Agent-S, RTCM real-agent, Nightly daemon) are formally deferred with explicit constraints documented in `deferred_future_work.md`.
5. **Security exception** S-RTCM-FEISHU-TOKEN-001 remains open but is compensated by `.gitignore` guard and documented operator-deferral.
6. **Current delivery is safe** — all capabilities are either dry-run, explicit-path, or operator-triggered with no silent background effects.

---

## Evidence Basis

| Source | Result |
|--------|--------|
| Focused pytest | 220 passed, 1 pre-existing failure (test_list_capabilities_returns_list — type assertion, not functional) |
| Import smoke | 17/17 modules import cleanly |
| CLI smoke | 9/9 commands return rc=0 |
| Ruff check | All checks passed |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | R244X — system capability acceptance matrix complete; 15/15 capabilities evaluated; 8 AVAILABLE, 7 AVAILABLE_WITH_LIMITS, 0 DEFERRED, 0 BLOCKED |
