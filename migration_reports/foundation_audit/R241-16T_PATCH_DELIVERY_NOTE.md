# R241-16T Patch Delivery Note

## Source Commit

- **Commit**: `94908556cc2ca66c219d361f424954945eee9e67`
- **Message**: Add manual foundation CI workflow
- **Changed Files**: `.github/workflows/foundation-manual-dispatch.yml`

## Artifact Paths

- **Patch**: `migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch`
  - SHA256: `3f9d456c201e4155787595ba18c45a06425264b6e1b6342289a3d4599c7f6fa8`
  - Size: 3277 bytes
- **Bundle**: `migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle`
  - SHA256: `99198cd2a9ae1c93d7302dafa0906dbf97746de515ab775fecb62996988092a6`
  - Size: 1314 bytes

## Safety Notes

- `workflow_dispatch` trigger only — no PR/push/schedule triggers
- No secrets, tokens, or webhook URLs included in patch
- No auto-fix or runtime write operations
- Only applies to `.github/workflows/foundation-manual-dispatch.yml`
- Safe to share as a code review artifact

## Pre-Apply Verification

**Dry-run first (does not modify working tree):**
```bash
cd <repo-root>
git apply --check migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch
```

## Apply Instructions

**Apply the patch:**
```bash
git am < migration_reports/foundation_audit/R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch
```

## Post-Apply Verification

**Verify the patch applied correctly:**
```bash
git diff-tree --no-commit-id --name-only -r 94908556cc2ca66c219d361f424954945eee9e67
git ls-tree -r 94908556cc2ca66c219d361f424954945eee9e67 -- .github/workflows/foundation-manual-dispatch.yml
git ls-tree -r HEAD -- .github/workflows/foundation-manual-dispatch.yml
```

## Important Warnings

**Do NOT run GitHub Actions from this patch.**

The workflow uses `workflow_dispatch` and must be manually triggered
on GitHub after the patch is applied and the workflow file is visible
on the remote `origin/main` branch.

Do NOT attempt to push this patch to the remote. The push already failed
with 403 permission denied. This delivery note is for local application
only.

**Apply status**: `unknown`

---
*Generated: 2026-04-26T10:31:43.555696+00:00*