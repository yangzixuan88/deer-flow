@echo off
set "DEERFLOW_HOST_PATH=E:\OpenClaw-Base\deerflow"
set "PYTHONPATH=."
python -c "import os; print('ENV:', repr(os.environ.get('DEERFLOW_HOST_PATH')))"
