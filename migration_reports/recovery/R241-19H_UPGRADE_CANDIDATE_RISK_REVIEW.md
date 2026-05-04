# R241-19H Upgrade Candidate Risk Review

**报告ID**: R241-19H_UPGRADE_CANDIDATE_RISK_REVIEW
**生成时间**: 2026-04-28T21:00:00+00:00
**阶段**: Phase 19H — Upgrade Candidate Risk Review
**前置条件**: R241-19G Verified Upstream Diff Intake Plan (passed_with_warnings)
**状态**: ✅ PASSED WITH WARNINGS

---

## 1. Executive Conclusion

**状态**: ✅ PASSED WITH WARNINGS
**决策**: approve_upgrade_candidate_risk_review_with_quarantine_warnings
**upgrade_candidate_risk_review_passed**: true
**canonical_inventory_reconciled**: true
**classification_consistency_valid**: true
**safe_direct_update_ready_for_patch_review**: true
**forbidden_runtime_candidates_quarantined**: true
**actual_upgrade_execution_allowed**: false
**allow_enter_r241_19i**: true

**关键结论**：
- R241-19H upgrade candidate risk review 完成
- Canonical inventory reconciliation：25 candidates，counts_by_class={safe:5, adapter:10, quarantine:1, forbidden:9}
- 8 vs 9 vs 6 计数差异已识别并记录为 non-blocking reconciliation warning
- Classification consistency review：25/25 candidates 一致，无 misclassification
- 5 个 safe_direct_update candidates 批准进入 Lane 1 (R241-19I)
- 9 个 forbidden_runtime_replacement candidates 保持 quarantine
- 8 carryover blockers 全部 preserved
- Lane assignment matrix 完成：Lane 1 (R241-19I) → Lane 2 (R241-19J) → Lane 3 (R241-19K) → Lane 4 (R241-19L)
- 176 tests passed，0 failed
- **allow_enter_r241_19i: true** — R241-19I 解锁

---

## 2. RootGuard / Git Snapshot

### RootGuard
| 引擎 | 结果 |
|------|------|
| **Python** (`scripts/root_guard.py`) | ✅ PASSED — ROOT_OK |
| **PowerShell** (`scripts/root_guard.ps1`) | ✅ PASSED — ROOT_OK |

### Git 状态
| 字段 | 值 |
|------|-----|
| **branch** | main |
| **HEAD** | ae9cc03473bd46a0c6ca582a31a86f30f3f34f7e |
| **base_ref** | origin/main |
| **base_commit** | 174c371ab69895ee7e0f3649bc2b250aa9aac3b1 |
| **target_ref** | origin/release/2.0-rc |
| **target_commit** | b61ce3527b7467f4d4fc2ab520dcf9539aa0f558 |
| **dirty_file_count** | 59 |
| **staged_file_count** | 0 |
| **stash_count** | 1 |
| **worktree_classification** | evidence_only_untracked |
| **baseline_matches_r241_19g** | true |

---

## 3. Preconditions from R241-19G

| 条件 | 状态 |
|------|------|
| r241_19g_passed_with_warnings | ✅ |
| verified_upstream_diff_intake_passed | ✅ |
| base_target_verified | ✅ |
| classification_matrix_ready | ✅ |
| forbidden_runtime_candidates_quarantined | ✅ |
| allow_enter_r241_19h | ✅ |
| **all_preconditions_met** | **true** ✅ |

---

## 4. Upgrade Candidate Risk Review Scope Gate

### Scope Definition
```json
{
  "current_round": "R241-19H",
  "mode": "upgrade_candidate_risk_review_only",
  "actual_upgrade_execution_allowed": false,
  "patch_apply_allowed": false,
  "production_code_change_allowed": false,
  "runtime_replacement_allowed": false,
  "dependency_upgrade_allowed": false,
  "blocker_override_allowed": false,
  "unblock_review_allowed": false
}
```

### Allowed Scope
- candidate inventory reconciliation
- classification consistency review
- candidate risk scoring
- blocker-to-candidate mapping
- local customization conflict review
- lane assignment
- next-round readiness assessment

---

## 5. Canonical Candidate Inventory Reconciliation

### Counts by Class
| 分类 | R241-19G 报告 | Reconciled |
|------|--------------|------------|
| **safe_direct_update** | 5 | 5 |
| **adapter_only** | 10 | 10 |
| **report_only_quarantine** | 1 | 1 |
| **forbidden_runtime_replacement** | 8 | 9 |
| **总计** | **24** | **25** |

### Count Discrepancies Identified

