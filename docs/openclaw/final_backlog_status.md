# Final Backlog Status — R228X Close

This document records the completion status of all items tracked during the Phase 7/8 repair and hardening cycle.

---

## Completed Areas

| Area | PR / Commit | Status |
|------|-------------|--------|
| Gateway run-route restoration | PR #4 (R156/R157) | ✅ AVAILABLE |
| Backend baseline repair (CI regression) | PR #6 | ✅ AVAILABLE — 37 isolation tests |
| Upgrade Center registry test coverage | PR #7 | ✅ AVAILABLE — 14 tests passing |
| Memory branch validation | R191 | ✅ AVAILABLE — 149/149 tests |
| Prompt / Skill / Tool validation | R192 | ✅ AVAILABLE — 276 tests |
| Feishu / Report dry-run | R195 | ✅ AVAILABLE_WITH_LIMITS — 14 parser tests |
| Nightly Review dry-run pipeline | PR #9 + PR #11 | ✅ AVAILABLE_WITH_LIMITS — dry-run + manual scheduler |
| Asset tracked dry-run adapter | PR #13 (R221) | ✅ AVAILABLE_WITH_LIMITS — 25 tests |
| RTCM tracked dry-run runtime | PR #14 (R224–R226) | ✅ AVAILABLE_WITH_LIMITS — 33 tests |
| Operational data gitignore guard | PR #8 | ✅ AVAILABLE |
| Cross-runtime integration smoke tests | R228X | ✅ 19/19 tests passing |
| Phase 8 capability matrix | R228X | ✅ 11 AVAILABLE + 4 AVAILABLE_WITH_LIMITS |

---

## Still-Open Operator Items

| Priority | Item | Blocker | Expected Action |
|----------|------|---------|-----------------|
| P0 | Feishu token rotation | Operator action required | Rotate via open.feishu.cn → revoke; store in vault; set `FEISHU_TOKEN_ROTATION_ACK=true` |
| P0 | S-RTCM-FEISHU-TOKEN-001 closure | Token rotation unconfirmed | After P0, exception can be closed |
| P1 | Feishu real-send production verification | P0 must be closed first | After token rotation, verify real-send works |
| P2 | Nightly Review scheduler daemon | Optional — deferred to R218 | CLI-triggered cron or systemd timer |
| P3 | Asset external Agent-S adapter spike | Research only | Evaluate wrapper feasibility |
| P4 | RTCM real-agent / production runtime | Deferred to future phase | Decision post-R227 |

---

## Pruned Items

The following items were considered during planning but deliberately excluded:

| Item | Reason for Exclusion |
|------|----------------------|
| Lark MCP SDK token-attach fix | SDK bug in stdio transport mode; Tavily MCP adopted as alternative |
| Exa MCP credentials | Not available; disabled until credentials provided |
| Mode router → RTCM real handoff | Untracked `.deerflow/rtcm/` cannot be used as runtime source; dry-run first mandated |
| Asset real Agent-S integration | External agent unknown; dry-run adapter only |
| RTCM operational log reading | `.deerflow/rtcm/` is operational data, not runtime source |
| Nightly Review daemon auto-start | Explicitly forbidden; CLI-triggered only |

---

## Phase 8 Acceptance Summary

**15 capabilities tracked** — all implemented and test-covered:

- **11 AVAILABLE**: Health endpoint, run route, fallback, real model path, MCP Tavily, AppConfig env refs, auth isolation, Memory branch, Prompt/Skill/Tool, Upgrade Center registry, gitignore guard
- **4 AVAILABLE_WITH_LIMITS**: Feishu/Report, Nightly Review, Asset runtime, RTCM roundtable
- **0 PARTIAL** — no metadata-only or incomplete routing hints remain
- **0 DEFERRED** — all originally deferred items now have dry-run implementations

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | R228X — initial backlog status document |