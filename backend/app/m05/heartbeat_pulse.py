import logging
import datetime
import json
import os
from app.runtime_paths import upgrade_center_state_dir
from app.m11.daemon_tick import DaemonTickEngine

logger = logging.getLogger(__name__)

class PulseCoordinator:
    """
    M05 全局心跳协调器官 (Heartbeat)
    彻底接管早期的 cron/jobs.json，包装为线程安全的 Tick Hook。
    """
    def __init__(self, daemon: DaemonTickEngine):
        self.daemon = daemon
        self._register_pulses()

    def _register_pulses(self):
        from app.m12.unified_config import UnifiedConfig
        # 1. 极速频率心跳 (网络连通与活性探测)
        self.daemon.register_daemon(
            name="sys_heartbeat",
            interval=UnifiedConfig().get("thresholds.heartbeat_interval_seconds", 300),
            task_func=self.pulse_check
        )

        # 2. 定时深夜复盘 (长达 10 分钟一次查询)
        self.daemon.register_daemon(
            name="night_reflection",
            interval=600,
            task_func=self.nightly_reflection
        )

    def pulse_check(self):
        """例行小周期的网络唤醒/状态心跳与 M03 系统扫描自检"""
        # logger.debug("[M05] Pulse Check Heartbeat Tick.")
        from app.m03.self_hardening import shars_instance
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(shars_instance.check_logs_for_anomalies())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(shars_instance.check_logs_for_anomalies())

    def nightly_reflection(self):
        """02:00 夜间复盘：深度记忆整理、全天对话压缩、技能衍生"""
        now = datetime.datetime.now()

        # R163 FIX: Catch-up 机制 — 若 Gateway 在 02:10 后启动，
        # 则在启动后第一次心跳时补火夜间演化（仅限当天未执行过的情况）。
        # 这解决了"Gateway 启动时已过时间窗口导致当天永不触发"的设计缺陷。
        catch_up_window = (now.hour == 2 and now.minute > 10) or (now.hour == 3 and now.minute == 0)
        in_primary_window = now.hour == 2 and 0 <= now.minute <= 10

        if in_primary_window or catch_up_window:
            today = datetime.date.today().isoformat()
            state_dir = str(upgrade_center_state_dir())
            daily_guard_path = os.path.join(state_dir, f"nightly_evolve_done_{today}.json")

            # 检查今天是否已执行过（双重防护：时间窗口 + 文件守卫）
            if not os.path.exists(daily_guard_path):
                logger.info(f"[M05] 触发夜间无人值守复盘 (Nightly Reflection) — 时间窗口={now.hour}:{now.minute:02d}...")
                self._execute_reflection()
            else:
                logger.debug(f"[M05] 时间窗口匹配但今晚已执行过，跳过 — {now.hour}:{now.minute:02d}")

    def _execute_reflection(self):
        """连接 AgentMemory 或触发后端大模型去汇总当天的 Registry 记录"""
        import asyncio

        # R163 FIX: 每日只执行一次，防止重复触发
        today = datetime.date.today().isoformat()
        state_dir = str(upgrade_center_state_dir())
        daily_guard_path = os.path.join(state_dir, f"nightly_evolve_done_{today}.json")

        if os.path.exists(daily_guard_path):
            logger.debug("[M05] 今晚的 nightly_evolution 已执行过，跳过")
            return

        os.makedirs(state_dir, exist_ok=True)
        with open(daily_guard_path, "w") as f:
            json.dump({"date": today, "executed": True}, f)

        logger.info("[M05] 开始挂载执行 M08 增强型日终体验学习系统 (UEF)...")
        from app.m08.learning_system import uef_instance
        try:
            # heartbeat ticks might be sync, we wrap the async call robustly
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(uef_instance.evolve())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(uef_instance.evolve())
        except Exception as e:
            logger.error(f"[M05] 执行 M08 UEF 时发生异常: {e}")

# 使用示范:
# daemon_engine = DaemonTickEngine()
# pulse_coordinator = PulseCoordinator(daemon_engine)
