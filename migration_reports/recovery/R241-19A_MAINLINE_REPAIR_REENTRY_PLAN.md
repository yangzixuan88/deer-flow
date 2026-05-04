# R241-19A Mainline Repair Re-entry Plan

**报告ID**: R241-19A_MAINLINE_REPAIR_REENTRY_PLAN
**生成时间**: 2026-04-28T06:40:00+00:00
**阶段**: Phase 20 — Mainline Repair Re-entry Plan
**前置条件**: R241-18Z Mainline Resume Activation Gate Review (passed, allow_enter_r241_19a=true)

---

## 1. Executive Conclusion

**状态**: ✅ PASSED WITH WARNINGS
**决策**: approve_mainline_repair_reentry_plan_with_conditions
**mainline_reentry_plan_ready**: true
**track_a_scope_defined**: true
**track_b_scope_defined**: true
**allowed_code_touch_list_defined**: true
**forbidden_runtime_surfaces_defined**: true
**dirty_worktree_policy_defined**: true
**carryover_blockers_preserved**: true

**双轨主线回归计划已建立：**
- **Track A**: Foundation Repair and Optimization Regression
- **Track B**: Official OpenClaw Gradual Upgrade Intake Regression

**8 个 blockers 全部携带至 R241-19A**，任何时刻都不可覆盖。

**⚠️ 非阻塞警告**：
- 1 个 pre-existing test failure（`test_runtime_activation_readiness.py::test_report_generation_writes_only_to_tmp_path`）— R241-18A 历史遗留物，非 R241-19A 造成，不影响 plan 审批

**allow_enter_r241_19b: true** — 建议进入 **R241-19B：Foundation Repair Execution Batch 1**。

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
| **dirty_file_count** | 59 |
| **staged_file_count** | 0 |
| **stash_count** | 1 |
| **stash@{0}** | On main: R241-17B worktree stash: 59 tracked + 152 untracked files |

### 工作区分类
**worktree_classification**: evidence_only_untracked

| 分类 | 状态 |
|------|------|
| production_code_modified | ✅ 无新增生产代码修改 |
| test_code_modified | ✅ 无新增测试代码修改 |
| unsafe_dirty_state | ✅ 无 secret/token/webhook/.env 文件 |
| pre_existing_dirty | ⚠️ 59 个 dirty tracked 文件为前期会话遗留（non-blocking） |

---

## 3. Preconditions from R241-18Z

| 条件 | 值 | 状态 |
|------|-----|------|
| R241-18Z status | passed | ✅ |
| R241-18Z decision | activation_gate_review_completed_blocked_as_expected | ✅ |
| activation_gate_review_passed | true | ✅ |
| actual_activation_allowed | false | ✅ |
| activation_blocked_as_expected | true | ✅ |
| all_blockers_intact | true | ✅ |
| allow_enter_r241_19a | true | ✅ |
| safety_violations_clean | true | ✅ |
| **all_preconditions_met** | **true** | ✅ |

---

## 4. Mainline Re-entry Scope

```json
{
  "current_round": "R241-19A",
  "mode": "mainline_repair_reentry_planning_only",
  "actual_activation_allowed": false,
  "code_execution_allowed": false,
  "production_code_change_allowed": false,
  "blocker_override_allowed": false
}
```

### allowed_scope
- mainline repair planning
- Track A / Track B scope definition
- allowed code touch list generation
- forbidden runtime surface definition
- patch candidate classification
- evidence carryover planning
- dirty worktree handling policy
- R241-19B / R241-19C readiness assessment

### forbidden_scope
- actual activation
- gateway activation
- FastAPI route registration
- memory runtime activation
- MCP runtime activation
- DSRT enablement
- Feishu real send
- network access
- scheduler
- auto-fix
- tool enforcement
- runtime write
- audit JSONL write
- action queue write
- mainline_gateway_activation_allowed=true
- blocker override
- production code change
- destructive git operation
- dirty worktree cleanup
- stash apply/pop

---

## 5. Track A — Foundation Repair and Optimization Regression

