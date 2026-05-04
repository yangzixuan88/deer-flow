import functools
import logging
import asyncio

from app.m11.sandbox_executor import mock_sandbox

logger = logging.getLogger(__name__)

def sandbox_protected(func):
    """
    [LEGACY — M11 沙盒保护已由 SandboxExecutor.pre_tool_use_audit() 承担]
    此装饰器保留作为"声明式沙盒意图"的文档标记，不推荐在新代码中使用。
    实际沙盒执行请直接使用 mock_sandbox.pre_tool_use_audit()。

    M11 沙盒保护墙装饰器
    用于包裹在 LangGraph Tools 或 skills 目录下的高危或执行类功能，拦截危险指令。
    对于 Windows MVP 阶段，主要生效于 pre_tool_use_audit 黑名单机制。
    待 Linux 环境就绪后，此包装器可被平滑重定向至 runsc 内部执行。

    注意: 此装饰器在代码库中无任何实际使用，仅作为遗留文档保留。
    请勿在新代码中使用此装饰器——使用 SandboxExecutor.pre_tool_use_audit() 代替。
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        command = kwargs.get('command') or kwargs.get('cmd') or (args[0] if args and isinstance(args[0], str) else None)
        if command and isinstance(command, str):
            # 高权限模式：审计但不阻塞 — 智能体保有完全执行权
            mock_sandbox.pre_tool_use_audit(command)

        return await func(*args, **kwargs)

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        command = kwargs.get('command') or kwargs.get('cmd') or (args[0] if args and isinstance(args[0], str) else None)
        if command and isinstance(command, str):
            # 高权限模式：审计但不阻塞 — 智能体保有完全执行权
            mock_sandbox.pre_tool_use_audit(command)

        return func(*args, **kwargs)

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