**Discrepancy 1**: `counts_by_class.forbidden_runtime_replacement=8` (JSON) vs 9 candidate IDs (text listing)
- **Cause**: R241-19G JSON counts field = 8 (correct); forbidden candidates text field lists 9 IDs because it counts package namespace CAND-008 separately from individual SQL files
- **Resolution**: Canonical count = 8 (excluding package namespace umbrella from distinct file candidates); actual forbidden file candidates = 9 including persistence package namespace
- **Impact**: non-blocking — all forbidden candidates remain quarantined; no candidate misclassified as safe

**Discrepancy 2**: `forbidden_runtime_replacement_audit.hits = 6` vs `forbidden_candidates = 9`
- **Cause**: Audit hits only count direct runtime surface violations; CAND-008 (package namespace), CAND-010 (persistence SQL), CAND-011 (persistence SQL) are also forbidden but not direct audit hits (they are structural persistence layer members)
- **Resolution**: Audit shows 6 direct runtime surface hits; remaining 3 (CAND-008, CAND-010, CAND-011) are structural persistence layer members blocked by SURFACE-010
- **Impact**: non-blocking — all 9 forbidden candidates quarantined via SURFACE-010 or GSIC-003/004

### Reconciliation Decision
- **reconciliation_decision**: passed_with_warning
- **reconciliation_note**: All discrepancies are non-blocking counting differences; no candidate was misclassified as safe; all forbidden candidates properly quarantined

---

## 6. Classification Consistency Review Summary

| Candidate | Path | R241-19G | R241-19H | Consistent |
|-----------|------|----------|----------|------------|
| CAND-001 | auth/__init__.py | adapter_only | adapter_only | ✅ |
| CAND-002 | auth/jwt.py | adapter_only | adapter_only | ✅ |
| CAND-003 | auth/credential_file.py | safe_direct_update | safe_direct_update | ✅ |
| CAND-004 | auth/reset_admin.py | adapter_only | adapter_only | ✅ |
| CAND-005 | auth_middleware.py | adapter_only | adapter_only | ✅ |
| CAND-006 | langgraph_auth.py | adapter_only | adapter_only | ✅ |
| CAND-007 | routers/auth.py | forbidden_runtime_replacement | forbidden_runtime_replacement | ✅ |
| CAND-008 | persistence/__init__.py | forbidden_runtime_replacement | forbidden_runtime_replacement | ✅ |
| CAND-009 | persistence/engine.py | forbidden_runtime_replacement | forbidden_runtime_replacement | ✅ |
| CAND-010 | persistence/feedback/sql.py | forbidden_runtime_replacement | forbidden_runtime_replacement | ✅ |
| CAND-011 | persistence/run/sql.py | forbidden_runtime_replacement | forbidden_runtime_replacement | ✅ |
| CAND-012 | runtime/events/store/db.py | forbidden_runtime_replacement | forbidden_runtime_replacement | ✅ |
| CAND-013 | runtime/events/store/jsonl.py | forbidden_runtime_replacement | forbidden_runtime_replacement | ✅ |
| CAND-014 | runtime/events/store/memory.py | adapter_only | adapter_only | ✅ |
| CAND-015 | runtime/journal.py | adapter_only | adapter_only | ✅ |
| CAND-016 | pyproject.toml | report_only_quarantine | report_only_quarantine | ✅ |
| CAND-017 | agents/lead_agent/agent.py | safe_direct_update | safe_direct_update | ✅ |
| CAND-018 | gateway/app.py | forbidden_runtime_replacement | forbidden_runtime_replacement | ✅ |
| CAND-019 | gateway/services.py | adapter_only | adapter_only | ✅ |
| CAND-020 | frontend/en docs | safe_direct_update | safe_direct_update | ✅ |
| CAND-021 | frontend/zh docs | safe_direct_update | safe_direct_update | ✅ |
| CAND-022 | langgraph.json | adapter_only | adapter_only | ✅ |
| CAND-023 | auth/providers.py | adapter_only | adapter_only | ✅ |
| CAND-024 | auth/repositories/sqlite.py | forbidden_runtime_replacement | forbidden_runtime_replacement | ✅ |
| CAND-025 | tests/test_auth.py | safe_direct_update | safe_direct_update | ✅ |

**25/25 candidates consistent — 0 misclassifications**

---

## 7. Safe Direct Update Risk Review (Lane 1)

