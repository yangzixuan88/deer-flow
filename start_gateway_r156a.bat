@echo off
:: R156A Gateway Startup Script
:: Sets DEERFLOW_HOST_PATH before starting uvicorn

set "DEERFLOW_HOST_PATH=E:\OpenClaw-Base\deerflow"
set "PYTHONPATH=."

cd /d "E:\OpenClaw-Base\deerflow\backend"

echo Starting DeerFlow Gateway with DEERFLOW_HOST_PATH=%DEERFLOW_HOST_PATH%
echo.

uv run python -m uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 --log-level info