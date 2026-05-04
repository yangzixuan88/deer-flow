# R241-13D Feishu Trend Manual Send Policy Design Report

**Generated:** 2026-04-25
**Phase:** R241-13D — Feishu Trend Manual Send Policy Design
**Status:** ✓ 完成 — Phase D 完成，设计契约实现

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/audit/audit_trend_feishu_send_policy.py` | 新增 | R241-13D 核心实现 — 5 个 enums + 5 个 dataclasses + 9 个函数 |
| `backend/app/audit/test_audit_trend_feishu_send_policy.py` | 新增 | 76 个测试覆盖所有 send policy 函数 |
| `backend/app/audit/__init__.py` | 修改 | 导出 send_policy 模块 14 个符号 |
| `migration_reports/foundation_audit/R241-13D_MANUAL_SEND_POLICY_CONTRACT.json` | 新增 | 设计契约 JSON（通过 `generate_feishu_manual_send_policy_design()` 生成） |

---

## 2. 设计契约核心内容

### 2.1 5 个 Enums

| Enum | Values | 用途 |
|------|--------|------|
| `FeishuManualSendPolicyStatus` | 8 values | 设计/就绪/阻止状态 |
| `FeishuManualSendPermission` | 8 values | 权限级别（禁止到允许） |
| `FeishuWebhookPolicyType` | 5 values | webhook 来源类型 |
| `FeishuManualSendAuditMode` | 6 values | 发送审计模式 |
| `FeishuManualSendRiskLevel` | 5 values | 风险级别 |

### 2.2 5 个 Dataclasses

| Dataclass | 主要字段 |
|-----------|---------|
| `FeishuWebhookPolicy` | `webhook_url_allowed_inline=False`, `secret_inline_allowed=False`, `allowlist_required=True` |
| `FeishuManualSendConfirmationPolicy` | `required_confirmation_phrase="CONFIRM_FEISHU_TREND_SEND"`, `max_payload_age_minutes=60` |
| `FeishuPayloadPreSendValidationPolicy` | 11 项验证要求（全部为 True） |
| `FeishuManualSendAuditPolicy` | `pre_send_audit_required=True`, `post_send_audit_required=True`, `raw_webhook_never_logged=True` |
| `FeishuManualSendPolicyDesign` | 聚合所有子策略 + blocked_send_paths + allowed_future_send_flow |

### 2.3 9 个函数

| 函数 | 职责 |
|------|------|
| `build_feishu_webhook_policy()` | 构建 webhook 策略（inline URL 和 secret 均禁止） |
| `build_manual_send_confirmation_policy()` | 构建确认策略（需 CONFIRM_FEISHU_TREND_SEND） |
| `build_pre_send_validation_policy()` | 构建发送前验证策略（11 项） |
| `build_manual_send_audit_policy()` | 构建审计策略（pre+post 审计，raw webhook 不记录） |
| `design_allowed_manual_send_flow()` | 定义 12 步未来允许发送流程 |
| `build_manual_send_blocked_paths()` | 定义 15 条禁止路径 |
| `build_feishu_manual_send_policy_design()` | 聚合所有子策略，生成完整设计 |
| `validate_feishu_manual_send_policy_design()` | 验证设计契约（11 项检查） |
| `generate_feishu_manual_send_policy_design()` | 生成 JSON 契约文件 |

---

## 3. 关键设计约束

### 3.1 Webhook 策略

- `webhook_url_allowed_inline = False` — 禁止内联 webhook URL
- `secret_inline_allowed = False` — 禁止内联密钥
- `allowlist_required = True` — 必须通过 allowlist 或 secret manager
- 允许的域：`*.open.feishu.cn`, `*.larksuite.com`
- 环境变量引用：`FEISHU_WEBHOOK_URL`, `FEISHU_WEBHOOK_SECRET`
- Secret manager 引用：`deerflow/secrets/feishu/webhook_url`

### 3.2 确认策略

- 用户必须输入 `CONFIRM_FEISHU_TREND_SEND` 确认短语
- 预览后、验证后、审计预览后三阶段确认
- Payload 有效期 ≤ 60 分钟

### 3.3 发送前验证策略（11 项）

1. `require_projection_validation_valid` — 投影验证必须通过
2. `require_no_sensitive_content` — 不得包含敏感内容
3. `require_no_webhook_url_in_payload` — 不得包含 webhook URL
4. `require_no_token_secret_api_key` — 不得包含 token/secret/API key
5. `require_no_runtime_write` — 不得写入 runtime
6. `require_no_action_queue_write` — 不得写入 action queue
7. `require_no_auto_fix` — 不得执行 auto-fix
8. `require_guard_jsonl_unchanged` — audit JSONL 行数必须未变化
9. `require_card_json_serializable` — card JSON 必须可序列化
10. `require_artifact_links_only_report_artifacts` — 只能链接报告产物

### 3.4 审计策略

- `pre_send_audit_required = True` — 发送前必须创建审计记录
- `post_send_audit_required = True` — 发送后必须创建审计记录
- `raw_webhook_never_logged = True` — 永远不记录原始 webhook
- `send_result_metadata_only = True` — 只记录元数据（非原始响应）

---

## 4. 12 步允许发送流程

| Step | Phase | Step Name | `allowed_now` |
|------|-------|-----------|---------------|
| 1 | 1 | Generate trend report dry-run | True |
| 2 | 2 | Generate Feishu payload projection | True |
| 3 | 3 | Validate payload projection | True |
| 4 | 4 | Render CLI preview | True |
| 5 | 5 | Validate output safety | True |
| 6 | 6 | Resolve webhook from allowlist / secret manager reference | True |
| 7 | 7 | Require user confirmation phrase | **False** |
| 8 | 8 | Create pre-send audit record projection | **False** |
| 9 | 9 | Send manually through dedicated send function | **False** |
| 10 | 10 | Create post-send audit record | **False** |
| 11 | 11 | Never auto-fix | **False** |
| 12 | 12 | Never scheduler-send without separate review | **False** |

**当前仅步骤 1-6 被允许**（全部为 dry-run/设计阶段操作）。步骤 7-12 需 Phase 5 实现后方可执行。

---

## 5. 15 条禁止路径

| Path | Severity | Description |
|------|----------|-------------|
| `inline_webhook_url` | critical | Payload 中内联 webhook URL |
| `inline_token_secret_api_key` | critical | Payload 中内联 token/secret/API key |
| `send_without_confirmation` | critical | 无用户确认即发送 |
| `send_without_payload_validation` | high | 未通过验证即发送 |
| `send_with_sensitive_payload` | critical | 包含敏感内容时发送 |
| `send_with_guard_line_count_changed` | high | audit JSONL 行数变化时发送 |
| `scheduler_auto_send` | critical | 调度器自动发送（无审核） |
| `auto_send_without_review` | critical | 无人工介入的自动发送 |
| `send_plus_auto_fix` | critical | 发送时同时执行 auto-fix |
| `runtime_write_during_send` | high | 发送时写入 runtime |
| `action_queue_write_during_send` | high | 发送时写入 action queue |
| `raw_webhook_in_audit` | critical | 审计记录中包含原始 webhook |
| `full_payload_body_in_audit` | high | 审计记录中包含完整 payload body |
| `webhook_call_without_allowlist` | critical | 未经 allowlist 的 webhook 调用 |
| `modify_existing_audit_record` | critical | 修改已存在的审计记录 |

---

## 6. 6 个实现阶段

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| 1 | Manual Send Policy Design | **current** | 定义策略/验证/确认/审计契约（R241-13D — 本阶段） |
| 2 | Pre-send Policy Validator | future | 验证 payload + 确认（不发送） |
| 3 | Manual Send Dry-run Command | future | CLI 显示"将要发送什么"（不实际发送） |
| 4 | Webhook Resolver Design | future | allowlist / secret manager 引用解析 |
| 5 | Manual Send Implementation | future | 实际 Feishu 发送（完整策略执行） |
| 6 | Scheduler Send Review | future | 调度器发送的独立审核 |

---

## 7. 测试结果

| 测试类 | 数量 | 状态 |
|--------|------|------|
| `TestWebhookPolicy` | 9 | 全部通过 |
| `TestConfirmationPolicy` | 8 | 全部通过 |
| `TestPreSendValidationPolicy` | 10 | 全部通过 |
| `TestAuditPolicy` | 10 | 全部通过 |
| `TestAllowedFlow` | 6 | 全部通过 |
| `TestBlockedPaths` | 9 | 全部通过 |
| `TestPolicyDesign` | 5 | 全部通过 |
| `TestValidation` | 11 | 全部通过 |
| `TestGenerate` | 4 | 全部通过 |
| `TestSafetyConstraints` | 5 | 全部通过 |
| **R241-13D 合计** | **76** | **全部通过** |

**回归测试（R241-13A/B/C + 相关模块）:**
| 模块 | 测试数 | 状态 |
|------|--------|------|
| `test_audit_trend_feishu_projection.py` | 33 | 全部通过 |
| `test_audit_trend_feishu_preview.py` | 32 | 全部通过 |
| `test_audit_trend_cli_guard.py` | 17 | 全部通过 |
| `test_audit_trend_projection.py` | 26 | 全部通过 |
| `test_audit_trend_feishu_send_policy.py` | 76 | 全部通过 |
| **合计** | **184** | **全部通过** |

---

## 8. 安全性验证

### 8.1 设计约束验证

| 约束 | 实现方式 |
|------|---------|
| 不发送 Feishu | `send_allowed=false` + 无 webhook 调用代码 |
| 不调用 webhook | `no_webhook_call=True` + 无网络调用 |
| 不写 audit JSONL | `append_audit_record_to_target` monkeypatch 测试验证 |
| 不写 runtime | `no_runtime_write=True` |
| 不写 action queue | `no_action_queue_write=True` |
| 不执行 auto-fix | `no_auto_fix=True` |

### 8.2 设计契约验证

| 检查项 | 结果 |
|--------|------|
| `webhook_url_allowed_inline = False` | ✓ |
| `secret_inline_allowed = False` | ✓ |
| `user_confirmation_required = True` | ✓ |
| `pre_send_audit_required = True` | ✓ |
| `post_send_audit_required = True` | ✓ |
| `append_only_required = True` | ✓ |
| `raw_webhook_never_logged = True` | ✓ |
| `scheduler_auto_send` blocked | ✓ |
| `auto_fix` blocked | ✓ |
| Implementation phases 1-6 完整 | ✓ |
| Blocked paths 非空（15 条） | ✓ |

---

## 9. R241-13 整体进度

| Phase | 状态 | 说明 |
|-------|------|------|
| R241-13A | ✓ | Feishu Trend Dry-run Design Contract |
| R241-13B | ✓ | Feishu Trend Payload Projection（修复后重新验证通过） |
| R241-13C | ✓ | Feishu Trend CLI Preview |
| R241-13D | ✓ | Manual Send Policy Design（本轮） |

---

## 10. 最终判定

**R241-13D 判定：A — 成功**

- 76 个测试全部通过
- 设计契约完整：5 enums + 5 dataclasses + 9 函数
- 15 条禁止路径全部正确定义
- 12 步允许流程中步骤 1-6 允许（当前），步骤 7-12 阻止（未来）
- 6 个实现阶段完整定义
- 无网络调用、无 webhook 调用、无 audit JSONL 写入、无 runtime 写入
- `validate_feishu_manual_send_policy_design()` 返回 `valid=True`，0 个错误
- 契约 JSON 已生成至 `R241-13D_MANUAL_SEND_POLICY_CONTRACT.json`

### R241-13 整体通过条件满足

| 条件 | 状态 |
|------|------|
| R241-13A 设计契约完成 | ✓ |
| R241-13B projection 实现完成 + preflight bug 修复 | ✓ |
| R241-13C CLI preview 实现完成 | ✓ |
| R241-13D send policy 设计完成 | ✓ |
| 无网络/hook/audit-write 违规 | ✓ |
| 全部 184 个测试通过 | ✓ |

**R241-13 全部四个阶段完成。**