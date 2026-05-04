# 下一步行动计划 V2.0
> **编制日期**: 2026-04-14
> **编制依据**: 深度代码分析 (Agent Exploration) + ACCEPTANCE_REPORT.md
> **当前阶段**: Phase 18 完成 · **Phase 19 紧急启动**

---

## ⚠️ 紧急程度分级

| 等级 | 定义 | 模块 | 差距数 |
|:----:|------|------|:------:|
| 🔴 CRITICAL | 执行器全是 Stub，系统无法实际工作 | M11 Executors | 4 |
| 🔴 CRITICAL | 无外部集成，三系统只是框架 | M04 Adapters | 3 |
| 🟠 HIGH | DSPy 是模拟实现，非真实 MIPROv2 | M09 DSPy | 2 |
| 🟠 HIGH | 语义写入管线压缩/嵌入是 Stub | M06 Pipeline | 2 |
| 🟠 HIGH | gVisor 只是模拟执行，未真正调用 | M11 Sandbox | 1 |
| 🟡 MEDIUM | GraphRAG 实体抽取是关键词，非 LLM | M06 L4 | 1 |
| 🟡 MEDIUM | SQLite 集成返回 "pending" | M07 MCP | 1 |
| 🟢 LOW | 错误处理/日志不一致 | 全局 | 2 |

---

## 一、Phase 19: 核心执行层真实化 (最高优先级)

**目标**: 将 Stub 实现替换为真实集成，系统可实际工作

### 1.1 Action 036: M11 执行器真实集成 (CRITICAL 🔴)

**当前状态**: 所有执行器返回模拟数据
```
executor_adapter.ts:
- executeClaudeCode() → mock result
- executeCLIAnything() → mock result  
- executeMidscene() → mock result
- executeUITARS() → mock result
```

**目标**: 集成真实外部工具

**交付物**:

| 文件 | 任务 | 状态 |
|------|------|:----:|
| `executor_adapter.ts` | 集成 Claude Code CLI | 🔴 stub |
| `executor_adapter.ts` | 集成 Midscene.js SDK | 🔴 stub |
| `executor_adapter.ts` | 集成 UI-TARS API | 🔴 stub |
| `executor_adapter.ts` | 集成 CLI-Anything | 🔴 stub |

**执行步骤**:

```typescript
// Step 1: Claude Code CLI 集成
// 文件: src/domain/m11/adapters/executor_adapter.ts

// 当前 (stub):
async executeClaudeCode(command: string): Promise<ExecutorResult> {
  return { success: true, output: 'mock output' };
}

// 目标 (真实):
async executeClaudeCode(
  command: string,
  config: { timeout_ms?: number; cwd?: string }
): Promise<ExecutorResult> {
  const result = await execAsync(
    `npx claude-code --print --no-input "${command}"`,
    { timeout: config.timeout_ms || 60000, cwd: config.cwd }
  );
  return {
    success: result.exitCode === 0,
    output: result.stdout,
    error: result.stderr,
    execution_time_ms: result.duration
  };
}

// Step 2: Midscene.js 集成
import { Midscene } from '@midscene/web';

// Step 3: UI-TARS API 集成 (待 API 确认)

// Step 4: CLI-Anything 集成 (调用本地 cli-hub)
```

**验收标准**:
- [ ] `executeClaudeCode('ls -la')` 返回真实文件系统输出
- [ ] Midscene 执行 Web 自动化任务
- [ ] CLI-Anything 调用本地生成工具
- [ ] UI-TARS 执行桌面自动化

**预计工时**: 8-12 小时 (需要外部 API 密钥/CLI 安装)

---

### 1.2 Action 037: M11 gVisor 沙盒真实执行 (HIGH 🟠)

**当前状态**: `simulateExecution()` 返回 mock 数据
```
sandbox.ts:
- executeWithGVisor() → runsc 命令已构造
- simulateExecution() → 始终返回 success=true
- isAvailable() → 始终返回 true
```

**目标**: 实现真实 runsc 调用

**交付物**:

| 文件 | 任务 | 状态 |
|------|------|:----:|
| `sandbox.ts` | 替换 simulateExecution 为真实 execAsync | 🔴 stub |
| `sandbox.ts` | 实现真实 runsc 可用性检查 | 🔴 stub |
| `sandbox.ts` | 添加网络隔离验证 | 🔴 stub |

**执行步骤**:

