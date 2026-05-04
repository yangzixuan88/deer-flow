import json
import sys

sys.path.insert(0, ".")


def test_final_report_truth_asset_memory_candidate():
    from app.rtcm.rtcm_integration_contract import project_rtcm_artifact

    artifact = project_rtcm_artifact("rtcm/session1/final_report.md")
    assert artifact["artifact_type"] == "final_report"
    assert artifact["truth_event_eligible"] is True
    assert artifact["asset_candidate_eligible"] is True
    assert artifact["memory_candidate_eligible"] is True
    assert artifact["long_term_memory_eligible"] is True


def test_signoff_rtcm_truth_eligible():
    from app.rtcm.rtcm_integration_contract import project_rtcm_artifact

    artifact = project_rtcm_artifact("rtcm/session1/signoff.json")
    assert artifact["artifact_type"] == "signoff"
    assert artifact["truth_event_eligible"] is True
    assert artifact["asset_candidate_eligible"] is False


def test_evidence_ledger_truth_asset_memory_candidate():
    from app.rtcm.rtcm_integration_contract import project_rtcm_artifact

    artifact = project_rtcm_artifact("rtcm/session1/evidence_ledger.json")
    assert artifact["artifact_type"] == "evidence_ledger"
    assert artifact["truth_event_eligible"] is True
    assert artifact["asset_candidate_eligible"] is True
    assert artifact["memory_candidate_eligible"] is True


def test_council_log_not_long_term_not_asset():
    from app.rtcm.rtcm_integration_contract import project_rtcm_artifact

    artifact = project_rtcm_artifact("rtcm/session1/council_log.md")
    assert artifact["artifact_type"] == "council_log"
    assert artifact["long_term_memory_eligible"] is False
    assert artifact["asset_candidate_eligible"] is False
    assert "council_log_not_long_term_memory" in artifact["warnings"]


def test_followup_candidate():
    from app.rtcm.rtcm_integration_contract import classify_rtcm_artifact

    artifact = classify_rtcm_artifact("rtcm/session1/followup_fix.md")
    assert artifact["artifact_type"] == "followup"
    assert artifact["followup_candidate_eligible"] is True


def test_unknown_artifact_warning():
    from app.rtcm.rtcm_integration_contract import classify_rtcm_artifact

    artifact = classify_rtcm_artifact("rtcm/session1/random.bin")
    assert artifact["artifact_type"] == "unknown"
    assert "unknown_rtcm_artifact_type" in artifact["warnings"]


def test_project_roundtable_session_executor_rtcm():
    from app.rtcm.rtcm_integration_contract import project_roundtable_session

    session = project_roundtable_session("rtcm/session1/manifest.json")
    assert session["executor"] == "rtcm"


def test_truth_candidates_exclude_council_log():
    from app.rtcm.rtcm_integration_contract import project_rtcm_artifact, project_rtcm_truth_candidates

    artifacts = [
        project_rtcm_artifact("rtcm/session1/final_report.md"),
        project_rtcm_artifact("rtcm/session1/council_log.md"),
    ]
    result = project_rtcm_truth_candidates(artifacts)
    assert result["candidate_count"] == 1
    assert result["by_truth_type"]["final_report_conclusion"] == 1


def test_asset_candidates_exclude_council_log():
    from app.rtcm.rtcm_integration_contract import project_rtcm_artifact, project_rtcm_asset_candidates

    artifacts = [
        project_rtcm_artifact("rtcm/session1/evidence_ledger.md"),
        project_rtcm_artifact("rtcm/session1/council_log.md"),
    ]
    result = project_rtcm_asset_candidates(artifacts)
    assert result["candidate_count"] == 1


def test_memory_candidates_exclude_council_log():
    from app.rtcm.rtcm_integration_contract import project_rtcm_artifact, project_rtcm_memory_candidates

    artifacts = [
        project_rtcm_artifact("rtcm/session1/final_report.md"),
        project_rtcm_artifact("rtcm/session1/council_log.md"),
    ]
    result = project_rtcm_memory_candidates(artifacts)
    assert result["candidate_count"] == 1


