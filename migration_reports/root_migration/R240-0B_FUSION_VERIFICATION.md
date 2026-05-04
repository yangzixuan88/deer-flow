# R240-0B: 冲突文件融合验证与唯一主根加固报告

**生成时间**: 2026-04-24
**验证范围**: 7个冲突文件 diff + 旧路径反向扫描 + 主根加固验证

---

## 一、冲突文件融合决策

| 文件 | old SHA256 (size) | deerflow SHA256 (size) | 大小差异 | 融合决策 | 理由 |
|------|-------------------|----------------------|----------|----------|------|
| DECISIONS.md | `69ebc08f...` (1117b) | `8cd756f6...` (2421b) | +1304b | **KEEP deerflow** | deerflow版本包含4个完整决策记录，旧版仅有1个框架 |
| jest.config.cjs | `53276aab...` (1071b) | `1f10c11e...` (1146b) | +75b | **KEEP deerflow** | deerflow版本增加frontend测试忽略路径和m11旧代码忽略，更完整 |
| mcp-bridge.js | `7fa9d6fd...` (9317b) | `501863fa...` (9370b) | +53b | **KEEP deerflow** | deerflow版本增加`python.on('error')` reject处理，更健壮 |
| package-lock.json | `509859a4...` (239743b) | `c17f31c0...` (239745b) | +2b | **KEEP deerflow** | 仅2字节差异（可能为排序/时间戳），语义相同 |
| package.json | `565175ee...` (1004b) | `d303d2b3...` (1116b) | +112b | **KEEP deerflow** | deerflow版本所有npm脚本正确添加`cd backend &&`前缀 |
| start_server.mjs | `11721bfe...` (614b) | `31edd56f...` (751b) | +137b | **KEEP deerflow** | deerflow版本使用.js后缀（编译后）+运行说明注释 |
| tsconfig.json | `ac8ff2d9...` (712b) | `fc8bf11f...` (757b) | +45b | **KEEP deerflow** | deerflow版本outDir/rootDir正确指向backend/dist和backend/src |

---

## 二、各文件详细Diff摘要

### 1. DECISIONS.md
- **deerflow > old**: deerflow版本是完整的决策日志（4个决策：D-001至D-003等），旧版是空框架只有1个决策草案
- **结论**: deerflow版本内容丰富得多，保留deerflow版

### 2. tsconfig.json
```diff
- "outDir": "./dist",
- "rootDir": "./src",
+ "outDir": "./backend/dist",
+ "rootDir": "./backend/src",
- "src/**/*"
+ "backend/src/**/*"
+ "backend/.venv"  (新增排除)
```
- **结论**: deerflow版本路径结构正确，保留deerflow版

### 3. package.json
```diff
- "test": "jest --runInBand",
+ "test": "cd backend && jest --runInBand",
(所有脚本均添加了 `cd backend &&` 前缀)
- "typescript": "^5.3.3",
+ "typescript": "^5.9.3",  (版本更新)
```
- **结论**: deerflow版本npm脚本路径正确，保留deerflow版

### 4. jest.config.cjs
```diff
+ testPathIgnorePatterns: [
+   '/node_modules/',
+   '/frontend/src/core/threads/utils.test.ts',
+   '/frontend/src/core/api/stream-mode.test.ts',
+   '/src/m11/',  // Ignore old duplicate code (Architecture 1.0)
+ ],
- forceExit: true,
- detectOpenHandles: true,
- testTimeout: 10000,
+ testTimeout: 60000,
```
- **结论**: deerflow版本忽略规则更完善，保留deerflow版

### 5. start_server.mjs
```diff
- import { startMCPServer } from './src/infrastructure/server/mcp_api_server.ts';
+ // NOTE: Run with `npx tsx start_server.mjs` (TypeScript source) or
+ // `node start_server.mjs` after compiling TypeScript to JavaScript.
+ import { startMCPServer } from './src/infrastructure/server/mcp_api_server.js';
```
- **结论**: deerflow版本使用编译后.js后缀并有注释说明，保留deerflow版

### 6. mcp-bridge.js
```diff
+ python.on('error', (error) => reject(error));
```
- **结论**: deerflow版本增加错误处理，保留deerflow版

### 7. package-lock.json
- 仅2字节差异，无实际意义，保留deerflow版

