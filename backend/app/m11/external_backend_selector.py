"""
External Backend Selector — DEPRECATED in favor of claude_code_router.py
==========================================================================

THIS FILE IS DEPRECATED.

All task routing now flows through claude_code_router.py which enforces
Claude Code CLI as the primary operator.

external_backend_selector.py is retained as a coprocessor registry helper only.
Do NOT use this as the entry point for task routing.

The primary routing entry point is: claude_code_router.claude_code_route()

This file is kept for: list_all_external_capabilities() and
get_backend_manifest() which are used by governance reporting only.

Routing table (applies after governance approval):
  task.type          task.difficulty   destination
  ─────────────────────────────────────────────────────
  web_scrape         low/medium        Scrapling HTTP/Browser
  web_scrape         high              Scrapling Spider + Agent-S
  gui_interaction     low/medium        operator stack
  gui_interaction     high              Agent-S backend
  desktop_isolation   any               Bytebot Docker sandbox
  mixed (web+gui)    medium/high       Agent-S backend
  file_operation     low/medium        operator stack
  file_operation     high              Bytebot sandbox

The selector NEVER:
  - Imports or executes a vendor's main loop / CLI
  - Creates parallel learning systems (M08 bypass)
  - Creates parallel asset systems (M07 bypass)
  - Grows layers above R19
  - Bypasses governance gate
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.m11.governance_bridge import governance_bridge

from app.m11 import scrapling_adapter
from app.m11 import agent_s_adapter
from app.m11 import bytebot_sandbox_mode

logger = logging.getLogger("m11_external_selector")


class TaskType(Enum):
    WEB_SCRAPE = "web_scrape"
    GUI_INTERACTION = "gui_interaction"
    DESKTOP_ISOLATION = "desktop_isolation"
    MIXED = "mixed"
    FILE_OPERATION = "file_operation"
    UNKNOWN = "unknown"


class TaskDifficulty(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RoutingDecision:
    destination: str  # 'scrapling' | 'agent_s' | 'bytebot' | 'operator_stack'
    capability_name: str
    invocation_shape: Dict[str, Any]
    governance_approved: bool
    blocked_reason: Optional[str] = None
    quarantined: bool = False
    forbidden_parallel: bool = False


def classify_task(task_descriptor: Dict[str, Any]) -> Tuple[TaskType, TaskDifficulty]:
    """
    Classify a task by type and difficulty based on its descriptor.

    Returns (TaskType, TaskDifficulty)
    """
    task_type = task_descriptor.get("type", "unknown")
    task_difficulty = task_descriptor.get("difficulty", "medium")
    has_gui = task_descriptor.get("has_gui", False)
    has_browser = task_descriptor.get("has_browser", False)
    requires_isolation = task_descriptor.get("requires_isolation", False)
    is_high_risk = task_descriptor.get("is_high_risk", False)

    # Infer task type from descriptor fields
    inferred_type = task_type
    if inferred_type == "unknown":
        if requires_isolation or is_high_risk:
            inferred_type = "desktop_isolation"
        elif has_gui:
            inferred_type = "gui_interaction"
        elif has_browser:
            inferred_type = "web_scrape"
        else:
            inferred_type = "unknown"

    # Map to enums
    type_map = {
        "web_scrape": TaskType.WEB_SCRAPE,
        "gui_interaction": TaskType.GUI_INTERACTION,
        "desktop_isolation": TaskType.DESKTOP_ISOLATION,
        "mixed": TaskType.MIXED,
        "file_operation": TaskType.FILE_OPERATION,
    }
    difficulty_map = {
        "low": TaskDifficulty.LOW,
        "medium": TaskDifficulty.MEDIUM,
        "high": TaskDifficulty.HIGH,
    }

    return (
        type_map.get(inferred_type, TaskType.UNKNOWN),
        difficulty_map.get(task_difficulty, TaskDifficulty.MEDIUM),
    )


def route_task(task_descriptor: Dict[str, Any]) -> RoutingDecision:
    """
    Main routing function: decides which backend handles a task.

    All governance checks happen here before capability admission.

    Returns RoutingDecision with destination and governance status.
    """
    task_type, task_difficulty = classify_task(task_descriptor)
    capability_name = task_descriptor.get("capability_name", "")
    task_instruction = task_descriptor.get("instruction", "")

    logger.info(f"[ExternalSelector] Routing: type={task_type.value} difficulty={task_difficulty.value}")

    # ── Route based on type + difficulty matrix ──────────────────────────────

    if task_type == TaskType.WEB_SCRAPE:
        return _route_web_scrape(task_descriptor, task_difficulty)

    elif task_type == TaskType.GUI_INTERACTION:
        return _route_gui_interaction(task_descriptor, task_difficulty)

    elif task_type == TaskType.DESKTOP_ISOLATION:
        return _route_desktop_isolation(task_descriptor)

    elif task_type == TaskType.MIXED:
        return _route_mixed(task_descriptor, task_difficulty)

    elif task_type == TaskType.FILE_OPERATION:
        # File operations always go to operator stack (internal)
        return _route_operator_stack(task_descriptor, "file_operation")

    else:
        return _route_operator_stack(task_descriptor, "unknown")


def _route_web_scrape(task_descriptor: Dict[str, Any], difficulty: TaskDifficulty) -> RoutingDecision:
    """Route web scraping tasks to Scrapling adapter."""
    has_js = task_descriptor.get("has_javascript_rendering", False)
    is_concurrent = task_descriptor.get("is_concurrent", False)

    if is_concurrent:
        capability = "scrapling.Spider"
    elif has_js:
        capability = "scrapling.DynamicFetcher"
    else:
        capability = "scrapling.Fetcher"

    return _governance_and_wrap(
        capability,
        task_descriptor,
        instruction=task_descriptor.get("url", ""),
    )


def _route_gui_interaction(task_descriptor: Dict[str, Any], difficulty: TaskDifficulty) -> RoutingDecision:
    """Route GUI interaction tasks."""
    if difficulty == TaskDifficulty.HIGH:
        # High-difficulty GUI → Agent-S
        return _governance_and_wrap_agent_s(task_descriptor, "AgentS3.predict")
    else:
        # Low/medium → operator stack
        return _route_operator_stack(task_descriptor, "gui_interaction")


def _route_desktop_isolation(task_descriptor: Dict[str, Any]) -> RoutingDecision:
    """Route desktop isolation tasks to Bytebot sandbox."""
    return _governance_and_wrap(
        "bytebotd_docker",
        task_descriptor,
        instruction=task_descriptor.get("instruction", ""),
    )


def _route_mixed(task_descriptor: Dict[str, Any], difficulty: TaskDifficulty) -> RoutingDecision:
    """Route mixed (web + GUI) tasks to Agent-S for high difficulty, Scrapling for medium."""
    if difficulty == TaskDifficulty.HIGH:
        return _governance_and_wrap_agent_s(task_descriptor, "AgentS3.predict")
    else:
        capability = "scrapling.Spider"
        return _governance_and_wrap(
            capability,
            task_descriptor,
            instruction=task_descriptor.get("url", ""),
        )


def _route_operator_stack(task_descriptor: Dict[str, Any], reason: str) -> RoutingDecision:
    """Route to internal operator stack (no external backend needed)."""
    return RoutingDecision(
        destination="operator_stack",
        capability_name="internal",
        invocation_shape={
            "reason": reason,
            "instruction": task_descriptor.get("instruction", ""),
            "note": "No external backend required; use internal operator stack",
        },
        governance_approved=True,
        blocked_reason=None,
    )


async def _governance_and_wrap(
    capability_name: str,
    task_descriptor: Dict[str, Any],
    instruction: str = "",
) -> RoutingDecision:
    """Apply governance check and wrap with Scrapling adapter."""
    try:
        approved = await scrapling_adapter.request_scrapling_capability(
            capability_name,
            task_descriptor,
            governance_bridge,
        )
    except Exception as e:
        logger.warning(f"[ExternalSelector] Scrapling governance check failed: {e}")
        approved = {"approved": False, "blocked": True, "reason": str(e)}

    if approved.get("blocked"):
        return RoutingDecision(
            destination="scrapling",
            capability_name=capability_name,
            invocation_shape=approved,
            governance_approved=False,
            blocked_reason=approved.get("reason"),
            quarantined=approved.get("quarantined", False),
        )

    return RoutingDecision(
        destination="scrapling",
        capability_name=capability_name,
        invocation_shape=approved.get("invocation_shape", {}),
        governance_approved=True,
    )


async def _governance_and_wrap_agent_s(
    task_descriptor: Dict[str, Any],
    capability_name: str,
) -> RoutingDecision:
    """Apply governance check and wrap with Agent-S adapter."""
    try:
        approved = await agent_s_adapter.request_agent_s_capability(
            capability_name,
            task_descriptor.get("instruction", ""),
            task_descriptor.get("observation", {}),
            governance_bridge,
        )
    except Exception as e:
        logger.warning(f"[ExternalSelector] Agent-S governance check failed: {e}")
        approved = {"approved": False, "blocked": True, "reason": str(e)}

    if approved.get("blocked"):
        return RoutingDecision(
            destination="agent_s",
            capability_name=capability_name,
            invocation_shape=approved,
            governance_approved=False,
            blocked_reason=approved.get("reason"),
            forbidden_parallel=approved.get("forbidden_parallel", False),
        )

    return RoutingDecision(
        destination="agent_s",
        capability_name=capability_name,
        invocation_shape=approved.get("invocation_shape", {}),
        governance_approved=True,
    )


# ── Public registry ────────────────────────────────────────────────────────────

def list_all_external_capabilities() -> Dict[str, List[Dict[str, str]]]:
    """Return all registered external capabilities grouped by backend."""
    return {
        "scrapling": {
            "safe": scrapling_adapter.list_safe_capabilities(),
            "quarantined": scrapling_adapter.list_quarantined_capabilities(),
        },
        "agent_s": {
            "safe": agent_s_adapter.list_safe_capabilities(),
            "forbidden_parallel": agent_s_adapter.list_forbidden_parallel_systems(),
        },
        "bytebot": {
            "safe": bytebot_sandbox_mode.list_safe_capabilities(),
            "forbidden_parallel": bytebot_sandbox_mode.list_forbidden_parallel_systems(),
        },
    }


def get_backend_manifest() -> Dict[str, Any]:
    """
    Return the full external backend manifest for governance visibility.
    Published via /health/governance as the 'external_backends' field.
    """
    capabilities = list_all_external_capabilities()
    return {
        "backends": ["scrapling", "agent_s", "bytebot"],
        "total_safe_capabilities": (
            len(capabilities["scrapling"]["safe"])
            + len(capabilities["agent_s"]["safe"])
            + len(capabilities["bytebot"]["safe"])
        ),
        "total_quarantined": (
            len(capabilities["scrapling"]["quarantined"])
            + len(capabilities["agent_s"]["forbidden_parallel"])
            + len(capabilities["bytebot"]["forbidden_parallel"])
        ),
        "routing_policy": "governance_gated | no_parallel_systems | no_bypass_routes",
        "capabilities": capabilities,
    }
