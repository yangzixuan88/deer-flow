from typing import Optional, Any
from langchain_core.tools import tool
from deerflow.agents.memory.storage import get_memory_storage
from deerflow.agents.memory.vector_storage import QdrantMemoryStorage
from deerflow.assets.memory_manager import CognitiveMemoryManager
import logging

logger = logging.getLogger(__name__)

@tool
async def ingest_knowledge(text: str, metadata: Optional[dict[str, Any]] = None) -> str:
    """将语义知识存入长期向量记忆库。
    
    此工具允许将特定事实、文档片段或重要上下文存储在向量数据库中，以便将来通过 RAG 进行检索。
    
    Args:
        text: 要存储的文本内容。
        metadata: 可选的元数据字典（例如：来源、类别）。
    """
    storage = get_memory_storage()
    if not isinstance(storage, QdrantMemoryStorage):
        return "错误：当前未启用向量存储。语义知识注入仅在 Qdrant 模式下可用。"
    
    # 注入工具来源标识
    final_metadata = metadata or {}
    if "source" not in final_metadata:
        final_metadata["source"] = "knowledge_tool"
        
    try:
        success = await storage.ingest(text, metadata=final_metadata)
        if success:
            logger.info("知识库完成入库: %s", text[:50])
            return f"✅ 知识已成功存入语义向量库：\n内容摘要：\"{text[:100]}...\""
        else:
            return "⚠️ 知识存入操作未报告错误，但返回了失败状态。请检查存储后端。"
    except Exception as e:
        logger.error("知识库入库异常: %s", e)
        return f"❌ 存入知识发生异常: {str(e)}"

@tool
async def search_memories(query: str, category: str = "all", limit: int = 5) -> str:
    """搜索长期记忆和历史经验。
    
    Args:
        query: 搜索关键词或语义描述。
        category: 类别 (all|experiences|facts)。
        limit: 返回结果的最大数量。
    """
    results = []
    
    # 1. 搜索事实库 (Facts)
    if category in ["all", "facts"]:
        storage = get_memory_storage()
        if isinstance(storage, QdrantMemoryStorage):
            facts = await storage.search(query, limit=limit)
            for f in facts:
                results.append(f"📌 [事实库] {f.content} (Score: {f.score:.2f})")
                
    # 2. 语义搜索经验资产 (XP)
    if category in ["all", "experiences"]:
        try:
            mm = CognitiveMemoryManager()
            xp_assets = mm.search_memory(query, limit=limit)
            for a in xp_assets:
                results.append(f"🧠 [历史经验] {a['name']} - {a.get('metadata', {}).get('summary', '无摘要')} (Tier: {a.get('tier', 'T4')})")
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            
    if not results:
        return f"🥀 未找到与 '{query}' 相关的记忆内容。"
        
    return "### 🔍 检索到的深度认知记忆:\n" + "\n".join(results)
