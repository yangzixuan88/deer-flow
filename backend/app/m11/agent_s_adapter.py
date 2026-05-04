"""
Agent-S Adapter — gui_grounding_coprocessor_for_claude_code
============================================================

ROLE: Subordinate coprocessor serving Claude Code CLI as primary operator.

STATUS: EXPERIMENTAL_DISABLED (see ADAPTER_STATUS below)

CAPABILITY SHAPE ONLY — no Agent-S main loop, bBoN, or CLI is imported or executed.

Claude Code CLI invokes Agent-S as gui_grounding_coprocessor_for_claude_code.
Agent-S NEVER:
  - Accepts tasks directly from users or other sources
  - Claims task completion authority
  - Runs its own main loop or bBoN governance
  - Bypasses Claude Code to update M08/M07 directly

ADAPTER_STATUS: "FUTURE_COPROCESSOR_ORCHESTRATION"
  当前状态: 物理不可达（not merely disabled — unreachable by design in current arch）

  为什么不可达:
    1. claude_code_route() 是 sync 函数，其 coprocessor 分支（_route_agent_s 等）
       物理上不可达——这是架构设计，不是 bug。
    2. 即使 _route_agent_s 被调用（它永远不会被调用），request_agent_s_capability()
       是 async 函数，需要 await；但 claude_code_route 是 sync 函数，不能 await。
    3. 当前真实的执行治理通过 HarnessReviewMiddleware (OCHA L2) 实现，
       工具在执行前已经过 OCHA L2 audit。
    4. _validate_routing_context() 在工具执行后调用 claude_code_route() 作为
       "路由策略验证器"（S1 语义闭环），不是物理执行入口。

  本适配器不是"待启用的 disabled"，而是"架构中当前物理不存在的未来编排路径"。
  不建议通过补 await 来"启用"——这会引入架构混淆（sync 函数 await async 协程）。
  若未来需要 Claude Code → Agent-S 真实编排，应通过独立 async 入口实现。

CONTROLLED_EVOLVABLE:
  - AgentS3.predict(high_difficulty_gui_task) — GUI agent with OSWorldACI grounding
  - OSWorldACI grounding module — OS state observation and action grounding
  - Reflection worker — self-correction via outcome replay

MUST NOT PARALLEL (FORBIDDEN_EXPANSION):
  - bBoN (belief-over-behavior Network) — Agent-S's own governance/NN system
  - CLI main loop — creates a parallel agent runtime
  - CodeAgent — standalone execution without deerflow governance

M08回流 record shape:
  primary_operator: "Claude Code CLI"
  supporting_capability: "Agent-S"
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("m11_agent_s_adapter")

EXTERNAL_VENDOR_PATH = "e:/OpenClaw-Base/deerflow/backend/external/Agent-S"


@dataclass
class AgentSCapability:
    """Shape of an available Agent-S capability for routing decisions."""
    name: str
    type: str  # 'gui_agent' | 'grounding' | 'reflection' | 'mcp'
    risk_level: str  # 'low' | 'medium' | 'high'
    governance_required: bool = True
    forbidden_parallel: bool = False  # True = must NOT create parallel runtime


AVAILABLE_CAPABILITIES: List[AgentSCapability] = [
    # Core GUI agent — medium-high risk, governance gate required
    AgentSCapability(name="AgentS3.predict", type="gui_agent", risk_level="high"),
    # OSWorldACI grounding — medium risk, governance gate required
    AgentSCapability(name="OSWorldACI", type="grounding", risk_level="medium"),
    # Reflection worker — medium risk, outcome replay feeds M08
    AgentSCapability(name="reflection_worker", type="reflection", risk_level="medium"),
]

FORBIDDEN_PARALLEL_SYSTEMS: List[AgentSCapability] = [
    # bBoN is Agent-S's own governance/NN — must NOT be paralleled
    AgentSCapability(name="bBoN", type="governance_nn", risk_level="high", forbidden_parallel=True),
    # CLI main loop creates a parallel runtime
    AgentSCapability(name="agent_s_cli", type="cli_main_loop", risk_level="high", forbidden_parallel=True),
    # CodeAgent runs without deerflow governance
    AgentSCapability(name="CodeAgent", type="standalone_agent", risk_level="high", forbidden_parallel=True),
]


def is_forbidden_parallel(capability_name: str) -> bool:
    """Return True if a capability would create a parallel runtime system."""
    return any(
        f.name == capability_name or capability_name.endswith(f".{f.name.split('.')[-1]}")
        for f in FORBIDDEN_PARALLEL_SYSTEMS
    )


async def request_agent_s_capability(
    capability_name: str,
    task_instruction: str,
    task_observation: Any,
    governance_bridge: Any,
) -> Dict[str, Any]:
    """
    Request an Agent-S capability through governance gate.

    Returns governance decision with invocation shape descriptor.

    CONTROLLED_EVOLVABLE: high_difficulty_gui_task → governance_bridge.check_meta_governance
    FORBIDDEN_EXPANSION: bBoN, CLI, CodeAgent → blocked
    """
    if is_forbidden_parallel(capability_name):
        logger.warning(f"[AgentSAdapter] FORBIDDEN_PARALLEL requested: {capability_name}")
        return {
            "approved": False,
            "blocked": True,
            "reason": f"FORBIDDEN_EXPANSION: {capability_name} would create parallel runtime — blocked",
            "forbidden_parallel": True,
        }

    # Governance gate for GUI agent admission
    try:
        decision = await governance_bridge.check_meta_governance({
            "decision_type": "capability_admission",
            "description": f"Agent-S capability: {capability_name}",
            "risk_level": _risk_level(capability_name),
            "stake_holders": ["governance", "M08_learning_SOR"],
            "capability_name": capability_name,
            "capability_type": _capability_type(capability_name),
            "task_instruction": task_instruction[:200] if task_instruction else None,
        })
        approved = decision.applied or not decision.blocking
    except Exception as e:
        logger.warning(f"[AgentSAdapter] Governance check failed: {e}")
        approved = False

    return {
        "approved": approved,
        "blocked": not approved,
        "capability_name": capability_name,
        "type": _capability_type(capability_name),
        "invocation_shape": _invocation_shape(capability_name, task_instruction, task_observation),
        "governance_required": True,
        "outcome_feeds_M08": True,  # All Agent-S outcomes route back to M08
    }


def _risk_level(capability_name: str) -> str:
    cap = next((c for c in AVAILABLE_CAPABILITIES if c.name == capability_name), None)
    return cap.risk_level if cap else "high"


def _capability_type(capability_name: str) -> str:
    cap = next((c for c in AVAILABLE_CAPABILITIES + FORBIDDEN_PARALLEL_SYSTEMS
                if c.name == capability_name), None)
    return cap.type if cap else "unknown"


def _invocation_shape(capability_name: str, task_instruction: str, task_observation: Any) -> Dict[str, Any]:
    """
    Return the invocation SHAPE for the requested capability.
    This is a descriptor only — no actual runtime import.
    """
    shapes = {
        "AgentS3.predict": {
            "module": "gui_agents.s3.agents.agent_s",
            "class": "AgentS3",
            "method": "predict",
            "params": {
                "instruction": task_instruction,
                "observation": task_observation,
            },
            "return": "action_predictions: List[ActionPrediction]",
            "note": "OSWorldACI grounding required; outcomes must feed M08 record_outcome loop",
            "governance_hook": "governance_bridge.record_outcome after each action",
        },
        "OSWorldACI": {
            "module": "gui_agents.s3.agents.grounding",
            "class": "OSWorldACI",
            "params": {
                "environment": task_observation.get("environment", "desktop"),
                "observation": task_observation,
            },
            "return": "grounded_observation: Dict[str, Any]",
            "note": "OS state observation and action grounding module",
        },
        "reflection_worker": {
            "module": "gui_agents.s3.agents.worker",
            "class": "ReflectionWorker",
            "params": {
                "task_instruction": task_instruction,
                "action_history": task_observation.get("action_history", []),
            },
            "return": "reflection_result: Dict[str, Any]",
            "note": "Self-correction via outcome replay; feeds M08 reputation loop",
        },
    }

    short_name = capability_name.split(".")[-1] if "." in capability_name else capability_name
    return shapes.get(short_name, shapes.get(capability_name, {"error": f"Unknown: {capability_name}"}))


def list_safe_capabilities() -> List[Dict[str, str]]:
    """List all non-forbidden Agent-S capabilities."""
    return [
        {"name": c.name, "type": c.type, "risk_level": c.risk_level}
        for c in AVAILABLE_CAPABILITIES
    ]


def list_forbidden_parallel_systems() -> List[Dict[str, str]]:
    """List all FORBIDDEN_EXPANSION parallel system components."""
    return [
        {"name": c.name, "type": c.type, "risk_level": c.risk_level}
        for c in FORBIDDEN_PARALLEL_SYSTEMS
    ]
