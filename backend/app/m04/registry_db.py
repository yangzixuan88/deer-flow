import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

# Use OPENCLAW_BASE so the path resolves correctly on Windows (HOME is Unix-only).
DB_PATH = os.path.join(
    os.environ.get("OPENCLAW_BASE", r"E:\OpenClaw-Base"),
    ".openclaw",
    "flows",
    "registry.sqlite",
)

def init_registry_db():
    """保证 registry.sqlite 创建所需的结构"""
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 表1: workflows (工作流组件及元数据)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflows (
                flow_id TEXT PRIMARY KEY,
                name TEXT,
                category TEXT,
                sop_source TEXT,
                nodes_json TEXT,
                edges_json TEXT,
                created_at INTEGER,
                updated_at INTEGER,
                risk_level TEXT,
                cost_estimate_json TEXT
            )
        ''')
        
        # 表2: search_assets (搜索提炼缓存、工具提纯缓存)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_assets (
                asset_id TEXT PRIMARY KEY,
                query TEXT,
                summary TEXT,
                confidence REAL,
                results_json TEXT,
                created_at INTEGER
            )
        ''')

        # 表3: tasks (拆解的独立 DAG boulder 结构)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                goal TEXT,
                status TEXT,
                dag_json TEXT,
                total_tokens INTEGER,
                created_at INTEGER,
                updated_at INTEGER
            )
        ''')
        
        # 表4: boulder_records (经验复盘用的执行追踪)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS boulder_records (
                record_id TEXT PRIMARY KEY,
                task_id TEXT,
                step_name TEXT,
                success BOOLEAN,
                latency_ms INTEGER,
                tokens_used INTEGER,
                log_json TEXT,
                created_at INTEGER
            )
        ''')
        
        conn.commit()
        logger.info("M04 - Registry tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize registry db: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    init_registry_db()
    print("M04 DB Schema Upgrade OK")