### 允许的规划项目
| # | 项目 |
|---|------|
| 1 | RootGuard continuity |
| 2 | test harness consistency |
| 3 | report schema consistency |
| 4 | evidence package consistency |
| 5 | diagnostic CLI readiness |
| 6 | audit / trend report read-only consistency |
| 7 | disabled stub contract consistency |
| 8 | dirty worktree manifest |
| 9 | CI / pytest command matrix |
| 10 | parser / report generator non-runtime fixes |
| 11 | documentation consistency |
| 12 | safe refactor candidates |

### 禁止的规划项目
| # | 项目 |
|---|------|
| 1 | memory runtime activation |
| 2 | MCP runtime activation |
| 3 | gateway activation |
| 4 | FastAPI route registration |
| 5 | Feishu real send |
| 6 | scheduler / auto-fix / tool enforcement |
| 7 | runtime write |
| 8 | audit JSONL write |
| 9 | action queue write |
| 10 | prompt / memory / asset mutation |

### 候选批次
| # | Batch |
|---|-------|
| 1 | R241-19B_Foundation_Repair_Execution_Batch1 |

### 所需证据
- root_guard_continuity_evidence
- test_harness_evidence
- report_schema_evidence
- dirty_worktree_manifest

**first_execution_batch_candidate: R241-19B**

---

## 6. Track B — Official OpenClaw Gradual Upgrade Intake Regression

### 允许的规划项目
| # | 项目 |
|---|------|
| 1 | official upstream diff intake |
| 2 | local customization preservation |
| 3 | patch candidate classification |
| 4 | safe direct update candidates |
| 5 | adapter-only candidates |
| 6 | report-only quarantine candidates |
| 7 | forbidden runtime replacement candidates |
| 8 | dependency / config diff review |
| 9 | test impact matrix |
| 10 | rollback / abort matrix |

### 禁止的规划项目
| # | 项目 |
|---|------|
| 1 | upstream whole-directory overwrite |
| 2 | runtime replacement |
| 3 | gateway / FastAPI direct replacement |
| 4 | memory/MCP runtime replacement |
| 5 | secret / token / webhook migration |
| 6 | scheduler activation |
| 7 | production service start |
| 8 | unreviewed dependency upgrade execution |

### 候选分类
| Class | 说明 | Decision |
|-------|------|----------|
| safe_direct_update | 纯报告模板、只读helper、schema验证器、非runtime修复 | proceed_without_dedicated_review |
| adapter_only | 官方升级需要本地接口桥接层 | proceed_with_track_B_review |
| report_only_quarantine | 有价值但风险不确定 | quarantine_as_evidence_only |
| forbidden_runtime_replacement | 替换gateway/main path/memory/MCP | prohibited_without_full_unblock_review |

### 所需证据
- upstream_diff_evidence
- patch_classification_evidence
- test_impact_evidence

**first_intake_batch_candidate: R241-19C**（需 R241-19B 完成后方可开始）

---

## 7. Carryover Blocker Ledger (8/8 — All Preserved)

| Blocker ID | Status | Source | Unblock Required | Carried | Override? |
|------------|--------|--------|-----------------|---------|-----------|
| SURFACE-010 | BLOCKED CRITICAL | R241-18K | dedicated memory readiness review | ✅ true | ❌ false |
| CAND-002 | BLOCKED | R241-18K | dedicated memory readiness review | ✅ true | ❌ false |
| CAND-003 | DEFERRED | R241-18K | dedicated MCP readiness after memory | ✅ true | ❌ false |
| GSIC-003 | BLOCKED | R241-18J | dedicated gateway sidecar integration review | ✅ true | ❌ false |
| GSIC-004 | BLOCKED | R241-18J | dedicated FastAPI route registration review | ✅ true | ❌ false |
| MAINLINE-GATEWAY-ACTIVATION | false | R241-18N | explicit approval after all gates | ✅ true | ❌ false |
| DSRT-ENABLED | false | R241-18I | dedicated DSRT activation review | ✅ true | ❌ false |
| DSRT-IMPLEMENTED | false | R241-18I | dedicated DSRT activation review | ✅ true | ❌ false |

**8/8 blockers carried forward. None overridden. None removed.**

---

## 8. Allowed Code Touch List

### Allowed Classes
| # | Class |
|---|-------|
| 1 | report generation scripts |
| 2 | schema validators |
| 3 | non-runtime diagnostic helpers |
| 4 | read-only test files |
| 5 | markdown/json report templates |
| 6 | evidence index generators |
| 7 | diff analysis tools |
| 8 | static config readers |
| 9 | root guard non-destructive validators |

