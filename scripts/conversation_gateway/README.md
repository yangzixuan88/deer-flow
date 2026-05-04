# Conversation Gateway 使用说明

## 功能概述

这是一个**对话文件查询中间件**，让你可以在不加载整个 50MB+ JSON 文件的情况下，按需查询对话内容。

## 目录结构

```
conversation_gateway/
├── __init__.py          # 包初始化
├── gateway.py           # 核心查询引擎
├── mcp_server.py         # MCP Server 封装
├── cli.py                # 命令行接口
└── README.md            # 本文件
```

## 快速开始

### 1. 命令行查询

```bash
cd E:/OpenClaw-Base/deerflow/scripts/conversation_gateway

# 列出所有对话
python cli.py --json /path/to/conversations.json --list

# 搜索关键词
python cli.py --json /path/to/conversations.json --search "OpenClaw 架构"

# 获取节点上下文
python cli.py --json /path/to/conversations.json --context <node_id>

# 导出为 context 格式（直接给大模型用）
python cli.py --json /path/to/conversations.json --export --max-tokens 8000
```

### 2. Python API 调用

```python
from conversation_gateway import ConversationGateway

# 初始化
gw = ConversationGateway("/path/to/conversations.json")

# 列出所有对话
convs = gw.get_conversations()
for c in convs:
    print(f"{c.title} - {c.node_count} 节点")

# 获取最大的对话
largest = gw.find_largest_conversation()

# 加载对话到内存
gw.load_conversation(largest.id)

# 搜索关键词
results = gw.search("OpenClaw", max_results=10)
for r in results:
    print(f"[{r['role']}] {r['content'][:100]}")

# 获取节点上下文
ctx = gw.get_context(node_id, before=5, after=5)

# 获取从根到某节点的路径
path = gw.get_ancestry(node_id)

# 导出为可直接使用的 context
context_str = gw.export_for_context_window(max_tokens=4000)
```

### 3. MCP Server 模式

可以让大模型通过 MCP 协议直接调用：

```bash
python cli.py --json /path/to/conversations.json --mcp
```

## 核心 API

### ConversationGateway

| 方法 | 说明 |
|------|------|
| `get_conversations()` | 获取所有对话摘要 |
| `find_largest_conversation()` | 获取节点最多的对话 |
| `load_conversation(id)` | 加载指定对话 |
| `search(query, max_results)` | 全文搜索 |
| `get_message(node_id)` | 获取单条消息 |
| `get_context(node_id, before, after)` | 获取前后上下文 |
| `get_ancestry(node_id)` | 获取从根到节点的路径 |
| `get_all_messages(max_messages)` | 获取所有消息 |
| `export_for_context_window(max_tokens)` | 导出为 context 格式 |

### Message 结构

```python
@dataclass
class Message:
    node_id: str           # 节点唯一 ID
    role: Role             # user / assistant / system
    content: str            # 消息内容
    timestamp: float       # 时间戳
    parent_id: str         # 父节点 ID
    children_ids: list     # 子节点 ID 列表
```

## 典型使用场景

### 场景 1: 继续之前的工作

```python
# 找到之前的对话
gw = ConversationGateway("conversations.json")
largest = gw.find_largest_conversation()

# 搜索之前讨论的内容
results = gw.search("OpenClaw 架构")

# 获取相关的上下文片段
for r in results[:5]:
    ctx = gw.get_context(r['node_id'], before=2, after=2)
    print(ctx)
```

### 场景 2: 给大模型提供上下文

```python
# 导出为 context 格式
context = gw.export_for_context_window(
    conversation_id="对话ID",
    max_tokens=8000
)

# 直接发送给大模型
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "你是 OpenClaw 项目的助手，正在继续之前的工作。"},
        {"role": "user", "content": context}
    ]
)
```

### 场景 3: 作为 MCP 工具调用

```python
# MCP Server 模式，大模型可以直接调用这些工具
tools = [
    "list_conversations",      # 列出对话
    "search_conversation",     # 搜索
    "get_message",             # 获取消息
    "get_context",             # 获取上下文
    "get_ancestry",            # 获取路径
    "export_context"           # 导出
]
```

## 数据格式

输入的 `conversations.json` 格式（ChatGPT 导出格式）：

```json
[
  {
    "id": "对话ID",
    "title": "对话标题",
    "create_time": 1701263540.306412,
    "mapping": {
      "节点ID": {
        "id": "节点ID",
        "parent": "父节点ID或null",
        "children": ["子节点ID列表"],
        "message": {
          "author": {"role": "user|assistant|system"},
          "content": {"parts": ["消息内容"]},
          "metadata": {...}
        }
      }
    }
  }
]
```

## 注意事项

1. **内存占用**：只加载元数据时内存占用小 (~1MB)，加载完整对话 mapping 时 ~50MB
2. **搜索性能**：首次搜索会构建消息缓存，之后搜索会很快
3. **节点 ID**：ChatGPT 的节点 ID 是 UUID 格式，可以从前面的查询结果中获取
