# R241-25I AUTH ACTIVATION REVIEW

**Phase:** R241-25I — Auth Activation Review
**Generated:** 2026-04-29
**Status:** COMPLETE
**Preceded by:** R241-25F
**Proceeding to:** R241-25J (authorization package ready)

---

## LANE 1 — Scope Gate

| Check | Result |
|-------|--------|
| Current branch | `r241/auth-disabled-wiring-v2` |
| HEAD | `29f8ed8a` |
| Tracked modifications | 0 |
| Read-only mode | CONFIRMED |
| R241-25F cleanup verified | YES (scratch empty, debug files gone) |

---

## LANE 2 — credential_file.py Security Review

### credential_file.py Analysis (origin/main SHA: `100ca3b0...`)

| Property | Value |
|----------|-------|
| File | `backend/app/gateway/auth/credential_file.py` |
| On private/main | **MISSING** |
| Risk | **LOW** |
| DB calls | **NONE** |
| init_engine calls | **NONE** |
| File write | `{base_dir}/admin_initial_credentials.txt` (mode 0600) |
| Atomic write | YES (`os.open` with `O_CREAT\|O_WRONLY\|O_TRUNC`) |
| Logging | NONE — caller logs the path, not the password |
| CodeQL fix | Addresses `py/clear-text-logging-sensitive-data` |

### Function: `write_initial_credentials(email, password, *, label="initial")`
- `label="initial"` — first boot credential creation
- `label="reset"` — password reset
- Returns `Path` object (not the password)
- File never world-readable (0600)
- Handles concurrent reset without race condition

### Port Safety Assessment
**CONFIRMED SAFE TO PORT** — zero DB surface, zero init_engine surface, atomic file write.

---

## LANE 3 — Private/Main Bootstrap Gap Review

### What Exists vs. What's Missing

| Component | origin/main | private/main | local working dir |
|-----------|-------------|--------------|-------------------|
| `credential_file.py` | YES | **MISSING** | MISSING (untracked) |
| `/initialize-admin` endpoint | YES | **MISSING** | MISSING |
| `/register` endpoint | YES | **MISSING** | YES (creates `user` role only) |
| `/setup-status` | `count_admin_users()==0` | `count_users()==0` | `count_users()==0` |
| `count_admin_users()` method | YES | **MISSING** | MISSING |
| `LocalAuthProvider` | YES | YES | YES |

### Bootstrap Chain Analysis

**origin/main flow:**
```
credential_file.py writes admin creds to file (mode 0600)
         ↓
operator reads file (stdout shows path only)
         ↓
POST /initialize-admin {email, password}
         ↓
create_user(system_role="admin", needs_setup=False)
         ↓
session cookie set, admin created
```

**private/main flow:**
```
NO PATH — credential_file.py absent, /initialize-admin absent
```

**local working directory flow:**
```
POST /register {email, password}
         ↓
create_user(system_role="user")  ← NOT admin!
         ↓
no admin creation path exists
```

### Gap Confirmed: **BLOCKING**

The `credential_bootstrap` BLOCKING gap from R241-24L is confirmed. private/main lacks ALL of:
1. `credential_file.py` — no file-based bootstrap
2. `/initialize-admin` — no admin creation endpoint
3. `count_admin_users()` — no admin-specific user count

### Severity: **BLOCKING for auth activation**

---

## LANE 4 — reset_admin.py Deferral Confirmation

### reset_admin.py Assessment

| Property | Value |
|----------|-------|
| File | `backend/app/gateway/auth/reset_admin.py` |
| On private/main | **MISSING** |
| Risk | **HIGH** |
| Calls init_engine | YES — `init_engine_from_config(config.database)` |
| DB writes | YES — `repo.update_user()` |
| Activation blocking | **NO** |

**Conclusion:** `reset_admin.py` is a **CLI operational tool**, not part of the auth activation gate. It directly manipulates the production DB and calls `init_engine_from_config`. Must be **deferred** to a future operational tooling phase.

**Defer confirmed: YES**

