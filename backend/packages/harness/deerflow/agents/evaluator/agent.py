import logging
import json
import re
from typing import Dict, Any, Optional
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage
from deerflow.models.patched_minimax import PatchedChatMiniMax
from deerflow.config.app_config import get_app_config

import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class EvaluatorAgent:
    def __init__(self, model_name: Optional[str] = None):
        # 显式加载 .env 确保在独立运行 (如 harness_server) 时也能获取 Key
        load_dotenv()

        app_config = get_app_config()
        # 优先使用配置中的模型名，默认使用 minimax-m2.7
        self.model_name = model_name or os.getenv("EVALUATOR_MODEL") or "MiniMax-M2.7"

        # 获取 Key
        api_key = os.getenv("MINIMAX_API_KEY")
        if not api_key:
            raise ValueError("MINIMAX_API_KEY environment variable is not set. Evaluator cannot function without a valid API key.")

        self.model = PatchedChatMiniMax(
            model=self.model_name,
            api_key=api_key,
            base_url=os.getenv("MINIMAX_BASE_URL") or "https://api.minimaxi.com/v1",
            temperature=0.1, # 评估需要高度确定性
        )

        # 加载提示词模板
        prompt_path = Path(__file__).parent.parent.parent / "skills" / "system" / "base_evaluator.md"
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.template = f.read()

    async def evaluate(
        self,
        proposed_action: Dict[str, Any],
        agent_thought: str,
        state_summary: str
    ) -> Dict[str, Any]:
        """
        执行评估逻辑
        """
        # 安全格式化：用双大括号转义 JSON 中的单大括号，防止 format() 冲突
        # 同时避免大括号内的冒号导致 KeyError
        safe_proposed_action = json.dumps(proposed_action, ensure_ascii=False, indent=2)
        safe_proposed_action = safe_proposed_action.replace("{", "{{").replace("}", "}}")

        try:
            prompt = self.template.format(
                proposed_action=safe_proposed_action,
                agent_thought=agent_thought,
                state_summary=state_summary
            )
        except (KeyError, ValueError) as e:
            logger.error(f"Template formatting failed: {e}, falling back to raw JSON")
            # 最后的兜底：不用模板格式化，直接拼接
            prompt = f"""# Evaluator Harness System (OCHA L2)

请审计以下工具调用：

提议行为:
{safe_proposed_action}

思考路径: {agent_thought}
历史摘要/状态: {state_summary}

请返回一个 JSON 格式的审计结果：
{{"decision": "APPROVED"|"REJECTED"|"MODIFIED", "reasoning": "...", "modified_action": null}}"""

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="请开始审计上述 Action。")
        ]
        
        try:
            logger.info(f"Evaluator [OCHA L2] started for: {proposed_action.get('name', 'unknown')}")
            response = await self.model.ainvoke(messages)
            content = response.content
            
            # --- 深度防御 JSON 提取逻辑 ---
            import re
            def extract_json(text):
                # 优先级1: 提取 ```json ... ```
                code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
                if code_block:
                    return code_block.group(1)
                # 优先级2: 提取第一个 { 到最后一个 }
                brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
                if brace_match:
                    return brace_match.group(1)
                return text

            clean_json_str = extract_json(content)
            result = None
            try:
                result = json.loads(clean_json_str)
                # 如果模型返回了嵌套的字符串 JSON，递归解析一次
                if isinstance(result, str):
                    result = json.loads(result)
                # 如果是列表，取第一个元素（如果它是字典）
                if isinstance(result, list) and len(result) > 0:
                    result = result[0]
            except (json.JSONDecodeError, TypeError):
                # 最后的兜底：尝试清理常见的无效控制字符
                try:
                    sanitized = re.sub(r"[\x00-\x1F\x7F]", "", clean_json_str)
                    result = json.loads(sanitized)
                except Exception:
                    pass

            # 如果最终还是无法解析为字典，构造一个错误结果，但不是抛出异常
            if not isinstance(result, dict):
                logger.error(f"Failed to parse dict from: {clean_json_str[:100]}")
                return {
                    "decision": "REJECTED",
                    "reasoning": f"解析失败：模型返回了非字典格式 ({type(result).__name__})",
                    "modified_action": None
                }

            # --- 统一字段映射 ---
            decision = str(result.get("decision", "REJECTED")).upper()
            reasoning = result.get("reasoning") or result.get("reason") or "未提供明确审计理由"
            
            logger.info(f"Evaluator Decision: {decision}")
            
            return {
                "decision": decision,
                "reasoning": reasoning,
                "modified_action": result.get("modified_action") or result.get("modified") or None,
                "clarification_needed": result.get("clarification_needed") or None
            }
            
        except Exception as e:
            logger.error(f"OCHA Evaluator Crash: {str(e)}")
            return {
                "decision": "REJECTED",
                "reasoning": f"OCHA 核心组件故障: {str(e)}",
                "modified_action": None
            }
