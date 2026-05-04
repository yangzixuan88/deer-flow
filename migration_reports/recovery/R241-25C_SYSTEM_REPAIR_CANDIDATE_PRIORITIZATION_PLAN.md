# R241-25C SYSTEM REPAIR CANDIDATE PRIORITIZATION PLAN

**Phase:** R241-25C — System Repair Candidate Prioritization
**Generated:** 2026-04-29
**Status:** COMPLETE (PLAN ONLY — no execution)
**Preceded by:** R241-25B (inventory complete)
**Proceeding to:** R241-25D (first execution phase)

---

## 1. PRIORITIZATION METHODOLOGY

### Dimensions Evaluated
| Dimension | Weight | Notes |
|-----------|--------|-------|
| Risk level | Highest | unknown > medium > low > none |
| Blocker impact | High | NONE preferred; AUTH_ACTIVATION_GATE highest |
| Execution authorization required | High | No-auth first; explicit auth later |
| Prerequisite dependencies | High | Parallel where possible; sequential where required |
| Cleanup category | Low | Hygiene vs. functional vs. monitoring |

### Execution Mode Definitions
| Mode | Meaning |
|------|---------|
| `PLAN_THEN_INSPECT` | Read-only inspection; report findings only |
| `READ_ONLY_ANALYSIS` | Git diff/log analysis; no branch modification |
| `CLEANUP_REQUIRES_AUTH` | File deletion; needs explicit user authorization |
| `PASSIVE_MONITORING` | No execution; periodic status check |
| `AUTH_ACTIVATION_REVIEW` | Code review without activation |

---

## 2. PREREQUISITE ANALYSIS

### Candidates with Prerequisites
| SRC | Prerequisite | Status |
|-----|--------------|--------|
| SRC-004 | Requires `origin/main` read access for diff | CONDITIONAL |
| SRC-005 | Requires `origin/main` read access for diff | CONDITIONAL |

### Candidates with No Prerequisites
| SRC | Can Execute Now |
|-----|----------------|
| SRC-001 | Read-only test file inspection |
| SRC-002 | Read-only storage.py inspection |
| SRC-003 | Read-only directory listing |
| SRC-009 | Passive CI monitoring |

### Parallel Execution Groups
```
Group 1 (no auth): SRC-001, SRC-002, SRC-003  → R241-25D
Group 2 (git read-only): SRC-004, SRC-005       → R241-25E
Group 3 (auth review): SRC-010                  → R241-25I (after auth)
```

---

## 3. AUTHORIZATION MATRIX

### No New Authorization Needed
| SRC | Reason | Execution Mode |
|-----|--------|----------------|
| SRC-001 | Read-only test file inspection | PLAN_THEN_INSPECT |
| SRC-002 | Static inventory of storage.py | PLAN_THEN_INSPECT |
| SRC-003 | Read-only directory listing | PLAN_THEN_INSPECT |
| SRC-009 | Passive PR monitoring | PASSIVE |

### Authorization Conditional
| SRC | Reason | Authorization Scope |
|-----|--------|---------------------|
| SRC-004 | Git diff analysis | Git read-only (origin/main) |
| SRC-005 | Git diff analysis | Git read-only (origin/main) |

### Authorization Required
| SRC | Reason | Risk |
|-----|--------|------|
| SRC-006 | Deletes scratch/ files | Low |
| SRC-007 | Deletes 5 _debug*.py files | Low |
| SRC-008 | Deletes migration reports | None |
| SRC-010 | Auth activation gate review | Medium |

---

## 4. PHASE ASSIGNMENT

### R241-25D — Static Inventory + Optional Dependency Guard
**Candidates:** SRC-001, SRC-002, SRC-003
**Authorization:** NOT required (all read-only inspection)
**Description:**
- SRC-001: Inspect `tests/test_gateway_auth_route_static.py` for broken imports due to email-validator
- SRC-002: Inspect `agents/memory/storage.py` content classification
- SRC-003: Inspect `app/m03/..m12/` directories (11 unknown dirs)

### R241-25E — Branch Divergence Analysis
**Candidates:** SRC-004, SRC-005
**Authorization:** CONDITIONAL (git read-only)
**Description:**
- SRC-004: Git diff origin/main vs private/main for `credential_file.py`
- SRC-005: Git diff origin/main vs private/main for `reset_admin.py`

### R241-25F — Hygiene Cleanup
**Candidates:** SRC-006, SRC-007
**Authorization:** REQUIRED (file deletion)
**Description:**
- SRC-006: Delete `packages/harness/deerflow/scratch/` contents
- SRC-007: Delete `backend/_debug*.py` (5 files)

### R241-25G — Report Pruning
**Candidates:** SRC-008
**Authorization:** REQUIRED (report deletion)
**Description:**
- SRC-008: Prune `migration_reports/recovery/` accumulated handoff reports

### R241-25H — CI Monitoring
**Candidates:** SRC-009
**Authorization:** NOT required (passive)
**Description:**
- SRC-009: Monitor PR #2645 CI status

### R241-25I — Auth Activation Review
**Candidates:** SRC-010
**Authorization:** REQUIRED (auth review scope)
**Description:**
- SRC-010: Review `credential_file.py` + `reset_admin.py` impact on auth activation gate

---

## 5. EXECUTION SEQUENCE

```
CAN EXECUTE NOW (no auth):
  R241-25D → SRC-001, SRC-002, SRC-003
  R241-25H → SRC-009 (passive monitoring)

REQUIRES USER AUTHORIZATION:
  R241-25E → SRC-004, SRC-005 (git read-only)
  R241-25F → SRC-006, SRC-007 (file deletion)
  R241-25G → SRC-008 (report deletion)
  R241-25I → SRC-010 (auth activation review)
```

---

## 6. CRITICAL DECISION POINTS

| Decision | Question | Risk | Recommendation |
|----------|----------|------|----------------|
| R241-25E | Authorize git read-only for origin/main diff? | None | Authorize |
| R241-25F | Authorize scratch/debug file deletion? | Low | User decide |
| R241-25G | Authorize report file deletion? | None | User decide |
| R241-25I | Authorize auth activation gate review? | Medium | Authorize |

---

## 7. TOP PRIORITY: R241-25D

**Why R241-25D is the safest first execution:**
1. All 3 candidates are read-only inspection — zero modification risk
2. No new authorization required — inherits R241-25B phase authorization
3. Outputs inform whether SRC-001 is actually broken or a false alarm
4. Outputs classify m03-m12 content for future hygiene decisions
5. No blockers affected

**R241-25D scope:**
- Inspect `tests/test_gateway_auth_route_static.py` → confirm broken imports
- Inspect `agents/memory/storage.py` → classify content
- Inspect `app/m03/..m12/` → list contents, classify

---

## 8. BLOCKERS PRESERVED (HARD CONSTRAINTS)

All blockers from R241-25A/25B remain intact:
- Production SQLite binding — BLOCKED
- Production Postgres binding — BLOCKED
- CAND-003 MCP binding — BLOCKED
- DSRT — DISABLED
- Actual gateway activation — BLOCKED
- `MAINLINE_GATEWAY_ACTIVATION=false` — CONFIRMED
- `AUTH_MIDDLEWARE_ENABLED=false` — CONFIRMED
- `AUTH_ROUTES_ENABLED=false` — CONFIRMED

---

## 9. HARD PROHIBITIONS (R241-25C)

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

*Generated by Claude Code — R241-25C LANE 8 (Report Generation)*
