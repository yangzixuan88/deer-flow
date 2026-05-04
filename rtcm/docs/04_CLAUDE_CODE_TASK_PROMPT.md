# 04｜给 Claude Code 的建议任务提示词

请将仓库中的 `rtcm/` 目录视为 **RTCM 圆桌讨论机制接入规格包**。  
你的目标是在当前工程中完成一个最小可运行 RTCM 骨架。

## 施工要求

1. 先只读理解：
   - `rtcm/docs/*`
   - `rtcm/config/integration_manifest.yaml`

2. 第一阶段只做：
   - config loader
   - prompt loader
   - runtime state initializer
   - project dossier writer
   - minimal round orchestrator skeleton

3. 暂时不要做：
   - 主系统深侵入
   - Feishu 渲染
   - 夜间复盘深链路
   - 替换现有主任务模式

4. 每次改动后必须输出：
   - 改动文件列表
   - 接入点说明
   - 风险说明
   - 回退方式
   - 最小测试方法

5. 所有实现应以：
   - `rtcm/config/*.yaml`
   - `rtcm/prompts/*.md`
   - `rtcm/examples/ai_manju_project/*`
   为准。
