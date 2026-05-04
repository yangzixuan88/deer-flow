# M01 DeerFlow 注入方案设计

**版本**: v1.0
**日期**: 2026-04-15
**目标**: 实现 M01 编排引擎与 DeerFlow 2.0 服务的无缝对接

---

## 1. 背景与目标

### 1.1 现状
- M01 编排引擎已完成本地实现（意图分类 → DAG 规划 → 本地 Coordinator 执行）
- `M01Config.deerflowEnabled` 配置存在但未被使用
- DeerFlow 2.0 服务已在 `e:\OpenClaw-Base\deerflow\` 部署，端口 8001

### 1.2 目标
当 `deerflowEnabled = true` 时，将 ORCHESTRATION 路径的 DAG 执行委托给 DeerFlow 服务，而非使用本地 Coordinator。

---

## 2. DeerFlow API 分析

### 2.1 核心端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `POST /api/threads` | 创建执行线程 | 启动新任务 |
| `GET /api/threads/{thread_id}` | 查询线程状态 | 轮询执行进度 |
| `POST /api/threads/{thread_id}/runs` | 触发 DAG 执行 | 提交编排任务 |
| `DELETE /api/threads/{thread_id}` | 清理线程 | 释放资源 |

### 2.2 请求格式（DeerFlow runs）

```typescript
// POST /api/threads/{thread_id}/runs
interface DeerFlowRunRequest {
  input: {
    prompt: string;           // 用户原始输入
    dag_plan: DAGPlan;         // M01 生成的 DAG 计划
    metadata: {
      session_id: string;
      request_id: string;
      priority: string;
    };
  };
  config: {
    recursion_limit: number;  // 默认 100
    checkpoint_threshold: number; // 检查点阈值
  };
}
```

### 2.3 响应格式

```typescript
interface DeerFlowRunResponse {
  run_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  thread_id: string;
  created_at: string;
}
```

---

## 3. 注入点设计

### 3.1 架构图

```
用户输入 → IntentClassifier.classify()
                    │
                    ├─ DIRECT_ANSWER → LLM 直答（不变）
                    ├─ CLARIFICATION → 生成澄清问题（不变）
                    └─ ORCHESTRATION ──┐
                                         │
                          ┌──────────────┴──────────────┐
                          │    deerflowEnabled?          │
                          ├─ false → 本地 Coordinator    │
                          └─ true → DeerFlow HTTP API    │
                                         │                │
                                    POST /api/threads    │
                                    /{thread_id}/runs    │
                                         │                │
                                    轮询状态直至完成    │
                                         │                │
                                    映射结果回本地格式  │
```

### 3.2 修改位置

| 文件 | 修改内容 |
|------|----------|
| `src/domain/m01/types.ts` | 添加 `DeerFlowConfig` 接口、请求/响应类型 |
| `src/domain/m01/deerflow_client.ts` | **新建** - DeerFlow API HTTP 客户端 |
| `src/domain/m01/orchestrator.ts` | 修改 `handleOrchestration()` - 条件路由 |
| `src/domain/m01/mod.ts` | 导出 `deerflowClient` |

---

## 4. 详细实现

### 4.1 DeerFlow 客户端（新增）

```typescript
// src/domain/m01/deerflow_client.ts
export class DeerFlowClient {
  constructor(private config: DeerFlowConfig) {}

  async createThread(): Promise<string> { /* POST /api/threads */ }
  async runTask(threadId: string, plan: DAGPlan, meta: TaskMetadata): Promise<DeerFlowRunResponse> { /* POST /api/threads/{id}/runs */ }
  async getThreadStatus(threadId: string): Promise<ThreadStatus> { /* GET /api/threads/{id} */ }
  async deleteThread(threadId: string): Promise<void> { /* DELETE /api/threads/{id} */ }

  async executeUntilComplete(threadId: string, runId: string, timeoutMs: number): Promise<ExecutionResult> {
    // 轮询直到完成/超时/失败
  }
}
```

### 4.2 编排器修改

```typescript
// orchestrator.ts - handleOrchestration 修改
private async handleOrchestration(request, classification, startTime): Promise<OrchestrationResult> {
  const dagPlan = this.dagPlanner.buildPlan(request);

  if (this.config.deerflowEnabled) {
    // 委托给 DeerFlow
    const result = await this.deerflowClient.execute(dagPlan, {
      session_id: request.sessionId,
      request_id: request.requestId,
    });
    return this.mapDeerFlowResult(result, startTime);
  } else {
    // 本地执行（现有逻辑）
    const completedNodes = await this.executeDAG(dagPlan);
    return { /* 现有格式 */ };
  }
}
```

### 4.3 结果映射

```typescript
// DeerFlow 结果 → 本地 OrchestrationResult
private mapDeerFlowResult(dfResult: DeerFlowExecutionResult, startTime: number): OrchestrationResult {
  return {
    requestId: dfResult.request_id,
    success: dfResult.status === 'completed',
    route: IntentRoute.ORCHESTRATION,
    execution: {
      dagPlan: dfResult.dag_plan,
      completedNodes: dfResult.completed_nodes,
      totalNodes: dfResult.total_nodes,
      duration: dfResult.duration,
    },
    executionTime: Date.now() - startTime,
    error: dfResult.error,
  };
}
```

---

## 5. 错误处理与降级

### 5.1 降级策略

```
DeerFlow 调用失败
       │
       ├─ 网络错误 → 回退到本地 Coordinator 执行
       ├─ 超时 → 回退到本地 Coordinator 执行
       └─ API 错误（4xx）→ 返回错误，不回退
```

### 5.2 超时配置

```typescript
const DEERFLOW_TIMEOUT = 300000; // 5分钟（与 defaultTimeout 一致）
const POLL_INTERVAL = 2000;       // 2秒轮询间隔
```

---

## 6. 飞书 → DeerFlow → OpenClaw 执行路径

```
飞书消息 → MCP Server (route_prompt)
                │
                ↓
         DeerFlow 编排层
         POST /api/threads/{thread_id}/runs
                │
                ↓
         OpenClaw M01 接收任务
         IntentClassifier 分类
                │
                ↓
         本地执行 or DeerFlow 委托
                │
                ↓
         结果返回 → 飞书卡片
```

---

## 7. 配置项

```typescript
// DeerFlow 配置（扩展 M01Config）
interface DeerFlowConfig {
  enabled: boolean;
  host: string;        // 默认 'localhost'
  port: number;        // 默认 8001
  timeoutMs: number;   // 默认 300000
  pollIntervalMs: number; // 默认 2000
}
```

环境变量映射：
- `DEERFLOW_ENABLED=true`
- `DEERFLOW_HOST=localhost`
- `DEERFLOW_PORT=8001`

---

## 8. 测试计划

| 测试 | 描述 | 状态 |
|------|------|------|
| T1 | DeerFlow 客户端连接测试 | 待实现 |
| T2 | 正常委托流程测试 | 待实现 |
| T3 | 降级回本地测试（DeerFlow 不可用） | 待实现 |
| T4 | 超时降级测试 | 待实现 |
| T5 | 结果映射正确性测试 | 待实现 |
