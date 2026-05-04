# R240 Runtime Root Relocation

Date: 2026-04-24

## Objective

Move DeerFlow user-level runtime data from:

- `C:\Users\win\.deerflow`

to the canonical project-local runtime root:

- `E:\OpenClaw-Base\deerflow\.deerflow`

The canonical repository root remains:

- `E:\OpenClaw-Base\deerflow`

## Migration Result

- Source existed before migration: yes
- Destination existed before migration: no
- Files copied: 964
- Bytes copied: 1,369,842
- SHA256 manifest match after copy: yes
- Old source path exists after migration: no
- Frozen old runtime archive exists: yes
- Frozen archive path: `C:\Users\win\.deerflow__MIGRATED_DO_NOT_USE`
- Frozen archive warning file: `README_DO_NOT_USE.txt`

## Runtime Path Policy

Default runtime root is now project-local:

- `E:\OpenClaw-Base\deerflow\.deerflow`

Override remains possible through:

- `DEERFLOW_RUNTIME_ROOT`

Primary helpers:

- `backend/app/runtime_paths.py`
- `backend/src/runtime_paths.ts`
- `backend/src/runtime_paths.mjs`

## Code Reference Closure

Runtime absolute old home references after migration:

- `C:\Users\win\.deerflow`: 0 in runtime code

Known remaining references:

- Historical blueprint/archive text in `openclaw_project`
- Test/scratch/dry-run references that are not part of the active runtime chain
- Project-local `.deerflow` references in runtime path helpers and `.gitignore`/`.dockerignore`

## Verification

- Python runtime path helper resolves to `E:\OpenClaw-Base\deerflow\.deerflow`
- JavaScript runtime path helper resolves to `E:\OpenClaw-Base\deerflow\.deerflow`
- RootGuard Python: PASS
- RootGuard PowerShell: PASS
- Python compile check for touched Python runtime files: PASS
- `npx --no-install tsc --noEmit` still fails because the repository has pre-existing TypeScript errors unrelated to the runtime root relocation.

## Final Status

The former user-level DeerFlow runtime root has been copied into the canonical project root and the original path has been frozen. Active runtime code now resolves DeerFlow runtime state under `E:\OpenClaw-Base\deerflow\.deerflow` by default.