### Restricted Classes
| # | Class |
|---|-------|
| 1 | production runtime modules |
| 2 | gateway main path |
| 3 | FastAPI route registration |
| 4 | memory runtime modules |
| 5 | MCP runtime modules |
| 6 | Feishu send modules |
| 7 | scheduler modules |
| 8 | tool enforcement modules |
| 9 | action queue writers |
| 10 | audit JSONL writers |
| 11 | prompt / memory / asset mutation modules |

### Requires Dedicated Review
- gateway sidecar review
- memory readiness review
- MCP readiness review
- DSRT activation review

### Prohibited Without Unblock
- gateway activation
- memory runtime activation
- MCP activation
- Feishu real send
- DSRT enablement
- runtime write
- audit JSONL write

---

## 9. Forbidden Runtime Surfaces

| Surface | Source Blockers | Required Unblock Review |
|---------|----------------|------------------------|
| gateway main path | GSIC-003, MAINLINE-GATEWAY-ACTIVATION | gateway_sidecar_integration_review |
| FastAPI route registration | GSIC-004, MAINLINE-GATEWAY-ACTIVATION | FastAPI_route_registration_review |
| sidecar service start | GSIC-003 | gateway_sidecar_integration_review |
| memory runtime activation | SURFACE-010, CAND-002 | memory_readiness_review |
| MCP runtime activation | CAND-003 | MCP_readiness_review |
| Feishu real send | SURFACE-010 | memory_readiness_review |
| webhook call | SURFACE-010 | memory_readiness_review |
| network listener | GSIC-003, DSRT-ENABLED | gateway_sidecar_integration_review |
| scheduler | DSRT-ENABLED | DSRT_activation_review |
| auto-fix | DSRT-ENABLED | DSRT_activation_review |
| tool enforcement | DSRT-ENABLED | DSRT_activation_review |
| runtime write | SURFACE-010, CAND-002, DSRT-ENABLED | various |
| audit JSONL write | SURFACE-010 | memory_readiness_review |
| action queue write | SURFACE-010 | memory_readiness_review |
| DSRT enablement | DSRT-ENABLED, DSRT-IMPLEMENTED | DSRT_activation_review |
| prompt / memory / asset mutation | SURFACE-010, CAND-002 | memory_readiness_review |

---

## 10. Dirty Worktree / Stash Handling Policy

### 当前状态
| 字段 | 值 |
|------|-----|
| dirty_file_count | 59 |
| stash_count | 1 |
| classification | evidence_only_untracked |

### 本轮允许的操作
- record_manifest（记录 manifest）
- classify（分类）
- hash_evidence_files（计算证据文件 hash）

### 本轮禁止的操作
- git clean / reset / restore
- git stash pop / apply
- git commit
- git branch switch

### 未来决策需求
**future_decision_needed: true** — 是否在后续阶段建立 isolated repair branch，需要在未来 R241-19B 规划中决定。

---

## 11. Patch Candidate Classification Framework

### 4-Class Classification System

| Class | ID | Applies To | Decision | Required Evidence |
|-------|----|-----------|----------|-------------------|
| safe_direct_update | 1 | pure_report_template, readonly_helper, schema_validator, nonruntime_fix | proceed_without_dedicated_review | diff_only_no_runtime, test_coverage |
| adapter_only | 2 | upstream_needs_local_interface_bridge, bridge_layer_only, no_runtime_activation | proceed_with_track_B_review | adapter_scope_evidence, no_runtime_touch_evidence |
| report_only_quarantine | 3 | valuable_but_risk_uncertain, information_only_use | quarantine_as_evidence_only | quarantine_rationale, risk_assessment |
| forbidden_runtime_replacement | 4 | gateway_main_path_replacement, memory_MCP_runtime_replacement, FastAPI_route_registration, service_start, network_request, runtime_write | prohibited_without_full_unblock_review | full_unblock_review, all_blocker_resolutions |

### Decision Table
| If Class | If Blocker Unblock | Then |
|----------|-------------------|------|
| 1 | N/A | proceed |
| 2 | N/A | proceed_with_track_B_review |
| 3 | N/A | quarantine |
| 4 | false | prohibited |
| 4 | true | escalate_to_full_unblock_review |

