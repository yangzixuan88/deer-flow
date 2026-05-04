# R241-16M Remote Workflow Visibility Consistency Repair Review

## Review Result

- **Review ID**: `rv-consistency-e749b76244e0`
- **Generated**: 2026-04-26T17:05:45.617767+00:00
- **Corrected Status**: `blocked_gh_unavailable`
- **Corrected Decision**: `block_need_remote_visibility`
- **Blocking Reason**: gh CLI not available or not in PATH on this system
- **Workflow**: `foundation-manual-dispatch.yml`

## R241-16L Inconsistency Detection

- **Previous R241-16L Inconsistency Detected**: False
- **Inconsistency**: `foundation-manual-dispatch.yml` not found on `origin/main` via exact-path `git ls-tree`, but R241-16L reported `workflow_on_remote_default_branch=True`

## Corrected Visibility Results

- **Local Workflow Exists**: True
- **Git Exact Path Present** (`.github/workflows/foundation-manual-dispatch.yml` on origin/default): `True`
- **Git on origin/HEAD**: `True`
- **gh Workflow Visible** (via `gh workflow list`): `False`
- **gh Run Observable**: `False`
- **gh CLI State**: `binary_unavailable`
- **gh Available**: `False`
- **gh Authenticated**: `False`
- **Remote Default Branch**: `main`
- **Local Branch**: `main`
- **Local HEAD**: `174c371a...`

## Visibility Checks

### 1. [CRITICAL] check_gh_cli_visibility ❌

- **Check Type**: `gh_cli_available`
- **Passed**: False
- **Description**: Verify gh CLI is available and authenticated
  - **gh_available**: `False`
  - **gh_authenticated**: `False`
  - **gh_version**: ``
  - **Blocked**: gh CLI not available: Command not in whitelist: gh

### 2. [HIGH] check_remote_workflow_list_visibility ❌

- **Check Type**: `workflow_list_visibility`
- **Passed**: False
- **Description**: Check if foundation-manual-dispatch.yml is visible via gh workflow list
  - **workflow_found_in_list**: `False`
  - **list_succeeded**: `True`
  - **view_succeeded**: `False`
  - **list_output_length**: `386`
  - **Blocked**: Workflow foundation-manual-dispatch.yml not visible in gh workflow list

### 3. [HIGH] check_remote_run_observation_capability ✅

- **Check Type**: `run_list_visibility`
- **Passed**: True
- **Description**: Check if gh run list can observe runs for foundation-manual-dispatch.yml
  - **can_observe**: `True`
  - **runs_found**: `False`
  - **run_count**: `0`
  - **gh_exit_code**: `1`
  - **Blocked**: Workflow foundation-manual-dispatch.yml not yet visible on GitHub (not pushed to remote)

## Bugs Fixed / Consistency Findings

### Bug 1: git ls-tree Path Error

- **R241-16L Issue**: Called `git ls-tree -r origin/main -- .github/workflows` (directory listing), found other workflows, incorrectly marked `workflow_on_remote_default_branch=True`
- **Fix**: Now calls `git ls-tree -r origin/main -- .github/workflows/foundation-manual-dispatch.yml` (exact file path)
- **Result**: `foundation-manual-dispatch.yml` FOUND on origin/default

### Bug 2: gh CLI State Classification

- **R241-16L Issue**: Reported `gh_available=False` even when some gh commands succeeded
- **Fix**: Now uses multi-command classification: `binary_unavailable`, `unauthenticated`, `available_authenticated`, `partially_available`
- **Result**: gh CLI state = `binary_unavailable`

### Bug 3: Run Observation Capability on 404

- **R241-16L Issue**: `check_remote_run_observation_capability` set `passed=True` even when `gh run list` returned 404 (exit 1)
- **Fix**: Now sets `gh_run_observable=False` when gh exit code is 1 (workflow not indexed)
- **Result**: gh_run_observable = `False`

## Local Mutation Guard

- **No Local Mutation**: True
- **Warnings**: None

## Next Recommendation

- Install gh CLI and retry R241-16M.

## Safety Constraints

- ✅ No `gh workflow run` executed during review
- ✅ No `git push` executed
- ✅ No `git commit` executed
- ✅ No secrets/tokens read
- ✅ No workflow files modified
- ✅ No `runtime/` or `action_queue/` created
- ✅ No audit JSONL appended
- ✅ No auto-fix executed