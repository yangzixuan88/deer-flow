# R241-11A Append-only Audit Trail Design Report

**Generated:** 2026-04-25
**Phase:** R241-11A — Append-only Audit Trail Contract Design
**Status:** A — 成功，可进入 R241-11B Dry-run Audit Record Projection 实现

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/audit/__init__.py` | 新增 | 模块导出接口 |
| `backend/app/audit/audit_trail_contract.py` | 新增 | Phase 1 合同定义：schema/redaction/projection |
| `backend/app/audit/test_audit_trail_contract.py` | 新增 | 29 个测试覆盖所有合同函数 |
| `migration_reports/foundation_audit/R241-11A_APPEND_ONLY_AUDIT_TRAIL_CONTRACT.json` | 新增 | `generate_append_only_audit_trail_design()` 生成 |
| `migration_reports/foundation_audit/R241-11A_APPEND_ONLY_AUDIT_TRAIL_DESIGN.md` | 新增 | 本报告 |

---

## 2. AuditTrailRecord 字段

| 字段 | 类型 | required | 说明 |
|------|------|----------|------|
| `audit_record_id` | str | ✅ | 唯一记录 ID |
| `event_type` | str | ✅ | AuditEventType 枚举值 |
| `write_mode` | str | ✅ | AuditWriteMode 枚举值（R241-11A 为 design_only） |
| `source_system` | str | ✅ | 来源系统（如 foundation_diagnostics_cli） |
| `source_command` | str | ❌ | CLI 子命令名 |
| `status` | str | ✅ | 诊断状态（ok/partial_warning/failed/projection_only） |
| `root` | str | ✅ | 被诊断的 ROOT 路径 |
| `generated_at` | str | ✅ | ISO8601 时间戳 |
| `observed_at` | str | ✅ | 记录被观察的时间 |
| `context_id` | str | ❌ | 上下文 ID（用于关联） |
| `request_id` | str | ❌ | 请求 ID |
| `mode_session_id` | str | ❌ | Mode 会话 ID |
| `mode_invocation_id` | str | ❌ | Mode 调用 ID |
| `tool_execution_id` | str | ❌ | 工具执行 ID |
| `review_id` | str | ❌ | Nightly review ID |
| `payload_ref` | str | ❌ | payload 引用路径 |
| `payload_hash` | str | ✅ | payload SHA256 前32位 |
| `summary` | dict | ✅ | 诊断 summary |
| `warnings` | list | ✅ | 警告列表 |
| `errors` | list | ✅ | 错误列表 |
| `sensitivity_level` | str | ✅ | AuditSensitivityLevel 枚举值 |
| `retention_class` | str | ✅ | AuditRetentionClass 枚举值 |
| `redaction_applied` | bool | ✅ | 是否应用了脱敏 |
| `redaction_warnings` | list | ❌ | 脱敏警告列表 |
| `append_only_target` | str | ❌ | 建议追加目标（R241-11A 不写入） |
| `schema_version` | str | ✅ | 固定 1.0 |

---

## 3. AuditTrailTargetSpec 字段

| 字段 | 类型 | required | 说明 |
|------|------|----------|------|
| `target_id` | str | ✅ | 目标唯一 ID |
| `target_path` | str | ✅ | JSONL 文件路径 |
| `format` | str | ✅ | 固定 jsonl |
| `append_only` | bool | ✅ | 固定 True |
| `allow_overwrite` | bool | ✅ | 固定 False |
| `rotation_policy` | str | ✅ | daily/weekly |
| `max_file_size_mb` | int | ✅ | 最大文件大小 |
| `retention_class` | str | ✅ | AuditRetentionClass |
| `requires_root_guard` | bool | ✅ | 固定 True |
| `backup_required` | bool | ✅ | 固定 False |
| `corruption_recovery_strategy` | str | ✅ | 恢复策略 |
| `warnings` | list | ❌ | 设计警告 |

### 默认 5 个 Target

| target_id | 用途 | retention_class |
|-----------|------|-----------------|
| `foundation_diagnostic_runs` | 所有 CLI 诊断运行 | medium_term_operational |
| `nightly_health_reviews` | Nightly health review | long_term_governance |
| `feishu_summary_dryruns` | Feishu dry-run projection | short_term_debug |
| `tool_runtime_projections` | Tool runtime projection | medium_term_operational |
| `mode_callgraph_projections` | Mode callgraph projection | medium_term_operational |

---

## 4. AuditRedactionPolicy 字段

| 字段 | 类型 | required | 说明 |
|------|------|----------|------|
| `policy_id` | str | ✅ | 固定 default |
| `redact_webhook_urls` | bool | ✅ | 固定 True |
| `redact_api_keys` | bool | ✅ | 固定 True |
| `redact_tokens` | bool | ✅ | 固定 True |
| `redact_file_contents` | bool | ✅ | 固定 True |
| `redact_prompt_body` | bool | ✅ | 固定 True |
| `redact_memory_body` | bool | ✅ | 固定 True |
| `redact_rtcm_artifact_body` | bool | ✅ | 固定 True |
| `allow_path_metadata` | bool | ✅ | 固定 True（保留路径但脱敏内容） |
| `allow_hashes` | bool | ✅ | 固定 True |
| `allow_counts` | bool | ✅ | 固定 True |
| `allow_first_line_preview` | bool | ✅ | 固定 True |
| `warnings` | list | ❌ | 设计警告 |

---

## 5. AuditQuerySpec 字段

| query_id | 维度 | 说明 |
|----------|------|------|
| `by_command` | command | 按 CLI 子命令过滤 |
| `by_status` | status | 按诊断状态过滤 |
| `by_date_range` | date | 按时间范围过滤 |
| `by_warning_type` | warning_type | 按警告类型过滤 |
| `by_error_type` | error_type | 按错误类型过滤 |
| `by_context_id` | context_id | 按上下文 ID 过滤 |
| `by_request_id` | request_id | 按请求 ID 过滤 |
| `by_severity` | severity | 按严重程度过滤 |
| `by_domain` | domain | 按领域过滤 |

> 注意：查询规格为只读设计定义，不实现真实查询索引。

---

## 6. Sensitivity Classification 规则

| 检测模式 | 示例 key | 判定等级 |
|----------|----------|----------|
| key 名含 webhook_url/endpoint | `webhook_url`, `webhook_endpoint` | secret_or_token |
| key 名含 api_key/secret/token/password/credential | `api_key`, `secret`, `token` | secret_or_token |
| key 名含 bearer/auth | `bearer_token`, `auth_header` | secret_or_token |
| value 匹配 webhook URL 模式 | `https://...webhook...` | secret_or_token |
| value 匹配 bearer/token 模式 | `sk-abcdef...` (20+ chars) | secret_or_token |
| key 名含 body/content | `prompt_body`, `memory_body` | user_private_content |
| key 名含 path metadata | `source_path`, `file_path` | sensitive_path_metadata |
| key 后缀含 _hash/_count/_total | `payload_hash`, `total_count` | internal_metadata |

