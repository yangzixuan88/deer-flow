"""
Conversation Gateway - ChatGPT 超大对话文件的按需查询接口

用法:
    from gateway import ConversationGateway

    gw = ConversationGateway("path/to/conversations.json")

    # 搜索关键词
    results = gw.search("OpenClaw 架构")

    # 获取某个节点的消息
    msg = gw.get_message(node_id)

    # 获取从当前节点到根的路径
    path = gw.get_ancestry(node_id)

    # 获取前后上下文
    context = gw.get_context(node_id, before=5, after=5)
"""

import json
import os
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """单条消息"""
    node_id: str
    role: Role
    content: str
    timestamp: Optional[float] = None
    parent_id: Optional[str] = None
    children_ids: list = None

    def __post_init__(self):
        if self.children_ids is None:
            self.children_ids = []


@dataclass
class ConversationSummary:
    """对话摘要"""
    id: str
    title: str
    node_count: int
    user_message_count: int
    assistant_message_count: int
    create_time: Optional[str] = None
    first_user_message: Optional[str] = None


class ConversationGateway:
    """
    对话语境查询网关

    核心价值：超大 JSON 文件（50MB+）无需全部加载给大模型，
    而是通过这个网关按需查询相关上下文。
    """

    def __init__(self, json_path: str, lazy_load: bool = True):
        """
        初始化网关

        Args:
            json_path: conversations.json 文件路径
            lazy_load: True=只解析元数据，False=预加载全部（内存占用大）
        """
        self.json_path = Path(json_path)
        self.lazy_load = lazy_load

        # 元数据缓存
        self.conversations_meta: list[ConversationSummary] = []
        self.conversation_index: dict[str, int] = {}  # id -> index

        # 当前加载的对话详情（按需加载）
        self.current_conversation: Optional[dict] = None
        self.current_mapping: Optional[dict] = None
        self.current_conv_id: Optional[str] = None

        # 消息缓存（用于 search）
        self._message_cache: list[Message] = []
        self._cache_built = False

        self._load_metadata()

    def _load_metadata(self):
        """加载元数据（快速，不加载完整 mapping）"""
        print(f"[Gateway] 加载元数据: {self.json_path}")

        with open(self.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for i, conv in enumerate(data):
            mapping = conv.get('mapping', {})

            # 统计消息数
            user_count = 0
            assistant_count = 0
            first_user = None

            for node_id, node in mapping.items():
                msg = node.get('message')
                if msg:
                    role = msg.get('author', {}).get('role')
                    if role == 'user':
                        user_count += 1
                        if first_user is None:
                            parts = msg.get('content', {}).get('parts', [])
                            if parts:
                                first_user = parts[0][:100] if parts[0] else None
                    elif role == 'assistant':
                        assistant_count += 1

            create_time = conv.get('create_time')
            if create_time:
                create_time = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M')

            summary = ConversationSummary(
                id=conv.get('id', ''),
                title=conv.get('title', '无标题'),
                node_count=len(mapping),
                user_message_count=user_count,
                assistant_message_count=assistant_count,
                create_time=create_time,
                first_user_message=first_user
            )

            self.conversations_meta.append(summary)
            self.conversation_index[summary.id] = i

        print(f"[Gateway] 发现 {len(self.conversations_meta)} 个对话")

        # 找到最大的那个对话
        largest = max(self.conversations_meta, key=lambda x: x.node_count)
        print(f"[Gateway] 最大对话: {largest.title} ({largest.node_count} 节点)")

    def load_conversation(self, conv_id: str):
        """
        加载指定对话到内存

        Args:
            conv_id: 对话 ID
        """
        if conv_id == self.current_conv_id and self.current_mapping:
            return  # 已经加载

        print(f"[Gateway] 加载对话: {conv_id}")

        with open(self.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        idx = self.conversation_index.get(conv_id)
        if idx is None:
            raise ValueError(f"未找到对话: {conv_id}")

        conv = data[idx]
        self.current_conversation = conv
        self.current_mapping = conv.get('mapping', {})
        self.current_conv_id = conv_id
        self._cache_built = False
        self._message_cache = []

        print(f"[Gateway] 对话已加载: {len(self.current_mapping)} 节点")

    def get_conversations(self) -> list[ConversationSummary]:
        """获取所有对话的摘要列表"""
        return self.conversations_meta

    def find_largest_conversation(self) -> ConversationSummary:
        """获取节点最多的对话"""
        return max(self.conversations_meta, key=lambda x: x.node_count)

    def get_conversation(self, conv_id: str) -> dict:
        """获取对话完整数据（需先 load）"""
        if self.current_conv_id != conv_id:
            self.load_conversation(conv_id)
        return self.current_conversation

    def _ensure_loaded(self):
        """确保有对话已加载"""
        if self.current_mapping is None:
            largest = self.find_largest_conversation()
            self.load_conversation(largest.id)

    def _build_message_cache(self):
        """构建消息缓存（用于搜索）"""
        if self._cache_built:
            return

        self._ensure_loaded()

        for node_id, node in self.current_mapping.items():
            msg = node.get('message')
            if msg is None:
                continue

            role_str = msg.get('author', {}).get('role', '')
            try:
                role = Role(role_str)
            except ValueError:
                role = Role.SYSTEM

            parts = msg.get('content', {}).get('parts', [])
            content = parts[0] if parts else ''

            if not content:
                continue

            self._message_cache.append(Message(
                node_id=node_id,
                role=role,
                content=str(content),
                timestamp=msg.get('create_time'),
                parent_id=node.get('parent'),
                children_ids=node.get('children', [])
            ))

        self._cache_built = True

    def search(
        self,
        query: str,
        max_results: int = 10,
        conversation_id: Optional[str] = None
    ) -> list[dict]:
        """
        搜索包含关键词的消息

        Args:
            query: 搜索关键词
            max_results: 最大返回数
            conversation_id: 指定对话，不指定则搜索最大对话

        Returns:
            [{node_id, role, content, score}, ...]
        """
        if conversation_id and conversation_id != self.current_conv_id:
            self.load_conversation(conversation_id)

        self._build_message_cache()

        query_lower = query.lower()
        results = []

        for msg in self._message_cache:
            if query_lower in msg.content.lower():
                # 简单评分：计算出现次数
                score = msg.content.lower().count(query_lower)
                results.append({
                    'node_id': msg.node_id,
                    'role': msg.role.value,
                    'content': msg.content[:500] + '...' if len(msg.content) > 500 else msg.content,
                    'score': score,
                    'timestamp': msg.timestamp
                })

        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:max_results]

    def get_message(self, node_id: str, conversation_id: Optional[str] = None) -> Optional[dict]:
        """
        获取指定节点的消息

        Args:
            node_id: 节点 ID
            conversation_id: 对话 ID

        Returns:
            {id, parent, children, author, content, metadata}
        """
        if conversation_id and conversation_id != self.current_conv_id:
            self.load_conversation(conversation_id)

        self._ensure_loaded()

        node = self.current_mapping.get(node_id)
        if node is None:
            return None

        msg = node.get('message')
        if msg is None:
            return None

        return {
            'id': node_id,
            'parent': node.get('parent'),
            'children': node.get('children', []),
            'author': msg.get('author', {}),
            'content': msg.get('content', {}),
            'metadata': msg.get('metadata', {})
        }

    def get_ancestry(self, node_id: str, conversation_id: Optional[str] = None) -> list[dict]:
        """
        获取从根到当前节点的路径

        Args:
            node_id: 起始节点 ID
            conversation_id: 对话 ID

        Returns:
            [{node_id, role, content}, ...] 从根到当前节点
        """
        if conversation_id and conversation_id != self.current_conv_id:
            self.load_conversation(conversation_id)

        self._ensure_loaded()

        path = []
        current_id = node_id

        while current_id:
            node = self.current_mapping.get(current_id)
            if node is None:
                break

            msg = node.get('message')
            if msg:
                parts = msg.get('content', {}).get('parts', [])
                content = parts[0] if parts else ''
                role = msg.get('author', {}).get('role', 'unknown')
            else:
                content = '[无消息]'
                role = 'unknown'

            path.append({
                'node_id': current_id,
                'role': role,
                'content': str(content)[:200] if content else ''
            })

            current_id = node.get('parent')

        path.reverse()
        return path

    def get_context(
        self,
        node_id: str,
        before: int = 3,
        after: int = 3,
        conversation_id: Optional[str] = None
    ) -> dict:
        """
        获取节点前后的对话上下文

        Args:
            node_id: 中心节点 ID
            before: 前几条消息
            after: 后几条消息
            conversation_id: 对话 ID

        Returns:
            {before: [], center: {}, after: []}
        """
        if conversation_id and conversation_id != self.current_conv_id:
            self.load_conversation(conversation_id)

        self._ensure_loaded()

        # 先获取线性顺序
        linear = self._get_linear_order()

        try:
            center_idx = next(i for i, n in enumerate(linear) if n['node_id'] == node_id)
        except StopIteration:
            return {'before': [], 'center': None, 'after': []}

        before_msgs = []
        for i in range(max(0, center_idx - before), center_idx):
            n = linear[i]
            msg = self.current_mapping.get(n['node_id'], {}).get('message')
            if msg:
                parts = msg.get('content', {}).get('parts', [])
                content = parts[0] if parts else ''
                before_msgs.append({
                    'node_id': n['node_id'],
                    'role': msg.get('author', {}).get('role', 'unknown'),
                    'content': str(content)[:300]
                })

        center_msg = self.get_message(node_id)

        after_msgs = []
        for i in range(center_idx + 1, min(len(linear), center_idx + after + 1)):
            n = linear[i]
            msg = self.current_mapping.get(n['node_id'], {}).get('message')
            if msg:
                parts = msg.get('content', {}).get('parts', [])
                content = parts[0] if parts else ''
                after_msgs.append({
                    'node_id': n['node_id'],
                    'role': msg.get('author', {}).get('role', 'unknown'),
                    'content': str(content)[:300]
                })

        return {
            'before': before_msgs,
            'center': center_msg,
            'after': after_msgs
        }

    def _get_linear_order(self) -> list[dict]:
        """获取线性化的消息顺序"""
        self._ensure_loaded()

        # BFS 从根节点遍历
        root_id = None
        for node_id, node in self.current_mapping.items():
            if node.get('parent') is None:
                root_id = node_id
                break

        if root_id is None:
            return []

        ordered = []
        queue = [root_id]
        visited = set()

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)

            node = self.current_mapping.get(node_id, {})
            ordered.append({'node_id': node_id, 'parent': node.get('parent')})

            for child_id in node.get('children', []):
                if child_id not in visited:
                    queue.append(child_id)

        return ordered

    def get_all_messages(
        self,
        conversation_id: Optional[str] = None,
        max_messages: Optional[int] = None
    ) -> list[dict]:
        """
        获取所有消息（用于外部处理）

        Args:
            conversation_id: 对话 ID
            max_messages: 最大消息数

        Returns:
            [{node_id, role, content, parent, children}, ...]
        """
        if conversation_id and conversation_id != self.current_conv_id:
            self.load_conversation(conversation_id)

        self._ensure_loaded()

        messages = []
        for node_id, node in self.current_mapping.items():
            msg = node.get('message')
            if msg is None:
                continue

            parts = msg.get('content', {}).get('parts', [])
            content = parts[0] if parts else ''

            messages.append({
                'node_id': node_id,
                'role': msg.get('author', {}).get('role', 'unknown'),
                'content': str(content),
                'parent': node.get('parent'),
                'children': node.get('children', [])
            })

            if max_messages and len(messages) >= max_messages:
                break

        return messages

    def export_for_context_window(
        self,
        conversation_id: Optional[str] = None,
        system_prompt: str = "你是OpenClaw项目的智能助手，正在继续之前的工作。",
        max_tokens: int = 4000
    ) -> str:
        """
        导出为可直接放入 context window 的格式

        用于将对话内容格式化后直接发送给大模型

        Args:
            conversation_id: 对话 ID
            system_prompt: 系统提示
            max_tokens: 最大 token 数（粗略估算）

        Returns:
            格式化后的对话字符串
        """
        messages = self.get_all_messages(conversation_id)

        # 转换为 OpenAI 格式
        formatted = []
        for msg in messages:
            if msg['role'] == 'system':
                continue  # 系统消息单独处理

            formatted.append(f"### {msg['role'].upper()}\n\n{msg['content'][:1000]}")

        # 组装
        output = f"{system_prompt}\n\n"
        output += "=" * 50 + "\n\n"

        char_limit = max_tokens * 4  # 粗略估算 1 token ≈ 4 字符

        for msg in formatted:
            if len(output) + len(msg) > char_limit:
                break
            output += msg + "\n\n"

        return output


