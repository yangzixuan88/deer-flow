# OpenClaw Future Roadmap

## Overview

The following items are intentionally deferred from the current OpenClaw delivery. Each requires separate authorization and a dedicated implementation boundary. Do not merge these into the current delivery claim.

---

## Deferred Items

### R240X — Feishu Real-Send Controlled Verification

**Status**: DEFERRED

**Description**: Controlled verification of Feishu/Lark real message send with explicit operator authorization.

**Required before start**:
- Explicit operator authorization (not self-service)
- Dedicated target channel/recipient specified
- Credential handling review (token must come from `app_config.lark`, never `token_cache.json`)
- Isolated PR — not mixed with other runtime features

**Constraints**:
- `--real` flag required as explicit opt-in
- Dry-run remains the default
- No production claim until verification completes
- S-RTCM-FEISHU-TOKEN-001 must be closed first

**Unblocks**: Full Feishu real-send production claim

---

### R241X — Asset External Agent-S Adapter Spike

**Status**: DEFERRED

**Description**: Research spike to evaluate whether the external `external/Agent-S/` runtime can be safely wrapped in a tracked adapter.

**Required before start**:
- Spike-only scope (no production code)
- Adapter interface definition reviewed
- No production claim from spike results

**Constraints**:
- No real Agent-S invocation in tests
- No `.deerflow/operation_assets` read by default
- Do not commit `external/Agent-S/` to git

**Unblocks**: Asset real execution integration decision (R223)

---

### R242X — RTCM Real-Agent Strategy Design

**Status**: DEFERRED

**Description**: Architecture design for promoting RTCM from dry-run consensus to real-agent orchestration.

**Required before start**:
- Design-only first phase (R242X = design, not implementation)
- Explicit agent lifecycle model
- Consensus authority model defined
- Side-effect boundary documented

**Constraints**:
- No real-agent execution before architecture approval
- Do not consume `.deerflow/rtcm` as runtime input
- Feishu send from RTCM requires R240X closure

**Unblocks**: RTCM real-agent production runtime (post-R242X)

---

### Nightly Review Scheduler Daemon / Cron

**Status**: DEFERRED

**Description**: Automated background scheduler for Nightly Review with lifecycle management.

**Required before start**:
- Explicit scheduler design document (R218)
- Lifecycle model (start/stop/status/health)
- No auto-start on import (absolute requirement)
- Operator-configured cron or systemd timer unit

**Constraints**:
- No silent background worker behavior
- No automatic scheduling without operator-configured trigger
- Failure recovery and retry policy defined

**Unblocks**: Automated Nightly Review execution

---

## Recommended Implementation Sequence

When authorization is granted, the recommended order is:

1. **R240X** — Feishu real-send (credentials are the primary blocker for production side effects)
2. **R241X** — Asset Agent-S spike (external runtime evaluation)
3. **R242X** — RTCM real-agent design (architecture must precede implementation)
4. **Nightly daemon** — Scheduler design follows Feishu verification

---

## Non-Goals (Hard Constraints)

These remain forbidden regardless of future authorization:

- **Do not** claim production real-agent RTCM runtime before R242X design is complete
- **Do not** implement auto-start daemon on module import
- **Do not** read `.deerflow/rtcm` or `.deerflow/operation_assets` as runtime source
- **Do not** merge deferred items into the current delivery PR
- **Do not** claim "security fully clean" while S-RTCM-FEISHU-TOKEN-001 is open

---

## Related Documents

| Document | Purpose |
|---------|---------|
| `deferred_future_work.md` | Detailed constraints and carry-forward rules |
| `maintenance_manual.md` | Golden rules and escalation path |
| `release_claims.md` | Allowed and forbidden public claims |
| `security_exception_register.md` | S-RTCM-FEISHU-TOKEN-001 status and resolution |

---

---

## R246 Operational Acceptance

### R246B — Operational Acceptance Plan Files (THIS PHASE)

**Status**: IN PROGRESS

**Description**: Create formal operational acceptance plan, machine-readable cases JSON, result template, and risk boundary documents.

**Delivered**:
- `subsystem_operational_acceptance_plan.md` — full acceptance plan with 20 domains, 6 layers
- `subsystem_operational_acceptance_cases.json` — ~195 cases covering all 20 systems
- `subsystem_operational_acceptance_result_template.md` — per-case result recording template
- `subsystem_operational_acceptance_risk_boundary.md` — binding safety contract

**Constraints**:
- Docs only — no runtime code changes
- No test modifications
- No token access
- No real-send

---

### R246C–R246H — Operational Acceptance Execution Phases

| Phase | Content | Constraints |
|-------|---------|-------------|
| R246C | L0 Foundation + L1 Main Chain + L3 MCP | dry-run only |
| R246D | L2 Path A Local Execution + L4 RTCM/AUTO/MEM | dry-run only |
| R246E | L4 PROMPT/EVO/TOOL | dry-run only |
| R246F | L4 ASSET/REPORT/NIGHTLY/CLI | dry-run only |
| R246G | L5 Security/Hygiene | no token access |
| R246H | Final analysis + gap summary | deferred fixes only |

**All phases**: No runtime code changes, no test changes, no real-send, no Agent-S.

---

### R247X — Targeted Fix Plan (If Gaps Found)

**Status**: DEFERRED

**Description**: If R246C–R246H execution reveals defects requiring code changes, create targeted fix plan.

**Trigger**: Any case returns `NEEDS_TARGETED_FIX`.

**Required before start**:
- Gap analysis from R246H complete
- Defect list documented
- Fix scope defined

**Constraints**:
- Fix-only scope — no new features
- Separate PR — not mixed with acceptance docs
- Test coverage for fix validated

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-07 | R245X — future roadmap documented; R240X/R241X/R242X/Nightly daemon deferred with explicit constraints and sequence |
| 2026-05-07 | R246B — operational acceptance plan files created; R246C–R246H execution phases defined; R247X targeted fix deferred |
