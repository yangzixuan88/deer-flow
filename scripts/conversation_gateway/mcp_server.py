"""
Conversation Gateway MCP Server

将 ConversationGateway 封装为 MCP Server，
让大模型可以通过 MCP 协议直接查询超大对话文件。

用法:
    # 启动 MCP Server
    python -m conversation_gateway.mcp_server --json_file /path/to/conversations.json

    # 或在 Python 中直接使用
    from conversation_gateway import ConversationGateway
    gw = ConversationGateway("/path/to/conversations.json")
"""

import json
import sys
from pathlib import Path
from typing import Optional, Any
from conversation_gateway.gateway import ConversationGateway


# MCP Server 实现
class MCPServer:
    """
    简化版 MCP Server

    接收 JSON-RPC 格式请求，返回 JSON-RPC 格式响应
    """

    def __init__(self, gateway: ConversationGateway):
        self.gateway = gateway
        self.tools = {
            'list_conversations': self.list_conversations,
            'search_conversation': self.search_conversation,
            'get_message': self.get_message,
            'get_context': self.get_context,
            'get_ancestry': self.get_ancestry,
            'get_linear_messages': self.get_linear_messages,
            'export_context': self.export_context,
        }

    def handle_request(self, request: dict) -> dict:
        """
        处理 MCP 请求

        MCP 请求格式:
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "tool_name",
                "arguments": {...}
            }
        }
        """
        try:
            method = request.get('method', '')
            req_id = request.get('id')

            if method == 'initialize':
                return {
                    'jsonrpc': '2.0',
                    'id': req_id,
                    'result': {
                        'protocolVersion': '2024-11-05',
                        'capabilities': {
                            'tools': {
                                'listChanged': True
                            }
                        },
                        'serverInfo': {
                            'name': 'conversation-gateway',
                            'version': '1.0.0'
                        }
                    }
                }

            elif method == 'tools/list':
                return {
                    'jsonrpc': '2.0',
                    'id': req_id,
                    'result': {
                        'tools': [
                            {
                                'name': 'list_conversations',
                                'description': '列出所有对话的摘要信息',
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {}
                                }
                            },
                            {
                                'name': 'search_conversation',
                                'description': '在对话中搜索关键词',
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {
                                        'query': {'type': 'string', 'description': '搜索关键词'},
                                        'max_results': {'type': 'integer', 'default': 10},
                                        'conversation_id': {'type': 'string'}
                                    },
                                    'required': ['query']
                                }
                            },
                            {
                                'name': 'get_message',
                                'description': '获取指定节点的消息详情',
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {
                                        'node_id': {'type': 'string'},
                                        'conversation_id': {'type': 'string'}
                                    },
                                    'required': ['node_id']
                                }
                            },
                            {
                                'name': 'get_context',
                                'description': '获取节点前后的对话上下文',
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {
                                        'node_id': {'type': 'string'},
                                        'before': {'type': 'integer', 'default': 3},
                                        'after': {'type': 'integer', 'default': 3},
                                        'conversation_id': {'type': 'string'}
                                    },
                                    'required': ['node_id']
                                }
                            },
                            {
                                'name': 'get_ancestry',
                                'description': '获取从根到当前节点的完整路径',
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {
                                        'node_id': {'type': 'string'},
                                        'conversation_id': {'type': 'string'}
                                    },
                                    'required': ['node_id']
                                }
                            },
                            {
                                'name': 'get_linear_messages',
                                'description': '获取对话的线性消息序列（用于构建上下文）',
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {
                                        'conversation_id': {'type': 'string'},
                                        'max_messages': {'type': 'integer', 'default': 50},
                                        'start_from_node': {'type': 'string'}
                                    }
                                }
                            },
                            {
                                'name': 'export_context',
                                'description': '导出为可放入 context window 的格式',
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {
                                        'conversation_id': {'type': 'string'},
                                        'max_tokens': {'type': 'integer', 'default': 4000}
                                    }
                                }
                            }
                        ]
                    }
                }

            elif method == 'tools/call':
                params = request.get('params', {})
                tool_name = params.get('name')
                arguments = params.get('arguments', {})

                if tool_name in self.tools:
                    result = self.tools[tool_name](**arguments)
                    return {
                        'jsonrpc': '2.0',
                        'id': req_id,
                        'result': {
                            'content': [
                                {
                                    'type': 'text',
                                    'text': json.dumps(result, ensure_ascii=False, indent=2)
                                }
                            ]
                        }
                    }
                else:
                    return {
                        'jsonrpc': '2.0',
                        'id': req_id,
                        'error': {
                            'code': -32601,
                            'message': f'Unknown tool: {tool_name}'
                        }
                    }

            else:
                return {
                    'jsonrpc': '2.0',
                    'id': req_id,
                    'error': {
                        'code': -32601,
                        'message': f'Unknown method: {method}'
                    }
                }

        except Exception as e:
            return {
                'jsonrpc': '2.0',
                'id': request.get('id'),
                'error': {
                    'code': -32603,
                    'message': str(e)
                }
            }

    def list_conversations(self) -> dict:
        """列出所有对话"""
        convs = self.gateway.get_conversations()
        return {
            'count': len(convs),
            'conversations': [
                {
                    'id': c.id,
                    'title': c.title,
                    'node_count': c.node_count,
                    'user_messages': c.user_message_count,
                    'assistant_messages': c.assistant_message_count,
                    'create_time': c.create_time,
                    'first_message': c.first_user_message
                }
                for c in convs
            ]
        }

    def search_conversation(
        self,
        query: str,
        max_results: int = 10,
        conversation_id: Optional[str] = None
    ) -> dict:
        """搜索对话"""
        results = self.gateway.search(query, max_results=max_results, conversation_id=conversation_id)
        return {
            'query': query,
            'count': len(results),
            'results': results
        }

    def get_message(
        self,
        node_id: str,
        conversation_id: Optional[str] = None
    ) -> dict:
        """获取单条消息"""
        return self.gateway.get_message(node_id, conversation_id) or {}

    def get_context(
        self,
        node_id: str,
        before: int = 3,
        after: int = 3,
        conversation_id: Optional[str] = None
    ) -> dict:
        """获取上下文"""
        return self.gateway.get_context(node_id, before=before, after=after, conversation_id=conversation_id)

    def get_ancestry(
        self,
        node_id: str,
        conversation_id: Optional[str] = None
    ) -> dict:
        """获取祖先路径"""
        return {
            'path': self.gateway.get_ancestry(node_id, conversation_id)
        }

    def get_linear_messages(
        self,
        conversation_id: Optional[str] = None,
        max_messages: int = 50,
        start_from_node: Optional[str] = None
    ) -> dict:
        """获取线性消息序列"""
        messages = self.gateway.get_all_messages(conversation_id, max_messages=max_messages)
        return {
            'count': len(messages),
            'messages': messages
        }

    def export_context(
        self,
        conversation_id: Optional[str] = None,
        max_tokens: int = 4000
    ) -> dict:
        """导出为 context 格式"""
        output = self.gateway.export_for_context_window(
            conversation_id=conversation_id,
            max_tokens=max_tokens
        )
        return {
            'context': output,
            'length': len(output)
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Conversation Gateway MCP Server")
    parser.add_argument('--json_file', '-f', required=True, help='conversations.json 文件路径')
    parser.add_argument('--port', '-p', type=int, default=8080, help='HTTP 端口')
    parser.add_argument('--stdio', action='store_true', help='使用 stdio 模式（默认）')

    args = parser.parse_args()

    print(f"[MCP Server] 初始化 Conversation Gateway...", file=sys.stderr)
    gateway = ConversationGateway(args.json_file)

    # 找到最大的对话
    largest = gateway.find_largest_conversation()
    print(f"[MCP Server] 已加载最大对话: {largest.title}", file=sys.stderr)

    server = MCPServer(gateway)

    # STDIO 模式：读取 stdin，输出到 stdout
    if args.stdio or True:
        print("[MCP Server] 运行于 STDIO 模式", file=sys.stderr)

        import sys
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = server.handle_request(request)
                print(json.dumps(response), flush=True)
            except json.JSONDecodeError as e:
                error_response = {
                    'jsonrpc': '2.0',
                    'id': None,
                    'error': {'code': -32700, 'message': f'Parse error: {e}'}
                }
                print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
