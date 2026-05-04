# 决策记录 (DECISIONS.md)

## 2026-04-13: 集成 OpenCLI 自动化枢纽

### 1. 背景
项目需要一个更强大、标准化且具备“AI 原生”特性的自动化工具链，用于打通 Web 操作、本地 CLI 调用以及桌面应用联动。

### 2. 决策
选择 **jackwener/opencli** 作为 OpenClaw 的核心自动化引擎（Automation Hub）。

### 3. 核心集成路径
- **协议层**: 使用 MCP (Model Context Protocol) 作为 OpenCLI 与 OpenClaw 后端的通信协议。
- **功能层**: 
    - 利用 `opencli operate` 替代/增强现有的 `browser_subagent` 逻辑。
    - 利用 `opencli synthesize` 自动生成符合 OpenClaw 规范的 `SKILL.md`。
- **环境层**: 建立浏览器桥接（Browser Bridge），在保持用户登录态的情况下执行任务。

### 4. 预期收益
- **开发效率**: 网站功能一键转 CLI，减少手工编写适配脚本的工作量。
- **系统稳定性**: 统一工具调用入口，增强沙箱（Sandbox）可控性。
- **用户体验**: 在飞书等渠道实现更复杂的自动化任务交互预览。

---
*记录人: Antigravity*
