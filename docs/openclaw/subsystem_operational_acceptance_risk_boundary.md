# OpenClaw Subsystem Operational Acceptance Risk Boundary

## Purpose

Defines what R246 operational acceptance may and may not do. This document is the **binding safety contract** for all R246C–R246H execution phases.

---

## Allowed Operations

The following operations are permitted during R246 operational acceptance:

### Source and Documentation Access

- Import of **tracked source code** only (in `backend/app/openclaw/`, `backend/app/openclaw_cli/`)
- Import smoke of tracked Python modules
- Reading **tracked documentation** only (in `docs/openclaw/`)
- Reading configuration files (`config.yaml`, `app_config.yaml`)

### Testing and Validation

- Running **focused test suites** for specific subsystems under test
- Running **import smoke tests** for module verification
- Running **pytest** with specific test files (not full suite unless warranted)
- Running **ruff** linting checks
- CLI smoke tests with explicit `--output` / `--store` temp paths

### Dry-Run Execution

- All CLI dry-run commands (asset-dry-run, rtcm-dry-run, nightly-run-once-preview)
- Export to **explicit temp paths** (`/tmp/`, `TEMP`, etc.)
- JSONL store operations with **explicit output path**
- Result collection under `.deerflow/operational_acceptance/R246/` (untracked)

### Output Management

- Writing evidence to **temp paths** only
- Writing export files to **explicit output paths** (no defaults)
- Creating **untracked evidence files** under `.deerflow/operational_acceptance/`
- Collecting test output for documentation

---

## Forbidden Operations

The following are **absolutely forbidden** at all times, including during acceptance testing:

### Token and Credential Access

- **NEVER** read `token_cache.json` content
- **NEVER** print, copy, or log token values
- **NEVER** use tokens from `token_cache.json` in any operation
- **NEVER** access credentials from any untracked file

### External API Operations

- **NEVER** call Feishu/Lark real-send API (`/open-apis/bot/v2/hook/`)
- **NEVER** send real messages to any Feishu channel
- **NEVER** make real external network calls (except necessary Tavily MCP via stdio)

### External Runtime

- **NEVER** invoke Agent-S (`external/Agent-S/`)
- **NEVER** execute any external untracked runtime
- **NEVER** use `.deerflow/rtcm/` as runtime input
- **NEVER** use `.deerflow/operation_assets/` as runtime input

### Background and Scheduling

- **NEVER** start daemon or background worker
- **NEVER** create cron or scheduled task
- **NEVER** implement auto-start on module import
- **NEVER** use Nightly Review daemon/scheduler

### Production Operations

- **NEVER** write to production database
- **NEVER** modify production configuration
- **NEVER** perform production deployment operations

### Git Operations

- **NEVER** run `git add .`
- **NEVER** run `git clean -fd`
- **NEVER** run `git reset --hard`
- **NEVER** run `git push --force`
- **NEVER** merge branches
- **NEVER** modify CI configuration

---

## Stop Conditions

**Stop immediately and request authorization** if any of the following occur:

| Stop Condition | Trigger | Required Action |
|---------------|---------|----------------|
| Real-send requested | Feishu/Lark real API call attempted | Stop, document, escalate to operator |
| Token access needed | `token_cache.json` access requested | Stop, document, escalate to operator |
| Agent-S execution needed | Agent-S runtime invocation requested | Stop, document, escalate to operator |
| Daemon/cron needed | Background scheduler requested | Stop, document, escalate to operator |
| Production DB needed | Production write requested | Stop, document, escalate to operator |
| External network needed | Real external call requested | Stop, document, escalate to operator |
| Runtime code change needed | Backend code modification needed | Stop, create fix task, do not modify |
| Test change needed | Test modification requested | Stop, create fix task, do not modify |

When stopping, record:
1. Case ID that triggered the stop
2. What was requested
3. Why it was rejected
4. What authorization would be needed
5. Output to `docs/openclaw/subsystem_operational_acceptance_stops.md`

---

## External Dependency Handling

The following are **known external dependencies** that are not yet available. When encountered, mark as `DEFERRED_EXTERNAL` and continue:

| Dependency | Reason | Status |
|-----------|--------|--------|
| Lark MCP SDK | SDK bug in stdio transport mode; Tavily MCP adopted as alternative | DEFERRED (SDK bug) |
| Exa MCP credentials | Credentials not available | DEFERRED (no credentials) |
| Feishu real-send | Token rotation deferred by operator | DEFERRED (operator action) |
| Agent-S adapter | External runtime unknown; dry-run only | DEFERRED (R241X spike) |
| RTCM real-agent | Architecture not designed; dry-run only | DEFERRED (R242X design) |
| Nightly daemon | Explicitly forbidden; manual scheduler only | DEFERRED (design deferred) |

---

## Future Authorization Boundary

The following require **separate future phases** with **explicit operator authorization**:

| Phase | What It Does | Required Authorization |
|-------|-------------|------------------------|
| R240X | Feishu real-send controlled verification | Operator explicit authorization + `FEISHU_TOKEN_ROTATION_ACK=true` |
| R241X | Agent-S adapter spike | Spike-only scope, no production code |
| R242X | RTCM real-agent strategy design | Design-only, no implementation |
| Nightly daemon/cron | Scheduler design (R218) | Explicit design document + lifecycle model |

**Do not merge R240X/R241X/R242X into current delivery PR.**

---

## Safety Checklist

Before starting each R246 group execution, verify:

- [ ] Working in correct branch (not main)
- [ ] No uncommitted changes to backend code
- [ ] No test changes staged
- [ ] `token_cache.json` not in current directory
- [ ] `.deerflow/rtcm/` not being used
- [ ] `.deerflow/operation_assets/` not being used
- [ ] `external/Agent-S/` not in use
- [ ] Only dry-run CLI commands planned
- [ ] Only explicit temp output paths planned
- [ ] CI config not modified

---

## Evidence Handling

All evidence collected during R246C–R246H:

- Stored under `.deerflow/operational_acceptance/R246/` (untracked)
- Referenced by path in cases.json `evidence_required` field
- Not committed to git
- Summarized in per-group result docs

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-07 | R246B — risk boundary created |