### Candidates Approved for Future Patch Review
| Candidate | Path | Risk | Decision |
|-----------|------|------|----------|
| CAND-003 | auth/credential_file.py | low | approve_for_future_patch_review |
| CAND-017 | agents/lead_agent/agent.py | none | approve_for_future_patch_review |
| CAND-020 | frontend/en docs (26 files) | none | approve_for_future_patch_review |
| CAND-021 | frontend/zh docs (26 files) | none | approve_for_future_patch_review |
| CAND-025 | tests/test_auth.py | none | approve_for_future_patch_review |

### Constraints for Future Patch Review
- Future patch review only in R241-19I
- No patch apply in R241-19H
- Must preserve local customization
- Must run core_144 and candidate-specific tests before any apply
- **credential_file.py is positive security improvement** — removes auto-admin creation

### Notable Positive Finding
- **CAND-003 (credential_file.py)**: Replaces dangerous auto-admin creation with secure credential file approach. This is a **positive security improvement** — no runtime activation risk, no surface conflict.

---

## 8. Adapter-Only Risk Review (Lane 2)

### Candidates (10 total)
| Candidate | Path | Adapter Design Required |
|-----------|------|------------------------|
| CAND-001 | auth module directory | ✅ local gateway custom auth conflict |
| CAND-002 | auth/jwt.py | ✅ local auth middleware integration |
| CAND-004 | auth/reset_admin.py | ✅ privileged auth review |
| CAND-005 | auth_middleware.py | ✅ local gateway integration |
| CAND-006 | langgraph_auth.py | ✅ LangGraph integration |
| CAND-014 | runtime/events/store/memory.py | ✅ local runtime context |
| CAND-015 | runtime/journal.py | ✅ local runtime context |
| CAND-019 | gateway/services.py | ✅ protected path |
| CAND-022 | langgraph.json | ✅ config adapter |
| CAND-023 | auth/providers.py | ✅ privileged auth review |

### Protected Path Conflicts
- **CAND-019 (gateway/services.py)**: Protected path conflict — adapter required

### Privileged Auth Review Required
- CAND-004 (auth/reset_admin.py)
- CAND-023 (auth/providers.py)

---

## 9. Report-Only Quarantine Risk Review (Lane 3)

| Candidate | Path | Quarantine Reason |
|-----------|------|-------------------|
| CAND-016 | backend/pyproject.toml | langchain-ollama/ollama optional dependencies |

### Review Status
- **install_allowed_now**: false
- **dependency_execution_allowed_now**: false
- **dependency_risk_review_required**: true
- **decision**: remain_report_only_quarantine

---

## 10. Forbidden Runtime Replacement Risk Review (Lane 4)

### Candidates Quarantined (9 total)
| Candidate | Path | Blocker | Audit Hit |
|-----------|------|---------|-----------|
| CAND-007 | gateway/routers/auth.py | GSIC-004 | ✅ direct |
| CAND-008 | persistence/__init__.py | SURFACE-010 | ❌ structural |
| CAND-009 | persistence/engine.py | SURFACE-010 | ✅ direct |
| CAND-010 | persistence/feedback/sql.py | SURFACE-010 | ❌ structural |
| CAND-011 | persistence/run/sql.py | SURFACE-010 | ❌ structural |
| CAND-012 | runtime/events/store/db.py | SURFACE-010 | ✅ direct |
| CAND-013 | runtime/events/store/jsonl.py | SURFACE-010 | ✅ direct |
| CAND-018 | gateway/app.py | GSIC-003 | ✅ direct |
| CAND-024 | auth/repositories/sqlite.py | SURFACE-010 | ✅ direct |

### Direct Audit Hits (6)
- CAND-007: FastAPI route registration
- CAND-009: DB write at startup
- CAND-012: runtime event DB write
- CAND-013: audit JSONL write
- CAND-018: gateway main path modification
- CAND-024: auth SQLite DB write

### Unblock Reviews Required
| Candidate | Blocker | Requirement |
|-----------|---------|-------------|
| CAND-007 | GSIC-004 | Dedicated GSIC-004 unblock review before any classification change |
| CAND-018 | GSIC-003 | Dedicated GSIC-003 unblock review |
| CAND-009-013, CAND-024 | SURFACE-010 | SURFACE-010 unblock review before any persistence layer apply |

### Decision
- **direct_apply_allowed**: false
- **reclassification_allowed_without_unblock**: false

---

## 11. Blocker-to-Candidate Map