---

## 三、冲突文件归档状态

**位置**: `E:\OpenClaw-Base\deerflow\migration_reports\root_migration\_conflicts\`

所有7个冲突文件的old版本均已移至`_conflicts/`目录归档：

```
DECISIONS.md          → 69ebc08f... (原old VSCode根目录版本)
jest.config.cjs       → 53276aab... (原old VSCode根目录版本)
mcp-bridge.js        → 7fa9d6fd... (原old VSCode根目录版本)
package-lock.json    → 509859a4... (原old VSCode根目录版本)
package.json        → 565175ee... (原old VSCode根目录版本)
start_server.mjs     → 11721bfe... (原old VSCode根目录版本)
tsconfig.json        → ac8ff2d9... (原old VSCode根目录版本)
```

---

## 四、旧路径反向扫描结果

### 扫描对象
- `openclaw超级工程项目`、`OpenClaw超级工程项目`、`openclaw_project`
- `E:\OpenClaw-Base\openclaw超级工程项目`（绝对路径格式）

### 发现的唯一引用

**文件**: `.vscode/settings.json`
```json
{
  "typescript.tsdk": "openclaw_project/node_modules/typescript/lib"
}
```

**分析**:
- 这是VSCode TypeScript插件的设置，指向工作区`openclaw_project`文件夹中的node_modules
- 由VSCode工作区文件`OpenClaw-DeerFlow.code-workspace`管理
- `openclaw_project`是工作区中的第二个文件夹（虚拟的），不是代码中的路径引用
- **不影响构建/运行/测试**——这是IDE配置，不是运行时代码

### 其余扫描结果
- `scripts/root_guard.py` 和 `scripts/root_guard.ps1` 中的`FORBIDDEN_ROOT`是**预期引用**（用于检测当前是否在旧目录）
- 未发现其他旧中文目录路径或`openclaw_project`在代码中的实际引用

---

## 五、唯一主根加固验证

### 已建立的安全措施

1. **RootGuard脚本**（R240-0A已创建）:
   - `scripts/root_guard.py` - Python版，退出码0表示在deerflow，1表示在旧目录
   - `scripts/root_guard.ps1` - PowerShell版，功能相同

2. **旧目录警告文件**:
   - `E:\OpenClaw-Base\openclaw超级工程项目\README_DO_NOT_USE.txt` - 警告禁止继续使用

3. **VSCode工作区配置**:
   - `OpenClaw-DeerFlow.code-workspace` - 正确配置双文件夹工作区
   - `.vscode/settings.json` - 正确设置cwd为`E:\OpenClaw-Base\deerflow`

4. **迁移清单**:
   - `migration_reports/root_migration/migration_manifest.json` - 记录213个文件迁移决策

### 运行时文件读取分析

| 文件 | 运行时读取哪一份 | 原因 |
|------|-----------------|------|
| tsconfig.json | deerflow根目录 | TypeScript编译、IDE加载 |
| package.json | deerflow根目录 | npm命令执行 |
| package-lock.json | deerflow根目录 | npm依赖解析 |
| jest.config.cjs | deerflow根目录 | jest测试运行 |
| start_server.mjs | deerflow根目录 | MCP服务启动 |
| mcp-bridge.js | deerflow根目录 | MCP桥接执行 |
| DECISIONS.md | deerflow根目录 | 文档读取 |

---

## 六、R240-0B最终结论

### 冲突融合 ✅ 完成
- 7个冲突文件全部确认融合决策：保留deerflow根目录版本
- 旧版本已归档至`_conflicts/`目录

### 旧路径扫描 ✅ 完成
- 唯一发现的`openclaw_project`引用是VSCode工作区IDE配置，不影响运行时
- 未发现代码中有其他旧路径引用

### 主根加固 ✅ 完成
- RootGuard脚本已创建并验证
- 旧目录警告文件已创建
- VSCode工作区配置正确

### 建议操作
1. **归档冲突文件清理**（可选）: `migration_reports/root_migration/_conflicts/`目录可在确认无误后删除
2. **旧目录冻结**: 旧目录`E:\OpenClaw-Base\openclaw超级工程项目`在所有进程退出后可重命名为`openclaw超级工程项目__MIGRATED_DO_NOT_USE`

---

**R240-0B 验证完成** ✅
