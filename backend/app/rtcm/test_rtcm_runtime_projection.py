import sys

sys.path.insert(0, ".")


def _session_tree(tmp_path):
    root = tmp_path / "rtcm" / "sessions" / "s1"
    dossier = root / "project_dossier"
    runtime = root / "runtime"
    dossier.mkdir(parents=True)
    runtime.mkdir()
    (dossier / "manifest.json").write_text("{}", encoding="utf-8")
    (runtime / "session_state.json").write_text("{}", encoding="utf-8")
    (dossier / "final_report.md").write_text("final", encoding="utf-8")
    (dossier / "evidence_ledger.json").write_text("{}", encoding="utf-8")
    (dossier / "council_log.jsonl").write_text("log", encoding="utf-8")
    return root


def test_config_yaml_classification():
    from app.rtcm.rtcm_runtime_projection import classify_rtcm_runtime_path

    result = classify_rtcm_runtime_path("rtcm/config/default.yaml")
    assert result["surface_type"] == "rtcm_config_spec"
    assert result["runtime_role"] == "config"


def test_prompt_md_classification():
    from app.rtcm.rtcm_runtime_projection import classify_rtcm_runtime_path

    result = classify_rtcm_runtime_path("rtcm/prompts/council.md")
    assert result["surface_type"] == "rtcm_prompt_template"
    assert result["runtime_role"] == "prompt"


def test_docs_md_classification():
    from app.rtcm.rtcm_runtime_projection import classify_rtcm_runtime_path

    result = classify_rtcm_runtime_path("rtcm/docs/overview.md")
    assert result["surface_type"] == "rtcm_docs"
    assert result["runtime_role"] == "documentation"


def test_source_code_classification():
    from app.rtcm.rtcm_runtime_projection import classify_rtcm_runtime_path

    result = classify_rtcm_runtime_path("backend/src/rtcm/foo.ts")
    assert result["surface_type"] == "rtcm_source_code"
    assert result["runtime_role"] == "source"


def test_test_file_classification():
    from app.rtcm.rtcm_runtime_projection import classify_rtcm_runtime_path

    result = classify_rtcm_runtime_path("backend/src/rtcm/foo_test.mjs")
    assert result["surface_type"] == "rtcm_test_file"
    assert result["runtime_role"] == "test"


def test_session_state_classification():
    from app.rtcm.rtcm_runtime_projection import classify_rtcm_runtime_path

    result = classify_rtcm_runtime_path("rtcm/s1/runtime/session_state.json")
    assert result["surface_type"] == "rtcm_runtime_state"
    assert result["runtime_role"] == "session_state"


def test_evidence_extract_classification():
    from app.rtcm.rtcm_runtime_projection import classify_rtcm_runtime_path

    result = classify_rtcm_runtime_path("rtcm/s1/runtime/evidence_extracts/a.json")
    assert result["surface_type"] == "rtcm_evidence_extract"
    assert result["runtime_role"] == "evidence"


def test_project_dossier_final_report_candidates():
    from app.rtcm.rtcm_runtime_projection import project_rtcm_runtime_path

    result = project_rtcm_runtime_path("rtcm/s1/project_dossier/final_report.md")
    assert result["runtime_role"] == "final_decision"
    assert result["truth_candidate_eligible"] is True
    assert result["asset_candidate_eligible"] is True
    assert result["memory_candidate_eligible"] is True


def test_project_dossier_evidence_ledger_candidates():
    from app.rtcm.rtcm_runtime_projection import project_rtcm_runtime_path

    result = project_rtcm_runtime_path("rtcm/s1/project_dossier/evidence_ledger.json")
    assert result["runtime_role"] == "evidence"
    assert result["truth_candidate_eligible"] is True
    assert result["asset_candidate_eligible"] is True
    assert result["memory_candidate_eligible"] is True


def test_project_dossier_council_log_not_long_term():
    from app.rtcm.rtcm_runtime_projection import project_rtcm_runtime_path

    result = project_rtcm_runtime_path("rtcm/s1/project_dossier/council_log.jsonl")
    assert result["runtime_role"] == "council_transcript"
    assert result["memory_candidate_eligible"] is False
    assert "council_log_not_long_term_memory" in result["warnings"]


