import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.m10.models import IntentProfile
from app.m10.llm_evaluator import evaluate_intent
from app.channels.message_bus import InboundMessage
from app.m12.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)

# 默认放行短语（中英双语）。可在 config.yaml 中 `thresholds.magic_proceed_phrases`
# 覆写。匹配采用 casefold + 去标点 + 去空白，规避"大小写/标点差异导致不放行"。
_DEFAULT_MAGIC_PHRASES: tuple[str, ...] = (
    # Chinese
    "你自己决定", "你决定", "随便", "随意", "无", "没有", "开始执行", "直接执行",
    "你看着办", "都行",
    # English
    "you decide", "up to you", "your call", "proceed", "go ahead",
    "no preference", "none", "whatever", "start", "just start",
)

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)


def _normalize(text: str) -> str:
    """Lower-case, strip punctuation & collapse whitespace for robust matching."""
    cleaned = _PUNCT_RE.sub(" ", text or "")
    return " ".join(cleaned.casefold().split())


# ---------------------------------------------------------------------------
# 消息意图类型判别（第 0 层 —— 位于 evaluate_intent 之前）
# ---------------------------------------------------------------------------
# 设计要点（见本文件顶部 "mode-elision" 讨论）：
#   M10 的 evaluate_intent + 追问循环只应在用户 **明确请求执行一个任务** 时启用；
#   日常闲聊、问候、情绪、纯知识问答都应该直接透传给 lead_agent，由它当作普通
#   对话回复。下面的正则给出一个快速 "heuristic 判别器"，LLM 仅在 heuristic
#   判不出来时兜底。
#
# 这一层的关键产出是 ``IntentKind`` —— "CHAT" 直接放行；"ACTION" 才进入追问流。

MODE_CHAT = "chat"
MODE_ACTION = "action"

# 明显的 chat 起始短语（中英文，全字符串起始匹配 + 允许标点结尾）。
_CHAT_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"你好|您好|hi|hello|hey|嗨|哈喽|早|早上好|中午好|晚上好|晚安|good\s+(?:morning|evening|night|afternoon)"
    r"|谢谢|感谢|thank\s*you|thanks|thx"
    r"|哈哈|呵呵|嘿嘿|lol|haha|hehe"
    r"|好的|好呀|行|ok|okay|got\s+it|明白|明白了|收到|roger|sure"
    r"|不错|棒|厉害|nice|cool|great|awesome"
    r"|在吗|在么|你在吗|hello\?*|are\s+you\s+there"
    r")\b",
    flags=re.IGNORECASE,
)

# 纯知识疑问句（用户只是想理解/讨论，而不是让系统去"做什么"）。
_CHAT_QUESTION_RE = re.compile(
    r"^\s*(?:"
    r"为什么|为啥|怎么理解|如何理解|什么是|这是什么|这什么|解释一下|能解释|能否解释|讲讲"
    r"|why\s+|what\s+(?:is|are|does)|how\s+does\s+it|what\s+do\s+you\s+mean|explain\s+to\s+me"
    r"|你觉得|你认为|你看|what\s+do\s+you\s+think"
    r")",
    flags=re.IGNORECASE,
)

# 明显的 action 触发词（用户把"让系统去做什么"写进了消息）。
_ACTION_TRIGGER_RE = re.compile(
    r"(?:"
    # 中文动作动词 / 祈使
    r"帮(?:我|忙)|请(?:帮|给|你)|给我(?:写|做|查|搜|生成|画|翻译)|替我|麻烦你"
    r"|执行|创建|生成|写一个|写个|写一份|做一个|做一份|做个|构建|搭建|开发|实现|部署|编译|运行"
    r"|搜(?:一下|下|索)?|查(?:一下|下|询|找|资料)|看一下(?:这|那)|找一下"
    r"|修复|重构|优化|分析|总结|翻译成?|转换为?|整理|列出|导出|下载|抓取|爬取"
    # 英文动作动词（起始或"please/help me"后接）
    r"|\b(?:please|pls)\s+\w+"
    r"|\bhelp\s+me\s+\w+"
    r"|\b(?:build|make|create|write|generate|search|find|lookup|look\s+up|scrape|deploy|"
    r"compile|run|execute|fix|refactor|analyze|summarize|translate|implement|develop|"
    r"list|export|download|fetch|draft|design)\s+(?:a|an|the|my|some|this|that|all|"
    r"me\s+)?\w+"
    r")",
    flags=re.IGNORECASE,
)


