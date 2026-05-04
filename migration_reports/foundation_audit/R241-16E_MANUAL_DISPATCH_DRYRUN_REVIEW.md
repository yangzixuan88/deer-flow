# R241-16E Manual Dispatch Dry-run Review

## 1. Modified Files

- `backend/app/foundation/ci_manual_dispatch_review.py`
- `backend/app/foundation/test_ci_manual_dispatch_review.py`
- `migration_reports/foundation_audit/R241-16E_MANUAL_DISPATCH_DRYRUN_REVIEW.json`
- `migration_reports/foundation_audit/R241-16E_MANUAL_DISPATCH_DRYRUN_REVIEW.md`

## 2. Enumerations

### ManualDispatchReadinessStatus

- ready_for_implementation_review, blocked_missing_confirmation_input, blocked_job_guard_missing,
- blocked_artifact_policy, blocked_existing_workflow_conflict, blocked_security_policy, design_only, unknown

### ManualDispatchRiskLevel

- low, medium, high, critical, unknown

### ManualDispatchJobGuardMode

- guarded_by_confirmation_input, guarded_by_if_false, guarded_by_stage_selection, disabled, unknown

### ManualDispatchImplementationOption

- keep_disabled_draft, manual_dispatch_plan_only, manual_dispatch_fast_safety_only, manual_dispatch_all_pr_stages, unknown

## 3. ManualDispatchInputSpec Fields

- input_id, name, required, default, expected_value, description
- blocks_execution_if_missing, blocks_execution_if_mismatch, secret_allowed, warnings, errors

## 4. ManualDispatchJobGuardSpec Fields

- job_id, job_type, guard_mode, enabled_by_default, requires_confirmation_input
- requires_stage_selection, allowed_stage_selections, forbidden_triggers
- network_allowed, secret_refs_allowed, runtime_write_allowed, auto_fix_allowed, warnings, errors

## 5. ManualDispatchDryRunReview Fields

- review_id, generated_at, status, dispatch_input_specs, job_guard_specs
- existing_workflow_compatibility, artifact_policy_check, path_compatibility_check
- threshold_policy_check, security_checks, rollback_plan
- implementation_options, recommended_option, recommendation_reason
- manual_confirmation_requirements, workflow_created, trigger_enabled,
- network_recommended, runtime_write_recommended, secret_read_recommended, auto_fix_recommended

## 6. Dispatch Input Specs Result

### confirm_manual_dispatch
- name: `confirm_manual_dispatch`
- required: `True`
- default: `None`
- expected_value: `CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN`
- blocks_if_missing: `True`
- blocks_if_mismatch: `True`
- secret_allowed: `False`

### stage_selection
- name: `stage_selection`
- required: `False`
- default: `all_pr`
- expected_value: `None`
- blocks_if_missing: `False`
- blocks_if_mismatch: `False`
- secret_allowed: `False`
- allowed_values: `['all_pr', 'fast', 'safety', 'collect_only', 'all_nightly']`
- forbidden_values: `['full', 'real_send', 'auto_fix', 'webhook', 'secret']`
  - ⚠️ full is manual_only and not available in manual dispatch dry-run

### execute_mode
- name: `execute_mode`
- required: `False`
- default: `plan_only`
- expected_value: `None`
- blocks_if_missing: `False`
- blocks_if_mismatch: `False`
- secret_allowed: `False`
- allowed_values: `['plan_only', 'execute_selected']`

## 7. Job Guard Specs Result

### job_smoke (smoke)
- guard_mode: `guarded_by_confirmation_input`
- enabled_by_default: `False`
- requires_confirmation_input: `True`
- requires_stage_selection: `False`
- allowed_stage_selections: `['all_pr', 'smoke', 'collect_only']`
- forbidden_triggers: `['pull_request', 'push', 'schedule']`
- network_allowed: `False`
- secret_refs_allowed: `False`
- runtime_write_allowed: `False`
- auto_fix_allowed: `False`
  - ⚠️ smoke is pr_warning only — does not block merge

### job_fast (fast)
- guard_mode: `guarded_by_confirmation_input`
- enabled_by_default: `False`
- requires_confirmation_input: `True`
- requires_stage_selection: `False`
- allowed_stage_selections: `['all_pr', 'fast', 'all_nightly']`
- forbidden_triggers: `['pull_request', 'push', 'schedule']`
- network_allowed: `False`
- secret_refs_allowed: `False`
- runtime_write_allowed: `False`
- auto_fix_allowed: `False`

### job_safety (safety)
- guard_mode: `guarded_by_confirmation_input`
- enabled_by_default: `False`
- requires_confirmation_input: `True`
- requires_stage_selection: `False`
- allowed_stage_selections: `['all_pr', 'safety', 'all_nightly']`
- forbidden_triggers: `['pull_request', 'push', 'schedule']`
- network_allowed: `False`
- secret_refs_allowed: `False`
- runtime_write_allowed: `False`
- auto_fix_allowed: `False`

