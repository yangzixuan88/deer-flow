#!/usr/bin/env python3
"""
Conversation Gateway CLI

命令行接口，快速查询超大对话文件

用法:
    # 列出所有对话
    python cli.py --json /path/to/conversations.json --list

    # 搜索关键词
    python cli.py --json /path/to/conversations.json --search "OpenClaw"

    # 获取节点上下文
    python cli.py --json /path/to/conversations.json --node <node_id>

    # 导出为可用的 context 格式
    python cli.py --json /path/to/conversations.json --export
"""

import argparse
import json
import sys
from pathlib import Path

# 添加父目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from gateway import ConversationGateway


def main():
    parser = argparse.ArgumentParser(
        description='Conversation Gateway - 超大对话文件查询工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --json conversations.json --list
  %(prog)s --json conversations.json --search "OpenClaw 架构"
  %(prog)s --json conversations.json --node abc123
  %(prog)s --json conversations.json --export
        """
    )

    parser.add_argument(
        '--json', '-f',
        required=True,
        help='conversations.json 文件路径'
    )

    # 操作模式
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--list', '-l',
        action='store_true',
        help='列出所有对话'
    )
    group.add_argument(
        '--search', '-s',
        metavar='QUERY',
        help='搜索关键词'
    )
    group.add_argument(
        '--node', '-n',
        metavar='NODE_ID',
        help='查询指定节点'
    )
    group.add_argument(
        '--context', '-c',
        metavar='NODE_ID',
        help='获取节点上下文'
    )
    group.add_argument(
        '--export', '-e',
        action='store_true',
        help='导出为 context 格式'
    )
    group.add_argument(
        '--mcp',
        action='store_true',
        help='启动 MCP Server 模式'
    )

    # 选项
    parser.add_argument(
        '--conv-id',
        help='指定对话 ID（不指定则使用最大的）'
    )
    parser.add_argument(
        '--max-results',
        type=int,
        default=10,
        help='最大搜索结果数（默认 10）'
    )
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=4000,
        help='导出时最大 token 数（默认 4000）'
    )

    args = parser.parse_args()

    # 初始化网关
    print(f"加载文件: {args.json}", file=sys.stderr)
    gw = ConversationGateway(args.json)

    # 执行操作
    if args.list:
        _cmd_list(gw)

    elif args.search:
        _cmd_search(gw, args.search, args.max_results, args.conv_id)

    elif args.node:
        _cmd_node(gw, args.node, args.conv_id)

    elif args.context:
        _cmd_context(gw, args.context, args.conv_id)

    elif args.export:
        _cmd_export(gw, args.conv_id, args.max_tokens)

    elif args.mcp:
        _cmd_mcp(args.json)

    else:
        parser.print_help()


def _cmd_list(gw: ConversationGateway):
    """列出所有对话"""
    convs = gw.get_conversations()

    print(f"\n{'='*60}")
    print(f"  发现 {len(convs)} 个对话")
    print(f"{'='*60}\n")

    for i, conv in enumerate(convs):
        largest_marker = " [最大]" if conv.node_count == max(c.node_count for c in convs) else ""
        print(f"  {i+1}. {conv.title}{largest_marker}")
        print(f"     ID: {conv.id}")
        print(f"     节点: {conv.node_count}, 用户消息: {conv.user_message_count}, AI回复: {conv.assistant_message_count}")
        print(f"     创建: {conv.create_time}")
        if conv.first_user_message:
            preview = conv.first_user_message[:60].replace('\n', ' ')
            print(f"     首条: {preview}...")
        print()


def _cmd_search(gw: ConversationGateway, query: str, max_results: int, conv_id: str):
    """搜索关键词"""
    results = gw.search(query, max_results=max_results, conversation_id=conv_id)

    print(f"\n{'='*60}")
    print(f"  搜索: {query}")
    print(f"  找到 {len(results)} 条结果")
    print(f"{'='*60}\n")

    for r in results:
        role_icon = "👤" if r['role'] == 'user' else "🤖"
        print(f"  {role_icon} [{r['role']}] {r['node_id'][:16]}...")
        print(f"     评分: {r['score']}")
        content = r['content'][:200].replace('\n', ' ')
        print(f"     {content}...")
        print()


def _cmd_node(gw: ConversationGateway, node_id: str, conv_id: str):
    """查询节点"""
    msg = gw.get_message(node_id, conversation_id=conv_id)

    if not msg:
        print(f"未找到节点: {node_id}")
        return

    print(f"\n{'='*60}")
    print(f"  节点: {node_id}")
    print(f"{'='*60}\n")

    print(f"  Role: {msg['author'].get('role')}")
    print(f"  Parent: {msg.get('parent', 'N/A')}")
    print(f"  Children: {msg.get('children', [])}")
    print()

    content = msg.get('content', {})
    parts = content.get('parts', [])
    if parts:
        print("  内容:")
        print("  " + "-"*50)
        for part in parts:
            text = str(part)[:1000]
            print(text)
        print("  " + "-"*50)


def _cmd_context(gw: ConversationGateway, node_id: str, conv_id: str):
    """获取上下文"""
    ctx = gw.get_context(node_id, conversation_id=conv_id)

    print(f"\n{'='*60}")
    print(f"  上下文: {node_id}")
    print(f"{'='*60}\n")

    print("  [前] " + "-"*50)
    for m in ctx['before']:
        icon = "👤" if m['role'] == 'user' else "🤖"
        print(f"  {icon} {m['content'][:100]}...")

    print()
    print("  [中心] " + "-"*50)
    if ctx['center']:
        content = ctx['center'].get('content', {})
        parts = content.get('parts', [])
        if parts:
            print(f"  👤 {parts[0][:200]}...")

    print()
    print("  [后] " + "-"*50)
    for m in ctx['after']:
        icon = "👤" if m['role'] == 'user' else "🤖"
        print(f"  {icon} {m['content'][:100]}...")


def _cmd_export(gw: ConversationGateway, conv_id: str, max_tokens: int):
    """导出为 context 格式"""
    output = gw.export_for_context_window(
        conversation_id=conv_id,
        max_tokens=max_tokens
    )

    print(f"\n{'='*60}")
    print(f"  Context 导出 (约 {len(output)} 字符)")
    print(f"{'='*60}\n")
    print(output)


def _cmd_mcp(json_path: str):
    """启动 MCP Server"""
    from mcp_server import MCPServer

    print("启动 MCP Server...", file=sys.stderr)
    gateway = ConversationGateway(json_path)
    largest = gateway.find_largest_conversation()
    print(f"已加载对话: {largest.title}", file=sys.stderr)

    server = MCPServer(gateway)

    print("MCP Server 运行中 (STDIO)...", file=sys.stderr)

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


if __name__ == '__main__':
    main()
