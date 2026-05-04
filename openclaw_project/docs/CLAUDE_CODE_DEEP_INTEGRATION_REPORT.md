# Claude Code 深度接入 OpenClaw 集成报告

> **文档版本**: v1.0
> **生成日期**: 2026-04-16
> **基于**: OpenClaw 超级工程项目架构分析 + GStack 技能系统深度调研
> **目标**: 实现 Claude Code 作为 OpenClaw M04/M11 执行层核心组件，完成深度神经网络式集成

---

## 第一章 · 现状分析

### 1.1 现有组件盘点

| 组件 | 文件路径 | 实现状态 | 代码行数 |
|------|---------|---------|---------|
| **ExecutorAdapter** | `src/domain/m11/adapters/executor_adapter.ts` | ✅ 已实现 | ~960 行 |
| **ClaudeCodeAdapter** | `src/infrastructure/execution/claude_code_adapter.ts` | ✅ 已实现 | ~50 行 |
| **ExecutorType 枚举** | `src/domain/m11/types.ts` | ✅ 已定义 | - |
| **VisualToolSelector** | `src/domain/m11/adapters/executor_adapter.ts` | ✅ 已实现 | ~150 行 |
| **M04 Coordinator** | `src/domain/m04/coordinator.ts` | ⚠️ 部分实现 | ~300+ 行 |
| **M06 记忆系统** | `src/domain/m06/` | ⚠️ 框架存在 | - |
| **GStack Skills** | `~/.claude/skills/gstack/` | ✅ 已安装 | 36+ SKILL.md |

### 1.2 架构断点分析