def test_followups_infer_task_workflow_autonomous():
    from app.rtcm.rtcm_integration_contract import project_rtcm_artifact, project_rtcm_followups

    artifacts = [
        project_rtcm_artifact("rtcm/s1/followup_fix_test.md"),
        project_rtcm_artifact("rtcm/s1/followup_pipeline_plan.md"),
        project_rtcm_artifact("rtcm/s1/followup_monitor_long-running.md"),
    ]
    result = project_rtcm_followups(artifacts)
    assert result["by_target_mode"]["task"] == 1
    assert result["by_target_mode"]["workflow"] == 1
    assert result["by_target_mode"]["autonomous_agent"] == 1


def test_link_rtcm_to_mode_invocation_ok():
    from app.rtcm.rtcm_integration_contract import link_rtcm_to_mode_invocation, project_roundtable_session

    projection = project_roundtable_session({"rtcm_session_id": "s1"})
    invocation = {"mode_invocation_id": "mi1", "mode_session_id": "ms1", "to_mode": "roundtable"}
    result = link_rtcm_to_mode_invocation(projection, invocation)
    assert result["link_ok"] is True
    assert result["linked_projection"]["mode_invocation_id"] == "mi1"


def test_missing_mode_invocation_warning():
    from app.rtcm.rtcm_integration_contract import link_rtcm_to_mode_invocation, project_roundtable_session

    projection = project_roundtable_session({"rtcm_session_id": "s1"})
    result = link_rtcm_to_mode_invocation(projection, None)
    assert "missing_mode_invocation" in result["warnings"]


def test_scan_rtcm_artifacts_tmp_path_no_real_scan(tmp_path):
    from app.rtcm.rtcm_integration_contract import scan_rtcm_artifacts

    session = tmp_path / ".deerflow" / "rtcm" / "s1"
    session.mkdir(parents=True)
    (session / "final_report.md").write_text("do not expose", encoding="utf-8")
    (session / "council_log.md").write_text("do not expose", encoding="utf-8")
    result = scan_rtcm_artifacts(str(tmp_path), max_files=10)
    assert result["classified_count"] == 2
    assert result["by_artifact_type"]["final_report"] == 1
    assert result["by_artifact_type"]["council_log"] == 1
    assert "do not expose" not in json.dumps(result, ensure_ascii=False)


def test_detect_risks_council_log_marked_long_term():
    from app.rtcm.rtcm_integration_contract import detect_rtcm_integration_risks, project_rtcm_artifact

    artifact = project_rtcm_artifact("rtcm/s1/council_log.md")
    artifact["long_term_memory_eligible"] = True
    risks = detect_rtcm_integration_risks({"artifact_projection": {"records": [artifact]}, "truth_candidates": {"candidates": []}, "followups": {"followups": []}})
    assert "council_log_marked_long_term" in risks["risk_by_type"]


def test_generate_sample_writes_only_tmp_path(tmp_path):
    from app.rtcm.rtcm_integration_contract import generate_rtcm_integration_sample

    root = tmp_path / "root"
    session = root / "rtcm" / "s1"
    session.mkdir(parents=True)
    (session / "final_report.md").write_text("report", encoding="utf-8")
    output = tmp_path / "sample.json"
    result = generate_rtcm_integration_sample(str(output), str(root), max_files=10)
    assert result["output_path"] == str(output)
    assert output.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["root", "sample.json"]


def test_does_not_modify_rtcm_runtime(tmp_path):
    from app.rtcm.rtcm_integration_contract import aggregate_rtcm_roundtable_projection

    session = tmp_path / "rtcm" / "s1"
    session.mkdir(parents=True)
    report = session / "final_report.md"
    report.write_text("report", encoding="utf-8")
    before = report.read_text(encoding="utf-8")
    aggregate_rtcm_roundtable_projection(str(tmp_path), max_files=10)
    after = report.read_text(encoding="utf-8")
    assert before == after


def test_no_governance_memory_asset_runtime_write(tmp_path):
    from app.rtcm.rtcm_integration_contract import generate_rtcm_integration_sample

    root = tmp_path / "root"
    root.mkdir()
    output = tmp_path / "sample.json"
    generate_rtcm_integration_sample(str(output), str(root), max_files=10)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["root", "sample.json"]
