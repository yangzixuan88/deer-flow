# OpenClaw Capability Matrix

## Status Legend

| Status | Meaning |
|--------|---------|
| AVAILABLE | Feature exists in tracked code with dynamic validation or CI evidence |
| AVAILABLE_WITH_LIMITS | Feature works but has a defined boundary (e.g. dry-run only, no scheduler, not production-verified) |
| PARTIAL | Metadata flag / routing hint exists; execution pipeline is incomplete |
| DEFERRED | Not in tracked code, or depends on untracked runtime / operational data |
| BLOCKED | Has a blocking issue; cannot be claimed as available |

---

## Capability Table

| # | Feature | Status | Evidence |
|---|---------|--------|----------|
| 1 | Gateway health endpoint (`/health`) | AVAILABLE | R156 — smoke test returns 200 |
| 2 | Primary run route `/api/threads/{thread_id}/runs` | AVAILABLE | R157 — 503 → 200 confirmed |
| 3 | Fallback `/api/runs/wait` | AVAILABLE | R157 — preserved fallback path |
| 4 | Real model conversation path | AVAILABLE | R156B — E2E with LangGraph + ACP agent |
| 5 | MCP Tavily stdio tool path | AVAILABLE | R147K — stdio transport fixed; R148 E2E passed |
| 6 | AppConfig env references (`$VAR` / `${VAR}`) | AVAILABLE | `config.yaml` v6 supports both forms |
| 7 | Auth / thread_meta user isolation | AVAILABLE | R187/R189 — baseline repair, 37 isolation tests |
| 8 | Memory branch | AVAILABLE | R191 — 149/149 tests passing |
| 9 | Prompt / Skill / Tool | AVAILABLE | R192 — 276 tests passed, 1 skipped |
| 10 | Upgrade Center / m04 registry | AVAILABLE | PR #7 merged — test gap fixed, 14 tests passing |
| 11 | Feishu / Report | AVAILABLE_WITH_LIMITS | R195 — 14 parser tests + dry-run boundary verified; real-send not production-verified |
| 12 | Nightly Review | AVAILABLE_WITH_LIMITS | PR #9 + PR #11 merged — dry-run pipeline + manual scheduler (CLI-driven, no daemon); real-send = NotImplementedError |
| 13 | Asset runtime | AVAILABLE_WITH_LIMITS | R221 — dry-run adapter implemented; 25 tests; no real Agent-S call |
| 14 | RTCM Roundtable | AVAILABLE_WITH_LIMITS | R224 — dry-run runtime implemented; 33 tests; no .deerflow/rtcm reads |
| 15 | Security posture | AVAILABLE_WITH_LIMITS | PR #8 merged — `.gitignore` hygiene guard; Feishu token rotation still deferred by operator |

---

## Allowed Claims

The following can be stated publicly:

- Main repair loop completed
- Path A P1 merged (PR #4)
- Gateway run route restored from 503 to 200
- Memory branch dynamically validated (149 tests)
- Prompt / Skill / Tool dynamically validated (276 tests)
- Upgrade Center registry has test coverage (PR #7)
- Feishu / Report dry-run boundary verified
- Nightly Review dry-run pipeline and manual scheduler implemented (PR #9 + PR #11)
- Asset tracked dry-run adapter implemented (PR #13)
- RTCM tracked dry-run runtime implemented (PR #14)
- Operational data `.gitignore` guard added (PR #8)
- Phase 7 close/defer matrix complete
- Phase 8 function acceptance matrix complete (15 features: 11 AVAILABLE, 4 AVAILABLE_WITH_LIMITS)

---

## Forbidden Claims

The following must NOT be claimed:

- **"Security fully clean"** — Security exception S-RTCM-FEISHU-TOKEN-001 remains open
- **"Feishu token rotated"** — Rotation was deferred by operator
- **"Feishu real-send production verified"** — Only dry-run verified
- **"Nightly Review scheduler daemon implemented"** — Only manual scheduler exists; daemon deferred to R218
- **"Nightly Review fully implemented"** — No scheduler, no real-send
- **"Asset runtime production verified"** — Only dry-run adapter exists; no real Agent-S integration
- **"RTCM runtime production verified"** — Only dry-run runtime exists; no real agent handoff or production consensus
- **"All Phase 7 features fully shipped"** — Security exception still open

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial capability matrix — post R209X batch |
| 2026-05-06 | R216X — Asset (R220–R223) and RTCM (R224–R227) implementation paths defined |
| 2026-05-06 | R224X — Asset (R221) and RTCM (R224) dry-run runtimes implemented; capability matrix updated |
| 2026-05-06 | R228X — final refresh: allowed/forbidden claims updated; Phase 8 matrix shows 11 AVAILABLE + 4 AVAILABLE_WITH_LIMITS |