```
┌─────────────────────────────────────────────────────────────────┐
│                      现有架构 (断点标记)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  M04 Coordinator                                                │
│       │                                                         │
│       │ [断点 #1]                                               │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  M11 ExecutorAdapter                                     │    │
│  │       │                                                  │    │
│  │       │ [断点 #2]                                        │    │
│  │       ▼                                                  │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │ executeClaudeCode() ✅                           │    │    │
│  │  │ - --task 自主模式 ✅                              │    │    │
│  │  │ - --print 单次模式 ✅                              │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  │                                                         │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │ ClaudeCodeAdapter (独立) ✅                       │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  [断点 #3] GStack Skills 未连接                                 │
│  [断点 #4] 执行记录未存入 M06 记忆                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 断点详情

| 断点 | 描述 | 影响 |
|------|------|------|
| **#1** | M04 Coordinator 未调用 ExecutorAdapter | 意图无法路由到执行层 |
| **#2** | executeClaudeCode() 未被 submit/execute 流程调用 | 任务无法执行 |
| **#3** | GStack Skills (36+ 个) 未注册为 M04 工具 | 无法使用 /review /qa 等技能 |
| **#4** | 执行记录未流入 M06 记忆 | 无跨会话学习能力 |

---

## 第二章 · 目标架构

### 2.1 完整集成架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OpenClaw 深度集成架构                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        M01 编排引擎层                                 │    │
│  │  用户输入 → 意图分类 → 路由决策                                        │    │
│  └─────────────────────────────────┬─────────────────────────────────────┘    │
│                                    │                                           │
│  ┌─────────────────────────────────▼─────────────────────────────────────┐    │
│  │                    M04 Coordinator (调度核心)                          │    │
│  │  ┌───────────────────────────────────────────────────────────────┐   │    │
│  │  │ ToolSet 注册表                                                 │   │    │
│  │  │  ├─ claude_code_task     (自主任务执行)                        │   │    │
│  │  │  ├─ claude_code_prompt   (单次提示执行)                       │   │    │
│  │  │  ├─ opencli_*           (浏览器自动化)                         │   │    │
│  │  │  ├─ midscene_*          (视觉自动化)                          │   │    │
│  │  │  └─ gstack_skill_*      (GStack 技能路由)                    │   │    │
│  │  └───────────────────────────────────────────────────────────────┘   │    │
│  │                                                                       │    │
│  │  ┌───────────────────────────────────────────────────────────────┐   │    │
│  │  │  SkillRouter (技能路由器)                                    │   │    │
│  │  │   ├─ "代码审查" → /review                                   │   │    │
│  │  │   ├─ "测试" → /qa                                           │   │    │
│  │  │   ├─ "构思" → /office-hours                                 │   │    │
│  │  │   ├─ "部署" → /ship                                         │   │    │
│  │  │   └─ "调查" → /investigate                                  │   │    │
│  │  └───────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────┬─────────────────────────────────────┘    │
│                                    │                                           │
│  ┌─────────────────────────────────▼─────────────────────────────────────┐    │
│  │                      M11 ExecutorAdapter                             │    │
│  │  ┌───────────────────────────────────────────────────────────────┐   │    │
│  │  │ submit(type, instruction, params)                          │   │    │
│  │  │   └─→ execute()                                             │   │    │
│  │  └───────────────────────────────────────────────────────────────┘   │    │
│  │                                                                       │    │
│  │  ┌──────────────┬──────────────┬──────────────┬──────────────┐   │    │
│  │  │ CLAUDE_CODE  │   OPENCLI    │   MIDSCENE   │  CLI_ANYTHING │   │    │
│  │  │     ✅        │     ✅       │     ✅       │      ✅       │   │    │
│  │  └──────────────┴──────────────┴──────────────┴──────────────┘   │    │
│  │                                                                       │    │
│  │  ┌───────────────────────────────────────────────────────────────┐   │    │
│  │  │ executeClaudeCode(task)                                     │   │    │
│  │  │   ├─ spawn('claude', ['--task', instruction])             │   │    │
│  │  │   ├─ gVisorSandbox.execute() (可选)                        │   │    │
│  │  │   └─ 返回 { output, sandboxed }                            │   │    │
│  │  └───────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────┬─────────────────────────────────────┘    │
│                                    │                                           │
│  ┌─────────────────────────────────▼─────────────────────────────────────┐    │
│  │                      M06/M08 记忆与学习系统                          │    │
│  │  ┌───────────────────────────────────────────────────────────────┐   │    │
│  │  │ ExecutionRecord                                            │   │    │
│  │  │   ├─ task_id, instruction, result                           │   │    │
│  │  │   ├─ success, error, duration_ms                           │   │    │
│  │  │   ├─ tokens_used, cost_usd                                 │   │    │
│  │  │   └─ timestamp                                             │   │    │
│  │  └───────────────────────────────────────────────────────────────┘   │    │
│  │                                                                       │    │
│  │  ┌───────────────────────────────────────────────────────────────┐   │    │
│  │  │ SkillSynthesizer (技能自合成器)                              │   │    │
│  │  │   ├─ 检测高频成功路径                                         │   │    │
│  │  │   ├─ 生成 SKILL.md                                           │   │    │
│  │  │   └─ 自动注册到 ToolSet                                       │   │    │
│  │  └───────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       GStack Skills 系统                             │    │
│  │  ~/.claude/skills/gstack/                                          │    │
│  │  ┌─────────┬─────────┬─────────┬─────────┬─────────┐            │    │
│  │  │ /review │ /qa     │ /ship   │ /office │ /invest │ ...        │    │
│  │  │         │         │         │ -hours  │ -igate  │ (36+)     │    │
│  │  └─────────┴─────────┴─────────┴─────────┴─────────┘            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
用户输入: "帮我审查 src/domain 下的代码"
    │
    ▼
M01 编排引擎 → 意图分类
    │ "代码审查" → category: code_review
    ▼
M04 Coordinator
    │
    ▼
SkillRouter 匹配
    │ /review skill 触发
    ▼
executorAdapter.submit(
    ExecutorType.CLAUDE_CODE,
    "使用 /review 审查代码仓库",
    { skill: "/review", target: "src/domain" }
)
    │
    ▼
M11 ExecutorAdapter.execute()
    │
    ├──→ executeClaudeCode()
    │        │
    │        ▼
    │    spawn('claude', ['--task', '...'])
    │        │
    │        ▼
    │    Claude Code 自主执行 /review 技能
    │        │
    │        ▼
    │    返回执行结果
    │
    ▼
M06 记忆系统 (post-execution hook)
    │
    ▼
执行记录存入 persistent_memory
    │
    ▼
M08 学习系统分析
    │ 高频成功路径 → 技能注册建议
    ▼
```

