# R241-10C Feishu-summary Dry-run CLI Expansion Report

**Generated:** 2026-04-25
**Phase:** R241-10C — Feishu-summary Dry-run CLI Binding
**Status:** A — 成功，可进入 R241-11A Append-only Audit Trail 设计

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/foundation/read_only_diagnostics_cli.py` | 修改 | Phase C 扩展，新增 feishu-summary 命令 |
| `backend/app/foundation/test_read_only_diagnostics_cli.py` | 修改 | 新增 14 个测试覆盖 Phase C 所有新命令（总计 48 tests） |
| `migration_reports/foundation_audit/R241-10C_FEISHU_SUMMARY_DRYRUN_CLI_SAMPLE.json` | 新增 | `all --write-report` 自动生成审计样例 |
| `migration_reports/foundation_audit/R241-10B_READONLY_DIAGNOSTIC_CLI_EXPANSION_SAMPLE.json` | 不变 | Phase B 样例保持不变 |

---

## 2. Updated Command Registry

**source_plan_ref:** `R241-9B_MINIMAL_READONLY_INTEGRATION_PLAN.json`

### Implemented Commands (Phase A + B + C)

```
truth-state   — governance truth/state outcome 诊断
queue-sandbox — experiment queue + sandbox execution 诊断
memory        — memory artifact 扫描 + 风险信号诊断
asset         — asset lifecycle 投影 + 风险信号诊断
prompt        — prompt source 扫描 + 治理风险诊断
rtcm          — RTCM runtime 扫描 + 风险信号诊断
nightly       — nightly foundation health review
feishu-summary — Feishu card payload projection dry-run  [NEW]
all           — 聚合以上全部命令
```

### Disabled Commands

```
(none) — feishu-summary 已从 disabled 移至 implemented
```

### Registry Warnings

```
- feishu_summary_projection_only   [NEW]
- no_real_feishu_push              [NEW]
- no_webhook_call                  [NEW]
```

**已移除的旧警告：**
- ❌ `phase_a_cli_core_diagnostics_implemented_except_feishu_summary`
- ❌ `feishu_summary_dry_run_not_bound`

---

## 3. Feishu-summary Diagnostic 实现结果

**Status:** `partial_warning` (exit 0)

```
review_loaded:           true
source_review_id:        nightly_review_5539144633
total_signals:          26
critical_count:          2
high_count:              10
action_candidate_count:  26
top_action_count:        10
feishu_payload_status:   projection_only
send_allowed:            false
webhook_required:        true
validation_valid:        true
no_webhook_call:        true
no_runtime_write:       true
```

**实现函数:**
- `run_feishu_summary_diagnostic()` — 只读执行 Feishu summary dry-run 诊断
- 调用链: `load_latest_nightly_review_sample()` → `summarize_review_for_user()` → `build_feishu_card_payload_projection()` → `validate_feishu_payload_projection()`

**约束遵守:**
- ✅ 不真实推送 Feishu / Lark
- ✅ 不调用 webhook
- ✅ 不发送机器人消息
- ✅ 不写 action queue
- ✅ 不写 runtime (memory.json / Qdrant / SQLite / checkpoints)
- ✅ 不修改 Gateway / M01 / M04 / DeerFlow run 主路径
- ✅ `_compact_payload()` 截断 card_json 元素列表

---

## 4. Feishu Card Payload Projection / Validation 结果

**Payload Projection:**
```
status:             projection_only
send_allowed:       false
send_blocked_reason: projection_only_no_webhook_call
webhook_required:    true
no_webhook_call:    true
no_runtime_write:   true
card_json.header.template: red (critical_count > 0)
```

**Validation:**
```
valid: true
blocked_reasons: [] (empty — no violations)
```

`build_feishu_card_payload_projection()` 已在 `foundation_health_summary.py` 中定义并被复用，无需在 CLI 层重新实现。

---

## 5. All Diagnostic 更新结果

**Status:** `partial_warning` (exit 0)

`all` 命令现已包含 Phase A + B + C 全部 8 个子命令：

```
commands_run:
  truth-state    → ok
  queue-sandbox  → partial_warning
  memory         → partial_warning
  asset          → partial_warning
  prompt         → partial_warning
  rtcm           → partial_warning
  nightly        → partial_warning
  feishu-summary → partial_warning

