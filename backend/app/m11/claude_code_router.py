"""
Claude Code Router — S1 Routing Policy Validator / Coprocessor Orchestration Blueprint
=====================================================================================
M11 — R17-R19 Governance — R17

ARCHITECTURE ROLE (precise, as of R58):
  ACTUAL execution governance:    HarnessReviewMiddleware (OCHA L2) — pre-execution gate
  ACTUAL outcome backflow:       LearningMiddleware → governance_bridge.record_outcome()
  THIS module (S1 validator):     Post-execution routing audit via _validate_routing_context()
  THIS module (coprocessor):     FUTURE aspirational blueprint — physically unreachable now

====================================================================
SYSTEM STATUS: CORE_ARCHITECTURE_FROZEN | OCHA_L2_ACTIVE | COPROCESSOR_FUTURE
====================================================================

S1 Semantic Closure (current physical role):
  - HarnessReviewMiddleware governs tool execution (pre-check, blocking on REJECTED).
  - After execution, LearningMiddleware._validate_routing_context() calls
    claude_code_route() to record routing policy compliance as audit trail.
  - In this post-execution role, DIRECT_EXECUTE is always returned
    (tool has already executed under OCHA L2 governance).

Future Coprocessor Orchestration (aspirational, not live code):
  - Coprocessor branches (_route_scrapling, _route_agent_s, _route_bytebot_sandbox)
    define routing policy for a future state where Claude Code orchestrates
    external coprocessors as subordinates.
  - Physically unreachable: claude_code_route() is sync; these branches are never called.
  - Retained as architectural blueprint, not active code paths.

Routing Protocol (S1 validator role):
  1. LearningMiddleware calls claude_code_route() after tool execution
  2. claude_code_route() returns RoutingDecision for audit record
  3. Coprocessor branches = documented policy, not physical execution paths

Execution Paths (documented policy / not physical in current arch):
  direct_execute          — OCHA-L2-governed tool execution (current live path)
  use_scrapling          — Future: Scrapling as subordinate coprocessor
  use_agent_s            — Future: Agent-S as subordinate coprocessor
  use_bytebot_sandbox    — Future: Bytebot as subordinate coprocessor
  use_operator_stack     — Low-level: operator stack as subordinate
  compose_multiple       — Future: multi-capability composition

This module SUPERSEDES external_backend_selector as the authoritative routing
policy reference. external_backend_selector is retained as coprocessor registry.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from app.m11.governance_bridge import governance_bridge
from app.m11 import scrapling_adapter
from app.m11 import agent_s_adapter
from app.m11 import bytebot_sandbox_mode
from app.m11.claude_code_primary_role import (
    PRIMARY_OPERATOR_ID,
    COPROCESSOR_REGISTRY,
    REGISTERED_COPROCESSORS,
    get_primary_operator_record,
    get_coprocessor_by_key,
)

logger = logging.getLogger("m11_claude_code_router")


class ExecutionPath(Enum):
    """Claude Code's possible execution decisions."""
    DIRECT_EXECUTE = "direct_execute"
    USE_SCRAPLING = "use_scrapling"
    USE_AGENT_S = "use_agent_s"
    USE_BYTEBOT_SANDBOX = "use_bytebot_sandbox"
    USE_OPERATOR_STACK = "use_operator_stack"
    COMPOSE_MULTIPLE = "compose_multiple"


@dataclass
class RoutingDecision:
    """Claude Code's routing decision for a task."""
    execution_path: ExecutionPath
    primary_operator: str  # Always "Claude Code CLI"
    coprocessor: Optional[str]        # Which coprocessor (if any)
    invocation_shape: Dict[str, Any]  # How to invoke
    governance_approved: bool
    blocked_reason: Optional[str] = None
    compose_plan: Optional[List[str]] = None  # For COMPOSE_MULTIPLE


@dataclass
class TaskDescriptor:
    """
    Unified task descriptor — all tasks enter through this shape.
    Claude Code is the only entity that creates and interprets these.
    """
    task_id: str
    instruction: str
    task_type: str          # 'web_scrape' | 'gui_interaction' | 'desktop_isolation' | 'mixed' | 'file_operation' | 'engineering' | 'unknown'
    difficulty: str          # 'low' | 'medium' | 'high'
    has_javascript: bool = False
    requires_isolation: bool = False
    is_high_risk: bool = False
    has_gui: bool = False
    requires_grounding: bool = False
    requires_multi_step: bool = False
    context: Dict[str, Any] = field(default_factory=dict)
    # Fields for M08/M07回流
    supporting_capability: Optional[str] = None