---

## 第三章 · 详细接入计划

### Phase 1: M04 ↔ M11 桥梁搭建 (1-2 天)

#### 任务 1.1: M04 导入 ExecutorAdapter

**文件**: `src/domain/m04/coordinator.ts`

```typescript
import {
  ExecutorAdapter,
  ExecutorType,
  executorAdapter,
  VisualToolSelector,
  visualToolSelector,
} from '../m11/adapters/executor_adapter';
```

#### 任务 1.2: 添加 ToolSet 注册方法

**文件**: `src/domain/m04/coordinator.ts` (新增方法)

```typescript
/**
 * 注册 Claude Code ToolSet 到 M04
 */
private registerClaudeCodeToolset(): void {
  this.tools.register({
    name: 'claude_code_task',
    description: 'Claude Code 自主任务执行 - 复杂任务、代码编写、系统操作',
    parameters: {
      instruction: { type: 'string', description: '执行指令' },
      timeout_ms: { type: 'number', default: 120000 },
      sandboxed: { type: 'boolean', default: true },
    },
    executor: ExecutorType.CLAUDE_CODE,
  });

  this.tools.register({
    name: 'claude_code_prompt',
    description: 'Claude Code 单次提示执行 - 简单查询、快速问答',
    parameters: {
      prompt: { type: 'string', description: '提示内容' },
      timeout_ms: { type: 'number', default: 60000 },
    },
    executor: ExecutorType.CLAUDE_CODE,
  });
}
```

#### 任务 1.3: M04.execute() 添加 M11 调用路径

**文件**: `src/domain/m04/coordinator.ts` (修改 execute 方法)

```typescript
// 在 switch (system_type) 中添加:
case SystemType.CLAUDE_CODE:
  const result = await this.executorAdapter.submit(
    ExecutorType.CLAUDE_CODE,
    context.metadata.instruction,
    { timeout_ms: context.metadata.timeout_ms, sandboxed: true }
  );
  return await this.executorAdapter.execute(result);
```

---

### Phase 2: GStack 技能路由 (2-3 天)

#### 任务 2.1: 创建 SkillRouter

**文件**: `src/domain/m04/skill_router.ts` (新建)

```typescript
/**
 * GStack 技能路由器
 * 将自然语言意图路由到对应 GStack Skill
 */

interface SkillRoute {
  patterns: RegExp[];
  skill: string;
  instruction: string;
  description: string;
}

const SKILL_ROUTES: SkillRoute[] = [
  {
    patterns: [/code.*review/i, /审查.*代码/i, /review.*code/i, /检查.*代码/i],
    skill: '/review',
    instruction: '执行高级代码审查，检查安全性、性能、最佳实践',
    description: '代码审查专家',
  },
  {
    patterns: [/test.*case/i, /测试.*用例/i, /qa/i, /run.*test/i],
    skill: '/qa',
    instruction: '执行全面 QA 测试，发现并修复 bug',
    description: 'QA 测试专家',
  },
  {
    patterns: [/deploy/i, /ship/i, /发布/i, /部署/i],
    skill: '/ship',
    instruction: '执行自动化发布流程，合并分支、运行测试、创建 PR',
    description: '发布工程师',
  },
  {
    patterns: [/product.*idea/i, /产品.*构思/i, /office.*hour/i, /创意.*验证/i],
    skill: '/office-hours',
    instruction: '使用 YC 方法论验证产品想法',
    description: 'YC 办公时间',
  },
  {
    patterns: [/investigate/i, /调试/i, /debug/i, /调查/i, /排查/i],
    skill: '/investigate',
    instruction: '系统化根因分析，定位问题源头',
    description: '调试调查专家',
  },
  {
    patterns: [/architect/i, /架构.*评审/i, /plan.*eng/i, /技术.*评审/i],
    skill: '/plan-eng-review',
    instruction: '从工程架构角度评审技术方案',
    description: '架构评审专家',
  },
  {
    patterns: [/careful/i, /danger/i, /危险/i, /安全.*警告/i],
    skill: '/careful',
    instruction: '显示危险操作的安全警告',
    description: '安全警告专家',
  },
];

export class SkillRouter {
  /**
   * 路由意图到 GStack Skill
   */
  route(intent: string): SkillRoute | null {
    for (const route of SKILL_ROUTES) {
      for (const pattern of route.patterns) {
        if (pattern.test(intent)) {
          return route;
        }
      }
    }
    return null;
  }

  /**
   * 构建 Skill 执行指令
   */
  buildInstruction(skill: string, context: string): string {
    return `使用 ${skill} 技能完成以下任务: ${context}`;
  }
}

export const skillRouter = new SkillRouter();
```