def test_discover_sessions_project_dossier(tmp_path):
    from app.rtcm.rtcm_runtime_projection import discover_rtcm_sessions

    _session_tree(tmp_path)
    result = discover_rtcm_sessions(str(tmp_path), max_files=100)
    assert result["session_count"] == 1
    session = result["sessions"][0]
    assert session["has_manifest"] is True
    assert session["has_final_report"] is True
    assert session["has_evidence_ledger"] is True
    assert session["has_council_log"] is True


def test_project_session_runtime_aggregates(tmp_path):
    from app.rtcm.rtcm_runtime_projection import project_rtcm_session_runtime

    root = _session_tree(tmp_path)
    result = project_rtcm_session_runtime(str(root))
    assert result["final_report_refs"]
    assert result["evidence_refs"]
    assert result["council_log_refs"]


def test_context_links_with_context():
    from app.rtcm.rtcm_runtime_projection import project_rtcm_context_links

    session = {"rtcm_session_id": "s1"}
    result = project_rtcm_context_links(session, context_envelope={"context_id": "ctx", "request_id": "req", "thread_id": "thread"})
    assert len(result["links"]) == 2
    assert result["warnings"] == []


def test_context_links_missing_context_warning():
    from app.rtcm.rtcm_runtime_projection import project_rtcm_context_links

    result = project_rtcm_context_links({"rtcm_session_id": "s1"})
    assert "missing_context_link" in result["warnings"]


def test_source_code_not_truth_candidate():
    from app.rtcm.rtcm_runtime_projection import project_rtcm_runtime_path

    result = project_rtcm_runtime_path("backend/src/rtcm/foo.ts")
    assert result["truth_candidate_eligible"] is False


def test_prompt_template_not_truth_candidate():
    from app.rtcm.rtcm_runtime_projection import project_rtcm_runtime_path

    result = project_rtcm_runtime_path("rtcm/prompts/council.md")
    assert result["truth_candidate_eligible"] is False


def test_detect_risks_missing_context_link(tmp_path):
    from app.rtcm.rtcm_runtime_projection import detect_rtcm_runtime_projection_risks, discover_rtcm_sessions, scan_rtcm_runtime_projection

    _session_tree(tmp_path)
    projection = {
        "runtime_path_projection": scan_rtcm_runtime_projection(str(tmp_path), max_files=100),
        "session_discovery": discover_rtcm_sessions(str(tmp_path), max_files=100),
    }
    risks = detect_rtcm_runtime_projection_risks(projection)
    assert "session_missing_context_link" in risks["risk_by_type"]


def test_generate_report_writes_only_tmp_path(tmp_path):
    from app.rtcm.rtcm_runtime_projection import generate_rtcm_runtime_projection_report

    root = tmp_path / "root"
    _session_tree(root)
    output = tmp_path / "sample.json"
    result = generate_rtcm_runtime_projection_report(str(output), str(root), max_files=100)
    assert result["output_path"] == str(output)
    assert output.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["root", "sample.json"]


def test_does_not_modify_rtcm_runtime(tmp_path):
    from app.rtcm.rtcm_runtime_projection import generate_rtcm_runtime_projection_report

    root = _session_tree(tmp_path)
    report = root / "project_dossier" / "final_report.md"
    before = report.read_text(encoding="utf-8")
    generate_rtcm_runtime_projection_report(str(tmp_path / "sample.json"), str(tmp_path), max_files=100)
    after = report.read_text(encoding="utf-8")
    assert before == after


def test_no_governance_memory_asset_runtime_write(tmp_path):
    from app.rtcm.rtcm_runtime_projection import generate_rtcm_runtime_projection_report

    root = tmp_path / "root"
    root.mkdir()
    output = tmp_path / "sample.json"
    generate_rtcm_runtime_projection_report(str(output), str(root), max_files=100)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["root", "sample.json"]
