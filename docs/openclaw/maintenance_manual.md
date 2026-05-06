# OpenClaw Maintenance Manual

## Purpose

This manual describes how to maintain the current OpenClaw delivery without violating the frozen safety boundaries. All operators should read this before making any changes to the tracked codebase.

---

## Golden Rules

These rules are **non-negotiable** for the current delivery:

1. **Do not read `token_cache.json`** — do not access, print, or copy it
2. **Do not commit `.deerflow/rtcm/`** — operational data must never enter tracked git
3. **Do not commit `.deerflow/operation_assets/`** — same constraint applies
4. **Do not invoke Agent-S** unless a separate adapter spike is explicitly authorized (R241X)
5. **Do not perform Feishu/Lark real-send** without a controlled verification stage (R240X)
6. **Do not add daemon / cron** without a scheduler lifecycle design (R218/R244X deferred)
7. **Do not claim production real-agent RTCM runtime** — dry-run only (R242X deferred)
8. **Keep dry-run and real execution paths separated** — never remove `--real` rejection

---

## Local Sync

From the repo root:

```powershell
cd E:\OpenClaw-Base\deerflow
git checkout main
git pull private main
git status -sb
git log --oneline -12
```

Verify:
- Branch is `main`
- HEAD is at a known good state
- No staged or modified files

---

## Focused Validation

Run before any significant change to confirm the system is healthy:

```powershell
cd E:\OpenClaw-Base\deerflow\backend

uv run pytest `
  tests/test_openclaw_operator_cli.py `
  tests/test_openclaw_integration_smoke.py `
  tests/test_asset_runtime_registry.py `
  tests/test_asset_runtime_dry_run.py `
  tests/test_rtcm_dry_run_runtime.py `
  tests/test_nightly_review_pipeline.py `
  tests/test_nightly_review_scheduler.py `
  tests/test_m04_registry_manager.py `
  -q
```

Expected: **220+ passed** (1 pre-existing type-assertion failure in `test_list_capabilities_returns_list` is acceptable — it is a type contract issue, not a functional failure).

---

## Operator CLI Smoke

Test the CLI is responsive:

```bash
python -m app.openclaw_cli.console list
python -m app.openclaw_cli.console capability-summary
python -m app.openclaw_cli.console asset-dry-run --capability asset.plan
python -m app.openclaw_cli.console rtcm-dry-run
python -m app.openclaw_cli.console nightly-dry-run
```

For export commands, **always use explicit temp paths**:

```bash
# Use temp directories — never write to .deerflow/
python -m app.openclaw_cli.console rtcm-dry-run-export --output "$env:TEMP\openclaw\rtcm.md"
python -m app.openclaw_cli.console nightly-export --store-path "$env:TEMP\openclaw\nightly.jsonl" --output "$env:TEMP\openclaw\nightly.md"
```

---

## Security Hygiene Checks

Run these to confirm the `.gitignore` guards are effective:

```bash
# Confirm no sensitive operational files are tracked
git ls-files .deerflow/rtcm/
git ls-files .deerflow/operation_assets/
git ls-files "**/token_cache.json"

# Confirm ignore rules are active
git check-ignore -v .deerflow/rtcm/
git check-ignore -v .deerflow/operation_assets/
git check-ignore -v "**/token_cache.json"
```

Expected: no output from `git ls-files`; ignore rules confirmed active.

---

## Adding New Runtime Features

When adding new runtime features:

1. **Read this manual first** — confirm the feature doesn't violate golden rules
2. **Check `deferred_future_work.md`** — if the feature is deferred, do not implement without separate authorization
3. **Maintain dry-run / real separation** — any new capability must have a dry-run path that is the default
4. **Add safety tests** — monkeypatch `builtins.open` to confirm no forbidden paths are accessed
5. **Update docs** — capability matrix, operator quickstart, maintenance manual

---

## When to Stop and Request Authorization

Stop and escalate if any of the following are requested:

- New runtime files need modification in `backend/app/`
- Feishu real-send is requested for any runtime
- Token access is needed for any purpose
- Agent-S integration is requested
- RTCM real-agent execution is requested
- Daemon / cron / background worker is requested
- Production DB or external side effects are involved
- Operational data (`.deerflow/rtcm/` or `.deerflow/operation_assets/`) needs to be committed

---

## Key File Locations

| Purpose | Location |
|--------|----------|
| Operator CLI | `backend/app/openclaw_cli/` |
| Asset runtime | `backend/app/asset_runtime/` |
| RTCM runtime | `backend/app/rtcm/` |
| Nightly Review | `backend/app/nightly_review/` |
| Capability matrix | `docs/openclaw/capability_matrix.md` |
| Deferred future work | `docs/openclaw/deferred_future_work.md` |
| Final delivery candidate | `docs/openclaw/final_delivery_candidate.md` |
| System acceptance matrix | `docs/openclaw/system_capability_acceptance_matrix.md` |
| Operator quickstart | `docs/openclaw/operator_quickstart.md` |
| Release claims | `docs/openclaw/release_claims.md` |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-07 | R245X — maintenance manual created; golden rules, validation, hygiene checks, escalation path |
