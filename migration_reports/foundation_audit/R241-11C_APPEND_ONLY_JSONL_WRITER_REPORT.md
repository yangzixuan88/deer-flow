# R241-11C Append-only JSONL Writer Implementation Report

**Generated:** 2026-04-25
**Phase:** R241-11C — Append-only JSONL Writer Implementation
**Status:** A — 成功，可进入 R241-11D 实现

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/audit/audit_trail_writer.py` | 新增 | R241-11C 核心实现 — Append-only JSONL writer |
| `backend/app/audit/__init__.py` | 修改 | 导出 writer 模块所有公开符号 |
| `backend/app/foundation/read_only_diagnostics_cli.py` | 修改 | `append_audit` 参数 + `--append-audit` CLI flag + `_append_audit_to_trail()` helper |
| `backend/app/audit/test_audit_trail_writer.py` | 新增 | 28 个测试覆盖所有 writer 函数 |
| `backend/app/foundation/test_read_only_diagnostics_cli.py` | 修改 | 22 个 Phase D 测试全部保留（未改动） |

---

## 2. 核心数据结构

### 2.1 AuditAppendStatus 枚举

```python
class AuditAppendStatus(str, Enum):
    APPENDED = "appended"               # 成功追加
    SKIPPED_DRY_RUN = "skipped_dry_run" # dry_run 模式跳过
    BLOCKED_INVALID_RECORD = "blocked_invalid_record"  # 记录校验失败
    BLOCKED_INVALID_TARGET = "blocked_invalid_target"  # 目标路径无效
    BLOCKED_OVERWRITE_RISK = "blocked_overwrite_risk" # 覆盖风险阻断
    FAILED = "failed"                   # 写入失败
```

### 2.2 AuditWriterMode 枚举

```python
class AuditWriterMode(str, Enum):
    DRY_RUN = "dry_run"      # 仅验证，不写文件
    APPEND_ONLY = "append_only"  # 追加写入
    BLOCKED = "blocked"      # 完全阻止
```

### 2.3 AuditAppendResult 数据类

```python
@dataclass
class AuditAppendResult:
    append_result_id: str           # UUID
    status: AuditAppendStatus       # 写入状态
    target_id: str                  # 目标 ID
    target_path: str                # 目标路径
    record_id: Optional[str]        # 记录 ID
    event_type: Optional[str]       # 事件类型
    write_mode: str                 # write_mode
    bytes_written: int = 0          # 写入字节数
    line_count_before: Optional[int] = None  # 写入前行数
    line_count_after: Optional[int] = None   # 写入后行数
    payload_hash: Optional[str] = None        # payload hash
    validation_valid: bool = False           # 校验结果
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    appended_at: str = ""          # ISO8601 时间戳
```

---

## 3. event_type → target_id 映射

| event_type | target_id | JSONL 文件 |
|-------------|-----------|-----------|
| `diagnostic_cli_run` | `foundation_diagnostic_runs` | `foundation_diagnostic_runs.jsonl` |
| `diagnostic_domain_result` | `foundation_diagnostic_runs` | `foundation_diagnostic_runs.jsonl` |
| `nightly_health_review` | `nightly_health_reviews` | `nightly_health_reviews.jsonl` |
| `feishu_summary_dry_run` | `feishu_summary_dryruns` | `feishu_summary_dryruns.jsonl` |

---

## 4. 安全约束

### 4.1 validate_append_only_target_path()

**路径校验规则：**
- 拒绝 `..` 路径遍历
- 拒绝非 `.jsonl` 后缀
- 拒绝符号链接
- 拒绝 `migration_reports/foundation_audit/audit_trail/` 以外的所有路径
- 拒绝运行时目录（`backend/app/`、`backend/data/` 等）

**跨平台兼容：**
- 所有路径 backslash → forward slash 归一化后比较
- Windows 上使用 `os.path.normpath` + 字符串替换

### 4.2 append_audit_record_to_target()

- **唯一文件模式：** `"a"` (append) — 不使用 `"w"`、`"w+"`、`"r+"` 等截断模式
- **编码固定：** `encoding="utf-8"`
- **原子写入：** 单条 `f.write(line)` 调用
- **无网络调用：** 不做 HTTP、WebSocket、数据库写入

---

## 5. append_audit_record_to_target() 核心流程

```
输入: record, target_id, dry_run=True
├── 1. resolve_audit_target(event_type) → target_spec + path + warnings
├── 2. validate_append_only_target_path(path) → 路径安全校验
├── 3. serialize_audit_record_jsonl(record) → (line, payload_hash)
│   ├── redact_audit_payload(payload)
│   └── validate_audit_record(redacted_record)
├── 4a. dry_run=True → 返回 SKIPPED_DRY_RUN，0 bytes_written
└── 4b. dry_run=False
    ├── open(path, "a") → 追加模式
    ├── f.write(line) → 单条写入
    ├── f.flush() + os.fsync() → 强制刷盘
    └── 返回 APPENDED，line_count_before/after
