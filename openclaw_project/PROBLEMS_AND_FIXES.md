# OpenClaw 项目问题清单与解决方案 (逐文件验证版)
> 生成日期: 2026-04-15
> 验证方式: 逐文件读取 + 逐行核对 + 测试运行
> 状态: **已验证** / 待修复

---

## 一、安全漏洞 (20项) - 已逐行验证

### 🔴 CRITICAL (5项) - 已确认

| # | 文件 | 行 | 漏洞类型 | 代码证据 | 修复方案 |
|---|------|:---:|----------|----------|----------|
| **S1** | `mcp-bridge.js` | 69-76 | **SQL注入** | ```sql = """${sql...}"""``` SQL嵌入脚本字符串 | 使用Python sqlite3参数化API |
| **S2** | `src/domain/m11/sandbox.ts` | 166-169 | **命令注入** | ```spawn(command, [], {shell: true})``` | 移除shell:true，使用数组spawn |
| **S3** | `src/domain/m11/adapters/executor_adapter.ts` | 156 | **命令注入** | ```claude --print "${instruction...}"``` | 使用数组参数传递 |
| **S4** | `src/infrastructure/server/mcp_api_server.ts` | 23 | **硬编码密钥** | ```API_KEY = 'dev-api-key-change-in-production'``` | 必检环境变量，无则抛错 |
| **S5** | `src/infrastructure/server/mcp_api_server.ts` | 398-401 | **CORS漏洞** | ```Access-Control-Allow-Origin: '*'``` | 改用域名白名单 |

### 🟠 HIGH (6项) - 已确认

| # | 文件 | 行 | 漏洞类型 | 代码证据 | 修复方案 |
|---|------|:---:|----------|----------|----------|
| **S6** | `src/infrastructure/docker-compose.yml` | 26,35,93,146 | **默认凭证** | ```requirepass ${REDIS_PASSWORD:-redis_password_change_me}``` | 部署时生成随机密码 |
| **S7** | `src/domain/m11/sandbox.ts` | 82-98 | **不安全命令构造** | ```'sh', '-c', escapedCmd``` 单引号可绕过 | 数组形式传递命令 |
| **S8** | `src/domain/m11/adapters/executor_adapter.ts` | 202-203 | **路径注入** | ```path.join(HOME, '.deerflow', toolName + '.sh')``` | 白名单验证工具名 |
| **S9** | `src/infrastructure/server/health_server.ts` | 223-248 | **敏感端点无认证** | /health返回系统信息 | 分级健康检查 |
| **S10** | `src/infrastructure/server/mcp_api_server.ts` | 35-48 | **缓存耗尽** | ```authCache = new Map()``` 无maxSize | 添加LRU驱逐maxSize=1000 |
| **S11** | `src/infrastructure/server/mcp_api_server.ts` | 426-522 | **输入验证缺失** | API参数无验证 | Zod schema验证 |

### 🟡 MEDIUM (7项) - 已确认

| # | 文件 | 行 | 问题 | 代码证据 | 修复方案 |
|---|------|:---:|------|----------|----------|
| **S12** | 多文件 | - | **console.log泄露** | 169处console语句 | 替换为logger |
| **S13** | `src/domain/memory/pipeline/semantic_writer.ts` | 248-257 | **XSS弱检测** | ```/<script/i``` 正则可绕过 | DOMPurify库 |
| **S14** | `src/domain/asset_packer.ts` | 37-39,86 | **路径遍历** | ```path.join(ASSETS_ROOT, asset.path)``` | isInside检查 |
| **S15** | `src/infrastructure/env_adapter/.env.example` | 14-24 | **占位密码** | ```PASSWORD=change_me_in_production``` | 随机值生成 |
| **S16** | `src/infrastructure/server/mcp_api_server.ts` | 45 | **时序攻击** | ```key === API_KEY``` | crypto.timingSafeEqual |
| **S17** | `src/infrastructure/server/mcp_api_server.ts` | 122-125 | **缺少安全头** | 无CSP/X-Frame-Options | helmet.js |
| **S18** | `mcp-bridge.js` | 104-108 | **Shell注入** | ```spawn('python', ['-c', script])``` | subprocess.run标准API |

### 🟢 LOW (2项) - 已确认