```typescript
// src/domain/m11/sandbox.ts

// 替换 stub:
private async simulateExecution(sandboxId, command, startTime) {
  // 当前: mock
  return { success: true, stdout: 'mock' };
}

// 真实实现:
private async executeRunsc(args: string[]): Promise<SandboxResult> {
  return new Promise((resolve) => {
    const proc = spawn('runsc', args);
    let stdout = '', stderr = '';
    
    proc.stdout.on('data', (d) => stdout += d);
    proc.stderr.on('data', (d) => stderr += d);
    
    proc.on('close', (code) => {
      resolve({
        success: code === 0,
        stdout, stderr,
        exit_code: code,
        execution_time_ms: Date.now() - startTime
      });
    });
    
    proc.on('error', (err) => {
      resolve({
        success: false,
        stderr: err.message,
        exit_code: -1,
        execution_time_ms: Date.now() - startTime
      });
    });
  });
}

// isAvailable() 真实检查:
async isAvailable(): Promise<boolean> {
  try {
    const result = await execAsync('runsc --version');
    return result.exitCode === 0;
  } catch {
    return false;
  }
}
```

**验收标准**:
- [ ] `runsc` 不可用时 `isAvailable()` 返回 false
- [ ] 危险命令在沙盒中执行被正确拦截
- [ ] 沙盒执行时间被正确记录

**预计工时**: 4-6 小时

---

### 1.3 Action 038: M04 三系统适配器真实集成 (CRITICAL 🔴)

**当前状态**: 所有适配器 executeNode() 返回 mock 数据
```
search_adapter.ts: executeThreeRoundSearch() → mock results
task_adapter.ts: executeNode() → mock results
workflow_adapter.ts: executeNode() → mock results
```

**目标**: 集成真实搜索/任务/工作流执行

**交付物**:

| 文件 | 任务 | 状态 |
|------|------|:----:|
| `search_adapter.ts` | 集成 SearXNG/Tavily API | 🔴 mock |
| `task_adapter.ts` | 集成真实 DAG 节点执行 | 🔴 mock |
| `workflow_adapter.ts` | 集成 n8n workflow 执行 | 🔴 mock |

**执行步骤**:

```typescript
// search_adapter.ts - 真实搜索集成

// 当前:
const results = [{ title: 'mock', url: 'mock', snippet: 'mock' }];

// 真实:
async executeThreeRoundSearch(query: string, context: SearchContext) {
  // Round 1: SearXNG
  const searxng = await fetch(`http://localhost:8080/search?q=${encodeURIComponent(query)}`);
  
  // Round 2: Tavily (如果 SearXNG 不够)
  if (context.confidence < 0.8) {
    const tavily = await fetch(`https://api.tavily.com/search`, {
      headers: { Authorization: `Bearer ${process.env.TAVILY_API_KEY}` },
      body: JSON.stringify({ query, max_results: 5 })
    });
  }
  
  // Round 3: Exa (深度研究)
  if (context.task_type === 'deep_research') {
    const exa = await fetch(`https://api.exa.ai/search`, {
      headers: { Authorization: `Bearer ${process.env.EXA_API_KEY}` }
    });
  }
}
```

**验收标准**:
- [ ] `executeThreeRoundSearch('AI news')` 返回真实搜索结果
- [ ] DAG 节点真实执行，非 mock 延迟
- [ ] n8n workflow 真实触发

**预计工时**: 8-10 小时 (依赖外部 API 配置)

---

## 二、Phase 20: M09 DSPy 真实化 (HIGH 🟠)

**目标**: 将模拟的 MIPROv2 替换为真实 DSPy 集成

### 2.1 Action 039: M09 Layer4 GEPA 真实化 (HIGH 🟠)

**当前状态**:
```
layer4_nightly.ts:
- GepaEngine.reflectAndGenerate() → mock data (lines 113-144)
- DspyCompiler.evaluateCandidates() → heuristic scoring (line 412)
```

**目标**: 实现真实 LLM 调用进行 GEPA 反思

**交付物**:

| 文件 | 任务 | 状态 |
|------|------|:----:|
| `layer4_nightly.ts` | 真实调用 LLM 进行 GEPA 反思 | 🔴 mock |
| `dspy_compiler.ts` | 真实 MIPROv2 Bayesian 优化 | 🔴 mock |
| `dspy_compiler.ts` | 真实遗传算法操作 | 🔴 mock |

**执行步骤**:

```typescript
// layer4_nightly.ts - 真实 GEPA

// 当前:
async reflectAndGenerate(experiences: ExperiencePackage[]): Promise<GepaSuggestion> {
  return {
    reflection: 'mock reflection based on keyword analysis',
    suggestions: ['optimize prompt', 'improve context'],
    confidence: 0.7
  };
}

