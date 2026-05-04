import sys
import os
import json
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path

# OpenClaw Architecture 2.0 Omni-Empowerment MCP Server
# Purpose: Expose "Nine-Dimensional Assets" as MCP Tools for Cursor/Claude.
# Aligns with "Full-Domain Empowerment" and "Lego-Style Mobility" rules.

# Path Resolution - Support pipe mode with environment variable fallback
try:
    # Normal execution: derive path from script location
    # mcp_server.py is at: PROJECT_ROOT/src/infrastructure/server/mcp_server.py
    # So we need to go up 4 levels: server -> infrastructure -> src -> PROJECT_ROOT
    INFRA_DIR = Path(__file__).parent.parent  # = src/infrastructure
    PROJECT_ROOT = INFRA_DIR.parent.parent     # = PROJECT_ROOT (up 2 more levels from INFRA_DIR)
except Exception:
    # Pipe mode: use environment variable or current directory
    _env_root = os.environ.get("OPENCLAW_ROOT")
    PROJECT_ROOT = Path(_env_root) if _env_root else Path.cwd()
    INFRA_DIR = PROJECT_ROOT / "src" / "infrastructure"

ASSETS_DIR = PROJECT_ROOT / "assets"
DB_PATH = ASSETS_DIR / "Asset_Manifest.sqlite"

# Debug: uncomment to see path resolution
# print(f"DEBUG: PROJECT_ROOT={PROJECT_ROOT}, DB_PATH={DB_PATH}", file=sys.stderr)

def get_db_path():
    """Get database path as string, handling Unicode on Windows."""
    db_path = DB_PATH
    # Always use absolute() + string conversion to avoid resolve() issues
    # resolve() can behave unexpectedly with relative path components
    abs_path = db_path.absolute()
    return str(abs_path)

# MCP API Server URL (Node.js)
MCP_API_BASE = os.environ.get("MCP_API_BASE", "http://localhost:8082")

# SECURITY: API key must be set via environment variable - no default
_MCP_API_KEY_ENV = os.environ.get("MCP_API_KEY")
if not _MCP_API_KEY_ENV:
    print("FATAL: MCP_API_KEY environment variable is not set. Production deployments must use a secure API key.", file=sys.stderr)
    sys.exit(1)
MCP_API_KEY = _MCP_API_KEY_ENV

def get_asset_content(name, asset_type):
    """Read asset content from filesystem."""
    # SECURITY: 防止路径遍历攻击 - 禁止 name 包含路径分隔符
    if name and any(sep in name for sep in ('/', '\\', '..', ':')):
        return f"[Error] Invalid asset name: path separators not allowed."

    type_map = {
        "DomainKnowledge": "domain_knowledge",
        "Skill": "cold_skills",
        "Task": "trace_logs",
        "Cognitive": "warm_memories"
    }

    subfolder = type_map.get(asset_type, "")
    target_path = ASSETS_DIR / subfolder / name if subfolder else None

    if target_path and target_path.exists():
        # SECURITY: 验证解析后的路径仍在 ASSETS_DIR 内
        resolved = target_path.resolve()
        assets_resolved = ASSETS_DIR.resolve()
        if not str(resolved).startswith(str(assets_resolved) + os.sep):
            return "[Error] Access denied: path outside assets directory."
        with open(target_path, "r", encoding="utf-8") as f:
            return f.read()

    # Fallback: Recursive search in assets/ (仅返回匹配的第一个文件)
    for p in ASSETS_DIR.rglob(name):
        # SECURITY: 验证每个匹配项都在 ASSETS_DIR 内
        resolved = p.resolve()
        assets_resolved = ASSETS_DIR.resolve()
        if not str(resolved).startswith(str(assets_resolved) + os.sep):
            continue  # 跳过目录外的匹配项
        with open(p, "r", encoding="utf-8") as f:
            return f.read()

    return f"[Error] Content for {name} ({asset_type}) not found."

def call_mcp_api(endpoint, params):
    """Call Node.js MCP API server via HTTP with authentication."""
    url = f"{MCP_API_BASE}{endpoint}"
    data = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "params": params
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MCP_API_KEY}"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("result", {})
    except urllib.error.URLError as e:
        return {"error": str(e), "fallback": True}
    except Exception as e:
        return {"error": str(e), "fallback": True}

