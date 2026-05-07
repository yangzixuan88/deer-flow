# OpenClaw Operator Quickstart

## Status

**AVAILABLE_WITH_LIMITS**

Operator-facing capabilities of the current OpenClaw delivery.

---

## What Operators Can Do Now

Operators can safely run dry-run and explicit export commands **without external credentials** or network access.

**Important**: All current capabilities are dry-run only. Real execution (Feishu send, Agent-S, RTCM real-agent, daemon) is explicitly deferred.

---

## Prerequisites

From `backend/` directory:

```bash
cd E:\OpenClaw-Base\deerflow\backend
```

---

## List Available Commands

```bash
python -m app.openclaw_cli.console list
```

Shows all 9 available commands with categories and descriptions.

---

## Check System Capabilities

```bash
python -m app.openclaw_cli.console capability-summary
```

Shows runtime status for Nightly Review, Asset, and RTCM.

---

## Asset Runtime

Dry-run Asset operations — no Agent-S is invoked:

```bash
# No-op capability
python -m app.openclaw_cli.console asset-dry-run --capability asset.noop

# Planning capability
python -m app.openclaw_cli.console asset-dry-run --capability asset.plan

# Package capability (external required — dry-run returns warning)
python -m app.openclaw_cli.console asset-dry-run --capability asset.package
```

Available capabilities: `asset.noop`, `asset.plan`, `asset.preview`, `asset.validate`, `asset.package`, `asset.publish`

**Notes**:
- No Agent-S invocation in any dry-run path
- External-required capabilities return a warning but do not fail
- No `.deerflow/operation_assets` is read

---

## RTCM Roundtable

Run a dry-run roundtable consensus:

```bash
python -m app.openclaw_cli.console rtcm-dry-run
```

Export the latest decision to markdown:

```bash
python -m app.openclaw_cli.console rtcm-dry-run-export --output "$env:TEMP\openclaw\rtcm.md"
```

Build an index from an explicit store:

```bash
python -m app.openclaw_cli.console rtcm-report-index --store "$env:TEMP\openclaw\rtcm.jsonl"
```

**Notes**:
- No `.deerflow/rtcm` is read
- No real agents are consulted
- No Feishu/Lark messages are sent
- All paths are explicit (no default operational paths)

---

## Nightly Review

Run a dry-run review:

```bash
python -m app.openclaw_cli.console nightly-dry-run
```

Preview scheduler capabilities:

```bash
python -m app.openclaw_cli.console nightly-schedule-preview
```

Export items to markdown:

```bash
python -m app.openclaw_cli.console nightly-export --store-path "$env:TEMP\openclaw\nightly.jsonl" --output "$env:TEMP\openclaw\nightly.md"
```

Preview run-once without sending:

```bash
python -m app.openclaw_cli.console nightly-run-once-preview --store-path "$env:TEMP\openclaw\nightly.jsonl"
```

**Notes**:
- No daemon is started
- No cron is configured
- No real Feishu/Lark messages are sent
- Explicit `--real` flag is **rejected** (exit code 2)

---

## Real Execution

**The current Operator CLI is dry-run / explicit export only.**

```bash
# This will fail with exit code 2
python -m app.openclaw_cli.console asset-dry-run --real
```

The `--real` flag is intentionally rejected. Real execution requires separate controlled verification (R240X).

---

## Quick Reference

| Command | Purpose | Real Send? |
|---------|---------|-----------|
| `list` | Show all commands | No |
| `capability-summary` | Show runtime statuses | No |
| `asset-dry-run --capability X` | Dry-run asset operation | No |
| `rtcm-dry-run` | Dry-run roundtable consensus | No |
| `rtcm-dry-run-export --output <path>` | Export decision to markdown | No |
| `rtcm-report-index --store <path>` | Build index from explicit store | No |
| `nightly-dry-run` | Dry-run nightly review | No |
| `nightly-schedule-preview` | Show scheduler capabilities | No |
| `nightly-export --output <path>` | Export to markdown | No |
| `nightly-run-once-preview` | Preview without sending | No |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-07 | R245X — operator quickstart created; commands, capabilities, quick reference table |
