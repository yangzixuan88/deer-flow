import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4
import time

logger = logging.getLogger(__name__)

from app.m04.registry_db import DB_PATH

class RegistryManager:
    """
    M04: 三系统协同库(Registry)的操作入口。负责提供高内聚的CRUD服务。
    这使得 M08 经验系统可以通过此接口反哺 M10 和 LangGraph，
    形成“解析-执行-复盘”闭环的数据总线。
    """
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ==========================
    # workflows (SOP 组件化管理)
    # ==========================
    def save_workflow(self, name: str, category: str, sop_source: str, nodes: dict, edges: dict, risk_level: str = "low", cost_estimate: dict = None) -> str:
        flow_id = f"flow_{uuid4().hex[:8]}"
        now = int(time.time())
        try:
            with self._get_connection() as conn:
                conn.execute(
                    '''INSERT INTO workflows 
                       (flow_id, name, category, sop_source, nodes_json, edges_json, created_at, updated_at, risk_level, cost_estimate_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (flow_id, name, category, sop_source, json.dumps(nodes), json.dumps(edges), now, now, risk_level, json.dumps(cost_estimate or {}))
                )
            logger.info(f"[M04] Saved reusable workflow: {name} ({flow_id})")
            return flow_id
        except Exception as e:
            logger.error(f"[M04] Error saving workflow: {e}")
            return None

    def get_workflow(self, flow_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM workflows WHERE flow_id=?", (flow_id,)).fetchone()
                if row:
                    data = dict(row)
                    data['nodes_json'] = json.loads(data['nodes_json']) if data['nodes_json'] else {}
                    data['edges_json'] = json.loads(data['edges_json']) if data['edges_json'] else {}
                    data['cost_estimate_json'] = json.loads(data['cost_estimate_json']) if data['cost_estimate_json'] else {}
                    return data
        except Exception as e:
            logger.error(f"[M04] Error fetching workflow {flow_id}: {e}")
        return None

    # ==========================
    # tasks (任务执行状态与 DAG Boulder 记录)
    # ==========================
    def save_task(self, goal: str, dag: dict, total_tokens: int = 0) -> str:
        task_id = f"task_{uuid4().hex[:8]}"
        now = int(time.time())
        try:
            with self._get_connection() as conn:
                conn.execute(
                    '''INSERT INTO tasks 
                       (task_id, goal, status, dag_json, total_tokens, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (task_id, goal, "pending", json.dumps(dag), total_tokens, now, now)
                )
            return task_id
        except Exception as e:
            logger.error(f"[M04] Error saving task: {e}")
            return None

    def update_task_status(self, task_id: str, status: str, additional_tokens: int = 0):
        now = int(time.time())
        try:
            with self._get_connection() as conn:
                conn.execute(
                    '''UPDATE tasks SET status = ?, updated_at = ?, total_tokens = total_tokens + ? WHERE task_id = ?''',
                    (status, now, additional_tokens, task_id)
                )
        except Exception as e:
            logger.error(f"[M04] Error updating task {task_id}: {e}")

# 供全局使用
registry_manager = RegistryManager()
