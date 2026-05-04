# OpenClaw 历史遗留问题本 (Unresolved Issues Log)

这份记录用于追踪由环境、网络连接或未来联调阶段才能彻底解决的“隐患盲区”，属于防遗忘备忘录：

## 1. M07 / MCP 插件链路超时崩溃问题 (Network & MCP Bridge)
- **现象记录**：在首次发送飞书资产核验请求时，后台出现 `mcp.shared.exceptions.McpError: Connection closed`。
- **底盘决议**：底层 Node 环境全局注入 `https://registry.npmmirror.com`，同时移除外联超时的 Github 官方版节点，换为国内响应高速源。✅已消除隐患。

## 2. Agent 内部沙盒边界碰撞 (Sandbox Path Restrictions)
- **现象记录**：探针流返回了 `Error: Only files in /mnt/user-data/outputs can be presented: /mnt/skills` 报错。
- **底盘决议**：全面在 `prompt.py` 补充防呆警告，同时创立 `SOUL.md` 大代理人格隔离层，从灵魂深处掐断试图不复制就抛出外部产物的想法。✅已消除隐患。

## 3. 飞书通信密钥与实际资产孤岛 (Feishu Missing Config)
- **现象记录**：网关虽起，但飞书长连接仍在静默状态，缺乏实际配置。
- **底盘决议**：底层 `.env` 网段预留就绪，测试期间应用“大总管环境”联入，验证打通外部连接环境。✅通道已就绪。

## 4. Kokoro TTS / fast-whisper 本地语音模型缺失
- **现象记录**：目前 `uv` 还没有把这些重量级视听矩阵加进虚拟环境中，系统只有文字接口。
- **方案延期**：推后至 MVP 正式版上云环节进行单体容器加装与显存剥离，目前文档中备案归纳。⚠️ 待下版本部署。

---
*注：本手册于全盘终局调试环节逐个歼灭。*
