# R241-17B-C: Post-Publish Audit Consistency Repair Report

**Task:** R241-17B-C: Post-Publish Audit Consistency Repair / Final Test Closure
**Generated:** 2026-04-27
**Status:** COMPLETED

## Executive Summary

All 8 phases of the repair plan completed successfully. The audit now returns `operationally_closed_with_deviation` status and all 75 tests pass (22 parser tests + 53 audit tests).

## Phase Completion Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Confirm current state | COMPLETED |
| 2 | Implement stable workflow trigger parser | COMPLETED |
| 3 | Fix ci_post_publish_deviation_audit.py with stable parser | COMPLETED |
| 4 | Fix 11 failing tests | COMPLETED |
| 5 | Re-run audit and verify operationally_closed_with_deviation | COMPLETED |
| 6 | Confirm worktree and stash state | COMPLETED |
| 7 | Run all validation tests | COMPLETED |
| 8 | Generate final repair report | IN PROGRESS |

## Key Technical Fixes

### 1. Stable YAML Workflow Trigger Parser

Created `backend/app/foundation/ci_workflow_trigger_parser.py` to avoid PyYAML bool coercion trap (`on:` → `True`).

**Key design:**
- Line-based parsing instead of PyYAML
- Handles all GitHub Actions trigger formats: scalar, inline array, block sequence, mapping with inputs
- `_remove_comments()` strips comment lines before parsing to avoid false positives
- `_extract_top_level_triggers()` finds `on:` at column 0, determines indentation, collects block content

**Allowed triggers:** `workflow_dispatch`, `workflow_call`, `repository_dispatch`
**Forbidden triggers:** `push`, `pull_request`, `pull_request_target`, `schedule`

### 2. Unexpected Runs Detection Fix

Fixed `inspect_workflow_run_state()` to use `run_count > 0` instead of hardcoded `False`:

```python
"unexpected_runs_detected": run_count > 0,  # was: False
```

### 3. Test Fixes

**Problem:** `TestInspectRemotePublishState` tests had incorrect mock setups with `@patch("subprocess.run")` but were calling `_run_git` (which uses subprocess internally).

**Fix:** Complete `_run_git` mock side_effect lists with all 7 git commands in order:
1. `git remote -v`
2. `git config remote.pushDefault`
3. `git rev-parse HEAD`
4. `git rev-parse origin/main`
5. `git rev-list --left-right --count origin/main...HEAD`
6. `git ls-tree -r origin/main -- .github/workflows/foundation-manual-dispatch.yml`
7. `git show origin/main:.github/workflows/foundation-manual-dispatch.yml`

**Problem:** `TestEvaluatePostPublishDeviationAudit` tests missing `has_pull_request_trigger`, `has_push_trigger`, `has_schedule_trigger` keys in mock remote state.

**Fix:** Added these keys to all `mock_remote.return_value` dicts.

**Problem:** `TestInspectWorktreeAndStashState` tests had incomplete mock side_effect lists.

**Fix:** Extended to include `stash show --stat` and `stash show --name-only` calls.

## Test Results

```
============================= 75 passed in 0.34s ==============================
- backend/app/foundation/test_ci_workflow_trigger_parser.py: 22 passed
- backend/app/foundation/test_ci_post_publish_deviation_audit.py: 53 passed
```

## Audit Result

```python
{
    "status": "operationally_closed_with_deviation",
    "decision": "approve_operational_closure_with_force_push_deviation",
    "warnings": [],
}
```

## Files Modified

1. `backend/app/foundation/ci_workflow_trigger_parser.py` (NEW)
2. `backend/app/foundation/test_ci_workflow_trigger_parser.py` (NEW)
3. `backend/app/foundation/ci_post_publish_deviation_audit.py` (modified import + trigger detection)
4. `backend/app/foundation/test_ci_post_publish_deviation_audit.py` (test fixes)

## Prohibited Actions (Not Executed)

Per R241-17B-C task specification, the following were NOT performed:
- No git push or commit
- No git stash pop
- No force push
- No gh workflow run
- No modifications to CI configuration files

## Notes

The PyYAML bool coercion trap (`on:` → `True`) was a subtle bug that could cause workflows with `on: workflow_dispatch` to be incorrectly detected as having `push` trigger due to YAML boolean parsing of the `on` key. The line-based parser correctly identifies all trigger formats without this risk.