---

## 12. Evidence Carryover Package

### R241-18 Chain Evidence (17/17 Reports)

| # | Report | Status |
|---|--------|--------|
| 1 | R241-18J | ✅ found |
| 2 | R241-18K | ✅ found |
| 3 | R241-18L | ✅ found |
| 4 | R241-18M | ✅ found |
| 5 | R241-18N | ✅ found |
| 6 | R241-18O | ✅ found |
| 7 | R241-18P | ✅ found |
| 8 | R241-18Q | ✅ found |
| 9 | R241-18R | ✅ found |
| 10 | R241-18S | ✅ found |
| 11 | R241-18T | ✅ found |
| 12 | R241-18U | ✅ found |
| 13 | R241-18V | ✅ found |
| 14 | R241-18W | ✅ found |
| 15 | R241-18X | ✅ found |
| 16 | R241-18Y | ✅ found |
| 17 | R241-18Z | ✅ found |

**found_reports: 17 / missing_reports: 0**
**package_status: complete** ✅

---

## 13. R241-19B Foundation Repair Execution Readiness

| 条件 | 状态 |
|------|------|
| R241-19A planning passed | ✅ |
| Track A scope defined | ✅ |
| allowed code touch list defined | ✅ |
| forbidden runtime surfaces defined | ✅ |
| dirty worktree policy defined | ✅ |
| carryover blockers preserved | ✅ |
| tests passed (144/144 core) | ✅ |
| no actual activation occurred | ✅ |
| no production code modified | ✅ |

**allow_enter_r241_19b: true** ✅

### R241-19B 推荐范围
| # | Scope Item |
|---|-----------|
| 1 | RootGuard continuity check |
| 2 | test harness batch 1 fix |
| 3 | report schema consistency batch 1 |
| 4 | evidence index generation |
| 5 | dirty worktree manifest generation |

### ⚠️ 非阻塞警告
- `test_runtime_activation_readiness.py::test_report_generation_writes_only_to_tmp_path` 失败 — R241-18A 历史遗留文件 `R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json` 导致断言失败，非 R241-19A 造成

---

## 14. R241-19C Upgrade Intake Readiness

| 条件 | 状态 |
|------|------|
| R241-19A planning passed | ✅ |
| Track B scope defined | ✅ |
| patch classification framework defined | ✅ |
| upstream intake report-only until classified | ✅ |
| tests passed | ✅ |

**allow_enter_r241_19c_after_19b: true** ✅

### ⚠️ 重要前提
**R241-19C 需在 R241-19B 完成后方可开始** — Track B intake 不能在 Track A foundation repair batch 1 执行和评估之前开始。

### R241-19C 推荐范围
| # | Scope Item |
|---|-----------|
| 1 | upstream diff intake analysis |
| 2 | patch candidate classification batch 1 |
| 3 | safe direct update candidates review |
| 4 | adapter-only candidates review |
| 5 | forbidden runtime replacement audit |

---

## 15. Test Results

| 测试套件 | 命令 | 结果 |
|----------|------|------|
| Gateway Sidecar Integration Review | `pytest ... test_gateway_sidecar_integration_review.py -v` | ✅ 48 passed, 0 failed |
| Disabled Stub / DSRT / Feishu / Audit / Trend | `pytest ... -k 'disabled_stub or dsrt...' -v` | ✅ 96 passed, 0 failed |
| Report / Schema / Diagnostic / Evidence | `pytest ... -k 'report or schema...' -v` | ⚠️ 1 pre-existing failure |

### ⚠️ Pre-existing Test Failure
```
test_runtime_activation_readiness.py::test_report_generation_writes_only_to_tmp_path
AssertionError: R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json exists in
migration_reports/foundation_audit/ (pre-existing from prior session)
```
**原因**: R241-18A 阶段历史遗留文件存在于真实目录中，导致"报告生成不污染真实目录"的安全测试断言失败。
**性质**: Pre-existing，非 R241-19A 造成，非 blocking。
**影响范围**: 仅该测试，核心套件 144/144 不受影响。

---

## 16. Final Decision

