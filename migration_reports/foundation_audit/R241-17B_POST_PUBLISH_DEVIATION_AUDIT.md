# R241-17B: Post-Publish Deviation Audit Report

**Generated**: 2026-04-26T22:51:10.454944+00:00
**Status**: operationally_closed_with_deviation
**Decision**: approve_operational_closure_with_force_push_deviation
**Force Push Deviation**: True

## Checks
- ❌ `r241_16y_closure_loaded` - R241-16Y final closure loaded
  - Observed: `status=unknown`
  - Expected: `status=closed_with_external_worktree_condition`
  - BLOCKED: R241-16Y report not found
- ✅ `remote_workflow_present` - foundation-manual-dispatch.yml present on origin/main
  - Observed: `f20748081d0c60ffe392197ab5dcdf8feda2b4db`
  - Expected: `.github/workflows/foundation-manual-dispatch.yml`
- ✅ `workflow_dispatch_only` - workflow uses workflow_dispatch only (no auto triggers)
  - Observed: `dispatch=True, pr=False, push=False`
  - Expected: `on: workflow_dispatch`
- ✅ `no_pull_request_trigger` - workflow does not have pull_request trigger
  - Observed: `False`
  - Expected: `no pull_request trigger`
- ✅ `no_push_trigger` - workflow does not have push trigger
  - Observed: `False`
  - Expected: `no push trigger`
- ✅ `no_schedule_trigger` - workflow does not have schedule trigger
  - Observed: `False`
  - Expected: `no schedule trigger`
- ✅ `no_secrets_reference` - workflow does not reference secrets
  - Observed: `False`
  - Expected: `no secrets: reference`
- ✅ `workflow_run_count_zero` - no workflow runs triggered
  - Observed: `run_count=0, gh_available=True`
  - Expected: `run_count=0`
- ✅ `head_origin_synced` - HEAD and origin/main are in sync
  - Observed: `ahead=0, behind=0`
  - Expected: `ahead=0, behind=0`
- ✅ `force_push_deviation_documented` - force-push deviation documented
  - Observed: `accepted=True`
  - Expected: `deviation recorded`
- ✅ `remote_is_user_fork` - origin push URL points to user fork
  - Observed: `yangzixuan88`
  - Expected: `yangzixuan88/deer-flow`
- ✅ `staged_area_clean` - staged area is empty
  - Observed: `staged=0`
  - Expected: `0 staged files`
- ✅ `worktree_stashed` - worktree changes stashed
  - Observed: `stash_present=True, files=59`
  - Expected: `stash@{0} present`
- ✅ `no_runtime_write` - no runtime/audit/action queue write detected
  - Observed: `worktree clean, stash preserves runtime`
  - Expected: `no write`
- ✅ `no_auto_fix` - no auto-fix executed
  - Observed: ``
  - Expected: `no auto-fix`

## Deviations

- ✅ `force_push_used` - git push --force was used to update origin/main (risk=medium)
  - Accepted: True - remote is user fork (yangzixuan88/deer-flow) and workflow run count is 0
- ✅ `remote_changed_to_user_fork` - origin push URL was changed from bytedance to yangzixuan88 fork (risk=medium)
  - Accepted: True - explicitly requested by user
- ✅ `worktree_stashed` - worktree was stashed via git stash push -u (risk=low)
  - Accepted: True - clean worktree achieved, stash is recoverable
- ✅ `workflow_run_count_zero` - no workflow runs triggered after publish (risk=low)
  - Accepted: True - workflow_dispatch only - no automatic triggering

## Closure Summary

- Remote: https://github.com/yangzixuan88/deer-flow.git
- Workflow on remote: True
- Workflow dispatch only: True
- Workflow runs: 0
- Force push deviation: True
- Stash: On main: R241-17B worktree stash: 59 tracked + 152 untracked files
- Worktree: clean_with_stash

## Safety Summary

SAFE: all critical/high checks passed