#### 任务 2.2: SKILL.md 加载器

**文件**: `src/domain/m04/skill_loader.ts` (新建)

```typescript
import * as fs from 'fs';
import * as path from 'path';

interface SkillDefinition {
  name: string;
  description: string;
  version?: string;
  commands?: string[];
  workflows?: string[];
}

const GSTACK_SKILLS_PATH = path.join(
  process.env.HOME || process.env.USERPROFILE || '',
  '.claude',
  'skills',
  'gstack'
);

export class SkillLoader {
  /**
   * 加载所有 GStack 技能
   */
  loadAllSkills(): Map<string, SkillDefinition> {
    const skills = new Map<string, SkillDefinition>();

    if (!fs.existsSync(GSTACK_SKILLS_PATH)) {
      console.warn('[SkillLoader] GStack skills not found at:', GSTACK_SKILLS_PATH);
      return skills;
    }

    const entries = fs.readdirSync(GSTACK_SKILLS_PATH, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) {
        const skillPath = path.join(GSTACK_SKILLS_PATH, entry.name, 'SKILL.md');
        if (fs.existsSync(skillPath)) {
          const skill = this.loadSkill(entry.name, skillPath);
          skills.set(entry.name, skill);
        }
      }
    }

    return skills;
  }

  /**
   * 加载单个技能
   */
  loadSkill(name: string, skillPath: string): SkillDefinition {
    const content = fs.readFileSync(skillPath, 'utf-8');

    // 解析 frontmatter
    const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
    if (frontmatterMatch) {
      const fm = this.parseFrontmatter(frontmatterMatch[1]);
      return {
        name: fm.name || name,
        description: fm.description || '',
        version: fm.version,
      };
    }

    return { name, description: '' };
  }

  /**
   * 解析 frontmatter
   */
  private parseFrontmatter(content: string): Record<string, string> {
    const result: Record<string, string> = {};
    const lines = content.split('\n');

    for (const line of lines) {
      const match = line.match(/^(\w+):\s*(.*)$/);
      if (match) {
        result[match[1]] = match[2].replace(/^["']|["']$/g, '');
      }
    }

    return result;
  }
}

export const skillLoader = new SkillLoader();
```

---

### Phase 3: 学习系统集成 (2-3 天)

#### 任务 3.1: 执行记录 Hook

**文件**: `src/domain/m11/adapters/executor_adapter.ts` (增强)

```typescript
// 在 execute() 方法的 finally 块后添加 post-execution hook:

private async recordExecution(task: ExecutorTask, result: ExecutorResult): Promise<void> {
  const record = {
    type: 'executor_execution',
    task_id: task.id,
    executor_type: task.type,
    instruction: task.instruction,
    success: result.success,
    error: result.error,
    duration_ms: result.execution_time_ms,
    timestamp: Date.now(),
    params: task.params,
  };

  // TODO: 发送到 M06 记忆系统
  // await memorySystem.write(record);

  console.log('[ExecutorAdapter] Execution recorded:', record);
}
```

