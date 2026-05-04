# R241-13C Feishu Trend CLI Preview Implementation Report

**Generated:** 2026-04-25
**Phase:** R241-13C — Feishu Trend CLI Preview
**Status:** ✓ 完成 — Phase C 完成，CLI preview 实现

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/audit/audit_trend_feishu_contract.py` | 修改 | 新增 `FeishuTrendPreviewFormat` 和 `FeishuTrendPreviewStatus` enums |
| `backend/app/audit/audit_trend_feishu_preview.py` | 新增 | R241-13C 核心实现 — CLI preview 3 个函数 |
| `backend/app/audit/test_audit_trend_feishu_preview.py` | 新增 | 32 个测试覆盖所有 preview 函数 |
| `backend/app/audit/__init__.py` | 修改 | 导出 preview 模块 3 个函数 + 2 个新 enums |
| `backend/app/foundation/read_only_diagnostics_cli.py` | 修改 | 添加 `audit-trend-feishu` CLI 命令 |
| `backend/app/audit/audit_trend_cli_guard.py` | 修改 | 修复 `compare_audit_jsonl_line_counts` 逻辑（preflight bug） |
| `backend/app/audit/audit_trend_feishu_projection.py` | 修改 | 修复 `generate_feishu_trend_payload_projection` guard 字典提取 bug |

---

## 2. Preflight 修复（2 个 bug）

### Bug 1: `compare_audit_jsonl_line_counts` 误报新增文件为变更

**文件:** `audit_trend_cli_guard.py:compare_audit_jsonl_line_counts`

**问题:** 比较逻辑使用 `before_counts | after_counts`（并集），当 dry-run 在 `before` 不存在的文件中写入新记录时，`None != N` 被判定为"变更"。

**根因:** `capture_audit_jsonl_line_counts` 对缺失文件返回 `warnings: ["audit_jsonl_missing:..."]`，dry-run 本身会生成/写入新的 audit JSONL（如 `feishu_summary_dryruns.jsonl`），导致比较时误判。

**修复:**
```python
# 修复前（bug）：联合所有路径，无视新增/缺失
all_paths = sorted(set(before_counts) | set(after_counts))

# 修复后：仅比较两个 snapshot 都有的文件
common_paths = sorted(set(before_counts) & set(after_counts))
# 新增/缺失的文件 -> warnings（不是 errors）
```

**效果:** `audit_jsonl_unchanged` 现在正确反映共有文件的行数变化，不因新增文件而误报。

### Bug 2: `generate_feishu_trend_payload_projection` 传错 guard 对象

**文件:** `audit_trend_feishu_projection.py:generate_feishu_trend_payload_projection`

**问题:** `run_guarded_audit_trend_cli_projection` 返回外层 dict `{"guard": {...}, "trend_report": {...}, ...}`，但代码直接将外层 dict 传给 `build_feishu_trend_sections(guard=guard_result)`。外层 dict 没有 `audit_jsonl_unchanged` 字段，`guard.get(...)` 返回 `None` → `bool(None) = False` → card 显示 `"false"`。

**修复:**
```python
# 修复前（bug）：传整个外层 dict
guard=guard_result

# 修复后：提取内层 guard dict
guard = guard_result.get("guard") if guard_result else None
payload = build_feishu_trend_payload_projection(..., guard=guard, ...)
```

**效果:** `guard_summary` 中 `audit_jsonl_unchanged` 显示为 `"true"`（与实际一致）。

---

## 3. R241-13C 新增的 3 个函数

### 3.1 `format_feishu_trend_payload_preview(payload, format)` → `str`

将 FeishuTrendPayloadProjection 格式化为可读的 CLI 输出。

| format | 输出内容 |
|--------|---------|
| `text` | 分栏 ASCII 格式，含 SAFETY FLAGS / SECTIONS / VALIDATION |
| `markdown` | GitHub-flavored markdown，含表格和安全标志 |
| `json` | 精简的 payload JSON（双重编码的 preview 字段） |

### 3.2 `run_feishu_trend_preview_diagnostic(window, format)` → `dict`

端到端诊断：
1. `generate_feishu_trend_payload_projection(...)` — projection + validation
2. `format_feishu_trend_payload_preview(...)` — 格式化输出

返回 `FeishuTrendPreviewStatus` 状态 (`success`/`failed`/`no_data`/`validation_error`)。

### 3.3 `generate_feishu_trend_preview_sample(output_path, format)` → `dict`

生成 R241-13C sample 文件，不写入 audit JSONL / runtime / action queue。

---

## 4. CLI 命令

### `audit-trend-feishu`

```
python -m app.foundation.read_only_diagnostics_cli audit-trend-feishu \
    [--format {text,json,markdown}] [--window {last_24h,last_7d,last_30d,all_available}]
