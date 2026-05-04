$env:DEERFLOW_HOST_PATH = "E:\OpenClaw-Base\deerflow"
$env:PYTHONPATH = "."
Set-Location "E:\OpenClaw-Base\deerflow\backend"
.\.venv\Scripts\python.exe -m uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001