#### 任务 3.2: 技能自合成检测

**文件**: `src/domain/m08/learning/skill_synthesizer.ts` (新建)

```typescript
/**
 * 技能自合成器
 * 检测高频成功执行路径，自动生成新技能
 */

interface ExecutionPattern {
  instruction: string;
  success_count: number;
  failure_count: number;
  avg_duration_ms: number;
  last_executed: number;
}

export class SkillSynthesizer {
  private patterns: Map<string, ExecutionPattern> = new Map();
  private readonly SYNTHESIS_THRESHOLD = 5; // 成功次数阈值

  /**
   * 记录执行结果
   */
  recordExecution(instruction: string, success: boolean, duration_ms: number): void {
    const key = this.normalizeInstruction(instruction);

    if (!this.patterns.has(key)) {
      this.patterns.set(key, {
        instruction: instruction,
        success_count: 0,
        failure_count: 0,
        avg_duration_ms: 0,
        last_executed: Date.now(),
      });
    }

    const pattern = this.patterns.get(key)!;
    if (success) {
      pattern.success_count++;
    } else {
      pattern.failure_count++;
    }

    // 更新平均执行时间
    const total = pattern.success_count + pattern.failure_count;
    pattern.avg_duration_ms =
      (pattern.avg_duration_ms * (total - 1) + duration_ms) / total;
    pattern.last_executed = Date.now();
  }

  /**
   * 检测可合成的技能
   */
  detectSynthesizableSkills(): ExecutionPattern[] {
    const candidates: ExecutionPattern[] = [];

    for (const pattern of this.patterns.values()) {
      if (pattern.success_count >= this.SYNTHESIS_THRESHOLD) {
        const success_rate = pattern.success_count / (pattern.success_count + pattern.failure_count);
        if (success_rate >= 0.8) {
          candidates.push(pattern);
        }
      }
    }

    return candidates.sort((a, b) => b.success_count - a.success_count);
  }

  /**
   * 生成 SKILL.md 内容
   */
  generateSkillMd(pattern: ExecutionPattern): string {
    return `---
name: auto_${Date.now()}
description: 自动合成的技能: ${pattern.instruction}
version: 1.0.0
---

# 自动合成技能

## 描述
${pattern.instruction}

## 使用场景
- 执行频率: ${pattern.success_count} 次
- 成功率: ${((pattern.success_count / (pattern.success_count + pattern.failure_count)) * 100).toFixed(1)}%
- 平均执行时间: ${(pattern.avg_duration_ms / 1000).toFixed(1)}s

