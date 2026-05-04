#!/bin/bash
cd /e/OpenClaw-Base/deerflow/backend
export DEERFLOW_HOST_PATH="E:\\OpenClaw-Base\\deerflow"
export PYTHONPATH="."
./.venv/Scripts/python.exe -m uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001