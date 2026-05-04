# R240-0E Final Physical Root Freeze Verification

Audit date: 2026-04-24
Scope: final physical freeze retry and verification for the old OpenClaw root.

## 1. 旧目录 rename 结果

Initial cwd:

```text
E:\OpenClaw-Base\codex
```

The cwd was not inside the old root or the frozen target. Rename was executed from:

```text
E:\OpenClaw-Base
```

Before rename:

| Path | Exists |
|---|---:|
| `E:\OpenClaw-Base\openclaw超级工程项目` | yes |
| `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE` | no |

PowerShell rename attempt:

```powershell
Rename-Item -LiteralPath "E:\OpenClaw-Base\openclaw超级工程项目" -NewName "openclaw超级工程项目__MIGRATED_DO_NOT_USE"
```

Result:

```text
RENAME_METHOD=PowerShell Rename-Item
RENAME_OK=False
ERROR=The process cannot access the file because it is being used by another process.
```

Python `os.rename` was also attempted from `E:\OpenClaw-Base`, but did not complete the freeze.

Final state after attempts:

| Path | Exists |
|---|---:|
| `E:\OpenClaw-Base\openclaw超级工程项目` | yes |
| `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE` | no |

## 2. 旧目录冻结状态

| Check | Result |
|---|---:|
| Old original directory absent | no |
| Frozen migrated directory exists | no |
| Frozen `README_DO_NOT_USE.txt` exists | no |
| Frozen README explicitly forbids old-dir use | not verifiable |

Physical freeze remains blocked.

## 3. 占用进程检查

Checked process classes:

- `Code.exe`
- `Codex.exe`
- `powershell.exe`
- `pwsh.exe`
- `cmd.exe`
- `bash.exe`
- `node.exe`
- `python.exe`

No visible `Code.exe` window currently reports the old root in its title. The only process command line containing the old-root keyword during the check was the temporary PowerShell inspection command itself.

Relevant visible process:

| PID | Process | Window title | Suspected old-dir occupier |
|---:|---|---|---:|
| 31000 | `Codex.exe` | `Codex` | no |

Assessment: Windows still reports the directory as in use, but the lock holder is not exposed by the checked process command lines/window titles. A stale file handle from an editor, shell, explorer integration, extension host, or background process remains possible.

## 4. RootGuard.py / ps1 双脚本最终复验

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

In `E:\OpenClaw-Base`:

| Command | Exit code | Result |
|---|---:|---|
| `powershell -ExecutionPolicy Bypass -File E:\OpenClaw-Base\deerflow\scripts\root_guard.ps1` | 1 | FAIL as expected, `WRONG_ROOT` |

Frozen directory RootGuard validation:

```text
FROZEN_DIR_MISSING
```

The frozen target does not exist, so final frozen-dir RootGuard validation cannot be completed.

## 5. 旧路径最终扫描结果

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
| `migration_archive_references_count` | 649 |

Unresolved conflict markers:

```text
unresolved_conflicts = 0
```

The single expected guard reference is `scripts\root_guard.py`. The remaining migration/archive matches are reports, conflict archive material, R240 documentation, and historical docs/comments.

## 6. VSCode workspace 最终复验

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

## 7. 主根轻量运行态复验

Executed in:

```text
E:\OpenClaw-Base\deerflow
```

| Check | Result |
|---|---|
| cwd | `E:\OpenClaw-Base\deerflow` |
| `package.json` name | `openclaw` |
| `package.json` version | `1.0.0` |
| `tsconfig.json` `rootDir` | `./backend/src` |
| `tsconfig.json` `outDir` | `./backend/dist` |
| `npm run` | exit code 0, listed scripts only |
| `npx --no-install tsc --version` | `Version 5.9.3`, exit code 0 |

No dependency installation, destructive command, pytest run, or real `queue_consumer` task was executed.

## 8. 最终判定

Final decision: **B. 主根逻辑唯一，但物理冻结仍阻塞**.

Pass conditions:

| Requirement | Status |
|---|---|
| `runtime_old_path_references_count = 0` | pass |
| `unresolved_conflicts = 0` | pass |
| `root_guard.py` deerflow PASS | pass |
| `root_guard.ps1` deerflow PASS | pass |
| `root_guard.py` old original directory FAIL | pass |
| `root_guard.ps1` old original directory FAIL | pass |
| VSCode workspace does not point to old Chinese directory | pass |
| `package.json` / `tsconfig.json` read from deerflow root | pass |

Blocking conditions:

| Requirement | Status |
|---|---|
| `E:\OpenClaw-Base\openclaw超级工程项目` absent | fail |
| `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE` exists | fail |
| RootGuard validation inside frozen directory | blocked because frozen directory is missing |

Unique blocking point:

```text
Rename of E:\OpenClaw-Base\openclaw超级工程项目 is still blocked by a Windows file handle.
```

Next safe action:

1. Close any remaining editor, terminal, Explorer window, extension host, or background tool that may have opened `E:\OpenClaw-Base\openclaw超级工程项目`.
2. Keep only `E:\OpenClaw-Base\deerflow\OpenClaw-DeerFlow.code-workspace` open.
3. Re-run:

```powershell
Rename-Item -LiteralPath "E:\OpenClaw-Base\openclaw超级工程项目" -NewName "openclaw超级工程项目__MIGRATED_DO_NOT_USE"
```

Until the rename succeeds, physical root uniqueness must not be declared complete.