## 执行命令
\`\`\`bash
${pattern.instruction}
\`\`\`
`;
  }

  /**
   * 规范化指令 (去除参数差异)
   */
  private normalizeInstruction(instruction: string): string {
    // 移除具体数值、URL 等差异部分
    return instruction
      .replace(/\d+/g, 'N')
      .replace(/https?:\/\/[^\s]+/g, 'URL')
      .replace(/["'].*?["']/g, '"VAL"')
      .trim()
      .toLowerCase();
  }
}

export const skillSynthesizer = new SkillSynthesizer();
```

---

## 第四章 · 文件变更清单

### 4.1 需要修改的文件

| 文件 | 操作 | 变更内容 |
|------|------|---------|
| `src/domain/m04/coordinator.ts` | 修改 | 导入 ExecutorAdapter，添加 ToolSet 注册，修改 execute() |
| `src/domain/m04/types.ts` | 修改 | 添加 CLAUDE_CODE SystemType |
| `src/domain/m11/adapters/executor_adapter.ts` | 修改 | 增强执行记录 Hook |

### 4.2 需要新建的文件

| 文件 | 用途 |
|------|------|
| `src/domain/m04/skill_router.ts` | GStack 技能路由器 |
| `src/domain/m04/skill_loader.ts` | SKILL.md 加载器 |
| `src/domain/m08/learning/skill_synthesizer.ts` | 技能自合成器 |
| `src/domain/m08/learning/execution_recorder.ts` | 执行记录存储器 |

### 4.3 依赖的现有文件

| 文件 | 用途 |
|------|------|
| `~/.claude/skills/gstack/*/SKILL.md` | GStack 技能定义 |
| `src/domain/m11/types.ts` | ExecutorType 枚举 |
| `src/infrastructure/execution/claude_code_adapter.ts` | Claude Code 适配器 |

---

## 第五章 · API 接口设计

### 5.1 M04 ToolSet 接口

```typescript
// 注册 ToolSet
coordinator.registerToolset({
  name: 'claude_code',
  tools: [
    {
      name: 'claude_code_task',
      description: 'Claude Code 自主任务执行',
      parameters: {
        instruction: { type: 'string', required: true },
        timeout_ms: { type: 'number', default: 120000 },
        sandboxed: { type: 'boolean', default: true },
      },
    },
    {
      name: 'claude_code_prompt',
      description: 'Claude Code 单次提示执行',
      parameters: {
        prompt: { type: 'string', required: true },
        timeout_ms: { type: 'number', default: 60000 },
      },
    },
  ],
});

// 执行 Tool
const result = await coordinator.executeTool('claude_code_task', {
  instruction: '编写一个 hello world 程序',
  timeout_ms: 60000,
});
```

### 5.2 SkillRouter 接口

```typescript
interface RouteResult {
  matched: boolean;
  skill: string | null;
  instruction: string | null;
  confidence: number;
}

// 路由意图
const route = skillRouter.route('帮我审查 src/domain 下的代码');
// → {
//      matched: true,
//      skill: '/review',
//      instruction: '使用 /review 技能完成以下任务: 帮我审查 src/domain 下的代码',
//      confidence: 0.95,
//    }
```

### 5.3 ExecutorAdapter 接口

```typescript
// 提交任务
const taskId = await executorAdapter.submit(
  ExecutorType.CLAUDE_CODE,
  '使用 /review 审查代码',
  { timeout_ms: 120000, sandboxed: true }
);

// 执行任务
const result = await executorAdapter.execute(taskId);
// → {
//      success: true,
//      task_id: 'task_xxx',
//      result: { output: '审查完成，发现 3 个问题...', sandboxed: true },
//      execution_time_ms: 45230,
//    }

// 获取状态
const status = executorAdapter.getTaskStatus(taskId);
// → ExecutorStatus.COMPLETED
```

---

## 第六章 · 安全考虑

### 6.1 命令注入防护

```typescript
// executeClaudeCode() 已实现命令白名单检查
// 危险模式检测:
const DANGEROUS_PATTERNS = [
  /[;&|`$(){}/\\]/,           // Shell 特殊字符
  /\brsync\b/,                // 潜在危险命令
  /\bmount\b/, /\bumount\b/,
  /\bchmod\b.*\b777\b/,
];

// 验证后才执行
```

### 6.2 沙箱执行

```typescript
// 可选的 gVisor 沙箱隔离
if (sandboxed) {
  const sandboxResult = await gVisorSandbox.execute(
    ['claude', '--task', instruction],
    { type: SandboxType.GVISOR, timeout_ms }
  );
}
```

### 6.3 GStack Skill 安全

```typescript
// SkillLoader 应验证:
1. 文件路径在允许目录内
2. frontmatter 无恶意代码
3. 内容不包含危险命令
```

---

## 第七章 · 验收标准

### Phase 1 验收

| 任务 | 验收标准 | 测试方法 |
|------|---------|---------|
| M04 导入 ExecutorAdapter | 编译无错误 | `npm run build` |
| ToolSet 注册 | 可见 claude_code_task 工具 | 调用 `coordinator.listTools()` |
| execute() 路由 | system_type=CLAUDE_CODE 正确路由 | 单元测试 |

### Phase 2 验收

| 任务 | 验收标准 | 测试方法 |
|------|---------|---------|
| SkillRouter 匹配 | "审查代码" → /review | 单元测试 |
| SkillLoader 加载 | 加载 36+ GStack 技能 | 统计加载数量 |
| 技能执行 | 执行 /review 成功 | E2E 测试 |

### Phase 3 验收

| 任务 | 验收标准 | 测试方法 |
|------|---------|---------|
| 执行记录 | 记录存入 M06 | 检查记忆层 |
| 自合成检测 | 5+ 次成功触发合成建议 | 模拟测试 |
| SKILL.md 生成 | 生成有效的技能文件 | 验证格式 |

---

## 第八章 · 时间估算

| Phase | 任务 | 工作量 | 人员 |
|-------|------|--------|------|
| **Phase 1** | M04 ↔ M11 桥梁 | 1-2 天 | 1 人 |
| | ├─ 导入 ExecutorAdapter | 0.5 天 | |
| | ├─ 注册 ToolSet | 0.5 天 | |
| | └─ 修改 execute() 路由 | 0.5 天 | |
| **Phase 2** | GStack 技能路由 | 2-3 天 | 1 人 |
| | ├─ SkillRouter 实现 | 1 天 | |
| | ├─ SkillLoader 实现 | 0.5 天 | |
| | └─ 路由注册到 M04 | 1 天 | |
| **Phase 3** | 学习系统集成 | 2-3 天 | 1 人 |
| | ├─ 执行记录 Hook | 1 天 | |
| | ├─ 技能自合成器 | 1.5 天 | |
| | └─ M06 记忆写入 | 0.5 天 | |
| **总计** | | **5-8 天** | **1 人** |

---

## 第九章 · 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Claude Code CLI 不可用 | 执行失败 | 优雅降级到本地 LLM 调用 |
| GStack Skills 路径变更 | 技能加载失败 | 配置化路径 + 降级到内建技能 |
| 命令注入绕过 | 安全风险 | 多层检查 + 沙箱隔离 |
| 执行超时 | 任务挂起 | 超时强制终止 + 重试机制 |
| 记忆写入失败 | 学习闭环断裂 | 本地缓冲 + 异步重试 |

---

## 第十章 · 附录

### A. GStack 可用技能列表 (36+)

```
产品构思阶段:
├─ /office-hours        YC 办公时间，产品创意验证
├─ /plan-ceo-review     CEO 视角评审
├─ /plan-eng-review     工程架构评审
└─ /plan-design-review  设计评审

开发阶段:
├─ /review              高级代码审查
├─ /investigate         调试调查专家
└─ /design-consultation 设计咨询

测试发布:
├─ /qa                  QA 测试 + Bug 修复
├─ /qa-only             Bug 报告
└─ /ship                自动化发布

文档与回顾:
├─ /document-release    文档更新
└─ /retro               团队回顾

强力工具:
├─ /codex               OpenAI Codex 审查
├─ /careful             危险警告
├─ /freeze              编辑锁定
└─ /guard               完全安全模式
```

### B. Claude Code CLI 参考

```bash
# 自主任务模式 (用于复杂任务)
claude code --task "编写一个 REST API" --yes

# 单次提示模式 (用于简单查询)
claude code "解释这段代码" --print

# 直接执行 (交互模式)
claude code

# 选项
--task <string>    自主执行任务
--print            打印结果到 stdout
--verbose          详细输出
--dangerously-skip-permissions  跳过权限确认 (危险)
--output <path>    输出到文件
```

### C. 参考文档

- GStack README: `~/.claude/skills/gstack/README.md`
- GStack ARCHITECTURE: `~/.claude/skills/gstack/ARCHITECTURE.md`
- OpenCLI Integration Plan: `docs/OPENCLI_INTEGRATION_PLAN.md`
- Hermes Agent Analysis: `docs/hermes_opencli_deep_改造计划.md`

---

*本文档作为 Claude Code 深度集成 OpenClaw 的对照标准文档*
*版本: v1.0 | 更新日期: 2026-04-16*
