"""
Claude Code Primary Role Registry
=================================
M11 — R17-R19 Governance Layer — Primary Operator Identity

THIS FILE IS PART OF THE CORE_IMMUTABLE ARCHITECTURE CONTRACT.

Claude Code CLI is the explicit first-class primary operator of the deerflow system.
All other capabilities (Scrapling, Agent-S, Bytebot, operator stack, MCP, plugins)
are subordinate coprocessors that serve Claude Code's orchestration.

NO capability may claim equal footing with Claude Code as a primary operator.
NO routing path may bypass Claude Code to directly invoke a coprocessor.

====================================================================
SYSTEM STATUS: CORE_ARCHITECTURE_FROZEN | CONTROLLED_EVOLUTION_ENABLED
====================================================================

Role Definitions:
  PRIMARY_OPERATOR:       Claude Code CLI (the general problem solver and orchestrator)
  COP_ROLES:              web_extraction_coprocessor | gui_grounding_coprocessor |
                          sandbox_tool_coprocessor | operator_stack_coprocessor |
                          mcp_coprocessor | plugin_coprocessor
  SYSTEM_OF_RECORD:       M08 (learning) | M07 (asset) — both updated by Claude Code
  GOVERNANCE_ANCHOR:      governance_bridge — validates Claude Code's orchestration decisions

Claude Code's Formal Identities:
  - primary_operator          : receives ALL tasks first; decides execution path
  - general_problem_solver    : handles arbitrary complexity without pre-defined skill
  - engineering_executor      : runs code, builds artifacts, modifies codebase
  - capability_orchestrator   : composes and sequences coprocessors
  - fallback_brain           : invoked when coprocessors fail or are unavailable
  - capability_builder        : generates adapters, wrappers, glue code, playbooks

Claude Code's Invocation Mandate:
  1. ALL tasks enter Claude Code first before any coprocessor is consulted
  2. Claude Code decides: direct_execute | invoke_coprocessor | compose_multiple
  3. Coprocessors return intermediate results to Claude Code only
  4. Claude Code unifies output and determines task completion
  5. Coprocessors MUST NOT bypass Claude Code to claim task completion

Coprocessor Subordination Contract:
  - Scrapling:      web_extraction_coprocessor_for_claude_code
  - Agent-S:        gui_grounding_coprocessor_for_claude_code
  - Bytebot:        sandbox_tool_mode_for_claude_code
  - Operator Stack: operator_stack_coprocessor_for_claude_code
  - MCP:            mcp_coprocessor_for_claude_code
  - Plugins:        plugin_coprocessor_for_claude_code

M08/M07回流协议:
  - primary_operator字段固定为 "Claude Code CLI"
  - supporting_capability字段记录调用的coprocessor
  - orchestration_owner固定为 "Claude Code CLI"
  - 不再接受来自coprocessor的直接回流（必须经Claude Code中转）

This registry is CONTROLLED_EVOLVABLE (adapter contracts may evolve
within the Claude-Code-as-primary-operator structure).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# ─── Claude Code Formal Role Identities ──────────────────────────────────────

PRIMARY_OPERATOR_ID = "Claude Code CLI"
PRIMARY_OPERATOR_VERSION = "1.0"
PRIMARY_OPERATOR_SINCE = "R17"

# The six faces of Claude Code as primary operator
CLAUDE_CODE_ROLES = [
    "primary_operator",
    "general_problem_solver",
    "engineering_executor",
    "capability_orchestrator",
    "fallback_brain",
    "capability_builder",
]

# Capabilities that Claude Code must retain for itself (never delegate away)
CLAUDE_CODE_INHERENT_CAPABILITIES = [
    "code_generation",
    "code_modification",
    "code_deletion",
    "architectural_design",
    "problem_decomposition",
    "workflow_orchestration",
    "adapter_generation",
    "wrapper_generation",
    "glue_code_generation",
    "playbook_generation",
    "recovery_script_generation",
    "diagnostic_analysis",
    "general_purpose_reasoning",
    "multi_step_planning",
    "output_unification",
    "task_completion_determination",
]

# Coprocessor roles and their registry names
COPROCESSOR_REGISTRY = {
    "scrapling":    "web_extraction_coprocessor_for_claude_code",
    "agent_s":      "gui_grounding_coprocessor_for_claude_code",
    "bytebot":      "sandbox_tool_coprocessor_for_claude_code",
    "operator":     "operator_stack_coprocessor_for_claude_code",
    "mcp":          "mcp_coprocessor_for_claude_code",
    "plugin":       "plugin_coprocessor_for_claude_code",
}


# ─── Capability Builder Role Definitions ───────────────────────────────────────

CAPABILITY_BUILDER_SCENARIOS = [
    # Generating new adapters when a new capability needs to be integrated
    {
        "scenario": "new_adapter_generation",
        "claude_code_action": "generate_adapter",
        "description": "Claude Code generates a new Python/TypeScript adapter to integrate a capability",
        "output_type": "adapter_file",
        "governance_required": True,
        "shadow_mode": True,
    },
    # Generating wrapper scripts around existing capabilities
    {
        "scenario": "wrapper_generation",
        "claude_code_action": "generate_wrapper",
        "description": "Claude Code creates a wrapper to expose a capability to the routing layer",
        "output_type": "wrapper_file",
        "governance_required": False,
        "shadow_mode": False,
    },
    # Generating glue code between coprocessors
    {
        "scenario": "glue_code_generation",
        "claude_code_action": "generate_glue",
        "description": "Claude Code writes glue code to connect coprocessor outputs to main chain",
        "output_type": "glue_module",
        "governance_required": False,
        "shadow_mode": False,
    },
    # Generating playbook for complex multi-step operations
    {
        "scenario": "playbook_generation",
        "claude_code_action": "generate_playbook",
        "description": "Claude Code authors a playbook for complex workflows involving multiple coprocessors",
        "output_type": "playbook_file",
        "governance_required": True,
        "shadow_mode": True,
    },
    # Generating recovery scripts when things go wrong
    {
        "scenario": "recovery_script_generation",
        "claude_code_action": "generate_recovery",
        "description": "Claude Code generates diagnostic and recovery scripts",
        "output_type": "recovery_script",
        "governance_required": False,
        "shadow_mode": False,
    },
    # Generating ingestion schemas for new data sources
    {
        "scenario": "ingest_schema_generation",
        "claude_code_action": "generate_schema",
        "description": "Claude Code designs and generates ingestion schemas for new capability outputs",
        "output_type": "schema_file",
        "governance_required": False,
        "shadow_mode": False,
    },
    # Generating new capability integration templates
    {
        "scenario": "integration_template_generation",
        "claude_code_action": "generate_template",
        "description": "Claude Code creates a new capability integration template",
        "output_type": "template_file",
        "governance_required": True,
        "shadow_mode": True,
    },
    # Performing local engineering diagnostics
    {
        "scenario": "engineering_diagnostics",
        "claude_code_action": "diagnose",
        "description": "Claude Code runs local diagnostics on codebase, configuration, or runtime state",
        "output_type": "diagnostic_report",
        "governance_required": False,
        "shadow_mode": False,
    },
]


@dataclass
class CoprocessorDescriptor:
    """Descriptor for a registered coprocessor subordinate to Claude Code."""
    registry_name: str          # e.g. "web_extraction_coprocessor_for_claude_code"
    capability_key: str          # e.g. "scrapling"
    short_name: str              # e.g. "Scrapling"
    invocation_verb: str         # e.g. "invoked_by_claude_code"
    primary_operator_field: str  # Always "Claude Code CLI" in M08/M07 records
    may_claim_completion: bool  # False — only Claude Code determines completion
    governance_gate: str         # Which governance method gates this coprocessor


# ─── Registered Coprocessors ───────────────────────────────────────────────────

REGISTERED_COPROCESSORS: List[CoprocessorDescriptor] = [
    CoprocessorDescriptor(
        registry_name="web_extraction_coprocessor_for_claude_code",
        capability_key="scrapling",
        short_name="Scrapling",
        invocation_verb="invoked_by_claude_code",
        primary_operator_field="Claude Code CLI",
        may_claim_completion=False,
        governance_gate="check_meta_governance",
    ),
    CoprocessorDescriptor(
        registry_name="gui_grounding_coprocessor_for_claude_code",
        capability_key="agent_s",
        short_name="Agent-S",
        invocation_verb="invoked_by_claude_code",
        primary_operator_field="Claude Code CLI",
        may_claim_completion=False,
        governance_gate="check_meta_governance",
    ),
    CoprocessorDescriptor(
        registry_name="sandbox_tool_coprocessor_for_claude_code",
        capability_key="bytebot",
        short_name="Bytebot",
        invocation_verb="invoked_by_claude_code",
        primary_operator_field="Claude Code CLI",
        may_claim_completion=False,
        governance_gate="check_meta_governance",
    ),
    CoprocessorDescriptor(
        registry_name="operator_stack_coprocessor_for_claude_code",
        capability_key="operator",
        short_name="Operator Stack",
        invocation_verb="invoked_by_claude_code",
        primary_operator_field="Claude Code CLI",
        may_claim_completion=False,
        governance_gate="check_meta_governance",
    ),
]


def get_coprocessor_by_key(key: str) -> Optional[CoprocessorDescriptor]:
    return next((c for c in REGISTERED_COPROCESSORS if c.capability_key == key), None)


def get_primary_operator_record(
    supporting_capability: str,
    outcome: str,
    task_type: str,
) -> Dict[str, str]:
    """
    Produce a M08/M07回流 record with Claude Code as primary_operator.

    All回流 records MUST have primary_operator = "Claude Code CLI".
    The supporting_capability field records which coprocessor was used (if any).
    """
    return {
        "primary_operator": PRIMARY_OPERATOR_ID,
        "supporting_capability": supporting_capability,
        "outcome": outcome,
        "task_category": task_type,
        "orchestration_owner": PRIMARY_OPERATOR_ID,
        "routed_by": "claude_code_router",
    }


def is_coprocessor_bypass(task_record: Dict[str, Any]) -> bool:
    """
    Detect if a task record represents a coprocessor bypass attempt
    (a coprocessor trying to claim primary_operator instead of Claude Code).
    """
    primary_op = task_record.get("primary_operator", "")
    return (
        primary_op != "" and
        primary_op != PRIMARY_OPERATOR_ID and
        primary_op not in [c.short_name for c in REGISTERED_COPROCESSORS]
    )
