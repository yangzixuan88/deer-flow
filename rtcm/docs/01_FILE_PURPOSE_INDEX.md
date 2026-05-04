# 01｜文件用途索引

## config/

### role_registry.final.yaml
圆桌角色制度规范：
- 主持官
- 监督官
- 8 位议员
- 角色字段、偏见、职责、成功指标

### agent_registry.rtcm.final.yaml
把角色映射为可运行 Agent：
- 固定轮序
- 全员在线
- hooks
- tool access
- crossfire
- nightly hooks

### issue_debate_protocol.final.yaml
议题辩论协议：
提出问题 → 假设 → 搜证 → 方案 → 质疑 → 回应 → 缺口 → 验证设计 → 执行验证 → 裁决 → 收官

### project_dossier_schema.final.yaml
项目档案 schema：
manifest / issue_cards / validation_runs / evidence_ledger / issue_graph / reports / acceptance_log 等

### prompt_loader_and_assembly_spec.final.yaml
定义不同角色如何加载 Prompt、如何拿上下文、如何被 parser 校验

### runtime_orchestrator_spec.final.yaml
定义一次会议运行的真实时序：
- 项目启动
- 议题调度
- 固定发言轮序
- 并行搜证
- 执行租约
- 返会
- 用户验收

### feishu_rendering_spec.final.yaml
定义飞书卡片展示和动作映射

### integration_manifest.yaml
给 Claude Code 的总入口清单

## prompts/
10 份角色 Prompt

## examples/
AI漫剧项目的完整样例 dossier
