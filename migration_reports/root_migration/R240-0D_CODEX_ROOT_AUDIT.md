# R240-0D Codex Root Audit

Audit date: 2026-04-24
Auditor: Codex independent verification
Scope: read-only verification plus creation of this report file.

## 1. 主目录存在性验证

| Path | Exists | Type |
|---|---:|---|
| `E:\OpenClaw-Base\deerflow` | yes | Directory |
| `E:\OpenClaw-Base\deerflow\openclaw_project` | yes | Directory |
| `E:\OpenClaw-Base\deerflow\OpenClaw-DeerFlow.code-workspace` | yes | File |
| `E:\OpenClaw-Base\deerflow\migration_reports\root_migration` | yes | Directory |
| `E:\OpenClaw-Base\deerflow\scripts\root_guard.py` | yes | File |
| `E:\OpenClaw-Base\deerflow\scripts\root_guard.ps1` | yes | File |

## 2. 旧目录冻结状态

| Path | Exists | Type | Audit meaning |
|---|---:|---|---|
| `E:\OpenClaw-Base\openclaw超级工程项目` | yes | Directory | Old original-name directory still exists. |
| `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE` | no | Missing | Frozen renamed directory not present. |

Result: physical freeze is not complete. Per R240-0D rules, this prevents conclusion A.

## 3. 旧路径反向扫描结果

Scan root: `E:\OpenClaw-Base\deerflow`

Text scan extensions included: `.ts`, `.tsx`, `.js`, `.mjs`, `.cjs`, `.json`, `.md`, `.yml`, `.yaml`, `.ps1`, `.py`, `.txt`, `.code-workspace`, `.toml`, `.ini`, `.env`, `.sh`.

Common generated/vendor directories skipped: `node_modules`, `.git`, `.venv`, `dist`, `build`, `__pycache__`, `.next`, `coverage`.

Classification counts:

| Category | Count | Notes |
|---|---:|---|
| `runtime_old_path_reference_count` | 0 | No active runtime code/config/script reference to the old Chinese root was found. |
| `ide_virtual_reference_count` | 2 | Workspace folder path and VSCode TypeScript SDK path using `openclaw_project`. |
| `expected_guard_reference_count` | 2 | RootGuard forbidden-root constants in `root_guard.py` and `root_guard.ps1`. |
| `migration_archive_reference_count` | 1062 | Migration reports, conflict/archive material, historical docs, README/test-plan references, and report/manifests. |

Observed non-runtime old-root references outside `migration_reports` are documentation/comment references, not active runtime path use:

| File | Finding |
|---|---|
| `backend\src\domain\hooks.ts` | Comment references `OpenClaw超级工程项目.docx`; no executable path use. |
| `backend\src\infrastructure\server\README.md` | README sample args reference old absolute path. |
| `openclaw_project\Mission.md` | Historical guiding-doc link/name. |
| `openclaw_project\TEST_PLAN.md` | Historical test-plan `cd` examples using old root. |
| `openclaw_project\assets\domain_knowledge\react_ui_comparison.md` | Historical archive path. |
| `openclaw_project\docs\DISASTER_RECOVERY_PLAYBOOK.md` | Historical recovery command example. |
| `openclaw_project\docs\hermes_opencli_deep_改造计划.md` | Historical archive filename reference. |
| `openclaw_project\docs\TRI_UNIFIED_AUTOMATION_PLAN.md` | Historical project layout references. |
| `openclaw_project\src\domain\hooks.ts` | Comment references `OpenClaw超级工程项目.docx`; no executable path use. |
| `openclaw_project\src\infrastructure\server\README.md` | README sample args reference old absolute path. |

## 4. 运行态关键文件来源验证

All checked key runtime files exist under the deerflow root.

| File | Exists | SHA256 | Last modified | Contains old Chinese root | Contains hardcoded cwd | References deerflow root |
|---|---:|---|---|---:|---:|---:|
| `package.json` | yes | `D303D2B384D4121D23B6957C9C42E249FA87B11AB16774AF8BC561639C23D698` | `2026-04-17 03:56:43 +08:00` | no | relative `cd backend` scripts only | no |
| `package-lock.json` | yes | `C17F31C0CCFD00AB31DDBE3B0BF65650A1C7BF03CB07F7666C14093058A7B7E2` | `2026-04-17 03:55:51 +08:00` | no | no | no |
| `tsconfig.json` | yes | `FC8BF11F3E6DD5FCDD83262D2810566E47B062440401FBFB152C8707A75F1282` | `2026-04-17 03:57:16 +08:00` | no | no | no |
| `jest.config.cjs` | yes | `1F10C11EB3A91C5B1F3A5ECE12BB4A1A5DA2703174AB3CAC9353ECECA65DEB8A` | `2026-04-17 05:12:27 +08:00` | no | no | no |
| `mcp-bridge.js` | yes | `501863FA0844D05D9D5A8830CA5E3C2E4A694B491D236A2269F5A934EC6B8A96` | `2026-04-17 06:17:02 +08:00` | no | no | no |
| `start_server.mjs` | yes | `31EDD56FA2796CF841247D7BD56E053F081139BCC69E83D4B499E6C367E052C2` | `2026-04-17 06:12:20 +08:00` | no | no | no |

`package.json` contains relative `cd backend` npm scripts. This is not an old-root hardcoded cwd and does not point to the forbidden directory.

## 5. openclaw_project 子项目验证

Path: `E:\OpenClaw-Base\deerflow\openclaw_project`

