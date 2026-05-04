# R241-25B SYSTEM REPAIR INVENTORY PLAN

**Phase:** R241-25B — System Repair Inventory Plan
**Generated:** 2026-04-29
**Status:** COMPLETE (PLAN ONLY — no execution)
**Preceded by:** R241-25A (foundation_completion_score=97, COMPLETE)
**Proceeding to:** R241-25C (prioritization)

---

## 1. SYSTEM REPAIR SCOPE BASELINE

### Module Roots
| Root | Type | Modules |
|------|------|---------|
| `backend/app/` | Primary application | 23 subdirectories |
| `backend/packages/harness/` | Harness package | Single package |
| `backend/packages/workspace/` | Workspace package | Single package |

### Inventory Scope Confirmed
- **Scope:** `backend/app/`, `backend/packages/`
- **Excluded:** `node_modules`, `.git`, `.venv`, `__pycache__`, `tmp/worktree`, frontend builds
- **migration_reports/recovery/:** Reports only, not a repair target

### Excluded Paths (172 untracked files)
These are local development artifacts, NOT tracked code:
- `backend/_debug*.py` (5 files) — debug artifacts
- `backend/m03/ .. m12/` (11 directories) — unknown
- `backend/app/asset/`, `backend/app/audit/`, `backend/app/foundation/` — unknown
- `backend/app/memory/` — unknown
- `backend/packages/harness/deerflow/scratch/` — scratch
- `.deerflow/`, `.openclaw/`, `.serena/` — tool configs

**Hygiene Decision:** Do NOT clean, git clean, or git add these files.

---

## 2. STATIC IMPORT INVENTORY DESIGN

### Method: AST-Only Scanning
- Walk all `.py` files in `backend/app/` and `backend/packages/`
- Parse with `ast.parse()` (no exec, no runtime import)
- Extract `Import` and `ImportFrom` nodes
- Cross-reference against known safe/unsafe lists

### Safe Import Whitelist (no top-level side effects)
```
typing, collections, contextlib, functools, pathlib,
os, sys, re, json, copy, dataclasses, enum, warnings,
tempfile, uuid, hashlib, hmac, base64, asyncio, inspect,
fastapi, starlette, pydantic, deerflow, app
```

### High-Risk Imports (potential side effects at top-level)
```
aiosqlite     — opens file handles
sqlalchemy    — may init engine
email_validator — may load native libs
psycopg2     — DB driver
redis        — network connection
requests/urllib3/httpx/aiohttp — network I/O
```

---

## 3. BROKEN IMPORT / MISSING DEPENDENCY INVENTORY

### Missing Dependencies
| Dependency | Status | Impact |
|------------|--------|--------|
| `email-validator` | **Installed (v2.3.0)** | Optional; used in auth routes |
| `httpx` | **Installed (v0.28.1)** | Used in channels; safe |

### Resolved Import Cascades (from prior R241 phases)
| Cascade | Module | Status |
|---------|--------|--------|
| `summarization_hook` | `deerflow.agents.lead_agent.prompt` | RESOLVED |
| `summarization_middleware` | `deerflow.agents.middlewares.summarization_middleware` | RESOLVED |
| `validate_agent_name` | `deerflow.agents.lead_agent.agent` | RESOLVED |
| `user_context.set_current_user` | `deerflow.runtime.user_context` | RESOLVED (R241-22W) |
| `thread_meta memory backend` | `deerflow.persistence.thread_meta` | RESOLVED (R241-22AA) |
| `engine import-safe` | `deerflow.persistence.engine` | RESOLVED (R241-22Z) |

### Unresolved Import Risks
| Item | Description | Priority |
|------|-------------|----------|
| `m03-m12` directories | 11 unknown directories; need content inspection | HIGH |
| `credential_file.py` | Exists on `origin/main` but not in `private/main` | MEDIUM |
| `reset_admin.py` | Exists on `origin/main` but not in `private/main` | LOW |
| `backend/app/memory/` | New directory; needs inspection | HIGH |
| `backend/app/gateway/auth/` | Branch divergence for auth features | MEDIUM |

---

## 4. RUNTIME SURFACE CLASSIFICATION

### Classification Key
| Class | Meaning |
|-------|---------|
| A | import-safe (no risky imports at top level) |
| B | import-unsafe (optional dependency only) |
| C | import-unsafe (runtime side effect risk) |
| D | db-writing-if-initialized |
| E | gateway-activation-sensitive |

