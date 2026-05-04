# R240-0D Final Root Closure

Audit date: 2026-04-24
Scope: old-root physical freeze retry, RootGuard.ps1 Unicode repair, final root uniqueness verification.

## 1. 旧目录物理冻结结果

Initial cwd:

```text
E:\OpenClaw-Base\codex
```

The working directory was not inside the old root or the migrated frozen root. Rename operations were executed from:

```text
E:\OpenClaw-Base
```

Physical freeze attempt:

```powershell
Rename-Item -LiteralPath "E:\OpenClaw-Base\openclaw超级工程项目" -NewName "openclaw超级工程项目__MIGRATED_DO_NOT_USE"
```

Result:

```text
RENAME_OK=False
ERROR=The process cannot access the file because it is being used by another process.
```

Python `os.rename` was also attempted from `E:\OpenClaw-Base`, but did not complete the freeze. A final retry with `Rename-Item` also failed with the same file-in-use error.

Final physical state:

| Check | Result |
|---|---:|
| `E:\OpenClaw-Base\openclaw超级工程项目` exists | yes |
| `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE` exists | no |
| Frozen `README_DO_NOT_USE.txt` exists | no |
| Frozen README contains explicit do-not-use warning | not verifiable |

Likely occupying process:

| PID | Process | Window title |
|---:|---|---|
| 29576 | `Code.exe` | `R240-0B_FUSION_VERIFICATION.md - openclaw超级工程项目 - Visual Studio Code` |

Other relevant visible processes:

| PID | Process | Window title |
|---:|---|---|
| 31000 | `Codex.exe` | `Codex` |
| 17956 | `msedge.exe` | `Branch · OpenClaw改造计划分析 和另外 23 个页面 - 个人 - Microsoft Edge` |

Assessment: the old directory is still opened by VS Code, so physical freeze is blocked. No forced process termination was performed.

## 2. RootGuard.ps1 修复说明

File repaired:

```text
E:\OpenClaw-Base\deerflow\scripts\root_guard.ps1
```

Changes made:

- Replaced fragile `-like "$FORBIDDEN_ROOT*"` path matching.
- Removed direct Chinese path literals from the script body to avoid Windows PowerShell UTF-8-without-BOM mojibake.
- Built `openclaw超级工程项目` from Unicode codepoints.
- Added explicit prefixes for both old original root and frozen migrated root:
  - `E:\OpenClaw-Base\openclaw超级工程项目`
  - `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE`
- Added path normalization using `Resolve-Path` and `[System.IO.Path]::GetFullPath()`.
- Added directory-boundary-safe comparison using `[System.StringComparison]::OrdinalIgnoreCase`.
- Outputs are now explicit:
  - `ROOT_OK`
  - `FORBIDDEN`
  - `WRONG_ROOT`

## 3. RootGuard.py / ps1 双脚本验证结果

In `E:\OpenClaw-Base\deerflow`:

| Command | Exit code | Result |
|---|---:|---|
| `python scripts\root_guard.py` | 0 | PASS, RootGuard OK |
| `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1` | 0 | PASS, `ROOT_OK` |

In still-existing old original directory `E:\OpenClaw-Base\openclaw超级工程项目`:

| Command | Exit code | Result |
|---|---:|---|
| `python E:\OpenClaw-Base\deerflow\scripts\root_guard.py` | 1 | FAIL as expected, `FORBIDDEN` |
| `powershell -ExecutionPolicy Bypass -File E:\OpenClaw-Base\deerflow\scripts\root_guard.ps1` | 1 | FAIL as expected, `FORBIDDEN` |

Wrong-root control check in `E:\OpenClaw-Base`:

| Command | Exit code | Result |
|---|---:|---|
| `powershell -ExecutionPolicy Bypass -File E:\OpenClaw-Base\deerflow\scripts\root_guard.ps1` | 1 | FAIL as expected, `WRONG_ROOT` |

Frozen old directory validation could not be performed because `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE` does not exist.