# CLI 接口
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Conversation Gateway - 超大对话文件查询工具")
    parser.add_argument("json_file", help="conversations.json 文件路径")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有对话")
    parser.add_argument("--search", "-s", help="搜索关键词")
    parser.add_argument("--node", "-n", help="查询指定节点")
    parser.add_argument("--context", "-c", help="获取节点上下文")
    parser.add_argument("--export", "-e", action="store_true", help="导出为 context 格式")
    parser.add_argument("--conv-id", help="指定对话 ID")

    args = parser.parse_args()

    gw = ConversationGateway(args.json_file)

    if args.list:
        print("\n=== 对话列表 ===")
        for i, conv in enumerate(gw.get_conversations()):
            print(f"{i+1}. {conv.title}")
            print(f"   ID: {conv.id}")
            print(f"   节点: {conv.node_count}, 用户: {conv.user_message_count}, AI: {conv.assistant_message_count}")
            print(f"   时间: {conv.create_time}")
            print()

    elif args.search:
        print(f"\n=== 搜索: {args.search} ===")
        results = gw.search(args.search, conversation_id=args.conv_id)
        for r in results:
            print(f"[{r['role']}] {r['node_id'][:20]}... (score: {r['score']})")
            print(f"   {r['content'][:150]}...")
            print()

    elif args.node:
        msg = gw.get_message(args.node, conversation_id=args.conv_id)
        if msg:
            print(f"\n=== 节点: {args.node} ===")
            print(f"Role: {msg['author'].get('role')}")
            print(f"Content: {msg['content']}")
        else:
            print(f"未找到节点: {args.node}")

    elif args.context:
        ctx = gw.get_context(args.context, conversation_id=args.conv_id)
        print(f"\n=== 上下文: {args.context} ===")
        print("\n--- 前 ---")
        for m in ctx['before']:
            print(f"[{m['role']}] {m['content'][:100]}...")
        print("\n--- 中心 ---")
        if ctx['center']:
            print(f"[{ctx['center']['author'].get('role')}] {ctx['center']['content']}")
        print("\n--- 后 ---")
        for m in ctx['after']:
            print(f"[{m['role']}] {m['content'][:100]}...")

    elif args.export:
        output = gw.export_for_context_window(conversation_id=args.conv_id)
        print(output)

    else:
        parser.print_help()