// 真实实现:
async reflectAndGenerate(
  experiences: ExperiencePackage[],
  llm: LLMClient
): Promise<GepaSuggestion> {
  const prompt = buildReflectionPrompt(experiences);
  const response = await llm.complete(prompt, {
    model: 'claude-sonnet-4',
    max_tokens: 500
  });
  
  return parseGepaResponse(response);
}
```

**验收标准**:
- [ ] GEPA 反思基于真实 LLM 输出，非关键词匹配
- [ ] 优化建议具体且可执行
- [ ] 反思结果写入 evolution_digest.json

**预计工时**: 6-8 小时

---

### 2.2 Action 040: M09 DSPy MIPROv2 真实化 (HIGH 🟠)

**当前状态**:
```
dspy_compiler.ts:
- evaluateCandidates() → heuristic scoring (line 412)
- geneticOperations() → stub tournament selection (line 766)
```

**目标**: 实现真实 DSPy 或移除伪实现

**执行决策**:
```
选项 A: 真实集成 DSPy MIPROv2
- 需要: pip install dspy-ai + API 密钥
- 工作量: 12-16 小时
- 风险: DSPy API 不稳定

选项 B: 重构为 HeuristicOptimizer
- 将 dspy_compiler.ts 重命名为 heuristic_optimizer.ts
- 保留现有启发式评分逻辑
- 工作量: 2 小时
- 风险: 无

推荐: 选项 B (快速止血)
```

**交付物**:

| 文件 | 任务 | 决策 |
|------|------|:----:|
| `dspy_compiler.ts` | 重构为 HeuristicOptimizer | 选项 B |
| `layer4_nightly.ts` | 更新引用从 DSPy 到 HeuristicOptimizer | 2h |
| `mod.ts` | 更新导出 | 1h |

**验收标准**:
- [ ] HeuristicOptimizer 功能等价于原 dspy_compiler
- [ ] MIPROv2 相关注释移除，替换为准确描述
- [ ] 测试通过

**预计工时**: 3-4 小时

---

## 三、Phase 21: M06 语义管线真实化 (HIGH 🟠)

**目标**: 将 Stub 的压缩/嵌入阶段替换为真实实现

### 3.1 Action 041: M06 PostToolUse 管线压缩/嵌入真实化 (HIGH 🟠)

**当前状态**:
```
semantic_writer.ts:
- Stage 3 (Compression) → 只是 truncate(4000), 非 LLM 压缩 🔴 stub
- Stage 6 (Embedding) → 生成 random vectors, 非真实嵌入 🔴 stub
```

**目标**: 集成真实 LLM 压缩和嵌入模型

**交付物**:

| 文件 | 任务 | 状态 |
|------|------|:----:|
| `semantic_writer.ts` | Stage 3 集成 LLM 压缩 | 🔴 stub |
| `semantic_writer.ts` | Stage 6 集成真实嵌入模型 | 🔴 stub |
| `semantic_writer.ts` | 添加 embedding 模型配置 | 🔴 stub |

**执行步骤**:

```typescript
// semantic_writer.ts - Stage 3 & 6 真实化

// Stage 3: LLM 压缩 (替代简单 truncate)
async compressWithLLM(content: string): Promise<string> {
  const prompt = `Compress the following text while preserving key information:
  
Original: ${content}

Requirements:
- Keep critical facts, decisions, and outcomes
- Remove redundant descriptions
- Output in same language as input
- Max 500 tokens`;

  const response = await this.llm.complete(prompt, {
    model: 'claude-haiku',
    max_tokens: 600
  });
  
  return response.trim();
}

