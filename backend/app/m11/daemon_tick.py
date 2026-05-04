import asyncio
import inspect
import threading
import logging
from typing import Callable, Dict

logger = logging.getLogger(__name__)

class DaemonTickEngine:
    """
    M11: 守护心跳系统 (Cron 载入与长进程监控)
    当被装载到 Gateway 生命周期后，它可以根据 crontabs.yaml 或者心跳配置
    自动唤起后台脱离大模型的死循环或长效监控逻辑（如监控短视频发文等）。
    支持同步和异步 task_func，使用 threading.Event 保证线程安全停止。
    """
    def __init__(self):
        self._daemons: Dict[str, threading.Thread] = {}
        # threading.Event 是线程安全的停止信号，替代 bool flag 的竞争条件
        self._stop_event = threading.Event()

    def register_daemon(self, name: str, task_func: Callable, interval: int = 60):
        """挂载一个常驻脚本舱逻辑，支持同步与异步 task_func"""
        stop_event = self._stop_event

        def _wrapper():
            logger.info(f"Daemon '{name}' started.")
            while not stop_event.is_set():
                try:
                    if inspect.iscoroutinefunction(task_func):
                        asyncio.run(task_func())
                    else:
                        task_func()
                except Exception as e:
                    logger.error(f"Daemon '{name}' execution failed: {e}")
                # wait(timeout) 在 stop_event 触发时立即返回，不必等完整 interval
                stop_event.wait(timeout=interval)
            logger.info(f"Daemon '{name}' gracefully stopped.")

        t = threading.Thread(target=_wrapper, daemon=True, name=f"daemon_{name}")
        self._daemons[name] = t

    def register_governance_drift_daemon(self, interval: int = 3600):
        """
        注册治理漂移检测 daemon — 定期检查 doctrine drift 并触发演化。
        这是 R19 LongHorizonDoctrineLayer 的触发入口。
        """
        from app.m11.governance_bridge import governance_bridge

        async def drift_check():
            try:
                logger.info("[GovernanceDriftDaemon] Running doctrine drift check...")
                record = await governance_bridge.check_doctrine_drift()
                raw = record.subprocess_result if hasattr(record, 'subprocess_result') else None

                # Write drift detection result to governance bridge outcome log
                # so it is persisted and visible to main-chain consumers
                has_drift = bool(raw and raw.get('has_drift'))
                signals = raw.get('signals', []) if raw else []
                if has_drift:
                    logger.warning(f"[GovernanceDriftDaemon] {len(signals)} doctrine drift signal(s) detected")
                    await governance_bridge.record_outcome(
                        outcome_type="doctrine_drift_detected",
                        actual_result=1.0,
                        predicted_result=0.5,
                        context={
                            "source_id": "governance_drift_daemon",
                            "task_goal": "Doctrine drift detection",
                            "tool_calls": len(signals),
                            "total_tokens": 0,
                            "total_duration_ms": 0,
                            "result_quality": 0.5,
                            "drift_signals": signals[:3],
                            "action": "evolve_doctrine_pending",
                        },
                    )
                    for sig in signals[:3]:
                        await governance_bridge.evolve_doctrine({"doctrine_id": sig.get('doctrine_id')})
                else:
                    logger.debug("[GovernanceDriftDaemon] No doctrine drift detected")
            except Exception as e:
                logger.error(f"[GovernanceDriftDaemon] Drift check failed: {e}")

        self.register_daemon("governance_drift_check", drift_check, interval)

    def start(self):
        self._stop_event.clear()
        for name, t in self._daemons.items():
            t.start()
            logger.info(f"M11 - Daemon Tick Engine initiated component: {name}")

    def stop(self):
        self._stop_event.set()
        for t in self._daemons.values():
            if t.is_alive():
                t.join(timeout=2.0)
        logger.info("M11 - Daemon Tick Engine has been halted.")

# 对外导出单例供 Gateway 或主循环装载
tick_engine = DaemonTickEngine()
