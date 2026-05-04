from backend.app.asset.asset_lifecycle_contract import (
    classify_asset_source,
    classify_lifecycle_tier,
    compute_asset_score_signals,
    detect_asset_lifecycle_risks,
    project_asset_candidate,
    project_memory_asset_candidates,
)


def test_prompt_path_maps_to_a7():
    assert classify_asset_source("prompts/gepa_prompt_signature.md")["asset_category"] == "A7_prompt_instruction"


def test_workflow_path_maps_to_a3():
    assert classify_asset_source("workflow/customer_support_sop.md")["asset_category"] == "A3_workflow_solution"


def test_tool_path_maps_to_a1():
    assert classify_asset_source("tools/mcp_executor_skill.json")["asset_category"] == "A1_tool_capability"


def test_qdrant_graph_path_maps_to_a9():
    assert classify_asset_source("data/qdrant/graphrag/domain_map.sqlite")["asset_category"] == "A9_domain_knowledge_map"


def test_rtcm_final_report_maps_to_cognitive_or_workflow():
    category = classify_asset_source(".deerflow/rtcm/dossiers/s1/final_report.md")["asset_category"]

    assert category in {"A5_cognitive_method", "A3_workflow_solution"}


def test_evidence_ledger_maps_to_source_or_knowledge_map():
    category = classify_asset_source(".deerflow/rtcm/dossiers/s1/evidence_ledger.json")["asset_category"]

    assert category in {"A6_information_source_network", "A9_domain_knowledge_map"}


def test_unknown_source_returns_unknown_warning():
    result = classify_asset_source("misc/blob.bin")

    assert result["asset_category"] == "unknown"
    assert result["warnings"]


def test_lifecycle_tier_none_is_candidate():
    assert classify_lifecycle_tier(None) == "candidate"


def test_lifecycle_tier_record():
    assert classify_lifecycle_tier(20) == "Record"


def test_lifecycle_tier_general():
    assert classify_lifecycle_tier(45) == "General"


def test_lifecycle_tier_available():
    assert classify_lifecycle_tier(65) == "Available"


def test_lifecycle_tier_premium():
    assert classify_lifecycle_tier(82) == "Premium"


def test_lifecycle_tier_core():
    assert classify_lifecycle_tier(95) == "Core"


def test_core_hint_produces_core_warning():
    result = project_asset_candidate("core/strategy_method.md", {"core_hint": True})

    assert result["lifecycle_tier"] == "Core"
    assert result["core_protected"] is True
    assert "core_requires_user_confirmation" in result["warnings"]


def test_compute_asset_score_signals_does_not_forge_missing_score():
    result = compute_asset_score_signals({"frequency": 80, "success_rate": 90})

    assert result["score"] is None
    assert "timeliness" in result["missing_components"]
    assert "missing_score_components" in result["warnings"]


def test_project_memory_asset_candidates_does_not_promote_assets():
    memory_projection = {
        "candidates": [
            {
                "memory_ref_id": "m1",
                "source_path": ".deerflow/rtcm/dossiers/s1/final_report.md",
                "source_system": "rtcm",
                "warnings": [],
            }
        ],
        "warnings": [],
    }

    result = project_memory_asset_candidates(memory_projection)

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["lifecycle_tier"] == "candidate"
    assert result["candidates"][0]["promotion_eligible"] is False


def test_raw_memory_fact_not_direct_formal_asset():
    result = project_asset_candidate({"source_path": "memory/raw_fact.json", "note": "raw memory fact"})

    assert "raw_memory_not_asset" in result["warnings"]
    assert result["lifecycle_tier"] == "candidate"


def test_detect_asset_lifecycle_risks_missing_unknown_core():
    records = [
        project_asset_candidate("unknown/blob.bin"),
        project_asset_candidate("core/domain_strategy.md", {"core_hint": True}),
    ]

    result = detect_asset_lifecycle_risks(records)

    assert result["risk_by_type"]["unknown_asset_category"] == 1
    assert result["risk_by_type"]["missing_score_components"] >= 1
    assert result["risk_by_type"]["core_requires_user_confirmation"] == 1
