@echo off
:: OpenClaw DeerFlow 服务启动器
:: 同时启动 LangGraph Dev Server (Port 2024) 和 Gateway (Port 8001)

title OpenClaw DeerFlow Launcher

echo ╔════════════════════════════════════════╗
echo ║     OpenClaw DeerFlow 启动器           ║
echo ╚════════════════════════════════════════╝
echo.

set "BACKEND_DIR=E:\OpenClaw-Base\deerflow\backend"

echo [1/2] 正在启动 LangGraph Dev Server (Port 2024)...
start "LangGraph Dev" cmd /k "cd /d %BACKEND_DIR% && uv run langgraph dev --no-browser --no-reload --n-jobs-per-worker 10"

echo     等待 LangGraph 初始化 (8秒)...
timeout /t 8 /nobreak >nul

echo [2/2] 正在启动 Gateway / 飞书通道 (Port 8001)...
start "DeerFlow Gateway" cmd /k "cd /d %BACKEND_DIR% && set PYTHONPATH=. && uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 --log-level info"

echo.
echo ✅ 两个服务已在独立窗口中启动！
echo.
echo    LangGraph : http://127.0.0.1:2024
echo    Gateway   : http://127.0.0.1:8001
echo    飞书大主管 : 现在发送消息测试响应
echo.
echo 关闭此窗口不影响服务运行。
pause
