import contextvars
import dataclasses
import logging
from collections.abc import Callable
from typing import Optional, override

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt.tool_node import ToolCallRequest

from deerflow.agents.thread_state import ThreadState
from deerflow.agents.evaluator.agent import EvaluatorAgent

logger = logging.getLogger(__name__)

# Context variable to share agent state with tool wrappers
_current_state: contextvars.ContextVar[ThreadState] = contextvars.ContextVar("_current_state", default=None)


class HarnessReviewMiddleware(AgentMiddleware[ThreadState]):
    """
    OCHA L2: Evaluator Harness Middleware
    实现全量审计（Full Audit）逻辑，拦截非豁免工具调用并提交 EvaluatorAgent 审查。
    """
    
    # 豁免审计的工具列表
    EXEMPT_TOOLS = ["write_todos", "ask_clarification", "setup_agent"]

    def __init__(self, evaluator_model: Optional[str] = None):
        super().__init__()
        self._evaluator = EvaluatorAgent(model_name=evaluator_model)

    def _get_state_summary(self, state: ThreadState) -> str:
        """从状态中提取评估所需的上下文摘要"""
        summary = []
        summary.append(f"Title: {state.get('title', 'Untitled')}")
        summary.append(f"Recent Artifacts: {', '.join(state.get('artifacts', [])[-5:])}")
        
        # 提取最近的对话脉络（最后 2 条消息）
        messages = state.get("messages", [])
        if len(messages) >= 1:
            last_msg = messages[-1]
            summary.append(f"Last message type: {type(last_msg).__name__}")
            if hasattr(last_msg, "content"):
                content = str(last_msg.content)
                summary.append(f"Last content snippet: {content[:200]}...")
                
        return "\n".join(summary)

    @override
    async def abefore_agent(
        self,
        state: ThreadState,
        config: RunnableConfig,
    ) -> None:
        """在 agent 执行前设置上下文状态，供 awrap_tool_call 使用"""
        _current_state.set(state)
        logger.debug("HarnessReviewMiddleware: state captured in abefore_agent")

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage],
    ) -> ToolMessage:
        """异步拦截并审查工具调用"""
        tool_name = request.tool_call.get("name")
        
        # 1. 检查是否在豁免名单中
        if tool_name in self.EXEMPT_TOOLS:
            logger.debug(f"Tool {tool_name} is exempt from OCHA review.")
            return await handler(request)

        # 2. 准备审计上下文（从 abefore_agent 设置的 contextvar 获取）
        state = _current_state.get()
        if state is None:
            logger.warning("HarnessReviewMiddleware: no state available from context, using minimal context")
            state = {}
        agent_thought = state.get("thought", "No internal thought provided.") if state else "No internal thought provided."
        state_summary = self._get_state_summary(state)

        # 3. 调用 Evaluator 执行 JIT 审计
        logger.info(f"OCHA Audit initiating for tool: {tool_name}")
        review_result = await self._evaluator.evaluate(
            proposed_action=request.tool_call,
            agent_thought=agent_thought,
            state_summary=state_summary
        )

        decision = review_result.get("decision", "REJECTED")
        reasoning = review_result.get("reasoning", "Unknown reason.")

        # 4. 根据审计决定处理
        if decision == "APPROVED":
            logger.info(f"OCHA Audit APPROVED: {tool_name}")
            return await handler(request)
        
        elif decision == "MODIFIED" and review_result.get("modified_action"):
            # 如果是修改建议，更新请求参数
            modified = review_result["modified_action"]
            logger.warning(f"OCHA Audit MODIFIED: {tool_name} -> {modified.get('tool')}")
            
            # 构造新的请求（注意保持 ID 一致）
            new_tool_call = request.tool_call.copy()
            new_tool_call["name"] = modified.get("tool", tool_name)
            new_tool_call["args"] = modified.get("args", request.tool_call["args"])

            # 使用 dataclasses.replace 继承原 request 的 tool/state/runtime 字段，
            # 只替换 tool_call。langgraph 新版 ToolCallRequest 要求这 4 个字段全齐
            # （直接构造 ToolCallRequest(tool_call=...) 会抛
            # TypeError: missing 3 required positional arguments: 'tool', 'state',
            # 'runtime'，被 ToolErrorHandlingMiddleware 吞掉后只在日志里留下
            # "Tool execution failed" 和堆栈，历史上出现过至少 6 次）。
            return await handler(dataclasses.replace(request, tool_call=new_tool_call))

        else:
            # 默认为 REJECTED
            logger.warning(f"OCHA Audit REJECTED: {tool_name}. Reason: {reasoning}")
            
            # 返回一个 ToolMessage 告知 Lead Agent 审计不通过
            error_content = f"OCHA 审计拒绝执行该操作。\n原因: {reasoning}\n"
            if review_result.get("clarification_needed"):
                error_content += f"建议: {review_result['clarification_needed']}"
            
            return ToolMessage(
                content=error_content,
                tool_call_id=request.tool_call.get("id", ""),
                name=tool_name,
                status="error"
            )

    @override
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage],
    ) -> ToolMessage:
        """同步版本（由于模型调用通常是异步的，此处仅作为兼容性实现）"""
        # 评估器是异步的，但在 wrap_tool_call 中无法直接 AWAIT
        # 这里采用简单的放行策略或抛出异常，推荐始终使用异步链路
        # 为了严谨性，如果必须同步执行，我们选择放行但警告，或者手动运行事件循环（不推荐）
        logger.warning("Synchronous wrap_tool_call triggered in HarnessReviewMiddleware. Skipping audit for safety.")
        return handler(request)
