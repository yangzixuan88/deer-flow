# OpenClaw Release Claims

## Purpose

This document defines what can and cannot be claimed publicly about the current OpenClaw delivery. Follow these guidelines when communicating about the system.

---

## Allowed Claims

The following statements **can be made** publicly:

### System Status
- "OpenClaw repair plan v2 is complete"
- "OpenClaw post-closeout hardening is complete"
- "vNext enhancement scope is frozen"
- "System-level capability acceptance is complete"
- "FINAL_DELIVERY_READY"

### Core Capabilities
- "Gateway / DeerFlow main chain has been repaired and validated"
- "Run / status / result closure has been accepted"
- "Memory, Prompt / Skill / Tool, and Upgrade Center have validated test coverage"

### Dry-Run Runtimes
- "Nightly Review dry-run pipeline is available"
- "Nightly Review manual scheduler and explicit export are implemented"
- "Asset dry-run runtime is available with tracked capability registry"
- "RTCM dry-run runtime is available with store, export, and report index"
- "OpenClaw Operator CLI provides a unified dry-run and explicit export console"

### Security
- "Operational data gitignore guard is active"
- "S-RTCM-FEISHU-TOKEN-001 is open and operator-deferred"
- "Token rotation is required before full security claims"

### Capability Counts
- "15 capabilities accepted: 8 AVAILABLE, 7 AVAILABLE_WITH_LIMITS"
- "No BLOCKED capabilities in the accepted delivery scope"

---

## Forbidden Claims

The following statements **must NOT be made**:

| Forbidden Claim | Why |
|----------------|-----|
| "Security fully clean" | S-RTCM-FEISHU-TOKEN-001 remains open |
| "Feishu real-send production verified" | Only dry-run verified; real-send deferred |
| "Agent-S integrated" | No Agent-S integration; dry-run adapter only |
| "Asset production execution verified" | Only dry-run adapter exists |
| "RTCM production runtime verified" | Only dry-run runtime; real-agent deferred |
| "RTCM real agents integrated" | No real agent handoff |
| "Nightly daemon implemented" | No daemon; manual scheduler only |
| "Nightly cron scheduler implemented" | No cron; explicit CLI-trigger only |
| "Fully autonomous production operation" | All side effects are dry-run or deferred |
| "External side effects are safe by default" | Requires separate controlled verification |

---

## Required Wording for Limited Capabilities

When describing the following capabilities, **always** use "AVAILABLE_WITH_LIMITS" and include the limitation:

| Capability | Required Wording | Limitation |
|-----------|----------------|------------|
| Feishu / Report | AVAILABLE_WITH_LIMITS | Dry-run only; real-send deferred |
| Nightly Review | AVAILABLE_WITH_LIMITS | No daemon/cron; manual scheduler only |
| Asset Runtime | AVAILABLE_WITH_LIMITS | Dry-run adapter only; no Agent-S |
| RTCM Roundtable | AVAILABLE_WITH_LIMITS | Dry-run runtime only; no real agents |
| Operator CLI | AVAILABLE_WITH_LIMITS | Dry-run / explicit export only; `--real` rejected |
| MCP external tools | AVAILABLE_WITH_LIMITS | Tavily works; Lark deferred; credentials required |
| Path A external flows | AVAILABLE_WITH_LIMITS | External executor availability varies |

**Example**: "Asset Runtime is AVAILABLE_WITH_LIMITS — a dry-run adapter with tracked capability registry exists, but no real Agent-S integration is available."

---

## Claim Construction Guide

### Correct Example
> "Nightly Review is AVAILABLE_WITH_LIMITS — a dry-run pipeline and manual scheduler are implemented. Real Feishu/Lark send is deferred to a future controlled verification stage."

### Incorrect Example
> "Nightly Review is available with a scheduler" (implies daemon/cron exists — forbidden)

### Incorrect Example
> "Feishu real-send works" (implies production verified — forbidden)

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-07 | R245X — release claims documented; allowed/forbidden lists; required wording for limited capabilities |