@dataclass
class ClarificationResult:
    action: str  # "ask_user", "ask_user_options", "proceed"
    question: str = ""
    intent_profile: IntentProfile | None = None
    options: list[str] | None = None
    # True 当本轮由 engine 判定为已澄清（供下游 middleware / logging 用，见 issue #1）
    clarified_by_engine: bool = False
    # 新增：消息类型判决。"chat" → 纯对话；"action" → 需要任务上下文。
    mode: str = MODE_ACTION
    # Diagnostics-only: 为什么最终走了这条路径（heuristic / llm / fallback / ...）。
    classification_reason: str = ""


class ClarificationEngine:
    """M10 意图澄清引擎。管理多轮追问的状态循环。

    重构要点（vs. 原版）:
      1. ``questions_asked`` 增量在 ``process_inbound`` 显式点递增，不再埋在
         ``_generate_question`` 里（issue #9）。
      2. 放行短语来自配置 + 中英双语 + 大小写/标点不敏感（issue #6）。
      3. 问题由 LLM 上下文生成，失败时回退到硬编码模板（issue #3）。
      4. 已澄清的 thread 在新消息看起来像"新任务"时会重置 profile（issue #2）。
      5. ``last_question_at`` 在真正发出问题时记录，供 TimeoutManager 使用（issue #4）。
      6. LLM 评估错误不再被静默吞掉；engine 会把它作为可观察事件看待（issue #5）。
    """

    def __init__(self):
        # We lazily import get_paths to avoid circular dependencies
        from deerflow.config.paths import get_paths
        self.get_paths = get_paths

    # ---- 状态持久化 ------------------------------------------------------

    def _get_state_file(self, thread_id: str) -> Path:
        outputs_dir = self.get_paths().sandbox_outputs_dir(thread_id).resolve()
        outputs_dir.mkdir(parents=True, exist_ok=True)
        return outputs_dir / ".m10_state.json"

    def load_state(self, thread_id: str) -> IntentProfile | None:
        state_file = self._get_state_file(thread_id)
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                return IntentProfile(**data)
            except Exception as e:
                logger.warning(f"无法读取 M10 状态文件: {e}")
        return None

    def save_state(self, thread_id: str, profile: IntentProfile):
        state_file = self._get_state_file(thread_id)
        state_file.write_text(profile.model_dump_json(indent=2), encoding="utf-8")

    # ---- 辅助：短语匹配 / 新任务检测 ------------------------------------

    def _magic_phrases(self) -> Iterable[str]:
        custom = UnifiedConfig().get("thresholds.magic_proceed_phrases", None)
        if isinstance(custom, list) and custom:
            return [str(p) for p in custom]
        return _DEFAULT_MAGIC_PHRASES

    def _is_magic_phrase(self, text: str) -> bool:
        norm = _normalize(text)
        if not norm:
            return False
        for phrase in self._magic_phrases():
            if norm == _normalize(phrase):
                return True
        return False

    def _looks_like_new_task(self, clarified: IntentProfile, message_text: str) -> bool:
        """Heuristic: after a thread was already cleared, if the user's new
        message is long enough to be a fresh task description AND doesn't mention
        the prior goal, treat it as a new task and reset (issue #2).

        This is intentionally conservative — we'd rather miss a boundary than
        wipe mid-task state. Threshold: message length >= 12 chars/words AND
        zero lexical overlap with the old goal's significant terms.
        """
        text = (message_text or "").strip()
        if len(text) < 12:
            return False
        old_goal = (clarified.goal or "").strip()
        if not old_goal:
            return False
        old_terms = {t for t in _normalize(old_goal).split() if len(t) >= 3}
        new_terms = set(_normalize(text).split())
        if not old_terms:
            return False
        overlap = old_terms & new_terms
        # No significant term overlap → likely a pivot to new task.
        return not overlap

    # ---- 消息意图分类（CHAT vs ACTION）----------------------------------

    def _heuristic_classify(self, text: str) -> tuple[str, str] | None:
        """Fast regex-based classifier. Returns (mode, reason) or None if unsure.

        Order of checks matters:
          1. action trigger first — 若同时命中 action 与 chat 前缀（比如
             "你好 帮我写一段 python"），应判为 action。
          2. 明显 chat 起始 + 无 action trigger → chat
          3. 纯知识问句 + 无 action trigger → chat
          4. 极短消息（<= 6 chars）无 action trigger → chat（寒暄 / 嗯 / 哦）
          5. 其他 → 让 LLM 去分
        """
        if not text or not text.strip():
            return (MODE_CHAT, "empty_message")

        stripped = text.strip()
        has_action = bool(_ACTION_TRIGGER_RE.search(stripped))
        if has_action:
            return (MODE_ACTION, "heuristic_action_trigger")

        # 没有 action 迹象时再看 chat 信号
        if _CHAT_PREFIX_RE.match(stripped):
            return (MODE_CHAT, "heuristic_chat_prefix")
        if _CHAT_QUESTION_RE.match(stripped):
            return (MODE_CHAT, "heuristic_pure_question")
        # 去除非字母数字字符后长度 <=6（含中文字符判断用 len() 近似）
        tight = _PUNCT_RE.sub("", stripped).strip()
        if len(tight) <= 6:
            return (MODE_CHAT, "heuristic_short_utterance")

        return None  # 交给 LLM 兜底

    async def _llm_classify(self, text: str, current_profile: IntentProfile | None) -> tuple[str, str]:
        """Ask a light LLM call: is this CHAT or ACTION? Cheap & short output."""
        try:
            from deerflow.models.factory import create_chat_model
            from langchain_core.messages import SystemMessage, HumanMessage

            has_open_task = bool(
                current_profile and (current_profile.goal or "").strip()
                and not current_profile.is_clarified()
            )
            system_prompt = (
                "你是一个消息类型判别器。根据用户输入，判断它属于以下哪一种：\n"
                "- CHAT：闲聊、问候、情绪表达、纯知识问答、对之前回答的反馈或追问；\n"
                "- ACTION：明确请求系统执行一个具体任务——搜索资料、写代码、生成文件、"
                "调度工作流、启动自主代理、做分析、翻译、总结等。\n"
                "仅输出一个单词：CHAT 或 ACTION，不要解释。"
            )
            ctx_hint = ""
            if has_open_task:
                ctx_hint = (
                    f"\n\n(上下文提示：当前 thread 已有未澄清完的任务目标"
                    f"'{current_profile.goal}'，如果用户消息是对这个任务的补充回答，应判为 ACTION。)"
                )
            llm = create_chat_model(thinking_enabled=False).bind(
                extra_body={"thinking": {"type": "disabled"}, "reasoning_effort": "off"},
                max_tokens=8,
            )
            response = await llm.ainvoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=f"用户消息：\n{text}{ctx_hint}")]
            )
            raw = response.content if hasattr(response, "content") else str(response)
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip().upper()
            if "ACTION" in raw:
                return (MODE_ACTION, "llm_action")
            if "CHAT" in raw:
                return (MODE_CHAT, "llm_chat")
            logger.warning(f"[M10] LLM 分类器返回无法解析: {raw!r}，默认 CHAT。")
            return (MODE_CHAT, "llm_unparseable_defaulted_chat")
        except Exception as e:
            logger.warning(f"[M10] LLM 分类器异常，默认 CHAT: {e}")
            return (MODE_CHAT, "llm_exception_defaulted_chat")

    async def _classify_message(self, text: str, current_profile: IntentProfile | None) -> tuple[str, str]:
        """Two-tier classifier. Returns (mode, reason).

        **Bias toward CHAT** when truly ambiguous —— 用户明确要求过"不要动不动就提问"，
        误判为 CHAT 的代价只是少优化一次任务 prompt；误判为 ACTION 的代价是问话
        打断对话体验（核心问题）。因此两层都倾向于保守放行。
        """
        # 已有开启中的澄清循环：视为 ACTION 延续。
        if current_profile and not current_profile.is_clarified() and current_profile.questions_asked > 0:
            return (MODE_ACTION, "continuing_open_clarification")

        heuristic = self._heuristic_classify(text)
        if heuristic is not None:
            return heuristic

        # 兜底让 LLM 判，模糊时返回 CHAT。
        return await self._llm_classify(text, current_profile)

    # ---- 问题生成：LLM 优先，模板兜底 -----------------------------------

    def _template_question(self, profile: IntentProfile) -> str:
        """Deterministic fallback used when the LLM question generator fails."""
        max_questions = UnifiedConfig().get("thresholds.max_questions", 4)
        if "goal" in profile.missing_critical or "deliverable" in profile.missing_critical:
            return (
                "收到任务，但在开始之前需要确认一下：您最终想要什么样的结果？"
                "或者说，做完之后产出物具体应该长什么样？（例如：Python脚本、总结报告还是直接回答）"
            )
        if "quality_bar" in profile.missing_critical or "constraints" in profile.missing_critical:
            return (
                "明白了。那么关于质量标准或边界有什么要求吗？什么样算是达到了您的期望？"
                "有没有不能碰的东西或强制不用的方案？"
            )
        if profile.questions_asked >= max_questions - 1:
            return (
                "好的。执行前最后一个专项问题：这些产出物主要给谁看/用？"
                "有什么特别偏好或上下文背景需要我参考吗？"
            )
        return (
            "还有什么您觉得我需要知道的吗？比如特定的格式要求或时间上的限制？"
            "如果不需要，请直接回复「开始执行」或「无」。"
        )

    async def _llm_question(self, profile: IntentProfile, original_text: str) -> str | None:
        """Ask the LLM to generate a context-aware, single focused question.

        Returns None on any failure, so the caller can fall back to the template.
        """
        try:
            from deerflow.models.factory import create_chat_model
            from langchain_core.messages import SystemMessage, HumanMessage

            system_prompt = (
                "你是一个任务澄清助手。请基于当前已知的意图画像与用户最近的消息，"
                "生成一个【单一焦点】的自然语言反问，补齐画像中缺失的关键字段。\n"
                "规则：\n"
                "1. 只问一个问题，语气友好、不要啰嗦；\n"
                "2. 如果用户的语种是英文，请用英文回复；如果是中文，请用中文；\n"
                "3. 不要重复已填充字段的信息；\n"
                "4. 如果缺 goal/deliverable，优先问；其次 quality_bar/constraints；最后 deadline；\n"
                "5. 只输出问题本身，不要前缀、不要引号、不要解释。"
            )
            user_prompt = (
                f"当前意图画像：\n{profile.model_dump_json(indent=2)}\n\n"
                f"用户最新消息：\n{original_text}\n\n"
                f"请生成下一个反问。"
            )
            llm = create_chat_model(thinking_enabled=False).bind(
                extra_body={"thinking": {"type": "disabled"}, "reasoning_effort": "off"}
            )
            response = await llm.ainvoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            )
            text = response.content if hasattr(response, "content") else str(response)
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            # Take only the first line to avoid multi-question floods.
            first_line = text.splitlines()[0].strip() if text else ""
            if first_line and len(first_line) <= 500:
                return first_line
            logger.warning("[M10] LLM 生成的追问为空或超长，回退到模板。")
        except Exception as e:
            logger.warning(f"[M10] LLM 追问生成失败，回退到模板: {e}")
        return None

    async def _generate_question(self, profile: IntentProfile, original_text: str) -> str:
        """Pure question producer — no side effects (issue #9)."""
        llm_q = await self._llm_question(profile, original_text)
        if llm_q:
            return llm_q
        return self._template_question(profile)

    # ---- 主入口 ----------------------------------------------------------

    async def process_inbound(self, msg: InboundMessage, thread_id: str) -> ClarificationResult:
        """拦截处理进入的消息。

        **第 0 层**：先判定这条消息是 CHAT 还是 ACTION。
        只有 ACTION 才进入后续的 evaluate_intent + 追问循环；CHAT 直接
        透传到 lead_agent，由它作为普通对话回复——这才是用户明确要求的
        "日常交流不被打断" 的行为。
        """
        logger.info(f"[M10] 正在处理 thread_id: {thread_id} 的意图澄清。")
        current_profile = self.load_state(thread_id)

        # --- 第 0 层：消息类型分类 ----------------------------------------
        mode, reason = await self._classify_message(msg.text, current_profile)
        logger.info(f"[M10] 消息分类: mode={mode}, reason={reason}, text_head={msg.text[:60]!r}")

        if mode == MODE_CHAT:
            # 闲聊 / 纯问答 / 情绪表达 —— 完全不动 profile、不起 evaluate_intent、
            # 不触发 search_optimizer，直接放行让 lead_agent 用对话模式回复。
            # 已有 profile 的 thread 也不删除（用户可能是任务中间抛个玩笑）。
            return ClarificationResult(
                action="proceed",
                intent_profile=current_profile,
                clarified_by_engine=bool(current_profile and current_profile.is_clarified()),
                mode=MODE_CHAT,
                classification_reason=reason,
            )

        # --- 进入 ACTION 流程 --------------------------------------------

        # 1. 已澄清 thread：先检测是否切换成了新任务（issue #2）。
        if current_profile and current_profile.is_clarified():
            if self._looks_like_new_task(current_profile, msg.text):
                logger.info(
                    "[M10] 检测到潜在的新任务切换（无词汇重叠），重置 thread 的 intent profile。"
                )
                current_profile = None  # 触发下方的重新评估
            else:
                return ClarificationResult(
                    action="proceed",
                    intent_profile=current_profile,
                    clarified_by_engine=True,
                    mode=MODE_ACTION,
                    classification_reason=reason,
                )

        # 2. 用户用放行短语 → 直接放行；**不要**浪费 LLM 调用（issue #6）。
        if current_profile and self._is_magic_phrase(msg.text):
            logger.info("[M10] 用户授权自由决定（magic phrase 命中），终止澄清。")
            current_profile.clarity_score = 1.0
            current_profile.refresh_task_signature()
            self.save_state(thread_id, current_profile)
            return ClarificationResult(
                action="proceed",
                intent_profile=current_profile,
                clarified_by_engine=True,
                mode=MODE_ACTION,
                classification_reason=reason,
            )

        # 3. LLM 评估当前输入（合并到历史 profile）。
        new_profile = await evaluate_intent(msg.text, current_profile)

        # 4. 评估失败的 observability：保留 error 标记写盘，但不卡住用户——
        #    回退策略是按 current_profile 的已知信息继续走追问路径，直到
        #    questions_asked 达上限后兜底放行（issue #5）。
        if new_profile.evaluation_error:
            logger.warning(
                f"[M10] evaluate_intent 返回错误标记: {new_profile.evaluation_error}. "
                "继续按已有 profile 追问/兜底。"
            )

        # 5. 再次检查放行短语（可能是从空状态起首条消息命中）。
        if self._is_magic_phrase(msg.text):
            new_profile.clarity_score = 1.0

        # 6. 判决
        max_questions = UnifiedConfig().get("thresholds.max_questions", 4)
        if new_profile.is_clarified() or new_profile.questions_asked >= max_questions:
            logger.info(
                f"[M10] 意图已明确或达轮次上限。clarity={new_profile.clarity_score}, "
                f"questions_asked={new_profile.questions_asked}"
            )
            new_profile.refresh_task_signature()
            self.save_state(thread_id, new_profile)
            return ClarificationResult(
                action="proceed",
                intent_profile=new_profile,
                clarified_by_engine=True,
                mode=MODE_ACTION,
                classification_reason=reason,
            )

        # 7. 需要继续追问：先生成问题（纯函数），再在此处显式记录副作用
        #    （issue #4 + #9）。
        question = await self._generate_question(new_profile, msg.text)
        new_profile.questions_asked += 1
        new_profile.last_question_at = time.time()
        new_profile.refresh_task_signature()
        self.save_state(thread_id, new_profile)

        return ClarificationResult(
            action="ask_user",
            question=question,
            intent_profile=new_profile,
            clarified_by_engine=False,
            mode=MODE_ACTION,
            classification_reason=reason,
        )
