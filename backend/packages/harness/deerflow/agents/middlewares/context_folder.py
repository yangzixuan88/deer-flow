import logging
import hashlib
from typing import Any, Dict, List, Optional, override
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain.agents.middleware import AgentMiddleware
from deerflow.agents.thread_state import ThreadState

logger = logging.getLogger(__name__)

class ContextFolderMiddleware(AgentMiddleware[ThreadState]):
    """
    ACI (Adaptive Context Integration) - Liquid context Folding
    实现液态上下文折叠：通过 Hash Anchor 识别关键节点，动态压缩非关键历史。
    """
    
    def __init__(self, threshold_messages: int = 15):
        super().__init__()
        self.threshold = threshold_messages

    def _calculate_hash_anchor(self, message: BaseMessage) -> str:
        """为消息生成 Hash 锚点，用于识别关键状态转换"""
        content = str(message.content)
        # 如果是工具调用，包含工具名
        if isinstance(message, AIMessage) and message.tool_calls:
            content += "".join([tc["name"] for tc in message.tool_calls])
        
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:8]

    def _is_anchor(self, message: BaseMessage) -> bool:
        """判定一条消息是否为不可折叠的强锚点"""
        # 1. 系统消息始终保留
        if isinstance(message, SystemMessage):
            return True
        
        # 2. 包含关键工具调用的消息（TODO, 澄清, 设置）
        if isinstance(message, AIMessage):
            for tc in message.tool_calls:
                if tc["name"] in ["write_todos", "ask_clarification", "setup_agent"]:
                    return True
            # 如果内容中由 AI 显式标记了 [Anchor]
            if "[Anchor]" in str(message.content):
                return True
        
        # 3. 最新的消息对（保留最近的 4 条以维持即时对话连贯性）
        return False

    def _fold_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """液态折叠逻辑"""
        if len(messages) <= self.threshold:
            return messages

        folded_history = []
        recent_cutoff = 4 # 始终保留最近 4 条
        
        # 分离出需要处理的历史区和保留的活跃区
        head = messages[:-recent_cutoff]
        tail = messages[-recent_cutoff:]
        
        last_fold_idx = -1
        
        for i, msg in enumerate(head):
            if self._is_anchor(msg) or i == 0: # 保留第一条和所有锚点
                # 如果之前有连续的非锚点消息，产生一个折叠块摘要（此处目前做标记，未来可接入 LLM Summary）
                if i - last_fold_idx > 1:
                    fold_size = i - last_fold_idx - 1
                    # 插入一个液态折叠标记位
                    anchor_token = self._calculate_hash_anchor(messages[i-1])
                    folded_history.append(SystemMessage(
                        content=f"--- [Liquid Fold: {fold_size} messages compressed | Hash: {anchor_token}] ---"
                    ))
                
                folded_history.append(msg)
                last_fold_idx = i
        
        # 处理 head 结尾的折叠
        if len(head) - last_fold_idx > 1:
            fold_size = len(head) - last_fold_idx - 1
            folded_history.append(SystemMessage(
                content=f"--- [Liquid Fold: {fold_size} messages compressed] ---"
            ))
            
        folded_history.extend(tail)
        return folded_history

    @override
    def wrap_pre_invoke(self, state: ThreadState) -> ThreadState:
        """在调用 LLM 之前执行折叠逻辑"""
        messages = state.get("messages", [])
        if not messages:
            return state
            
        original_count = len(messages)
        folded_messages = self._fold_messages(messages)
        new_count = len(folded_messages)
        
        if new_count < original_count:
            logger.info(f"ACI Liquid Fold triggered: {original_count} -> {new_count} messages.")
            # 更新状态中的消息
            # 注意：由于 state 是 TypedDict，这里需要 shallow copy 或直接更新
            state["messages"] = folded_messages
            
        return state