| # | 文件 | 行 | 问题 | 代码证据 | 修复方案 |
|---|------|:---:|------|----------|----------|
| **S19** | `src/domain/m11/adapters/executor_adapter.ts` | 203 | **环境变量信任** | ```process.env.HOME``` | 验证路径格式 |
| **S20** | `src/infrastructure/env_adapter/env_adapter.py` | 6-14 | **弱IP检测** | ```connect(("8.8.8.8", 80))``` | netifaces库 |

---

## 二、Stub/未完成实现 (12项) - 已逐行验证

### 🔴 高优先级 (4项) - 已确认

| # | 文件 | 行 | 问题 | 代码证据 | 修复方案 |
|---|------|:---:|------|----------|----------|
| **ST1** | `src/application/search_service.ts` | 51-71 | **搜索返回mock** | ```const mockResult: SearchResult = { sources: [...假数据...] }``` | Tavily/Exa API集成 |
| **ST2** | `src/domain/m04/coordinator.ts` | 110-116 | **搜索stub** | ```results: [], summary: 'Search completed via coordinator'``` | SearchAdapter集成 |
| **ST3** | `src/domain/m04/coordinator.ts` | 154-163 | **工作流stub** | ```nodes: [], edges: []``` | WorkflowAdapter集成 |
| **ST4** | `src/domain/prompt_engine/dspy_compiler.ts` | 418-443 | **规则评分** | ```// 简化评估：基于提示词特征打分 score = 0.5``` | LLM真实评估 |

### 🟠 中优先级 (4项) - 已确认

| # | 文件 | 行 | 问题 | 代码证据 | 修复方案 |
|---|------|:---:|------|----------|----------|
| **ST5** | `src/domain/prompt_engine/layer4_nightly.ts` | 232-246 | **模拟沙盒测试** | ```simulatedScore = 0.85 + Math.random() * 0.05``` | 真实历史用例执行 |
| **ST6** | `src/domain/prompt_engine/layer4_nightly.ts` | 384-388 | **假优化** | ```return `[DSPy优化版] ${content}` ``` | MIPROv2 LLM优化 |
| **ST7** | `src/domain/m04/adapters/search_adapter.ts` | 97-99 | **失败回退mock** | ```mockSearch()``` 返回假数据 | 正确错误传播 |
| **ST8** | `src/domain/prompt_engine/layer4_nightly.ts` | 252-262 | **随机决策** | ```Math.random() > 0.3``` | 分数阈值比较 |

### 🟡 低优先级 (4项) - 已确认

| # | 文件 | 行 | 问题 | 代码证据 | 修复方案 |
|---|------|:---:|------|----------|----------|
| **ST9** | `src/domain/hooks.ts` | 434,534 | **吞没错误** | ```.catch(() => {})``` | 日志记录 |
| **ST10** | `src/infrastructure/llm_adapter.ts` | 多处 | **mock回退** | API key缺失时返回假数据 | 快速失败 |
| **ST11** | `src/infrastructure/dapr/dapr_client.ts` | 257-264 | **错误吞没** | ```return null``` on error | 错误传播 |
| **ST12** | `src/infrastructure/server/mcp_api_server.ts` | 351-388 | **SQLite pending** | ```// TODO: 实现``` | 完成集成 |

---

## 三、性能问题 (7项) - 已逐行验证

### 🔴 高优先级 (3项) - 已确认

| # | 文件 | 行 | 问题 | 代码证据 | 修复方案 |
|---|------|:---:|------|----------|----------|
| **P1** | `src/infrastructure/server/mcp_api_server.ts` | 35 | **authCache无上限** | ```authCache = new Map()``` | 添加maxSize=1000 |
| **P2** | `src/domain/prompt_engine/dspy_compiler.ts` | 187,290 | **compilationCache无上限** | ```compilationCache = new Map()``` | 添加maxSize+TTL |
| **P3** | `src/domain/prompt_engine/layer1_router.ts` | 145-191 | **assetCache无上限** | ```cached.push(fragment)``` 无限push | LRU驱逐 |

### 🟠 中优先级 (3项) - 已确认

| # | 文件 | 行 | 问题 | 代码证据 | 修复方案 |
|---|------|:---:|------|----------|----------|
| **P4** | `src/domain/asset_packer.ts` | 88,118 | **同步文件I/O** | ```fs.readFileSync()``` x3 | fs.promises异步 |
| **P5** | `src/domain/auto_patcher.ts` | 33,46,67 | **同步文件I/O** | ```fs.writeFileSync()``` x3 | fs.promises异步 |
| **P6** | `src/domain/memory/layer1/working_memory.ts` | 214-247 | **O(n²)算法** | ```for i... for j...``` 嵌套循环 | hash分组优化 |

