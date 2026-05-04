# R240-0F Post-Reboot Physical Freeze Success

Audit date: 2026-04-24
Scope: post-reboot retry after Windows handle blockage.

## 1. handle64.exe Location Check

`handle64.exe` and `handle.exe` were not found in PATH or the checked common locations:

- `C:\Sysinternals`
- `C:\Tools\Sysinternals`
- `C:\Program Files\Sysinternals`
- `C:\Users\win\Downloads`
- `E:\OpenClaw-Base\tools`
- `E:\OpenClaw-Base\bin`

The tool was not needed after reboot because the directory rename succeeded.

## 2. Physical Rename Result

Rename was executed from:

```text
E:\OpenClaw-Base
```

Command:

```powershell
Rename-Item -LiteralPath "E:\OpenClaw-Base\openclaw超级工程项目" -NewName "openclaw超级工程项目__MIGRATED_DO_NOT_USE"
```

Result:

```text
RENAME_OK=True
RENAME_METHOD=PowerShell Rename-Item
OLD_EXISTS=False
FROZEN_EXISTS=True
```

## 3. Frozen Directory State

| Check | Result |
|---|---:|
| `E:\OpenClaw-Base\openclaw超级工程项目` absent | yes |
| `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE` exists | yes |
| `README_DO_NOT_USE.txt` exists in frozen directory | yes |
| README contains explicit do-not-use/migrated warning | yes |

## 4. RootGuard Repair and Verification

`root_guard.py` was repaired after the successful rename so it explicitly forbids both:

- `E:\OpenClaw-Base\openclaw超级工程项目`
- `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE`

Both RootGuard scripts now avoid fragile Chinese-path literals for the forbidden directory name and construct it from Unicode codepoints.

In `E:\OpenClaw-Base\deerflow`:

| Command | Exit code | Result |
|---|---:|---|
| `python scripts\root_guard.py` | 0 | PASS, `ROOT_OK` |
| `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1` | 0 | PASS, `ROOT_OK` |

In `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE`:

| Command | Exit code | Result |
|---|---:|---|
| `python E:\OpenClaw-Base\deerflow\scripts\root_guard.py` | 1 | FAIL as expected, `FORBIDDEN` |
| `powershell -ExecutionPolicy Bypass -File E:\OpenClaw-Base\deerflow\scripts\root_guard.ps1` | 1 | FAIL as expected, `FORBIDDEN` |

In `E:\OpenClaw-Base`:

| Command | Exit code | Result |
|---|---:|---|
| `python E:\OpenClaw-Base\deerflow\scripts\root_guard.py` | 1 | FAIL as expected, outside root |
| `powershell -ExecutionPolicy Bypass -File E:\OpenClaw-Base\deerflow\scripts\root_guard.ps1` | 1 | FAIL as expected, `WRONG_ROOT` |

## 5. Final Old-Path Scan

Scan root:

```text
E:\OpenClaw-Base\deerflow
```

Search terms:

- `openclaw超级工程项目`
- `E:\OpenClaw-Base\openclaw超级工程项目`
- `E:/OpenClaw-Base/openclaw超级工程项目`

Classification counts:

| Category | Count |
|---|---:|
| `runtime_old_path_references_count` | 0 |
| `expected_guard_references_count` | 0 |
| `migration_archive_references_count` | 678 |

Unresolved conflict markers:

```text
unresolved_conflicts = 0
```

## 6. Workspace and Runtime Verification

Workspace:

| Check | Result |
|---|---:|
| Contains `deerflow-main` | yes |
| Contains `openclaw_project` | yes |
| References old Chinese directory | no |
| `terminal.integrated.cwd` | `E:\OpenClaw-Base\deerflow` |

VSCode settings:

| Check | Result |
|---|---:|
| `terminal.integrated.cwd` points to deerflow | yes |
| References old Chinese directory | no |
| `openclaw_project` use | internal TypeScript SDK path |

Runtime light check:

| Check | Result |
|---|---|
| cwd | `E:\OpenClaw-Base\deerflow` |
| `package.json` name/version | `openclaw` / `1.0.0` |
| `tsconfig.json` `rootDir` / `outDir` | `./backend/src` / `./backend/dist` |
| `npm run` | exit code 0, listed scripts only |
| `npx --no-install tsc --version` | `Version 5.9.3`, exit code 0 |

## 7. Final Decision

Final decision: **A. 主根唯一性物理 + 逻辑 + 运行态全部完成**.

All required conditions are satisfied:

| Requirement | Status |
|---|---|
| Old original directory absent | pass |
| Frozen migrated directory exists | pass |
| `runtime_old_path_references_count = 0` | pass |
| `unresolved_conflicts = 0` | pass |
| `root_guard.py` deerflow PASS | pass |
| `root_guard.ps1` deerflow PASS | pass |
| `root_guard.py` frozen dir FAIL | pass |
| `root_guard.ps1` frozen dir FAIL | pass |
| Workspace/config do not point to old directory | pass |
| `package.json` / `tsconfig.json` read from deerflow root | pass |

The only real project root is now:

```text
E:\OpenClaw-Base\deerflow
```