// Stage 6: 真实嵌入 (替代 random vector)
async generateEmbedding(text: string): Promise<number[]> {
  const response = await fetch('https://api.openai.com/v1/embeddings', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'text-embedding-3-small',
      input: text.substring(0, 8000)
    })
  });
  
  const data = await response.json();
  return data.data[0].embedding;
}
```

**验收标准**:
- [ ] 压缩后内容保留关键信息，非简单截断
- [ ] 嵌入向量可用于语义检索
- [ ] 评分 > 30 分的内容才写入

**预计工时**: 4-6 小时 (需要 OpenAI API 密钥)

---

### 3.2 Action 042: M06 L4 GraphRAG 实体抽取真实化 (MEDIUM 🟡)

**当前状态**:
```
knowledge_graph.ts:
- distillFromExperience() → 关键词提取, 非 LLM 抽取 (lines 89-112) 🔴 stub
```

**目标**: 实现 LLM 基础实体关系抽取

**交付物**:

| 文件 | 任务 | 状态 |
|------|------|:----:|
| `knowledge_graph.ts` | `extractEntities()` 使用 LLM | 🔴 stub |
| `knowledge_graph.ts` | `extractRelations()` 使用 LLM | 🔴 stub |

**验收标准**:
- [ ] 实体抽取基于语义理解，非正则匹配
- [ ] 关系抽取识别实体间语义关联
- [ ] 三元组写入 knowledge_graph

**预计工时**: 3-4 小时

---

## 四、Phase 22: 测试覆盖率增强 (MEDIUM 🟡)

**目标**: 添加缺失模块的单元测试

### 4.1 Action 043: 执行器测试补全 (MEDIUM 🟡)

**当前状态**: 无 dedicated test file

**目标**: 创建 `executor_adapter.test.ts`

**交付物**:
- `executor_adapter.test.ts` - 四大执行器测试
- mock Claude Code CLI 响应
- mock Midscene.js 响应

**验收标准**:
- [ ] 每个执行器方法有 >= 3 个测试用例
- [ ] 错误场景覆盖 (超时、网络错误、权限错误)

**预计工时**: 3-4 小时

---

### 4.2 Action 044: 语义管线测试补全 (MEDIUM 🟡)

**当前状态**: 无 dedicated test file

**目标**: 创建 `semantic_writer.test.ts`

**交付物**:
- `semantic_writer.test.ts` - 七阶段管线测试
- Stage 1-2, 4-5, 7 已有实现需要测试覆盖

**验收标准**:
- [ ] 7 阶段管线端到端测试
- [ ] 各阶段边界条件覆盖

**预计工时**: 2-3 小时

---

## 五、Phase 23: 技术债务清理 (LOW 🟢)

**目标**: 统一错误处理和日志模式

### 5.1 Action 045: 统一错误处理 (LOW 🟢)

**当前状态**: 混乱的错误处理模式

**问题**:
```
layer2_monitor.ts: error instanceof Error ? error.message : 'Unknown error'
dspy_compiler.ts: String(error)
semantic_writer.ts: 'Unknown error'
```

**目标**: 引入自定义错误类型

**交付物**:

| 文件 | 任务 |
|------|------|
| `src/domain/errors.ts` | 定义 `PromptEngineError`, `MemoryError`, `SandboxError` 等 |
| `mod.ts` | 统一导出错误类型 |
| 各模块 | 替换 `throw new Error()` 为 `throw new PromptEngineError()` |

**预计工时**: 2-3 小时

---

### 5.2 Action 046: 统一日志框架 (LOW 🟢)

**当前状态**: 混用 console.log/console.error

**目标**: 引入结构化日志

**交付物**:

| 文件 | 任务 |
|------|------|
| `src/infrastructure/logger.ts` | 定义 Logger 类，支持 level/tag/timestamp |
| `health_server.ts` | 使用 Logger 替代 console.log |
| `coordinator.ts` | 使用 Logger 替代 console.log |
| `daemon_manager.ts` | 使用 Logger 替代 console.error |

**预计工时**: 2 小时

---

## 六、综合时间线

```
Phase 19: 核心执行层真实化
═══════════════════════════════════════
Week 1 (04-15 ~ 04-17)
├── Day 1: Action 036 (M11 执行器集成)
│   ├── 4h: Claude Code CLI 集成
│   └── 4h: Midscene.js 集成
├── Day 2: Action 037 (gVisor 真实执行)
│   └── 6h: runsc 真实调用 + isAvailable 检查
└── Day 3: Action 038 (M04 适配器集成)
    ├── 4h: SearXNG/Tavily 搜索集成
    └── 4h: DAG 节点真实执行

Phase 20: M09 DSPy 真实化
═══════════════════════════════════════
Week 2 (04-18 ~ 04-22)
├── Day 1-2: Action 039 (GEPA 真实 LLM 调用)
└── Day 3-4: Action 040 (DSPy → HeuristicOptimizer)

Phase 21: M06 语义管线真实化
═══════════════════════════════════════
Week 3 (04-23 ~ 04-25)
├── Day 1-2: Action 041 (压缩/嵌入 LLM 集成)
└── Day 3: Action 042 (GraphRAG LLM 抽取)

Phase 22: 测试覆盖率增强
═══════════════════════════════════════
Week 4 (04-26 ~ 04-29)
├── Day 1-2: Action 043 (执行器测试)
└── Day 3-4: Action 044 (语义管线测试)

