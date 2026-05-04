import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path

from app.m10.engine import ClarificationEngine
from app.m10.models import IntentProfile
from app.channels.message_bus import InboundMessage, InboundMessageType, MessageBus
from app.channels.store import ChannelStore

logger = logging.getLogger(__name__)

class TimeoutManager:
    def __init__(self, bus: MessageBus, store: ChannelStore, clarification_engine: ClarificationEngine):
        self.bus = bus
        self.store = store
        self.engine = clarification_engine
        self._running = False
        self._task = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scan_loop())
        logger.info("[M10 Timeout Manager] Started.")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[M10 Timeout Manager] Stopped.")

    async def _scan_loop(self):
        while self._running:
            try:
                await self._check_timeouts()
            except Exception as e:
                logger.error(f"[M10 Timeout Manager] scan loop error: {e}")
            await asyncio.sleep(30)  # 每30秒扫描一次

    async def _check_timeouts(self):
        # 扫描所有的 thread_id 并检查 M10 状态
        # 依赖于 store 提供的 list_entries（部分 ChannelStore 实现可能未提供该方法）
        if not hasattr(self.store, "list_entries") or not callable(self.store.list_entries):
            logger.debug("[M10 Timeout Manager] store 未实现 list_entries()，跳过超时扫描。")
            return
        try:
            entries = self.store.list_entries()
        except Exception as e:
            logger.warning(f"[M10 Timeout Manager] list_entries() 调用失败: {e}")
            return
        now = time.time()

        for entry in entries:
            thread_id = entry.get("thread_id")
            channel_name = entry.get("channel_name")
            chat_id = entry.get("chat_id")
            user_id = entry.get("user_id", "")
            if not thread_id or not channel_name or not chat_id:
                continue
            
            # 加载状态
            state_file = self.engine._get_state_file(thread_id)
            if not state_file.exists():
                continue
            
            profile = self.engine.load_state(thread_id)
            if not profile or profile.is_clarified():
                continue

            # issue #4：优先以 profile.last_question_at 判定"用户静默时长"。
            # 只有 engine 真正发出问题时才会写入该字段，因此 LLM 评估等后台
            # save_state 调用不会错误地重置计时器。仅当该字段缺失（历史 state
            # 或异常情况）时才回退到文件 mtime。
            if profile.last_question_at is not None:
                reference_ts = profile.last_question_at
                source = "last_question_at"
            else:
                reference_ts = state_file.stat().st_mtime
                source = "state_mtime_fallback"
            elapsed = now - reference_ts

            # 用户超过设定时间未回复，且尚未澄清
            from app.m12.unified_config import UnifiedConfig
            timeout_per_question = UnifiedConfig().get("thresholds.timeout_per_question", 120)
            cancel_window = UnifiedConfig().get("thresholds.cancel_window", 300)

            if timeout_per_question <= elapsed < cancel_window:
                # 只在进入超时区间触发一次猜测
                tag_file = state_file.parent / ".m10_timeout_triggered"
                if tag_file.exists():
                    continue

                logger.info(
                    f"[M10 Timeout Manager] Thread {thread_id} timeout "
                    f"(elapsed={elapsed:.1f}s via {source}). Triggering auto-guess..."
                )
                # 记录触发
                tag_file.touch()

                guess_msg = (
                    "（系统检测到您2分钟未回复，M10引擎已为您自动启用默认/猜测设置，"
                    "并准备开始执行。如果您想取消，请在5分钟内输入『取消』。）"
                )

                # 发送提示
                from app.channels.message_bus import OutboundMessage
                outbound = OutboundMessage(
                    channel_name=channel_name,
                    chat_id=chat_id,
                    thread_id=thread_id,
                    text=guess_msg,
                    metadata={"m10_synthetic": True, "reason": "timeout_auto_guess"},
                )
                await self.bus.publish_outbound(outbound)

                # 修改状态：显式放行并清空 last_question_at（用户已"被代答"）。
                profile.clarity_score = 1.0
                profile.last_question_at = None
                profile.refresh_task_signature()
                self.engine.save_state(thread_id, profile)

                # issue #7：合成 inbound 仍然发布，但附带 metadata 明确标记
                # 为系统生成，便于审计/日志与下游过滤器区分"真用户/假用户"。
                inbound = InboundMessage(
                    channel_name=channel_name,
                    chat_id=chat_id,
                    user_id=user_id,
                    text="你自己决定并开始执行",
                    msg_type=InboundMessageType.CHAT,
                    metadata={
                        "m10_synthetic": True,
                        "reason": "timeout_auto_guess",
                        "elapsed_seconds": round(elapsed, 2),
                        "source": source,
                    },
                )
                # 重新发布到 bus 中
                await self.bus.publish_inbound(inbound)

            # 超时5分钟，强制收尾或不做处理
            # 若5分钟仍未被响应，这里后续可以加入取消窗口逻辑
