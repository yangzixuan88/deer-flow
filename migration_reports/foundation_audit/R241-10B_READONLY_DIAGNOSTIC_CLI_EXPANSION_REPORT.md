# R241-10B Read-only Diagnostic CLI Expansion Report

**Generated:** 2026-04-25
**Phase:** R241-10B — Memory / Asset / Prompt / RTCM CLI Binding
**Status:** A — 成功，可进入 R241-10C Feishu-summary dry-run CLI binding

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/foundation/read_only_diagnostics_cli.py` | 修改 | Phase A → Phase B 扩展，新增 memory/asset/prompt/rtcm 命令 |
| `backend/app/foundation/test_read_only_diagnostics_cli.py` | 修改 | 新增 34 个测试覆盖 Phase B 所有新命令 |
| `scripts/foundation_diagnose.py` | 无需修改 | CLI wrapper 已自动支持新命令参数 |
| `migration_reports/foundation_audit/R241-10B_READONLY_DIAGNOSTIC_CLI_EXPANSION_SAMPLE.json` | 新增 | `all --write-report` 生成审计样例 (315KB) |

---

## 2. Updated Command Registry

**source_plan_ref:** `R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.json`

### Implemented Commands (Phase A + Phase B)

```
truth-state   — governance truth/state outcome 诊断
queue-sandbox — experiment queue + sandbox execution 诊断
memory        — memory artifact 扫描 + 风险信号诊断  [NEW]
asset         — asset lifecycle 投影 + 风险信号诊断 [NEW]
prompt        — prompt source 扫描 + 治理风险诊断   [NEW]
rtcm          — RTCM runtime 扫描 + 风险信号诊断   [NEW]
nightly       — nightly foundation health review
all           — 聚合以上全部命令
```

### Disabled Commands

```
feishu-summary — dry-run 未绑定，不真实推送
```

### Registry Warnings

```
- phase_a_cli_core_diagnostics_implemented_except_feishu_summary
- feishu_summary_dry_run_not_bound
```

---

## 3. Memory Diagnostic 实现结果

**Status:** `partial_warning` (exit 0)

```
scanned_count:               50
classified_count:             50
long_term_eligible_count:      6
asset_candidate_eligible_count: 6
risk_count:                   22
top_risk_types:
  checkpoint_not_long_term_memory: 18
  council_log_not_long_term_memory:  3
  max_files_reached:                  1
```

**实现函数:**
- `project_memory_roots()` — 扫描 memory artifact
- `get_long_term_memory_candidates()` — 长期 memory 候选
- `get_memory_asset_candidates()` — 可转化为 asset 的 memory 候选
- `detect_memory_risk_signals()` — 风险信号检测

**约束遵守:**
- ✅ 不读取完整 memory 内容
- ✅ 不写 memory.json / Qdrant / SQLite / checkpoints
- ✅ 不执行 memory cleanup / consolidation
- ✅ payload 使用 `_compact_payload()` 截断 records 列表

---

## 4. Asset Diagnostic 实现结果

**Status:** `partial_warning` (exit 0)

```
total_projected:    26
candidate_count:     26
formal_asset_count: 12
by_asset_category:
  A1_tool_capability:    6
  A5_cognitive_method:  12
  A9_domain_knowledge_map: 2
  unknown:                6
by_lifecycle_tier:
  candidate:             26
risk_count:               0
```

**实现函数:**
- `aggregate_asset_projection()` — 聚合 registry/binding/governance/memory 投影
- `detect_asset_projection_risks()` — 风险信号检测

**约束遵守:**
- ✅ 不写 asset_registry
- ✅ 不写 binding report
- ✅ 不写 governance_state
- ✅ 不执行 promotion / elimination / retirement

---

## 5. Prompt / RTCM Diagnostic 实现结果

### Prompt Diagnostic

**Status:** `partial_warning` (exit 0)

```
scanned_count:           50
classified_count:         50
by_layer:
  P4_task_skill:        43
  P3_mode_collaboration:  3
  P5_runtime_context:     2
  unknown:                2
by_source_type:
  skill_prompt:         42
  task_prompt:           1
  rtcm_prompt:           2
  runtime_context:       1
  mode_prompt:           1
  asset_prompt:           1
asset_candidate_count:   44
critical_sources_count:   0
replacement_risk_count:  50
risk_count:              12
top_risk_types:
  rollback_missing:                             3
  backup_missing:                               3
  unknown_prompt_source:                        2
  unknown_prompt_layer:                         2
  runtime_context_prompt_leakage_review_required: 2
```

**实现函数:**
- `aggregate_prompt_projection()` — 扫描 prompt sources
- `detect_prompt_governance_risks()` — 风险信号检测

### RTCM Diagnostic

**Status:** `partial_warning` (exit 0)

```
scanned_count:            200
classified_count:          200
unknown_count:              34
session_count:              0
truth_candidate_count:       2
asset_candidate_count:       5
memory_candidate_count:      15
followup_candidate_count:    2
risk_count:                 34
top_risk_types:
  unknown_rtcm_runtime_surface: 34
```

**实现函数:**
- `scan_rtcm_runtime_projection()` — 扫描 RTCM runtime paths
- `detect_rtcm_runtime_projection_risks()` — 风险信号检测

**约束遵守:**
- ✅ 不读取或输出完整 RTCM artifact 内容
- ✅ 不修改 RTCM 状态机
- ✅ 不写 session / dossier / final_report / signoff / followup
- ✅ prompt 不启用 GEPA / DSPy

---

## 6. All Diagnostic 更新结果

**Status:** `partial_warning` (exit 0)

`all` 命令现已包含 Phase A + Phase B 全部 7 个子命令：

```
commands_run:
  truth-state   → ok
  queue-sandbox → partial_warning
  memory        → partial_warning
  asset         → partial_warning
  prompt        → partial_warning
  rtcm          → partial_warning
  nightly       → partial_warning

