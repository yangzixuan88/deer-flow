#!/usr/bin/env python3
"""
OpenClaw Backup & Restore Manager
==================================
Phase 14: 生产准备 - 容灾恢复组件

功能:
- 状态数据备份 (Redis + SQLite)
- 自动备份调度
- 增量备份支持
- 跨区域复制准备
- 一键恢复

用法:
  python backup_manager.py backup          # 创建备份
  python backup_manager.py restore <id>   # 恢复指定备份
  python backup_manager.py list           # 列出所有备份
  python backup_manager.py schedule       # 启动定时备份守护进程
"""

import os
import sys
import json
import shutil
import sqlite3
import hashlib
import datetime
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

# ============================================
# 配置
# ============================================

BACKUP_DIR = Path(__file__).parent.parent.parent / "backups"
REDIS_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "redis"
SQLITE_PATH = Path(__file__).parent.parent.parent / "assets" / "Asset_Manifest.sqlite"
RETENTION_DAYS = 30
INCREMENTAL_THRESHOLD_HOURS = 6

# ============================================
# 备份元数据管理
# ============================================

METADATA_FILE = BACKUP_DIR / "backup_metadata.json"

def load_metadata() -> Dict[str, Any]:
    """加载备份元数据"""
    if not METADATA_FILE.exists():
        return {"backups": [], "last_incremental": None}
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_metadata(metadata: Dict[str, Any]) -> None:
    """保存备份元数据"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

def calculate_file_hash(filepath: Path) -> str:
    """计算文件 SHA256 哈希"""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

# ============================================
# 备份核心逻辑
# ============================================

def backup_sqlite(db_path: Path, backup_folder: Path) -> Dict[str, Any]:
    """备份 SQLite 数据库"""
    result = {
        "file": db_path.name,
        "size_bytes": 0,
        "hash": "",
        "status": "pending"
    }

    if not db_path.exists():
        result["status"] = "skipped"
        result["note"] = "Database file not found"
        return result

    dest_path = backup_folder / db_path.name
    try:
        # 使用 SQLite 在线备份 API
        conn = sqlite3.connect(str(db_path))
        backup_conn = sqlite3.connect(str(dest_path))
        conn.backup(backup_conn)
        backup_conn.close()
        conn.close()

        result["size_bytes"] = dest_path.stat().st_size
        result["hash"] = calculate_file_hash(dest_path)
        result["status"] = "success"
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)

    return result

def backup_redis(backup_folder: Path) -> Dict[str, Any]:
    """备份 Redis 数据"""
    result = {
        "dir": str(REDIS_DATA_DIR),
        "size_bytes": 0,
        "file_count": 0,
        "status": "pending"
    }

    if not REDIS_DATA_DIR.exists():
        result["status"] = "skipped"
        result["note"] = "Redis data directory not found"
        return result

    redis_backup_dir = backup_folder / "redis_data"
    try:
        shutil.copytree(REDIS_DATA_DIR, redis_backup_dir, dirs_exist_ok=True)

        # 计算总大小
        total_size = sum(f.stat().st_size for f in redis_backup_dir.rglob("*") if f.is_file())
        file_count = sum(1 for f in redis_backup_dir.rglob("*") if f.is_file())

        result["size_bytes"] = total_size
        result["file_count"] = file_count
        result["status"] = "success"
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)

    return result

def backup_config(backup_folder: Path) -> Dict[str, Any]:
    """备份配置文件"""
    result = {
        "configs": [],
        "status": "success"
    }

    project_root = Path(__file__).parent.parent.parent
    config_files = [
        "docker-compose.yml",
        ".env.example",
        "typedoc.json",
    ]

    for config_file in config_files:
        src = project_root / config_file
        if src.exists():
            dest = backup_folder / config_file
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            result["configs"].append(config_file)

    return result

def create_backup(incremental: bool = False) -> Optional[str]:
    """创建备份"""
    print(f"[Backup] Creating {'incremental' if incremental else 'full'} backup...")

    # 创建备份目录
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_id = f"backup_{timestamp}"
    backup_folder = BACKUP_DIR / backup_id
    backup_folder.mkdir(parents=True, exist_ok=True)

    # 备份各组件
    backup_info = {
        "id": backup_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "type": "incremental" if incremental else "full",
        "components": {},
        "total_size_bytes": 0,
        "status": "in_progress"
    }

    # SQLite
    sqlite_result = backup_sqlite(SQLITE_PATH, backup_folder)
    backup_info["components"]["sqlite"] = sqlite_result
    if sqlite_result["status"] == "success":
        backup_info["total_size_bytes"] += sqlite_result["size_bytes"]

    # Redis
    redis_result = backup_redis(backup_folder)
    backup_info["components"]["redis"] = redis_result
    if redis_result["status"] == "success":
        backup_info["total_size_bytes"] += redis_result["size_bytes"]

    # 配置
    config_result = backup_config(backup_folder)
    backup_info["components"]["config"] = config_result

    # 计算总大小
    backup_info["total_size_bytes"] = sum(
        c.get("size_bytes", 0)
        for c in backup_info["components"].values()
        if isinstance(c, dict)
    )

    # 保存备份信息
    backup_info["status"] = "completed"
    with open(backup_folder / "backup_info.json", "w", encoding="utf-8") as f:
        json.dump(backup_info, f, indent=2, ensure_ascii=False)

    # 更新元数据
    metadata = load_metadata()
    metadata["backups"].append({
        "id": backup_id,
        "timestamp": backup_info["timestamp"],
        "type": backup_info["type"],
        "size_bytes": backup_info["total_size_bytes"],
        "status": "completed"
    })
    if incremental:
        metadata["last_incremental"] = backup_id
    save_metadata(metadata)

    print(f"[Backup] Completed: {backup_id}")
    print(f"  - Total size: {backup_info['total_size_bytes'] / 1024 / 1024:.2f} MB")
    print(f"  - Location: {backup_folder}")

    return backup_id

def restore_backup(backup_id: str) -> bool:
    """恢复指定备份"""
    backup_folder = BACKUP_DIR / backup_id
    backup_info_file = backup_folder / "backup_info.json"

    if not backup_info_file.exists():
        print(f"[Restore] Backup not found: {backup_id}")
        return False

    with open(backup_info_file, "r", encoding="utf-8") as f:
        backup_info = json.load(f)

    print(f"[Restore] Restoring backup: {backup_id}")
    print(f"[Restore] WARNING: This will overwrite current data!")

    # TODO: 添加确认提示

    # 恢复 SQLite
    sqlite_comp = backup_info.get("components", {}).get("sqlite", {})
    if sqlite_comp.get("status") == "success":
        src = backup_folder / SQLITE_PATH.name
        if src.exists():
            # 先备份当前数据库
            if SQLITE_PATH.exists():
                shutil.copy2(SQLITE_PATH, SQLITE_PATH.with_suffix(".sql.backup"))
            shutil.copy2(src, SQLITE_PATH)
            print(f"[Restore] SQLite restored: {SQLITE_PATH}")

    # 恢复 Redis
    redis_comp = backup_info.get("components", {}).get("redis", {})
    if redis_comp.get("status") == "success":
        redis_backup_dir = backup_folder / "redis_data"
        if redis_backup_dir.exists():
            # 先备份当前数据
            if REDIS_DATA_DIR.exists():
                shutil.copytree(REDIS_DATA_DIR, REDIS_DATA_DIR.with_name("redis_data.backup"), dirs_exist_ok=True)
            shutil.copytree(redis_backup_dir, REDIS_DATA_DIR, dirs_exist_ok=True)
            print(f"[Restore] Redis data restored: {REDIS_DATA_DIR}")

    print("[Restore] Completed successfully!")
    return True

def list_backups() -> List[Dict[str, Any]]:
    """列出所有备份"""
    metadata = load_metadata()
    backups = metadata.get("backups", [])

    if not backups:
        print("[Backup] No backups found")
        return []

    print(f"\n{'='*60}")
    print(f"{'ID':<30} {'TYPE':<12} {'SIZE':<12} {'TIMESTAMP'}")
    print(f"{'-'*60}")

    for backup in reversed(backups[-10:]):  # 显示最近10个
        size_mb = backup.get("size_bytes", 0) / 1024 / 1024
        print(f"{backup['id']:<30} {backup.get('type', 'full'):<12} {size_mb:>8.2f} MB  {backup.get('timestamp', '')}")

    print(f"{'='*60}")
    print(f"Total backups: {len(backups)}")

    return backups

def cleanup_old_backups(retention_days: int = RETENTION_DAYS) -> int:
    """清理过期备份"""
    metadata = load_metadata()
    backups = metadata.get("backups", [])

    cutoff = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    removed = 0

    new_backups = []
    for backup in backups:
        ts = datetime.datetime.fromisoformat(backup["timestamp"])
        if ts > cutoff:
            new_backups.append(backup)
        else:
            # 删除过期备份
            backup_folder = BACKUP_DIR / backup["id"]
            if backup_folder.exists():
                shutil.rmtree(backup_folder)
            removed += 1

    metadata["backups"] = new_backups
    save_metadata(metadata)

    if removed > 0:
        print(f"[Cleanup] Removed {removed} expired backups")
    else:
        print(f"[Cleanup] No expired backups to remove")

    return removed

# ============================================
# 定时备份守护进程
# ============================================

def run_backup_daemon(interval_hours: int = 6):
    """运行定时备份守护进程"""
    import time

    print(f"[BackupDaemon] Starting backup daemon (interval: {interval_hours}h)")
    print(f"[BackupDaemon] Press Ctrl+C to stop")

    while True:
        # 检查是否需要增量备份
        metadata = load_metadata()
        last_incremental = metadata.get("last_incremental")
        needs_incremental = False

        if last_incremental:
            backup_folder = BACKUP_DIR / last_incremental / "backup_info.json"
            if backup_folder.exists():
                with open(backup_folder, "r") as f:
                    info = json.load(f)
                ts = datetime.datetime.fromisoformat(info["timestamp"])
                hours_since = (datetime.datetime.now() - ts).total_seconds() / 3600
                needs_incremental = hours_since >= INCREMENTAL_THRESHOLD_HOURS

        # 执行备份
        if needs_incremental:
            create_backup(incremental=True)
            cleanup_old_backups()
        else:
            print(f"[BackupDaemon] Next incremental backup in {INCREMENTAL_THRESHOLD_HOURS - hours_since:.1f} hours")

        time.sleep(interval_hours * 3600)

# ============================================
# CLI 入口
# ============================================

def main():
    parser = argparse.ArgumentParser(description="OpenClaw Backup & Restore Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # backup 命令
    backup_parser = subparsers.add_parser("backup", help="Create a backup")
    backup_parser.add_argument("--incremental", action="store_true", help="Create incremental backup")

    # restore 命令
    restore_parser = subparsers.add_parser("restore", help="Restore a backup")
    restore_parser.add_argument("backup_id", help="Backup ID to restore")

    # list 命令
    subparsers.add_parser("list", help="List all backups")

    # schedule 命令
    schedule_parser = subparsers.add_parser("schedule", help="Run backup daemon")
    schedule_parser.add_argument("--interval", type=int, default=6, help="Backup interval in hours")

    # cleanup 命令
    cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup old backups")
    cleanup_parser.add_argument("--days", type=int, default=RETENTION_DAYS, help="Retention days")

    args = parser.parse_args()

    if args.command == "backup":
        create_backup(incremental=args.incremental)
    elif args.command == "restore":
        restore_backup(args.backup_id)
    elif args.command == "list":
        list_backups()
    elif args.command == "schedule":
        run_backup_daemon(interval_hours=args.interval)
    elif args.command == "cleanup":
        cleanup_old_backups(retention_days=args.days)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
