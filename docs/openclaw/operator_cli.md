# OpenClaw Operator CLI — Dry-Run Console

## Overview

`backend/app/openclaw_cli/` provides a unified operator CLI that exposes all tracked dry-run runtimes through a single entry point. Operators can inspect system capabilities and execute dry-run simulations without network access, credential exposure, or real message delivery.

## Usage

```bash
# List all available commands
python -m app.openclaw_cli.console list

# Show capability summary (all runtimes)
python -m app.openclaw_cli.console capability-summary

# Nightly Review dry-run
python -m app.openclaw_cli.console nightly-dry-run
python -m app.openclaw_cli.console nightly-dry-run --store-path /tmp/nightly.jsonl --limit 10
python -m app.openclaw_cli.console nightly-schedule-preview

# Asset Runtime dry-run
python -m app.openclaw_cli.console asset-dry-run
python -m app.openclaw_cli.console asset-dry-run --payload-summary "test summary"
python -m app.openclaw_cli.console asset-dry-run --capability asset.plan

# RTCM Roundtable dry-run
python -m app.openclaw_cli.console rtcm-dry-run
python -m app.openclaw_cli.console rtcm-dry-run --topic "Custom topic"
```

## Safety Guarantees

| Guarantee | Enforcement |
|-----------|-------------|
| Dry-run only | All commands delegate to `*_dry_run()` paths; `--real` flag is explicitly rejected (exit code 2) |
| No token access | `token_cache.json` never read; verified by `test_no_token_cache_access` safety test |
| No operational data | `.deerflow/rtcm/` and `.deerflow/operation_assets/` never opened; verified by safety tests |
| No network calls | No `requests`, `httpx`, or channel `send()` invoked in dry-run paths |
| No daemon auto-start | `NightlyReviewStore` / scheduler never auto-started on import |

## Commands

| Command | Description |
|---------|-------------|
| `list` | List all registered commands with names, descriptions, and categories |
| `capability-summary` | Show all runtimes with their status and command lists |
| `nightly-dry-run` | Execute Nightly Review dry-run; outputs pending items as JSON |
| `nightly-schedule-preview` | Show scheduler capability (daemon=False, real_send=False) |
| `asset-dry-run` | Execute Asset Runtime dry-run; returns capability + dry_run status |
| `rtcm-dry-run` | Execute RTCM Roundtable dry-run; returns decision record with consensus |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (unknown command, exception) |
| 2 | `--real` flag rejected |

## Architecture

```
app/openclaw_cli/
├── __init__.py          # Public API re-exports
├── commands.py          # OperatorCommand / OperatorCommandResult dataclasses + registry
├── console.py           # main(), run_command(), capability_summary(), argparse setup
└── runtimes/
    ├── __init__.py     # Re-exports all wrapper functions
    ├── nightly.py       # run_nightly_dry_run(), preview_nightly_schedule()
    ├── asset.py         # run_asset_dry_run()
    └── rtcm.py          # run_rtcm_dry_run()
```

Each runtime wrapper:
1. Creates a typed `*Request.new(dry_run=True)` object
2. Delegates to the existing `execute_*_dry_run()` function
3. Maps the result to `OperatorCommandResult` with structured payload
4. Adds dry-run safety warnings

## Asset Capability Registry

Asset dry-run uses a tracked capability registry (`default_capabilities.json`) that enumerates 6 dry-run capabilities:

| Capability | Category | External Runtime Required |
|-----------|----------|-------------------------|
| `asset.noop` | general | No |
| `asset.plan` | planning | No |
| `asset.preview` | preview | No |
| `asset.validate` | validation | No |
| `asset.package` | packaging | Yes (not invoked in dry-run) |
| `asset.publish` | publishing | Yes (not invoked in dry-run) |

The registry is loaded via `importlib.resources` from `app.asset_runtime.capabilities.default_capabilities.json`. The `DryRunAssetRuntimeAdapter` is wired to this registry, so `asset-dry-run --capability asset.X` routes to the appropriate registered capability.

## Relationship to Existing Code

- **Does NOT modify** `app/nightly_review/mode_router.py`
- **Does NOT modify** `app/asset_runtime/adapter.py`
- **Does NOT create new execution paths** — only wraps existing dry-run runtimes
- Uses `argparse` with `parse_known_args()` to intercept `--real` before subparsers

## Test Coverage

42 tests covering:
- Import side-effect isolation
- Command registry completeness
- Each runtime wrapper output structure
- Asset capability registry (18 tests)
- Registry-aware dry-run adapter (8 tests)
- Asset CLI with capability selection (5 tests)
- JSON serializability of all outputs
- Safety: no Feishu send, no network, no token_cache, no .deerflow/rtcm access
- `--real` flag rejection with exit code 2

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | R237X — Unified operator CLI implemented; 37 tests passing; ruff clean |
| 2026-05-06 | R238X — Asset capability registry wired to CLI; 42 tests passing |
