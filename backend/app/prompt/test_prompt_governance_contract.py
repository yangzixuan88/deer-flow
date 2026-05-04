import json
import sys

sys.path.insert(0, ".")


def test_soul_md_maps_p6_critical_warning():
    from app.prompt.prompt_governance_contract import classify_prompt_source

    record = classify_prompt_source("SOUL.md")
    assert record["source_type"] == "soul"
    assert record["priority_layer"] == "P6_identity_base"
    assert record["risk_level"] == "critical"
    assert "soul_is_identity_base_not_highest_override" in record["warnings"]


def test_hard_constraint_prompt_maps_p1():
    from app.prompt.prompt_governance_contract import classify_prompt_source

    record = classify_prompt_source("prompts/hard_constraints/root_guard_prompt.md")
    assert record["priority_layer"] == "P1_hard_constraints"


def test_user_preference_maps_p2():
    from app.prompt.prompt_governance_contract import classify_prompt_source

    record = classify_prompt_source("user/preferences/high_autonomy.md", {"source_type": "user_preference"})
    assert record["priority_layer"] == "P2_user_preferences"


def test_mode_orchestration_prompt_maps_p3():
    from app.prompt.prompt_governance_contract import classify_prompt_source

    record = classify_prompt_source("prompts/mode_orchestration_prompt.md")
    assert record["priority_layer"] == "P3_mode_collaboration"


def test_skill_prompt_maps_p4():
    from app.prompt.prompt_governance_contract import classify_prompt_source

    record = classify_prompt_source("skills/code/SKILL.md")
    assert record["priority_layer"] == "P4_task_skill"


def test_runtime_context_prompt_maps_p5():
    from app.prompt.prompt_governance_contract import classify_prompt_source

    record = classify_prompt_source("runtime/context_prompt.md")
    assert record["priority_layer"] == "P5_runtime_context"


def test_dspy_candidate_asset_candidate():
    from app.prompt.prompt_governance_contract import classify_prompt_source

    record = classify_prompt_source("experiments/dspy/signature.json")
    assert record["source_type"] == "dspy_candidate"
    assert record["optimization_status"] == "candidate"
    assert record["asset_candidate_eligible"] is True


def test_gepa_candidate_replacement_warning():
    from app.prompt.prompt_governance_contract import classify_prompt_source

    record = classify_prompt_source("experiments/gepa/generated_prompt.md")
    assert record["source_type"] == "gepa_candidate"
    assert "generated_prompt_requires_test_backup_rollback" in record["warnings"]


def test_p1_vs_p6_conflict_p1_wins():
    from app.prompt.prompt_governance_contract import classify_prompt_source, resolve_prompt_conflict

    p1 = classify_prompt_source("prompts/hard_constraints/root_guard_prompt.md")
    p6 = classify_prompt_source("SOUL.md")
    result = resolve_prompt_conflict(p1, p6)
    assert result["decision"] == "source_a_wins"
    assert result["winning_layer"] == "P1_hard_constraints"


def test_p2_vs_p4_conflict_p2_wins():
    from app.prompt.prompt_governance_contract import classify_prompt_source, resolve_prompt_conflict

    p2 = classify_prompt_source("user/preferences/high_autonomy.md", {"source_type": "user_preference"})
    p4 = classify_prompt_source("skills/code/SKILL.md")
    result = resolve_prompt_conflict(p2, p4)
    assert result["decision"] == "source_a_wins"
    assert result["winning_layer"] == "P2_user_preferences"


def test_same_layer_conflict_requires_review():
    from app.prompt.prompt_governance_contract import classify_prompt_source, resolve_prompt_conflict

    a = classify_prompt_source("skills/code/SKILL.md")
    b = classify_prompt_source("skills/test/SKILL.md")
    result = resolve_prompt_conflict(a, b)
    assert result["decision"] == "requires_review"
    assert "same_layer_conflict_requires_review" in result["warnings"]


def test_unknown_cannot_override_known():
    from app.prompt.prompt_governance_contract import classify_prompt_source, resolve_prompt_conflict

    unknown = classify_prompt_source("misc/random.txt")
    known = classify_prompt_source("skills/code/SKILL.md")
    result = resolve_prompt_conflict(unknown, known)
    assert result["decision"] == "source_b_wins"
    assert "unknown_layer_cannot_override_known_layer" in result["warnings"]


def test_soul_replacement_requires_backup_rollback_user_confirmation():
    from app.prompt.prompt_governance_contract import assess_prompt_replacement_risk, classify_prompt_source

    record = classify_prompt_source("SOUL.md")
    risk = assess_prompt_replacement_risk(record)
    assert risk["risk_level"] == "critical"
    assert risk["requires_backup"] is True
    assert risk["requires_rollback"] is True
    assert risk["requires_user_confirmation"] is True


def test_dspy_candidate_cannot_direct_replace_production():
    from app.prompt.prompt_governance_contract import assess_prompt_replacement_risk, classify_prompt_source

    record = classify_prompt_source("experiments/dspy/signature.json")
    risk = assess_prompt_replacement_risk(record)
    assert risk["replacement_allowed"] is False
    assert "generated_candidate_cannot_directly_replace_production" in risk["warnings"]


def test_prompt_asset_candidate_a7_for_reusable_prompt():
    from app.prompt.prompt_governance_contract import classify_prompt_source, project_prompt_asset_candidate

    record = classify_prompt_source("skills/code/SKILL.md")
    candidate = project_prompt_asset_candidate(record)
    assert candidate["asset_candidate_eligible"] is True
    assert candidate["asset_category"] == "A7_prompt_instruction"


def test_p1_hard_constraint_not_ordinary_a7_asset():
    from app.prompt.prompt_governance_contract import classify_prompt_source, project_prompt_asset_candidate

    record = classify_prompt_source("prompts/hard_constraints/root_guard_prompt.md")
    candidate = project_prompt_asset_candidate(record)
    assert candidate["asset_candidate_eligible"] is False
    assert candidate["asset_category"] == "protected_hard_constraint_source"


def test_scan_prompt_sources_tmp_path_no_full_content(tmp_path):
    from app.prompt.prompt_governance_contract import scan_prompt_sources

    secret_content = "FULL_PROMPT_CONTENT_SHOULD_NOT_APPEAR"
    prompt_file = tmp_path / "skills" / "code" / "SKILL.md"
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text(secret_content, encoding="utf-8")
    result = scan_prompt_sources(str(tmp_path), max_files=10)
    dumped = json.dumps(result, ensure_ascii=False)
    assert result["classified_count"] == 1
    assert secret_content not in dumped


def test_generate_prompt_governance_sample_writes_only_tmp_path(tmp_path):
    from app.prompt.prompt_governance_contract import generate_prompt_governance_sample

    output = tmp_path / "prompt_sample.json"
    result = generate_prompt_governance_sample(str(output))
    assert result["output_path"] == str(output)
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert len(data["records"]) >= 7
    assert sorted(path.name for path in tmp_path.iterdir()) == ["prompt_sample.json"]
