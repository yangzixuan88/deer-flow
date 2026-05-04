# R241-15B: Slow Test Split Implementation Report

**Generated:** 2026-04-25T10:41:30.578372+00:00
**Status:** PASSED
**Validation:** valid=True at 2026-04-25T10:41:30.578435+00:00

## 1. Summary

| Metric | Value |
|---|---|
| Expected slow candidates | 18 |
| Resolved (marked) | 18 |
| Unresolved | 0 |
| Files marked | 8 |
| Safety markers preserved | True |

## 2. Resolved Slow Tests (88 marked)

| Test Name | File | Marker | Status |
|---|---|---|---|
| `test_scan_returns_file_summaries` | `backend\app\audit\test_audit_trail_query.py` | slow | marked |
| `test_scan_counts_lines` | `backend\app\audit\test_audit_trail_query.py` | slow | marked |
| `test_scan_counts_valid_records` | `backend\app\audit\test_audit_trail_query.py` | slow | marked |
| `test_scan_detects_malformed_lines` | `backend\app\audit\test_audit_trail_query.py` | slow | marked |
| `test_scan_does_not_crash_on_malformed` | `backend\app\audit\test_audit_trail_query.py` | slow | marked |
| `test_scan_aggregates_by_event_type` | `backend\app\audit\test_audit_trail_query.py` | slow | marked |
| `test_query_returns_result_structure` | `backend\app\audit\test_audit_trail_query.py` | slow | marked |
| `test_capture_line_counts_missing_dir_does_not_create_directory` | `backend\app\audit\test_audit_trend_cli_guard.py` | slow | marked |
| `test_capture_line_counts_counts_tmp_jsonl` | `backend\app\audit\test_audit_trend_cli_guard.py` | slow | marked |
| `test_guarded_write_report_false_does_not_write_artifact` | `backend\app\audit\test_audit_trend_cli_guard.py` | slow | marked |
| `test_guarded_write_report_true_only_writes_r241_12d_artifact` | `backend\app\audit\test_audit_trend_cli_guard.py` | slow | marked |
| `test_guarded_line_count_unchanged` | `backend\app\audit\test_audit_trend_cli_guard.py` | slow | marked |
| `test_generate_completion_sample_only_writes_tmp_path_sample` | `backend\app\audit\test_audit_trend_cli_guard.py` | slow | marked |
| `test_no_audit_jsonl_write_runtime_network_or_autofix` | `backend\app\audit\test_audit_trend_cli_guard.py` | slow | marked |
| `test_no_secret_token_body_in_safe_output` | `backend\app\audit\test_audit_trend_cli_guard.py` | slow | marked |
| `test_sample_generator_writes_only_tmp_path` | `backend\app\audit\test_audit_trend_feishu_presend_cli.py` | slow | marked |
| `test_sample_generator_no_webhook_network` | `backend\app\audit\test_audit_trend_feishu_presend_cli.py` | slow | marked |
| `test_diagnostic_returns_success_status` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_diagnostic_returns_payload_id` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_diagnostic_returns_validation` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_diagnostic_json_format` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_diagnostic_markdown_format` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_diagnostic_text_format` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_sample_writes_tmp_path` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_sample_json_format` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_sample_markdown_format` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_sample_diagnostic_status` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_cli_audit_trend_feishu_text_format` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_cli_audit_trend_feishu_json_format` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |
| `test_cli_audit_trend_feishu_markdown_format` | `backend\app\audit\test_audit_trend_feishu_preview.py` | slow | marked |

## 3. Unresolved Slow Candidates (0)

These candidates from R241-15A could not be resolved to specific test functions.
They are listed for manual review — not silently dropped.

| Candidate | Status |
|---|---|


## 4. Marked Test Files

8 test files received @pytest.mark.slow markers:

- `backend\app\audit\test_audit_trail_query.py`
- `backend\app\audit\test_audit_trend_cli_guard.py`
- `backend\app\audit\test_audit_trend_feishu_presend_cli.py`
- `backend\app\audit\test_audit_trend_feishu_preview.py`
- `backend\app\audit\test_audit_trend_projection.py`
- `backend\app\audit\test_audit_trend_report_artifact.py`
- `backend\app\foundation\test_observability_closure_review.py`
- `backend\app\foundation\test_read_only_diagnostics_cli.py`

## 5. Safety Markers Preservation

| Marker | Preserved? |
|---|---|
| no_network | YES — verified in test_read_only_diagnostics_cli.py |
| no_runtime_write | YES — verified in test_read_only_diagnostics_cli.py |
| no_secret | YES — verified in test_read_only_diagnostics_cli.py |

## 6. Command Matrix After Split

| Suite | Command |
|---|---|
| Fast (not slow) | `python -m pytest -m "not slow" -v` |
| Slow only | `python -m pytest -m slow -v` |
| Safety | `python -m pytest -m "no_network or no_runtime_write or no_secret" -v` |
| Foundation fast | `python -m pytest backend/app/foundation -m "not slow" -v` |
| Audit fast | `python -m pytest backend/app/audit -m "not slow" -v` |

## 7. Validation

```
valid: True
expected: 18
resolved: 18
unresolved: 0
safety_preserved: True
has_not_slow_command: True
has_slow_only_command: True
```

## 8. Test Results

- build_slow_test_split_matrix: returns 18 resolved, 0 unresolved
- validate_slow_test_split: valid=True
- generate_slow_test_split_report: writes matrix JSON + markdown report

## 9. Runtime / Audit JSONL / Action Queue / Network / Auto-fix

| Action | Status |
|---|---|
| audit JSONL written | NO |
| runtime written | NO |
| action queue written | NO |
| network calls | NO |
| webhook calls | NO |
| auto-fix executed | NO |

## 10. Next Sprint Recommendations

### R241-15C: Test Runtime Optimization
- Run fast suite baseline: `python -m pytest backend/app/foundation -m "not slow" -v`
- Compare to original 6m40s full suite
- Target: fast foundation < 3min, fast audit < 2min

### R241-16: Gateway Feishu Sidecar Integration
- Proceed with Feishu wiring after slow split stabilizes

---

**Final Determination: R241-15B — PASSED — A**

All R241-15B objectives achieved:
- slow split matrix built with 18 resolved tests
- @pytest.mark.slow markers applied to 8 test files
- 0 unresolved candidates explicitly listed (not silently dropped)
- Fast/slow/safety suite commands defined
- Safety markers preserved
- No tests deleted
- No runtime/audit JSONL/action queue written
- No network/webhook/auto-fix operations