---

## 7. Redaction Policy 规则

| 操作 | 规则 |
|------|------|
| webhook URL / token / secret value | → `[REDACTED]` |
| prompt/memory/rtcm body key | → `[CONTENT_REDACTED]` |
| 绝对路径 key | 保留（allow_path_metadata=True） |
| _hash/_count/_total 字段 | 保留 |
| 其他字段 | 原样保留 |

`redact_audit_payload()` 返回脱敏副本，不修改原输入。

---

## 8. Audit Record Projection 规则

`create_audit_record_from_diagnostic_result(result, event_type)`:

1. **提取字段**：`command`, `status`, `root`, `generated_at`, `summary`, `warnings`, `errors`
2. **计算 payload_hash**：SHA256(JSON, sorted) 前32位
3. **敏感度分类**：调用 `classify_audit_sensitivity(payload)`
4. **脱敏**：调用 `redact_audit_payload(payload)`
5. **写入模式**：固定 `design_only`
6. **append_only_target**：仅建议路径，不实际写入

---

## 9. Append-only Target Specs

**默认目标目录：** `migration_reports/foundation_audit/audit_trail/`

| 文件 | 说明 |
|------|------|
| `foundation_diagnostic_runs.jsonl` | 所有 CLI 诊断运行记录 |
| `nightly_health_reviews.jsonl` | Nightly health review 记录 |
| `feishu_summary_dryruns.jsonl` | Feishu dry-run projection 记录 |
| `tool_runtime_projections.jsonl` | Tool runtime projection 记录 |
| `mode_callgraph_projections.jsonl` | Mode callgraph projection 记录 |

**约束：**
- `append_only=True`, `allow_overwrite=False`
- JSONL 一行一条记录
- 每条记录必须包含 `schema_version`
- 每条记录必须包含 `payload_hash`

---

## 10. Implementation Phases

