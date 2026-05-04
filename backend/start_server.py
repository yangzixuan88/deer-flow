"""
启动 uvicorn 并把 stdout+stderr 同时写入日志文件 + 打印到控制台。
"""
import subprocess, sys, threading, os

LOG_FILE = r"C:\Users\win\AppData\Local\Temp\uvicorn_live.log"
BACKEND  = r"E:\OpenClaw-Base\deerflow\backend"
UVICORN  = r"E:\OpenClaw-Base\deerflow\backend\.venv\Scripts\uvicorn.exe"

def tee(src, log_path):
    """读取进程输出并写入文件；不向控制台打印，避免 GBK 编码崩溃。"""
    with open(log_path, "w", encoding="utf-8", errors="replace", buffering=1) as log:
        for line in iter(src.readline, b""):
            text = line.decode("utf-8", errors="replace")
            log.write(text)

proc = subprocess.Popen(
    [UVICORN, "app.gateway.app:app",
     "--host", "0.0.0.0", "--port", "8001", "--log-level", "info",
     "--app-dir", BACKEND],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    cwd=BACKEND,
)

t = threading.Thread(target=tee, args=(proc.stdout, LOG_FILE), daemon=True)
t.start()
proc.wait()