### Key Module Classifications
| Module | Class | Notes |
|--------|-------|-------|
| `app/gateway/app.py` | **E** | Gateway entry, middleware activation |
| `app/gateway/deps.py` | A | Dependency injection, TYPE_CHECKING guard |
| `app/gateway/auth_middleware.py` | A | Auth middleware definition (safe) |
| `app/gateway/auth/errors.py` | A | Auth error codes only |
| `app/gateway/routers/auth.py` | A | Auth routes, no db/middleware |
| `packages/harness/deerflow/persistence/engine.py` | **D** | DB init, create_all — BLOCKER surface |
| `packages/harness/deerflow/runtime/user_context.py` | A | User context, safe |
| `packages/harness/deerflow/agents/lead_agent/agent.py` | A | Lead agent, safe |
| `packages/harness/deerflow/agents/factory.py` | A | Agent factory, safe |
| `packages/harness/deerflow/agents/memory/storage.py` | A | Memory storage, safe |

### High-Risk Surfaces (BLOCKERS preserved)
| Surface | Class | Blocker |
|---------|-------|---------|
| `persistence/engine.py` | D | Production SQLite blocked |
| `persistence/models.py` | D | Production SQLite blocked |
| `app/gateway/app.py` | E | Auth activation gate |
| `app/gateway/deps.py` | E | Auth activation gate |

### No-Touch Surfaces
```
packages/harness/deerflow/persistence/engine.py     — PRODUCTION DB BLOCKER
packages/harness/deerflow/persistence/models.py   — PRODUCTION DB BLOCKER
app/gateway/app.py                                  — AUTH ACTIVATION GATE (audited)
app/gateway/deps.py                                — AUTH ACTIVATION GATE (audited)
```

---

## 5. SYSTEM REPAIR CANDIDATE QUEUE

### Candidate Summary
| ID | Path | Category | Risk | Phase |
|----|------|----------|------|-------|
| SRC-001 | `tests/test_gateway_auth_route_static.py` | optional-dep-guard | low | R241-25D |
| SRC-002 | `agents/memory/storage.py` | static-inventory | unknown | R241-25D |
| SRC-003 | `app/m03-m12/` (11 dirs) | hygiene-inspection | unknown | R241-25D |
| SRC-004 | `gateway/auth/credential_file.py` | branch-divergence | medium | R241-25E |
| SRC-005 | `gateway/auth/reset_admin.py` | branch-divergence | low | R241-25E |
| SRC-006 | `deerflow/scratch/` | hygiene-cleanup | low | R241-25F |
| SRC-007 | `backend/_debug*.py` | hygiene-cleanup | none | R241-25F |
| SRC-008 | `migration_reports/recovery/` | report-pruning | none | R241-25G |
| SRC-009 | `PR #2645` | ci-monitoring | external | R241-25H |
| SRC-010 | `gateway/auth/` (credential + reset) | auth-activation-review | medium | R241-25I |

### Candidate by Category
```
optional-dependency-guard:  SRC-001
static-inventory-only:     SRC-002
hygiene-inspection:          SRC-003
branch-divergence-analysis: SRC-004, SRC-005
hygiene-cleanup:            SRC-006, SRC-007
report-pruning:             SRC-008
ci-monitoring:              SRC-009
auth-activation-review:     SRC-010
```

---

## 6. RECOMMENDED NEXT PHASE

### R241-25C: System Repair Candidate Prioritization

**Scope (PLAN ONLY):**
1. Finalize prioritization of SRC-001 through SRC-010
2. Assign phase numbers R241-25D through R241-25M
3. Determine which candidates need explicit user authorization
4. Identify which candidates can be executed without new authorization

**Execution allowed in R241-25C:** NONE (plan only)
**Execution allowed in R241-25D+:** Per-candidate authorization required

### Phase Sequence
```
R241-25C → R241-25D (SRC-001, SRC-002, SRC-003)
        → R241-25E (SRC-004, SRC-005)
        → R241-25F (SRC-006, SRC-007)
        → R241-25G (SRC-008)
        → R241-25H (SRC-009)
        → R241-25I (SRC-010)
```

---

## 7. BLOCKERS PRESERVED (HARD CONSTRAINTS)

All blockers from R241-25A remain intact:
- Production SQLite binding — BLOCKED
- Production Postgres binding — BLOCKED
- CAND-003 MCP binding — BLOCKED
- DSRT — DISABLED
- Actual gateway activation — BLOCKED
- `MAINLINE_GATEWAY_ACTIVATION=false` — CONFIRMED
- `AUTH_MIDDLEWARE_ENABLED=false` — CONFIRMED
- `AUTH_ROUTES_ENABLED=false` — CONFIRMED

---

## 8. HARD PROHIBITIONS (R241-25B)

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

*Generated by Claude Code — R241-25B LANE 8 (Report Generation)*
