# RTCM 工程包体检报告 v1.1

## 体检结论

上一版工程包 **不建议直接作为最终接入包**。  
主要问题不是语法错误，而是：

1. **配置被简化过头**，和之前确认过的完整设计相比，缺少若干关键字段
2. **Prompt Loader 路径写死到 `./rtcm/examples/...`**，不适合真实接入
3. **样例项目 dossier 不完整**，缺少 schema 中声明的多个文件
4. **若直接交给 Claude Code 开工，容易导致它按“缩减版协议”实现，而不是按我们确认的完整版协议**

---

## 检查结果

### A. 结构检查
- YAML/JSON 语法：通过
- 基本目录结构：通过
- Prompt 数量：通过（10 份）
- 示例可运行：通过（`run_demo.py` 可执行）

### B. 一致性检查
#### 发现 1：`role_registry.final.yaml` 缺少大量我们之前确认的角色字段
上一版只有：
- id
- name
- title
- role_type
- identity
- mission

但之前确认过的完整版本还应有：
- `core_responsibilities`
- `non_responsibilities`
- `personality`
- `default_bias`
- `debate_functions`
- `evidence_preferences`
- `permissions`
- `failure_modes`
- `success_metrics`

#### 发现 2：`agent_registry.rtcm.final.yaml` 缺少运行级字段
上一版缺少：
- `model_policy`
- `hooks`
- `tool_access_profile`
- `crossfire_policy`
- `evidence_ledger`
- `uncertainty_capture`
- `issue_graph`
- `nightly_optimization_hooks`

#### 发现 3：`issue_debate_protocol.final.yaml` 过于简化
缺少：
- `user_intervention_policy`
- `dissent_policy`
- `uncertainty_policy`
- `issue_card_schema` 的完整字段
- `metrics`
- `archival`

#### 发现 4：`prompt_loader_and_assembly_spec.final.yaml` 路径不稳
上一版把：
- `prompt_root`
- `dossier_root`

写死到示例路径。  
真实接入时应改为：
- 相对项目根路径可配置
- 或明确支持 `./rtcm/` 与 `~/.deerflow/roundtable/` 两种安装位

#### 发现 5：`project_dossier_schema.final.yaml` 与样例不一致
Schema 声明了以下文件，但样例缺失：
- `council_log.jsonl`
- `hypothesis_board.json`
- `linked_assets.json`
- `acceptance_log.jsonl`
- `resume_index.json`
- `workflow_optimization_suggestions.json`

#### 发现 6：`runtime_orchestrator_spec.final.yaml` 与前面确认过的运行编排相比过短
缺少：
- `runtime_state`
- `issue_execution_loop`
- `supervisor_runtime_checks`
- `user_intervention_runtime`
- `artifact_persistence`
- `learning_handoff`
- `feishu_runtime_hooks`
- `failure_handling`
- `metrics`

#### 发现 7：`feishu_rendering_spec.final.yaml` 过于瘦身
缺少：
- 具体 card templates
- status badges
- user action mapping
- visibility policy
- safety rendering rules
- archive rendering

---

## 修复策略

本次 v1.1 修正版已做：

1. 恢复并补齐配置字段
2. 修正 Prompt Loader 路径策略
3. 补全样例 dossier 缺失文件
4. 增强运行编排规范
5. 增强 Feishu 渲染规范
6. 保留 VSCode + Claude Code 的接入说明和任务提示词
7. 新增 `validate_bundle.py` 作为工程包自检脚本

---

## 现在这版是否可直接用于接入

**可以。**

但仍建议接入顺序保持不变：

1. 先只读理解
2. 先做 loader / runtime state / dossier writer
3. 再做 round orchestrator
4. 再接 Feishu
5. 再接夜间复盘
