# R241-25E BRANCH DIVERGENCE ANALYSIS

**Phase:** R241-25E — Branch Divergence Analysis
**Generated:** 2026-04-29
**Status:** COMPLETE
**Preceded by:** R241-25D
**Proceeding to:** R241-25F (hygiene cleanup authorization)

---

## LANE 1 — Scope Gate

| Check | Result |
|-------|--------|
| Current branch | `r241/auth-disabled-wiring-v2` |
| HEAD | `29f8ed8a` |
| origin/main SHA | `4a9f1d54` |
| private/main SHA | `8f69ffce` |
| Tracked modifications | 0 |
| Git fetch executed | YES |
| Read-only mode | CONFIRMED |

---

## LANE 2 — SRC-004: credential_file.py Diff

### Existence
| Branch | Exists | SHA |
|--------|--------|-----|
| origin/main | YES | `100ca3b0...` |
| private/main | **NO** | — |

### Content Summary
`credential_file.py` — **Write initial admin credentials to a restricted file.**

Core function: `write_initial_credentials(email, password, *, label="initial")`
- Writes to `{base_dir}/admin_initial_credentials.txt` with **mode 0600** (owner-only read/write)
- Atomic file creation via `os.open` with `O_WRONLY | O_CREAT | O_TRUNC`
- File format: plain text with email + password, labeled as "initial" or "reset"
- **No database calls** — pure credential file bootstrap
- **No init_engine** — safe to add without triggering production DB

### Risk Assessment
| Dimension | Value |
|-----------|-------|
| Risk | **LOW** |
| Calls init_engine | NO |
| DB write on import | NO |
| File write | YES (mode 0600) |
| Activation blocking | YES (bootstrap gap) |

### Conclusion
`credential_file.py` exists on `origin/main` but is **absent from private/main**. This directly corresponds to the "credential_bootstrap" production gap identified as **BLOCKING** in R241-24L.

**Action needed:** Decide whether to import `credential_file.py` into private/main's auth flow, or implement an alternative bootstrap mechanism.

**Outcome:** `divergence_requires_decision`

---

## LANE 3 — SRC-005: reset_admin.py Diff

### Existence
| Branch | Exists | SHA |
|--------|--------|-----|
| origin/main | YES | `7b7da74d...` |
| private/main | **NO** | — |

### Content Summary
`reset_admin.py` — **CLI tool to reset admin password.**

Core function: `_run(email)` async function
- Calls `await init_engine_from_config(config.database)` — **PRODUCTION_DB_BLOCKER**
- Calls `repo.update_user(user)` — **DB write**
- Calls `write_initial_credentials()` — credential file write
- Finds admin via `SELECT ... WHERE system_role = 'admin'` direct SQL
- CLI entrypoint with `argparse`

### Risk Assessment
| Dimension | Value |
|-----------|-------|
| Risk | **HIGH** |
| Calls init_engine | YES |
| DB write | YES |
| Activation blocking | NO (CLI tool, not activation gate) |

### Conclusion
`reset_admin.py` exists on `origin/main` but is **absent from private/main**. It is a **CLI operational tool**, not part of the auth activation gate. It directly calls production DB init and should NOT be imported into private/main without explicit production_DB authorization.

**This is NOT a blocking gap for auth activation** — it is a non-blocking operational gap.

**Outcome:** `safe_to_defer`

---

## LANE 4 — Auth Activation Impact Review

### Full Auth Directory Divergence

```
backend/app/gateway/auth/
  ─ credential_file.py   [origin only — MISSING on private] ← BLOCKING
  ─ reset_admin.py       [origin only — MISSING on private] ← deferred
  ─ csrf_middleware.py   [origin only — MISSING on private] ← non-blocking
  ─ config.py            [modified between branches]
  ─ errors.py             [modified between branches]
  ─ local_provider.py     [modified between branches]
  ─ password.py          [modified between branches]
  ─ providers.py          [modified between branches]
  ─ repositories/*        [modified between branches]
```

### Production Gap Mapping (R241-24L)

| Gap ID | Description | Status | Corresponding File |
|--------|-------------|--------|-------------------|
| `schema_ownership` | No explicit migration system | BLOCKING | N/A — deeper issue |
| `credential_bootstrap` | No pre-existing users; first admin creation | **BLOCKING** | `credential_file.py` (origin only) |
| `route_authorization` | Full audit of all /api routes incomplete | BLOCKING | N/A — audit needed |
| `reset_admin` | No admin password reset mechanism | NON-BLOCKING | `reset_admin.py` (origin only) |

