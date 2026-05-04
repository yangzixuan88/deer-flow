# R53 · 容器重建后运行态一致性验证（Source Fix → Image → Container → Health Output）

**目标**：验证 R52 源码修复已真实进入运行态，`/health/governance` 的 `external_backends` 不再报错
**执行结果**：✅ 完全通过，R52 修复已完全收口

---

## 1. 运行容器新旧状态核验结果

### 镜像新旧对比

| 属性 | 旧镜像 | 新镜像 | 变化 |
|---|---|---|---|
| Image ID | `898ddc2c68e3` | `c29c7223eebe` | ✅ 不同（已重建） |
| 创建时间 | `2026-04-20T22:40:04` | `2026-04-21T08:18:21` | ✅ 新于源码修复时间 |
| 容器启动时间 | `2026-04-20T22:40:08` | `2026-04-21T00:22:27` | ✅ 新容器已启动 |
| 镜像大小 | 5.13GB | 5.13GB（相同 build context） | 一致 |

**结论**：旧镜像已废弃，新镜像已构建并投入使用。

### 容器内文件验证

```bash
# 容器内直接 import 测试（强证据）
docker exec infrastructure-openclaw-app-1 python3 -c "
    import sys; sys.path.insert(0, '/app/backend')
    from app.m11.external_backend_selector import get_backend_manifest
    result = get_backend_manifest()
    print('backends:', result.get('backends'))
    print('error:', result.get('error'))
"
# ✅ 输出：backends: ['scrapling', 'agent_s', 'bytebot'], error: None
```

**结论**：容器内 Python 模块行为已与源码修复一致，`get_backend_manifest()` 直接成功，无 `dataclass` 错误。

---

## 2. 最小重建方案与已执行修改

### 执行的命令

```bash
cd backend/src/infrastructure
docker compose build --no-cache openclaw-app  # 镜像重建
docker compose up -d --no-deps openclaw-app   # 容器重建（不重拉全栈）
sleep 15  # 等待 Gateway 启动
```

### 修改内容

**无新增代码修改** — 重建复用了 R52 已修复的源文件：
- `backend/app/m11/external_backend_selector.py` 第 38 行：`from dataclasses import dataclass`（R52 已添加）

### 重建范围

- ✅ 仅重建 `openclaw-app` 服务
- ✅ 不影响 Redis、Dapr、n8n、qdrant 等依赖服务
- ✅ 保留 `openclaw-data` volume（thread 数据不丢失）
- ✅ 保留 `config.yaml` bind mount

---

## 3. 容器内修复生效核验结果

### 三层证据链（全部通过）

| 层级 | 验证方法 | 结果 |
|---|---|---|
| **容器内模块行为** | `docker exec ... python3 -c "from app.m11.external_backend_selector import get_backend_manifest"` | ✅ 无错误，返回真实 backends |
| **HTTP health 输出** | `GET /health/governance` → `external_backends.error` | ✅ `None`，不再是 `"name 'dataclass' is not defined"` |
| **镜像/容器 ID** | `docker inspect` | ✅ 新镜像（`c29c7223eebe`），旧镜像（`898ddc2c68e3`）已废弃 |

---

## 4. `/health/governance` 运行态验证结果

### 修复前后对比

| 字段 | 修复前（容器旧镜像） | 修复后（容器新镜像） |
|---|---|---|
| `external_backends.error` | `"name 'dataclass' is not defined"` ❌ | `null` ✅ |
| `external_backends.backends` | `[]` | `["scrapling", "agent_s", "bytebot"]` ✅ |
| `external_backends.total_safe_capabilities` | `null` | `13` ✅ |
| `external_backends.total_quarantined` | `null` | `11` ✅ |
| `external_backends.capabilities.scrapling` | `{}` | `{"safe": [...], "quarantined": [...]}` ✅ |
| `external_backends.capabilities.agent_s` | `{}` | `{"safe": [...], "forbidden_parallel": [...]}` ✅ |
| `external_backends.capabilities.bytebot` | `{}` | `{"safe": [...], "forbidden_parallel": [...]}` ✅ |

### governance readiness 一致性（最终状态）

| 检查项 | `/health/ready` | `/health/governance` | 一致性 |
|---|---|---|---|
| `ts_engine_available` | `true` | `true` | ✅ 完全一致 |
| `governance_bridge status` | `ready` | `ready` | ✅ 完全一致 |
| overall | `ready` | `CORE_ARCHITECTURE_FROZEN`（语义不同层级，无矛盾） | ✅ 一致 |

---

## 5. 回归验证结果

### R1：确认旧镜像/旧容器问题是否存在
- ✅ 已确认：旧镜像 ID `898ddc2c68e3`（创建于 2026-04-20 22:40），新镜像 ID `c29c7223eebe`（创建于 2026-04-21 08:18）

### R2：完成最小 rebuild/restart，并让修复进入运行态
- ✅ 镜像已重建（`--no-cache`），容器已 recreate 并 start
- ✅ 仅影响 `openclaw-app`，依赖服务未动

### R3：`/health/governance` 的 `external_backends` 不再报 dataclass 错误
- ✅ `error: null`，`backends: ["scrapling", "agent_s", "bytebot"]`，`total_safe_capabilities: 13`

### R4：容器内代码/行为与源码修复一致
- ✅ 容器内 `get_backend_manifest()` 直接成功，无 `NameError`

### R5：不引入新平行部署系统，不破坏现有主链边界
- ✅ 无新服务，无新健康系统
- ✅ Redis（`healthy`）、Dapr（`Up 3h`）、n8n/qdrant 等依赖服务未受影响

### R6：本轮输出足以判断 R52 这一簇是否已完全收口
- ✅ 源码修复 → 新镜像 → 新容器 → health 输出，四层全部对齐
- ✅ R52 修复簇**正式收口**

---

## 6. 本轮后的全局判断

```
源码（external_backend_selector.py）✅ = 新镜像 ✅ = 新容器 ✅ = health 输出 ✅

R52 修复簇：
  - dataclass import 缺失（R52 根因）→ 源码已修 ✅ → 新镜像已构建 ✅
  - 新容器已启动 ✅ → /health/governance external_backends 恢复正常 ✅

governance health 契约整体状态：
  - /health/ready governance 部分：ready / ts_engine_available=true ✅（R52 确认）
  - /health/governance external_backends：backends 列表 + capabilities 详情 ✅（R53 确认）
  - /health/governance governance 部分：ready / ts_engine_available=true ✅（R52 确认）
  - 三层健康端点语义一致，无矛盾 ✅

结论：gateway/governance health 这一簇已完全收口，无残留不确定性。
```

---

## 7. 下一轮最优先方向建议

**推荐 Round 54：Feishu 通道端到端验证（R50 续）**

**原因**：
1. Gateway/Governance 健康契约已完整可信，无遗留问题
2. R50 已验证 Feishu 通道代码链完整（ChannelManager → LangGraph → reply card），但无真实消息触发
3. 现在 governance bridge 可用，可测试 `check_meta_governance()` / `record_outcome()` 等真实 governance 调用
4. 下一步应验证外部通道是否能真实触发 governance 决策循环

**备选方向**：M07 Asset System 健康验证（`dpbs_instance` 在 `/health/ready` 中是否暴露状态？）

**不建议继续 health deeper**：健康契约已完整，继续深挖只会发现无关边界问题。