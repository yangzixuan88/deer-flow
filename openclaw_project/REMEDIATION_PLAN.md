# OpenClaw 修复执行规划
> 生成日期: 2026-04-15
> 待用户验收后执行

---

## 执行原则

1. **安全第一**: 所有 CRITICAL/HIGH 安全漏洞优先修复
2. **分批执行**: 每批修复一个完整模块，便于此验证
3. **测试驱动**: 修复后立即运行测试验证
4. **不破坏**: 确保现有功能不被影响

---

## 分批执行计划

### 📦 第一批: P0 安全修复 (CRITICAL)
**预计时间**: 2-3 小时
**目标**: 修复 7 个 CRITICAL 安全漏洞

| 序号 | 文件 | 修复内容 | 关键改动 |
|:---:|------|----------|----------|
| 1 | `mcp-bridge.js` | SQL注入修复 | 参数化查询 |
| 2 | `src/domain/m11/sandbox.ts` | 移除 shell:true | 数组形式spawn |
| 3 | `src/domain/m11/adapters/executor_adapter.ts` | 命令注入防护 | 白名单+shell移除 |
| 4 | `src/infrastructure/server/mcp_api_server.ts` | 硬编码密钥 | 启动时必检密钥 |
| 5 | `src/infrastructure/server/mcp_api_server.ts` | CORS修复 | 域名白名单 |
| 6 | `mcp-bridge.js` | Shell注入修复 | subprocess标准API |
| 7 | `src/infrastructure/docker-compose.yml` | 默认凭证 | 随机密码生成 |

---

### 📦 第二批: P1 安全 + Stub (HIGH + 核心Stub)
**预计时间**: 4-6 小时
**目标**: 5个HIGH安全漏洞 + 6个核心Stub实现

| 序号 | 文件 | 修复内容 | 关键改动 |
|:---:|------|----------|----------|
| 1 | `src/infrastructure/server/mcp_api_server.ts` | 输入验证 | Zod schema验证 |
| 2 | `src/infrastructure/server/mcp_api_server.ts` | API密钥缓存 | LRU驱逐 |
| 3 | `src/domain/m11/sandbox.ts` | 不安全命令构造 | 数组形式传递命令 |
| 4 | `src/infrastructure/server/health_server.ts` | 敏感端点认证 | 分级健康检查 |
| 5 | `src/application/search_service.ts` | 搜索服务真实化 | Tavily/Exa集成 |
| 6 | `src/domain/m04/coordinator.ts` | 搜索集成 | SearchAdapter调用 |
| 7 | `src/domain/prompt_engine/dspy_compiler.ts` | LLM评估 | 真实LLM调用 |
| 8 | `src/domain/prompt_engine/layer4_nightly.ts` | 沙盒测试 | 真实用例执行 |

---

### 📦 第三批: P2 中优先级
**预计时间**: 3-4 小时
**目标**: 8个MEDIUM安全漏洞 + 6个中优先级Stub + 4个性能问题

| 序号 | 文件 | 修复内容 |
|:---:|------|----------|
| 1 | 多文件 | console.log → 统一logger |
| 2 | `src/domain/hooks.ts` | 错误处理完善 |
| 3 | `src/infrastructure/llm_adapter.ts` | 快速失败 |
| 4 | `src/infrastructure/dapr/dapr_client.ts` | 错误传播 |
| 5 | `src/domain/memory/layer1/working_memory.ts` | O(n²)算法优化 |
| 6 | `src/domain/asset_packer.ts` | 异步文件I/O |
| 7 | `src/domain/asset_packer.ts` | 路径遍历防护 |
| 8 | `src/domain/memory/pipeline/semantic_writer.ts` | XSS防护增强 |

---

### 📦 第四批: P3 收尾
**预计时间**: 2-3 小时
**目标**: LOW问题 + 测试修复 + 剩余性能问题

| 序号 | 文件 | 修复内容 |
|:---:|------|----------|
| 1 | `src/infrastructure/server/mcp_api_server.ts` | 安全头 (helmet.js) |
| 2 | `src/infrastructure/server/mcp_api_server.ts` | timingSafeEqual |
| 3 | `src/domain/m11/sandbox.test.ts` | 添加 isAvailable skip |
| 4 | `src/domain/memory/layer2/session_memory.ts` | 分页+清理机制 |
| 5 | `src/infrastructure/logger.ts` | AbortController支持 |

---

## 修复文件清单

| 批次 | 文件数 | 主要修改 |
|:----:|:------:|----------|
| 第一批 | 4 | 安全关键修复 |
| 第二批 | 6 | 安全+核心Stub |
| 第三批 | 8 | 中优先级 |
| 第四批 | 5 | 收尾 |
| **总计** | **~23** | |

---

## 验收标准

每批修复完成后：
- [ ] TypeScript 编译 0 错误
- [ ] 相关测试通过
- [ ] 无新增安全漏洞（用安全审计工具扫描）
- [ ] 代码审查无异议

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 安全修复破坏现有功能 | 高 | 每批修复后运行完整测试套件 |
| Stub实现引入新bug | 中 | 测试驱动，先写测试再实现 |
| 性能修复改变行为 | 低 | 性能基准测试前后对比 |
