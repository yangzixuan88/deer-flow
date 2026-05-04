import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from langchain.agents.middleware import AgentMiddleware
from deerflow.agents.thread_state import ThreadState

logger = logging.getLogger(__name__)

class RalphLoopMiddleware(AgentMiddleware):
    """
    RalphLoop 中间件实现了 §05 定义的 6 步自主循环逻辑。
    步骤: OBTAIN -> REASON -> ACT -> LEARN -> PERSIST -> HEARTBEAT
    """

    def __init__(self, agent_name: str = "main", boulder_path: str = "boulder.json"):
        self.agent_name = agent_name
        self.boulder_path = boulder_path
        self.reports_dir = Path.home() / ".deerflow" / "reports"

    def _load_boulder(self) -> dict:
        if not os.path.exists(self.boulder_path):
            return {}
        try:
            with open(self.boulder_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load boulder.json: {e}")
            return {}

    def _save_boulder(self, data: dict):
        try:
            data["last_updated"] = datetime.now().isoformat()
            with open(self.boulder_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save boulder.json: {e}")

    async def abefore_agent(self, state: ThreadState, config: RunnableConfig) -> ThreadState:
        """OBTAIN 阶段: 从 boulder.json 加载状态并注入上下文。"""
        from pathlib import Path
        boulder = self._load_boulder()
        
        # 1. 注入 Ralph 循环状态
        loop_status = f"""
<ralph_loop_status>
- 当前节点: {boulder.get("current_node", "START")}
- 任务目标: {boulder.get("mission_goal", "N/A")}
- 进度: {boulder.get("progress_percentage", 0)}%
- 失败次数: {boulder.get("failures_count", 0)}
</ralph_loop_status>
"""
        messages = list(state.get("messages", []))
        messages.append(SystemMessage(content=loop_status))

        # 2. 注入夜间复盘报告 (仅限大主管)
        if self.agent_name != "main":
            state["messages"] = messages
            return state

        latest_report_file = self.reports_dir / "latest_report.json"
        
        try:
            with open(latest_report_file, "r", encoding="utf-8") as f:
                report = json.load(f)
                report_msg = f"""
<nightly_review_push>
日期: {report.get('date')}
摘要: {report.get('summary_text')}
模式发现: {", ".join(report.get('patterns', []))}
系统进化: {", ".join(report.get('asset_evolutions', []))}
</nightly_review_push>
"""
                messages.append(SystemMessage(content=report_msg))
                logger.info(f"Nightly report for {report.get('date')} injected into context.")
        except Exception as e:
            logger.error(f"Failed to inject nightly report: {e}")

        state["messages"] = messages
        return state

    async def aafter_agent(self, state: ThreadState, config: RunnableConfig) -> ThreadState:
        """LEARN & PERSIST 阶段: 根据 Agent 结果更新 boulder.json。"""
        # Note: In a real implementation, we might parse the agent's output for node transitions.
        # For the foundation, we just update the timestamp and basic stats.
        boulder = self._load_boulder()
        
        # Hard Context Reset Logic (§05.2.3)
        # This is a placeholder for actual token-based reset which happens in TokenUsageMiddleware
        # But we can trigger a state sync here.
        
        # To be fully compliant with §05, we should expect a 'boulder_update' in the agent's output
        # or handle automatic transitions.
        
        self._save_boulder(boulder)
        return state