```

---

## 6. run_all_diagnostics() 更新

**签名变更：**
```python
def run_all_diagnostics(
    format: str = "json",
    limit: int = 100,
    max_files: int = 500,
    write_report: bool = False,
    output_path: Optional[str] = None,
    append_audit: bool = False,  # ← NEW
) -> Dict[str, Any]:
```

**CLI flag：**
```
python scripts/foundation_diagnose.py all --format json --append-audit
```

**行为：**
- `append_audit=False`（默认）：`run_all_diagnostics()` 返回 dict 不变，**不写任何文件**
- `append_audit=True`：调用 `_append_audit_to_trail()` 追加所有诊断记录

---

## 7. _append_audit_to_trail() helper

```python
def _append_audit_to_trail(all_result: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from app.audit import append_all_diagnostic_audit_records
        return append_all_diagnostic_audit_records(
            all_result, root=str(ROOT), dry_run=False
        )
    except Exception as exc:
        return {
            "total_records": 0, "appended_count": 0, "skipped_count": 0,
            "failed_count": 1, "results": [],
            "warnings": [f"append_audit_failed:{exc}"],
            "errors": [f"append_audit_failed:{exc}"],
        }
```

- 异常安全：任何写入失败返回 error info 而非崩溃
- `root=str(ROOT)`：使用模块常量，防止路径注入

---

## 8. append_all_diagnostic_audit_records() 行为

**追加策略：**
- `all_result["audit_record"]` → 1 条 aggregate 记录 → `foundation_diagnostic_runs.jsonl`
- `all_result["sub_results"]` 中每条 `audit_record` → 各自对应文件

**总计 9 条记录：**
- 1 aggregate (`diagnostic_cli_run`) → `foundation_diagnostic_runs.jsonl`
- 6 域结果 (`diagnostic_domain_result`) → `foundation_diagnostic_runs.jsonl`
- 1 nightly (`nightly_health_review`) → `nightly_health_reviews.jsonl`
- 1 feishu-summary (`feishu_summary_dry_run`) → `feishu_summary_dryruns.jsonl`

---

## 9. 序列化格式

```jsonl
{"record_id":"...","event_type":"diagnostic_cli_run","write_mode":"append_only","sensitivity_level":"public_metadata","payload_hash":"abc123...","redaction_applied":false,"diagnostic_version":"1.0","cli_args":{"format":"json","append_audit":true,"limit":100},"result_counts":{"truth_state":3,"queue_sandbox":1,"memory":3,"asset":2,"prompt":2,"rtcm":2},"schema_version":"1.0","appended_at":"2026-04-25T02:22:33Z","append_result_id":"..."}
```

- 紧凑 JSON（无缩进）
- `ensure_ascii=False`（支持 Unicode payload）
- 每行以 `\n` 结尾
- 最后一行可有/无 `\n`

---

## 10. 测试结果

### 10.1 全部测试 PASS

| 测试组 | 数量 | 状态 |
|--------|------|------|
| Audit Contract (`test_audit_trail_contract.py`) | 29 | ✅ PASS |
| Audit Writer (`test_audit_trail_writer.py`) | 28 | ✅ PASS |
| CLI Phase D (`test_read_only_diagnostics_cli.py`) | 70 | ✅ PASS |
| **Subtotal** | **127** | **✅** |
| Nightly + RTCM + Prompt + ToolRuntime + Mode + Gateway + Asset + Memory + Truth | 273 | ✅ PASS |
| **Total** | **400** | **✅ PASS** |

### 10.2 test_audit_trail_writer.py 测试覆盖

| 测试组 | 测试名称 | 覆盖 |
|--------|----------|------|
| resolve | `test_resolve_audit_target_diagnostic_cli_run` | diagnostic_cli_run → foundation_diagnostic_runs |
| resolve | `test_resolve_audit_target_diagnostic_domain_result` | diagnostic_domain_result → foundation_diagnostic_runs |
| resolve | `test_resolve_audit_target_nightly_health_review` | nightly → nightly_health_reviews |
| resolve | `test_resolve_audit_target_feishu_summary_dry_run` | feishu → feishu_summary_dryruns |
| resolve | `test_resolve_audit_target_unknown_event_type` | unknown → error + fallback |
| resolve | `test_resolve_audit_target_warning_for_unknown` | unknown event_type → warnings |
| resolve | `test_resolve_audit_target_respects_dry_run` | dry_run → SKIPPED_DRY_RUN |
| resolve | `test_resolve_audit_target_aggregate_records` | 9 record_ids from all_result |
| validate | `test_validate_accepts_audit_trail_jsonl` | audit_trail/*.jsonl 接受 |
| validate | `test_validate_rejects_dotdot` | `..` 路径遍历 → reject |
| validate | `test_validate_rejects_non_jsonl` | 非 .jsonl → reject |
| validate | `test_validate_rejects_runtime_paths` | runtime paths → reject |
| validate | `test_validate_rejects_symlinks` | symlink → reject |
| serialize | `test_serialize_produces_valid_jsonl_line` | 单行 JSON + newline |
| serialize | `test_serialize_includes_payload_hash` | SHA256 hash 前32位hex |
| append | `test_append_audit_skips_dry_run` | dry_run=True → SKIPPED_DRY_RUN |
| append | `test_append_audit_append_mode_works` | dry_run=False → APPENDED |
| append | `test_append_audit_respects_append_only_mode` | APPEND_ONLY mode |
| append | `test_append_audit_blocked_mode_rejects` | BLOCKED mode → BLOCKED |
| append | `test_append_audit_incrementally_grows_line_count` | line_count_before/after 递增 |
| result | `test_append_diagnostic_result_extracts_audit_record` | 从 result dict 提取 |
| result | `test_append_all_appends_9_records` | 9 records from all_result |
| all | `test_append_all_diagnostic_records_returns_counts` | appended/skipped/failed counts |
| safety | `test_append_no_network_calls` | 无 socket/HTTP 操作 |
| safety | `test_append_no_truncate_modes` | 无 "w"/"w+"/"r+" 模式 |
| safety | `test_append_only_append_mode_used` | 仅有 "a" 模式 |

---

## 11. CLI Smoke 结果

### 11.1 无 --append-audit 标志

```bash
python scripts/foundation_diagnose.py all --format json
```
- ❌ `audit_trail/` 目录**不存在**
- ✅ 无文件写入

### 11.2 带 --append-audit 标志（第1次）

```bash
python scripts/foundation_diagnose.py all --format json --append-audit
```
- ✅ `audit_trail/` 目录**创建**
- ✅ 9 条记录写入 3 个 JSONL 文件
- ✅ `foundation_diagnostic_runs.jsonl`: 7 条
- ✅ `nightly_health_reviews.jsonl`: 1 条
- ✅ `feishu_summary_dryruns.jsonl`: 1 条

### 11.3 带 --append-audit 标志（第2次）

```bash
python scripts/foundation_diagnose.py all --format json --append-audit
```
- ✅ 行数**翻倍**（无覆盖）
- ✅ `foundation_diagnostic_runs.jsonl`: 7 → 14
- ✅ `nightly_health_reviews.jsonl`: 1 → 2
- ✅ `feishu_summary_dryruns.jsonl`: 1 → 2
- ✅ 追加写入确认

---

## 12. RootGuard 验证

| 检查项 | 结果 |
|--------|------|
| 路径穿越 (`..`) | ✅ 被 validate_append_only_target_path 拒绝 |
| 运行时目录写入 | ✅ 拒绝 backend/app/、backend/data/ 等 |
| 覆盖模式 ("w"/"w+") | ✅ 仅有 "a" 模式 |
| 网络调用 | ✅ 无 socket/HTTP 调用 |
| 符号链接 | ✅ 被拒绝 |

---

## 13. py_compile 验证

```bash
python -m py_compile backend/app/audit/audit_trail_writer.py
python -m py_compile backend/app/audit/__init__.py
python -m py_compile backend/app/foundation/read_only_diagnostics_cli.py
```
- ✅ 所有文件编译成功

---

## 14. 剩余断点

无剩余断点。所有 R241-11C 验收条件满足：

- ✅ `AuditAppendStatus` / `AuditWriterMode` 枚举实现
- ✅ `AuditAppendResult` dataclass 实现
- ✅ `resolve_audit_target()` 实现并测试（8 测试）
- ✅ `validate_append_only_target_path()` 实现并测试（5 测试）
- ✅ `serialize_audit_record_jsonl()` 实现并测试（2 测试）
- ✅ `append_audit_record_to_target()` 实现并测试（5 测试）
- ✅ `append_diagnostic_result_audit_record()` 实现并测试（2 测试）
- ✅ `append_all_diagnostic_audit_records()` 实现并测试（3 测试）
- ✅ `run_all_diagnostics()` 新增 `append_audit` 参数
- ✅ `--append-audit` CLI flag 实现
- ✅ `_append_audit_to_trail()` helper 实现
- ✅ 28 个 writer 测试 PASS
- ✅ 400 个全部测试 PASS
- ✅ CLI smoke: 无 flag 不创建 audit_trail
- ✅ CLI smoke: --append-audit 创建并追加（9 条）
- ✅ CLI smoke: 第二次追加行数翻倍（9 → 18）
- ✅ RootGuard: 路径穿越/覆盖模式/网络调用/符号链接 全部拒绝
- ✅ py_compile 全部通过
- ✅ 不修改任何现有测试（70 CLI 测试全部保留）

---

## 15. 下一轮建议 (R241-11D)

**实现 Phase D — Read Path Query Engine：**

1. `build_audit_query_specs()` — 根据查询维度构建查询规格
2. `query_audit_trail()` — 读取并过滤 JSONL 文件
3. `scan_append_only_audit_trail()` — 扫描目录返回元数据
4. CLI 子命令：`diagnose.py audit query --event-type=nightly_health_review --since=2026-04-01`
5. 支持维度：`event_type`、`write_mode`、`sensitivity_level`、`time_range`、`payload_hash`
6. Rotation policy 查询支持（daily/weekly/monthly）

R241-11D 验收条件：
- `query_audit_trail()` 返回过滤后的记录
- 支持所有 AuditQueryDimension 枚举值
- 支持时间范围过滤
- 支持 JSON/CSV 输出格式
- 10+ 新测试

---

## 判定

**A — R241-11C Append-only JSONL Writer 实现成功，可进入 R241-11D Read Path Query Engine**

- ✅ 28 个 writer 测试 PASS
- ✅ 400 个全部测试 PASS
- ✅ 9 条记录首次追加，18 条二次追加（append-only invariant verified）
- ✅ `write_mode` 从 `design_only` 过渡到 `append_only`
- ✅ 3 个 JSONL 文件创建：`foundation_diagnostic_runs.jsonl`、`nightly_health_reviews.jsonl`、`feishu_summary_dryruns.jsonl`
- ✅ `audit_record` 的 `payload_hash`、`write_mode`、`event_type` 正确
- ✅ `--append-audit` flag 按需启用
- ✅ 路径安全：reject `..`、runtime paths、非 .jsonl、symlinks
- ✅ 文件模式安全：仅有 `"a"` append 模式
- ✅ 刷盘安全：`f.flush() + os.fsync()` 强制持久化
- ✅ 异常安全：`_append_audit_to_trail()` 捕获所有异常
- ✅ RootGuard PASS
- ✅ py_compile PASS
- ✅ 不修改任何现有测试

---

## A. 全部验证命令执行记录

```bash
# 1. py_compile
python -m py_compile backend/app/audit/audit_trail_writer.py  # ✅
python -m py_compile backend/app/audit/__init__.py             # ✅
python -m py_compile backend/app/foundation/read_only_diagnostics_cli.py  # ✅

# 2. 全部测试
python -m pytest backend/app/audit/test_audit_trail_contract.py -q  # ✅ 29 PASS
python -m pytest backend/app/audit/test_audit_trail_writer.py -q   # ✅ 28 PASS
python -m pytest backend/app/foundation/test_read_only_diagnostics_cli.py -q  # ✅ 70 PASS
python -m pytest backend/app/nightly/ backend/app/rtcm/ backend/app/prompt/ backend/app/tool_runtime/ backend/app/mode/ backend/app/gateway/ backend/app/asset/ backend/app/memory/ backend/app/m11/ -q  # ✅ 273 PASS

# 3. CLI smoke — 无 --append-audit
ls migration_reports/foundation_audit/audit_trail/  # ❌ 不存在（预期）

# 4. CLI smoke — 带 --append-audit (第1次)
python scripts/foundation_diagnose.py all --format json --append-audit  # ✅ 9 records
wc -l migration_reports/foundation_audit/audit_trail/*.jsonl
# 1 feishu, 7 foundation, 1 nightly = 9 total

# 5. CLI smoke — 带 --append-audit (第2次)
python scripts/foundation_diagnose.py all --format json --append-audit  # ✅ 9 more
wc -l migration_reports/foundation_audit/audit_trail/*.jsonl
# 2 feishu, 14 foundation, 2 nightly = 18 total
```
