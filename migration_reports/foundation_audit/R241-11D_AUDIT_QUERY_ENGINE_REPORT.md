# R241-11D Append-only Audit Trail Read Path Query Engine Report

**Generated:** 2026-04-25
**Phase:** R241-11D — Append-only Audit Trail Read Path Query Engine
**Status:** A — 成功，Phase D 完成

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/audit/audit_trail_query.py` | 新增 | R241-11D 核心实现 — 只读查询引擎 |
| `backend/app/audit/__init__.py` | 修改 | 导出 query 模块所有公开符号 |
| `backend/app/foundation/read_only_diagnostics_cli.py` | 修改 | `audit-scan` + `audit-query` 子命令 |
| `backend/app/audit/test_audit_trail_query.py` | 新增 | 52 个测试覆盖所有 query 函数 |
| `backend/app/foundation/test_read_only_diagnostics_cli.py` | 修改 | 5 个 Phase D CLI 测试 |

---

## 2. 核心数据结构

### 2.1 AuditQueryStatus 枚举

```python
class AuditQueryStatus(str, Enum):
    OK = "ok"                               # 成功，无警告
    PARTIAL_WARNING = "partial_warning"     # 成功，但有部分记录无效
    NO_RECORDS = "no_records"               # 无匹配记录
    INVALID_QUERY = "invalid_query"         # 查询参数无效
    FAILED = "failed"                       # 查询执行失败
```

### 2.2 AuditQueryOutputFormat 枚举

```python
class AuditQueryOutputFormat(str, Enum):
    JSON = "json"       # 缩进 JSON
    JSONL = "jsonl"     # 每行一条 JSON 记录
    CSV = "csv"         # CSV 格式
    TEXT = "text"       # 纯文本表格
    MARKDOWN = "markdown"  # Markdown 表格
```

### 2.3 AuditRecordSource 枚举

```python
class AuditRecordSource(str, Enum):
    FOUNDATION_DIAGNOSTIC_RUNS = "foundation_diagnostic_runs"
    NIGHTLY_HEALTH_REVIEWS = "nightly_health_reviews"
    FEISHU_SUMMARY_DRYRUNS = "feishu_summary_dryruns"
    TOOL_RUNTIME_PROJECTIONS = "tool_runtime_projections"
    MODE_CALLGRAPH_PROJECTIONS = "mode_callgraph_projections"
```

### 2.4 AuditTrailFileSummary 数据类

```python
@dataclass
class AuditTrailFileSummary:
    target_id: str
    file_path: str
    exists: bool
    line_count: int = 0
    scanned_count: int = 0
    valid_count: int = 0
    invalid_line_count: int = 0
    file_size_bytes: int = 0
    first_record_id: Optional[str] = None
    last_record_id: Optional[str] = None
    first_generated_at: Optional[str] = None
    last_generated_at: Optional[str] = None
```

### 2.5 AuditQueryFilter 数据类

```python
@dataclass
class AuditQueryFilter:
    event_types: Optional[List[str]] = None
    source_commands: Optional[List[str]] = None
    statuses: Optional[List[str]] = None
    write_modes: Optional[List[str]] = None
    sensitivity_levels: Optional[List[str]] = None
    payload_hashes: Optional[List[str]] = None
    audit_record_ids: Optional[List[str]] = None
    start_time: Optional[str] = None  # ISO8601
    end_time: Optional[str] = None    # ISO8601
    target_ids: Optional[List[str]] = None
    order_by: str = "observed_at"
    order_dir: str = "desc"
    limit: int = 100
    offset: int = 0
```

### 2.6 AuditQueryResult 数据类

```python
@dataclass
class AuditQueryResult:
    query_id: str
    status: AuditQueryStatus
    filters_applied: Dict[str, Any]
    output_format: str
    total_matched: int
    records_returned: int
    scanned_count: int
    records: List[Dict[str, Any]]
    file_summaries: List[AuditTrailFileSummary]
    missing_files: List[str]
    discovered_files: List[str]
    warnings: List[str]
    errors: List[str]
    query_duration_ms: float