```

**行为:**
- 运行 `run_feishu_trend_preview_diagnostic(...)`
- 按格式打印 preview
- Exit code: `0` (success/no_data) / `1` (failed/validation_error)

**约束（与 R241-13B 一致）:**
- 不发送 Feishu 消息
- 不调用 webhook
- 不写入 audit JSONL
- 不写入 runtime / action queue
- 不执行 auto-fix

---

## 5. 测试结果

| 测试类 | 数量 | 状态 |
|--------|------|------|
| `TestFormatPreview` | 7 | 全部通过 |
| `TestPreviewDiagnostic` | 6 | 全部通过 |
| `TestPreviewSample` | 4 | 全部通过 |
| `TestSafetyConstraints` | 3 | 全部通过 |
| `TestPreviewEnums` | 2 | 全部通过 |
| `TestCliIntegration` | 6 | 全部通过 |
| `TestGuardDataIntegrity` | 3 | 全部通过 |
| **R241-13C 合计** | **32** | **全部通过** |

**回归测试（R241-13B + R241-13C + 相关模块）:**
| 模块 | 测试数 | 状态 |
|------|--------|------|
| `test_audit_trend_feishu_projection.py` | 33 | 全部通过 |
| `test_audit_trend_feishu_preview.py` | 32 | 全部通过 |
| `test_audit_trend_cli_guard.py` | 17 | 全部通过 |
| `test_audit_trend_projection.py` | 26 | 全部通过 |
| **合计** | **108** | **全部通过** |

---

## 6. 安全性验证

### 6.1 约束验证

| 约束 | 实现方式 |
|------|---------|
| 不发送 Feishu | `send_allowed=False` + 无 webhook 调用代码 |
| 不调用 webhook | `no_webhook_call=True` + 无网络调用 |
| 不写 audit JSONL | `append_audit_record_to_target` monkeypatch 测试验证 |
| 不写 runtime | `no_runtime_write=True` |
| 不写 action queue | `no_action_queue_write=True` |
| 不执行 auto-fix | `no_auto_fix=True` |

### 6.2 Preview 特有约束

| 约束 | 验证 |
|------|------|
| Preview 不含 webhook URL | 测试验证 preview 文本无 `https?://` |
| Sample 不调用 audit write | monkeypatch `append_audit_record_to_target` 计数验证 |

---

## 7. 依赖关系（仅读）

```
audit_trend_feishu_preview.py
├── audit_trend_feishu_projection.py  (generate_feishu_trend_payload_projection, validate — read only)
├── audit_trend_feishu_contract.py    (enums, schemas — read only)
└── audit_trend_projection.py         (generate_dryrun_nightly_trend_report — read only)

read_only_diagnostics_cli.py
└── audit_trend_feishu_preview.py    (run_feishu_trend_preview_diagnostic — read only)
```

---

## 8. Preflight 修复对 R241-13B 的影响

| 修复 | R241-13B 影响 |
|------|-------------|
| `compare_audit_jsonl_line_counts` | `audit_jsonl_unchanged` 从 `false` 变为 `true`（正确值） |
| `generate_feishu_trend_payload_projection` | `guard["audit_jsonl_unchanged"]` 从 `None` 变为 `true`（card 显示正确） |

**重新生成的 R241-13B sample** (`R241-13B_FEISHU_TREND_PAYLOAD_PROJECTION_SAMPLE.json`) 中：
- `guard_summary.audit_jsonl_unchanged = true` ✓
- `sections[guard_summary].items[audit_jsonl_unchanged].value = "true"` ✓
- `validation.line_count_changed = false` ✓

---

## 9. R241-13 整体进度

| Phase | 状态 | 说明 |
|-------|------|------|
| R241-13A | ✓ | Feishu Trend Dry-run Design Contract |
| R241-13B | ✓ | Feishu Trend Payload Projection（修复后重新验证通过） |
| R241-13C | ✓ | Feishu Trend CLI Preview（本轮） |
| R241-13D | 待开始 | Manual send policy design |

---

## 10. 下一轮建议（R241-13D）

1. 设计 Manual send policy：webhook 策略验证、用户确认流程、脱敏审核
2. 实现 `send_allowed=true` 的 Feishu 实际发送路径
3. 添加 `--dry-run` 确认模式：`audit-trend-feishu --dry-run --send`
4. 考虑 card JSON 预览的 rich terminal 输出（彩色格式化）