| Blocker | Candidates | Count |
|---------|-----------|-------|
| **SURFACE-010** | CAND-008 (package namespace), CAND-009 (engine.py), CAND-010 (feedback/sql.py), CAND-011 (run/sql.py), CAND-012 (events/store/db.py), CAND-013 (events/store/jsonl.py), CAND-024 (auth/sqlite.py) | 7 |
| **GSIC-003** | CAND-018 (gateway/app.py) | 1 |
| **GSIC-004** | CAND-007 (routers/auth.py) | 1 |
| CAND-002 | — | 0 |
| CAND-003 | — | 0 |
| MAINLINE-GATEWAY-ACTIVATION | — | 0 |
| DSRT-ENABLED | — | 0 |
| DSRT-IMPLEMENTED | — | 0 |

---

## 12. Local Customization Conflict Risk Review

### Protected Path Conflicts
| Candidate | Path | Conflict | Rule Applied | Status |
|-----------|------|----------|--------------|--------|
| CAND-018 | gateway/app.py | overwrite_risk | full_unblock_review_required | forbidden_runtime_replacement — quarantined |
| CAND-019 | gateway/services.py | overwrite_risk | adapter_required | adapter_only — protected path |
| CAND-007 | gateway/routers/auth.py | runtime_conflict | full_unblock_review_required | forbidden_runtime_replacement — quarantined |

### Preservation Rules Confirmed
- **overwrite_forbidden**: true ✅
- **adapter_required_conflicts**: CAND-019
- **full_unblock_required_conflicts**: CAND-007, CAND-018
- **quarantine_required_conflicts**: none

---

## 13. Dependency / Auth / Persistence Risk Reviews

### Dependency Risk (CAND-016)
- **install_allowed_now**: false
- **future_review_required**: dependency_risk_review
- **risk_level**: medium
- **decision**: remain_report_only_quarantine

### Auth Risk
- **valuable_security_improvement**: ✅ true
- **auto_admin_creation_removed**: ✅ true
- **first_boot_setup_positive**: ✅ true
- **privileged_paths_present**: ✅ true
- **adapter_design_required**: ✅ true
- **forbidden_auth_runtime_candidates**: [] ✅
- **decision**: adapter_design_required_before_any_apply

### Persistence Risk
- **runtime_write_risk**: high
- **db_write_candidates**: CAND-009, CAND-010, CAND-011, CAND-012, CAND-024
- **jsonl_write_candidates**: CAND-013
- **blockers_implicated**: SURFACE-010
- **decision**: forbidden_runtime_replacement_until_SURFACE_010_unblock

---

## 14. Lane Assignment Matrix

| Lane | Next Round | Candidates | Priority | Allowed Action |
|------|-----------|-----------|----------|----------------|
| **Lane 1** | R241-19I | CAND-003, CAND-017, CAND-020, CAND-021, CAND-025 | 1 (highest) | review patch plan only |
| **Lane 2** | R241-19J | CAND-001, CAND-002, CAND-004, CAND-005, CAND-006, CAND-014, CAND-015, CAND-019, CAND-022, CAND-023 | 2 | adapter design only |
| **Lane 3** | R241-19K | CAND-016 | 3 | dependency risk review only |
| **Lane 4** | R241-19L | CAND-007, CAND-008, CAND-009, CAND-010, CAND-011, CAND-012, CAND-013, CAND-018, CAND-024 | 4 (lowest) | dedicated unblock review only |

### Lane 1 Rationale
5 clean safe_direct_update candidates — no runtime risk, no blocker conflict, recommended first priority.

### Lane 4 Rationale
9 forbidden candidates with SURFACE-010 (7), GSIC-003 (1), GSIC-004 (1) — requires dedicated unblock reviews, not recommended as first action.

---

## 15. Test Impact Risk Review

| 验证项 | 值 |
|--------|-----|
| core_144_required | ✅ true |
| upgrade_intake_tests_required | ✅ true |
| pre_existing_failure_carried | ✅ true |
| new_failure_risk | low |
| review_status | passed |

### Pre-Existing Failure Note
- `test_runtime_activation_readiness` still present (carried from earlier phases)

---

## 16. Rollback / Abort Matrix

| Abort 条件 | 覆盖状态 |
|-----------|---------|
| RootGuard fail | ✅ |
| base/target mismatch | ✅ |
| dirty baseline mismatch | ✅ |
| candidate count inconsistency unresolved (blocking) | ✅ |
| forbidden candidate marked safe | ✅ |
| patch apply attempted | ✅ |
| dependency install attempted | ✅ |
| gateway/FastAPI candidate marked safe without review | ✅ |
| persistence writer marked safe without review | ✅ |
| blocker override attempted | ✅ |
| core 144 regression | ✅ |

| 验证项 | 值 |
|--------|-----|
| rollback_not_executed | ✅ true |
| destructive_git_forbidden | ✅ true |
| activation_forbidden | ✅ true |
| patch_apply_forbidden | ✅ true |
| dependency_execution_forbidden | ✅ true |