# ─── Claude Code's Primary Routing Decision Engine ──────────────────────────────

def claude_code_route(task: TaskDescriptor) -> RoutingDecision:
    """
    Routing Policy Validator / S1 Semantic Closure.

    THIS IS NOT THE PRIMARY EXECUTION GATE.
    Actual execution governance flows through HarnessReviewMiddleware (OCHA L2).

    This function serves two roles:
    1. S1 Routing Validator (post-execution): Called by LearningMiddleware after
       tool execution to create an auditable record of routing policy compliance.
       In this role, it always returns DIRECT_EXECUTE because the actual tool
       has already been executed (governed by OCHA L2).
    2. Future Coprocessor Orchestration (inactive): The coprocessor branches
       (_route_scrapling, _route_agent_s, _route_bytebot_sandbox) are defined
       for future Claude Code → coprocessor orchestration but are physically
       unreachable in the current architecture — they require claude_code_route
       itself to be async, which it is not, and are further gated behind task
       types that are handled by DIRECT_EXECUTE in practice.

    Returns RoutingDecision with Claude Code as primary_operator.
    """
    logger.info(
        f"[ClaudeCodeRouter] Task {task.task_id}: "
        f"type={task.task_type} difficulty={task.difficulty}"
    )

    # ── Claude Code's own judgment: can I handle this directly? ──────────────
    if _is_direct_executable(task):
        logger.info(f"[ClaudeCodeRouter] Claude Code → DIRECT_EXECUTE")
        return RoutingDecision(
            execution_path=ExecutionPath.DIRECT_EXECUTE,
            primary_operator=PRIMARY_OPERATOR_ID,
            coprocessor=None,
            invocation_shape={
                "handler": "Claude Code CLI",
                "mode": "direct_execute",
                "instruction": task.instruction,
                "task_category": task.task_type,
            },
            governance_approved=True,
        )

    # ── Single coprocessor decisions ─────────────────────────────────────────
    if task.task_type in ("web_scrape", "web_crawl") and task.difficulty != "high":
        return _route_scrapling(task)

    if task.task_type in ("gui_interaction", "mixed") and task.difficulty == "high":
        return _route_agent_s(task)

    if task.requires_isolation or task.task_type == "desktop_isolation":
        return _route_bytebot_sandbox(task)

    if task.task_type in ("file_operation", "low_level_execution"):
        return _route_operator_stack(task)

    # ── Multi-coprocessor composition ────────────────────────────────────────
    if task.requires_multi_step or (task.difficulty == "high" and task.requires_grounding):
        return _route_compose_multiple(task)

    # ── Default: Claude Code handles it ──────────────────────────────────────
    # Even unknown tasks fall back to Claude Code as primary operator
    logger.info(f"[ClaudeCodeRouter] Default → DIRECT_EXECUTE (fallback_brain)")
    return RoutingDecision(
        execution_path=ExecutionPath.DIRECT_EXECUTE,
        primary_operator=PRIMARY_OPERATOR_ID,
        coprocessor=None,
        invocation_shape={
            "handler": "Claude Code CLI",
            "mode": "fallback_brain",
            "instruction": task.instruction,
            "fallback_reason": "unclassified_task",
        },
        governance_approved=True,
    )


def _is_direct_executable(task: TaskDescriptor) -> bool:
    """
    Claude Code decides: can I handle this myself without invoking a coprocessor?

    Direct execute applies when:
    - Task is engineering/code-focused (Claude Code's core strength)
    - Difficulty is low/medium and doesn't require browser/isolation
    - No specific coprocessor capability is needed
    """
    engineering_task_types = {
        "engineering", "code_generation", "code_modification",
        "architectural_design", "diagnostic", "planning",
        "general_reasoning", "multi_step_planning", "unknown",
    }

    if task.task_type in engineering_task_types:
        return True

    # Low-difficulty web tasks can be described to Scrapling by Claude Code
    # but for simple URL fetches, Claude Code can handle directly
    if task.task_type == "web_scrape" and task.difficulty == "low" and not task.has_javascript:
        return True

    # Simple GUI actions at low difficulty don't need Agent-S
    if task.task_type == "gui_interaction" and task.difficulty == "low":
        return True

    return False


