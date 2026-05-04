import os
import socket
import platform
from pathlib import Path

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def generate_env():
    project_root = Path(__file__).parent.parent.parent.parent
    infra_dir = project_root / "src" / "infrastructure"
    env_example = infra_dir / "env_adapter" / ".env.example"
    env_file = infra_dir / ".env"

    if not env_example.exists():
        with open(env_example, "w") as f:
            f.write("# OpenClaw System Environment Variables\n")
            f.write(f"LOCAL_IP={get_local_ip()}\n")
            f.write(f"OS_PLATFORM={platform.system()}\n")
            f.write("TUNNEL_TOKEN=your_cloudflare_tunnel_token_here\n")
            f.write("FEISHU_WEBHOOK_PORT=8080\n")

    if not env_file.exists():
        with open(env_example, "r") as f:
            content = f.read()
        with open(env_file, "w") as f:
            f.write(content)
        print(f"Generated .env at {env_file}")

if __name__ == "__main__":
    generate_env()
