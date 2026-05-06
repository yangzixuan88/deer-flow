# OpenClaw vNext Enhancement Closeout

## Status

**VNext enhancement scope is closed** for the current delivery cycle. No additional runtime features will be added before system-level capability acceptance.

---

## Enhancement Delivery Summary

This cycle delivered three major enhancements to the OpenClaw dry-run runtime system, all implemented within strict safety boundaries.

### R237X — Operator CLI Dry-run Console

**Status**: COMPLETE

**Delivered**:
- Unified operator CLI entry point (`python -m app.openclaw_cli.console`)
- `list` command — enumerate all registered commands
- `capability-summary` command — show all runtime statuses
- Nightly Review commands: `nightly-dry-run`, `nightly-schedule-preview`, `nightly-export`, `nightly-run-once-preview`
- Asset commands: `asset-dry-run` with capability selection
- RTCM commands: `rtcm-dry-run`, `rtcm-dry-run-export`, `rtcm-report-index`
- JSON output for all commands
- `--real` flag explicitly rejected (exit code 2)
- No credential access; no operational data reads

**Evidence**: PR #16 merged (20e77145); 37 tests passing

---

### R238X — Asset Capability Registry

**Status**: COMPLETE

**Delivered**:
- Tracked `default_capabilities.json` with 6 dry-run capabilities
- `registry.py` loader and validator using `importlib.resources`
- `DryRunAssetRuntimeAdapter` wired to capability registry
- Operator CLI `--capability` flag for asset dry-run selection
- No `.deerflow/operation_assets` read; no Agent-S invocation

**Evidence**: PR #17 merged (29e5aad9); 42 tests passing

---

### R239X — RTCM / Nightly Export Hardening

**Status**: COMPLETE

**Delivered**:
- RTCM JSONL store hardening: `get()`, `latest()`, `list_records(limit)`, `export_json()`, `export_markdown()`
- Malformed-line skip for resilient store reading
- RTCM reporter: `build_markdown_index()`, `build_json_index()` for multi-record reports
- Nightly CLI: `--output` flag for markdown export
- Operator CLI export commands: `rtcm-dry-run-export`, `rtcm-report-index`, `nightly-export`, `nightly-run-once-preview`
- Explicit-path design: no default `.deerflow/rtcm` in any export path

**Evidence**: PR #18 merged (f921339c); 58 tests passing

---

## Closed Enhancement Boundary

### Included in Current Delivery

| Component | What's Available |
|-----------|-----------------|
| Gateway / repair | Health endpoint, run route, auth isolation |
| Memory | Branch fully validated |
| Prompt / Skill / Tool | Registry and execution validated |
| Upgrade Center | Test coverage complete |
| Feishu / Report | Dry-run boundary confirmed |
| Nightly Review | Dry-run + manual scheduler + explicit export |
| Asset Runtime | Dry-run adapter + tracked capability registry |
| RTCM Roundtable | Dry-run runtime + store/export/index |
| Operator CLI | Unified dry-run/export console |
| Security | `.gitignore` hygiene guard active |

### Excluded from Current Delivery

The following are intentionally **not** part of this cycle:

| Item | Reason |
|------|--------|
| Feishu real-send | Requires credential rotation and controlled verification |
| Agent-S adapter spike | External runtime needs separate boundary |
| RTCM real-agent runtime | Architecture decision deferred |
| Nightly daemon / cron | Lifecycle and production risk |
| Automatic background worker | No auto-start on import mandate |

---

## Enhancement Freeze Decision

**No additional vNext runtime features** should be added before system-level capability acceptance (R244X).

All delivered capabilities are classified as **AVAILABLE_WITH_LIMITS** — they work within defined dry-run boundaries but are not production-verified for real external side effects.

---

## Next Phase

**R244X — System-Level Capability Acceptance Matrix**

The next phase focuses on:
- Operator-facing delivery summary
- Capability classification with evidence
- Forbidden claims audit
- Final freeze of allowed vs. prohibited public statements

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | R243X — vNext enhancement closeout freeze documented; R237X/R238X/R239X marked complete; next phase R244X |
