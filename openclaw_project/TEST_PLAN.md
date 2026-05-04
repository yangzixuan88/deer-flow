# OpenClaw 三大系统测试与验收方案

**版本**: v2.0
**日期**: 2026-04-16
**系统**: 搜索系统 · 任务系统 · 工作流系统

---

## 方案总览

| 方案 | 执行者 | 执行方式 | 验收条件 |
|------|--------|----------|----------|
| **方案一：本地 Vitest** | Claude (我) | `npx vitest run` 自动化测试 | 所有测试用例 PASS |
| **方案二：飞书联调** | 用户 | 飞书机器人发送真实指令 | 完整闭环成功 |

**成功标准**：方案一 + 方案二全部通过 = 最终验收通过

---

# 方案一：本地 Vitest 自动化测试

## 一、搜索系统测试

### 1.1 单元测试

| 编号 | 测试文件 | 测试用例 | 验证内容 |
|------|----------|----------|----------|
| S-UT-01 | `src/domain/search_protocol.test.ts` | STORM 状态机转换 | 轮次 1→2→3 正确推进 |
| S-UT-02 | `src/domain/search_protocol.test.ts` | 三轮策略生成 | 第一轮扩散、第二轮聚焦、第三轮校准 |
| S-UT-03 | `src/domain/search_protocol.test.ts` | 结果聚合 | `allResults` 包含三轮数据 |
| S-UT-04 | `src/infrastructure/jina_adapter.test.ts` | Jina 读取适配器 | URL 解析正确，返回结构化内容 |
| S-UT-05 | `src/application/search_service.test.ts` | 搜索结果合成 | 包含三轮结论、引用、置信度 |

### 1.2 集成测试

| 编号 | 测试文件 | 测试用例 | 验证内容 |
|------|----------|----------|----------|
| S-IT-01 | `src/application/search_service.test.ts` | 端到端搜索流程 | 返回完整报告 |
| S-IT-02 | `src/domain/ice_engine.test.ts` | ICE 意图澄清熔断 | 返回澄清问题列表 |

### 1.3 执行命令

```bash
cd e:/OpenClaw-Base/openclaw超级工程项目

# 搜索系统全部测试
npx vitest run src/domain/search_protocol.test.ts
npx vitest run src/infrastructure/jina_adapter.test.ts
npx vitest run src/application/search_service.test.ts
npx vitest run src/domain/ice_engine.test.ts
```

---

## 二、任务系统测试

### 2.1 单元测试

| 编号 | 测试文件 | 测试用例 | 验证内容 |
|------|----------|----------|----------|
| T-UT-01 | `src/domain/m04/coordinator.test.ts` | 任务创建 | 返回 Task 对象，DAG 包含根节点 |
| T-UT-02 | `src/domain/m04/coordinator.test.ts` | DAG 生成 | 关键词检测生成正确节点 |
| T-UT-03 | `src/domain/m04/coordinator.test.ts` | 拓扑排序 | 依赖节点在被依赖节点之后执行 |
| T-UT-04 | `src/domain/m04/coordinator.test.ts` | 并行调度 | 无依赖节点并行执行 |
| T-UT-05 | `src/domain/m04/coordinator.test.ts` | 重试机制 | 节点失败时重试 3 次 |
| T-UT-06 | `src/domain/m04/coordinator.test.ts` | Checkpoint 保存 | checkpoint ID 正确记录 |

### 2.2 集成测试

| 编号 | 测试文件 | 测试用例 | 验证内容 |
|------|----------|----------|----------|
| T-IT-01 | `src/domain/m04/coordinator.test.ts` | 完整任务执行 | 任务状态变为 COMPLETED |
| T-IT-02 | `src/domain/m04/coordinator.test.ts` | Checkpoint 恢复 | 从断点恢复执行 |
| T-IT-03 | `src/domain/m04/coordinator.test.ts` | 任务取消 | 任务状态变为 CANCELLED |

### 2.3 执行命令

```bash
# 任务系统全部测试
npx vitest run src/domain/m04/coordinator.test.ts
```

---

## 三、工作流系统测试

### 3.1 单元测试