### 🟡 低优先级 (1项) - 已确认

| # | 文件 | 行 | 问题 | 代码证据 | 修复方案 |
|---|------|:---:|------|----------|----------|
| **P7** | `src/domain/m04/coordinator.ts` | 393 | **JSON深拷贝低效** | ```JSON.parse(JSON.stringify(task))``` | structuredClone() |

---

## 四、测试失败 (4项) - 已运行验证

| # | 文件 | 测试名称 | 失败原因 | 环境/代码 |
|---|------|---------|----------|-----------|
| **T1** | `src/domain/m11/sandbox.test.ts:28` | should execute command in sandbox | `runsc` 不存在Windows | **ENV** |
| **T2** | `src/domain/e2e/scenarios.test.ts:262` | should block dangerous command... | `runsc` 不存在Windows | **ENV** |
| **T3** | `src/domain/e2e/scenarios.test.ts:274` | should allow safe command execution | `runsc` 不存在Windows | **ENV** |
| **T4** | `src/domain/m04/coordinator_sandbox_integration.test.ts:68` | should execute safe command successfully | `runsc` 不存在Windows | **ENV** |

**测试结果**: 5 failed, 15 passed | 4 failed, 395 passed, 2 skipped | **总计401测试**

---

## 五、其他问题

### 控制台语句未替换 (169处)

| 文件 | 数量 |
|------|:----:|
| `src/domain/*.ts` (多文件) | ~120 |
| `src/infrastructure/*.ts` | ~40 |
| `src/application/*.ts` | ~9 |

---

## 问题汇总表

| 类别 | CRITICAL | HIGH | MEDIUM | LOW | TOTAL |
|------|:--------:|:----:|:------:|:---:|:-----:|
| 安全漏洞 | 5 | 6 | 7 | 2 | **20** |
| Stub实现 | 4 | 4 | 4 | 0 | **12** |
| 性能问题 | 3 | 3 | 1 | 0 | **7** |
| 测试失败 | 0 | 0 | 0 | 4 | **4** |
| **总计** | **12** | **13** | **12** | **6** | **43** |

---

## 修复执行批次

### 📦 第一批: P0 安全修复 (CRITICAL)
| # | 文件 | 修复内容 |
|:---:|------|----------|
| 1 | `mcp-bridge.js` | SQL参数化 |
| 2 | `sandbox.ts` | 移除shell:true |
| 3 | `executor_adapter.ts` | 命令参数化 |
| 4 | `mcp_api_server.ts` | 必检API密钥 |
| 5 | `mcp_api_server.ts` | CORS白名单 |

### 📦 第二批: P1 安全+Stub
| # | 文件 | 修复内容 |
|:---:|------|----------|
| 6 | `docker-compose.yml` | 随机密码 |
| 7 | `sandbox.ts` | 数组形式命令 |
| 8 | `mcp_api_server.ts` | 输入验证(Zod) |
| 9 | `search_service.ts` | 真实搜索API |
| 10 | `coordinator.ts` | 搜索/工作流集成 |
| 11 | `dspy_compiler.ts` | LLM评估 |
| 12 | `layer4_nightly.ts` | 真实沙盒测试 |

### 📦 第三批: P2 中优先级
| # | 文件 | 修复内容 |
|:---:|------|----------|
| 13 | 多文件 | console→logger |
| 14 | `semantic_writer.ts` | XSS防护 |
| 15 | `asset_packer.ts` | 路径遍历检查 |
| 16 | `dapr_client.ts` | 错误传播 |
| 17 | `working_memory.ts` | O(n²)优化 |
| 18 | `asset_packer.ts` | 异步文件I/O |

### 📦 第四批: P3 收尾
| # | 文件 | 修复内容 |
|:---:|------|----------|
| 19 | 测试文件 | 添加isAvailable skip |
| 20 | `mcp_api_server.ts` | helmet.js安全头 |
| 21 | 性能缓存 | 添加maxSize |
| 22 | `hooks.ts` | 错误处理 |

---

## 验证完成标准

- [ ] TypeScript 编译 0 错误
- [ ] 相关测试通过
- [ ] 安全漏洞扫描通过
- [ ] 代码审查无异议