---

## LANE 5 — Integration Strategy

### Strategy Comparison

| Strategy | Description | Completes Bootstrap | Risk | Execution Allowed |
|----------|-------------|-------------------|------|-----------------|
| A | Port `credential_file.py` only | **NO** | LOW | NO |
| B | Port full bootstrap chain | **YES** | MEDIUM | NO (needs auth) |
| C | Defer until production SQLite review | NO | NONE | N/A |

### Recommended: **Strategy B**

**Full bootstrap port** — requires 3 components:

1. **`credential_file.py`** (LOW risk)
   - From origin/main SHA `100ca3b0`
   - No DB, no init_engine
   - Atomic mode 0600 file write

2. **`/initialize-admin` endpoint** (MEDIUM risk — requires engine)
   - Add to `routers/auth.py`
   - Creates first admin
   - Requires engine initialization (production_DB constraint already blocks)

3. **`count_admin_users()` method** (MEDIUM risk — requires engine)
   - Add to `LocalAuthProvider`
   - Checks `WHERE system_role = 'admin'`
   - Required by `/initialize-admin` gate

### Why Not Strategy A?
`credential_file.py` alone cannot complete the bootstrap. You need `/initialize-admin` to consume the credentials and create the admin user. Strategy A solves the credential generation but not the user creation.

### Strategy B Risk Assessment
- `credential_file.py`: LOW (no DB, no engine)
- `count_admin_users()`: MEDIUM (DB query, but read-only count)
- `/initialize-admin`: MEDIUM (DB write — but controlled by `count_admin_users()` guard)

All three require engine initialization to work — which is already blocked by production SQLite/Postgres blockers. **Execution in R241-25J is scoped per-file with explicit authorization.**

---

## LANE 6 — R241-25J Authorization Package

### Phase: R241-25J_CREDENTIAL_BOOTSTRAP_PORT_AUTHORIZATION

**Files in scope (Strategy B — Full Bootstrap Port):**

| File | Operation | Risk | Authorization |
|------|-----------|------|-------------|
| `credential_file.py` | Add from origin/main SHA `100ca3b0` | LOW | Required |
| `auth/local_provider.py` | Add `count_admin_users()` method | MEDIUM | Required |
| `routers/auth.py` | Add `/initialize-admin` endpoint | MEDIUM | Required |

**Allowed in R241-25J:**
- Add `credential_file.py` from origin/main
- AST/import validation
- Add `count_admin_users()` to LocalAuthProvider
- Add `/initialize-admin` endpoint to router
- **No** `write_initial_credentials()` execution
- **No** DB writes
- **No** init_engine calls
- **No** gateway activation

**Forbidden in R241-25J:**
- `reset_admin.py` (HIGH risk — not part of activation gate)
- `init_engine` / `init_engine_from_config` calls
- Production DB writes
- `app.py` modification
- AUTH flags modification
- Writing actual credential file

---

## LANE 7 — PR #2645 Passive Recheck

| Item | Value |
|------|-------|
| State | OPEN |
| Mergeable | true |
| Mergeable state | blocked |
| CI triggered | license/cla=success; all others=not triggered |
| CI missing | true |

---

## Outcome Summary

| SRC | Outcome | Notes |
|-----|---------|-------|
| SRC-004 (credential_file.py) | `divergence_requires_decision` | Strategy B — full port in R241-25J |
| SRC-005 (reset_admin.py) | `safe_to_defer` | CLI tool, production DB, not activation gate |

### Authorization Package: **READY** for R241-25J

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

## Phase Sequence (updated)

```
R241-25D → DONE
R241-25E → DONE
R241-25F → DONE ✓
R241-25G → Report pruning (authorization needed)
R241-25H → PR #2645 passive monitoring (no auth)
R241-25I → DONE ✓ — Auth activation review complete
R241-25J → CREDENTIAL_BOOTSTRAP_PORT ← NEXT (authorization needed)
```

---

*Generated by Claude Code — R241-25I LANE 8 (Report Generation)*
