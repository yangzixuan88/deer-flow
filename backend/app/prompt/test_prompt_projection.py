import json
import sys

sys.path.insert(0, ".")


def _make_prompt_tree(tmp_path):
    soul = tmp_path / "SOUL.md"
    soul.write_text("SOUL identity base prompt", encoding="utf-8")
    prompt = tmp_path / "prompts" / "task_prompt.md"
    prompt.parent.mkdir()
    prompt.write_text("TASK PROMPT CONTENT SHOULD NOT BE FULLY EXPOSED" * 5, encoding="utf-8")
    dspy = tmp_path / "experiments" / "dspy" / "signature.json"
    dspy.parent.mkdir(parents=True)
    dspy.write_text('{"signature":"candidate"}', encoding="utf-8")
    gepa = tmp_path / "experiments" / "gepa" / "generated_prompt.md"
    gepa.parent.mkdir(parents=True)
    gepa.write_text("GEPA candidate", encoding="utf-8")
    return soul, prompt, dspy, gepa


def test_discover_prompt_runtime_paths_missing_root_warning(tmp_path):
    from app.prompt.prompt_projection import discover_prompt_runtime_paths

    result = discover_prompt_runtime_paths(str(tmp_path / "missing"))
    assert "root_missing" in result["warnings"]


def test_load_prompt_source_snapshot_missing_file_warning(tmp_path):
    from app.prompt.prompt_projection import load_prompt_source_snapshot

    result = load_prompt_source_snapshot(str(tmp_path / "missing.md"))
    assert result["exists"] is False
    assert "source_missing" in result["warnings"]


def test_load_prompt_source_snapshot_hash_no_full_content(tmp_path):
    from app.prompt.prompt_projection import load_prompt_source_snapshot

    content = "SECRET_PROMPT_CONTENT_SHOULD_NOT_FULLY_APPEAR_" * 10
    path = tmp_path / "prompt.md"
    path.write_text(content, encoding="utf-8")
    result = load_prompt_source_snapshot(str(path))
    dumped = json.dumps(result, ensure_ascii=False)
    assert result["sha256"]
    assert result["size_bytes"] == len(content.encode("utf-8"))
    assert content not in dumped


def test_project_prompt_sources_tmp_path_soul_prompt_dspy_gepa(tmp_path):
    from app.prompt.prompt_projection import project_prompt_sources

    _make_prompt_tree(tmp_path)
    result = project_prompt_sources(str(tmp_path), max_files=20)
    assert result["classified_count"] >= 4
    assert result["by_source_type"]["soul"] == 1
    assert result["by_source_type"]["dspy_candidate"] == 1
    assert result["by_source_type"]["gepa_candidate"] == 1


def test_project_prompt_sources_no_full_content(tmp_path):
    from app.prompt.prompt_projection import project_prompt_sources

    _, prompt, _, _ = _make_prompt_tree(tmp_path)
    secret = prompt.read_text(encoding="utf-8")
    result = project_prompt_sources(str(tmp_path), max_files=20)
    assert secret not in json.dumps(result, ensure_ascii=False)


def test_project_prompt_replacement_risks_critical_high(tmp_path):
    from app.prompt.prompt_projection import project_prompt_replacement_risks, project_prompt_sources

    _make_prompt_tree(tmp_path)
    records = project_prompt_sources(str(tmp_path), max_files=20)["records"]
    result = project_prompt_replacement_risks(records)
    assert result["critical_replacement_count"] >= 1
    assert result["high_replacement_count"] >= 1


def test_project_prompt_asset_candidates_includes_dspy_gepa(tmp_path):
    from app.prompt.prompt_projection import project_prompt_asset_candidates, project_prompt_sources

    _make_prompt_tree(tmp_path)
    records = project_prompt_sources(str(tmp_path), max_files=20)["records"]
    result = project_prompt_asset_candidates(records)
    source_types = result["by_source_type"]
    assert source_types["dspy_candidate"] == 1
    assert source_types["gepa_candidate"] == 1


def test_project_prompt_asset_candidates_excludes_soul_ordinary_a7(tmp_path):
    from app.prompt.prompt_projection import project_prompt_asset_candidates, project_prompt_sources

    _make_prompt_tree(tmp_path)
    records = project_prompt_sources(str(tmp_path), max_files=20)["records"]
    result = project_prompt_asset_candidates(records)
    protected_types = {item["source_type"] for item in result["protected_sources"]}
    assert "soul" in protected_types


def test_detect_prompt_governance_risks_critical_without_rollback(tmp_path):
    from app.prompt.prompt_projection import aggregate_prompt_projection

    _make_prompt_tree(tmp_path)
    result = aggregate_prompt_projection(str(tmp_path), max_files=20)
    assert "critical_prompt_without_rollback" in result["risk_signals"]["risk_by_type"]


def test_detect_prompt_governance_risks_generated_candidate_without_test(tmp_path):
    from app.prompt.prompt_projection import aggregate_prompt_projection

    _make_prompt_tree(tmp_path)
    result = aggregate_prompt_projection(str(tmp_path), max_files=20)
    assert "generated_prompt_candidate_without_test" in result["risk_signals"]["risk_by_type"]


def test_aggregate_prompt_projection_source_risk_asset(tmp_path):
    from app.prompt.prompt_projection import aggregate_prompt_projection

    _make_prompt_tree(tmp_path)
    result = aggregate_prompt_projection(str(tmp_path), max_files=20)
    assert "source_projection" in result
    assert "replacement_risks" in result
    assert "asset_candidates" in result
    assert result["summary"]["classified_count"] >= 4


def test_generate_prompt_projection_report_writes_only_tmp_path(tmp_path):
    from app.prompt.prompt_projection import generate_prompt_projection_report

    root = tmp_path / "root"
    root.mkdir()
    _make_prompt_tree(root)
    output = tmp_path / "sample.json"
    result = generate_prompt_projection_report(str(output), str(root), max_files=20)
    assert result["output_path"] == str(output)
    assert output.exists()
    assert "source_projection" in json.loads(output.read_text(encoding="utf-8"))
    assert sorted(path.name for path in tmp_path.iterdir()) == ["root", "sample.json"]


def test_max_files_reached_warning(tmp_path):
    from app.prompt.prompt_projection import project_prompt_sources

    _make_prompt_tree(tmp_path)
    result = project_prompt_sources(str(tmp_path), max_files=1)
    assert "max_files_reached" in result["warnings"]


def test_does_not_modify_real_prompt_file(tmp_path):
    from app.prompt.prompt_projection import aggregate_prompt_projection

    soul, _, _, _ = _make_prompt_tree(tmp_path)
    before = soul.read_text(encoding="utf-8")
    aggregate_prompt_projection(str(tmp_path), max_files=20)
    after = soul.read_text(encoding="utf-8")
    assert before == after


def test_does_not_enable_gepa_dspy(tmp_path):
    import app.prompt.prompt_projection as projection

    _make_prompt_tree(tmp_path)
    result = projection.aggregate_prompt_projection(str(tmp_path), max_files=20)
    assert result["source_projection"]["optimization_candidates_count"] >= 2
    assert not hasattr(projection, "run_gepa")
    assert not hasattr(projection, "run_dspy")
