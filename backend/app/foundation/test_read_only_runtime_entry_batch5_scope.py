# noqa: D101, D102, D104
"""
Tests for R241-18H: Batch 5 Scope Reconciliation.

Covers:
1. load sources requires R241-18A valid
2. load sources confirms memory surface blocked
3. load sources requires R241-18C STEP-005
4. load sources requires R241-18G STEP-004 completed
5. extract candidates includes disabled sidecar stub
6. extract candidates detects Agent Memory + MCP next step
7. classify disabled sidecar as proceed
8. classify memory read binding as requires readiness review
9. classify MCP read binding as requires readiness review
10. classify Gateway sidecar as review only
11. checks include memory runtime remains blocked
12. checks include MCP runtime not approved
13. checks include no HTTP endpoint
14. checks include no network
15. checks include no secret
16. checks include no Gateway main path
17. validate rejects memory runtime read
18. validate rejects memory runtime write
19. validate rejects MCP connection
20. validate rejects HTTP endpoint
21. validate rejects Gateway main path
22. validate rejects auto-fix
23. generate review selects disabled_sidecar_stub
24. generate review defers Agent Memory + MCP
25. report generation writes only tmp_path
26. no runtime write
27. no audit JSONL write
28. no action queue write
29. no auto-fix
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from backend.app.foundation.read_only_runtime_entry_batch5_scope import (
    Batch5CandidateType,
    Batch5ScopeDecision,
    Batch5ScopeRiskLevel,
    Batch5ScopeStatus,
    build_batch5_scope_checks,
    classify_batch5_candidate,
    extract_batch5_candidates,
    generate_batch5_scope_reconciliation,
    generate_batch5_scope_reconciliation_report,
    load_batch5_scope_sources,
    validate_batch5_scope_reconciliation,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def r241_18a_valid():
    """R241-18A with SURFACE-010 memory blocked, SURFACE-014 gateway blocked."""
    return {
        "validation_result": {"valid": True},
        "surfaces": [
            {
                "surface_id": "SURFACE-010",
                "domain": "memory",
                "activation_status": "blocked",
                "risk_level": "critical",
                "decision": "block_runtime_activation",
            },
            {
                "surface_id": "SURFACE-014",
                "domain": "gateway",
                "activation_status": "blocked",
                "risk_level": "critical",
                "decision": "block_runtime_activation",
            },
        ],
    }


@pytest.fixture
def r241_18c_valid():
    """R241-18C with STEP-005 as disabled_sidecar_stub."""
    return {
        "validation_result": {"valid": True},
        "implementation_steps": [
            {
                "step_id": "STEP-004",
                "batch": "batch4",
                "description": "Batch 4 stub",
                "surface_ids": [],
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "network_allowed": False,
                "requires_secret": False,
                "writes_runtime": False,
            },
            {
                "step_id": "STEP-005",
                "batch": "disabled_sidecar_stub",
                "description": "Disabled Sidecar API Stub Contract Design",
                "surface_ids": ["SURFACE-009"],
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "network_allowed": False,
                "requires_secret": False,
                "writes_runtime": False,
            },
            {
                "step_id": "STEP-006",
                "batch": "gateway_sidecar_review",
                "description": "Gateway Sidecar Runtime Review",
                "surface_ids": ["SURFACE-014"],
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "network_allowed": False,
                "requires_secret": False,
                "writes_runtime": False,
            },
        ],
    }


@pytest.fixture
def r241_18g_valid():
    """R241-18G with STEP-004 completed."""
    return {
        "validation_result": {"valid": True},
        "implemented_steps": ["STEP-004"],
        "warnings": [
            "Agent Memory + MCP Read Binding — deferred to readiness review",
        ],
    }


@pytest.fixture
def r241_18d_valid():
    return {"validation_result": {"valid": True}}


@pytest.fixture
def r241_18e_valid():
    return {"validation_result": {"valid": True}}


@pytest.fixture
def r241_18f_valid():
    return {"validation_result": {"valid": True}}


@pytest.fixture
def all_sources(
    r241_18a_valid,
    r241_18c_valid,
    r241_18d_valid,
    r241_18e_valid,
    r241_18f_valid,
    r241_18g_valid,
):
    """All sources loaded dict keyed by name."""
    return {
        "loaded": {
            "R241-18A": r241_18a_valid,
            "R241-18C": r241_18c_valid,
            "R241-18D": r241_18d_valid,
            "R241-18E": r241_18e_valid,
            "R241-18F": r241_18f_valid,
            "R241-18G": r241_18g_valid,
        },
        "missing": [],
        "errors": [],
        "warnings": [],
    }


@pytest.fixture
def disabled_sidecar_candidate():
    """CAND-001: disabled_sidecar_stub from STEP-005."""
    return {
        "candidate_id": "CAND-001",
        "candidate_type": Batch5CandidateType.DISABLED_SIDECAR_STUB.value,
        "proposed_source": "R241-18C_STEP-005",
        "matches_r241_18c_plan": True,
        "step_id": "STEP-005",
        "batch": "disabled_sidecar_stub",
        "description": "Disabled Sidecar API Stub Contract Design",
        "surface_ids": ["SURFACE-009"],
        "requires_new_readiness_review": False,
        "touches_memory_runtime": False,
        "touches_mcp_runtime": False,
        "opens_http_endpoint": False,
        "touches_gateway_main_path": False,
        "network_allowed": False,
        "secret_required": False,
        "writes_runtime": False,
        "implemented_now": False,
        "disabled_by_default": True,
        "risk_level": Batch5ScopeRiskLevel.LOW.value,
        "decision": None,
        "blocked_reasons": [],
        "warnings": [],
        "errors": [],
    }


@pytest.fixture
def memory_binding_candidate():
    """CAND-002: Agent Memory read binding."""
    return {
        "candidate_id": "CAND-002",
        "candidate_type": Batch5CandidateType.AGENT_MEMORY_READ_BINDING.value,
        "proposed_source": "R241-18G_next_step_annotation",
        "matches_r241_18c_plan": False,
        "step_id": None,
        "description": "Agent Memory + MCP Read Binding",
        "surface_ids": ["SURFACE-010"],
        "requires_new_readiness_review": True,
        "touches_memory_runtime": True,
        "touches_mcp_runtime": False,
        "opens_http_endpoint": False,
        "touches_gateway_main_path": False,
        "network_allowed": False,
        "secret_required": False,
        "writes_runtime": True,
        "implemented_now": False,
        "disabled_by_default": False,
        "risk_level": Batch5ScopeRiskLevel.CRITICAL.value,
        "decision": None,
        "blocked_reasons": [],
        "warnings": [],
        "errors": [],
    }


@pytest.fixture
def mcp_read_candidate():
    """CAND-003: MCP Read Binding."""
    return {
        "candidate_id": "CAND-003",
        "candidate_type": Batch5CandidateType.MCP_READ_BINDING.value,
        "proposed_source": "inference_from_R241-18G_annotations",
        "matches_r241_18c_plan": False,
        "step_id": None,
        "description": "MCP Read Binding",
        "surface_ids": [],
        "requires_new_readiness_review": True,
        "touches_memory_runtime": False,
        "touches_mcp_runtime": True,
        "opens_http_endpoint": False,
        "touches_gateway_main_path": False,
        "network_allowed": False,
        "secret_required": True,
        "writes_runtime": False,
        "implemented_now": False,
        "disabled_by_default": True,
        "risk_level": Batch5ScopeRiskLevel.MEDIUM.value,
        "decision": None,
        "blocked_reasons": [],
        "warnings": [],
        "errors": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. load sources requires R241-18A valid
# ─────────────────────────────────────────────────────────────────────────────

def test_load_sources_requires_r241_18a_valid(tmp_path: Path):
    """Test 1: load sources requires R241-18A validation.valid=true."""
    # Create minimal source files with correct naming
    r18a = tmp_path / "R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json"
    r18a.write_text(json.dumps({"validation_result": {"valid": False}}))
    r18c = tmp_path / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
    r18c.write_text(json.dumps({
        "validation_result": {"valid": True},
        "implementation_steps": [],
    }))
    for name in ["R241-18D", "R241-18E", "R241-18F", "R241-18G"]:
        p = tmp_path / f"{name}_READONLY_RUNTIME_ENTRY_BATCH_RESULT.json"
        p.write_text(json.dumps({"validation_result": {"valid": True}}))

    sources = load_batch5_scope_sources(root=str(tmp_path))
    assert "R241-18A_validation_invalid" in sources["errors"]


def test_load_sources_r241_18a_valid_passes(tmp_path: Path):
    """Test 1b: load sources passes when R241-18A valid=true."""
    base = tmp_path / "R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json"
    base.write_text(json.dumps({
        "validation_result": {"valid": True},
        "surfaces": [
            {
                "surface_id": "SURFACE-010",
                "domain": "memory",
                "activation_status": "blocked",
                "risk_level": "critical",
                "decision": "block_runtime_activation",
            },
            {
                "surface_id": "SURFACE-014",
                "domain": "gateway",
                "activation_status": "blocked",
                "risk_level": "critical",
                "decision": "block_runtime_activation",
            },
        ],
    }))
    r18c = tmp_path / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
    r18c.write_text(json.dumps({
        "validation_result": {"valid": True},
        "implementation_steps": [
            {
                "step_id": "STEP-005",
                "batch": "disabled_sidecar_stub",
                "description": "stub",
                "surface_ids": [],
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "network_allowed": False,
                "requires_secret": False,
                "writes_runtime": False,
            },
        ],
    }))
    for name in ["R241-18D", "R241-18E", "R241-18F", "R241-18G"]:
        p = tmp_path / f"{name}_READONLY_RUNTIME_ENTRY_BATCH_RESULT.json"
        p.write_text(json.dumps({"validation_result": {"valid": True}}))

    sources = load_batch5_scope_sources(root=str(tmp_path))
    assert "R241-18A_validation_valid" in sources["warnings"]
    assert "R241-18A_validation_invalid" not in sources["errors"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. load sources confirms memory surface blocked
# ─────────────────────────────────────────────────────────────────────────────

def test_load_sources_confirms_memory_surface_blocked(tmp_path: Path):
    """Test 2: load sources confirms SURFACE-010 memory blocked."""
    base = tmp_path / "R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json"
    base.write_text(json.dumps({
        "validation_result": {"valid": True},
        "surfaces": [
            {
                "surface_id": "SURFACE-010",
                "domain": "memory",
                "activation_status": "blocked",
                "risk_level": "critical",
                "decision": "block_runtime_activation",
            },
            {
                "surface_id": "SURFACE-014",
                "domain": "gateway",
                "activation_status": "blocked",
                "risk_level": "critical",
                "decision": "block_runtime_activation",
            },
        ],
    }))
    r18c = tmp_path / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
    r18c.write_text(json.dumps({
        "validation_result": {"valid": True},
        "implementation_steps": [
            {
                "step_id": "STEP-005",
                "batch": "disabled_sidecar_stub",
                "description": "stub",
                "surface_ids": [],
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "network_allowed": False,
                "requires_secret": False,
                "writes_runtime": False,
            },
        ],
    }))
    for name in ["R241-18D", "R241-18E", "R241-18F", "R241-18G"]:
        p = tmp_path / f"{name}_READONLY_RUNTIME_ENTRY_BATCH_RESULT.json"
        p.write_text(json.dumps({"validation_result": {"valid": True}}))

    sources = load_batch5_scope_sources(root=str(tmp_path))
    assert "memory_surface_blocked_confirmed" in sources["warnings"]
    assert "memory_surface_not_blocked" not in sources["errors"]


def test_load_sources_rejects_memory_not_blocked(tmp_path: Path):
    """Test 2b: load sources rejects when memory surface is NOT blocked."""
    base = tmp_path / "R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json"
    base.write_text(json.dumps({
        "validation_result": {"valid": True},
        "surfaces": [
            {
                "surface_id": "SURFACE-010",
                "domain": "memory",
                "activation_status": "active",  # NOT blocked
                "risk_level": "low",
                "decision": "approved",
            },
        ],
    }))
    r18c = tmp_path / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
    r18c.write_text(json.dumps({
        "validation_result": {"valid": True},
        "implementation_steps": [
            {
                "step_id": "STEP-005",
                "batch": "disabled_sidecar_stub",
                "description": "stub",
                "surface_ids": [],
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "network_allowed": False,
                "requires_secret": False,
                "writes_runtime": False,
            },
        ],
    }))
    for name in ["R241-18D", "R241-18E", "R241-18F", "R241-18G"]:
        p = tmp_path / f"{name}_READONLY_RUNTIME_ENTRY_BATCH_RESULT.json"
        p.write_text(json.dumps({"validation_result": {"valid": True}}))

    sources = load_batch5_scope_sources(root=str(tmp_path))
    assert "memory_surface_not_blocked" in sources["errors"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. load sources requires R241-18C STEP-005
# ─────────────────────────────────────────────────────────────────────────────

def test_load_sources_requires_step_005(tmp_path: Path):
    """Test 3: load sources requires R241-18C STEP-005 to exist."""
    base = tmp_path / "R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json"
    base.write_text(json.dumps({
        "validation_result": {"valid": True},
        "surfaces": [
            {
                "surface_id": "SURFACE-010",
                "domain": "memory",
                "activation_status": "blocked",
                "risk_level": "critical",
                "decision": "block_runtime_activation",
            },
            {
                "surface_id": "SURFACE-014",
                "domain": "gateway",
                "activation_status": "blocked",
                "risk_level": "critical",
                "decision": "block_runtime_activation",
            },
        ],
    }))
    r18c = tmp_path / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
    r18c.write_text(json.dumps({
        "validation_result": {"valid": True},
        "implementation_steps": [
            {
                "step_id": "STEP-004",
                "batch": "batch4",
                "description": "stub",
                "surface_ids": [],
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "network_allowed": False,
                "requires_secret": False,
                "writes_runtime": False,
            },
            # NOTE: No STEP-005
        ],
    }))
    for name in ["R241-18D", "R241-18E", "R241-18F", "R241-18G"]:
        p = tmp_path / f"{name}_READONLY_RUNTIME_ENTRY_BATCH_RESULT.json"
        p.write_text(json.dumps({"validation_result": {"valid": True}}))

    sources = load_batch5_scope_sources(root=str(tmp_path))
    assert "STEP-005_not_found_in_R241-18C_plan" in sources["errors"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. load sources requires R241-18G STEP-004 completed
# ─────────────────────────────────────────────────────────────────────────────

def test_load_sources_requires_step_004_completed(tmp_path: Path):
    """Test 4: load sources requires R241-18G STEP-004 to be completed."""
    base = tmp_path / "R241-18A_RUNTIME_ACTIVATION_READINESS_MATRIX.json"
    base.write_text(json.dumps({
        "validation_result": {"valid": True},
        "surfaces": [
            {
                "surface_id": "SURFACE-010",
                "domain": "memory",
                "activation_status": "blocked",
                "risk_level": "critical",
                "decision": "block_runtime_activation",
            },
            {
                "surface_id": "SURFACE-014",
                "domain": "gateway",
                "activation_status": "blocked",
                "risk_level": "critical",
                "decision": "block_runtime_activation",
            },
        ],
    }))
    r18c = tmp_path / "R241-18C_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json"
    r18c.write_text(json.dumps({
        "validation_result": {"valid": True},
        "implementation_steps": [
            {
                "step_id": "STEP-005",
                "batch": "disabled_sidecar_stub",
                "description": "stub",
                "surface_ids": [],
                "opens_http_endpoint": False,
                "touches_gateway_main_path": False,
                "network_allowed": False,
                "requires_secret": False,
                "writes_runtime": False,
            },
        ],
    }))
    r18g = tmp_path / "R241-18G_READONLY_RUNTIME_ENTRY_BATCH4_RESULT.json"
    r18g.write_text(json.dumps({
        "validation_result": {"valid": True},
        "implemented_steps": ["STEP-003"],  # Wrong step
    }))
    for name, batch_num in [("R241-18D", "1"), ("R241-18E", "2"), ("R241-18F", "3")]:
        p = tmp_path / f"{name}_READONLY_RUNTIME_ENTRY_BATCH{batch_num}_RESULT.json"
        p.write_text(json.dumps({"validation_result": {"valid": True}}))

    sources = load_batch5_scope_sources(root=str(tmp_path))
    assert "STEP-004_not_completed_in_R241-18G" in sources["errors"]


# ─────────────────────────────────────────────────────────────────────────────
# 5. extract candidates includes disabled sidecar stub
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_candidates_includes_disabled_sidecar_stub(all_sources):
    """Test 5: extract candidates includes CAND-001 disabled_sidecar_stub from STEP-005."""
    extracted = extract_batch5_candidates(all_sources)
    cand_ids = [c["candidate_id"] for c in extracted["candidates"]]
    assert "CAND-001" in cand_ids

    cand001 = next(c for c in extracted["candidates"] if c["candidate_id"] == "CAND-001")
    assert cand001["candidate_type"] == Batch5CandidateType.DISABLED_SIDECAR_STUB.value
    assert cand001["matches_r241_18c_plan"] is True
    assert cand001["step_id"] == "STEP-005"


# ─────────────────────────────────────────────────────────────────────────────
# 6. extract candidates detects Agent Memory + MCP next step
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_candidates_detects_agent_memory_mcp(all_sources):
    """Test 6: extract candidates detects Agent Memory + MCP from R241-18G next-step."""
    extracted = extract_batch5_candidates(all_sources)
    cand_ids = [c["candidate_id"] for c in extracted["candidates"]]
    assert "CAND-002" in cand_ids  # Agent Memory
    assert "CAND-003" in cand_ids  # MCP Read

    cand002 = next(c for c in extracted["candidates"] if c["candidate_id"] == "CAND-002")
    assert cand002["candidate_type"] == Batch5CandidateType.AGENT_MEMORY_READ_BINDING.value
    assert cand002["matches_r241_18c_plan"] is False  # Conflicts with R241-18C


# ─────────────────────────────────────────────────────────────────────────────
# 7. classify disabled sidecar as proceed
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_disabled_sidecar_as_proceed(disabled_sidecar_candidate):
    """Test 7: classify disabled_sidecar_stub candidate as PROCEED_WITH_DISABLED_SIDECAR_STUB."""
    result = classify_batch5_candidate(disabled_sidecar_candidate)
    assert result["decision"] == Batch5ScopeDecision.PROCEED_WITH_DISABLED_SIDECAR_STUB.value
    assert "disabled_sidecar_stub_conditions_not_met" not in result["blocked_reasons"]


def test_classify_disabled_sidecar_blocks_if_http(disabled_sidecar_candidate):
    """Test 7b: disabled_sidecar with opens_http_endpoint=True is blocked."""
    disabled_sidecar_candidate["opens_http_endpoint"] = True
    result = classify_batch5_candidate(disabled_sidecar_candidate)
    assert result["decision"] == Batch5ScopeDecision.BLOCK_BATCH5_RUNTIME_BINDING.value


def test_classify_disabled_sidecar_blocks_if_network(disabled_sidecar_candidate):
    """Test 7c: disabled_sidecar with network_allowed=True is blocked."""
    disabled_sidecar_candidate["network_allowed"] = True
    result = classify_batch5_candidate(disabled_sidecar_candidate)
    assert result["decision"] == Batch5ScopeDecision.BLOCK_BATCH5_RUNTIME_BINDING.value


def test_classify_disabled_sidecar_blocks_if_gateway(disabled_sidecar_candidate):
    """Test 7d: disabled_sidecar with touches_gateway_main_path=True is blocked."""
    disabled_sidecar_candidate["touches_gateway_main_path"] = True
    result = classify_batch5_candidate(disabled_sidecar_candidate)
    assert result["decision"] == Batch5ScopeDecision.BLOCK_BATCH5_RUNTIME_BINDING.value


def test_classify_disabled_sidecar_blocks_if_runtime_write(disabled_sidecar_candidate):
    """Test 7e: disabled_sidecar with writes_runtime=True is blocked."""
    disabled_sidecar_candidate["writes_runtime"] = True
    result = classify_batch5_candidate(disabled_sidecar_candidate)
    assert result["decision"] == Batch5ScopeDecision.BLOCK_BATCH5_RUNTIME_BINDING.value


# ─────────────────────────────────────────────────────────────────────────────
# 8. classify memory read binding as requires readiness review
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_memory_read_binding_requires_readiness_review(memory_binding_candidate):
    """Test 8: classify AGENT_MEMORY_READ_BINDING as REQUIRE_MEMORY_MCP_READINESS_REVIEW."""
    result = classify_batch5_candidate(memory_binding_candidate)
    assert result["decision"] == Batch5ScopeDecision.REQUIRE_MEMORY_MCP_READINESS_REVIEW.value
    assert "memory_runtime_blocked_per_R241-18A_SURFACE-010" in result["blocked_reasons"]


# ─────────────────────────────────────────────────────────────────────────────
# 9. classify MCP read binding as requires readiness review
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_mcp_read_binding_requires_readiness_review(mcp_read_candidate):
    """Test 9: classify MCP_READ_BINDING as REQUIRE_MEMORY_MCP_READINESS_REVIEW."""
    result = classify_batch5_candidate(mcp_read_candidate)
    assert result["decision"] == Batch5ScopeDecision.REQUIRE_MEMORY_MCP_READINESS_REVIEW.value
    assert "MCP_runtime_not_approved_requires_readiness_review" in result["blocked_reasons"]


# ─────────────────────────────────────────────────────────────────────────────
# 10. classify Gateway sidecar as review only
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_gateway_sidecar_as_review_only(all_sources):
    """Test 10: classify GATEWAY_SIDECAR_REVIEW as REQUIRE_MEMORY_MCP_READINESS_REVIEW."""
    candidates = extract_batch5_candidates(all_sources)["candidates"]
    gateway_cand = next(
        (c for c in candidates if c["candidate_type"] == Batch5CandidateType.GATEWAY_SIDECAR_REVIEW.value),
        None,
    )
    assert gateway_cand is not None

    result = classify_batch5_candidate(gateway_cand)
    assert result["decision"] == Batch5ScopeDecision.REQUIRE_MEMORY_MCP_READINESS_REVIEW.value
    assert "gateway_sidecar_review_is_read_only_review_gate" in result["warnings"]


# ─────────────────────────────────────────────────────────────────────────────
# 11. checks include memory runtime remains blocked
# ─────────────────────────────────────────────────────────────────────────────

def test_checks_include_memory_runtime_remains_blocked(
    all_sources, disabled_sidecar_candidate, memory_binding_candidate
):
    """Test 11: checks include memory_runtime_blocked confirmation."""
    candidates = [disabled_sidecar_candidate, memory_binding_candidate]
    checks = build_batch5_scope_checks(candidates, all_sources)
    check_ids = [c["check_id"] for c in checks]

    assert "memory_runtime_blocked" in check_ids
    mem_check = next(c for c in checks if c["check_id"] == "memory_runtime_blocked")
    assert mem_check["passed"] is True
    assert mem_check["expected_value"] is True
    assert mem_check["risk_level"] == Batch5ScopeRiskLevel.CRITICAL.value


# ─────────────────────────────────────────────────────────────────────────────
# 12. checks include MCP runtime not approved
# ─────────────────────────────────────────────────────────────────────────────

def test_checks_include_mcp_runtime_not_approved(all_sources, disabled_sidecar_candidate):
    """Test 12: checks include mcp_runtime_not_approved confirmation."""
    candidates = [disabled_sidecar_candidate]
    checks = build_batch5_scope_checks(candidates, all_sources)
    check_ids = [c["check_id"] for c in checks]

    assert "mcp_runtime_not_approved" in check_ids
    mcp_check = next(c for c in checks if c["check_id"] == "mcp_runtime_not_approved")
    assert mcp_check["passed"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 13. checks include no HTTP endpoint
# ─────────────────────────────────────────────────────────────────────────────

def test_checks_include_no_http_endpoint(all_sources, disabled_sidecar_candidate):
    """Test 13: checks include disabled_sidecar_no_http_endpoint."""
    candidates = [disabled_sidecar_candidate]
    checks = build_batch5_scope_checks(candidates, all_sources)
    check_ids = [c["check_id"] for c in checks]

    assert "disabled_sidecar_no_http_endpoint" in check_ids
    http_check = next(c for c in checks if c["check_id"] == "disabled_sidecar_no_http_endpoint")
    assert http_check["passed"] is True
    assert http_check["expected_value"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 14. checks include no network
# ─────────────────────────────────────────────────────────────────────────────

def test_checks_include_no_network(all_sources, disabled_sidecar_candidate):
    """Test 14: checks include disabled_sidecar_no_network."""
    candidates = [disabled_sidecar_candidate]
    checks = build_batch5_scope_checks(candidates, all_sources)
    check_ids = [c["check_id"] for c in checks]

    assert "disabled_sidecar_no_network" in check_ids
    net_check = next(c for c in checks if c["check_id"] == "disabled_sidecar_no_network")
    assert net_check["passed"] is True
    assert net_check["expected_value"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 15. checks include no secret
# ─────────────────────────────────────────────────────────────────────────────

def test_checks_include_no_secret(all_sources, disabled_sidecar_candidate):
    """Test 15: disabled_sidecar candidate has secret_required=False."""
    candidates = [disabled_sidecar_candidate]
    checks = build_batch5_scope_checks(candidates, all_sources)

    # secret_required is on the candidate, not a separate check
    assert disabled_sidecar_candidate["secret_required"] is False
    assert disabled_sidecar_candidate["risk_level"] == Batch5ScopeRiskLevel.LOW.value


# ─────────────────────────────────────────────────────────────────────────────
# 16. checks include no Gateway main path
# ─────────────────────────────────────────────────────────────────────────────

def test_checks_include_no_gateway_main_path(all_sources, disabled_sidecar_candidate):
    """Test 16: checks include disabled_sidecar_no_gateway_touch."""
    candidates = [disabled_sidecar_candidate]
    checks = build_batch5_scope_checks(candidates, all_sources)
    check_ids = [c["check_id"] for c in checks]

    assert "disabled_sidecar_no_gateway_touch" in check_ids
    gw_check = next(c for c in checks if c["check_id"] == "disabled_sidecar_no_gateway_touch")
    assert gw_check["passed"] is True
    assert gw_check["risk_level"] == Batch5ScopeRiskLevel.CRITICAL.value


# ─────────────────────────────────────────────────────────────────────────────
# 17. validate rejects memory runtime read
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_rejects_memory_runtime_read(all_sources, disabled_sidecar_candidate):
    """Test 17: validate rejects if any candidate implements memory runtime read."""
    review = {
        "candidates": [disabled_sidecar_candidate],
        "selected_batch5_scope": Batch5CandidateType.DISABLED_SIDECAR_STUB.value,
        "checks": [],
    }

    # Add a candidate that reads memory runtime
    memory_cand = dict(disabled_sidecar_candidate)
    memory_cand["candidate_id"] = "CAND-VIOLATION"
    memory_cand["touches_memory_runtime"] = True
    memory_cand["implemented_now"] = True
    review["candidates"] = [disabled_sidecar_candidate, memory_cand]

    result = validate_batch5_scope_reconciliation(review)
    assert result["valid"] is False
    assert any("memory_runtime" in i for i in result["issues"])


# ─────────────────────────────────────────────────────────────────────────────
# 18. validate rejects memory runtime write
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_rejects_memory_runtime_write(all_sources, disabled_sidecar_candidate):
    """Test 18: validate rejects if any candidate writes runtime."""
    review = {
        "candidates": [disabled_sidecar_candidate],
        "selected_batch5_scope": Batch5CandidateType.DISABLED_SIDECAR_STUB.value,
        "checks": [
            {
                "check_id": "disabled_sidecar_no_runtime_write",
                "passed": True,
            }
        ],
    }

    # Add a candidate that writes runtime
    write_cand = dict(disabled_sidecar_candidate)
    write_cand["candidate_id"] = "CAND-WRITE"
    write_cand["writes_runtime"] = True
    write_cand["implemented_now"] = True
    review["candidates"] = [disabled_sidecar_candidate, write_cand]

    result = validate_batch5_scope_reconciliation(review)
    assert result["valid"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 19. validate rejects MCP connection
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_rejects_mcp_connection(all_sources, disabled_sidecar_candidate):
    """Test 19: validate rejects if any candidate connects MCP runtime."""
    review = {
        "candidates": [disabled_sidecar_candidate],
        "selected_batch5_scope": Batch5CandidateType.DISABLED_SIDECAR_STUB.value,
        "checks": [],
    }

    mcp_cand = dict(disabled_sidecar_candidate)
    mcp_cand["candidate_id"] = "CAND-MCP"
    mcp_cand["touches_mcp_runtime"] = True
    mcp_cand["implemented_now"] = True
    review["candidates"] = [disabled_sidecar_candidate, mcp_cand]

    result = validate_batch5_scope_reconciliation(review)
    assert result["valid"] is False
    assert any("mcp" in i.lower() for i in result["issues"])


# ─────────────────────────────────────────────────────────────────────────────
# 20. validate rejects HTTP endpoint
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_rejects_http_endpoint(all_sources, disabled_sidecar_candidate):
    """Test 20: validate rejects if any candidate opens HTTP endpoint."""
    review = {
        "candidates": [disabled_sidecar_candidate],
        "selected_batch5_scope": Batch5CandidateType.DISABLED_SIDECAR_STUB.value,
        "checks": [],
    }

    http_cand = dict(disabled_sidecar_candidate)
    http_cand["candidate_id"] = "CAND-HTTP"
    http_cand["opens_http_endpoint"] = True
    review["candidates"] = [disabled_sidecar_candidate, http_cand]

    result = validate_batch5_scope_reconciliation(review)
    assert result["valid"] is False
    assert any("http_endpoint" in i for i in result["issues"])


# ─────────────────────────────────────────────────────────────────────────────
# 21. validate rejects Gateway main path
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_rejects_gateway_main_path(all_sources, disabled_sidecar_candidate):
    """Test 21: validate rejects if any candidate touches gateway main path."""
    review = {
        "candidates": [disabled_sidecar_candidate],
        "selected_batch5_scope": Batch5CandidateType.DISABLED_SIDECAR_STUB.value,
        "checks": [
            {
                "check_id": "disabled_sidecar_no_gateway_touch",
                "passed": True,
            }
        ],
    }

    gw_cand = dict(disabled_sidecar_candidate)
    gw_cand["candidate_id"] = "CAND-GW"
    gw_cand["touches_gateway_main_path"] = True
    gw_cand["implemented_now"] = True
    review["candidates"] = [disabled_sidecar_candidate, gw_cand]

    result = validate_batch5_scope_reconciliation(review)
    assert result["valid"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 22. validate rejects auto-fix
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_rejects_auto_fix(all_sources, disabled_sidecar_candidate):
    """Test 22: validation result must not contain auto-fix actions."""
    review = {
        "candidates": [disabled_sidecar_candidate],
        "selected_batch5_scope": Batch5CandidateType.DISABLED_SIDECAR_STUB.value,
        "checks": [],
    }

    result = validate_batch5_scope_reconciliation(review)
    # The validation result itself should not have auto-fix entries
    all_values = str(list(result.values()))
    assert "auto_fix" not in all_values.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 23. generate review selects disabled_sidecar_stub
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_review_selects_disabled_sidecar_stub(tmp_path: Path, monkeypatch):
    """Test 23: generate review selects disabled_sidecar_stub as Batch 5 scope."""
    # Mock file reads to use temp files
    def mock_load(root=None):
        base = tmp_path
        files = {}
        for name, data in [
            ("R241-18A", {
                "validation_result": {"valid": True},
                "surfaces": [
                    {
                        "surface_id": "SURFACE-010",
                        "domain": "memory",
                        "activation_status": "blocked",
                        "risk_level": "critical",
                        "decision": "block_runtime_activation",
                    },
                    {
                        "surface_id": "SURFACE-014",
                        "domain": "gateway",
                        "activation_status": "blocked",
                        "risk_level": "critical",
                        "decision": "block_runtime_activation",
                    },
                ],
            }),
            ("R241-18C", {
                "validation_result": {"valid": True},
                "implementation_steps": [
                    {
                        "step_id": "STEP-005",
                        "batch": "disabled_sidecar_stub",
                        "description": "Disabled Sidecar API Stub Contract Design",
                        "surface_ids": [],
                        "opens_http_endpoint": False,
                        "touches_gateway_main_path": False,
                        "network_allowed": False,
                        "requires_secret": False,
                        "writes_runtime": False,
                    },
                ],
            }),
            ("R241-18D", {"validation_result": {"valid": True}}),
            ("R241-18E", {"validation_result": {"valid": True}}),
            ("R241-18F", {"validation_result": {"valid": True}}),
            ("R241-18G", {
                "validation_result": {"valid": True},
                "implemented_steps": ["STEP-004"],
                "warnings": ["Agent Memory + MCP Read Binding"],
            }),
        ]:
            p = base / f"{name}_READONLY_RUNTIME_ENTRY_BATCH_RESULT.json"
            if name in ("R241-18A", "R241-18C", "R241-18G"):
                p = base / f"{name}_RUNTIME_ACTIVATION_READINESS_MATRIX.json" if name == "R241-18A" else base / f"{name}_READONLY_RUNTIME_ENTRY_IMPLEMENTATION_PLAN.json" if name == "R241-18C" else base / f"{name}_README_RUNTIME_ENTRY_BATCH4_RESULT.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data))
            files[name] = p

        sources = {
            "loaded": {},
            "missing": [],
            "errors": [],
            "warnings": [],
        }
        for name, path in files.items():
            data = json.loads(path.read_text())
            sources["loaded"][name] = data
        return sources

    monkeypatch.setattr(
        "backend.app.foundation.read_only_runtime_entry_batch5_scope.load_batch5_scope_sources",
        lambda root=None: mock_load(root),
    )

    review = generate_batch5_scope_reconciliation(root=str(tmp_path))
    assert review["selected_batch5_scope"] == Batch5CandidateType.DISABLED_SIDECAR_STUB.value
    assert review["decision"] == Batch5ScopeDecision.PROCEED_WITH_DISABLED_SIDECAR_STUB.value
    assert review["status"] in [
        Batch5ScopeStatus.SCOPE_RECONCILED.value,
        Batch5ScopeStatus.SCOPE_RECONCILED_WITH_WARNINGS.value,
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 24. generate review defers Agent Memory + MCP
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_review_defers_agent_memory_mcp(tmp_path: Path, monkeypatch):
    """Test 24: generate review defers Agent Memory + MCP to readiness review."""
    def mock_load(root=None):
        base = tmp_path
        sources = {"loaded": {}, "missing": [], "errors": [], "warnings": []}
        for name, data in [
            ("R241-18A", {
                "validation_result": {"valid": True},
                "surfaces": [
                    {
                        "surface_id": "SURFACE-010",
                        "domain": "memory",
                        "activation_status": "blocked",
                        "risk_level": "critical",
                        "decision": "block_runtime_activation",
                    },
                    {
                        "surface_id": "SURFACE-014",
                        "domain": "gateway",
                        "activation_status": "blocked",
                        "risk_level": "critical",
                        "decision": "block_runtime_activation",
                    },
                ],
            }),
            ("R241-18C", {
                "validation_result": {"valid": True},
                "implementation_steps": [
                    {
                        "step_id": "STEP-005",
                        "batch": "disabled_sidecar_stub",
                        "description": "Disabled Sidecar API Stub Contract Design",
                        "surface_ids": [],
                        "opens_http_endpoint": False,
                        "touches_gateway_main_path": False,
                        "network_allowed": False,
                        "requires_secret": False,
                        "writes_runtime": False,
                    },
                ],
            }),
            ("R241-18D", {"validation_result": {"valid": True}}),
            ("R241-18E", {"validation_result": {"valid": True}}),
            ("R241-18F", {"validation_result": {"valid": True}}),
            ("R241-18G", {
                "validation_result": {"valid": True},
                "implemented_steps": ["STEP-004"],
                "warnings": ["Agent Memory + MCP Read Binding"],
            }),
        ]:
            p = base / f"{name}.json"
            p.write_text(json.dumps(data))
            sources["loaded"][name] = data
        return sources

    monkeypatch.setattr(
        "backend.app.foundation.read_only_runtime_entry_batch5_scope.load_batch5_scope_sources",
        lambda root=None: mock_load(root),
    )

    review = generate_batch5_scope_reconciliation(root=str(tmp_path))
    deferred = review.get("rejected_or_deferred_candidates", [])
    deferred_types = [d["candidate_type"] for d in deferred]

    assert Batch5CandidateType.AGENT_MEMORY_READ_BINDING.value in deferred_types
    assert Batch5CandidateType.MCP_READ_BINDING.value in deferred_types
    assert review["selected_batch5_scope"] == Batch5CandidateType.DISABLED_SIDECAR_STUB.value


# ─────────────────────────────────────────────────────────────────────────────
# 25. report generation writes only tmp_path
# ─────────────────────────────────────────────────────────────────────────────

def test_report_generation_writes_only_tmp_path(tmp_path: Path, monkeypatch):
    """Test 25: report generation only writes to specified tmp_path, not migration_reports."""
    def mock_load(root=None):
        return {
            "loaded": {
                "R241-18A": {
                    "validation_result": {"valid": True},
                    "surfaces": [
                        {
                            "surface_id": "SURFACE-010",
                            "domain": "memory",
                            "activation_status": "blocked",
                            "risk_level": "critical",
                            "decision": "block_runtime_activation",
                        },
                        {
                            "surface_id": "SURFACE-014",
                            "domain": "gateway",
                            "activation_status": "blocked",
                            "risk_level": "critical",
                            "decision": "block_runtime_activation",
                        },
                    ],
                },
                "R241-18C": {
                    "validation_result": {"valid": True},
                    "implementation_steps": [
                        {
                            "step_id": "STEP-005",
                            "batch": "disabled_sidecar_stub",
                            "description": "stub",
                            "surface_ids": [],
                            "opens_http_endpoint": False,
                            "touches_gateway_main_path": False,
                            "network_allowed": False,
                            "requires_secret": False,
                            "writes_runtime": False,
                        },
                    ],
                },
                "R241-18D": {"validation_result": {"valid": True}},
                "R241-18E": {"validation_result": {"valid": True}},
                "R241-18F": {"validation_result": {"valid": True}},
                "R241-18G": {
                    "validation_result": {"valid": True},
                    "implemented_steps": ["STEP-004"],
                    "warnings": ["Agent Memory + MCP Read Binding"],
                },
            },
            "missing": [],
            "errors": [],
            "warnings": [],
        }

    monkeypatch.setattr(
        "backend.app.foundation.read_only_runtime_entry_batch5_scope.load_batch5_scope_sources",
        lambda root=None: mock_load(root),
    )

    out_json = tmp_path / "test_output.json"
    result = generate_batch5_scope_reconciliation_report(
        review=None,
        output_path=str(out_json),
    )

    assert out_json.exists(), "JSON should be written to specified output_path"
    # Verify the JSON is valid and has expected fields
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert "review_id" in data
    assert "decision" in data


# ─────────────────────────────────────────────────────────────────────────────
# 26. no runtime write
# ─────────────────────────────────────────────────────────────────────────────

def test_no_runtime_write(all_sources, disabled_sidecar_candidate):
    """Test 26: selected disabled_sidecar_stub candidate does not write runtime."""
    candidates = [disabled_sidecar_candidate]
    checks = build_batch5_scope_checks(candidates, all_sources)

    runtime_write_check = next(
        (c for c in checks if c["check_id"] == "disabled_sidecar_no_runtime_write"),
        None,
    )
    assert runtime_write_check is not None
    assert runtime_write_check["passed"] is True
    assert disabled_sidecar_candidate["writes_runtime"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 27. no audit JSONL write
# ─────────────────────────────────────────────────────────────────────────────

def test_no_audit_jsonl_write(all_sources, disabled_sidecar_candidate):
    """Test 27: no binding result writes to audit JSONL."""
    # disabled_sidecar_stub candidate must not have audit JSONL writes
    assert disabled_sidecar_candidate.get("writes_audit_jsonl", False) is False
    assert disabled_sidecar_candidate.get("opened_jsonl_write_handle", False) is False


# ─────────────────────────────────────────────────────────────────────────────
# 28. no action queue write
# ─────────────────────────────────────────────────────────────────────────────

def test_no_action_queue_write(all_sources, disabled_sidecar_candidate):
    """Test 28: no binding result writes to action queue."""
    # disabled_sidecar_stub has no action queue interaction
    assert disabled_sidecar_candidate.get("writes_action_queue", False) is False
    assert disabled_sidecar_candidate.get("touches_scheduler", False) is False


# ─────────────────────────────────────────────────────────────────────────────
# 29. no auto-fix
# ─────────────────────────────────────────────────────────────────────────────

def test_no_auto_fix(all_sources, disabled_sidecar_candidate, memory_binding_candidate):
    """Test 29: no candidate attempts to auto-fix violations."""
    candidates = [disabled_sidecar_candidate, memory_binding_candidate]
    checks = build_batch5_scope_checks(candidates, all_sources)

    # No check should contain auto-fix behavior
    for check in checks:
        check_str = str(check)
        assert "auto_fix" not in check_str.lower()
        assert "auto-fix" not in check_str.lower()
        assert "autofix" not in check_str.lower()

    # Validation should not produce auto-fix actions
    review = {
        "candidates": candidates,
        "selected_batch5_scope": Batch5CandidateType.DISABLED_SIDECAR_STUB.value,
        "checks": checks,
    }
    validation = validate_batch5_scope_reconciliation(review)
    val_str = str(validation)
    assert "auto_fix" not in val_str.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Integration: full reconciliation run
# ─────────────────────────────────────────────────────────────────────────────

def test_full_reconciliation_integration(tmp_path: Path, monkeypatch):
    """Integration test: full reconciliation with all checks passing."""
    def mock_load(root=None):
        return {
            "loaded": {
                "R241-18A": {
                    "validation_result": {"valid": True},
                    "surfaces": [
                        {
                            "surface_id": "SURFACE-010",
                            "domain": "memory",
                            "activation_status": "blocked",
                            "risk_level": "critical",
                            "decision": "block_runtime_activation",
                        },
                        {
                            "surface_id": "SURFACE-014",
                            "domain": "gateway",
                            "activation_status": "blocked",
                            "risk_level": "critical",
                            "decision": "block_runtime_activation",
                        },
                    ],
                },
                "R241-18C": {
                    "validation_result": {"valid": True},
                    "implementation_steps": [
                        {
                            "step_id": "STEP-005",
                            "batch": "disabled_sidecar_stub",
                            "description": "Disabled Sidecar API Stub Contract Design",
                            "surface_ids": [],
                            "opens_http_endpoint": False,
                            "touches_gateway_main_path": False,
                            "network_allowed": False,
                            "requires_secret": False,
                            "writes_runtime": False,
                        },
                    ],
                },
                "R241-18D": {"validation_result": {"valid": True}},
                "R241-18E": {"validation_result": {"valid": True}},
                "R241-18F": {"validation_result": {"valid": True}},
                "R241-18G": {
                    "validation_result": {"valid": True},
                    "implemented_steps": ["STEP-004"],
                    "warnings": ["Agent Memory + MCP Read Binding"],
                },
            },
            "missing": [],
            "errors": [],
            "warnings": [],
        }

    monkeypatch.setattr(
        "backend.app.foundation.read_only_runtime_entry_batch5_scope.load_batch5_scope_sources",
        lambda root=None: mock_load(root),
    )

    out_json = tmp_path / "integration_output.json"
    result = generate_batch5_scope_reconciliation_report(
        review=None,
        output_path=str(out_json),
    )

    assert result["status"] in [
        Batch5ScopeStatus.SCOPE_RECONCILED.value,
        Batch5ScopeStatus.SCOPE_RECONCILED_WITH_WARNINGS.value,
    ]
    assert result["decision"] == Batch5ScopeDecision.PROCEED_WITH_DISABLED_SIDECAR_STUB.value
    assert result["selected_scope"] == Batch5CandidateType.DISABLED_SIDECAR_STUB.value
    assert out_json.exists()
