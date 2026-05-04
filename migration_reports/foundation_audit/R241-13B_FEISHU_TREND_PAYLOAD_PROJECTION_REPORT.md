# R241-13B Feishu Trend Payload Projection Implementation Report

**Generated:** 2026-04-25
**Phase:** R241-13B — Feishu Trend Payload Projection
**Status:** A — 成功，Phase D 完成

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/audit/audit_trend_feishu_projection.py` | 新增 | R241-13B 核心实现 — Feishu Trend Payload Projection |
| `backend/app/audit/__init__.py` | 修改 | 导出 projection 模块 6 个函数 |
| `backend/app/audit/test_audit_trend_feishu_projection.py` | 新增 | 33 个测试覆盖所有 projection 函数 |

---

## 2. 实现的 6 个函数

### 2.1 build_feishu_trend_sections

构建 FeishuTrendCardSection 列表（8 个 section）。

| Section | 说明 |
|---------|------|
| `headline` | 单行趋势健康标题 |
| `trend_overview` | 窗口/记录数/series/regression 统计 |
| `regression_summary` | 最多 5 条回归信号（consolidated 成单个 section） |
| `guard_summary` | 安全 guard 结果（audit_jsonl_unchanged 等） |
| `artifact_links` | 仅接受 `migration_reports/foundation_audit/` 下的报告 artifact |
| `warnings` | 最多 8 条警告 |
| `next_step` | 推荐的下一步操作 |
| `safety_notice` | projection_only 声明 |

关键约束：
- `regression_summary` 不超过 5 条（合并为单个 section 中的 items）
- `warnings` 不超过 8 条
- `artifact_links` 拒绝 `audit_trail/`、`runtime/`、`action_queue/` 路径

### 2.2 build_feishu_trend_card_json

从 sections 构建 Feishu/Lark card JSON。

- 返回标准 Feishu card 结构：`config`、`header`、`elements`
- `_safety` 字段标注 `projection_only`、`send_allowed=false`、`no_network_call`
- 不包含 webhook URL / token / secret
- JSON 可序列化验证

### 2.3 build_feishu_trend_payload_projection

核心 projection 函数，生成 `FeishuTrendPayloadProjection` dict。

强制字段：

| 字段 | 值 |
|------|-----|
| `status` | `projection_only` |
| `send_permission` | `projection_only` |
| `send_allowed` | `false` |
| `webhook_required` | `true` |
| `no_webhook_call` | `true` |
| `no_runtime_write` | `true` |
| `no_action_queue_write` | `true` |
| `no_auto_fix` | `true` |

### 2.4 validate_feishu_trend_payload_projection

验证 projection 的安全性，返回 `FeishuTrendValidationResult`。

检查规则：
- `send_allowed is False`
- `status in {projection_only, design_only}`
- `no_webhook_call is True`
- `no_runtime_write is True`
- `no_action_queue_write is True`
- `no_auto_fix is True`
- webhook URL / token / secret / api_key 不存在
- artifact links 仅指向 report artifacts
- `guard.audit_jsonl_unchanged != False`
- `guard.sensitive_output_detected != True`
- `guard.network_call_detected != True`

### 2.5 generate_feishu_trend_payload_projection

端到端 dry-run projection：

1. `run_guarded_audit_trend_cli_projection(write_report=False)`
2. `generate_dryrun_nightly_trend_report(...)`
3. `build_feishu_trend_payload_projection(...)`
4. `validate_feishu_trend_payload_projection(...)`

### 2.6 generate_feishu_trend_payload_projection_sample

生成 sample 到 `migration_reports/foundation_audit/R241-13B_FEISHU_TREND_PAYLOAD_PROJECTION_SAMPLE.json`。

---

## 3. 测试结果

| 测试类 | 数量 | 状态 |
|--------|------|------|
| `TestBuildSections` | 7 | 全部通过 |
| `TestBuildCardJson` | 3 | 全部通过 |
| `TestPayloadProjection` | 8 | 全部通过 |
| `TestValidation` | 8 | 全部通过 |
| `TestGenerateProjection` | 1 | 通过 |
| `TestSample` | 2 | 全部通过 |
| `TestSafetyConstraints` | 3 | 全部通过 |
| **合计** | **33** | **全部通过** |

---

## 4. 安全性验证

### 4.1 已禁止的行为

| 约束 | 验证 |
|------|------|
| 不推送 Feishu | `send_allowed=False` + 无 webhook 调用代码 |
| 不调用 webhook | `no_webhook_call=True` + 无网络调用 |
| 不写 audit JSONL | 测试验证 `append_audit_record_to_target` 未被调用 |
| 不写 runtime | `no_runtime_write=True` |
| 不写 action queue | `no_action_queue_write=True` |
| 不执行 auto-fix | `no_auto_fix=True` |
| 不输出 secret/token | `_SENSITIVE_KEY_RE` 检测 |
| 不输出 webhook URL | `_WEBHOOK_RE` 检测 |

### 4.2 Validation 检测的安全违规

| 违规类型 | 检测方式 |
|----------|----------|
| `send_allowed=True` | `send_allowed_is_false` 检查 |
| webhook URL 出现 | `_WEBHOOK_RE` 正则 |
| token/secret/api_key | `_SENSITIVE_KEY_RE` 正则 |
| `audit_jsonl_unchanged=False` | `line_count_changed` 检查 |
| `sensitive_output_detected=True` | `sensitive_content_detected` 检查 |
| `network_call_detected=True` | `blocked_reasons` 包含 `guard_network_call_detected` |
| forbidden artifact path | `_FORBIDDEN_ARTIFACT_PATH_PREFIXES` 列表 |

---

## 5. 依赖关系（仅读）

```
audit_trend_feishu_projection.py
├── audit_trend_feishu_contract.py  (schemas, enums — read only)
├── audit_trend_projection.py       (generate_dryrun_nightly_trend_report, summarize_trend_report — read only)
└── audit_trend_cli_guard.py        (run_guarded_audit_trend_cli_projection — read only)
```

---

## 6. 当前剩余断点

1. **CLI dry-run preview** 未实现（R241-13C 可选）：`audit-trend-feishu` 子命令
2. **Manual send policy** 未设计：webhook 策略、用户确认、脱敏审核
3. **Scheduler integration** 未开始：需要独立 review

---

## 7. 下一轮建议（R241-13C）

1. 实现 `audit-trend-feishu` CLI preview 命令
2. 设计 webhook policy 验证规则
3. 添加 card_json 预览输出（TEXT/MARKDOWN 格式）
4. 考虑添加 `dry_run_preview` 参数控制 artifact 是否写入

---

## 8. R241-13 整体进度

| Phase | 状态 | 说明 |
|-------|------|------|
| R241-13A | ✓ | Feishu Trend Dry-run Design Contract |
| R241-13B | ✓ | Feishu Trend Payload Projection (本轮) |
| R241-13C | 待开始 | audit-trend-feishu CLI dry-run preview |
| R241-13D | 待开始 | Manual send policy design |
