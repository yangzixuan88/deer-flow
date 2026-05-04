# R241-15D Targeted Marker Refinement Report

## 1. Modified Files

- `backend/app/foundation/targeted_marker_refinement.py`
- `backend/app/foundation/test_targeted_marker_refinement.py`
- `backend/app/foundation/test_read_only_diagnostics_cli.py`
- `migration_reports/foundation_audit/R241-15D_TARGETED_MARKER_REFINEMENT_MATRIX.json`
- `migration_reports/foundation_audit/R241-15D_TARGETED_MARKER_REFINEMENT_REPORT.md`

## 2. durations baseline before

- foundation fast before: 181 passed / 30 deselected, 315.74s pytest runtime, 317.76s wall-clock
- audit fast before: 359 passed / 57 deselected, 2.01s pytest runtime, 4.29s wall-clock
- safety before: 5 passed / 622 deselected, 1.01s pytest runtime, 3.39s wall-clock
- collect-only before: 627 collected, 2.86s wall-clock

## 3. top duration tests

- 38.90s `test_format_json_returns_dict`
- 34.64s `test_no_tool_execution`
- 34.28s `test_audit_record_payload_hash_present`
- 34.16s `test_format_markdown_returns_string`
- 34.16s `test_format_text_returns_string`
- 34.08s `test_run_all_has_audit_record_event_type_diagnostic_cli_run`
- 17.22s `test_run_feishu_summary_diagnostic_send_allowed_false`
- 13.06s `test_audit_record_redaction_applied_for_sensitive_payload`
- 12.98s `test_run_feishu_summary_diagnostic_validation_present`
- 12.97s `test_run_feishu_summary_has_audit_record_event_type_feishu_summary_dry_run`
- 12.91s `test_run_nightly_has_audit_record_event_type_nightly_health_review`
- 12.86s `test_run_feishu_summary_diagnostic_webhook_required_true`
- 12.84s `test_run_feishu_summary_diagnostic_no_webhook_call_flag`

## 4. candidate confirmation result

- reviewed: 5
- confirmed_slow_marker_needed: 5
- keep_fast_unit: 0
- needs_synthetic_fixture_later: 0
- safety_marker_only: 0
- unresolved_for_manual_review: 0

## 5. marker changes applied

- `backend/app/foundation/test_read_only_diagnostics_cli.py::test_run_feishu_summary_diagnostic_send_allowed_false` -> slow, integration; reason=real Feishu summary projection path in foundation fast durations
- `backend/app/foundation/test_read_only_diagnostics_cli.py::test_run_feishu_summary_diagnostic_webhook_required_true` -> slow, integration; reason=real Feishu summary projection path in foundation fast durations
- `backend/app/foundation/test_read_only_diagnostics_cli.py::test_run_feishu_summary_diagnostic_no_webhook_call_flag` -> slow, integration; reason=real Feishu summary projection path in foundation fast durations
- `backend/app/foundation/test_read_only_diagnostics_cli.py::test_run_feishu_summary_diagnostic_validation_present` -> slow, integration; reason=real Feishu summary projection path in foundation fast durations

## 6. unresolved candidates

- none

## 7. fast / slow / safety remeasure after

- foundation fast after: 182 passed / 49 deselected, 10.42s pytest runtime, 12.41s wall-clock
- audit fast after: 359 passed / 57 deselected, 1.83s pytest runtime, 3.82s wall-clock
- slow after: 106 passed / 541 deselected, 419.35s pytest runtime, 421.35s wall-clock
- safety after: 5 passed / 642 deselected, 0.96s pytest runtime, 3.16s wall-clock
- collect-only after: 647 collected, 2.64s wall-clock

## 8. performance delta

- foundation fast delta: -305.32s pytest runtime, 96.70% faster
- audit fast delta: -0.18s pytest runtime
- slow suite delta: +303.75s pytest runtime, expected after moving real diagnostic work out of fast lane
- safety delta: -0.05s pytest runtime

## 9. validation result

- valid: True
- warnings: []
- errors: []

## 10. Test Results

- RootGuard Python / PowerShell: PASS
- Compile: PASS
- new targeted marker tests: 20 passed
- previous optimization/stabilization tests: 54 passed
- marker list: 8 required markers present
- collect-only: 647 collected
- foundation fast: 182 passed / 49 deselected
- audit fast: 359 passed / 57 deselected
- slow suite: 106 passed / 541 deselected
- safety suite: 5 passed / 642 deselected

## 11. Deleted Or Skipped Tests

No tests are deleted. No tests are skipped or xfailed.

## 12. Safety Coverage

No. Existing safety markers remain runnable as a separate suite.

## 13. Runtime / Audit JSONL / Action Queue Writes

No runtime, audit JSONL, or action queue writes are performed.

## 14. Network / Webhook Calls

No network or webhook calls are performed.

## 15. Auto-fix

No auto-fix is performed.

## 16. Remaining Breakpoints

- Additional high-duration tests should only be marked after fresh `--durations` evidence.
- Scan-heavy tests remain candidates for R241-15E synthetic fixture replacement.

## 17. Next Recommendation

Proceed to R241-15E Synthetic Fixture Replacement for remaining real repository scan and sample generation cost.
