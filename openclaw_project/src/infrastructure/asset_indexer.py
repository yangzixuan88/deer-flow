import sqlite3
import hashlib
import json
import os
import datetime
from pathlib import Path

# OpenClaw Architecture 2.0 Asset Indexer (Nine-Dimensional Manifest)
# Purpose: Maintain a global index of all digital assets with millisecond-level deduplication.
# Aligns with "Never step into the same pit twice" rule.

DB_PATH = Path(__file__).parent.parent.parent / "assets" / "Asset_Manifest.sqlite"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Nine-Dimensional Table:
    # 1. id (Primary Key)
    # 2. asset_name (Unique Name)
    # 3. type (Search, Task, Tool, Cognitive, Network, Skill, DomainKnowledge, MetaRule, EnvConfig)
    # 4. fingerprint (Content-based MD5)
    # 5. quality_score (F6.1 Score)
    # 6. success_rate (0.0-1.0)
    # 7. usage_count (Number of times reused)
    # 8. last_used (Timestamp)
    # 9. metadata_json (Additional attributes: size, latency, cost, etc.)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            fingerprint TEXT UNIQUE NOT NULL,
            quality_score REAL DEFAULT 0.0,
            success_rate REAL DEFAULT 0.0,
            usage_count INTEGER DEFAULT 1,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        )
    ''')
    conn.commit()
    conn.close()

def generate_fingerprint(data: str):
    return hashlib.md5(data.encode('utf-8')).hexdigest()

def index_asset(name, asset_type, content, quality_score=0.0, metadata=None):
    fingerprint = generate_fingerprint(content)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if exists
        cursor.execute("SELECT id, usage_count FROM assets WHERE fingerprint = ?", (fingerprint,))
        row = cursor.fetchone()
        
        if row:
            # Increment usage count
            new_count = row[1] + 1
            cursor.execute("UPDATE assets SET usage_count = ?, last_used = ? WHERE id = ?", (new_count, now, row[0]))
            print(f"[AssetIndexer] Duplicate detected: Incremented usage count for '{name}' (ID: {row[0]})")
        else:
            # Insert new
            cursor.execute('''
                INSERT INTO assets (name, type, fingerprint, quality_score, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, asset_type, fingerprint, quality_score, json.dumps(metadata)))
            print(f"[AssetIndexer] Indexed new asset: '{name}' ({asset_type})")
            
        conn.commit()
    except sqlite3.Error as e:
        print(f"[AssetIndexer] DB Error: {e}")
    finally:
        conn.close()

def query_assets(category: str = None, min_quality: float = 0.0, limit: int = 100):
    """Query assets by category with minimum quality score."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        query = "SELECT id, name, type, quality_score, usage_count, last_used FROM assets WHERE quality_score >= ?"
        params = [min_quality]
        if category:
            query += " AND type = ?"
            params.append(category)
        query += " ORDER BY quality_score DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [
            {"id": r[0], "name": r[1], "type": r[2], "quality_score": r[3], "usage_count": r[4], "last_used": r[5]}
            for r in rows
        ]
    except sqlite3.Error as e:
        print(f"[AssetIndexer] Query Error: {e}")
        return []
    finally:
        conn.close()

def get_asset_by_id(asset_id: int):
    """Get asset details by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, type, fingerprint, quality_score, success_rate, usage_count, last_used, metadata FROM assets WHERE id = ?", (asset_id,))
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0], "name": row[1], "type": row[2], "fingerprint": row[3],
                "quality_score": row[4], "success_rate": row[5], "usage_count": row[6],
                "last_used": row[7], "metadata": row[8]
            }
        return None
    except sqlite3.Error as e:
        print(f"[AssetIndexer] Get Error: {e}")
        return None
    finally:
        conn.close()

def create_asset(name: str, asset_type: str, content: str, quality_score: float = 0.0, metadata: dict = None):
    """Create a new asset."""
    fingerprint = generate_fingerprint(content)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO assets (name, type, fingerprint, quality_score, metadata, last_used)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, asset_type, fingerprint, quality_score, json.dumps(metadata), now))
        conn.commit()
        return {"success": True, "id": cursor.lastrowid}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Asset with same fingerprint already exists"}
    except sqlite3.Error as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Asset Indexer CLI')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Query command
    q = subparsers.add_parser('query', help='Query assets')
    q.add_argument('--category', type=str, help='Filter by category')
    q.add_argument('--min-quality', type=float, default=0.0, help='Minimum quality score')
    q.add_argument('--limit', type=int, default=100, help='Result limit')

    # Get command
    g = subparsers.add_parser('get', help='Get asset by ID')
    g.add_argument('--id', type=int, required=True, help='Asset ID')

    # Create command
    c = subparsers.add_parser('create', help='Create new asset')
    c.add_argument('--name', type=str, required=True, help='Asset name')
    c.add_argument('--type', type=str, required=True, help='Asset type')
    c.add_argument('--content', type=str, required=True, help='Asset content')
    c.add_argument('--quality', type=float, default=0.5, help='Quality score')

    args = parser.parse_args()

    if args.command == 'query':
        results = query_assets(args.category, args.min_quality, args.limit)
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif args.command == 'get':
        result = get_asset_by_id(args.id)
        print(json.dumps(result, indent=2, ensure_ascii=False) if result else json.dumps({"error": "Not found"}))
    elif args.command == 'create':
        result = create_asset(args.name, args.type, args.content, args.quality)
        print(json.dumps(result, ensure_ascii=False))
