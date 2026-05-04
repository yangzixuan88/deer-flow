"""
Bytebot Adapter — sandbox_tool_coprocessor_for_claude_code
========================================================

ROLE: Subordinate coprocessor serving Claude Code CLI as primary operator.

STATUS: EXPERIMENTAL_DISABLED (see ADAPTER_STATUS below)

CAPABILITY SHAPE ONLY — no bytebotd daemon, bytebot-ui, or bytebot-agent
is imported or executed as a parallel runtime.

Claude Code CLI invokes Bytebot as sandbox_tool_coprocessor_for_claude_code.
Bytebot NEVER:
  - Accepts tasks directly from users or other sources
  - Claims task completion authority
  - Runs as a standalone desktop agent outside sandbox
  - Bypasses Claude Code to update M08/M07 directly

ADAPTER_STATUS: "FUTURE_COPROCESSOR_ORCHESTRATION"
  当前状态: 物理不可达（not merely disabled — unreachable by design in current arch）

  为什么不可达:
    1. claude_code_route() 是 sync 函数，其 coprocessor 分支（_route_bytebot_sandbox 等）
       物理上不可达——这是架构设计，不是 bug。
    2. 即使 _route_bytebot_sandbox 被调用（它永远不会被调用），request_bytebot_capability()
       是 async 函数，需要 await；但 claude_code_route 是 sync 函数，不能 await。
    3. 当前真实的执行治理通过 HarnessReviewMiddleware (OCHA L2) 实现，
       工具在执行前已经过 OCHA L2 audit。
    4. _validate_routing_context() 在工具执行后调用 claude_code_route() 作为
       "路由策略验证器"（S1 语义闭环），不是物理执行入口。

  本适配器不是"待启用的 disabled"，而是"架构中当前物理不存在的未来编排路径"。
  不建议通过补 await 来"启用"——这会引入架构混淆（sync 函数 await async 协程）。
  若未来需要 Claude Code → Bytebot 真实编排，应通过独立 async 入口实现。

CONTROLLED_EVOLVABLE:
  - bytebotd Docker container (Xvfb + XFCE4 + nut-js)
  - /computer-use REST API client pattern (move_mouse, click_mouse, screenshot, type_text)
  - NutService (cross-platform desktop automation via nut-js)
  - InputTrackingService (action replay for replay/audit)

FORBIDDEN_EXPANSION:
  - bytebot-agent — parallel agent runtime
  - bytebot-ui — parallel UI
  - bytebot-agent-cc — parallel agent-cloud connector
  - bytebot-llm-proxy — parallel LLM routing

Only the Docker image recipe and REST API client SHAPE are extracted.
The bytebotd container IS the isolation boundary — not a parallel agent runtime.

M08回流 record shape:
  primary_operator: "Claude Code CLI"
  supporting_capability: "Bytebot sandbox"
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("m11_bytebot_adapter")

EXTERNAL_VENDOR_PATH = "e:/OpenClaw-Base/deerflow/backend/external/bytebot"


@dataclass
class BytebotCapability:
    """Shape of an available Bytebot capability."""
    name: str
    type: str  # 'docker' | 'rest_api' | 'automation' | 'replay'
    risk_level: str  # 'low' | 'medium' | 'high'
    governance_required: bool = True
    forbidden_parallel: bool = False


AVAILABLE_CAPABILITIES: List[BytebotCapability] = [
    # Docker desktop sandbox — high risk but isolated in container
    BytebotCapability(name="bytebotd_docker", type="docker", risk_level="high"),
    # REST API actions — medium risk, all actions logged
    BytebotCapability(name="computer_use_api", type="rest_api", risk_level="medium"),
    # nut-js automation service
    BytebotCapability(name="NutService", type="automation", risk_level="medium"),
    # Action replay for audit — medium risk
    BytebotCapability(name="InputTrackingService", type="replay", risk_level="medium"),
]

FORBIDDEN_PARALLEL_SYSTEMS: List[BytebotCapability] = [
    BytebotCapability(name="bytebot-agent", type="agent_runtime", risk_level="high", forbidden_parallel=True),
    BytebotCapability(name="bytebot-ui", type="ui_runtime", risk_level="high", forbidden_parallel=True),
    BytebotCapability(name="bytebot-agent-cc", type="cloud_connector", risk_level="high", forbidden_parallel=True),
    BytebotCapability(name="bytebot-llm-proxy", type="llm_router", risk_level="high", forbidden_parallel=True),
]


# REST API action shapes (from packages/shared/src/computer_use_service.ts)
COMPUTER_USE_ACTIONS = [
    "move_mouse",
    "click_mouse",
    "right_click_mouse",
    "scroll",
    "type_text",
    "press_key",
    "screenshot",
    "screenshot_area",
    "get_clipboard",
    "set_clipboard",
]


def is_forbidden_parallel(capability_name: str) -> bool:
    """Return True if a capability would create a parallel runtime."""
    return any(
        f.name == capability_name or capability_name.endswith(f".{f.name.split('.')[-1]}")
        for f in FORBIDDEN_PARALLEL_SYSTEMS
    )


async def request_bytebot_capability(
    capability_name: str,
    task_config: Dict[str, Any],
    governance_bridge: Any,
) -> Dict[str, Any]:
    """
    Request a Bytebot sandbox capability through governance gate.

    Returns governance decision with Docker sandbox profile and REST API shape.

    CONTROLLED_EVOLVABLE: desktop_isolation_task → governance_bridge.check_meta_governance
    """
    if is_forbidden_parallel(capability_name):
        logger.warning(f"[BytebotAdapter] FORBIDDEN_PARALLEL requested: {capability_name}")
        return {
            "approved": False,
            "blocked": True,
            "reason": f"FORBIDDEN_EXPANSION: {capability_name} would create parallel runtime — blocked",
            "forbidden_parallel": True,
        }

    # Governance gate for desktop isolation capability
    try:
        decision = await governance_bridge.check_meta_governance({
            "decision_type": "capability_admission",
            "description": f"Bytebot sandbox: {capability_name}",
            "risk_level": _risk_level(capability_name),
            "stake_holders": ["governance", "M08_learning_SOR"],
            "capability_name": capability_name,
            "capability_type": _capability_type(capability_name),
            "isolation_level": task_config.get("isolation_level", "container"),
        })
        approved = decision.applied or not decision.blocking
    except Exception as e:
        logger.warning(f"[BytebotAdapter] Governance check failed: {e}")
        approved = False

    return {
        "approved": approved,
        "blocked": not approved,
        "capability_name": capability_name,
        "type": _capability_type(capability_name),
        "invocation_shape": _invocation_shape(capability_name, task_config),
        "governance_required": True,
        "outcome_feeds_M08": True,
        "docker_isolation": True,  # bytebotd container IS the isolation boundary
    }


def _risk_level(capability_name: str) -> str:
    cap = next((c for c in AVAILABLE_CAPABILITIES if c.name == capability_name), None)
    return cap.risk_level if cap else "high"


def _capability_type(capability_name: str) -> str:
    cap = next((c for c in AVAILABLE_CAPABILITIES + FORBIDDEN_PARALLEL_SYSTEMS
                if c.name == capability_name), None)
    return cap.type if cap else "unknown"


def _invocation_shape(capability_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return the invocation SHAPE for the requested capability.
    This is a descriptor only — no actual runtime import.
    """
    shapes = {
        "bytebotd_docker": {
            "docker_image": "bytebotd:latest",
            "docker_compose_path": "external/bytebot/docker/docker-compose.yml",
            "runtime_args": {
                "display": ":99",
                "screen_resolution": config.get("resolution", "1920x1080"),
            },
            "isolation": "container (Xfce4 + Xvfb)",
            "note": "Desktop daemon container; nut-js automation runs inside; NOT a parallel agent",
        },
        "computer_use_api": {
            "base_url": config.get("bytebotd_url", "http://localhost:8765"),
            "endpoint": "/computer-use",
            "actions": COMPUTER_USE_ACTIONS,
            "action_shape": {
                "move_mouse": {"x": "int", "y": "int"},
                "click_mouse": {"button": "left|right|middle", "x": "int", "y": "int"},
                "type_text": {"text": "str", "delay_ms": "int"},
                "screenshot": {"region": "x,y,w,h (optional)"},
                "press_key": {"key": "str"},
            },
            "note": "REST API client pattern only; real calls go through governance-gated executor",
        },
        "NutService": {
            "module": "packages.bytebotd.services.nut_service",
            "type": "cross_platform_desktop_automation",
            "note": "nut-js based; provides mouse/keyboard/screen APIs inside container",
        },
        "InputTrackingService": {
            "module": "packages.bytebotd.services.input_tracking",
            "type": "action_replay_and_audit",
            "note": "Records all input actions for replay/audit; feeds M08 outcome loop",
        },
    }

    return shapes.get(capability_name, {"error": f"Unknown: {capability_name}"})


def get_docker_compose_path() -> str:
    """Return path to bytebot Docker Compose recipe."""
    return f"{EXTERNAL_VENDOR_PATH}/docker/docker-compose.yml"


def list_safe_capabilities() -> List[Dict[str, str]]:
    """List all non-forbidden Bytebot capabilities."""
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