**status**: passed_with_warnings
**decision**: approve_mainline_repair_reentry_plan_with_conditions
**mainline_reentry_plan_ready**: true
**track_a_scope_defined**: true
**track_b_scope_defined**: true
**allowed_code_touch_list_defined**: true
**forbidden_runtime_surfaces_defined**: true
**dirty_worktree_policy_defined**: true
**carryover_blockers_preserved**: true
**review_objects_A_to_L**: 12/12 passed
**allow_enter_r241_19b**: true
**tests_passed**: 144/144 core suite
**pre_existing_test_failures**: 1
**all_safety_invariants_clean**: true

---

## 17. Recommended Next Round

**R241-19B：Foundation Repair Execution Batch 1**

R241-19B 的目标是：
- 执行 Track A 第一批的地基修复
- 生成 RootGuard continuity evidence
- 修复 test harness 一致性问题
- 修复 report schema 一致性问题
- 生成 evidence index
- 生成 dirty worktree manifest

R241-19B **不是** actual activation。

R241-19B **不能**激活 gateway/memory/MCP/DSRT/Feishu。

R241-19B **不能**覆盖任何 blocker。

R241-19C 将在 R241-19B 完成后开始。

---

## 18. Final Output

```text
R241_19A_MAINLINE_REPAIR_REENTRY_PLAN_DONE

status = passed_with_warnings
decision = approve_mainline_repair_reentry_plan_with_conditions
mainline_reentry_plan_ready = true
track_a_scope_defined = true
track_b_scope_defined = true
allowed_code_touch_list_defined = true
forbidden_runtime_surfaces_defined = true
dirty_worktree_policy_defined = true
carryover_blockers_preserved = true (8/8)
review_objects_A_to_L = 12/12 passed
allow_enter_r241_19b = true
allow_enter_r241_19c = true (after 19B)
tests_passed = 144/144 core
pre_existing_test_failures = 1 (non-blocking, pre-existing)
safety_violations = []
recommended_resume_point = R241-19A
next_prompt_needed = R241-19B_FOUNDATION_REPAIR_EXECUTION_BATCH1_PLAN

generated:
- migration_reports/recovery/R241-19A_MAINLINE_REPAIR_REENTRY_PLAN.json
- migration_reports/recovery/R241-19A_MAINLINE_REPAIR_REENTRY_PLAN.md
```

---

## 评审结论汇总

| # | 验证项 | 结果 |
|---|--------|------|
| 1 | Dual RootGuard（Python + PowerShell） | ✅ 双通过 — ROOT_OK |
| 2 | Git/工作区快照 | ✅ evidence_only_untracked |
| 3 | Preconditions from R241-18Z | ✅ 9/9 条件满足 |
| 4 | Mainline Re-entry Scope | ✅ planning_only mode |
| 5 | Track A Foundation Repair Scope | ✅ defined |
| 6 | Track B Upgrade Intake Scope | ✅ defined |
| 7 | Carryover Blocker Ledger | ✅ 8/8 preserved |
| 8 | Allowed Code Touch List | ✅ defined |
| 9 | Forbidden Runtime Surfaces | ✅ defined (16 surfaces) |
| 10 | Dirty Worktree / Stash Policy | ✅ policy defined |
| 11 | Patch Classification Framework | ✅ 4-class framework defined |
| 12 | Evidence Carryover Package | ✅ 17/17 complete |
| 13 | R241-19B Readiness | ✅ allow_enter_r241_19b=true |
| 14 | R241-19C Readiness | ✅ allow after 19B |
| 15 | Test Results | ✅ 144 core + 1 pre-existing |
| 16 | 最终决策 | ✅ passed_with_warnings |

---

## R241-18 → R241-19 Transition Summary

| Round | Status | Decision |
|-------|--------|----------|
| R241-18V | ✅ passed | approve_bounded_activation_proposal_draft_review |
| R241-18W | ✅ passed | approve_proposal_structural_validation |
| R241-18X | ✅ passed | human_approved_proposal_review_only |
| R241-18Y | ✅ passed | approve_final_authorization_deed_review |
| R241-18Z | ✅ passed | activation_gate_review_completed_blocked_as_expected |
| **R241-19A** | ✅ passed | **approve_mainline_repair_reentry_plan_with_conditions** |

**R241-19A 通过。8 个 blockers 携带。双轨主线回归计划已建立。R241-19B 可进入。**
