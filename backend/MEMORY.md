# MEMORY.md - Long-term Memory

## 关于用户

- **用户名称**：杨先生
- **时区**：Asia/Shanghai

## 项目历史

### 2026-04-17 LarkSuite CLI 集成完成 ✅

**LarkSuite CLI 全面接入 DeerFlow 项目**

- **Phase 1**: lark-cli 安装和 Bot 凭据配置
- **Phase 2**: LarkCLIAdapter 开发 + 22 个 SKILL.md 文件
- **Phase 3**: 协调器意图识别与路由
- **Phase 4**: 集成测试
- **Phase 5**: 文档

**技术要点：**
- lark-cli v1.0.13 使用 `+command` 语法
- `USER_ONLY_COMMANDS`: 联系人、Wiki 等 API 需要 `--as user`
- 任务创建需要 `task:task:write` 权限

**文件位置：**
- 适配器: `backend/src/domain/m11/adapters/lark_cli_adapter.ts`
- 协调器: `backend/src/domain/m04/coordinator.ts` (LARKSUITE 路由)
- 技能: `skills/custom/larksuite/` (22个技能文件)

### 2026-04-12 OpenClaw 超级工程项目 Phase 11 完成 ✅

**卧底模式 (Undercover Mode)**
- 文件: `undercover_mode.py`
- 4个卧底等级: HIDDEN, DISGUISED, WATCHDOG, GHOST
- 威胁检测器 (prompt injection, data exfiltration, privilege escalation等)

**完整命令系统**
- 命令数量: 89个命令
- 分类: file操作、git、session、config、developer、security等

### 架构转移完成 (2026-04-17)

从 OpenClaw 超级工程项目转移到 DeerFlow 的构建产物：

| 组件 | 状态 |
|------|------|
| `backend/src/domain/m04/` | ✅ 完整 (17个文件) |
| `backend/src/domain/m11/` | ✅ 完整 (8个文件) |
| `backend/src/infrastructure/` | ✅ 全部更新 |
| `skills/custom/larksuite/` | ✅ 24个技能文件 |

## 近期进展

### Phase 12 完成
- 卧底模式 (Undercover Mode) 已完成并集成
- 命令系统89个命令完成注册和执行器

### Phase 13 进行中
- 记忆系统数据质量审计

## 项目状态

- **LarkSuite CLI 集成**: 核心功能 100% 完成
- **权限配置**: task:task:write 已添加
- **Skills**: 22个飞书技能已就绪

## 技术债务

- 部分飞书 API 需要用户身份认证 (`--as user`)，这是飞书安全策略
- 联系人搜索 Wiki 搜索需要用户授权

## 任务队列规范

- 每次任务完成后必须更新相关状态
- 自主改进任务生成后立即执行，不堆积
