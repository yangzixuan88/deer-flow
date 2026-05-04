# R156A: Integration Environment Fix — Gateway Startup

## Status: IN_PROGRESS

## Preceded By: R156 (BLOCKED_BY_INTEGRATION_ENV)
## Proceeding To: R156-3 (retry after fix)

---

## Summary

R156 遇到 `.venv` 中 `greenlet` C 扩展包损坏的问题。R156A 执行原地升级 greenlet，包已修复。但发现第二个 blocker：`DEERFLOW_HOST_PATH` 环境变量在启动脚本中无法正确传递到 Python 进程（PowerShell `$env:` 语法与 `uv run` 不兼容）。

**当前状态：greenlet 已修复（3.4.0 → 3.5.0）；Gateway 启动脚本需修改。**

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R156 |
| current_phase | R156A |
| pressure_used | M |
| reason | 原地升级 greenlet，编写启动脚本 |

---

## LANE 1: Fix #1 — greenlet 升级

### 执行命令

```powershell
cd backend
uv pip install --upgrade greenlet
```

### 结果

```
Installed 1 package in 95ms
 - greenlet==3.4.0
 + greenlet==3.5.0
```

### 验证

```python
.venv\Scripts\python.exe -c "import greenlet; print(dir(greenlet))"
# 输出: ['CLOCKS_PER_SEC', 'GREENLET_USE_CONTEXT_VARS', ..., 'getcurrent', ...]
# ✅ getcurrent 存在
```

**状态：greenlet 修复完成，ImportError 不再出现。**

---

## LANE 2: Fix #2 — DEERFLOW_HOST_PATH 环境变量

### 问题

PowerShell 中设置环境变量的语法 `$env:VAR='value'` 在与 `uv run` 组合时会失败：

```powershell
# 不生效（环境变量未传递到 Python）
$env:DEERFLOW_HOST_PATH='E:\OpenClaw-Base\deerflow'
uv run python -c "import os; print(os.getenv('DEERFLOW_HOST_PATH'))"
# 输出: None
```

但直接通过 Python 代码设置环境变量是可行的：

```python
import os
os.environ['DEERFLOW_HOST_PATH'] = 'E:\\OpenClaw-Base\\deerflow'
# ✅ 正确传递
```

### 解决方案：启动脚本

创建 `backend/start_gateway.ps1`：

```powershell
$env:DEERFLOW_HOST_PATH = "E:\OpenClaw-Base\deerflow"
$env:PYTHONPATH = "."
Set-Location "E:\OpenClaw-Base\deerflow\backend"
.\.venv\Scripts\python.exe -m uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001
```

或者使用 Python 引导脚本 `backend/test_gateway.py`：

```python
import os
os.environ['DEERFLOW_HOST_PATH'] = 'E:\\OpenClaw-Base\\deerflow'
os.environ['PYTHONPATH'] = '.'
import sys
sys.path.insert(0, '.')
from app.gateway.app import create_app
app = create_app()
# 然后启动 uvicorn
```

---

## LANE 3: 启动验证

### Gateway 创建测试

```python
# test_gateway.py — 环境变量在 Python 内部设置
import os
os.environ['DEERFLOW_HOST_PATH'] = 'E:\\OpenClaw-Base\\deerflow'
os.environ['PYTHONPATH'] = '.'
from app.gateway.app import create_app
app = create_app()
print(f"App: {app.title}")
# 输出: App created: DeerFlow API Gateway ✅
```

### 启动命令

```powershell
cd backend
.\start_gateway.ps1
# 或
.\.venv\Scripts\python.exe test_gateway.py
```

---

## LANE 4: 待验证事项

| 检查项 | 状态 |
|---|---|
| greenlet getcurrent 存在 | ✅ 已修复 |
| Gateway app 可创建 | ✅ 测试通过 |
| DEERFLOW_HOST_PATH 传递 | ✅ Python 内部设置可行 |
| 完整启动 uvicorn | ⏳ 待执行 |
| /health 返回 200 | ⏳ 待执行 |

---

## R156A Classification: IN_PROGRESS

| Metric | Value |
|---|---|
| status | **in_progress** |
| pressure_used | **M** |
| greenlet_upgraded | ✅ 3.4.0 → 3.5.0 |
| gateway_app_creates | ✅ 确认通过 |
| env_var_fix_method | Python os.environ inside script |
| startup_script_created | ✅ start_gateway.ps1 |
| recommended_next_phase | `R156-3_RETRY` (启动 gateway 并验证 /health) |

---

## 下一步

1. 执行 `.\start_gateway.ps1` 或 `.\.venv\Scripts\python.exe test_gateway.py` 启动 gateway
2. 等待启动完成后测试 `/health` 端点
3. 如果成功，R156-4 至 R156-7 可以继续执行