| Check | Result |
|---|---:|
| Directory exists | yes |
| `package.json` exists | no |
| `tsconfig.json` exists | no |
| `src/` exists | yes |
| `docs/` exists | yes |
| TypeScript / TSX files present | yes, 213 |
| Markdown files present | yes, 213 |
| Config-like files present | yes, 213 |
| Obvious active dependency on old Chinese root | no |

Notes: `openclaw_project` is correctly treated as an internal deerflow subproject directory. Its old-root references are historical docs/comments and README examples, not active runtime configuration.

## 6. 冲突文件状态验证

Conflict archive path: `E:\OpenClaw-Base\deerflow\migration_reports\root_migration\_conflicts`

| Check | Result |
|---|---:|
| `conflict_archive_exists` | yes |
| `archived_conflict_count` | 7 |
| `unresolved_conflicts_count` | 0 |

Archived conflict files present:

| File | Present |
|---|---:|
| `DECISIONS.md` | yes |
| `jest.config.cjs` | yes |
| `mcp-bridge.js` | yes |
| `package-lock.json` | yes |
| `package.json` | yes |
| `start_server.mjs` | yes |
| `tsconfig.json` | yes |

No `unresolved_conflicts` marker file was found.

## 7. RootGuard 验证

In `E:\OpenClaw-Base\deerflow`:

| Command | Exit code | Result |
|---|---:|---|
| `python scripts\root_guard.py` | 0 | PASS, output includes RootGuard OK. |
| `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1` | 0 | PASS, output includes RootGuard OK. |

In frozen directory `E:\OpenClaw-Base\openclaw超级工程项目__MIGRATED_DO_NOT_USE`:

| Check | Result |
|---|---|
| Directory exists | no |
| RootGuard validation | Cannot perform because the frozen directory is absent. |

Supplemental validation in still-existing old original directory `E:\OpenClaw-Base\openclaw超级工程项目`:

| Command | Exit code | Result |
|---|---:|---|
| `python E:\OpenClaw-Base\deerflow\scripts\root_guard.py` | 1 | FAIL as expected, output includes `FORBIDDEN`. |
| `powershell -ExecutionPolicy Bypass -File E:\OpenClaw-Base\deerflow\scripts\root_guard.ps1` | 1 | FAIL as expected, output warns current directory is outside expected root. |

## 8. VSCode 工作区验证

Workspace file: `E:\OpenClaw-Base\deerflow\OpenClaw-DeerFlow.code-workspace`

| Check | Result |
|---|---:|
| `folders` contains `deerflow-main` | yes |
| `folders` contains `openclaw_project` | yes |
| `terminal.integrated.cwd` is `E:\OpenClaw-Base\deerflow` | yes |
| Old Chinese directory used as workspace folder | no |
| Old Chinese directory used as terminal cwd | no |

VSCode settings file: `E:\OpenClaw-Base\deerflow\.vscode\settings.json`

| Check | Result |
|---|---:|
| File exists | yes |
| `terminal.integrated.cwd` is `E:\OpenClaw-Base\deerflow` | yes |
| References old Chinese directory | no |
| `typescript.tsdk` | `openclaw_project/node_modules/typescript/lib` |

The `openclaw_project` references are IDE/subproject references, not old-root references.

## 9. 最小运行态验证

Working directory verification:

| Check | Result |
|---|---|
| Current working directory | `E:\OpenClaw-Base\deerflow` |
| `package.json` read path | `E:\OpenClaw-Base\deerflow\package.json` |
| `package.json` package name | `openclaw` |
| `tsconfig.json` read path | `E:\OpenClaw-Base\deerflow\tsconfig.json` |

`npm run`:

| Check | Result |
|---|---:|
| npm available | yes |
| `npm run` exit code | 0 |
| Behavior | listed scripts only; no lifecycle script was executed. |

Scripts listed: `test`, `test:watch`, `test:coverage`, `test:m04`, `test:m06`, `test:m11`, `test:integration`, `docs`.

TypeScript:

| Command | Exit code | Result |
|---|---:|---|
| `npx --no-install tsc --noEmit` | 2 | TypeScript was available locally, but compile failed with existing project type errors. This is not a root-directory failure. |

`queue_consumer.py`:

| Check | Result |
|---|---|
| File found | `E:\OpenClaw-Base\deerflow\backend\app\m11\queue_consumer.py` |
| Safe command run | `python backend\app\m11\queue_consumer.py --help` |
| Exit code | 0 |
| Note | `--once` would consume and write queue state, so it was not executed. |

## 10. 最终结论

Conclusion: **B. 主根逻辑唯一，但物理冻结未完成**.

Rationale:

| Requirement | Status |
|---|---|
| `E:\OpenClaw-Base\deerflow` exists | pass |
| `openclaw_project` is inside deerflow | pass |
| old original directory does not exist | fail |
| frozen old directory exists | fail |
| `runtime_old_path_reference_count = 0` | pass |
| `unresolved_conflicts_count = 0` | pass |
| RootGuard in deerflow passes | pass |
| RootGuard rejects old original directory | pass |
| VSCode workspace does not reference old Chinese directory | pass |
| key runtime files are present under deerflow root | pass |

Unique blocking point: the old original-name directory still exists and the required frozen rename target does not exist.

Required manual operation:

```powershell
Rename-Item -Path "E:\OpenClaw-Base\openclaw超级工程项目" -NewName "openclaw超级工程项目__MIGRATED_DO_NOT_USE"
```

No file deletion, migration, conflict repair, dependency installation, or `.openclaw` runtime-state modification was performed during this audit.