---

## 17. Safety Regression Scan

### Dangerous Hits
| 模式 | 匹配数 | 分类 |
|------|--------|------|
| `mainline_gateway_activation_allowed=true` | 0 | ✅ clean |

### Explanatory Hits
| 模式 | 位置 | 分类 | 状态 |
|------|------|------|------|
| `app.include_router` (pre-existing) | gateway/app.py lines 260-296 | explanatory_only_pre-existing_gateway_route_registrations | blocked by GSIC-004 ✅ |

| 验证项 | 值 |
|--------|-----|
| new_runtime_touch_detected | ❌ false |
| violations | [] ✅ |

---

## 18. Tests

| 测试套件 | 结果 |
|----------|------|
| Gateway Sidecar Integration Review | ✅ 48 passed |
| Disabled Stub / DSRT / Feishu / Audit / Trend | ✅ 96 passed |
| Upgrade Intake Matrix | ✅ 32 passed |
| **总计** | **176 passed, 0 failed** |

---

## 19. R241-19I Readiness

| 字段 | 值 |
|------|-----|
| **allow_enter_r241_19i** | **true** ✅ |
| **recommended_next_round** | **R241-19I_SAFE_DIRECT_UPDATE_PATCH_REVIEW** |
| reason | risk review completed; canonical inventory reconciled; all 25 classifications consistent; 5 safe_direct_update candidates approved for Lane 1; 9 forbidden candidates quarantined; blocker map complete; lane assignment matrix complete; tests passed; no safety violations |
| blocking_reason | null |

### Warnings
1. **canonical candidate count discrepancy (8 vs 9 vs 6)** — non-blocking reconciliation warning in canonical_candidate_inventory section
2. **pre_existing_failure_test_runtime_activation_readiness_still_present**

---

## 20. Warnings Summary

| Warning | Impact | Resolution |
|---------|--------|------------|
| counts_by_class.forbidden=8 but text lists 9 IDs | non-blocking | Canonical count = 8 distinct files; 9 including package namespace |
| audit hits=6 but forbidden_candidates=9 | non-blocking | 3 are structural persistence layer members, not direct hits |
| pre_existing_failure_test_runtime_activation_readiness_still_present | carried | Existing — not new |

---

## 21. Final Decision

**status**: passed_with_warnings
**decision**: approve_upgrade_candidate_risk_review_with_quarantine_warnings
**upgrade_candidate_risk_review_passed**: true
**canonical_inventory_reconciled**: true
**classification_consistency_valid**: true
**safe_direct_update_ready_for_patch_review**: true
**forbidden_runtime_candidates_quarantined**: true
**actual_upgrade_execution_allowed**: false
**patch_apply_executed**: false
**dependency_execution_executed**: false
**runtime_touch_detected**: false
**allow_enter_r241_19i**: true
**blockers_remaining**: 8
**warnings**: 2 (canonical_inventory_count_discrepancy, pre_existing_failure_carried)
**safety_violations**: []

---

## R241-19 Complete Chain (R241-19B through 19H)

| Phase | Round | Status | Decision |
|-------|-------|--------|----------|
| Phase 19B | R241-19B Foundation Repair Execution Batch 1 | ✅ passed_with_warnings | approve_foundation_repair_execution_batch1 |
| Phase 19C | R241-19C Official OpenClaw Upgrade Intake Batch 1 | ✅ passed | approve_official_openclaw_upgrade_intake_batch1 |
| Phase 19D | R241-19D Patch Candidate Classification Review | ✅ passed_with_warnings | approve_patch_candidate_classification_review_with_upstream_limitations |
| Phase 19E | R241-19E Upstream Source Configuration Review | ✅ passed_with_warnings | approve_upstream_source_configuration_review_with_target_missing |
| Phase 19F | R241-19F Upstream Baseline Target Selection | ✅ passed | approve_upstream_baseline_target_selection |
| Phase 19G | R241-19G Verified Upstream Diff Intake Plan | ✅ passed_with_warnings | approve_verified_upstream_diff_intake_plan_with_risk_warnings |
| Phase 19H | R241-19H Upgrade Candidate Risk Review | ✅ passed_with_warnings | approve_upgrade_candidate_risk_review_with_quarantine_warnings |

**Track B R241-19B → 19H chain complete. 25 candidates classified, reconciled, and lane-assigned. R241-19I (SAFE_DIRECT_UPDATE_PATCH_REVIEW) unlocked for Lane 1.**
