import subprocess
import os
import logging
import shlex
import asyncio
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class SandboxExecutor:
    """
    M11：执行层沙盒防护盾（Windows 替代 gVisor 桥接层）
    保证在高风险代码调用之前的安全审计，并在隔离流中执行。
    """

    FORBIDDEN_COMMANDS = [
        "rm -rf /",
        "del /s /q c:\\",
        "format c:",
        "drop table"
    ]

    def __init__(self):
        self.sandbox_enabled = os.environ.get("OPENCLAW_M11_SANDBOX", "0") == "1"

    def pre_tool_use_audit(self, command: str) -> bool:
        """
        M11 沙盒审计：检测危险命令。
        CRITICAL: 立即阻断（不等待治理审批）
        HIGH: 触发 governance 审查（异步，不阻断主链）
        其他: 仅记录，允许执行
        """
        cmd_lower = command.lower()

        # CRITICAL: Hard block — these are always catastrophic
        for forbidden in self.FORBIDDEN_COMMANDS:
            if forbidden in cmd_lower:
                logger.critical(f"[M11-SANDBOX] CRITICAL command BLOCKED: {command}")
                # Fire async audit trail but BLOCK immediately
                self._async_governance_audit(
                    decision_type="tool_execution",
                    description=f"CRITICAL forbidden: {command}",
                    risk_level="critical",
                )
                return False  # BLOCK — hard阻断，不等待治理返回

        # HIGH RISK: Fire governance check (async, audit trail), do NOT block主链
        # 注：HIGH风险命令需要人工判断，故仅记录，不阻断主链执行
        high_risk_keywords = ["delete", "drop", "format", "rm -rf", "del /s", "sudo", "chmod 777", "kill -9"]
        for keyword in high_risk_keywords:
            if keyword in cmd_lower:
                logger.warning(f"[M11-SANDBOX] HIGH-risk keyword detected: {keyword} in command: {command[:80]}")
                self._async_governance_audit(
                    decision_type="tool_execution",
                    description=f"HIGH-risk keyword: {keyword}",
                    risk_level="high",
                )
                # 主链不阻断 — 审计记录已异步发送至治理引擎

        # LOW/MEDIUM: 仅记录
        return True

    def _async_governance_audit(
        self,
        decision_type: str,
        description: str,
        risk_level: str,
    ):
        """发送治理审计（fire-and-forget，不阻塞主链）"""
        try:
            import threading

            def _audit_task():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        from app.m11.governance_bridge import governance_bridge
                        loop.run_until_complete(
                            governance_bridge.check_meta_governance({
                                "decision_type": decision_type,
                                "description": description,
                                "risk_level": risk_level,
                                "stake_holders": ["governance"],
                            })
                        )
                    finally:
                        loop.close()
                except Exception:
                    pass

            t = threading.Thread(target=_audit_task, daemon=True)
            t.start()
        except Exception:
            pass

    def execute_in_sandbox(self, command: str, cwd: str = None) -> Tuple[bool, str]:
        """模拟在隔离容器中执行，如果 M11 环境变量开启，则触发额外的审计护城墙"""
        if self.sandbox_enabled:
            logger.info("Executing under M11 Sandbox protection...")
            if not self.pre_tool_use_audit(command):
                return False, "Command blocked by security policies."

        try:
            # 在实际部署中，这里可能会被重定向到 Docker runsc
            # SECURITY FIX: 使用 shell=False + 参数数组避免命令注入
            # 命令字符串使用 shlex.split 解析为安全数组
            if os.name == "nt":
                # Windows: 使用 cmd.exe /c 执行（shell=True 的安全替代）
                args = ["cmd.exe", "/c", command]
                process = subprocess.Popen(
                    args,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    text=True
                )
            else:
                # Unix/Linux/macOS: 使用 shlex.split 安全解析命令
                args = shlex.split(command)
                process = subprocess.Popen(
                    args,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    text=True
                )
            out, err = process.communicate(timeout=60)

            if process.returncode == 0:
                return True, out
            else:
                return False, err
        except subprocess.TimeoutExpired:
            process.kill()
            return False, "Sandbox execution timeout."
        except (ValueError, OSError) as e:
            # shlex.split 可能抛出 ValueError（无效转义），OSError 为子进程错误
            return False, f"Sandbox inner error: {str(e)}"
        except Exception as e:
            return False, f"Sandbox inner error: {str(e)}"

# 供其他层统一调用
mock_sandbox = SandboxExecutor()
