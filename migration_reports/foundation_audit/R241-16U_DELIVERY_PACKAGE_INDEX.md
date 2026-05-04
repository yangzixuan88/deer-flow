# R241-16U Delivery Package Index

**Index ID**: `R241-16U-index`
**Generated**: `2026-04-26T10:33:05.160737+00:00`
**Source Commit**: `94908556cc2ca66c219d361f424954945eee9e67`
**Changed Files**: `.github/workflows/foundation-manual-dispatch.yml`

## Artifact Table

| Role | Path | Size | SHA256 | Required | Safe | Recommended Action |
|------|------|------|--------|----------|------|---------------------|
| patch | R241-16S_FOUNDATION_MANUAL_WORKFLOW.patch | 3277 | `3f9d456c201e4155...` | yes | yes | Review, then apply with `git am` |
| bundle | R241-16S_FOUNDATION_MANUAL_WORKFLOW.bundle | 1314 | `99198cd2a9ae1c93...` | yes | yes | Import via `git bundle` for review |
| manifest | R241-16S_PATCH_BUNDLE_MANIFEST.json | 2530 | `2d0f4df82448f736...` | yes | no | Reference for artifact integrity |
| verification_report | R241-16T_PATCH_BUNDLE_VERIFICATION_RESULT.json | 29333 | `490af52c4d985a37...` | yes | yes | Read before applying patch |
| delivery_note | R241-16T_PATCH_DELIVERY_NOTE.md | 2160 | `4261a8cb9bb898e2...` | yes | yes | Read apply/verify instructions |
| generation_result | R241-16S_PATCH_BUNDLE_GENERATION_RESULT.json | 33283 | `334d407a56640588...` | no | no | Archive |

## Do-Not-Run Warnings

**DO NOT** run `gh workflow run foundation-manual-dispatch.yml`.
The workflow uses `workflow_dispatch` and must be manually triggered
on GitHub after the patch is applied AND the workflow file is visible
on the remote `origin/main` branch.

**DO NOT** push this patch to the remote. The push already failed
with 403 permission denied. This delivery is for local application only.

**Known warning**: `git apply --check` may show 'already exists'
because source commit `94908556` is already in the local tree.
This is expected and does not indicate a problem.