| Phase | 名称 | 说明 |
|-------|------|------|
| 1 | Design-only Contract | 当前 R241-11A，仅定义 schema / design / validation |
| 2 | Dry-run Audit Record Projection | 从 CLI result 生成 AuditTrailRecord，但不写文件 |
| 3 | Append-only JSONL Writer | 写 audit_trail/*.jsonl，不覆盖，不写其他路径 |
| 4 | Audit Query Helper | 读 JSONL，按 command/status/date 查询，不做全文搜索 |
| 5 | Nightly Trend Report | 汇总历史 audit records 到 nightly/daily/weekly 趋势摘要 |
| 6 | Feishu Audit Summary Dry-run | 生成 Feishu audit summary projection，不推送 |

---

## 11. 测试结果

**29 tests PASSED** in 0.18s

### 测试覆盖

| 测试组 | 覆盖内容 |
|--------|---------|
| Sensitivity Classification | webhook URL, api_key/secret/token, private body, public metadata, internal metadata |
| Redaction Policy | 返回 dict，默认策略 |
| Redaction | 不修改原输入，脱敏 webhook/token/secret，脱敏 body，保留路径 metadata |
| Audit Record Projection | 生成 payload_hash, write_mode=design_only, 脱敏敏感字段 |
| Validation | 拒绝 raw secret/token, 拒绝完整 private body, 接受有效记录 |
| Target Specs | 不创建文件，5个 targets，append_only=True/allow_overwrite=False |
| Query Specs | command/status/date/context_id/request_id 维度 |
| Design Aggregation | 6 phases, blocked_paths, integration_points |
| Generator | 只写 tmp_path, JSON 结构正确 |
| Safety | 不写真实 JSONL, 不修改 runtime, 不调用网络, CLI 未修改 |

---

## 12. 是否写真实 audit log / JSONL

| 检查项 | 结果 |
|--------|------|
| 写真实 audit_trail JSONL | ❌ 无 — `build_audit_target_specs()` 仅生成 spec，不创建文件 |
| 写 runtime | ❌ 无 — 所有函数为只读设计定义 |
| 创建 audit_trail 目录 | ❌ 无 — `generate_append_only_audit_trail_design()` 仅写 JSON report |

---

## 13. 是否修改 CLI / Gateway / runtime

| 检查项 | 结果 |
|--------|------|
| 修改 `read_only_diagnostics_cli.py` | ❌ 无 — 仅被引用，未修改 |
| 修改 `scripts/foundation_diagnose.py` | ❌ 无 |
| 修改 Gateway | ❌ 无 |
| 写 runtime (memory.json / Qdrant / SQLite) | ❌ 无 |
| 写 action queue | ❌ 无 |
| 开放 HTTP API endpoint | ❌ 无 |

---

## 14. 当前剩余断点

无剩余断点。Phase 1 设计合同完整覆盖：

- ✅ AuditTrailRecord schema（25字段）
- ✅ AuditTrailTargetSpec（5个 targets）
- ✅ AuditRedactionPolicy
- ✅ AuditQuerySpec（9个查询维度）
- ✅ AppendOnlyAuditTrailDesign
- ✅ 分类/脱敏/projection/验证函数
- ✅ 29 tests PASSED
- ✅ 未写真实 JSONL / 未改 CLI / 未调用网络

---

## 15. 下一轮建议 (R241-11B)

**Dry-run Audit Record Projection 实现：**

将 `create_audit_record_from_diagnostic_result()` 集成到 `read_only_diagnostics_cli.py` 的 `run_all_diagnostics()`，在 `write_report=False` 时也生成 audit record（通过返回值传递），但不写文件。

实现要点：
1. `run_all_diagnostics()` 返回值中增加 `audit_record` 字段
2. 每次 CLI 运行生成一个 `diagnostic_cli_run` 类型的 audit record
3. `run_feishu_summary_diagnostic()` 生成 `feishu_summary_dry_run` 类型
4. Phase 2 仍不写文件，仅通过返回值传递 audit record

R241-11B 验收条件：
- `run_all_diagnostics()` 返回值包含 `audit_record`
- `audit_record` 的 `write_mode` 仍为 `design_only`
- `audit_record` 的 `payload_hash` 正确计算
- 不创建任何 JSONL 文件
- 29 tests 继续 PASS

---

## 判定

**A — R241-11A 成功，可进入 R241-11B Dry-run Audit Record Projection 实现**

- ✅ 新增 `audit_trail_contract.py` 和测试文件
- ✅ 29 tests PASSED
- ✅ AuditTrailRecord schema 完整（25字段）
- ✅ AuditTrailTargetSpec 完整（5个 targets）
- ✅ AuditRedactionPolicy 完整
- ✅ AuditQuerySpec 完整（9个查询维度）
- ✅ 明确 Phase 1-6 implementation path
- ✅ 能从 diagnostic result 生成 design-only audit record projection
- ✅ 未写真实 audit JSONL
- ✅ 未创建 audit_trail runtime 目录
- ✅ 未修改 CLI/Gateway/runtime
- ✅ 未调用 webhook/网络
- ✅ 未输出 raw secret/token/full prompt/memory/RTCM body