async def _route_scrapling(task: TaskDescriptor) -> RoutingDecision:
    """Route to Scrapling as subordinate coprocessor."""
    capability = "scrapling.Fetcher"
    if task.has_javascript:
        capability = "scrapling.DynamicFetcher"

    try:
        approved = await scrapling_adapter.request_scrapling_capability(
            capability,
            {"url": task.instruction, **task.context},
            governance_bridge,
        )
    except Exception as e:
        logger.warning(f"[ClaudeCodeRouter] Scrapling governance check failed: {e}")
        approved = {"approved": False, "blocked": True, "reason": str(e)}

    if approved.get("blocked"):
        # Fall back to Claude Code direct execution
        logger.warning(f"[ClaudeCodeRouter] Scrapling blocked: {approved.get('reason')}, falling back to direct")
        return RoutingDecision(
            execution_path=ExecutionPath.DIRECT_EXECUTE,
            primary_operator=PRIMARY_OPERATOR_ID,
            coprocessor="scrapling",
            invocation_shape={
                "handler": "Claude Code CLI",
                "mode": "fallback_brain",
                "reason": "coprocessor_blocked",
                "original_coprocessor": "Scrapling",
            },
            governance_approved=True,
        )

    return RoutingDecision(
        execution_path=ExecutionPath.USE_SCRAPLING,
        primary_operator=PRIMARY_OPERATOR_ID,
        coprocessor="scrapling",
        invocation_shape={
            "handler": "Scrapling",
            "mode": "web_extraction_coprocessor_for_claude_code",
            "capability": capability,
            "claude_code_instruction": task.instruction,
            "returns_to": "Claude Code CLI",
        },
        governance_approved=True,
    )


async def _route_agent_s(task: TaskDescriptor) -> RoutingDecision:
    """Route to Agent-S as subordinate coprocessor for high-difficulty GUI tasks."""
    try:
        approved = await agent_s_adapter.request_agent_s_capability(
            "AgentS3.predict",
            task.instruction,
            task.context.get("observation", {}),
            governance_bridge,
        )
    except Exception as e:
        logger.warning(f"[ClaudeCodeRouter] Agent-S governance check failed: {e}")
        approved = {"approved": False, "blocked": True, "reason": str(e)}

    if approved.get("blocked"):
        logger.warning(f"[ClaudeCodeRouter] Agent-S blocked: {approved.get('reason')}, falling back to direct")
        return RoutingDecision(
            execution_path=ExecutionPath.DIRECT_EXECUTE,
            primary_operator=PRIMARY_OPERATOR_ID,
            coprocessor="agent_s",
            invocation_shape={
                "handler": "Claude Code CLI",
                "mode": "fallback_brain",
                "reason": "coprocessor_blocked",
                "original_coprocessor": "Agent-S",
            },
            governance_approved=True,
        )

    return RoutingDecision(
        execution_path=ExecutionPath.USE_AGENT_S,
        primary_operator=PRIMARY_OPERATOR_ID,
        coprocessor="agent_s",
        invocation_shape={
            "handler": "Agent-S",
            "mode": "gui_grounding_coprocessor_for_claude_code",
            "capability": "AgentS3.predict",
            "claude_code_instruction": task.instruction,
            "returns_to": "Claude Code CLI",
            "outcome_feeds_m08": True,
        },
        governance_approved=True,
    )


