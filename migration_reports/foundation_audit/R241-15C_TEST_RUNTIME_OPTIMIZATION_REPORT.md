# R241-15C Test Runtime Optimization Report

## 1. 修改文件清单

新增：

- `backend/app/foundation/runtime_optimization_plan.py`
- `backend/app/foundation/test_runtime_optimization.py`
- `migration_reports/foundation_audit/R241-15C_TEST_RUNTIME_OPTIMIZATION_PLAN.json`
- `migration_reports/foundation_audit/R241-15C_TEST_RUNTIME_OPTIMIZATION_REPORT.md`

测试 marker 配置补充：

- `pytest.ini`

## 2. runtime baseline summary

- `original_baseline_runtime`: 6m40s+ / 400s+
- `foundation_fast_runtime`: 314.81s, 181 passed, 0 failed, 0 skipped, 30 deselected
- `audit_fast_runtime`: 4.34s, 359 passed, 0 failed, 0 skipped, 57 deselected
- `fast_combined_runtime`: 5m19.15s
- `slow_suite_runtime`: 115.60s, 87 passed, 0 failed, 0 skipped, 539 deselected
- `safety_suite_runtime`: 3.72s, 5 passed, 0 failed, 0 skipped, 622 deselected
- `collect_only_runtime`: 2.39s, 627 collected
- `stabilization_tests_runtime`: 2.38s, 36 passed
- `improvement_estimate`: approximately 80.85s saved vs 6m40s baseline, 20.21% faster for foundation+audit fast path

## 3. fast / slow / safety suite measurements

Measured commands:

- `python -m pytest backend/app/foundation -m "not slow" -v`: PASS, 181 passed / 30 deselected, 314.81s
- `python -m pytest backend/app/audit -m "not slow" -v`: PASS, 359 passed / 57 deselected, 4.34s
- `python -m pytest backend/app/foundation backend/app/audit -m slow -v`: PASS, 87 passed / 539 deselected, 115.60s
- `python -m pytest backend/app/foundation backend/app/audit -m "no_network or no_runtime_write or no_secret" -v`: PASS, 5 passed / 622 deselected, 3.72s
- `python -m pytest backend/app/foundation/test_stabilization_plan.py -v`: PASS, 36 passed, 2.38s
- `python -m pytest backend/app/foundation backend/app/audit --collect-only -q`: PASS, 627 collected, 2.39s

## 4. remaining slow-in-fast candidates

Detection found 173 heuristic candidates still reachable by fast suite. They are not automatically changed in this round except safety marker additions for R241-15C tests.

Candidate breakdown:

- CLI smoke: 106
- sample generation: 21
- filesystem scan: 20
- slow helper in fast path: 15
- aggregate diagnostic: 11

Representative candidates:

- `backend/app/foundation/test_integration_readiness.py:6`: filesystem scan
- `backend/app/foundation/test_integration_readiness.py:19`: filesystem scan
- `backend/app/foundation/test_integration_readiness.py:128`: filesystem scan
- `backend/app/foundation/test_observability_closure_review.py:69`: CLI smoke
- `backend/app/foundation/test_read_only_diagnostics_cli.py:19`: CLI smoke

Recommended marker change: confirm each candidate, then add `@pytest.mark.slow` only to real repository scans, real CLI smoke, full aggregate diagnostics, and sample/artifact generation. Do not mark pure unit tests slow.

## 5. marker quality audit

- Required markers: `smoke`, `unit`, `integration`, `slow`, `full`, `no_network`, `no_runtime_write`, `no_secret`
- Marker list command now exposes all 8 required markers from repository root.
- `slow_marker_count`: 89
- `safety_marker_count`: 6
- `slow_marker_too_broad`: false
- `safety_tests_all_marked_slow`: false
- `no_network_runnable`: true
- `no_runtime_write_runnable`: true
- `no_secret_runnable`: true

Adjustment made: added root `pytest.ini` so `python -m pytest --markers` works from the required root, and added safety markers to R241-15C safety tests. No tests were deleted or skipped.

## 6. optimization options

- Option A: Marker Refinement. Correct missed or over-broad markers after reviewing candidates.
- Option B: Fixture Caching. Cache read-only synthetic projection inputs in pytest fixtures.
- Option C: Synthetic Fixture Replacement. Replace real repository scans with `tmp_path` synthetic fixtures where classification logic is the target.
- Option D: Split CLI Smoke from Unit Tests. Keep real CLI smoke under integration/slow markers.
- Option E: CI Stage Matrix. Keep fast, slow, safety, and full stages separate.

## 7. recommended option

Recommended next step: Option A first, focused on foundation fast. Foundation fast remains 314.81s and dominates the combined fast runtime; audit fast is already 4.34s. After marker refinement, apply Option C to scan-heavy tests that can safely use synthetic fixtures.

## 8. validation result

`validate_runtime_optimization_plan`: valid=true.

Validation confirms the plan does not recommend deleting tests, skipping safety tests, xfail safety tests, network calls, webhook calls, runtime writes, audit JSONL writes, or auto-fix.

## 9. 测试结果

- RootGuard Python: PASS
- RootGuard PowerShell: PASS
- Compile: PASS
- New runtime optimization tests: 18 passed
- Stabilization regression: 36 passed
- Marker list: PASS, 8 custom markers visible
- Foundation fast: 181 passed / 30 deselected
- Audit fast: 359 passed / 57 deselected
- Slow-only: 87 passed / 539 deselected
- Safety suite: 5 passed / 622 deselected
- Collect-only: 627 collected

## 10. 是否删除/跳过测试

否。未删除任何测试，未使用 skip/xfail 掩盖失败，未跳过安全测试。

## 11. 是否降低安全覆盖

否。安全覆盖反而补齐了可执行 marker：`no_network`、`no_runtime_write`、`no_secret` 现在可通过指定 safety suite 单独运行。

## 12. 是否写 runtime / audit JSONL / action queue

否。未写 runtime、audit JSONL、trend database、governance_state、experiment_queue 或 action queue。

## 13. 是否调用 network / webhook

否。未调用 network，未调用 webhook，未读取或输出真实 webhook URL / token / secret。

## 14. 是否执行 auto-fix

否。未执行 auto-fix，未执行真实工具调用，未做 asset promotion/elimination、memory cleanup 或 prompt replacement。

## 15. 当前剩余断点

- Foundation fast 仍为 314.81s，是当前主要瓶颈。
- 仍有 173 个 heuristic slow-in-fast candidates，需要人工确认后做最小 marker refinement。
- Safety suite 当前只有 5 个显式 marker 测试，后续应继续给已有安全断言补充 no_network / no_runtime_write / no_secret marker。
- 部分候选为启发式误报，下一轮应结合 `pytest --durations` 做精确排序。

## 16. 下一轮建议

进入下一阶段：对 foundation fast 做 targeted marker refinement + `pytest --durations` 精确测量。建议优先处理真实 CLI smoke、full aggregate diagnostics、sample/artifact generation，再考虑用 synthetic fixture 替代真实目录扫描。
