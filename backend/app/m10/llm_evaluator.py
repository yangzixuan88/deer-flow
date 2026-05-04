import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from deerflow.models.factory import create_chat_model

from app.m10.models import IntentProfile

logger = logging.getLogger(__name__)

# 系统提示词：负责抽取四维参数
EVALUATOR_SYSTEM_PROMPT = """你是一个任务意图解析引擎。
你需要分析用户输入的消息，并将其映射到 IntentProfile 结构中。
核心规则：
1. 请仅提取用户明确提到或可以毫无歧义推断的信息。
2. 如果用户没有提及某个字段，请保留为空字符串("")或空列表([])，绝不随意发散和猜测。
3. 你的输出必须是一个完整的 JSON 对象，不要包含任何其他文字，不要包含 <thinking> 标签。
JSON 格式如下：
{
  "goal": "字符串",
  "deliverable": "字符串",
  "audience": "字符串",
  "quality_bar": "字符串",
  "constraints": ["字符串"],
  "deadline": "字符串",
  "budget_tokens": 数字
}
"""

async def evaluate_intent(message_text: str, current_profile: IntentProfile | None = None) -> IntentProfile:
    """
    使用轻量级大模型对当前的意图进行抽取合并。
    如果存在 current_profile，则会在上一次的基础上增量补充。
    """
    try:
        # 使用基础大模型（关闭深度思考以提高解析速度）
        llm = create_chat_model(thinking_enabled=False)
        # 显式禁用 thinking
        llm = llm.bind(
            extra_body={
                "thinking": {"type": "disabled"},
                "reasoning_effort": "off"
            }
        )

        context_prompt = ""
        if current_profile:
            context_prompt = f"之前已解析出的状态:\n{current_profile.model_dump_json(indent=2)}\n请结合以上的先前状态与下述最新的用户消息，输出合并后的最新 IntentProfile。"
        else:
            context_prompt = "请解析以下新任务请求的 IntentProfile。"

        messages = [
            SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
            HumanMessage(content=f"{context_prompt}\n\n最新的用户消息：\n{message_text}")
        ]

        logger.info("[M10] 调用 LLM 评估当前意图解析...")
        # 直接调用 LLM 获取文本响应
        response = await llm.ainvoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)

        # 移除 <think> 和 </think> 标签和其内容 (MiniMax 使用 Markdown 格式的 thinking 标签)
        response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)

        result = None
        # 尝试直接解析整个响应为 JSON
        try:
            result = IntentProfile.model_validate_json(response_text.strip())
        except Exception:
            pass

        # 如果直接解析失败，尝试提取 JSON 代码块
        if not result:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    result = IntentProfile.model_validate_json(json_match.group(1).strip())
                except Exception:
                    pass

        # 尝试找到第一个 { 到最后一个 } 之间的内容
        if not result:
            first_brace = response_text.find('{')
            last_brace = response_text.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str = response_text[first_brace:last_brace + 1]
                try:
                    result = IntentProfile.model_validate_json(json_str.strip())
                except Exception:
                    pass

        # 验证合法性
        if isinstance(result, IntentProfile):
            # 继承 questions_asked 与运行时元数据（不属于 LLM 解析范围），
            # 避免 LLM 返回时把这些字段重置为默认值。
            if current_profile:
                result.questions_asked = current_profile.questions_asked
                result.last_question_at = current_profile.last_question_at
                result.cached_search_optimization = current_profile.cached_search_optimization
                result.cached_search_signature = current_profile.cached_search_signature
            # 健康返回：显式清空上一轮错误信号（issue #5）
            result.evaluation_error = None
            # 重新计算得分与任务指纹
            result.evaluate_clarity()
            result.refresh_task_signature()
            logger.info(
                f"[M10] 意图解析完成: goal='{result.goal}', "
                f"clarity={result.clarity_score}, signature={result.task_signature}"
            )
            return result
        else:
            error_msg = f"parse_failed: could not extract IntentProfile from LLM response (head={response_text[:200]!r})"
            logger.warning(f"[M10] {error_msg}")
            return _failed_evaluation(current_profile, error_msg)

    except Exception as e:
        logger.exception(f"[M10] evaluate_intent 出错: {e}")
        return _failed_evaluation(current_profile, f"exception: {e!r}")


def _failed_evaluation(
    current_profile: IntentProfile | None,
    error_msg: str,
) -> IntentProfile:
    """Return a profile marked with ``evaluation_error`` so the engine can tell
    "LLM misfired" apart from "user said nothing informative" (issue #5).

    Prior behavior silently returned current_profile unchanged, which made
    transient API outages indistinguishable from a legitimately sparse
    message and caused the engine to ask the same question forever.
    """
    if current_profile is not None:
        # Copy to avoid mutating caller's instance (defensive — pydantic v2).
        profile = current_profile.model_copy(deep=True)
    else:
        profile = IntentProfile()
    profile.evaluation_error = error_msg
    profile.evaluate_clarity()
    profile.refresh_task_signature()
    return profile
