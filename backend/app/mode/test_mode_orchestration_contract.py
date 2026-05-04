from pathlib import Path

from backend.app.mode.mode_orchestration_contract import (
    build_mode_call_graph,
    complete_mode_invocation,
    create_mode_invocation,
    create_mode_session,
    generate_mode_callgraph_sample,
    summarize_mode_call_graph,
    validate_mode_invocation_policy,
)


def test_create_mode_session_auto_includes_primary_mode():
    session = create_mode_session("task", active_modes=["search"])

    assert "task" in session["active_modes"]
    assert "search" in session["active_modes"]


def test_create_mode_session_dedupes_active_modes():
    session = create_mode_session("task", active_modes=["task", "search", "search"])

    assert session["active_modes"].count("task") == 1
    assert session["active_modes"].count("search") == 1


def test_invalid_primary_mode_maps_unknown_warning():
    session = create_mode_session("bad_mode")

    assert session["primary_mode"] == "unknown"
    assert session["warnings"]


def test_create_mode_invocation_task_to_search():
    invocation = create_mode_invocation("s1", "task", "search", "collect evidence")

    assert invocation["from_mode"] == "task"
    assert invocation["to_mode"] == "search"
    assert invocation["status"] == "planned"


def test_create_mode_invocation_roundtable_executor_rtcm():
    invocation = create_mode_invocation("s1", "task", "roundtable", "review", executor="rtcm")

    assert invocation["to_mode"] == "roundtable"
    assert invocation["executor"] == "rtcm"


def test_complete_mode_invocation_generates_mode_result():
    invocation = create_mode_invocation("s1", "task", "search", "collect")

    result = complete_mode_invocation(invocation, "evidence_summary", output_refs=["ref1"])

    assert result["updated_invocation"]["status"] == "completed"
    assert result["mode_result"]["result_type"] == "evidence_summary"
    assert result["mode_result"]["output_refs"] == ["ref1"]


def test_build_mode_call_graph_nodes_edges():
    session = create_mode_session("task", active_modes=["search"])
    invocation = create_mode_invocation(session["mode_session_id"], "task", "search", "collect")

    graph = build_mode_call_graph(session, [invocation])

    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1


def test_summarize_mode_call_graph_counts_from_to():
    session = create_mode_session("task", active_modes=["search", "roundtable"])
    invocations = [
        create_mode_invocation(session["mode_session_id"], "task", "search", "collect"),
        create_mode_invocation(session["mode_session_id"], "task", "roundtable", "review", executor="rtcm"),
    ]
    graph = build_mode_call_graph(session, invocations)

    summary = summarize_mode_call_graph(graph)

    assert summary["by_from_mode"]["task"] == 2
    assert summary["by_to_mode"]["search"] == 1
    assert summary["roundtable_invocation_count"] == 1


def test_policy_detects_roundtable_executor_missing():
    invocation = create_mode_invocation("s1", "task", "roundtable", "review")

    result = validate_mode_invocation_policy(invocation)

    assert "roundtable_executor_missing_when_to_mode_roundtable" in result["warnings"]


def test_policy_detects_invalid_mode():
    invocation = create_mode_invocation("s1", "bad", "search", "x")

    result = validate_mode_invocation_policy(invocation)

    assert "invalid_mode" in result["warnings"]


def test_switch_primary_mode_without_reason_warns():
    invocation = create_mode_invocation("s1", "task", "workflow", "", return_policy="switch_primary_mode")

    result = validate_mode_invocation_policy(invocation)

    assert "switch_primary_mode_requires_reason" in result["warnings"]


def test_clarification_to_autonomous_agent_warns():
    invocation = create_mode_invocation("s1", "clarification", "autonomous_agent", "bad")

    result = validate_mode_invocation_policy(invocation)

    assert "clarification_should_not_call_autonomous_agent" in result["warnings"]


def test_generate_mode_callgraph_sample_writes_tmp_path(tmp_path):
    output = tmp_path / "mode_sample.json"

    result = generate_mode_callgraph_sample(str(output))

    assert result["written"] is True
    assert output.exists()


def test_no_external_action_side_effect(tmp_path):
    output = tmp_path / "sample.json"

    generate_mode_callgraph_sample(str(output))

    assert list(tmp_path.iterdir()) == [output]


def test_does_not_write_governance_memory_asset_runtime(tmp_path):
    output = tmp_path / "sample.json"

    result = generate_mode_callgraph_sample(str(output))

    assert Path(result["output_path"]) == output
    assert "migration_reports" not in str(output)