## 4. 旧路径最终扫描结果

Scan root:

```text
E:\OpenClaw-Base\deerflow
```

Search terms:

- `openclaw超级工程项目`
- `OpenClaw超级工程项目`
- `E:\OpenClaw-Base\openclaw超级工程项目`
- `E:/OpenClaw-Base/openclaw超级工程项目`

Classification counts:

| Category | Count |
|---|---:|
| `runtime_old_path_references_count` | 0 |
| `expected_guard_references_count` | 1 |
| `migration_archive_references_count` | 632 |

Notes:

- The remaining expected guard keyword match is in `scripts\root_guard.py`.
- `root_guard.ps1` now constructs the old Chinese directory name using Unicode codepoints, so it is not matched by the literal keyword scan.
- Non-runtime matches are migration reports, R240 reports, historical docs, README/test-plan examples, and source comments referencing `OpenClaw超级工程项目.docx`; these are not active runtime path references.

## 5. VSCode workspace 验证结果

Workspace:

```text
E:\OpenClaw-Base\deerflow\OpenClaw-DeerFlow.code-workspace
```

| Check | Result |
|---|---:|
| Contains `deerflow-main` | yes |
| Contains `openclaw_project` | yes |
| References old Chinese directory | no |
| `terminal.integrated.cwd` | `E:\OpenClaw-Base\deerflow` |

VSCode settings:

```text
E:\OpenClaw-Base\deerflow\.vscode\settings.json
```

| Check | Result |
|---|---:|
| `terminal.integrated.cwd` points to deerflow | yes |
| References old Chinese directory | no |
| `openclaw_project` use | `typescript.tsdk`, internal deerflow subproject reference |

## 6. 主根最小运行态验证结果

In `E:\OpenClaw-Base\deerflow`:

| Check | Result |
|---|---|
| cwd | `E:\OpenClaw-Base\deerflow` |
| `package.json` name | `openclaw` |
| `package.json` version | `1.0.0` |
| `tsconfig.json` path | `E:\OpenClaw-Base\deerflow\tsconfig.json` |
| `compilerOptions.rootDir` | `./backend/src` |
| `compilerOptions.outDir` | `./backend/dist` |
| `npm run` | exit code 0, listed scripts only |
| `npx --no-install tsc --version` | `Version 5.9.3`, exit code 0 |

No destructive command was executed and no dependency was installed.

## 7. 最终判定

Final decision: **B. 主根逻辑唯一，但仍有一个收口阻塞**.

Blocking point:

```text
E:\OpenClaw-Base\openclaw超级工程项目
```

still exists because it is locked by another process, most likely VS Code PID 29576 whose title indicates it is opened on the old directory.

All non-physical checks that could be completed passed:

| Requirement | Status |
|---|---|
| `runtime_old_path_references_count = 0` | pass |
| `unresolved_conflicts = 0` | pass |
| `root_guard.py` deerflow PASS | pass |
| `root_guard.ps1` deerflow PASS | pass |
| `root_guard.py` old original dir FAIL | pass |
| `root_guard.ps1` old original dir FAIL | pass |
| VSCode deerflow workspace does not point to old Chinese directory | pass |
| `package.json` / `tsconfig.json` read from deerflow root | pass |
| Old original directory absent | fail |
| Frozen directory exists | fail |

Required next manual action:

1. Close the VS Code window titled `R240-0B_FUSION_VERIFICATION.md - openclaw超级工程项目 - Visual Studio Code`, or reopen VS Code only through `E:\OpenClaw-Base\deerflow\OpenClaw-DeerFlow.code-workspace`.
2. Re-run:

```powershell
Rename-Item -LiteralPath "E:\OpenClaw-Base\openclaw超级工程项目" -NewName "openclaw超级工程项目__MIGRATED_DO_NOT_USE"
```

3. Then re-run RootGuard in the frozen directory.

Until that rename succeeds, physical root uniqueness must not be declared complete.