disabled_commands: [] (empty)
write_report: false
```

**单个 diagnostic 失败时的行为:** 整体降级为 `partial_warning`，不崩溃

**`write_report=true` 行为:** 写入
`migration_reports/foundation_audit/R241-10C_FEISHU_SUMMARY_DRYRUN_CLI_SAMPLE.json`

---

## 6. Format / CLI Smoke 结果

### Format 支持

| Format | 实现 | 处理对象 |
|--------|------|---------|
| `json` | ✅ | 完整 structured payload，含 feishu payload projection |
| `markdown` | ✅ | 处理 feishu-summary summary，标注 projection_only/send_allowed/webhook_required |
| `text` | ✅ | 处理 feishu-summary summary，显示关键 projection 字段 |

### CLI Smoke 结果

| 命令 | Exit Code | Status |
|------|-----------|--------|
| `feishu-summary --format json` | 0 | partial_warning |
| `feishu-summary --format markdown` | 0 | partial_warning |
| `feishu-summary --format text` | 0 | partial_warning |
| `all --format json --write-report` | 0 | partial_warning (文件写入确认) |

---

## 7. 测试结果

**48 tests PASSED** in 287.69s

### 测试覆盖

| 测试组 | 覆盖内容 |
|--------|---------|
| Registry Tests | implemented 包含 feishu-summary; disabled 为空; warnings 正确 |
| Feishu Diagnostic | monkeypatch 不调用 webhook; send_allowed=false; import failure graceful |
| All Aggregate | 包含 8 个子命令; 单个失败 partial_warning; write_report 正确 |
| Format Tests | json/markdown/text 支持 feishu-summary |
| CLI Main | feishu-summary json/text 均 exit 0 |
| Safety Tests | 不真实推送; 不调用网络; 不写 action queue; 不输出 webhook URL/secret/token |

---

## 8. 是否真实推送 / 调用 webhook / 写 runtime / 输出 secret

| 检查项 | 结果 |
|--------|------|
| 真实推送 Feishu / Lark | ❌ 无 — `send_allowed=False` |
| 调用 Feishu webhook | ❌ 无 — `no_webhook_call=True` |
| 发送机器人消息 | ❌ 无 — 无 HTTP POST 调用 |
| 写 action queue | ❌ 无 — 只读操作 |
| 写 governance_state | ❌ 无 |
| 写 experiment_queue | ❌ 无 |
| 修改 memory / asset / prompt / RTCM runtime | ❌ 无 |
| 开放 HTTP API endpoint | ❌ 无 |
| 修改 Gateway / M01 / M04 / DeerFlow run 主路径 | ❌ 无 |
| 输出 webhook URL / secret / token | ❌ 无 — card_json 中无 credentials 字段 |
| 执行自动修复 | ❌ 无 |
| 执行真实工具调用 | ❌ 无 |
| asset promotion / elimination | ❌ 无 |

---

## 9. 当前剩余断点 & 下一轮建议

### 剩余断点

无剩余断点。所有 Phase A + B + C 的 9 个命令（truth-state, queue-sandbox, memory, asset, prompt, rtcm, nightly, feishu-summary, all）全部实现并通过测试。

### 下一轮建议 (R241-11A)

**Append-only Audit Trail 设计:**

R241-10A/B/C 完成了 Minimal Read-only Integration CLI 的全部实现。当前 codebase 的只读诊断能力已覆盖：

- truth-state / queue-sandbox（治理 truth/state outcome）
- memory / asset / prompt / rtcm（生命周期各层）
- nightly（foundation health review）
- feishu-summary（dry-run Feishu projection）

R241-11A 可设计 append-only audit trail，将 CLI 每次运行的诊断结果（status/warnings/errors）以 append-only 方式写入审计日志，不覆盖历史记录，支持长期趋势追踪。

### R241-11A 验收条件预览

```
- append-only 审计日志实现
- 不覆盖历史记录
- 每次 CLI 运行追加新条目
- 支持按 command/status/date 过滤
- 不修改已有诊断逻辑
```

---

## 10. 主线任务校准思辨

### 本轮核心决策：复用 vs 封装

本轮的关键设计决策是**直接复用** `foundation_health_summary.py` 中已有的 Feishu payload 函数，而非重新实现：

- ✅ `build_feishu_card_payload_projection()` — 直接复用，输出 `send_allowed=False` 强制 projection-only
- ✅ `validate_feishu_payload_projection()` — 直接复用，验证 projection 合规性
- ✅ `summarize_review_for_user()` / `summarize_review_by_domain()` — 直接复用
- ❌ 不复制粘贴 — 通过 `_safe_call()` 封装，保持 DRY

这种复用策略的优势：
1. **零新增逻辑** — 不引入新的 Feishu payload 构建逻辑，减少维护负担
2. **强制 projection-only** — `build_feishu_card_payload_projection()` 本身就输出 `send_allowed=False`，无需额外约束
3. **验证一致性** — `validate_feishu_payload_projection()` 确保 projection payload 结构正确

### Projection-only 约束的保证机制

`send_allowed=False` 不是靠 CLI 层强制，而是由 `build_feishu_card_payload_projection()` 函数本身保证（第 297 行硬编码 `send_allowed=False`）。这意味着即使有人绕过 CLI 直接调用该函数，仍然是 projection-only。

---

## 判定

**A — R241-10C 成功，可进入 R241-11A Append-only Audit Trail 设计**

- ✅ feishu-summary CLI binding 实现并通过 smoke
- ✅ all diagnostic 覆盖 8 commands（truth-state, queue-sandbox, memory, asset, prompt, rtcm, nightly, feishu-summary）
- ✅ Feishu payload projection `send_allowed=false`，`webhook_required=true`
- ✅ 未真实推送 Feishu / Lark
- ✅ 未调用 webhook / 网络
- ✅ 未写 runtime/Gateway/action queue
- ✅ 未输出 webhook URL / secret / token
- ✅ 测试通过（48 tests PASSED）
- ✅ CLI smoke 通过（4/4 commands exit 0）
- ✅ 未开放 HTTP API
- ✅ command registry 中 feishu-summary 从 disabled 移至 implemented