async def _route_bytebot_sandbox(task: TaskDescriptor) -> RoutingDecision:
    """Route to Bytebot sandbox as subordinate coprocessor for desktop isolation."""
    try:
        approved = await bytebot_sandbox_mode.request_bytebot_capability(
            "bytebotd_docker",
            {"isolation_level": "container", **task.context},
            governance_bridge,
        )
    except Exception as e:
        logger.warning(f"[ClaudeCodeRouter] Bytebot governance check failed: {e}")
        approved = {"approved": False, "blocked": True, "reason": str(e)}

    if approved.get("blocked"):
        logger.warning(f"[ClaudeCodeRouter] Bytebot blocked: {approved.get('reason')}, falling back to direct")
        return RoutingDecision(
            execution_path=ExecutionPath.DIRECT_EXECUTE,
            primary_operator=PRIMARY_OPERATOR_ID,
            coprocessor="bytebot",
            invocation_shape={
                "handler": "Claude Code CLI",
                "mode": "fallback_brain",
                "reason": "coprocessor_blocked",
                "original_coprocessor": "Bytebot",
            },
            governance_approved=True,
        )

    return RoutingDecision(
        execution_path=ExecutionPath.USE_BYTEBOT_SANDBOX,
        primary_operator=PRIMARY_OPERATOR_ID,
        coprocessor="bytebot",
        invocation_shape={
            "handler": "Bytebot",
            "mode": "sandbox_tool_coprocessor_for_claude_code",
            "capability": "bytebotd_docker",
            "claude_code_instruction": task.instruction,
            "returns_to": "Claude Code CLI",
            "docker_isolation": True,
        },
        governance_approved=True,
    )


def _route_operator_stack(task: TaskDescriptor) -> RoutingDecision:
    """Route to operator stack as subordinate coprocessor."""
    return RoutingDecision(
        execution_path=ExecutionPath.USE_OPERATOR_STACK,
        primary_operator=PRIMARY_OPERATOR_ID,
        coprocessor="operator",
        invocation_shape={
            "handler": "Operator Stack",
            "mode": "operator_stack_coprocessor_for_claude_code",
            "claude_code_instruction": task.instruction,
            "returns_to": "Claude Code CLI",
        },
        governance_approved=True,
    )


def _route_compose_multiple(task: TaskDescriptor) -> RoutingDecision:
    """
    Claude Code orchestrates multiple coprocessors in sequence/parallel.
    E.g., Scrapling for data + Agent-S for GUI validation + Bytebot for isolation test.
    Claude Code holds the composition plan and unifies the final output.
    """
    compose_plan: List[str] = []

    if task.requires_grounding:
        compose_plan.append("AgentS3.predict")
    if task.has_javascript or task.task_type in ("web_scrape", "web_crawl"):
        compose_plan.append("Scrapling")
    if task.requires_isolation:
        compose_plan.append("Bytebot")

    # Always include Claude Code in the composition
    compose_plan.insert(0, "Claude Code CLI (orchestrator)")

    return RoutingDecision(
        execution_path=ExecutionPath.COMPOSE_MULTIPLE,
        primary_operator=PRIMARY_OPERATOR_ID,
        coprocessor="|".join(compose_plan),
        invocation_shape={
            "handler": "Claude Code CLI",
            "mode": "capability_orchestrator",
            "compose_plan": compose_plan,
            "claude_code_instruction": task.instruction,
            "returns_to": "Claude Code CLI (unifies output)",
        },
        governance_approved=True,
        compose_plan=compose_plan,
    )


# ─── Outcome Recording for M08/M07回流 ─────────────────────────────────────────

def record_outcome_through_claude_code(
    task: TaskDescriptor,
    decision: RoutingDecision,
    outcome: str,
    actual_result: Any = None,
) -> Dict[str, str]:
    """
    All outcome records passed to M08/M07 MUST have Claude Code as primary_operator.

    This function ensures the回流 protocol is respected:
      - Coprocessor results flow back through Claude Code
      - primary_operator field = "Claude Code CLI"
      - supporting_capability = the coprocessor used (if any)
      - orchestration_owner = "Claude Code CLI"
    """
    return get_primary_operator_record(
        supporting_capability=decision.coprocessor or "none (direct)",
        outcome=outcome,
        task_type=task.task_type,
    )


# ─── Public Registry ────────────────────────────────────────────────────────────

def get_coproc_status_summary() -> Dict[str, Any]:
    """Return coprocessor status for health/governance endpoints."""
    return {
        "primary_operator": PRIMARY_OPERATOR_ID,
        "registered_coprocessors": [
            {
                "key": c.capability_key,
                "name": c.short_name,
                "role": c.registry_name,
                "may_claim_completion": c.may_claim_completion,
            }
            for c in REGISTERED_COPROCESSORS
        ],
        "routing_policy": "claude_code_primary | coprocessors_subordinate | no_direct_bypass",
        "claude_code_roles": [
            "primary_operator",
            "general_problem_solver",
            "engineering_executor",
            "capability_orchestrator",
            "fallback_brain",
            "capability_builder",
        ],
    }