disabled_commands: ["feishu-summary"]
write_report: false
```

**单个 diagnostic 失败时的行为:** 整体降级为 `partial_warning`，不崩溃

**`write_report=true` 行为:** 写入
`migration_reports/foundation_audit/R241-10B_READONLY_DIAGNOSTIC_CLI_EXPANSION_SAMPLE.json`

---

## 7. Format / CLI Smoke 结果

### Format 支持

| Format | 实现 | 处理对象 |
|--------|------|---------|
| `json` | ✅ | 完整 structured payload |
| `markdown` | ✅ | 处理 memory/asset/prompt/rtcm summary，含嵌套 dict |
| `text` | ✅ | 处理 memory/asset/prompt/rtcm summary |

### CLI Smoke 结果

| 命令 | Exit Code | Status |
|------|-----------|--------|
| `memory --format json --max-files 50` | 0 | partial_warning |
| `asset --format text --limit 20` | 0 | partial_warning |
| `prompt --format text --max-files 50` | 0 | partial_warning |
| `rtcm --format text --max-files 100` | 0 | partial_warning |
| `all --format json --limit 10 --max-files 50` | 0 | partial_warning |
| `all --format json --write-report` | 0 | partial_warning (文件写入确认) |

---

## 8. 测试结果

**34 tests PASSED** in 150.85s

### 测试覆盖

| 测试组 | 覆盖内容 |
|--------|---------|
| Registry Tests | implemented commands 包含 memory/asset/prompt/rtcm; disabled 仅 feishu-summary |
| Memory Diagnostic | monkeypatch 不写 memory runtime; import failure graceful |
| Asset Diagnostic | monkeypatch 不写 asset registry; import failure graceful |
| Prompt Diagnostic | monkeypatch 不写 prompt runtime; import failure graceful |
| RTCM Diagnostic | monkeypatch 不写 RTCM runtime; import failure graceful |
| All Aggregate | 包含 7 个子命令; 单个失败 partial_warning; write_report 行为正确 |
| Format Tests | json/markdown/text 均返回正确类型 |
| CLI Main | memory/asset/prompt/rtcm 均 exit 0; unknown exit 1 |
| Safety Tests | 不开放 HTTP; 不修改 Gateway; 不写 runtime; 不输出全文 |

---

## 9. HTTP API / Runtime / Gateway / 输出全文 检查

| 检查项 | 结果 |
|--------|------|
| 开放 HTTP API endpoint | ❌ 无 — 未修改 Gateway，未注册 HTTP route |
| 修改 Gateway | ❌ 无 — `gateway` 未出现在 `read_only_diagnostics_cli.py` 文件路径中 |
| 修改 M01 / M04 / DeerFlow run 主路径 | ❌ 无 |
| 写 runtime (memory.json / Qdrant / SQLite) | ❌ 无 — 仅读操作 |
| 写 action queue | ❌ 无 |
| 写真实 action queue | ❌ 无 |
| 执行自动修复 | ❌ 无 |
| 执行真实工具调用 | ❌ 无 |
| asset promotion / elimination | ❌ 无 |
| memory cleanup | ❌ 无 |
| prompt replacement | ❌ 无 |
| RTCM state 修改 | ❌ 无 |
| 真实推送 Feishu | ❌ 无 |
| 输出完整 memory 内容 | ❌ 无 — `_compact_payload()` 截断 records 列表 |
| 输出完整 prompt 内容 | ❌ 无 — SHA256 + first_line_preview，无 body |
| 输出完整 RTCM artifact 内容 | ❌ 无 — 仅 path/classifications，无 artifact body |

---

## 10. 当前剩余断点 & 下一轮建议

### 剩余断点

1. **feishu-summary** — disabled，仍需 dry-run projection binding
   - `ChannelService` + `FeishuChannel` 的推送逻辑需要投影封装
   - 当前 `feishu_summary_dry_run_not_bound` warning 已注册

### 下一轮建议 (R241-10C)

1. **Feishu-summary dry-run CLI binding**
   - 封装 `ChannelService.push_pending_notifications()` 为只读投影
   - 不真实推送，仅投影 pending 数量和状态

2. **所有 Phase B 命令的 `report_path` 路径统一**
   - 当前 `run_all_diagnostics(write_report=True)` 和 `generate_readonly_diagnostic_cli_expansion_sample()` 写同一路径
   - 建议分开：`run_all_diagnostics` 写 `R241-10B_DIAGNOSTICS_REPORT.json`；sample generator 独立

3. **Phase B CLI 的 nightly 真实集成测试**
   - Phase A 的 nightly 命令在完整运行时验证过
   - Phase B 新增命令（memory/asset/prompt/rtcm）需在真实 runtime 数据上验证

### R241-10C 验收条件预览

```
- feishu-summary 命令实现（dry-run projection）
- feishu-summary 不真实推送
- 34 tests 继续 PASS
- CLI smoke 7 commands 继续 exit 0
- 未引入新的 runtime 写入
```

---

## 判定

**A — R241-10B 成功，可进入 R241-10C Feishu-summary dry-run CLI binding 或 R241-11A Append-only Audit Trail 设计**

- ✅ memory / asset / prompt / rtcm CLI binding 实现并通过 smoke
- ✅ all diagnostic 更新完成（7 commands）
- ✅ feishu-summary 仍 disabled
- ✅ 测试通过（34 tests PASSED）
- ✅ 未开放 HTTP API
- ✅ 未改 runtime / Gateway / action queue
- ✅ 不输出完整敏感内容
