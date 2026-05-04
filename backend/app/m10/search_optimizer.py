import logging
import os
import re
import asyncio
from pydantic import BaseModel, Field

from app.m10.models import IntentProfile

# NOTE: tavily, deerflow.models.factory, and langchain_core are intentionally
# NOT imported at module level.  They are heavy/optional dependencies that are
# only needed at call time; importing them here would crash the entire
# app.channels import chain if any of them is absent.
logger = logging.getLogger(__name__)

class OptimizedPromptPackage(BaseModel):
    system_prompt_enhancements: str = Field(default="", description="给系统预设/底层角色的最佳实践和增强约束建议")
    workflow_suggestions: str = Field(default="", description="工作流推荐（例如：建议分步骤进行、建议使用哪些库等）")
    knowledge_references: list[str] = Field(default_factory=list, description="精选的前沿/优质参考文献链接或摘要")

async def _tavily_search(query: str) -> str:
    """使用 Tavily 进行深度搜索。"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.warning("[M10 Optimizer] No TAVILY_API_KEY found.")
        return ""

    try:
        from tavily import AsyncTavilyClient  # lazy import — optional dependency
        client = AsyncTavilyClient(api_key=api_key)
        response = await client.search(
            query=query,
            search_depth="advanced",
            include_answer=True,
            include_raw_content=False,
            max_results=3
        )
        # 整理上下文
        context = []
        if response.get("answer"):
            context.append(f"Tavily Answer: {response['answer']}")
        for res in response.get("results", []):
            context.append(f"- {res.get('title')}: {res.get('content')} ({res.get('url')})")
        return "\n".join(context)
    except Exception as e:
        logger.error(f"[M10 Optimizer] Tavily search error: {e}")
        return ""

async def _exa_search(query: str) -> str:
    """使用 Exa 进行极简技术搜索。"""
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        logger.warning("[M10 Optimizer] No EXA_API_KEY found.")
        return ""

    try:
        from exa_py import Exa
        exa = Exa(api_key)
        
        def run_exa():
            return exa.search_and_contents(
                query,
                type="auto",
                num_results=2,
                text=True,
                highlights=True
            )
        
        response = await asyncio.to_thread(run_exa)
        
        context = []
        for res in response.results:
            snippet = res.text[:300] + "..." if res.text else ""
            context.append(f"- {res.title}: {snippet} ({res.url})")
        return "\n".join(context)
    except Exception as e:
        logger.error(f"[M10 Optimizer] Exa search error: {e}")
        return ""

async def optimize_intent(profile: IntentProfile) -> OptimizedPromptPackage:
    """
    基于已明确的用户意图，实时使用外部搜索组装增强的提示词包。
    """
    logger.info(f"[M10 Optimizer] 开始为任务目标 '{profile.goal}' 进行提示词优化。")

    # 根据 Profile 生成专门领域的搜索词
    # 对于开发任务，我们可以搜索最新库版本、最佳实践
    search_query = f"{profile.goal} latest best practices documentation github"
    if profile.constraints:
        search_query += f" avoid {' '.join(profile.constraints)}"
    
    logger.info(f"[M10 Optimizer] 搜索策略执行中: {search_query}")
    
    # 并发进行两大引擎检索
    tavily_task = asyncio.create_task(_tavily_search(search_query))
    exa_task = asyncio.create_task(_exa_search(search_query))
    
    results = await asyncio.gather(tavily_task, exa_task, return_exceptions=True)
    tavily_ctx = results[0] if isinstance(results[0], str) else ""
    exa_ctx = results[1] if isinstance(results[1], str) else ""
    
    combined_context = f"====== Tavily 视野 ======\n{tavily_ctx}\n\n====== Exa 视野 ======\n{exa_ctx}"
    
    # 呼叫 LLM 进行规整输出
    try:
        # Lazy imports — only pulled in when the LLM call is actually needed.
        from deerflow.models.factory import create_chat_model  # noqa: PLC0415
        from langchain_core.messages import SystemMessage, HumanMessage  # noqa: PLC0415

        system_prompt = """你是一个代码与提示词增强大师。请结合以下外部搜索结果，给 LangGraph 的 Agent 提供最优的解决思路、约束纪律以及推荐工作流。
重要：你的输出必须是一个完整的 JSON 对象，不要包含任何其他文字，不要包含 <thinking> 标签。
JSON 格式如下：
{
  "system_prompt_enhancements": "字符串",
  "workflow_suggestions": "字符串",
  "knowledge_references": [{"title": "字符串", "url": "字符串", "snippet": "字符串"}]
}"""
        text_prompt = f"我的原始任务意图：\n{profile.model_dump_json(indent=2)}\n\n我搜索到的最新外部知识库：\n{combined_context}\n\n请输出针对此任务的最优规划！"

        # 使用 thinking_enabled=False 并显式设置 extra_body 来禁用 thinking
        llm = create_chat_model(thinking_enabled=False)
        # 额外确保禁用 thinking - 设置 extra_body
        llm = llm.bind(
            extra_body={
                "thinking": {"type": "disabled"},
                "reasoning_effort": "off"
            }
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=text_prompt)
        ]

        # 直接调用 LLM 获取文本响应
        response = await llm.ainvoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)

        # 移除 <think> 和 </think> 标签和其内容 (MiniMax 使用 Markdown 格式的 thinking 标签)
        response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)

        # 尝试提取 JSON
        # 先尝试直接解析整个响应
        try:
            pkg = OptimizedPromptPackage.model_validate_json(response_text.strip())
            logger.info("[M10 Optimizer] 提示词包增强完成 (直接解析)。")
            return pkg
        except Exception:
            pass

        # 如果直接解析失败，尝试提取 JSON 代码块
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                pkg = OptimizedPromptPackage.model_validate_json(json_match.group(1).strip())
                logger.info("[M10 Optimizer] 提示词包增强完成 (从代码块提取)。")
                return pkg
            except Exception:
                pass

        # 尝试找到第一个 { 到最后一个 } 之间的内容
        first_brace = response_text.find('{')
        last_brace = response_text.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_str = response_text[first_brace:last_brace + 1]
            try:
                pkg = OptimizedPromptPackage.model_validate_json(json_str.strip())
                logger.info("[M10 Optimizer] 提示词包增强完成 (提取括号内内容)。")
                return pkg
            except Exception:
                pass

        logger.warning(f"[M10 Optimizer] 无法从响应中提取 JSON: {response_text[:200]}")
    except Exception as e:
        logger.exception(f"[M10 Optimizer] 组装 Prompt 异常: {e}")

    # Fallback 返回默认
    return OptimizedPromptPackage(
        system_prompt_enhancements="无外部知识更新，按常规纪律执行。",
        workflow_suggestions="遵循既有逻辑标准直接执行。",
        knowledge_references=[]
    )