```

---

## 3. 查询路径函数

| 函数 | 说明 |
|------|------|
| `discover_audit_trail_files(root)` | 发现所有 `migration_reports/foundation_audit/audit_trail/*.jsonl` 文件 |
| `scan_append_only_audit_trail(root)` | 扫描所有 JSONL 文件，返回 `AuditTrailFileSummary` 列表 |
| `load_audit_jsonl_records(file_path, filters)` | 加载单个 JSONL 文件，应用过滤器 |
| `build_audit_query_filter(...)` | 从参数构建 `AuditQueryFilter`，带自动修正和警告 |
| `record_matches_audit_filter(record, filters)` | 判断单条记录是否匹配过滤器 |
| `query_audit_trail(root, filters, output_format)` | 主查询入口，返回 `Dict[str, Any]` |
| `summarize_audit_query_result(result)` | 生成统计摘要（按 event_type、status 等分组计数） |
| `format_audit_query_result(result, format)` | 格式化输出为 JSON/JSONL/CSV/TEXT/MARKDOWN |

---

## 4. 安全约束

### 4.1 绝对禁止

- **无任何 JSONL 写入操作** — 所有函数均为只读
- **无网络调用** — 无 webhooks、无 API 请求
- **无运行时修改** — 不调用 append writer
- **无 `sensitivity_level: end_user_pii` 原始数据暴露** — 输出时 `redact_audit_payload` 遮蔽敏感字段

### 4.2 路径约束

- 审计轨迹根路径：`migration_reports/foundation_audit/audit_trail/`
- JSONL 文件结构：`{target_id}.jsonl`
- 绝对禁止访问 `migration_reports/` 目录以外的路径

---

## 5. CLI 命令

### 5.1 audit-scan

```bash
python scripts/foundation_diagnose.py audit-scan [--format json|jsonl|csv|text|markdown]
```

发现并扫描所有审计轨迹 JSONL 文件，返回文件摘要统计。

### 5.2 audit-query

```bash
python scripts/foundation_diagnose.py audit-query \
    [--event-type TYPE] \
    [--source-command CMD] \
    [--status STATUS] \
    [--write-mode MODE] \
    [--sensitivity-level LEVEL] \
    [--payload-hash HASH] \
    [--audit-record-id ID] \
    [--start-time ISO8601] \
    [--end-time ISO8601] \
    [--target-id ID] \
    [--order FIELD:dir] \
    [--limit N] \
    [--format json|jsonl|csv|text|markdown]
```

查询审计轨迹记录，支持所有过滤器组合。

---

## 6. 测试覆盖

| 测试模块 | 数量 | 状态 |
|----------|------|------|
| `test_audit_trail_query.py` | 52 | 全部通过 |
| `test_read_only_diagnostics_cli.py` (Phase D) | 5 | 全部通过 |

**CLI Smoke 测试：**

| 测试 | 命令 | 状态 |
|------|------|------|
| smoke-1 | `audit-scan --format json` | PASS |
| smoke-2 | `audit-scan --format markdown` | PASS |
| smoke-3 | `audit-query --status partial_warning --limit 5` | PASS |
| smoke-4 | `audit-query --status partial_warning --limit 5 --format json` | PASS |
| smoke-5 | `audit-query --status partial_warning --limit 20 --format csv` | PASS |

---

## 7. append-only 不变性验证

- 所有 JSONL 文件（`foundation_diagnostic_runs.jsonl`、`nightly_health_reviews.jsonl`、`feishu_summary_dryruns.jsonl`）行数在所有 smoke 测试前后保持不变
- `test_audit_query_does_not_trigger_append` 验证 `append_all_diagnostic_audit_records` 在 `audit-query` 执行期间从未被调用
- `test_audit_scan_does_not_write_files` 验证文件写入前后行数完全一致

---

## 8. 输出格式示例

### 8.1 JSON 格式（默认）

```json
{
  "query_id": "audit_query_...,
  "status": "ok",
  "filters_applied": {"status": ["partial_warning"]},
  "output_format": "json",
  "total_matched": 18,
  "records_returned": 18,
  "scanned_count": 18,
  "records": [...],
  "file_summaries": [...],
  "missing_files": [],
  "discovered_files": [...],
  "warnings": [],
  "errors": [],
  "query_duration_ms": 12.34
}
```

### 8.2 CSV 格式

```csv
audit_record_id,event_type,write_mode,source_command,status,sensitivity_level,payload_hash,generated_at,observed_at,appended_at,schema_version
audit_...,diagnostic_cli_run,design_only,all,partial_warning,public_metadata,sha256...,2026-04-25T...,2026-04-25T...,,1.0
```

---

## 9. 已知限制

- `mode_callgraph_projections.jsonl` 和 `tool_runtime_projections.jsonl` 在 fixture 测试环境中存在格式错误行，不影响正常文件查询
- CSV 输出使用标准库 `csv.DictWriter`，不支持嵌套字段展开
- 查询超时未实现 — 大文件场景下建议使用 `--limit` 参数