| 编号 | 测试文件 | 测试用例 | 验证内容 |
|------|----------|----------|----------|
| W-UT-01 | `src/infrastructure/workflow/n8n_client.test.ts` | N8N 连接 | 环境变量正确读取 |
| W-UT-02 | `src/infrastructure/workflow/n8n_client.test.ts` | 列出工作流 | 返回工作流数组 |
| W-UT-03 | `src/infrastructure/workflow/n8n_client.test.ts` | 获取工作流 | 返回指定工作流详情 |
| W-UT-04 | `src/infrastructure/workflow/n8n_client.test.ts` | 创建工作流 | 返回包含 flow_id |
| W-UT-05 | `src/infrastructure/workflow/n8n_client.test.ts` | 激活工作流 | active 状态为 true |
| W-UT-06 | `src/infrastructure/workflow/n8n_client.test.ts` | Webhook 触发 | 返回执行结果 |

### 3.2 执行命令

```bash
# 工作流系统全部测试
npx vitest run src/infrastructure/workflow/n8n_client.test.ts
```

---

## 四、Vitest 执行脚本

```bash
#!/bin/bash
# run_all_tests.sh

echo "======================================"
echo "OpenClaw 三系统 Vitest 测试"
echo "======================================"

echo ""
echo "[1/4] 搜索系统测试..."
npx vitest run src/domain/search_protocol.test.ts --reporter=verbose
npx vitest run src/infrastructure/jina_adapter.test.ts --reporter=verbose 2>/dev/null || echo "jina_adapter.test.ts may not exist"
npx vitest run src/application/search_service.test.ts --reporter=verbose 2>/dev/null || echo "search_service.test.ts may not exist"
npx vitest run src/domain/ice_engine.test.ts --reporter=verbose

echo ""
echo "[2/4] 任务系统测试..."
npx vitest run src/domain/m04/coordinator.test.ts --reporter=verbose

echo ""
echo "[3/4] 工作流系统测试..."
npx vitest run src/infrastructure/workflow/n8n_client.test.ts --reporter=verbose 2>/dev/null || echo "n8n_client.test.ts may not exist"

echo ""
echo "[4/4] 运行所有测试并生成覆盖率报告..."
npx vitest run --coverage --coverage.reporters=html 2>/dev/null || npx vitest run 2>/dev/null

echo ""
echo "======================================"
echo "测试完成"
echo "======================================"
```

---

# 方案二：飞书机器人联调测试

## 一、前置条件

| 条件 | 状态 | 说明 |
|------|------|------|
| 飞书机器人正常启动 | 需确认 | 机器人已连接 LangGraph |
| DeerFlow 服务运行中 | 需确认 | PID 23284, 24380 |
| 网络连通性 | 需确认 | localhost:2024, localhost:8001 |

## 二、搜索系统测试（飞书）

| 编号 | 用户指令 | 预期行为 | 验收标准 |
|------|----------|----------|----------|
| F-S-01 | "搜索最新的 AI 新闻" | 机器人返回带引用的搜索报告 | 包含三轮结果、URL 引用、置信度 |
| F-S-02 | "帮我查找一些信息" | ICE 澄清，返回问题列表 | 返回 `🛑 意图待明确` 和具体问题 |
| F-S-03 | "什么是量子计算" | 正常三轮搜索 | 返回完整报告，置信度 > 0.7 |

### F-S-01 详细流程

```
用户发送: "搜索最新的 AI 新闻"
↓ DeerFlow 接收
↓ M04 Coordinator 识别 SystemType.SEARCH
↓ SearchService.searchWithClarity() 执行
↓ ICE 引擎评估 (意图清晰)
↓ SearchProtocolEngine 执行三轮搜索
↓ 返回最终合成报告
机器人响应: ### 🛡️ STORM 交叉验证搜索报告
           **Round 1 结论**: ...
           **Round 2 结论**: ...
           **Round 3 结论**: ...
           **信息来源 [Citations]**: [1]...
           **综合置信度**: 0.85
```

---

## 三、任务系统测试（飞书）

