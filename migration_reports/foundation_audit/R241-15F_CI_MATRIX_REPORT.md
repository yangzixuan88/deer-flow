# R241-15F CI Matrix Report

## 1. Modified Files

- `backend/app/foundation/ci_matrix_plan.py`
- `backend/app/foundation/test_ci_matrix_plan.py`
- `docs/testing/FOUNDATION_TESTING_GUIDE.md`
- `migration_reports/foundation_audit/R241-15F_CI_MATRIX_PLAN.json`
- `migration_reports/foundation_audit/R241-15F_CI_MATRIX_REPORT.md`

## 2. CI stage catalog

- Smoke: `python -m pytest -m smoke -v`
- Fast Unit + Fast Integration: `python -m pytest backend/app/foundation backend/app/audit -m "not slow" -v`
- Safety: `python -m pytest backend/app/foundation backend/app/audit -m "no_network or no_runtime_write or no_secret" -v`
- Slow Integration: `python -m pytest backend/app/foundation backend/app/audit -m slow -v`
- Full Regression: `python -m pytest backend/app/foundation backend/app/audit backend/app/nightly backend/app/rtcm backend/app/prompt backend/app/tool_runtime backend/app/mode backend/app/gateway backend/app/asset backend/app/memory backend/app/m11 -v`

## 3. marker usage policy

- `smoke`: Minimal import/registry/root health tests expected to finish quickly. Fast lane allowed: True
- `unit`: Pure functions: validators, formatters, classifiers, schema builders. Fast lane allowed: True
- `integration`: Cross-module helpers, CLI wrappers, projections, query helpers. Fast lane allowed: True
- `slow`: Real repo scan, real aggregate diagnostic, real CLI smoke, sample/report generation. Fast lane allowed: False
- `full`: Full regression-only cases or broad coverage groups. Fast lane allowed: False
- `no_network`: Tests proving no webhook/network calls happen. Fast lane allowed: True
- `no_runtime_write`: Tests proving no runtime/action queue/governance writes happen. Fast lane allowed: True
- `no_secret`: Tests proving no token/secret/webhook URL/full private body is output. Fast lane allowed: True

## 4. synthetic fixture policy

Should use:
- formatter structure only
- payload schema only
- projection aggregation shape
- report/sample JSON shape
- path validation
- audit_record field existence
- repeated run_all_diagnostics without validating real repo state

## 5. real boundary keep rules

- RootGuard
- append-only audit JSONL invariant
- audit query real JSONL read smoke
- trend CLI guard line count
- no network / no webhook / no secret / no runtime write safety
- Feishu preview / pre-send validator real CLI smoke
- at least one real repo scan slow smoke
- Gateway smoke

## 6. test contribution checklist

- Is this unit / integration / slow / safety / full?
- Does it read the real repository?
- Does it scan many files?
- Does it generate sample/report artifacts?
- Does it call CLI aggregate diagnostics?
- Does it involve network/webhook/secret/runtime write boundaries?
- Can it use a synthetic fixture?
- Must it keep a real boundary?
- Does it need no_network / no_runtime_write / no_secret marker?
- Will it pollute the fast lane?

## 7. report path consistency result

- primary exists: True at `E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit`
- backend path exists: True at `E:\OpenClaw-Base\deerflow\backend\migration_reports\foundation_audit`
- path inconsistency: True
- action taken: reported_only_no_migration_no_delete

## 8. runtime baseline and thresholds

- baselines: {'foundation_fast_baseline': 11.33, 'audit_fast_baseline': 2.37, 'slow_baseline': 6.84, 'safety_baseline': 1.07, 'collect_only_baseline': 2.86}
- thresholds: {'foundation_fast_warning_threshold': 30, 'foundation_fast_blocker_threshold': 60, 'audit_fast_warning_threshold': 15, 'slow_suite_warning_threshold': 60, 'safety_suite_warning_threshold': 10, 'collect_only_warning_threshold': 10}

## 9. validation result

- valid: True
- warnings: []
- errors: []

## 10. Test Results

- RootGuard Python: PASS
- RootGuard PowerShell: PASS
- Compile: PASS
- New tests: `backend/app/foundation/test_ci_matrix_plan.py` = 26 passed in 0.16s
- Stabilization tests: 96 passed in 1.16s
- Marker list: 8 project markers present (`smoke`, `unit`, `integration`, `slow`, `full`, `no_network`, `no_runtime_write`, `no_secret`)
- Foundation fast: 230 passed, 49 deselected in 10.76s
- Audit fast: 359 passed, 57 deselected in 2.17s
- Slow suite: 106 passed, 589 deselected in 6.88s
- Safety suite: 5 passed, 690 deselected in 1.06s
- Collect-only: 695 collected in 0.34s

## 11. Deleted Or Skipped Tests

No tests are deleted. No tests are skipped or xfailed.

## 12. Safety Coverage

No safety coverage is reduced. Safety markers remain independently runnable.

## 13. Runtime / Audit JSONL / Action Queue

No runtime, audit JSONL, or action queue writes are performed.

## 14. Network / Webhook

No network or webhook calls are performed.

## 15. Auto-fix

No auto-fix is performed.

## 16. Remaining Breakpoints

- Resolve or document the `backend/migration_reports/foundation_audit` compatibility path.
- Add CI configuration only in a future implementation pass.

## 17. Next Recommendation

Proceed to manual confirmation and CI implementation planning.