def handle_request(request):
    try:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            return {
                "id": request_id,
                "result": {
                    "capabilities": {
                        "tools": {
                            "listChanged": True
                        }
                    },
                    "serverInfo": {
                        "name": "OpenClaw-Omni-Empowerment-Server",
                        "version": "1.1.0"
                    }
                }
            }

        elif method == "tools/list":
            # 返回所有可用工具
            return {
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "get_optimized_prompt",
                            "description": "Retrieve an optimized prompt/skill from the OpenClaw Asset Library.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "asset_name": {"type": "string", "description": "The specific name of the skill or knowledge asset."}
                                },
                                "required": ["asset_name"]
                            }
                        },
                        {
                            "name": "list_available_assets",
                            "description": "List all gold-level assets (Quality > 0.7) in the current environment.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "asset_type": {"type": "string", "description": "Filter by type (DomainKnowledge, Skill, etc.)"}
                                }
                            }
                        },
                        {
                            "name": "route_prompt",
                            "description": "Route user input through M09 Prompt Engine and get assembled prompt.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "user_input": {"type": "string", "description": "User input to route"},
                                    "task_type": {"type": "string", "description": "Optional task type override"},
                                    "safety_rules": {"type": "array", "items": {"type": "string"}, "description": "Safety rules to apply"},
                                    "available_tools": {"type": "array", "items": {"type": "string"}, "description": "Available tools context"}
                                },
                                "required": ["user_input"]
                            }
                        },
                        {
                            "name": "recognize_task_type",
                            "description": "Recognize task type from user input using M09 TaskTypeRecognizer.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "user_input": {"type": "string", "description": "User input to analyze"}
                                },
                                "required": ["user_input"]
                            }
                        },
                        {
                            "name": "search_memory",
                            "description": "Search memories from M06 Memory system.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Search query"},
                                    "layer": {"type": "string", "enum": ["working", "session", "persistent", "knowledge"], "description": "Memory layer"},
                                    "limit": {"type": "integer", "description": "Max results"},
                                    "filter": {"type": "object", "description": "MongoDB-like filter criteria, e.g. {\"quality_score\": {\"$gte\": 0.8}}"}
                                },
                                "required": ["query"]
                            }
                        }
                    ]
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            # M09: 提示词路由
            if tool_name == "route_prompt":
                api_result = call_mcp_api("/api/v1/prompt/route", {
                    "userInput": tool_args.get("user_input", ""),
                    "taskType": tool_args.get("task_type"),
                    "safetyRules": tool_args.get("safety_rules", []),
                    "availableTools": tool_args.get("available_tools", [])
                })

                if api_result.get("fallback"):
                    # API不可用，返回提示
                    return {
                        "id": request_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": f"[MCP-API Fallback] Prompt routing via HTTP API failed: {api_result.get('error')}\n\nPlease ensure Node.js MCP API server is running on port 8082."
                            }]
                        }
                    }

                return {
                    "id": request_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": f"[M09] Routed Prompt:\n\nTask Type: {api_result.get('task_type', 'unknown')}\nFragments Used: {', '.join(api_result.get('fragments_used', []))}\nEstimated Tokens: {api_result.get('estimated_tokens', 0)}\n\n--- Prompt Content ---\n{api_result.get('content', '')}"
                        }]
                    }
                }

            # M09: 任务类型识别
            elif tool_name == "recognize_task_type":
                api_result = call_mcp_api("/api/v1/prompt/recognize", {
                    "userInput": tool_args.get("user_input", "")
                })

                if api_result.get("fallback"):
                    return {
                        "id": request_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": f"[MCP-API Fallback] Task type recognition via HTTP API failed: {api_result.get('error')}"
                            }]
                        }
                    }

                task_types = api_result.get("task_types", [])
                types_text = "\n".join([f"- {t['task_type']} (confidence: {t['confidence']:.2f})" for t in task_types])

                return {
                    "id": request_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": f"[M09] Task Type Recognition:\n\n{types_text or 'No task types recognized'}"
                        }]
                    }
                }

            # M06: 记忆搜索
            elif tool_name == "search_memory":
                api_result = call_mcp_api("/api/v1/memory/search", {
                    "query": tool_args.get("query", ""),
                    "layer": tool_args.get("layer", "session"),
                    "limit": tool_args.get("limit", 10),
                    "filter": tool_args.get("filter", {})
                })

                if api_result.get("fallback"):
                    return {
                        "id": request_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": f"[MCP-API Fallback] Memory search via HTTP API failed: {api_result.get('error')}"
                            }]
                        }
                    }

                results = api_result.get("results", [])
                results_text = "\n".join([f"- [{r.get('layer', 'unknown')}] {r.get('content', '')[:100]}" for r in results[:5]])

                return {
                    "id": request_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": f"[M06] Memory Search Results (Layer: {api_result.get('layer', 'unknown')}):\n\n{results_text or 'No results found'}"
                        }]
                    }
                }

            # 原有的 SQLite 资产查询（保留作为 fallback）
            db_path_str = get_db_path()
            conn = sqlite3.connect(db_path_str)
            cursor = conn.cursor()

            if tool_name == "get_optimized_prompt":
                asset_name = tool_args.get("asset_name")
                cursor.execute("SELECT name, type, quality_score FROM assets WHERE name = ? OR name LIKE ?", (asset_name, f"%{asset_name}%"))
                row = cursor.fetchone()
                if row:
                    content = get_asset_content(row[0], row[1])
                    return {
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Asset: {row[0]}\nType: {row[1]}\nQuality: {row[2]}\n\nContent:\n{content}"
                                }
                            ]
                        }
                    }
                else:
                    return {
                        "id": request_id,
                        "result": {"content": [{"type": "text", "text": f"Asset '{asset_name}' not found in manifest."}], "isError": True}
                    }

            elif tool_name == "list_available_assets":
                asset_type = tool_args.get("asset_type")
                query = "SELECT name, type, quality_score, usage_count FROM assets WHERE quality_score >= 0.7"
                params = []
                # SECURITY FIX: 使用参数化查询防止 SQL 注入
                if asset_type:
                    query += " AND type = ?"
                    params.append(asset_type)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                assets_list = "\n".join([f"- {r[0]} ({r[1]}) | Score: {r[2]} | Used: {r[3]}" for r in rows])
                return {
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Available Assets (Quality > 0.7):\n{assets_list or 'None'}"
                            }
                        ]
                    }
                }

            conn.close()

        return {"id": request_id, "error": {"code": -32601, "message": "Method not found"}}

    except Exception as e:
        return {"id": request.get("id"), "error": {"code": -32603, "message": str(e)}}

def main():
    # MCP Protocol communicates via JSON-RPC over stdio
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            continue

if __name__ == "__main__":
    main()
