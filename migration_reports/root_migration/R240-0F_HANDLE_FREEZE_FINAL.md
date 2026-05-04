# R240-0F Handle Freeze Final

Audit date: 2026-04-24
Scope: Windows handle/location troubleshooting and final physical freeze retry.

## 1. 句柄定位结果

Initial cwd:

```text
E:\OpenClaw-Base\codex
```

The cwd was not inside the old root or frozen target.

Initial directory state:

| Path | Exists |
|---|---:|
| `E:\OpenClaw-Base\openclaw超级工程项目` | yes |
| `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE` | no |

### Method A: Sysinternals handle.exe

| Tool | Available |
|---|---:|
| `handle.exe` | no |
| `handle64.exe` | no |

No Sysinternals handle tool was available in PATH.

### Method B: Windows Restart Manager API

Target registered:

```text
E:\OpenClaw-Base\openclaw超级工程项目
```

Result:

```text
RM_START=0
RM_REGISTER=0
RM_GETLIST_INITIAL=5
RM_NEEDED=0
```

Interpretation: Restart Manager session and resource registration succeeded, but `RmGetList` returned `5` and no process list. This did not identify the lock holder.

### Method B: PowerShell/WMI process scan

Checked process classes:

- `Code.exe`
- `Code Helper.exe`
- `Codex.exe`
- `Claude.exe`
- `powershell.exe`
- `pwsh.exe`
- `cmd.exe`
- `bash.exe`
- `node.exe`
- `python.exe`
- `git.exe`
- `rg.exe`
- `explorer.exe`

Strict scan terms:

- `openclaw超级工程项目`
- `E:\OpenClaw-Base\openclaw超级工程项目`
- `E:/OpenClaw-Base/openclaw超级工程项目`

Result: no persistent candidate process was found whose window title, executable path, or command line pointed to the old directory. Matches observed during scanning were the temporary PowerShell inspection commands themselves.

### Method C: openfiles

`openfiles /local` result:

```text
ERROR: Logged-on user does not have administrative privilege.
```

`openfiles` could not be used for local handle enumeration in this session.

### Remaining reasonable suspects

Because Windows still reports the directory as in use but the checked process command lines/window titles do not expose the holder, the remaining likely sources are:

- Explorer window, preview pane, shell extension, or thumbnail/indexing handle.
- VSCode extension host or TypeScript server with a stale handle after the visible old-root window closed.
- Windows Search indexer or Defender/antivirus scanning the old directory.
- Git/file watcher process not exposing the old path in command line.
- Codex/Claude-related background child process with an inherited or stale handle.
- Terminal process whose cwd is not visible through WMI command-line inspection.

No process was force-killed.

## 2. rename 结果

PowerShell attempt from `E:\OpenClaw-Base`:

```powershell
Rename-Item -LiteralPath "E:\OpenClaw-Base\openclaw超级工程项目" -NewName "openclaw超级工程项目__MIGRATED_DO_NOT_USE"
```

Result:

```text
PS_RENAME_OK=False
PS_ERROR=The process cannot access the file because it is being used by another process.
OLD_EXISTS=True
FROZEN_EXISTS=False
```

Python attempt from `E:\OpenClaw-Base` used UTF-8-safe codepoint construction for the Chinese directory name:

```text
PY_RENAME_OK=False
PY_ERROR=PermissionError(13, '另一个程序正在使用此文件，进程无法访问。')
OLD_EXISTS=True
FROZEN_EXISTS=False
```

## 3. 冻结状态

| Check | Result |
|---|---:|
| Old original directory absent | no |
| Frozen migrated directory exists | no |
| Frozen `README_DO_NOT_USE.txt` exists | no |

Physical freeze is still blocked by a Windows file handle.

## 4. RootGuard 复验结果

In `E:\OpenClaw-Base\deerflow`:

| Command | Exit code | Result |
|---|---:|---|
| `python scripts\root_guard.py` | 0 | PASS, RootGuard OK |
| `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1` | 0 | PASS, `ROOT_OK` |

In still-existing old original directory `E:\OpenClaw-Base\openclaw超级工程项目`:

| Command | Exit code | Result |
|---|---:|---|
| `python E:\OpenClaw-Base\deerflow\scripts\root_guard.py` | 1 | FAIL as expected, forbidden root |
| `powershell -ExecutionPolicy Bypass -File E:\OpenClaw-Base\deerflow\scripts\root_guard.ps1` | 1 | FAIL as expected, `FORBIDDEN` |

Frozen directory RootGuard validation could not be performed because the frozen directory does not exist.

## 5. 旧路径扫描结果

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
| `expected_guard_references_count` | 1 |
| `migration_archive_references_count` | 664 |

Unresolved conflict markers:

```text
unresolved_conflicts = 0
```

Workspace/settings regression check:

| Check | Result |
|---|---:|
| `OpenClaw-DeerFlow.code-workspace` references old directory | no |
| `.vscode\settings.json` references old directory | no |

## 6. 最终判定

Final decision: **B. 主根逻辑唯一，但物理冻结仍被句柄阻塞**.

Pass conditions:

| Requirement | Status |
|---|---|
| `runtime_old_path_references_count = 0` | pass |
| `unresolved_conflicts = 0` | pass |
| `root_guard.py` deerflow PASS | pass |
| `root_guard.ps1` deerflow PASS | pass |
| `root_guard.py` old directory FAIL | pass |
| `root_guard.ps1` old directory FAIL | pass |
| Workspace/config do not reference old directory | pass |

Blocking conditions:

| Requirement | Status |
|---|---|
| Old original directory absent | fail |
| Frozen directory exists | fail |
| RootGuard frozen-directory FAIL verification | blocked because frozen directory is missing |

Unique blocking point:

```text
Windows still holds a file handle on E:\OpenClaw-Base\openclaw超级工程项目.
```

The exact holder was not identified by available non-admin tools. Sysinternals `handle.exe` was unavailable; `openfiles` required admin; Restart Manager did not return a process list; WMI command-line/window-title scanning found no persistent old-root process.

Recommended next safe action:

1. Close Explorer windows, VSCode/Codex/Claude windows, terminals, and background dev servers if acceptable.
2. If possible, use Sysinternals Process Explorer or `handle64.exe` as administrator to search for `openclaw超级工程项目`.
3. If no holder is found, reboot Windows and run the rename before opening editors or terminals:

```powershell
Rename-Item -LiteralPath "E:\OpenClaw-Base\openclaw超级工程项目" -NewName "openclaw超级工程项目__MIGRATED_DO_NOT_USE"
```

Until that rename succeeds, physical root uniqueness must not be declared complete.