### Activation Blocking Gap Confirmed: YES

**`credential_file.py` is the critical missing piece for auth activation.**

Without `credential_file.py` (or an equivalent mechanism), there is **no secure path to create the initial admin credentials** during auth activation on private/main.

**However:** `credential_file.py` itself is safe to add — it has NO DB dependencies, NO init_engine calls. The question is whether/how the auth activation flow should call it.

### Production Risk: MEDIUM

Risk: How does first-admin creation work on private/main?

The `register` endpoint can create users, but the `credential_file.py` bootstrap mechanism (writing initial credentials to a secure file) is absent. This means:
- First admin setup on private/main would require an alternative mechanism
- The file-based credential bootstrap is a DeerFlow-specific security enhancement (avoids logging secrets)

---

## LANE 5 — PR #2645 Passive Recheck

| Item | Value |
|------|-------|
| State | OPEN |
| Mergeable | true |
| Mergeable state | blocked |
| CI triggered | license/cla=success; all others=not triggered |
| CI missing | true |

---

## LANE 6 — Outcome Classification

| SRC | Outcome | Rationale |
|-----|---------|----------|
| SRC-004 | `divergence_requires_decision` | credential_file.py missing on private; low-risk file but BLOCKING for auth activation |
| SRC-005 | `safe_to_defer` | reset_admin.py missing; high-risk CLI with DB access; non-blocking for activation |

---

## LANE 7 — Recommendation

### Recommended: R241-25F — Hygiene Cleanup Authorization

**Candidates:** SRC-006, SRC-007

**Scope:**
- Authorize deletion of `packages/harness/deerflow/scratch/` contents
- Authorize deletion of `backend/_debug*.py` (5 files)

**Why next:**
- Both are low-risk hygiene cleanups
- R241-25F requires explicit user authorization for file deletion
- R241-25E findings (credential_file gap) should be addressed separately via R241-25I or a dedicated auth activation review

### Alternative: R241-25I — Auth Activation Review
If user wants to immediately address the credential_file.py bootstrap gap.

### Phase Sequence (updated)
```
R241-25E → DONE (divergence analyzed)
R241-25F → scratch/debug cleanup ← NEXT (authorization needed)
R241-25G → report pruning (authorization needed)
R241-25H → PR #2645 passive monitoring (no auth)
R241-25I → auth activation review (authorization needed for review scope)
```

---

## Key Findings Summary

1. **`credential_file.py`** — origin/main only, private/main missing. **BLOCKING for auth activation.** Low-risk file (no DB). Decision needed: import or alternative.

2. **`reset_admin.py`** — origin/main only, private/main missing. **NOT blocking.** High-risk CLI (calls init_engine). Should be deferred.

3. **Full auth divergence** — 8 modified files + 3 origin-only files between branches. The auth infrastructure on private/main has been reworked vs. origin/main.

4. **Production risk confirmed** — credential bootstrap gap remains BLOCKING on private/main.

---

## Blockers Preserved

- Production SQLite binding — BLOCKED
- Production Postgres binding — BLOCKED
- CAND-003 MCP binding — BLOCKED
- DSRT — DISABLED
- Actual gateway activation — BLOCKED
- `MAINLINE_GATEWAY_ACTIVATION=false` — CONFIRMED
- `AUTH_MIDDLEWARE_ENABLED=false` — CONFIRMED
- `AUTH_ROUTES_ENABLED=false` — CONFIRMED

---

## Hard Prohibitions

```
NO code modification
NO deletion of untracked files
NO git clean / git add
NO reset / stash
NO AUTH flags enablement
NO production init_engine
NO DB writes
NO JSONL writes
NO gateway activation
NO dependency installation
NO pyproject modification
NO push to main
NO merge PR #2645
NO blocker override
```

---

## Compliance

| Metric | Value |
|--------|-------|
| Code modified | **false** |
| DB written | **false** |
| JSONL written | **false** |
| Gateway activation allowed | **false** |
| Production DB write allowed | **false** |
| Push main executed | **false** |
| Merge executed | **false** |
| Blockers preserved | **true** |
| Safety violations | **[]** |

---

*Generated by Claude Code — R241-25E LANE 7 (Report Generation)*
