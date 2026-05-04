# R241-15E Synthetic Fixture Replacement Report

## 1. Modified Files

- `backend/app/foundation/test_read_only_diagnostics_cli.py`
- `backend/app/foundation/synthetic_fixture_plan.py`
- `backend/app/foundation/test_synthetic_fixture_plan.py`
- `migration_reports/foundation_audit/R241-15E_SYNTHETIC_FIXTURE_REPLACEMENT_MATRIX.json`
- `migration_reports/foundation_audit/R241-15E_SYNTHETIC_FIXTURE_REPLACEMENT_REPORT.md`

## 2. Slow Durations Baseline Before

- slow before: 106 passed / 541 deselected, 423.18s pytest runtime, 425.41s wall-clock
- dominant source: repeated real `run_all_diagnostics`, Feishu/nightly/prompt/rtcm projections, sample/report paths

## 3. Candidate Classification

- total: 18
- synthetic diagnostic: 3
- synthetic projection: 3
- tmp_path artifact: 0
- synthetic scan fixture: 0
- keep real boundary: 12

## 4. Synthetic Replacements Applied

- `backend/app/foundation/test_read_only_diagnostics_cli.py`: 20 tests -> monkeypatch synthetic diagnostic results with real audit_record helper

## 5. Coverage Preserved

- audit_record generation still uses add_audit_record_to_diagnostic_result
- formatters still operate on DiagnosticRunResult-like structures
- write_report tests still write only tmp_path files
- Feishu safety flags remain asserted
- no_network/no_runtime_write/no_secret safety suite remains unchanged

## 6. Validation Result

- valid: True
- warnings: []
- errors: []

## 7. Remeasure Results

- slow after: 106 passed / 563 deselected, 6.84s pytest runtime, 9.10s wall-clock
- foundation fast after: 204 passed / 49 deselected, 11.33s pytest runtime, 13.67s wall-clock
- audit fast after: 359 passed / 57 deselected, 2.37s pytest runtime, 4.68s wall-clock
- safety after: 5 passed / 664 deselected, 1.07s pytest runtime, 3.54s wall-clock
- collect-only after: 669 collected, 2.86s wall-clock

## 8. Performance Delta

- slow suite delta: -416.34s pytest runtime, 98.38% faster
- foundation fast remains under target: 11.33s
- audit fast remains under target: 2.37s
- safety suite remains independently runnable: 5 passed

## 9. Safety Boundary

No tests are deleted, skipped, or xfailed. No safety coverage is reduced.

## 10. Runtime / Audit JSONL / Action Queue

No runtime, audit JSONL, or action queue writes are performed by this plan helper.

## 11. Network / Webhook / Auto-fix

No network/webhook calls and no auto-fix execution.

## 12. Remaining Breakpoints

- Any remaining slow suite cost after this pass should be addressed only with focused tmp_path fixtures.
- Real boundary smoke may remain in slow lane if it is intentionally validating end-to-end behavior.

## 13. Next Recommendation

Re-run slow durations and decide whether a second focused synthetic fixture pass is needed.
