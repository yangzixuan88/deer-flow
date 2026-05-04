# M01 编排引擎与 DeerFlow 注入方案

> **编制日期**: 2026-04-15
> **目标**: 实现 M01 编排引擎，作为 OpenClaw 的核心调度层

---

## 1. 现状分析

### 1.1 已有模块
- **M04 (三系统协同)**: 已实现 SearchAdapter、TaskAdapter、WorkflowAdapter
- **M10 (意图澄清)**: 已实现五维清晰度评分和 IntentProfile
- **M11 (执行守护)**: 已实现 gVisor 沙盒和 RiskAssessor

### 1.2 缺失模块
- **M01 (编排引擎)**: 未实现，需要作为系统入口和调度核心

### 1.3 架构定位
```
用户请求
    ↓
┌─────────────────────────────────────┐
│           M01 编排引擎               │
│  ┌─────────────────────────────┐    │
│  │ 意图分类器 (3条路由路径)     │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ DAG 规划器                  │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ SharedContext 管理           │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│           M04 三系统协同           │
│  (Search / Task / Workflow)        │
└─────────────────────────────────────┘
```

---

## 2. 路由决策矩阵

| 输入特征 | 路由路径 | 处理方式 |
|---------|---------|---------|
| 单步、<30字、无需工具 | 路径A: 直答 | LLM 直接回答 |
| 意图模糊、缺参数 | 路径B: 追问 | M10 澄清引擎 |
| 多步骤、需搜索/执行 | 路径C: 编排 | DeerFlow DAG |

---

## 3. 实现计划

### Phase 1: 核心类型定义
```typescript
// src/domain/m01/types.ts
export enum IntentRoute {
  DIRECT_ANSWER = 'direct',      // 路径A
  CLARIFICATION = 'clarify',    // 路径B
  ORCHESTRATION = 'orchestrate'  // 路径C
}

export interface OrchestrationRequest {
  userInput: string;
  intentProfile: IntentProfile;
  context: SharedContext;
}

export interface DAGNode {
  id: string;
  task: string;
  systemType: SystemType;
  dependencies: string[];
  timeout: number;
  expectedOutput: string;
}
```

### Phase 2: 意图分类器
```typescript
// src/domain/m01/intent_classifier.ts
export class IntentClassifier {
  classify(input: string): IntentRoute;
  estimateComplexity(input: string): number; // 1-10
  needsSearch(input: string): boolean;
  needsTools(input: string): boolean;
}
```

### Phase 3: DAG 规划器
```typescript
// src/domain/m01/dag_planner.ts
export class DAGPlanner {
  plan(request: OrchestrationRequest): DAGNode[];
  validateDependencies(nodes: DAGNode[]): boolean;
  estimateDuration(nodes: DAGNode[]): number;
}
```

### Phase 4: 编排器入口
```typescript
// src/domain/m01/orchestrator.ts
export class Orchestrator {
  async execute(request: OrchestrationRequest): Promise<ExecutionResult>;
  private async classifyAndRoute(request: OrchestrationRequest): Promise<IntentRoute>;
  private async buildDAG(request: OrchestrationRequest): Promise<DAGNode[]>;
  private async executeDAG(nodes: DAGNode[]): Promise<ExecutionResult>;
}
```

---

## 4. 验收标准

- [ ] 意图分类准确率 > 85%
- [ ] DAG 规划正确性验证
- [ ] 与 M04 三系统协同正常
- [ ] 路径A/B/C 都能正确路由
- [ ] 单元测试覆盖率 > 80%

---

## 5. 依赖关系

```
M01 (本模块)
├── M10 (意图澄清) - 用于路径B澄清
├── M04 (三系统协同) - DAG 执行
├── M11 (执行守护) - 沙盒执行
└── M06 (记忆架构) - SharedContext
```
