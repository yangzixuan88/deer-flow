"""
R156A Gateway Startup Script - Debug version
Sets DEERFLOW_HOST_PATH in Python, then starts uvicorn
"""
import os
import sys

# Debug: print env vars BEFORE setting
print(f"BEFORE: DEERFLOW_HOST_PATH = {os.environ.get('DEERFLOW_HOST_PATH', 'NOT SET')}")

# Set environment variables BEFORE any other imports
os.environ['DEERFLOW_HOST_PATH'] = 'E:\\OpenClaw-Base\\deerflow'
os.environ['PYTHONPATH'] = '.'

# Debug: print env vars AFTER setting
print(f"AFTER: DEERFLOW_HOST_PATH = {os.environ.get('DEERFLOW_HOST_PATH', 'NOT SET')}")

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(__file__))

# Now import and start uvicorn
import uvicorn
from app.gateway.app import create_app

if __name__ == "__main__":
    app = create_app()
    print(f"Starting DeerFlow Gateway on 0.0.0.0:8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")