# R241-16A: CI Implementation Plan

**Generated:** 2026-04-26T17:03:16.779023+00:00
**Status:** design_only
**Validation:** valid=True at 2026-04-26T17:03:16.779313+00:00

---

## 1. CI Stage Implementation Specs

### Smoke (`impl_stage_smoke`)
- **Command:** `python -m pytest -m smoke -v`
- **Gating:** `pr_warning`
- **Expected runtime:** 60s (warning: 45s)
- **PR required:** False
- **Nightly required:** False
- **Marker:** `smoke`
- **Artifacts:** ['pytest_log']
  - ⚠️ smoke stage is pr_warning only — does not block merge

### Fast Unit + Fast Integration (`impl_stage_fast`)
- **Command:** `python -m pytest backend/app/foundation backend/app/audit -m "not slow" -v`
- **Gating:** `pr_blocking`
- **Expected runtime:** 30s (warning: 30s)
- **PR required:** True
- **Nightly required:** True
- **Marker:** `not slow`
- **Artifacts:** ['pytest_log', 'coverage_report']

### Safety Boundaries (`impl_stage_safety`)
- **Command:** `python -m pytest backend/app/foundation backend/app/audit -m "no_network or no_runtime_write or no_secret" -v`
- **Gating:** `pr_blocking`
- **Expected runtime:** 10s (warning: 10s)
- **PR required:** True
- **Nightly required:** True
- **Marker:** `no_network or no_runtime_write or no_secret`
- **Artifacts:** ['pytest_log']

### Slow Integration (`impl_stage_slow`)
- **Command:** `python -m pytest backend/app/foundation backend/app/audit -m slow -v`
- **Gating:** `nightly_required`
- **Expected runtime:** 60s (warning: 60s)
- **PR required:** False
- **Nightly required:** True
- **Marker:** `slow`
- **Artifacts:** ['pytest_log', 'foundation_audit_report']
  - ⚠️ slow stage is nightly_required — creates stabilization ticket on warning but does not block PR

### Full Regression (`impl_stage_full`)
- **Command:** `python -m pytest backend/app/foundation backend/app/audit backend/app/nightly backend/app/rtcm backend/app/prompt backend/app/tool_runtime backend/app/mode backend/app/gateway backend/app/asset backend/app/memory backend/app/m11 -v`
- **Gating:** `manual_only`
- **Expected runtime:** Nones (warning: 300s)
- **PR required:** False
- **Nightly required:** False
- **Marker:** `None`
- **Artifacts:** ['pytest_log', 'foundation_audit_report', 'coverage_report']
  - ⚠️ full stage is manual_only — not required on PR or nightly

### Collection Check (`impl_stage_collect_only`)
- **Command:** `python -m pytest backend/app/foundation backend/app/audit --collect-only -q`
- **Gating:** `pr_warning`
- **Expected runtime:** 10s (warning: 10s)
- **PR required:** False
- **Nightly required:** False
- **Marker:** `None`
- **Artifacts:** ['pytest_log']
  - ⚠️ collect-only stage is pr_warning only — catches collection errors without running tests

---

## 2. PR / Nightly / Manual Gating Policy

| Stage | Gating | PR Required | Nightly Required |
|---|---|---|---|
| Smoke | pr_warning | False | False |
| Fast Unit + Fast Integration | pr_blocking | True | True |
| Safety Boundaries | pr_blocking | True | True |
| Slow Integration | nightly_required | False | True |
| Full Regression | manual_only | False | False |
| Collection Check | pr_warning | False | False |

### Policy Detail

- **pr_blocking**: Stage must pass for PR to merge.
- **pr_warning**: Stage failure creates PR comment but does not block merge.
- **nightly_required**: Stage runs in nightly pipeline, not on PR.
- **manual_only**: Stage runs manually only, not in automated pipelines.

---

## 3. Artifact Collection / Path Compatibility

### art_spec_foundation_reports (foundation_audit_report)
- **Destination:** `foundation_audit_reports`
- **Retention:** 30 days
- **Include:** ['*.json', '*.md']
- **Exclude:** ['**/audit_trail/*.jsonl', '**/runtime/**', '**/action_queue/**', '**/.secret/**', '**/webhook_url*', '**/*token*', '**/*secret*']
- **Path handling:** collect_both_report_warning
- **Secrets allowed:** False
- **Runtime files allowed:** False
  - ⚠️ primary path: not found
  - ⚠️ secondary path: not found
  - ⚠️ path_inconsistency: both paths exist — no migration, no deletion in this phase