### job_collect_only (collect_only)
- guard_mode: `guarded_by_confirmation_input`
- enabled_by_default: `False`
- requires_confirmation_input: `True`
- requires_stage_selection: `False`
- allowed_stage_selections: `['all_pr', 'collect_only']`
- forbidden_triggers: `['pull_request', 'push', 'schedule']`
- network_allowed: `False`
- secret_refs_allowed: `False`
- runtime_write_allowed: `False`
- auto_fix_allowed: `False`
  - ⚠️ collect-only is pr_warning only

### job_slow (slow)
- guard_mode: `guarded_by_stage_selection`
- enabled_by_default: `False`
- requires_confirmation_input: `True`
- requires_stage_selection: `True`
- allowed_stage_selections: `['all_nightly']`
- forbidden_triggers: `['pull_request', 'push', 'schedule']`
- network_allowed: `False`
- secret_refs_allowed: `False`
- runtime_write_allowed: `False`
- auto_fix_allowed: `False`
  - ⚠️ slow is nightly_required — not available in all_pr selection

## 8. Security Checks Result

- ✅ PASS `check_no_pr_trigger` (critical): Manual dispatch workflow must not have pull_request trigger.
- ✅ PASS `check_no_push_trigger` (critical): Manual dispatch workflow must not have push trigger.
- ✅ PASS `check_no_schedule_trigger` (high): Manual dispatch workflow must not have schedule trigger.
- ✅ PASS `check_no_secrets` (critical): No secret refs allowed in manual dispatch job specs.
- ✅ PASS `check_no_network` (critical): No network calls allowed in manual dispatch jobs.
- ✅ PASS `check_no_webhook` (critical): No webhook calls allowed in manual dispatch jobs.
- ✅ PASS `check_no_runtime_write` (critical): No runtime writes allowed in manual dispatch jobs.
- ✅ PASS `check_no_audit_jsonl_write` (high): Audit JSONL writes are forbidden in manual dispatch.
- ✅ PASS `check_no_action_queue_write` (high): Action queue writes are forbidden in manual dispatch.
- ✅ PASS `check_no_auto_fix` (critical): Auto-fix is never executed in manual dispatch dry-run.
- ✅ PASS `check_no_feishu_send` (critical): Feishu/Lark send is forbidden in manual dispatch.
- ✅ PASS `check_artifact_policy_excludes_sensitive` (high): Artifact policy excludes audit_trail JSONL, runtime, action_queue, secrets.
- ✅ PASS `check_existing_workflows_unchanged` (medium): Existing workflows are only read; not modified.
- ✅ PASS `check_workflow_remains_manual_dispatch` (critical): Workflow remains manual dispatch only — no auto triggers.

## 9. Existing Workflow Compatibility Result

- workflow_count: `0`

## 10. Artifact / Path / Threshold Policy Result

- artifact specs: `4`
- path action: `report_only`
- path inconsistency: `False`

## 11. Rollback Plan

- rollback_plan_id: `R241-16E_manual_dispatch_rollback`
- Set workflow file to if: ${{ false }} or remove workflow_dispatch trigger.
- Remove confirmation input from workflow_dispatch inputs.
- Use scripts/ci_foundation_check.py as local fallback.
- Validate with local plan-only smoke.

## 12. Implementation Options

- option_a: Keep Disabled Draft Only (risk=low)
  Continue with R241-16C state; no new manual dispatch workflow created.
- option_b: Manual Dispatch Plan-only Workflow (risk=low)
  Create a manual-only workflow that defaults to plan_only mode. No execution without explicit execute_mode=execute_selected.
- option_c: Manual Dispatch Fast+Safety Execute (risk=medium) **[RECOMMENDED]**
  Allow manual trigger of fast+safety execute_selected. Still no PR blocking.
- option_d: Manual Dispatch All PR Stages (risk=medium)
  Allow manual trigger of smoke+fast+safety+collect_only. All remain pr_warning / non-blocking.

**Recommended:** `option_c` — existing_workflow_conflict_low_fast_safety_ready

## 13. Manual Confirmation Requirements

- phrase: `CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN`
- workflow_dispatch trigger only
- no pull_request / push / schedule triggers
- no secrets
- no network / webhook calls
- no runtime writes
- no audit JSONL writes
- no action queue writes
- no auto-fix
- no Feishu send
- plan_only as default execute_mode

## 14. Validation Result

- valid: `True`
- errors: `[]`
- warnings: `[]`

## 15. Test Result

To be populated from verification command output.

## 16. Workflow / Trigger

No workflow is created. No trigger is enabled.

## 17. Existing Workflow Mutation

Existing workflow files are only read; they are not modified.

## 18. Secret Access

No secret is read.

## 19. Network / Webhook

No network or webhook call is performed.

## 20. Runtime / Audit JSONL / Action Queue

No runtime, audit JSONL, or action queue write is performed.

## 21. Auto-fix

No auto-fix is executed.

## 22. Remaining Breakpoints

- Manual confirmation phrase required before any workflow creation.
- Existing backend workflows with PR/push triggers should be reviewed for overlap.
- Full stage (manual_only) is out of scope for this dry-run review.

## 23. Next Recommendation

Proceed to R241-16F Manual Dispatch Workflow Draft Implementation Review
or wait for explicit CONFIRM_MANUAL_FOUNDATION_CI_DRYRUN confirmation.