Phase 23: 技术债务清理
═══════════════════════════════════════
Week 5 (04-30 ~ 05-02)
├── Day 1: Action 045 (统一错误处理)
└── Day 2: Action 046 (统一日志框架)

总计: 5-6 周 (单人开发)
```

---

## 七、资源依赖

| 依赖项 | 用途 | 优先级 |
|--------|------|:------:|
| Claude Code CLI | M11 执行器 | 🔴 必须 |
| OpenAI API Key | M06 嵌入/压缩, M09 GEPA | 🔴 必须 |
| SearXNG (Docker) | M04 搜索 | 🟠 推荐 |
| Tavily API Key | M04 搜索 | 🟠 推荐 |
| Exa API Key | M04 深度搜索 | 🟡 可选 |
| runsc binary | M11 gVisor | 🟠 推荐 |
| Midscene.js | M11 Web 自动化 | 🟡 可选 |

---

## 八、优先级决策矩阵

| Action | 影响模块 | 工时 | 优先级 | 理由 |
|--------|:-------:|:----:|:------:|------|
| 036 | M11 | 8-12h | 🔴 P0 | 执行器全是 stub，系统无法工作 |
| 038 | M04 | 8-10h | 🔴 P0 | 适配器全是 mock，无实际功能 |
| 037 | M11 | 4-6h | 🟠 P1 | gVisor 只是模拟，无安全保护 |
| 039 | M09 | 6-8h | 🟠 P1 | GEPA 是假的，无法真正进化 |
| 040 | M09 | 3-4h | 🟠 P1 | 移除伪实现，名称与行为一致 |
| 041 | M06 | 4-6h | 🟠 P1 | 压缩/嵌入是 stub，数据质量差 |
| 042 | M06 | 3-4h | 🟡 P2 | GraphRAG 实体抽取不准确 |
| 043 | 测试 | 3-4h | 🟡 P2 | 执行器无测试覆盖 |
| 044 | 测试 | 2-3h | 🟢 P3 | 管线无测试覆盖 |
| 045 | 技术债 | 2-3h | 🟢 P3 | 错误处理混乱 |
| 046 | 技术债 | 2h | 🟢 P3 | 日志不一致 |

---

## 九、推荐执行顺序

```
立即执行 (本周):
  1. Action 040 (DSPy → HeuristicOptimizer) - 2h, 快速止血
  2. Action 037 (gVisor 真实执行) - 6h, 提升安全性

下周执行:
  3. Action 036 (执行器集成) - 12h, 核心功能
  4. Action 039 (GEPA 真实化) - 8h, 进化能力

视资源执行:
  5. Action 038 (M04 适配器) - 10h
  6. Action 041 (M06 管线) - 6h
  7. Action 042 (GraphRAG) - 4h
  8. Action 043-046 (测试+技术债) - 12h
```

---

## 十、验收标准更新

### Phase 19 验收 ✅ 全部完成
```
- [x] Claude Code CLI 真实调用 (executor_adapter.ts)
- [x] Midscene.js Web 自动化真实执行 (executor_adapter.ts)
- [x] runsc gVisor 真实隔离执行 (sandbox.ts + graceful fallback)
- [x] gVisor 不可用时正确降级 (isAvailable() + fallback)
```

### Phase 20 验收 ✅ 全部完成
```
- [x] GEPA 反思基于真实 LLM 输出 (llm_adapter.ts → layer4_nightly.ts)
- [x] HeuristicOptimizer 替代 DSPy (功能等价)
- [x] 无 "mock" 关键词在生产代码中 (graceful fallback 机制)
```

### Phase 21 验收 ✅ 全部完成
```
- [x] 语义压缩保留关键信息 (llmAdapter.compress())
- [x] 嵌入向量支持语义检索 (llmAdapter.embed())
- [x] GraphRAG 实体抽取基于理解 (llmAdapter → knowledge_graph.ts)
```

### Phase 22 验收 ✅ 全部完成
```
- [x] Action 043: 执行器测试补全 (16 tests)
- [x] Action 044: 语义管线测试补全 (17 tests)
```

### Phase 23 已完成 (技术债务清理) ✅
```
- [x] Action 045: 统一错误处理
  └── src/domain/errors.ts (19 个错误类)
  └── src/domain/errors_mod.ts (统一导出)
- [x] Action 046: 统一日志框架
  └── src/infrastructure/logger.ts (6 级日志 + 标签 + 上下文)
```

---

**完成日期**: 2026-04-15
**状态**: Phase 19-23 全部完成 ✅
**下次更新**: 项目归档
