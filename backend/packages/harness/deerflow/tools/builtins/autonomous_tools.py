import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from langchain_core.tools import tool
from deerflow.assets.asset_manager import AssetManager, DigitalAsset
from deerflow.agents.thread_state import ThreadState

logger = logging.getLogger(__name__)

@tool
def update_mission_state(node: str, progress: int, goal: Optional[str] = None) -> str:
    """
    更新 boulder.json 中的任务状态 (§05)。
    用于在 Ralph Loop 节点间（OBTAIN, REASON, ACT, LEARN, PERSIST, HEARTBEAT）进行切换。
    """
    try:
        boulder_path = "boulder.json"
        data = {}
        if Path(boulder_path).exists():
            with open(boulder_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        data["current_node"] = node
        data["progress_percentage"] = progress
        if goal:
            data["mission_goal"] = goal
        
        with open(boulder_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        return f"任务状态已更新为 {node} ({progress}%)."
    except Exception as e:
        return f"更新任务状态失败: {str(e)}"

@tool
def persist_digital_asset(id: str, name: str, category: str, content: Any, scoring_adjustment: Optional[Dict] = None) -> str:
    """
    在资产库 (DAS) 中保存或更新数字资产 (§07)。
    分类包括: tools (工具), resources (资源), workflows (工作流), experiences (经验), 
    cognitive (认知), networks (网络), prompts (提示词), preferences (偏好), knowledge-maps (知识图谱)。
    """
    try:
        manager = AssetManager()
        asset = DigitalAsset(id=id, name=name, category=category, content=content)
        if scoring_adjustment:
            asset.scoring.update(scoring_adjustment)
            asset.calculate_score()
        
        manager.register_asset(asset)
        return f"资产 {id} 已持久化至 {category} (分阶: {asset.tier})。"
    except Exception as e:
        return f"持久化资产失败: {str(e)}"

@tool
def propose_evolution_task(task_description: str, priority: int = 5, reason: Optional[str] = None) -> str:
    """
    为系统的自主进化提出新任务 (§10)。
    夜间复盘引擎利用此工具建议优化项或新能力的开发。
    """
    try:
        tasks_dir = Path("mission/evolution")
        tasks_dir.mkdir(parents=True, exist_ok=True)
        
        task_id = f"evo-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        task_data = {
            "id": task_id,
            "description": task_description,
            "priority": priority,
            "reason": reason or "由学习系统自动发现并提出",
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        with open(tasks_dir / f"{task_id}.json", "w", encoding="utf-8") as f:
            json.dump(task_data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"已提出进化任务: {task_id}")
        return f"进化任务 {task_id} 提出成功。"
    except Exception as e:
        return f"提出进化任务失败: {str(e)}"
