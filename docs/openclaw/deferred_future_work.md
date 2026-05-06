# Deferred Future Work

These items are intentionally deferred from the current OpenClaw vNext enhancement cycle. Each item has a defined boundary and explicit constraints that must be respected before any future implementation.

---

## R240X — Feishu Real-Send Controlled Verification

**Status**: DEFERRED

**Reason**: Requires real credentials, explicit operator authorization, and isolated controlled verification. This is a production-side-effect operation that cannot be mixed with dry-run runtime work.

**Required preconditions before work begins**:
1. Operator rotates Feishu bot token via open.feishu.cn → credentials → revoke
2. New token stored in operator-managed vault (not `.deerflow/rtcm/token_cache.json`)
3. `FEISHU_TOKEN_ROTATION_ACK=true` set in environment
4. Separate controlled-verification PR authorized by operator

**Allowed future scope**:
- Dedicated controlled verification PR (isolated from other runtime work)
- Explicit operator-provided target channel/recipient
- Integration test with real Feishu bot
- `--real` flag implementation behind explicit operator opt-in

**Forbidden before separate authorization**:
- Production claim of Feishu real-send capability
- Automatic real-send in any runtime path
- Logging or printing of any token value
- Real-send mixed into same PR as other runtime features

---

## R241X — Asset External Agent-S Adapter Spike

**Status**: DEFERRED

**Reason**: The `external/Agent-S/` directory is outside tracked runtime. Adapter integration may expand scope unpredictably. A dedicated spike with explicit boundary is required before any production claim.

**Required preconditions before work begins**:
1. Research spike evaluating Agent-S CLI interface and capability surface
2. Adapter interface design reviewed and approved
3. No production claim before spike completes

**Allowed future scope**:
- SPIKE only (research, no production code)
- Adapter interface definition
- Dry-run capability (no real Agent-S invocation)
- Explicit opt-in for external Agent-S call

**Forbidden before separate authorization**:
- Claiming "Asset runtime fully implemented"
- Invoking Agent-S in any automated test
- Reading `.deerflow/operation_assets/` as runtime source
- Mixing Agent-S work into same PR as other runtime features

---

## R242X — RTCM Real-Agent Strategy Design

**Status**: DEFERRED

**Reason**: Real-agent orchestration is a separate architecture problem from the dry-run consensus runtime. The report delivery, agent handoff, and side-effect controls each need independent design before production implementation.

**Required preconditions before work begins**:
1. RTCM dry-run runtime accepted (current PR #18)
2. Architecture design document for real-agent handoff
3. Separate decision on consensus vs. single-decision-maker approach
4. No real-agent execution before architecture approval

**Allowed future scope**:
- Design-only first (R242X as design phase)
- Integration helpers for dry-run promotion path
- Report delivery mechanism design
- External agent interface definition

**Forbidden before separate authorization**:
- RTCM real-agent execution in any automated pipeline
- Production claim of "RTCM runtime fully implemented"
- Consuming `.deerflow/rtcm/` operational data as runtime input
- Feishu real-send from RTCM runtime before R240X closure

---

## Nightly Review Scheduler Daemon / Cron / Background Worker

**Status**: DEFERRED

**Reason**: Current delivery is explicit manual scheduler and export only. Background execution introduces lifecycle management, failure recovery, and production operational risk that requires separate design and explicit operator authorization.

**Required preconditions before work begins**:
1. Manual scheduler and export accepted (current PR #11)
2. Explicit scheduler design document (R218)
3. No auto-start on import (absolute requirement)
4. cron or systemd timer unit designed separately
5. No silent background worker behavior

**Allowed future scope**:
- Explicit CLI-triggered scheduler invocation
- cron job or systemd timer unit design
- Lifecycle management (start/stop/status)
- Failure recovery and retry logic
- Health monitoring endpoint

**Forbidden before separate authorization**:
- Auto-starting any background worker on module import
- Silent daemon behavior without explicit CLI invocation
- Automatic scheduling without operator-configured cron
- Production claim of "Nightly Review daemon implemented"

---

## Summary of Deferred Items

| Item | Type | Key Constraint | Unblocks |
|------|------|---------------|----------|
| R240X Feishu real-send | production verification | `FEISHU_TOKEN_ROTATION_ACK=true` | Full Feishu claim |
| R241X Agent-S adapter spike | research | No production code | Asset real integration |
| R242X RTCM real-agent design | architecture design | Design-first, no execution | RTCM full implementation |
| Nightly daemon/cron | operational | No auto-start on import | Automated scheduling |

---

## Carry-Forward Rules (Non-Negotiable)

All future work on deferred items must respect:

1. **Token origin**: Credentials must come from `app_config.lark`, never from `.deerflow/rtcm/token_cache.json`
2. **No operational data as runtime**: `.deerflow/rtcm/` and `.deerflow/operation_assets/` are never imported or read
3. **Explicit opt-in**: `--real` flag required for any real API call; dry-run is always the default
4. **No mixed PRs**: Deferred items do not mix with other runtime features in the same PR
5. **S-RTCM-FEISHU-TOKEN-001 remains OPEN**: No "security fully clean" claim until operator rotation confirmed

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | R243X — deferred future work documented; R240X/R241X/R242X and Nightly daemon defined with explicit boundaries; carry-forward rules confirmed |