### art_spec_ci_matrix (ci_matrix_report)
- **Destination:** `ci_matrix_reports`
- **Retention:** 90 days
- **Include:** ['R241-15*', 'R241-16*']
- **Exclude:** []
- **Path handling:** primary_only
- **Secrets allowed:** False
- **Runtime files allowed:** False

### art_spec_pytest_logs (pytest_log)
- **Destination:** `pytest_logs`
- **Retention:** 7 days
- **Include:** ['**/pytest.log', '**/.pytest_cache/**', '**/tmp/**/pytest*.log']
- **Exclude:** ['**/audit_trail/**']
- **Path handling:** none
- **Secrets allowed:** False
- **Runtime files allowed:** False
  - ⚠️ pytest logs are temp — only collect if explicitly enabled

### art_spec_junit_xml (junit_xml)
- **Destination:** `junit_reports`
- **Retention:** 14 days
- **Include:** ['**/junit*.xml', '**/test-results/**/*.xml']
- **Exclude:** []
- **Path handling:** none
- **Secrets allowed:** False
- **Runtime files allowed:** False
  - ⚠️ junit xml is optional — requires --junit-xml flag in pytest command

### Report Path Compatibility

- **Primary path:** `C:\Users\win\AppData\Local\Temp\pytest-of-win\pytest-678\test_generate_plan_dry_run_doe0\migration_reports\foundation_audit` (exists: False)
- **Secondary path:** `C:\Users\win\AppData\Local\Temp\pytest-of-win\pytest-678\test_generate_plan_dry_run_doe0\backend\migration_reports\foundation_audit` (exists: False)
- **Path inconsistency:** False
- **Action now:** `report_only`
- **Migration allowed now:** False
- **Deletion allowed now:** False

---

## 4. Threshold Policy / Blocked Actions

### Thresholds

- Foundation fast warning: 30s, blocker: 60s
- Audit fast warning: 15s
- Slow suite warning: 60s
- Safety suite warning: 10s
- Collect-only warning: 10s

### Blocked Actions

- ❌ enabling_real_feishu_send: Feishu send requires explicit opt-in per R241-15F policy
- ❌ network_call: CI stages must not call external services
- ❌ webhook_call: Webhook calls are forbidden in CI environment
- ❌ reading_real_secrets: CI should not read real tokens/secrets from environment
- ❌ runtime_write: Runtime state writes are forbidden in CI
- ❌ action_queue_write: Action queue writes are forbidden in CI
- ❌ auto_fix: Auto-fix is never executed in CI environment
- ❌ gateway_mutation: Gateway state mutations are forbidden in CI
- ❌ audit_jsonl_overwrite_truncate_delete: Audit JSONL must never be modified by CI stages
- ❌ deleting_tests: CI must not delete existing tests
- ❌ skipping_safety_tests: Safety tests (no_network/no_runtime_write/no_secret) must not be skipped
- ❌ reducing_security_coverage: CI must maintain current security coverage level

---

## 5. Implementation Phases

| Phase | Name | Creates Workflow | Blocks Real CI |
|---|---|---|---|
| phase_1 | Design-only Plan | False | True |
| phase_2 | Local Script Dry-run | False | False |
| phase_3 | CI Workflow Draft (disabled) | True | False |
| phase_4 | PR Blocking Fast + Safety | True | True |
| phase_5 | Nightly Slow + Full | True | True |
| phase_6 | Artifact Retention / Report Publishing | False | False |
| phase_7 | Future Sidecar / Gateway Integration Review | False | False |

**Current phase:** phase_1
**Next blocked phase:** phase_2 — Phase 1 is design-only — next phase (phase_2) requires explicit user confirmation to proceed

---

## 6. Validation

- **Valid:** True
- **Errors:** 0
- **Warnings:** 4

  - ⚠️ Artifact spec art_spec_foundation_reports should exclude secret files
  - ⚠️ Artifact spec art_spec_ci_matrix should exclude secret files
  - ⚠️ Artifact spec art_spec_pytest_logs should exclude secret files
  - ⚠️ Artifact spec art_spec_junit_xml should exclude secret files

---

## 7. Policy Flags

- Network call recommended: `False`
- Runtime write recommended: `False`
- Auto-fix recommended: `False`
- Delete tests recommended: `False`
- Skip safety tests recommended: `False`
- Creates real workflow: `False`

---

## 8. Next Steps (R241-16B)

1. Proceed to local script dry-run (`scripts/ci_foundation_check.py`) after explicit confirmation.
2. Validate local script against all 5 stage commands.
3. Document any path or environment differences between local script and GitHub Actions.

---

**Final Determination: R241-16A — PASSED — A**

Design-only phase completed. No real workflow created. No runtime modified.
No audit JSONL written. No network called. No auto-fix executed.