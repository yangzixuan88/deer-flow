from pydantic import BaseModel, Field
from typing import Any, List, Optional

class IntentProfile(BaseModel):
    """
    M10 意图画像结构 (IntentProfile)
    记录任务澄清状态的核心数据结构。
    """
    # 核心意图
    goal: str = Field(default="", description="最终想达成什么")
    deliverable: str = Field(default="", description="产出物是什么形态")
    audience: str = Field(default="", description="给谁用/谁来看")
    quality_bar: str = Field(default="", description="什么叫做好")

    # 约束
    constraints: List[str] = Field(default_factory=list, description="不能做什么/不能碰什么")
    dependencies: List[str] = Field(default_factory=list, description="前置条件有哪些")
    deadline: Optional[str] = Field(default=None, description="时间要求")
    budget_tokens: Optional[str] = Field(default=None, description="资源预算（AAL模式用）")

    # 上下文
    domain: str = Field(default="", description="属于哪个领域")
    task_type: str = Field(default="", description="任务类型（搜索/代码/写作等）")
    mode: str = Field(default="", description="对应哪种执行模式")
    related_assets: List[str] = Field(default_factory=list, description="相关的历史资产ID")

    # 澄清状态
    clarity_score: float = Field(default=0.0, description="0-1，≥0.85开始执行")
    questions_asked: int = Field(default=0, description="已问了几个问题")
    filled_fields: List[str] = Field(default_factory=list, description="已填充的字段名称")
    missing_critical: List[str] = Field(default_factory=list, description="仍缺失的关键字段名称")

    # --- 新增：运行时元数据 -------------------------------------------------
    # 用户最后一次被提问的 Unix 时间戳；TimeoutManager 依据它判断"静默时长"，
    # 避免用 state-file mtime 被 LLM 评估写盘意外重置（修复 issue #4）。
    last_question_at: Optional[float] = Field(
        default=None,
        description="Unix ts of last question sent to user; None if never asked",
    )
    # 任务指纹：对已澄清 profile 的 goal/deliverable 做简短归一化。
    # 用于（1）检测新任务（issue #2）；（2）缓存 search_optimizer 结果（issue #8）。
    task_signature: str = Field(
        default="",
        description="Normalized signature of goal+deliverable; changes → new task",
    )
    # LLM 评估异常时写入，避免外层把"LLM 炸了"当成"用户没说清楚"（issue #5）。
    evaluation_error: Optional[str] = Field(
        default=None,
        description="Last evaluate_intent failure message; None if healthy",
    )
    # 缓存 search_optimizer 的结果，配合 task_signature 复用（issue #8）。
    cached_search_optimization: Optional[dict[str, Any]] = Field(
        default=None,
        description="Cached OptimizedPromptPackage.model_dump() for task_signature",
    )
    cached_search_signature: Optional[str] = Field(
        default=None,
        description="task_signature when cached_search_optimization was produced",
    )

    def evaluate_clarity(self) -> float:
        """
        根据五维权重重新计算当前画像的质量评分。
        基于规范，评分算法：
        goal已明确      +0.30
        deliverable已明确 +0.25
        quality_bar已明确 +0.20
        constraints已明确 +0.15
        deadline/budget已明确 +0.10
        """
        score = 0.0
        filled = []
        missing = []

        if self.goal and self.goal.strip():
            score += 0.30
            filled.append("goal")
        else:
            missing.append("goal")

        if self.deliverable and self.deliverable.strip():
            score += 0.25
            filled.append("deliverable")
        else:
            missing.append("deliverable")

        if self.quality_bar and self.quality_bar.strip():
            score += 0.20
            filled.append("quality_bar")
        else:
            missing.append("quality_bar")

        if self.constraints and len(self.constraints) > 0:
            score += 0.15
            filled.append("constraints")
        else:
            missing.append("constraints")

        if (self.deadline and self.deadline.strip()) or (self.budget_tokens and str(self.budget_tokens).strip()):
            score += 0.10
            filled.append("deadline/budget_tokens")
        else:
            missing.append("deadline/budget_tokens")

        self.clarity_score = round(min(score, 1.0), 2)
        self.filled_fields = filled
        self.missing_critical = missing

        return self.clarity_score

    def is_clarified(self) -> bool:
        """判断是否满足 >= 阈值 的强制执行门槛。

        每次调用都先重算 clarity_score，防止字段已填充但分数尚未刷新时的
        静默误判（把"已清晰"的任务继续当作"待澄清"反复追问）。
        """
        self.evaluate_clarity()  # 强制刷新，不依赖缓存值
        from app.m12.unified_config import UnifiedConfig
        threshold = UnifiedConfig().get("thresholds.clarity_threshold", 0.85)
        return self.clarity_score >= threshold

    # ------------------------------------------------------------------
    # 任务指纹 —— 用于新任务检测与 search_optimizer 结果缓存键。
    # 采用短 MD5 前缀以保持文件体积，goal+deliverable 小写去空白后 hash。
    # ------------------------------------------------------------------
    def compute_task_signature(self) -> str:
        import hashlib
        raw = f"{(self.goal or '').strip().lower()}||{(self.deliverable or '').strip().lower()}"
        if not raw.strip("|"):
            return ""
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]

    def refresh_task_signature(self) -> str:
        """Recompute and store task_signature in-place."""
        self.task_signature = self.compute_task_signature()
        return self.task_signature