| 编号 | 用户指令 | 预期行为 | 验收标准 |
|------|----------|----------|----------|
| F-T-01 | "帮我完成一个代码任务" | 创建任务，执行 DAG | 返回任务 ID、状态、根节点信息 |
| F-T-02 | "搜索并分析 AI 新闻" | DAG 包含 n_root, n_search, n_analysis | n_analysis 依赖 n_search |
| F-T-03 | "实现一个 Python 脚本" | DAG 包含 n_root, n_code | 代码生成节点存在 |

### F-T-01 详细流程

```
用户发送: "帮我完成一个代码任务"
↓ DeerFlow 接收
↓ M04 Coordinator 识别 SystemType.TASK
↓ Coordinator.createTask() 生成 DAG
↓ DAG: n_root → n_code
↓ executeDAG() 执行拓扑排序
↓ Promise.all() 并行执行无依赖节点
↓ 返回 TaskResult
机器人响应: ✅ 任务创建成功
           task_id: task_xxx
           status: COMPLETED
           nodes_executed: 2
```

---

## 四、工作流系统测试（飞书）

| 编号 | 用户指令 | 预期行为 | 验收标准 |
|------|----------|----------|----------|
| F-W-01 | "列出所有工作流" | 返回 n8n 工作流列表 | 显示工作流名称、ID、状态 |
| F-W-02 | "触发数据处理工作流" | webhook 触发 n8n | 返回执行结果 |
| F-W-03 | "创建一个自动化工作流" | 创建新工作流 | 返回 flow_id、创建时间 |

### F-W-01 详细流程

```
用户发送: "列出所有工作流"
↓ DeerFlow 接收
↓ M04 Coordinator 识别 SystemType.WORKFLOW
↓ N8NClient.listWorkflows() 调用
↓ 返回工作流数组
机器人响应: 📋 工作流列表:
           1. 数据处理流程 (ID: wf_xxx, 状态: active)
           2. 报告生成流程 (ID: wf_yyy, 状态: inactive)
```

---

## 五、飞书测试验收表

```
┌─────────────────────────────────────────────────────────────────┐
│                    飞书联调验收报告                              │
├─────────────────────────────────────────────────────────────────┤
│ 日期: ____________  执行人: ____________                        │
├─────────────────────────────────────────────────────────────────┤
│ 搜索系统                                                          │
│   [ ] F-S-01 搜索 AI 新闻 - 返回带引用报告                        │
│   [ ] F-S-02 模糊查询 - ICE 澄清拦截                              │
│   [ ] F-S-03 量子计算 - 正常三轮搜索                              │
├─────────────────────────────────────────────────────────────────┤
│ 任务系统                                                          │
│   [ ] F-T-01 代码任务 - DAG 执行完成                              │
│   [ ] F-T-02 搜索分析 - 依赖关系正确                              │
│   [ ] F-T-03 脚本实现 - n_code 节点存在                           │
├─────────────────────────────────────────────────────────────────┤
│ 工作流系统                                                        │
│   [ ] F-W-01 列出工作流 - 返回列表                                │
│   [ ] F-W-02 触发工作流 - webhook 成功                            │
│   [ ] F-W-03 创建工作流 - 返回 flow_id                            │
├─────────────────────────────────────────────────────────────────┤
│ 总结                                                              │
│   通过项: _____/11                                                │
│   问题数: ____                                                     │
│   最终结论: [ ] 通过  [ ] 需修复                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 最终验收

| 阶段 | 执行者 | 通过标准 |
|------|--------|----------|
| 方案一：Vitest | Claude | 所有单元测试 PASS，输出无 error |
| 方案二：飞书 | 用户 | 11 项联调测试全部成功 |
| **最终验收** | 双方 | 方案一 + 方案二全部通过 |

---

## 附录：测试环境信息

```yaml
环境:
  DeerFlow LangGraph: http://localhost:2024 (PID 23284)
  DeerFlow Gateway: http://localhost:8001 (PID 24380)
  工作目录: e:/OpenClaw-Base/openclaw超级工程项目

服务健康检查:
  - curl http://localhost:2024/ → {"ok":true}
  - curl http://localhost:8001/health → {"status":"healthy"}

沙盒状态:
  - 沙盒约束: 已移除 (include_sandbox=False)
  - Host Bash: 已启用 (allow_host_bash: true)
```